import time
from collections import deque

from mathesis.backend import LeanBackend
from mathesis.controller import Controller
from mathesis.impasse import ImpasseDetector
from mathesis.operators import Operator
from mathesis.types import (
    Cost,
    ProofState,
    SearchResult,
    TraceEvent,
    prop_to_string,
    state_key,
)


def current_wall_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000.0)


def fresh_intro_name(state: ProofState) -> str:
    base = "h_" + str(len(state.hypotheses) + len(state.pending))
    existing = {hyp.name for hyp in state.hypotheses}
    existing.update(item.name for item in state.pending)
    if base not in existing:
        return base
    counter = 0
    while True:
        candidate = base + "_" + str(counter)
        if candidate not in existing:
            return candidate
        counter += 1


def lean_intro_name(state: ProofState) -> str:
    if not state.goals:
        return fresh_intro_name(state)
    prop = state.goals[0].proposition
    if prop.name is None:
        return fresh_intro_name(state)
    goal_text = prop.name.strip()
    starts_forall = goal_text.startswith("∀") or goal_text.startswith("forall")
    if not starts_forall:
        return fresh_intro_name(state)
    if goal_text.startswith("∀"):
        rest = goal_text[1:].strip()
    else:
        rest = goal_text[len("forall"):].strip()
    if not rest:
        return fresh_intro_name(state)
    opener = rest[0]
    if opener != "(" and opener != "{":
        return fresh_intro_name(state)
    closer = ")" if opener == "(" else "}"
    end = rest.find(closer)
    if end < 0:
        return fresh_intro_name(state)
    group = rest[1:end]
    if ":" not in group:
        return fresh_intro_name(state)
    left, _, _ = group.partition(":")
    names = left.split()
    existing = {hyp.name for hyp in state.hypotheses}
    existing.update(item.name for item in state.pending)
    for candidate in names:
        cleaned = candidate.strip()
        if not cleaned:
            continue
        if cleaned not in existing:
            return cleaned
    return fresh_intro_name(state)


def retrieval_tactics(state: ProofState) -> list[str]:
    tactics: list[str] = []
    if not state.goals:
        return tactics
    goal_prop = state.goals[0].proposition
    if goal_prop.name is not None:
        goal_text = goal_prop.name
    else:
        goal_text = prop_to_string(goal_prop)
    if "\u2223" in goal_text:
        tactics.append("apply dvd_trans")
    if "\u2264" in goal_text or "<=" in goal_text:
        tactics.append("apply le_trans")
        tactics.append("apply Nat.le_trans")
    if "=" in goal_text:
        tactics.append("apply Eq.trans")
    if "Even" in goal_text:
        tactics.append("exact Nat.even_mul_succ_self _")
    tactics.append("exact Nat.prime_two")
    tactics.append("exact Nat.zero_add _")
    tactics.append("exact Nat.add_comm _ _")
    tactics.append("exact List.append_nil _")
    tactics.append("exact Real.exp_pos _")
    tactics.append("exact (Real.exp_pos _).le")
    if "pilotPoly" in goal_text:
        tactics.append("unfold MathesisPilot.pilotPoly")
    if "pilotSeq" in goal_text:
        tactics.append("unfold MathesisPilot.pilotSeq")
    real_vars: list[str] = []
    for hyp in state.hypotheses:
        if hyp.proposition.name is not None:
            type_text = hyp.proposition.name
        else:
            type_text = prop_to_string(hyp.proposition)
        if type_text.strip() == "\u211d":
            real_vars.append(hyp.name)
    for var_name in real_vars:
        tactics.append("exact sq_nonneg " + var_name)
    return tactics


def lean_tactic_portfolio(state: ProofState) -> list[str]:
    tactics: list[str] = []
    tactics.append("intro " + lean_intro_name(state))
    for hyp in state.hypotheses:
        tactics.append("exact " + hyp.name)
    for hyp in state.hypotheses:
        tactics.append("apply " + hyp.name)
    tactics.append("simp")
    tactics.append("omega")
    tactics.append("constructor")
    tactics.append("linarith")
    tactics.append("nlinarith")
    tactics.append("ring")
    tactics.append("positivity")
    tactics.append("norm_num")
    tactics.extend(retrieval_tactics(state))
    return tactics


def tactic_expansions(state: ProofState) -> list[str]:
    if not state.goals:
        return []
    if state.backend_token is not None:
        return lean_tactic_portfolio(state)
    tactics: list[str] = []
    current = state.goals[0].proposition
    if current.name is None or state.backend_token is not None:
        tactics.append("intro " + fresh_intro_name(state))
    for hyp in state.hypotheses:
        tactics.append("exact " + hyp.name)
    for hyp in state.hypotheses:
        tactics.append("apply " + hyp.name)
    return tactics


def have_tactic_text(
    before: ProofState, after: ProofState, description: str
) -> str:
    if after.pending and (not before.pending or len(after.pending) > len(before.pending)):
        newest = after.pending[-1]
        return "have " + newest.name + " : " + prop_to_string(newest.proposition)
    return description


