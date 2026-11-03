import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from mathesis.types import (
    ApplyResult,
    Goal,
    Hypothesis,
    PendingHave,
    ProofState,
    make_atom,
    parse_prop,
    props_equal,
    split_premises,
    is_atom,
)
from mathesis.proof_rules import find_forbidden, find_forbidden_in_proof

SORRY_WARNING = "declaration uses 'sorry'"
# Lean 4.35 quotes the name with backticks (declaration uses `sorry`); older
# versions used single quotes. Match both.
SORRY_WARNING_RE = re.compile(r"declaration uses [`']sorry[`']")


def has_sorry_warning(text: str) -> bool:
    return SORRY_WARNING_RE.search(text) is not None


class LeanBackend(Protocol):
    def reset(self, theorem: str) -> ProofState:
        raise NotImplementedError

    def apply(self, state: ProofState, tactic: str) -> ApplyResult:
        raise NotImplementedError

    def check_proof(self, theorem: str, proof: list[str] | tuple[str, ...]) -> bool:
        raise NotImplementedError


def empty_state_for(theorem: str) -> ProofState:
    prop = parse_prop(theorem)
    return ProofState(goals=(Goal(proposition=prop),), hypotheses=(), pending=())


def lookup_hypothesis(state: ProofState, name: str) -> Hypothesis | None:
    for hyp in state.hypotheses:
        if hyp.name == name:
            return hyp
    return None


def fresh_hypothesis_name(state: ProofState, base: str) -> str:
    existing = {hyp.name for hyp in state.hypotheses}
    existing.update(item.name for item in state.pending)
    if base not in existing:
        return base
    counter = 0
    while True:
        candidate = base + "_" + str(counter)
        if candidate not in existing:
            return candidate
        counter += 1


def promote_finished_haves(
    goals: tuple[Goal, ...],
    hypotheses: tuple[Hypothesis, ...],
    pending: tuple[PendingHave, ...],
) -> tuple[tuple[Hypothesis, ...], tuple[PendingHave, ...]]:
    current_hyps = hypotheses
    current_pending = pending
    while current_pending and len(goals) == current_pending[-1].base_len:
        finished = current_pending[-1]
        current_pending = current_pending[:-1]
        already = any(hyp.name == finished.name for hyp in current_hyps)
        if already:
            continue
        current_hyps = current_hyps + (
            Hypothesis(name=finished.name, proposition=finished.proposition),
        )
    return current_hyps, current_pending


