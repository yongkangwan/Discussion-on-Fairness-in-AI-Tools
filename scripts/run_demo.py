#!/usr/bin/env python3
"""Offline, synthetic-only training/evaluation using the real repository pipeline."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.preprocess_articles import preprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'runs/demo')
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('Use a new or empty output directory')
    out.mkdir(parents=True, exist_ok=True)
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    import torch
    import transformers
    from transformers import BertConfig, BertForSequenceClassification, BertTokenizerFast
    torch.manual_seed(42)
    torch.set_num_threads(1)
    model_dir = out / 'tiny_bert'
    model_dir.mkdir()
    vocab = ROOT / 'data/examples/vocab.txt'
    keyword = 'vocab' if int(transformers.__version__.split('.')[0]) >= 5 else 'vocab_file'
    tokenizer = BertTokenizerFast(**{keyword: str(vocab)}, do_lower_case=True)
    tokenizer.save_pretrained(model_dir)
    config = BertConfig(vocab_size=len(tokenizer), hidden_size=8,
                        num_hidden_layers=1, num_attention_heads=2, intermediate_size=16,
                        hidden_dropout_prob=0.0, attention_probs_dropout_prob=0.0,
                        max_position_embeddings=32, pad_token_id=0, num_labels=2)
    BertForSequenceClassification(config).save_pretrained(model_dir)
    manifests = {}
    for name in ('demo_positive', 'demo_negative', 'demo_external_positive', 'demo_external_negative'):
        manifests[name] = preprocess(ROOT / f'data/examples/{name}.jsonl', out / f'{name}.jsonl',
                                     model_dir, 32, 4, 'demo-only')
    env = dict(os.environ, OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    def run(script, arguments):
        subprocess.run([sys.executable, str(ROOT / script), *map(str, arguments)],
                       cwd=ROOT, env=env, check=True)
    run('train.py', ['--positive-files', out / 'demo_positive.jsonl',
        '--negative-files', out / 'demo_negative.jsonl', '--model-name', model_dir,
        '--local-files-only', '--output-dir', out / 'training', '--epochs', '1',
        '--max-length', '32', '--train-batch-size', '4', '--eval-batch-size', '4',
        '--num-workers', '0', '--log-every', '0', '--device', 'cpu'])
    run('evaluate.py', ['--model-dir', out / 'training/best_model',
        '--positive-files', out / 'demo_external_positive.jsonl',
        '--negative-files', out / 'demo_external_negative.jsonl',
        '--output-dir', out / 'external', '--max-length', '32', '--batch-size', '4',
        '--device', 'cpu', '--save-chunk-predictions'])
    result = json.loads((out / 'external/external_results.json').read_text())
    summary = dict(data_status='demo-only', paper_results_reproduced=False,
                   model='randomly initialized tiny BERT, one epoch; not a useful detector',
                   preprocessing=manifests, external_metrics=result['article_metrics'])
    (out / 'DEMO_SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(f'DEMO-ONLY complete: {out / "DEMO_SUMMARY.json"}')


if __name__ == '__main__':
    main()
