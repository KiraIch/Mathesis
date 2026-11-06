# 小型 Lean 4 形式證明基準的評測可靠性：以提示差距為案例的負面結果

> **狀態**：初稿（2026-11-06）。結構依 Datasets and Benchmarks 論文的常見寫法，尚未定稿。
>
> **標記**：`[待作者補充：…]` 表示材料中沒有、需作者提供；`[待補引用：…]` 表示需要引用，但閱讀筆記中沒有對應文獻。
>
> **來源縮寫**（各節末與括號內使用）：`datasheet` = `docs/datasheet-lean_hard.md`；`neg` = `docs/paper-negative-results.md`；`plan` = `docs/paper-plan.md`；`notes-A`、`notes-B` = `docs/related-work-notes-A.md`、`docs/related-work-notes-B.md`；`b0-json` = `runs/analysis/b0_report_k8_2seeds.json`；`sig-json` = `runs/analysis/significance_k32_combined.json`。

## 摘要

本文以 Lean 4 形式證明基準 `lean_hard`（啟用 92 題，另有 17 題已退役並保留在檔案中；datasheet §2.1）與 DeepSeek-Prover-V2-7B 為測試床，討論小型基準上的成功率差距有多可靠。核心主張是：在本文的設定下，單一 seed、k=8 的成功率差距不足以作為結論，需要量測 seed 噪音、逐題檢定與可重驗的判定。

具體結果如下。(1) seed 噪音：兩個 seed 的 B0 逐題 |Δpass@1|，原 89 題最大為 0.25，含新增題的啟用 92 題最大為 0.625（`lean_nat_r_mod_seven_pow`，7/8 對 2/8；b0-json `noise_floor`；neg §4）。(2) 提示差距（hint-gap，定義見 datasheet §1）：`lean_real_geom_mean_two` 在 k=8 時 gap 為 +0.625，k=32 時為 +0.125（p = 0.450；neg §4）（此題是 k=8 結果中 gap 第二大的題，縮小含向平均值回歸的成分，見第 1 節）。在 38 題、k=32 的量測中，有資訊（非天花板，且兩條件合計至少 1 次成功）的題為 18 題；未校正 p<0.05 的「hint 有效」有 3 題，經 Holm 校正後只有 `lean_logic_drinker_implication` 1 題通過（sig-json `summary`；neg §3）。(3) 判定可重現：三個 run 共 3144 個樣本全部與儲存值一致，0 個不一致（plan §11.1）。

這些結果只適用於本文的設定：單一 7B 證明器、單一提示規則（「第一個 `have`」，事後確定、非預先登記；neg §1）、k=32 的單一 seed。判定可重現不等於生成可重現。本文不主張提示在一般情況下有效或無效。

## 1 引言

本文的動機來自自己的量測，而非既有文獻的論斷。在無提示、k=8 的設定下，同一證明器（DeepSeek-Prover-V2-7B）的兩個 seed 之間，逐題 pass@1 差距在原 89 題中最大為 0.25，在含新增題的啟用 92 題中最大為 0.625（`lean_nat_r_mod_seven_pow`，seed 0 為 7/8，seed 1 為 2/8；b0-json `noise_floor`；neg §4）。在這組數據下，單一 seed 的逐題比較無法把抽樣噪音與真實差異分開。

本文以「提示差距」（hint-gap）作為案例檢驗此問題。提示差距是提示版的成功率減去原版的成功率；提示版在題目前加入參考證明的第一個 `have` 陳述，只給陳述、不給證明（datasheet §1）。在 k=8 時，`lean_real_geom_mean_two` 的 gap 為 +0.625；改為 k=32 後為 +0.125（p = 0.450；neg §4）。需注意此題是 k=8 結果中 gap 第二大的題（`074803Z` 的 37 題中，gap ≥ 0.375 的只有 `lean_logic_drinker_implication` +0.875、本題 +0.625、`lean_nat_sum_even` +0.375；plan §11.1），事後挑選最大者本來就會因向平均值回歸而在更大樣本時縮小，因此這個縮小只能部分歸因於抽樣噪音，不能當作噪音大小的量測；噪音大小以上述 B0 兩個 seed 的逐題差距為準。在 38 題、k=32 的量測中，經 Holm 校正後只有 1 題通過（sig-json `summary`；neg §3）。判定以 Lean 4 與 Mathlib 進行。[待補引用：Lean 4 與 Mathlib 的標準引用]

關於既有論文如何報告成功率，我們只檢查了第 2 節引用的 9 篇（`docs/related-work-notes-C.md`，以關鍵字搜尋全文，結果不外推到其他文獻）。其中 3 篇報告了某種形式的變異：ProofEvolve [Ye 等 2026, arXiv:2608.26334] 報告三次獨立執行的平均並附誤差線；NanoProof [Kripner 與 Straka 2026, arXiv:2610.11605] 報告三次獨立的 RL 訓練並附 min/max 範圍；DeepSeek-Prover-V2 [Ren 等 2025, arXiv:2504.21801] 在表中以 μ ± σ 報告平均與標準差，但全文搜尋未見其執行次數。另 6 篇（HAGeo、AMBER、DeepInsight、DSP、LEGO-Prover、Goedel-Prover-V2）在全文以關鍵字搜尋沒有找到獨立執行、標準差定義、信賴區間或誤差線的敘述；Goedel-Prover-V2 的表中有 ± 但文中未定義。這是關鍵字搜尋的結果，不表示這些論文沒有做。此外，上述報告的變異是整體流程或訓練的變異，本文所量的是同一證明器、同一題目在不同 seed 下的逐題差距，兩者不同，我們沒有檢查這 9 篇是否也量過後者。

