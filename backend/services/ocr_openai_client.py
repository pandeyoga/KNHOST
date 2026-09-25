"""GRN Fase 4 — satu-satunya modul yang meng-import `openai` (§4.8).

Kunci: `integrations.openai.api_key` → cadangan env `OPENAI_API_KEY`. Responses API + JSON Schema strict + store=False.
Mode tiruan (uji tanpa kunci): hanya bila env `OCR_ALLOW_MOCK=1` DAN nama model diawali `mock-` → jawaban diambil dari
`backend/tests/fixtures/ocr/<nama>.json`.
"""
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

from services.ocr_sj_v2 import PROMPT_SJ_V2, SCHEMA_SJ_V2

_SEM = asyncio.Semaphore(4)
_FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "ocr"


class OcrError(Exception):
    def __init__(self, code: str, message: str, usage: Dict[str, int] | None = None, latency_ms: int = 0):
        super().__init__(message)
        self.code, self.message, self.usage, self.latency_ms = code, message, usage or {}, latency_ms


async def resolve_key() -> str:
    from services.integrations_service import get_integrations
    cfg = (await get_integrations()).get("openai", {}) or {}
    return (cfg.get("api_key") or os.environ.get("OPENAI_API_KEY") or "").strip()


def _usage(resp: Any) -> Dict[str, int]:
    u = getattr(resp, "usage", None)
    if not u:
        return {"input": 0, "cached_input": 0, "output": 0, "reasoning": 0}
    return {"input": getattr(u, "input_tokens", 0) or 0,
            "cached_input": getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0,
            "output": getattr(u, "output_tokens", 0) or 0,
            "reasoning": getattr(getattr(u, "output_tokens_details", None), "reasoning_tokens", 0) or 0}


def _mock(model: str) -> Dict[str, Any]:
    path = _FIXTURES / f"{model[len('mock-'):]}.json"
    if not path.is_file():
        raise OcrError("OCR_SCHEMA", f"Fixture tiruan {path.name} tidak ada.")
    return {"data": json.loads(path.read_text()), "usage": {"input": 1000, "cached_input": 0, "output": 500, "reasoning": 0},
            "latency_ms": 5}


async def extract(parts: List[Dict[str, Any]], n_pages: int, *, model: str, reasoning_effort: str,
                  max_output_tokens: int, extract_packing_list: bool) -> Dict[str, Any]:
    """Return {data, usage, latency_ms}; gagal → OcrError(code) dengan kode §4.8."""
    if model.startswith("mock-") and os.environ.get("OCR_ALLOW_MOCK") == "1":
        return _mock(model)
    key = await resolve_key()
    if not key:
        raise OcrError("OCR_AUTH", "Kunci OpenAI belum diisi di menu Integrasi.")
    from openai import APITimeoutError, AsyncOpenAI, AuthenticationError, RateLimitError
    client = AsyncOpenAI(api_key=key, timeout=60.0, max_retries=2)
    content = [{"type": "input_text",
                "text": f"Dokumen {n_pages} halaman. EXTRACT_PACKING_LIST={'true' if extract_packing_list else 'false'}."},
               *parts]
    t0 = time.monotonic()
    async with _SEM:
        try:
            resp = await client.responses.create(
                model=model, instructions=PROMPT_SJ_V2,
                input=[{"role": "user", "content": content}],
                text={"format": {"type": "json_schema", "name": "surat_jalan_v2", "schema": SCHEMA_SJ_V2, "strict": True}},
                reasoning={"effort": reasoning_effort}, max_output_tokens=max_output_tokens, store=False)
        except AuthenticationError as exc:
            raise OcrError("OCR_AUTH", "Kunci OpenAI ditolak (401).") from exc
        except RateLimitError as exc:
            raise OcrError("OCR_RATE_LIMIT", "OpenAI membatasi permintaan (429). Coba lagi sebentar.") from exc
        except APITimeoutError as exc:
            raise OcrError("OCR_TIMEOUT", "OpenAI tidak menjawab dalam batas waktu.") from exc
        except Exception as exc:  # noqa: BLE001 — model tak dikenal, 5xx, jaringan
            raise OcrError("OCR_API", f"Panggilan OpenAI gagal: {type(exc).__name__}: {str(exc)[:200]}") from exc
    latency = int((time.monotonic() - t0) * 1000)
    usage = _usage(resp)
    if getattr(resp, "status", "") == "incomplete":
        raise OcrError("OCR_INCOMPLETE", "Jawaban OpenAI terpotong (batas token).", usage, latency)
    for item in getattr(resp, "output", None) or []:
        for c in getattr(item, "content", None) or []:
            if getattr(c, "refusal", None):
                raise OcrError("OCR_REFUSAL", "OpenAI menolak membaca dokumen ini.", usage, latency)
    try:
        data = json.loads(resp.output_text)
    except (TypeError, ValueError) as exc:
        raise OcrError("OCR_SCHEMA", "Jawaban OpenAI bukan JSON sesuai skema.", usage, latency) from exc
    if not isinstance(data, dict) or not {"header", "lines", "totals"} <= set(data):
        raise OcrError("OCR_SCHEMA", "Jawaban OpenAI tidak memuat header/lines/totals.", usage, latency)
    return {"data": data, "usage": usage, "latency_ms": latency}


async def test_connection(key: str) -> Dict[str, Any]:
    from openai import AsyncOpenAI, AuthenticationError
    try:
        models = await AsyncOpenAI(api_key=key, timeout=20.0, max_retries=0).models.list()
    except AuthenticationError as exc:
        raise ValueError("Kunci OpenAI ditolak (401).") from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Tidak bisa terhubung ke OpenAI: {type(exc).__name__}") from exc
    ids = [m.id for m in getattr(models, "data", [])]
    return {"models_seen": len(ids), "sample": ids[:5]}
