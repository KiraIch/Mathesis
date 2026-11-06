# 資料集 datasheet：`lean_hard`

狀態：草稿（2026-11-06）。版本號、授權與引用格式待作者補充（見第 9 節）。

資料集位置：`benchmark/lean_hard/`（`problems.json`、`lean/`、`hints/`）。

---

## 1. 概述

**用途。** `lean_hard` 用來衡量 LLM 定理證明器在 Lean 4 + Mathlib 上的表現（pass@k），並提供「construction gap」（hint-gap）這個操作化量測的題目與提示檔。

**hint-gap 的定義。** 對題目 p、固定證明器 M、固定預算 B（`docs/paper-plan.md` §3.2）：

```
Gap_B(p) = Pr[solve p | B, 提示版] - Pr[solve p | B, 原版]
```

提示版是在題目前加上參考證明的第一個 `have` 陳述（只給陳述，不給證明）。hint 規則寫在 `benchmark/lean_hard/hints/first_have.json` 的 `rule` 欄位：`first typed have in reference_proof, as '<name> : <statement>'`。

**語言與工具鏈**（來源：`benchmark/lean_hard/lean/` 與 `lean/` 目錄）：

| 項目 | 值 | 來源 |
|---|---|---|
| Lean | `leanprover/lean4:v4.35.0` | `lean/lean-toolchain` |
| Mathlib | `require mathlib from git ... @ "v4.35.0"` | `lean/lakefile.lean` |
| Mathlib rev | `56a005855ea17e0b0958f73ec801ae140b0a1679` | `lean/lake-manifest.json` |
| Lean 檔的 import | 109 個檔案皆為 `import Mathlib`，內容放在 `namespace MathesisHard` | 以 `grep -L "^import Mathlib"` 檢查，無例外 |

專案根目錄沒有 `lean-toolchain` 檔。

**版本說明。** `docs/paper-plan.md` §5.3 寫的候選池是 89 題（工作樹），這是 2026-11-04 汰換之前的數字。本檔的數字以目前的 `problems.json`（109 筆，其中 92 筆啟用、17 筆退役）為準。

---

## 2. 組成

以下數字是以 `python3` 讀取 `benchmark/lean_hard/problems.json` 計算的（本次撰寫時執行，未寫入任何檔案）。「啟用」指沒有 `retired` 欄位的題目。

### 2.1 題數

| 項目 | 題數 |
|---|---|
| 總題數（`problems.json`） | 109 |
| 啟用題數（無 `retired` 欄位） | 92 |
| 已退役題數（有 `retired` 欄位） | 17 |
| insight 題（啟用） | 46 |
| routine 題（啟用） | 46 |
| insight 題（總計，含退役） | 60（其中退役 14） |

退役 17 題中，14 題為 insight（2026-11-04 汰換），3 題為 routine（2026-11-06，近似重複）。

### 2.2 家族（`family`）

| family | 總計 | 啟用 | 退役 |
|---|---|---|---|
| ineq | 27 | 20 | 7 |
| real | 23 | 19 | 4 |
| nat | 26 | 21 | 5 |
| logic | 13 | 12 | 1 |
| custom | 8 | 8 | 0 |
| set | 6 | 6 | 0 |
| algebra | 6 | 6 | 0 |

### 2.3 其他分布（總計 / 啟用）

| 欄位 | 值：題數（總計 / 啟用） |
|---|---|
| `difficulty` | 1：9 / 9；2：37 / 29；3：43 / 37；4：18 / 15；5：2 / 2 |
| `novelty` | novel：83 / 72；perturbed：10 / 5；textbook：16 / 15 |
| `contamination_risk`（作者標註） | low：73 / 62；medium：26 / 21；high：10 / 9 |
| `mathlib_match` | none：69 / 58；variant：37 / 31；exact：3 / 3 |
| `source` | mathlib：98 / 81；core：11 / 11 |
| `bench_split` | dev：109 / 92（全部為 dev） |
| `budget_nodes` | 45：85 / 68；15：24 / 24 |
| `verified` | true：109 / 92 |

`exact` 的三題是 `lean_real_exp_linear`、`lean_set_diff_union`、`lean_set_inter_mono`。

### 2.4 Lean 檔與 hint 檔

