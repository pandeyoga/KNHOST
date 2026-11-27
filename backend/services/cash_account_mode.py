"""Kas & Bank bagian 1 (D1) — akun buku besar per rekening: mode per PT dan sub-akun rekening.

Rancangan: `docs/superpowers/specs/2026-11-27-kas-bank-1-rekening-pindah-dana-design.md` §5.1 dan §7 (butir 1–3).

* **Mode per PT** — penanda di `system_settings{scope: "__kas_per_rekening__"}`: kunci = id PT, nilai =
  `{"sejak": <ISO>, "oleh": <nama>}`. Ditulis SEKALI (`nyalakan`) — oleh persetujuan pindah saldo PT itu (Tugas 3);
  tidak ada migrasi saat aplikasi menyala dan tidak ada jalan mematikannya. Selama PT belum aktif semua jurnal kasnya
  persis seperti sebelumnya (`gl_service.akun_kas`).
* **Sub-akun rekening** — `buat_subakun`: akun khusus PT `{induk}-{NN}` (induk 1-1100 untuk bank/kas besar, 1-1110 untuk
  kas kecil; NN = nomor dua digit terkecil yang belum dipakai di PT itu di bawah induk itu), nama = nama rekening,
  `is_cash`, `bank_account_id`, `dibuat_dari_rekening`; atau akun bagan PT yang sudah ada pilihan Finance (diperiksa
  `periksa_akun_pilihan`; tandanya dipotret sebelum dipasang dan dipulihkan persis bila usulan pindah saldo ditolak —
  `potret_akun_pilihan` / `pulihkan_akun_pilihan`). Kodenya ditulis ke `bank_accounts.gl_account_code` dan tidak
  berubah walau nama rekening berubah (nama akun buatan sistem ikut nama rekening: `ikut_nama_rekening`).
* Pemakai: `gl_service.akun_kas` (satu pembantu akun kas jurnal), `bank_service.create_account` (rekening baru di PT
  aktif), `gl_service.create_manual_entry` (jurnal manual ke akun ber-`bank_account_id` ditolak).

Batas: tidak ada indeks unik (database uji tiruan tidak menguji indeks parsial); balapan dua pembuat sub-akun ditangani
dengan klaim bersyarat pada rekening (`gl_account_code` kosong) dan pemeriksaan kode tunggal sesudah sisip.
"""
import re
from typing import Any, Dict, List, Optional

from core_utils import new_id, now_iso
from db import db

SCOPE = "__kas_per_rekening__"
#: Akun induk sub-akun per jenis kas rekening (`bank_service.account_cash_type`).
INDUK = {"kas_besar": "1-1100", "kas_kecil": "1-1110"}
_KUNCI_SAH = re.compile(r"^[A-Za-z0-9_\-]+$")
_COBA_NOMOR = 5
#: Tanda akun rekening yang dipasang `buat_subakun(kode=…)` pada akun bagan PT pilihan Finance (dipotret sebelum
#: dipasang dan dipulihkan persis bila usulan pindah saldo ditolak — `potret_akun_pilihan` / `pulihkan_akun_pilihan`).
TANDA_AKUN_PILIHAN = ("is_cash", "bank_account_id", "is_cash_dari_rekening")


class SubAkunError(ValueError):
    """Sub-akun rekening tidak bisa dibuat atau akun pilihan tidak layak — pesan siap tampil (router → 400)."""


def _kunci_sah(entity_id: Any) -> str:
    eid = str(entity_id or "").strip()
    return eid if eid and _KUNCI_SAH.match(eid) else ""


async def _nama_pt(entity_id: str) -> str:
    from services.cash_ledger import _nama_pt as nama
    return await nama(entity_id)


# ── Mode per PT ──────────────────────────────────────────────────────────────────────────────────────────────────────
async def aktif_sejak(entity_id: Optional[str]) -> str:
    """Waktu PT `entity_id` mulai memakai akun per rekening (ISO), kosong bila belum. Dokumen penanda kembar (balapan
    dua `nyalakan` pertama) digabung; yang paling awal berlaku."""
    eid = _kunci_sah(entity_id)
    if not eid:
        return ""
    sejak = [d[eid]["sejak"] async for d in db.system_settings.find({"scope": SCOPE}, {"_id": 0, eid: 1})
             if isinstance(d.get(eid), dict) and d[eid].get("sejak")]
    return min(sejak) if sejak else ""


