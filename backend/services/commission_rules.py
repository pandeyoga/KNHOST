"""KA-1 — aturan pengali komisi per artikel: validasi nilai tabel + pembaca kunci Pusat Pengaturan.

Kunci `commission.price_*` (pengali menurut harga jual) dan `commission.achievement_*` (pengali capaian target) hidup di
Pusat Pengaturan (`config_catalog_core`). Modul ini memeriksa isi tabelnya saat disimpan (`config_resolver.set_value`)
dan membacanya untuk mesin komisi. Rancangan: `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md`.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

PRICE_KEYS = ("commission.price_basis", "commission.price_bands", "commission.price_source_rules")
ACH_KEYS = ("commission.achievement_multiplier", "commission.achievement_basis", "commission.achievement_tiers")
SUMBER_KHUSUS = ("special_approval", "customer", "special_order")
CARA_SUMBER = ("ikut_pita", "pengali_tetap")

_KUNCI_HARGA_LAIN = ("discount_threshold_type", "discount_threshold", "discount_mechanic", "discount_factor",
                     "discount_potong_rp", "default_margin_cap_pct")
_BAWAAN_SUMBER = {"cara": "ikut_pita", "pengali": 1.0}
ACUAN_FIELD = {"daftar_pt": "list_price", "umum": "global_price", "batas_bawah": "floor_price"}
NAMA_SUMBER = {"special_approval": "Harga khusus", "customer": "Harga pelanggan", "special_order": "Pesanan khusus"}
ALASAN_LABEL: Dict[str, str] = {
    "harga_penuh": "Harga jual tidak di bawah harga acuan",
    "pita": "{selisih}% di bawah harga acuan",
    "tanpa_pembanding": "Harga acuan belum ada, komisi tidak dikurangi",
    "diskon_baris": "Diskon baris di bawah ambang",
    "diskon_lewat_ambang": "Diskon baris melewati ambang",
    **{f"sumber_tetap:{k}": f"{v}, memakai pengali tetap" for k, v in NAMA_SUMBER.items()},
}
#: BTP-5 (A1-6) — kode alasan baris rincian koreksi & saldo potongan (bukan alasan harga; `price_reason` baris rincian).
KOREKSI_BATAL, KOREKSI_TUTUP_SISA = "koreksi_batal", "koreksi_tutup_sisa"
POTONGAN_TERBAWA, POTONGAN_DIBAWA = "potongan_terbawa", "potongan_dibawa"
LABEL_KOREKSI = {KOREKSI_BATAL: "Koreksi komisi: pesanan {nomor} {kata}",
                 KOREKSI_TUTUP_SISA: "Koreksi komisi: sisa pesanan {nomor} ditutup"}
LABEL_TERBAWA = "Potongan komisi terbawa dari {bulan}"
LABEL_DIBAWA = "Sisa potongan komisi dibawa ke bulan berikutnya"


def _angka(v: Any, nama: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise ValueError(f"{nama} harus berupa angka.")
    try:
        n = float(v)
    except ValueError:
        raise ValueError(f"{nama} harus berupa angka.") from None
    if not math.isfinite(n):
        raise ValueError(f"{nama} harus berupa angka.")
    return n


def _baris(value: Any, nama: str) -> List[Dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{nama} minimal berisi satu baris.")
    if not all(isinstance(r, dict) for r in value):
        raise ValueError(f"Isi {nama} tidak sah.")
    return value


def _pengali(r: Dict[str, Any], nama: str) -> float:
    p = _angka(r.get("pengali"), f"Pengali pada {nama}")
    if p < 0:
        raise ValueError(f"Pengali pada {nama} tidak boleh negatif.")
    return p


def _periksa_pita(value: Any) -> Any:
    nama = "Pita pengali harga"
    rows = _baris(value, nama)
    batas, kosong = [], []
    for r in rows:
        p = _pengali(r, nama)
        s = r.get("sampai_pct")
        if s is None or (isinstance(s, str) and not s.strip()):
            kosong.append({"sampai_pct": None, "pengali": p})
            continue
        s = _angka(s, f"Batas selisih pada {nama}")
        if s <= 0:
            raise ValueError(f"Batas selisih pada {nama} harus lebih dari 0.")
        batas.append({"sampai_pct": s, "pengali": p})
    if len(kosong) != 1:
        raise ValueError(f"{nama} harus punya tepat satu baris terakhir tanpa batas (kolom batas dikosongkan).")
    nilai = [b["sampai_pct"] for b in batas]
    if len(set(nilai)) != len(nilai):
        raise ValueError(f"Batas selisih pada {nama} tidak boleh kembar.")
    return sorted(batas, key=lambda b: b["sampai_pct"]) + kosong


def _periksa_sumber(value: Any) -> Any:
    nama = "Aturan asal harga"
    rows = _baris(value, nama)
    out, lihat = [], set()
    for r in rows:
        sumber, cara = r.get("sumber"), r.get("cara")
        if sumber not in SUMBER_KHUSUS:
            raise ValueError(f"Asal harga pada {nama} tidak dikenal. Pilihan: "
                             + ", ".join(NAMA_SUMBER[k] for k in SUMBER_KHUSUS) + ".")
        if sumber in lihat:
            raise ValueError(f"Asal harga pada {nama} tidak boleh kembar.")
        lihat.add(sumber)
        if cara not in CARA_SUMBER:
            raise ValueError(f"Cara pada {nama} harus 'Ikut cara harga' atau 'Pengali tetap'.")
        out.append({"sumber": sumber, "cara": cara, "pengali": _pengali(r, nama)})
    return out


def _periksa_jenjang(value: Any) -> Any:
    nama = "Jenjang pengali capaian"
    rows = _baris(value, nama)
    out = []
    for r in rows:
        m = _angka(r.get("capaian_min_pct"), f"Capaian mulai pada {nama}")
        if m < 0:
            raise ValueError(f"Capaian mulai pada {nama} tidak boleh negatif.")
        out.append({"capaian_min_pct": m, "pengali": _pengali(r, nama)})
    nilai = [o["capaian_min_pct"] for o in out]
    if len(set(nilai)) != len(nilai):
        raise ValueError(f"Capaian mulai pada {nama} tidak boleh kembar.")
    if 0 not in nilai:
        raise ValueError(f"{nama} wajib punya satu baris yang mulai dari 0%.")
    return sorted(out, key=lambda o: o["capaian_min_pct"])


_PEMERIKSA = {
    "commission.price_bands": _periksa_pita,
    "commission.price_source_rules": _periksa_sumber,
    "commission.achievement_tiers": _periksa_jenjang,
}


def rate_key(doc: Dict[str, Any]) -> str:
    """Kunci keunikan tarif insentif per PT: `varian:<id>` · `artikel:<id>` · `kategori:<kategori>`."""
    if (doc.get("product_id") or "").strip():
        return f"varian:{doc['product_id'].strip()}"
    if (doc.get("template_id") or "").strip():
        return f"artikel:{doc['template_id'].strip()}"
    return f"kategori:{(doc.get('category') or '').strip()}"


def periksa_nilai(key: str, value: Any) -> Any:
    """Nilai bersih kunci tabel pengali komisi (kunci lain dikembalikan apa adanya). `ValueError` berpesan siap tampil."""
    fn = _PEMERIKSA.get(key)
    return fn(value) if fn else value


KUNCI_ATURAN = list(PRICE_KEYS) + ["insentif.harga_acuan"] + [f"commission.{k}" for k in _KUNCI_HARGA_LAIN]


def susun_aturan_pt(nilai: Dict[str, Any]) -> Dict[str, Any]:
    """Aturan harga satu PT dari `{kunci: nilai}` (nilai tabel sudah bersih). Aturan asal harga dilengkapi ke tiga sumber."""
    ada = {r["sumber"]: r for r in nilai["commission.price_source_rules"]}
    aturan_sumber = [dict(ada.get(s) or {"sumber": s, **_BAWAAN_SUMBER}) for s in SUMBER_KHUSUS]
    out = {
        "price_basis": nilai["commission.price_basis"],
        "price_bands": nilai["commission.price_bands"],
        "price_source_rules": aturan_sumber,
        "acuan": nilai["insentif.harga_acuan"],
    }
    for k in _KUNCI_HARGA_LAIN:
        out[k] = nilai[f"commission.{k}"]
    return out


async def aturan_pt(entity_id: Optional[str], hipotetis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Aturan harga komisi satu PT. `hipotetis` = `{kunci: nilai}` yang menimpa nilai tersimpan (untuk simulasi)."""
    from services import config_resolver
    res = await config_resolver.resolve_keys(KUNCI_ATURAN, {"entity_id": entity_id or ""})
    nilai = {k: res[k]["value"] for k in KUNCI_ATURAN}
    for k, v in (hipotetis or {}).items():
        if k in nilai:
            nilai[k] = _PEMERIKSA[k](v) if k in _PEMERIKSA else v
    return susun_aturan_pt(nilai)


