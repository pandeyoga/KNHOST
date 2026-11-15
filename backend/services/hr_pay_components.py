"""PY-T1 (PY-01, PY-02) — komponen gaji per PT (`hr_pay_components`): isi awal, validasi, pembangun `components[]`.

Satu PT punya daftar komponennya sendiri (K-37). Tiap komponen menyebut kolom lama slip tempat nominalnya dijumlahkan
(`bucket`), sehingga jurnal, PDF, ekspor, dan rekap pajak yang membaca kolom lama tidak berubah angkanya.

Isi awal tiap PT (idempoten, saat server menyala dan saat daftar komponen PT itu pertama dibaca) menghasilkan slip
yang SAMA PERSIS dengan hitungan kolom lama: gaji pokok, tunjangan (satu baris per tunjangan di master karyawan), lembur,
komisi dari mesin komisi, tiga potongan BPJS karyawan, lima tanggungan BPJS perusahaan, PPh 21, THR (hanya proses
THR), dan RAPEL (PY-T2 — selisih gaji berlaku mundur, masukan proses reguler & susulan).

PY-T2 — nilai Gaji Pokok dan komponen tetap bulanan dibaca dari riwayat kompensasi bertanggal berlaku
(`segment_lines` atas potongan periode `hr_compensation_service.segments`), bukan dari master karyawan.

PY-T3 — tanda `in_bpjs_base`, `in_overtime_base`, `prorate` dipakai mesin (`basis`); potongan absensi bawaan
(`POT_ALPHA`, `POT_CUTI_TG`, `POT_TELAT`, `attendance_deductions`); cara hitung buatan pengguna `per_hari_hadir` dan
`persen_dasar` (`rate_components`); nilai komponen tetap per potongan periode lewat `nilai_tetap` (prorata masuk/keluar,
hari kerja).

Fungsi murni (tanpa database): `earning_components`, `statutory_components`, `derive_columns`, `components_match_columns`,
`basis`, `nilai_tetap`, `rate_components`, `attendance_deductions`.
Akses database: `ensure_defaults`, `ensure_defaults_all`, `list_components`, `create_component`, `update_component`.
"""
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from db import db
from core_utils import new_id, now_iso, safe_doc

KINDS = ("pendapatan", "potongan", "tanggungan_perusahaan")
CALCS = ("tetap_bulanan", "per_jam", "masukan", "undang_undang", "absensi", "per_hari_hadir", "persen_dasar")
# PY-T3 — cara hitung yang boleh dipilih untuk komponen buatan pengguna (nilai dari antrean masukan, `rate` × hari hadir,
# atau `rate` % × gaji pokok). `absensi` = potongan bawaan dari absensi & pengaturan (tidak bisa dibuat pengguna).
USER_CALCS = ("masukan", "per_hari_hadir", "persen_dasar")
RATE_CALCS = ("per_hari_hadir", "persen_dasar")
BUCKETS = ("base_salary", "allowances", "overtime", "commission", "other_earnings", "bpjs_emp", "bpjs_er", "pph21",
           "other_deductions")
STATUTORY_CODES = ("bpjs_kes_emp", "bpjs_jht_emp", "bpjs_jp_emp", "bpjs_kes_er", "bpjs_jht_er", "bpjs_jp_er",
                   "bpjs_jkk_er", "bpjs_jkm_er", "pph21")
RUN_TYPES = ("regular", "thr", "susulan")
RUN_TYPE_LABEL = {"regular": "Reguler", "thr": "THR", "susulan": "Susulan"}
KIND_LABEL = {"pendapatan": "Pendapatan", "potongan": "Potongan", "tanggungan_perusahaan": "Tanggungan perusahaan"}
CALC_LABEL = {"tetap_bulanan": "Tetap bulanan", "per_jam": "Per jam", "masukan": "Masukan",
              "undang_undang": "Menurut undang-undang", "absensi": "Dari absensi & pengaturan",
              "per_hari_hadir": "Per hari hadir", "persen_dasar": "Persen gaji pokok"}
# PY-T3 — potongan absensi bawaan (kode → (kunci pengaturan, label satuan)).
POTONGAN_ABSENSI = {"POT_ALPHA": "hari", "POT_CUTI_TG": "hari", "POT_TELAT": "menit"}

# Komponen pendapatan yang nilainya dari mesin komisi (bukan dari antrean masukan). Masukan manual untuk kode ini tetap
# boleh (ditambahkan ke kolom komisi).
ENGINE_CODES = ("KOMISI",)
# Kolom yang boleh dipilih komponen BUATAN PENGGUNA (komponen bawaan memakai kolom bawaannya). Komisi tidak termasuk:
# kolom komisi diakru per PT per bulan (`gl_service.post_incentive_accrual`), jadi hanya mesin komisi yang mengisinya.
USER_BUCKETS = {"pendapatan": ("allowances", "overtime", "other_earnings"), "potongan": ("other_deductions",)}
EARNING_BUCKETS = ("base_salary", "allowances", "overtime", "commission", "other_earnings")

