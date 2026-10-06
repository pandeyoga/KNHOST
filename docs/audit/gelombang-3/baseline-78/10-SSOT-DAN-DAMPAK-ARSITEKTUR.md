# SSOT dan dampak lintas modul

## Kontrak metrik harus mencakup sumber dan grain

Nama dan rumus saja belum cukup. Setiap angka perlu mendefinisikan source document/field, grain, eligible status, entity/owner, sales ownership, line, tanggal bisnis, unit dasar, price/tax/cost basis, denominator, rounding, freshness dan perlakuan null/error. Contohnya revenue 3000 dibagi count 20 secara aritmetika benar tetapi salah populasi. Nilai dan velocity stok dapat terduplikasi jika join owner dihilangkan terlalu awal. Nama performer bukan identity user.

Catatan: D4-ORDER-01, D4-STOCK-01, D4-RND-01, D4-HR-01, D4-SALES-01. UI sales boleh melihat stok gabungan sesuai kebutuhan pengguna; ledger dan kepemilikan tetap per badan usaha.

## Lifecycle PO harus satu sumber kebenaran

PO producer sudah menyimpan unit dokumen dan quantity_base. Consumer incoming harus memakai outstanding base quantity, bukan quantity mentah berlabel base_unit. Producer receipt menetapkan status partial, sementara shared OPEN_PO_STATUSES tidak memasukkan partial. Memperbaiki daftar status saja belum cukup jika consumer kemudian menjumlah seluruh ordered quantity dan mengabaikan received_qty.

Catatan: D4-GLOBAL-01, D4-SUPPLY-01, V3-PO-01/02/03, D4-AI-06. Review ATP, POS desktop/mobile, pending SO, forecast, reorder, GRN variance, return dan amendment pada fixture sama.

## Rencana supply berbeda dari supply yang dieksekusi

Rencana 20+80 bukan supply 100 jika satu PR20 dipakai ulang. Scope full berdasarkan request tidak benar jika interco 70 gagal sesudah stock 30 berhasil. Supply PO100 yang ditawarkan ke dua SO100 membutuhkan pegging eksklusif untuk janji pasti, atau label forecast nonexclusive yang jelas. Riwayat naratif tidak menggantikan reference aktif dan remaining quantity.

Catatan: D4-PLAN-01/02/03/04/05. Bagian sukses perlu operation identity, qty efektif dan reference; bagian gagal harus dapat dilanjutkan tanpa mengulang efek sukses. UI error proses tidak boleh terhapus hanya karena refresh GET berhasil.

## Demand dan stock harus diklaim secara atomik

Allocator dapat menjaga roll dengan CAS tetapi tetap overfulfill satu SO jika dua proses membaca shortage 100 dan masing-masing reserve 80. Demand claim SO/version harus dikoordinasikan dengan supply reservation, persist allocations, cancellation dan compensation. Mengganti satu $set menjadi $inc saja tidak menyelesaikan bound demand atau recovery.

Catatan: D4-BACKORDER-01, V3-MRES-01/02. Uji manual fulfillment versus automatic GR fulfillment dan cancel/retry pada line yang sama.

## Keandalan write memengaruhi seluruh read model

Stock consume, insert movement, child roll, posting GL, deposit/receipt dan publish fact adalah efek terpisah. Marker done/reversed yang mendahului physical restore dapat menutup recovery. Read model ETL delete-before-insert dapat kosong saat insert gagal. Revenue report yang salah source tidak otomatis berarti ledger posting salah; keduanya harus diuji dengan expected yang sesuai.

Catatan: V3-PROD-01/02, V3-MKO-01, V3-AR-01, V3-BANK-01, V3-MASTER-01, V3-CUT-01, D4-AI-03/04. Severity ledger berbeda dari label dashboard, tetapi keduanya perlu sumber dan bukti yang tepat.

## Helper kanonis harus dipakai seluruh consumer

Scope kredit benar pada satu sales KPI belum cukup bila home consumer memanggil tanpa entitas. Canonical bill fallback tidak membenarkan formula AP analytics yang berbeda. Snapshot term SO harus dipakai forecast agar tidak mengikuti term customer yang berubah. Rack→Level→Bin harus dipakai reporting capacity. Lookup master harus berdasarkan requested IDs; menaikkan cap hanya menggeser kegagalan.

Catatan: D4-SALES-02/03, D4-AI-01, D4-FIN-01/02, D4-WMS-03, D4-DASH-01, D4-CAP-01. Duplikasi fungsi _clean_perms tetap dicatat sebagai V3-DUP-01. Finite query cap hanya menjadi bug bila ada bukti kehilangan atau salah angka.

## Waktu dan frontend request generation

UTC adalah format penyimpanan; hari bisnis WIB, separation employee dan last measured accuracy membutuhkan source yang sesuai. App sudah meremount layar saat entity berubah. Race yang terbukti adalah periode berubah dalam komponen yang sama, tanpa guard request generation. Chart 14 hari harus diberi label atau mengikuti pilihan periode; perbaikan angka API tidak menjamin chart benar.

Catatan: D4-DATE-01, V3-DATE-01, D4-WMS-01/02, D4-HR-02, D4-FE-01/02.

## Dampak positif patch dan batas penutupannya

Agregat revenue server sudah benar pada counterexample 30 order; cap katalog 103 berhasil; full core 309/310 dan W2 82/82 lulus. Planner baru menyediakan split pemenuhan dan riwayat keputusan, serta global stock memperbaiki POV lintas entitas. Akan tetapi producer-consumer dan partial execution masih memiliki counterexample khusus. Penutupan perlu before/after pada failure window, scope, UOM dan consumer lain; hasil hijau yang lebih sempit tidak boleh menutup temuan yang lebih luas.
