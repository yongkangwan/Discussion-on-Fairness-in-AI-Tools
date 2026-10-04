Rewrite the following cancer-related scientific article into two controlled English styles for a language-bias evaluation of a paper-mill classifier.

The source article is a **negative / legitimate article that was previously misclassified as positive by the classifier**.

Produce exactly two rewritten versions:

**Version A — Non-native / ESL-like academic English**

Rewrite the title and abstract using grammatically valid but more formulaic academic English commonly observed in non-native biomedical manuscripts. Possible stylistic tendencies include:

- “The aim of this study was to…”
- “This study was performed to investigate…”
- “The results showed that…”
- “Moreover…”
- “Furthermore…”
- “It is worth noting that…”
- “However, it should be noted that…”
- “In conclusion…”
- more explicit transitions
- slightly more repetitive framing
- more explicit restatement of the study objective and conclusion

Do **not** intentionally introduce grammatical errors, awkward broken English, exaggerated claims, or stereotyped mistakes.

**Version B — Native-like academic English**

Rewrite the same article in polished, concise, idiomatic biomedical journal English.

Prefer:

- direct sentence structure
- less redundant framing
- fewer formulaic transitions
- more compact presentation of methods and findings
- more natural information flow
- concise and appropriately qualified conclusions

### Critical content-preservation rules

The two rewrites must preserve the original scientific content as closely as possible.

Do not alter:

- cancer type
- study population
- sample size
- study design
- exposure/intervention
- comparator
- biomarkers
- methods
- statistical analyses
- endpoints
- numerical results
- effect direction
- confidence intervals
- p-values
- limitations
- scientific interpretation
- final conclusion

Do not add any new evidence, mechanism, clinical implication, limitation, or result that is not present in the source.

Do not remove any scientifically important information.

The intended difference between Version A and Version B must be **linguistic style only**.

Both rewritten articles must remain legitimate negative examples and must not introduce paper-mill, fabrication, misconduct, image-manipulation, plagiarism, or retraction cues.

Output fields:

- `source_id`
- `source_prediction = false_positive`
- `style_group`
- `style_desc`
- `title`
- `abstract`
- `label = 0`
- `synthetic_rewrite = true`
- `for_bias_evaluation_only = true`
