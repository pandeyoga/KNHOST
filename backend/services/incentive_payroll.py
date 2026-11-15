"""KM-T4 (KM-07, PY-06; keputusan K-13, K-22, K-26) — Lembar Insentif tersambung ke gaji dan buku besar, per PT.

Sakelar per PT = pengaturan `hr.payroll_commission_mode`, dibaca SATU pembaca `hr_payroll_service.commission_mode`:

  accrue_then_settle (bawaan) · pay_on_invoice · nilai lain → komisi mesin masuk slip seperti dulu; lembar = keputusan saja
                                                               (`payroll_linked: false`, `gl_status: "not_required"`)
  off   → komisi mesin 0 (mesin tidak dipanggil); lembar = keputusan saja
  sheet → komisi mesin 0; lembar yang disahkan = jurnal beban & hutang insentif + masukan gaji komponen `INSENTIF`

Mengesahkan lembar di PT bermode `sheet` (`sahkan_tertaut`, urutan `02_STANDAR.md` §1):

  PERIKSA  tiap sales tertaut karyawan aktif · komponen `INSENTIF` aktif di PT induk tiap karyawan · tanggal jurnal =
           `periodic_posting.journal_date(PT lembar, bulan terakhir periode dasar paling akhir)` · periode tanggal itu
           terbuka (`preflight_posting`)                                   → gagal = tidak ada tulisan apa pun
  NIAT     `submitted` → `approving` bersyarat (`rev`) + jatah kerja (`approving_lease_until`) + tanggal jurnal + koreksi
  EFEK     satu masukan `approved` per baris bernominal (`hr_pay_inputs.enqueue_input`, kunci `isheet:<lembar>:<baris>`,
           PT = PT induk karyawan, `source_ref.charge_entity_id` = PT lembar)
  JURNAL   `gl_service.post_durable(..., post_incentive_sheet)` — satu jurnal per lembar di buku PT lembar
  SELESAI  `approving` → `approved`; jurnal gagal → tetap `approved` dengan `gl_status: "failed"` (Posting Gagal jenis
           `incentive_sheet`, ulang = langkah EFEK + JURNAL). Panggilan ulang atas `approving` (proses mati di tengah)
           meneruskan dari EFEK sesudah jatah kerjanya habis.

Gaji (`hr_payroll_service`): baris `INSENTIF` ber-`charge_entity_id` dilunasi jurnal gaji — PT proses = PT lembar →
Dr hutang insentif; PT lain → Dr piutang antar-PT + tagihan `interco_charge_service`. Sesudah proses diposting,
`tandai_dibayar` memberi `paid_run_id` pada baris lembar yang masukannya dipakai proses itu (lembar yang semua baris
bernominalnya terbayar → `paid`); anulir proses → `lepas_dibayar` (lembar kembali `approved`).

Invarian `INV-KM-4` (`cek_hutang_insentif`, dipanggil `scripts/verify_data_integrity.py`) dan daftar periksa kesiapan
beralih (`kesiapan`, `GET /api/incentive/switch-readiness`).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from core_utils import now_iso, rupiah
from db import db
from services import incentive_sheet_service as iss

MODE_SHEET = "sheet"
MODE_OFF = "off"
MODE_ACCRUE = "accrue_then_settle"
#: Pilihan sakelar yang mematikan komisi mesin di slip PT itu.
TANPA_MESIN = (MODE_OFF, MODE_SHEET)
KOMPONEN = "INSENTIF"
SUMBER = "incentive_sheet"   # jenis sumber masukan gaji dan `source_type` jurnal lembar
#: Jatah kerja satu pengesahan yang sedang berjalan (menit). Batas teknis, bukan aturan bisnis.
LEASE_MINUTES = 2

PESAN_TANPA_KARYAWAN = ("{sales} belum tertaut ke data karyawan, jadi insentifnya tidak bisa masuk gaji. Tautkan akunnya "
                        "di kartu karyawan.")
PESAN_KOMPONEN = "Komponen gaji Insentif belum aktif di {pt}."
PESAN_PERIODE = ("Periode {bulan} sudah ditutup, jadi beban insentif tidak bisa dibukukan di bulan itu. Buka periodenya "
                 "atau ubah pengaturan tanggal jurnal periodik.")
PESAN_SEDANG = "Lembar {nomor} sedang diproses. Muat ulang."
PESAN_BELUM_SELESAI = "Lembar {nomor} belum selesai disahkan: {sebab} Ulangi Sahkan."


def input_key(sheet_id: str, line_id: str) -> str:
    """Kunci masukan gaji satu baris lembar (unik `hr_pay_inputs.source_key`)."""
    return f"isheet:{sheet_id}:{line_id}"


def _lease_until() -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=LEASE_MINUTES)).isoformat()


async def mode_pt(entity_id: str) -> str:
    from services.hr_payroll_service import commission_mode
    return await commission_mode(entity_id)


async def _nama_pt(entity_id: str) -> str:
    e = await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "legal_name": 1, "short_name": 1,
                                                                "name": 1}) or {}
    return e.get("legal_name") or e.get("name") or e.get("short_name") or entity_id


async def _bulan_terakhir(entity_id: str, lines: List[Dict[str, Any]]) -> str:
    """Bulan terakhir periode dasar paling akhir di lembar: `2026-10` → 2026-10; `2026-Q3` → 2026-09; `2026` → bulan
    akhir tahun buku PT (`incentive_periods.months_of`)."""
    from services import incentive_periods as ip
    akhir = ""
    for x in lines:
        months = await ip.months_of(x.get("basis_period_type") or "month", x.get("basis_period") or "", entity_id)
        if months and months[-1] > akhir:
            akhir = months[-1]
    return akhir


# ── Pengesahan di PT bermode `sheet` ─────────────────────────────────────────────────────────────────────────────────
async def periksa(doc: Dict[str, Any], lines: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Langkah PERIKSA (tanpa tulisan). → `{karyawan: {sales_id: karyawan}, journal_date}` atau `LembarError`."""
    from services import gl_service as gl
    from services import hr_pay_components as pc
    from services import periodic_posting
    karyawan: Dict[str, Dict[str, Any]] = {}
    for x in lines:
        sid = x.get("sales_id") or ""
        if sid in karyawan:
            continue
        emp = await db.hr_employees.find_one({"user_id": sid or "__none__", "status": "active"},
                                             {"_id": 0, "id": 1, "entity_id": 1, "name": 1})
        if not emp or not emp.get("entity_id"):
            raise iss.LembarError(PESAN_TANPA_KARYAWAN.format(sales=x.get("sales_name") or "Sales"), 400)
        karyawan[sid] = emp
    for pt in sorted({e["entity_id"] for e in karyawan.values()}):
        comp = (await pc.components_for(pt)).get(KOMPONEN)
        if not comp or comp.get("is_active") is False:
            raise iss.LembarError(PESAN_KOMPONEN.format(pt=await _nama_pt(pt)), 400)
    bulan = await _bulan_terakhir(doc["entity_id"], lines) or str(doc.get("pay_period") or "")
    jd = await periodic_posting.journal_date(doc["entity_id"], bulan)
    try:
        await gl.preflight_posting(doc["entity_id"], jd)
    except gl.ClosedPeriodError as exc:
        raise iss.LembarError(PESAN_PERIODE.format(bulan=periodic_posting.label_periode(jd[:7])), 409) from exc
    return {"karyawan": karyawan, "journal_date": jd}


