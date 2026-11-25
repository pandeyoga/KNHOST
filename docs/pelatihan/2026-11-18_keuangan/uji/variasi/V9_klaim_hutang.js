// V9 · HUTANG & PAJAK — bukti di LAYAR untuk klaim teks materi F11–F13 dan A2 yang belum dibuktikan uji lain.
// Tiap langkah = satu klaim (`kode · klaim`), dikerjakan dengan akun peran yang benar lalu dicocokkan dengan buku.
//
//   cd backend && python ../docs/pelatihan/2026-11-18_keuangan/uji/variasi/V9_siapkan.py --peserta 89 --po 2
//   KN_BLOK="tagihan:89,kontrabon:90,faktur:90" node docs/pelatihan/2026-11-18_keuangan/uji/variasi/V9_klaim_hutang.js
//
// Data: tagihan F11 & tagihan kontrabon peserta (belum dibayar, belum dikontrabon), SO peserta tanpa faktur pajak, dan
// PO 2 yard yang diterima gudang tetapi belum ditagih (`v9:po_terima`, blok tagihan). Hasil → uji/hasil/V9/hutang-<blok>/.
const { Run, assert, kartu, akunPeserta, rp, num, sleep, mongo } = require("../lib");
const { REK_BCA, pilih, setuju, jurnalDari, tungguTeks, tungguToast } = require("../hutang_lib");
const k9 = require("./v9lib");

const KSC = "&entity=ent_ksc";


