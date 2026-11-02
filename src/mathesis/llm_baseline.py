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

import math
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from mathesis.lean_pilot import default_lean_pilot_dir, load_lean_pilot
from mathesis.runlog import default_repo_root, derive_seed

MODEL_NAME = "mlx-community/DeepSeek-Prover-V2-7B-4bit"
DEFAULT_K = 8
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TEMP = 0.6
LEAN_TIMEOUT_S = 180
SEED_CONFIG = "b0"
SEED_MASK = (1 << 63) - 1

# Uniform Mathlib environment for all problems (prover is Mathlib-trained); benchmark files are not modified.
EVAL_HEADER = "import Mathlib\n"

PROMPT_TEMPLATE = "Complete the following Lean 4 code:\n\n```lean4\n{header}\n```\n"

# Verification controls: Lean-only core, Mathlib, and Mathlib plus Mathesis.Defs.
CONTROL_PROBLEMS = ("lean_nat_add_comm", "lean_sq_nonneg", "lean_poly_lower")
NEGATIVE_PROOFS = (
    ("sorry", "sorry", "forbidden_token"),
    ("admit", "admit", "forbidden_token"),
    ("invalid_tactic", "this_is_not_a_tactic_xyz", "lean_error"),
)

FORBIDDEN_RE = re.compile(r"\b(sorry|admit|axiom)\b")
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
        cut = rest.find(":=")
        if cut < 0 or _normalize(rest[:cut]) != signature:
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


def has_forbidden_token(text: str) -> str | None:
    found = FORBIDDEN_RE.search(text)
    return found.group(1) if found else None


def judge(proof: str, returncode: int, output: str, timed_out: bool = False):
    """Pure pass/fail rule -> (passed, failure_class, first_error_line)."""
    if timed_out:
        return False, "timeout", "timeout after " + str(LEAN_TIMEOUT_S) + "s"
    token = has_forbidden_token(proof) or has_forbidden_token(output)
    if token is not None:
        return False, "forbidden_token", "forbidden token: " + token
    error_line = ""
    for line in output.splitlines():
        if ERROR_RE.search(line):
            error_line = line.strip()
            break
    if error_line:
        return False, "lean_error", error_line
    if returncode != 0:
        return False, "lean_error", "exit code " + str(returncode)
    return True, "ok", ""


# -------------------------------------------------------------- Lean execution


@dataclass
class LeanRun:
    returncode: int
    output: str
    seconds: float
    timed_out: bool


def _lean_env() -> dict:
    env = dict(os.environ)
    elan = str(Path.home() / ".elan" / "bin")
    if shutil.which("lake") is None:
        env["PATH"] = elan + os.pathsep + env.get("PATH", "")
    return env


def run_lean(path, lean_dir=None, timeout: int = LEAN_TIMEOUT_S) -> LeanRun:
    cwd = Path(lean_dir) if lean_dir is not None else default_lean_dir()
    started = time.monotonic()
    try:
        completed = subprocess.run(
            lean_verify_command(path),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=_lean_env(),
        )
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", errors="replace")
        return LeanRun(-1, partial, time.monotonic() - started, True)
    except OSError as exc:
        raise EnvironmentFailure("cannot run lake: " + str(exc)) from exc
    output = (completed.stdout or "") + (completed.stderr or "")
    elapsed = time.monotonic() - started
    if "no such file or directory" in output.lower():
        # A missing candidate file is a harness bug, not a failed proof.
        raise EnvironmentFailure("candidate file not found by lake: " + output.strip()[:300])
    if completed.returncode < 0 or (
        completed.returncode != 0 and ENV_ERROR_RE.search(output)
    ):
        raise EnvironmentFailure(
            "lean environment failure (rc=" + str(completed.returncode) + "): "
            + output.strip()[:300]
        )
    return LeanRun(completed.returncode, output, elapsed, False)


@dataclass
class Verification:
    passed: bool
    failure_class: str
    first_error_line: str
    seconds: float
    returncode: int
    output: str


