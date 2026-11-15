# Test Credentials — KNHOST (lokal audit, test_database)

Seed: `bash scripts/restore_local_demo.sh` · DB `test_database` · backend 8001 · password semua akun: `demo12345`

| email | role |
|---|---|
| admin@kainnusantara.id | admin |
| sales@kainnusantara.id | sales |
| salesadmin@kainnusantara.id | sales_admin |
| manager@kainnusantara.id | manager |
| md@kainnusantara.id | md |
| mdquality@kainnusantara.id | md_quality |
| qc@kainnusantara.id | qc |
| warehouse@kainnusantara.id | warehouse |
| whadmin@kainnusantara.id | warehouse_admin |
| finance@kainnusantara.id | finance |
| designer@kainnusantara.id | designer |
| sampleadmin@kainnusantara.id | sample_admin |

Catatan: `backend/.env` lokal di-set (MONGO_URL, DB_NAME=test_database, CORS_ORIGINS) untuk menjalankan app di sandbox audit. JANGAN commit `.env`.