# kunci rincian BPJS di slip lama (`bpjs_emp` / `bpjs_er`) per kode undang-undang
STATUTORY_SLOT = {
    "bpjs_kes_emp": ("bpjs_emp", "kesehatan"), "bpjs_jht_emp": ("bpjs_emp", "jht"), "bpjs_jp_emp": ("bpjs_emp", "jp"),
    "bpjs_kes_er": ("bpjs_er", "kesehatan"), "bpjs_jht_er": ("bpjs_er", "jht"), "bpjs_jp_er": ("bpjs_er", "jp"),
    "bpjs_jkk_er": ("bpjs_er", "jkk"), "bpjs_jkm_er": ("bpjs_er", "jkm"),
}


def _c(code: str, name: str, kind: str, calc: str, bucket: str, sort: int, *, taxable: bool,
       statutory_code: str = "", run_types: Tuple[str, ...] = ("regular",), bpjs_base: bool = False,
       ot_base: bool = False, prorate: bool = False, akun_beban_gaji: bool = False) -> Dict[str, Any]:
    out = {"code": code, "name": name, "kind": kind, "calc": calc, "bucket": bucket, "taxable": taxable,
           "in_bpjs_base": bpjs_base, "in_overtime_base": ot_base, "prorate": prorate,
           "statutory_code": statutory_code, "account_code": "", "allowed_run_types": list(run_types),
           "sort": sort, "is_active": True, "system": True}
    if akun_beban_gaji:   # PY-T3 — akun diisi saat isi awal dari `gl_service.ACC_BEBAN_GAJI` (P9, tidak ditulis di sini)
        out["_akun_beban_gaji"] = True
    return out


# Isi awal (K-37 — data per PT; pemilik menambah komponennya sendiri lewat layar Komponen & Masukan).
# `taxable` tanggungan Kesehatan/JKK/JKM = ya: premi yang dibayar pemberi kerja itu sudah masuk bruto pajak slip hari
# ini (HR-01, `compute_payslip`); ditandai di sini supaya bruto pajak = Σ komponen kena pajak tanpa mengubah angka.
DEFAULT_COMPONENTS: List[Dict[str, Any]] = [
    # PY-T3 — Gaji Pokok & Tunjangan diprorata (bila "Gaji karyawan masuk/keluar tengah bulan" dinyalakan) dan menjadi
    # dasar upah sehari potongan absensi.
    _c("GAJI_POKOK", "Gaji Pokok", "pendapatan", "tetap_bulanan", "base_salary", 10, taxable=True,
       bpjs_base=True, ot_base=True, prorate=True),
    _c("TUNJANGAN", "Tunjangan", "pendapatan", "tetap_bulanan", "allowances", 20, taxable=True, prorate=True),
    _c("LEMBUR", "Lembur", "pendapatan", "per_jam", "overtime", 30, taxable=True),
    _c("KOMISI", "Komisi / insentif penjualan", "pendapatan", "masukan", "commission", 40, taxable=True),
    _c("THR", "THR", "pendapatan", "masukan", "other_earnings", 50, taxable=True, run_types=("thr",)),
    # PY-T2 — selisih gaji yang berlaku mundur (masukan `pending` dari pengesahan riwayat kompensasi).
    _c("RAPEL", "Rapel", "pendapatan", "masukan", "other_earnings", 55, taxable=True,
       run_types=("regular", "susulan")),
    _c("BPJS_KES", "BPJS Kesehatan", "potongan", "undang_undang", "bpjs_emp", 110, taxable=False,
       statutory_code="bpjs_kes_emp"),
    _c("BPJS_JHT", "BPJS JHT", "potongan", "undang_undang", "bpjs_emp", 120, taxable=False,
       statutory_code="bpjs_jht_emp"),
    _c("BPJS_JP", "BPJS JP", "potongan", "undang_undang", "bpjs_emp", 130, taxable=False,
       statutory_code="bpjs_jp_emp"),
    # PY-T3 (K-38) — potongan absensi bawaan: nilai dari absensi & pengaturan PT (bawaan mati → tidak muncul). Bertanda
    # kena pajak = MENGURANGI bruto pajak; akun = beban gaji (dikredit → mengurangi beban, bukan menjadi hutang).
    _c("POT_ALPHA", "Potongan tidak hadir", "potongan", "absensi", "other_deductions", 140, taxable=True,
       akun_beban_gaji=True),
    _c("POT_CUTI_TG", "Potongan cuti tanpa gaji", "potongan", "absensi", "other_deductions", 145, taxable=True,
       akun_beban_gaji=True),
    _c("POT_TELAT", "Potongan terlambat", "potongan", "absensi", "other_deductions", 150, taxable=True,
       akun_beban_gaji=True),
    _c("PPH21", "PPh 21", "potongan", "undang_undang", "pph21", 190, taxable=False, statutory_code="pph21",
       run_types=("regular", "thr", "susulan")),
    _c("BPJS_KES_PT", "BPJS Kesehatan (perusahaan)", "tanggungan_perusahaan", "undang_undang", "bpjs_er", 210,
       taxable=True, statutory_code="bpjs_kes_er"),
    _c("BPJS_JHT_PT", "BPJS JHT (perusahaan)", "tanggungan_perusahaan", "undang_undang", "bpjs_er", 220,
       taxable=False, statutory_code="bpjs_jht_er"),
    _c("BPJS_JP_PT", "BPJS JP (perusahaan)", "tanggungan_perusahaan", "undang_undang", "bpjs_er", 230,
       taxable=False, statutory_code="bpjs_jp_er"),
    _c("BPJS_JKK", "BPJS JKK", "tanggungan_perusahaan", "undang_undang", "bpjs_er", 240, taxable=True,
       statutory_code="bpjs_jkk_er"),
    _c("BPJS_JKM", "BPJS JKM", "tanggungan_perusahaan", "undang_undang", "bpjs_er", 250, taxable=True,
       statutory_code="bpjs_jkm_er"),
]
DEFAULT_CODES = tuple(c["code"] for c in DEFAULT_COMPONENTS)
CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,29}$")


