# Data release policy

This project uses bibliographic identifiers and text retrieved from external scholarly databases. The public repository follows a **minimal-redistribution** policy.

## What we release

The intended public data package contains only the information needed to reconstruct experimental cohorts without republishing third-party article text:

- PubMed identifiers (PMIDs)
- cohort membership / experimental role
- labels used by the reproduction pipeline
- deterministic sampling metadata
- hashes and manifests needed for reproducibility

## What we do not release

The public repository should not contain:

- copied PubMed titles or abstracts
- author affiliations copied from PubMed records
- PubPeer comments or other PubPeer page text
- full-text articles
- internally cached third-party text

Users should retrieve source text directly from the relevant provider and comply with the provider's current terms, licenses, and access policies.

## Exporting PMIDs from an internal working copy

If you have access to the private working data, use:

```bash
python scripts/export_pmids.py \
  --input path/to/internal_cohort.jsonl \
  --output data/pmids/cohort.txt
```

The script reads the `pmid` field, de-duplicates identifiers, sorts them deterministically, and writes one PMID per line. It does not copy titles, abstracts, affiliations, or token arrays.

Multiple files can be combined:

```bash
python scripts/export_pmids.py \
  --input file_a.jsonl file_b.jsonl file_c.jsonl \
  --output data/pmids/combined_cohort.txt
```

## Rebuilding model inputs

The current training code consumes pre-tokenized JSONL. Before the public release is finalized, the exact preprocessing/tokenization script used for the accepted-paper experiments should be included here so that users can rebuild those inputs from the released PMID lists.

Do **not** substitute a newly invented preprocessing pipeline for the one used in the paper: tokenization/chunking choices affect reproducibility.

## Cohorts to export before release

The final release should provide PMID lists corresponding to the paper's experimental cohorts, including:

- reproduction training / validation / test sources
- external validation cohorts
- the 5,000-paper non-native-English high-impact sample
- the 5,000-paper native-English high-impact sample
- any source-paper cohorts used in the controlled rewriting experiments, where redistribution is permitted

Exact filenames should be documented once the final experiment artifacts are reconciled with the accepted manuscript.
