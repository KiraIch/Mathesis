import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# generic_match rule: a body hit is generic when the collapsed statement body is shorter than 15 characters (trivial shapes such as "P → P" or "n ≤ n" match by chance, so they are not memorization evidence).
GENERIC_BODY_CHARS = 15
HIT_CAP = 3


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


def default_out_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return repo_root() / "runs" / "contamination" / (stamp + ".json")


def parse_args(argv: list) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Heuristic contamination audit for the Lean pilot benchmark.")
    parser.add_argument("--out", type=Path, default=None, help="JSON result path (default: runs/contamination/<UTC timestamp>.json)")
    return parser.parse_args(argv)


def audit(out_path: Path) -> int:
    problems = load_problems()
    root = repo_root()
    mathlib_dir = root / "lean" / ".lake" / "packages" / "mathlib" / "Mathlib"
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
        rel = str(path.relative_to(root))
        for entry, (stem, body) in keys:
            label = str(entry["name"])
            if len(name_hits[label]) < HIT_CAP and stem and stem in text:
                name_hits[label].append(rel)
            if len(frag_hits[label]) < HIT_CAP and body and body in flat:
                frag_hits[label].append(rel)
    print("contamination audit for lean pilot benchmark")
    print("method: substring search over in-repo Mathlib source for the theorem stem and the collapsed statement body")
    print("this audit is heuristic and is not proof of non-contamination; absence of a hit does not mean a result is novel to the literature or unseen in training")
    print("name | novelty | mathlib_match | contamination_risk | stem_hits | body_hits | audit_notes")
    novel_total = 0
    records = []
    checked_total = 0
    for entry, (_, body) in keys:
        label = str(entry["name"])
        if str(entry.get("novelty")) in ("perturbed", "novel"):
            novel_total += 1
        checked = bool(files) and bool(body)
        if checked:
            checked_total += 1
        generic = bool(frag_hits[label]) and len(body) < GENERIC_BODY_CHARS
        if not files:
            note = "mathlib source not found; nothing searched"
        elif not body:
            note = "empty statement body; body not searched"
        elif generic:
            note = "body hit is generic (body under 15 characters); not memorization evidence"
        elif frag_hits[label]:
            note = "body hit on full statement body; judgment call"
        else:
            note = "no body hit"
        records.append({
            "name": label,
            "checked": checked,
            "stem_hits": list(name_hits[label]),
            "body_hits": list(frag_hits[label]),
            "generic_match": generic,
            "note": note,
        })
        stems = ";".join(Path(h).name for h in name_hits[label]) if name_hits[label] else "none"
        frags = ";".join(Path(h).name for h in frag_hits[label]) if frag_hits[label] else "none"
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
    payload = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": "substring search over in-repo Mathlib source for the theorem stem and the collapsed statement body; heuristic only",
        "mathlib_dir": str(mathlib_dir.relative_to(root)),
        "mathlib_files_scanned": len(files),
        "problems_audited": len(problems),
        "problems_checked": checked_total,
        "problems": records,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("problems audited: " + str(len(problems)) + "; perturbed or novel: " + str(novel_total))
    print("problems checked: " + str(checked_total))
    print("mathlib files scanned: " + str(len(files)))
    print("json written to: " + str(out_path))
    print("reminder: heuristic screen only; treat exact and variant flags as judgment calls backed by this screen, not as contamination proofs")
    return 0


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    raise SystemExit(audit(args.out if args.out is not None else default_out_path()))
