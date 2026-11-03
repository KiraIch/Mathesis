import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from mathesis.backend import SubprocessLeanBackend
from mathesis.controller import (
    AlwaysRestructureController,
    FixedScheduleController,
    ImpasseController,
    RandomTriggerController,
)
from mathesis.experiment import (
    PILOT_BUDGET_WALL_MS,
    PILOT_CONFIGS,
    default_problems_path,
    format_per_problem,
    format_summary_table,
    load_problems,
    run_pilot,
    run_single,
)
from mathesis.impasse import ImpasseDetector
from mathesis.lean_bench import (
    FROZEN_IMPASSE_PATIENCE,
    FROZEN_IMPASSE_THRESHOLD,
    LEAN_BENCH_ALL_CONFIGS,
    LEAN_BENCH_DEFAULT_CONFIGS,
    format_lean_bench_rows,
    format_lean_bench_summary,
    run_lean_bench,
    select_lean_bench_problems,
)
from mathesis.pantograph_backend import PantographBackend, default_pantograph_repl
from mathesis.lean_pilot import (
    default_lean_pilot_dir,
    default_lean_pilot_path,
    load_lean_pilot,
)
from mathesis import llm_baseline
from mathesis.runlog import start_run
from mathesis.search import breadth_first_search
from mathesis.types import PilotProblem


def build_demo_problem() -> PilotProblem:
    return PilotProblem(
        name="demo_trans",
        theorem="(P -> Q) -> (Q -> R) -> P -> R",
        family="implication",
        insight=True,
        reference_proof=(
            "intro hPQ",
            "intro hQR",
            "intro hP",
            "have hQ : Q",
            "apply hPQ",
            "exact hP",
            "apply hQR",
            "exact hQ",
        ),
        budget_nodes=100,
    )


def run_smoke() -> int:
    problem = build_demo_problem()
    configs = [
        ("Mathesis", ImpasseController()),
        ("AlwaysRestructure", AlwaysRestructureController()),
        ("FixedSchedule", FixedScheduleController(interval=5)),
        ("RandomTrigger", RandomTriggerController(probability=0.2, seed=0)),
    ]
    full = {}
    for label, controller in configs:
        detector = ImpasseDetector(
            threshold=0.15, patience=1, window=5, budget=10
        )
        outcome = run_single(problem, controller, detector=detector)
        full[label] = {problem.name: outcome}
    print("smoke theorem: " + problem.theorem)
    print("smoke detector is relaxed to exercise the impasse path; not a result.")
    print(format_per_problem([problem], full))
    print(format_summary_table(full))
    return 0


def summarize_for_log(results) -> dict:
    summary = {}
    for config_name, per_problem in results.items():
        total = len(per_problem)
        solved = sum(1 for item in per_problem.values() if item.success)
        summary[config_name] = {
            "solved": solved,
            "total": total,
            "solve_rate": (solved / total) if total else 0.0,
        }
    return summary


def detector_params(detector: ImpasseDetector) -> dict:
    return {
        "threshold": detector.threshold,
        "patience": detector.patience,
        "window": detector.window,
        "stall_weight": detector.stall_weight,
        "duplicate_weight": detector.duplicate_weight,
        "budget_weight": detector.budget_weight,
    }


def open_run(out: str, command: str, args: dict, seed: int):
    """start_run, or None after a one-line stderr error when out is not writable."""
    try:
        return start_run(Path(out), command, args, seed)
    except OSError as exc:
        print(
            "cannot create run directory under " + str(out) + ": " + str(exc),
            file=sys.stderr,
        )
        return None


def run_pilot_command(out: str = "runs", seed: int = 0) -> int:
    path = default_problems_path()
    problems = load_problems(path)
    run = open_run(
        out,
        "pilot",
        {
            "problems_path": str(path),
            "out": str(out),
            "configs": list(PILOT_CONFIGS),
            "detector": detector_params(ImpasseDetector()),
            "budget_wall_ms": PILOT_BUDGET_WALL_MS,
        },
        int(seed),
    )
    if run is None:
        return 1
    with run.guard() as outcome:
        results = run_pilot(path, run=run, seed=int(seed))
        outcome.summary = summarize_for_log(results)
    print("pilot problems: " + str(len(problems)))
    print(format_per_problem(problems, results))
    print(format_summary_table(results))
    print("run dir: " + str(run.path))
    return 0


