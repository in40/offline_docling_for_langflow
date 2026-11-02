# Deployment runbook — new server

Target: air-gapped host with NVIDIA GPU. Package dir: `offline-docling/` (referred to as `$PKG`).

## 0. Prerequisites check

```bash
docker --version                      # >= 20.10
docker compose version                # v2 plugin
nvidia-smi                            # driver >= 550 (cu126 runtime)
docker info | grep -i nvidia          # nvidia runtime registered
df -h /var/lib/docker                 # >= 25 GB free
free -g                               # >= 16 GB RAM
```

If `nvidia` runtime missing: install `nvidia-container-toolkit`, then
`nvidia-ctk runtime configure --runtime=docker && systemctl restart docker`.

## 1. Verify integrity

```bash
cd $PKG
sha256sum -c SHA256SUMS
```

All lines must say `OK`. If your security process scans files first, do it now:
rootfs tars and the model cache are plain gzipped tars — extract and scan freely.

## 2. Load images + models + start stack

```bash
./load_images.sh
```

Takes ~5-10 min (imports 3 rootfs images, extracts model cache, `docker compose up -d`).
Idempotent — safe to re-run.

## 3. Verify

```bash
# health (allow ~2 min for first start)
curl -s http://localhost:5001/health

# models present inside serve container
docker exec docling-serve-offline ls /opt/app-root/src/.cache/docling/models

# all containers healthy/up
docker compose -f docker-compose.offline.yml ps
```

Expected models dir: `docling-project--docling-models`, `docling-project--docling-layout-heron`,
`docling-project--CodeFormulaV2`, `docling-project--DocumentFigureClassifier-v2.0`, `EasyOcr`, `RapidOcr`.

## 4. Smoke test (real conversion)

```bash
# create a tiny test PDF
python3 - <<'EOF'
# minimal one-page PDF
pdf = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj
4 0 obj<</Length 44>>stream
BT /F1 24 Tf 72 720 Td (Hello offline) Tj ET
endstream
endobj
trailer<</Root 1 0 R>>
%%EOF"""
open("/tmp/test.pdf","wb").write(pdf)
EOF

# convert via proxy (recommended external API)
curl -s -F "files=@/tmp/test.pdf" \
  "http://localhost:5002/v1/convert/file/sync" \
  -H "accept: application/json" | head -c 400
```

JSON with `status: "success"` = stack is working.

## 5. Endpoints

- **docling-proxy :5002** — use this externally; `/v1/convert/file/sync`, `/v1/convert/file/async`; multipart with working `ocr_engine`/`ocr_lang`
- **docling-serve :5001** — raw API + `/docs` OpenUI; multipart has OCR-options bug #567, prefer proxy
- **docling-mcp :8000** — MCP streamable-http at `http://<host>:8000/mcp`

OCR defaults: `rapidocr` / `eslav` (ru+en). Per-request override (proxy):
`-F "ocr_engine=easyocr" -F "ocr_lang=ru" -F "ocr_lang=en"`.
Available engines: `rapidocr`, `easyocr`, `tesseract` (rus langpack baked in).

## 6. Exposing externally (replicate old front)

Old setup: nginx + TLS + bearer key in front of the proxy. Minimal equivalent:

```nginx
location /docling/ {
    auth_request /_docling_auth;
    proxy_pass http://127.0.0.1:5002/;
    proxy_read_timeout 600s;
    client_max_body_size 100m;
}
location = /_docling_auth {
    internal;
    if ($http_authorization = "Bearer <NEW-SECRET>") { return 204; }
    return 401;
}
```

Generate a fresh secret — do not reuse the old key.

## 7. Troubleshooting

- **`CUDA out of memory`** — lower workers: set `DOCLING_SERVE_ENG_LOC_NUM_WORKERS: "2"` (each worker ≈1-2 GB VRAM), `docker compose ... up -d` again.
- **`Bus error` during conversion** — `shm_size` too small; keep `8g` or raise.
- **Container tries to reach internet / HF timeouts** — check `HF_HUB_OFFLINE=1` env survived import: `docker exec docling-serve-offline printenv | grep OFFLINE`; model mount exists at `/opt/app-root/src/.cache/docling/models`.
- **Permission denied on models** — `chown -R 1001:0 $PKG/models/models` (container runs as uid 1001).
- **`import` fails on old docker** — needs docker >= 20.10 for gzipped `docker import`.
- **Slow first request** — models load lazily per worker on first conversion (`LOAD_MODELS_AT_BOOT=false`); warm up with the smoke test.

## 8. Ops

```bash
cd $PKG
docker compose -f docker-compose.offline.yml logs -f docling-serve   # logs
docker compose -f docker-compose.offline.yml restart                 # restart
docker compose -f docker-compose.offline.yml down                    # stop
```

Data: stack is stateless — only inputs/outputs, no persistent state to back up.
