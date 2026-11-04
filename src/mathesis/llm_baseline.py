"""Baseline B0: pass@k of a local LLM prover on the Lean pilot benchmark.

Pipeline per problem: build a constant prompt from the statement header, sample
k completions with mlx_lm (one batch of k), extract the proof, rebuild the full
file from the *fixed* header plus the proof, and check it with `lake env lean`.

PROMPT TEMPLATE (constant; PROMPT_TEMPLATE below), sent as one user turn through
the tokenizer's chat template (non-CoT prompt of DeepSeek-Prover-V2):

    Complete the following Lean 4 code:

    ```lean4
    <header: imports, namespace and the theorem statement up to and including ':= by'>
    ```

Statement integrity: the candidate file is always <header> + <proof body> +
<footer> from the benchmark file. If the model restates the theorem, its
statement must match the benchmark statement (whitespace-insensitive), otherwise
the sample fails with `statement_mismatch`; only the text after `:= by` is kept.

A candidate passes only if Lean exits 0, the proof text and Lean output contain no
`sorry`/`admit`/`axiom` token, and the Lean output contains no `error`.
`native_decide` and `set_option` are not rejected.
"""

import atexit
import json
import math
import os
import random
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from mathesis.lean_pilot import default_lean_pilot_dir, load_lean_pilot
from mathesis.proof_rules import FORBIDDEN_RE, find_forbidden, find_forbidden_in_proof
from mathesis.runlog import default_repo_root, derive_seed

BACKENDS = ("transformers", "mlx")
DEFAULT_BACKEND = "transformers"
MLX_MODEL_NAME = "mlx-community/DeepSeek-Prover-V2-7B-4bit"
TRANSFORMERS_MODEL_NAME = "deepseek-ai/DeepSeek-Prover-V2-7B"
MODEL_NAME = MLX_MODEL_NAME  # backward-compatible alias; prefer default_model_name(backend)
# Samples per model.generate call on the transformers backend. 1 keeps the KV cache
# small (a 7B bf16 model leaves little headroom on a 16 GB card).
TRANSFORMERS_CHUNK_SIZE = 1
DEFAULT_K = 8
# Concurrent Lean checks; generation stays sequential, verification overlaps with it.
DEFAULT_VERIFY_WORKERS = 12
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TEMP = 0.6
LEAN_TIMEOUT_S = 180
SEED_CONFIG = "b0"
SEED_MASK = (1 << 63) - 1

# Uniform Mathlib environment for all problems (prover is Mathlib-trained); benchmark files are not modified.
EVAL_HEADER = "import Mathlib\n"

PROMPT_TEMPLATE = "Complete the following Lean 4 code:\n\n```lean4\n{header}\n```\n"

# Hint-gap condition: names the auxiliary construction from the reference proof, never the proof.
HINT_PROMPT_TEMPLATE = (
    "Complete the following Lean 4 code. A useful auxiliary step is: {hint}\n\n"
    "```lean4\n{header}\n```\n"
)
HINT_GAP_RESAMPLES = 10000
HINT_GAP_CI_SEED = 0

# Verification controls: Lean-only core, Mathlib, and Mathlib plus Mathesis.Defs.
CONTROL_PROBLEMS = ("lean_nat_add_comm", "lean_sq_nonneg", "lean_poly_lower")
NEGATIVE_PROOFS = (
    ("sorry", "sorry", "forbidden_token"),
    ("admit", "admit", "forbidden_token"),
    ("invalid_tactic", "this_is_not_a_tactic_xyz", "lean_error"),
)

# Judge rule version, written to every row. v2: comments are stripped from the proof text
# before the forbidden-token check (see mathesis.proof_rules); rows from a v1 run (no
# `judge_version` key) used the unstripped text and must not be re-read under v2.
JUDGE_VERSION = "v2"
FORBIDDEN_SOURCES = ("proof", "output")
# Network isolation for the Lean subprocess: auto = `unshare -rn` when it works here.
SANDBOX_ENV = "MATHESIS_LEAN_SANDBOX"
SANDBOX_MODES = ("auto", "off")
SANDBOX_PREFIX = ("unshare", "-rn")
# The only variables the Lean subprocess receives (HOME is a private temp dir).
LEAN_ENV_WHITELIST = ("PATH", "ELAN_HOME", "LANG", "LC_ALL", "TMPDIR", "HOME")
ERROR_RE = re.compile(r"\berror\b", re.IGNORECASE)
# Lean output that signals a broken toolchain/project rather than a bad proof.
ENV_ERROR_RE = re.compile(
    r"unknown module prefix|object file .* does not exist|failed to read file"
    r"|unknown package|lake: command not found|toolchain .* is not installed",
    re.IGNORECASE,
)
FENCE_RE = re.compile(r"```[ \t]*([A-Za-z0-9_+-]*)[ \t]*\n(.*?)(?:```|\Z)", re.DOTALL)
THEOREM_NAME_RE = re.compile(r"\b(?:theorem|lemma)\s+(\S+)")


class EnvironmentFailure(RuntimeError):
    """Lean toolchain or project is broken; results would be meaningless."""


# ---------------------------------------------------------------- pure helpers


