# GPU setup and validation

The full BERT training/evaluation workflow passed on a single **RTX 4090 D
(24 GB)** on 2026-10-04, using CUDA FP16, 512-token inputs and batch size 32.
The standard CPU tests also passed: **16 tests in 6.00 seconds**. PMID integrity
checks and `pip check` passed in the same environment.

## Tested environment

| Component | Version |
|---|---|
| System | AutoDL, Ubuntu 22.04.5 LTS, x86_64 |
| GPU / driver | NVIDIA GeForce RTX 4090 D / 595.71.05 |
| Python | 3.12.3 |
| PyTorch / CUDA runtime | 2.8.0+cu128 / 12.8 |
| Transformers | 4.57.6 |
| NumPy / scikit-learn | 2.3.2 / 1.7.2 |
| safetensors | 0.6.2 |
| tokenizers / huggingface-hub | 0.22.2 / 0.36.2 |

The machine already had Python and CUDA-enabled PyTorch installed. From a login
terminal with that Python active, run these commands in the repository root:

```bash
python -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install -r requirements-gpu-tested.txt
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

`--system-site-packages` reuses the image's PyTorch installation. The tested
requirements pin the listed application dependencies; they are not a complete
lock of the AutoDL image. On another machine, install an appropriate CUDA-enabled
PyTorch build first. A separate CUDA toolkit installation was not needed for this
test.

## Download the model once

The check uses the pretrained `google-bert/bert-base-uncased` encoder with a new
two-class classification head: 12 layers, hidden size 768, 12 attention heads,
and **109,483,778 trainable parameters**. The model source is pinned to
[revision 86b5e0934494bd15c9632b12f734a8a67f723594](https://huggingface.co/google-bert/bert-base-uncased/tree/86b5e0934494bd15c9632b12f734a8a67f723594).

```bash
HF_HUB_DISABLE_XET=1 HF_HUB_DOWNLOAD_TIMEOUT=60 python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
    "google-bert/bert-base-uncased",
    revision="86b5e0934494bd15c9632b12f734a8a67f723594",
    local_dir="cache/bert-base-uncased",
    allow_patterns=["config.json", "model.safetensors", "tokenizer.json",
                    "tokenizer_config.json", "vocab.txt", "LICENSE"],
    max_workers=2,
)
PY
```

Direct access to Hugging Face failed on the tested machine. Enabling AutoDL's
preinstalled network acceleration with `source /etc/network_turbo` allowed the
download from the official Hub. This is only needed where that AutoDL helper
exists and direct access fails. After downloading, the validation runs offline.

## Run the GPU check

```bash
python scripts/run_gpu_validation.py \
  --model-dir cache/bert-base-uncased \
  --output-dir runs/gpu-validation
```

Use a fresh output directory for another run. The script creates 64 internal and
16 disjoint external synthetic articles describing fictional colored objects.
Each article produces a 512-token chunk and a 188-token tail using the explicit
preprocessing recipe with 32 content tokens of overlap. The internal split is
44 training / 11 validation / 9 test articles. Both classes are represented in
each partition. These are **demo-only functional inputs**, not paper data.

The script runs the existing `train.py` for two epochs and then starts a separate
`evaluate.py` process. It checks actual CUDA FP16 forward calls, full-model
training, batch shape `(32, 512)`, finite losses, updated and reloaded classifier
weights, threshold selection from the saved internal-validation predictions,
reuse of that threshold on disjoint external articles, and article-level means
of chunk probabilities. The original training/evaluation code is unchanged.

## Measured results

| Stage | Process wall time | Peak allocated GPU memory | Peak reserved GPU memory |
|---|---:|---:|---:|
| Training, selection, reload and internal evaluation | 11.27 s | 7.84 GiB | 8.11 GiB |
| Separate external evaluation | 8.12 s | 0.98 GiB | 1.17 GiB |

The complete check took **21.84 seconds**, including preprocessing, subprocess
startup and verification, excluding dependency installation and model download.
Stage wall times include Python/library startup. The report also records narrower
in-process timings separately. Memory values are each subprocess's PyTorch CUDA
allocator peaks; reserved includes allocator caching. They exclude non-PyTorch
CUDA allocations and are not total `nvidia-smi` board usage.

See the [machine-readable report](validation/rtx4090d-2026-10-04.json) for exact
measurements, input/model/code hashes and observed batch shapes. Each new run
writes `GPU_VALIDATION.json`, stage logs, resource reports, model weights,
threshold and predictions under its output directory. The measured times apply
to this small functional check, not a complete paper-scale training run, and
can vary between runs. No research-quality detector or paper metric is claimed.
