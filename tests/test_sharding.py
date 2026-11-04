import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mathesis import cli, llm_baseline

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPTS))
    return module


merge = _load("merge_shards")
launcher = _load("run_sharded")
K = 3
PREFLIGHT = {"ok": True}


def _passes(name, condition):
    """Deterministic fake outcome per (problem, condition) so shards agree with a full run."""
    seed = sum(ord(c) for c in name + condition)
    return [(seed + i) % 3 == 0 for i in range(K)]


def _write_rows(run, prob, condition):
    tag = prob["name"] + ("" if condition is None else "__" + condition)
    flags = _passes(prob["name"], condition or "")
    for i, ok in enumerate(flags):
        row = {"problem": prob["name"], "sample_index": i, "passed": ok,
               "failure_class": "none" if ok else ("wrong" if i % 2 else "extract")}
        if condition is not None:
            row["condition"] = condition
        run.append_result(row)
        for sub, ext in (("candidates", ".lean"), ("candidates", ".out"), ("responses", ".txt")):
            d = run.path / sub
            d.mkdir(exist_ok=True)
            (d / (tag + "_" + str(i) + ext)).write_text(tag, encoding="utf-8")
    return llm_baseline._problem_stats(len(flags), sum(flags), K)


def fake_run_b0(run, problems, **kwargs):
    from collections import Counter
    per, fails = {}, Counter()
    for prob in problems:
        per[prob["name"]] = _write_rows(run, prob, None)
    for line in run.results_path.read_text().splitlines():
        fails[json.loads(line)["failure_class"]] += 1
    return llm_baseline._with_preflight(llm_baseline.summarize_b0(per, K, dict(fails)), PREFLIGHT)


def fake_run_hint_gap(run, problems, **kwargs):
    from collections import Counter
    targets = kwargs.get("targets")
    if targets is None:
        targets = llm_baseline.select_hint_gap_problems(problems, kwargs["limit"], kwargs["names"])
    pairs, fails = {}, Counter()
    for prob in targets:
        pairs[prob["name"]] = {c: _write_rows(run, prob, c) for c in ("plain", "hint")}
    for line in run.results_path.read_text().splitlines():
        fails[json.loads(line)["failure_class"]] += 1
    return llm_baseline._with_preflight(
        llm_baseline.summarize_hint_gap(pairs, K, failure_class_counts=dict(fails)), PREFLIGHT)


def run_cli(kind, out, shard=None, limit=None, extra=None):
    target = {"b0": "run_b0", "hint-gap": "run_hint_gap"}[kind]
    fake = {"b0": fake_run_b0, "hint-gap": fake_run_hint_gap}[kind]
    with mock.patch.object(llm_baseline, target, side_effect=fake) as patched:
        with contextlib.redirect_stdout(io.StringIO()):
            if kind == "b0":
                rc = cli.run_b0_command(k=K, limit=limit, max_tokens=8, out=str(out), shard=shard,
                                        **(extra or {}))
            else:
                rc = cli.run_hint_gap_command(k=K, limit=limit, max_tokens=8, out=str(out),
                                              shard=shard, **(extra or {}))
    return rc, patched


def only_dir(parent):
    dirs = [p for p in Path(parent).iterdir() if p.is_dir()]
    assert len(dirs) == 1, dirs
    return dirs[0]


def manifest_of(path):
    return json.loads((path / "manifest.json").read_text("utf-8"))


