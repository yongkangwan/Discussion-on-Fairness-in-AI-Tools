# Data card: evidence, cohorts, and preprocessing

Updated: 2026-09-29. This card documents data sources, cohort membership,
input format, training settings and preprocessing. It distinguishes paper-reported
aggregate results, versioned historical data, synthetic demo inputs and newly
retrieved/reprocessed data (`reconstruction`).

## Data contents

| Category | Released artifact | What it establishes |
|---|---|---|
| Paper-reported aggregate data | `paper_results/*.csv` | Existing transcriptions of manuscript tables; no article-level provenance |
| Versioned historical data | `pmids/historical/`, `pmids/manifest.json` | Identifiers extracted from surviving archived artifacts, with immutable source references and counts |
| Demo-only | `examples/`, `run_demo.sh` | Entirely synthetic text and a runnable software demonstration |
| New reconstruction | Local `data/generated/` or `runs/` | Current provider records and an explicitly chosen new tokenization recipe |

`paper_results/` contains manuscript-reported aggregate tables, stored separately
from the source cohorts. Experiment 4 lists 3,000 per style in the summary but
2,999 pairs in `paired_outcomes.csv`; the pair-level inclusion record is needed
to explain that denominator difference.

## Source provenance

The target repository and private archive `main` at
`401799b59bb91874b0e0dab2908b32d3de9bf360` have cleaned trees. The archive's old
PR #1 retains a base reference to **`c61fbf422a1f43e78a94b71cb1b8b28d7407d949`**
and a head reference to `8b0f71d440822927cbeb491f8104d6ab7f765205`. Both historical
trees expose the same raw-data blob IDs. The base commit contains
`EXPERIMENT_REPORT.md`, pre-tokenized JSONL, and three sampling manifests. These
provide the source evidence recorded in `pmids/manifest.json`.

Source links require archive access. Public readers can inspect the exported
identifier lists, source blob IDs, counts and hashes, but cannot independently
read private source blobs without that access. No archive history or third-party
article text is imported into this repository. See [pmids/README.md](pmids/README.md)
for the inventory and verification instructions.

The historical report describes a 2026-07-27 run with 4,218 internal articles,
3,290 external positives and 2,999 raw external negatives (2,987 after removal of
12 overlapping internal articles). Its two 5,000-article audit groups have mean
positive scores **0.266995** and **0.012326**, versus **0.42** and **0.02** in the
paper table. The historical internal test accuracy is **0.95265**, versus **0.97**
in the paper table. Matching sample sizes alone does not establish final-paper
membership. That report records threshold `0.0316187665` for its run. In the
training code, the final threshold is calculated from the internal validation
set after selecting the model; each new run saves its own value in `threshold.json`.

## Cohort meanings and limitations

Historical README and report identify `positive_chunks.jsonl` as internal
positive-role data and `top_china.jsonl`, `top_other_train.jsonl`,
`top_taiwan.jsonl` (Taiwan, China) as internal negative-role sources. These are source pools;
the training script subsequently assigns their articles to train/validation/test
and saves the mapping in `split_manifest.json`. `positive_chunks_dedup_pubpeer.jsonl`
is the historical external positive-role source. Its stored labels are all 0;
the loader overrides them to 1 because of its explicit input role.
`top_other_prove.jsonl` is the report's external negative source.

`china_5000` and `other_5000` are historical cohort names. They do not establish
individual authors' native language, nationality, or research integrity. The
negative labels are research assumptions, not article-level adjudications.
`positive_chunks_china` is an additional historical source with no recovered
role in the final paper; a filename alone is not evidence of experimental use.
The original query strings, retrieval dates, high-impact journal inclusion rules,
geographic/linguistic assignment criteria, positive-label adjudication and exact
cohort construction before tokenization remain unverified.

