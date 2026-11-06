# 負面結果：hint-gap 在 DeepSeek-Prover-V2-7B 與 `lean_hard` 上的結果（草稿）

> 狀態：草稿（2026-11-06）。對應 `docs/paper-plan.md` §11 的 G1 判定與路線決定。數字後括號內為來源檔；無法由檔案核對者列於第 9 節。

## 摘要

在 DeepSeek-Prover-V2-7B、提示規則「`reference_proof` 的第一個 `have`」、`lean_hard` 題組（啟用 92 題，本次比較 38 題）下，沒有足夠的題目顯示提示有穩定效果。依本文的判定規則（規則是在資料大部分已見之後才定下，並非預先登記，見第 1 節），38 題中有 18 題「有資訊」（可由 hint-gap 判讀）。未校正 p<0.05 的「hint 有效」有 3 題，「hint 有害」有 1 題；經 Holm 校正後，主要家族只有 1 題通過（`lean_logic_drinker_implication`）。因此無法依 hint-gap 圈出原計畫要求的 ≥40 題 insight 子集。

此結果只適用於本文描述的單一證明器與單一提示規則，不推廣到其他證明器或其他提示形式。Mathesis 控制層（H1）未檢驗，Mathesis 也未實作。

（來源：`runs/analysis/significance_k32_combined.json` 的 `summary`）

## 1. 研究問題與判定規則

**研究問題**：固定證明器與提示規則時，能否由 hint-gap 找出「提示明顯有效」的題目子集？

**定義**

- 每題每條件取樣 k=32 次。成功率 = 成功次數 c / 32（程式中的 `pass_at_1` 欄位，見 `scripts/hint_significance.py` 第 198–199 行）。
- hint-gap = hint 成功率 − plain 成功率。
- 每題以 Fisher 精確檢定（二側，`fisher_exact_2x2`）比較 2×2 表。α = 0.05（`ALPHA = 0.05`，同檔第 22 行）。
- **hint 有效**：p < 0.05 且 gap > 0。**hint 有害**：p < 0.05 且 gap < 0。
- **天花板**：plain 成功次數 = 32 的題，不檢定。

**多重比較（Holm step-down）**

- **主要分析**的家族：有資訊的題，即非天花板且 plain 與 hint 成功次數合計 ≥ 1。
- **敏感度分析**的家族：所有非天花板的已檢定題。
- 上述家族定義與程式一致（`scripts/hint_significance.py` 第 7–8 行、第 238–250 行）。

**規則的時間點（並非預先登記）**

- 判定規則記載於 `docs/paper-plan.md` §11 的「insight 題的判定規則」段，日期 2026-11-06。**定規則時，舊 23 題的 k=32 結果已看過，新 15 題中也已看過 12 題（shard0/1/2）**；只有 shard3 的 3 題（`real_r_nested_diff`、`nat_r_sophie_germain_composite`、`algebra_r_sq_hom_comm`）是在規則之後才出現。因此本文不主張預先登記。
- 結論對規則中最有爭議的一項（Holm 家族）不敏感：38 題合併後，主要家族（18 題）與敏感度家族（38 題）都只有 `lean_logic_drinker_implication` 通過。
- 原目標「insight ≥ 40 題」改為實際可得題數。本文件只能引用 paper-plan 的文字記載，見第 9 節。

## 2. 資料與方法

**題組**

| 項目 | 內容 | 來源 |
|---|---|---|
| 題組 | `benchmark/lean_hard`，`problems.json` 共 109 題，啟用 92 題（退役 17 題） | `benchmark/lean_hard/problems.json`，`runs/analysis/b0_report_k8_2seeds.json` |
| 比較題 | 38 題 = 舊 23 題（`20261104T131752Z_hint-gap-merged`）＋ 新 15 題（`20261106T061711Z_hint-gap-merged`，B0 篩選後非天花板者） | 兩個 manifest 的 `args.problems`，`docs/paper-plan.md` §11.1 |

**提示（hint）**