async def aturan_capaian(entity_id: str, at: Optional[datetime] = None) -> Dict[str, Any]:
    """Aturan pengali capaian target PT pada waktu `at` (bawaan: sekarang)."""
    from services import config_resolver
    res = await config_resolver.resolve_keys(list(ACH_KEYS), {"entity_id": entity_id}, at=at)
    return {"aktif": bool(res["commission.achievement_multiplier"]["value"]),
            "basis": res["commission.achievement_basis"]["value"],
            "jenjang": res["commission.achievement_tiers"]["value"]}


# ═══════════════════════════════════════════════════════════════════════════
# Fungsi murni — pemilihan tarif, potret aturan, pengali harga, hitung baris (KA-3)
# ═══════════════════════════════════════════════════════════════════════════
def pilih_tarif(indeks: Dict[str, Dict[str, Any]], *, product_id: str, template_id: str,
                category: str) -> Optional[Dict[str, Any]]:
    """Tarif yang berlaku bagi satu varian: varian → artikel → kategori. Salinan dokumen + asal tingkat & lingkup."""
    for tingkat, kunci in (("varian", f"varian:{(product_id or '').strip()}"),
                           ("artikel", f"artikel:{(template_id or '').strip()}"),
                           ("kategori", f"kategori:{(category or '').strip()}")):
        if kunci.endswith(":"):
            continue
        doc = indeks.get(kunci)
        if doc:
            return {**doc, "asal_tingkat": tingkat, "asal_lingkup": doc.get("_lingkup", "semua_pt")}
    return None


def _isi(nilai: Any, cadangan: Any) -> Any:
    return cadangan if nilai is None else nilai


def _dari_tarif(tarif: Dict[str, Any], kunci: str, nilai_pt: Any) -> Any:
    """Isian baris tarif menimpa nilai PT bila KUNCINYA ada — juga bila nilainya None — sama dengan mesin lama
    (`{**cfg, **rate}`; pembacanya memperlakukan None sebagai 0: batas margin None = tanpa batas). Kunci tidak ada di
    baris tarif → nilai PT."""
    return tarif[kunci] if kunci in tarif else nilai_pt


def potret(tarif: Optional[Dict[str, Any]], pt: Dict[str, Any], *, artikel: Optional[Dict[str, Any]],
           sumber: str, waktu: str) -> Dict[str, Any]:
    """Potret aturan komisi satu baris pesanan (`items[].commission_rule`, v1). Batas margin & isian diskon: kunci yang
    ADA di baris tarif dipakai apa adanya (None tetap None), kunci yang TIDAK ADA → nilai PT (mesin lama). Pita/aturan
    asal harga milik tarif (bukan None) menggantikan milik PT; None = ikut PT."""
    t = None
    if tarif:
        t = {"id": tarif.get("id"), "asal_tingkat": tarif.get("asal_tingkat"), "asal_lingkup": tarif.get("asal_lingkup"),
             "per_unit_amount": float(tarif.get("per_unit_amount", 0) or 0),
             "margin_cap_pct": _dari_tarif(tarif, "margin_cap_pct", pt.get("default_margin_cap_pct"))}
        for k in ("discount_threshold_type", "discount_threshold", "discount_mechanic", "discount_factor",
                  "discount_potong_rp"):
            t[k] = _dari_tarif(tarif, k, pt.get(k))
    return {
        "v": 1, "sumber": sumber, "dipotret_pada": waktu,
        "artikel": dict(artikel) if artikel else None,
        "tarif": t,
        "price_basis": pt.get("price_basis"), "acuan": pt.get("acuan"),
        "price_bands": _isi((tarif or {}).get("price_bands"), pt.get("price_bands")),
        "price_source_rules": _isi((tarif or {}).get("price_source_rules"), pt.get("price_source_rules")),
    }


def sumber_harga(line: Dict[str, Any]) -> str:
    """Asal harga baris: pesanan khusus bila ada harga pesanan khusus, selain itu `price_source` (kosong → global)."""
    if line.get("price_source") == "special_order" or line.get("special_order_price"):
        return "special_order"
    return line.get("price_source") or "global"


def pilih_pita(pita: List[Dict[str, Any]], selisih_pct: float) -> float:
    """Pengali pita pertama yang `selisih ≤ sampai_pct` (batas termasuk); baris tanpa batas menangkap sisanya."""
    for r in pita:
        batas = r.get("sampai_pct")
        if batas is None or selisih_pct <= float(batas):
            return float(r.get("pengali", 0) or 0)
    return 0.0


