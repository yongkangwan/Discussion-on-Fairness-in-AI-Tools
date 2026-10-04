# Data and run-artifact availability

Updated: 2026-10-04. This page separates implemented training methods from the
input snapshots and saved outputs needed to replay a specific experiment.

## Available data and code

- `paper_results/`: four manuscript-reported aggregate result tables.
- `pmids/historical/`: 11 source-pool and sampled-cohort PMID lists, containing
  22,562 distinct identifiers, with source commits, blob IDs, counts and hashes.
- `DATA_CARD.md`: cohort roles, JSONL schema, preprocessing and training rules.
- `train.py`, `paper_mill_common.py` and `evaluate.py`: article-level splitting,
  model selection, internal-validation threshold selection and evaluation.
- `examples/` and `run_demo.sh`: 32 synthetic articles and an offline end-to-end demo.
- Retrieval, preprocessing and identifier verification utilities.
- [`prompts/`](../prompts/README.md): author-supplied shared-scenario generation
  design, requested output schema and paired-data review guidance. This is an
  approximate account of the design, not a verified historical request log.
- Generation provider: OpenAI, as reported by the author. The latest-flagship
  description as of 2026-04-02 points to GPT-5.4; the exact variant/snapshot is
  unspecified. See the [model note and official source](../prompts/README.md#generation-model).

## Settings and outputs established by the training code

| Item | Implemented rule | Saved output |
|---|---|---|
| Split | PMID-level stratification; 70% / 17.5% / 12.5%, seed 42 by default | `split_manifest.json` |
| Base model | `bert-base-uncased` by default | Run configuration and model config |
| Model selection | Lowest internal-validation chunk loss; article AUROC tie-break | `best_model/` and selection metadata |
| Final threshold | Calculate from internal-validation article probabilities after reloading the selected model; default objective is Youden | `threshold.json`, with `selection_set: "internal_validation"` |
| Evaluation | Freeze the chosen model and threshold for internal test and external data | Article predictions and result summaries |
| Chunk input | Read pre-tokenized arrays; maximum length 512 by default; reject overlength chunks and pad within batches | Source hashes, chunk counts and run configuration |

These methods and defaults are **available**, not pending author confirmation.
Each new training run generates its split membership, selected weights and final
threshold. A saved numeric threshold from another run is not a replacement for
this internal-validation procedure. Full details and commands are in
[docs/REPRODUCIBILITY.md](../docs/REPRODUCIBILITY.md).

## Source versions

The released identifiers were extracted from archive commit
`c61fbf422a1f43e78a94b71cb1b8b28d7407d949`. The three sampled cohorts match both
archived JSONL membership and sampling-manifest chunk counts. The two audit-list
hashes also match the historical experiment report. See
[pmids/README.md](pmids/README.md) for evidence and overlap checks.

That report gives audit mean scores of 0.266995 and 0.012326, while the manuscript
aggregate tables give 0.42 and 0.02. These records describe different results and
remain separately identified. Cohort sizes alone do not establish that all
released identifiers correspond to each manuscript experiment.

## Additional artifacts needed for exact historical replay

- **Run-specific input and split records:** the original mapping from inputs and
  saved `split_manifest.json` to each reported experiment. The splitter itself is
  implemented and can generate assignments for a new run.
- **Upstream data construction:** source retrieval dates, query/filter records,
  journal lists, label/proxy definitions and original tokenizer snapshot. Training
  reads pre-tokenized chunks, so it does not establish original title/abstract
  composition, stride/overlap or short-tail handling.
- **Saved run outputs:** selected trained weights, `threshold.json`, per-article
  predictions and software environment for the original reported run. Model and
  threshold selection rules are documented above.
- **Controlled-experiment records:** exact historical requests, generation
  settings, source/pair mappings and outputs. A shared-scenario prompt design is
  now available; prompts for experiments 1, 3 and 4 remain unavailable.
  Experiment 4's summary lists 3,000 per style whereas the
  paired table totals 2,999; the inclusion record is needed to explain the difference.
- **Historical sampling inputs:** raw `other_20000.jsonl` and the old internal
  `split_manifest.json` for replaying the original eligibility calculation.

The original experiment workspace is reported as unavailable. New retrievals
may contain revised provider records and are labeled `reconstruction`; synthetic
examples remain `demo-only`. This preserves the distinction between executable
methods, versioned data and the evidence needed for exact numerical replay.
