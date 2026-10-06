# Fase 05 — Frontend, tests dan closure evidence

Audit baseline `d6da1a3d536228582645abb98aea19f3e491f300`. Baca tracker/temuan rinci dan source saat ini; repo dapat berubah setelah audit. Kerjakan source producer→projection→API→UI dan failure/reversal windows, bukan hanya file yang disebut. Jangan mengganti oracle untuk menutupi bug. Setelah implementasi, tandai implemented_pending_validation dengan commit, daftar file, expected/actual uji, unit/periode/scope, serta batas uji. Jangan mengklaim fixed sebelum review independen.

## V3-DUP-01 — Helper _clean_perms didefinisikan dua kali

**Prioritas:** P3 · **Status:** confirmed_open · **Bukti:** static_quality_observation.

**Letak:** [backend/services/custom_role_service.py:60](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/services/custom_role_service.py#L60).

**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** AST seluruh backend menemukan dua definisi top-level identik pada baris60 dan67. Definisi kedua menimpa pertama; body kini sama sehingga ini maintainability debt, bukan beda perilaku akses.

**Dampak dan batas interpretasi:** Dua definisi identik pada file yang sama; syntax parser tidak menolaknya.

**Observasi:** Dua definisi identik pada file yang sama; syntax parser tidak menolaknya.

```python
  57:     return out
  58: 
  59: 
  60: def _clean_perms(perms: Any) -> Dict[str, List[str]]:
  61:     try:
  62:         return clean_permissions(perms)
  63:     except ValueError as exc:
  64:         raise HTTPException(status_code=400, detail=str(exc)) from exc
  65: 
  66: 
  67: def _clean_perms(perms: Any) -> Dict[str, List[str]]:
```

**Prompt perbaikan:**

> Periksa `V3-DUP-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Hapus definisi identik dengan satu canonical helper; tambahkan deteksi duplicate top-level definition dalam quality check yang sesuai, tanpa menggandakan business-rule tests. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Satu definisi, custom permission normal/error contract tetap sama. Jangan menjadikan ini P1 atau menghitungnya sebagai bug akses yang sudah terbukti.

**Hubungan dengan catatan lain:** GN-15

## V3-BUILD-01 — Dependency build frontend tidak mempunyai lockfile terlacak

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** static_quality_observation.

**Letak:** [frontend/package.json:151](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/frontend/package.json#L151).

**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Repo mendeklarasikan Yarn1.22.22 tetapi tidak melacak yarn.lock, package-lock.json atau pnpm-lock.yaml. Fresh install harus meresolusikan dependency transitive; dua build tidak mempunyai dependency graph terkunci.

**Dampak dan batas interpretasi:** Install lokal melaporkan No lockfile found; build berhasil dengan warnings memakai dependency graph yang diselesaikan hari audit. Ini risiko reproducibility, bukan bukti frontend gagal build.

**Observasi:** Install lokal melaporkan No lockfile found; build berhasil dengan warnings memakai dependency graph yang diselesaikan hari audit. Ini risiko reproducibility, bukan bukti frontend gagal build.

```json
 148:     "**/tinyglobby/picomatch": "4.0.4",
 149:     "http-proxy-middleware": "2.0.10"
 150:   },
 151:   "packageManager": "yarn@1.22.22+sha512.a6b2f7906b721bba3d67d4aff083df04dad64c399707841b7acf00f6b133b7ac24255f2652fa22ae3534329dc6180534e98d17432037ff6fd140556e2bb3137e"
 152: }
```

**Prompt perbaikan:**

> Periksa `V3-BUILD-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Commit satu lockfile canonical sesuai packageManager; pipeline harus gagal jika lock tidak ada/berbeda dan memakai frozen/immutable install. Simpan runtime versions dan dependency integrity. Jangan commit node_modules/build/.env. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fresh isolated install pada dua runner memakai graph/integrity sama. Build smoke lulus dari lock, lint warning relevan ditinjau; packageManager dan pipeline tidak saling memilih manager berbeda.

**Hubungan dengan catatan lain:** GN-15

