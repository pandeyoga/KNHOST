"""AG-T1 — satu lapisan antara mesin percakapan Tanya KN dan penyedia model.

Pemanggil (`ai_chat_service._model_loop`, `ai_chat_service.job_ai_prewarm`, `ai_narrative._ai_text`) hanya berbicara
dengan `ModelProvider` lewat `active_provider()`. Pustaka klien penyedia hanya diimpor di modul ini (uji statik
`tests_mem/test_AGT1_penyedia.py` U16). Tes memasang pelaksana tiruan lewat `set_test_provider`
(`services/ai_provider_fake.py`), sehingga putaran alat bisa diuji tanpa panggilan ke luar dan tanpa kunci.

Percakapan (`conversation`) berisi butir netral: pesan `{"role": "user"|"assistant", "content": …}`, hasil alat
`tool_result(call_id, output)`, dan butir mentah `ModelTurn.carry` dari pelaksana yang wajib dikirim balik apa adanya
(mis. jejak penalaran terenkripsi dan permintaan alat). Pelaksana menerjemahkan butir netral ke bentuk penyedianya.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Protocol, Tuple

TOOL_RESULT = "tool_result"


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ModelTurn:
    text: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    usage: Dict[str, int] = field(default_factory=dict)
    carry: List[Any] = field(default_factory=list)   # butir mentah yang wajib dikirim balik di giliran berikutnya


class ModelProvider(Protocol):
    name: str

    async def run_turn(self, *, model: str, instructions: List[str], tools: List[Dict[str, Any]], conversation: List[Any],
                       effort: str, max_output_tokens: int,
                       on_text: Optional[Callable[[str], Awaitable[None]]] = None) -> ModelTurn: ...

    async def short_text(self, *, model: str, instructions: str, content: str,
                         max_output_tokens: int) -> Tuple[str, Dict[str, int]]: ...

    async def prewarm(self, *, model: str, instructions: List[str], tools: List[Dict[str, Any]]) -> Dict[str, int]: ...

    def price_of(self, model: str) -> Optional[Dict[str, float]]: ...


def tool_result(call_id: str, output: str) -> Dict[str, Any]:
    """Butir percakapan netral: keluaran satu panggilan alat."""
    return {"type": TOOL_RESULT, "call_id": call_id, "output": output}


# ── Pelaksana penyedia model lewat Responses API (pemanggilan fungsi + cache prompt) ──────────────────────────────────
PRICE_VERSION = "2026-06-perkiraan"
# USD per 1 juta token (dipindah dari `ai_cost.PRICES`, angka tidak berubah). Harga model ringkas = perkiraan; perbarui
# setelah tagihan penyedia pertama. Model yang tidak dikenal dihitung dengan harga model utama.
_PRICES: Dict[str, Dict[str, float]] = {
    "gpt-6-sol": {"input": 2.50, "cached_input": 0.25, "output": 10.00},
    "gpt-6-luna": {"input": 0.50, "cached_input": 0.05, "output": 2.00},
}
_PRICE_FALLBACK = "gpt-6-sol"
_CACHE_KEY = "kn-bi"


def _usage(resp: Any, *, cached: bool = True) -> Dict[str, int]:
    u = getattr(resp, "usage", None)
    out = {"input_tokens": int(getattr(u, "input_tokens", 0) or 0), "output_tokens": int(getattr(u, "output_tokens", 0) or 0)}
    if cached:
        out["cached_tokens"] = int(getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0)
    return out


class ResponsesProvider:
    """Pelaksana sungguhan. Kunci dari menu Integrasi (atau variabel lingkungan) — tidak pernah ditulis di sini."""

    name = "responses"

    def __init__(self, api_key: str) -> None:
        self._key = api_key

    def _client(self, timeout: float):
        from openai import AsyncOpenAI
        return AsyncOpenAI(api_key=self._key, timeout=timeout, max_retries=1)

    @staticmethod
    def _prefix(instructions: List[str]) -> List[Dict[str, Any]]:
        """Urutan tetap demi cache prompt: instruksi ke-1 tanpa titik potong, sisanya dengan titik potong eksplisit."""
        out = []
        for i, text in enumerate(instructions):
            part: Dict[str, Any] = {"type": "input_text", "text": text}
            if i:
                part["prompt_cache_breakpoint"] = {"mode": "explicit"}
            out.append({"role": "developer", "content": [part]})
        return out

    @staticmethod
    def _items(conversation: List[Any]) -> List[Any]:
        return [{"type": "function_call_output", "call_id": it["call_id"], "output": it["output"]}
                if isinstance(it, dict) and it.get("type") == TOOL_RESULT else it for it in conversation]

    async def run_turn(self, *, model, instructions, tools, conversation, effort, max_output_tokens, on_text=None):
        stream = await self._client(60.0).responses.create(
            model=model, tools=tools, input=self._prefix(instructions) + self._items(conversation), stream=True,
            reasoning={"effort": effort}, parallel_tool_calls=True, max_output_tokens=max_output_tokens, store=False,
            include=["reasoning.encrypted_content"], prompt_cache_key=_CACHE_KEY,
            extra_body={"prompt_cache_options": {"mode": "implicit", "ttl": "30m"}})
        resp = None
        async for sev in stream:
            et = getattr(sev, "type", "")
            if et == "response.output_text.delta":
                if on_text:
                    await on_text(sev.delta)
            elif et == "response.completed":
                resp = sev.response
            elif et in ("response.failed", "response.incomplete", "error"):
                err = getattr(getattr(getattr(sev, "response", None), "error", None), "message", None) or getattr(sev, "message", None)
                raise RuntimeError(err or f"model berhenti ({et})")
        if resp is None:
            raise RuntimeError("respons model terputus")
        calls = [ToolCall(id=o.call_id, name=o.name, arguments=json.loads(o.arguments or "{}"))
                 for o in resp.output if getattr(o, "type", "") == "function_call"]
        carry = [o.model_dump(exclude_none=True) for o in resp.output if getattr(o, "type", "") in ("reasoning", "function_call")]
        return ModelTurn(text="" if calls else (resp.output_text or ""), tool_calls=calls, usage=_usage(resp), carry=carry)

    async def short_text(self, *, model, instructions, content, max_output_tokens):
        resp = await self._client(45.0).responses.create(
            model=model, store=False, max_output_tokens=max_output_tokens, reasoning={"effort": "low"},
            input=[{"role": "developer", "content": [{"type": "input_text", "text": instructions}]},
                   {"role": "user", "content": [{"type": "input_text", "text": content}]}])
        return (resp.output_text or "").strip(), _usage(resp)

    async def prewarm(self, *, model, instructions, tools):
        resp = await self._client(60.0).responses.create(
            model=model, tools=tools, max_output_tokens=16, store=False, prompt_cache_key=_CACHE_KEY,
            input=self._prefix(instructions) + [{"role": "user", "content": "ok"}],
            extra_body={"prompt_cache_options": {"mode": "implicit", "ttl": "30m", "prewarm": True}})
        return _usage(resp, cached=False)

    def price_of(self, model: str) -> Optional[Dict[str, float]]:
        return _PRICES.get(model) or _PRICES[_PRICE_FALLBACK]


# ── Pemilihan pelaksana ──────────────────────────────────────────────────────────────────────────────────────────────
_TEST_PROVIDER: Optional[ModelProvider] = None


def set_test_provider(p: Optional[ModelProvider]) -> None:
    """Hanya dipanggil tes: pasang pelaksana tiruan (None = kembali ke pelaksana sungguhan)."""
    global _TEST_PROVIDER
    _TEST_PROVIDER = p


async def _resolve_key() -> str:
    from services.ocr_openai_client import resolve_key
    return await resolve_key()


async def configured_provider() -> Optional[ModelProvider]:
    """Pelaksana yang siap dipakai TANPA melihat sakelar `ai.enabled` (layar status: "kunci ada"). None = tanpa kunci."""
    if _TEST_PROVIDER is not None:
        return _TEST_PROVIDER
    key = await _resolve_key()
    return ResponsesProvider(key) if key else None


async def active_provider() -> Optional[ModelProvider]:
    """Pelaksana untuk memanggil model sekarang. None = fitur mati (`ai.enabled`) atau tidak ada kunci."""
    from services.config_resolver import value_of
    if not await value_of("ai.enabled"):
        return None
    return await configured_provider()
