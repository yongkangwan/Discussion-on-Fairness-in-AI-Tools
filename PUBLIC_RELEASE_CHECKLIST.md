# Public release checklist

This file is for release preparation and should be removed or converted into an issue before the repository is made public.

## Completed data-release work

- [x] Add paper-derived aggregate tables under `data/paper_results/`.
- [x] Document that final article-level PMIDs must come from the exact accepted-paper artifacts, not the older mismatched working data.

## Earlier validation (before the 2026-09-29 data additions)

- [x] GitHub Actions CI is passing on the cleaned current tree.
- [x] Earlier cleanup removed private filesystem paths from runtime defaults. Historical filenames now appear intentionally in provenance documentation.

## Blocking items

- [ ] Add the final, de-anonymized author list.
- [ ] Add the paper-specific OpenReview/forum URL and final paper link.
- [ ] Choose and add a code license.
- [ ] Recover final accepted-paper PMID/cohort files from an independent backup, if one exists. If none can be recovered, document the available source versions and limits of exact numerical reproduction.
- [ ] Add the **exact preprocessing/tokenization code** used to build the pre-tokenized JSONL inputs.
- [ ] Recover or reconstruct from surviving records the code/prompts/configuration for the paper's four controlled LLM experiments, clearly labeling anything reconstructed after acceptance.
- [x] Document the author-supplied shared-scenario generation prompt design and paired-data checks in `prompts/`; exact historical requests, generation settings and other experiment prompts remain pending.
- [x] Distinguish paper-reported aggregate tables, versioned historical cohorts and demo inputs.

## Important result mismatch to resolve

The historical archive's `EXPERIMENT_REPORT.md` does **not** match the final manuscript's reported values.

Examples:

- Archived report: China/Other screening mean scores are approximately 0.267 / 0.012.
- Accepted manuscript: non-native/native high-impact groups are reported as 42.0% / 2.0%.
- Archived report: internal test accuracy is approximately 95.3%.
- Accepted manuscript Table 1: reproduction internal accuracy is reported as 97%.

Do not publish the old experiment report as the canonical result record until the exact final artifacts are identified.

## 2026-09-29 data additions

- [x] Recover 11 versioned historical identifier lists with 22,562 distinct PMIDs.
- [x] Match three sampled cohorts to both JSONL and sampling manifests; verify report hashes for the two audit lists.
- [x] Add data card, provenance manifests, pairwise overlaps, recovery/verification scripts and artifact availability notes.
- [x] Add a runnable synthetic-only demo and explicit new preprocessing/retrieval utilities.
- [x] Preserve manuscript aggregate CSVs unchanged and document the experiment 4 denominator discrepancy.

## Repository hygiene

- [x] Remove raw JSONL files containing titles/abstracts/affiliations from the current release tree.
- [x] Remove manifests containing absolute private filesystem paths from the current release tree.
- [x] Remove the legacy hard-coded local-path filtering script.
- [x] Rename `test.py` to `evaluate.py` and update the smoke test/imports.
- [x] Replace `negtive_exclude_positive.py` with portable `scripts/filter_overlap.py`.
- [x] Add `run_smoke.sh` for a one-command code-path check; a full paper reproduction command remains pending final data preparation.
- [x] Add GitHub Actions CI for `pytest`.
- [x] Scan the current default branch for common credential patterns; no matches found.
- [ ] Before switching visibility to public, rewrite Git history to remove the old raw-data blobs. Exact commands are in `docs/HISTORY_CLEANUP.md`.
