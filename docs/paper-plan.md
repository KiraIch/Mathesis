# Mathesis 投稿計畫 v1.1（2026-11-03）

> **作者資訊（2026-11-03 提供）**：ChiaAn Lin，Master Program for Precision Health and Intelligent Medicine。
> 注意：RIKEN CBS 申請與預印本的單位寫法要一致，發布前再確認（見 §10）。
>
> **v1.1 變更（2026-11-03）**：(1) 目標改為 **2027-01-08 RIKEN CBS 截止前完成成果**；(2) 標註改為 **LLM 輔助並揭露**；(3) 底層證明器保留 **DeepSeek-Prover-V2-7B（MLX 4-bit）**；(4) §6 改為 9 週衝刺計畫，原長期時程保留在 §6 末；(5) §11 更新為目前狀態。
>
> **v1.2（2026-11-03）**：1/8 的交付物確認為**申請書**（英文；研究計畫書與研究陳述兩份；尚未指定指導教授）。草稿見 `docs/application/research-plan.md`。預印本改為申請後的選項，不再是 1/8 的必要項目。

> 用途：把 Mathesis 從 RIKEN 研究計畫書的 pilot，推進成一篇可預印的研究成果。
> 依據：2026-11-02 的唯讀審計，以及 2026-11-03 的 B0 結果。
> 與 `docs/research-design.md` 的關係：該文件仍是博士計畫的長期藍圖。本文件只處理第一篇成果，並在必要處修正它（見 §2.3）。

---

## 0. 結論先行

1. **現況**：框架是真實程式碼，底層 LLM 證明器已能在本機跑出真實 Lean 結果。B0 基線（MLX 4bit 後端，run 不在本 checkout 中）：舊 50 題（`lean_pilot`）pass@1 0.907、pass@8 1.000，已飽和；新 38 題（`lean_hard`）pass@1 0.819、pass@8 0.895，仍有區分力。Linux transformers bf16 的現有 run 見 §11.1。**但 Mathesis 控制層還不是方法**：impasse 在 pilot 上全為 0，沒有 LLM 算子，hint-gap 已實作，正式數據尚未完成（見 §11）。
2. **核心問題不變**：

   > **LLM 證明器在需要「輔助構造」的定理上卡住時，由「僵局（impasse）」觸發、型別化的表徵重構，能否在等算力條件下，勝過同一套算子用固定排程或隨機觸發的版本？**

3. **目標（v1.1 新增）**：2027-01-08 前完成四件事：
   - (a) construction-gap benchmark v1（衝刺版約 80–100 題，含 insight/routine 配對）；
   - (b) hint-gap 測量；
   - (c) Mathesis v1 的 H1 判定（dev 為主，test 只跑一次）；
   - (d) 申請書草稿與可重現的程式碼、結果。
4. **成果形式**：預印本（arXiv 或同等）＋可重現程式碼。投稿順序不變：預印本之後才考慮 NeurIPS 2027 主會（截稿約 2027 年 5 月中，以官方公告為準）與保底的 Datasets & Benchmarks。
5. **保底**：若 H1 不成立，仍以 benchmark 與負面結果寫成預印本。不論 H1 成敗，都會產出一份成果。
6. **時程風險很高**：9 週內要完成 benchmark、系統與 test 實驗。§6 列出砍掉的範圍與門檻，任何一關延誤就砍範圍，不延長截止日。

---

## 1. 現況診斷（審計證據，2026-11-02，部分於 11-03 更新）

| 面向 | 現況 | 對成果的影響 |
|---|---|---|
| 程式框架 | search、controller、operators、impasse 是真實程式碼。單元測試 415 tests，OK（skipped=10，皆為 gated：kernel、LeanInteract、lean-bench 已在本機通過；Pantograph 未安裝） | 可沿用 |
| Lean 環境 | Lean v4.35.0、Mathlib v4.35.0 已建好；Pantograph v0.3.19 在 Mac 上已編譯，EPYC 本機尚未安裝 | 就緒 |
| 真實 Lean 路徑 | B0 已用真實 Lean（`lake env lean`）跑過舊題組與新題組；gated 測試在 review 修正後尚未重跑 | 要重跑（§6 W1） |
| 實驗結果 | B0：舊題組與新題組各一次完整 run，manifest、results、summary 齊全 | 已有第一組真實數字 |
| Benchmark | 舊 `lean_pilot` 50 題：test split 已被 B0 用過，不能再當 test；新 `lean_hard`：commit 版 38 題（14 題 insight）；工作樹已擴充為 89 題（40 題 insight，全部 `dev`，Lean 驗證通過，待 commit） | 需要擴充並重新切 split |
| 算子 | AddSubgoal（子式枚舉）、TemplateHave（手寫模板，疑似過擬合）、OracleHave（只當上界）、AddSymbol（mock 下永遠失敗） | 需要 LLM 提案、型別過濾的算子 |
| 控制器 | 四個控制器的 `choose()` 仍是 `pick_first`。impasse 分數的 budget 項已設為 0，pilot 上 impasse 全為 0 | 「impasse 驅動」目前名不符實 |
| hint-gap | `src/` 內沒有 hint 相關實作 | 核心操作化尚未測量 |
| Baseline | B0 完成；B1、B2、B4 未實作 | H1 尚無法檢驗 |
| LLM | 底層 DeepSeek-Prover-V2-7B 已可載入，batch 8 約 95 tok/s | 已有 LLM，但還沒接控制層 |
| 版本控制 | `debfb76`（初始）、`b582c58`（新題組與 `--benchmark`）、`f84a92a`（`docs/`，含本文件 v1.2）。程式與 benchmark 的其餘變更尚未 commit | 待你決定 commit 範圍 |
| 文獻 | 設計文件中約 10 條 2026 文獻已核對（§9.1） | 新穎性核對進行中 |

