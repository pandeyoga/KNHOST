// V5 — Variasi isian BAYAR TAGIHAN SUPPLIER (F11 · Keuangan › Hutang › Tagihan › [Bayar]).
// Pertanyaan pemilik: "kalau peserta mengetik nominal dengan cara lain, apakah tidak galat dan hitungannya benar?"
// Setiap kasus = satu langkah: masukan PERSIS yang diketik (huruf demi huruf) → yang harus terjadi di layar → cek buku.
//   KN_PESERTA=71 KN_PESERTA2=72 node docs/pelatihan/2026-11-18_keuangan/uji/variasi/V5_bayar_tagihan.js
// Peserta 1 (bawaan 71): kasus format (tanpa simpan), bayar sebagian dari Kas Toko, sisa dengan klik ganda.
// Peserta 2 (bawaan 72): lebih bayar dalam toleransi, tanggal bayar di masa depan (dibatalkan lagi), kurang bayar receh.
const { Run, assert, rp, num, kartu, akunPeserta, mongo, api } = require("../lib");
const { REK_BCA, pilih, setuju, cekJurnal, tungguTeks } = require("../hutang_lib");
const { ketik, pilihTanggal, intipKonfirmasi, rpLayar, Tabel, jurnalSumber } = require("./hpg_lib");

const P1 = String(process.env.KN_PESERTA || "71").padStart(2, "0");
const P2 = String(process.env.KN_PESERTA2 || "72").padStart(2, "0");
const REK_KAS = "Kas Toko KSC";
const LAYAR = "Hutang › Tagihan › Bayar pemasok";
const tabel = new Tabel("V5");

const bill = (id) => mongo(`return db.vendor_bills.findOne({id:"${id}"},{_id:0})`);
const kasDari = (ids) => mongo(`return db.cash_transactions.find({id:{$in:${JSON.stringify(ids)}}},{_id:0}).toArray()`) || [];

async function bukaTagihan(r, no, tg) {
  await r.login(akunPeserta(no));
  await r.go("vendor-bills", "&entity=ent_ksc");
  await r.tid("vendor-bills-view").waitFor();
  await r.tid("vb-search").fill(`Latihan ${no}`);
  await r.idle(900);
  await r.tid(`vb-open-${tg.tagihan_id}`).click();
  await r.tid("vendor-bill-detail-panel").waitFor();
  await r.idle(500);
}
async function bukaForm(r) {
  await r.tid("vb-action-pay").click();
  await r.tid("pay-supplier-modal").waitFor();
  await r.tid("pay-supplier-number").waitFor();
  await r.idle(300);
}
const alasan = async (r) => (await r.tid("pay-supplier-reason").innerText().catch(() => "")).trim();
const pratinjau = async (r) => (await r.tid("pay-supplier-amount-preview").innerText().catch(() => "")).replace(/\s+/g, " ").trim();
/** Rupiah dengan sen bila ada (konfirmasi form Bayar pemasok tidak membulatkan sen). */
const rpSen = (n) => "Rp " + Number(n).toLocaleString("id-ID", { maximumFractionDigits: 2 });
const INGGRIS = /\b(error|failed|invalid|exceed|must|undefined|NaN|null)\b/i;

