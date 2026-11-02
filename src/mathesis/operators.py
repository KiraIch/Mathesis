from enum import Enum
from typing import Protocol

from mathesis.types import (
    ApplyResult,
    Candidate,
    Cost,
    ProofState,
    Prop,
    is_atom,
    prop_to_string,
    props_equal,
    subformulas,
)


class OperatorFamily(str, Enum):
    ADD_SUBGOAL = "add_subgoal"
    ADD_SYMBOL = "add_symbol"


class Operator(Protocol):
    @property
    def id(self) -> str:
        raise NotImplementedError

    @property
    def family(self) -> OperatorFamily:
        raise NotImplementedError

    def pre(self, state: ProofState) -> bool:
        raise NotImplementedError

    def propose(
        self, state: ProofState, context: dict
    ) -> list[Candidate]:
        raise NotImplementedError

    def cost(self, candidate: Candidate) -> Cost:
        raise NotImplementedError

    def apply(self, state: ProofState, candidate: Candidate) -> ApplyResult:
        raise NotImplementedError


def is_nontrivial(candidate_prop: Prop, state: ProofState) -> bool:
    if not state.goals:
        return False
    current = state.goals[0].proposition
    if props_equal(candidate_prop, current):
        return False
    for hyp in state.hypotheses:
        if props_equal(candidate_prop, hyp.proposition):
            return False
    if is_atom(candidate_prop):
        return True
    assert candidate_prop.left is not None
    assert candidate_prop.right is not None
    if props_equal(candidate_prop.left, current):
        return False
    if props_equal(candidate_prop.right, current):
        return False
    return True


def collect_pool(state: ProofState) -> list[Prop]:
    pool: list[Prop] = []
    for goal in state.goals:
        for item in subformulas(goal.proposition):
            if item not in pool:
                pool.append(item)
    for hyp in state.hypotheses:
        for item in subformulas(hyp.proposition):
            if item not in pool:
                pool.append(item)
    ordered = sorted(pool, key=lambda item: prop_to_string(item))
    return ordered


class AddSubgoalOperator:
    def __init__(self, backend) -> None:
        self.backend = backend
        self.operator_id = "add_subgoal"
        self.operator_family = OperatorFamily.ADD_SUBGOAL

    @property
    def id(self) -> str:
        return self.operator_id

    @property
    def family(self) -> OperatorFamily:
        return self.operator_family

    def pre(self, state: ProofState) -> bool:
        return len(state.goals) > 0

    def propose(
        self, state: ProofState, context: dict
    ) -> list[Candidate]:
        if not self.pre(state):
            return []
        limit = 6
        if "limit" in context and isinstance(context["limit"], int):
            limit = int(context["limit"])
        pool = collect_pool(state)
        out: list[Candidate] = []
        for prop in pool:
            if not is_nontrivial(prop, state):
                continue
            out.append(
                Candidate(
                    operator_id=self.operator_id,
                    family=self.operator_family.value,
                    proposition=prop,
                    witness=None,
                    description="have " + prop_to_string(prop),
                )
            )
            if len(out) >= limit:
                break
        return out

    def cost(self, candidate: Candidate) -> Cost:
        return Cost(lean_heartbeats=5, search_nodes=1, wall_ms=0)

    def apply(self, state: ProofState, candidate: Candidate) -> ApplyResult:
        if candidate.proposition is None:
            return ApplyResult(
                success=False,
                new_state=None,
                error="subgoal candidate needs a proposition",
                heartbeats=1,
            )
        if not is_nontrivial(candidate.proposition, state):
            return ApplyResult(
                success=False,
                new_state=None,
                error="trivial subgoal rejected",
                heartbeats=1,
            )
        return self.backend.add_subgoal(
            state, prop_to_string(candidate.proposition), None
        )


def strip_have_proof(text: str) -> str:
    cleaned = text.strip()
    if ":=" not in cleaned:
        return cleaned
    head, _, _ = cleaned.partition(":=")
    return head.strip()


def sanitize_name_fragment(text: str) -> str:
    kept: list[str] = []
    for ch in text:
        if ch.isalnum():
            kept.append(ch)
        else:
            kept.append("_")
    joined = "".join(kept).strip("_")
    if not joined:
        return "x"
    if len(joined) > 12:
        joined = joined[:12]
    return joined


