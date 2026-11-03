import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mathesis import cli, llm_baseline
from mathesis.lean_pilot import default_lean_pilot_dir, load_lean_pilot

# Keys only the hint-gap manifest carries; everything else must match b0's.
HINT_ONLY_KEYS = {"hint_prompt_template", "problems", "auxiliary_sha256"}


def _quiet_main(argv):
    with contextlib.redirect_stdout(io.StringIO()):
        return cli.main(argv)


def _only_manifest(out_dir: Path) -> dict:
    runs = [path for path in Path(out_dir).iterdir() if path.is_dir()]
    if len(runs) != 1:
        raise AssertionError("expected one run dir, got " + str(runs))
    return json.loads((runs[0] / "manifest.json").read_text("utf-8"))


class RunArgsManifestTest(unittest.TestCase):
    """b0 and hint-gap manifests: shared arg keys, problem list, benchmark hashes."""

    def _run_b0(self, out_dir, limit=3, verify_workers=3):
        seen = {}

        def fake_run_b0(run, problems, **kwargs):
            seen["names"] = [prob["name"] for prob in problems]
            return llm_baseline.summarize_b0({}, kwargs["k"])

        with mock.patch.object(llm_baseline, "run_b0", side_effect=fake_run_b0):
            with contextlib.redirect_stdout(io.StringIO()):
                rc = cli.run_b0_command(
                    k=2, limit=limit, max_tokens=8, seed=0, out=str(out_dir),
                    verify_workers=verify_workers,
                )
        self.assertEqual(rc, 0)
        return _only_manifest(out_dir), seen["names"]

    def _run_hint(self, out_dir, limit=2, verify_workers=3):
        seen = {}

        def fake_run_hint_gap(run, problems, **kwargs):
            selected = llm_baseline.select_hint_gap_problems(
                problems, kwargs["limit"], kwargs["names"],
            )
            seen["names"] = [prob["name"] for prob in selected]
            return llm_baseline.summarize_hint_gap({}, kwargs["k"])

        with mock.patch.object(llm_baseline, "run_hint_gap", side_effect=fake_run_hint_gap):
            with contextlib.redirect_stdout(io.StringIO()):
                rc = cli.run_hint_gap_command(
                    k=2, limit=limit, max_tokens=8, seed=0, out=str(out_dir),
                    verify_workers=verify_workers,
                )
        self.assertEqual(rc, 0)
        return _only_manifest(out_dir), seen["names"]

    def test_b0_and_hint_gap_share_arg_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            b0_manifest, _ = self._run_b0(Path(tmp) / "b0")
            hint_manifest, _ = self._run_hint(Path(tmp) / "hint")
            b0_keys = set(b0_manifest["args"])
            hint_keys = set(hint_manifest["args"])
            self.assertEqual(b0_keys, hint_keys - HINT_ONLY_KEYS)
            self.assertFalse(HINT_ONLY_KEYS & b0_keys)
            for key in ("verify_workers", "problem_names", "benchmark_sha256"):
                self.assertIn(key, b0_keys)
                self.assertIn(key, hint_keys)

    def test_manifest_records_lean_sandbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, _ = self._run_b0(Path(tmp) / "b0")
        sandbox = manifest["args"]["lean_sandbox"]
        self.assertIn(sandbox["mode"], ("unshare-net", "none"))
        self.assertIn("env_whitelist", sandbox)

    def test_b0_problem_names_match_what_run_b0_receives(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, received = self._run_b0(Path(tmp) / "b0", limit=3, verify_workers=5)
            expected = [entry["name"] for entry in load_lean_pilot()[:3]]
            self.assertEqual(received, expected)
            self.assertEqual(manifest["args"]["problem_names"], expected)
            self.assertEqual(manifest["args"]["verify_workers"], 5)

    def test_hint_gap_problem_names_match_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, selected = self._run_hint(Path(tmp) / "hint", limit=2)
            self.assertTrue(selected, "real benchmark should have hint-gap targets")
            self.assertEqual(manifest["args"]["problem_names"], selected)
            self.assertEqual(manifest["args"]["problems"], selected)
            self.assertLessEqual(len(selected), 2)

    def test_benchmark_sha256_covers_problems_json_and_used_lean_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, names = self._run_b0(Path(tmp) / "b0", limit=2)
            base = default_lean_pilot_dir()
            entries = {entry["name"]: entry for entry in load_lean_pilot()}
            digest = manifest["args"]["benchmark_sha256"]
            self.assertEqual(
                digest["problems_json"],
                hashlib.sha256((base / "problems.json").read_bytes()).hexdigest(),
            )
            expected_files = {}
            for name in names:
                lean_file = entries[name]["lean_file"]
                data = (base / lean_file).read_bytes()
                expected_files[lean_file] = hashlib.sha256(data).hexdigest()
            self.assertEqual(digest["lean_files"], expected_files)

    def test_controls_manifest_lists_only_control_problems(self):
        fake_report = {"c1": [], "c2": [], "c1_pass": True, "c2_pass": True}
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(llm_baseline, "run_controls", return_value=fake_report), \
                    mock.patch.object(llm_baseline, "format_controls", return_value=""):
                with contextlib.redirect_stdout(io.StringIO()):
                    cli.run_b0_command(k=2, limit=None, max_tokens=8, out=tmp, controls=True)
            manifest = _only_manifest(Path(tmp))
        self.assertEqual(manifest["args"]["problem_names"], list(llm_baseline.CONTROL_PROBLEMS))
        self.assertEqual(
            sorted(manifest["args"]["benchmark_sha256"]["lean_files"]),
            sorted(
                str(entry["lean_file"]) for entry in load_lean_pilot()
                if entry["name"] in llm_baseline.CONTROL_PROBLEMS
            ),
        )

    def test_auxiliary_sha256_follows_documented_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, selected = self._run_hint(Path(tmp) / "hint", limit=2)
            by_name = {entry["name"]: entry for entry in load_lean_pilot()}
            pairs = [[name, by_name[name]["auxiliary"]] for name in sorted(selected)]
            text = json.dumps(pairs, ensure_ascii=False, separators=(",", ":"))
            self.assertEqual(
                manifest["args"]["auxiliary_sha256"],
                hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )


class CliInputValidationTest(unittest.TestCase):
    def test_hint_gap_empty_problems_flag_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(llm_baseline, "run_hint_gap") as run_hint_gap:
                rc = _quiet_main(["hint-gap", "--problems", "", "--out", tmp])
            self.assertEqual(rc, 2)
            run_hint_gap.assert_not_called()
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_lean_replay_limit_below_one_is_rejected(self):
        with mock.patch.object(cli, "SubprocessLeanBackend") as backend:
            rc = _quiet_main(["lean-replay", "--limit", "0"])
        self.assertEqual(rc, 2)
        backend.assert_not_called()

    def test_lean_bench_limit_below_one_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(cli, "run_lean_bench") as run_bench:
                rc = _quiet_main(["lean-bench", "--limit", "0", "--out", tmp])
            self.assertEqual(rc, 2)
            run_bench.assert_not_called()
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_lean_bench_patience_below_one_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(cli, "run_lean_bench") as run_bench:
                rc = _quiet_main(["lean-bench", "--impasse-patience", "0", "--out", tmp])
            self.assertEqual(rc, 2)
            run_bench.assert_not_called()
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
