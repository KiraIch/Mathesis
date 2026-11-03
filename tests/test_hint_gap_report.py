import contextlib
import importlib.util
import io
import json
import random
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "hint_gap_report.py"
_spec = importlib.util.spec_from_file_location("hint_gap_report", SCRIPT)
rep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rep)


def rows(problem, condition, passes, derived=1):
    out = []
    for i, ok in enumerate(passes):
        row = {"problem": problem, "sample_index": i, "passed": ok, "derived_seed": derived}
        if condition is not None:
            row["condition"] = condition
        out.append(row)
    return out


def bits(c, n):
    return [True] * c + [False] * (n - c)


def hint_fixture(k=4):
    """a: plain 4/4 hint 4/4; b: plain 0/4 hint 2/4; c: plain 2/4 hint 4/4; d: plain 0/4 hint 0/4."""
    spec = {"a": (4, 4), "b": (0, 2), "c": (2, 4), "d": (0, 0)}
    out = []
    for name, (pc, hc) in spec.items():
        out += rows(name, "plain", bits(pc, k), derived=hash(name) % 1000)
        out += rows(name, "hint", bits(hc, k))
    return out


class BinomialResampleTest(unittest.TestCase):
    def test_endpoints_are_deterministic_and_leave_rng_untouched(self):
        rng = random.Random(7)
        state = rng.getstate()
        for _ in range(50):
            self.assertEqual(rep.binomial_resample(rng, 0, 8), 0)
            self.assertEqual(rep.binomial_resample(rng, 8, 8), 8)
        self.assertEqual(rng.getstate(), state)

    def test_interior_stays_in_range(self):
        rng = random.Random(1)
        draws = {rep.binomial_resample(rng, 3, 8) for _ in range(500)}
        self.assertTrue(draws <= set(range(9)))
        self.assertGreater(len(draws), 1)

    def test_all_endpoint_problems_give_degenerate_ci(self):
        pairs = [(0, 8, 0, 8), (8, 8, 8, 8)]
        means = rep.two_layer_bootstrap(pairs, 200, 0)
        self.assertEqual(set(means), {0.0})
        block = rep.ci_block(means, 0.0)
        self.assertEqual(block["ci95"], [0.0, 0.0])
        self.assertTrue(block["lower_at_zero"])


class ReproducibilityTest(unittest.TestCase):
    def test_same_seed_same_result_different_seed_differs(self):
        pairs = [(2, 8, 5, 8), (0, 8, 3, 8), (8, 8, 7, 8), (4, 8, 4, 8)]
        a = rep.two_layer_bootstrap(pairs, 300, 0)
        b = rep.two_layer_bootstrap(pairs, 300, 0)
        c = rep.two_layer_bootstrap(pairs, 300, 1)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_full_report_reproducible(self):
        h = hint_fixture()
        r1 = rep.build_report(h, [], resamples=200, seed=3)
        r2 = rep.build_report(h, [], resamples=200, seed=3)
        self.assertEqual(json.dumps(r1, sort_keys=True), json.dumps(r2, sort_keys=True))

    def test_interval_is_not_clamped(self):
        # every gap is >= 0 with a floor at 0, so the lower end is exactly 0: reported, flagged, unchanged
        pairs = [(0, 8, 0, 8)] * 9 + [(0, 8, 8, 8)]
        block = rep.ci_block(rep.two_layer_bootstrap(pairs, 500, 0), 0.1)
        self.assertEqual(block["ci95"][0], 0.0)
        self.assertTrue(block["lower_at_zero"])


class EmptyInputTest(unittest.TestCase):
    def test_empty_bootstrap_returns_none(self):
        self.assertIsNone(rep.two_layer_bootstrap([], 100, 0))
        self.assertIsNone(rep.problem_only_bootstrap([], 100, 0))
        self.assertIsNone(rep.ci_block(None, None)["ci95"])

    def test_empty_run_does_not_crash(self):
        report = rep.build_report([], [], resamples=50)
        self.assertTrue(report["incomplete"])
        self.assertEqual(report["counts"]["n_paired"], 0)
        self.assertIsNone(report["mean_gap"])
        self.assertIsNone(report["bootstrap"]["two_layer"]["ci95"])
        self.assertEqual(report["noise_floor"]["status"], "no_overlap")
        json.dumps(report)

    def test_quantile_empty(self):
        self.assertIsNone(rep.quantile([], 0.5))

    def test_resamples_must_be_positive(self):
        with self.assertRaises(ValueError):
            rep.two_layer_bootstrap([(1, 2, 1, 2)], 0, 0)


