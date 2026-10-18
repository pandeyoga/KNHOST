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
    import re as _re
    name = model[len('mock-'):]
    # KN-E29 — nama fixture hanya [A-Za-z0-9_-]; "mock-../../x" tidak bisa membaca berkas lain.
    if not _re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name):
        raise OcrError("OCR_SCHEMA", "Nama model tiruan tidak sah.")
    path = (_FIXTURES / f"{name}.json").resolve()
    if path.parent != _FIXTURES.resolve() or not path.is_file():
        raise OcrError("OCR_SCHEMA", f"Fixture tiruan {path.name} tidak ada.")
    data = json.loads(path.read_text())
    data["is_mock"] = True   # KN-E29 — hasil tiruan ditandai sampai ke data & UI
    return {"data": data, "usage": {"input": 1000, "cached_input": 0, "output": 500, "reasoning": 0},
            "latency_ms": 5, "is_mock": True}


async def extract(parts: List[Dict[str, Any]], n_pages: int, *, model: str, reasoning_effort: str,
                  max_output_tokens: int, extract_packing_list: bool, hints: str = "") -> Dict[str, Any]:
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
               *([{"type": "input_text", "text": hints}] if hints else []), *parts]
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


_ORIENT_SCHEMA = {"type": "object", "properties": {"rotate_cw": {"type": "integer", "enum": [0, 90, 180, 270]}},
                  "required": ["rotate_cw"], "additionalProperties": False}
_ORIENT_PROMPT = ("Photo of a printed document. How many degrees must the image be rotated CLOCKWISE so the main "
                  "printed text reads normally left-to-right, top-to-bottom?")


async def _small_json(model: str, instructions: str, image_part: Dict[str, Any], schema: Dict[str, Any], name: str,
                      code: str) -> Dict[str, Any]:
    key = await resolve_key()
    if not key:
        raise OcrError("OCR_AUTH", "Kunci OpenAI belum diisi di menu Integrasi.")
    from openai import AsyncOpenAI
    t0 = time.monotonic()
    async with _SEM:
        try:
            resp = await AsyncOpenAI(api_key=key, timeout=30.0, max_retries=1).responses.create(
                model=model, instructions=instructions, input=[{"role": "user", "content": [image_part]}],
                text={"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}},
                reasoning={"effort": "low"}, max_output_tokens=3000, store=False)
            data = json.loads(resp.output_text)
        except Exception as exc:  # noqa: BLE001 — pemeriksaan tambahan gagal → alur utama jalan terus
            raise OcrError(code, f"Pemeriksaan gagal: {type(exc).__name__}") from exc
    return {"data": data, "usage": _usage(resp), "latency_ms": int((time.monotonic() - t0) * 1000)}


async def detect_rotation(image_part: Dict[str, Any], *, model: str) -> Dict[str, Any]:
    """Foto SJ sering miring 90° (WhatsApp membuang EXIF) → model menebak putaran searah jarum jam."""
    r = await _small_json(model, _ORIENT_PROMPT, image_part, _ORIENT_SCHEMA, "orient", "OCR_ORIENT")
    return {"rotate_cw": int(r["data"]["rotate_cw"]), "usage": r["usage"], "latency_ms": r["latency_ms"]}


_QUALITY_SCHEMA = {"type": "object", "additionalProperties": False,
                   "required": ["is_document", "cut_off_sides", "blurry", "glare_or_shadow", "legibility", "advice"],
                   "properties": {
                       "is_document": {"type": "boolean"},
                       "cut_off_sides": {"type": "array", "items": {"type": "string", "enum": ["atas", "bawah", "kiri", "kanan"]}},
                       "blurry": {"type": "boolean"}, "glare_or_shadow": {"type": "boolean"},
                       "legibility": {"type": "string", "enum": ["jelas", "sebagian", "buruk"]},
                       "advice": {"type": "string"}}}
_QUALITY_PROMPT = (
    "Kamu pemeriksa mutu foto surat jalan/packing list SEBELUM dibaca otomatis. Nilai foto ini:\n"
    "- is_document: apakah foto berisi dokumen surat jalan/packing list/nota.\n"
    "- cut_off_sides: sisi dokumen yang TERPOTONG di tepi foto sehingga ada tulisan/tabel/kop/tanda tangan yang hilang. "
    "Kertas yang sedikit keluar bingkai tapi tanpa tulisan hilang BUKAN terpotong. Abaikan dokumen lain di latar.\n"
    "- blurry: tulisan kabur/goyang sehingga angka sulit dibaca.\n"
    "- glare_or_shadow: pantulan cahaya atau bayangan menutupi bagian tulisan.\n"
    "- legibility: jelas (semua angka tabel terbaca) / sebagian / buruk.\n"
    "- advice: satu kalimat Bahasa Indonesia ≤ 20 kata untuk staf gudang bila perlu foto ulang; kosong bila foto sudah baik.\n"
    "Foto miring 90° atau terbalik TIDAK masalah (diputar otomatis).")


async def photo_quality(image_part: Dict[str, Any], *, model: str) -> Dict[str, Any]:
    r = await _small_json(model, _QUALITY_PROMPT, image_part, _QUALITY_SCHEMA, "photo_quality", "OCR_QUALITY")
    return {**r["data"], "usage": r["usage"], "latency_ms": r["latency_ms"]}


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
