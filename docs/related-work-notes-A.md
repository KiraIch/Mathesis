# Related Work 閱讀筆記 (A)

本檔為論文 Related Work 的閱讀筆記，涵蓋五篇 arXiv 論文。目的是記錄各篇在「觸發時機」、「消融實驗」、「提示（輔助構造、引理、子目標）差距」三個面向的實際內容，並與本工作（Lean 4 + Mathlib，以 DeepSeek-Prover-V2-7B 量測 hint-gap，資料集 `lean_hard` 92 題，結果為負面）作比較。

## 方法與核對

- 全文以 `pdftotext` 取得（版面模式與非版面模式各一份），中繼資料來自 `export.arxiv.org` API。所有 PDF 與文字檔只放在 scratchpad，未放入專案目錄。
- 引句均以 `grep` 對照文字檔確認（先原樣比對，再將換行與多餘空白正規化後比對）。
- 「PDF p.N」為 `pdftotext` 換頁計數，不是論文印刷頁碼。
- 標題與摘要取自 PDF 首頁。摘要由版面模式文字還原：兩欄排版造成的行尾連字號已還原（例如 `whole-proof`、`general-purpose`），文字內容未改寫。
- 文中可疑指令：以關鍵詞（如 ignore、disregard、system prompt、assistant）掃描五篇文字檔，未發現要求讀者或 AI 執行的內容。命中的 "Claude ..." 字樣皆為論文中的模型名稱。此為關鍵詞掃描，未逐頁閱讀全文。

---

## 1. ProofEvolve: Neuro-Symbolic Evolution for Formal Automated Theorem Proving

- **書目**：ProofEvolve: Neuro-Symbolic Evolution for Formal Automated Theorem Proving；Wenqian Ye, Ziwei Guan, Eric Xie et al.；arXiv:2608.26334；提交日期 2026-08-26（API `published`）。
- **摘要原文**：

> Automated theorem proving offers a natural foundation for recursive self-improvement in scientific discovery. However, existing neural provers do not fully preserve this recursive structure, where the learning process should be self-improving over time. Existing methods either embed proof experience into model parameters through expensive weight updates, or keep verified intermediate deductions only within the current problem. In addition, these methods also heavily rely on sparse whole-proof feedback, even when unsuccessful partial attempts contain useful discoveries. To close the gap, we propose ProofEvolve, a neuro-symbolic framework that evolves explicit, formally verified symbolic proof structures with neural models to decisively expand the knowledge boundary. In this framework, the neural model proposes variation operators, including decompositions, repairs, and schema recombinations. The symbolic Lean kernel verifies every proof transition. Over the evolution loops, ProofEvolve computes verified closure over the resulting proof directed acyclic graphs (DAGs). Within each problem, ProofEvolve evolves partial AND-OR proof DAGs in a behaviorally indexed archive. Across problems, kernel-checked schema extraction adds newly proved sub-DAGs to a persistent schema library. Proof DAGs inherit the solved results through typed schema recombination, with every residual premise exposed as a new subgoal. This evolutionary process preserves verified results from incomplete attempts and makes them available for later proofs without weakening formal soundness. Across three competition-level Lean benchmarks, ProofEvolve achieves the highest average solve rate among the evaluated proof systems.

- **Q1（是否依「何時」觸發重構／分解／構造）**：**是（僅限 repair 分支）**
  - 「In repair, available only for a previously rejected proposal at the same state」（§4.2，PDF p.5）。
  - 「Choose an applicable o ∈ {decompose, recombine}.」（Algorithm 1 第 8 行，PDF p.15）。Algorithm 1 第 5 行以「是否有 rejected edit」決定走 repair，否則每輪於 decompose 與 recombine 中選擇；decompose 本身不依失敗或僵局觸發。
- **Q2（觸發時機的消融）**：**否**
  - 「We remove one operator at a time on the 60 IMO-LeanProofBench problems.」（§5.4，PDF p.9）。消融對象是移除 decomposition、recombination、repair 三種算子，未比較觸發時機。