async def aktif(entity_id: Optional[str]) -> bool:
    """Apakah jurnal kas PT `entity_id` memakai sub-akun rekening."""
    return bool(await aktif_sejak(entity_id))


async def nyalakan(entity_id: str, by: Any) -> None:
    """Nyalakan akun per rekening untuk PT `entity_id` — SEKALI; panggilan berikutnya tidak menimpa waktu & pelakunya.
    Dibaca dulu, lalu ditulis bersyarat kuncinya belum ada (pola `bank_auto_receipt_service.ensure_aktif_sejak`)."""
    eid = _kunci_sah(entity_id)
    if not eid:
        raise ValueError(f"Id PT tidak sah untuk penanda akun per rekening: {entity_id!r}.")
    if await aktif_sejak(eid):
        return
    oleh = (by.get("name") if isinstance(by, dict) else by) or "system"
    nilai = {"sejak": now_iso(), "oleh": str(oleh)}
    syarat = {"scope": SCOPE, eid: {"$exists": False}}
    if await db.system_settings.find_one({"scope": SCOPE}, {"_id": 0, "scope": 1}) is None:
        await db.system_settings.update_one(syarat, {"$set": {eid: nilai}}, upsert=True)
    else:   # tanpa upsert: dokumen penanda tetap satu
        await db.system_settings.update_one(syarat, {"$set": {eid: nilai}})


# ── Sub-akun rekening ────────────────────────────────────────────────────────────────────────────────────────────────
def induk_untuk(rekening: Dict[str, Any]) -> str:
    from services.bank_service import account_cash_type
    return INDUK[account_cash_type(rekening)]


async def _nama_rekening(account_id: str) -> str:
    acc = await db.bank_accounts.find_one({"id": account_id}, {"_id": 0, "name": 1}) or {}
    return acc.get("name") or account_id


async def periksa_akun_pilihan(rekening: Dict[str, Any], kode: str) -> Dict[str, Any]:
    """PERIKSA (tanpa tulisan) akun bagan PT `kode` yang dipilih Finance untuk `rekening`. → dokumen akun.

    Syarat: bukan kode bawaan bersama (kode bawaan dipetakan ulang per PT), akun khusus PT rekening itu, aktif, bisa
    diposting, berjenis aset, bukan akun kontrol buku pembantu, bukan hasil pemetaan PT itu untuk kebutuhan APA PUN
    (`kas_bank.*`: jurnal kas tanpa akun rekening dipetakan ke sana; kebutuhan lain — tinjauan akhir Minor 3: jurnal
    otomatis jalur itu ikut masuk — saldo akun rekening tidak lagi sama dengan buku kas rekening), belum dipakai
    rekening lain. Gagal → `SubAkunError`."""
    from services import gl_mapping_registry as reg, gl_mapping_service as glm
    kode = (kode or "").strip()
    eid = rekening.get("entity_id") or ""
    rid = rekening.get("id") or ""
    pt = await _nama_pt(eid)
    if kode in reg.REMAP_BY_DEFAULT or kode in INDUK.values():
        raise SubAkunError(f"Akun {kode} adalah akun bawaan bersama semua PT. Pilih akun khusus {pt}, atau "
                           f"kosongkan supaya sistem membuat sub-akun rekening.")
    akun = await db.gl_accounts.find_one({"code": kode, "entity_id": eid}, {"_id": 0})
    if not akun:
        raise SubAkunError(f"Akun {kode} tidak ada di bagan akun {pt}.")
    if akun.get("is_active") is False:
        raise SubAkunError(f"Akun {kode} nonaktif.")
    if akun.get("is_postable") is False:
        raise SubAkunError(f"Akun {kode} adalah akun induk — pilih akun detail.")
    if (akun.get("type") or "") != "asset":
        raise SubAkunError(f"Akun {kode} bukan akun aset (kas/bank).")
    if kode in await glm.control_accounts(eid):
        raise SubAkunError(f"Akun {kode} adalah akun kontrol buku pembantu, bukan akun kas/bank.")
    for entry in reg.ENTRIES:   # tinjauan T1 I1 + akhir Minor 3 — pemetaan efektif PT itu (PT → global → bawaan)
        if await glm.account_for(entry["key"], eid) == kode:
            jalur = ("jurnal kas tanpa akun rekening" if entry["key"].startswith("kas_bank.")
                     else "jurnal otomatis jalur itu")
            raise SubAkunError(f"Akun {kode} sedang dipakai Pemetaan Akun \"{entry['label']}\" ({entry['key']}) di "
                               f"{pt}, jadi {jalur} ikut masuk ke akun ini. Pilih akun lain, atau ganti pemetaannya "
                               f"dulu di Pemetaan Akun.")
    pemakai = akun.get("bank_account_id") or ""
    if not pemakai or pemakai == rid:
        lain = await db.bank_accounts.find_one({"entity_id": eid, "gl_account_code": kode, "id": {"$ne": rid}},
                                               {"_id": 0, "id": 1})
        pemakai = (lain or {}).get("id") or pemakai
    if pemakai and pemakai != rid:
        raise SubAkunError(f"Akun {kode} sudah dipakai rekening {await _nama_rekening(pemakai)}.")
    return akun


