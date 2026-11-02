import subprocess
import sys
import unittest
from unittest.mock import patch

from mathesis.backend import MockLeanBackend, SubprocessLeanBackend, decode_lean_goals


class BackendTest(unittest.TestCase):
    def setUp(self):
        self.backend = MockLeanBackend()

    def test_reset(self):
        state = self.backend.reset("P -> P")
        self.assertEqual(len(state.goals), 1)
        self.assertEqual(len(state.hypotheses), 0)

    def test_intro_exact(self):
        state = self.backend.reset("P -> P")
        first = self.backend.apply(state, "intro h")
        self.assertTrue(first.success)
        self.assertIsNotNone(first.new_state)
        assert first.new_state is not None
        second = self.backend.apply(first.new_state, "exact h")
        self.assertTrue(second.success)
        assert second.new_state is not None
        self.assertEqual(len(second.new_state.goals), 0)

    def test_intro_needs_implication(self):
        state = self.backend.reset("P")
        result = self.backend.apply(state, "intro h")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertIsNone(result.new_state)

    def test_intro_duplicate_name(self):
        state = self.backend.reset("P -> Q -> P")
        first = self.backend.apply(state, "intro h")
        assert first.new_state is not None
        second = self.backend.apply(first.new_state, "intro h")
        self.assertFalse(second.success)

    def test_exact_unknown(self):
        state = self.backend.reset("P -> P")
        first = self.backend.apply(state, "intro h")
        assert first.new_state is not None
        result = self.backend.apply(first.new_state, "exact missing")
        self.assertFalse(result.success)

    def test_exact_mismatch(self):
        state = self.backend.reset("P -> Q")
        first = self.backend.apply(state, "intro h")
        assert first.new_state is not None
        result = self.backend.apply(first.new_state, "exact h")
        self.assertFalse(result.success)

    def test_apply_single(self):
        state = self.backend.reset("(P -> Q) -> P -> Q")
        first = self.backend.apply(state, "intro hPQ")
        assert first.new_state is not None
        second = self.backend.apply(first.new_state, "intro hP")
        assert second.new_state is not None
        third = self.backend.apply(second.new_state, "apply hPQ")
        self.assertTrue(third.success)
        assert third.new_state is not None
        fourth = self.backend.apply(third.new_state, "exact hP")
        self.assertTrue(fourth.success)

    def test_apply_mismatch(self):
        state = self.backend.reset("P -> Q")
        first = self.backend.apply(state, "intro h")
        assert first.new_state is not None
        result = self.backend.apply(first.new_state, "apply h")
        self.assertFalse(result.success)

    def test_invalid_tactic_structured(self):
        state = self.backend.reset("P -> P")
        result = self.backend.apply(state, "bogus tactic")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertIsNone(result.new_state)

    def test_empty_tactic_structured(self):
        state = self.backend.reset("P -> P")
        result = self.backend.apply(state, "   ")
        self.assertFalse(result.success)

    def test_use_supported_as_error(self):
        state = self.backend.reset("P -> P")
        result = self.backend.apply(state, "use witness")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_add_subgoal_flow(self):
        state = self.backend.reset("(P -> Q) -> (Q -> R) -> P -> R")
        first = self.backend.apply(state, "intro hPQ")
        assert first.new_state is not None
        second = self.backend.apply(first.new_state, "intro hQR")
        assert second.new_state is not None
        third = self.backend.apply(second.new_state, "intro hP")
        assert third.new_state is not None
        added = self.backend.add_subgoal(third.new_state, "Q", "hQ")
        self.assertTrue(added.success)
        assert added.new_state is not None
        self.assertEqual(len(added.new_state.goals), 2)
        prove_q = self.backend.apply(added.new_state, "apply hPQ")
        assert prove_q.new_state is not None
        self.assertTrue(prove_q.success)
        close_q = self.backend.apply(prove_q.new_state, "exact hP")
        assert close_q.new_state is not None
        self.assertTrue(close_q.success)
        names = [hyp.name for hyp in close_q.new_state.hypotheses]
        self.assertIn("hQ", names)

    def test_have_string(self):
        state = self.backend.reset("P -> Q -> P")
        first = self.backend.apply(state, "intro hP")
        assert first.new_state is not None
        result = self.backend.apply(first.new_state, "have hQ : Q")
        self.assertTrue(result.success)

    def test_add_subgoal_bad_prop(self):
        state = self.backend.reset("P -> P")
        result = self.backend.add_subgoal(state, "-> ->", None)
        self.assertFalse(result.success)

    def test_check_proof_true(self):
        ok = self.backend.check_proof("P -> P", ["intro h", "exact h"])
        self.assertTrue(ok)

    def test_check_proof_false(self):
        ok = self.backend.check_proof("P -> P", ["intro h"])
        self.assertFalse(ok)
        bad = self.backend.check_proof("P -> P", ["exact h"])
        self.assertFalse(bad)

    def test_subprocess_requires_lean_interact(self):
        stub = SubprocessLeanBackend()
        with patch.dict(sys.modules, {"lean_interact": None}):
            with self.assertRaises(RuntimeError):
                stub.reset("P -> P")

    def test_subprocess_runtime_error_mentions_venv(self):
        stub = SubprocessLeanBackend()
        with patch.dict(sys.modules, {"lean_interact": None}):
            try:
                stub.reset("P -> P")
            except RuntimeError as exc:
                self.assertIn(".venv", str(exc))
            else:
                self.fail("expected RuntimeError")

    def test_subprocess_apply_without_token_is_structured_error(self):
        stub = SubprocessLeanBackend()
        state = self.backend.reset("P -> P")
        self.assertIsNone(state.backend_token)
        result = stub.apply(state, "intro h")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertIsNone(result.new_state)

    def test_decode_lean_goals_single(self):
        goals, hyps = decode_lean_goals(["P : Prop\nh : P\n⊢ P"])
        self.assertEqual(len(goals), 1)
        self.assertEqual(len(hyps), 2)
        names = sorted(hyp.name for hyp in hyps)
        self.assertEqual(names, ["P", "h"])

    def test_decode_lean_goals_shared_binder(self):
        goals, hyps = decode_lean_goals(["P Q : Prop\nhP : P\n⊢ Q → P"])
        self.assertEqual(len(goals), 1)
        names = sorted(hyp.name for hyp in hyps)
        self.assertEqual(names, ["P", "Q", "hP"])

    def test_decode_lean_goals_case_tag(self):
        goals, hyps = decode_lean_goals(
            ["case left\nP Q : Prop\nhP : P\n⊢ P", "case right\nP Q : Prop\n⊢ Q"]
        )
        self.assertEqual(len(goals), 2)
        names = sorted(hyp.name for hyp in hyps)
        self.assertIn("hP", names)

    def test_subprocess_render(self):
        stub = SubprocessLeanBackend()
        text = stub.render_file("P -> P", ["intro h", "exact h"])
        self.assertIn("P -> P", text)
        self.assertIn("intro h", text)
        self.assertIn("exact h", text)

    def test_subprocess_check_proof_pass(self):
        stub = SubprocessLeanBackend()
        done = subprocess.CompletedProcess(args=["lean"], returncode=0)
        with patch("shutil.which", return_value="/usr/bin/lean"):
            with patch("subprocess.run", return_value=done) as runner:
                self.assertTrue(stub.check_proof("P -> P", ["intro h", "exact h"]))
                self.assertTrue(runner.called)

    def test_subprocess_check_proof_fail(self):
        stub = SubprocessLeanBackend()
        done = subprocess.CompletedProcess(args=["lean"], returncode=1)
        with patch("shutil.which", return_value="/usr/bin/lean"):
            with patch("subprocess.run", return_value=done):
                self.assertFalse(stub.check_proof("P -> P", ["intro h"]))

    def test_subprocess_check_proof_no_toolchain(self):
        stub = SubprocessLeanBackend()
        with patch("shutil.which", return_value=None):
            with self.assertRaises(RuntimeError):
                stub.check_proof("P -> P", ["intro h", "exact h"])