async def sahkan_tertaut(doc: Dict[str, Any], lines: List[Dict[str, Any]], totals: Dict[str, int],
                         rencana: Dict[str, Any], catatan: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """NIAT → EFEK → JURNAL → SELESAI untuk lembar `submitted` yang sudah lolos PERIKSA (`periksa`)."""
    now = now_iso()
    for x in lines:
        emp = rencana["karyawan"][x["sales_id"]]
        x["employee_id"] = emp["id"]
        x["pay_entity_id"] = emp["entity_id"]
        x["input_key"] = input_key(doc["id"], x["id"])
    out = await iss._simpan(doc, "submitted", {
        "status": "approving", "lines": lines, "totals": totals, "payroll_linked": True,
        "journal_date": rencana["journal_date"], "gl_status": "pending", "approved_by": iss._siapa(actor),
        "approved_at": now, "approval_note": catatan, "approving_lease_until": _lease_until()})
    return await _lanjut(out, actor)


async def lanjutkan(doc: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Pengesahan yang berhenti di `approving`: diteruskan dari EFEK bila jatah kerja pelaku sebelumnya sudah habis."""
    from pymongo import ReturnDocument
    won = await db.incentive_sheets.find_one_and_update(
        {"id": doc["id"], "status": "approving",
         "$or": [{"approving_lease_until": {"$in": ["", None]}}, {"approving_lease_until": {"$lt": now_iso()}}]},
        {"$set": {"approving_lease_until": _lease_until(), "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not won:
        raise iss.LembarError(PESAN_SEDANG.format(nomor=doc.get("number") or ""), 409)
    return await _lanjut(won, actor)


async def _masukan(doc: Dict[str, Any], actor: Dict[str, Any]) -> int:
    """EFEK — satu masukan gaji `approved` per baris bernominal (idempoten per kunci baris). → banyak masukan."""
    from services import hr_pay_inputs as pi
    pelaku = doc.get("approved_by") or iss._siapa(actor)
    n = 0
    for x in doc.get("lines") or []:
        amt = int(x.get("amount") or 0)
        if not amt:
            continue
        await pi.enqueue_input(
            entity_id=x["pay_entity_id"], employee_id=x["employee_id"], pay_period=doc["pay_period"],
            component_code=KOMPONEN,
            label=f"{x.get('component_name') or 'Insentif'} — {x.get('basis_label') or x.get('basis_period') or ''}",
            amount=amt, source_type=SUMBER, source_key=x.get("input_key") or input_key(doc["id"], x["id"]),
            source_ref={"sheet_id": doc["id"], "sheet_number": doc.get("number") or "", "number": doc.get("number") or "",
                        "line_id": x["id"], "charge_entity_id": doc["entity_id"]},
            basis_period=x.get("basis_period") or "", actor=pelaku)
        n += 1
    return n


async def _jurnal(doc: Dict[str, Any], *, raise_on_fail: bool = False) -> Dict[str, Any]:
    from services import gl_service as gl
    pelaku = (doc.get("approved_by") or {}).get("name") or "system"
    return await gl.post_durable(iss.COLL, doc["id"], lambda: gl.post_incentive_sheet(doc, pelaku),
                                 source_type=SUMBER, source_id=doc["id"], raise_on_fail=raise_on_fail)


async def _lanjut(doc: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    from pymongo import ReturnDocument
    try:
        await _masukan(doc, actor)
    except Exception as exc:  # noqa: BLE001 — jatah kerja dilepas supaya Sahkan berikutnya meneruskan
        await db.incentive_sheets.update_one({"id": doc["id"], "status": "approving"},
                                             {"$set": {"approving_lease_until": "", "updated_at": now_iso()}})
        raise iss.LembarError(PESAN_BELUM_SELESAI.format(nomor=doc.get("number") or "", sebab=str(exc).rstrip(".") + "."),
                              409) from exc
    await _jurnal(doc)
    hist = iss._riwayat("approve", doc.get("approved_by") or iss._siapa(actor), now_iso(), doc.get("approval_note") or "",
                        "submitted", "approved")
    out = await db.incentive_sheets.find_one_and_update(
        {"id": doc["id"], "status": "approving"},
        {"$set": {"status": "approved", "approving_lease_until": "", "updated_at": now_iso()}, "$inc": {"rev": 1},
         "$push": {"history": hist}}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    return out or await iss.get_sheet(doc["id"]) or doc


async def ulang_jurnal(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """Jalur Ulang Posting jenis `incentive_sheet`: masukan dipastikan ada (idempoten), lalu jurnal lembar sekali.
    Masih gagal → melempar (panel: 409 "Posting masih gagal: …")."""
    cur = await iss.get_sheet(doc["id"]) or doc
    if cur.get("status") == "approving":
        cur = await lanjutkan(cur, actor)
        if cur.get("gl_status") != "failed":
            return
    await _masukan(cur, actor)
    await _jurnal(cur, raise_on_fail=True)


async def info_lembar(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Untuk layar rincian lembar: sakelar PT lembar, tanggal jurnal (tersimpan, atau perkiraan bila lembar diajukan di
    PT bermode `sheet`), banyak baris bernominal yang masuk gaji, dan periode bayarnya."""
    from config_registry import require
    from services import periodic_posting
    mode = await mode_pt(doc["entity_id"])
    label = next((o["label"] for o in require("hr.payroll_commission_mode").get("options") or ()
                  if o.get("value") == mode), mode)
    lines = doc.get("lines") or []
    jd = doc.get("journal_date") or ""
    if not jd and mode == MODE_SHEET and doc.get("status") in ("draft", "submitted") and lines:
        try:
            bulan = await _bulan_terakhir(doc["entity_id"], lines)
            jd = await periodic_posting.journal_date(doc["entity_id"], bulan) if bulan else ""
        except ValueError:
            jd = ""
    return {"mode": mode, "mode_label": label, "sheet_mode": mode == MODE_SHEET,
            "linked": bool(doc.get("payroll_linked")), "journal_date": jd,
            "lines_to_payroll": sum(1 for x in lines if int(x.get("amount") or 0)),
            "pay_period": doc.get("pay_period") or ""}


# ── Gaji: baris lembar dibayar / dilepas ─────────────────────────────────────────────────────────────────────────────
async def _perbarui_lembar(sheet_id: str, ubah: Callable[[List[Dict[str, Any]]], bool], pelaku: str,
                           alasan: str) -> None:
    """Ubah baris satu lembar dengan pembaruan bersyarat `rev` (dua proses gaji PT berbeda bisa membayar baris lembar
    yang sama bersamaan). Status `approved` ↔ `paid` mengikuti baris: lunas = semua baris bernominal ber-`paid_run_id`."""
    for _ in range(8):
        doc = await db.incentive_sheets.find_one({"id": sheet_id}, {"_id": 0})
        if not doc or doc.get("status") not in iss.DISAHKAN:
            return
        lines = [dict(x) for x in doc.get("lines") or []]
        if not ubah(lines):
            return
        bernominal = [x for x in lines if int(x.get("amount") or 0)]
        lunas = bool(bernominal) and all(x.get("paid_run_id") for x in bernominal)
        baru = "paid" if lunas else "approved"
        upd: Dict[str, Any] = {"$set": {"lines": lines, "status": baru, "updated_at": now_iso()}, "$inc": {"rev": 1}}
        if baru != doc["status"]:
            upd["$push"] = {"history": iss._riwayat("paid" if baru == "paid" else "unpaid", {"id": "", "name": pelaku},
                                                    now_iso(), alasan, doc["status"], baru)}
        res = await db.incentive_sheets.update_one({"id": sheet_id, "rev": int(doc.get("rev") or 0)}, upd)
        if res.modified_count:
            return
    raise RuntimeError(f"Lembar insentif {sheet_id} terus berubah; tanda bayar belum tertulis.")


async def tandai_dibayar(run: Dict[str, Any]) -> int:
    """Sesudah proses gaji `posted`: baris lembar yang masukannya dipakai proses itu diberi `paid_run_id`. → baris."""
    per_lembar: Dict[str, set] = {}
    async for inp in db.hr_pay_inputs.find({"used_run_id": run["id"], "status": "used", "source_type": SUMBER},
                                           {"_id": 0, "source_ref": 1}):
        ref = inp.get("source_ref") or {}
        if ref.get("sheet_id") and ref.get("line_id"):
            per_lembar.setdefault(ref["sheet_id"], set()).add(ref["line_id"])
    n = 0
    for sid, ids in per_lembar.items():
        def ubah(lines: List[Dict[str, Any]], ids=ids) -> bool:
            berubah = False
            for x in lines:
                if x.get("id") in ids and x.get("paid_run_id") != run["id"]:
                    x.update({"paid_run_id": run["id"], "paid_run_number": run.get("number") or "",
                              "paid_at": now_iso()})
                    berubah = True
            return berubah
        await _perbarui_lembar(sid, ubah, run.get("posted_by") or "system", f"Dibayar lewat {run.get('number') or ''}")
        n += len(ids)
    return n


async def lepas_dibayar(run: Dict[str, Any], pelaku: str = "system") -> int:
    """Anulir proses gaji: `paid_run_id` baris yang dibayar proses itu dikosongkan; lembar kembali `approved`."""
    ids = [d["id"] async for d in db.incentive_sheets.find({"lines.paid_run_id": run["id"]}, {"_id": 0, "id": 1})]
    for sid in ids:
        def ubah(lines: List[Dict[str, Any]]) -> bool:
            berubah = False
            for x in lines:
                if x.get("paid_run_id") == run["id"]:
                    for f in ("paid_run_id", "paid_run_number", "paid_at"):
                        x.pop(f, None)
                    berubah = True
            return berubah
        await _perbarui_lembar(sid, ubah, pelaku, f"Penggajian {run.get('number') or ''} dianulir")
    return len(ids)


async def sesudah_posting(run: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """Dipanggil `post_run_gl` sesudah proses `posted`: tagihan antar-PT terbit (jurnal PT tertagih) + baris dibayar."""
    from services import interco_charge_service as icc
    await icc.terbitkan(run, actor)
    await tandai_dibayar(run)


# ── Kesiapan beralih (GET /api/incentive/switch-readiness) ───────────────────────────────────────────────────────────
def _bulan_lalu(ym: str, n: int) -> str:
    y, m = int(ym[:4]), int(ym[5:7]) - n
    while m <= 0:
        y, m = y - 1, m + 12
    return f"{y:04d}-{m:02d}"


async def saldo_hutang_insentif(entity_id: str) -> float:
    """Saldo (kredit − debit) akun hutang insentif PT itu — semua kode pemetaan `penjualan.hutang_insentif`."""
    from services import gl_mapping_service as glm
    codes = set(await glm.known_codes("penjualan.hutang_insentif", entity_id))
    tot = 0
    async for je in db.journal_entries.find({"entity_id": entity_id, "status": {"$ne": "void"},
                                             "lines.account_code": {"$in": sorted(codes)}}, {"_id": 0, "lines": 1}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") in codes:
                tot += round(float(ln.get("credit") or 0) * 100) - round(float(ln.get("debit") or 0) * 100)
    return tot / 100


async def kesiapan(entity_id: str) -> Dict[str, Any]:
    """Daftar periksa sebelum PT dialihkan ke Lembar Insentif. Tidak mengubah apa pun (H5: sakelar diubah pemilik)."""
    from config_registry import require
    from services import incentive_facts as ifc
    from services import periodic_posting
    mode = await mode_pt(entity_id)
    label = next((o["label"] for o in require("hr.payroll_commission_mode").get("options") or ()
                  if o.get("value") == mode), mode)
    checks: List[Dict[str, Any]] = []
    # 1 — pencocokan angka KM-T1 dua bulan terakhir yang sudah lewat
    ini = periodic_posting.hari_ini()[:7]
    bulan = [_bulan_lalu(ini, 2), _bulan_lalu(ini, 1)]
    salah = []
    for p in bulan:
        rec = await ifc.reconcile(entity_id, p)
        if not (rec["omzet"]["ok"] and rec["pencairan"]["ok"]):
            salah.append(periodic_posting.label_periode(p))
    nama = " dan ".join(periodic_posting.label_periode(p) for p in bulan)
    checks.append({"code": "pencocokan", "ok": not salah,
                   "text": (f"Pencocokan angka {nama} cocok dengan buku besar." if not salah else
                            f"Pencocokan angka {' dan '.join(salah)} belum cocok dengan buku besar. Periksa di "
                            "Pencocokan angka.")})
    # 2 — saldo hutang insentif PT = 0 (akrual komisi otomatis sudah dilunasi gaji)
    saldo = await saldo_hutang_insentif(entity_id)
    checks.append({"code": "saldo_hutang", "ok": abs(saldo) < 1,
                   "text": ("Saldo hutang insentif PT ini Rp 0 — akrual komisi otomatis sudah dilunasi." if abs(saldo) < 1
                            else f"Saldo hutang insentif PT ini masih {rupiah(saldo)}. Lunasi lewat gaji dulu supaya "
                                 "insentif tidak terbayar dua kali.")})
    # 3 — semua sales pada lembar draf & diajukan tertaut karyawan aktif
    belum: List[str] = []
    async for s in db.incentive_sheets.find({"entity_id": entity_id, "status": {"$in": ["draft", "submitted"]}},
                                            {"_id": 0, "lines": 1}):
        for x in s.get("lines") or []:
            if x.get("sales_name") in belum:
                continue
            if not await db.hr_employees.find_one({"user_id": x.get("sales_id") or "__none__", "status": "active"},
                                                  {"_id": 0, "id": 1}):
                belum.append(x.get("sales_name") or "Sales")
    checks.append({"code": "tautan_karyawan", "ok": not belum,
                   "text": ("Semua sales pada lembar draf dan diajukan sudah tertaut ke data karyawan." if not belum else
                            f"Belum tertaut ke data karyawan: {', '.join(sorted(belum)[:5])}"
                            f"{' dan lainnya' if len(belum) > 5 else ''}. Tautkan akunnya di kartu karyawan.")})
    # 4 — tidak ada proses gaji yang belum diposting dan memuat komisi mesin
    runs = [r async for r in db.hr_payroll_runs.find(
        {"entity_id": entity_id, "status": {"$in": ["draft", "pending_approval", "approved"]}},
        {"_id": 0, "id": 1, "number": 1})]
    berkomisi: List[str] = []
    for r in runs:
        if await db.hr_payslips.find_one({"run_id": r["id"], "components": {"$elemMatch": {
                "code": "KOMISI", "amount": {"$ne": 0}, "source": {"$exists": False}}}}, {"_id": 0, "id": 1}):
            berkomisi.append(r.get("number") or r["id"])
    checks.append({"code": "proses_gaji", "ok": not berkomisi,
                   "text": ("Tidak ada proses gaji yang belum diposting dan memuat komisi otomatis." if not berkomisi else
                            f"Proses gaji {', '.join(berkomisi[:3])} memuat komisi otomatis dan belum diposting. "
                            "Selesaikan atau hitung ulang sesudah beralih.")})
    return {"entity_id": entity_id, "mode": mode, "mode_label": label, "checks": checks,
            "ready": all(c["ok"] for c in checks)}


# ── INV-KM-4 ─────────────────────────────────────────────────────────────────────────────────────────────────────────
async def cek_hutang_insentif(entity_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """INV-KM-4, per PT bermode `sheet`: saldo akun hutang insentif = Σ nominal baris lembar `payroll_linked` yang
    berjurnal (`gl_status` posted) dan belum ber-`paid_run_id`. → baris per PT {entity_id, saldo, lembar, ok}."""
    q: Dict[str, Any] = {"id": entity_id} if entity_id else {}
    out: List[Dict[str, Any]] = []
    async for e in db.business_entities.find(q, {"_id": 0, "id": 1}):
        eid = e.get("id")
        if not eid or await mode_pt(eid) != MODE_SHEET:
            continue
        lembar = 0
        async for s in db.incentive_sheets.find({"entity_id": eid, "payroll_linked": True, "gl_status": "posted",
                                                 "status": {"$in": list(iss.DISAHKAN)}}, {"_id": 0, "lines": 1}):
            lembar += sum(int(x.get("amount") or 0) for x in s.get("lines") or [] if not x.get("paid_run_id"))
        saldo = await saldo_hutang_insentif(eid)
        out.append({"entity_id": eid, "saldo": saldo, "lembar": float(lembar), "ok": abs(saldo - lembar) < 1})
    return out
