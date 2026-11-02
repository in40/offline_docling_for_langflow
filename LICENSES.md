# Component licenses — docling offline package

Audit date: 2026-11-02. Method: `pip-licenses` inside each container (441 pkgs in serve),
HuggingFace model cards, base image inspection. Full machine-readable dumps: `licenses/*.csv`.

## Application stack

- docling, docling-serve, docling-core, docling-parse, docling-ibm-models, docling-mcp — **Apache-2.0** (Docling project / IBM)
- proxy_server.py, mcp_server.py — own code, no third-party deps beyond listed below
- Base images: CentOS Stream 9 (UBI-family, freely redistributable), Debian 13 trixie (mixed OSS), CPython 3.12 (PSF)

## Python dependencies (serve image, 441 packages)

Distribution: MIT ~170, Apache-2.0 ~108, BSD-2/3 ~92, PSF-2.0, ISC, MPL-2.0 (few), Unlicense.

Notable exceptions:

- **NVIDIA proprietary (30 pkgs)**: nvidia-cublas/cudnn/cuda-runtime/cusolver/cufft/curand/cusparse/nvrtc/cupti/cufile/nccl/cusparselt/nvtx/torch-cu12 etc. — NVIDIA Software License Agreement; runtime libraries are explicitly **redistributable** with applications. No source-disclosure obligation.
- **python-bidi — LGPL-3.0** (EasyOCR dependency). Used as ordinary imported library; no linking/modification obligations triggered for internal deployment.
- **google-crc32c** — metadata says UNKNOWN, actual license Apache-2.0.
- No AGPL, no GPL-copyleft code in the stack.

## Model weights

- docling-project/docling-models (layout + tableformer) — **CDLA-Permissive-2.0 / Apache-2.0**
- docling-project/docling-layout-heron — **Apache-2.0**
- docling-project/DocumentFigureClassifier-v2.0 — **Apache-2.0**
- docling-project/CodeFormulaV2 — **CDLA-Permissive-2.0**
- EasyOCR models (craft_mlt_25k, english_g2, latin_g2, cyrillic_g2) — **Apache-2.0** (JaidedAI/EasyOCR)
- RapidOCR PP-OCRv4/v5 eslav onnx — **Apache-2.0** (RapidAI/RapidOCR, derived from PaddleOCR Apache-2.0)
- Tesseract rus langpack — **Apache-2.0**

CDLA-Permissive-2.0 is a permissive data license: internal use and redistribution allowed with attribution conditions satisfied by this notice.

## Not included / target-side obligations

- **NVIDIA GPU driver** — proprietary, must be installed on target (>= 550 for cu126) from NVIDIA; not part of this package.
- Docker engine (Apache-2.0 / Moby) — target-side install.

## Bottom line

All components are permissive-licensed (Apache-2.0/MIT/BSD) or redistributable proprietary runtime (NVIDIA CUDA libs). One LGPL-3.0 library (python-bidi) used as-is. No copyleft propagation, no source-disclosure obligations for internal secure-environment deployment. Keep this file + `licenses/` with the package for the compliance record.
