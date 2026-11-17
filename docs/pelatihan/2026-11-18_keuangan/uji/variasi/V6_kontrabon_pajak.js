// V6 — Variasi isian KONTRABON (F12), FAKTUR PAJAK KELUARAN (F13), SAMPLE BERBAYAR (F14).
//   KN_PESERTA=73 KN_PESERTA2=75 node docs/pelatihan/2026-11-18_keuangan/uji/variasi/V6_kontrabon_pajak.js
// Peserta 1 (bawaan 73): kontrabon berpotongan dibayar sebagian lalu lunas; faktur pajak dengan berbagai NSFP; sample
// berbayar dengan kwitansi kurang dari total. Peserta 2 (bawaan 75): NSFP kembar (beda format); kwitansi sample lebih.
const { Run, assert, rp, num, kartu, akunPeserta, mongo } = require("../lib");
const { REK_BCA, pilih, setuju, cekJurnal, tungguTeks, menu } = require("../hutang_lib");
const { ketik, pilihTanggal, intipKonfirmasi, rpLayar, Tabel, jurnalSumber } = require("./hpg_lib");

const P1 = String(process.env.KN_PESERTA || "73").padStart(2, "0");
const P2 = String(process.env.KN_PESERTA2 || "75").padStart(2, "0");
const KSC = "&entity=ent_ksc";
const tabel = new Tabel("V6");
const INGGRIS = /\b(error|failed|invalid|exceed|must|undefined|NaN|null)\b/i;
const last = (r) => r.steps[r.steps.length - 1];
const catat = (r, row) => tabel.add({ ...row, hasil: last(r).ok ? (row.hasil || "lulus") : "gagal",
  catatan: (row.catatan || "") + (last(r).ok ? "" : ` · GAGAL: ${last(r).info}`) });

