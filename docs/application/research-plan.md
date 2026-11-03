# Research Plan (DRAFT v0.1, 2026-11-03)

> **Status:** working draft for the RIKEN CBS application due 2027-01-08. Items in [square brackets] need input (official requirements, supervisor, page limit). Results marked *measured* were produced by the code in this repository on the dates given; nothing else is claimed.

**Title (working):** Mathesis: Impasse-Triggered Auxiliary Construction for Neural Theorem Proving in Lean 4

**Applicant:** ChiaAn Lin, Master Program for Precision Health and Intelligent Medicine
**Target lab / supervisor:** [not yet designated]

---

## 1. Problem

Large language models that generate whole Lean 4 proofs now solve many routine problems, but they stall on a specific class: problems whose proofs require an **auxiliary construction**, such as an intermediate lemma, a witness, a generalized induction hypothesis, or an auxiliary function. Current systems handle this by sampling more candidates, by decomposing every problem into subgoals up front, or by relying on large-scale search. None of these decides **when** a solver should restructure its representation of the problem, and none measures how much a construction is missing.

Cognitive work on insight describes a similar pattern: a solver fixates on an inadequate representation, reaches an impasse, and a representational change resolves it (Ohlsson, 1992; Knoblich et al., 1999). The AI tradition has a direct precedent in impasse-driven subgoaling (Laird, Newell & Rosenbloom, 1987) and in failure-driven lemma speculation (Ireland & Bundy, 1996). What is missing is an operational, measurable version of this idea inside a modern prover, evaluated under matched compute.

## 2. Research question and hypotheses

**Main question.** In Lean 4, when a language-model prover is stuck on a problem that needs an auxiliary construction, does a control loop that (i) detects an impasse from observable failure signals and (ii) applies a type-checked restructuring operator outperform the same operators triggered on a fixed schedule or at random, at equal compute?

| ID | Hypothesis | Kill criterion |
|---|---|---|
| H1 | On insight problems, impasse-triggered restructuring solves more problems than fixed-schedule and random triggering with the same expected number of triggers | The 95% CI of (Mathesis − max of the two controls) includes 0. **H1 is the kill criterion.** |
| H2 | The gain concentrates on insight problems, not routine controls | Interaction CI includes 0 |
| H3 | Choosing operators from failure traces beats random operator choice | CI includes 0 |

If H1 fails, the project still yields a benchmark and a documented negative result.

## 3. Approach

**Measurement first: construction gap.** For a problem *p*, a fixed prover *M*, and a fixed budget *B*, the construction gap is the difference between the solve probability with a hint and without it, where the hint states the auxiliary construction from a reference proof but not the proof itself. Insight problems are defined operationally as problems with a large gap and a low unhinted solve rate. Each insight problem is paired with a routine control of matched baseline difficulty and near-zero gap. This makes "needs insight" a measured quantity rather than a judgment.

**Control layer (Mathesis).** Three components sit above an unmodified prover:

1. *Impasse detection* from Lean error traces, stalled goal states (hashed), repetition rate, and budget used. Features are fixed on a calibration split only.
2. *Restructuring operators* proposed by the language model from the failure trace, then filtered by Lean type checking and elaboration. Version 1 uses two operators: `AddSubgoal` (introduce an intermediate `have`) and `AddSymbol` (introduce a witness or auxiliary definition). A template-based operator is kept only as an ablation, because hand-written templates can act as an answer oracle.
3. *Operator selection* by a contextual bandit on impasse features, with a random selector as one of the baselines.

**Underlying prover.** DeepSeek-Prover-V2-7B, 4-bit quantized, run locally through MLX. It is a chain-of-thought model; this is a stated deviation from an earlier plan that required a non-CoT prover, and it is reported as such.

**Benchmark.** An insight/routine benchmark built from miniF2F (Zheng, Han & Polu, 2021), from perturbed and newly written problems, and from problems we verify in Lean 4. Contamination is screened by substring search against the Mathlib source and by a memorization probe; the screen is heuristic and reported as such.