- **Q3（給／不給提示的成功率差距）**：**是（以引理／schema library 為對象）**
  - 「ProofEvolve solves 19.8% of the targets when the library grows across targets」與「7.3% when the library is reset before each target.」（合成組合式引理族的受控實驗，PDF p.10）。
  - 「whereas random retrieval from the same library gives no improvement.」（引言，印刷頁 2）。
  - 註：此為「可用引理」的對照，不是輔助構造或子目標的對照。
- **Q4（基準與規模）**：
  - 「PutnamBench (326), IMO-LeanProofBench (60), and CombiBench (99)」（目標清單，PDF p.17）；共 485 個 target。
  - 另有 Lean Workbook 切分：「on 744 Lean Workbook theorems disjoint from the 9,968-theorem source stream」（引言，印刷頁 2）。
- **Q5（證明器／模型；是否開源）**：
  - 「with a frontier LLM (Claude Opus 4.8) as the base model」（引言，PDF p.3）；「Proprietary baselines (Claude Opus 4.8) are accessed」（PDF p.17），即透過 API 存取。
  - 「frontier open-weight model Qwen3.5-397B-A17B-FP8」（引言，PDF p.3），用於 Lean Workbook 切分。
  - 本篇自身程式碼或權重是否釋出：**文中未提**（全文未找到 code 或 repository 釋出聲明）。
- **Q6（與本工作的關係）**：本篇同樣量測「可用引理（schema library）」對成功率的影響（19.8% 對 7.3%，合成資料）。設定不同：模型為 Claude Opus 4.8 與 Qwen3.5-397B，基準為 PutnamBench、IMO-LeanProofBench、CombiBench，與本工作的 DeepSeek-Prover-V2-7B 與 `lean_hard` 不可直接比較。

**總結**：ProofEvolve **未做觸發時機的消融**，答案：**否**。依據為 §5.4 的「We remove one operator at a time」，以及 Algorithm 1 中 repair 與 decompose/recombine 的分支條件（PDF p.9、p.15）。Repair 的失敗觸發屬於流程設計，論文未對該觸發條件做消融。

---

## 2. HAGeo: Gold-Medal-Level Olympiad Geometry Solving with Efficient Heuristic Auxiliary Constructions

- **書目**：Gold-Medal-Level Olympiad Geometry Solving with Efficient Heuristic Auxiliary Constructions；Boyan Duan, Xiao Liang, Shuai Lu et al.；arXiv:2512.00097；提交日期 2025-11-27（API `published`）。
- **摘要原文**：

> Automated theorem proving in Euclidean geometry, particularly for International Mathematical Olympiad (IMO) level problems, remains a major challenge and an important research focus in Artificial Intelligence. In this paper, we present a highly efficient method for geometry theorem proving that runs entirely on CPUs without relying on neural network–based inference. Our initial study shows that a simple random strategy for adding auxiliary points can achieve “silver-medal” level human performance on IMO. Building on this, we propose HAGeo, a Heuristic-based method for adding Auxiliary constructions in Geometric deduction that solves 28 of 30 problems on the IMO-30 benchmark, achieving “gold-medal” level performance and surpassing AlphaGeometry, a competitive neural network–based approach, by a notable margin. To evaluate our method and existing approaches more comprehensively, we further construct HAGeo-409, a benchmark consisting of 409 geometry problems with human-assessed difficulty levels. Compared with the widely used IMO-30, our benchmark poses greater challenges and provides a more precise evaluation, setting a higher bar for geometry theorem proving.

- **Q1**：**是**
  - 「If the system fails to solve a geometric problem in the initial DDAR, we add auxiliary points based on our」（§4.5，PDF p.7）。只有初始 DDAR 失敗後才加入輔助構造。
  - 相關敘述：「If the DDAR fails to solve the problem, we further attempt K different auxiliary constructions」（§4.1；頁碼未確認）。
- **Q2**：**否**
  - 「We conduct an ablation study to analyze the effect of the number of attempts K (Pass@K)」（§5.3，PDF p.9）。消融對象是嘗試次數 K，未比較觸發時機。