class MockLeanBackend:
    def reset(self, theorem: str) -> ProofState:
        return empty_state_for(theorem)

    def apply(self, state: ProofState, tactic: str) -> ApplyResult:
        stripped = tactic.strip()
        if not stripped:
            return ApplyResult(
                success=False,
                new_state=None,
                error="empty tactic",
                heartbeats=1,
            )
        if stripped.startswith("intro "):
            return self.apply_intro(state, stripped[len("intro "):].strip())
        if stripped.startswith("exact "):
            return self.apply_exact(state, stripped[len("exact "):].strip())
        if stripped.startswith("apply "):
            return self.apply_apply(state, stripped[len("apply "):].strip())
        if stripped.startswith("have "):
            return self.apply_have(state, stripped[len("have "):].strip())
        if stripped.startswith("use "):
            return ApplyResult(
                success=False,
                new_state=None,
                error="use is not supported in propositional mock",
                heartbeats=1,
            )
        return ApplyResult(
            success=False,
            new_state=None,
            error="unknown tactic " + repr(stripped),
            heartbeats=1,
        )

    def apply_intro(self, state: ProofState, name: str) -> ApplyResult:
        if not state.goals:
            return ApplyResult(
                success=False,
                new_state=None,
                error="no goals to introduce",
                heartbeats=1,
            )
        if not name or not name[0].isalpha():
            return ApplyResult(
                success=False,
                new_state=None,
                error="invalid hypothesis name " + repr(name),
                heartbeats=1,
            )
        if lookup_hypothesis(state, name) is not None:
            return ApplyResult(
                success=False,
                new_state=None,
                error="hypothesis already exists " + repr(name),
                heartbeats=1,
            )
        current = state.goals[0]
        rest = state.goals[1:]
        if is_atom(current.proposition):
            return ApplyResult(
                success=False,
                new_state=None,
                error="intro needs an implication goal",
                heartbeats=1,
            )
        assert current.proposition.left is not None
        assert current.proposition.right is not None
        new_hyp = Hypothesis(name=name, proposition=current.proposition.left)
        new_goal = Goal(proposition=current.proposition.right)
        new_goals = (new_goal,) + rest
        new_hyps = state.hypotheses + (new_hyp,)
        final_hyps, final_pending = promote_finished_haves(
            new_goals, new_hyps, state.pending
        )
        new_state = ProofState(
            goals=new_goals, hypotheses=final_hyps, pending=final_pending
        )
        return ApplyResult(success=True, new_state=new_state, error=None, heartbeats=1)

    def apply_exact(self, state: ProofState, name: str) -> ApplyResult:
        if not state.goals:
            return ApplyResult(
                success=False,
                new_state=None,
                error="no goals to close",
                heartbeats=1,
            )
        hyp = lookup_hypothesis(state, name)
        if hyp is None:
            return ApplyResult(
                success=False,
                new_state=None,
                error="unknown hypothesis " + repr(name),
                heartbeats=1,
            )
        current = state.goals[0]
        if not props_equal(hyp.proposition, current.proposition):
            return ApplyResult(
                success=False,
                new_state=None,
                error="exact type mismatch",
                heartbeats=1,
            )
        new_goals = state.goals[1:]
        final_hyps, final_pending = promote_finished_haves(
            new_goals, state.hypotheses, state.pending
        )
        new_state = ProofState(
            goals=new_goals, hypotheses=final_hyps, pending=final_pending
        )
        return ApplyResult(success=True, new_state=new_state, error=None, heartbeats=1)

    def apply_apply(self, state: ProofState, name: str) -> ApplyResult:
        if not state.goals:
            return ApplyResult(
                success=False,
                new_state=None,
                error="no goals to apply",
                heartbeats=1,
            )
        hyp = lookup_hypothesis(state, name)
        if hyp is None:
            return ApplyResult(
                success=False,
                new_state=None,
                error="unknown hypothesis " + repr(name),
                heartbeats=1,
            )
        current = state.goals[0]
        rest = state.goals[1:]
        if props_equal(hyp.proposition, current.proposition):
            new_goals = rest
            final_hyps, final_pending = promote_finished_haves(
                new_goals, state.hypotheses, state.pending
            )
            new_state = ProofState(
                goals=new_goals, hypotheses=final_hyps, pending=final_pending
            )
            return ApplyResult(
                success=True, new_state=new_state, error=None, heartbeats=1
            )
        if is_atom(hyp.proposition):
            return ApplyResult(
                success=False,
                new_state=None,
                error="apply type mismatch",
                heartbeats=1,
            )
        premises, conclusion = split_premises(hyp.proposition)
        if not props_equal(conclusion, current.proposition):
            return ApplyResult(
                success=False,
                new_state=None,
                error="apply conclusion mismatch",
                heartbeats=1,
            )
        new_premise_goals = tuple(Goal(proposition=item) for item in premises)
        new_goals = new_premise_goals + rest
        final_hyps, final_pending = promote_finished_haves(
            new_goals, state.hypotheses, state.pending
        )
        new_state = ProofState(
            goals=new_goals, hypotheses=final_hyps, pending=final_pending
        )
        return ApplyResult(success=True, new_state=new_state, error=None, heartbeats=1)

    def apply_have(self, state: ProofState, payload: str) -> ApplyResult:
        if ":" not in payload:
            return ApplyResult(
                success=False,
                new_state=None,
                error="have needs name and proposition separated by colon",
                heartbeats=1,
            )
        name_part, prop_part = payload.split(":", 1)
        name = name_part.strip()
        prop_text = prop_part.strip()
        if not name:
            return self.add_subgoal(state, prop_text, None)
        return self.add_subgoal(state, prop_text, name)

    def add_subgoal(
        self, state: ProofState, proposition: str, name: str | None = None
    ) -> ApplyResult:
        try:
            prop = parse_prop(proposition)
        except ValueError as exc:
            return ApplyResult(
                success=False, new_state=None, error=str(exc), heartbeats=1
            )
        chosen = name.strip() if name is not None and name.strip() else ""
        if not chosen:
            chosen = fresh_hypothesis_name(
                state, "h_have_" + str(len(state.hypotheses) + len(state.pending))
            )
        if not chosen[0].isalpha():
            return ApplyResult(
                success=False,
                new_state=None,
                error="invalid have name " + repr(chosen),
                heartbeats=1,
            )
        if lookup_hypothesis(state, chosen) is not None:
            return ApplyResult(
                success=False,
                new_state=None,
                error="hypothesis already exists " + repr(chosen),
                heartbeats=1,
            )
        for item in state.pending:
            if item.name == chosen:
                return ApplyResult(
                    success=False,
                    new_state=None,
                    error="pending name already exists " + repr(chosen),
                    heartbeats=1,
                )
        new_goal = Goal(proposition=prop)
        new_goals = (new_goal,) + state.goals
        new_pending = state.pending + (
            PendingHave(name=chosen, proposition=prop, base_len=len(state.goals)),
        )
        new_state = ProofState(
            goals=new_goals, hypotheses=state.hypotheses, pending=new_pending
        )
        return ApplyResult(success=True, new_state=new_state, error=None, heartbeats=1)

    def check_proof(
        self, theorem: str, proof: list[str] | tuple[str, ...]
    ) -> bool:
        try:
            state = self.reset(theorem)
        except ValueError:
            return False
        for tactic in proof:
            result = self.apply(state, tactic)
            if not result.success or result.new_state is None:
                return False
            state = result.new_state
        return len(state.goals) == 0


