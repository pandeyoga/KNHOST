# Integrasi dengan Development Plan 35 IMP

Paket utama P00–P10 dan 35 IMP tetap berlaku. Addendum ini menambah adapter/API hardware, bukan mengganti model stok atau mengubah fingerprint P09 menjadi RFID.

| Plan utama | Hubungan RFID |
|---|---|
| P00 | Bersama RF00: baseline repo dan PoC hardware. |
| P01 / IMP-20 | Scope user-site, owner, device dan task operator menjadi fondasi RF01. |
| P02 / IMP-22–25 | C72 putaway dan gate memakai resolver/status/rules/owner yang sama. |
| RF-P / CP30EN | Print job dan encoding ditelusuri ke roll, gudang, tag, attempt, hasil item dan verifikasi C72; label tidak menambah stok. |
| P03 / IMP-21,26,27 | Gate membandingkan movement; actual receipt tidak diposting hanya karena tag terbaca. |
| P04 / IMP-05,06 | Loading C72 mengikuti alokasi roll dan quantity/doc yang sah. |
| P08 / IMP-01,28,29 | Opname RFID dan device health/exception terhubung ke meja, dashboard, dan adjustment berapproval. |
| P09 | Fingerprint tetap memakai protokol kehadiran; SDK UHF Chainway tidak otomatis menggantikannya. |
| P10 | Tambahkan gate RF04: UAT nyata CP30EN + C72 + UR300 pada versi ERP dan middleware yang cocok. |

Status utama tetap di BACKLOG.json paket utama; status lima belas kebutuhan hardware berada di RFID_BACKLOG.json addendum. Keduanya mempunyai identitas berbeda dan tidak memuat counter status requirement yang sama. P10 tidak ditutup sampai RF04 yang mencakup printer tervalidasi. Validator utama hanya menghitung 35 IMP; laporan P10 melampirkan tracker/evidence addendum sebagai gate eksternal.

Jika aplikasi middleware sudah ada di repo terpisah/vendor, catat repo/build/kontrak/SDK dan evaluasi kecocokannya; jangan membangun ulang tanpa pemeriksaan. Semua perubahan task/operator/device harus terintegrasi ke SSOT ERP.
