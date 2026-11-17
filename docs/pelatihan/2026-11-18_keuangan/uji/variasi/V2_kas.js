// V2 — VARIASI isian Kas & Bank: Kas Kecil (F07: LPJ bernota desimal, LPJ > PD, baris salah, tanpa bukti), Transaksi Kas
// (F09: format nominal, SETIAP kategori × arah → akun lawan jurnal), Titipan Sales (F08: setoran ≠ titipan). Lewat LAYAR
// dengan akun peserta (+ manager untuk persetujuan LPJ), lalu cek BUKU (kas, jurnal, saldo rekening dihitung ulang).
//   KN_PESERTA=66 KN_PESERTA2=67 node docs/pelatihan/2026-11-18_keuangan/uji/variasi/V2_kas.js
// Butuh dua peserta segar (PD kas kecil masing-masing berstatus disetujui).
const os = require("os");
const path = require("path");
const { Run, api, assert, kartu, peserta, akunPeserta, rp, sleep, mongo } = require("../lib.js");
const kb = require("../kasbank_lib.js");
const { bersihkanHasil } = require("../piutang_lib");
const v = require("./vlib");

const NO = peserta("66");
const NO2 = String(process.env.KN_PESERTA2 || "67").padStart(2, "0");
const t = v.tabel("V2");
const LK = "Kas Kecil · LPJ";
const LT = "Transaksi Kas";

/** Saldo rekening dihitung ULANG dari transaksi kas (saldo awal + Σ masuk − Σ keluar, tidak anulir) — bukan angka layanan.
 *  Aturan tertulis (`bank_service._txns_for`): rekening TUNGGAL jenis kasnya di PT ikut menghitung kas lama tanpa rekening
 *  milik PT & jenis kas itu (Kas Toko KSC = satu-satunya rekening kas kecil KSC). */
function saldoHitung(accId) {
  return mongo(`const a=db.bank_accounts.findOne({id:"${accId}"}); let s=Number(a.opening_balance||0);
    const tunggal=db.bank_accounts.countDocuments({entity_id:a.entity_id,cash_type:a.cash_type,is_active:{$ne:false}})===1;
    const q=tunggal?{status:{$ne:"void"},$or:[{account_id:a.id},{account_id:{$in:[null,""]},entity_id:a.entity_id,cash_type:a.cash_type}]}
      :{account_id:a.id,status:{$ne:"void"}};
    db.cash_transactions.find(q).forEach(x=>{s+= (x.direction==="in"?1:-1)*Number(x.amount||0)});
    return Math.round(s*100)/100`);
}

