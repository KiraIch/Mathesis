import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "hint_significance.py"
_spec = importlib.util.spec_from_file_location("hint_significance", SCRIPT)
hs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hs)


class FisherExactTest(unittest.TestCase):
    def test_known_drinker_implication(self):
        # 27/32 vs 3/32: p < 0.0001 (exact: ~1.255e-9)
        table = [[27, 5], [3, 29]]
        p = hs.fisher_exact_2x2(table)
        self.assertLess(p, 0.0001)
        self.assertAlmostEqual(p, 1.2551106092146884e-09, delta=1e-12)

    def test_known_nat_sum_even(self):
        # 14/32 vs 5/32: p ≈ 0.027
        table = [[14, 18], [5, 27]]
        p = hs.fisher_exact_2x2(table)
        self.assertAlmostEqual(p, 0.0271922596, places=4)

    def test_known_zero_vs_zero(self):
        # 0/32 vs 0/32: p = 1.0
        table = [[0, 32], [0, 32]]
        p = hs.fisher_exact_2x2(table)
        self.assertEqual(p, 1.0)

    def test_known_ineq_sq_sum_abc_four(self):
        # 8/32 vs 0/32: p ≈ 0.0048
        table = [[8, 24], [0, 32]]
        p = hs.fisher_exact_2x2(table)
        self.assertAlmostEqual(p, 0.00475278, places=4)

    def test_known_ceiling_vs_ceiling(self):
        # 32/32 vs 32/32: p = 1.0
        table = [[32, 0], [32, 0]]
        p = hs.fisher_exact_2x2(table)
        self.assertEqual(p, 1.0)

    def test_symmetry(self):
        # Swapping rows or columns gives identical two-tailed p-value
        table = [[14, 18], [5, 27]]
        p1 = hs.fisher_exact_2x2(table)
        p2 = hs.fisher_exact_2x2([[5, 27], [14, 18]])  # swap rows
        p3 = hs.fisher_exact_2x2([[18, 14], [27, 5]])  # swap cols
        p4 = hs.fisher_exact_2x2([[27, 5], [18, 14]])  # transpose
        self.assertEqual(p1, p2)
        self.assertEqual(p1, p3)
        self.assertEqual(p1, p4)

    def test_invalid_table_inputs(self):
        with self.assertRaises(ValueError):
            hs.fisher_exact_2x2([[1, 2, 3], [4, 5, 6]])
        with self.assertRaises(ValueError):
            hs.fisher_exact_2x2([[-1, 33], [5, 27]])


class HolmBonferroniTest(unittest.TestCase):
    def test_empty_list(self):
        self.assertEqual(hs.holm_bonferroni([]), [])

    def test_single_value(self):
        self.assertEqual(hs.holm_bonferroni([0.02]), [0.02])
        self.assertEqual(hs.holm_bonferroni([1.0]), [1.0])

    def test_step_down_hand_calculated(self):
        raw = [0.01, 0.04, 0.03, 0.005]
        # m=4
        # sorted: 0.005 (idx 3), 0.01 (idx 0), 0.03 (idx 2), 0.04 (idx 1)
        # rank 0: 0.005 * 4 = 0.02 -> cum_max=0.02 -> idx 3: 0.02
        # rank 1: 0.01 * 3 = 0.03 -> cum_max=0.03 -> idx 0: 0.03
        # rank 2: 0.03 * 2 = 0.06 -> cum_max=0.06 -> idx 2: 0.06
        # rank 3: 0.04 * 1 = 0.04 -> cum_max=max(0.06, 0.04)=0.06 -> idx 1: 0.06
        expected = [0.03, 0.06, 0.06, 0.02]
        self.assertEqual(hs.holm_bonferroni(raw), expected)

    def test_capped_at_one(self):
        raw = [0.6, 0.7, 0.8]
        adjusted = hs.holm_bonferroni(raw)
        self.assertEqual(adjusted, [1.0, 1.0, 1.0])


