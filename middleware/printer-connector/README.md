# KN Printer Connector — printer label RFID Chainway CP30EN (PREP-F)

Layanan kecil di **PC gudang** (Windows) yang menghubungkan ERP Kain Nusantara (VPS) dengan printer label RFID
**Chainway CP30EN** di LAN gudang. Ia menarik antrean cetak dari ERP memakai *device key* per printer, mengirim
ZPL ke printer lewat **TCP 9100**, membaca status/hasil printer, mencatat semuanya di **ledger SQLite lokal**, lalu
melaporkan **hasil per label** ke ERP.

> **Status: disiapkan TANPA perangkat.** Semua perintah RFID ZPL (`^RS`, `^RFW,H`, `^RFR`+`^HV`, `^RVE`) dan format
> balasan status (`~HS`, `~HQES`, `~HI`) diambil dari bahasa ZPL Zebra dan **belum terbukti di CP30EN**. Uji meja saat
> unit datang: lihat `docs/rfid/hasil/PREP-F-PRINTER-CP30EN.md` §"Daftar uji meja".

## Cara kerja (singkat)

```
ERP (VPS)  ⇄ HTTPS (X-Device-Key) ⇄  Connector di PC gudang  ⇄ TCP 9100 ⇄  CP30EN
                                       └ ledger SQLite per printer
```

Per label: **niat dicatat → ERP menerima "mulai" (start) → status "sedang dikirim" ditulis ke disk → ZPL dikirim →
connector menunggu printer selesai + balasan RFID → hasil dicatat → hasil dilaporkan ke ERP.**

Prinsip keselamatan:

- **Tidak ada cetak ulang otomatis.** Label yang sudah/sedang dikirim tetapi hasilnya tidak diketahui (timeout,
  koneksi putus, PC mati) dilaporkan **"tidak pasti"** dan diputuskan operator di ERP (*Tag RFID → Antrean Printer →
  Perlu tindak lanjut*), dengan bukti (pindai C72).
- **Tanpa izin ERP, tidak ada label baru dimulai** (start barrier). Bila internet gudang putus, antrean **tertahan**;
  hasil yang sudah ada tetap tersimpan di ledger dan dikirim saat tersambung lagi. (Sejalan dengan keputusan pemilik
  9 Nov 2026: tidak ada server lokal; perangkat tidak memutus sendiri tanpa server.)
- **Socket terkirim ≠ tercetak.** Sukses hanya bila printer selesai (buffer kosong, tanpa galat) DAN chip terbukti
  tertulis (baca balik EPC sama dengan ERP, atau laporan encode `+`). Selain itu → gagal / tidak pasti.
- **Satu worker per printer**, identitas (device key), ledger, dan kunci berkas sendiri. Dua connector pada printer
  yang sama ditolak (kunci berkas lokal + lease ERP per *instance*).
- Status **printer** (siap / kertas habis / kepala terbuka / tidak terjangkau) dilaporkan **terpisah** dari heartbeat
  **connector**.

## Kebutuhan