Controlled experiments 1–2 concern generated text, for which a PMID need not
exist. The author-supplied [generation prompt designs](../prompts/README.md)
are available: free-form generation requests 3,000 articles per style without
requiring matched scientific content; shared-scenario generation requests 3,000
A/B pairs with scientific content held fixed by instruction. These designs are
not verified historical requests or released generated datasets. The author
identifies OpenAI as the generation provider and describes
the model as the latest available on 2026-04-02; the [model note](../prompts/README.md#generation-model)
maps this to GPT-5.4 under a latest-flagship interpretation, with the exact
variant/snapshot unspecified. Experiments 3–4 need recovered source-PMID/pair/style mappings, prompts,
model versions and generation settings. No such final artifacts were found in
the inspected trees. We do not populate plausible substitutes.

## Training configuration and processing

The following settings and rules are implemented in [train.py](../train.py),
[paper_mill_common.py](../paper_mill_common.py) and [evaluate.py](../evaluate.py):

| Setting | Default / rule |
|---|---|
| Base model | `bert-base-uncased` |
| Article split | 70% training / 17.5% internal validation / 12.5% internal test |
| Split seed | 42; stratified by article label |
| Maximum accepted chunk length | 512 tokens |
| Training | 10 epochs; train/eval batch size 32; gradient accumulation 1 |
| Optimizer | AdamW; learning rate `1.4e-5`; weight decay `0.025` |
| Schedule | Cosine; warm-up ratio `0.15` |
| Checkpoint selection | Lowest internal-validation chunk loss; article AUROC breaks ties |
| Final threshold | Derived from internal-validation article scores; default objective is Youden |

Command-line arguments can override the defaults; the training run saves its
configuration and outputs. The processing sequence is:

1. Load **already tokenized** JSONL. Positive/negative command-line file roles
   force labels 1/0; labels are not inferred from title, affiliation or PMID.
2. Merge identical `(pmid, chunk_index)` token payloads; fail on conflicting
   payloads or cross-role article labels. Require consecutive chunk indices from
   zero, equal token-array lengths and valid attention masks. Missing
   `token_type_ids` become zeros. Text and metadata are not consumed by the model.
3. Reject chunks longer than the configured maximum (default 512), rather than
   silently truncating. Dynamically pad to the batch's longest chunk.
4. Split sorted unique PMIDs with two stratified `train_test_split` calls, using
   seed 42 and ratios 0.7/0.175/0.125 by default. The second call splits the
   holdout with test fraction `0.125 / (0.175 + 0.125)`. All chunks stay with their
   article. `train.py` writes the resulting membership to `split_manifest.json`.
   Reusing the same input membership, labels, seed and software versions permits
   regeneration; verification against an old run requires that run's saved manifest.
5. Train at chunk level. Choose the checkpoint by minimum validation chunk
   cross-entropy, with validation article AUROC as tie-break.
6. Compute each chunk's `softmax(logits)[1]`. Article probability is the
   **unweighted arithmetic mean of those probabilities**, not the mean of logits
   or hard predictions. Different chunk lengths do not change their weights.
7. Reload the selected model and derive the **final threshold from internal
   validation articles only** (default Youden objective;
   ties prefer specificity, sensitivity, then the higher cutoff). Classify with
   `mean_positive_probability >= threshold`. Freeze it for internal test and
   external evaluation. `threshold.json` explicitly records
   `selection_set: "internal_validation"`, the value, objective and run ID;
   `evaluate.py` loads this threshold without refitting it. Per-epoch thresholds
   in `training_history.json` are diagnostics. Check evaluation PMIDs against
   the training manifest.

The historical audit sampling manifests additionally record seed 42 and ranking
by SHA-256 of the UTF-8 string `str(seed) + NUL + pmid`, with PMID tie-break.
Select the first N eligible articles and retain every chunk. Both audit samples
exclude internal-pool PMIDs, external-positive PMIDs, and the opposite raw audit
pool. They do **not** exclude external negatives; the historical report records
800 overlaps for Other. The absent `other_20000.jsonl` and original split manifest
prevent complete replay of eligibility/ranking. Recovered sampled lists still
establish the selected article IDs directly.

## Chunk schema and preprocessing

Required model-input fields are `pmid` (string), `chunk_index` (non-negative
integer), `input_ids` (nonempty integer list), `attention_mask` (same-length 0/1
list); `token_type_ids` is optional and defaults to zeros. Row `label` records the
source value but the CLI role controls the loaded label. Archived records may
also include `title`, `abstract`, and `meta` with journal/date/author/affiliation
fields; those fields and token arrays are not part of this identifier release.

`train.py` loads pre-tokenized chunks; it does not split raw article text.
Its 512-token limit validates the saved inputs and is not a stride or overlap
setting. The old README states `bert-base-uncased` vocabulary.
Inspected blobs support the presence of pre-tokenized chunks with lengths up to
512 and zero-based chunk indices. Some archived title/abstract strings include
literal `Title:` / `Abstract:` prefixes. **This does not establish whether those
prefixes were tokenized, how title and abstract were combined, or the exact
preprocessing used for the final paper.**

| Parameter | Evidence / status |
|---|---|
| Model family / vocabulary name | Historical README says `bert-base-uncased`; exact tokenizer revision/files unknown |
| Maximum accepted input length | 512 in historical report and loader default, including whatever tokens are stored |
| Text composition, separators, prefix handling | Unknown; no original generator recovered |
| Single sequence versus title/abstract pair | Unknown |
| Sentence splitting / whitespace / normalization | Unknown |
| Content window size / special-token placement | Unknown original recipe; cannot infer from maximum length alone |
| Stride / overlap | Unknown; not inferred or set to a guessed paper value |
| Truncation / short final chunk / original padding | Unknown preprocessing policy; loader itself rejects overlength chunks and pads batches |
| Chunk index and article aggregation | Verified current loader and historical report/code as described above |

## Rebuilding inputs without redistributing text

Re-fetching a PMID today can return a revised record. It does not recover the
historical text, labels, final cohort assignments, or tokenizer revision.
`scripts/fetch_pubmed.py` is a **new reconstruction utility**. It saves the raw
provider XML locally, checks returned PMID membership, extracts title/abstract,
and records retrieval time and SHA-256 hashes. It requires an explicit research
label; no labels are inferred. Missing abstracts are listed in its manifest.
Book records or missing IDs cause a mismatch error rather than silent omission.

From the repository root, after reviewing the desired cohort's historical role:

```bash
python scripts/fetch_pubmed.py \
  --pmids data/pmids/historical/internal_negative_top_china.txt \
  --email YOUR_CONTACT_EMAIL --label 0 \
  --output-dir data/generated/top_china_current
```

For a **new, explicitly configured** preprocessing run, first obtain and preserve
a local tokenizer snapshot with its revision and files, then run:

```bash
python scripts/preprocess_articles.py \
  --input data/generated/top_china_current/articles.jsonl \
  --output data/generated/top_china_current/chunks.jsonl \
  --tokenizer-dir /path/to/local/tokenizer-snapshot \
  --max-length YOUR_CHOSEN_TOTAL_LENGTH \
  --overlap YOUR_CHOSEN_CONTENT_OVERLAP \
  --status reconstruction
```

There are deliberately no default values for maximum length or overlap here.
This utility supports BERT tokenizers only and uses the documented new
single-sequence recipe: stripped
title, two newlines, stripped abstract; no added textual prefixes; tokenize
without specials; content capacity = maximum length minus two; step = capacity minus overlap;
wrap each window with the local tokenizer's `[CLS]` and `[SEP]` IDs, with all-zero
token types;
retain the short last window; no saved padding. It records parameters, package
version and local tokenizer file hashes. It **cannot reproduce unknown original
chunk boundaries**. It accepts only `reconstruction` or `demo-only`, never a
`paper` provenance label. See [examples/README.md](examples/README.md) for the
fully runnable offline example.

Use provider data under the provider's terms and applicable article permissions.
This project conservatively distributes identifiers and synthetic text; it does
not assert that every PubMed abstract has the same redistribution license.
Consult [NCBI E-utilities guidance](https://www.ncbi.nlm.nih.gov/books/NBK25497/)
and [EFetch documentation](https://www.ncbi.nlm.nih.gov/books/NBK25499/) before
large retrievals, including NCBI tool/email registration guidance. Avoid running
multiple retrieval jobs that share an IP at once. The script makes sequential requests with a 0.4-second pause,
no API key, and sends the supplied contact email to NCBI.

## Additional artifacts for exact historical replay

The split algorithm, model-selection rule and validation-threshold procedure are
available in code and described above. The following are **saved inputs/outputs
or upstream preprocessing records**, rather than unspecified training methods:

- Run-specific input membership and `split_manifest.json`, linked to the paper
  tables by run ID and source/output hashes.
- Original retrieval/query/filter records, dates, journal lists, labels and proxy
  definitions; raw `other_20000.jsonl` for replaying historical audit eligibility.
- Original tokenizer snapshot and text-to-chunk generator, including title/abstract
  composition, prefix handling, overlap and short-tail policy.
- Saved trained weights, the selected run's `threshold.json`, predictions and
  environment. Fresh training produces these artifacts, including a newly
  calculated internal-validation threshold.
- Exact historical controlled-experiment requests, generation settings,
  source/pair mappings and outputs; prompts for experiments 3 and 4;
  the inclusion record explaining experiment 4's denominator. The free-form and
  shared-scenario designs in `prompts/` document the supplied methodology but not
  those run records.

See [FINAL_DATA_STATUS.md](FINAL_DATA_STATUS.md) for the availability summary.