## D4-FE-01 — Grafik velocity Manager selalu memotong menjadi14hari

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [frontend/src/features/manager/ManagerDashboard.jsx:100](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/frontend/src/features/manager/ManagerDashboard.jsx#L100).

**Tampilan / rantai terkait:** Manager Dashboard: periode 7/30/90 vs velocity chart · Period selector → reporting velocity → frontend slicing.

**Penyebab:** Dataset velocity dari API dipotong slice(-14) tanpa mengikuti period pilihan.

**Dampak dan batas interpretasi:** OriginalJS expression diuji: input7 tampil7(control), input30/90 masing-masing14. Judul/periode dapat memberikan kesan datasetlengkap.

- `D4-FE-01-chart-7` — expected `7`; actual `7`; `pass`.
- `D4-FE-01-chart-30` — expected `30`; actual `14`; `observed_difference`.
- `D4-FE-01-chart-90` — expected `90`; actual `14`; `observed_difference`.

```javascript
  97:   useEffect(() => { load(); }, [period, agingDays, selectedEntity]);
  98: 
  99:   const funnelChartData = (funnel?.funnel || []).filter(f => !["cancelled", "expired"].includes(f.status));
 100:   const velocityData = (velocity?.velocity || []).slice(-14); // last 14 days
 101:   const utilizationData = utilization.map(w => ({
 102:     name: w.warehouse_city || w.warehouse_name,
 103:     on_hand: w.on_hand_qty,
 104:     capacity: w.total_capacity,
 105:     pct: w.utilization_pct,
 106:   }));
 107: 
```

**Prompt perbaikan:**

> Periksa `D4-FE-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan range period yang sama dengan request atau label last14days secara eksplisit jika itu tujuan grafik. Jangan memotong data tanpa indikasi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Periode7/30/90 menunjukkan dataset sesuai tanggalpilihan; emptydays tetapkontrak API, boundarydates/labeltooltip diperiksa diUI.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-FE-02 — Respons lama dapat menimpa dashboard setelah pengguna beralih entitas

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [frontend/src/features/manager/ManagerDashboard.jsx:69](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/frontend/src/features/manager/ManagerDashboard.jsx#L69).

**Tampilan / rantai terkait:** Manager Dashboard entity/filter controls · Entity switch → concurrent API requests → React state.

**Penyebab:** load/useEffect tidak membatalkan request lama atau menjaga generation. RequestA lambat selesai setelahB dan menulis stateA meskipun selectionB.

**Dampak dan batas interpretasi:** Transportterkontrol menjalankan original load: B selesai→stateB benar; A selesai kemudian→stateA. Probe function-level, tidak mengklaim browserE2E atau semua halaman memiliki bug yang sudahteruji.

- `D4-FE-02-after-current-response` — expected `"B"`; actual `"B"`; `pass`.
- `D4-FE-02-stale-entity-overwrite` — expected `"B"`; actual `"A"`; `observed_difference`.

```javascript
  66: 
  67:   const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  68: 
  69:   const load = async () => {
  70:     setLoading(true);
  71:     // F0-E: laporan ter-scope per entitas aktif ('all' = oversight lintas-PT).
  72:     const ent = selectedEntity || "all";
  73:     const cfg = { headers, params: { entity_id: ent } };
  74:     try {
  75:       const [sumRes, funnelRes, velRes, custRes, utilRes, agingRes] = await Promise.all([
  76:         axios.get(`${API}/reports/summary`, cfg),
```

**Prompt perbaikan:**

> Periksa `D4-FE-02` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Implement generationguard/AbortController yang melindungi semua setters termasuk loading/error. Data beberapaendpoint harus satu requestgeneration. Audit pola sama dihalaman lain dengan probe terpisah. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** SwitchA→B dan responseoutoforder: semuakartu/chart B; staleerrors dan finallyA tidakmengubahB. Rapidperiod/categorychanges, unmount dan combinedpartialfail diperiksa.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-TEST-01 — Tes konsistensi ATP dapat lulus walaupun mencatat mismatch

**Prioritas:** P2 · **Status:** open_definition_or_test_gap · **Bukti:** source_review_test_oracle.

**Letak:** [backend/tests/test_iter149_audit.py:116](https://github.com/pandeyoga/KNHOST/blob/d6da1a3d536228582645abb98aea19f3e491f300/backend/tests/test_iter149_audit.py#L116).

**Tampilan / rantai terkait:** Verification pipeline / ATP oracle · Inventory report → old regression test → green status.

**Penyebab:** test_stock_atp_sum_matches mengumpulkan bad_row/bad_wh dan menulis/print hasil tanpa assert terakhir yang menolak mismatch. Formula lama juga perlu diselaraskan dengan pendingdemandyang didokumentasikan.

**Dampak dan batas interpretasi:** Green test ini hanya membuktikanHTTP/listshape, bukan ATPformula benar. test_iter150 memilikiassert yang lebihbermakna sehingga perbaikannya harus menghindari oracle lama yangsalah.

**Observasi:** {}

```python
 113:     assert r.status_code == 200, r.text
 114:     rows = r.json()
 115:     assert isinstance(rows, list)
 116:     bad_row = []
 117:     bad_wh = []
 118:     for row in rows:
 119:         av = float(row.get('total_available') or 0)
 120:         inc = float(row.get('total_incoming') or 0)
 121:         rsv = float(row.get('total_reserved') or 0)
 122:         atp = float(row.get('total_atp') or 0)
 123:         expected = av + inc - rsv
```

**Prompt perbaikan:**

> Periksa `D4-TEST-01` pada commit `d6da1a3d536228582645abb98aea19f3e491f300` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Definisikan formulaavailability/ATP bersama timbisnis, buat independentoracle dengan fixture partialreserve/hold/pending/incoming. Tambahkan assertionmismatch dan test-negatif yangmemastikanoracle gagal terhadapmutasi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** InjectwrongATP→testFAIL; correctformula→PASS. Uji fixture>100SKU, multiowner, pendingcut, externalincoming dan no-dependencydemoaccount.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

