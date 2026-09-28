# Data release policy

This repository uses a **minimal-redistribution** data policy.

## Included now

Paper-derived aggregate tables are available under `paper_results/`:

- `reproduction_metrics.csv`
- `fairness_audit_summary.csv`
- `controlled_experiments_summary.csv`
- `paired_outcomes.csv`

These summarize the results reported in the accepted manuscript.

## Article-level public data

The intended final article-level package will contain only identifiers and experiment metadata needed to reconstruct the cohorts:

- PMIDs
- split / cohort membership
- benchmark labels or analysis-group labels
- deterministic sampling metadata
- hashes/manifests
- controlled-experiment pair IDs, prompts/configuration, and model outputs where appropriate

The exact final article-level files are **not yet included**, because the currently accessible repository artifacts do not match the accepted manuscript's headline values. See [FINAL_DATA_STATUS.md](FINAL_DATA_STATUS.md).

## Not redistributed

The public repository should not contain:

- copied PubMed titles or abstracts
- author affiliations copied from PubMed records
- PubPeer comments or other PubPeer page text
- full-text articles
- internally cached third-party text

Users should retrieve source text directly from the relevant provider and comply with the provider's current terms, licenses, and access policies.

## Exporting PMIDs from a verified final working copy

After the exact accepted-paper artifacts are located:

```bash
python scripts/export_pmids.py \
  --input path/to/verified_final_cohort.jsonl \
  --output data/pmids/cohort.txt
```

The script reads only the `pmid` field, de-duplicates identifiers, and writes one PMID per line.

## Rebuilding model inputs

The training code consumes pre-tokenized JSONL. The final public release should include the exact preprocessing/tokenization code used for the accepted-paper experiments so that users can rebuild model inputs from the released identifiers.

Do not substitute an approximate preprocessing pipeline: tokenization and chunking choices affect reproducibility.
