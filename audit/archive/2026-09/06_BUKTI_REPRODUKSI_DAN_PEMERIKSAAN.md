# Bukti reproduksi dan pemeriksaan

Reproduksi mengompilasi body fungsi asli dari AST snapshot dan mengganti dependency dengan mock deterministik dalam memori. Tidak menulis data aplikasi, tidak mengakses reader/printer dan tidak memakai token repository. Mock DB bukan Mongo: transaksi, index, projection, concurrent scheduling dan permission middleware tidak dibuktikan oleh fixture ini. Setiap defect harus ditambahkan test integrasi saat diperbaiki.

## Hasil fixture

Ada 18 skenario: 16 perilaku cacat/gap berhasil ditunjukkan dan 2 kontrol positif. Untuk cacat, keberhasilan fixture berarti bug teramati, bukan fitur aplikasi lulus. Dua kontrol menunjukkan single overbill ditolak serta rounding allocation konservatif pada kasus sederhana; tidak membenarkan seluruh modul.

### 1. RF-01

Output yang diamati:

```json
{
  "id": "RF-01",
  "observed": {
    "stored": "E253-D716-8405-1743-B7B9-586D",
    "chip_payload": "E253D71684051743B7B9586D",
    "exact_lookup_match": false
  },
  "required": "Canonical EPC must match raw reader output",
  "reproduced": true
}
```

### 2. RF-02

Output yang diamati:

```json
{
  "id": "RF-02",
  "observed": {
    "result": "green",
    "reason": "Keluar ter-otorisasi (status: delivered)."
  },
  "required": "Reject exited roll without live document/source/manifest",
  "reproduced": true
}
```

### 3. RF-03

Output yang diamati:

```json
{
  "id": "RF-03",
  "observed": {
    "result": "green",
    "reason": "Barang transit diterima (status: in_transit_transfer)."
  },
  "required": "Reject transit receipt at wrong destination",
  "reproduced": true
}
```

### 4. RF-04

Output yang diamati:

```json
{
  "id": "RF-04",
  "observed": "Dispatch guard returned successfully without any loading check",
  "required": "Mandatory RFID workflow requires valid shipment check",
  "reproduced": true
}
```

### 5. RF-11

Output yang diamati:

```json
{
  "id": "RF-11",
  "observed": true,
  "required": "Escape ZPL control characters from master data",
  "reproduced": true
}
```

### 6. FN-01

Output yang diamati:

```json
{
  "id": "FN-01",
  "observed": {
    "voucher": 100,
    "actual_inventory_increment": 130.0,
    "rows": [
      {
        "id": "P",
        "length_initial": 70,
        "length_remaining": 70,
        "unit_cost": 11.0,
        "landed_cost_total": 70.0,
        "updated_at": "2026-09-28T00:00:00Z",
        "landed_cost_refs": [
          "LCV1"
        ]
      },
      {
        "id": "C",
        "length_initial": 30,
        "length_remaining": 30,
        "unit_cost": 12.0,
        "parent_roll_id": "P",
        "root_roll_id": "P",
        "updated_at": "2026-09-28T00:00:00Z",
        "landed_cost_refs": [
          "LCV1",
          "LCV1"
        ],
        "landed_cost_total": 30.0
      }
    ]
  },
  "required": "Increment should equal 100 across physical parent/child",
  "reproduced": true
}
```

### 7. FN-02

Output yang diamati:

```json
{
  "id": "FN-02",
  "observed": {
    "match_status": "matched",
    "total_billed": 120,
    "received": 100
  },
  "required": "Block aggregate billing 120 > receipt 100",
  "reproduced": true
}
```

### 8. FN-03

Output yang diamati:

```json
{
  "id": "FN-03",
  "observed": {
    "wac": 95.72,
    "qty": 2.0
  },
  "required": "Both rolls cost 100/m; quantity 1.9144m and WAC 100",
  "reproduced": true
}
```

### 9. FN-04

Output yang diamati:

```json
{
  "id": "FN-04",
  "observed": {
    "operating": -100.0,
    "investing": 100.0,
    "reconciled": true
  },
  "required": "Depreciation-only journal: CFO 0, CFI 0",
  "reproduced": true
}
```