class PrimaryAndSensitivityHolmTest(unittest.TestCase):
    """驗證主要分析（informative）與敏感度分析（all tested）在手算小例子的行為。"""

    def test_hand_calculated_family_difference(self):
        """手算過程說明：

        定義 4 道題目（均 n=32）：
          p1: plain 0/32, hint 8/32
              Fisher 2x2 = [[8, 24], [0, 32]] => p ≈ 0.0047527822
              gap = +0.25 > 0, plain.c + hint.c = 8 >= 1 => informative=True
          p2: plain 5/32, hint 14/32
              Fisher 2x2 = [[14, 18], [5, 27]] => p ≈ 0.0271922596
              gap = +0.28125 > 0, plain.c + hint.c = 19 >= 1 => informative=True
          p3: plain 0/32, hint 0/32
              Fisher 2x2 = [[0, 32], [0, 32]] => p = 1.0
              gap = 0.0, plain.c + hint.c = 0 < 1 => informative=False
          p4: plain 32/32, hint 32/32
              plain 天花板（plain.c == plain.n） => 不檢定，informative=False

        1. 主要分析家族（informative=True）：只有 p1 與 p2，m_info = 2。
           依 p 值升冪排序：
             rank 0: p1 (p ≈ 0.00475278), multiplier = 2 - 0 = 2
                     p_holm = 2 * 0.0047527822 = 0.0095055644
                     gap > 0 且 p_holm < 0.05 => hint_helps_holm = True
             rank 1: p2 (p ≈ 0.02719226), multiplier = 2 - 1 = 1
                     p_holm = max(0.0095055644, 1 * 0.0271922596) = 0.0271922596
                     gap > 0 且 p_holm < 0.05 => hint_helps_holm = True
           未在主要家族中的題目：
             p3: p_holm = None, hint_helps_holm = False
             p4: p_holm = None, hint_helps_holm = False

        2. 敏感度分析家族（所有非天花板題）：包含 p1, p2, p3，m_all = 3。
           依 p 值升冪排序：
             rank 0: p1 (p ≈ 0.00475278), multiplier = 3 - 0 = 3
                     p_holm_all = 3 * 0.0047527822 = 0.0142583466
                     gap > 0 且 p_holm_all < 0.05 => hint_helps_holm_all = True
             rank 1: p2 (p ≈ 0.02719226), multiplier = 3 - 1 = 2
                     p_holm_all = max(0.0142583466, 2 * 0.0271922596) = 0.0543845192
                     p_holm_all > 0.05 => hint_helps_holm_all = False （敏感度分析下失去顯著性！）
             rank 2: p3 (p = 1.0), multiplier = 3 - 2 = 1
                     p_holm_all = max(0.0543845192, 1 * 1.0) = 1.0
                     hint_helps_holm_all = False
           天花板題：
             p4: p_holm_all = None, hint_helps_holm_all = False
        """
        data = {
            "p1": {"plain": {"c": 0, "n": 32}, "hint": {"c": 8, "n": 32}},
            "p2": {"plain": {"c": 5, "n": 32}, "hint": {"c": 14, "n": 32}},
            "p3": {"plain": {"c": 0, "n": 32}, "hint": {"c": 0, "n": 32}},
            "p4": {"plain": {"c": 32, "n": 32}, "hint": {"c": 32, "n": 32}},
        }
        report = hs.build_significance_report(data)
        pp = report["per_problem"]

        # p1 驗證
        self.assertTrue(pp["p1"]["informative"])
        self.assertAlmostEqual(pp["p1"]["p_holm"], 0.00950556, places=6)
        self.assertAlmostEqual(pp["p1"]["p_holm_all"], 0.01425835, places=6)
        self.assertTrue(pp["p1"]["hint_helps_holm"])
        self.assertTrue(pp["p1"]["hint_helps_holm_all"])

        # p2 驗證（主要顯著，敏感度不顯著）
        self.assertTrue(pp["p2"]["informative"])
        self.assertAlmostEqual(pp["p2"]["p_holm"], 0.02719226, places=6)
        self.assertAlmostEqual(pp["p2"]["p_holm_all"], 0.05438452, places=6)
        self.assertTrue(pp["p2"]["hint_helps_holm"])
        self.assertFalse(pp["p2"]["hint_helps_holm_all"])

        # p3: 兩條件均 0 成功
        self.assertFalse(pp["p3"]["informative"])
        self.assertTrue(pp["p3"]["tested"])
        self.assertEqual(pp["p3"]["p"], 1.0)
        self.assertIsNone(pp["p3"]["p_holm"])
        self.assertIsNotNone(pp["p3"]["p_holm_all"])
        self.assertEqual(pp["p3"]["p_holm_all"], 1.0)
        self.assertFalse(pp["p3"]["hint_helps_holm"])
        self.assertFalse(pp["p3"]["hint_helps_holm_all"])

        # p4: plain 天花板
        self.assertFalse(pp["p4"]["informative"])
        self.assertFalse(pp["p4"]["tested"])
        self.assertIsNone(pp["p4"]["p"])
        self.assertIsNone(pp["p4"]["p_holm"])
        self.assertIsNone(pp["p4"]["p_holm_all"])
        self.assertEqual(pp["p4"]["classification"], "plain_ceiling")
        self.assertFalse(pp["p4"]["hint_helps_holm"])
        self.assertFalse(pp["p4"]["hint_helps_holm_all"])

        # Summary 驗證
        s = report["summary"]
        self.assertEqual(s["n_problems"], 4)
        self.assertEqual(s["n_tested"], 3)
        self.assertEqual(s["n_informative"], 2)
        self.assertEqual(s["n_hint_helps"], 2)
        self.assertEqual(s["n_hint_helps_holm"], 2)
        self.assertEqual(s["n_hint_helps_holm_all"], 1)
        self.assertEqual(s["n_passing_holm"], 2)

    def test_zero_success_problem_attributes(self):
        """驗證驗收標準 b：兩條件都 0 成功的題 informative=False, p_holm=None, p_holm_all 不為 None。"""
        data = {
            "p_zero": {"plain": {"c": 0, "n": 32}, "hint": {"c": 0, "n": 32}},
            "p_other": {"plain": {"c": 1, "n": 32}, "hint": {"c": 2, "n": 32}},
        }
        report = hs.build_significance_report(data)
        item = report["per_problem"]["p_zero"]
        self.assertFalse(item["informative"])
        self.assertTrue(item["tested"])
        self.assertEqual(item["p"], 1.0)
        self.assertIsNone(item["p_holm"])
        self.assertIsNotNone(item["p_holm_all"])
        self.assertEqual(item["classification"], "no_detectable_effect")

    def test_plain_ceiling_problem_attributes(self):
        """驗證驗收標準 c：plain 天花板題 informative=False, p_holm=None, p_holm_all=None。"""
        data = {
            "p_ceil": {"plain": {"c": 32, "n": 32}, "hint": {"c": 32, "n": 32}},
            "p_other": {"plain": {"c": 2, "n": 32}, "hint": {"c": 5, "n": 32}},
        }
        report = hs.build_significance_report(data)
        item = report["per_problem"]["p_ceil"]
        self.assertFalse(item["informative"])
        self.assertFalse(item["tested"])
        self.assertIsNone(item["p"])
        self.assertIsNone(item["p_holm"])
        self.assertIsNone(item["p_holm_all"])
        self.assertEqual(item["classification"], "plain_ceiling")


