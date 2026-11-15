"""TX-T1 (K-33, TX-06) — aturan pajak per PT yang bisa dijadwalkan, potret aturan di dokumen, dan data pajak pelanggan.

Masalah lama: tarif PPN dibaca dari dokumen pengaturan SAAT INI tanpa tanggal; faktor DPP nilai lain 11/12 ditulis mati di
empat tempat; pembulatan dua desimal ditulis mati; daftar kode transaksi faktur dan bawaannya (04/01) ditulis mati; pesanan
tidak menyimpan faktor maupun cara bulat, sehingga hitung ulang pesanan lama (override, amandemen) memakai aturan hari itu.

Satu pintu:
  * `tax_settings(entity_id, at)` — sepuluh kunci pajak dibaca lewat `config_resolver.resolve(..., at=at)` (lapisan PT +
    jadwal "berlaku sejak"); PT bukan PKP (profil PT) memaksa tarif 0. Hasil = potret + kode transaksi + `sources`.
  * `potret(settings)` — isi `tax_snapshot` dokumen; `potret_dokumen(doc)` — potret tersimpan, atau turunan field lama
    (`ppn_rate`, `ppn_mode`, `dpp_nilai_lain`) dengan aturan sebelum unit ini (11/12, per dokumen, dua desimal).
  * `round_money(value, satuan)` — SATU fungsi bulat pajak (D5).
  * `default_kode(snapshot, customer, settings)` — kode transaksi bawaan faktur.
  * `periksa_profil_pajak(...)` / `customer_tax(...)` / `data_incomplete(...)` — data pajak pelanggan.

Unit ini memindah nilai yang SUDAH ada di kode menjadi pengaturan bernilai sama (H4); tidak ada tarif, faktor, atau kode
baru. Bentuk NPWP/NIK (jumlah digit) hanya peringatan — menunggu konfirmasi konsultan pajak.
"""
import re
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Tuple

from db import db

#: Kunci pajak yang dibaca `tax_settings` (urutan = urutan kartu Pusat Pengaturan › Pajak).
KUNCI_PAJAK = (
    "tax.ppn_rate", "tax.dpp_nilai_lain", "tax.ppn_mode",
    "tax.dpp_nilai_lain_pembilang", "tax.dpp_nilai_lain_penyebut",
    "tax.pembulatan_tingkat", "tax.pembulatan_satuan",
    "tax.kode_transaksi_diizinkan", "tax.kode_transaksi_bawaan", "tax.kode_transaksi_bawaan_dpp_nilai_lain",
)
#: Kunci registry → nama field hasil `tax_settings` / `tax_snapshot`.
FIELD_KUNCI = {
    "tax.ppn_rate": "ppn_rate", "tax.dpp_nilai_lain": "dpp_nilai_lain", "tax.ppn_mode": "ppn_mode",
    "tax.dpp_nilai_lain_pembilang": "dpp_pembilang", "tax.dpp_nilai_lain_penyebut": "dpp_penyebut",
    "tax.pembulatan_tingkat": "pembulatan_tingkat", "tax.pembulatan_satuan": "pembulatan_satuan",
    "tax.kode_transaksi_diizinkan": "kode_transaksi_diizinkan", "tax.kode_transaksi_bawaan": "kode_transaksi_bawaan",
    "tax.kode_transaksi_bawaan_dpp_nilai_lain": "kode_transaksi_bawaan_dpp_nilai_lain",
}
#: Field `tax_snapshot` (spesifikasi TX-T1 bagian Data). `asal` menandai potret turunan dokumen lama.
FIELD_POTRET = ("ppn_rate", "dpp_nilai_lain", "dpp_pembilang", "dpp_penyebut", "ppn_mode",
                "pembulatan_tingkat", "pembulatan_satuan", "is_pkp", "berlaku_pada")
SATUAN_BULAT = ("dua_desimal", "rupiah_penuh")
TINGKAT_BULAT = ("dokumen", "baris")


