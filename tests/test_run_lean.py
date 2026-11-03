"""run_lean process management, failure rules and sandbox; verify_proof evidence files."""

import os
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mathesis import llm_baseline as b0


class FakeProc:
    def __init__(self, stdout="", stderr="", returncode=0, pid=4242, effects=None):
        self.pid = pid
        self.returncode = returncode
        self._stdout, self._stderr = stdout, stderr
        self.effects = list(effects) if effects is not None else None
        self.communicate_calls = []
        self.wait_calls = []

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        return self.returncode

    def communicate(self, timeout=None):
        self.communicate_calls.append(timeout)
        if self.effects:
            effect = self.effects.pop(0)
            if isinstance(effect, BaseException):
                raise effect
            return effect
        return self._stdout, self._stderr


class RunLeanBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cand = Path(self._tmp.name) / "cand.lean"
        self.cand.write_text("import Mathlib\n", encoding="utf-8")
        env = mock.patch.dict(os.environ, {b0.SANDBOX_ENV: "off"})
        env.start()
        self.addCleanup(env.stop)

    def run_with(self, proc, **kwargs):
        with mock.patch.object(b0.subprocess, "Popen", return_value=proc) as popen, \
                mock.patch.object(b0.os, "killpg") as killpg:
            try:
                result = b0.run_lean(self.cand, lean_dir=self._tmp.name, **kwargs)
            finally:
                self.popen, self.killpg = popen, killpg
        return result


class RunLeanOutcomeTest(RunLeanBase):
    def test_normal_run_merges_stdout_and_stderr(self):
        result = self.run_with(FakeProc("out ", "err", 0))
        self.assertEqual((result.returncode, result.output, result.timed_out), (0, "out err", False))
        self.killpg.assert_not_called()

    def test_popen_gets_new_session_and_pipes(self):
        self.run_with(FakeProc())
        kwargs = self.popen.call_args.kwargs
        self.assertTrue(kwargs["start_new_session"])
        self.assertEqual(kwargs["cwd"], self._tmp.name)
        self.assertEqual(self.popen.call_args.args[0][-1], str(self.cand.resolve()))

    def test_oserror_is_environment_failure(self):
        with mock.patch.object(b0.subprocess, "Popen", side_effect=FileNotFoundError("lake")):
            with self.assertRaises(b0.EnvironmentFailure):
                b0.run_lean(self.cand, lean_dir=self._tmp.name)

    def test_killed_by_signal_is_environment_failure(self):
        with self.assertRaisesRegex(b0.EnvironmentFailure, "rc=-9"):
            self.run_with(FakeProc("", "", -9))

    def test_broken_toolchain_output_is_environment_failure(self):
        out = "error: unknown module prefix 'Mathlib'"
        with self.assertRaises(b0.EnvironmentFailure):
            self.run_with(FakeProc(out, "", 1))

    def test_lean_error_is_a_normal_result(self):
        out = str(self.cand) + ":3:2: error: unsolved goals\n"
        result = self.run_with(FakeProc(out, "", 1))
        self.assertEqual((result.returncode, result.timed_out), (1, False))

    def test_nonzero_exit_without_diagnostic_is_a_normal_run(self):
        # E.g. a stack overflow abort caused by the proof: judged lean_crash, run goes on.
        for out in ("", "Killed", "Stack overflow detected. Aborting."):
            result = self.run_with(FakeProc(out, "", 134))
            self.assertEqual((result.returncode, result.timed_out), (134, False))
            self.assertEqual(
                b0.judge("\n  simp", result.returncode, result.output)[1:],
                ("lean_crash", "lean exited rc=134 without diagnostics"),
            )

    def test_warning_only_with_nonzero_exit_is_a_normal_run(self):
        result = self.run_with(FakeProc("x.lean:1:0: warning: hi\n", "", 1))
        self.assertEqual(result.returncode, 1)