def format_lean_pilot_table(problems) -> str:
    header = "name | family | insight | novelty | mathlib_match | contamination_risk | source | verified | difficulty | budget | lean_file | auxiliary | audit_notes"
    lines = [header]
    for entry in problems:
        lines.append(
            str(entry["name"])
            + " | "
            + str(entry["family"])
            + " | "
            + str(entry["insight"])
            + " | "
            + str(entry["novelty"])
            + " | "
            + str(entry["mathlib_match"])
            + " | "
            + str(entry["contamination_risk"])
            + " | "
            + str(entry["source"])
            + " | "
            + str(entry["verified"])
            + " | "
            + str(entry["difficulty"])
            + " | "
            + str(entry["budget_nodes"])
            + " | "
            + str(entry["lean_file"])
            + " | "
            + str(entry["auxiliary"])
            + " | "
            + str(entry["audit_notes"])
        )
    return "\n".join(lines)


def run_lean_pilot_command() -> int:
    path = default_lean_pilot_path()
    base_dir = default_lean_pilot_dir()
    problems = load_lean_pilot(path)
    print("lean pilot problems: " + str(len(problems)))
    print(format_lean_pilot_table(problems))
    flagged = [entry for entry in problems if entry["verified"] is True]
    print(
        "metadata verified=true for "
        + str(len(flagged))
        + " of "
        + str(len(problems))
        + " entries"
    )
    lean = shutil.which("lean")
    lake = shutil.which("lake")
    if lean is None or lake is None:
        print("Lean toolchain not found; dataset prepared but unverified")
        return 0
    seen = []
    for entry in problems:
        candidate = str(entry["lean_file"])
        if candidate not in seen:
            seen.append(candidate)
    expected = {}
    for entry in problems:
        key = str(entry["lean_file"])
        if key not in expected:
            expected[key] = entry["verified"] is True
    lean_dir = Path(__file__).resolve().parents[2] / "lean"
    manifest = lean_dir / "lake-manifest.json"
    lakefile = lean_dir / "lakefile.lean"
    project_text = ""
    if manifest.is_file():
        project_text += manifest.read_text(encoding="utf-8")
    if lakefile.is_file():
        project_text += lakefile.read_text(encoding="utf-8")
    project_has_mathlib = "mathlib" in project_text
    mismatches = []
    checked = 0
    skipped = 0
    for rel in seen:
        target = base_dir / rel
        needs_mathlib = "import Mathlib" in target.read_text(encoding="utf-8")
        if needs_mathlib and not project_has_mathlib:
            print(rel + " | skip | needs Mathlib project")
            skipped += 1
            continue
        try:
            completed = subprocess.run(
                ["lake", "env", "lean", str(target)],
                cwd=str(lean_dir),
                capture_output=True,
                text=True,
                timeout=120,
            )
        except Exception as exc:
            print(rel + " | fail | " + str(exc))
            mismatches.append(rel)
            checked += 1
            continue
        passed = completed.returncode == 0
        want = expected.get(rel, False)
        if passed:
            print(rel + " | pass | metadata verified=" + str(want))
        else:
            print(rel + " | fail | returncode=" + str(completed.returncode))
        checked += 1
        if passed != want:
            mismatches.append(rel)
    if mismatches:
        print("lean check finished with mismatches: " + ", ".join(mismatches))
        return 1
    print(
        "lean check finished; "
        + str(checked)
        + " checked, "
        + str(skipped)
        + " skipped; kernel result matches metadata for checked files"
    )
    return 0


def run_lean_replay_command(limit: int) -> int:
    path = default_lean_pilot_path()
    problems = load_lean_pilot(path)
    core = [entry for entry in problems if entry["source"] == "core"]
    selected = core[:limit]
    backend = SubprocessLeanBackend()
    failures = 0
    for entry in selected:
        name = str(entry["name"])
        theorem = str(entry["theorem"])
        reference = [str(item) for item in entry["reference_proof"]]
        try:
            state = backend.reset(theorem)
        except Exception as exc:
            print(name + " | fail | 0 | reset: " + str(exc))
            failures += 1
            continue
        steps = 0
        error = ""
        ok = True
        for tactic in reference:
            result = backend.apply(state, tactic)
            if not result.success or result.new_state is None:
                error = result.error or "tactic failed"
                ok = False
                break
            state = result.new_state
            steps += 1
        if ok and len(state.goals) != 0:
            ok = False
            error = "goals remain: " + str(len(state.goals))
        if ok:
            print(name + " | pass | " + str(steps) + " | ")
        else:
            print(name + " | fail | " + str(steps) + " | " + error)
            failures += 1
    print(
        "lean replay finished; "
        + str(len(selected) - failures)
        + " passed, "
        + str(failures)
        + " failed, "
        + str(len(selected))
        + " attempted"
    )
    return 1 if failures else 0


