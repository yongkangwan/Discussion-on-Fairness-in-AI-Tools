"""Statistical analysis of article-level paper-mill prediction files."""

from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np

from paper_mill_common import (
    SCHEMA_VERSION,
    compute_article_metrics,
    file_fingerprint,
    prepare_empty_output_dir,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarise article-level probabilities and thresholded positive rates, "
            "with confidence intervals and pairwise bootstrap comparisons."
        )
    )
    parser.add_argument(
        "--group",
        action="append",
        required=True,
        metavar="NAME=JSONL",
        help="Repeat once for each article prediction JSONL file.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--confidence-level", type=float, default=0.95)
    parser.add_argument("--bootstrap-replicates", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def parse_group_specs(specs: list[str]) -> dict[str, Path]:
    groups: dict[str, Path] = {}
    for spec in specs:
        if "=" not in spec:
            raise ValueError(f"Invalid --group {spec!r}; expected NAME=JSONL")
        name, raw_path = spec.split("=", maxsplit=1)
        name = name.strip()
        if not name:
            raise ValueError("Group name cannot be empty")
        if name in groups:
            raise ValueError(f"Duplicate group name: {name}")
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Prediction JSONL does not exist: {path}")
        groups[name] = path
    return groups


def load_prediction_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_pmids: set[str] = set()
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
            required = {
                "pmid",
                "label",
                "mean_positive_probability",
                "prediction",
                "threshold",
            }
            if not isinstance(row, dict) or not required.issubset(row):
                missing = sorted(required - set(row if isinstance(row, dict) else {}))
                raise ValueError(f"{path}:{line_number}: missing fields {missing}")
            pmid = str(row["pmid"])
            if pmid in seen_pmids:
                raise ValueError(f"{path}:{line_number}: duplicate PMID {pmid}")
            seen_pmids.add(pmid)
            score = float(row["mean_positive_probability"])
            threshold = float(row["threshold"])
            prediction = int(row["prediction"])
            label = int(row["label"])
            if not 0.0 <= score <= 1.0 or not 0.0 <= threshold <= 1.0:
                raise ValueError(f"{path}:{line_number}: probability/cutoff outside [0,1]")
            if label not in (0, 1) or prediction not in (0, 1):
                raise ValueError(f"{path}:{line_number}: label/prediction must be 0 or 1")
            if prediction != int(score >= threshold):
                raise ValueError(
                    f"{path}:{line_number}: prediction disagrees with score >= threshold"
                )
            rows.append(row)
    if not rows:
        raise ValueError(f"Prediction file is empty: {path}")
    return rows


def percentile_interval(
    values: np.ndarray, confidence_level: float
) -> dict[str, float]:
    alpha = 1.0 - confidence_level
    return {
        "lower": float(np.quantile(values, alpha / 2.0)),
        "upper": float(np.quantile(values, 1.0 - alpha / 2.0)),
        "confidence_level": confidence_level,
    }


def bootstrap_location_and_variance(
    values: np.ndarray,
    *,
    replicates: int,
    confidence_level: float,
    rng: np.random.Generator,
    block_size: int = 128,
) -> dict[str, dict[str, float] | None]:
    n = len(values)
    means = np.empty(replicates, dtype=float)
    variances = np.empty(replicates, dtype=float) if n > 1 else None
    offset = 0
    while offset < replicates:
        count = min(block_size, replicates - offset)
        indices = rng.integers(0, n, size=(count, n))
        samples = values[indices]
        means[offset : offset + count] = np.mean(samples, axis=1)
        if variances is not None:
            variances[offset : offset + count] = np.var(samples, axis=1, ddof=1)
        offset += count
    return {
        "mean": percentile_interval(means, confidence_level),
        "sample_variance": (
            None
            if variances is None
            else percentile_interval(variances, confidence_level)
        ),
        "method": {
            "name": "nonparametric percentile bootstrap",
            "replicates": replicates,
        },
    }


def bootstrap_difference(
    first: np.ndarray,
    second: np.ndarray,
    *,
    replicates: int,
    confidence_level: float,
    rng: np.random.Generator,
    block_size: int = 128,
) -> dict[str, Any]:
    differences = np.empty(replicates, dtype=float)
    offset = 0
    while offset < replicates:
        count = min(block_size, replicates - offset)
        first_indices = rng.integers(0, len(first), size=(count, len(first)))
        second_indices = rng.integers(0, len(second), size=(count, len(second)))
        differences[offset : offset + count] = (
            np.mean(first[first_indices], axis=1)
            - np.mean(second[second_indices], axis=1)
        )
        offset += count
    result = percentile_interval(differences, confidence_level)
    result.update(
        {
            "method": "independent nonparametric percentile bootstrap",
            "replicates": replicates,
        }
    )
    return result


def wilson_interval(
    successes: int, total: int, confidence_level: float
) -> dict[str, float]:
    if total < 1:
        raise ValueError("Wilson interval requires total > 0")
    alpha = 1.0 - confidence_level
    z = NormalDist().inv_cdf(1.0 - alpha / 2.0)
    proportion = successes / total
    denominator = 1.0 + z * z / total
    centre = (proportion + z * z / (2.0 * total)) / denominator
    half_width = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / total
            + z * z / (4.0 * total * total)
        )
        / denominator
    )
    return {
        "lower": max(0.0, centre - half_width),
        "upper": min(1.0, centre + half_width),
        "confidence_level": confidence_level,
        "method": "Wilson score interval",
    }