---

## 2. 研究定位

### 2.1 為什麼不能正面和 SOTA 比解題率

DeepSeek-Prover-V2、Kimina、Goedel-Prover-V2、Seed-Prover 這類系統，在 miniF2F 上的表現靠的是大規模 RL 與龐大算力。一個人加一台 M5 不可能在「總解題率」上贏。審稿人也不會接受「我們打敗了 BFS」這種結論。

### 2.2 我們能贏的地方：控制層，而不是模型

貢獻放在**證明器之上的控制層**。底層模型固定用一個公開的證明器，比較的是**什麼時候重構、用哪個算子重構**。這是乾淨的消融問題，算力可以控制，結論也不依賴我們擁有最強的模型。

### 2.3 對 `research-design.md` 與 v1.0 的修正

| 原設計 | 修正 | 理由 |
|---|---|---|
| 模板與枚舉產生候選，LLM 可選 | **LLM 依失敗軌跡提案，再經 Lean 型別與 elaboration 過濾**；模板只當消融 | 模板會被批評是答案 oracle，也已觀察到過擬合 |
| BFS 是底層搜尋 | 底層換成公開 LLM 證明器（whole-proof 生成），BFS 保留成符號 baseline | 與 2026 年的領域現況對齊 |
| 主實驗用**非 CoT** 證明器（v1.0） | **改用 DeepSeek-Prover-V2-7B（CoT）**，並在論文中揭露為偏差 | 已在本機可用、B0 已實測；衝刺時程內沒有時間替換 |
| 15–20 題 pilot；v1.0 的 150–200 題 | 衝刺版 80–100 題（test ≥50）；長期版再擴到 150–200 題 | 9 週內的可行規模；統計力下降，須在結果中報告 CI |
| 「insight 題」由人工標註 | **hint-gap 做操作化定義**（§3.2）；LLM 輔助標註並揭露（§5.3） | 客觀、可重現；單人無法做雙人 κ，所以 κ 改為 LLM 與作者的一致性 |
| 人類研究放在 Y2–Y3 | 主論文不做，認知科學只當動機與詮釋框架 | 範圍控制；AGENTS.md 規定認知建模的主張必須有行為資料 |

---

## 3. 論文核心

### 3.1 暫定題目

- *When to Restructure: Impasse-Triggered Auxiliary Construction for LLM Theorem Provers*
- 備選：*Mind the Construction Gap: Measuring and Closing the Auxiliary-Construction Bottleneck in Formal Theorem Proving*

### 3.2 關鍵操作化：construction gap（hint-gap）

對題目 \(p\)、固定的證明器 \(M\)、固定預算 \(B\)：

\[
\mathrm{Gap}_B(p) = \Pr[\text{solve } p \mid B, \text{提示版}] - \Pr[\text{solve } p \mid B, \text{原版}]
\]

「提示版」是在題目前面加上參考證明中的輔助構造（`have` 陳述、witness、輔助函數），**只給陳述，不給證明**。

- **Insight 題**：Gap 大（門檻於 W2 依 Gap 分布決定，並記錄在 §11），而且原版解題率低。
- **Routine 對照題**：統計結構與原版難度相近，但 Gap ≈ 0。

好處有三：把「需要頂悟」變成可量測的量；直接量化 LLM 證明器的瓶頸；也讓 OracleHave 有了正當角色，作為上界。

### 3.3 預期貢獻（論文 §1 的寫法）

1. **Construction-gap benchmark**：衝刺版 80–100 題（insight 與 routine 配對）、擾動版本與污染審計；長期版 150–200 題。
2. **Mathesis 控制層**：impasse 偵測（根據 Lean 錯誤軌跡、狀態停滯、重複率）加上型別化重構算子（AddSubgoal、AddSymbol，長期加 Generalize、Reformulate）加上 bandit 式算子選擇。可以接到任何證明器上。
3. **等算力的因果消融**：「何時重構」對上固定排程與隨機觸發；「選哪個算子」對上隨機算子；「是否需要重構」對上 pass@k。
4. **可審計的僵局與重構軌跡**：用來做個案研究與失敗分類。

