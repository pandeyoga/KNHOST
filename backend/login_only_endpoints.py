"""PR-T3 — daftar endpoint yang SAH cukup dengan login (standar `docs/blueprint/02_STANDAR.md` §3.1 Z3).

Selain endpoint di sini, setiap rute ber-sesi wajib memanggil `require_permission` / `require_any_permission` sebagai
pernyataan pertama handler (Z1). Kunci = (metode, jalur persis seperti `server.app.routes`), nilai = alasan:

* ``milik_sendiri`` — hanya data milik pengguna itu (jalur `/me`, `/mine`, atau disaring `user_id` aktor);
* ``rujukan``       — data rujukan tanpa nominal (wilayah, enum, daftar peran, termin, nama PT) atau isi yang sudah
                      disaring izin modul di dalam handler;
* ``sesi``          — infrastruktur sesi (siapa saya, konteks PT aktif, kunci publik notifikasi dorong).

Isi = 53 baris berputusan "Tetap" di tabel A `docs/blueprint/unit/PR-T3.md`, + 1 baris PR-T5 (`GET /api/access/labels`),
+ 6 baris PR-T8b (temuan penjaga matriks T8-01…T8-05: perilakunya sudah benar, putusannya belum tertulis). Endpoint yang
ditangani unit lain (PR-T2 asisten, KF-T1 Pusat Pengaturan, KP-T4 persetujuan, PK-17 beranda, PR-T4 meja kerja)
ditambahkan atau tidak oleh unit itu. Dibaca penjaga matriks (unit PR-T8): rute login-saja di luar daftar ini = merah.
Uji: `backend/tests_mem/test_PRT3_login_saja.py::test_PRT3_U13_daftar_login_only_menunjuk_rute`,
`backend/tests_mem/test_PRT8b_gerbang_pertama.py::test_PRT8b_U8_login_saja_tertulis`.
"""
from typing import Dict, Tuple

MILIK_SENDIRI = "milik_sendiri"
RUJUKAN = "rujukan"
SESI = "sesi"

