"""Unit and integration tests for scripts/replay_verify.py."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import scripts.replay_verify as rv
from mathesis import llm_baseline


def _create_mock_run(
    base_dir: Path,
    manifest_overrides: dict | None = None,
    results_rows: list[dict] | None = None,
    responses: dict[str, str] | None = None,
    summary_data: dict | None = None,
) -> Path:
    run_dir = base_dir / "mock_run"
    run_dir.mkdir(parents=True, exist_ok=True)
    responses_dir = run_dir / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "lean_toolchain": "leanprover/lean4:v4.35.0",
        "mathlib_rev": "56a005855ea17e0b0958f73ec801ae140b0a1679",
        "args": {},
    }
    if manifest_overrides:
        manifest.update(manifest_overrides)
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    if results_rows is None:
        results_rows = [
            {
                "problem": "lean_ineq_amgm3",
                "sample_index": 0,
                "passed": True,
                "failure_class": "ok",
                "first_error_line": "",
                "judge_version": "v2",
                "lean_returncode": 0,
            },
            {
                "problem": "lean_ineq_amgm3",
                "sample_index": 1,
                "passed": True,
                "failure_class": "ok",
                "first_error_line": "",
                "judge_version": "v2",
                "lean_returncode": 0,
            },
            {
                "problem": "lean_nat_sum_even",
                "sample_index": 0,
                "passed": False,
                "failure_class": "lean_error",
                "first_error_line": "error: unsolved goals",
                "judge_version": "v2",
                "lean_returncode": 1,
            },
        ]
    lines = [json.dumps(r) for r in results_rows]
    (run_dir / "results.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if responses is None:
        resp_amgm3 = (
            "```lean4\n"
            "theorem lean_ineq_amgm3 : ∀ a b c : ℝ, 0 ≤ a → 0 ≤ b → 0 ≤ c → 27 * (a * b * c) ≤ (a + b + c) ^ 3 := by\n"
            "  intro a b c h0 h1 h2\n"
            "```\n"
        )
        resp_nat_sum = (
            "```lean4\n"
            "theorem lean_nat_sum_even : ∀ n : ℕ, 2 ∣ ∑ i ∈ Finset.range n, i * (i + 1) := by\n"
            "  sorry\n"
            "```\n"
        )
        responses = {
            "lean_ineq_amgm3_0.txt": resp_amgm3,
            "lean_ineq_amgm3_1.txt": resp_amgm3,
            "lean_nat_sum_even_0.txt": resp_nat_sum,
        }
    for filename, content in responses.items():
        (responses_dir / filename).write_text(content, encoding="utf-8")

    if summary_data is None:
        summary_data = {
            "status": "ok",
            "summary": {
                "per_problem": {
                    "lean_ineq_amgm3": {"c": 2, "n": 2, "pass_at_1": 1.0, "pass_at_k": 1.0},
                    "lean_nat_sum_even": {"c": 0, "n": 1, "pass_at_1": 0.0, "pass_at_k": 0.0},
                }
            },
        }
    (run_dir / "summary.json").write_text(
        json.dumps(summary_data, indent=2) + "\n", encoding="utf-8"
    )

    return run_dir


class TestReplayVerify(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)
        self.bench_dir = Path("benchmark/lean_hard")

    def _fake_verify(self, header, proof, footer, path, lean_dir=None, timeout=None):
        stem = Path(path).stem
        if "lean_ineq_amgm3" in stem:
            return llm_baseline.Verification(
                passed=True,
                failure_class="ok",
                first_error_line="",
                seconds=0.01,
                returncode=0,
                output="",
                lean_returncode=0,
                forbidden_source=None,
            )
        return llm_baseline.Verification(
            passed=False,
            failure_class="lean_error",
            first_error_line="error: unsolved goals",
            seconds=0.01,
            returncode=1,
            output="error: unsolved goals\n",
            lean_returncode=1,
            forbidden_source=None,
        )

    def test_all_consistent_exits_0(self):
        run_dir = _create_mock_run(self.tmp_path)
        with mock.patch.object(llm_baseline, "verify_proof", side_effect=self._fake_verify):
            rc, report = rv.replay_verify(run_dir, benchmark_dir=self.bench_dir)
        self.assertEqual(rc, 0)
        self.assertTrue(report["summary"]["all_consistent"])
        self.assertEqual(report["summary"]["total_samples"], 3)
        self.assertEqual(report["summary"]["consistent_samples"], 3)
        self.assertEqual(report["summary"]["inconsistent_samples"], 0)
        self.assertEqual(report["discrepancies"], [])
        self.assertEqual(report["per_problem"]["lean_ineq_amgm3"]["replayed"]["c"], 2)
        self.assertEqual(report["per_problem"]["lean_ineq_amgm3"]["diff_c"], 0)
        self.assertEqual(report["per_problem"]["lean_nat_sum_even"]["replayed"]["c"], 0)
        self.assertEqual(report["per_problem"]["lean_nat_sum_even"]["diff_c"], 0)

    def test_inconsistency_detected_exits_1(self):
        # Alter lean_ineq_amgm3 sample 0 in results.jsonl to claim it failed
        rows = [
            {
                "problem": "lean_ineq_amgm3",
                "sample_index": 0,
                "passed": False,  # Was True
                "failure_class": "lean_error",  # Was ok
                "first_error_line": "some error",
                "judge_version": "v2",
                "lean_returncode": 1,
            },
            {
                "problem": "lean_ineq_amgm3",
                "sample_index": 1,
                "passed": True,
                "failure_class": "ok",
                "first_error_line": "",
                "judge_version": "v2",
                "lean_returncode": 0,
            },
            {
                "problem": "lean_nat_sum_even",
                "sample_index": 0,
                "passed": False,
                "failure_class": "lean_error",
                "first_error_line": "error: unsolved goals",
                "judge_version": "v2",
                "lean_returncode": 1,
            },
        ]
        run_dir = _create_mock_run(self.tmp_path, results_rows=rows)
        with mock.patch.object(llm_baseline, "verify_proof", side_effect=self._fake_verify):
            rc, report = rv.replay_verify(run_dir, benchmark_dir=self.bench_dir)
        self.assertEqual(rc, 1)
        self.assertFalse(report["summary"]["all_consistent"])
        self.assertEqual(report["summary"]["total_samples"], 3)
        self.assertEqual(report["summary"]["consistent_samples"], 2)
        self.assertEqual(report["summary"]["inconsistent_samples"], 1)
        self.assertEqual(len(report["discrepancies"]), 1)
        disc = report["discrepancies"][0]
        self.assertEqual(disc["problem"], "lean_ineq_amgm3")
        self.assertEqual(disc["sample_index"], 0)
        self.assertEqual(disc["original"]["passed"], False)
        self.assertEqual(disc["original"]["failure_class"], "lean_error")
        self.assertEqual(disc["replayed"]["passed"], True)
        self.assertEqual(disc["replayed"]["failure_class"], "ok")

    def test_missing_response_file_exits_2(self):
        run_dir = _create_mock_run(self.tmp_path)
        (run_dir / "responses" / "lean_ineq_amgm3_1.txt").unlink()
        with mock.patch.object(llm_baseline, "verify_proof", side_effect=self._fake_verify):
            rc, report = rv.replay_verify(run_dir, benchmark_dir=self.bench_dir)
        self.assertEqual(rc, 2)
        self.assertEqual(report, {})

    def test_judge_version_mismatch_in_manifest_exits_2(self):
        run_dir = _create_mock_run(self.tmp_path, manifest_overrides={"judge_version": "v1"})
        with mock.patch.object(llm_baseline, "verify_proof", side_effect=self._fake_verify):
            rc, report = rv.replay_verify(run_dir, benchmark_dir=self.bench_dir)
        self.assertEqual(rc, 2)
        self.assertEqual(report, {})

    def test_judge_version_mismatch_in_results_exits_2(self):
        rows = [
            {
                "problem": "lean_ineq_amgm3",
                "sample_index": 0,
                "passed": True,
                "failure_class": "ok",
                "first_error_line": "",
                "judge_version": "v999",  # Mismatch
                "lean_returncode": 0,
            }
        ]
        run_dir = _create_mock_run(self.tmp_path, results_rows=rows)
        with mock.patch.object(llm_baseline, "verify_proof", side_effect=self._fake_verify):
            rc, report = rv.replay_verify(run_dir, benchmark_dir=self.bench_dir)
        self.assertEqual(rc, 2)
        self.assertEqual(report, {})

    def test_hints_file_sha256_mismatch_exits_2(self):
        hints_file = self.tmp_path / "hints.json"
        hints_file.write_text('{"hints": {}}\n', encoding="utf-8")
        manifest_overrides = {
            "args": {
                "hints_file": str(hints_file),
                "hints_file_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
            }
        }
        run_dir = _create_mock_run(self.tmp_path, manifest_overrides=manifest_overrides)
        with mock.patch.object(llm_baseline, "verify_proof", side_effect=self._fake_verify):
            rc, report = rv.replay_verify(run_dir, benchmark_dir=self.bench_dir)
        self.assertEqual(rc, 2)
        self.assertEqual(report, {})

    def test_missing_run_dir_or_files_exits_2(self):
        non_existent = self.tmp_path / "non_existent"
        rc, report = rv.replay_verify(non_existent, benchmark_dir=self.bench_dir)
        self.assertEqual(rc, 2)

        run_dir = _create_mock_run(self.tmp_path)
        (run_dir / "results.jsonl").unlink()
        rc, report = rv.replay_verify(run_dir, benchmark_dir=self.bench_dir)
        self.assertEqual(rc, 2)

    def test_problems_filter_and_limit_samples(self):
        run_dir = _create_mock_run(self.tmp_path)
        with mock.patch.object(llm_baseline, "verify_proof", side_effect=self._fake_verify):
            rc, report = rv.replay_verify(
                run_dir,
                benchmark_dir=self.bench_dir,
                problems=["lean_ineq_amgm3"],
                limit_samples=1,
            )
        self.assertEqual(rc, 0)
        self.assertEqual(report["summary"]["total_samples"], 1)
        self.assertEqual(list(report["per_problem"].keys()), ["lean_ineq_amgm3"])
        self.assertEqual(report["per_problem"]["lean_ineq_amgm3"]["replayed"]["n"], 1)

    def test_cli_execution_with_out_and_table(self):
        run_dir = _create_mock_run(self.tmp_path)
        out_json = self.tmp_path / "out" / "replay.json"
        with mock.patch.object(llm_baseline, "verify_proof", side_effect=self._fake_verify):
            rc = rv.main([
                str(run_dir),
                "--benchmark", str(self.bench_dir),
                "--out", str(out_json),
                "--table",
            ])
        self.assertEqual(rc, 0)
        self.assertTrue(out_json.is_file())
        data = json.loads(out_json.read_text(encoding="utf-8"))
        self.assertEqual(data["summary"]["consistent_samples"], 3)


class TestReplayVerifyRealLeanIntegration(unittest.TestCase):
    def test_real_lean_replay_on_b0_merged(self):
        run_dir = Path("runs/20261104T054619Z_b0-merged")
        if not run_dir.is_dir():
            self.skipTest("run directory runs/20261104T054619Z_b0-merged not found")

        elan_bin = Path.home() / ".elan" / "bin"
        lake_found = shutil.which("lake") is not None or (elan_bin / "lake").is_file()
        if not lake_found:
            self.skipTest("lake / Lean executable not found")

        if os.environ.get("ELAN_TOOLCHAIN") != "leanprover/lean4:v4.35.0":
            self.skipTest("ELAN_TOOLCHAIN=leanprover/lean4:v4.35.0 not set")

        if str(elan_bin) not in os.environ.get("PATH", "") and shutil.which("lake") is None:
            self.skipTest("~/.elan/bin not in PATH")

        # Select 2 problems with --limit-samples 8
        rc, report = rv.replay_verify(
            run_dir=run_dir,
            benchmark_dir="benchmark/lean_hard",
            problems="lean_ineq_amgm3,lean_nat_sum_even",
            limit_samples=8,
            verify_workers=4,
        )
        self.assertEqual(rc, 0)
        self.assertTrue(report["summary"]["all_consistent"])
        self.assertEqual(report["summary"]["inconsistent_samples"], 0)
        self.assertEqual(report["summary"]["total_samples"], 8)
        self.assertEqual(report["summary"]["consistent_samples"], 8)


if __name__ == "__main__":
    unittest.main()