- 規則（兩個 manifest 相同）：`first typed have in reference_proof, as '<name> : <statement>'`，即取 `reference_proof` 中第一個有型別標註的 `have`。
- 檔案：舊 23 題使用 `benchmark/lean_hard/hints/first_have.json`（37 項），新 15 題使用 `benchmark/lean_hard/hints/first_have_v2.json`（46 項）。兩檔的 `rule` 欄位相同。v2 內舊 23 題的 hint 與 v1 逐一相同（本次核對 23 題）。
- 提示模板（manifest 的 `prompt_template` 與 `hint_prompt_template`）：
  - plain：`Complete the following Lean 4 code:` 後接 lean4 程式區塊。
  - hint：`Complete the following Lean 4 code. A useful auxiliary step is: {hint}` 後接同樣的區塊。

**模型與取樣**（`runs/20261104T131752Z_hint-gap-merged/manifest.json` 的 `args`）

- 模型：`deepseek-ai/DeepSeek-Prover-V2-7B`，backend `transformers`。
- temperature 0.6，max_tokens 1024，k = 32，基礎 seed = 0。
- 每題每條件的種子由題名推導：`derive_seed(seed, problem, config)`，取 SHA-256（`"seed:problem:config"`）前 8 bytes（`src/mathesis/runlog.py` 第 101–104 行）。
- 4 GPU 分片（manifest 的 `shard_runs` 有 4 項，即 `shard0`–`shard3`）。`verify_workers` = 3。

**判定與沙箱**

- judge v2：forbidden token 先剝除證明文字中的註解再檢查，Lean 輸出逐字檢查，並新增 `lean_crash`（`docs/paper-plan.md` §11 表格第 16 列，commit `246539e`）。本次以 `git merge-base --is-ancestor` 確認 `246539e` 是 manifest 的 `git_commit`（`39cbd1c`）的祖先。
- Lean 子行程：`lake env lean <candidate.lean>`，cwd 為 `lean/`，timeout 180 秒。沙箱 `mode` 為 `unshare-net`（`unshare -rn`），環境變數白名單為 PATH、ELAN_HOME、LANG、LC_ALL、TMPDIR、HOME（manifest 的 `lean_sandbox`）。

**分析**

- `scripts/hint_significance.py` 合併兩個 k=32 run 目錄，輸出 `runs/analysis/significance_k32_combined.json`。兩個 run 的題目集合不重疊（交集為 0）。

## 3. 結果

**摘要計數**（`runs/analysis/significance_k32_combined.json` 的 `summary`）

| 項目 | 數 |
|---|---|
| 已檢定題數 | 38 |
| 天花板（不檢定） | 0 |
| 有資訊的題（主要家族） | 18 |
| 未校正 p<0.05 的 hint 有效 | 3 |
| 未校正 p<0.05 的 hint 有害 | 1 |
| 無可偵測效應 | 34 |
| Holm 後通過（主要家族，18 題） | 1 |
| Holm 後通過（敏感度家族，38 題） | 1 |

- Holm 後通過的題是 `lean_logic_drinker_implication`：plain 3/32、hint 27/32，gap +0.75，p = 1.26e-9，p_holm = 2.26e-8，p_holm_all = 4.77e-8。
- 未校正 p<0.05 的 hint 有效題為 `lean_logic_drinker_implication`、`lean_ineq_sq_sum_abc_four`（0/32 → 8/32，p = 0.0048）與 `lean_nat_sum_even`（5/32 → 14/32，p = 0.027）。
- 未校正 p<0.05 的 hint 有害題為 `lean_algebra_r_sq_hom_comm`（27/32 → 18/32，p = 0.027）。
- 逐題表格見附錄 A。

## 4. k=8 與 k=32 的對照，以及 seed 噪音下限

**(a) 小樣本的 gap 不可信**：以 `lean_real_geom_mean_two` 為例。

