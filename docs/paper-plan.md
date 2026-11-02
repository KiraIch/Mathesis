# Mathesis 投稿計畫 v1.0（2026-11-02）

> 用途：把 Mathesis 從 RIKEN 研究計畫書的 pilot，推進成一篇頂級會議論文。
> 依據：2026-11-02 由三個 Haiku agent 完成的唯讀審計（程式碼、Lean 與 benchmark、`docs/research-design.md`），測試結果已由主 session 重跑確認。
> 與 `docs/research-design.md` 的關係：該文件仍是博士計畫的長期藍圖。本文件只處理「第一篇頂會論文」，並在必要處修正它（見 §2.3）。

---

## 0. 結論先行

1. **以目前的狀態，這個專案投不了頂會。** 框架是真的程式碼，但已驗證的只有 mock 後端。50 題 benchmark 接近教科書等級，沒有任何真實 Lean 實驗結果，也沒有 LLM。算子是針對題目手寫的模板，控制器只取第一個候選（詳見 §1）。
2. **核心想法值得做，但要換戰場。** 我們不再和 SOTA 證明器比誰的解題率高，改為回答一個更尖銳、也比較新的問題：

   > **LLM 證明器在需要「輔助構造」的定理上卡住時，由「僵局（impasse）」觸發、型別化的表徵重構，能否在等算力條件下，勝過同一套算子用固定排程或隨機觸發的版本？**

3. **主投 NeurIPS 2027 主會（截稿約 2027 年 5 月中，以官方公告為準）。** 另有一篇保底論文已設計好：若 H1 失敗，就轉投 NeurIPS 2027 Datasets & Benchmarks track，主打「構造缺口（construction gap）」benchmark 與分析。不論 H1 成敗，都會產出一篇論文。
4. 剩約 **28 週**，排成 5 個階段，中間有 4 個 go/no-go 門檻（§6）。

---

## 1. 現況診斷（審計證據）

| 面向 | 現況 | 對投稿的影響 |
|---|---|---|
| 程式框架 | 4,191 行 Python，其中 search/controller/operators/impasse 是真實程式碼。`157 tests OK (skipped=10)`：主 session 已用 `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests` 重跑確認 | 可沿用，不用重寫 |
| Lean 環境 | Lean v4.35.0，Mathlib v4.35.0 已建好（8,643 個 olean），Pantograph v0.3.19 的 repl 已編譯 | 環境就緒，這是最大的資產 |
| 真實 Lean 路徑 | SubprocessLeanBackend 與 PantographBackend 的程式碼都在，但 10 個 gated 測試從沒跑過 | 第一週就要打通 |
| 實驗結果 | **零**。CLI 只印到 stdout，沒有 results、manifest、seed 紀錄 | 必須補上實驗管線 |
| Benchmark | 50 題（insight 25／routine 25，test 40／calibration 10）。40 題是教科書題，31 題污染風險高。真正需要非平凡輔助構造的約 6 題 | 要整套重建 |
| 算子 | AddSubgoal（子式枚舉）、TemplateHave（手寫 sq_nonneg 模板，疑似過擬合）、OracleHave（直接用參考解答，只能當上界）、AddSymbol（mock 下永遠失敗） | 需要換成 LLM 產生、型別過濾的算子 |
| 控制器 | 四個控制器的 `choose()` 都是 `pick_first`（已確認，見 `src/mathesis/controller.py:34`）。impasse 分數含單調遞增的 budget 項，搜尋後段無論如何都會觸發 | 「impasse 驅動」目前名不符實 |
| Baseline | 缺：等算力控制、隨機選候選、LLM proposer、pass@k | H1 無法檢驗 |
| LLM | 完全沒有 | 2026 年的頂會審稿人一定會問 |
| 版本控制 | git 沒有任何 commit | 要先 commit 以保留 provenance（待你同意） |
| 文獻 | 設計文件有約 10 條 2026 文獻疑似無法驗證（ProofEvolve、NanoProof、AutoformBench、Doulfoukar 2026 等） | 正在核對，見 §9 |

