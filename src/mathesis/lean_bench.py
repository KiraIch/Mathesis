import time

from mathesis.backend import SubprocessLeanBackend
from mathesis.controller import (
    AlwaysRestructureController,
    FixedScheduleController,
    ImpasseController,
    RandomTriggerController,
)
from mathesis.impasse import ImpasseDetector
from mathesis.lean_pilot import default_lean_pilot_path, load_lean_pilot
from mathesis.operators import OracleHaveOperator, TemplateHaveOperator
from mathesis.search import breadth_first_search
from mathesis.types import Cost, SearchResult, TraceEvent


LEAN_BENCH_DEFAULT_CONFIGS = (
    "bfs",
    "bfs+oracle-have",
    "mathesis+oracle-have",
    "fixed+oracle-have",
)


LEAN_BENCH_ALL_CONFIGS = (
    "bfs",
    "bfs+oracle-have",
    "mathesis+oracle-have",
    "fixed+oracle-have",
    "random+oracle-have",
    "bfs+template-have",
    "mathesis+template-have",
    "fixed+template-have",
    "random+template-have",
)


TEMPLATE_LABEL = (
    "template-have configs use a non-oracle forward-chaining and "
    "sq_nonneg pattern operator, kept separate from oracle-have results"
)


ORACLE_LABEL = (
    "oracle-have configs use reference have lines as an upper-bound "
    "plumbing check, not a discovery result"
)


FROZEN_IMPASSE_THRESHOLD = 0.3
FROZEN_IMPASSE_PATIENCE = 3


def oracle_haves_for(reference_proof) -> tuple[str, ...]:
    out: list[str] = []
    for item in reference_proof:
        text = str(item).strip()
        if text.startswith("have "):
            out.append(text)
    return tuple(out)


def imports_for_source(source) -> tuple[str, ...]:
    if str(source).strip() == "mathlib":
        return ("Mathlib",)
    return ()


def imports_for_entry(entry) -> tuple[str, ...]:
    raw = entry.get("imports")
    if not raw:
        return ("Mathlib",)
    return tuple(str(item) for item in raw)


def make_lean_controller(name: str):
    if name == "bfs":
        return ImpasseController()
    if name == "bfs+oracle-have":
        return AlwaysRestructureController()
    if name == "mathesis+oracle-have":
        return ImpasseController()
    if name == "fixed+oracle-have":
        return FixedScheduleController(interval=5)
    if name == "random+oracle-have":
        return RandomTriggerController(probability=0.2, seed=0)
    if name == "bfs+template-have":
        return AlwaysRestructureController()
    if name == "mathesis+template-have":
        return ImpasseController()
    if name == "fixed+template-have":
        return FixedScheduleController(interval=5)
    if name == "random+template-have":
        return RandomTriggerController(probability=0.2, seed=0)
    raise ValueError("unknown lean-bench config " + repr(name))


def make_lean_operators(backend, haves: tuple[str, ...], config_name: str):
    if config_name in (
        "bfs+template-have",
        "mathesis+template-have",
        "fixed+template-have",
        "random+template-have",
    ):
        return [TemplateHaveOperator(backend)]
    if config_name == "bfs":
        return []
    if not haves:
        return []
    return [OracleHaveOperator(backend, haves)]


def run_single_lean_config(
    backend,
    theorem: str,
    reference_proof,
    config_name: str,
    budget_nodes: int,
    timeout: int,
    threshold: float = FROZEN_IMPASSE_THRESHOLD,
    patience: int = FROZEN_IMPASSE_PATIENCE,
    initial_state=None,
) -> tuple[SearchResult, int, str]:
    haves = oracle_haves_for(reference_proof)
    operators = make_lean_operators(backend, haves, config_name)
    controller = make_lean_controller(config_name)
    detector = ImpasseDetector(
        threshold=float(threshold), patience=int(patience), budget=budget_nodes
    )
    start = time.monotonic()
    error = ""
    try:
        result = breadth_first_search(
            backend=backend,
            theorem=theorem,
            operators=operators,
            controller=controller,
            detector=detector,
            budget_nodes=budget_nodes,
            budget_heartbeats=budget_nodes * 20,
            budget_wall_ms=int(timeout) * 1000,
            initial_state=initial_state,
        )
    except Exception as exc:
        error = str(exc)
        cost = Cost(lean_heartbeats=0, search_nodes=0, wall_ms=0)
        result = SearchResult(
            success=False,
            proof=(),
            nodes=0,
            cost=cost,
            impasse_count=0,
            operator_uses=0,
            trace=(TraceEvent(kind="error", detail=error[:200], node_index=0),),
        )
    wall_ms = int((time.monotonic() - start) * 1000)
    return result, wall_ms, error


def make_bench_backend(backend_name: str, timeout: int, pantograph_repl=None):
    if str(backend_name) == "pantograph":
        from mathesis.pantograph_backend import PantographBackend

        return PantographBackend(
            repl_path=pantograph_repl, modules=("Mathlib",), timeout=int(timeout)
        )
    return SubprocessLeanBackend(timeout=int(timeout))