| 項目 | 數量 | 來源 |
|---|---|---|
| `benchmark/lean_hard/lean/*.lean` | 109 | 目錄計數；與 `problems.json` 的 `lean_file` 一一對應（已檢查，無缺檔） |
| `hints/first_have.json`（2026-11-04 前） | 37 筆 | `hints` 欄位計數 |
| `hints/first_have_v2.json`（2026-11-04 後） | 46 筆 | `hints` 欄位計數，跳過退役題 |

---

## 3. 欄位說明

`problems.json` 的根結構是 `{"problems": [ ... ]}`。欄位清單與型別檢查由 `src/mathesis/lean_pilot.py` 的 `REQUIRED_FIELDS` 與 `validate_lean_pilot` 執行。本檔所附的 validator 對目前的檔案回傳 `True`（本次撰寫時執行）。

| 欄位 | 型別 | 說明 |
|---|---|---|
| `name` | str | 題目識別碼，前綴 `lean_`；全檔不重複。 |
| `theorem` | str | Lean 定理陳述（`∀ ... , ...` 形式，不含 `:= by`）。全檔不重複。 |
| `family` | str | 家族，見 2.2。 |
| `insight` | bool | 是否為 insight 題。判定依據見第 5.2 節。 |
| `reference_proof` | list[str] | 參考證明的 tactic 行列表。validator 要求不得含 `sorry`；`insight: true` 的題目必須含 `have`。hint 規則取自這個欄位的第一個 `have`。 |
| `auxiliary` | str | 輔助構造的文字說明。`insight: true` 的 60 題全部非空；`insight: false` 的 49 題全部為空字串。`hint-gap` 指令在沒有 `--hints` 時，提示文字取自此欄位（`src/mathesis/llm_baseline.py` 約第 1116 行）；有 `--hints` 時，提示文字取自 hint 檔（`src/mathesis/cli.py` 的 `hint_gap_targets`）。hint 檔的內容由 `reference_proof` 的第一個 `have` 產生（`scripts/extract_hints.py`）。 |
| `budget_nodes` | int | 搜尋預算（節點數）。`src/mathesis/lean_bench.py` 使用它；B0 的 loader 不讀取。 |
| `lean_file` | str | 相對於 `benchmark/lean_hard/` 的 Lean 檔路徑，例如 `lean/ineq_amgm3.lean`。 |
| `source` | str | `core` 或 `mathlib`。validator 只檢查這兩個值；語意未在文件中說明（見第 9 節）。 |
| `verified` | bool | 驗證旗標。validator 只檢查型別；編譯結果的記錄見第 4 節。 |
| `difficulty` | int 1–5 | 難度標註（作者標註或 LLM 輔助標註，來源見第 4 節）。 |
| `novelty` | str | `textbook`、`perturbed` 或 `novel`。 |
| `contamination_risk` | str | `low`、`medium` 或 `high`。作者標註，見第 5.3 節。 |
| `mathlib_match` | str | `none`、`variant` 或 `exact`，表示與 Mathlib 現有陳述的相似度。 |
| `audit_notes` | str | 審查註記。2026-11-04 的審查結果以 `[2026-11-04 audit]` 標記。 |
| `bench_split` | str | 目前全部為 `dev`。 |
| `retired` | str（選填） | 退役說明。存在此欄位即為退役；B0 仍會跑這些題，hint-gap 與 hint 檔會跳過它們（見第 5.1 節）。 |

### 3.1 範例條目

以下是檔案中的第一筆條目（`lean_ineq_amgm3`），原文照錄。這題是退役題，所以可以同時示範 `retired` 欄位。

