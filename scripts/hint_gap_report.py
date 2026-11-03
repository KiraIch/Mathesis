"""Read-only statistics report for a hint-gap run.

Reads results.jsonl of one hint-gap run (--hint-run) and one B0 run (--b0-run) and
reports per-problem pass@1 for the plain and hint conditions, ceiling/floor counts,
a two-layer bootstrap 95% CI of the mean gap, and a noise floor taken from the
plain-vs-plain difference between the two independent plain samples of the same problem.

Nothing is sampled from a model and no derived seed is touched: the only randomness is the
bootstrap, driven by --seed. Bootstrap interval ends are reported exactly as computed: a
bound that lands on 0 is flagged in the output, never nudged or clamped.
"""
import argparse
import json
import random
import statistics
import sys
from fractions import Fraction
from pathlib import Path

DEFAULT_RESAMPLES = 10000
DEFAULT_SEED = 0
CI_LEVEL = 0.95

SCHEMA_VERSION = 1


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------ loading

def read_results(path) -> list:
    """Rows of a results.jsonl; blank lines are skipped, a malformed line raises."""
    rows = []
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{number}: invalid JSON ({exc})") from exc
    return rows


def read_manifest_problems(run_dir):
    """Planned problem list from manifest.json args.problems, or None when unavailable."""
    path = Path(run_dir) / "manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    problems = (manifest.get("args") or {}).get("problems")
    return list(problems) if problems else None


def tally(rows, default_condition=None) -> dict:
    """{problem: {condition: {sample_index: passed}}}; a repeated sample_index keeps the last row."""
    out = {}
    for row in rows:
        condition = row.get("condition", default_condition)
        slot = out.setdefault(row["problem"], {}).setdefault(condition, {})
        slot[int(row["sample_index"])] = bool(row["passed"])
    return out


def counts(samples: dict) -> dict:
    return {"c": sum(1 for v in samples.values() if v), "n": len(samples)}


# ----------------------------------------------------------------- bootstrap

def binomial_resample(rng, c: int, n: int) -> int:
    """Successes among n Bernoulli(c/n) draws.

    Deterministic at the endpoints: c == 0 gives 0 and c == n gives n, without touching the RNG.
    """
    if n <= 0:
        return 0
    if c <= 0:
        return 0
    if c >= n:
        return n
    p = c / n
    return sum(1 for _ in range(n) if rng.random() < p)


def percentile_interval(values, level=CI_LEVEL):
    """Percentile interval of a list; index rule matches llm_baseline.summarize_hint_gap."""
    ordered = sorted(values)
    total = len(ordered)
    alpha = (1.0 - level) / 2.0
    return [ordered[int(alpha * (total - 1))], ordered[int((1.0 - alpha) * (total - 1))]]


def two_layer_bootstrap(pairs: list, resamples: int, seed: int):
    """Bootstrap the mean gap.

    pairs: [(plain_c, plain_n, hint_c, hint_n), ...] one tuple per problem.
    Layer 1 resamples problems with replacement; layer 2 redraws each selected problem's
    plain and hint successes as Binomial(n, c/n). Returns the sorted resampled means,
    or None for an empty set.
    """
    if resamples < 1:
        raise ValueError("resamples must be >= 1")
    total = len(pairs)
    if total == 0:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(resamples):
        acc = 0.0
        for _ in range(total):
            pc, pn, hc, hn = pairs[rng.randrange(total)]
            plain = binomial_resample(rng, pc, pn) / pn if pn else 0.0
            hint = binomial_resample(rng, hc, hn) / hn if hn else 0.0
            acc += hint - plain
        means.append(acc / total)
    means.sort()
    return means


def problem_only_bootstrap(gaps: list, resamples: int, seed: int):
    """Layer 1 only (resample problems, keep observed gaps); a reference for the two-layer CI."""
    if resamples < 1:
        raise ValueError("resamples must be >= 1")
    total = len(gaps)
    if total == 0:
        return None
    rng = random.Random(seed)
    means = [sum(gaps[rng.randrange(total)] for _ in range(total)) / total
             for _ in range(resamples)]
    means.sort()
    return means


def ci_block(means, point):
    if means is None:
        return {"point": None, "ci95": None, "lower_at_zero": None, "upper_at_zero": None,
                "note": "no problems: interval undefined"}
    low, high = percentile_interval(means)
    return {
        "point": point,
        "ci95": [low, high],
        "lower_at_zero": low == 0.0,
        "upper_at_zero": high == 0.0,
        "note": "interval ends are reported as computed; a bound equal to 0 is not adjusted",
    }


# ----------------------------------------------------------------- noise floor

