"""Parallel Lean verification in run_b0 / run_hint_gap: ordering, bounds, errors, CLI."""

import contextlib
import io
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from mathesis import llm_baseline as b0

K = 5


class FakeRun:
    def __init__(self, path):
        self.path = Path(path)
        self.rows = []

    def append_result(self, record):
        self.rows.append(record)


def make_problems(n):
    return [
        {"name": "p" + str(i), "header": "H" + str(i), "footer": "F",
         "insight": True, "auxiliary": "aux" + str(i)}
        for i in range(n)
    ]


def fake_generate(model, tokenizer, prompt_ids, k, max_tokens, temp, seed, backend):
    # texts encode the prompt id so each prompt differs; sample 1 has no proof.
    tag = str(prompt_ids[0])
    texts = ["NOPROOF" if i == 1 else tag + "_" + str(i) for i in range(k)]
    return texts, [10 + i for i in range(k)], 1.5


def fake_encode(tokenizer, prompt):
    return [prompt]


def fake_extract(text, header):
    if text == "NOPROOF":
        return None, "no_proof"
    return text, ""


class FakeVerifier:
    """Deterministic delays (later samples finish first); tracks concurrency."""

    def __init__(self, delay_scale=0.004):
        self.lock = threading.Lock()
        self.active = 0
        self.max_active = 0
        self.calls = 0
        self.delay_scale = delay_scale

    def __call__(self, header, proof, footer, path, lean_dir=None, timeout=None):
        with self.lock:
            self.active += 1
            self.calls += 1
            self.max_active = max(self.max_active, self.active)
        try:
            index = int(proof.rsplit("_", 1)[1])
            time.sleep(self.delay_scale * (K - index))
            return b0.Verification(
                index % 2 == 0, "ok" if index % 2 == 0 else "lean_error",
                "" if index % 2 == 0 else "err " + header + " " + str(index),
                0.25 * index, 0, "",
            )
        finally:
            with self.lock:
                self.active -= 1


def patched(verifier):
    return contextlib.ExitStack(), [
        mock.patch.object(b0, "load_model", return_value=("m", "t")),
        mock.patch.object(b0, "encode_prompt", fake_encode),
        mock.patch.object(b0, "generate_samples", fake_generate),
        mock.patch.object(b0, "extract_proof", fake_extract),
        mock.patch.object(b0, "verify_proof", verifier),
    ]


def run_with(fn, verifier, **kwargs):
    stack, patches = patched(verifier)
    with stack, tempfile.TemporaryDirectory() as tmp:
        for p in patches:
            stack.enter_context(p)
        run = FakeRun(tmp)
        lines = []
        result = fn(run, progress=lines.append, **kwargs)
        files = sorted(x.name for x in (run.path / "responses").iterdir())
        texts = {x.name: x.read_text() for x in (run.path / "responses").iterdir()}
        return run.rows, lines, result, files, texts


def b0_call(problems, workers):
    return lambda run, progress: b0.run_b0(
        run, problems, K, 64, 7, progress=progress, verify_workers=workers
    )


def expected_b0_rows(problems):
    rows = []
    for prob in problems:
        derived = b0.derived_b0_seed(7, prob["name"])
        for i in range(K):
            has_proof = i != 1
            passed = has_proof and i % 2 == 0
            if not has_proof:
                fc, fe, vs = "no_proof", "no_proof", 0.0
            else:
                fc = "ok" if passed else "lean_error"
                fe = "" if passed else "err " + prob["header"] + " " + str(i)
                vs = 0.25 * i
            rows.append({
                "problem": prob["name"], "sample_index": i, "passed": passed,
                "first_error_line": fe, "generated_tokens": 10 + i,
                "gen_seconds": 1.5, "verify_seconds": vs, "seed": 7,
                "derived_seed": derived, "failure_class": fc, "truncated": False,
            })
    return rows


class ParallelOrderTest(unittest.TestCase):
    def test_rows_match_sequential_order_and_content(self):
        problems = make_problems(4)
        rows, lines, summary, files, _ = run_with(b0_call(problems, 12), FakeVerifier())
        self.assertEqual(rows, expected_b0_rows(problems))
        self.assertEqual(
            lines,
            ["[" + str(i + 1) + "/4] p" + str(i) + " passed 3/5" for i in range(4)],
        )
        self.assertEqual(len(files), 4 * K)
        self.assertEqual(summary, b0.summarize_b0(
            {"p" + str(i): b0._problem_stats(5, 3, K) for i in range(4)}, K))

    def test_one_worker_equals_many_workers(self):
        problems = make_problems(3)
        one = run_with(b0_call(problems, 1), FakeVerifier(0.001))
        many = run_with(b0_call(problems, 12), FakeVerifier(0.001))
        self.assertEqual(one[0], many[0])
        self.assertEqual(one[1], many[1])
        self.assertEqual(one[2], many[2])
        self.assertEqual(one[3], many[3])
        self.assertEqual(one[4], many[4])
        self.assertEqual(one[0], expected_b0_rows(problems))

    def test_hint_gap_order_and_progress(self):
        problems = make_problems(3)

        def call(run, progress):
            return b0.run_hint_gap(
                run, problems, K, 64, 7, progress=progress, verify_workers=12
            )

        rows, lines, summary, files, _ = run_with(call, FakeVerifier())
        order = [(r["problem"], r["condition"], r["sample_index"]) for r in rows]
        self.assertEqual(
            order,
            [("p" + str(p), c, i) for p in range(3) for c in ("plain", "hint")
             for i in range(K)],
        )
        self.assertEqual(len(files), 3 * 2 * K)
        self.assertEqual(
            lines,
            ["[" + str(i + 1) + "/3] p" + str(i) + " plain 3/5 hint 3/5" for i in range(3)],
        )
        seq = run_with(
            lambda run, progress: b0.run_hint_gap(
                run, problems, K, 64, 7, progress=progress, verify_workers=1
            ),
            FakeVerifier(0.001),
        )
        self.assertEqual(seq[0], rows)
        self.assertEqual(seq[2], summary)

    def test_hint_gap_rows_keep_condition_derived_seed(self):
        problems = make_problems(1)

        def call(run, progress):
            return b0.run_hint_gap(
                run, problems, K, 64, 7, progress=progress, verify_workers=4
            )

        rows = run_with(call, FakeVerifier(0.0))[0]
        self.assertEqual(rows[0]["derived_seed"], b0.derived_b0_seed(7, "p0#plain"))
        self.assertEqual(rows[K]["derived_seed"], b0.derived_b0_seed(7, "p0#hint"))