```json
{
 "name": "lean_ineq_amgm3",
 "theorem": "∀ a b c : ℝ, 0 ≤ a → 0 ≤ b → 0 ≤ c → 27 * (a * b * c) ≤ (a + b + c) ^ 3",
 "family": "ineq",
 "insight": true,
 "reference_proof": [
  "intro a b c ha hb hc",
  "have h1 : 0 ≤ (a + b + c) * ((a - b) ^ 2 + (b - c) ^ 2 + (c - a) ^ 2) := mul_nonneg (by linarith) (by positivity)",
  "nlinarith [h1, mul_nonneg ha (sq_nonneg (b - c)), mul_nonneg hb (sq_nonneg (c - a)), mul_nonneg hc (sq_nonneg (a - b))]"
 ],
 "budget_nodes": 45,
 "lean_file": "lean/ineq_amgm3.lean",
 "source": "mathlib",
 "verified": true,
 "auxiliary": "(a+b+c)(sum of squared differences) and a(b-c)^2 cross terms",
 "difficulty": 4,
 "novelty": "novel",
 "contamination_risk": "low",
 "mathlib_match": "none",
 "audit_notes": "three-variable AM-GM in cubic form; no direct Mathlib statement in this shape",
 "bench_split": "dev",
 "retired": "2026-11-04: plain ceiling, 16/16 over B0 seeds 0 and 1 (20261103T122531Z_b0, 20261104T054619Z_b0-merged); kept for B0 comparability, excluded from hint-gap targets"
}
```

對應的 Lean 檔 `benchmark/lean_hard/lean/ineq_amgm3.lean` 內容為 `import Mathlib`、`namespace MathesisHard`、定理陳述與 `:= by` 後的證明，最後 `end MathesisHard`。

---

## 4. 建構流程

來源：`docs/paper-plan.md` §5.3（建構流程）與 §11（狀態與 2026-11-04 汰換）。下列每一段都標明來源章節；文件中沒有寫到的事項不在此推定。

**4.1 候選池（§5.3 第 1 點）。** 候選池包括新題組 `lean_hard`、擾動題與新造題，以及 miniF2F 子集。miniF2F 在文件中標為「尚未下載」（§5.3 附註）。文件沒有說明 `lean_hard` 是否包含 miniF2F 來源的題目（見第 9 節）。

**4.2 Lean 驗證（§5.3 第 1 點、§11 第 8 項）。** §5.3 寫明題目「已 Lean 驗證」。§11 第 8 項記錄 38 題版的 `lean_hard` 「全部 Lean 驗證通過」，commit `b582c58`。本次撰寫時的檢查：

- `benchmark/lean_hard/lean/*.lean` 中以 `grep` 搜尋 `sorry`、`admit`、`axiom`，沒有任何檔案命中。
- `validate_lean_pilot` 檢查 `reference_proof` 不含 `sorry`，且 `insight` 題含 `have`。

本次**沒有重新編譯**任何 Lean 檔。「每題能通過編譯」這個敘述的依據是 §11 第 8 項的歷史記錄，不是本次重跑的結果。

**4.3 禁用 token 規則。** B0 的判定規則把 `sorry`、`admit`、`axiom` 視為禁用 token，證明文字與 Lean 輸出都要檢查（`src/mathesis/llm_baseline.py` 模組說明）。這是判定候選證明的規則，不是題庫建構時的檢查；題庫本身的檢查只有第 4.2 節的兩項。

**4.4 insight 與 routine 標註（§5.3 第 6 點；2026-11-06 作者決定）。** `insight` 是結構標註：表示該題的解法需要非顯然的輔助構造。標註內容依 §5.3 第 6 點包括「是否需要非平凡輔助構造、難度 1–5、與 Mathlib 的相似度」，標註者為 LLM，並由作者盲標 20 題核對（盲標結果未在本 checkout 中，見第 9 節）。hint-gap 的 Gap 不用來定義 insight。詳見第 5.2 節。

**4.5 2026-11-04 audit（§5.3 第 1 點、`audit_notes`）。** §5.3 記錄：2026-11-04 的陳述審查發現 1 組代數等價重複與 2 題近似重複，已在 `audit_notes` 註記，「凍結題庫時移除」。目前 `audit_notes` 含 `[2026-11-04 audit]` 標記的條目共 11 筆。其中一筆是係數修正：`lean_ineq_cube_sum_zero_sixth` 的 auxiliary 係數由 4 改為 2（`audit_notes` 原文：「runs before this date used the wrong coefficient in the hint」）。

**4.6 2026-11-04 汰換（§11.1 表格中的 `20261104T141934Z` 與 `20261104T150345Z` 兩列）。**

