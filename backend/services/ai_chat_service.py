"""Tanya KN F2.2 — orkestrator chat bebas (pemanggilan alat lewat penyedia model).

Siap pakai tetapi MATI sampai `ai.enabled=true` DAN kunci penyedia model terpasang (menu Integrasi atau variabel
lingkungan). Selama mati, pertanyaan dijawab dengan saran template (tanpa model).
AG-T1 — penyedia model hanya diajak bicara lewat `services/ai_provider.py` (`active_provider()`); tes memasang
pelaksana tiruan. Urutan permintaan tetap demi cache prompt (§7.1): tools → instruksi#1 system → instruksi#2
katalog (titik potong) → instruksi#3 konteks sesi (titik potong) → percakapan (append-only).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from db import db
from core_utils import new_id, now_iso
from services import ai_cost, ai_provider, ai_templates, ai_tools
from services.ai_number_check import verify
from services.analytics_config import ai_policy
from services.analytics_time import now_wib
from services.config_resolver import value_of
from dependencies import has_permission

logger = logging.getLogger(__name__)
_DATA = Path(__file__).resolve().parents[1] / "data" / "ai"
SYSTEM_PROMPT_V1 = (_DATA / "system_prompt_kn_analitik_v1.md").read_text(encoding="utf-8")
CATALOG_V1 = (_DATA / "katalog_semantik_v1.md").read_text(encoding="utf-8")
TOOLS_V1 = json.loads((_DATA / "tools_kn_analitik_v1.json").read_text(encoding="utf-8"))
VERSIONS = "prompt sp-v1 · katalog cat-v1 · tool tools-v1"
# AG-T2 — mode Keuangan: alat baca lewat pintu aplikasi sendiri, instruksi tambahan, teks tidak dialirkan.
TOOLS_FIN_V1 = json.loads((_DATA / "tools_kn_keuangan_v1.json").read_text(encoding="utf-8"))
FINANCE_PROMPT_V1 = (_DATA / "system_prompt_kn_keuangan_v1.md").read_text(encoding="utf-8")
# AG-T3 — alat `prepare_action` (kartu tindakan golongan A/B) hanya di mode Keuangan. Tidak ada alat untuk menyetujui.
TOOLS_ACT_V1 = json.loads((_DATA / "tools_kn_tindakan_v1.json").read_text(encoding="utf-8"))
MODES = ("umum", "keuangan")
#: Konstanta teknis (bukan aturan bisnis): satu putaran ulang bila pemeriksa angka menolak jawaban mode Keuangan.
FINANCE_VERIFY_RETRIES = 1
#: Pengaliran teks model per mode (RISIKO unit: mode Keuangan terasa lebih lambat; membatalkan = ubah di sini).
STREAM_BY_MODE = {"umum": True, "keuangan": False}
FINANCE_FALLBACK = ("Saya tidak bisa memastikan angka untuk pertanyaan ini. Data yang berhasil diambil ada di tabel "
                    "di bawah.")
#: Alat yang mengubah data (kartu tindakan). Ditolak sesudah alat teks bebas dipakai pada giliran yang sama.
ACTION_TOOLS = frozenset({"propose_action", "prepare_action"})
ACTION_BLOCKED = "Alat tindakan tidak tersedia pada giliran ini."
#: Label sehari-hari alat untuk teks status di layar (kode alat tidak ditampilkan; L1).
TOOL_STATUS_LABEL = {
    "query_metrics": "angka ringkasan", "analyze_change": "analisis perubahan", "list_records": "daftar dokumen",
    "run_report": "laporan", "find_entities": "pencarian nama", "get_document": "dokumen", "ops_metrics": "metrik operasional",
    "forecast": "perkiraan", "propose_action": "draf tindakan", "prepare_action": "kartu tindakan",
    "fin_journal_search": "jurnal", "fin_journal_get": "rincian jurnal", "fin_account_ledger": "buku besar",
    "fin_trial_balance": "neraca saldo", "fin_income_statement": "laba rugi", "fin_balance_sheet": "neraca",
    "fin_cash_flow": "arus kas", "fin_equity_changes": "perubahan ekuitas", "fin_ar_aging": "umur piutang",
    "fin_ar_customer": "piutang pelanggan", "fin_ap_summary": "ringkasan hutang", "fin_vendor_bills": "tagihan pemasok",
    "fin_cash_position": "posisi kas & bank", "fin_bank_unmatched": "mutasi bank", "fin_bank_candidates": "saran pencocokan",
    "fin_period_status": "status periode", "fin_posting_failures": "posting gagal", "fin_interco_balances": "saldo antar-PT",
    "fin_elimination_candidates": "usulan eliminasi", "fin_tax_invoices": "faktur pajak", "fin_vat_summary": "rekap PPN",
    "fin_budget_vs_actual": "anggaran",
}
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


async def status(user: Dict[str, Any]) -> Dict[str, Any]:
    cfg, pol = await chat_config(), await ai_policy()
    has_key, mock = (await ai_provider.configured_provider()) is not None, _is_mock(cfg)
    budget = await ai_cost.budget_state()
    live = bool(cfg["enabled"]) and has_key and not mock and not budget["exceeded"]
    return {"chat_enabled": bool(cfg["enabled"]) and (mock or (has_key and not budget["exceeded"])),
            "config_enabled": bool(cfg["enabled"]), "has_key": has_key, "narrative_ai": live, "budget": budget,
            "mock": mock, "model": cfg["model_main"], "sales_definition": pol["sales_definition"],
            "sales_attribution": pol["sales_attribution"],
            # PR-T2 — dari izin peran (Peran & Hak Akses › Asisten Tanya KN), bukan daftar peran di pengaturan.
            "can_view_margin": await has_permission(user, "ai", "view_margin"),
            "can_view_stock_value": await has_permission(user, "ai", "view_stock_value"),
            "can_edit_rules": await has_permission(user, "ai", "manage"),
            # AG-T2 (K-45) — mode Keuangan: izin `ai_finance.view` DAN sakelar akun yang dinyalakan pemilik.
            "finance_enabled": await finance_enabled(user)}


async def finance_enabled(user: Dict[str, Any]) -> bool:
    return bool((user.get("ai_finance") or {}).get("enabled")) and await has_permission(user, "ai_finance", "view")


async def _session_context(user, ctx, *, masked: bool = False) -> str:
    margin, stock = await has_permission(user, "ai", "view_margin"), await has_permission(user, "ai", "view_stock_value")
    now = now_wib()
    ents = [e async for e in db.business_entities.find({"id": {"$in": ctx.allowed_entity_ids}}, {"_id": 0, "id": 1, "short_name": 1})
            .sort("id", 1)]   # KN-E40 — urutan tetap supaya prefix cache tidak pecah
    name = {e["id"]: e.get("short_name") or e["id"] for e in ents}
    role = user.get("role")
    # AG-T2 (b) — cakupan "hanya miliknya" dari sifat peran (PR-T4), bukan nama peran `sales` (dulu `role == "sales"`).
    from services.data_scope import own_scoped
    own = own_scoped(user)
    # AG-T2 (AG-06) — penyamaran menyala: nama pengguna tidak dikirim ke penyedia model.
    who = "Pengguna" if masked else user.get("name")
    # KN-E40 — tanpa jam:menit (dulu cache pecah tiap menit); tanggal cukup untuk "hari ini".
    return (f"# KONTEKS SESI\nHari ini: {_HARI[now.weekday()]}, {now.day} {now.strftime('%m')}/{now.year} (WIB)\n"
            f"Pengguna: {who} · peran: {role} · lini produk: {', '.join(user.get('allowed_line_codes') or []) or 'semua'}\n"
            f"Entitas aktif: {name.get(ctx.active_entity_id, ctx.active_entity_id)} · boleh melihat: {', '.join(name.values())} · "
            f"mode: {'semua entitas' if getattr(ctx, 'view_all', False) else 'satu entitas'}\n"
            f"Hak data: margin={'ya' if margin else 'tidak'} · nilai stok={'ya' if stock else 'tidak'} · "
            f"hanya pelanggan sendiri={'ya' if own else 'tidak'}\nVersi: {VERSIONS}" + await _glossary())


async def _glossary() -> str:
    raw = str(await value_of("ai.glossary") or "")
    lines = [ln.strip() for ln in raw.splitlines() if "=" in ln and ln.split("=", 1)[0].strip()][:80]
    if not lines:
        return ""
    return "\n# KAMUS ISTILAH PERUSAHAAN (bahasa sehari-hari tim → arti)\n" + "\n".join(f"- {ln[:160]}" for ln in lines)


CONTEXT_TYPES = {"customer": ("Pelanggan", "id"), "product": ("Produk", "id"), "sales_order": ("Pesanan penjualan", "nomor"),
                 "purchase_order": ("Purchase order", "nomor"), "goods_receipt": ("Kedatangan barang (GRN)", "nomor"),
                 "sales_return": ("Retur penjualan", "nomor"), "purchase_return": ("Retur pembelian", "nomor"),
                 "vendor_bill": ("Tagihan supplier", "nomor"), "makloon_order": ("Order makloon", "nomor"),
                 # AG-T3 — tombol "Tanya soal layar ini" di layar keuangan (Buku Besar, Piutang, Kas & Bank, Tutup Buku)
                 "journal_entry": ("Jurnal", "nomor"), "ar_receipt": ("Piutang pelanggan", "id"),
                 "bank_line": ("Mutasi bank", "id"), "period": ("Periode tutup buku", "nomor")}


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


async def _load_chat_session(session_id: Optional[str], user, question: str, mode: str = "umum") -> Dict[str, Any]:
    if session_id:
        s = await db.ai_chat_sessions.find_one({"id": session_id, "user_id": user["id"]}, {"_id": 0})
        if s:
            return s
    s = {"id": new_id("aichat"), "user_id": user["id"], "title": question[:80], "turns": [], "items": [],
         "mode": mode, "created_at": now_iso(), "updated_at": now_iso()}
    await db.ai_chat_sessions.insert_one(dict(s))
    return s


async def _questions_today(user_id: str) -> int:
    return await db.ai_usage_log.count_documents({"user_id": user_id, "feature": "bi_chat",
                                                  "created_at": {"$gte": now_wib().replace(hour=0, minute=0).isoformat()}})


@dataclass
class _TurnState:
    """AG-T2 — keadaan satu giliran pengguna (mode, pintu aplikasi, penyamaran, aturan alat teks bebas)."""
    mode: str = "umum"
    api: Any = None
    masker: Any = None
    scope: Dict[str, Any] = field(default_factory=dict)
    free_text_seen: bool = False
    raw_results: List[Dict[str, Any]] = field(default_factory=list)
    question: str = ""   # AG-T3 — kalimat permintaan pengguna disimpan di kartu tindakan (`request`)

    @property
    def finance(self) -> bool:
        return self.mode == "keuangan"


async def chat_events(question: str, session_id: Optional[str], deep: bool, user, ctx,
                      context: Optional[Dict[str, Any]] = None, *, mode: str = "umum",
                      api: Any = None) -> AsyncIterator[Dict[str, Any]]:
    cfg = await chat_config()
    mode = mode if mode in MODES else "umum"
    session = await _load_chat_session(session_id, user, question, mode)
    prefix_ctx = context_prefix(context)
    turn_user = {"role": "user", "content": question, "at": now_iso(), **({"mode": mode} if mode != "umum" else {}),
                 **({"context": {k: str(context.get(k) or "")[:120] for k in ("type", "id", "label")}} if prefix_ctx else {})}
    allowed = await ai_templates.allowed_ids(user)   # PR-T2 — templat berizin, bukan nama peran
    # AG-T2 — mode Keuangan tidak dirutekan ke templat: angka harus datang dari alat yang memanggil layar.
    routed = None if (prefix_ctx or mode == "keuangan") else \
        ai_templates.route(question, allowed, int(await value_of("ai.route_threshold_pct") or 90))
    if routed:
        async for ev in _template_answer(routed, question, session, turn_user, user, ctx,
                                         f"Pertanyaan ini cocok dengan template \u201c{routed['title']}\u201d, jadi dijawab langsung tanpa AI."):
            yield ev
        return
    mock = _is_mock(cfg)
    provider = await ai_provider.active_provider() if cfg["enabled"] and not mock else None
    budget = await ai_cost.budget_state() if provider else {"exceeded": False}
    if not cfg["enabled"] or not (provider or mock) or budget["exceeded"]:
        text = ("Anggaran AI bulan ini sudah habis, jadi chat bebas dimatikan sampai bulan depan. " if budget["exceeded"] else
                "Asisten chat bebas belum aktif (menunggu kunci penyedia model dan persetujuan pengiriman data agregat). ") + \
            "Sementara itu, template laporan berikut bisa langsung menjawab tanpa AI:"
        sugg = ai_templates.suggest(question, allowed)
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
        tpl = next((t for t in ai_templates.suggest(question, allowed, n=50) if not any(p.get("required") for p in t["params"])), None)
        if not tpl:
            yield {"type": "done", "error": "Tidak ada laporan yang cocok untuk peran Anda.", "session_id": session["id"]}
            return
        await _finalize_usage(res_id, cfg["model_main"], {}, 0)
        async for ev in _template_answer(tpl, question, session, turn_user, user, ctx,
                                         f"[MODE UJI \u2014 jawaban tiruan tanpa penyedia model] Pertanyaan Anda dijawab dengan laporan \u201c{tpl['title']}\u201d."):
            yield ev
        return
    st = await _turn_state(mode, api, session, ctx)
    st.question = question
    sys_prompt = SYSTEM_PROMPT_V1 + ("\n\n" + FINANCE_PROMPT_V1 if st.finance else "")
    instructions = [sys_prompt, CATALOG_V1, await _session_context(user, ctx, masked=st.masker is not None)]
    q_model = st.masker.mask_text(question) if st.masker else question   # nama yang sudah dikenal sesi → kode
    items: List[Any] = _cap_history(list(session.get("items") or [])) + [{"role": "user", "content": prefix_ctx + q_model}]
    results: List[Dict[str, Any]] = []
    rids: List[str] = []
    usage_tot: Dict[str, int] = {}
    text, started, retried = "", time.perf_counter(), 0
    ver: Optional[Dict[str, Any]] = None
    try:
        async for ev in _model_loop(provider, cfg, deep, instructions, items, results, rids, usage_tot, user, ctx, session, st):
            if ev.get("type") == "_final":
                text = ev["text"]
            else:
                yield ev
        if st.finance:
            # AG-T2 — pemeriksa angka sebagai PENGHALANG: teks baru dikirim sesudah lolos; satu putaran ulang.
            yield {"type": "status", "text": "Memeriksa angka\u2026"}
            ver = verify(text, results, q_model)
            while not ver["ok"] and retried < FINANCE_VERIFY_RETRIES:
                retried += 1
                items += [{"role": "assistant", "content": text}, {"role": "user", "content": _retry_note(ver)}]
                async for ev in _model_loop(provider, cfg, deep, instructions, items, results, rids, usage_tot, user, ctx,
                                            session, st):
                    if ev.get("type") == "_final":
                        text = ev["text"]
                    else:
                        yield ev
                yield {"type": "status", "text": "Memeriksa angka\u2026"}
                ver = verify(text, results, q_model)
    finally:   # KN-E33 — dicatat walau klien memutus koneksi (CancelledError/GeneratorExit)
        await _finalize_usage(res_id, cfg["model_main"], usage_tot, int((time.perf_counter() - started) * 1000), provider)
    if not st.finance:
        items.append({"role": "assistant", "content": text})
        ver = verify(text, results, q_model)   # atas teks & hasil bersamaran (yang dilihat model)
        shown = st.masker.unmask(text) if st.masker else text
        if st.masker:   # AG-T2 (b) — nama samaran → nama asli sebelum dikirim ke layar; daftar tak cocok ikut dipulihkan
            ver = {**ver, "unmatched": [st.masker.unmask(u) for u in ver["unmatched"]]}
        await _append(session, [turn_user, {"role": "assistant", "content": shown, "verification": ver, "usage": usage_tot,
                                            "result_ids": rids, "at": now_iso()}], items, replace_items=True,
                      extra_set={"alias_map": st.masker.export()} if st.masker else None)
        yield {"type": "done", "verification": ver, "usage": usage_tot, "session_id": session["id"], "result_ids": rids, "text": shown}
        return
    replaced = not ver["ok"]
    if replaced:
        text = FINANCE_FALLBACK
    items.append({"role": "assistant", "content": text})
    shown = st.masker.unmask(text) if st.masker else text   # urutan: teks model → pemeriksa → kembalikan nama → kirim
    # Angka yang tidak cocok TIDAK ikut dikirim (tidak ada di event maupun riwayat sesi).
    v_out = {"ok": bool(ver["ok"]), "checked": ver["checked"], "unmatched_count": len(ver["unmatched"]),
             "retried": retried, "replaced": replaced}
    srcs = _sources(st)
    extra = {"mode": "keuangan", **({"alias_map": st.masker.export()} if st.masker else {})}
    await _append(session, [turn_user, {"role": "assistant", "content": shown, "verification": v_out, "usage": usage_tot,
                                        "result_ids": rids, "sources": srcs, "mode": "keuangan", "at": now_iso()}],
                  items, replace_items=True, extra_set=extra)
    yield {"type": "done", "mode": "keuangan", "verification": v_out, "sources": srcs, "entity_label": st.scope.get("label", ""),
           "usage": usage_tot, "session_id": session["id"], "result_ids": rids, "text": shown}


class _StreamUnmask:
    """AG-T2 (b) — teks mengalir: kode samaran (`PLG-001`) dikembalikan ke nama asli; potongan yang mungkin awal kode
    ditahan sampai potongan berikutnya (kode tidak pernah tampil terbelah)."""
    _TAIL = re.compile(r"[A-Z]{1,3}(?:-\d{0,5})?$")

    def __init__(self, masker) -> None:
        self.masker, self.buf = masker, ""

    def feed(self, text: str) -> str:
        s = self.buf + (text or "")
        m = self._TAIL.search(s)
        cut = m.start() if m else len(s)
        self.buf = s[cut:]
        return self.masker.unmask(s[:cut])

    def flush(self) -> str:
        s, self.buf = self.buf, ""
        return self.masker.unmask(s)


def _retry_note(ver: Dict[str, Any]) -> str:
    return ("[Pemeriksa angka] Angka berikut tidak ada di hasil alat: " + ", ".join(ver["unmatched"][:20]) +
            ". Tulis ulang jawaban hanya dengan angka yang ada di hasil alat (pakai `totals`); jangan menghitung sendiri.")


async def _turn_state(mode: str, api: Any, session: Dict[str, Any], ctx) -> _TurnState:
    from entity_scope import scope_meta
    from services import ai_privacy
    st = _TurnState(mode=mode, api=api)
    # AG-T2 (b) — penyamaran berlaku di kedua mode (dulu hasil alat mode umum terkirim apa adanya, AG-06).
    st.scope = await scope_meta(ctx)
    st.masker = await ai_privacy.masker_for(session, st.scope.get("entity_ids") or [ctx.active_entity_id])
    return st


def _sources(st: _TurnState) -> List[Dict[str, Any]]:
    """AG-T2 — sumber jawaban disusun server dari hasil alat giliran itu (bukan dari teks model)."""
    from services.ai_finance_tools import COMBINED_NOTE
    out: List[Dict[str, Any]] = []
    combined = st.scope.get("mode") == "combined"
    for res in st.raw_results:
        for r in [res] + list((res.get("sections") or {}).values()):
            if not isinstance(r, dict) or not r.get("result_id"):
                continue
            notes = list(r.get("notes") if r.get("notes") is not None else (r.get("warnings") or []))
            if combined and COMBINED_NOTE not in notes:
                notes.insert(0, COMBINED_NOTE)
            out.append({"result_id": r["result_id"], "title": r.get("title") or "",
                        "entity_label": r.get("entity_label") or st.scope.get("label") or "",
                        "period_label": r.get("period_label") or (r.get("period") or {}).get("label") or "",
                        "notes": notes, "link": r.get("link")})
    return out



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


async def _finalize_usage(rid: str, model: str, usage: Dict[str, int], latency_ms: int, provider=None) -> None:
    price = provider.price_of(model) if provider else None
    await db.ai_usage_log.update_one({"id": rid}, {"$set": {
        "usage": usage, "cost_usd": ai_cost.cost_usd(model, usage, price), "latency_ms": latency_ms, "status": "done"}})


async def _turn_events(provider, **kw) -> AsyncIterator[Dict[str, Any]]:
    """AG-T1 — satu giliran model; potongan teks diteruskan sebagai event `delta` SELAGI giliran berjalan (bentuk event
    SSE sama dengan sebelum lapisan penyedia). Event terakhir `{"type": "_turn", "turn": ModelTurn}`."""
    q: asyncio.Queue = asyncio.Queue()

    async def on_text(t: str) -> None:
        q.put_nowait(t)

    task = asyncio.ensure_future(provider.run_turn(on_text=on_text, **kw))
    try:
        while not task.done() or not q.empty():
            if not q.empty():
                yield {"type": "delta", "text": q.get_nowait()}
                continue
            getter = asyncio.ensure_future(q.get())
            await asyncio.wait({task, getter}, return_when=asyncio.FIRST_COMPLETED)
            if getter.done():
                yield {"type": "delta", "text": getter.result()}
            else:
                getter.cancel()
        yield {"type": "_turn", "turn": task.result()}
    finally:   # klien memutus koneksi → giliran yang masih berjalan dihentikan
        if not task.done():
            task.cancel()


async def _model_loop(provider, cfg, deep, instructions, items, results, rids, usage_tot, user, ctx, session,
                      st: Optional[_TurnState] = None):
    st = st or _TurnState()
    stream = STREAM_BY_MODE.get(st.mode, True)
    tools = TOOLS_V1 + TOOLS_FIN_V1 + TOOLS_ACT_V1 if st.finance else TOOLS_V1
    text = ""
    for _ in range(int(cfg["max_tool_rounds"] or 6)):
        yield {"type": "status", "text": "Menganalisis pertanyaan…" if not results else "Menyusun jawaban…"}
        turn, streamed = None, False
        unmask_buf = _StreamUnmask(st.masker) if st.masker else None
        async for ev in _turn_events(provider, model=cfg["model_main"], instructions=instructions, tools=tools,
                                     conversation=items, effort=cfg["deep_effort"] if deep else cfg["reasoning_effort"],
                                     max_output_tokens=int(cfg["max_output_tokens"] or 4000)):
            if ev["type"] == "_turn":
                turn = ev["turn"]
                if stream and unmask_buf is not None:
                    rest = unmask_buf.flush()
                    if rest:
                        yield {"type": "delta", "text": rest}
            elif stream:   # AG-T2 — mode Keuangan: teks model tidak dialirkan sebelum diperiksa
                streamed = True
                if unmask_buf is not None:   # AG-T2 (b) — kode samaran dikembalikan ke nama asli SELAGI mengalir
                    part = unmask_buf.feed(ev["text"])
                    if part:
                        yield {"type": "delta", "text": part}
                else:
                    yield ev
        for k, v in (turn.usage or {}).items():
            usage_tot[k] = usage_tot.get(k, 0) + int(v or 0)
        items += list(turn.carry)
        if not turn.tool_calls:
            text = turn.text or ""
            break
        if streamed:
            yield {"type": "delta_reset"}
        for c in turn.tool_calls:
            args = st.masker.unmask_obj(c.arguments) if st.masker else c.arguments   # kode samaran → nama asli
            yield {"type": "status", "text": f"Mengambil data ({TOOL_STATUS_LABEL.get(c.name, 'data')})…"}
            yield {"type": "tool", "name": c.name, "arguments": args}
            res = await _run_tool(c.name, args, user, ctx, session, st)
            st.raw_results.append(res)
            to_model = st.masker.mask(res) if st.masker else res
            results.append(to_model)
            for r in [res] + list((res.get("sections") or {}).values()):
                if r.get("result_id"):
                    rids.append(r["result_id"])
                    yield {"type": "result", "result_id": r["result_id"], "title": r.get("title")}
            items.append(ai_provider.tool_result(c.id, json.dumps(_trim(to_model, int(cfg["result_rows_to_model"] or 50)),
                                                                  ensure_ascii=False, default=str)))
    yield {"type": "_final", "text": text}


async def _run_tool(name: str, args: Dict[str, Any], user, ctx, session, st: _TurnState) -> Dict[str, Any]:
    """Satu panggilan alat. Mode Keuangan (AG-T2): alat `fin_*` lewat pintu aplikasi sendiri; alat tindakan ditolak
    sesudah alat teks bebas dipakai pada giliran ini; teks bebas dibungkus penanda data; gaji selalu dibuang."""
    from services.ai_privacy import drop_salary
    if not st.finance:
        from services import ai_self_api
        tok = ai_self_api.bind(st.api) if st.api is not None else None   # laporan keuangan `run_report` lewat pintu ini
        try:
            return drop_salary(await ai_tools.execute(name, args, user, ctx, session["id"]))
        finally:
            if tok is not None:
                ai_self_api.unbind(tok)
    from services import ai_finance_tools as fin
    if name in ACTION_TOOLS and st.free_text_seen:
        return {"error": ACTION_BLOCKED}
    if name == "prepare_action":   # AG-T3 — kartu disiapkan; giliran model berhenti di sini (menyetujui = layar)
        from fastapi import HTTPException
        from services import ai_cards
        try:
            card = await ai_cards.prepare(str(args.get("action") or ""), args.get("args") or {}, api=st.api, user=user,
                                          ctx=ctx, session_id=session["id"], user_request=st.question)
        except HTTPException as exc:
            return {"error": str(exc.detail)}
        return ai_cards.tool_result(card)
    if name in fin.TOOLS:
        res = await fin.execute(name, args, fin.FinCall(api=st.api, user=user, ctx=ctx, session_id=session["id"],
                                                        scope=st.scope))
    else:
        res = await ai_tools.execute(name, args, user, ctx, session["id"])
        if name in fin.FREE_TEXT_TOOLS:
            res = fin.wrap_free_text(res)
    if name in fin.FREE_TEXT_TOOLS:
        st.free_text_seen = True
    return drop_salary(res)


async def _template_answer(tpl, question, session, turn_user, user, ctx, lead: str) -> AsyncIterator[Dict[str, Any]]:
    """Jawaban chat dari template (routing F5 / mode uji): angka server, blok kn-*, narasi otomatis."""
    yield {"type": "status", "text": f"Menjalankan {tpl['title']}\u2026"}
    out = await ai_templates.run(tpl["id"], {}, user, ctx, session["id"])
    rids = list(out["results"])
    for rid, r in out["results"].items():
        yield {"type": "result", "result_id": rid, "title": r.get("title")}
    blocks = [f"```kn-{'chart' if b['kind'] == 'chart' else 'table'}\n{json.dumps(b, ensure_ascii=False)}\n```"
              for b in out["blocks"] if b["kind"] in ("chart", "table")]
    allowed = await ai_templates.allowed_ids(user)
    follow = json.dumps([t["title"] for t in ai_templates.suggest(question, allowed, n=4) if t["id"] != tpl["id"]][:3],
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
    provider = await ai_provider.active_provider()
    if provider is None or (await ai_cost.budget_state())["exceeded"]:
        return {"scanned": 0, "created": 0, "detail": "Dilewati (tanpa kunci atau anggaran habis)"}
    usage = await provider.prewarm(model=cfg["model_main"], instructions=[SYSTEM_PROMPT_V1, CATALOG_V1], tools=TOOLS_V1)
    await db.ai_usage_log.insert_one({"id": new_id("aiu"), "feature": "bi_prewarm", "model": cfg["model_main"], "usage": usage,
                                      "cost_usd": ai_cost.cost_usd(cfg["model_main"], usage, provider.price_of(cfg["model_main"])),
                                      "created_at": now_wib().isoformat()})
    return {"scanned": 1, "created": 0, "detail": f"Prefix dipanaskan ({usage['input_tokens']} token)"}


async def _append(session, turns, items, replace_items: bool = False, extra_set: Optional[Dict[str, Any]] = None) -> None:
    upd: Dict[str, Any] = {"$push": {"turns": {"$each": turns}}, "$set": {"updated_at": now_iso(), **(extra_set or {})}}
    if replace_items:
        upd["$set"]["items"] = items
    await db.ai_chat_sessions.update_one({"id": session["id"]}, upd)
