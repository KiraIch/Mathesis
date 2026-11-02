import json
from pathlib import Path


REQUIRED_FIELDS = (
    "name",
    "theorem",
    "family",
    "insight",
    "reference_proof",
    "budget_nodes",
    "lean_file",
    "source",
    "verified",
    "auxiliary",
    "difficulty",
    "novelty",
    "contamination_risk",
    "mathlib_match",
    "audit_notes",
)

NOVELTY_VALUES = ("textbook", "perturbed", "novel")
CONTAMINATION_VALUES = ("low", "medium", "high")
MATHLIB_MATCH_VALUES = ("none", "variant", "exact")


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_lean_pilot_dir() -> Path:
    return default_repo_root() / "benchmark" / "lean_pilot"


def default_lean_pilot_path() -> Path:
    return default_lean_pilot_dir() / "problems.json"


def load_lean_pilot(path=None):
    if path is None:
        location = default_lean_pilot_path()
    else:
        location = Path(path)
    raw = json.loads(location.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "problems" in raw:
        entries = raw["problems"]
    elif isinstance(raw, list):
        entries = raw
    else:
        raise ValueError("lean pilot file needs a list or a dict with problems")
    base_dir = location.parent
    validate_lean_pilot(entries, base_dir=base_dir)
    return entries


def validate_lean_pilot(problems, base_dir=None):
    if base_dir is None:
        base = default_lean_pilot_dir()
    else:
        base = Path(base_dir)
    if not isinstance(problems, list):
        raise ValueError("lean pilot problems must be a list")
    count = len(problems)
    if count < 38 or count > 64:
        raise ValueError("lean pilot needs 38 to 64 problems got " + str(count))
    seen_names = set()
    seen_theorems = set()
    insight_count = 0
    routine_count = 0
    novel_count = 0
    for entry in problems:
        if not isinstance(entry, dict):
            raise ValueError("each lean pilot entry must be a dict")
        for field in REQUIRED_FIELDS:
            if field not in entry:
                raise ValueError("missing field " + str(field))
        name = entry["name"]
        theorem = entry["theorem"]
        family = entry["family"]
        insight = entry["insight"]
        reference_proof = entry["reference_proof"]
        budget_nodes = entry["budget_nodes"]
        lean_file = entry["lean_file"]
        source = entry["source"]
        verified = entry["verified"]
        auxiliary = entry["auxiliary"]
        difficulty = entry["difficulty"]
        novelty = entry["novelty"]
        contamination_risk = entry["contamination_risk"]
        mathlib_match = entry["mathlib_match"]
        audit_notes = entry["audit_notes"]
        if not isinstance(name, str) or not name:
            raise ValueError("name must be a non-empty string")
        if name in seen_names:
            raise ValueError("duplicate name " + repr(name))
        seen_names.add(name)
        if not isinstance(theorem, str) or not theorem:
            raise ValueError("theorem must be a non-empty string")
        if theorem in seen_theorems:
            raise ValueError("duplicate theorem string " + repr(theorem))
        seen_theorems.add(theorem)
        if not isinstance(family, str) or not family:
            raise ValueError("family must be a non-empty string")
        if not isinstance(insight, bool):
            raise ValueError("insight must be a bool")
        if insight:
            insight_count += 1
        else:
            routine_count += 1
        if not isinstance(reference_proof, list) or not reference_proof:
            raise ValueError("reference_proof must be a non-empty list")
        for tactic in reference_proof:
            if not isinstance(tactic, str) or not tactic:
                raise ValueError("each tactic must be a non-empty string")
            if "sorry" in tactic:
                raise ValueError("reference proof must not use sorry")
        if insight:
            has_have = False
            for tactic in reference_proof:
                if "have" in tactic:
                    has_have = True
            if not has_have:
                raise ValueError("insight problem needs a have tactic " + repr(name))
        if not isinstance(budget_nodes, int) or budget_nodes <= 0:
            raise ValueError("budget_nodes must be a positive int")
        if not isinstance(lean_file, str) or not lean_file:
            raise ValueError("lean_file must be a non-empty string")
        target = base / lean_file
        if not target.is_file():
            raise ValueError("lean file not found " + str(target))
        if source not in ("core", "mathlib"):
            raise ValueError("source must be core or mathlib")
        if not isinstance(verified, bool):
            raise ValueError("verified must be a bool")
        if not isinstance(auxiliary, str):
            raise ValueError("auxiliary must be a string")
        if not isinstance(difficulty, int) or difficulty < 1 or difficulty > 5:
            raise ValueError("difficulty must be an int from 1 to 5")
        if novelty not in NOVELTY_VALUES:
            raise ValueError("novelty must be textbook perturbed or novel " + repr(name))
        if novelty in ("perturbed", "novel"):
            novel_count += 1
        if contamination_risk not in CONTAMINATION_VALUES:
            raise ValueError("contamination_risk must be low medium or high " + repr(name))
        if mathlib_match not in MATHLIB_MATCH_VALUES:
            raise ValueError("mathlib_match must be none variant or exact " + repr(name))
        if not isinstance(audit_notes, str):
            raise ValueError("audit_notes must be a string " + repr(name))
        if "imports" in entry:
            imports_value = entry["imports"]
            if not isinstance(imports_value, list):
                raise ValueError("imports must be a list " + repr(name))
            for module in imports_value:
                if not isinstance(module, str) or not module.strip():
                    raise ValueError(
                        "each import must be a non-empty string " + repr(name)
                    )
    if insight_count < 12:
        raise ValueError("need at least 12 insight problems got " + str(insight_count))
    if routine_count < 12:
        raise ValueError("need at least 12 routine problems got " + str(routine_count))
    if novel_count < 8:
        raise ValueError("need at least 8 perturbed or novel problems got " + str(novel_count))
    return True
