// V1 — VARIASI isian "Terima pembayaran" (Piutang › Penagihan & Penerimaan, ReceivePaymentModal) lewat LAYAR dengan akun
// peserta, lalu cek BUKU (kwitansi, sisa SO, jurnal Bank D / Piutang K / Uang Muka 2-1400, saldo titipan).
//   KN_PESERTA=61 node docs/pelatihan/2026-11-18_keuangan/uji/variasi/V1_terima_pembayaran.js
// Butuh peserta SEGAR (so_lunas & so_sebagian belum dibayar): `seed_pelatihan_keuangan_kn.py --mulai 61 --peserta 61`.
// Kasus C6 memanggil `scripts.latih_keuangan.b_piutang --berikut NN` (tagihan berikutnya untuk memakai titipan).
const path = require("path");
const { execFileSync } = require("child_process");
const { Run, api, assert, kartu, peserta, akunPeserta, mongo, rp, sleep } = require("../lib");
const { KSC, bukaPenagihan, barisSo, sisaSo, jurnalKwitansi, cekJurnalSeimbang, pelangganPeserta, titipan, pilih,
  bersihkanHasil } = require("../piutang_lib");
const v = require("./vlib");

const NO = peserta("61");
const BACKEND = path.resolve(__dirname, "../../../../../backend");
const t = v.tabel("V1");
const L = "Terima pembayaran";
const idr = (n, dec = 2) => Number(n).toLocaleString("id-ID", { minimumFractionDigits: dec, maximumFractionDigits: dec });