// ── Blok TAGIHAN (F11, A2, K02) ──────────────────────────────────────────────────────────────────────────────────────
async function blokTagihan(r, d, NO) {
  const step = (meta, fn) => k9.klaim(r, d, meta, fn);
  const K = kartu(NO);
  // KN_PO_KUNCI: kartu PO lain (mis. `v9:po_terima_2` dari `V9_siapkan.py --kunci`) bila PO pertama sudah ditagih.
  const tb = K["a_dasar:tagihan_bayar"]; const tk = K["a_dasar:tagihan_kontrabon"]; const po = K[process.env.KN_PO_KUNCI || "v9:po_terima"];
  const soFaktur = K["a_dasar:so_lunas"];
  const SFX = po ? po.po.split("-").pop() : "";   // No. faktur pemasok unik per PO uji
  const bukaHutang = async () => {
    await r.tid("nav-accounts-payable").click().catch(async () => {
      await r.tid("nav-group-toggle-keuangan").click(); await r.tid("nav-accounts-payable").click();
    });
    await r.tid("vendor-bills-view").waitFor();
    await r.idle(500);
  };
  const tagihanPo = (poId) => mongo(`return db.vendor_bills.find({po_id:"${poId}",status:{$ne:"cancelled"}},{_id:0}).sort({created_at:1}).toArray()`);
  assert(tb && tk && po && soFaktur, `Kartu peserta ${NO} belum lengkap (tagihan, v9:po_terima)`);
  assert(!tagihanPo(po.po_id).length, `${po.po} sudah ditagih — siapkan PO baru (V9_siapkan.py)`);
  const vbTb = mongo(`return db.vendor_bills.findOne({id:"${tb.tagihan_id}"},{_id:0,status:1,supplier_invoice_no:1,bill_number:1})`);
  r.note(`Peserta ${NO} · ${tb.tagihan} (${vbTb.supplier_invoice_no}, ${vbTb.status}) · ${tk.tagihan} · ${po.po} ${po.qty} yard · ${soFaktur.so}`);

  // ── F11: Finance tidak membuat/membatalkan tagihan; GR/IR tanpa 'Tampilkan yang sudah nol' ──────────────────────
  await r.login(akunPeserta(NO));
  await step({ kode: "F11", bagian: "catatan_pelatih", peran: "Finance",
    klaim: "Finance boleh melihat dan membayar tagihan; membuat dan membatalkan tagihan tetap wewenang Manajer",
    harap: "Daftar Tagihan untuk Finance: tanpa [Buat Tagihan]; rincian tagihan Terposting: hanya [Bayar], tanpa [Batalkan]. Manajer melihat [Buat Tagihan]" },
  async () => {
    await bukaHutang();
    const buat = await r.tid("create-vendor-bill-button").count();
    await r.tid("vb-search").fill(`Latihan ${NO}`);
    await r.tid(`vb-open-${tb.tagihan_id}`).click();
    await r.tid("vendor-bill-detail-panel").waitFor();
    await r.idle(500);
    const t = { bayar: await r.tid("vb-action-pay").count(), batal: await r.tid("vb-action-cancel-posted").count() };
    await r.shot("f11-finance-tagihan");
    await r.tid("vb-detail-close").click();
    assert(!buat && t.bayar && !t.batal, `Finance: Buat Tagihan=${buat} · ${JSON.stringify(t)}`);
    return `Finance: [Buat Tagihan] ${buat ? "ada" : "tidak ada"} · rincian ${tb.tagihan}: ${JSON.stringify(t)}`;
  });

  await step({ kode: "F11", bagian: "kesalahan_umum.3", peran: "Finance",
    klaim: "Mencari PO di GR/IR tanpa centang 'Tampilkan yang sudah nol' memunculkan 'Tidak ada sisa GR/IR yang cocok' — tanda sudah beres",
    harap: `GR/IR cari ${tb.po}: tanpa centang → 'Tidak ada sisa GR/IR yang cocok dengan saringan.'; dicentang → baris PO dengan Sisa GR/IR Rp 0` },
  async () => {
    await r.tid("hub-tab-gr-ir").click();
    await r.tid("grir-view").waitFor();
    await r.page.waitForFunction(() => !document.querySelector('[data-testid="grir-loading"]'), null, { timeout: 30000 }).catch(() => {});
    if (await r.tid("grir-show-zero").isChecked()) await r.tid("grir-show-zero").uncheck();
    await r.tid("grir-search").locator("input").first().fill(tb.po).catch(async () => r.tid("grir-search").fill(tb.po));
    await r.tid("grir-empty").waitFor({ timeout: 30000 });
    const kosong = await k9.teks(r, "grir-empty");
    await r.shot("f11-grir-tanpa-nol");
    await r.tid("grir-show-zero").check();
    const poDoc = mongo(`return db.purchase_orders.findOne({po_number:"${tb.po}"},{_id:0,id:1})`);
    await r.tid(`grir-row-${poDoc.id}`).waitFor({ timeout: 15000 });
    const sisa = await k9.teks(r, `grir-balance-${poDoc.id}`);
    assert(/Tidak ada sisa GR\/IR yang cocok/.test(kosong) && num(sisa) === 0, `kosong '${kosong}' · sisa '${sisa}'`);
    await r.tid("grir-show-zero").uncheck();
    return `tanpa centang: '${kosong}' · dicentang: ${tb.po} sisa ${sisa}`;
  });

  // ── A2: 3-way match di tagihan pemasok (Manajer membuat tagihan) ──────────────────────────────────────────────────
  await r.login("manager");
  const bukaBuat = async (inv, qty, harga) => {
    await bukaHutang();
    await r.tid("create-vendor-bill-button").click();
    await r.tid("vendor-bill-create-modal").waitFor();
    await pilih(r, "vb-po-select", po.po);
    await r.tid("vb-item-billed-0").waitFor({ timeout: 15000 });
    await r.tid("vb-invoice-input").fill(inv);
    await r.tid("vb-item-billed-0").fill(String(qty));
    const box = r.tid("vb-item-price-0");
    await box.click(); await box.press("Control+A"); await box.press("Delete");
    await r.page.keyboard.type(String(harga), { delay: 10 });
    await sleep(800);
    return { pill: await k9.teks(r, "vb-overall-match"), tombol: await k9.teks(r, "vb-submit-now"),
      mati: await r.tid("vb-submit-now").isDisabled(), toleransi: await k9.teks(r, "vb-tolerance-note") };
  };
  await step({ kode: "A2", bagian: "titik_kontrol.4", peran: "Manajer",
    klaim: "Nomor faktur pemasok tidak boleh dipakai dua kali untuk pemasok yang sama (cegah tagihan ganda)",
    harap: `Tagihan baru ${po.po} dengan No. faktur ${vbTb.supplier_invoice_no} (sudah dipakai ${tb.tagihan}) → ditolak 'No. invoice supplier … sudah dipakai pada ${tb.tagihan}'; tidak ada tagihan baru` },
  async () => {
    const f = await bukaBuat(vbTb.supplier_invoice_no, po.qty, 14000);
    await r.tid("vb-submit-now").click();
    const err = await tungguTeks(r, "vendor-bill-create-modal-error", /sudah dipakai/, 15000);
    await r.shot("a2-faktur-kembar");
    assert(err.includes(vbTb.supplier_invoice_no) && err.includes(tb.tagihan) && !tagihanPo(po.po_id).length, `pesan: ${err}`);
    await r.tid("vb-create-close").click();
    return `${f.pill} · ${err}`;
  });

  await step({ kode: "A2", bagian: "titik_kontrol.3", peran: "Manajer",
    klaim: "3-way match: jumlah tagih tidak boleh melebihi jumlah diterima (lebih tagih ditolak)",
    harap: `Tagih ${po.qty + 4} yard padahal diterima ${po.qty} (lebih 4 yard = Rp 56.000, di atas ambang Rp 50.000) → label 'Lebih tagih (tidak bisa dikirim)'; tombol kirim mati 'Perbaiki Kelebihan Tagih Dulu'` },
  async () => {
    const f = await bukaBuat(`INV-V9-${NO}-${SFX}-LEBIH`, po.qty + 4, 14000);
    await r.shot("a2-lebih-tagih");
    assert(/Lebih tagih/i.test(f.pill) && f.mati && /Perbaiki Kelebihan Tagih/.test(f.tombol), JSON.stringify(f));
    await r.tid("vb-create-close").click();
    assert(!tagihanPo(po.po_id).length, "tagihan lebih tagih tersimpan");
    return `${f.pill} · tombol [${f.tombol}] mati · ${f.toleransi}`;
  });

  let vbC = null; let vbD = null;
  await step({ kode: "A2", bagian: "konsep.2", peran: "Manajer",
    klaim: "Cocok bersih → tagihan langsung terposting; selisih DALAM toleransi (±5% harga, atau nilainya ≤ ambang Rp 50.000) dianggap cocok, bukan 'perlu persetujuan'",
    harap: "Tagih 1 yard Rp 14.420 (+3% dari harga PO Rp 14.000) → label 'Cocok bersih' → [Kirim & Posting] → tagihan langsung Terposting tanpa persetujuan" },
  async () => {
    const f = await bukaBuat(`INV-V9-${NO}-${SFX}-A`, 1, 14420);
    assert(/Cocok bersih/i.test(f.pill) && /Kirim & Posting/.test(f.tombol), JSON.stringify(f));
    await r.shot("a2-harga-dalam-toleransi");
    await r.tid("vb-submit-now").click();
    await r.tid("vendor-bill-create-modal").waitFor({ state: "detached", timeout: 20000 });
    [vbC] = tagihanPo(po.po_id);
    assert(vbC && vbC.status === "posted" && vbC.match_status === "matched", `tagihan ${vbC && vbC.status} ${vbC && vbC.match_status}`);
    return `${f.pill} (${f.toleransi}) → ${vbC.bill_number} ${vbC.status} · match ${vbC.match_status}`;
  });

  await step({ kode: "A2", bagian: "titik_kontrol.3", peran: "Manajer",
    klaim: "Selisih harga di atas toleransi butuh persetujuan",
    harap: "Tagih 1 yard Rp 70.000 (harga PO Rp 14.000; selisih Rp 56.000 melewati ±5% DAN ambang Rp 50.000) → label 'Ada selisih (perlu persetujuan)' → [Kirim (minta persetujuan)] → status Menunggu persetujuan, belum berjurnal" },
  async () => {
    const f = await bukaBuat(`INV-V9-${NO}-${SFX}-B`, 1, 70000);
    assert(/perlu persetujuan/i.test(f.pill) && /minta persetujuan/.test(f.tombol), JSON.stringify(f));
    await r.shot("a2-harga-di-atas-toleransi");
    await r.tid("vb-submit-now").click();
    await r.tid("vendor-bill-create-modal").waitFor({ state: "detached", timeout: 20000 });
    vbD = tagihanPo(po.po_id).find((b) => b.supplier_invoice_no === `INV-V9-${NO}-${SFX}-B`);
    assert(vbD && vbD.status === "pending_approval" && vbD.match_status === "warning", `tagihan ${vbD && vbD.status}`);
    assert(!jurnalDari([vbD.id]).length, "tagihan menunggu persetujuan sudah berjurnal");
    return `${f.pill} → ${vbD.bill_number} ${vbD.status} · ${(vbD.match_exceptions || []).map((x) => x.detail).join("; ")}`;
  });

  await step({ kode: "F11", bagian: "kesalahan_umum.0", peran: "Finance",
    klaim: "Tagihan berselisih jangan dibayar sebelum diputus — siapa yang memutus?",
    harap: "Finance membuka tagihan 'Menunggu persetujuan': tidak ada tombol [Bayar]; tombol putus mengikuti Aturan Persetujuan (dicatat apa adanya)" },
  async () => {
    await r.login(akunPeserta(NO));
    await bukaHutang();
    await r.tid("vb-search").fill(vbD.bill_number);
    await r.page.getByText("Memuat tagihan supplier").waitFor({ state: "detached", timeout: 45000 }).catch(() => {});
    await r.tid(`vb-open-${vbD.id}`).click({ timeout: 45000 });
    await r.tid("vendor-bill-detail-panel").waitFor();
    await r.idle(600);
    const t = { bayar: await r.tid("vb-action-pay").count(), setujui: await r.tid("vb-action-approve").count(),
      tolak: await r.tid("vb-action-reject").count(), petunjuk: await k9.teks(r, "vb-decide-hint") };
    await r.shot("f11-finance-tagihan-berselisih");
    await r.tid("vb-detail-close").click();
    assert(!t.bayar, `Finance bisa membayar tagihan berselisih ${JSON.stringify(t)}`);
    return `Finance pada ${vbD.bill_number}: ${JSON.stringify(t)}`;
  });

  await step({ kode: "A2", bagian: "titik_kontrol.3", peran: "Manajer → Admin",
    klaim: "Tagihan berselisih harga diputus orang kedua: pembuat tagihan (Manajer) tidak memutus sendiri; Admin menolak, tidak dijurnal",
    harap: "Manajer (pembuat) membuka tagihan: tanpa [Setujui]/[Tolak], tertulis 'Tagihan Anda — disetujui orang lain (kontrol dua orang)'; Admin [Tolak] + alasan → status Ditolak; tidak ada jurnal" },
  async () => {
    await r.login("manager");
    await bukaHutang();
    await r.tid("vb-search").fill(vbD.bill_number);
    await r.page.getByText("Memuat tagihan supplier").waitFor({ state: "detached", timeout: 45000 }).catch(() => {});
    await r.tid(`vb-open-${vbD.id}`).click({ timeout: 45000 });
    await r.tid("vendor-bill-detail-panel").waitFor();
    await r.idle(600);
    const mgr = { setujui: await r.tid("vb-action-approve").count(), tolak: await r.tid("vb-action-reject").count(),
      catatan: await k9.teks(r, "vb-decide-hint") };
    await r.shot("a2-pembuat-tidak-memutus");
    await r.tid("vb-detail-close").click().catch(() => {});
    assert(!mgr.setujui && !mgr.tolak && /orang lain/.test(mgr.catatan), `Manajer (pembuat): ${JSON.stringify(mgr)}`);
    await r.login("admin");
    await bukaHutang();
    await r.tid("vb-search").fill(vbD.bill_number);
    await r.page.getByText("Memuat tagihan supplier").waitFor({ state: "detached", timeout: 45000 }).catch(() => {});
    await r.tid(`vb-open-${vbD.id}`).click({ timeout: 45000 });
    await r.tid("vendor-bill-detail-panel").waitFor();
    await r.tid("vb-action-reject").click();
    await r.tid("vb-reject-confirm-reason").waitFor({ timeout: 10000 });
    await r.tid("vb-reject-confirm-reason").fill("Harga faktur tidak sesuai PO — minta faktur ulang dari pemasok");
    await r.shot("a2-admin-tolak-tagihan-berselisih");
    await r.tid("vb-reject-confirm-confirm").click();
    await r.page.waitForFunction(() => !document.querySelector('[data-testid="vb-action-reject"]'), null, { timeout: 20000 });
    const b = mongo(`return db.vendor_bills.findOne({id:"${vbD.id}"},{_id:0,status:1})`);
    // Tagihan yang ditolak berstatus 'cancelled' (Dibatalkan) — tidak dijurnal.
    assert(/reject|cancel/.test(b.status) && !jurnalDari([vbD.id]).length, `status ${b.status}`);
    await r.tid("vb-detail-close").click().catch(() => {});
    await r.login("manager");
    return `Manajer (pembuat): ${JSON.stringify(mgr)} · Admin menolak → ${vbD.bill_number} ${b.status} · jurnal 0`;
  });

  // Penutup (bukan klaim): tagih 1 yard sisa dengan harga PO supaya PO tertagih penuh — hanya bila langkah sebelumnya jalan.
  assert(vbC && vbD, "langkah tagihan sebelumnya gagal — penutup tidak dijalankan");
  await bukaBuat(`INV-V9-${NO}-${SFX}-C`, 1, 14000);
  await r.tid("vb-submit-now").click();
  await r.tid("vendor-bill-create-modal").waitFor({ state: "detached", timeout: 20000 });
  r.note(`Penutup: tagihan INV-V9-${NO}-${SFX}-C 1 yard Rp 14.000 → ${(tagihanPo(po.po_id).find((b) => b.supplier_invoice_no === `INV-V9-${NO}-${SFX}-C`) || {}).status}`);

  await step({ kode: "K02", bagian: "kesalahan_umum.2", peran: "Finance",
    klaim: "Selama 'Selisih harga pembelian' belum dipilih, selisih harga tagihan tertinggal di GR/IR dan kliring tidak tersedia",
    harap: `GR/IR ${po.po}: sisa = diterima Rp 28.000 − ditagih Rp 28.420 = −Rp 420 'termasuk selisih harga'; pita 'Akun "Selisih harga pembelian" belum diatur…'; tanpa tombol [Kliring]` },
  async () => {
    await r.login(akunPeserta(NO));
    await bukaHutang();
    await r.tid("hub-tab-gr-ir").click();
    await r.tid("grir-view").waitFor();
    await r.tid("grir-search").locator("input").first().fill(po.po).catch(async () => r.tid("grir-search").fill(po.po));
    await r.tid("grir-show-zero").check();
    await r.page.getByText("Memuat GR/IR").waitFor({ state: "detached", timeout: 20000 }).catch(() => {});
    await r.tid(`grir-row-${po.po_id}`).waitFor({ timeout: 15000 });
    const sisa = await tungguTeks(r, `grir-balance-${po.po_id}`, /Rp/, 15000).catch(() => "");
    const varian = await k9.teks(r, `grir-variance-${po.po_id}`);
    const pita = await k9.teks(r, "grir-mapping-missing");
    const kliring = await r.tid(`grir-clear-${po.po_id}`).count();
    await r.shot("k02-grir-selisih-harga");
    assert(Math.abs(Math.abs(num(sisa.split(/\s+termasuk/)[0])) - 420) < 1 && /Selisih harga pembelian/.test(pita) && !kliring,
      `sisa '${sisa}' · '${varian}' · pita '${pita}' · kliring ${kliring}`);
    return `sisa ${sisa} · ${varian} · pita: ${pita.slice(0, 120)} · tombol Kliring: tidak ada`;
  });

}

