# Fase 05 — Frontend, tests dan closure evidence

Audit baseline `a904d989b622f7da14c4892d03cf6ef0c43f3084`. Baca tracker/temuan rinci dan source saat ini; repo dapat berubah setelah audit. Kerjakan source producer→projection→API→UI dan failure/reversal windows, bukan hanya file yang disebut. Jangan mengganti oracle untuk menutupi bug. Setelah implementasi, tandai implemented_pending_validation dengan commit, daftar file, expected/actual uji, unit/periode/scope, serta batas uji. Jangan mengklaim fixed sebelum review independen.

## V3-DUP-01 — Helper _clean_perms didefinisikan dua kali

**Prioritas:** P3 · **Status:** confirmed_open · **Bukti:** static_quality_observation.

**Letak:** [backend/services/custom_role_service.py:60](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/custom_role_service.py#L60).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** AST seluruh backend menemukan dua definisi top-level identik pada baris 60 dan 67. Definisi kedua menimpa pertama; body kini sama sehingga ini maintainability debt, bukan beda perilaku akses.

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

> Periksa `V3-DUP-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Hapus definisi identik dengan satu canonical helper; tambahkan deteksi duplicate top-level definition dalam quality check yang sesuai, tanpa menggandakan business-rule tests. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Satu definisi, custom permission normal/error contract tetap sama. Jangan menjadikan ini P1 atau menghitungnya sebagai bug akses yang sudah terbukti.

**Hubungan dengan catatan lain:** GN-15

## V3-BUILD-01 — Dependency build frontend tidak mempunyai lockfile terlacak

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** static_quality_observation.

**Letak:** [frontend/package.json:151](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/package.json#L151).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Repo mendeklarasikan Yarn 1.22.22 tetapi tidak melacak yarn.lock, package-lock.json atau pnpm-lock.yaml. Fresh install harus meresolusikan dependency transitive; dua build tidak mempunyai dependency graph terkunci.

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

> Periksa `V3-BUILD-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Commit satu lockfile canonical sesuai packageManager; pipeline harus gagal jika lock tidak ada/berbeda dan memakai frozen/immutable install. Simpan runtime versions dan dependency integrity. Jangan commit node_modules/build/.env. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fresh isolated install pada dua runner memakai graph/integrity sama. Build smoke lulus dari lock, lint warning relevan ditinjau; packageManager dan pipeline tidak saling memilih manager berbeda.

**Hubungan dengan catatan lain:** GN-15

## D4-FE-01 — Grafik velocity Manager selalu memotong menjadi 14 hari

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [frontend/src/features/manager/ManagerDashboard.jsx:100](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/manager/ManagerDashboard.jsx#L100).



**Tampilan / rantai terkait:** Manager Dashboard: periode 7/30/90 vs velocity chart · Period selector → reporting velocity → frontend slicing.

**Penyebab:** Dataset velocity dari API dipotong slice(-14) tanpa mengikuti period pilihan.

**Dampak dan batas interpretasi:** JavaScript asli expression diuji: input 7 tampil 7(control), input 30/90 masing-masing 14. Judul/periode dapat memberikan kesan dataset lengkap.

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

> Periksa `D4-FE-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan range period yang sama dengan request atau label 14 hari terakhir secara eksplisit jika itu tujuan grafik. Jangan memotong data tanpa indikasi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Periode 7/30/90 menunjukkan dataset sesuai tanggalpilihan; emptydays tetapkontrak API, batas tanggal/label tooltip diperiksa diUI.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-FE-02 — Respons periode lama dapat menimpa grafik setelah periode diganti

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [frontend/src/features/manager/ManagerDashboard.jsx:69](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/manager/ManagerDashboard.jsx#L69).



**Tampilan / rantai terkait:** Manager Dashboard → pilihan periode / aging days pada entitas yang sama · Period 30 → period 90 → concurrent API load → old 30 response → React state.

**Penyebab:** load/useEffect tidak membatalkan request lama atau menjaga generation. Pergantian periode tidak remount komponen; request 30 yang selesai setelah 90 menulis ulang data. App.js L528 memakai key selectedEntity, sehingga hipotesis awal pergantian entitas ditarik: probe lama melewati remount.

**Dampak dan batas interpretasi:** Original function load pada entitas A: respons periode 90 selesai dan field total_orders yang dipakai UI bernilai 90; respons periode 30 selesai belakangan lalu total_orders menjadi 30 saat pilihan masih 90. Bukti ini JavaScript function-level dengan transport terkontrol, bukan browser E2E. Klaim entity-overwrite pada draf historis tidak dipakai sebagai temuan.

- `D4-FE-02-after-current-period-response` — expected `90`; actual `90`; `pass`.
- `D4-FE-02-stale-period-overwrite` — expected `90`; actual `30`; `observed_difference`.

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

> Periksa `D4-FE-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Implement generation guard/AbortController yang melindungi seluruh setters termasuk loading/error pada pergantian periode, aging days dan refresh. Data beberapa endpoint harus satu request generation. Pertahankan remount entitas yang sudah ada; audit pola halaman lain dengan bukti terpisah. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Pada entitas sama, period 30→90 dan respons out-of-order: grafik tetap 90; respons/error/finally 30 tidak mengubah state 90. Uji aging-days, refresh, unmount dan partial failure. Uji browser diperlukan untuk validasi rendered UI.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-TEST-01 — Tes konsistensi ATP dapat lulus walaupun mencatat mismatch

**Prioritas:** P2 · **Status:** open_definition_or_test_gap · **Bukti:** source_review_test_oracle.

**Letak:** [backend/tests/test_iter149_audit.py:116](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/tests/test_iter149_audit.py#L116).



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

> Periksa `D4-TEST-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Definisikan formulaavailability/ATP bersama timbisnis, buat independentoracle dengan fixture partialreserve/hold/pending/incoming. Tambahkan assertionmismatch dan test-negatif yangmemastikanoracle gagal terhadapmutasi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** InjectwrongATP→testFAIL; correctformula→PASS. Uji fixture>100SKU, multiowner, pendingcut, externalincoming dan no-dependencydemoaccount.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-PLAN-04 — Pesan kegagalan pemenuhan parsial terhapus oleh refresh otomatis

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** javascript_function_counterexample.

**Letak:** [frontend/src/features/sales_admin/FulfillmentDecisionDialog.jsx:59](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/sales_admin/FulfillmentDecisionDialog.jsx#L59).



**Tampilan / rantai terkait:** Dialog Rencana pemenuhan: ErrorNotice · POST partial failure → catch error → load GET → setError empty.

**Penyebab:** submit menaruh pesan error lalu memanggil load; saat GET sukses load menjalankan setError kosong sehingga pesan kegagalan dan informasi bagian yang telah diproses hilang.

**Dampak dan batas interpretasi:** Function asli menghasilkan error transitions kosong → Interco failed; stock 30 already executed → kosong. Operator kehilangan pesan penting sebelum melanjutkan. Bukti ini function-level JavaScript dengan transport terkontrol, bukan uji browser.

- `D4-PLAN-04-error-erased` — expected `"Interco failed; stock30 already executed and persisted"`; actual `""`; `observed_difference`.

```javascript
  56:       };
  57:       const res = await fulfillmentPlanDecide(orderId, body);
  58:       onDecided?.(`${res?.order_number || orderNumber}: ${res?.decision?.summary || "rencana pemenuhan tercatat."}`);
  59:     } catch (e) { setError(apiErrorText(e, "Gagal menjalankan rencana pemenuhan.")); load(); }
  60:     finally { setBusy(false); }
  61:   }
  62: 
  63:   return (
  64:     <div className="modal-overlay" data-testid="fulfill-dialog" onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
  65:       <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 920, maxHeight: "92vh", overflowY: "auto" }}>
  66:         <div className="flex flex-wrap items-start justify-between gap-2">
