"""Run b0 or hint-gap split by problem across GPUs, then merge the shards.

    python scripts/run_sharded.py --gpus 0,1,2,3 --out runs -- b0 --k 8 --seed 0

One `python -m mathesis.cli <cmd> ... --shard i/N --out <out>/shards_<stamp>/shard<i>` process
is started per GPU (CUDA_VISIBLE_DEVICES=<gpu>, rest of the environment inherited), logging to
shard<i>.log next to its run dir. When every shard exits 0, scripts/merge_shards.py combines
them into a new run under <out>. A failed shard is reported and nothing is merged.
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import merge_shards  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ("b0", "hint-gap")
FORBIDDEN = ("--shard", "--out", "--controls")


def parse_gpus(text: str) -> list[str]:
    gpus = [part.strip() for part in text.split(",")]
    if not gpus or any(not g.isdigit() for g in gpus) or len(set(gpus)) != len(gpus):
        raise ValueError("--gpus must be distinct comma-separated GPU indexes, got " + repr(text))
    return gpus


def build_commands(gpus: list[str], command: str, cli_args: list[str], shards_dir: Path,
                   python: str = sys.executable) -> list[dict]:
    """One {argv, env, run_out, log} per GPU; shard i of N runs on gpus[i]."""
    if command not in COMMANDS:
        raise ValueError("command must be one of " + ", ".join(COMMANDS))
    for arg in cli_args:
        if arg.split("=", 1)[0] in FORBIDDEN:
            raise ValueError(arg.split("=", 1)[0] + " is set by run_sharded.py; do not pass it")
    count = len(gpus)
    jobs = []
    for index, gpu in enumerate(gpus):
        run_out = Path(shards_dir) / ("shard" + str(index))
        argv = [python, "-m", "mathesis.cli", command, *cli_args,
                "--shard", str(index) + "/" + str(count), "--out", str(run_out)]
        jobs.append({
            "argv": argv, "env": {"CUDA_VISIBLE_DEVICES": gpu}, "run_out": run_out,
            "log": Path(shards_dir) / ("shard" + str(index) + ".log"),
        })
    return jobs


def shard_run_dirs(run_out: Path) -> list[Path]:
    return sorted(p for p in Path(run_out).iterdir() if p.is_dir()) if Path(run_out).is_dir() else []


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--gpus", required=True, help="comma-separated GPU indexes, one shard each")
    parser.add_argument("--out", default="runs", help="parent directory (default: runs)")
    parser.add_argument("rest", nargs=argparse.REMAINDER, help="-- <b0|hint-gap> [cli args...]")
    args = parser.parse_args(argv)
    args.out = str(Path(args.out).resolve())  # the shard processes run with cwd = repo root
    rest = args.rest[1:] if args.rest[:1] == ["--"] else args.rest
    try:
        gpus = parse_gpus(args.gpus)
        if not rest:
            raise ValueError("missing command: -- <b0|hint-gap> [args...]")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        shards_dir = Path(args.out) / ("shards_" + stamp)
        jobs = build_commands(gpus, rest[0], rest[1:], shards_dir)
    except ValueError as exc:
        print("run_sharded: " + str(exc), file=sys.stderr)
        return 2
    shards_dir.mkdir(parents=True, exist_ok=False)
    procs = []
    for job in jobs:
        log = open(job["log"], "w", encoding="utf-8")
        env = dict(os.environ, **job["env"])
        src = str(REPO_ROOT / "src")
        env["PYTHONPATH"] = src + os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else src
        proc = subprocess.Popen(job["argv"], env=env, stdout=log, stderr=subprocess.STDOUT,
                                cwd=str(REPO_ROOT))
        procs.append((job, proc, log))
        print("started shard on GPU " + job["env"]["CUDA_VISIBLE_DEVICES"] + ": log " + str(job["log"]))
    codes = []
    for job, proc, log in procs:
        codes.append(proc.wait())
        log.close()
    bad = [(job, code) for (job, _, _), code in zip(procs, codes) if code != 0]
    if bad:
        for job, code in bad:
            print("shard failed rc=" + str(code) + ": see " + str(job["log"]), file=sys.stderr)
        print("run_sharded: not merging; shard dirs under " + str(shards_dir), file=sys.stderr)
        return 1
    dirs = []
    for job in jobs:
        found = shard_run_dirs(job["run_out"])
        if len(found) != 1:
            print("run_sharded: expected one run dir in " + str(job["run_out"]), file=sys.stderr)
            return 1
        dirs.append(found[0])
    try:
        merged = merge_shards.merge_shards(dirs, args.out)
    except merge_shards.MergeError as exc:
        print("run_sharded: merge failed: " + str(exc), file=sys.stderr)
        return 1
    print("merged run dir: " + str(merged))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