- 14 題 insight 題在 `122531Z` 與 `054619Z` 兩個 seed 的 B0 中共 16/16 全對，標記 `retired`，保留在 `problems.json` 以便 B0 可比，不再作為 hint-gap 目標。
- 新增 20 題 insight 題。啟用題數變為 95。
- 新題的 B0 篩選（k=8，各 seed 8 次，合計 16 次）：pass@1 seed 0 為 0.444、seed 1 為 0.400；pass@8 為 0.550 / 0.600。16 次中，16/16 的題 5 題、中段 7 題、0/16 的題 8 題。
- hint 檔改用 `hints/first_have_v2.json`，跳過退役題。

**4.7 hint-gap 量測（§11 表格各列）。** 量測的 run 與分析結果列在 §11.1。本資料集不含 run 的原始輸出（見第 9 節）。

**4.8 2026-11-06 標記退役（作者決定）。** 2026-11-04 的 audit 找出 1 組代數等價重複與 2 題近似重複（見 4.5）。作者決定將其中 3 題標記為 `retired`，檔案保留：`lean_ineq_three_pairs_mean`、`lean_nat_shifted_odd_sum`、`lean_real_sqrt_le_avg_one`。三題皆為 routine（`insight: false`）。啟用題數由 95 變為 92。

---

## 5. 資料狀態與已知問題

### 5.1 退役題為何保留

退役的 17 題中，14 題是 B0 的天花板題（16/16，2026-11-04），3 題是近似重複題（2026-11-06，見 4.8）。全部保留在 `problems.json` 中，以便 B0 在新舊版本之間比較。

- B0 的 loader（`load_b0_problems`）**不會跳過**退役題；`mathesis b0` 會跑全部 109 筆（若沒有用 `--problems` 限制）。
- hint-gap 的目標（`llm_baseline.py` 約第 1074 行）與 hint 檔產生（`scripts/extract_hints.py`）會**跳過**退役題。

因此使用者要留意：B0 的 pass@k 若沒有指定題目，會包含退役題，與只看 92 題的數字不同。

### 5.2 insight 標籤的依據

**決定（2026-11-06，作者）：`insight` 是結構標註，不是 hint-gap 實測的結果。** `insight` 表示該題解法需要非顯然的輔助構造，由作者與 LLM 標註；hint-gap 的 Gap 是獨立量測，不用來定義 insight。以下是此決定下可檢查的結構對應，以及 hint-gap 實測的結果：

1. 結構上的對應已檢查：`insight: true` 的 60 題全部 `auxiliary` 非空且 `reference_proof` 含 `have`；`insight: false` 的 49 題 `auxiliary` 全部為空。（3 題 routine 的 `reference_proof` 文字中含字串 `have`，本次未逐一確認是否為 tactic。）
2. hint-gap 實測的結果不支持以它來解釋標籤。k=32 的合併分析（38 題，`runs/analysis/significance_k32_combined.json`）：
   - 可分析題（informative）18 題；
   - 未校正 p<0.05、hint 有效：3 題；
   - Holm 校正後通過：1 題（`lean_logic_drinker_implication`）；
   - hint 有害（未校正 p<0.05）：1 題（`lean_algebra_r_sq_hom_comm`）。

因此 insight 標籤與 hint 的效果**沒有可偵測的關聯**，不得宣稱兩者相關。

標註輸出：LLM 標註的原始輸出目錄 `benchmark/annotations/` 在目前的 checkout 中**不存在**（已檢查）。標註 prompt、回應與作者盲標的存放位置待作者補充（見第 9 節）。

### 5.3 污染風險

**審計方法**（`scripts/contamination_audit.py`，模組說明與 `--help`）。在 `lean/.lake/packages/mathlib/Mathlib` 下的 `.lean` 檔做子字串搜尋，比對兩件事：

- 定理名稱的 stem（去掉 `lean_` 前綴與家族前綴後的部分）；
- 摺疊空白後的陳述主體（`theorem` 中最後一個 `),` 之後的部分）。

主體短於 15 個字元的命中判為 generic，不算記憶證據。腳本自己的說明寫明：這是啟發式篩檢，不是污染的證明；沒有命中不代表題目未曾出現在訓練資料中。

**結果。** 最新的審計輸出是 `runs/contamination/20261106T062924Z.json`（2026-11-06，method 為啟發式篩選）：

