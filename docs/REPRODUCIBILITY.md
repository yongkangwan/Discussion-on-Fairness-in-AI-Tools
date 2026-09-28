# Reproducibility status

The original AutoDL instance used for the final accepted-paper experiments is no longer available.

This repository therefore makes an explicit distinction between **methodological reproducibility** and **exact numerical reproducibility**.

## What remains reproducible

The following parts can still be documented and reproduced:

- the BERT-based training and evaluation pipeline;
- article-level splitting and chunk aggregation logic;
- validation-only threshold selection;
- external evaluation and overlap checking;
- the paper's aggregate result tables;
- the stated cohort-selection criteria;
- the design of the four linguistic-style controlled experiments.

## What is currently missing

The following exact accepted-paper artifacts have not been recovered:

- final article-level PMID lists for the reported cohorts;
- the exact final train/validation/test assignment used for the accepted-paper numbers;
- per-sample outputs for the four controlled experiments;
- the exact prompts and generation configuration used in the final controlled experiments;
- the exact final preprocessing/tokenization artifacts;
- the final trained checkpoint corresponding to the reported accepted-paper results.

The older working data that previously existed in this repository produced different summary values and must not be represented as the exact accepted-paper data.

## Consequence

A reader can reproduce the **method and experimental design**, but should not expect a fresh run to reproduce the accepted paper's exact numeric tables unless the original final artifacts are recovered.

If new cohorts are regenerated from the published criteria, they should be versioned and clearly labeled as a **post-acceptance reconstruction**.

## Data-release principle

The public release follows a minimal-redistribution policy: publish identifiers, cohort metadata, code, prompts/configuration where available, and derived aggregate tables; do not republish third-party article text.