### 3.4 假設與否證條件（**跑 test split 前要在 OSF 預註冊**）

| 編號 | 假設 | 主要指標 | 否證條件 |
|---|---|---|---|
| H1 | 在 insight split 上，impasse 觸發的重構勝過同一算子庫的固定排程與隨機觸發（觸發次數期望值相同） | 預算 B\* 下的解題率；mixed-effects logistic 迴歸，題目與家族為隨機效應 | Mathesis 減去 max(B1, B2) 的 95% CI 包含 0 |
| H2 | 重構帶來的增益集中在 insight 題（insight × 方法交互作用） | 交互作用項 | 交互作用的 CI 包含 0 |
| H3 | 依失敗軌跡選算子，勝過隨機選算子 | 解題率 | 與 B4 的差距 CI 包含 0 |
| H4 | 在 1× 與 4× 預算下，Mathesis 都在 solve-vs-cost Pareto 前緣上 | 曲線 | 有任一預算點被 pass@k 支配 |

- Seed 不算獨立樣本。用 Holm–Bonferroni 校正，paired bootstrap 當輔助。
- **H1 是 kill criterion**：H1 失敗就以負面結果寫成預印本（§4）。這個判定由主模型做，不下放給 subagent。
- 衝刺版 H4 只做 1× 與 4× 的子集，16× 不做。

---

## 4. 投稿與發表策略

| 優先序 | 目標 | 截止（約，以官方公告為準） | 條件 |
|---|---|---|---|
| **第一** | **RIKEN CBS 申請** | **2027-01-08** | 成果（申請書草稿＋可重現結果）完成。形式待 §10 第 1 項確認 |
| 第二 | 預印本（arXiv 或同等） | 2027-01 之後，須你明確同意 | arXiv 需要有 endorsement 的帳號；單位寫法見 §10 第 4 項 |
| 主投 | **NeurIPS 2027 主會** | 2027 年 5 月中 | H1 成立 |
| 保底 | **NeurIPS 2027 Datasets & Benchmarks** | 約同期 | H1 不成立，改以 benchmark 與負面結果為主 |
| 早期回饋 | ICML 2027 的 AI for Math 類 workshop，或 NeurIPS 2027 的 MATH-AI workshop | 2027 年春夏 | 送 pilot 結果，風險低 |
| 下一輪 | ICLR 2028 | 約 2027 年 9–10 月 | 被拒或需要更多實驗時 |

ICML 2027（約 2027 年 1 月底截稿）不建議當主投。

---

## 5. 系統與實驗設計

### 5.1 系統架構（Mathesis v1）

```
題目 ──► 底層證明器 M（DeepSeek-Prover-V2-7B，whole-proof 取樣，k 次）──► Lean 驗證（lake env lean / Pantograph）
              ▲                                         │ 錯誤訊息、未解 goal、狀態
              │                                         ▼
        重構後的狀態 ◄── 算子 R（LLM 提案 → elaboration 過濾 → 輔助引理遞迴證明）
                                     ▲
                       控制器：impasse 偵測 + 算子選擇
```

- **底層證明器**：DeepSeek-Prover-V2-7B（`mlx-community/DeepSeek-Prover-V2-7B-4bit`，MLX，CoT）。
  - 原計畫要求非 CoT；v1.1 改為 CoT，理由見 §2.3。
  - 只有在 G0 判定 CoT 的有效證明率太低（例如大量截斷、輸出無法驗證）時，才換成其他證明器。
  - 權重授權欄位為空，發布任何衍生資料前要先確認授權（§11）。
- **Impasse 特徵**（只在 calibration split 上預先決定並校準）：連續失敗次數、錯誤類型的熵與重複率、未解 goal 的停滯程度（goal 狀態雜湊）、已用預算比例（修掉現有實作中的單調偏誤）。
- **算子**（衝刺版做 2 個）：
  - `AddSubgoal`：提一個 `have` 中間引理，分別證明引理與剩下的部分。
  - `AddSymbol`：引入 witness 或輔助函數（`use`、`set`、`let`）。
  - 長期版再加 `Generalize`、`Reformulate`。
  - 每個算子都有專屬 prompt、型別文法過濾和 Lean elaboration 檢查。
- **算子選擇**：LinUCB 或 Thompson sampling，以 impasse 特徵為 context。衝刺版若時間不夠，先用 RandomCandidateSelector（B4）。

### 5.2 Baseline（全部等算力：LLM 生成 token 數加 Lean 呼叫次數相同，另報 wall-clock）

| 代號 | 說明 | 檢驗什麼 | 衝刺版 |
|---|---|---|---|
| B0 | 底層證明器 pass@k | 重構本身有沒有用 | ✅（已有數字） |
| B1 | 同一算子庫，固定排程（每 N 次失敗觸發） | **H1：何時重構** | ✅ |
| B2 | 同一算子庫，隨機觸發（觸發次數期望值與 Mathesis 相同） | **H1：何時重構** | ✅ |
| B3 | 一開始就分解（子目標分解式） | 先分解 vs 遇到僵局才重構 | 可選 |
| B4 | impasse 觸發，但隨機選算子 | **H3：選哪個算子** | ✅ |
| B5 | 模板算子（現有的 TemplateHave） | LLM 提案的必要性 | 可選 |
| UB | Oracle 輔助提示（hint-gap 的上界） | 天花板 | ✅ |
| Sym | 現有的 BFS 加 Lean automation（`aesop`、`nlinarith` 等） | 符號 baseline | 可選 |

