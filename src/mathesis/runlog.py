"""Reproducible run artifacts: manifest.json, results.jsonl, summary.json."""

import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

UNKNOWN = "unknown"
GIT_TIMEOUT_S = 10


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run_git(repo_dir: Path, args: list[str]) -> str | None:
    """Return stripped stdout of a git command, or None when it cannot be obtained."""
    try:
        completed = subprocess.run(
            ["git"] + args,
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print("runlog: git " + " ".join(args) + " failed: " + str(exc), file=sys.stderr)
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def git_commit(repo_dir: Path) -> str:
    out = _run_git(repo_dir, ["rev-parse", "HEAD"])
    return out if out else UNKNOWN


def git_dirty(repo_dir: Path) -> bool | None:
    """True/False for a dirty/clean tree; None when git status is unavailable."""
    out = _run_git(repo_dir, ["status", "--porcelain"])
    if out is None:
        return None
    return out != ""


def lean_toolchain(repo_dir: Path) -> str:
    path = repo_dir / "lean" / "lean-toolchain"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return UNKNOWN
    return text if text else UNKNOWN


def mathlib_rev(repo_dir: Path) -> str:
    path = repo_dir / "lean" / "lake-manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return UNKNOWN
    packages = data.get("packages", []) if isinstance(data, dict) else []
    for package in packages:
        if isinstance(package, dict) and package.get("name") == "mathlib":
            rev = package.get("rev")
            if rev:
                return str(rev)
    return UNKNOWN


class CountingBackend:
    """Transparent proxy that counts calls to the Lean backend."""

    COUNTED = ("reset", "apply", "check_proof")

    def __init__(self, inner) -> None:
        self._inner = inner
        self.calls = 0

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if name in self.COUNTED and callable(attr):
            def counted(*args, **kwargs):
                self.calls += 1
                return attr(*args, **kwargs)

            return counted
        return attr


class RunDir:
    def __init__(self, path: Path, started: float) -> None:
        self.path = Path(path)
        self._started = started

    @property
    def results_path(self) -> Path:
        return self.path / "results.jsonl"

    def append_result(self, record: dict) -> None:
        line = json.dumps(record, sort_keys=True)
        with open(self.results_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()

    def finish(self, summary: dict) -> None:
        payload = {
            "summary": summary,
            "wall_clock_seconds": time.monotonic() - self._started,
        }
        (self.path / "summary.json").write_text(
            json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )


def start_run(
    root: Path,
    command: str,
    args: dict,
    seed: int,
    repo_dir: Path | None = None,
) -> RunDir:
    """Create <root>/<UTC timestamp>_<command>/ and write manifest.json.

    repo_dir is where git and lean/ metadata are looked up (default: this repo).
    """
    repo = Path(repo_dir) if repo_dir is not None else default_repo_root()
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    base = stamp + "_" + str(command)
    run_path = root_path / base
    suffix = 0
    while True:
        try:
            run_path.mkdir()
            break
        except FileExistsError:
            suffix += 1
            run_path = root_path / (base + "_" + str(suffix))
    manifest = {
        "timestamp_utc": now.isoformat(),
        "command": str(command),
        "args": args,
        "seed": int(seed),
        "git_commit": git_commit(repo),
        "git_dirty": git_dirty(repo),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "lean_toolchain": lean_toolchain(repo),
        "mathlib_rev": mathlib_rev(repo),
    }
    (run_path / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return RunDir(run_path, time.monotonic())