| 設定 | plain | hint | gap | p | 來源 |
|---|---|---|---|---|---|
| k=8（`20261104T074803Z_hint-gap-merged`，judge v2） | 1/8 | 6/8 | +0.625 | 未檢定 | `runs/analysis/hint_gap_report_20261104T074803Z_hint-gap-merged.json`（`/per_problem`） |
| k=32（合併 38 題） | 12/32 | 16/32 | +0.125 | 0.450 | `runs/analysis/significance_k32_combined.json` |

k=8 的 +0.625 在 k=32 縮為 +0.125，p = 0.45。

**(b) seed 間噪音下限**（無提示 B0，k=8）

B0 的 seed 比較見 `runs/analysis/b0_report_k8_2seeds.json`。下表的第一列為本次以 `scripts/b0_report.py` 的 `load_seed_problems` 重算（該檔未輸出此子集）。

| 子集 | 題數 | 逐題 \|Δpass@1\| 最大值 | 來源 |
|---|---|---|---|
| 原 89 題 | 89 | 0.25 | 本次重算：seed 0 = `20261103T122531Z_b0`，seed 1 = `20261104T054619Z_b0-merged` |
| 新增 20 題 | 20 | 0.625 | 本次重算：seed 0 = `20261104T141934Z_b0-merged`，seed 1 = `20261104T150345Z_b0-merged` |
| 啟用 92 題 | 92 | 0.625 | `b0_report_k8_2seeds.json` 的 `noise_floor.active.max` |
| 全部 109 題 | 109 | 0.625 | `b0_report_k8_2seeds.json` 的 `noise_floor.all.max` |

- 最大值 0.625 的題為 `lean_nat_r_mod_seven_pow`：seed 0 為 7/8，seed 1 為 2/8。
- 原 89 題中最大值 0.25 的題為 `lean_logic_peirce`、`lean_nat_cube_lt_three_pow`、`lean_real_frac_lt_one`、`lean_real_nested_sqrt_sum`。
- 這是 k=8、無提示的 seed 間差異，不是 k=32 hint-gap 的噪音。它顯示小樣本下單題就可出現 0.25–0.625 的差異。

## 5. 為何不能解讀為「構造性提示沒有幫助」

1. **基線與受測為同一模型**。plain 與 hint 都是 DeepSeek-Prover-V2-7B 的輸出。結果描述的是此模型在此提示規則下的行為，不是某類提示的性質。

2. **檢定力不足**。以 n = 32 對 32、基線成功率 0.5、二側 Fisher 精確檢定（α = 0.05）計算：
   - 公式：power(δ) = Σ over (x, y) with y > x and p_Fisher(x, y) < 0.05 of Binom(x; 32, 0.5) · Binom(y; 32, 0.5 + δ)。
   - δ = 0.25：power = 0.46。
   - δ = 0.125：power = 0.13（0.127）。
   - 假設：獨立二項分佈、基線固定為 0.5。實際基線因題而異，本次未量測其他基線。這是單點計算，不是正式的效力分析。

3. **結果對 hint 的選擇敏感**。`lean_real_lucas_five` 在 k=8、人工 hint 下 gap = +0.875（`runs/analysis/hint_gap_report_20261103T154014Z_hint-gap.json`，`abs_gap` = 0.875）。改為「第一個 `have`」後 gap = 0（依 `docs/paper-plan.md` §11.1 的 `20261104T074803Z` 列，本次未重算）。注意 `20261103T154014Z` 使用 judge v1，且其 `lean_ineq_cube_sum_zero_sixth` 的 hint 係數有誤（paper-plan §11.1 記載）。因此這組對照只能作為定性例子。

4. **多重檢定**。38 題在 α = 0.05 下，若所有題都是虛無假設，預期約 38 × 0.05 = 1.9 次 p<0.05（假設獨立）。實際未校正 p<0.05 共 4 題（3 有效、1 有害）。
   - `lean_nat_sum_even`（p = 0.027）、`lean_ineq_sq_sum_abc_four`（p = 0.0048）、`lean_algebra_r_sq_hom_comm`（hint 有害，p = 0.027）與預期假陽性的量級相當。它們的主要家族 p_holm 分別為 0.435、0.081、0.435，不宜單獨解讀為效應或傷害。
   - `lean_logic_drinker_implication` 是唯一在主要與敏感度家族都通過 Holm 的題（p_holm = 2.26e-8）。但它仍只來自單一證明器、單一提示規則、單一 seed。

