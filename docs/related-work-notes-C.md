# Related Work 閱讀筆記 (C)

本檔記錄已讀的 9 篇論文是否報告隨機性或不確定性（Q1–Q4）。涵蓋 A 組 5 篇、B 組 4 篇（不含 B 組的基準論文 2109.00110、2302.12433、2407.11214）。

**限定：** 「文中未提」只表示「在該檔全文以下方關鍵字沒找到相關上下文」，不等於論文沒做。本檔的結論只描述這 9 篇。

## 方法與核對

- 文字來源：scratchpad 下 `litA/`、`litB/` 的 `<arXiv編號>.txt`。9 檔全部存在，未重新下載，未執行這些檔案。`litA/quotes.txt` 與 `*.p12.txt` 不在本次範圍，未使用。
- 「PDF p.N」依 pdftotext 換頁字元推算，未與 PDF 印刷頁碼逐頁核對，可能有 ±1 的誤差。
- 引句以 `grep -F` 對原文比對。跨行的句子拆成單行片段分別比對。
- 答案定義：「是」表示有引句支持；「否」表示命中的上下文經判讀不符合該項（本檔未使用）；「文中未提」表示下表關鍵字在該檔找不到相關上下文。
- Q3 在總表中的欄位定義為「是否明確報告每題樣本數（pass@k 的 k 或 sample budget）」。單次或多次執行另在各節說明。
- 關鍵字命中數為 `grep -aic`（不分大小寫、子字串匹配，含參考文獻與 "Seed-Prover" 等），判讀見各節。

關鍵字命中數（欄位代號：PE = ProofEvolve、HG = HAGeo、AM = AMBER、NP = NanoProof、DI = DeepInsight、DS = DeepSeek-Prover-V2、DSP = Draft Sketch Prove、LG = LEGO-Prover、GP = Goedel-Prover-V2）：

| 關鍵字 | PE | HG | AM | NP | DI | DS | DSP | LG | GP |
|---|---|---|---|---|---|---|---|---|---|
| seed | 23 | 0 | 2 | 5 | 0 | 0 | 0 | 1 | 5 |
| variance | 3 | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| standard deviation | 4 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| std | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| confidence interval | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| error bar | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| significan | 1 | 3 | 13 | 0 | 3 | 7 | 2 | 4 | 13 |
| bootstrap | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| ± | 12 | 0 | 0 | 0 | 0 | 35 | 0 | 0 | 9 |
| repeated | 3 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 |
| independent run | 2 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| independent（任何用法） | 9 | 3 | 0 | 24 | 0 | 1 | 0 | 1 | 3 |
| runs | 24 | 3 | 0 | 4 | 0 | 0 | 0 | 1 | 0 |
| trial | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| pass@ | 3 | 5 | 14 | 7 | 0 | 6 | 0 | 0 | 46 |
| sample budget | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 0 |
| averag | 7 | 5 | 1 | 3 | 6 | 3 | 0 | 1 | 28 |
| random | 12 | 23 | 2 | 3 | 3 | 0 | 3 | 4 | 0 |
| stochastic | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| reproduc | 3 | 0 | 3 | 7 | 1 | 0 | 1 | 0 | 0 |
| determinis | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| sensitiv | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

---

## A 組

### 1. ProofEvolve：Neuro-Symbolic Evolution for Formal Automated Theorem Proving（arXiv:2608.26334）

- **Q1：是。** "Mean solve rate (%) over three independent runs on PutnamBench"（PDF p.8，Table 1 標題）。
- **Q2：是（誤差線）。** "Error bars show the run-to-run" / "standard deviation across independent reruns."（PDF p.9，Figure 3 標題）。誤差線為 run-to-run 標準差，不是信賴區間；全文未見顯著性檢定（"significan" 命中 1 次，為 "significant effectiveness" 的敘述用語）。
- **Q3：是。** "We compare against pass@16 sampling from"（PDF p.8）；系統本身以 "A per-target budget caps the model calls, Lean-kernel calls, tokens, and wall-clock time each target may use."（PDF p.10）限制每題預算。主表數字為三次執行的平均（見 Q1）。
- **Q4：是。** "The three runs are independent samples from the decoder, and" / "the reported standard deviation measures variation across these runs."（PDF p.25，附錄 F.6）。另有 "The band is ±1 run-to-run standard deviation of the lift"（PDF p.10，Figure 5 標題）。
- 注意：PDF p.9 的消融實驗寫 "run with five random seeds to ensure statistical stability"，與主表的三次執行不同（見待確認事項）。

### 2. HAGeo：Gold-Medal-Level Olympiad Geometry Solving with Efficient Heuristic Auxiliary Constructions（arXiv:2512.00097）

