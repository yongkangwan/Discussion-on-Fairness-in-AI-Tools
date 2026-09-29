# Data inventory and provenance

This directory contains article identifiers, aggregate result tables and synthetic
examples for the training and evaluation pipeline:

| Location | Category | Scope |
|---|---|---|
| [`paper_results/`](paper_results/) | Paper-reported aggregate results | Existing manuscript transcriptions, not recomputed using this release |
| [`pmids/historical/`](pmids/historical/) | Versioned historical data | PMID-only source pools and archived samples, not final-paper cohort assignments |
| [`examples/`](examples/) | **Demo-only** | 32 synthetic articles; safe offline text-to-chunk-to-training/evaluation example |
| `generated/` (ignored) | New reconstruction | Current provider text and newly configured preprocessing, stored locally |

Start with [DATA_CARD.md](DATA_CARD.md) for cohort meanings, source provenance,
verified processing rules, training configuration and preprocessing details, and reconstruction
commands. [pmids/README.md](pmids/README.md) lists each recovered cohort with
counts and explains verification. [FINAL_DATA_STATUS.md](FINAL_DATA_STATUS.md)
tracks the remaining gaps.

## Run the demo

After installing the top-level requirements, from the repository root:

```bash
bash run_demo.sh
python scripts/verify_pmid_release.py
```

The demo uses a tiny randomly initialized BERT and synthetic `DEMO-*` article
identifiers. Its scores demonstrate pipeline behavior and are not scientific results.
See [examples/README.md](examples/README.md) for inputs, parameters and outputs.

## Export a newly recovered, verified source

```bash
python scripts/export_pmids.py --input /path/to/source.jsonl --output /path/to/cohort.txt
python scripts/export_pmids.py --input /path/to/source.jsonl.manifest.json \
  --input-format sampling-manifest --output /path/to/cohort.txt
```

Exports are unique numeric PMIDs, sorted numerically, one per line. Synthetic
IDs are rejected. Exporting identifiers alone does not verify experimental role
or final-paper membership: record source revision/blob, hashes, counts, labels,
split evidence and provenance before adding a list to this release.

## Minimal redistribution

We publish identifiers, source/run metadata, derived aggregate tables, code and
original synthetic examples. We do not republish source titles/abstracts, author
affiliations, PubPeer text, full text, or historical token arrays (which may allow
reconstruction of text). Retrieval utilities save provider records locally and
mark them as new reconstructions; provider records may have changed since the
historical experiments. A PMID match does not establish a text-version match.

Training generates the PMID split, selects the model, and derives the final
threshold from the internal validation set. These methods are implemented in
code; their per-run outputs are `split_manifest.json`, `best_model/` and
`threshold.json`. Original saved outputs for every paper experiment are not
included. [FINAL_DATA_STATUS.md](FINAL_DATA_STATUS.md) distinguishes these missing
artifacts from the available methods and settings.