(async () => {
  bersihkanHasil("V2");
  const r = await new Run("V2", "Variasi isian — Kas Kecil, Transaksi Kas, Titipan Sales").start();
  const k1 = kartu(NO)["c_kas:pd_kas_kecil"];
  const k2 = kartu(NO2)["c_kas:pd_kas_kecil"];
  const toast = (re) => kb.tunggu(r, "pc-toast", re);
  const bukaPd = async (k) => {
    await kb.menu(r, "petty-cash");
    await r.tid("pc-search").fill(k.pd);
    await r.tid(`pc-row-${k.pd_id}`).waitFor();
    await r.tid(`pc-open-${k.pd_id}`).click();
    await r.tid("ca-detail").waitFor();
    await r.idle(300);
  };
  const cairkan = async (k) => {
    await bukaPd(k);
    await r.tid("ca-disburse-btn").click();
    await r.tid("ca-disburse-modal").waitFor();
    await r.tid("ca-disburse-account-sole").waitFor();
    await r.tid("ca-disburse-confirm").click();
    await kb.konfirmasi(r, "ca-disburse-money-confirm");
    await toast(`${k.pd} dicairkan`);
    await r.idle(300);
  };
  /** Isi form LPJ: baris [uraian, kategori, nominal-diketik]. */
  const isiLpj = async (baris) => {
    await r.tid("pc-settle-btn").click();
    await r.tid("stl-form").waitFor();
    for (let i = 0; i < baris.length; i++) {
      if (i > 0) await r.tid("stl-add-line").click();
      await r.tid(`stl-line-desc-${i}`).fill(baris[i][0]);
      await kb.pilih(r, `stl-line-cat-${i}`, baris[i][1]);
      if (baris[i][2] !== "") await v.ketik(r, `stl-line-amount-${i}`, baris[i][2]);
    }
    await r.tid("stl-divisi").fill("Penjualan");
    await sleep(300);
  };
  const tutupForm = async () => {
    if (await r.tid("stl-form").count()) { await r.tid("stl-form").getByRole("button", { name: "Batal" }).click(); await r.idle(200); }
    if (await r.tid("pc-detail-modal").count()) { await r.tid("pc-detail-modal-close-x").click(); await r.idle(200); }
  };

  try {
    assert(k1 && k2, `Kartu peserta ${NO}/${NO2} belum punya c_kas:pd_kas_kecil`);
    const kasToko = await kb.rekening(akunPeserta(NO), "Kas Toko KSC");
    await r.login(akunPeserta(NO));

    // ── A. LPJ bernota desimal → disetujui → sisa diterima ───────────────────────────────────────────────────────
    const N1 = 185000.5; const N2 = 47000; const PAKAI = N1 + N2; const SISA = v.r2(k1.nominal - PAKAI);
    let stl = null;
    await v.kasus(r, t, { layar: LK, isian: "Nominal baris LPJ", masukan: "185.000,50 dan 47.000 (dua nota)",
      harap: `Total Pengeluaran Rp 232.001 (232.000,50); Sisa ${rp(SISA)}; LPJ tersimpan persis 232.000,50`, hasil: "diperbaiki",
      catatan: "Dulu '185.000,50' diketik → '185.00050' / koma membuat Number() = NaN → baris DIBUANG diam-diam saat simpan." }, async () => {
      await cairkan(k1);
      await isiLpj([["Bensin & tol (nota SPBU)", "transportasi", "185.000,50"], ["Fotokopi & materai", "fotocopy_printing_jilid_materai", "47.000"]]);
      assert((await kb.teks(r, "stl-total-pengeluaran")) === "Rp 232.001", `total ${await kb.teks(r, "stl-total-pengeluaran")}`);
      assert((await kb.teks(r, "stl-sisa")) === rp(SISA), `sisa ${await kb.teks(r, "stl-sisa")}`);
      await r.tid("stl-submit").click();
      await r.tid("stl-form").waitFor({ state: "hidden" });
      await toast(/STL-\d+ disimpan/);
      stl = mongo(`return db.cash_advance_settlements.findOne({cash_advance_id:"${k1.pd_id}",status:{$ne:"rejected"}},{_id:0})`);
      assert(stl && stl.total_pengeluaran === PAKAI && stl.expense_lines.map((l) => l.amount).join() === `${N1},${N2}`,
        `LPJ ${JSON.stringify(stl && stl.expense_lines.map((l) => l.amount))}`);
      return `${stl.number} · total ${stl.total_pengeluaran} · sisa ${stl.sisa_kurang_dana}`;
    });
    await v.kasus(r, t, { layar: LK, isian: "Tombol [Ajukan] tanpa foto nota", masukan: "(tidak ada lampiran)",
      harap: "Pengaturan 'finance.lpj_wajib_lampiran' MENYALA → ditolak 'Lampirkan minimal satu bukti …'; MATI (bawaan) → LPJ terajukan tanpa bukti",
      hasil: "keputusan", catatan: "Di lingkungan uji pengaturan MATI (bawaan): LPJ bisa diajukan TANPA foto nota. Pertanyaan pemilik: nyalakan wajib bukti LPJ untuk PT? (F07 mengajarkan unggah bukti, tetapi sistem tidak memaksanya.) Bila menyala, penolakannya berbahasa Indonesia (pesan di atas, `cash_advance_service.submit_settlement`)." }, async () => {
      await r.tid("stl-detail").waitFor();
      await r.tid("stl-submit-btn").click();
      await r.page.waitForFunction((n) => /diajukan/.test(document.querySelector('[data-testid="pc-toast"]')?.innerText || "")
        || !!document.querySelector('[data-testid="stl-detail-error"]'), stl.number, { timeout: 15000 });
      if (await r.tid("stl-detail-error").count()) {
        const e = (await r.tid("stl-detail-error").innerText()).trim();
        assert(/Lampirkan minimal satu bukti/.test(e) && (await kb.teks(r, "stl-detail-status")) === "Draf", e);
        return `MENYALA → ${e}`;
      }
      assert((await kb.teks(r, "stl-detail-status")) === "Diajukan", "status");
      return "MATI → LPJ diajukan tanpa lampiran";
    });
    await v.kasus(r, t, { layar: LK, isian: "LPJ disetujui manajer → jurnal", masukan: "lampirkan nota → Ajukan → manager Setujui & Posting GL",
      harap: `Jurnal: 6-4600 D 185.000,50 · 6-4300 D 47.000 · 1-1400 K 232.000,50 (seimbang)`, hasil: "lulus", peran: "Finance + Manajer" }, async () => {
      if (await r.tid("stl-submit-btn").count()) {     // pengaturan wajib bukti menyala → lampirkan dulu
        const nota = path.join(os.tmpdir(), `nota-variasi-${NO}.png`);
        await r.page.screenshot({ path: nota, clip: { x: 0, y: 0, width: 200, height: 120 } });
        await r.tid("stl-attach-input").setInputFiles(nota);
        await toast(/dilampirkan/);
        await r.tid("stl-submit-btn").click();
        await toast(`${stl.number} diajukan`);
      }
      await r.login("manager");
      await bukaPd(k1);
      await r.tid("stl-approve-btn").click();
      await kb.konfirmasi(r, "stl-approve-confirm");
      await toast(`${stl.number} disetujui`);
      const je = kb.seimbang(kb.jurnal("petty_cash_settlement", stl.id), "jurnal LPJ");
      assert(kb.adaBaris(je, "6-4600", "D", N1) && kb.adaBaris(je, "6-4300", "D", N2) && kb.adaBaris(je, "1-1400", "K", PAKAI), kb.teksJurnal(je));
      return kb.teksJurnal(je);
    });
    await v.kasus(r, t, { layar: LK, isian: "Terima pengembalian sisa (nominal sen)", masukan: `sisa ${rp(SISA)} (267.999,50)`,
      harap: "Kas masuk persis 267.999,50; uang muka PD bersih 0; saldo Kas Toko = hitung ulang (saldo awal + Σ masuk − Σ keluar)", hasil: "lulus" }, async () => {
      await r.login(akunPeserta(NO));
      await bukaPd(k1);
      await r.tid("stl-return-btn").click();
      await r.tid("stl-return-modal").waitFor();
      await r.tid("stl-return-modal-account-sole").waitFor();
      await r.tid("stl-return-modal-submit").click();
      const msg = await kb.konfirmasi(r, "stl-return-confirm");
      await toast(`Sisa uang muka ${stl.number} diterima`);
      const s = mongo(`return db.cash_advance_settlements.findOne({id:"${stl.id}"},{_id:0,sisa_dikembalikan:1})`);
      const kas = kb.kas(s.sisa_dikembalikan.cash_txn_id);
      assert(kas.direction === "in" && kas.amount === SISA, `kas sisa ${kas.amount}`);
      const ca = mongo(`return db.cash_advances.findOne({id:"${k1.pd_id}"},{_id:0,disbursement:1})`);
      const ids = [ca.disbursement.cash_txn_id, stl.id, kas.id];
      const net = mongo(`let n=0; db.journal_entries.find({source_id:{$in:${JSON.stringify(ids)}},status:{$ne:"void"}}).forEach(j=>j.lines.forEach(l=>{if(l.account_code==="1-1400") n+=(l.debit||0)-(l.credit||0);})); return Math.round(n*100)/100;`);
      assert(Math.abs(net) < 0.01, `uang muka PD bersih ${net}`);
      const api1 = (await kb.rekening(akunPeserta(NO), "Kas Toko KSC")).balance;
      const hit = saldoHitung(kasToko.id);
      assert(Math.abs(api1 - hit) < 0.01, `saldo layar ${api1} ≠ hitung ulang ${hit}`);
      return `${msg.slice(0, 90)} · uang muka bersih ${net} · saldo Kas Toko ${rp(hit)} (hitung ulang = layar)`;
    });
    await tutupForm();

    // ── B. LPJ peserta kedua: baris salah, uraian kosong, LPJ > PD ──────────────────────────────────────────────────
    await r.login(akunPeserta(NO2));
    await v.kasus(r, t, { layar: LK, isian: "Nominal baris LPJ", masukan: "baris 2 diketik -5.000",
      harap: "Ditolak: 'Periksa baris 2: nominal tidak boleh minus.'; tidak ada LPJ", hasil: "diperbaiki",
      catatan: "Dulu baris minus dibuang diam-diam saat simpan, padahal Total di layar ikut dikurangi (tersimpan ≠ terlihat)." }, async () => {
      await cairkan(k2);
      await isiLpj([["Bensin", "transportasi", "100.000"], ["Koreksi", "transportasi", "-5.000"]]);
      await r.tid("stl-submit").click();
      const e = await kb.teks(r, "stl-form-error");
      assert(/baris 2: nominal tidak boleh minus/.test(e), e);
      assert(!mongo(`return db.cash_advance_settlements.countDocuments({cash_advance_id:"${k2.pd_id}"})`), "LPJ tersimpan");
      return e;
    });
    await v.kasus(r, t, { layar: LK, isian: "Baris beruraian tanpa nominal", masukan: "baris 2 'Parkir' nominal kosong",
      harap: "Ditolak: 'Periksa baris 2: isi nominalnya atau hapus barisnya.'", hasil: "diperbaiki",
      catatan: "Dulu baris dibuang diam-diam." }, async () => {
      await v.ketik(r, "stl-line-amount-1", "");
      await r.tid("stl-line-desc-1").fill("Parkir");
      await r.tid("stl-submit").click();
      await sleep(300);
      const e = await kb.teks(r, "stl-form-error");
      assert(/baris 2: isi nominalnya/.test(e), e);
      return e;
    });
    let stl2 = null;
    await v.kasus(r, t, { layar: LK, isian: "LPJ melebihi PD + uraian kosong", masukan: "baris 1 (uraian kosong) 400.000 · baris 2 'Parkir' 150.000,00 (Σ 550.000 > PD 500.000)",
      harap: "Form: 'Kekurangan Dana Rp 50.000'; daftar manajer: 'Perkiraan hutang reimburse Rp 50.000' + tombol [Buka]; disetujui → jurnal beban D 550.000 = 1-1400 K 500.000 + 2-1650 Hutang Reimburse K 50.000",
      hasil: "keputusan", catatan: "Uraian kosong DITERIMA (tidak wajib) — pertanyaan pemilik: wajibkan uraian per nota? DIPERBAIKI: dulu baris PD di daftar menampilkan 'Hutang reimburse Rp 50.000' + tombol [Bayar] (ditolak server) MENGGANTIKAN [Buka] sebelum LPJ disetujui → manajer tidak bisa membuka PD dari barisnya.",
      peran: "Finance + Manajer" }, async () => {
      await r.tid("stl-line-desc-0").fill("");
      await v.ketik(r, "stl-line-amount-0", "400.000");
      await v.ketik(r, "stl-line-amount-1", "150.000,00");
      await sleep(300);
      const sisaTeks = await kb.teks(r, "stl-sisa");
      assert(sisaTeks === "Rp 50.000" && (await kb.isi(r.tid("stl-form"))).includes("Kekurangan Dana"), `ringkasan ${sisaTeks}`);
      await r.tid("stl-submit").click();
      await r.tid("stl-form").waitFor({ state: "hidden" });
      await toast(/STL-\d+ disimpan/);
      stl2 = mongo(`return db.cash_advance_settlements.findOne({cash_advance_id:"${k2.pd_id}",status:{$ne:"rejected"}},{_id:0})`);
      assert(stl2.total_pengeluaran === 550000 && stl2.sisa_kurang_dana === -50000, JSON.stringify(stl2 && stl2.sisa_kurang_dana));
      const sisaBaris = await kb.teks(r, `pc-sisa-${k2.pd_id}`).catch(() => "");
      const nota = path.join(os.tmpdir(), `nota-variasi-${NO2}.png`);
      await r.page.screenshot({ path: nota, clip: { x: 0, y: 0, width: 200, height: 120 } });
      await r.tid("stl-attach-input").setInputFiles(nota);
      await toast(/dilampirkan/);
      await r.tid("stl-submit-btn").click();
      await toast(`${stl2.number} diajukan`);
      await r.login("manager");
      await kb.menu(r, "petty-cash");
      await r.tid("pc-search").fill(k2.pd);
      await r.tid(`pc-row-${k2.pd_id}`).waitFor();
      const baris = await kb.isi(r.tid(`pc-row-${k2.pd_id}`));
      assert(/Perkiraan hutang reimburse/.test(baris) && !(await r.tid(`pc-pay-${k2.pd_id}`).count()), `baris manajer: ${baris}`);
      await bukaPd(k2);
      await r.tid("stl-approve-btn").click();
      await kb.konfirmasi(r, "stl-approve-confirm");
      await toast(`${stl2.number} disetujui`);
      const je = kb.seimbang(kb.jurnal("petty_cash_settlement", stl2.id), "jurnal LPJ > PD");
      const beban = je.lines.filter((l) => /^6-/.test(l.account_code)).reduce((s, l) => s + Number(l.debit || 0), 0);
      assert(Math.abs(beban - 550000) < 0.01 && kb.adaBaris(je, "1-1400", "K", 500000) && kb.adaBaris(je, "2-1650", "K", 50000), kb.teksJurnal(je));
      return `${stl2.number} · ${kb.teksJurnal(je)}`;
    });
    await tutupForm();

    // ── C. Transaksi Kas: format nominal + setiap kategori × arah → akun lawan ──────────────────────────────────────
    await r.login(akunPeserta(NO));
    const bukaKas = async () => {
      if (await r.tid("cash-form").count()) return;
      await kb.menu(r, "cash-management");
      await r.tid("create-cash-button").click();
      await r.tid("cash-form").waitFor();
    };
    const catat = async ({ arah, kategori, nominal, ket }) => {
      await bukaKas();
      await kb.pilih(r, "cash-type-select", "kas_kecil");
      await kb.pilih(r, "cash-direction-select", arah);
      await v.ketik(r, "cash-amount-input", nominal);
      await kb.pilih(r, "cash-category-select", kategori);
      await r.tid("cash-account-sole").waitFor();
      await r.tid("cash-description-input").fill(ket);
      await sleep(300);
      await r.tid("submit-cash-button").click();
    };
    const AKUN = { operasional: ["6-4000", "1-9999"], pembelian: ["1-1300", "1-9999"], gaji: ["6-1000", "1-9999"],
      transfer: ["1-1150", "1-1150"], modal: ["6-4000", "3-1000"], lain: ["6-4000", "1-9999"] };
    const KET = { operasional: "", pembelian: "Kas keluar 'Pembelian' mendebit 1-1300 Persediaan tanpa barang masuk (persediaan buku ≠ stok) — pertanyaan pemilik.",
      gaji: "", transfer: "Lewat 1-1150 Kas Transit (perbaikan 17 Nov).", modal: "Keluar 'Setoran Modal' (prive/penarikan) jatuh ke 6-4000 BEBAN — seharusnya ekuitas; pertanyaan pemilik.",
      lain: "Masuk 'Lain-lain' → 1-9999 Suspense (pertanyaan pemilik yang sudah tercatat)." };
    const FORMAT = ["12.345,50", "12345", "Rp 1.250", "1,500,000", "2.000", "3.374.122,50"];
    let i = 0;
    for (const kategori of Object.keys(AKUN)) {
      for (const arah of ["out", "in"]) {
        const nominal = FORMAT[i % FORMAT.length]; i++;
        const n = { "12.345,50": 12345.5, "12345": 12345, "Rp 1.250": 1250, "1,500,000": 1500000, "2.000": 2000, "3.374.122,50": 3374122.5 }[nominal];
        const akun = AKUN[kategori][arah === "out" ? 0 : 1];
        const ragu = (kategori === "modal" && arah === "out") || (kategori === "pembelian" && arah === "out")
          || (arah === "in" && ["operasional", "pembelian", "gaji", "lain"].includes(kategori));
        await v.kasus(r, t, { layar: LT, isian: `Kategori ${kategori} · ${arah === "out" ? "Keluar" : "Masuk"} · Nominal`, masukan: nominal,
          harap: `Kas tersimpan persis ${n}; jurnal ${arah === "out" ? `${akun} D / 1-1110 K` : `1-1110 D / ${akun} K`}`,
          hasil: ragu ? "keputusan" : (/[.,]/.test(nominal) ? "diperbaiki" : "lulus"),
          catatan: [/[.,]/.test(nominal) ? "Nominal bertitik/koma dulu terbaca salah (mis. '12.345,50' → NaN/12,35)." : "",
            arah === "in" && kategori !== "transfer" && kategori !== "modal" ? `Masuk '${kategori}' → 1-9999 Suspense (tidak ada kata kunci) — perlu reklas manual.` : "",
            arah === "out" ? KET[kategori] : (kategori === "lain" ? KET.lain : "")].filter(Boolean).join(" ") }, async () => {
          const ket = `Variasi ${kategori} ${arah} — Latihan ${NO}`;
          await catat({ arah, kategori, nominal, ket });
          const msg = await kb.tunggu(r, "cash-notice", /Transaksi KSC\/CASH-\d+/);
          const nomor = msg.match(/KSC\/CASH-\d+/)[0];
          const tx = mongo(`return db.cash_transactions.findOne({number:"${nomor}",entity_id:"ent_ksc"},{_id:0})`);
          assert(tx.amount === n && tx.direction === arah && tx.account_id === kasToko.id, `kas ${tx.amount} ${tx.direction}`);
          const je = kb.seimbang(kb.jurnal("cash_transaction", tx.id), "jurnal kas");
          const ok = arah === "out" ? kb.adaBaris(je, akun, "D", n) && kb.adaBaris(je, "1-1110", "K", n)
            : kb.adaBaris(je, "1-1110", "D", n) && kb.adaBaris(je, akun, "K", n);
          assert(ok, kb.teksJurnal(je));
          return kb.teksJurnal(je);
        });
      }
    }
    for (const [mas, harap] of [["-100", "Nominal harus lebih dari 0."], ["abc", "Nominal harus lebih dari 0."], ["0", "Nominal harus lebih dari 0."]]) {
      await v.kasus(r, t, { layar: LT, isian: "Nominal", masukan: mas, harap: `Pesan di dalam pop-up: '${harap}'; tidak ada transaksi`, hasil: "lulus" }, async () => {
        const n0 = mongo(`return db.cash_transactions.countDocuments({account_id:"${kasToko.id}"})`);
        await catat({ arah: "out", kategori: "operasional", nominal: mas, ket: `Variasi salah — Latihan ${NO}` });
        const e = await kb.teks(r, "cash-form-error");
        assert(e.includes(harap), e);
        assert(mongo(`return db.cash_transactions.countDocuments({account_id:"${kasToko.id}"})`) === n0, "transaksi tercatat");
        return e;
      });
    }
    await v.kasus(r, t, { layar: LT, isian: "Kas keluar MELEBIHI saldo Kas Toko", masukan: "saldo + 1.000.000",
      harap: "Ditolak 'saldo tidak cukup' ATAU tercatat (aturan pemilik)", hasil: "keputusan",
      catatan: "Tidak ada penjaga saldo: kas kecil boleh MINUS. Pertanyaan pemilik: tolak kas keluar di atas saldo? (transaksi uji dianulir admin sesudahnya)" }, async () => {
      const saldo = saldoHitung(kasToko.id);
      const keluar = Math.round(saldo + 1000000);
      await catat({ arah: "out", kategori: "operasional", nominal: keluar.toLocaleString("id-ID"), ket: `Variasi melebihi saldo — Latihan ${NO}` });
      const msg = await kb.tunggu(r, "cash-notice", /Transaksi KSC\/CASH-\d+/).catch(async () => `DITOLAK: ${await kb.teks(r, "cash-form-error")}`);
      let info = msg;
      const m = msg.match(/KSC\/CASH-\d+/);
      if (m) {
        const tx = mongo(`return db.cash_transactions.findOne({number:"${m[0]}",entity_id:"ent_ksc"},{_id:0,id:1,amount:1})`);
        info = `TERCATAT ${m[0]} ${rp(tx.amount)} → saldo Kas Toko ${rp(saldoHitung(kasToko.id))}`;
        const adm = await api("admin");
        await adm.post(`/cash-transactions/${tx.id}/void`, { reason: "Uji variasi: kas keluar melebihi saldo (dianulir)" }, kb.KSC);
        info += ` · dianulir admin → saldo ${rp(saldoHitung(kasToko.id))}`;
      }
      return info;
    });
    const akhir = (await kb.rekening(akunPeserta(NO), "Kas Toko KSC")).balance;
    await v.kasus(r, t, { layar: "Rekening & Saldo", isian: "Saldo Kas Toko KSC", masukan: "(hitung ulang sesudah semua transaksi)",
      harap: "Saldo di layar = saldo awal + Σ kas masuk − Σ kas keluar (tidak anulir)", hasil: "lulus" }, async () => {
      await kb.menu(r, "bank-accounts");
      const card = await kb.isi(r.tid(`bank-card-${kasToko.id}`));
      const hit = saldoHitung(kasToko.id);
      assert(Math.abs(akhir - hit) < 0.01 && card.includes(rp(hit).replace("Rp ", "")), `kartu ${card} · api ${akhir} · hitung ${hit}`);
      return `${rp(hit)} · ${card.slice(0, 80)}`;
    });

    // ── D. Titipan Sales: setoran ≠ titipan ───────────────────────────────────────────────────────────────────────
    const k3 = kartu(NO)["c_kas:titipan_sales"];
    await v.kasus(r, t, { layar: "Titipan Sales", isian: "Jumlah setoran saat diterima Finance", masukan: "(tidak bisa diubah di layar)",
      harap: "Form 'Terima setoran' menampilkan Jumlah = setoran (teks, bukan isian) — Finance tidak bisa menerima nominal lain", hasil: "lulus",
      catatan: "Selisih fisik uang harus ditolak ([Tolak] + alasan) lalu sales mengajukan setoran baru." }, async () => {
      await kb.menu(r, "cash-holdings");
      await r.tid(`cth-receive-${k3.setoran_id}`).click();
      await r.tid("cth-receive-form").waitFor();
      const jml = await kb.teks(r, "cth-receive-amount");
      const isian = await r.tid("cth-receive-form").locator("input[inputmode=decimal]").count();
      assert(jml === rp(k3.nominal) && isian === 0, `jumlah ${jml} · isian nominal ${isian}`);
      await r.tid("cth-receive-form").getByRole("button", { name: "Batal" }).click();
      return `Jumlah ${jml} (teks)`;
    });
    await v.kasus(r, t, { layar: "Titipan Sales (HP sales)", isian: "Jumlah disetor", masukan: "titipan + 1.000.000 (lewat API akun sales)",
      harap: "Ditolak dengan pesan Indonesia (melebihi titipan yang dipegang)", hasil: "lulus", peran: "Sales" }, async () => {
      const s = await api("sales");
      try {
        await s.post("/cash-deposits", { amount: k3.nominal + 1000000, note: "uji variasi", entity_id: kb.KSC }, kb.KSC);
        throw new Error("setoran berlebih DITERIMA");
      } catch (e) {
        assert(e.status === 400 || e.status === 409, e.message);
        return e.message.replace(/^.*→ /, "");
      }
    });
  } catch (e) {
    r.note("berhenti: " + e.message);
  }
  t.simpan();
  await r.finish();
})();
