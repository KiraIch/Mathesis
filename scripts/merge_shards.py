"""Merge `--shard I/N` runs of b0 or hint-gap into one run directory.

    python scripts/merge_shards.py SHARD_RUN_DIR... --out OUT_PARENT

The shard run dirs are only read. The merged run is a new `<timestamp>_<kind>-merged`
directory under OUT_PARENT holding manifest.json, results.jsonl (full problem order, then
condition plain/hint, then sample_index), candidates/, responses/, preflight/ and a
summary.json recomputed from the rows with the same summarize functions the runs use.
Nothing is sampled and no Lean check is run.
"""
import argparse
import json
import os
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mathesis import cli, llm_baseline, runlog  # noqa: E402

CONDITIONS = ("plain", "hint")
# Manifest args that legitimately differ between shards of one run.
SHARD_ARG_KEYS = {"shard", "problem_names", "problems", "auxiliary_sha256", "out"}
KINDS = ("b0", "hint-gap")


class MergeError(Exception):
    pass


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MergeError("cannot read " + str(path) + ": " + str(exc)) from None


def _read_rows(path: Path) -> list:
    rows = []
    try:
        with open(path, encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                if line.strip():
                    try:
                        rows.append(json.loads(line))
                    except ValueError as exc:
                        raise MergeError(
                            str(path) + " line " + str(number) + ": " + str(exc)
                        ) from None
    except OSError as exc:
        raise MergeError("cannot read " + str(path) + ": " + str(exc)) from None
    return rows


def _comparable(args: dict) -> dict:
    out = {key: value for key, value in args.items() if key not in SHARD_ARG_KEYS}
    bench = dict(out.get("benchmark_sha256") or {})
    bench.pop("lean_files", None)
    out["benchmark_sha256"] = bench
    return out


def load_shard(path) -> dict:
    path = Path(path)
    manifest = _read_json(path / "manifest.json")
    summary_doc = _read_json(path / "summary.json")
    if summary_doc.get("status") != "ok":
        raise MergeError(
            str(path) + ": summary status is " + repr(summary_doc.get("status"))
            + " (" + str(summary_doc.get("error")) + "), not 'ok'"
        )
    args = manifest.get("args") or {}
    shard = args.get("shard")
    if (not isinstance(shard, list) or len(shard) != 2
            or not all(isinstance(v, int) for v in shard)):
        raise MergeError(str(path) + ": manifest args.shard is not [I, N] (not a shard run)")
    return {
        "path": path, "manifest": manifest, "args": args, "shard": tuple(shard),
        "summary": summary_doc.get("summary") or {}, "wall": summary_doc.get("wall_clock_seconds"),
        "rows": _read_rows(path / "results.jsonl"),
    }


def validate_shards(shards: list) -> tuple[str, list]:
    """Check the shards belong together; return (kind, full_problem_names)."""
    if not shards:
        raise MergeError("no shard run dirs given")
    first = shards[0]
    kind = first["manifest"].get("command")
    if kind not in KINDS:
        raise MergeError("shard command must be one of " + ", ".join(KINDS) + ", got " + repr(kind))
    count = first["shard"][1]
    full = first["args"].get("full_problem_names")
    if not isinstance(full, list) or not full:
        raise MergeError(str(first["path"]) + ": manifest args.full_problem_names missing")
    reference = _comparable(first["args"])
    for shard in shards:
        label = str(shard["path"])
        if shard["manifest"].get("command") != kind:
            raise MergeError(label + ": command differs from " + str(first["path"]))
        if shard["manifest"].get("seed") != first["manifest"].get("seed"):
            raise MergeError(label + ": seed differs")
        if shard["shard"][1] != count:
            raise MergeError(label + ": shard count N differs")
        if shard["args"].get("full_problem_names") != full:
            raise MergeError(label + ": full_problem_names differ")
        other = _comparable(shard["args"])
        if other != reference:
            keys = sorted(k for k in set(other) | set(reference) if other.get(k) != reference.get(k))
            raise MergeError(label + ": manifest args differ in " + ", ".join(keys))
    indexes = sorted(shard["shard"][0] for shard in shards)
    if indexes != list(range(count)):
        raise MergeError(
            "shards must cover 0.." + str(count - 1) + " exactly once, got " + str(indexes)
        )
    covered = []
    for shard in shards:
        covered.extend(shard["args"].get("problem_names") or [])
    if len(covered) != len(set(covered)) or set(covered) != set(full):
        raise MergeError("union of shard problem_names does not equal full_problem_names")
    for shard in shards:
        expected = [n for i, n in enumerate(full) if i % count == shard["shard"][0]]
        if shard["args"].get("problem_names") != expected:
            raise MergeError(str(shard["path"]) + ": problem_names is not its round-robin subset")
    return kind, list(full)


def _order_rows(rows: list, names: list, kind: str, label: str) -> list:
    position = {name: i for i, name in enumerate(names)}
    for row in rows:
        if row.get("problem") not in position:
            raise MergeError(label + ": row for unexpected problem " + repr(row.get("problem")))
        if kind == "hint-gap" and row.get("condition") not in CONDITIONS:
            raise MergeError(label + ": hint-gap row without a plain/hint condition")

    def key(row):
        cond = CONDITIONS.index(row["condition"]) if kind == "hint-gap" else 0
        return position[row["problem"]], cond, int(row["sample_index"])

    ordered = sorted(rows, key=key)
    keys = [key(row) for row in ordered]
    if len(keys) != len(set(keys)):
        raise MergeError(label + ": duplicate (problem, condition, sample_index) rows")
    return ordered


def summarize_rows(rows: list, names: list, kind: str, k: int) -> dict:
    """Rebuild the run summary (without lean_preflight) from result rows, as the run does."""
    cells = {}
    failures = Counter()
    for row in rows:
        cond = row["condition"] if kind == "hint-gap" else None
        n, c = cells.get((row["problem"], cond), (0, 0))
        cells[(row["problem"], cond)] = (n + 1, c + (1 if row["passed"] else 0))
        failures[row["failure_class"]] += 1
    stats = llm_baseline._problem_stats
    if kind == "b0":
        per_problem = {name: stats(*cells[(name, None)], k) for name in names if (name, None) in cells}
        return llm_baseline.summarize_b0(per_problem, k, dict(failures))
    pairs = {}
    for name in names:
        if (name, "plain") in cells or (name, "hint") in cells:
            pairs[name] = {cond: stats(*cells[(name, cond)], k) for cond in CONDITIONS}
    return llm_baseline.summarize_hint_gap(pairs, k, failure_class_counts=dict(failures))


def _same_json(a, b) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _link_or_copy(src, dst) -> None:
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _copy_tree(src: Path, dst: Path) -> None:
    dst.mkdir(exist_ok=True)
    for item in sorted(src.iterdir()):
        target = dst / item.name
        if target.exists():
            raise MergeError("file collision while merging: " + str(target))
        if item.is_dir():
            _copy_tree(item, target)
        else:
            _link_or_copy(item, target)


def merge_shards(shard_dirs, out_parent) -> Path:
    shards = sorted((load_shard(p) for p in shard_dirs), key=lambda s: s["shard"][0])
    kind, full = validate_shards(shards)
    first = shards[0]
    k = int(first["args"]["k"])
    for shard in shards:
        label = str(shard["path"])
        mine = _order_rows(shard["rows"], shard["args"]["problem_names"], kind, label)
        own = summarize_rows(mine, shard["args"]["problem_names"], kind, k)
        stored = {key: v for key, v in shard["summary"].items() if key != "lean_preflight"}
        if not _same_json(own, stored):
            raise MergeError(label + ": summary.json does not match its results.jsonl")
        expected_rows = len(shard["args"]["problem_names"]) * k * (2 if kind == "hint-gap" else 1)
        if len(mine) != expected_rows:
            raise MergeError(label + ": expected " + str(expected_rows) + " rows, found " + str(len(mine)))
    rows = _order_rows([r for s in shards for r in s["rows"]], full, kind, "merged")
    summary = summarize_rows(rows, full, kind, k)
    summary = llm_baseline._with_preflight(summary, first["summary"].get("lean_preflight"))

    args = dict(first["args"])
    args["shard"] = None
    args["problem_names"] = list(full)
    args["out"] = str(out_parent)
    lean_files = {}
    for shard in shards:
        lean_files.update((shard["args"].get("benchmark_sha256") or {}).get("lean_files") or {})
    args["benchmark_sha256"] = dict(args.get("benchmark_sha256") or {}, lean_files=lean_files)
    if kind == "hint-gap":
        problems = llm_baseline.load_b0_problems(None, args.get("benchmark"))
        hints = None
        if args.get("hints_file"):
            if runlog.file_sha256(Path(args["hints_file"])) != args.get("hints_file_sha256"):
                raise MergeError("hints_file changed since the shards ran: " + str(args["hints_file"]))
            hints = cli.load_hint_file(args["hints_file"])["hints"]
        targets = cli.hint_gap_targets(problems, None, full, hints)
        if [p["name"] for p in targets] != full:
            raise MergeError("benchmark no longer yields the hint-gap targets of these shards")
        args["problems"] = list(full)
        args["auxiliary_sha256"] = cli._auxiliary_sha256(targets)
        for shard in shards:
            subset = [p for p in targets if p["name"] in set(shard["args"]["problem_names"])]
            if cli._auxiliary_sha256(subset) != shard["args"].get("auxiliary_sha256"):
                raise MergeError(str(shard["path"]) + ": auxiliary_sha256 no longer matches the benchmark")
    args["shard_runs"] = [str(s["path"]) for s in shards]

    out_root = Path(out_parent)
    run = runlog.start_run(out_root, kind + "-merged", args, int(first["manifest"]["seed"]))
    manifest = dict(first["manifest"])
    manifest["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["command"] = kind
    manifest["args"] = args
    manifest["merged_from_git_commits"] = sorted({str(s["manifest"].get("git_commit")) for s in shards})
    (run.path / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2, default=str) + "\n", encoding="utf-8"
    )
    with open(run.results_path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    for sub in ("candidates", "responses"):
        (run.path / sub).mkdir(exist_ok=True)
        for shard in shards:
            if (shard["path"] / sub).is_dir():
                _copy_tree(shard["path"] / sub, run.path / sub)
    for shard in shards:
        if (shard["path"] / "preflight").is_dir():
            name = "preflight" if shard is first else "preflight_shard" + str(shard["shard"][0])
            _copy_tree(shard["path"] / "preflight", run.path / name)
    walls = [s["wall"] for s in shards if isinstance(s["wall"], (int, float))]
    payload = {
        "status": "ok", "error": "", "summary": summary,
        # Shards run in parallel, so the slowest one bounds the run.
        "wall_clock_seconds": max(walls) if walls else None,
    }
    (run.path / "summary.json").write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return run.path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("shards", nargs="+", help="shard run directories")
    parser.add_argument("--out", required=True, help="parent directory for the merged run")
    args = parser.parse_args(argv)
    try:
        path = merge_shards(args.shards, args.out)
    except MergeError as exc:
        print("merge_shards: " + str(exc), file=sys.stderr)
        return 1
    print("merged run dir: " + str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
