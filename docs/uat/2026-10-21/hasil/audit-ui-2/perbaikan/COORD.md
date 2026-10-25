# Perbaikan koordinator (permintaan lintas grup untuk berkas G0 & backend tanpa pemilik)

| Asal | Butir | Perubahan | Berkas |
|---|---|---|---|
| G2 | G2-26/G5 | "Rate Insentif Sales" → "Tarif Insentif Sales" (judul & tab) | `frontend/src/config/hubTabs.js`, `config/navMeta.js` |
| G3 | G3-13 | Judul RFID Indonesia: "Tag RFID", "Monitor Gerbang", "Perangkat RFID (Pembaca / Gerbang)" | `config/navMeta.js` |
| G2 | G2-33 | Sub-status SO: "Stok siap — bisa dikonfirmasi", "Siap diambil (gudang)" | `utils/soStatus.js` |
| G3 | G3-31 | Papan antrean: judul kosong/"—" tidak lagi dirakit "· —" | `components/WaitingQueueBoard.jsx` |
| G2 | "Pengaju: —" | Pengajuan harga khusus dari SO & checkout ikut mengisi `requested_by_name` | `backend/routers/so_approvals.py`, `backend/services/so_special_price_service.py` |
| G2 | P-02 | Pengganti retur: penyetuju "sistem (KLR-05)" → "Sistem (harga transaksi asal)", alasan tanpa kode keputusan | `backend/services/return_replacement_service.py` |
| G3 | G3-33 | Statistik lot mengirim `qty_remaining_by_unit` (layar sudah siap) | `backend/services/lot_service.py` |
| G3 | G3-18 | Meta inspeksi: petugas membawa `dedicated` & `group` ("Petugas QC" / "Peran lain") | `backend/routers/inspections.py` |

| G4 | G4-12 | PO batal (`/purchase-orders/{id}/cancel`) & PO ditolak memanggil `release_po_realizations` → PR kembali bisa direalisasi | `backend/routers/purchase_orders_extra.py`, `backend/routers/purchase_orders.py` |
| G4 | G4-11 | Batal PR menerima `{notes}` → alasan & pelaku tercatat (layar sudah mengirim) | `backend/routers/purchase_requisitions.py` |
| G4 | G4-30 | Chip status bayar PO tidak menghitung PO batal/ditolak | `backend/routers/purchase_orders.py` |
| G4 | G4-13/19 | Judul "Kontrak Blanket PO · Panggilan Kirim", "Biaya Masuk (landed cost) · Alokasi HPP Roll"; label audit landed cost; "(tidak ada di master)" | `config/navMeta.js`, `config/auditLabels.js`, `hooks/useCatalogMasters.js` |

| G5b | P-11 | Tab bawah aplikasi HP 10px → 11px | `frontend/src/styles/mobile.css` |
| G5b | G5-21 | Antrean server "Payroll menunggu pengesahan" → "Penggajian menunggu pengesahan" | `backend/services/approval_backlog_service.py` |

Belum dikerjakan (dicatat untuk pemilik/tindak lanjut): dari G5b — `entity_master_service` teks bantu ber-backtick
(sudah ditimpa di layar), `entity_lifecycle_service.EDITABLE_FIELDS` kode wilayah (G5-25), `approval_matrix_service`
nama pengaju, `role_reality_service` nomor dokumen, host QR PDF dari URL publik, nomor dokumen di `audit_logs`,
`RoleDesk.jsx` notifikasi lama "tahap: <kode>" (notifikasi baru sudah berlabel); `order_journey_service` menandai langkah verifikasi yang
dilewati (layar sudah menangani), `sales_orders_extra` filter `has_backorder` (menunggu keputusan definisi Backorder),
`return_timeline_service` grade per roll (keputusan G2-15), KNSelect pencarian sisi server (G2-17).