def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k)."""
    if n < 1 or k < 1 or k > n or c < 0 or c > n:
        raise ValueError("need 1 <= k <= n and 0 <= c <= n")
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def split_lean_file(text: str) -> tuple[str, str]:
    """Split a benchmark .lean file into (header, footer).

    header: everything up to and including the first line ending in ':= by'
    (no trailing newline). footer: the trailing column-0 'end X' lines.
    """
    lines = text.splitlines()
    header_end = None
    for index, line in enumerate(lines):
        if line.rstrip().endswith(":= by"):
            header_end = index
            break
    if header_end is None:
        raise ValueError("no ':= by' line in lean file")
    footer_lines = []
    for line in reversed(lines[header_end + 1 :]):
        if not line.strip():
            continue
        if re.match(r"end\s+\S+\s*$", line):
            footer_lines.append(line.strip())
            continue
        break
    footer_lines.reverse()
    return "\n".join(lines[: header_end + 1]), "\n".join(footer_lines)


def with_eval_header(header: str) -> str:
    """Prepend EVAL_HEADER unless the header already imports Mathlib itself."""
    if any(line.strip() == EVAL_HEADER.strip() for line in header.splitlines()):
        return header
    return EVAL_HEADER + header


def build_prompt(header: str) -> str:
    return PROMPT_TEMPLATE.format(header=with_eval_header(header))


def build_hinted_prompt(header: str, hint: str) -> str:
    return HINT_PROMPT_TEMPLATE.format(hint=hint, header=with_eval_header(header))


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _header_signature(header: str) -> tuple[str, str]:
    """(theorem name, normalized statement text after the name, before ':= by')."""
    match = None
    for found in THEOREM_NAME_RE.finditer(header):
        match = found
    if match is None:
        raise ValueError("no theorem in header")
    rest = header[match.end() :]
    cut = rest.rindex(":=")
    return match.group(1), _normalize(rest[:cut])


def _statement_cut(rest: str, signature: str) -> int | None:
    """Index of the ':=' that ends the statement in `rest` (text after the theorem name).

    Same cut as `_header_signature` (the ':=' before 'by'): a ':=' inside the
    statement (`let x := 1; ...`) or in the proof body is not the cut. It is the
    first ':=' whose preceding text equals the benchmark statement.
    """
    for found in re.finditer(r":=", rest):
        if _normalize(rest[: found.start()]) == signature:
            return found.start()
    return None


def extract_code_block(response: str, name: str) -> str | None:
    """Pick the last fenced block mentioning the theorem, else the first block.

    An unterminated final block (generation cut at max_tokens) is kept as is.
    """
    blocks = [body for _lang, body in FENCE_RE.findall(response)]
    if not blocks:
        return None
    for body in reversed(blocks):
        if re.search(r"\b(?:theorem|lemma)\s+" + re.escape(name) + r"\b", body):
            return body
    return blocks[0]


def extract_proof(response: str, header: str) -> tuple[str | None, str]:
    """Return (proof_text_after_by, reason). proof_text is None on failure.

    reason is "" on success, else no_code_block / statement_mismatch /
    not_tactic_proof / empty_proof.
    """
    name, signature = _header_signature(header)
    block = extract_code_block(response, name)
    if block is None:
        return None, "no_code_block"
    start = re.search(r"\b(?:theorem|lemma)\s+" + re.escape(name) + r"\b", block)
    if start is None:
        if re.search(r"\b(?:theorem|lemma)\b", block):
            return None, "statement_mismatch"
        lines = block.splitlines()
        first = next((ln for ln in lines if ln.strip()), "")
        indent = "" if first.startswith((" ", "\t")) else "  "
        body = "\n" + "\n".join((indent + ln) if ln.strip() else ln for ln in lines)
    else:
        rest = block[start.end() :]
        cut = _statement_cut(rest, signature)
        if cut is None:
            return None, "statement_mismatch"
        after = rest[cut + 2 :]
        by = re.match(r"\s*by\b", after)
        if by is None:
            return None, "not_tactic_proof"
        body = after[by.end() :]
    kept = body.rstrip().splitlines()
    while kept and re.match(r"end\s+\S+\s*$", kept[-1]):
        kept.pop()
        while kept and not kept[-1].strip():
            kept.pop()
    proof = "\n".join(kept)
    if not proof.strip():
        return None, "empty_proof"
    return proof, ""


def build_candidate(header: str, proof: str, footer: str) -> str:
    header = with_eval_header(header)
    text = header + proof.rstrip()
    if proof.lstrip(" \t") == proof and not proof.startswith("\n"):
        text = header + " " + proof.rstrip()
    text += "\n"
    if footer:
        text += footer + "\n"
    return text


def lean_verify_command(path) -> list[str]:
    # lake runs from the Lean project directory, so the candidate path must be absolute.
    return ["lake", "env", "lean", str(Path(path).resolve())]


def default_lean_dir() -> Path:
    return default_repo_root() / "lean"


def has_forbidden_token(text: str, is_output: bool = False) -> str | None:
    """Forbidden token in `text`, else None.

    Proof text (default) is checked with comments stripped, and an unterminated
    block comment counts as forbidden. Lean output (`is_output`) is checked verbatim.
    """
    return find_forbidden(text) if is_output else find_forbidden_in_proof(text)


def judge_with_source(
    proof: str, returncode: int, output: str, timed_out: bool = False,
    timeout_s: int = LEAN_TIMEOUT_S,
):
    """Pass/fail rule -> (passed, failure_class, first_error_line, forbidden_source).

    forbidden_source is "proof" or "output" for a forbidden_token failure, else None.
    """
    if timed_out:
        return False, "timeout", "timeout after " + str(timeout_s) + "s", None
    token = has_forbidden_token(proof)
    source = "proof"
    if token is None:
        token = has_forbidden_token(output, is_output=True)
        source = "output"
    if token is not None:
        return False, "forbidden_token", "forbidden token: " + token, source
    error_line = ""
    for line in output.splitlines():
        if ERROR_RE.search(line):
            error_line = line.strip()
            break
    if error_line:
        return False, "lean_error", error_line, None
    if returncode != 0:
        # Non-zero exit and no `error` line: Lean was cut short (stack overflow, OOM
        # kill, ...) rather than rejecting the proof with a diagnostic.
        return False, "lean_crash", "lean exited rc=" + str(returncode) + " without diagnostics", None
    return True, "ok", "", None


def judge(
    proof: str, returncode: int, output: str, timed_out: bool = False,
    timeout_s: int = LEAN_TIMEOUT_S,
):
    """Pure pass/fail rule -> (passed, failure_class, first_error_line)."""
    return judge_with_source(proof, returncode, output, timed_out, timeout_s)[:3]


# -------------------------------------------------------------- Lean execution


@dataclass
class LeanRun:
    returncode: int
    output: str
    seconds: float
    timed_out: bool


_SANDBOX_LOCK = threading.Lock()
_SANDBOX_PROBE: bool | None = None  # cached `unshare -rn true` result, per process
_LEAN_HOME: str | None = None  # private HOME shared by this process's Lean checks


def _lean_home() -> str:
    """A private, empty HOME for Lean subprocesses (never the real home directory)."""
    global _LEAN_HOME
    with _SANDBOX_LOCK:
        if _LEAN_HOME is None or not os.path.isdir(_LEAN_HOME):
            _LEAN_HOME = tempfile.mkdtemp(prefix="mathesis_lean_home_")
            atexit.register(shutil.rmtree, _LEAN_HOME, True)
        return _LEAN_HOME


def _lean_env() -> dict:
    """Whitelisted environment: PATH, ELAN_HOME, LANG, LC_ALL, TMPDIR and a private HOME.

    `lake env lean` finds its toolchain through PATH and ELAN_HOME alone (checked:
    no LEAN_PATH or other variable is needed; `lake env` sets LEAN_PATH itself).
    Everything else (tokens, proxies, the real HOME) is dropped.
    """
    env = {"HOME": _lean_home()}
    for name in ("PATH", "ELAN_HOME", "LANG", "LC_ALL", "TMPDIR"):
        if name in os.environ:
            env[name] = os.environ[name]
    elan_home = env.get("ELAN_HOME") or str(Path.home() / ".elan")
    env["ELAN_HOME"] = elan_home
    if shutil.which("lake", path=env.get("PATH")) is None:
        env["PATH"] = str(Path(elan_home) / "bin") + os.pathsep + env.get("PATH", "")
    return env


def _sandbox_available() -> bool:
    global _SANDBOX_PROBE
    with _SANDBOX_LOCK:
        if _SANDBOX_PROBE is None:
            try:
                probe = subprocess.run(
                    [*SANDBOX_PREFIX, "true"], capture_output=True, timeout=10
                )
                _SANDBOX_PROBE = probe.returncode == 0
            except (OSError, subprocess.SubprocessError):
                _SANDBOX_PROBE = False
        return _SANDBOX_PROBE


def _sandbox_prefix() -> list[str]:
    """Command prefix that cuts the network (`unshare -rn`), or [] when off/unavailable.

    MATHESIS_LEAN_SANDBOX is read on every call: "auto" (default) or "off".
    """
    mode = os.environ.get(SANDBOX_ENV, "auto").strip().lower() or "auto"
    if mode not in SANDBOX_MODES:
        raise EnvironmentFailure(
            SANDBOX_ENV + " must be one of " + "/".join(SANDBOX_MODES) + ", got " + repr(mode)
        )
    if mode == "auto" and _sandbox_available():
        return list(SANDBOX_PREFIX)
    return []


def lean_sandbox_info() -> dict:
    """What isolation the next Lean check gets (for the run manifest)."""
    prefix = _sandbox_prefix()
    return {
        "mode": "unshare-net" if prefix else "none",
        "requested": os.environ.get(SANDBOX_ENV, "auto").strip().lower() or "auto",
        "command_prefix": prefix,
        "env_whitelist": list(LEAN_ENV_WHITELIST),
        "home": "private temp dir",
    }


def _kill_group(proc) -> None:
    """SIGKILL the whole process group of `proc` (started with start_new_session)."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass  # already gone


