# Copyright 2026 The offline-docling authors
# SPDX-License-Identifier: Apache-2.0
"""HTTP-прокси поверх docling-serve: обход бага docling-serve#567.

docling-serve (проверено на v1.32.0) игнорирует ocr_engine/ocr_lang и прочие
OCR-опции, переданные полями multipart-формы в /v1/convert/file* — всегда
работает дефолтный RapidOCR с англо-китайской моделью. Рабочий путь —
JSON-эндпоинт /v1/convert/source, там опции применяются.


Этот сервис принимает multipart-запросы в формате API docling-serve,
перекодирует файлы в base64 и проксирует их в /v1/convert/source(async)
с корректными OCR-опциями. Наружу торчит тот же API (file/async + status +
result + health), поэтому клиенты (test_convert.py и т.п.) работают без
изменений — достаточно направить их на порт прокси.


Переменные окружения:
    DOCLING_URL  — базовый URL docling-serve (по умолчанию http://docling:5001)
    OCR_ENGINE   — движок OCR по умолчанию (по умолчанию rapidocr)
    OCR_LANG     — языки через запятую (по умолчанию eslav)
    PROXY_PORT   — порт прослушивания (по умолчанию 5002)


Поля формы ocr_engine/ocr_lang в запросе переопределяют дефолты из env.
"""


import base64
import os


import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route


DOCLING_URL = os.environ.get("DOCLING_URL", "http://docling:5001").rstrip("/")
OCR_ENGINE = os.environ.get("OCR_ENGINE", "rapidocr")
OCR_LANG = [s.strip() for s in os.environ.get("OCR_LANG", "eslav").split(",") if s.strip()]


HTTP_TIMEOUT = httpx.Timeout(1800.0, connect=10.0)




async def _convert(request: Request, docling_path: str) -> Response:
    """multipart /v1/convert/file* -> JSON /v1/convert/source*."""
    form = await request.form()
    sources = []
    for upload in form.getlist("files"):
        content = await upload.read()
        sources.append({
            "kind": "file",
            "base64_string": base64.b64encode(content).decode(),
            "filename": upload.filename,
        })
    if not sources:
        return JSONResponse({"detail": "поле files пустое"}, status_code=422)


    options = {
        "to_formats": form.getlist("to_formats") or ["md"],
        "ocr_engine": form.get("ocr_engine") or OCR_ENGINE,
        "ocr_lang": form.getlist("ocr_lang") or OCR_LANG,
    }
    for flag in ("do_ocr", "force_ocr", "do_table_structure"):
        value = form.get(flag)
        if value is not None:
            options[flag] = value.lower() in ("1", "true", "yes")


    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.post(f"{DOCLING_URL}{docling_path}",
                                 json={"options": options, "sources": sources})
    return Response(resp.content, status_code=resp.status_code,
                    media_type=resp.headers.get("content-type"))




async def convert_file(request: Request) -> Response:
    return await _convert(request, "/v1/convert/source")




async def convert_file_async(request: Request) -> Response:
    return await _convert(request, "/v1/convert/source/async")




async def proxy_get(request: Request) -> Response:
    """Прозрачное проксирование GET-запросов (status/poll, result, health)."""
    path = request.url.path
    if request.url.query:
        path += "?" + request.url.query
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(f"{DOCLING_URL}{path}")
    return Response(resp.content, status_code=resp.status_code,
                    media_type=resp.headers.get("content-type"))




app = Starlette(routes=[
    Route("/v1/convert/file", convert_file, methods=["POST"]),
    Route("/v1/convert/file/async", convert_file_async, methods=["POST"]),
    Route("/{path:path}", proxy_get, methods=["GET"]),
])


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PROXY_PORT", "5002")))