def verify_proof(
    header: str, proof: str, footer: str, path, lean_dir=None, timeout=LEAN_TIMEOUT_S
) -> Verification:
    """Write header+proof+footer to `path` and check it with Lean."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_candidate(header, proof, footer), encoding="utf-8")
    result = run_lean(target, lean_dir=lean_dir, timeout=timeout)
    output = result.output.replace(str(target.parent) + os.sep, "")
    passed, failure_class, first_error = judge(
        proof, result.returncode, output, result.timed_out
    )
    return Verification(
        passed, failure_class, first_error, result.seconds, result.returncode,
        output,
    )


# -------------------------------------------------------------------- problems


def load_b0_problems(limit=None):
    """Problems in problems.json order, each with header/footer parsed from its file."""
    base = default_lean_pilot_dir()
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


# ------------------------------------------------------------------ generation


def load_model(name: str = MODEL_NAME):
    """Load model and tokenizer; mlx is imported here so unit tests never need it."""
    from mlx_lm import load

    return load(name)


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


def generate_samples(model, tokenizer, prompt_ids, k, max_tokens, temp, seed):
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


def derived_b0_seed(seed: int, problem: str) -> int:
    return derive_seed(int(seed), problem, SEED_CONFIG) & SEED_MASK


def run_b0(run, problems, k, max_tokens, seed, temp=DEFAULT_TEMP, lean_dir=None,
           model_name=MODEL_NAME, progress=print) -> dict:
    """Generate and verify k samples per problem; return the summary dict."""
    model, tokenizer = load_model(model_name)
    per_problem = {}
    cdir = run.path / "candidates"
    for index, prob in enumerate(problems):
        name = prob["name"]
        derived = derived_b0_seed(seed, name)
        prompt_ids = encode_prompt(tokenizer, build_prompt(prob["header"]))
        texts, counts, gen_seconds = generate_samples(
            model, tokenizer, prompt_ids, k, max_tokens, temp, derived
        )
        passed_count = 0
        rdir = run.path / "responses"
        rdir.mkdir(exist_ok=True)
        for sample_index, (text, count) in enumerate(zip(texts, counts)):
            (rdir / (name + "_" + str(sample_index) + ".txt")).write_text(
                text, encoding="utf-8"
            )
            proof, reason = extract_proof(text, prob["header"])
            if proof is None:
                ver = Verification(False, reason, reason, 0.0, -1, "")
            else:
                ver = verify_proof(
                    prob["header"], proof, prob["footer"],
                    cdir / (name + "_" + str(sample_index) + ".lean"), lean_dir,
                )
            passed_count += 1 if ver.passed else 0
            run.append_result(
                {
                    "problem": name,
                    "sample_index": sample_index,
                    "passed": ver.passed,
                    "first_error_line": ver.first_error_line,
                    "generated_tokens": count,
                    "gen_seconds": gen_seconds,  # whole batch of k, shared by its samples
                    "verify_seconds": ver.seconds,
                    "seed": int(seed),
                    "derived_seed": derived,
                    "failure_class": ver.failure_class,
                    "truncated": count >= int(max_tokens),
                }
            )
        per_problem[name] = {
            "n": len(texts),
            "c": passed_count,
            "pass_at_1": pass_at_k(len(texts), passed_count, 1),
            "pass_at_k": pass_at_k(len(texts), passed_count, int(k)),
        }
        progress(
            "[" + str(index + 1) + "/" + str(len(problems)) + "] " + name
            + " passed " + str(passed_count) + "/" + str(len(texts))
        )
    return summarize_b0(per_problem, k)


def summarize_b0(per_problem: dict, k: int) -> dict:
    total = len(per_problem)
    mean1 = sum(v["pass_at_1"] for v in per_problem.values()) / total if total else 0.0
    meank = sum(v["pass_at_k"] for v in per_problem.values()) / total if total else 0.0
    return {
        "n_problems": total,
        "k": int(k),
        "pass_at_1": mean1,
        "pass_at_k": meank,
        "per_problem": per_problem,
    }


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
    return "\n".join(lines)
