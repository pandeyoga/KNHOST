| Baris | Kasus | Kode lama | Dokumen berubah | Tambahan baris (mutasi/kas/jurnal) | Status lama → sesudah | Pesan lama (dipotong) |
|---|---|---|---|---|---|---|
| 1 | setujui | 200 | ya | — | pending_approval → posted | None |
| 2 | batal | 200 | ya | — | posted → cancelled | None |
| 3 | setujui | 400 | tidak | — | pending_approval → pending_approval | Tidak ada roll target untuk dialokasi (mungkin sudah dihapus). |
| 4 | bayar | 200 | ya | cash_transactions +1, journal_entries +1 | applied → applied | None |
| 5 | kirim | 409 | tidak | — | picked → picked | Roll commit untuk order tak cukup dikirim (tersedia 0 dari 10.0). |
| 6 | selesai | 500 | ya | — | qc_check → qc_check | Internal Server Error |
| 7 | setujui opname | 500 | ya | inventory_movements +1 | submitted → submitted | Internal Server Error |
| 7 | finalisasi opname per roll | 500 | ya | inventory_movements +1 | open → open | Internal Server Error |
| 8 | susut potong | 200 | ya | inventory_movements +2 | available → available | None |
| 8 | buang BS retur | 400 | tidak | — | available → available | Roll R-BS tidak sedang menunggu keputusan tahap ini. |
| 8 | potong uji MDQ | 500 | ya | inventory_movements +1 | available → available | Internal Server Error |
| 9 | selesaikan retur | 200 | ya | — | inspected → refund_settled | None |
| 9 | selesaikan per roll | 400 | tidak | — | refund_settled → refund_settled | Retur berstatus 'refund_settled' — penyelesaian hanya sesudah disetujui/QC. |
| 9 | lengkapi per roll | 500 | ya | — | inspected → inspected | Internal Server Error |
| 10 | setujui amandemen nota kredit | 500 | ya | — | pending_approval → approved | Internal Server Error |
| 10 | terbitkan nota batal item | 500 | ya | — | pending_finance → issued | Internal Server Error |
| 11 | kirim bahan | 409 | tidak | — | in_progress → in_progress | Bahan prd_pk37_8b5a5325 di Gudang Uji PK-37 milik Sukacita hanya tersedia 0 , bu |
| 11 | catat jasa | 500 | ya | — | in_progress → in_progress | Internal Server Error |
| 11 | terima hasil | 400 | tidak | — | in_progress → in_progress | Minimal 1 roll output dengan LOT manual wajib diisi |
| 12 | terbitkan | 409 | tidak | — | draft → draft | Periode 2026-11 sudah DITUTUP (terkunci). Jurnal mundur ke tanggal 2026-11-14 me |
| 12 | bebaskan | 400 | tidak | — | issued → issued | Label alasan 'nego' tidak terdaftar / sudah tidak aktif. |
| 12 | ubah nominal | 400 | tidak | — | issued → issued | Label alasan 'nego' tidak terdaftar / sudah tidak aktif. |
| 12 | bayar | 400 | tidak | — | issued → issued | Rekening tidak ditemukan atau bukan milik PT nota denda ini. |
| 13 | putuskan selisih kwitansi | 400 | tidak | — | posted → posted | Label alasan 'x' tidak terdaftar / sudah tidak aktif. |
| 14 | selesaikan WO | 400 | tidak | — | released → released | Stok bahan Bahan tidak cukup: butuh 10 meter, tersedia 0 (roll ditahan QC/dipesa |
| 15 | biaya bank | 409 | tidak | — | unmatched → unmatched | Periode 2026-11 sudah DITUTUP (terkunci). Jurnal mundur ke tanggal 2026-11-14 me |
| 15 | titipan | 200 | ya | cash_transactions +1 | unmatched → holding | None |
| 15 | alokasi titipan | 409 | tidak | — | holding → holding | Periode 2026-11 sudah DITUTUP (terkunci). Jurnal mundur ke tanggal 2026-11-14 me |
| 16 | setujui transfer | 200 | ya | — | waiting_approval → completed | None |
| 17 | ambil bahan | 400 | ya | — | available → available | Pengambilan bahan dibatalkan: jurnal beban sample gagal dibuat (Periode 2026-11  |
| 18 | setujui klaim | 500 | tidak | — | in_progress → in_progress | Internal Server Error |
| 18 | setujui susut | 409 | tidak | — | in_progress → in_progress | {'code': 'STATE_CHANGED', 'message': "Dokumen sudah berubah (status 'in_progress |
| 19 | tambah saldo | 500 | tidak | — | active → active | Internal Server Error |
| 20 | selesaikan kasus | 400 | tidak | — | in_progress → in_progress | Periode 2026-11 sudah DITUTUP (terkunci). Jurnal mundur ke tanggal 2026-11-14 me |
