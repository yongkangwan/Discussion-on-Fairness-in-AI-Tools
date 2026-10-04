Generate a synthetic negative validation dataset for evaluating whether a paper-mill classifier is sensitive to academic English writing style.

Create 6000 synthetic cancer-related research articles:

- 3000 in Group A: ESL-like academic English, approximating stylistic patterns often seen in non-native biomedical writing.
- 3000 in Group B: polished native-like academic English.

All samples must be legitimate-looking negative examples and must not contain explicit fraud, fabrication, paper-mill, retraction, image-manipulation, or misconduct cues.

Cover a broad range of cancer-related study families, including:

- registry outcome studies
- single-center clinical studies
- molecular cohort studies
- biomarker validation
- diagnostic models
- comparative effectiveness
- radiomics
- pathology validation
- surgical quality
- survivorship
- screening epidemiology
- meta-analysis / evidence synthesis
- translational studies

For each generated article, sample:

- cancer type
- study family
- clinical/research setting
- scientific focus
- endpoint
- plausible sample size
- methods
- plausible quantitative or qualitative finding
- limitation
- conclusion

Group A should use grammatically valid but more formulaic and explicit academic English, with tendencies such as:

- “The aim of this study was to…”
- “This study was performed to investigate…”
- “The results showed that…”
- “Moreover…”
- “In conclusion…”
- somewhat more repetitive framing

Group B should use more concise, idiomatic, direct biomedical English, with:

- fewer formulaic transitions
- less redundant framing
- more natural information flow
- more compact conclusions

Do not intentionally make Group A scientifically weaker, less plausible, more exaggerated, or more suspicious than Group B.

The intended class label for every sample is 0.

Output fields:\
`id, label, synthetic, for_bias_evaluation_only, style_group, style_desc, paired_content_id, cancer_type, study_family, setting, focus, endpoint, title, abstract`.
