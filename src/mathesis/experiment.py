import json
import time
from pathlib import Path

from mathesis.backend import MockLeanBackend
from mathesis.controller import (
    AlwaysRestructureController,
    FixedScheduleController,
    ImpasseController,
    RandomTriggerController,
)
from mathesis.impasse import ImpasseDetector
from mathesis.operators import AddSubgoalOperator, AddSymbolOperator
from mathesis.runlog import CountingBackend
from mathesis.search import breadth_first_search
from mathesis.types import PilotProblem, SearchResult


def load_problems(path: str | Path) -> list[PilotProblem]:
    location = Path(path)
    raw = json.loads(location.read_text(encoding="utf-8"))
    problems: list[PilotProblem] = []
    if isinstance(raw, dict) and "problems" in raw:
        entries = raw["problems"]
    elif isinstance(raw, list):
        entries = raw
    else:
        raise ValueError("problems file needs a list or a dict with problems")
    for entry in entries:
        problems.append(
            PilotProblem(
                name=str(entry["name"]),
                theorem=str(entry["theorem"]),
                family=str(entry.get("family", "implication")),
                insight=bool(entry.get("insight", False)),
                reference_proof=tuple(str(item) for item in entry.get("reference_proof", [])),
                budget_nodes=int(entry.get("budget_nodes", 100)),
            )
        )
    return problems


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_problems_path() -> Path:
    return default_repo_root() / "benchmark" / "pilot" / "problems.json"


def make_stack(
    budget_nodes: int, backend=None
) -> tuple[MockLeanBackend, list, ImpasseDetector]:
    if backend is None:
        backend = MockLeanBackend()
    operators = [AddSubgoalOperator(backend), AddSymbolOperator(backend)]
    detector = ImpasseDetector(budget=budget_nodes)
    return backend, operators, detector


def run_single(
    problem: PilotProblem,
    controller,
    budget_wall_ms: int = 5000,
    detector: ImpasseDetector | None = None,
) -> SearchResult:
    return run_single_measured(problem, controller, budget_wall_ms, detector)[0]


def run_single_measured(
    problem: PilotProblem,
    controller,
    budget_wall_ms: int = 5000,
    detector: ImpasseDetector | None = None,
) -> tuple[SearchResult, int, float]:
    """Like run_single, but also returns (Lean backend calls, wall-clock seconds)."""
    counted = CountingBackend(MockLeanBackend())
    backend, operators, default_detector = make_stack(problem.budget_nodes, counted)
    active_detector = detector if detector is not None else default_detector
    start = time.monotonic()
    result = breadth_first_search(
        backend=backend,
        theorem=problem.theorem,
        operators=operators,
        controller=controller,
        detector=active_detector,
        budget_nodes=problem.budget_nodes,
        budget_heartbeats=problem.budget_nodes * 20,
        budget_wall_ms=budget_wall_ms,
    )
    return result, counted.calls, time.monotonic() - start


def run_pilot(
    problems_path: str | Path | None = None,
    budget_wall_ms: int = 5000,
    run=None,
    seed: int = 0,
) -> dict[str, dict[str, SearchResult]]:
    if problems_path is None:
        problems_path = default_problems_path()
    problems = load_problems(problems_path)
    results: dict[str, dict[str, SearchResult]] = {}
    for config_name in [
        "Mathesis",
        "AlwaysRestructure",
        "FixedSchedule",
        "RandomTrigger",
    ]:
        per_problem: dict[str, SearchResult] = {}
        for problem in problems:
            fresh_controller = recreate_controller(config_name, seed)
            outcome, lean_calls, wall_seconds = run_single_measured(
                problem, fresh_controller, budget_wall_ms=budget_wall_ms
            )
            per_problem[problem.name] = outcome
            if run is not None:
                run.append_result(
                    {
                        "problem": problem.name,
                        "family": problem.family,
                        "config": config_name,
                        "solved": bool(outcome.success),
                        "nodes": int(outcome.nodes),
                        "lean_calls": int(lean_calls),
                        "wall_seconds": wall_seconds,
                        "budget_nodes": int(problem.budget_nodes),
                        "seed": int(seed),
                        "error": "",
                        "impasse_count": int(outcome.impasse_count),
                        "operator_uses": int(outcome.operator_uses),
                    }
                )
        results[config_name] = per_problem
    return results


