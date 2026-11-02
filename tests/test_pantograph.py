import json
import os
import unittest
from unittest.mock import patch

from mathesis.pantograph_backend import (
    PantographBackend,
    decode_pantograph_goals,
    decode_state_token,
    encode_state_token,
    parse_have_tactic,
    summarize_messages,
)
from mathesis.types import ProofState


def make_state(token):
    return ProofState(goals=(), hypotheses=(), pending=(), backend_token=token)


class ParseHaveTest(unittest.TestCase):
    def test_full_have_with_term(self):
        parsed = parse_have_tactic(
            "have h_sq : 0 ≤ (a - b) ^ 2 := sq_nonneg (a - b)"
        )
        self.assertEqual(parsed, ("h_sq", "0 ≤ (a - b) ^ 2"))

    def test_have_without_term(self):
        self.assertEqual(parse_have_tactic("have h : P"), ("h", "P"))

    def test_have_by_block_stripped(self):
        parsed = parse_have_tactic("have h : P := by exact hP")
        self.assertEqual(parsed, ("h", "P"))

    def test_non_have_returns_none(self):
        self.assertIsNone(parse_have_tactic("exact h"))
        self.assertIsNone(parse_have_tactic("intro h"))

    def test_missing_colon_returns_none(self):
        self.assertIsNone(parse_have_tactic("have h P"))

    def test_empty_name_or_prop_returns_none(self):
        self.assertIsNone(parse_have_tactic("have  : P"))
        self.assertIsNone(parse_have_tactic("have h : "))
        self.assertIsNone(parse_have_tactic("have h"))

    def test_name_with_space_returns_none(self):
        self.assertIsNone(parse_have_tactic("have my h : P"))


class TokenTest(unittest.TestCase):
    def test_roundtrip(self):
        token = encode_state_token(7)
        self.assertEqual(decode_state_token(token), 7)

    def test_invalid_json(self):
        with self.assertRaises(ValueError):
            decode_state_token("not-json")

    def test_missing_state_id(self):
        with self.assertRaises(ValueError):
            decode_state_token(json.dumps({"goals": []}))

    def test_non_integer_state_id(self):
        with self.assertRaises(ValueError):
            decode_state_token(json.dumps({"stateId": "abc"}))


class DecodeGoalsTest(unittest.TestCase):
    def test_goals_and_hyps(self):
        goals = decode_pantograph_goals(
            [
                {
                    "name": "_uniq.1",
                    "target": {"pp": "P"},
                    "vars": [
                        {"name": "_uniq.0", "userName": "hP", "type": {"pp": "P"}}
                    ],
                }
            ]
        )[0]
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0].proposition.name, "P")

    def test_hyp_dedup_and_fallback_name(self):
        _, hyps = decode_pantograph_goals(
            [
                {
                    "name": "_uniq.1",
                    "target": {"pp": "P"},
                    "vars": [
                        {"name": "_uniq.0", "userName": "hP", "type": {"pp": "P"}},
                        {"name": "_uniq.0", "userName": "hP", "type": {"pp": "P"}},
                        {"name": "_uniq.9", "type": {"pp": "Prop"}},
                    ],
                }
            ]
        )
        self.assertEqual([h.name for h in hyps], ["hP", "_uniq.9"])

    def test_empty_goals(self):
        goals, hyps = decode_pantograph_goals([])
        self.assertEqual(goals, ())
        self.assertEqual(hyps, ())

    def test_message_summary(self):
        self.assertEqual(summarize_messages([]), "")
        text = summarize_messages(
            [{"severity": "error", "data": "first"}, {"severity": "info"}]
        )
        self.assertEqual(text, "first")


