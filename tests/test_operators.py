import unittest

from mathesis.backend import MockLeanBackend
from mathesis.operators import (
    AddSubgoalOperator,
    AddSymbolOperator,
    is_nontrivial,
)
from mathesis.types import parse_prop


class OperatorsTest(unittest.TestCase):
    def setUp(self):
        self.backend = MockLeanBackend()
        self.subgoal = AddSubgoalOperator(self.backend)
        self.symbol = AddSymbolOperator(self.backend)

    def test_nontrivial_rejects_goal(self):
        state = self.backend.reset("P -> P")
        prop = parse_prop("P -> P")
        self.assertFalse(is_nontrivial(prop, state))

    def test_nontrivial_rejects_hyp_alias(self):
        state = self.backend.reset("P -> Q -> P")
        first = self.backend.apply(state, "intro hP")
        assert first.new_state is not None
        alias = parse_prop("P")
        self.assertFalse(is_nontrivial(alias, first.new_state))

    def test_nontrivial_accepts_novel(self):
        state = self.backend.reset("(P -> Q) -> (Q -> R) -> P -> R")
        prop = parse_prop("Q")
        self.assertTrue(is_nontrivial(prop, state))

    def test_subgoal_pre(self):
        state = self.backend.reset("P -> P")
        self.assertTrue(self.subgoal.pre(state))

    def test_subgoal_propose_filtered(self):
        state = self.backend.reset("(P -> Q) -> (Q -> R) -> P -> R")
        candidates = self.subgoal.propose(state, {})
        self.assertGreater(len(candidates), 0)
        for candidate in candidates:
            assert candidate.proposition is not None
            self.assertTrue(is_nontrivial(candidate.proposition, state))

    def test_subgoal_apply(self):
        state = self.backend.reset("(P -> Q) -> (Q -> R) -> P -> R")
        candidates = self.subgoal.propose(state, {})
        self.assertGreater(len(candidates), 0)
        result = self.subgoal.apply(state, candidates[0])
        self.assertTrue(result.success)
        assert result.new_state is not None
        self.assertGreater(len(result.new_state.goals), len(state.goals))

    def test_subgoal_rejects_trivial(self):
        state = self.backend.reset("P -> P")
        from mathesis.types import Candidate

        trivial = Candidate(
            operator_id="add_subgoal",
            family="add_subgoal",
            proposition=parse_prop("P -> P"),
            witness=None,
            description="trivial",
        )
        result = self.subgoal.apply(state, trivial)
        self.assertFalse(result.success)

    def test_symbol_propose_pool(self):
        state = self.backend.reset("P -> P")
        candidates = self.symbol.propose(state, {})
        self.assertEqual(len(candidates), 3)
        witnesses = [item.witness for item in candidates]
        self.assertIn("a", witnesses)

    def test_symbol_apply_mock_only(self):
        state = self.backend.reset("P -> P")
        candidates = self.symbol.propose(state, {})
        result = self.symbol.apply(state, candidates[0])
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_cost_present(self):
        state = self.backend.reset("P -> P")
        candidates = self.subgoal.propose(state, {})
        if candidates:
            cost = self.subgoal.cost(candidates[0])
            self.assertGreaterEqual(cost.lean_heartbeats, 0)
        symbol_cost = self.symbol.cost(self.symbol.propose(state, {})[0])
        self.assertGreaterEqual(symbol_cost.lean_heartbeats, 0)


if __name__ == "__main__":
    unittest.main()