// ── Blok KONTRABON (F12) ─────────────────────────────────────────────────────────────────────────────────────────────
async function blokKontrabon(r, d, NO) {
  const step = (meta, fn) => k9.klaim(r, d, meta, fn);
  const K = kartu(NO);
  const tb = K["a_dasar:tagihan_bayar"]; const tk = K["a_dasar:tagihan_kontrabon"]; const po = K["v9:po_terima"];
  const soFaktur = K["a_dasar:so_lunas"];
  const bukaHutang = async () => {
    await r.tid("nav-accounts-payable").click().catch(async () => {
      await r.tid("nav-group-toggle-keuangan").click(); await r.tid("nav-accounts-payable").click();
    });
    await r.tid("vendor-bills-view").waitFor();
    await r.idle(500);
  };
  const tagihanPo = (poId) => mongo(`return db.vendor_bills.find({po_id:"${poId}",status:{$ne:"cancelled"}},{_id:0}).sort({created_at:1}).toArray()`);
  assert(tk && !mongo(`return db.contra_bons.countDocuments({"bills.bill_id":"${tk.tagihan_id}",status:{$ne:"cancelled"}})`),
    `Kartu peserta ${NO}: tagihan kontrabon tidak ada / sudah dikontrabon`);
  // ── F12: kontrabon Disetujui belum bisa dibayar; satu faktur satu kontrabon ───────────────────────────────────────
  let cb = null;
  const bill0 = mongo(`return db.vendor_bills.findOne({id:"${tk.tagihan_id}"},{_id:0,supplier_name:1,grand_total:1,status:1})`);
  const bukaCb = async () => {
    await r.go("contra-bons", KSC);
    await r.tid("contra-bons-view").waitFor();
    await r.tid("cb-filter-q").fill(cb.number);
    await r.tid(`cb-row-${cb.id}`).waitFor({ timeout: 15000 });
    await r.tid(`cb-row-${cb.id}`).click();
    await r.tid("cb-detail-panel").waitFor();
    await r.idle(600);
  };
  const wizard = async () => {
    await r.go("contra-bons", KSC);
    await r.tid("contra-bons-view").waitFor();
    await r.tid("cb-new").click();
    await r.tid("cb-create-wizard").waitFor();
    await pilih(r, "cb-create-supplier", bill0.supplier_name);
    await r.tid("cb-create-prep-summary").waitFor();
    await r.idle(500);
    return k9.teks(r, "cb-create-prep-summary");
  };
  await r.login("manager");
  // Persiapan (langkah F12 yang sudah diuji): Manajer membuat & memverifikasi, Admin menyetujui.
  await wizard();
  await r.tid("cb-create-next").click();
  await r.tid(`cb-create-pick-${tk.tagihan_id}`).waitFor();
  for (const t of await r.page.$$eval('[data-testid^="cb-create-pick-"]', (els) => els.map((e) => e.getAttribute("data-testid")))) {
    const mau = t === `cb-create-pick-${tk.tagihan_id}`;
    if ((await r.tid(t).isChecked()) !== mau) await r.tid(t).click();
  }
  await r.tid("cb-create-next").click();
  await r.tid("cb-create-review").waitFor();
  await r.tid("cb-create-submit-now").check();
  await r.tid("cb-create-submit").click();
  await r.tid("cb-create-wizard").waitFor({ state: "detached", timeout: 20000 });
  cb = mongo(`return db.contra_bons.find({"bills.bill_id":"${tk.tagihan_id}",status:{$ne:"cancelled"}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
  assert(cb, "kontrabon tidak terbit");
  await tungguTeks(r, "cb-action-primary", /Verifikasi/);
  await r.tid("cb-action-primary").click();
  await tungguTeks(r, "cb-detail-status", /Terverifikasi/);
  r.note(`Persiapan: ${cb.number} (${tk.tagihan}) dibuat & diverifikasi Manajer`);

  await step({ kode: "F12", bagian: "catatan_pelatih", peran: "Manajer",
    klaim: "Satu faktur hanya boleh ada di satu kontrabon",
    harap: `Kontrabon baru untuk pemasok yang sama: ${tk.tagihan} (sudah di ${cb.number}) tidak ditawarkan lagi` },
  async () => {
    const ring = await wizard();
    await r.tid("cb-create-next").click().catch(() => {});
    await r.idle(800);
    const pick = await r.tid(`cb-create-pick-${tk.tagihan_id}`).count();
    await r.shot("f12-faktur-tidak-ditawarkan");
    await r.page.keyboard.press("Escape");
    assert(!pick, `${tk.tagihan} masih ditawarkan`);
    return `ringkasan pemasok: ${ring.slice(0, 120)} · ${tk.tagihan} ditawarkan: tidak`;
  });

  await r.login("admin");
  await bukaCb();
  await r.tid("cb-action-primary").click();
  await tungguTeks(r, "cb-detail-status", /Disetujui/);
  r.note(`Persiapan: ${cb.number} disetujui Admin (orang kedua)`);

  await step({ kode: "F12", bagian: "kesalahan_umum.2", peran: "Finance",
    klaim: "Finance tidak menemukan tombol bayar pada kontrabon 'Disetujui'; kontrabon harus 'Dijadwalkan bayar' dulu",
    harap: `Finance membuka ${cb.number} (Disetujui): tidak ada [Catat pembayaran]; tertulis langkah berikutnya 'Jadwalkan pembayaran'` },
  async () => {
    await r.login(akunPeserta(NO));
    await bukaCb();
    const st = await k9.teks(r, "cb-detail-status");
    const utama = (await r.tid("cb-action-primary").count()) ? await k9.teks(r, "cb-action-primary") : "";
    const panel = await k9.teks(r, "cb-detail-panel");
    await r.shot("f12-finance-disetujui");
    assert(/Disetujui/.test(st) && !/Catat pembayaran/.test(utama) && /Jadwalkan pembayaran/.test(panel), `status ${st} · tombol '${utama}'`);
    return `status ${st} · tombol utama '${utama || "—"}' · ${(panel.match(/Langkah berikutnya[^.]*/) || [""])[0].slice(0, 140)}`;
  });

  await r.login("manager");
  await bukaCb();
  await r.tid("cb-action-primary").click();
  await r.tid("cb-schedule-modal").waitFor();
  await pilih(r, "cb-schedule-account", REK_BCA);
  await r.tid("cb-schedule-save").click();
  await r.tid("cb-schedule-modal").waitFor({ state: "detached", timeout: 15000 });
  await tungguTeks(r, "cb-detail-status", /Dijadwalkan/);
  r.note(`Penutup: ${cb.number} dijadwalkan Manajer`);

  await step({ kode: "F12", bagian: "kesalahan_umum.2", peran: "Finance",
    klaim: "Sesudah 'Dijadwalkan bayar', Finance mencatat pembayaran kontrabon",
    harap: `Finance: tombol [Catat pembayaran] tampil → bayar dari BCA → status Sudah dibayar; jurnal Hutang Usaha (D) / Bank (K) ${rp(bill0.grand_total)}` },
  async () => {
    await r.login(akunPeserta(NO));
    await bukaCb();
    const b = r.tid("cb-action-primary");
    assert(/Catat pembayaran/.test(await b.innerText()), `tombol utama: ${await b.innerText()}`);
    await b.click();
    await r.tid("pay-supplier-modal").waitFor();
    await r.tid("pay-supplier-number").waitFor();
    const rek = await k9.teks(r, "pay-supplier-account");
    if (!rek.includes(REK_BCA)) await pilih(r, "pay-supplier-account", REK_BCA);
    await r.tid("pay-supplier-submit").click();
    await setuju(r, "pay-supplier-confirm");
    await r.tid("pay-supplier-modal").waitFor({ state: "detached", timeout: 20000 });
    await tungguTeks(r, "cb-detail-status", /Sudah dibayar/);
    const paid = mongo(`return db.contra_bons.findOne({id:"${cb.id}"},{_id:0})`);
    const p = (paid.payments || [])[0] || {};
    const je = jurnalDari([p.cash_txn_id, p.payment_intent_id, p.id, cb.id].filter(Boolean)).find((j) => j.lines.some((l) => l.account_code === "2-1100"));
    k9.cekJurnal(je, [["2-1100", "D", Number(paid.totals.net_payable)]]);
    return `${cb.number} ${paid.status} · ${k9.ringkasJurnal(je)}`;
  });

}

// ── Blok FAKTUR (F13) ────────────────────────────────────────────────────────────────────────────────────────────────
async function blokFaktur(r, d, NO) {
  const step = (meta, fn) => k9.klaim(r, d, meta, fn);
  const K = kartu(NO);
  const tb = K["a_dasar:tagihan_bayar"]; const tk = K["a_dasar:tagihan_kontrabon"]; const po = K["v9:po_terima"];
  const soFaktur = K["a_dasar:so_lunas"];
  const bukaHutang = async () => {
    await r.tid("nav-accounts-payable").click().catch(async () => {
      await r.tid("nav-group-toggle-keuangan").click(); await r.tid("nav-accounts-payable").click();
    });
    await r.tid("vendor-bills-view").waitFor();
    await r.idle(500);
  };
  const tagihanPo = (poId) => mongo(`return db.vendor_bills.find({po_id:"${poId}",status:{$ne:"cancelled"}},{_id:0}).sort({created_at:1}).toArray()`);
  // ── F13: faktur pajak — Finance tidak membatalkan; boleh membuat pengganti ───────────────────────────────────────
  assert(soFaktur && !mongo(`return db.tax_invoices.countDocuments({order_id:"${soFaktur.so_id}",status:{$ne:"batal"}})`),
    `${soFaktur && soFaktur.so} sudah berfaktur — pakai peserta lain`);
  await r.login(akunPeserta(NO));
  let fkt = null;
  await step({ kode: "F13", bagian: "kesalahan_umum.0", peran: "Finance",
    klaim: "Faktur yang sudah terbit hanya bisa dibatalkan Manajer; Finance boleh menerbitkan dan membuat faktur pengganti",
    harap: `Finance [Terbitkan] faktur ${soFaktur.so} di Beranda Keuangan → di Pajak › Faktur Keluaran Finance melihat [Terbitkan Pengganti] tanpa [Batalkan]; Manajer melihat [Batalkan]` },
  async () => {
    await r.go("finance-desk", KSC);
    await r.tid("finance-desk").waitFor();
    await r.tid("fin-desk-search-faktur_pajak").fill(soFaktur.so);
    await r.tid(`fin-desk-faktur_pajak-action-${soFaktur.so_id}`).waitFor({ timeout: 20000 });
    await r.tid(`fin-desk-faktur_pajak-action-${soFaktur.so_id}`).click();
    await r.tid("fkt-modal").waitFor();   // pop-up pratinjau faktur → [Terbitkan]
    await r.tid("fkt-modal-submit").click();
    await tungguToast(r, /diterbitkan/, 20000);   // hasil aksi = toast
    fkt = mongo(`return db.tax_invoices.find({order_id:"${soFaktur.so_id}",status:{$ne:"batal"}},{_id:0,id:1,number:1,status:1}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
    assert(fkt, "faktur tidak terbit");
    await r.go("tax-invoices", KSC);
    await r.tid("tax-invoices-view").waitFor();
    await r.tid("fkt-search").fill(soFaktur.so);
    await r.tid(`fkt-row-${fkt.id}`).waitFor({ timeout: 15000 });
    const fin = { pengganti: await r.tid(`fkt-replace-${fkt.id}`).count(), batal: await r.tid(`fkt-cancel-${fkt.id}`).count() };
    await r.shot("f13-finance-faktur");
    await r.login("manager");
    await r.go("tax-invoices", KSC);
    await r.tid("tax-invoices-view").waitFor();
    await r.tid("fkt-search").fill(soFaktur.so);
    await r.tid(`fkt-row-${fkt.id}`).waitFor({ timeout: 15000 });
    const mgr = { batal: await r.tid(`fkt-cancel-${fkt.id}`).count() };
    assert(fin.pengganti && !fin.batal && mgr.batal, `Finance ${JSON.stringify(fin)} · Manajer ${JSON.stringify(mgr)}`);
    return `${fkt.number} · Finance ${JSON.stringify(fin)} · Manajer ${JSON.stringify(mgr)}`;
  });
}

