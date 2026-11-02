import json
import tempfile
import unittest
from pathlib import Path

from mathesis.experiment import default_problems_path, load_problems, run_pilot
from mathesis.runlog import CountingBackend, start_run

MANIFEST_KEYS = (
    "timestamp_utc",
    "command",
    "args",
    "seed",
    "git_commit",
    "git_dirty",
    "python_version",
    "platform",
    "machine",
    "lean_toolchain",
    "mathlib_rev",
)


class RunLogTest(unittest.TestCase):
    def test_manifest_keys_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = start_run(Path(tmp), "pilot", {"a": 1}, 7)
            self.assertTrue(run.path.name.endswith("_pilot"))
            manifest = json.loads((run.path / "manifest.json").read_text("utf-8"))
            for key in MANIFEST_KEYS:
                self.assertIn(key, manifest)
            self.assertEqual(manifest["command"], "pilot")
            self.assertEqual(manifest["args"], {"a": 1})
            self.assertEqual(manifest["seed"], 7)
            self.assertNotEqual(manifest["lean_toolchain"], "")

    def test_results_jsonl_one_object_per_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = start_run(Path(tmp), "pilot", {}, 0)
            run.append_result({"problem": "p1", "solved": True})
            run.append_result({"problem": "p2", "solved": False})
            lines = (run.path / "results.jsonl").read_text("utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            records = [json.loads(line) for line in lines]
            self.assertEqual(records[0]["problem"], "p1")
            self.assertIs(records[1]["solved"], False)

    def test_git_failure_yields_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "norepo"
            repo.mkdir()
            run = start_run(Path(tmp) / "runs", "pilot", {}, 0, repo_dir=repo)
            manifest = json.loads((run.path / "manifest.json").read_text("utf-8"))
            self.assertEqual(manifest["git_commit"], "unknown")
            self.assertIsNone(manifest["git_dirty"])
            self.assertEqual(manifest["lean_toolchain"], "unknown")
            self.assertEqual(manifest["mathlib_rev"], "unknown")

    def test_summary_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = start_run(Path(tmp), "pilot", {}, 0)
            run.finish({"solved": 3})
            data = json.loads((run.path / "summary.json").read_text("utf-8"))
            self.assertEqual(data["summary"], {"solved": 3})
            self.assertGreaterEqual(data["wall_clock_seconds"], 0.0)

    def test_same_second_runs_do_not_collide(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = start_run(Path(tmp), "pilot", {}, 0)
            second = start_run(Path(tmp), "pilot", {}, 0)
            self.assertNotEqual(first.path, second.path)

    def test_counting_backend_counts_calls(self):
        class Fake:
            marker = "x"

            def reset(self, theorem):
                return theorem

            def apply(self, state, tactic):
                return tactic

        counted = CountingBackend(Fake())
        counted.reset("t")
        counted.apply("s", "intro")
        self.assertEqual(counted.calls, 2)
        self.assertEqual(counted.marker, "x")

    def test_run_pilot_writes_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = start_run(Path(tmp), "pilot", {}, 3)
            path = default_problems_path()
            run_pilot(path, run=run, seed=3)
            lines = (run.path / "results.jsonl").read_text("utf-8").splitlines()
            self.assertEqual(len(lines), 4 * len(load_problems(path)))
            record = json.loads(lines[0])
            for key in (
                "problem", "family", "config", "solved", "nodes", "lean_calls",
                "wall_seconds", "budget_nodes", "seed", "error",
            ):
                self.assertIn(key, record)
            self.assertEqual(record["seed"], 3)
            self.assertGreater(record["lean_calls"], 0)


if __name__ == "__main__":
    unittest.main()
