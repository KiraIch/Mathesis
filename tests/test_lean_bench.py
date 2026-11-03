import io
import os
import unittest
from contextlib import redirect_stdout

from mathesis.backend import MockLeanBackend
from mathesis.lean_bench import (
    LEAN_BENCH_ALL_CONFIGS,
    LEAN_BENCH_DEFAULT_CONFIGS,
    ORACLE_LABEL,
    format_lean_bench_rows,
    format_lean_bench_summary,
    imports_for_entry,
    make_lean_controller,
    make_lean_operators,
    oracle_haves_for,
    run_single_lean_config,
    select_lean_bench_problems,
)
from mathesis.operators import OracleHaveOperator, TemplateHaveOperator
from mathesis.search import (
    lean_intro_name,
    lean_tactic_portfolio,
    tactic_expansions,
)
from mathesis.types import Goal, Hypothesis, ProofState, make_atom


def make_lean_state(goal_text, hyps=(), token="0"):
    goals = (Goal(proposition=make_atom(goal_text)),) if goal_text else ()
    hypotheses = tuple(
        Hypothesis(name=name, proposition=make_atom(type_text))
        for name, type_text in hyps
    )
    return ProofState(
        goals=goals, hypotheses=hypotheses, pending=(), backend_token=token
    )


class LeanBenchUnitTest(unittest.TestCase):
    def test_oracle_haves_extract(self):
        reference = [
            "intro P",
            "have hQ : Q := hPQ hP",
            "exact hQR hQ",
            "have h : 0 ≤ a ^ 2 := sq_nonneg a",
        ]
        haves = oracle_haves_for(reference)
        self.assertEqual(len(haves), 2)
        self.assertIn("have hQ : Q := hPQ hP", haves)
        self.assertNotIn("intro P", haves)

    def test_imports_for_entry_default(self):
        self.assertEqual(imports_for_entry({"name": "x"}), ("Mathlib",))
        self.assertEqual(imports_for_entry({"imports": []}), ("Mathlib",))

    def test_imports_for_entry_custom(self):
        entry = {"name": "x", "imports": ["Mathlib", "Mathesis.Defs"]}
        self.assertEqual(
            imports_for_entry(entry), ("Mathlib", "Mathesis.Defs")
        )

    def test_oracle_haves_empty(self):
        self.assertEqual(oracle_haves_for(["intro h", "exact h"]), ())

    def test_lean_intro_preserves_forall(self):
        state = make_lean_state("∀ (P : Prop), P → P")
        self.assertEqual(lean_intro_name(state), "P")

    def test_lean_intro_second_binder(self):
        state = make_lean_state(
            "∀ (Q R : Prop), Q → R", hyps=(("P", "Prop"),)
        )
        self.assertEqual(lean_intro_name(state), "Q")

    def test_lean_intro_fresh_for_arrow(self):
        state = make_lean_state("P → Q", hyps=(("P", "Prop"),))
        name = lean_intro_name(state)
        self.assertTrue(name.startswith("h_"))
        self.assertNotIn(name, ["P"])

    def test_lean_portfolio_fixed_set(self):
        state = make_lean_state("P → P", hyps=(("h", "P"),))
        tactics = lean_tactic_portfolio(state)
        self.assertIn("simp", tactics)
        self.assertIn("omega", tactics)
        self.assertIn("constructor", tactics)
        self.assertIn("linarith", tactics)
        self.assertIn("nlinarith", tactics)
        self.assertIn("ring", tactics)
        self.assertIn("positivity", tactics)
        self.assertIn("norm_num", tactics)
        self.assertIn("exact h", tactics)
        self.assertIn("apply h", tactics)
        self.assertTrue(any(item.startswith("intro ") for item in tactics))
        for item in tactics:
            self.assertFalse(item.strip().startswith("have "))

    def test_tactic_branch_mock_vs_lean(self):
        from mathesis.types import parse_prop

        mock_state = ProofState(
            goals=(Goal(proposition=parse_prop("P -> P")),),
            hypotheses=(),
            pending=(),
            backend_token=None,
        )
        mock_tactics = tactic_expansions(mock_state)
        self.assertNotIn("simp", mock_tactics)
        lean_state = make_lean_state("P → P")
        lean_tactics = tactic_expansions(lean_state)
        self.assertIn("simp", lean_tactics)

    def test_oracle_propose_both_forms(self):
        backend = MockLeanBackend()
        operator = OracleHaveOperator(backend, ("have hQ : Q := hPQ hP",))
        state = make_lean_state("R")
        candidates = operator.propose(state, {})
        descriptions = [item.description for item in candidates]
        self.assertIn("have hQ : Q := hPQ hP", descriptions)
        self.assertIn("have hQ : Q", descriptions)

    def test_oracle_pre_empty(self):
        backend = MockLeanBackend()
        operator = OracleHaveOperator(backend, ())
        state = make_lean_state("R")
        self.assertFalse(operator.pre(state))
        self.assertEqual(operator.propose(state, {}), [])

    def test_template_empty_for_mock(self):
        backend = MockLeanBackend()
        operator = TemplateHaveOperator(backend)
        state = backend.reset("P -> P")
        self.assertEqual(operator.propose(state, {}), [])

    def test_template_forward_proposes(self):
        backend = MockLeanBackend()
        operator = TemplateHaveOperator(backend)
        state = make_lean_state(
            "R", hyps=(("hPQ", "P → Q"), ("hP", "P"), ("hQR", "Q → R"))
        )
        candidates = operator.propose(state, {})
        self.assertGreater(len(candidates), 0)
        first = candidates[0].description
        self.assertTrue(first.startswith("have "))
        self.assertIn(":=", first)

    def test_controllers_build(self):
        for name in LEAN_BENCH_ALL_CONFIGS:
            controller = make_lean_controller(name)
            self.assertTrue(controller.should_restructure(0, True) in (True, False))

    def test_operators_same_tactics_bfs_empty(self):
        backend = MockLeanBackend()
        self.assertEqual(make_lean_operators(backend, (), "bfs"), [])
        self.assertEqual(
            make_lean_operators(backend, ("have h : Q := hPQ hP",), "bfs"), []
        )
        operators = make_lean_operators(
            backend, ("have h : Q := hPQ hP",), "mathesis+oracle-have"
        )
        self.assertEqual(len(operators), 1)

    def test_operators_template_branch(self):
        from mathesis.operators import TemplateHaveOperator

        backend = MockLeanBackend()
        operators = make_lean_operators(backend, (), "bfs+template-have")
        self.assertEqual(len(operators), 1)
        self.assertIsInstance(operators[0], TemplateHaveOperator)
        operators = make_lean_operators(backend, (), "mathesis+template-have")
        self.assertEqual(len(operators), 1)
        self.assertIsInstance(operators[0], TemplateHaveOperator)
        operators = make_lean_operators(
            backend, ("have h : Q := hPQ hP",), "fixed+template-have"
        )
        self.assertEqual(len(operators), 1)
        self.assertIsInstance(operators[0], TemplateHaveOperator)
        operators = make_lean_operators(
            backend, ("have h : Q := hPQ hP",), "random+template-have"
        )
        self.assertEqual(len(operators), 1)
        self.assertIsInstance(operators[0], TemplateHaveOperator)
        operators = make_lean_operators(
            backend, ("have h : Q := hPQ hP",), "mathesis+template-have"
        )
        self.assertEqual(len(operators), 1)
        self.assertIsInstance(operators[0], TemplateHaveOperator)

    def test_template_label_shown_for_template_configs(self):
        from mathesis.lean_bench import TEMPLATE_LABEL
        from mathesis.types import Cost, SearchResult

        problems = [
            {"name": "demo", "theorem": "P → P", "reference_proof": []},
        ]
        outcome = SearchResult(
            success=True,
            proof=("simp",),
            nodes=2,
            cost=Cost(lean_heartbeats=2, search_nodes=2, wall_ms=8),
            impasse_count=0,
            operator_uses=1,
            trace=(),
        )
        results = {"mathesis+template-have": {"demo": outcome}}
        walls = {"mathesis+template-have": {"demo": 9}}
        errors = {"mathesis+template-have": {"demo": ""}}
        rows = format_lean_bench_rows(problems, results, walls, errors)
        summary = format_lean_bench_summary(results, walls)
        self.assertIn(TEMPLATE_LABEL, rows)
        self.assertIn(TEMPLATE_LABEL, summary)
        plain = format_lean_bench_summary(
            {"bfs": {"demo": outcome}}, {"bfs": {"demo": 9}}
        )
        self.assertNotIn(TEMPLATE_LABEL, plain)

    def test_default_configs(self):
        self.assertIn("bfs", LEAN_BENCH_DEFAULT_CONFIGS)
        self.assertIn("bfs+oracle-have", LEAN_BENCH_DEFAULT_CONFIGS)
        self.assertIn("mathesis+oracle-have", LEAN_BENCH_DEFAULT_CONFIGS)
        self.assertEqual(len(LEAN_BENCH_DEFAULT_CONFIGS), 4)

    def test_split_filter_counts(self):
        calib = select_lean_bench_problems(limit=50, split="calibration")
        test = select_lean_bench_problems(limit=50, split="test")
        everything = select_lean_bench_problems(limit=50)
        self.assertEqual(len(calib), 10)
        self.assertEqual(len(test), 40)
        self.assertEqual(len(everything), 50)
        names_calib = {entry["name"] for entry in calib}
        names_test = {entry["name"] for entry in test}
        self.assertEqual(len(names_calib & names_test), 0)
        for entry in calib:
            self.assertEqual(entry["bench_split"], "calibration")

    def test_select_rejects_limit_below_one(self):
        for limit in (0, -1):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    select_lean_bench_problems(limit=limit)

    def test_select_limit_none_returns_all(self):
        everything = select_lean_bench_problems(limit=None)
        self.assertEqual(len(everything), len(select_lean_bench_problems(limit=10000)))
        self.assertGreater(len(everything), 10)

    def test_single_config_accepts_detector_settings(self):
        backend = MockLeanBackend()
        result, wall_ms, error = run_single_lean_config(
            backend,
            "P -> P",
            [],
            "bfs",
            10,
            5,
            0.2,
            2,
            None,
        )
        self.assertEqual(error, "")
        self.assertGreaterEqual(wall_ms, 0)
        self.assertTrue(result.success)

    def test_search_initial_state_skips_reset(self):
        from mathesis.controller import ImpasseController
        from mathesis.impasse import ImpasseDetector
        from mathesis.search import breadth_first_search

        backend = MockLeanBackend()
        shared = backend.reset("P -> P")
        result = breadth_first_search(
            backend=backend,
            theorem="not a theorem (((",
            operators=[],
            controller=ImpasseController(),
            detector=ImpasseDetector(budget=10),
            budget_nodes=10,
            budget_heartbeats=200,
            budget_wall_ms=5000,
            initial_state=shared,
        )
        self.assertTrue(result.success)

    def test_format_contains_oracle_label(self):
        problems = [
            {"name": "demo", "theorem": "P → P", "reference_proof": []},
        ]
        from mathesis.types import Cost, SearchResult

        outcome = SearchResult(
            success=True,
            proof=("intro P", "intro h", "exact h"),
            nodes=3,
            cost=Cost(lean_heartbeats=3, search_nodes=3, wall_ms=10),
            impasse_count=0,
            operator_uses=0,
            trace=(),
        )
        results = {"bfs": {"demo": outcome}}
        walls = {"bfs": {"demo": 12}}
        errors = {"bfs": {"demo": ""}}
        rows = format_lean_bench_rows(problems, results, walls, errors)
        summary = format_lean_bench_summary(results, walls)
        self.assertIn(ORACLE_LABEL, rows)
        self.assertIn(ORACLE_LABEL, summary)
        self.assertIn("solve_rate", summary)
        self.assertIn("bfs", summary)