class MissingFileTest(RunLeanBase):
    def test_lakes_missing_file_message_aborts(self):
        out = "no such file or directory (error code: 2)\n  file: " + str(self.cand.resolve())
        with self.assertRaisesRegex(b0.EnvironmentFailure, "not found"):
            self.run_with(FakeProc(out, "", 1))

    def test_candidate_name_alone_is_enough(self):
        out = "No such file or directory (error code: 2)\n  file: cand.lean"
        with self.assertRaises(b0.EnvironmentFailure):
            self.run_with(FakeProc("", out, 1))

    def test_other_no_such_file_text_does_not_abort(self):
        out = "other.lean:9:1: error: no such file or directory: Foo/Bar.lean\n"
        result = self.run_with(FakeProc(out, "", 1))
        self.assertEqual(result.returncode, 1)
        self.assertIn("Foo/Bar.lean", result.output)

    def test_plain_line_about_another_file_does_not_abort(self):
        out = "error: could not read Foo/Bar.lean: No such file or directory\n"
        self.assertEqual(self.run_with(FakeProc(out, "", 1)).returncode, 1)

    def test_diagnostic_on_the_candidate_does_not_abort(self):
        # A message the proof itself provoked, reported at the candidate's own position.
        out = str(self.cand.resolve()) + ":3:2: error: no such file or directory (cand.lean)\n"
        result = self.run_with(FakeProc(out, "", 1))
        self.assertEqual(result.returncode, 1)

    def test_candidate_must_exist_before_lake_runs(self):
        self.cand.unlink()
        with mock.patch.object(b0.subprocess, "Popen") as popen:
            with self.assertRaisesRegex(b0.EnvironmentFailure, "does not exist"):
                b0.run_lean(self.cand, lean_dir=self._tmp.name)
        popen.assert_not_called()


class RunLeanTimeoutTest(RunLeanBase):
    def timeout(self, stdout=b"partial"):
        return subprocess.TimeoutExpired(["lake"], 5, output=stdout)

    def test_timeout_kills_process_group_and_reaps(self):
        proc = FakeProc(effects=[self.timeout(), ("", "")])
        result = self.run_with(proc, timeout=5)
        self.killpg.assert_called_once_with(4242, signal.SIGKILL)
        self.assertEqual(len(proc.communicate_calls), 2)
        self.assertEqual(proc.communicate_calls[0], 5)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.returncode, -1)

    def test_timeout_keeps_bytes_stdout(self):
        result = self.run_with(FakeProc(effects=[self.timeout(b"par\xffti"), ("", "")]), timeout=5)
        self.assertEqual(result.output, "par�ti")

    def test_timeout_output_from_reaping_call_wins(self):
        result = self.run_with(FakeProc(effects=[self.timeout(None), ("a", "b")]), timeout=5)
        self.assertEqual(result.output, "ab")

    def test_timeout_survives_stuck_pipes(self):
        proc = FakeProc(effects=[self.timeout(), subprocess.TimeoutExpired(["lake"], 10)])
        result = self.run_with(proc, timeout=5)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.output, "partial")
        self.assertEqual(proc.wait_calls, [5])  # killed child is reaped, no zombie

    def test_killpg_on_gone_process_is_ignored(self):
        proc = FakeProc(effects=[self.timeout(), ("", "")])
        with mock.patch.object(b0.subprocess, "Popen", return_value=proc), \
                mock.patch.object(b0.os, "killpg", side_effect=ProcessLookupError):
            result = b0.run_lean(self.cand, lean_dir=self._tmp.name, timeout=5)
        self.assertTrue(result.timed_out)

    def test_keyboard_interrupt_kills_group_and_propagates(self):
        proc = FakeProc(effects=[KeyboardInterrupt(), ("", "")])
        with self.assertRaises(KeyboardInterrupt):
            self.run_with(proc)
        self.killpg.assert_called_once_with(4242, signal.SIGKILL)


