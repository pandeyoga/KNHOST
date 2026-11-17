// H01 — Data karyawan baru (Finance, K-SDM-01): SDM › Karyawan › [Tambah Karyawan] dengan NIK, tanggal masuk, NPWP,
// status PTKP, rekening bank, gaji pokok & tunjangan. Karyawan baru = "Latihan NN · Andi Pratama" (Kartu Peserta ›
// "Karyawan baru"), masuk 1 Oktober 2026 → terlewat proses gaji reguler Oktober (sudah diposting) → gaji Oktobernya
// dibayar sebagai Rapel di proses susulan November (H02–H04).
//   node docs/pelatihan/2026-11-18_keuangan/uji/sdm/H01_karyawan_baru.js      (bawaan peserta 51; KN_PESERTA=52 …)
//   KN_ULANG=1 … → karyawan latihan peserta itu yang sudah ada diganti nama "(uji lama)" dulu (khusus lingkungan lokal).
const { Run, assert, rp, peserta, akunPeserta, mongo } = require("../lib");
const s = require("./sdm_lib");

(async () => {
  const no = peserta("51");
  const d = s.dataKaryawan(no);
  const r = await new Run("H01", "Data karyawan baru").start();
  if (process.env.KN_ULANG) {
    mongo(`return db.hr_employees.updateMany({name:${JSON.stringify(d.nama)},entity_id:"ent_ksc"},
      {$set:{name:${JSON.stringify(d.nama + " (uji lama)")},status:"resigned"}}).modifiedCount`);
  }
  r.note(`Peserta ${no} · ${d.nama} · masuk ${d.tanggal_masuk} · PTKP ${d.ptkp} · gaji pokok ${rp(d.gaji_pokok)} + ${d.tunjangan} ${rp(d.tunjangan_nominal)}`);
  let emp = null;

  await r.step(1, "Finance", "Login → SDM › [[Karyawan]] → [[Tambah Karyawan]]", "Form \"Tambah Karyawan\" empat bagian: Data Pribadi · Kepegawaian · Pajak & Statutory · Bank & Komponen Gaji", async () => {
    await s.masuk(r, akunPeserta(no));
    assert(!s.karyawan(d.nama), `karyawan ${d.nama} sudah ada — pakai peserta baru (atau KN_ULANG=1 di lingkungan lokal)`);
    await s.menu(r, "hrd", "hr-people");
    await r.tid("employees-view").waitFor();
    await s.klikPotret(r, r.tid("create-employee-button"), "daftar-karyawan");
    await r.tid("employee-form-drawer").waitFor();
    return await r.text("employee-form-drawer-title");
  });

  await r.step(2, "Finance", `Bagian Data Pribadi & Kepegawaian: *Nama Lengkap* ${d.nama} · *NIK* ${d.nik} · *Status Kepegawaian* Tetap · *Tanggal Masuk* 1 Okt 2026 · *PT* Sukacita`, "Isian terisi; PT terkunci ke PT Anda", async () => {
    await r.tid("employee-name-input").fill(d.nama);
    await r.tid("employee-nik-input").fill(d.nik);
    await s.pilihTanggal(r, "employee-joindate-input", d.tanggal_masuk);
    const pt = await r.text("employee-entity-select").catch(() => "");
    if (!/Sukacita/i.test(pt)) await s.pilih(r, "employee-entity-select", "Sukacita");
    await r.tid("employee-sec-1").scrollIntoViewIfNeeded();
    await r.shot("data-pribadi-kepegawaian");
    return `PT ${await r.text("employee-entity-select")} · masuk ${await r.text("employee-joindate-input")}`;
  });

  await r.step(3, "Finance", `Bagian Pajak & Statutory: *NPWP* ${d.npwp} · *Status PTKP* K1 (kawin, 1 tanggungan)`, "PTKP K1 → PPh 21 memakai tarif efektif kategori B", async () => {
    await r.tid("employee-npwp-input").fill(d.npwp);
    await s.pilihPersis(r, "employee-ptkp-select", d.ptkp.replace("/", ""));
    await r.tid("employee-sec-3").scrollIntoViewIfNeeded();
    await r.shot("pajak-ptkp", { locator: r.tid("employee-sec-3") });
    const v = await r.text("employee-ptkp-select");
    assert(v === d.ptkp.replace("/", ""), `PTKP terpilih ${v}`);
    return `PTKP ${v}`;
  });

  await r.step(4, "Finance", `Bagian Bank & Komponen Gaji: *Nama Bank* ${d.bank} · *No. Rekening* ${d.rekening} · *Atas Nama* ${d.atas_nama} · *Gaji Pokok* ${rp(d.gaji_pokok)} · [[+]] tunjangan *${d.tunjangan}* ${rp(d.tunjangan_nominal)}`, "Pratinjau di bawah kotak gaji: Rp 7.500.000", async () => {
    await r.tid("employee-bank-name-input").fill(d.bank);
    await r.tid("employee-bank-acc-input").fill(d.rekening);
    await r.tid("employee-bank-name-acc-input").fill(d.atas_nama);
    await r.tid("employee-salary-input").fill(String(d.gaji_pokok).replace(/\B(?=(\d{3})+(?!\d))/g, "."));
    await r.tid("employee-add-allowance").click();
    await r.tid("allowance-name-0").fill(d.tunjangan);
    await r.tid("allowance-amount-0").fill(String(d.tunjangan_nominal).replace(/\B(?=(\d{3})+(?!\d))/g, "."));
    const prev = await r.text("employee-salary-input-preview");
    assert(prev.includes(rp(d.gaji_pokok).replace("Rp ", "")), `pratinjau gaji: ${prev}`);
    await r.tid("employee-sec-4").scrollIntoViewIfNeeded();
    await s.sorot(r.tid("employee-save-button"));
    await r.shot("bank-gaji", { locator: r.tid("employee-form-drawer") });
    await s.lepas(r.tid("employee-save-button"));
    return `pratinjau ${prev}`;
  });

  await r.step(5, "Finance", "Klik [[Simpan]]", "Pesan \"Karyawan baru dibuat.\"; baris baru EMP-… di daftar dengan gaji pokok Rp 7.500.000, status Aktif", async () => {
    // Server dev bisa sedang dimuat ulang (agent lain mengubah berkas backend) → simpan diulang bila belum tersimpan.
    for (let i = 1; i <= 3; i += 1) {
      await r.tid("employee-save-button").click();
      try { await r.tid("employee-form-drawer").waitFor({ state: "detached", timeout: 20000 }); break; } catch (e) {
        const galat = await r.text("employee-form-error").catch(() => "");
        if (s.karyawan(d.nama)) { await r.tid("employee-cancel-button").click().catch(() => {}); break; }
        if (i === 3) throw new Error(`form tidak tertutup: ${galat}`);
        r.note(`simpan diulang (${i}): ${galat}`);
        await s.tungguApi();
      }
    }
    emp = s.karyawan(d.nama);
    assert(emp, "karyawan tidak tersimpan");
    await r.tid("employee-search").fill(`Latihan ${no}`);
    await r.tid(`employee-row-${emp.id}`).waitFor({ timeout: 10000 });
    const row = (await r.tid(`employee-row-${emp.id}`).innerText()).replace(/\s+/g, " ");
    assert(row.includes(rp(d.gaji_pokok).replace("Rp ", "")), `baris: ${row}`);
    await s.sorot(r.tid(`employee-row-${emp.id}`));
    await r.shot("karyawan-tersimpan");
    await s.lepas(r.tid(`employee-row-${emp.id}`));
    return row;
  });

  await r.step(6, "Finance", "Cek data: buka [[Karyawan 360°]] (ikon grafik) pada baris itu → bagian Riwayat kompensasi", "Kompensasi berlaku 1 Okt 2026: gaji pokok Rp 7.500.000 + tunjangan transport Rp 500.000, status Disahkan; penugasan PT Sukacita", async () => {
    assert(emp.ptkp_status === "K1" && emp.npwp === d.npwp && emp.bank_acc_no === d.rekening && emp.join_date === d.tanggal_masuk,
      `DB karyawan: ${JSON.stringify({ ptkp: emp.ptkp_status, npwp: emp.npwp, rek: emp.bank_acc_no, masuk: emp.join_date })}`);
    assert(Number(emp.base_salary) === d.gaji_pokok && (emp.allowances || [])[0]?.amount === d.tunjangan_nominal, "gaji/tunjangan DB");
    const komp = mongo(`return db.hr_compensation_history.find({employee_id:"${emp.id}"},{_id:0}).toArray()`) || [];
    const asg = mongo(`return db.hr_employee_assignments.find({employee_id:"${emp.id}"},{_id:0}).toArray()`) || [];
    await r.tid(`detail-employee-${emp.id}`).click();
    await r.tid("emp-comp-section").waitFor({ timeout: 15000 });
    await r.idle(600);
    const t = (await r.tid("emp-comp-section").innerText()).replace(/\s+/g, " ");
    assert(t.includes("7.500.000"), `riwayat kompensasi: ${t.slice(0, 300)}`);
    await r.tid("emp-comp-section").scrollIntoViewIfNeeded();
    await s.sorot(r.tid("emp-comp-section"));
    await r.shot("riwayat-kompensasi");
    return `${emp.code} · kompensasi ${komp.length} baris (${komp.map((k) => k.status).join(",")}) · penugasan ${asg.length} · ${t.slice(0, 200)}`;
  });

  await r.finish();
})();