def quantile(sorted_values, q):
    """Linear-interpolation quantile (numpy default) of an already sorted list."""
    if not sorted_values:
        return None
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def noise_floor(plain_by_problem: dict, b0_by_problem: dict, gaps: dict, hint_derived: dict,
                b0_derived: dict) -> dict:
    """|pass@1(hint-run plain) - pass@1(B0)| over problems present in both, and what it says about |gap|."""
    shared = sorted(p for p in plain_by_problem if p in b0_by_problem
                    and plain_by_problem[p]["n"] > 0 and b0_by_problem[p]["n"] > 0)
    per_problem = {}
    for name in shared:
        a, b = plain_by_problem[name], b0_by_problem[name]
        per_problem[name] = {
            "hint_run_plain": a, "b0": b,
            "abs_diff": abs(a["c"] / a["n"] - b["c"] / b["n"]),
            "same_derived_seed": (name in hint_derived and name in b0_derived
                                  and hint_derived[name] == b0_derived[name]),
        }
    values = sorted(v["abs_diff"] for v in per_problem.values())
    result = {
        "n_overlap": len(shared),
        "problems_without_b0": sorted(p for p in plain_by_problem if p not in b0_by_problem),
        "same_derived_seed_count": sum(1 for v in per_problem.values() if v["same_derived_seed"]),
        "median": None, "p90": None, "mean": None, "max": None,
        "per_problem": per_problem,
        "gap_interpretation": None,
        "note": ("noise is the absolute difference of two independent plain samples; problems at "
                 "ceiling or floor in both contribute 0, so the distribution is a lower-leaning "
                 "estimate when most overlapping problems are saturated"),
    }
    if not values:
        result["status"] = "no_overlap"
        result["gap_interpretation"] = {
            "reason": "no problem has both hint-run plain and B0 samples; |gap| cannot be "
                      "compared with an empirical noise distribution"}
        return result
    result["status"] = "ok"
    result["median"] = quantile(values, 0.5)
    result["p90"] = quantile(values, 0.9)
    result["mean"] = statistics.fmean(values)
    result["max"] = values[-1]
    result["gap_interpretation"] = interpret_gaps(gaps, values, result["median"], result["p90"])
    return result


def interpret_gaps(gaps: dict, noise_values: list, median, p90) -> dict:
    """Place each problem's |gap| in the empirical noise distribution."""
    per_problem = {}
    for name, gap in sorted(gaps.items()):
        size = abs(gap)
        at_most = sum(1 for v in noise_values if v <= size)
        per_problem[name] = {
            "abs_gap": size,
            # share of noise differences that are <= |gap|; 1.0 means |gap| is at the noise maximum or above
            "noise_percentile_rank": at_most / len(noise_values),
            "exceeds_noise_median": size > median,
            "exceeds_noise_p90": size > p90,
        }
    nonzero = [v for v in per_problem.values() if v["abs_gap"] > 0]
    sizes = [abs(g) for g in gaps.values()]
    return {
        "mean_abs_gap": statistics.fmean(sizes) if sizes else None,
        "n_nonzero_gap": len(nonzero),
        "n_exceeding_noise_median": sum(1 for v in nonzero if v["exceeds_noise_median"]),
        "n_exceeding_noise_p90": sum(1 for v in nonzero if v["exceeds_noise_p90"]),
        "per_problem": per_problem,
    }


# --------------------------------------------------------------------- report

def derived_seeds(rows, condition=None) -> dict:
    out = {}
    for row in rows:
        if condition is not None and row.get("condition") != condition:
            continue
        if "derived_seed" in row:
            out[row["problem"]] = row["derived_seed"]
    return out


def completeness(hint_tally: dict, planned, n_rows: int) -> dict:
    """Compare the rows present with problems x 2 conditions x k."""
    group_sizes = [len(samples) for conds in hint_tally.values() for samples in conds.values()]
    k = max(group_sizes) if group_sizes else 0
    problems = list(planned) if planned else sorted(hint_tally)
    expected = len(problems) * 2 * k
    reasons = []
    missing_problems = sorted(p for p in problems if p not in hint_tally)
    if missing_problems:
        reasons.append(f"{len(missing_problems)} planned problem(s) have no rows")
    short = sorted(f"{p}/{c}: {len(s)}/{k}"
                   for p, conds in hint_tally.items() for c, s in conds.items() if len(s) < k)
    if short:
        reasons.append(f"{len(short)} problem-condition group(s) have fewer than k samples")
    unpaired = sorted(p for p, conds in hint_tally.items()
                      if "plain" not in conds or "hint" not in conds)
    if unpaired:
        reasons.append(f"{len(unpaired)} problem(s) lack the plain or the hint condition")
    if n_rows < expected:
        reasons.append(f"rows {n_rows} < expected {expected} (problems x 2 x k)")
    return {
        "incomplete": bool(reasons) or not hint_tally,
        "k": k,
        "n_problems_expected": len(problems),
        "expected_rows": expected,
        "actual_rows": n_rows,
        "reasons": reasons or (["no rows"] if not hint_tally else []),
        "missing_problems": missing_problems,
        "short_groups": short,
        "unpaired_problems": unpaired,
    }