// ── Kontrabon ────────────────────────────────────────────────────────────────────────────────────────────────────
async function kontrabon(r, no) {
  const LAYAR = "Hutang › Kontrabon";
  const tg = kartu(no)["a_dasar:tagihan_kontrabon"];
  const b0 = mongo(`return db.vendor_bills.findOne({id:"${tg.tagihan_id}"},{_id:0})`);
  const TOTAL = Number(b0.grand_total);
  const POT = 12600;
  const NET = TOTAL - POT;
  let cb = null;
  const bukaCb = async () => {
    await r.go("contra-bons", KSC);
    await r.tid("contra-bons-view").waitFor();
    await r.tid("cb-filter-q").fill(cb.number);
    await r.tid(`cb-row-${cb.id}`).click();
    await r.tid("cb-detail-panel").waitFor();
    await r.idle(500);
  };
  const muatCb = () => mongo(`return db.contra_bons.findOne({id:"${cb.id}"},{_id:0})`);

  await r.step("K1", "Manajer", `Kontrabon baru untuk ${b0.supplier_name}: centang ${tg.tagihan}, JANGAN centang *Ajukan langsung* → [[Terbitkan kontrabon]]`,
    `Kontrabon Draf, nilai tagihan ${rpLayar(TOTAL)}`, async () => {
      await r.login("manager");
      await r.go("contra-bons", KSC);
      await r.tid("contra-bons-view").waitFor();
      await r.tid("cb-new").click();
      await r.tid("cb-create-wizard").waitFor();
      await pilih(r, "cb-create-supplier", b0.supplier_name);
      await r.tid("cb-create-prep-summary").waitFor();
      await r.tid("cb-create-next").click();
      await r.tid(`cb-create-pick-${tg.tagihan_id}`).waitFor();
      for (const t of await r.page.$$eval('[data-testid^="cb-create-pick-"]', (els) => els.map((e) => e.getAttribute("data-testid")))) {
        const want = t === `cb-create-pick-${tg.tagihan_id}`;
        if ((await r.tid(t).isChecked()) !== want) await r.tid(t).click();
      }
      await r.tid("cb-create-next").click();
      await r.tid("cb-create-review").waitFor();
      if (await r.tid("cb-create-submit-now").isChecked()) await r.tid("cb-create-submit-now").uncheck();
      await r.tid("cb-create-submit").click();
      await r.tid("cb-create-wizard").waitFor({ state: "detached", timeout: 20000 });
      cb = mongo(`return db.contra_bons.find({"bills.bill_id":"${tg.tagihan_id}",status:{$ne:"cancelled"}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]||null`);
      assert(cb && cb.status === "draft", `kontrabon ${cb && cb.status}`);
      await tungguTeks(r, "cb-detail-status", /Draf/i);
      return `${cb.number} draf · tagihan ${rp(cb.totals.bills_total)}`;
    });
  catat(r, { layar: LAYAR, isian: "Wizard kontrabon", masukan: `1 faktur ${tg.tagihan}, tanpa ajukan langsung`, harap: "draf, nilai = total faktur" });
  if (!cb) return;

  const potongan = async (masukan, harapOk) => {
    await r.tid("cb-add-deduction").click();
    await r.tid("cb-deduction-modal").waitFor();
    await pilih(r, "cb-deduction-kind", "Denda keterlambatan supplier");
    await ketik(r, "cb-deduction-amount", masukan);
    await r.tid("cb-deduction-reason").click();
    const opt = r.page.getByRole("option", { name: /terlambat|telat/i }).first();
    await ((await opt.count()) ? opt : r.page.getByRole("option").first()).click();
    const pv = (await r.tid("cb-deduction-amount-preview").innerText().catch(() => "")).trim();
    const dis = await r.tid("cb-deduction-save").isDisabled();
    if (dis) { await r.tid("cb-deduction-modal").getByRole("button", { name: "Batal" }).click(); return { dis, pv }; }
    await r.tid("cb-deduction-save").click();
    const out = await Promise.race([
      r.tid("cb-deduction-modal").waitFor({ state: "detached", timeout: 15000 }).then(() => ({ saved: true })),
      r.tid("cb-deduction-error").waitFor({ timeout: 15000 }).then(async () => ({ err: await r.text("cb-deduction-error") })),
    ]);
    if (out.err) await r.tid("cb-deduction-modal").getByRole("button", { name: "Batal" }).click();
    return { ...out, pv, dis };
  };

  await r.step("K2", "Manajer", `[[Tambah potongan]] · *Jenis* Denda keterlambatan supplier · *Nominal* "${(TOTAL + 100000).toLocaleString("id-ID")}" (lebih dari nilai faktur)`,
    "Ditolak dengan pesan Indonesia (nilai bersih kontrabon tidak boleh negatif); tidak ada potongan tersimpan", async () => {
      const o = await potongan((TOTAL + 100000).toLocaleString("id-ID"));
      assert(!o.saved, `potongan ${o.pv} TERSIMPAN`);
      const msg = o.err || "(tombol mati)";
      assert(!INGGRIS.test(msg), `pesan: ${msg}`);
      assert(!(muatCb().deductions || []).length, "ada potongan tersimpan");
      return `pratinjau ${o.pv} · ${msg}`;
    });
  catat(r, { layar: `${LAYAR} › Tambah potongan`, isian: "Nominal potongan", masukan: (TOTAL + 100000).toLocaleString("id-ID"),
    harap: "ditolak: nilai bersih tidak boleh negatif" });

  await r.step("K3", "Manajer", `[[Tambah potongan]] · Denda keterlambatan supplier · *Nominal* "${POT.toLocaleString("id-ID")}" · alasan → [[Tambah potongan]]`,
    `Potongan ${rpLayar(POT)}; Nilai bersih = ${rpLayar(TOTAL)} − ${rpLayar(POT)} = ${rpLayar(NET)} (layar & DB)`, async () => {
      const o = await potongan(POT.toLocaleString("id-ID"));
      assert(o.saved, `potongan tidak tersimpan: ${o.err || "tombol mati"} (pratinjau ${o.pv})`);
      await r.idle(800);
      const d = muatCb();
      assert(Math.abs(d.totals.deductions_total - POT) < 0.01 && Math.abs(d.totals.net_payable - NET) < 0.01,
        `DB potongan ${d.totals.deductions_total}, bersih ${d.totals.net_payable}`);
      const net = num(await r.text("cb-total-net"));
      assert(net === NET, `layar nilai bersih ${await r.text("cb-total-net")}`);
      return `pratinjau ${o.pv} · tagihan ${rp(d.totals.bills_total)} − potongan ${rp(d.totals.deductions_total)} = bersih ${rp(d.totals.net_payable)}`;
    });
  catat(r, { layar: `${LAYAR} › Tambah potongan`, isian: "Nominal potongan", masukan: POT.toLocaleString("id-ID"),
    harap: `bersih ${rpLayar(NET)}`, hasil: "diperbaiki", catatan: "dulu \"12.600\" terbaca Rp 12,60 (satu titik = desimal, Number()) — diperbaiki MoneyInput/parseMoney" });

  await r.step("K4", "Manajer → Admin", "Manajer [[Ajukan]] → [[Verifikasi 3-way match]]; Admin [[Setujui kontrabon]]", "Status Disetujui", async () => {
    for (const re of [/Ajukan/, /Verifikasi/]) {
      await tungguTeks(r, "cb-action-primary", re);
      await r.tid("cb-action-primary").click();
      await r.idle(900);
    }
    await tungguTeks(r, "cb-detail-status", /Terverifikasi/);
    await r.login("admin");
    await bukaCb();
    await tungguTeks(r, "cb-action-primary", /Setujui/);
    await r.tid("cb-action-primary").click();
    await tungguTeks(r, "cb-detail-status", /Disetujui/);
    return muatCb().status;
  });

  const kemarin = new Date(Date.now() + 7 * 3600e3 - 86400e3).toISOString().slice(0, 10);
  await r.step("K5", "Manajer", `[[Jadwalkan pembayaran]]: *Tanggal rencana* ${kemarin} (KEMARIN) · ${REK_BCA} → [[Simpan jadwal bayar]]`,
    "Diterima (rencana lewat tanggal = sudah jatuh tempo) atau ditolak dengan pesan jelas — tidak 5xx", async () => {
      await r.login("manager");
      await bukaCb();
      await r.tid("cb-action-primary").click();
      await r.tid("cb-schedule-modal").waitFor();
      await pilihTanggal(r, "cb-schedule-date", kemarin);
      await pilih(r, "cb-schedule-account", REK_BCA);
      await r.tid("cb-schedule-save").click();
      const res = await Promise.race([
        r.tid("cb-schedule-modal").waitFor({ state: "detached", timeout: 15000 }).then(() => "ok"),
        r.tid("cb-schedule-error").waitFor({ timeout: 15000 }).then(() => "err"),
      ]);
      if (res === "err") return `ditolak: ${await r.text("cb-schedule-error")}`;
      const d = muatCb();
      return `diterima: ${d.status} · rencana ${d.schedule.planned_payment_date}`;
    });
  catat(r, { layar: `${LAYAR} › Jadwalkan pembayaran`, isian: "Tanggal rencana", masukan: `${kemarin} (kemarin)`,
    harap: "diterima atau ditolak jelas", hasil: "keputusan", catatan: `${last(r).info} — tanggal rencana lampau tidak dibatasi; perlu aturan? (pemilik)` });

  let cb1 = null;
  await r.step("K6", "Finance", `Finance peserta: [[Catat pembayaran]] → ketik "${(NET + 1).toLocaleString("id-ID")}" (lebih Rp 1)`,
    `Tombol [[Bayar]] mati: melebihi sisa ${rpLayar(NET)}`, async () => {
      await r.login(akunPeserta(no));
      await bukaCb();
      await r.tid("cb-action-primary").click();
      await r.tid("pay-supplier-modal").waitFor();
      await r.tid("pay-supplier-number").waitFor();
      assert(num(await r.text("pay-supplier-outstanding")) === NET, `sisa di form ${await r.text("pay-supplier-outstanding")}`);
      await r.tid("pay-supplier-deduction-note").waitFor();
      await ketik(r, "pay-supplier-amount", (NET + 1).toLocaleString("id-ID"));
      assert(await r.tid("pay-supplier-submit").isDisabled(), "tombol Bayar aktif");
      return `${await r.text("pay-supplier-reason")} · catatan potongan: ${await r.text("pay-supplier-deduction-note")}`;
    });
  catat(r, { layar: `${LAYAR} › Catat pembayaran`, isian: "Nominal dibayar", masukan: (NET + 1).toLocaleString("id-ID"),
    harap: "ditolak sebelum simpan", hasil: "diperbaiki", catatan: "dulu ditolak server sesudah konfirmasi" });

  await r.step("K7", "Finance", `Ketik "500.000" · ${REK_BCA} → [[Bayar]] → [[Ya, bayar]]`,
    `Bayar sebagian: status tetap Dijadwalkan, Sudah dibayar Rp 500.000, sisa ${rpLayar(NET - 500000)}; potongan diterapkan; jurnal potongan Hutang (D) / Pendapatan Denda 4-9300 (K) ${rpLayar(POT)} + jurnal kas Hutang (D) / Bank (K) Rp 500.000`, async () => {
      await ketik(r, "pay-supplier-amount", "500.000");
      const acc = await r.text("pay-supplier-account");
      if (!acc.includes(REK_BCA)) await pilih(r, "pay-supplier-account", REK_BCA);
      const msg = await intipKonfirmasi(r, "pay-supplier-submit", "pay-supplier-confirm", { batal: false });
      assert(msg.includes("500.000"), `konfirmasi ${msg}`);
      await setuju(r, "pay-supplier-confirm");
      await r.tid("pay-supplier-modal").waitFor({ state: "detached", timeout: 20000 });
      await r.idle(1000);
      cb1 = muatCb();
      assert(Math.abs(cb1.totals.paid_total - 500000) < 0.01 && Math.abs(cb1.totals.outstanding - (NET - 500000)) < 0.01,
        `DB dibayar ${cb1.totals.paid_total} sisa ${cb1.totals.outstanding}`);
      assert(cb1.status !== "paid", `status ${cb1.status}`);
      const p = cb1.payments[0];
      const je = jurnalSumber([p.cash_txn_id, p.payment_intent_id, cb.id, ...(cb1.deductions || []).map((x) => `${cb.id}:${x.id}`)]);
      const jeKas = je.find((j) => j.lines.some((l) => l.account_code === "2-1100" && Number(l.debit) === 500000));
      const jePot = je.find((j) => j.lines.some((l) => l.account_code === "4-9300"));
      assert(jeKas && jePot, `jurnal kas ${jeKas && jeKas.number} / potongan ${jePot && jePot.number}`);
      const bank = jeKas.lines.find((l) => Number(l.credit) > 0);
      return `${cekJurnal(jeKas, [["2-1100", "D", 500000], [bank.account_code, "K", 500000]])} · ${cekJurnal(jePot, [["2-1100", "D", POT], ["4-9300", "K", POT]])}`;
    });
  catat(r, { layar: `${LAYAR} › Catat pembayaran`, isian: "Nominal dibayar", masukan: "500.000 (sebagian)",
    harap: `sisa ${rpLayar(NET - 500000)}; jurnal potongan + kas`, hasil: "diperbaiki", catatan: "\"500.000\" dulu terbaca Rp 500" });

  await r.step("K8", "Finance", `[[Catat pembayaran]] lagi (nominal terisi sisa ${rpLayar(NET - 500000)}) → [[Bayar]] → [[Ya, bayar]]`,
    `Status Sudah dibayar; Σ kas = ${rpLayar(NET)}; tagihan ${tg.tagihan} Lunas (kas ${rpLayar(NET)} + potongan ${rpLayar(POT)} = ${rpLayar(TOTAL)})`, async () => {
      await tungguTeks(r, "cb-action-primary", /Catat pembayaran/);
      await r.tid("cb-action-primary").click();
      await r.tid("pay-supplier-number").waitFor();
      const v = await r.tid("pay-supplier-amount").inputValue();
      assert(num(v) === NET - 500000 || Number(v) === NET - 500000, `nominal terisi ${v}`);
      await r.tid("pay-supplier-submit").click();
      await setuju(r, "pay-supplier-confirm");
      await r.tid("pay-supplier-modal").waitFor({ state: "detached", timeout: 20000 });
      await tungguTeks(r, "cb-detail-status", /Sudah dibayar/);
      const d = muatCb();
      const bill = mongo(`return db.vendor_bills.findOne({id:"${tg.tagihan_id}"},{_id:0,status:1,amount_paid:1,grand_total:1})`);
      assert(d.status === "paid" && Math.abs(d.totals.paid_total - NET) < 0.01, `kontrabon ${d.status} ${d.totals.paid_total}`);
      assert(bill.status === "paid" && Math.abs(bill.amount_paid - TOTAL) < 0.01, `tagihan ${bill.status} ${bill.amount_paid}`);
      const ids = d.payments.flatMap((p) => [p.cash_txn_id, p.payment_intent_id]).concat([cb.id], (d.deductions || []).map((x) => `${cb.id}:${x.id}`));
      const hutangD = jurnalSumber(ids).reduce((s, j) => s + j.lines.filter((l) => l.account_code === "2-1100").reduce((a, l) => a + Number(l.debit || 0) - Number(l.credit || 0), 0), 0);
      assert(Math.abs(hutangD - TOTAL) < 0.01, `Σ debit Hutang Usaha jurnal kontrabon ${hutangD} ≠ ${TOTAL}`);
      return `kontrabon ${d.status}: kas ${rp(d.totals.paid_total)} + potongan ${rp(d.totals.deductions_total)} · tagihan ${bill.status} ${rp(bill.amount_paid)} · Σ D 2-1100 ${rp(hutangD)}`;
    });
  catat(r, { layar: `${LAYAR} › Catat pembayaran`, isian: "Nominal dibayar", masukan: `sisa ${rpLayar(NET - 500000)}`,
    harap: "lunas; Σ hutang berkurang = nilai faktur" });
}