- **Q3**：**是**（依表 2 與 §4 流程推論；論文未明文標示 DDAR 列為「無輔助構造」）
  - 表 2 欄位：「DDAR 15」、「HAGeo 28」，表題為「Comparison on the IMO-30 benchmark.」（PDF p.8）。
  - 「Notably, our proposed HAGeo solves 28 out of 30 problems」（§5.2，PDF p.8）。
- **Q4**：
  - IMO-30：30 題（「solves 28 of 30 problems on the IMO-30 benchmark」，摘要）。
  - HAGeo-409：「a benchmark consisting of 409 geometry problems with human-assessed difficulty levels」（摘要）。
- **Q5**：
  - 方法不使用神經網路推論：「runs entirely on CPUs without relying on neural network–based inference」（摘要）。
  - 程式碼與基準連結列於首頁：「Code: https://github.com/boduan1/HAGeo」，以及「Benchmark: https://huggingface.co/datasets/HAGeo-409」（PDF p.1）。僅確認連結存在，未檢查 repository 內容。
- **Q6**：本篇同樣量測「加入／不加入輔助構造」的成功數差距（IMO-30：DDAR 15 對 HAGeo 28），與本工作的 hint-gap 概念最接近。但本篇為歐氏幾何、不使用 LLM、不在 Lean 中，數字不可直接比較。

---

## 3. Construction–Verification: A Benchmark for Applied Mathematics in Lean 4

- **書目**：Construction–Verification: A Benchmark for Applied Mathematics in Lean 4（中繼資料標題為 Construction-Verification）；Bowen Yang, Yi Yuan, Chenyi Li et al.；arXiv:2602.01291；提交日期 2026-02-01（API `published`）。
- **摘要原文**：

> Recent advances in large language models have demonstrated impressive capabilities in mathematical formalization. However, existing benchmarks focus on logical verification of declarative propositions, often neglecting the task of explicitly synthesizing solutions. This limitation is particularly acute in applied mathematics domains, where the goal is frequently to derive concrete values or executable algorithms rather than solely proving theorems. To address this, we introduce a Lean 4 framework that enforces a construction-verification workflow, compelling the agent to define explicit solutions before proving their correctness. We curate a comprehensive benchmark AMBER (Applied Mathematics BEnchmark for Reasoning) spanning core domains of applied mathematics, including convex analysis, optimization, numerical algebra, and high-dimensional probability. Aside from theorem proving, our benchmark features complex tasks such as evaluation, algorithm design, and representation transformation. Experiments reveal that current models face significant difficulties with these constructive tasks. Notably, we observe that general-purpose reasoning models consistently outperform specialized theorem provers. We attribute this to a degradation of instruction following capabilities in specialized models. Fine-tuning on proof corpora appears to induce “tactical overfitting”, compromising the ability to adhere to complex constructive requirements, whereas general models retain the versatility needed for multi-task formal reasoning.

- **Q1**：**否**
  - 「compelling the agent to define explicit solutions before proving their correctness」（摘要，PDF p.1）。流程為固定的「先構造、後證明」順序，未見依失敗或僵局觸發的機制。
- **Q2**：**否**
  - 「Ablation results on the 100-problem subset.」（表 3，PDF p.9）；§5.3 標題為「Ablation Study on Prompts」（PDF p.8）。消融對象是提示形式，未涉及觸發時機。
- **Q3**：**否**
  - 比較的是提示形式，而非提供輔助構造、引理或子目標。§5.3 的三組條件為：construction-verification 提示、標準程式補全（standard code completion）、僅證明（proof only）。表 3 列出「Construction-Verification 8/100」，正文另述「drops to 6% with standard completion」，依此可見三組成功率為 8、6、5（以 100 題子集計）。
- **Q4（基準與規模）**：「the dataset contains an exact split of 100 Easy and 100 Hard problems.」（PDF p.20）。即 Easy 100 題與 Hard 100 題，合計 200 題。
- **Q5（模型；是否開源）**：
  - 「We access proprietary models via their official APIs」（附錄 D.1，PDF p.22），包括 DeepSeek-V3.2-Thinking 與 GPT-5.1。
  - 「we locally deploy prominent open-source models fine-tuned for formal mathematics, including Kimina-Prover and Goedel-Prover」（附錄 D.1，PDF p.22）。
  - 基準資料與程式碼是否釋出：**文中未提**（全文未找到 repository 或資料下載連結）。