def pilih_jenjang(jenjang: List[Dict[str, Any]], capaian_pct: float) -> float:
    """Pengali jenjang dengan `capaian_min_pct` terbesar yang tidak melebihi capaian (tak ada → 1)."""
    lolos = [r for r in jenjang if float(r.get("capaian_min_pct", 0) or 0) <= capaian_pct]
    if not lolos:
        return 1.0
    return float(max(lolos, key=lambda r: float(r.get("capaian_min_pct", 0) or 0)).get("pengali", 0) or 0)


def faktor_diskon(cfg: Dict[str, Any], line: Dict[str, Any], per_unit: float) -> Tuple[float, float]:
    """Kembalikan (tarif_efektif, faktor) berdasar mekanik diskon baris (cara lama).

    3 mekanik (dapat diatur): tier_factor | potong_rp | cutoff. Ambang: pct | rp_per_unit.
    """
    qty = float(line.get("quantity", 0) or 0)
    price = float(line.get("price", 0) or 0)
    line_total = float(line.get("line_total", 0) or 0)
    disc_pct = float(line.get("discount_percent", 0) or 0)
    net_unit = (line_total / qty) if qty else price
    disc_rp_per_unit = max(price - net_unit, 0.0)

    from config_registry import default_of   # KF-T2 (KF-06) — cadangan = bawaan registry (dulu 0 dan 1,0)
    thr_type = cfg.get("discount_threshold_type", "pct")
    threshold = float(cfg.get("discount_threshold", default_of("commission.discount_threshold")) or 0)
    over = (disc_pct > threshold) if thr_type == "pct" else (disc_rp_per_unit > threshold)
    if not over:
        return per_unit, 1.0

    mech = cfg.get("discount_mechanic", "tier_factor")
    if mech == "cutoff":
        return per_unit, 0.0
    if mech == "potong_rp":
        return max(per_unit - float(cfg.get("discount_potong_rp", 0) or 0), 0.0), 1.0
    return per_unit, float(cfg.get("discount_factor", default_of("commission.discount_factor")) or 0)  # tier_factor


def pengali_harga(aturan: Dict[str, Any], line: Dict[str, Any]) -> Tuple[float, float, str, Optional[float]]:
    """`(tarif_efektif, pengali, alasan, selisih_pct)` untuk satu baris menurut `aturan` (bentuk potret).

    Pita/aturan asal harga tidak ada atau kosong → bawaan registri (satu pita terbuka ×1,0; semua ikut pita),
    bukan ×0."""
    from config_registry import default_of
    tarif_cfg = aturan["tarif"]
    tarif = float(tarif_cfg.get("per_unit_amount", 0) or 0)
    s = sumber_harga(line)
    if s in SUMBER_KHUSUS:
        aturan_sumber = aturan.get("price_source_rules") or default_of("commission.price_source_rules")
        r = next((x for x in aturan_sumber if x.get("sumber") == s), None)
        if r and r.get("cara") == "pengali_tetap":
            return tarif, float(r.get("pengali", 1.0) or 0), f"sumber_tetap:{s}", None
    alasan = "diskon_baris"
    if aturan.get("price_basis") == "pricelist":
        acuan = float(line.get(ACUAN_FIELD.get(aturan.get("acuan"), "list_price")) or 0)
        qty = float(line.get("quantity", 0) or 0)
        if acuan > 0 and qty > 0:
            bersih = float(line.get("line_total", 0) or 0) / qty
            selisih = (acuan - bersih) / acuan * 100
            if selisih <= 0:
                return tarif, 1.0, "harga_penuh", 0.0
            pita = aturan.get("price_bands") or default_of("commission.price_bands")
            return tarif, pilih_pita(pita, selisih), "pita", round(selisih, 2)
        alasan = "tanpa_pembanding"
    t, f = faktor_diskon(tarif_cfg, line, tarif)
    if (t, f) != (tarif, 1.0):
        alasan = "diskon_lewat_ambang"
    return t, f, alasan, None


def label_alasan(alasan: str, selisih: Optional[float]) -> str:
    """Teks layar untuk kode alasan harga; selisih `pita` dibulatkan 2 desimal, koma Indonesia, nol di belakang dibuang."""
    teks = ALASAN_LABEL.get(alasan, "")
    if "{selisih}" not in teks:
        return teks
    if selisih is None:
        return "Di bawah harga acuan"
    n = f"{round(float(selisih), 2):.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return teks.format(selisih=n)


def hitung_baris(aturan: Dict[str, Any], line: Dict[str, Any], *, fraksi: float, bobot: float, biaya: float,
                 biaya_diketahui: bool, pengali_capaian: float) -> Dict[str, Any]:
    """Komisi satu baris pesanan: qty terbayar × tarif efektif × pengali harga × pengali capaian, dibatasi margin."""
    tarif_cfg = aturan["tarif"]
    tarif, faktor, alasan, selisih = pengali_harga(aturan, line)
    base_qty = float(line.get("base_quantity", line.get("quantity", 0)) or 0)
    qty_line = float(line.get("quantity", 0) or 0)
    line_total = float(line.get("line_total", 0) or 0)
    # Pendapatan bersih per satuan DASAR (konsisten dengan qty dasar terbayar, P3-8).
    net_base = (line_total / base_qty) if base_qty else ((line_total / qty_line) if qty_line else float(line.get("price", 0) or 0))
    unit_margin = net_base - biaya
    cap_pct = float(tarif_cfg.get("margin_cap_pct", 0) or 0)

    def _komisi(fr: float) -> Tuple[float, float, bool]:
        qty = base_qty * fr
        kotor = qty * tarif * faktor * pengali_capaian
        if cap_pct > 0 and biaya_diketahui:   # P2-3: batas margin hanya bila biaya diketahui
            batas = (cap_pct / 100.0) * max(qty * unit_margin, 0.0)
            return max(min(kotor, batas), 0.0) * bobot, qty, kotor > batas
        return max(kotor, 0.0) * bobot, qty, False

    komisi, qty, dibatasi = _komisi(fraksi)
    return {"komisi": komisi, "komisi_penuh": _komisi(1.0)[0], "qty_dasar_terbayar": qty, "tarif": tarif,
            "pengali_harga": faktor, "alasan_harga": alasan, "selisih_pct": selisih,
            "pengali_capaian": pengali_capaian, "dibatasi": dibatasi}