(async () => {
  bersihkanHasil("V1");
  const r = await new Run("V1", "Variasi isian — Terima pembayaran pelanggan").start();
  const k = kartu(NO);
  const SL = k["a_dasar:so_lunas"]; const SS = k["a_dasar:so_sebagian"];
  const cust = pelangganPeserta(NO);
  const fin = await api(akunPeserta(NO));
  const jmlKwitansi = () => mongo(`return db.ar_receipts.countDocuments({customer_id:"${cust.id}",status:{$ne:"void"}})`);
  const form = async () => ({ total: await v.teksAtau(r, "ar-receipt-total"), reason: await v.teksAtau(r, "ar-receipt-reason"),
    hint: await v.teksAtau(r, "ar-receipt-variance-hint"), mati: await r.tid("ar-receipt-submit").isDisabled() });
  const tungguHint = async (re) => {
    await sleep(1300);   // penilaian selisih ditunda 450 ms + permintaan API: tunggu yang BARU, bukan petunjuk lama
    await r.page.waitForFunction((s) => new RegExp(s).test(
      (document.querySelector('[data-testid="ar-receipt-variance-hint"]') || {}).innerText || ""), re.source, { timeout: 10000 });
  };
  async function bukaForm(soId) {
    if (await r.tid("ar-receipt-modal").count()) { await r.tid("ar-receipt-cancel").click(); await r.idle(300); }
    await bukaPenagihan(r);
    await barisSo(r, soId);
    await r.tid(`collection-pay-${soId}`).click();
    await r.tid("ar-receipt-modal").waitFor();
    await r.tid(`ar-receipt-alloc-${soId}`).waitFor();
    await r.page.waitForFunction(() => !document.querySelector('[data-testid="ar-receipt-account-loading"]'));
    await r.idle(700);
  }
  /** Simpan → (dialog selisih: pilih `kind`) → konfirmasi Ya. → teks pemberitahuan. */
  let dobelInfo = "";
  async function simpan({ kind = "", reason = "", note = "", dobel = false } = {}) {
    if (dobel) {
      // Klik ganda: klik ke-2 jatuh di latar gelap dialog konfirmasi yang baru terbuka → dialog tertutup (= Batal).
      await r.tid("ar-receipt-submit").dblclick();
      await sleep(800);
      const terbuka = await r.tid("ar-receipt-confirm").count();
      dobelInfo = terbuka ? "dialog konfirmasi tetap terbuka" : "klik ganda menutup dialog konfirmasi (tidak tersimpan) → klik sekali lagi";
      if (!terbuka) await r.tid("ar-receipt-submit").click();
    } else await r.tid("ar-receipt-submit").click();
    if (kind) {
      await r.tid("payment-variance-dialog").waitFor();
      await r.tid(`pv-option-${kind}`).click();
      if (reason) await pilih(r, "pv-reason", reason);
      await r.tid("pv-note").fill(note || "uji variasi");
      await r.tid("pv-submit").click();
    }
    await r.tid("ar-receipt-confirm").waitFor();
    if (dobel) await r.tid("ar-receipt-confirm-confirm").dblclick({ timeout: 5000 }).catch(() => {});
    else await r.tid("ar-receipt-confirm-confirm").click();
    await r.tid("collection-notice").waitFor({ timeout: 20000 });
    await r.idle(600);
    return r.text("collection-notice");
  }
  const kwitansiBaru = (sejak) => mongo(`return db.ar_receipts.find({customer_id:"${cust.id}",status:{$ne:"void"},
    created_at:{$gt:"${sejak}"}},{_id:0}).sort({created_at:1}).toArray()`);
  const kini = () => mongo(`return new Date().toISOString()`);

  try {
    assert(SL && SS && cust, `Kartu peserta ${NO} belum lengkap — jalankan seed_pelatihan_keuangan_kn.py`);
    assert(Math.abs(sisaSo(SL.so_id) - SL.total) < 0.01 && Math.abs(sisaSo(SS.so_id) - SS.total) < 0.01,
      `SO peserta ${NO} sudah pernah dibayar — pakai peserta segar`);
    r.note(`Peserta ${NO} · ${SL.so} ${SL.total} · ${SS.so} ${SS.total} · pelanggan ${cust.name}`);
    await r.login(akunPeserta(NO));
    await bukaForm(SL.so_id);
    const sisaL = sisaSo(SL.so_id);
    const alloc = `ar-receipt-alloc-${SL.so_id}`;

    // ── A. Kotak alokasi "Atur sendiri" (form dibuka dari baris SO lunas) ─────────────────────────────────────────
    await v.kasus(r, t, { layar: L, isian: "Alokasi ke tagihan (Atur sendiri)", masukan: "ketik 9.999.999 (di atas sisa)",
      harap: `Kotak dibatasi = sisa ${rp(sisaL)}; 'Nominal sesuai tagihan — tidak ada selisih'`, hasil: "lulus" }, async () => {
      await v.ketik(r, alloc, "9.999.999");
      await tungguHint(/tidak ada selisih/);
      const f = await form();
      assert(Math.abs(Number(await r.tid(alloc).inputValue()) - sisaL) < 0.01 && f.total === rp(sisaL), JSON.stringify(f));
      return `${await r.tid(alloc).inputValue()} · ${f.total}`;
    });
    await v.kasus(r, t, { layar: L, isian: "Alokasi ke tagihan", masukan: "tempel 'Rp 9.999.999'",
      harap: `Diterima, dibatasi = sisa ${rp(sisaL)}`, hasil: "diperbaiki",
      catatan: "Dulu tempelan bertitik/berawalan Rp ditolak diam-diam (kotak tetap 0)." }, async () => {
      await v.ketik(r, alloc, "Rp 9.999.999", { tempel: true });
      await tungguHint(/tidak ada selisih/);
      const f = await form();
      assert(f.total === rp(sisaL), JSON.stringify(f));
      return f.total;
    });
    await v.kasus(r, t, { layar: L, isian: "Alokasi ke tagihan", masukan: "ketik 1.000.000,50",
      harap: "Total diterima Rp 1.000.001 (1.000.000,50); petunjuk 'Kurang bayar …'", hasil: "diperbaiki",
      catatan: "Dulu koma membuat kotak jadi 0 lalu digit berikutnya → Rp 50 (nominal salah). Kini MoneyInput membaca koma desimal." }, async () => {
      await v.ketik(r, alloc, "1.000.000,50");
      await tungguHint(/Kurang bayar/);
      const f = await form();
      assert(await r.tid(alloc).inputValue() === "1.000.000,50" && f.total === "Rp 1.000.001", JSON.stringify(f));
      assert(f.hint.includes(rp(sisaL - 1000000.5).replace("Rp ", "")), `selisih: ${f.hint}`);
      return f.hint;
    });
    await v.kasus(r, t, { layar: L, isian: "Alokasi ke tagihan", masukan: "ketik 1,500,000 (gaya Inggris)",
      harap: "Dibaca Rp 1.500.000", hasil: "diperbaiki", catatan: "Dulu tiap koma me-nol-kan kotak → Rp 0/Rp 123." }, async () => {
      await v.ketik(r, alloc, "1,500,000");
      await tungguHint(/Kurang bayar/);
      const f = await form();
      assert(f.total === "Rp 1.500.000", JSON.stringify(f));
      return f.total;
    });
    await v.kasus(r, t, { layar: L, isian: "Alokasi ke tagihan", masukan: `ketik sisa persis bergaya Indonesia ${idr(sisaL)}`,
      harap: `Total = ${rp(sisaL)}; tidak ada selisih`, hasil: "diperbaiki", catatan: "Dulu → Rp 50." }, async () => {
      await v.ketik(r, alloc, idr(sisaL));
      await tungguHint(/tidak ada selisih/);
      const f = await form();
      assert(f.total === rp(sisaL) && !f.mati, JSON.stringify(f));
      return `${await r.tid(alloc).inputValue()} · ${f.total}`;
    });
    for (const [mas, harap, ket] of [["0", "Tombol mati + 'Isi nominal diterima.'", ""],
      ["(kosongkan)", "Tombol mati + 'Isi nominal diterima.'", ""],
      ["abc", "Huruf tidak masuk; tombol mati + 'Isi nominal diterima.'", ""]]) {
      await v.kasus(r, t, { layar: L, isian: "Alokasi ke tagihan", masukan: mas, harap, hasil: "lulus", catatan: ket }, async () => {
        await v.ketik(r, alloc, mas === "(kosongkan)" ? "" : mas);
        await sleep(700);
        const f = await form();
        assert(f.mati && /Isi nominal diterima/.test(f.reason), JSON.stringify(f));
        return `${JSON.stringify(await r.tid(alloc).inputValue())} · ${f.reason}`;
      });
    }
    await v.kasus(r, t, { layar: L, isian: "Alokasi ke tagihan", masukan: "ketik -100",
      harap: "Minus tidak bisa masuk kotak alokasi (tidak pernah tersimpan negatif); yang tampil & dihitung Rp 100", hasil: "lulus",
      catatan: "Tanda minus diabaikan → Rp 100 terlihat di Total & petunjuk Kurang bayar." }, async () => {
      await v.ketik(r, alloc, "-100");
      await tungguHint(/Kurang bayar/);
      const f = await form();
      assert(f.total === "Rp 100", JSON.stringify(f));
      return f.total;
    });

    // ── B. "Tertua dulu": Nominal diterima ────────────────────────────────────────────────────────────────────────
    await r.tid("ar-receipt-mode-auto").click();
    await r.tid("ar-receipt-amount").waitFor();
    const terbuka = sisaL + sisaSo(SS.so_id);
    const kasusB = [
      ["ketik", "3.374.123", "Rp 3.374.123", "diperbaiki", "Dulu terketik '3.374123' = Rp 3 (nominal salah tanpa peringatan)."],
      ["ketik", "3374123", "Rp 3.374.123", "lulus", ""],
      ["ketik", "3,374,123", "Rp 3.374.123", "diperbaiki", "Dulu '3,374123' → Rp 0, tombol mati."],
      ["ketik", "3374122,5", "Rp 3.374.123", "diperbaiki", "Dulu pratinjau Rp 3.374.123 tetapi Total Rp 0 & 'Isi nominal diterima.'"],
      ["ketik", "3.374.122,50", "Rp 3.374.123", "diperbaiki", "Dulu → Rp 3."],
      ["tempel", "Rp 3.374.123", "Rp 3.374.123", "diperbaiki", "Dulu tempelan ditolak diam-diam."],
      ["tempel", "Rp 3 374 123", "Rp 3.374.123", "diperbaiki", "Dulu ditolak / Rp 0."],
      ["tempel", "3.374.123,-", "Rp 3.374.123", "diperbaiki", "Gaya kwitansi 'Rp …,-'."],
    ];
    for (const [cara, mas, harapTotal, hasil, catatan] of kasusB) {
      await v.kasus(r, t, { layar: L, isian: "Nominal diterima (Tertua dulu)", masukan: `${cara} ${mas}`,
        harap: `Total diterima ${harapTotal}; kotak berisi '${mas.replace(/^Rp\s*/, "")}' (awalan Rp dibuang — kotak sudah berlabel Rp); petunjuk selisih`, hasil, catatan }, async () => {
        await v.ketik(r, "ar-receipt-amount", mas, { tempel: cara === "tempel" });
        await tungguHint(/bayar|selisih/);
        const f = await form();
        const isi = await r.tid("ar-receipt-amount").inputValue();
        assert(f.total === harapTotal && !f.mati && isi === mas.replace(/^Rp\s*/, ""), `${JSON.stringify(f)} · kotak '${isi}'`);
        return `${f.total} · ${f.hint.slice(0, 90)}`;
      });
    }
    await v.kasus(r, t, { layar: L, isian: "Nominal diterima", masukan: "ketik -100",
      harap: "Kotak bergaris merah, tombol mati + 'Nominal tidak boleh minus.'", hasil: "diperbaiki",
      catatan: "Dulu alasannya 'Isi nominal diterima.' padahal nominal sudah diisi." }, async () => {
      await v.ketik(r, "ar-receipt-amount", "-100");
      await sleep(600);
      const f = await form();
      assert(f.mati && /tidak boleh minus/.test(f.reason), JSON.stringify(f));
      return f.reason;
    });
    await v.kasus(r, t, { layar: L, isian: "Nominal diterima", masukan: "ketik abc",
      harap: "Huruf tidak masuk; tombol mati + 'Isi nominal diterima.'", hasil: "lulus" }, async () => {
      await v.ketik(r, "ar-receipt-amount", "abc");
      await sleep(600);
      const f = await form();
      assert(f.mati && (await r.tid("ar-receipt-amount").inputValue()) === "" && /Isi nominal/.test(f.reason), JSON.stringify(f));
      return f.reason;
    });
    await v.kasus(r, t, { layar: L, isian: "Nominal diterima", masukan: "ketik 99.999.999.999 → [Simpan kwitansi] → [Batal] di dialog selisih",
      harap: "Total Rp 99.999.999.999; petunjuk 'Lebih bayar …'; Simpan → dialog 'Lebih bayar' wajib diputus; Batal → tidak ada kwitansi",
      hasil: "keputusan", catatan: "Dulu terketik Rp 100. Kini terbaca benar, tetapi TIDAK ada batas atas/peringatan khusus untuk lebih bayar raksasa (salah ketik nol) — hanya dialog selisih + kalimat konfirmasi. Pertanyaan pemilik: perlu batas/peringatan lebih bayar > X?" }, async () => {
      const n0 = jmlKwitansi();
      await v.ketik(r, "ar-receipt-amount", "99.999.999.999");
      await tungguHint(/Lebih bayar/);
      const f = await form();
      assert(f.total === "Rp 99.999.999.999", JSON.stringify(f));
      await r.tid("ar-receipt-submit").click();
      await r.tid("payment-variance-dialog").waitFor();
      const kal = await r.text("pv-sentence");
      await r.tid("pv-cancel").click();
      await r.tid("payment-variance-dialog").waitFor({ state: "detached" });
      assert(jmlKwitansi() === n0, "kwitansi tercatat padahal dibatalkan");
      assert(!(await r.tid("ar-receipt-submit").isDisabled()), "tombol simpan macet sesudah batal");
      return `${f.hint.slice(0, 80)} · dialog: ${kal.slice(0, 120)}`;
    });
    await v.kasus(r, t, { layar: L, isian: "Tombol [Batal] form", masukan: "isi 1.000.000 lalu klik [Batal]",
      harap: "Form tertutup, tidak ada kwitansi baru", hasil: "lulus" }, async () => {
      const n0 = jmlKwitansi();
      await v.ketik(r, "ar-receipt-amount", "1.000.000");
      await r.tid("ar-receipt-cancel").click();
      await r.tid("ar-receipt-modal").waitFor({ state: "detached" });
      assert(jmlKwitansi() === n0, "kwitansi bertambah");
      return "form tertutup";
    });
    await v.kasus(r, t, { layar: L, isian: "No. referensi", masukan: "(kosong)",
      harap: "Boleh kosong (pengaturan 'payment.wajib_nomor_referensi' bawaan mati) — tombol tetap aktif", hasil: "lulus",
      catatan: "Catatan kode: form membaca `settings/effective → payment.wajib_nomor_referensi`, kunci itu tidak dikirim endpoint (penanda 'wajib' di layar tidak pernah menyala); backend tetap menolak dengan pesan Indonesia bila pengaturan dinyalakan." }, async () => {
      await bukaForm(SS.so_id);
      await v.ketik(r, `ar-receipt-alloc-${SS.so_id}`, "500.000");
      await tungguHint(/Kurang bayar/);
      assert(!(await r.tid("ar-receipt-submit").isDisabled()), "tombol mati tanpa referensi");
      return "aktif";
    });

    // ── C. Disimpan + cek buku ────────────────────────────────────────────────────────────────────────────────────
    await v.kasus(r, t, { layar: L, isian: "Alokasi SO kedua + keputusan 'Sisa tetap jadi piutang'", masukan: "ketik 1.000.000,50",
      harap: "Kwitansi tepat Rp 1.000.000,50; jurnal 1-1100 D = 1-1200 K = 1.000.000,50; sisa SO = total − 1.000.000,50",
      hasil: "diperbaiki" }, async () => {
      const t0 = kini(); const s0 = sisaSo(SS.so_id);
      await v.ketik(r, `ar-receipt-alloc-${SS.so_id}`, "1.000.000,50");
      await r.tid("ar-receipt-reference").fill(`V1-${NO}-C1`);
      await tungguHint(/Kurang bayar/);
      const note = await simpan({ kind: "outstanding", reason: "Bayar sebagian (disepakati)" });
      const rc = kwitansiBaru(t0);
      assert(rc.length === 1 && rc[0].amount === 1000000.5, `kwitansi ${JSON.stringify(rc.map((x) => x.amount))}`);
      cekJurnalSeimbang(jurnalKwitansi(rc[0]), [["1-1100", "D", 1000000.5], ["1-1200", "K", 1000000.5]]);
      const harap = v.r2(s0 - 1000000.5);
      assert(Math.abs(sisaSo(SS.so_id) - harap) < 0.01, `sisa ${sisaSo(SS.so_id)} ≠ ${harap}`);
      const row = (await (await barisSo(r, SS.so_id)).innerText()).replace(/\s+/g, " ");
      assert(row.includes(rp(harap).replace("Rp ", "")), `baris: ${row}`);
      return `${note} · sisa ${harap}`;
    });
    await v.kasus(r, t, { layar: L, isian: "Alokasi SO lunas + klik ganda [Simpan kwitansi] & [Ya, simpan]",
      masukan: `tempel 'Rp ${idr(sisaL)}'`, harap: "Tepat SATU kwitansi = sisa; SO lunas; jurnal seimbang", hasil: "lulus",
      catatan: "Tidak pernah dobel (inFlight + kunci idempotensi). Tetapi klik ganda [Simpan kwitansi] membuat klik ke-2 jatuh di latar dialog konfirmasi → dialog langsung tertutup (= Batal), peserta harus klik lagi. Akar: utils/overlayDismiss.js (di luar area perbaikan) — usulan patch di laporan." }, async () => {
      const t0 = kini();
      await bukaForm(SL.so_id);
      await v.ketik(r, alloc, `Rp ${idr(sisaL)}`, { tempel: true });
      await r.tid("ar-receipt-reference").fill(`V1-${NO}-C2`);
      await tungguHint(/tidak ada selisih/);
      const note = await simpan({ dobel: true });
      await sleep(1500);
      const rc = kwitansiBaru(t0);
      assert(rc.length === 1 && Math.abs(rc[0].amount - sisaL) < 0.01, `kwitansi baru ${rc.length}: ${JSON.stringify(rc.map((x) => x.amount))}`);
      assert(sisaSo(SL.so_id) <= 0.01, "SO belum lunas");
      cekJurnalSeimbang(jurnalKwitansi(rc[0]), [["1-1100", "D", sisaL], ["1-1200", "K", sisaL]]);
      return `${dobelInfo} · ${note}`;
    });
    const besok = mongo(`return new Date(Date.now()+7*3600e3+35*86400e3).toISOString().slice(0,10)`);
    await v.kasus(r, t, { layar: L, isian: "Tanggal terima di MASA DEPAN", masukan: `${besok} · alokasi 200.000`,
      harap: "Ditolak dengan pesan jelas ATAU diterima bertanggal itu (aturan pemilik)", hasil: "keputusan",
      catatan: "Tidak ada penjaga tanggal masa depan di form maupun backend (kalender tidak membatasi). Kwitansi & jurnal bertanggal masa depan. Pertanyaan pemilik: tolak/peringatkan tanggal > hari ini?" }, async () => {
      const t0 = kini();
      await bukaForm(SS.so_id);
      await v.ketik(r, `ar-receipt-alloc-${SS.so_id}`, "200.000");
      await v.pilihTanggal(r, "ar-receipt-date", besok);
      await r.tid("ar-receipt-reference").fill(`V1-${NO}-C3`);
      await tungguHint(/Kurang bayar/);
      const note = await simpan({ kind: "outstanding", reason: "Bayar sebagian (disepakati)" });
      const rc = kwitansiBaru(t0);
      assert(rc.length === 1 && rc[0].amount === 200000, "kwitansi masa depan");
      const je = jurnalKwitansi(rc[0]);
      cekJurnalSeimbang(je, [["1-1100", "D", 200000], ["1-1200", "K", 200000]]);
      return `DITERIMA: ${note} · tanggal kwitansi ${String(rc[0].receipt_date).slice(0, 10)} · jurnal ${je.number} ${String(je.date).slice(0, 10)}`;
    });
    await v.kasus(r, t, { layar: L, isian: "Tanggal terima di periode TERTUTUP", masukan: "15 Sep 2026 (periode Sep 2026 ditutup sementara untuk uji) · alokasi 100.000",
      harap: "Ditolak di dalam form: 'Periode … sudah DITUTUP …'; tidak ada kwitansi; tombol tidak macet", hasil: "lulus" }, async () => {
      const n0 = jmlKwitansi();
      const cid = `pcl_uji_v1_${NO}`;
      mongo(`db.period_closings.insertOne({id:"${cid}",entity_id:"${KSC}",period_type:"month",period_key:"2026-09",
        period_label:"September 2026",start_date:"2026-09-01",end_date:"2026-09-30",status:"closed",stale:false,note:"uji variasi V1"}); return 1`);
      try {
        await bukaForm(SS.so_id);
        await v.ketik(r, `ar-receipt-alloc-${SS.so_id}`, "100.000");
        await v.pilihTanggal(r, "ar-receipt-date", "2026-09-15");
        await tungguHint(/Kurang bayar/);
        await r.tid("ar-receipt-submit").click();
        await r.tid("payment-variance-dialog").waitFor();
        await r.tid("pv-option-outstanding").click();
        await pilih(r, "pv-reason", "Bayar sebagian (disepakati)");
        await r.tid("pv-note").fill("uji periode tertutup");
        await r.tid("pv-submit").click();
        await r.tid("ar-receipt-confirm").waitFor();
        await r.tid("ar-receipt-confirm-confirm").click();
        const err = r.tid("ar-receipt-modal").getByText(/DITUTUP/);
        await err.first().waitFor({ timeout: 15000 });
        const msg = (await err.first().innerText()).replace(/\s+/g, " ");
        assert(jmlKwitansi() === n0, "kwitansi tercatat di periode tertutup");
        assert(!(await r.tid("ar-receipt-submit").isDisabled()), "tombol macet");
        return msg.slice(0, 200);
      } finally {
        mongo(`db.period_closings.deleteOne({id:"${cid}"}); return 1`);
      }
    });
    const sisaS = sisaSo(SS.so_id);
    const LEBIH = 250000;
    const transfer = v.r2(sisaS + LEBIH);
    await v.kasus(r, t, { layar: L, isian: "Nominal diterima (Tertua dulu) di atas sisa → 'Simpan sebagai deposit'",
      masukan: `ketik ${idr(transfer)}`, harap: `Kwitansi ${rp(transfer)}: jurnal 1-1100 D ${idr(transfer)} · 1-1200 K ${idr(sisaS)} · 2-1400 K ${idr(LEBIH)}; titipan pelanggan +${idr(LEBIH)}`,
      hasil: "diperbaiki", catatan: "Dulu '…,xx' bertitik terketik salah (Rp 3/0)." }, async () => {
      const t0 = kini(); const tit0 = titipan(cust.id);
      await bukaForm(SS.so_id);
      await r.tid("ar-receipt-mode-auto").click();
      await v.ketik(r, "ar-receipt-amount", idr(transfer));
      await r.tid("ar-receipt-reference").fill(`V1-${NO}-C5`);
      await tungguHint(/Lebih bayar/);
      const note = await simpan({ kind: "deposit", reason: "Pelanggan transfer berlebih" });
      const rc = kwitansiBaru(t0);
      assert(rc.length === 1 && Math.abs(rc[0].amount - transfer) < 0.01, `kwitansi ${JSON.stringify(rc.map((x) => x.amount))}`);
      cekJurnalSeimbang(jurnalKwitansi(rc[0]), [["1-1100", "D", transfer], ["1-1200", "K", sisaS], ["2-1400", "K", LEBIH]]);
      assert(Math.abs(titipan(cust.id) - (tit0 + LEBIH)) < 0.01, `titipan ${titipan(cust.id)} ≠ ${tit0 + LEBIH}`);
      // Saldo titipan dihitung ulang dari kwitansi: Σ tak teralokasi − Σ titipan terpakai (bukan dari angka layanan).
      const hit = mongo(`let s=0; db.ar_receipts.find({customer_id:"${cust.id}",status:{$ne:"void"}}).forEach(x=>{s+=(x.unapplied_amount||0)-(x.used_deposit||0)}); return Math.round(s*100)/100`);
      assert(Math.abs(hit - titipan(cust.id)) < 0.01, `titipan dihitung ${hit} ≠ dokumen ${titipan(cust.id)}`);
      return `${note} · titipan ${titipan(cust.id)} (hitung ulang ${hit})`;
    });
    let berikut = null;
    await v.kasus(r, t, { layar: L, isian: "Pakai titipan — nominal titipan", masukan: "centang 'Pakai titipan', ketik 999.999 (di atas tersedia)",
      harap: `Kotak titipan dibatasi = tersedia ${rp(LEBIH)}`, hasil: "lulus" }, async () => {
      execFileSync(process.env.KN_PY || "python3", ["-m", "scripts.latih_keuangan.b_piutang", "--berikut", String(Number(NO))],
        { cwd: BACKEND, env: process.env, timeout: 300000 });
      berikut = kartu(NO)["b_piutang:so_berikut"];
      assert(berikut && berikut.so_id, "so_berikut tidak terbentuk");
      await bukaForm(berikut.so_id);
      await r.tid("ar-receipt-use-deposit").check();
      await v.ketik(r, "ar-receipt-deposit-amount", "999.999");
      await sleep(500);
      const val = await r.tid("ar-receipt-deposit-amount").inputValue();
      assert(Number(val) === LEBIH, `kotak titipan ${val}`);
      return `${berikut.so} · kotak titipan ${val}`;
    });
    await v.kasus(r, t, { layar: L, isian: "Pakai titipan sebagian", masukan: "ketik 100.000 di kotak titipan",
      harap: `Nominal diterima = total SO − 100.000; jurnal 1-1100 D + 2-1400 D 100.000 = 1-1200 K total; titipan tersisa ${rp(LEBIH - 100000)}`,
      hasil: "lulus" }, async () => {
      const t0 = kini();
      await v.ketik(r, "ar-receipt-deposit-amount", "100.000");
      await r.tid("ar-receipt-reference").fill(`V1-${NO}-C7`);
      const uang = v.r2(berikut.total - 100000);
      await r.page.waitForFunction((s) => (document.querySelector('[data-testid="ar-receipt-amount-manual"]') || {}).innerText === s,
        rp(uang).replace(" ", " "), { timeout: 8000 }).catch(() => {});
      const nom = await r.text("ar-receipt-amount-manual");
      assert(nom === rp(uang), `nominal ${nom} ≠ ${rp(uang)}`);
      await tungguHint(/tidak ada selisih/);
      const note = await simpan();
      const rc = kwitansiBaru(t0);
      assert(rc.length === 1 && Math.abs(rc[0].amount - uang) < 0.01 && Math.abs(rc[0].used_deposit - 100000) < 0.01,
        JSON.stringify(rc.map((x) => ({ a: x.amount, d: x.used_deposit }))));
      cekJurnalSeimbang(jurnalKwitansi(rc[0]), [["1-1100", "D", uang], ["2-1400", "D", 100000], ["1-1200", "K", berikut.total]]);
      assert(Math.abs(titipan(cust.id) - (LEBIH - 100000)) < 0.01, `titipan ${titipan(cust.id)}`);
      return `${note} · titipan ${titipan(cust.id)}`;
    });
    const det = await fin.get(`/ar-receipts/open-orders?customer_id=${cust.id}`, KSC);
    r.note(`tagihan terbuka tersisa: ${det.map((o) => `${o.number} ${o.outstanding}`).join(", ") || "-"}`);
  } catch (e) {
    r.note("berhenti: " + e.message);
  }
  t.simpan();
  await r.finish();
})();