// ── Faktur pajak ─────────────────────────────────────────────────────────────────────────────────────────────────
async function terbitkanFaktur(r, no) {
  const so = kartu(no)["a_dasar:so_lunas"];
  const order = mongo(`return db.sales_orders.findOne({id:"${so.so_id}"},{_id:0,number:1})`);
  let f = mongo(`return db.tax_invoices.findOne({order_id:"${so.so_id}",status:{$in:["normal","pengganti"]}},{_id:0})`);
  if (f) return { f, order, so };
  await r.tid("finance-desk").waitFor();
  await r.tid("fin-desk-search-faktur_pajak").fill(order.number);
  await r.tid(`fin-desk-faktur_pajak-action-${so.so_id}`).click();
  await tungguTeks(r, "fin-desk-toast", /diterbitkan/, 20000);
  f = mongo(`return db.tax_invoices.findOne({order_id:"${so.so_id}",status:"normal"},{_id:0})`);
  return { f, order, so };
}

async function isiNsfp(r, f, nilai) {
  await r.tid(`fkt-nsfp-${f.id}`).click();
  await r.tid("fkt-modal").waitFor();
  await r.tid("fkt-nsfp-input").fill("");
  await r.tid("fkt-nsfp-input").pressSequentially(nilai, { delay: 10 });
  await r.tid("fkt-modal-submit").click();
  const res = await Promise.race([
    r.tid("fkt-modal").waitFor({ state: "detached", timeout: 15000 }).then(() => ({ ok: true })),
    r.tid("fkt-modal-error").waitFor({ timeout: 15000 }).then(async () => ({ err: await r.text("fkt-modal-error") })),
  ]);
  if (res.err) await r.tid("fkt-modal").getByRole("button", { name: "Batal" }).click();
  const doc = mongo(`return db.tax_invoices.findOne({id:"${f.id}"},{_id:0,nsfp:1,nsfp_key:1})`);
  return { ...res, doc };
}

