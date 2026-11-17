// F05 — Rencana pembayaran (cicilan) & denda keterlambatan — data `b_piutang:cicilan` (pelanggan kedua peserta).
//   node docs/pelatihan/2026-11-18_keuangan/uji/F05_rencana_denda.js            (peserta bawaan 02)
//   KN_PESERTA=21 node docs/pelatihan/2026-11-18_keuangan/uji/F05_rencana_denda.js
const { Run, api, assert, kartu, peserta, akunPeserta, mongo, rp } = require("./lib");
const { KSC, bukaMenu, sorot, lepas, klikSorot } = require("./piutang_lib");
const { bersihkanHasil } = require("./piutang_lib");

const NO = peserta("02");
const r2 = (v) => Math.round(Number(v || 0) * 100) / 100;

(async () => {
  bersihkanHasil("F05");
  const r = await new Run("F05", "Rencana pembayaran (cicilan) & denda keterlambatan").start();
  const k = kartu(NO)["b_piutang:cicilan"];
  let pen = null;
  try {
    assert(k && k.so_id, `Kartu peserta ${NO} belum punya b_piutang:cicilan — jalankan seed … --hanya b_piutang:`);
    const plan = mongo(`return db.payment_plans.findOne({id:"${k.rencana_id}"},{_id:0})`);
    const l1 = plan.lines[0];
    const hariTelat = Math.round((Date.parse(new Date().toISOString().slice(0, 10)) - Date.parse(l1.due_date)) / 86400000);
    const sisa1 = r2(l1.amount - (l1.paid_amount || 0));
    const dendaHarap = r2(sisa1 * 0.02 * (hariTelat / 30));          // aturan bawaan: 2 %/bulan, tenggang 0, dasar = cicilan
    r.note(`Peserta ${NO} · ${k.pelanggan} · ${k.so} · ${k.rencana} · cicilan 1 ${sisa1} telat ${hariTelat} hari → denda ${dendaHarap}`);
    const sudah = mongo(`return db.penalties.countDocuments({plan_id:"${k.rencana_id}"})`);
    if (sudah > 0) throw new Error(`rencana ${k.rencana} sudah punya nota denda — pakai peserta segar`);

    await r.step(1, "Finance", "Masuk → Keuangan › Piutang › Rencana & Denda › tab Jadwal Pembayaran, cari 'Latihan NN'",
      `Baris ${k.rencana}: ${k.so}, mode 'Bebas / campuran', nilai ${rp(k.total)}, berikutnya ${l1.due_date} · ${rp(sisa1)}, tanda '1 telat'`,
      async () => {
        await r.login(akunPeserta(NO));
        await bukaMenu(r, "ar-aging", "payment-plans", { nama: "menu-rencana" });
        await klikSorot(r, r.tid("pp-tab-jadwal"), "tab-jadwal-pembayaran");
        await r.tid("pp-search").fill(`Latihan ${NO}`);
        const row = r.tid(`pp-plan-row-${k.rencana_id}`);
        await row.waitFor({ timeout: 15000 });
        await r.idle(800);
        const t = (await row.innerText()).replace(/\s+/g, " ");
        assert(t.includes(k.so) && /1 telat/.test(t) && t.includes(rp(sisa1).replace("Rp ", "")), `baris rencana: ${t}`);
        assert(/Aktif/.test(t), `status rencana belum berbahasa Indonesia: ${t}`);
        await sorot(row);
        await r.shot("rencana-jadwal");
        await lepas(row);
        return t;
      });

    await r.step(2, "Finance", "Klik ikon [Buka pesanan] di baris rencana → [Lihat detail & aksi] → panel 'Jadwal Pembayaran & Denda'",
      "Cicilan 1 berstatus terbuka & lewat jatuh tempo ('1 baris telat'); tombol [Hitung Denda] dan [Ubah Jadwal] tersedia",
      async () => {
        await klikSorot(r, r.tid(`pp-open-so-${k.rencana_id}`), "buka-pesanan");
        await r.tid("so-open-full-detail").waitFor({ timeout: 20000 });
        await r.idle(600);
        await klikSorot(r, r.tid("so-open-full-detail"), "lihat-detail-pesanan");
        const panel = r.tid("so-payment-panel");
        await panel.waitFor({ timeout: 20000 });
        await r.idle(1200);
        const t = (await panel.innerText()).replace(/\s+/g, " ");
        assert(/1 baris telat/.test(t) && t.includes("Cicilan 1"), `panel jadwal: ${t.slice(0, 300)}`);
        assert(await r.tid("sop-accrue").count() === 1 && await r.tid("sop-edit").count() === 1, "tombol Hitung Denda/Ubah Jadwal tidak ada");
        await sorot(panel);
        await r.shot("pesanan-jadwal-cicilan");
        await lepas(panel);
        return t.slice(0, 250);
      });

    await r.step(3, "Finance", "Tutup detail pesanan (×) → Keuangan › Piutang › tab Saldo & Umur → cari 'Cicilan NN' → klik barisnya",
      `Baris pelanggan: 'telat ${hariTelat} hr', kolom 1–30 hari ${rp(sisa1)}, Denda ${rp(dendaHarap)} 'est. — belum jadi nota'`, async () => {
        await r.page.keyboard.press("Escape");          // tutup jendela detail pesanan
        await r.idle(500);
        await bukaMenu(r, "ar-aging", "ar-aging", { nama: "menu-saldo-umur" });
        await r.tid("ar-aging-search").fill(`Cicilan ${NO}`);
        const row = r.tid(`ar-aging-row-${k.pelanggan_id}`);
        await row.waitFor({ timeout: 15000 });
        await r.idle(800);
        const t = (await row.innerText()).replace(/\s+/g, " ");
        assert(t.includes(`telat ${hariTelat} hr`) && t.includes(rp(dendaHarap).replace("Rp ", "")) && /belum jadi nota/.test(t),
          `baris umur: ${t}`);
        await sorot(r.tid(`ar-denda-cell-${k.pelanggan_id}`));
        await klikSorot(r, row, "umur-pelanggan-telat");
        await lepas(r.tid(`ar-denda-cell-${k.pelanggan_id}`));
        return t;
      });

    await r.step(4, "Finance", "Rincian pelanggan: baca Jadwal Tagihan & est. denda → klik [Buat Nota Denda]",
      `Cicilan 1 'Telat ${hariTelat} hari'; est. denda ${rp(dendaHarap)} belum jadi nota; tombol [Buat Nota Denda] aktif`, async () => {
        const m = r.tid("ar-aging-detail-modal");
        await m.waitFor();
        await r.idle(1200);
        const t = (await m.innerText()).replace(/\s+/g, " ");
        assert(t.includes("Cicilan 1") && t.includes(rp(dendaHarap).replace("Rp ", "")), `rincian: ${t.slice(0, 400)}`);
        assert(!(await r.tid("ar-aging-accrue").isDisabled()), "tombol Buat Nota Denda mati");
        await klikSorot(r, r.tid("ar-aging-accrue"), "umur-rincian-sebelum-nota");
        return t.slice(0, 250);
      });

    await r.step(5, "Finance", "Baca pesan hasil [Buat Nota Denda]",
      "Pesan '1 nota denda siap: DN-DENDA-… Nota masih USULAN — belum menyentuh buku besar'; tombol jadi mati + alasannya",
      async () => {
        await r.tid("ar-aging-accrue-notice").waitFor({ timeout: 20000 });
        await r.idle(1200);
        const msg = await r.text("ar-aging-accrue-notice");
        assert(/1 nota denda siap/.test(msg) && /USULAN/.test(msg), `pesan: ${msg}`);
        pen = mongo(`return db.penalties.findOne({plan_id:"${k.rencana_id}"},{_id:0})`);
        assert(pen && pen.status === "draft" && Math.abs(pen.amount - dendaHarap) < 1, `nota denda ${JSON.stringify(pen && { s: pen.status, a: pen.amount })}`);
        const jurnal = mongo(`return db.journal_entries.countDocuments({source_id:"${pen.id}"})`);
        assert(jurnal === 0, "nota usulan sudah berjurnal");
        assert(await r.tid("ar-aging-accrue").isDisabled(), "tombol Buat Nota Denda tidak mati sesudah semua denda jadi nota");
        const why = await r.text("ar-aging-accrue-reason");
        await sorot(r.tid("ar-aging-accrue-notice"));
        await sorot(r.tid("ar-aging-accrue-reason"));
        await r.shot("nota-denda-usulan");
        await lepas(r.tid("ar-aging-accrue-notice"));
        return `${msg} · ${pen.number} ${pen.amount} · alasan tombol mati: ${why}`;
      });

    await r.step(6, "Finance", "Tutup rincian → tab Rencana & Denda › Antrean Denda › saring 'Usulan (draf)' → baca nota → klik [Terbitkan]",
      `Nota ${"DN-DENDA-…"}: 'Cicilan 1 · jatuh tempo … · telat ${hariTelat} hari', nominal ${rp(dendaHarap)}, aturan 2%/bulan`, async () => {
        await r.page.keyboard.press("Escape");
        await r.idle(400);
        await klikSorot(r, r.tid("hub-tab-payment-plans"), "tab-rencana-denda");
        await r.tid("pp-tab-denda").click();
        await r.tid("pp-filter-draft").click();
        await r.tid("pp-search").fill(pen.number);
        const row = r.tid(`penalty-row-${pen.id}`);
        await row.waitFor({ timeout: 15000 });
        await r.idle(800);
        const t = (await row.innerText()).replace(/\s+/g, " ");
        assert(t.includes(`telat ${hariTelat} hari`) && t.includes(rp(pen.amount).replace("Rp ", "")), `baris nota: ${t}`);
        await sorot(row);
        await klikSorot(r, r.tid(`penalty-issue-${pen.id}`), "antrean-denda-usulan");
        await lepas(row);
        return t + " · rincian: " + (pen.explain || []).join(" | ");
      });

    await r.step(7, "Finance", "Konfirmasi [Terbitkan] → saring 'Terbit'",
      "Status nota berubah 'Terbit (berjurnal)'; KPI 'Denda terbit (belum dibayar)' bertambah", async () => {
        await r.tid("confirm-modal").waitFor();
        const msg = await r.text("confirm-modal-message");
        await klikSorot(r, r.tid("confirm-modal-confirm"), "konfirmasi-terbitkan");
        await r.page.waitForFunction((id) => !document.querySelector(`[data-testid="penalty-issue-${id}"]`), pen.id, { timeout: 20000 });
        await r.tid("pp-filter-issued").click();
        await r.tid(`penalty-row-${pen.id}`).waitFor({ timeout: 15000 });
        await r.idle(800);
        const t = (await r.tid(`penalty-row-${pen.id}`).innerText()).replace(/\s+/g, " ");
        assert(/Terbit/i.test(t), `baris sesudah terbit: ${t}`);
        await sorot(r.tid(`penalty-row-${pen.id}`));
        await r.shot("denda-terbit");
        return `${msg} → ${t}`;
      });

    await r.step(8, "Finance", "Cek buku: jurnal nota denda",
      `Piutang Denda (D) = Pendapatan Denda (K) = ${rp(dendaHarap)} — seimbang`, async () => {
        const p = mongo(`return db.penalties.findOne({id:"${pen.id}"},{_id:0})`);
        assert(p.status === "issued" && p.je_id, `status ${p.status} je ${p.je_id}`);
        const je = mongo(`return db.journal_entries.findOne({id:"${p.je_id}"},{_id:0})`);
        const d = je.lines.reduce((s, l) => s + Number(l.debit || 0), 0);
        const kr = je.lines.reduce((s, l) => s + Number(l.credit || 0), 0);
        assert(Math.abs(d - kr) < 0.01 && Math.abs(d - p.amount) < 0.01, `jurnal ${je.number} D ${d} K ${kr}`);
        const fin = await api(akunPeserta(NO));
        const det = await fin.get(`/penalties/${pen.id}`, KSC);
        return `${je.number}: ${je.lines.map((l) => `${l.account_code} ${l.account_name} D${l.debit} K${l.credit}`).join(" · ")} · status ${det.status_label || det.status}`;
      });
  } catch (e) {
    r.note("berhenti: " + e.message);
  }
  await r.finish();
})();
