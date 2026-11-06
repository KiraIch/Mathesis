"""Statistical significance testing for hint-gap benchmark runs.

Computes Fisher's exact test (two-tailed) on 2x2 contingency tables
[[hint_success, hint_fail], [plain_success, plain_fail]] using math.comb,
classifies problems into hint_helps / hint_hurts / no_detectable_effect / plain_ceiling,
and performs Holm-Bonferroni multiple comparison correction on:
  - Primary analysis: informative problems (non-ceiling and plain.c + hint.c >= 1)
  - Sensitivity analysis: all non-ceiling problems
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
REQUIRED_N = 32
ALPHA = 0.05
REL_TOL = 1e-9


class SignificanceError(Exception):
    """Raised for input validation and duplicate problem errors."""


def fisher_exact_2x2(table: list[list[int]], rel_tol: float = REL_TOL) -> float:
    """Two-sided Fisher's exact test for a 2x2 contingency table using math.comb.

    table: [[hint_success, hint_fail], [plain_success, plain_fail]]
    Returns two-tailed p-value defined as the sum of hypergeometric probabilities
    of all tables with probability <= observed table probability * (1 + rel_tol).
    """
    if len(table) != 2 or len(table[0]) != 2 or len(table[1]) != 2:
        raise ValueError(f"table must be 2x2, got {table!r}")
    a, b = table[0]
    c, d = table[1]
    if a < 0 or b < 0 or c < 0 or d < 0:
        raise ValueError(f"table cells must be non-negative integers, got {table!r}")

    r0, r1 = a + b, c + d
    c0, c1 = a + c, b + d
    total = r0 + r1
    denom = math.comb(total, c0)
    if denom == 0:
        return 1.0

    x_min = max(0, c0 - r1)
    x_max = min(r0, c0)
    nums = {x: math.comb(r0, x) * math.comb(r1, c0 - x) for x in range(x_min, x_max + 1)}
    obs_num = nums[a]

    # Use Fraction for exact arithmetic without floating point precision issues
    tol_factor = 1 + Fraction(str(rel_tol)) if rel_tol else Fraction(1)
    cutoff = obs_num * tol_factor

    total_num = sum(v for v in nums.values() if v <= cutoff)
    return min(1.0, float(Fraction(total_num, denom)))


def holm_bonferroni(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni step-down correction for multiple comparisons.

    Given a list of p-values, returns a list of adjusted p-values in the
    original order:
      p_adj_(i) = min(1.0, max(p_adj_(i-1), (m - i) * p_(i)))
    where i = 0 .. m-1 is the 0-based rank of sorted p-values.
    """
    m = len(p_values)
    if m == 0:
        return []
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    adj = [0.0] * m
    cum_max = 0.0
    for rank, (orig_idx, p) in enumerate(indexed):
        val = min(1.0, p * (m - rank))
        cum_max = max(cum_max, val)
        adj[orig_idx] = cum_max
    return adj