async def _kode_berikutnya(entity_id: str, induk: str, lewati: frozenset = frozenset()) -> str:
    """`{induk}-{NN}` dengan NN dua digit terkecil yang belum dipakai di PT itu (akun global berkode sama ikut dihitung:
    akun PT berkode sama akan menutupinya di bagan akun efektif). `lewati` = kode yang dianggap sudah dipakai (perkiraan
    kode beberapa sub-akun sekaligus di pratinjau pindah saldo, tanpa tulisan)."""
    pola = re.compile(rf"^{re.escape(induk)}-(\d{{2}})$")
    dipakai = {int(m.group(1)) for m in (pola.match(k) for k in lewati) if m}
    async for a in db.gl_accounts.find({"code": {"$regex": pola.pattern},
                                        "entity_id": {"$in": [entity_id, None, ""]}}, {"_id": 0, "code": 1}):
        m = pola.match(a.get("code") or "")
        if m:
            dipakai.add(int(m.group(1)))
    for n in range(1, 100):
        if n not in dipakai:
            return f"{induk}-{n:02d}"
    raise SubAkunError(f"Nomor sub-akun {induk} di {await _nama_pt(entity_id)} sudah habis (99). Pilih akun bagan "
                       f"PT yang sudah ada untuk rekening ini.")


async def perkiraan_kode(rekening: Dict[str, Any], lewati: frozenset = frozenset()) -> str:
    """Kode sub-akun yang AKAN dibuat `buat_subakun` untuk rekening tanpa akun — pratinjau pindah saldo, tanpa tulisan.
    `lewati` = kode perkiraan rekening lain di pratinjau yang sama."""
    return await _kode_berikutnya(rekening.get("entity_id") or "", induk_untuk(rekening), lewati)


async def _kode_milik(entity_id: str, kode: str, akun_id: str) -> bool:
    """Sesudah sisip: benar bila akun `akun_id` adalah pemilik sah `kode` di PT itu (yang tertua bila kembar)."""
    rows = await db.gl_accounts.find({"code": kode, "entity_id": {"$in": [entity_id, None, ""]}},
                                     {"_id": 0, "id": 1, "created_at": 1}).to_list(10)
    rows.sort(key=lambda a: (a.get("created_at") or "", a.get("id") or ""))
    return bool(rows) and rows[0]["id"] == akun_id


