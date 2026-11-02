import os
import unittest

from mathesis.lean_pilot import default_lean_pilot_path, load_lean_pilot


@unittest.skipUnless(
    os.environ.get("MATHESIS_LEAN_INTERACT") == "1",
    "set MATHESIS_LEAN_INTERACT=1 to run LeanInteract checks",
)
class LeanInteractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from mathesis.backend import SubprocessLeanBackend

        cls.backend = SubprocessLeanBackend()

    def test_reset_identity(self):
        state = self.backend.reset("∀ (P : Prop), P → P")
        self.assertEqual(len(state.goals), 1)
        self.assertEqual(len(state.hypotheses), 0)
        self.assertIsNotNone(state.backend_token)

    def test_replay_identity(self):
        state = self.backend.reset("∀ (P : Prop), P → P")
        for tactic in ("intro P", "intro h", "exact h"):
            result = self.backend.apply(state, tactic)
            self.assertTrue(result.success, result.error)
            assert result.new_state is not None
            state = result.new_state
        self.assertEqual(len(state.goals), 0)

    def test_invalid_tactic_structured(self):
        state = self.backend.reset("∀ (P : Prop), P → P")
        result = self.backend.apply(state, "bogus_tactic_xyz")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertIsNone(result.new_state)

    def test_state_key_ignores_token(self):
        from mathesis.types import state_key

        first = self.backend.reset("∀ (P : Prop), P → P")
        second = self.backend.reset("∀ (P : Prop), P → P")
        self.assertIsNotNone(first.backend_token)
        self.assertIsNotNone(second.backend_token)
        self.assertEqual(state_key(first), state_key(second))

    def test_replay_first_five_core(self):
        problems = load_lean_pilot(default_lean_pilot_path())
        core = [entry for entry in problems if entry["source"] == "core"][:5]
        self.assertEqual(len(core), 5)
        for entry in core:
            with self.subTest(name=entry["name"]):
                state = self.backend.reset(str(entry["theorem"]))
                for tactic in entry["reference_proof"]:
                    result = self.backend.apply(state, str(tactic))
                    self.assertTrue(result.success, result.error)
                    assert result.new_state is not None
                    state = result.new_state
                self.assertEqual(len(state.goals), 0)


if __name__ == "__main__":
    unittest.main()
