# Final paper data and rebuttal archive status

Updated 2026-09-29. **Author clarification: this repository's working artifacts
were produced during rebuttal and are not fully consistent with the paper's
experiments.** Recovery of an old repository file establishes rebuttal provenance,
not final-paper provenance.

## Available now

- `paper_results/`: four existing aggregate result tables described in the earlier
  release as manuscript transcriptions. Preserved unchanged; not regenerated with
  the available rebuttal code/data or independently checked against a manuscript
  during this audit.
- `pmids/historical/`: identifier-only exports from verifiable old archive blobs
  and sampling manifests, with source commit/blob IDs, counts and SHA-256 checks.
- `DATA_CARD.md`: observed schema, verified loader/splitting/sampling/aggregation
  logic, uncertain original preprocessing settings and explicit provenance levels.
- `examples/` and `run_demo.sh`: synthetic-only inputs and an offline end-to-end
  training/evaluation demonstration. No real-paper text or model is required.
- Explicit new retrieval/preprocessing utilities that mark outputs as
  `reconstruction` or `demo-only` and record hashes and configuration.

## Recovery performed

Inspected both repositories' main trees at
`401799b59bb91874b0e0dab2908b32d3de9bf360`, their available commit history, and the
archive's old PR #1 references. Its old base
`c61fbf422a1f43e78a94b71cb1b8b28d7407d949` exposes source JSONL and three sampled
cohort manifests even though those artifacts are absent from current main.
See [pmids/README.md](pmids/README.md) and [DATA_CARD.md](DATA_CARD.md) for exact
scope and evidence. No old commits were merged into the target repository.

The old report's audit means are 0.266995 and 0.012326, unlike the manuscript
transcriptions' 0.42 and 0.02. We therefore explicitly publish these as rebuttal
historical cohorts. Matching the 5,000-per-group sample sizes cannot resolve the
provenance difference.

## Still not recovered / author confirmation needed

1. Exact paper-used cohorts, labels, exclusions and train/validation/test
   assignments, together with evidence connecting them to manuscript tables.
2. Original text snapshots and acquisition dates; query strings, journal lists,
   inclusion/exclusion rules, and language/geography proxy construction.
3. Original text composition and chunk generator: tokenizer revision, prefix
   handling, special tokens, stride/overlap, normalization, tail and padding rules.
4. Paper-run checkpoint, frozen threshold, environment and per-article outputs.
5. Controlled experiments' prompts, generation configuration, source PMIDs where
   applicable, sample/pair IDs, outputs and exclusion log. Experiment 4's summary
   says 3,000 per style while its paired table totals 2,999; do not invent the
   missing pair or alter the published transcription without confirmation.
6. Historical raw `other_20000.jsonl` and original `split_manifest.json`, needed
   to fully replay the archived sampling eligibility and exact internal split.

Earlier repository documentation records that the final AutoDL workspace is no
longer available. Independent author/collaborator backups would be needed to
resolve these gaps. No new broad backup search is claimed here.

## Release rule

Keep **paper-reported aggregate data**, **verified historical rebuttal data**,
**demo-only data**, and **new reconstructions** distinct. Do not reverse-engineer
article membership from aggregate statistics, or infer original chunking from
plausible BERT defaults. A regenerated run should receive a new run ID and should
not be described as the paper's original experiment.