5. **主要家族的組成會改變結論**。只用舊 23 題時（有資訊 11 題，Holm 後通過 2 題），`lean_ineq_sq_sum_abc_four` 的主要 p_holm = 0.0475，通過 α = 0.05。合併新 15 題後（有資訊 18 題），p_holm 升到 0.081，不再通過。本次以 `scripts/hint_significance.py` 的 `build_significance_report` 對 23 題重算，未寫入檔案，值為 0.04753。因此這個結論不穩，不應只依 p 值門檻判讀。

## 6. 對資料集使用者的含意

- `insight` 標籤（`benchmark/lean_hard/problems.json` 的 `insight` 欄位）是結構標註：標示「解法是否需要非顯然的輔助構造」。它不是由 hint 效果決定。因此不應以 `insight = True` 預期「給提示會變好」。
- hint-gap 的結果隨證明器、提示規則與取樣數而變（第 4、5 節）。若要用本資料集評估提示，建議以目標證明器與目標提示規則重新量測，使用足夠的 k 與多個 seed，並事先登記判定規則。
- 本文件的數字不應直接作為其他證明器的提示效果估計。

## 7. 限制

- **單一證明器**：DeepSeek-Prover-V2-7B（transformers backend）。未更換為更強的證明器。
- **單一提示規則**：第一個有型別標註的 `have`。未檢驗完整證明草稿、多個 `have`，或人工撰寫的提示。
- **取樣**：k = 32 只有 seed 0。seed 噪音只在 k=8、無提示的 B0 上量過。
- **題組規模**：比較 38 題，其中有資訊的 18 題。非天花板且有成功次數的題數少，子集間比較的樣本不足。
- **標註**：`insight` 為結構標註，標註流程含 LLM 標註（比例與審核流程待作者補充）。
- **適用範圍**：本結果不推廣到其他證明器、其他提示形式，或 Mathesis 控制層。

## 8. 可重現性

**Run 目錄**（`runs/` 下）

| 用途 | 目錄 |
|---|---|
| hint，k=32，舊 23 題 | `20261104T131752Z_hint-gap-merged`（由 `shards_20261104T080302Z/shard0`–`shard3` 合併） |
| hint，k=32，新 15 題 | `20261106T061711Z_hint-gap-merged`（shard3 於 GPU 3 重跑，見 paper-plan §11.1） |
| hint，k=8，37 題 | `20261104T074803Z_hint-gap-merged` |
| hint，k=8，40 題（judge v1，僅探索性） | `20261103T154014Z_hint-gap` |
| B0，k=8，seed 0 | `20261103T122531Z_b0`、`20261104T141934Z_b0-merged` |
| B0，k=8，seed 1 | `20261104T054619Z_b0-merged`、`20261104T150345Z_b0-merged` |

**判定的可重現性（2026-11-06）**：以 `scripts/replay_verify.py` 在同一台機器（Lean v4.35.0、同一版 Mathlib、judge v2、`unshare -rn` 沙箱）對下列三個 run 全量重新驗證其儲存的回應，樣本的 `passed` 與 `failure_class` 全部與儲存值一致：`20261104T054619Z_b0-merged` 712/712、`20261104T131752Z_hint-gap-merged` 1472/1472、`20261106T061711Z_hint-gap-merged` 960/960，共 3144 個樣本，0 個不一致（`runs/analysis/replay_*.json`）。**範圍限制**：這證明的是「給定儲存的回應，判定可重現」，不是生成本身可重現；生成的可重現性另以 4 張 GPU 重新生成同一種子的回應逐位元相同（16/16）驗證。只在單一機器與單一 Lean／Mathlib 版本上驗證，未跨機器。