class SandboxTest(RunLeanBase):
    def command(self, mode, available=True):
        with mock.patch.dict(os.environ, {b0.SANDBOX_ENV: mode}), \
                mock.patch.object(b0, "_sandbox_available", return_value=available):
            self.run_with(FakeProc())
        return self.popen.call_args.args[0]

    def test_auto_prefixes_unshare_when_available(self):
        cmd = self.command("auto")
        self.assertEqual(cmd[:2], ["unshare", "-rn"])
        self.assertEqual(cmd[2:], b0.lean_verify_command(self.cand))

    def test_auto_without_unshare_has_no_prefix(self):
        self.assertEqual(self.command("auto", available=False), b0.lean_verify_command(self.cand))

    def test_off_has_no_prefix(self):
        self.assertEqual(self.command("off"), b0.lean_verify_command(self.cand))

    def test_default_mode_is_auto(self):
        with mock.patch.dict(os.environ):
            os.environ.pop(b0.SANDBOX_ENV, None)
            with mock.patch.object(b0, "_sandbox_available", return_value=True):
                self.assertEqual(b0.lean_sandbox_info()["mode"], "unshare-net")

    def test_invalid_mode_is_rejected(self):
        with mock.patch.dict(os.environ, {b0.SANDBOX_ENV: "maybe"}):
            with self.assertRaises(b0.EnvironmentFailure):
                b0.run_lean(self.cand, lean_dir=self._tmp.name)
            with self.assertRaises(b0.EnvironmentFailure):
                b0.lean_sandbox_info()

    def test_info_reports_mode_and_whitelist(self):
        with mock.patch.dict(os.environ, {b0.SANDBOX_ENV: "off"}):
            info = b0.lean_sandbox_info()
        self.assertEqual(info["mode"], "none")
        self.assertEqual(info["env_whitelist"], list(b0.LEAN_ENV_WHITELIST))
        with mock.patch.dict(os.environ, {b0.SANDBOX_ENV: "auto"}), \
                mock.patch.object(b0, "_sandbox_available", return_value=True):
            info = b0.lean_sandbox_info()
        self.assertEqual(info["mode"], "unshare-net")
        self.assertEqual(info["command_prefix"], ["unshare", "-rn"])

    def test_probe_is_cached(self):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0)

        with mock.patch.object(b0, "_SANDBOX_PROBE", None), \
                mock.patch.object(b0.subprocess, "run", fake_run):
            self.assertTrue(b0._sandbox_available())
            self.assertTrue(b0._sandbox_available())
        self.assertEqual(calls, [["unshare", "-rn", "true"]])

    def test_probe_failure_means_unavailable(self):
        with mock.patch.object(b0, "_SANDBOX_PROBE", None), \
                mock.patch.object(b0.subprocess, "run", side_effect=FileNotFoundError):
            self.assertFalse(b0._sandbox_available())
        with mock.patch.object(b0, "_SANDBOX_PROBE", None), \
                mock.patch.object(
                    b0.subprocess, "run",
                    return_value=subprocess.CompletedProcess([], 1),
                ):
            self.assertFalse(b0._sandbox_available())