LOGIN_ONLY: Dict[Tuple[str, str], str] = {
    # ── Infrastruktur sesi ──────────────────────────────────────────────────
    ("GET", "/api/auth/me"): SESI,
    ("GET", "/api/auth/context"): SESI,
    ("GET", "/api/push/public-key"): SESI,
    # PR-T8b (T8-03) — dua bendera izin pemanggil sendiri (`interco_price.view` / `.set`) untuk menampilkan tombol.
    ("GET", "/api/interco/prices/access"): SESI,
    # ── Data rujukan ────────────────────────────────────────────────────────
    ("GET", "/api/roles"): RUJUKAN,                      # label, lintas PT, beranda; tanpa nominal
    ("GET", "/api/documents/resolve"): RUJUKAN,          # jenis dokumen disaring izin modul (`_may_view`)
    ("GET", "/api/entities"): RUJUKAN,                   # tanpa `entity.view` hanya kunci rujukan (S2)
    ("GET", "/api/enums"): RUJUKAN,
    ("GET", "/api/enums/stage-transitions"): RUJUKAN,
    ("POST", "/api/enums/stage-transitions/validate"): RUJUKAN,
    ("POST", "/api/enums/products/validate"): RUJUKAN,
    ("GET", "/api/enums/{name}"): RUJUKAN,
    ("GET", "/api/master/fabric-types"): RUJUKAN,
    ("GET", "/api/payment-terms"): RUJUKAN,              # kode, nama, dan hari termin
    ("GET", "/api/finance/period-unlocks/active"): RUJUKAN,   # pemberitahuan tanpa nominal, terbatas PT pengguna
    ("GET", "/api/access/labels"): RUJUKAN,              # PR-T5 — kamus label sumber daya, aksi, modul
    # PR-T8b (T8-01) — dipanggil sekali untuk seluruh aplikasi; tiap bagian (pesanan, pelanggan, produk, gudang, angka
    # stok) diisi hanya bila peran memegang izin lihatnya, bagian lain kosong/0 dan kuerinya tidak jalan (PR-T3 S1).
    ("GET", "/api/dashboard"): RUJUKAN,
    ("GET", "/api/wilayah/countries"): RUJUKAN,
    ("GET", "/api/wilayah/provinces"): RUJUKAN,
    ("GET", "/api/wilayah/regencies"): RUJUKAN,
    ("GET", "/api/wilayah/districts"): RUJUKAN,
    ("GET", "/api/wilayah/villages"): RUJUKAN,
    ("GET", "/api/wilayah/postal-code/{code}"): RUJUKAN,
    ("GET", "/api/wilayah/search"): RUJUKAN,
    ("POST", "/api/wilayah/validate"): RUJUKAN,
    # ── Milik sendiri ───────────────────────────────────────────────────────
    ("GET", "/api/hr/employees/me"): MILIK_SENDIRI,
    ("GET", "/api/hr/attendance/me"): MILIK_SENDIRI,
    ("POST", "/api/hr/attendance/clock-in"): MILIK_SENDIRI,
    ("POST", "/api/hr/attendance/clock-out"): MILIK_SENDIRI,
    ("GET", "/api/hr/kpi/me"): MILIK_SENDIRI,
    ("GET", "/api/hr/leave-requests/me"): MILIK_SENDIRI,
    ("POST", "/api/hr/leave-requests/me"): MILIK_SENDIRI,
    ("GET", "/api/hr/leave-balance/me"): MILIK_SENDIRI,
    ("GET", "/api/hr/overtime/me"): MILIK_SENDIRI,
    ("POST", "/api/hr/overtime/me"): MILIK_SENDIRI,
    ("GET", "/api/hr/payslips/me"): MILIK_SENDIRI,
    ("POST", "/api/hr/field-tracks"): MILIK_SENDIRI,
    ("GET", "/api/hr/visits/me"): MILIK_SENDIRI,
    ("GET", "/api/hr/visits/mine"): MILIK_SENDIRI,
    ("POST", "/api/hr/visits/check-in"): MILIK_SENDIRI,
    ("POST", "/api/hr/visits/{visit_id}/check-out"): MILIK_SENDIRI,
    ("GET", "/api/notifications"): MILIK_SENDIRI,
    ("GET", "/api/notifications/unread-count"): MILIK_SENDIRI,
    ("POST", "/api/notifications/read-all"): MILIK_SENDIRI,
    ("POST", "/api/notifications/{notification_id}/read"): MILIK_SENDIRI,
    ("GET", "/api/onboarding"): MILIK_SENDIRI,
    ("POST", "/api/onboarding/{task_id}/complete"): MILIK_SENDIRI,
    ("POST", "/api/onboarding/reset"): MILIK_SENDIRI,
    ("POST", "/api/push/subscribe"): MILIK_SENDIRI,      # langganan perangkat pengguna
    ("POST", "/api/push/unsubscribe"): MILIK_SENDIRI,
    ("GET", "/api/push/status"): MILIK_SENDIRI,
    ("POST", "/api/push/test"): MILIK_SENDIRI,
    ("GET", "/api/rnd/reports/my-kpi"): MILIK_SENDIRI,
    ("GET", "/api/stock/my-site"): MILIK_SENDIRI,
    ("PUT", "/api/stock/my-site"): MILIK_SENDIRI,
    ("GET", "/api/location-scope"): MILIK_SENDIRI,       # lokasi kerja pengguna
    # PR-T8b (T8-02) — boleh-tidaknya PEMANGGIL memutus (KP-T4): tanpa izin setujui → `allowed: false` + kalimat Z6;
    # nominal berasal dari pemanggil sendiri, jawabannya tidak memuat data dokumen.
    ("GET", "/api/approval-policies/can-decide/me"): MILIK_SENDIRI,
    # PR-T8b (T8-04) — slip milik karyawan yang tertaut ke akun, atau pemegang `hr.view` (`_can_view_slip`, diperiksa
    # sesudah slip dimuat); selain itu 403.
    ("GET", "/api/hr/payslips/{slip_id}"): MILIK_SENDIRI,
    ("GET", "/api/hr/payslips/{slip_id}/pdf"): MILIK_SENDIRI,
    # PR-T8b (T8-05) — pengaju membatalkan cutinya sendiri; selain pengaju wajib `hr.manage_attendance` (diperiksa
    # sesudah pengajuan dimuat).
    ("POST", "/api/hr/leave-requests/{leave_id}/cancel"): MILIK_SENDIRI,
}