// ── Blok GRIR (K02): baca ulang GR/IR PO `v9:po_terima` sesudah blok tagihan (hanya membaca) ─────────────────────────
async function blokGrir(r, d, NO) {
  const step = (meta, fn) => k9.klaim(r, d, meta, fn);
  const po = kartu(NO)["v9:po_terima"];
  const bukaHutang = async () => {
    await r.tid("nav-accounts-payable").click().catch(async () => {
      await r.tid("nav-group-toggle-keuangan").click(); await r.tid("nav-accounts-payable").click();
    });
    await r.tid("vendor-bills-view").waitFor();
    await r.idle(500);
  };
  assert(po, `peserta ${NO} tanpa v9:po_terima`);
  await r.login(akunPeserta(NO));
  await step({ kode: "K02", bagian: "kesalahan_umum.2", peran: "Finance",
    klaim: "Selama 'Selisih harga pembelian' belum dipilih, selisih harga tagihan tertinggal di GR/IR dan kliring tidak tersedia",
    harap: `GR/IR ${po.po}: sisa = diterima Rp 28.000 − ditagih Rp 28.420 = −Rp 420 'termasuk selisih harga'; pita 'Akun "Selisih harga pembelian" belum diatur…'; tanpa tombol [Kliring]` },
  async () => {
    await r.login(akunPeserta(NO));
    await bukaHutang();
    await r.tid("hub-tab-gr-ir").click();
    await r.tid("grir-view").waitFor();
    await r.tid("grir-search").locator("input").first().fill(po.po).catch(async () => r.tid("grir-search").fill(po.po));
    await r.tid("grir-show-zero").check();
    await r.page.getByText("Memuat GR/IR").waitFor({ state: "detached", timeout: 20000 }).catch(() => {});
    await r.tid(`grir-row-${po.po_id}`).waitFor({ timeout: 15000 });
    const sisa = await tungguTeks(r, `grir-balance-${po.po_id}`, /Rp/, 15000).catch(() => "");
    const varian = await k9.teks(r, `grir-variance-${po.po_id}`);
    const pita = await k9.teks(r, "grir-mapping-missing");
    const kliring = await r.tid(`grir-clear-${po.po_id}`).count();
    await r.shot("k02-grir-selisih-harga");
    assert(Math.abs(Math.abs(num(sisa.split(/\s+termasuk/)[0])) - 420) < 1 && /Selisih harga pembelian/.test(pita) && !kliring,
      `sisa '${sisa}' · '${varian}' · pita '${pita}' · kliring ${kliring}`);
    return `sisa ${sisa} · ${varian} · pita: ${pita.slice(0, 120)} · tombol Kliring: tidak ada`;
  });
}