async function faktur(r, no, no2) {
  const LAYAR = "Akuntansi & Pajak › Pajak › Faktur Keluaran";
  let F = null;
  await r.step("P1", "Finance", `Login peserta ${no} → Meja Finance → [[Terbitkan]] faktur SO peserta → Pajak › Faktur Keluaran, cari SO`,
    "Faktur FKT-… Normal, NSFP belum diisi", async () => {
      await r.login(akunPeserta(no));
      F = await terbitkanFaktur(r, no);
      await menu(r, "akuntansi", "tax-hub");
      await r.tid("tax-invoices-view").waitFor();
      await r.tid("fkt-search").fill(F.order.number);
      await r.tid(`fkt-row-${F.f.id}`).waitFor();
      return `${F.f.number} · ${F.order.number}`;
    });
  if (!F) return;
  const f = F.f;
  const kasus = [
    ["ABC-DEF", "huruf saja", "keputusan", "DITERIMA tanpa peringatan → NSFP tersimpan \"ABC-DEF\" tanpa kunci kembar (nsfp_key kosong). Usul cek: 13–17 digit sesudah titik/strip/spasi dibuang (K-04)"],
    ["12345", "5 digit", "keputusan", "DITERIMA tanpa peringatan (label kotak \"16 digit\"). Usul cek panjang (K-04)"],
    [`01002611180000${no}1`, "17 digit", "keputusan", "diterima (format e-Faktur 17 digit = kode transaksi+status+seri) — sesuai bila K-04 memutuskan"],
    [`010.026-11.180000${no}`, "bertitik & strip", "lulus", "diterima; kunci kembar = digit saja"],
  ];
  let i = 2;
  for (const [nilai, ket, hasil, cat] of kasus) {
    await r.step(`P${i++}`, "Finance", `Ikon [[#]] → *Nomor Seri Faktur Pajak*: "${nilai}" (${ket}) → [[Konfirmasi]]`,
      "Diterima atau ditolak dengan pesan jelas; dicatat apa adanya (aturan bentuk NSFP = keputusan K-04)", async () => {
        const o = await isiNsfp(r, f, nilai);
        if (o.err) return `DITOLAK: ${o.err}`;
        await tungguTeks(r, `fkt-nsfp-text-${f.id}`, new RegExp(nilai.replace(/[.\-]/g, "\\$&")));
        return `DITERIMA · DB nsfp "${o.doc.nsfp}" · kunci "${o.doc.nsfp_key || "—"}"`;
      });
    catat(r, { layar: LAYAR, isian: "Nomor Seri Faktur Pajak", masukan: nilai, harap: "aturan bentuk = keputusan K-04", hasil, catatan: `${last(r).info} — ${cat}` });
  }

  await r.step(`P${i++}`, "Finance", `Peserta ${no2}: terbitkan fakturnya → isi NSFP "01002611180000${no}" (digit SAMA dengan faktur peserta ${no}, tanpa titik)`,
    `Ditolak: "Nomor seri … sudah dipakai faktur ${f.number}"`, async () => {
      await r.login(akunPeserta(no2));
      const F2 = await terbitkanFaktur(r, no2);
      await menu(r, "akuntansi", "tax-hub");
      await r.tid("tax-invoices-view").waitFor();
      await r.tid("fkt-search").fill(F2.order.number);
      await r.tid(`fkt-row-${F2.f.id}`).waitFor();
      const o = await isiNsfp(r, F2.f, `01002611180000${no}`);
      assert(o.err && o.err.includes(f.number) && /sudah dipakai/.test(o.err), `NSFP kembar ${o.err ? "pesan: " + o.err : "DITERIMA"}`);
      const o2 = await isiNsfp(r, F2.f, `010.026-11.180000${no2}`);
      assert(o2.ok, `NSFP peserta ${no2} ditolak: ${o2.err}`);
      return `${o.err} · NSFP sendiri ${o2.doc.nsfp} diterima`;
    });
  catat(r, { layar: LAYAR, isian: "Nomor Seri Faktur Pajak", masukan: `01002611180000${no} (kembar, format lain)`, harap: "ditolak: sudah dipakai" });

  await r.step(`P${i++}`, "Pemeriksa", "Hitung ulang faktur peserta dari baris SO: DPP nilai lain = 11/12 × DPP; PPN = 12% × DPP nilai lain; PPN faktur = PPN Keluaran jurnal pengiriman",
    "Semua sama (±Rp 1)", async () => {
      const so = mongo(`return db.sales_orders.findOne({id:"${F.so.so_id}"},{_id:0,items:1,net_subtotal:1,total_amount:1,discount_total:1,ppn_amount:1,grand_total:1})`);
      const doc = mongo(`return db.tax_invoices.findOne({id:"${f.id}"},{_id:0})`);
      const dpp = Number(so.net_subtotal ?? so.total_amount);
      const dppLain = Math.round(dpp * 11 / 12 * 100) / 100;
      const ppn = Math.round(dppLain * 0.12 * 100) / 100;
      const ships = mongo(`const sids=db.shipments.find({order_id:"${F.so.so_id}"},{_id:0,id:1}).toArray().map(x=>x.id);
        return db.journal_entries.find({status:{$ne:"void"},source_type:"shipment_revenue",source_id:{$in:sids}},{_id:0,number:1,lines:1}).toArray()`);
      const ppnGl = ships.flatMap((j) => j.lines).filter((l) => l.account_code === "2-1200").reduce((s, l) => s + Number(l.credit || 0) - Number(l.debit || 0), 0);
      const d = (a, b) => Math.abs(Number(a) - Number(b)) <= 1;
      // Faktur: `net_subtotal` = DPP (harga jual), `dpp` = DPP nilai lain (11/12), `dpp_nilai_lain` = penanda true/false.
      assert(d(doc.net_subtotal, dpp), `DPP faktur ${doc.net_subtotal} ≠ SO ${dpp}`);
      assert(doc.dpp_nilai_lain === true && d(doc.dpp, dppLain), `DPP nilai lain ${doc.dpp} (penanda ${doc.dpp_nilai_lain}) ≠ 11/12×${dpp} = ${dppLain}`);
      assert(d(doc.ppn_amount, ppn), `PPN faktur ${doc.ppn_amount} ≠ 12%×${dppLain} = ${ppn}`);
      assert(d(ppnGl, doc.ppn_amount), `PPN Keluaran buku ${ppnGl} ≠ faktur ${doc.ppn_amount}`);
      assert(d(doc.grand_total, Number(dpp) + Number(doc.ppn_amount)), `total faktur ${doc.grand_total}`);
      return `DPP ${rp(dpp)} → nilai lain ${rp(dppLain)} → PPN ${rp(ppn)} (faktur ${rp(doc.ppn_amount)}, buku 2-1200 ${rp(ppnGl)}) · total ${rp(doc.grand_total)}`;
    });
  catat(r, { layar: LAYAR, isian: "(hitung ulang)", masukan: "DPP nilai lain 11/12 × 12%", harap: "faktur = jurnal = hitung ulang" });
}