- 掃描 8,624 個 Mathlib `.lean` 檔；檢查全部 109 題；
- 新增的 20 題：名稱命中 0 題、內文命中 0 題；
- 全部 109 題：名稱 stem 命中 10 題、內文非 generic 命中 0 題。

名稱命中的 10 題與先前 `runs/contamination/20261103T121925Z.json`（89 題）的命中題目相同（已比對）；先前已確認這 10 題全部屬於原始 38 題版本（與 `git show b582c58` 的 `problems.json` 比對）。

這是啟發式篩選，**不是污染的證明**；沒有命中不代表題目未曾出現在訓練資料中。

`contamination_risk` 欄位是作者標註；§5.3 寫「我自己標的 contamination 等級比篩檢更保守」。

### 5.4 與 Mathlib 相似的題目

`mathlib_match` 為 `variant` 的 31 題與 `exact` 的 3 題（啟用題）應由使用者自行過濾，特別是 `exact` 的三題。`audit_notes` 另外記錄了下列近似或重複題（均已於 2026-11-06 標記退役，檔案保留）：

| 題目 | `audit_notes` 的記載（節錄） |
|---|---|
| `lean_ineq_three_pairs_mean` | 與 `lean_ineq_pairwise_sum_le` 代數等價；註記寫「duplicate, exclude in sensitivity analysis and drop at benchmark freeze」。2026-11-06 已標記退役，檔案保留。 |
| `lean_nat_shifted_odd_sum` | `lean_nat_odd_sum` 的 index shift，「near-duplicate」。2026-11-06 已標記退役，檔案保留。 |
| `lean_real_sqrt_le_avg_one` | `lean_real_geom_mean_two` 的特例（b=1），「near-duplicate」。2026-11-06 已標記退役，檔案保留。 |

§5.3 寫「凍結題庫時移除」；作者於 2026-11-06 決定改為標記退役（`retired` 欄位），檔案保留。

### 5.5 其他已知限制

- **split。** 全部 109 題的 `bench_split` 都是 `dev`。§5.3 第 5 點計畫的 calibration / dev / test 切分沒有在檔案中實作。
- **`lean_ineq_cube_sum_zero_sixth` 的 hint。** 2026-11-04 之前的 hint-gap run 使用了錯誤係數（見第 4.5 節）。
- **`mathesis b0 --controls`。** `src/mathesis/llm_baseline.py` 的 `CONTROL_PROBLEMS` 是 `lean_nat_add_comm`、`lean_sq_nonneg`、`lean_poly_lower`，這三題都不在 `lean_hard` 中（已檢查）。依程式碼判斷，`--controls` 搭配 `--benchmark benchmark/lean_hard` 會失敗；本次**未實際執行**這個指令。
- **判定版本。** 2026-11-04 的 commit `246539e` 把判定改為 judge v2（見 §11 第 16 項）。`20261103T122531Z_b0` 的 seed 0 結果原為 v1；該 commit 的訊息記載「Re-verification of 20261103T122531Z under v2: 525/525 passes unchanged」。§11.1 未逐行註明 seed 0 的判定版本。
- **v1 與 v2 不可混用。** §11 第 16 項：v1 判定的既有 run，其 forbidden 判定不得以 v2 重新解讀。

---

## 6. 建議用法與不建議的用法

### 6.1 建議用法

**跑 B0（`mathesis b0`）。** 這個專案沒有安裝 console script（`pyproject.toml` 未定義 `[project.scripts]`），所以以模組方式執行，與 `Makefile` 的慣例一致。`b0` 的 `--benchmark` 預設是 `benchmark/lean_pilot`，**跑 `lean_hard` 時必須指定**：

```bash
PYTHONPATH=src python3 -m mathesis.cli b0 --benchmark benchmark/lean_hard --k 8 --seed 0 --out runs
```

參數預設值（`python3 -m mathesis.cli b0 --help`，以及 `src/mathesis/llm_baseline.py`）：

- `--k` 預設 8（`DEFAULT_K`）；
- `--backend` 預設 `transformers`；模型 `deepseek-ai/DeepSeek-Prover-V2-7B`（`TRANSFORMERS_MODEL_NAME`）；
- `--verify-workers` 預設 12；
- `--problems` 可以限制題目（逗號分隔，例如只跑 `--problems` 指定的 20 題）。

