#!/usr/bin/env python3
"""Read-only audit of insight labels against a B0 run's per-sample results.

Reads benchmark/lean_hard/problems.json and <run>/results.jsonl, computes the
plain pass@1 per problem (passed samples / samples, k=8), prints one table row
per problem plus summary statistics, and writes the same content as JSON.

Nothing is modified except the --out file. Stdlib only.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROBLEMS = ROOT / "benchmark" / "lean_hard" / "problems.json"
DEFAULT_RUN = ROOT / "runs" / "20261103T122531Z_b0"
DEFAULT_OUT = ROOT / "runs" / "analysis" / "insight_audit.json"
K = 8


def load_problems(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    problems = data["problems"]
    return problems


def load_results(path):
    """Return {problem: {sample_index: passed}} and a list of warnings."""
    samples = defaultdict(dict)
    warnings = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            name = row["problem"]
            idx = row["sample_index"]
            if idx in samples[name]:
                warnings.append(
                    f"duplicate sample: problem={name} sample_index={idx} (line {lineno})"
                )
            samples[name][idx] = bool(row["passed"])
    return samples, warnings


def aux_nonempty(problem):
    aux = problem.get("auxiliary")
    return isinstance(aux, str) and aux.strip() != ""


def build_rows(problems, samples):
    rows = []
    for p in problems:
        name = p["name"]
        outcomes = samples.get(name, {})
        n = len(outcomes)
        c = sum(1 for v in outcomes.values() if v)
        pass_at_1 = c / n if n else None
        if n and c == n and n == K:
            band = "ceiling"
        elif n and c == 0:
            band = "floor"
        else:
            band = ""
        rows.append(
            {
                "name": name,
                "insight": bool(p.get("insight")),
                "aux_nonempty": aux_nonempty(p),
                "plain_pass": c,
                "n_samples": n,
                "pass_at_1": pass_at_1,
                "band": band,
                "family": p.get("family"),
                "difficulty": p.get("difficulty"),
                "mathlib_match": p.get("mathlib_match"),
            }
        )
    return rows


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def summarize(rows):
    mismatch = [
        {"name": r["name"], "insight": r["insight"], "aux_nonempty": r["aux_nonempty"]}
        for r in rows
        if r["insight"] != r["aux_nonempty"]
    ]
    insight_rows = [r for r in rows if r["insight"]]
    routine_rows = [r for r in rows if not r["insight"]]
    band_counts = {}
    for label, group in (("insight", insight_rows), ("routine", routine_rows)):
        band_counts[label] = {
            "n_problems": len(group),
            "ceiling_8_of_8": sum(1 for r in group if r["band"] == "ceiling"),
            "floor_0_of_8": sum(1 for r in group if r["band"] == "floor"),
        }
    return {
        "insight_vs_aux_mismatch": mismatch,
        "mean_pass_at_1": {
            "insight": mean([r["pass_at_1"] for r in insight_rows]),
            "routine": mean([r["pass_at_1"] for r in routine_rows]),
            "n_insight": len(insight_rows),
            "n_routine": len(routine_rows),
        },
        "ceiling_floor_by_insight": band_counts,
    }


def fmt(x):
    return "-" if x is None else str(x)


def print_table(rows):
    headers = [
        "name", "insight", "aux", "plain_pass", "band",
        "family", "diff", "mathlib_match",
    ]
    table = []
    for r in rows:
        table.append([
            r["name"],
            "Y" if r["insight"] else "N",
            "Y" if r["aux_nonempty"] else "N",
            f"{r['plain_pass']}/{r['n_samples']}",
            r["band"] or "-",
            fmt(r["family"]),
            fmt(r["difficulty"]),
            fmt(r["mathlib_match"]),
        ])
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in table)) if table else len(headers[i])
        for i in range(len(headers))
    ]
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("-" * len(line))
    for row in table:
        print("  ".join(v.ljust(widths[i]) for i, v in enumerate(row)))


def print_summary(summary):
    print()
    print("== Summary ==")
    mm = summary["insight_vs_aux_mismatch"]
    if mm:
        print(f"(1) insight != aux_nonempty for {len(mm)} problem(s):")
        for m in mm:
            print(f"    {m['name']}: insight={m['insight']} aux_nonempty={m['aux_nonempty']}")
    else:
        print("(1) insight label and aux_nonempty are identical for every problem.")
    mp = summary["mean_pass_at_1"]
    print(
        f"(2) mean plain pass@1: insight={fmt(mp['insight'])} (n={mp['n_insight']}), "
        f"routine={fmt(mp['routine'])} (n={mp['n_routine']})"
    )
    print("(3) ceiling (8/8) and floor (0/8) counts by group:")
    for label, c in summary["ceiling_floor_by_insight"].items():
        print(
            f"    {label}: problems={c['n_problems']} "
            f"ceiling={c['ceiling_8_of_8']} floor={c['floor_0_of_8']}"
        )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--problems", type=Path, default=DEFAULT_PROBLEMS,
                    help="problems.json (key 'problems')")
    ap.add_argument("--run", type=Path, default=DEFAULT_RUN,
                    help="B0 run directory containing results.jsonl")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help="JSON output path (parent directories are created)")
    args = ap.parse_args(argv)

    problems = load_problems(args.problems)
    samples, warnings = load_results(args.run / "results.jsonl")

    names = {p["name"] for p in problems}
    missing = sorted(names - set(samples))
    extra = sorted(set(samples) - names)
    for name in missing:
        warnings.append(f"problem in problems.json has no results: {name}")
    for name in extra:
        warnings.append(f"results contain problem not in problems.json: {name}")
    short = sorted(n for n in names & set(samples) if len(samples[n]) != K)
    for name in short:
        warnings.append(f"problem {name} has {len(samples[name])} samples (expected k={K})")

    rows = build_rows(problems, samples)
    summary = summarize(rows)

    print_table(rows)
    print_summary(summary)
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)

    result = {
        "problems_file": str(args.problems),
        "run_dir": str(args.run),
        "k": K,
        "n_problems": len(rows),
        "warnings": warnings,
        "rows": rows,
        "summary": summary,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