def require_lean_interact():
    try:
        from lean_interact import (
            Command,
            LeanREPLConfig,
            LeanServer,
            LocalProject,
            ProofStep,
        )
        from lean_interact.interface import LeanError
    except ImportError as exc:
        raise RuntimeError(
            "lean_interact is not available in this Python; "
            "run with .venv/bin/python "
            "(LeanInteract 0.11.6 is installed in .venv)."
        ) from exc
    return (Command, LeanError, LeanREPLConfig, LeanServer, LocalProject, ProofStep)


def default_lean_project_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "lean"


def split_lean_hyp(line: str) -> tuple[list[str], str] | None:
    if " : " not in line:
        return None
    names_part, _, type_part = line.partition(" : ")
    names = names_part.split()
    cleaned = type_part.strip()
    if not names or not cleaned:
        return None
    return names, cleaned


def split_lean_goal_text(text: str) -> tuple[str, list[tuple[str, str]]]:
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    if lines and lines[0].startswith("case "):
        lines = lines[1:]
    marker = -1
    for index, line in enumerate(lines):
        if line.startswith("⊢"):
            marker = index
            break
    if marker < 0:
        return " ".join(lines).strip(), []
    goal = (lines[marker][1:].strip() + " " + " ".join(lines[marker + 1 :])).strip()
    pairs: list[tuple[str, str]] = []
    for line in lines[:marker]:
        parsed = split_lean_hyp(line)
        if parsed is None:
            continue
        names, type_text = parsed
        for name in names:
            pairs.append((name, type_text))
    if not goal:
        goal = text.strip()
    return goal, pairs


def decode_lean_goals(
    raw_goals: list[str] | tuple[str, ...],
) -> tuple[tuple[Goal, ...], tuple[Hypothesis, ...]]:
    goals: list[Goal] = []
    hyps: list[Hypothesis] = []
    seen: set[str] = set()
    for text in raw_goals:
        goal_text, pairs = split_lean_goal_text(text)
        goals.append(Goal(proposition=make_atom(goal_text)))
        for name, type_text in pairs:
            if name in seen:
                continue
            seen.add(name)
            hyps.append(Hypothesis(name=name, proposition=make_atom(type_text)))
    return tuple(goals), tuple(hyps)


def build_import_prefix(imports: tuple[str, ...] | list[str] = ()) -> str:
    prefix = ""
    for module in tuple(imports):
        cleaned = str(module).strip()
        if cleaned:
            prefix += "import " + cleaned + "\n"
    return prefix


def build_reset_command(
    name: str, theorem: str, imports: tuple[str, ...] | list[str] = ()
) -> str:
    return (
        build_import_prefix(imports)
        + "theorem " + name + " : " + theorem + " := by sorry"
    )


