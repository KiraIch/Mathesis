# Mathesis：以僵局驅動表徵重構的自動數學發現系統

## 研究設計 v0.2

> 狀態：已根據一輪科學嚴謹度審查修訂。標記 2026 的文獻多為預印本或最新會議論文，投稿前請重新核對作者、venue 與版本。
>
> 目標：RIKEN CBS 博士班研究計畫書 + 一個現實可執行的 12 個月可行性 pilot。

---

## 0. 一頁摘要

**問題**：神經定理證明器（AlphaProof、AlphaGeometry、DeepSeek-Prover 等）擅長在大量資料與算力下預測 tactic；但當證明需要「輔助構造」（auxiliary construction）——輔助函數、輔助點、生成函數、不變量、中間引理——現有系統多半依賴領域專用啟發式或大規模搜索，缺乏一個域通用、可解釋、可審計的控制機制。

**缺口**：認知科學用「僵局（impasse）→ 表徵重構（representational restructuring）→ 頓悟（insight）」描述人類解題的關鍵一步；這個機制尚未被嚴格操作化、實作進現代證明助理，並用 compute-matched 的方式與搜索、LLM baseline 隔離比較。

**構想**：Mathesis 是一個以 Lean 4 為驗證核心的神經符號系統。它把「頓悟」操作化為**固定預算下、由 Lean 驗證器確認的搜尋成本下降**：

> 若一個重構算子 \(R\) 把狀態 \(s\) 變成 \(s'\)，使得在固定預算 \(B\) 下「從 \(s'\) 完成證明的成本」顯著低於「從 \(s\) 完成證明的成本」，且 \(R\) 自身（含證明其輔助引理）的成本很低，則 \(R\) 具有 insight gain。

工作迴圈：**有界搜尋 → 偵測僵局 → 選擇重構算子 → 產生良型別輔助構造 → Lean 驗證 → 記錄／鞏固**。

**評估**：建立一個輔助構造 benchmark（含 routine 對照題、難度匹配、污染審計），主要比較 **Mathesis vs. 使用同一算子庫但沒有 impasse 控制器的 BFS**，再與 Lean 自動化、固定排程重構、隨機重構、隨機輔助構造、以及一至兩個可執行的 LLM baseline 比較。所有比較固定 tactic set、lemma library、Lean 版本、timeout，並報告成本向量。

**近期目標**：不是讓系統發明全新數學理論，而是讓它在**未見過、且參考證明需要輔助構造**的定理上，自行找到可驗證的證明。長期才延伸到 lemma／conjecture discovery。

**MVP 定位**：12 個月只做可行性 pilot（15–20 題、2 個算子、一個關鍵消融），不是 confirmatory study。完整的 100+ 題、統計檢定、類比與鞏固留到博士 Y2。

---

## 1. 研究問題與貢獻

### 1.1 主研究問題

> 將 insight 操作化為「固定預算下的 censored 搜尋成本下降」，並以「僵局偵測 + 型別化表徵重構」為控制迴路，能否讓 Lean 4 中的自動定理證明在未見的輔助構造問題上，勝過**使用同一算子庫但沒有 impasse 控制器**的 compute-matched 搜索？

這個對照是關鍵：如果 Mathesis 只贏過「沒有算子庫的 BFS」，那可能只是算子庫的功勞；必須贏過「有算子庫、但隨機或固定排程觸發」的版本，才能支持 impasse 控制本身有效。

### 1.2 子問題

| 編號 | 問題 | 主要實驗 |
|---|---|---|
| RQ1 | impasse 觸發的重構，是否比固定排程／隨機觸發更有效？ | E1, E2 |
| RQ2 | 型別化算子庫是否比隨機輔助構造更有效？ | E1, E2 |
| RQ3 | 成功軌跡鞏固後，能否轉移到同族未見題？ | E3（Y2） |
| RQ4 | 類比檢索能否改善算子選擇？ | E2（Y2） |
| RQ5 | 系統軌跡是否可解釋，且與人類僵局／難度有對應？ | E6, E7（Y2–Y3） |

### 1.3 預期貢獻

1. **概念貢獻**：一個可證偽、可審計的「數學 insight」操作定義，把 impasse/restructuring 接到 Lean 驗證器與固定預算的成本模型。
2. **系統貢獻**：Mathesis——Lean 4 中的型別化重構控制架構，含可插拔算子、impasse 偵測、成本會計與認知日誌。
3. **資料貢獻**：一個公開的輔助構造 benchmark，含 insight/routine 配對、難度匹配、標註者間一致性與污染審計。
4. **實證貢獻**：compute-matched 的對照實驗，特別是「同一算子庫、無 impasse 控制器」這個關鍵 baseline；以及 operator-design split 下的泛化評估。
5. **認知科學貢獻**（Y2–Y3，選配）：模型 impasse/restructuring 軌跡與人類 think-aloud／難度評分的對應。

---

## 2. 與原始構想的差異：為什麼不把 GAN／HDC／遺傳演化當核心

原始構想的「GAN 生成輔助物件」「超維計算編碼數學概念」「遺傳演化突變輔助函數」聽起來吸引人，但作為核心機制有幾個問題：

1. **GAN 缺少可用的對抗訊號**。「這個輔助函數對證明有沒有用」不是平滑、可微的判別問題；真正訊號來自 Lean 的稀疏回饋（證明成功／失敗、搜尋成本）。GAN 很容易生成「看起來像數學式」的東西，而不是「能讓證明通過」的東西。
2. **HDC 不是必要複雜度**。證明狀態是圖結構（goal、local context、lemma dependencies）；graph kernel、GNN 或結構特徵已足夠做檢索。HDC 增加工程負擔，卻沒有對應的科學問題。
3. **無型別的遺傳演化＝昂貴的隨機搜索**。輔助物件必須是良型別的 Lean 項；沒有型別文法與驗證回饋，GP 只是在符號空間亂走。合理替代是 **typed program synthesis + bandit／學習式選擇 + verifier-in-the-loop**。
4. **「發現新數學結構」的承諾太大**。MVP 聚焦「發現輔助構造與中間引理」，不承諾「發明新理論」。後者需要更嚴格的 novelty 評估，留作長期目標。

