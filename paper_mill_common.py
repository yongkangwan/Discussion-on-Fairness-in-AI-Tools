"""Shared data, aggregation, threshold, and evaluation utilities.

The JSONL files in this project are already tokenized into BERT chunks.  This
module deliberately consumes those token arrays directly so that train and test
use exactly the same chunk boundaries.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import torch
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split
from torch.utils.data import Dataset


SCHEMA_VERSION = 1


@dataclass
class ChunkRecord:
    """One pre-tokenized chunk and its article-level metadata."""

    pmid: str
    chunk_index: int
    label: int
    input_ids: list[int]
    attention_mask: list[int]
    token_type_ids: list[int]
    sources: set[str] = field(default_factory=set)


@dataclass
class LoadedCorpus:
    """A de-duplicated collection of chunks grouped by PMID."""

    chunks: list[ChunkRecord]
    article_labels: dict[str, int]
    article_sources: dict[str, list[str]]
    source_stats: list[dict[str, Any]]

    @property
    def article_ids(self) -> list[str]:
        return sorted(self.article_labels)

    @property
    def n_articles(self) -> int:
        return len(self.article_labels)


class ChunkDataset(Dataset[ChunkRecord]):
    def __init__(self, chunks: Sequence[ChunkRecord]) -> None:
        self.chunks = list(chunks)

    def __len__(self) -> int:
        return len(self.chunks)

    def __getitem__(self, index: int) -> ChunkRecord:
        return self.chunks[index]


class DynamicPaddingCollator:
    """Dynamically pad pre-tokenized chunks to the longest item in a batch."""

    def __init__(self, pad_token_id: int = 0) -> None:
        self.pad_token_id = int(pad_token_id)

    def __call__(self, records: Sequence[ChunkRecord]) -> dict[str, Any]:
        if not records:
            raise ValueError("Cannot collate an empty batch")

        batch_size = len(records)
        max_len = max(len(record.input_ids) for record in records)
        input_ids = torch.full(
            (batch_size, max_len), self.pad_token_id, dtype=torch.long
        )
        attention_mask = torch.zeros((batch_size, max_len), dtype=torch.long)
        token_type_ids = torch.zeros((batch_size, max_len), dtype=torch.long)

        for row, record in enumerate(records):
            length = len(record.input_ids)
            input_ids[row, :length] = torch.tensor(record.input_ids, dtype=torch.long)
            attention_mask[row, :length] = torch.tensor(
                record.attention_mask, dtype=torch.long
            )
            token_type_ids[row, :length] = torch.tensor(
                record.token_type_ids, dtype=torch.long
            )

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids,
            "labels": torch.tensor([record.label for record in records], dtype=torch.long),
            "pmids": [record.pmid for record in records],
            "chunk_indices": [record.chunk_index for record in records],
            "sources": [sorted(record.sources) for record in records],
        }


def set_global_seed(seed: int, deterministic: bool = True) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if deterministic:
        torch.use_deterministic_algorithms(True, warn_only=True)
        if hasattr(torch.backends, "cudnn"):
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.deterministic = True


def resolve_device(requested: str) -> torch.device:
    requested = requested.lower()
    if requested == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")
    device = torch.device(requested)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is False")
    if device.type == "mps" and not (
        hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    ):
        raise RuntimeError("MPS was requested but is not available")
    return device


def _coerce_int_list(
    value: Any,
    *,
    field_name: str,
    path: Path,
    line_number: int,
) -> list[int]:
    if not isinstance(value, list) or not value:
        raise ValueError(
            f"{path}:{line_number}: {field_name} must be a non-empty JSON array"
        )
    result: list[int] = []
    for position, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, int):
            raise ValueError(
                f"{path}:{line_number}: {field_name}[{position}] must be an integer"
            )
        result.append(item)
    return result


def _same_payload(left: ChunkRecord, right: ChunkRecord) -> bool:
    return (
        left.label == right.label
        and left.input_ids == right.input_ids
        and left.attention_mask == right.attention_mask
        and left.token_type_ids == right.token_type_ids
    )


def _normalise_role_files(
    positive_files: Sequence[str | Path], negative_files: Sequence[str | Path]
) -> list[tuple[Path, int, str]]:
    entries: list[tuple[Path, int, str]] = []
    seen: dict[Path, str] = {}
    for paths, label, role in (
        (positive_files, 1, "positive"),
        (negative_files, 0, "negative"),
    ):
        for raw_path in paths:
            path = Path(raw_path).expanduser().resolve()
            if not path.is_file():
                raise FileNotFoundError(f"Input JSONL does not exist: {path}")
            if path in seen:
                raise ValueError(
                    f"Input file was supplied more than once or in both roles: {path} "
                    f"({seen[path]} and {role})"
                )
            seen[path] = role
            entries.append((path, label, role))
    if not entries:
        raise ValueError("At least one positive or negative JSONL file is required")
    return entries


def load_labeled_corpus(
    positive_files: Sequence[str | Path],
    negative_files: Sequence[str | Path],
    *,
    max_length: int = 512,
) -> LoadedCorpus:
    """Load JSONL files and force labels according to their CLI role.

    Repeated ``(pmid, chunk_index)`` records with identical token payloads are
    merged.  Conflicting payloads or article labels fail fast.
    """

    if max_length < 1:
        raise ValueError("max_length must be positive")

    entries = _normalise_role_files(positive_files, negative_files)
    chunks_by_key: dict[tuple[str, int], ChunkRecord] = {}
    article_labels: dict[str, int] = {}
    article_sources_sets: dict[str, set[str]] = defaultdict(set)
    source_stats: list[dict[str, Any]] = []

    for path, forced_label, role in entries:
        display_source = str(path)
        stats: dict[str, Any] = {
            "path": display_source,
            "role": role,
            "forced_label": forced_label,
            "lines": 0,
            "new_chunks": 0,
            "duplicate_chunks_merged": 0,
            "label_overrides": 0,
            "original_label_counts": {},
        }
        original_counts: defaultdict[str, int] = defaultdict(int)

        with path.open("r", encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                stats["lines"] += 1
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
                if not isinstance(raw, dict):
                    raise ValueError(f"{path}:{line_number}: each JSONL row must be an object")

                original_label = raw.get("label", None)
                original_counts[str(original_label)] += 1
                if original_label != forced_label:
                    stats["label_overrides"] += 1

                raw_pmid = raw.get("pmid")
                if raw_pmid is None:
                    raise ValueError(f"{path}:{line_number}: missing pmid")
                pmid = str(raw_pmid).strip()
                if not pmid:
                    raise ValueError(f"{path}:{line_number}: empty pmid")

                chunk_index = raw.get("chunk_index")
                if (
                    isinstance(chunk_index, bool)
                    or not isinstance(chunk_index, int)
                    or chunk_index < 0
                ):
                    raise ValueError(
                        f"{path}:{line_number}: chunk_index must be a non-negative integer"
                    )

                input_ids = _coerce_int_list(
                    raw.get("input_ids"),
                    field_name="input_ids",
                    path=path,
                    line_number=line_number,
                )
                attention_mask = _coerce_int_list(
                    raw.get("attention_mask"),
                    field_name="attention_mask",
                    path=path,
                    line_number=line_number,
                )
                raw_token_types = raw.get("token_type_ids")
                token_type_ids = (
                    [0] * len(input_ids)
                    if raw_token_types is None
                    else _coerce_int_list(
                        raw_token_types,
                        field_name="token_type_ids",
                        path=path,
                        line_number=line_number,
                    )
                )

                if not (
                    len(input_ids) == len(attention_mask) == len(token_type_ids)
                ):
                    raise ValueError(
                        f"{path}:{line_number}: input_ids, attention_mask, and "
                        "token_type_ids must have equal lengths"
                    )
                if len(input_ids) > max_length:
                    raise ValueError(
                        f"{path}:{line_number}: token length {len(input_ids)} exceeds "
                        f"max_length={max_length}; pre-split this article instead of truncating"
                    )
                if min(input_ids) < 0:
                    raise ValueError(f"{path}:{line_number}: input_ids cannot be negative")
                if any(value not in (0, 1) for value in attention_mask):
                    raise ValueError(
                        f"{path}:{line_number}: attention_mask must contain only 0/1"
                    )
                if not any(attention_mask):
                    raise ValueError(f"{path}:{line_number}: attention_mask is all zero")
                if min(token_type_ids) < 0:
                    raise ValueError(
                        f"{path}:{line_number}: token_type_ids cannot be negative"
                    )

                known_label = article_labels.get(pmid)
                if known_label is not None and known_label != forced_label:
                    raise ValueError(
                        f"PMID {pmid} occurs in both positive and negative inputs"
                    )
                article_labels[pmid] = forced_label
                article_sources_sets[pmid].add(display_source)

                record = ChunkRecord(
                    pmid=pmid,
                    chunk_index=chunk_index,
                    label=forced_label,
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    token_type_ids=token_type_ids,
                    sources={display_source},
                )
                key = (pmid, chunk_index)
                existing = chunks_by_key.get(key)
                if existing is None:
                    chunks_by_key[key] = record
                    stats["new_chunks"] += 1
                elif _same_payload(existing, record):
                    existing.sources.add(display_source)
                    stats["duplicate_chunks_merged"] += 1
                else:
                    raise ValueError(
                        f"Conflicting payloads for PMID {pmid}, chunk_index {chunk_index}; "
                        f"latest occurrence is {path}:{line_number}"
                    )

        stats["original_label_counts"] = dict(sorted(original_counts.items()))
        source_stats.append(stats)

    indices_by_article: dict[str, list[int]] = defaultdict(list)
    for pmid, chunk_index in chunks_by_key:
        indices_by_article[pmid].append(chunk_index)
    for pmid, indices in indices_by_article.items():
        actual = sorted(indices)
        expected = list(range(len(actual)))
        if actual != expected:
            raise ValueError(
                f"PMID {pmid} has non-contiguous chunk indices {actual}; expected {expected}"
            )

    chunks = sorted(chunks_by_key.values(), key=lambda item: (item.pmid, item.chunk_index))
    article_sources = {
        pmid: sorted(sources) for pmid, sources in article_sources_sets.items()
    }
    return LoadedCorpus(
        chunks=chunks,
        article_labels=dict(sorted(article_labels.items())),
        article_sources=dict(sorted(article_sources.items())),
        source_stats=source_stats,
    )


def validate_token_ranges(
    corpus: LoadedCorpus,
    *,
    vocab_size: int,
    type_vocab_size: int = 2,
) -> None:
    if vocab_size < 1 or type_vocab_size < 1:
        raise ValueError("Model vocab sizes must be positive")
    for record in corpus.chunks:
        largest_token = max(record.input_ids)
        if largest_token >= vocab_size:
            raise ValueError(
                f"PMID {record.pmid} chunk {record.chunk_index} contains token id "
                f"{largest_token}, but model vocab_size={vocab_size}"
            )
        largest_type = max(record.token_type_ids)
        if largest_type >= type_vocab_size:
            raise ValueError(
                f"PMID {record.pmid} chunk {record.chunk_index} contains token_type_id "
                f"{largest_type}, but model type_vocab_size={type_vocab_size}"
            )


def stratified_article_split(
    article_labels: Mapping[str, int],
    *,
    train_ratio: float,
    validation_ratio: float,
    test_ratio: float,
    seed: int,
) -> dict[str, list[str]]:
    ratios = (train_ratio, validation_ratio, test_ratio)
    if any(ratio <= 0 for ratio in ratios):
        raise ValueError("train, validation, and test ratios must all be positive")
    if not math.isclose(sum(ratios), 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError(f"Split ratios must sum to 1.0, got {sum(ratios):.12f}")

    article_ids = sorted(article_labels)
    labels = [article_labels[pmid] for pmid in article_ids]
    if set(labels) != {0, 1}:
        raise ValueError("Stratified train/validation/test splitting requires both labels")

    holdout_ratio = validation_ratio + test_ratio
    try:
        train_ids, holdout_ids = train_test_split(
            article_ids,
            test_size=holdout_ratio,
            random_state=seed,
            shuffle=True,
            stratify=labels,
        )
        holdout_labels = [article_labels[pmid] for pmid in holdout_ids]
        relative_test_ratio = test_ratio / holdout_ratio
        validation_ids, test_ids = train_test_split(
            holdout_ids,
            test_size=relative_test_ratio,
            random_state=seed,
            shuffle=True,
            stratify=holdout_labels,
        )
    except ValueError as exc:
        raise ValueError(
            "Could not create a stratified article-level split. Each class needs "
            "enough articles for all three subsets."
        ) from exc

    split = {
        "train": sorted(train_ids),
        "validation": sorted(validation_ids),
        "test": sorted(test_ids),
    }
    split_sets = {name: set(ids) for name, ids in split.items()}
    if (
        split_sets["train"] & split_sets["validation"]
        or split_sets["train"] & split_sets["test"]
        or split_sets["validation"] & split_sets["test"]
    ):
        raise AssertionError("Article-level split leakage detected")
    if set().union(*split_sets.values()) != set(article_ids):
        raise AssertionError("Article-level split lost one or more PMIDs")
    return split


def select_chunks(corpus: LoadedCorpus, article_ids: Iterable[str]) -> list[ChunkRecord]:
    selected = set(article_ids)
    return [record for record in corpus.chunks if record.pmid in selected]


def split_summary(
    split: Mapping[str, Sequence[str]], article_labels: Mapping[str, int]
) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for name, article_ids in split.items():
        positives = sum(article_labels[pmid] == 1 for pmid in article_ids)
        negatives = sum(article_labels[pmid] == 0 for pmid in article_ids)
        result[name] = {
            "articles": len(article_ids),
            "positive_articles": int(positives),
            "negative_articles": int(negatives),
        }
    return result


def aggregate_chunk_predictions(
    chunk_predictions: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Average positive-class probabilities across all chunks of each article."""

    grouped: dict[str, dict[str, Any]] = {}
    for row in chunk_predictions:
        pmid = str(row["pmid"])
        label = int(row["label"])
        probability = float(row["positive_probability"])
        if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
            raise ValueError(f"Invalid positive probability for PMID {pmid}: {probability}")
        group = grouped.setdefault(
            pmid,
            {
                "pmid": pmid,
                "label": label,
                "probabilities": [],
                "chunk_indices": [],
                "sources": set(),
            },
        )
        if group["label"] != label:
            raise ValueError(f"Inconsistent chunk labels for PMID {pmid}")
        group["probabilities"].append(probability)
        group["chunk_indices"].append(int(row["chunk_index"]))
        group["sources"].update(row.get("sources", []))

    article_rows: list[dict[str, Any]] = []
    for pmid in sorted(grouped):
        group = grouped[pmid]
        chunk_indices = sorted(group["chunk_indices"])
        if chunk_indices != list(range(len(chunk_indices))):
            raise ValueError(
                f"Prediction rows for PMID {pmid} have invalid chunk indices {chunk_indices}"
            )
        article_rows.append(
            {
                "pmid": pmid,
                "label": int(group["label"]),
                "n_chunks": len(group["probabilities"]),
                "mean_positive_probability": float(np.mean(group["probabilities"])),
                "sources": sorted(group["sources"]),
            }
        )
    return article_rows


