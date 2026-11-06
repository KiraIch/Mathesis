"""Read-only statistics report for B0 (no-hint baseline) runs across multiple seeds.

Compares seed runs, computes per-seed metrics (overall pass@1, pass@k, bootstrap CI),
stratification by insight/routine and by family, cross-seed noise floor (|Δpass@1|
distribution, median, p90, max, seed1-seed0 mean diff and CI), and combined saturation
classification (ceiling, middle, floor).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_RESAMPLES = 10000
DEFAULT_BOOTSTRAP_SEED = 0
CI_LEVEL = 0.95


class B0ReportError(Exception):
    """Raised for input validation errors."""


def quantile(sorted_values: list[float], q: float) -> float | None:
    """Linear-interpolation quantile (numpy default) of an already sorted list."""
    if not sorted_values:
        return None
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def percentile_interval(values: list[float], level: float = CI_LEVEL) -> list[float] | None:
    """Percentile interval [alpha, 1-alpha] of a sorted list."""
    if not values:
        return None
    total = len(values)
    alpha = (1.0 - level) / 2.0
    low = values[int(alpha * (total - 1))]
    high = values[int((1.0 - alpha) * (total - 1))]
    return [low, high]


def bootstrap_mean_ci(
    values: list[float],
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
    level: float = CI_LEVEL,
) -> list[float] | None:
    """Bootstrap 95% CI of the mean by resampling values with replacement."""
    if not values:
        return None
    if resamples < 1:
        raise ValueError("resamples must be >= 1")
    rng = random.Random(seed)
    total = len(values)
    means = [
        sum(values[rng.randrange(total)] for _ in range(total)) / total
        for _ in range(resamples)
    ]
    means.sort()
    return percentile_interval(means, level=level)


def load_benchmark_problems(benchmark_arg: Path) -> dict[str, dict[str, Any]]:
    """Load problems from problems.json in a benchmark directory or path."""
    path = benchmark_arg
    if path.is_dir():
        path = path / "problems.json"
    if not path.is_file():
        raise B0ReportError(f"benchmark problems file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise B0ReportError(f"cannot read benchmark file {path}: {exc}") from exc

    if not isinstance(data, dict) or "problems" not in data:
        raise B0ReportError(f"{path}: expected JSON object with 'problems' list")

    problems = data["problems"]
    if not isinstance(problems, list):
        raise B0ReportError(f"{path}: 'problems' must be a list")

    out: dict[str, dict[str, Any]] = {}
    for p in problems:
        if not isinstance(p, dict) or "name" not in p:
            raise B0ReportError(f"{path}: problem entry missing 'name'")
        out[p["name"]] = p
    return out


def parse_seed_runs_arg(seed_runs_args: list[str]) -> dict[str, list[Path]]:
    """Parse repeatable --seed-runs arguments of form '<seed>:<dir1>,<dir2>...'."""
    out: dict[str, list[Path]] = {}
    for arg in seed_runs_args:
        if ":" not in arg:
            raise B0ReportError(
                f"invalid --seed-runs format: {arg!r} (expected <seed>:<dir1>,<dir2>...)"
            )
        seed_str, dirs_str = arg.split(":", 1)
        seed_str = seed_str.strip()
        if not seed_str:
            raise B0ReportError(f"invalid --seed-runs format: missing seed in {arg!r}")
        dirs = [Path(d.strip()) for d in dirs_str.split(",") if d.strip()]
        if not dirs:
            raise B0ReportError(f"invalid --seed-runs format: no directories specified in {arg!r}")
        out.setdefault(seed_str, []).extend(dirs)
    return out


def load_run_summary(
    run_dir: Path, expected_k: int | None = None
) -> tuple[dict[str, dict[str, Any]], int]:
    """Load and validate summary.json from a single run directory."""
    if not run_dir.is_dir():
        raise B0ReportError(f"{run_dir}: not a directory")

    summary_file = run_dir / "summary.json"
    if not summary_file.is_file():
        raise B0ReportError(f"{run_dir}: missing summary.json")

    try:
        data = json.loads(summary_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise B0ReportError(f"{summary_file}: invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise B0ReportError(f"{summary_file}: root JSON must be an object")

    if data.get("status") != "ok":
        status_val = data.get("status")
        err_msg = data.get("error", "")
        detail = f" (error: {err_msg})" if err_msg else ""
        raise B0ReportError(f"{run_dir}: status is not ok (status={status_val!r}){detail}")

    summary_block = data.get("summary")
    if isinstance(summary_block, dict) and "per_problem" in summary_block:
        per_problem = summary_block["per_problem"]
        k = summary_block.get("k")
    elif "per_problem" in data and isinstance(data["per_problem"], dict):
        per_problem = data["per_problem"]
        k = data.get("k")
    else:
        raise B0ReportError(f"{summary_file}: missing 'per_problem' dictionary")

    if not isinstance(per_problem, dict):
        raise B0ReportError(f"{summary_file}: 'per_problem' must be a dictionary")

    # Determine / validate k
    if k is not None:
        try:
            k = int(k)
        except ValueError:
            raise B0ReportError(f"{summary_file}: invalid k={k!r}")

    if expected_k is not None:
        if k is not None and k != expected_k:
            raise B0ReportError(
                f"{run_dir}: run k={k} does not match expected k={expected_k}"
            )
        run_k = expected_k
    else:
        if k is None:
            # Fall back to first problem's n if k is not explicitly in summary
            first_n = next((v.get("n") for v in per_problem.values() if isinstance(v, dict)), None)
            if first_n is None:
                raise B0ReportError(f"{summary_file}: cannot determine k")
            run_k = int(first_n)
        else:
            run_k = k

    # Validate each problem's n and c
    for name, pdata in per_problem.items():
        if not isinstance(pdata, dict):
            raise B0ReportError(f"{summary_file}: problem '{name}' entry must be an object")
        n = pdata.get("n")
        c = pdata.get("c")
        if n != run_k:
            raise B0ReportError(
                f"{run_dir}: problem '{name}' has n={n}, expected {run_k}"
            )
        if not isinstance(c, int) or c < 0 or c > n:
            raise B0ReportError(f"{summary_file}: problem '{name}' has invalid c={c}")

    return per_problem, run_k


def load_seed_problems(
    dirs: list[Path], seed_id: str, expected_k: int | None = None
) -> tuple[dict[str, dict[str, Any]], int]:
    """Load problems for a single seed across its constituent run directories."""
    collected: dict[str, dict[str, Any]] = {}
    sources: dict[str, Path] = {}
    current_k = expected_k

    for rdir in dirs:
        pp, r_k = load_run_summary(rdir, expected_k=current_k)
        if current_k is None:
            current_k = r_k
        for name, pdata in pp.items():
            if name in sources:
                raise B0ReportError(
                    f"seed {seed_id}: duplicate problem '{name}' found in {rdir} "
                    f"(already present in {sources[name]})"
                )
            sources[name] = rdir
            collected[name] = pdata

    assert current_k is not None
    return collected, current_k


def validate_across_seeds(
    seeds_data: dict[str, dict[str, dict[str, Any]]],
    bench_problems: dict[str, dict[str, Any]],
    benchmark_path: Path,
) -> None:
    """Validate problems exist in benchmark and that seed problem sets match."""
    valid_names = set(bench_problems.keys())

    # Check problems belong to problems.json
    for seed_id, probs in seeds_data.items():
        for name in probs:
            if name not in valid_names:
                raise B0ReportError(
                    f"problem '{name}' in seed {seed_id} not found in {benchmark_path}"
                )

    # Check exactly 2 seeds
    if len(seeds_data) != 2:
        raise B0ReportError(
            f"expected exactly 2 seeds (e.g. 0 and 1), found {len(seeds_data)}: {list(seeds_data.keys())}"
        )

    # Check identical problem sets across seeds
    seed_keys = sorted(seeds_data.keys())
    s0, s1 = seed_keys[0], seed_keys[1]
    set0 = set(seeds_data[s0].keys())
    set1 = set(seeds_data[s1].keys())
    if set0 != set1:
        only_0 = sorted(set0 - set1)
        only_1 = sorted(set1 - set0)
        raise B0ReportError(
            f"problem sets differ between seed {s0} and seed {s1} "
            f"(only in seed {s0}: {only_0}, only in seed {s1}: {only_1})"
        )


def compute_seed_metrics(
    probs: dict[str, dict[str, Any]],
    active_names: set[str],
    resamples: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    """Compute overall pass@1, pass@k, and CI for active and all problem subsets."""
    out = {}
    for subset_name, is_active_only in [("active", True), ("all", False)]:
        names = [n for n in sorted(probs.keys()) if (not is_active_only or n in active_names)]
        if not names:
            out[subset_name] = {
                "n_problems": 0,
                "mean_pass_at_1": None,
                "mean_pass_at_k": None,
                "ci95_pass_at_1": None,
            }
            continue
        p1_values = [probs[n]["pass_at_1"] for n in names]
        pk_values = [probs[n]["pass_at_k"] for n in names]
        mean_p1 = sum(p1_values) / len(p1_values)
        mean_pk = sum(pk_values) / len(pk_values)
        ci95 = bootstrap_mean_ci(p1_values, resamples=resamples, seed=bootstrap_seed)
        out[subset_name] = {
            "n_problems": len(names),
            "mean_pass_at_1": mean_p1,
            "mean_pass_at_k": mean_pk,
            "ci95_pass_at_1": ci95,
        }
    return out


def compute_stratification(
    seeds_data: dict[str, dict[str, dict[str, Any]]],
    active_names: set[str],
    bench_problems: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compute mean pass@1 per seed broken down by insight/routine and by family."""
    seed_keys = sorted(seeds_data.keys())

    # By insight / routine
    by_insight: dict[str, Any] = {}
    for kind_label, kind_bool in [("insight", True), ("routine", False)]:
        sub_names = [
            n for n in active_names
            if bool(bench_problems[n].get("insight")) == kind_bool
        ]
        sub_names.sort()
        means = {}
        for s in seed_keys:
            if sub_names:
                means[s] = sum(seeds_data[s][n]["pass_at_1"] for n in sub_names) / len(sub_names)
            else:
                means[s] = None
        by_insight[kind_label] = {
            "n_problems": len(sub_names),
            "mean_pass_at_1": means,
        }

    # By family
    families = sorted(set(bench_problems[n].get("family", "unknown") for n in active_names))
    by_family: dict[str, Any] = {}
    for fam in families:
        sub_names = [
            n for n in active_names
            if bench_problems[n].get("family") == fam
        ]
        sub_names.sort()
        means = {}
        for s in seed_keys:
            if sub_names:
                means[s] = sum(seeds_data[s][n]["pass_at_1"] for n in sub_names) / len(sub_names)
            else:
                means[s] = None
        by_family[fam] = {
            "n_problems": len(sub_names),
            "mean_pass_at_1": means,
        }

    return {
        "by_insight": by_insight,
        "by_family": by_family,
    }


