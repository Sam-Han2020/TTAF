# TTAF

**EMNLP 2026 Findings**

Code release for **Leveraging Teacher-Forcing Token-Level Anomaly Signals for Heterogeneous Backdoor Filtering in LLMs**.

## Overview

![TTAF framework](./assets/method.jpg)

TTAF (Teacher-Forcing Token-Level Anomaly Filtering) detects suspicious instruction-tuning samples before fine-tuning. It scores localized target-token anomalies under teacher forcing, smooths the token-level signal, and aggregates the strongest local evidence into a sample-level filtering score.

This repository provides the paper-facing TTAF detection and filtering workflow for the supported attacks on four question-answering datasets used in the paper.



## Environment

- Python 3.10
- A CUDA-capable GPU
- Access to `meta-llama/Llama-2-7b-chat-hf` or equivalent local weights

```bash
conda create -n ttaf python=3.10
conda activate ttaf
pip install -r requirements.txt
```

If the model is gated, request access on Hugging Face and log in before running the code.



## Running

Run the following command from the repository root:

```bash
python casualDefense.py \
  [--config_path ./genConfigs/TTAF.json] \
  [--dataset webqa/freebaseqa/nq/coqa] \
  [--poisoner word/stylebkd/cba_instruction/cba_context/iba/ptrojan] \
  [--attack_mode append/internal/prefix/rewrite] \
  [--poison_rate FLOAT] \
  [--seed INTEGER] \
  [--detect_only]
```

Example:

```bash
python casualDefense.py \
  --config_path ./genConfigs/TTAF.json \
  --dataset webqa \
  --poisoner word \
  --attack_mode append \
  --poison_rate 0.10 \
  --seed 42 \
  --detect_only
```



## Outputs

Detection-only results:

```text
outputResults/detect_only/<run-name>/
├── detectOutput.json
├── detectSummary.json
└── time.json
```

Full-run results:

```text
outputResults/full/<run-name>/
├── summary.json
├── summary.txt
├── testOutput.json
└── time.json
```

TTAF feature artifacts:

```text
ttaf/<dataset>/<poisoner>/<timestamp>/ttaf_features.pkl
```

Generated model weights, poisoned-data caches, result files, and feature
artifacts are excluded by `.gitignore`.



## Acknowledgement

This work builds on the following repositories:

- OpenBackdoor: https://github.com/thunlp/OpenBackdoor
- GraCeFul: https://github.com/ZrW00/GraceFul