### 5.3 Benchmark 建構流程

1. **候選池**：
   - miniF2F 子集（來源與授權見下方附註）；
   - 新題組 `lean_hard`（工作樹 89 題，已 Lean 驗證；2026-11-04 的陳述審查發現 1 組代數等價重複與 2 題近似重複，已在 `audit_notes` 註記，凍結題庫時移除）；
   - 擾動題與新造題（改常數、改結構，以控制污染）；
   - 舊 `lean_pilot` 50 題：test split 已被 B0 使用，不能再進 test，只作為 calibration 或 dev 的參考。
2. **涵蓋家族**（衝刺版 6–8 個）：不等式（AM-GM、Cauchy 型）、自然數與整除、歸納、集合與邏輯、代數恆等式、自訂遞迴定義。
3. **計算 Gap_B**：B0 證明器在原版與提示版上各取樣 k=8。依 Gap 門檻分出 insight 題，並為每題配一題 routine 對照（陳述長度、家族、原版解題率相近）。
4. **污染審計**：Mathlib 子字串比對（既有腳本，已修掉短陳述略過的 bug）；對 miniF2F 做重疊檢查；做 memorization probe；比較原版與擾動版的效能落差。
   - 現況：`lean_hard` 89 題在主體比對中沒有非泛用命中；名稱片段命中 10 題（皆為舊 38 題），經檢視皆為雜訊。
   - 注意：這是啟發式篩檢，不是污染的證明。我自己標的 contamination 等級比篩檢更保守。
5. **Split**：
   - calibration 20 題（調 impasse 門檻）；
   - dev 30 題（開發算子 prompt）；
   - **test ≥50 題（預註冊後只跑一次）**，衝刺版的規模低於長期版的 ≥100，必須在結果中報告 CI。
   - operator-design split：test 中有些家族不出現在 dev。
6. **標註（LLM 輔助，揭露）**：2026-11-03 確認沒有第二位人工標註者，改為以下流程：
   - **標註內容**：每題「是否需要非平凡輔助構造」、難度 1–5、與 Mathlib 的相似度（none／variant／exact）。
   - **標註者**：與證明器不同家族的 LLM（候選：Claude 系列，透過 API；需要你同意，見 §10 第 3 項）。
   - **穩定性**：每題標註跑 3 次，取多數決，並記錄三次一致率。所有提示與回應全文存入 `benchmark/annotations/`。
   - **作者核對**：作者以盲標方式標註 20 題（分層抽樣），報告 LLM 與作者的一致性（Cohen κ），以及 LLM 自身的三次一致率。
   - **主要結論不依賴 LLM 標註**：insight／routine 配對以 hint-gap 為準；LLM 標註只用於描述性統計與一致性檢查。另報告去掉 LLM 過濾後的結果（敏感度分析）。
   - **論文揭露**：方法與限制段寫明「標註由 LLM 輔助、作者抽樣核對、未雇用獨立人工標註者」，並釋出 prompt 與標註檔。

**miniF2F 來源附註（2026-11-03 查證，尚未下載）**：

- 原始 benchmark：`openai/miniF2F`（Zheng, Han, Polu 2021，arXiv:2109.00110）。
- Lean 4 版本有兩個候選：
  - `yangky11/miniF2F-lean4`，最新版本對應 Lean v4.20.0（本專案為 v4.35.0，需要 port）；
  - `google-deepmind/minif2f`，Lean 4 fork，有修正形式化與非形式描述。
- **授權**：`yangky11/miniF2F-lean4` 的 LICENSE 尚未確認；上游 OpenAI 的 Lean 部分被描述為 Apache-2.0，但這是搜尋結果的說明，尚未親自核對。使用前要打開 LICENSE 檔確認。
- **下載**：尚未下載。下載前會先回報檔名、來源與大小，並取得你同意。

### 5.4 算力預估（**僅 Mac M5 / 24GB**，2026-11-02 決定：不動用伺服器與桌機）

- 底層證明器：DeepSeek-Prover-V2-7B（MLX 4-bit，`mlx-lm` 已安裝於 conda 環境 `mathesis`）。
- 實測吞吐量：單流約 23 tok/s；batch 4 約 94 tok/s；batch 8 約 95 tok/s（總吞吐量）。
- 已完成的 B0 實測：舊題組 50 題 × k=8，wall-clock 4,793 秒（約 80 分鐘）。新題組 38 題 × k=8 也已完成，耗時以其 manifest 為準。
- 衝刺版規模：benchmark 80–100 題 × k=8，原版與提示版各跑一次，加上 dev 與 test 的 Mathesis 與 baseline；總量依 W1–W2 的實測再估，不先估死。
- Lean 驗證吃 CPU；`lean/.lake` 已建好（7.2 GB，已排除於 git）。
- 所有 seed 固定；每個 benchmark 結果註明 M5、MLX、耗時（依 AGENTS.md）。