def compute_noise_floor(
    s0_data: dict[str, dict[str, Any]],
    s1_data: dict[str, dict[str, Any]],
    names: list[str],
    resamples: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    """Compute cross-seed |Δpass@1| distribution, quantiles, and signed mean diff with CI."""
    if not names:
        return {
            "n_problems": 0,
            "counts": {"0.0": 0, "0.125": 0, "0.25": 0, ">0.25": 0},
            "median": None,
            "p90": None,
            "max": None,
            "mean_diff": None,
            "ci95_diff": None,
        }

    signed_diffs = [s1_data[n]["pass_at_1"] - s0_data[n]["pass_at_1"] for n in names]
    abs_diffs = sorted(abs(d) for d in signed_diffs)

    c_0 = sum(1 for d in abs_diffs if abs(d - 0.0) < 1e-9)
    c_125 = sum(1 for d in abs_diffs if abs(d - 0.125) < 1e-9)
    c_25 = sum(1 for d in abs_diffs if abs(d - 0.25) < 1e-9)
    c_gt = sum(1 for d in abs_diffs if d > 0.25 + 1e-9)

    mean_diff = sum(signed_diffs) / len(signed_diffs)
    ci95 = bootstrap_mean_ci(signed_diffs, resamples=resamples, seed=bootstrap_seed)

    return {
        "n_problems": len(names),
        "counts": {
            "0.0": c_0,
            "0.125": c_125,
            "0.25": c_25,
            ">0.25": c_gt,
        },
        "median": quantile(abs_diffs, 0.5),
        "p90": quantile(abs_diffs, 0.9),
        "max": abs_diffs[-1] if abs_diffs else None,
        "mean_diff": mean_diff,
        "ci95_diff": ci95,
    }


def compute_saturation(
    s0_data: dict[str, dict[str, Any]],
    s1_data: dict[str, dict[str, Any]],
    active_names: set[str],
    bench_problems: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compute combined-seed saturation counts (ceiling, middle, floor) for active problems."""
    cats = {"insight": {"ceiling": 0, "middle": 0, "floor": 0, "n_problems": 0},
            "routine": {"ceiling": 0, "middle": 0, "floor": 0, "n_problems": 0},
            "total": {"ceiling": 0, "middle": 0, "floor": 0, "n_problems": 0}}

    for name in active_names:
        c = s0_data[name]["c"] + s1_data[name]["c"]
        n = s0_data[name]["n"] + s1_data[name]["n"]
        if c == n:
            bucket = "ceiling"
        elif c == 0:
            bucket = "floor"
        else:
            bucket = "middle"

        kind = "insight" if bench_problems[name].get("insight") else "routine"
        cats[kind][bucket] += 1
        cats[kind]["n_problems"] += 1
        cats["total"][bucket] += 1
        cats["total"]["n_problems"] += 1

    return cats


def build_b0_report(
    seeds_data: dict[str, dict[str, dict[str, Any]]],
    bench_problems: dict[str, dict[str, Any]],
    benchmark_path: str,
    resamples: int = DEFAULT_RESAMPLES,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Build complete structured report dictionary."""
    seed_keys = sorted(seeds_data.keys())
    s0, s1 = seed_keys[0], seed_keys[1]

    # Active problems: problems in benchmark that are in the run and not retired
    run_problem_names = set(seeds_data[s0].keys())
    active_names = {
        n for n in run_problem_names
        if not bench_problems[n].get("retired")
    }
    all_names = sorted(run_problem_names)
    sorted_active_names = sorted(active_names)

    # 1. Per-seed metrics
    seeds_block = {}
    for s in seed_keys:
        seeds_block[s] = compute_seed_metrics(
            seeds_data[s], active_names, resamples=resamples, bootstrap_seed=bootstrap_seed
        )

    # 2. Stratification
    stratification = compute_stratification(seeds_data, active_names, bench_problems)

    # 3. Noise floor
    noise_floor = {
        "active": compute_noise_floor(
            seeds_data[s0], seeds_data[s1], sorted_active_names,
            resamples=resamples, bootstrap_seed=bootstrap_seed
        ),
        "all": compute_noise_floor(
            seeds_data[s0], seeds_data[s1], all_names,
            resamples=resamples, bootstrap_seed=bootstrap_seed
        ),
    }

    # 4. Saturation
    saturation = compute_saturation(seeds_data[s0], seeds_data[s1], active_names, bench_problems)

    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark": benchmark_path,
        "seeds_compared": [s0, s1],
        "bootstrap": {
            "resamples": resamples,
            "seed": bootstrap_seed,
            "level": CI_LEVEL,
        },
        "seeds": seeds_block,
        "stratification": stratification,
        "noise_floor": noise_floor,
        "saturation": saturation,
    }


def format_table(report: dict[str, Any]) -> str:
    """Format report into human-readable text tables."""
    s0, s1 = report["seeds_compared"]
    b_info = report["bootstrap"]
    lines = [
        "=" * 85,
        f"B0 Baseline Report (benchmark: {report['benchmark']}, bootstrap_seed={b_info['seed']}, resamples={b_info['resamples']})",
        "=" * 85,
        "",
        "1. Overall Seed Performance",
        "-" * 85,
        f"{'Group':7s} | {'Seed':4s} | {'Problems':8s} | {'mean pass@1':12s} | {'mean pass@k':12s} | {'95% Bootstrap CI (pass@1)':25s}",
        "-" * 85,
    ]

    for group in ["active", "all"]:
        for s in [s0, s1]:
            d = report["seeds"][s][group]
            p1_str = f"{d['mean_pass_at_1']:.4f}" if d["mean_pass_at_1"] is not None else "-"
            pk_str = f"{d['mean_pass_at_k']:.4f}" if d["mean_pass_at_k"] is not None else "-"
            ci = d["ci95_pass_at_1"]
            ci_str = f"[{ci[0]:.4f}, {ci[1]:.4f}]" if ci else "-"
            lines.append(
                f"{group:7s} | {s:4s} | {d['n_problems']:8d} | {p1_str:12s} | {pk_str:12s} | {ci_str:25s}"
            )

    lines.extend([
        "",
        f"2. Stratification (Active Problems, N={report['seeds'][s0]['active']['n_problems']})",
        "-" * 85,
        f"{'Category':12s} | {'Subset':10s} | {'Problems':8s} | {f'Seed {s0} pass@1':13s} | {f'Seed {s1} pass@1':13s} | {f'Diff ({s1}-{s0})':14s}",
        "-" * 85,
    ])

    for k, v in report["stratification"]["by_insight"].items():
        m0 = v["mean_pass_at_1"].get(s0)
        m1 = v["mean_pass_at_1"].get(s1)
        m0_str = f"{m0:.4f}" if m0 is not None else "-"
        m1_str = f"{m1:.4f}" if m1 is not None else "-"
        diff_str = f"{(m1 - m0):+.4f}" if (m0 is not None and m1 is not None) else "-"
        lines.append(
            f"{'insight':12s} | {k:10s} | {v['n_problems']:8d} | {m0_str:13s} | {m1_str:13s} | {diff_str:14s}"
        )

    for fam, v in report["stratification"]["by_family"].items():
        m0 = v["mean_pass_at_1"].get(s0)
        m1 = v["mean_pass_at_1"].get(s1)
        m0_str = f"{m0:.4f}" if m0 is not None else "-"
        m1_str = f"{m1:.4f}" if m1 is not None else "-"
        diff_str = f"{(m1 - m0):+.4f}" if (m0 is not None and m1 is not None) else "-"
        lines.append(
            f"{'family':12s} | {fam:10s} | {v['n_problems']:8d} | {m0_str:13s} | {m1_str:13s} | {diff_str:14s}"
        )

    lines.extend([
        "",
        f"3. Seed Noise Floor (Seed {s1} vs Seed {s0})",
        "-" * 105,
        f"{'Group':7s} | {'N':5s} | {'|Δ|=0':6s} | {'|Δ|=0.125':9s} | {'|Δ|=0.25':8s} | {'|Δ|>0.25':8s} | {'median':6s} | {'p90':6s} | {'max':6s} | {'mean diff':10s} | {'95% CI (diff)':23s}",
        "-" * 105,
    ])

    for group in ["active", "all"]:
        nf = report["noise_floor"][group]
        c = nf["counts"]
        ci = nf["ci95_diff"]
        ci_str = f"[{ci[0]:.4f}, {ci[1]:.4f}]" if ci else "-"
        md_str = f"{nf['mean_diff']:+.4f}" if nf["mean_diff"] is not None else "-"
        med_str = f"{nf['median']:.4f}" if nf["median"] is not None else "-"
        p90_str = f"{nf['p90']:.4f}" if nf["p90"] is not None else "-"
        max_str = f"{nf['max']:.4f}" if nf["max"] is not None else "-"
        lines.append(
            f"{group:7s} | {nf['n_problems']:5d} | {c['0.0']:6d} | {c['0.125']:9d} | {c['0.25']:8d} | {c['>0.25']:8d} | {med_str:6s} | {p90_str:6s} | {max_str:6s} | {md_str:10s} | {ci_str:23s}"
        )

    lines.extend([
        "",
        f"4. Combined Seed Saturation (Active Problems, N={report['saturation']['total']['n_problems']}, k=16)",
        "-" * 85,
        f"{'Type':8s} | {'Problems':8s} | {'Ceiling (c=16)':18s} | {'Middle (0<c<16)':18s} | {'Floor (c=0)':18s}",
        "-" * 85,
    ])

    for row_key in ["insight", "routine", "total"]:
        sat = report["saturation"][row_key]
        n_p = sat["n_problems"]
        c_pct = (sat["ceiling"] / n_p * 100) if n_p else 0.0
        m_pct = (sat["middle"] / n_p * 100) if n_p else 0.0
        f_pct = (sat["floor"] / n_p * 100) if n_p else 0.0
        ceil_str = f"{sat['ceiling']:4d} ({c_pct:5.1f}%)"
        mid_str = f"{sat['middle']:4d} ({m_pct:5.1f}%)"
        floor_str = f"{sat['floor']:4d} ({f_pct:5.1f}%)"
        lines.append(
            f"{row_key:8s} | {n_p:8d} | {ceil_str:18s} | {mid_str:18s} | {floor_str:18s}"
        )

    lines.append("=" * 85)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Statistics report for B0 (no-hint baseline) across multiple seeds."
    )
    parser.add_argument(
        "--seed-runs",
        action="append",
        required=True,
        help="seed runs in format <seed>:<dir1>,<dir2>...",
    )
    parser.add_argument(
        "--benchmark",
        type=Path,
        required=True,
        help="benchmark directory or problems.json path",
    )
    parser.add_argument(
        "--resamples",
        type=int,
        default=DEFAULT_RESAMPLES,
        help=f"bootstrap resamples (default: {DEFAULT_RESAMPLES})",
    )
    parser.add_argument(
        "--bootstrap-seed",
        type=int,
        default=DEFAULT_BOOTSTRAP_SEED,
        help=f"bootstrap random seed (default: {DEFAULT_BOOTSTRAP_SEED})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output JSON file path (default: stdout)",
    )
    parser.add_argument(
        "--table",
        action="store_true",
        default=False,
        help="print text table",
    )
    args = parser.parse_args(argv)

    if args.resamples < 1:
        print("error: --resamples must be >= 1", file=sys.stderr)
        return 2

    try:
        bench_problems = load_benchmark_problems(args.benchmark)
        seed_runs_map = parse_seed_runs_arg(args.seed_runs)

        expected_k: int | None = None
        seeds_data: dict[str, dict[str, dict[str, Any]]] = {}
        for s_id, dirs in seed_runs_map.items():
            probs, k = load_seed_problems(dirs, s_id, expected_k=expected_k)
            if expected_k is None:
                expected_k = k
            seeds_data[s_id] = probs

        validate_across_seeds(seeds_data, bench_problems, args.benchmark)

        report = build_b0_report(
            seeds_data,
            bench_problems,
            str(args.benchmark),
            resamples=args.resamples,
            bootstrap_seed=args.bootstrap_seed,
        )
    except B0ReportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

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
