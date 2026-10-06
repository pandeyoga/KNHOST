# Hasil pengujian dan adjudikasi

Full suite kandidat: **1.549 pass / 467 fail / 72 skip / 173 error**, 2.261 testcase termasukcollectionerror. Pembanding memakai tes kandidat yang sama: **1.540 pass / 463 fail / 73 skip / 185 error**. Assertion tidak diubah. Perubahan adaptasi lokal tercatat di evidence.

**467 fail tidak sama dengan467bug.** Suite lama mencampurkan fixture demo, mutasi yang bergantung state tes lain, event-loopMotor shared, credential/permissionlama dan beberapa oracle statuskode. Semua hasil dipertahankan agar kegagalan tidak disembunyikan.

## Petunjuk klasifikasi seluruh nonpass

| Kategori otomatis | Jumlah testcase nonpass |
|---|---|
| `assertion_or_contract_needs_review` | 318 |
| `async_fixture_loop` | 84 |
| `fixture_credentials_or_auth_contract` | 60 |
| `fixture_login_rate_limit` | 75 |
| `fixture_or_upstream_precondition_needs_review` | 88 |
| `harness_environment_or_collection` | 15 |

Kategori di atas hanya petunjuk dari traceback, bukan verdict seluruhcase. Register `evidence/pytest-adjudication-register.csv` menandai kasus yang masih membutuhkan fixture/kontrak dan rerun independen. Sebuah401/403 dapat merupakan guard yangbenar; sebelummengubahpermission, pahamiaktor danflow sah.

## Semua kandidat nonpass baru pada differential

Perubahanstatus23; lima kandidatnonpassbaru;13berubahmenjadipass. Angka ini tidakmengatribusikan semua perubahan padapatch karena suite stateful.

### `test_iter25_revision_filter.TestRevisionFilter::test_min_revision_zero_returns_all`

Expected is a hardcoded count of all demo design requests (4), actual6. Source revision predicate is unchanged and endpoint returns matching total/items. Fixture/global-state difference; not independently proved as application regression.

### `test_iter25_revision_filter.TestRevisionFilter::test_no_min_revision_returns_all_four`

Same count oracle as above. Requires an isolated set of exactly4 owned documents; normal extra documents must not make a pagination/filter test fail.

### `test_iter276_g2_md_audit.TestAlurJ::test_J5_designer_hanya_melihat_tiga`

The negative access-control assertion (unassignedDSR-00001 absent) passes; only hardcoded total3vs5 fails. Source query still assigned_to=actor.id. Extra assigned records require fixture review, not a claim of cross-user visibility.

### `test_sesi14_idempotency::test_idempotency_scan_pick`

Fails before exercising idempotency because no created outbound template exists. Stateful fixture precondition, not proof duplicate picks occur.

### `test_w2_targeted.TestW2_017_ConcurrentDepositUse::test_two_concurrent_receipts_one_wins_one_409`

Exactly one200; losing worker400 Deposit tidak cukup (remaining20) instead of409. Status-code/race-order oracle differs; result does not prove doubleuse. Separate V3-AR-01 fault window remains confirmed and is not dismissed by this safe contention rejection.


## Replay core dan extended

Core:15skrip,310assertionterekstrak,299pass/11fail. Extended:41skrip,448assertion,403pass/45fail; empat skrip exitnonzero/timeout. W2 mempunyai formatPASS tersendiri; count diperbarui dari log asli, semua empat skrip exit0.

Kegagalan extended mencakup: font OCR yangtidakada padaWindowsfixture; restore test menggunakan replacementNone; prasyarat payroll tanpa activeemployee; beberapa headerpermissionlama; transfer/return menggunakan roll yangbukan lagiowner/scopebaris; recovery/cut fixture belum memenuhi verifikasitag terbaru; dan beberapa branch belumteruji karena skenario berhenti sebelumnya. Tidak diberi statusbug tanpa counterexampleoriginal yangterarah.

**Kasus produksi tetap diperiksa terpisah:** faultinject stock/movement, reversal, ARreceipt, bankallocation, makloonoutput, cut dan masterbatch menghasilkan17counterexamplelama yang tetapvalid. Runtime data-lineage dan pureJS probes memakai expected independen yang dijelaskan pada tiapcatatan. Test-nya tidak sekadar memintaHTTP200.

## Batas collection dan adaptasi

Dua modul memilikiimportfilemismatch pada collection; modul `test_wilayah_extra.py` mempunyaimodule-levelSystemExit dan `test_notifications_iter33.py` mempunyaimodule-sideeffect/subprocess. Dua terakhir tidak dijalankan dalamfullsuite. Copy test mengubah lokasi sehingga beberapaROOTderivedpath lama bisa menjadi invalid; ini limitation harness, tidak dibebankan sebagaibug aplikasi. Loop/lifecyclefixture memerlukan isolasi permodul.

Buildfrontendcandidate **Compiled successfully** memakai dependencycache lokal yang sebelumnya terpasang; ESLintplugin dinonaktifkan. Ini bukti build, bukan hasil lint bersih, freshlockedinstall ataupun E2EUI. Nodewarning dan detailbundlesize ada di evidence/frontend-build.log.

## Kontrol kualitas oracle

`D4-TEST-01` menemukan test yang hanya print/write ATPmismatch tanpa assert yangmenolakmismatch. Status hijau tes tersebut tidakmenutup formula. Independentfixture dan pemisahan free/physical/ATP/pending/incoming diperlukan sebelum memperbaiki expected.

Tidak ada klaim seluruh nonpass telah dituntaskan atau coveragebehavior100%. Registry menyediakan pekerjaan yangterukur untuk melengkapi validasi, dan temuan yangdiberi confirmed mempunyai bukti terpisah.
