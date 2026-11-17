// K04 — Rekening kas & bank: peserta (Finance, izin kelola rekening) membuat rekening bank dengan saldo awal, melihat
// jurnal yang lahir (Kas Besar / Bank (D) · Ekuitas Saldo Awal (K)) dan kartunya di Kas & Bank › Rekening & Saldo.
// Sesudah latihan pelatih membersihkan: saldo awal dinolkan (jurnal penyesuaian) lalu rekening dinonaktifkan — saldo
// buku besar Sukacita kembali seperti semula (dibuktikan).
//   node docs/pelatihan/2026-11-18_keuangan/uji/konfigurasi/K04_rekening_kas_bank.js     (bawaan peserta 11)
const { api, assert, peserta, akunPeserta, mongo, rp, num } = require("../lib");
const k = require("./konfig_lib");

const SALDO = 1000000;
const saldoAkun = (kode) => mongo(`let s=0; db.journal_entries.find({entity_id:"${k.KSC}",status:{$ne:"void"},"lines.account_code":"${kode}"},{lines:1})
  .forEach(j=>j.lines.forEach(l=>{ if(l.account_code==="${kode}") s+= (l.debit||0)-(l.credit||0); })); return Math.round(s*100)/100;`);

(async () => {
  const no = peserta("11");
  const nama = `Rekening Latihan ${no}`;
  const r = await k.mulai("K04", "Rekening kas & bank");
  const fin = await api(akunPeserta(no));
  const ada = mongo(`return db.bank_accounts.findOne({entity_id:"${k.KSC}",name:${JSON.stringify(nama)},is_active:{$ne:false}},{_id:0,id:1})`);
  if (ada) await fin.patch(`/bank-accounts/${ada.id}`, { opening_balance: 0, is_active: false, reason: "Bersihkan sisa uji K04" });
  const awal = { kas: saldoAkun("1-1100"), ekuitas: saldoAkun("3-2900"),
    aktif: mongo(`return db.bank_accounts.countDocuments({entity_id:"${k.KSC}",is_active:{$ne:false}})`) };
  k.simpanJson(r, "sebelum.json", awal);
  r.note(`Sebelum: 1-1100 ${rp(awal.kas)} · 3-2900 ${rp(awal.ekuitas)} · rekening aktif ${awal.aktif}`);
  let acc = null;
  let kpi0 = {};

  try {
    await r.step(1, "Finance", "Masuk dengan akun peserta → menu Keuangan › Kas & Bank (tab Rekening & Saldo)",
      "Lima kartu: Kas & Bank (buku besar) · Total Saldo Rekening · Saldo Bank · Saldo Kas · Mutasi Belum Dicocokkan; lalu kartu per rekening", async () => {
        await r.login(akunPeserta(no));
        await r.tid("finance-desk").waitFor();
        await k.menuPotret(r, "keuangan", "cash-bank", "menu-kas-bank");
        await r.tid("bank-accounts-view").waitFor();
        await r.tid("bank-cards").waitFor();
        await r.idle(800);
        for (const x of ["gl", "total", "bank", "cash"]) kpi0[x] = num(await r.text(`bank-kpi-${x}-value`));
        await k.potret(r, r.tid("bank-add-toggle"), "rekening-dan-saldo");
        return `buku besar ${rp(kpi0.gl)} · total rekening ${rp(kpi0.total)} · bank ${rp(kpi0.bank)} · kas ${rp(kpi0.cash)}`;
      });

    await r.step(2, "Finance", `Klik [[Tambah Akun]] → isi rekening bank '${nama}' dengan saldo awal Rp 1.000.000; *Dipakai untuk* hanya Operasional`,
      "Form 'Tambah Akun Kas / Bank' untuk PT Sukacita: 1 Identitas rekening (nama, jenis, bank, nomor, atas nama, saldo awal), 2 Dipakai untuk, 3 Cara bayar, 4 Catatan untuk penyetuju", async () => {
        await r.tid("bank-add-toggle").click();
        await r.tid("bank-add-form").waitFor();
        await r.tid("bank-form-name").fill(nama);
        await r.tid("bank-form-bankname").fill("Bank Mandiri");
        await r.tid("bank-form-accountno").fill(`13000000${no}`);
        await r.tid("bank-form-holder").fill("Sukacita Textile");
        await r.tid("bank-form-opening").fill(String(SALDO));
        for (const p of ["penerimaan_pelanggan", "pembayaran_pemasok", "gaji"]) {
          const c = r.tid(`bank-form-purpose-${p}`);
          if (await c.isChecked()) await c.uncheck();
        }
        assert(await r.tid("bank-form-purpose-operasional").isChecked(), "Operasional tidak tercentang");
        const sub = (await r.tid("bank-add-form").innerText()).replace(/\s+/g, " ");
        assert(/Sukacita/.test(sub), "form tidak menyebut PT Sukacita");
        await r.shot("form-tambah-rekening");
        await k.potret(r, r.tid("bank-form-submit"), "form-tambah-rekening-simpan", { full: false });
        return `saldo awal ${await r.text("bank-form-opening-preview").catch(() => rp(SALDO))}`;
      });

    await r.step(3, "Finance", "Klik [[Simpan Akun]]",
      `Pesan 'Akun kas/bank ditambahkan.'; kartu '${nama}' (Bank Mandiri · nomor) bersaldo Rp 1.000.000; kartu Total Saldo Rekening dan Kas & Bank (buku besar) naik Rp 1.000.000`, async () => {
        await r.tid("bank-form-submit").click();
        await r.tid("bank-add-form").waitFor({ state: "detached", timeout: 20000 });
        const notice = await k.tungguTeks(r, "bank-notice", /ditambahkan|pengajuan/);
        assert(/ditambahkan/.test(notice), `rekening butuh persetujuan orang kedua: ${notice}`);
        acc = mongo(`return db.bank_accounts.findOne({entity_id:"${k.KSC}",name:${JSON.stringify(nama)},is_active:{$ne:false}},{_id:0})`);
        assert(acc && acc.opening_balance === SALDO && acc.account_type === "bank", `DB rekening: ${JSON.stringify(acc)}`);
        assert(JSON.stringify(acc.purposes) === JSON.stringify(["operasional"]), `peruntukan ${acc.purposes}`);
        const card = r.tid(`bank-card-${acc.id}`);
        await card.waitFor();
        assert(num(await card.innerText().then((t) => (t.match(/Rp\s?[\d.]+/) || [""])[0])) === SALDO, "kartu rekening bukan Rp 1.000.000");
        // Kelas berjalan bersama (peserta lain membayar dari BCA): total dicocokkan dengan jumlah saldo rekening saat itu
        // (API), bukan dengan angka langkah 1.
        const totalApi = async () => Math.round((await fin.get("/bank-accounts")).filter((a) => a.entity_id === k.KSC)
          .reduce((x, a) => x + Number(a.balance || 0), 0));
        await k.tunggu(async () => {
          await r.tid("bank-refresh").click(); await r.idle(500);
          const t = num(await r.text("bank-kpi-total-value"));
          return Math.abs(t - (await totalApi())) < 1;
        }, "Total Saldo Rekening tidak sama dengan jumlah saldo rekening");
        await k.potret(r, card, "rekening-baru");
        return `${notice} · ${acc.name} · ${acc.bank_name} ${acc.account_number} · total rekening ${await r.text("bank-kpi-total-value")}`;
      });

    await r.step(4, "Finance", "Cek buku: Akuntansi & Pajak › Buku Besar → ketik nama rekening di kotak cari → klik jurnal 'Saldo awal rekening …'",
      "Jurnal saldo awal: 1-1100 Kas Besar / Bank (D) Rp 1.000.000 · 3-2900 Ekuitas Saldo Awal (K) Rp 1.000.000 — seimbang", async () => {
        const je = mongo(`return db.journal_entries.findOne({source_type:"bank_opening_balance",source_id:"${acc.id}"},{_id:0})`);
        const txt = k.cekJurnal(je, [["1-1100", "D", SALDO], ["3-2900", "K", SALDO]]);
        await k.menuPotret(r, "akuntansi", "ledger", "menu-buku-besar");
        await r.tid("gl-view").waitFor();
        await r.tid("gl-journal-search").fill(nama);
        await r.idle(1200);
        const row = r.tid(`gl-journal-row-${je.id}`);
        await row.waitFor({ timeout: 15000 });
        await k.klikPotret(r, row, "cari-jurnal-saldo-awal");
        await r.tid("gl-journal-detail").waitFor();
        await r.idle(400);
        const det = (await r.tid("gl-journal-detail").innerText()).replace(/\s+/g, " ");
        assert(det.includes("1-1100") && det.includes("3-2900"), `rincian jurnal: ${det.slice(0, 200)}`);
        await r.shot("jurnal-saldo-awal");
        await r.page.keyboard.press("Escape");
        assert(Math.round(saldoAkun("1-1100") - awal.kas) === SALDO, "saldo 1-1100 tidak naik Rp 1.000.000");
        return txt;
      });

    await r.step(5, "Finance", `Kembali ke Kas & Bank › Rekening & Saldo → klik kartu '${nama}'`,
      "Pop-up mutasi rekening: belum ada transaksi; saldo kartu = saldo awal. Rekening ini hanya ditawarkan di layar Operasional (tidak muncul di pilihan rekening penerimaan pelanggan)", async () => {
        await k.menuPotret(r, "keuangan", "cash-bank", "menu-kas-bank-2");
        await r.tid(`bank-card-${acc.id}`).click();
        await r.tid("bank-ledger").waitFor();
        await r.idle(800);
        const t = (await r.tid("bank-ledger").innerText()).replace(/\s+/g, " ");
        await r.shot("mutasi-rekening-baru");
        await r.tid("bank-ledger-close").click();
        const penerima = await fin.get(`/bank-accounts/receiving?entity_id=${k.KSC}`).catch(() => null);
        const muncul = Array.isArray(penerima) && penerima.some((x) => x.id === acc.id);
        assert(!muncul, "rekening operasional ikut ditawarkan sebagai rekening penerimaan pelanggan");
        return `${t.slice(0, 160)}${penerima ? " · tidak ada di daftar rekening penerima" : ""}`;
      });
  } finally {
    await r.step(6, "Pelatih", "Sesudah kelas: nolkan saldo awal rekening latihan lalu nonaktifkan (Ubah rekening › hapus centang Aktif)",
      "Jurnal penyesuaian 3-2900 (D) / 1-1100 (K) Rp 1.000.000; rekening nonaktif; efek bersih rekening latihan di buku = nol, jumlah rekening aktif sama dengan sebelum latihan", async () => {
        acc = acc || mongo(`return db.bank_accounts.findOne({entity_id:"${k.KSC}",name:${JSON.stringify(nama)},is_active:{$ne:false}},{_id:0})`);
        if (acc) await fin.patch(`/bank-accounts/${acc.id}`, { opening_balance: 0, is_active: false, reason: "Selesai latihan K04" });
        const adj = acc ? mongo(`return db.journal_entries.findOne({source_type:"bank_opening_adjustment",source_id:{$regex:"^${acc.id}:"}},{_id:0})`) : null;
        // Kelas berjalan bersama: saldo 1-1100 Sukacita ikut bergerak oleh transaksi peserta lain, jadi yang dibuktikan
        // adalah efek bersih jurnal rekening latihan ini (saldo awal + penyesuaian) = nol dan rekening aktif kembali sama.
        const efek = acc ? mongo(`const r={}; db.journal_entries.find({status:{$ne:"void"},$or:[{source_type:"bank_opening_balance",source_id:"${acc.id}"},
          {source_type:"bank_opening_adjustment",source_id:{$regex:"^${acc.id}:"}}]},{lines:1}).forEach(j=>j.lines.forEach(l=>{
          r[l.account_code]=Math.round(((r[l.account_code]||0)+(l.debit||0)-(l.credit||0))*100)/100; })); return r;`) : {};
        const sesudah = { aktif: mongo(`return db.bank_accounts.countDocuments({entity_id:"${k.KSC}",is_active:{$ne:false}})`),
          efek_bersih: efek, nonaktif: acc ? mongo(`return db.bank_accounts.findOne({id:"${acc.id}"},{_id:0,is_active:1,opening_balance:1})`) : null };
        k.simpanJson(r, "sesudah.json", sesudah);
        assert(sesudah.aktif === awal.aktif, `rekening aktif ${sesudah.aktif} ≠ ${awal.aktif}`);
        assert(Object.values(efek).every((v) => Math.abs(v) < 0.01), `efek bersih jurnal rekening latihan ≠ 0: ${JSON.stringify(efek)}`);
        assert(!acc || (sesudah.nonaktif.is_active === false && sesudah.nonaktif.opening_balance === 0), "rekening latihan belum nonaktif / saldo awal ≠ 0");
        return `${adj ? k.cekJurnal(adj, [["3-2900", "D", SALDO], ["1-1100", "K", SALDO]]) : "rekening tidak dibuat"} · efek bersih ${JSON.stringify(efek)} · rekening aktif ${sesudah.aktif}`;
      });
  }
  await r.finish();
})();