class ClassificationAndReportTest(unittest.TestCase):
    def test_classification_categories(self):
        data = {
            "p_helps": {
                "plain": {"c": 3, "n": 32},
                "hint": {"c": 27, "n": 32},
            },
            "p_hurts": {
                "plain": {"c": 27, "n": 32},
                "hint": {"c": 3, "n": 32},
            },
            "p_no_effect": {
                "plain": {"c": 5, "n": 32},
                "hint": {"c": 6, "n": 32},
            },
            "p_ceiling": {
                "plain": {"c": 32, "n": 32},
                "hint": {"c": 32, "n": 32},
            },
        }
        report = hs.build_significance_report(data)
        summary = report["summary"]
        self.assertEqual(summary["n_problems"], 4)
        self.assertEqual(summary["n_tested"], 3)
        self.assertEqual(summary["n_informative"], 3)
        self.assertEqual(summary["n_hint_helps"], 1)
        self.assertEqual(summary["n_hint_hurts"], 1)
        self.assertEqual(summary["n_no_detectable_effect"], 1)
        self.assertEqual(summary["n_plain_ceiling"], 1)

        pp = report["per_problem"]
        self.assertEqual(pp["p_helps"]["classification"], "hint_helps")
        self.assertTrue(pp["p_helps"]["tested"])
        self.assertTrue(pp["p_helps"]["informative"])
        self.assertIsNotNone(pp["p_helps"]["p"])
        self.assertIsNotNone(pp["p_helps"]["p_holm"])
        self.assertIsNotNone(pp["p_helps"]["p_holm_all"])

        self.assertEqual(pp["p_hurts"]["classification"], "hint_hurts")
        self.assertTrue(pp["p_hurts"]["informative"])
        self.assertFalse(pp["p_hurts"]["hint_helps_holm"])
        self.assertFalse(pp["p_hurts"]["hint_helps_holm_all"])

        self.assertEqual(pp["p_no_effect"]["classification"], "no_detectable_effect")
        self.assertTrue(pp["p_no_effect"]["informative"])
        self.assertFalse(pp["p_no_effect"]["hint_helps_holm"])
        self.assertFalse(pp["p_no_effect"]["hint_helps_holm_all"])

        self.assertEqual(pp["p_ceiling"]["classification"], "plain_ceiling")
        self.assertFalse(pp["p_ceiling"]["informative"])
        self.assertFalse(pp["p_ceiling"]["tested"])
        self.assertIsNone(pp["p_ceiling"]["p"])
        self.assertIsNone(pp["p_ceiling"]["p_holm"])
        self.assertIsNone(pp["p_ceiling"]["p_holm_all"])
        self.assertFalse(pp["p_ceiling"]["hint_helps_holm"])
        self.assertFalse(pp["p_ceiling"]["hint_helps_holm_all"])


