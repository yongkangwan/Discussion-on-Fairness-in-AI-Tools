# Training, evaluation and reproducibility

The repository includes article-level dataset splitting, BERT fine-tuning,
validation-based model and threshold selection, external evaluation, and fairness
analysis. Data identifiers and source versions are listed in
[the PMID inventory](../data/pmids/README.md).

## Configuration implemented in code

[train.py](../train.py) defaults to `bert-base-uncased`, seed 42, 10 epochs,
learning rate `1.4e-5`, weight decay `0.025`, cosine scheduling with 15% warm-up,
and train/evaluation batch sizes of 32. Input chunks may contain up to 512 tokens.
Use command-line arguments to change these settings; retain the run configuration
with the outputs.

[paper_mill_common.py](../paper_mill_common.py) deduplicates chunks by
`(pmid, chunk_index)` and splits articles, stratified by label, into 70% training,
17.5% internal validation and 12.5% internal test. All chunks from an article stay
in one partition. The split is generated from the input PMID/label set and seed,
and written to `split_manifest.json`.

## Model selection and the final threshold

1. Train on training-set chunks. Select the checkpoint with the lowest internal
   validation chunk cross-entropy loss, using validation article AUROC to break ties.
2. Reload that checkpoint and predict the internal validation set. Average the
   chunk softmax positive probabilities to obtain one score per article.
3. Derive the final threshold **only from internal-validation article scores**.
   The default objective maximizes Youden's index (sensitivity + specificity − 1).
   Ties prefer specificity, then sensitivity, then the higher threshold.
4. Save the result in `threshold.json`, including the value, objective, run ID,
   selected epoch and `selection_set: "internal_validation"`. Per-epoch thresholds
   in the training history are diagnostic; the saved final threshold uses the
   selected checkpoint.
5. Freeze the model and threshold before evaluating internal test or external
   cohorts. An article is positive when its mean score is at least the threshold.

The threshold-selection method is fully implemented; no manually chosen cutoff
is needed for training. Its numeric value depends on the trained model and
validation predictions, so it is a **run output**, not a universal model setting.

## Running and retaining a run

Follow the [README training command](../README.md#training-the-bert-classifier).
Retain these outputs together:

| Artifact | Purpose |
|---|---|
| `split_manifest.json` | Exact article assignments, input hashes and labels |
| `run_config.json` | Training settings and environment |
| `best_model/` | Model weights, tokenizer and checkpoint selection metadata |
| `threshold.json` | Final internal-validation cutoff and its run identity |
| `training_history.json` | Per-epoch training and validation results |
| Prediction JSONL and result JSON files | Per-article scores and aggregate metrics |

Use the same run's checkpoint and threshold for external evaluation:

```bash
python evaluate.py \
  --model-dir runs/my_run/best_model \
  --threshold-file runs/my_run/threshold.json \
  --positive-files /path/to/external_positive.jsonl \
  --negative-files /path/to/external_negative.jsonl \
  --output-dir runs/my_run/external
```

`evaluate.py` checks model/threshold run IDs when present, checks cohort overlap
using the training manifest, and loads the saved cutoff without selecting a new
one on external data.

## Text preprocessing and data versions

Training consumes pre-tokenized JSONL. The loader validates chunk length, indices
and token arrays and dynamically pads batches; raw-text composition and chunk
boundaries are upstream preprocessing steps. The documented preprocessing utility
provides an explicit recipe for new inputs, while original generator settings
not established by archived records remain listed in
[the data card](../data/DATA_CARD.md).

Paper-reported tables, historical cohorts and synthetic demo data are versioned
separately. Some original input snapshots and saved run artifacts are not included.
The available code specifies how to generate splits, select models and calculate
thresholds; exact replay of a particular historical result also needs its inputs,
software environment and saved artifacts. See
[data availability](../data/FINAL_DATA_STATUS.md).

## Offline checks

For a full BERT-base CUDA/FP16 check with 512-token inputs, see the
[GPU setup and validation guide](GPU_VALIDATION.md). It includes the tested
environment and a synthetic functional-check report with timing and memory peaks.

After installing requirements:

```bash
bash run_demo.sh
python scripts/verify_pmid_release.py
python -m pytest -q
```

The synthetic demo runs preprocessing, training and evaluation without network
access. Its scores verify pipeline behavior and are not scientific results.
