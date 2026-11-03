import json
import os
import select
import shutil
import subprocess
import tempfile
from pathlib import Path

from mathesis.backend import default_lean_project_dir, has_sorry_warning
from mathesis.proof_rules import find_forbidden, find_forbidden_in_proof
from mathesis.types import (
    ApplyResult,
    Goal,
    Hypothesis,
    ProofState,
    make_atom,
)


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_pantograph_repl() -> Path:
    override = os.environ.get("PANTOGRAPH_REPL", "").strip()
    if override:
        return Path(override)
    return (
        default_repo_root() / ".pantograph" / ".lake" / "build" / "bin" / "repl"
    )


def parse_have_tactic(text: str) -> tuple[str, str] | None:
    stripped = text.strip()
    if not stripped.startswith("have "):
        return None
    rest = stripped[len("have "):].strip()
    if ":" not in rest:
        return None
    name_part, _, prop_part = rest.partition(":")
    name = name_part.strip()
    prop = prop_part.strip()
    if ":=" in prop:
        prop = prop.split(":=", 1)[0].strip()
    if not name or not prop:
        return None
    if any(ch.isspace() for ch in name):
        return None
    return name, prop


def encode_state_token(state_id: int) -> str:
    return json.dumps({"stateId": int(state_id)}, sort_keys=True)


def decode_state_token(token: str) -> int:
    try:
        payload = json.loads(token)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid pantograph token " + repr(token)) from exc
    if not isinstance(payload, dict) or "stateId" not in payload:
        raise ValueError("invalid pantograph token " + repr(token))
    try:
        return int(payload["stateId"])
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid pantograph token " + repr(token)) from exc


def goal_target_text(goal: dict) -> str:
    target = goal.get("target", {})
    if isinstance(target, dict):
        return str(target.get("pp", "?"))
    return str(target)


def decode_pantograph_goals(
    goals,
) -> tuple[tuple[Goal, ...], tuple[Hypothesis, ...]]:
    decoded_goals: list[Goal] = []
    decoded_hyps: list[Hypothesis] = []
    seen: set[str] = set()
    for entry in goals or []:
        if not isinstance(entry, dict):
            continue
        decoded_goals.append(Goal(proposition=make_atom(goal_target_text(entry))))
        variables = entry.get("vars", [])
        for var in variables or []:
            if not isinstance(var, dict):
                continue
            raw_name = var.get("userName", var.get("name", ""))
            name_text = str(raw_name)
            if not name_text or name_text in seen:
                continue
            seen.add(name_text)
            var_type = var.get("type", {})
            if isinstance(var_type, dict):
                type_text = str(var_type.get("pp", "?"))
            else:
                type_text = str(var_type)
            decoded_hyps.append(
                Hypothesis(name=name_text, proposition=make_atom(type_text))
            )
    return tuple(decoded_goals), tuple(decoded_hyps)


def summarize_messages(messages) -> str:
    parts: list[str] = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        data = message.get("data", "")
        if data:
            parts.append(str(data))
    return "; ".join(parts)