因此，本設計保留認知科學的**控制結構**（impasse → restructuring → consolidation），但把**生成機制**換成可驗證、可消融、可計算成本的部分。

---

## 3. 理論基礎

### 3.1 表徵改變理論（Representational Change Theory）

Ohlsson（1992）與 Knoblich 等人（1999）主張：解題者一開始建立不適當的問題表徵，導致僵局；突破來自「約束放鬆（constraint relaxation）」與「組塊分解（chunk decomposition）」等表徵重構。Mathesis 的元認知層就是把這個控制結構操作化。

### 3.2 雙重歷程理論（Dual-Process Theory）

Evans 與 Stanovich（2013）區分 Type 1（快速、自動、聯想）與 Type 2（緩慢、序列、依賴工作記憶）。Mathesis 借用這個區分作為**設計隱喻**：

- **System 1／Type 1**：類比檢索、結構映射、快速提出「這題像什麼」的假設。
- **System 2／Type 2**：有界最佳-first 搜索、Lean 驗證、工作記憶限制。

本計畫**不宣稱**系統在生物學上等同人類雙歷程；它只借用這個架構作為工程先驗。若 WP3（人類研究）不做，認知框架只留在討論，不作為主要貢獻。

### 3.3 結構映射理論（Structure-Mapping Theory）

Gentner（1983）的類比理論強調關係結構的映射，而非表面符號相似。Mathesis 的 System 1 把證明狀態編碼成「目標—假設—引理依賴」圖，檢索結構相似的歷史證明軌跡，再把算子／子目標映射到新題。

### 3.4 手段—目的分析與 proof planning

Newell 與 Simon（1972）的手段—目的分析是 System 2 的基礎。Bundy（1988）的 proof planning 與 Melis（1995）的 analogy-driven proof-plan construction 已經展示了「轉移證明計畫」與「重構表徵」的價值；Mathesis 的差異在於把這些想法放進 Lean 依賴型別環境，並用 compute-matched 的方式隔離 impasse 控制的貢獻。

### 3.5 主動推論（Active Inference）作為替代形式化（選配）

2026 年有研究把 insight 形式化為 Bayesian model reduction，把 impasse 視為對可能行動的不確定性升高（Doulfoukar et al., 2026）。本計畫不以此為主要框架，但可在討論章節比較「重構＝模型縮減」與「重構＝搜尋成本下降」兩種操作化。

---

## 4. 操作化定義與假設

### 4.1 為什麼需要更嚴格的定義

「頓悟」很容易變成事後敘事。若沒有固定預算、censoring、成本會計與非平凡性檢查，任何「引入一個 `have`」都可以被說成 insight。以下定義是為了讓 H1 可被否證。

### 4.2 定義

**預算 \(B\)**：一個固定的資源上限，包含搜尋節點數、Lean heartbeats、wall-clock、LLM tokens 等；主實驗以 Lean heartbeats + wall-clock 為主要成本，因為它們跨 tactic set 比較公平。

**Censored cost**：對狀態 \(s\)，令

\[
T_B(s) = \begin{cases}
\text{從 } s \text{ 到證明的成本}, & \text{若在 } B \text{ 內成功}; \\
\infty, & \text{否則}.
\end{cases}
\]

不要用 \(C(s)=\infty\) 直接做比值；改用 survival analysis／censored regression，或以下的分類指標。

**Insight gain（分類版，主要）**：