def hitung_koreksi(aturan: Dict[str, Any], line: Dict[str, Any], *, fraksi: float, bobot: float, biaya: float,
                   biaya_diketahui: bool, pengali_capaian: float) -> Dict[str, Any]:
    """BTP-5 (A1-6) — koreksi komisi satu baris untuk uang pesanan yang pindah ke titipan (batal sesudah bayar / tutup
    sisa): NEGATIF dari komisi yang dulu dihitung untuk bagian itu — `hitung_baris` dengan |fraksi| (aturan potret yang
    sama, batas margin yang sama), lalu dibalik tandanya. Tidak lewat pemotong nol/batas margin sebagai angka negatif:
    kalau dipotong, koreksinya hilang (rancangan §5.9). Bentuk sama dengan `hitung_baris`; `komisi` ≤ 0,
    `qty_dasar_terbayar` ≤ 0."""
    h = hitung_baris(aturan, line, fraksi=abs(float(fraksi or 0)), bobot=bobot, biaya=biaya,
                     biaya_diketahui=biaya_diketahui, pengali_capaian=pengali_capaian)
    return {**h, "komisi": -h["komisi"], "komisi_penuh": -h["komisi_penuh"],
            "qty_dasar_terbayar": -h["qty_dasar_terbayar"]}


def label_koreksi(kode: str, nomor: str, kata: str = "dibatalkan") -> str:
    """Teks rincian baris koreksi: pesanan (nomor) + alasan ("sisa ditutup" / "dibatalkan" / "kedaluwarsa")."""
    return LABEL_KOREKSI[kode].format(nomor=nomor or "-", kata=kata or "dibatalkan")


# ── Pemuat dari database (satu-satunya bagian yang menyentuh Mongo) ─────────
async def muat_indeks_tarif(entity_id: Optional[str]) -> Dict[str, Dict[str, Any]]:
    """`rate_key` → tarif aktif (+ `_lingkup` "pt"/"semua_pt"). Baris PT menimpa baris `all`; tanpa PT hanya `all`."""
    from db import db
    ent = entity_id if entity_id and entity_id != "all" else None
    rows = await db.incentive_rates.find({"status": "active", "entity_id": {"$in": [ent, "all"] if ent else ["all"]}},
                                         {"_id": 0}).to_list(None)
    indeks: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        if r.get("entity_id") == "all":
            indeks[r.get("rate_key") or rate_key(r)] = {**r, "_lingkup": "semua_pt"}
    for r in rows:
        if ent and r.get("entity_id") == ent:
            indeks[r.get("rate_key") or rate_key(r)] = {**r, "_lingkup": "pt"}
    return indeks


# ── KA-4 — potret aturan komisi per baris pesanan ───────────────────────────
def _artikel_ringkas(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return None
    return {"id": doc.get("id"), "nama": doc.get("name"), "kode": doc.get("sku_prefix")}


async def _muat_artikel(template_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    from db import db
    ids = sorted({t for t in template_ids if t})
    if not ids:
        return {}
    rows = await db.product_templates.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "name": 1, "sku_prefix": 1}).to_list(len(ids))
    return {r["id"]: r for r in rows}


async def potret_pesanan(entity_id: str, items: List[Dict[str, Any]], products: Dict[str, Dict[str, Any]], *,
                         sumber: str = "pesanan") -> None:
    """Isi `it["commission_rule"]` tiap baris pesanan dengan aturan yang berlaku SEKARANG (satu kueri artikel)."""
    from core_utils import now_iso
    indeks = await muat_indeks_tarif(entity_id)
    pt = await aturan_pt(entity_id)
    artikel = await _muat_artikel([(products.get(it.get("product_id")) or {}).get("template_id") or "" for it in items])
    waktu = now_iso()
    for it in items:
        prod = products.get(it.get("product_id")) or {}
        tpl = prod.get("template_id") or ""
        tarif = pilih_tarif(indeks, product_id=it.get("product_id") or "", template_id=tpl,
                            category=it.get("category") or prod.get("category") or "")
        it["commission_rule"] = potret(tarif, pt, artikel=_artikel_ringkas(artikel.get(tpl)), sumber=sumber, waktu=waktu)


def kategori_baris(line: Dict[str, Any], prod: Dict[str, Any]) -> str:
    """Kategori baris pesanan YANG SUDAH ADA untuk mencari tarif kategori: isian `category` baris bila kuncinya ada — juga
    bila kosong (mesin lama: `rates.get(line.get("category", ""))`, kategori kosong = tanpa tarif kategori) — selain itu
    kategori produk (baris tanpa kunci itu diisi `bootstrap.backfill_so_line_category` dari produk). Pesanan BARU
    (`potret_pesanan`) memakai kategori produk bila baris kosong."""
    return (line.get("category") or "") if "category" in line else (prod.get("category") or "")


async def aturan_dari_sekarang(line: Dict[str, Any], entity_id: Optional[str], cache: Dict[str, Any], *,
                               sumber: str) -> Dict[str, Any]:
    """Potret aturan baris dari aturan SEKARANG (tidak ditulis ke basis data). `cache` menyimpan indeks tarif
    (`("indeks", PT)`), aturan PT (`("pt", PT)`), produk dan artikel; pemanggil boleh mengisi dua kunci pertama lebih dulu
    (simulasi: indeks sekarang + draf)."""
    from core_utils import now_iso
    from db import db
    ent = entity_id or ""
    if ("indeks", ent) not in cache:
        cache[("indeks", ent)] = await muat_indeks_tarif(entity_id)
    if ("pt", ent) not in cache:
        cache[("pt", ent)] = await aturan_pt(entity_id)
    pid = line.get("product_id") or ""
    if ("produk", pid) not in cache:
        cache[("produk", pid)] = await db.products.find_one({"id": pid}, {"_id": 0, "template_id": 1, "category": 1}) or {}
    prod = cache[("produk", pid)]
    tpl = prod.get("template_id") or ""
    if tpl and ("artikel", tpl) not in cache:
        cache[("artikel", tpl)] = (await _muat_artikel([tpl])).get(tpl)
    tarif = pilih_tarif(cache[("indeks", ent)], product_id=pid, template_id=tpl, category=kategori_baris(line, prod))
    return potret(tarif, cache[("pt", ent)], artikel=_artikel_ringkas(cache.get(("artikel", tpl))),
                  sumber=sumber, waktu=now_iso())


async def aturan_baris(line: Dict[str, Any], entity_id: Optional[str], cache: Dict[str, Any]) -> Dict[str, Any]:
    """Potret baris bila ada; bila tidak, potret dari aturan sekarang (`sumber="saat_hitung"`, tidak ditulis ke basis data).
    `cache` menyimpan indeks tarif, aturan PT, produk dan artikel selama satu proses hitung."""
    if line.get("commission_rule"):
        return line["commission_rule"]
    return await aturan_dari_sekarang(line, entity_id, cache, sumber="saat_hitung")


