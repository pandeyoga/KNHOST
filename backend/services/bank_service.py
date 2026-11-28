"""Bank/Cash Accounts service (EPIC7-B) — multi-akun kas & bank + rekonsiliasi.

Koleksi kanonik: `bank_accounts` (master akun). Mutasi tetap memakai
`cash_transactions` (SSOT kas) dengan field opsional `account_id` yang
menautkan transaksi ke akun. Saldo akun = opening_balance + Σ(in) − Σ(out)
transaksi posted (non-void) milik akun tsb.

PK-21 (SL-10) — status "terekonsiliasi" punya SATU sumber: alokasi mutasi bank (`bank_recon_service`, field
`reconciled_amount`). Saldo terekonsiliasi & jumlah "belum dicocokkan" diturunkan dari angka itu
(`bank_recon_service.txn_reconciled`); tanda manual `reconciled` ya/tidak sudah dihapus (endpoint → 410).
"""
from typing import Any, Dict, List, Optional

from db import db
from core_utils import new_id, now_iso, safe_doc, DEFAULT_ENTITY_ID
from services.bank_recon_service import txn_reconciled

VALID_ACCOUNT_TYPES = {"bank", "cash"}
#: Jenis kas rekening. Kas & Bank 3 (C1) — `kas_kasir` jenis ketiga (rekening tunai uang pelanggan, akun 1-1105);
#: rekening lama tidak dikonversi.
CASH_TYPES = {"kas_kecil", "kas_besar", "kas_kasir"}
#: Dua jenis kas sebelum Kas & Bank 3 — dasar pengisian `cash_type` rekening lama (`backfill_cash_type`).
_JENIS_LAMA = ("kas_kecil", "kas_besar")

PESAN_JENIS_KAS = "Jenis kas harus kas kecil, kas kasir, atau kas besar."
PESAN_KASIR_TUNAI = "Kas kasir hanya untuk rekening kas tunai, bukan rekening bank."
PESAN_DANA_TETAP_NEGATIF = "Dana tetap tidak boleh negatif."
PESAN_DANA_TETAP_KAS_KECIL = "Dana tetap hanya untuk rekening kas kecil."
PESAN_LOKASI_JENIS = "Lokasi hanya untuk rekening kas kasir dan kas kecil."
PESAN_LOKASI_TIDAK_ADA = "Lokasi kerja yang dipilih tidak ditemukan."
#: Kas & Bank 3 (§7.8 butir 5) — jenis kas rekening yang boleh berlokasi kerja.
JENIS_BERLOKASI = ("kas_kasir", "kas_kecil")


def account_cash_type(acc: Dict[str, Any]) -> str:
    """G3 D4-CASH-01 — jenis kas TETAP dari master rekening (bukan dari transaksi aktif): `kas_besar`, `kas_kecil`, atau
    `kas_kasir` (Kas & Bank 3). Tanpa `cash_type` tersimpan → dari `account_type` seperti dulu (tunai = kas kecil)."""
    ct = acc.get("cash_type")
    if ct in CASH_TYPES:
        return ct
    return "kas_kecil" if acc.get("account_type") == "cash" else "kas_besar"


async def backfill_cash_type() -> int:
    """Isi `cash_type` rekening lama SEKALI (hanya yang belum punya): mayoritas jenis kas riwayat
    transaksinya (termasuk void), bila tak ada riwayat → dari `account_type`. Rekening lama hanya mengenal dua jenis
    kas lama (`_JENIS_LAMA`); kas kasir selalu dipilih eksplisit saat rekening dibuat."""
    n = 0
    async for acc in db.bank_accounts.find({"cash_type": {"$nin": list(CASH_TYPES)}}, {"_id": 0}):
        counts = {ct: await db.cash_transactions.count_documents({"account_id": acc["id"], "cash_type": ct})
                  for ct in _JENIS_LAMA}
        if counts["kas_kecil"] or counts["kas_besar"]:
            ct = "kas_kecil" if counts["kas_kecil"] > counts["kas_besar"] else "kas_besar"
            src = "backfill_history"
        else:
            ct, src = account_cash_type(acc), "backfill_account_type"
        res = await db.bank_accounts.update_one(
            {"id": acc["id"], "cash_type": {"$nin": list(CASH_TYPES)}},
            {"$set": {"cash_type": ct, "cash_type_source": src}})
        n += res.modified_count
    return n


# ─── PM-T1 — atas nama, peruntukan, cara bayar yang dilayani, bawaan penerimaan per PT ────────────────────────────
#: Peruntukan rekening (urutan = urutan layar). Rekening lama dianggap boleh dipakai untuk semuanya (perilaku hari ini).
PERUNTUKAN = ("penerimaan_pelanggan", "pembayaran_pemasok", "gaji", "operasional")
BIDANG_PM = ("holder_name", "purposes", "payment_method_codes", "default_receiving_methods", "show_on_documents")


def _aktif(acc: Dict[str, Any]) -> bool:
    return acc.get("is_active") is not False and acc.get("status") != "inactive"


