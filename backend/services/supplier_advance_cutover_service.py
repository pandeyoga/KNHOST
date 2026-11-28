"""Kas & Bank bagian 4 (C8) — pindah saldo uang muka pemasok per PT: pratinjau, siapkan, setujui orang kedua, tolak.

Rancangan: `docs/superpowers/specs/2026-11-28-kas-bank-4-uang-muka-design.md` §5.4, §6, §7 butir 7, §7.9.1–§7.9.2. Pola
`cash_account_cutover_service` (Kas & Bank 1).

* **Pratinjau** (`pratinjau`, tanpa tulisan) — buku pembantu uang muka pemasok PT per pemasok
  (`supplier_advance_service`: kas `ap_advance` − potongan kontrabon terjurnal + kasus lebih bayar − pengembalian dana
  kasus), total yang akan dipindah, saldo 1-1400 PT, saldo akun uang muka pemasok PT, penahan berkalimat, `sidik`, dan
  usulan yang masih hidup (dengan penilaian kontrol dua orang untuk pembaca).
* **Siapkan** (`siapkan`, izin `accounting.manage`) — ditolak bila PT sudah pindah, ada usulan hidup, atau ada penahan
  (§7.9.2: kontrabon belum dibayar yang memuat potongan uang muka, jurnal uang muka pemasok gagal/tertunda, pemasok
  bernilai negatif, akun uang muka pemasok PT sudah bersaldo sebelum pindah). Membekukan baris, total, dan sidik di
  usulan `menunggu` (koleksi `supplier_advance_cutovers`).
* **Setujui** (`setujui`, orang kedua — `dual_control.tolak_bila_pelaku_sama("pindah_uang_muka_pemasok")`, bawaan dua
  orang juga Admin) — PERIKSA: hitung ulang; penahan → 409; sidik ≠ sidik saat disiapkan → 409 (tolak lalu siapkan
  ulang); periode & akun jurnal diperiksa. KLAIM: `menunggu` → `memproses` bersyarat + jatah waktu (dua penyetuju
  bersamaan: satu menang). EFEK, urutan tetap:
    1. jurnal reklas Dr akun uang muka pemasok PT / Cr 1-1400 sebesar total, bertanggal buku hari persetujuan — SEBELUM
       penanda (ketetapan pengendali (a)); total 0 → tanpa jurnal. Gagal → usulan kembali `menunggu`, tidak ada yang
       berubah;
    2. `supplier_advance_mode.nyalakan` — sejak itu semua jalur uang muka pemasok PT memakai akun uang muka pemasok;
    3. susulan: uang muka pemasok yang terjurnal ke 1-1400 di sela hitung dan penanda = total buku pembantu sekarang −
       saldo akun uang muka pemasok (akun kontrol: sebelum pindah tidak ada yang masuk ke sana — penahan memastikan nol);
       ≠ 0 → jurnal susulan. Gagal → usulan tetap `memproses` (PT sudah pindah), tampil di Posting Gagal, diteruskan
       dengan Setujui lagi atau Ulangi Posting (`lanjutkan`).
  SELESAI: `disetujui` + nomor jurnal. Sesudahnya pembalikan uang muka pemasok lama dialihkan ke akun uang muka pemasok
  (`gl_service.baris_uang_muka_pemasok`).
* **Tolak** (`tolak`) — hanya usulan `menunggu`, alasan ≥ 5 huruf; tidak ada yang berubah.

Tidak ada yang berjalan saat aplikasi menyala; tidak ada tanggal mundur; VPS tidak memindah apa pun sampai Finance PT itu
melakukannya.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pymongo import ReturnDocument

from core_utils import from_cents, now_iso, rupiah, safe_doc, to_cents
from db import db

COLL = "supplier_advance_cutovers"
AKSI_KONTROL = "pindah_uang_muka_pemasok"
LEASE_MINUTES = 2   # jatah kerja satu persetujuan yang sedang berjalan; batas teknis, bukan aturan bisnis
STATUS_LABEL = {"menunggu": "Menunggu persetujuan", "memproses": "Sedang diproses", "disetujui": "Disetujui",
                "ditolak": "Ditolak"}
HIDUP = ("menunggu", "memproses")

PESAN_TIDAK_ADA = "Usulan pindah saldo uang muka pemasok tidak ditemukan."
PESAN_ANGKA_BERUBAH = ("Angka uang muka pemasok berubah sejak usulan ini disiapkan. Tolak usulan ini, lalu siapkan "
                       "ulang.")
PESAN_SEDANG = "Pindah saldo uang muka pemasok {pt} sedang diproses. Tunggu sebentar lalu muat ulang."


def _galat(status: int, pesan: str) -> HTTPException:
    return HTTPException(status_code=status, detail=pesan)


def _lease_until() -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=LEASE_MINUTES)).isoformat()


async def _nama_pt(entity_id: str) -> str:
    from services.cash_ledger import _nama_pt as nama
    return await nama(entity_id)


async def _pt_ada(entity_id: str) -> None:
    if not entity_id or entity_id == "all":
        raise _galat(400, "Pilih satu PT untuk pindah saldo uang muka pemasok.")
    if not await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "id": 1}):
        raise _galat(404, "PT tidak ditemukan.")


def _sidik(baris: List[Dict[str, Any]]) -> str:
    """Sidik buku pembantu: per pemasok semua kolom (sen). Berubah bila ada uang muka/potongan/kasus baru sejak dimuat."""
    from services.supplier_advance_service import KOLOM
    isi = sorted([r["supplier_id"], *[to_cents(r[k]) for k in KOLOM]] for r in baris)
    return hashlib.sha256(json.dumps(isi, ensure_ascii=False).encode("utf-8")).hexdigest()[:24]


async def _saldo(key: str, entity_id: str) -> int:
    from services import gl_mapping_service as glm
    from services import gl_service as gl
    return await gl.accounts_balance_cents(await glm.known_codes(key, entity_id), entity_id)


async def _hitung(entity_id: str) -> Dict[str, Any]:
    """Hitungan pindah saldo PT itu (tanpa tulisan)."""
    from services import gl_mapping_service as glm
    from services import supplier_advance_mode as mode
    from services import supplier_advance_service as sas
    bacaan = await sas.bacaan_pindah(entity_id)
    aktif = await mode.aktif(entity_id)
    akun_pemasok = await glm.account_for("hutang.uang_muka_pemasok", entity_id)
    akun_karyawan = await glm.account_for("kas_bank.uang_muka_karyawan", entity_id)
    saldo_pemasok = await _saldo("hutang.uang_muka_pemasok", entity_id)
    penahan = list(bacaan["penahan"])
    if not aktif and saldo_pemasok:
        penahan.append({"jenis": "akun_pemasok_bersaldo", "nomor": akun_pemasok, "kalimat": (
            f"Akun {akun_pemasok} PT ini sudah bersaldo {rupiah(from_cents(saldo_pemasok))} sebelum pindah saldo. "
            "Periksa dan pindahkan isinya dulu, supaya sesudah pindah saldonya sama dengan buku pembantu uang muka "
            "pemasok.")})
    total = to_cents(bacaan["total"])
    return {"entity_id": entity_id, "pt": await _nama_pt(entity_id), "aktif": aktif,
            "aktif_sejak": await mode.aktif_sejak(entity_id), "baris": bacaan["baris"], "total": from_cents(total),
            "advance_balance_info": bacaan["advance_balance_info"],
            "saldo_1_1400": from_cents(await _saldo("kas_bank.uang_muka_karyawan", entity_id)),
            "akun_1_1400": akun_karyawan, "akun_pemasok": akun_pemasok,
            "saldo_akun_pemasok": from_cents(saldo_pemasok), "penahan": penahan,
            "baris_jurnal": _rencana_jurnal(total, akun_pemasok, akun_karyawan), "sidik": _sidik(bacaan["baris"])}


def _rencana_jurnal(sen: int, pemasok: str, karyawan: str) -> List[Dict[str, Any]]:
    """Baris jurnal reklas yang akan terbit (sama dengan `gl_service.post_pindah_uang_muka_pemasok`)."""
    if not sen:
        return []
    dr, cr = (pemasok, karyawan) if sen > 0 else (karyawan, pemasok)
    n = from_cents(abs(sen))
    return [{"account_code": dr, "debit": n, "credit": 0.0}, {"account_code": cr, "debit": 0.0, "credit": n}]


def _alasan(hit: Dict[str, Any], hidup: Optional[Dict[str, Any]]) -> str:
    if hit["aktif"]:
        return (f"{hit['pt']} sudah memakai akun uang muka pemasok sendiri sejak {hit['aktif_sejak'][:10]}. Pindah "
                "saldo hanya sekali per PT.")
    if hidup:
        return (f"Usulan pindah saldo uang muka pemasok {hit['pt']} yang disiapkan {hidup.get('disiapkan_oleh', '')} "
                "masih menunggu persetujuan. Setujui atau tolak dulu.")
    if hit["penahan"]:
        return " ".join(p["kalimat"] for p in hit["penahan"])
    return ""


def _bentuk(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return None
    out = safe_doc(doc)
    out["status_label"] = STATUS_LABEL.get(out.get("status"), out.get("status") or "")
    return out


async def _usulan_hidup(entity_id: str) -> Optional[Dict[str, Any]]:
    return await db[COLL].find_one({"entity_id": entity_id, "status": {"$in": list(HIDUP)}}, {"_id": 0})


async def ambil(usulan_id: str) -> Optional[Dict[str, Any]]:
    return _bentuk(await db[COLL].find_one({"id": usulan_id}, {"_id": 0}))


def _pengaju(u: Dict[str, Any]) -> List[str]:
    return [u.get("disiapkan_oleh_id") or u.get("disiapkan_oleh") or ""]


async def pratinjau(entity_id: str, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """`GET /api/uang-muka-pemasok/pindah/{entity_id}/pratinjau` → `{entity_id, pt, aktif, aktif_sejak, baris: [{supplier_id,
    nama, dari_kas, dipotong_terjurnal, dari_kasus, refund_kasus, sisa}], total, advance_balance_info, saldo_1_1400,
    akun_1_1400, akun_pemasok, saldo_akun_pemasok, penahan: [{jenis, nomor, kalimat}], baris_jurnal, sidik, bisa_siapkan,
    alasan, usulan, usulan_terakhir}`. `usulan` (hidup) membawa `kontrol` = penilaian dua orang untuk `actor` (aturan
    yang sama dengan `setujui`) supaya layar menonaktifkan Setujui dengan alasan tertulis."""
    from services import dual_control
    await _pt_ada(entity_id)
    hit = await _hitung(entity_id)
    hidup = await _usulan_hidup(entity_id)
    hit["alasan"] = _alasan(hit, hidup)
    hit["bisa_siapkan"] = not hit["alasan"]
    hit["usulan"] = _bentuk(hidup)
    if hidup and actor is not None and hidup.get("status") == "menunggu":
        hit["usulan"]["kontrol"] = await dual_control.periksa(AKSI_KONTROL, hidup, actor, entity_id,
                                                              pengaju=_pengaju(hidup))
    rows = await db[COLL].find({"entity_id": entity_id}, {"_id": 0}).sort("created_at", -1).to_list(1)
    hit["usulan_terakhir"] = _bentuk(rows[0]) if rows else None
    return hit


def _jejak(aksi: str, actor: Dict[str, Any], catatan: str = "") -> Dict[str, Any]:
    return {"aksi": aksi, "oleh": actor.get("name", ""), "oleh_id": actor.get("id", ""), "pada": now_iso(),
            "catatan": catatan}


async def siapkan(entity_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """`POST /api/uang-muka-pemasok/pindah/{entity_id}/siapkan` — PERIKSA (PT belum pindah, tanpa usulan hidup, tanpa
    penahan) → usulan `menunggu` yang membekukan `baris`, `total`, `sidik`."""
    await _pt_ada(entity_id)
    hit = await _hitung(entity_id)
    hidup = await _usulan_hidup(entity_id)
    alasan = _alasan(hit, hidup)
    if alasan:
        raise _galat(409, alasan if hit["aktif"] or hidup else f"Pindah saldo uang muka pemasok {hit['pt']} belum "
                                                                f"bisa disiapkan: {alasan}")
    n = await db[COLL].count_documents({"entity_id": entity_id})
    now = now_iso()
    doc = {
        "id": f"pum_{entity_id}_{n + 1:03d}", "entity_id": entity_id,
        "label": f"Pindah saldo uang muka pemasok {hit['pt']}", "status": "menunggu",
        "baris": hit["baris"], "total": hit["total"], "sidik": hit["sidik"], "saldo_1_1400": hit["saldo_1_1400"],
        "akun_pemasok": hit["akun_pemasok"], "akun_1_1400": hit["akun_1_1400"],
        "advance_balance_info": hit["advance_balance_info"],
        "disiapkan_oleh": actor.get("name", ""), "disiapkan_oleh_id": actor.get("id", ""), "disiapkan_pada": now,
        "disetujui_oleh": "", "disetujui_oleh_id": "", "disetujui_pada": "", "ditolak_oleh": "",
        "ditolak_oleh_id": "", "ditolak_pada": "", "alasan_tolak": "", "lease_until": "",
        "jejak": [_jejak("siapkan", actor, f"Total dipindah {rupiah(hit['total'])}")],
        "created_at": now, "updated_at": now,
    }
    try:
        await db[COLL].insert_one(dict(doc))
    except Exception as exc:  # noqa: BLE001 — dua siapkan bersamaan: id per PT kembar (`uq_id`) → satu menang
        if "E11000" not in str(exc) and "duplicate key" not in str(exc).lower():
            raise
        raise _galat(409, f"Usulan pindah saldo uang muka pemasok {hit['pt']} baru saja disiapkan orang lain. "
                          "Muat ulang.") from exc
    return await ambil(doc["id"]) or {}


async def tolak(usulan_id: str, alasan: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """`POST /api/uang-muka-pemasok/pindah/{id}/tolak` — hanya usulan `menunggu`; tidak ada yang berubah."""
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
    """`POST /api/uang-muka-pemasok/pindah/{id}/setujui {sidik}` — lihat docstring modul. `sidik` = sidik yang dilihat
    penyetuju (opsional; berbeda dari hitung ulang → 409). Usulan `memproses` (persetujuan yang terhenti) diteruskan."""
    from services import dual_control
    from services import gl_service as gl
    from services import supplier_advance_mode as mode
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
    # ── PERIKSA ────────────────────────────────────────────────────────────────────────────────────────────────────
    await dual_control.tolak_bila_pelaku_sama(AKSI_KONTROL, u, actor, eid, pengaju=_pengaju(u))
    if await mode.aktif(eid):
        raise _galat(409, f"{pt} sudah memakai akun uang muka pemasok sendiri.")
    hit = await _hitung(eid)
    if hit["penahan"]:
        raise _galat(409, f"Pindah saldo uang muka pemasok {pt} belum bisa disetujui: "
                          f"{' '.join(p['kalimat'] for p in hit['penahan'])}")
    if hit["sidik"] != u.get("sidik") or ((sidik or "").strip() and sidik.strip() != hit["sidik"]):
        raise _galat(409, PESAN_ANGKA_BERUBAH)
    tanggal = tanggal_buku()
    try:
        if hit["baris_jurnal"]:
            await gl.preflight_entry(lines=[{**b, "fixed_account": True} for b in hit["baris_jurnal"]],
                                     entity_id=eid, date=tanggal, source_type=gl.SOURCE_PINDAH_UANG_MUKA_PEMASOK)
        else:
            await gl.preflight_posting(eid, tanggal)
    except (gl.JournalValidationError, gl.ClosedPeriodError) as exc:
        raise _galat(409, f"Pindah saldo uang muka pemasok {pt} belum bisa disetujui: {exc} Tidak ada yang "
                          "berubah.") from exc
    # ── KLAIM: menunggu → memproses (dua penyetuju bersamaan: satu menang) ───────────────────────────────────────────
    klaim = await db[COLL].find_one_and_update(
        {"id": usulan_id, "status": "menunggu"},
        {"$set": {"status": "memproses", "disetujui_oleh": actor.get("name", ""),
                  "disetujui_oleh_id": actor.get("id", ""), "disetujui_pada": now_iso(), "tanggal_jurnal": tanggal,
                  "lease_until": _lease_until(), "updated_at": now_iso()},
         "$push": {"jejak": _jejak("setujui", actor, f"Sidik {hit['sidik']} · total {rupiah(hit['total'])}")}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not klaim:
        raise _galat(409, PESAN_SEDANG.format(pt=pt))
    return await _lanjutkan(klaim, actor)


async def lanjutkan(usulan_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Teruskan persetujuan yang terhenti (`memproses`) — dari `setujui` lagi atau Ulangi Posting (jenis
    `pindah_uang_muka_pemasok`). Persetujuan yang masih memegang jatah waktu → 409."""
    u = await db[COLL].find_one({"id": usulan_id}, {"_id": 0}) or {}
    if u.get("status") != "memproses":
        raise _galat(409, "Usulan pindah saldo uang muka pemasok ini tidak sedang menunggu diteruskan. Muat ulang.")
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
    """Lepas jatah waktu sesudah langkah gagal (dicatat di jejak). `kembali_menunggu` = belum ada yang berubah (jurnal
    reklas belum terbit, PT belum pindah): usulan kembali `menunggu`."""
    upd: Dict[str, Any] = {"lease_until": "", "updated_at": now_iso()}
    jejak = {"$push": {"jejak": _jejak("setujui_gagal", actor, galat[:300])}}
    if kembali_menunggu:
        upd.update(status="menunggu", disetujui_oleh="", disetujui_oleh_id="", disetujui_pada="")
        await db[COLL].update_one({"id": usulan_id, "status": "memproses"},
                                  {"$set": upd, "$unset": {"tanggal_jurnal": "", "gl_status": "", "gl_error": "",
                                                           "gl_failed_at": ""}, **jejak})
        return
    await db[COLL].update_one({"id": usulan_id}, {"$set": upd, **jejak})


