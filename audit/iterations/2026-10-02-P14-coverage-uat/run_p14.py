"""P14 — jalankan ulang seluruh regression fase P01–P14 pada HEAD kerja lalu petakan ke coverage.json.

Usage: cd /app/backend && python ../audit/iterations/2026-10-02-P14-coverage-uat/run_p14.py [--no-run]
--no-run: pakai keluaran runs/*.txt yang sudah ada (mis. setelah menambah uat_results.json).
Status: tested_pass hanya bila kasus dieksekusi penuh oleh invariant yang lulus; cakupan sebagian = partial.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT = HERE.parents[1]
RUNS = HERE / "runs"
BASE_SHA = "8fcb9dc9588cf14d9eeb534be38168a1c50f23d3"
REL = f"iterations/{HERE.name}"

R = {  # kunci → skrip repro (relatif terhadap audit/iterations)
    "p01_dev": "2026-09-30-P01-device-credentials/repro_rf12_rf13.py",
    "p01_s1": "2026-09-30-P01-scope-batch1/repro_p01_scope.py",
    "p01_s2": "2026-09-30-P01-scope-batch2/repro_p01_batch2.py",
    "p01_cx10": "2026-10-01-P01-ix06-cx10/repro_cx10.py",
    "p01_ix06": "2026-10-01-P01-ix06-cx10/repro_ix06.py",
    "p02": "2026-10-01-P02-core-roll/repro_p02.py",
    "p06_qc": "2026-10-01-P06-qc-sampling/repro_pg01_ix15.py",
    "p02_wm02": "2026-10-02-P02-wm02-reservation/repro_wm02.py",
    "p03": "2026-10-02-P03-durable-posting/repro_p03.py",
    "p06": "2026-10-02-P06-receiving/repro_p06.py",
    "p11": "2026-10-02-P11-mutasi-konversi/repro_p11.py",
    "p12": "2026-10-02-P12-payroll-hr-marketing/repro_p12.py",
    "p13": "2026-10-02-P13-audit-secret-label/repro_p13.py",
    "p04": "2026-10-03-P04-costing/repro_p04.py",
    "fu1": "2026-10-03-WM02-identity-CX05-panel/repro_followup.py",
    "fu2": "2026-10-04-label-reimburse-poline-badge/repro_followup2.py",
    "p05": "2026-10-05-P05-coa-reports-close/repro_p05.py",
    "fu3": "2026-10-05-P05-coa-reports-close/repro_followup3.py",
    "p07": "2026-10-06-P07-dispatch-identity-reversal/repro_p07.py",
    "p07b": "2026-10-07-P07-fulfillment-saga-loading/repro_p07b.py",
    "p08": "2026-10-08-P08-tag-printer-verify/repro_p08.py",
    "p09": "2026-10-08-P09-gate-contract/repro_p09.py",
    "p10": "2026-10-08-P10-opname-financial/repro_p10.py",
    "p14": f"{HERE.name}/repro_p14_history.py",
    "p14b": f"{HERE.name}/repro_p14b_cases.py",
}

P, T = "partial", "tested_pass"
# kasus → (skrip, status bila semua lulus, catatan batas cakupan)
MAP = {
    "AUTH-01": (["p14"], P, "Login valid/invalid & revoke logout diuji; expiry TTL belum diuji dengan time-travel."),
    "AUTH-02": (["p01_s1", "p01_s2"], P, "IDOR lintas entitas/owner pada endpoint temuan P01; belum sweep semua endpoint."),
    "MASTER-02": (["p01_ix06", "p01_s1"], P, "Payroll & Finance settings A tidak mengubah B (IX-06/IX-07); master lain belum."),
    "MASTER-03": (["p05"], P, "Override COA entitas (FN-05/FN-06); layer clear untuk config lain belum."),
    "MASTER-04": (["p02"], P, "Fallback UOM tak dikenal (GN-13/IX-13); alias master lain belum."),
    "GRN-01": (["p06", "p03"], P, "Receiving & jurnal GRN durable (IX-14); karantina end-to-end UI belum."),
    "GRN-05": (["p03"], P, "Jurnal GRN gagal tidak menutup GRN (IX-14); periode tertutup penuh belum."),
    "QC-01": (["p06_qc"], T, "IX-15 keputusan sebagian menyisakan task."),
    "QC-02": (["p11", "p06"], T, "IX-11 produksi menolak roll hold; AX-08 putaway hold."),
    "QC-03": (["p06"], T, "IX-09 reopen inspeksi membatalkan indikator retur."),
    "QC-04": (["p04", "p11"], P, "Nilai retur beli & AP (IX-16, GN-07); UI belum."),
    "PRET-01": (["p04"], P, "Kontrak net/gross non-PPN (IX-16)."),
    "PRET-02": (["p03"], P, "Retur tidak approved sebelum jurnal (IX-17); retry penuh belum."),
    "PRET-03": (["p04"], P, "Retur PPN AP credit (IX-16); cash refund dokumen belum."),
    "PRET-05": (["p03"], P, "Jurnal ditolak → retur tetap draft (IX-17)."),
    "PRET-06": (["p11"], P, "Read-set & partial return (GN-07); concurrent approve belum."),
    "PROD-01": (["p11"], T, "GN-06 WO memakai BOM rilis, bukan terbaru."),
    "PROD-02": (["p11"], P, "Claim WO (GN-06); kegagalan GL lalu retry belum diinjeksi."),
    "PROD-03": (["p11"], T, "IX-11 roll held tidak dikonsumsi."),
    "PROD-05": (["p11"], P, "Makloon receive terikat versi step (CX-13); biaya & retur makloon belum."),
    "INV-01": (["p02"], T, "WM-01 split atomik/normalisasi mempertahankan total."),
    "INV-02": (["p02", "p06"], P, "AX-05/WM-04/WM-09 lokasi transfer; antargudang UI belum."),
    "INV-03": (["p10"], P, "WM-07/WM-08 expected per bin & approval; cutoff/recount belum."),
    "INV-04": (["p11"], P, "GN-08 konversi permintaan internal tidak ganda; rekonsiliasi dua buku belum."),
    "INV-05": (["p02", "p01_s2"], T, "GN-13 rebuild tidak menulis snapshot lama; AX-04 owner filter."),
    "RFID-01": (["p08"], T, "RF-01 EPC kanonik ZPL = DB = raw reader (simulasi software)."),
    "RFID-02": (["p09"], T, "RF-02 gate OUT memvalidasi dokumen/status/roll/tujuan (software)."),
    "RFID-03": (["p07"], T, "RF-05 loading tidak clean bila roll wajib belum bertag."),
    "RFID-04": (["p08"], T, "IX-12 attach gagal tidak meninggalkan tag aktif."),
    "RFID-05": (["p09"], P, "RF-16 replay/duplicate/passage; offline reconnect perangkat nyata belum."),
    "SALE-01": (["p07", "p07b"], P, "Pick→dispatch identitas & saga; invoice dataset acuan belum."),
    "SALE-03": (["p02_wm02", "p07b"], P, "WM-02 reservasi parsial, CX-12 special order; cancel reservasi belum."),
    "SALE-04": (["p03", "p01_s2"], T, "CX-01 batas nominal/saldo, CX-02 lintas owner/entitas."),
    "SALE-05": (["p07"], P, "CX-11 harga baris retur; pajak & receipt asli belum."),
    "APAR-01": (["p05", "p04"], P, "FN-02 3-way match overbilling; pembayaran & reversal AP belum."),
    "APAR-02": (["p03"], P, "CX-08 reschedule & FN-10 AR durable."),
    "APAR-03": (["p03"], T, "CX-06 arah/rekening, CX-07 alokasi ganda."),
    "APAR-04": (["p03", "fu2"], T, "CX-04 retry payout, CX-05 settlement ulang."),
    "APAR-05": (["p03"], P, "FN-10/CX-03/FN-15 recovery state; seluruh sumber belum."),
    "GL-01": (["p03", "p05"], P, "FN-08 opening rekening & FN-15 invariant jurnal; TB semua sumber belum."),
    "GL-02": (["p05"], T, "FN-09 void jurnal di periode tertutup ditolak."),
    "GL-03": (["p05"], T, "IX-08 approval basi & FN-13 close ganda."),
    "GL-04": (["p01_s1"], T, "IX-10 unlock lintas entitas."),
    "GL-05": (["p05"], P, "CX-09 eliminasi sesuai entitas; multi-periode belum."),
    "HR-01": (["p12"], P, "HR-03/IX-01 saldo & lintas tahun; IX-02 duplikat HR-03."),
    "HR-02": (["p12"], T, "IX-03 shift malam, IX-04 lembur belum disetujui, HR-02 multiplier."),
    "HR-03": (["p12"], P, "Payroll periode; posting GL & pembayaran end-to-end belum."),
    "HR-04": (["p12"], P, "HR-01 PPh21 masa terakhir (software); tabel pajak/BPJS butuh validasi legal."),
    "HR-05": (["p01_ix06", "p12"], P, "IX-06 settings lintas entitas; void/retry payroll belum."),
    "COMM-01": (["p01_s2"], P, "GN-09 entitas CRM; merge duplikat belum."),
    "COMM-02": (["p12"], T, "MK-01 metrik parsial mempertahankan nilai."),
    "DOC-01": (["p01_cx10", "p01_s1"], T, "CX-10 e-sign terikat versi, IX-05 metadata lintas entitas."),
    "DOC-03": (["p05"], P, "IX-08 stale decision unlock; approval berjenjang lain belum."),
    "DOC-04": (["p01_s2"], P, "GN-16 laporan AI pribadi; scheduled report belum."),
    "DOC-05": (["p01_s2"], P, "GN-16 digest penerima sah."),
    "OPS-01": (["p14"], P, "Bootstrap & indeks diverifikasi di preview; deployment produksi belum."),
    "OPS-02": (["p03"], P, "Outbox/durable posting; restart scheduler belum diinjeksi."),
    "OPS-04": (["p07b", "p03"], P, "GN-11 saga release; crash tiap tahap belum."),
    "PRET-04": (["p14b"], T, "RMA ditolak supplier → goods_back: roll available utuh, tanpa nota debit/jurnal, goods-back ulang ditolak."),
    "SALE-02": (["p14b"], T, "Gap produk: router POS hanya rekomendasi (best-sellers/FBT/substitutes); belum ada shift close, void, split tender."),
    "DESIGN-01": (["p14b"], P, "Request→assign→desain→ajukan→revisi→ajukan ulang→ACC (status permintaan ikut Studio); lanjutan ke produksi belum."),
    "DESIGN-03": (["p14b"], P, "Cancel wajib alasan, cancel ulang ditolak, permintaan batal tak melahirkan desain; reopen desain belum."),
    "DESIGN-04": (["p14b"], P, "Desainer B ditolak buka/unggah ke tugas A dan daftar B bersih; pemindahan penugasan belum."),
    "AUTH-03": (["p14b"], T, "Role custom customer.view: view 200, update 403, modul lain 403."),
    "AUTH-05": (["p14b"], T, "Pencabutan izin langsung berlaku; PUT /permissions mengganti seluruh matriks tanpa versi."),
}
BLOCKED = {
    "RFID-06": "Butuh reader/printer/PLC fisik + firmware; simulasi software tidak menggantikan commissioning.",
    "OPS-05": "Backup/restore butuh lingkungan & kebijakan pemilik (target DB non-preview).",
}
NEW_CASES = [
    {"id": "AUDIT-01", "group": "Jejak audit", "scenario": "Riwayat perubahan akun GL & pelanggan: nilai lama→baru, pelaku, sumber, sidik isi, izin"},
    {"id": "AUDIT-02", "group": "Jejak audit", "scenario": "Perubahan gaji/PII tercatat sebagai field berubah dengan nilai disamarkan"},
    {"id": "AUDIT-03", "group": "Jejak audit", "scenario": "Pemindai secret memblokir di pre-commit dan CI"},
]
NEW_MAP = {"AUDIT-01": (["p14"], T, "API + tamper detection; UI tab diuji UAT."),
           "AUDIT-02": (["p14"], T, "base_salary disamarkan, tanpa perubahan tidak dicatat."),
           "AUDIT-03": (["p14"], P, "Skrip & konfigurasi ada; eksekusi GitHub Actions nyata belum diamati.")}


def _public_api():
    env = (AUDIT.parent / "frontend/.env").read_text()
    url = re.search(r"^REACT_APP_BACKEND_URL=\"?([^\"\n]+)", env, re.M).group(1)
    return url.rstrip("/") + "/api"


# Harness cookie-only (httpx) tidak mengirim cookie Secure lewat http://localhost → jalankan via HTTPS publik.
API_OVERRIDE = {"p01_s1": _public_api}


def run_all(only=None):
    RUNS.mkdir(exist_ok=True)
    env = {**os.environ, "KN_API": "http://localhost:8001/api", "MONGO_URL": os.environ.get("MONGO_URL", "mongodb://localhost:27017"),
           "DB_NAME": os.environ.get("DB_NAME", "test_database")}
    for key, rel in R.items():
        if only and key not in only:
            continue
        env["KN_API"] = API_OVERRIDE[key]() if key in API_OVERRIDE else "http://localhost:8001/api"
        t0 = time.time()
        try:
            p = subprocess.run([sys.executable, str(AUDIT / "iterations" / rel), str(AUDIT.parent)], cwd=AUDIT.parent / "backend",
                               env=env, capture_output=True, text=True, timeout=900)
            out = p.stdout + ("\n[stderr]\n" + p.stderr[-3000:] if p.returncode else "")
        except subprocess.TimeoutExpired:
            out = "TIMEOUT 900s"
        (RUNS / f"{key}.txt").write_text(f"# {rel} ({time.time() - t0:.0f}s)\n{out}")
        print(key, summarize(key))


# Harness lama yang memanggil kontrak sebelum perubahan fase berikutnya: invariant diganti versi teradaptasi di p14.
DRIFT = {"p01_s2": ["multi-entity count session is scannable by its creator scope"]}


def summarize(key):
    f = RUNS / f"{key}.txt"
    if not f.exists():
        return {"pass": 0, "fail": 0, "ok": False, "missing": True}
    txt = f.read_text()
    m = re.findall(r"pass=(\d+)\s+fail=(\d+)", txt)
    if m:
        ps, fl = map(int, m[-1])
    else:
        ps = len(re.findall(r"^\s*(PASS|OK)\b", txt, re.M))
        fl = len(re.findall(r"^\s*(FAIL)\b", txt, re.M))
    failed = re.findall(r'"invariant": "([^"]+)",\s*"pass": false', txt)
    drift = [x for x in failed if x in DRIFT.get(key, [])]
    out = {"pass": ps, "fail": fl, "ok": ps > 0 and fl - len(drift) == 0}
    if drift:
        out["drift_excluded"] = drift
    return out


def case_ok(key, cid, matrix):
    """Bila keluaran skrip memuat invariant ber-id kasus ini, nilai hanya invariant itu; selain itu status skrip."""
    txt = (RUNS / f"{key}.txt").read_text() if (RUNS / f"{key}.txt").exists() else ""
    own = re.findall(r'"id": "' + re.escape(cid) + r'",\s*"invariant": "[^"]+",\s*"pass": (true|false)', txt)
    return all(x == "true" for x in own) if own else matrix[key]["ok"]


def main():
    only = [a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")]
    if "--no-run" not in sys.argv:
        run_all(only[0] if only else None)
    matrix = {k: {"script": v, **summarize(k)} for k, v in R.items()}
    (HERE / "regression_matrix.json").write_text(json.dumps(matrix, indent=1, ensure_ascii=False))
    uat_file = HERE / "uat_results.json"
    uat = json.loads(uat_file.read_text()) if uat_file.exists() else {}
    cov_path = AUDIT / "coverage.json"
    cov = json.loads(cov_path.read_text())
    have = {c["id"] for c in cov["cases"]}
    for nc in NEW_CASES:
        if nc["id"] not in have:
            cov["cases"].append({**nc, "historical_status": "Kasus baru P14", "historical_evidence": "—",
                                 "audited_commit": None, "current_status": "not_revalidated", "tested_commit": None,
                                 "evidence": [], "notes": ""})
    mapping = {**MAP, **NEW_MAP}
    for c in cov["cases"]:
        cid = c["id"]
        if cid in BLOCKED:
            c.update(current_status="blocked", tested_commit=None, evidence=[], notes=f"P14: {BLOCKED[cid]}")
        elif cid in mapping:
            keys, status, note = mapping[cid]
            res = [case_ok(k, cid, matrix) for k in keys]
            ok = all(res)
            failed = [k for k, r in zip(keys, res) if not r]
            st = status if ok else ("tested_fail" if status == T else "partial")
            c.update(current_status=st, tested_commit=BASE_SHA,
                     evidence=[f"{REL}/runs/{k}.txt" for k in keys],
                     notes=f"P14: {note}" + (f" GAGAL: {', '.join(failed)}." if failed else ""))
        else:
            c.update(current_status="planned", tested_commit=None, evidence=[],
                     notes="P14: belum ada invariant/UAT yang mengeksekusi skenario ini; dijadwalkan.")
        if cid in uat:
            u = uat[cid]
            c.update(current_status=u["status"], tested_commit=BASE_SHA,
                     evidence=sorted(set(c.get("evidence") or []) | {f"{REL}/UAT.md"}),
                     notes=(c.get("notes") or "") + f" UAT: {u['note']}")
    cov["scope"] = ("Baseline 96 kasus + kasus P14 (AUDIT-*); bukan seluruh kombinasi aplikasi. "
                    "tested_pass = skenario dieksekusi oleh invariant lulus di DB sintetis, bukan sign-off.")
    cov_path.write_text(json.dumps(cov, indent=2, ensure_ascii=False) + "\n")
    from collections import Counter
    print(json.dumps(Counter(c["current_status"] for c in cov["cases"]), indent=1))


main()
