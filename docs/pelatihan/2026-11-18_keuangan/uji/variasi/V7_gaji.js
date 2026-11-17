// V7 — Variasi isian SETORAN GAJI & PAJAK (F15 · SDM › Penggajian › Setoran & Pajak) + hitung ulang PPh 21 TER.
//   KN_PESERTA=71 KN_PESERTA2=72 node docs/pelatihan/2026-11-18_keuangan/uji/variasi/V7_gaji.js
// Peserta 1: bayar gaji susulan, variasi format nominal setoran (tanpa simpan), lebih setor, setor PPh 21 sendiri.
// Peserta 2: gaji bersih & PPh 21 BERSEN (mis. Rp 788.116,50 / Rp 33.883,50) — dibayar & disetor dengan koma sen.
// PPh 21 dihitung ulang dari slip dengan TABEL BAWAAN aplikasi (`backend/data/pph21_bawaan.py`, BELUM diverifikasi
// terhadap lampiran PP 58/2023 — temuan PY-03 / keputusan pemilik K-42); selisih terhadap tabel peraturan dicatat.
const { Run, assert, rp, num, kartu, akunPeserta, mongo } = require("../lib");
const { REK_BCA, pilih, cekJurnal, tungguTeks, menu } = require("../hutang_lib");
const { ketik, Tabel, rpLayar } = require("./hpg_lib");

const P1 = String(process.env.KN_PESERTA || "71").padStart(2, "0");
const P2 = String(process.env.KN_PESERTA2 || "72").padStart(2, "0");
const LAYAR = "SDM › Penggajian › Setoran & Pajak";
const tabel = new Tabel("V7");
const last = (r) => r.steps[r.steps.length - 1];
const catat = (r, row) => tabel.add({ ...row, hasil: last(r).ok ? (row.hasil || "lulus") : "gagal",
  catatan: (row.catatan || "") + (last(r).ok ? "" : ` · GAGAL: ${last(r).info}`) });
const rpSen = (n) => "Rp " + Number(n).toLocaleString("id-ID", { maximumFractionDigits: 2 });
const nb = (s) => String(s || "").replace(/[  ]/g, " ");

// Tabel TER bawaan aplikasi (salinan `backend/data/pph21_bawaan.py`) — batas atas inklusif, tarif.
const TER_APP = {
  A: [[5400000, 0], [5650000, .0025], [5950000, .005], [6300000, .0075], [6750000, .01], [7500000, .0125], [8550000, .015],
    [9650000, .0175], [10750000, .02], [11250000, .025], [11600000, .03], [12500000, .035], [13750000, .04], [15100000, .045],
    [16950000, .05], [19750000, .06], [24150000, .07], [26450000, .08], [29550000, .09], [33450000, .10]],
  B: [[6200000, 0], [6500000, .0025], [6850000, .005], [7300000, .0075], [9200000, .01], [10750000, .0125], [11250000, .015],
    [11600000, .02], [12600000, .025], [13600000, .03], [14950000, .035], [16950000, .04], [19750000, .05], [24150000, .06]],
  C: [[6600000, 0], [6950000, .0025], [7350000, .005], [7800000, .0075], [8850000, .01], [9800000, .0125], [10950000, .015],
    [11200000, .0175], [12600000, .02], [13600000, .025], [14950000, .03], [16950000, .035], [19750000, .04], [24150000, .05]],
};
// TER kategori A menurut lampiran PP 58/2023 sebagaimana kami ketahui (pembanding; WAJIB dicek konsultan pajak, K-42).
const TER_PP58_A = [[5400000, 0], [5650000, .0025], [5950000, .005], [6300000, .0075], [6750000, .01], [7500000, .0125],
  [8550000, .015], [9650000, .0175], [10050000, .02], [10350000, .0225], [10700000, .025], [11050000, .03], [11600000, .035],
  [12500000, .04], [13750000, .05], [15100000, .06], [16950000, .07], [19750000, .08], [24150000, .09], [26450000, .10]];
const PTKP_TER = { TK0: "A", TK1: "A", K0: "A", TK2: "B", TK3: "B", K1: "B", K2: "B", K3: "C" };
const tarif = (tab, bruto) => (tab.find(([batas]) => bruto <= batas) || [0, NaN])[1];