async def _sisip_subakun(acc: Dict[str, Any]) -> Dict[str, Any]:
    from services.gl_service import normal_balance
    eid = acc.get("entity_id") or ""
    induk = induk_untuk(acc)
    for _ in range(_COBA_NOMOR):
        kode = await _kode_berikutnya(eid, induk)
        now = now_iso()
        doc = {"id": new_id("gla"), "code": kode, "name": acc.get("name") or kode, "type": "asset",
               "normal_balance": normal_balance("asset"), "parent_code": induk, "is_postable": True,
               "is_active": True, "system": False, "currency": acc.get("currency") or "IDR",
               "description": f"Akun buku besar rekening {acc.get('name') or ''}".strip(), "entity_id": eid,
               "is_cash": True, "bank_account_id": acc["id"], "dibuat_dari_rekening": True,
               "created_at": now, "updated_at": now}
        await db.gl_accounts.insert_one(dict(doc))
        if await _kode_milik(eid, kode, doc["id"]):
            return doc
        await db.gl_accounts.delete_one({"id": doc["id"]})   # kalah balapan nomor → nomor berikutnya
    raise SubAkunError("Sub-akun rekening gagal dibuat karena nomornya bentrok. Ulangi.")


async def buat_subakun(rekening: Dict[str, Any], *, kode: str = "") -> str:
    """Akun buku besar rekening `rekening` (dokumen `bank_accounts`, minimal `id`). → kode akun.

    Rekening sudah ber-`gl_account_code` → kode itu (idempoten; `kode` lain → `SubAkunError`). `kode` diisi → akun PT
    yang sudah ada (diperiksa `periksa_akun_pilihan`) ditandai `is_cash` + `bank_account_id`. Kosong → sub-akun baru
    `{induk}-{NN}`. Lalu `bank_accounts.gl_account_code` ditulis bersyarat masih kosong; kalah balapan → tulisan
    sendiri dibatalkan dan kode pemenang dikembalikan. Tidak menyalakan mode PT."""
    rid = (rekening or {}).get("id") or ""
    acc = await db.bank_accounts.find_one({"id": rid}, {"_id": 0}) if rid else None
    if not acc:
        raise SubAkunError("Rekening tidak ditemukan.")
    eid = acc.get("entity_id") or ""
    kode = (kode or "").strip()
    ada = acc.get("gl_account_code") or ""
    if ada:
        if kode and kode != ada:
            raise SubAkunError(f"Rekening {acc.get('name', '')} sudah memakai akun {ada}.")
        return ada
    now = now_iso()
    if kode:
        akun = await periksa_akun_pilihan(acc, kode)
        tanda: Dict[str, Any] = {"is_cash": True, "bank_account_id": rid, "updated_at": now}
        if not akun.get("is_cash"):
            tanda["is_cash_dari_rekening"] = True   # dilepas kembali oleh `lepas_subakun`
        res = await db.gl_accounts.update_one({"id": akun["id"], "bank_account_id": {"$in": [None, "", rid]}},
                                              {"$set": tanda})
        if not res.matched_count:
            raise SubAkunError(f"Akun {kode} baru saja dipakai rekening lain. Muat ulang lalu pilih lagi.")
    else:
        sisa = await db.gl_accounts.find_one({"bank_account_id": rid, "entity_id": eid}, {"_id": 0, "code": 1})
        kode = (sisa or {}).get("code") or (await _sisip_subakun(acc))["code"]   # sisa = tautan yang terputus
    res = await db.bank_accounts.update_one({"id": rid, "gl_account_code": {"$in": [None, ""]}},
                                            {"$set": {"gl_account_code": kode, "updated_at": now}})
    if res.matched_count:
        return kode
    menang = (await db.bank_accounts.find_one({"id": rid}, {"_id": 0, "gl_account_code": 1}) or {}).get(
        "gl_account_code") or ""
    if menang != kode:
        await _lepas_akun(rid, kode)
    if menang:
        return menang
    raise SubAkunError("Akun buku besar rekening gagal ditautkan. Muat ulang lalu ulangi.")