\[
G_B(R,s) =
\begin{cases}
+1, & T_B(s)=\infty,\ T_B(s')<\infty \quad \text{(突破)}; \\
\log \dfrac{T_B(s)}{T_B(s')}, & T_B(s),T_B(s')<\infty; \\
-1, & T_B(s)<\infty,\ T_B(s')=\infty \quad \text{(破壞)}; \\
0, & \text{兩者皆失敗}.
\end{cases}
\]

再扣除重構成本：

\[
\text{NetGain}_B(R,s) = G_B(R,s) - \lambda \cdot \frac{\text{Cost}(R)}{B}.
\]

**Cost(R)** 必須包含：生成候選、Lean 檢查、**證明輔助引理的成本**、以及額外子目標的搜尋成本。不能只算「提出一個想法」的成本。

**非平凡輔助（nontrivial auxiliary）**：一個輔助物件／引理必須滿足：

1. 它在最終證明的依賴圖中被使用；
2. 它不是目標的定義展開、單純改名、或 definitionally equal 的 trivial `have`；
3. 在「移除該輔助物件、其餘設定相同」的消融中，固定預算 \(B\) 下搜尋失敗（對「必要輔助」子集）；
4. 人類標註者依 rubric 判定為非平凡（0/1），至少兩位標註者，報告 Cohen's \(\kappa\)。

第 3 點成本高，只在子集上做；第 4 點用於人類評分實驗。

**Operator-design split**：算子庫必須在一組「算子開發集」上設計與凍結，該集合與 test benchmark 的定理家族不重疊。若算子是由看過 test 參考證明的人設計，H1 會被「把答案編進算子庫」污染。正式實驗前凍結算子庫，並記錄每個算子的設計來源。

### 4.3 假設

| 假設 | 陳述 | 主要預測 | 否證條件 |
|---|---|---|---|
| **H1（核心）** | 在輔助構造 benchmark 上，Mathesis 在固定預算下的解題率高於**使用同一算子庫但沒有 impasse 控制器**的 BFS。 | E1 中 Mathesis 的 solve-vs-log-cost 曲線較優。 | 若與同算子庫 BFS 無顯著差異，H1 不成立；impasse 控制不是有效成分。 |
| H2 | 增益主要來自需要非平凡輔助構造的題目，而非 routine 題。 | insight 題的增益顯著大於難度匹配的 routine 題。 | 若兩類增益相近，H2 不成立（可能只是整體搜索變好）。 |
| H3 | 將成功重構鞏固為 meta-lemma／啟發式後，能轉移到同族未見題。 | leave-one-family-out 中，有鞏固的系統優於無鞏固與同大小隨機引理庫。 | 若無轉移增益，H3 不成立（Y2）。 |
| H4 | 類比檢索改善算子選擇，優於隨機、UCB、與 goal-type retrieval。 | 消融中 analogy 版本顯著較優。 | 若無差異，H4 不成立（Y2）。 |
| H5 | 系統 impasse／restructuring 軌跡與人類難度評分或 think-aloud 模式有可檢測對應。 | 模型 impasse 分數能預測人類主觀難度／停頓。 | 若無相關，認知詮釋需弱化（Y2–Y3）。 |

**MVP 只做 H1、H2 的可行性版本**；H3–H5 是博士 Y2–Y3 的工作。MVP 的樣本量不足以做 confirmatory test，應報告效果量與 CI，並明確標示為 pilot。

### 4.4 主要與次要終點

- **主要終點（confirmatory study）**：held-out test set 上、固定預算 \(B\) 的 solve rate；以 mixed-effects logistic regression 分析，控制題目難度與家族。
- **次要終點**：solve-vs-log-cost 曲線下面積（AUC）、censored cost、Lean heartbeats、wall-clock、proof length、非平凡輔助數量、operator coverage/usage、人類評分。
- **MVP 終點**：可行性與效果量估計，不追求 p < 0.05。

---

## 5. 系統架構

### 5.1 總覽

```
                    ┌─────────────────────────────┐
                    │  Metacognitive Controller    │
                    │  (bandit / fixed policy)     │
                    └──────────┬──────────────────┘
                               │ choose operator / continue
      ┌────────────────────────┼────────────────────────┐
      │                        │                        │
┌─────▼─────┐          ┌───────▼───────┐        ┌───────▼───────┐
│ System 1  │          │  Typed         │        │  Consolidation │
│ Analogy / │          │  Restructuring │        │  (Y2)          │
│ Retrieval │          │  Operators     │        │                │
│ (Y2)      │          │                │        │                │
└─────┬─────┘          └───────┬───────┘        └───────┬───────┘
      │                        │                        │
      └────────────┬───────────┴────────────┬───────────┘
                   │                        │
          ┌────────▼────────┐      ┌────────▼────────┐
          │ System 2        │      │ Lean 4 Verifier │
          │ bounded search  │─────▶│ + Mathlib       │
          │ (BFS)           │◀─────│ proof states    │
          └────────┬────────┘      └─────────────────┘
                   │
          ┌────────▼────────┐
          │ Impasse Detector│
          └─────────────────┘
```

### 5.2 驗證層與信任邊界

- **Ground truth**：所有候選證明都必須通過 Lean kernel；LLM 的「看起來對」不算。
- **Axiom audit**：每個成功證明執行 `#print axioms`；拒絕 `sorryAx`、自訂 `axiom`、未想要的 `Classical.choice` 以外的非標準公理。明確決定 `native_decide` 是否允許（它會引入 `Lean.ofReduceBool` 等信任假設），並在論文中報告。
- **互動方式**：優先使用現成 harness（LeanDojo、LeanInteract、Pantograph、LeanTree 之一），不要從零寫 REPL；用 Lean metaprogramming 取得結構化 proof state。
- **版本控制**：pin Lean toolchain 與 Mathlib commit；`lake exe cache get`；CI 快取建置。
- **背景知識的兩條 track**：
  - **Mathlib track**：允許完整 Mathlib，測試實用解題能力；MVP 用這條。
  - **Minimal-background track**：限制 lemma library 到基本算術／代數／集合論引理，測試「從少數公理出發」的發現能力；難度高，留作後期延伸。
- **Proof-state hash**：必須處理 alpha-equivalence、metavariable 實例化、local context 順序、definitional equality；否則 duplicate detection 與 novelty 指標會失真。

### 5.3 System 2：有界搜尋

- 演算法：最佳-first search；MCTS/HTPS-style 留到 Y2 作為外部 baseline，不是 MVP 核心。
- **工作記憶限制**：不硬編碼「5–9 個項目」；用 beam width、frontier size、context budget 等超參數模擬有限容量，並做消融。
- **狀態表示**：goal stack、local context、已用 lemma、搜尋深度、標準化後的狀態 hash。
- **固定 tactic set**：Mathesis 與所有 baseline 使用同一個可套用 tactic 集合（`apply`, `rw`, `simp`, `exact`, `have`, `use`, `constructor`, `by_contra`, `linarith`, `nlinarith`, `omega`, `polyrith`, `aesop` 等），避免「Mathesis 的 tactic 比較強」的混淆。
- **成本上限**：Lean heartbeats、搜尋節點、wall-clock、LLM tokens 分開記錄；所有比較 compute-matched。

### 5.4 僵局偵測（MVP 簡化版）

不要用 8 個特徵在 15 題上調參。MVP 先用 3 個預先註冊的特徵：

- `nodes_since_progress / B`：距離上次「新子目標關閉」或「goal complexity 下降」的節點比例。
- `duplicate_state_rate`：最近視窗內重複狀態比例。
- `budget_fraction`：已用預算比例。

判定：加權分數超過預先註冊的門檻且持續 \(k\) 步，即進入 impasse。門檻在**獨立的 calibration set** 上校準，test set 凍結後不得調整。

**必須有的對照**：

- `fixed-schedule`：每 N 個節點重構一次，不看 impasse。
- `random-trigger`：以相同頻率隨機觸發重構。
- `oracle-impasse`（上界）：由人工標註「這題什麼時候該重構」。
- 若 Mathesis 與 fixed-schedule/random-trigger 無差異，則 impasse detector 的貢獻不成立。

### 5.5 型別化重構算子（Typed Restructuring Operators）

算子的分類應按**狀態改變的類型**，而不是按 tactic 名稱；否則 `have` 會同時被歸類為「輔助物件」與「中間引理」。

以下為語言無關的介面；MVP 用 Python 實作，Rust 只在效能瓶頸時才引入。

```
Operator {
  id, family,                    // AddSymbol | AddSubgoal | ChangeType |
                                 // Reindex | Symmetry | Contradiction | ...
  pre(state) -> bool             // 前置條件
  propose(state, context) -> list[Candidate]
  cost(candidate) -> Cost        // 含證明輔助引理的成本
  apply(state, candidate) -> State | LeanError
}
```

MVP 只做兩個算子家族：

1. **AddSymbol／auxiliary witness**：在 local context 引入一個新的、良型別的物件（函數、常數、集合、見證），並要求 Lean 接受其定義或存在性。
2. **AddSubgoal／intermediate lemma**：用 `have` 引入一個可獨立證明的子目標；候選由 anti-unification／模板產生，並必須被 Lean 驗證。

其他算子（表徵改變、對稱、商、重排、不變量、類比映射）列為 Y2 擴展。MVP 不追求算子數量，而是把「impasse 控制 + 型別化生成」的因果鏈做乾淨。

**生成方式**：typed grammar／候選模板 + bandit 選擇；可用 LLM 產生候選，但候選必須經 Lean 驗證。LLM 不是真理來源。

### 5.6 System 1：類比與檢索（Y2）

- **編碼**：proof state → graph（goal node、hypothesis nodes、lemma dependency edges、type edges）。
- **檢索**：先用 graph kernel／結構特徵；資料夠多再上 GNN。
- **結構映射**：找出 source proof trace 與 target state 的關係對應；把 source 的算子序列映射成 target 的候選算子。
- **輸出**：排序的「算子 + 子目標」建議，交給 controller 評分。
- **對照**：random、UCB、goal-type retrieval、oracle analogy；沒有這些對照，H4 不成立。
- **防泄漏**：檢索庫只含 train split；test 參考證明不得進入庫。

### 5.7 元認知控制器

- **狀態**：impasse 特徵 + 算子歷史 + 剩餘預算。
- **動作**：選擇重構算子，或「繼續搜索」。
- **獎勵**：Lean 驗證的進展（新子目標關閉、成本下降、最終成功）減去成本懲罰。
- **演算法**：MVP 用固定規則／LinUCB；資料夠多再考慮 offline RL。MVP 不需要複雜 RL。
- **關鍵**：controller 要學到「何時停止硬搜、何時重構」；但 H1 的對照必須是同一算子庫、無 controller，否則無法隔離。

### 5.8 鞏固（Y2）

成功後抽取：impasse 特徵、選用算子、輔助物件／子目標、後續證明路徑、成本下降幅度。用 anti-unification 抽象成 meta-lemma／heuristic，附前置條件與驗證過的實例。

**失敗模式**：抽象過度（學到 benchmark-specific 符號）、抽象不足（無法轉移）、鞏固庫膨脹（檢索變慢）。緩解：held-out 驗證、同大小隨機引理庫對照、定期 pruning。

### 5.9 可解釋性

系統輸出認知日誌：

```
[impasse] nodes_since_progress=120, duplicate_rate=0.43, budget=0.61
[candidates] add_aux_symbol (0.71), add_subgoal (0.22), continue (0.07)
[chosen] add_aux_symbol: f(x) = x^2 - 2
[verify] Lean: new subgoal provable; cost 840 -> 37 heartbeats
[log] operator family=AddSymbol, nontrivial=yes, human_rating=4
```

這支撐「認知軌跡」與可審計性，但**不能單獨證明**認知效度；需要 WP3 的人類資料。

### 5.10 MVP 範圍

**MVP 不做**：GAN／HDC／GP 核心、完整雙歷程架構、新數學理論、幾何形式化、類比、鞏固、人類研究、MCTS、minimal-background track、external benchmarks。

**MVP 要做**：

- 15–20 題 pilot（含 routine 對照）；
- 一個 3 特徵 impasse detector；
- 兩個算子家族：AddSymbol、AddSubgoal；
- **BFS + 同一算子庫、無 impasse 控制器**（關鍵 baseline）；
- fixed-schedule 與 random-trigger 對照；
- 成本模型（Lean heartbeats、節點、wall-clock）；
- 認知日誌與個案研究；
- 一至兩個可執行的 LLM baseline（若資源允許）。

---

## 6. Benchmark 設計

### 6.1 原則

1. **Insight 與 routine 配對**：每題 insight 題配一題同領域、**以 baseline 解題率匹配難度**的 routine 題；不能只靠人類主觀難度，否則 H2 會與難度混淆。
2. **Reference proof 不給系統看**：系統只看到 theorem statement 與受限 lemma library；參考證明與建構註記只給評估者。
3. **家族切分**：train/dev/test 按定理家族切，不隨機切；test 家族在算子設計時不可見。
4. **Operator-design split**：算子庫在獨立的「算子開發集」上設計與凍結；該集合與 test 家族不重疊。
5. **污染與記憶化審計**：確認定理不在 Mathlib、不在 LLM 訓練資料；使用 canary、memorization probe、以及 novel/perturbed 題。
6. **可形式化**：優先選 Lean/Mathlib 已有定義的領域；幾何先不做，或只做座標化版本。

### 6.2 Pilot 例子 vs. confirmatory benchmark

以下 textbook 例子**只作為 pilot 校準**，不作為 confirmatory benchmark，因為它們幾乎都在 Mathlib 與 LLM 預訓練中：

| 類別 | Pilot insight 題 | 輔助構造 | Routine 對照 |
|---|---|---|---|
| 數論 | 前 n 個整數和 | 配對 \(i\) 與 \(n+1-i\) | 直接歸納 |
| 數論 | 無限多質數 | \(N=p_1\cdots p_k+1\) | 證明給定數是質數 |
| 數論 | \(\sqrt{2}\) 無理數 | 反證 + 奇偶性 | \(\sqrt{4}\) 是有理數 |
| 代數 | AM–GM（兩數） | 平方非負／輔助函數 | 展開 \((a-b)^2\ge 0\) |
| 代數 | Cauchy–Schwarz | 輔助二次函數 | 代入具體數值 |
| 組合 | 雙重計數 | 兩種方式數同一集合 | 直接套公式 |
| 組合 | 生成函數解遞迴 | 構造生成函數 | 展開前幾項 |
| 分析 | 輔助函數證不等式 | 構造 \(f(t)\) 用單調性 | 直接估計 |

**Confirmatory benchmark** 應該是：

- 100+ 題，8–12 個家族；
- 以近期文獻、競賽題變體、或 expert-generated 的 novel/perturbed 題為主；
- 每題有 reference proof、建構註記、難度標籤、允許 lemma library；
- 兩位標註者獨立標註「是否需要非平凡輔助」與難度，報告 \(\kappa\)；
- 以 baseline 解題率做難度匹配，而不是只靠 1–5 主觀評分；
- 題目與 Mathlib／LLM 的污染審計紀錄。

### 6.3 形式化協議

- 每題一個 Lean file：`theorem` statement + `sorry` 版本（給系統）+ 參考證明（評估用，獨立存放）。
- 建構註記：參考證明用到的輔助物件、為什麼需要它、對應的認知策略。
- 難度標籤：人類評分（1–5）＋ baseline 解題率 ＋ reference proof 長度。
- Lemma library：每題指定允許使用的引理集合；Mathlib track 與 minimal track 分開。
- Axiom audit：所有參考證明與系統證明都執行 `#print axioms`。

### 6.4 污染與記憶化

- **Canary**：在 benchmark 中加入不可能在訓練資料出現的標記／變體，檢查 LLM baseline 是否表現異常好。
- **Memorization probe**：對每個定理，測 LLM 在只給 statement 時能否背出參考證明；若可，標記為 contaminated。
- **Novel/perturbed**：改動參數、結構、或組合兩個已知結果，讓「檢索已知證明」不能直接奏效。
- **黑名單**：任何在 Mathlib 中已有同名／等價證明的定理，預設排除或移到 external set。
- **External benchmarks**：miniF2F、ProofNet、PutnamBench 只用於泛化檢查，不作為主要貢獻；注意 ProofNet 是 Lean 3，porting 成本要計入。

### 6.5 切分與規模

- **MVP pilot**：15–20 題（含 routine 對照），用於校準與可行性，不做 confirmatory test。
- **Confirmatory**：100+ 題，8–12 家族；train/dev/test 按家族切；另設 operator-development set。
- **External**：miniF2F、PutnamBench 子集（Y2）。
- **Geometry subset**：Y2–Y3，且必須先 port 到 Lean；在那之前不與 HAGeo 直接比較。

### 6.6 指標

| 指標 | 說明 |
|---|---|
| Solve rate @ budget | 固定預算下的解題率；主要終點 |
| Solve-vs-log-cost AUC | 多個預算點的曲線下面積 |
| Censored cost-to-proof | 失敗視為 censored；用 survival analysis |
| Lean heartbeats | 跨 tactic set 較公平的成本 |
| Wall-clock / tactic runtime | 實際時間；受硬體負載影響，需多次測量 |
| Nodes-to-proof | 搜尋節點數 |
| Proof length | tactic 數／AST 大小；不是 elegance 的唯一指標 |
| Nontrivial auxiliary count | 依 §4.2 的定義，不是數 `have` |
| Operator coverage / usage | 哪些算子被用、用多少次、成功率 |
| Insight gain | §4.2 的 NetGain |
| Transfer gain | 鞏固後在未見家族的增益（Y2） |
| Human rating | 數學家對 insight／elegance 的 1–5 評分（Y2） |
| Cognitive correspondence | 與人類 impasse／難度資料的相關性（Y2–Y3） |

---

## 7. 實驗計畫

### 7.1 實驗總表

| 編號 | 問題 | 設計 | 主要對照 | 成功標準 |
|---|---|---|---|---|
| **E1** | impasse 控制是否有效？ | compute-matched，固定 benchmark | **BFS + 同一算子庫、無 impasse 控制器**；fixed-schedule；random-trigger | Mathesis 的 solve-vs-log-cost 曲線較優 |
| E2 | 算子庫與生成方式 | 消融 | 隨機輔助構造、無算子庫、LLM 提案 vs. 模板 | 型別化算子庫有可測貢獻 |
| E3 | 轉移（Y2） | leave-one-family-out | 無鞏固、同大小隨機引理庫 | 有鞏固顯著較優 |
| E4 | 算力擴展 | 多預算點 Pareto | BFS；MCTS 作為 Y2 外部 baseline | 低預算區間優勢明顯 |
| E5 | 個案研究 | 質性分析 | 人類參考證明 | 找到非平凡輔助構造 |
| E6 | 人類評分（Y2） | 盲評、隨機順序、rubric | 人類證明、LLM 證明 | ICC 可接受、評分可區分 |
| E7 | 認知對照（Y2–Y3） | think-aloud／難度評分 | 人類資料 | 有顯著相關 |

### 7.2 Baselines 與對照（關鍵）

- **BFS + 同一算子庫、無 impasse 控制器（最重要）**：算子庫相同，只是不偵測 impasse、不做重構；用來隔離「impasse 控制」的貢獻。
- **Fixed-schedule restructuring**：每 N 個節點重構一次。
- **Random-trigger restructuring**：以相同頻率隨機觸發。
- **Random auxiliary construction + BFS**：HAGeo-style 隨機輔助點／隨機輔助物件；測試「隨機構造 + 搜索」是否已足夠。
- **Lean 自動化 portfolio**：`aesop`、`simp`、`omega`、`linarith`、`nlinarith`、`polyrith`。
- **最佳-first 搜索**：固定 tactic set + premise retrieval（LeanDojo-style）。
- **Retrieval-only**：只做 premise selection，不重構。
- **Oracle impasse／operator**：上界，估計重構選擇還有多大改進空間。
- **人類專家上界**：不是 baseline，而是 reference；用來判斷 benchmark 是否合理。
- **LLM tactic agent（1–2 個可執行）**：NanoProof（小型 open-weight）或 DeepSeek-Prover-V1.5 7B 可在單機／伺服器跑；frontier 模型（DeepSeek-Prover-V2 671B、Kimina 72B）在 4×A4000 16GB 上不現實（需量化／多機），只能走 API，並以 token／美元成本匹配。Aristotle、Seed-Prover 若無公開 API，移到 related work，不列入實驗。
- **HAGeo**：只在幾何子集且已 port 到 Lean 時比較；否則列 related work。
- **QuickSpec／Hipster**：等式／歸納領域的 lemma discovery，放 related work，不作為直接 baseline。

### 7.3 Compute matching 與成本向量

所有比較必須：

- 相同硬體（或換算 FLOPs）；
- 相同 tactic set、lemma library、premise retrieval；
- 相同 Lean 版本、timeout；
- 相同 seed 數與平行度；
- 報告多個預算點（1×、4×、16×），而不是單點。

成本向量至少包含：Lean heartbeats、tactic runtime、搜尋節點、wall-clock、LLM tokens、API 美元成本、GPU-hours。不要只用 nodes 或 wall-clock 單一指標；`simp`/`aesop` 一個 tactic 內含大量內部搜尋，node 數不可跨 tactic set 直接比較。

### 7.4 統計與 power

- **MVP**：15–20 題，報告效果量與 95% CI，明確標示為 pilot；不做 confirmatory p 值。
- **Confirmatory**：先用 pilot 效果量做 power analysis，決定 100+ 題的樣本；以 mixed-effects logistic regression（隨機效應：題目、家族）分析 solve rate；paired bootstrap／Wilcoxon 作輔助；Holm–Bonferroni 控制多重比較。
- **預註冊**：主要終點、分析族、停止規則、排除標準；test set 凍結後不得調參。
- **報告所有 run**：包括失敗、timeout、崩潰；不能只報成功案例。
- **Seeds**：seed 是技術重複，不增加 item-level N；不要把 5 seeds 當成 5 倍樣本。

### 7.5 消融

- Impasse 特徵逐項（3 特徵 → 1 特徵、2 特徵）。
- 算子庫大小（2 算子 vs. 4 算子）。
- 類比 vs. goal-type retrieval vs. random（Y2）。
- 鞏固 vs. 同大小隨機引理庫（Y2）。
- LLM 提案 vs. 模板／typed grammar。
- Premise retrieval vs. 無 retrieval。
- Axiom audit 前後的差異（若允許 `native_decide`，結果是否改變）。

### 7.6 負面結果

如果重構沒有幫助，仍然是可發表結果：

- 「何時 impasse-driven restructuring 有助於 Lean ATP？」——負面結果 + 邊界條件分析；
- benchmark、成本方法學、operator-design split 本身有價值；
- 可轉向「LLM + 重構」混合系統，或「重構用於人類輔助」的 HCI 方向。

---

## 8. 可行性、資源與時程

### 8.1 軟體棧

- **Lean 4 + Mathlib**：驗證器；pin toolchain 與 Mathlib commit；`lake exe cache get`。
- **Python first**：用 LeanDojo／LeanInteract／Pantograph／LeanTree 之一做 proof-state 互動與實驗腳本；MVP 不要從零寫 Rust harness。
- **Rust（選配）**：只有在搜尋／狀態管理成為效能瓶頸時才引入；不是 MVP 的必要條件。
- **ML**：PyTorch 只在需要 GNN 或 value model 時使用；MVP 可以只用規則與 bandit。
- **實驗管理**：Hydra／Optuna／簡單 YAML + CLI；MLflow／Weights & Biases 選配。
- **儲存**：proof traces、impasse logs、operator decisions、Lean check results、成本向量。

### 8.2 硬體

- **Mac M5**：開發、Lean 互動、小規模實驗。
- **Server（EPYC + 4× RTX A4000）**：平行 Lean 檢查、小模型 inference、大規模 seed。
- **注意**：Lean 檢查是 CPU-bound；GPU 主要給 LLM／GNN。4×A4000 16GB 跑不動 671B／72B 模型；frontier 模型只能走 API，成本匹配要用美元／token。

### 8.3 12 個月 MVP（聚焦版）

| 月份 | 里程碑 | 產出 |
|---|---|---|
| M1 | 文獻回顧、Lean harness 選型、benchmark 規格 | 文獻表、可跑的 Lean 互動範例、題目清單 |
| M2 | 10–15 題 pilot、BFS + Lean automation baseline | pilot benchmark、baseline harness |
| M3 | Impasse detector（3 特徵）、2 算子家族 | Mathesis v0.1 |
| M4 | **BFS + 同一算子庫、無 impasse 控制器**；fixed-schedule／random-trigger | 關鍵對照 |
| M5–6 | Pilot 實驗、成本模型、go/no-go | 初步 solve-vs-cost 曲線、效果量 |
| M7–8 | 一至兩個 LLM baseline（若可行）、個案研究 | 外部對照、failure taxonomy |
| M9–10 | 分析、寫作 | workshop paper／thesis draft |
| M11–12 | 開源、投稿、答辯 | code + benchmark release |

**MVP 的 success criterion**：不是「打敗 AlphaProof」，而是「在 15–20 題 pilot 上，Mathesis vs. 同算子庫 BFS 的效果量值得做 Y2 的 confirmatory study」，或「得到明確的負面結果與邊界條件」。

### 8.4 明確要砍的東西

12 個月一人不可能完成以下全部，MVP 必須砍：

- 類比檢索（Y2）；
- 鞏固與轉移（Y2）；
- 人類 think-aloud 研究（Y2–Y3，需 IRB）；
- MCTS/HTPS 完整實作（用 BFS + 現成 baseline 即可）；
- 幾何形式化與 HAGeo 比較（Y2–Y3，需 port 到 Lean）；
- minimal-background track（Y2–Y3）；
- 100+ 題 confirmatory benchmark（Y2）；
- 4–5 個算子（MVP 只做 2 個）；
- external benchmarks（Y2）。

### 8.5 36 個月博士時程（RIKEN CBS）

- **Y1**：MVP + pilot；Lean harness；15–20 題；2 算子；關鍵消融；送 IRB（若做 WP3）。
- **Y2**：100+ 題 confirmatory benchmark；類比、鞏固、轉移；LLM baseline；人類評分。
- **Y3**：WP3 人類 think-aloud／難度對照；幾何或分析延伸；論文與學位論文。

### 8.6 Go/No-Go 門檻

- **G1（M3）**：Lean harness 與 10–15 題可跑；否則縮小題目範圍或換 harness。
- **G2（M6）**：Mathesis 在 pilot 上與同算子庫 BFS 有可解釋的效果量；否則轉向負面結果／邊界條件分析。
- **G3（M9）**：LLM baseline 與個案研究可完成；否則把 LLM 對照移到 Y2，MVP 只做符號對照。
- **G4（M12）**：完成 workshop paper／thesis draft 與開源。

---

## 9. 風險與緩解

| 風險 | 影響 | 緩解 |
|---|---|---|
| Benchmark 太難／太易 | 無法定論 | pilot 校準；以 baseline 解題率分層；先做代數／數論／組合，不急著幾何 |
| Lean 形式化成本高 | 進度延遲 | 重用 Mathlib；用現成 harness；與 Lean 數學家合作；只形式化 statement，reference proof 獨立 |
| 算子庫是「答案 oracle」 | H1 虛高 | operator-design split；凍結算子庫；獨立數學家審查；報告算子來源 |
| Impasse detector 過擬合 | 無法泛化 | 3 特徵、預註冊門檻、獨立 calibration set；fixed/random trigger 對照 |
| 搜尋爆炸 | 算力不足 | 預算上限、premise filtering、operator pruning、快取 |
| 「Insight」定義被質疑 | 論文說服力 | censored cost、非平凡性檢查、人類評分、負面結果；避免過度宣稱 |
| 與 HAGeo／ProofEvolve／QuickSpec 重疊 | novelty 不足 | 明確定位；直接比較可比較的部分；其餘放 related work |
| LLM 污染 | 結果虛高 | held-out family、canary、memorization probe、novel/perturbed、開源模型 |
| 過擬合 benchmark | 無法轉移 | family split、operator-design split、leave-one-family-out、external set |
| 人類研究倫理 | 無法發表 | 及早送 IRB、知情同意、匿名化、資料管理計畫 |
| 單人專案範圍過大 | 無法按時 | MVP 只做 15–20 題 + 2 算子 + 1 關鍵消融；其餘列 Y2–Y3 |
| 硬體不足 | 無法跑 frontier LLM | 用 1B–7B open-weight；frontier 只走 API 並以美元成本匹配 |

---

## 10. 新穎性與定位

| 系統／文獻 | 做什麼 | 與 Mathesis 的差異 |
|---|---|---|
| AlphaProof（Hubert et al., 2025） | LLM + RL + Lean，大規模神經搜索 | Mathesis 不追求大規模預訓練或超越 AlphaProof 的算力效率；重點是**可解釋的 impasse 控制與成本會計** |
| AlphaGeometry／AlphaGeometry2（2024/2025） | 幾何專用神經符號 | Mathesis 域通用；幾何只是後期子集 |
| HAGeo（Duan et al., 2025/2026） | CPU heuristic／隨機輔助構造，IMO 幾何 | HAGeo 顯示「隨機輔助點 + 強幾何 deduction」已很強；Mathesis 的 scope 是**沒有強 deduction closure 的代數／數論／組合**，且用 Lean 驗證；幾何不直接比較，除非 port 到 Lean |
| ProofEvolve（2026） | 神經符號演化 + persistent schema library | ProofEvolve 偏向 evolutionary schema recombination；Mathesis 強調 **impasse-triggered** representation change，並做 trigger 消融（impasse vs. fixed vs. random） |
| QuickSpec／Hipster（2013/2014） | 等式理論探索、lemma discovery | 主要處理等式／歸納；Mathesis 是 goal-directed、跨表徵、Lean-based；QuickSpec/Hipster 放 related work |
| Melis（1995）；Bundy（1988） | proof-plan analogy、proof planning | Mathesis 建立在此之上；差異是 Lean 依賴型別、typed operators、compute-matched 評估 |
| 認知架構（Soar／ACT-R） | 通用認知模型 | Mathesis 是聚焦「數學 insight」的計算模型，不是通用架構 |
| LLM tactic agents（2025–2026） | tactic 預測 | Mathesis 可把 LLM 當候選產生器之一；核心是元認知控制；做 with/without LLM 消融 |

**Novelty claim（保守、可防守版）**：

> We are not aware of a controlled, compute-matched study that isolates the effect of impasse-triggered, typed representational restructuring for auxiliary-construction problems in Lean 4. Mathesis contributes (i) an operationalization of insight as censored proof-search cost reduction with a nontriviality criterion, (ii) a typed operator interface and a benchmark designed to separate operator-library effects from controller effects, and (iii) an evaluation against the critical baseline of the same operator library without an impasse controller.

**不要說**：

- 「first system to ...」（除非做過系統性文獻回顧，且限定詞足夠）；
- 「比 AlphaProof 省 3–4 個數量級算力」（沒有根據；AlphaProof 的 inference budget 可以很小）；
- 「能發現人類尚未發現的新數學結構」（MVP 不做這個）。

---

## 11. RIKEN CBS 研究計畫包裝

### 11.1 三個 work packages

1. **WP1（計算模型）**：Mathesis 的 impasse／restructuring／consolidation 架構與 Lean 實作；MVP 只做 impasse + 2 算子。
2. **WP2（benchmark 與評估）**：輔助構造 benchmark、compute-matched 比較、operator-design split、消融與轉移。
3. **WP3（認知對照，Y2–Y3）**：人類 think-aloud／難度評分與模型軌跡的對應；需 IRB、樣本數與操弄設計。若 WP3 不可行，本計畫應以 AI4Math 為主，認知框架只作討論，不宣稱認知效度。

### 11.2 為什麼適合 CBS

- CBS 的核心是腦與認知科學；本計畫用形式數學當「認知測試台」，檢驗 insight 的計算理論，而不是單純的 ATP 工程。
- 提供可證偽的計算模型，能與人類行為／神經資料對話（WP3）。
- 有明確的 AI4Math 應用價值（人類輔助證明、教育、自動化）。

### 11.3 English pitch（約 200 字，已修正過度宣稱）

> Current AI systems such as AlphaProof use large-scale neural search to find formal proofs, but they do not explicitly model the cognitive mechanisms that make human mathematical discovery possible: impasse detection, representational restructuring, analogical mapping, and the consolidation of insights into reusable lemmas. I propose **Mathesis**, a neuro-symbolic system that uses Lean 4 as a verifier and implements a controlled loop: a bounded deductive search (System 2), a typed restructuring operator bank, and a metacognitive controller that detects impasses and proposes auxiliary constructions or intermediate lemmas. Crucially, I operationalize "insight" as a **censored reduction in proof-search cost under a fixed budget**, making the central claim falsifiable, and I isolate the controller's effect against the critical baseline of the same operator library without impasse detection. I will build a benchmark of auxiliary-construction problems with matched routine controls, contamination audits, and an operator-design split, and evaluate Mathesis against compute-matched symbolic and neural baselines. The project will provide (i) a computational model of mathematical insight, (ii) an open benchmark and system, and (iii) a human-model comparison testing whether the model's impasse and restructuring traces correspond to human problem solving.

---

## 12. 開放問題

1. **表徵**：proof state 要編碼到什麼粒度，類比才有用？goal type、local context、lemma graph 的權重怎麼定？
2. **Typed 輔助物件生成**：如何用 Lean 的型別資訊限制候選空間，避免大量 ill-typed 項？
3. **Impasse 校準**：3 個特徵是否跨領域穩定？要不要學一個 impasse classifier？如何避免在 test 上調參？
4. **非平凡性**：如何自動判定一個輔助物件「不是 trivial `have`」？人類 rubric 的 \(\kappa\) 能到多少？
5. **Operator-design split**：算子庫要多大才公平？獨立數學家設計的算子是否會引入另一種 bias？
6. **鞏固**：anti-unification 的抽象層級怎麼選？如何避免 benchmark-specific shortcut？
7. **公平比較**：LLM baseline 的算力怎麼換算？API 模型的污染怎麼審計？
8. **Insight 的認知效度**：模型的 impasse 分數真的對應人類主觀僵局，還是只是搜尋停滯？
9. **Negative results**：如果重構只在少數題型有效，如何把邊界條件變成貢獻？

---

## 13. 參考文獻（節選）

**認知科學**

- Newell, A., & Simon, H. A. (1972). *Human Problem Solving*. Prentice-Hall.
- Ohlsson, S. (1992). Information-processing explanations of insight and related phenomena. In *Advances in the Psychology of Thinking*.
- Knoblich, G., Ohlsson, S., Haider, H., & Rhenius, D. (1999). Constraint relaxation and chunk decomposition in insight problem solving. *Journal of Experimental Psychology: Learning, Memory, and Cognition*.
- Gentner, D. (1983). Structure-mapping: A theoretical framework for analogy. *Cognitive Science*.
- Evans, J. St. B. T., & Stanovich, K. E. (2013). Dual-process theories of higher cognition: Advancing the debate. *Perspectives on Psychological Science*.
- Danek, A. H., & Salvi, C. (2023). Restructuring processes and Aha! experiences in insight problem solving. *Nature Reviews Psychology*.
- Doulfoukar, Y., Pezzulo, G., & Stuyck, H. (2026). Unveiling the Aha! moment: A computational account of insight in active inference. *Psychonomic Bulletin & Review*.
- VanLehn, K. (1989). Problem solving and cognitive skill acquisition. In *Foundations of Cognitive Science*.
- Lovett, M. C., & Anderson, J. R. (1996). History of success and current context in problem solving. *Cognitive Psychology*.

**自動定理證明與 AI4Math**

- Bundy, A. (1988). The use of explicit plans to guide inductive proofs. *CADE*.
- Melis, E. (1995). A model of analogy-driven proof-plan construction. *IJCAI*.
- Melis, E., & Whittle, J. (1999). Analogy in inductive theorem proving. *Journal of Automated Reasoning*.
- Polu, S., & Sutskever, I. (2020). Generative language modeling for automated theorem proving. arXiv:2009.03393.
- Lample, G., et al. (2022). HyperTree Proof Search for neural theorem proving. *NeurIPS*.
- Yang, K., et al. (2023). LeanDojo: Theorem proving with retrieval-augmented language models. *NeurIPS*.
- Trinh, T. H., et al. (2024). Solving olympiad geometry without human demonstrations. *Nature*.
- Hubert, T., et al. (2025). Olympiad-level formal mathematical reasoning with reinforcement learning. *Nature*. https://www.nature.com/articles/s41586-025-09833-y
- Chervonyi, Y., et al. (2025). AlphaGeometry2.
- Duan, et al. (2025/2026). Gold-medal-level olympiad geometry solving with efficient heuristic auxiliary constructions. arXiv:2512.00097.
- ProofEvolve (2026). Neuro-symbolic evolution for formal automated theorem proving. arXiv:2608.26334.
- Kripner, M., & Straka, M. (2026). NanoProof: Open and efficient automated theorem proving in Lean 4. arXiv:2610.11605.
- AutoformBench (2026). A Lean formalization benchmark for advanced mathematics. Preprint / NeurIPS 2026 MATH-AI workshop (venue to verify).
- Construction–Verification benchmark (2026). A benchmark for applied mathematics in Lean 4. arXiv:2602.01291.
- Claessen, K., et al. (2013). QuickSpec: Guessing formal specifications using testing.
- Johansson, M., et al. (2014). Hipster: Integrating theory exploration in a proof assistant. arXiv:1405.3426.

**Benchmarks 與工具**

- Zheng, K., et al. (2021). MiniF2F.
- Azerbayev, Z., et al. (2023). ProofNet. (Lean 3; porting cost.)
- Tsoukalas, G., et al. (2024). PutnamBench.
- Liu, C., et al. (2023). FIMO.
- CombiBench (2025). (Verify authors before citation.)
- LeanDojo, LeanInteract, Pantograph, LeanTree: Lean 4 proof-state interaction tools; verify current versions and licenses before use.

> 注意：2026 年條目多為預印本或最新會議論文；正式投稿前請核對作者、venue、arXiv 編號與最新版本。

---

## 14. 工程下一步（給實作 phase）

1. 選定 Lean 4 harness（LeanDojo／LeanInteract／Pantograph／LeanTree），跑通一個 theorem 的 proof-state 抽取與 tactic 執行。
2. 建立 `benchmark/` 的 10–15 題 pilot（Lean files + metadata + reference proof 分離）。
3. 建立 BFS + Lean automation baseline；固定 tactic set、lemma library、timeout、成本記錄。
4. 實作 3 特徵 impasse detector；在獨立 calibration set 上校準。
5. 實作兩個算子家族：AddSymbol（auxiliary witness）、AddSubgoal（intermediate lemma）。
6. 實作**BFS + 同一算子庫、無 impasse 控制器**與 fixed-schedule／random-trigger 對照。
7. 跑 pilot，產出第一條 solve-vs-log-cost 曲線、效果量、failure taxonomy。
8. 再決定是否進入 LLM baseline、類比、鞏固與 confirmatory benchmark。

> 本文件只定義研究設計與評估邏輯，不指定最終程式碼；實作工作另行分工。
