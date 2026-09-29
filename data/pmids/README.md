# Verified historical rebuttal PMID inventory

**These are rebuttal-stage artifacts, not the paper's verified experiment cohorts.**
Author clarification and [the data card](../DATA_CARD.md) explain the distinction.
Identifiers preserve historical source membership, not judgments about articles or
authors. Positive/negative roles describe the old experimental setup.

| List | Unique PMIDs | Source chunk rows | Historical role |
|---|---:|---:|---|
| [internal_positive_pool](historical/internal_positive_pool.txt) | 2,122 | 2,518 | internal positive-role pool |
| [internal_negative_top_china](historical/internal_negative_top_china.txt) | 100 | 100 | internal negative-role source |
| [internal_negative_top_other_train](historical/internal_negative_top_other_train.txt) | 1,400 | 1,683 | internal negative-role source |
| [internal_negative_top_taiwan](historical/internal_negative_top_taiwan.txt) | 600 | 668 | internal negative-role source |
| [external_positive_pubpeer](historical/external_positive_pubpeer.txt) | 3,290 | 3,961 | external positive-role source |
| [external_negative_raw](historical/external_negative_raw.txt) | 2,999 | 3,612 | raw external negative-role source |
| [external_negative_clean](historical/external_negative_clean.txt) | 2,987 | 3,599 | external negative after internal-pool exclusion |
| [audit_china_candidate_pool](historical/audit_china_candidate_pool.txt) | 8,000 | 9,015 | candidate audit source pool |
| [audit_china_5000](historical/audit_china_5000.txt) | 5,000 | 5,656 | historical sampled audit cohort |
| [audit_other_5000](historical/audit_other_5000.txt) | 5,000 | 5,695 | historical sampled audit cohort |
| [additional_positive_china](historical/additional_positive_china.txt) | 2,027 | 2,412 | additional source; experimental use not established |

The lists contain **22,562 distinct PMIDs** in total; rows overlap and must not be summed as independent articles.
Internal positive plus the three internal negative pools contain 4,218 unique
articles. No original train/validation/test assignment is recovered. The negative
sources share four article memberships (two China/Other, two Taiwan/Other).
The external negative raw pool shares 12 PMIDs with the internal union; the clean
list equals exactly raw minus that union. The two 5,000-article audit lists are
disjoint and have no overlap with the internal union or external positives.
Other audit and raw external negative lists share 800 articles, retained in the
historical run. Full pairwise intersections are in [overlap_counts.csv](overlap_counts.csv).

## Provenance and checks

Sources come from the [private archive commit](https://github.com/yongkangwan/Discussion-on-Fairness-in-AI-Tools-private-archive/tree/c61fbf422a1f43e78a94b71cb1b8b28d7407d949)
`c61fbf422a1f43e78a94b71cb1b8b28d7407d949`, discoverable via
[old PR #1](https://github.com/yongkangwan/Discussion-on-Fairness-in-AI-Tools-private-archive/pull/1).
The three derived cohorts were checked **both** against archived JSONL membership
and sampling-manifest PMID/chunk counts. Their counts agree exactly. China and
Other list SHA-256 hashes also match the old experiment report:

- China: `65007ca71044cfe021270b299d8804e0580f26d27bc11cf00bde6de4d966bff2`
- Other: `70604c090c9f5ef4d5808caf09ef1ac95555a84eff884fd7edcbb96757dd91ab`

[manifest.json](manifest.json) records source paths, immutable Git blob IDs,
source counts, observed label/length statistics, sampling evidence and released
list hashes. Lists contain unique numeric PMIDs in ascending numeric order with
a final LF. No article text, author metadata or historical token arrays are released.
The historical sampler uses lexicographic sorting; all identifiers in the two audit samples
have equal width, so the two sort orders and resulting hashes coincide.

```bash
# Public, offline integrity and overlap verification:
python scripts/verify_pmid_release.py

# With an authorized archive clone containing the old source commit:
python scripts/recover_historical_pmids.py --archive /path/to/private-archive \
  --output-dir data/generated/recovered-pmids
```

The recovery command reads pinned Git objects, verifies source blob hashes and
checks its output against this release. It does not fetch, modify the archive,
reintroduce old history, or export text/token arrays. If the old commit is missing,
fetch it into the private archive using the source commit above first.

Archive access is required to independently inspect the underlying private
evidence. Exported hashes establish file integrity, not final-paper provenance.
The original raw `other_20000.jsonl` and internal split manifest were not found
in the inspected historical tree, preventing full replay of sampling eligibility.

## Missing paper and controlled-experiment lists

No final-paper cohort/split files are created. We do not publish empty or guessed
`training_pmids.txt`, `validation_pmids.txt`, or controlled-experiment lists.
For generated experiments 1–2, PMID may be inapplicable. For rewriting experiments
3–4, the original source-PMID and pair mappings remain unavailable. See
[FINAL_DATA_STATUS.md](../FINAL_DATA_STATUS.md) for the author-confirmation TODOs.
