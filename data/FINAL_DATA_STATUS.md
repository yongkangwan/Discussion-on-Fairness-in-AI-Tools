# Final data package status

This file records what has been verified for the public release and what is still missing.

## Verified and included

The repository now includes **paper-level aggregate result tables** transcribed from the accepted manuscript:

- `paper_results/reproduction_metrics.csv`
- `paper_results/fairness_audit_summary.csv`
- `paper_results/controlled_experiments_summary.csv`
- `paper_results/paired_outcomes.csv`

These are small, derived tables and do not redistribute third-party article text.

## Final article-level cohort files are not yet available here

The accepted manuscript refers to article-level cohorts for:

1. reproduction / validation;
2. the 5,000 non-native-English-proxy high-impact papers;
3. the 5,000 native-English-proxy high-impact papers;
4. source papers used for controlled rewriting experiments.

The current GitHub repository does **not** contain a verified final artifact set that can be tied to the accepted manuscript's headline numbers. The old private working artifacts previously stored in this repository produced different summary values and therefore must not be released as the final paper data.

A search of the currently accessible project files found the manuscript, but no separate final cohort files or controlled-experiment artifacts matching the accepted-paper numbers.

## What is needed to finish the release

To finalize the public article-level package, locate the exact files used for the accepted manuscript and export only:

### `reproduction_cohorts.csv`

Recommended columns:

```text
pmid,split,benchmark_label,source_cohort
```

### `fairness_audit_cohorts.csv`

Recommended columns:

```text
pmid,analysis_group,sample_id
```

where `analysis_group` should use transparent proxy labels such as
`non_native_english_proxy` and `native_english_proxy`.

### Controlled experiments

For generated experiments, release:

```text
experiment,sample_id,pair_id,style,score,prediction
```

plus the exact prompts and generation configuration used in the accepted paper.

For experiments derived from real papers, prefer releasing identifiers, pair mappings, prompts/configuration, and model outputs rather than redistributing source article text unless redistribution rights have been checked.

## Integrity rule

Do not populate the article-level files by reverse-engineering or approximating the manuscript's aggregate statistics. They must come from the exact final artifacts used to produce the accepted paper.
