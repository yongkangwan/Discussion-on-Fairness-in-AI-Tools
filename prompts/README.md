# Controlled language-style generation

[`shared_scenario_pairs.md`](shared_scenario_pairs.md) specifies 3,000 matched
pairs of synthetic cancer-research titles and abstracts. Each pair describes a
single hypothetical study in two academic English styles, holding scientific
content fixed by design. It is an evaluation dataset specification, not the
classifier's internal validation set used to select a decision threshold.

## Prompt source and experiment coverage

The project author supplied this prompt on 2026-10-04 as an approximate account
of the prompt design. The prompt file preserves the supplied wording. Its shared
scenario design corresponds conceptually to `exp2_shared_skeleton` in
[`data/paper_results/`](../data/paper_results/); the exact historical request and
its association with a saved generation run have not been verified. The target
of 3,000 pairs is a requested dataset size, not a released dataset count.

This prompt does not document free-form generation or rewriting existing real
articles (experiments 1, 3 and 4). Their prompts remain to be supplied. Paper
aggregate results, versioned historical PMID lists and the offline demo retain
their existing provenance. No new generated papers or experiment results are
included with this prompt.

## Output contract

The fields and scientific attributes to hold fixed are specified in the prompt.
For a new run, JSONL with one object per title/abstract is a practical storage
format; JSONL is a repository recommendation, not a recovered historical setting.

- Use globally unique `id` values and exactly two records for every `pair_id`:
  one `style_group: "A"` and one `style_group: "B"`.
- Preserve every requested field. Store `label` as integer `0` and `synthetic`
  and `for_bias_evaluation_only` as boolean `true`.
- Treat A/B as requested writing styles, not the nationality or language
  background of real authors. `label = 0` is the intended synthetic negative
  class, not an independently verified statement about real research.
- Retain pair/style metadata alongside model inputs. Only article text should
  enter the classifier; identifiers, style descriptions and labels are metadata.
  These synthetic identifiers are not PMIDs and do not belong in `data/pmids/`.

## Preparing and checking a new run

Generating in batches is a practical option if an output limit prevents returning
all pairs at once. Record any batch-size instruction or other prompt modification
in the actual request log, and use non-overlapping ID ranges. Retain complete
pairs when retrying or excluding records.

Check unique IDs, required fields, A/B membership and final pair counts. Compare
the paired scenario, cancer type, setting, period and focus fields. Also review
the titles and abstracts for agreement in sample size, methods, biomarkers,
outcomes, numerical findings, effect direction, limitations and conclusions.
Matching metadata alone cannot establish scientific equivalence. Retaining a
structured shared-scenario record for each pair can support this review in new
runs; that additional record is not part of the supplied output schema.

Record content discrepancies and every exclusion or regeneration, then report
the actual number of retained complete pairs. Prompt instructions express the
intended control; successful generation and review establish whether it was met.

For classifier evaluation, use the same selected checkpoint, tokenizer,
preprocessing settings and frozen internal-validation threshold for both styles.
Keep these evaluation examples out of training and threshold selection. Aggregate
chunks at article level and join A/B predictions by `pair_id` before calculating
style-specific positive rates and paired outcome counts. Any resampling should
keep the two members of a pair together.

## Generation records still needed

The supplied design does not establish the provider, exact model/version,
generation date, system instructions, temperature, top-p, seed, token limit,
batching, retries or filtering used in the original experiment. These values
must not be inferred from the prompt. For new runs, save the actual settings
(including provider defaults or unsupported options), exact requests, raw
responses, shared-scenario records if used, reviewed rows, exclusions and hashes.
Also retain the evaluated checkpoint, preprocessing configuration, threshold and
per-article predictions so that generated data can be traced to result tables.