---

## 2. 研究定位

### 2.1 為什麼不能正面和 SOTA 比解題率

DeepSeek-Prover-V2、Kimina、Goedel-Prover-V2、Seed-Prover 這類系統，在 miniF2F 上的表現靠的是大規模 RL 與龐大算力。一個人加一台 M5 加小型 GPU 叢集，在「總解題率」上不可能贏。審稿人也不會接受「我們打敗了 BFS」這種結論。

### 2.2 我們能贏的地方：控制層，而不是模型

貢獻放在**證明器之上的控制層**。底層模型固定用一個公開的證明器，比較的是：**什麼時候重構、用哪個算子重構**。這是乾淨的消融問題，算力需求可以控制，結論也不依賴我們擁有最強的模型。

### 2.3 對 `research-design.md` 的修正

| 原設計 | 修正 | 理由 |
|---|---|---|
| 模板與枚舉產生候選，LLM 可選 | **LLM 依失敗軌跡提案，再經 Lean 型別與 elaboration 過濾**；模板只當消融 | 模板會被批評是答案 oracle，也已觀察到過擬合 |
| BFS 是底層搜尋 | 底層換成公開 LLM 證明器（whole-proof 生成），BFS 保留成符號 baseline | 與 2026 年的領域現況對齊 |
| 15–20 題 pilot | 150–200 題，並分出獨立的 calibration、dev、test split | 15–20 題撐不起統計結論，也無法再切出 calibration set |
| 「insight 題」由人工標註 | **用 hint-gap 做操作化定義**（§3.2），人工標註降為輔助 | 客觀、可重現；也解決單人無法做雙人標註 κ 的問題 |
| 人類研究放在 Y2–Y3 | 主論文不做，認知科學只當動機與詮釋框架 | 範圍控制；AGENTS.md 規定，認知建模的主張必須有行為資料 |

---

## 3. 論文核心

### 3.1 暫定題目

- *When to Restructure: Impasse-Triggered Auxiliary Construction for LLM Theorem Provers*
- 備選：*Mind the Construction Gap: Measuring and Closing the Auxiliary-Construction Bottleneck in Formal Theorem Proving*

### 3.2 關鍵操作化：construction gap（hint-gap）

對題目 \(p\)、固定的證明器 \(M\)、固定預算 \(B\)：

\[
\mathrm{Gap}_B(p) = \Pr[\text{solve } p \mid B] \text{ 提示版} - \Pr[\text{solve } p \mid B] \text{ 原版}
\]

「提示版」是在題目前面加上參考證明中的輔助構造（`have` 陳述、witness、輔助函數），**只給陳述，不給證明**。

- **Insight 題**：Gap 大（例如 ≥0.3），而且原版解題率低。
- **Routine 對照題**：統計結構與原版難度相近，但 Gap ≈ 0。

好處有三：把「需要頂悟」變成可量測的量；直接量化 LLM 證明器的瓶頸，本身就是一個發現；也讓 OracleHave 有了正當角色，作為上界。

### 3.3 預期貢獻（論文 §1 的寫法）

1. **Construction-gap benchmark**：150–200 題，含 insight 與 routine 配對、擾動版本與污染審計。首次系統性量化 SOTA 開源證明器的輔助構造瓶頸。
2. **Mathesis 控制層**：impasse 偵測（根據 Lean 錯誤軌跡、狀態停滯、重複率）加上型別化重構算子（AddSubgoal、AddSymbol、Generalize、Reformulate）加上 bandit 式算子選擇。可以接到任何證明器上。
3. **等算力的因果消融**：「何時重構」對上固定排程與隨機觸發；「選哪個算子」對上隨機算子；「是否需要重構」對上 pass@k。
4. **可審計的僵局與重構軌跡**：用來做個案研究與失敗分類。