def _jenis(acc: Dict[str, Any]) -> str:
    return "cash" if acc.get("account_type") == "cash" else "bank"


def bidang_efektif(acc: Dict[str, Any], tunggal: bool = False) -> Dict[str, Any]:
    """Nilai lima field PM-T1 yang BERLAKU untuk rekening ini. Rekening lama (field belum ada) memakai nilai awal
    spesifikasi: empat peruntukan; cara bayar menurut jenisnya; bawaan penerimaan = cara bayar pertama jenisnya HANYA
    bila ia satu-satunya rekening aktif PT untuk jenisnya (`tunggal`); atas nama kosong; tidak tampil di dokumen."""
    from services.payment_method_service import kode_awal_rekening
    kode = kode_awal_rekening(_jenis(acc))
    return {
        "holder_name": acc.get("holder_name", ""),
        "purposes": list(acc["purposes"]) if "purposes" in acc else list(PERUNTUKAN),
        "payment_method_codes": list(acc["payment_method_codes"]) if "payment_method_codes" in acc else list(kode),
        "default_receiving_methods": (list(acc["default_receiving_methods"]) if "default_receiving_methods" in acc
                                      else (kode[:1] if tunggal and _aktif(acc) else [])),
        "show_on_documents": bool(acc.get("show_on_documents", False)),
    }