def _as_text(data) -> str:
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return data or ""


_DIAGNOSTIC_LINE_RE = re.compile(r"^\s*\S.*?:\d+:\d+:")


def _candidate_missing(output: str, path: Path) -> bool:
    """True if lake itself reported the candidate file as missing.

    Lean diagnostics (`<file>:<line>:<col>: ...`) are skipped: a message the proof
    provoked (say, `include` of a missing file) is not a harness failure.
    """
    if "no such file or directory" not in output.lower():
        return False
    rest = "\n".join(
        line for line in output.splitlines() if not _DIAGNOSTIC_LINE_RE.match(line)
    )
    return "no such file or directory" in rest.lower() and (
        str(path) in rest or path.name in rest
    )


def run_lean(path, lean_dir=None, timeout: int = LEAN_TIMEOUT_S) -> LeanRun:
    """Run `lake env lean <path>` in its own session and process group.

    Timeout: the whole group is SIGKILLed (lake leaves lean children behind
    otherwise). EnvironmentFailure: lake cannot run, the candidate file is
    missing, lake itself died from a signal (rc < 0), or the output shows a
    broken toolchain. A non-zero exit with no Lean `error` line (stack overflow,
    OOM kill, ...) is a normal LeanRun; `judge` classes it as `lean_crash`.
    """
    cwd = Path(lean_dir) if lean_dir is not None else default_lean_dir()
    candidate = Path(path).resolve()
    if not candidate.is_file():
        raise EnvironmentFailure("candidate file does not exist: " + str(candidate))
    command = _sandbox_prefix() + lean_verify_command(path)
    started = time.monotonic()
    try:
        proc = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_lean_env(),
            start_new_session=True,
        )
    except OSError as exc:
        raise EnvironmentFailure("cannot run lake: " + str(exc)) from exc
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _kill_group(proc)
        partial = _as_text(exc.stdout)
        try:
            stdout, stderr = proc.communicate(timeout=10)
            partial = _as_text(stdout) + _as_text(stderr) or partial
        except subprocess.TimeoutExpired:
            # Something outside the group still holds the pipes; the child itself
            # was SIGKILLed, so reap it to avoid leaving a zombie.
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        return LeanRun(-1, partial, time.monotonic() - started, True)
    except BaseException:
        _kill_group(proc)  # Ctrl-C etc.: do not leave lean running
        try:
            proc.communicate(timeout=10)
        except Exception:
            pass
        raise
    output = (stdout or "") + (stderr or "")
    elapsed = time.monotonic() - started
    if _candidate_missing(output, candidate):
        # A missing candidate file is a harness bug, not a failed proof.
        raise EnvironmentFailure("candidate file not found by lake: " + output.strip()[:300])
    rc = proc.returncode
    if rc < 0 or (rc != 0 and ENV_ERROR_RE.search(output)):
        raise EnvironmentFailure(
            "lean environment failure (rc=" + str(rc) + "): " + output.strip()[:300]
        )
    return LeanRun(rc, output, elapsed, False)


@dataclass
class Verification:
    passed: bool
    failure_class: str
    first_error_line: str
    seconds: float
    returncode: int
    output: str
    # Real Lean exit code; None when Lean did not run (no proof) or timed out.
    lean_returncode: int | None = None
    forbidden_source: str | None = None  # "proof" / "output" for forbidden_token