- **Q6（與本工作的關係）**：同為 Lean 4 基準，但本篇量測的是提示形式對成功率的影響，而非提供輔助構造或引理的差距。本篇的模型與基準與本工作（DeepSeek-Prover-V2-7B、`lean_hard`）不同，結果不可直接比較。

---

## 4. NanoProof: Open and Efficient Automated Theorem Proving in Lean 4

- **書目**：NanoProof: Open and Efficient Automated Theorem Proving in Lean 4；Matěj Kripner, Milan Straka（共 2 位作者）；arXiv:2610.11605；提交日期 2026-10-08（API `published`）。
- **摘要原文**：

> We introduce NanoProof, to our knowledge the first factorized execution-guided theorem prover in Lean 4 whose training data, extraction tooling, training pipeline, and weights are all released, making it end-to-end reproducible using open-source resources. To this end, we build and release a dataset of structured proof trees, as well as a tool for programmatic interaction and data extraction within the Lean 4 formal verifier. To support sustainable research, we focus on compute efficiency to facilitate accessible training and evaluation. NanoProof achieves 50.8% pass@16 on MiniF2F-Test, exceeding the two closest systems of its class, HyperTree Proof Search and ABEL, at roughly 90× and 7× less compute, and using more than four orders of magnitude less compute than AlphaProof. Stronger open-weight provers exist, but they are fine-tuned from large pretrained language models and release neither training data nor pipeline; NanoProof shows that the factorized execution-guided class of provers can be rebuilt from scratch with modest resources.

- **Q1**：**文中未提**
  - 「to split proof states into separate branches that can be explored independently」（引言，PDF p.1–2）。文中描述 factorized search 允許分裂證明狀態，但未說明何時觸發分裂或重構的規則。
- **Q2**：**否**
  - 「the absence of proper ablations: only diverse tactic sampling」與「is ablated, while the other search-level techniques are re-」（限制段落，PDF p.9）。作者自述只消融了 diverse tactic sampling，未對觸發時機做消融。
- **Q3**：**文中未提**。實驗中未找到「給／不給提示（輔助構造、引理、子目標）」的對照設定。
- **Q4（基準與規模）**：
  - MiniF2F-Test：「NanoProof achieves 50.8% pass@16 on MiniF2F-Test」（摘要，PDF p.1）。
  - 題數：文中未明列 MiniF2F-Test 題數。附錄估算文字中出現「test set size 244」（PDF p.16），但未明指為 MiniF2F-Test，因此不採用為該基準的題數。
- **Q5（模型；是否開源）**：
  - 模型：1B 參數（「Total Parameters 1B」，Table 1，PDF p.13）；以 Nemotron-CC-Math-4+ 前 10B tokens 作基底訓練（實驗章節）。
  - 開源：「are all released, making it end-to-end reproducible using」（摘要，PDF p.1）。
  - 原始碼：「The Python package and its source code is available at https://github.com」（註腳，PDF p.2）。文字檔中網址被截斷，完整網址未確認。
- **Q6（與本工作的關係）**：本篇強調可重現性與計算量，可作為開放釋出的參考點。本篇未量測提示差距（Q3 文中未提），與本工作的研究問題不重疊。模型為 1B 參數、以數學文本從頭基底訓練，與本工作的 DeepSeek-Prover-V2-7B 不同。

---

## 5. Learning to Reason with Insight for Informal Theorem Proving

- **書目**：Learning to Reason with Insight for Informal Theorem Proving；Yunhe Li, Hao Shi, Bowen Deng et al.；arXiv:2604.16278；提交日期 2026-04-17（API `published`；PDF 為 v2，蓋章日期 2026-05-29）。
- **摘要原文**：