其餘參數見 `--help`。

**judge v2 與沙箱。** judge 版本由常數 `JUDGE_VERSION = "v2"` 決定，不需另外設定。Lean 子行程的網路隔離由環境變數 `MATHESIS_LEAN_SANDBOX` 控制，預設 `auto`（用 `unshare -rn`，不可用時不隔離）；`off` 可關閉（見 §11 第 16 項）。`runs/20261104T054619Z_b0-merged/summary.json` 中的 `lean_preflight.sandbox.mode` 為 `unshare-net`。

**hint-gap。** 指令為 `PYTHONPATH=src python3 -m mathesis.cli hint-gap`，參數包括 `--benchmark`、`--hints`（指向 `benchmark/lean_hard/hints/first_have_v2.json` 之類的 hint 檔）、`--problems`、`--k`。詳見 `--help`。

**顯著性分析。** `scripts/hint_significance.py` 接收一個或多個 hint-gap-merged run 目錄（`--help`）。

**污染審計。** `scripts/contamination_audit.py --benchmark benchmark/lean_hard --out <path>`。預設的 benchmark 同樣是 `lean_pilot`，要指定。

**judge v2 的重新驗證。** 可以用已存的候選檔重新判定；見 `git log` 中 `246539e` 的訊息。本次未執行。

### 6.2 不建議的用法

- **不要用 pass@1 在這個資料集上宣稱超越 SOTA。** 啟用題數 92 題，題組規模小，且 `dev` 是唯一切分（見第 5.5 節）。`docs/paper-plan.md` §2.1 寫明不能正面與 SOTA 比較解題率。
- **不要把 hint-gap 的結果解讀為「構造性提示無效」或「有效」的一般結論。** 文件的說法是：在此證明器、此 hint 規則（第一個 `have`）、此題組下沒有可偵測的穩定效果（`docs/paper-plan.md` §11）。`lean_real_lucas_five` 在 k=8 的 +0.875 會隨 hint 選法變成 0，所以 Gap 對 hint 選擇敏感。
- **不要用單一 seed 的差異判斷題目難度變化。** `054619Z` 與 `122531Z` 的逐題 |Δpass@1| 中位數為 0、p90 為 0.125、最大 0.25（`docs/paper-plan.md` §11.1）。
- **不要把退役題當作新題的對照，也不要用它們做 hint-gap 目標。**
- **不要在沒有重新驗證的情況下混用 v1 與 v2 的判定結果。**

---

## 7. 評測結果摘要

模型為 DeepSeek-Prover-V2-7B；k=8；資料為 `lean_hard` 的 89 題版本（即 2026-11-04 汰換前的題組，包含目前標記為退役的 17 題）。數字來自各 run 的 `summary.json`，本次確認與 `docs/paper-plan.md` §11.1 一致。

| run | seed | pass@1 | pass@8 | 判定 | 備註 |
|---|---|---|---|---|---|
| `runs/20261103T122531Z_b0` | 0 | 0.737 | 0.820 | seed 0 | 分析以此 run 為準（§11.1）。判定版本見第 5.5 節。 |
| `runs/20261104T054619Z_b0-merged` | 1 | 0.730 | 0.820 | judge v2 + 沙箱 | 4 GPU 分片後合併；`summary.json` 的 `failure_class_counts.forbidden_token` 為 4。 |

兩次 run 的 pass@1 差異為 0.007；§11.1 記錄逐題比較的噪音下限：89 題中 74 題 |Δ| 為 0、11 題為 0.125、4 題為 0.25。

**注意。** 這兩次 run 使用的是 89 題，不是目前的 92 題啟用題組。§11 第 10 項另有一次 38 題版的 MLX 4bit run（pass@1 0.819、pass@8 0.895），run 目錄不在本 checkout 中，本節未納入。

**新題 B0 篩選**（§11.1，20 題，k=8）：pass@1 0.444（seed 0）與 0.400（seed 1）；pass@8 0.550 與 0.600。

---

## 8. 授權與引用