def verify_proof(
    header: str, proof: str, footer: str, path, lean_dir=None, timeout=LEAN_TIMEOUT_S
) -> Verification:
    """Write header+proof+footer to `path` and check it with Lean."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_candidate(header, proof, footer), encoding="utf-8")
    result = run_lean(target, lean_dir=lean_dir, timeout=timeout)
    output = result.output.replace(str(target.parent) + os.sep, "")
    # Evidence: the Lean output the judge saw, next to the candidate (same stem, .out).
    target.with_suffix(".out").write_text(output, encoding="utf-8")
    passed, failure_class, first_error, source = judge_with_source(
        proof, result.returncode, output, result.timed_out, timeout
    )
    return Verification(
        passed, failure_class, first_error, result.seconds, result.returncode,
        output, None if result.timed_out else result.returncode, source,
    )


# -------------------------------------------------------------------- problems


def load_b0_problems(limit=None, benchmark_dir=None):
    """Problems in problems.json order, each with header/footer parsed from its file."""
    base = Path(benchmark_dir) if benchmark_dir is not None else default_lean_pilot_dir()
    entries = load_lean_pilot(base / "problems.json")
    if limit is not None:
        entries = entries[: int(limit)]
    problems = []
    for entry in entries:
        text = (base / str(entry["lean_file"])).read_text(encoding="utf-8")
        header, footer = split_lean_file(text)
        problems.append(
            {
                "name": str(entry["name"]),
                "header": header,
                "footer": footer,
                "reference_proof": [str(t) for t in entry["reference_proof"]],
                "auxiliary": str(entry.get("auxiliary", "")),
                "insight": bool(entry.get("insight", False)),
            }
        )
    return problems


def reference_proof_text(tactics) -> str:
    return "\n" + "\n".join("  " + t for t in tactics)


# -------------------------------------------------------------------- controls


def run_controls(run, problems, lean_dir=None) -> dict:
    """C1: reference proofs must pass. C2: wrong proofs must fail (sorry via the check)."""
    by_name = {p["name"]: p for p in problems}
    missing = [n for n in CONTROL_PROBLEMS if n not in by_name]
    if missing:
        raise ValueError("control problems missing: " + ", ".join(missing))
    cdir = run.path / "control_candidates"
    c1, c2 = [], []
    for name in CONTROL_PROBLEMS:
        prob = by_name[name]
        ver = verify_proof(
            prob["header"], reference_proof_text(prob["reference_proof"]),
            prob["footer"], cdir / (name + "_reference.lean"), lean_dir,
        )
        c1.append(
            {"problem": name, "passed": ver.passed, "expected": True,
             "ok": ver.passed is True, "failure_class": ver.failure_class,
             "first_error_line": ver.first_error_line, "seconds": ver.seconds}
        )
        for label, proof, want_class in NEGATIVE_PROOFS:
            ver = verify_proof(
                prob["header"], "\n  " + proof, prob["footer"],
                cdir / (name + "_" + label + ".lean"), lean_dir,
            )
            record = {
                "problem": name, "variant": label, "passed": ver.passed,
                "expected": False, "failure_class": ver.failure_class,
                "expected_class": want_class,
                "first_error_line": ver.first_error_line,
                "lean_returncode": ver.returncode, "seconds": ver.seconds,
                # sorry/admit must be rejected by our rule, not merely by Lean.
                "ok": ver.passed is False and ver.failure_class == want_class,
            }
            if want_class == "forbidden_token":
                record["lean_alone_would_pass"] = (
                    ver.returncode == 0 and not ERROR_RE.search(ver.output)
                )
            c2.append(record)
    c1_ok = all(r["ok"] for r in c1)
    c2_ok = all(r["ok"] for r in c2)
    return {"C1": {"ok": c1_ok, "results": c1}, "C2": {"ok": c2_ok, "results": c2},
            "ok": c1_ok and c2_ok}


def format_controls(report: dict) -> str:
    lines = []
    for key, title in (("C1", "reference proofs must pass"),
                       ("C2", "wrong proofs must fail")):
        lines.append(key + " (" + title + "): " + ("PASS" if report[key]["ok"] else "FAIL"))
        for row in report[key]["results"]:
            label = row["problem"] + (" / " + row["variant"] if "variant" in row else "")
            lines.append(
                "  " + label + " | passed=" + str(row["passed"]) + " | class="
                + row["failure_class"] + " | " + ("ok" if row["ok"] else "UNEXPECTED")
                + (" | " + row["first_error_line"][:100] if row["first_error_line"] else "")
            )
    lines.append("controls: " + ("PASS" if report["ok"] else "FAIL"))
    return "\n".join(lines)


# ------------------------------------------------------------------- preflight

PREFLIGHT_GOOD = ("theorem mathesis_preflight : (1 : ℕ) + 1 = 2 := by", "\n  norm_num")
PREFLIGHT_BAD = ("theorem mathesis_preflight_bad : (1 : ℕ) + 1 = 3 := by", "\n  norm_num")
LEAN_CRASH_WARN_FRACTION = 0.10


def preflight_lean(lean_dir=None, out_dir=None, timeout: int = LEAN_TIMEOUT_S) -> dict:
    """Check the Lean pipeline on one known-good and one known-bad proof, before any model loads.

    Both go through `verify_proof` (same header, sandbox and environment as real
    candidates). The good proof must come back `ok`, the bad one `lean_error`;
    otherwise EnvironmentFailure, because a broken sandbox would otherwise only
    show up as a whole run of `lean_crash` rows. Candidates and `.out` files go to
    `out_dir` (never candidates/); the result is also saved as `out_dir/preflight.json`.
    """
    if out_dir is None:
        raise ValueError("preflight_lean needs an out_dir")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = (("good", PREFLIGHT_GOOD, "ok"), ("bad", PREFLIGHT_BAD, "lean_error"))
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=len(cases)) as pool:
        futures = [
            pool.submit(verify_proof, header, proof, "", out_dir / (label + ".lean"),
                        lean_dir, timeout)
            for label, (header, proof), _ in cases
        ]
        verdicts = [future.result() for future in futures]
    result = {"mode": lean_sandbox_info()["mode"], "sandbox": lean_sandbox_info(),
              "ok": True, "seconds": time.monotonic() - started}
    problems = []
    for (label, _, want), ver in zip(cases, verdicts):
        result[label + "_failure_class"] = ver.failure_class
        result[label + "_seconds"] = ver.seconds
        if ver.failure_class != want:
            result["ok"] = False
            problems.append(
                label + " proof: expected " + want + ", got " + ver.failure_class
                + " (rc=" + str(ver.returncode) + "): " + (ver.output.strip()[:300] or "<no output>")
            )
    (out_dir / "preflight.json").write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    if problems:
        raise EnvironmentFailure(
            "lean preflight failed (sandbox mode " + result["mode"] + "): " + "; ".join(problems)
        )
    return result


def _check_run_sizes(k, max_tokens) -> None:
    if int(k) < 1:
        raise ValueError("k must be >= 1")
    if int(max_tokens) < 1:
        raise ValueError("max_tokens must be >= 1")


def _with_preflight(summary: dict, info) -> dict:
    if info is not None:
        summary["lean_preflight"] = info
    return summary


# ------------------------------------------------------------------ generation


def check_backend(backend: str) -> str:
    if backend not in BACKENDS:
        raise ValueError(
            "unknown backend " + repr(backend) + "; allowed: " + ", ".join(BACKENDS)
        )
    return backend


def default_model_name(backend: str = DEFAULT_BACKEND) -> str:
    check_backend(backend)
    return MLX_MODEL_NAME if backend == "mlx" else TRANSFORMERS_MODEL_NAME


def load_model(name: str | None = None, backend: str = DEFAULT_BACKEND):
    """Load (model, tokenizer); mlx/torch/transformers are imported lazily."""
    check_backend(backend)
    if name is None:
        name = default_model_name(backend)
    if backend == "mlx":
        from mlx_lm import load

        return load(name)
    return _load_transformers(name)


def _load_transformers(name: str):
    """bf16 model on the single visible CUDA device (select it via CUDA_VISIBLE_DEVICES)."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("transformers backend needs a CUDA device (torch.cuda.is_available() is False)")
    tokenizer = AutoTokenizer.from_pretrained(name)
    try:
        model = AutoModelForCausalLM.from_pretrained(
            name, torch_dtype=torch.bfloat16, device_map="cuda"
        )
    except ImportError:  # device_map needs accelerate; load on CPU and move instead
        model = AutoModelForCausalLM.from_pretrained(name, torch_dtype=torch.bfloat16)
        model = model.to("cuda")
    model.eval()
    return model, tokenizer


