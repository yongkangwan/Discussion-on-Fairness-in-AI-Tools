# Controlled language-style generation

These prompts specify synthetic cancer-research titles and abstracts for
language-style bias evaluation. Their use of "validation dataset" refers to
classifier evaluation, not the internal validation set used to select a threshold.

| Prompt | Design | Requested size | Corresponding experiment design |
|---|---|---|---|
| [`free_form.md`](free_form.md) | Generate articles in two styles without requiring shared scientific content across groups | 3,000 A + 3,000 B | `exp1_free_form` |
| [`shared_scenario_pairs.md`](shared_scenario_pairs.md) | Render each shared study scenario in both styles | 3,000 matched pairs | `exp2_shared_skeleton` |

## Prompt source and experiment coverage

The project author supplied these prompts on 2026-10-04 as approximate accounts
of the prompt designs. The prompt files preserve the supplied wording. The
experiment mapping above describes their conceptual correspondence to
[`data/paper_results/`](../data/paper_results/); exact historical requests and
their associations with saved generation runs have not been verified. Requested
sizes are generation targets, not released dataset counts.

Rewriting existing real articles (experiments 3 and 4) is not covered; those
prompts remain to be supplied. Paper aggregate results, versioned historical
PMID lists and the offline demo retain
their existing provenance. No new generated papers or experiment results are
included with these prompts.

## Generation model

**Provider: OpenAI. Model family: GPT-5.4 (inferred from the author's date-based
description).** The author describes using OpenAI's latest model as of
2026-04-02. Interpreting "latest" as the latest flagship generation identifies
GPT-5.4: OpenAI's [official release log](https://developers.openai.com/api/docs/changelog)
records GPT-5.4 and GPT-5.4 Pro on 2026-03-05, followed by GPT-5.4 mini/nano on
2026-03-17; GPT-5.5 was released to the API on 2026-04-24.

The date alone does not identify the selected variant, ChatGPT mode, API model
ID or snapshot. Those details remain unspecified rather than assigning a
particular variant to the experiment. The date is a model-availability reference,
not a verified timestamp for every generation request.

## Output contract

The output fields are specified in each prompt; their schemas are different.
For a new run, JSONL with one object per title/abstract is a practical storage
format; JSONL is a repository recommendation, not a recovered historical setting.

- Use globally unique `id` values and `style_group` values of `"A"` or `"B"`.
- Preserve every requested field. Store `label` as integer `0` and `synthetic`
  and `for_bias_evaluation_only` as boolean `true` for new runs. The free-form
  prompt names these flags without specifying their serialized values; this
  boolean convention makes its synthetic evaluation purpose explicit.
- Treat A/B as requested writing styles, not the nationality or language
  background of real authors. `label = 0` is the intended synthetic negative
  class, not an independently verified statement about real research.
- Retain pair/style metadata alongside model inputs. Only article text should
  enter the classifier; identifiers, style descriptions and labels are metadata.
  These synthetic identifiers are not PMIDs and do not belong in `data/pmids/`.

### Free-form output

`free_form.md` requests `paired_content_id`, but does not define its values or
require matched A/B content. Preserve this field without treating it as evidence
of pairing. For a new unpaired run, use JSON `null` as an explicit repository
convention, recording that choice in the run metadata. Historical values remain
unspecified. Do not fabricate A/B matches from row order or similar topics.

Check 3,000 retained articles per group, unique IDs, required fields, plausible
research content and absence of the excluded misconduct cues. Compare group
distributions of cancer type, study family, setting, endpoint and sample size
where available. The prompt requests diversity and similar scientific quality;
it does not guarantee equal topic distributions or identical scientific content.
Report any imbalance alongside the style comparison. Use group-level positive
rates; a paired outcome table requires independently established content matches.

### Shared-scenario output

`shared_scenario_pairs.md` requires exactly two records for every `pair_id`: one
A and one B. This pairing requirement applies only to the shared-scenario design.

## Preparing and checking a new run

Generating in batches is a practical option if an output limit prevents returning
all articles at once. Record any batch-size instruction or other prompt modification
in the actual request log, and use non-overlapping ID ranges. Record every
exclusion or regeneration and the final retained group counts. In the
shared-scenario design, retain complete pairs when retrying or excluding records.

For the shared-scenario design, check final pair counts and compare
the paired scenario, cancer type, setting, period and focus fields. Also review
the titles and abstracts for agreement in sample size, methods, biomarkers,
outcomes, numerical findings, effect direction, limitations and conclusions.
Matching metadata alone cannot establish scientific equivalence. Retaining a
structured shared-scenario record for each pair can support this review in new
runs; that additional record is not part of the supplied output schema.

Record content discrepancies and the actual number of retained complete pairs.
Prompt instructions express the intended control; successful generation and
review establish whether it was met.

For classifier evaluation, use the same selected checkpoint, tokenizer,
preprocessing settings and frozen internal-validation threshold for both styles.
Keep these evaluation examples out of training and threshold selection. Aggregate
chunks at article level before calculating style-specific positive rates. For
the shared-scenario design, also join A/B predictions by `pair_id` to calculate
paired outcome counts; resampling must keep the two members of a pair together.

## Generation records still needed

The provider and date-based model-family identification are recorded above.
The exact variant/snapshot, request dates, system instructions, temperature,
top-p, seed, token limit, batching, retries and filtering used in the original
experiment remain unspecified. These values must not be inferred from the prompt
or release date. For new runs, save the actual settings
(including provider defaults or unsupported options), exact requests, raw
responses, shared-scenario records if used, reviewed rows, exclusions and hashes.
Also retain the evaluated checkpoint, preprocessing configuration, threshold and
per-article predictions so that generated data can be traced to result tables.