- **授權：CC BY 4.0（作者決定，2026-11-06）。** 完整聲明見 `benchmark/lean_hard/LICENSE.md`。資料集（`problems.json`、`hints/`、本說明文件）與 `lean/` 下的題目證明檔採 CC BY 4.0。依賴的 Mathlib 等第三方套件維持各自授權（Mathlib 為 Apache-2.0，已檢查其 `lean/.lake/packages/mathlib/LICENSE`），不在此授權範圍。著作權人與年份待作者補充。文件中關於權重授權的說明（`docs/paper-plan.md` §11 已知問題）針對模型權重，與資料集授權無關。
- **引用格式：待作者補充。**
- **作者（文件記載）。** `ChiaAn Lin`（`docs/paper-plan.md` 首段，「作者資訊（2026-11-03 提供）」）。所屬單位待確認（`docs/paper-plan.md` §10 第 4 項）。

---

## 9. 待作者補充

下列事項在文件或程式碼中找不到，或文件內容不一致，本檔不做推測：

1. **著作權人與年份**：已填，ChiaAn Lin，2026，單位 Master Program for Health and Intelligent Medicine（2026-11-06 作者提供；`benchmark/lean_hard/LICENSE.md`）。DOI：目前有 Zenodo 軟體釋出 10.5281/zenodo.24001509（2026-11-06 快照，creator 為 KiraIch；concept DOI 10.5281/zenodo.24001508）；定稿時應建立新版本取得新 DOI。
2. **引用格式**與 DOI；是否有預印本或版本 DOI。
3. **版本號**（資料集本身的版本，與 Lean 或 Mathlib 版本無關）。
4. **聯絡方式**。
5. **作者所屬單位**（`docs/paper-plan.md` §10 第 4 項，尚未決定）。
6. **LLM 標註的輸出與作者盲標**：`benchmark/annotations/` 目錄在 checkout 中不存在；標註的 prompt、回應、三次一致率，以及作者盲標 20 題與 Cohen κ 的資料位置未知。
7. **`source` 欄位的語意**（`core` 與 `mathlib` 各指什麼）。
8. **`lean_hard` 是否包含 miniF2F 題目**。§5.3 的候選池有 miniF2F，但檔案中沒有標示來源。
9. **hint-gap 的原始 run 目錄**（`runs/20261104T074803Z_hint-gap-merged` 等）：本 checkout 中存在分析檔，但要確認哪些 run 目錄需要隨資料集釋出。
10. **§11 第 4 項的「新題組 38/38 已檢查」**：對應的輸出檔在 `runs/contamination/` 中找不到。2026-11-06 的全 109 題審計已存在（見第 5.3 節）。
11. **split**：calibration / dev / test 的切分是否要在釋出前實作（§5.3 第 5 點）。
12. **`verified` 的編譯記錄**：目前只有 §11 第 8 項的歷史敘述；是否要附上一次完整的 Lean 編譯 log。
13. **`mathesis b0 --controls` 與 `lean_hard`** 不相容（見第 5.5 節），是否要修或在文件中保留限制。
14. **`docs/paper-plan.md` §11 的 2026-11-06 判定段**仍寫「維持以 Gap 定義 insight」，與 2026-11-06 的結構標註決定相反。本次依指示未改該段（歷史決定紀錄），需作者確認是否要加註或改寫。

---

## 附錄：本檔的計算與來源

- 題數、分布：以 `python3` 讀取 `benchmark/lean_hard/problems.json` 計算（第 2 節）。
- validator：`src/mathesis/lean_pilot.py` 的 `validate_lean_pilot(P, base_dir="benchmark/lean_hard")` 回傳 `True`。
- sorry 檢查：`grep -ln "sorry\|admit\|axiom" benchmark/lean_hard/lean/*.lean`，無命中。
- k=32 分析：`runs/analysis/significance_k32_combined.json` 的 `n_problems`、`n_informative`、`n_hint_helps`、`n_hint_helps_holm`、`n_hint_hurts`、`n_passing_holm`。
- 污染審計（109 題）：`runs/contamination/20261106T062924Z.json`。
- B0 數字：各 run 的 `summary.json` 的 `pass_at_1`、`pass_at_k`。
- 汰換與 B0 篩選數字：`docs/paper-plan.md` §11 與 §11.1。