### 3.4 假設與否證條件（**跑 test split 前要在 OSF 預註冊**）

| 編號 | 假設 | 主要指標 | 否證條件 |
|---|---|---|---|
| H1 | 在 insight split 上，impasse 觸發的重構勝過同一算子庫的固定排程與隨機觸發（觸發次數期望值相同） | 預算 B\* 下的解題率；用 mixed-effects logistic 迴歸，題目與家族為隨機效應 | Mathesis 減去 max(B1, B2) 的 95% CI 包含 0 |
| H2 | 重構帶來的增益集中在 insight 題（insight × 方法交互作用） | 交互作用項 | 交互作用的 CI 包含 0 |
| H3 | 依失敗軌跡選算子，勝過隨機選算子 | 解題率 | 與 B4 的差距 CI 包含 0 |
| H4 | 在 1×、4×、16× 預算下，Mathesis 都在 solve-vs-cost Pareto 前緣上 | 曲線 | 有任一預算點被 pass@k 支配 |

- Seed 不算獨立樣本。用 Holm–Bonferroni 校正，paired bootstrap 當輔助。
- **H1 是 kill criterion**：H1 失敗就切到保底論文（§4）。這個判定由主模型做，不下放給 subagent。

---

## 4. 投稿策略

| 優先序 | 目標 | 截稿（約，以官方公告為準） | 條件 |
|---|---|---|---|
| 主投 | **NeurIPS 2027 主會** | 2027 年 5 月中 | H1 成立 |
| 保底 | **NeurIPS 2027 Datasets & Benchmarks** | 約同期 | H1 不成立；論文改以 construction-gap benchmark 與「LLM 證明器的構造瓶頸」分析為主，負面結果也寫進去 |
| 早期回饋 | ICML 2027 的 AI for Math 類 workshop，或 NeurIPS 2027 的 MATH-AI workshop | 2027 年春夏 | 送 pilot 結果，風險低 |
| 下一輪 | ICLR 2028 | 約 2027 年 9–10 月 | 被拒或需要更多實驗時 |
| 期刊延伸 | TMLR；若補上人類研究則投 *Cognitive Science* | 不限 | 加入人類僵局資料以後 |

ICML 2027（約 2027 年 1 月底截稿）時間太緊，**不建議**當主投。

---

## 5. 系統與實驗設計

### 5.1 系統架構（Mathesis v1）

```
題目 ──► 底層證明器 M（whole-proof 取樣，k 次）──► Lean 驗證（Pantograph / LeanInteract）
              ▲                                         │ 錯誤訊息、未解 goal、狀態
              │                                         ▼
        重構後的狀態 ◄── 算子 R（由 LLM 提案 → elaboration 過濾 → 輔助引理遞迴證明）
                                     ▲
                       控制器：impasse 偵測 + 算子選擇（contextual bandit）
```

- **底層證明器**：主實驗用**非 CoT** 的開源 7–8B 證明器（候選：DeepSeek-Prover-V1.5-RL、Goedel-Prover-V1）。輸出短，吞吐量高。另用一個 CoT 證明器（Goedel-Prover-V2-8B 或 Kimina-Distill-8B）在子集上做穩健性檢查。W1 量測吞吐量後再定案。
- **Impasse 特徵**（只在 calibration split 上預先決定並校準）：連續失敗次數、錯誤類型的熵與重複率、未解 goal 的停滯程度（Pantograph 的 goal 狀態雜湊）、已用預算比例（修掉現有實作中的單調偏誤）。
- **算子**（MVP 做 2 個，完整版 4 個）：
  - `AddSubgoal`：提一個 `have` 中間引理，分別證明引理與剩下的部分。
  - `AddSymbol`：引入 witness 或輔助函數（`use`、`set`、`let`）。
  - `Generalize`：加強歸納假設或一般化陳述。
  - `Reformulate`：變數代換或正規化（例如 WLOG、取對數、平移）。
  
  每個算子都有專屬 prompt、型別文法過濾和 Lean elaboration 檢查。