async function bukaSetoran(r, no) {
  await r.login(akunPeserta(no));
  await menu(r, "hrd", "hr-payroll-hub");
  await r.tid("pay-queue").waitFor();
}

async function bayarGaji(r, runId) {
  await r.tid(`pay-queue-pay-${runId}`).click();
  await r.tid("pay-form").waitFor();
  await r.tid("pay-form-summary").waitFor({ timeout: 15000 });
  const acc = await r.text("pay-form-account");
  if (!acc.includes(REK_BCA)) await pilih(r, "pay-form-account", REK_BCA);
  const ring = await r.text("pay-form-summary");
  await r.tid("pay-form-submit").click();
  const msg = nb(await r.text("confirm-modal-message"));
  await r.tid("confirm-modal-confirm").click();
  await r.tid("pay-form").waitFor({ state: "detached", timeout: 20000 });
  await r.tid("transfer-panel").waitFor({ timeout: 10000 }).catch(() => {});
  if (await r.tid("transfer-modal-close-x").count()) {
    await r.tid("transfer-modal-close-x").click();
    await r.tid("transfer-panel").waitFor({ state: "detached" }).catch(() => {});
  }
  return { ring, msg };
}

async function bukaFormSetor(r) {
  await pilih(r, "remit-period", "Oktober 2026");
  await r.idle(600);
  await r.tid("remit-create").click();
  await r.tid("remit-form").waitFor();
  await pilih(r, "remit-form-kind", "PPh 21");
  const accSel = r.tid("remit-form-account-select");
  if (await accSel.count()) {
    const t = await accSel.innerText().catch(() => "");
    if (!t.includes(REK_BCA)) await pilih(r, "remit-form-account-select", REK_BCA);
  }
}

/** Ketik nominal setoran, klik [Catat Setoran]: → {konfirmasi} (lalu Batal bila `batal`) atau {galat} di form. */
async function cobaSetor(r, masukan, { batal = true } = {}) {
  await ketik(r, "remit-form-amount", masukan);
  const pv = nb((await r.tid("remit-form-amount-preview").innerText().catch(() => "")).trim());
  await r.tid("remit-form-submit").click();
  const res = await Promise.race([
    r.tid("confirm-modal-message").waitFor({ timeout: 6000 }).then(() => "konfirmasi"),
    r.tid("remit-form-error").waitFor({ timeout: 6000 }).then(() => "galat"),
  ]).catch(() => "diam");
  if (res === "galat") return { pv, galat: nb(await r.text("remit-form-error")) };
  if (res === "diam") return { pv, galat: "(tidak ada reaksi)" };
  const judul = nb(await r.page.locator('[data-testid="confirm-modal"] .modal-title').first().innerText().catch(() => ""));
  const msg = nb(await r.text("confirm-modal-message"));
  if (batal) {
    await r.tid("confirm-modal-cancel").click();
    await r.tid("confirm-modal-message").waitFor({ state: "detached", timeout: 6000 }).catch(() => {});
  }
  return { pv, konfirmasi: `${judul} ${msg}`.trim() };
}

function hitungPph(slipId) {
  const s = mongo(`return db.hr_payslips.findOne({id:"${slipId}"},{_id:0})`);
  const prior = mongo(`const dead=["cancelled","void","rejected"]; const runs=db.hr_payroll_runs.find({entity_id:"${s.entity_id}",period:"${s.period}",status:{$nin:dead},id:{$ne:"${s.run_id}"}},{_id:0,id:1,created_at:1}).toArray().map(x=>x.id);
    return db.hr_payslips.find({run_id:{$in:runs},employee_id:"${s.employee_id}",created_at:{$lt:"${s.created_at}"}},{_id:0,tax_gross:1,pph21:1,run_id:1}).toArray()`);
  const bruto = prior.reduce((a, x) => a + Number(x.tax_gross || 0), 0) + Number(s.tax_gross);
  const kat = PTKP_TER[s.ptkp_status];
  const t = tarif(TER_APP[kat], bruto);
  const sebulan = Math.round(bruto * t);
  const dipotong = prior.reduce((a, x) => a + Number(x.pph21 || 0), 0);
  const pph = Math.max(0, sebulan - dipotong);
  const pp58 = kat === "A" ? Math.max(0, Math.round(bruto * tarif(TER_PP58_A, bruto)) - dipotong) : null;
  return { s, prior, bruto, kat, t, sebulan, dipotong, pph, pp58 };
}