def normal_mean_interval(
    mean: float,
    standard_error: float,
    confidence_level: float,
) -> dict[str, float | str]:
    alpha = 1.0 - confidence_level
    z = NormalDist().inv_cdf(1.0 - alpha / 2.0)
    return {
        "lower": mean - z * standard_error,
        "upper": mean + z * standard_error,
        "confidence_level": confidence_level,
        "method": "normal approximation",
    }


def summarise_group(
    rows: list[dict[str, Any]],
    *,
    confidence_level: float,
    bootstrap_replicates: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    scores = np.asarray(
        [float(row["mean_positive_probability"]) for row in rows], dtype=float
    )
    predictions = np.asarray([int(row["prediction"]) for row in rows], dtype=int)
    labels = np.asarray([int(row["label"]) for row in rows], dtype=int)
    thresholds = {float(row["threshold"]) for row in rows}
    if len(thresholds) != 1:
        raise ValueError("Each prediction group must use exactly one frozen threshold")
    threshold = next(iter(thresholds))
    n = len(scores)
    sample_variance = float(np.var(scores, ddof=1)) if n > 1 else None
    standard_deviation = math.sqrt(sample_variance) if sample_variance is not None else None
    standard_error = standard_deviation / math.sqrt(n) if standard_deviation is not None else None
    positive_count = int(np.sum(predictions))
    positive_rate = positive_count / n
    quantile_levels = [0.025, 0.05, 0.25, 0.5, 0.75, 0.95, 0.975]
    bootstrap = bootstrap_location_and_variance(
        scores,
        replicates=bootstrap_replicates,
        confidence_level=confidence_level,
        rng=rng,
    )
    metric_rows = [
        {
            "pmid": str(row["pmid"]),
            "label": int(row["label"]),
            "mean_positive_probability": float(row["mean_positive_probability"]),
        }
        for row in rows
    ]
    return {
        "n_articles": n,
        "label_counts": {
            "0": int(np.sum(labels == 0)),
            "1": int(np.sum(labels == 1)),
        },
        "threshold": threshold,
        "positive_probability": {
            "mean": float(np.mean(scores)),
            "sample_variance": sample_variance,
            "standard_deviation": standard_deviation,
            "standard_error": standard_error,
            "normal_mean_confidence_interval": (
                None
                if standard_error is None
                else normal_mean_interval(
                    float(np.mean(scores)), standard_error, confidence_level
                )
            ),
            "bootstrap_confidence_intervals": bootstrap,
            "minimum": float(np.min(scores)),
            "maximum": float(np.max(scores)),
            "quantiles": {
                str(level): float(np.quantile(scores, level))
                for level in quantile_levels
            },
        },
        "thresholded_classification": {
            "predicted_positive_count": positive_count,
            "predicted_negative_count": n - positive_count,
            "predicted_positive_rate": positive_rate,
            "predicted_positive_rate_percent": 100.0 * positive_rate,
            "bernoulli_sample_variance": (
                float(np.var(predictions, ddof=1)) if n > 1 else None
            ),
            "positive_rate_confidence_interval": wilson_interval(
                positive_count, n, confidence_level
            ),
        },
        "article_classification_metrics": compute_article_metrics(
            metric_rows, threshold
        ),
    }


def cohens_d(first: np.ndarray, second: np.ndarray) -> float | None:
    if len(first) < 2 or len(second) < 2:
        return None
    first_variance = np.var(first, ddof=1)
    second_variance = np.var(second, ddof=1)
    pooled_variance = (
        (len(first) - 1) * first_variance + (len(second) - 1) * second_variance
    ) / (len(first) + len(second) - 2)
    if pooled_variance == 0:
        return None
    return float((np.mean(first) - np.mean(second)) / math.sqrt(pooled_variance))


def fmt(value: Any, digits: int = 6) -> str:
    return "NA" if value is None else f"{float(value):.{digits}f}"


def render_markdown(
    group_summaries: dict[str, dict[str, Any]],
    comparisons: list[dict[str, Any]],
    confidence_level: float,
    bootstrap_replicates: int,
    seed: int,
) -> str:
    confidence_percent = 100.0 * confidence_level
    lines = [
        "# Paper-mill screening statistical analysis",
        "",
        f"Frozen model threshold used throughout. Confidence level: {confidence_percent:.1f}%; "
        f"bootstrap replicates: {bootstrap_replicates}; seed: {seed}.",
        "",
        "## Cohort summary",
        "",
        "| Cohort | N | Mean P(positive) | Sample variance | Bootstrap mean CI | "
        "Predicted positive | Positive-rate Wilson CI |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, summary in group_summaries.items():
        probability = summary["positive_probability"]
        decision = summary["thresholded_classification"]
        mean_ci = probability["bootstrap_confidence_intervals"]["mean"]
        rate_ci = decision["positive_rate_confidence_interval"]
        lines.append(
            f"| {name} | {summary['n_articles']} | {fmt(probability['mean'])} | "
            f"{fmt(probability['sample_variance'])} | "
            f"[{fmt(mean_ci['lower'])}, {fmt(mean_ci['upper'])}] | "
            f"{decision['predicted_positive_count']} "
            f"({decision['predicted_positive_rate_percent']:.3f}%) | "
            f"[{100 * rate_ci['lower']:.3f}%, {100 * rate_ci['upper']:.3f}%] |"
        )
    if comparisons:
        lines.extend(
            [
                "",
                "## Pairwise comparisons",
                "",
                "Differences are first cohort minus second cohort.",
                "",
                "| Comparison | Mean-probability difference | Bootstrap CI | "
                "Cohen's d | Positive-rate difference | Bootstrap CI |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for comparison in comparisons:
            mean_ci = comparison["mean_probability_difference"][
                "bootstrap_confidence_interval"
            ]
            rate_ci = comparison["positive_rate_difference"][
                "bootstrap_confidence_interval"
            ]
            lines.append(
                f"| {comparison['first_group']} - {comparison['second_group']} | "
                f"{fmt(comparison['mean_probability_difference']['estimate'])} | "
                f"[{fmt(mean_ci['lower'])}, {fmt(mean_ci['upper'])}] | "
                f"{fmt(comparison['cohens_d'])} | "
                f"{100 * comparison['positive_rate_difference']['estimate']:.3f}% | "
                f"[{100 * rate_ci['lower']:.3f}%, {100 * rate_ci['upper']:.3f}%] |"
            )
    lines.extend(
        [
            "",
            "## Interpretation notes",
            "",
            "- Mean P(positive) is the mean article-level model probability, where each article "
            "score is the arithmetic mean of its chunk probabilities.",
            "- Predicted positive rate uses the cutoff selected only on the internal validation set.",
            "- For cohorts treated as negative, predicted positive rate is the observed false-positive "
            "rate under that labeling assumption; it is not a population prevalence estimate.",
            "- Confidence intervals quantify sampling uncertainty for these fixed cohorts and model; "
            "they do not include uncertainty from model training or label error.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    if not 0.0 < args.confidence_level < 1.0:
        raise ValueError("--confidence-level must be between 0 and 1")
    if args.bootstrap_replicates < 100:
        raise ValueError("--bootstrap-replicates must be at least 100")
    group_paths = parse_group_specs(args.group)
    output_dir = prepare_empty_output_dir(args.output_dir)
    rng = np.random.default_rng(args.seed)

    rows_by_group = {
        name: load_prediction_rows(path) for name, path in group_paths.items()
    }
    all_thresholds = {
        float(row["threshold"])
        for rows in rows_by_group.values()
        for row in rows
    }
    if len(all_thresholds) != 1:
        raise ValueError("All groups must use the same frozen model threshold")

    group_summaries = {
        name: summarise_group(
            rows,
            confidence_level=args.confidence_level,
            bootstrap_replicates=args.bootstrap_replicates,
            rng=rng,
        )
        for name, rows in rows_by_group.items()
    }
    comparisons: list[dict[str, Any]] = []
    for first_name, second_name in itertools.combinations(rows_by_group, 2):
        first_rows = rows_by_group[first_name]
        second_rows = rows_by_group[second_name]
        first_scores = np.asarray(
            [float(row["mean_positive_probability"]) for row in first_rows]
        )
        second_scores = np.asarray(
            [float(row["mean_positive_probability"]) for row in second_rows]
        )
        first_predictions = np.asarray(
            [int(row["prediction"]) for row in first_rows], dtype=float
        )
        second_predictions = np.asarray(
            [int(row["prediction"]) for row in second_rows], dtype=float
        )
        comparisons.append(
            {
                "first_group": first_name,
                "second_group": second_name,
                "mean_probability_difference": {
                    "estimate": float(np.mean(first_scores) - np.mean(second_scores)),
                    "bootstrap_confidence_interval": bootstrap_difference(
                        first_scores,
                        second_scores,
                        replicates=args.bootstrap_replicates,
                        confidence_level=args.confidence_level,
                        rng=rng,
                    ),
                },
                "positive_rate_difference": {
                    "estimate": float(
                        np.mean(first_predictions) - np.mean(second_predictions)
                    ),
                    "bootstrap_confidence_interval": bootstrap_difference(
                        first_predictions,
                        second_predictions,
                        replicates=args.bootstrap_replicates,
                        confidence_level=args.confidence_level,
                        rng=rng,
                    ),
                },
                "cohens_d": cohens_d(first_scores, second_scores),
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "frozen_threshold": next(iter(all_thresholds)),
        "confidence_level": args.confidence_level,
        "bootstrap_replicates": args.bootstrap_replicates,
        "seed": args.seed,
        "input_files": {
            name: file_fingerprint(path) for name, path in group_paths.items()
        },
        "groups": group_summaries,
        "pairwise_comparisons": comparisons,
    }
    write_json(output_dir / "analysis.json", payload)
    markdown = render_markdown(
        group_summaries,
        comparisons,
        args.confidence_level,
        args.bootstrap_replicates,
        args.seed,
    )
    (output_dir / "analysis.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"Analysis artifacts: {output_dir}")


if __name__ == "__main__":
    main()