class ComponentConflict(ValueError):
    """Kode komponen kembar di PT yang sama (router → 409)."""


# ── fungsi murni ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _r2(v: Any) -> float:
    return round(float(v or 0), 2)


def by_code(comps: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {c["code"]: c for c in comps or []}


def allowed(comp: Optional[Dict[str, Any]], run_type: str) -> bool:
    """Komponen aktif dan dimuat jenis proses itu."""
    return bool(comp) and comp.get("is_active", True) is not False and \
        run_type in (comp.get("allowed_run_types") or ["regular"])


def _line(comp: Dict[str, Any], amount: float, label: str = "", **extra: Any) -> Dict[str, Any]:
    out = {"code": comp["code"], "name": comp.get("name") or comp["code"], "label": label or comp.get("name") or
           comp["code"], "kind": comp["kind"], "bucket": comp["bucket"], "amount": _r2(amount),
           "taxable": bool(comp.get("taxable"))}
    if comp.get("statutory_code"):
        out["statutory_code"] = comp["statutory_code"]
    if comp.get("account_code"):
        out["account_code"] = comp["account_code"]
    out.update({k: v for k, v in extra.items() if v not in (None, "")})
    return out


def allowance_rows(allowances: Any) -> List[Tuple[str, float]]:
    """Tunjangan master karyawan → [(nama, nominal)] (bentuk lama: angka tunggal → satu baris tanpa nama)."""
    if isinstance(allowances, (int, float)):
        return [("", float(allowances))] if float(allowances) else []
    rows: List[Tuple[str, float]] = []
    for a in allowances or [] if isinstance(allowances, list) else []:
        if isinstance(a, dict):
            amt = float(a.get("amount", 0) or 0)
            if amt:
                rows.append((str(a.get("name") or "").strip(), amt))
        elif isinstance(a, (int, float)) and float(a):
            rows.append(("", float(a)))
    return rows


def input_line(comp: Dict[str, Any], inp: Dict[str, Any]) -> Dict[str, Any]:
    """Satu masukan antrean → satu baris komponen (label = keterangan masukan)."""
    src = {"type": inp.get("source_type", ""), "key": inp.get("source_key", ""), "id": inp.get("id", "")}
    ref = inp.get("source_ref") or {}
    if isinstance(ref, dict) and ref.get("number"):
        src["number"] = ref["number"]
    return _line(comp, float(inp.get("amount") or 0), inp.get("label") or "",
                 basis_period=inp.get("basis_period") or "", source=src)


def nilai_tetap(seg: Dict[str, Any], comp: Dict[str, Any], value: Any, dim: int, potong: bool
                ) -> Tuple[float, Optional[Tuple[str, str, int]]]:
    """PY-T3 — nilai satu komponen tetap dalam satu potongan periode → (nominal, rentang label atau None).

    * potongan dipotong masa kerja (`masuk_keluar`, `hr_pay_rules.atur_potongan`) dan komponennya ber-`prorate` →
      nilai × n ÷ d menurut `hr.prorata_masuk_keluar` (pembulatan slip), label = rentang masa kerja;
    * potongan perubahan gaji ber-`rasio_ubah` (`hr.prorata_perubahan_gaji` = hari kerja) → nilai × hari kerja potongan ÷
      hari kerja bulan (rupiah penuh, sama dengan PY-T2);
    * selain itu PY-T2: sebulan penuh → nilai; dipotong → nilai × hari ÷ hari kalender (rupiah penuh)."""
    from services import hr_compensation_service as _hc
    from services import hr_pay_rules as _pr
    mk = seg.get("masuk_keluar")
    if mk and comp.get("prorate"):
        n, d = mk["rasio"]
        hari = max(0, int(mk["date_to"][8:10]) - int(mk["date_from"][8:10]) + 1)
        amt = _pr.bulatkan(float(value or 0) * n / d, _pr.RUPIAH if mk.get("bulat") == "rupiah" else None) if d else 0.0
        return amt, (mk["date_from"], mk["date_to"], hari)
    if not potong:
        return float(value or 0), None
    if seg.get("rasio_ubah"):
        n, d = seg["rasio_ubah"]
        amt = _pr.bulatkan(float(value or 0) * n / d, _pr.RUPIAH) if d else 0.0
    else:
        amt = _hc.prorate(value, seg["days"], dim)
    return amt, (seg["date_from"], seg["date_to"], seg["days"])


def segment_lines(comps: Dict[str, Dict[str, Any]], segments: Iterable[Dict[str, Any]], *,
                  run_type: str = "regular") -> List[Dict[str, Any]]:
    """PY-T2 — baris Gaji Pokok dan komponen tetap bulanan dari potongan periode (`hr_compensation_service.segments`).

    Satu potongan sebulan penuh → satu baris per komponen bernilai penuh (sama dengan slip sebelum PY-T2: "Gaji Pokok",
    "Tunjangan — Transport"). Lebih dari satu potongan (aturan `hari_kalender`) → tiap potongan baris sendiri berlabel
    "{nama} ({tgl awal}–{tgl akhir} {bulan})" bernilai nilai × hari potongan ÷ hari kalender bulan itu (rupiah penuh)."""
    from services import hr_compensation_service as _hc
    segs = list(segments or ())
    out: List[Dict[str, Any]] = []
    if run_type != "regular" or not segs:
        return out
    from services import hr_pay_rules as _pr
    dim = _hc.period_bounds(segs[0]["date_from"][:7])[2]
    potong = len(segs) > 1 or not segs[0].get("full")

    def baris(comp: Dict[str, Any], seg: Dict[str, Any], value: Any, label: str) -> Optional[Dict[str, Any]]:
        amt, rentang = nilai_tetap(seg, comp, value, dim, potong)
        if rentang is None:
            return _line(comp, amt, label)
        if seg.get("masuk_keluar") and comp.get("prorate") and not seg["masuk_keluar"]["rasio"][0]:
            return None   # potongan seluruhnya di luar masa kerja karyawan
        teks = _pr.rentang_label(rentang[0], rentang[1])
        return _line(comp, amt, f"{label or comp.get('name') or comp['code']} {teks}",
                     date_from=rentang[0], date_to=rentang[1], days=rentang[2])

    for seg in segs:
        gp = comps.get("GAJI_POKOK")
        if allowed(gp, run_type):
            ln = baris(gp, seg, seg.get("base_salary"), "")
            if ln is not None:
                out.append(ln)
        for fc in seg.get("fixed_components") or ():
            comp = comps.get(fc.get("component_code") or "TUNJANGAN")
            if not allowed(comp, run_type) or comp.get("calc") != "tetap_bulanan" or comp["code"] == "GAJI_POKOK":
                continue
            amt = float(fc.get("amount") or 0)
            if not amt:
                continue
            nama, ket = comp.get("name") or comp["code"], str(fc.get("label") or "").strip()
            ln = baris(comp, seg, amt, f"{nama} — {ket}" if ket and ket != nama else "")
            if ln is not None:
                out.append(ln)
    return out


def earning_components(comps: Dict[str, Dict[str, Any]], *, run_type: str = "regular", base: float = 0.0,
                       allowances: Any = None, overtime: float = 0.0, overtime_min: int = 0,
                       commission: float = 0.0, inputs: Iterable[Dict[str, Any]] = (),
                       segments: Optional[Iterable[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Baris pendapatan dan potongan masukan satu slip (tanpa BPJS dan PPh 21).

    Proses reguler: gaji pokok, tunjangan per nama, lembur, komisi mesin (masing-masing bila komponennya aktif untuk
    jenis proses itu) + masukan antrean. Proses THR/susulan: hanya masukan antrean. PY-T2 — `segments` (potongan
    periode dari riwayat kompensasi) menggantikan `base`/`allowances` untuk baris Gaji Pokok dan komponen tetap."""
    out: List[Dict[str, Any]] = []
    if run_type == "regular" and segments is not None:
        out.extend(segment_lines(comps, segments, run_type=run_type))
    elif run_type == "regular":
        gp = comps.get("GAJI_POKOK")
        if allowed(gp, run_type):
            out.append(_line(gp, base))
        tj = comps.get("TUNJANGAN")
        if allowed(tj, run_type):
            for nama, amt in allowance_rows(allowances):
                out.append(_line(tj, amt, f"{tj.get('name') or 'Tunjangan'} — {nama}" if nama else ""))
    # PY-T3 — lembur dan komisi untuk SEMUA proses reguler. Sejak PY-T2 proses reguler selalu berpotongan periode
    # (`segments`), sehingga baris ini — yang dulu hanya di cabang tanpa potongan — tidak pernah masuk slip (lembur dan
    # komisi tidak terbayar; ditemukan uji setara PY-T3).
    if run_type == "regular":
        lb = comps.get("LEMBUR")
        if allowed(lb, run_type) and (overtime or overtime_min):
            out.append(_line(lb, overtime, qty=round(overtime_min / 60.0, 2) if overtime_min else None))
        km = comps.get("KOMISI")
        if allowed(km, run_type) and commission:
            out.append(_line(km, commission))
    for inp in inputs or ():
        comp = comps.get(inp.get("component_code") or "")
        if comp and allowed(comp, run_type) and comp.get("calc") == "masukan":
            out.append(input_line(comp, inp))
    return out


def _angka(v: float) -> str:
    s = f"{float(v):,.2f}".rstrip("0").rstrip(".")
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def rate_components(comps: Dict[str, Dict[str, Any]], *, run_type: str = "regular", present_days: int = 0,
                    base_salary: float = 0.0) -> List[Dict[str, Any]]:
    """PY-T3 — komponen buatan pengguna berhitung `per_hari_hadir` (`rate` × hari hadir) dan `persen_dasar` (`rate` % ×
    gaji pokok slip ini, sesudah prorata). Hanya proses reguler; nominal 0 tidak dibuat barisnya."""
    out: List[Dict[str, Any]] = []
    if run_type != "regular":
        return out
    for comp in sorted(comps.values(), key=lambda c: (c.get("sort", 0), c["code"])):
        if comp.get("calc") not in RATE_CALCS or not allowed(comp, run_type):
            continue
        rate = float(comp.get("rate") or 0)
        if comp["calc"] == "per_hari_hadir":
            amt, label = rate * int(present_days or 0), f"{comp.get('name') or comp['code']} ({int(present_days or 0)} hari)"
        else:
            amt, label = rate / 100.0 * float(base_salary or 0), f"{comp.get('name') or comp['code']} ({_angka(rate)} %)"
        if amt:
            out.append(_line(comp, amt, label, qty=present_days if comp["calc"] == "per_hari_hadir" else None,
                             rate=rate))
    return out


def attendance_deductions(comps: Dict[str, Dict[str, Any]], *, run_type: str = "regular",
                          kehadiran: Optional[Dict[str, Any]] = None, daily: float = 0.0, per_minute: float = 0.0,
                          alpha_on: bool = False, unpaid_on: bool = False) -> List[Dict[str, Any]]:
    """PY-T3 (K-38) — potongan absensi (komponen bawaan POT_ALPHA, POT_CUTI_TG, POT_TELAT) dari ringkasan kehadiran
    (`hr_pay_rules.hitung_kehadiran`): tidak hadir & cuti tanpa gaji = upah sehari × hari; terlambat = menit × tarif."""
    out: List[Dict[str, Any]] = []
    k = kehadiran or {}
    if run_type != "regular" or not k:
        return out
    for code, on, n, nilai in (("POT_ALPHA", alpha_on, int(k.get("alpha_days") or 0), daily),
                               ("POT_CUTI_TG", unpaid_on, int(k.get("unpaid_days") or 0), daily),
                               ("POT_TELAT", per_minute > 0, int(k.get("late_min") or 0), per_minute)):
        comp = comps.get(code)
        if not on or not n or not allowed(comp, run_type):
            continue
        out.append(_line(comp, nilai * n, f"{comp.get('name') or code} ({n} {POTONGAN_ABSENSI[code]})", qty=n))
    return out


def statutory_components(comps: Dict[str, Dict[str, Any]], *, run_type: str = "regular",
                         bpjs_emp: Optional[Dict[str, float]] = None, bpjs_er: Optional[Dict[str, float]] = None,
                         bpjs_rates: Optional[Dict[str, float]] = None, bpjs_on: Optional[Dict[str, bool]] = None,
                         pph21: Optional[float] = None, pph21_rate_pct: float = 0.0,
                         pph21_method: str = "ter") -> List[Dict[str, Any]]:
    """Baris BPJS (hanya program yang aktif untuk karyawan itu) dan PPh 21 (selalu satu baris bila komponennya aktif).

    `bpjs_rates` = persen per kode undang-undang (1.0 = 1 %); `bpjs_on` = {"kes": bool, "tk": bool}."""
    out: List[Dict[str, Any]] = []
    on = bpjs_on or {}
    rates = bpjs_rates or {}
    nilai = {"bpjs_emp": bpjs_emp or {}, "bpjs_er": bpjs_er or {}}
    for comp in sorted(comps.values(), key=lambda c: (c.get("sort", 0), c["code"])):
        sc = comp.get("statutory_code") or ""
        if sc not in STATUTORY_SLOT or not allowed(comp, run_type):
            continue
        prog = "kes" if sc.startswith("bpjs_kes") else "tk"
        if not on.get(prog):
            continue
        slot, sub = STATUTORY_SLOT[sc]
        out.append(_line(comp, float(nilai[slot].get(sub, 0) or 0), rate=rates.get(sc)))
    pc = next((c for c in comps.values() if c.get("statutory_code") == "pph21"), None)
    if pph21 is not None and allowed(pc, run_type):
        out.append(_line(pc, pph21, rate=round(pph21_rate_pct, 4) if pph21_method == "ter" else None,
                         method=pph21_method))
    return out


def sort_components(lines: List[Dict[str, Any]], comps: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    order = {k: i for i, k in enumerate(KINDS)}
    return sorted(lines, key=lambda ln: (order.get(ln["kind"], 9), (comps.get(ln["code"]) or {}).get("sort", 500)))


def derive_columns(components: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Kolom lama slip dari `components[]`: tiap kolom = Σ `amount` komponen ber-`bucket` itu.

    `salary_earnings = base_salary + allowances + overtime + other_earnings`; `gross = salary_earnings + commission`;
    `net = gross − bpjs_emp_total − pph21 − other_deductions`; `tax_gross = Σ amount komponen kena pajak` (pendapatan dan
    tanggungan perusahaan) − Σ potongan bertanda kena pajak (PY-T3: potongan tidak hadir, cuti tanpa gaji, terlambat)."""
    b = {k: 0.0 for k in BUCKETS}
    emp = {"kesehatan": 0.0, "jht": 0.0, "jp": 0.0}
    er = {"kesehatan": 0.0, "jht": 0.0, "jp": 0.0, "jkk": 0.0, "jkm": 0.0}
    tax_gross = 0.0
    for ln in components or ():
        amt = float(ln.get("amount") or 0)
        b[ln.get("bucket") or "other_earnings"] = b.get(ln.get("bucket") or "other_earnings", 0.0) + amt
        slot = STATUTORY_SLOT.get(ln.get("statutory_code") or "")
        if slot:
            (emp if slot[0] == "bpjs_emp" else er)[slot[1]] += amt
        if ln.get("taxable"):
            # PY-T3 — potongan bertanda kena pajak (potongan absensi) MENGURANGI bruto pajak; potongan lain (BPJS,
            # PPh 21, potongan buatan pengguna) tidak bertanda, jadi tidak ikut.
            tax_gross += -amt if ln.get("kind") == "potongan" else amt
    salary = _r2(b["base_salary"] + b["allowances"] + b["overtime"] + b["other_earnings"])
    gross = _r2(salary + b["commission"])
    emp_total, pph, other_ded = _r2(b["bpjs_emp"]), _r2(b["pph21"]), _r2(b["other_deductions"])
    return {"base_salary": _r2(b["base_salary"]), "allowances": _r2(b["allowances"]), "overtime": _r2(b["overtime"]),
            "commission": _r2(b["commission"]), "other_earnings": _r2(b["other_earnings"]),
            "salary_earnings": salary, "gross": gross, "tax_gross": _r2(tax_gross),
            "bpjs_emp": {k: _r2(v) for k, v in emp.items()}, "bpjs_er": {k: _r2(v) for k, v in er.items()},
            "bpjs_emp_total": emp_total, "bpjs_er_total": _r2(b["bpjs_er"]), "pph21": pph,
            "other_deductions": other_ded, "net": _r2(gross - emp_total - pph - other_ded)}


def basis(comps: Dict[str, Dict[str, Any]], lines: Iterable[Dict[str, Any]], flag: str) -> float:
    """PY-T3 — Σ nominal baris PENDAPATAN yang komponennya bertanda `flag` (`in_bpjs_base` = dasar BPJS,
    `in_overtime_base` = dasar upah lembur, `prorate` = dasar potongan harian). Lembur dan komisi tidak pernah ikut."""
    tot = 0.0
    for ln in lines or ():
        comp = comps.get(ln.get("code") or "") or {}
        if ln.get("kind") == "pendapatan" and ln.get("bucket") not in ("overtime", "commission") and comp.get(flag):
            tot += float(ln.get("amount") or 0)
    return tot


COLUMN_KEYS = ("base_salary", "allowances", "overtime", "commission", "salary_earnings", "gross", "tax_gross",
               "bpjs_emp_total", "bpjs_er_total", "pph21", "net")


def components_match_columns(slip: Dict[str, Any]) -> List[str]:
    """Kolom lama yang TIDAK sama dengan turunan `components[]` slip (selisih > 0,5 sen). [] = cocok semua."""
    if not slip.get("components"):
        return []
    d = derive_columns(slip["components"])
    beda = []
    for k in COLUMN_KEYS + ("other_earnings", "other_deductions"):
        if k in ("other_earnings", "other_deductions") and k not in slip:
            if abs(d[k]) > 0.005:
                beda.append(k)
            continue
        if abs(float(slip.get(k) or 0) - d[k]) > 0.005:
            beda.append(k)
    return beda


# ── database ─────────────────────────────────────────────────────────────────────────────────────────────────────────
async def ensure_defaults(entity_id: str) -> int:
    """Isi awal komponen satu PT (idempoten; komponen yang sudah ada TIDAK diubah). → jumlah komponen baru."""
    if not entity_id or entity_id == "all":
        return 0
    have = {c["code"] async for c in db.hr_pay_components.find({"entity_id": entity_id}, {"_id": 0, "code": 1})}
    baru = 0
    for d in DEFAULT_COMPONENTS:
        if d["code"] in have:
            continue
        doc = {**d, "allowed_run_types": list(d["allowed_run_types"]), "entity_id": entity_id}
        if doc.pop("_akun_beban_gaji", False):   # PY-T3 — potongan absensi mengkredit beban gaji (P9: konstanta GL)
            from services.gl_service import ACC_BEBAN_GAJI
            doc["account_code"] = ACC_BEBAN_GAJI
        res = await db.hr_pay_components.update_one(
            {"entity_id": entity_id, "code": d["code"]},
            {"$setOnInsert": {**doc, "id": new_id("pcomp"), "created_at": now_iso(), "updated_at": now_iso(),
                              "created_by": "system"}}, upsert=True)
        baru += 1 if getattr(res, "upserted_id", None) is not None else 0
    return baru


async def ensure_defaults_all() -> int:
    """Isi awal untuk semua PT (dipanggil saat server menyala)."""
    total = 0
    async for e in db.business_entities.find({}, {"_id": 0, "id": 1}):
        if e.get("id"):
            total += await ensure_defaults(e["id"])
    return total


async def list_components(entity_id: str, *, active_only: bool = False) -> List[Dict[str, Any]]:
    await ensure_defaults(entity_id)
    q: Dict[str, Any] = {"entity_id": entity_id}
    if active_only:
        q["is_active"] = {"$ne": False}
    rows = await db.hr_pay_components.find(q, {"_id": 0}).sort([("sort", 1), ("code", 1)]).to_list(500)
    return [safe_doc(r) for r in rows]


async def components_for(entity_id: str) -> Dict[str, Dict[str, Any]]:
    """Peta kode → komponen PT itu (isi awal dijamin)."""
    return by_code(await list_components(entity_id))


async def _check_account(entity_id: str, code: str) -> str:
    from services import gl_service as gl
    from services import gl_mapping_service as _glm
    code = (code or "").strip()
    acc = (await gl.effective_accounts([code], entity_id)).get(code) if code else None
    if not acc or acc.get("is_active") is False or acc.get("is_postable") is False:
        raise ValueError(f"Akun {code or '(kosong)'} tidak ada atau tidak aktif di bagan akun PT ini.")
    if code in await _glm.control_accounts(entity_id):   # 02 §1 P10 — penggajian bukan pemilik buku pembantu itu
        raise ValueError(f"Akun {code} adalah akun kontrol buku pembantu dan tidak bisa dipakai komponen gaji.")
    return code


def _run_types(v: Any) -> List[str]:
    rts = [str(x) for x in (v or []) if str(x) in RUN_TYPES]
    if not rts:
        raise ValueError("Pilih minimal satu jenis proses gaji untuk komponen ini.")
    return sorted(set(rts), key=RUN_TYPES.index)


async def create_component(entity_id: str, data: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Komponen baru buatan pengguna. Saat ini hanya cara hitung `masukan` (nilai dari antrean masukan): komponen tetap
    per karyawan menyusul (PY-T2), per jam dan persen dasar menyusul (PY-T3) — supaya tidak ada komponen tanpa nilai."""
    await ensure_defaults(entity_id)
    code = str(data.get("code") or "").strip().upper()
    if not CODE_RE.match(code):
        raise ValueError("Kode komponen 2–30 huruf besar, angka, atau garis bawah, diawali huruf (mis. BONUS).")
    name = str(data.get("name") or "").strip()
    if not name:
        raise ValueError("Nama komponen wajib diisi.")
    kind = str(data.get("kind") or "")
    if kind not in USER_BUCKETS:
        raise ValueError("Jenis komponen baru harus pendapatan atau potongan.")
    calc = str(data.get("calc") or "masukan")
    if calc not in USER_CALCS:
        raise ValueError("Cara hitung komponen baru harus masukan, per hari hadir, atau persen gaji pokok.")
    rate = _rate(calc, data.get("rate"))
    bucket = str(data.get("bucket") or USER_BUCKETS[kind][-1])
    if bucket not in USER_BUCKETS[kind]:
        raise ValueError("Kolom slip tidak cocok dengan jenis komponen.")
    account = str(data.get("account_code") or "").strip()
    if kind == "potongan" and not account:
        raise ValueError("Komponen potongan wajib punya akun.")
    if account:
        account = await _check_account(entity_id, account)
    doc = {"id": new_id("pcomp"), "entity_id": entity_id, "code": code, "name": name, "kind": kind, "calc": calc,
           "bucket": bucket, "taxable": bool(data.get("taxable", kind == "pendapatan")) and kind == "pendapatan",
           "in_bpjs_base": bool(data.get("in_bpjs_base")), "in_overtime_base": bool(data.get("in_overtime_base")),
           "prorate": bool(data.get("prorate")), "statutory_code": "", "account_code": account,
           # PY-T3 — per hari hadir / persen gaji pokok hanya bernilai di proses reguler (absensi & gaji pokok bulan itu).
           "allowed_run_types": ["regular"] if calc in RATE_CALCS else _run_types(
               data.get("allowed_run_types") or ["regular", "susulan"]),
           "rate": rate, "sort": int(data.get("sort") or 300), "is_active": data.get("is_active", True) is not False,
           "system": False, "created_at": now_iso(), "updated_at": now_iso(),
           "created_by": actor.get("name", "system"), "created_by_id": actor.get("id", "")}
    from pymongo.errors import DuplicateKeyError
    if await db.hr_pay_components.find_one({"entity_id": entity_id, "code": code}, {"_id": 1}):
        raise ComponentConflict("Kode komponen sudah dipakai di PT ini.")
    try:
        await db.hr_pay_components.insert_one(dict(doc))
    except DuplicateKeyError as exc:   # D7 — indeks unik (entity_id, code)
        raise ComponentConflict("Kode komponen sudah dipakai di PT ini.") from exc
    return doc


SYSTEM_LOCKED = ("kind", "calc", "bucket", "statutory_code", "allowed_run_types", "is_active", "code")


def _rate(calc: str, v: Any) -> float:
    """PY-T3 — nilai komponen per hari hadir (rupiah > 0) / persen gaji pokok (0 < persen ≤ 100); cara lain → 0."""
    if calc not in RATE_CALCS:
        return 0.0
    try:
        x = float(v)
    except (TypeError, ValueError) as exc:
        raise ValueError("Isi nilai komponen (rupiah per hari hadir atau persen gaji pokok).") from exc
    if x <= 0 or (calc == "persen_dasar" and x > 100):
        raise ValueError("Nilai per hari hadir harus lebih dari 0; persen gaji pokok 0–100.")
    return round(x, 4)


async def update_component(comp_id: str, entity_id: str, data: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    cur = await db.hr_pay_components.find_one({"id": comp_id, "entity_id": entity_id}, {"_id": 0})
    if not cur:
        raise LookupError("Komponen gaji tidak ditemukan di PT ini.")
    patch: Dict[str, Any] = {}
    if cur.get("system"):
        for k in SYSTEM_LOCKED:
            if k in data and data[k] != cur.get(k) and not (k == "allowed_run_types" and
                                                            sorted(data[k] or []) == sorted(cur.get(k) or [])):
                raise ValueError("Komponen bawaan tidak bisa diubah jenisnya.")
    else:
        if "code" in data and str(data["code"] or "").strip().upper() != cur["code"]:
            raise ValueError("Kode komponen tidak bisa diubah; buat komponen baru bila perlu.")
        if "kind" in data and data["kind"] != cur["kind"]:
            raise ValueError("Jenis komponen tidak bisa diubah; buat komponen baru bila perlu.")
        if "bucket" in data and data["bucket"] != cur["bucket"]:
            if data["bucket"] not in USER_BUCKETS.get(cur["kind"], ()):
                raise ValueError("Kolom slip tidak cocok dengan jenis komponen.")
            patch["bucket"] = data["bucket"]
        if "allowed_run_types" in data:
            patch["allowed_run_types"] = _run_types(data["allowed_run_types"])
        if "is_active" in data:
            patch["is_active"] = bool(data["is_active"])
        if "taxable" in data:
            patch["taxable"] = bool(data["taxable"]) and cur["kind"] == "pendapatan"
        if "rate" in data and cur.get("calc") in RATE_CALCS:
            patch["rate"] = _rate(cur["calc"], data["rate"])
    if "name" in data:
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("Nama komponen wajib diisi.")
        patch["name"] = name
    if "sort" in data:
        patch["sort"] = int(data.get("sort") or 0)
    for k in ("in_bpjs_base", "in_overtime_base", "prorate"):   # PY-T3 — dibaca penghitung slip (`basis`)
        if k in data:
            patch[k] = bool(data[k])
    if "account_code" in data:
        account = str(data.get("account_code") or "").strip()
        if cur["kind"] == "potongan" and cur.get("calc") != "undang_undang" and not account:
            raise ValueError("Komponen potongan wajib punya akun.")
        if account and (cur.get("calc") == "undang_undang" or cur.get("bucket") == "commission"):
            raise ValueError("Komponen ini memakai akun bawaannya, jadi akunnya tidak bisa diganti.")
        patch["account_code"] = await _check_account(entity_id, account) if account else ""
    if not patch:
        return safe_doc(cur)
    patch.update({"updated_at": now_iso(), "updated_by": actor.get("name", "system"),
                  "updated_by_id": actor.get("id", "")})
    await db.hr_pay_components.update_one({"id": comp_id, "entity_id": entity_id}, {"$set": patch})
    return safe_doc(await db.hr_pay_components.find_one({"id": comp_id}, {"_id": 0}))
