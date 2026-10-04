#!/usr/bin/env python3
"""Full BERT-base CUDA/FP16 functional check with synthetic long articles."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import functools
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import runpy
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def read_json(path):
    return json.loads(path.read_text())


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2) + '\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def measured_stage(metrics_path, script, arguments):
    """Measure in the process that owns the CUDA allocations, without editing training."""
    import torch
    from transformers import BertForSequenceClassification
    torch.set_num_threads(4)
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    observations = Counter()
    shapes = set()
    weights = []
    original = BertForSequenceClassification.forward

    @functools.wraps(original)
    def observed(self, *args, **kwargs):
        ids = kwargs.get('input_ids')
        if ids is None and args:
            ids = args[0]
        require(ids is not None and ids.is_cuda, 'BERT forward must execute on CUDA')
        require(torch.is_autocast_enabled('cuda'), 'CUDA autocast must be active')
        require(torch.get_autocast_dtype('cuda') == torch.float16, 'Expected FP16 autocast')
        shapes.add(tuple(ids.shape))
        observations['cuda_fp16_forward_calls'] += 1
        if self.training and torch.is_grad_enabled():
            observations['training_forward_calls'] += 1
            if ids.shape[1] == 512:
                observations['training_512_token_batches'] += 1
        observations['parameters'] = sum(p.numel() for p in self.parameters())
        observations['trainable_parameters'] = sum(p.numel() for p in self.parameters() if p.requires_grad)
        # First and last forward include the initial and reloaded selected classifier.
        weights.append(hashlib.sha256(self.classifier.weight.detach().float().cpu().numpy().tobytes()).hexdigest())
        return original(self, *args, **kwargs)

    BertForSequenceClassification.forward = observed
    started = time.perf_counter()
    status = 'failed'
    try:
        sys.argv = [str(ROOT / script), *arguments]
        runpy.run_path(str(ROOT / script), run_name='__main__')
        status = 'passed'
    finally:
        torch.cuda.synchronize()
        write_json(Path(metrics_path), dict(
            status=status, elapsed_seconds=time.perf_counter() - started,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(),
            peak_reserved_bytes=torch.cuda.max_memory_reserved(),
            observations=dict(observations), input_shapes=sorted(shapes),
            first_classifier_sha256=weights[0] if weights else None,
            last_classifier_sha256=weights[-1] if weights else None,
        ))
        BertForSequenceClassification.forward = original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, required=True,
                        help='Local pretrained bert-base-uncased snapshot (weights and tokenizer).')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'runs/gpu-validation')
    parser.add_argument('--batch-size', type=int, default=32)
    args = parser.parse_args()
    require(args.batch_size > 0, 'Batch size must be positive')
    model_dir = args.model_dir.resolve(strict=True)
    out = args.output_dir.resolve()
    require(not out.exists() or not any(out.iterdir()), 'Use a new or empty output directory')
    out.mkdir(parents=True, exist_ok=True)
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    os.environ['OMP_NUM_THREADS'] = '4'
    os.environ['MKL_NUM_THREADS'] = '4'
    import torch
    from transformers import AutoConfig
    from scripts.preprocess_articles import preprocess
    from paper_mill_common import choose_threshold
    require(torch.cuda.is_available(), 'A CUDA GPU is required')
    config = AutoConfig.from_pretrained(model_dir, local_files_only=True)
    require((config.model_type, config.num_hidden_layers, config.hidden_size,
             config.num_attention_heads, config.intermediate_size, config.vocab_size,
             config.max_position_embeddings) == ('bert', 12, 768, 12, 3072, 30522, 512),
            'Expected the full bert-base-uncased architecture')
    started = time.perf_counter()
    prepared = {}
    for cohort, count in [('internal', 32), ('external', 8)]:
        for label, color in [(0, 'blue'), (1, 'red')]:
            name = f'{cohort}_{label}'
            raw = out / f'{name}_articles.jsonl'
            rows = [dict(pmid=f'DEMO-GPU-{cohort}-{label}-{i:03d}', label=label,
                         data_status='demo-only', title=f'Synthetic {color} objects {i}',
                         abstract=(f'This fictional exercise describes {color} objects in a controlled room. ' * 60))
                    for i in range(count)]
            raw.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            chunks = out / f'{name}.jsonl'
            manifest = preprocess(raw, chunks, model_dir, 512, 32, 'demo-only')
            encoded = read_rows(chunks)
            lengths = [len(row['input_ids']) for row in encoded]
            require(max(lengths) == 512 and min(lengths) < 512, 'Need full and short-tail chunks')
            require(min(Counter(row['pmid'] for row in encoded).values()) >= 2,
                    'Every validation article must exercise multi-chunk aggregation')
            prepared[name] = dict(articles=manifest['articles'], chunks=manifest['chunks'],
                                  chunk_lengths=sorted(set(lengths)), sha256=digest(chunks))

    def run(stage, script, arguments):
        command = [sys.executable, str(Path(__file__).resolve()), '--stage',
                   str(out / f'{stage}_resources.json'), script, *map(str, arguments)]
        wall = time.perf_counter()
        with (out / f'{stage}.log').open('w') as log:
            subprocess.run(command, cwd=ROOT, env=os.environ.copy(), stdout=log,
                           stderr=subprocess.STDOUT, check=True)
        wall_seconds = time.perf_counter() - wall
        resources = read_json(out / f'{stage}_resources.json')
        resources['process_wall_seconds'] = wall_seconds
        write_json(out / f'{stage}_resources.json', resources)
        print(f'{stage} passed ({wall_seconds:.1f}s including process startup)', flush=True)

    run('training', 'train.py', ['--positive-files', out / 'internal_1.jsonl',
        '--negative-files', out / 'internal_0.jsonl', '--model-name', model_dir,
        '--local-files-only', '--output-dir', out / 'training', '--epochs', '2',
        '--max-length', '512', '--train-batch-size', args.batch_size,
        '--eval-batch-size', args.batch_size, '--device', 'cuda', '--fp16', '--log-every', '1'])
    cutoff_file = out / 'training/threshold.json'
    cutoff_hash = digest(cutoff_file)
    run('external', 'evaluate.py', ['--model-dir', out / 'training/best_model',
        '--threshold-file', cutoff_file, '--positive-files', out / 'external_1.jsonl',
        '--negative-files', out / 'external_0.jsonl', '--output-dir', out / 'external',
        '--max-length', '512', '--batch-size', args.batch_size, '--device', 'cuda',
        '--fp16', '--save-chunk-predictions'])

    cutoff = read_json(cutoff_file)
    split = read_json(out / 'training/split_manifest.json')
    history = read_json(out / 'training/training_history.json')
    validation = read_rows(out / 'training/validation_article_predictions.jsonl')
    external = read_json(out / 'external/external_results.json')
    training_resources = read_json(out / 'training_resources.json')
    external_resources = read_json(out / 'external_resources.json')
    require(all(math.isfinite(r[k]) for r in history
                for k in ('train_chunk_loss', 'validation_chunk_loss')), 'Non-finite loss')
    require(cutoff['selection_set'] == 'internal_validation', 'Wrong threshold selection set')
    require({r['pmid'] for r in validation} ==
            {r['pmid'] for r in split['articles'] if r['split'] == 'validation'},
            'Validation predictions must match the saved split')
    require(choose_threshold(validation, objective=cutoff['objective'])['threshold'] == cutoff['threshold'],
            'Saved cutoff does not match internal-validation selection')
    require(digest(cutoff_file) == cutoff_hash and external['threshold'] == cutoff['threshold'],
            'External evaluation must reuse the frozen cutoff')
    require(external['run_id'] == cutoff['run_id'] and not external['training_overlap_pmids'],
            'Run identity or external overlap check failed')
    require(external['article_metrics']['n_articles'] == 16, 'Expected 16 external articles')
    grouped = defaultdict(list)
    for row in read_rows(out / 'external/external_chunk_predictions.jsonl'):
        grouped[row['pmid']].append(row['positive_probability'])
    for row in read_rows(out / 'external/external_article_predictions.jsonl'):
        values = grouped[row['pmid']]
        require(len(values) >= 2 and math.isclose(sum(values) / len(values),
                row['mean_positive_probability'], abs_tol=1e-7), 'Article aggregation mismatch')
        require(row['prediction'] == int(row['mean_positive_probability'] >= cutoff['threshold']),
                'External decision does not use the frozen cutoff')
    obs = training_resources['observations']
    require(obs['trainable_parameters'] > 100_000_000 and obs['training_512_token_batches'] > 0,
            'Full BERT training at 512 tokens was not observed')
    require([args.batch_size, 512] in training_resources['input_shapes'], 'Requested batch shape not exercised')
    require(training_resources['first_classifier_sha256'] != training_resources['last_classifier_sha256'],
            'Reloaded classifier weights did not change during training')
    summary = dict(
        status='passed', data_status='demo-only', paper_results_reproduced=False,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        python=platform.python_version(), os=platform.platform(), gpu=torch.cuda.get_device_name(0),
        gpu_total_bytes=torch.cuda.get_device_properties(0).total_memory, cuda_runtime=torch.version.cuda,
        versions={name: importlib.metadata.version(name) for name in
                  ('torch', 'transformers', 'numpy', 'scikit-learn', 'safetensors', 'tokenizers', 'huggingface-hub')},
        model_files={p.name: digest(p) for p in sorted(model_dir.iterdir()) if p.is_file()},
        source_files={name: digest(ROOT / name) for name in
                      ('train.py', 'evaluate.py', 'paper_mill_common.py',
                       'scripts/preprocess_articles.py', 'scripts/run_gpu_validation.py')},
        configuration=dict(epochs=2, batch_size=args.batch_size, max_length=512, overlap=32, fp16=True),
        inputs=prepared, split_summary=split['summary'], training=training_resources,
        external=external_resources, total_elapsed_seconds=time.perf_counter() - started,
        checks=['CUDA FP16 forwards', 'full BERT trainable', '512-token batch', 'finite losses',
                'updated weights reloaded', 'validation-derived cutoff', 'frozen external cutoff',
                'disjoint external articles', 'chunk means and hard predictions'],
        memory_note='Per-process PyTorch allocator peaks, not total board memory; timing excludes model download and installation.',
    )
    write_json(out / 'GPU_VALIDATION.json', summary)
    print(f'GPU functional validation passed: {out / "GPU_VALIDATION.json"}', flush=True)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--stage':
        measured_stage(sys.argv[2], sys.argv[3], sys.argv[4:])
    else:
        main()