def make_search_backend(backend_name: str, pantograph_repl=None):
    if str(backend_name) == "pantograph":
        return PantographBackend(repl_path=pantograph_repl, modules=("Mathlib",))
    return SubprocessLeanBackend()


def run_lean_search_command(
    budget_nodes: int, backend_name: str = "leaninteract", pantograph_repl=None
) -> int:
    path = default_lean_pilot_path()
    problems = load_lean_pilot(path)
    wanted = ("lean_prop_identity", "lean_prop_const")
    selected = [entry for entry in problems if entry["name"] in wanted]
    backend = make_search_backend(backend_name, pantograph_repl)
    failures = 0
    for entry in selected:
        name = str(entry["name"])
        theorem = str(entry["theorem"])
        try:
            result = breadth_first_search(
                backend=backend,
                theorem=theorem,
                operators=[],
                controller=ImpasseController(),
                detector=ImpasseDetector(budget=budget_nodes),
                budget_nodes=budget_nodes,
                budget_heartbeats=budget_nodes * 20,
                budget_wall_ms=240000,
            )
        except Exception as exc:
            print(name + " | fail | 0 | search: " + str(exc))
            failures += 1
            continue
        if result.success:
            print(
                name
                + " | pass | "
                + str(result.nodes)
                + " | "
                + "; ".join(result.proof)
            )
        else:
            print(name + " | fail | " + str(result.nodes) + " | no proof found")
            failures += 1
    return 1 if failures else 0


def run_lean_bench_command(
    limit: int,
    budget_nodes: int,
    timeout: int,
    configs_text: str,
    family,
    split,
    threshold: float,
    patience: int,
    backend_name: str = "leaninteract",
    pantograph_repl=None,
    out: str = "runs",
    seed: int = 0,
) -> int:
    raw = [item.strip() for item in str(configs_text).split(",")]
    configs = [item for item in raw if item]
    if not configs:
        configs = list(LEAN_BENCH_DEFAULT_CONFIGS)
    for item in configs:
        if item not in LEAN_BENCH_ALL_CONFIGS:
            print("unknown lean-bench config " + repr(item))
            print("allowed: " + ", ".join(LEAN_BENCH_ALL_CONFIGS))
            return 2
    problems = select_lean_bench_problems(limit=limit, family=family, split=split)
    print("lean bench problems: " + str(len(problems)))
    print("lean bench configs: " + ", ".join(configs))
    print("lean bench budget_nodes: " + str(budget_nodes))
    print("lean bench timeout: " + str(timeout))
    print("lean bench split: " + str(split if split else "all"))
    print("lean bench backend: " + str(backend_name))
    print(
        "lean bench impasse: threshold="
        + str(threshold)
        + " patience="
        + str(patience)
    )
    run = open_run(
        out,
        "lean-bench",
        {
            "limit": limit,
            "budget_nodes": budget_nodes,
            "timeout": timeout,
            "configs": configs,
            "family": family,
            "split": split,
            "impasse_threshold": threshold,
            "impasse_patience": patience,
            "detector": detector_params(
                ImpasseDetector(threshold=threshold, patience=patience)
            ),
            "budget_wall_ms": int(timeout) * 1000,
            "backend": backend_name,
            "pantograph_repl": pantograph_repl,
            "out": str(out),
        },
        int(seed),
    )
    if run is None:
        return 1
    try:
        with run.guard() as outcome:
            results, walls, errors = run_lean_bench(
                problems,
                budget_nodes=budget_nodes,
                timeout=timeout,
                config_names=configs,
                threshold=threshold,
                patience=patience,
                backend_name=backend_name,
                pantograph_repl=pantograph_repl,
                run=run,
                seed=int(seed),
            )
            outcome.summary = summarize_for_log(results)
    except Exception as exc:
        print("lean bench failed: " + str(exc))
        print("run dir: " + str(run.path))
        return 1
    print(format_lean_bench_rows(problems, results, walls, errors))
    print(format_lean_bench_summary(results, walls))
    print("run dir: " + str(run.path))
    return 0