def breadth_first_search(
    backend: LeanBackend,
    theorem: str,
    operators: list[Operator],
    controller: Controller,
    detector: ImpasseDetector,
    budget_nodes: int = 100,
    budget_heartbeats: int = 1000,
    budget_wall_ms: int = 5000,
    initial_state: ProofState | None = None,
) -> SearchResult:
    start = time.monotonic()
    if initial_state is not None:
        initial = initial_state
    else:
        try:
            initial = backend.reset(theorem)
        except ValueError:
            cost = Cost(lean_heartbeats=0, search_nodes=0, wall_ms=0)
            return SearchResult(
                success=False,
                proof=(),
                nodes=0,
                cost=cost,
                impasse_count=0,
                operator_uses=0,
                trace=(TraceEvent(kind="error", detail="invalid theorem", node_index=0),),
            )
    detector.reset()
    queue: deque[tuple[ProofState, tuple[str, ...]]] = deque()
    queue.append((initial, ()))
    visited = {state_key(initial)}
    nodes = 0
    heartbeats = 0
    impasse_count = 0
    operator_uses = 0
    trace: list[TraceEvent] = []
    best_goal_count: int | None = None
    last_impasse = False

    while queue:
        if nodes >= budget_nodes:
            trace.append(
                TraceEvent(kind="budget", detail="node budget reached", node_index=nodes)
            )
            break
        if heartbeats >= budget_heartbeats:
            trace.append(
                TraceEvent(
                    kind="budget", detail="heartbeat budget reached", node_index=nodes
                )
            )
            break
        if current_wall_ms(start) >= budget_wall_ms:
            trace.append(
                TraceEvent(kind="budget", detail="wall budget reached", node_index=nodes)
            )
            break
        state, proof = queue.popleft()
        if len(state.goals) == 0:
            cost = Cost(
                lean_heartbeats=heartbeats,
                search_nodes=nodes,
                wall_ms=current_wall_ms(start),
            )
            return SearchResult(
                success=True,
                proof=proof,
                nodes=nodes,
                cost=cost,
                impasse_count=impasse_count,
                operator_uses=operator_uses,
                trace=tuple(trace),
            )
        if best_goal_count is None:
            best_goal_count = len(state.goals)
            made_progress_seed = True
        else:
            made_progress_seed = len(state.goals) < best_goal_count
            if made_progress_seed:
                best_goal_count = len(state.goals)
        allow_operators = controller.should_restructure(nodes, last_impasse)
        successors: list[tuple[ProofState, str, bool]] = []
        for tactic in tactic_expansions(state):
            result = backend.apply(state, tactic)
            heartbeats += result.heartbeats
            if not result.success or result.new_state is None:
                continue
            key = state_key(result.new_state)
            if key in visited:
                successors.append((result.new_state, tactic, True))
                continue
            visited.add(key)
            successors.append((result.new_state, tactic, False))
        operator_candidates = []
        if allow_operators:
            for operator in operators:
                if not operator.pre(state):
                    continue
                try:
                    proposed = operator.propose(state, {})
                except Exception:
                    continue
                operator_candidates.extend(
                    [(operator, item) for item in proposed]
                )
            operator_candidates = sorted(
                operator_candidates, key=lambda pair: pair[1].description
            )
            remaining = list(operator_candidates)
            while remaining:
                chosen = controller.choose(state, [item[1] for item in remaining])
                if chosen is None:
                    break
                pair = next(item for item in remaining if item[1] is chosen)
                remaining.remove(pair)
                operator, _ = pair
                result = operator.apply(state, chosen)
                heartbeats += result.heartbeats
                if not result.success or result.new_state is None:
                    continue
                key = state_key(result.new_state)
                tactic_text = have_tactic_text(
                    state, result.new_state, chosen.description
                )
                if key in visited:
                    successors.append((result.new_state, tactic_text, True))
                    break
                visited.add(key)
                successors.append((result.new_state, tactic_text, False))
                operator_uses += 1
                trace.append(
                    TraceEvent(
                        kind="operator",
                        detail=chosen.description,
                        node_index=nodes,
                    )
                )
                break
        duplicate_hits = sum(1 for _, _, dup in successors if dup)
        is_duplicate_node = duplicate_hits > 0 and len(successors) > 0
        for new_state, tactic_text, was_duplicate in successors:
            if was_duplicate:
                continue
            queue.append((new_state, proof + (tactic_text,)))
        if best_goal_count is not None and len(state.goals) < best_goal_count:
            made_progress = True
            best_goal_count = len(state.goals)
        else:
            made_progress = made_progress_seed
        fired = detector.update(made_progress, is_duplicate_node, nodes + 1)
        last_impasse = fired
        if fired:
            impasse_count += 1
            trace.append(
                TraceEvent(kind="impasse", detail="impasse detected", node_index=nodes)
            )
        nodes += 1

    cost = Cost(
        lean_heartbeats=heartbeats,
        search_nodes=nodes,
        wall_ms=current_wall_ms(start),
    )
    return SearchResult(
        success=False,
        proof=(),
        nodes=nodes,
        cost=cost,
        impasse_count=impasse_count,
        operator_uses=operator_uses,
        trace=tuple(trace),
    )
