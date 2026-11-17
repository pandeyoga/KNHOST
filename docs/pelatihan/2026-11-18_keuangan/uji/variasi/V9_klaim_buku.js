// V9 · BUKU, LAPORAN & FONDASI — bukti di LAYAR untuk klaim teks materi K01–K05 dan A5 yang belum dibuktikan uji lain.
// Semua langkah HANYA MEMBACA (tidak menyimpan pengaturan, akun, atau rekening): aman diulang kapan saja.
//
//   KN_PESERTA=86 node docs/pelatihan/2026-11-18_keuangan/uji/variasi/V9_klaim_buku.js
//
// Hasil → uji/hasil/V9/buku/.
const { Run, assert, peserta, akunPeserta, rp, sleep, mongo } = require("../lib");
const k9 = require("./v9lib");

const NO = peserta("86");
const KSC = "ent_ksc";
/** Nominal PERTAMA di teks ("Rp 26.127.376", "-Rp 1.000", "Rp -1.000"); baris Neraca bisa memuat kolom pembanding. */
const uang = (s) => {
  const m = String(s || "").replace(/\s+/g, " ").match(/([-−]?)\s*Rp\s*([-−]?)\s*([\d.]+(?:,\d+)?)/);
  if (!m) return 0;
  const n = Number(m[3].replace(/\./g, "").replace(",", "."));
  return (m[1] || m[2]) ? -n : n;
};