`[待作者補充：本文動機是否還需要說明既有基準的不足；以上查核只支持「9 篇中有 6 篇在全文搜尋中未見變異的報告」，不支持「既有論文普遍不報告變異」]`

本文的貢獻如下。

1. **評測協議**：seed 噪音的量測（B0 兩個 seed 的逐題比較）、逐題 Fisher 精確檢定加 Holm 校正、可重驗的判定，以及判定所用的 Lean 子行程沙箱（見第 4 節；datasheet §3–§5；neg §1–§2）。判定重驗涵蓋三個 run 共 3144 個樣本，全部與儲存值一致（plan §11.1）。
2. **測試床資料集 `lean_hard`**：啟用 92 題、17 題退役，附建構與審計紀錄（datasheet §2.1、§3）。
3. **案例研究**：hint-gap 在此設定下不穩定的負面結果，包括 k=8 與 k=32 的對照、逐題檢定與多重校正，以及對 hint 選擇與子集組成的敏感度（見第 6 節；neg §3–§4）。

本文的結論只限於：單一 7B 證明器（DeepSeek-Prover-V2-7B）、單一提示規則（「第一個 `have`」）、k=32 的單一 seed。判定重驗在同一台機器、同一版 Lean v4.35.0 與 Mathlib 上進行（plan §11.1）；判定可重現只表示給定已儲存的回應時，判定逐樣本一致，本文不證明生成可重現（plan §11.1）。

本文不比較各證明器的解題率，也不主張提示在一般情況下有效或無效（datasheet §6.2；neg §5）。本文也不包含控制層系統的評測；該部分在原計畫中未實作、未檢驗（plan §11）。

<!-- 來源: docs/paper-negative-results.md, docs/datasheet-lean_hard.md, docs/paper-plan.md, runs/analysis/b0_report_k8_2seeds.json, runs/analysis/significance_k32_combined.json -->

## 2 相關工作

**證明器與子目標分解。** DeepSeek-Prover-V2 [Ren 等 2025, arXiv:2504.21801] 先由 DeepSeek-V3 將題目分解為子目標，再以證明器解子目標（notes-B §1）。DSP [Jiang 等 2022, arXiv:2210.12283] 將非形式證明映射為形式 sketch，並由自動證明器填補其中的子猜想（notes-B §2）。LEGO-Prover [Wang 等 2023, arXiv:2310.00656] 在證明前先將問題分解為子目標 lemma，並使用不斷增長的 lemma 庫（notes-B §3）。Goedel-Prover-V2 [Lin 等 2025, arXiv:2508.03613] 的主流程是依 Lean 編譯器回饋修正證明，子問題只在失敗之後才出現（notes-B §4）。notes-B 已讀的段落中，四篇都沒有比較「何時分解」的消融。

**輔助構造與引理庫。** HAGeo [Duan 等 2025, arXiv:2512.00097] 在初始 DDAR 失敗後才加入輔助構造，IMO-30 上 DDAR 為 15 題、HAGeo 為 28 題（notes-A §2，表 2）。它與本文的 hint-gap 概念最接近，但它處理歐氏幾何、不使用神經網路推論，也不在 Lean 中，數字不可直接比較（notes-A §2 Q6）。ProofEvolve [Ye 等 2026, arXiv:2608.26334] 的對照是引理庫：在合成的組合式引理族上，庫跨題累積時為 19.8%，每題前重設時為 7.3%（notes-A §1 Q3）。這是「可用引理」的對照，不是提示的對照，兩者不應相提並論。

**Lean 4 基準與提示形式。** AMBER（Construction–Verification）[Yang 等 2026, arXiv:2602.01291] 比較 construction-verification 提示與標準程式補全等提示形式，作者報告通用推理模型的表現優於專用證明器（notes-A §3）。NanoProof [Kripner 與 Straka 2026, arXiv:2610.11605] 強調訓練資料、工具與權重皆釋出，但文中未量測提示差距（notes-A §4）。DeepInsight [Li 等 2026, arXiv:2604.16278] 處理非形式證明中核心技巧的訓練，論文未量測推論時給予提示的成功率差距；其 insight 是訓練目標，與本文 `insight` 欄位的結構標註不同（notes-A §5）。

**版本差異。** 引用各論文的數字時需注意版本。DeepSeek-Prover-V2 的 PutnamBench 解題數，API 摘要為 49、下載的 PDF 摘要為 47；PDF 正文說明 49 為初始結果，排除兩題後為 47（notes-B §8）。LEGO-Prover 的 miniF2F-test 數字，API 摘要為 47.1%、PDF 摘要為 50.0%（notes-B §8）。本文引用這些數字只為描述，不作排名。

<!-- 來源: docs/related-work-notes-A.md, docs/related-work-notes-B.md -->

## 3 資料集 `lean_hard`

### 3.1 組成

`lean_hard` 共 109 筆條目，其中啟用 92 筆、退役 17 筆（datasheet §2.1）。啟用題中，insight 題 46 筆、routine 題 46 筆（datasheet §2.1）。各家族的數量如下。

| family | 總計 | 啟用 | 退役 |
|---|---|---|---|
| ineq | 27 | 20 | 7 |
| real | 23 | 19 | 4 |
| nat | 26 | 21 | 5 |
| logic | 13 | 12 | 1 |
| custom | 8 | 8 | 0 |
| set | 6 | 6 | 0 |
| algebra | 6 | 6 | 0 |