class WorkerBoundTest(unittest.TestCase):
    def test_never_exceeds_verify_workers(self):
        for workers in (1, 3):
            verifier = FakeVerifier(0.01)
            run_with(b0_call(make_problems(4), workers), verifier)
            self.assertLessEqual(verifier.max_active, workers)
            self.assertEqual(verifier.calls, 4 * (K - 1))
        verifier = FakeVerifier(0.01)
        run_with(b0_call(make_problems(4), 3), verifier)
        self.assertGreater(verifier.max_active, 1)

    def test_pool_is_shared_so_prompts_overlap(self):
        # With a per-prompt pool of 12 only K-1=4 checks could ever run together;
        # a shared pool lets the next prompts' checks start while earlier ones run.
        verifier = FakeVerifier(0.03)
        run_with(b0_call(make_problems(6), 12), verifier)
        self.assertGreater(verifier.max_active, K - 1)

    def test_invalid_workers_rejected(self):
        for bad in (0, -1):
            with self.assertRaises(ValueError):
                b0.run_b0(FakeRun("."), [], 1, 1, 0, verify_workers=bad)
            with self.assertRaises(ValueError):
                b0.run_hint_gap(FakeRun("."), [], 1, 1, 0, verify_workers=bad)


class ExceptionTest(unittest.TestCase):
    def test_verifier_error_propagates_after_earlier_rows(self):
        base = FakeVerifier(0.001)

        def failing(header, proof, footer, path, lean_dir=None, timeout=None):
            if header == "H1" and proof.endswith("_3"):
                raise RuntimeError("lean exploded")
            return base(header, proof, footer, path, lean_dir)

        stack, patches = patched(failing)
        with stack, tempfile.TemporaryDirectory() as tmp:
            for p in patches:
                stack.enter_context(p)
            run = FakeRun(tmp)
            with self.assertRaisesRegex(RuntimeError, "lean exploded"):
                b0.run_b0(run, make_problems(3), K, 64, 7, progress=lambda s: None,
                          verify_workers=12)
        # Same rows the sequential code had logged before failing: all of p0,
        # then p1 samples 0..2 (sample 3 raised).
        expected = expected_b0_rows(make_problems(3))
        self.assertEqual(run.rows, expected[: K + 3])

    def test_generation_error_still_flushes_submitted_prompts(self):
        calls = []

        def gen(*args):
            calls.append(1)
            if len(calls) == 3:
                raise ValueError("gpu fell over")
            return fake_generate(*args)

        stack, patches = patched(FakeVerifier(0.001))
        with stack, tempfile.TemporaryDirectory() as tmp:
            for p in patches:
                stack.enter_context(p)
            stack.enter_context(mock.patch.object(b0, "generate_samples", gen))
            run = FakeRun(tmp)
            with self.assertRaisesRegex(ValueError, "gpu fell over"):
                b0.run_b0(run, make_problems(4), K, 64, 7, progress=lambda s: None,
                          verify_workers=12)
        self.assertEqual(run.rows, expected_b0_rows(make_problems(4))[: 2 * K])


class VerifyWorkersCliTest(unittest.TestCase):
    def test_default_is_12_for_both_subcommands(self):
        from mathesis import cli

        seen = {}

        def fake_b0(*args, **kwargs):
            seen["b0"] = kwargs
            return 0

        def fake_hg(*args, **kwargs):
            seen["hg"] = kwargs
            return 0

        with mock.patch.object(cli, "run_b0_command", fake_b0), \
                mock.patch.object(cli, "run_hint_gap_command", fake_hg):
            self.assertEqual(cli.main(["b0"]), 0)
            self.assertEqual(cli.main(["hint-gap"]), 0)
            self.assertEqual(seen["b0"]["verify_workers"], 12)
            self.assertEqual(seen["hg"]["verify_workers"], 12)
            cli.main(["b0", "--verify-workers", "3"])
            cli.main(["hint-gap", "--verify-workers", "5"])
            self.assertEqual(seen["b0"]["verify_workers"], 3)
            self.assertEqual(seen["hg"]["verify_workers"], 5)
        self.assertEqual(b0.DEFAULT_VERIFY_WORKERS, 12)

    def test_commands_reject_nonpositive_and_pass_through(self):
        from mathesis import cli

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.run_b0_command(1, 1, 8, verify_workers=0), 2)
            self.assertEqual(cli.run_hint_gap_command(1, 1, 8, verify_workers=0), 2)
        with tempfile.TemporaryDirectory() as out, \
                mock.patch.object(b0, "run_b0", return_value={"ok": 1}) as run, \
                mock.patch.object(b0, "format_b0_summary", return_value=""), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.run_b0_command(1, 1, 8, out=out, verify_workers=4), 0)
        self.assertEqual(run.call_args.kwargs["verify_workers"], 4)


if __name__ == "__main__":
    unittest.main()
