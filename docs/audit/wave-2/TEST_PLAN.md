# Menjalankan reproduksi dan regression

## Lingkungan

Python3.12 dan MongoDB8.0.12 dipakai saat audit. Daftar versi historis di baseline/repro/historical-environment-dependencies.json adalah referensi, bukan lockfile deployment atau jaminan lintas platform. Gunakan environment terisolasi yang kompatibel dengan backend kandidat, dependency repo dan httpx/Motor; catat versi aktual dan setiap penyesuaian. Paket tidak menyertakan Python, Mongo, wheel atau source aplikasi.

Mongo lokal dedicated harus bind127.0.0.1 port27919. Harness membuat DB knhost_audit_<uuid>, menonaktifkan dotenv dan memblokir outbound socket; tidak menjalankan lifespan/scheduler. Baca harness sebelum replay. Jangan mengarahkannya ke data nyata. Tidak ada cleanup otomatis; hapus DB sintetis hanya setelah bukti disimpan dan target diverifikasi.

## Urutan aman terhadap bukti

Dari root repo:

```text
python docs/audit/wave-2/tools/check_package.py
python docs/audit/wave-2/tools/prepare_iteration.py --name P01-001
```

Perintah kedua menyalin baseline ke iterations/P01-001/replay/; target yang sudah ada ditolak. Semua relative output reproducer tetap berada pada salinan ini. Set KNHOST_REPO ke path absolut checkout kandidat, bukan path folder audit.

PowerShell:

```powershell
$env:KNHOST_REPO = (Get-Location).Path
python docs/audit/wave-2/iterations/P01-001/replay/repro/wave2_rnd_line_scope.py
```

POSIX:

```sh
export KNHOST_REPO="$PWD"
python docs/audit/wave-2/iterations/P01-001/replay/repro/wave2_rnd_line_scope.py
```

Simpan log/exit code. Jangan menjalankan seluruh harness sekaligus: beberapa dataset besar, dan helper/fixture mempunyai dependensi impor. Setelah bukti sebelum perubahan disimpan, pakai iterasi/nama baru untuk hasil sesudah perubahan. Regression dengan expected benar ditempatkan di tests repo atau iterasi; catat perbedaan dari harness lama. Kegagalan assertion bug lama pada kandidat fixed harus dianalisis, bukan dihitung sebagai kegagalan produk tanpa membaca state.

## Cakupan per fase

|Fase|Harness utama dan kontrol|
|---|---|
|P01|wave2_count, wave2_transfer, wave2_rfid, validate_w2_rfid, wave2_rnd_line_scope|
|P02|wave2_count, wave2_transfer, wave2_projection, wave2_grn_partial/capacity/recovery, wave2_qc_flow, wave2_multi_po, wave2_wms_uom|
|P03|wave2_makloon, wave2_claim_payment; perluas full GRN HTTP partial/multi-gudang|
|P04|wave2_production_flow/recovery/capacity|
|P05|wave2_ar, wave2_cash_refund, wave2_advance, wave2_sales_flow|
|P06|wave2_gl_capacity/close, wave2_bank_flow, wave2_payroll_flow|
|P07|wave2_rfid, validate_w2_rfid; rig fisik terpisah|
|P08|client_requirements_probes sebagai penjelasan; tambah lifecycle/UAT sesuai memo dan prompt27|
|P09|Regression terintegrasi dan oracle subledger/GL, browser/hardware; bukan replay semua script saja|

Nama pada tabel tanpa ekstensi memakai .py di replay/repro. Reproducer memakai fixture sintetis tertentu; jangan menganggap ia menguji semua permission, pajak, UI atau hardware. Acceptance tambahan dan batas n-1/n/n+1 tercantum pada prompt tiap fase. check_package hanya memeriksa kelengkapan/integritas dokumentasi, bukan hasil aplikasi.