/** Satu kasus format nominal: ketik → (harap angka) konfirmasi menyebut nominal itu lalu Batal · (harap null) ditolak. */
async function kasusFormat(r, no, masukan, harap, catatan = "") {
  const ok = await r.step(no, "Finance", `Ketik di *Nominal dibayar*: "${masukan}"`,
    harap === null ? "Tombol [[Bayar]] mati dengan alasan berbahasa Indonesia; tidak ada yang tersimpan"
      : `Pratinjau & konfirmasi menyebut ${rpSen(harap)} (lalu [[Batal]])`, async () => {
      const v = await ketik(r, "pay-supplier-amount", masukan);
      const pv = await pratinjau(r);
      const dis = await r.tid("pay-supplier-submit").isDisabled();
      const why = await alasan(r);
      if (harap === null) {
        assert(dis, `tombol Bayar AKTIF untuk "${masukan}" (kotak "${v}", pratinjau "${pv}")`);
        assert(why && !INGGRIS.test(why), `alasan tombol mati: "${why}"`);
        return `kotak "${v}" · pratinjau "${pv || "—"}" · tombol mati: "${why}"`;
      }
      assert(!dis, `tombol Bayar mati untuk "${masukan}" (kotak "${v}", pratinjau "${pv}", alasan "${why}")`);
      assert(Math.abs(num(pv) - harap) <= 0.5, `pratinjau "${pv}" ≠ ${rpSen(harap)}`);
      const msg = await intipKonfirmasi(r, "pay-supplier-submit", "pay-supplier-confirm");
      assert(msg.includes(rpSen(harap).replace("Rp ", "")), `konfirmasi "${msg}" tidak menyebut ${rpSen(harap)}`);
      return `kotak "${v}" · pratinjau "${pv}" · konfirmasi "${msg.slice(0, 90)}…"`;
    });
  tabel.add({ layar: LAYAR, isian: "Nominal dibayar", masukan, harap: harap === null ? "ditolak dengan alasan Indonesia"
    : `terbaca ${rpSen(harap)}`, hasil: ok ? (catatan.startsWith("diperbaiki") ? "diperbaiki" : "lulus") : "gagal",
  catatan: (catatan.replace(/^diperbaiki:?\s*/, "") || "") + (ok ? "" : ` · GAGAL: ${r.steps[r.steps.length - 1].info}`) });
}