class DirectoryLoadingAndValidationTest(unittest.TestCase):
    def test_missing_directory(self):
        with self.assertRaises(hs.SignificanceError):
            hs.load_run_summary(Path("nonexistent_path_xyz"))

    def test_missing_summary_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(hs.SignificanceError):
                hs.load_run_summary(Path(tmp))

    def test_status_not_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "summary.json"
            p.write_text(json.dumps({"status": "failed", "error": "timeout"}), encoding="utf-8")
            with self.assertRaises(hs.SignificanceError):
                hs.load_run_summary(Path(tmp))

    def test_n_not_32(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "summary.json"
            content = {
                "status": "ok",
                "summary": {
                    "per_problem": {
                        "prob1": {
                            "plain": {"c": 1, "n": 16},
                            "hint": {"c": 2, "n": 16},
                        }
                    }
                },
            }
            p.write_text(json.dumps(content), encoding="utf-8")
            with self.assertRaises(hs.SignificanceError):
                hs.load_run_summary(Path(tmp))

    def test_duplicate_problem_handling(self):
        def make_dir(tmp, name, c_plain):
            d = Path(tmp) / name
            d.mkdir()
            content = {
                "status": "ok",
                "summary": {
                    "per_problem": {
                        "shared_prob": {
                            "plain": {"c": c_plain, "n": 32},
                            "hint": {"c": 10, "n": 32},
                        }
                    }
                },
            }
            (d / "summary.json").write_text(json.dumps(content), encoding="utf-8")
            return d

        with tempfile.TemporaryDirectory() as tmp:
            d1 = make_dir(tmp, "run1", 2)
            d2 = make_dir(tmp, "run2", 4)

            # Duplicate without prefer_last raises SignificanceError
            with self.assertRaises(hs.SignificanceError):
                hs.load_and_merge_runs([d1, d2], prefer_last=False)

            # With prefer_last, keeps d2's plain c=4
            merged = hs.load_and_merge_runs([d1, d2], prefer_last=True)
            self.assertEqual(merged["shared_prob"]["plain"]["c"], 4)


class KnownDatasetIntegrationTest(unittest.TestCase):
    KNOWN_RUN = Path(__file__).resolve().parents[1] / "runs" / "20261104T131752Z_hint-gap-merged"

    def test_reproduces_known_run_statistics(self):
        if not self.KNOWN_RUN.is_dir():
            self.skipTest("known run directory not found")

        problems = hs.load_run_summary(self.KNOWN_RUN)
        report = hs.build_significance_report(problems)
        pp = report["per_problem"]

        # Summary checks: 23 total, 23 tested, 11 informative
        s = report["summary"]
        self.assertEqual(s["n_problems"], 23)
        self.assertEqual(s["n_tested"], 23)
        self.assertEqual(s["n_informative"], 11)
        self.assertEqual(s["n_hint_helps"], 3)
        self.assertEqual(s["n_hint_hurts"], 0)
        self.assertEqual(s["n_no_detectable_effect"], 20)
        self.assertEqual(s["n_plain_ceiling"], 0)
        self.assertEqual(s["n_hint_helps_holm"], 2)       # 主要分析通過題數
        self.assertEqual(s["n_hint_helps_holm_all"], 1)   # 敏感度分析通過題數
        self.assertEqual(s["n_passing_holm"], 2)

        # drinker_implication: plain 3/32 hint 27/32 p < 0.0001, p_holm < 0.0001
        drinker = pp["lean_logic_drinker_implication"]
        self.assertEqual(drinker["plain"]["c"], 3)
        self.assertEqual(drinker["hint"]["c"], 27)
        self.assertLess(drinker["p"], 0.0001)
        self.assertLess(drinker["p_holm"], 0.0001)
        self.assertLess(drinker["p_holm_all"], 0.0001)
        self.assertEqual(drinker["classification"], "hint_helps")
        self.assertTrue(drinker["hint_helps_holm"])
        self.assertTrue(drinker["hint_helps_holm_all"])

        # ineq_sq_sum_abc_four: 0/32 vs 8/32 p ≈ 0.0048, p_holm ≈ 0.0475, p_holm_all ≈ 0.1046
        ineq = pp["lean_ineq_sq_sum_abc_four"]
        self.assertEqual(ineq["plain"]["c"], 0)
        self.assertEqual(ineq["hint"]["c"], 8)
        self.assertAlmostEqual(ineq["p"], 0.0048, places=4)
        self.assertAlmostEqual(ineq["p_holm"], 0.0475, places=4)
        self.assertAlmostEqual(ineq["p_holm_all"], 0.1046, places=4)
        self.assertEqual(ineq["classification"], "hint_helps")
        self.assertTrue(ineq["hint_helps_holm"])
        self.assertFalse(ineq["hint_helps_holm_all"])

        # nat_sum_even: 5/32 vs 14/32 p ≈ 0.027, p_holm ≈ 0.2447, p_holm_all ≈ 0.5710
        nat = pp["lean_nat_sum_even"]
        self.assertEqual(nat["plain"]["c"], 5)
        self.assertEqual(nat["hint"]["c"], 14)
        self.assertAlmostEqual(nat["p"], 0.0272, places=3)
        self.assertAlmostEqual(nat["p_holm"], 0.2447, places=4)
        self.assertAlmostEqual(nat["p_holm_all"], 0.5710, places=4)
        self.assertEqual(nat["classification"], "hint_helps")
        self.assertFalse(nat["hint_helps_holm"])
        self.assertFalse(nat["hint_helps_holm_all"])

        # All other problems have p > 0.2
        significant_names = {
            "lean_logic_drinker_implication",
            "lean_nat_sum_even",
            "lean_ineq_sq_sum_abc_four",
        }
        for name, item in pp.items():
            if name not in significant_names:
                self.assertGreater(item["p"], 0.2, f"problem {name} expected p > 0.2, got {item['p']}")
                self.assertEqual(item["classification"], "no_detectable_effect")
                self.assertFalse(item["hint_helps_holm"])
                self.assertFalse(item["hint_helps_holm_all"])


class CliTest(unittest.TestCase):
    KNOWN_RUN = Path(__file__).resolve().parents[1] / "runs" / "20261104T131752Z_hint-gap-merged"

    def test_cli_stdout_json(self):
        if not self.KNOWN_RUN.is_dir():
            self.skipTest("known run directory not found")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = hs.main([str(self.KNOWN_RUN)])
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["summary"]["n_tested"], 23)
        self.assertEqual(data["summary"]["n_informative"], 11)
        self.assertEqual(data["summary"]["n_hint_helps"], 3)
        self.assertEqual(data["summary"]["n_hint_helps_holm"], 2)
        self.assertEqual(data["summary"]["n_hint_helps_holm_all"], 1)

    def test_cli_out_file(self):
        if not self.KNOWN_RUN.is_dir():
            self.skipTest("known run directory not found")

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "sub" / "report.json"
            code = hs.main([str(self.KNOWN_RUN), "--out", str(out_path)])
            self.assertEqual(code, 0)
            self.assertTrue(out_path.is_file())
            data = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(data["summary"]["n_tested"], 23)
            self.assertEqual(data["summary"]["n_informative"], 11)

    def test_cli_table_flag(self):
        if not self.KNOWN_RUN.is_dir():
            self.skipTest("known run directory not found")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = hs.main([str(self.KNOWN_RUN), "--table"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("Summary: tested=23/23", out)
        self.assertIn("informative=11", out)
        self.assertIn("passed_holm=2 (all=1)", out)
        self.assertIn("p_holm_all", out)
        self.assertIn("lean_logic_drinker_implication", out)
        idx_drinker = out.index("lean_logic_drinker_implication")
        idx_cube = out.index("lean_ineq_cube_sum_zero_sixth")
        self.assertLess(idx_drinker, idx_cube)

    def test_cli_error_returns_nonzero(self):
        err_buf = io.StringIO()
        with contextlib.redirect_stderr(err_buf):
            code = hs.main(["nonexistent_run_directory_12345"])
        self.assertNotEqual(code, 0)
        self.assertIn("error:", err_buf.getvalue())


if __name__ == "__main__":
    unittest.main()
