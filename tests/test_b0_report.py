import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "b0_report.py"
_spec = importlib.util.spec_from_file_location("b0_report", SCRIPT)
b0 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b0)


class QuantileAndBootstrapTest(unittest.TestCase):
    def test_quantile_empty_and_single(self):
        self.assertIsNone(b0.quantile([], 0.5))
        self.assertEqual(b0.quantile([3.0], 0.5), 3.0)
        self.assertEqual(b0.quantile([3.0], 0.9), 3.0)

    def test_quantile_interpolation(self):
        # 0.0, 1.0 -> median 0.5
        self.assertEqual(b0.quantile([0.0, 1.0], 0.5), 0.5)
        # 0, 0, 1, 1, 1 -> p90 is 1.0
        self.assertAlmostEqual(b0.quantile([0.0, 0.0, 1.0, 1.0, 1.0], 0.9), 1.0)

    def test_bootstrap_empty(self):
        self.assertIsNone(b0.bootstrap_mean_ci([], 100, 0))

    def test_bootstrap_resamples_must_be_positive(self):
        with self.assertRaises(ValueError):
            b0.bootstrap_mean_ci([0.5], 0, 0)

    def test_bootstrap_reproducibility(self):
        vals = [0.0, 0.25, 0.5, 0.75, 1.0]
        ci1 = b0.bootstrap_mean_ci(vals, resamples=200, seed=42)
        ci2 = b0.bootstrap_mean_ci(vals, resamples=200, seed=42)
        ci3 = b0.bootstrap_mean_ci(vals, resamples=200, seed=99)
        self.assertEqual(ci1, ci2)
        self.assertNotEqual(ci1, ci3)