- **算子選擇**：LinUCB 或 Thompson sampling，以 impasse 特徵為 context。

### 5.2 Baseline（全部等算力：LLM 生成 token 數加 Lean 呼叫次數相同，另報 wall-clock）

| 代號 | 說明 | 檢驗什麼 |
|---|---|---|
| B0 | 底層證明器 pass@k | 重構本身有沒有用 |
| B1 | 同一算子庫，固定排程（每 N 次失敗觸發） | **H1：何時重構** |
| B2 | 同一算子庫，隨機觸發（觸發次數期望值與 Mathesis 相同） | **H1：何時重構** |
| B3 | 一開始就分解（DSP 或 DeepSeek-V2 式的子目標分解） | 先分解 vs 遇到僵局才重構 |
| B4 | impasse 觸發，但隨機選算子 | **H3：選哪個算子** |
| B5 | 模板算子（現有的 TemplateHave） | LLM 提案的必要性 |
| UB | Oracle 輔助提示（hint-gap 的上界） | 天花板 |
| Sym | 現有的 BFS 加 Lean automation（`aesop`、`nlinarith` 等） | 符號 baseline |

### 5.3 Benchmark 建構流程

1. **候選池**：miniF2F-test、PutnamBench 中參考證明含輔助構造的題目，加上現有 50 題中的約 6 題，再加上擾動與新造的題目（改常數、改結構，以控制污染）。
2. **涵蓋家族**（目標 8–10 個）：SOS 與平方 witness 的不等式；代換後套 AM-GM／Cauchy；數論的模數與不變量論證；歸納加強；伸縮和與輔助序列；函數方程代入；多項式輔助構造；存在性 witness。
3. **計算 Gap_B**，用 B0 證明器在原版與提示版上各取樣 k 次。依 Gap 門檻分出 insight 題，並為每題配一題 routine 對照（陳述長度、家族、原版解題率相近）。
4. **污染審計**：Mathlib 子字串比對（沿用現有腳本，修掉短陳述被略過的 bug）；對 miniF2F、PutnamBench 做重疊檢查；做 memorization probe（給定理名稱，看模型能不能補出陳述）；比較原版與擾動版的效能落差。
5. **Split**：calibration 20 題（調 impasse 門檻）、dev 30 題（開發算子 prompt）、**test ≥100 題（預註冊後只跑一次）**，並另設一個 operator-design split：test 中有些家族不出現在 dev。
6. **不做人工標註**（2026-11-02 確認：沒有標註者）。「非平凡輔助」完全由 hint-gap 定義，不報告人工 κ。論文的限制段要寫清楚：insight 的判定是操作化定義，不是人類判斷。

### 5.4 算力預估（**僅 Mac M5 / 24GB**，2026-11-02 決定：不動用伺服器與桌機）

- 底層證明器改用 **MLX 4-bit 量化的 7B 證明器**（`mlx-lm` 已安裝於 conda 環境 `mathesis`，GPU 可用）。權重約 4–5 GB，佔得下 24GB 統一記憶體。
- 吞吐量**尚未實測**（要先下載權重，見 §10）。在實測前，不估 GPU 時數。
- 因為吞吐量有限，主實驗規模要縮：取樣次數 k 從 32 降到 8（B0 pass@8 為主指標），16× 預算只在 10–20 題子集上跑。實際 k 由 W1 實測決定。
- Lean 驗證吃 CPU，M5 的效能核心足以應付；Lean 與 Mathlib 已在 `lean/.lake` 建好（7.2 GB，已排除於 git）。
- Benchmark 註明 M5、MPS、耗時（依 AGENTS.md）。所有 seed 都固定。

---

## 6. 時程（2026-11-03 → 2027-05 中）