(async () => {
  const r = await new Run("V5", "Variasi isian — bayar tagihan supplier (F11)").start();
  const k1 = kartu(P1)["a_dasar:tagihan_bayar"];
  const k2 = kartu(P2)["a_dasar:tagihan_bayar"];
  try {
    assert(k1 && k2, `kartu peserta ${P1}/${P2} belum punya a_dasar:tagihan_bayar`);
    const b1 = bill(k1.tagihan_id);
    const TOTAL = Number(b1.grand_total);
    assert(b1.status === "posted" && !Number(b1.amount_paid), `tagihan ${k1.tagihan} peserta ${P1} sudah dipakai (${b1.status}, dibayar ${b1.amount_paid})`);
    r.note(`Peserta ${P1}: ${k1.tagihan} ${rp(TOTAL)} · peserta ${P2}: ${k2.tagihan}`);

    await r.step(1, "Finance", `Login finance.latih${P1} → Hutang › Tagihan → ${k1.tagihan} → [[Bayar]] → *Rekening sumber* ${REK_BCA}`,
      `Form terbuka, Sisa hutang ${rpLayar(TOTAL)}, nominal terisi penuh`, async () => {
        await bukaTagihan(r, P1, k1);
        await bukaForm(r);
        await pilih(r, "pay-supplier-account", REK_BCA);
        assert(num(await r.text("pay-supplier-outstanding")) === TOTAL, "sisa hutang ≠ total");
        return `nominal awal "${await r.tid("pay-supplier-amount").inputValue()}"`;
      });

    // ── Format nominal (tidak disimpan) ──────────────────────────────────────────────────────────────────────────
    const T = TOTAL;
    const fmt = (n) => n.toLocaleString("id-ID");
    const en = (n) => n.toLocaleString("en-US");
    await kasusFormat(r, 2, fmt(T), T, "diperbaiki: dulu diketik jadi \"1.864800\" = Rp 1,86 (MoneyInput, perbaikan agen Piutang)");
    await kasusFormat(r, 3, String(T), T);
    await kasusFormat(r, 4, en(T), T, "diperbaiki: dulu \"1,864800\" → tombol mati \"Isi nominal dibayar.\"");
    await kasusFormat(r, 5, `Rp ${fmt(T)}`, T, "diperbaiki: dulu \" 1.864800\" = Rp 1,86");
    await kasusFormat(r, 6, `Rp${T}`, T);
    await kasusFormat(r, 7, fmt(T).replace(/\./g, " "), T, "diperbaiki: pratinjau benar tetapi tombol mati (Number(\"1 864 800\") = NaN)");
    await kasusFormat(r, 8, `${fmt(T)},00`, T, "diperbaiki: dulu \"1.86480000\" = Rp 1,86");
    await kasusFormat(r, 9, `${fmt(T - 100000)},50`, T - 100000 + 0.5, "diperbaiki: koma sen dulu terbaca 0 (\"Isi nominal dibayar.\")");
    await kasusFormat(r, 10, "0", null);
    await kasusFormat(r, 11, "", null);
    await kasusFormat(r, 12, "-500000", null, "tanda minus: ditolak");
    await kasusFormat(r, 13, "abc", null, "huruf tidak masuk ke kotak");
    await kasusFormat(r, 14, fmt(T + 100), null,
      "diperbaiki: dulu DITERIMA diam-diam — kelebihan Rp 100 (≤ toleransi selisih Rp 5.000) menjadi kas keluar kedua \"uang muka supplier\" tanpa pemberitahuan");
    await kasusFormat(r, 15, fmt(2000000), null,
      "diperbaiki: dulu ditolak server dengan \"Pembayaran (2000000.0) melebihi sisa hutang (1864800.0) … pilih keputusan 'Kelebihan jadi uang muka supplier'\" — pilihan itu tidak ada di form");

    // ── Bayar sebagian dari Kas Toko, lalu sisanya dengan klik ganda ─────────────────────────────────────────────
    let pay1 = null;
    const SEBAGIAN = 500000;
    let ok = await r.step(16, "Finance", `Ketik "500.000" · *Rekening sumber* ${REK_KAS} → [[Bayar]] → [[Ya, bayar]]`,
      `Bayar sebagian Rp 500.000: status tetap Terposting, Sudah Dibayar Rp 500.000, Sisa Hutang ${rpLayar(TOTAL - SEBAGIAN)}; jurnal Hutang Usaha (D) / Kas Kecil (K) Rp 500.000`, async () => {
        await ketik(r, "pay-supplier-amount", "500.000");
        await pilih(r, "pay-supplier-account", REK_KAS);
        const msg = await intipKonfirmasi(r, "pay-supplier-submit", "pay-supplier-confirm", { batal: false });
        assert(msg.includes("500.000") && msg.includes(REK_KAS), `konfirmasi: ${msg}`);
        await setuju(r, "pay-supplier-confirm");
        await r.tid("pay-supplier-modal").waitFor({ state: "detached", timeout: 20000 });
        await tungguTeks(r, "vb-fin-paid", /500\.000/);
        assert(/Terposting/.test(await r.text("vb-detail-status")), `status ${await r.text("vb-detail-status")}`);
        assert(num(await r.text("vb-fin-outstanding")) === TOTAL - SEBAGIAN, `sisa layar ${await r.text("vb-fin-outstanding")}`);
        const b = bill(k1.tagihan_id);
        assert(b.status === "posted" && Math.abs(b.amount_paid - SEBAGIAN) < 0.01, `DB ${b.status} dibayar ${b.amount_paid}`);
        pay1 = b.payments.find((p) => !p.voided);
        const je = jurnalSumber([pay1.cash_txn_id, pay1.payment_intent_id]).find((j) => j.lines.some((l) => l.account_code === "2-1100"));
        assert(je, "jurnal bayar sebagian tidak ada");
        const kas = je.lines.find((l) => Number(l.credit) > 0);
        assert(kas.account_code === "1-1110", `akun kredit ${kas.account_code} ${kas.account_name} (harap 1-1110 Kas Kecil untuk ${REK_KAS})`);
        return `konfirmasi "${msg}" · ${cekJurnal(je, [["2-1100", "D", SEBAGIAN], ["1-1110", "K", SEBAGIAN]])}`;
      });
    tabel.add({ layar: LAYAR, isian: "Nominal dibayar + Rekening sumber", masukan: `500.000 · ${REK_KAS}`,
      harap: `sebagian Rp 500.000; sisa ${rpLayar(TOTAL - SEBAGIAN)}; jurnal 2-1100 D / 1-1110 K`, hasil: ok ? "diperbaiki" : "gagal",
      catatan: "dulu \"500.000\" terbaca Rp 500 (satu titik = desimal) — diperbaiki MoneyInput/parseMoney" + (ok ? "" : ` · GAGAL: ${r.steps.at(-1).info}`) });

    const SISA = TOTAL - SEBAGIAN;
    ok = await r.step(17, "Finance", `[[Bayar]] lagi: nominal terisi sisa → *Rekening sumber* ${REK_BCA} → [[Bayar]] → klik GANDA [[Ya, bayar]]`,
      `Tepat SATU pembayaran ${rpLayar(SISA)}; status Lunas, Sisa Rp 0; dua jurnal berjumlah ${rpLayar(TOTAL)}`, async () => {
        await bukaForm(r);
        assert(num(await r.text("pay-supplier-outstanding")) === SISA, "sisa di form ≠ sisa hutang");
        const v = await r.tid("pay-supplier-amount").inputValue();
        assert(num(v) === SISA || Number(v) === SISA, `nominal terisi "${v}"`);
        await pilih(r, "pay-supplier-account", REK_BCA);
        await r.tid("pay-supplier-submit").click();
        await r.tid("pay-supplier-confirm-confirm").waitFor();
        await r.tid("pay-supplier-confirm-confirm").dblclick().catch(() => {});
        await r.tid("pay-supplier-modal").waitFor({ state: "detached", timeout: 20000 });
        await tungguTeks(r, "vb-detail-status", /Lunas/);
        const b = bill(k1.tagihan_id);
        const live = b.payments.filter((p) => !p.voided);
        assert(live.length === 2, `pembayaran tercatat ${live.length} (harap 2)`);
        assert(b.status === "paid" && Math.abs(b.amount_paid - TOTAL) < 0.01, `DB ${b.status} ${b.amount_paid}`);
        const kas = kasDari(live.map((p) => p.cash_txn_id)).filter((c) => c.status !== "void");
        assert(kas.length === 2, `kas keluar ${kas.length}`);
        const je = jurnalSumber(live.flatMap((p) => [p.cash_txn_id, p.payment_intent_id])).filter((j) => j.lines.some((l) => l.account_code === "2-1100"));
        const hutangD = je.reduce((s, j) => s + j.lines.filter((l) => l.account_code === "2-1100").reduce((a, l) => a + Number(l.debit || 0), 0), 0);
        assert(je.length === 2 && Math.abs(hutangD - TOTAL) < 0.01, `jurnal ${je.length}, D hutang ${hutangD}`);
        return `${live.map((p) => `${p.cash_txn_number} ${rp(p.amount)}`).join(" + ")} = ${rp(b.amount_paid)} · jurnal ${je.map((j) => j.number).join(", ")} D 2-1100 ${rp(hutangD)}`;
      });
    tabel.add({ layar: LAYAR, isian: "Ya, bayar (klik ganda)", masukan: `sisa ${rpLayar(SISA)} · klik ganda`, harap: "satu pembayaran, tagihan Lunas",
      hasil: ok ? "lulus" : "gagal", catatan: ok ? "kunci niat bayar (Idempotency-Key) mencegah kas ganda" : r.steps.at(-1).info });

    ok = await r.step(18, "Finance", "Tagihan Lunas: tombol [[Bayar]] tidak ada lagi", "Tidak bisa membayar dua kali (\"Tagihan lunas.\")", async () => {
      assert(!(await r.tid("vb-action-pay").count()), "tombol Bayar masih tampil");
      return "tombol Bayar hilang";
    });
    tabel.add({ layar: LAYAR, isian: "tombol Bayar", masukan: "tagihan sudah Lunas", harap: "tidak bisa bayar lagi", hasil: ok ? "lulus" : "gagal", catatan: "" });

    // ── Peserta 2: tanggal masa depan, kurang bayar receh ────────────────────────────────────────────────────────
    const b2 = bill(k2.tagihan_id);
    const T2 = Number(b2.grand_total);
    assert(b2.status === "posted" && !Number(b2.amount_paid), `tagihan peserta ${P2} sudah dipakai`);
    const now = new Date(Date.now() + 7 * 3600e3);
    const depan = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 15)).toISOString().slice(0, 10);
    let payDepan = null;
    ok = await r.step(19, "Finance", `Login finance.latih${P2}, bayar ${k2.tagihan}: ketik "100000", *Tanggal bayar* ${depan} (bulan depan) → [[Bayar]] → [[Ya, bayar]]`,
      "Diterima sebagai pembayaran bertanggal maju (keputusan pemilik: boleh/tidak?) ATAU ditolak dengan pesan jelas — tidak 5xx", async () => {
        await bukaTagihan(r, P2, k2);
        await bukaForm(r);
        await pilih(r, "pay-supplier-account", REK_BCA);
        await ketik(r, "pay-supplier-amount", "100000");
        await pilihTanggal(r, "pay-supplier-date", depan);
        const msg = await intipKonfirmasi(r, "pay-supplier-submit", "pay-supplier-confirm", { batal: false });
        await setuju(r, "pay-supplier-confirm");
        const hasil = await Promise.race([
          r.tid("pay-supplier-modal").waitFor({ state: "detached", timeout: 20000 }).then(() => "tersimpan"),
          r.tid("pay-supplier-error").waitFor({ timeout: 20000 }).then(() => "ditolak"),
        ]);
        if (hasil === "ditolak") {
          const e = await r.text("pay-supplier-error");
          assert(!INGGRIS.test(e), `pesan: ${e}`);
          await r.tid("pay-supplier-cancel").click();
          return `ditolak: "${e}"`;
        }
        const b = bill(k2.tagihan_id);
        payDepan = b.payments.find((p) => !p.voided);
        const je = jurnalSumber([payDepan.cash_txn_id, payDepan.payment_intent_id])[0];
        return `DITERIMA: konfirmasi "${msg}" · ${payDepan.cash_txn_number} paid_at ${payDepan.paid_at} · jurnal ${je && je.number} bertanggal ${je && String(je.date).slice(0, 10)}`;
      });
    tabel.add({ layar: LAYAR, isian: "Tanggal bayar", masukan: `${depan} (bulan depan)`, harap: "keputusan pemilik: tanggal maju boleh?",
      hasil: "keputusan", catatan: (r.steps.at(-1).info || "") + " · kalender tidak membatasi tanggal maju; jurnal kas lahir di bulan depan" });

    if (payDepan) {
      await r.step(20, "Finance", "Batalkan pembayaran bertanggal maju itu (pemeriksa, lewat API resmi)", "Pembayaran dibatalkan, jurnal dibalik, tagihan kembali terbuka penuh", async () => {
        const s = await api(akunPeserta(P2));
        await s.post(`/vendor-bills/${k2.tagihan_id}/payments/${payDepan.id}/void`, { notes: "Uji variasi V5 — tanggal maju dibatalkan" }, "ent_ksc");
        const b = bill(k2.tagihan_id);
        assert(b.status === "posted" && Math.abs(Number(b.amount_paid)) < 0.01, `DB ${b.status} ${b.amount_paid}`);
        const asal = mongo(`return db.journal_entries.findOne({source_type:"cash_transaction",source_id:"${payDepan.cash_txn_id}"},{_id:0,number:1,date:1})`);
        const balik = mongo(`return db.journal_entries.findOne({source_type:"cash_transaction_void",source_id:"${payDepan.cash_txn_id}"},{_id:0,number:1,date:1})`);
        assert(balik && String(balik.date).slice(0, 10) === String(asal.date).slice(0, 10),
          `jurnal pembalik ${balik && balik.number} bertanggal ${balik && balik.date}, jurnal asli ${asal.number} ${asal.date} — bulan berjalan dapat Dr Bank / Cr Hutang tanpa jurnal asal`);
        return `tagihan ${b.status}, dibayar ${b.amount_paid} · ${asal.number} ${asal.date} dibalik ${balik.number} ${balik.date}`;
      });
      tabel.add({ layar: LAYAR, isian: "Batalkan pembayaran (tanggal maju)", masukan: `pembayaran ${depan} dibatalkan hari ini`,
        harap: "jurnal pembalik bertanggal sama dengan jurnal asli", hasil: r.steps.at(-1).ok ? "diperbaiki" : "gagal",
        catatan: "dulu pembalik bertanggal HARI INI (Nov) sedangkan aslinya Des → saldo Bank & Hutang November menggelembung; diperbaiki routers/vendor_bills.py void_vendor_bill_payment" + (r.steps.at(-1).ok ? "" : ` · GAGAL: ${r.steps.at(-1).info}`) });
      await r.tid("vb-detail-close").click().catch(() => {});
      await bukaTagihan(r, P2, k2);
    }

    ok = await r.step(21, "Finance", `Bayar ${k2.tagihan}: ketik "${(T2 - 800).toLocaleString("id-ID")}" (kurang Rp 800 dari sisa) → [[Bayar]] → [[Ya, bayar]]`,
      `Form menyebut sisa Rp 800 tetap hutang (seperti tulisan "Bayar sebagian diizinkan; sisanya tetap hutang") ATAU menjelaskan sebelum simpan bahwa selisih receh dihapus`, async () => {
        await bukaForm(r);
        await pilih(r, "pay-supplier-account", REK_BCA);
        await ketik(r, "pay-supplier-amount", (T2 - 800).toLocaleString("id-ID"));
        const note = (await r.tid("pay-supplier-modal").innerText()).replace(/\s+/g, " ");
        const msg = await intipKonfirmasi(r, "pay-supplier-submit", "pay-supplier-confirm", { batal: false });
        await setuju(r, "pay-supplier-confirm");
        await r.tid("pay-supplier-modal").waitFor({ state: "detached", timeout: 20000 });
        await r.idle(800);
        const b = bill(k2.tagihan_id);
        const dec = mongo(`return db.payment_variance_decisions.find({bill_id:"${k2.tagihan_id}"},{_id:0,kind:1,amount:1,delta:1,status:1,journal_entry_id:1}).toArray()`);
        const st = await r.text("vb-detail-status");
        const sisa = num(await r.text("vb-fin-outstanding"));
        const disebut = /dihapus|toleransi|receh/i.test(note + " " + msg);
        assert(disebut || (sisa === 800 && b.status === "posted"),
          `sisa Rp 800 DIHAPUS diam-diam: status ${st}, sisa layar ${sisa}, DB ${b.status} paid ${b.amount_paid} closed ${b.ap_variance_closed}, keputusan ${JSON.stringify(dec)}; form & konfirmasi tidak menyebutnya ("${msg}")`);
        return `status ${st} · sisa ${sisa} · konfirmasi "${msg}" · keputusan ${JSON.stringify(dec)}`;
      });
    tabel.add({ layar: LAYAR, isian: "Nominal dibayar", masukan: `${(T2 - 800).toLocaleString("id-ID")} (kurang Rp 800)`,
      harap: "sisa Rp 800 tetap hutang, atau form memberi tahu selisih receh dihapus", hasil: ok ? "diperbaiki" : "gagal",
      catatan: "dulu: selisih ≤ toleransi Rp 5.000 (payment.variance_ap_tolerance_rupiah) DIHAPUS otomatis (tagihan Lunas, jurnal selisih) padahal form menulis \"sisanya tetap hutang\"" + (ok ? "" : ` · GAGAL: ${r.steps.at(-1).info}`) });
  } catch (e) {
    r.note("GALAT: " + (e && e.message ? e.message : e));
  } finally {
    tabel.simpan();
    await r.finish();
  }
})();
