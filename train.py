"""Fine-tune BERT on pre-tokenized paper-level chunks.

The split is made at PMID/article level.  Chunks inherit their article label for
training, while validation and test predictions are averaged back to one score
per article.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import math
import platform
import sys
import time
import uuid
from collections import Counter, defaultdict
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import torch
from torch.nn.utils import clip_grad_norm_
from torch.optim import AdamW
from torch.utils.data import DataLoader
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_scheduler,
)

from paper_mill_common import (
    SCHEMA_VERSION,
    ChunkDataset,
    DynamicPaddingCollator,
    aggregate_chunk_predictions,
    attach_hard_predictions,
    choose_threshold,
    compute_article_metrics,
    file_fingerprint,
    load_labeled_corpus,
    predict_chunks,
    prepare_empty_output_dir,
    resolve_device,
    select_chunks,
    set_global_seed,
    split_summary,
    stratified_article_split,
    validate_token_ranges,
    write_json,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fine-tune bert-base-uncased at chunk level, aggregate probabilities "
            "by PMID, select a validation cutoff, and evaluate the internal test set."
        )
    )
    parser.add_argument(
        "--positive-files",
        nargs="+",
        type=Path,
        required=True,
        help="Positive-role JSONL file(s); their row labels are forced to 1.",
    )
    parser.add_argument(
        "--negative-files",
        nargs="+",
        type=Path,
        required=True,
        help="Negative-role JSONL file(s); their row labels are forced to 0.",
    )
    parser.add_argument("--model-name", default="bert-base-uncased")
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Do not download missing Hugging Face model files.",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("runs/paper_mill_bert_seed42")
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--validation-ratio", type=float, default=0.175)
    parser.add_argument("--test-ratio", type=float, default=0.125)
    parser.add_argument("--max-length", type=int, default=512)

    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--learning-rate", type=float, default=1.4e-5)
    parser.add_argument("--weight-decay", type=float, default=0.025)
    parser.add_argument("--warmup-ratio", type=float, default=0.15)
    parser.add_argument("--train-batch-size", type=int, default=32)
    parser.add_argument("--eval-batch-size", type=int, default=32)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=1)
    parser.add_argument(
        "--scheduler-type",
        choices=["linear", "cosine", "cosine_with_restarts"],
        default="cosine",
    )
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--log-every", type=int, default=25)
    parser.add_argument(
        "--threshold-objective",
        choices=["youden", "f1", "balanced_accuracy"],
        default="youden",
        help="Validation-set objective used to choose the article cutoff.",
    )
    parser.add_argument(
        "--device",
        default="auto",
        help="auto, cpu, cuda, cuda:0, or mps (default: auto).",
    )
    parser.add_argument(
        "--fp16",
        action="store_true",
        help="Use CUDA automatic mixed precision. Only valid on CUDA.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    positive_integer_fields = (
        "epochs",
        "train_batch_size",
        "eval_batch_size",
        "gradient_accumulation_steps",
        "max_length",
    )
    for name in positive_integer_fields:
        if getattr(args, name) < 1:
            raise ValueError(f"--{name.replace('_', '-')} must be positive")
    if args.num_workers < 0:
        raise ValueError("--num-workers cannot be negative")
    if args.log_every < 0:
        raise ValueError("--log-every cannot be negative")
    if args.learning_rate <= 0:
        raise ValueError("--learning-rate must be positive")
    if args.weight_decay < 0:
        raise ValueError("--weight-decay cannot be negative")
    if not 0.0 <= args.warmup_ratio < 1.0:
        raise ValueError("--warmup-ratio must be in [0, 1)")
    if args.max_grad_norm <= 0:
        raise ValueError("--max-grad-norm must be positive")


def package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
    for package in ("torch", "transformers", "scikit-learn", "numpy"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def create_manifest(
    *,
    corpus: Any,
    split: dict[str, list[str]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    split_by_pmid = {
        pmid: split_name for split_name, pmids in split.items() for pmid in pmids
    }
    chunks_per_article: Counter[str] = Counter(record.pmid for record in corpus.chunks)
    file_roles = {
        str(Path(path).expanduser().resolve()): "positive"
        for path in args.positive_files
    }
    file_roles.update(
        {
            str(Path(path).expanduser().resolve()): "negative"
            for path in args.negative_files
        }
    )
    fingerprints = []
    for path, role in file_roles.items():
        fingerprint = file_fingerprint(path)
        fingerprint["role"] = role
        fingerprints.append(fingerprint)

    articles = []
    for pmid in sorted(corpus.article_labels):
        articles.append(
            {
                "pmid": pmid,
                "label": corpus.article_labels[pmid],
                "split": split_by_pmid[pmid],
                "n_chunks": int(chunks_per_article[pmid]),
                "sources": corpus.article_sources[pmid],
            }
        )
    summary = split_summary(split, corpus.article_labels)
    for split_name, pmids in split.items():
        summary[split_name]["chunks"] = len(select_chunks(corpus, pmids))

    return {
        "schema_version": SCHEMA_VERSION,
        "split_unit": "article/pmid",
        "stratified_by": "article label",
        "seed": args.seed,
        "ratios": {
            "train": args.train_ratio,
            "validation": args.validation_ratio,
            "test": args.test_ratio,
        },
        "summary": summary,
        "deduplicated_total_articles": corpus.n_articles,
        "deduplicated_total_chunks": len(corpus.chunks),
        "source_load_stats": corpus.source_stats,
        "input_files": fingerprints,
        "articles": articles,
    }


def make_data_loader(
    chunks: list[Any],
    *,
    batch_size: int,
    collator: DynamicPaddingCollator,
    shuffle: bool,
    num_workers: int,
    seed: int,
    pin_memory: bool,
) -> DataLoader[Any]:
    generator = torch.Generator()
    generator.manual_seed(seed)
    return DataLoader(
        ChunkDataset(chunks),
        batch_size=batch_size,
        shuffle=shuffle,
        collate_fn=collator,
        num_workers=num_workers,
        pin_memory=pin_memory,
        persistent_workers=num_workers > 0,
        generator=generator,
        drop_last=False,
    )


def create_optimizer(model: torch.nn.Module, learning_rate: float, weight_decay: float) -> AdamW:
    no_decay_terms = ("bias", "LayerNorm.weight", "layer_norm.weight")
    decay_parameters = []
    no_decay_parameters = []
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        if any(term in name for term in no_decay_terms):
            no_decay_parameters.append(parameter)
        else:
            decay_parameters.append(parameter)
    return AdamW(
        [
            {"params": decay_parameters, "weight_decay": weight_decay},
            {"params": no_decay_parameters, "weight_decay": 0.0},
        ],
        lr=learning_rate,
    )


def train_one_epoch(
    *,
    model: torch.nn.Module,
    data_loader: DataLoader[Any],
    optimizer: torch.optim.Optimizer,
    scheduler: Any,
    device: torch.device,
    gradient_accumulation_steps: int,
    max_grad_norm: float,
    use_fp16: bool,
    scaler: Any | None,
    epoch: int,
    log_every: int,
    global_optimizer_step: int,
) -> tuple[float, int]:
    model.train()
    optimizer.zero_grad(set_to_none=True)
    total_loss = 0.0
    total_examples = 0
    n_batches = len(data_loader)
    final_group_size = n_batches % gradient_accumulation_steps
    if final_group_size == 0:
        final_group_size = gradient_accumulation_steps

    for batch_number, batch in enumerate(data_loader, start=1):
        labels = batch["labels"].to(device, non_blocking=True)
        model_inputs = {
            "input_ids": batch["input_ids"].to(device, non_blocking=True),
            "attention_mask": batch["attention_mask"].to(device, non_blocking=True),
            "token_type_ids": batch["token_type_ids"].to(device, non_blocking=True),
        }
        amp_context = (
            torch.autocast(device_type="cuda", dtype=torch.float16)
            if use_fp16
            else nullcontext()
        )
        with amp_context:
            outputs = model(**model_inputs, labels=labels)
            loss = outputs.loss
        batch_size = labels.shape[0]
        total_loss += float(loss.detach().cpu()) * batch_size
        total_examples += batch_size

        scaled_loss = loss / gradient_accumulation_steps
        if scaler is None:
            scaled_loss.backward()
        else:
            scaler.scale(scaled_loss).backward()

        should_step = (
            batch_number % gradient_accumulation_steps == 0 or batch_number == n_batches
        )
        if not should_step:
            continue

        if scaler is not None:
            scaler.unscale_(optimizer)
        if batch_number == n_batches and final_group_size < gradient_accumulation_steps:
            correction = gradient_accumulation_steps / final_group_size
            for parameter in model.parameters():
                if parameter.grad is not None:
                    parameter.grad.mul_(correction)
        clip_grad_norm_(model.parameters(), max_grad_norm)
        if scaler is None:
            optimizer.step()
        else:
            scaler.step(optimizer)
            scaler.update()
        scheduler.step()
        optimizer.zero_grad(set_to_none=True)
        global_optimizer_step += 1

        if log_every and global_optimizer_step % log_every == 0:
            running_loss = total_loss / total_examples
            current_lr = scheduler.get_last_lr()[0]
            print(
                f"epoch={epoch} optimizer_step={global_optimizer_step} "
                f"batch={batch_number}/{n_batches} train_loss={running_loss:.6f} "
                f"lr={current_lr:.3e}",
                flush=True,
            )

    if total_examples == 0:
        raise ValueError("Training data loader was empty")
    return total_loss / total_examples, global_optimizer_step


def main() -> None:
    args = parse_args()
    validate_args(args)
    set_global_seed(args.seed)
    device = resolve_device(args.device)
    if args.fp16 and device.type != "cuda":
        raise ValueError("--fp16 requires a CUDA device")
    output_dir = prepare_empty_output_dir(args.output_dir)
    run_id = uuid.uuid4().hex
    started_at = time.time()

    print("Loading and validating pre-tokenized JSONL files...", flush=True)
    corpus = load_labeled_corpus(
        args.positive_files,
        args.negative_files,
        max_length=args.max_length,
    )
    split = stratified_article_split(
        corpus.article_labels,
        train_ratio=args.train_ratio,
        validation_ratio=args.validation_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )
    manifest = create_manifest(corpus=corpus, split=split, args=args)
    write_json(output_dir / "split_manifest.json", manifest)
    print(f"Split summary: {manifest['summary']}", flush=True)
    for stats in corpus.source_stats:
        if stats["label_overrides"]:
            print(
                f"Forced {stats['label_overrides']} labels to {stats['forced_label']} "
                f"for {stats['path']}",
                flush=True,
            )

    pretrained_kwargs: dict[str, Any] = {
        "local_files_only": args.local_files_only,
    }
    if args.cache_dir is not None:
        pretrained_kwargs["cache_dir"] = str(args.cache_dir)
    print(f"Loading model {args.model_name!r} on {device}...", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model_name, **pretrained_kwargs)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name,
        num_labels=2,
        **pretrained_kwargs,
    )
    # These names describe the screening decision, not ground-truth misconduct.
    model.config.id2label = {0: "SCREEN_NEGATIVE", 1: "SCREEN_POSITIVE"}
    model.config.label2id = {"SCREEN_NEGATIVE": 0, "SCREEN_POSITIVE": 1}
    model.config.paper_mill_run_id = run_id
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

    pad_token_id = tokenizer.pad_token_id
    if pad_token_id is None:
        pad_token_id = getattr(model.config, "pad_token_id", None)
    if pad_token_id is None:
        raise ValueError("The selected model/tokenizer has no pad_token_id")
    collator = DynamicPaddingCollator(pad_token_id)
    train_chunks = select_chunks(corpus, split["train"])
    validation_chunks = select_chunks(corpus, split["validation"])
    test_chunks = select_chunks(corpus, split["test"])
    pin_memory = device.type == "cuda"
    train_loader = make_data_loader(
        train_chunks,
        batch_size=args.train_batch_size,
        collator=collator,
        shuffle=True,
        num_workers=args.num_workers,
        seed=args.seed,
        pin_memory=pin_memory,
    )
    validation_loader = make_data_loader(
        validation_chunks,
        batch_size=args.eval_batch_size,
        collator=collator,
        shuffle=False,
        num_workers=args.num_workers,
        seed=args.seed,
        pin_memory=pin_memory,
    )
    test_loader = make_data_loader(
        test_chunks,
        batch_size=args.eval_batch_size,
        collator=collator,
        shuffle=False,
        num_workers=args.num_workers,
        seed=args.seed,
        pin_memory=pin_memory,
    )

    optimizer = create_optimizer(model, args.learning_rate, args.weight_decay)
    optimizer_steps_per_epoch = math.ceil(
        len(train_loader) / args.gradient_accumulation_steps
    )
    total_optimizer_steps = optimizer_steps_per_epoch * args.epochs
    warmup_steps = int(total_optimizer_steps * args.warmup_ratio)
    scheduler = get_scheduler(
        name=args.scheduler_type,
        optimizer=optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_optimizer_steps,
    )
    if args.fp16:
        # torch.amp.GradScaler was added after the earliest supported PyTorch
        # versions; retain a compatibility path for torch 2.1/2.2.
        if hasattr(torch.amp, "GradScaler"):
            scaler = torch.amp.GradScaler("cuda")
        else:
            scaler = torch.cuda.amp.GradScaler()
    else:
        scaler = None

    run_config = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "command": " ".join(sys.argv),
        "arguments": vars(args),
        "device": str(device),
        "package_versions": package_versions(),
        "model_selection": {
            "metric": "validation chunk-level cross-entropy loss",
            "direction": "minimize",
            "tie_break": "validation article-level AUROC",
        },
        "aggregation": "arithmetic mean of chunk softmax P(label=1)",
        "total_optimizer_steps": total_optimizer_steps,
        "warmup_steps": warmup_steps,
    }
    write_json(output_dir / "run_config.json", run_config)

    best_model_dir = output_dir / "best_model"
    best_auroc = -math.inf
    best_validation_loss = math.inf
    best_epoch: int | None = None
    history: list[dict[str, Any]] = []
    global_optimizer_step = 0

    for epoch in range(1, args.epochs + 1):
        train_loss, global_optimizer_step = train_one_epoch(
            model=model,
            data_loader=train_loader,
            optimizer=optimizer,
            scheduler=scheduler,
            device=device,
            gradient_accumulation_steps=args.gradient_accumulation_steps,
            max_grad_norm=args.max_grad_norm,
            use_fp16=args.fp16,
            scaler=scaler,
            epoch=epoch,
            log_every=args.log_every,
            global_optimizer_step=global_optimizer_step,
        )
        validation_chunk_rows, validation_loss = predict_chunks(
            model,
            validation_loader,
            device=device,
            use_fp16=args.fp16,
        )
        validation_article_rows = aggregate_chunk_predictions(validation_chunk_rows)
        epoch_cutoff = choose_threshold(
            validation_article_rows, objective=args.threshold_objective
        )
        validation_metrics = compute_article_metrics(
            validation_article_rows, epoch_cutoff["threshold"]
        )
        validation_auroc = float(validation_metrics["auroc"])
        epoch_record = {
            "epoch": epoch,
            "train_chunk_loss": train_loss,
            "validation_chunk_loss": validation_loss,
            "validation_metrics": validation_metrics,
            "validation_threshold_selection": epoch_cutoff,
        }
        history.append(epoch_record)
        write_json(output_dir / "training_history.json", history)
        print(
            f"epoch={epoch} train_loss={train_loss:.6f} "
            f"validation_loss={validation_loss:.6f} "
            f"article_auroc={validation_auroc:.6f} "
            f"cutoff={epoch_cutoff['threshold']:.8f}",
            flush=True,
        )

        is_better = validation_loss < best_validation_loss - 1e-12 or (
            math.isclose(validation_loss, best_validation_loss, abs_tol=1e-12)
            and validation_auroc > best_auroc
        )
        if is_better:
            best_auroc = validation_auroc
            best_validation_loss = validation_loss
            best_epoch = epoch
            best_model_dir.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(best_model_dir, safe_serialization=True)
            tokenizer.save_pretrained(best_model_dir)
            write_json(
                best_model_dir / "selection.json",
                {
                    "epoch": epoch,
                    "validation_article_auroc": validation_auroc,
                    "validation_chunk_loss": validation_loss,
                },
            )
            print(f"Saved new best model from epoch {epoch}", flush=True)

    if best_epoch is None:
        raise RuntimeError("Training completed without selecting a best checkpoint")

    print(f"Reloading best model from epoch {best_epoch}...", flush=True)
    del model
    if device.type == "cuda":
        torch.cuda.empty_cache()
    model = AutoModelForSequenceClassification.from_pretrained(
        best_model_dir,
        local_files_only=True,
    ).to(device)

    # Select the operating point once, using only the internal validation set.
    validation_chunk_rows, validation_loss = predict_chunks(
        model,
        validation_loader,
        device=device,
        use_fp16=args.fp16,
    )
    validation_article_rows = aggregate_chunk_predictions(validation_chunk_rows)
    threshold_selection = choose_threshold(
        validation_article_rows, objective=args.threshold_objective
    )
    threshold = float(threshold_selection["threshold"])
    validation_metrics = compute_article_metrics(validation_article_rows, threshold)
    validation_output_rows = attach_hard_predictions(validation_article_rows, threshold)

    threshold_payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "threshold": threshold,
        "objective": args.threshold_objective,
        "selection_set": "internal_validation",
        "selection": threshold_selection,
        "best_epoch": best_epoch,
        "best_model_relative_path": "best_model",
        "aggregation": "arithmetic mean of chunk softmax P(label=1)",
        "prediction_rule": "mean_positive_probability >= threshold",
        "validation_chunk_loss": validation_loss,
        "validation_metrics": validation_metrics,
    }
    write_json(output_dir / "threshold.json", threshold_payload)
    write_jsonl(output_dir / "validation_article_predictions.jsonl", validation_output_rows)

    # The internal test set is touched only after model and threshold are frozen.
    test_chunk_rows, test_loss = predict_chunks(
        model,
        test_loader,
        device=device,
        use_fp16=args.fp16,
    )
    test_article_rows = aggregate_chunk_predictions(test_chunk_rows)
    test_metrics = compute_article_metrics(test_article_rows, threshold)
    test_output_rows = attach_hard_predictions(test_article_rows, threshold)
    write_jsonl(output_dir / "internal_test_article_predictions.jsonl", test_output_rows)

    results = {
        "schema_version": SCHEMA_VERSION,
        "best_epoch": best_epoch,
        "threshold": threshold_payload,
        "validation": {
            "chunk_loss": validation_loss,
            "article_metrics": validation_metrics,
        },
        "internal_test": {
            "chunk_loss": test_loss,
            "article_metrics": test_metrics,
        },
        "elapsed_seconds": time.time() - started_at,
    }
    write_json(output_dir / "internal_results.json", results)
    print(
        "Training complete. "
        f"best_epoch={best_epoch}, threshold={threshold:.8f}, "
        f"internal_test_auroc={test_metrics['auroc']:.6f}, "
        f"internal_test_sensitivity={test_metrics['sensitivity_recall']:.6f}, "
        f"internal_test_specificity={test_metrics['specificity']:.6f}",
        flush=True,
    )
    print(f"Artifacts: {output_dir}", flush=True)


if __name__ == "__main__":
    main()