> Although most of the automated theorem-proving approaches depend on formal proof systems, informal theorem proving can align better with large language models’ (LLMs) strength in natural language processing. In this work, we identify a primary bottleneck in informal theorem proving as a lack of insight, namely the difficulty of recognizing the core techniques required to solve complex problems. To address this, we propose DeepInsight, a unified training framework designed to cultivate this essential reasoning skill and enable LLMs to perform insightful reasoning. Our framework consists of three components: (1) DeepInsightTheorem, a hierarchical dataset that structures informal proofs by explicitly extracting core techniques and proof sketches alongside the final proof; (2) a Progressive Multi-Stage SFT strategy that mimics the human learning process, teaching the model proof writing, planning, and insight identification; and (3) InsightPO, a policy optimization method that assigns structured rewards over this insight hierarchy. Our experiments on challenging mathematical benchmarks demonstrate that this insight-aware generation strategy significantly outperforms baselines. These results demonstrate that teaching models to identify and apply core techniques can substantially improve their mathematical reasoning.

- **Q1**：**否**
  - 訓練採固定階段：「For a given base model, we first fine-tune it on the theorem-proof pairs for 3 epochs, then on the」（PDF p.7）；之後為 theorem-sketch-proof 與完整階層資料各 3 epochs。依固定排程進行，未見依失敗或僵局觸發。
- **Q2**：**否**
  - 「Two-Stage Training: This is a streamlined」（PDF p.7）。比較的是階段數（two-stage 對 three-stage），未涉及觸發時機。
- **Q3**：**文中未提**
  - 「higher when incorporating insight, especially for」（PDF p.8）。文中未明確定義「incorporating insight」所對應的對照條件，Figure 7 僅有 caption「Max scores in evaluation across benchmarks.」，本筆記未檢視該圖內容。
- **Q4（基準與規模）**：
  - 評測欄位為 FIMO、Putnam、HMMT（表格欄位「FIMO Putnam HMMT」，例見 PDF p.16 附錄表格；正文 Table 2 亦為同一組欄位）。
  - 各基準題數：文中未找到。
- **Q5（模型；是否開源）**：
  - 「two open-source model families: Qwen2.5」與 Llama3（PDF p.7），實驗包括 Qwen2.5 1.5B/3B/7B 與 Llama3 系列。
  - 「DeepSeek-R1 as the verifier」（PDF p.7）。另以 o3-mini 作第二評審。
  - 程式碼與資料是否釋出：**文中未提**。
- **Q6（與本工作的關係）**：本篇處理非形式化（informal）證明，與本工作的 Lean 4 形式化設定不同。本篇的「insight」是訓練時提供的核心技巧，與提示概念相近，但論文未量測推論時給予提示的成功率差距（Q3 文中未提）。兩者不可直接比較。

---

## 總結

- **ProofEvolve 是否已做觸發時機的消融：否。**
  - 依據一：「We remove one operator at a time on the 60 IMO-LeanProofBench problems.」（§5.4，PDF p.9）。消融對象為三種算子（decomposition、recombination、repair）的移除。
  - 依據二：Algorithm 1 以「是否有 rejected edit」決定 repair 分支（PDF p.15）。此條件存在，但論文未對它做消融。
- 就本筆記已讀的段落而言，HAGeo 與 ProofEvolve 有「依失敗觸發」的設計（HAGeo：初始 DDAR 失敗後才加輔助構造；ProofEvolve：repair 僅在 rejected proposal 後觸發），且兩者的消融都未比較觸發時機。其餘三篇未找到類似的觸發設計（NanoProof 未詳述搜尋分裂規則，見其 Q1）。

## 未確認或待作者決定

- HAGeo 表 2 的 DDAR 列是否即「不加輔助構造」，論文未明文標示（Q3 為依流程的推論）。
- NanoProof 完整原始碼網址在文字檔中被截斷。
- DeepInsight 的 Figure 7 內容未檢視；各篇 PDF 中的表格數字未逐一重算。
- 摘要中的連字號依版面還原；若要與論文正式版逐字比對，建議以 arXiv 網頁版為準。