def encode_prompt(tokenizer, prompt: str) -> list[int]:
    template = getattr(tokenizer, "chat_template", None)
    if template:
        text = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            add_generation_prompt=True,
            tokenize=False,
        )
        return list(tokenizer.encode(text, add_special_tokens=False))
    return list(tokenizer.encode(prompt))


def new_token_sequences(sequences, prompt_len: int, eos_ids) -> list[list[int]]:
    """Drop the prompt from each generated row and cut at the first stop token.

    The stop token itself and any padding after it are removed, so the result holds
    only the sampled completion tokens (a row that never stops keeps all of its tokens).
    """
    stops = set(eos_ids)
    out = []
    for row in sequences:
        tokens = []
        for token in list(row)[int(prompt_len):]:
            token = int(token)
            if token in stops:
                break
            tokens.append(token)
        out.append(tokens)
    return out


def _hit_eos_flags(sequences, prompt_len: int, eos_ids) -> list[bool]:
    """Per row: did a stop token appear among the generated tokens?"""
    stops = set(eos_ids)
    return [any(int(t) in stops for t in list(row)[int(prompt_len):]) for row in sequences]


class _Generated(tuple):
    """(texts, token_counts, seconds) plus `hit_eos`, a per-sample list or None if unknown."""

    hit_eos = None


def _eos_ids(tokenizer, model) -> list[int]:
    ids = []
    for source in (getattr(model, "generation_config", None), tokenizer):
        value = getattr(source, "eos_token_id", None)
        if value is None:
            continue
        ids.extend(value if isinstance(value, (list, tuple)) else [value])
    return sorted({int(i) for i in ids})


def generate_samples(model, tokenizer, prompt_ids, k, max_tokens, temp, seed,
                     backend: str = DEFAULT_BACKEND):
    """k samples for one prompt -> (texts, token_counts, seconds)."""
    check_backend(backend)
    if backend == "mlx":
        return _generate_samples_mlx(model, tokenizer, prompt_ids, k, max_tokens, temp, seed)
    return _generate_samples_transformers(
        model, tokenizer, prompt_ids, k, max_tokens, temp, seed
    )


def _generate_samples_mlx(model, tokenizer, prompt_ids, k, max_tokens, temp, seed):
    """One batch of k samples -> (texts, token_counts, batch_seconds)."""
    import mlx.core as mx
    from mlx_lm.generate import batch_generate
    from mlx_lm.sample_utils import make_sampler

    mx.random.seed(int(seed))
    started = time.monotonic()
    response = batch_generate(
        model,
        tokenizer,
        [prompt_ids] * int(k),
        max_tokens=int(max_tokens),
        sampler=make_sampler(temp=float(temp)),
        completion_batch_size=int(k),
        prefill_batch_size=int(k),
        return_token_ids=True,
    )
    seconds = time.monotonic() - started
    return list(response.texts), [len(t) for t in response.token_ids], seconds


