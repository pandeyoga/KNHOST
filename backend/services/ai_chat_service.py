"""Tanya KN F2.2 — orkestrator chat bebas (OpenAI Responses API + function calling).

Siap pakai tetapi MATI sampai `ai.enabled=true` DAN kunci OpenAI terpasang (integrasi `openai`
atau env OPENAI_API_KEY). Selama mati, pertanyaan dijawab dengan saran template (tanpa model).
Urutan permintaan tetap demi prompt caching (§7.1): tools → developer#1 system → developer#2
katalog (breakpoint) → developer#3 konteks sesi (breakpoint) → percakapan (append-only).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from db import db
from core_utils import new_id, now_iso
from services import ai_cost, ai_templates, ai_tools
from services.ai_number_check import verify
from services.analytics_config import ai_policy
from services.analytics_time import now_wib
from services.config_resolver import value_of

logger = logging.getLogger(__name__)
_DATA = Path(__file__).resolve().parents[1] / "data" / "ai"
SYSTEM_PROMPT_V1 = (_DATA / "system_prompt_kn_analitik_v1.md").read_text(encoding="utf-8")
CATALOG_V1 = (_DATA / "katalog_semantik_v1.md").read_text(encoding="utf-8")
TOOLS_V1 = json.loads((_DATA / "tools_kn_analitik_v1.json").read_text(encoding="utf-8"))
VERSIONS = "prompt sp-v1 · katalog cat-v1 · tool tools-v1"
_HARI = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
_BLOCK_RE = re.compile(r"(```kn-[\s\S]*?```)")
STREAM_DELAY_S = 0.02


async def stream_text(text: str) -> AsyncIterator[Dict[str, Any]]:
    """Teks jadi (template/mode uji/notice) dikirim kata demi kata; blok kn-* utuh agar JSON tak terpotong."""
    for part in _BLOCK_RE.split(text or ""):
        if not part:
            continue
        if part.startswith("```kn-"):
            yield {"type": "delta", "text": part}
            continue
        words = re.findall(r"\s*\S+", part)
        if not words:
            # part is pure whitespace (typical between kn-* blocks) — emit once
            yield {"type": "delta", "text": part}
            await asyncio.sleep(STREAM_DELAY_S)
            continue
        for word in words:
            yield {"type": "delta", "text": word}
            await asyncio.sleep(STREAM_DELAY_S)
        if part[-1:].isspace():
            yield {"type": "delta", "text": part[len(part.rstrip()):]}


async def chat_config() -> Dict[str, Any]:
    keys = ("enabled", "model_main", "reasoning_effort", "deep_effort", "max_tool_rounds", "max_output_tokens",
            "result_rows_to_model", "daily_question_limit")
    return {k: await value_of(f"ai.{k}") for k in keys}


def _is_mock(cfg: Dict[str, Any]) -> bool:
    # KN-E44 — mode tiruan butuh penjaga env eksplisit (sama seperti OCR), bukan hanya nama model.
    import os as _os
    return str(cfg.get("model_main") or "").startswith("mock") and _os.environ.get("AI_ALLOW_MOCK", "1") == "1"


async def resolve_key() -> str:
    from services.ocr_openai_client import resolve_key as _rk
    return await _rk()


async def status(user: Dict[str, Any]) -> Dict[str, Any]:
    cfg, pol = await chat_config(), await ai_policy()
    has_key, mock = bool(await resolve_key()), _is_mock(cfg)
    budget = await ai_cost.budget_state()
    live = bool(cfg["enabled"]) and has_key and not mock and not budget["exceeded"]
    return {"chat_enabled": bool(cfg["enabled"]) and (mock or (has_key and not budget["exceeded"])),
            "config_enabled": bool(cfg["enabled"]), "has_key": has_key, "narrative_ai": live, "budget": budget,
            "mock": mock, "model": cfg["model_main"], "sales_definition": pol["sales_definition"],
            "sales_attribution": pol["sales_attribution"], "margin_roles": pol["margin_roles"],
            "stock_value_roles": pol["stock_value_roles"], "can_edit_rules": user.get("role") in ("admin", "manager")}


async def _session_context(user, ctx) -> str:
    pol = await ai_policy()
    now = now_wib()
    ents = [e async for e in db.business_entities.find({"id": {"$in": ctx.allowed_entity_ids}}, {"_id": 0, "id": 1, "short_name": 1})
            .sort("id", 1)]   # KN-E40 — urutan tetap supaya prefix cache tidak pecah
    name = {e["id"]: e.get("short_name") or e["id"] for e in ents}
    role = user.get("role")
    # KN-E40 — tanpa jam:menit (dulu cache pecah tiap menit); tanggal cukup untuk "hari ini".
    return (f"# KONTEKS SESI\nHari ini: {_HARI[now.weekday()]}, {now.day} {now.strftime('%m')}/{now.year} (WIB)\n"
            f"Pengguna: {user.get('name')} · peran: {role} · lini produk: {', '.join(user.get('allowed_line_codes') or []) or 'semua'}\n"
            f"Entitas aktif: {name.get(ctx.active_entity_id, ctx.active_entity_id)} · boleh melihat: {', '.join(name.values())} · "
            f"mode: {'semua entitas' if getattr(ctx, 'view_all', False) else 'satu entitas'}\n"
            f"Hak data: margin={'ya' if role in pol['margin_roles'] else 'tidak'} · nilai stok={'ya' if role in pol['stock_value_roles'] else 'tidak'} · "
            f"hanya pelanggan sendiri={'ya' if role == 'sales' else 'tidak'}\nVersi: {VERSIONS}" + await _glossary())


async def _glossary() -> str:
    raw = str(await value_of("ai.glossary") or "")
    lines = [ln.strip() for ln in raw.splitlines() if "=" in ln and ln.split("=", 1)[0].strip()][:80]
    if not lines:
        return ""
    return "\n# KAMUS ISTILAH PERUSAHAAN (bahasa sehari-hari tim → arti)\n" + "\n".join(f"- {ln[:160]}" for ln in lines)


CONTEXT_TYPES = {"customer": ("Pelanggan", "id"), "product": ("Produk", "id"), "sales_order": ("Pesanan penjualan", "nomor"),
                 "purchase_order": ("Purchase order", "nomor"), "goods_receipt": ("Kedatangan barang (GRN)", "nomor")}


def context_prefix(context: Optional[Dict[str, Any]]) -> str:
    """Konteks halaman asal pertanyaan → awalan pesan untuk model (nilai dibatasi & dibersihkan)."""
    if not isinstance(context, dict) or context.get("type") not in CONTEXT_TYPES:
        return ""
    label, key = CONTEXT_TYPES[context["type"]]
    clean = lambda v: re.sub(r"[\[\]\n\r`]", " ", str(v or ""))[:120].strip()  # noqa: E731
    ref = clean(context.get("id")) if key == "id" else clean(context.get("label") or context.get("id"))
    return f"[Konteks halaman: {label} \u201c{clean(context.get('label'))}\u201d · {key}: {ref}]\n"


def _trim(res: Dict[str, Any], n: int) -> Dict[str, Any]:
    out = dict(res)
    if isinstance(out.get("rows"), list):
        out["truncated"] = out.get("truncated") or len(out["rows"]) > n
        out["rows"] = out["rows"][:n]
    if isinstance(out.get("sections"), dict):
        out["sections"] = {k: _trim(v, n) for k, v in out["sections"].items()}
    return out


async def _load_chat_session(session_id: Optional[str], user, question: str) -> Dict[str, Any]:
    if session_id:
        s = await db.ai_chat_sessions.find_one({"id": session_id, "user_id": user["id"]}, {"_id": 0})
        if s:
            return s
    s = {"id": new_id("aichat"), "user_id": user["id"], "title": question[:80], "turns": [], "items": [],
         "created_at": now_iso(), "updated_at": now_iso()}
    await db.ai_chat_sessions.insert_one(dict(s))
    return s


async def _questions_today(user_id: str) -> int:
    return await db.ai_usage_log.count_documents({"user_id": user_id, "feature": "bi_chat",
                                                  "created_at": {"$gte": now_wib().replace(hour=0, minute=0).isoformat()}})


async def chat_events(question: str, session_id: Optional[str], deep: bool, user, ctx,
                      context: Optional[Dict[str, Any]] = None) -> AsyncIterator[Dict[str, Any]]:
    cfg = await chat_config()
    session = await _load_chat_session(session_id, user, question)
    prefix_ctx = context_prefix(context)
    turn_user = {"role": "user", "content": question, "at": now_iso(),
                 **({"context": {k: str(context.get(k) or "")[:120] for k in ("type", "id", "label")}} if prefix_ctx else {})}
    role = user.get("role") or ""
    routed = None if prefix_ctx else ai_templates.route(question, role, int(await value_of("ai.route_threshold_pct") or 90))
    if routed:
        async for ev in _template_answer(routed, question, session, turn_user, user, ctx,
                                         f"Pertanyaan ini cocok dengan template \u201c{routed['title']}\u201d, jadi dijawab langsung tanpa AI."):
            yield ev
        return
    mock = _is_mock(cfg)
    key = await resolve_key() if cfg["enabled"] and not mock else ""
    budget = await ai_cost.budget_state() if key else {"exceeded": False}
    if not cfg["enabled"] or not (key or mock) or budget["exceeded"]:
        text = ("Anggaran AI bulan ini sudah habis, jadi chat bebas dimatikan sampai bulan depan. " if budget["exceeded"] else
                "Asisten chat bebas belum aktif (menunggu kunci OpenAI dan persetujuan pengiriman data agregat). ") + \
            "Sementara itu, template laporan berikut bisa langsung menjawab tanpa AI:"
        sugg = ai_templates.suggest(question, role)
        await _append(session, [turn_user, {"role": "assistant", "content": text, "suggestions": sugg, "at": now_iso()}], [])
        async for ev in stream_text(text):
            yield ev
        yield {"type": "done", "disabled": True, "suggestions": sugg, "session_id": session["id"], "verification": None, "text": text}
        return
    # KN-E33 — kuota DIRESERVASI atomik sebelum memanggil model (sisip dulu, lalu hitung): permintaan
    # paralel tidak bisa lolos semua; baris reservasi diperbarui dengan pemakaian nyata di `finally`.
    res_id = await _reserve_usage(cfg["model_main"], user, ctx)
    if await _questions_today(user["id"]) > int(cfg["daily_question_limit"] or 60):
        await db.ai_usage_log.delete_one({"id": res_id})
        yield {"type": "done", "error": "Kuota pertanyaan harian Anda sudah habis.", "session_id": session["id"]}
        return
    if mock:
        tpl = next((t for t in ai_templates.suggest(question, role, n=50) if not any(p.get("required") for p in t["params"])), None)
        if not tpl:
            yield {"type": "done", "error": "Tidak ada laporan yang cocok untuk peran Anda.", "session_id": session["id"]}
            return
        await _finalize_usage(res_id, cfg["model_main"], {}, 0)
        async for ev in _template_answer(tpl, question, session, turn_user, user, ctx,
                                         f"[MODE UJI \u2014 jawaban tiruan tanpa OpenAI] Pertanyaan Anda dijawab dengan laporan \u201c{tpl['title']}\u201d."):
            yield ev
        return
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=key, timeout=60.0, max_retries=1)
    prefix = [
        {"role": "developer", "content": [{"type": "input_text", "text": SYSTEM_PROMPT_V1}]},
        {"role": "developer", "content": [{"type": "input_text", "text": CATALOG_V1, "prompt_cache_breakpoint": {"mode": "explicit"}}]},
        {"role": "developer", "content": [{"type": "input_text", "text": await _session_context(user, ctx),
                                           "prompt_cache_breakpoint": {"mode": "explicit"}}]},
    ]
    items: List[Any] = _cap_history(list(session.get("items") or [])) + [{"role": "user", "content": prefix_ctx + question}]
    results: List[Dict[str, Any]] = []
    rids: List[str] = []
    usage_tot: Dict[str, int] = {}
    text, started = "", time.perf_counter()
    try:
        async for ev in _model_loop(client, cfg, deep, prefix, items, results, rids, usage_tot, user, ctx, session):
            if ev.get("type") == "_final":
                text = ev["text"]
            else:
                yield ev
    finally:   # KN-E33 — dicatat walau klien memutus koneksi (CancelledError/GeneratorExit)
        await _finalize_usage(res_id, cfg["model_main"], usage_tot, int((time.perf_counter() - started) * 1000))
    items.append({"role": "assistant", "content": text})
    ver = verify(text, results)
    await _append(session, [turn_user, {"role": "assistant", "content": text, "verification": ver, "usage": usage_tot,
                                        "result_ids": rids, "at": now_iso()}], items, replace_items=True)
    yield {"type": "done", "verification": ver, "usage": usage_tot, "session_id": session["id"], "result_ids": rids, "text": text}


_HISTORY_MAX_ITEMS = 60


def _cap_history(items: List[Any]) -> List[Any]:
    """KN-E40 — riwayat dibatasi; potong di batas pesan pengguna agar pasangan tool-call tetap utuh."""
    if len(items) <= _HISTORY_MAX_ITEMS:
        return items
    cut = len(items) - _HISTORY_MAX_ITEMS
    starts = [i for i, it in enumerate(items) if isinstance(it, dict) and it.get("role") == "user" and i >= cut]
    return items[starts[0]:] if starts else []


async def _reserve_usage(model: str, user, ctx) -> str:
    rid = new_id("aiu")
    await db.ai_usage_log.insert_one({"id": rid, "feature": "bi_chat", "model": model, "user_id": user["id"],
                                      "entity_id": ctx.active_entity_id, "usage": {}, "cost_usd": 0.0,
                                      "status": "reserved", "created_at": now_wib().isoformat(), "latency_ms": 0})
    return rid


async def _finalize_usage(rid: str, model: str, usage: Dict[str, int], latency_ms: int) -> None:
    await db.ai_usage_log.update_one({"id": rid}, {"$set": {
        "usage": usage, "cost_usd": ai_cost.cost_usd(model, usage), "latency_ms": latency_ms, "status": "done"}})


async def _model_loop(client, cfg, deep, prefix, items, results, rids, usage_tot, user, ctx, session):
    text = ""
    for _ in range(int(cfg["max_tool_rounds"] or 6)):
        yield {"type": "status", "text": "Menganalisis pertanyaan…" if not results else "Menyusun jawaban…"}
        stream = await client.responses.create(
            model=cfg["model_main"], tools=TOOLS_V1, input=prefix + items, stream=True,
            reasoning={"effort": cfg["deep_effort"] if deep else cfg["reasoning_effort"]}, parallel_tool_calls=True,
            max_output_tokens=int(cfg["max_output_tokens"] or 4000), store=False, include=["reasoning.encrypted_content"],
            prompt_cache_key="kn-bi", extra_body={"prompt_cache_options": {"mode": "implicit", "ttl": "30m"}})
        resp, streamed = None, False
        async for sev in stream:
            et = getattr(sev, "type", "")
            if et == "response.output_text.delta":
                streamed = True
                yield {"type": "delta", "text": sev.delta}
            elif et == "response.completed":
                resp = sev.response
            elif et in ("response.failed", "response.incomplete", "error"):
                err = getattr(getattr(getattr(sev, "response", None), "error", None), "message", None) or getattr(sev, "message", None)
                raise RuntimeError(err or f"model berhenti ({et})")
        if resp is None:
            raise RuntimeError("respons model terputus")
        u = getattr(resp, "usage", None)
        if u:
            for k in ("input_tokens", "output_tokens"):
                usage_tot[k] = usage_tot.get(k, 0) + int(getattr(u, k, 0) or 0)
            usage_tot["cached_tokens"] = usage_tot.get("cached_tokens", 0) + int(getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0)
        calls = [o for o in resp.output if getattr(o, "type", "") == "function_call"]
        items += [o.model_dump(exclude_none=True) for o in resp.output if getattr(o, "type", "") in ("reasoning", "function_call")]
        if not calls:
            text = resp.output_text or ""
            break
        if streamed:
            yield {"type": "delta_reset"}
        for c in calls:
            args = json.loads(c.arguments or "{}")
            yield {"type": "status", "text": f"Mengambil data ({c.name})…"}
            yield {"type": "tool", "name": c.name, "arguments": args}
            res = await ai_tools.execute(c.name, args, user, ctx, session["id"])
            results.append(res)
            for r in [res] + list((res.get("sections") or {}).values()):
                if r.get("result_id"):
                    rids.append(r["result_id"])
                    yield {"type": "result", "result_id": r["result_id"], "title": r.get("title")}
            items.append({"type": "function_call_output", "call_id": c.call_id,
                          "output": json.dumps(_trim(res, int(cfg["result_rows_to_model"] or 50)), ensure_ascii=False, default=str)})
    yield {"type": "_final", "text": text}


async def _template_answer(tpl, question, session, turn_user, user, ctx, lead: str) -> AsyncIterator[Dict[str, Any]]:
    """Jawaban chat dari template (routing F5 / mode uji): angka server, blok kn-*, narasi otomatis."""
    yield {"type": "status", "text": f"Menjalankan {tpl['title']}\u2026"}
    out = await ai_templates.run(tpl["id"], {}, user, ctx, session["id"])
    rids = list(out["results"])
    for rid, r in out["results"].items():
        yield {"type": "result", "result_id": rid, "title": r.get("title")}
    blocks = [f"```kn-{'chart' if b['kind'] == 'chart' else 'table'}\n{json.dumps(b, ensure_ascii=False)}\n```"
              for b in out["blocks"] if b["kind"] in ("chart", "table")]
    follow = json.dumps([t["title"] for t in ai_templates.suggest(question, user.get("role") or "", n=4) if t["id"] != tpl["id"]][:3],
                        ensure_ascii=False)
    text = f"{lead} Angka di bawah dihitung langsung oleh server.\n\n" + (f"{out['narrative']}\n\n" if out.get("narrative") else "") + \
        "\n\n".join(blocks) + f"\n\n```kn-followups\n{follow}\n```"
    await _append(session, [turn_user, {"role": "assistant", "content": text, "result_ids": rids, "template_id": tpl["id"], "at": now_iso()}], [])
    async for ev in stream_text(text):
        yield ev
    yield {"type": "done", "verification": None, "session_id": session["id"], "result_ids": rids, "template_id": tpl["id"], "text": text}


async def job_ai_prewarm() -> Dict[str, Any]:
    """§7.3 — hari kerja: kirim prefix statis agar cache prompt hangat. Diam bila mati/tanpa kunci/mode uji."""
    cfg = await chat_config()
    if now_wib().weekday() >= 5 or not await value_of("ai.prewarm_enabled") or not cfg["enabled"] or _is_mock(cfg):
        return {"scanned": 0, "created": 0, "detail": "Dilewati (mati, akhir pekan, atau mode uji)"}
    key = await resolve_key()
    if not key or (await ai_cost.budget_state())["exceeded"]:
        return {"scanned": 0, "created": 0, "detail": "Dilewati (tanpa kunci atau anggaran habis)"}
    from openai import AsyncOpenAI
    resp = await AsyncOpenAI(api_key=key, timeout=60.0, max_retries=1).responses.create(
        model=cfg["model_main"], tools=TOOLS_V1, max_output_tokens=16, store=False, prompt_cache_key="kn-bi",
        input=[{"role": "developer", "content": [{"type": "input_text", "text": SYSTEM_PROMPT_V1}]},
               {"role": "developer", "content": [{"type": "input_text", "text": CATALOG_V1, "prompt_cache_breakpoint": {"mode": "explicit"}}]},
               {"role": "user", "content": "ok"}],
        extra_body={"prompt_cache_options": {"mode": "implicit", "ttl": "30m", "prewarm": True}})
    u = getattr(resp, "usage", None)
    usage = {"input_tokens": int(getattr(u, "input_tokens", 0) or 0), "output_tokens": int(getattr(u, "output_tokens", 0) or 0)}
    await db.ai_usage_log.insert_one({"id": new_id("aiu"), "feature": "bi_prewarm", "model": cfg["model_main"], "usage": usage,
                                      "cost_usd": ai_cost.cost_usd(cfg["model_main"], usage), "created_at": now_wib().isoformat()})
    return {"scanned": 1, "created": 0, "detail": f"Prefix dipanaskan ({usage['input_tokens']} token)"}


async def _append(session, turns, items, replace_items: bool = False) -> None:
    upd: Dict[str, Any] = {"$push": {"turns": {"$each": turns}}, "$set": {"updated_at": now_iso()}}
    if replace_items:
        upd["$set"]["items"] = items
    await db.ai_chat_sessions.update_one({"id": session["id"]}, upd)
