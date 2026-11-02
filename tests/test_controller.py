import unittest

from mathesis.controller import (
    ImpasseController,
    RandomCandidateSelector,
    pick_first,
)
from mathesis.types import Candidate, Goal, ProofState, parse_prop


def _candidates() -> list[Candidate]:
    return [
        Candidate("op", "fam", None, None, description)
        for description in ("c", "a", "d", "b")
    ]


def _state() -> ProofState:
    return ProofState(goals=(Goal(parse_prop("P -> P")),), hypotheses=())


class ControllerSelectorTest(unittest.TestCase):
    def test_default_selector_equals_pick_first(self):
        candidates = _candidates()
        chosen = ImpasseController().choose(_state(), candidates)
        self.assertEqual(chosen, pick_first(candidates))
        self.assertEqual(chosen.description, "a")

    def test_default_selector_empty(self):
        self.assertIsNone(ImpasseController().choose(_state(), []))

    def test_random_selector_reproducible_and_member(self):
        candidates = _candidates()
        first = RandomCandidateSelector(seed=7)
        second = RandomCandidateSelector(seed=7)
        picks_first = [first(_state(), candidates) for _ in range(20)]
        picks_second = [second(_state(), candidates) for _ in range(20)]
        self.assertEqual(picks_first, picks_second)
        for item in picks_first:
            self.assertIn(item, candidates)

    def test_random_selector_empty_returns_none(self):
        self.assertIsNone(RandomCandidateSelector(seed=0)(_state(), []))

    def test_controller_uses_custom_selector(self):
        candidates = _candidates()
        controller = ImpasseController(selector=RandomCandidateSelector(seed=3))
        chosen = controller.choose(_state(), candidates)
        self.assertIn(chosen, candidates)


if __name__ == "__main__":
    unittest.main()