// ── Sample berbayar ──────────────────────────────────────────────────────────────────────────────────────────────
async function terimaUang(r, no, s, masukan, ref) {
  await menu(r, "penjualan", "customers-crm");
  await r.tid("customer-list").waitFor();
  await r.tid("customer-search").fill(`Butik Sample Peserta ${no}`);
  await r.tid(`customer-row-${s.pelanggan_id}`).click();
  await r.tid("customer-360-receive").waitFor({ timeout: 15000 });
  await r.idle(500);
  await r.tid("customer-360-receive").click();
  await r.tid("ar-receipt-modal").waitFor();
  // Tunggu form selesai memuat (nominal terisi otomatis sesudah muat) — mengetik lebih cepat dari itu tercampur dengan
  // isian otomatis (lihat catatan tabel: "50.000" menjadi "832.500").
  await r.page.waitForFunction(() => !document.querySelector('[data-testid="ar-receipt-loading"]'), null, { timeout: 15000 });
  await r.idle(400);
  await ketik(r, "ar-receipt-amount", masukan);
  const pv = (await r.tid("ar-receipt-amount-preview").innerText().catch(() => "")).trim();
  assert(num(pv) === num(masukan), `nominal terbaca ${pv} untuk "${masukan}"`);
  await r.page.waitForFunction(() => !document.querySelector('[data-testid="ar-receipt-account-loading"]'), null, { timeout: 15000 }).catch(() => {});
  await r.idle(600);
  const accText = (await r.tid("ar-receipt-account-field").innerText().catch(() => "")).replace(/\s+/g, " ");
  if (!accText.includes(REK_BCA)) {
    await r.page.locator('[data-testid="ar-receipt-account-field"] [role="combobox"], [data-testid="ar-receipt-account"]').first().click();
    await r.page.getByRole("option", { name: new RegExp(REK_BCA) }).first().click();
  }
  await r.tid("ar-receipt-reference").fill(ref);
  await r.idle(600);
  await r.tid("ar-receipt-submit").click();
  const ada = await Promise.race([
    r.tid("ar-receipt-confirm").waitFor({ timeout: 10000 }).then(() => "konfirmasi"),
    r.tid("payment-variance-dialog").waitFor({ timeout: 10000 }).then(() => "selisih"),
  ]);
  let selisih = "";
  if (ada === "selisih") {
    selisih = (await r.text("pv-sentence")).replace(/\s+/g, " ");
    await r.tid("pv-option-deposit").click().catch(() => {});
    await r.tid("pv-submit").click();
    await r.tid("ar-receipt-confirm").waitFor({ timeout: 10000 }).catch(() => {});
  }
  if (!(await r.tid("ar-receipt-confirm").count())) {
    await r.tid("ar-receipt-modal").waitFor({ state: "detached", timeout: 20000 });
    return `selisih: ${selisih}`;
  }
  const msg = await r.text("ar-receipt-confirm-message");
  await r.tid("ar-receipt-confirm-confirm").click();
  await r.tid("ar-receipt-modal").waitFor({ state: "detached", timeout: 20000 });
  return selisih ? `${msg} · selisih: ${selisih}` : msg;
}

