# Perubahan kandidat dan histori

Baseline `5b7f34122bd104f4426ccd7f72b38fb7969eda8f` → current `a904d989b622f7da14c4892d03cf6ef0c43f3084`: 799 path berubah. Tahap sesi `d6da1a3d536228582645abb98aea19f3e491f300` → current: 753 path berubah, 49 file backend/frontend code. Banyak path berupa artefak audit UX dan screenshot; jumlah path bukan ukuran kedalaman perbaikan bisnis.

Daftar lengkap tersedia pada `source-delta.csv`. Inventaris current, syntax parse, test suite, counterexample dan route execution memakai commit a904. Dokumen historis d6da disimpan pada `history/stage-d6da1a3`, beserta erratum FE-02; jangan menggabungkan count/status tahap berbeda.

| Patch terlihat | Bukti current | Kesimpulan |
|---|---|---|
| Dashboard master cap 100→3000 |103 SKU lulus;3003 SKU dengan material reserve pada SKU terakhir gagal KPI | Perbaikan parsial; D4-DASH-01 diperbarui, klaim cap 100 ditutup |
| Revenue aggregate server |30 confirmed orders 100 → grand 3000/count 30 | Producer sudah benar; denominator dan customer aggregate UI masih salah |
| Global stock/incoming |Physical combined stock tersedia; PO yard→base producer benar | Incoming consumer kehilangan unit dan partial status |
| Split fulfillment plan |Stock/reorder/interco/wait dapat disusun | Referenced qty, duplicate input, partial scope dan exclusive supply belum konsisten |
| Admin override policy |Explicit bypass/self-approval sesuai policy baru | Tidak otomatis dicatat sebagai SoD bug; requirement tetap perlu disepakati |
| New integration tests |14 pass/3 fail/5 skip | Fallback PR/hardcoded fixture membatasi real-chain proof |
