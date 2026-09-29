# Data card: evidence, cohorts, and preprocessing

Audit date: 2026-09-29. **Author clarification: the repository code and working
data were produced during rebuttal; they no longer align exactly with the
experiments in the paper.** Historical identifiers below therefore mean
**verified rebuttal-stage artifacts**, not recovered paper cohorts.

This card separates **paper-reported data**, **verified
historical data**, and **demo-only data**. A new retrieval/preprocessing run is
additionally labeled **reconstruction**; it is not promoted to either historical
or final paper data.

## Evidence levels and contents

| Category | Released artifact | What it establishes |
|---|---|---|
| Paper-reported aggregate data | `paper_results/*.csv` | Existing transcriptions of manuscript tables; no article-level provenance |
| Paper actual article-level data | Not recovered | No verified final cohort, split, checkpoint, or controlled-experiment pair mapping |
| Verified historical rebuttal data | `pmids/historical/`, `pmids/manifest.json` | Identifiers extracted from surviving archived artifacts, with immutable source references and counts |
| Demo-only | `examples/`, `run_demo.sh` | Entirely synthetic text and a runnable software demonstration |
| New reconstruction | Local `data/generated/` or `runs/` | Current provider records and an explicitly chosen new tokenization recipe |

The manuscript was not independently supplied during this audit. Existing
`paper_results/` values were inspected and preserved, not re-transcribed or
silently reconciled with the older report. In particular, experiment 4 reports
3,000 per style in the summary but 2,999 pairs in `paired_outcomes.csv`; the missing
pair/denominator requires author confirmation.

## Source provenance and recovery boundary

The target repository and private archive `main` at
`401799b59bb91874b0e0dab2908b32d3de9bf360` have cleaned trees. The archive's old
PR #1 retains a base reference to **`c61fbf422a1f43e78a94b71cb1b8b28d7407d949`**
and a head reference to `8b0f71d440822927cbeb491f8104d6ab7f765205`. Both historical
trees expose the same raw-data blob IDs. The base commit contains
`EXPERIMENT_REPORT.md`, pre-tokenized JSONL, and three sampling manifests. These
are the evidence for this release, not the cached ChatGPT discussion.

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
membership. The historical threshold `0.0316187665` belongs to that old run only;
we do not make it a default or claim it reproduces the paper.

## Cohort meanings and limitations

Historical README and report identify `positive_chunks.jsonl` as internal
positive-role data and `top_china.jsonl`, `top_other_train.jsonl`,
`top_taiwan.jsonl` as internal negative-role sources. These are source pools,
**not recovered train/validation/test assignments**. `positive_chunks_dedup_pubpeer.jsonl`
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
exist. Experiments 3–4 need recovered source-PMID/pair/style mappings, prompts,
model versions and generation settings. No such final artifacts were found in
the inspected trees. We do not populate plausible substitutes.

## Verified code behavior (not proof of final-paper settings)

At the inspected main commit, `paper_mill_common.py`, `train.py`, `evaluate.py`
and `sample_articles.py` implement:

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
   article. Original exact assignments require the missing split manifest.
5. Train at chunk level. Choose the checkpoint by minimum validation chunk
   cross-entropy, with validation article AUROC as tie-break.
6. Compute each chunk's `softmax(logits)[1]`. Article probability is the
   **unweighted arithmetic mean of those probabilities**, not the mean of logits
   or hard predictions. Different chunk lengths do not change their weights.
7. Select a threshold on validation articles only (default Youden objective;
   ties prefer specificity, sensitivity, then the higher cutoff). Classify with
   `mean_positive_probability >= threshold`. Freeze it for internal test and
   external evaluation. Check evaluation PMIDs against the training manifest.

The historical audit sampling manifests additionally record seed 42 and ranking
by SHA-256 of the UTF-8 string `str(seed) + NUL + pmid`, with PMID tie-break.
Select the first N eligible articles and retain every chunk. Both audit samples
exclude internal-pool PMIDs, external-positive PMIDs, and the opposite raw audit
pool. They do **not** exclude external negatives; the historical report records
800 overlaps for Other. The absent `other_20000.jsonl` and original split manifest
prevent complete replay of eligibility/ranking. Recovered sampled lists still
establish the selected article IDs directly.

## Chunk schema and the unknown original tokenizer recipe

Required model-input fields are `pmid` (string), `chunk_index` (non-negative
integer), `input_ids` (nonempty integer list), `attention_mask` (same-length 0/1
list); `token_type_ids` is optional and defaults to zeros. Row `label` records the
source value but the CLI role controls the loaded label. Archived records may
also include `title`, `abstract`, and `meta` with journal/date/author/affiliation
fields; those fields and token arrays are not part of this identifier release.

The old README states `bert-base-uncased` vocabulary and a 512-token maximum.
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

## Author-confirmation TODOs

- Recover the exact final PMID cohort lists and train/validation/test manifest;
  link them to the paper's tables with run IDs and source/output hashes.
- Recover the original fetch/query/filter scripts, source dates, labeling rules,
  journal lists, exclusions and geographic/language proxy definitions.
- Recover the tokenizer snapshot and original title/abstract composition,
  prefix handling, special-token, overlap, tail and normalization settings.
- Recover the final checkpoint, frozen threshold, per-article predictions and
  environment; do not substitute the historical threshold above.
- Recover controlled-experiment prompts, model/version/settings, source/pair IDs,
  outputs and exclusion logs; explain experiment 4's 3,000 versus 2,999 count.
- Confirm a code/synthetic-example license separately. No third-party material
  is relicensed by these additions.