# ═══════════════════════════════════════════════════════════════════════════
# KA-6 — pengali capaian target + pembekuan aturan bulan saat akrual
# ═══════════════════════════════════════════════════════════════════════════
#: Kode alasan `pengali_capaian` (info["alasan"]).
ALASAN_CAPAIAN = ("mati", "semua_pt", "bukan_bulan", "tanpa_target_bulanan", "jenjang")
#: Basis capaian → kolom persen pengumpul Capaian KM-T2 (`None` = tanpa target periode itu).
_KOLOM_CAPAIAN = {"omzet_bersih": "pct_omzet", "uang_masuk": "pct_pencairan"}
PESAN_BUKAN_BULAN = "Periode komisi yang dibekukan harus satu bulan, contoh: 2026-11."
PESAN_BELUM_AKRUAL = "Aturan komisi {bulan} baru bisa dibekukan sesudah akrual komisinya dibukukan."


def bulan_komisi(period: Any) -> Optional[str]:
    """`YYYY-MM` bila `period` satu bulan; selain itu `None` (triwulan, tahun, bentuk lain)."""
    from services import incentive_periods as ip
    try:
        return ip.normalize("month", str(period or ""))[1]
    except ip.PeriodeError:
        return None


def bulan_periode(period: Any) -> List[str]:
    """Bulan (`YYYY-MM`) dalam periode triwulan `YYYY-Qn` / tahun `YYYY` mesin komisi; selain itu `[]`. Triwulan & tahun
    KALENDER (bulan tutup tahun buku 12), sama dengan `sales_force_service._in_period`."""
    from services import incentive_periods as ip
    p = str(period or "").strip().upper()
    for jenis in ("quarter", "year"):
        try:
            return ip.months_between(*ip.bounds_with(jenis, p, 12))
        except ip.PeriodeError:
            continue
    return []


def akhir_bulan_wib(bulan: str) -> datetime:
    """Detik terakhir bulan `YYYY-MM` jam dinding WIB (hari terakhir 23.59.59) — saat jenjang bulan itu dibaca."""
    from services.book_date import WIB
    from services.periodic_posting import akhir_periode
    return datetime.fromisoformat(f"{akhir_periode(bulan)}T23:59:59").replace(tzinfo=WIB)


async def capaian_aktif(entity_id: Optional[str], bulan: Optional[Iterable[str]] = None) -> bool:
    """Pengali capaian menyala di PT itu ("Semua PT"/kosong → `False`). Tanpa `bulan`: nilai SAAT INI. Dengan `bulan`
    (`YYYY-MM`): menyala di SALAH SATU bulan itu menurut aturan bulannya (`_aturan_bulan`: dokumen beku, selain itu
    nilai pada akhir bulan) — mesin memakainya untuk memutuskan triwulan/tahun dihitung sebagai Σ hasil per bulan
    (`sales_force_service.compute_commission`), tidak bergantung pada pengaturan hari ini."""
    if not entity_id or entity_id == "all":
        return False
    if bulan is None:
        return bool((await aturan_capaian(entity_id))["aktif"])
    for b in bulan:
        if (await _aturan_bulan(entity_id, b))[0]["aktif"]:
            return True
    return False


async def _jurnal_akrual_hidup(entity_id: str, bulan: str) -> Optional[Dict[str, Any]]:
    """Jurnal akrual insentif (bukan koreksi) PT·bulan yang tidak dianulir (`gl_service.post_incentive_accrual`)."""
    from db import db
    return await db.journal_entries.find_one({"source_type": "incentive_accrual", "source_id": f"{entity_id}:{bulan}",
                                              "status": {"$ne": "void"}}, {"_id": 0, "id": 1})


async def _beku_berlaku(doc: Optional[Dict[str, Any]]) -> bool:
    """Dokumen beku hanya berlaku selama jurnal akrual yang membekukannya (`journal_id`) tidak dianulir. Akrual gagal
    dibukukan (mis. periode tertutup) atau dianulir → dokumen diabaikan (aturan akhir bulan) dan diganti saat akrual
    berikutnya dibukukan."""
    jid = (doc or {}).get("journal_id")
    if not jid:
        return False
    from db import db
    return bool(await db.journal_entries.find_one({"id": jid, "source_type": "incentive_accrual",
                                                   "status": {"$ne": "void"}}, {"_id": 0, "id": 1}))


async def _aturan_beku(entity_id: str, bulan: str) -> Optional[Dict[str, Any]]:
    from db import db
    doc = await db.commission_period_rules.find_one({"entity_id": entity_id, "period": bulan},
                                                    {"_id": 0, "achievement": 1, "journal_id": 1})
    return doc["achievement"] if await _beku_berlaku(doc) else None


async def _aturan_bulan(entity_id: str, bulan: str) -> Tuple[Dict[str, Any], str]:
    """`(aturan capaian bulan itu, sumber)`: dokumen beku `commission_period_rules` (`"beku"`), selain itu nilai kunci
    yang berlaku pada akhir bulan 23.59.59 WIB (`"akhir_bulan"`)."""
    beku = await _aturan_beku(entity_id, bulan)
    if beku:
        return beku, "beku"
    return await aturan_capaian(entity_id, at=akhir_bulan_wib(bulan)), "akhir_bulan"


async def _capaian_pct(entity_id: str, sales_id: str, bulan: str, basis: str) -> Optional[float]:
    """Persen capaian sales bulan itu = sel tabel Capaian KM-T2 (fakta disegarkan dulu; target BULANAN saja)."""
    from services.incentive_me import capaian_saya
    return (await capaian_saya(entity_id, sales_id, bulan)).get(_KOLOM_CAPAIAN.get(basis, "pct_omzet"))


async def pengali_capaian(entity_id: Optional[str], sales_id: str, period: str) -> Tuple[float, Dict[str, Any]]:
    """`(pengali, info)` capaian target sales untuk komisi `period` (rancangan §6.4).

    Aturan = dokumen beku `commission_period_rules` bulan itu bila ada (`sumber_jenjang="beku"`), selain itu nilai
    kunci `commission.achievement_*` yang berlaku pada akhir bulan komisi 23.59.59 WIB (`"akhir_bulan"`). Capaian =
    angka bulan komisi (bulan uang masuk) dibanding target BULANAN. Pengali 1 dengan alasan: `semua_pt` ("Semua PT" —
    definisi angka berbeda per PT) · `bukan_bulan` (triwulan/tahun dihitung langsung dan salah satu bulannya menyala;
    `compute_commission` memecahnya per bulan) · `mati` (untuk triwulan/tahun: mati di semua bulannya) ·
    `tanpa_target_bulanan`; selain itu `jenjang` (`pilih_jenjang`). Dokumen beku dipakai hanya selama jurnal akrualnya
    tidak dianulir (`_beku_berlaku`).
    info = `{"aktif", "basis", "capaian_pct", "sumber_jenjang", "alasan"}`."""
    info: Dict[str, Any] = {"aktif": None, "basis": None, "capaian_pct": None, "sumber_jenjang": None, "alasan": ""}
    if not entity_id or entity_id == "all":
        return 1.0, {**info, "alasan": "semua_pt"}
    bulan = bulan_komisi(period)
    if bulan is None:   # triwulan/tahun: menyala bila salah satu bulannya menyala menurut aturan bulan itu
        daftar = bulan_periode(period)
        aktif = (await capaian_aktif(entity_id, daftar) if daftar
                 else bool((await aturan_capaian(entity_id))["aktif"]))
        info["aktif"] = aktif
        return 1.0, {**info, "alasan": "bukan_bulan" if aktif else "mati"}
    aturan, sumber = await _aturan_bulan(entity_id, bulan)
    info.update(aktif=bool(aturan["aktif"]), basis=aturan["basis"], sumber_jenjang=sumber)
    if not info["aktif"]:
        return 1.0, {**info, "alasan": "mati"}
    pct = await _capaian_pct(entity_id, sales_id, bulan, info["basis"])
    if pct is None:
        return 1.0, {**info, "alasan": "tanpa_target_bulanan"}
    return pilih_jenjang(aturan["jenjang"], float(pct)), {**info, "capaian_pct": pct, "alasan": "jenjang"}


