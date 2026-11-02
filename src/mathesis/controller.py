import random
from typing import Callable, Protocol

from mathesis.types import Candidate, ProofState


class Controller(Protocol):
    def should_restructure(
        self, node_index: int, impasse_fired: bool
    ) -> bool:
        raise NotImplementedError

    def choose(
        self, state: ProofState, candidates: list[Candidate]
    ) -> Candidate | None:
        raise NotImplementedError


def pick_first(
    candidates: list[Candidate],
) -> Candidate | None:
    if not candidates:
        return None
    ordered = sorted(candidates, key=lambda item: item.description)
    return ordered[0]


Selector = Callable[[ProofState, list[Candidate]], Candidate | None]


class RandomCandidateSelector:
    """Uniform random choice among candidates (random-candidate baseline B4)."""

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)
        self.rng = random.Random(self.seed)

    def __call__(
        self, state: ProofState, candidates: list[Candidate]
    ) -> Candidate | None:
        if not candidates:
            return None
        return self.rng.choice(candidates)


def _pick_first_selector(
    state: ProofState, candidates: list[Candidate]
) -> Candidate | None:
    return pick_first(candidates)


class ImpasseController:
    def __init__(self, selector: Selector | None = None) -> None:
        self.selector: Selector = selector or _pick_first_selector

    def should_restructure(
        self, node_index: int, impasse_fired: bool
    ) -> bool:
        return bool(impasse_fired)

    def choose(
        self, state: ProofState, candidates: list[Candidate]
    ) -> Candidate | None:
        return self.selector(state, candidates)


class AlwaysRestructureController:
    def should_restructure(
        self, node_index: int, impasse_fired: bool
    ) -> bool:
        return True

    def choose(
        self, state: ProofState, candidates: list[Candidate]
    ) -> Candidate | None:
        return pick_first(candidates)


class FixedScheduleController:
    def __init__(self, interval: int = 5) -> None:
        cleaned = int(interval)
        if cleaned < 1:
            cleaned = 1
        self.interval = cleaned

    def should_restructure(
        self, node_index: int, impasse_fired: bool
    ) -> bool:
        if node_index <= 0:
            return False
        return (node_index % self.interval) == 0

    def choose(
        self, state: ProofState, candidates: list[Candidate]
    ) -> Candidate | None:
        return pick_first(candidates)


class RandomTriggerController:
    def __init__(self, probability: float = 0.2, seed: int = 0) -> None:
        clamped = float(probability)
        if clamped < 0.0:
            clamped = 0.0
        if clamped > 1.0:
            clamped = 1.0
        self.probability = clamped
        self.seed = int(seed)
        self.rng = random.Random(self.seed)

    def should_restructure(
        self, node_index: int, impasse_fired: bool
    ) -> bool:
        return self.rng.random() < self.probability

    def choose(
        self, state: ProofState, candidates: list[Candidate]
    ) -> Candidate | None:
        return pick_first(candidates)