**分析檔**（`runs/analysis/`）

- `significance_k32_combined.json`：主要分析，38 題。
- `b0_report_k8_2seeds.json`：B0 兩 seed 的噪音下限。
- `hint_gap_report_20261104T074803Z_hint-gap-merged.json`、`hint_gap_report_20261103T154014Z_hint-gap.json`：k=8 的 gap 數據。

**腳本**（參數以 `--help` 為準）

- `scripts/hint_significance.py <run_dir> [<run_dir> ...] [--out FILE] [--table]`：Fisher 檢定與 Holm 校正。
- `scripts/b0_report.py --seed-runs <seed>:<dir1>,<dir2> [--seed-runs ...] --benchmark <dir> [--out FILE] [--table]`：B0 seed 比較。
- `scripts/merge_shards.py --out <parent> <shard_dir> [...]`：合併 `--shard I/N` 的分片。
- `scripts/run_sharded.py --gpus <i,j,...> [--out <parent>] -- <b0|hint-gap> [args]`：按題目切分到各 GPU，最後合併。

**環境**（manifest 記錄）

- Lean toolchain：`leanprover/lean4:v4.35.0`。
- mathlib rev：`56a005855e0b0958f73ec801ae140b0a1679`。
- Python 3.13.18；platform `Linux-5.15.0-139-generic-x86_64-with-glibc2.31`。
- git commit：`39cbd1c9a55dbafc05b1d624c71af1344516d831`（`git_dirty` 為 true，見第 9 節）。

## 9. 待作者補充與已知問題

1. **沒有預先登記**：規則在大部分資料已見之後才定（見第 1 節），論文中應稱為「事後確定的分析規則」。
2. **未記錄的工作樹狀態**：`20261104T131752Z_hint-gap-merged/manifest.json` 的 `git_dirty` 為 true，但 `git_diff_hash` 為 `e3b0c44298fc`。這是空字串的 SHA-256 前綴，因此未提交的程式狀態沒有被記錄。待作者確認。
3. **B0 的 seed 對應**：`b0_report_k8_2seeds.json` 未記錄 `--seed-runs` 參數。本文件的對應由題數（89 + 20）與題目集合推得，兩 seed 的題目集合相同（109 題）。待作者確認實際指令。
4. **89 題最大值 0.25**：未寫入任何分析檔，為本次重算的結果（第 4 節）。
5. **`lean_real_lucas_five` 的 k=8 → 第一個 `have` 的 gap = 0**：引自 paper-plan §11.1，本次未獨立核對。
6. **`20261103T154014Z` 的限制**：使用 judge v1，且 `lean_ineq_cube_sum_zero_sixth` hint 係數有誤（paper-plan §11.1 記載）。本文只將其作為定性例子。
7. **新 15 題的分片重跑**：paper-plan 記載 shard3 失敗目錄（`shard3_dead_gpu_lost`、`shard3_rerun_failed_nocuda`）與「取樣相同」的主張。本次未核對這些目錄。
8. **`insight` 標註流程**：LLM 參與的程度、審核流程與 `runs/analysis/insight_labels_122531Z.json`、`scripts/audit_insight_labels.py` 的對應，待作者補充。
9. **效力分析**：第 5 節的 power 為單點計算。正式的效力分析（含基線與效應量的範圍）待作者決定是否補上。
10. **`hint_gap_report_*.json` 的產生指令**：本次未核對是哪個腳本與參數產生這兩個檔。

## 附錄 A：逐題結果（k=32，38 題）

來源：`runs/analysis/significance_k32_combined.json` 的 `per_problem`。「—」表示該題不在主要家族（非有資訊題）。分類欄的「有資訊」即屬於主要家族。