class LeanBenchCountingTest(unittest.TestCase):
    def test_lean_calls_include_shared_reset_and_derived_seed(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest import mock

        from mathesis import lean_bench
        from mathesis.runlog import derive_seed, start_run

        class ImportsMock(MockLeanBackend):
            imports = ()

        entry = {
            "name": "p_id",
            "theorem": "P -> P",
            "family": "prop",
            "reference_proof": ["intro h", "exact h"],
        }
        with tempfile.TemporaryDirectory() as tmp:
            run = start_run(Path(tmp), "lean-bench", {}, 5)
            with mock.patch.object(
                lean_bench, "make_bench_backend", return_value=ImportsMock()
            ):
                lean_bench.run_lean_bench(
                    [entry], budget_nodes=10, timeout=5, config_names=["bfs"],
                    run=run, seed=5,
                )
            lines = (run.path / "results.jsonl").read_text("utf-8").splitlines()
        record = json.loads(lines[0])
        backend = ImportsMock()
        shared = backend.reset("P -> P")
        _r, _w, _e, search_calls = lean_bench.run_single_lean_config_measured(
            backend, "P -> P", entry["reference_proof"], "bfs", 10, 5,
            initial_state=shared,
        )
        # search_calls excludes the shared reset; the record must include it once
        self.assertEqual(record["lean_calls"], search_calls + 1)
        self.assertEqual(record["derived_seed"], derive_seed(5, "p_id", "bfs"))


@unittest.skipUnless(
    os.environ.get("MATHESIS_LEAN_BENCH") == "1"
    or os.environ.get("MATHESIS_LEAN_INTERACT") == "1",
    "set MATHESIS_LEAN_BENCH=1 to run lean-bench integration",
)
class LeanBenchIntegrationTest(unittest.TestCase):
    def test_lean_bench_limit_3(self):
        from mathesis.cli import main

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(
                [
                    "lean-bench",
                    "--limit",
                    "3",
                    "--budget-nodes",
                    "8",
                    "--timeout",
                    "30",
                    "--configs",
                    "bfs,bfs+oracle-have",
                ]
            )
        output = buffer.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("lean bench problems: 3", output)
        self.assertIn("bfs", output)
        self.assertIn("solve_rate", output)
        self.assertIn(ORACLE_LABEL, output)


if __name__ == "__main__":
    unittest.main()
