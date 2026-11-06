#!/usr/bin/env python3
"""Replay verification for stored run responses without model calls.

Verifies responses against Lean sandbox and judge v2, and compares results against
results.jsonl and summary.json.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from mathesis import llm_baseline, runlog
from mathesis.llm_baseline import (
    DEFAULT_VERIFY_WORKERS,
    JUDGE_VERSION,
    _check_verify_workers,
    default_lean_dir,
    default_repo_root,
    extract_proof,
    load_b0_problems,
    verify_proof,
)


def _err(msg: str) -> None:
    print(f"replay_verify error: {msg}", file=sys.stderr)


def _warn(msg: str) -> None:
    print(f"replay_verify warning: {msg}", file=sys.stderr)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Replay verification of recorded responses against Lean sandbox and judge v2."
    )
    parser.add_argument(
        "run_dir",
        help="Path to run directory containing results.jsonl, manifest.json, summary.json, and responses/",
    )
    parser.add_argument(
        "--benchmark",
        default="benchmark/lean_hard",
        help="Benchmark directory containing problems.json (default: benchmark/lean_hard)",
    )
    parser.add_argument(
        "--verify-workers",
        type=int,
        default=DEFAULT_VERIFY_WORKERS,
        help=f"Number of parallel verification workers (default: {DEFAULT_VERIFY_WORKERS})",
    )
    parser.add_argument(
        "--problems",
        default=None,
        help="Comma-separated problem names to verify",
    )
    parser.add_argument(
        "--limit-samples",
        type=int,
        default=None,
        help="Limit total samples to verify",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output JSON report to FILE or DIR (writes replay_report.json if DIR)",
    )
    parser.add_argument(
        "--table",
        action="store_true",
        help="Print text summary table to stdout",
    )
    return parser.parse_args(argv)


def _format_table(
    run_dir: Path,
    warnings: list[str],
    total_samples: int,
    consistent_count: int,
    discrepancies: list[dict],
    per_problem_comp: dict,
    is_hint_gap: bool,
) -> str:
    lines = []
    lines.append("=" * 82)
    lines.append(f"Replay Verification Report: {run_dir}")
    lines.append("=" * 82)

    if warnings:
        lines.append("Environment Warnings:")
        for w in warnings:
            lines.append(f"  * {w}")
        lines.append("-" * 82)

    match_pct = (consistent_count / total_samples * 100.0) if total_samples > 0 else 0.0
    lines.append(f"Samples Replayed : {total_samples}")
    lines.append(f"Consistent       : {consistent_count} ({match_pct:.1f}%)")
    lines.append(f"Inconsistent     : {len(discrepancies)}")
    lines.append("-" * 82)

    if is_hint_gap:
        lines.append(f"{'Problem':<35} | {'Cond':<5} | {'Replayed c/n':<12} | {'Stored c/n':<12} | {'Diff c':<6}")
        lines.append("-" * 82)
        for prob_name, conds in sorted(per_problem_comp.items()):
            for cond, data in sorted(conds.items()):
                rep = f"{data['replayed']['c']}/{data['replayed']['n']}"
                st_c = data['stored']['c']
                st_n = data['stored']['n']
                st = f"{st_c}/{st_n}" if st_c is not None and st_n is not None else "N/A"
                diff = f"{data['diff_c']:+d}" if data['diff_c'] is not None else "-"
                lines.append(f"{prob_name:<35} | {cond:<5} | {rep:<12} | {st:<12} | {diff:<6}")
    else:
        lines.append(f"{'Problem':<40} | {'Replayed c/n':<14} | {'Stored c/n':<14} | {'Diff c':<6}")
        lines.append("-" * 82)
        for prob_name, data in sorted(per_problem_comp.items()):
            rep = f"{data['replayed']['c']}/{data['replayed']['n']}"
            st_c = data['stored']['c']
            st_n = data['stored']['n']
            st = f"{st_c}/{st_n}" if st_c is not None and st_n is not None else "N/A"
            diff = f"{data['diff_c']:+d}" if data['diff_c'] is not None else "-"
            lines.append(f"{prob_name:<40} | {rep:<14} | {st:<14} | {diff:<6}")

    if discrepancies:
        lines.append("-" * 82)
        lines.append(f"Discrepancies ({len(discrepancies)}):")
        for d in discrepancies:
            cond_str = f" [{d['condition']}]" if d['condition'] else ""
            orig = f"passed={d['original']['passed']} ({d['original']['failure_class']})"
            rep = f"passed={d['replayed']['passed']} ({d['replayed']['failure_class']})"
            lines.append(f"  * {d['problem']}{cond_str} #{d['sample_index']}:")
            lines.append(f"      Original: {orig}")
            lines.append(f"      Replayed: {rep}")
            if d['replayed']['first_error_line']:
                lines.append(f"      Error   : {d['replayed']['first_error_line']}")

    lines.append("=" * 82)
    status_str = "ALL CONSISTENT (SUCCESS)" if len(discrepancies) == 0 else "INCONSISTENCY DETECTED (FAILURE)"
    lines.append(f"Outcome: {status_str}")
    lines.append("=" * 82)
    return "\n".join(lines)


def replay_verify(
    run_dir: str | Path,
    benchmark_dir: str | Path = "benchmark/lean_hard",
    verify_workers: int = DEFAULT_VERIFY_WORKERS,
    problems: str | list[str] | None = None,
    limit_samples: int | None = None,
) -> tuple[int, dict]:
    """Execute replay verification. Returns (exit_code, report_dict)."""
    run_path = Path(run_dir)
    if not run_path.is_dir():
        _err(f"run directory does not exist or is not a directory: {run_path}")
        return 2, {}

    manifest_file = run_path / "manifest.json"
    if not manifest_file.is_file():
        _err(f"manifest.json missing in {run_path}")
        return 2, {}

    results_file = run_path / "results.jsonl"
    if not results_file.is_file():
        _err(f"results.jsonl missing in {run_path}")
        return 2, {}

    summary_file = run_path / "summary.json"
    if not summary_file.is_file():
        _err(f"summary.json missing in {run_path}")
        return 2, {}

    responses_dir = run_path / "responses"
    if not responses_dir.is_dir():
        _err(f"responses directory missing in {run_path}")
        return 2, {}

    try:
        workers = _check_verify_workers(verify_workers)
    except (ValueError, TypeError) as exc:
        _err(str(exc))
        return 2, {}

    if limit_samples is not None and limit_samples < 1:
        _err("--limit-samples must be >= 1")
        return 2, {}

    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except Exception as exc:
        _err(f"cannot read manifest.json: {exc}")
        return 2, {}

    manifest_jv = manifest.get("judge_version")
    if manifest_jv is not None and manifest_jv != JUDGE_VERSION:
        _err(f"manifest judge_version '{manifest_jv}' != current JUDGE_VERSION '{JUDGE_VERSION}'")
        return 2, {}

    manifest_args = manifest.get("args")
    if isinstance(manifest_args, dict) and "hints_file" in manifest_args:
        hints_path_str = manifest_args.get("hints_file")
        expected_sha = manifest_args.get("hints_file_sha256")
        hints_path = Path(hints_path_str) if hints_path_str else None
        if hints_path and not hints_path.is_file():
            candidate = Path(benchmark_dir) / "hints" / hints_path.name
            if candidate.is_file():
                hints_path = candidate
            else:
                candidate = default_repo_root() / hints_path_str
                if candidate.is_file():
                    hints_path = candidate
        if hints_path is None or not hints_path.is_file():
            _err(f"hints_file recorded in manifest not found: {hints_path_str}")
            return 2, {}
        if expected_sha:
            actual_sha = hashlib.sha256(hints_path.read_bytes()).hexdigest()
            if actual_sha != expected_sha:
                _err(f"hints_file sha256 mismatch: actual={actual_sha} vs expected={expected_sha}")
                return 2, {}

    repo_dir = default_repo_root()
    current_toolchain = runlog.lean_toolchain(repo_dir)
    current_mathlib = runlog.mathlib_rev(repo_dir)
    recorded_toolchain = manifest.get("lean_toolchain")
    recorded_mathlib = manifest.get("mathlib_rev")

    warnings = []
    if recorded_toolchain and current_toolchain != recorded_toolchain:
        w = (
            f"Lean toolchain mismatch: current '{current_toolchain}' vs recorded '{recorded_toolchain}'. "
            f"Results may vary across toolchain versions."
        )
        warnings.append(w)
        _warn(w)
    if recorded_mathlib and current_mathlib != recorded_mathlib:
        w = (
            f"Mathlib revision mismatch: current '{current_mathlib}' vs recorded '{recorded_mathlib}'. "
            f"Results may vary across mathlib revisions."
        )
        warnings.append(w)
        _warn(w)

    benchmark_path = Path(benchmark_dir)
    if not (benchmark_path / "problems.json").is_file():
        _err(f"benchmark problems.json missing at {benchmark_path / 'problems.json'}")
        return 2, {}
    try:
        problems_list = load_b0_problems(benchmark_dir=benchmark_path)
        problems_by_name = {p["name"]: p for p in problems_list}
    except Exception as exc:
        _err(f"failed to load benchmark problems: {exc}")
        return 2, {}

    requested_names = None
    if problems:
        if isinstance(problems, str):
            requested_names = [n.strip() for n in problems.split(",") if n.strip()]
        else:
            requested_names = [str(n).strip() for n in problems if str(n).strip()]
        if not requested_names:
            _err("--problems list cannot be empty")
            return 2, {}
        unknown = [n for n in requested_names if n not in problems_by_name]
        if unknown:
            _err(f"unknown problem(s) in --problems: {', '.join(unknown)}")
            return 2, {}

    results_rows = []
    with open(results_file, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception as exc:
                _err(f"invalid JSON on line {line_no} in results.jsonl: {exc}")
                return 2, {}
            row_jv = row.get("judge_version")
            if row_jv is not None and row_jv != JUDGE_VERSION:
                _err(f"results.jsonl line {line_no} judge_version '{row_jv}' != current '{JUDGE_VERSION}'")
                return 2, {}
            results_rows.append(row)

    if not results_rows:
        _err("results.jsonl contains no sample rows")
        return 2, {}

    if requested_names is not None:
        requested_set = set(requested_names)
        results_rows = [r for r in results_rows if r.get("problem") in requested_set]
        found_names = {r.get("problem") for r in results_rows}
        missing_names = [n for n in requested_names if n not in found_names]
        if missing_names:
            _err(f"problem(s) not found in results.jsonl: {', '.join(missing_names)}")
            return 2, {}

    if limit_samples is not None:
        results_rows = results_rows[:limit_samples]

    if not results_rows:
        _err("no sample rows selected for replay")
        return 2, {}

    sample_tasks = []
    for row in results_rows:
        prob_name = row["problem"]
        condition = row.get("condition")
        sample_idx = row["sample_index"]
        tag = prob_name + ("__" + condition if condition else "")
        resp_file = responses_dir / f"{tag}_{sample_idx}.txt"
        if not resp_file.is_file():
            _err(f"missing response file: {resp_file}")
            return 2, {}
        sample_tasks.append((row, prob_name, condition, sample_idx, tag, resp_file))

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_candidates = Path(tmp_dir) / "candidates"
        tmp_candidates.mkdir(parents=True, exist_ok=True)

        def verify_one(task):
            row, prob_name, condition, sample_idx, tag, resp_file = task
            prob = problems_by_name[prob_name]
            resp_text = resp_file.read_text(encoding="utf-8")
            proof, reason = extract_proof(resp_text, prob["header"])
            if proof is None:
                return {
                    "passed": False,
                    "failure_class": reason,
                    "first_error_line": reason,
                    "lean_returncode": None,
                }
            cand_path = tmp_candidates / f"{tag}_{sample_idx}.lean"
            ver = llm_baseline.verify_proof(
                prob["header"],
                proof,
                prob["footer"],
                cand_path,
                lean_dir=default_lean_dir(),
            )
            return {
                "passed": ver.passed,
                "failure_class": ver.failure_class,
                "first_error_line": ver.first_error_line,
                "lean_returncode": ver.lean_returncode,
            }

        with ThreadPoolExecutor(max_workers=workers) as executor:
            replayed_results = list(executor.map(verify_one, sample_tasks))

    discrepancies = []
    consistent_count = 0
    per_problem_replayed = defaultdict(lambda: {"c": 0, "n": 0})
    per_problem_condition_replayed = defaultdict(lambda: defaultdict(lambda: {"c": 0, "n": 0}))

    for task, res in zip(sample_tasks, replayed_results):
        row, prob_name, condition, sample_idx, tag, _ = task
        old_passed = bool(row["passed"])
        old_failure = str(row["failure_class"])
        new_passed = bool(res["passed"])
        new_failure = str(res["failure_class"])

        is_match = (old_passed == new_passed) and (old_failure == new_failure)
        if is_match:
            consistent_count += 1
        else:
            discrepancies.append({
                "problem": prob_name,
                "condition": condition,
                "sample_index": sample_idx,
                "original": {
                    "passed": old_passed,
                    "failure_class": old_failure,
                    "first_error_line": row.get("first_error_line", ""),
                },
                "replayed": {
                    "passed": new_passed,
                    "failure_class": new_failure,
                    "first_error_line": res["first_error_line"],
                },
            })

        if condition is not None:
            per_problem_condition_replayed[prob_name][condition]["n"] += 1
            if new_passed:
                per_problem_condition_replayed[prob_name][condition]["c"] += 1
        else:
            per_problem_replayed[prob_name]["n"] += 1
            if new_passed:
                per_problem_replayed[prob_name]["c"] += 1

    try:
        stored_summary = json.loads(summary_file.read_text(encoding="utf-8"))
        stored_per_problem = stored_summary.get("summary", {}).get("per_problem", {})
    except Exception:
        stored_per_problem = {}

    per_problem_comp = {}
    is_hint_gap = len(per_problem_condition_replayed) > 0

    if is_hint_gap:
        for prob_name, conds in sorted(per_problem_condition_replayed.items()):
            stored_prob = stored_per_problem.get(prob_name, {})
            per_problem_comp[prob_name] = {}
            for cond, stats in sorted(conds.items()):
                stored_cond = stored_prob.get(cond, {})
                sc = stored_cond.get("c")
                sn = stored_cond.get("n")
                per_problem_comp[prob_name][cond] = {
                    "replayed": stats,
                    "stored": {"c": sc, "n": sn},
                    "diff_c": (stats["c"] - sc) if sc is not None and stats["n"] == sn else None,
                }
    else:
        for prob_name, stats in sorted(per_problem_replayed.items()):
            stored_prob = stored_per_problem.get(prob_name, {})
            sc = stored_prob.get("c")
            sn = stored_prob.get("n")
            per_problem_comp[prob_name] = {
                "replayed": stats,
                "stored": {"c": sc, "n": sn},
                "diff_c": (stats["c"] - sc) if sc is not None and stats["n"] == sn else None,
            }

    report = {
        "run_dir": str(run_path.resolve()),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "judge_version": JUDGE_VERSION,
        "environment": {
            "current_lean_toolchain": current_toolchain,
            "current_mathlib_rev": current_mathlib,
            "recorded_lean_toolchain": recorded_toolchain,
            "recorded_mathlib_rev": recorded_mathlib,
            "warnings": warnings,
        },
        "summary": {
            "total_samples": len(results_rows),
            "consistent_samples": consistent_count,
            "inconsistent_samples": len(discrepancies),
            "all_consistent": len(discrepancies) == 0,
        },
        "discrepancies": discrepancies,
        "per_problem": per_problem_comp,
    }

    exit_code = 0 if len(discrepancies) == 0 else 1
    return exit_code, report


def main(argv=None) -> int:
    args = parse_args(argv)
    exit_code, report = replay_verify(
        run_dir=args.run_dir,
        benchmark_dir=args.benchmark,
        verify_workers=args.verify_workers,
        problems=args.problems,
        limit_samples=args.limit_samples,
    )

    if exit_code == 2:
        return 2

    is_hint_gap = False
    if report.get("per_problem"):
        first_val = next(iter(report["per_problem"].values()))
        if isinstance(first_val, dict) and ("plain" in first_val or "hint" in first_val):
            is_hint_gap = True

    table_text = _format_table(
        run_dir=Path(args.run_dir),
        warnings=report.get("environment", {}).get("warnings", []),
        total_samples=report.get("summary", {}).get("total_samples", 0),
        consistent_count=report.get("summary", {}).get("consistent_samples", 0),
        discrepancies=report.get("discrepancies", []),
        per_problem_comp=report.get("per_problem", {}),
        is_hint_gap=is_hint_gap,
    )

    if args.out:
        out_path = Path(args.out)
        if out_path.is_dir() or str(args.out).endswith(os.sep) or str(args.out).endswith("/"):
            out_file = out_path / "replay_report.json"
        else:
            out_file = out_path
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.table:
        print(table_text)
    elif not args.out:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
