import unittest

from mathesis.backend import MockLeanBackend
from mathesis.controller import (
    AlwaysRestructureController,
    FixedScheduleController,
    ImpasseController,
    RandomTriggerController,
)
from mathesis.impasse import ImpasseDetector
from mathesis.operators import AddSubgoalOperator, AddSymbolOperator
from mathesis.search import breadth_first_search, retrieval_tactics
from mathesis.types import Goal, Hypothesis, ProofState, make_atom, state_key


class SearchTest(unittest.TestCase):
    def make_stack(self, budget=50):
        backend = MockLeanBackend()
        operators = [AddSubgoalOperator(backend), AddSymbolOperator(backend)]
        detector = ImpasseDetector(budget=budget)
        return backend, operators, detector

    def test_simple_success(self):
        backend, operators, detector = self.make_stack(budget=50)
        result = breadth_first_search(
            backend=backend,
            theorem="P -> P",
            operators=operators,
            controller=ImpasseController(),
            detector=detector,
            budget_nodes=50,
            budget_heartbeats=1000,
            budget_wall_ms=5000,
        )
        self.assertTrue(result.success)
        self.assertGreater(len(result.proof), 0)
        self.assertTrue(backend.check_proof("P -> P", list(result.proof)))

    def test_budget_enforcement(self):
        backend, operators, detector = self.make_stack(budget=200)
        result = breadth_first_search(
            backend=backend,
            theorem="(P -> Q -> R) -> (P -> Q) -> P -> R",
            operators=operators,
            controller=ImpasseController(),
            detector=detector,
            budget_nodes=2,
            budget_heartbeats=1000,
            budget_wall_ms=5000,
        )
        self.assertFalse(result.success)
        self.assertLessEqual(result.nodes, 2)

    def test_heartbeat_budget(self):
        backend, operators, detector = self.make_stack(budget=100)
        result = breadth_first_search(
            backend=backend,
            theorem="(P -> Q) -> (Q -> R) -> P -> R",
            operators=operators,
            controller=ImpasseController(),
            detector=detector,
            budget_nodes=100,
            budget_heartbeats=1,
            budget_wall_ms=5000,
        )
        self.assertFalse(result.success)

    def test_duplicate_dedup(self):
        backend = MockLeanBackend()
        first = backend.reset("P -> P")
        second = backend.reset("P -> P")
        self.assertEqual(state_key(first), state_key(second))
        _, operators, detector = self.make_stack(budget=50)
        result = breadth_first_search(
            backend=backend,
            theorem="P -> Q -> P",
            operators=operators,
            controller=AlwaysRestructureController(),
            detector=detector,
            budget_nodes=50,
            budget_heartbeats=1000,
            budget_wall_ms=5000,
        )
        self.assertTrue(result.success)

    def test_controllers_share_machinery(self):
        for controller in [
            ImpasseController(),
            AlwaysRestructureController(),
            FixedScheduleController(interval=5),
            RandomTriggerController(probability=0.2, seed=0),
        ]:
            backend, operators, detector = self.make_stack(budget=60)
            result = breadth_first_search(
                backend=backend,
                theorem="(P -> Q) -> P -> Q",
                operators=operators,
                controller=controller,
                detector=detector,
                budget_nodes=60,
                budget_heartbeats=1200,
                budget_wall_ms=5000,
            )
            self.assertTrue(result.success)
            self.assertTrue(backend.check_proof("(P -> Q) -> P -> Q", list(result.proof)))

    def test_fixed_schedule(self):
        controller = FixedScheduleController(interval=3)
        self.assertFalse(controller.should_restructure(0, False))
        self.assertFalse(controller.should_restructure(1, True))
        self.assertTrue(controller.should_restructure(3, False))
        self.assertTrue(controller.should_restructure(6, True))

    def test_always(self):
        controller = AlwaysRestructureController()
        self.assertTrue(controller.should_restructure(0, False))
        self.assertTrue(controller.should_restructure(10, True))

    def test_impasse_only(self):
        controller = ImpasseController()
        self.assertFalse(controller.should_restructure(5, False))
        self.assertTrue(controller.should_restructure(5, True))

    def test_random_seeded(self):
        first = RandomTriggerController(probability=0.5, seed=123)
        second = RandomTriggerController(probability=0.5, seed=123)
        for index in range(10):
            self.assertEqual(
                first.should_restructure(index, False),
                second.should_restructure(index, False),
            )

    def test_controller_sees_full_candidate_list(self):
        class RecordingController:
            def __init__(self):
                self.candidate_counts = []

            def should_restructure(self, node_index, impasse_fired):
                return True

            def choose(self, state, candidates):
                self.candidate_counts.append(len(candidates))
                return candidates[0] if candidates else None

        controller = RecordingController()
        backend, operators, detector = self.make_stack(budget=200)
        result = breadth_first_search(
            backend=backend,
            theorem="(P -> Q) -> (Q -> R) -> P -> R",
            operators=operators,
            controller=controller,
            detector=detector,
            budget_nodes=200,
            budget_heartbeats=4000,
            budget_wall_ms=5000,
        )
        self.assertTrue(result.success)
        self.assertGreater(max(controller.candidate_counts), 1)

    def test_trace_and_cost(self):
        backend, operators, detector = self.make_stack(budget=50)
        result = breadth_first_search(
            backend=backend,
            theorem="P -> P",
            operators=operators,
            controller=ImpasseController(),
            detector=detector,
            budget_nodes=50,
            budget_heartbeats=1000,
            budget_wall_ms=5000,
        )
        self.assertGreaterEqual(result.cost.search_nodes, 0)
        self.assertGreaterEqual(result.cost.lean_heartbeats, 0)
        self.assertGreaterEqual(result.cost.wall_ms, 0)
        self.assertIsNotNone(result.trace)