| 階段 | 週次 | 工作 | 產出 | 門檻 |
|---|---|---|---|---|
| **P0 基礎** | W1–2（11 月上中旬） | git 初始 commit；實驗管線（results JSONL、run manifest、seed、成本會計）；打通 Pantograph 與 LeanInteract 的 gated 測試；把底層證明器部署到伺服器並量測吞吐量 | 可重現的 `make lean-bench` 結果檔 | **G0**：證明器在 miniF2F 子集上的 pass@8，與公開數字差距在合理範圍內 |
| **P1 Benchmark** | W3–8（11 月下旬–12 月） | 收集候選、算 Gap、做擾動、污染審計、凍結 split；**OSF 預註冊** H1–H4 | `benchmark/v1/`、datasheet、預註冊連結 | **G1**（12 月底）：≥100 題 insight 題（Gap ≥ 門檻）、≥60 對 routine 配對 |
| **P2 系統** | W6–12（12 月–1 月） | LLM 算子、impasse 特徵、bandit、B0–B5 全部 baseline；只用 calibration 與 dev | Mathesis v1 | **G2**（1 月底）：dev 上 Mathesis 對 B1／B2 有可見差距，管線吞吐量足夠跑完整實驗 |
| **P3 實驗** | W13–18（2 月–3 月中） | test split 只跑一次；1×／4×／16× 預算掃描；消融；miniF2F／PutnamBench 外部子集；個案研究 | 主表、Pareto 圖、交互作用分析 | **G3**（3 月中）：**H1 判定 → 決定投主會或 D&B** |
| **P4 寫作** | W19–24（3 月下旬–5 月中） | 撰寫論文、圖表、附錄、reproducibility checklist；整理程式碼與 benchmark 準備釋出；內部審稿（code-reviewer 加上主模型模擬審稿） | 投稿版 PDF | 截稿前一週定稿 |
| 期間 | 4–5 月 | 視情況送 workshop | — | — |

**緩衝**：P1 與 P2 有 3 週重疊（W6–8）。若 G1 延誤，P3 最多壓縮 2 週；再晚就直接轉保底 D&B。

---

## 7. 論文大綱（9 頁加附錄）

1. **Introduction**：AlphaProof 與 DeepSeek-Prover 之後，瓶頸在輔助構造；介紹 construction gap 與「何時重構」的問題；列出貢獻。
2. **Related Work**：LLM 證明器、子目標分解（DSP、LEGO-Prover、DeepSeek-V2）、proof planning 與 failure-driven lemma speculation（Bundy、Ireland & Bundy）、Soar 的 impasse-driven subgoaling、insight 的認知科學（Ohlsson、Knoblich）。
3. **Problem Formulation**：預算、censored cost、Gap 的定義、insight gain。
4. **Construction-Gap Benchmark**：建構流程、統計、污染審計。圖 1：各證明器在 insight 與 routine 題上的 Gap 分布。
5. **Mathesis**：impasse 偵測、算子、選擇策略。圖 2：架構圖。
6. **Experiments**：主表（H1–H3）；圖 3：solve-vs-cost Pareto（H4）；消融；外部 benchmark。
7. **Analysis**：僵局軌跡個案、失敗分類、算子使用分布。
8. **Limitations & Broader Impact**。
- 附錄：預註冊對照、完整超參數、datasheet、算力報告、prompt 全文。

---

## 8. 分工與執行規範

| 類別 | 負責 | 備註 |
|---|---|---|
| 假設、kill criteria、統計判定、benchmark 收錄標準、論文論證 | **主模型（不得下放）** | 依 AGENTS.md 科學規範 |
| 管線、算子、baseline、測試 | `implementer`（多檔案時用 Sonnet）、`qa-tester` | AGENTS.md 寫的 `muse-contributor` 在這台機器上不存在，改用 `implementer`。每次委派都要附絕對路徑、驗收命令和不可違反的規則 |
| 程式碼審查 | `code-reviewer` | 每次非瑣碎變更後 |
| 文獻核對、新論文追蹤 | `researcher` 或 Haiku | 結論必附來源 |
| 驗收 | **主模型自己重跑驗收命令** | 不只憑 subagent 的回報採信 |