def run_b0_command(
    k: int,
    limit,
    max_tokens: int,
    seed: int = 0,
    out: str = "runs",
    controls: bool = False,
    benchmark_dir: str | None = None,
    backend: str = llm_baseline.DEFAULT_BACKEND,
    verify_workers: int = llm_baseline.DEFAULT_VERIFY_WORKERS,
) -> int:
    if k < 1 or max_tokens < 1 or (limit is not None and limit < 1):
        print("b0 needs --k >= 1, --max-tokens >= 1 and --limit >= 1")
        return 2
    if verify_workers < 1:
        print("b0 needs --verify-workers >= 1")
        return 2
    problems = llm_baseline.load_b0_problems(None if controls else limit, benchmark_dir)
    base_args = {
        "model": llm_baseline.default_model_name(backend),
        "backend": backend,
        "k": k,
        "limit": limit,
        "max_tokens": max_tokens,
        "temperature": llm_baseline.DEFAULT_TEMP,
        "prompt_template": llm_baseline.PROMPT_TEMPLATE,
        "eval_header": llm_baseline.EVAL_HEADER,
        "lean_command": llm_baseline.lean_verify_command("<candidate.lean>"),
        "lean_cwd": str(llm_baseline.default_lean_dir()),
        "lean_timeout_s": llm_baseline.LEAN_TIMEOUT_S,
        "benchmark": str(benchmark_dir or llm_baseline.default_lean_pilot_dir()),
        "out": str(out),
    }
    if controls:
        base_args["control_problems"] = list(llm_baseline.CONTROL_PROBLEMS)
        run = open_run(out, "b0-controls", base_args, int(seed))
        if run is None:
            return 1
        report = None
        try:
            with run.guard() as outcome:
                report = llm_baseline.run_controls(run, problems)
                (run.path / "controls.json").write_text(
                    json.dumps(report, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8",
                )
                outcome.summary = {
                    "C1": report["C1"]["ok"],
                    "C2": report["C2"]["ok"],
                    "ok": report["ok"],
                }
        except Exception as exc:
            print("b0 controls failed: " + str(exc))
            print("run dir: " + str(run.path))
            return 1
        print(llm_baseline.format_controls(report))
        print("run dir: " + str(run.path))
        return 0 if report["ok"] else 1
    print("b0 problems: " + str(len(problems)))
    print("b0 backend: " + backend + " model: " + llm_baseline.default_model_name(backend))
    print("b0 k: " + str(k) + " max_tokens: " + str(max_tokens))
    run = open_run(out, "b0", base_args, int(seed))
    if run is None:
        return 1
    try:
        with run.guard() as outcome:
            outcome.summary = llm_baseline.run_b0(
                run, problems, k=k, max_tokens=max_tokens, seed=int(seed), backend=backend,
                verify_workers=verify_workers,
            )
    except Exception as exc:
        print("b0 failed: " + str(exc))
        print("run dir: " + str(run.path))
        return 1
    print(llm_baseline.format_b0_summary(outcome.summary))
    print("run dir: " + str(run.path))
    return 0


def run_hint_gap_command(
    k: int,
    limit,
    max_tokens: int,
    seed: int = 0,
    out: str = "runs",
    benchmark_dir: str | None = None,
    names: list[str] | None = None,
    backend: str = llm_baseline.DEFAULT_BACKEND,
    verify_workers: int = llm_baseline.DEFAULT_VERIFY_WORKERS,
) -> int:
    if k < 1 or max_tokens < 1 or (limit is not None and limit < 1):
        print("hint-gap needs --k >= 1, --max-tokens >= 1 and --limit >= 1")
        return 2
    if verify_workers < 1:
        print("hint-gap needs --verify-workers >= 1")
        return 2
    problems = llm_baseline.load_b0_problems(None, benchmark_dir)
    try:
        targets = llm_baseline.select_hint_gap_problems(problems, limit, names)
    except ValueError as exc:
        print("hint-gap: " + str(exc))
        return 2
    if not targets:
        print("hint-gap: no insight problems with an auxiliary construction in this benchmark")
        return 2
    base_args = {
        "model": llm_baseline.default_model_name(backend),
        "backend": backend,
        "k": k,
        "limit": limit,
        "max_tokens": max_tokens,
        "temperature": llm_baseline.DEFAULT_TEMP,
        "prompt_template": llm_baseline.PROMPT_TEMPLATE,
        "hint_prompt_template": llm_baseline.HINT_PROMPT_TEMPLATE,
        "eval_header": llm_baseline.EVAL_HEADER,
        "lean_command": llm_baseline.lean_verify_command("<candidate.lean>"),
        "lean_cwd": str(llm_baseline.default_lean_dir()),
        "lean_timeout_s": llm_baseline.LEAN_TIMEOUT_S,
        "benchmark": str(benchmark_dir or llm_baseline.default_lean_pilot_dir()),
        "problems": [p["name"] for p in targets],
        "out": str(out),
    }
    print("hint-gap problems: " + str(len(targets)))
    print("hint-gap backend: " + backend + " model: " + llm_baseline.default_model_name(backend))
    print("hint-gap k: " + str(k) + " max_tokens: " + str(max_tokens))
    run = open_run(out, "hint-gap", base_args, int(seed))
    if run is None:
        return 1
    try:
        with run.guard() as outcome:
            outcome.summary = llm_baseline.run_hint_gap(
                run, problems, k=k, max_tokens=max_tokens, seed=int(seed),
                limit=limit, names=names, backend=backend,
                verify_workers=verify_workers,
            )
    except Exception as exc:
        print("hint-gap failed: " + str(exc))
        print("run dir: " + str(run.path))
        return 1
    print(llm_baseline.format_hint_gap_summary(outcome.summary))
    print("run dir: " + str(run.path))
    return 0


def run_features() -> int:
    detector = ImpasseDetector(threshold=0.2, patience=2, window=5, budget=10)
    trace = [
        (False, False),
        (False, True),
        (False, True),
        (False, True),
        (False, False),
    ]
    for index, pair in enumerate(trace):
        progress = pair[0]
        duplicate = pair[1]
        fired = detector.update(progress, duplicate, index + 1)
        current = detector.features()
        print(
            "step "
            + str(index + 1)
            + " nodes_since_progress="
            + format(current.nodes_since_progress, ".3f")
            + " duplicate_state_rate="
            + format(current.duplicate_state_rate, ".3f")
            + " budget_fraction="
            + format(current.budget_fraction, ".3f")
            + " fired="
            + str(fired)
        )
    final = detector.features()
    print(
        "final nodes_since_progress="
        + format(final.nodes_since_progress, ".3f")
        + " duplicate_state_rate="
        + format(final.duplicate_state_rate, ".3f")
        + " budget_fraction="
        + format(final.budget_fraction, ".3f")
    )
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="mathesis")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("smoke")
    pilot_parser = sub.add_parser("pilot")
    pilot_parser.add_argument("--out", type=str, default="runs")
    pilot_parser.add_argument("--seed", type=int, default=0)
    sub.add_parser("features")
    sub.add_parser("lean-pilot")
    replay_parser = sub.add_parser("lean-replay")
    replay_parser.add_argument("--limit", type=int, default=5)
    search_parser = sub.add_parser("lean-search")
    search_parser.add_argument("--budget-nodes", type=int, default=20)
    search_parser.add_argument(
        "--backend", type=str, default="leaninteract",
        choices=["leaninteract", "pantograph"],
    )
    search_parser.add_argument("--pantograph-repl", type=str, default=None)
    bench_parser = sub.add_parser("lean-bench")
    bench_parser.add_argument("--limit", type=int, default=10)
    bench_parser.add_argument("--budget-nodes", type=int, default=30)
    bench_parser.add_argument("--timeout", type=int, default=60)
    bench_parser.add_argument(
        "--configs", type=str, default=",".join(LEAN_BENCH_DEFAULT_CONFIGS)
    )
    bench_parser.add_argument("--family", type=str, default=None)
    bench_parser.add_argument("--split", type=str, default=None)
    bench_parser.add_argument("--impasse-threshold", type=float, default=FROZEN_IMPASSE_THRESHOLD)
    bench_parser.add_argument("--impasse-patience", type=int, default=FROZEN_IMPASSE_PATIENCE)
    bench_parser.add_argument(
        "--backend", type=str, default="leaninteract",
        choices=["leaninteract", "pantograph"],
    )
    bench_parser.add_argument("--pantograph-repl", type=str, default=None)
    bench_parser.add_argument("--out", type=str, default="runs")
    bench_parser.add_argument("--seed", type=int, default=0)
    b0_parser = sub.add_parser("b0")
    b0_parser.add_argument("--k", type=int, default=llm_baseline.DEFAULT_K)
    b0_parser.add_argument("--limit", type=int, default=None)
    b0_parser.add_argument(
        "--max-tokens", type=int, default=llm_baseline.DEFAULT_MAX_TOKENS
    )
    b0_parser.add_argument("--seed", type=int, default=0)
    b0_parser.add_argument("--out", type=str, default="runs")
    b0_parser.add_argument(
        "--benchmark",
        type=str,
        default=None,
        help="benchmark directory holding problems.json (default: benchmark/lean_pilot)",
    )
    b0_parser.add_argument(
        "--controls",
        action="store_true",
        help="run only the validation controls C1/C2 (no model, no generation)",
    )
    b0_parser.add_argument(
        "--backend",
        type=str,
        default=llm_baseline.DEFAULT_BACKEND,
        choices=list(llm_baseline.BACKENDS),
        help="generation backend (default: transformers; mlx is Apple-silicon only)",
    )
    b0_parser.add_argument(
        "--verify-workers",
        type=int,
        default=llm_baseline.DEFAULT_VERIFY_WORKERS,
        help="concurrent Lean checks (default: %d)" % llm_baseline.DEFAULT_VERIFY_WORKERS,
    )
    hint_parser = sub.add_parser("hint-gap")
    hint_parser.add_argument("--k", type=int, default=llm_baseline.DEFAULT_K)
    hint_parser.add_argument("--limit", type=int, default=None)
    hint_parser.add_argument(
        "--max-tokens", type=int, default=llm_baseline.DEFAULT_MAX_TOKENS
    )
    hint_parser.add_argument("--seed", type=int, default=0)
    hint_parser.add_argument("--out", type=str, default="runs")
    hint_parser.add_argument(
        "--benchmark",
        type=str,
        default=None,
        help="benchmark directory holding problems.json (default: benchmark/lean_pilot)",
    )
    hint_parser.add_argument(
        "--problems",
        type=str,
        default=None,
        help="comma-separated problem names to restrict the hint-gap targets to",
    )
    hint_parser.add_argument(
        "--backend",
        type=str,
        default=llm_baseline.DEFAULT_BACKEND,
        choices=list(llm_baseline.BACKENDS),
        help="generation backend (default: transformers; mlx is Apple-silicon only)",
    )
    hint_parser.add_argument(
        "--verify-workers",
        type=int,
        default=llm_baseline.DEFAULT_VERIFY_WORKERS,
        help="concurrent Lean checks (default: %d)" % llm_baseline.DEFAULT_VERIFY_WORKERS,
    )
    args = parser.parse_args(argv)
    if args.command == "smoke":
        return run_smoke()
    if args.command == "pilot":
        return run_pilot_command(args.out, args.seed)
    if args.command == "features":
        return run_features()
    if args.command == "lean-pilot":
        return run_lean_pilot_command()
    if args.command == "lean-replay":
        return run_lean_replay_command(args.limit)
    if args.command == "lean-search":
        return run_lean_search_command(args.budget_nodes, args.backend, args.pantograph_repl)
    if args.command == "lean-bench":
        return run_lean_bench_command(
            args.limit,
            args.budget_nodes,
            args.timeout,
            args.configs,
            args.family,
            args.split,
            args.impasse_threshold,
            args.impasse_patience,
            args.backend,
            args.pantograph_repl,
            args.out,
            args.seed,
        )
    if args.command == "b0":
        return run_b0_command(
            args.k, args.limit, args.max_tokens, args.seed, args.out, args.controls, args.benchmark,
            args.backend, verify_workers=args.verify_workers,
        )
    if args.command == "hint-gap":
        names = args.problems.split(",") if args.problems else None
        return run_hint_gap_command(
            args.k, args.limit, args.max_tokens, args.seed, args.out, args.benchmark, names,
            args.backend, verify_workers=args.verify_workers,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