class PantographBackend:
    def __init__(
        self,
        repl_path=None,
        modules=("Mathlib",),
        project_dir=None,
        timeout=120,
    ):
        if repl_path is None:
            self.repl_path = default_pantograph_repl()
        else:
            self.repl_path = Path(repl_path)
        self.modules = tuple(str(item) for item in tuple(modules))
        if project_dir is None:
            self.project_dir = None
        else:
            self.project_dir = Path(project_dir)
        self.timeout = timeout
        self._proc = None
        self._active_modules: tuple[str, ...] | None = None
        self._theorem_counter = 0

    def close(self):
        proc, self._proc = self._proc, None
        self._active_modules = None
        if proc is None:
            return
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _readline(self, proc, timeout):
        try:
            ready, _, _ = select.select([proc.stdout], [], [], timeout)
        except Exception:
            return None
        if not ready:
            return None
        try:
            return proc.stdout.readline()
        except Exception:
            return None

    def _spawn(self, modules):
        self.close()
        lake = shutil.which("lake")
        if lake is not None:
            command = [lake, "env", str(self.repl_path)] + [str(m) for m in modules]
        else:
            command = [str(self.repl_path)] + [str(m) for m in modules]
        if self.project_dir is not None:
            workdir = str(self.project_dir)
        else:
            workdir = str(default_lean_project_dir())
        try:
            proc = subprocess.Popen(
                command,
                cwd=workdir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
        except Exception as exc:
            raise ValueError("pantograph repl failed to start: " + str(exc))
        greeting = self._readline(proc, self.timeout)
        if greeting is None or greeting.strip() != "ready.":
            try:
                proc.kill()
            except Exception:
                pass
            raise ValueError("pantograph repl did not greet: " + repr(greeting))
        self._proc = proc
        self._active_modules = tuple(modules)
        return proc

    def _ensure(self, modules):
        wanted = tuple(modules)
        if self._proc is not None and self._active_modules == wanted:
            try:
                if self._proc.poll() is None:
                    return self._proc
            except Exception:
                pass
        return self._spawn(wanted)

    def _send(
        self, command: str, payload: dict, modules=None
    ) -> dict:
        if modules is not None:
            wanted = tuple(modules)
        elif self._active_modules is not None:
            wanted = self._active_modules
        else:
            wanted = self.modules
        proc = self._ensure(wanted)
        line = command + " " + json.dumps(payload)
        try:
            proc.stdin.write(line + "\n")
            proc.stdin.flush()
        except Exception as exc:
            self.close()
            raise ValueError("pantograph repl write failed: " + str(exc))
        raw = self._readline(proc, self.timeout)
        if raw is None or not raw.strip():
            self.close()
            raise ValueError("pantograph repl timed out waiting for " + command)
        try:
            response = json.loads(raw)
        except ValueError as exc:
            self.close()
            raise ValueError(
                "pantograph repl returned invalid json: " + raw[:200]
            ) from exc
        if isinstance(response, dict) and "error" in response:
            raise ValueError(
                "pantograph "
                + command
                + " failed: "
                + str(response.get("desc", response.get("error")))
            )
        if not isinstance(response, dict):
            self.close()
            raise ValueError("pantograph repl returned unexpected response")
        return response

    def reset(self, theorem: str, imports=()) -> ProofState:
        if imports:
            wanted = tuple(str(item) for item in tuple(imports) if str(item).strip())
            if not wanted:
                wanted = self.modules
        else:
            wanted = self.modules
        if self._active_modules is not None and wanted != self._active_modules:
            self.close()
        self._theorem_counter += 1
        try:
            started = self._send("goal.start", {"expr": theorem}, wanted)
        except ValueError as exc:
            raise ValueError(
                "pantograph reset failed for " + repr(theorem) + ": " + str(exc)
            )
        if "stateId" not in started:
            raise ValueError("pantograph goal.start returned no stateId")
        try:
            state_id = int(started["stateId"])
        except (ValueError, TypeError) as exc:
            raise ValueError("pantograph goal.start returned bad stateId") from exc
        try:
            printed = self._send(
                "goal.print", {"stateId": state_id, "goals": True}, wanted
            )
        except ValueError as exc:
            raise ValueError("pantograph goal.print failed: " + str(exc))
        if printed.get("rootHasSorry") is True:
            raise ValueError("pantograph initial state has sorry")
        if printed.get("rootHasUnsafe") is True:
            raise ValueError("pantograph initial state is unsafe")
        goals, hyps = decode_pantograph_goals(printed.get("goals", []))
        return ProofState(
            goals=goals,
            hypotheses=hyps,
            pending=(),
            backend_token=encode_state_token(state_id),
        )

    def apply(self, state: ProofState, tactic: str) -> ApplyResult:
        stripped = tactic.strip()
        if not stripped:
            return ApplyResult(
                success=False,
                new_state=None,
                error="empty tactic",
                heartbeats=1,
            )
        if state.backend_token is None:
            return ApplyResult(
                success=False,
                new_state=None,
                error="state has no pantograph token; reset with PantographBackend first",
                heartbeats=1,
            )
        try:
            state_id = decode_state_token(state.backend_token)
        except ValueError as exc:
            return ApplyResult(
                success=False, new_state=None, error=str(exc), heartbeats=1
            )
        forbidden = find_forbidden_in_proof(stripped)
        if forbidden is not None:
            return ApplyResult(
                success=False,
                new_state=None,
                error="forbidden token in tactic: " + forbidden,
                heartbeats=1,
            )
        parsed = parse_have_tactic(stripped)
        if parsed is not None:
            name, prop = parsed
            payload: dict = {
                "stateId": state_id,
                "have": prop,
                "binderName": name,
            }
        else:
            payload = {"stateId": state_id, "goalId": 0, "tactic": stripped}
        try:
            response = self._send("goal.tactic", payload)
        except ValueError as exc:
            return ApplyResult(
                success=False, new_state=None, error=str(exc), heartbeats=1
            )
        messages = response.get("messages", [])
        if response.get("hasSorry") is True or has_sorry_warning(
            summarize_messages(messages)
        ):
            return ApplyResult(
                success=False,
                new_state=None,
                error="pantograph reported sorry: " + summarize_messages(messages),
                heartbeats=1,
            )
        if response.get("hasUnsafe") is True:
            return ApplyResult(
                success=False,
                new_state=None,
                error="pantograph reported unsafe: " + summarize_messages(messages),
                heartbeats=1,
            )
        if response.get("parseError") is not None:
            return ApplyResult(
                success=False,
                new_state=None,
                error="pantograph parse error: " + str(response.get("parseError")),
                heartbeats=1,
            )
        if "nextStateId" not in response or response.get("goals") is None:
            detail = summarize_messages(messages) or "pantograph tactic failed"
            return ApplyResult(
                success=False, new_state=None, error=detail, heartbeats=1
            )
        try:
            next_id = int(response["nextStateId"])
        except (ValueError, TypeError) as exc:
            return ApplyResult(
                success=False,
                new_state=None,
                error="pantograph returned bad nextStateId",
                heartbeats=1,
            )
        goals, hyps = decode_pantograph_goals(response.get("goals", []))
        new_state = ProofState(
            goals=goals,
            hypotheses=hyps,
            pending=(),
            backend_token=encode_state_token(next_id),
        )
        return ApplyResult(success=True, new_state=new_state, error=None, heartbeats=1)

    def check_proof(
        self, theorem: str, proof: list[str] | tuple[str, ...], imports=("Mathlib",)
    ) -> bool:
        if find_forbidden_in_proof("\n".join(str(t) for t in proof)) is not None:
            return False
        lines: list[str] = []
        for module in tuple(imports):
            cleaned = str(module).strip()
            if cleaned:
                lines.append("import " + cleaned)
        lines.append("theorem tmp_proof_check : " + theorem + " := by")
        for tactic in proof:
            lines.append("  " + str(tactic))
        marker = chr(35) + "print axioms tmp_proof_check"
        lines.append(marker)
        text = "\n".join(lines) + "\n"
        lake = shutil.which("lake")
        if lake is None:
            return False
        if self.project_dir is not None:
            workdir = str(self.project_dir)
        else:
            workdir = str(default_lean_project_dir())
        with tempfile.TemporaryDirectory(prefix="mathesis_panto_") as tmpdir:
            target = Path(tmpdir) / "Check.lean"
            target.write_text(text, encoding="utf-8")
            try:
                completed = subprocess.run(
                    [lake, "env", "lean", str(target)],
                    cwd=workdir,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )
            except subprocess.TimeoutExpired:
                return False
        combined = completed.stdout + completed.stderr
        if completed.returncode != 0:
            return False
        if "sorryAx" in combined or find_forbidden(combined) is not None:
            return False
        return True
