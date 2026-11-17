// K05 — Aturan Keuangan & Pajak (Pengaturan › Keuangan & Pajak › Aturan Keuangan & Pajak): pelatih (Admin — izin kelola
// pengaturan) membaca kunci penting (PPN & DPP nilai lain, syarat bayar, denda, toleransi selisih bayar, nomor referensi,
// titipan sales, kas kecil, cara bayar), lalu MENGUBAH satu aturan khusus Sukacita (kelompok umur piutang 30·60·90 →
// 15·30·60), peserta (Finance) melihat akibatnya di Piutang › Saldo & Umur, dan pelatih MENGEMBALIKAN ("Ikuti nilai grup").
// Pengaturan dipotret sebelum, dikembalikan di `finally`, dan dibuktikan sama.
//   node docs/pelatihan/2026-11-18_keuangan/uji/konfigurasi/K05_aturan_keuangan_pajak.js     (bawaan peserta 11)
const { api, assert, peserta, akunPeserta, mongo } = require("../lib");
const k = require("./konfig_lib");

const KUNCI = "ar.aging_buckets";
const BARU = [15, 30, 60];
const BACA = {   // kunci penting yang dibaca (nilai dicocokkan layar ↔ API)
  "pajak-pembukuan": ["tax.ppn_rate", "tax.dpp_nilai_lain", "tax.dpp_nilai_lain_pembilang", "tax.dpp_nilai_lain_penyebut",
    "finance.lpj_wajib_lampiran"],
  "pembayaran-pelanggan": ["finance.default_payment_term_code", "ar.denda_rate_pct_per_month", "ar.grace_days",
    "payment.variance_tolerance_rupiah", "payment.wajib_nomor_referensi", "pembayaran.sales_terima_tunai"],
};

async function judulKolom(r) {
  await r.tid("ar-aging-table").waitFor({ timeout: 20000 });
  return r.page.$$eval('[data-testid^="ar-aging-col-"]', (els) => els.map((e) => e.textContent.replace(/\s+/g, " ").trim()));
}