（datasheet §2.2）

啟用題中，`mathlib_match` 為 `variant` 的有 31 題、為 `exact` 的有 3 題，`exact` 三題為 `lean_real_exp_linear`、`lean_set_diff_union`、`lean_set_inter_mono`（datasheet §2.3、§5.4）。使用者應依研究目的自行過濾。`contamination_risk` 由作者標註，啟用題中 low 62 題、medium 21 題、high 9 題（datasheet §2.3）。

每個 `.lean` 檔的 import 皆為 `import Mathlib`，內容位於 `namespace MathesisHard`（datasheet §1、§2.4）。工具鏈為 `leanprover/lean4:v4.35.0`，Mathlib 版本為 `56a005855ea17e0b0958f73ec801ae140b0a1679`（datasheet §1，來源 `lean/lake-manifest.json`）。

### 3.2 建構與審計

**候選池。** 候選池包括新題組、擾動題與新造題，以及 miniF2F 子集；miniF2F 在建構時尚未下載（datasheet §4.1）。`lean_hard` 是否包含 miniF2F 來源的題目，文件沒有說明（datasheet §9 第 8 項）。

**形式檢查。** 所有 `lean/*.lean` 以 `grep` 搜尋 `sorry`、`admit`、`axiom`，無命中。`validate_lean_pilot` 檢查 `reference_proof` 不含 `sorry`，且 `insight: true` 的題目含 `have`（datasheet §4.2）。**本次撰寫時沒有重新編譯任何 Lean 檔。** 「每題通過編譯」的依據是 38 題版本的歷史記錄（plan §11 第 8 項，commit `b582c58`；datasheet §4.2）。`[待作者補充：是否附上一次完整的 Lean 編譯 log（datasheet §9 第 12 項）]`

**標籤。** `insight` 是結構標註，表示該題的解法是否需要非顯然的輔助構造。標註者為 LLM，並由作者盲標 20 題核對；盲標結果與標註輸出目錄 `benchmark/annotations/` 在本 checkout 中不存在（datasheet §4.4、§5.2、§9 第 6 項）。2026-11-06 的作者決定是：`insight` 不由 hint-gap 的 Gap 定義（datasheet §5.2）。`contamination_risk` 與 `mathlib_match` 為作者標註（datasheet §3）。

**2026-11-04 審計與汰換。** 審計發現 1 組代數等價重複與 2 題近似重複，有 11 筆條目帶 `[2026-11-04 audit]` 標記（datasheet §4.5）。其中 `lean_ineq_cube_sum_zero_sixth` 的 hint 係數由 4 修正為 2（datasheet §4.5）。同日，14 題 insight 題在兩個 B0 seed 中共 16/16 全對，被標為退役；另新增 20 題 insight 題（datasheet §4.6；plan §11.1）。

**2026-11-06 退役。** 作者將 3 題近似重複標為退役：`lean_ineq_three_pairs_mean`、`lean_nat_shifted_odd_sum`、`lean_real_sqrt_le_avg_one`，三題皆為 routine（datasheet §4.8）。

### 3.3 欄位

`problems.json` 的根結構為 `{"problems": [...]}`。主要欄位如下（datasheet §3）。

| 欄位 | 型別 | 說明 |
|---|---|---|
| `name` | str | 題目識別碼，前綴 `lean_`，全檔不重複 |
| `theorem` | str | Lean 定理陳述，不含 `:= by` |
| `family` | str | 家族 |
| `insight` | bool | 結構標註（見 3.2） |
| `reference_proof` | list[str] | 參考證明的 tactic 行列表 |
| `auxiliary` | str | 輔助構造的文字說明；`insight: true` 的 60 題皆非空，`insight: false` 的 49 題皆為空字串（datasheet §3） |
| `budget_nodes` | int | 搜尋預算（節點數）；B0 的 loader 不讀取（datasheet §3） |
| `lean_file` | str | 相對於 `benchmark/lean_hard/` 的 Lean 檔路徑 |
| `source` | str | `core` 或 `mathlib`；語意未在文件中說明（datasheet §9 第 7 項） |
| `verified` | bool | 驗證旗標；validator 只檢查型別（datasheet §3） |
| `difficulty`、`novelty`、`contamination_risk`、`mathlib_match` | 見 datasheet §3 | 作者或 LLM 輔助標註 |
| `audit_notes` | str | 審查註記 |
| `bench_split` | str | 目前全部為 `dev` |
| `retired` | str（選填） | 存在即表示退役，並附說明 |

欄位與型別由 `src/mathesis/lean_pilot.py` 的 `REQUIRED_FIELDS` 與 `validate_lean_pilot` 檢查；本檔撰寫時 validator 對目前檔案回傳 `True`（datasheet §3）。

### 3.4 退役、污染與已知問題