### 10. FN-04B

Output yang diamati:

```json
{
  "id": "FN-04B",
  "observed": {
    "operating": 100.0,
    "investing": -100.0,
    "reconciled": true
  },
  "required": "Credit asset purchase without cash: CFO 0, CFI 0",
  "reproduced": true
}
```

### 11. CONTROL-01

Output yang diamati:

```json
{
  "id": "CONTROL-01",
  "observed": "blocked",
  "required": "Single-line overbilling is blocked",
  "reproduced": true
}
```

### 12. CONTROL-02

Output yang diamati:

```json
{
  "id": "CONTROL-02",
  "observed": 100.0,
  "required": "Allocation rounding conserves voucher total",
  "reproduced": true
}
```

### 13. RF-12

Output yang diamati:

```json
{
  "id": "RF-12",
  "observed": {
    "api_key_returned": true
  },
  "required": "Ordinary list response masks device credential",
  "reproduced": true
}
```

### 14. RF-13

Output yang diamati:

```json
{
  "id": "RF-13",
  "observed": {
    "status": "disabled",
    "accepted": true
  },
  "required": "Disabled device must be rejected",
  "reproduced": true
}
```

### 15. RF-08

Output yang diamati:

```json
{
  "id": "RF-08",
  "observed": {
    "requested_owner": "B",
    "returned_owner": "A"
  },
  "required": "Separate cycle sessions by authorized entity scope",
  "reproduced": true
}
```

### 16. RF-09

Output yang diamati:

```json
{
  "id": "RF-09",
  "observed": {
    "valid_multi_owner_session_blocked_403": true
  },
  "required": "Authorized multi-entity session should accept its scope",
  "reproduced": true
}
```

### 17. FN-05

Output yang diamati:

```json
{
  "id": "FN-05",
  "observed": {
    "code": "4-1000",
    "type": "expense",
    "entity_id": "B"
  },
  "required": "Entity A account must resolve by A, not last unrelated B record",
  "reproduced": true
}
```

### 18. HR-02

Output yang diamati:

```json
{
  "id": "HR-02",
  "observed": {
    "two_hours_pay": 3000.0,
    "hourly_rate": 1000
  },
  "required": "Ordinary day first hour 1.5x + next hour 2x = 3500",
  "reproduced": true
}
```

## Parse frontend

```json
{
  "method": "Parse syntax only; not a build, eslint, React runtime or UI test",
  "checked": 821,
  "errors": []
}
```

821 berkas diparse; tidak ditemukan syntax error. Tidak menilai hook/lifecycle, render, bundle dependency, accessibility atau usability.

## Parse Python

1035 berkas Python diparse; 0 syntax error. Parse tidak mengimpor module atau menjalankan endpoint.

## Pyflakes

| Jenis warning | Jumlah |
|---|---:|
| FStringMissingPlaceholders | 198 |
| RedefinedWhileUnused | 1 |
| UnusedImport | 211 |
| UnusedIndirectAssignment | 2 |
| UnusedVariable | 32 |

Pyflakes 4.0.0 memeriksa 551 berkas; 444 warning total. UndefinedName = 0. Tidak setiap warning merupakan bug; review bisnis menghasilkan temuan terkurasi yang terpisah.

## Artifact credential

Pemeriksaan hanya metadata file nonkosong dan pola umum, bukan pengujian credential terhadap server. Tidak ada nilai token/secrets yang dicetak dalam laporan. Adanya artifact .tok/.tok_mgr pada public snapshot cukup untuk meminta pemeriksaan dan rotasi bila masih berlaku; tidak dibuktikan bahwa token masih valid atau dapat mengakses produksi.

## Batas interpretasi

Risiko konkurensi di laporan berasal dari urutan read/write/CAS yang ditelusuri. Contoh interleaving menunjukkan bagaimana invariant dapat rusak; belum merupakan concurrency load test Mongo. Source yang tampak tidak memiliki guard harus diperiksa terhadap middleware/callers sebelum membuat kesimpulan akses universal. Temuan menuliskan batas itu bila relevan. Pemeriksaan bawaan dengan dependency/DB skip dijelaskan di [cakupan](04_CAKUPAN_DAN_VERIFIKASI.md).
