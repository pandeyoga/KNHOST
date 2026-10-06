# Pengujian dan adjudikasi hasil

Kandidat terbaru `a904d989b622f7da14c4892d03cf6ef0c43f3084`: **1539 pass, 484 fail, 76 skip, 173 error**, 2272 testcase records. Pengujian berlangsung pada DB lokal dan assertion asli dipertahankan. Copy tes mengadaptasi path Linux, API localhost, lokasi ROOT dan env database; manifest perubahan tersedia pada evidence. Dua modul dengan side effect saat import—`test_wilayah_extra.py` dan `test_notifications_iter33.py`—dikecualikan dan bukan diberi status pass.

## Seluruh nonpass full pytest

| Petunjuk traceback otomatis | Jumlah |
|---|---|
| `assertion_or_contract_needs_review` | 335 |
| `fixture_credentials_or_auth_contract` | 59 |
| `fixture_or_upstream_precondition_needs_review` | 88 |
| `harness_environment_or_collection` | 15 |
| `async_fixture_loop` | 85 |
| `fixture_login_rate_limit` | 75 |

Klasifikasi di atas adalah petunjuk, bukan pembuktian manual seluruh 657 kasus. Semua testcase dan traceback ada pada `latest/evidence/pytest-triage-register.csv` dan XML. Fixture shared/event-loop Motor, rate limit login, akun/permission lama dan hardcoded data ikut memengaruhi suite. Jangan mengganti expected, memperlemah guard atau menyatakan semua nonpass sebagai bug.

## Tes yang ditambahkan patch terbaru

Tiga modul baru menghasilkan 14 pass/3 fail/5 skip. Tiga failure terkait populasi lot demo: ekspektasi 34 versus aktual 29 dan distribusi BTK 13 versus 8/status karantina. Fixture bukan dataset yang unik terhadap tes itu. Lima skip mempertahankan kekurangan prasyarat. Skenario pemenuhan intercompany dapat memakai fallback PR ketika kontrak harga internal tidak tersedia; status pass pada jalur fallback tidak membuktikan interco purchase→ownership→shipping selesai.

## Replay gelombang sebelumnya

| Kelompok | Skrip | Pemeriksaan | Pass | Fail | Nonzero/timeout |
|---|---|---|---|---|---|
| core | 15 | 310 | 309 | 1 | 0 |
| w2 | 4 | 82 | 82 | 0 | 0 |
| extended | 41 | 455 | 414 | 41 | 3 |

Semua hasil nonpass replay diperinci pada `latest/evidence/replay-nonpass-adjudication.csv`. Bukti awal connection-refused dipertahankan, kemudian tiga skrip diulang dengan pembacaan frontend.env diarahkan ke server suite yang benar; assertion tidak berubah. Core RF-05 masih terblokir oleh fixture tanpa tag. Extended mencakup permission 403, prasyarat return/employee/design yang tidak terbentuk, font OCR tidak tersedia, entitas hardcoded tidak ada, dan timeout. Semua ini dipisahkan dari counterexample yang sudah terbukti.

Kasus COMM-05 mempunyai oracle max(created_at), sedangkan helper kanonis memakai valid_from, created_at, id. Perbedaan tie-break tidak diberi status bug secara otomatis. Follow-up OPS-02 menjalankan scanner tiga kali dan membuktikan level target 1→2→2 sesuai manager→admin; tambahan notifikasi antarlevel memang dirancang. Assertion no-growth seluruh jobs tidak cukup membuktikan duplikasi. Ini kontrol terarah, bukan sertifikasi seluruh scanner bebas race. RF-09 dan flow desain tertentu tetap memerlukan contract/fixture adjudication; tidak dinyatakan tuntas.

## Bukti terarah yang tetap terbuka

17 counterexample fault lama berhasil direproduksi pada source terbaru; temuan ini tidak ditutup oleh W2 82/82. Counterexample baru memakai source asli, expected independen, input terukur dan hasil actual. Race di SO stock fill menjadwalkan dua final-write setelah masing-masing allocator asli berjalan; produksi kode tidak diganti. Function-level JS memakai transport terkontrol agar respons out-of-order dapat diuji, namun masih memerlukan browser test.

Tahap d6da dan baseline 5b7 mempunyai full-suite results sendiri, disimpan sebagai histori. Perbandingan stateful itu bukan eksperimen bersih untuk mengatribusikan seluruh perubahan pass/fail ke patch terbaru. Angka tahap lama tidak dipakai sebagai angka pengujian current commit.
