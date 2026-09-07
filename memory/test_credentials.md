# Test Credentials
# Agent writes here when creating/modifying auth credentials (admin accounts, test users).
# Testing agent reads this before auth tests. Fork/continuation agents read on startup.

Lingkungan lokal pengujian saja. Base URL API: baca REACT_APP_BACKEND_URL di /app/frontend/.env.
Konteks badan usaha uji: ent_ksc (header X-Entity-Id; pilih badan usaha yang sama di layar).

- Admin: admin@kainnusantara.id / demo12345
- MD (merchandiser): md@kainnusantara.id / demo12345
- Manajer: manager@kainnusantara.id / demo12345
- Sales: sales@kainnusantara.id / demo12345
- Admin Sales: salesadmin@kainnusantara.id / demo12345
- Finance: finance@kainnusantara.id / demo12345
- Gudang: warehouse@kainnusantara.id / demo12345

Login UI testid: login-email-input, login-password-input, login-submit-button.
Routing uji: ?view=md-products&entity=ent_ksc · ?view=rnd-specs&entity=ent_ksc · ?view=sales.
KNSelect: opsi <testid>-option-<value>, pencarian <testid>-search.
Gunakan prefix TEST_ untuk data baru; bersihkan hanya ID uji.
Jika akun md@ hilang setelah seed: `supervisorctl restart backend` (bootstrap idempoten).