---

## 6. 時程（2026-11-03 → 2027-01-08，衝刺版）

| 週 | 日期 | 工作 | 產出 | 門檻 |
|---|---|---|---|---|
| **W1** | 11/03–11/09 | 本文件更新；gated 測試重跑；miniF2F 經你同意後下載、port 到 v4.35、子集 pass@8；hint-gap 試測（`lean_pilot` 25 題已完成；`lean_hard` 40 目標進行中） | 測試結果、G0 子集數字、hint-gap 初步分布 | **G0**：子集可正常執行，CoT 有效證明率可接受（若太低，改換證明器，重算時程） |
| **W2–3** | 11/10–11/23 | benchmark v1：擴到 80–100 題；hint-gap（k=8，原版與提示版）；routine 配對；LLM 標註與作者盲標 20 題 | `benchmark/v1/`、標註檔、一致性報告 | **G1**（11/23）：insight ≥40 題、routine 配對 ≥25 對（門檻為初步設定，若 Gap 分布不足就調整並記錄在 §11） |
| **W4–5** | 11/24–12/07 | Mathesis v1（衝刺版）：LLM 提案的 AddSubgoal、AddSymbol；型別與 elaboration 過濾；impasse 特徵在 calibration 上校準；接 RandomCandidateSelector；實作 B0、B1、B2、B4；只跑 calibration 與 dev | dev 結果、校準報告 | **G2**（12/07）：dev 上 Mathesis 對 B1／B2 有可見差距。若沒有，H1 轉為負面結果路線 |
| **W6** | 12/08–12/14 | 凍結算子庫、特徵、門檻、split、預算；撰寫並提交 OSF 預註冊（H1、H2） | 預註冊連結 | 預註冊完成，之後不改 |
| **W7** | 12/15–12/21 | test 只跑一次（compute-matched）；bootstrap CI；mixed-effects 分析 | 主表 | **G3**（12/21）：H1 判定 |
| **W8** | 12/22–12/31 | 一個預算的消融；個案分析；圖表；Related Work 定稿 | 圖表、消融表 | 12/31 之後不再改實驗（假期緩衝） |
| **W9** | 2027-01-01–01-07 | 申請書定稿（預印本為申請後的選項，見 v1.2）；reproducibility（manifest、版本、程式碼）；單位與作者確認 | 草稿與程式碼包 | 01-07 送你審閱 |
| **截止** | **2027-01-08** | RIKEN CBS 申請截止 | — | — |

**衝刺版砍掉的範圍**（任一關延誤就先砍這些）：

- 1× 與 4× 以外的預算掃描、16× 全部取消；
- PutnamBench 外部子集；
- B3、B5、Sym（可選，時間夠才做）；
- minimal-background track；
- 人類研究；
- Y2 的鞏固與類比。

**平行工作流**：

| 工作流 | 角色 | 內容 | 依賴 |
|---|---|---|---|
| A 基準題組 | implementer（寫題與 hint-gap 程式）、qa-tester（驗證） | 擴題、Gap、配對、污染審計、LLM 標註流程 | 無，可立即開始 |
| B 控制層 | implementer；impasse 校準的問題用 debugger | 特徵、算子、selector、B1／B2／B4 | 需要 A 的 calibration 與 dev |
| C 量測與測試 | qa-tester | gated 測試重跑、G0、manifest 檢查 | 無，可立即開始 |
| D 文獻與新穎性 | researcher | 精讀 ProofEvolve、HAGeo（§9.2），改寫 Related Work | 結論要在 G2 前完成，否則 H1 切入角度不定 |

**主要風險**：

| 風險 | 處理 |
|---|---|
| H1 不成立 | 以 benchmark 與負面結果寫成預印本 |
| CoT 證明器有效輸出太少 | G0 判定，必要時換證明器，並重算時程 |
| test ≥50 的統計力不足 | 預註冊寫明效果量門檻；報告 CI；不宣稱小於 CI 的差距 |
| ProofEvolve 已做觸發時機消融 | D 工作流的結論調整 H1 的切入角度 |
| 假期（12/24–1/1） | 12/31 凍結實驗 |
| LLM 標註偏差 | 揭露；作者盲標 20 題核對；敏感度分析 |

**長期版時程（原 v1.0，保留）**：P0 基礎（11 月）→ P1 benchmark 150–200 題與 OSF 預註冊（12 月底）→ P2 系統（1 月）→ P3 實驗（2 月–3 月中，H1 判定、決定主會或 D&B）→ P4 寫作（3 月下旬–5 月中）。若 2027-01-08 之後仍要投 NeurIPS 2027 主會，就以長期版為準擴充。

