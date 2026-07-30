from __future__ import annotations

import json
import sys
from pathlib import Path

import transformers
from transformers import BertConfig, BertForSequenceClassification, BertTokenizerFast

import test as evaluate_script
import train as train_script


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )


def _token_row(pmid: str, label: int, content_token: int) -> dict:
    return {
        "pmid": pmid,
        "chunk_index": 0,
        "label": label,
        "input_ids": [2, content_token, 3],
        "attention_mask": [1, 1, 1],
        "token_type_ids": [0, 0, 0],
    }


def _make_tiny_local_bert(model_dir: Path) -> None:
    model_dir.mkdir()
    vocab_path = model_dir / "vocab.txt"
    vocab_path.write_text(
        "[PAD]\n[UNK]\n[CLS]\n[SEP]\n[MASK]\npaper\nauthentic\n",
        encoding="utf-8",
    )
    major_version = int(transformers.__version__.split(".", maxsplit=1)[0])
    if major_version >= 5:
        tokenizer = BertTokenizerFast(vocab=str(vocab_path), do_lower_case=True)
    else:
        tokenizer = BertTokenizerFast(vocab_file=str(vocab_path), do_lower_case=True)
    tokenizer.save_pretrained(model_dir)
    config = BertConfig(
        vocab_size=7,
        hidden_size=8,
        num_hidden_layers=1,
        num_attention_heads=2,
        intermediate_size=16,
        hidden_dropout_prob=0.0,
        attention_probs_dropout_prob=0.0,
        max_position_embeddings=16,
        type_vocab_size=2,
        pad_token_id=0,
        num_labels=2,
    )
    BertForSequenceClassification(config).save_pretrained(model_dir)


def test_tiny_model_training_and_external_evaluation(
    tmp_path: Path, monkeypatch
) -> None:
    model_dir = tmp_path / "tiny_bert"
    _make_tiny_local_bert(model_dir)
    positive = tmp_path / "positive.jsonl"
    negative = tmp_path / "negative.jsonl"
    _write_jsonl(
        positive, [_token_row(f"p{i}", 1, 5) for i in range(10)]
    )
    _write_jsonl(
        negative, [_token_row(f"n{i}", 0, 6) for i in range(10)]
    )
    run_dir = tmp_path / "run"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "train.py",
            "--positive-files",
            str(positive),
            "--negative-files",
            str(negative),
            "--model-name",
            str(model_dir),
            "--local-files-only",
            "--output-dir",
            str(run_dir),
            "--epochs",
            "1",
            "--train-batch-size",
            "4",
            "--eval-batch-size",
            "4",
            "--gradient-accumulation-steps",
            "1",
            "--max-length",
            "16",
            "--num-workers",
            "0",
            "--log-every",
            "0",
            "--device",
            "cpu",
        ],
    )
    train_script.main()

    assert (run_dir / "best_model" / "config.json").is_file()
    assert (run_dir / "threshold.json").is_file()
    internal_results = json.loads(
        (run_dir / "internal_results.json").read_text(encoding="utf-8")
    )
    assert internal_results["internal_test"]["article_metrics"]["n_articles"] == 3

    external_positive = tmp_path / "external_positive.jsonl"
    external_negative = tmp_path / "external_negative.jsonl"
    # Positive rows intentionally carry the wrong on-disk label to verify the
    # source-role override used by the real PubPeer external file.
    _write_jsonl(
        external_positive,
        [_token_row("external_p1", 0, 5), _token_row("external_p2", 0, 5)],
    )
    _write_jsonl(
        external_negative,
        [_token_row("external_n1", 0, 6), _token_row("external_n2", 0, 6)],
    )
    external_dir = tmp_path / "external"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test.py",
            "--model-dir",
            str(run_dir / "best_model"),
            "--threshold-file",
            str(run_dir / "threshold.json"),
            "--positive-files",
            str(external_positive),
            "--negative-files",
            str(external_negative),
            "--output-dir",
            str(external_dir),
            "--batch-size",
            "4",
            "--max-length",
            "16",
            "--device",
            "cpu",
        ],
    )
    evaluate_script.main()

    external_results = json.loads(
        (external_dir / "external_results.json").read_text(encoding="utf-8")
    )
    assert external_results["article_metrics"]["n_articles"] == 4
    assert external_results["article_metrics"]["n_positive"] == 2
    assert external_results["source_load_stats"][0]["label_overrides"] == 2