def _generate_samples_transformers(model, tokenizer, prompt_ids, k, max_tokens, temp,
                                   seed, chunk_size: int = TRANSFORMERS_CHUNK_SIZE):
    """k samples via model.generate, `chunk_size` sequences per call (same return as MLX).

    Sampling matches mlx make_sampler(temp): temperature only, no top-k (HF defaults
    to top_k=50, so it is disabled explicitly) and top_p=1.0.
    """
    import torch

    torch.manual_seed(int(seed))
    torch.cuda.manual_seed_all(int(seed))
    eos_ids = _eos_ids(tokenizer, model)
    pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else eos_ids[0]
    prompt_len = len(prompt_ids)
    input_ids = torch.tensor([list(prompt_ids)], dtype=torch.long, device=model.device)
    attention_mask = torch.ones_like(input_ids)
    remaining = int(k)
    completions: list[list[int]] = []
    hit_eos: list[bool] = []
    started = time.monotonic()
    with torch.inference_mode():
        while remaining > 0:
            n = min(remaining, max(1, int(chunk_size)))
            out = model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                do_sample=True,
                temperature=float(temp),
                top_p=1.0,
                top_k=0,
                max_new_tokens=int(max_tokens),
                num_return_sequences=n,
                pad_token_id=pad_id,
            )
            rows = out.tolist()
            completions.extend(new_token_sequences(rows, prompt_len, eos_ids))
            hit_eos.extend(_hit_eos_flags(rows, prompt_len, eos_ids))
            del out
            remaining -= n
    seconds = time.monotonic() - started
    texts = [tokenizer.decode(ids, skip_special_tokens=True) for ids in completions]
    generated = _Generated((texts, [len(ids) for ids in completions], seconds))
    generated.hit_eos = hit_eos
    return generated


def derived_b0_seed(seed: int, problem: str) -> int:
    return derive_seed(int(seed), problem, SEED_CONFIG) & SEED_MASK


def _problem_stats(n: int, passed: int, k: int) -> dict:
    return {
        "n": n,
        "c": passed,
        "pass_at_1": pass_at_k(n, passed, 1),
        "pass_at_k": pass_at_k(n, passed, int(k)),
    }


@dataclass
class _PendingPrompt:
    """One prompt whose samples are generated and whose Lean checks are in flight."""

    name: str
    counts: list
    futures: list
    gen_seconds: float
    seed: int
    derived: int
    max_tokens: int
    extra: dict
    on_done: object = field(default=None)  # called with (n, passed) once rows are flushed
    flushed: int = 0  # rows already logged, so a retried flush never duplicates them
    passed: int = 0
    batch_size: int = 0
    hit_eos: object = field(default=None)  # per-sample list, or None when the backend cannot say
    failure_counts: object = field(default=None)  # shared Counter of failure_class, or None


def _constant(value):
    return value


def _check_verify_workers(verify_workers) -> int:
    if int(verify_workers) < 1:
        raise ValueError("verify_workers must be >= 1")
    return int(verify_workers)


def _sample_prompt(run, model, tokenizer, prob, prompt_text, tag, derived, k,
                   max_tokens, temp, seed, lean_dir, extra,
                   backend: str = DEFAULT_BACKEND, executor=None,
                   failure_counts=None) -> _PendingPrompt:
    """Sample k completions for one prompt and submit each sample's Lean check to `executor`.

    `tag` names the response and candidate files; `extra` is merged into each row.
    Response files are written here, on the calling thread, before the job is
    submitted. The rows are logged later by `_flush_prompt`, in sample order.
    """
    cdir = run.path / "candidates"
    rdir = run.path / "responses"
    rdir.mkdir(exist_ok=True)
    prompt_ids = encode_prompt(tokenizer, prompt_text)
    generated = generate_samples(
        model, tokenizer, prompt_ids, k, max_tokens, temp, derived, backend
    )
    texts, counts, gen_seconds = generated
    hit_eos = getattr(generated, "hit_eos", None)
    futures = []
    for sample_index, text in enumerate(texts):
        (rdir / (tag + "_" + str(sample_index) + ".txt")).write_text(
            text, encoding="utf-8"
        )
        proof, reason = extract_proof(text, prob["header"])
        if proof is None:
            futures.append(
                executor.submit(_constant, Verification(False, reason, reason, 0.0, -1, ""))
            )
        else:
            futures.append(executor.submit(
                verify_proof, prob["header"], proof, prob["footer"],
                cdir / (tag + "_" + str(sample_index) + ".lean"), lean_dir,
            ))
    return _PendingPrompt(
        prob["name"], list(counts), futures, gen_seconds, int(seed), derived,
        int(max_tokens), dict(extra), batch_size=int(k),
        hit_eos=None if hit_eos is None else list(hit_eos), failure_counts=failure_counts,
    )


def _flush_prompt(run, pending: _PendingPrompt) -> tuple[int, int]:
    """Log one row per sample in sample order; a failed check re-raises here."""
    for sample_index in range(pending.flushed, len(pending.futures)):
        count = pending.counts[sample_index]
        ver = pending.futures[sample_index].result()
        row = {
            "problem": pending.name,
            "sample_index": sample_index,
            "passed": ver.passed,
            "first_error_line": ver.first_error_line,
            "generated_tokens": count,
            "gen_seconds": pending.gen_seconds,  # whole batch of k, shared by its samples
            "verify_seconds": ver.seconds,
            "seed": pending.seed,
            "derived_seed": pending.derived,
            "failure_class": ver.failure_class,
            "truncated": count >= pending.max_tokens,
            "lean_returncode": ver.lean_returncode,
            "judge_version": JUDGE_VERSION,
            "forbidden_source": ver.forbidden_source,
            "batch_size": pending.batch_size,
            "hit_eos": None if pending.hit_eos is None else pending.hit_eos[sample_index],
        }
        row.update(pending.extra)
        run.append_result(row)
        # Only after the row is logged, so a retried flush never double-counts.
        pending.passed += 1 if ver.passed else 0
        if pending.failure_counts is not None:
            pending.failure_counts[ver.failure_class] += 1
        pending.flushed = sample_index + 1
    return len(pending.futures), pending.passed


def _drain(run, queue: deque, block: bool) -> None:
    """Flush prompts from the head of `queue`, never out of order.

    Without `block`, stop at the first head whose checks are still running.
    """
    while queue:
        head = queue[0]
        if not block and not all(f.done() for f in head.futures):
            return
        n, passed_count = _flush_prompt(run, head)
        queue.popleft()
        head.on_done(n, passed_count)


