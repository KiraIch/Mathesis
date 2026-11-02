import json
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_problems() -> list:
    path = repo_root() / "benchmark" / "lean_pilot" / "problems.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "problems" in raw:
        return raw["problems"]
    return raw


def collapse(text: str) -> str:
    return " ".join(text.split())


def statement_body(theorem: str) -> str:
    if ")," in theorem:
        return theorem.split("),")[-1].strip()
    return theorem.strip()


def problem_keys(entry: dict) -> tuple:
    name = str(entry["name"])
    stem = name[5:] if name.startswith("lean_") else name
    body = collapse(statement_body(str(entry["theorem"])))
    return stem, body


def audit() -> int:
    problems = load_problems()
    mathlib_dir = repo_root() / "lean" / ".lake" / "packages" / "mathlib" / "Mathlib"
    keys = [(entry, problem_keys(entry)) for entry in problems]
    name_hits: dict = {str(entry["name"]): [] for entry, _ in keys}
    frag_hits: dict = {str(entry["name"]): [] for entry, _ in keys}
    files = sorted(mathlib_dir.rglob("*.lean")) if mathlib_dir.is_dir() else []
    if not files:
        print("mathlib source not found at " + str(mathlib_dir))
        print("heuristic audit skipped; flags below are judgment-only")
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        flat = collapse(text)
        for entry, (stem, body) in keys:
            label = str(entry["name"])
            if len(name_hits[label]) < 3 and stem and stem in text:
                name_hits[label].append(str(path.name))
            if len(frag_hits[label]) < 3 and body and len(body) >= 9 and body in flat:
                frag_hits[label].append(str(path.name))
    print("contamination audit for lean pilot benchmark")
    print("method: substring search over in-repo Mathlib source for the theorem stem and the collapsed statement body")
    print("this audit is heuristic and is not proof of non-contamination; absence of a hit does not mean a result is novel to the literature or unseen in training")
    print("name | novelty | mathlib_match | contamination_risk | stem_hits | body_hits | audit_notes")
    novel_total = 0
    for entry, _ in keys:
        label = str(entry["name"])
        if str(entry.get("novelty")) in ("perturbed", "novel"):
            novel_total += 1
        stems = ";".join(name_hits[label]) if name_hits[label] else "none"
        frags = ";".join(frag_hits[label]) if frag_hits[label] else "none"
        print(
            label
            + " | "
            + str(entry.get("novelty"))
            + " | "
            + str(entry.get("mathlib_match"))
            + " | "
            + str(entry.get("contamination_risk"))
            + " | "
            + stems
            + " | "
            + frags
            + " | "
            + str(entry.get("audit_notes"))
        )
    print("problems audited: " + str(len(problems)) + "; perturbed or novel: " + str(novel_total))
    print("mathlib files scanned: " + str(len(files)))
    print("reminder: heuristic screen only; treat exact and variant flags as judgment calls backed by this screen, not as contamination proofs")
    return 0


if __name__ == "__main__":
    raise SystemExit(audit())