def bulan_awal_periode(period: Any) -> Optional[str]:
    """Bulan pertama periode komisi: bulan itu sendiri (`YYYY-MM`), bulan pertama triwulan/tahun; selain itu `None`."""
    bulan = bulan_komisi(period)
    if bulan:
        return bulan
    daftar = bulan_periode(period)
    return daftar[0] if daftar else None


#: BTP-5 (A1-6, ruling R13/R16/R17/R19) — SATU tempat finalisasi komisi per (PT, sales, bulan) + saldo potongannya:
#: indeks wajib `uq_commission_carry`. Ditulis setiap kali komisi bulan itu difinalkan untuk PT itu
#: (`catat_saldo_potongan`); dibaca mesin untuk saldo masuk bulan berikutnya (`saldo_potongan_awal`) dan untuk menilai
#: apakah bulan bayar sebuah pesanan sudah final sebelum pesanan itu batal / ditutup sisanya (`penilai_final`).
KOLEKSI_SALDO = "commission_carry_balances"


async def catatan_berlaku(doc: Dict[str, Any]) -> bool:
    """Finalisasi yang dicatat masih berlaku: tanpa jurnal (`journal_id` kosong — bulan bertotal 0 diakru tanpa jurnal),
    atau jurnal yang dicatatnya (akrual insentif, atau jurnal gaji pada mode tanpa akrual mis. `pay_on_invoice`) masih
    hidup: tidak `void` dan belum dibalik (`gl_service.reversal_of` — anulir proses gaji membalik jurnal gajinya).
    Tidak berlaku → saldo & status final bulan itu TIDAK dibaca sampai bulan itu difinalkan lagi."""
    jid = (doc or {}).get("journal_id") or ""
    if not jid:
        return True
    from db import db
    from services.gl_service import reversal_of   # lokal: gl_service memanggil modul ini
    je = await db.journal_entries.find_one({"id": jid, "status": {"$ne": "void"}}, {"_id": 0})
    return bool(je) and not await reversal_of(je)