---

## 7. 論文大綱（9 頁加附錄）

1. **Introduction**：AlphaProof 與 DeepSeek-Prover 之後，瓶頸在輔助構造；介紹 construction gap 與「何時重構」的問題；列出貢獻。
2. **Related Work**：LLM 證明器、子目標分解（DSP、LEGO-Prover、DeepSeek-V2）、proof planning 與 failure-driven lemma speculation（Bundy、Ireland & Bundy）、Soar 的 impasse-driven subgoaling、insight 的認知科學（Ohlsson、Knoblich）。
3. **Problem Formulation**：預算、censored cost、Gap 的定義、insight gain。
4. **Construction-Gap Benchmark**：建構流程、統計、污染審計、LLM 標註與揭露。圖 1：各證明器在 insight 與 routine 題上的 Gap 分布。
5. **Mathesis**：impasse 偵測、算子、選擇策略。圖 2：架構圖。
6. **Experiments**：主表（H1–H3）；圖 3：solve-vs-cost Pareto（H4，衝刺版為子集）；消融；限制與偏差（CoT 證明器、LLM 標註、test 規模）。
7. **Analysis**：僵局軌跡個案、失敗分類、算子使用分布。
8. **Limitations & Broader Impact**。
- 附錄：預註冊對照、完整超參數、datasheet、算力報告、prompt 全文、標註全文。

---

## 8. 分工與執行規範

| 類別 | 負責 | 備註 |
|---|---|---|
| 假設、kill criteria、統計判定、benchmark 收錄標準、論文論證 | **主模型（不得下放）** | 依 AGENTS.md 科學規範 |
| 管線、算子、baseline、測試 | `implementer`（多檔案時用 Sonnet）、`qa-tester` | AGENTS.md 寫的 `muse-contributor` 在這台機器上不存在，改用 `implementer`。每次委派都要附絕對路徑、驗收命令和不可違反的規則 |
| 程式碼審查 | `code-reviewer` | 每次非瑣碎變更後 |
| 文獻核對、新論文追蹤 | `researcher` 或 Haiku | 結論必附來源 |
| LLM 標註 | 主模型設計 prompt 與抽樣；標註由 API 完成 | 作者盲標 20 題不委派 |
| 驗收 | **主模型自己重跑驗收命令** | 不只憑 subagent 的回報採信 |

不可違反的規則：test split 在預註冊前不能碰；OracleHave 只當上界，不能當方法；不提交 `literature/**/*.pdf`、`data/raw`、模型權重；miniF2F 等外部資料下載前要先取得同意。

---

## 9. 文獻與理論依據

PDF 存在 `literature/`（已加入 `.gitignore`），索引見：

- `literature/ml/INDEX.md`、`refs.bib`：ATP 與 LLM 證明器；
- `literature/cogsci/INDEX.md`、`refs.bib`：insight、impasse、proof planning；
- `literature/verify/VERIFICATION.md`：`research-design.md` 中可疑 2026 文獻的核對結果。

理論骨架（論文 §2 與 §3 要用的四條線）：

1. **Insight 的表徵改變理論**：Ohlsson 1992、Knoblich et al. 1999、Öllinger et al. 2014。這是「僵局觸發重構」的認知依據。
2. **Impasse-driven subgoaling**：Soar（Laird, Newell & Rosenbloom 1987）。這是 AI 史上最直接的前例，論文**必須**討論它，以便和它區隔。
3. **Failure-driven proof planning**：Bundy 1988、Ireland & Bundy 1996（productive use of failure，lemma speculation）、Melis 1995。這是「從失敗中生成輔助引理」的直接前例，也是新穎性論證的關鍵對手。
4. **LLM 證明器與子目標分解**：DSP、LEGO-Prover、DeepSeek-Prover-V2、Goedel-Prover-V2。它們一律先分解，不靠僵局決定何時分解。

> 投稿前，所有 2026 年的文獻都要逐條核對作者、venue 與版本，核對不到的一律刪除。

### 9.1 文獻核對結果（2026-11-02，主 session 已用 arXiv API 抽查 4 篇標題）

- 全部確有其文，但有 3 處要修正：
  - 「Danek & Salvi 2023」的作者其實是 **Wiley & Danek**（*Nat Rev Psychol* 3:42–55，Crossref 已確認）。
  - QuickSpec 是 **TAP 2010**，不是 2013。
  - AutoformBench 查不到 NeurIPS workshop 的出處。
- Doulfoukar, Pezzulo & Stuyck 2026 **確實發表在 PBR**（doi:10.3758/s13423-026-02983-8，2026-09-17；主 session 已用 Crossref 確認）。核對 agent 原本說「只有預印本」，是錯的。
- Öllinger et al. 2014 發表在 *Psychological Research*，不是 *Frontiers*。
- HAGeo 不是一篇獨立論文，而是 Duan et al.（arXiv:2512.00097，ACL 2026）提出的方法名稱。
- 詳細內容見 `literature/verify/VERIFICATION.md`。