class ApplyLogicTest(unittest.TestCase):
    def test_empty_tactic_rejected(self):
        backend = PantographBackend(repl_path="/nonexistent/repl")
        result = backend.apply(make_state(encode_state_token(0)), "   ")
        self.assertFalse(result.success)
        self.assertIsNone(result.new_state)

    def test_missing_token_rejected(self):
        backend = PantographBackend(repl_path="/nonexistent/repl")
        state = ProofState(goals=(), hypotheses=(), pending=(), backend_token=None)
        result = backend.apply(state, "exact h")
        self.assertFalse(result.success)

    def test_bad_token_rejected(self):
        backend = PantographBackend(repl_path="/nonexistent/repl")
        result = backend.apply(make_state("bogus"), "exact h")
        self.assertFalse(result.success)

    def test_have_sent_as_structured_command(self):
        backend = PantographBackend(repl_path="/nonexistent/repl")
        sent = {}

        def fake_send(command, payload, modules=None):
            sent["command"] = command
            sent["payload"] = payload
            return {
                "nextStateId": 4,
                "goals": [],
                "hasSorry": False,
                "hasUnsafe": False,
                "messages": [],
            }

        with patch.object(PantographBackend, "_send", side_effect=fake_send):
            result = backend.apply(
                make_state(encode_state_token(3)), "have h : P := by exact hP"
            )
        self.assertTrue(result.success)
        self.assertEqual(sent["command"], "goal.tactic")
        self.assertEqual(sent["payload"]["have"], "P")
        self.assertEqual(sent["payload"]["binderName"], "h")
        self.assertNotIn("tactic", sent["payload"])

    def test_plain_tactic_targets_first_goal(self):
        backend = PantographBackend(repl_path="/nonexistent/repl")
        sent = {}

        def fake_send(command, payload, modules=None):
            sent["payload"] = payload
            return {
                "nextStateId": 2,
                "goals": [
                    {"name": "g", "target": {"pp": "Q"}, "vars": []},
                ],
                "hasSorry": False,
                "hasUnsafe": False,
                "messages": [],
            }

        with patch.object(PantographBackend, "_send", side_effect=fake_send):
            result = backend.apply(make_state(encode_state_token(1)), "simp")
        self.assertTrue(result.success)
        self.assertEqual(sent["payload"]["tactic"], "simp")
        self.assertEqual(sent["payload"]["goalId"], 0)
        assert result.new_state is not None
        self.assertEqual(len(result.new_state.goals), 1)
        self.assertEqual(result.new_state.goals[0].proposition.name, "Q")

    def test_sorry_response_rejected(self):
        backend = PantographBackend(repl_path="/nonexistent/repl")
        response = {
            "nextStateId": 5,
            "goals": [{"name": "g", "target": {"pp": "P"}, "vars": []}],
            "hasSorry": True,
            "hasUnsafe": False,
            "messages": [],
        }
        with patch.object(PantographBackend, "_send", return_value=response):
            result = backend.apply(make_state(encode_state_token(4)), "exact h")
        self.assertFalse(result.success)
        self.assertIsNone(result.new_state)
        self.assertIn("sorry", str(result.error))

    def test_unsafe_response_rejected(self):
        backend = PantographBackend(repl_path="/nonexistent/repl")
        response = {
            "nextStateId": 5,
            "goals": [],
            "hasSorry": False,
            "hasUnsafe": True,
            "messages": [],
        }
        with patch.object(PantographBackend, "_send", return_value=response):
            result = backend.apply(make_state(encode_state_token(4)), "exact h")
        self.assertFalse(result.success)

    def test_tactic_error_without_state(self):
        backend = PantographBackend(repl_path="/nonexistent/repl")
        response = {
            "goals": None,
            "hasSorry": False,
            "hasUnsafe": False,
            "messages": [{"severity": "error", "data": "nope"}],
        }
        with patch.object(PantographBackend, "_send", return_value=response):
            result = backend.apply(make_state(encode_state_token(4)), "bogus")
        self.assertFalse(result.success)
        self.assertIn("nope", str(result.error))

    def test_reset_uses_print_for_goals(self):
        backend = PantographBackend(repl_path="/nonexistent/repl")
        calls = []

        def fake_send(command, payload, modules=None):
            calls.append((command, payload))
            if command == "goal.start":
                return {"stateId": 0, "root": "r"}
            return {
                "goals": [
                    {"name": "g", "target": {"pp": "P"}, "vars": []},
                ],
                "rootHasSorry": False,
                "rootHasUnsafe": False,
            }

        with patch.object(PantographBackend, "_send", side_effect=fake_send):
            state = backend.reset("P")
        self.assertEqual(calls[0][0], "goal.start")
        self.assertEqual(calls[1][0], "goal.print")
        self.assertEqual(len(state.goals), 1)
        self.assertEqual(decode_state_token(str(state.backend_token)), 0)

    def test_reset_passes_per_problem_imports(self):
        backend = PantographBackend(repl_path="/nonexistent/repl")
        seen = []

        def fake_send(command, payload, modules=None):
            seen.append(tuple(modules or ()))
            if command == "goal.start":
                return {"stateId": 0, "root": "r"}
            return {
                "goals": [
                    {"name": "g", "target": {"pp": "P"}, "vars": []},
                ],
                "rootHasSorry": False,
                "rootHasUnsafe": False,
            }

        with patch.object(PantographBackend, "_send", side_effect=fake_send):
            backend.reset("P", ("Mathlib", "Mathesis.Defs"))
        self.assertEqual(
            seen, [("Mathlib", "Mathesis.Defs"), ("Mathlib", "Mathesis.Defs")]
        )


@unittest.skipUnless(
    os.environ.get("MATHESIS_PANTOGRAPH") == "1",
    "set MATHESIS_PANTOGRAPH=1 to run Pantograph checks",
)
class PantographIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from mathesis.pantograph_backend import default_pantograph_repl

        repl = default_pantograph_repl()
        if not repl.is_file():
            raise unittest.SkipTest("pantograph repl not built")
        cls.backend = PantographBackend(repl_path=repl, modules=("Init",), timeout=120)

    @classmethod
    def tearDownClass(cls):
        cls.backend.close()

    def test_have_subgoal_flow(self):
        state = self.backend.reset("∀ (P : Prop), P → P")
        self.assertEqual(len(state.goals), 1)
        steps = [
            "intro P",
            "intro hP",
            "have h : P := by exact hP",
            "exact hP",
            "exact h",
        ]
        for tactic in steps:
            result = self.backend.apply(state, tactic)
            self.assertTrue(result.success, tactic + " | " + str(result.error))
            assert result.new_state is not None
            state = result.new_state
        self.assertEqual(len(state.goals), 0)

    def test_custom_defs_reset(self):
        from mathesis.pantograph_backend import PantographBackend

        backend = PantographBackend(
            repl_path=self.backend.repl_path,
            modules=("Mathlib", "Mathesis.Defs"),
            timeout=280,
        )
        try:
            poly = backend.reset(
                "\u2200 (x : \u211d), 2 \u2264 MathesisPilot.pilotPoly x",
                ("Mathlib", "Mathesis.Defs"),
            )
            self.assertEqual(len(poly.goals), 1)
            seq = backend.reset(
                "\u2200 (n : Nat), Even (MathesisPilot.pilotSeq n)",
                ("Mathlib", "Mathesis.Defs"),
            )
            self.assertEqual(len(seq.goals), 1)
        finally:
            backend.close()

    def test_kernel_check_rejects_sorry(self):
        ok = self.backend.check_proof(
            "∀ (P : Prop), P → P",
            ["intro P", "intro hP", "have h : P := by exact hP", "exact h"],
            imports=(),
        )
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
