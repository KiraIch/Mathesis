import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def repo_lean_dir():
    return Path(__file__).resolve().parents[1] / "lean"


def run_repl(repl_bin, commands, timeout=180):
    proc_input = "\n".join(commands) + "\n"
    completed = subprocess.run(
        [str(repl_bin), "Init"],
        input=proc_input,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return completed


def goal_lines(goals):
    lines = []
    for index, goal in enumerate(goals or []):
        target = goal.get("target", {})
        if isinstance(target, dict):
            shown = str(target.get("pp", "?"))
        else:
            shown = str(target)
        lines.append(
            "    goal "
            + str(index)
            + " name="
            + str(goal.get("name"))
            + " target="
            + shown
        )
    return lines


def main(argv):
    if len(argv) != 2:
        print("usage: pantograph_have_probe.py <path-to-pantograph-repl>")
        return 2
    repl_bin = Path(argv[1])
    if not repl_bin.is_file():
        print("repl binary not found: " + str(repl_bin))
        return 2
    lake = shutil.which("lake")
    if lake is None:
        print("lake not found on PATH; need elan toolchain for kernel check")
        return 2
    commands = [
        "goal.start {\"expr\": \"∀ (P : Prop), P → P\"}",
        "goal.tactic {\"stateId\": 0, \"tactic\": \"intro P\"}",
        "goal.tactic {\"stateId\": 1, \"tactic\": \"intro hP\"}",
        "goal.tactic {\"stateId\": 2, \"have\": \"P\", \"binderName\": \"h\"}",
        "goal.tactic {\"stateId\": 3, \"goalId\": 0, \"tactic\": \"exact hP\"}",
        "goal.tactic {\"stateId\": 4, \"goalId\": 0, \"tactic\": \"exact h\"}",
    ]
    try:
        completed = run_repl(repl_bin, commands)
    except subprocess.TimeoutExpired:
        print("pantograph repl timed out")
        return 1
    if completed.returncode != 0:
        print("repl exited with code " + str(completed.returncode))
        print(completed.stderr[-2000:])
        return 1
    raw_lines = [
        line for line in completed.stdout.splitlines() if line.strip() != ""
    ]
    if not raw_lines or raw_lines[0].strip() != "ready.":
        print("unexpected repl greeting: " + completed.stdout[:500])
        return 1
    responses = raw_lines[1:]
    print("repl responses: " + str(len(responses)) + " for " + str(len(commands)) + " commands")
    if len(responses) != len(commands):
        print("response count mismatch")
        for line in responses:
            print("    " + line[:300])
        return 1
    repl_ok = True
    parsed = []
    for index, line in enumerate(responses):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            print("step " + str(index) + " invalid json: " + str(exc))
            repl_ok = False
            continue
        parsed.append(payload)
        if "error" in payload:
            print("step " + str(index) + " error: " + str(payload.get("desc")))
            repl_ok = False
            continue
        print(
            "step "
            + str(index)
            + " nextStateId="
            + str(payload.get("nextStateId"))
            + " hasSorry="
            + str(payload.get("hasSorry"))
            + " hasUnsafe="
            + str(payload.get("hasUnsafe"))
        )
        for gl in goal_lines(payload.get("goals")):
            print(gl)
        messages = payload.get("messages") or []
        for message in messages:
            print("    message severity=" + str(message.get("severity")))
    if not repl_ok:
        print("REPL_FLOW_FAIL")
        return 1
    final = parsed[-1]
    if (final.get("goals") or []) != []:
        print("REPL_FLOW_FAIL: final goals not empty")
        return 1
    if final.get("hasSorry") is not False:
        print("REPL_FLOW_FAIL: final hasSorry is not false")
        return 1
    print("REPL_FLOW_OK: have subgoal solved, main goal closed, hasSorry false")
    marker = chr(35) + "print axioms probe"
    proof_text = (
        "theorem probe : ∀ (P : Prop), P → P := by\n"
        "  intro P\n"
        "  intro hP\n"
        "  have h : P := by\n"
        "    exact hP\n"
        "  exact h\n" + marker + "\n"
    )
    with tempfile.TemporaryDirectory(prefix="panto_probe_") as tmpdir:
        target = Path(tmpdir) / "Probe.lean"
        target.write_text(proof_text, encoding="utf-8")
        try:
            checked = subprocess.run(
                [lake, "env", "lean", str(target)],
                cwd=str(repo_lean_dir()),
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            print("kernel check timed out")
            return 1
    combined = checked.stdout + checked.stderr
    print("kernel output: " + combined.strip()[:500])
    if checked.returncode != 0:
        print("KERNEL_FAIL: lean exited " + str(checked.returncode))
        return 1
    if "sorryAx" in combined:
        print("KERNEL_FAIL: sorryAx present")
        return 1
    if "does not depend on any axioms" not in combined:
        print("KERNEL_WARN: unexpected axioms output")
        return 1
    print("KERNEL_OK: no axioms, no sorryAx")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