- **退役題保留在檔案中。** 17 題退役，其中 14 題為 B0 天花板題、3 題為近似重複題（datasheet §5.1）。`b0` 的 loader 不會跳過退役題，因此未指定 `--problems` 時，B0 的 pass@k 會包含 17 題退役題（datasheet §5.1）。hint-gap 的目標與 hint 檔產生會跳過退役題（datasheet §5.1）。
- **污染審計（啟發式）。** 審計掃描 8,624 個 Mathlib `.lean` 檔，檢查全部 109 題（`runs/contamination/20261106T062924Z.json`，datasheet §5.3）。名稱 stem 命中 10 題，內文非 generic 命中 0 題。新增的 20 題兩項皆為 0。命中的 10 題與先前的審計相同，且已確認屬於原始 38 題版本（datasheet §5.3）。這是啟發式篩選，**不是污染的證明**；沒有命中也不代表題目未曾出現在訓練資料中（datasheet §5.3）。
- **切分。** 全部 109 題的 `bench_split` 皆為 `dev`。計畫中的 calibration / dev / test 切分未在檔案中實作（datasheet §5.5）。
- **hint 檔的歷史錯誤。** 2026-11-04 之前的 hint-gap run 使用了錯誤係數的 `lean_ineq_cube_sum_zero_sixth` hint（datasheet §4.5、§5.5）。

<!-- 來源: docs/datasheet-lean_hard.md, docs/paper-plan.md (§11, §11.1) -->

## 4 評測協議

### 4.1 證明器與生成設定

證明器為 `deepseek-ai/DeepSeek-Prover-V2-7B`，後端為 `transformers`（`src/mathesis/llm_baseline.py` 的 `TRANSFORMERS_MODEL_NAME`、`DEFAULT_BACKEND`）。程式的預設值為 `DEFAULT_K = 8`、`DEFAULT_MAX_TOKENS = 1024`、`DEFAULT_TEMP = 0.6`、`DEFAULT_VERIFY_WORKERS = 12`（同檔）。

hint-gap 的 k=32 manifest 記錄 temperature 0.6、max_tokens 1024、基礎 seed 0，verify_workers 為 3（neg §2）。B0 各 run 的實際參數以其 `manifest.json` 為準。`[待作者補充：B0 run 的 manifest 參數逐一核對結果；本次撰寫未逐一核對]`

**種子。** 基礎 seed 之外，每題每條件的種子由題名推導：對字串 `"seed:problem:config"` 取 SHA-256，取前 8 bytes（neg §2，`src/mathesis/runlog.py` 第 101–104 行）。在 4 張 GPU 上，同一 seed 的回應逐位元相同（16/16；neg §8）。

**分片。** `scripts/run_sharded.py` 依題目將工作分到各 GPU，最後由 `scripts/merge_shards.py` 合併（neg §8）。

### 4.2 判定（judge v2）

候選證明的禁用 token 為 `sorry`、`admit`、`axiom`（datasheet §4.3）。judge v2 的變更如下（plan §11 第 16 項，commit `246539e`）。

- forbidden token 檢查前，先剝除證明文字中的註解；未閉合的區塊註解視為 forbidden。
- Lean 的輸出仍逐字檢查。
- 新增失敗類別 `lean_crash`（子行程非零退出且無診斷）。

v1 判定的既有 run 不得以 v2 重新解讀；若要比較，需以 v2 重新驗證候選檔（plan §11 第 16 項；datasheet §5.5）。B0 seed 0 的 run `20261103T122531Z_b0` 原為 v1；commit 訊息記載其在 v2 下 525/525 通過不變（datasheet §5.5）。`plan` §11.1 未逐行註明 seed 0 的判定版本（datasheet §5.5）。

### 4.3 沙箱

Lean 子行程以 `lake env lean <candidate.lean>` 執行，工作目錄為 `lean/`，timeout 為 180 秒（neg §2）。網路隔離由環境變數 `MATHESIS_LEAN_SANDBOX` 控制，預設 `auto`，即可用時使用 `unshare -rn`；設為 `off` 則關閉（`src/mathesis/llm_baseline.py` 的 `SANDBOX_ENV` 與 `SANDBOX_PREFIX = ("unshare", "-rn")`；plan §11 第 16 項）。環境變數以白名單傳入，白名單為 PATH、ELAN_HOME、LANG、LC_ALL、TMPDIR、HOME（neg §2）；plan §11 第 16 項說明 HOME 為私有暫存目錄。Run 的 manifest 記錄 sandbox mode 為 `unshare-net`（datasheet §6.1）。

### 4.4 重驗

`scripts/replay_verify.py` 不需要模型或 GPU，以已儲存的回應重新判定（neg §8）。其參數包括 `--benchmark`、`--verify-workers`、`--problems`、`--limit-samples`、`--out`、`--table`（`scripts/replay_verify.py` 的 `add_argument`）。`[待作者補充：replay_verify.py 的完整指令列，包括位置參數]`

重驗的範圍是判定，不是生成：它證明的是「給定儲存的回應，判定可逐樣本重現」（neg §8；plan §11.1）。

<!-- 來源: docs/paper-negative-results.md, docs/datasheet-lean_hard.md, docs/paper-plan.md (§11, §11.1), docs/related-work-notes-A.md, src/mathesis/llm_baseline.py, scripts/replay_verify.py -->

## 5 基線結果（B0）

**設定。** B0 為無提示的基線，k=8，使用兩個 seed，主要分析為啟用的 92 題（b0-json；plan §11.1）。seed 0 由 `20261103T122531Z_b0`（舊 89 題）與 `20261104T141934Z_b0-merged`（新 20 題）組成；seed 1 由 `20261104T054619Z_b0-merged` 與 `20261104T150345Z_b0-merged` 組成（neg §8）。`b0-json` 未記錄這個對應所用的 `--seed-runs` 參數；本文的對應由題數與題目集合推得，尚待作者確認（neg §9 第 3 項）。

