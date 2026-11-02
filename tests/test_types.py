import unittest

from mathesis.types import (
    Cost,
    Goal,
    Hypothesis,
    PilotProblem,
    ProofState,
    alpha_equivalent,
    hash_proof_state,
    make_atom,
    make_imp,
    normalize_prop,
    parse_prop,
    prop_size,
    prop_to_string,
    props_equal,
    split_premises,
    state_key,
    states_alpha_equivalent,
    subformulas,
)


class TypesTest(unittest.TestCase):
    def test_parse_atom(self):
        prop = parse_prop("P")
        self.assertEqual(prop, make_atom("P"))

    def test_parse_implication_right_assoc(self):
        prop = parse_prop("P -> Q -> P")
        expected = make_imp(make_atom("P"), make_imp(make_atom("Q"), make_atom("P")))
        self.assertEqual(prop, expected)

    def test_parse_parentheses(self):
        prop = parse_prop("(P -> Q) -> P -> Q")
        left = make_imp(make_atom("P"), make_atom("Q"))
        expected = make_imp(left, make_imp(make_atom("P"), make_atom("Q")))
        self.assertEqual(prop, expected)

    def test_roundtrip(self):
        for text in ["P -> P", "P -> Q -> P", "(P -> Q) -> P -> Q"]:
            prop = parse_prop(text)
            rebuilt = parse_prop(prop_to_string(prop))
            self.assertEqual(prop, rebuilt)

    def test_invalid_proposition(self):
        with self.assertRaises(ValueError):
            parse_prop("")

    def test_invalid_trailing(self):
        with self.assertRaises(ValueError):
            parse_prop("P ->")

    def test_prop_size(self):
        prop = parse_prop("P -> Q")
        self.assertEqual(prop_size(prop), 3)
        self.assertEqual(prop_size(make_atom("P")), 1)

    def test_subformulas_cover(self):
        prop = parse_prop("(P -> Q) -> P")
        parts = subformulas(prop)
        texts = sorted(prop_to_string(item) for item in parts)
        self.assertIn("P", texts)
        self.assertIn("P -> Q", texts)

    def test_split_premises(self):
        prop = parse_prop("P -> Q -> R")
        premises, conclusion = split_premises(prop)
        self.assertEqual(len(premises), 2)
        self.assertEqual(conclusion, make_atom("R"))

    def test_props_equal(self):
        first = parse_prop("P -> Q")
        second = parse_prop("P -> Q")
        third = parse_prop("P -> R")
        self.assertTrue(props_equal(first, second))
        self.assertFalse(props_equal(first, third))

    def test_alpha_interface(self):
        first = parse_prop("P -> Q")
        second = parse_prop("P -> Q")
        self.assertTrue(alpha_equivalent(first, second))
        self.assertEqual(normalize_prop(first), first)

    def test_state_key_stable(self):
        prop = parse_prop("P -> P")
        first = ProofState(
            goals=(Goal(proposition=prop),), hypotheses=(), pending=()
        )
        second = ProofState(
            goals=(Goal(proposition=prop),), hypotheses=(), pending=()
        )
        self.assertEqual(state_key(first), state_key(second))
        self.assertEqual(hash_proof_state(first), hash_proof_state(second))
        self.assertTrue(states_alpha_equivalent(first, second))

    def test_state_key_hyp_order_insensitive(self):
        goal = Goal(proposition=parse_prop("R"))
        hyp_a = Hypothesis(name="hA", proposition=parse_prop("P"))
        hyp_b = Hypothesis(name="hB", proposition=parse_prop("Q"))
        first = ProofState(goals=(goal,), hypotheses=(hyp_a, hyp_b), pending=())
        second = ProofState(goals=(goal,), hypotheses=(hyp_b, hyp_a), pending=())
        self.assertEqual(state_key(first), state_key(second))

    def test_state_key_ignores_backend_token(self):
        goal = Goal(proposition=parse_prop("P -> P"))
        first = ProofState(goals=(goal,), hypotheses=(), backend_token=None)
        second = ProofState(goals=(goal,), hypotheses=(), backend_token="7")
        self.assertEqual(state_key(first), state_key(second))
        self.assertTrue(states_alpha_equivalent(first, second))

    def test_cost_and_pilot(self):
        cost = Cost(lean_heartbeats=7, search_nodes=5, wall_ms=12)
        self.assertEqual(cost.lean_heartbeats, 7)
        problem = PilotProblem(
            name="demo",
            theorem="P -> P",
            family="implication",
            insight=False,
            reference_proof=("intro h", "exact h"),
            budget_nodes=10,
        )
        self.assertFalse(problem.insight)
        self.assertEqual(problem.budget_nodes, 10)


if __name__ == "__main__":
    unittest.main()
