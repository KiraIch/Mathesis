import shutil
import subprocess
import sys
from pathlib import Path


def repo_lean_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "lean"


def main() -> int:
    lean = shutil.which("lean")
    lake = shutil.which("lake")
    if lean is None or lake is None:
        print("Lean toolchain not found; skipping Lean build check.")
        print("To enable the Lean check, install elan and run elan toolchain install.")
        print("Expected Lean files live in lean/ and stay unbuilt for this scaffold task.")
        return 0
    lean_dir = repo_lean_dir()
    print("Found Lean at " + str(lean) + " and Lake at " + str(lake))
    print("Running lake build in " + str(lean_dir))
    try:
        completed = subprocess.run(
            ["lake", "build"],
            cwd=str(lean_dir),
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        print("lake build timed out after 300 seconds.")
        return 1
    if completed.stdout:
        print(completed.stdout[-4000:])
    if completed.stderr:
        print(completed.stderr[-4000:])
    if completed.returncode == 0:
        print("lake build succeeded.")
        return 0
    print("lake build failed with exit code " + str(completed.returncode))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
