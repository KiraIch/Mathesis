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


class HintGapTest(unittest.TestCase):
    def test_hinted_prompt_names_hint_and_keeps_header(self):
        prompt = b0.build_hinted_prompt(HEADER, "the (a-b)^2 cross terms")
        self.assertIn("the (a-b)^2 cross terms", prompt)
        self.assertIn("theorem lean_x", prompt)
        self.assertNotIn("auxiliary step", b0.build_prompt(HEADER))

    def test_plain_prompt_unchanged(self):
        expected = b0.PROMPT_TEMPLATE.format(header=b0.with_eval_header(HEADER))
        self.assertEqual(b0.build_prompt(HEADER), expected)

    def test_targets_are_insight_problems_with_auxiliary(self):
        problems = [
            {"name": "i1", "insight": True, "auxiliary": "x"},
            {"name": "i2", "insight": True, "auxiliary": ""},
            {"name": "r1", "insight": False, "auxiliary": "x"},
            {"name": "i3", "insight": True, "auxiliary": "y"},
        ]
        names = [p["name"] for p in b0.select_hint_gap_problems(problems)]
        self.assertEqual(names, ["i1", "i3"])
        limited = b0.select_hint_gap_problems(problems, limit=1)
        self.assertEqual([p["name"] for p in limited], ["i1"])

    def test_names_restrict_targets_and_reject_non_targets(self):
        problems = [
            {"name": "i1", "insight": True, "auxiliary": "x"},
            {"name": "i2", "insight": True, "auxiliary": "y"},
            {"name": "r1", "insight": False, "auxiliary": ""},
        ]
        picked = b0.select_hint_gap_problems(problems, names=["i2"])
        self.assertEqual([p["name"] for p in picked], ["i2"])
        with self.assertRaises(ValueError):
            b0.select_hint_gap_problems(problems, names=["r1"])

    def test_gap_is_difference_of_pass_at_1(self):
        pairs = {
            "a": {"plain": b0._problem_stats(8, 2, 8), "hint": b0._problem_stats(8, 6, 8)},
            "b": {"plain": b0._problem_stats(8, 4, 8), "hint": b0._problem_stats(8, 4, 8)},
        }
        s = b0.summarize_hint_gap(pairs, 8, resamples=500)
        self.assertAlmostEqual(s["per_problem"]["a"]["gap"], 0.5)
        self.assertAlmostEqual(s["per_problem"]["b"]["gap"], 0.0)
        self.assertAlmostEqual(s["mean_gap"], 0.25)
        low, high = s["ci95"]
        self.assertLessEqual(low, s["mean_gap"])
        self.assertGreaterEqual(high, s["mean_gap"])

    def test_bootstrap_is_deterministic(self):
        pairs = {
            "a": {"plain": b0._problem_stats(8, 2, 8), "hint": b0._problem_stats(8, 5, 8)},
            "b": {"plain": b0._problem_stats(8, 3, 8), "hint": b0._problem_stats(8, 1, 8)},
        }
        first = b0.summarize_hint_gap(pairs, 8, resamples=200)["ci95"]
        second = b0.summarize_hint_gap(pairs, 8, resamples=200)["ci95"]
        self.assertEqual(first, second)

    def test_empty_summary_is_undefined(self):
        s = b0.summarize_hint_gap({}, 8)
        self.assertEqual(s["n_problems"], 0)
        self.assertIsNone(s["mean_gap"])
        self.assertIn("not defined", b0.format_hint_gap_summary(s))


if __name__ == "__main__":
    unittest.main()


class LeanVerifyCommandTest(unittest.TestCase):
    def test_candidate_path_is_absolute_for_relative_input(self):
        from pathlib import Path

        cmd = b0.lean_verify_command("runs/x/candidates/a.lean")
        self.assertEqual(cmd[:3], ["lake", "env", "lean"])
        self.assertTrue(Path(cmd[3]).is_absolute())


class FakeGenConfig:
    def __init__(self, eos):
        self.eos_token_id = eos


class FakeModel:
    def __init__(self, eos):
        self.generation_config = FakeGenConfig(eos)


class FakeTokenizer:
    def __init__(self, eos):
        self.eos_token_id = eos