**結果。** 下表數字取自 `b0-json`，四捨五入至小數點後三位；原始值見該檔。pass@1 的 95% 信賴區間以題目重抽樣的 bootstrap 計算，10,000 次重抽樣，seed 為 0（b0-json `bootstrap`；[待補引用：bootstrap 方法]）。pass@k 的定義與估計量 `[待補引用：pass@k 的定義與估計量]`。

| 指標 | seed 0 | seed 1 |
|---|---|---|
| pass@1 平均（啟用 92 題） | 0.626 | 0.610 |
| pass@8 平均（啟用 92 題） | 0.728 | 0.739 |
| pass@1 的 95% CI（啟用 92 題） | [0.535, 0.715] | [0.519, 0.698] |
| pass@1 平均（全部 109 題，含退役） | 0.683 | 0.670 |

（b0-json `seeds`；CI 數字與啟用題的 pass@1、pass@8 亦見 plan §11.1）

依題型分層的 pass@1 如下（b0-json `stratification.by_insight`）。

| 分層 | 題數 | seed 0 | seed 1 |
|---|---|---|---|
| insight | 46 | 0.307 | 0.291 |
| routine | 46 | 0.946 | 0.929 |

**噪音下限。** 啟用 92 題中，兩個 seed 之間逐題 |Δpass@1| 為 0 的有 72 題、為 0.125 的有 13 題、為 0.25 的有 6 題、大於 0.25 的有 1 題；中位數為 0，p90 為 0.125，最大值為 0.625（b0-json `noise_floor.active`）。最大值的題為 `lean_nat_r_mod_seven_pow`，seed 0 為 7/8，seed 1 為 2/8（neg §4(b)）。原 89 題的最大值為 0.25（neg §4(b)）；新增 20 題的最大值同為 0.625（neg §4(b)，本次重算，未寫入分析檔）。這是 k=8、無提示的 seed 間差異，不是 hint-gap 的噪音，但它顯示小樣本下單一題就可能出現 0.25 至 0.625 的差異（neg §4(b)）。

**飽和分類。** 以兩個 seed 合併（k=16）分類：16/16 全對為天花板，0/16 為地板，其餘為中段（b0-json `saturation`；分類規則見 `scripts/b0_report.py`）。insight 題為天花板 5、中段 19、地板 22；routine 題為天花板 37、中段 8、地板 1；合計為天花板 42、中段 27、地板 23（b0-json `saturation`）。routine 題的 pass@1 約為 0.93 至 0.95，多數已飽和。因此 B0 較適合作為題目難度的描述，不宜單獨用來比較方法。`[待作者補充：B0 基線的解讀是否需與其他基線比較]`

**限制。** B0 的數字不應用來宣稱超越已發表的 SOTA 數字（datasheet §6.2）。兩個 seed 只是噪音下限的粗略估計，不是完整的變異量估計。

<!-- 來源: docs/paper-plan.md (§11.1), docs/paper-negative-results.md (§4, §8, §9), runs/analysis/b0_report_k8_2seeds.json, scripts/b0_report.py, docs/datasheet-lean_hard.md (§6.2) -->

## 6 hint-gap 與負面結果

### 6.1 操作化與判定規則

hint-gap 定義為（datasheet §1）：

Gap_B(p) = Pr[solve p | B, 提示版] − Pr[solve p | B, 原版]

對題目 p、固定證明器、固定預算 B。提示版在題目前加入參考證明的第一個 `have` 陳述，只給陳述、不給證明（datasheet §1）。

判定規則（neg §1，`scripts/hint_significance.py`）如下。

- 每題每條件取樣 k=32 次，成功率為成功次數 c/32。
- 每題以雙尾 Fisher 精確檢定比較 2×2 表（`[待補引用：Fisher 精確檢定]`），α = 0.05。
- **hint 有效**：p < 0.05 且 gap > 0；**hint 有害**：p < 0.05 且 gap < 0。
- **天花板**：plain 成功次數為 32 的題，不檢定。
- **多重比較**：以 Holm step-down 校正（`[待補引用：Holm 校正]`）。主要分析的家族為「有資訊」的題，即非天花板且兩條件合計至少 1 次成功；敏感度分析的家族為所有非天花板的已檢定題。

**規則的時間點。** 規則記載於 `docs/paper-plan.md` §11，日期為 2026-11-06。定規則時，舊 23 題的 k=32 結果已經看過，新 15 題中也已看過 12 題（shard0、shard1、shard2）；只有 shard3 的 3 題（`real_r_nested_diff`、`nat_r_sophie_germain_composite`、`algebra_r_sq_hom_comm`）是在規則之後才出現（neg §1）。**本文不主張預先登記。** 規則應稱為事後確定的分析規則。

規則對 38 題的 Holm 家族選擇不敏感：主要家族（18 題）與敏感度家族（38 題）都只有 `lean_logic_drinker_implication` 通過（neg §1）。但只用舊 23 題時，結論會改變（見 6.6）。原定「insight ≥ 40 題」的目標，改為實際可得題數（neg §1）。

### 6.2 比較集合與提示

比較集合為 38 題，由舊 23 題與新 15 題組成（neg §2）。

- 舊 23 題：`runs/20261104T131752Z_hint-gap-merged`，hint 檔為 `benchmark/lean_hard/hints/first_have.json`（37 項）。
- 新 15 題：`runs/20261106T061711Z_hint-gap-merged`，為 B0 篩選後非天花板者，hint 檔為 `benchmark/lean_hard/hints/first_have_v2.json`（46 項）。

