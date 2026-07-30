from __future__ import annotations

import json
import sys
from pathlib import Path

import analyze_predictions
import sample_articles


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )


def _chunk(pmid: str, chunk_index: int = 0, label: int = 0) -> dict:
    return {
        "pmid": pmid,
        "chunk_index": chunk_index,
        "label": label,
        "input_ids": [101, 102],
        "attention_mask": [1, 1],
        "token_type_ids": [0, 0],
    }


def test_article_sampler_excludes_pmids_and_keeps_all_chunks(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source.jsonl"
    exclusion = tmp_path / "exclusion.jsonl"
    rows = [_chunk(f"p{i}") for i in range(10)]
    rows.extend([_chunk("p0", 1), _chunk("p1", 1)])
    _write_jsonl(source, rows)
    _write_jsonl(exclusion, [_chunk("p2", label=1)])
    output = tmp_path / "sample.jsonl"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sample_articles.py",
            "--input",
            str(source),
            "--output",
            str(output),
            "--n-articles",
            "5",
            "--seed",
            "42",
            "--label",
            "0",
            "--exclude-jsonl",
            str(exclusion),
        ],
    )
    sample_articles.main()

    sampled_rows = [json.loads(line) for line in output.read_text().splitlines()]
    sampled_pmids = {row["pmid"] for row in sampled_rows}
    manifest = json.loads(
        Path(str(output) + ".manifest.json").read_text(encoding="utf-8")
    )
    assert len(sampled_pmids) == 5
    assert "p2" not in sampled_pmids
    assert manifest["sampled_articles"] == 5
    assert manifest["excluded_input_articles"] == 1
    for pmid in sampled_pmids:
        expected_chunks = 2 if pmid in {"p0", "p1"} else 1
        assert sum(row["pmid"] == pmid for row in sampled_rows) == expected_chunks


def _prediction(pmid: str, score: float, threshold: float = 0.5) -> dict:
    return {
        "pmid": pmid,
        "label": 0,
        "n_chunks": 1,
        "mean_positive_probability": score,
        "prediction": int(score >= threshold),
        "threshold": threshold,
        "sources": [],
    }


def test_analysis_reports_probability_and_positive_rate_intervals(
    tmp_path: Path, monkeypatch
) -> None:
    china = tmp_path / "china.jsonl"
    other = tmp_path / "other.jsonl"
    _write_jsonl(
        china,
        [_prediction("c1", 0.1), _prediction("c2", 0.4), _prediction("c3", 0.8)],
    )
    _write_jsonl(
        other,
        [_prediction("o1", 0.2), _prediction("o2", 0.3), _prediction("o3", 0.4)],
    )
    output_dir = tmp_path / "analysis"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "analyze_predictions.py",
            "--group",
            f"china={china}",
            "--group",
            f"other={other}",
            "--output-dir",
            str(output_dir),
            "--bootstrap-replicates",
            "200",
            "--seed",
            "42",
        ],
    )
    analyze_predictions.main()

    result = json.loads((output_dir / "analysis.json").read_text(encoding="utf-8"))
    china_summary = result["groups"]["china"]
    assert china_summary["positive_probability"]["mean"] == (0.1 + 0.4 + 0.8) / 3
    assert china_summary["thresholded_classification"]["predicted_positive_count"] == 1
    assert "positive_rate_confidence_interval" in china_summary[
        "thresholded_classification"
    ]
    assert len(result["pairwise_comparisons"]) == 1
    assert (output_dir / "analysis.md").is_file()
