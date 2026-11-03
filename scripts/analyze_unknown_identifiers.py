import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Names removed or renamed in the pinned Mathlib, mapped to the replacement expected at root level.
# An entry is only used when the Mathlib source confirms both halves (see classify()).
STALE_CANDIDATES = {
    "le_div_iff": "le_div_iff₀",
    "div_le_iff": "div_le_iff₀",
    "div_lt_iff": "div_lt_iff₀",
    "div_le_div_iff": "div_le_div_iff₀",
    "mul_right_inv": "mul_inv_cancel",
}

CATEGORY_ORDER = ["stale", "namespace_missing", "other"]
UNKNOWN_RE = re.compile(r"[Uu]nknown identifier `([^`]+)`")
FILE_RE = re.compile(r"([^\s:]+\.lean):")
BLOCK_COMMENT_RE = re.compile(r"/-.*?-/", re.S)
NAMESPACE_RE = re.compile(r"^\s*namespace\s+(\S+)\s*$")
SECTION_RE = re.compile(r"^\s*(?:noncomputable\s+)?section(?:\s+\S+)?\s*$")
END_RE = re.compile(r"^\s*end(?:\s+\S+)?\s*$")
OPEN_RE = re.compile(r"^\s*(?:private\s+)?open\s+(.*)$")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_args(argv: list) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify unknown-identifier failures in a run's results.jsonl (stale / namespace_missing / other).")
    parser.add_argument("--run", type=Path, required=True, help="run directory holding results.jsonl and candidates/ (relative paths tried against cwd, then the repo root)")
    parser.add_argument("--out", type=Path, default=None, help="JSON output path (default: <repo>/runs/analysis/unknown_identifiers_<run name>.json)")
    parser.add_argument("--mathlib", type=Path, default=None, help="Mathlib source dir (default: <repo>/lean/.lake/packages/mathlib/Mathlib)")
    return parser.parse_args(argv)


def definition_pattern(name: str) -> re.Pattern:
    # group(1) captures modifiers such as protected/private; the lookahead keeps `name` from matching `name'` or `name₀`.
    return re.compile(
        r"^\s*(?:@\[[^\]]*\]\s*)?((?:(?:private|protected|noncomputable|nonrec)\s+)*)"
        r"(?:theorem|lemma|def|abbrev)\s+" + re.escape(name) + r"(?![\w'.!?₀-₉])"
    )


def scan_file(path: Path, pattern: re.Pattern) -> list:
    """Return (line, namespace, protected, code) for each definition matching pattern, tracking namespace/section/end nesting."""
    text = path.read_text(encoding="utf-8", errors="replace")
    text = BLOCK_COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    stack = []
    hits = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        code = raw.split("--", 1)[0]
        m = NAMESPACE_RE.match(code)
        if m:
            stack.append(m.group(1))
            continue
        if SECTION_RE.match(code):
            stack.append("")
            continue
        if END_RE.match(code):
            if stack:
                stack.pop()
            continue
        m = pattern.match(code)
        if m:
            namespace = ".".join(part for part in stack if part)
            protected = bool(re.search(r"\b(?:protected|private)\b", m.group(1)))
            hits.append((line_no, namespace, protected, code.strip()))
    return hits


def files_mentioning(mathlib_dir: Path, name: str) -> list:
    proc = subprocess.run(
        ["grep", "-rlF", "--include=*.lean", name, str(mathlib_dir)],
        capture_output=True, text=True, check=False,
    )
    return sorted(Path(p) for p in proc.stdout.splitlines() if p)


def find_definitions(mathlib_dir: Path, name: str, cache: dict) -> list:
    if name not in cache:
        pattern = definition_pattern(name)
        found = []
        for path in files_mentioning(mathlib_dir, name):
            rel = "Mathlib/" + path.relative_to(mathlib_dir).as_posix()
            for line_no, namespace, protected, code in scan_file(path, pattern):
                found.append({
                    "location": f"{rel}:{line_no}",
                    "namespace": namespace or "(root)",
                    "protected": protected,
                    "code": code[:160],
                })
        cache[name] = found
    return cache[name]


def describe(d: dict) -> str:
    flags = " protected" if d["protected"] else ""
    return f"{d['location']} [namespace {d['namespace']}{flags}] {d['code']}"


def opened_namespaces(text: str) -> set:
    opened = set()
    for raw in text.splitlines():
        m = OPEN_RE.match(raw.split("--", 1)[0])
        if not m:
            continue
        rest = re.sub(r"\s+in\b.*$", "", m.group(1)).strip()
        for token in rest.split():
            if token != "scoped":
                opened.add(token)
    return opened