class SyntheticDataStatisticsTest(unittest.TestCase):
    """手算小例子驗證所有統計量計算。

    資料集設計：
      4 道題目（全部 n=8）：
        - p1: insight=True, retired=None, family="algebra"
        - p2: insight=True, retired=None, family="algebra"
        - p3: insight=False, retired=None, family="logic"
        - p4: insight=False, retired="stale", family="logic"  <-- 已退役！

      啟用題（active）：p1, p2, p3（N=3）
      全部題（all）：p1, p2, p3, p4（N=4）

      Seed 0：
        - p1: c=8/8 (pass@1=1.0, pass@k=1.0)
        - p2: c=0/8 (pass@1=0.0, pass@k=0.0)
        - p3: c=4/8 (pass@1=0.5, pass@k=1.0)
        - p4: c=8/8 (pass@1=1.0, pass@k=1.0)

      Seed 1：
        - p1: c=8/8 (pass@1=1.0, pass@k=1.0)
        - p2: c=2/8 (pass@1=0.25, pass@k=1.0)
        - p3: c=4/8 (pass@1=0.5, pass@k=1.0)
        - p4: c=4/8 (pass@1=0.5, pass@k=1.0)

      手算數值驗證：
      1. Seed 0:
         active (N=3):
           mean pass@1 = (1.0 + 0.0 + 0.5) / 3 = 1.5 / 3 = 0.5
           mean pass@k = (1.0 + 0.0 + 1.0) / 3 = 2/3 ≈ 0.6667
         all (N=4):
           mean pass@1 = (1.0 + 0.0 + 0.5 + 1.0) / 4 = 2.5 / 4 = 0.625
           mean pass@k = (1 + 0 + 1 + 1) / 4 = 0.75

      2. Seed 1:
         active (N=3):
           mean pass@1 = (1.0 + 0.25 + 0.5) / 3 = 1.75 / 3 = 7/12 ≈ 0.5833
           mean pass@k = (1.0 + 1.0 + 1.0) / 3 = 1.0
         all (N=4):
           mean pass@1 = (1.0 + 0.25 + 0.5 + 0.5) / 4 = 2.25 / 4 = 0.5625
           mean pass@k = 1.0

      3. 分層（只對 active 題）：
         insight (p1, p2, N=2):
           s0 pass@1 = (1.0 + 0.0) / 2 = 0.5
           s1 pass@1 = (1.0 + 0.25) / 2 = 0.625
         routine (p3, N=1):
           s0 pass@1 = 0.5
           s1 pass@1 = 0.5
         family algebra (p1, p2, N=2):
           s0 pass@1 = 0.5, s1 pass@1 = 0.625
         family logic (p3, N=1):
           s0 pass@1 = 0.5, s1 pass@1 = 0.5

      4. 雜訊下限（Seed 1 vs Seed 0，Signed diff d = s1 - s0）：
         active 題：
           p1: d = 1.0 - 1.0 = 0.0, |d| = 0.0
           p2: d = 0.25 - 0.0 = +0.25, |d| = 0.25
           p3: d = 0.5 - 0.5 = 0.0, |d| = 0.0
           |d| 分布：0.0: 2 題，0.125: 0 題，0.25: 1 題，>0.25: 0 題
           median = 0.0, max = 0.25
           mean diff = (0.0 + 0.25 + 0.0) / 3 = 1/12 ≈ 0.0833
         all 題：
           p4: d = 0.5 - 1.0 = -0.5, |d| = 0.5
           |d| 分布：0.0: 2 題，0.125: 0 題，0.25: 1 題，>0.25: 1 題
           max = 0.5
           mean diff = (0.0 + 0.25 + 0.0 - 0.5) / 4 = -0.25 / 4 = -0.0625

      5. 飽和分類（合併兩 seed，c = c0 + c1, n = 8 + 8 = 16，只對 active 題）：
         p1: c = 8 + 8 = 16 (ceiling)
         p2: c = 0 + 2 = 2 (middle)
         p3: c = 4 + 4 = 8 (middle)
         insight (p1, p2): ceiling=1, middle=1, floor=0
         routine (p3): ceiling=0, middle=1, floor=0
         total: ceiling=1, middle=2, floor=0
    """

    def setUp(self):
        self.bench_problems = {
            "p1": {"name": "p1", "family": "algebra", "insight": True},
            "p2": {"name": "p2", "family": "algebra", "insight": True},
            "p3": {"name": "p3", "family": "logic", "insight": False},
            "p4": {"name": "p4", "family": "logic", "insight": False, "retired": "stale"},
        }
        self.s0 = {
            "p1": {"c": 8, "n": 8, "pass_at_1": 1.0, "pass_at_k": 1.0},
            "p2": {"c": 0, "n": 8, "pass_at_1": 0.0, "pass_at_k": 0.0},
            "p3": {"c": 4, "n": 8, "pass_at_1": 0.5, "pass_at_k": 1.0},
            "p4": {"c": 8, "n": 8, "pass_at_1": 1.0, "pass_at_k": 1.0},
        }
        self.s1 = {
            "p1": {"c": 8, "n": 8, "pass_at_1": 1.0, "pass_at_k": 1.0},
            "p2": {"c": 2, "n": 8, "pass_at_1": 0.25, "pass_at_k": 1.0},
            "p3": {"c": 4, "n": 8, "pass_at_1": 0.5, "pass_at_k": 1.0},
            "p4": {"c": 4, "n": 8, "pass_at_1": 0.5, "pass_at_k": 1.0},
        }
        self.seeds_data = {"0": self.s0, "1": self.s1}

    def test_hand_calculated_metrics(self):
        report = b0.build_b0_report(
            self.seeds_data,
            self.bench_problems,
            "synthetic_bench",
            resamples=200,
            bootstrap_seed=42,
        )

        # 1. Per seed
        s0_m = report["seeds"]["0"]
        self.assertEqual(s0_m["active"]["n_problems"], 3)
        self.assertAlmostEqual(s0_m["active"]["mean_pass_at_1"], 0.5)
        self.assertAlmostEqual(s0_m["active"]["mean_pass_at_k"], 2 / 3)
        self.assertEqual(s0_m["all"]["n_problems"], 4)
        self.assertAlmostEqual(s0_m["all"]["mean_pass_at_1"], 0.625)
        self.assertAlmostEqual(s0_m["all"]["mean_pass_at_k"], 0.75)

        s1_m = report["seeds"]["1"]
        self.assertEqual(s1_m["active"]["n_problems"], 3)
        self.assertAlmostEqual(s1_m["active"]["mean_pass_at_1"], 7 / 12)
        self.assertAlmostEqual(s1_m["active"]["mean_pass_at_k"], 1.0)
        self.assertEqual(s1_m["all"]["n_problems"], 4)
        self.assertAlmostEqual(s1_m["all"]["mean_pass_at_1"], 0.5625)
        self.assertAlmostEqual(s1_m["all"]["mean_pass_at_k"], 1.0)

        # 2. Stratification
        strat = report["stratification"]
        ins = strat["by_insight"]
        self.assertEqual(ins["insight"]["n_problems"], 2)
        self.assertAlmostEqual(ins["insight"]["mean_pass_at_1"]["0"], 0.5)
        self.assertAlmostEqual(ins["insight"]["mean_pass_at_1"]["1"], 0.625)
        self.assertEqual(ins["routine"]["n_problems"], 1)
        self.assertAlmostEqual(ins["routine"]["mean_pass_at_1"]["0"], 0.5)
        self.assertAlmostEqual(ins["routine"]["mean_pass_at_1"]["1"], 0.5)

        fam = strat["by_family"]
        self.assertEqual(fam["algebra"]["n_problems"], 2)
        self.assertAlmostEqual(fam["algebra"]["mean_pass_at_1"]["0"], 0.5)
        self.assertAlmostEqual(fam["algebra"]["mean_pass_at_1"]["1"], 0.625)
        self.assertEqual(fam["logic"]["n_problems"], 1)
        self.assertAlmostEqual(fam["logic"]["mean_pass_at_1"]["0"], 0.5)
        self.assertAlmostEqual(fam["logic"]["mean_pass_at_1"]["1"], 0.5)

        # 3. Noise floor
        nf_act = report["noise_floor"]["active"]
        self.assertEqual(nf_act["n_problems"], 3)
        self.assertEqual(nf_act["counts"]["0.0"], 2)
        self.assertEqual(nf_act["counts"]["0.125"], 0)
        self.assertEqual(nf_act["counts"]["0.25"], 1)
        self.assertEqual(nf_act["counts"][">0.25"], 0)
        self.assertAlmostEqual(nf_act["median"], 0.0)
        self.assertAlmostEqual(nf_act["max"], 0.25)
        self.assertAlmostEqual(nf_act["mean_diff"], 1 / 12)

        nf_all = report["noise_floor"]["all"]
        self.assertEqual(nf_all["n_problems"], 4)
        self.assertEqual(nf_all["counts"]["0.0"], 2)
        self.assertEqual(nf_all["counts"]["0.125"], 0)
        self.assertEqual(nf_all["counts"]["0.25"], 1)
        self.assertEqual(nf_all["counts"][">0.25"], 1)
        self.assertAlmostEqual(nf_all["max"], 0.5)
        self.assertAlmostEqual(nf_all["mean_diff"], -0.0625)

        # 4. Saturation
        sat = report["saturation"]
        self.assertEqual(sat["insight"]["ceiling"], 1)
        self.assertEqual(sat["insight"]["middle"], 1)
        self.assertEqual(sat["insight"]["floor"], 0)
        self.assertEqual(sat["routine"]["ceiling"], 0)
        self.assertEqual(sat["routine"]["middle"], 1)
        self.assertEqual(sat["routine"]["floor"], 0)
        self.assertEqual(sat["total"]["ceiling"], 1)
        self.assertEqual(sat["total"]["middle"], 2)
        self.assertEqual(sat["total"]["floor"], 0)

        # 5. Table formatting renders without crash
        table_text = b0.format_table(report)
        self.assertIn("1. Overall Seed Performance", table_text)
        self.assertIn("2. Stratification", table_text)
        self.assertIn("3. Seed Noise Floor", table_text)
        self.assertIn("4. Combined Seed Saturation", table_text)


