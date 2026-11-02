from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Prop:
    name: str | None = None
    left: Prop | None = None
    right: Prop | None = None


@dataclass(frozen=True)
class Hypothesis:
    name: str
    proposition: Prop


@dataclass(frozen=True)
class Goal:
    proposition: Prop


@dataclass(frozen=True)
class PendingHave:
    name: str
    proposition: Prop
    base_len: int


@dataclass(frozen=True)
class ProofState:
    goals: tuple[Goal, ...]
    hypotheses: tuple[Hypothesis, ...]
    pending: tuple[PendingHave, ...] = ()
    backend_token: str | None = None


@dataclass(frozen=True)
class Candidate:
    operator_id: str
    family: str
    proposition: Prop | None
    witness: str | None
    description: str


@dataclass(frozen=True)
class Cost:
    lean_heartbeats: int
    search_nodes: int
    wall_ms: int


@dataclass(frozen=True)
class ApplyResult:
    success: bool
    new_state: ProofState | None
    error: str | None
    heartbeats: int


@dataclass(frozen=True)
class TraceEvent:
    kind: str
    detail: str
    node_index: int


@dataclass(frozen=True)
class SearchResult:
    success: bool
    proof: tuple[str, ...]
    nodes: int
    cost: Cost
    impasse_count: int
    operator_uses: int
    trace: tuple[TraceEvent, ...]


@dataclass(frozen=True)
class PilotProblem:
    name: str
    theorem: str
    family: str
    insight: bool
    reference_proof: tuple[str, ...]
    budget_nodes: int


def make_atom(name: str) -> Prop:
    return Prop(name=name, left=None, right=None)


def make_imp(left: Prop, right: Prop) -> Prop:
    return Prop(name=None, left=left, right=right)


def is_atom(prop: Prop) -> bool:
    return prop.name is not None


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    current = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            if current:
                tokens.append(current)
                current = ""
            i += 1
            continue
        if ch == "(" or ch == ")":
            if current:
                tokens.append(current)
                current = ""
            tokens.append(ch)
            i += 1
            continue
        if ch == "-" and i + 1 < len(text) and text[i + 1] == ">":
            if current:
                tokens.append(current)
                current = ""
            tokens.append("->")
            i += 2
            continue
        if ch.isalnum() or ch == "_":
            current += ch
            i += 1
            continue
        raise ValueError("unexpected character " + repr(ch))
    if current:
        tokens.append(current)
    return tokens


def parse_tokens(tokens: list[str], pos: int) -> tuple[Prop, int]:
    left, pos = parse_primary(tokens, pos)
    if pos < len(tokens) and tokens[pos] == "->":
        right, pos = parse_tokens(tokens, pos + 1)
        return make_imp(left, right), pos
    return left, pos


def parse_primary(tokens: list[str], pos: int) -> tuple[Prop, int]:
    if pos >= len(tokens):
        raise ValueError("unexpected end of proposition")
    token = tokens[pos]
    if token == "(":
        inner, next_pos = parse_tokens(tokens, pos + 1)
        if next_pos >= len(tokens) or tokens[next_pos] != ")":
            raise ValueError("missing closing parenthesis")
        return inner, next_pos + 1
    if token == ")" or token == "->":
        raise ValueError("unexpected token " + repr(token))
    if not token[0].isalpha():
        raise ValueError("invalid atom " + repr(token))
    return make_atom(token), pos + 1


def parse_prop(text: str) -> Prop:
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty proposition")
    tokens = tokenize(stripped)
    if not tokens:
        raise ValueError("empty proposition")
    prop, pos = parse_tokens(tokens, 0)
    if pos != len(tokens):
        raise ValueError("trailing tokens " + repr(tokens[pos:]))
    return prop


def prop_to_string(prop: Prop) -> str:
    if is_atom(prop):
        assert prop.name is not None
        return prop.name
    assert prop.left is not None
    assert prop.right is not None
    left_text = prop_to_string(prop.left)
    right_text = prop_to_string(prop.right)
    if not is_atom(prop.left):
        left_text = "(" + left_text + ")"
    return left_text + " -> " + right_text


def prop_size(prop: Prop) -> int:
    if is_atom(prop):
        return 1
    assert prop.left is not None
    assert prop.right is not None
    return 1 + prop_size(prop.left) + prop_size(prop.right)


def subformulas(prop: Prop) -> tuple[Prop, ...]:
    seen: list[Prop] = []
    stack: list[Prop] = [prop]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.append(current)
        if not is_atom(current):
            assert current.left is not None
            assert current.right is not None
            stack.append(current.left)
            stack.append(current.right)
    return tuple(seen)


def split_premises(prop: Prop) -> tuple[tuple[Prop, ...], Prop]:
    premises: list[Prop] = []
    current = prop
    while not is_atom(current):
        assert current.left is not None
        assert current.right is not None
        premises.append(current.left)
        current = current.right
    return tuple(premises), current


def normalize_prop(prop: Prop) -> Prop:
    return prop


def props_equal(first: Prop, second: Prop) -> bool:
    return first == second


def alpha_equivalent(first: Prop, second: Prop) -> bool:
    return first == second


def states_alpha_equivalent(first: ProofState, second: ProofState) -> bool:
    return state_key(first) == state_key(second)


def state_key(state: ProofState) -> tuple:
    goal_parts: list[tuple[str, str]] = []
    for goal in state.goals:
        goal_parts.append((prop_to_string(normalize_prop(goal.proposition)), "open"))
    hyps_sorted = sorted(state.hypotheses, key=lambda item: item.name)
    hyp_parts: list[tuple[str, str]] = []
    for hyp in hyps_sorted:
        hyp_parts.append((hyp.name, prop_to_string(normalize_prop(hyp.proposition))))
    pending_parts: list[tuple[str, str, int]] = []
    for item in state.pending:
        pending_parts.append(
            (item.name, prop_to_string(normalize_prop(item.proposition)), item.base_len)
        )
    return (tuple(goal_parts), tuple(hyp_parts), tuple(pending_parts))


def hash_proof_state(state: ProofState) -> int:
    return hash(state_key(state))
