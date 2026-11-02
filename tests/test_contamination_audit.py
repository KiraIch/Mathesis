import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "contamination_audit.py"
_spec = importlib.util.spec_from_file_location("contamination_audit", SCRIPT)
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


class ContaminationAuditHelpersTest(unittest.TestCase):
    def test_generic_rule_uses_constant(self):
        limit = audit.GENERIC_BODY_CHARS
        self.assertTrue(audit.is_generic_body("x" * (limit - 1)))
        self.assertFalse(audit.is_generic_body("x" * limit))
        self.assertIn(str(limit), audit.generic_note())

    def test_stem_prefix_stripping(self):
        self.assertEqual(audit.stem_for_name("lean_nat_zero_add"), "zero_add")
        self.assertEqual(audit.stem_for_name("lean_list_append_nil"), "append_nil")
        self.assertEqual(audit.stem_for_name("nat_zero_add"), "zero_add")
        self.assertEqual(audit.stem_for_name("lean_identity"), "identity")

    def test_problem_keys_returns_stripped_stem(self):
        stem, body = audit.problem_keys(
            {"name": "lean_nat_zero_add", "theorem": "∀ (n : Nat), 0 + n = n"}
        )
        self.assertEqual(stem, "zero_add")
        self.assertEqual(body, "0 + n = n")

    def test_unique_path_collision_suffix(self):
        base = Path("/x/run.json")
        taken = set()
        self.assertEqual(audit.unique_path(base, taken.__contains__), base)
        taken.add(base)
        self.assertEqual(
            audit.unique_path(base, taken.__contains__), Path("/x/run_1.json")
        )
        taken.add(Path("/x/run_1.json"))
        self.assertEqual(
            audit.unique_path(base, taken.__contains__), Path("/x/run_2.json")
        )

    def test_resolve_out_path_relative_to_cwd(self):
        cwd = Path("/work/dir")
        self.assertEqual(
            audit.resolve_out_path(Path("out.json"), cwd), Path("/work/dir/out.json")
        )
        self.assertEqual(
            audit.resolve_out_path(Path("/abs/out.json"), cwd), Path("/abs/out.json")
        )


if __name__ == "__main__":
    unittest.main()