def classify(name: str, candidate_text, mathlib_dir: Path, cache: dict) -> dict:
    defs = find_definitions(mathlib_dir, name, cache)
    evidence = [describe(d) for d in defs]
    root_public = [d for d in defs if d["namespace"] == "(root)" and not d["protected"]]

    if name in STALE_CANDIDATES and not root_public:
        replacement = STALE_CANDIDATES[name]
        repl_root = [d for d in find_definitions(mathlib_dir, replacement, cache)
                     if d["namespace"] == "(root)" and not d["protected"]]
        if repl_root:
            return {
                "category": "stale",
                "suggestion": f"replace with {replacement}",
                "note": f"no root-level definition of {name} in Mathlib source; {replacement} is root-level there",
                "evidence": evidence + [describe(d) for d in repl_root[:3]],
            }

    if not defs:
        return {"category": "other", "suggestion": "", "note": "no definition found in Mathlib source", "evidence": []}
    if root_public:
        return {"category": "other", "suggestion": "", "note": "root-level definition exists; namespace is not the explanation, inspect manually", "evidence": evidence}

    public = [d for d in defs if not d["protected"]]
    if not public:
        return {"category": "other", "suggestion": "", "note": "only protected/private definitions exist; open does not expose them", "evidence": evidence}

    note = "" if candidate_text is not None else "candidate file not found; open statements unchecked. "
    opened = opened_namespaces(candidate_text) if candidate_text is not None else set()
    namespaces = sorted({d["namespace"] for d in public})
    missing = [ns for ns in namespaces if ns not in opened]
    if not missing:
        return {"category": "other", "suggestion": "", "note": note + f"candidate file already opens {', '.join(namespaces)}", "evidence": evidence}
    if len(missing) > 1:
        qualified = [ns for ns in missing if re.search(r"(?<![\w.])" + re.escape(ns) + r"\.", candidate_text or "")]
        if len(qualified) != 1:
            return {"category": "other", "suggestion": "", "note": note + f"ambiguous: defined in namespaces {', '.join(missing)}", "evidence": evidence}
        note += f"tie-break: candidate file uses {qualified[0]}. qualifier; "
        missing = qualified
    return {
        "category": "namespace_missing",
        "suggestion": f"open {missing[0]}",
        "note": note + f"defined in namespace {missing[0]}, not opened by candidate file",
        "evidence": evidence,
    }


def main(argv: list) -> int:
    args = parse_args(argv)
    root = repo_root()

    run_dir = None
    for candidate in (Path.cwd() / args.run, root / args.run):
        if (candidate / "results.jsonl").is_file():
            run_dir = candidate
            break
    if run_dir is None:
        print("results.jsonl not found under run dir: " + str(args.run), file=sys.stderr)
        return 1

    mathlib_dir = args.mathlib if args.mathlib is not None else root / "lean" / ".lake" / "packages" / "mathlib" / "Mathlib"
    if not mathlib_dir.is_dir():
        print("mathlib source not found at " + str(mathlib_dir) + "; nothing classified, nothing written", file=sys.stderr)
        return 1

    rows = [json.loads(line) for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    selected = [r for r in rows
                if r.get("failure_class") == "lean_error"
                and ("Unknown identifier" in r.get("first_error_line", "") or "unknown identifier" in r.get("first_error_line", ""))]

    groups = {}
    unparsed = []
    for r in selected:
        line = r["first_error_line"]
        m = UNKNOWN_RE.search(line)
        if not m:
            unparsed.append(line)
            continue
        file_m = FILE_RE.search(line)
        base = Path(file_m.group(1)).name if file_m else None
        groups.setdefault((m.group(1), base), []).append(r)

    cache = {}
    text_cache = {}
    merged = {}
    for (name, base), group in groups.items():
        candidate_text = None
        if base is not None:
            if base not in text_cache:
                path = run_dir / "candidates" / base
                text_cache[base] = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None
            candidate_text = text_cache[base]
        verdict = classify(name, candidate_text, mathlib_dir, cache)
        key = (name, verdict["category"], verdict["suggestion"])
        example = FILE_RE.sub(lambda m: Path(m.group(1)).name + ":", group[0]["first_error_line"], count=1)
        entry = merged.setdefault(key, {
            "name": name,
            "category": verdict["category"],
            "rows": 0,
            "problems": set(),
            "candidate_files": set(),
            "example_error_line": example,
            "suggestion": verdict["suggestion"],
            "note": verdict["note"],
            "evidence": [],
        })
        entry["rows"] += len(group)
        entry["problems"].update(r["problem"] for r in group)
        if base is not None:
            entry["candidate_files"].add(base)
        for line in verdict["evidence"]:
            if line not in entry["evidence"]:
                entry["evidence"].append(line)
    entries = []
    for entry in merged.values():
        entry["problems"] = sorted(entry["problems"])
        entry["candidate_files"] = sorted(entry["candidate_files"])
        entries.append(entry)
    entries.sort(key=lambda e: (CATEGORY_ORDER.index(e["category"]), -e["rows"], e["name"]))

    category_rows = {c: sum(e["rows"] for e in entries if e["category"] == c) for c in CATEGORY_ORDER}

    print("unknown identifier analysis for " + str(run_dir))
    print("selected rows: " + str(len(selected)) + "; unparsed rows: " + str(len(unparsed)))
    print("name | category | rows | suggestion | example error line")
    for e in entries:
        print(f"{e['name']} | {e['category']} | {e['rows']} | {e['suggestion']} | {e['example_error_line'][:150]}")
    print("rows per category: " + ", ".join(f"{c}={category_rows[c]}" for c in CATEGORY_ORDER))
    for e in entries:
        print(f"- {e['name']} ({e['category']}): {e['note']}")
        for line in e["evidence"][:6]:
            print("    " + line)

    out_path = args.out if args.out is not None else root / "runs" / "analysis" / f"unknown_identifiers_{run_dir.name}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run": str(run_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mathlib": str(mathlib_dir),
        "selection": "failure_class == lean_error and first_error_line contains 'Unknown identifier' or 'unknown identifier'",
        "selected_rows": len(selected),
        "unparsed_rows": unparsed,
        "category_rows": category_rows,
        "entries": entries,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("json written to: " + str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