def recreate_controller(name: str, seed: int = 0):
    if name == "Mathesis":
        return ImpasseController()
    if name == "AlwaysRestructure":
        return AlwaysRestructureController()
    if name == "FixedSchedule":
        return FixedScheduleController(interval=5)
    if name == "RandomTrigger":
        return RandomTriggerController(probability=0.2, seed=int(seed))
    raise ValueError("unknown configuration " + repr(name))


def summarize_config(per_problem: dict[str, SearchResult]) -> dict[str, float]:
    total = len(per_problem)
    solved = sum(1 for item in per_problem.values() if item.success)
    if total == 0:
        return {
            "solve_rate": 0.0,
            "mean_nodes": 0.0,
            "mean_heartbeats": 0.0,
            "mean_wall_ms": 0.0,
            "mean_impasse": 0.0,
            "mean_operator": 0.0,
        }
    mean_nodes = sum(item.nodes for item in per_problem.values()) / total
    mean_heartbeats = (
        sum(item.cost.lean_heartbeats for item in per_problem.values()) / total
    )
    mean_wall = sum(item.cost.wall_ms for item in per_problem.values()) / total
    mean_impasse = sum(item.impasse_count for item in per_problem.values()) / total
    mean_operator = sum(item.operator_uses for item in per_problem.values()) / total
    return {
        "solve_rate": solved / total,
        "mean_nodes": mean_nodes,
        "mean_heartbeats": mean_heartbeats,
        "mean_wall_ms": mean_wall,
        "mean_impasse": mean_impasse,
        "mean_operator": mean_operator,
    }


def format_summary_table(
    results: dict[str, dict[str, SearchResult]],
) -> str:
    header = (
        "config | solve_rate | mean_nodes | mean_heartbeats | mean_wall_ms | "
        "mean_impasse | mean_operator"
    )
    lines = [header]
    for config_name in ["Mathesis", "AlwaysRestructure", "FixedSchedule", "RandomTrigger"]:
        if config_name not in results:
            continue
        summary = summarize_config(results[config_name])
        lines.append(
            config_name
            + " | "
            + format(summary["solve_rate"], ".3f")
            + " | "
            + format(summary["mean_nodes"], ".1f")
            + " | "
            + format(summary["mean_heartbeats"], ".1f")
            + " | "
            + format(summary["mean_wall_ms"], ".1f")
            + " | "
            + format(summary["mean_impasse"], ".2f")
            + " | "
            + format(summary["mean_operator"], ".2f")
        )
    return "\n".join(lines)


def format_per_problem(
    problems: list[PilotProblem],
    results: dict[str, dict[str, SearchResult]],
) -> str:
    lines: list[str] = []
    for problem in problems:
        parts = ["problem " + problem.name + " insight=" + str(problem.insight)]
        for config_name in ["Mathesis", "AlwaysRestructure", "FixedSchedule", "RandomTrigger"]:
            if config_name in results and problem.name in results[config_name]:
                outcome = results[config_name][problem.name]
                flag = "ok" if outcome.success else "fail"
                parts.append(
                    config_name
                    + ":"
                    + flag
                    + " nodes="
                    + str(outcome.nodes)
                    + " beats="
                    + str(outcome.cost.lean_heartbeats)
                    + " imp="
                    + str(outcome.impasse_count)
                    + " ops="
                    + str(outcome.operator_uses)
                )
        lines.append(" ".join(parts))
    return "\n".join(lines)
