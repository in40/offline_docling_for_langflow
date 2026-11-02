# Docling offline package

Self-contained Docling document-conversion stack (GPU) for air-gapped deployment.
Built from chat.sorokinonline.com production deployment, 2026-11-02.

## Contents

- `images/*.rootfs.tar.gz` — flattened container filesystems (docker export), scannable as plain tars
- `images/*.config.json` — original image configs (ENV/CMD/USER...) for audit
- `models/docling-models-cache.tar.gz` — all Docling/OCR model weights (layout, tableformer, heron, CodeFormulaV2, figure classifier, EasyOCR ru+en, RapidOCR eslav)
- `src/` — proxy_server.py, mcp_server.py sources + Dockerfiles (reference)
- `load_images.sh` — imports images via `docker import`, extracts cache, starts stack
- `DEPLOY.md` — step-by-step runbook for the new server (start here)
- `docker-compose.offline.yml` — stack definition
- `SHA256SUMS` — integrity

## Security scanning

Each rootfs tar is a plain filesystem tree: `tar tzf serve.rootfs.tar.gz` or extract and scan.
Model cache is plain files (note: EasyOCR `.pth` are pickle-format torch checkpoints).
Verify integrity first: `sha256sum -c SHA256SUMS`.

## Prereqs (target host)

- docker + compose plugin
- NVIDIA driver >= 550 (cu126), nvidia-container-toolkit
- ~25GB disk, 16GB+ RAM, GPU with 8GB+ VRAM (models load per worker, 4 workers)

## Deploy

```
sha256sum -c SHA256SUMS
./load_images.sh
```

## Services / ports

- docling-serve: `5001` — REST API (`/health`, `/v1/convert/*`), OpenAPI at `/docs`
- docling-proxy: `5002` — same API, working ocr_engine/ocr_lang multipart (use this externally)
- docling-mcp: `8000` — MCP streamable-http at `/mcp`

Default OCR: rapidocr / eslav (ru+en). Override per request via `ocr_engine`/`ocr_lang`.

## Smoke test

```
curl -s http://localhost:5001/health
curl -s -F "files=@test.pdf" http://localhost:5002/v1/convert/file/sync \
  -H "accept: application/json" | head -c 300
```

## Notes

- `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1` set — no network fetches attempted
- Models mounted at `/opt/app-root/src/.cache/docling/models` (read-write)
- Original public front (nginx + bearer key + TLS) not included — replicate in secure env if needed
