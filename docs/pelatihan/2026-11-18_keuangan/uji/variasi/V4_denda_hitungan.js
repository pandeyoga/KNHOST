// V4 — Rencana & Denda (F05) + hitungan yang DIHITUNG ULANG di skrip (rumus sendiri, bukan angka layanan):
//   umur piutang per kolom (belum jatuh tempo · 1–30 · 31–60 · 61–90 · >90) dari baris jadwal & tanggal hari ini,
//   taksiran denda dari ATURAN (tarif %/bulan, tenggang, dasar, batas atas, minimum) → layar Saldo & Umur, nota denda,
//   jurnal; ubah jadwal cicilan (Σ ≠ nilai dokumen ditolak, nominal bergaya Indonesia, tanggal lampau).
//   KN_PESERTA=64 KN_PESERTA2=65 node docs/pelatihan/2026-11-18_keuangan/uji/variasi/V4_denda_hitungan.js
// Peserta 1: rencana cicilan belum pernah dinotadenda. Peserta 2: rencana cicilan yang boleh diubah.
const { Run, api, assert, kartu, peserta, akunPeserta, mongo, rp, sleep } = require("../lib");
const { KSC, bukaMenu, bersihkanHasil } = require("../piutang_lib");
const v = require("./vlib");

const NO = peserta("64");
const NO2 = String(process.env.KN_PESERTA2 || "65").padStart(2, "0");
const t = v.tabel("V4");
const LA = "Piutang › Saldo & Umur";
const LR = "Piutang › Rencana & Denda";

const hariIni = () => mongo(`return new Date(Date.now()+7*3600e3).toISOString().slice(0,10)`);
const hari = (a, b) => Math.round((Date.parse(b) - Date.parse(a)) / 86400000);

/** Umur piutang SATU pelanggan dihitung ulang dari jadwal (rencana hidup) / jatuh tempo pesanan + pembayaran. */
function umurHitung(custId, edges) {
  const hariini = hariIni();
  const data = mongo(`const sos=db.sales_orders.find({customer_id:"${custId}",status:{$nin:["cancelled","draft","rejected"]}},
      {_id:0,id:1,grand_total:1,total_amount:1,payments:1,due_date:1}).toArray();
    return sos.map(o=>({o, plan: db.payment_plans.findOne({doc_id:o.id,status:{$ne:"void"}},{_id:0,lines:1})}))`);
  const b = { current: 0, b1_30: 0, b31_60: 0, b61_90: 0, b90_plus: 0 };
  const kunci = ["b1_30", "b31_60", "b61_90", "b90_plus"];
  const baris = [];
  for (const { o, plan } of data) {
    const paid = (o.payments || []).reduce((s, p) => s + Number(p.amount || 0), 0);
    let lines = plan ? plan.lines.map((l) => ({ due: String(l.due_date).slice(0, 10), sisa: Number(l.amount) - Number(l.paid_amount || 0) }))
      : [{ due: String(o.due_date || "").slice(0, 10), sisa: Number(o.grand_total ?? o.total_amount) - paid }];
    for (const l of lines) {
      if (l.sisa <= 0.005) continue;
      const telat = Math.max(0, hari(l.due, hariini));
      const k = telat <= 0 ? "current" : (kunci[edges.findIndex((e) => telat <= e)] || "b90_plus");
      b[k] = v.r2(b[k] + l.sisa);
      baris.push({ ...l, telat, k });
    }
  }
  return { b, baris, total: v.r2(Object.values(b).reduce((s, x) => s + x, 0)) };
}

/** Taksiran denda satu baris dari ATURAN: (dasar × tarif% × hari-kena/30), dibatasi batas atas, nol bila < minimum. */
function dendaHitung(sisaBaris, sisaPesanan, telat, a) {
  if (a.mode === "off" || telat <= a.grace_days) return 0;
  const dasar = a.base === "installment" ? sisaBaris : sisaPesanan;
  let n = v.r2(dasar * (a.rate_pct_per_month / 100) * ((telat - a.grace_days) / 30));
  if (a.cap_pct > 0) n = Math.min(n, v.r2(dasar * a.cap_pct / 100));
  return n < a.min_amount ? 0 : n;
}