def _iso(at: Optional[datetime]) -> str:
    t = at or datetime.now(timezone.utc)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.isoformat()


# ── pembulatan ──────────────────────────────────────────────────────────────────────────────────────────────────────
def round_money(value: float, satuan: str) -> float:
    """D5 — satu fungsi bulat pajak. `dua_desimal` = `round(v, 2)` (perilaku sebelum unit ini, persis);
    `rupiah_penuh` = ke rupiah terdekat, setengah ke atas (Rp 135.802,37 → Rp 135.802; Rp 11.000,55 → Rp 11.001)."""
    v = float(value or 0)
    if satuan == "dua_desimal":
        return round(v, 2)
    if satuan == "rupiah_penuh":
        return float(Decimal(repr(v)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    raise ValueError(f"Cara pembulatan PPN tidak dikenal: {satuan!r}")


# ── aturan per PT ───────────────────────────────────────────────────────────────────────────────────────────────────
async def _pt_pkp(entity_id: str) -> bool:
    """Sama dengan `config_service.get_effective_settings`: PT yang ditemukan dan `default_tax_mode != "ppn"` → bukan PKP;
    tanpa PT (grup / "Semua PT") atau PT tidak ditemukan → PKP."""
    if not entity_id or entity_id == "all":
        return True
    ent = await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "default_tax_mode": 1})
    return True if not ent else ent.get("default_tax_mode") == "ppn"


async def tax_settings(entity_id: str, at: Optional[datetime] = None) -> Dict[str, Any]:
    """Aturan pajak PT pada waktu `at` (bawaan: sekarang). Sepuluh kunci `KUNCI_PAJAK` dibaca lewat
    `config_resolver.resolve(key, {"entity_id"}, at=at)` — nilai berjadwal "berlaku sejak" ikut dihormati.
    PT bukan PKP → `ppn_rate` 0 dan `is_pkp` False (penimpa terdaftar `pt_bukan_pkp`).

    Hasil: field `tax_snapshot` (`FIELD_POTRET`) + tiga kunci kode transaksi + `sources` ({field: lapisan asal})."""
    from services.config_resolver import resolve_keys
    ent = entity_id if entity_id and entity_id != "all" else ""
    hasil = await resolve_keys(list(KUNCI_PAJAK), {"entity_id": ent}, at=at)
    out: Dict[str, Any] = {}
    sources: Dict[str, str] = {}
    for key in KUNCI_PAJAK:
        res = hasil[key]
        out[FIELD_KUNCI[key]] = res["value"]
        sources[FIELD_KUNCI[key]] = (res["overridden_by"] or {}).get("id") or res["source_layer"]
    is_pkp = await _pt_pkp(ent)
    out["ppn_rate"] = float(out["ppn_rate"] or 0) if is_pkp else 0.0
    out["dpp_nilai_lain"] = bool(out["dpp_nilai_lain"])
    out["dpp_pembilang"] = int(out["dpp_pembilang"])
    out["dpp_penyebut"] = int(out["dpp_penyebut"])
    out["kode_transaksi_diizinkan"] = [str(k) for k in out["kode_transaksi_diizinkan"] or []]
    out["is_pkp"] = is_pkp
    out["berlaku_pada"] = _iso(at)
    out["sources"] = sources
    return out