- **Q1：文中未提。** 關鍵字命中：seed 0、variance 1、runs 3。variance 那一次是 "problems, which could lead to high variance in evaluation."（PDF p.2），指的是題數只有 30 題，不是重複執行。runs 的 3 次都是 DDAR 引擎的重跑，例如 "re-runs the DDAR."（PDF p.4），不是評估的重複執行。
- **Q2：文中未提。** 關鍵字命中：confidence interval 0、error bar 0、bootstrap 0、significan 3（皆為 "significantly higher efficiency" 之類的敘述）。
- **Q3：是。** "we use K = 4096 auxiliary"（PDF p.7，IMO-30）；"we set the number of attempts K = 2048 for both our"（PDF p.7，HAGeo-409）。單次或多次執行：文中未提。
- **Q4：文中未提。** 關鍵字命中：variance 1、sensitiv 0、stochastic 0。唯一相近句為 Q1 所引的 "high variance in evaluation"，其原因是題數少，與隨機性無關。

### 3. AMBER：Construction–Verification: A Benchmark for Formalizing Applied Mathematics in Lean 4（arXiv:2602.01291）

- **Q1：文中未提。** 關鍵字命中：seed 2（兩次皆為 "Seed-Prover" 的參考文獻）、independent 0、runs 0、reproduc 3（指可重現的評測環境，非重複執行）。
- **Q2：文中未提。** 關鍵字命中：confidence interval 0、error bar 0、bootstrap 0、significan 13（皆為一般敘述，例如 "significantly misled the models"，PDF p.23）。
- **Q3：是。** "based on n = 16 samples per problem"（PDF p.23，Table 6 說明）。pass@k 以 n = 16 個樣本估計無偏估計量。單次或多次執行：文中未提。
- **Q4：是（僅指估計量的變異）。** "Evaluating Pass@k by simply generating k samples" / "and checking if at least one is correct results in high variance."（PDF p.23，附錄 D.3）。這是說明抽樣估計量在樣本數少時變異大，並非重複執行的結果差異。

### 4. NanoProof：Open and Efficient Automated Theorem Proving in Lean 4（arXiv:2610.11605）

- **Q1：是。** "We perform three independent runs of RL training and"（PDF p.8，§5.1）。
- **Q2：是（非信賴區間）。** "over three independent runs with min/max bands."（PDF p.8，Figure 4 標題）；正文 "report the mean score with min/max bands."（PDF p.8）。圖上為 min/max 範圍，不是 CI 或 SD。未見顯著性檢定（significan 0）。
- **Q3：是。** "under the budget of 256" / "MCTS iterations."（PDF p.8，訓練曲線）；"on MiniF2F-Test under 512 iterations."（PDF p.8，最終 pass@16 結果）。最終的 50.8% pass@16 來自 "A final checkpoint, selected from the three" 中的一個檢查點，即單次評估。
- **Q4：文中未提。** 關鍵字命中：sensitiv 0、variance 0。正文只有設計說明 "independent in terms of both the theorems sampled by the"（PDF p.8，接 "The runs are"），沒有討論結果對隨機性的敏感度。

### 5. DeepInsight：Learning to Reason with Insight for Informal Theorem Proving（arXiv:2604.16278）

- **Q1：文中未提。** 關鍵字命中：seed 0、variance 0、runs 0、independent 0。
- **Q2：文中未提。** 關鍵字命中：confidence interval 0、error bar 0、bootstrap 0、significan 3（一般敘述）。
- **Q3：文中未提。** 取樣數未給出。只有 "generations use the same benchmark split, decod-" / "ing budget, proof extraction rule, LLM-as-judge"（PDF p.15）提到 decoding budget（跨行拆開，原文為 decod-ing），但沒有數值。
- **Q4：文中未提。** 關鍵字命中：sensitiv 0、stochastic 0。相近句為 "Using only one LLM as a judge may introduce" / "bias in evaluation."（PDF p.16）。這是評審偏誤，不是隨機性。

---

## B 組

### 6. DeepSeek-Prover-V2（arXiv:2504.21801）

- **Q1：是（僅報告 σ）。** "denotes the average accuracy 𝜇 and the standard deviation 𝜎"（PDF p.8，Table 1 標題）。文中未說明 μ±σ 來自幾次獨立執行。
- **Q2：文中未提。** 表中有 ± 值（± 命中 35 次），但沒有 CI、誤差線圖或顯著性檢定。significan 7 次，例如 "which significantly" / "outperforms its non-CoT counterpart."（PDF p.10）是一般敘述。
- **Q3：是。** Table 1 的 "Sample budget" 欄（PDF p.8）；"49 problems using a sample budget of 1024 per problem."（PDF p.10）。單次或多次執行：PutnamBench 的段落寫 "Our initial run solved"（PDF p.10），文中只有這一次執行的描述。
- **Q4：文中未提。** 關鍵字命中：sensitiv 0、variance 0、random 0。

### 7. Draft, Sketch, and Prove（DSP；arXiv:2210.12283）