class BackendSelectionTest(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(b0.DEFAULT_BACKEND, "transformers")
        self.assertEqual(b0.BACKENDS, ("transformers", "mlx"))
        self.assertEqual(b0.default_model_name(), "deepseek-ai/DeepSeek-Prover-V2-7B")
        self.assertEqual(b0.default_model_name("transformers"), b0.TRANSFORMERS_MODEL_NAME)
        self.assertEqual(
            b0.default_model_name("mlx"), "mlx-community/DeepSeek-Prover-V2-7B-4bit"
        )

    def test_unknown_backend_rejected(self):
        for call in (
            lambda: b0.check_backend("cuda"),
            lambda: b0.default_model_name("cuda"),
            lambda: b0.load_model("x", backend="cuda"),
            lambda: b0.generate_samples(None, None, [1], 1, 1, 0.6, 0, backend="cuda"),
        ):
            with self.assertRaises(ValueError):
                call()

    def test_generate_samples_dispatch(self):
        from unittest import mock

        with mock.patch.object(b0, "_generate_samples_mlx", return_value="mlx") as m, \
                mock.patch.object(b0, "_generate_samples_transformers", return_value="hf") as t:
            args = ("model", "tok", [1, 2], 3, 16, 0.6, 7)
            self.assertEqual(b0.generate_samples(*args, backend="mlx"), "mlx")
            self.assertEqual(b0.generate_samples(*args), "hf")
            self.assertEqual(b0.generate_samples(*args, backend="transformers"), "hf")
            m.assert_called_once_with(*args)
            self.assertEqual(t.call_count, 2)

    def test_load_model_dispatch_and_default_name(self):
        from unittest import mock

        with mock.patch.object(b0, "_load_transformers", return_value=("m", "t")) as hf:
            self.assertEqual(b0.load_model(), ("m", "t"))
            hf.assert_called_once_with(b0.TRANSFORMERS_MODEL_NAME)
            hf.reset_mock()
            b0.load_model("custom/name", backend="transformers")
            hf.assert_called_once_with("custom/name")

    def test_no_torch_or_transformers_import_at_module_level(self):
        source = Path(b0.__file__).read_text(encoding="utf-8")
        for line in source.splitlines():
            if line.startswith(("import torch", "from torch", "import transformers", "from transformers")):
                self.fail("module-level import: " + line)


class NewTokenSequencesTest(unittest.TestCase):
    def test_strips_prompt_and_cuts_at_eos(self):
        rows = [[10, 11, 5, 6, 99, 0, 0], [10, 11, 7, 8, 9, 4, 3]]
        self.assertEqual(
            b0.new_token_sequences(rows, 2, [99]), [[5, 6], [7, 8, 9, 4, 3]]
        )

    def test_immediate_eos_gives_empty_completion(self):
        self.assertEqual(b0.new_token_sequences([[1, 99, 0]], 1, [99]), [[]])

    def test_multiple_stop_ids_and_empty_input(self):
        self.assertEqual(b0.new_token_sequences([[1, 5, 98, 6]], 1, [99, 98]), [[5]])
        self.assertEqual(b0.new_token_sequences([], 3, [99]), [])

    def test_eos_ids_from_model_and_tokenizer(self):
        self.assertEqual(b0._eos_ids(FakeTokenizer(100001), FakeModel(100001)), [100001])
        self.assertEqual(b0._eos_ids(FakeTokenizer(2), FakeModel([5, 2])), [2, 5])
        self.assertEqual(b0._eos_ids(FakeTokenizer(7), object()), [7])
        self.assertEqual(b0._eos_ids(FakeTokenizer(None), FakeModel(None)), [])


class CliBackendTest(unittest.TestCase):
    def test_parser_default_and_choices(self):
        import contextlib
        import io
        from unittest import mock

        from mathesis import cli

        seen = {}

        def fake_b0(*args, **kwargs):
            seen["b0"] = args
            return 0

        def fake_hg(*args, **kwargs):
            seen["hg"] = args
            return 0

        with mock.patch.object(cli, "run_b0_command", fake_b0), \
                mock.patch.object(cli, "run_hint_gap_command", fake_hg):
            self.assertEqual(cli.main(["b0"]), 0)
            self.assertEqual(seen["b0"][-1], "transformers")
            self.assertEqual(cli.main(["b0", "--backend", "mlx"]), 0)
            self.assertEqual(seen["b0"][-1], "mlx")
            self.assertEqual(cli.main(["hint-gap"]), 0)
            self.assertEqual(seen["hg"][-1], "transformers")
            self.assertEqual(cli.main(["hint-gap", "--backend", "mlx"]), 0)
            self.assertEqual(seen["hg"][-1], "mlx")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                cli.main(["b0", "--backend", "cuda"])

    def test_b0_command_passes_backend_and_model(self):
        import contextlib
        import io
        import tempfile
        from unittest import mock

        from mathesis import cli

        for backend, model in (("transformers", b0.TRANSFORMERS_MODEL_NAME),
                               ("mlx", b0.MLX_MODEL_NAME)):
            with tempfile.TemporaryDirectory() as out, \
                    mock.patch.object(b0, "run_b0", return_value={"ok": 1}) as run, \
                    mock.patch.object(b0, "format_b0_summary", return_value=""), \
                    contextlib.redirect_stdout(io.StringIO()) as buf:
                code = cli.run_b0_command(1, 1, 8, out=out, backend=backend)
            self.assertEqual(code, 0)
            self.assertEqual(run.call_args.kwargs["backend"], backend)
            self.assertIn(model, buf.getvalue())