class InputValidationTest(unittest.TestCase):
    def make_run_dir(self, parent, name, pp, status="ok", k=8):
        d = parent / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "summary.json").write_text(
            json.dumps({"status": status, "summary": {"k": k, "per_problem": pp}}),
            encoding="utf-8",
        )
        return d

    def make_benchmark_file(self, parent, problems):
        p = parent / "problems.json"
        p.write_text(json.dumps({"problems": problems}), encoding="utf-8")
        return p

    def test_missing_summary_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bench = self.make_benchmark_file(tmp, [{"name": "p1"}])
            empty_dir = tmp / "empty"
            empty_dir.mkdir()
            with contextlib.redirect_stderr(io.StringIO()):
                code = b0.main([
                    "--seed-runs", f"0:{empty_dir}",
                    "--seed-runs", f"1:{empty_dir}",
                    "--benchmark", str(bench),
                ])
            self.assertEqual(code, 2)

    def test_status_not_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bench = self.make_benchmark_file(tmp, [{"name": "p1"}])
            d0 = self.make_run_dir(tmp, "d0", {"p1": {"c": 8, "n": 8, "pass_at_1": 1.0, "pass_at_k": 1.0}}, status="failed")
            with contextlib.redirect_stderr(io.StringIO()):
                code = b0.main([
                    "--seed-runs", f"0:{d0}",
                    "--seed-runs", f"1:{d0}",
                    "--benchmark", str(bench),
                ])
            self.assertEqual(code, 2)

    def test_k_or_n_inconsistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bench = self.make_benchmark_file(tmp, [{"name": "p1"}, {"name": "p2"}])
            # d0 has k=8, but p1 has n=4
            d0 = self.make_run_dir(tmp, "d0", {"p1": {"c": 4, "n": 4, "pass_at_1": 1.0, "pass_at_k": 1.0}}, k=8)
            with contextlib.redirect_stderr(io.StringIO()):
                code = b0.main([
                    "--seed-runs", f"0:{d0}",
                    "--seed-runs", f"1:{d0}",
                    "--benchmark", str(bench),
                ])
            self.assertEqual(code, 2)

    def test_duplicate_problem_same_seed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bench = self.make_benchmark_file(tmp, [{"name": "p1"}])
            d1 = self.make_run_dir(tmp, "d1", {"p1": {"c": 8, "n": 8, "pass_at_1": 1.0, "pass_at_k": 1.0}})
            d2 = self.make_run_dir(tmp, "d2", {"p1": {"c": 8, "n": 8, "pass_at_1": 1.0, "pass_at_k": 1.0}})
            # d1 and d2 both passed to seed 0 -> duplicate problem p1
            with contextlib.redirect_stderr(io.StringIO()):
                code = b0.main([
                    "--seed-runs", f"0:{d1},{d2}",
                    "--seed-runs", f"1:{d1}",
                    "--benchmark", str(bench),
                ])
            self.assertEqual(code, 2)

    def test_problem_not_in_problems_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bench = self.make_benchmark_file(tmp, [{"name": "p_valid"}])
            d0 = self.make_run_dir(tmp, "d0", {"p_unknown": {"c": 8, "n": 8, "pass_at_1": 1.0, "pass_at_k": 1.0}})
            with contextlib.redirect_stderr(io.StringIO()):
                code = b0.main([
                    "--seed-runs", f"0:{d0}",
                    "--seed-runs", f"1:{d0}",
                    "--benchmark", str(bench),
                ])
            self.assertEqual(code, 2)

    def test_problem_sets_differ_between_seeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bench = self.make_benchmark_file(tmp, [{"name": "p1"}, {"name": "p2"}])
            d0 = self.make_run_dir(tmp, "d0", {"p1": {"c": 8, "n": 8, "pass_at_1": 1.0, "pass_at_k": 1.0}})
            d1 = self.make_run_dir(tmp, "d1", {"p2": {"c": 8, "n": 8, "pass_at_1": 1.0, "pass_at_k": 1.0}})
            err_buf = io.StringIO()
            with contextlib.redirect_stderr(err_buf):
                code = b0.main([
                    "--seed-runs", f"0:{d0}",
                    "--seed-runs", f"1:{d1}",
                    "--benchmark", str(bench),
                ])
            self.assertEqual(code, 2)
            self.assertIn("problem sets differ", err_buf.getvalue())

    def test_bootstrap_seed_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            problems = [{"name": f"p{i}"} for i in range(10)]
            bench = self.make_benchmark_file(tmp, problems)
            pp0 = {
                f"p{i}": {"c": i % 8, "n": 8, "pass_at_1": (i % 8) / 8.0, "pass_at_k": 1.0 if (i % 8) > 0 else 0.0}
                for i in range(10)
            }
            pp1 = {
                f"p{i}": {"c": (i + 1) % 8, "n": 8, "pass_at_1": ((i + 1) % 8) / 8.0, "pass_at_k": 1.0}
                for i in range(10)
            }
            d0 = self.make_run_dir(tmp, "d0", pp0)
            d1 = self.make_run_dir(tmp, "d1", pp1)

            out1, out2, out3 = tmp / "o1.json", tmp / "o2.json", tmp / "o3.json"
            b0.main([
                "--seed-runs", f"0:{d0}", "--seed-runs", f"1:{d1}",
                "--benchmark", str(bench), "--bootstrap-seed", "7", "--resamples", "500",
                "--out", str(out1),
            ])
            b0.main([
                "--seed-runs", f"0:{d0}", "--seed-runs", f"1:{d1}",
                "--benchmark", str(bench), "--bootstrap-seed", "7", "--resamples", "500",
                "--out", str(out2),
            ])
            b0.main([
                "--seed-runs", f"0:{d0}", "--seed-runs", f"1:{d1}",
                "--benchmark", str(bench), "--bootstrap-seed", "8", "--resamples", "500",
                "--out", str(out3),
            ])

            self.assertEqual(out1.read_text(), out2.read_text())
            data1 = json.loads(out1.read_text())
            data3 = json.loads(out3.read_text())
            self.assertNotEqual(
                data1["seeds"]["0"]["active"]["ci95_pass_at_1"],
                data3["seeds"]["0"]["active"]["ci95_pass_at_1"],
            )