def load_run_summary(run_dir: Path) -> dict[str, Any]:
    """Load and validate summary.json from a hint-gap run directory."""
    if not run_dir.is_dir():
        raise SignificanceError(f"{run_dir}: not a directory")

    summary_file = run_dir / "summary.json"
    if not summary_file.is_file():
        raise SignificanceError(f"{run_dir}: missing summary.json")

    try:
        data = json.loads(summary_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SignificanceError(f"{summary_file}: invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise SignificanceError(f"{summary_file}: root JSON must be an object")

    if data.get("status") != "ok":
        status_val = data.get("status")
        err_msg = data.get("error", "")
        detail = f" (error: {err_msg})" if err_msg else ""
        raise SignificanceError(
            f"{run_dir}: status is not ok (status={status_val!r}){detail}"
        )

    summary_block = data.get("summary")
    if isinstance(summary_block, dict) and "per_problem" in summary_block:
        per_problem = summary_block["per_problem"]
    elif "per_problem" in data and isinstance(data["per_problem"], dict):
        per_problem = data["per_problem"]
    else:
        raise SignificanceError(f"{summary_file}: missing 'per_problem' dictionary")

    if not isinstance(per_problem, dict):
        raise SignificanceError(f"{summary_file}: 'per_problem' must be a dictionary")

    # Validate n == 32 for each problem
    for name, pdata in per_problem.items():
        if not isinstance(pdata, dict):
            raise SignificanceError(f"{summary_file}: problem '{name}' entry must be an object")
        plain = pdata.get("plain")
        hint = pdata.get("hint")
        if not isinstance(plain, dict) or not isinstance(hint, dict):
            raise SignificanceError(
                f"{summary_file}: problem '{name}' missing 'plain' or 'hint' dictionary"
            )

        pn = plain.get("n")
        hn = hint.get("n")
        if pn != REQUIRED_N or hn != REQUIRED_N:
            raise SignificanceError(
                f"{run_dir}: problem '{name}' has n != {REQUIRED_N} (plain n={pn}, hint n={hn})"
            )

        pc = plain.get("c")
        hc = hint.get("c")
        if not isinstance(pc, int) or pc < 0 or pc > pn:
            raise SignificanceError(f"{summary_file}: problem '{name}' invalid plain c={pc}")
        if not isinstance(hc, int) or hc < 0 or hc > hn:
            raise SignificanceError(f"{summary_file}: problem '{name}' invalid hint c={hc}")

    return per_problem


def load_and_merge_runs(
    run_dirs: list[Path], prefer_last: bool = False
) -> dict[str, dict[str, Any]]:
    """Load per_problem from run directories, handling duplicates."""
    collected: dict[str, dict[str, Any]] = {}
    sources: dict[str, Path] = {}

    for rdir in run_dirs:
        per_problem = load_run_summary(rdir)
        for name, pdata in per_problem.items():
            if name in sources:
                if not prefer_last:
                    raise SignificanceError(
                        f"duplicate problem '{name}' found in {rdir} "
                        f"(previously seen in {sources[name]}); pass --prefer-last to allow overwrite"
                    )
            sources[name] = rdir
            collected[name] = pdata

    return collected


def build_significance_report(
    per_problem_input: dict[str, dict[str, Any]],
    alpha: float = ALPHA,
    rel_tol: float = REL_TOL,
) -> dict[str, Any]:
    """Perform Fisher exact test, classification, and primary/sensitivity Holm corrections."""
    per_problem_out: dict[str, dict[str, Any]] = {}
    tested_names: list[str] = []
    tested_p_values: list[float] = []
    informative_names: list[str] = []
    informative_p_values: list[float] = []

    for name in sorted(per_problem_input.keys()):
        pdata = per_problem_input[name]
        pc = int(pdata["plain"]["c"])
        pn = int(pdata["plain"]["n"])
        hc = int(pdata["hint"]["c"])
        hn = int(pdata["hint"]["n"])

        plain_pass = float(Fraction(pc, pn))
        hint_pass = float(Fraction(hc, hn))
        gap = float(Fraction(hc, hn) - Fraction(pc, pn))

        is_ceiling = (pc == pn)
        is_informative = bool(not is_ceiling and (pc + hc >= 1))

        entry: dict[str, Any] = {
            "plain": {"c": pc, "n": pn, "pass_at_1": plain_pass},
            "hint": {"c": hc, "n": hn, "pass_at_1": hint_pass},
            "gap": gap,
            "p": None,
            "p_holm": None,
            "p_holm_all": None,
            "classification": "",
            "category": "",
            "hint_helps_holm": False,
            "hint_helps_holm_all": False,
            "informative": is_informative,
            "tested": False,
        }

        # Plain ceiling: when plain success count equals n, do not test
        if is_ceiling:
            entry["classification"] = "plain_ceiling"
            entry["category"] = "plain_ceiling"
            entry["tested"] = False
        else:
            table = [[hc, hn - hc], [pc, pn - pc]]
            p_val = fisher_exact_2x2(table, rel_tol=rel_tol)
            entry["p"] = p_val
            entry["tested"] = True

            # Classification (unadjusted Fisher p-value)
            if hint_pass > plain_pass and p_val < alpha:
                cls = "hint_helps"
            elif hint_pass < plain_pass and p_val < alpha:
                cls = "hint_hurts"
            else:
                cls = "no_detectable_effect"

            entry["classification"] = cls
            entry["category"] = cls

            # Sensitivity family (all non-ceiling tested problems)
            tested_names.append(name)
            tested_p_values.append(p_val)

            # Primary family (informative problems: non-ceiling and pc + hc >= 1)
            if is_informative:
                informative_names.append(name)
                informative_p_values.append(p_val)

        per_problem_out[name] = entry

    # Primary Holm-Bonferroni correction (informative family)
    info_adj_p = holm_bonferroni(informative_p_values)
    info_map = dict(zip(informative_names, info_adj_p))

    # Sensitivity Holm-Bonferroni correction (all tested non-ceiling problems)
    all_adj_p = holm_bonferroni(tested_p_values)
    all_map = dict(zip(tested_names, all_adj_p))

    for name in tested_names:
        item = per_problem_out[name]
        # Sensitivity
        p_all = all_map[name]
        item["p_holm_all"] = p_all
        item["hint_helps_holm_all"] = bool(item["gap"] > 0 and p_all < alpha)

        # Primary
        if item["informative"]:
            p_pri = info_map[name]
            item["p_holm"] = p_pri
            item["hint_helps_holm"] = bool(item["gap"] > 0 and p_pri < alpha)
        else:
            item["p_holm"] = None
            item["hint_helps_holm"] = False

    n_problems = len(per_problem_out)
    n_tested = len(tested_names)
    n_informative = len(informative_names)
    n_hint_helps = sum(1 for v in per_problem_out.values() if v["classification"] == "hint_helps")
    n_hint_hurts = sum(1 for v in per_problem_out.values() if v["classification"] == "hint_hurts")
    n_no_detectable = sum(
        1 for v in per_problem_out.values() if v["classification"] == "no_detectable_effect"
    )
    n_plain_ceiling = sum(
        1 for v in per_problem_out.values() if v["classification"] == "plain_ceiling"
    )
    n_hint_helps_holm = sum(1 for v in per_problem_out.values() if v["hint_helps_holm"])
    n_hint_helps_holm_all = sum(1 for v in per_problem_out.values() if v["hint_helps_holm_all"])

    summary = {
        "n_problems": n_problems,
        "n_tested": n_tested,
        "n_informative": n_informative,
        "n_hint_helps": n_hint_helps,
        "n_hint_hurts": n_hint_hurts,
        "n_no_detectable_effect": n_no_detectable,
        "n_plain_ceiling": n_plain_ceiling,
        "n_hint_helps_holm": n_hint_helps_holm,
        "n_hint_helps_holm_all": n_hint_helps_holm_all,
        "n_passing_holm": n_hint_helps_holm,
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "n_problems": n_problems,
        "n_tested": n_tested,
        "n_informative": n_informative,
        "n_hint_helps": n_hint_helps,
        "n_hint_hurts": n_hint_hurts,
        "n_hint_helps_holm": n_hint_helps_holm,
        "n_hint_helps_holm_all": n_hint_helps_holm_all,
        "n_passing_holm": n_hint_helps_holm,
        "per_problem": per_problem_out,
    }


def format_table(report: dict[str, Any]) -> str:
    """Format report into a text table sorted by gap descending."""
    summary = report["summary"]
    per_problem = report["per_problem"]

    # Sort: descending gap, ascending p (None sorted last), ascending problem name
    def sort_key(item: tuple[str, dict[str, Any]]):
        name, val = item
        pval = val["p"]
        p_sort = pval if pval is not None else 2.0
        return (-val["gap"], p_sort, name)

    ordered = sorted(per_problem.items(), key=sort_key)

    lines = [
        f"Summary: tested={summary['n_tested']}/{summary['n_problems']} "
        f"informative={summary['n_informative']} "
        f"hint_helps={summary['n_hint_helps']} "
        f"hint_hurts={summary['n_hint_hurts']} "
        f"passed_holm={summary['n_hint_helps_holm']} (all={summary['n_hint_helps_holm_all']}) "
        f"plain_ceiling={summary['n_plain_ceiling']}",
        f"{'problem':42s} | {'plain':7s} | {'hint':7s} | {'gap':7s} | {'p':10s} | {'p_holm':10s} | {'p_holm_all':10s} | {'classification':20s} | {'holm':5s}",
        "-" * 135,
    ]

    for name, p in ordered:
        pc = p["plain"]["c"]
        pn = p["plain"]["n"]
        hc = p["hint"]["c"]
        hn = p["hint"]["n"]

        pval = p["p"]
        phval = p["p_holm"]
        ph_all_val = p["p_holm_all"]

        def _fmt(val: float | None) -> str:
            if val is None:
                return "-"
            if val < 0.0001:
                return "<0.0001"
            return f"{val:.4f}"

        p_str = _fmt(pval)
        ph_str = _fmt(phval)
        ph_all_str = _fmt(ph_all_val)

        gap_str = f"{p['gap']:+.4f}"
        cls_str = p["classification"]
        hlm_str = str(p["hint_helps_holm"])

        lines.append(
            f"{name:42s} | {pc:2d}/{pn:2d}   | {hc:2d}/{hn:2d}   | {gap_str:7s} | {p_str:10s} | {ph_str:10s} | {ph_all_str:10s} | {cls_str:20s} | {hlm_str:5s}"
        )

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Statistical significance report for hint-gap runs."
    )
    parser.add_argument(
        "runs",
        nargs="+",
        type=Path,
        help="one or more hint-gap-merged run directories",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write output JSON to file (default: stdout)",
    )
    parser.add_argument(
        "--table",
        action="store_true",
        default=False,
        help="print text table sorted by gap",
    )
    parser.add_argument(
        "--prefer-last",
        action="store_true",
        default=False,
        help="prefer later run directory on duplicate problems instead of raising error",
    )
    args = parser.parse_args(argv)

    try:
        problems_data = load_and_merge_runs(args.runs, prefer_last=args.prefer_last)
    except SignificanceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report = build_significance_report(problems_data)
    json_text = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json_text, encoding="utf-8")

    if args.table:
        table_text = format_table(report)
        print(table_text)
    elif args.out is None:
        sys.stdout.write(json_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