class EnvWhitelistTest(RunLeanBase):
    def test_only_whitelisted_variables_reach_lean(self):
        extra = {
            "SECRET_TOKEN": "hunter2", "HF_TOKEN": "x", "HTTP_PROXY": "http://p",
            "CUDA_VISIBLE_DEVICES": "3", "LANG": "C.UTF-8", "TMPDIR": "/tmp",
        }
        with mock.patch.dict(os.environ, extra):
            self.run_with(FakeProc())
        env = self.popen.call_args.kwargs["env"]
        self.assertTrue(set(env) <= set(b0.LEAN_ENV_WHITELIST))
        for name in ("SECRET_TOKEN", "HF_TOKEN", "HTTP_PROXY", "CUDA_VISIBLE_DEVICES"):
            self.assertNotIn(name, env)
        self.assertEqual(env["LANG"], "C.UTF-8")
        self.assertIn("PATH", env)
        self.assertIn("ELAN_HOME", env)

    def test_home_is_private_and_not_the_real_home(self):
        self.run_with(FakeProc())
        env = self.popen.call_args.kwargs["env"]
        self.assertNotEqual(Path(env["HOME"]).resolve(), Path.home().resolve())
        self.assertTrue(Path(env["HOME"]).is_dir())
        self.assertEqual(os.listdir(env["HOME"]), [])
        self.run_with(FakeProc())
        self.assertEqual(self.popen.call_args.kwargs["env"]["HOME"], env["HOME"])

    def test_elan_home_defaults_to_dot_elan_and_is_kept_if_set(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("ELAN_HOME", None)
            self.assertEqual(b0._lean_env()["ELAN_HOME"], str(Path.home() / ".elan"))
        with mock.patch.dict(os.environ, {"ELAN_HOME": "/opt/elan"}):
            self.assertEqual(b0._lean_env()["ELAN_HOME"], "/opt/elan")

    def test_elan_bin_is_added_to_path_when_lake_is_missing(self):
        with mock.patch.dict(os.environ, {"PATH": "/nonexistent-dir", "ELAN_HOME": "/opt/elan"}):
            self.assertTrue(b0._lean_env()["PATH"].startswith("/opt/elan/bin" + os.pathsep))


class VerifyProofEvidenceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "candidates" / "p0_3.lean"

    def verify(self, proof, run, **kwargs):
        with mock.patch.object(b0, "run_lean", return_value=run):
            return b0.verify_proof("H", proof, "", self.path, **kwargs)

    def test_output_saved_next_to_candidate(self):
        out = str(self.path.parent) + os.sep + "p0_3.lean:2:0: error: bad\n"
        ver = self.verify("\n  simp", b0.LeanRun(1, out, 0.5, False))
        saved = self.path.with_suffix(".out")
        self.assertEqual(saved.name, "p0_3.out")
        self.assertEqual(saved.read_text(encoding="utf-8"), "p0_3.lean:2:0: error: bad\n")
        self.assertEqual(saved.read_text(encoding="utf-8"), ver.output)
        self.assertEqual((ver.passed, ver.failure_class, ver.lean_returncode), (False, "lean_error", 1))

    def test_returncode_none_on_timeout_and_timeout_message(self):
        ver = self.verify("\n  simp", b0.LeanRun(-1, "partial", 5.0, True), timeout=5)
        self.assertEqual((ver.failure_class, ver.first_error_line), ("timeout", "timeout after 5s"))
        self.assertIsNone(ver.lean_returncode)
        self.assertEqual(ver.returncode, -1)
        self.assertTrue(self.path.with_suffix(".out").is_file())

    def test_forbidden_source_proof_and_output(self):
        ver = self.verify("\n  sorry", b0.LeanRun(0, "", 0.1, False))
        self.assertEqual((ver.failure_class, ver.forbidden_source), ("forbidden_token", "proof"))
        out = "f.lean:3:8: warning: declaration uses 'sorry'"
        ver = self.verify("\n  exact?", b0.LeanRun(0, out, 0.1, False))
        self.assertEqual((ver.failure_class, ver.forbidden_source), ("forbidden_token", "output"))
        ver = self.verify("\n  simp", b0.LeanRun(0, "", 0.1, False))
        self.assertEqual((ver.passed, ver.forbidden_source, ver.lean_returncode), (True, None, 0))

    def test_environment_failure_writes_no_evidence(self):
        with mock.patch.object(b0, "run_lean", side_effect=b0.EnvironmentFailure("x")):
            with self.assertRaises(b0.EnvironmentFailure):
                b0.verify_proof("H", "\n  simp", "", self.path)
        self.assertFalse(self.path.with_suffix(".out").exists())


if __name__ == "__main__":
    unittest.main()