class CompletenessTest(unittest.TestCase):
    def test_complete_run_not_flagged(self):
        report = rep.build_report(hint_fixture(), [], resamples=20)
        self.assertFalse(report["incomplete"])
        self.assertEqual(report["completeness"]["k"], 4)
        self.assertEqual(report["completeness"]["expected_rows"], 4 * 2 * 4)

    def test_truncated_rows_flagged_but_still_computed(self):
        partial = hint_fixture()[:-3]  # last hint group of d loses samples
        report = rep.build_report(partial, [], resamples=20)
        self.assertTrue(report["incomplete"])
        self.assertEqual(report["completeness"]["actual_rows"], 29)
        self.assertEqual(report["counts"]["n_paired"], 4)
        self.assertIsNotNone(report["bootstrap"]["two_layer"]["ci95"])

    def test_missing_planned_problem_flagged(self):
        report = rep.build_report(hint_fixture(), [], resamples=20,
                                  planned_problems=["a", "b", "c", "d", "e"])
        self.assertTrue(report["incomplete"])
        self.assertEqual(report["completeness"]["missing_problems"], ["e"])

    def test_missing_condition_flagged_and_excluded_from_gap(self):
        partial = hint_fixture() + rows("e", "plain", bits(4, 4))
        report = rep.build_report(partial, [], resamples=20)
        self.assertTrue(report["incomplete"])
        self.assertEqual(report["completeness"]["unpaired_problems"], ["e"])
        self.assertIsNone(report["per_problem"]["e"]["gap"])
        self.assertEqual(report["counts"]["n_paired"], 4)


class CountsTest(unittest.TestCase):
    def test_ceiling_floor_nonzero(self):
        report = rep.build_report(hint_fixture(), [], resamples=20)
        counts = report["counts"]
        self.assertEqual(counts["plain_ceiling"], 1)          # a
        self.assertEqual(counts["plain_floor"], 2)            # b, d
        self.assertEqual(counts["nonzero_gap"], 2)            # b (+0.5), c (+0.5)
        self.assertEqual(report["per_problem"]["b"]["gap"], 0.5)
        self.assertEqual(report["per_problem"]["a"]["plain"]["pass_at_1"], 1.0)
        self.assertEqual(report["mean_gap"], 0.25)

    def test_nonzero_gap_list(self):
        report = rep.build_report(hint_fixture(), [], resamples=20)
        self.assertEqual(report["counts"]["nonzero_gap_problems"], ["b", "c"])


class NoiseFloorTest(unittest.TestCase):
    def test_noise_distribution_and_interpretation(self):
        h = hint_fixture()
        b0 = []  # a: 4/4 (diff 0), b: 2/4 (diff .5), c: 0/4 (diff .5); d absent
        b0 += rows("a", None, bits(4, 4), derived=99991)
        b0 += rows("b", None, bits(2, 4))
        b0 += rows("c", None, bits(0, 4))
        report = rep.build_report(h, b0, resamples=20)
        noise = report["noise_floor"]
        self.assertEqual(noise["status"], "ok")
        self.assertEqual(noise["n_overlap"], 3)
        self.assertEqual(noise["problems_without_b0"], ["d"])
        self.assertEqual(noise["median"], 0.5)
        self.assertAlmostEqual(noise["p90"], 0.5)
        interp = noise["gap_interpretation"]
        self.assertEqual(interp["n_nonzero_gap"], 2)
        self.assertEqual(interp["n_exceeding_noise_p90"], 0)
        self.assertEqual(interp["per_problem"]["b"]["noise_percentile_rank"], 1.0)

    def test_no_overlap_is_reported_not_faked(self):
        b0 = rows("zzz", None, bits(4, 4))
        report = rep.build_report(hint_fixture(), b0, resamples=20)
        noise = report["noise_floor"]
        self.assertEqual(noise["status"], "no_overlap")
        self.assertEqual(noise["n_overlap"], 0)
        self.assertIsNone(noise["median"])
        self.assertIsNone(noise["p90"])

    def test_quantile_interpolates(self):
        self.assertEqual(rep.quantile([0.0, 1.0], 0.5), 0.5)
        self.assertAlmostEqual(rep.quantile([0.0, 0.0, 1.0, 1.0, 1.0], 0.9), 1.0)
        self.assertEqual(rep.quantile([3.0], 0.9), 3.0)


class CliTest(unittest.TestCase):
    def test_main_writes_json_from_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hint_dir, b0_dir = tmp / "20990101T000000Z_hint-gap", tmp / "b0"
            hint_dir.mkdir()
            b0_dir.mkdir()
            (hint_dir / "results.jsonl").write_text(
                "\n".join(json.dumps(r) for r in hint_fixture()) + "\n", encoding="utf-8")
            (b0_dir / "results.jsonl").write_text(
                "\n".join(json.dumps(r) for r in rows("a", None, bits(3, 4))) + "\n",
                encoding="utf-8")
            out = tmp / "out" / "report.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = rep.main(["--hint-run", str(hint_dir), "--b0-run", str(b0_dir),
                                 "--out", str(out), "--resamples", "50"])
            self.assertEqual(code, 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["bootstrap"]["resamples"], 50)
            self.assertEqual(data["noise_floor"]["n_overlap"], 1)

    def test_missing_run_returns_error_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stderr(io.StringIO()):
                code = rep.main(["--hint-run", tmp, "--b0-run", tmp,
                                 "--out", str(Path(tmp) / "x.json")])
            self.assertEqual(code, 2)

    def test_default_out_name(self):
        path = rep.default_out(Path("runs/20261103T101932Z_hint-gap"))
        self.assertEqual(path.name, "hint_gap_report_20261103T101932Z_hint-gap.json")
        self.assertEqual(path.parent.name, "analysis")


if __name__ == "__main__":
    unittest.main()