不可違反的規則：test split 在預註冊前不能碰；OracleHave 只當上界，不能當方法；不提交 `literature/**/*.pdf`、`data/raw`、模型權重。

---

## 9. 文獻與理論依據

PDF 存在 `literature/`（已加入 `.gitignore`），索引見：

- `literature/ml/INDEX.md`、`refs.bib`：ATP 與 LLM 證明器（下載中）
- `literature/cogsci/INDEX.md`、`refs.bib`：insight、impasse、proof planning（下載中）
- `literature/verify/VERIFICATION.md`：`research-design.md` 中可疑 2026 文獻的核對結果（進行中）

理論骨架（論文 §2 與 §3 要用的四條線）：

1. **Insight 的表徵改變理論**：Ohlsson 1992、Knoblich et al. 1999、Öllinger et al. 2014。這是「僵局觸發重構」的認知依據。
2. **Impasse-driven subgoaling**：Soar（Laird, Newell & Rosenbloom 1987）。這是 AI 史上最直接的前例，論文**必須**討論它，以便和它區隔。
3. **Failure-driven proof planning**：Bundy 1988、Ireland & Bundy 1996（productive use of failure，lemma speculation）、Melis 1995。這是「從失敗中生成輔助引理」的直接前例，也是新穎性論證的關鍵對手。
4. **LLM 證明器與子目標分解**：DSP、LEGO-Prover、DeepSeek-Prover-V2、Goedel-Prover-V2。這是和現代方法區隔的地方：它們一律先分解，不靠僵局決定何時分解。

> 投稿前，所有 2026 年的文獻都要逐條核對作者、venue 與版本，核對不到的一律刪除。

### 9.1 文獻核對結果（2026-11-02，主 session 已用 arXiv API 抽查 4 篇標題）

- **全部確有其文，但有 3 處要修正**：
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
| **NanoProof**（2610.11605） | 小算力、可重現的 Lean 證明器 | 可以當底層證明器的候選（完全開源、算力低），值得認真考慮 |
| DeepSeek-Prover-V2、DSP、LEGO-Prover | 子目標或引理分解 | 它們一律先分解；我們的 B3 baseline 就是直接檢驗這個差別 |
| Li et al. 2026（arXiv:2604.16278） | 把缺乏「insight」（認出核心技巧）列為 LLM 定理證明的瓶頸，但做的是非形式證明 | 我們在 Lean 中用 hint-gap 做形式化、可量測的定義。它的存在正好支持我們的動機，引用時要做區隔 |

### 9.3 文獻庫現況

| 資料夾 | 已下載 | 只有 metadata | 找不到 |
|---|---|---|---|
| `literature/ml/` | 32 | 0 | 0 |
| `literature/cogsci/` | 7 | 19 | 3（Ohlsson 1992、Newell & Simon 1972、Lenat AM） |
| `literature/verify/` | 9 | — | — |

**需要你透過學校圖書館手動取得**（付費牆或擋爬蟲；理論章節的核心文獻）：Knoblich et al. 1999（JEP:LMC）、Ohlsson 1992、Öllinger et al. 2014、Laird, Newell & Rosenbloom 1987（Soar）、Ireland & Bundy 1996（JAR）、Bundy 1988（Edinburgh ERA 有公開版）、Melis 1995（IJCAI 公開）、Kounios & Beeman 2014、Friston et al. 2017（UCL Discovery 有公開版）。

**行動**：P0 期間由主模型精讀 ProofEvolve 與 HAGeo。如果 ProofEvolve 已經做了觸發時機的消融，就要調整 H1 的切入角度。

---

## 10. 需要你決定或提供的事