class ResetCommandTest(unittest.TestCase):
    def test_core_command_has_no_import(self):
        from mathesis.backend import build_reset_command

        cmd = build_reset_command("thm_1", "P -> P", ())
        self.assertEqual(cmd, "theorem thm_1 : P -> P := by sorry")

    def test_mathlib_command_single_prefix(self):
        from mathesis.backend import build_reset_command

        cmd = build_reset_command("thm_2", "∀ (a : ℝ), 0 ≤ a", ("Mathlib",))
        self.assertEqual(
            cmd, "import Mathlib\ntheorem thm_2 : ∀ (a : ℝ), 0 ≤ a := by sorry"
        )

    def test_blank_modules_skipped(self):
        from mathesis.backend import build_reset_command

        cmd = build_reset_command("thm_3", "P -> P", ("", "  "))
        self.assertEqual(cmd, "theorem thm_3 : P -> P := by sorry")

    def test_backend_imports_default_empty(self):
        stub = SubprocessLeanBackend()
        self.assertEqual(stub.imports, ())

    def test_backend_imports_init_param(self):
        stub = SubprocessLeanBackend(imports=("Mathlib",))
        self.assertEqual(stub.imports, ("Mathlib",))

    def test_imports_for_source(self):
        from mathesis.lean_bench import imports_for_source

        self.assertEqual(imports_for_source("mathlib"), ("Mathlib",))
        self.assertEqual(imports_for_source("core"), ())
        self.assertEqual(imports_for_source(""), ())


if __name__ == "__main__":
    unittest.main()