兩個 run 的題目集合不重疊（neg §2）。提示規則為 `first typed have in reference_proof, as '<name> : <statement>'`，兩個 hint 檔的 `rule` 相同；v2 中舊 23 題的 hint 與 v1 逐一相同（neg §2）。

提示模板（neg §2）：plain 為 `Complete the following Lean 4 code:` 後接 Lean 4 程式區塊；hint 為 `Complete the following Lean 4 code. A useful auxiliary step is: {hint}` 後接同樣的區塊。模型、temperature、max_tokens 與 seed 見 4.1。判定與沙箱見 4.2 與 4.3。

### 6.3 結果

下表取自 `sig-json` 的 `summary`（neg §3）。

| 項目 | 題數 |
|---|---|
| 已檢定題數 | 38 |
| 天花板（不檢定） | 0 |
| 有資訊（主要家族） | 18 |
| 未校正 p < 0.05 的 hint 有效 | 3 |
| 未校正 p < 0.05 的 hint 有害 | 1 |
| 無可偵測效應 | 34 |
| Holm 後通過（主要家族，18 題） | 1 |
| Holm 後通過（敏感度家族，38 題） | 1 |

未校正 p < 0.05 的四題如下（neg 附錄 A，`sig-json` 的 `per_problem`）。

| 題名 | plain c/32 | hint c/32 | gap | p | p_holm（主要） | p_holm_all（敏感度） |
|---|---|---|---|---|---|---|
| `lean_logic_drinker_implication` | 3 | 27 | +0.75 | 1.26e-9 | 2.26e-8 | 4.77e-8 |
| `lean_ineq_sq_sum_abc_four` | 0 | 8 | +0.25 | 0.0048 | 0.081 | 0.176 |
| `lean_nat_sum_even` | 5 | 14 | +0.28125 | 0.027 | 0.435 | 0.979 |
| `lean_algebra_r_sq_hom_comm` | 27 | 18 | −0.28125 | 0.027 | 0.435 | 0.979 |

只有 `lean_logic_drinker_implication` 通過 Holm 校正。它仍只來自單一證明器、單一提示規則、單一 seed（neg §5(4)）。`lean_algebra_r_sq_hom_comm` 是唯一的未校正 hint 有害題，其 hint 反而降低成功率（neg §3）。

### 6.4 k=8 與 k=32 的對照

`lean_real_geom_mean_two` 是小樣本 gap 不可信的例子。在 k=8（`runs/20261104T074803Z_hint-gap-merged`，judge v2）中，plain 為 1/8、hint 為 6/8，gap 為 +0.625，未檢定。在 k=32（38 題合併）中，plain 為 12/32、hint 為 16/32，gap 為 +0.125，p = 0.450（neg §4(a)）。

各 k=32 子集的平均 gap，以及 plan 記載的兩層 95% CI 如下（plan §11.1）。這些 CI 的計算方式未在本檔重現。

| run | 題數 | 平均 gap | 95% CI |
|---|---|---|---|
| `20261104T131752Z_hint-gap-merged`（k=32，舊 23 題） | 23 | +0.057 | [−0.008, 0.143] |
| `20261106T061711Z_hint-gap-merged`（k=32，新 15 題） | 15 | −0.004 | [−0.073, +0.060] |

### 6.5 檢定力與多重檢定

以 n = 32 對 32、基線成功率 0.5、雙尾 Fisher 精確檢定（α = 0.05）計算，檢定力在 δ = 0.25 時為 0.46，在 δ = 0.125 時為 0.13（0.127）。這是單點計算，假設獨立二項分佈，基線固定為 0.5；實際基線因題而異，本次未量測其他基線。它不是正式的效力分析（neg §5(2)）。

38 題在 α = 0.05 下，若所有題都是虛無假設，預期約 1.9 次 p < 0.05（假設獨立；neg §5(4)）。實際未校正 p < 0.05 共 4 題（3 有效、1 有害）。`lean_nat_sum_even`、`lean_ineq_sq_sum_abc_four` 與 `lean_algebra_r_sq_hom_comm` 的數量與預期假陽性相當，其主要家族的 p_holm 分別為 0.435、0.081、0.435，不宜單獨解讀為效應或傷害（neg §5(4)）。

### 6.6 結果對 hint 選擇與子集組成的敏感度

- **hint 選擇。** `lean_real_lucas_five` 在 k=8 的人工 hint 下 gap 為 +0.875（`runs/analysis/hint_gap_report_20261103T154014Z_hint-gap.json`）。改為第一個 `have` 後 gap 為 0（plan §11.1，`20261104T074803Z` 列）。前者來自 judge v1 的 run，且同一 run 中 `lean_ineq_cube_sum_zero_sixth` 的 hint 係數有誤；因此這組對照只能作為定性例子。本文撰寫時未獨立重算第二個數字（neg §4(3)、§9 第 5 項）。
- **子集組成。** 只用舊 23 題時，有資訊的題為 11 題，Holm 後通過 2 題；`lean_ineq_sq_sum_abc_four` 的主要 p_holm 為 0.0475，通過 α = 0.05。合併新 15 題後（有資訊 18 題），p_holm 升至 0.081，不再通過。0.0475 由本次以 `scripts/hint_significance.py` 的 `build_significance_report` 對 23 題重算，未寫入檔案（neg §5(5)）。因此這個結論不穩定，不應只依 p 值門檻判讀。

### 6.7 為何不能解讀為「構造性提示沒有幫助」

