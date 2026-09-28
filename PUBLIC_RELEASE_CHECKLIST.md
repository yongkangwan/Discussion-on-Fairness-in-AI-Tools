# Public release checklist

This file is for release preparation and should be removed or converted into an issue before the repository is made public.

## Blocking items

- [ ] Add the final, de-anonymized author list.
- [ ] Add the paper-specific OpenReview/forum URL and final paper link.
- [ ] Choose and add a code license.
- [ ] Export final PMID-only cohort files from the exact artifacts used in the accepted paper.
- [ ] Add the **exact preprocessing/tokenization code** used to build the pre-tokenized JSONL inputs.
- [ ] Add the code/prompts/configuration for the paper's four controlled LLM experiments.
- [ ] Reconcile the repository experiment report with the accepted manuscript.

## Important result mismatch to resolve

The current private repository's `EXPERIMENT_REPORT.md` does **not** match the final manuscript's reported values.

Examples:

- Current repo report: China/Other screening mean scores are approximately 0.267 / 0.012.
- Accepted manuscript: non-native/native high-impact groups are reported as 42.0% / 2.0%.
- Current repo report: internal test accuracy is approximately 95.3%.
- Accepted manuscript Table 1: reproduction internal accuracy is reported as 97%.

Do not publish the old experiment report as the canonical result record until the exact final artifacts are identified.

## Repository hygiene

- [ ] Remove raw JSONL files containing titles/abstracts/affiliations.
- [ ] Remove manifests containing absolute private filesystem paths.
- [ ] Remove hard-coded local paths.
- [ ] Rename `test.py` to a clearer evaluation entry point if desired and update tests/imports.
- [ ] Replace or remove `negtive_exclude_positive.py`; it contains hard-coded local Windows paths and a typo in the filename.
- [ ] Add a one-command smoke/demo workflow after the final data-preparation pipeline is fixed.
- [ ] Add CI for `pytest`.
- [ ] Run secret scanning before publication.
- [ ] Create the public repository from a **clean tree without the private repository's Git history**.