def _safe_divide(numerator: float, denominator: float) -> float | None:
    return None if denominator == 0 else float(numerator / denominator)


def _score_summary(scores: np.ndarray) -> dict[str, float]:
    return {
        "min": float(np.min(scores)),
        "q1": float(np.quantile(scores, 0.25)),
        "median": float(np.median(scores)),
        "mean": float(np.mean(scores)),
        "q3": float(np.quantile(scores, 0.75)),
        "max": float(np.max(scores)),
    }


def compute_article_metrics(
    article_predictions: Sequence[Mapping[str, Any]], threshold: float
) -> dict[str, Any]:
    if not article_predictions:
        raise ValueError("No article predictions were supplied")
    if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be finite and in [0, 1]")

    labels = np.asarray([int(row["label"]) for row in article_predictions], dtype=int)
    scores = np.asarray(
        [float(row["mean_positive_probability"]) for row in article_predictions],
        dtype=float,
    )
    if not np.all(np.isin(labels, [0, 1])):
        raise ValueError("Article labels must be 0 or 1")
    predictions = (scores >= threshold).astype(int)

    tp = int(np.sum((labels == 1) & (predictions == 1)))
    tn = int(np.sum((labels == 0) & (predictions == 0)))
    fp = int(np.sum((labels == 0) & (predictions == 1)))
    fn = int(np.sum((labels == 1) & (predictions == 0)))
    n_positive = int(np.sum(labels == 1))
    n_negative = int(np.sum(labels == 0))
    has_both_classes = n_positive > 0 and n_negative > 0

    sensitivity = _safe_divide(tp, tp + fn)
    specificity = _safe_divide(tn, tn + fp)
    metrics: dict[str, Any] = {
        "n_articles": int(len(labels)),
        "n_positive": n_positive,
        "n_negative": n_negative,
        "threshold": float(threshold),
        "prediction_rule": "mean_positive_probability >= threshold",
        "score_summary": _score_summary(scores),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "sensitivity_recall": sensitivity,
        "specificity": specificity,
        "false_negative_rate": None if sensitivity is None else float(1.0 - sensitivity),
        "false_positive_rate": None if specificity is None else float(1.0 - specificity),
        "auroc": None,
        "average_precision": None,
        "accuracy": None,
        "balanced_accuracy": None,
        "precision_ppv": None,
        "npv": None,
        "f1": None,
        "mcc": None,
        "brier_score": None,
        "single_class_evaluation": not has_both_classes,
    }

    if has_both_classes:
        precision = _safe_divide(tp, tp + fp)
        npv = _safe_divide(tn, tn + fn)
        f1 = _safe_divide(2 * tp, 2 * tp + fp + fn)
        mcc_denominator = math.sqrt(
            (tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)
        )
        metrics.update(
            {
                "auroc": float(roc_auc_score(labels, scores)),
                "average_precision": float(average_precision_score(labels, scores)),
                "accuracy": float(np.mean(predictions == labels)),
                "balanced_accuracy": float((sensitivity + specificity) / 2.0),
                "precision_ppv": precision,
                "npv": npv,
                "f1": f1,
                "mcc": _safe_divide(tp * tn - fp * fn, mcc_denominator),
                "brier_score": float(np.mean((scores - labels) ** 2)),
            }
        )
    return metrics