async function bukaSos(r, sosNo, id) {
  await menu(r, "penjualan", "sample-orders");
  await r.tid("sample-orders-view").waitFor();
  await r.tid("sample-orders-search").fill(sosNo);
  await r.tid(`sample-order-row-${id}`).click();
  await r.idle(600);
}

async function sample(r, no, no2) {
  const LAYAR = "Penjualan › Pesanan Sample (+ Terima pembayaran)";
  const s = kartu(no)["d_hutang:sample_berbayar"];
  const sos = mongo(`return db.sales_orders.findOne({id:"${s.sos_id}"},{_id:0,number:1,grand_total:1})`);
  const T = Number(sos.grand_total);
  await r.step("S1", "Finance", `Peserta ${no}: Terima pembayaran Butik Sample, *Nominal diterima* "50.000" (kurang dari total ${rpLayar(T)})`,
    `Kwitansi Rp 50.000; SOS status bayar Sebagian; jurnal Bank (D) / Uang Muka Pelanggan (K) Rp 50.000`, async () => {
      await r.login(akunPeserta(no));
      const msg = await terimaUang(r, no, s, "50.000", `TRF-V6-${no}-A`);
      const rc = mongo(`return db.ar_receipts.find({"allocations.order_id":"${s.sos_id}",status:{$ne:"void"}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]`);
      assert(rc && Math.abs(rc.amount - 50000) < 0.01, `kwitansi ${rc && rc.amount}`);
      const o = mongo(`return db.sales_orders.findOne({id:"${s.sos_id}"},{_id:0,payment_status:1,paid_total:1})`);
      const je = jurnalSumber([rc.cash_txn_id, rc.id]).find((j) => j.lines.some((l) => l.account_code === "1-1100"));
      const um = je.lines.find((l) => Number(l.credit) > 0);
      assert(/Uang Muka/i.test(um.account_name || ""), `akun kredit ${um.account_code} ${um.account_name}`);
      return `konfirmasi "${msg}" · ${rc.number} · SOS ${o.payment_status} ${rp(o.paid_total)} · ${cekJurnal(je, [["1-1100", "D", 50000], [um.account_code, "K", 50000]])}`;
    });
  catat(r, { layar: LAYAR, isian: "Nominal diterima", masukan: "50.000 (kurang dari total)", harap: "kwitansi Rp 50.000, SOS sebagian", hasil: "lulus" });

  await r.step("S2", "Finance", "Pesanan Sample → SOS peserta → [[Setujui Pembayaran]]",
    `Rincian menyebut "Uang tercatat masuk: Rp 50.000 dari ${rpLayar(T)} — kurang ${rpLayar(T - 50000)}"; dialog "Uang belum lengkap" minta konfirmasi → [[Batal]] → SOS tetap Menunggu ACC bayar`, async () => {
      await bukaSos(r, sos.number, s.sos_id);
      const t = await r.text("sample-detail-paid");
      assert(t.includes("50.000") && t.includes(rpLayar(T - 50000).replace("Rp ", "")), `rincian: ${t}`);
      const msg = await intipKonfirmasi(r, "sample-detail-approve-payment", "sample-approve-short");
      const o = mongo(`return db.sales_orders.findOne({id:"${s.sos_id}"},{_id:0,status:1,sample_payment_status:1})`);
      assert(o.status === "waiting_approval", `SOS ${o.status}`);
      return `${t} · dialog "${msg}" → batal → ${o.status}`;
    });
  catat(r, { layar: LAYAR, isian: "Setujui Pembayaran", masukan: "uang baru Rp 50.000", harap: "diberi tahu kurang bayar sebelum setuju",
    hasil: "diperbaiki", catatan: "dulu disetujui tanpa info uang masuk (server tidak memeriksa kwitansi) — kini rincian & konfirmasi menyebut kekurangan" });

  await r.step("S3", "Finance", `Terima pembayaran sisa "${(T - 50000).toLocaleString("id-ID")}" → Setujui Pembayaran`,
    "SOS Lunas → tanpa dialog tambahan → \"pembayaran disetujui\"; status Siap ke gudang", async () => {
      await terimaUang(r, no, s, (T - 50000).toLocaleString("id-ID"), `TRF-V6-${no}-B`);
      await bukaSos(r, sos.number, s.sos_id);
      assert(/lunas/.test(await r.text("sample-detail-paid")), `rincian: ${await r.text("sample-detail-paid")}`);
      await r.tid("sample-detail-approve-payment").click();
      const msg = await tungguTeks(r, "sample-orders-toast", /pembayaran disetujui/);
      const o = mongo(`return db.sales_orders.findOne({id:"${s.sos_id}"},{_id:0,status:1,payment_status:1,paid_total:1})`);
      assert(o.status === "approved" && o.payment_status === "paid" && Math.abs(o.paid_total - T) < 0.01, `SOS ${JSON.stringify(o)}`);
      return `${msg} · SOS ${o.status}/${o.payment_status} ${rp(o.paid_total)}`;
    });
  catat(r, { layar: LAYAR, isian: "Nominal diterima", masukan: (T - 50000).toLocaleString("id-ID"), harap: "lunas, setujui tanpa dialog" });

  const s2 = kartu(no2)["d_hutang:sample_berbayar"];
  const sos2 = mongo(`return db.sales_orders.findOne({id:"${s2.sos_id}"},{_id:0,number:1,grand_total:1})`);
  const T2 = Number(sos2.grand_total);
  await r.step("S4", "Finance", `Peserta ${no2}: Terima pembayaran "100.000" (LEBIH ${rpLayar(100000 - T2)} dari total ${rpLayar(T2)})`,
    `Kwitansi Rp 100.000; SOS Lunas; kelebihan ${rpLayar(100000 - T2)} jadi titipan/deposit pelanggan (bukan pendapatan); jurnal seimbang`, async () => {
      await r.login(akunPeserta(no2));
      const msg = await terimaUang(r, no2, s2, "100.000", `TRF-V6-${no2}`);
      const rc = mongo(`return db.ar_receipts.find({"allocations.order_id":"${s2.sos_id}",status:{$ne:"void"}},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]`);
      const o = mongo(`return db.sales_orders.findOne({id:"${s2.sos_id}"},{_id:0,payment_status:1,paid_total:1})`);
      const je = jurnalSumber([rc.cash_txn_id, rc.id]).find((j) => j.lines.some((l) => l.account_code === "1-1100"));
      assert(Math.abs(rc.amount - 100000) < 0.01 && o.payment_status === "paid", `kwitansi ${rc.amount}, SOS ${o.payment_status}`);
      const pend = je.lines.filter((l) => /^4-/.test(l.account_code));
      assert(!pend.length, `kelebihan masuk pendapatan: ${JSON.stringify(pend)}`);
      return `konfirmasi "${msg}" · ${rc.number} applied ${rp(rc.applied_total)} unapplied ${rp(rc.unapplied_amount)} · SOS ${o.payment_status} ${rp(o.paid_total)} · ${je.number} [${je.lines.map((l) => `${l.account_code} ${Number(l.debit) ? "D" : "K"} ${Math.round(l.debit || l.credit)}`).join(" · ")}]`;
    });
  catat(r, { layar: LAYAR, isian: "Nominal diterima", masukan: "100.000 (lebih dari total)", harap: "kelebihan jadi deposit, jurnal seimbang" });
}

(async () => {
  const r = await new Run("V6", "Variasi isian — kontrabon, faktur pajak, sample berbayar (F12–F14)").start();
  const bagian = (process.env.KN_BAGIAN || "kontrabon,faktur,sample").split(",");
  try {
    if (bagian.includes("kontrabon")) await kontrabon(r, P1);
    if (bagian.includes("faktur")) await faktur(r, P1, P2);
    if (bagian.includes("sample")) await sample(r, P1, P2);
  } catch (e) {
    r.note("GALAT: " + (e && e.message ? e.message : e));
  } finally {
    tabel.simpan();
    await r.finish();
  }
})();