class RetrievalTacticsTest(unittest.TestCase):
    def make_state(self, goal_text, hyps=()):
        goals = (Goal(proposition=make_atom(goal_text)),) if goal_text else ()
        hypotheses = tuple(
            Hypothesis(name=name, proposition=make_atom(type_text))
            for name, type_text in hyps
        )
        return ProofState(
            goals=goals, hypotheses=hypotheses, pending=(), backend_token="0"
        )

    def test_empty_goals_give_nothing(self):
        state = ProofState(goals=(), hypotheses=(), pending=(), backend_token="0")
        self.assertEqual(retrieval_tactics(state), [])

    def test_dvd_goal_proposes_dvd_trans(self):
        state = self.make_state("a \u2223 c", (("h1", "a \u2223 b"),))
        tactics = retrieval_tactics(state)
        self.assertIn("apply dvd_trans", tactics)
        self.assertNotIn("apply Eq.trans", tactics)

    def test_le_goal_proposes_transitivity(self):
        state = self.make_state("a \u2264 c")
        tactics = retrieval_tactics(state)
        self.assertIn("apply le_trans", tactics)
        self.assertIn("apply Nat.le_trans", tactics)

    def test_eq_goal_proposes_eq_trans(self):
        state = self.make_state("a = c")
        self.assertIn("apply Eq.trans", retrieval_tactics(state))

    def test_ground_lemmas_always_present(self):
        state = self.make_state("P")
        tactics = retrieval_tactics(state)
        self.assertIn("exact Nat.prime_two", tactics)
        self.assertIn("exact Nat.zero_add _", tactics)
        self.assertIn("exact Nat.add_comm _ _", tactics)
        self.assertIn("exact List.append_nil _", tactics)
        self.assertIn("exact Real.exp_pos _", tactics)
        self.assertIn("exact (Real.exp_pos _).le", tactics)

    def test_even_goal_proposes_even_lemma(self):
        state = self.make_state("Even (n * (n + 1))")
        self.assertIn(
            "exact Nat.even_mul_succ_self _", retrieval_tactics(state)
        )

    def test_pilot_defs_unfold(self):
        poly = self.make_state("2 \u2264 MathesisPilot.pilotPoly x")
        tactics = retrieval_tactics(poly)
        self.assertIn("unfold MathesisPilot.pilotPoly", tactics)
        self.assertNotIn("unfold MathesisPilot.pilotSeq", tactics)
        seq = self.make_state("Even (MathesisPilot.pilotSeq n)")
        seq_tactics = retrieval_tactics(seq)
        self.assertIn("unfold MathesisPilot.pilotSeq", seq_tactics)
        self.assertNotIn("unfold MathesisPilot.pilotPoly", seq_tactics)

    def test_real_hyps_propose_sq_nonneg(self):
        state = self.make_state(
            "0 \u2264 (a - b) ^ 2",
            (("a", "\u211d"), ("b", "\u211d"), ("h", "P")),
        )
        tactics = retrieval_tactics(state)
        self.assertIn("exact sq_nonneg a", tactics)
        self.assertIn("exact sq_nonneg b", tactics)
        self.assertFalse(any("exact sq_nonneg h" in t for t in tactics))

    def test_no_have_tactics(self):
        state = self.make_state("a = b", (("x", "\u211d"),))
        for tactic in retrieval_tactics(state):
            self.assertFalse(tactic.strip().startswith("have "))

    def test_portfolio_includes_retrieval(self):
        from mathesis.search import lean_tactic_portfolio

        state = self.make_state("a \u2223 c")
        tactics = lean_tactic_portfolio(state)
        self.assertIn("apply dvd_trans", tactics)
        self.assertIn("simp", tactics)


if __name__ == "__main__":
    unittest.main()
