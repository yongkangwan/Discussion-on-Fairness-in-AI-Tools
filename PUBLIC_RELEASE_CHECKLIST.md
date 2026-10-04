# Release status

Updated: 2026-10-04.

## Verified

- [x] Training, evaluation, sampling and fairness-analysis code is available.
- [x] PMID cohort lists have source versions, counts, hashes and overlap checks.
- [x] Paper-reported tables, historical cohorts and demo-only inputs are distinguished.
- [x] All four author-supplied generation/rewriting prompt designs are documented.
- [x] CPU tests, offline demo and GitHub Actions pass.
- [x] Full BERT-base CUDA/FP16 training and evaluation pass on an RTX 4090 D;
  see [the GPU guide](docs/GPU_VALIDATION.md).
- [x] The release repository's main history contains no archived raw article
  JSONL datasets. Only curated synthetic examples are included in the current tree.
- [x] Remote inventory contains only main, with no tags or pull requests.
- [x] Checks for common credential patterns found no matches in inspected text.

## Publication metadata

- [ ] Select and add a code license.
- [ ] Add authors, the public paper link and citation metadata when appropriate.

## Further reproducibility artifacts

Additional original request logs, run outputs, source mappings and upstream
preprocessing records would improve exact numerical replay. Their availability
is tracked in [the data status](data/FINAL_DATA_STATUS.md); these are not missing
implementations of the available training or threshold-selection methods.

The private archive remains separate. See [release history](docs/HISTORY_CLEANUP.md)
for the verified history boundary. Changing repository visibility is a separate
GitHub setting; this document does not change it.