def _baca_waktu(v: Any) -> Optional[datetime]:
    """Waktu ISO → `datetime` berzona (tanpa zona = UTC); kosong/tak terbaca → None."""
    from datetime import timezone
    try:
        d = datetime.fromisoformat(str(v).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _sebelum(a: Any, b: Any) -> bool:
    """Waktu ISO `a` lebih awal dari `b` (zona ikut; tanpa zona = UTC). Salah satu kosong/tak terbaca → False."""
    da, db_ = _baca_waktu(a), _baca_waktu(b)
    return bool(da and db_ and da < db_)


def _paling_awal(waktu: Iterable[Any]) -> str:
    """Waktu ISO paling awal dari `waktu` (yang tak terbaca dilewati); "" bila tidak ada."""
    terbaca = [(d, str(v)) for v in waktu for d in (_baca_waktu(v),) if d]
    return min(terbaca)[1] if terbaca else ""


async def waktu_final_cadangan(entity_id: str, bulan: str) -> str:
    """BTP-5 (ruling R25, tinjauan akhir I1) — waktu final CADANGAN komisi PT·bulan untuk bulan yang difinalkan sebelum
    catatan finalisasi ada (data sebelum rilis cabang ini): `created_at` paling awal dari jurnal akrual insentif
    (`incentive_accrual`, kunci `PT:bulan`) yang hidup, atau jurnal gaji (`payroll_run` — kunci proses gaji PT·bulan
    itu, atau kunci lama `PT:bulan`) yang terposting. "Hidup/terposting" = tidak `void` dan belum dibalik
    (`gl_service.reversal_of`, sama dengan `catatan_berlaku`). Tidak ada keduanya → "" (belum final). Hanya membaca —
    tidak ada catatan yang ditulis (tanpa backfill)."""
    if not entity_id or entity_id == "all" or not bulan:
        return ""
    from db import db
    from services.gl_service import reversal_of   # lokal: gl_service memanggil modul ini
    kunci = f"{entity_id}:{bulan}"
    proses = [r["id"] async for r in db.hr_payroll_runs.find({"entity_id": entity_id, "period": bulan},
                                                              {"_id": 0, "id": 1}) if r.get("id")]
    calon: List[str] = []
    async for je in db.journal_entries.find(
            {"status": {"$ne": "void"}, "$or": [
                {"source_type": "incentive_accrual", "source_id": kunci},
                {"source_type": "payroll_run", "source_id": {"$in": [kunci, *proses]}}]},
            {"_id": 0}):
        if je.get("created_at") and not await reversal_of(je):
            calon.append(je["created_at"])
    return _paling_awal(calon)


def penilai_final(sales_id: str, entity_id: Optional[str]):
    """BTP-5 (R16/R19/R25) — `async (pt, bulan, waktu) -> bool`: komisi bulan `bulan` sales ini di PT `pt` sudah FINAL
    sebelum `waktu` — ada catatan finalisasi (`commission_carry_balances`) yang `finalized_at`-nya (saat angka yang
    difinalkan dihitung, `catat_saldo_potongan`) lebih awal dari `waktu` DAN finalisasinya masih berlaku
    (`catatan_berlaku`). R25 — TANPA catatan sama sekali untuk (PT, sales, bulan) (bulan yang difinalkan sebelum
    rilis): final sejak `waktu_final_cadangan` (jurnal akrual hidup / jurnal gaji terposting PT·bulan itu, paling awal);
    catatan yang ada selalu menang atas cadangan. Catatan dimuat sekali per proses hitung (hanya bila dipanggil: sales
    tanpa pesanan batal/tutup sisa tidak membaca apa pun); cadangan sekali per PT·bulan."""
    cache: Dict[str, Any] = {}

    async def _final(pt: str, bulan: str, waktu: str) -> bool:
        if "doc" not in cache:
            from db import db
            q: Dict[str, Any] = {"sales_id": sales_id}
            if entity_id and entity_id != "all":
                q["entity_id"] = entity_id
            cache["doc"] = {(d.get("entity_id") or "", d.get("period") or ""): d
                            async for d in db[KOLEKSI_SALDO].find(q, {"_id": 0})}
            cache["sah"], cache["cadangan"] = {}, {}
        kunci = (pt or "", bulan or "")
        d = cache["doc"].get(kunci)
        if d is None:
            if kunci not in cache["cadangan"]:
                cache["cadangan"][kunci] = await waktu_final_cadangan(*kunci)
            return _sebelum(cache["cadangan"][kunci], waktu)
        if not _sebelum(d.get("finalized_at"), waktu):
            return False
        jid = d.get("journal_id") or ""
        if jid not in cache["sah"]:
            cache["sah"][jid] = await catatan_berlaku(d)
        return cache["sah"][jid]
    return _final


async def saldo_potongan_awal(sales_id: str, period: Any, entity_id: Optional[str]) -> Dict[str, float]:
    """BTP-5 (A1-6) — saldo potongan komisi yang terbawa ke periode ini, per PT: `carry_out` sales itu di
    `commission_carry_balances` bulan SEBELUM bulan pertama periode, PT yang sama, hanya catatan yang berlaku
    (`catatan_berlaku`) dan hanya angka negatif; tidak ada → `{}` (saldo 0). PT tertentu → satu PT; "Semua PT"/kosong →
    setiap PT yang menyimpan saldo sales itu (dijumlah pemanggil per PT)."""
    awal = bulan_awal_periode(period)
    if not awal or not sales_id:
        return {}
    from db import db
    from services import incentive_periods as ip
    q: Dict[str, Any] = {"period": ip.previous_period("month", awal), "sales_id": sales_id, "carry_out": {"$lt": 0}}
    if entity_id and entity_id != "all":
        q["entity_id"] = entity_id
    out: Dict[str, float] = {}
    async for doc in db[KOLEKSI_SALDO].find(q, {"_id": 0}):
        if await catatan_berlaku(doc):
            ent = doc.get("entity_id") or ""
            out[ent] = round(out.get(ent, 0.0) + float(doc.get("carry_out") or 0), 2)
    return out


async def catat_saldo_potongan(entity_id: str, period: str, rincian: Optional[Iterable[Dict[str, Any]]], *,
                               oleh: str, sumber: str, journal_id: str = "") -> int:
    """BTP-5 (A1-6, R13/R16/R17/R19/R25) — catat finalisasi komisi per sales untuk PT·bulan yang komisinya DIFINALKAN:
    akrual manual (juga bila total PT 0 dan tanpa jurnal), posting gaji (dari hasil mesin di slip, SEMUA mode gaji yang
    menjalankan mesin), dan setiap akrual diulang. `rincian` = baris per sales yang membawa hasil mesin (`carry_out`,
    + `commission_raw`, `carry_in`, `total`, `computed_at`); baris tanpa `carry_out` / bergalat dilewati. Upsert untuk
    setiap sales (juga saldo 0 — catatan menandai bulan itu final).

    R19 — `finalized_at` = saat ANGKA yang difinalkan dihitung (`computed_at`: hitung slip saat proses gaji dibuat /
    dihitung ulang, atau hitung mesin saat akrual; tanpa itu = sekarang). Ditimpa HANYA bila finalisasi lama catatan itu
    sudah tidak berlaku saat ditulis (`catatan_berlaku`: jurnalnya `void` / dibalik); selama finalisasi lama masih
    berlaku, `finalized_at` tidak pernah ditimpa (finalisasi ulang = koreksi atas angka yang sama-sama sudah final).
    R25 — catatan PERTAMA (belum pernah ada) memakai waktu paling awal dari `computed_at` dan `waktu_final_cadangan`
    (bulan yang difinalkan sebelum rilis tetap final sejak jurnal akrual/gajinya).
    `journal_id` = jurnal finalisasi (akrual insentif, atau jurnal gaji pada mode tanpa akrual); "" bila tidak ada.
    Pemanggil menulis SESUDAH jurnalnya berhasil. → jumlah catatan yang ditulis."""
    from pymongo.errors import DuplicateKeyError
    from core_utils import new_id, now_iso
    from db import db
    bulan = bulan_komisi(period)
    if not entity_id or entity_id == "all" or not bulan:
        return 0
    ditulis = 0
    cadangan: Optional[str] = None   # R25 — waktu final cadangan PT·bulan (dibaca sekali, hanya bila perlu)
    for r in rincian or ():
        sid = r.get("sales_id") or ""
        if not sid or r.get("galat") or r.get("carry_out") is None:
            continue
        q = {"entity_id": entity_id, "sales_id": sid, "period": bulan}
        sekarang = now_iso()
        isi = {"carry_out": round(float(r.get("carry_out") or 0), 2) or 0.0,
               "carry_in": round(float(r.get("carry_in") or 0), 2) or 0.0,
               "commission_raw": round(float(r.get("commission_raw") or 0), 2) or 0.0,
               "total": round(float(r.get("total") or 0), 2), "source": sumber, "journal_id": journal_id or "",
               "recorded_at": sekarang, "recorded_by": oleh or ""}
        waktu_final = str(r.get("computed_at") or "") or sekarang
        ada = await db[KOLEKSI_SALDO].find_one(q, {"_id": 0})
        if ada is None:
            # R25 — catatan PERTAMA untuk bulan yang sudah difinalkan sebelum rilis (jurnal akrual hidup / jurnal gaji
            # terposting lebih awal): waktu finalnya tetap waktu cadangan itu — tanpa ini finalisasi ulang membuat bulan
            # itu berbalik "belum final" (catatan menang atas cadangan). Bulan baru: jurnalnya lahir sesudah angka
            # dihitung, jadi waktu final tetap `computed_at`.
            if cadangan is None:
                cadangan = await waktu_final_cadangan(entity_id, bulan)
            waktu_final = _paling_awal((waktu_final, cadangan)) or waktu_final
        if ada is not None and await catatan_berlaku(ada):
            await db[KOLEKSI_SALDO].update_one(q, {"$set": isi})   # finalisasi lama masih berlaku: waktu final tetap
        else:
            try:
                await db[KOLEKSI_SALDO].update_one(
                    q, {"$set": {**isi, "finalized_at": waktu_final}, "$setOnInsert": {"id": new_id("cmsb")}},
                    upsert=True)
            except DuplicateKeyError:   # dua finalisasi bersamaan: dokumen pemenang diperbarui (waktu finalnya tetap)
                await db[KOLEKSI_SALDO].update_one(q, {"$set": isi})
        ditulis += 1
    return ditulis


def _rincian_bersih(rincian: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Baris catatan per sales dari pemanggil (`{sales_id, total, breakdown?, employee_id?}` atau `{sales_id, galat}`);
    total dibulatkan 2 desimal."""
    out = []
    for r in rincian:
        if r.get("galat"):
            out.append({"sales_id": r.get("sales_id") or "", "total": None, "galat": str(r["galat"])})
            continue
        baris = {"sales_id": r.get("sales_id") or "", "total": round(float(r.get("total") or 0), 2)}
        for k in ("employee_id", "breakdown"):
            if r.get(k) is not None:
                baris[k] = r[k]
        out.append(baris)
    return out


async def _rincian_hitung_ulang(entity_id: str, bulan: str) -> Tuple[List[Dict[str, Any]], str]:
    """Catatan per sales dihitung ulang dengan mesin (cadangan bila pemanggil tidak membawa rincian). Upaya terbaik:
    galat satu sales → baris itu bertanda `galat` (sales lain tetap dicatat); galat daftar sales → `([], kalimat)`."""
    from services import sales_force_service as sf          # lokal: sales_force_service mengimpor modul ini
    from services.incentive_targets import sales_roster
    try:
        daftar = await sales_roster(entity_id, "month", bulan)
    except Exception as exc:  # noqa: BLE001 — catatan saja; jurnal & aturan beku tidak boleh gagal karenanya
        return [], f"Daftar sales tidak bisa dimuat saat dibekukan: {exc}"
    sales: List[Dict[str, Any]] = []
    for u in daftar:
        try:
            c = await sf.compute_commission(u["id"], bulan, entity_id=entity_id)
            sales.append({"sales_id": u["id"], "total": round(float(c.get("total_incentive") or 0), 2),
                          "breakdown": c.get("breakdown") or []})
        except Exception as exc:  # noqa: BLE001 — catatan saja (tinjauan akhir I2)
            sales.append({"sales_id": u["id"], "total": None, "galat": f"Komisi sales ini gagal dihitung saat dibekukan: {exc}"})
    return sales, ""


async def bekukan_periode(entity_id: str, period: str, *, oleh: str, journal_id: str = "",
                          rincian_sales: Optional[List[Dict[str, Any]]] = None, sumber_rincian: str = "") -> Dict[str, Any]:
    """Bekukan aturan komisi bulan itu saat akrual dibukukan (rancangan §6.4, §6.5a; `02_STANDAR.md` §5 D3).

    Dipanggil `gl_service.post_incentive_accrual` SESUDAH jurnal akrual pertama tersimpan, dan sebelum jurnal koreksi.
    `commission_period_rules` `{id "cmpr_…", entity_id, period, achievement {aktif, basis, jenjang} (nilai yang berlaku
    pada akhir bulan — SATU-SATUNYA yang dibekukan & dibaca mesin), sales [{sales_id, total, breakdown?, employee_id?,
    galat?}] (CATATAN per sales), sales_sumber, sales_galat?, journal_id (jurnal akrual yang membekukan), recorded_at,
    recorded_by, replaces?}`. Saldo potongan komisi (BTP-5) TIDAK di sini, tetapi di `commission_carry_balances`
    (`catat_saldo_potongan`).

    Tinjauan akhir I2 — `sales` hanya catatan dan tidak pernah menggagalkan akrual: `rincian_sales` dari pemanggil
    dipakai apa adanya (posting gaji: komisi slip yang diakru, `sales_sumber="slip_gaji"`; akrual manual: hasil mesin yang
    sama dengan total jurnal, `"akrual"`), tanpa menghitung ulang. Tanpa `rincian_sales` → dihitung ulang upaya terbaik
    (`"hitung_ulang"`; galat satu sales = baris bertanda `galat`, galat daftar sales = `sales_galat`). Galat membaca aturan
    capaian (yang dibekukan) tetap merambat — akrual berikutnya membekukan ulang.

    Dokumen yang ada dan jurnal akrualnya masih hidup dikembalikan, tidak ditimpa — koreksi akrual sesudahnya tetap
    memakai jenjang beku, angka hanya berubah karena data sumber (bayar/retur). Dokumen yang jurnal akrualnya tidak ada
    / dianulir DIGANTI (satu dokumen per PT·bulan; `replaces` mencatat yang diganti) dengan aturan akhir bulan saat ini.
    `journal_id` kosong → jurnal akrual hidup PT·bulan itu; tidak ada → `ValueError`."""
    from pymongo.errors import DuplicateKeyError
    from core_utils import new_id, now_iso
    from db import db
    bulan = bulan_komisi(period)
    if not entity_id or entity_id == "all" or bulan is None:
        raise ValueError(PESAN_BUKAN_BULAN)
    jid = journal_id or ((await _jurnal_akrual_hidup(entity_id, bulan)) or {}).get("id", "")
    if not jid:
        from services.incentive_periods import period_label
        raise ValueError(PESAN_BELUM_AKRUAL.format(bulan=period_label("month", bulan)))
    q = {"entity_id": entity_id, "period": bulan}
    ada = await db.commission_period_rules.find_one(q, {"_id": 0})
    if ada and await _beku_berlaku(ada):
        return ada
    achievement = await aturan_capaian(entity_id, at=akhir_bulan_wib(bulan))   # yang dibekukan: dulu, dan merambat
    galat_daftar = ""
    try:
        if rincian_sales is not None:
            sales, sumber = _rincian_bersih(rincian_sales), sumber_rincian or "pemanggil"
        else:
            (sales, galat_daftar), sumber = await _rincian_hitung_ulang(entity_id, bulan), "hitung_ulang"
    except Exception as exc:  # noqa: BLE001 — catatan saja; jurnal sudah tersimpan
        sales, sumber, galat_daftar = [], sumber_rincian or "hitung_ulang", f"Rincian per sales tidak bisa disusun: {exc}"
    doc = {"id": new_id("cmpr"), **q, "achievement": achievement, "sales": sales, "sales_sumber": sumber,
           "journal_id": jid, "recorded_at": now_iso(), "recorded_by": oleh or ""}
    if galat_daftar:
        doc["sales_galat"] = galat_daftar
    if ada:   # potret lama tanpa jurnal akrual hidup (akrual gagal / dianulir) → diganti, tetap satu per PT·bulan
        doc["replaces"] = {k: ada.get(k) for k in ("id", "journal_id", "recorded_at", "recorded_by")}
        await db.commission_period_rules.replace_one(q, dict(doc))
        return doc
    try:
        await db.commission_period_rules.insert_one(dict(doc))
    except DuplicateKeyError:   # dua akrual bersamaan: dokumen pemenang yang berlaku (indeks uq_commission_period)
        return await db.commission_period_rules.find_one(q, {"_id": 0})
    return doc