class ShardSelectionTest(unittest.TestCase):
    def test_b0_round_robin_and_manifest(self):
        full = [p["name"] for p in llm_baseline.load_b0_problems(7, None)]
        with tempfile.TemporaryDirectory() as tmp:
            rc, patched = run_cli("b0", tmp, shard="1/3", limit=7)
            self.assertEqual(rc, 0)
            args = manifest_of(only_dir(tmp))["args"]
        self.assertEqual(args["shard"], [1, 3])
        self.assertEqual(args["problem_names"], full[1::3])
        self.assertEqual(args["full_problem_names"], full)
        self.assertEqual([p["name"] for p in patched.call_args[0][1]], full[1::3])
        self.assertEqual(len(args["benchmark_sha256"]["lean_files"]), len(full[1::3]))

    def test_hint_gap_round_robin_and_manifest(self):
        problems = llm_baseline.load_b0_problems(None, None)
        full = [p["name"] for p in llm_baseline.select_hint_gap_problems(problems, 6)]
        with tempfile.TemporaryDirectory() as tmp:
            rc, patched = run_cli("hint-gap", tmp, shard="0/2", limit=6)
            self.assertEqual(rc, 0)
            args = manifest_of(only_dir(tmp))["args"]
        self.assertEqual(args["shard"], [0, 2])
        self.assertEqual(args["problem_names"], full[0::2])
        self.assertEqual(args["problems"], full[0::2])
        self.assertEqual(args["full_problem_names"], full)
        self.assertEqual(patched.call_args.kwargs["names"], full[0::2])
        subset = llm_baseline.select_hint_gap_problems(problems, None, full[0::2])
        self.assertEqual(args["auxiliary_sha256"], cli._auxiliary_sha256(subset))

    def test_unsharded_manifest_has_null_shard(self):
        for kind in ("b0", "hint-gap"):
            with tempfile.TemporaryDirectory() as tmp:
                run_cli(kind, tmp, limit=2)
                args = manifest_of(only_dir(tmp))["args"]
            self.assertIsNone(args["shard"])
            self.assertNotIn("full_problem_names", args)

    def test_bad_shard_specs_rejected_without_run_dir(self):
        for spec in ("3/3", "-1/2", "0/0", "a/b", "1", "1/2/3", ""):
            for kind in ("b0", "hint-gap"):
                with tempfile.TemporaryDirectory() as tmp:
                    rc, patched = run_cli(kind, tmp, shard=spec)
                    self.assertEqual(rc, 2, (kind, spec))
                    patched.assert_not_called()
                    self.assertEqual(list(Path(tmp).iterdir()), [])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["b0", "--shard", "2/2"]), 2)
            self.assertEqual(cli.main(["hint-gap", "--shard", "x"]), 2)

    def test_shard_with_controls_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = cli.run_b0_command(k=2, limit=None, max_tokens=8, out=tmp,
                                        controls=True, shard="0/2")
            self.assertEqual(rc, 2)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_empty_shard_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, patched = run_cli("b0", tmp, shard="2/3", limit=2)
            self.assertEqual(rc, 2)
            patched.assert_not_called()


class MergeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def make_shards(self, kind, count, limit, tag="s"):
        dirs = []
        for i in range(count):
            out = self.tmp / (tag + str(i))
            rc, _ = run_cli(kind, out, shard=str(i) + "/" + str(count), limit=limit)
            self.assertEqual(rc, 0)
            dirs.append(only_dir(out))
        return dirs

    def unsharded(self, kind, limit):
        out = self.tmp / ("full_" + kind)
        self.assertEqual(run_cli(kind, out, limit=limit)[0], 0)
        return only_dir(out)

    def check_equivalent(self, kind, count, limit):
        shards = self.make_shards(kind, count, limit)
        full = self.unsharded(kind, limit)
        merged = Path(merge.merge_shards(list(reversed(shards)), self.tmp / "merged"))
        self.assertTrue(merged.name.endswith("_" + kind + "-merged"))
        want = json.loads((full / "summary.json").read_text())
        got = json.loads((merged / "summary.json").read_text())
        self.assertEqual(got["status"], "ok")
        self.assertEqual(got["summary"], want["summary"])
        self.assertEqual((merged / "results.jsonl").read_text(), (full / "results.jsonl").read_text())
        fm, mm = manifest_of(full)["args"], manifest_of(merged)["args"]
        self.assertEqual(mm["problem_names"], fm["problem_names"])
        self.assertEqual(mm["benchmark_sha256"], fm["benchmark_sha256"])
        self.assertEqual(mm.get("auxiliary_sha256"), fm.get("auxiliary_sha256"))
        self.assertEqual(mm.get("problems"), fm.get("problems"))
        self.assertEqual(mm["shard_runs"], [str(d) for d in shards])
        for sub in ("candidates", "responses"):
            self.assertEqual(sorted(p.name for p in (merged / sub).iterdir()),
                             sorted(p.name for p in (full / sub).iterdir()))
        return want["summary"], shards

    def test_b0_merge_matches_unsharded(self):
        summary, _ = self.check_equivalent("b0", 3, 8)
        self.assertEqual(summary["n_problems"], 8)

    def test_hint_gap_merge_matches_unsharded_including_ci(self):
        summary, _ = self.check_equivalent("hint-gap", 3, 7)
        self.assertEqual(summary["n_problems"], 7)
        self.assertEqual(len(summary["ci95"]), 2)
        self.assertEqual(len(summary["ci95_two_level"]), 2)

    def test_merge_refuses_to_overwrite_and_is_read_only(self):
        shards = self.make_shards("b0", 2, 4)
        before = {str(p): p.read_bytes() for d in shards for p in d.rglob("*") if p.is_file()}
        first = merge.merge_shards(shards, self.tmp / "m")
        second = merge.merge_shards(shards, self.tmp / "m")
        self.assertNotEqual(first, second)
        after = {str(p): p.read_bytes() for d in shards for p in d.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_rejects_mismatched_args(self):
        shards = self.make_shards("b0", 2, 4)
        path = shards[1] / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["args"]["max_tokens"] = 999
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(merge.MergeError, "max_tokens"):
            merge.merge_shards(shards, self.tmp / "m")
        self.assertFalse((self.tmp / "m").exists())

    def test_rejects_seed_mismatch(self):
        shards = self.make_shards("b0", 2, 4)
        path = shards[0] / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["seed"] = 5
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(merge.MergeError, "seed"):
            merge.merge_shards(shards, self.tmp / "m")

    def test_rejects_missing_and_duplicate_shard(self):
        shards = self.make_shards("b0", 3, 6)
        with self.assertRaisesRegex(merge.MergeError, "exactly once"):
            merge.merge_shards(shards[:2], self.tmp / "m")
        with self.assertRaisesRegex(merge.MergeError, "exactly once"):
            merge.merge_shards([shards[0], shards[1], shards[1]], self.tmp / "m")

    def test_rejects_failed_status(self):
        shards = self.make_shards("hint-gap", 2, 4)
        path = shards[1] / "summary.json"
        doc = json.loads(path.read_text())
        doc["status"] = "error"
        doc["error"] = "boom"
        path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(merge.MergeError, "not 'ok'"):
            merge.merge_shards(shards, self.tmp / "m")

    def test_rejects_unsharded_run_and_tampered_rows(self):
        full = self.unsharded("b0", 2)
        with self.assertRaisesRegex(merge.MergeError, "not a shard run"):
            merge.merge_shards([full], self.tmp / "m")
        shards = self.make_shards("b0", 2, 4, tag="t")
        path = shards[0] / "results.jsonl"
        lines = path.read_text().splitlines()
        row = json.loads(lines[0])
        row["passed"] = not row["passed"]
        path.write_text("\n".join([json.dumps(row)] + lines[1:]) + "\n")
        with self.assertRaisesRegex(merge.MergeError, "does not match"):
            merge.merge_shards(shards, self.tmp / "m")


def _hint_names(count):
    """`count` lean_pilot names in benchmark order, at least one of them a routine problem."""
    problems = llm_baseline.load_b0_problems(None, None)
    routine = [p["name"] for p in problems if not (p["insight"] and p["auxiliary"])]
    chosen = set(routine[:1]) | {p["name"] for p in problems[:count - 1]}
    return [p["name"] for p in problems if p["name"] in chosen]


def _write_hint_file(path, names):
    hints = {name: "h_" + name + " : True" for name in names}
    Path(path).write_text(json.dumps({"rule": "test rule", "source": "test", "hints": hints}),
                          encoding="utf-8")
    return hints


class HintFileTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.names = _hint_names(5)
        self.hint_path = self.tmp / "hints.json"
        self.hints = _write_hint_file(self.hint_path, self.names)

    def test_targets_follow_hint_file_including_routine(self):
        out = self.tmp / "run"
        rc, patched = run_cli("hint-gap", out, extra={"hints_file": str(self.hint_path)})
        self.assertEqual(rc, 0)
        targets = patched.call_args.kwargs["targets"]
        self.assertEqual([p["name"] for p in targets], self.names)
        self.assertTrue(any(not p["insight"] for p in targets))
        self.assertEqual({p["name"]: p["auxiliary"] for p in targets}, self.hints)
        args = manifest_of(only_dir(out))["args"]
        self.assertEqual(args["problem_names"], self.names)
        self.assertEqual(args["hint_rule"], "test rule")
        self.assertEqual(args["hints_file"], str(self.hint_path.resolve()))
        self.assertEqual(args["hints_file_sha256"], cli.file_sha256(self.hint_path))
        self.assertEqual(args["auxiliary_sha256"], cli._auxiliary_sha256(targets))

    def test_without_hint_file_manifest_has_no_hint_fields(self):
        out = self.tmp / "run"
        self.assertEqual(run_cli("hint-gap", out, limit=2)[0], 0)
        args = manifest_of(only_dir(out))["args"]
        for key in ("hints_file", "hints_file_sha256", "hint_rule"):
            self.assertNotIn(key, args)

    def test_bad_hint_files_rejected_without_run_dir(self):
        bad = {
            "unknown": {"rule": "r", "hints": {"no_such_problem": "x"}},
            "empty": {"rule": "r", "hints": {}},
            "norule": {"hints": {self.names[0]: "x"}},
            "blank": {"rule": "r", "hints": {self.names[0]: "  "}},
        }
        for label, data in bad.items():
            path = self.tmp / (label + ".json")
            path.write_text(json.dumps(data), encoding="utf-8")
            out = self.tmp / ("out_" + label)
            out.mkdir()
            rc, patched = run_cli("hint-gap", out, extra={"hints_file": str(path)})
            self.assertEqual(rc, 2, label)
            patched.assert_not_called()
            self.assertEqual(list(out.iterdir()), [], label)
        rc, _ = run_cli("hint-gap", self.tmp / "missing_out",
                        extra={"hints_file": str(self.tmp / "missing.json")})
        self.assertEqual(rc, 2)

    def test_sharded_hint_file_merge_matches_unsharded(self):
        extra = {"hints_file": str(self.hint_path)}
        shards = []
        for i in range(2):
            out = self.tmp / ("s" + str(i))
            self.assertEqual(run_cli("hint-gap", out, shard=str(i) + "/2", extra=extra)[0], 0)
            shards.append(only_dir(out))
        full_out = self.tmp / "full"
        self.assertEqual(run_cli("hint-gap", full_out, extra=extra)[0], 0)
        full = only_dir(full_out)
        merged = Path(merge.merge_shards(shards, self.tmp / "merged"))
        self.assertEqual(json.loads((merged / "summary.json").read_text())["summary"],
                         json.loads((full / "summary.json").read_text())["summary"])
        self.assertEqual((merged / "results.jsonl").read_text(), (full / "results.jsonl").read_text())
        self.assertEqual(manifest_of(merged)["args"]["auxiliary_sha256"],
                         manifest_of(full)["args"]["auxiliary_sha256"])

    def test_merge_rejects_changed_hint_file(self):
        extra = {"hints_file": str(self.hint_path)}
        shards = []
        for i in range(2):
            out = self.tmp / ("s" + str(i))
            self.assertEqual(run_cli("hint-gap", out, shard=str(i) + "/2", extra=extra)[0], 0)
            shards.append(only_dir(out))
        _write_hint_file(self.hint_path, self.names[:-1])
        with self.assertRaises(merge.MergeError):
            merge.merge_shards(shards, self.tmp / "merged")


class LauncherTest(unittest.TestCase):
    def test_parse_gpus(self):
        self.assertEqual(launcher.parse_gpus("0,1, 3"), ["0", "1", "3"])
        for bad in ("", "a", "0,0", "0,,1"):
            with self.assertRaises(ValueError):
                launcher.parse_gpus(bad)

    def test_build_commands(self):
        jobs = launcher.build_commands(["2", "3"], "hint-gap", ["--k", "8", "--seed=1"],
                                       Path("/x/shards_T"), python="py")
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[1]["env"], {"CUDA_VISIBLE_DEVICES": "3"})
        self.assertEqual(jobs[1]["argv"], [
            "py", "-m", "mathesis.cli", "hint-gap", "--k", "8", "--seed=1",
            "--shard", "1/2", "--out", "/x/shards_T/shard1"])
        self.assertEqual(jobs[0]["log"], Path("/x/shards_T/shard0.log"))

    def test_build_commands_rejects_reserved_flags_and_bad_command(self):
        for extra in (["--shard", "0/2"], ["--out=x"], ["--controls"]):
            with self.assertRaises(ValueError):
                launcher.build_commands(["0"], "b0", extra, Path("/x"))
        with self.assertRaises(ValueError):
            launcher.build_commands(["0"], "pilot", [], Path("/x"))

    def test_main_does_not_merge_when_a_shard_fails(self):
        class FakeProc:
            def __init__(self, code):
                self.code = code

            def wait(self):
                return self.code

        codes = iter([0, 1])
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(launcher.subprocess, "Popen",
                                   side_effect=lambda *a, **k: FakeProc(next(codes))), \
                    mock.patch.object(launcher.merge_shards, "merge_shards") as merger, \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                rc = launcher.main(["--gpus", "0,1", "--out", tmp, "--", "b0", "--k", "2"])
            self.assertEqual(rc, 1)
            merger.assert_not_called()

    def test_main_merges_when_all_succeed(self):
        class FakeProc:
            def wait(self):
                return 0

        def popen(argv, **kwargs):
            run_out = Path(argv[argv.index("--out") + 1])
            (run_out / "r").mkdir(parents=True)
            self.assertIn("CUDA_VISIBLE_DEVICES", kwargs["env"])
            return FakeProc()

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(launcher.subprocess, "Popen", side_effect=popen), \
                    mock.patch.object(launcher.merge_shards, "merge_shards",
                                      return_value=Path(tmp) / "merged") as merger, \
                    contextlib.redirect_stdout(io.StringIO()):
                rc = launcher.main(["--gpus", "0,1", "--out", tmp, "--", "b0"])
            self.assertEqual(rc, 0)
            self.assertEqual(len(merger.call_args[0][0]), 2)


if __name__ == "__main__":
    unittest.main()
