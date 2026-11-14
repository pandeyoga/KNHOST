"""KP-T7 — pengingat terjadwal yang bisa diatur: PENERIMA dan AMBANG per PT.

Sebelum unit ini penerima tiap pengingat ditulis sebagai satu nama peran di titik kejadian
(`recipient_role="manager"`) dan ambangnya konstanta modul (hutang ≤ 7 hari, perintah kerja 3/7 hari, …). Pemilik
tidak bisa menentukan per PT siapa yang menerima maupun kapan diingatkan (KP-09, KP-20, KP-21).

Satu pintu:

* `recipients_for(reminder_id, entity_id)` — baris `{mode, roles, permission}` dari tabel `notif.reminder_recipients`:
  tabel PT (menimpa tabel utuh) → tabel grup → bawaan registry.
* `notify(reminder_id, entity_id, **kw)` — `mode="peran"` dengan SATU peran → `create_notification(recipient_role=…)`
  persis seperti sebelum unit ini (bawaan semua pengingat, sehingga tidak ada kotak masuk yang berubah saat dipasang);
  beberapa peran → `create_addressed(roles=…)`; `mode="izin"` → `create_addressed(permission=…)` (per orang, pagar PT
  dihitung saat kirim). Notifikasi untuk pemegang akun (per orang) tidak lewat sini.
* `threshold(key, entity_id)` / `per_pt(key)` — nilai ambang per PT dokumen; cadangan saat galat = bawaan registry
  (`02_STANDAR.md` §2.2). `per_pt` menyimpan sementara per PT dalam satu jalan.

Membatalkan: kosongkan `notif.reminder_recipients` (kembali ke bawaan); ambang kembali ke bawaan registry.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional



def _registry():
    """Impor malas: `config_catalog_core` mengimpor modul ini saat registry sedang dimuat (pilihan editor tabel), jadi
    `config_registry` tidak boleh diimpor di tingkat modul — bila modul ini dimuat lebih dulu (mis. skrip migrasi
    KP-T7), impor melingkar gagal."""
    import config_registry
    return config_registry

logger = logging.getLogger("reminder_policy")

KUNCI_PENERIMA = "notif.reminder_recipients"

#: Pengingat terjadwal yang penerimanya bisa diatur (id → label manusia). Urutan = urutan layar.
PENGINGAT: Dict[str, str] = {
    "ar_overdue": "Piutang jatuh tempo",
    "ar_due_soon": "Piutang mendekati jatuh tempo",
    "ap_due": "Hutang pemasok jatuh tempo",
    "depreciation_due": "Penyusutan aset belum dijalankan",
    "budget_alert": "Peringatan anggaran",
    "production_stalled": "Perintah kerja tertunda",
    "ops_stalled": "Tugas gudang tertunda",
    "po_arrival": "Barang PO datang (salinan manajer)",
    "po_arrival_gudang": "Barang PO datang (salinan gudang)",
    "backorder_ready": "Barang pendingan siap (salinan manajer)",
}
MODE_LABEL = {"peran": "Peran yang dipilih", "izin": "Semua pemegang izin"}
#: Pengingat lintas PT: notifikasinya tidak ber-PT (umur piutang seluruh pelanggan; penyusutan satu periode untuk semua
#: aset) → hanya baris GRUP yang berlaku; baris tabel PT untuk pengingat ini diabaikan.
LINTAS_PT = ("ar_overdue", "depreciation_due")

#: Bawaan = penerima yang ditulis di kode sebelum unit ini (U5: notifikasi yang lahir sama persis).
BAWAAN_PENERIMA: List[Dict[str, Any]] = [
    *({"reminder": r, "mode": "peran", "roles": ["manager"], "permission": ""}
      for r in ("ar_overdue", "ap_due", "depreciation_due", "budget_alert", "po_arrival", "backorder_ready")),
    *({"reminder": r, "mode": "peran", "roles": ["warehouse"], "permission": ""}
      for r in ("production_stalled", "ops_stalled", "po_arrival_gudang")),
    {"reminder": "ar_due_soon", "mode": "izin", "roles": [], "permission": "ar_receipt.create"},
]

#: Rantai eskalasi bawaan (dulu `escalation_service.ESCALATION_CHAIN`).
BAWAAN_ESKALASI: Dict[str, str] = {"sales": "manager", "warehouse": "manager", "manager": "admin",
                                    "all": "admin", "": "admin"}


# ═══ Pilihan untuk editor (dibaca katalog saat registry dimuat) ═══════════════
def role_options() -> List[Dict[str, str]]:
    """Peran bawaan (id → label). Peran kustom ditambahkan layar dari daftar peran yang sedang berlaku."""
    import role_registry as rr
    return [{"value": rid, "label": rr.role_label(rid, long=True)} for rid in rr.role_ids()]


def permission_options() -> List[Dict[str, str]]:
    """Semua pasangan izin yang dikenal katalog modul, berlabel Indonesia (tanpa id teknis di label)."""
    from access_modules import ACTION_LABEL, MODULE_CATALOG, RESOURCE_LABEL, full_actions
    out: List[Dict[str, str]] = []
    seen = set()
    for m in MODULE_CATALOG:
        for res in m.get("resources") or []:
            for act in full_actions(res):
                val = f"{res}.{act}"
                if val in seen:
                    continue
                seen.add(val)
                aksi = ACTION_LABEL.get(val) or ACTION_LABEL.get(act, act)
                out.append({"value": val, "label": f"{RESOURCE_LABEL.get(res, res)} — {aksi}"})
    return out


# ═══ Pemeriksa nilai saat simpan (dipanggil `config_resolver.set_value`) ══════
def _peran_ada(role: str) -> bool:
    from role_registry import is_role
    return is_role(role)


def _izin_ada(perm: str) -> bool:
    from access_modules import full_actions
    res, _, act = str(perm or "").partition(".")
    return bool(res and act) and act in full_actions(res)


def _periksa_penerima(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("Penerima tiap pengingat harus berupa daftar baris.")
    out: List[Dict[str, Any]] = []
    dipakai: Dict[str, int] = {}
    for n, row in enumerate(value, 1):
        if not isinstance(row, dict):
            raise ValueError(f"Baris {n}: isinya tidak sah.")
        rid = str(row.get("reminder") or "").strip()
        if rid not in PENGINGAT:
            raise ValueError(f"Pengingat “{rid}” tidak dikenal.")
        if rid in dipakai:
            raise ValueError(f"Baris {n}: pengingat “{PENGINGAT[rid]}” sudah ada di baris {dipakai[rid]}.")
        dipakai[rid] = n
        mode = str(row.get("mode") or "").strip()
        if mode not in MODE_LABEL:
            raise ValueError(f"Baris {n}: pilih cara menentukan penerima (“{MODE_LABEL['peran']}” atau "
                             f"“{MODE_LABEL['izin']}”).")
        if mode == "peran":
            raw = row.get("roles")
            roles = [raw] if isinstance(raw, str) else list(raw or [])
            roles = [str(r).strip() for r in roles if str(r).strip()]
            if not roles:
                raise ValueError(f"Baris {n}: pilih paling sedikit satu peran.")
            for r in roles:
                if not _peran_ada(r):
                    raise ValueError(f"Peran “{r}” tidak ada.")
            out.append({"reminder": rid, "mode": "peran", "roles": list(dict.fromkeys(roles)), "permission": ""})
        else:
            perm = str(row.get("permission") or "").strip()
            if not _izin_ada(perm):
                raise ValueError(f"Izin “{perm}” tidak ada.")
            out.append({"reminder": rid, "mode": "izin", "roles": [], "permission": perm})
    return out


def _periksa_eskalasi(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("Rantai eskalasi harus berupa pasangan peran penerima → peran di atasnya.")
    out: Dict[str, str] = {}
    for src, dst in value.items():
        src, dst = str(src or "").strip(), str(dst or "").strip()
        if src not in ("all", "") and not _peran_ada(src):
            raise ValueError(f"Peran “{src}” tidak ada.")
        if not _peran_ada(dst):
            raise ValueError(f"Peran “{dst}” tidak ada.")
        out[src] = dst
    return out


def _periksa_peran_siaran(value: Any) -> List[str]:
    roles = [str(r).strip() for r in (value or []) if str(r).strip()]
    for r in roles:
        if not _peran_ada(r):
            raise ValueError(f"Peran “{r}” tidak ada.")
    return list(dict.fromkeys(roles))


def _periksa_hari_piutang(value: Any) -> List[int]:
    out: List[int] = []
    for i, x in enumerate(value or [], 1):
        try:
            num = float(x)
        except (TypeError, ValueError):
            num = float("nan")
        if isinstance(x, bool) or num != num or num != int(num) or not -30 <= num <= 30:
            raise ValueError(f"Hari pengingat piutang butir {i} harus bilangan bulat −30 sampai 30 "
                             f"(diberi {x!r}).")
        out.append(int(num))
    return sorted(set(out))


def _periksa_nomor_pic(value: Any) -> str:
    from services import wa_alert_service as wa
    nomor = str(value or "").strip()
    if not nomor:
        return ""
    if not wa.valid_phone(nomor):
        raise ValueError("Nomor WhatsApp PIC tidak valid. Contoh: 081234567890.")
    return wa.format_id_phone(nomor)


PEMERIKSA = {
    KUNCI_PENERIMA: _periksa_penerima,
    "notif.escalation_chain": _periksa_eskalasi,
    "notif.wa_broadcast_roles": _periksa_peran_siaran,
    "notif.ar_due_soon_offsets": _periksa_hari_piutang,
    "notif.wa_pic_number": _periksa_nomor_pic,
}


def periksa_nilai(key: str, value: Any) -> Any:
    """Nilai bersih kunci KP-T7 (atau nilai apa adanya untuk kunci lain). `ValueError` berpesan siap tampil."""
    fn = PEMERIKSA.get(key)
    return fn(value) if fn else value


# ═══ Ambang ══════════════════════════════════════════════════════════════════
async def threshold(key: str, entity_id: Optional[str] = None) -> Any:
    """Nilai kunci untuk PT `entity_id` ("" = nilai grup); galat → bawaan registry (`02` §2.2)."""
    from services.config_resolver import value_of
    try:
        val = await value_of(key, {"entity_id": entity_id or ""})
    except Exception as exc:  # noqa: BLE001 — pengingat tidak boleh mati karena pengaturan
        logger.warning("[reminder_policy] %s gagal dibaca (%s) — memakai bawaan registry", key, exc)
        return _registry().default_of(key)
    return _registry().default_of(key) if val is None else val


class PerPT:
    """Ambang satu kunci, dibaca sekali per PT dalam satu jalan pengingat."""

    def __init__(self, key: str) -> None:
        self.key = key
        self._nilai: Dict[str, Any] = {}

    async def __call__(self, entity_id: Optional[str] = None) -> Any:
        eid = str(entity_id or "")
        if eid not in self._nilai:
            self._nilai[eid] = await threshold(self.key, eid)
        return self._nilai[eid]


def per_pt(key: str) -> PerPT:
    _registry().require(key)
    return PerPT(key)


async def active_entity_ids() -> List[str]:
    from db import db
    rows = await db.business_entities.find({"status": {"$ne": "inactive"}}, {"_id": 0, "id": 1}).to_list(200)
    return [r["id"] for r in rows if r.get("id")]


async def union_over_entities(key: str, ambang: PerPT, extra: Iterable[str] = ("",)) -> List[Any]:
    """Gabungan nilai daftar `key` untuk grup + semua PT aktif (mis. hari pengingat piutang)."""
    out: List[Any] = []
    for eid in [*extra, *await active_entity_ids()]:
        for v in await ambang(eid) or []:
            if v not in out:
                out.append(v)
    return out


# ═══ Penerima ════════════════════════════════════════════════════════════════
def _cari(tabel: Any, reminder_id: str) -> Optional[Dict[str, Any]]:
    for row in tabel if isinstance(tabel, list) else []:
        if isinstance(row, dict) and row.get("reminder") == reminder_id:
            return row
    return None


async def recipients_for(reminder_id: str, entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Baris `{mode, roles, permission}` pengingat itu: tabel PT → tabel grup → bawaan.

    Nilai PT `notif.reminder_recipients` menimpa tabel utuh; pengingat yang tidak ada di tabel PT memakai baris grup,
    lalu bawaan."""
    from services.config_resolver import resolve
    if reminder_id not in PENGINGAT:
        raise KeyError(f"Pengingat '{reminder_id}' tidak terdaftar di reminder_policy.PENGINGAT")
    tabel: List[Any] = []
    try:
        eid = "" if reminder_id in LINTAS_PT else str(entity_id or "")
        if eid and eid != "all":
            pt = await resolve(KUNCI_PENERIMA, {"entity_id": eid})
            if pt["source_layer"] in ("entity", "legacy_entity"):
                tabel.append(pt["value"])
        grup = await resolve(KUNCI_PENERIMA, {})
        if grup["source_layer"] != "code_default":
            tabel.append(grup["value"])
    except Exception as exc:  # noqa: BLE001 — penerima tidak boleh hilang karena pengaturan rusak
        logger.warning("[reminder_policy] penerima %s gagal dibaca (%s) — memakai bawaan", reminder_id, exc)
    tabel.append(_registry().default_of(KUNCI_PENERIMA))
    for t in tabel:
        row = _cari(t, reminder_id)
        if row:
            raw = row.get("roles")
            roles = [raw] if isinstance(raw, str) else [str(r) for r in (raw or []) if r]
            return {"reminder": reminder_id, "mode": row.get("mode") or "peran", "roles": roles,
                    "permission": str(row.get("permission") or "")}
    return {"reminder": reminder_id, "mode": "peran", "roles": [], "permission": ""}