class SubprocessLeanBackend:
    def __init__(self, project_dir=None, timeout=120, imports=()):
        if project_dir is None:
            self.project_dir = None
        else:
            self.project_dir = Path(project_dir)
        self.timeout = timeout
        self.imports = tuple(str(item) for item in tuple(imports) if str(item).strip())
        self._server = None
        self._theorem_counter = 0

    def _ensure_server(self):
        _, _, LeanREPLConfig, LeanServer, LocalProject, _ = require_lean_interact()
        if self._server is not None:
            try:
                if self._server.is_alive():
                    return self._server
            except Exception:
                pass
            try:
                self._server.kill()
            except Exception:
                pass
            self._server = None
        if self.project_dir is not None:
            directory = self.project_dir
        else:
            directory = default_lean_project_dir()
        if directory.is_dir():
            config = LeanREPLConfig(project=LocalProject(directory=str(directory)))
        else:
            config = LeanREPLConfig()
        self._server = LeanServer(config)
        return self._server

    def reset(self, theorem: str) -> ProofState:
        Command, LeanError, _, _, _, _ = require_lean_interact()
        server = self._ensure_server()
        self._theorem_counter += 1
        name = "mathesis_replay_" + str(self._theorem_counter)
        try:
            response = server.run(
                Command(cmd=build_reset_command(name, theorem, self.imports)),
                timeout=self.timeout,
            )
        except Exception as exc:
            raise ValueError(
                "lean reset failed for " + repr(theorem) + ": " + str(exc)
            )
        if isinstance(response, LeanError):
            raise ValueError(
                "invalid theorem " + repr(theorem) + ": " + response.message.strip()
            )
        sorries = getattr(response, "sorries", [])
        if not sorries or sorries[0].proof_state is None:
            raise ValueError("lean returned no proof state for " + repr(theorem))
        raw_goal = sorries[0].goal.strip()
        if raw_goal.startswith("⊢"):
            raw_goal = raw_goal[1:].strip()
        goals = (Goal(proposition=make_atom(raw_goal)),) if raw_goal else ()
        return ProofState(
            goals=goals,
            hypotheses=(),
            pending=(),
            backend_token=str(sorries[0].proof_state),
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
                error="state has no Lean proof-state token; reset with SubprocessLeanBackend first",
                heartbeats=1,
            )
        try:
            token = int(state.backend_token)
        except ValueError:
            return ApplyResult(
                success=False,
                new_state=None,
                error="invalid backend token " + repr(state.backend_token),
                heartbeats=1,
            )
        forbidden = find_forbidden_in_proof(stripped)
        if forbidden is not None:
            return ApplyResult(
                success=False,
                new_state=None,
                error="forbidden token in tactic: " + forbidden,
                heartbeats=1,
            )
        _, LeanError, _, _, _, ProofStep = require_lean_interact()
        server = self._ensure_server()
        try:
            response = server.run(
                ProofStep(proofState=token, tactic=stripped),
                timeout=self.timeout,
            )
        except Exception as exc:
            return ApplyResult(
                success=False,
                new_state=None,
                error="lean tactic failed " + repr(stripped) + ": " + str(exc),
                heartbeats=1,
            )
        if isinstance(response, LeanError):
            detail = response.message.strip() or "lean error"
            return ApplyResult(
                success=False, new_state=None, error=detail, heartbeats=1
            )
        errors = [
            message.data
            for message in response.messages
            if message.severity == "error"
        ]
        if errors:
            return ApplyResult(
                success=False,
                new_state=None,
                error="; ".join(errors),
                heartbeats=1,
            )
        if any(has_sorry_warning(str(message.data)) for message in response.messages):
            return ApplyResult(
                success=False,
                new_state=None,
                error=SORRY_WARNING,
                heartbeats=1,
            )
        status = response.proof_status or ""
        if status.startswith("Completed"):
            new_state = ProofState(
                goals=(),
                hypotheses=state.hypotheses,
                pending=(),
                backend_token=str(response.proof_state),
            )
            return ApplyResult(
                success=True, new_state=new_state, error=None, heartbeats=1
            )
        if not response.goals:
            detail = status.strip() or "tactic left no goals without completing"
            return ApplyResult(
                success=False, new_state=None, error=detail, heartbeats=1
            )
        goals, hyps = decode_lean_goals(response.goals)
        new_state = ProofState(
            goals=goals,
            hypotheses=hyps,
            pending=(),
            backend_token=str(response.proof_state),
        )
        return ApplyResult(success=True, new_state=new_state, error=None, heartbeats=1)

    def render_file(self, theorem: str, proof: list[str] | tuple[str, ...]) -> str:
        # Propositional benchmark statements use free P/Q/R (e.g. "P -> Q -> P");
        # keep the variable line so they elaborate, as before imports were added.
        lines = ["variable (P Q R : Prop)", "theorem tmp_proof_check : " + theorem + " := by"]
        for tactic in proof:
            lines.append("  " + tactic)
        return build_import_prefix(self.imports) + "\n".join(lines) + "\n"

    def resolve_command(self, target: str) -> list[str]:
        lake = shutil.which("lake")
        lean = shutil.which("lean")
        if self.project_dir is not None and lake is not None:
            return [lake, "env", "lean", target]
        if lean is not None:
            return [lean, target]
        raise RuntimeError(
            "Lean toolchain not found on PATH; "
            "install elan and ensure lean or lake is available."
        )

    def check_proof(
        self, theorem: str, proof: list[str] | tuple[str, ...]
    ) -> bool:
        proof_text = "\n".join(str(tactic) for tactic in proof)
        if find_forbidden_in_proof(proof_text) is not None:
            return False
        text = self.render_file(theorem, proof)
        with tempfile.TemporaryDirectory(prefix="mathesis_lean_") as tmpdir:
            target = Path(tmpdir) / "Check.lean"
            target.write_text(text, encoding="utf-8")
            command = self.resolve_command(str(target))
            if self.project_dir is not None:
                workdir = str(self.project_dir)
            else:
                workdir = tmpdir
            try:
                completed = subprocess.run(
                    command,
                    cwd=workdir,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )
            except subprocess.TimeoutExpired:
                return False
        if completed.returncode != 0:
            return False
        output = (completed.stdout or "") + (completed.stderr or "")
        return find_forbidden(output) is None