async def _lanjutkan(u: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """EFEK + JURNAL + SELESAI untuk usulan yang sudah diklaim (`memproses`, jatah waktu dipegang pemanggil)."""
    from services import gl_service as gl
    from services import supplier_advance_mode as mode
    from services import supplier_advance_service as sas
    eid, uid = u["entity_id"], u["id"]
    pt = await _nama_pt(eid)
    oleh = {"id": u.get("disetujui_oleh_id", ""), "name": u.get("disetujui_oleh", "") or actor.get("name", "")}
    label = u.get("label") or f"Pindah saldo uang muka pemasok {pt}"
    tanggal = u.get("tanggal_jurnal") or ""
    sumber = gl.SOURCE_PINDAH_UANG_MUKA_PEMASOK
    if not await mode.aktif(eid):
        # 1. Jurnal reklas SEBELUM penanda (pembantu akun masih 1-1400; akun dari pemetaan langsung).
        try:
            await gl.post_durable(
                COLL, uid, lambda: gl.post_pindah_uang_muka_pemasok(
                    usulan_id=uid, entity_id=eid, amount=float(u.get("total") or 0), date=tanggal, label=label,
                    created_by=oleh["name"] or "system"),
                source_type=sumber, source_id=uid, raise_on_fail=True)
        except Exception as exc:  # noqa: BLE001 — jurnal reklas belum ada → tidak ada yang berubah
            ada = await db.journal_entries.find_one({"source_type": sumber, "source_id": uid,
                                                     "status": {"$ne": "void"}}, {"_id": 0, "id": 1})
            await _lepas_jatah(uid, actor, str(exc) or exc.__class__.__name__, kembali_menunggu=not ada)
            raise _galat(409, f"Pindah saldo uang muka pemasok {pt} belum bisa disetujui: {str(exc)[:300]}. "
                              + ("Tidak ada yang berubah." if not ada else "Setujui lagi untuk melanjutkan.")) from exc
        # 2. PT pindah (tulis sekali). Sejak penanda ini semua jalur uang muka pemasok PT memakai akunnya sendiri.
        try:
            await mode.nyalakan(eid, oleh)
        except Exception as exc:  # noqa: BLE001 — jurnal reklas sudah terbit: usulan tetap `memproses`, diteruskan
            await _lepas_jatah(uid, actor, str(exc) or exc.__class__.__name__)
            raise _galat(409, f"Jurnal reklas uang muka pemasok {pt} sudah terbit, tetapi penanda PT belum menyala: "
                              f"{str(exc)[:300]}. Setujui lagi untuk melanjutkan.") from exc
    try:
        # 3. Susulan: uang muka pemasok yang masih di 1-1400 (terjurnal di sela hitung dan penanda) — buku pembantu
        #    sekarang − saldo akun uang muka pemasok (sebelum pindah nol: penahan `akun_pemasok_bersaldo`).
        sl = await sas.subledger(eid)
        susulan = to_cents(sl["total"]) - await _saldo("hutang.uang_muka_pemasok", eid)
        if susulan:
            await gl.post_durable(
                COLL, uid, lambda: gl.post_pindah_uang_muka_pemasok(
                    usulan_id=uid, entity_id=eid, amount=from_cents(susulan), date=tanggal, label=label,
                    bagian="susulan", created_by=oleh["name"] or "system"),
                source_type=sumber, source_id=f"{uid}:susulan", field="susulan_gl_status", raise_on_fail=True)
    except Exception as exc:  # noqa: BLE001 — PT sudah pindah: usulan tetap `memproses`, bisa diteruskan
        await _lepas_jatah(uid, actor, str(exc) or exc.__class__.__name__)
        raise _galat(409, f"{pt} sudah memakai akun uang muka pemasok sendiri, tetapi jurnal susulan pindah saldonya "
                          f"belum terbit: {str(exc)[:300]}. Ulangi dari Keuangan › Posting Gagal, atau setujui lagi "
                          "usulan ini.") from exc
    # 4. SELESAI.
    jes = {j["source_id"]: j async for j in db.journal_entries.find(
        {"source_type": sumber, "source_id": {"$in": [uid, f"{uid}:susulan"]}, "status": {"$ne": "void"}},
        {"_id": 0, "id": 1, "number": 1, "source_id": 1, "lines": 1})}

    from services import gl_mapping_service as glm
    akun = await glm.account_for("hutang.uang_muka_pemasok", eid)

    def _neto(je: Optional[Dict[str, Any]]) -> int:   # Dr akun uang muka pemasok bertanda + (susulan bisa negatif)
        return sum(to_cents(ln.get("debit")) - to_cents(ln.get("credit"))
                   for ln in (je or {}).get("lines") or [] if ln.get("account_code") == akun)

    reklas, sus = jes.get(uid), jes.get(f"{uid}:susulan")
    dipindah = _neto(reklas) + _neto(sus)
    await db[COLL].update_one({"id": uid, "status": "memproses"}, {
        "$set": {"status": "disetujui", "aktif_sejak": await mode.aktif_sejak(eid),
                 "journal_entry_id": (reklas or {}).get("id", ""), "journal_number": (reklas or {}).get("number", ""),
                 "susulan": from_cents(_neto(sus)), "susulan_journal_entry_id": (sus or {}).get("id", ""),
                 "susulan_journal_number": (sus or {}).get("number", ""), "total_dipindah": from_cents(dipindah),
                 "lease_until": "", "selesai_pada": now_iso(), "updated_at": now_iso()},
        "$push": {"jejak": _jejak("selesai", actor, f"Jurnal {(reklas or {}).get('number') or '—'}"
                                  + (f"; susulan {sus.get('number', '')}" if sus else "")
                                  + f"; dipindah {rupiah(from_cents(dipindah))}")}})
    return await ambil(uid) or {}