(async () => {
  const no = peserta("11");
  const r = await k.mulai("K05", "Aturan keuangan & pajak");
  const admin = await api("admin");
  const sebelum = { system_settings: k.potretSystemSettings(), nilai: (await k.nilaiConfig(admin, KUNCI)).value,
    sumber: (await k.nilaiConfig(admin, KUNCI)).source_label };
  k.simpanJson(r, "sebelum.json", sebelum);
  r.note(`Sebelum: ${KUNCI} Sukacita = ${JSON.stringify(sebelum.nilai)} (${sebelum.sumber})`);
  let kolom0 = [];
  let diubah = false;

  await r.step(1, "Admin (pelatih)", "Buka Pengaturan › Keuangan & Pajak (tab Aturan Keuangan & Pajak); *Berlaku untuk* Satu PT · Sukacita Textile",
    "Tiga kelompok: Pembayaran pelanggan · Pajak, pembukuan & antar-PT · Bank & uang yang nyangkut; tiap baris: nama aturan, nilai, asal nilai (Bawaan sistem / Aturan grup / Khusus Sukacita) dan tingkat risiko", async () => {
      await r.login("admin");
      await r.go("settings-cfg-finance", `&entity=${k.KSC}`);
      await r.tid("cfg-group-chips").waitFor();
      await r.idle(1000);
      const chips = (await r.text("cfg-group-chips"));
      assert(/Pembayaran pelanggan/.test(chips) && /Pajak/.test(chips) && /Bank/.test(chips), `kelompok: ${chips}`);
      assert(/Sukacita/.test(await r.text("cfg-scope-ribbon")), "pita lingkup tidak menyebut Sukacita");
      await k.potret(r, r.tid("cfg-scope-box"), "aturan-keuangan");
      return chips;
    });

  await r.step(2, "Admin (pelatih)", "Klik kelompok [[Pajak, pembukuan & antar-PT]] → ketik 'PPN' di kotak cari → buka baris 'Tarif PPN'",
    "Tarif PPN 12 %, Pakai DPP nilai lain Ya (faktor 11/12 → PPN efektif 11 % dari harga jual), Cara menghitung PPN dari harga; penjelasan dan contoh tampil saat baris dibuka", async () => {
      await r.tid("cfg-group-pajak-pembukuan").click();
      await r.idle(600);
      await r.tid("cfg-search").fill("PPN");
      await r.idle(900);
      const out = [];
      for (const key of ["tax.ppn_rate", "tax.dpp_nilai_lain"]) {
        await r.tid(`cfg-card-${key}`).waitFor();
        const v = await k.nilaiConfig(admin, key);
        out.push(`${await r.text(`cfg-card-label-${key}`)}: ${await r.text(`cfg-compact-value-${key}`)} (API ${JSON.stringify(v.value)})`);
      }
      const rate = (await k.nilaiConfig(admin, "tax.ppn_rate")).value;
      const p = (await k.nilaiConfig(admin, "tax.dpp_nilai_lain_pembilang")).value;
      const q = (await k.nilaiConfig(admin, "tax.dpp_nilai_lain_penyebut")).value;
      assert(Number(rate) === 12 && Number(p) === 11 && Number(q) === 12, `PPN ${rate} · DPP ${p}/${q}`);
      await r.tid("cfg-card-toggle-tax.ppn_rate").click();
      await r.idle(400);
      await k.potret(r, r.tid("cfg-card-tax.ppn_rate"), "tarif-ppn");
      return `${out.join(" · ")} · efektif ${(rate * p / q).toFixed(2)} %`;
    });

  await r.step(3, "Admin (pelatih)", "Ganti isi cari menjadi 'LPJ'",
    "Kas kecil: 'LPJ kas kecil wajib berlampiran bukti' — nilai sekarang dan asalnya", async () => {
      await r.tid("cfg-search").fill("LPJ");
      await r.idle(900);
      const key = "finance.lpj_wajib_lampiran";
      await r.tid(`cfg-card-${key}`).waitFor();
      await k.potret(r, r.tid(`cfg-card-${key}`), "kas-kecil-lpj");
      return `${await r.text(`cfg-card-label-${key}`)}: ${await r.text(`cfg-compact-value-${key}`)} · ${await r.text(`cfg-layer-badge-${key}`)}`;
    });

  await r.step(4, "Admin (pelatih)", "Kosongkan cari → klik kelompok [[Pembayaran pelanggan]] → baca bagian Syarat bayar, Kwitansi pelanggan, Denda telat bayar, Selisih bayar",
    "Syarat bayar bawaan NET30 · Wajibkan nomor referensi di kwitansi · Tunai yang diterima sales dicatat sebagai titipan (Khusus Sukacita) · Bunga denda 2 %/bulan, masa tenggang · Selisih bayar yang dianggap lunas Rp 5.000", async () => {
      await r.tid("cfg-search").fill("");
      await r.tid("cfg-group-pembayaran-pelanggan").click();
      await r.idle(900);
      const out = [];
      for (const key of BACA["pembayaran-pelanggan"]) {
        await r.tid(`cfg-card-${key}`).waitFor();
        const v = await k.nilaiConfig(admin, key);
        out.push(`${await r.text(`cfg-card-label-${key}`)} = ${await r.text(`cfg-compact-value-${key}`)} [${v.source_label || v.source}]`);
      }
      await r.tid("cfg-section-syarat-bayar").scrollIntoViewIfNeeded().catch(() => {});
      await r.shot("pembayaran-pelanggan", { full: true });
      const tol = (await k.nilaiConfig(admin, "payment.variance_tolerance_rupiah")).value;
      assert(Number(tol) > 0, `toleransi selisih ${tol}`);
      return out.join(" · ");
    });

  await r.step(5, "Finance", "Masuk dengan akun peserta → Keuangan › Piutang (tab Saldo & Umur) → baca judul kolom umur",
    "Kolom: Belum jatuh tempo · 1–30 hari · 31–60 hari · 61–90 hari · > 90 hari (mengikuti aturan 'Kelompok umur piutang' 30 · 60 · 90)", async () => {
      await r.login(akunPeserta(no));
      await r.tid("finance-desk").waitFor();
      await k.menuPotret(r, "keuangan", "ar-aging", "menu-piutang");
      await r.tid("ar-aging-view").waitFor();
      kolom0 = await judulKolom(r);
      assert(kolom0.join("|") === "Belum jatuh tempo|1–30 hari|31–60 hari|61–90 hari|> 90 hari", `kolom awal: ${kolom0}`);
      await k.potret(r, r.tid("ar-aging-col-b1_30"), "umur-piutang-awal");
      return kolom0.join(" · ");
    });

  try {
    await r.step(6, "Admin (pelatih)", "Kembali ke Aturan Keuangan & Pajak (Satu PT · Sukacita) → buka baris 'Kelompok umur piutang (hari)' → ubah batas menjadi 15 · 30 · 60 → isi alasan → [[Simpan]]",
      "Kotak 'Akan berubah: 30 · 60 · 90 → 15 · 30 · 60 untuk Sukacita' dan 'Hanya Sukacita yang terpengaruh — PT lain tidak berubah.'; sesudah simpan lencana asal berubah menjadi 'Khusus Sukacita'", async () => {
        await r.login("admin");
        await r.go("settings-cfg-finance", `&entity=${k.KSC}`);
        await r.tid("cfg-group-pembayaran-pelanggan").click();
        await r.idle(800);
        await r.tid(`cfg-card-toggle-${KUNCI}`).click();
        await r.tid(`cfg-input-${KUNCI}`).waitFor();
        for (let i = 0; i < BARU.length; i += 1) await r.tid(`cfg-input-${KUNCI}-${i}`).fill(String(BARU[i]));
        await r.tid(`cfg-dirty-${KUNCI}`).waitFor();
        const dirty = (await r.text(`cfg-dirty-${KUNCI}`));
        assert(/Sukacita/.test(dirty) && /PT lain tidak berubah/.test(dirty), `kotak perubahan: ${dirty}`);
        await r.tid(`cfg-reason-${KUNCI}`).fill("Peragaan pelatihan K05 — dikembalikan sesudah demo");
        await k.potret(r, r.tid(`cfg-save-${KUNCI}`), "ubah-kelompok-umur");
        await r.tid(`cfg-save-${KUNCI}`).click();
        diubah = true;
        await k.tunggu(async () => JSON.stringify((await k.nilaiConfig(admin, KUNCI)).value) === JSON.stringify(BARU), "nilai belum tersimpan");
        await r.idle(800);
        const badge = await r.text(`cfg-layer-badge-${KUNCI}`);
        const glob = await admin.get(`/config/effective?q=${KUNCI}&scope=global`);
        const g = (glob.items || []).find((x) => x.key === KUNCI);
        assert(JSON.stringify(g.value) === JSON.stringify(sebelum.nilai), `nilai grup ikut berubah: ${JSON.stringify(g.value)}`);
        await k.potret(r, r.tid(`cfg-card-${KUNCI}`), "kelompok-umur-tersimpan");
        return `${dirty.slice(0, 140)} · asal: ${badge} · nilai grup tetap ${JSON.stringify(g.value)}`;
      });

    await r.step(7, "Finance", "Muat ulang Piutang › Saldo & Umur (ikon muat ulang)",
      "Judul kolom langsung mengikuti aturan baru: 1–15 hari · 16–30 hari · 31–60 hari · > 60 hari — tanpa mengubah satu transaksi pun", async () => {
        await r.login(akunPeserta(no));
        await r.go("ar-aging");
        await r.tid("ar-aging-view").waitFor();
        const kol = await judulKolom(r);
        assert(kol.join("|") === "Belum jatuh tempo|1–15 hari|16–30 hari|31–60 hari|> 60 hari", `kolom baru: ${kol}`);
        await k.potret(r, r.tid("ar-aging-col-b1_30"), "umur-piutang-sesudah-ubah");
        return kol.join(" · ");
      });
  } finally {
    await r.step(8, "Admin (pelatih)", "Buka lagi baris 'Kelompok umur piutang (hari)' → klik [[Ikuti nilai grup]] → isi *Alasan* → [[Ikuti nilai grup]]",
      "Nilai kembali 30 · 60 · 90 berasal 'Aturan grup'; pengaturan tersimpan sama persis dengan sebelum peragaan", async () => {
        if (diubah) {
          await r.login("admin");
          await r.go("settings-cfg-finance", `&entity=${k.KSC}`);
          await r.tid("cfg-group-pembayaran-pelanggan").click();
          await r.idle(800);
          await r.tid(`cfg-card-toggle-${KUNCI}`).click();
          const btn = r.tid(`cfg-clear-entity-${KUNCI}`);
          await btn.waitFor({ timeout: 8000 });
          await k.klikPotret(r, btn, "ikuti-nilai-grup");
          await r.tid("cfg-clear-confirm").waitFor({ timeout: 8000 });
          const msg = (await r.tid("cfg-clear-confirm-message").innerText()).replace(/\s+/g, " ");
          await r.tid("cfg-clear-confirm-reason").fill("Selesai peragaan pelatihan K05");
          await k.potret(r, r.tid("cfg-clear-confirm-confirm"), "konfirmasi-ikuti-grup");
          await r.tid("cfg-clear-confirm-confirm").click();
          r.note(`Konfirmasi: ${msg}`);
          await k.tunggu(async () => JSON.stringify((await k.nilaiConfig(admin, KUNCI)).value) === JSON.stringify(sebelum.nilai), "nilai belum kembali", 15000)
            .catch(async () => {   // cadangan bila layar gagal
              await admin.post("/config/values/clear", { key: KUNCI, scope_type: "entity", scope_id: k.KSC, reason: "Pemulihan otomatis uji K05" });
            });
        }
        const it = await k.nilaiConfig(admin, KUNCI);
        const sesudah = { system_settings: k.potretSystemSettings(), nilai: it.value, sumber: it.source_label };
        k.simpanJson(r, "sesudah.json", sesudah);
        assert(JSON.stringify(sesudah) === JSON.stringify(sebelum), `pengaturan berbeda: ${k.beda(sebelum, sesudah)}`);
        await r.idle(600);
        await r.shot("kembali-nilai-grup");
        return `${KUNCI} = ${JSON.stringify(it.value)} (${it.source_label}); system_settings global & Sukacita = sebelum`;
      });

    await r.step(9, "Finance", "Muat ulang Piutang › Saldo & Umur",
      "Kolom kembali: Belum jatuh tempo · 1–30 · 31–60 · 61–90 · > 90 hari", async () => {
        await r.login(akunPeserta(no));
        await r.go("ar-aging");
        const kol = await judulKolom(r);
        assert(kol.join("|") === kolom0.join("|"), `kolom ${kol} ≠ awal ${kolom0}`);
        await k.potret(r, r.tid("ar-aging-col-b1_30"), "umur-piutang-kembali");
        return kol.join(" · ");
      });
  }
  await r.finish();
})();
