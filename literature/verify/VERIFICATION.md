# Reference verification: docs/research-design.md (section 13 and in-text citations)

Checked 2026-11-02. The source doc was not edited. Sources: arXiv API, Crossref, WebSearch, one WebFetch (Meta AutoformBench page).

## Verdict table

| # | Doc line | Cited as | Verdict | Evidence |
|---|---|---|---|---|
| 1 | 617 | Doulfoukar, Pezzulo & Stuyck (2026). *Unveiling the Aha! moment...* Psychonomic Bulletin & Review | **CORRECTED**: preprint exists, PBR publication not found | Crossref: OSF/PsyArXiv preprint, DOI 10.31234/osf.io/3nasx (v1 2025-02-16, v2 2026-04-08, v3 2026-07-18), same title and authors. Crossref filtered to PBR returns nothing. Web search found no PBR paper by these authors. Cite as preprint until a journal version is shown. https://doi.org/10.31234/osf.io/3nasx |
| 2 | 616 | Danek, A. H., & Salvi, C. (2023). *Restructuring processes and Aha! experiences...* Nature Reviews Psychology | **CORRECTED**: authors are Wiley & Danek; Salvi is not an author | Crossref: DOI 10.1038/s44159-023-00257-x, Nat Rev Psychol 3:42-55. Authors: Jennifer Wiley and Amory H. Danek (Heidelberg catalogue). Online 2023-12-14, issue 2024. https://doi.org/10.1038/s44159-023-00257-x |
| 3 | 630 | Hubert et al. (2025). *Olympiad-level formal mathematical reasoning with RL.* Nature | **VERIFIED** | Crossref: DOI 10.1038/s41586-025-09833-y, Nature, online 2025-11-12. The URL in the doc matches the DOI. https://doi.org/10.1038/s41586-025-09833-y |
| 4 | 632 | Duan et al. (2025/2026). *Gold-medal-level olympiad geometry solving...* arXiv:2512.00097 | **VERIFIED** (venue added) | arXiv 2512.00097, 2025-11-27, 10 authors, first author Boyan Duan. Web: ACL 2026 long paper, acl-long.991. https://arxiv.org/abs/2512.00097 |
| 5 | 633 | ProofEvolve (2026), arXiv:2608.26334 | **VERIFIED** | arXiv 2608.26334, 2026-08-26, *ProofEvolve: Neuro-Symbolic Evolution for Formal Automated Theorem Proving*, Ye, Guan, Xie et al. (9 authors). https://arxiv.org/abs/2608.26334 |
| 6 | 634 | Kripner & Straka (2026). NanoProof, arXiv:2610.11605 | **VERIFIED** | arXiv 2610.11605, 2026-10-08, *NanoProof: Open and Efficient Automated Theorem Proving in Lean 4*, Matěj Kripner and Milan Straka. https://arxiv.org/abs/2610.11605 |
| 7 | 635 | AutoformBench (2026). "NeurIPS 2026 MATH-AI workshop" | **VERIFIED that it exists; venue CORRECTED** (no NeurIPS evidence) | Meta publication page dated 2026-10-13, *AutoformBench: A Lean Formalization Benchmark for Advanced Mathematics*, 341 Lean 4 tasks from 24 sources. 9 authors: Charles Arnal, Ahmad Rammal, Niket Patel, Fabian Gloeckle, Bartosz Piotrowski, Amaury Hayat, Julia Kempe, Remi Munos, Vivien Cabannes. Code: github.com/facebookresearch/autoformbench. No arXiv ID shown and no NeurIPS/workshop mention. Do not cite the NeurIPS venue. An arXiv title search returns only an unrelated form-understanding paper (2603.29832). https://ai.meta.com/research/publications/autoformbench-a-lean-formalization-benchmark-for-advanced-mathematics |
| 8 | 636 | Construction-Verification benchmark (2026), arXiv:2602.01291 | **VERIFIED** | arXiv 2602.01291, 2026-02-01, *Construction-Verification: A Benchmark for Applied Mathematics in Lean 4*, Bowen Yang et al. (8 authors). https://arxiv.org/abs/2602.01291 |
| 9 | 637 | Claessen, K., et al. (2013). QuickSpec | **CORRECTED**: year is 2010; venue TAP 2010 (LNCS) | Crossref: *QuickSpec: Guessing Formal Specifications Using Testing*, Claessen, Smallbone, Hughes, 2010, LNCS, DOI 10.1007/978-3-642-13977-2_3. The doc's 2013 is wrong. https://doi.org/10.1007/978-3-642-13977-2_3 |
| 10 | 638 | Johansson et al. (2014). Hipster, arXiv:1405.3426 | **VERIFIED** | arXiv 1405.3426, 2014-05-14, *Hipster: Integrating Theory Exploration in a Proof Assistant*, Johansson, Rosen, Smallbone, Claessen. Venue not checked. https://arxiv.org/abs/1405.3426 |
| 11 | 646 | CombiBench (2025), authors to verify | **VERIFIED** (metadata added) | arXiv 2505.03171, 2025-05-06, *CombiBench: Benchmarking LLM Capability for Combinatorial Mathematics*, Junqi Liu, Xiaohan Lin, Jonas Bayer, Yael Dillies et al. (16 authors). https://arxiv.org/abs/2505.03171 |
| 12 | 645 | Liu, C., et al. (2023). FIMO | **VERIFIED** (arXiv id added) | arXiv 2309.04295 (v2), 2023-09-08, *FIMO: A Challenge Formal Dataset for Automated Theorem Proving*, Chengwu Liu et al. (12 authors). https://arxiv.org/abs/2309.04295 |
| 13 | 554, 377, 418, 425 | HAGeo | **VERIFIED** as the system from item 4, not a separate paper | HAGeo is the name used for the method and its HAGeo-409 benchmark in Duan et al., arXiv 2512.00097 (ACL 2026). Web summaries (emergentmind) report 83.0% vs 39.3% for AlphaGeometry on HAGeo-409. Those numbers come from secondary sources and were not checked against the paper. Cite it as Duan et al. |
| 14a | 625 | Melis & Whittle (1999). JAR | **VERIFIED** | Crossref: *Analogy in Inductive Theorem Proving*, DOI 10.1023/A:1005936130801, Journal of Automated Reasoning, 1999-02. https://doi.org/10.1023/A:1005936130801 |
| 14b | 619 | Lovett & Anderson (1996). Cognitive Psychology | **VERIFIED** | Crossref: *History of Success and Current Context in Problem Solving*, DOI 10.1006/cogp.1996.0016, Cognitive Psychology, 1996-10. https://doi.org/10.1006/cogp.1996.0016 |
| 14c | 618 | VanLehn (1989). Foundations of Cognitive Science | **VERIFIED** | Crossref: *Problem Solving and Cognitive Skill Acquisition*, DOI 10.7551/mitpress/3072.003.0016, in *The Foundations of Cognitive Science*, 1989-11. https://doi.org/10.7551/mitpress/3072.003.0016 |
| 15a | 209, 473, 647 | LeanInteract | **EXISTS as software only** | GitHub augustepoiroux/LeanInteract and PyPI package lean-interact. No dedicated arXiv paper found. Cite as software, not as a paper. https://github.com/augustepoiroux/LeanInteract |
| 15b | 209, 473, 647 | LeanTree | **VERIFIED** | arXiv 2507.14722, 2025-07-19, *LeanTree: Accelerating White-Box Proof Search with Factorized States in Lean 4*, Matěj Kripner, Michal Šustr, Milan Straka. ICML 2025 virtual listing (icml.cc/virtual/2025/52384). https://arxiv.org/abs/2507.14722 |
| extra | 626 | Polu & Sutskever (2020), arXiv:2009.03393 | **VERIFIED** | arXiv 2009.03393, 2020-09-07, *Generative Language Modeling for Automated Theorem Proving*. https://arxiv.org/abs/2009.03393 |
| not checked | 624 | Melis (1995). IJCAI | NOT CHECKED | Outside the requested list. |

