> **Review lanjutan 29 September 2026:** baca [hasil validasi Astra](07_REVIEW_ASTRA_MULAI_DI_SINI.md) dan [koreksi per temuan](08_VALIDASI_65_TEMUAN.md) sebelum memakai laporan/prompt awal ini. Sebagian klaim telah dipersempit atau dikoreksi.

# Audit KNHOST — temuan kode dan proses bisnis

Snapshot: [`d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`](https://github.com/pandeyoga/KNHOST/commit/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467), cabang main yang diambil pada 28 September 2026. Audit tidak mengubah kode aplikasi atau data server.

## Keputusan kesiapan

**RFID/gate: belum layak menjadi kontrol utama izin keluar/masuk. WMS: fondasi operasional ada, tetapi belum layak dinyatakan aman untuk stok enterprise tanpa perbaikan blocker. Finance: belum layak dipakai sebagai angka final yang dianggap akurat tanpa rekonsiliasi independen dan perbaikan temuan.** Ini penilaian kode snapshot, bukan kesimpulan bahwa setiap transaksi deployed sudah salah.

Tiga akar masalah terbesar: (1) identitas/status/document movement tidak dijaga konsisten pada semua pintu; (2) atomic claim pada dokumen induk tidak menjamin atomisitas roll atau pemulihan lintas-koleksi; (3) subledger dan GL/laporan tidak selalu berasal dari kejadian serta valuation yang sama.

Temuan terkurasi: **65** (47 P1, 16 P2, 2 P3). Jumlah ini bukan jumlah semua warning lint, dan tidak termasuk setiap baris gap enterprise pada dokumen fit-gap. Beberapa temuan merangkum satu keluarga cacat; jangan menjumlah ulang dampaknya sebagai kerugian independen.

P1 = penghalang penggunaan pada proses terkait: izin fisik, stok/nilai, financial correctness atau akses data. P2 = cacat operasional/kontrol yang penting tetapi tidak selalu menyebabkan salah buku saat ini. P3 = maintainability. “Direproduksi” berarti fungsi AST asli dieksekusi dengan mock dependency; “terbukti statis” berarti jalur kode dibaca dan kontraknya ditelusuri; “risiko konkurensi” adalah interleaving yang mungkin dari kode, belum stress test Mongo. Tidak ada P0 yang dinyatakan tanpa bukti dampak produksi aktual.

Lihat [cakupan dan verifikasi](04_CAKUPAN_DAN_VERIFIKASI.md), [analisis fitur/UI/enterprise](02_RFID_WMS_FINANCE_FIT_GAP.md), dan [prompt perbaikan](03_PROMPT_PERBAIKAN_AGENT.md). Tidak adanya temuan spesifik pada suatu file bukan sertifikasi file bebas bug.

## Daftar temuan

| ID | Prioritas | Temuan | Bukti |
|---|---|---|---|
| [RF-01](#rf-01) | P1 | Format EPC database berbeda dari EPC yang ditulis ke chip | Direproduksi |
| [RF-02](#rf-02) | P1 | Gate OUT menganggap status sebagai izin keluar | Direproduksi |
| [RF-03](#rf-03) | P1 | Gate IN menerima transit di gudang mana pun | Direproduksi |
| [RF-04](#rf-04) | P1 | Final Loading Check belum menjadi prasyarat dispatch | Perilaku terbukti; gap kontrol |
| [RF-05](#rf-05) | P1 | Loading Check clean walaupun sebagian roll tidak punya tag | Terbukti dari jalur kode |
| [RF-06](#rf-06) | P1 | Hasil loading melekat pada SO, tidak pada versi shipment aktual | Risiko kontrol dari kode |
| [RF-07](#rf-07) | P1 | Tombol simulasi dapat mengisi bukti verifikasi operasional | Terbukti dari UI dan API |
| [RF-08](#rf-08) | P1 | Sesi dan histori Cycle Count RFID tidak terisolasi entitas | Direproduksi sebagian; jalur lengkap statis |
| [RF-09](#rf-09) | P2 | Cycle count lintas entitas dibuat tetapi tidak dapat dipindai | Direproduksi |
| [RF-10](#rf-10) | P1 | Mesin sesi bersama tidak memvalidasi jenis sesi dan kehilangan scan konkuren | Terbukti statis; konkurensi perlu DB test |
| [RF-11](#rf-11) | P2 | Payload ZPL dan custom EPC tidak divalidasi aman | Direproduksi untuk ZPL; EPC statis |
| [RF-12](#rf-12) | P1 | Daftar device membocorkan API key hardware | Direproduksi |
| [RF-13](#rf-13) | P1 | Device dinonaktifkan masih diterima autentikasi | Direproduksi |
| [RF-14](#rf-14) | P2 | Lifecycle cetak mengklaim tag tercetak terlalu dini dan retry verifikasi buntu | Terbukti statis |
| [RF-15](#rf-15) | P1 | Antrean printer tidak memiliki claim dan ack tidak membatasi tipe device | Terbukti statis; balapan perlu integration test |
| [RF-16](#rf-16) | P2 | Ingest belum mempunyai event identity, passage window dan deduplikasi lintas batch | Gap integrasi terbukti dari kontrak |
| [RF-17](#rf-17) | P2 | Definisi stok fisik RFID berbeda dari SSOT dan metrik count mengabaikan extra | Terbukti statis |
| [WM-01](#wm-01) | P1 | Normalisasi setelah split atomik dapat mengembalikan stok yang sudah diambil | Risiko konkurensi dibuktikan urutan kode |
| [WM-02](#wm-02) | P1 | Reservasi parsial langsung melahirkan roll anak sebelum pemotongan fisik | Gap SSOT fisik dari desain |
| [WM-03](#wm-03) | P1 | Konfirmasi tiba dengan scan kosong memindahkan semua roll | Terbukti statis |
| [WM-04](#wm-04) | P1 | Putaway antar-gudang in-transit tidak mengubah bucket stok roll | Terbukti statis |
| [WM-05](#wm-05) | P1 | PA dapat berebut roll dan arrival menulis lokasi tanpa prasyarat roll | Risiko konkurensi statis |
| [WM-06](#wm-06) | P1 | Scan picking tidak memvalidasi identitas roll dan menerima qty negatif | Terbukti statis |
| [WM-07](#wm-07) | P1 | Stock opname per bin memakai expected seluruh gudang dan membolehkan duplikasi | Terbukti statis |
| [WM-08](#wm-08) | P1 | Adjustment shortage dapat parsial tetapi sesi tetap approved | Terbukti statis; konkurensi belum dieksekusi |
| [WM-09](#wm-09) | P2 | Penerimaan exception PA tidak menulis mutasi transfer | Terbukti statis |
| [FN-01](#fn-01) | P1 | Landed cost menghitung anak split dua kali | Direproduksi |
| [FN-02](#fn-02) | P1 | 3-way match lolos overbilling dari baris produk duplikat | Direproduksi |
| [FN-03](#fn-03) | P1 | WAC menjumlah panjang dan cost lintas unit tanpa konversi | Direproduksi |
| [FN-04](#fn-04) | P1 | Arus kas seimbang tetapi klasifikasi transaksi nonkas salah | Direproduksi dua skenario |
| [FN-05](#fn-05) | P1 | Master akun laporan menggabungkan override entitas dengan last-write-wins | Direproduksi |
| [FN-06](#fn-06) | P2 | Jurnal manual menolak akun custom entitas dan mengabaikan override | Terbukti statis |
| [FN-07](#fn-07) | P1 | Kas manual tidak langsung berjurnal dan void kas tidak membalik jurnal | Terbukti statis |
| [FN-08](#fn-08) | P1 | Opening balance rekening dan perubahan rekening tidak tersambung GL | Terbukti statis |
| [FN-09](#fn-09) | P1 | Void jurnal manual melewati penguncian periode | Terbukti statis |
| [FN-10](#fn-10) | P1 | Pembayaran AR dapat sukses walau jurnal kas gagal | Terbukti statis |
| [FN-11](#fn-11) | P1 | HPP per shipment memakai rata-rata semua roll pesanan | Terbukti statis; angka contoh deterministik |
| [FN-12](#fn-12) | P1 | Edit master aset mengubah nilai/akun tanpa mengoreksi jurnal perolehan | Terbukti statis |
| [FN-13](#fn-13) | P1 | Close periode dapat berjalan dua kali secara bersamaan | Risiko konkurensi statis |
| [FN-14](#fn-14) | P1 | Stock opname tidak memposting variance GL dan surplus dibuat tanpa cost | Terbukti statis |
| [FN-15](#fn-15) | P2 | Helper autopost tidak menegakkan invariant jurnal di pintu insert | Kelemahan kontrol statis |
| [FN-16](#fn-16) | P2 | Neraca default tidak membatasi tanggal meski diberi label hari ini | Terbukti statis |
| [GN-01](#gn-01) | P1 | Idempotency tidak terikat user cookie, entitas dan payload | Terbukti statis |
| [GN-02](#gn-02) | P1 | WebSocket GPS dapat dilanggan user biasa dan mengabaikan expiry/scope | Terbukti statis |
| [GN-03](#gn-03) | P1 | Ledger rekening dan reconcile kas berdasarkan ID tidak memeriksa entitas dokumen | Terbukti statis |
| [GN-04](#gn-04) | P1 | R&D dapat mengambil bahan dari roll badan usaha lain | Terbukti statis |
| [GN-05](#gn-05) | P1 | Rollback pengambilan bahan R&D dapat menimpa pemakaian roll lain | Risiko konkurensi statis |
| [GN-06](#gn-06) | P1 | Produksi menyelesaikan WO tanpa claim dan memakai BOM terbaru | Terbukti statis; konkurensi belum DB test |
| [GN-07](#gn-07) | P1 | Retur supplier mengurangi roll dengan read-set dan partial return kehilangan identitas fisik | Risiko konkurensi dan gap traceability statis |
| [GN-08](#gn-08) | P1 | Konversi permintaan internal dapat melahirkan transaksi antar-PT ganda | Risiko konkurensi statis |
| [GN-09](#gn-09) | P1 | CRM mengamankan owner sales tetapi tidak entitas pada operasi berdasarkan ID | Terbukti statis |
| [GN-10](#gn-10) | P2 | Rekomendasi POS memakai entity query tanpa resolusi izin dan stok global | Terbukti statis |
| [GN-11](#gn-11) | P1 | Saga release menghapus lock tanpa mengecek efek yang sudah terposting | Risiko pemulihan statis |
| [GN-12](#gn-12) | P2 | Agregasi kritis berhenti pada batas to_list tanpa penanda truncation | Terbukti statis; kasus skala belum DB test |
| [GN-13](#gn-13) | P2 | Rebuild projection dapat menulis snapshot lama dan fallback UOM mencampur unit | Risiko konkurensi dan logika statis |
| [GN-14](#gn-14) | P2 | Audit log selalu before=None dan source secrets tersimpan dalam repo publik | Kontrol statis; validitas secret belum diverifikasi |
| [GN-15](#gn-15) | P3 | Duplikasi helper dan definisi status menunjukkan SSOT belum konsisten | Terbukti static exact AST; sebagian risiko desain |
| [HR-01](#hr-01) | P1 | PPh21 memakai TER bahkan pada masa pajak terakhir | Gap akurasi statis terhadap acuan resmi |
| [HR-02](#hr-02) | P1 | Lembur memakai multiplier flat dan dua sumber menit berpotensi tumpang tindih | Direproduksi formula; dedup risiko statis |
| [HR-03](#hr-03) | P2 | Persetujuan cuti tidak mengecek ulang saldo dan cuti lintas tahun salah pembebanan | Terbukti statis |
| [MK-01](#mk-01) | P2 | Input metrik marketing parsial mengganti seluruh metrik sebelumnya | Terbukti statis |
| [UX-01](#ux-01) | P1 | Gate kiosk menampilkan hasil lama sebagai LIVE dan tidak mengagregasi satu passage | Terbukti dari source UI; belum uji visual hardware |
| [UX-02](#ux-02) | P2 | Unduhan ZPL lewat tautan tidak membawa konteks entitas yang dipilih | Risiko UI statis |
| [GN-16](#gn-16) | P1 | Laporan AI pribadi disiarkan melalui notifikasi dan digest tidak membatasi entitas | Terbukti dari kontrak audience dan query |
| [UX-03](#ux-03) | P3 | Panel biaya OCR menampilkan ID entitas mentah | Terbukti dari render source |

<a id="rf-01"></a>
## RF-01 · P1 — Format EPC database berbeda dari EPC yang ditulis ke chip

**Status bukti:** Direproduksi.

**Letak kode dan bukti:**

[backend/services/rfid_service.py:43](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_service.py#L43)

```text
  42 |     s = ("E2" + h)[:24]
  43 |     return "-".join(s[i:i + 4] for i in range(0, 24, 4))
  44 |
  45 |
```

[backend/services/rfid_print_service.py:43](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L43)

```text
  42 |     """ZPL label 4x2" (203dpi) dengan tulis EPC ke chip RFID (^RFW,H)."""
  43 |     epc_hex = epc.replace("-", "")[:24]
  44 |     sku = (tag.get("sku") or "")[:28]
  45 |     name = (tag.get("product_name") or "")[:40]
```

[backend/services/rfid_ingest_service.py:99](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L99)

```text
  98 |     for raw in list(dict.fromkeys(e.strip().upper() for e in epcs if e and e.strip()))[:500]:
  99 |         tag = await db.rfid_tags.find_one({"epc": raw, "status": "active"}, {"_id": 0})
 100 |         roll = await db.inventory_rolls.find_one({"id": tag["roll_id"]}, {"_id": 0}) if tag else None
 101 |         if not tag or not roll:
```

**Akar masalah.** Generator menyimpan EPC dengan tanda hubung; ZPL menghapus tanda hubung; ingest dan scan_verify hanya strip/uppercase lalu mencari kecocokan persis. Tidak ada canonicalizer bersama. Middleware eksternal mungkin memformat ulang, tetapi kontrak backend sendiri tidak menjamin itu.

**Skenario/reproduksi.** RF-01 menghasilkan EPC berkelompok dari fungsi asli, mengambil payload ^RFW, dan membuktikan kedua string berbeda. Reader yang mengirim 24 hex tanpa hubung akan dianggap EPC asing atau extra meskipun tag dicetak sistem sendiri.

**Dampak.** Gate merah palsu, gagal verifikasi, missing palsu, dan insiden palsu. Ini penghalang integrasi hardware.

**Perbaikan yang diminta.** Simpan EPC canonical uppercase hex tanpa separator; formatter hanya untuk tampilan. Migrasi data dan referensi expected/scanned; deteksi benturan sebelum unique index. Validasi panjang/hex secara eksplisit.

**Kriteria selesai.** Encode→ZPL→raw reader→ingest→verify harus menunjuk roll yang sama; input berseparator/lowercase di normalisasi konsisten; dua representasi tidak boleh menghasilkan dua tag.

**Prompt:** gunakan tiket `RF-01` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="rf-02"></a>
## RF-02 · P1 — Gate OUT menganggap status sebagai izin keluar

**Status bukti:** Direproduksi.

**Letak kode dan bukti:**

[backend/services/rfid_ingest_service.py:78](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L78)

```text
  77 |         return {"result": "red", "reason": "Roll masih AVAILABLE — tidak ada dokumen keluar (SO/transfer/PA). Keluar tak sah."}
  78 |     if status in GREEN_OUT_STATUSES:
  79 |         ref = roll.get("reserved_ref") or {}
  80 |         so = ""
```

[backend/services/rfid_service.py:32](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_service.py#L32)

```text
  31 | # siap berangkat dinyatakan MERAH oleh layar operator tetapi HIJAU oleh perangkat keras.
  32 | GREEN_OUT = {"reserved", "allocated", "committed", "picked", "packed",
  33 |              "in_transit_sales", "in_transit_transfer", "delivered", "consumed"}
  34 | RED_OUT = {"available", "quarantine"}
```

**Akar masalah.** Cabang umum OUT menerima reserved/allocated/committed/picked/packed/transit/delivered/consumed. SO hanya dibaca untuk nomor; tidak diperiksa status, gudang asal, shipment aktif, atau keanggotaan roll pada manifest. PA juga diterima dari journey tanpa cek status PA pada cabang OUT.

**Skenario/reproduksi.** RF-02: roll delivered milik gudang SOURCE dibaca gate OTHER, tanpa SO/PA; hasil green. Reserved saja juga dapat green sebelum benar-benar siap pengiriman.

**Dampak.** Lampu hijau dapat mengizinkan barang yang salah, dokumen batal, atau tag lama. Sebutan “sadar-dokumen” pada doc string tidak sesuai keketatan implementasi.

**Perbaikan yang diminta.** Gunakan otorisasi movement aktif berisi roll_id, source/destination, status release, manifest_version, waktu, lane dan owner. OUT harus cocok source dan manifest; delivered/consumed tidak otomatis sah. Simulator memakai evaluator yang sama.

**Kriteria selesai.** Uji SO batal, PA selesai, roll salah gudang, roll belum release, tag consumed, salah shipment, dan replay keluar: seluruhnya ditahan dengan reason code yang jelas.

**Prompt:** gunakan tiket `RF-02` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="rf-03"></a>
## RF-03 · P1 — Gate IN menerima transit di gudang mana pun

**Status bukti:** Direproduksi.

**Letak kode dan bukti:**

[backend/services/rfid_ingest_service.py:65](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L65)

```text
  64 |                 f"SALAH GUDANG — {pa['pa_number']} menuju {pa.get('to_warehouse_name', '?')}, bukan gudang ini.")}
  65 |         if status in ("in_transit_transfer", "in_transit_sales"):
  66 |             return {"result": "green", "reason": f"Barang transit diterima (status: {status})."}
  67 |         if roll.get("warehouse_id") == wh_id:
```

**Akar masalah.** Jika PA tidak ditemukan/aktif, status transit langsung green. Transfer dan shipment tujuan tidak dicari; bahkan transit penjualan dianggap boleh diterima di gudang internal mana saja.

**Skenario/reproduksi.** RF-03 mengirim roll in_transit_transfer ke warehouse WRONG tanpa dokumen tujuan; fungsi asli memberi green.

**Dampak.** Tidak memenuhi kebutuhan gudang berbeda bangunan yang pernah dibahas: salah bangunan harus alarm, bukan diterima.

**Perbaikan yang diminta.** Resolusi dokumen transit wajib dari ref dan validasi destination, membership, owner, expected route dan status. Dokumen hilang atau tidak konsisten masuk exception; jangan fallback green.

**Kriteria selesai.** Roll menuju D dibaca IN H harus red; IN D hanya green saat movement aktif dan roll tercantum. Transit_sales tidak boleh dianggap transfer internal.

**Prompt:** gunakan tiket `RF-03` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="rf-04"></a>
## RF-04 · P1 — Final Loading Check belum menjadi prasyarat dispatch

**Status bukti:** Perilaku terbukti; gap kontrol.

**Letak kode dan bukti:**

[backend/services/loading_check_service.py:104](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L104)

```text
 103 |     lc = (so or {}).get("loading_check")
 104 |     if lc and lc.get("result") != "clean":
 105 |         raise HTTPException(status_code=400, detail=(
 106 |             f"Final Loading Check TIDAK BERSIH (missing {len(lc.get('missing') or [])}, "
```

**Akar masalah.** dispatch_guard menahan sesi terbuka dan hasil bermasalah, tetapi bila loading_check tidak pernah dibuat ia mengizinkan dispatch. Kontrol ini opsional secara implementasi. Ini gap terhadap tujuan pencegahan wrong-roll shipment, bukan klaim bahwa semua gudang wajib RFID.

**Skenario/reproduksi.** RF-04 memanggil guard untuk SO tanpa sesi atau hasil check; kembali normal.

**Dampak.** Operator dapat melewati sweep handheld seluruhnya dan tetap mengirim.

**Perbaikan yang diminta.** Buat policy per gudang/tracking_mode: RFID wajib check valid; barcode/manual memakai proses alternatif eksplisit. Override hanya permission tertentu dengan alasan dan audit, bukan ketiadaan data.

**Kriteria selesai.** Untuk policy RFID mandatory, dispatch tanpa check ditolak. Policy barcode tetap operasional melalui scan/override yang terkontrol; UI menjelaskan alasan blokir.

**Prompt:** gunakan tiket `RF-04` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="rf-05"></a>
## RF-05 · P1 — Loading Check clean walaupun sebagian roll tidak punya tag

**Status bukti:** Terbukti dari jalur kode.

**Letak kode dan bukti:**

[backend/services/loading_check_service.py:56](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L56)

```text
  55 |         "expected": expected, "scanned_epcs": [], "missing": [], "extra": [],
  56 |         "untagged_count": len(rolls) - len(expected),
  57 |         # Peringatan dini: roll expected yang BELUM committed akan lolos check tapi
  58 |         # tertahan saat dispatch (ship_order_rolls hanya kirim roll committed).
```

[backend/services/loading_check_service.py:77](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L77)

```text
  76 |         raise HTTPException(status_code=400, detail="Sesi sudah selesai")
  77 |     clean = "clean" if not prog["missing"] and not prog["extra"] else "with_issues"
  78 |     now = now_iso()
  79 |     # INV-ATOMIC-01 — klaim sesi (status open) SESUDAH validasi, sebelum SO ditulis; finish_set.
```

**Akar masalah.** Expected hanya berisi roll yang punya tag aktif. untagged_count di catat sebagai angka peringatan tetapi tidak ikut menentukan clean dan tidak disimpan sebagai blocker pada SO.

**Skenario/reproduksi.** Alokasi dua roll: satu bertag dan satu tanpa tag. Scan satu EPC; missing/extra kosong, sesi menjadi clean walau roll kedua belum diverifikasi.

**Dampak.** Angka 100% menyesatkan; roll tanpa tag bisa salah/tertinggal tanpa tertahan.

**Perbaikan yang diminta.** Manifest verifikasi mencakup semua roll fisik. Roll tanpa RFID perlu scan barcode id entitas atau pengecualian berizin; untagged unresolved berarti tidak clean.

**Kriteria selesai.** Satu tagged+ satu untagged tidak boleh clean setelah satu EPC. Tidak aktifnya tag, retired tag dan dangling tag_id juga di hitung unresolved.

**Prompt:** gunakan tiket `RF-05` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="rf-06"></a>
## RF-06 · P1 — Hasil loading melekat pada SO, tidak pada versi shipment aktual

**Status bukti:** Risiko kontrol dari kode.

**Letak kode dan bukti:**

[backend/services/loading_check_service.py:54](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L54)

```text
  53 |         "so_number": so.get("number", ""), "print_job_id": None,
  54 |         "owner_entity_id": so.get("entity_id"), "warehouse_id": None,
  55 |         "expected": expected, "scanned_epcs": [], "missing": [], "extra": [],
  56 |         "untagged_count": len(rolls) - len(expected),
```

[backend/services/loading_check_service.py:84](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L84)

```text
  83 |     await db.sales_orders.update_one({"id": prog["order_id"]}, {"$set": {"loading_check": {
  84 |         "session_id": session_id, "result": clean,
  85 |         "matched": prog["matched_count"], "expected": prog["expected_count"],
  86 |         "missing": prog["missing"], "extra": prog["extra"], "checked_at": now}}})
```

[backend/services/loading_check_service.py:93](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L93)

```text
  92 |
  93 | async def dispatch_guard(order_id: Optional[str]) -> None:
  94 |     """Blokir dispatch bila loading check terbuka / hasil terakhir tidak bersih."""
  95 |     if not order_id:
```

**Akar masalah.** Snapshot expected seluruh roll SO tidak mengikat task/shipment, gudang, allocation_version atau hash manifest. Guard hanya membaca result terakhir; perubahan alokasi/picking setelah check tidak membatalkan hasil.

**Skenario/reproduksi.** Check clean, ganti roll alokasi atau tambah pengiriman parsial gudang lain, lalu dispatch dengan result lama. Skenario ini perlu integration test untuk memastikan seluruh jalur perubahan; guard sendiri tidak mempunyai validasi versi.

**Dampak.** Barang yang diberangkatkan bisa berbeda dari barang yang lolos verifikasi; SO multi-gudang/partial shipment sulit dipastikan.

**Perbaikan yang diminta.** Sesi per shipment/task+warehouse dengan manifest immutable/version; invalidasi bila roll/qty/order berubah; guard membandingkan hash/version dan freshness.

**Kriteria selesai.** Pergantian satu roll setelah clean wajib recheck. Dua shipment parsial punya sesi independen. Check shipment A tidak membuka dispatch B.

**Prompt:** gunakan tiket `RF-06` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="rf-07"></a>
## RF-07 · P1 — Tombol simulasi dapat mengisi bukti verifikasi operasional

**Status bukti:** Terbukti dari UI dan API.

**Letak kode dan bukti:**

[frontend/src/features/rfid/CycleCountPanel.jsx:67](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/rfid/CycleCountPanel.jsx#L67)

```text
  66 |                 className="rounded-lg bg-[#0058CC] px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-40">Kirim Scan</button>
  67 |               <button data-testid="cc-simulate" disabled={busy}
  68 |                 onClick={() => scan((session.expected || []).map((e) => e.epc))}
  69 |                 className="flex items-center gap-1 rounded-lg border border-[#0058CC] px-3 py-1.5 text-[11px] font-semibold text-[#0058CC] disabled:opacity-40">
```

[frontend/src/features/rfid/RfidPrintVerifyPanel.jsx:244](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/rfid/RfidPrintVerifyPanel.jsx#L244)

```text
 243 |                 </button>
 244 |                 <button data-testid="rfid-verify-simulate" disabled={busy}
 245 |                   onClick={() => sendScan((session.expected || []).map((e) => e.epc))}
 246 |                   className="flex items-center gap-1 rounded-lg border border-[#0058CC] px-3 py-1.5 text-[11px] font-semibold text-[#0058CC] disabled:opacity-40">
```

[frontend/src/features/wms/LoadingCheckPanel.jsx:79](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/wms/LoadingCheckPanel.jsx#L79)

```text
  78 |               className="rounded bg-[#4B3B9E] px-2.5 py-1 text-[10.5px] font-semibold text-white disabled:opacity-40">Kirim Scan</button>
  79 |             <button data-testid="lc-simulate" disabled={busy}
  80 |               onClick={() => scan((session.expected || []).map((e) => e.epc))}
  81 |               className="flex items-center gap-1 rounded border border-[#4B3B9E] px-2.5 py-1 text-[10.5px] font-semibold text-[#4B3B9E] disabled:opacity-40">
```

**Akar masalah.** UI mengirim semua EPC expected ke endpoint scan produksi untuk simulasi. Tidak ada pemisahan namespace/sesi simulasi yang menjaga hasil tidak digunakan sebagai verifikasi nyata. Endpoint menerima EPC dari user biasa tanpa bukti device.

**Skenario/reproduksi.** Mulai count/print verify/loading; gunakan simulasi semua tag; selesaikan. Sistem tidak dapat membedakan bukti fisik dari daftar yang disalin dari expected.

**Dampak.** Kontrol inventori dan loading dapat menjadi sekadar klik; audit tidak membuktikan barang pernah dipindai.

**Perbaikan yang diminta.** Simulation hanya environment/sesi test yang tidak boleh dispatch atau memutakhirkan journey produksi. Untuk operasi, sertakan asal scan dan id entitas reader; manual override terpisah dan di audit.

**Kriteria selesai.** Hasil simulated tidak dapat memberi clean operasional atau izin dispatch. User tanpa override tidak dapat mengesahkan seluruh expected lewat tombol simulasi.

**Prompt:** gunakan tiket `RF-07` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="rf-08"></a>
## RF-08 · P1 — Sesi dan histori Cycle Count RFID tidak terisolasi entitas

**Status bukti:** Direproduksi sebagian; jalur lengkap statis.

**Letak kode dan bukti:**

[backend/services/cycle_count_service.py:22](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cycle_count_service.py#L22)

```text
  21 |     existing = await db.rfid_verify_sessions.find_one(
  22 |         {"kind": "cycle_count", "warehouse_id": warehouse_id, "status": "open"}, {"_id": 0})
  23 |     if existing:
  24 |         return safe_doc(existing)
```

[backend/services/cycle_count_service.py:53](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cycle_count_service.py#L53)

```text
  52 |
  53 | async def complete(session_id: str, actor_name: str) -> Dict[str, Any]:
  54 |     sess = await db.rfid_verify_sessions.find_one({"id": session_id}, {"_id": 0})
  55 |     if not sess or sess.get("kind") != "cycle_count":
```

[backend/services/cycle_count_service.py:111](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cycle_count_service.py#L111)

```text
 110 |
 111 | async def get_count(cc_id: str) -> Dict[str, Any]:
 112 |     cc = await db.rfid_cycle_counts.find_one({"id": cc_id}, {"_id": 0})
 113 |     if not cc:
```

**Akar masalah.** Pencarian sesi existing hanya gudang/kind/status. complete tidak menerima scope; histori/count detail tidak punya guard owner. Dokumen hasil count bahkan tidak menyimpan owner scope. Ini berbeda dari cycle-count non-RFID yang sudah memakai guard_doc.

**Skenario/reproduksi.** RF-08: sesi entitas A terbuka di gudang shared; pengguna B start dan mendapat sesi A. Permission wms tidak sama dengan izin terhadap data badan usaha A.

**Dampak.** Kebocoran daftar expected/selisih dan penutupan count badan usaha lain.

**Perbaikan yang diminta.** Stempel immutable scope_ids/owner; existing harus tepat scope; guard scan, progress, complete, history dan detail. Backfill histori lama dengan asal session; data tidak bisa dipetakan jangan dianggap global bebas.

**Kriteria selesai.** User B tidak dapat melihat, reuse, scan atau complete sesi A meski warehouse sama. Histori hanya scope authorized; admin view-all eksplisit.

**Prompt:** gunakan tiket `RF-08` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="rf-09"></a>
## RF-09 · P2 — Cycle count lintas entitas dibuat tetapi tidak dapat dipindai

**Status bukti:** Direproduksi.

**Letak kode dan bukti:**

[backend/services/cycle_count_service.py:44](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cycle_count_service.py#L44)

```text
  43 |         "warehouse_id": warehouse_id, "warehouse_name": wh.get("name", ""),
  44 |         "owner_entity_id": scope_ids[0] if len(scope_ids) == 1 else None,
  45 |         "expected": expected, "scanned_epcs": [], "missing": [], "extra": [],
  46 |         "status": "open", "created_at": now_iso(), "created_by": actor_name,
```

[backend/services/rfid_print_service.py:214](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L214)

```text
 213 |         raise HTTPException(status_code=404, detail="Sesi verifikasi tidak ditemukan")
 214 |     if sess.get("owner_entity_id") not in scope_ids:
 215 |         raise HTTPException(status_code=403, detail="Sesi di luar entitas Anda")
 216 |     if sess["status"] != "open":
```

**Akar masalah.** Saat scope lebih dari satu, session.owner_entity_id=None. scan_verify membandingkan None dengan daftar entity ID dan menolak. Representasi scope berbeda antara pembuat dan pemakai sesi.

**Skenario/reproduksi.** RF-09: sesi multi-owner valid dengan scope A/B selalu 403 pada scan.

**Dampak.** Count gudang shared oleh manager view-all menjadi jalan buntu; operator terdorong mencari workaround.

**Perbaikan yang diminta.** Representasikan scope sebagai set entity IDs dan validasi subset authorized; atau buat sesi per owner secara eksplisit. Jangan memakai None untuk arti lintas entitas.

**Kriteria selesai.** Single owner, multi-owner authorized, user dengan subset owner, dan view-all diuji tanpa kebocoran cross-scope.

**Prompt:** gunakan tiket `RF-09` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="rf-10"></a>
## RF-10 · P1 — Mesin sesi bersama tidak memvalidasi jenis sesi dan kehilangan scan konkuren

**Status bukti:** Terbukti statis; konkurensi perlu DB test.

**Letak kode dan bukti:**

[backend/services/rfid_print_service.py:219](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L219)

```text
 218 |     clean = {e.strip().upper() for e in epcs if e and e.strip()}
 219 |     merged = sorted(set(sess.get("scanned_epcs") or []) | clean)
 220 |     await db.rfid_verify_sessions.update_one({"id": session_id}, {"$set": {
 221 |         "scanned_epcs": merged, "updated_at": now_iso()}})
```

[backend/services/rfid_print_service.py:236](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L236)

```text
 235 |
 236 | async def complete_verify(session_id: str, scope_ids: List[str]) -> Dict[str, Any]:
 237 |     prog = await _verify_progress(session_id)
 238 |     if prog.get("owner_entity_id") not in scope_ids:
```

**Akar masalah.** scan membaca lalu $set keseluruhan scanned_epcs sehingga dua batch bersamaan dapat saling menimpa. Update tidak berprasyarat status open. complete_verify tidak memastikan kind print_verify dan dapat memproses loading_check/cycle_count karena memakai koleksi yang sama.

**Skenario/reproduksi.** Dua scan A/B membaca []; tulisan terakhir menghilangkan batch lain. Panggil print complete dengan ID sesi loading: sesi selesai, journey berubah tag_verified, tetapi loading_check SO tidak diperbarui.

**Dampak.** Missing palsu, scan terlambat mengubah sesi final, dan workflow yang salah menutup sesi.

**Perbaikan yang diminta.** Sesi punya kind wajib; semua endpoint assert kind. Scan gunakan atomic $addToSet/$each dengan status/scope guard; complete snapshot/claim mencegah late write. Unknown ID harus 404, bukan sess.get pada None.

**Kriteria selesai.** Dua batch paralel mempertahankan union; scan setelah complete ditolak; endpoint print tidak menerima loading/count; unknown session menghasilkan 404.

**Prompt:** gunakan tiket `RF-10` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="rf-11"></a>
## RF-11 · P2 — Payload ZPL dan custom EPC tidak divalidasi aman

**Status bukti:** Direproduksi untuk ZPL; EPC statis.

**Letak kode dan bukti:**

[backend/services/rfid_print_service.py:43](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L43)

```text
  42 |     """ZPL label 4x2" (203dpi) dengan tulis EPC ke chip RFID (^RFW,H)."""
  43 |     epc_hex = epc.replace("-", "")[:24]
  44 |     sku = (tag.get("sku") or "")[:28]
  45 |     name = (tag.get("product_name") or "")[:40]
```

[backend/services/rfid_print_service.py:52](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L52)

```text
  51 |         f"^RFW,H^FD{epc_hex}^FS\n"
  52 |         f"^FO20,15^A0N,28,28^FD{name}^FS\n"
  53 |         f"^FO20,50^A0N,24,24^FDSKU: {sku}^FS\n"
  54 |         f"^FO20,80^A0N,24,24^FDRoll: {roll_no}  Lot: {lot}^FS\n"
```

[backend/services/rfid_service.py:122](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_service.py#L122)

```text
 121 |
 122 | async def encode_tag(roll_id: str, scope_ids: List[str], epc: Optional[str] = None,
 123 |                      actor_name: str = "System") -> Dict[str, Any]:
 124 |     roll = await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0})
```

**Akar masalah.** Nama/SKU/roll/lot disisipkan langsung ke bahasa perintah printer. EPC custom tidak dijamin 24 hex; ZPL memotong 24 karakter sehingga dua EPC data base dapat ditulis sebagai chip yang sama.

**Skenario/reproduksi.** RF-11 memasukkan product_name berisi ^FS^FO0,0^FDINJECTED dan perintah itu muncul verbatim di label. Dua EPC dengan awalan 24 hex sama dan suffix berbeda ditulis identik.

**Dampak.** Label rusak, perintah printer tak diinginkan, id entitas tag berbeda dari data base. Tidak membuktikan eksekusi kode pada server.

**Perbaikan yang diminta.** Escape/encode field text ZPL, batasi control characters; validasi EPC canonical dan panjang; jangan silently truncate. Dokumentasikan jenis encoding EPC internal vs GS1.

**Kriteria selesai.** Test ^, ~, new line, Unicode, string panjang, nonhex, 23/25/32hex; tidak ada command injection atau collision akibat truncation.

**Prompt:** gunakan tiket `RF-11` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="rf-12"></a>
## RF-12 · P1 — Daftar device membocorkan API key hardware

**Status bukti:** Direproduksi.

**Letak kode dan bukti:**

[backend/services/rfid_service.py:197](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_service.py#L197)

```text
 196 |         q["warehouse_id"] = warehouse_id
 197 |     devs = await db.rfid_devices.find(q, {"_id": 0}).sort("code", 1).to_list(500)
 198 |     return [safe_doc(d) for d in devs]
 199 |
```

[backend/routers/rfid.py:304](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L304)

```text
 303 | @router.get("/rfid/devices")
 304 | async def get_devices(request: Request, warehouse_id: Optional[str] = None) -> Dict[str, Any]:
 305 |     await require_permission(request, "wms", "view")
 306 |     devs = await rfid.list_devices(warehouse_id)
```

**Akar masalah.** ensure_api_key menyimpan api_key di device. list_devices memproyeksikan hanya _id keluar dan mengembalikan semua field. Route list biasa bukan endpoint khusus pengambilan credential.

**Skenario/reproduksi.** RF-12: record device bertest key dikembalikan apa adanya oleh fungsi list. Key tersebut dapat dipakai device ingest/heartbeat tanpa login user.

**Dampak.** User yang boleh melihat device dapat menyamar reader/printer, mengirim event palsu dan mengubah bukti verifikasi.

**Perbaikan yang diminta.** Whitelist public DTO; key hanya ditampilkan sekali pada provisioning berizin. Simpan hash key untuk authenticate; rotasi credential yang pernah terbuka; sanitasi audit/log.

**Kriteria selesai.** Semua list/detail/update response tidak berisi key/hash. Viewer tidak dapat mengambil key. Rotasi membuat key lama tidak berlaku.

**Prompt:** gunakan tiket `RF-12` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="rf-13"></a>
## RF-13 · P1 — Device dinonaktifkan masih diterima autentikasi

**Status bukti:** Direproduksi.

**Letak kode dan bukti:**

[backend/services/rfid_ingest_service.py:35](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L35)

```text
  34 |         raise HTTPException(status_code=401, detail="Header X-Device-Key wajib")
  35 |     dev = await db.rfid_devices.find_one({"api_key": device_key}, {"_id": 0})
  36 |     if not dev:
  37 |         raise HTTPException(status_code=401, detail="Device key tidak dikenal")
```

**Akar masalah.** Authenticate hanya menguji keberadaan key. Disabled/status offline tidak merupakan revocation; heartbeat dan ingest kemudian dapat menyetelnya online kembali.

**Skenario/reproduksi.** RF-13: record status disabled dengan key valid tetap diterima authenticate.

**Dampak.** Penonaktifan device di UI tidak menghentikan device bocor atau rusak. Online/offline sebaiknya terpisah dari enabled/disabled.

**Perbaikan yang diminta.** Pisahkan lifecycle enabled dari health; reject disabled/revoked; key rotation dan grace policy eksplisit. Heartbeat tidak mengaktifkan kembali device.

**Kriteria selesai.** Disabled ditolak pada ingest, heartbeat dan printer pull/ack; offline tetapi enabled bisa reconnect sesuai policy.

**Prompt:** gunakan tiket `RF-13` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="rf-14"></a>
## RF-14 · P2 — Lifecycle cetak mengklaim tag tercetak terlalu dini dan retry verifikasi buntu

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/services/rfid_print_service.py:20](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L20)

```text
  19 | JOURNEY_STAGES = [
  20 |     "received_transit", "tag_printed", "tag_verified", "cross_dock_ready",
  21 |     "putaway_assigned", "putaway_in_transit", "stored", "gate_exception",
  22 | ]
```

[backend/services/rfid_print_service.py:189](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L189)

```text
 188 | # ─── Verifikasi (expected vs scanned) ────────────────────────────────────────
 189 | async def start_verify(job_id: str, scope_ids: List[str], actor_name: str) -> Dict[str, Any]:
 190 |     job = await get_print_job(job_id, scope_ids)
 191 |     if job["status"] not in ("printed", "queued"):
```

**Akar masalah.** Create job mengaktifkan tag dan menaikkan journey ke tag_printed ketika job baru queued. start_verify mengizinkan queued tetapi menolak verified_with_issues, padahal operator perlu ulang untuk missing. Reprint juga bisa menurunkan journey stored menjadi tag_printed/tag_verified.

**Skenario/reproduksi.** Printer belum pernah menerima job, tetapi roll ter tulis “Tag Dicetak”. Selesaikan verify dengan missing, lalu start verify lagi ditolak. Reprint roll tersimpan berpotensi masuk antrean perjalanan ulang.

**Dampak.** Status operasional tidak sama dengan kejadian fisik; pemulihan kegagalan cetak/verifikasi tidak tuntas.

**Perbaikan yang diminta.** Pisahkan encode intent→queued→printer acknowledged→read-after-write verified→active. Tag replacement/reprint tidak reset storage journey; retry buat revision session yang jelas.

**Kriteria selesai.** Queued tidak berlabel printed. Verify gagal bisa di ulang; reprint stored tidak memindahkan lokasi atau routing; kegagalan item ke-2 tidak meninggalkan tag item ke-1 aktif tanpa job.

**Prompt:** gunakan tiket `RF-14` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="rf-15"></a>
## RF-15 · P1 — Antrean printer tidak memiliki claim dan ack tidak membatasi tipe device

**Status bukti:** Terbukti statis; balapan perlu integration test.

**Letak kode dan bukti:**

[backend/services/rfid_ingest_service.py:144](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L144)

```text
 143 | # ─── Printer pull (middleware ambil antrean ZPL) ────────────────────────────
 144 | async def pending_jobs_for_device(device: Dict[str, Any]) -> Dict[str, Any]:
 145 |     if device.get("type") != "printer":
 146 |         raise HTTPException(status_code=400, detail="Device bukan printer")
```

[backend/services/rfid_ingest_service.py:153](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L153)

```text
 152 |
 153 | async def ack_job_printed(device: Dict[str, Any], job_id: str) -> Dict[str, Any]:
 154 |     job = await db.rfid_print_jobs.find_one({"id": job_id}, {"_id": 0, "items.zpl": 0})
 155 |     if not job:
```

**Akar masalah.** Dua printer di gudang yang sama membaca job queued yang sama tanpa lease/claim/printer assignment. Ack hanya mengecek gudang dan status, bukan bahwa device printer pemilik claim.

**Skenario/reproduksi.** Printer P1/P2 pull sebelum ack: keduanya bisa mencetak tag ber-EPC sama pada dua fisik. Gate/handheld dengan key gudang sama dapat ack job printed.

**Dampak.** Duplikasi fisik EPC dan bukti cetak palsu walau satu record tag di data base.

**Perbaikan yang diminta.** Atomic job lease ke pada printer tertentu, attempt_id, TTL dan recovery; ack wajib printer pemilik attempt; kemampuan QR/RFID berbeda; simpan hasil perlabel/write-readback.

**Kriteria selesai.** Dua pull paralel tidak mendapatkan ownership job yang sama. Ack dari gate, wrong printer, expired lease atau attempt lama ditolak.

**Prompt:** gunakan tiket `RF-15` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="rf-16"></a>
## RF-16 · P2 — Ingest belum mempunyai event identity, passage window dan deduplikasi lintas batch

**Status bukti:** Gap integrasi terbukti dari kontrak.

**Letak kode dan bukti:**

[backend/services/rfid_ingest_service.py:98](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L98)

```text
  97 |     now = now_iso()
  98 |     for raw in list(dict.fromkeys(e.strip().upper() for e in epcs if e and e.strip()))[:500]:
  99 |         tag = await db.rfid_tags.find_one({"epc": raw, "status": "active"}, {"_id": 0})
 100 |         roll = await db.inventory_rolls.find_one({"id": tag["roll_id"]}, {"_id": 0}) if tag else None
```

[backend/services/rfid_ingest_service.py:110](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L110)

```text
 109 |                           "owner_entity_id": None, "result": "red",
 110 |                           "reason": decision["reason"], "timestamp": now})
 111 |             continue
 112 |         if device.get("type") == "gate":
```

**Akar masalah.** Dedup hanya dalam satu request; limit 500 dipotong diam-diam. Kontrak tidak menyimpan event_id/device timestamp/antenna/RSSI/session passage atau arah hasil sensor. Arah berasal dari konfigurasi device. Unique EPC aktif juga tidak tampak di bootstrap repo; index DB deployed belum diperiksa.

**Skenario/reproduksi.** Reader terus membaca tag diam: retry/batch berikut menciptakan read/incident baru. Lebih dari 500 EPC tidak seluruhnya di proses dan tidak dilaporkan dropped.

**Dampak.** Alert flooding, false movement dan audit perjalanan yang sulit dibedakan dari multipath/stray read. Bukan bukti middleware deployed tidak memiliki filter sendiri.

**Perbaikan yang diminta.** Kontrak event batch dengan idempotency identity, capture time, antenna, passage/lane, direction confidence, limit explicit dan dead-letter. Simpan raw observation terpisah business event; active EPC uniqueness canonical.

**Kriteria selesai.** Replay event sama tidak menggandakan business event/incident. Tag diam tidak dianggap berulang kali keluar. >limit ditolak/dipecah dengan acknowledgement jelas.

**Prompt:** gunakan tiket `RF-16` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="rf-17"></a>
## RF-17 · P2 — Definisi stok fisik RFID berbeda dari SSOT dan metrik count mengabaikan extra

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/services/rfid_service.py:21](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_service.py#L21)

```text
  20 | # Status roll yang dianggap "fisik ada" (kandidat tag).
  21 | PHYSICAL_STATUSES = [
  22 |     "available", "reserved", "allocated", "quarantine",
  23 |     "committed", "picked", "packed", "hold",
```

[backend/services/cycle_count_service.py:80](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cycle_count_service.py#L80)

```text
  79 |     found = len(expected) - len(missing)
  80 |     accuracy = round(found / len(expected) * 100, 1) if expected else 100.0
  81 |     now = now_iso()
  82 |     cc = {
```

**Akar masalah.** RFID mempunyai daftar physical ter sendiri yang memasukkan transit sales/transfer dan menghilangkan blocked/damaged/wip dibanding status fisik roll. Expected hanya tag aktif; roll tanpa tag hilang dari denominator. accuracy=found/expected tetap 100% jika seluruh expected plus EPC extra ter baca.

**Skenario/reproduksi.** Roll WIP di gudang tidak di hitung, barang transit ikut expected asal, dan extra tidak menurunkan angka accuracy meski result with_issues.

**Dampak.** Dua modul dapat melaporkan jumlah fisik berbeda; label akurasi 100% bukan count accuracy seluruh gudang.

**Perbaikan yang diminta.** Pisahkan owned/on_hand/at_location/eligible_count; gunakan satu definisi domain bersama. Tampilkan coverage tag, read recall, extra rate dan unresolved count secara terpisah.

**Kriteria selesai.** Matriks semua status roll diuji terhadap count eligibility. UI tidak menampilkan 100% inventori hanya dari subset tagged; extra selalu terlihat sebagai masalah.

**Prompt:** gunakan tiket `RF-17` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="wm-01"></a>
## WM-01 · P1 — Normalisasi setelah split atomik dapat mengembalikan stok yang sudah diambil

**Status bukti:** Risiko konkurensi dibuktikan urutan kode.

**Letak kode dan bukti:**

[backend/services/roll_service.py:490](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L490)

```text
 489 |
 490 | async def _split_roll(roll: Dict[str, Any], take: float, order_id: str) -> Optional[Dict[str, Any]]:
 491 |     """Pecah roll available: kurangi sisa parent, buat child roll reserved sebesar `take`.
 492 |
```

[backend/services/roll_service.py:508](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L508)

```text
 507 |         {"id": roll["id"]},
 508 |         {"$set": {"length_remaining": round(float(parent.get("length_remaining", 0)), 2),
 509 |                   "length_initial": round(float(parent.get("length_initial", 0)), 2)}},
 510 |     )
```

**Akar masalah.** Pengurangan parent memakai atomic $inc, lalu update kedua melakukan $set dari snapshot hasil operasi pertama tanpa CAS/version. Atomic decrement kehilangan manfaat bila snapshot lama ditulis setelah split berikutnya. Jika insert_child_roll gagal, parent sudah berkurang tanpa kompensasi.

**Skenario/reproduksi.** Parent 100: A decrement30→snapshot 70; B decrement40→snapshot 30; B normalisasi 30; A normalisasi 70. Child total 70 + parent 70=140, padahal awal 100. Kegagalan insert child setelah decrement membuat panjang hilang. Ini trace interleaving, bukan hasil uji Mongo konkuren.

**Dampak.** Stok bisa tercipta/hilang, memengaruhi ATP, HPP dan genealogy.

**Perbaikan yang diminta.** Hapus stale normalization; gunakan integer scaled quantity atau atomic pipeline rounding. Split harus durable operation dengan parent/child conservation dan idempotent recovery; CAS/version menyertakan status dan qty.

**Kriteria selesai.** Parallel split30/40 dari 100 selalu total 100 parent 30; fault injection sesudah decrement/child insert pulih tanpa loss/duplicate. Jangan hanya menambah lock parent-document sales order.

**Prompt:** gunakan tiket `WM-01` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="wm-02"></a>
## WM-02 · P1 — Reservasi parsial langsung melahirkan roll anak sebelum pemotongan fisik

**Status bukti:** Gap SSOT fisik dari desain.

**Letak kode dan bukti:**

[backend/services/roll_service.py:490](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L490)

```text
 489 |
 490 | async def _split_roll(roll: Dict[str, Any], take: float, order_id: str) -> Optional[Dict[str, Any]]:
 491 |     """Pecah roll available: kurangi sisa parent, buat child roll reserved sebesar `take`.
 492 |
```

[backend/services/roll_service.py:523](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L523)

```text
 522 |     })
 523 |     child = await insert_child_roll(child, roll)
 524 |     return child
 525 |
```

**Akar masalah.** Alokasi parsial mengurangi panjang parent dan membuat child reserved saat checkout. Sebelum petugas memotong, fisik masih satu roll bertag parent tetapi data base sudah dua id entitas. insert_child_roll membersihkan tag child; tidak otomatis membuat bukti pemotongan dan pemasangan tag baru.

**Skenario/reproduksi.** Roll 100 di tag; SO reserve30. Data base parent 70+child 30, tag lama di fisik100. Gate/picking memerlukan child yang belum ada secara fisik.

**Dampak.** Pemetaan “1 tag = 1 roll fisik” tidak konsisten sepanjang flow; pembatalan/alokasi ulang dapat membuat genealogy administratif yang belum pernah terjadi.

**Perbaikan yang diminta.** Pisahkan quantity reservation dari physical cut work. Child fisik hanya diposting setelah cut confirmation dengan actual length/waste/remnant dan tag/barcode anak. Alternatif reserved fragment harus jelas bukan inventory_roll fisik.

**Kriteria selesai.** Reserve30 belum menciptakan id entitas fisik baru. Cut 100→70+30 conservation, parent/child tags unik, child tidak boleh loading sebelum identity verification.

**Prompt:** gunakan tiket `WM-02` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="wm-03"></a>
## WM-03 · P1 — Konfirmasi tiba dengan scan kosong memindahkan semua roll

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/services/putaway_order_service.py:177](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/putaway_order_service.py#L177)

```text
 176 |                       precondition={"status": {"$in": ["open", "in_transit"]}}, actor=actor_name)
 177 |     scanned = {e.strip().upper() for e in (scanned_epcs or []) if e and e.strip()}
 178 |     arrived, exceptions = [], []
 179 |     for item in order["items"]:
```

[backend/services/putaway_order_service.py:180](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/putaway_order_service.py#L180)

```text
 179 |     for item in order["items"]:
 180 |         if scanned and (item.get("epc") or "").upper() not in scanned:
 181 |             item["status"] = "exception"
 182 |             exceptions.append(item)
```

**Akar masalah.** None dan [] sama-sama menjadi set kosong. Kondisi if scanned gagal sehingga semua item masuk cabang arrived. Dokstring mengatakan EPC diberikan membatasi roll, tetapi explicit empty batch berarti semua diterima.

**Skenario/reproduksi.** PA berisi 10 roll; POST arrival dengan scanned_epcs=[]; seluruh roll berpindah ke gudang tujuan, terbit mutasi/BTG, walau nol EPC ter baca.

**Dampak.** Bukti penerimaan fisik salah dan barang yang tertinggal dianggap sudah tiba.

**Perbaikan yang diminta.** Bedakan field tidak disediakan dari scan kosong. Mode scan: kosong berarti none arrived. Mode manual: aksi ter sendiri dengan permission/alasan dan item selection; no silent all.

**Kriteria selesai.** [] memindahkan0; subset memindahkan subset; None tidak otomatis menerima semua pada flow hardware. Override all mengharuskan reason dan jejak aktor.

**Prompt:** gunakan tiket `WM-03` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="wm-04"></a>
## WM-04 · P1 — Putaway antar-gudang in-transit tidak mengubah bucket stok roll

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/services/putaway_order_service.py:154](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/putaway_order_service.py#L154)

```text
 153 |
 154 | async def dispatch(order_id: str, scope_ids: List[str]) -> Dict[str, Any]:
 155 |     order = await _get(order_id, scope_ids)
 156 |     if order["status"] != "open":
```

[backend/services/putaway_order_service.py:160](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/putaway_order_service.py#L160)

```text
 159 |         "status": "in_transit", "dispatched_at": now_iso(), "updated_at": now_iso()}})
 160 |     await set_journey([i["roll_id"] for i in order["items"]], "putaway_in_transit")
 161 |     return await _get(order_id, scope_ids)
 162 |
```

**Akar masalah.** Dispatch PA hanya mengubah status dokumen dan journey. Roll tetap available di gudang asal sampai arrival; balance/ATP berasal dari roll.status, bukan journey. Barang dalam perjalanan masih dapat dijanjikan dari lokasi asal.

**Skenario/reproduksi.** Dispatch roll available dari Transit ke D; baca inventory/ATP atau lakukan reservasi sebelum arrival: status fisik yang digunakan allocator masih available.

**Dampak.** Double allocation operasional dan on-hand lokasi yang tidak sesuai keberadaan barang.

**Perbaikan yang diminta.** Integrasikan movement PA dengan mesin transfer roll bersama: at_source→in_transit→at_destination, reservation blocked, ownership tetap; movement dan balance rebuild tersinkron.

**Kriteria selesai.** Sesudah PA dispatch ATP source berkurang, owned tidak hilang, transit terlapor; arrival hanya sekali menambah location destination; cancellation/recovery punya state eksplisit.

**Prompt:** gunakan tiket `WM-04` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="wm-05"></a>
## WM-05 · P1 — PA dapat berebut roll dan arrival menulis lokasi tanpa prasyarat roll

**Status bukti:** Risiko konkurensi statis.

**Letak kode dan bukti:**

[backend/services/putaway_order_service.py:129](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/putaway_order_service.py#L129)

```text
 128 |     }
 129 |     await db.putaway_orders.insert_one(dict(order))
 130 |     await set_journey([i["roll_id"] for i in items], "putaway_assigned", {"putaway_order_id": order["id"]})
 131 |     return safe_doc(order)
```

[backend/services/putaway_order_service.py:192](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/putaway_order_service.py#L192)

```text
 191 |     for item in arrived:
 192 |         roll_ops.append(UpdateOne({"id": item["roll_id"]}, {"$set": {
 193 |             "warehouse_id": order["to_warehouse_id"], "bin_id": None, "updated_at": now}}))
 194 |         tag_ops.append(UpdateOne({"roll_id": item["roll_id"], "status": "active"},
```

**Akar masalah.** Create memeriksa journey tag_verified lalu insert PA dan set_journey tanpa claim per roll. Dua PA dapat lolos sebelum journey berubah. Arrival mengunci PA sendiri tetapi update roll hanya id, tidak cek PA yang sedang memiliki roll, asal, status atau version.

**Skenario/reproduksi.** PA A dan B dibuat serentak untuk roll sama ke D/H. Confirm A lalu B: doc claims berbeda tidak mencegah lokasi roll ditimpa.

**Dampak.** Satu roll muncul pada dua instruksi perjalanan dan bisa dianggap tiba di dua gudang.

**Perbaikan yang diminta.** Movement ownership per roll dengan active_movement unique/atomic claim; PA create all-or-none dengan recovery; arrival CAS sesuai movement/source/owner/version.

**Kriteria selesai.** Dua PA satu roll: hanya satu menang; stale PA tidak dapat memindahkan roll lagi; reserved/quarantine/zero roll ditolak sesuai policy.

**Prompt:** gunakan tiket `WM-05` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="wm-06"></a>
## WM-06 · P1 — Scan picking tidak memvalidasi identitas roll dan menerima qty negatif

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/routers/outbound_picking.py:82](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking.py#L82)

```text
  81 | @router.post("/outbound/tasks/{task_id}/scan-pick")
  82 | async def scan_pick_item(
  83 |     task_id: str,
  84 |     request: Request,
```

[backend/routers/outbound_picking.py:112](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking.py#L112)

```text
 111 |     # Update picked qty
 112 |     new_picked_qty = task.get("picked_qty", 0.0) + actual_qty
 113 |     expected_qty = task.get("quantity", 0.0)
 114 |
```

[backend/routers/outbound_picking.py:139](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking.py#L139)

```text
 138 |         "lot": lot or task.get("lot", ""),
 139 |         "roll_id": roll_id or task.get("roll_id", ""),
 140 |         "bin_id": bin_id or task.get("bin_id", ""),
 141 |         "updated_at": now_iso()
```

**Akar masalah.** Endpoint menambah qty task lalu menyimpan roll_id/bin_id/lot dari parameter tanpa memuat roll atau memastikan product/owner/warehouse/reserved_ref/bin cocok. Hanya batas atas qty dicek; actual_qty negatif tidak ditolak. CAS picked_qty sudah ada, tetapi CAS tidak memperbaiki validasi bisnis.

**Skenario/reproduksi.** Pick task produkA dengan roll_id produkB atau randomstring dan qty memenuhi expected; task bisa packing. Pick qty-5 menurunkan progress tanpa reversal audit.

**Dampak.** Bukti picking salah barang dan pencatatan progress dapat dimanipulasi. Dispatch ledger reserved roll tidak menjamin fisik yang dipilih benar.

**Perbaikan yang diminta.** Scan identity server-resolved; validasi roll membership/status/bin/owner serta unit; qty finite>0; koreksi negative via undo event terpisah. Tasks per roll atau manifest yang jelas.

**Kriteria selesai.** Salah SKU/bin/gudang/owner/EPC atau roll tidak allocated ditolak. Negative/NaN/inf/zero ditolak; concurrent good scans tetap tidak hilang.

**Prompt:** gunakan tiket `WM-06` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="wm-07"></a>
## WM-07 · P1 — Stock opname per bin memakai expected seluruh gudang dan membolehkan duplikasi

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/routers/cycle_count.py:119](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cycle_count.py#L119)

```text
 118 |         "owner_entity_id": owner,
 119 |         "expected_qty": float(balance.get("on_hand_qty", 0)) if balance else 0.0,
 120 |         "actual_qty": None,
 121 |         "status": "pending",
```

[backend/routers/cycle_count.py:117](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cycle_count.py#L117)

```text
 116 |         "product_name": product["name"],
 117 |         "bin_id": payload.bin_id,
 118 |         "owner_entity_id": owner,
 119 |         "expected_qty": float(balance.get("on_hand_qty", 0)) if balance else 0.0,
```

[backend/routers/cycle_count.py:36](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cycle_count.py#L36)

```text
  35 | class CycleCountItemUpdate(BaseModel):
  36 |     actual_qty: float
  37 |     notes: str = ""
  38 |
```

**Akar masalah.** Bin disimpan sebagai metadata tetapi expected diperoleh dari inventory_balances produk×warehouse×owner, tanpa bin. Item sama dapat ditambahkan berkali-kali; actual_qty tidak punya ge=0. Discrepancy kemudian diterapkan perbaris.

**Skenario/reproduksi.** Warehouse100 dengan binA40/binB60; hitung binA aktual 40, expected 100 menghasilkan shortage60 palsu. Dua item identik dengan expected 100/actual 90 masing-masing dapat menerapkan -10 dua kali. Nilai actual negatif juga diterima schema.

**Dampak.** Salah adjustment permanen akibat definisi scope hitung, bukan selisih fisik.

**Perbaikan yang diminta.** Snapshot count scope dari rolls perbin/owner; unique count key, freeze/version & blind count policy; validasi nonnegative finite quantity. Jangan mengulang discrepancy agregat perbin.

**Kriteria selesai.** BinA40 menghasilkan diff0; duplicate count key409; negative/NaN ditolak. Approve dua bin menghitung perbin tanpa double reduction.

**Prompt:** gunakan tiket `WM-07` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="wm-08"></a>
## WM-08 · P1 — Adjustment shortage dapat parsial tetapi sesi tetap approved

**Status bukti:** Terbukti statis; konkurensi belum dieksekusi.

**Letak kode dan bukti:**

[backend/services/roll_service.py:1602](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L1602)

```text
1601 |
1602 | async def apply_cycle_count_adjustment(
1603 |     product_id: str, warehouse_id: str, owner_entity_id: str, diff: float,
1604 |     session_id: str, created_by: str = "System",
```

[backend/routers/cycle_count.py:231](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cycle_count.py#L231)

```text
 230 |         owner = discrepancy.get("owner_entity_id") or DEFAULT_ENTITY_ID
 231 |         await apply_cycle_count_adjustment(
 232 |             discrepancy["product_id"], session["warehouse_id"], owner, diff, session_id,
 233 |             created_by=actor["name"],
```

**Akar masalah.** Helper shortage mengurangi roll dengan read→set tanpa CAS; kandidat status tidak mencakup semua bucket fisik yang membentuk on_hand. Kekurangan residual hanya warning dan return jumlah aktual; approve mengabaikan return dan menandai seluruh sesi approved.

**Skenario/reproduksi.** Expected mencakup picked/packed tetapi shortage hanya memiliki cukup available/reserved sebagian. Adjustment yang berhasil kurang dari discrepancy, namun dokumen menyatakan approved. Reservation simultan dapat ditimpa.

**Dampak.** Bukti opname tidak sama dengan adjustment tersimpan; stok dan transaksi terkait saling bertentangan.

**Perbaikan yang diminta.** Adjustment by roll/count line dengan CAS dan target lengkap; periksa actual_applied==requested, durable recovery; selisih yang belum diterapkan tetap exception. Setiap stock status punya policy terpusat.

**Kriteria selesai.** Tidak cukup eligible stock harus fail/exception tanpa approve palsu. Parallel count vs reservation tidak over write. Detail tampil requested/applied/unresolved per line.

**Prompt:** gunakan tiket `WM-08` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="wm-09"></a>
## WM-09 · P2 — Penerimaan exception PA tidak menulis mutasi transfer

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/services/putaway_order_service.py:228](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/putaway_order_service.py#L228)

```text
 227 |
 228 | async def resolve_exception(order_id: str, roll_ids: List[str], action: str,
 229 |                             scope_ids: List[str], actor_name: str) -> Dict[str, Any]:
 230 |     """Checker (handheld scan ulang di ERP): `accept` = barang ternyata sah → pindahkan;
```

**Akar masalah.** Resolve accept memindahkan warehouse roll/tag dan rebuild balance, tetapi tidak menulis inventory_movements seperti confirm_arrival. Jalur alternatif menghasilkan perubahan fisik yang tidak ada di ledger movement.

**Skenario/reproduksi.** Arrival missed satu roll; manager accept exception. Lokasi dan balance berubah tetapi history transfer out/in untuk roll itu tidak muncul.

**Dampak.** SSOT roll dan jejak mutasi tidak bisa di rekonsiliasi; investigasi gate salah/missing menjadi sulit.

**Perbaikan yang diminta.** Gunakan posting movement tunggal yang sama untuk arrival normal/exception; reference PA/BTG, override reason, qty snapshot dan actor; update counters dari hasil nyata.

**Kriteria selesai.** Accept exception menulis tepat satu out/in pasangan, rebuild dua lokasi dan counters; retry tidak menggandakan mutasi.

**Prompt:** gunakan tiket `WM-09` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="fn-01"></a>
## FN-01 · P1 — Landed cost menghitung anak split dua kali

**Status bukti:** Direproduksi.

**Letak kode dan bukti:**

[backend/services/landed_cost_service.py:62](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/landed_cost_service.py#L62)

```text
  61 |         return []
  62 |     query: Dict[str, Any] = {"acquired.ref_id": {"$in": list(po_ids)},
  63 |                              "status": {"$nin": ["scrapped", "cancelled"]}}
  64 |     if entity_id and entity_id != "all":
```

[backend/services/landed_cost_service.py:159](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/landed_cost_service.py#L159)

```text
 158 |         before = await db.inventory_rolls.find_one(
 159 |             {"id": a["roll_id"]},
 160 |             {"_id": 0, "id": 1, "roll_no": 1, "unit_cost": 1, "base_unit_cost": 1,
 161 |              "length_remaining": 1, "owner_entity_id": 1, "entity_id": 1})
```

[backend/services/landed_cost_service.py:173](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/landed_cost_service.py#L173)

```text
 172 |              "id": {"$ne": a["roll_id"]},
 173 |              "landed_cost_refs": {"$ne": voucher_number}},
 174 |             {"$inc": {"unit_cost": a["per_unit"]},
 175 |              "$set": {"updated_at": now_iso()},
```

**Akar masalah.** Target PO dapat berisi parent dan child yang mewarisi acquired.ref_id. Apply parent mempropagasi per_unit ke anak; loop kemudian melakukan increment langsung anak tanpa guard landed_cost_refs. Guard hanya ada pada update_many descendant.

**Skenario/reproduksi.** FN-01: parent 70 dan child 30, unit_cost10, voucher100 basis qty. Alokasi70/30 (per unit 1) tetapi parent+1, child+2; nilai stok naik130. Reproduksi menjalankan compute/apply asli dengan DB mock.

**Dampak.** Persediaan/HPP/margin overstated meski total allocations pada voucher tetap 100 dan jurnal voucher bisa seimbang.

**Perbaikan yang diminta.** Pilih target ekonomi disjoint: semua physical fragments tanpa propagate, atau root-level propagate yang tidak dibilling ulang. Per-voucher per roll idempotency dan conservation nilai; rekonsiliasi voucher→rolls→GL.

**Kriteria selesai.** Parent 70+child 30 voucher100 menghasilkan nilai+100; multiple levels, roll sold, partial/scrapped, retry dan order loop berbeda tidak mengubah hasil.

**Prompt:** gunakan tiket `FN-01` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="fn-02"></a>
## FN-02 · P1 — 3-way match lolos overbilling dari baris produk duplikat

**Status bukti:** Direproduksi.

**Letak kode dan bukti:**

[backend/services/vendor_bill_service.py:78](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/vendor_bill_service.py#L78)

```text
  77 |         received = float(po_it.get("received_qty", 0) or 0)
  78 |         prior = float(billed_so_far.get(pid, 0) or 0)
  79 |         billed = float(bi.get("billed_qty", bi.get("quantity", 0)) or 0)
  80 |         po_price = float(po_it.get("price", 0) or 0)
```

[backend/services/vendor_bill_service.py:73](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/vendor_bill_service.py#L73)

```text
  72 |     warning = False
  73 |     for bi in priced_items:
  74 |         pid = bi.get("product_id")
  75 |         po_it = po_items.get(pid, {})
```

[backend/routers/vendor_bills.py:204](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vendor_bills.py#L204)

```text
 203 |     raw_items: List[Dict[str, Any]] = []
 204 |     for line in payload.items:
 205 |         po_it = po_items.get(line.product_id)
 206 |         if not po_it:
```

**Akar masalah.** Setiap baris membandingkan qty dengan received-prior yang sama; qty baris sebelumnya pada bill ini tidak diakumulasikan. Router/schema tidak menolak duplicate product lines pada flow create yang diperiksa. PO mapping byproduct juga menghilangkan id entitas line PO.

**Skenario/reproduksi.** FN-02: receipt 100, prior 0, dua billed60 pada produk sama, toleransi0; match_status matched walau total 120. Satu billed120 berhasil diblok sebagai kontrol pembanding.

**Dampak.** AP tagihan melebihi barang diterima; 3-way matching memberi rasa aman palsu.

**Perbaikan yang diminta.** Cocokkan PO line ID dan receipt line; aggregate current bill+posted prior+concurrent pending reservations. Duplicate explicit ditolak atau di jumlah konsisten; submit/approve revalidasi atomik.

**Kriteria selesai.** 60+60 vs100 blocked; PO produk sama dua harga tidak over write; dua bill bersamaan tidak melewati receipt cap. Credit note/cancel mengembalikan billable sesuai policy.

**Prompt:** gunakan tiket `FN-02` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="fn-03"></a>
## FN-03 · P1 — WAC menjumlah panjang dan cost lintas unit tanpa konversi

**Status bukti:** Direproduksi.

**Letak kode dan bukti:**

[backend/services/costing_service.py:70](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/costing_service.py#L70)

```text
  69 |             continue
  70 |         total_len += ln
  71 |         cost = _roll_cost(r)
  72 |         if cost > 0:
```

[backend/services/costing_service.py:74](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/costing_service.py#L74)

```text
  73 |             costed_len += ln
  74 |             total_val += cost * ln
  75 |             # base_unit_cost = HPP sebelum landed; bila kosong anggap = cost (landed 0).
  76 |             b = float(r.get("base_unit_cost") or 0) or cost
```

**Akar masalah.** wac_for_product menghitung total raw length_remaining lalu total_value/raw length tanpa membaca roll.unit. Hasil diberi base_unit produk sehingga yard dan meter seolah unit sama. Valuation cost per roll dapat benar sendiri; kesalahan muncul denominator dan cost per base.

**Skenario/reproduksi.** FN-03: 1yard cost 91.44/yard dan1meter cost 100/m, keduanya100/m. Fungsi mengembalikan qty2 dan WAC 95.72; benar qty 1.9144m dan WAC 100/m.

**Dampak.** Margin, pricing floor, valuasi retur/fallback HPP dan laporan stok salah pada mixed-UOM.

**Perbaikan yang diminta.** Normalize quantity ke base unit memakai satu resolver konversi; nilai tetap qty_native×cost_native. Snapshot conversion di transaksi; missing/invalid conversion hard exception, jangan penjumlahan raw.

**Kriteria selesai.** Mixed meter/yard/kg sesuai konversi produk menghasilkan nilai/qtybase yang benar; unknown conversion tidak dianggap1. Pembagian dan rounding diuji pada partial roll.

**Prompt:** gunakan tiket `FN-03` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="fn-04"></a>
## FN-04 · P1 — Arus kas seimbang tetapi klasifikasi transaksi nonkas salah

**Status bukti:** Direproduksi dua skenario.

**Letak kode dan bukti:**

[backend/services/cash_flow_service.py:61](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cash_flow_service.py#L61)

```text
  60 |         d_raw = _raw(end_agg, code) - _raw(begin_agg, code)
  61 |         cash_effect = round(-d_raw, 2)
  62 |
  63 |         if _is_cash(code):
```

[backend/services/cash_flow_service.py:75](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cash_flow_service.py#L75)

```text
  74 |         elif atype == "asset":
  75 |             if code.startswith("1-2"):
  76 |                 investing.append(line)
  77 |             else:
```

**Akar masalah.** Laporan membagi perubahan saldo semua akun nonkas berdasarkan prefix. Id entitas neraca menjamin total delta kas, tetapi tidak mengidentifikasi apakah transaksi benar-benar kas atau nonkas. Penyusutan, reclass dan beli aset kredit salah ditempatkan; cash codes juga fixed dua akun.

**Skenario/reproduksi.** FN-04: Dr beban100/Cr akumulasi penyusutan100 → CFO-100 CFI+100, reconciled true; seharusnya keduanya0. FN-04B: beli aset kredit100 → CFO+100 CFI-100, padahal tanpa arus kas.

**Dampak.** Laporan arus kas menyesatkan walau total kas benar. Flag reconciled bukan bukti IAS7/PSAK compliance.

**Perbaikan yang diminta.** Bangun noncash adjustments dan business classification berbasis journal/source/account metadata; exclude noncash investing/financing dan disclose; cash equivalence tidak hardcoded prefix semata.

**Kriteria selesai.** Depresiasi/beli aset kredit/reclass/landed accrual memberi nol cashflow; actual cash asset purchase masuk CFI; accrual sale+receipt CFO benar; angka diverifikasi fixture akuntan. Acuan IAS7 tercantum di fit-gap.

**Prompt:** gunakan tiket `FN-04` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="fn-05"></a>
## FN-05 · P1 — Master akun laporan menggabungkan override entitas dengan last-write-wins

**Status bukti:** Direproduksi.

**Letak kode dan bukti:**

[backend/services/financial_statement_service.py:41](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/financial_statement_service.py#L41)

```text
  40 | async def _accounts_map() -> Dict[str, Dict[str, Any]]:
  41 |     rows = await db.gl_accounts.find({}, {"_id": 0}).to_list(2000)
  42 |     return {a["code"]: a for a in rows}
  43 |
```

[backend/services/financial_statement_service.py:42](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/financial_statement_service.py#L42)

```text
  41 |     rows = await db.gl_accounts.find({}, {"_id": 0}).to_list(2000)
  42 |     return {a["code"]: a for a in rows}
  43 |
  44 |
```

**Akar masalah.** Scope journal sudah dipisahkan, tetapi _accounts_map membaca seluruh COA dan key hanya code. Override kode sama entitas B dapat menjadi nama/type laporan A, tergantung urutan cursor. Scope laporan tidak diteruskan ke resolver akun.

**Skenario/reproduksi.** FN-05: kode 4-1000 A income, B expense; map menghasilkan B sehingga revenue A bisa masuk expense. Bahkan jika konfigurasi hanya mengganti nama, nama badan usaha lain tetap digunakan.

**Dampak.** Neraca/P&L dan closing dapat salah klasifikasi; isolasi journal tidak cukup menjaga isolasi chart of accounts.

**Perbaikan yang diminta.** Resolve effective COA per entity: global default + exact entity override; enforce invariant type/code bila override dibatasi. Consolidation agregasi account dimension eksplisit.

**Kriteria selesai.** Laporan A selalu memakai akun A/global; urutan insert tidak mengubah hasil; kode custom hanya A tidak mengubah B; consolidation tidak mengambil random override.

**Prompt:** gunakan tiket `FN-05` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="fn-06"></a>
## FN-06 · P2 — Jurnal manual menolak akun custom entitas dan mengabaikan override

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/services/gl_service.py:567](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L567)

```text
 566 |     accounts = {a["code"]: a for a in await db.gl_accounts.find(
 567 |         {"code": {"$in": codes}, "entity_id": {"$in": [None, ""]}},
 568 |         {"_id": 0}).to_list(2000)}
 569 |     for c in codes:
```

**Akar masalah.** create_manual_entry memuat hanya akun global meski master mendukung akun per entitas. Akun valid milik entitas dipilih di UI dapat ditolak; override inactive/header badan usaha juga tidak diperiksa jika global tetap active/postable.

**Skenario/reproduksi.** Buat akun custom khususA lalu post manual: akun tidak ditemukan. Override global account A inactive dapat tetap diposting memakai record global.

**Dampak.** COA dan posting punya SSOT aturan berbeda; konfigurasi entitas tidak ditaati.

**Perbaikan yang diminta.** Gunakan resolver akun effective yang sama untuk list, manual, auto post dan reports; validasi active/postable/type sebelum entry.

**Kriteria selesai.** Custom A berhasil di A, ditolak B; inactive override menghalangi post; global default bekerja saat tidak ada override.

**Prompt:** gunakan tiket `FN-06` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="fn-07"></a>
## FN-07 · P1 — Kas manual tidak langsung berjurnal dan void kas tidak membalik jurnal

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/routers/cash.py:108](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash.py#L108)

```text
 107 | @router.post("/cash-transactions")
 108 | async def create_cash_transaction(payload: CashTransactionCreate, request: Request) -> Dict[str, Any]:
 109 |     """Catat transaksi kas masuk/keluar."""
 110 |     actor = await require_permission(request, "cash", "create")
```

[backend/routers/cash.py:156](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash.py#L156)

```text
 155 | @router.post("/cash-transactions/{txn_id}/void")
 156 | async def void_cash_transaction(txn_id: str, request: Request) -> Dict[str, Any]:
 157 |     """Batalkan/void transaksi kas (saldo tidak lagi dihitung)."""
 158 |     actor = await require_permission(request, "cash", "delete")
```

**Akar masalah.** Create kas menyimpan cash_transactions tanpa posting GL pada jalur itu. Backfill/sync dapat membuat jurnal kemudian, tetapi void kas hanya mengubah status transaksi. Void generic juga perlu membedakan transaksi berasal dari receipt/AP agar subledger sumber tidak ditinggal aktif.

**Skenario/reproduksi.** Input kas masuk100 → dashboard kas naik tetapi GL kas belum naik sampai sync. Setelah sync, void kas → dashboardturun sedangkan JE tetap aktif. Jalur backfill bukan reversal.

**Dampak.** Cash ledger ≠ GL dan receipt/payment dapat mempunyai status berbeda. Finance belum bisa dipercaya sebagai real-time buku final.

**Perbaikan yang diminta.** Posting journal+cash sebagai satu durable operation; void sumber harus reversal jurnal dan unwind sumber sesuai lifecycle. Cash autogenerated hanya dibatalkan melalui dokumen asal; no generic source bypass.

**Kriteria selesai.** Create/void manual dan receipt/AP derived diuji cashledger=GL sesudah setiap aksi, retry/failure dan periode tertutup. Sync tidak melahirkan double posting/revive void.

**Prompt:** gunakan tiket `FN-07` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="fn-08"></a>
## FN-08 · P1 — Opening balance rekening dan perubahan rekening tidak tersambung GL

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/services/bank_service.py:78](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/bank_service.py#L78)

```text
  77 |         "entity_id": payload.entity_id or DEFAULT_ENTITY_ID,
  78 |         "opening_balance": round(float(payload.opening_balance or 0), 2),
  79 |         "currency": payload.currency or "IDR",
  80 |         "note": (payload.note or "").strip(),
```

[backend/services/bank_service.py:94](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/bank_service.py#L94)

```text
  93 |     upd = {k: v for k, v in patch.items() if v is not None}
  94 |     if "opening_balance" in upd:
  95 |         upd["opening_balance"] = round(float(upd["opening_balance"]), 2)
  96 |     if "name" in upd:
```

**Akar masalah.** Saldo awal rekening disimpan sebagai field yang dipakai menghitung saldo berjalan. Create/update opening_balance tidak membuat jurnal pembukaan atau koreksi, sehingga buku rekening dan GL dapat memakai basis awal yang berbeda.

**Skenario/reproduksi.** Buat rekening dengan saldo awal Rp1 juta: ledger rekening bertambah, tetapi operasi ini tidak menambah GL. Ubah menjadi Rp2 juta: saldo historis rekening bergeser tanpa jurnal perubahan.

**Dampak.** Rekonsiliasi rekening, arus kas dan neraca dapat berbeda meskipun setiap layar tampak normal.

**Perbaikan yang diminta.** Pembukaan rekening harus terikat jurnal, tanggal, pemetaan akun dan entitas. Kunci saldo awal setelah posting; koreksi melalui adjustment/reversal berizin. Periksa juga account_id pada penerimaan/pembayaran agar masuk rekening yang benar.

**Kriteria selesai.** Saldo awal rekening sesuai GL; edit historis tidak diam-diam mengubah saldo. Transfer mempunyai dua sisi, dan penerimaan AR/AP muncul pada ledger rekening yang sesuai.

**Prompt:** gunakan tiket `FN-08` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="fn-09"></a>
## FN-09 · P1 — Void jurnal manual melewati penguncian periode

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/services/gl_service.py:673](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L673)

```text
 672 |
 673 | async def void_entry(entry_id: str, actor: Dict[str, Any]) -> Optional[Dict[str, Any]]:
 674 |     je = await db.journal_entries.find_one({"id": entry_id}, {"_id": 0})
 675 |     if not je:
```

[backend/services/gl_service.py:687](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L687)

```text
 686 |     # F-9 — void jurnal dalam periode tertutup juga mengubah angka → tandai stale
 687 |     await _mark_stale_closings(je.get("entity_id", ""), je.get("date", ""))
 688 |     return await db.journal_entries.find_one({"id": entry_id}, {"_id": 0})
 689 |
```

**Akar masalah.** Posting memanggil enforce_closed_period_guard, tetapi void_entry tidak. Menandai closing stale setelah void tidak menggantikan izin membuka periode. Route void yang diperiksa juga tidak menjalankan guard periode sendiri.

**Skenario/reproduksi.** Tutup bulan yang berisi jurnal manual, lalu void jurnal bulan tersebut menggunakan izin accounting manage tanpa unlock. Saldo laporan berubah walaupun periode masih tertutup.

**Dampak.** Laporan yang sudah ditutup dapat berubah tanpa persetujuan pembukaan periode.

**Perbaikan yang diminta.** Terapkan kebijakan periode yang sama pada void/reversal. Untuk periode terkunci, utamakan reversal pada periode berjalan sesuai kebijakan buku. Pembukaan periode memerlukan hak, alasan dan audit; mutation status/source memakai CAS.

**Kriteria selesai.** Periode tertutup tidak berubah melalui void tanpa otorisasi unlock. Reversal periode berjalan mempertahankan jurnal asli dan jejak pembatalannya.

**Prompt:** gunakan tiket `FN-09` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="fn-10"></a>
## FN-10 · P1 — Pembayaran AR dapat sukses walau jurnal kas gagal

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/services/ar_receipt_service.py:71](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ar_receipt_service.py#L71)

```text
  70 |
  71 | async def _post_cash_in(receipt: Dict[str, Any], actor: Dict[str, Any]) -> Optional[str]:
  72 |     """Posting kas masuk untuk penerimaan AR. Mengembalikan id cash_transaction."""
  73 |     amt = round(float(receipt.get("amount", 0) or 0), 2)
```

[backend/services/ar_receipt_service.py:106](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ar_receipt_service.py#L106)

```text
 105 |         await _gl.post_cash_transaction(cdoc)
 106 |     except Exception as exc:  # noqa: BLE001 — kwitansi tetap sah; backfill akan menyusul
 107 |         logger.warning("[_post_cash_in] efek samping gagal diabaikan: %s", exc)  # KN-C10
 108 |     return cdoc["id"]
```

**Akar masalah.** _post_cash_in memasukkan transaksi kas lalu mencoba posting GL dalam try/except yang mengabaikan kegagalan. Receipt dan alokasi pesanan dapat terlanjur berubah ketika GL ditolak. Tidak terlihat outbox posting durable pada fungsi tersebut.

**Skenario/reproduksi.** Buat gl.post_cash_transaction melempar error: receipt/kas dapat tetap dibuat sementara GL belum mencatat kas. Sync mungkin memperbaiki kemudian, tetapi fungsi ini tidak memberikan jaminan penyelesaian atau status pending yang dapat dipantau.

**Dampak.** Piutang, uang muka, ledger kas dan GL dapat mempunyai hasil berbeda; akurasi laporan dan closing terpengaruh.

**Perbaikan yang diminta.** Gunakan operasi bisnis atomik atau saga durable dengan posting outbox dan status pending/failed. Preflight periode dan gunakan compensation yang aman; kegagalan finansial tidak boleh ditampilkan sebagai sukses final.

**Kriteria selesai.** Kegagalan GL menghasilkan status pending/failed yang terlihat atau rollback konsisten. Retry tidak menggandakan jurnal, dan receipt belum final sebelum posting wajib selesai.

**Prompt:** gunakan tiket `FN-10` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="fn-11"></a>
## FN-11 · P1 — HPP per shipment memakai rata-rata semua roll pesanan

**Status bukti:** Terbukti statis; angka contoh deterministik.

**Letak kode dan bukti:**

[backend/services/gl_service.py:992](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L992)

```text
 991 |         return None
 992 |     cogs = round(qty * await _order_item_unit_cost(order, it), 2)
 993 |     if cogs <= EPS:
 994 |         return None
```

[backend/services/gl_service.py:1070](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L1070)

```text
1069 |
1070 | async def _order_item_unit_cost(order: Dict[str, Any], item: Dict[str, Any]) -> float:
1071 |     """F-7 — cost per unit untuk 1 baris order (engine costing TUNGGAL).
1072 |
```

**Akar masalah.** post_shipment_cogs memakai _order_item_unit_cost untuk baris pesanan, yang merata-ratakan roll milik order. Ia tidak mengambil snapshot biaya roll pada shipment aktual. Unit biaya juga harus sesuai unit kuantitas shipment.

**Skenario/reproduksi.** Pesanan memiliki dua roll masing-masing 100 meter, dengan biaya 10 dan 30 per meter. Shipment pertama hanya membawa roll murah: rata-rata 20 menghasilkan HPP 2.000, sedangkan biaya roll keluar 1.000. Total dua shipment mungkin akhirnya sama, tetapi margin/periode masing-masing salah.

**Dampak.** HPP shipment parsial dan nilai stok tersisa dapat berbeda dari subledger roll yang benar-benar keluar.

**Perbaikan yang diminta.** Simpan alokasi shipment per roll, jumlah dalam unit asal/base, serta biaya yang dibekukan saat dispatch. Jurnal berasal dari jumlah extended cost aktual. Koreksi landed cost setelah shipment mengikuti kebijakan variance eksplisit.

**Kriteria selesai.** Shipment roll murah mencatat HPP 1.000 dan shipment roll mahal 3.000. Edit biaya roll tidak mengubah laporan historis tanpa event koreksi. Partial roll, mixed UOM dan retur mengacu snapshot yang sama.

**Prompt:** gunakan tiket `FN-11` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="fn-12"></a>
## FN-12 · P1 — Edit master aset mengubah nilai/akun tanpa mengoreksi jurnal perolehan

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/services/fixed_asset_service.py:141](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/fixed_asset_service.py#L141)

```text
 140 |
 141 | async def update_asset(asset_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
 142 |     a = await db.fin_fixed_assets.find_one({"id": asset_id}, {"_id": 0})
 143 |     if not a:
```

**Akar masalah.** update_asset mengizinkan perubahan field finansial tertentu tanpa menyelaraskan jurnal perolehan yang sudah ada. Pembatasan saat depresiasi bukan pengganti amendment terhadap financial event perolehan.

**Skenario/reproduksi.** Aset sudah diperoleh dengan nilai 100, belum didepresiasi. Ubah nilai menjadi 150 atau akun aset: kartu/basis depresiasi berubah, tetapi jurnal perolehan tetap 100 pada akun lama.

**Dampak.** Register aset, basis depresiasi dan GL aset dapat berbeda.

**Perbaikan yang diminta.** Kunci field finansial setelah kapitalisasi. Perubahan memakai amendment/reclassification/reversal yang berizin dan mematuhi periode; edit nonfinansial tetap dapat dilakukan biasa.

**Kriteria selesai.** Nilai perolehan dan akumulasi depresiasi pada register sesuai GL. Edit biaya/tanggal/akun yang diizinkan menghasilkan jurnal koreksi yang benar atau ditolak dengan alasan jelas.

**Prompt:** gunakan tiket `FN-12` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="fn-13"></a>
## FN-13 · P1 — Close periode dapat berjalan dua kali secara bersamaan

**Status bukti:** Risiko konkurensi statis.

**Letak kode dan bukti:**

[backend/services/closing_service.py:253](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/closing_service.py#L253)

```text
 252 |
 253 | async def close_period(period_type: str, period_key: str, actor: Dict[str, Any],
 254 |                        entity_id: str, note: str = "") -> Dict[str, Any]:
 255 |     if period_type not in ("month", "year"):
```

[backend/services/closing_service.py:270](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/closing_service.py#L270)

```text
 269 |
 270 |     closing_id = new_id("close")
 271 |     je = None
 272 |     if lines:
```

[backend/services/closing_service.py:312](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/closing_service.py#L312)

```text
 311 |     }
 312 |     await db.period_closings.insert_one(rec)
 313 |     return safe_doc(rec)
 314 |
```

**Akar masalah.** close_period mengecek penutupan sebelumnya, kemudian membuat jurnal dan record tanpa claim atomik atas periode. Unique source jurnal tidak cukup karena setiap panggilan membuat closing_id baru. Bootstrap yang diperiksa tidak menetapkan unique logical closing key.

**Skenario/reproduksi.** Dua request bersamaan melihat periode belum ditutup dan laba yang sama. Keduanya dapat membuat jurnal penutup laba 100 sehingga laba ditahan dipindah 200. Ini interleaving dari source, belum uji konkurensi Mongo.

**Dampak.** Closing ganda dapat merusak laba ditahan dan menghasilkan periode tumpang tindih. Tombol UI yang dinonaktifkan tidak melindungi server.

**Perbaikan yang diminta.** Gunakan operation key durable berdasarkan entitas, tipe dan periode, policy overlap bulan/tahun, CAS lifecycle/revision dan source jurnal idempotent. Pulihkan failure antara posting jurnal dan penyimpanan closing record.

**Kriteria selesai.** Parallel close/reclose dan overlap bulan/tahun hanya menghasilkan satu revision sah. Failure injection tidak meninggalkan jurnal orphan/ganda; reopen mengikuti prosedur pemulihan yang tervalidasi.

**Prompt:** gunakan tiket `FN-13` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="fn-14"></a>
## FN-14 · P1 — Stock opname tidak memposting variance GL dan surplus dibuat tanpa cost

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/services/roll_service.py:1602](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L1602)

```text
1601 |
1602 | async def apply_cycle_count_adjustment(
1603 |     product_id: str, warehouse_id: str, owner_entity_id: str, diff: float,
1604 |     session_id: str, created_by: str = "System",
```

[backend/routers/cycle_count.py:224](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cycle_count.py#L224)

```text
 223 |             + ". Buka kembali sesi dan hitung ulang item tersebut sebelum disetujui."))
 224 |     for discrepancy in session.get("discrepancies", []):
 225 |         diff = float(discrepancy["difference"])
 226 |         if abs(diff) < 0.001:
```

**Akar masalah.** Approval opname mengubah roll dan rebuild balance tanpa jurnal selisih stok. Surplus yang dibuat lewat create_inbound_roll tidak diberi unit_cost sehingga menjadi stok bernilai nol. Opening-equity true-up bukan pengganti klasifikasi selisih operasional.

**Skenario/reproduksi.** Shortage 10 meter pada biaya 100 mengurangi subledger 1.000 tetapi GL inventory tetap. Surplus 10 meter menambah kuantitas tanpa valuation yang jelas.

**Dampak.** Quantity/value subledger tidak sesuai GL; kerugian stok tidak masuk periode yang tepat dan margin berikutnya dapat salah.

**Perbaikan yang diminta.** Tetapkan valuation policy per selisih yang disetujui pemilik buku. Kekurangan umumnya mengurangi inventory dan mencatat stock loss; surplus mengikuti klasifikasi kebijakan. Wajib ada snapshot biaya, reason dan tautan jurnal.

**Kriteria selesai.** Setiap adjustment mempunyai nilai dan jurnal yang sesuai serta dapat direkonsiliasi. Zero cost memerlukan alasan/override eksplisit; shortage roll reserved/picked tidak diam-diam merusak pesanan.

**Prompt:** gunakan tiket `FN-14` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="fn-15"></a>
## FN-15 · P2 — Helper autopost tidak menegakkan invariant jurnal di pintu insert

**Status bukti:** Kelemahan kontrol statis.

**Letak kode dan bukti:**

[backend/services/gl_service.py:503](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L503)

```text
 502 |                         ref: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
 503 |     """Insert jurnal seimbang. Caller MEMASTIKAN balance (helper auto-post).
 504 |     `ref` (opsional) = tautan dokumen induk, mis. {"order_id": ...} untuk jurnal per surat jalan."""
 505 |     names = await _account_names([l["account_code"] for l in lines])
```

[backend/services/gl_service.py:508](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L508)

```text
 507 |     total_debit = round(sum(l["debit"] for l in norm), 2)
 508 |     total_credit = round(sum(l["credit"] for l in norm), 2)
 509 |     number = await next_doc_number("journal_entries", "number", "JE-", entity_id=entity_id)
 510 |     doc = {
```

**Akar masalah.** _insert_entry menormalisasi angka lalu menulis posted tanpa menolak debit/kredit yang berbeda, angka nonfinite, negatif atau akun yang tidak layak posting. Setiap caller diminta menjaga sendiri. Ini kelemahan pintu kontrol, bukan bukti seluruh autopost saat ini tidak seimbang.

**Skenario/reproduksi.** Caller baru atau edge case mengirim baris tidak seimbang: helper tetap dapat posting jika guard periode lolos. Keamanan ledger tidak seharusnya bergantung pada komentar tanggung jawab caller.

**Dampak.** Satu cacat formula dapat langsung menghasilkan jurnal rusak tanpa fail-fast.

**Perbaikan yang diminta.** Gunakan validator pusat dengan Decimal/scaled amount, equality setelah rounding, resolusi akun effective, tanggal/entitas/periode serta source identity. Tambahkan fixture bermakna pada setiap jenis autopost.

**Kriteria selesai.** Jurnal tidak seimbang, NaN/Infinity, angka negatif yang tidak sesuai model, akun hilang/inactive/nonpostable dan baris dual-sided ditolak sebelum insert. Posting valid tetap menghasilkan total yang tepat.

**Prompt:** gunakan tiket `FN-15` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="fn-16"></a>
## FN-16 · P2 — Neraca default tidak membatasi tanggal meski diberi label hari ini

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/services/financial_statement_service.py:174](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/financial_statement_service.py#L174)

```text
 173 |
 174 | async def balance_sheet(as_of: Optional[str] = None,
 175 |                         compare_as_of: Optional[str] = None,
 176 |                         scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
```

**Akar masalah.** Saat as_of tidak diberikan, filter tanggal tidak dipasang pada aggregate; respons memakai tanggal sekarang sebagai label as_of. Jurnal bertanggal masa depan dapat masuk neraca yang terlihat berlaku hari ini. Format tanggal/timezone juga harus konsisten.

**Skenario/reproduksi.** Tambahkan jurnal bulan depan lalu buka neraca tanpa as_of. Query tanpa cutoff dapat memasukkannya, sedangkan permintaan dengan tanggal hari ini mengecualikannya.

**Dampak.** Saldo dashboard dan laporan bertanggal eksplisit dapat berbeda tanpa transaksi baru; label tanggal laporan menyesatkan.

**Perbaikan yang diminta.** Resolve effective_as_of sekali dan gunakan pada filter serta label. Validasi tanggal jurnal dengan format/timezone yang jelas; dokumentasikan default laporan finansial secara konsisten.

**Kriteria selesai.** Jurnal masa depan tidak masuk neraca default hari ini, tetapi masuk bila as_of memang masa depan. Uji batas akhir hari/timezone; label tanggal sama dengan cutoff query.

**Prompt:** gunakan tiket `FN-16` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="gn-01"></a>
## GN-01 · P1 — Idempotency tidak terikat user cookie, entitas dan payload

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/idempotency.py:32](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/idempotency.py#L32)

```text
  31 |             return await call_next(request)
  32 |         who = request.headers.get("authorization", "")[-24:] or request.cookies.get("kn_session", "")[-24:]
  33 |         doc_id = f"{key}|{request.method}|{request.url.path}|{who}"
  34 |         now = datetime.now(timezone.utc)
```

[backend/dependencies.py:9](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/dependencies.py#L9)

```text
   8 |
   9 | SESSION_COOKIE = "session_token"
  10 |
  11 | # FASE E-1 (E1.6) — metode yang MENGUBAH data; dipakai penjaga kunci-tulis entitas.
```

[backend/idempotency.py:33](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/idempotency.py#L33)

```text
  32 |         who = request.headers.get("authorization", "")[-24:] or request.cookies.get("kn_session", "")[-24:]
  33 |         doc_id = f"{key}|{request.method}|{request.url.path}|{who}"
  34 |         now = datetime.now(timezone.utc)
  35 |         try:
```

**Akar masalah.** Middleware membaca cookie kn_session, sementara autentikasi memakai session_token. Pengguna cookie tanpa Authorization mempunyai who kosong yang sama. Kunci tidak memuat entitas atau hash payload, dan respons cache dikembalikan sebelum autentikasi endpoint berjalan.

**Skenario/reproduksi.** User A menyimpan respons untuk key K dan path P. User B yang memakai cookie dengan key/path sama dapat menerima respons A; caller yang mengetahui key juga dapat mencoba replay tanpa autentikasi ulang. Mengganti entitas atau isi request dengan key sama tidak menghasilkan validasi mismatch. UUID acak mengurangi tabrakan kebetulan, tetapi tidak memperbaiki isolasi.

**Dampak.** Respons transaksi dapat bocor atau diulang dalam konteks yang salah, terutama pada antrean offline gudang.

**Perbaikan yang diminta.** Autentikasi harus berjalan sebelum lookup. Ikat kunci pada user ID stabil, entitas yang diizinkan, metode, path dan payload hash. Payload berbeda harus 409. Simpan hasil pemulihan operasi secara durable; jangan menggunakan potongan token sebagai identitas.

**Kriteria selesai.** Key sama pada dua user/entitas tidak berbagi respons; replay tanpa login ditolak; payload berbeda 409; retry sah tidak menggandakan efek walaupun proses sempat mati.

**Prompt:** gunakan tiket `GN-01` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="gn-02"></a>
## GN-02 · P1 — WebSocket GPS dapat dilanggan user biasa dan mengabaikan expiry/scope

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/server.py:294](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/server.py#L294)

```text
 293 |     is_manager = user.get("role") in ("admin", "manager")
 294 |     subscribe = (mode == "subscribe") or (mode != "publish" and is_manager)
 295 |
 296 |     if subscribe:
```

[backend/services/tracking_service.py:61](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/tracking_service.py#L61)

```text
  60 |
  61 | async def auth_ws_token(token: str) -> Optional[Dict[str, Any]]:
  62 |     """Validasi token sesi (query param) untuk WebSocket. Return user atau None."""
  63 |     if not token:
```

[backend/services/tracking_service.py:41](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/tracking_service.py#L41)

```text
  40 |     def snapshot(self) -> List[Dict[str, Any]]:
  41 |         return list(self.latest.values())
  42 |
  43 |     async def broadcast(self, msg: Dict[str, Any]) -> None:
```

**Akar masalah.** mode=subscribe mengalahkan pemeriksaan is_manager. auth_ws_token hanya mencari sesi dan user aktif tanpa expires_at, berbeda dari autentikasi HTTP. Snapshot dan broadcast TrackManager juga tidak menyaring entitas penerima.

**Skenario/reproduksi.** User biasa memilih mode subscribe dan menerima lokasi semua karyawan. Token kedaluwarsa yang belum dibersihkan TTL masih diterima. Manager yang hanya ditugaskan ke A menerima posisi B karena subscriber tidak mempunyai scope.

**Dampak.** Kebocoran lokasi pribadi lintas peran dan badan usaha. Koneksi lama juga perlu dihentikan ketika izin dicabut.

**Perbaikan yang diminta.** Pakai validasi sesi bersama untuk HTTP/WS, permission tracking khusus dan scope per subscriber. Saring snapshot/broadcast, periksa expiry/revocation dan tutup koneksi yang tidak lagi sah. Hindari token sesi panjang di URL/log.

**Kriteria selesai.** User sales tidak dapat subscribe; token expired ditolak meski record masih ada; manager A hanya menerima A; pencabutan akses menghentikan koneksi dan event baru.

**Prompt:** gunakan tiket `GN-02` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="gn-03"></a>
## GN-03 · P1 — Ledger rekening dan reconcile kas berdasarkan ID tidak memeriksa entitas dokumen

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/routers/bank.py:82](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank.py#L82)

```text
  81 |     await require_permission(request, "cash", "view")
  82 |     led = await bank_service.account_ledger(account_id)
  83 |     if led is None:
  84 |         raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
```

[backend/routers/bank.py:92](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank.py#L92)

```text
  91 |     actor = await require_permission(request, "cash", "create")
  92 |     txn = await bank_service.reconcile_txn(txn_id, payload.reconciled)
  93 |     if txn is None:
  94 |         raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan")
```

**Akar masalah.** List dan patch rekening mempunyai scope/guard_doc, tetapi ledger rekening serta reconcile kas hanya memeriksa permission lalu memuat arbitrary ID. current_user memvalidasi entitas pada header/body; ia tidak otomatis memvalidasi pemilik setiap dokumen yang dicari lewat ID.

**Skenario/reproduksi.** User yang boleh mengelola kas A mengetahui account_id/txn_id B lalu meminta ledger atau reconcile. Payload reconciled tidak menyebut entitas B, sehingga penjaga entity pada body tidak mencegah akses ini.

**Dampak.** Buku bank badan usaha lain dapat dibaca dan status rekonsiliasinya diubah.

**Perbaikan yang diminta.** Muat dokumen dan guard entitas sebelum service dipanggil. Ambil entity dari record, bukan dari input. Rekening legacy shared mengikuti kebijakan migrasi eksplisit.

**Kriteria selesai.** User A ditolak pada ledger/reconcile milik B; admin lintas entitas mengikuti izin eksplisit; ID yang ditebak tidak membocorkan nomor rekening atau saldo.

**Prompt:** gunakan tiket `GN-03` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="gn-04"></a>
## GN-04 · P1 — R&D dapat mengambil bahan dari roll badan usaha lain

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/routers/rnd.py:318](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L318)

```text
 317 |     ctx = await entity_ctx(request)
 318 |     doc = await _sample_guard(sample_id, ctx)
 319 |     if doc.get("spec_id"):
 320 |         raise HTTPException(status_code=400, detail=f"Sample ini sudah punya spesifikasi {doc.get('spec_number') or ''}.")
```

[backend/services/rnd_sample_service.py:1188](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rnd_sample_service.py#L1188)

```text
1187 |         raise RndError("Jumlah bahan yang diambil harus lebih dari 0.")
1188 |     roll = await db.inventory_rolls.find_one({"id": payload.get("roll_id") or ""}, {"_id": 0})
1189 |     if not roll:
1190 |         raise RndError("Roll tidak ditemukan.")
```

**Akar masalah.** Route R&D mengamankan sample, tetapi tidak mengamankan roll bahan. issue_material mencari roll dari payload.roll_id dan memeriksa status/panjang tanpa membandingkan owner roll dengan entitas sample atau scope pengguna. CAS roll menjaga konkurensi, bukan otorisasi.

**Skenario/reproduksi.** User R&D A pada sample A memasukkan roll available milik B. Stok B berkurang dan beban dapat diposting ke B, sementara material issue ditautkan ke sample A. Payload roll_id tidak memicu body entity guard.

**Dampak.** Pengeluaran barang dan biaya lintas badan usaha tanpa transaksi internal yang sah.

**Perbaikan yang diminta.** Validasi owner roll terhadap sample dan user context sebelum mutasi. Penggunaan material lintas entitas harus melalui intercompany yang disahkan. Validasi produk/gudang/unit sesuai kebutuhan sample.

**Kriteria selesai.** Sample A tidak dapat mengurangi roll B sebelum movement/JE apa pun; transfer ownership yang sah memungkinkan pemakaian; material A untuk sample A tetap berfungsi.

**Prompt:** gunakan tiket `GN-04` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="gn-05"></a>
## GN-05 · P1 — Rollback pengambilan bahan R&D dapat menimpa pemakaian roll lain

**Status bukti:** Risiko konkurensi statis.

**Letak kode dan bukti:**

[backend/services/rnd_sample_service.py:1246](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rnd_sample_service.py#L1246)

```text
1245 |             await db.inventory_rolls.update_one({"id": roll["id"]}, {"$set": {
1246 |                 "length_remaining": have, "status": roll.get("status"), "updated_at": at}})
1247 |             await roll_service.rebuild_balance(roll.get("product_id"),
1248 |                                                roll.get("warehouse_id"),
```

**Akar masalah.** Pengambilan awal memakai CAS yang baik. Tetapi bila GL gagal, rollback melakukan $set ke panjang/status awal tanpa version guard. Transaksi lain bisa sudah memakai sisa roll sebelum kompensasi tersebut dijalankan.

**Skenario/reproduksi.** Roll100: issue A10 membuat90; issue B20 sukses membuat70; posting GL A gagal, lalu rollback A mengembalikan panjang100. Pemakaian B hilang dari stok walaupun movement dan JE B masih ada.

**Dampak.** Kompensasi menciptakan stok dan membuat pesan “stok tidak diubah” tidak sesuai keadaan akhir.

**Perbaikan yang diminta.** Gunakan operation/version dan kompensasi yang hanya membalik kontribusi A. Klaim/fencing harus mencakup posting dan pemulihan; status serta balance dihitung dari hasil yang konsisten.

**Kriteria selesai.** GL A gagal bersamaan dengan B sukses menghasilkan panjang80, bukan100/90; rollback tidak menimpa status/ref operasi lain; pemulihan ulang tidak menambah stok lagi.

**Prompt:** gunakan tiket `GN-05` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="gn-06"></a>
## GN-06 · P1 — Produksi menyelesaikan WO tanpa claim dan memakai BOM terbaru

**Status bukti:** Terbukti statis; konkurensi belum DB test.

**Letak kode dan bukti:**

[backend/services/production_service.py:358](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/production_service.py#L358)

```text
 357 | # ═══ Selesaikan WO — konsumsi bahan → produksi barang jadi ═══════════════════
 358 | async def complete_work_order(wo_id: str, scope: Optional[Dict[str, Any]] = None,
 359 |                               actor_name: str = "") -> Dict[str, Any]:
 360 |     wo = await db.mfg_work_orders.find_one({"id": wo_id, **(scope or {})}, {"_id": 0})
```

[backend/services/production_service.py:278](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/production_service.py#L278)

```text
 277 |         raise ValueError(f"Work Order status '{wo['status']}' tidak bisa dirilis.")
 278 |     bom = await get_bom(wo["bom_id"], None)
 279 |     plan = await _material_plan(bom, wo["planned_qty"], wo["warehouse_id"], wo["entity_id"]) if bom else wo["material_plan"]
 280 |     await db.mfg_work_orders.update_one({"id": wo_id}, {"$set": {
```

[backend/services/production_service.py:339](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/production_service.py#L339)

```text
 338 |             await db.inventory_rolls.update_one(
 339 |                 {"id": r["id"]}, {"$set": {"length_remaining": new_len, "updated_at": now_iso()}})
 340 |         await db.inventory_movements.insert_one({
 341 |             "id": new_id("mov"), "product_id": product_id, "warehouse_id": warehouse_id,
```

**Akar masalah.** complete_work_order tidak mengklaim WO; konsumsi bahan melakukan read lalu set roll tanpa CAS. Pemeriksaan available sebelumnya tidak atomik. Draft juga bisa diselesaikan. Bahan diambil dari BOM terbaru, bukan revision/material plan yang dibekukan saat WO dibuat atau dirilis.

**Skenario/reproduksi.** Dua complete WO yang sama dapat membuat dua output. Dua WO berbeda bisa membaca dan mengonsumsi stok100 yang sama. Edit BOM setelah release mengubah bahan yang dipakai WO lama; kegagalan pada bahan kedua dapat meninggalkan konsumsi bahan pertama.

**Dampak.** Stok/output/nilai bisa ganda atau produksi memakai recipe yang tidak disetujui.

**Perbaikan yang diminta.** Bekukan BOM revision dan material plan pada WO. Klaim WO, reservasi/CAS bahan dan gunakan tahapan durable consume→output→JE. Validasi jumlah aktual yang diterapkan serta yield/waste; draft harus mengikuti release policy.

**Kriteria selesai.** Complete bersamaan hanya membuat satu output; dua WO tidak memakai qty yang sama; draft tidak langsung selesai; perubahan BOM tidak mengubah WO released; fault setiap tahap dapat dipulihkan.

**Prompt:** gunakan tiket `GN-06` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="gn-07"></a>
## GN-07 · P1 — Retur supplier mengurangi roll dengan read-set dan partial return kehilangan identitas fisik

**Status bukti:** Risiko konkurensi dan gap traceability statis.

**Letak kode dan bukti:**

[backend/services/purchase_return_service.py:621](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/purchase_return_service.py#L621)

```text
 620 |
 621 | async def _consume_available_rolls(product_id, warehouse_id, owner_entity_id, qty, ret) -> float:
 622 |     """Kurangi roll available (FIFO) sebesar qty → status returned_supplier / split.
 623 |     Catat movement return_out. Return total qty yang berhasil dikurangi."""
```

[backend/services/purchase_return_service.py:663](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/purchase_return_service.py#L663)

```text
 662 |
 663 | async def _consume_specific_rolls(roll_ids, owner_entity_id, qty, ret) -> float:
 664 |     """Retur PRESISI — kurangi roll/lot SPESIFIK yang dipilih user (bukan FIFO).
 665 |     Menelusuri roll asal supplier/invoice tertentu. Return total qty yang dikurangi."""
```

**Akar masalah.** Konsumsi roll untuk retur supplier memakai update berdasarkan ID setelah read, tanpa prasyarat status/panjang. Partial return hanya mengurangi parent tanpa membuat identitas fisik potongan retur. Helper specific juga tidak menyaring owner/status; validasi caller harus dibuktikan pada semua jalur.

**Skenario/reproduksi.** Reservation atau penjualan bersamaan dapat ditimpa retur. Retur30 dari roll100 mencatat keluar30 tetapi tag parent tetap pada sisa70; potongan30 yang dikirim tidak mempunyai roll retur baru. Ini bukan klaim bahwa seluruh caller sudah terbukti menembus owner.

**Dampak.** Konkurensi stok dan genealogy RFID retur tidak presisi; manifest supplier RMA kurang dapat ditelusuri.

**Perbaikan yang diminta.** Gunakan core consume/split dengan CAS, konversi unit, owner/status dan provenance supplier yang wajib. Buat identitas child fisik retur serta tag/barcode; pastikan actual_applied sama dengan requested.

**Kriteria selesai.** Retur bersamaan dengan sale tidak mengonsumsi dua kali; parent70 dan child retur30 terpisah; mixed UOM benar; roll wrong-owner ditolak di semua entrypoint.

**Prompt:** gunakan tiket `GN-07` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="gn-08"></a>
## GN-08 · P1 — Konversi permintaan internal dapat melahirkan transaksi antar-PT ganda

**Status bukti:** Risiko konkurensi statis.

**Letak kode dan bukti:**

[backend/services/internal_request_service.py:415](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/internal_request_service.py#L415)

```text
 414 |     try:
 415 |         pair = await ics.create(payload, actor.get("name", ""), actor_user=actor)
 416 |     except ics.IntercoError as exc:
 417 |         # Kalimat mesin G-6 sudah menuntun (mis. “buat kontrak internal dulu”),
```

[backend/services/internal_request_service.py:427](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/internal_request_service.py#L427)

```text
 426 |                  "source_entity_name": await _entity_name(seller),
 427 |                  "interco_pair_id": pair.get("pair_id", ""),
 428 |                  "interco_number_seller": seller_doc.get("number", ""),
 429 |                  "interco_number_buyer": buyer_doc.get("number", ""),
```

**Akar masalah.** convert membaca request open, membuat pair intercompany, kemudian menulis converted. Tidak ada claim pada request atau unique logical conversion key. source_request_id disimpan tetapi tidak digunakan untuk dedup creation pada flow yang diperiksa.

**Skenario/reproduksi.** Dua convert bersamaan dari request yang sama masing-masing membuat pair seller/buyer. Request hanya menyimpan pair yang terakhir ditulis.

**Dampak.** Demand/tagihan internal ganda dan dokumen orphan yang tidak tertaut dari request.

**Perbaikan yang diminta.** Klaim request sebelum create pair; gunakan key source request+revision untuk operasi conversion. Retry memuat pair existing. Partial pair creation harus dapat dilanjutkan atau dikompensasi dengan benar.

**Kriteria selesai.** Convert paralel menghasilkan satu pair; cancel vs convert tidak saling menimpa; fault setelah create sebelum update request melanjutkan pair yang sama.

**Prompt:** gunakan tiket `GN-08` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="gn-09"></a>
## GN-09 · P1 — CRM mengamankan owner sales tetapi tidak entitas pada operasi berdasarkan ID

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/routers/crm_omnichannel.py:126](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm_omnichannel.py#L126)

```text
 125 |
 126 | async def _guard_lead_owner(request: Request, lead_id: str, actor: Dict[str, Any]):
 127 |     lead = await oc.get_lead(lead_id)
 128 |     if not lead:
```

[backend/services/crm_omnichannel_service.py:148](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/crm_omnichannel_service.py#L148)

```text
 147 |     if existing_customer_id:
 148 |         cust = await db.customers.find_one({"id": existing_customer_id}, {"_id": 0})
 149 |         if not cust:
 150 |             return None, "Pelanggan tujuan tidak ditemukan."
```

**Akar masalah.** _guard_lead_owner memeriksa kepemilikan hanya untuk role sales, tanpa assert entity. Custom role dengan customer.create/update dapat memutasi lead entitas lain melalui ID. Convert ke existing_customer_id juga tidak memeriksa kesamaan entity customer dan lead; delete interaction mempunyai pola serupa.

**Skenario/reproduksi.** User A dengan custom permission mengirim patch/convert/delete lead B. Lead A dapat ditautkan ke customer B meski tidak ada kebijakan hubungan lintas entitas yang membenarkannya.

**Dampak.** Data pelanggan/CRM lintas badan usaha dapat bocor atau salah hubungan. Scope list tidak melindungi aksi berdasarkan ID.

**Perbaikan yang diminta.** Guard entity dan row ownership pada seluruh aksi ID; validasi referenced customer. Turunkan scope dari context server. Jangan menjadikan nama role sales satu-satunya aturan row access.

**Kriteria selesai.** A tidak memutasi B melalui ID; perpindahan entity/ownership mencabut akses lama; konversi customer beda entity ditolak; admin mengikuti policy eksplisit.

**Prompt:** gunakan tiket `GN-09` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="gn-10"></a>
## GN-10 · P2 — Rekomendasi POS memakai entity query tanpa resolusi izin dan stok global

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/routers/pos.py:20](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pos.py#L20)

```text
  19 |     await require_permission(request, "order", "view")
  20 |     return await pos_svc.best_sellers(entity_id=entity_id, limit=limit)
  21 |
  22 |
```

[backend/services/pos_recommendation_service.py:15](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/pos_recommendation_service.py#L15)

```text
  14 | async def _live_orders(entity_id: Optional[str]) -> List[Dict[str, Any]]:
  15 |     q: Dict[str, Any] = {}
  16 |     if entity_id and entity_id != "all":
  17 |         q["entity_id"] = entity_id
```

[backend/services/pos_recommendation_service.py:26](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/pos_recommendation_service.py#L26)

```text
  25 |         return None
  26 |     summ = await product_summary(pid)
  27 |     return {
  28 |         "product_id": pid,
```

**Akar masalah.** Route rekomendasi POS mempunyai permission order.view, tetapi entity_id query tidak diresolusikan melalui entity_ctx/resolve_scope_ids. Tanpa entity, service membaca semua order. Enrichment stok/substitute memakai product_summary global tanpa owner scope.

**Skenario/reproduksi.** User A meminta entity B, all atau kosong dan mendapat agregat revenue/qty di luar scope. Produk yang hanya tersedia di B juga dapat ditawarkan sebagai substitute tersedia untuk A.

**Dampak.** Kebocoran analitik dan rekomendasi stok yang tidak dapat dipenuhi langsung pada POS A.

**Perbaikan yang diminta.** Resolve entity scope authorized pada router dan teruskan ke analytics serta inventory enrichment. Pisahkan available langsung dari opsi yang memerlukan transfer/intercompany dan lead time.

**Kriteria selesai.** Query B tanpa izin ditolak; default memakai A; stok hanya B bukan available A; opsi intercompany ditampilkan dengan syarat approval/lead time.

**Prompt:** gunakan tiket `GN-10` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="gn-11"></a>
## GN-11 · P1 — Saga release menghapus lock tanpa mengecek efek yang sudah terposting

**Status bukti:** Risiko pemulihan statis.

**Letak kode dan bukti:**

[backend/routers/saga_locks.py:36](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/saga_locks.py#L36)

```text
  35 |         raise HTTPException(status_code=404, detail="Tidak ada kunci saga pada dokumen ini.")
  36 |     await release(collection, doc_id)
  37 |     await audit(actor["name"], "saga_lock_released", collection, doc_id, {"lock": doc[LOCK]})
  38 |     return {"released": True, "collection": collection, "id": doc_id, "lock": doc[LOCK]}
```

[backend/services/atomic_claim.py:53](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/atomic_claim.py#L53)

```text
  52 |
  53 | async def release(collection: str, doc_id: str) -> None:
  54 |     await db[collection].update_one({"id": doc_id}, {"$unset": {LOCK: ""}})
  55 |
```

**Akar masalah.** Claim mengunci dokumen induk, bukan seluruh transaksi lintas koleksi atau roll yang juga digunakan induk lain. Endpoint release admin langsung menghapus lock tanpa memeriksa tahap/efek yang telah diposting. Lock sendiri tidak membuktikan exactly-once recovery.

**Skenario/reproduksi.** Inbound/return/PA mati sesudah roll atau movement dibuat tetapi sebelum status akhir. Admin release lalu retry dapat mengulang efek yang sudah ada. Hasil persis bergantung guard masing-masing source; fault test wajib, bukan asumsi semua flow pasti duplicate.

**Dampak.** Pemulihan manual dapat menggandakan stok/jurnal atau meninggalkan partial state tanpa petunjuk yang cukup.

**Perbaikan yang diminta.** Simpan operation ledger dengan tahap, effect keys dan version/fencing. Release harus mengikuti pemeriksaan efek dan rencana resume/compensate, bukan unlock generik. UI recovery menunjukkan apa yang sudah terjadi.

**Kriteria selesai.** Fault pada setiap tahap pulih tepat sekali; lock operasi aktif tidak dilepas tanpa fencing; audit pemulihan mencatat efek, aktor dan hasil.

**Prompt:** gunakan tiket `GN-11` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="gn-12"></a>
## GN-12 · P2 — Agregasi kritis berhenti pada batas to_list tanpa penanda truncation

**Status bukti:** Terbukti statis; kasus skala belum DB test.

**Letak kode dan bukti:**

[backend/services/roll_service.py:184](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L184)

```text
 183 |
 184 | async def rebuild_balance(product_id: str, warehouse_id: str, owner_entity_id: str) -> Dict[str, Any]:
 185 |     """Hitung ulang satu segmen balance (product × warehouse × owner) dari rolls."""
 186 |     rolls = await db.inventory_rolls.find(
```

[backend/services/financial_statement_service.py:60](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/financial_statement_service.py#L60)

```text
  59 |         q["date"] = date_filter
  60 |     entries = await db.journal_entries.find(q, {"_id": 0, "lines": 1}).to_list(100000)
  61 |     agg: Dict[str, Dict[str, float]] = {}
  62 |     for je in entries:
```

[backend/services/costing_service.py:60](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/costing_service.py#L60)

```text
  59 |         query["owner_entity_id"] = entity_id
  60 |     rolls = await db.inventory_rolls.find(query, {"_id": 0}).to_list(5000)
  61 |
  62 |     total_len = 0.0
```

[backend/routers/cash.py:76](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash.py#L76)

```text
  75 |
  76 |     all_rows = await db.cash_transactions.find({"status": {"$ne": "void"}}, {"_id": 0}).to_list(2000)
  77 |     kecil_q = [r for r in all_rows if r.get("cash_type") == "kas_kecil"
  78 |                and r.get("entity_id") in entities]
```

**Akar masalah.** Rebuild balance menarik maksimum10.000 roll, WAC5.000, laporan keuangan100.000 jurnal dan cash summary2.000 transaksi. Banyak analitik mempunyai cap serupa. Batas daftar UI boleh, tetapi total/projection tidak boleh menganggap halaman tersebut sebagai seluruh data.

**Skenario/reproduksi.** Pada10.001 roll atau100.001 jurnal, record setelah cap tidak dihitung. Cash summary menyaring entity setelah pengambilan capped, sehingga data entitas lain dapat memenuhi batas dan menyembunyikan saldo entitas aktif.

**Dampak.** Kesalahan total baru muncul saat data membesar; demo kecil atau guard to_list bound tidak membuktikan angka enterprise benar.

**Perbaikan yang diminta.** Pakai aggregation/streaming untuk total dan nilai; scope sebelum query. Detail memakai pagination dengan total/has_more. Verifikasi index dan fixture tepat di sekitar setiap batas.

**Kriteria selesai.** Cap−1/cap/cap+1 menghasilkan total akurat; laporan100k+ jurnal reconcile; UI tidak menjadikan satu halaman sebagai total financial.

**Prompt:** gunakan tiket `GN-12` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="gn-13"></a>
## GN-13 · P2 — Rebuild projection dapat menulis snapshot lama dan fallback UOM mencampur unit

**Status bukti:** Risiko konkurensi dan logika statis.

**Letak kode dan bukti:**

[backend/services/roll_service.py:184](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L184)

```text
 183 |
 184 | async def rebuild_balance(product_id: str, warehouse_id: str, owner_entity_id: str) -> Dict[str, Any]:
 185 |     """Hitung ulang satu segmen balance (product × warehouse × owner) dari rolls."""
 186 |     rolls = await db.inventory_rolls.find(
```

**Akar masalah.** Rebuild membaca state roll lalu menulis projection tanpa revision barrier; dua rebuild dapat selesai di luar urutan pembacaan. Saat konversi unit gagal, error ditangkap dan panjang native tetap dapat ditambahkan ke bucket base unit.

**Skenario/reproduksi.** Rebuild A membaca stok lama; mutasi B dan rebuild B menulis saldo baru; A kemudian menimpa saldo baru dengan snapshot lama. Yard yang gagal dikonversi tetap ikut dijumlahkan seolah meter.

**Dampak.** ATP/projection tidak sesuai roll dan dapat bertahan sampai rebuild berikutnya; unit salah menghasilkan saldo yang tampak sah.

**Perbaikan yang diminta.** Gunakan revision/watermark atau pembacaan stabil dengan retry. Konversi unit wajib valid; projection gagal/invalid harus terlihat sebagai exception, bukan fallback1:1. Pantau lag dan drift.

**Kriteria selesai.** Rebuild out-of-order tidak menurunkan revision; conversion failure menandai saldo invalid; source dan projection reconcile setelah mutasi konkurensi.

**Prompt:** gunakan tiket `GN-13` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="gn-14"></a>
## GN-14 · P2 — Audit log selalu before=None dan source secrets tersimpan dalam repo publik

**Status bukti:** Kontrol statis; validitas secret belum diverifikasi.

**Letak kode dan bukti:**

[backend/dependencies.py:168](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/dependencies.py#L168)

```text
 167 |             "scope_entity_id": scope or None,
 168 |             "before": None,
 169 |             "after": clean_after,
 170 |             "reason": reason,
```

**Akar masalah.** Helper audit selalu menulis before=None; after bergantung caller dan sering hanya ringkasan. Ia adalah event log, belum cukup untuk merekonstruksi semua perubahan financial. Repo publik juga melacak .tok dan .tok_mgr, masing-masing45byte nonempty, serta artifact restore env. Nilai tidak dicetak, dipakai atau dikirim dalam audit; credential aktif belum dibuktikan.

**Skenario/reproduksi.** Perubahan saldo awal/field financial tidak mempunyai nilai sebelum perubahan dari helper. Bila file token berisi sesi yang masih berlaku, pembaca repo dapat mengambilnya. Domain histories lain perlu diperiksa sebagai sumber tambahan, bukan dianggap tidak ada.

**Dampak.** Auditability financial terbatas dan ada potensi credential exposure; kedua observasi perlu remediation yang berbeda.

**Perbaikan yang diminta.** Audit financial memuat actor ID, entity, operation/source, alasan serta before/after diff immutable dengan redaction. Inventaris/rotasi token berisiko, bersihkan history secara terkontrol dan pasang secret scanning; jangan sekadar menghapus file tree terbaru.

**Kriteria selesai.** Perubahan amount/status/account dapat direkonstruksi; audit tidak memuat secret; repo/history bebas secret nyata; validitas credential diperiksa pemilik tanpa menaruh nilainya di laporan.

**Prompt:** gunakan tiket `GN-14` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="gn-15"></a>
## GN-15 · P3 — Duplikasi helper dan definisi status menunjukkan SSOT belum konsisten

**Status bukti:** Terbukti static exact AST; sebagian risiko desain.

**Letak kode dan bukti:**

[backend/services/contract_service.py:62](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/contract_service.py#L62)

```text
  61 | # ═══════════════════════════════════════════════════════════════════════════
  62 | async def get_settings(entity_id: str = "") -> Dict[str, Any]:
  63 |     """Kebijakan efektif. FASE E-4 (E4.5): bila `entity_id` diisi, setelan khusus
  64 |     badan usaha itu MENIMPA nilai global — dulu satu nilai memaksa seluruh grup.
```

[backend/services/lot_service.py:59](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/lot_service.py#L59)

```text
  58 | # ═══════════════════════════════════════════════════════════════════════════
  59 | async def get_settings(entity_id: str = "") -> Dict[str, Any]:
  60 |     """Kebijakan efektif. FASE E-4 (E4.5): bila `entity_id` diisi, setelan khusus
  61 |     badan usaha itu MENIMPA nilai global — dulu satu nilai memaksa seluruh grup.
```

[backend/services/receiving_uom_service.py:63](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L63)

```text
  62 | # ═══════════════════════════════════════════════════════════════════════════
  63 | async def get_settings(entity_id: str = "") -> Dict[str, Any]:
  64 |     """Kebijakan efektif. FASE E-4 (E4.5): bila `entity_id` diisi, setelan khusus
  65 |     badan usaha itu MENIMPA nilai global — dulu satu nilai memaksa seluruh grup.
```

[backend/services/uom_rules_service.py:146](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/uom_rules_service.py#L146)

```text
 145 | # ═══ Pengaturan toleransi (configurable — keputusan pemilik) ═════════════════
 146 | async def get_settings(entity_id: str = "") -> Dict[str, Any]:
 147 |     """Kebijakan efektif. FASE E-4 (E4.5): bila `entity_id` diisi, setelan khusus
 148 |     badan usaha itu MENIMPA nilai global — dulu satu nilai memaksa seluruh grup.
```

**Akar masalah.** Scanner menemukan dua pasangan get_settings dengan AST identik. Duplikasi business policy lebih penting: physical status RFID berbeda dari roll, resolver COA berbeda antarposting/report, dan evaluator gate simulator berbeda dari hardware. Tidak semua duplikasi kode adalah bug.

**Skenario/reproduksi.** Menambah status atau mengubah fallback pada satu jalur dapat memberi hasil berbeda pada jalur lain. Pasangan helper get_settings sendiri belum terbukti menghasilkan data salah.

**Dampak.** Drift aturan dan biaya pemeliharaan. Perbaikan harus mengutamakan policy bisnis dibanding kosmetik pengurangan baris.

**Perbaikan yang diminta.** Satukan policy/resolver domain dan contract tests. Gabungkan helper config hanya bila semantiknya benar-benar sama. Snapshot dokumen tetap immutable dan jangan diganti konfigurasi live saat laporan historis.

**Kriteria selesai.** Entry point yang setara memberi keputusan yang sama; refactor helper mempertahankan entity fallback; semua status diuji terhadap policy yang terpusat.

**Prompt:** gunakan tiket `GN-15` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="hr-01"></a>
## HR-01 · P1 — PPh21 memakai TER bahkan pada masa pajak terakhir

**Status bukti:** Gap akurasi statis terhadap acuan resmi.

**Letak kode dan bukti:**

[backend/services/hr_payroll_service.py:191](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L191)

```text
 190 |     _pph21_on = bool((cfg.get("feature_toggles", {}) or {}).get("pph21", True))
 191 |     rate = ter_rate(category, gross) if (cfg.get("ter_enabled", True) and _pph21_on) else 0.0
 192 |     pph21 = round(gross * rate, 2)
 193 |     net = round(gross - emp_total - pph21, 2)
```

[backend/services/hr_payroll_service.py:192](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L192)

```text
 191 |     rate = ter_rate(category, gross) if (cfg.get("ter_enabled", True) and _pph21_on) else 0.0
 192 |     pph21 = round(gross * rate, 2)
 193 |     net = round(gross - emp_total - pph21, 2)
 194 |     return {
```

**Akar masalah.** compute_payslip tidak membedakan Desember atau bulan terakhir bekerja; setiap period menggunakan TER. Tidak ditemukan rekonsiliasi tahunan Pasal17 pada flow payroll yang ditelusuri. TER disabled menghasilkan0, bukan formula progresif alternatif.

**Skenario/reproduksi.** Pegawai tetap dengan penghasilan bervariasi atau berhenti sebelum Desember tetap mendapat pajak monthly TER pada masa terakhir, bukan pajak tahunan/bagian tahun dikurangi potongan sebelumnya.

**Dampak.** Net pay dan total pajak dapat lebih/kurang potong. Jenis pegawai dan fasilitas DTP memerlukan policy tersendiri; audit ini tidak menyatakan seluruh skenario perpajakan sudah tercakup.

**Perbaikan yang diminta.** Bangun policy pajak effective-dated dengan annual/part-year earnings, pengurang, PTKP/PKP, Pasal17, prior withholding/refund dan termination. Akuntan memvalidasi fixture independen sesuai aturan resmi yang berlaku.

**Kriteria selesai.** TER masa biasa dan rekonsiliasi masa terakhir, bonus, join/leave tengah tahun, refund serta basis BPJS/PTKP diuji terhadap perhitungan independen. Rujukan DJP pada dokumen fit-gap.

**Prompt:** gunakan tiket `HR-01` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="hr-02"></a>
## HR-02 · P1 — Lembur memakai multiplier flat dan dua sumber menit berpotensi tumpang tindih

**Status bukti:** Direproduksi formula; dedup risiko statis.

**Letak kode dan bukti:**

[backend/services/hr_payroll_service.py:180](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L180)

```text
 179 |     ot_filed = await _period_filed_overtime_min(emp["id"], period, entity_id)
 180 |     ot_min = ot_auto + ot_filed
 181 |     overtime = _overtime_amount(base, ot_min, cfg)
 182 |     commission = await _commission_for(emp, period, entity_id)
```

[backend/services/hr_payroll_service.py:156](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L156)

```text
 155 |     hourly = base / divisor
 156 |     return round((overtime_min / 60.0) * hourly * mult, 2)
 157 |
 158 |
```

**Akar masalah.** Total menit lembur dikalikan satu multiplier default1.5, tanpa pembagian jam pertama/berikutnya dan jenis hari. Menit attendance otomatis dan approved filed dijumlah tanpa pairing shift/date; overlap aktual harus diperiksa dari data.

**Skenario/reproduksi.** HR-02: upah sejam1000, lembur2jam hari kerja menghasilkan3000; acuan1.5jam pertama+2jam berikutnya menghasilkan3500. Bila attendance120menit dan pengajuan120menit menggambarkan kejadian sama, jumlah240 akan menggandakan waktu.

**Dampak.** Payroll bisa kurang/lebih bayar; pajak dan biaya turunannya ikut salah.

**Perbaikan yang diminta.** Satu overtime event per hari/shift yang di-approve. Attendance mengusulkan actual time dan filed approval mengesahkan event yang sama. Hitung tier hari kerja/istirahat/libur, wage base serta batas sesuai kebijakan/regulasi.

**Kriteria selesai.** Dua jam normal=3.5×upah sejam; hari libur dan jadwal5/6hari mengikuti fixture resmi; overlap sumber dihitung sekali; kejadian unapproved/duplicate tidak dibayar.

**Prompt:** gunakan tiket `HR-02` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="hr-03"></a>
## HR-03 · P2 — Persetujuan cuti tidak mengecek ulang saldo dan cuti lintas tahun salah pembebanan

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/services/hr_leave_service.py:87](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L87)

```text
  86 | async def recompute_balance(employee_id: str, entity_id: str, year: int) -> Dict[str, Any]:
  87 |     """Hitung ulang & simpan saldo cuti tahunan: remaining = entitlement - used(approved)."""
  88 |     entitlement = await _annual_entitlement(entity_id)
  89 |     existing = await db.hr_leave_balances.find_one(
```

[backend/services/hr_leave_service.py:202](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L202)

```text
 201 |
 202 | async def approve_leave(leave_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
 203 |     lv = await db.hr_leave_requests.find_one({"id": leave_id}, {"_id": 0})
 204 |     if not lv:
```

[backend/services/hr_leave_service.py:96](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L96)

```text
  95 |     q = {"employee_id": employee_id, "leave_type": {"$in": DEDUCT_TYPES},
  96 |          "date_from": {"$regex": f"^{year:04d}"}}
  97 |     async for r in db.hr_leave_requests.find(q, {"_id": 0, "status": 1, "days": 1}):
  98 |         if r.get("status") == "approved":
```

**Akar masalah.** Submit membandingkan days dengan remaining tanpa mengurangi pending reservation; approve tidak memeriksa ulang saldo. Recompute membebankan seluruh days menurut tahun date_from, bukan tahun setiap work_date. Kehadiran cuti juga tidak ditautkan ke request ID pada clear.

**Skenario/reproduksi.** Entitlement12: dua pengajuan10hari dapat diterima dan keduanya disetujui sehingga used20/remaining−8. Cuti yang melintasi Desember–Januari dibebankan seluruhnya ke tahun awal. Membatalkan satu cuti dapat menghapus attendance leave yang dibuat request lain pada tanggal sama.

**Dampak.** Saldo cuti dan attendance salah; tidak selalu langsung mengubah GL tetapi dapat memengaruhi payroll/KPI.

**Perbaikan yang diminta.** Reservasi/revalidasi saldo secara atomik per employee/year; bagi days ke tahun masing-masing dengan kalender kerja/libur; guard overlap. Simpan leave_request_id pada attendance dan hapus hanya record sumber yang benar.

**Kriteria selesai.** Approved days tidak melebihi entitlement tanpa override; lintas tahun dibebankan benar; overlap ditolak; cancel satu request tidak menghapus attendance request lain.

**Prompt:** gunakan tiket `HR-03` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="mk-01"></a>
## MK-01 · P2 — Input metrik marketing parsial mengganti seluruh metrik sebelumnya

**Status bukti:** Terbukti statis.

**Letak kode dan bukti:**

[backend/services/marketing_service.py:259](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/marketing_service.py#L259)

```text
 258 |     snap = {**clean, "recorded_at": now_iso(), "by": actor.get("name", ""), "note": note.strip()}
 259 |     await db.mkt_posts.update_one({"id": pid}, {"$set": {"metrics": {**clean, "recorded_at": snap["recorded_at"]}, "updated_at": now_iso()},
 260 |                                                 "$push": {"metrics_history": snap}})
 261 |     return await db.mkt_posts.find_one({"id": pid}, {"_id": 0})
```

**Akar masalah.** record_metrics memilih hanya field yang dikirim lalu mengganti seluruh metrics. Request parsial dapat menghapus nilai sebelumnya; history menyimpan patch tetapi dashboard membaca snapshot baru yang tidak lengkap.

**Skenario/reproduksi.** Catat likes10, lalu kirim hanya reach100. Current metrics kehilangan likes sehingga engagement campaign turun. Bila kontrak sengaja full replacement, schema/UI harus mewajibkan snapshot lengkap; saat ini tidak.

**Dampak.** KPI dan analitik marketing salah walaupun patch historis masih tersimpan.

**Perbaikan yang diminta.** PATCH per field metrics.<name> atau merge snapshot dengan version. Bedakan nilai0 eksplisit dari field tidak dikirim; simpan metadata/full snapshot history yang konsisten.

**Kriteria selesai.** Update reach tidak menghapus likes; likes0 mengganti nilainya; dua update field berbeda bersamaan tidak saling menimpa; total campaign reconcile.

**Prompt:** gunakan tiket `MK-01` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="ux-01"></a>
## UX-01 · P1 — Gate kiosk menampilkan hasil lama sebagai LIVE dan tidak mengagregasi satu passage

**Status bukti:** Terbukti dari source UI; belum uji visual hardware.

**Letak kode dan bukti:**

[frontend/src/features/rfid/RfidGateMonitorView.jsx:71](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/rfid/RfidGateMonitorView.jsx#L71)

```text
  70 |       const [r, s] = await Promise.all([
  71 |         axios.get(`${API}/rfid/reads`, { params: { ...params, limit: 25 } }),
  72 |         axios.get(`${API}/rfid/summary`, { params }),
  73 |       ]);
```

[frontend/src/features/rfid/RfidGateMonitorView.jsx:76](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/rfid/RfidGateMonitorView.jsx#L76)

```text
  75 |       setSummary(s.data);
  76 |     } catch { /* polling senyap */ }
  77 |   };
  78 |
```

[frontend/src/features/rfid/RfidGateMonitorView.jsx:121](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/rfid/RfidGateMonitorView.jsx#L121)

```text
 120 |         const gateReads = gateId ? reads.filter((r) => r.device_id === gateId) : reads;
 121 |         const last = gateReads[0];
 122 |         const red = last?.result === "red";
 123 |         const bg = !last ? "#101418" : red ? "#C0341D" : last.result === "green" ? "#1B7F4B" : "#0058CC";
```

**Akar masalah.** Read limit25 diambil sebelum filter inventory/gate pada frontend; traffic lain dapat menutupi gate pilihan. Kegagalan polling disenyapkan tanpa expiry hasil; label LIVE dan green lama tetap terlihat. Verdict kiosk memakai satu EPC, bukan seluruh passage.

**Skenario/reproduksi.** Sesudah green, reader/network mati dan layar tetap green/LIVE. Passage mempunyai satu roll unauthorized dan roll lain green; hasil teratas dapat menampilkan green. Lebih25 inventory reads menenggelamkan event gate.

**Dampak.** Isyarat “lolos” tidak selalu berdasarkan kejadian terkini. Siren browser untuk fresh red sudah ada, tetapi tidak menggantikan verdict/alarm per passage dan status kesehatan.

**Perbaikan yang diminta.** Filter gate/device di server dengan cursor. Agregasi passage harus red-dominant, alarm latched dan acknowledge terpisah. Tampilkan heartbeat age, network status, waktu fetch terakhir dan verdict TTL; offline menjadi UNKNOWN/TAHAN sesuai policy.

**Kriteria selesai.** Disconnect mengubah status sesuai TTL; passage campuran selalu TAHAN; traffic lain tidak menutupi gate; acknowledge tidak menghapus pelanggaran sumber.

**Prompt:** gunakan tiket `UX-01` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="ux-02"></a>
## UX-02 · P2 — Unduhan ZPL lewat tautan tidak membawa konteks entitas yang dipilih

**Status bukti:** Risiko UI statis.

**Letak kode dan bukti:**

[frontend/src/features/rfid/RfidPrintVerifyPanel.jsx:180](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/rfid/RfidPrintVerifyPanel.jsx#L180)

```text
 179 |               className="secondary-button text-[11px]"><X size={12} /> Tutup</button>
 180 |             <a data-testid="rfid-job-zpl" href={`${API}/rfid/print-jobs/${activeJob.id}/zpl`} target="_blank" rel="noreferrer"
 181 |               className="secondary-button text-[11px]"><Download size={12} /> Unduh ZPL</a>
 182 |             {activeJob.status === "queued" && (
```

**Akar masalah.** Unduh lewat href browser membawa cookie tetapi tidak membawa X-Entity-Id dari apiClient. User multi-entitas yang memilih entity berbeda dari home dapat ditolak pada job valid karena konteks download kembali ke home. Jangan memperbaikinya dengan melonggarkan guard server.

**Skenario/reproduksi.** Login homeA, pilihB, buka jobB lalu klik direct download ZPL. Request tidak membawa header entitas pilihan. Browser integration test diperlukan untuk memastikan respons pada deployment aktual.

**Dampak.** Operator sulit mencetak untuk badan usaha yang dipilih dan mendapat pesan scope yang membingungkan.

**Perbaikan yang diminta.** Fetch blob melalui apiClient dengan entity header lalu download object URL; atau ticket singkat yang terikat job/entity/user. Jangan memakai token sesi permanen di URL.

**Kriteria selesai.** Job B dapat diunduh dari selected B dengan scope benar; job tanpa izin ditolak; ticket expired tidak berlaku dan object URL dibersihkan.

**Prompt:** gunakan tiket `UX-02` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="gn-16"></a>
## GN-16 · P1 — Laporan AI pribadi disiarkan melalui notifikasi dan digest tidak membatasi entitas

**Status bukti:** Terbukti dari kontrak audience dan query.

**Letak kode dan bukti:**

[backend/services/ai_schedules.py:92](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ai_schedules.py#L92)

```text
  91 |         await create_notification(notif_type="ai_report", title=f"Laporan terjadwal: {sched['title']}", body=body[:1200],
  92 |                                   link="tanya-kn", entity_id=sched["entity_id"], recipient_user=sched["user_id"],
  93 |                                   ref=run["id"], dedupe=False)
  94 |     except ScheduleError as exc:
```

[backend/services/notification_service.py:67](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/notification_service.py#L67)

```text
  66 |     *, notif_type: str, title: str, body: str, severity: str = "info",
  67 |     link: str = "", entity_id: Optional[str] = None, recipient_role: str = "all",
  68 |     recipient_user: Optional[str] = None, ref: str = "", dedupe: bool = True,
  69 |     dedupe_scope: str = "unread",
```

[backend/services/notification_scope.py:47](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/notification_scope.py#L47)

```text
  46 |         ]}
  47 |     audience = {"$or": [
  48 |         {"recipient_role": {"$in": await audience_roles(user)}},
  49 |         {"recipient_user": uid},
```

[backend/services/digest_service.py:119](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/digest_service.py#L119)

```text
 118 |         q = {"$and": [q, await relevance_filter(user_doc)]}
 119 |     rows = await db.notifications.find(
 120 |         q, {"_id": 0, "type": 1, "title": 1, "severity": 1, "read": 1}).to_list(MAX_SCAN)
 121 |
```

**Akar masalah.** run_schedule mengirim recipient_user tanpa mengosongkan recipient_role yang default all. Filter pembaca menggunakan OR role/user; pengguna lain pada entitas sama yang boleh membuka Tanya KN dapat menerima body narasi laporan pribadi. Admin mempunyai pengecualian filter pribadi sendiri, jadi bukan seluruh pengguna otomatis menerima. Selain itu summarize_for pada digest menerapkan relevance_filter tetapi tidak filter entity/allowed_entity_ids; projection judul dapat memasukkan notifikasi entitas lain.

**Skenario/reproduksi.** Buat laporan terjadwal privat untuk user U1, lalu buka notifikasi sebagai U2 pada entitas sama dengan izin Tanya KN. Untuk digest, buat dua notifikasi role-compatible milik A/B dan jalankan ringkasan untuk user hanya A: query tidak membatasi B. Ini skenario source-based, belum pengiriman WhatsApp nyata.

**Dampak.** Narasi laporan pribadi dan judul transaksi dapat tersebar di luar penerima atau entitas yang semestinya. Body sensitif dapat terlihat meski detail laporan mempunyai guard yang benar.

**Perbaikan yang diminta.** Untuk notifikasi individual set recipient_role kosong atau pakai helper audience khusus. Satukan audience/relevance/entity policy antara inbox, digest, WA dan web push. Periksa notifikasi historis yang sudah salah audience dengan dry-run tanpa menyebarkan kembali isinya.

**Kriteria selesai.** U2 tidak menerima laporan U1; user A tidak menerima judul/notifikasi B di inbox, digest, push atau WA. Penerima U1 tetap menerima sekali. Notifikasi sistem/shared hanya mengikuti policy eksplisit.

**Prompt:** gunakan tiket `GN-16` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).

<a id="ux-03"></a>
## UX-03 · P3 — Panel biaya OCR menampilkan ID entitas mentah

**Status bukti:** Terbukti dari render source.

**Letak kode dan bukti:**

[frontend/src/features/wms/grn/GrnOcrUsagePanel.jsx:53](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/wms/grn/GrnOcrUsagePanel.jsx#L53)

```text
  52 |                   <td className="px-2 py-1.5 font-mono">{r.model}</td>
  53 |                   <td className="px-2">{r.entity_id}</td>
  54 |                   <td className="px-2 tabular-nums">{n(r.calls)}</td>
  55 |                   <td className="px-2 tabular-nums">{n(r.ok)}</td>
```

**Akar masalah.** Kolom Badan usaha menampilkan entity_id teknis meskipun helper label bersama tersedia pada frontend. Ini mengurangi kejelasan bagi operator dan finance saat meninjau biaya OCR.

**Skenario/reproduksi.** Rows usage berisi entity_id internal: tabel menampilkan ID alih-alih nama badan usaha. Guardrail juga menandai MobileMdApp, tetapi itu false positive karena user.name berbagi baris dengan entityShortById; temuan ini hanya panel OCR yang benar-benar memakai raw ID.

**Dampak.** Operator harus menghafal ID; biaya per badan usaha lebih sulit diverifikasi.

**Perbaikan yang diminta.** Gunakan resolver label entitas atau EntityBadge yang sesuai context, dengan fallback manusiawi untuk legacy entity tidak ditemukan. Pertahankan ID sebagai metadata teknis bila diperlukan.

**Kriteria selesai.** Tabel menampilkan nama entitas yang benar, fallback jelas untuk record legacy, dan tidak memunculkan ID mentah sebagai label utama.

**Prompt:** gunakan tiket `UX-03` di [03_PROMPT_PERBAIKAN_AGENT.md](03_PROMPT_PERBAIKAN_AGENT.md).
