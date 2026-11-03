import os
import shutil
import subprocess
import unittest
from pathlib import Path
from mathesis.lean_pilot import (
    default_lean_pilot_path,
    load_lean_pilot,
    validate_lean_pilot,
)


class LeanPilotTest(unittest.TestCase):
    def test_metadata_loads(self):
        path = default_lean_pilot_path()
        problems = load_lean_pilot(path)
        self.assertGreaterEqual(len(problems), 38)
        self.assertLessEqual(len(problems), 100)

    def test_unique_names_and_theorems(self):
        problems = load_lean_pilot(default_lean_pilot_path())
        names = [entry["name"] for entry in problems]
        self.assertEqual(len(names), len(set(names)))
        theorems = [entry["theorem"] for entry in problems]
        self.assertEqual(len(theorems), len(set(theorems)))

    def test_lean_files_exist(self):
        root = Path(__file__).resolve().parents[1]
        base = root / "benchmark" / "lean_pilot"
        problems = load_lean_pilot(base / "problems.json")
        for entry in problems:
            target = base / str(entry["lean_file"])
            self.assertTrue(target.is_file(), "missing " + str(target))
            text = target.read_text(encoding="utf-8")
            self.assertIn("namespace MathesisPilot", text)
            self.assertNotIn("sorry", text)

    def test_insight_and_routine_counts(self):
        problems = load_lean_pilot(default_lean_pilot_path())
        insights = [entry for entry in problems if entry["insight"] is True]
        routines = [entry for entry in problems if entry["insight"] is False]
        self.assertGreaterEqual(len(insights), 12)
        self.assertGreaterEqual(len(routines), 12)
        for entry in insights:
            tactics = entry["reference_proof"]
            found = False
            for tactic in tactics:
                if "have" in tactic:
                    found = True
            self.assertTrue(found, "insight needs have " + str(entry["name"]))

    def test_novelty_and_audit_fields(self):
        problems = load_lean_pilot(default_lean_pilot_path())
        novel = [
            entry
            for entry in problems
            if entry["novelty"] in ("perturbed", "novel")
        ]
        self.assertGreaterEqual(len(novel), 8)
        for entry in problems:
            self.assertIn(entry["novelty"], ("textbook", "perturbed", "novel"))
            self.assertIn(entry["contamination_risk"], ("low", "medium", "high"))
            self.assertIn(entry["mathlib_match"], ("none", "variant", "exact"))
            self.assertIsInstance(entry["audit_notes"], str)

    def test_verified_flags(self):
        problems = load_lean_pilot(default_lean_pilot_path())
        for entry in problems:
            self.assertIsInstance(entry["verified"], bool)
            self.assertIn(entry["source"], ("core", "mathlib"))
            self.assertIs(entry["verified"], True)
            self.assertGreaterEqual(entry["difficulty"], 1)
            self.assertLessEqual(entry["difficulty"], 5)
            self.assertGreater(entry["budget_nodes"], 0)
            self.assertTrue(entry["reference_proof"])

    def test_validate_accepts_dataset(self):
        problems = load_lean_pilot(default_lean_pilot_path())
        self.assertTrue(validate_lean_pilot(problems))

    def test_imports_field_present_and_valid(self):
        problems = load_lean_pilot(default_lean_pilot_path())
        flagged = [
            entry for entry in problems if "imports" in entry
        ]
        self.assertEqual(len(flagged), 2)
        names = sorted(entry["name"] for entry in flagged)
        self.assertEqual(names, ["lean_poly_lower", "lean_seq_even"])
        for entry in flagged:
            self.assertEqual(
                tuple(entry["imports"]), ("Mathlib", "Mathesis.Defs")
            )

    def test_imports_field_rejects_bad_values(self):
        problems = load_lean_pilot(default_lean_pilot_path())
        import copy

        bad_type = copy.deepcopy(problems)
        bad_type[0]["imports"] = "Mathlib"
        with self.assertRaises(ValueError):
            validate_lean_pilot(bad_type)
        bad_entry = copy.deepcopy(problems)
        bad_entry[0]["imports"] = ["Mathlib", "  "]
        with self.assertRaises(ValueError):
            validate_lean_pilot(bad_entry)

    def test_used_in_test_split_all_recorded_b0(self):
        problems = load_lean_pilot(default_lean_pilot_path())
        test_entries = [entry for entry in problems if entry["bench_split"] == "test"]
        self.assertEqual(len(test_entries), 40)
        for entry in test_entries:
            self.assertIn("used_in", entry)
            self.assertIn("B0", entry["used_in"], "B0 missing for " + str(entry["name"]))

    def test_used_in_is_optional(self):
        problems = load_lean_pilot(default_lean_pilot_path())
        import copy

        without = copy.deepcopy(problems)
        for entry in without:
            entry.pop("used_in", None)
        self.assertTrue(validate_lean_pilot(without))

    def test_used_in_rejects_bad_values(self):
        problems = load_lean_pilot(default_lean_pilot_path())
        import copy

        bad_type = copy.deepcopy(problems)
        bad_type[0]["used_in"] = "B0"
        with self.assertRaises(ValueError):
            validate_lean_pilot(bad_type)
        bad_item = copy.deepcopy(problems)
        bad_item[0]["used_in"] = [1]
        with self.assertRaises(ValueError):
            validate_lean_pilot(bad_item)
        bad_empty = copy.deepcopy(problems)
        bad_empty[0]["used_in"] = ["B0", "  "]
        with self.assertRaises(ValueError):
            validate_lean_pilot(bad_empty)

    @unittest.skipUnless(
        os.environ.get("MATHESIS_KERNEL_TESTS") == "1",
        "set MATHESIS_KERNEL_TESTS=1 to run kernel checks",
    )
    def test_verified_files_pass_kernel_check(self):
        root = Path(__file__).resolve().parents[1]
        base = root / "benchmark" / "lean_pilot"
        lean_dir = root / "lean"
        problems = load_lean_pilot(base / "problems.json")
        lake = shutil.which("lake")
        self.assertIsNotNone(lake, "lake not found on PATH")
        project_text = ""
        manifest = lean_dir / "lake-manifest.json"
        lakefile = lean_dir / "lakefile.lean"
        if manifest.is_file():
            project_text += manifest.read_text(encoding="utf-8")
        if lakefile.is_file():
            project_text += lakefile.read_text(encoding="utf-8")
        project_has_mathlib = "mathlib" in project_text
        failures = []
        checked = 0
        skipped = 0
        for entry in problems:
            if entry["verified"] is not True:
                continue
            target = base / str(entry["lean_file"])
            needs_mathlib = "import Mathlib" in target.read_text(encoding="utf-8")
            if needs_mathlib and not project_has_mathlib:
                skipped += 1
                continue
            completed = subprocess.run(
                ["lake", "env", "lean", str(target)],
                cwd=str(lean_dir),
                capture_output=True,
                text=True,
                timeout=300,
            )
            checked += 1
            if completed.returncode != 0:
                failures.append(str(entry["lean_file"]) + ": " + completed.stderr[-2000:])
        self.assertEqual(failures, [], "kernel check failed for " + str(failures))
        self.assertGreater(checked, 0, "no verified files were kernel-checked")
        if not project_has_mathlib:
            self.assertGreater(skipped, 0, "expected mathlib files to be skipped")


if __name__ == "__main__":
    unittest.main()