- **Q1：文中未提。** 關鍵字命中：seed 0、standard deviation 0、runs 0。variance 1 次見 Q4。
- **Q2：文中未提。** 關鍵字命中：confidence interval 0、error bar 0、significan 2（"significantly reduced number of calls" 為 PDF p.3 的一般敘述）。
- **Q3：是。** "statements to sample 100 informal proofs per problem"（PDF p.6）；"the total number of queries made to Codex per problem to be 100"（PDF p.6）；"with temperature T = 0.6 and top p = 0.95 for Minerva models"（PDF p.6）。單次或多次執行：文中未提。
- **Q4：是。** "because the randomly sampled examples in the prompt are not suitable"（PDF p.10）；作者說 "like to reduce this variance by attempting autoformalization multiple times"（PDF p.10），並寫明因成本而未做。這是提示隨機抽樣造成的結果差異，不是重複執行的結果。

### 8. LEGO-Prover（arXiv:2310.00656）

- **Q1：文中未提。** 關鍵字命中：seed 1（"seed theorems"，PDF p.8，指種子定理）、variance 0、standard deviation 0、runs 1（參考文獻）。
- **Q2：文中未提。** 關鍵字命中：confidence interval 0、error bar 0、bootstrap 1（參考文獻標題）、significan 4（一般敘述）。
- **Q3：是。** "up to 20 informal proofs per problem"（PDF p.7）；"we perform ablation only under 50 proving attempts per problem"（PDF p.7）。單次或多次執行：文中未提。
- **Q4：文中未提。** 相近句為 "For each proving attempt, we randomly select"（PDF p.7），這是方法描述，沒有討論結果對隨機性的敏感度。

### 9. Goedel-Prover-V2（arXiv:2508.03613）

- **Q1：文中未提。** Table 2 有 ± 值（例如 "88.1% ± 0.8%"，PDF p.7），但全文未定義 ±，也未說明執行次數（standard deviation 0 次）。"reaches an average of 92.7%"（PDF p.9）未說明平均的對象。因此 Q1 標為文中未提，並列為待確認。
- **Q2：文中未提。** 關鍵字命中：confidence interval 0、error bar 0、bootstrap 0、significan 13（例如 "removing compiler feedback significantly lowers performance"，PDF p.9，一般敘述）。
- **Q3：是。** "Performance of different whole-proof generation methods on MiniF2F test split."（PDF p.7，Table 2，含 Budget 欄）；"The performance (%) of Goedel-Prover-V2 on MiniF2F across different compute budget."（PDF p.9，Table 4）。單次或多次執行：文中未提。
- **Q4：文中未提。** 關鍵字命中：sensitiv 0、stochastic 0、random 0。附錄中關於「同一題重複生成」的敘述（PDF p.23）談的是題目生成的多樣性，不是評估結果的隨機性。

---

## 總結

| 論文 | Q1 多次執行／標準差 | Q2 CI／誤差線／顯著性 | Q3 每題樣本數 | Q4 對隨機性敏感 |
|---|---|---|---|---|
| 1 ProofEvolve（2608.26334） | 是 | 是 | 是 | 是 |
| 2 HAGeo（2512.00097） | 文中未提 | 文中未提 | 是 | 文中未提 |
| 3 AMBER（2602.01291） | 文中未提 | 文中未提 | 是 | 是 |
| 4 NanoProof（2610.11605） | 是 | 是 | 是 | 文中未提 |
| 5 DeepInsight（2604.16278） | 文中未提 | 文中未提 | 文中未提 | 文中未提 |
| 6 DeepSeek-Prover-V2（2504.21801） | 是 | 文中未提 | 是 | 文中未提 |
| 7 DSP（2210.12283） | 文中未提 | 文中未提 | 是 | 是 |
| 8 LEGO-Prover（2310.00656） | 文中未提 | 文中未提 | 是 | 文中未提 |
| 9 Goedel-Prover-V2（2508.03613） | 文中未提 | 文中未提 | 是 | 文中未提 |

就這 9 篇而言：Q1 的「是」出現在 3 篇，其中 ProofEvolve 與 NanoProof 報告多次獨立執行，DeepSeek-Prover-V2 只報告 σ，未說明執行次數。Q2 的「是」只見於 ProofEvolve（標準差誤差線）與 NanoProof（min/max 範圍），9 篇都沒有報告信賴區間或顯著性檢定。Q4 的「是」出現在 ProofEvolve、AMBER、DSP，其中 AMBER 與 DSP 談的是抽樣估計量或提示抽樣的變異，不是重複執行。

## 待確認

1. ProofEvolve：PDF p.9 的消融實驗寫 "run with five random seeds"，主表與 Table 7 則為三次執行。作者需確認兩者是否為不同實驗。
2. Goedel-Prover-V2：Table 2 的 ± 未定義，"reaches an average of 92.7%"（PDF p.9）的平均對象不明。需要作者查原文或 PDF 版面。
3. DeepSeek-Prover-V2：Table 1 的 σ 未說明來源（執行次數、種子）。
4. 頁碼為換頁字元推算，引用到論文中時需對照 PDF 印刷頁碼。
