# Reproducibility scope

The authors clarify that this repository's working code/data arose during
**rebuttal** and are not fully consistent with experiments in the paper.
The original final experiment workspace is reported as unavailable.

## What this release supports

- Running and inspecting the rebuttal BERT training/evaluation workflow:
  PMID-level splitting, chunk-probability averaging, validation-only threshold
  selection and external overlap checks.
- Inspecting verified historical rebuttal PMID pools/samples with source
  references, counts and hashes, without publishing third-party article text.
- Running a fully offline synthetic demo through the actual training and
  evaluation scripts.
- Creating explicitly labeled new reconstructions from provider records with
  recorded retrieval and tokenizer settings.
- Reading existing manuscript aggregate result transcriptions separately from
  the available rebuttal artifacts.

## What this release does not establish

It does not recover the exact paper cohort membership, split assignment,
text/tokenizer snapshot, original chunk generator, final checkpoint/threshold,
or controlled-experiment prompts, outputs and pair mappings. The historical
rebuttal report has different metrics from the manuscript transcriptions.
The new preprocessing script is a documented recipe, not a recovered original.

See [the data card](../data/DATA_CARD.md), [PMID inventory](../data/pmids/README.md)
and [remaining TODOs](../data/FINAL_DATA_STATUS.md).

```bash
# After installing requirements:
bash run_demo.sh
python scripts/verify_pmid_release.py
python -m pytest -q
```

Demo artifacts validate software behavior; their model scores are not scientific
results. Exact numerical reproduction of the paper is not currently supported.
