# Public release checklist

This file is for release preparation and should be removed or converted into an issue before the repository is made public.

## Completed data-release work

- [x] Add paper-derived aggregate tables under `data/paper_results/`.
- [x] Document that final article-level PMIDs must come from the exact accepted-paper artifacts, not the older mismatched working data.

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

- [x] Remove raw JSONL files containing titles/abstracts/affiliations from the current release tree.
- [x] Remove manifests containing absolute private filesystem paths from the current release tree.
- [x] Remove the legacy hard-coded local-path filtering script.
- [x] Rename `test.py` to `evaluate.py` and update the smoke test/imports.
- [x] Replace `negtive_exclude_positive.py` with portable `scripts/filter_overlap.py`.
- [x] Add `run_smoke.sh` for a one-command code-path check; a full paper reproduction command remains pending final data preparation.
- [x] Add GitHub Actions CI for `pytest`.
- [ ] Run secret scanning before publication.
- [ ] Before switching visibility to public, create/rewrite to a **clean history without the removed raw-data blobs**.