| 題名 | plain c/32 | hint c/32 | gap | p | p_holm（主要） | p_holm_all（敏感度） | 分類 |
|---|---|---|---|---|---|---|---|
| lean_algebra_boolean_ring_comm | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
| lean_algebra_r_cube_id_six | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
| lean_algebra_r_sq_hom_comm | 27 | 18 | −0.28125 | 0.027 | 0.435 | 0.979 | hint_hurts / 有資訊 |
| lean_custom_ff_add_two_sum | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
| lean_custom_fib2_bound | 1 | 3 | +0.0625 | 0.613 | 1.0 | 1.0 | no_detectable_effect / 有資訊 |
| lean_custom_r_fibpair_coprime | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
| lean_ineq_cube_sum_zero_sixth | 30 | 31 | +0.03125 | 1.0 | 1.0 | 1.0 | no_detectable_effect / 有資訊 |
| lean_ineq_cyc_sq_over_lin | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
| lean_ineq_inv_add_two | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
| lean_ineq_r_inv_sq_pair | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
| lean_ineq_r_sq_plus_recip | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
| lean_ineq_r_vasc_sos | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
| lean_ineq_ratio_two | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
| lean_ineq_sq_sum_abc_four | 0 | 8 | +0.25 | 0.0048 | 0.081 | 0.176 | hint_helps / 有資訊 |
| lean_ineq_sum_sq_over_sum_cyc | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
| lean_ineq_two_plus_inv_product | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
| lean_ineq_weighted_recip_36 | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
| lean_logic_drinker_implication | 3 | 27 | +0.75 | 1.26e-9 | 2.26e-8 | 4.77e-8 | hint_helps / 有資訊（Holm 通過） |
| lean_logic_no_infinite_descent | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
| lean_logic_r_dependent_choice | 4 | 11 | +0.21875 | 0.075 | 1.0 | 1.0 | no_detectable_effect / 有資訊 |
| lean_logic_serial_transitive_finite_refl | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
| lean_nat_cube_lt_three_pow | 14 | 11 | −0.09375 | 0.609 | 1.0 | 1.0 | no_detectable_effect / 有資訊 |
| lean_nat_dvd_sq_sum_eq | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
| lean_nat_r_mod_seven_pow | 22 | 18 | −0.125 | 0.439 | 1.0 | 1.0 | no_detectable_effect / 有資訊 |
| lean_nat_r_sophie_germain_composite | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
| lean_nat_r_sq_lt_two_pow | 30 | 27 | −0.09375 | 0.426 | 1.0 | 1.0 | no_detectable_effect / 有資訊 |
| lean_nat_sum_even | 5 | 14 | +0.28125 | 0.027 | 0.435 | 0.979 | hint_helps / 有資訊 |
| lean_real_geom_mean_two | 12 | 16 | +0.125 | 0.450 | 1.0 | 1.0 | no_detectable_effect / 有資訊 |
| lean_real_inv_power_five | 28 | 26 | −0.0625 | 0.732 | 1.0 | 1.0 | no_detectable_effect / 有資訊 |
| lean_real_lucas_five | 3 | 1 | −0.0625 | 0.613 | 1.0 | 1.0 | no_detectable_effect / 有資訊 |
| lean_real_nested_sqrt_sum | 3 | 0 | −0.09375 | 0.238 | 1.0 | 1.0 | no_detectable_effect / 有資訊 |
| lean_real_r_diff_prod_fourth | 19 | 19 | 0 | 1.0 | 1.0 | 1.0 | no_detectable_effect / 有資訊 |
| lean_real_r_nested_diff | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
| lean_real_r_qm_sqrt_pair | 17 | 21 | +0.125 | 0.446 | 1.0 | 1.0 | no_detectable_effect / 有資訊 |
| lean_real_r_quad_fun_twenty | 9 | 12 | +0.09375 | 0.595 | 1.0 | 1.0 | no_detectable_effect / 有資訊 |
| lean_real_sqrt_sum_lt_sqrt | 5 | 9 | +0.125 | 0.365 | 1.0 | 1.0 | no_detectable_effect / 有資訊 |
| lean_set_monotone_fixed_point | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
| lean_set_r_image_inter_injective | 0 | 0 | 0 | 1 | — | 1 | no_detectable_effect / 非有資訊 |