(async () => {
  bersihkanHasil("V4");
  const r = await new Run("V4", "Rencana & Denda + hitungan dihitung ulang").start();
  const k = kartu(NO)["b_piutang:cicilan"];
  const k2 = kartu(NO2)["b_piutang:cicilan"];
  try {
    assert(k && k2, "kartu cicilan belum ada");
    assert(!mongo(`return db.penalties.countDocuments({plan_id:"${k.rencana_id}"})`), `rencana ${k.rencana} sudah bernota denda — pakai peserta segar`);
    const fin = await api(akunPeserta(NO));
    const ag = await fin.get("/ar/aging?entity_id=ent_ksc", KSC);
    const aturan = ag.config.penalty;          // MASUKAN aturan (bukan hasil hitung): tarif, tenggang, dasar, batas, minimum
    const edges = ag.config.aging_buckets;
    r.note(`aturan denda: ${JSON.stringify({ mode: aturan.mode, base: aturan.base, rate: aturan.rate_pct_per_month, grace: aturan.grace_days, cap: aturan.cap_pct, min: aturan.min_amount })} · kolom umur ${edges}`);
    const u = umurHitung(k.pelanggan_id, edges);
    const sisaPesanan = u.baris.reduce((s, l) => s + l.sisa, 0);
    const dendaHarap = v.r2(u.baris.reduce((s, l) => s + dendaHitung(l.sisa, sisaPesanan, l.telat, aturan), 0));
    await r.login(akunPeserta(NO));

    await v.kasus(r, t, { layar: LA, isian: "Kolom umur piutang pelanggan cicilan", masukan: `${k.pelanggan} (cicilan 1 jatuh tempo ${k.jatuh_tempo_1}, cicilan 2 ${k.jatuh_tempo_2})`,
      harap: `Dihitung ulang: belum jatuh tempo ${rp(u.b.current)} · 1–30 ${rp(u.b.b1_30)} · 31–60 ${rp(u.b.b31_60)} · 61–90 ${rp(u.b.b61_90)} · >90 ${rp(u.b.b90_plus)} = layanan = layar`,
      hasil: "lulus" }, async () => {
      const row = (ag.customers || []).find((c) => c.customer_id === k.pelanggan_id);
      for (const key of Object.keys(u.b)) assert(Math.abs(row[key] - u.b[key]) < 0.01, `${key}: layanan ${row[key]} ≠ hitung ${u.b[key]}`);
      await bukaMenu(r, "ar-aging", "ar-aging");
      await r.tid("ar-aging-search").fill(k.pelanggan);
      const el = r.tid(`ar-aging-row-${k.pelanggan_id}`);
      await el.waitFor({ timeout: 15000 });
      await r.idle(500);
      const teks = (await el.innerText()).replace(/\s+/g, " ");
      for (const key of Object.keys(u.b)) if (u.b[key] > 0) assert(teks.includes(rp(u.b[key]).replace("Rp ", "")), `layar tanpa ${key} ${rp(u.b[key])}: ${teks}`);
      return `${JSON.stringify(u.b)} · ${teks.slice(0, 160)}`;
    });
    await v.kasus(r, t, { layar: LA, isian: "Taksiran denda (kolom Denda)", masukan: `aturan ${aturan.rate_pct_per_month}%/bulan · tenggang ${aturan.grace_days} hr · dasar ${aturan.base} · batas ${aturan.cap_pct}% · minimum ${rp(aturan.min_amount)}`,
      harap: `Σ (dasar × ${aturan.rate_pct_per_month}% × (hari telat − tenggang)/30) = ${rp(dendaHarap)} (= ${dendaHarap}); layar sama`, hasil: "lulus" }, async () => {
      const row = (ag.customers || []).find((c) => c.customer_id === k.pelanggan_id);
      assert(Math.abs(row.denda - dendaHarap) < 0.01, `layanan ${row.denda} ≠ hitung ${dendaHarap}`);
      const cell = await v.teksAtau(r, `ar-denda-cell-${k.pelanggan_id}`);
      assert(cell.includes(rp(dendaHarap).replace("Rp ", "")), `sel denda: ${cell}`);
      return `${u.baris.map((l) => `${l.due} sisa ${l.sisa} telat ${l.telat}`).join(" · ")} → ${dendaHarap} · layar '${cell}'`;
    });
    let pen = null;
    await v.kasus(r, t, { layar: LA, isian: "[Buat Nota Denda]", masukan: "(rincian pelanggan → Buat Nota Denda)",
      harap: `Nota USULAN = ${rp(dendaHarap)}, belum berjurnal; rincian hitungan menyebut tarif & hari`, hasil: "lulus" }, async () => {
      await r.tid(`ar-aging-row-${k.pelanggan_id}`).click();
      await r.tid("ar-aging-detail-modal").waitFor();
      await r.idle(800);
      await r.tid("ar-aging-accrue").click();
      await r.tid("ar-aging-accrue-notice").waitFor({ timeout: 20000 });
      pen = mongo(`return db.penalties.find({plan_id:"${k.rencana_id}"},{_id:0}).toArray()`);
      const tot = v.r2(pen.reduce((s, p) => s + p.amount, 0));
      assert(Math.abs(tot - dendaHarap) < 0.01 && pen.every((p) => p.status === "draft"), `nota ${tot} ≠ ${dendaHarap}`);
      assert(!mongo(`return db.journal_entries.countDocuments({source_id:{$in:${JSON.stringify(pen.map((p) => p.id))}}})`), "nota usulan berjurnal");
      return `${await r.text("ar-aging-accrue-notice")} · ${pen.map((p) => `${p.number} ${p.amount} [${(p.explain || []).join(" | ")}]`).join(" ; ")}`;
    });
    await v.kasus(r, t, { layar: LR, isian: "[Terbitkan] nota denda", masukan: "(Antrean Denda → Terbitkan → konfirmasi)",
      harap: `Jurnal seimbang: piutang denda D = 4-9300 Pendapatan Denda K = ${rp(dendaHarap)}`, hasil: "lulus" }, async () => {
      await r.page.keyboard.press("Escape");
      await bukaMenu(r, "ar-aging", "payment-plans");
      await r.tid("pp-tab-denda").click();
      await r.tid("pp-filter-draft").click();
      const p = pen[0];
      await r.tid("pp-search").fill(p.number);
      await r.tid(`penalty-issue-${p.id}`).waitFor({ timeout: 15000 });
      await r.tid(`penalty-issue-${p.id}`).click();
      await r.tid("confirm-modal").waitFor();
      await r.tid("confirm-modal-confirm").click();
      await r.page.waitForFunction((id) => !document.querySelector(`[data-testid="penalty-issue-${id}"]`), p.id, { timeout: 20000 });
      const d = mongo(`return db.penalties.findOne({id:"${p.id}"},{_id:0,status:1,je_id:1,amount:1})`);
      const je = mongo(`return db.journal_entries.findOne({id:"${d.je_id}"},{_id:0,number:1,lines:1})`);
      const dr = je.lines.reduce((s, l) => s + Number(l.debit || 0), 0); const kr = je.lines.reduce((s, l) => s + Number(l.credit || 0), 0);
      assert(d.status === "issued" && Math.abs(dr - kr) < 0.01 && Math.abs(dr - p.amount) < 0.01
        && je.lines.some((l) => l.account_code === "4-9300" && Math.abs(l.credit - p.amount) < 0.01), JSON.stringify(je.lines));
      return `${je.number}: ${je.lines.map((l) => `${l.account_code} D${l.debit} K${l.credit}`).join(" · ")}`;
    });

    // ── Ubah jadwal cicilan (peserta 2) ───────────────────────────────────────────────────────────────────────────
    await r.login(akunPeserta(NO2));
    const plan0 = mongo(`return db.payment_plans.findOne({id:"${k2.rencana_id}"},{_id:0,lines:1})`);
    const total2 = v.r2(plan0.lines.reduce((s, l) => s + Number(l.amount), 0));
    const bukaUbah = async () => {
      if (await r.tid("so-payment-panel").isVisible().catch(() => false)) {   // rincian pesanan masih terbuka
        await r.tid("sop-edit").click();
        await r.tid("payment-plan-builder").waitFor();
        return;
      }
      await bukaMenu(r, "ar-aging", "payment-plans");
      await r.tid("pp-tab-jadwal").click();
      await r.tid("pp-search").fill(k2.pelanggan);
      await r.tid(`pp-open-so-${k2.rencana_id}`).click();
      await r.tid("so-open-full-detail").waitFor({ timeout: 20000 });
      await r.tid("so-open-full-detail").click();
      await r.tid("so-payment-panel").waitFor({ timeout: 20000 });
      await r.idle(800);
      await r.tid("sop-edit").click();
      await r.tid("payment-plan-builder").waitFor();
    };
    await v.kasus(r, t, { layar: LR, isian: "Ubah Jadwal · nominal cicilan 1", masukan: "1.000.000 (Σ jadwal ≠ nilai dokumen)",
      harap: "Label merah 'Selisih Rp …' (= nilai dokumen − Σ jadwal) dan [Simpan perubahan] mati", hasil: "lulus" }, async () => {
      await bukaUbah();
      await v.ketik(r, "ppb-amount-0", "1.000.000");
      await sleep(300);
      const sel = await r.text("ppb-unbalanced");
      const harap = v.r2(total2 - 1000000 - Number(plan0.lines[1].amount));
      assert(sel.includes(rp(harap).replace("Rp ", "")) && (await r.tid("ppb-save").isDisabled()), `${sel} · harap ${harap}`);
      return sel;
    });
    const c1 = 2000000; const c2 = v.r2(total2 - c1);
    const c2Teks = c2.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    await v.kasus(r, t, { layar: LR, isian: "Ubah Jadwal · nominal bergaya Indonesia", masukan: `cicilan 1 '2.000.000' · cicilan 2 '${c2Teks}'`,
      harap: "'Sudah pas'; tersimpan persis; umur piutang & taksiran denda ikut nominal baru (dihitung ulang)", hasil: "diperbaiki",
      catatan: "Dulu koma desimal di kotak nominal jadwal → 0 lalu digit berikutnya (mis. Rp 50): jadwal tidak pernah pas." }, async () => {
      await v.ketik(r, "ppb-amount-0", "2.000.000");
      await v.ketik(r, "ppb-amount-1", c2Teks);
      await sleep(300);
      await r.tid("ppb-balanced").waitFor({ timeout: 5000 });
      await r.tid("ppb-save").click();
      await r.tid("payment-plan-builder").waitFor({ state: "detached", timeout: 20000 });
      const p = mongo(`return db.payment_plans.findOne({id:"${k2.rencana_id}"},{_id:0,lines:1})`);
      assert(p.lines[0].amount === c1 && p.lines[1].amount === c2, JSON.stringify(p.lines.map((l) => l.amount)));
      const ag2 = await (await api(akunPeserta(NO2))).get("/ar/aging?entity_id=ent_ksc", KSC);
      const row = ag2.customers.find((c) => c.customer_id === k2.pelanggan_id);
      const u2 = umurHitung(k2.pelanggan_id, ag2.config.aging_buckets);
      const sp = u2.baris.reduce((s, l) => s + l.sisa, 0);
      const d2 = v.r2(u2.baris.reduce((s, l) => s + dendaHitung(l.sisa, sp, l.telat, ag2.config.penalty), 0));
      for (const key of Object.keys(u2.b)) assert(Math.abs(row[key] - u2.b[key]) < 0.01, `${key}: ${row[key]} ≠ ${u2.b[key]}`);
      assert(Math.abs(row.denda - d2) < 0.01, `denda ${row.denda} ≠ ${d2}`);
      return `jadwal ${p.lines.map((l) => l.amount).join(" + ")} · umur ${JSON.stringify(u2.b)} · denda ${d2}`;
    });
    const lampau = mongo(`return new Date(Date.now()+7*3600e3-10*86400e3).toISOString().slice(0,10)`);
    await v.kasus(r, t, { layar: LR, isian: "Ubah Jadwal · jatuh tempo cicilan 2 di MASA LAMPAU", masukan: lampau,
      harap: "Ditolak dengan pesan ATAU diterima (aturan pemilik); bila diterima: cicilan 2 langsung telat & ikut umur/denda", hasil: "keputusan",
      catatan: "Diterima tanpa peringatan: jadwal baru bisa langsung telat (denda berjalan sejak tanggal lampau). Pertanyaan pemilik: tolak/peringatkan jatuh tempo < hari ini saat mengubah jadwal?" }, async () => {
      await bukaUbah();
      await v.pilihTanggal(r, "ppb-due-1", lampau);
      await r.tid("ppb-balanced").waitFor({ timeout: 5000 });
      await r.tid("ppb-save").click();
      await sleep(1500);
      const err = await v.teksAtau(r, "ppb-error");
      const p = mongo(`return db.payment_plans.findOne({id:"${k2.rencana_id}"},{_id:0,lines:1})`);
      if (String(p.lines[1].due_date).slice(0, 10) !== lampau) return `DITOLAK: ${err}`;
      const u3 = umurHitung(k2.pelanggan_id, edges);
      return `DITERIMA: cicilan 2 jatuh tempo ${lampau} → umur ${JSON.stringify(u3.b)}`;
    });
  } catch (e) {
    r.note("berhenti: " + e.message);
  }
  t.simpan();
  await r.finish();
})();
