# Synthetic pipeline demo — demo-only

All text here was created for this repository's software demonstration. None is
copied from a real article or used in the paper. `DEMO-*` strings occupy the
loader's `pmid` field solely as synthetic article IDs; they are **not PubMed IDs**.
Labels distinguish red/blue imaginary shapes, not scientific integrity.

| File | Articles | Role |
|---|---:|---|
| `demo_positive.jsonl` | 12 | Internal positive-role toy examples |
| `demo_negative.jsonl` | 12 | Internal negative-role toy examples |
| `demo_external_positive.jsonl` | 4 | Disjoint external positive-role examples |
| `demo_external_negative.jsonl` | 4 | Disjoint external negative-role examples |

After installing the repository requirements, run from the repository root:

```bash
bash run_demo.sh
# A second run needs a fresh directory:
bash run_demo.sh --output-dir runs/demo-second
```

No network, API key, pretrained checkpoint, GPU, or research corpus is needed at
runtime. `PYTHON=/path/to/python bash run_demo.sh` selects a Python environment.
The demo creates a local WordPiece tokenizer from `vocab.txt`, initializes a tiny
BERT randomly (hidden size 8, one layer, two heads), preprocesses text, and runs
the actual `train.py` and `evaluate.py` on CPU for one epoch. It retains the
production code's PMID-level split, validation threshold and mean chunk score.
This tests pipeline mechanics; its scores have no research interpretation.

Demo preprocessing is a **new recipe**, not recovered paper preprocessing:
`title.strip() + "\n\n" + abstract.strip()`, single-sequence tokenization without
special tokens, windows of 30 content tokens plus `[CLS]`/`[SEP]` (32 total),
overlap of 4 content tokens (step 26), retained short final window, zero-based
chunk indices, no saved padding. The loader pads within each batch. Text lengths
vary deliberately so the demo includes multi-chunk articles and short tails.

Outputs under ignored `runs/demo/` include:

- tokenized JSONL and preprocessing manifests (input/output/tokenizer hashes);
- `training/split_manifest.json`, `training/best_model/`, `training/threshold.json`;
- internal and external article-level predictions and metrics;
- `external/external_chunk_predictions.jsonl` and `DEMO_SUMMARY.json`.

The internal 24 articles split into 16 train / 4 validation / 4 test with the
current splitter's rounding. The 8 external articles are disjoint. Existing output
directories containing files are rejected. All source rows and preprocessing
manifests are marked `demo-only`; standard train/evaluate result schemas do not
propagate that field, so retain the enclosing `DEMO_SUMMARY.json` with the run.