def _run_overlapped(run, verify_workers, produce) -> None:
    """Drive `produce(executor, queue)` (generation, main thread) with one shared pool.

    Rows are logged in the order prompts were queued. If anything fails, prompts
    already submitted are flushed best-effort (as the sequential code would have
    logged them) and the original error is re-raised.
    """
    workers = _check_verify_workers(verify_workers)
    queue: deque = deque()
    executor = ThreadPoolExecutor(max_workers=workers)
    try:
        try:
            produce(executor, queue)
            _drain(run, queue, block=True)
        except BaseException:  # includes KeyboardInterrupt: still log finished work
            try:
                _drain(run, queue, block=True)
            except Exception:
                pass
            raise
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def run_b0(run, problems, k, max_tokens, seed, temp=DEFAULT_TEMP, lean_dir=None,
           model_name=None, backend=DEFAULT_BACKEND, progress=print,
           verify_workers: int = DEFAULT_VERIFY_WORKERS, lean_check: bool = True) -> dict:
    """Generate and verify k samples per problem; return the summary dict.

    Generation is sequential; Lean checks run on `verify_workers` threads shared by
    all problems. Rows and progress lines keep the sequential order. Arguments and
    (unless `lean_check` is False) the Lean pipeline are checked before the model loads.
    """
    _check_verify_workers(verify_workers)
    _check_run_sizes(k, max_tokens)
    info = preflight_lean(lean_dir, run.path / "preflight") if lean_check else None
    model, tokenizer = load_model(model_name, backend)
    per_problem = {}
    failure_counts = Counter()

    def produce(executor, queue):
        for index, prob in enumerate(problems):
            name = prob["name"]
            derived = derived_b0_seed(seed, name)

            def done(n, passed_count, index=index, name=name):
                per_problem[name] = _problem_stats(n, passed_count, k)
                progress(
                    "[" + str(index + 1) + "/" + str(len(problems)) + "] " + name
                    + " passed " + str(passed_count) + "/" + str(n)
                )

            pending = _sample_prompt(
                run, model, tokenizer, prob, build_prompt(prob["header"]), name,
                derived, k, max_tokens, temp, seed, lean_dir, {}, backend, executor,
                failure_counts,
            )
            pending.on_done = done
            queue.append(pending)
            _drain(run, queue, block=False)

    _run_overlapped(run, verify_workers, produce)
    return _with_preflight(summarize_b0(per_problem, k, dict(failure_counts)), info)


# ------------------------------------------------------------------- hint gap


def select_hint_gap_problems(problems, limit=None, names=None) -> list:
    """Insight problems with an auxiliary construction: the only ones where the gap is defined.

    `names` restricts the selection to the given problem names; each must be a target.
    """
    if limit is not None and int(limit) < 1:
        raise ValueError("limit must be >= 1")
    targets = [p for p in problems if p["insight"] and p["auxiliary"]]
    if names is not None:
        if len(names) == 0:
            raise ValueError("names must not be empty")
        wanted = set(names)
        missing = wanted - {p["name"] for p in targets}
        if missing:
            raise ValueError("not hint-gap targets: " + ", ".join(sorted(missing)))
        targets = [p for p in targets if p["name"] in wanted]
    return targets if limit is None else targets[: int(limit)]


def run_hint_gap(run, problems, k, max_tokens, seed, limit=None, names=None,
                 temp=DEFAULT_TEMP, lean_dir=None, model_name=None,
                 backend=DEFAULT_BACKEND, progress=print,
                 verify_workers: int = DEFAULT_VERIFY_WORKERS,
                 lean_check: bool = True, targets=None) -> dict:
    """Sample k completions with and without the auxiliary hint for each target problem.

    Lean checks run on `verify_workers` threads shared by all prompts; rows and
    progress lines keep the sequential (plain, then hint) order. `targets`, when
    given, is used as-is (each entry's `auxiliary` is the hint) instead of
    selecting from `problems` with limit/names.
    """
    _check_verify_workers(verify_workers)
    _check_run_sizes(k, max_tokens)
    if targets is None:
        targets = select_hint_gap_problems(problems, limit, names)
    else:
        targets = list(targets)
        if not targets:
            raise ValueError("targets must not be empty")
    info = preflight_lean(lean_dir, run.path / "preflight") if lean_check else None
    model, tokenizer = load_model(model_name, backend)
    pairs = {}
    failure_counts = Counter()

    def produce(executor, queue):
        for index, prob in enumerate(targets):
            name = prob["name"]
            prompts = {
                "plain": build_prompt(prob["header"]),
                "hint": build_hinted_prompt(prob["header"], prob["auxiliary"]),
            }
            pairs[name] = {}
            for condition, prompt_text in prompts.items():
                derived = derived_b0_seed(seed, name + "#" + condition)

                def done(n, passed_count, index=index, name=name, condition=condition):
                    pairs[name][condition] = _problem_stats(n, passed_count, k)
                    if condition != "hint":
                        return
                    progress(
                        "[" + str(index + 1) + "/" + str(len(targets)) + "] " + name
                        + " plain " + str(pairs[name]["plain"]["c"])
                        + "/" + str(pairs[name]["plain"]["n"])
                        + " hint " + str(pairs[name]["hint"]["c"])
                        + "/" + str(pairs[name]["hint"]["n"])
                    )

                pending = _sample_prompt(
                    run, model, tokenizer, prob, prompt_text, name + "__" + condition,
                    derived, k, max_tokens, temp, seed, lean_dir,
                    {"condition": condition}, backend, executor, failure_counts,
                )
                pending.on_done = done
                queue.append(pending)
                _drain(run, queue, block=False)

    _run_overlapped(run, verify_workers, produce)
    return _with_preflight(
        summarize_hint_gap(pairs, k, failure_class_counts=dict(failure_counts)), info
    )


def _binomial_resample(rng, c: int, n: int) -> int:
    """Successes among n Bernoulli(c/n) draws; endpoints are exact and leave the RNG alone."""
    if n <= 0 or c <= 0:
        return 0
    if c >= n:
        return n
    p = c / n
    return sum(1 for _ in range(n) if rng.random() < p)


def _two_level_ci95(per_problem: dict, resamples: int) -> list:
    """Bootstrap CI of the mean gap: resample problems, then each condition's samples.

    Uses its own Random(HINT_GAP_CI_SEED + 1), so the problem-only `ci95` stream is untouched.
    """
    cells = [(v["plain"]["c"], v["plain"]["n"], v["hint"]["c"], v["hint"]["n"])
             for v in per_problem.values()]
    total = len(cells)
    rng = random.Random(HINT_GAP_CI_SEED + 1)
    means = []
    for _ in range(resamples):
        acc = 0.0
        for _ in range(total):
            pc, pn, hc, hn = cells[rng.randrange(total)]
            plain = _binomial_resample(rng, pc, pn) / pn if pn else 0.0
            hint = _binomial_resample(rng, hc, hn) / hn if hn else 0.0
            acc += hint - plain
        means.append(acc / total)
    means.sort()
    return [means[int(0.025 * (resamples - 1))], means[int(0.975 * (resamples - 1))]]