### 9.2 新穎性威脅（必讀全文，並寫進 Related Work 做區隔）

| 論文 | 重疊之處 | 我們的區隔 |
|---|---|---|
| **ProofEvolve**（arXiv:2608.26334） | 由神經模型提出「變異算子」（分解、修復、schema 重組），Lean 驗證，形成 proof DAG | 它沒有「何時重構」的控制，算子是持續演化的。我們的核心是**僵局觸發**加上**等算力的觸發時機消融**。應當成 baseline，或至少在討論中正面比較 |
| **HAGeo**（Duan et al. 2512.00097） | 啟發式輔助構造，幾何領域 | 我們做的是 Lean 的通用代數、數論與分析，而且有可學習的觸發機制 |
| **AMBER / Construction-Verification**（2602.01291） | 「先構造、再驗證」的 benchmark | 它談的是應用數學的解答合成；我們談的是證明中的輔助構造，加上 hint-gap 的操作化 |
| **NanoProof**（2610.11605） | 小算力、可重現的 Lean 證明器 | 可以當底層證明器的替代候選（完全開源、算力低）。目前主線仍是 DeepSeek-Prover-V2 |
| DeepSeek-Prover-V2、DSP、LEGO-Prover | 子目標或引理分解 | 它們一律先分解；我們的 B3 baseline 就是直接檢驗這個差別 |
| Li et al. 2026（arXiv:2604.16278） | 把缺乏「insight」列為 LLM 定理證明的瓶頸，但做的是非形式證明 | 我們在 Lean 中用 hint-gap 做形式化、可量測的定義。它的存在支持我們的動機，引用時要做區隔 |

### 9.3 文獻庫現況

| 資料夾 | 已下載 | 只有 metadata | 找不到 |
|---|---|---|---|
| `literature/ml/` | 32 | 0 | 0 |
| `literature/cogsci/` | 7 | 19 | 3（Ohlsson 1992、Newell & Simon 1972、Lenat AM） |
| `literature/verify/` | 9 | — | — |

**需要你透過學校圖書館手動取得**（付費牆或擋爬蟲；理論章節的核心文獻）：Knoblich et al. 1999（JEP:LMC）、Ohlsson 1992、Öllinger et al. 2014、Laird, Newell & Rosenbloom 1987（Soar）、Ireland & Bundy 1996（JAR）、Bundy 1988（Edinburgh ERA 有公開版）、Melis 1995（IJCAI 公開）、Kounios & Beeman 2014、Friston et al. 2017（UCL Discovery 有公開版）。

**行動**：W1 由 D 工作流精讀 ProofEvolve 與 HAGeo。若 ProofEvolve 已經做了觸發時機的消融，就要調整 H1 的切入角度。

---

## 10. 需要你決定或提供的事

1. **1/8 截止的成果形式**（最重要）：我假設是「申請書草稿 ＋ 可重現程式碼與結果」（v1.2 已確認交付物為申請書）。若 RIKEN CBS 的格式或字數與此不同，請告訴我，時程會變。
2. **miniF2F 下載同意**：請同意下載 `yangky11/miniF2F-lean4` 或 `google-deepmind/minif2f` 其中之一（我建議後者，它是 Lean 4 fork，並有修正）。下載前我會先回報檔名、來源與大小。
3. **LLM 標註器**：請決定用哪個模型與 API。這會把題目陳述送到外部服務；題目是公開 benchmark 的內容，但仍屬外部傳輸，需要你同意並提供 API 金鑰。
4. **作者與單位**：預印本與 OSF 預註冊要用 Master Program 還是 RIKEN CBS？兩者要和 RIKEN CBS 申請的寫法一致。
5. **預印本發布**：需要你明確同意。arXiv 也需要有 endorsement 的帳號，請確認。
6. **版本控制**：`docs/paper-plan.md` 已在 `f84a92a` 提交；程式與 benchmark 的其餘變更待 commit。

---

## 11. 目前狀態（2026-11-03）