def choose_threshold(
    article_predictions: Sequence[Mapping[str, Any]],
    *,
    objective: str = "youden",
) -> dict[str, Any]:
    """Choose a validation threshold with deterministic specificity-first ties."""

    allowed = {"youden", "f1", "balanced_accuracy"}
    if objective not in allowed:
        raise ValueError(f"objective must be one of {sorted(allowed)}, got {objective!r}")
    labels = np.asarray([int(row["label"]) for row in article_predictions], dtype=int)
    scores = np.asarray(
        [float(row["mean_positive_probability"]) for row in article_predictions],
        dtype=float,
    )
    if set(labels.tolist()) != {0, 1}:
        raise ValueError("Threshold selection requires both positive and negative articles")

    candidates = sorted(set([0.0, 1.0, *scores.tolist()]))
    best_key: tuple[float, float, float, float] | None = None
    best: dict[str, Any] | None = None
    for threshold in candidates:
        predictions = (scores >= threshold).astype(int)
        tp = int(np.sum((labels == 1) & (predictions == 1)))
        tn = int(np.sum((labels == 0) & (predictions == 0)))
        fp = int(np.sum((labels == 0) & (predictions == 1)))
        fn = int(np.sum((labels == 1) & (predictions == 0)))
        sensitivity = tp / (tp + fn)
        specificity = tn / (tn + fp)
        f1 = 0.0 if (2 * tp + fp + fn) == 0 else 2 * tp / (2 * tp + fp + fn)
        balanced_accuracy = (sensitivity + specificity) / 2.0
        values = {
            "youden": sensitivity + specificity - 1.0,
            "f1": f1,
            "balanced_accuracy": balanced_accuracy,
        }
        objective_value = float(values[objective])
        # Equal objective values prefer specificity, then sensitivity, then the
        # higher cutoff.  This makes the paper-mill screen conservative.
        key = (objective_value, specificity, sensitivity, float(threshold))
        if best_key is None or key > best_key:
            best_key = key
            best = {
                "threshold": float(threshold),
                "objective": objective,
                "objective_value": objective_value,
                "tie_break": "specificity, then sensitivity, then higher threshold",
                "n_candidates": len(candidates),
                "sensitivity_recall": float(sensitivity),
                "specificity": float(specificity),
                "f1": float(f1),
                "balanced_accuracy": float(balanced_accuracy),
                "youden": float(sensitivity + specificity - 1.0),
            }
    if best is None:
        raise AssertionError("Threshold search produced no candidate")
    return best