class OracleHaveOperator:
    def __init__(self, backend, haves: tuple[str, ...] | list[str] = ()) -> None:
        self.backend = backend
        self.haves = tuple(str(item) for item in haves)
        self.operator_id = "oracle_have"
        self.operator_family = OperatorFamily.ADD_SUBGOAL

    @property
    def id(self) -> str:
        return self.operator_id

    @property
    def family(self) -> OperatorFamily:
        return self.operator_family

    def pre(self, state: ProofState) -> bool:
        return len(state.goals) > 0 and len(self.haves) > 0

    def propose(
        self, state: ProofState, context: dict
    ) -> list[Candidate]:
        if not self.pre(state):
            return []
        out: list[Candidate] = []
        seen: set[str] = set()
        for item in self.haves:
            cleaned = item.strip()
            if not cleaned.startswith("have "):
                continue
            if cleaned not in seen:
                seen.add(cleaned)
                out.append(
                    Candidate(
                        operator_id=self.operator_id,
                        family=self.operator_family.value,
                        proposition=None,
                        witness=None,
                        description=cleaned,
                    )
                )
            stripped = strip_have_proof(cleaned)
            if stripped != cleaned and stripped.startswith("have ") and stripped not in seen:
                seen.add(stripped)
                out.append(
                    Candidate(
                        operator_id=self.operator_id,
                        family=self.operator_family.value,
                        proposition=None,
                        witness=None,
                        description=stripped,
                    )
                )
        return out

    def cost(self, candidate: Candidate) -> Cost:
        return Cost(lean_heartbeats=5, search_nodes=1, wall_ms=0)

    def apply(self, state: ProofState, candidate: Candidate) -> ApplyResult:
        text = candidate.description.strip()
        if not text.startswith("have "):
            return ApplyResult(
                success=False,
                new_state=None,
                error="oracle candidate needs a have tactic",
                heartbeats=1,
            )
        return self.backend.apply(state, text)