class RealRunIntegrationTest(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]
    RUN_S0_PART1 = ROOT / "runs" / "20261103T122531Z_b0"
    RUN_S0_PART2 = ROOT / "runs" / "20261104T141934Z_b0-merged"
    RUN_S1_PART1 = ROOT / "runs" / "20261104T054619Z_b0-merged"
    RUN_S1_PART2 = ROOT / "runs" / "20261104T150345Z_b0-merged"
    BENCHMARK = ROOT / "benchmark" / "lean_hard"

    def _real_runs_available(self):
        return (
            self.RUN_S0_PART1.is_dir()
            and self.RUN_S0_PART2.is_dir()
            and self.RUN_S1_PART1.is_dir()
            and self.RUN_S1_PART2.is_dir()
            and self.BENCHMARK.is_dir()
        )

    def test_original_89_problems(self):
        """驗證驗收標準：原 89 題目錄執行結果。

        預期：全部題 mean pass@1: seed 0 為 0.7374、seed 1 為 0.7303；
        原 89 題 |Δpass@1| 分布：0 有 74 題、0.125 有 11 題、0.25 有 4 題，
        median 0、p90 0.125、max 0.25。
        """
        if not (self.RUN_S0_PART1.is_dir() and self.RUN_S1_PART1.is_dir() and self.BENCHMARK.is_dir()):
            self.skipTest("89-problem run directories not found")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = b0.main([
                "--seed-runs", f"0:{self.RUN_S0_PART1}",
                "--seed-runs", f"1:{self.RUN_S1_PART1}",
                "--benchmark", str(self.BENCHMARK),
                "--resamples", "500",
            ])
        self.assertEqual(code, 0)
        report = json.loads(buf.getvalue())

        # 89 problems mean pass@1
        s0_p1 = report["seeds"]["0"]["all"]["mean_pass_at_1"]
        s1_p1 = report["seeds"]["1"]["all"]["mean_pass_at_1"]
        self.assertAlmostEqual(s0_p1, 0.7374, places=4)
        self.assertAlmostEqual(s1_p1, 0.7303, places=4)

        # 89 problems noise floor
        nf = report["noise_floor"]["all"]
        self.assertEqual(nf["n_problems"], 89)
        self.assertEqual(nf["counts"]["0.0"], 74)
        self.assertEqual(nf["counts"]["0.125"], 11)
        self.assertEqual(nf["counts"]["0.25"], 4)
        self.assertEqual(nf["counts"][">0.25"], 0)
        self.assertAlmostEqual(nf["median"], 0.0)
        self.assertAlmostEqual(nf["p90"], 0.125)
        self.assertAlmostEqual(nf["max"], 0.25)

    def test_full_real_runs_statistics(self):
        """驗證驗收標準：全 4 目錄執行結果。

        全部題 109 題。
        飽和分類（只含啟用題）：
        - insight（共 46 題）：天花板 5、中段 19、地板 22；
        - routine（啟用題）：天花板 39（若 49 題啟用）或 37（若 46 題啟用，3 題退役）。
        """
        if not self._real_runs_available():
            self.skipTest("real run directories not available")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = b0.main([
                "--seed-runs", f"0:{self.RUN_S0_PART1},{self.RUN_S0_PART2}",
                "--seed-runs", f"1:{self.RUN_S1_PART1},{self.RUN_S1_PART2}",
                "--benchmark", str(self.BENCHMARK),
                "--resamples", "1000",
            ])
        self.assertEqual(code, 0)
        report = json.loads(buf.getvalue())

        # 總題數 109
        self.assertEqual(report["seeds"]["0"]["all"]["n_problems"], 109)
        self.assertEqual(report["seeds"]["1"]["all"]["n_problems"], 109)

        # 飽和分類
        sat = report["saturation"]
        # insight 固定 46 題
        self.assertEqual(sat["insight"]["n_problems"], 46)
        self.assertEqual(sat["insight"]["ceiling"], 5)
        self.assertEqual(sat["insight"]["middle"], 19)
        self.assertEqual(sat["insight"]["floor"], 22)

        # routine
        self.assertIn(sat["routine"]["n_problems"], (46, 49))
        if sat["routine"]["n_problems"] == 49:
            self.assertEqual(sat["routine"]["ceiling"], 39)
            self.assertEqual(sat["routine"]["middle"], 9)
            self.assertEqual(sat["routine"]["floor"], 1)
        else:
            self.assertEqual(sat["routine"]["ceiling"], 37)
            self.assertEqual(sat["routine"]["middle"], 8)
            self.assertEqual(sat["routine"]["floor"], 1)


class CliTest(unittest.TestCase):
    def test_cli_table_flag(self):
        root = Path(__file__).resolve().parents[1]
        r0 = root / "runs" / "20261103T122531Z_b0"
        r1 = root / "runs" / "20261104T054619Z_b0-merged"
        bench = root / "benchmark" / "lean_hard"
        if not (r0.is_dir() and r1.is_dir() and bench.is_dir()):
            self.skipTest("runs not found")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = b0.main([
                "--seed-runs", f"0:{r0}",
                "--seed-runs", f"1:{r1}",
                "--benchmark", str(bench),
                "--table",
                "--resamples", "100",
            ])
        self.assertEqual(code, 0)
        text = buf.getvalue()
        self.assertIn("1. Overall Seed Performance", text)
        self.assertIn("2. Stratification", text)
        self.assertIn("3. Seed Noise Floor", text)
        self.assertIn("4. Combined Seed Saturation", text)


if __name__ == "__main__":
    unittest.main()