## Summary of problems

- **No outright fabrications found.** Every item except AutoformBench's venue matches a real record.
- **Misattributions to fix before citing:**
  - Danek & Salvi: the author is wrong. It should be Wiley & Danek (line 616).
  - Doulfoukar et al.: the Psychonomic Bulletin & Review venue was not found. Only the OSF/PsyArXiv preprint exists (line 617).
  - AutoformBench: the NeurIPS 2026 MATH-AI workshop venue is not supported by any source found (line 635).
  - QuickSpec: the year should be 2010, not 2013 (line 637).
- **Missing identifiers:** the FIMO arXiv id (2309.04295), the CombiBench arXiv id and authors (2505.03171), and the LeanTree arXiv id (2507.14722) can now be filled in.
- **HAGeo** is not a separate reference. It is the name of the method and benchmark in Duan et al. (line 554 and related lines).

## Downloaded PDFs (open-access arXiv, verified by `file`, all >50KB)

Directory: `/Users/hibiki/Desktop/Japan/SideProject/Mathesis/literature/verify/`

- arxiv_2512.00097.pdf (1.46 MB), Duan et al.
- arxiv_2608.26334.pdf (1.22 MB), ProofEvolve
- arxiv_2610.11605.pdf (1.01 MB), NanoProof
- arxiv_2602.01291.pdf (0.50 MB), Construction-Verification
- arxiv_1405.3426.pdf (0.29 MB), Hipster
- arxiv_2309.04295.pdf (0.30 MB), FIMO
- arxiv_2505.03171.pdf (1.91 MB), CombiBench
- arxiv_2507.14722.pdf (1.16 MB), LeanTree
- arxiv_2009.03393.pdf (0.55 MB), Polu & Sutskever. `file` reports "1 pages", which looks like a metadata quirk. Check it manually.

Not downloaded: AutoformBench (no arXiv id; the only link is a Meta CDN PDF, which was not fetched), Hubert et al. (Nature, paywalled), Doulfoukar (OSF preprint, not arXiv), Danek & Wiley (Nature Reviews, paywalled), QuickSpec and VanLehn (Springer/MIT Press), Lovett & Anderson and Melis & Whittle (paywalled journals).

BibTeX for verified items is in `/Users/hibiki/Desktop/Japan/SideProject/Mathesis/literature/verify/refs.bib`.