1. **算力**：實際可用的是 4× A4000 伺服器還是 RTX 5060？這會決定底層證明器的選擇和實驗規模。
2. **git 初始 commit**：目前完全沒有版本紀錄。建議在 P0 第一天 commit（`.gitignore` 已排除 `.lake`、PDF 與 venv）。
3. **第二位標註者**：有沒有同儕可以標約 50 題？沒有的話就用 LLM 加揭露。
4. **作者與單位**：會影響 OSF 預註冊和 workshop 投稿。

## 11. P0 執行狀態（2026-11-02）

| # | 項目 | 狀態 |
|---|---|---|
| 1 | 初始 commit | ✅ `debfb76`（95 個檔案，PDF 與 `.lake` 排除） |
| 2 | 實驗管線：`runs/<時間>_<指令>/` 含 `manifest.json`（commit、seed、Lean／Mathlib 版本、平台）、`results.jsonl`、`summary.json` | ✅ 已實作，pilot 已跑通；lean-bench 路徑尚未以真實 Lean 端到端跑過 |
| 3 | 修 impasse 單調 budget 偏誤；`choose()` 可插拔（新增 `RandomCandidateSelector`） | ✅ 已完成，但**有副作用**，見下 |
| 4 | 修 `contamination_audit.py` 短陳述略過的 bug，輸出 JSON | ✅ 50/50 題都已檢查（原本 46/50） |
| 5 | gated Lean／Pantograph 測試 | ✅ 全部通過（kernel 10、LeanInteract 5、Pantograph 28、lean-bench 24，0 失敗）。注意：這次是在 review 修正之前跑的，修正後還沒重跑 gated 測試 |
| 6 | 底層證明器部署（MLX）、miniF2F 子集的 G0 檢查 | ⏳ 權重下載中（見下） |
| 7 | 審查 review 發現的 12 點 | ✅ 修了其中 8 點（manifest、失敗時寫 summary、lean_calls 口徑、每題派生 seed、審計 stem bug、dev extra 等）；其餘留到後續階段（見下） |

**證明器權重**：`mlx-community/DeepSeek-Prover-V2-7B-4bit`（HF，3.90 GB，無 gate；HF 頁面授權欄位為空，使用前要再確認授權）。存於 HF cache（`~/.cache/huggingface`），不在 repo 內。**已下載並可載入**（snapshot `851514b6`）。

**W1 初步吞吐量（M5，MLX，單流、未批次）**：約 **9.8 tok/s**（含首次呼叫暖機，數字偏保守）。以計畫的規模（200 題 × k=8 × 約 1.5k token）推算約 2.4M token，單流需約 68 小時，**不可行**。下一步要評估 mlx-lm 的批次生成，以及縮小 k 或題數。生成品質也要看：單次樣本輸出有大量重複的 `nlinarith` 行，G0 時要檢查它是否真的能產生可用證明。**注意**：它是 CoT 證明器，計畫的主實驗要非 CoT，所以這只是 G0 的起點，W1 量測後再定案。

**留到後續階段的 review 項目**：`RandomCandidateSelector` 尚未接進任何 config（B4 要用，屬 P2）；lean-bench 的 `FROZEN_IMPASSE_THRESHOLD = 0.3` 是針對舊分數凍結的，要重新校準；`generic_match` 只看字元長度，規則過於粗略；`default_repo_root` 在兩處各定義一次，非 editable 安裝會指錯位置。

**重要發現（必讀）**：把 impasse 的 budget 權重改成 0 之後，**pilot 上 Mathesis 的 `impasse_count` 全部為 0**（已用目前程式碼重跑確認）。也就是說，目前的 "Mathesis" 在 pilot 上等同於不加控制的搜尋。這是修 bug 的直接後果，不是新 bug。權重必須在 calibration split 上重新校準，這一步不能用 test 題做。在校準完成前，任何「Mathesis 勝過 baseline」的說法都不成立。

**環境**：conda 環境 `mathesis`（`environment.yml`，Python 3.13，含 `mlx-lm`、`pytest`），依 AGENTS.md 建立，不使用 base。
