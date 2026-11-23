"""KA-1 — aturan pengali komisi per artikel: validasi nilai tabel + pembaca kunci Pusat Pengaturan.

Kunci `commission.price_*` (pengali menurut harga jual) dan `commission.achievement_*` (pengali capaian target) hidup di
Pusat Pengaturan (`config_catalog_core`). Modul ini memeriksa isi tabelnya saat disimpan (`config_resolver.set_value`)
dan membacanya untuk mesin komisi. Rancangan: `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md`.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

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


# ── Pemuat dari database (satu-satunya bagian yang menyentuh Mongo) ─────────
async def muat_indeks_tarif(entity_id: Optional[str]) -> Dict[str, Dict[str, Any]]:
    """`rate_key` → tarif aktif (+ `_lingkup` "pt"/"semua_pt"). Baris PT menimpa baris `all`; tanpa PT hanya `all`."""
    from db import db
    ent = entity_id if entity_id and entity_id != "all" else None
    rows = await db.incentive_rates.find({"status": "active"}, {"_id": 0}).to_list(5000)
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


async def aturan_baris(line: Dict[str, Any], entity_id: Optional[str], cache: Dict[str, Any]) -> Dict[str, Any]:
    """Potret baris bila ada; bila tidak, potret dari aturan sekarang (`sumber="saat_hitung"`, tidak ditulis ke basis data).
    `cache` menyimpan indeks tarif, aturan PT, produk dan artikel selama satu proses hitung."""
    if line.get("commission_rule"):
        return line["commission_rule"]
    from core_utils import now_iso
    from db import db
    ent = entity_id or ""
    if ("indeks", ent) not in cache:
        cache[("indeks", ent)] = await muat_indeks_tarif(entity_id)
        cache[("pt", ent)] = await aturan_pt(entity_id)
    pid = line.get("product_id") or ""
    if ("produk", pid) not in cache:
        cache[("produk", pid)] = await db.products.find_one({"id": pid}, {"_id": 0, "template_id": 1, "category": 1}) or {}
    prod = cache[("produk", pid)]
    tpl = prod.get("template_id") or ""
    if tpl and ("artikel", tpl) not in cache:
        cache[("artikel", tpl)] = (await _muat_artikel([tpl])).get(tpl)
    tarif = pilih_tarif(cache[("indeks", ent)], product_id=pid, template_id=tpl,
                        category=line.get("category") or prod.get("category") or "")
    return potret(tarif, cache[("pt", ent)], artikel=_artikel_ringkas(cache.get(("artikel", tpl))),
                  sumber="saat_hitung", waktu=now_iso())


# ═══════════════════════════════════════════════════════════════════════════
# KA-6 — pengali capaian target + pembekuan aturan bulan saat akrual
# ═══════════════════════════════════════════════════════════════════════════
#: Kode alasan `pengali_capaian` (info["alasan"]).
ALASAN_CAPAIAN = ("mati", "semua_pt", "bukan_bulan", "tanpa_target_bulanan", "jenjang")
#: Basis capaian → kolom persen pengumpul Capaian KM-T2 (`None` = tanpa target periode itu).
_KOLOM_CAPAIAN = {"omzet_bersih": "pct_omzet", "uang_masuk": "pct_pencairan"}
PESAN_BUKAN_BULAN = "Periode komisi yang dibekukan harus satu bulan, contoh: 2026-11."


def bulan_komisi(period: Any) -> Optional[str]:
    """`YYYY-MM` bila `period` satu bulan; selain itu `None` (triwulan, tahun, bentuk lain)."""
    from services import incentive_periods as ip
    try:
        return ip.normalize("month", str(period or ""))[1]
    except ip.PeriodeError:
        return None


def akhir_bulan_wib(bulan: str) -> datetime:
    """Detik terakhir bulan `YYYY-MM` jam dinding WIB (hari terakhir 23.59.59) — saat jenjang bulan itu dibaca."""
    from services.book_date import WIB
    from services.periodic_posting import akhir_periode
    return datetime.fromisoformat(f"{akhir_periode(bulan)}T23:59:59").replace(tzinfo=WIB)


async def capaian_aktif(entity_id: Optional[str]) -> bool:
    """Pengali capaian menyala SAAT INI di PT itu ("Semua PT"/kosong → `False`). Mesin memakainya untuk memutuskan
    periode triwulan/tahun dihitung sebagai Σ hasil per bulan (`sales_force_service.compute_commission`)."""
    if not entity_id or entity_id == "all":
        return False
    return (await aturan_capaian(entity_id))["aktif"]


async def _aturan_beku(entity_id: str, bulan: str) -> Optional[Dict[str, Any]]:
    from db import db
    doc = await db.commission_period_rules.find_one({"entity_id": entity_id, "period": bulan},
                                                    {"_id": 0, "achievement": 1})
    return (doc or {}).get("achievement")


async def _capaian_pct(entity_id: str, sales_id: str, bulan: str, basis: str) -> Optional[float]:
    """Persen capaian sales bulan itu = sel tabel Capaian KM-T2 (fakta disegarkan dulu; target BULANAN saja)."""
    from services.incentive_me import capaian_saya
    return (await capaian_saya(entity_id, sales_id, bulan)).get(_KOLOM_CAPAIAN.get(basis, "pct_omzet"))


async def pengali_capaian(entity_id: Optional[str], sales_id: str, period: str) -> Tuple[float, Dict[str, Any]]:
    """`(pengali, info)` capaian target sales untuk komisi `period` (rancangan §6.4).

    Aturan = dokumen beku `commission_period_rules` bulan itu bila ada (`sumber_jenjang="beku"`), selain itu nilai
    kunci `commission.achievement_*` yang berlaku pada akhir bulan komisi 23.59.59 WIB (`"akhir_bulan"`). Capaian =
    angka bulan komisi (bulan uang masuk) dibanding target BULANAN. Pengali 1 dengan alasan: `semua_pt` ("Semua PT" —
    definisi angka berbeda per PT) · `bukan_bulan` (triwulan/tahun dihitung langsung; `compute_commission` memecahnya
    per bulan) · `mati` · `tanpa_target_bulanan`; selain itu `jenjang` (`pilih_jenjang`).
    info = `{"aktif", "basis", "capaian_pct", "sumber_jenjang", "alasan"}`."""
    info: Dict[str, Any] = {"aktif": None, "basis": None, "capaian_pct": None, "sumber_jenjang": None, "alasan": ""}
    if not entity_id or entity_id == "all":
        return 1.0, {**info, "alasan": "semua_pt"}
    bulan = bulan_komisi(period)
    if bulan is None:
        aturan = await aturan_capaian(entity_id)
        info.update(aktif=aturan["aktif"], basis=aturan["basis"])
        return 1.0, {**info, "alasan": "bukan_bulan" if aturan["aktif"] else "mati"}
    beku = await _aturan_beku(entity_id, bulan)
    aturan = beku or await aturan_capaian(entity_id, at=akhir_bulan_wib(bulan))
    info.update(aktif=bool(aturan["aktif"]), basis=aturan["basis"], sumber_jenjang="beku" if beku else "akhir_bulan")
    if not info["aktif"]:
        return 1.0, {**info, "alasan": "mati"}
    pct = await _capaian_pct(entity_id, sales_id, bulan, info["basis"])
    if pct is None:
        return 1.0, {**info, "alasan": "tanpa_target_bulanan"}
    return pilih_jenjang(aturan["jenjang"], float(pct)), {**info, "capaian_pct": pct, "alasan": "jenjang"}


async def bekukan_periode(entity_id: str, period: str, *, oleh: str) -> Dict[str, Any]:
    """Bekukan aturan komisi bulan itu saat akrual dibukukan (rancangan §6.4, §6.5a; `02_STANDAR.md` §5 D3).

    Sisip-bila-belum-ada `commission_period_rules` `{id "cpr_…", entity_id, period, achievement {aktif, basis,
    jenjang} (nilai yang berlaku pada akhir bulan), sales [{sales_id, total, breakdown}] (catatan hasil mesin per sales
    daftar PT saat dibekukan), recorded_at, recorded_by}`. Idempoten: dokumen yang sudah ada dikembalikan, tidak
    ditimpa — koreksi akrual sesudahnya tetap memakai jenjang beku, angka hanya berubah karena data sumber
    (bayar/retur)."""
    from pymongo.errors import DuplicateKeyError
    from core_utils import new_id, now_iso
    from db import db
    bulan = bulan_komisi(period)
    if not entity_id or entity_id == "all" or bulan is None:
        raise ValueError(PESAN_BUKAN_BULAN)
    q = {"entity_id": entity_id, "period": bulan}
    ada = await db.commission_period_rules.find_one(q, {"_id": 0})
    if ada:
        return ada
    from services import sales_force_service as sf          # lokal: sales_force_service mengimpor modul ini
    from services.incentive_targets import sales_roster
    achievement = await aturan_capaian(entity_id, at=akhir_bulan_wib(bulan))
    sales: List[Dict[str, Any]] = []
    for u in await sales_roster(entity_id, "month", bulan):
        c = await sf.compute_commission(u["id"], bulan, entity_id=entity_id)
        sales.append({"sales_id": u["id"], "total": round(float(c.get("total_incentive") or 0), 2),
                      "breakdown": c.get("breakdown") or []})
    doc = {"id": new_id("cpr"), **q, "achievement": achievement, "sales": sales, "recorded_at": now_iso(),
           "recorded_by": oleh or ""}
    try:
        await db.commission_period_rules.insert_one(dict(doc))
    except DuplicateKeyError:   # dua akrual bersamaan: dokumen pemenang yang berlaku (indeks uq_commission_period)
        return await db.commission_period_rules.find_one(q, {"_id": 0})
    return doc
