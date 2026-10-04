Generate a synthetic validation dataset for studying language-style bias in a classifier that detects paper-mill articles.

Create **3000 matched pairs**, giving a total of **6000 cancer-related synthetic papers**.

For every pair, first construct one shared underlying research scenario. The two versions in the pair must describe exactly the same hypothetical study and must not differ in scientific content.

Each pair must share:

- cancer type
- study scenario/design
- study setting
- study period
- sample size
- variables or biomarkers studied
- methods
- outcome
- effect direction
- numerical results where applicable
- limitations
- scientific conclusion

Then render this same study in two different writing styles:

**Group A:** English manuscript style commonly associated with China-authored biomedical academic writing. Use grammatically valid academic English, but allow stylistic tendencies such as more explicit framing, formulaic transitions, phrases such as “the present study aimed to…”, “the results showed that…”, “moreover”, “it is worth noting that…”, “however, it should be noted…”, and more explicit conclusion statements. Do not intentionally insert obvious grammar mistakes, broken English, caricatures, or stereotypical errors.

**Group B:** polished native-English biomedical journal style. Use more concise, idiomatic, direct academic prose, fewer formulaic transitions, less redundant framing, and more natural information flow.

Critically, **do not make Group A scientifically weaker, more exaggerated, more suspicious, more mechanistic, or more paper-mill-like than Group B**. The only intended difference between A and B is surface-level academic English style.

All papers must:

- be related to cancer research;
- represent plausible legitimate biomedical research;
- be negative examples for paper-mill detection;
- avoid fabrication cues, implausible biological claims, retraction language, image-manipulation language, paper-mill terminology, or obviously fraudulent patterns;
- cover diverse cancer types and research scenarios.

Include diverse scenarios such as:

- epidemiology and cancer risk
- biomarker validation
- pathology concordance
- diagnostic models
- radiomics/imaging
- surgery outcomes
- treatment outcomes
- survivorship and quality of life
- health-services research
- preclinical or translational mechanisms

Output one row per paper with:

- `id`
- `style_group`
- `style_desc`
- `pair_id`
- `scenario`
- `cancer_type`
- `setting`
- `period`
- `shared_focus`
- `title`
- `abstract`
- `label = 0`
- `synthetic = true`
- `for_bias_evaluation_only = true`

For each `pair_id`, output exactly one A version and one B version.

Do not let topic, cancer type, study design, numerical findings, or conclusion systematically correlate with style group.
