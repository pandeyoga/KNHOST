# Indeks temuan dan fase

Status terkini ada pada tracker aktif, bukan tabel ini.

|ID|Prioritas audit|Fase|Temuan|
|---|---|---|---|
|[W2-001](findings/W2-001.md)|P1|[P03](phases/P03.md)|Toleransi jumlah receipt menyebabkan drift nilai roll terhadap GL|
|[W2-002](findings/W2-002.md)|P1|[P03](phases/P03.md)|Receipt menerima output warehouse tidak terdaftar|
|[W2-003](findings/W2-003.md)|P1|[P03](phases/P03.md)|Partial receipt kehilangan lokasi asal saat finalisasi|
|[W2-004](findings/W2-004.md)|P1|[P03](phases/P03.md)|Cancel bill jasa makloon tidak membalik utang GL|
|[W2-005](findings/W2-005.md)|P1|[P03](phases/P03.md)|Race potong bon dan pembayaran meloloskan paid melebihi grand|
|[W2-006](findings/W2-006.md)|P1|[P01](phases/P01.md)|Owner otomatis opname dapat memilih stok entitas di luar scope|
|[W2-007](findings/W2-007.md)|P1|[P02](phases/P02.md)|Reject stale menimpa approved setelah adjustment stok|
|[W2-008](findings/W2-008.md)|P1|[P01](phases/P01.md)|Transfer manual A dapat mereservasi roll milik B|
|[W2-009](findings/W2-009.md)|P1|[P02](phases/P02.md)|Reservasi transfer pilihan roll tidak rebuild balance|
|[W2-010](findings/W2-010.md)|P1|[P01](phases/P01.md)|Histori pembacaan RFID tidak menerapkan scope owner roll|
|[W2-011](findings/W2-011.md)|P2|[P07](phases/P07.md)|Race acknowledge versus resolve dapat memundurkan status insiden|
|[W2-012](findings/W2-012.md)|P2|[P07](phases/P07.md)|Concurrent red reads membuat dua insiden open untuk EPC dan device sama|
|[W2-013](findings/W2-013.md)|P1|[P02](phases/P02.md)|GRN closed meskipun finalisasi hanya memproses500 dari501 roll|
|[W2-014](findings/W2-014.md)|P1|[P02](phases/P02.md)|Qty dasar QC dipakai sebagai unit harga PO pada retur supplier|
|[W2-015](findings/W2-015.md)|P1|[P05](phases/P05.md)|Pelunasan murni deposit melewati posting reklasifikasi GL|
|[W2-016](findings/W2-016.md)|P1|[P05](phases/P05.md)|Void sumber deposit gagal setelah payment dan kas dibalik|
|[W2-017](findings/W2-017.md)|P1|[P05](phases/P05.md)|CAS deposit terlambat meninggalkan pembayaran tanpa dana|
|[W2-018](findings/W2-018.md)|P1|[P05](phases/P05.md)|Void menimpa pembayaran baru dengan snapshot array lama|
|[W2-019](findings/W2-019.md)|P2|[P02](phases/P02.md)|Split QC menggandakan berat aktual tersimpan|
|[W2-020](findings/W2-020.md)|P1|[P05](phases/P05.md)|Refund jual final meskipun buku kas gagal dan retry tidak melengkapi efek|
|[W2-021](findings/W2-021.md)|P1|[P06](phases/P06.md)|Batas query5000/50000/100000 memotong saldo rekening dan laporan keuangan|
|[W2-022](findings/W2-022.md)|P1|[P06](phases/P06.md)|Payroll paid mengkredit kas GL tanpa transaksi buku kas|
|[W2-023](findings/W2-023.md)|P1|[P06](phases/P06.md)|Payroll menerima akun beban sebagai sumber pembayaran|
|[W2-024](findings/W2-024.md)|P1|[P04](phases/P04.md)|WO completed dengan konsumsi bahan terpotong pada5000 roll|
|[W2-025](findings/W2-025.md)|P1|[P01](phases/P01.md)|Scope lini R&D hanya membatasi daftar; detail dan patch sample lintas lini tetap diterima|