```

**Prompt perbaikan:**

> Periksa `D4-PLAN-04` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Pisahkan load error dari execution error dan pertahankan hasil partial sampai pengguna menutupnya. Refresh data tidak boleh menghapus pesan proses yang belum diakui. Jelaskan bagian sukses, gagal dan tindakan lanjutan. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** POST gagal parsial lalu GET sukses tetap menampilkan pesan dan bagian 30 yang sukses. GET gagal harus menampilkan kedua konteks dengan jelas. Lengkapi browser test tanpa mengubah oracle.

**Hubungan dengan catatan lain:** D4-PLAN-03, D4-FE-02

## D4-ORDER-01 — Rata-rata pesanan membagi revenue seluruh pesanan dengan hanya 20 pesanan terbaru

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** public_api_to_original_javascript_counterexample.

**Letak:** [frontend/src/features/orders/OrderDashboard.jsx:74](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/orders/OrderDashboard.jsx#L74).



**Tampilan / rantai terkait:** Pesanan → Dasbor: jumlah orders, Rata-rata Pesanan, Top Customers, Status Distribution dan Expiring · Public /dashboard cap 20 → App state data.orders → OrdersView orders prop → OrderDashboard metrics; /sales-orders/stats/summary aggregate semua pesanan.

**Penyebab:** Patch revenue memakai summary.revenue[period].grand_total seluruh pesanan, tetapi denominator recentOrders.length tetap dari window 20. Server sudah menyediakan revenue.count untuk populasi dan status yang sama; consumer mengabaikannya. Top Customers dan status/pending/expiry juga memakai window lokal tanpa label cakupan. Halaman list memakai pagination dan summary server, sehingga list benar tidak membuktikan dasbor benar.

**Dampak dan batas interpretasi:** Fixture 30 SO confirmed 100 pada entitas dan periode sama: original public API memberikan orders 20 dan revenue 3000/count 30. Original JavaScript useMemo memberi totalRevenue 3000 (kontrol PASS), totalOrders 20 dan avg 150 padahal 100. Top Customers untuk customer yang sama hanya 2000 padahal 3000. Ini source-grain mismatch, bukan kesalahan operasi pembagian. Tidak ada klaim bahwa seluruh tabel latest 10 salah; batas 10 pada Recent Orders diberi label jelas.

- `D4-ORDER-01-revenue-control` — expected `3000`; actual `3000`; `pass`.
- `D4-ORDER-01-count` — expected `30`; actual `20`; `observed_difference`.
- `D4-ORDER-01-average` — expected `100`; actual `150`; `observed_difference`.
- `D4-ORDER-01-customer-revenue` — expected `3000`; actual `2000`; `observed_difference`.

```javascript
  71:       totalOrders: recentOrders.length,
  72:       pendingOrders: pendingOrders.length,
  73:       expiringSoon: expiringSoon.length,
  74:       avgOrderValue: recentOrders.length > 0 ? totalRevenue / recentOrders.length : 0,
  75:       topCustomers,
  76:       statusCounts,
  77:       recentOrders: orders.slice(0, 10)
  78:     };
  79:   }, [orders, timeRange, summary]);
  80:   
  81:   const formatCurrency = (amount) => {
```

**Prompt perbaikan:**

> Periksa `D4-ORDER-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan revenue.count sebagai denominator jika rata-rata didefinisikan atas status terpenuhi; definisikan totalOrders terpisah bila mencakup semua status. Hitung Top Customers, distribusi status, pending dan expiry di server dengan scope entity/sales-owner/line/periode yang sama. Label setiap pengecualian periode atau dataset parsial. Jangan memuat seluruh dokumen di browser untuk memperbaiki agregat. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** 30 SO confirmed 100 menghasilkan revenue 3000/count 30/avg 100 dan customer revenue 3000. Uji >20 dan >200, mix reserved/cancelled/fulfilled, periode 7/30/90, sales-owner, line scope dan perubahan filter. Bandingkan seluruh widget dengan source query independen; Recent Orders tetap boleh 10 dengan labelnya.

**Hubungan dengan catatan lain:** D4-DASH-01, D4-FE-01

## D4-DOC-01 — Pratinjau Template Dokumen Dasar memanggil endpoint yang tidak tersedia dan mengabaikan jenis template

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** original_public_api_to_original_javascript_contract_counterexample.

**Letak:** [frontend/src/hooks/useAppActions.js:616](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/hooks/useAppActions.js#L616).

**Lokasi kode lain dalam rantai:** [frontend/src/features/admin/AdminView.jsx:542](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/admin/AdminView.jsx#L542) · [frontend/src/AppViewRouter.jsx:260](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/AppViewRouter.jsx#L260) · [backend/routers/documents.py:283](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/documents.py#L283).

**Tampilan / rantai terkait:** Pengaturan → Template Dokumen Dasar → Pratinjau pada baris template; iframe live preview · nav doc-templates-basic → AdminView templates → row button → AppViewRouter onPreviewTemplate → useAppActions.previewTemplate → missing POST route.

**Penyebab:** Callback melakukan POST /document-templates/{id}/preview, tetapi aplikasi hanya menyediakan GET /documents/preview/{order_id} beserta CRUD template. Original hook juga mematok document_type invoice walaupun row yang dipilih adalah Surat Jalan. Jalur ini masih terhubung pada activeView doc-templates-basic, sehingga bukan hanya fungsi lama yang tidak pernah dipakai.

**Dampak dan batas interpretasi:** Original public creator membuat template Surat Jalan yang dapat dilihat lewat GET list; satu SO state fixture milikA tersedia. Exact POST dari UI mendapat 404. Original hook dengan original 404 memberi notice Not Found dan tidak mengisi previewHtml. Transport control membuktikan URL yang dipanggil; request body invoice padahal selected row surat_jalan. Existing GET document preview memberi 200 HTML pada fixture sama, sehingga bukan masalah seluruh renderer atau data kosong. DOM tidak diuji; SO fixture bukan full create/fulfill producer.

- `D4-DOC-01-existing-template-control` — expected `{"http": 200, "exists": true}`; actual `{"http": 200, "exists": true}`; `pass`.
- `D4-DOC-01-preview-contract` — expected `200`; actual `404`; `observed_difference`.
- `D4-DOC-01-alternative-renderer-control` — expected `{"http": 200, "html": true}`; actual `{"http": 200, "html": true}`; `pass`.
- `D4-DOC-01-original-route-control` — expected `"http://audit.local/api/document-templates/tmpl_437b60725d91/preview"`; actual `"http://audit.local/api/document-templates/tmpl_437b60725d91/preview"`; `pass`.
- `D4-DOC-01-selected-template-document-type` — expected `"surat_jalan"`; actual `"invoice"`; `observed_difference`.
- `D4-DOC-01-original-preview-html` — expected `true`; actual `false`; `observed_difference`.

```javascript
 613: 
 614:   const previewTemplate = async (templateId, orderId) => {
 615:     try {
 616:       const response = await axios.post(`${API}/document-templates/${templateId}/preview`, { document_type: "invoice", source_id: orderId, actor: user?.name || "Admin" }, { responseType: "text" });
 617:       setPreviewHtml(response.data);
 618:       setNotice("Preview template diperbarui.");
 619:     } catch (error) {
 620:       setNotice(error.response?.data?.detail || "Preview template gagal. Pastikan ada order untuk preview.");
 621:     }
 622:   };
 623: 
```

**Prompt perbaikan:**

> Periksa `D4-DOC-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Satukan kontrak preview berdasarkan source document dan selected template ID/type. UI meneruskan jenis template yang dipilih; server memvalidasi entity, permissions, template effective layer dan kompatibilitas source tanpa membuat generated document/transaksi. Jangan sekadar mengganti endpoint ke GET yang mengabaikan selected ID. Pastikan template dasar dan PDF designer mempunyai batas fitur yang jelas dan dokumen yang benar-benar dicetak memakai format/field yang sama dengan preview. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Admin membuka Template Dokumen Dasar dengan SO yang sah: Pratinjau template Surat Jalan/invoice/jenis lain memberi 200 HTML untuk selected template dan document type yang tepat. Dua template tipe sama harus dapat dipratinjau berbeda sesuai ID, global vs entity override terkontrol, source berbeda entitas ditolak, disabled template ditangani jelas, tanpa generated-doc atau ledger side effect. Uji empty orders, permissions, invalid template/source, error recovery, iframe HTML dan output cetak.

**Hubungan dengan catatan lain:** D4-FE-02

