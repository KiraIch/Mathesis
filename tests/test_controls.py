import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from mathesis import llm_baseline as b0

# Every test patches verify_proof, so no Lean process is started.

REFERENCE_TACTIC = "exact foo_reference_tactic"


def _problems(names=None, extra=()):
    names = b0.CONTROL_PROBLEMS if names is None else names
    problems = [
        {
            "name": n,
            "header": "import Mathlib\n",
            "footer": "end\n",
            "reference_proof": [REFERENCE_TACTIC],
            "auxiliary": "",
            "insight": False,
        }
        for n in names
    ]
    for n in extra:
        problems.append(dict(problems[0], name=n))
    return problems


def _default_fields(stem):
    """Lean outcome for a candidate file stem, as a healthy run would produce it."""
    if stem.endswith("_reference"):
        return dict(passed=True, failure_class="ok", first_error_line="", returncode=0)
    for label, _proof, want_class in b0.NEGATIVE_PROOFS:
        if stem.endswith("_" + label):
            if want_class == "forbidden_token":
                return dict(passed=False, failure_class="forbidden_token",
                            first_error_line="forbidden token: " + label, returncode=0)
            return dict(passed=False, failure_class="lean_error",
                        first_error_line="x.lean:4:3: error: unknown tactic", returncode=1)
    raise AssertionError("unexpected candidate file: " + stem)


class FakeVerifyProof:
    """Stands in for b0.verify_proof. `overrides` maps a candidate stem to Verification fields."""

    def __init__(self, overrides=None, raise_exc=None):
        self.overrides = overrides or {}
        self.raise_exc = raise_exc
        self.calls = []  # (stem, proof, path)

    def __call__(self, header, proof, footer, path, lean_dir=None, timeout=None):
        stem = Path(path).name[: -len(".lean")]
        self.calls.append((stem, proof, Path(path)))
        if self.raise_exc is not None:
            raise self.raise_exc
        fields = _default_fields(stem)
        fields.update(self.overrides.get(stem, {}))
        return b0.Verification(
            seconds=0.0, output="", lean_returncode=None, forbidden_source=None, **fields
        )


class ControlsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run = SimpleNamespace(path=Path(tmp.name))

    def _run(self, overrides=None, problems=None, raise_exc=None):
        fake = FakeVerifyProof(overrides, raise_exc=raise_exc)
        with mock.patch.object(b0, "verify_proof", fake):
            report = b0.run_controls(self.run, problems if problems is not None else _problems())
        return report, fake

    def _row(self, report, key, problem, variant=None):
        rows = [
            r for r in report[key]["results"]
            if r["problem"] == problem and r.get("variant") == variant
        ]
        self.assertEqual(len(rows), 1, (key, problem, variant))
        return rows[0]

    # ---- normal path and C1 / C2 verdicts

    def test_all_controls_pass(self):
        report, fake = self._run()
        self.assertTrue(report["C1"]["ok"])
        self.assertTrue(report["C2"]["ok"])
        self.assertTrue(report["ok"])
        self.assertEqual(len(report["C1"]["results"]), 3)
        self.assertEqual(len(report["C2"]["results"]), 9)  # 3 problems x 3 negative proofs
        self.assertEqual(len(fake.calls), 12)
        for row in report["C1"]["results"]:
            self.assertIs(row["passed"], True)
            self.assertTrue(row["ok"])

    def test_one_reference_failure_fails_c1_and_report(self):
        overrides = {"lean_sq_nonneg_reference": dict(
            passed=False, failure_class="lean_error", first_error_line="bad", returncode=1)}
        report, _ = self._run(overrides)
        self.assertFalse(report["C1"]["ok"])
        self.assertFalse(report["ok"])
        self.assertTrue(report["C2"]["ok"])  # C2 is still evaluated and unaffected
        bad = self._row(report, "C1", "lean_sq_nonneg")
        self.assertIs(bad["passed"], False)
        self.assertIs(bad["expected"], True)
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["first_error_line"], "bad")
        for name in ("lean_nat_add_comm", "lean_poly_lower"):
            self.assertTrue(self._row(report, "C1", name)["ok"])

    def test_all_references_fail_still_reports_fail(self):
        overrides = {n + "_reference": dict(passed=False, failure_class="lean_error", returncode=1)
                     for n in b0.CONTROL_PROBLEMS}
        report, _ = self._run(overrides)
        self.assertFalse(report["C1"]["ok"])
        self.assertFalse(report["ok"])
        self.assertTrue(all(not r["ok"] for r in report["C1"]["results"]))

    def test_c2_wrong_failure_class_fails(self):
        overrides = {"lean_nat_add_comm_sorry": dict(
            passed=False, failure_class="lean_error", first_error_line="lean said no",
            returncode=1)}
        report, _ = self._run(overrides)
        self.assertFalse(report["C2"]["ok"])
        self.assertFalse(report["ok"])
        row = self._row(report, "C2", "lean_nat_add_comm", "sorry")
        self.assertEqual(row["failure_class"], "lean_error")
        self.assertEqual(row["expected_class"], "forbidden_token")
        self.assertFalse(row["ok"])
        self.assertTrue(report["C1"]["ok"])

    def test_c2_negative_proof_that_passes_fails(self):
        overrides = {"lean_poly_lower_admit": dict(
            passed=True, failure_class="ok", first_error_line="", returncode=0)}
        report, _ = self._run(overrides)
        self.assertFalse(report["C2"]["ok"])
        self.assertFalse(report["ok"])
        row = self._row(report, "C2", "lean_poly_lower", "admit")
        self.assertIs(row["passed"], True)
        self.assertFalse(row["ok"])

    def test_invalid_tactic_expected_lean_error_is_recorded(self):
        report, _ = self._run()
        row = self._row(report, "C2", "lean_sq_nonneg", "invalid_tactic")
        self.assertEqual(row["expected_class"], "lean_error")
        self.assertEqual(row["failure_class"], "lean_error")
        self.assertEqual(row["lean_returncode"], 1)
        self.assertTrue(row["ok"])
        self.assertNotIn("lean_alone_would_pass", row)

    def test_forbidden_token_rows_record_lean_alone_would_pass(self):
        report, _ = self._run()
        for variant in ("sorry", "admit"):
            row = self._row(report, "C2", "lean_nat_add_comm", variant)
            self.assertEqual(row["lean_returncode"], 0)
            self.assertIs(row["lean_alone_would_pass"], True)

    def test_only_control_problems_are_verified(self):
        problems = _problems(extra=("lean_not_a_control",))
        report, fake = self._run(problems=problems)
        self.assertTrue(report["ok"])
        names = {r["problem"] for key in ("C1", "C2") for r in report[key]["results"]}
        self.assertEqual(names, set(b0.CONTROL_PROBLEMS))
        self.assertFalse(any("lean_not_a_control" in stem for stem, _, _ in fake.calls))

    def test_candidate_proof_text_and_paths(self):
        _, fake = self._run()
        by_stem = {stem: (proof, path) for stem, proof, path in fake.calls}
        self.assertEqual(by_stem["lean_nat_add_comm_reference"][0],
                         "\n  " + REFERENCE_TACTIC)
        self.assertEqual(by_stem["lean_nat_add_comm_sorry"][0], "\n  sorry")
        self.assertEqual(by_stem["lean_nat_add_comm_invalid_tactic"][0],
                         "\n  this_is_not_a_tactic_xyz")
        for stem, (_, path) in by_stem.items():
            self.assertEqual(path, self.run.path / "control_candidates" / (stem + ".lean"))

    # ---- error paths

    def test_missing_control_problem_raises_value_error(self):
        problems = _problems(names=[n for n in b0.CONTROL_PROBLEMS if n != "lean_poly_lower"])
        fake = FakeVerifyProof()
        with mock.patch.object(b0, "verify_proof", fake):
            with self.assertRaises(ValueError) as cm:
                b0.run_controls(self.run, problems)
        self.assertIn("lean_poly_lower", str(cm.exception))
        self.assertEqual(fake.calls, [])  # fails before any candidate is verified

    def test_empty_problem_list_raises_value_error(self):
        with self.assertRaises(ValueError) as cm:
            self._run(problems=[])
        for name in b0.CONTROL_PROBLEMS:
            self.assertIn(name, str(cm.exception))

    def test_environment_failure_propagates_not_recorded_as_fail(self):
        # An environment problem must stop the run, not turn into a silent C1/C2 FAIL row.
        with self.assertRaises(b0.EnvironmentFailure):
            self._run(raise_exc=b0.EnvironmentFailure("lean missing"))

    # ---- format_controls

    def test_format_controls_all_pass(self):
        report, _ = self._run()
        text = b0.format_controls(report)
        lines = text.splitlines()
        self.assertEqual(lines[0], "C1 (reference proofs must pass): PASS")
        self.assertIn("C2 (wrong proofs must fail): PASS", lines)
        self.assertEqual(lines[-1], "controls: PASS")
        self.assertIn("  lean_nat_add_comm | passed=True | class=ok | ok", lines)
        self.assertIn("  lean_nat_add_comm / sorry | passed=False | class=forbidden_token | ok"
                      " | forbidden token: sorry", lines)
        self.assertNotIn("UNEXPECTED", text)
        self.assertEqual(len(lines), 1 + 3 + 1 + 9 + 1)

    def test_format_controls_reports_fail_and_unexpected_rows(self):
        overrides = {
            "lean_sq_nonneg_reference": dict(
                passed=False, failure_class="lean_error", first_error_line="bad ref",
                returncode=1),
            "lean_poly_lower_admit": dict(passed=True, failure_class="ok", returncode=0,
                                          first_error_line=""),
        }
        report, _ = self._run(overrides)
        text = b0.format_controls(report)
        lines = text.splitlines()
        self.assertIn("C1 (reference proofs must pass): FAIL", lines)
        self.assertIn("C2 (wrong proofs must fail): FAIL", lines)
        self.assertEqual(lines[-1], "controls: FAIL")
        self.assertIn("  lean_sq_nonneg | passed=False | class=lean_error | UNEXPECTED | bad ref",
                      lines)
        self.assertIn("  lean_poly_lower / admit | passed=True | class=ok | UNEXPECTED", lines)

    def test_format_controls_truncates_first_error_line_to_100_chars(self):
        overrides = {"lean_sq_nonneg_reference": dict(
            passed=False, failure_class="lean_error", first_error_line="E" * 300, returncode=1)}
        report, _ = self._run(overrides)
        text = b0.format_controls(report)
        self.assertIn("E" * 100, text)
        self.assertNotIn("E" * 101, text)

    def test_format_controls_no_trailing_separator_when_no_error_line(self):
        report, _ = self._run()
        c1_rows = [line for line in b0.format_controls(report).splitlines()
                   if line.startswith("  lean_") and " / " not in line]
        self.assertEqual(len(c1_rows), 3)
        for line in c1_rows:
            self.assertTrue(line.endswith("| ok"), line)


if __name__ == "__main__":
    unittest.main()