| # | 項目 | 狀態 |
|---|---|---|
| 1 | 初始 commit | ✅ `debfb76`（95 個檔案，PDF 與 `.lake` 排除） |
| 2 | 實驗管線：`runs/<時間>_<指令>/` 含 `manifest.json`、`results.jsonl`、`summary.json` | ✅ 已用於舊題組與新題組的完整 B0 run |
| 3 | 修 impasse 單調 budget 偏誤；`choose()` 可插拔（`RandomCandidateSelector`） | ✅ 已完成；**副作用**：pilot 上 `impasse_count` 全為 0，權重待校準 |
| 4 | 修 `contamination_audit.py`；支援 `--benchmark` | ✅ 舊題組 50/50；新題組 38/38 已檢查 |
| 5 | gated Lean／Pantograph 測試 | ✅ review 前全部通過；review 修正後尚未重跑（W1） |
| 6 | 底層證明器 DeepSeek-Prover-V2-7B（MLX 4-bit） | ✅ 可載入；batch 8 約 95 tok/s。G0（miniF2F 子集）尚未做（W1） |
| 7 | review 的 12 點 | ✅ 修了 8 點；其餘見下 |
| 8 | 新 benchmark `lean_hard`（38 題，`dev`） | ✅ 全部 Lean 驗證通過；commit `b582c58` |
| 9 | B0 舊題組（`lean_pilot` 50 題，run `runs/20261102T171018Z_b0`；MLX 4bit 後端，run 不在本 checkout 中） | pass@1 0.907、pass@8 1.000（飽和，不再用於區分方法） |
| 10 | B0 新題組（`lean_hard` 38 題，run `runs/20261102T184627Z_b0`；MLX 4bit 後端，run 不在本 checkout 中） | pass@1 0.819、pass@8 0.895；4 題完全失敗，皆為真實 Lean 錯誤（Mathlib 名稱錯誤、omega、unsolved goals）。注意：部分失敗來自 Mathlib 名稱記憶，與數學難度混淆 |
| 11 | hint-gap 測量 | ✅ 已實作（`hint-gap` 指令）；`lean_pilot` 25 題流程試測完成（只作參考）；`lean_hard` 40 目標進行中，完成前不引用（見 §11.1） |
| 12 | Mathesis 控制層（LLM 算子、校準） | ❌ 未做（W4–5） |
| 13 | OSF 預註冊 | ❌ 未做（W6） |
| 14 | miniF2F 來源 | ✅ 已查證來源與版本；授權待確認；**尚未下載**（§10 第 2 項） |
| 15 | 文獻精讀（ProofEvolve、HAGeo） | ❌ 未做（W1，D 工作流） |
| 16 | judge v2（2026-11-04，僅 phase1 worktree，未 commit） | forbidden token 改為先剝除證明文字的註解再查（未閉合的區塊註解視為 forbidden；Lean 輸出仍逐字查）；新增 `lean_crash`（子行程非零退出且無診斷）；Lean 子行程沙箱：環境變數白名單（PATH、ELAN_HOME、LANG、LC_ALL、TMPDIR，HOME 為私有暫存目錄），`unshare -rn` 網路隔離（由 `MATHESIS_LEAN_SANDBOX` 控制，預設 auto）。**v1 判定的既有 run（含 §11.1 的四個 Linux run，以及 Mac/MLX 的兩個 run）的 forbidden 判定不得以 v2 重新解讀；若要比較，需以 v2 重新驗證候選檔。** |
| 17 | search.py 預算邊界 L-1 漏判 | 已修（僅 phase1 worktree，未 commit）：預算耗盡時，若佇列中已有已解出的狀態，現在回傳成功。修正前的 lean-bench 與 pilot 結果，在預算邊界上的 solve rate 不可與修正後直接比較。 |

### 11.1 Linux transformers bf16 的 run（本機 `runs/`）

數字取自各 run 的 `summary.json`。

| run | 題組 | 題數 | pass@1 | pass@8 | 狀態與用途 |
|---|---|---|---|---|---|
| `20261103T091021Z_b0` | `lean_hard` 舊版 | 38 | 0.826 | 0.921 | 完成。是 `20261103T122531Z_b0` 的子集重複（題名全部包含於其中），分析以 `122531Z` 為準 |
| `20261103T122531Z_b0` | `lean_hard` | 89 | 0.737 | 0.820 | 完成。分析以此 run 為準 |
| `20261103T101932Z_hint-gap` | `lean_pilot` | 25 | — | — | 完成，**只作流程試測**（`lean_pilot` 的 test split 依 §5.3 只作參考）。mean gap +0.010，95% CI [0.000, 0.025]；25 題中 21 題的 plain pass@1 已為 1.0（天花板） |
| `20261103T154014Z_hint-gap` | `lean_hard` 40 個目標 | 40 | — | — | **執行中**，完成前不引用。注意：此 run 送出的 `lean_ineq_cube_sum_zero_sixth` hint 寫 `4*((x-y)(2x+y)(x+2y))^2`，代數上應為 `2*`（x=1, y=0 時兩側皆為 8）；`problems.json` 已於 2026-11-04 修正，但此 run 用的是錯誤係數。部分 hint 含策略性內容（`reference_proof` 中的代數提示），此 run 的 Gap 是否保留為正式數據，待作者決定 |

**已知問題**：

- `RandomCandidateSelector` 尚未接進任何 config（B4 要用，屬 W4–5）。
- `FROZEN_IMPASSE_THRESHOLD = 0.3` 是針對舊分數凍結的，要在 calibration 上重新校準。
- `generic_match` 只看字元長度，規則過於粗略。
- `default_repo_root` 在兩處各定義一次，非 editable 安裝會指錯位置。
- 權重授權欄位為空（`mlx-community/DeepSeek-Prover-V2-7B-4bit`）。
- 環境：conda `mathesis`（`environment.yml`，Python 3.13，含 `mlx-lm`、`pytest`），依 AGENTS.md 建立，不使用 base。
