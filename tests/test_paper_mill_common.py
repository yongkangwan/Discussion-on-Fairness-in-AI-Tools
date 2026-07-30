from __future__ import annotations

import json
from pathlib import Path

import pytest

from paper_mill_common import (
    DynamicPaddingCollator,
    aggregate_chunk_predictions,
    choose_threshold,
    compute_article_metrics,
    load_labeled_corpus,
    stratified_article_split,
)


def _row(pmid: str, chunk_index: int, label: int, tokens: list[int]) -> dict:
    return {
        "pmid": pmid,
        "chunk_index": chunk_index,
        "label": label,
        "input_ids": tokens,
        "attention_mask": [1] * len(tokens),
        "token_type_ids": [0] * len(tokens),
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )


def test_loader_forces_role_labels_and_merges_identical_chunks(tmp_path: Path) -> None:
    positive = tmp_path / "positive.jsonl"
    negative_a = tmp_path / "negative_a.jsonl"
    negative_b = tmp_path / "negative_b.jsonl"
    _write_jsonl(positive, [_row("p1", 0, 0, [101, 102])])
    duplicate_negative = _row("n1", 0, 0, [101, 200, 102])
    _write_jsonl(negative_a, [duplicate_negative])
    _write_jsonl(negative_b, [duplicate_negative])

    corpus = load_labeled_corpus([positive], [negative_a, negative_b])

    assert corpus.article_labels == {"n1": 0, "p1": 1}
    assert len(corpus.chunks) == 2
    assert corpus.source_stats[0]["label_overrides"] == 1
    negative_record = next(record for record in corpus.chunks if record.pmid == "n1")
    assert len(negative_record.sources) == 2


def test_loader_rejects_cross_role_pmid(tmp_path: Path) -> None:
    positive = tmp_path / "positive.jsonl"
    negative = tmp_path / "negative.jsonl"
    _write_jsonl(positive, [_row("same", 0, 1, [101, 102])])
    _write_jsonl(negative, [_row("same", 0, 0, [101, 102])])

    with pytest.raises(ValueError, match="both positive and negative"):
        load_labeled_corpus([positive], [negative])


def test_article_split_is_stratified_and_has_no_leakage() -> None:
    labels = {f"p{i}": 1 for i in range(30)}
    labels.update({f"n{i}": 0 for i in range(30)})

    split = stratified_article_split(
        labels,
        train_ratio=0.8,
        validation_ratio=0.1,
        test_ratio=0.1,
        seed=42,
    )

    sets = {name: set(pmids) for name, pmids in split.items()}
    assert len(sets["train"]) == 48
    assert len(sets["validation"]) == 6
    assert len(sets["test"]) == 6
    assert sets["train"].isdisjoint(sets["validation"])
    assert sets["train"].isdisjoint(sets["test"])
    assert sets["validation"].isdisjoint(sets["test"])
    for pmids in sets.values():
        assert sum(labels[pmid] for pmid in pmids) == len(pmids) // 2


def test_chunk_probabilities_are_averaged_per_article() -> None:
    chunks = [
        {
            "pmid": "a",
            "chunk_index": 0,
            "label": 1,
            "positive_probability": 0.2,
            "sources": ["x"],
        },
        {
            "pmid": "a",
            "chunk_index": 1,
            "label": 1,
            "positive_probability": 0.8,
            "sources": ["x"],
        },
        {
            "pmid": "b",
            "chunk_index": 0,
            "label": 0,
            "positive_probability": 0.1,
            "sources": ["y"],
        },
    ]

    articles = aggregate_chunk_predictions(chunks)

    assert articles[0]["pmid"] == "a"
    assert articles[0]["n_chunks"] == 2
    assert articles[0]["mean_positive_probability"] == pytest.approx(0.5)


def test_threshold_is_selected_on_article_scores() -> None:
    articles = [
        {"pmid": "n1", "label": 0, "mean_positive_probability": 0.1},
        {"pmid": "n2", "label": 0, "mean_positive_probability": 0.4},
        {"pmid": "p1", "label": 1, "mean_positive_probability": 0.6},
        {"pmid": "p2", "label": 1, "mean_positive_probability": 0.9},
    ]

    selection = choose_threshold(articles, objective="youden")
    metrics = compute_article_metrics(articles, selection["threshold"])

    assert selection["threshold"] == pytest.approx(0.6)
    assert metrics["sensitivity_recall"] == 1.0
    assert metrics["specificity"] == 1.0
    assert metrics["auroc"] == 1.0


def test_positive_only_metrics_do_not_claim_specificity_or_auroc() -> None:
    articles = [
        {"pmid": "p1", "label": 1, "mean_positive_probability": 0.8},
        {"pmid": "p2", "label": 1, "mean_positive_probability": 0.2},
    ]

    metrics = compute_article_metrics(articles, threshold=0.5)

    assert metrics["single_class_evaluation"] is True
    assert metrics["sensitivity_recall"] == 0.5
    assert metrics["specificity"] is None
    assert metrics["auroc"] is None
    assert metrics["accuracy"] is None


def test_dynamic_padding_collator_preserves_metadata() -> None:
    from paper_mill_common import ChunkRecord

    records = [
        ChunkRecord("a", 0, 1, [101, 102], [1, 1], [0, 0], {"x"}),
        ChunkRecord("b", 0, 0, [101, 200, 102], [1, 1, 1], [0, 0, 0], {"y"}),
    ]

    batch = DynamicPaddingCollator(pad_token_id=0)(records)

    assert batch["input_ids"].shape == (2, 3)
    assert batch["input_ids"][0].tolist() == [101, 102, 0]
    assert batch["attention_mask"][0].tolist() == [1, 1, 0]
    assert batch["pmids"] == ["a", "b"]
