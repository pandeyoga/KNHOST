"""KF-T8 — bangkitkan isi `scripts/guardrails/config_fallback_allow.json` dari temuan pohon saat ini.

Dijalankan sekali saat penjaga lahir (14 Nov 2026). Butir "bukan pengaturan" ditulis tangan (tabel BUKAN); sisanya
garis dasar beralasan (kelas dampak dihitung dari batas registry). Pemakaian:
    python buat_garis_dasar.py <root repo> > config_fallback_allow.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT / "scripts" / "guardrails"))
import verify_config_fallback as v  # noqa: E402

BUKAN = [  # (berkas, kunci, potongan, alasan)
    ("backend/services/hr_payroll_service.py", "hr.feature_toggles.pph21", 'float(s.get("pph21", 0) or 0) for s in prior',
     "Bukan pengaturan: nominal PPh 21 pada slip gaji sebelumnya (`s` = slip), bukan sakelar "
     "`hr.feature_toggles.pph21`."),
    ("backend/services/tax_invoice_service.py", "tax.ppn_rate", 'float(order.get("ppn_rate", 0)',
     "Bukan pengaturan: tarif PPN yang tersimpan pada dokumen pesanan (`order`), bukan `tax.ppn_rate`."),
    ("backend/services/tax_invoice_service.py", "tax.ppn_rate", 'order.get("effective_rate", order.get("ppn_rate", 0))',
     "Bukan pengaturan: tarif efektif/PPN yang tersimpan pada dokumen pesanan (`order`), bukan `tax.ppn_rate`."),
    ("backend/services/tax_invoice_service.py", "tax.ppn_rate", "fkt.get('ppn_rate', 0)",
     "Bukan pengaturan: tarif PPN tercetak dari faktur pajak tersimpan (`fkt`)."),
    ("backend/services/config_service.py", "tax.dpp_nilai_lain", '"dpp_nilai_lain": tax.get("dpp_nilai_lain", False)',
     "Bukan pengaturan: `tax` = hasil `compute_tax` (selalu memuat `dpp_nilai_lain`); cabang tanpa PPN mengisinya "
     "False."),
    ("backend/services/interco_service.py", "antar_entitas.pricing_mode", 'payload.get("pricing_mode") or ""',
     "Bukan pengaturan: isian permintaan (`payload`); bila kosong baris berikutnya membaca pengaturan lewat "
     "`_config`."),
    ("backend/services/interco_service.py", "antar_entitas.ppn_mode", 'payload.get("ppn_mode") or ""',
     "Bukan pengaturan: isian permintaan (`payload`); bila kosong baris berikutnya membaca pengaturan lewat "
     "`_config`."),
    ("backend/services/lot_service.py", "lot.enforcement_mode", 'payload.get("enforcement_mode") or ""',
     "Bukan pengaturan: isian permintaan simpan (`payload`); kosong = tidak diubah."),
    ("backend/services/contract_service.py", "makloon.contract_mode", 'payload.get("contract_mode") or ""',
     "Bukan pengaturan: isian permintaan simpan (`payload`); kosong = tidak diubah."),
    ("backend/routers/incentive_rates.py", "commission.incentive_unit", 'doc.get("incentive_unit") or ""',
     "Bukan pengaturan: isian tarif baru (`doc` = isi permintaan); kosong → baris berikutnya membaca pengaturan."),
]


def kosong(x):
    return x in (0, 0.0, "", None) or x == [] or x == {}


def kelas(e, temuan_baris):
    b = [t for t in temuan_baris if t["bentuk"].startswith("b")]
    a = [t for t in temuan_baris if t["bentuk"].startswith("a")]
    d = e.get("default")
    for t in b:
        lit = t["nilai"]
        boleh_kosong = (e["type"] in v_angka and (e.get("min") is None or e["min"] <= 0)) or (
            e["type"] == "text" and not (e.get("ref") and str(d or "").strip()))   # rujukan master: kosong ditolak
        tertulis = "dibaca sistem sebagai" in (e.get("help") or "")    # KF-T4 T5 — arti 0 tertulis di kartu
        if not kosong(lit) and boleh_kosong and tertulis and v.sama(lit, d):
            return ("sama_bawaan", f"Garis dasar KF-T8: `or {lit!r}` = bawaan registry dan arti 0 tertulis di "
                                   f"penjelasan kunci (\"Isi 0 dibaca sistem sebagai …\"); ganti dengan "
                                   f"`or config_registry.default_of(\"{e['key']}\")`, lalu hapus butir ini.")
        if not kosong(lit) and boleh_kosong:
            batas = f"batas bawah {e['min']}" if e["type"] in v_angka else "teks boleh kosong"
            return ("berdampak", f"Garis dasar KF-T8 (temuan, berdampak): `or {lit!r}` mengganti nilai kosong/0 yang "
                                 f"sah ({batas}) menjadi {lit!r}; bawaan registry {d!r}. Perbaiki di unit pemilik "
                                 f"kunci, lalu hapus butir ini.")
    for t in b:
        lit = t["nilai"]
        if not v.sama(lit, d):
            return ("hanya_bila_kosong", f"Garis dasar KF-T8: cadangan `or {lit!r}` ≠ bawaan {d!r}, hanya terpakai bila "
                                         f"nilai tersimpan kosong/None. Ganti dengan `config_registry.default_of`, lalu "
                                         f"hapus butir ini.")
    for t in a:
        if not v.sama(t["nilai"], d):
            return ("beda_bawaan", f"Garis dasar KF-T8 (temuan): cadangan {t['nilai']!r} ≠ bawaan {d!r} bila kunci "
                                   f"tidak ada di dokumen. Perbaiki di unit pemilik kunci, lalu hapus butir ini.")
    lit = (a or b)[0]["nilai"]
    return ("sama_bawaan", f"Garis dasar KF-T8: cadangan {lit!r} = bawaan registry; ganti dengan "
                           f"`config_registry.default_of(\"{e['key']}\")`, lalu hapus butir ini.")


v_angka = ("int", "duration", "pct", "money", "decimal")
h = v.analyse(ROOT, v.MODE_BAWAAN, allow=[])
reg = {e["key"]: e for e in h["entries"]}
per_baris = {}
for t in h["temuan"]:
    per_baris.setdefault((t["file"], t["key"], t["line"]), []).append(t)

butir, sudah = [], set()
for f, k, pot, alasan in BUKAN:
    assert any(t["file"] == f and t["key"] == k and pot in t["line_text"] for t in h["temuan"]), (f, k, pot)
    butir.append({"file": f, "key": k, "line_text": pot, "jenis": "bukan_pengaturan", "alasan": alasan})
for (f, k, no), ts in sorted(per_baris.items()):
    if any(f == b["file"] and k == b["key"] and b["line_text"] in ts[0]["line_text"] for b in butir[:len(BUKAN)]):
        continue
    pot = min((t["potongan"] for t in ts if t["potongan"]), key=len)
    jenis, alasan = kelas(reg[k], ts)
    sig = (f, k, pot)
    if sig in sudah:
        continue
    sudah.add(sig)
    butir.append({"file": f, "key": k, "line_text": pot, "jenis": jenis, "alasan": alasan})

entity = v.analyse(ROOT, v.MODE_ENTITY, allow=[])
for t in entity["temuan"]:
    butir.append({"file": t["file"], "key": t["key"], "line_text": t["potongan"], "mode": "entity", "jenis": "garis_dasar",
                  "alasan": "KF-T3 — sisa kelas KF-10 (ditemukan KF-T8): nilai PT dokumen belum diteruskan ke "
                            "`value_of`; perbaiki lalu hapus butir ini."})

print(json.dumps({
    "_catatan": ("KF-T8 — pengecualian penjaga `verify_config_fallback.py` (INV-CFG-09/10). Butir yang tidak lagi cocok "
                 "dengan kode = merah (pengecualian basi), jadi daftar ini hanya bisa berkurang. `jenis`: "
                 "bukan_pengaturan (temuan palsu: bukan pembacaan pengaturan) · berdampak / beda_bawaan (temuan nyata, "
                 "milik unit pemilik kunci) · hanya_bila_kosong / sama_bawaan (cadangan yang harus memakai "
                 "config_registry.default_of) · garis_dasar (INV-CFG-10). Garis dasar dibuat 14 Nov 2026."),
    "pengecualian": butir}, ensure_ascii=False, indent=1))