const BLOK = (process.env.KN_BLOK || "tagihan:89,kontrabon:90,faktur:90")
  .split(",").map((x) => x.trim()).filter(Boolean).map((x) => { const [b, n] = x.split(":"); return [b, String(n).padStart(2, "0")]; });
const JALAN = { tagihan: blokTagihan, kontrabon: blokKontrabon, faktur: blokFaktur, grir: blokGrir };
const JUDUL = { tagihan: "tagihan pemasok & 3-way match (F11, A2, K02)", kontrabon: "kontrabon (F12)", faktur: "faktur pajak (F13)", grir: "GR/IR selisih harga (K02)" };

(async () => {
  let semua = true;
  for (const [blok, no] of BLOK) {
    const fn = JALAN[blok];
    if (!fn) { console.log(`blok tidak dikenal: ${blok}`); semua = false; continue; }
    k9.bersihkan(`hutang-${blok}`);
    const d = k9.daftar(`hutang-${blok}`);
    const r = await new Run(d.kode, `V9 · Bukti klaim materi Hutang & Pajak — ${JUDUL[blok]} · peserta ${no}`).start();
    try { await fn(r, d, no); } catch (e) { r.note("berhenti: " + e.message); }
    d.simpan();
    semua = (await r.finish()) && semua;
  }
  process.exitCode = semua ? 0 : 1;
})();