1. **基線與受測為同一模型。** plain 與 hint 都是 DeepSeek-Prover-V2-7B 的輸出。結果描述的是此模型在此提示規則下的行為，不是某類提示的性質（neg §5(1)）。
2. **檢定力不足。** 對 δ = 0.125（基線 0.5 提高到 0.625）的效應，單題檢定力約為 0.13（6.5）。
3. **結果對 hint 選擇敏感。** 見 6.6。
4. **子集組成會改變結論。** 見 6.6。

`insight` 標籤與 hint 效果之間，目前沒有可偵測的關聯。因此不應以 `insight = True` 預期「給提示會變好」，也不得宣稱兩者相關（datasheet §5.2、§6；neg §6）。本文只能陳述：在此證明器、此 hint 規則、此題組下，沒有可偵測的效果（plan §11）。

<!-- 來源: docs/paper-negative-results.md (§1–§6, 附錄 A), runs/analysis/significance_k32_combined.json, docs/paper-plan.md (§11, §11.1), docs/datasheet-lean_hard.md (§1, §5.2, §6), benchmark/lean_hard/hints/first_have.json, benchmark/lean_hard/hints/first_have_v2.json -->

## 7 限制

- **單一證明器。** 只使用 DeepSeek-Prover-V2-7B（transformers backend），未更換為其他證明器（neg §7）。
- **單一提示規則。** 只使用「第一個有型別標註的 `have`」。未檢驗完整證明草稿、多個 `have`，或人工撰寫的提示（neg §7）。
- **取樣與 seed。** k=32 只有 seed 0。seed 噪音只在 k=8、無提示的 B0 上量過（neg §7）。
- **事後確定的規則。** 判定規則不是預先登記的（6.1）。
- **題組規模。** 比較 38 題，其中有資訊的為 18 題；子集之間的比較樣本不足（neg §7）。
- **標註。** `insight` 為結構標註，流程含 LLM 標註；標註比例與審核流程待作者補充（neg §7；datasheet §9 第 6 項）。
- **切分。** 全部為 `dev`，沒有獨立的 test split（datasheet §5.5）。
- **判定版本。** 同時存在 v1 與 v2 判定的 run；v1 的 forbidden 判定不得以 v2 重新解讀（plan §11 第 16 項）。B0 seed 0 的判定版本未逐行註明（datasheet §5.5）。
- **重驗範圍。** 重驗只在單一機器與單一 Lean／Mathlib 版本上進行（plan §11.1；neg §8）。
- **未執行的指令。** `mathesis b0 --controls` 所用的 `CONTROL_PROBLEMS` 不在 `lean_hard` 中；依程式碼判斷，此組合會失敗，但本次未實際執行（datasheet §5.5）。
- **污染審計。** 為啟發式篩選，不是污染的證明（datasheet §5.3）。
- **Pantograph 與 MLX 的 run。** Pantograph 整合測試未驗證（plan §11 第 5 項）。MLX 4-bit 的 run 目錄不在本 checkout 中（datasheet §7；plan §11 第 9、10 項）。

<!-- 來源: docs/paper-negative-results.md (§7), docs/datasheet-lean_hard.md (§5.3, §5.5, §7, §9), docs/paper-plan.md (§11, §11.1) -->

## 8 可重現性與資料可得性

### 8.1 指令

以下指令取自 datasheet §6.1 與 neg §8。旗標名稱已由 `add_argument` 確認存在的部分包括 `--k`、`--seed`、`--out`、`--problems`、`--hints`、`--shard`、`--verify-workers`；完整參數以 `--help` 為準。

```bash
# B0 基線（k=8）
PYTHONPATH=src python3 -m mathesis.cli b0 --benchmark benchmark/lean_hard --k 8 --seed 0 --out runs

# hint-gap（k=32，hint 檔為 first_have_v2.json）
PYTHONPATH=src python3 -m mathesis.cli hint-gap --benchmark benchmark/lean_hard \
  --hints benchmark/lean_hard/hints/first_have_v2.json --problems <題名清單> --k 32 --out runs

# 顯著性分析（Fisher 檢定與 Holm 校正）
python3 scripts/hint_significance.py <run_dir> [<run_dir> ...] --out <file> --table

# B0 seed 比較與噪音下限
python3 scripts/b0_report.py --seed-runs 0:<dir1>,<dir2> --seed-runs 1:<dir3>,<dir4> \
  --benchmark benchmark/lean_hard --out <file> --table

# 污染審計（啟發式）
python3 scripts/contamination_audit.py --benchmark benchmark/lean_hard --out <path>

# 重驗已儲存的回應（不需模型或 GPU）
python3 scripts/replay_verify.py --benchmark benchmark/lean_hard --verify-workers 12 ...
```

`<題名清單>` 與各 run 目錄見 8.2。`[待作者補充：b0_report.py 的實際 --seed-runs 指令；neg §9 第 3 項]` 指令列中的 `...` 為 `replay_verify.py` 位置參數的佔位，`[待作者補充：replay_verify.py 的完整指令列]`。`b0` 的 `--benchmark` 預設為 `benchmark/lean_pilot`，跑 `lean_hard` 時必須指定（datasheet §6.1）。

### 8.2 Run 目錄

