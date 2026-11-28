"""Kas & Bank bagian 4 (C8) — buku pembantu uang muka pemasok per PT, penahan pindah saldonya, dan daftar uang muka
terbuka (karyawan & pemasok) dibanding saldo akunnya.

Rancangan: `docs/superpowers/specs/2026-11-28-kas-bank-4-uang-muka-design.md` §5.4, §5.5, §7.9.1, §7.9.2.

* **Buku pembantu** (`subledger`, §7.9.1) — dihitung dari DOKUMEN PT itu, per pemasok, hanya yang jurnalnya sudah terbit
  (dan tidak dibalik): kas `ap_advance` PT itu (kelebihan bayar tagihan & keputusan selisih bayar "jadi uang muka")
  − potongan kontrabon `supplier_advance` yang SUDAH terjurnal + kasus "lebih bayar pemasok" aksi `uang_muka_supplier`
  − pengembalian dana kasus aksi `terima_refund_supplier`. Ini sumber yang sama dengan jurnal yang menyentuh akun uang muka
  pemasok (`gl_service.akun_uang_muka_pemasok`), jadi sesudah PT pindah: saldo akun uang muka pemasok = total buku
  pembantu. `suppliers.advance_balance` (satu angka per pemasok untuk SEMUA PT, tidak turun oleh potongan kontrabon) hanya
  keterangan (`advance_balance_info`), bukan penahan.
* **Penahan** (`penahan`, §7.9.2) — dokumen uang muka pemasok PT itu yang jurnalnya belum terbit (kontrabon belum dibayar
  yang memuat potongan uang muka, jurnal potongan gagal, kas uang muka yang jurnalnya gagal/tertunda/sedang dibatalkan,
  penyelesaian kasus yang belum tuntas) dan baris pemasok bernilai negatif ("periksa kasus"). Selama ada penahan, pindah
  saldo tidak bisa disiapkan atau disetujui.
* **Uang muka terbuka** (`uang_muka_terbuka`, §5.5; baca saja) — karyawan: PD terbuka per pemegang (cair belum di-LPJ,
  atau sisa LPJ yang belum kembali) dibanding saldo akun uang muka karyawan (1-1400); pemasok: buku pembantu dibanding saldo
  akun uang muka pemasok PT (PT sudah pindah), atau digabung ke 1-1400 dengan catatan (PT belum pindah). Dipakai layar
  dan butir tutup buku `uang_muka_cocok`.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from core_utils import from_cents, rupiah, to_cents
from db import db

AKSI_UANG_MUKA = "uang_muka_supplier"       # kasus "lebih bayar pemasok" → uang muka (Dr uang muka / Cr 2-1100)
AKSI_REFUND = "terima_refund_supplier"      # kasus → pemasok mengembalikan uang (Dr kas / Cr uang muka)
KOLOM = ("dari_kas", "dipotong_terjurnal", "dari_kasus", "refund_kasus")
TANDA = {"dari_kas": 1, "dipotong_terjurnal": -1, "dari_kasus": 1, "refund_kasus": -1}

KET_1400_BIAYA = "Akun ini juga memuat biaya dibayar dimuka; selisih sebesar biaya dibayar dimuka itu wajar."
KET_1400_PEMASOK = ("Akun ini masih memuat uang muka pemasok sampai PT ini memindah saldonya ke akun Uang Muka "
                    "Pemasok (Pindah saldo uang muka pemasok).")


async def _jurnal(source_type: str, source_id: str) -> Optional[Dict[str, Any]]:
    return await db.journal_entries.find_one({"source_type": source_type, "source_id": source_id,
                                              "status": {"$ne": "void"}}, {"_id": 0})


async def _keadaan(je: Optional[Dict[str, Any]]) -> str:
    """Keadaan jurnal dokumen: `terjurnal` (masuk buku pembantu), `dibalik` (bersih nol, dilewati), `tertunda` (belum
    terbit / sedang dibalik → penahan)."""
    from services import gl_service as gl
    if not je or je.get("reversed_by_entry_id") == "pending":
        return "tertunda"
    return "dibalik" if await gl.reversal_of(je) else "terjurnal"


async def _baca(entity_id: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, str]]:
    """Semua dokumen uang muka pemasok PT itu → (gerak `[{supplier_id, kolom, sen}]` yang terjurnal, tertunda `[{jenis,
    nomor, kalimat}]`, nama pemasok dari dokumen `{supplier_id: nama}`)."""
    gerak: List[Dict[str, Any]] = []
    tertunda: List[Dict[str, Any]] = []
    nama: Dict[str, str] = {}

    def catat(sid: str, kolom: str, sen: int) -> None:
        if sen:
            gerak.append({"supplier_id": sid or "", "kolom": kolom, "sen": sen})

    # (1) Kas `ap_advance` — kelebihan bayar tagihan PT itu (juga keputusan selisih bayar "jadi uang muka").
    kas = [t async for t in db.cash_transactions.find(
        {"ref_type": "ap_advance", "entity_id": entity_id, "status": {"$ne": "void"}},
        {"_id": 0, "id": 1, "number": 1, "ref_id": 1, "ref_number": 1, "amount": 1, "voiding": 1,
         "counterparty_name": 1})]
    tagihan = {b["id"]: b async for b in db.vendor_bills.find(
        {"id": {"$in": sorted({t.get("ref_id") or "" for t in kas})}},
        {"_id": 0, "id": 1, "supplier_id": 1, "supplier_name": 1, "bill_number": 1})}
    for t in kas:
        b = tagihan.get(t.get("ref_id") or "") or {}
        sid = b.get("supplier_id") or ""
        nama.setdefault(sid, b.get("supplier_name") or t.get("counterparty_name") or "")
        keadaan = "tertunda" if t.get("voiding") else await _keadaan(await _jurnal("cash_transaction", t["id"]))
        if keadaan == "terjurnal":
            catat(sid, "dari_kas", to_cents(t.get("amount")))
        elif keadaan == "tertunda":
            nomor = t.get("number") or t["id"]
            tertunda.append({"jenis": "kas_tertunda", "nomor": nomor, "kalimat": (
                f"Jurnal kas uang muka pemasok {nomor} ({rupiah(t.get('amount'))}, tagihan "
                f"{t.get('ref_number') or b.get('bill_number') or '—'}) belum terbit atau sedang dibatalkan. Ulangi di "
                "Keuangan › Posting Gagal, atau tunggu pembatalannya selesai.")})

    # (2) Potongan kontrabon `supplier_advance` PT itu — masuk buku pembantu hanya bila jurnal potongannya terbit
    #     (jurnal Cr uang muka terbit saat kontrabon dibayar, `ap_payment_service._post_journals`).
    async for cb in db.contra_bons.find({"entity_id": entity_id, "deductions.kind": "supplier_advance"},
                                        {"_id": 0, "id": 1, "number": 1, "status": 1, "supplier_id": 1,
                                         "supplier_name": 1, "deductions": 1}):
        sid = cb.get("supplier_id") or ""
        nama.setdefault(sid, cb.get("supplier_name") or "")
        for d in cb.get("deductions") or []:
            sen = to_cents(d.get("amount"))
            if d.get("kind") != "supplier_advance" or not d.get("posts_gl") or sen <= 0:
                continue
            keadaan = await _keadaan(await _jurnal("contra_bon_deduction", f"{cb['id']}:{d.get('id')}"))
            if keadaan == "terjurnal":
                catat(sid, "dipotong_terjurnal", sen)
            elif keadaan == "tertunda" and cb.get("status") != "cancelled":
                nomor = cb.get("number") or cb["id"]
                if d.get("applied_at") or cb.get("status") == "paid":
                    tertunda.append({"jenis": "potongan_gagal", "nomor": nomor, "kalimat": (
                        f"Jurnal potongan uang muka pemasok {rupiah(from_cents(sen))} kontrabon {nomor} belum terbit. "
                        "Ulangi di Keuangan › Posting Gagal.")})
                else:
                    tertunda.append({"jenis": "kontrabon_belum_dibayar", "nomor": nomor, "kalimat": (
                        f"Kontrabon {nomor} ({cb.get('supplier_name') or 'pemasok'}) memuat potongan uang muka pemasok "
                        f"{rupiah(from_cents(sen))} yang belum dibayar. Bayar atau batalkan kontrabonnya dulu.")})

    # (3) Kasus "lebih bayar pemasok" PT itu — uang muka (jurnal `finance_case` `{kasus}:ap_adv…`) dan pengembalian dana
    #     (kas masuk `ref_type=finance_case`).
    async for c in db.finance_cases.find(
            {"entity_id": entity_id, "$or": [{"resolution_intent.action": {"$in": [AKSI_UANG_MUKA, AKSI_REFUND]}},
                                             {"resolution.action": {"$in": [AKSI_UANG_MUKA, AKSI_REFUND]}}]},
            {"_id": 0, "id": 1, "number": 1, "supplier_id": 1, "resolution_intent": 1, "resolution": 1}):
        niat = c.get("resolution_intent") or {}
        aksi = niat.get("action") or (c.get("resolution") or {}).get("action") or ""
        sid = (niat.get("payload") or {}).get("supplier_id") or c.get("supplier_id") or ""
        nomor = c.get("number") or c["id"]
        if niat.get("status") == "pending":
            tertunda.append({"jenis": "kasus_tertunda", "nomor": nomor, "kalimat": (
                f"Penyelesaian kasus {nomor} (uang muka pemasok) belum tuntas — jurnalnya belum terbit. Ulangi di "
                "Keuangan › Posting Gagal.")})
            continue
        if aksi == AKSI_UANG_MUKA:
            jes = await db.journal_entries.find(
                {"source_type": "finance_case", "source_id": {"$regex": f"^{re.escape(c['id'])}:ap_adv(:|$)"},
                 "entity_id": entity_id, "status": {"$ne": "void"}}, {"_id": 0}).to_list(20)
            for je in jes:
                if await _keadaan(je) == "terjurnal":
                    catat(sid, "dari_kasus", to_cents(je.get("total_debit")))
        else:
            async for t in db.cash_transactions.find(
                    {"ref_type": "finance_case", "ref_id": c["id"], "direction": "in", "entity_id": entity_id,
                     "status": {"$ne": "void"}}, {"_id": 0, "id": 1, "amount": 1, "voiding": 1}):
                if not t.get("voiding") and await _keadaan(await _jurnal("cash_transaction", t["id"])) == "terjurnal":
                    catat(sid, "refund_kasus", to_cents(t.get("amount")))
    return gerak, tertunda, nama


def _baris(gerak: List[Dict[str, Any]], nama: Dict[str, str]) -> List[Dict[str, Any]]:
    per: Dict[str, Dict[str, int]] = {}
    for g in gerak:
        per.setdefault(g["supplier_id"], {k: 0 for k in KOLOM})[g["kolom"]] += g["sen"]
    out = []
    for sid, sen in per.items():
        sisa = sum(TANDA[k] * v for k, v in sen.items())
        out.append({"supplier_id": sid, "nama": nama.get(sid) or "", "_sisa": sisa,
                    **{k: from_cents(v) for k, v in sen.items()}, "sisa": from_cents(sisa)})
    out.sort(key=lambda r: ((r["nama"] or "").lower(), r["supplier_id"]))
    return out


async def subledger(entity_id: str) -> Dict[str, Any]:
    """Buku pembantu uang muka pemasok PT `entity_id` (§7.9.1). → `{baris: [{supplier_id, nama, dari_kas,
    dipotong_terjurnal, dari_kasus, refund_kasus, sisa}], total, advance_balance_info: [{supplier_id, nama,
    advance_balance, sisa, kalimat}]}` — `advance_balance_info` = pemasok yang saldo kartunya (`advance_balance`, semua PT)
    berbeda dengan buku pembantu PT ini (keterangan saja)."""
    gerak, _tertunda, nama = await _baca(entity_id)
    return await _susun(gerak, nama)


async def _susun(gerak: List[Dict[str, Any]], nama: Dict[str, str]) -> Dict[str, Any]:
    baris = _baris(gerak, nama)
    kartu = {s["id"]: s async for s in db.suppliers.find({"id": {"$in": [r["supplier_id"] for r in baris]}},
                                                        {"_id": 0, "id": 1, "name": 1, "advance_balance": 1})}
    info = []
    for r in baris:
        s = kartu.get(r["supplier_id"]) or {}
        r["nama"] = s.get("name") or r["nama"] or r["supplier_id"] or "(pemasok tanpa kartu)"
        if s and to_cents(s.get("advance_balance")) != r["_sisa"]:
            info.append({"supplier_id": r["supplier_id"], "nama": r["nama"],
                         "advance_balance": from_cents(to_cents(s.get("advance_balance"))), "sisa": r["sisa"],
                         "kalimat": (f"Saldo uang muka di kartu pemasok {r['nama']} {rupiah(s.get('advance_balance'))} "
                                     f"(semua PT, tidak berkurang oleh potongan kontrabon) berbeda dengan buku pembantu "
                                     f"PT ini {rupiah(r['sisa'])} — hanya keterangan.")})
    total = sum(r.pop("_sisa") for r in baris)
    return {"baris": baris, "total": from_cents(total), "advance_balance_info": info}


async def penahan(entity_id: str) -> List[Dict[str, Any]]:
    """Penahan pindah saldo uang muka pemasok PT `entity_id` (§7.9.2) → `[{jenis, nomor, kalimat}]` (kosong = boleh):
    dokumen yang jurnal uang mukanya belum terbit (`kontrabon_belum_dibayar`, `potongan_gagal`, `kas_tertunda`,
    `kasus_tertunda`) dan pemasok bernilai negatif (`baris_negatif`)."""
    hasil = await bacaan_pindah(entity_id)
    return hasil["penahan"]


async def bacaan_pindah(entity_id: str) -> Dict[str, Any]:
    """Satu bacaan untuk pratinjau pindah saldo: buku pembantu + penahan (dokumen dibaca sekali)."""
    gerak, tertunda, nama = await _baca(entity_id)
    sl = await _susun(gerak, nama)
    negatif = [{"jenis": "baris_negatif", "nomor": r["nama"], "kalimat": (
        f"Uang muka pemasok {r['nama']} di PT ini bernilai negatif ({rupiah(r['sisa'])}) — periksa kasus "
        "pengembalian dana dan potongan kontrabon pemasok itu (mungkin uang mukanya tercatat di PT lain).")}
        for r in sl["baris"] if to_cents(r["sisa"]) < 0]
    return {**sl, "penahan": tertunda + negatif}


# ── Uang muka terbuka (karyawan & pemasok) vs saldo akun ─────────────────────────────────────────────────────────────
def _pemegang(pd: Dict[str, Any]) -> Dict[str, str]:
    """Pemegang uang PD: bidang `pemegang` (Kas & Bank 4 Tugas 2) bila ada, selain itu pembuat PD."""
    p = pd.get("pemegang") or {}
    if p.get("id") or p.get("nama"):
        return {"jenis": p.get("jenis") or "pengguna", "id": p.get("id") or "", "nama": p.get("nama") or ""}
    return {"jenis": "pengguna", "id": pd.get("created_by_id") or "", "nama": pd.get("created_by") or ""}


async def pd_terbuka(entity_id: str) -> List[Dict[str, Any]]:
    """PD PT itu yang uangnya masih di tangan pemegang (yang tersisa di akun uang muka karyawan): dicairkan dan LPJ-nya
    belum terjurnal (sisa = nominal cair), atau LPJ terjurnal dengan sisa yang belum dikembalikan (open/returning)."""
    pds = [p async for p in db.cash_advances.find({"entity_id": entity_id, "status": {"$in": ["disbursed", "settled"]}},
                                                  {"_id": 0})]
    lpj = {s.get("cash_advance_id"): s async for s in db.cash_advance_settlements.find(
        {"cash_advance_id": {"$in": [p["id"] for p in pds]}, "status": "posted_to_gl"}, {"_id": 0})}
    out = []
    for p in pds:
        cair = to_cents((p.get("disbursement") or {}).get("amount") or p.get("total_amount"))
        s = lpj.get(p["id"])
        if s:
            sr = s.get("sisa_dikembalikan") or {}
            sisa = to_cents(sr.get("amount")) if sr.get("status") in ("open", "returning") else 0
        elif p.get("status") == "disbursed":
            sisa = cair
        else:
            sisa = 0
        if sisa <= 0:
            continue
        out.append({"id": p["id"], "number": p.get("number", ""), "kegiatan": p.get("kegiatan", ""),
                    "status": p.get("status", ""), "pemegang": _pemegang(p), "dicairkan": from_cents(cair),
                    "dipertanggungjawabkan": from_cents(cair - sisa) if s else 0.0, "sisa": from_cents(sisa),
                    "lpj_number": (s or {}).get("number", ""), "lpj_jatuh_tempo": p.get("lpj_jatuh_tempo") or "",
                    "_sen": sisa})
    out.sort(key=lambda r: (r["pemegang"]["nama"].lower(), r["number"]))
    return out


async def uang_muka_terbuka(entity_id: str) -> Dict[str, Any]:
    """`GET /api/uang-muka/terbuka?entity_id=` — daftar uang muka terbuka PT itu dibanding saldo akunnya (keadaan hari
    ini). → `{entity_id, pt, pemasok_pindah, aktif_sejak, karyawan: {pemegang: [{pemegang, pd, total}], total},
    pemasok: {baris, total, advance_balance_info, akun}, akun: [{akun, nama, saldo, daftar, selisih, isi, keterangan}]}`.
    PT belum pindah: satu baris akun 1-1400 dengan daftar = karyawan + pemasok (+ catatan); sudah pindah: 1-1400 vs
    karyawan dan akun uang muka pemasok vs buku pembantu."""
    from services import gl_mapping_service as glm
    from services import gl_service as gl
    from services import supplier_advance_mode as mode
    from services.cash_ledger import _nama_pt
    pds = await pd_terbuka(entity_id)
    per: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for p in pds:
        k = (p["pemegang"]["jenis"], p["pemegang"]["id"] or p["pemegang"]["nama"])
        g = per.setdefault(k, {"pemegang": p["pemegang"], "pd": [], "_sen": 0})
        g["_sen"] += p["_sen"]
        g["pd"].append({x: v for x, v in p.items() if x != "_sen"})
    kelompok = [{"pemegang": g["pemegang"], "pd": g["pd"], "total": from_cents(g["_sen"])} for g in per.values()]
    sen_karyawan = sum(p["_sen"] for p in pds)
    sl = await subledger(entity_id)
    sen_pemasok = to_cents(sl["total"])
    pindah = await mode.aktif(entity_id)
    kode_k = await glm.account_for("kas_bank.uang_muka_karyawan", entity_id)
    kode_p = await glm.account_for("hutang.uang_muka_pemasok", entity_id)
    nama_akun = await gl.effective_accounts([kode_k, kode_p], entity_id)
    saldo_k = await gl.accounts_balance_cents(await glm.known_codes("kas_bank.uang_muka_karyawan", entity_id),
                                              entity_id)

    def baris(kode: str, saldo: int, daftar: int, isi: List[str], ket: List[str]) -> Dict[str, Any]:
        return {"akun": kode, "nama": (nama_akun.get(kode) or {}).get("name", ""), "saldo": from_cents(saldo),
                "daftar": from_cents(daftar), "selisih": from_cents(saldo - daftar), "isi": isi,
                "keterangan": " ".join(ket)}

    if pindah:
        saldo_p = await gl.accounts_balance_cents(await glm.known_codes("hutang.uang_muka_pemasok", entity_id),
                                                  entity_id)
        akun = [baris(kode_k, saldo_k, sen_karyawan, ["karyawan"], [KET_1400_BIAYA]),
                baris(kode_p, saldo_p, sen_pemasok, ["pemasok"], [])]
        akun_pemasok = kode_p
    else:
        akun = [baris(kode_k, saldo_k, sen_karyawan + sen_pemasok, ["karyawan", "pemasok"],
                      [KET_1400_PEMASOK, KET_1400_BIAYA])]
        akun_pemasok = kode_k
    return {"entity_id": entity_id, "pt": await _nama_pt(entity_id), "pemasok_pindah": pindah,
            "aktif_sejak": await mode.aktif_sejak(entity_id),
            "karyawan": {"pemegang": kelompok, "total": from_cents(sen_karyawan), "akun": kode_k},
            "pemasok": {**sl, "akun": akun_pemasok}, "akun": akun}
