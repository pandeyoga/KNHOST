# IMPLEMENTATION — GN-15 (SSOT helper & status) + AUTH-05 (matriks izin ber-versi)

- Tanggal: 2026-10-02. Basis `8fcb9dc9588cf14d9eeb534be38168a1c50f23d3` + patch P14/P15 di pohon kerja (SHA kandidat diisi setelah commit platform).
- Catatan: rencana audit hanya punya P00–P14. "P15" di sini adalah label iterasi untuk sisa pekerjaan sesudah P14, **bukan** fase baru di `phases/plan.json`; GN-15 tetap tercatat di fase P02.

## Reproduksi HEAD (sebelum patch, statis)

- `get_settings` di `contract_service`, `lot_service`, `receiving_uom_service`, `uom_rules_service` punya badan AST identik (4 salinan).
- `analytics_catalog.PHYSICAL_ROLL_STATUSES` adalah tuple tulisan tangan **tanpa `wip`**, sedangkan `roll_service.PHYSICAL_ROLL_STATUSES` (dipakai saldo gudang, GL, WAC, RFID) memuat `wip`. Akibatnya stok fisik di Tanya KN/snapshot analitik berbeda dengan saldo gudang bila ada roll WIP.
- AUTH-05: `PUT /permissions` mengganti seluruh matriks tanpa versi. Dua penyimpanan bersamaan → satu hilang (`runs/p14b.txt` putaran sebelumnya: `ra=False rb=True`).

## Perubahan

- `services/config_resolver.policy_settings(scope, defaults, entity_id)` — satu resolver default → global → override badan usaha (+ `entity_overrides`). Keempat `get_settings` mendelegasikan ke sini; perilaku identik (dibuktikan kontrak). `update_settings` sengaja tetap per domain karena validasinya berbeda.
- `services/analytics_catalog.PHYSICAL_ROLL_STATUSES` diturunkan dari `roll_service` (kini termasuk `wip`).
- `GET /permissions` mengembalikan `version`; `PUT /permissions` wajib membawa `version` → simpan atomik `{version}` + `$inc`; versi basi **409**, tanpa versi **400**; audit kini menyimpan matriks sebelum. Frontend (`useAppActions`) menyimpan versi terakhir dan mengirimnya; pesan 409 tampil sebagai notifikasi.

## Regression

- `repro_gn15.py` → [after_patch.txt](after_patch.txt): resolver tunggal, fallback per kunci, override entitas, `all` = global, definisi stok fisik sama di analitik/stock analytics/RFID.
- `repro_p14b_cases.py` AUTH-05: penyimpanan bersamaan → satu 409, versi basi 409, tanpa versi 400, pencabutan izin langsung berlaku.
- Seluruh harness P01–P14 dijalankan ulang → [full_regression_console.txt](full_regression_console.txt).

## Batas

- Penulis lain ke `permission_settings` (editor peran/bootstrap) tidak menaikkan versi; hanya `PUT /permissions` yang dijaga.
- Duplikasi kebijakan lain yang disebut kartu (resolver COA posting vs laporan, evaluator gate simulator vs hardware) sudah ditangani di P05/P09; tidak diubah lagi di sini.
- SALE-02 (POS shift/void/split tender): **tidak berlaku** atas keputusan pemilik `PG-SALE02` (semua penjualan lewat Sales Order); coverage `not_applicable`, premis diverifikasi di `repro_p14b`.
