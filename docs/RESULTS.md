# Results highlighted in the paper

> These are existing manuscript-reported aggregate transcriptions. The repository
> working code and datasets arose during rebuttal and do not fully match the paper
> experiments. These values were not recomputed from the released historical
> cohorts or synthetic demo. See [the data card](../data/DATA_CARD.md).

This page summarizes the headline results reported in the accepted manuscript. It is intentionally concise; exact experiment artifacts and preprocessing code are being reconciled before the final public release.

## Model reproduction

The reproduced BERT-based paper-mill detector achieves performance close to the originally reported study and is used as the baseline for the fairness audit.

| Validation setting | Accuracy | Sensitivity | Specificity |
|---|---:|---:|---:|
| Internal reproduction | 97% (513/528) | 97% (260/267) | 97% (253/261) |
| External reproduction | 98% (6171/6289) | 97% (3201/3290) | 99% (2970/2999) |

## Real-world linguistic-bias audit

On 5,000 legitimate high-impact-journal papers in each group:

| Group | Number of papers | Mean predicted paper-mill probability |
|---|---:|---:|
| Non-native English | 5,000 | 42.0% |
| Native English | 5,000 | 2.0% |

The large prediction gap motivates the controlled experiments that follow.

## Controlled style experiments

Across four LLM-based experiments, non-native-English style consistently receives a higher positive rate than native-English style.

| Experiment | Non-native English | Native English |
|---|---:|---:|
| Free-form generation | 95.3% | 30.8% |
| Shared skeleton | 55.3% | 18.4% |
| Rewrite false positives | 98.4% | 89.4% |
| Rewrite true negatives | 4.4% | 1.2% |

In the paired experiments, changing from native-English style to non-native-English style can move examples from negative to positive; the reverse direction is not observed in the reported paired results.

## Interpretation

These results are evidence about **model behavior and linguistic sensitivity**, not evidence that any individual paper, author, institution, country, or linguistic group engaged in research misconduct.