def run_lean_bench(
    problems,
    budget_nodes: int = 30,
    timeout: int = 60,
    config_names: tuple[str, ...] | list[str] = LEAN_BENCH_DEFAULT_CONFIGS,
    threshold: float = FROZEN_IMPASSE_THRESHOLD,
    patience: int = FROZEN_IMPASSE_PATIENCE,
    backend_name: str = "leaninteract",
    pantograph_repl=None,
):
    ordered = [str(item) for item in config_names]
    backend = make_bench_backend(backend_name, int(timeout), pantograph_repl)
    results: dict[str, dict[str, SearchResult]] = {name: {} for name in ordered}
    walls: dict[str, dict[str, int]] = {name: {} for name in ordered}
    errors: dict[str, dict[str, str]] = {name: {} for name in ordered}
    for entry in problems:
        name = str(entry["name"])
        theorem = str(entry["theorem"])
        reference = [str(item) for item in entry["reference_proof"]]
        wanted_imports = imports_for_entry(entry)
        try:
            if hasattr(backend, "imports"):
                backend.imports = wanted_imports
                shared = backend.reset(theorem)
            else:
                shared = backend.reset(theorem, wanted_imports)
        except ValueError as exc:
            shared = None
            reset_error = str(exc)
        else:
            reset_error = ""
        for config_name in ordered:
            if shared is None:
                cost = Cost(lean_heartbeats=0, search_nodes=0, wall_ms=0)
                result = SearchResult(
                    success=False,
                    proof=(),
                    nodes=0,
                    cost=cost,
                    impasse_count=0,
                    operator_uses=0,
                    trace=(
                        TraceEvent(
                            kind="error",
                            detail=reset_error[:200],
                            node_index=0,
                        ),
                    ),
                )
                wall_ms = 0
                error = reset_error
            else:
                result, wall_ms, error = run_single_lean_config(
                    backend,
                    theorem,
                    reference,
                    config_name,
                    budget_nodes,
                    int(timeout),
                    threshold,
                    patience,
                    shared,
                )
            results[config_name][name] = result
            walls[config_name][name] = wall_ms
            errors[config_name][name] = error
    return results, walls, errors


def summarize_lean_bench(
    results: dict[str, dict[str, SearchResult]],
    walls: dict[str, dict[str, int]],
) -> dict[str, dict[str, float]]:
    summary: dict[str, dict[str, float]] = {}
    for config_name, per_problem in results.items():
        total = len(per_problem)
        if total == 0:
            summary[config_name] = {
                "solve_rate": 0.0,
                "solved": 0.0,
                "total": 0.0,
                "mean_nodes": 0.0,
                "mean_wall_ms": 0.0,
                "mean_impasse": 0.0,
                "mean_operator": 0.0,
            }
            continue
        solved = sum(1 for item in per_problem.values() if item.success)
        mean_nodes = sum(item.nodes for item in per_problem.values()) / total
        wall_map = walls.get(config_name, {})
        if wall_map:
            mean_wall = sum(wall_map.get(key, 0) for key in per_problem) / total
        else:
            mean_wall = sum(item.cost.wall_ms for item in per_problem.values()) / total
        mean_impasse = sum(item.impasse_count for item in per_problem.values()) / total
        mean_operator = sum(item.operator_uses for item in per_problem.values()) / total
        summary[config_name] = {
            "solve_rate": solved / total,
            "solved": float(solved),
            "total": float(total),
            "mean_nodes": mean_nodes,
            "mean_wall_ms": mean_wall,
            "mean_impasse": mean_impasse,
            "mean_operator": mean_operator,
        }
    return summary


def format_lean_bench_rows(
    problems,
    results: dict[str, dict[str, SearchResult]],
    walls: dict[str, dict[str, int]],
    errors: dict[str, dict[str, str]],
) -> str:
    lines = [ORACLE_LABEL]
    if any("template-have" in config_name for config_name in results):
        lines.append(TEMPLATE_LABEL)
    for entry in problems:
        name = str(entry["name"])
        for config_name in results:
            if name not in results[config_name]:
                continue
            outcome = results[config_name][name]
            wall_ms = walls.get(config_name, {}).get(name, outcome.cost.wall_ms)
            message = errors.get(config_name, {}).get(name, "")
            flag = "ok" if outcome.success else "fail"
            proof_text = "; ".join(outcome.proof) if outcome.success else ""
            lines.append(
                name
                + " | "
                + config_name
                + " | "
                + flag
                + " | nodes="
                + str(outcome.nodes)
                + " | wall_ms="
                + str(wall_ms)
                + " | imp="
                + str(outcome.impasse_count)
                + " | ops="
                + str(outcome.operator_uses)
                + " | err="
                + message
                + " | proof="
                + proof_text
            )
    return "\n".join(lines)


def format_lean_bench_summary(
    results: dict[str, dict[str, SearchResult]],
    walls: dict[str, dict[str, int]],
) -> str:
    summary = summarize_lean_bench(results, walls)
    lines = [ORACLE_LABEL]
    if any("template-have" in config_name for config_name in results):
        lines.append(TEMPLATE_LABEL)
    lines.append(
        "config | solve_rate | solved/total | mean_nodes | mean_wall_ms | "
        "mean_impasse | mean_operator"
    )
    for config_name in results:
        item = summary[config_name]
        lines.append(
            config_name
            + " | "
            + format(item["solve_rate"], ".3f")
            + " | "
            + str(int(item["solved"]))
            + "/"
            + str(int(item["total"]))
            + " | "
            + format(item["mean_nodes"], ".1f")
            + " | "
            + format(item["mean_wall_ms"], ".1f")
            + " | "
            + format(item["mean_impasse"], ".2f")
            + " | "
            + format(item["mean_operator"], ".2f")
        )
    return "\n".join(lines)


def select_lean_bench_problems(limit: int = 10, family=None, split=None):
    path = default_lean_pilot_path()
    problems = load_lean_pilot(path)
    if family is not None and str(family) != "":
        wanted = str(family)
        problems = [entry for entry in problems if str(entry["family"]) == wanted]
    if split is not None and str(split) != "" and str(split) != "all":
        wanted_split = str(split)
        problems = [
            entry for entry in problems if str(entry.get("bench_split", "")) == wanted_split
        ]
    return problems[: int(limit)]