def attach_hard_predictions(
    article_predictions: Sequence[Mapping[str, Any]], threshold: float
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in article_predictions:
        result = dict(row)
        result["prediction"] = int(float(row["mean_positive_probability"]) >= threshold)
        result["threshold"] = float(threshold)
        rows.append(result)
    return rows


def file_sha256(path: str | Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while block := handle.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def file_fingerprint(path: str | Path) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    stat = resolved.stat()
    return {
        "path": str(resolved),
        "size_bytes": int(stat.st_size),
        "sha256": file_sha256(resolved),
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_json(path: str | Path, payload: Any) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(
            payload,
            handle,
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
            default=_json_default,
            allow_nan=False,
        )
        handle.write("\n")


def write_jsonl(path: str | Path, rows: Iterable[Mapping[str, Any]]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    dict(row),
                    ensure_ascii=False,
                    default=_json_default,
                    allow_nan=False,
                )
                + "\n"
            )


def prepare_empty_output_dir(path: str | Path) -> Path:
    destination = Path(path).expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(
            f"Output directory is not empty: {destination}. Use a new run directory "
            "to avoid mixing results from different experiments."
        )
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def load_threshold_file(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if "threshold" not in payload:
        raise ValueError(f"Threshold file has no 'threshold' field: {path}")
    threshold = float(payload["threshold"])
    if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
        raise ValueError(f"Threshold must be finite and in [0, 1] in {path}")
    payload["threshold"] = threshold
    return payload


def load_manifest_pmids(path: str | Path) -> set[str]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    articles = payload.get("articles")
    if not isinstance(articles, list):
        raise ValueError(f"Manifest has no valid 'articles' list: {path}")
    return {str(article["pmid"]) for article in articles}


def predict_chunks(
    model: torch.nn.Module,
    data_loader: torch.utils.data.DataLoader[Any],
    *,
    device: torch.device,
    use_fp16: bool = False,
) -> tuple[list[dict[str, Any]], float]:
    """Run deterministic chunk inference and return rows plus mean CE loss."""

    if use_fp16 and device.type != "cuda":
        raise ValueError("FP16 inference is supported only on CUDA")
    model.eval()
    rows: list[dict[str, Any]] = []
    total_loss = 0.0
    total_examples = 0
    with torch.inference_mode():
        for batch in data_loader:
            labels = batch["labels"].to(device, non_blocking=True)
            model_inputs = {
                "input_ids": batch["input_ids"].to(device, non_blocking=True),
                "attention_mask": batch["attention_mask"].to(
                    device, non_blocking=True
                ),
                "token_type_ids": batch["token_type_ids"].to(
                    device, non_blocking=True
                ),
            }
            with torch.autocast(
                device_type="cuda", dtype=torch.float16, enabled=use_fp16
            ):
                outputs = model(**model_inputs, labels=labels)
            probabilities = torch.softmax(outputs.logits.float(), dim=-1)[:, 1]
            batch_size = labels.shape[0]
            total_loss += float(outputs.loss.detach().cpu()) * batch_size
            total_examples += batch_size
            for index in range(batch_size):
                rows.append(
                    {
                        "pmid": batch["pmids"][index],
                        "chunk_index": int(batch["chunk_indices"][index]),
                        "label": int(labels[index].detach().cpu()),
                        "positive_probability": float(
                            probabilities[index].detach().cpu()
                        ),
                        "sources": batch["sources"][index],
                    }
                )
    if total_examples == 0:
        raise ValueError("Inference data loader was empty")
    return rows, total_loss / total_examples