(async () => {
  const r = await new Run("V7", "Variasi isian — bayar gaji & setor PPh 21, hitung ulang TER (F15)").start();
  try {
    const g1 = kartu(P1)["d_hutang:gaji_susulan"];
    const g2 = kartu(P2)["d_hutang:gaji_susulan"];
    assert(g1 && g2, "kartu peserta belum punya d_hutang:gaji_susulan");
    const run1 = mongo(`return db.hr_payroll_runs.findOne({id:"${g1.proses_gaji_id}"},{_id:0})`);
    const run2 = mongo(`return db.hr_payroll_runs.findOne({id:"${g2.proses_gaji_id}"},{_id:0})`);
    assert(run1.status === "posted" && run2.status === "posted", `status proses ${run1.status}/${run2.status} (harus Diposting, belum dibayar)`);

    // ── Hitung ulang PPh 21 & jurnal posting ─────────────────────────────────────────────────────────────────────
    for (const [kode, run] of [["G1", run1], ["G2", run2]]) {
      await r.step(kode, "Pemeriksa", `Hitung ulang PPh 21 TER slip ${run.number}: bruto sebulan (proses sebelumnya + susulan) × tarif TER kategori PTKP − PPh yang sudah dipotong`,
        "PPh 21 slip = hitung ulang; jurnal posting: Hutang Insentif (D) = Hutang Gaji (K) + Hutang PPh 21 (K); BPJS 0 (susulan tanpa gaji pokok)", async () => {
          const slip = mongo(`return db.hr_payslips.findOne({run_id:"${run.id}"},{_id:0,id:1})`);
          const h = hitungPph(slip.id);
          assert(Math.abs(h.pph - Number(h.s.pph21)) <= 1, `PPh slip ${h.s.pph21} ≠ hitung ulang ${h.pph} (bruto ${h.bruto} × ${h.t} − ${h.dipotong})`);
          assert(Math.abs(Number(h.s.net) - (Number(h.s.gross) - Number(h.s.pph21) - Number(h.s.bpjs_emp_total || 0))) < 0.01, "bersih ≠ bruto − PPh − BPJS");
          const je = mongo(`return db.journal_entries.findOne({id:"${run.journal_id}"},{_id:0})`);
          const txt = cekJurnal(je, [["2-1600", "K", run.totals.net], ["2-1800", "K", run.totals.pph21], ["2-1500", "D", run.totals.commission]]);
          return `${h.s.employee_name} ${h.s.ptkp_status}→TER ${h.kat}: bruto sebulan ${rp(h.bruto)} (${h.prior.length} proses sebelumnya) × ${(h.t * 100).toFixed(2)}% = ${rp(h.sebulan)} − dipotong ${rp(h.dipotong)} = ${rp(h.pph)} (slip ${rp(h.s.pph21)}) · ${txt}`
            + (h.pp58 !== null && Math.abs(h.pp58 - h.pph) > 1 ? ` · MENURUT PP 58/2023 (TER A ${(tarif(TER_PP58_A, h.bruto) * 100).toFixed(2)}%): ${rp(h.pp58)} — selisih ${rp(h.pp58 - h.pph)}` : "");
        });
      catat(r, { layar: "SDM › Penggajian (slip susulan)", isian: "PPh 21 TER", masukan: `${run.number} bruto ${rp(run.totals.gross)}`,
        harap: "PPh slip = hitung ulang dengan tabel aplikasi; jurnal seimbang", hasil: /PP 58/.test(last(r).info) ? "keputusan" : "lulus",
        catatan: (last(r).info || "") + (/PP 58/.test(last(r).info) ? " — tabel TER bawaan belum diverifikasi (PY-03/K-42)" : "") });
    }

    await r.step("G3", "Pemeriksa", "Akun 2-1500 Hutang Insentif Penjualan PT Sukacita, Oktober 2026: akrual (K) vs komisi yang dilunasi slip gaji (D)",
      "Saldo 0 (akrual = Σ komisi slip semua proses Oktober)", async () => {
        const runs = mongo(`return db.hr_payroll_runs.find({entity_id:"ent_ksc",period:"2026-10",status:{$in:["posted","paying","paid"]}},{_id:0,"totals.commission":1}).toArray()`);
        const kom = runs.reduce((a, x) => a + Number((x.totals || {}).commission || 0), 0);
        const agg = mongo(`const o={}; db.journal_entries.aggregate([{$match:{entity_id:"ent_ksc",status:{$ne:"void"}}},{$unwind:"$lines"},{$match:{"lines.account_code":{$in:["2-1500","6-5000"]}}},{$group:{_id:"$lines.account_code",d:{$sum:"$lines.debit"},c:{$sum:"$lines.credit"}}}]).forEach(x=>o[x._id]=x.d-x.c); return o;`);
        assert(Math.abs(agg["2-1500"] || 0) < 1, `2-1500 bersaldo ${rp(agg["2-1500"])} (debit) — Beban Insentif 6-5000 ${rp(agg["6-5000"])} vs komisi slip ${rp(kom)} (${runs.length} proses)`);
        return `2-1500 = ${rp(agg["2-1500"] || 0)} · 6-5000 = ${rp(agg["6-5000"])} · Σ komisi slip ${rp(kom)}`;
      });
    catat(r, { layar: "Akuntansi › Buku Besar (2-1500)", isian: "akrual insentif", masukan: "proses reguler + susulan Oktober",
      harap: "Hutang Insentif nol; Beban Insentif = Σ komisi slip", hasil: "diperbaiki",
      catatan: "dulu akrual PT·periode disamakan dengan komisi proses TERAKHIR (services/posting_registry.py post_payroll) → Beban Insentif Okt kurang ±Rp 17,6 jt, 2-1500 bersaldo debit; data lama ikut terkoreksi saat proses gaji Oktober berikutnya diposting" });

    // ── Peserta 1: bayar gaji, variasi setoran ───────────────────────────────────────────────────────────────────
    await r.step("G4", "Finance", `Login peserta ${P1} → Penggajian › Setoran & Pajak → [[Bayar]] ${run1.number} → ${REK_BCA} → [[Bayar gaji]] → konfirmasi`,
      `Konfirmasi menyebut ${rpSen(run1.totals.net)}; jurnal Hutang Gaji (D) / Bank (K) = gaji bersih`, async () => {
        await bukaSetoran(r, P1);
        const o = await bayarGaji(r, run1.id);
        assert(o.msg.includes(rpSen(run1.totals.net).replace("Rp ", "")), `konfirmasi: ${o.msg}`);
        const paid = mongo(`return db.hr_payroll_runs.findOne({id:"${run1.id}"},{_id:0})`);
        const je = mongo(`return db.journal_entries.findOne({id:"${paid.paid_journal_id}"},{_id:0})`);
        const kre = je.lines.find((l) => Number(l.credit) > 0);
        return `${o.ring} · "${o.msg}" · ${cekJurnal(je, [["2-1600", "D", run1.totals.net], [kre.account_code, "K", run1.totals.net]])}`;
      });
    catat(r, { layar: LAYAR, isian: "Bayar gaji", masukan: `${run1.number} · ${REK_BCA}`, harap: "jurnal Hutang Gaji D / Bank K = bersih" });

    let sisa0 = 0;
    await r.step("G5", "Finance", "*Masa gaji* Oktober 2026 → [[Catat Setoran]] → *Jenis* PPh 21", "Form terbuka; nominal terisi sisa PPh 21 Oktober", async () => {
      await bukaFormSetor(r);
      sisa0 = num(await r.text("remit-card-pph21-sisa"));
      return `sisa PPh 21 Oktober ${await r.text("remit-card-pph21-sisa")} · nominal awal "${await r.tid("remit-form-amount").inputValue()}"`;
    });

    const kasus = [
      ["40.864,50", 40864.5], ["40864.5", 40864.5], ["40.864", 40864], ["40,864.50", 40864.5], ["Rp 40.864,50", 40864.5],
      ["0", "Nominal harus lebih dari 0."], ["", "Nominal harus lebih dari 0."],
    ];
    let n = 6;
    for (const [masukan, harap] of kasus) {
      await r.step(`G${n++}`, "Finance", `*Nominal (Rp)*: "${masukan}" → [[Catat Setoran]]`,
        typeof harap === "number" ? `Konfirmasi menyebut ${rpSen(harap)} (lalu Batal)` : `Pesan "${harap}"`, async () => {
          const o = await cobaSetor(r, masukan);
          if (typeof harap === "number") {
            assert(o.konfirmasi && o.konfirmasi.includes(rpSen(harap).replace("Rp ", "")), `"${masukan}" → ${o.konfirmasi || o.galat} (pratinjau ${o.pv})`);
            return `pratinjau ${o.pv} · ${o.konfirmasi.slice(0, 120)}`;
          }
          assert(o.galat === harap, `"${masukan}" → ${o.galat || o.konfirmasi}`);
          return o.galat;
        });
      catat(r, { layar: `${LAYAR} › Catat Setoran`, isian: "Nominal (Rp)", masukan, harap: typeof harap === "number" ? `terbaca ${rpSen(harap)}` : harap,
        hasil: /^(40.864,50|40,864.50|Rp 40.864,50|40.864)$/.test(masukan) ? "diperbaiki" : "lulus",
        catatan: masukan === "40.864" ? "dulu satu titik = desimal (Rp 40,86); kini titik + 3 angka = ribuan (MoneyInput/parseMoney)"
          : /40.864,50|40,864.50|Rp/.test(masukan) ? "dulu \"40.864,50\" diketik menjadi \"40.86450\" (Rp 40,86) — MoneyInput/parseMoney" : "" });
    }

    await r.step(`G${n++}`, "Finance", "*Nominal*: sisa PPh 21 Oktober + Rp 1.000 → [[Catat Setoran]]", "Pesan \"Nominal melebihi sisa kewajiban (Rp …)\" — tidak tersimpan", async () => {
      const lebih = (sisa0 + 1000).toLocaleString("id-ID");
      const o = await cobaSetor(r, lebih);
      assert(o.galat && /melebihi sisa kewajiban/.test(o.galat), `"${lebih}" → ${o.galat || o.konfirmasi}`);
      return `"${lebih}" → ${o.galat}`;
    });
    catat(r, { layar: `${LAYAR} › Catat Setoran`, isian: "Nominal (Rp)", masukan: "sisa + 1.000", harap: "ditolak: melebihi sisa kewajiban" });

    let setor1 = null;
    const PPH1 = Number(run1.totals.pph21);
    await r.step(`G${n++}`, "Finance", `*Nominal* "${PPH1.toLocaleString("id-ID")}" (PPh 21 proses sendiri) · *Nomor bukti setor* NTPN-V7-${P1} → [[Catat Setoran]] → [[Catat setoran]]`,
      `Setoran tersimpan ${rpSen(PPH1)}; Sisa PPh 21 turun tepat ${rpSen(PPH1)}; jurnal Hutang PPh 21 (D) / Bank (K)`, async () => {
        await ketik(r, "remit-form-amount", PPH1.toLocaleString("id-ID"));
        await r.tid("remit-form-ref").fill(`NTPN-V7-${P1}`);
        await r.tid("remit-form-submit").click();
        await r.tid("confirm-modal-confirm").click();
        await r.tid("remit-form").waitFor({ state: "detached", timeout: 20000 });
        await tungguTeks(r, "remit-msg", /tercatat/);
        await r.idle(800);
        setor1 = mongo(`return db.hr_statutory_remittances.findOne({reference:"NTPN-V7-${P1}",status:"done"},{_id:0})`);
        assert(setor1 && Math.abs(setor1.amount - PPH1) < 0.01, `DB ${setor1 && setor1.amount}`);
        const sisa = num(await r.text("remit-card-pph21-sisa"));
        assert(Math.abs(sisa0 - PPH1 - sisa) < 0.01, `sisa ${sisa0} → ${sisa}, harap ${sisa0 - PPH1}`);
        const je = mongo(`return db.journal_entries.findOne({id:"${setor1.journal_entry_id}"},{_id:0})`);
        const kre = je.lines.find((l) => Number(l.credit) > 0);
        return `${setor1.number} · sisa ${rpSen(sisa0)} → ${rpSen(sisa)} · ${cekJurnal(je, [["2-1800", "D", PPH1], [kre.account_code, "K", PPH1]])}`;
      });
    catat(r, { layar: `${LAYAR} › Catat Setoran`, isian: "Nominal (Rp)", masukan: `${PPH1.toLocaleString("id-ID")} (sebagian dari sisa)`, harap: "sisa turun tepat sebesar setoran" });

    // ── Peserta 2: nominal bersen ────────────────────────────────────────────────────────────────────────────────
    const NET2 = Number(run2.totals.net);
    const PPH2 = Number(run2.totals.pph21);
    await r.step(`G${n++}`, "Finance", `Login peserta ${P2} → [[Bayar]] ${run2.number} (bersih ${rpSen(NET2)})`,
      `Konfirmasi menyebut ${rpSen(NET2)}; jurnal Hutang Gaji (D) / Bank (K) ${rpSen(NET2)} (sen tidak hilang)`, async () => {
        await bukaSetoran(r, P2);
        const o = await bayarGaji(r, run2.id);
        const paid = mongo(`return db.hr_payroll_runs.findOne({id:"${run2.id}"},{_id:0})`);
        const je = mongo(`return db.journal_entries.findOne({id:"${paid.paid_journal_id}"},{_id:0})`);
        const kre = je.lines.find((l) => Number(l.credit) > 0);
        const txt = cekJurnal(je, [["2-1600", "D", NET2], [kre.account_code, "K", NET2]]);
        return `"${o.msg}" · ${txt}` + (o.msg.includes(rpSen(NET2).replace("Rp ", "")) ? "" : ` · KONFIRMASI MEMBULATKAN: tidak menyebut ${rpSen(NET2)}`);
      });
    catat(r, { layar: `${LAYAR} › Bayar gaji`, isian: "Bayar gaji", masukan: `${run2.number} bersih ${rpSen(NET2)}`, harap: "jurnal = bersih bersen",
      hasil: /MEMBULATKAN/.test(last(r).info) ? "keputusan" : "lulus",
      catatan: /MEMBULATKAN/.test(last(r).info) ? "jurnal benar, tetapi kalimat konfirmasi bayar gaji membulatkan sen (formatCurrency) — usul tampilkan sen" : "" });

    const PPH2T = PPH2.toLocaleString("id-ID", { minimumFractionDigits: Number.isInteger(PPH2) ? 0 : 2 });
    await r.step(`G${n++}`, "Finance", `[[Catat Setoran]] PPh 21 *Nominal* "${PPH2T}" · NTPN-V7-${P2} → simpan`,
      `Tersimpan ${rpSen(PPH2)} (sen utuh); jurnal Hutang PPh 21 (D) / Bank (K) ${rpSen(PPH2)}`, async () => {
        await bukaFormSetor(r);
        const o = await cobaSetor(r, PPH2T, { batal: false });
        assert(o.konfirmasi && o.konfirmasi.includes(rpSen(PPH2).replace("Rp ", "")), `konfirmasi ${o.konfirmasi || o.galat}`);
        await r.tid("confirm-modal-cancel").click();
        await r.tid("remit-form-ref").fill(`NTPN-V7-${P2}`);
        await r.tid("remit-form-submit").click();
        await r.tid("confirm-modal-confirm").click();
        await r.tid("remit-form").waitFor({ state: "detached", timeout: 20000 });
        await tungguTeks(r, "remit-msg", /tercatat/);
        const st = mongo(`return db.hr_statutory_remittances.findOne({reference:"NTPN-V7-${P2}",status:"done"},{_id:0})`);
        assert(st && Math.abs(st.amount - PPH2) < 0.005, `DB ${st && st.amount}`);
        const je = mongo(`return db.journal_entries.findOne({id:"${st.journal_entry_id}"},{_id:0})`);
        const kre = je.lines.find((l) => Number(l.credit) > 0);
        return `${o.konfirmasi.slice(0, 100)} · ${await r.text("remit-msg")} · ${cekJurnal(je, [["2-1800", "D", PPH2], [kre.account_code, "K", PPH2]])}`;
      });
    catat(r, { layar: `${LAYAR} › Catat Setoran`, isian: "Nominal (Rp)", masukan: PPH2T, harap: `tersimpan ${rpSen(PPH2)}`, hasil: "diperbaiki",
      catatan: "konfirmasi & kartu kini menulis sen (dulu dibulatkan: kartu \"Sisa Rp 33.884\" lalu Rp 33.884 ditolak melebihi sisa)" });
  } catch (e) {
    r.note("GALAT: " + (e && e.message ? e.message : e));
  } finally {
    tabel.simpan();
    await r.finish();
  }
})();
