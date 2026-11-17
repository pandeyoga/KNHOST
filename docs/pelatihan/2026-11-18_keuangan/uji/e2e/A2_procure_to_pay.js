// A2 — PENGADAAN SAMPAI BAYAR (procure to pay), PT Sukacita — alur ujung ke ujung LEWAT LAYAR, tiap peran dengan akunnya.
//
//   Gudang (warehouse@) PR  →  Manajer setujui PR  →  Manajer konversi PR → PO  →  Admin setujui PO (≥ Rp 100 juta,
//   pembuat ≠ penyetuju)  →  Gudang terima barang (Barang Masuk, 75 roll)  →  Kepala Gudang tugaskan SPK kedatangan  →
//   MD Quality periksa & terima  →  Manajer catat tagihan pemasok (3-way match, PPN masukan)  →  Finance periksa tagihan
//   →  Manajer kontrabon (+ Admin setujui, Manajer jadwalkan)  →  Finance bayar  →  Finance rekonsiliasi mutasi bank  →
//   Finance baca GR/IR & Jejak Dokumen.  Di tiap tahap: layar dicocokkan + buku (jurnal seimbang, nominal).
//
//   node docs/pelatihan/2026-11-18_keuangan/uji/e2e/A2_procure_to_pay.js           (bawaan peserta 31)
//   KN_PESERTA=33 node …/A2_procure_to_pay.js
//   KN_MULAI=8 node …  → lanjut dari langkah 8 memakai keadaan tersimpan (hasil/A2/keadaan.json) — hanya untuk perbaikan
//                        skrip; uji resmi selalu dari langkah 1 dengan peserta baru.
//   KN_SAMPAI=21 node …  → persiapan kelas: rantai dibangun lewat layar sampai kontrabon dijadwalkan; peserta lalu
//                        mengerjakan sendiri langkah Finance (bayar, rekonsiliasi, GR/IR, Jejak Dokumen).
// Butuh: akun & pemasok peserta (`seed_pelatihan_keuangan_kn.py --mulai NN --peserta NN --hanya a_dasar:akun` lalu
// `--hanya a_dasar:mitra`). Satu peserta = satu PR baru (aman dijalankan ulang dengan peserta lain).
const fs = require("fs");
const path = require("path");
const { Run, assert, rp, num, sleep, peserta, akunPeserta, mongo, api } = require("../lib");
const { pilih, setuju, jurnalDari, cekJurnal, tungguTeks, sorot, lepas, klikPotret } = require("../hutang_lib");
const kb = require("../kasbank_lib");

const KSC = "ent_ksc";
const REK_BCA = "BCA Operasional KSC";
const SKU = "DMO-GRY-WVN-001";          // Grey Woven Katun Poplin (yard)
const QTY = 7500;                       // yard
const ROLL = 75;                        // rencana roll (100 yard/roll)
const HARGA = 14000;                    // Rp/yard (penawaran pemasok)
const DPP = QTY * HARGA;                // Rp 105.000.000 → PR ≥ Rp 50 juta & PO ≥ Rp 100 juta perlu persetujuan
const PPN = Math.round(DPP * 11 / 12 * 0.12);   // PPN 12% × DPP nilai lain 11/12 = Rp 11.550.000
const TOTAL = DPP + PPN;

const NO = peserta("31");
const MULAI = Number(process.env.KN_MULAI || 1);
const PEMASOK = `Latihan ${NO} · Pemasok Grey Peserta ${NO}`;
const ALASAN = `Stok grey poplin untuk celup — Latihan ${NO}`;
const FAKTUR = `INV-A2-${NO}-${Date.now().toString(36).toUpperCase().slice(-5)}`;

const r0 = new Run("A2", "Pengadaan sampai bayar (procure to pay) — PT Sukacita");
const FKEADAAN = path.join(r0.dir, "keadaan.json");
let K = {};   // keadaan dokumen: pr, po, task, spk, bill, cb, …
if (MULAI > 1) K = JSON.parse(fs.readFileSync(FKEADAAN, "utf8"));
const simpan = () => fs.writeFileSync(FKEADAAN, JSON.stringify(K, null, 2));

/** Buka menu samping (grup dibuka dulu bila tertutup), lalu tab hub bila disebut. */
async function buka(r, navId, tab, group) {
  const item = r.tid(`nav-${navId}`);
  if (!(await item.isVisible().catch(() => false)) && group) {
    await r.tid(`nav-group-toggle-${group}`).click();
    await item.waitFor({ timeout: 8000 });
  }
  await item.click();
  await r.idle(600);
  if (tab) {
    const t = r.tid(`hub-tab-${tab}`);
    if (await t.isVisible().catch(() => false)) { await t.click(); await r.idle(600); }
  }
}

/** KNSelect yang bisa dicari: klik, ketik, pilih opsi yang memuat teks. */
async function pilihCari(r, testId, ketik, re) {
  for (let i = 0; ; i++) {   // daftar opsi bisa belum termuat saat pop-up baru terbuka → coba ulang
    await r.tid(testId).first().click();
    await sleep(300);
    if (ketik) { await r.page.keyboard.type(ketik, { delay: 20 }); await sleep(500); }
    const opt = r.page.getByRole("option").filter({ hasText: re || ketik }).first();
    try {
      await opt.waitFor({ timeout: 5000 });
      await opt.click();
      await sleep(300);
      return;
    } catch (e) {
      if (await r.page.locator('[role="listbox"],[cmdk-list]').first().isVisible().catch(() => false)) await r.page.keyboard.press("Escape");
      if (i >= 2) throw new Error(`opsi "${re || ketik}" tidak ada di ${testId}`);
      await sleep(1500);
    }
  }
}

const db1 = (coll, q, proj = "{_id:0}") => mongo(`return db.${coll}.findOne(${q},${proj})`);
const SAMPAI = Number(process.env.KN_SAMPAI || 99);   // persiapan kelas: KN_SAMPAI=21 = berhenti sesudah kontrabon dijadwalkan
const langkah = (no) => no >= MULAI && no <= SAMPAI;

