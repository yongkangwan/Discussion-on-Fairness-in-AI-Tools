# BERT 论文工厂文章筛查复现

这套代码直接读取现有 JSONL 中预先切好的 BERT token，在 chunk 层面微调
`bert-base-uncased`，再把同一 PMID 的所有 chunk 的阳性概率做算术平均，得到文章级
概率。阳性标签固定为 `1`，阴性标签固定为 `0`。

## 实现约定

- 内部阳性：`positive_chunks.jsonl`。
- 内部阴性：`top_china.jsonl`、`top_other_train.jsonl`、`top_taiwan.jsonl`。
- 先按 `(pmid, chunk_index)` 去重，再按 PMID 分层划分 70%/17.5%/12.5%；同一篇文章的
  chunk 不会跨集合。
- BERT 输入最长 512 token；代码不静默截断超过 512 的预切分 chunk，而是直接报错。
- 每个 chunk 继承文章标签，训练损失在 chunk 层面计算。
- 文章分数为 `mean(softmax(logits)[:, 1])`，不是硬分类均值，也不是 logits 均值。
- 每轮模型用内部验证集 chunk-level evaluation loss 选择最佳 checkpoint，文章级 AUROC
  作为同分规则。最佳模型确定后，仅在内部
  验证集选择一次阈值，随后冻结阈值评估内部测试集和所有外部数据。
- 阈值目标默认是 Youden 指数；也可切换为 F1 或 balanced accuracy。同分时依次优先
  specificity、sensitivity 和较高阈值。

加载器按文件在命令行中的角色强制覆盖标签，而不信任行内旧标签。这一点很重要：
`positive_chunks_dedup_pubpeer.jsonl` 的现有行内 `label` 全部是 `0`，但作为
`--positive-files` 传入后会全部按阳性 `1` 评估。

## 安装

建议使用带 CUDA 的 PyTorch 环境；当前数据规模下，CPU 完整训练会非常慢。

```powershell
python -m pip install -r requirements.txt
```

首次运行时会从 Hugging Face 下载 `bert-base-uncased` 权重。若权重已在本地缓存，可加
`--local-files-only`。现有 JSONL 已经使用 `bert-base-uncased` 的词表编码，代码不会
重新分词。

## 训练与内部测试

在本目录运行：

```powershell
python train.py `
  --positive-files positive_chunks.jsonl `
  --negative-files top_china.jsonl top_other_train.jsonl top_taiwan.jsonl `
  --model-name bert-base-uncased `
  --output-dir runs/paper_mill_bert_seed42 `
  --seed 42 `
  --train-ratio 0.7 `
  --validation-ratio 0.175 `
  --test-ratio 0.125 `
  --epochs 10 `
  --learning-rate 1.4e-5 `
  --weight-decay 0.025 `
  --warmup-ratio 0.15 `
  --scheduler-type cosine `
  --train-batch-size 32 `
  --eval-batch-size 32 `
  --gradient-accumulation-steps 1 `
  --threshold-objective youden `
  --fp16
```

没有 CUDA 时删去 `--fp16`。每个输出目录必须为空，以免不同实验的文件混在一起。

主要产物：

- `split_manifest.json`：文章级划分、数据 SHA-256、去重及标签覆盖统计。
- `best_model/`：验证集文章级 AUROC 最优的模型与 tokenizer。
- `threshold.json`：只由内部验证集确定的冻结阈值和选择准则。
- `validation_article_predictions.jsonl`：验证集文章级概率和分类。
- `internal_test_article_predictions.jsonl`：内部测试集文章级概率和分类。
- `internal_results.json`：验证集和内部测试集的文章级指标。
- `training_history.json`：各轮损失、文章级指标和当轮验证阈值。

## 外部测试

只评估已明确的外部阳性集：

```powershell
python test.py `
  --model-dir runs/paper_mill_bert_seed42/best_model `
  --threshold-file runs/paper_mill_bert_seed42/threshold.json `
  --positive-files positive_chunks_dedup_pubpeer.jsonl `
  --output-dir runs/paper_mill_bert_seed42/external_positive
```

只有阳性时只能估计 sensitivity/recall、TP、FN 和概率分布，不能估计 specificity 或
AUROC。因此结果文件会将不适用的指标写为 `null`。

目录中的 `top_other_prove.jsonl` 看起来像候选外部阴性集，但本次需求没有明确确认其
角色，所以代码不会静默使用它。确认它确实是外部阴性后，可运行完整外部评估：

```powershell
python test.py `
  --model-dir runs/paper_mill_bert_seed42/best_model `
  --threshold-file runs/paper_mill_bert_seed42/threshold.json `
  --positive-files positive_chunks_dedup_pubpeer.jsonl `
  --negative-files top_other_prove.jsonl `
  --output-dir runs/paper_mill_bert_seed42/external_full
```

测试脚本默认读取训练目录中的 `split_manifest.json` 并检查 PMID 泄漏；检测到重叠会
直接停止。输出为 `external_article_predictions.jsonl` 和 `external_results.json`。

## 与 BMJ 原文的差异

当前默认采用 [BMJ 原文](https://www.bmj.com/content/392/bmj-2025-087581)报告的
70% 训练、17.5% 优化、12.5% 内部验证比例。为保持本项目数据的既有 chunk 边界，代码
仍按 chunk（而非原文的句子）输入并平均 chunk 概率。阈值选择目标在原需求中未指定，故
做成显式参数并将实际选择完整写入 `threshold.json`。
