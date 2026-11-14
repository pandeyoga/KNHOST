"""AG-T1 — pelaksana penyedia model TIRUAN untuk tes (tanpa panggilan ke luar, tanpa kunci).

    from services import ai_provider
    from services.ai_provider_fake import ScriptedProvider
    tiruan = ScriptedProvider([{"tool": "find_entities", "args": {"kind": "supplier", "query": "s1"}},
                               {"text": "Ada satu pemasok."}])
    ai_provider.set_test_provider(tiruan)      # … jalankan alur …; lalu set_test_provider(None)

`script` = daftar langkah, atau fungsi `(conversation) -> langkah`. Langkah: `{"tool": nama, "args": {...}}` (model
meminta satu alat), `{"text": "..."}` (model menjawab), atau `{"error": "..."}` (penyedia gagal → `RuntimeError`).
Langkah habis = jawaban teks kosong. Setiap permintaan dicatat di `.calls` (jenis, model, instruksi, daftar alat,
salinan percakapan) supaya tes bisa memeriksa apa yang dikirim ke penyedia.
"""
from __future__ import annotations

import copy
from typing import Any, Callable, Dict, List, Optional, Union

from services.ai_provider import ModelTurn, ToolCall

Langkah = Dict[str, Any]


class ScriptedProvider:
    name = "tiruan"

    def __init__(self, script: Union[List[Langkah], Callable[[List[Any]], Langkah]],
                 prices: Optional[Dict[str, Dict[str, float]]] = None) -> None:
        self.script = script
        self.prices = prices or {}
        self.calls: List[Dict[str, Any]] = []
        self._i = 0

    def _langkah(self, conversation: List[Any]) -> Langkah:
        if callable(self.script):
            return self.script(conversation) or {"text": ""}
        if self._i >= len(self.script):
            return {"text": ""}
        step = self.script[self._i]
        self._i += 1
        return step

    @staticmethod
    def _usage(step: Langkah) -> Dict[str, int]:
        return dict(step.get("usage") or {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0})

    async def run_turn(self, *, model, instructions, tools, conversation, effort, max_output_tokens, on_text=None):
        self.calls.append({"kind": "run_turn", "model": model, "instructions": list(instructions), "tools": list(tools),
                           "conversation": copy.deepcopy(conversation), "effort": effort,
                           "max_output_tokens": max_output_tokens})
        step = self._langkah(conversation)
        if step.get("error"):
            raise RuntimeError(step["error"])
        if step.get("tool"):
            cid = f"tiruan_{len(self.calls)}"
            args = dict(step.get("args") or {})
            return ModelTurn(text="", tool_calls=[ToolCall(id=cid, name=step["tool"], arguments=args)],
                             usage=self._usage(step),
                             carry=[{"type": "tool_call", "call_id": cid, "name": step["tool"], "arguments": args}])
        text = str(step.get("text") or "")
        if on_text and text:
            await on_text(text)
        return ModelTurn(text=text, usage=self._usage(step))

    async def short_text(self, *, model, instructions, content, max_output_tokens):
        self.calls.append({"kind": "short_text", "model": model, "instructions": instructions, "content": content,
                           "max_output_tokens": max_output_tokens})
        step = self._langkah([{"role": "user", "content": content}])
        if step.get("error"):
            raise RuntimeError(step["error"])
        return str(step.get("text") or "").strip(), self._usage(step)

    async def prewarm(self, *, model, instructions, tools):
        self.calls.append({"kind": "prewarm", "model": model, "instructions": list(instructions), "tools": list(tools)})
        return {"input_tokens": 0, "output_tokens": 0}

    def price_of(self, model: str) -> Optional[Dict[str, float]]:
        return self.prices.get(model)
