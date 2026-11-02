# Copyright 2026 The offline-docling authors
# SPDX-License-Identifier: Apache-2.0
"""MCP-сервер поверх docling-serve: конвертация документов как MCP-инструменты.

Транспорт: streamable-http (агенты подключаются по сети к http://<host>:8000/mcp).
Тяжёлая работа (парсинг, OCR, модели) остаётся в контейнере docling-serve —
этот сервер лишь проксирует вызовы в его HTTP API.


Переменные окружения:
    DOCLING_URL           — базовый URL docling-serve (по умолчанию http://docling:5001)
    MCP_HOST / MCP_PORT   — адрес прослушивания (по умолчанию 0.0.0.0:8000)
    DOCLING_POLL_TIMEOUT  — таймаут ожидания конвертации, сек (по умолчанию 1800)
    OCR_ENGINE / OCR_LANG — движок и языки OCR (по умолчанию rapidocr / eslav)
    MCP_MAX_BODY_MB       — макс. размер тела запроса, МБ (по умолчанию 64;
                            в SDK mcp дефолт 4 МБ — большие PDF в base64
                            отклоняются с HTTP 413)


Примечание: используется JSON-эндпоинт /v1/convert/source/async, т.к.
multipart /v1/convert/file/async игнорирует OCR-опции (баг docling-serve#567).
"""


import base64
import binascii
import os
import time


import httpx
from mcp.server.fastmcp import FastMCP


DOCLING_URL = os.environ.get("DOCLING_URL", "http://docling:5001").rstrip("/")
POLL_TIMEOUT = int(os.environ.get("DOCLING_POLL_TIMEOUT", "1800"))
OCR_ENGINE = os.environ.get("OCR_ENGINE", "rapidocr")
OCR_LANG = [s.strip() for s in os.environ.get("OCR_LANG", "eslav").split(",") if s.strip()]
MAX_BODY = int(os.environ.get("MCP_MAX_BODY_MB", "64")) * 1024 * 1024


OPTIONS = {
    "to_formats": ["md"],
    "ocr_engine": OCR_ENGINE,
    "ocr_lang": OCR_LANG,
}


mcp = FastMCP(
    "docling",
    host=os.environ.get("MCP_HOST", "0.0.0.0"),
    port=int(os.environ.get("MCP_PORT", "8000")),
    max_request_body_size=MAX_BODY,
)




def _wait_result(client: httpx.Client, task_id: str) -> str:
    """Опрашивает docling-serve до завершения задачи и возвращает markdown."""
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        status = client.get(f"{DOCLING_URL}/v1/status/poll/{task_id}?wait=60").json()
        task_status = status["task_status"]
        if task_status == "success":
            result = client.get(f"{DOCLING_URL}/v1/result/{task_id}").json()
            return result["document"]["md_content"]
        if task_status == "failure":
            raise RuntimeError(f"Конвертация завершилась с ошибкой: {status}")
    raise TimeoutError(f"Конвертация не завершилась за {POLL_TIMEOUT} сек (task_id={task_id})")




@mcp.tool()
def convert_document_url(url: str) -> str:
    """Конвертировать документ (PDF, DOCX, HTML и др.) по публичному URL в markdown."""
    with httpx.Client(timeout=httpx.Timeout(70.0, connect=10.0)) as client:
        task = client.post(
            f"{DOCLING_URL}/v1/convert/source/async",
            json={"sources": [{"kind": "http", "url": url}], "options": OPTIONS},
        )
        task.raise_for_status()
        return _wait_result(client, task.json()["task_id"])




@mcp.tool()
def convert_document_base64(filename: str, content_base64: str) -> str:
    """Конвертировать документ в markdown. Содержимое передаётся в base64,
    filename нужен для определения формата (report.pdf, letter.docx, page.html...)."""
    try:
        content = base64.b64decode(content_base64, validate=True)
    except binascii.Error as exc:
        raise ValueError(f"content_base64 не является валидным base64: {exc}") from exc
    with httpx.Client(timeout=httpx.Timeout(70.0, connect=10.0)) as client:
        task = client.post(
            f"{DOCLING_URL}/v1/convert/source/async",
            json={
                "sources": [{
                    "kind": "file",
                    "base64_string": base64.b64encode(content).decode(),
                    "filename": filename,
                }],
                "options": OPTIONS,
            },
        )
        task.raise_for_status()
        return _wait_result(client, task.json()["task_id"])




@mcp.tool()
def docling_health() -> str:
    """Проверить доступность docling-serve (health check)."""
    with httpx.Client(timeout=10.0) as client:
        return client.get(f"{DOCLING_URL}/health").text




if __name__ == "__main__":
    import uvicorn
    import starlette.requests
    original_limit = getattr(starlette.requests.Request, "HEADER_LIMIT", None)
    starlette.requests.Request.HEADER_LIMIT = MAX_BODY
    print(f"HEADER_LIMIT: {original_limit} -> {MAX_BODY} ({MAX_BODY // 1024 // 1024} MB)")
    mcp.run(transport="streamable-http")