(async () => {
  const r = await r0.start();
  // Penolakan izin (403) yang dipanggil layar saat peran bekerja — dicatat (bukan gagal) untuk audit layar.
  const tolak = new Set();
  r.page.on("response", (res) => {
    if (res.status() === 403 && res.url().includes("/api/")) {
      const k = `${r.who.split("@")[0]} ${res.request().method()} ${res.url().replace(/^.*\/api/, "/api").split("?")[0]}`;
      if (!tolak.has(k)) { tolak.add(k); r.note(`403: ${k}`); }
    }
  });
  const sup = db1("suppliers", `{name:${JSON.stringify(PEMASOK)}}`);
  const prod = db1("products", `{sku:"${SKU}"}`, "{_id:0,id:1,name:1}");
  if (!sup || !prod) { r.note(`Pemasok ${PEMASOK} / produk ${SKU} belum ada — jalankan seed peserta ${NO} (a_dasar:akun, a_dasar:mitra)`); await r.finish(); return; }
  r.note(`Peserta ${NO} · ${PEMASOK} · ${prod.name} ${QTY} yard × ${rp(HARGA)} = DPP ${rp(DPP)} · PPN ${rp(PPN)} · total ${rp(TOTAL)}`);

  // ── 1. Gudang membuat PR ────────────────────────────────────────────────────────────────────────────────────────
  if (langkah(1)) await r.step(1, "Gudang", "Login warehouse@ → Pembelian › Pengadaan › tab Permintaan Pembelian → [[PR Baru]]",
    "Pop-up \"Buat Permintaan Pembelian\": pilih artikel → warna → [[Tambah]], lalu lokasi kirim, supplier preferensi, alasan", async () => {
      await r.login("warehouse");
      await buka(r, "sourcing", "purchase-requisitions", "pembelian");
      await r.tid("purchase-requisitions-view").waitFor();
      await klikPotret(r, r.tid("pr-create-btn"), "gudang-pr-baru");
      await r.tid("pr-create-modal").waitFor();
      await sleep(600);
      await pilihCari(r, "pr-article-select", "Grey Woven Katun Poplin", SKU);
      await pilihCari(r, "pr-product-select", "", SKU);
      await sorot(r.tid("pr-product-select"));
      await klikPotret(r, r.tid("pr-add-line"), "gudang-pilih-barang");
      await lepas(r.tid("pr-product-select"));
      await r.tid("pr-line-0").waitFor();
      return await r.text("pr-line-0");
    });

  if (langkah(1)) await r.step(2, "Gudang", `Isi baris: *Qty* ${QTY} · *Roll* ${ROLL} · *Est. Harga* ${rp(HARGA)}; *Lokasi kirim* Jakarta; *Supplier Preferensi* (Tampilkan semua supplier) ${PEMASOK}; *Alasan*; biarkan centang *Langsung ajukan persetujuan* → [[Simpan PR]]`,
    `Total Estimasi ${rp(DPP)}; sesudah simpan: pesan "PR-… dibuat.", baris PR berstatus Menunggu Persetujuan (≥ Rp 50 juta → perlu Manajer)`, async () => {
      await r.tid("pr-qty-0").fill(String(QTY));
      await r.tid("pr-rolls-0").fill(String(ROLL));
      const harga = r.tid("pr-price-0");
      await harga.click(); await harga.fill(String(HARGA));
      await r.page.keyboard.press("Tab");
      await pilihCari(r, "pr-site", "", "Jakarta");
      await r.tid("pr-supplier-show-all").first().click();
      await pilihCari(r, "pr-supplier", `Latihan ${NO}`, PEMASOK);
      await r.tid("pr-reason").fill(ALASAN);
      assert(await r.tid("pr-submit-now").isChecked(), "centang Langsung ajukan tidak aktif");
      const tot = await r.text("pr-form-total");
      assert(num(tot) === DPP, `Total Estimasi ${tot} ≠ ${rp(DPP)}`);
      await sorot(r.tid("pr-form-total"));
      await klikPotret(r, r.tid("pr-submit"), "gudang-isi-pr");
      await lepas(r.tid("pr-form-total"));
      await r.tid("pr-create-modal").waitFor({ state: "detached", timeout: 15000 });
      const toast = await tungguTeks(r, "pr-toast", /dibuat/);
      const pr = mongo(`return db.purchase_requisitions.find({preferred_supplier_id:"${sup.id}",reason:${JSON.stringify(ALASAN)}},{_id:0})
        .sort({created_at:-1}).limit(1).toArray()[0]||null`);
      assert(pr, "PR tidak tersimpan");
      assert(pr.status === "pending_approval" && pr.approval_required, `status PR ${pr.status}, perlu persetujuan ${pr.approval_required}`);
      assert(Math.abs(pr.total_est_amount - DPP) < 0.01, `total PR ${pr.total_est_amount}`);
      K.pr = { id: pr.id, number: pr.number }; simpan();
      await r.tid(`pr-row-${pr.id}`).waitFor();
      await sorot(r.tid(`pr-row-${pr.id}`));
      await r.shot("gudang-pr-menunggu");
      await lepas(r.tid(`pr-row-${pr.id}`));
      return `${toast} · ${pr.number} ${pr.status} · ${pr.warehouse_name} · peran pemutus ${pr.required_approval_role}`;
    });

  // ── 2. Manajer menyetujui PR ─────────────────────────────────────────────────────────────────────────────────────
  if (langkah(3)) await r.step(3, "Manajer", "Login manager@ → Pembelian › Pengadaan › Permintaan Pembelian → baris PR → [[Detail →]] → [[Setujui]] → [[Setujui PR]]",
    "Rincian PR: Persetujuan \"Perlu Manajer\", Total Estimasi; sesudah setuju status Disetujui dan panel \"Pemenuhan & Realisasi\" muncul", async () => {
      await r.login("manager");
      await buka(r, "sourcing", "purchase-requisitions", "pembelian");
      await r.tid("purchase-requisitions-view").waitFor();
      await r.tid("pr-search").fill(K.pr.number);
      await r.idle(600);
      await klikPotret(r, r.tid(`pr-open-${K.pr.id}`), "manajer-daftar-pr");
      await r.tid("pr-detail").waitFor();
      await r.idle(500);
      const d = (await r.tid("pr-detail").innerText()).replace(/\s+/g, " ");
      assert(/Perlu Manajer/i.test(d), `rincian PR tanpa "Perlu Manajer": ${d.slice(0, 300)}`);
      await klikPotret(r, r.tid("pr-action-approve"), "manajer-setujui-pr");
      const msg = await tungguTeks(r, "confirm-modal", /Setujui/);
      await sorot(r.tid("confirm-modal-confirm"));
      await r.shot("manajer-konfirmasi-pr");
      await setuju(r, "confirm-modal");
      await r.tid("pr-action-convert").waitFor({ timeout: 15000 });
      const pr = db1("purchase_requisitions", `{id:"${K.pr.id}"}`);
      assert(pr.status === "approved" && pr.approved_by, `status ${pr.status}`);
      return `${msg.slice(0, 160)} · disetujui oleh ${pr.approved_by}`;
    });

  // ── 3. Manajer mengubah PR menjadi PO ────────────────────────────────────────────────────────────────────────────
  if (langkah(4)) await r.step(4, "Manajer", "Di rincian PR klik [[Konversi ke PO]] → periksa *Supplier* (terisi dari supplier preferensi) & *Lokasi kirim* Jakarta → [[Buat PO]]",
    `PO KSC/PO-… lahir dari PR (PR berstatus Jadi PO); nilai PO ${rp(DPP)} + PPN ${rp(PPN)} = ${rp(TOTAL)} → Menunggu persetujuan (≥ Rp 100 juta)`, async () => {
      if (!(await r.tid("pr-detail").isVisible().catch(() => false))) {
        await r.login("manager");
        await buka(r, "sourcing", "purchase-requisitions", "pembelian");
        await r.tid(`pr-open-${K.pr.id}`).click();
        await r.tid("pr-detail").waitFor();
      }
      await r.tid("pr-action-convert").click();
      await r.tid("pr-convert-modal").waitFor();
      await sleep(500);
      const supT = await r.text("pr-convert-supplier");
      if (!supT.includes(PEMASOK)) await pilihCari(r, "pr-convert-supplier", `Latihan ${NO}`, PEMASOK);
      await klikPotret(r, r.tid("pr-convert-confirm"), "manajer-konversi-po");
      await r.tid("pr-convert-modal").waitFor({ state: "detached", timeout: 20000 });
      await r.idle(800);
      const pr = db1("purchase_requisitions", `{id:"${K.pr.id}"}`);
      assert(pr.po_id, `PR belum tertaut PO (status ${pr.status})`);
      const po = db1("purchase_orders", `{id:"${pr.po_id}"}`);
      K.po = { id: po.id, number: po.po_number }; simpan();
      assert(po.supplier_id === sup.id, "pemasok PO beda");
      assert(Math.abs(po.total_amount - DPP) < 0.01 && Math.abs(po.grand_total - TOTAL) < 0.01, `nilai PO ${po.total_amount} / ${po.grand_total}`);
      await sorot(r.tid("pr-linked-po"));
      await r.shot("pr-jadi-po");
      await lepas(r.tid("pr-linked-po"));
      return `${po.po_number} status ${po.status} · persetujuan ${po.approval_status} (${po.required_approval_role}) · DPP ${rp(po.total_amount)} · PPN ${rp(po.ppn_amount)} · total ${rp(po.grand_total)}`;
    });

  // ── 4. Persetujuan PO: pembuat (Manajer) tidak boleh menyetujui sendiri → Admin ────────────────────────────────────
  const bukaPersetujuan = async () => {
    await buka(r, "approval-inbox", "purchase-approval");
    await r.tid("purchase-approval-view").waitFor();
    await r.idle(800);
    const cari = r.tid("po-approval-search");
    if (await cari.isVisible().catch(() => false)) { await cari.fill(K.po.number); await r.idle(400); }
    await r.tid(`po-approval-row-${K.po.id}`).waitFor({ timeout: 15000 });
  };
  if (langkah(5)) await r.step(5, "Manajer", "Pusat Persetujuan › tab Persetujuan Pembelian → cari nomor PO",
    "Baris PO: Total (termasuk PPN) dan DPP, status Menunggu; kolom Aksi bergembok \"PO Anda — disetujui orang lain\" (pembuat ≠ penyetuju)", async () => {
      if (r.who !== "manager@kainnusantara.id") await r.login("manager");
      await bukaPersetujuan();
      const row = (await r.tid(`po-approval-row-${K.po.id}`).innerText()).replace(/\s+/g, " ");
      assert(row.includes(rp(TOTAL).replace("Rp ", "")), `total PO di baris: ${row}`);
      assert(await r.tid(`po-approve-${K.po.id}`).count() === 0, "Manajer pembuat PO melihat tombol Setujui");
      const kunci = await r.text(`po-approve-locked-${K.po.id}`);
      assert(/PO Anda/.test(kunci), `alasan kunci: "${kunci}"`);
      await sorot(r.tid(`po-approval-row-${K.po.id}`));
      await r.shot("manajer-po-terkunci");
      await lepas(r.tid(`po-approval-row-${K.po.id}`));
      return row.slice(0, 200);
    });

  if (langkah(6)) await r.step(6, "Admin", "Login admin@ → Pusat Persetujuan › Persetujuan Pembelian → baris PO → [[Setujui]]",
    "Pesan \"PO KSC/PO-… disetujui penuh…\"; PO pindah ke tab Disetujui; tugas Barang Masuk untuk Gudang Jakarta terbentuk (rencana 75 roll)", async () => {
      await r.login("admin");
      await bukaPersetujuan();
      await klikPotret(r, r.tid(`po-approve-${K.po.id}`), "admin-setujui-po");
      const msg = await tungguTeks(r, "po-approval-notice", /disetujui/);
      const po = db1("purchase_orders", `{id:"${K.po.id}"}`);
      assert(po.approval_status === "approved" && po.status !== "waiting_approval", `PO ${po.status}/${po.approval_status}`);
      const task = mongo(`return db.wms_tasks.findOne({po_id:"${K.po.id}",flow_type:"inbound"},{_id:0,id:1,status:1,expected_qty:1,expected_rolls:1,warehouse_name:1})`);
      assert(task && Number(task.expected_qty) === QTY, `tugas penerimaan: ${JSON.stringify(task)}`);
      K.task = { id: task.id }; simpan();
      await sorot(r.tid("po-approval-notice"));
      await r.shot("admin-po-disetujui");
      await lepas(r.tid("po-approval-notice"));
      return `${msg} · disetujui oleh ${po.approved_by} · tugas ${task.status} ${task.expected_qty} yard rencana ${task.expected_rolls} roll di ${task.warehouse_name}`;
    });

  // ── 5. Gudang menerima barang (Barang Masuk › Scan Terima per PO) ─────────────────────────────────────────────────
  const DYE = `DL-A2-${NO}`;
  const SJ = `SJ-LTH${NO}-${Date.now().toString(36).toUpperCase().slice(-4)}`;
  if (langkah(7)) await r.step(7, "Gudang", "Login warehouse@ → Gudang › Operasi Gudang › tab Barang Masuk → tab Scan Terima per PO → cari nomor PO → klik tugasnya",
    `Tugas PO: 0/${QTY} yard · rencana ${ROLL} roll, status Menunggu barang; panel kanan berisi pilihan Scan Label Supplier / Input Manual`, async () => {
      await r.login("warehouse");
      await buka(r, "wms-operations", "goods-receipts", "gudang");
      await r.tid("goods-receipts-view").waitFor();
      await klikPotret(r, r.tid("grn-view-tab-legacy"), "gudang-tab-scan-per-po");
      await r.tid("inbound-scan-panel").waitFor();
      await r.idle(800);
      await r.tid("inbound-search").fill(K.po.number);
      await r.idle(400);
      const row = r.tid(`inbound-task-${K.task.id}`);
      await row.waitFor({ timeout: 15000 });
      const t = (await row.innerText()).replace(/\s+/g, " ");
      assert(t.includes(`rencana ${ROLL} roll`), `daftar tugas tanpa rencana ${ROLL} roll: ${t}`);
      await klikPotret(r, row, "gudang-tugas-po");
      await r.tid("inbound-mode-toggle").waitFor();
      return t;
    });

  if (langkah(7)) await r.step(8, "Gudang", `Pilih [[Input Manual]] → *Qty diterima* ${QTY} (yard) · *Dye Lot* ${DYE} → [[Kirim Hasil Scan]]`,
    `Pesan "Penerimaan tercatat — Diterima ${QTY.toLocaleString("id-ID")} dari ${QTY.toLocaleString("id-ID")} yard"; muncul tombol [[Selesaikan]]`, async () => {
      await r.tid("inbound-mode-manual").click();
      await r.tid("receive-doc-qty-input").waitFor();
      await r.tid("receive-doc-qty-input").fill(String(QTY));
      await r.tid("scan-dye-lot-input").fill(DYE);
      await r.idle(600);
      await klikPotret(r, r.tid(`scan-task-${K.task.id}`), "gudang-input-manual");
      await r.page.waitForFunction((id) => !!document.querySelector(`[data-testid="complete-task-${id}"]`), K.task.id, { timeout: 15000 });
      const task = mongo(`return db.wms_tasks.findOne({id:"${K.task.id}"},{_id:0,status:1,received_qty:1})`);
      assert(Number(task.received_qty) === QTY, `diterima ${task.received_qty}`);
      return `tugas ${task.status} · diterima ${task.received_qty}`;
    });

  if (langkah(7)) await r.step(9, "Gudang", `Klik [[Selesaikan]] → di pop-up "Goods Receipt — Rincian Roll" klik [[Buat ${ROLL} roll (bagi rata …)]] → isi *Lot supplier*, *No. SJ supplier* ${SJ}, Dye Lot tiap roll → [[Selesaikan Penerimaan]]`,
    `Form berisi ${ROLL} roll × 100 yard (Σ = ${QTY.toLocaleString("id-ID")} yard ✓); sesudah simpan: pesan "Barang masuk gudang", roll masuk karantina menunggu pemeriksaan kedatangan (SPK MD Quality)`, async () => {
      await r.tid(`complete-task-${K.task.id}`).click();
      await r.tid("gr-catchweight-modal").waitFor();
      await r.idle(500);
      await r.tid("gr-fill-plan-rolls").click();
      await r.tid(`gr-roll-row-${ROLL - 1}`).waitFor();
      await r.tid("gr-supplier-lot").fill(`LOT-${NO}-A2`);
      await r.tid("gr-supplier-dn").fill(SJ);
      for (let i = 0; i < ROLL; i++) {
        const dl = r.tid(`gr-roll-dyelot-${i}`);
        if (!(await dl.inputValue())) await dl.fill(DYE);
      }
      const tot = await r.text("gr-roll-totals");
      await sorot(r.tid("gr-plan-rolls"));
      await klikPotret(r, r.tid("gr-submit-complete"), "gudang-rincian-roll");
      await lepas(r.tid("gr-plan-rolls"));
      await r.tid("gr-catchweight-modal").waitFor({ state: "detached", timeout: 30000 });
      await r.tid("gr-lot-result").waitFor({ timeout: 15000 });
      await r.shot("gudang-hasil-penerimaan");
      const task = mongo(`return db.wms_tasks.findOne({id:"${K.task.id}"},{_id:0,status:1,received_qty:1,qty_rolls:1,gl_posting:1})`);
      const rolls = mongo(`return db.inventory_rolls.find({$or:[{po_id:"${K.po.id}"},{"acquired.ref_id":"${K.po.id}"}]},{_id:0,status:1}).toArray()`);
      const spk = mongo(`return db.inspections.findOne({task_id:"${K.task.id}"},{_id:0,id:1,number:1,status:1,md_only:1})`);
      assert(rolls.length === ROLL, `roll terbentuk ${rolls.length}`);
      assert(spk, "SPK kedatangan tidak terbentuk");
      K.spk = { id: spk.id, number: spk.number }; simpan();
      const st = [...new Set(rolls.map((x) => x.status))].join(",");
      return `${tot} · tugas ${task.status} · ${rolls.length} roll (${st}) · SPK ${spk.number} ${spk.status} md_only=${spk.md_only} · jurnal GR ${task.gl_posting && task.gl_posting.status}`;
    });

  if (langkah(7)) await r.step(10, "Buku", "Cek buku: jurnal penerimaan barang (GR)", `Persediaan Barang 1-1300 (D) ${rp(DPP)} / Hutang Belum Ditagih (GR/IR) 2-1150 (K) ${rp(DPP)} — nilai PO tanpa PPN, seimbang`, async () => {
      const je = jurnalDari([K.task.id]).find((j) => j.source_type === "goods_receipt");
      assert(je, "jurnal GR tidak ada");
      K.je_gr = je.number; simpan();
      return cekJurnal(je, [["1-1300", "D", DPP], ["2-1150", "K", DPP]]);
    });

  // ── 6. Pemeriksaan kedatangan: Kepala Gudang menugaskan SPK → MD Quality memeriksa & menerima ─────────────────────
  const bukaSpk = async () => {
    await buka(r, "quality-hub", "inspections");
    await r.tid("inspections-view").waitFor();
    await r.idle(600);
    await r.tid("ins-search").fill(K.spk.number);
    await r.idle(800);
    const b = r.tid(`ins-detail-${K.spk.id}`);
    await b.waitFor({ timeout: 15000 });
    return b;
  };
  if (langkah(11)) await r.step(11, "Kepala Gudang", "Login wh.admin@ → Kualitas › SPK Inspeksi → cari nomor SPK → buka → *Tugaskan ke petugas inspect* Lestari Wulandari (MD Quality) → [[Tugaskan]]",
    "SPK kedatangan berstatus Draf berisi 75 roll; catatan \"SPK MD Quality (warna & handfeel)…\"; sesudah ditugaskan status Ditugaskan", async () => {
      await r.login("wh.admin");
      const b = await bukaSpk();
      await klikPotret(r, b, "kepala-gudang-daftar-spk");
      await r.tid("ins-detail-panel").waitFor();
      await r.idle(600);
      await pilihCari(r, "ins-assign-select", "", "Lestari");
      await klikPotret(r, r.tid("ins-assign-button"), "kepala-gudang-tugaskan");
      await tungguTeks(r, "ins-detail-status", /Ditugaskan|Assigned/i);
      const spk = db1("inspections", `{id:"${K.spk.id}"}`, "{_id:0,status:1,assigned_to_name:1,lines:1,md_only:1}");
      return `SPK ${K.spk.number} ${spk.status} · ${spk.lines.length} baris · md_only ${spk.md_only} · petugas ${spk.assigned_to_name || ""}`;
    });

  if (langkah(12)) await r.step(12, "MD Quality", "Login mdquality@ → Kualitas › SPK Inspeksi → buka SPK → pada roll pertama klik [[MD Quality]] → *Hasil banding warna* Sesuai sample · *Hasil banding handfeel* Sesuai sample → [[Simpan hasil]]",
    "Baris roll pertama: warna & handfeel Sesuai; \"Dicek MD Quality 1 dari 75 (sampling)\"", async () => {
      await r.login("mdquality");
      const b = await bukaSpk();
      await b.click();
      await r.tid("ins-detail-panel").waitFor();
      await r.idle(600);
      const spk = db1("inspections", `{id:"${K.spk.id}"}`, "{_id:0,lines:1}");
      const ln = spk.lines[0];
      await klikPotret(r, r.tid(`ins-line-mdq-${ln.id}`), "mdq-baris-pertama");
      await r.tid("ins-line-modal").waitFor();
      await pilihCari(r, "ins-color-select", "", /Sesuai sample/);
      await pilihCari(r, "ins-handfeel-select", "", /Sesuai sample/);
      await r.tid("ins-line-remark").fill(`Warna & handfeel sesuai sample — Latihan ${NO}`);
      await klikPotret(r, r.tid("ins-line-submit"), "mdq-isi-hasil");
      await r.tid("ins-line-modal").waitFor({ state: "detached", timeout: 15000 });
      await r.idle(800);
      const samp = await r.text("ins-detail-sampling").catch(() => "");
      return `roll ${ln.roll_no || ln.roll_id} · ${samp}`;
    });

  if (langkah(12)) await r.step(13, "MD Quality", "Pada bagian Tindakan pilih *Keputusan akhir* Diterima seluruhnya → [[Tutup SPK]]",
    "SPK Selesai · keputusan Diterima; 75 roll lepas karantina menjadi stok tersedia di Gudang Jakarta (roll yang tidak dicek ditandai \"lolos lewat sampling\")", async () => {
      await pilihCari(r, "ins-decision-select", "", /Diterima seluruhnya/);
      await klikPotret(r, r.tid("ins-finish-button"), "mdq-tutup-spk");
      const ask = r.tid("confirm-modal");
      if (await ask.isVisible({ timeout: 2000 }).catch(() => false)) await setuju(r, "confirm-modal");
      await tungguTeks(r, "ins-detail-status", /Selesai|Done|Closed/i, 20000);
      await r.idle(600);
      await sorot(r.tid("ins-detail-decision"));
      await r.shot("mdq-spk-selesai");
      await lepas(r.tid("ins-detail-decision"));
      const rolls = mongo(`return db.inventory_rolls.find({$or:[{po_id:"${K.po.id}"},{"acquired.ref_id":"${K.po.id}"}]},{_id:0,status:1,warehouse_id:1}).toArray()`);
      const st = {};
      rolls.forEach((x) => { st[x.status] = (st[x.status] || 0) + 1; });
      assert((st.available || 0) === ROLL, `status roll: ${JSON.stringify(st)}`);
      const task = mongo(`return db.wms_tasks.findOne({id:"${K.task.id}"},{_id:0,status:1})`);
      const po = db1("purchase_orders", `{id:"${K.po.id}"}`, "{_id:0,status:1}");
      return `keputusan ${await r.text("ins-detail-decision")} · roll ${JSON.stringify(st)} · tugas ${task.status} · PO ${po.status}`;
    });

  // ── 7. Tagihan pemasok (3-way match PO ↔ penerimaan ↔ faktur) → hutang ──────────────────────────────────────────
  if (langkah(14)) await r.step(14, "Manajer", `Login manager@ → Keuangan › Hutang › Tagihan → [[Tagihan baru]] → *Pesanan Pembelian* PO peserta · *No. Faktur Supplier* ${FAKTUR}`,
    `Baris PO terisi otomatis: tagih ${QTY.toLocaleString("id-ID")} yard (= diterima) × ${rp(HARGA)}; pencocokan "Cocok bersih"; Subtotal (sebelum PPN) ${rp(DPP)}`, async () => {
      await r.login("manager");
      await buka(r, "accounts-payable", "vendor-bills", "keuangan");
      await r.tid("vendor-bills-view").waitFor();
      await r.idle(600);
      await klikPotret(r, r.tid("create-vendor-bill-button"), "manajer-tagihan-baru");
      await r.tid("vendor-bill-create-modal").waitFor();
      await r.idle(600);
      await pilihCari(r, "vb-po-select", K.po.number, K.po.number);
      await r.tid("vb-item-row-0").waitFor({ timeout: 15000 });
      await r.tid("vb-invoice-input").fill(FAKTUR);
      await r.idle(400);
      assert(num(await r.tid("vb-item-billed-0").inputValue()) === QTY, "qty tagih ≠ diterima");
      const match = await r.text("vb-overall-match");
      assert(/Cocok bersih/i.test(match), `pencocokan: ${match}`);
      const sub = await r.text("vb-gross-total");
      assert(num(sub) === DPP, `subtotal ${sub}`);
      await sorot(r.tid("vb-overall-match"));
      await sorot(r.tid("vb-submit-now"));
      await r.shot("manajer-isi-tagihan");
      await lepas(r.tid("vb-overall-match"));
      await lepas(r.tid("vb-submit-now"));
      return `${match} · subtotal ${sub} · tombol "${await r.text("vb-submit-now")}"`;
    });

  if (langkah(14)) await r.step(15, "Manajer", "Klik [[Kirim & Posting]]",
    `Pesan "Tagihan VB-… dibuat — langsung terposting (cocok bersih)."; rincian: Total ${rp(TOTAL)} = DPP ${rp(DPP)} + PPN Masukan ${rp(PPN)}, Sisa Hutang ${rp(TOTAL)}, jatuh tempo NET30`, async () => {
      await r.tid("vb-submit-now").click();
      const confirm = r.tid("confirm-modal");
      if (await confirm.isVisible({ timeout: 2000 }).catch(() => false)) await setuju(r, "confirm-modal");
      await r.tid("vendor-bill-create-modal").waitFor({ state: "detached", timeout: 20000 });
      const msg = await tungguTeks(r, "vb-notice", /terposting/);
      const bill = mongo(`return db.vendor_bills.find({po_id:"${K.po.id}",status:{$ne:"cancelled"}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]`);
      assert(bill && bill.status === "posted", `tagihan ${bill && bill.status}`);
      assert(Math.abs(bill.grand_total - TOTAL) < 0.01 && Math.abs(bill.ppn_amount - PPN) < 0.01, `nilai tagihan ${bill.grand_total} / PPN ${bill.ppn_amount}`);
      K.bill = { id: bill.id, number: bill.bill_number }; simpan();
      await r.tid("vb-search").fill(K.bill.number);
      await r.idle(800);
      await r.tid(`vb-open-${bill.id}`).click();
      await r.tid("vendor-bill-detail-panel").waitFor();
      await r.idle(800);
      assert(num(await r.text("vb-fin-ppn")) === PPN, "PPN Masukan di rincian");
      assert(num(await r.text("vb-fin-outstanding")) === TOTAL, "Sisa Hutang di rincian");
      await sorot(r.tid("vb-fin-ppn"));
      await r.shot("tagihan-terposting");
      await lepas(r.tid("vb-fin-ppn"));
      return `${msg} · ${bill.bill_number} jatuh tempo ${bill.due_date} · DPP ${rp(bill.net_subtotal || bill.total_amount)} · PPN ${rp(bill.ppn_amount)} · total ${rp(bill.grand_total)}`;
    });

  if (langkah(14)) await r.step(16, "Buku", "Cek buku: jurnal tagihan pemasok", `GR/IR 2-1150 (D) ${rp(DPP)} + PPN Masukan 1-1500 (D) ${rp(PPN)} / Hutang Usaha 2-1100 (K) ${rp(TOTAL)}, seimbang; sisa GR/IR PO = 0`, async () => {
      const je = jurnalDari([K.bill.id]).find((j) => j.source_type === "vendor_bill");
      assert(je, "jurnal tagihan tidak ada");
      K.je_bill = je.number; simpan();
      const grir = mongo(`return db.journal_entries.aggregate([{$match:{"ref.po_id":"${K.po.id}",status:{$ne:"void"}}},{$unwind:"$lines"},
        {$match:{"lines.account_code":"2-1150"}},{$group:{_id:null,d:{$sum:"$lines.debit"},k:{$sum:"$lines.credit"}}}]).toArray()[0]||{d:0,k:0}`);
      assert(Math.abs(grir.k - grir.d) < 0.01, `sisa GR/IR PO ${grir.k - grir.d}`);
      return `${cekJurnal(je, [["2-1150", "D", DPP], ["1-1500", "D", PPN], ["2-1100", "K", TOTAL]])} · GR/IR PO: K ${rp(grir.k)} − D ${rp(grir.d)} = 0`;
    });

  if (langkah(17)) await r.step(17, "Finance", `Login akun peserta (${akunPeserta(NO)}) → Keuangan › Hutang › Tagihan → cari "Latihan ${NO}" → [[Detail →]]`,
    `Rincian: Terposting · Match Bersih · "3-way match bersih" (Pesan = Terima = Tagih ${QTY.toLocaleString("id-ID")}, Harga PO = Harga Bill); Dokumen Terkait: PO & jurnal`, async () => {
      await r.login(akunPeserta(NO));
      await klikPotret(r, r.tid("nav-accounts-payable"), "finance-menu-hutang");
      await r.tid("vendor-bills-view").waitFor();
      await r.idle(600);
      await r.tid("vb-search").fill(`Latihan ${NO}`);
      await r.idle(1000);
      await klikPotret(r, r.tid(`vb-open-${K.bill.id}`), "finance-cari-tagihan");
      await r.tid("vendor-bill-detail-panel").waitFor();
      await r.idle(800);
      assert(/Match Bersih/.test(await r.text("vb-detail-match")), "bukan Match Bersih");
      assert(/3-way match bersih/.test(await r.text("vb-match-clean")), "teks 3-way match bersih tidak tampil");
      const it = await r.text("vb-detail-item-0");
      const panel = (await r.tid("vendor-bill-detail-panel").innerText()).replace(/\s+/g, " ");
      assert(panel.includes(K.po.number), "PO tidak disebut di rincian");
      await sorot(r.tid("vb-match-clean"));
      await r.shot("finance-3way-match");
      await lepas(r.tid("vb-match-clean"));
      return `${it.slice(0, 200)}`;
    });

  // ── 8. Kontrabon (tukar faktur): Manajer buat & verifikasi → Admin setujui → Manajer jadwalkan → Finance bayar ──────
  const bukaCb = async () => {
    await buka(r, "accounts-payable", "contra-bons", "keuangan");
    await r.tid("contra-bons-view").waitFor();
    await r.tid("cb-filter-q").fill(K.cb.number);
    const row = r.tid(`cb-row-${K.cb.id}`);
    await row.waitFor({ timeout: 15000 });
    await row.click();
    await r.tid("cb-detail-panel").waitFor();
    await r.idle(500);
  };
  if (langkah(18)) await r.step(18, "Manajer", `Login manager@ → Keuangan › Hutang › tab Kontrabon → [[Kontrabon baru]] → *Supplier* ${PEMASOK} → [[Lanjut]] → centang tagihan VB → [[Lanjut]] → centang *Ajukan langsung* → [[Terbitkan kontrabon]]`,
    `Bilah hijau "Kontrabon KSC/CB-… terbit — 1 faktur digabung, nilai bersih ${rp(TOTAL)}"; status Diajukan`, async () => {
      await r.login("manager");
      await buka(r, "accounts-payable", "contra-bons", "keuangan");
      await r.tid("contra-bons-view").waitFor();
      await r.idle(500);
      await klikPotret(r, r.tid("cb-new"), "manajer-kontrabon-baru");
      await r.tid("cb-create-wizard").waitFor();
      await pilihCari(r, "cb-create-supplier", `Latihan ${NO}`, PEMASOK);
      await r.tid("cb-create-prep-summary").waitFor();
      await r.idle(400);
      await r.tid("cb-create-next").click();
      const cek = r.tid(`cb-create-pick-${K.bill.id}`);
      await cek.waitFor();
      const semua = await r.page.$$eval('[data-testid^="cb-create-pick-"]', (els) => els.map((e) => e.getAttribute("data-testid")));
      for (const t of semua) {
        const box = r.tid(t);
        const mau = t === `cb-create-pick-${K.bill.id}`;
        if ((await box.isChecked()) !== mau) await box.click();
      }
      await sorot(r.tid(`cb-create-bill-${K.bill.id}`));
      await klikPotret(r, r.tid("cb-create-next"), "manajer-kontrabon-faktur");
      await r.tid("cb-create-review").waitFor();
      await r.tid("cb-create-submit-now").check();
      await klikPotret(r, r.tid("cb-create-submit"), "manajer-kontrabon-periksa");
      await r.tid("cb-create-wizard").waitFor({ state: "detached", timeout: 20000 });
      const msg = await tungguTeks(r, "cb-notice", /terbit/);
      const cb = mongo(`return db.contra_bons.find({"bills.bill_id":"${K.bill.id}",status:{$ne:"cancelled"}},{_id:0,id:1,number:1,totals:1,status:1}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
      assert(cb && Math.abs(Number(cb.totals.net_payable) - TOTAL) < 0.01, `kontrabon ${JSON.stringify(cb)}`);
      K.cb = { id: cb.id, number: cb.number }; simpan();
      await tungguTeks(r, "cb-detail-status", /Diajukan/);
      return msg;
    });

  if (langkah(18)) await r.step(19, "Manajer", "Di rincian kontrabon klik [[Verifikasi 3-way match]]", "Status Terverifikasi (3-way match dijalankan ulang tanpa selisih)", async () => {
      await r.idle(800);
      await tungguTeks(r, "cb-action-primary", /Verifikasi/);
      await klikPotret(r, r.tid("cb-action-primary"), "manajer-verifikasi-kontrabon");
      await tungguTeks(r, "cb-detail-status", /Terverifikasi/);
      return await r.text("cb-notice");
    });

  if (langkah(20)) await r.step(20, "Admin", "Login admin@ → Keuangan › Hutang › Kontrabon → buka kontrabon → [[Setujui kontrabon]]",
    "Status Disetujui (kontrol dua orang: pembuat kontrabon tidak menyetujui sendiri)", async () => {
      await r.login("admin");
      await bukaCb();
      await tungguTeks(r, "cb-action-primary", /Setujui/);
      await klikPotret(r, r.tid("cb-action-primary"), "admin-setujui-kontrabon");
      await tungguTeks(r, "cb-detail-status", /Disetujui/);
      return await r.text("cb-notice");
    });

  if (langkah(21)) await r.step(21, "Manajer", `Login manager@ → buka kontrabon → [[Jadwalkan pembayaran]] → *Rekening rencana* ${REK_BCA} → [[Simpan jadwal bayar]]`,
    "Status Dijadwalkan bayar; tanggal rencana = jatuh tempo, rekening BCA", async () => {
      await r.login("manager");
      await bukaCb();
      await klikPotret(r, r.tid("cb-action-primary"), "manajer-jadwalkan");
      await r.tid("cb-schedule-modal").waitFor();
      await pilih(r, "cb-schedule-account", REK_BCA);
      await klikPotret(r, r.tid("cb-schedule-save"), "manajer-jadwal-bayar");
      await r.tid("cb-schedule-modal").waitFor({ state: "detached", timeout: 15000 });
      await tungguTeks(r, "cb-detail-status", /Dijadwalkan/);
      const doc = mongo(`return db.contra_bons.findOne({id:"${K.cb.id}"},{_id:0,schedule:1,status:1,due_date:1})`);
      return `jadwal ${doc.schedule.planned_payment_date} (jatuh tempo ${doc.due_date}) · ${doc.schedule.method}`;
    });

  let paid;
  if (langkah(22)) await r.step(22, "Finance", `Login akun peserta → Keuangan › Hutang › Kontrabon → buka kontrabon → [[Catat pembayaran]] → periksa rekening ${REK_BCA} → [[Bayar]] → [[Ya, bayar]]`,
    `Form "Bayar pemasok": Kontrabon KSC/CB-…, sisa ${rp(TOTAL)}; konfirmasi menyebut nominal, pemasok & rekening; sesudahnya status Sudah dibayar`, async () => {
      await r.login(akunPeserta(NO));
      await bukaCb();
      const b = r.tid("cb-action-primary");
      assert(/Catat pembayaran/.test(await b.innerText()), `tombol utama Finance: ${await b.innerText()}`);
      await klikPotret(r, b, "finance-catat-pembayaran");
      await r.tid("pay-supplier-modal").waitFor();
      await r.tid("pay-supplier-number").waitFor();
      assert(num(await r.text("pay-supplier-outstanding")) === TOTAL, "sisa di form ≠ nilai bersih");
      const rek = await r.text("pay-supplier-account");
      if (!rek.includes(REK_BCA)) await pilih(r, "pay-supplier-account", REK_BCA);
      await klikPotret(r, r.tid("pay-supplier-submit"), "finance-form-bayar");
      const msg = await r.text("pay-supplier-confirm-message");
      assert(msg.includes(REK_BCA) && msg.includes(PEMASOK), `konfirmasi: ${msg}`);
      await sorot(r.tid("pay-supplier-confirm-confirm"));
      await r.shot("finance-konfirmasi-bayar");
      await setuju(r, "pay-supplier-confirm");
      await r.tid("pay-supplier-modal").waitFor({ state: "detached", timeout: 20000 });
      await tungguTeks(r, "cb-detail-status", /Sudah dibayar/);
      await sorot(r.tid("cb-detail-status"));
      await r.shot("finance-kontrabon-dibayar");
      await lepas(r.tid("cb-detail-status"));
      paid = mongo(`return db.contra_bons.findOne({id:"${K.cb.id}"},{_id:0})`);
      assert(paid.status === "paid", `status DB ${paid.status}`);
      const p = (paid.payments || [])[0] || {};
      K.kas = { id: p.cash_txn_id, number: p.cash_txn_number || "" }; simpan();
      return `konfirmasi "${msg}"`;
    });

  if (langkah(22)) await r.step(23, "Buku", "Cek buku: jurnal pembayaran & status tagihan", `Hutang Usaha 2-1100 (D) ${rp(TOTAL)} / Kas Besar / Bank 1-1100 (K) ${rp(TOTAL)}, seimbang; tagihan Lunas; kas keluar dari ${REK_BCA}`, async () => {
      paid = paid || mongo(`return db.contra_bons.findOne({id:"${K.cb.id}"},{_id:0})`);
      const bill = db1("vendor_bills", `{id:"${K.bill.id}"}`, "{_id:0,status:1,amount_paid:1,grand_total:1}");
      assert(bill.status === "paid" && Number(bill.amount_paid) + 0.01 >= Number(bill.grand_total), `tagihan ${bill.status} ${bill.amount_paid}`);
      const p = (paid.payments || [])[0] || {};
      const je = jurnalDari([p.cash_txn_id, p.payment_intent_id, p.id, K.cb.id]).find((j) => (j.lines || []).some((l) => l.account_code === "2-1100"));
      assert(je, "jurnal bayar tidak ditemukan");
      K.je_bayar = je.number;
      const cash = mongo(`return db.cash_transactions.findOne({id:"${p.cash_txn_id}"},{_id:0,id:1,number:1,amount:1,account_id:1,direction:1})`);
      const bank = db1("bank_accounts", `{id:"${cash.account_id}"}`, "{_id:0,name:1}");
      assert(bank.name === REK_BCA && cash.direction === "out" && Math.abs(cash.amount - TOTAL) < 0.01, `kas ${JSON.stringify(cash)} ${bank.name}`);
      K.kas = { id: cash.id, number: cash.number }; simpan();
      return `${cekJurnal(je, [["2-1100", "D", TOTAL], ["1-1100", "K", TOTAL]])} · kas ${cash.number} · tagihan ${bill.status}`;
    });

  // ── 9. Rekonsiliasi bank: mutasi keluar di rekening koran = kas keluar pembayaran ────────────────────────────────────
  if (langkah(24)) await r.step(24, "Finance", `Keuangan › Kas & Bank › Rekonsiliasi → rekening ${REK_BCA} → [[Impor mutasi bank]] → template BCA (CSV) → tempel 1 baris "TRSF E-BANKING DB … LATIHAN ${NO} PEMASOK GREY" ${rp(TOTAL)} → [[Pratinjau]] → [[Impor]]`,
    `"Terbaca 1 baris … keluar ${rp(TOTAL)}"; sesudah impor baris mutasi berstatus Perlu keputusan`, async () => {
      const bca = await kb.rekening(akunPeserta(NO), REK_BCA);
      K.bca = bca.id; simpan();
      const tgl = kb.hariIni();
      const teks = ["Tanggal,Keterangan,Cabang,Jumlah,DB/CR,Saldo",
        `${tgl.bca},TRSF E-BANKING DB ${K.cb.number} LATIHAN ${NO} PEMASOK GREY,0000,"${kb.nominalBca(TOTAL)}",DB,0`].join("\n");
      await kb.menu(r, "bank-reconciliation");
      await kb.pilih(r, "recon-account-select", bca.id);
      await r.tid("recon-summary").waitFor();
      await klikPotret(r, r.tid("recon-import-toggle"), "finance-rekon-impor");
      await r.tid("recon-import-panel").waitFor();
      const fmts = await (await api(akunPeserta(NO))).get("/bank-reconciliation/formats", KSC);
      const fBca = fmts.find((f) => f.bank_code === "bca" && (f.file_kind || "csv") === "csv");
      await kb.pilih(r, "recon-format-select", fBca.id);
      await r.tid("recon-raw").fill(teks);
      await r.tid("recon-preview-btn").click();
      const t = await kb.tunggu(r, "recon-preview", /Terbaca 1 baris/);
      await kb.shotSorot(r, "finance-rekon-pratinjau", r.tid("recon-import-submit"));
      await r.tid("recon-import-submit").click();
      const n = await kb.tunggu(r, "recon-notice", /Impor BCA/);
      const line = mongo(`return db.bank_statement_lines.findOne({bank_account_id:"${bca.id}",description:{$regex:"LATIHAN ${NO} PEMASOK GREY"}},{_id:0,id:1,status:1})`);
      assert(line, "baris mutasi tidak tersimpan");
      K.mutasi = line.id; simpan();
      return `${t.split("Tanggal")[0]} · ${n}`;
    });

  if (langkah(24)) await r.step(25, "Finance", `Cari "LATIHAN ${NO}" di daftar mutasi → pada baris itu klik [[Cocokkan]] → pada kandidat kas pembayaran (nominal sama) klik [[Tautkan]]`,
    "Kandidat = transaksi kas keluar pembayaran kontrabon (nominal sama, tanggal sama); sesudah Tautkan: \"Mutasi ditautkan …\" dan baris Tercocok — tanpa jurnal baru", async () => {
      await r.tid("recon-lines-search").fill(`LATIHAN ${NO}`);
      await r.idle(400);
      await r.tid(`recon-line-${K.mutasi}`).waitFor();
      const st0 = mongo(`return db.bank_statement_lines.findOne({id:"${K.mutasi}"},{_id:0,status:1})`).status;
      if (st0 !== "matched") {
        await klikPotret(r, r.tid(`recon-matchbtn-${K.mutasi}`), "finance-rekon-cocokkan", { locator: r.tid("recon-lines-table") });
        await r.tid("recon-match-modal").waitFor();
        const cand = r.tid(`recon-cand-${K.kas.id}`);
        await cand.waitFor();
        const ct = await kb.isi(cand);
        await kb.shotSorot(r, "finance-rekon-kandidat", r.tid(`recon-pick-cand-${K.kas.id}`), { locator: r.tid("recon-match-modal") });
        await r.tid(`recon-pick-cand-${K.kas.id}`).click();
        await kb.tunggu(r, "recon-notice", /Mutasi ditautkan/);
        await r.tid("recon-match-modal").waitFor({ state: "detached" });
        r.note(`kandidat: ${ct}`);
      } else r.note("baris mutasi sudah tercocok otomatis oleh pengguna lain (Cocokkan otomatis)");
      await r.tid("recon-lines-search").fill(`LATIHAN ${NO}`);
      await kb.tunggu(r, `recon-status-${K.mutasi}`, /^Tercocok$/);
      const line = mongo(`return db.bank_statement_lines.findOne({id:"${K.mutasi}"},{_id:0,status:1,allocations:1})`);
      assert((line.allocations || []).some((a) => a.txn_id === K.kas.id), "mutasi tertaut ke kas lain");
      const c = kb.kas(K.kas.id);
      assert(Math.abs(Number(c.reconciled_amount || 0) - Number(c.amount)) < 0.01, "kas belum terekonsiliasi penuh");
      assert(kb.jurnal("cash_transaction", K.kas.id).length <= 1, "pencocokan menerbitkan jurnal ganda");
      await kb.sorot(r.tid(`recon-line-${K.mutasi}`));
      await r.shot("finance-rekon-tercocok", { locator: r.tid("recon-lines-table") });
      await kb.lepas(r.tid(`recon-line-${K.mutasi}`));
      return `mutasi ${line.status} → kas ${K.kas.number}`;
    });

  // ── 10. GR/IR & Jejak Dokumen ─────────────────────────────────────────────────────────────────────────────────────
  if (langkah(26)) await r.step(26, "Finance", "Keuangan › Hutang › tab GR/IR (Diterima Belum Ditagih) → cari nomor PO → centang *Tampilkan yang sudah nol*",
    `Baris PO: Nilai diterima ${rp(DPP)} = Sudah ditagih ${rp(DPP)}, Sisa GR/IR Rp 0`, async () => {
      await buka(r, "accounts-payable", "gr-ir", "keuangan");
      await r.tid("grir-view").waitFor();
      await r.tid("grir-search").locator("input").first().fill(K.po.number).catch(async () => r.tid("grir-search").fill(K.po.number));
      await r.tid("grir-show-zero").check();
      const row = r.tid(`grir-row-${K.po.id}`);
      await row.waitFor({ timeout: 15000 });
      await r.idle(500);
      const t = (await row.innerText()).replace(/\s+/g, " ");
      assert(num(await r.text(`grir-balance-${K.po.id}`)) === 0, "sisa GR/IR ≠ 0");
      assert(t.split(rp(DPP).replace("Rp ", "")).length >= 3, `nilai diterima/ditagih ≠ ${rp(DPP)}: ${t}`);
      await sorot(r.tid(`grir-balance-${K.po.id}`));
      await r.shot("finance-grir-nol");
      await lepas(r.tid(`grir-balance-${K.po.id}`));
      return t.slice(0, 200);
    });

  if (langkah(26)) await r.step(27, "Finance", `Pusat Dokumen › tab Jejak Dokumen → ketik ${K.po ? K.po.number : "nomor PO"} → klik hasilnya`,
    "Rantai: PR → PO → tugas terima/penerimaan → SPK kedatangan → tagihan → kontrabon → kas pembayaran → jurnal (GR, tagihan, bayar)", async () => {
      await buka(r, "document-center", "doc-trace");
      await r.tid("doc-trace-view").waitFor();
      await r.tid("trace-search-input").fill(K.po.number);
      await r.tid(`trace-result-${K.po.id}`).click();
      await r.tid("trace-anchor-card").waitFor({ timeout: 20000 });
      await r.tid("trace-graph").waitFor();
      await r.idle(1500);
      const g = await r.text("trace-graph");
      const harus = [K.pr.number, K.po.number, K.bill.number, K.cb.number, K.kas.number, K.je_gr, K.je_bill, K.je_bayar].filter(Boolean);
      const ada = harus.filter((x) => g.includes(x));
      const hilang = harus.filter((x) => !g.includes(x));
      await r.shot("finance-jejak-dokumen", { full: true });
      await r.page.evaluate(() => {
        const el = document.querySelector('[data-testid="trace-graph"]');
        for (const e of [el, ...el.querySelectorAll("*")]) if (e.scrollWidth > e.clientWidth + 10) e.scrollLeft = e.scrollWidth;
      });
      await r.idle(300);
      await r.shot("finance-jejak-dokumen-kanan", { locator: r.tid("trace-graph") });
      assert(!hilang.length, `jejak tidak memuat: ${hilang.join(", ")} (ada: ${ada.join(", ")})`);
      return `rantai memuat ${ada.join(" → ")}`;
    });

  await r.finish();
})();