async def _lepas_akun(rekening_id: str, kode: str) -> None:
    """Lepas tautan akun `kode` dari rekening: akun buatan sistem yang belum dipakai jurnal dihapus, akun PT pilihan
    Finance dikembalikan (tanda rekening dan tanda kas yang dipasang `buat_subakun` dicabut)."""
    async for a in db.gl_accounts.find({"bank_account_id": rekening_id, "code": kode}, {"_id": 0}):
        if a.get("dibuat_dari_rekening"):
            dipakai = await db.journal_entries.count_documents(
                {"entity_id": a.get("entity_id"), "lines.account_code": kode, "status": {"$ne": "void"}})
            if not dipakai:
                await db.gl_accounts.delete_one({"id": a["id"]})
            continue
        cabut: Dict[str, Any] = {"bank_account_id": ""}
        if a.get("is_cash_dari_rekening"):
            cabut.update(is_cash="", is_cash_dari_rekening="")
        await db.gl_accounts.update_one({"id": a["id"]}, {"$unset": cabut, "$set": {"updated_at": now_iso()}})


async def potret_akun_pilihan(rekening: Dict[str, Any], kode: str) -> Optional[Dict[str, Any]]:
    """Tinjauan akhir I2 — keadaan tanda (`TANDA_AKUN_PILIHAN`) akun bagan PT `kode` SEBELUM dipilih Finance untuk
    `rekening`, tanpa tulisan; disimpan di usulan pindah saldo. None = akun tidak ada di bagan PT itu."""
    akun = await db.gl_accounts.find_one({"code": kode, "entity_id": rekening.get("entity_id") or ""},
                                         {"_id": 0, "id": 1, **{f: 1 for f in TANDA_AKUN_PILIHAN}})
    if not akun:
        return None
    return {"rekening_id": rekening.get("id") or "", "kode": kode, "akun_id": akun["id"],
            "sebelum": {f: akun[f] for f in TANDA_AKUN_PILIHAN if f in akun}}


async def pulihkan_akun_pilihan(potret: Dict[str, Any]) -> None:
    """Tinjauan akhir I2 (usulan pindah saldo ditolak) — tanda akun pilihan Finance kembali PERSIS seperti `potret`
    (field yang dulu tidak ada dihapus), dan rekening dilepas dari akun itu (`gl_account_code` kosong → pratinjau
    menawarkan sub-akun buatan sistem lagi). Hanya bila akun itu masih ditautkan ke rekening tersebut."""
    rid, kode = potret.get("rekening_id") or "", potret.get("kode") or ""
    sebelum: Dict[str, Any] = potret.get("sebelum") or {}
    upd: Dict[str, Any] = {"$set": {**{f: sebelum[f] for f in TANDA_AKUN_PILIHAN if f in sebelum},
                                    "updated_at": now_iso()}}
    hapus: List[str] = [f for f in TANDA_AKUN_PILIHAN if f not in sebelum]
    if hapus:
        upd["$unset"] = {f: "" for f in hapus}
    res = await db.gl_accounts.update_one({"id": potret.get("akun_id") or "", "bank_account_id": rid}, upd)
    if res.matched_count:
        await db.bank_accounts.update_one({"id": rid, "gl_account_code": kode},
                                          {"$set": {"gl_account_code": "", "updated_at": now_iso()}})


async def lepas_subakun(rekening_id: str) -> None:
    """Pemulihan pembuatan rekening yang gagal (`bank_service.create_account`): lepas akun buku besar rekening itu."""
    acc = await db.bank_accounts.find_one({"id": rekening_id}, {"_id": 0, "gl_account_code": 1}) or {}
    kode = acc.get("gl_account_code") or ""
    if not kode:
        sisa = await db.gl_accounts.find_one({"bank_account_id": rekening_id}, {"_id": 0, "code": 1})
        kode = (sisa or {}).get("code") or ""
    if kode:
        await _lepas_akun(rekening_id, kode)


async def ikut_nama_rekening(rekening: Dict[str, Any], nama: str) -> None:
    """Nama sub-akun buatan sistem mengikuti nama rekening (kodenya tetap). Akun PT pilihan Finance tidak disentuh."""
    kode = rekening.get("gl_account_code") or ""
    nama = (nama or "").strip()
    if not kode or not nama:
        return
    await db.gl_accounts.update_one(
        {"code": kode, "entity_id": rekening.get("entity_id") or "", "bank_account_id": rekening.get("id") or "",
         "dibuat_dari_rekening": True},
        {"$set": {"name": nama, "description": f"Akun buku besar rekening {nama}", "updated_at": now_iso()}})
