import math
import unittest
from pathlib import Path

from mathesis import llm_baseline as b0

HEADER = (
    "import Mathlib\n"
    "namespace MathesisPilot\n"
    "theorem lean_x : ∀ (a b : Nat), a + b = b + a := by"
)
FILE_TEXT = HEADER + "\n  intro a\n  intro b\n  exact Nat.add_comm a b\nend MathesisPilot\n"


class PassAtKTest(unittest.TestCase):
    def test_all_failed(self):
        self.assertEqual(b0.pass_at_k(8, 0, 8), 0.0)
        self.assertEqual(b0.pass_at_k(8, 0, 1), 0.0)

    def test_all_passed(self):
        self.assertEqual(b0.pass_at_k(8, 8, 8), 1.0)
        self.assertEqual(b0.pass_at_k(8, 8, 1), 1.0)

    def test_k_equals_n_is_any_passed(self):
        for n in (1, 2, 8):
            for c in range(n + 1):
                self.assertEqual(b0.pass_at_k(n, c, n), 1.0 if c > 0 else 0.0)

    def test_pass_at_one_is_fraction(self):
        self.assertAlmostEqual(b0.pass_at_k(8, 2, 1), 0.25)

    def test_known_value(self):
        self.assertAlmostEqual(b0.pass_at_k(4, 1, 2), 1 - math.comb(3, 2) / math.comb(4, 2))
        self.assertAlmostEqual(b0.pass_at_k(4, 1, 2), 0.5)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            b0.pass_at_k(2, 3, 1)
        with self.assertRaises(ValueError):
            b0.pass_at_k(2, 1, 3)
        with self.assertRaises(ValueError):
            b0.pass_at_k(2, 1, 0)


class PromptTest(unittest.TestCase):
    def test_split_file(self):
        header, footer = b0.split_lean_file(FILE_TEXT)
        self.assertEqual(header, HEADER)
        self.assertEqual(footer, "end MathesisPilot")

    def test_split_requires_by(self):
        with self.assertRaises(ValueError):
            b0.split_lean_file("theorem t : True := trivial\n")

    def test_prompt_template(self):
        prompt = b0.build_prompt(HEADER)
        self.assertEqual(
            prompt,
            "Complete the following Lean 4 code:\n\n```lean4\n" + HEADER + "\n```\n",
        )
        self.assertTrue(prompt.rstrip().endswith("```"))
        self.assertIn(":= by\n```", prompt)

    def test_eval_header_prepended_once(self):
        bare = HEADER[len("import Mathlib\n"):]
        self.assertEqual(b0.EVAL_HEADER, "import Mathlib\n")
        self.assertIn("```lean4\nimport Mathlib\nnamespace", b0.build_prompt(bare))
        self.assertEqual(b0.build_prompt(bare), b0.build_prompt(HEADER))
        for header in (bare, HEADER):
            text = b0.build_candidate(header, "\n  omega", "end MathesisPilot")
            self.assertTrue(text.startswith(b0.EVAL_HEADER))
            self.assertEqual(text.splitlines().count("import Mathlib"), 1)

    def test_eval_header_keeps_benchmark_imports(self):
        header = "import Mathesis.Defs\nnamespace X\ntheorem t : True := by"
        text = b0.build_candidate(header, "\n  trivial", "end X")
        self.assertTrue(text.startswith("import Mathlib\nimport Mathesis.Defs\n"))

    def test_all_benchmark_files_parse(self):
        problems = b0.load_b0_problems()
        self.assertEqual(len(problems), 50)
        for prob in problems:
            self.assertTrue(prob["header"].endswith(":= by"), prob["name"])
            self.assertIn(prob["name"], prob["header"])
            self.assertTrue(prob["footer"].startswith("end "), prob["name"])
            self.assertNotIn("sorry", b0.build_prompt(prob["header"]))