def potret(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Isi `tax_snapshot` dari hasil `tax_settings` (tanpa kode transaksi dan sumber)."""
    return {k: settings[k] for k in FIELD_POTRET}


def _nilai_lain_lama(doc: Dict[str, Any]) -> bool:
    """Bendera DPP nilai lain dokumen lama: field `dpp_nilai_lain` bila ada; dokumen pembelian lama tidak menyimpannya →
    ditebak dari angkanya, sama dengan `pdf_resolvers._uses_dpp_nilai_lain` (DPP ≈ 11/12 × harga sebelum PPN)."""
    if doc.get("dpp_nilai_lain") is not None:
        return bool(doc.get("dpp_nilai_lain"))
    dpp, ppn = float(doc.get("dpp") or 0), float(doc.get("ppn_amount") or 0)
    base = round(float(doc.get("grand_total") or 0) - ppn, 2)
    return dpp > 0 and ppn > 0 and base > 0 and abs(dpp - base * 11 / 12) <= 1 and abs(dpp - base) > 1


def potret_lama(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Aturan sebelum TX-T1 untuk dokumen tanpa potret: tarif/mode/bendera dari field dokumen, faktor 11/12, dibulatkan
    per dokumen ke dua desimal (spesifikasi TX-T1 bagian Data; tanpa migrasi). `asal` = "dokumen_lama"."""
    return {
        "ppn_rate": float(doc["ppn_rate"] or 0),
        "dpp_nilai_lain": _nilai_lain_lama(doc),
        "dpp_pembilang": 11, "dpp_penyebut": 12,
        "ppn_mode": doc["ppn_mode"],
        "pembulatan_tingkat": "dokumen", "pembulatan_satuan": "dua_desimal",
        "is_pkp": bool(doc["is_pkp"]) if "is_pkp" in doc else float(doc["ppn_rate"] or 0) > 0,
        "berlaku_pada": str(doc.get("created_at") or ""),
        "asal": "dokumen_lama",
    }


def potret_dokumen(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Potret aturan pajak dokumen (pesanan, PO, faktur): `tax_snapshot` tersimpan; dokumen lama ber-`ppn_rate` +
    `ppn_mode` → `potret_lama`; dokumen tanpa field pajak sama sekali → None (dihitung dari aturan PT saat ini)."""
    if not doc:
        return None
    snap = doc.get("tax_snapshot")
    if isinstance(snap, dict) and snap:
        return dict(snap)
    if "ppn_rate" in doc and "ppn_mode" in doc:
        return potret_lama(doc)
    return None


def faktor_teks(snapshot: Optional[Dict[str, Any]]) -> str:
    """"11/12" — pecahan DPP nilai lain potret (dokumen lama: aturan lama)."""
    s = snapshot if snapshot and "dpp_pembilang" in snapshot else potret_lama({"ppn_rate": 0, "ppn_mode": ""})
    return f"{int(s['dpp_pembilang'])}/{int(s['dpp_penyebut'])}"


# ── TX-T2 (K-32) — pemicu faktur ────────────────────────────────────────────────────────────────────────────────────
#: Nilai `tax.pemicu_faktur` yang terdaftar tetapi belum bisa dipakai → pesan penolakan saat disimpan (H4: jurnal PPN atas
#: uang muka belum ditetapkan; konfirmasi konsultan pajak).
PEMICU_BELUM_BISA = {
    "uang_muka": "Pemicu 'uang muka' belum bisa dipakai: menunggu ketetapan jurnal PPN atas uang muka.",
}


def periksa_pemicu_faktur(value: Any) -> Any:
    """Penjaga simpan `tax.pemicu_faktur` (dipanggil `config_resolver.set_value`): nilai terdaftar yang belum bisa
    dipakai → `ValueError` berpesan (400). Nilai lain dikembalikan apa adanya."""
    pesan = PEMICU_BELUM_BISA.get(str(value or ""))
    if pesan:
        raise ValueError(pesan)
    return value


# ── kode transaksi faktur ───────────────────────────────────────────────────────────────────────────────────────────
def pesan_kode_tidak_dipakai(kode: str) -> str:
    return f"Kode transaksi {kode} tidak dipakai PT ini."


def default_kode(snapshot: Dict[str, Any], customer: Optional[Dict[str, Any]], settings: Dict[str, Any]) -> str:
    """Urutan: kode bawaan pelanggan (`customers.tax_profile.kode_transaksi`) → bawaan PT menurut DPP nilai lain
    dokumen (`tax.kode_transaksi_bawaan_dpp_nilai_lain` bila potret ber-DPP nilai lain, selain itu
    `tax.kode_transaksi_bawaan`)."""
    milik = str(((customer or {}).get("tax_profile") or {}).get("kode_transaksi") or "").strip()
    if milik:
        return milik
    if bool((snapshot or {}).get("dpp_nilai_lain")):
        return str(settings["kode_transaksi_bawaan_dpp_nilai_lain"])
    return str(settings["kode_transaksi_bawaan"])


def periksa_kode(kode: str, settings: Dict[str, Any]) -> str:
    """Kode sah = ada di `tax.kode_transaksi_diizinkan` PT; selain itu `ValueError` berpesan siap tampil."""
    k = (kode or "").strip()
    if k not in settings["kode_transaksi_diizinkan"]:
        raise ValueError(pesan_kode_tidak_dipakai(k))
    return k


# ── data pajak pelanggan ────────────────────────────────────────────────────────────────────────────────────────────
ID_TYPES = ("npwp", "nik", "")
_HANYA_ANGKA_TANDA = re.compile(r"^[0-9.\-/\s]*$")
#: Jumlah digit yang lazim — hanya PERINGATAN, tidak menolak simpan (konfirmasi konsultan pajak).
_DIGIT_NPWP = (15, 16)
_DIGIT_NIK = (16,)


def _digit(teks: str) -> str:
    return "".join(ch for ch in teks if ch.isdigit())


def _periksa_nomor(label: str, nilai: Any, lazim: Tuple[int, ...]) -> Tuple[str, List[str]]:
    teks = str(nilai if nilai is not None else "").strip()
    if not _HANYA_ANGKA_TANDA.match(teks):
        raise ValueError(f"{label} hanya boleh berisi angka.")
    peringatan: List[str] = []
    n = len(_digit(teks))
    if teks and n not in lazim:
        harap = " atau ".join(str(x) for x in lazim)
        peringatan.append(f"{label} berisi {n} angka; biasanya {harap} angka. Periksa lagi sebelum menerbitkan faktur.")
    return teks, peringatan


def periksa_npwp(nilai: Any) -> Tuple[str, List[str]]:
    """NPWP pelanggan: hanya angka dan tanda baca (400 bila tidak); jumlah digit di luar 15/16 = peringatan."""
    return _periksa_nomor("NPWP", nilai, _DIGIT_NPWP)


def periksa_profil_pajak(profil: Any, *, kode_diizinkan: List[str]) -> Tuple[Dict[str, Any], List[str]]:
    """Bersihkan `customers.tax_profile` → (profil, peringatan). `ValueError` berpesan bila tidak sah.

    Field tak dikenal dibuang. `kode_transaksi` kosong = ikut PT; terisi = harus ada di daftar kode PT pelanggan."""
    if profil is None:
        profil = {}
    if not isinstance(profil, dict):
        raise ValueError("Data pajak pelanggan tidak sah.")
    id_type = str(profil.get("id_type") or "").strip().lower()
    if id_type not in ID_TYPES:
        raise ValueError("Identitas pajak harus NPWP atau NIK.")
    peringatan: List[str] = []
    nik, warn = _periksa_nomor("NIK", profil.get("nik"), _DIGIT_NIK)
    peringatan += warn
    if id_type == "nik" and not nik:
        raise ValueError("NIK wajib diisi bila identitas pajak memakai NIK.")
    is_pkp = profil.get("is_pkp")
    if is_pkp not in (True, False, None):
        raise ValueError("Status PKP pelanggan harus PKP, Bukan PKP, atau belum diisi.")
    kode = str(profil.get("kode_transaksi") or "").strip()
    if kode and kode not in kode_diizinkan:
        raise ValueError(pesan_kode_tidak_dipakai(kode))
    bersih = {
        "id_type": id_type,
        "nik": nik,
        "tax_name": str(profil.get("tax_name") or "").strip()[:200],
        "tax_address": str(profil.get("tax_address") or "").strip()[:500],
        "is_pkp": is_pkp,
        "kode_transaksi": kode,
        "always_tax_invoice": bool(profil.get("always_tax_invoice")),
    }
    return bersih, peringatan


def _alamat_utama(customer: Dict[str, Any]) -> str:
    addrs = customer.get("addresses") or []
    a = next((x for x in addrs if x.get("is_primary")), addrs[0] if addrs else {})
    return f"{a.get('address', '')}, {a.get('city', '')}".strip(", ")


def customer_tax(customer: Optional[Dict[str, Any]], nama_dokumen: str = "") -> Dict[str, Any]:
    """Potret data pajak pembeli untuk faktur: identitas (`id_type` + `id_number`), nama & alamat menurut dokumen pajak
    (kosong = nama pelanggan dan alamat utama), status PKP. `customers.npwp` tetap pemilik nomor NPWP."""
    c = customer or {}
    prof = c.get("tax_profile") or {}
    npwp = str(c.get("npwp") or "").strip()
    id_type = str(prof.get("id_type") or "").strip() or ("npwp" if npwp else "")
    nomor = str(prof.get("nik") or "").strip() if id_type == "nik" else (npwp if id_type == "npwp" else "")
    return {
        "id_type": id_type,
        "id_number": nomor,
        "tax_name": str(prof.get("tax_name") or "").strip() or nama_dokumen or str(c.get("name") or ""),
        "tax_address": str(prof.get("tax_address") or "").strip() or _alamat_utama(c),
        "is_pkp": prof.get("is_pkp"),
    }


def data_incomplete(ctax: Dict[str, Any]) -> List[str]:
    """Kekurangan data pajak pembeli (penerbitan TIDAK ditolak di TX-T1): `identitas_pajak`, `alamat_pajak`."""
    out: List[str] = []
    if not ctax.get("id_number"):
        out.append("identitas_pajak")
    if not ctax.get("tax_address"):
        out.append("alamat_pajak")
    return out


# ── produk (disimpan, BELUM dipakai mesin — L5) ─────────────────────────────────────────────────────────────────────
PERLAKUAN_PPN = ("kena", "dibebaskan", "tidak_dipungut")


def periksa_pajak_produk(data: Dict[str, Any]) -> None:
    """`products.tax_treatment` (bawaan `kena`) dan `tax_item_code` — disimpan dan ditampilkan bertanda "belum dipakai
    mesin" (PPN per barang di luar lingkup TX-T1). Mengubah `data` di tempat; `ValueError` bila tidak sah."""
    if "tax_treatment" in data:
        v = str(data["tax_treatment"] or "").strip().lower() or "kena"
        if v not in PERLAKUAN_PPN:
            raise ValueError("Perlakuan PPN harus kena, dibebaskan, atau tidak dipungut.")
        data["tax_treatment"] = v
    if "tax_item_code" in data:
        data["tax_item_code"] = str(data["tax_item_code"] or "").strip()[:40]


# ── layar ───────────────────────────────────────────────────────────────────────────────────────────────────────────
async def bagian_pajak_layar(entity_id: str) -> Dict[str, Any]:
    """Nilai pajak yang DIPAKAI mesin hari ini (L6) dengan nama daun dokumen pengaturan (`tax.*`), untuk pratinjau harga
    (POS, PO) dan pilihan kode transaksi (form pelanggan, Faktur Keluaran). Kunci yang belum pernah diatur ikut tampil
    dengan bawaan registry."""
    s = await tax_settings(entity_id)
    out = {k.split(".", 1)[1]: s[FIELD_KUNCI[k]] for k in KUNCI_PAJAK}   # daun dokumen = kunci tanpa "tax."
    out["is_pkp"] = s["is_pkp"]
    # TX-T2 — pemicu faktur PT (detail pesanan: tombol terbit manual vs tautan draf per surat jalan).
    from services.config_resolver import value_of
    out["pemicu_faktur"] = await value_of("tax.pemicu_faktur", {"entity_id": entity_id or ""})
    return out
