#!/usr/bin/env python3
"""Extract `have` statements from reference proofs as hint candidates.

Reads benchmark/<name>/problems.json. For each problem, every typed `have`
in reference_proof gives a candidate `<name> : <statement>` (the text before
`:=`; proof bodies are never included). Anonymous `have : P` is named `this`.
Untyped `have h := e` is counted in n_have but yields no candidate.

Reports whether each problem's `auxiliary` text equals one of the candidate
statements after whitespace normalization. Writes JSON to stdout or --out.
Read-only apart from --out. Stdlib only.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HAVE_RE = re.compile(r"^[·.]?\s*have(?=[\s:])\s*(.*)$")
NAMED_RE = re.compile(r"^([^\s:]+)\s*:(?!=)\s*(.*)$", re.S)
ANON_RE = re.compile(r"^:(?!=)\s*(.*)$", re.S)


def normalize(text):
    return " ".join(text.split())


def _indent(line):
    return len(line) - len(line.lstrip())


def _have_statement(lines, index):
    """Return (name, statement) for a typed have starting at lines[index], else None."""
    line = lines[index]
    match = HAVE_RE.match(line.strip())
    if match is None:
        return None
    text = match.group(1)
    column = _indent(line)
    # A statement may span lines; keep joining more-indented lines until `:=`.
    next_index = index + 1
    while ":=" not in text and next_index < len(lines) and _indent(lines[next_index]) > column:
        text = text + " " + lines[next_index].strip()
        next_index += 1
    if ":=" not in text:
        return None
    head = text.split(":=", 1)[0].strip()
    named = NAMED_RE.match(head)
    if named is not None:
        return named.group(1), normalize(named.group(2))
    anon = ANON_RE.match(head)
    if anon is not None:
        return "this", normalize(anon.group(1))
    return None


def extract_have_statements(reference_proof):
    """Return (n_have, [(name, statement), ...]) for a list of tactic lines."""
    n_have = 0
    statements = []
    for index, line in enumerate(reference_proof):
        if HAVE_RE.match(line.strip()) is None:
            continue
        n_have += 1
        found = _have_statement(reference_proof, index)
        if found is not None and found[1]:
            statements.append(found)
    return n_have, statements


def extract_problem(entry):
    n_have, statements = extract_have_statements(entry["reference_proof"])
    auxiliary = entry["auxiliary"]
    aux_norm = normalize(auxiliary)
    matches = bool(aux_norm) and any(aux_norm == normalize(stmt) for _, stmt in statements)
    return {
        "name": entry["name"],
        "insight": bool(entry["insight"]),
        "n_have": n_have,
        "hints": [name + " : " + stmt for name, stmt in statements],
        "current_auxiliary": auxiliary,
        "auxiliary_matches_have": matches,
        "retired": str(entry.get("retired", "")),
    }


def summarize(rows):
    insight = [r for r in rows if r["insight"]]
    routine = [r for r in rows if not r["insight"]]
    matched = [r for r in insight if r["auxiliary_matches_have"]]
    return {
        "n_problems": len(rows),
        "n_insight": len(insight),
        "n_routine": len(routine),
        "routine_with_have": sum(1 for r in routine if r["n_have"] > 0),
        "insight_with_have": sum(1 for r in insight if r["n_have"] > 0),
        "insight_with_hint": sum(1 for r in insight if r["hints"]),
        "insight_auxiliary_matches_have": len(matched),
        "insight_auxiliary_match_ratio": (len(matched) / len(insight)) if insight else None,
    }


def load_problems(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "problems" in data:
        return data["problems"]
    if isinstance(data, list):
        return data
    raise ValueError("problems file needs a list or a dict with problems: " + str(path))


def build_report(problems, source):
    rows = [extract_problem(entry) for entry in problems]
    return {"source": source, "summary": summarize(rows), "problems": rows}


FIRST_HAVE_RULE = "first typed have in reference_proof, as '<name> : <statement>'"


def first_have_hint_file(report):
    """Hint file for `mathesis.cli hint-gap --hints`: each problem's first extracted have."""
    hints = {row["name"]: row["hints"][0] for row in report["problems"]
             if row["hints"] and not row.get("retired")}
    return {"rule": FIRST_HAVE_RULE, "source": report["source"], "hints": hints}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("benchmark", help="benchmark directory name under benchmark/, e.g. lean_hard")
    parser.add_argument("--out", type=Path, default=None,
                        help="write JSON here (parent directories are created); default stdout")
    parser.add_argument("--first-have-hints", type=Path, default=None,
                        help="also write a hint-gap --hints file using each problem's first have")
    args = parser.parse_args(argv)

    path = ROOT / "benchmark" / args.benchmark / "problems.json"
    if not path.is_file():
        parser.error("problems file not found: " + str(path))
    report = build_report(load_problems(path), str(path))
    if args.first_have_hints is not None:
        args.first_have_hints.parent.mkdir(parents=True, exist_ok=True)
        args.first_have_hints.write_text(
            json.dumps(first_have_hint_file(report), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out is None:
        sys.stdout.write(text)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