(async () => {
  k9.bersihkan("buku");
  const d = k9.daftar("buku");
  const r = await new Run(d.kode, "V9 · Bukti klaim materi Buku Besar, Laporan & Fondasi (K01–K05, A5)").start();
  const step = (meta, fn) => k9.klaim(r, d, meta, fn);
  const pilihPT = async (id) => {
    const sw = r.tid("entity-switcher");
    if (!(await sw.count())) return;
    await sw.click();
    await r.tid(`entity-option-${id}`).click();
    await r.idle(1200);
  };

  try {
    // ── A5: laba bersih Laba-Rugi = Laba Tahun Berjalan di Neraca ────────────────────────────────────────────────────
    await r.login("manager");
    await pilihPT(KSC);
    await step({ kode: "A5", bagian: "cek_buku.1", peran: "Manajer",
      klaim: "Laba bersih di Laba-Rugi = perubahan laba ditahan di Neraca untuk periode yang sama",
      harap: "Laba-Rugi 1 Jan–hari ini: Laba Bersih = baris 'Laba Tahun Berjalan' (Ekuitas) di Neraca hari ini; Laba Ditahan 3-2000 baru berubah saat tutup buku (tahun ini tanpa jurnal penutup)" },
    async () => {
      await r.go("financial-statements", `&entity=${KSC}`);
      await r.tid("financial-statements-view").waitFor();
      await r.tid("fs-pl-mode-range").click().catch(() => {});
      await r.tid("fs-pl-kpi-net").waitFor({ timeout: 20000 });
      await r.idle(1500);
      const net = uang(await k9.teks(r, "fs-pl-kpi-net"));
      const rentang = await k9.teks(r, "fs-pl-period-hint").catch(() => "");
      await r.shot("a5-laba-rugi");
      await r.tid("fs-tab-bs").click();
      await r.tid("fs-bs-total-assets").waitFor({ timeout: 20000 });
      await r.idle(1200);
      const baris = r.page.locator("tr", { hasText: "Laba Tahun Berjalan" }).first();
      const lb = uang(await baris.innerText());
      const ld = (await r.tid("fs-bs-line-3-2000").count()) ? await k9.teks(r, "fs-bs-line-3-2000") : "(3-2000 tidak tampil)";
      const penutup = mongo(`return db.journal_entries.countDocuments({entity_id:"${KSC}",status:{$ne:"void"},date:{$gte:"2026-01-01"},
        "lines.account_code":"3-2000"})`);
      await baris.scrollIntoViewIfNeeded();
      await r.shot("a5-neraca-laba-berjalan");
      assert(Math.abs(net - lb) < 1, `Laba Bersih L/R ${rp(net)} ≠ Laba Tahun Berjalan ${rp(lb)}`);
      return `L/R ${rentang || "1 Jan–hari ini"}: Laba Bersih ${rp(net)} = Neraca 'Laba Tahun Berjalan' ${rp(lb)} · ${ld} · jurnal 2026 yang menyentuh 3-2000: ${penutup}`;
    });

    // ── K01: akun yang ditambah di lingkup Semua PT masuk Template Global ─────────────────────────────────────────────
    await step({ kode: "K01", bagian: "kesalahan_umum.2", peran: "Manajer",
      klaim: "Menambah akun saat bilah atas memilih 'Semua PT': akun masuk Template Global dan dipakai semua PT",
      harap: "Bilah atas Semua PT → Bagan Akun → [Tambah Akun]: pop-up menulis 'Akun akan dibuat sebagai template global (semua PT).' (tidak disimpan); PT Sukacita → 'khusus untuk PT Sukacita'" },
    async () => {
      await pilihPT("all");
      await r.go("ledger");
      await r.tid("hub-tab-chart-of-accounts").click();
      await r.tid("coa-add-toggle").waitFor({ timeout: 20000 });
      await r.tid("coa-add-toggle").click();
      await r.tid("coa-add-form").waitFor();
      const semua = await k9.teks(r, "coa-add-form");
      await r.shot("k01-tambah-akun-semua-pt");
      await r.tid("coa-add-form-cancel").click();
      await pilihPT(KSC);
      await r.go("ledger");
      await r.tid("hub-tab-chart-of-accounts").click();
      await r.tid("coa-add-toggle").waitFor({ timeout: 20000 });
      await r.tid("coa-add-toggle").click();
      await r.tid("coa-add-form").waitFor();
      const satu = await k9.teks(r, "coa-add-form");
      await r.tid("coa-add-form-cancel").click();
      assert(/template global \(semua PT\)/.test(semua) && /khusus untuk PT Sukacita/.test(satu), `Semua PT: ${semua.slice(0, 120)} · Sukacita: ${satu.slice(0, 120)}`);
      return `Semua PT: '${(semua.match(/Akun akan dibuat[^.]*\./) || [""])[0]}' · Sukacita: '${(satu.match(/Akun akan dibuat[^.]*\./) || [""])[0]}'`;
    });

    // ── K02: Manajer hanya melihat pemetaan; Finance boleh mengubah ──────────────────────────────────────────────────
    const tombolAtur = () => r.page.locator('[data-testid^="glmap-edit-"]').count();
    await step({ kode: "K02", bagian: "konsep.4", peran: "Manajer",
      klaim: "Finance boleh mengubah pemetaan (bersama Admin); Manajer hanya melihat",
      harap: "Pengaturan › Keuangan & Pajak › Pemetaan Akun: Manajer tidak punya tombol [Atur PT]/ubah; Finance punya" },
    async () => {
      await r.go("gl-account-mappings", `&entity=${KSC}`);
      await r.tid("gl-mapping-view").waitFor({ timeout: 20000 });
      await r.idle(1200);
      const mgr = await tombolAtur();
      await r.shot("k02-manajer-lihat-saja");
      await r.login(akunPeserta(NO));
      await r.go("gl-account-mappings", `&entity=${KSC}`);
      await r.tid("gl-mapping-view").waitFor({ timeout: 20000 });
      await r.idle(1200);
      const fin = await tombolAtur();
      assert(mgr === 0 && fin > 0, `tombol ubah: Manajer ${mgr} · Finance ${fin}`);
      return `tombol ubah pemetaan: Manajer ${mgr} · Finance ${fin}`;
    });

    // ── K05: Finance dan layar Aturan Keuangan & Pajak ────────────────────────────────────────────────────────────────
    await step({ kode: "K05", bagian: "kesalahan_umum.3", peran: "Finance",
      klaim: "Finance hanya melihat Pengaturan › Keuangan & Pajak › Pemetaan Akun (tidak melihat layar Aturan Keuangan & Pajak)",
      harap: "Menu Pengaturan › Keuangan & Pajak untuk Finance: tab yang tampil dicatat apa adanya; tab 'Aturan Keuangan & Pajak' tidak ada" },
    async () => {
      const nav = r.tid("nav-settings-finance");
      if (!(await nav.isVisible().catch(() => false))) {
        await r.tid("nav-group-toggle-settings-hub").click().catch(() => {});
      }
      await nav.click();
      await r.idle(1200);
      const tabs = await r.page.locator('[data-testid^="hub-tab-"]').allInnerTexts();
      const aturan = await r.tid("hub-tab-settings-cfg-finance").count();
      await r.shot("k05-finance-tab-pengaturan");
      assert(!aturan, `Finance melihat tab Aturan: ${tabs.join(" | ")}`);
      return `tab untuk Finance: ${tabs.map((t) => t.trim()).filter(Boolean).join(" | ") || "(satu layar Pemetaan Akun)"} · layar: ${(await k9.teks(r, "gl-mapping-view")).slice(0, 60)}`;
    });

    // ── K04: form Ubah rekening tidak memuat saldo awal ───────────────────────────────────────────────────────────────
    await step({ kode: "K04", bagian: "kesalahan_umum.2", peran: "Finance",
      klaim: "Saldo awal tidak bisa diubah lewat [Ubah rekening]: form ubah tidak memuat saldo awal",
      harap: "Kas & Bank › Rekening & Saldo › kartu BCA Operasional KSC › [Ubah rekening]: form tanpa isian Saldo Awal (tidak disimpan)" },
    async () => {
      const bca = mongo(`return db.bank_accounts.findOne({entity_id:"${KSC}",name:"BCA Operasional KSC"},{_id:0,id:1})`);
      await r.go("bank-accounts", `&entity=${KSC}`);
      await r.tid(`bank-card-${bca.id}`).waitFor({ timeout: 20000 });
      await r.tid(`bank-card-${bca.id}`).click();
      await r.tid("bank-ledger").waitFor();
      await r.tid("bank-ledger-edit").click();
      await r.tid("bank-form-name").waitFor();
      await r.idle(500);
      const opening = await r.tid("bank-form-opening").count();
      const jenis = await k9.teks(r, "bank-form-type-reason");
      await r.shot("k04-ubah-rekening-tanpa-saldo-awal");
      await r.page.keyboard.press("Escape");
      assert(!opening, "form ubah memuat Saldo Awal");
      return `form Ubah rekening BCA Operasional KSC: isian Saldo Awal tidak ada · ${jenis}`;
    });

    // ── K05: aturan berisiko tinggi wajib beralasan (tidak disimpan) ─────────────────────────────────────────────────
    await r.login("admin");
    await pilihPT(KSC);
    await step({ kode: "K05", bagian: "kesalahan_umum.2", peran: "Admin",
      klaim: "Lupa mengisi alasan pada aturan berisiko tinggi — tombol Simpan tidak aktif",
      harap: "Aturan Keuangan & Pajak › Tarif PPN (risiko tinggi): ubah nilai tanpa alasan → [Simpan] mati; isi alasan → [Simpan] aktif. Tidak disimpan (halaman dimuat ulang)" },
    async () => {
      const KUNCI = "tax.ppn_rate";
      await r.go("settings-cfg-finance", `&entity=${KSC}`);
      await r.tid("cfg-group-chips").waitFor({ timeout: 20000 });
      await r.tid("cfg-group-pajak-pembukuan").click();
      await r.tid("cfg-search").fill("PPN");
      await r.tid(`cfg-card-toggle-${KUNCI}`).click();
      const inp = r.tid(`cfg-input-${KUNCI}`);
      await inp.waitFor();
      const awal = await inp.inputValue();
      await inp.fill("11");
      await r.tid(`cfg-dirty-${KUNCI}`).waitFor();
      const tanpa = await r.tid(`cfg-save-${KUNCI}`).isDisabled();
      await r.shot("k05-tanpa-alasan");
      await r.tid(`cfg-reason-${KUNCI}`).fill("uji V9 — tidak disimpan");
      const dengan = await r.tid(`cfg-save-${KUNCI}`).isDisabled();
      await r.page.reload();
      await r.idle(1500);
      const tetap = mongo(`return (db.system_settings.find({key:"${KUNCI}"},{_id:0,scope:1,value:1}).toArray())`);
      assert(tanpa && !dengan, `Simpan mati tanpa alasan=${tanpa} · dengan alasan mati=${dengan}`);
      return `nilai ${awal} → 11: [Simpan] tanpa alasan ${tanpa ? "mati" : "aktif"}, dengan alasan ${dengan ? "mati" : "aktif"} · tidak disimpan (pengaturan tersimpan: ${JSON.stringify(tetap).slice(0, 120)})`;
    });
  } catch (e) {
    r.note("berhenti: " + e.message);
  }
  d.simpan();
  await r.finish();
})();
