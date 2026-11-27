"""Kas & Bank bagian 1 (D1 aktif + D4) — alat pindah saldo per PT: pratinjau, siapkan, setujui, tolak.

Rancangan: `docs/superpowers/specs/2026-11-27-kas-bank-1-rekening-pindah-dana-design.md` §5.3, §6, §7 butir 8 (2–5).

* **Pratinjau** (`pratinjau`, tanpa tulisan) — untuk tiap rekening PT: akun tujuan (akun rekening yang sudah ada, atau
  perkiraan sub-akun yang akan dibuat), saldo buku kas rekening (`bank_service.account_ledger`), dan DARI AKUN MANA
  saldonya dipindah. Asal dihitung dari baris jurnal yang benar-benar terbit untuk kas rekening itu: jurnal saldo awal
  rekening, dan baris kas lama yang dipasangkan ke dokumen kasnya dengan aturan yang SAMA dengan pembalik kas lama
  Tugas 2 (`gl_service.kas_jurnal` + `pasang_baris_kas`; ketetapan R8b) — jadi saldo yang dipindah tepat sama dengan
  baris yang kelak dialihkan pembaliknya ke akun rekening. Kas lama tanpa rekening ikut rekening TUNGGAL jenis kasnya
  (`bank_service.sole_account_id`, aturan buku kas rekening); selain itu tetap di akun lama. Jalur tanpa dokumen kas
  (penjualan tunai tanpa surat jalan, pelepasan aset, ongkir retur — R6) tidak pernah masuk buku kas rekening, jadi
  tetap di akun lama: terlihat di `akun_lama` (saldo, dipindah, sisa).
* **Siapkan** (`siapkan`) — ditolak bila PT sudah aktif, ada usulan yang menunggu, atau ada posting kas gagal/tertunda
  (`posting_tertunda`); membuat akun rekening (idempoten; akun bagan PT pilihan Finance boleh — butir 4, akun yang
  dipilih boleh berjurnal); menyimpan usulan `menunggu` di koleksi sendiri `cash_account_cutovers`.
* **Setujui** (`setujui`, orang kedua — `dual_control.tolak_bila_pelaku_sama("pindah_saldo_kas")`) — server menghitung
  ulang; sidik berbeda dari sidik yang dilihat penyetuju → 409 "Angka berubah, muat ulang." Lalu satu langkah berklaim
  (pola `interco_charge_service.settle` / `_lanjut_settle`: klaim bersyarat status + jatah waktu, niat tersimpan, jurnal
  tahan-gagal, ulang dari Posting Gagal meneruskan niat): akun rekening lengkap → periksa jurnal (akun, periode) →
  `cash_account_mode.nyalakan` → hitung ulang dengan batas waktu `aktif_sejak` → jurnal `pindah_saldo_kas` bertanggal
  hari persetujuan (WIB) → `account_id` kas lama tunggal → `disetujui`.

  Konsistensi dengan penanda waktu (ketetapan pengendali (a)): hitungan yang DIPOSTING dibuat SESUDAH `nyalakan`, dengan
  batas yang sama dengan aturan pembalik (`baris_kas_rekening`: jurnal & kas terbit sebelum `aktif_sejak`). Kas yang
  dijurnal sebelum penanda (masih ke akun lama) ikut dipindah; kas sesudah penanda langsung ke sub-akun. Tidak ada kas
  yang jatuh di luar kedua ember. Hitungan sebelum klaim hanya untuk membandingkan sidik; bila berbeda dari yang
  diposting (kas tercatat di antara keduanya), keduanya dicatat (`sidik_disetujui`, `sidik_diposting`).
* **Tolak** (`tolak`) — tidak ada yang berubah selain akun rekening yang sudah dibuat (tetap, kosong). Sebelum disetujui
  akun rekening bisa diganti lewat siapkan ulang (§7 butir 2: kode boleh diganti sebelum pindah saldo disetujui).

Tidak ada yang berjalan saat aplikasi menyala; tidak ada tanggal mundur.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from pymongo import ReturnDocument

from core_utils import now_iso, rupiah, safe_doc
from db import db

COLL = "cash_account_cutovers"
AKSI_KONTROL = "pindah_saldo_kas"
LEASE_MINUTES = 2   # jatah kerja satu persetujuan yang sedang berjalan; batas teknis, bukan aturan bisnis
STATUS_LABEL = {"menunggu": "Menunggu persetujuan", "memproses": "Sedang diproses", "disetujui": "Disetujui",
                "ditolak": "Ditolak"}
HIDUP = ("menunggu", "memproses")

PESAN_ANGKA_BERUBAH = "Angka berubah, muat ulang."
PESAN_TIDAK_ADA = "Usulan pindah saldo tidak ditemukan."
PESAN_SEDANG = "Pindah saldo {pt} sedang diproses. Tunggu sebentar lalu muat ulang."

#: Jenis Posting Gagal (`posting_registry.KINDS`) yang dokumennya membawa atau menumpangkan kas (ketetapan (b)): kas
#: sendiri, kwitansi, refund retur jual (nota kredit) & beli, perolehan aset ber-kas, pembatalan kwitansi (pembalik
#: kas), pelunasan antar-PT / tagihan insentif / pindah aset (kas kembar), setoran titipan tunai. Nilai = field PT yang
#: dibaca (bawaan `entity_field` registri; tagihan insentif: kedua pihak — kas kembar ada di kedua PT).
JENIS_POSTING_KAS: Dict[str, Tuple[str, ...]] = {
    "cash_transaction": (), "ar_receipt": (), "credit_note": (), "purchase_return": (), "fixed_asset": (),
    "ar_receipt_void": (), "interco_settlement_payer": (), "interco_settlement_payee": (),
    "interco_incentive_charge": ("to_entity_id", "from_entity_id"), "fixed_asset_settle_payer": (),
    "fixed_asset_settle_payee": (), "cash_deposit": (),
}
LABEL_TERTUNDA = {
    "kas_tertunda": "Transaksi kas yang jurnalnya belum selesai atau sedang dibatalkan",
    "pembalik_tertunda": "Jurnal yang sedang dibalik",
    "kas_tanpa_jurnal_induk": "Kas yang menunggu jurnal dokumen induknya",
    "gaji_jalur_lama": "Penggajian yang jurnal bayarnya sudah terbit tetapi kasnya belum tercatat",
}


def _galat(status: int, pesan: str) -> HTTPException:
    return HTTPException(status_code=status, detail=pesan)


def _sen(x: Any) -> int:
    return int(round(float(x or 0) * 100))


def _rp(sen: int) -> float:
    return round(sen / 100, 2)


def _lease_until() -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=LEASE_MINUTES)).isoformat()


async def _nama_pt(entity_id: str) -> str:
    from services.cash_ledger import _nama_pt as nama
    return await nama(entity_id)


async def _pt_ada(entity_id: str) -> None:
    if not entity_id or entity_id == "all":
        raise _galat(400, "Pilih satu PT untuk pindah saldo kas per rekening.")
    if not await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "id": 1}):
        raise _galat(404, "PT tidak ditemukan.")


# ── Posting kas gagal / tertunda ─────────────────────────────────────────────────────────────────────────────────────
async def posting_tertunda(entity_id: str) -> Tuple[int, List[Dict[str, Any]]]:
    """Jumlah posting kas yang gagal atau tertunda di PT itu + rinciannya `[{jenis, label, jumlah}]`.

    * Baris panel Posting Gagal PT itu untuk jenis `JENIS_POSTING_KAS` (saringan `failed_query` registri);
    * kas yang jurnalnya masih `pending` atau sedang dibatalkan (`voiding`); jurnal yang sedang dibalik
      (`reversed_by_entry_id: "pending"`);
    * kas yang menumpang jurnal dokumen induk (`parent_journal`) yang belum terbit (`gl_service.jurnal_induk_kas`);
    * ketetapan R8a — proses gaji berstatus `posted`/`paying` yang jurnal `payroll_pay` jalur lamanya sudah terbit
      tetapi kas pembayarannya belum tercatat (kas yang kelak menumpang jurnal lama itu menurunkan buku kas rekening
      tanpa menyentuh akun rekening)."""
    from services import gl_service as gl
    from services import posting_registry as reg
    rincian: List[Dict[str, Any]] = []

    def catat(jenis: str, label: str, n: int) -> None:
        if n:
            rincian.append({"jenis": jenis, "label": label, "jumlah": int(n)})

    for kind, pihak in JENIS_POSTING_KAS.items():
        spec = reg.KINDS[kind]
        fields = pihak or (spec["entity_field"],)
        q = {"$and": [dict(spec["failed_query"]), {"$or": [{f: entity_id} for f in fields]}]}
        catat(kind, spec["label"], await db[spec["collection"]].count_documents(q))
    catat("kas_tertunda", LABEL_TERTUNDA["kas_tertunda"], await db.cash_transactions.count_documents(
        {"entity_id": entity_id, "status": {"$ne": "void"}, "$or": [{"gl_status": "pending"}, {"voiding": True}]}))
    catat("pembalik_tertunda", LABEL_TERTUNDA["pembalik_tertunda"], await db.journal_entries.count_documents(
        {"entity_id": entity_id, "reversed_by_entry_id": "pending"}))
    menumpang = [t async for t in db.cash_transactions.find(
        {"entity_id": entity_id, "status": {"$ne": "void"}, "gl_posted": True, "parent_journal": {"$nin": [None, ""]}},
        {"_id": 0, "id": 1, "entity_id": 1, "journal_entry_id": 1, "parent_journal": 1})]
    ids = {x for t in menumpang for x in (t.get("journal_entry_id"), t.get("parent_journal")) if x}
    ada = {j["id"] async for j in db.journal_entries.find({"id": {"$in": sorted(ids)}, "status": {"$ne": "void"}},
                                                          {"_id": 0, "id": 1})}
    n = 0
    for t in menumpang:
        if not ({t.get("journal_entry_id"), t.get("parent_journal")} & ada) and not await gl.jurnal_induk_kas(t):
            n += 1
    catat("kas_tanpa_jurnal_induk", LABEL_TERTUNDA["kas_tanpa_jurnal_induk"], n)
    n = 0
    async for run in db.hr_payroll_runs.find({"entity_id": entity_id, "status": {"$in": ["posted", "paying"]}},
                                             {"_id": 0}):
        je = await db.journal_entries.find_one(
            {"source_type": "payroll_pay", "source_id": await gl.payroll_source_id(run), "entity_id": entity_id,
             "status": {"$ne": "void"}}, {"_id": 0, "id": 1})
        if je and not await db.cash_transactions.find_one(
                {"status": {"$ne": "void"}, "$or": [{"ref_type": "payroll_run", "ref_id": run["id"]},
                                                    {"journal_entry_id": je["id"]}, {"parent_journal": je["id"]}]},
                {"_id": 0, "id": 1}):
            n += 1
    catat("gaji_jalur_lama", LABEL_TERTUNDA["gaji_jalur_lama"], n)
    return sum(x["jumlah"] for x in rincian), rincian


async def _tolak_bila_tertunda(entity_id: str) -> None:
    n, rincian = await posting_tertunda(entity_id)
    if n:
        isi = "; ".join(f"{x['label']}: {x['jumlah']}" for x in rincian)
        raise _galat(409, f"{await _nama_pt(entity_id)} masih punya {n} posting kas yang gagal atau tertunda ({isi}). "
                          f"Selesaikan dulu di Keuangan › Posting Gagal, lalu ulangi.")


# ── Hitungan (pratinjau) ─────────────────────────────────────────────────────────────────────────────────────────────
def _sidik(rekening: List[Dict[str, Any]], tunggal: List[Dict[str, Any]]) -> str:
    """Sidik angka: rekening, akun tujuan (sub-akun yang belum dibuat = "(baru)"), nominal per akun asal (sen), dan kas
    lama tanpa rekening yang ikut rekening tunggal. Berubah bila ada kas/jurnal baru sejak dimuat."""
    isi = {"rekening": [[r["id"], "(baru)" if r["akun_tujuan_baru"] else r["akun_tujuan"],
                         [[a["akun"], _sen(a["jumlah"])] for a in r["asal"]]] for r in rekening],
           "tunggal": sorted(i for g in tunggal for i in g["kas_ids"])}
    return hashlib.sha256(json.dumps(isi, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:24]


async def _hitung(entity_id: str, *, sejak: str = "") -> Dict[str, Any]:
    """Hitungan pindah saldo PT itu (tanpa tulisan). `sejak` (ISO) = batas waktu aturan pembalik: hanya jurnal & kas
    yang terbit SEBELUM-nya (dipakai saat disetujui, sesudah `nyalakan`); kosong = semuanya (pratinjau).

    `sumber` = baris jurnal yang dipindah `[{jenis: "saldo_awal"|"kas", journal_id, indeks, rekening_id, akun, sen}]`
    (bahan uji kesetaraan dengan `gl_service.baris_kas_rekening`)."""
    from services import bank_service as bs
    from services import cash_account_mode as mode
    from services import gl_service as gl
    from services import report_basis as rb
    reks = await bs.rekening_pt(entity_id)
    rek_by_id = {r["id"]: r for r in reks}
    lama = await rb.kode_kas(entity_id) - await gl.kode_akun_rekening(entity_id)
    # Kas lama tanpa rekening: ikut rekening TUNGGAL jenis kasnya (aturan buku kas rekening `_txns_for`), selain itu
    # tetap di akun lama.
    tunggal_kas: Dict[str, str] = {}
    tunggal: List[Dict[str, Any]] = []
    tetap: List[Dict[str, Any]] = []
    for ct in ("kas_besar", "kas_kecil"):
        q: Dict[str, Any] = {"entity_id": entity_id, "cash_type": ct, "status": {"$ne": "void"},
                             "$or": [{"account_id": {"$exists": False}}, {"account_id": {"$in": [None, ""]}}]}
        if sejak:
            q["created_at"] = {"$lt": sejak}
        rows = [t async for t in db.cash_transactions.find(q, {"_id": 0, "id": 1, "amount": 1, "direction": 1})]
        if not rows:
            continue
        net = sum(_sen(t.get("amount")) * (1 if t.get("direction") == "in" else -1) for t in rows)
        sole = await bs.sole_account_id(entity_id, ct)
        if sole:
            tunggal_kas.update({t["id"]: sole for t in rows})
            tunggal.append({"cash_type": ct, "rekening_id": sole,
                            "rekening_nama": rek_by_id.get(sole, {}).get("name", ""), "jumlah_kas": len(rows),
                            "jumlah": _rp(net), "kas_ids": sorted(t["id"] for t in rows)})
        else:
            n_rek = sum(1 for r in reks if bs._aktif(r) and bs.account_cash_type(r) == ct)
            tetap.append({"cash_type": ct, "jumlah_kas": len(rows), "jumlah": _rp(net), "rekening_aktif": n_rek})
    # Asal per rekening per akun dari baris jurnal yang benar-benar terbit.
    asal: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    sumber: List[Dict[str, Any]] = []

    def tambah(jenis: str, je: Dict[str, Any], i: int, rid: str) -> None:
        ln = je["lines"][i]
        sen = _sen(ln.get("debit")) - _sen(ln.get("credit"))
        asal[rid][ln["account_code"]] += sen
        sumber.append({"jenis": jenis, "journal_id": je.get("id", ""), "indeks": i, "rekening_id": rid,
                       "akun": ln["account_code"], "sen": sen})

    jq: Dict[str, Any] = {"entity_id": entity_id, "status": {"$ne": "void"},
                          "lines.account_code": {"$in": sorted(lama)}}
    if sejak:
        jq["created_at"] = {"$lt": sejak}
    async for je in db.journal_entries.find(jq, {"_id": 0}).sort([("created_at", 1), ("id", 1)]):
        st = je.get("source_type") or ""
        if gl.is_reversal_type(st):
            continue
        lines = je.get("lines") or []
        if st in rb.SUMBER_SALDO_AWAL:   # saldo awal rekening (`bank_service._post_opening`): tanpa dokumen kas
            rid = (je.get("source_id") or "").split(":")[0]
            if rid in rek_by_id and not await gl.reversal_of(je):
                for i, ln in enumerate(lines):
                    if ln.get("account_code") in lama:
                        tambah("saldo_awal", je, i, rid)
            continue
        kas = [t for t in await gl.kas_jurnal(je)
               if (t.get("account_id") in rek_by_id or (not t.get("account_id") and t.get("id") in tunggal_kas))
               and (not sejak or (t.get("created_at") or "") < sejak)]
        if not kas or await gl.reversal_of(je):
            continue   # jurnal yang sudah dibalik: pembaliknya ikut tidak dipindah (keduanya di akun lama, bersih 0)
        for i, t in gl.pasang_baris_kas(lines, kas, lama).items():
            tambah("kas", je, i, t.get("account_id") or tunggal_kas[t["id"]])
    # Rekening: akun tujuan, saldo buku, asal, selisih.
    kode_asal = {c for a in asal.values() for c in a}
    tujuan_ada = {r.get("gl_account_code") for r in reks if r.get("gl_account_code")}
    akun_ef = await gl.effective_accounts(sorted(kode_asal | lama | tujuan_ada), entity_id)
    perkiraan: set = set()
    rekening: List[Dict[str, Any]] = []
    for r in reks:
        kode = r.get("gl_account_code") or ""
        baru = not kode
        if baru:
            kode = await mode.perkiraan_kode(r, frozenset(perkiraan | tujuan_ada))
            perkiraan.add(kode)
        daftar = [{"akun": c, "nama": (akun_ef.get(c) or {}).get("name", ""), "jumlah": _rp(s)}
                  for c, s in sorted(asal.get(r["id"], {}).items()) if s]
        dipindah = sum(_sen(a["jumlah"]) for a in daftar)
        saldo_tujuan = 0 if baru else await gl.accounts_balance_cents([kode], entity_id)
        saldo_buku = _sen(((await bs.account_ledger(r["id"])) or {}).get("balance"))
        rekening.append({
            "id": r["id"], "nama": r.get("name", ""), "cash_type": bs.account_cash_type(r),
            "aktif": bs._aktif(r), "akun_tujuan": kode,
            "akun_tujuan_nama": r.get("name", "") if baru else (akun_ef.get(kode) or {}).get("name", ""),
            "akun_tujuan_baru": baru, "saldo_buku": _rp(saldo_buku), "asal": daftar, "dipindah": _rp(dipindah),
            "saldo_akun_tujuan": _rp(saldo_tujuan), "saldo_sesudah": _rp(saldo_tujuan + dipindah),
            "selisih": _rp(saldo_tujuan + dipindah - saldo_buku)})
    # Baris jurnal: per rekening per akun asal Dr tujuan / Cr asal; asal negatif → sisi dibalik; nol dilewati.
    baris: List[Dict[str, Any]] = []
    for r in rekening:
        for a in r["asal"]:
            m = a["jumlah"]
            ket = f"Pindah saldo {r['nama']} dari {a['akun']}"
            dr, cr = (r["akun_tujuan"], a["akun"]) if m > 0 else (a["akun"], r["akun_tujuan"])
            nama = {r["akun_tujuan"]: r["akun_tujuan_nama"], a["akun"]: a["nama"]}
            baris += [{"account_code": dr, "account_name": nama[dr], "debit": abs(m), "credit": 0.0,
                       "description": ket},
                      {"account_code": cr, "account_name": nama[cr], "debit": 0.0, "credit": abs(m),
                       "description": ket}]
    # Akun lama: saldo sekarang, yang dipindah, sisa (kas tanpa dokumen, kas lama tanpa rekening tunggal, jurnal lain).
    akun_lama = []
    for c in sorted(lama | kode_asal):
        saldo = await gl.accounts_balance_cents([c], entity_id)
        pindah = sum(a.get(c, 0) for a in asal.values())
        if saldo or pindah:
            akun_lama.append({"akun": c, "nama": (akun_ef.get(c) or {}).get("name", ""), "saldo": _rp(saldo),
                              "dipindah": _rp(pindah), "sisa": _rp(saldo - pindah)})
    jumlah, rincian = await posting_tertunda(entity_id)
    return {
        "entity_id": entity_id, "pt": await _nama_pt(entity_id),
        "aktif": await mode.aktif(entity_id), "aktif_sejak": await mode.aktif_sejak(entity_id),
        "rekening": rekening,
        "kas_tanpa_rekening": {"tunggal": tunggal, "tetap": _rp(sum(_sen(x["jumlah"]) for x in tetap)),
                               "tetap_rincian": tetap},
        "akun_lama": akun_lama, "posting_gagal": jumlah, "posting_gagal_rincian": rincian,
        "baris_jurnal": baris, "total_dipindah": round(sum(b["debit"] for b in baris), 2),
        "sidik": _sidik(rekening, tunggal), "sumber": sumber,
    }


async def pratinjau(entity_id: str) -> Dict[str, Any]:
    """`GET /api/kas-per-rekening/{entity_id}/pratinjau` — hitungan pindah saldo PT itu (tanpa tulisan) + usulan yang
    masih hidup. Bentuk: `{entity_id, pt, aktif, aktif_sejak, rekening: [{id, nama, cash_type, aktif, akun_tujuan,
    akun_tujuan_nama, akun_tujuan_baru, saldo_buku, asal: [{akun, nama, jumlah}], dipindah, saldo_akun_tujuan,
    saldo_sesudah, selisih}], kas_tanpa_rekening: {tunggal: [...], tetap, tetap_rincian}, akun_lama: [{akun, nama,
    saldo, dipindah, sisa}], posting_gagal, posting_gagal_rincian, baris_jurnal, total_dipindah, sidik, usulan}`."""
    await _pt_ada(entity_id)
    hit = await _hitung(entity_id)
    hit.pop("sumber", None)
    hit["usulan"] = await _usulan_hidup(entity_id)
    return hit


def _ringkas(hit: Dict[str, Any]) -> Dict[str, Any]:
    """Potret hitungan yang disimpan di usulan (tanpa daftar baris sumber)."""
    keep = ("rekening", "kas_tanpa_rekening", "akun_lama", "baris_jurnal", "total_dipindah", "sidik")
    return {k: hit[k] for k in keep}


# ── Usulan ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def _bentuk(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return None
    out = safe_doc(doc)
    out.pop("rencana", None)
    out["status_label"] = STATUS_LABEL.get(out.get("status"), out.get("status") or "")
    return out


async def _usulan_hidup(entity_id: str) -> Optional[Dict[str, Any]]:
    return _bentuk(await db[COLL].find_one({"entity_id": entity_id, "status": {"$in": list(HIDUP)}}, {"_id": 0}))


async def ambil(usulan_id: str) -> Optional[Dict[str, Any]]:
    return _bentuk(await db[COLL].find_one({"id": usulan_id}, {"_id": 0}))


async def daftar(scope: Dict[str, Any], status: str = "", page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    """`GET /api/kas-per-rekening/usulan` — usulan pindah saldo per PT (terbaru dulu), berhalaman."""
    q: Dict[str, Any] = dict(scope or {})
    if status:
        q["status"] = status
    page, page_size = max(1, int(page or 1)), max(1, min(int(page_size or 20), 100))
    total = await db[COLL].count_documents(q)
    rows = await db[COLL].find(q, {"_id": 0}).sort("created_at", -1).skip((page - 1) * page_size).to_list(page_size)
    return {"items": [_bentuk(r) for r in rows], "total": total, "page": page, "page_size": page_size,
            "has_more": page * page_size < total,
            "statuses": [{"value": k, "label": v} for k, v in STATUS_LABEL.items()]}


def _jejak(aksi: str, actor: Dict[str, Any], catatan: str = "") -> Dict[str, Any]:
    return {"aksi": aksi, "oleh": actor.get("name", ""), "oleh_id": actor.get("id", ""), "pada": now_iso(),
            "catatan": catatan}


async def _periksa_pilihan(entity_id: str, pilihan: Dict[str, Any], reks: List[Dict[str, Any]]) -> Dict[str, str]:
    """PERIKSA (tanpa tulisan) akun pilihan Finance `{id rekening: kode akun}` ("" = sub-akun buatan sistem)."""
    from services import cash_account_mode as mode
    by_id = {r["id"]: r for r in reks}
    pt = await _nama_pt(entity_id)
    out: Dict[str, str] = {}
    for rid, kode in (pilihan or {}).items():
        kode = str(kode or "").strip()
        if rid not in by_id:
            raise _galat(400, f"Rekening {rid} bukan rekening {pt}.")
        if kode and kode in out.values():
            raise _galat(400, f"Akun {kode} dipilih untuk lebih dari satu rekening.")
        if kode and kode != by_id[rid].get("gl_account_code"):
            try:
                await mode.periksa_akun_pilihan(by_id[rid], kode)
            except mode.SubAkunError as exc:
                raise _galat(400, str(exc)) from exc
        out[rid] = kode
    return out


async def _pasang_akun(rek: Dict[str, Any], kode: Optional[str]) -> None:
    """Akun rekening (idempoten). `kode` None = pertahankan akun yang ada / buat sub-akun; "" = sub-akun buatan
    sistem; kode lain = akun bagan PT pilihan Finance. PT belum aktif → akun lama rekening (kosong, tanpa jurnal) boleh
    diganti."""
    from services import cash_account_mode as mode
    ada = rek.get("gl_account_code") or ""
    if kode is None or kode == ada or (kode == "" and ada and await _buatan_sistem(rek, ada)):
        if not ada:
            await mode.buat_subakun(rek)
        return
    if ada:
        await mode.lepas_subakun(rek["id"])
        await db.bank_accounts.update_one({"id": rek["id"], "gl_account_code": ada},
                                          {"$set": {"gl_account_code": "", "updated_at": now_iso()}})
    await mode.buat_subakun(rek, kode=kode)


async def _buatan_sistem(rek: Dict[str, Any], kode: str) -> bool:
    return bool(await db.gl_accounts.find_one({"code": kode, "entity_id": rek.get("entity_id") or "",
                                               "bank_account_id": rek["id"], "dibuat_dari_rekening": True},
                                              {"_id": 0, "id": 1}))


async def siapkan(entity_id: str, pilihan_akun: Optional[Dict[str, Any]], actor: Dict[str, Any]) -> Dict[str, Any]:
    """`POST /api/kas-per-rekening/{entity_id}/siapkan` — periksa (PT belum aktif, tanpa usulan hidup, nol posting kas
    gagal/tertunda, akun pilihan layak) → akun rekening (idempoten) → usulan `menunggu` + hitungannya."""
    from services import bank_service as bs
    from services import cash_account_mode as mode
    await _pt_ada(entity_id)
    pt = await _nama_pt(entity_id)
    if await mode.aktif(entity_id):
        raise _galat(409, f"{pt} sudah memakai akun buku besar per rekening sejak "
                          f"{(await mode.aktif_sejak(entity_id))[:10]}. Pindah saldo hanya sekali per PT.")
    hidup = await _usulan_hidup(entity_id)
    if hidup:
        raise _galat(409, f"Usulan pindah saldo {pt} yang disiapkan {hidup.get('disiapkan_oleh', '')} masih menunggu "
                          f"persetujuan. Setujui atau tolak dulu.")
    await _tolak_bila_tertunda(entity_id)
    reks = await bs.rekening_pt(entity_id)
    pilihan = await _periksa_pilihan(entity_id, pilihan_akun or {}, reks)
    try:
        for r in reks:
            await _pasang_akun(r, pilihan.get(r["id"]) if r["id"] in pilihan else None)
    except mode.SubAkunError as exc:
        raise _galat(400, str(exc)) from exc
    hit = await _hitung(entity_id)
    n = await db[COLL].count_documents({"entity_id": entity_id})
    now = now_iso()
    doc = {
        "id": f"psk_{entity_id}_{n + 1:03d}", "entity_id": entity_id, "label": f"Pindah saldo kas {pt}",
        "status": "menunggu", "pilihan_akun": pilihan, "hitungan_disiapkan": _ringkas(hit),
        "sidik_disiapkan": hit["sidik"], "total_dipindah": hit["total_dipindah"],
        "disiapkan_oleh": actor.get("name", ""), "disiapkan_oleh_id": actor.get("id", ""), "disiapkan_pada": now,
        "disetujui_oleh": "", "disetujui_oleh_id": "", "disetujui_pada": "", "ditolak_oleh": "", "ditolak_oleh_id": "",
        "ditolak_pada": "", "alasan_tolak": "", "lease_until": "",
        "jejak": [_jejak("siapkan", actor, f"Total dipindah {rupiah(hit['total_dipindah'])}")],
        "created_at": now, "updated_at": now,
    }
    try:
        await db[COLL].insert_one(dict(doc))
    except Exception as exc:  # noqa: BLE001 — dua siapkan bersamaan: id per PT kembar (`uq_id`) → satu menang
        if "E11000" not in str(exc) and "duplicate key" not in str(exc).lower():
            raise
        raise _galat(409, f"Usulan pindah saldo {pt} baru saja disiapkan orang lain. Muat ulang.") from exc
    return {**(await ambil(doc["id"]) or {}), "pratinjau": {k: v for k, v in hit.items() if k != "sumber"}}


async def tolak(usulan_id: str, alasan: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """`POST /api/kas-per-rekening/usulan/{id}/tolak` — hanya usulan `menunggu`; tidak ada yang berubah selain akun
    rekening yang sudah dibuat (tetap, kosong)."""
    u = await db[COLL].find_one({"id": usulan_id}, {"_id": 0})
    if not u:
        raise _galat(404, PESAN_TIDAK_ADA)
    alasan = (alasan or "").strip()
    if len(alasan) < 5:
        raise _galat(400, "Alasan penolakan wajib diisi (minimal 5 huruf).")
    res = await db[COLL].update_one({"id": usulan_id, "status": "menunggu"}, {
        "$set": {"status": "ditolak", "alasan_tolak": alasan, "ditolak_oleh": actor.get("name", ""),
                 "ditolak_oleh_id": actor.get("id", ""), "ditolak_pada": now_iso(), "updated_at": now_iso()},
        "$push": {"jejak": _jejak("tolak", actor, alasan)}})
    if not res.modified_count:
        raise _galat(409, f"Usulan pindah saldo ini berstatus {STATUS_LABEL.get(u.get('status'), u.get('status'))}, "
                          "jadi tidak bisa ditolak.")
    return await ambil(usulan_id) or {}


async def setujui(usulan_id: str, sidik: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """`POST /api/kas-per-rekening/usulan/{id}/setujui` — lihat docstring modul. Usulan `memproses` (persetujuan yang
    terhenti di tengah) diteruskan dari niat tersimpan (sidik tidak dibandingkan lagi; PT mungkin sudah menyala)."""
    from services import cash_account_mode as mode
    from services import dual_control
    from services import gl_service as gl
    from services.book_date import tanggal_buku
    u = await db[COLL].find_one({"id": usulan_id}, {"_id": 0})
    if not u:
        raise _galat(404, PESAN_TIDAK_ADA)
    eid = u["entity_id"]
    pt = await _nama_pt(eid)
    if u.get("status") == "memproses":
        return await lanjutkan(usulan_id, actor)
    if u.get("status") != "menunggu":
        raise _galat(409, f"Usulan pindah saldo ini sudah {STATUS_LABEL.get(u.get('status'), '').lower()}.")
    await dual_control.tolak_bila_pelaku_sama(
        AKSI_KONTROL, u, actor, eid, pengaju=[u.get("disiapkan_oleh_id") or u.get("disiapkan_oleh") or ""])
    if await mode.aktif(eid):
        raise _galat(409, f"{pt} sudah memakai akun buku besar per rekening.")
    await _tolak_bila_tertunda(eid)
    hit = await _hitung(eid)
    if hit["sidik"] != (sidik or "").strip():
        raise _galat(409, PESAN_ANGKA_BERUBAH)
    tanggal = tanggal_buku()
    try:
        await gl.preflight_posting(eid, tanggal)
    except gl.ClosedPeriodError as exc:
        raise _galat(409, f"Pindah saldo {pt} belum bisa disetujui: {exc} Tidak ada yang berubah.") from exc
    # ── NIAT: klaim bersyarat menunggu → memproses (dua penyetuju bersamaan: satu menang) ──────────────────────────
    klaim = await db[COLL].find_one_and_update(
        {"id": usulan_id, "status": "menunggu"},
        {"$set": {"status": "memproses", "disetujui_oleh": actor.get("name", ""),
                  "disetujui_oleh_id": actor.get("id", ""), "disetujui_pada": now_iso(), "tanggal_jurnal": tanggal,
                  "sidik_disetujui": hit["sidik"], "lease_until": _lease_until(), "updated_at": now_iso()},
         "$push": {"jejak": _jejak("setujui", actor, f"Sidik {hit['sidik']}")}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not klaim:
        raise _galat(409, PESAN_SEDANG.format(pt=pt))
    return await _lanjutkan(klaim, actor)


async def lanjutkan(usulan_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Teruskan persetujuan yang terhenti (`memproses`) — dari `setujui` lagi atau Ulang Posting (jenis
    `pindah_saldo_kas`). Klaim jatah waktu dulu: persetujuan yang masih berjalan → 409."""
    u = await db[COLL].find_one({"id": usulan_id}, {"_id": 0}) or {}
    if u.get("status") != "memproses":
        raise _galat(409, "Usulan pindah saldo ini tidak sedang menunggu diteruskan. Muat ulang.")
    klaim = await db[COLL].find_one_and_update(
        {"id": usulan_id, "status": "memproses",
         "$or": [{"lease_until": {"$in": ["", None]}}, {"lease_until": {"$lt": now_iso()}}]},
        {"$set": {"lease_until": _lease_until(), "updated_at": now_iso()},
         "$push": {"jejak": _jejak("lanjutkan", actor)}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not klaim:
        raise _galat(409, PESAN_SEDANG.format(pt=await _nama_pt(u.get("entity_id", ""))))
    return await _lanjutkan(klaim, actor)


async def _lepas_jatah(usulan_id: str, actor: Dict[str, Any], galat: str, *, kembali_menunggu: bool = False) -> None:
    """Lepas jatah waktu sesudah langkah gagal (dicatat di jejak). `kembali_menunggu` = PT belum menyala: usulan kembali
    `menunggu` (tidak ada yang berubah selain akun rekening kosong)."""
    upd: Dict[str, Any] = {"lease_until": "", "updated_at": now_iso()}
    jejak = {"$push": {"jejak": _jejak("setujui_gagal", actor, galat[:300])}}
    if kembali_menunggu:
        upd.update(status="menunggu", disetujui_oleh="", disetujui_oleh_id="", disetujui_pada="", sidik_disetujui="")
        await db[COLL].update_one({"id": usulan_id, "status": "memproses"},
                                  {"$set": upd, "$unset": {"tanggal_jurnal": "", "rencana": ""}, **jejak})
        return
    await db[COLL].update_one({"id": usulan_id}, {"$set": upd, **jejak})


async def _lanjutkan(u: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """EFEK + JURNAL + SELESAI untuk usulan yang sudah diklaim (`memproses`, jatah waktu dipegang pemanggil)."""
    from services import bank_service as bs
    from services import cash_account_mode as mode
    from services import gl_service as gl
    eid, uid = u["entity_id"], u["id"]
    pt = await _nama_pt(eid)
    oleh = {"id": u.get("disetujui_oleh_id", ""), "name": u.get("disetujui_oleh", "") or actor.get("name", "")}
    label = u.get("label") or f"Pindah saldo kas {pt}"
    if not await mode.aktif(eid):
        # 1. Akun rekening lengkap (rekening yang dibuat sesudah disiapkan mendapat sub-akun) + periksa jurnal (akun,
        #    periode) SEBELUM PT menyala — gagal: usulan kembali menunggu, tidak ada yang menyala.
        try:
            for r in await bs.rekening_pt(eid):
                if not r.get("gl_account_code"):
                    await mode.buat_subakun(r)
            pra = await _hitung(eid)
            if pra["baris_jurnal"]:
                await gl.preflight_entry(lines=[{**b, "fixed_account": True} for b in pra["baris_jurnal"]],
                                         entity_id=eid, date=u.get("tanggal_jurnal") or "",
                                         source_type=gl.SOURCE_PINDAH_SALDO_KAS)
        except (mode.SubAkunError, gl.JournalValidationError, gl.ClosedPeriodError) as exc:
            await _lepas_jatah(uid, actor, str(exc), kembali_menunggu=True)
            raise _galat(409, f"Pindah saldo {pt} belum bisa disetujui: {exc} Tidak ada yang berubah.") from exc
        except Exception as exc:
            await _lepas_jatah(uid, actor, str(exc) or exc.__class__.__name__, kembali_menunggu=True)
            raise
        # 2. PT menyala (tulis sekali). Sejak penanda ini kas baru PT masuk sub-akun.
        await mode.nyalakan(eid, oleh)
    try:
        # 3. Niat: hitung ulang dengan batas `aktif_sejak` (aturan pembalik Tugas 2), disimpan sekali.
        if not u.get("rencana"):
            sejak = await mode.aktif_sejak(eid)
            hit = await _hitung(eid, sejak=sejak)
            rencana = {"aktif_sejak": sejak, "baris_jurnal": hit["baris_jurnal"],
                       "tunggal": [{"rekening_id": g["rekening_id"], "kas_ids": g["kas_ids"]}
                                   for g in hit["kas_tanpa_rekening"]["tunggal"]]}
            await db[COLL].update_one({"id": uid, "rencana": {"$exists": False}}, {"$set": {
                "rencana": rencana, "aktif_sejak": sejak, "sidik_diposting": hit["sidik"],
                "hitungan_diposting": _ringkas(hit), "total_dipindah": hit["total_dipindah"], "updated_at": now_iso()}})
            u = await db[COLL].find_one({"id": uid}, {"_id": 0})
        rencana = u["rencana"]
        # 4. Jurnal tahan-gagal (gagal → `gl_status: failed`, panel Posting Gagal; ulang = `lanjutkan`).
        res = await gl.post_durable(
            COLL, uid, lambda: gl.post_pindah_saldo_kas(
                usulan_id=uid, entity_id=eid, lines=rencana["baris_jurnal"], date=u.get("tanggal_jurnal") or "",
                label=label, created_by=oleh["name"] or "system"),
            source_type=gl.SOURCE_PINDAH_SALDO_KAS, source_id=uid, raise_on_fail=True)
        # 5. Kas lama tanpa rekening yang ikut rekening tunggal → `account_id` (jurnalnya tidak diubah).
        for g in rencana.get("tunggal") or []:
            await db.cash_transactions.update_many(
                {"id": {"$in": g["kas_ids"]}, "entity_id": eid,
                 "$or": [{"account_id": {"$exists": False}}, {"account_id": {"$in": [None, ""]}}]},
                {"$set": {"account_id": g["rekening_id"], "account_id_dari_pindah_saldo": uid,
                          "updated_at": now_iso()}})
        ditautkan = await db.cash_transactions.count_documents({"entity_id": eid, "account_id_dari_pindah_saldo": uid})
    except HTTPException as exc:
        await _lepas_jatah(uid, actor, str(exc.detail))
        raise
    except Exception as exc:  # noqa: BLE001 — PT sudah menyala: usulan tetap `memproses`, bisa diteruskan
        await _lepas_jatah(uid, actor, str(exc) or exc.__class__.__name__)
        raise _galat(409, f"{pt} sudah memakai akun per rekening, tetapi pindah saldonya belum selesai: "
                          f"{str(exc)[:300]}. Ulangi dari Keuangan › Posting Gagal atau setujui lagi.") from exc
    # 6. SELESAI.
    je = res.get("journal") or {}
    await db[COLL].update_one({"id": uid, "status": "memproses"}, {
        "$set": {"status": "disetujui", "journal_entry_id": res.get("journal_entry_id", ""),
                 "journal_number": je.get("number", ""), "kas_ditautkan": ditautkan,
                 "lease_until": "", "selesai_pada": now_iso(), "updated_at": now_iso()},
        "$push": {"jejak": _jejak("selesai", actor, f"Jurnal {je.get('number', '') or '—'}; {ditautkan} kas lama "
                                                     f"tanpa rekening diberi rekening")}})
    return await ambil(uid) or {}
