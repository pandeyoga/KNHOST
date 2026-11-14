"""R6.5 — Scheduler (APScheduler) untuk alert & notifikasi terjadwal.

DESAIN
- **AsyncIOScheduler** zona **Asia/Jakarta** (WIB) → jadwal harian 08:00 WIB benar-benar
  08:00 WIB, bukan UTC.
- **Guard single-instance**: uvicorn `--reload` menjalankan proses reloader + worker;
  hanya worker yang menjalankan lifespan. Untuk aman ganda, dipakai LOCK dengan
  heartbeat di `system_settings` scope='alerts' (field `lock`). Proses lain yang
  melihat lock masih segar (<180s) TIDAK menjalankan scheduler-nya.
- **Registry job** dideklarasikan sekali (`JOBS`); jadwal & on/off dapat diubah user
  lewat API tanpa mengubah kode.
- Setiap eksekusi dicatat di `sys_scheduler_runs` (histori: durasi, status, jumlah
  notifikasi dibuat, pesan WA ter-antre, error).
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db import db
from core_utils import new_id, now_iso
from services import alert_service as alerts
from services import export_schedule as _expsched   # L11 — export terjadwal
from services import interco_service as _ic_remind   # LN-024 — pengingat bayar antar-PT
from services import alert_ops_service as ops        # PS-21 — job operasional
from services import digest_service as digest
from services import escalation_service as escalation
from services import marketing_service as _mkt
from services import penalty_service as penalties      # FASE G-2 — akrual denda
from services import finance_case_scan as cases        # FASE G-9 — pemindai kasus keuangan
from services import contra_bon_reminder as contrabon  # FASE G-7 — pengingat tukar faktur
from services import interco_reminder as icreminder    # FASE G-6b — pengingat settlement antar-PT
from services import period_unlock_service as punlock   # FASE G-5 — auto-tutup jendela unlock periode
from services import rnd_sla_service as rndsla          # PS-18 — eskalasi SLA sample R&D
from services import approval_reminder as aprem          # 2026-08-15 — pengingat antrean persetujuan
from services import turn_notification_service as _turn  # 2026-09 — giliran Anda
from services import inventory_drift_watch as invdrift   # 2026-06 — pemantau drift persediaan
from services import saga_lock_watch as sagawatch         # 2026-09 — kunci saga menggantung (T-01 Opsi B)
from services import printer_stuck_watch as prstuck       # Sesi 15 — label tertahan tanpa printer online
from services import rfid_v2_health as rfidhealth         # PREP-D1 — kesehatan reader gate U300 V2 (AUD-MW-17)
from services import gate_txn_service as gatetxn          # PREP-H — ulang transaksi gate tertunda/gagal
from services import rfid_v2_retention as rfidretention   # PREP-H — masa simpan bukti gate (arsip → hapus)
from services import wa_alert_service as wa
from services import analytics_facts as _facts           # Tanya KN F1 — fakta penjualan
from services import ai_schedules as _aisched            # Tanya KN F4 — laporan terjadwal
from services import analytics_snapshots as _snaps       # Tanya KN F5 — snapshot stok & piutang
from services import ai_chat_service as _aichat          # Tanya KN §7.3 — prewarm cache prompt
from services import ai_insights as _aiins               # Tanya KN — peringatan anomali harian
from services import config_resolver as _cfgres          # KF-T3 — pengaturan terjadwal yang jatuh tempo

logger = logging.getLogger("scheduler")

SETTINGS_SCOPE = "alerts"
TZ = "Asia/Jakarta"
LOCK_TTL_SECONDS = 180
HEARTBEAT_SECONDS = 60
LOCK_RETRY_SECONDS = 30    # coba ambil-alih lock berkala bila sedang dipegang proses lain
_OWNER = f"{os.uname().nodename}:{os.getpid()}"

_scheduler = None          # AsyncIOScheduler | None


async def _reservation_expiry_job():
    from services.inventory_service import expire_old_reservations   # FIX-3b — dulu dipicu GET (STK-11)
    return {"expired": await expire_old_reservations()}


async def _supplier_deadline_job():
    from services import return_disposition_service as _rds   # LN-093 (impor malas, hindari siklus)
    return await _rds.job_supplier_deadline_reminder()


async def _entity_tax_status_job():
    from services import entity_lifecycle_service as _lc   # KP-T1 — status PKP terjadwal (impor malas)
    return await _lc.job_entity_tax_status_due()

_owns_lock = False


# ═══ Registry job ═══════════════════════════════════════════════════════════
JOBS: List[Dict[str, Any]] = [
    {"id": "ar_overdue", "label": "Piutang Jatuh Tempo (AR)",
     "description": "Pindai piutang pelanggan yang lewat jatuh tempo (umur piutang) → notifikasi manager & sales pemegang akun.",
     "kind": "daily", "hour": 8, "minute": 0, "fn": alerts.job_ar_overdue,
     "link": "ar-aging"},
    {"id": "ap_due", "label": "Hutang Supplier Jatuh Tempo (AP)",
     "description": "Tagihan supplier terposting yang jatuh tempo dalam batas hari yang diatur (bawaan 7 hari) atau sudah lewat (berdasarkan termin pembayaran supplier).",  # KP-T7
     "kind": "daily", "hour": 8, "minute": 5, "fn": alerts.job_ap_due,
     "link": "vendor-bills"},
    {"id": "depreciation_due", "label": "Reminder Penyusutan Aset",
     "description": "Ingatkan bila penyusutan bulan lalu belum dijalankan untuk aset tetap aktif.",
     "kind": "daily", "hour": 8, "minute": 10, "fn": alerts.job_depreciation_due,
     "link": "fixed-assets"},
    {"id": "budget_alert", "label": "Peringatan Anggaran",
     "description": "Anggaran yang TERLAMPAUI atau mendekati batas (realisasi + komitmen PO) per entitas.",
     "kind": "daily", "hour": 8, "minute": 15, "fn": alerts.job_budget_alert,
     "link": "budget"},
    {"id": "production_stalled", "label": "Perintah Kerja Produksi Tertunda",
     "description": "WO dirilis melewati batas hari yang diatur (bawaan 3) belum selesai, WO draf melewati batasnya (bawaan 7), atau WO dengan bahan kurang.",  # KP-T7
     "kind": "daily", "hour": 8, "minute": 20, "fn": alerts.job_production_stalled,
     "link": "production"},
    {"id": "ops_stalled", "label": "Tugas Gudang Tertunda",
     "description": "Tugas barang masuk/keluar terbuka melewati batas hari yang diatur (bawaan 2), diringkas per gudang & arah.",  # KP-T7
     "kind": "interval", "interval_hours": 4, "fn": alerts.job_ops_stalled,
     "link": "operations"},
    # ── FIX-3b (B3a STK-11, B2b ANOM-06 / K-B2b-12) ─────────────────────────
    {"id": "reservation_expiry", "label": "Kedaluwarsa Reservasi Pesanan",
     "description": "Pesanan yang BELUM disetujui (Dicadangkan / Menunggu persetujuan) dan masa reservasinya (3 hari) "
                    "lewat dibuat Kedaluwarsa; roll yang dicadangkan dilepas kembali ke stok. Pesanan yang sudah "
                    "disetujui atau menunggu barang (backorder) TIDAK pernah kedaluwarsa otomatis. Dulu dijalankan "
                    "diam-diam saat daftar pesanan/dasbor dibuka.",
     "kind": "interval", "interval_minutes": 30, "fn": _reservation_expiry_job,
     "link": "orders"},
    {"id": "event_scan", "label": "Pindai Event Sistem",
     "description": "Stok menipis, reservasi mendekati kedaluwarsa, dan pesanan/PO menunggu persetujuan.",
     "kind": "interval", "interval_hours": 4, "fn": alerts.job_event_scan,
     "link": "operations"},
    # ── R6.6 ──────────────────────────────────────────────────────────────
    {"id": "escalation_scan", "label": "Eskalasi Alert Belum Ditindak",
     "description": "Peringatan penting yang belum dibaca melewati batas waktu dinaikkan otomatis ke atasan (sales/gudang → manager → admin).",
     "kind": "interval", "interval_hours": 2, "fn": escalation.job_escalation_scan,
     "link": ""},
    {"id": "content_reminder", "label": "Pengingat Tayang Konten Sosial Media",
     "description": "Post terjadwal yang tayang dalam jarak menit yang diatur (bawaan 60) atau terlambat → ingatkan PIC (in-app & WA) agar diposting dan ditandai Tayang.",  # KP-T7
     "kind": "interval", "interval_minutes": 15, "fn": _mkt.job_content_reminder,
     "link": "mkt-calendar"},
    {"id": "daily_digest", "label": "Ringkasan Harian (WhatsApp)",
     "description": "Gabungkan seluruh alert hari ini menjadi SATU pesan ringkas per penerima — mencegah staf kebanjiran notifikasi.",
     "kind": "daily", "hour": 8, "minute": 30, "fn": digest.job_daily_digest,
     "link": ""},
    # ── PS-21 (quick win operasional) ─────────────────────────────────────
    {"id": "po_arrival", "label": "Barang PO Datang",
     "description": "Penerimaan barang PO (GR) yang selesai dalam jendela jam yang diatur (bawaan 24) → beri tahu MD/manager, gudang, dan sales yang punya pesanan pendingan atas produk itu.",  # KP-T7
     "kind": "interval", "interval_hours": 2, "fn": ops.job_po_arrival,
     "link": "purchasing"},
    {"id": "backorder_ready", "label": "Barang Pendingan Siap",
     "description": "Order dengan pendingan (backorder) yang stoknya sudah tersedia di gudang → beri tahu sales pemegang akun agar bisa follow-up pelanggan.",
     "kind": "interval", "interval_hours": 2, "fn": ops.job_backorder_ready,
     "link": "orders"},
    {"id": "ar_due_soon", "label": "Piutang Mendekati Jatuh Tempo",   # KP-T7 — hari pengingat kini pengaturan
     "description": "Ingatkan piutang tepat pada hari yang diatur (bawaan H-3, H-1, hari-H, dan H+1; melengkapi 'Piutang Jatuh Tempo' yang memindai umur piutang lama). Penyaringan ganda harian mencegah pesan dobel.",
     "kind": "daily", "hour": 7, "minute": 55, "fn": ops.job_ar_due_soon,
     "link": "ar-aging"},
    # ── FASE G-2 ──────────────────────────────────────────────────────────
    {"id": "penalty_accrual", "label": "Hitung Denda Keterlambatan",
     "description": "Pindai seluruh rencana pembayaran aktif; cicilan/milestone yang melewati jatuh tempo + masa tenggang dibuatkan USULAN nota denda (draft, tanpa jurnal) agar masih bisa dinegosiasikan. Idempotent: satu nota per baris per bulan.",
     "kind": "daily", "hour": 7, "minute": 45, "fn": penalties.job_penalty_accrual,
     "link": "payment-plans"},
    # ── FASE G-9 ──────────────────────────────────────────────────────────
    {"id": "finance_case_scan", "label": "Pindai Kasus Keuangan",
     "description": "Cari uang yang nyangkut lalu buatkan kasusnya sendiri: titipan dana tak dikenal yang menganggur lebih lama dari batas, dan pembayaran pelanggan yang terlihat dobel. Kasus yang melewati batas waktu (SLA) dinaikkan ke manager lalu admin. Idempotent: dijalankan berkali-kali tidak menggandakan kasus.",
     "kind": "daily", "hour": 8, "minute": 25, "fn": cases.job_finance_case_scan,
     "link": "finance-cases"},
    # ── FASE G-7 ──────────────────────────────────────────────────────────
    {"id": "contra_bon_reminder", "label": "Pengingat Tukar Faktur (Kontrabon)",
     "description": "Ingatkan H-n sebelum jadwal tukar faktur tiap supplier, berisi jumlah penerimaan barang yang belum ditagih dan tagihan yang siap dikontrabon. Sekaligus menaikkan kontrabon yang menunggu verifikasi/persetujuan lebih lama dari batas waktunya. Idempotent: satu notifikasi per hari per supplier/kontrabon.",
     "kind": "daily", "hour": 7, "minute": 30, "fn": contrabon.job_contra_bon_reminder,
     "link": "contra-bons"},
    # ── FASE G-6b ─────────────────────────────────────────────────────────
    {"id": "interco_settlement_reminder", "label": "Pengingat Settlement Antar-PT",
     "description": "Ingatkan Keuangan bila saldo satu pasangan PT tidak bergerak lebih lama dari batas di Pusat Pengaturan (antar_entitas.settlement_reminder_days). MENGINGATKAN, bukan memaksa — netting tetap dijalankan manual lewat tombol 'Buat Settlement' (keputusan pemilik). Umur saldo dihitung dari aktivitas NYATA (dokumen & settlement terakhir), bukan dari kapan barisnya terakhir dihitung ulang. Idempotent: satu notifikasi per hari per pasangan PT.",
     "kind": "daily", "hour": 7, "minute": 40, "fn": icreminder.job_interco_settlement_reminder,
     "link": "interco-transactions"},
    # ── FASE G-5 ──────────────────────────────────────────────────────────
    {"id": "period_unlock_auto_close", "label": "Tutup Otomatis Jendela Buka Periode",
     "description": "Tutup sendiri jendela 'Buka Periode (Unlock)' yang sudah lewat batas waktu (config periode.unlock_window_hours). Jendela yang sempat dipakai memposting jurnal mundur ditandai 'reclosed' + closing-nya jadi 'basi' agar admin bisa Tutup Ulang; yang tak terpakai jadi 'expired'. Idempotent: hanya menyentuh unlock yang benar-benar sudah lewat.",
     "kind": "interval", "interval_hours": 1, "fn": punlock.job_period_unlock_auto_close,
     "link": "period-unlock"},
    # ── PS-18 ─────────────────────────────────────────────────────────────
    {"id": "rnd_sla_escalation", "label": "Eskalasi SLA Sample R&D",     "description": "Round sample labdip/proofing yang masih berjalan tetapi sudah lewat tenggat diberitahukan ke manager setiap hari; bila keterlambatannya sudah mencapai batas di Pusat Pengaturan (rnd.sla_escalate_admin_days, bawaan 3 hari) notifikasi ikut dinaikkan ke admin/pemilik. Permintaan yang sudah diputus atau dibatalkan dilewati. Idempotent: satu notifikasi per hari per round, jadi boleh dijalankan berkali-kali.",
     "kind": "daily", "hour": 7, "minute": 35, "fn": rndsla.job_rnd_sla_escalation,
     "link": "rnd-reports"},
    # ── PENGINGAT ANTREAN PERSETUJUAN (permintaan pemilik 2026-08-15) ──────
    {"id": "approval_backlog_reminder", "label": "Pengingat Keputusan yang Menunggu",
     "description": "Ingatkan manajer setiap pagi tentang dokumen yang menunggu "
                    "KEPUTUSANNYA paling lama — bukan sekadar jumlah, tetapi nomor "
                    "dokumen, jenis, dan sudah berapa hari menunggu (mis. 'PO-00010 · "
                    "Palembang Silk House — menunggu 12 hari'). Sumber angkanya SAMA "
                    "dengan KPI beranda & Pusat Persetujuan (services/"
                    "approval_backlog_service.py) sehingga tidak mungkin berbeda. "
                    "Ambang umur diatur pemilik di Pusat Pengaturan "
                    "(approval.reminder_min_days, bawaan 2 hari); bila umur dokumen "
                    "sudah ≥ 2× ambang, notifikasi ikut dinaikkan ke admin/pemilik "
                    "karena antreannya bukan menumpuk lagi tetapi MANDEK. Idempotent: "
                    "satu notifikasi per hari per badan usaha.",
     "kind": "daily", "hour": 7, "minute": 45, "fn": aprem.job_approval_backlog_reminder,
     "link": "approval-inbox"},
    # ── INV-GL-DRIFT (lanjutan 2026-06) ───────────────────────────────────
    {"id": "inventory_drift_watch", "label": "Pantau Selisih Persediaan (GL vs Fisik)",
     "description": "Bandingkan nilai fisik roll (subledger) dengan saldo GL "
                    "Persediaan 1-1300 tiap buku, lalu beri tahu yang berwenang "
                    "memposting true-up (izin accounting.manage) bila selisihnya "
                    "melewati ambang di Pusat Pengaturan "
                    "(inventory.drift_alert_rupiah, bawaan Rp 1.000). Selisih "
                    "persediaan tidak pernah memunculkan galat — sebelum job ini ia "
                    "hanya terlihat kalau seseorang menjalankan alat pengembang, "
                    "sehingga neraca bisa berselisih berhari-hari tanpa ada yang "
                    "tahu. Pesannya menyebut nilai fisik, saldo GL, arah selisih, "
                    "dan true-up terakhir beserta dasarnya. Idempotent: satu "
                    "notifikasi per hari per badan usaha; job ini TIDAK memposting "
                    "jurnal apa pun.",
     "kind": "daily", "hour": 6, "minute": 40,
     "fn": invdrift.job_inventory_drift_watch, "link": "general-ledger"},
    # ── T-01 Opsi B (2026-09) ─────────────────────────────────────────────
    {"id": "saga_lock_watch", "label": "Kunci Saga Menggantung",
     "description": "Aksi multi-koleksi yang diklaim lalu mati di tengah meninggalkan "
                    "`saga_lock` pada dokumen induk: aksi ulang ditolak 409 sampai admin "
                    "melepasnya. Sebelum job ini kunci hanya terlihat bila admin kebetulan "
                    "membuka Pusat Pengaturan → Kunci Saga. Job ini memindai semua koleksi "
                    "induk yang dikunci dan memberi tahu admin bila umur kunci melewati "
                    "ambang di Pusat Pengaturan (saga.stuck_lock_minutes, bawaan 10 menit) — "
                    "menyebut dokumen, aksi, siapa, sejak kapan, dan alasan gagal bila ada. "
                    "Job ini TIDAK melepas kunci. Idempotent: satu notifikasi per hari per kunci.",
     "kind": "interval", "interval_minutes": 10, "fn": sagawatch.job_saga_lock_watch,
     "link": "settings-config"},
    # ── Sesi 15 — label tertahan ─────────────────────────────────────────
    {"id": "printer_stuck_watch", "label": "Label Tertahan di Printer",
     "description": "Antrean label (QR/RFID) yang menunggu melewati batas menit yang diatur (bawaan 30) di gudang tanpa printer "  # KP-T7
                    "online (heartbeat > 5 menit) diberitahukan ke kepala gudang & manager: "
                    "jumlah label, umur antrean, gudang. Satu notifikasi per gudang sampai "
                    "antrean bersih (dedupe unread). Job ini TIDAK mengubah antrean.",
     "kind": "interval", "interval_minutes": 10, "fn": prstuck.job_printer_stuck_watch,
     "link": "operations"},
    # ── PREP-D1 — kesehatan reader gate U300 V2 ──────────────────────────
    {"id": "rfid_reader_health_watch", "label": "Kesehatan Reader Gate RFID",
     "description": "Reader gate U300 V2 yang berhenti membaca, laporannya (telemetry) terlambat, atau antreannya "
                    "menumpuk diberitahukan ke kepala gudang & manager — satu notifikasi per reader per aturan saat "
                    "aturan berubah aktif. Ambang = titik awal kalibrasi. Job ini TIDAK mengubah reader/lintasan.",
     "kind": "interval", "interval_minutes": 5, "fn": rfidhealth.job_rfid_reader_health_watch,
     "link": "settings-devices"},
    # ── PREP-H — transaksi gate di pekerja latar + masa simpan bukti ──────
    {"id": "rfid_gate_txn_retry", "label": "Ulang Transaksi Gate RFID",
     "description": "Jaring pengaman pekerja latar transaksi gate (tiba putaway, terima transfer, bukti keluar per "
                    "trip): lintasan yang transaksinya masih menunggu, gagal (diulang bertahap 30 dtk → 1 jam), atau "
                    "pemrosesnya mati di tengah dikerjakan ulang. Idempoten — tidak menggandakan tiba/terima. Sesudah "
                    "7 kali gagal berhenti dan menunggu tombol 'Ulangi transaksi' di Antrean periksa.",
     "kind": "interval", "interval_minutes": 2, "fn": gatetxn.job_rfid_gate_txn_retry,
     "link": "settings-devices"},
    {"id": "rfid_evidence_retention", "label": "Masa Simpan Bukti Gate RFID",
     "description": "Bukti mentah lintasan gate (bacaan per tag × antena, sinar photo-eye) yang lebih tua dari "
                    "masa simpan diarsipkan ke berkas terkompresi di server lalu dihapus dari database; bacaan gate "
                    "jalur lama juga. Keputusan lintasan, klaim lewat, sesi dokumen, antrean periksa & buku transaksi "
                    "TIDAK pernah dihapus. Mode uji coba hanya menghitung. Setelan: rfid.evidence_retention_*.",
     "kind": "daily", "hour": 2, "minute": 30, "fn": rfidretention.job_rfid_evidence_retention,
     "link": "settings-config"},
    # ── 2026-09 — giliran Anda ───────────────────────────────────────────
    {"id": "turn_scan", "label": "Pemberitahuan Giliran Anda",
     "description": "Menyapu SO, PO, retur penjualan/pembelian, dan permintaan sample: setiap dokumen "
                    "yang berpindah tahap memberi tahu peran yang harus bertindak berikutnya (lonceng), "
                    "dan menutup pemberitahuan tahap sebelumnya. Jaring pengaman untuk transisi yang "
                    "tidak lewat jejak audit; satu pemberitahuan per (dokumen, tahap, orang).",
     "kind": "interval", "interval_minutes": 5, "fn": _turn.job_turn_scan,
     "link": "notifications"},
    # Tanya KN F1.1 — tabel fakta penjualan untuk asisten analitik.
    {"id": "ai_fact_sync", "label": "Fakta Penjualan Analitik (inkremental)",
     "description": "Memperbarui tabel fakta penjualan (fact_sales_lines) dari pesanan yang berubah sejak "
                    "sinkron terakhir. Dipakai asisten Tanya KN & template laporan.",
     "kind": "interval", "interval_minutes": 5, "fn": _facts.job_fact_sync, "link": "notifications"},
    {"id": "ai_fact_nightly", "label": "Fakta Penjualan Analitik (bangun ulang 90 hari)",
     "description": "Membangun ulang fakta penjualan 90 hari terakhir setiap malam sebagai jaring pengaman.",
     "kind": "daily", "hour": 2, "minute": 0, "fn": _facts.job_fact_nightly, "link": "notifications"},
    {"id": "ai_schedule_dispatch", "label": "Laporan Terjadwal Tanya KN",
     "description": "Menjalankan laporan template yang dijadwalkan pengguna (harian/mingguan) dengan hak akses "
                    "pemilik jadwal, lalu mengirim ringkasannya sebagai notifikasi aplikasi.",
     "kind": "interval", "interval_minutes": 5, "fn": _aisched.job_ai_schedule_dispatch, "link": "tanya-kn"},
    {"id": "ai_snapshot_daily", "label": "Snapshot Harian Stok & Piutang (analitik)",
     "description": "Menyimpan posisi stok (per entitas × gudang × produk) dan piutang (per pelanggan × umur) "
                    "setiap malam agar asisten bisa menjawab posisi per tanggal lampau.",
     "kind": "daily", "hour": 23, "minute": 55, "fn": _snaps.job_snapshot_daily, "link": "tanya-kn"},
    {"id": "ai_maintenance", "label": "Pemeliharaan Tanya KN (retensi riwayat)",
     "description": "Menghapus sesi chat & riwayat laporan terjadwal yang lebih tua dari ai.chat_retention_days.",
     "kind": "daily", "hour": 3, "minute": 15, "fn": _aisched.job_ai_maintenance, "link": "tanya-kn"},
    {"id": "ai_prewarm", "label": "Pemanasan Cache Prompt Tanya KN",
     "description": "Hari kerja pagi: mengirim prefix statis ke OpenAI agar pertanyaan pertama lebih murah. "
                    "Diam bila ai.prewarm_enabled mati, tanpa kunci, atau mode uji.",
     "kind": "daily", "hour": 6, "minute": 55, "fn": _aichat.job_ai_prewarm, "link": "tanya-kn"},
    {"id": "interco_payment_reminder", "label": "Pengingat Bayar Antar-PT",
     "description": "Memberi tahu finance PT pembayar beberapa hari sebelum tanggal bayar antar-PT sesuai cutoff yang "
                    "diatur (tidak berjalan selama cutoff KLX-03 belum dikonfigurasi).",
     "kind": "interval", "interval_minutes": 60, "fn": _ic_remind.job_interco_payment_reminder,
     "link": "interco-transactions"},
    {"id": "return_supplier_deadline_reminder", "label": "Pengingat Batas Retur Supplier (Antar-PT)",
     "description": "Memberi tahu gudang/admin & finance PT pemasok (mis. CST) N hari (returns.supplier_reminder_days) "
                    "sebelum masa retur supplier roll hasil retur internal habis.",
     "kind": "daily", "hour": 7, "minute": 30, "fn": _supplier_deadline_job, "link": "interco-transactions"},
    {"id": "export_schedule_dispatch", "label": "Export Terjadwal (Pusat Export)",
     "description": "Menjalankan template export yang dijadwalkan mingguan/bulanan dengan hak akses pemilik saat itu; "
                    "file siap diunduh di Pusat Export → Pekerjaan dan pemilik diberi notifikasi.",
     "kind": "interval", "interval_minutes": 5, "fn": _expsched.job_export_schedule_dispatch, "link": "export-center"},
    # ── KP-T1 — status PKP bertanggal berlaku (KP-02) ─────────────────────────────────────────────────────
    {"id": "entity_tax_status_due", "label": "Terapkan Perubahan Status PKP Terjadwal",
     "description": "Perubahan status PKP badan usaha yang dijadwalkan (Pengaturan › Badan Usaha › Ubah status PKP) "
                    "diterapkan pada tanggal berlakunya: status berubah, riwayat bertambah, jadwal dihapus. Dokumen "
                    "yang sudah ada tidak dihitung ulang. Idempoten — juga dijalankan saat aplikasi menyala.",
     "kind": "daily", "hour": 0, "minute": 5, "fn": _entity_tax_status_job, "link": "entities-access"},
    {"id": "ai_anomaly_scan", "label": "Peringatan Anomali Tanya KN",
     "description": "Tiap pagi memindai penjualan turun per sales, piutang mulai macet, stok yang akan habis, dan PO "
                    "supplier terlambat; hasilnya tampil di tab Peringatan Tanya KN dan dikirim ke lonceng. Tanpa biaya AI.",
     "kind": "daily", "hour": 7, "minute": 0, "fn": _aiins.job_ai_anomaly_scan, "link": "tanya-kn"},
    # ── KF-T3 (KF-09) — dulu nilai berjadwal hanya disalin ke penyimpanan lama saat layar Pengaturan dibuka ──
    {"id": "config_apply_due", "label": "Aktifkan Pengaturan Terjadwal",
     "description": "Menerapkan perubahan pengaturan yang tanggal berlakunya sudah tiba.",
     "kind": "interval", "interval_minutes": 5, "fn": _cfgres.job_config_apply_due, "link": "settings-config"},
]
JOB_MAP: Dict[str, Dict[str, Any]] = {j["id"]: j for j in JOBS}


def job_defaults(job: Dict[str, Any]) -> Dict[str, Any]:
    if job["kind"] == "daily":
        return {"enabled": True, "hour": job["hour"], "minute": job["minute"]}
    if job.get("interval_minutes"):
        return {"enabled": True, "interval_minutes": job["interval_minutes"]}
    return {"enabled": True, "interval_hours": job["interval_hours"]}


# ── KP-T7 (KP-09) — satuan selang per job, job teknis terkunci, penerima & ambang tiap pengingat ─────────────────────
# Dulu pemicu memilih `interval_minutes` lebih dulu dan nilai itu selalu ada dari bawaan job, sehingga `interval_hours`
# yang dikirim layar untuk job bersatuan menit tersimpan tetapi tidak pernah dipakai. Kini satuan job menentukan field.
#: Job gerbang RFID: selangnya tidak diubah dari layar (titik henti H7 — ASUMSI spesifikasi KP-T7). Perilaku job tetap.
LOCKED_JOBS = ("rfid_reader_health_watch", "rfid_gate_txn_retry")

#: Pengingat (`reminder_policy.PENGINGAT`) yang dikirim tiap job → kolom "Penerima".
JOB_REMINDERS: Dict[str, tuple] = {
    "ar_overdue": ("ar_overdue",), "ap_due": ("ap_due",), "depreciation_due": ("depreciation_due",),
    "budget_alert": ("budget_alert",), "production_stalled": ("production_stalled",), "ops_stalled": ("ops_stalled",),
    "po_arrival": ("po_arrival", "po_arrival_gudang"), "backorder_ready": ("backorder_ready",),
    "ar_due_soon": ("ar_due_soon",),
}
#: Kunci pengaturan yang menjadi ambang tiap job → kolom "Ambang" (kunci yang tidak terdaftar dilewati).
JOB_THRESHOLDS: Dict[str, tuple] = {
    "ar_overdue": ("notif.max_alerts_per_run",),
    "ap_due": ("notif.ap_due_soon_days", "notif.max_alerts_per_run"),
    "budget_alert": ("notif.max_alerts_per_run",),
    "production_stalled": ("notif.wo_released_stale_days", "notif.wo_draft_stale_days", "notif.max_alerts_per_run"),
    "ops_stalled": ("notif.warehouse_task_stale_days",),
    "po_arrival": ("notif.po_arrival_lookback_hours", "notif.max_alerts_per_run"),
    "backorder_ready": ("notif.max_alerts_per_run",),
    "ar_due_soon": ("notif.ar_due_soon_offsets", "notif.max_alerts_per_run"),
    "escalation_scan": ("notif.max_alerts_per_run",),
    "content_reminder": ("notif.content_reminder_window_minutes",),
    "turn_scan": ("notif.turn_stale_days",),
    "printer_stuck_watch": ("notif.printer_stuck_minutes",),
    "inventory_drift_watch": ("inventory.drift_alert_rupiah", "inventory.drift_critical_multiplier"),
    "approval_backlog_reminder": ("approval.reminder_min_days", "approval.reminder_max_listed"),
    "saga_lock_watch": ("saga.stuck_lock_minutes",),
    "rnd_sla_escalation": ("rnd.sla_escalate_admin_days",),
    "interco_settlement_reminder": ("antar_entitas.settlement_reminder_days",),
    "period_unlock_auto_close": ("periode.unlock_window_hours",),
    "return_supplier_deadline_reminder": ("returns.supplier_reminder_days",),
    "interco_payment_reminder": ("interco_payment.reminder_days",),
    "contra_bon_reminder": ("contra_bon.reminder_days_before",),
}


def interval_unit(job: Dict[str, Any]) -> str:
    """"menit" bila bawaan job `interval_minutes`, "jam" untuk job berselang lain, "" untuk job harian."""
    if job["kind"] == "daily":
        return ""
    return "menit" if job.get("interval_minutes") else "jam"


def interval_value(job: Dict[str, Any], cfg: Dict[str, Any]) -> Optional[int]:
    """Selang yang DIPAKAI pemicu (satuan `interval_unit`); None untuk job harian."""
    unit = interval_unit(job)
    if unit == "menit":
        return int(cfg.get("interval_minutes") or job["interval_minutes"])
    if unit == "jam":
        return int(cfg.get("interval_hours") or job.get("interval_hours") or 4)
    return None


def job_patch_error(job: Dict[str, Any], patch: Dict[str, Any]) -> str:
    """Pesan 400 bila selang yang dikirim tidak cocok dengan satuan job ("" = sah)."""
    menit, jam = patch.get("interval_minutes") is not None, patch.get("interval_hours") is not None
    if not (menit or jam):
        return ""
    label = job["label"]
    if job["id"] in LOCKED_JOBS:
        return f"Jadwal “{label}” tidak bisa diubah dari layar."
    unit = interval_unit(job)
    if not unit:
        return f"Jadwal “{label}” diatur dengan jam dan menit harian."
    if unit == "menit" and jam:
        return f"Jadwal “{label}” diatur dalam menit."
    if unit == "jam" and menit:
        return f"Jadwal “{label}” diatur dalam jam."
    return ""


def _teks_ambang(key: str, entry: Dict[str, Any], value: Any) -> str:
    unit = entry.get("unit") or ""
    if key == "notif.ar_due_soon_offsets":
        return ", ".join(("H" if int(o) == 0 else f"H{int(o):+d}") for o in (value or [])) or "tidak ada"
    if entry.get("type") == "money":
        return "Rp" + f"{float(value or 0):,.0f}".replace(",", ".")
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return f"{value} {unit}".strip()


async def job_policy(job_id: str, entity_id: str) -> Dict[str, Any]:
    """`recipients` (ringkasan penerima efektif) + `thresholds` (`[{key, label, value, unit, text, group}]`) untuk PT
    `entity_id` ("" = nilai grup)."""
    import config_registry as registry
    from services import reminder_policy
    reminders = JOB_REMINDERS.get(job_id) or ()
    recipients = await reminder_policy.ringkasan_penerima(reminders, entity_id) if reminders else ""
    thresholds: List[Dict[str, Any]] = []
    for key in JOB_THRESHOLDS.get(job_id) or ():
        entry = registry.get(key)
        if not entry or entry.get("status") != "active":
            continue
        value = await reminder_policy.threshold(key, entity_id)
        thresholds.append({"key": key, "label": entry["label"], "value": value, "unit": entry.get("unit") or "",
                           "text": _teks_ambang(key, entry, value), "group": entry["group"]})
    return {"recipients": recipients, "recipient_key": reminder_policy.KUNCI_PENERIMA if reminders else "",
            "thresholds": thresholds}


async def effective_config() -> Dict[str, Dict[str, Any]]:
    """Gabungan default kode + override tersimpan (per job)."""
    st = await wa.raw_settings()
    saved = st.get("jobs") or {}
    out: Dict[str, Dict[str, Any]] = {}
    for job in JOBS:
        cfg = {**job_defaults(job), **(saved.get(job["id"]) or {})}
        out[job["id"]] = cfg
    return out


def schedule_label(job: Dict[str, Any], cfg: Dict[str, Any]) -> str:
    if job["kind"] == "daily":
        return f"Harian {int(cfg.get('hour', 0)):02d}:{int(cfg.get('minute', 0)):02d} WIB"
    # KP-T7 — label = selang yang dipakai pemicu, menurut satuan job
    return f"Setiap {interval_value(job, cfg)} {interval_unit(job)}"


# ═══ Histori eksekusi ═══════════════════════════════════════════════════════
async def run_job(job_id: str, trigger: str = "schedule",
                  actor: str = "System") -> Dict[str, Any]:
    """Jalankan 1 job + catat histori. Tidak pernah raise (kecuali job_id tak dikenal)."""
    job = JOB_MAP.get(job_id)
    if not job:
        raise ValueError(f"Job '{job_id}' tidak dikenal.")
    started = time.perf_counter()
    doc: Dict[str, Any] = {
        "id": new_id("srun"), "job_id": job_id, "job_label": job["label"],
        "trigger": trigger, "actor": actor, "started_at": now_iso(),
        "status": "running", "created": 0, "scanned": 0, "wa_queued": 0,
        "detail": "", "error": "", "duration_ms": 0, "finished_at": "",
    }
    wa_before = await db.sys_wa_outbox.count_documents({})
    try:
        res = await job["fn"]()
        wa_after = await db.sys_wa_outbox.count_documents({})
        doc.update({
            "status": "success",
            "created": int(res.get("created", 0) or 0),
            "scanned": int(res.get("scanned", 0) or 0),
            "detail": str(res.get("detail", "") or ""),
            "wa_queued": max(0, wa_after - wa_before),
        })
    except Exception as exc:  # noqa: BLE001 — job gagal tidak boleh mematikan scheduler
        logger.warning("[scheduler] job %s gagal: %s", job_id, exc)
        doc.update({"status": "failed", "error": str(exc)})
    doc["duration_ms"] = int((time.perf_counter() - started) * 1000)
    doc["finished_at"] = now_iso()
    await db.sys_scheduler_runs.insert_one(dict(doc))
    return doc


async def last_runs() -> Dict[str, Dict[str, Any]]:
    """Run terakhir per job (untuk kolom 'Terakhir jalan')."""
    out: Dict[str, Dict[str, Any]] = {}
    for job in JOBS:
        row = await db.sys_scheduler_runs.find_one(
            {"job_id": job["id"]}, {"_id": 0}, sort=[("started_at", -1)])
        if row:
            out[job["id"]] = row
    return out


async def runs_history(job_id: Optional[str] = None, limit: int = 60) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if job_id:
        q["job_id"] = job_id
    return await db.sys_scheduler_runs.find(q, {"_id": 0}).sort("started_at", -1).to_list(int(limit))


# ═══ Lock single-instance ═════════════════════════════════════════════════
def _epoch() -> float:
    return datetime.now(timezone.utc).timestamp()


def _owner_alive(owner: str) -> bool:
    """Apakah proses pemegang lock masih hidup?

    Uvicorn `--reload` mematikan worker lama tanpa membersihkan lock, sehingga
    heartbeat bisa terlihat "segar" padahal prosesnya sudah tidak ada → scheduler
    tidak pernah menyala lagi. Untuk owner di NODE INI kita cek `/proc/<pid>`;
    owner dari node lain dianggap hidup (hanya TTL heartbeat yang berlaku).
    """
    try:
        node, pid = str(owner).rsplit(":", 1)
    except ValueError:
        return True
    if node != os.uname().nodename:
        return True
    return os.path.exists(f"/proc/{pid}")


async def _try_acquire_lock() -> bool:
    doc = await db.system_settings.find_one({"scope": SETTINGS_SCOPE}, {"_id": 0, "lock": 1}) or {}
    lock = doc.get("lock") or {}
    fresh = (_epoch() - float(lock.get("heartbeat", 0) or 0)) < LOCK_TTL_SECONDS
    owner = lock.get("owner") or ""
    if fresh and owner != _OWNER and _owner_alive(owner):
        logger.info("[scheduler] lock dipegang %s — instance ini tidak menjadwalkan job.",
                    owner)
        return False
    if fresh and owner != _OWNER:
        # Heartbeat masih segar tetapi PROSES pemegangnya sudah mati (mis. akibat
        # hot-reload uvicorn) → ambil alih sekarang, jangan tunggu TTL habis.
        logger.info("[scheduler] lock basi (proses %s mati) — diambil alih %s.", owner, _OWNER)
    await db.system_settings.update_one(
        {"scope": SETTINGS_SCOPE},
        {"$set": {"lock": {"owner": _OWNER, "heartbeat": _epoch(), "since": now_iso()}},
         "$setOnInsert": {"id": new_id("set"), "scope": SETTINGS_SCOPE,
                          "created_at": now_iso()}},
        upsert=True)
    return True


async def _heartbeat() -> None:
    await db.system_settings.update_one(
        {"scope": SETTINGS_SCOPE}, {"$set": {"lock.owner": _OWNER, "lock.heartbeat": _epoch()}})


# ═══ Start / reschedule ══════════════════════════════════════════════════
async def _apply_jobs() -> int:
    """(Re)daftarkan semua job sesuai konfigurasi efektif. Return jumlah job aktif."""
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    if _scheduler is None:
        return 0
    cfg_all = await effective_config()
    active = 0
    for job in JOBS:
        jid = job["id"]
        cfg = cfg_all[jid]
        try:
            _scheduler.remove_job(jid)
        except Exception as exc:  # noqa: BLE001 — belum terdaftar
            logger.warning("[_apply_jobs] efek samping gagal diabaikan: %s", exc)  # KN-C10
        if not cfg.get("enabled", True):
            continue
        if job["kind"] == "daily":
            trigger = CronTrigger(hour=int(cfg.get("hour", 8)),
                                  minute=int(cfg.get("minute", 0)), timezone=TZ)
        elif interval_unit(job) == "menit":   # KP-T7 — satuan job menentukan field yang dipakai
            trigger = IntervalTrigger(minutes=interval_value(job, cfg), timezone=TZ)
        else:
            trigger = IntervalTrigger(hours=interval_value(job, cfg), timezone=TZ)
        _scheduler.add_job(run_job, trigger=trigger, id=jid, args=[jid],
                           kwargs={"trigger": "schedule"}, replace_existing=True,
                           max_instances=1, coalesce=True, misfire_grace_time=3600)
        active += 1
    return active


async def _boot_scheduler() -> Dict[str, Any]:
    """Buat & jalankan AsyncIOScheduler (dipakai saat startup maupun saat ambil-alih lock)."""
    global _scheduler
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    _scheduler = AsyncIOScheduler(timezone=TZ)
    active = await _apply_jobs()
    _scheduler.add_job(_heartbeat, trigger=IntervalTrigger(seconds=HEARTBEAT_SECONDS),
                       id="__heartbeat__", replace_existing=True, max_instances=1)
    _scheduler.start()
    logger.info("[scheduler] aktif (%s job) zona %s · owner=%s", active, TZ, _OWNER)
    return {"started": True, "jobs": active, "timezone": TZ, "owner": _OWNER}


async def _lock_retry_loop() -> None:
    """Coba ambil-alih lock berkala sampai scheduler benar-benar menyala.

    Tanpa loop ini, satu kali gagal ambil lock (mis. worker lama baru mati) membuat
    scheduler MATI PERMANEN sampai service di-restart manual.
    """
    global _owns_lock
    while True:
        await asyncio.sleep(LOCK_RETRY_SECONDS)
        if _scheduler is not None and _scheduler.running:
            return
        try:
            if await _try_acquire_lock():
                _owns_lock = True
                await _boot_scheduler()
                return
        except Exception as exc:  # noqa: BLE001 — retry berikutnya
            logger.warning("[scheduler] retry lock gagal: %s", exc)


async def start_scheduler() -> Dict[str, Any]:
    """Dipanggil dari lifespan server. Aman bila dipanggil ulang (idempotent)."""
    global _scheduler, _owns_lock
    if _scheduler is not None and _scheduler.running:
        return {"started": True, "already": True, "owner": _OWNER}
    if os.environ.get("KN_DISABLE_SCHEDULER") == "1":
        logger.info("[scheduler] dinonaktifkan via KN_DISABLE_SCHEDULER=1")
        return {"started": False, "reason": "disabled_by_env"}
    _owns_lock = await _try_acquire_lock()
    if not _owns_lock:
        asyncio.create_task(_lock_retry_loop())  # noqa: RUF006 — task siklus hidup app
        return {"started": False, "reason": "lock_held_by_other",
                "retry_in_seconds": LOCK_RETRY_SECONDS}
    return await _boot_scheduler()


async def reschedule() -> Dict[str, Any]:
    """Terapkan ulang jadwal setelah pengaturan diubah user."""
    if _scheduler is None or not _scheduler.running:
        return {"rescheduled": False, "reason": "scheduler_not_running"}
    active = await _apply_jobs()
    return {"rescheduled": True, "jobs": active}


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        try:
            _scheduler.shutdown(wait=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[shutdown] efek samping gagal diabaikan: %s", exc)  # KN-C10
    _scheduler = None


def _next_run(job_id: str) -> str:
    if _scheduler is None:
        return ""
    try:
        j = _scheduler.get_job(job_id)
    except Exception:  # noqa: BLE001
        return ""
    if not j or not getattr(j, "next_run_time", None):
        return ""
    return j.next_run_time.isoformat()


async def jobs_status(entity_id: str = "") -> Dict[str, Any]:
    """Status lengkap untuk UI admin: jadwal, on/off, run terakhir, run berikutnya.

    KP-T7 — `entity_id` = PT aktif layar ("" = nilai grup) untuk ringkasan penerima & ambang."""
    cfg_all = await effective_config()
    lasts = await last_runs()
    rows: List[Dict[str, Any]] = []
    for job in JOBS:
        jid = job["id"]
        cfg = cfg_all[jid]
        last = lasts.get(jid) or {}
        rows.append({
            "id": jid, "label": job["label"], "description": job["description"],
            "kind": job["kind"], "link": job.get("link", ""),
            "enabled": bool(cfg.get("enabled", True)),
            "hour": cfg.get("hour"), "minute": cfg.get("minute"),
            "interval_hours": cfg.get("interval_hours"),
            # KP-T7 — satuan + selang yang DIPAKAI pemicu, kunci job teknis, penerima & ambang untuk PT aktif
            "interval_unit": interval_unit(job), "interval_value": interval_value(job, cfg),
            "locked": jid in LOCKED_JOBS, **(await job_policy(jid, entity_id)),
            "schedule_label": schedule_label(job, cfg),
            "next_run": _next_run(jid),
            "last_run_at": last.get("started_at", ""),
            "last_status": last.get("status", ""),
            "last_created": last.get("created", 0),
            "last_detail": last.get("detail", ""),
            "last_error": last.get("error", ""),
            "last_duration_ms": last.get("duration_ms", 0),
        })
    return {
        "running": bool(_scheduler is not None and _scheduler.running),
        "owner": _OWNER if _owns_lock else "",
        "timezone": TZ,
        "jobs": rows,
        "generated_at": now_iso(),
    }


async def summary() -> Dict[str, Any]:
    """KPI ringkas untuk header view admin."""
    day = now_iso()[:10]
    runs_today = await db.sys_scheduler_runs.count_documents({"started_at": {"$gte": day}})
    failed_today = await db.sys_scheduler_runs.count_documents(
        {"started_at": {"$gte": day}, "status": "failed"})
    notif_today = await db.notifications.count_documents({"created_at": {"$gte": day}})
    unread = await db.notifications.count_documents(
        {"read": {"$ne": True}, "read_by.0": {"$exists": False}})
    cfg_all = await effective_config()
    enabled = sum(1 for c in cfg_all.values() if c.get("enabled", True))
    return {
        "jobs_total": len(JOBS), "jobs_enabled": enabled,
        "runs_today": runs_today, "failed_today": failed_today,
        "notifications_today": notif_today, "notifications_unread": unread,
        "wa": await wa.outbox_stats(),
        "delivery_mode": (await wa.raw_settings())["wa"].get("delivery_mode", "instant"),
        "escalation": await escalation.escalation_stats(),
        "running": bool(_scheduler is not None and _scheduler.running),
        "generated_at": now_iso(),
    }


async def run_all(trigger: str = "manual", actor: str = "System") -> Dict[str, Any]:
    """Jalankan SEMUA job aktif berurutan (tombol 'Jalankan Semua')."""
    cfg_all = await effective_config()
    results = []
    for job in JOBS:
        if not cfg_all[job["id"]].get("enabled", True):
            continue
        results.append(await run_job(job["id"], trigger=trigger, actor=actor))
        await asyncio.sleep(0)  # beri ruang event loop
    return {"runs": results, "created": sum(r.get("created", 0) for r in results),
            "failed": sum(1 for r in results if r.get("status") == "failed")}