**Annotation.** No second human annotator is available. Auxiliary-construction need, difficulty, and Mathlib similarity are labeled with an LLM from a different model family, three runs per item, majority vote. The author blind-labels 20 stratified items, and agreement (Cohen's κ) is reported. All prompts and outputs are released. The primary conclusions do not depend on these labels; they are used for descriptive statistics and a sensitivity analysis.

## 4. Preliminary results (measured)

| Date | Benchmark | Problems × samples | pass@1 | pass@8 | Notes |
|---|---|---|---|---|---|
| 2026-11-02 | Original 50-problem set | 50 × 8 | 0.907 | 1.000 | Saturated; not usable to separate methods |
| 2026-11-03 | New 38-problem set | 38 × 8 | 0.819 | 0.895 | 4 problems unsolved; failures are Lean errors, not harness errors |

- The verification controls passed: all reference proofs are accepted, and deliberately wrong proofs are rejected.
- Failure analysis of the new set (first Lean error of the 55 non-passing samples): 27 are unknown identifiers, mostly Mathlib names, 7 unsolved goals, 3 `omega` failures, 15 other Lean errors, and 3 forbidden tokens. Unknown identifiers mix lemma recall with mathematical difficulty, so the write-up reports them separately.
- The impasse signal is **not yet functional**: in the current pilot the impasse count is zero after an earlier bug fix, so the control layer is not yet a method. Calibration is the first system milestone.
- Earlier runs with a path bug were discarded and are retained in the repository as invalid runs.

These numbers are baseline measurements. They do not yet test any hypothesis.

## 5. Methods of evaluation

- **Baselines at equal compute:** the same prover with no control (B0); fixed-schedule triggering (B1); random triggering with matched expected trigger count (B2); random operator choice (B4); a hint upper bound (UB). Compute is matched by counting generated tokens and Lean calls; wall-clock is reported separately.
- **Splits:** calibration (20 problems, for impasse thresholds), development (30 problems, for operator prompts), and a held-out test split (≥50 problems in the sprint version), used once after pre-registration.
- **Statistics:** mixed-effects logistic regression with problem and family as random effects; paired bootstrap as a check; Holm–Bonferroni correction across hypotheses. Seeds are treated as repeated measures, not independent samples.
- **Reproducibility:** every run writes a manifest with the git commit, seed, Lean and Mathlib versions, and platform, plus per-problem results. Code and benchmark will be released with the write-up.

## 6. Feasibility

- **Hardware:** a single Apple M5 with 24 GB unified memory. Measured throughput: about 23 tokens/s single-stream and about 95 tokens/s with batch size 8. The full baseline run on 50 problems × 8 samples took about 80 minutes wall-clock.
- **Software:** Lean 4 v4.35.0 with a matching Mathlib build; Pantograph and LeanInteract backends exist and have passing gated tests (as of the last full run before the most recent review fixes, which are being re-tested).
- **Scope control:** the sprint version drops full budget sweeps (only 1× and 4×), external benchmark subsets, and the minimal-background track. Each dropped item is listed in the project plan with its reason.

## 7. Timeline (2026-11-03 → 2027-01-08)

| Week (dates) | Work | Milestone |
|---|---|---|
| W1 (11/03–11/09) | Re-run gated tests; prover check on a miniF2F subset (after data is approved); pilot hint-gap measurement | Prover check passes |
| W2–3 (11/10–11/23) | Benchmark v1 (80–100 problems); hint-gap measurement; LLM-assisted annotation with author check | ≥40 insight problems, ≥25 routine pairs |
| W4–5 (11/24–12/07) | Control layer v1 on calibration and development splits; baselines B0, B1, B2, B4 | Development shows a visible gap versus B1/B2, or the project reports a negative result |
| W6 (12/08–12/14) | Freeze algorithm, splits, budget; pre-register H1–H2 | Pre-registration posted |
| W7 (12/15–12/21) | Held-out test run (once); statistics | H1 decision |
| W8–W9 (12/22–01/07) | Ablation; write-up; reproducibility package | Application submitted by 2027-01-08 |

**Honesty about the timeline:** the held-out test run is the riskiest step. If it cannot finish by mid-December, the application reports the pre-registered design and the development results, and does not claim a test-set result.

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| H1 is not supported | A negative result with a benchmark is still a contribution; reported in full |
| The chain-of-thought prover produces few valid proofs | Checked in the first week; switch prover if needed and re-plan |
| Lemma-name recall dominates failures | Separate recall from difficulty in analysis; include a name-hint ablation |
| Small test split reduces power | Pre-register the effect size of interest; report confidence intervals; avoid over-claiming |
| An earlier paper already studies trigger timing | Read it in week 1 and adjust H1 framing |
| LLM labels are biased | Disclosed; author check on 20 items; sensitivity analysis without LLM filtering |

## 9. Expected contributions

1. A measurable definition of construction gap for Lean 4 provers, with a released benchmark of paired insight and routine problems.
2. A controlled, compute-matched test of when to restructure, which is the central question of the project.
3. An open implementation with manifests and a contamination screen, usable by others on consumer hardware.

## 10. Relation to prior work

- *Impasse-driven subgoaling:* Soar (Laird, Newell & Rosenbloom, 1987). Differs in that Mathesis uses a learned or calibrated trigger on a neural prover rather than production rules.
- *Failure-driven lemma speculation:* Ireland & Bundy (1996); Melis (1995). Differs in the trigger timing evaluation under compute matching, and in the LLM proposer.
- *Whole-proof and decomposition provers:* DeepSeek-Prover-V2; DSP; LEGO-Prover. These decompose uniformly; Mathesis decides when to restructure, and the decomposition baseline is included to test that difference.
- *Insight and representational change:* Ohlsson (1992); Knoblich et al. (1999). These motivate the impasse signal; they are not operationalized for Lean in prior work.

## 11. Why this research, why now

Neural provers are improving quickly, but the field has few controlled measurements of which *decisions* the search should make, as opposed to which *model* to use. Mathesis treats the trigger as a first-class decision and measures it. The measurement is cheap enough to be done by one student on a laptop, which is also why the results can be reproduced by others.

---

## References (to verify before submission)

- Chen, M. et al. (2021). Evaluating Large Language Models Trained on Code. arXiv:2107.03374. [verify pass@k definition used]
- Zheng, K., Han, J. M., & Polu, S. (2021). miniF2F: a cross-system benchmark for formal Olympiad-level mathematics. arXiv:2109.00110.
- DeepSeek-AI. DeepSeek-Prover-V2. [add citation]
- Ireland, A., & Bundy, A. (1996). Productive use of failure in inductive proof. Journal of Automated Reasoning. [verify volume]
- Knoblich, G., Ohlsson, S., Haider, H., & Rhenius, D. (1999). Constraint relaxation and chunk decomposition in insight problem solving. Journal of Experimental Psychology: Learning, Memory, and Cognition. [verify]
- Laird, J. E., Newell, A., & Rosenbloom, P. S. (1987). SOAR: An architecture for general intelligence. Artificial Intelligence. [verify]
- Melis, E. (1995). Lemma speculation in proof planning. IJCAI. [verify]
- Ohlsson, S. (1992). Information-processing explanations of insight and related phenomena. [verify]

---

## Open items (input needed)

1. Official requirements: page limit, required sections, submission format, and whether a CV or recommendation letters are required.
2. Supervisor or lab, if one is identified; the direction in §3 may need to change to match it.
3. Personal background for the separate research statement (education, prior research, motivation). Not drafted yet, because it must come from the applicant.