- Windows 10/11 64-bit, **Python 3.11** (64-bit) dari python.org — hanya pustaka standar, tidak ada `pip install`.
- PC dan printer di LAN yang sama; printer ber-IP tetap (DHCP reservation) dan port 9100 terbuka.
- PC bisa menjangkau ERP lewat HTTPS.
- (Untuk layanan) [NSSM](https://nssm.cc) atau Task Scheduler.

## Pasang

1. Salin folder `middleware/printer-connector` ke PC gudang, mis. `C:\KN\printer-connector`.
2. Di ERP (admin): **Perangkat RFID → tambah perangkat tipe `printer`** untuk tiap CP30EN (gudang yang benar), lalu
   **terbitkan API key**. Key **hanya tampil sekali** — catat langsung ke tempat aman.
3. Simpan key **di luar berkas konfigurasi**:
   - variabel lingkungan sistem, mis. `KN_PRN_RCM1_KEY` (NSSM: `AppEnvironmentExtra`), **atau**
   - berkas `keys\<nama-printer>.key` yang aksesnya dibatasi (klik kanan → Properties → Security: hanya
     SYSTEM + Administrators).
4. Buat `C:\ProgramData\KN-Printer-Connector\config.json` dari `config.example.json`:
   `erp_url`, dan per printer `name`, `host` (IP printer), `port` (9100), `device_key_env` / `device_key_file`.
5. Periksa tanpa mencetak:
   ```
   cd C:\KN\printer-connector
   python -m kn_printer_connector check --config C:\ProgramData\KN-Printer-Connector\config.json
   ```
   Hasil yang diharapkan: `ERP ok — device … profil 203 dpi 70.0×22.0 mm …` dan `printer: ready`.
6. Atur **profil printer** di ERP (*Tag RFID → Antrean Printer → Profil & kalibrasi*, admin): dpi 203/300, geser
   (offset), posisi inlay (`^RS`), laporan encode. Pratinjau label tampil langsung.

### Sebagai layanan Windows (NSSM, disarankan)

PowerShell *Run as Administrator* dari folder connector:

```
.\install\install-service-nssm.ps1 -Python "C:\Program Files\Python311\python.exe" -Nssm "C:\Tools\nssm.exe"
C:\Tools\nssm.exe set KNPrinterConnector AppEnvironmentExtra KN_PRN_RCM1_KEY=<key-printer>
Start-Service KNPrinterConnector
```

Layanan mulai otomatis saat PC menyala dan dimulai ulang bila berhenti. Saat dihentikan, connector menyelesaikan
pencatatan label yang sedang berjalan (maks 60 detik).

### Alternatif: Task Scheduler

Buat tugas "At startup", akun SYSTEM, *Run whether user is logged on or not*, aksi:
`C:\KN\printer-connector\install\run-connector.cmd` (atur `PYTHON` dan `KN_CONNECTOR_CONFIG` di berkas itu atau
di variabel lingkungan sistem). Skrip mengulang connector bila berhenti.

## Berkas & log

| Lokasi (bawaan `data_dir`) | Isi |
|---|---|
| `<data_dir>\<printer>\ledger.sqlite3` | ledger per printer (niat, start, kirim, hasil, laporan) — **jangan dihapus** saat update |
| `<data_dir>\<printer>\connector.lock` | kunci satu-instance |
| `<data_dir>\logs\connector.log` | log berotasi (5 MB × 10); device key disamarkan |

Lihat ringkasan ledger: `python -m kn_printer_connector ledger --config …`

## Operasi harian & gangguan

| Kejadian | Perilaku connector | Tindakan orang |
|---|---|---|
| Kertas/ribbon habis, kepala terbuka | label berikut tidak dimulai; status printer dilaporkan ke ERP; label yang sedang tertahan ditunggu sampai 10 menit | pasang media / tutup kepala — cetak lanjut sendiri |
| Printer mati / kabel LAN lepas | tidak ada label baru dimulai; label yang terputus di tengah → "tidak pasti" | nyalakan printer; tinjau label "tidak pasti" di ERP |
| Internet gudang putus | antrean tertahan; hasil disimpan lokal; dicoba ulang dengan jeda bertahap (maks 60 dtk) | tidak perlu apa-apa; cek internet cadangan |
| PC mati/restart di tengah cetak | saat hidup lagi: label yang terkirim tanpa hasil → "tidak pasti", **tidak dicetak ulang** | tinjau di ERP (pindai label dengan C72 bila ada) |
| Encode gagal (VOID) | label dilaporkan **gagal** | musnahkan label VOID; di ERP pilih *Cetak ulang dengan EPC baru* |
| Dua connector memakai key sama | connector kedua tidak mendapat job; ERP menandai konflik | matikan salah satu |

**Cetak ulang teks** (teks rusak, chip baik) dan **ganti tag** (EPC baru) dibuat di ERP; connector hanya menjalankan
job yang diterbitkan ERP — ia tidak pernah membuat EPC atau memutuskan cetak ulang sendiri.

## Simulator printer (tanpa perangkat)

```
python simulator/zpl_printer_sim.py --port 9100 --encode-fail 3,6 --paper-out-after 5
```

Lalu arahkan `host` printer di config ke `127.0.0.1`. Gangguan lain: `--hang 9` (label macet), `--drop-at 4`
(koneksi putus), `--duplicate-results`. Simulator meniru bahasa ZPL, **bukan** bukti perilaku CP30EN.

## Uji

```
python -m pytest -q tests                 # connector + simulator + ERP tiruan (tanpa backend)
```
Uji ujung-ke-ujung dengan ERP sungguhan: `backend/tests/test_prep_f_connector_e2e.py` (jalankan di kontainer backend).

## Update & copot

- Update: hentikan layanan, ganti folder kode, **biarkan `data_dir`** (ledger) apa adanya, jalankan lagi.
- Copot: `nssm remove KNPrinterConnector confirm`. Simpan `data_dir` bila masih ada hasil yang belum terlapor
  (`ledger` → `pending_results` harus 0).
