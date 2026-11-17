// K06 — Termin & plafon kredit pelanggan, termin pemasok. Peserta (Finance) membaca profil kredit pelanggannya
// (plafon, termin yang diizinkan, termin bawaan, tahan pesanan bila telat, status) dan MENGAJUKAN perubahan; Manajer
// (pelatih) MENYETUJUI. Lalu pelatih menunjukkan daftar Syarat Bayar per PT dan termin pemasok. Data yang berubah hanya
// profil kredit pelanggan latihan peserta; pengaturan bersama tidak disentuh (dibuktikan).
//   node docs/pelatihan/2026-11-18_keuangan/uji/konfigurasi/K06_termin_plafon.js     (bawaan peserta 11)
const { api, assert, peserta, akunPeserta, mongo, rp, num } = require("../lib");
const k = require("./konfig_lib");

const PLAFON = 300000000;

(async () => {
  const no = peserta("11");
  const r = await k.mulai("K06", "Termin & plafon kredit");
  const fin = await api(akunPeserta(no));
  const mgr = await api("manager");
  const cust = mongo(`return db.customers.findOne({name:/^Latihan ${no} · Toko Kain/},{_id:0,id:1,name:1})`);
  const sup = mongo(`return db.suppliers.findOne({name:/^Latihan ${no} · Pemasok/},{_id:0,id:1,name:1,payment_term_code:1})`);
  assert(cust && sup, `pelanggan/pemasok latihan ${no} belum ada (jalankan seed --hanya a_dasar:mitra)`);
  const sebelum = k.potretSystemSettings();
  const profil = async () => k.ulang(() => fin.get(`/customers/${cust.id}/credit-profile?entity_id=${k.KSC}`));
  const p0 = await profil();
  const termTarget = (p0.effective.allowed_term_codes || []).includes("NET14") ? ["NET30"] : ["NET14", "NET30"];
  r.note(`Pelanggan ${cust.name} · plafon ${rp(p0.effective.credit_limit)} (${p0.effective.limit_mode}) · pengajuan terbuka ${p0.pending_request ? p0.pending_request.number : "-"} · termin sasaran ${termTarget}`);

  const bukaKredit = async (sesiNama, potretCari = false) => {
    await r.go("customers-crm", `&entity=${k.KSC}`);
    await r.tid("customer-search").waitFor();
    await r.tid("customer-search").fill(`Latihan ${no}`);
    await r.idle(1000);
    if (potretCari) await k.potret(r, r.tid(`customer-row-${cust.id}`), "cari-pelanggan");
    await r.tid(`customer-row-${cust.id}`).click();
    await r.tid("customer-360-tab-kredit").click();
    await r.tid("customer-credit-tab").waitFor();
    await r.tid("customer-credit-rows").waitFor({ timeout: 15000 });
    await r.idle(500);
    return sesiNama;
  };

  await r.step(1, "Finance", `Masuk dengan akun peserta → Penjualan › CRM & Pelanggan → cari 'Latihan ${no}' → klik pelanggan Anda → bagian [[Kredit]]`,
    "Profil kredit Sukacita: Jenis plafon/Plafon kredit, Termin yang diizinkan, Termin bawaan, Tahan pesanan bila telat lebih dari (hari), Status kredit — tiap nilai berlencana asal (bawaan PT / khusus pelanggan)", async () => {
      await r.login(akunPeserta(no));
      await r.tid("finance-desk").waitFor();
      await bukaKredit("finance", true);
      const rows = (await r.text("customer-credit-rows"));
      for (const s of ["Plafon", "Termin", "Status kredit"]) assert(rows.includes(s), `profil tanpa "${s}": ${rows}`);
      await k.potret(r, r.tid("customer-credit-rows"), "profil-kredit");
      return rows.slice(0, 260);
    });

  await r.step(2, "Finance", "Bila belum ada pengajuan menunggu: klik [[Ajukan perubahan]] → *Jenis plafon* Plafon khusus pelanggan ini · *Plafon kredit* Rp 300.000.000 · *Alasan* → [[Ajukan]]. Bila sudah ada (usulan saat pelanggan dibuat): baca kotak 'Menunggu keputusan'",
    "Kotak 'Menunggu keputusan' memuat perubahan Plafon kredit → Rp 300.000.000; tombol [[Ajukan perubahan]] mati ('Masih ada pengajuan yang menunggu keputusan'); Finance juga melihat tombol Setujui (K-FIN-01) — keputusan di latihan ini diperagakan Manajer", async () => {
      let p = await profil();
      const sudahKhusus = p.effective.limit_mode === "khusus" && Number(p.effective.credit_limit) === PLAFON;
      if (!p.pending_request) {
        await k.klikPotret(r, r.tid("customer-credit-request"), "ajukan-perubahan");
        await r.tid("credit-request-modal").waitFor();
        await k.pilih(r, "credit-request-limit-mode", "Plafon khusus pelanggan ini");
        await r.tid("credit-request-limit").fill(String(sudahKhusus ? PLAFON - 50000000 : PLAFON));
        await r.tid("credit-request-reason").fill(`Pelatihan K06 — plafon pelanggan latihan ${no}`);
        await k.potret(r, r.tid("credit-request-submit"), "form-ajukan-plafon");
        await r.tid("credit-request-submit").click();
        await r.tid("credit-request-modal").waitFor({ state: "detached", timeout: 15000 });
      }
      await r.tid("customer-credit-pending").waitFor({ timeout: 15000 });
      p = await profil();
      const ch = (p.pending_request.label_changes || []).map((c) => `${c.label} → ${c.to}`).join(", ");
      assert(/Plafon kredit/.test(ch), `pengajuan tanpa plafon: ${ch}`);
      assert(await r.tid("customer-credit-request").isDisabled(), "tombol Ajukan perubahan tidak mati");
      await r.kfin(r.tid("customer-credit-approve"), "tombol Setujui perubahan profil kredit");
      await k.potret(r, r.tid("customer-credit-pending"), "menunggu-keputusan");
      return `${p.pending_request.number} oleh ${p.pending_request.requested_by}: ${ch}`;
    });

  let pend = null;
  await r.step(3, "Manajer (pelatih)", `Masuk sebagai Manajer → Keuangan › Piutang › tab [[Kredit & Plafon]] → ketik 'Latihan ${no}' di kotak cari → baris 'Ubah Profil' pelanggan latihan → [[Setujui]] → [[Setujui]]`,
    "Antrean 'Menunggu keputusan' memuat baris Ubah Profil (pengaju, isi perubahan, alasan); konfirmasi menyebut pelanggan & PT; sesudah disetujui baris hilang dari antrean", async () => {
      pend = (await profil()).pending_request;
      await r.login("manager");
      await r.go("credit-overrides", `&entity=${k.KSC}`);
      await r.tid("credit-desk-view").waitFor();
      await r.tid("credit-desk-search").fill(`Latihan ${no}`);
      await r.idle(1200);
      const row = r.tid(`credit-desk-row-${pend.id}`);
      await row.waitFor({ timeout: 15000 });
      const t = (await row.innerText()).replace(/\s+/g, " ");
      await k.klikPotret(r, r.tid(`credit-desk-approve-${pend.id}`), "manajer-setujui");
      await r.tid("credit-desk-decision").waitFor();
      const msg = (await r.tid("credit-desk-decision").innerText()).replace(/\s+/g, " ");
      await k.potret(r, r.tid("credit-desk-decision-confirm"), "konfirmasi-setujui");
      await r.tid("credit-desk-decision-confirm").click();
      await row.waitFor({ state: "detached", timeout: 15000 });
      const req = mongo(`return db.credit_profile_requests.findOne({id:"${pend.id}"},{_id:0,status:1,decided_by:1})`);
      assert(req && req.status !== "diajukan", `status pengajuan ${req && req.status}`);
      return `${t.slice(0, 160)} · konfirmasi: ${msg.slice(0, 120)} · status ${req.status} oleh ${req.decided_by}`;
    });

  await r.step(4, "Finance", "Kembali ke kartu pelanggan Anda → bagian [[Kredit]] (muat ulang)",
    "Plafon kredit berubah sesuai pengajuan dan berlencana 'khusus pelanggan'; riwayat perubahan kredit mencatat pengaju & penyetuju", async () => {
      await r.login(akunPeserta(no));
      await bukaKredit("finance");
      const p = await profil();
      const toLimit = (pend.changes || []).find((c) => c.field === "credit_limit");
      assert(p.effective.limit_mode === "khusus" && (!toLimit || Number(p.effective.credit_limit) === Number(toLimit.to)),
        `plafon efektif ${p.effective.limit_mode} ${p.effective.credit_limit}`);
      const v = await r.text("customer-credit-value-credit_limit").catch(async () => r.text("customer-credit-rows"));
      assert(num(v) === Math.round(p.effective.credit_limit) || v.includes(rp(p.effective.credit_limit).replace("Rp ", "")), `layar plafon: ${v}`);
      await k.potret(r, r.tid("customer-credit-rows"), "plafon-berlaku");
      return `plafon ${rp(p.effective.credit_limit)} (${p.effective.limit_source})`;
    });

  await r.step(5, "Finance", `Klik [[Ajukan perubahan]] → bagian Termin pembayaran: centang ${termTarget.join(" & ")} · *Termin bawaan* Kredit NET 30 Hari · *Alasan* → [[Ajukan]]`,
    "Form menulis 'Termin di luar daftar ditolak saat pesanan dibuat'; sesudah diajukan muncul kotak 'Menunggu keputusan' berisi Termin yang diizinkan & Termin bawaan", async () => {
      await k.klikPotret(r, r.tid("customer-credit-request"), "ajukan-termin");
      await r.tid("credit-request-modal").waitFor();
      const p = await profil();
      for (const t of p.term_options) {
        const box = r.tid(`credit-request-term-${t.code}`).locator("input");
        const mau = termTarget.includes(t.code);
        if ((await box.isChecked()) !== mau) await box.click();
      }
      await k.pilih(r, "credit-request-default-term", "Kredit NET 30 Hari");
      const sec = (await r.text("credit-request-section-terms"));
      assert(/ditolak saat pesanan dibuat/.test(sec), `penjelasan termin: ${sec.slice(0, 120)}`);
      await r.tid("credit-request-reason").fill(`Pelatihan K06 — termin pelanggan latihan ${no}`);
      await k.potret(r, r.tid("credit-request-section-terms"), "form-termin");
      await r.tid("credit-request-submit").click();
      await r.tid("credit-request-modal").waitFor({ state: "detached", timeout: 15000 });
      await r.tid("customer-credit-pending").waitFor({ timeout: 15000 });
      pend = (await profil()).pending_request;
      const ch = (pend.label_changes || []).map((c) => `${c.label} → ${JSON.stringify(c.to)}`).join(", ");
      assert(/Termin yang diizinkan/.test(ch), `pengajuan termin: ${ch}`);
      return `${pend.number}: ${ch}`;
    });

  await r.step(6, "Manajer (pelatih)", "Masuk sebagai Manajer → CRM & Pelanggan → pelanggan latihan → bagian [[Kredit]] → [[Setujui]] di kotak 'Menunggu keputusan' → [[Setujui]]",
    "Termin yang diizinkan & termin bawaan langsung berlaku untuk pesanan baru pelanggan ini di Sukacita", async () => {
      await r.login("manager");
      await bukaKredit("manager");
      await r.tid("customer-credit-pending").waitFor();
      await k.klikPotret(r, r.tid("customer-credit-approve"), "manajer-setujui-di-kartu");
      await r.tid("credit-request-approve-confirm").waitFor();
      await r.tid("credit-request-approve-confirm-confirm").click();
      await r.tid("customer-credit-pending").waitFor({ state: "detached", timeout: 15000 });
      const p = await profil();
      assert(JSON.stringify([...p.effective.allowed_term_codes].sort()) === JSON.stringify([...termTarget].sort()) && p.effective.default_term_code === "NET30",
        `termin efektif ${p.effective.allowed_term_codes} · bawaan ${p.effective.default_term_code}`);
      await r.idle(400);
      await k.potret(r, r.tid("customer-credit-rows"), "termin-berlaku");
      return `termin diizinkan ${p.effective.allowed_term_codes.join(", ")} · bawaan ${p.effective.default_term_code}`;
    });

  await r.step(7, "Manajer (pelatih)", "Pengaturan › Perusahaan (PT) › tab [[Master per PT]] → kelompok [[Syarat Pembayaran]]",
    "Daftar syarat bayar (CASH, NET7, NET14, NET30, DP50, Bertahap 3x, CBD, NET60, NET90) dengan jumlah hari; asal Global atau khusus PT", async () => {
      await r.go("entity-masters", `&entity=${k.KSC}`);
      await r.tid("entity-masters-view").waitFor();
      await r.tid("em-group-payment-terms").click();
      await r.idle(1000);
      const rows = await r.page.$$eval('[data-testid^="em-row-"]', (els) => els.map((e) => e.innerText.replace(/\s+/g, " ").trim()));
      const kode = (await profil()).term_options.map((t) => t.code);
      assert(kode.every((c) => rows.some((x) => x.includes(c))), `syarat bayar tidak lengkap di layar: ${kode}`);
      await k.potret(r, r.tid("em-group-payment-terms"), "master-syarat-bayar");
      return `${rows.length} syarat bayar: ${kode.join(", ")}`;
    });

  await r.step(8, "Manajer (pelatih)", `Pembelian › Master Pembelian › Pemasok → cari 'Latihan ${no}' → klik ikon rincian pada pemasok latihan`,
    "Rincian pemasok memuat termin bayar (contoh NET30 = jatuh tempo tagihan 30 hari sesudah tanggal tagihan)", async () => {
      await r.go("suppliers", `&entity=${k.KSC}`);
      await r.tid("suppliers-view").waitFor();
      await r.tid("supplier-search").fill(`Latihan ${no}`);
      await r.idle(1000);
      await k.klikPotret(r, r.tid(`detail-supplier-${sup.id}`), "pemasok-latihan");
      await r.idle(1200);
      const body = (await r.page.locator("body").innerText()).replace(/\s+/g, " ");
      const term = mongo(`return db.payment_terms.findOne({code:"${sup.payment_term_code}"},{_id:0,name:1,net_days:1})`) || {};
      assert(body.includes(sup.payment_term_code) || (term.name && body.includes(term.name)), `rincian pemasok tanpa termin ${sup.payment_term_code}`);
      await r.shot("rincian-pemasok-termin");
      return `${sup.name}: termin ${sup.payment_term_code} (${term.name || "?"}, ${term.net_days ?? "?"} hari)`;
    });

  await r.step(9, "Pelatih", "Pastikan pengaturan bersama tidak berubah",
    "Aturan kredit PT (plafon bawaan, periksa kredit, blokir telat) sama dengan sebelum skenario — yang berubah hanya profil pelanggan latihan", async () => {
      const sesudah = k.potretSystemSettings();
      assert(JSON.stringify(sesudah) === JSON.stringify(sebelum), `pengaturan berubah: ${k.beda(sebelum, sesudah)}`);
      return "system_settings global & Sukacita tidak berubah";
    });
  await r.finish();
})();