async def rekening_pt(entity_id: str) -> List[Dict[str, Any]]:
    """Semua rekening PT + `_efektif` (field PM-T1 yang berlaku). Ketunggalan dihitung per jenis di antara yang aktif."""
    accs = await db.bank_accounts.find({"entity_id": entity_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    hitung: Dict[str, int] = {}
    for a in accs:
        if _aktif(a):
            hitung[_jenis(a)] = hitung.get(_jenis(a), 0) + 1
    for a in accs:
        a["_efektif"] = bidang_efektif(a, tunggal=hitung.get(_jenis(a), 0) == 1)
    await _bawaan_tunai_kasir(entity_id, accs)
    return accs


async def _bawaan_tunai_kasir(entity_id: str, accs: List[Dict[str, Any]]) -> None:
    """Kas & Bank 3 (C1, keputusan pemilik: uang tunai pelanggan masuk kas kasir; ketetapan pengendali R4) — bawaan
    penerimaan TUNAI yang BERLAKU (`_efektif`, tidak ditulis) di PT yang punya rekening kas kasir aktif penerima:

    * bawaan tunai yang tersimpan di rekening BUKAN kas kasir tidak berlaku (juga yang ditulis isi awal PM-T1 saat kas
      kecil lama masih satu-satunya rekening tunai — mis. tepat sebelum rekening kasir pertama dibuat dari layar);
    * tepat satu kas kasir penerima cara bayar itu → kasir itu bawaannya;
    * dua kas kasir penerima atau lebih → bawaan tersimpan di salah satu kasir berlaku, selain itu tanpa bawaan (kasir
      memilih rekening).
    PT tanpa kas kasir aktif: tidak berubah sama sekali."""
    kasir = [a for a in accs if _aktif(a) and account_cash_type(a) == "kas_kasir"]
    if not kasir:
        return
    from services import payment_method_service as pms
    for kode in sorted({k for a in kasir for k in a["_efektif"]["payment_method_codes"]}):
        if not await pms.is_cash(entity_id, kode):
            continue
        penerima = [a for a in kasir if "penerimaan_pelanggan" in a["_efektif"]["purposes"]
                    and kode in a["_efektif"]["payment_method_codes"]]
        if not penerima:
            continue
        for a in accs:
            e = a["_efektif"]
            if account_cash_type(a) != "kas_kasir" and kode in e["default_receiving_methods"]:
                e["default_receiving_methods"] = [m for m in e["default_receiving_methods"] if m != kode]
        if len(penerima) == 1 and kode not in penerima[0]["_efektif"]["default_receiving_methods"]:
            penerima[0]["_efektif"]["default_receiving_methods"].append(kode)


async def isi_awal_bidang_rekening(tulis: bool = False, entity_id: str = "") -> Dict[str, Any]:
    """PM-T1 — pengisian awal field baru rekening LAMA (idempoten). Hanya field yang BELUM ada yang diisi (syarat
    `$exists: False`), dengan nilai `bidang_efektif`. `tulis=False` (bawaan) = lapor saja.

    Bawaan penerimaan yang akan berbenturan dengan rekening lain PT itu (yang sudah bawaan untuk cara bayar yang sama)
    diisi `[]` — satu bawaan per (PT, cara bayar), dijaga indeks unik `uq_default_receiving`."""
    q: Dict[str, Any] = {"$or": [{f: {"$exists": False}} for f in BIDANG_PM]}
    if entity_id:
        q["entity_id"] = entity_id
    pts = sorted({a.get("entity_id") or "" async for a in db.bank_accounts.find(q, {"_id": 0, "entity_id": 1})})
    rincian: List[Dict[str, Any]] = []
    diubah = 0
    for eid in pts:
        accs = await rekening_pt(eid)
        terpakai = {m for a in accs if "default_receiving_methods" in a for m in a["default_receiving_methods"]}
        for a in accs:
            hilang = [f for f in BIDANG_PM if f not in a]
            if not hilang:
                continue
            isi = {f: a["_efektif"][f] for f in hilang}
            if "default_receiving_methods" in isi:
                isi["default_receiving_methods"] = [m for m in isi["default_receiving_methods"] if m not in terpakai]
                terpakai |= set(isi["default_receiving_methods"])
            rincian.append({"entity_id": eid, "account_id": a["id"], "name": a.get("name", ""), "isi": isi})
            if tulis:
                res = await db.bank_accounts.update_one(
                    {"id": a["id"], **{f: {"$exists": False} for f in hilang}}, {"$set": isi})
                diubah += res.modified_count
    return {"mode": "tulis" if tulis else "lapor", "diperiksa": len(rincian),
            "diubah": diubah if tulis else 0, "rincian": rincian}


def _posted(txn: Dict[str, Any]) -> bool:
    return txn.get("status") != "void"


async def sole_account_id(entity_id: str, cash_type: str) -> str:
    """Rekening SATU-SATUNYA milik PT untuk jenis kas ini (kas kecil / kas kasir / kas besar-bank), atau "" bila 0 /
    lebih dari 1."""
    if not entity_id or cash_type not in CASH_TYPES:
        return ""
    # PM-T1 — rekening dinonaktifkan lewat `is_active: False` (field `status` tidak pernah diisi layar ini).
    accs = [a async for a in db.bank_accounts.find({"entity_id": entity_id, "is_active": {"$ne": False},
                                                    "status": {"$ne": "inactive"}},
                                                    {"_id": 0, "id": 1, "cash_type": 1, "account_type": 1})]
    ids = [a["id"] for a in accs if account_cash_type(a) == cash_type]
    return ids[0] if len(ids) == 1 else ""


async def _txns_for(account_id: str) -> List[Dict[str, Any]]:
    """Mutasi rekening. UAT 24 Okt (audit UI 060↔061) — transaksi kas TANPA rekening (kas manual lama, kwitansi,
    refund) dulu tidak masuk saldo rekening mana pun sehingga saldo rekening ≠ ringkasan kas. Bila rekening ini
    satu-satunya rekening PT untuk jenis kasnya, transaksi tanpa rekening milik PT & jenis kas itu ikut dihitung."""
    acc = await db.bank_accounts.find_one({"id": account_id}, {"_id": 0, "id": 1, "entity_id": 1, "cash_type": 1,
                                                                "account_type": 1}) or {}
    q: Dict[str, Any] = {"account_id": account_id, "status": {"$ne": "void"}}
    ct = account_cash_type(acc) if acc else ""
    if acc and await sole_account_id(acc.get("entity_id") or "", ct) == account_id:
        q = {"status": {"$ne": "void"}, "$or": [
            {"account_id": account_id},
            {"account_id": {"$in": [None, ""]}, "entity_id": acc.get("entity_id"), "cash_type": ct}]}
    return await db.cash_transactions.find(q, {"_id": 0}).sort("txn_date", -1).to_list(None)   # W2-021 — SELURUH mutasi


def _balance(opening: float, txns: List[Dict[str, Any]], reconciled_only: bool = False) -> float:
    bal = float(opening or 0)
    for t in txns:
        if reconciled_only and not txn_reconciled(t):   # PK-21 — dari angka pencocokan, bukan tanda tersimpan
            continue
        amt = float(t.get("amount", 0) or 0)
        bal += amt if t.get("direction") == "in" else -amt
    return round(bal, 2)


def _enrich(acc: Dict[str, Any], txns: List[Dict[str, Any]]) -> Dict[str, Any]:
    opening = float(acc.get("opening_balance", 0) or 0)
    inflow = round(sum(float(t.get("amount", 0) or 0) for t in txns if t.get("direction") == "in"), 2)
    outflow = round(sum(float(t.get("amount", 0) or 0) for t in txns if t.get("direction") == "out"), 2)
    reconciled = sum(1 for t in txns if txn_reconciled(t))   # PK-21
    return {
        **acc,
        "balance": _balance(opening, txns),
        "reconciled_balance": _balance(opening, txns, reconciled_only=True),
        "inflow": inflow,
        "outflow": outflow,
        "txn_count": len(txns),
        "unreconciled_count": len(txns) - reconciled,
    }


async def list_accounts(entity_id: Optional[str] = None,
                        scope: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = dict(scope) if scope is not None else {}
    if scope is None and entity_id and entity_id != "all":
        q["entity_id"] = entity_id
    accounts = await db.bank_accounts.find(q, {"_id": 0}).sort("created_at", 1).to_list(500)
    efektif: Dict[str, Dict[str, Any]] = {}   # PM-T1 — field atas nama/peruntukan/cara bayar yang BERLAKU
    for eid in sorted({a.get("entity_id") or "" for a in accounts}):
        for a in await rekening_pt(eid):
            efektif[a["id"]] = a["_efektif"]
    akun = await _akun_buku_besar(accounts)
    kas = await _bidang_kas(accounts)
    out = []
    for acc in accounts:
        txns = await _txns_for(acc["id"])
        out.append({**_enrich(acc, txns), **efektif.get(acc["id"], bidang_efektif(acc)), **akun(acc),
                    **await kas(acc, txns)})
    return out


# ─── Kas & Bank 3 (Tugas 1) — jenis kas terkunci, dana tetap & lokasi rekening, jarak opname ───────────────────────
async def _bidang_kas(accounts: List[Dict[str, Any]]):
    """Kolom layar Rekening (Kas & Bank 3): `dana_tetap` (0 = tidak memakai dana tetap; rekening lama tanpa bidang = 0),
    `location_id` + `location_name` (lokasi kerja `warehouse_sites`), `jenis_kas_terkunci` (jenis kas tidak bisa
    diubah lagi — `alasan_jenis_kas_terkunci`). Dokumen rekening lama tidak ditulis."""
    ids = sorted({a.get("location_id") for a in accounts if a.get("location_id")})
    nama = {s["id"]: s.get("name") or "" async for s in db.warehouse_sites.find({"id": {"$in": ids}},
                                                                                 {"_id": 0, "id": 1, "name": 1})}

    async def bidang(acc: Dict[str, Any], txns: List[Dict[str, Any]]) -> Dict[str, Any]:
        lokasi = acc.get("location_id") or ""
        return {"dana_tetap": round(float(acc.get("dana_tetap") or 0), 2), "location_id": lokasi,
                "location_name": nama.get(lokasi, ""),
                "jenis_kas_terkunci": bool(await alasan_jenis_kas_terkunci(acc, txns))}
    return bidang


async def punya_kas(acc: Dict[str, Any], txns: Optional[List[Dict[str, Any]]] = None) -> bool:
    """Rekening sudah punya transaksi kas: saldo awal (terjurnal), dokumen kas ber-`account_id` rekening ini (termasuk
    yang dibatalkan — jurnal dan pembaliknya tetap di akun jenis kas lama), atau kas tanpa rekening yang ikut buku kas
    rekening tunggal jenisnya (`_txns_for`). `txns` = hasil `_txns_for` yang sudah dibaca pemanggil (hemat kueri)."""
    if abs(float(acc.get("opening_balance") or 0)) > 0.005 or acc.get("opening_je_id"):
        return True
    if await db.cash_transactions.find_one({"account_id": acc.get("id") or "__none__"}, {"_id": 0, "id": 1}):
        return True
    return bool(txns if txns is not None else await _txns_for(acc.get("id") or ""))


async def alasan_jenis_kas_terkunci(acc: Dict[str, Any], txns: Optional[List[Dict[str, Any]]] = None) -> str:
    """Kas & Bank 3 (spesifikasi §5.1) — kalimat alasan jenis kas rekening tidak bisa diubah; "" = boleh diubah.

    * Akun buku besar rekening sudah ada (PT mode per rekening): sub-akunnya dibuat di bawah induk jenis kas itu
      (`cash_account_mode.INDUK`) dan kodenya tidak pernah berubah — mengganti jenis membuat akun di induk yang salah.
    * Rekening sudah punya transaksi kas (`punya_kas`): jurnal lamanya ada di akun jenis kas lama — mengganti jenis
      membuat buku kas rekening ≠ buku besar. Saldo dipindah lewat Pindah Dana ke rekening baru."""
    nama = acc.get("name") or ""
    kode = acc.get("gl_account_code") or ""
    if kode:
        return (f"Jenis kas rekening {nama} tidak bisa diubah karena akun buku besarnya ({kode}) dibuat untuk jenis "
                f"kas itu. Nonaktifkan rekening ini lalu buat rekening baru dengan jenis kas yang benar.")
    if await punya_kas(acc, txns):
        return (f"Jenis kas rekening {nama} tidak bisa diubah karena rekening ini sudah punya transaksi kas. "
                f"Pindahkan saldonya lewat Pindah Dana ke rekening baru dengan jenis kas yang benar.")
    return ""


async def periksa_bidang_kas(acc: Dict[str, Any]) -> Dict[str, Any]:
    """Kas & Bank 3 — PERIKSA (tanpa tulisan) jenis kas, dana tetap, dan lokasi rekening `acc` (nilai SESUDAH perubahan,
    digabung dengan isi rekening). → `{cash_type, dana_tetap, location_id}` bersih. Gagal → `ValueError` berkalimat.

    * `cash_type` ∈ `CASH_TYPES`; kosong = dari `account_type` (seperti dulu). Kas kasir hanya untuk rekening tunai.
    * `dana_tetap` ≥ 0; > 0 hanya untuk rekening kas kecil (0 = tidak memakai dana tetap).
    * `location_id` opsional: lokasi kerja yang ada (`warehouse_sites`), hanya untuk kas kasir & kas kecil; satu
      rekening kas kecil aktif per lokasi per PT."""
    ct = (acc.get("cash_type") or "").strip()
    if ct and ct not in CASH_TYPES:
        raise ValueError(PESAN_JENIS_KAS)
    ct = ct or account_cash_type({"account_type": acc.get("account_type")})
    if ct == "kas_kasir" and acc.get("account_type") != "cash":
        raise ValueError(PESAN_KASIR_TUNAI)
    try:
        dana = round(float(acc.get("dana_tetap") or 0), 2)
    except (TypeError, ValueError):
        raise ValueError(PESAN_DANA_TETAP_NEGATIF)
    if dana < 0:
        raise ValueError(PESAN_DANA_TETAP_NEGATIF)
    if dana > 0 and ct != "kas_kecil":
        raise ValueError(PESAN_DANA_TETAP_KAS_KECIL)
    lokasi = str(acc.get("location_id") or "").strip()
    if lokasi:
        if ct not in JENIS_BERLOKASI:
            raise ValueError(PESAN_LOKASI_JENIS)
        site = await db.warehouse_sites.find_one({"id": lokasi}, {"_id": 0, "name": 1})
        if not site:
            raise ValueError(PESAN_LOKASI_TIDAK_ADA)
        if ct == "kas_kecil" and _aktif(acc):
            eid = acc.get("entity_id") or ""
            async for lain in db.bank_accounts.find({"entity_id": eid, "location_id": lokasi,
                                                     "id": {"$ne": acc.get("id") or ""}}, {"_id": 0}):
                if _aktif(lain) and account_cash_type(lain) == "kas_kecil":
                    from services.cash_ledger import _nama_pt
                    raise ValueError(f"Lokasi {site.get('name') or lokasi} sudah punya rekening kas kecil "
                                     f"{lain.get('name', '')} di {await _nama_pt(eid)}. Satu lokasi hanya untuk satu "
                                     f"rekening kas kecil.")
    return {"cash_type": ct, "dana_tetap": dana, "location_id": lokasi}


#: Kas & Bank 3 (C3) — pengaturan jarak opname per jenis kas rekening tunai (`config_catalog_bank.py`).
KUNCI_OPNAME_HARI = {"kas_kasir": "kas.opname_kasir_hari", "kas_kecil": "kas.opname_kas_kecil_hari",
                     "kas_besar": "kas.opname_kas_besar_hari"}


async def hari_opname(entity_id: str, cash_type: str) -> int:
    """Kas & Bank 3 — jarak opname (hari) rekening berjenis kas `cash_type` di PT `entity_id`: rekening tunai yang
    opname terakhirnya lebih lama dari ini = jatuh tempo (pengingat Meja Keuangan). Jenis tak dikenal → `KeyError`."""
    from services.config_resolver import value_of
    return int(await value_of(KUNCI_OPNAME_HARI[cash_type], {"entity_id": entity_id}))


async def _akun_buku_besar(accounts: List[Dict[str, Any]]):
    """Kas & Bank 1 (Tugas 6, layar Rekening) — kolom "Akun buku besar" (kode + nama akun bagan PT) dan penanda PT
    yang belum memakai akun per rekening. → fungsi rekening → `{gl_account_name, akun_per_rekening_aktif,
    akun_per_rekening_sejak}`. Kode akun tetap dari `gl_account_code` rekening (hanya-baca)."""
    from services import cash_account_mode as _mode
    sejak = {eid: await _mode.aktif_sejak(eid) for eid in sorted({a.get("entity_id") or "" for a in accounts})}
    pasang = sorted({(a.get("entity_id") or "", a["gl_account_code"]) for a in accounts if a.get("gl_account_code")})
    nama: Dict[tuple, str] = {}
    if pasang:
        async for g in db.gl_accounts.find({"$or": [{"entity_id": e, "code": c} for e, c in pasang]},
                                           {"_id": 0, "entity_id": 1, "code": 1, "name": 1}):
            nama[(g.get("entity_id") or "", g.get("code") or "")] = g.get("name") or ""

    def bidang(acc: Dict[str, Any]) -> Dict[str, Any]:
        eid = acc.get("entity_id") or ""
        return {"gl_account_name": nama.get((eid, acc.get("gl_account_code") or ""), ""),
                "akun_per_rekening_aktif": bool(sejak.get(eid)), "akun_per_rekening_sejak": sejak.get(eid) or ""}
    return bidang


async def unlinked_transactions(entity_ids: List[str]) -> Dict[str, Any]:
    """Transaksi kas (non-void) yang TIDAK masuk saldo rekening mana pun: tanpa `account_id` dan tidak terserap
    rekening tunggal PT untuk jenis kasnya (aturan `_txns_for`). Penjelas selisih buku besar vs total rekening."""
    out = {"count": 0, "inflow": 0.0, "outflow": 0.0, "net": 0.0}
    if not entity_ids:
        return out
    sole: Dict[Any, str] = {}
    q = {"entity_id": {"$in": list(entity_ids)}, "status": {"$ne": "void"},
         "$or": [{"account_id": {"$exists": False}}, {"account_id": {"$in": [None, ""]}}]}
    async for t in db.cash_transactions.find(q, {"_id": 0, "entity_id": 1, "cash_type": 1, "amount": 1,
                                                 "direction": 1}):
        key = (t.get("entity_id") or "", t.get("cash_type") or "")
        if key not in sole:
            sole[key] = await sole_account_id(key[0], key[1]) if key[1] in CASH_TYPES else ""
        if sole[key]:
            continue   # ikut dihitung di saldo rekening tunggal PT itu
        amt = float(t.get("amount", 0) or 0)
        out["count"] += 1
        if t.get("direction") == "in":
            out["inflow"] += amt
        else:
            out["outflow"] += amt
    out["inflow"], out["outflow"] = round(out["inflow"], 2), round(out["outflow"], 2)
    out["net"] = round(out["inflow"] - out["outflow"], 2)
    return out


async def cash_position(entity_ids: List[str]) -> Dict[str, Any]:
    """Keputusan pemilik K-02 (26 Okt) — angka utama "Kas & Bank" = saldo BUKU BESAR akun kas+bank (sumber yang sama
    dengan Dasbor Keuangan & Proyeksi Arus Kas). Rekening & Saldo = rincian per rekening; selisih keduanya dijelaskan
    lewat transaksi kas yang belum tertaut ke rekening.

    Kas & Bank 1 — akun kas = `report_basis.kode_kas` (bawaan 1-1100/1-1110 + pemetaan + akun `is_cash`, termasuk
    sub-akun rekening). Baris: dua akun bawaan selalu tampil; akun kas lain tampil bila pernah dijurnal."""
    from services import financial_statement_service as fs
    from services import report_basis as rb
    from services.cash_flow_service import CASH_CODES
    scope = {"entity_id": {"$in": list(entity_ids or [])}}
    amap = await fs._accounts_map(scope)   # noqa: SLF001 — helper laporan yang sama dipakai Dasbor Keuangan
    agg = await fs._aggregate(scope, None, include_closing=True)   # noqa: SLF001
    kas = await rb.kode_kas(scope)
    lines, total = [], 0.0
    for code in sorted(set(CASH_CODES) | {c for c in kas if c in agg}):
        v = agg.get(code, {"debit": 0.0, "credit": 0.0})
        bal = round(float(v.get("debit", 0) or 0) - float(v.get("credit", 0) or 0), 2)
        total += bal
        lines.append({"code": code, "name": amap.get(code, {}).get("name", code), "balance": bal})
    return {"gl_total": round(total, 2), "gl_accounts": lines,
            "unlinked": await unlinked_transactions(entity_ids or []),
            "source_label": "Saldo buku besar akun kas & bank"}


async def _cabut_bawaan_lain(entity_id: str, account_id: str, methods: List[str]) -> None:
    """PM-T1 — satu bawaan penerimaan per (PT, cara bayar): rekening lain PT itu kehilangan tanda bawaan cara bayar
    yang sama (operasi yang sama dengan penulisan rekening ini)."""
    if not methods:
        return
    await db.bank_accounts.update_many(
        {"entity_id": entity_id, "id": {"$ne": account_id}, "default_receiving_methods": {"$in": list(methods)}},
        {"$pull": {"default_receiving_methods": {"$in": list(methods)}}})


async def _tulis_bawaan(entity_id: str, account_id: str, methods: List[str], tulis) -> Any:
    """Cabut bawaan lain lalu `tulis()`; benturan indeks unik (dua permintaan bersamaan) → ulangi (paling banyak 3×)."""
    from pymongo.errors import DuplicateKeyError
    for percobaan in range(3):
        await _cabut_bawaan_lain(entity_id, account_id, methods)
        try:
            return await tulis()
        except DuplicateKeyError:
            if percobaan == 2:
                raise
    return None


async def periksa_akun_rekening_baru(entity_id: str, kode: str, account_id: str = "") -> None:
    """Kas & Bank 1 — PERIKSA (tanpa tulisan) akun buku besar pilihan Finance untuk rekening BARU: hanya di PT yang sudah
    memakai akun per rekening, akunnya layak (`cash_account_mode.periksa_akun_pilihan`), dan belum berjurnal (rekening
    baru bersaldo awal sendiri; saldo/riwayat akun lama tidak ikut buku kas rekening — tinjauan T1 I1). Kosong = lolos
    (sistem membuat sub-akun bila PT aktif). Gagal → `ValueError` berkalimat."""
    from services import cash_account_mode as _mode
    kode = (kode or "").strip()
    if not kode:
        return
    if not await _mode.aktif(entity_id):
        from services.cash_ledger import _nama_pt
        raise ValueError(f"{await _nama_pt(entity_id)} belum memakai akun buku besar per rekening. Kosongkan pilihan "
                         f"akun buku besar; akun rekening diatur saat pindah saldo PT ini.")
    await _mode.periksa_akun_pilihan({"entity_id": entity_id, "id": account_id}, kode)
    if await db.journal_entries.find_one({"entity_id": entity_id, "lines.account_code": kode,
                                          "status": {"$ne": "void"}}, {"_id": 0, "id": 1}):
        raise ValueError(f"Akun {kode} sudah punya saldo atau riwayat jurnal. Pilih akun yang masih kosong, atau "
                         f"kosongkan pilihan supaya sistem membuat sub-akun rekening.")


async def create_account(payload, actor: Dict[str, Any], bidang: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """`bidang` = field PM-T1 yang sudah diperiksa (`bank_account_change_service.periksa_isian`).

    Kas & Bank 3 — jenis kas (`kas_kecil` / `kas_kasir` / `kas_besar`), dana tetap, dan lokasi diperiksa
    `periksa_bidang_kas` (sekali lagi saat diterapkan; pengajuan bisa diputus lama sesudah diajukan)."""
    if payload.account_type not in VALID_ACCOUNT_TYPES:
        raise ValueError("account_type harus 'bank' atau 'cash'")
    doc = {
        "id": new_id("bank"),
        "name": payload.name.strip(),
        "account_type": payload.account_type,
        "cash_type": "",
        "cash_type_source": "explicit",
        "bank_name": (payload.bank_name or "").strip(),
        "account_number": (payload.account_number or "").strip(),
        "entity_id": payload.entity_id or DEFAULT_ENTITY_ID,
        "opening_balance": round(float(payload.opening_balance or 0), 2),
        "currency": payload.currency or "IDR",
        "note": (payload.note or "").strip(),
        "is_active": True,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    kas = await periksa_bidang_kas({**doc, "cash_type": getattr(payload, "cash_type", "") or "",
                                    "dana_tetap": getattr(payload, "dana_tetap", 0) or 0,
                                    "location_id": getattr(payload, "location_id", "") or ""})
    doc.update(kas)
    doc.update(bidang or bidang_efektif(doc))
    from services import cash_account_mode as _mode
    from services import gl_service as _gl
    # Kas & Bank 1 (D1) — PT yang sudah memakai akun per rekening: rekening baru langsung mendapat akun buku besarnya
    # (sub-akun baru, atau akun PT pilihan Finance) dan saldo awalnya dijurnal ke akun itu. PT belum aktif: seperti dulu.
    kode_pilih = (getattr(payload, "gl_account_code", "") or "").strip()
    per_rekening = await _mode.aktif(doc["entity_id"])
    await periksa_akun_rekening_baru(doc["entity_id"], kode_pilih, doc["id"])   # PERIKSA sebelum rekening tertulis
    if doc["opening_balance"]:
        await _gl.preflight_posting(doc["entity_id"], now_iso())
    await _tulis_bawaan(doc["entity_id"], doc["id"], doc.get("default_receiving_methods") or [],
                        lambda: db.bank_accounts.insert_one(dict(doc)))
    try:
        if per_rekening:
            doc["gl_account_code"] = await _mode.buat_subakun(doc, kode=kode_pilih)
        je = await _post_opening(doc, doc["opening_balance"], "bank_opening_balance", doc["id"])
    except Exception:
        if per_rekening:
            await _mode.lepas_subakun(doc["id"])
        await db.bank_accounts.delete_one({"id": doc["id"]})  # FN-08 — rekening + jurnal pembukaan satu operasi
        raise
    if je:
        await db.bank_accounts.update_one({"id": doc["id"]}, {"$set": {"opening_je_id": je["id"]}})
        doc["opening_je_id"] = je["id"]
    return _enrich(safe_doc(doc), [])


OPENING_EQUITY_ACC = "3-2900"


async def _post_opening(acc: Dict[str, Any], amount: float, source_type: str, source_id: str):
    """FN-08 — saldo awal rekening terikat GL: Dr Kas/Bank ↔ Cr Ekuitas Saldo Awal (tanda dibalik bila negatif).
    Kas & Bank 1 — akun kas lewat `gl_service.akun_kas`: sub-akun rekening di PT yang sudah memakai akun per rekening,
    selain itu akun menurut JENIS REKENING seperti dulu (tunai → 1-1110, bank → 1-1100); rekening kas kasir → 1-1105
    (Kas & Bank 3)."""
    from services import gl_service as _gl
    amt = round(float(amount or 0), 2)
    if abs(amt) <= 0.005:
        return None
    # Kas & Bank 3 — rekening kas kasir → akun kas kasir; selain itu menurut `account_type` persis seperti dulu.
    jenis = ("kas_kasir" if account_cash_type(acc) == "kas_kasir"
             else "kas_kecil" if acc.get("account_type") == "cash" else "kas_besar")
    cash_acc = await _gl.akun_kas(acc.get("entity_id") or DEFAULT_ENTITY_ID, acc.get("id") or "", jenis)
    dr, cr = (cash_acc, OPENING_EQUITY_ACC) if amt > 0 else (OPENING_EQUITY_ACC, cash_acc)
    await _gl.seed_default_coa()
    return await _gl._insert_entry(
        lines=[{"account_code": dr, "debit": abs(amt), "credit": 0.0, "description": f"Saldo awal {acc['name']}"},
               {"account_code": cr, "debit": 0.0, "credit": abs(amt), "description": f"Saldo awal {acc['name']}"}],
        description=f"Saldo awal rekening {acc['name']}", date=now_iso(), source_type=source_type,
        source_id=source_id, entity_id=acc.get("entity_id") or DEFAULT_ENTITY_ID, created_by="system",
        source_label=acc["name"])


class RekeningBerubah(ValueError):
    """PM-T1 — nilai yang diajukan sudah tidak sama dengan isi rekening sekarang (409)."""


async def update_account(account_id: str, patch: Dict[str, Any],
                         syarat: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """`syarat` (PM-T1) = nilai lama yang harus masih tersimpan (persetujuan perubahan) — beda → `RekeningBerubah`."""
    acc = await db.bank_accounts.find_one({"id": account_id, **(syarat or {})}, {"_id": 0})
    if not acc:
        if syarat and await db.bank_accounts.find_one({"id": account_id}, {"_id": 0, "id": 1}):
            raise RekeningBerubah("Perubahan rekening ini sudah diputus atau datanya sudah berubah. Ajukan ulang.")
        return None
    upd = {k: v for k, v in patch.items() if v is not None}
    if {"cash_type", "dana_tetap", "location_id", "is_active"} & set(upd):
        # Kas & Bank 3 — jenis kas / dana tetap / lokasi diperiksa pada nilai SESUDAH perubahan; jenis kas terkunci
        # sesudah rekening punya kas (diperiksa lagi saat diterapkan: kas bisa tercatat di sela pengajuan).
        kas = await periksa_bidang_kas({**acc, **upd})
        if "cash_type" in upd and kas["cash_type"] != account_cash_type(acc):
            alasan = await alasan_jenis_kas_terkunci(acc)
            if alasan:
                raise ValueError(alasan)
        upd.update({f: kas[f] for f in ("cash_type", "dana_tetap", "location_id") if f in upd})
        if "cash_type" in upd:
            upd["cash_type_source"] = "explicit"
    if "opening_balance" in upd:
        upd["opening_balance"] = round(float(upd["opening_balance"]), 2)
        delta = round(upd["opening_balance"] - float(acc.get("opening_balance") or 0), 2)
        if abs(delta) > 0.005:
            # FN-08 — saldo awal terkunci pada jurnal; koreksi = jurnal penyesuaian selisih (bukan edit diam-diam).
            if not acc.get("opening_je_id") and float(acc.get("opening_balance") or 0):
                raise ValueError("Saldo awal lama rekening ini belum terjurnal — koreksi lewat jurnal manual "
                                 "(Dr/Cr Kas-Bank ↔ 3-2900) oleh Keuangan, bukan edit saldo awal.")
            from services import gl_service as _gl
            await _gl.preflight_posting(acc.get("entity_id") or DEFAULT_ENTITY_ID, now_iso())
            n = await db.journal_entries.count_documents({"source_type": "bank_opening_adjustment",
                                                          "source_id": {"$regex": f"^{account_id}:"}})
            je = await _post_opening({**acc, **upd}, delta, "bank_opening_adjustment", f"{account_id}:{n + 1}")
            if not acc.get("opening_je_id") and je:
                upd["opening_je_id"] = je["id"]
        else:
            upd.pop("opening_balance")
    if "name" in upd:
        upd["name"] = str(upd["name"]).strip()
    upd["updated_at"] = now_iso()
    flt = {"id": account_id, **(syarat or {})}

    async def _tulis():
        res = await db.bank_accounts.update_one(flt, {"$set": upd})
        if syarat and not res.matched_count:
            raise RekeningBerubah("Perubahan rekening ini sudah diputus atau datanya sudah berubah. Ajukan ulang.")
        return res
    await _tulis_bawaan(acc.get("entity_id") or "", account_id, upd.get("default_receiving_methods") or [], _tulis)
    acc = await db.bank_accounts.find_one({"id": account_id}, {"_id": 0})
    if "name" in upd and acc.get("gl_account_code"):   # Kas & Bank 1 — nama sub-akun ikut nama rekening, kode tetap
        from services import cash_account_mode as _mode
        await _mode.ikut_nama_rekening(acc, upd["name"])
    txns = await _txns_for(account_id)
    return {**_enrich(acc, txns), **bidang_efektif(acc)}


async def account_ledger(account_id: str) -> Optional[Dict[str, Any]]:
    acc = await db.bank_accounts.find_one({"id": account_id}, {"_id": 0})
    if not acc:
        return None
    txns = await _txns_for(account_id)
    # running balance (kronologis menaik)
    chron = sorted(txns, key=lambda t: (t.get("txn_date") or "", t.get("number") or ""))
    running = float(acc.get("opening_balance", 0) or 0)
    for t in chron:
        amt = float(t.get("amount", 0) or 0)
        running += amt if t.get("direction") == "in" else -amt
        t["running_balance"] = round(running, 2)
        # PK-21 — lencana layar (Terekonsiliasi / Sebagian / Belum) membaca turunan dari `reconciled_amount`; tanda
        # manual lama yang masih tersimpan tidak ditampilkan sebagai "terekonsiliasi".
        t["reconciled"] = txn_reconciled(t)
        t["reconciled_amount"] = round(float(t.get("reconciled_amount") or 0), 2)
    chron.reverse()  # tampilkan terbaru dulu
    return {**_enrich(acc, txns), "transactions": chron}
