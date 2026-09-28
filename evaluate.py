"""Evaluate a trained paper-mill BERT model with its frozen cutoff."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification

from paper_mill_common import (
    SCHEMA_VERSION,
    ChunkDataset,
    DynamicPaddingCollator,
    aggregate_chunk_predictions,
    attach_hard_predictions,
    compute_article_metrics,
    file_fingerprint,
    load_labeled_corpus,
    load_manifest_pmids,
    load_threshold_file,
    predict_chunks,
    prepare_empty_output_dir,
    resolve_device,
    set_global_seed,
    validate_token_ranges,
    write_json,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate external positive/negative JSONL files after averaging each "
            "article's chunk probabilities. The validation cutoff is never refit."
        )
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("runs/paper_mill_bert_seed42/best_model"),
    )
    parser.add_argument(
        "--threshold-file",
        type=Path,
        default=None,
        help="Default: threshold.json in the parent of --model-dir.",
    )
    parser.add_argument(
        "--positive-files",
        nargs="*",
        type=Path,
        default=[],
        help="Positive-role external JSONL file(s); row labels are forced to 1.",
    )
    parser.add_argument(
        "--negative-files",
        nargs="*",
        type=Path,
        default=[],
        help=(
            "Optional external negative JSONL file(s); row labels are forced to 0. "
            "Without these, only positive-only sensitivity can be estimated."
        ),
    )
    parser.add_argument(
        "--manifest-file",
        type=Path,
        default=None,
        help=(
            "Training split manifest used for leakage checks. Default: "
            "split_manifest.json in the parent of --model-dir if present."
        ),
    )
    parser.add_argument(
        "--allow-training-overlap",
        action="store_true",
        help="Allow external PMIDs that occur in the training manifest (not recommended).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Default: external_test in the parent of --model-dir.",
    )
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument(
        "--save-chunk-predictions",
        action="store_true",
        help="Also save one probability row per chunk.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.batch_size < 1 or args.max_length < 1:
        raise ValueError("--batch-size and --max-length must be positive")
    if not args.positive_files and not args.negative_files:
        raise ValueError(
            "Provide at least one --positive-files or --negative-files input."
        )
    if args.num_workers < 0:
        raise ValueError("--num-workers cannot be negative")
    set_global_seed(args.seed)
    device = resolve_device(args.device)
    if args.fp16 and device.type != "cuda":
        raise ValueError("--fp16 requires a CUDA device")

    model_dir = args.model_dir.expanduser().resolve()
    if not model_dir.is_dir():
        raise FileNotFoundError(f"Model directory does not exist: {model_dir}")
    run_dir = model_dir.parent
    threshold_file = (
        args.threshold_file.expanduser().resolve()
        if args.threshold_file is not None
        else run_dir / "threshold.json"
    )
    if not threshold_file.is_file():
        raise FileNotFoundError(f"Threshold file does not exist: {threshold_file}")
    threshold_payload = load_threshold_file(threshold_file)
    threshold = float(threshold_payload["threshold"])
    aggregation = threshold_payload.get("aggregation")
    if aggregation is not None and "mean" not in str(aggregation).lower():
        raise ValueError(
            f"Threshold file expects unsupported aggregation method: {aggregation!r}"
        )

    output_dir = prepare_empty_output_dir(
        args.output_dir if args.output_dir is not None else run_dir / "external_test"
    )
    started_at = time.time()
    print("Loading external JSONL files and overriding labels by file role...", flush=True)
    corpus = load_labeled_corpus(
        args.positive_files,
        args.negative_files,
        max_length=args.max_length,
    )
    for stats in corpus.source_stats:
        if stats["label_overrides"]:
            print(
                f"Forced {stats['label_overrides']} labels to {stats['forced_label']} "
                f"for {stats['path']}",
                flush=True,
            )

    inferred_manifest = run_dir / "split_manifest.json"
    if args.manifest_file is not None:
        manifest_file: Path | None = args.manifest_file.expanduser().resolve()
        if not manifest_file.is_file():
            raise FileNotFoundError(f"Manifest file does not exist: {manifest_file}")
    elif inferred_manifest.is_file():
        manifest_file = inferred_manifest
    else:
        manifest_file = None

    overlap: list[str] = []
    if manifest_file is not None:
        training_pmids = load_manifest_pmids(manifest_file)
        overlap = sorted(training_pmids & set(corpus.article_ids))
        if overlap and not args.allow_training_overlap:
            preview = ", ".join(overlap[:10])
            raise ValueError(
                f"External data overlap the training manifest by {len(overlap)} PMIDs "
                f"(first values: {preview}). Use a disjoint external set or explicitly "
                "pass --allow-training-overlap."
            )
    else:
        print(
            "Warning: no split_manifest.json was found, so training/external PMID "
            "overlap could not be checked.",
            flush=True,
        )

    print(f"Loading model from {model_dir} on {device}...", flush=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_dir, local_files_only=True
    )
    threshold_run_id = threshold_payload.get("run_id")
    model_run_id = getattr(model.config, "paper_mill_run_id", None)
    if threshold_run_id is not None and threshold_run_id != model_run_id:
        raise ValueError(
            "The threshold file and model directory belong to different training "
            f"runs (threshold run_id={threshold_run_id!r}, model run_id={model_run_id!r})."
        )
    model_max_length = int(getattr(model.config, "max_position_embeddings", 512))
    if args.max_length > model_max_length:
        raise ValueError(
            f"--max-length={args.max_length} exceeds model max_position_embeddings="
            f"{model_max_length}"
        )
    validate_token_ranges(
        corpus,
        vocab_size=int(model.config.vocab_size),
        type_vocab_size=int(getattr(model.config, "type_vocab_size", 2)),
    )
    model.to(device)

    pad_token_id = getattr(model.config, "pad_token_id", None)
    if pad_token_id is None:
        raise ValueError("Saved model config has no pad_token_id")
    data_loader = DataLoader(
        ChunkDataset(corpus.chunks),
        batch_size=args.batch_size,
        shuffle=False,
        collate_fn=DynamicPaddingCollator(pad_token_id),
        num_workers=args.num_workers,
        pin_memory=device.type == "cuda",
        persistent_workers=args.num_workers > 0,
        drop_last=False,
    )
    chunk_rows, chunk_loss = predict_chunks(
        model,
        data_loader,
        device=device,
        use_fp16=args.fp16,
    )
    article_rows = aggregate_chunk_predictions(chunk_rows)
    metrics = compute_article_metrics(article_rows, threshold)
    output_rows = attach_hard_predictions(article_rows, threshold)

    write_jsonl(output_dir / "external_article_predictions.jsonl", output_rows)
    if args.save_chunk_predictions:
        write_jsonl(output_dir / "external_chunk_predictions.jsonl", chunk_rows)

    input_fingerprints: list[dict[str, Any]] = []
    for path in [*args.positive_files, *args.negative_files]:
        input_fingerprints.append(file_fingerprint(path))
    results = {
        "schema_version": SCHEMA_VERSION,
        "run_id": model_run_id,
        "command": " ".join(sys.argv),
        "model_dir": str(model_dir),
        "threshold_file": str(threshold_file),
        "threshold": threshold,
        "threshold_objective": threshold_payload.get("objective"),
        "aggregation": "arithmetic mean of chunk softmax P(label=1)",
        "chunk_loss": chunk_loss,
        "article_metrics": metrics,
        "source_load_stats": corpus.source_stats,
        "input_files": input_fingerprints,
        "training_manifest": None if manifest_file is None else str(manifest_file),
        "training_overlap_pmids": overlap,
        "elapsed_seconds": time.time() - started_at,
    }
    write_json(output_dir / "external_results.json", results)

    if metrics["single_class_evaluation"]:
        if metrics["n_positive"]:
            print(
                "Positive-only external evaluation complete: "
                f"articles={metrics['n_articles']}, "
                f"sensitivity={metrics['sensitivity_recall']:.6f}, "
                f"TP={metrics['tp']}, FN={metrics['fn']}. "
                "AUROC and specificity are undefined without external negatives.",
                flush=True,
            )
        else:
            print(
                "Negative-only external evaluation complete: "
                f"articles={metrics['n_articles']}, "
                f"specificity={metrics['specificity']:.6f}, "
                f"TN={metrics['tn']}, FP={metrics['fp']}. "
                "AUROC and sensitivity are undefined without external positives.",
                flush=True,
            )
    else:
        print(
            "External evaluation complete: "
            f"articles={metrics['n_articles']}, AUROC={metrics['auroc']:.6f}, "
            f"sensitivity={metrics['sensitivity_recall']:.6f}, "
            f"specificity={metrics['specificity']:.6f}",
            flush=True,
        )
    print(f"Artifacts: {output_dir}", flush=True)


if __name__ == "__main__":
    main()
