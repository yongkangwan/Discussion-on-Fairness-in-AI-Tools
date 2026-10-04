Rewrite the following cancer-related scientific article into two controlled English styles for a language-bias evaluation of a paper-mill classifier.

The source article is a **negative / legitimate article that was previously correctly classified as negative by the classifier**.

Produce exactly two rewritten versions:

**Version A — Non-native / ESL-like academic English**

Rewrite the title and abstract using grammatically correct but more formulaic academic English commonly observed in non-native biomedical writing.

Appropriate stylistic tendencies may include:

- “The aim of this study was to…”
- “This study was performed to investigate…”
- “The results demonstrated that…”
- “Moreover…”
- “Furthermore…”
- “It is worth noting that…”
- “Nevertheless…”
- “Therefore…”
- “In conclusion…”
- more explicit transitions
- more repetitive framing
- more explicit statement of aims and conclusions

Do not deliberately introduce poor grammar or stereotypical language errors.

**Version B — Native-like academic English**

Rewrite the same article in polished native-like biomedical journal English.

Use:

- concise, direct phrasing
- fewer formulaic transitions
- less repetition
- more compact methods/results presentation
- more natural paragraph flow
- restrained and appropriately qualified conclusions

### Critical content-preservation rules

The two rewrites must preserve the source article's scientific meaning.

Keep unchanged:

- disease/cancer type
- study objective
- cohort characteristics
- sample size
- study setting
- methodology
- statistical methods
- variables
- interventions/exposures
- outcome definitions
- numerical values
- effect sizes
- direction of associations
- uncertainty
- limitations
- clinical interpretation
- conclusion

Do not add, remove, strengthen, weaken, or reinterpret any scientific claim.

Do not make Version A more suspicious, exaggerated, mechanistic, or paper-mill-like than Version B.

The only intended manipulation is **writing style**.

Both outputs must remain legitimate negative examples.

Output fields:

- `source_id`
- `source_prediction = true_negative`
- `style_group`
- `style_desc`
- `title`
- `abstract`
- `label = 0`
- `synthetic_rewrite = true`
- `for_bias_evaluation_only = true`
