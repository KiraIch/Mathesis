import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "extract_hints.py"
_spec = importlib.util.spec_from_file_location("extract_hints", SCRIPT)
eh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eh)


class ExtractHavesTest(unittest.TestCase):
    def test_named_have_forms(self):
        proof = [
            "have h1 : 0 ≤ a ^ 2 := sq_nonneg a",
            "have h2 : x = y := by",
            "  have h3 : x ≠ 0 := hx.ne'",
            "· have k : ∀ x y : ℝ, 0 < x → y ≤ x := by",
        ]
        n_have, statements = eh.extract_have_statements(proof)
        self.assertEqual(n_have, 4)
        self.assertEqual(
            statements,
            [
                ("h1", "0 ≤ a ^ 2"),
                ("h2", "x = y"),
                ("h3", "x ≠ 0"),
                ("k", "∀ x y : ℝ, 0 < x → y ≤ x"),
            ],
        )

    def test_anonymous_have_is_this(self):
        n_have, statements = eh.extract_have_statements(["have : 0 ≤ a := by positivity"])
        self.assertEqual(n_have, 1)
        self.assertEqual(statements, [("this", "0 ≤ a")])

    def test_untyped_have_counts_but_gives_no_hint(self):
        proof = ["have h := sq_nonneg (a - b)", "have := foo", "exact h"]
        n_have, statements = eh.extract_have_statements(proof)
        self.assertEqual(n_have, 2)
        self.assertEqual(statements, [])

    def test_no_have_returns_empty(self):
        n_have, statements = eh.extract_have_statements(["intro P", "intro h", "exact h"])
        self.assertEqual(n_have, 0)
        self.assertEqual(statements, [])

    def test_proof_body_is_excluded(self):
        proof = ["have hq : 0 ≤ a ^ 2 + b := by nlinarith [sq_nonneg (a + b), sq_nonneg a]"]
        _, statements = eh.extract_have_statements(proof)
        self.assertEqual(statements, [("hq", "0 ≤ a ^ 2 + b")])
        self.assertNotIn(":=", statements[0][1])
        self.assertNotIn("nlinarith", statements[0][1])

    def test_multiline_statement_joined_until_assign(self):
        proof = [
            "have h : 0 ≤",
            "    (a - b) ^ 2 := sq_nonneg (a - b)",
            "exact h",
        ]
        n_have, statements = eh.extract_have_statements(proof)
        self.assertEqual(n_have, 1)
        self.assertEqual(statements, [("h", "0 ≤ (a - b) ^ 2")])

    def test_unterminated_have_gives_no_hint(self):
        proof = ["have h : 0 ≤ a", "  exact foo"]
        n_have, statements = eh.extract_have_statements(proof)
        self.assertEqual(n_have, 1)
        self.assertEqual(statements, [])


class ExtractProblemTest(unittest.TestCase):
    def _entry(self, auxiliary, insight=True, proof=None):
        return {
            "name": "p",
            "insight": insight,
            "auxiliary": auxiliary,
            "reference_proof": proof
            or ["have h : 0 ≤ a ^ 2 := sq_nonneg a", "exact h"],
        }

    def test_hint_string_and_auxiliary_match(self):
        row = eh.extract_problem(self._entry("0 ≤  a ^ 2"))
        self.assertEqual(row["hints"], ["h : 0 ≤ a ^ 2"])
        self.assertTrue(row["auxiliary_matches_have"])
        self.assertEqual(row["current_auxiliary"], "0 ≤  a ^ 2")
        self.assertEqual(row["n_have"], 1)

    def test_prose_auxiliary_does_not_match(self):
        row = eh.extract_problem(self._entry("nonnegative square"))
        self.assertFalse(row["auxiliary_matches_have"])

    def test_empty_auxiliary_does_not_match(self):
        row = eh.extract_problem(self._entry(""))
        self.assertFalse(row["auxiliary_matches_have"])

    def test_summary_counts(self):
        rows = [
            eh.extract_problem(self._entry("0 ≤ a ^ 2")),
            eh.extract_problem(self._entry("prose", insight=True)),
            eh.extract_problem(self._entry("", insight=False, proof=["intro h", "exact h"])),
            eh.extract_problem(self._entry("", insight=False)),
        ]
        summary = eh.summarize(rows)
        self.assertEqual(summary["n_problems"], 4)
        self.assertEqual(summary["n_insight"], 2)
        self.assertEqual(summary["n_routine"], 2)
        self.assertEqual(summary["routine_with_have"], 1)
        self.assertEqual(summary["insight_auxiliary_matches_have"], 1)
        self.assertEqual(summary["insight_auxiliary_match_ratio"], 0.5)

    def test_main_writes_json(self):
        problems = {
            "problems": [
                self._entry("0 ≤ a ^ 2"),
                self._entry("", insight=False, proof=["exact h"]),
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            bench = Path(tmp) / "bench"
            bench_dir = bench / "benchmark" / "toy"
            bench_dir.mkdir(parents=True)
            (bench_dir / "problems.json").write_text(json.dumps(problems), encoding="utf-8")
            out = Path(tmp) / "out" / "hints.json"
            original_root = eh.ROOT
            eh.ROOT = bench
            try:
                self.assertEqual(eh.main(["toy", "--out", str(out)]), 0)
            finally:
                eh.ROOT = original_root
            report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(report["summary"]["n_problems"], 2)
        self.assertEqual(report["problems"][0]["hints"], ["h : 0 ≤ a ^ 2"])
        self.assertEqual(report["problems"][1]["n_have"], 0)


class FirstHaveHintFileTest(unittest.TestCase):
    def test_first_have_only_and_problems_without_have_skipped(self):
        report = {"source": "src", "problems": [
            {"name": "a", "hints": ["h1 : x = 1", "h2 : y = 2"]},
            {"name": "b", "hints": []},
            {"name": "c", "hints": ["k : True"]},
            {"name": "d", "hints": ["r : False"], "retired": "ceiling"},
        ]}
        out = eh.first_have_hint_file(report)
        self.assertEqual(out["hints"], {"a": "h1 : x = 1", "c": "k : True"})
        self.assertEqual(out["rule"], eh.FIRST_HAVE_RULE)
        self.assertEqual(out["source"], "src")

    def test_cli_writes_hint_file_loadable_by_hint_gap(self):
        from mathesis import cli
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "hints.json"
            with open(Path(tmp) / "report.json", "w", encoding="utf-8") as fh:
                import contextlib
                with contextlib.redirect_stdout(fh):
                    self.assertEqual(eh.main(["lean_hard", "--first-have-hints", str(path)]), 0)
            loaded = cli.load_hint_file(path)
            report = json.loads((Path(tmp) / "report.json").read_text("utf-8"))
        expected = {
            r["name"]: r["hints"][0]
            for r in report["problems"]
            if r["hints"] and not r.get("retired")
        }
        self.assertTrue(any(r.get("retired") and r["hints"] for r in report["problems"]))
        self.assertEqual(loaded["hints"], expected)
        self.assertEqual(loaded["rule"], eh.FIRST_HAVE_RULE)


if __name__ == "__main__":
    unittest.main()
