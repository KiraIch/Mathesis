import tempfile
import unittest
from pathlib import Path
from mathesis.controller import ImpasseController
from mathesis.impasse import ImpasseDetector
from mathesis.experiment import (
    format_summary_table,
    load_problems,
    run_pilot,
    run_single,
    summarize_config,
)


class ExperimentTest(unittest.TestCase):
    def test_load_problems(self):
        root = Path(__file__).resolve().parents[1]
        path = root / "benchmark" / "pilot" / "problems.json"
        problems = load_problems(path)
        self.assertGreaterEqual(len(problems), 8)
        self.assertLessEqual(len(problems), 10)
        names = [item.name for item in problems]
        self.assertIn("identity", names)
        self.assertIn("chain_6", names)
        insights = [item for item in problems if item.insight]
        self.assertGreaterEqual(len(insights), 5)
        routines = [item for item in problems if not item.insight]
        self.assertGreaterEqual(len(routines), 3)
        for item in problems:
            self.assertTrue(item.theorem)
            self.assertGreater(item.budget_nodes, 0)
            self.assertTrue(item.reference_proof)

    def test_pilot_runs(self):
        root = Path(__file__).resolve().parents[1]
        path = root / "benchmark" / "pilot" / "problems.json"
        results = run_pilot(path, budget_wall_ms=5000)
        for expected in [
            "Mathesis",
            "AlwaysRestructure",
            "FixedSchedule",
            "RandomTrigger",
        ]:
            self.assertIn(expected, results)
        problems = load_problems(path)
        for config_results in results.values():
            self.assertEqual(len(config_results), len(problems))
        table = format_summary_table(results)
        self.assertIn("solve_rate", table)
        self.assertIn("Mathesis", table)

    def test_summarize(self):
        from mathesis.types import Cost, SearchResult
        ok = SearchResult(
            success=True,
            proof=("intro h", "exact h"),
            nodes=4,
            cost=Cost(lean_heartbeats=8, search_nodes=4, wall_ms=3),
            impasse_count=1,
            operator_uses=1,
            trace=(),
        )
        failed = SearchResult(
            success=False,
            proof=(),
            nodes=10,
            cost=Cost(lean_heartbeats=20, search_nodes=10, wall_ms=5),
            impasse_count=2,
            operator_uses=0,
            trace=(),
        )
        summary = summarize_config({"a": ok, "b": failed})
        self.assertAlmostEqual(summary["solve_rate"], 0.5)
        self.assertAlmostEqual(summary["mean_nodes"], 7.0)

    def test_reference_proofs_replay(self):
        from mathesis.backend import MockLeanBackend
        root = Path(__file__).resolve().parents[1]
        path = root / "benchmark" / "pilot" / "problems.json"
        problems = load_problems(path)
        backend = MockLeanBackend()
        for problem in problems:
            self.assertTrue(
                backend.check_proof(problem.theorem, list(problem.reference_proof)),
                "reference proof failed for " + problem.name,
            )

    def test_natural_impasse_path(self):
        root = Path(__file__).resolve().parents[1]
        path = root / "benchmark" / "pilot" / "problems.json"
        problems = load_problems(path)
        hits = []
        for problem in problems:
            # legacy weights: this path relied on the 0.2 budget-fraction term
            legacy = ImpasseDetector(budget=problem.budget_nodes, budget_weight=0.2)
            outcome = run_single(problem, ImpasseController(), detector=legacy)
            if outcome.impasse_count > 0 and outcome.operator_uses > 0:
                hits.append(problem.name)
        self.assertGreaterEqual(len(hits), 1)

    def test_tmp_load(self):
        payload = (
            '{"problems": ['
            '{"name": "tmp", "theorem": "P -> P", "family": "implication", '
            '"insight": false, "reference_proof": ["intro h", "exact h"], '
            '"budget_nodes": 10}]}'
        )
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "problems.json"
            target.write_text(payload, encoding="utf-8")
            problems = load_problems(target)
            self.assertEqual(len(problems), 1)
            self.assertEqual(problems[0].name, "tmp")


if __name__ == "__main__":
    unittest.main()