def summarize_hint_gap(pairs: dict, k: int, resamples: int = HINT_GAP_RESAMPLES,
                       failure_class_counts: dict | None = None) -> dict:
    """Per-problem gap = pass@1(hint) - pass@1(plain); mean with a paired bootstrap over problems.

    `ci95` resamples problems only; `ci95_two_level` also redraws each condition's samples.
    """
    if resamples < 1:
        raise ValueError("resamples must be >= 1")
    per_problem = {}
    for name, cond in pairs.items():
        per_problem[name] = {
            "plain": cond["plain"],
            "hint": cond["hint"],
            "gap": cond["hint"]["pass_at_1"] - cond["plain"]["pass_at_1"],
        }
    gaps = [v["gap"] for v in per_problem.values()]
    total = len(gaps)
    counts = {"failure_class_counts": dict(sorted((failure_class_counts or {}).items()))}
    if total == 0:
        return {"n_problems": 0, "k": int(k), "mean_gap": None, "ci95": None,
                "per_problem": per_problem, "n_nonzero_gap": 0, "n_plain_ceiling": 0,
                "n_plain_floor": 0, "ci95_two_level": None, **counts}
    rng = random.Random(HINT_GAP_CI_SEED)
    means = []
    for _ in range(resamples):
        draw = [gaps[rng.randrange(total)] for _ in range(total)]
        means.append(sum(draw) / total)
    means.sort()
    low = means[int(0.025 * (resamples - 1))]
    high = means[int(0.975 * (resamples - 1))]
    plains = [v["plain"] for v in per_problem.values()]
    return {
        "n_problems": total,
        "k": int(k),
        "mean_gap": sum(gaps) / total,
        "ci95": [low, high],
        "per_problem": per_problem,
        "n_nonzero_gap": sum(1 for g in gaps if abs(g) > 1e-12),
        "n_plain_ceiling": sum(1 for p in plains if p["n"] > 0 and p["c"] == p["n"]),
        "n_plain_floor": sum(1 for p in plains if p["c"] == 0),
        "ci95_two_level": _two_level_ci95(per_problem, resamples),
        **counts,
    }


def _format_failure_classes(summary: dict) -> list[str]:
    counts = summary.get("failure_class_counts")
    if not counts:
        return []
    lines = ["failure classes: " + ", ".join(k + "=" + str(v) for k, v in sorted(counts.items()))]
    total = sum(counts.values())
    crashes = counts.get("lean_crash", 0)
    if total and crashes / total > LEAN_CRASH_WARN_FRACTION:
        lines.append(
            "WARNING: lean_crash is " + format(100.0 * crashes / total, ".1f") + "% of "
            + str(total) + " samples (> " + format(100.0 * LEAN_CRASH_WARN_FRACTION, ".0f")
            + "%): check the Lean sandbox/environment before trusting these results"
        )
    return lines


def format_hint_gap_summary(summary: dict) -> str:
    lines = ["problem | plain | hint | gap"]
    for name, v in summary["per_problem"].items():
        lines.append(
            name + " | " + str(v["plain"]["c"]) + "/" + str(v["plain"]["n"]) + " | "
            + str(v["hint"]["c"]) + "/" + str(v["hint"]["n"]) + " | "
            + format(v["gap"], "+.3f")
        )
    if summary["mean_gap"] is None:
        lines.append("no insight problems with an auxiliary construction: hint gap not defined")
    else:
        low, high = summary["ci95"]
        lines.append(
            "mean gap over " + str(summary["n_problems"]) + " problems: "
            + format(summary["mean_gap"], "+.3f") + " (95% bootstrap CI ["
            + format(low, "+.3f") + ", " + format(high, "+.3f") + "])"
        )
        if summary.get("ci95_two_level") is not None:
            low2, high2 = summary["ci95_two_level"]
            lines.append(
                "two-level 95% CI (problems + samples): ["
                + format(low2, "+.3f") + ", " + format(high2, "+.3f") + "]"
            )
        if "n_nonzero_gap" in summary:
            lines.append(
                "nonzero gap: " + str(summary["n_nonzero_gap"]) + "/" + str(summary["n_problems"])
                + " problems; plain at ceiling: " + str(summary["n_plain_ceiling"])
                + ", at floor: " + str(summary["n_plain_floor"])
            )
    lines.extend(_format_failure_classes(summary))
    return "\n".join(lines)


def summarize_b0(per_problem: dict, k: int, failure_class_counts: dict | None = None) -> dict:
    total = len(per_problem)
    mean1 = sum(v["pass_at_1"] for v in per_problem.values()) / total if total else 0.0
    meank = sum(v["pass_at_k"] for v in per_problem.values()) / total if total else 0.0
    summary = {
        "n_problems": total,
        "k": int(k),
        "pass_at_1": mean1,
        "pass_at_k": meank,
        "per_problem": per_problem,
        "failure_class_counts": dict(sorted((failure_class_counts or {}).items())),
    }
    if not total:
        summary["empty"] = True  # 0.0 above means "nothing measured", not "all failed"
    return summary


def format_b0_summary(summary: dict) -> str:
    lines = ["problem | passed/n | pass@1 | pass@" + str(summary["k"])]
    for name, v in summary["per_problem"].items():
        lines.append(
            name + " | " + str(v["c"]) + "/" + str(v["n"]) + " | "
            + format(v["pass_at_1"], ".3f") + " | " + format(v["pass_at_k"], ".3f")
        )
    lines.append(
        "overall over " + str(summary["n_problems"]) + " problems: pass@1="
        + format(summary["pass_at_1"], ".3f") + " pass@" + str(summary["k"]) + "="
        + format(summary["pass_at_k"], ".3f")
    )
    if summary.get("empty"):
        lines.append("no problems were run: the 0.000 values above are not a measurement")
    lines.extend(_format_failure_classes(summary))
    return "\n".join(lines)
