"""KP-T8 (KP-16) — satu koneksi WhatsApp untuk dua pemakai: Pengingat (`alerts`) dan Kirim Dokumen (`documents`).

Sebelum KP-T8 tiap pemakai menyimpan penyedia, nomor, dan token sendiri-sendiri: `system_settings{scope: "alerts"}.wa`
(pengingat) dan `integration_settings{id: "whatsapp"}` (kirim dokumen). Kini koneksi (penyedia + kredensial) disimpan
SATU kali di `system_settings{scope: "integrations"}.whatsapp`; dua field token selalu terbungkus (`secret_box`).
Pengaturan pemakaian tetap di tempatnya (pengingat: `enabled`, `pic_number`, `send_to_roles`, `min_severity`,
`delivery_mode`, `critical_bypass`; kirim dokumen: `enabled`, `simulate`).

Pembaca menerima bentuk lama maupun baru: selama koneksi tunggal belum ada, `for_consumer(nama)` mengembalikan
konfigurasi lama pemakai itu (perilaku sebelum KP-T8). Koneksi tunggal lahir lewat `PUT/adopt` di layar Integrasi atau
skrip `scripts/migrate_kpt8_rahasia.py` (dijalankan pemilik — H3); dua konfigurasi lama yang BERBEDA tidak pernah
digabung otomatis.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from db import db
from core_utils import new_id, now_iso
from services import secret_box

SCOPE = "integrations"
FIELD = "whatsapp"
PROVIDERS = ("simulated", "meta_cloud", "fonnte")
TOKEN_FIELDS = ("access_token", "fonnte_token")
KONEKSI_FIELDS = ("provider", "access_token", "fonnte_token", "phone_number_id", "sender", "sender_label",
                  "default_country_code", "template_name", "template_lang")
#: Field yang ditolak `PUT /api/scheduler/settings` & `PUT /api/deliveries/whatsapp/settings` setelah koneksi tunggal ada.
FIELD_KONEKSI_LAMA = KONEKSI_FIELDS + ("clear_tokens",)
DEFAULT_KONEKSI: Dict[str, Any] = {
    "provider": "simulated", "access_token": "", "fonnte_token": "", "phone_number_id": "", "sender": "",
    "sender_label": "Kain Nusantara", "default_country_code": "62", "template_name": "", "template_lang": "id",
}
PEMAKAI = ("alerts", "documents")
LABEL_PEMAKAI = {"alerts": "Pengingat", "documents": "Kirim Dokumen"}
LABEL_PENYEDIA = {"simulated": "Simulasi", "meta_cloud": "Meta WhatsApp Cloud", "fonnte": "Fonnte"}
PESAN_DIATUR_DI_INTEGRASI = "Koneksi WhatsApp diatur di Pengaturan › Sistem › Integrasi & Audit."
PESAN_SUDAH_SATU = "Koneksi WhatsApp sudah satu."


class KoneksiError(ValueError):
    """Isian koneksi tidak sah (pesan untuk manusia); `status` = kode HTTP yang dipakai router."""

    def __init__(self, pesan: str, status: int = 400):
        super().__init__(pesan)
        self.status = status


# ═══ pembungkus token ═══════════════════════════════════════════════════════════
def buka(row: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """Salinan `row` dengan token terbuka. Token yang tidak bisa dibuka DIBIARKAN terbungkus (simpan berikutnya tidak
    menghapusnya) dan galatnya dikembalikan."""
    out, galat = dict(row), ""
    for k in TOKEN_FIELDS:
        if out.get(k):
            try:
                out[k] = secret_box.open(out[k])
            except secret_box.SecretBoxError as exc:
                galat = str(exc)
    return out, galat


def bungkus(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    for k in TOKEN_FIELDS:
        if k in out:
            out[k] = secret_box.seal(str(out.get(k) or ""))
    return out


async def bungkus_malas(collection: str, query: Dict[str, Any], prefix: str, row: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """Token polos lama dibungkus di basis data saat pertama dibaca (bila kunci terpasang — pola kunci penyedia),
    lalu kembalikan salinan terbuka."""
    polos = {f"{prefix}{k}": secret_box.seal(str(row[k])) for k in TOKEN_FIELDS
             if row.get(k) and not secret_box.is_sealed(row[k])}
    if polos and secret_box.available():
        await db[collection].update_one(query, {"$set": polos})
    return buka(row)


# ═══ bentuk & ringkasan ═════════════════════════════════════════════════════════
def bentuk(row: Dict[str, Any]) -> Dict[str, Any]:
    """Field koneksi saja (nilai kosong → bawaan)."""
    return {k: (row.get(k) if row.get(k) not in (None, "") else DEFAULT_KONEKSI[k]) for k in KONEKSI_FIELDS}


def configured(c: Dict[str, Any]) -> bool:
    return bool((c.get("provider") == "meta_cloud" and c.get("access_token") and c.get("phone_number_id"))
                or (c.get("provider") == "fonnte" and c.get("fonnte_token")))


def terisi(c: Dict[str, Any]) -> bool:
    """Konfigurasi lama dianggap terisi bila penyedianya bukan simulasi atau ada token tersimpan."""
    return (c.get("provider") or "simulated") != "simulated" or any(c.get(k) for k in TOKEN_FIELDS)


def _token_utama(c: Dict[str, Any]) -> str:
    return str(c.get("fonnte_token") if c.get("provider") == "fonnte" else
               c.get("access_token") if c.get("provider") == "meta_cloud" else "")


def identitas(c: Dict[str, Any]) -> Tuple[str, str, str]:
    """(penyedia, nomor pengirim, token penyedia itu) — dasar "sama" saat menggabung (spesifikasi KP-T8 Data #3)."""
    return (c.get("provider") or "simulated", str(c.get("phone_number_id") or ""), _token_utama(c))


def ringkas(c: Dict[str, Any]) -> Dict[str, Any]:
    """Ringkasan tanpa token (untuk layar)."""
    return {**{k: c.get(k, DEFAULT_KONEKSI[k]) for k in KONEKSI_FIELDS if k not in TOKEN_FIELDS},
            "provider_label": LABEL_PENYEDIA.get(c.get("provider") or "simulated", c.get("provider")),
            "has_access_token": bool(c.get("access_token")), "has_fonnte_token": bool(c.get("fonnte_token")),
            "configured": configured(c)}


# ═══ baca ═══════════════════════════════════════════════════════════════════════
async def _tersimpan() -> Optional[Dict[str, Any]]:
    rec = await db.system_settings.find_one({"scope": SCOPE}, {"_id": 0, FIELD: 1}) or {}
    return rec.get(FIELD) or None


async def ada_koneksi_tunggal() -> bool:
    return bool(await _tersimpan())


async def lama(nama: str) -> Dict[str, Any]:
    """Konfigurasi koneksi lama milik satu pemakai (token terbuka; `secret_error` bila tidak bisa dibuka)."""
    if nama == "alerts":
        from services import wa_alert_service as was
        st = await was.raw_settings()
        return {**bentuk(st["wa"]), "secret_error": st.get("secret_error", "")}
    if nama == "documents":
        from services import delivery_service as ds
        row, galat = await ds.raw_row()
        return {**bentuk(row), "secret_error": galat}
    raise KoneksiError("Pemakai WhatsApp tidak dikenal.")


async def for_consumer(name: str) -> Dict[str, Any]:
    """Koneksi tunggal (token sudah dibuka) bila ada; bila belum, konfigurasi lama pemakai itu (perilaku hari ini).
    `managed` = koneksi tunggal dipakai; `secret_error` = token terbungkus yang tidak bisa dibuka."""
    if name not in PEMAKAI:
        raise KoneksiError("Pemakai WhatsApp tidak dikenal.")
    t = await _tersimpan()
    if t:
        c, galat = buka(bentuk(t))
        return {**c, "managed": True, "secret_error": galat}
    return {**await lama(name), "managed": False}


def gabung(a: Dict[str, Any], d: Dict[str, Any]) -> Dict[str, Any]:
    """Dua konfigurasi yang sama → satu: isian pengingat dipakai, yang kosong dilengkapi dari kirim dokumen."""
    out = {}
    for k in KONEKSI_FIELDS:
        va, vd = a.get(k), d.get(k)
        out[k] = va if va not in (None, "") and va != DEFAULT_KONEKSI[k] else (vd if vd not in (None, "") else va)
    return out


def rencana_dari(a: Dict[str, Any], d: Dict[str, Any], ada_tunggal: bool) -> Dict[str, Any]:
    """Fungsi murni: keadaan dua konfigurasi lama `a` (pengingat) dan `d` (kirim dokumen), token terbuka.

    `sudah_satu` · `kosong` · `satu` (salah satu terisi) · `sama` (penyedia, nomor, token sama) · `berbeda`.
    `hasil` = koneksi yang akan dipakai untuk `satu`/`sama`; None untuk lainnya (yang berbeda diputuskan pemilik)."""
    ta, td = terisi(a), terisi(d)
    hasil, sumber = None, ""
    if ada_tunggal:
        keadaan = "sudah_satu"
    elif not ta and not td:
        keadaan = "kosong"
    elif ta != td:
        keadaan, sumber = "satu", ("alerts" if ta else "documents")
        hasil = bentuk(a if ta else d)
    elif identitas(a) == identitas(d) and not (a.get("secret_error") or d.get("secret_error")):
        keadaan, sumber, hasil = "sama", "gabungan", gabung(bentuk(a), bentuk(d))
    else:
        keadaan = "berbeda"
    return {"keadaan": keadaan, "sumber": sumber, "hasil": hasil,
            "alerts": {**ringkas(a), "terisi": ta}, "documents": {**ringkas(d), "terisi": td}}


async def rencana_gabung() -> Dict[str, Any]:
    """`rencana_dari` atas konfigurasi lama yang tersimpan sekarang."""
    return rencana_dari(await lama("alerts"), await lama("documents"), bool(await _tersimpan()))


async def public_view() -> Dict[str, Any]:
    """Jawaban `GET /api/admin/integrations/whatsapp` — token tidak pernah dikirim."""
    t = await _tersimpan()
    if t:
        c = bentuk(t)
        out = {**ringkas(c), "used_by": {"alerts": True, "documents": True}, "conflict": None,
               "source": t.get("source", ""), "updated_at": t.get("updated_at", ""), "updated_by": t.get("updated_by", "")}
        _, galat = buka(c)
    else:
        r = await rencana_gabung()
        dasar = r["hasil"] or dict(DEFAULT_KONEKSI)
        out = {**ringkas(dasar), "configured": False, "used_by": {"alerts": False, "documents": False},
               "conflict": ({"alerts": r["alerts"], "documents": r["documents"]} if r["keadaan"] == "berbeda" else None),
               "source": "", "updated_at": "", "updated_by": "",
               # Belum satu koneksi: isian diisi dari konfigurasi lama yang akan dipakai (tanpa token).
               "candidate_from": r["sumber"] if r["hasil"] else ""}
        galat = ""
    out.update(secrets_key_configured=secret_box.available(), secret_error=galat, providers=list(PROVIDERS))
    return out


# ═══ tulis ══════════════════════════════════════════════════════════════════════
def validasi(c: Dict[str, Any]) -> None:
    prov = c.get("provider") or "simulated"
    if prov not in PROVIDERS:
        raise KoneksiError(f"Penyedia harus salah satu dari: {', '.join(LABEL_PENYEDIA[p] for p in PROVIDERS)}.")
    if prov == "meta_cloud" and not (c.get("access_token") and c.get("phone_number_id")):
        raise KoneksiError("Meta Cloud butuh access_token + phone_number_id. "
                           "Isi kredensial atau pilih provider Simulasi.")
    if prov == "fonnte" and not c.get("fonnte_token"):
        raise KoneksiError("Fonnte butuh fonnte_token. Isi token atau pilih provider Simulasi.")


async def simpan_koneksi(c: Dict[str, Any], actor: str, source: str) -> None:
    """Tulis koneksi tunggal (token dibungkus). `source`: `manual` · `alerts` · `documents` · `gabungan`."""
    await _simpan(c, actor, source)


async def _simpan(c: Dict[str, Any], actor: str, source: str) -> None:
    obj = {**bungkus(bentuk(c)), "source": source, "updated_at": now_iso(), "updated_by": actor}
    await db.system_settings.update_one(
        {"scope": SCOPE},
        {"$set": {FIELD: obj},
         "$setOnInsert": {"id": new_id("set"), "scope": SCOPE, "created_at": now_iso()}},
        upsert=True)


async def simpan(patch: Dict[str, Any], actor: str) -> Dict[str, Any]:
    """`PUT …/whatsapp`: token kosong/tidak dikirim = tidak diubah; `clear_tokens` menghapus keduanya. Dasar = koneksi
    tunggal, atau (belum ada) konfigurasi lama yang akan dipakai, atau bawaan."""
    t = await _tersimpan()
    if t:
        base, _ = buka(bentuk(t))
    else:
        base = dict((await rencana_gabung())["hasil"] or DEFAULT_KONEKSI)
    patch = dict(patch or {})
    if patch.pop("clear_tokens", False):
        for k in TOKEN_FIELDS:
            base[k] = ""
    for k, v in patch.items():
        if k not in KONEKSI_FIELDS or v is None:
            continue
        v = str(v).strip()
        if k in TOKEN_FIELDS and not v:
            continue
        base[k] = v
    validasi(base)
    await _simpan(base, actor, "manual")
    return await public_view()


async def adopt(dari: str, reason: str, actor: str) -> Dict[str, Any]:
    """Jadikan konfigurasi lama satu pemakai koneksi tunggal untuk keduanya (keputusan atas dua koneksi berbeda)."""
    if await _tersimpan():
        raise KoneksiError(PESAN_SUDAH_SATU, status=409)
    if dari not in PEMAKAI:
        raise KoneksiError("Pilih koneksi Pengingat atau Kirim Dokumen.")
    if not (reason or "").strip():
        raise KoneksiError("Alasan wajib diisi.")
    c = await lama(dari)
    if not terisi(c):
        raise KoneksiError(f"Konfigurasi WhatsApp {LABEL_PEMAKAI[dari]} masih kosong — tidak ada yang bisa dipakai.")
    if c.get("secret_error"):
        raise KoneksiError(c["secret_error"])
    await _simpan(c, actor, dari)
    return await public_view()


def field_lama_ditolak(patch: Dict[str, Any]) -> list:
    """Field koneksi yang dikirim ke endpoint pemakai (None/False = tidak dikirim)."""
    return [k for k in FIELD_KONEKSI_LAMA if k in (patch or {}) and patch[k] not in (None, False)]