async def notify(reminder_id: str, entity_id: Optional[str], **kw: Any) -> List[Dict[str, Any]]:
    """Kirim satu pengingat ke penerima yang berlaku untuk PT `entity_id`.

    `entity_id` juga menjadi `entity_id` notifikasi APA ADANYA (None tetap None) supaya bawaan lahir sama persis
    dengan sebelum unit ini. Kembali: daftar notifikasi yang benar-benar dibuat (yang ter-dedupe tidak masuk)."""
    from services.notification_service import create_addressed, create_notification
    row = await recipients_for(reminder_id, entity_id)
    kw["entity_id"] = entity_id
    if row["mode"] == "izin":
        res, _, act = row["permission"].partition(".")
        if not (res and act):
            return []
        return await create_addressed(permission=(res, act), **kw)
    roles = row["roles"]
    if len(roles) == 1:
        note = await create_notification(recipient_role=roles[0], **kw)
        return [note] if note else []
    if not roles:
        return []
    return await create_addressed(roles=tuple(roles), **kw)


# ═══ Ringkasan untuk layar Penjadwal (GET /api/scheduler/jobs) ═══════════════
def _label_izin(perm: str) -> str:
    from access_modules import ACTION_LABEL, RESOURCE_LABEL
    res, _, act = perm.partition(".")
    aksi = ACTION_LABEL.get(perm) or ACTION_LABEL.get(act, act)
    return f"Pemegang izin {RESOURCE_LABEL.get(res, res)} — {aksi}"


def label_penerima(row: Dict[str, Any]) -> str:
    import role_registry as rr
    if row.get("mode") == "izin":
        return _label_izin(str(row.get("permission") or ""))
    roles = row.get("roles") or []
    return ", ".join(rr.role_label(r) for r in roles) if roles else "Tidak ada penerima"


async def ringkasan_penerima(reminder_ids: Iterable[str], entity_id: Optional[str]) -> str:
    """Satu kalimat penerima efektif untuk PT aktif (mis. "Manajer", "Manajer · Gudang")."""
    teks: List[str] = []
    for rid in reminder_ids:
        t = label_penerima(await recipients_for(rid, entity_id))
        if t not in teks:
            teks.append(t)
    return " · ".join(teks)