| 用途 | 目錄 |
|---|---|
| hint，k=32，舊 23 題 | `runs/20261104T131752Z_hint-gap-merged`（由 `shards_20261104T080302Z` 的 shard0–shard3 合併） |
| hint，k=32，新 15 題 | `runs/20261106T061711Z_hint-gap-merged`（shard3 於 GPU 3 重跑） |
| hint，k=8，37 題 | `runs/20261104T074803Z_hint-gap-merged` |
| hint，k=8，40 題（judge v1，僅探索性） | `runs/20261103T154014Z_hint-gap` |
| B0，k=8，seed 0 | `runs/20261103T122531Z_b0`、`runs/20261104T141934Z_b0-merged` |
| B0，k=8，seed 1 | `runs/20261104T054619Z_b0-merged`、`runs/20261104T150345Z_b0-merged` |
| 分析檔 | `runs/analysis/significance_k32_combined.json`、`runs/analysis/b0_report_k8_2seeds.json`、`runs/analysis/hint_gap_report_*.json` |

（neg §8；plan §11.1）`[待作者補充：釋出時要隨資料集附上哪些 run 目錄；neg §9 第 9 項]`

### 8.3 重驗與生成的可重現性

2026-11-06，在同一台機器（Lean v4.35.0、同一版 Mathlib、judge v2、`unshare -rn` 沙箱）以 `scripts/replay_verify.py` 對三個 run 全量重驗已儲存的回應。`passed` 與 `failure_class` 與儲存值一致的情形如下（neg §8；plan §11.1）。

| run | 樣本數 | 不一致數 |
|---|---|---|
| `20261104T054619Z_b0-merged` | 712 | 0 |
| `20261104T131752Z_hint-gap-merged` | 1,472 | 0 |
| `20261106T061711Z_hint-gap-merged` | 960 | 0 |
| 合計 | 3,144 | 0 |

**範圍。** 這證明的是「給定儲存的回應，判定可逐樣本重現」。生成本身的可重現性另以 4 張 GPU 重新生成同一種子的回應，結果逐位元相同（16/16；neg §8）。兩者都只在單一機器與單一 Lean／Mathlib 版本上驗證，未跨機器（neg §8；plan §11.1）。重驗不證明生成可重現。

### 8.4 環境

- Lean toolchain：`leanprover/lean4:v4.35.0`（datasheet §1）。
- Mathlib rev：`56a005855ea17e0b0958f73ec801ae140b0a1679`（datasheet §1，來源 `lean/lake-manifest.json`）。
- Python 3.13.18；platform `Linux-5.15.0-139-generic-x86_64-with-glibc2.31`（neg §8）。
- git commit `39cbd1c9a55dbafc05b1d624c71af1344516d831`。manifest 的 `git_dirty` 為 true，但 `git_diff_hash` 為 `e3b0c44298fc`，即空字串的 SHA-256 前綴，因此未提交的程式狀態沒有被記錄（neg §8、§9 第 2 項）。

### 8.5 資料可得性

- 資料集位於 `benchmark/lean_hard/`，包含 `problems.json`、`lean/` 與 `hints/`（datasheet 檔頭）。
- 資料集不含 run 的原始輸出（datasheet §4.7）。分析檔位於 `runs/analysis/`（8.2）。
- MLX 後端的 run 目錄不在本 checkout 中（datasheet §7）。
- 模型權重的授權：`[待作者補充：DeepSeek-Prover-V2-7B 權重的授權條款]`。plan §11 的已知問題記載，權重授權欄位目前為空，且針對 `mlx-community/DeepSeek-Prover-V2-7B-4bit`。

<!-- 來源: docs/datasheet-lean_hard.md (§1, §4.7, §6.1, §7), docs/paper-negative-results.md (§8, §9), docs/paper-plan.md (§11, §11.1), src/mathesis/cli.py, scripts/replay_verify.py -->

## 9 倫理與授權

- **資料集授權。** `lean_hard` 的資料集（`problems.json`、`hints/`、說明文件，以及 `lean/` 下的題目與證明檔）採 CC BY 4.0（`benchmark/lean_hard/LICENSE.md`；datasheet §8）。
- **第三方授權。** Mathlib 為 Apache-2.0，依其原授權，不在本資料集的授權範圍（datasheet §8）。
- **著作權人與年份。** `[待作者補充：著作權人與年份，LICENSE.md 中為待補欄位]`
- **引用格式與 DOI。** `[待作者補充]`
- **作者與單位。** 文件記載的作者為 ChiaAn Lin（datasheet §8）。所屬單位 `[待作者補充]`（plan §10 第 4 項，尚未決定）。
- **LLM 參與。** 題目的 `insight`、`difficulty` 等欄位含 LLM 輔助標註；標註的 prompt、回應與審核紀錄 `[待作者補充：存放位置]`（datasheet §4.4、§9 第 6 項）。
- **個人資料與敏感內容。** `[待作者補充：是否有個資或敏感內容的檢查紀錄；材料中未記載]`
- **使用限制。** 不應以本資料集的 pass@1 宣稱超越 SOTA，不應把 hint-gap 結果推廣為一般結論（datasheet §6.2）。

<!-- 來源: docs/datasheet-lean_hard.md (§4.4, §8, §9), benchmark/lean_hard/LICENSE.md, docs/paper-plan.md (§10, §11 已知問題) -->

## 附錄

**附錄 A：逐題結果（k=32，38 題）。** 完整的逐題表見 `docs/paper-negative-results.md` 附錄 A，本文不重貼。表中欄位包括 plain 與 hint 的成功次數、gap、p 值，以及主要與敏感度兩種家族的 p_holm。

<!-- 來源: docs/paper-negative-results.md (附錄 A) -->