class ExtractProofTest(unittest.TestCase):
    def test_full_restatement(self):
        response = (
            "Here is the proof.\n```lean4\nimport Mathlib\nnamespace MathesisPilot\n"
            "theorem lean_x : ∀ (a b : Nat),\n    a + b = b + a := by\n"
            "  intro a b\n  omega\nend MathesisPilot\n```\n"
        )
        proof, reason = b0.extract_proof(response, HEADER)
        self.assertEqual(reason, "")
        self.assertEqual(proof, "\n  intro a b\n  omega")
        text = b0.build_candidate(HEADER, proof, "end MathesisPilot")
        self.assertEqual(
            text, HEADER + "\n  intro a b\n  omega\nend MathesisPilot\n"
        )

    def test_body_only_block_is_indented(self):
        proof, reason = b0.extract_proof("```lean4\nintro a b\nomega\n```", HEADER)
        self.assertEqual(reason, "")
        self.assertEqual(proof, "\n  intro a b\n  omega")

    def test_changed_statement_rejected(self):
        response = (
            "```lean4\ntheorem lean_x : ∀ (a b : Nat), a + b = a + b := by\n  rfl\n```"
        )
        proof, reason = b0.extract_proof(response, HEADER)
        self.assertIsNone(proof)
        self.assertEqual(reason, "statement_mismatch")

    def test_renamed_theorem_rejected(self):
        response = "```lean4\ntheorem other : True := by\n  trivial\n```"
        self.assertEqual(b0.extract_proof(response, HEADER)[1], "statement_mismatch")

    def test_no_block_and_empty(self):
        self.assertEqual(b0.extract_proof("no code here", HEADER)[1], "no_code_block")
        response = "```lean4\ntheorem lean_x : ∀ (a b : Nat), a + b = b + a := by\n```"
        self.assertEqual(b0.extract_proof(response, HEADER)[1], "empty_proof")

    def test_term_mode_rejected(self):
        response = (
            "```lean4\ntheorem lean_x : ∀ (a b : Nat), a + b = b + a :=\n"
            "  fun a b => Nat.add_comm a b\n```"
        )
        self.assertEqual(b0.extract_proof(response, HEADER)[1], "not_tactic_proof")

    def test_unterminated_block_is_kept(self):
        response = "```lean4\ntheorem lean_x : ∀ (a b : Nat), a + b = b + a := by\n  intro a"
        proof, reason = b0.extract_proof(response, HEADER)
        self.assertEqual((proof, reason), ("\n  intro a", ""))

    def test_inline_proof_gets_space(self):
        text = b0.build_candidate(HEADER, "simp", "")
        self.assertTrue(text.endswith(":= by simp\n"))


class JudgeTest(unittest.TestCase):
    PROOF = "\n  intro a\n  exact foo"

    def test_pass(self):
        self.assertEqual(b0.judge(self.PROOF, 0, "x: warning: hi"), (True, "ok", ""))

    def test_sorry_and_admit_rejected_even_when_lean_exits_zero(self):
        out = "f.lean:3:8: warning: declaration uses 'sorry'"
        for word in ("sorry", "admit"):
            passed, cls, line = b0.judge("\n  " + word, 0, "")
            self.assertFalse(passed)
            self.assertEqual(cls, "forbidden_token")
        passed, cls, _ = b0.judge("\n  skip", 0, out)
        self.assertFalse(passed)
        self.assertEqual(cls, "forbidden_token")

    def test_axiom_rejected(self):
        self.assertFalse(b0.judge("\n  exact ax\naxiom ax : False", 0, "")[0])

    def test_word_boundary(self):
        self.assertTrue(b0.judge("\n  exact sorryless_lemma", 0, "")[0])

    def test_error_in_output(self):
        passed, cls, line = b0.judge(self.PROOF, 0, "a.lean:4:2: error: unknown identifier")
        self.assertFalse(passed)
        self.assertEqual(cls, "lean_error")
        self.assertIn("unknown identifier", line)

    def test_nonzero_exit(self):
        self.assertEqual(b0.judge(self.PROOF, 1, "")[:2], (False, "lean_error"))

    def test_timeout(self):
        self.assertEqual(b0.judge(self.PROOF, -1, "", timed_out=True)[:2], (False, "timeout"))


class CommandTest(unittest.TestCase):
    def test_verify_command(self):
        self.assertEqual(
            b0.lean_verify_command(Path("/tmp/x.lean")),
            ["lake", "env", "lean", str(Path("/tmp/x.lean").resolve())],
        )

    def test_lean_dir(self):
        self.assertEqual(b0.default_lean_dir().name, "lean")
        self.assertTrue((b0.default_lean_dir() / "lakefile.lean").is_file())


class SummaryTest(unittest.TestCase):
    def test_summary(self):
        per = {
            "a": {"n": 2, "c": 1, "pass_at_1": 0.5, "pass_at_k": 1.0},
            "b": {"n": 2, "c": 0, "pass_at_1": 0.0, "pass_at_k": 0.0},
        }
        s = b0.summarize_b0(per, 2)
        self.assertEqual(s["n_problems"], 2)
        self.assertAlmostEqual(s["pass_at_1"], 0.25)
        self.assertAlmostEqual(s["pass_at_k"], 0.5)

    def test_derived_seed_stable(self):
        self.assertEqual(b0.derived_b0_seed(0, "p"), b0.derived_b0_seed(0, "p"))
        self.assertNotEqual(b0.derived_b0_seed(0, "p"), b0.derived_b0_seed(0, "q"))
        self.assertLess(b0.derived_b0_seed(0, "p"), 1 << 63)

    def test_no_mlx_import_at_module_level(self):
        source = Path(b0.__file__).read_text(encoding="utf-8")
        for line in source.splitlines():
            if line.startswith(("import mlx", "from mlx")):
                self.fail("module-level mlx import: " + line)


if __name__ == "__main__":
    unittest.main()


class LeanVerifyCommandTest(unittest.TestCase):
    def test_candidate_path_is_absolute_for_relative_input(self):
        from pathlib import Path

        cmd = b0.lean_verify_command("runs/x/candidates/a.lean")
        self.assertEqual(cmd[:3], ["lake", "env", "lean"])
        self.assertTrue(Path(cmd[3]).is_absolute())