class TemplateHaveOperator:
    def __init__(self, backend) -> None:
        self.backend = backend
        self.operator_id = "template_have"
        self.operator_family = OperatorFamily.ADD_SUBGOAL

    @property
    def id(self) -> str:
        return self.operator_id

    @property
    def family(self) -> OperatorFamily:
        return self.operator_family

    def pre(self, state: ProofState) -> bool:
        return len(state.goals) > 0

    def propose(
        self, state: ProofState, context: dict
    ) -> list[Candidate]:
        if not self.pre(state):
            return []
        if state.backend_token is None:
            return []
        existing: set[str] = {hyp.name for hyp in state.hypotheses}
        existing.update(item.name for item in state.pending)
        out: list[Candidate] = []

        def fresh(base: str) -> str:
            cleaned = base.strip()
            if not cleaned:
                cleaned = "h_tmpl"
            if cleaned in existing:
                counter = 0
                while True:
                    trial = cleaned + "_" + str(counter)
                    if trial not in existing:
                        existing.add(trial)
                        return trial
                    counter += 1
            existing.add(cleaned)
            return cleaned

        seen: set[str] = set()

        def emit(description: str) -> None:
            if len(out) >= 8:
                return
            if description in seen:
                return
            seen.add(description)
            out.append(
                Candidate(
                    operator_id=self.operator_id,
                    family=self.operator_family.value,
                    proposition=None,
                    witness=None,
                    description=description,
                )
            )

        typed: list[tuple[str, str]] = []
        for hyp in state.hypotheses:
            if hyp.proposition.name is not None:
                type_text = hyp.proposition.name
            else:
                type_text = prop_to_string(hyp.proposition)
            typed.append((hyp.name, type_text))
        forward_added = 0
        for func_name, func_type in typed:
            if forward_added >= 2:
                break
            separator = ""
            if "→" in func_type:
                separator = "→"
            elif "->" in func_type:
                separator = "->"
            else:
                continue
            parts = func_type.split(separator)
            if len(parts) < 2:
                continue
            premise = parts[0].strip()
            conclusion = separator.join(parts[1:]).strip()
            if not premise or not conclusion:
                continue
            for arg_name, arg_type in typed:
                if arg_name == func_name:
                    continue
                if arg_type.strip() != premise:
                    continue
                base = "h_tmpl_" + sanitize_name_fragment(conclusion)
                name = fresh(base)
                description = (
                    "have " + name + " : " + conclusion + " := " + func_name + " " + arg_name
                )
                out.append(
                    Candidate(
                        operator_id=self.operator_id,
                        family=self.operator_family.value,
                        proposition=None,
                        witness=None,
                        description=description,
                    )
                )
                forward_added += 1
                break
        goal_text = ""
        if state.goals:
            goal_prop = state.goals[0].proposition
            if goal_prop.name is not None:
                goal_text = goal_prop.name
            else:
                goal_text = prop_to_string(goal_prop)
        needs_sq = ("≤" in goal_text) or ("<=" in goal_text)
        if needs_sq:
            real_vars: list[str] = []
            for hyp_name, hyp_type in typed:
                if hyp_type.strip() == "ℝ":
                    real_vars.append(hyp_name)
            real_vars = real_vars[:3]
            pairs: list[tuple[str, str]] = []
            for i in range(len(real_vars)):
                for j in range(i + 1, len(real_vars)):
                    pairs.append((real_vars[i], real_vars[j]))
                    if len(pairs) >= 2:
                        break
                if len(pairs) >= 2:
                    break
            for first, second in pairs:
                name = fresh("h_sq_" + sanitize_name_fragment(first + second))
                emit(
                    "have "
                    + name
                    + " : 0 ≤ ("
                    + first
                    + " - "
                    + second
                    + ") ^ 2 := sq_nonneg ("
                    + first
                    + " - "
                    + second
                    + ")"
                )
                pname = fresh("h_sq_add_" + sanitize_name_fragment(first + second))
                emit(
                    "have "
                    + pname
                    + " : 0 ≤ ("
                    + first
                    + " + "
                    + second
                    + ") ^ 2 := sq_nonneg ("
                    + first
                    + " + "
                    + second
                    + ")"
                )
            if len(pairs) >= 1:
                first, second = pairs[0]
                sname = fresh("h_sum_sq_" + sanitize_name_fragment(first + second))
                emit(
                    "have "
                    + sname
                    + " : 0 ≤ "
                    + first
                    + " ^ 2 + "
                    + second
                    + " ^ 2 := add_nonneg (sq_nonneg "
                    + first
                    + ") (sq_nonneg "
                    + second
                    + ")"
                )
            if len(real_vars) >= 3:
                coeff = real_vars[0]
                others = real_vars[1:]
                for target in others:
                    partner = next(
                        item for item in others if item != target
                    )
                    kname = fresh("h_sq_k_" + sanitize_name_fragment(target + coeff))
                    emit(
                        "have "
                        + kname
                        + " : 0 ≤ ("
                        + target
                        + " - "
                        + coeff
                        + " * "
                        + partner
                        + ") ^ 2 := sq_nonneg ("
                        + target
                        + " - "
                        + coeff
                        + " * "
                        + partner
                        + ")"
                    )
            if not pairs and len(real_vars) == 1:
                only = real_vars[0]
                name = fresh("h_sq_template")
                emit(
                    "have " + name + " : 0 ≤ " + only + " ^ 2 := sq_nonneg " + only
                )
            elif not pairs:
                for only in real_vars[:2]:
                    name = fresh("h_sq_" + sanitize_name_fragment(only))
                    emit(
                        "have "
                        + name
                        + " : 0 ≤ "
                        + only
                        + " ^ 2 := sq_nonneg "
                        + only
                    )
        return out

    def cost(self, candidate: Candidate) -> Cost:
        return Cost(lean_heartbeats=5, search_nodes=1, wall_ms=0)

    def apply(self, state: ProofState, candidate: Candidate) -> ApplyResult:
        text = candidate.description.strip()
        if not text.startswith("have "):
            return ApplyResult(
                success=False,
                new_state=None,
                error="template candidate needs a have tactic",
                heartbeats=1,
            )
        return self.backend.apply(state, text)


class AddSymbolOperator:
    def __init__(self, backend=None, term_pool: tuple[str, ...] = ("a", "b", "c")) -> None:
        self.backend = backend
        self.term_pool = term_pool
        self.operator_id = "add_symbol"
        self.operator_family = OperatorFamily.ADD_SYMBOL

    @property
    def id(self) -> str:
        return self.operator_id

    @property
    def family(self) -> OperatorFamily:
        return self.operator_family

    def pre(self, state: ProofState) -> bool:
        return len(state.goals) > 0

    def propose(
        self, state: ProofState, context: dict
    ) -> list[Candidate]:
        if not self.pre(state):
            return []
        out: list[Candidate] = []
        for term in self.term_pool:
            out.append(
                Candidate(
                    operator_id=self.operator_id,
                    family=self.operator_family.value,
                    proposition=None,
                    witness=term,
                    description="witness " + term,
                )
            )
        return out

    def cost(self, candidate: Candidate) -> Cost:
        return Cost(lean_heartbeats=2, search_nodes=1, wall_ms=0)

    def apply(self, state: ProofState, candidate: Candidate) -> ApplyResult:
        if candidate.witness is None:
            return ApplyResult(
                success=False,
                new_state=None,
                error="symbol candidate needs a witness",
                heartbeats=1,
            )
        if self.backend is None:
            return ApplyResult(
                success=False,
                new_state=None,
                error="symbol introduction needs existential support",
                heartbeats=1,
            )
        return self.backend.apply(state, "use " + candidate.witness)