def build_report(hint_rows, b0_rows, resamples=DEFAULT_RESAMPLES, seed=DEFAULT_SEED,
                 planned_problems=None, hint_run="", b0_run="") -> dict:
    hint_tally = tally(hint_rows)
    b0_tally = tally(b0_rows, default_condition="plain")
    status = completeness(hint_tally, planned_problems, len(hint_rows))

    per_problem = {}
    for name in sorted(hint_tally):
        conds = hint_tally[name]
        plain = counts(conds["plain"]) if "plain" in conds else None
        hint = counts(conds["hint"]) if "hint" in conds else None
        entry = {"plain": plain, "hint": hint, "gap": None}
        for part in (plain, hint):
            if part is not None:
                part["pass_at_1"] = part["c"] / part["n"]
        if plain and hint:
            entry["gap"] = float(Fraction(hint["c"], hint["n"]) - Fraction(plain["c"], plain["n"]))
        per_problem[name] = entry

    paired = {n: v for n, v in per_problem.items() if v["gap"] is not None}
    gaps = {n: v["gap"] for n, v in paired.items()}
    plain_all = {n: v["plain"] for n, v in per_problem.items() if v["plain"]}
    hint_all = {n: v["hint"] for n, v in per_problem.items() if v["hint"]}

    def sat(group, kind):
        return sorted(n for n, v in group.items()
                      if v["n"] > 0 and (v["c"] == v["n"] if kind == "ceiling" else v["c"] == 0))

    plain_ceiling, plain_floor = sat(plain_all, "ceiling"), sat(plain_all, "floor")
    nonzero = sorted(n for n, g in gaps.items() if g != 0)
    counts_block = {
        "n_problems_with_rows": len(per_problem),
        "n_paired": len(paired),
        "plain_ceiling": len(plain_ceiling),
        "plain_floor": len(plain_floor),
        "hint_ceiling": len(sat(hint_all, "ceiling")),
        "hint_floor": len(sat(hint_all, "floor")),
        "nonzero_gap": len(nonzero),
        "plain_ceiling_problems": plain_ceiling,
        "plain_floor_problems": plain_floor,
        "nonzero_gap_problems": nonzero,
    }

    pair_tuples = [(v["plain"]["c"], v["plain"]["n"], v["hint"]["c"], v["hint"]["n"])
                   for _, v in sorted(paired.items())]
    point = (sum(gaps.values()) / len(gaps)) if gaps else None
    two_layer = ci_block(two_layer_bootstrap(pair_tuples, resamples, seed), point)
    one_layer = ci_block(problem_only_bootstrap([gaps[n] for n in sorted(gaps)], resamples, seed),
                         point)

    b0_counts = {n: counts(c["plain"]) for n, c in b0_tally.items() if "plain" in c}
    b0_short = sorted(n for n, c in b0_counts.items() if c["n"] < max(
        (x["n"] for x in b0_counts.values()), default=0))
    noise = noise_floor(plain_all, b0_counts, gaps,
                        derived_seeds(hint_rows, "plain"), derived_seeds(b0_rows))

    return {
        "schema_version": SCHEMA_VERSION,
        "hint_run": hint_run,
        "b0_run": b0_run,
        "incomplete": status["incomplete"],
        "completeness": status,
        "bootstrap": {
            "resamples": resamples, "seed": seed, "level": CI_LEVEL,
            "layers": "1: resample problems with replacement; 2: per problem, redraw plain and "
                      "hint successes as Binomial(n, c/n)",
            "two_layer": two_layer,
            "problem_only": one_layer,
        },
        "counts": counts_block,
        "mean_gap": point,
        "per_problem": per_problem,
        "noise_floor": noise,
        "b0": {"n_problems": len(b0_counts), "groups_short_of_max_n": b0_short},
    }


# ------------------------------------------------------------------------ CLI

def default_out(hint_run: Path) -> Path:
    return repo_root() / "runs" / "analysis" / f"hint_gap_report_{hint_run.resolve().name}.json"


def format_summary(report: dict) -> str:
    c, boot, noise = report["counts"], report["bootstrap"]["two_layer"], report["noise_floor"]
    lines = [
        f"hint-run: {report['hint_run']}  incomplete={report['incomplete']}",
        f"problems paired={c['n_paired']}  plain ceiling={c['plain_ceiling']} floor={c['plain_floor']}"
        f"  hint ceiling={c['hint_ceiling']} floor={c['hint_floor']}  nonzero gap={c['nonzero_gap']}",
        f"mean gap={report['mean_gap']}  two-layer 95% CI={boot['ci95']}",
        f"noise floor: n_overlap={noise['n_overlap']} median={noise['median']} p90={noise['p90']}",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hint-run", required=True, type=Path, help="hint-gap run directory")
    parser.add_argument("--b0-run", required=True, type=Path, help="B0 run directory")
    parser.add_argument("--out", type=Path, default=None,
                        help="output JSON (default runs/analysis/hint_gap_report_<hint-run>.json)")
    parser.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)
    if args.resamples < 1:
        parser.error("--resamples must be >= 1")

    try:
        hint_rows = read_results(args.hint_run / "results.jsonl")
        b0_rows = read_results(args.b0_run / "results.jsonl")
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report = build_report(hint_rows, b0_rows, args.resamples, args.seed,
                          read_manifest_problems(args.hint_run),
                          str(args.hint_run), str(args.b0_run))
    out = args.out if args.out is not None else default_out(args.hint_run)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(format_summary(report))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
