# Paper-reported aggregate tables

These CSV files transcribe the final manuscript of *Text-Based AI Tools for
Research Integrity Must Be Audited on Linguistic Fairness Before Deployment*,
supplied by the authors on 2026-11-08 (11 pages). They are reported aggregate
results, not metrics recomputed from the released historical PMID lists or demo.

Source PDF SHA-256: `2a50b7250c76f06df88396daa18aa93fea68eb85f4c7dd8638792e88f0cc3de3`.

| File | Final manuscript source |
|---|---|
| `reproduction_metrics.csv` | Table 1, page 5 |
| `fairness_audit_summary.csv` | Tables 2 and 3, page 5 |
| `controlled_experiments_summary.csv` | Table 4, page 6 |
| `paired_outcomes.csv` | Table 5, page 7 |

The final Table 3 reports mean scores of **42.0% and 3.0%**, an approximately
**14-fold** difference. Final Table 5 reports experiment 4 counts of **98, 0, 35,
and 2,867**, totaling **3,000 pairs**. The other values in these CSV files were
checked against Tables 1-5 and remain unchanged. Rates retain the manuscript's
reported rounding; `total_pairs` is the sum of the four paired outcome counts.

In `fairness_audit_summary.csv`, `n = 5000` counts each group's negative audit
articles and is the denominator for specificity and the mean score. Table 2
combines those articles with the same 3,290 positive examples for each group:
accuracy uses 8,290 samples, and sensitivity uses the 3,290 shared positives.
The language-group labels refer to the negative articles, not the shared positives.

Historical source counts and scores in `../pmids/` and `../DATA_CARD.md` retain
their own provenance; these manuscript corrections do not relabel those cohorts.
