// R7 · SETORAN TANPA NAMA → TITIPAN → ALOKASI ke pesanan. Baris "SETORAN TUNAI CDM" tidak punya pasangan di buku:
// [[Titipkan]] (Dr Bank / Cr Titipan) → tab Dana Titipan → [[Alokasikan]] ke pesanan pelanggan latihan (Dr Titipan / Cr
// Piutang). Cek buku: dua jurnal seimbang, sisa titipan 0, sisa tagihan pesanan berkurang sebesar setoran.
//
//   KN_PESERTA=85 node docs/pelatihan/2026-11-18_keuangan/uji/rekonsiliasi/R7_titipan.js
const { Run, assert, rp, mongo } = require("../lib.js");
const kb = require("../kasbank_lib.js");
const bk = require("../buku_lib.js");
const rk = require("./rekon_lib.js");

(async () => {
  const r = await new Run("R7", "Rekonsiliasi · setoran tanpa nama — titipkan lalu alokasikan").start();
  let c;
  try { c = await rk.siapkan(r); } catch (e) { r.note(String(e.message)); await r.finish(); return; }
  const k = c.g("titipan");
  const [mf] = c.barisManifest("R7");
  let ln;
  let sisaAwal;
  const sisaPesanan = async () => {
    const rows = await (await rk.sesi(c)).get(`/ar-receipts/open-orders?customer_id=${k.customer_id}`, kb.KSC);
    const o = rows.find((x) => (x.id || x.order_id) === k.so_id);
    return o ? Number(o.outstanding ?? o.outstanding_amount ?? 0) : 0;
  };

  await r.step(1, "Finance", `Rekonsiliasi → BCA Operasional KSC → [[Impor mutasi bank]] → [[Pilih berkas]] ${c.namaBerkas("R7")} → [[Pratinjau]] → [[Impor]] → [[Cocokkan otomatis]]`,
    `1 baris baru "SETORAN TUNAI CDM LATIHAN NN" ${rp(k.nominal)}; sesudah Cocokkan otomatis tetap "Perlu keputusan" tanpa usulan`, async () => {
      sisaAwal = await sisaPesanan();
      assert(sisaAwal >= k.nominal - 0.01, `sisa tagihan ${k.so} ${rp(sisaAwal)} < setoran ${rp(k.nominal)}`);
      await rk.bukaRekon(r, c);
      const x = await rk.imporExcel(r, c, "R7", { baris: 1 });
      const t = await rk.cocokOtomatis(r);
      await rk.saring(r, c);
      ln = rk.baris(c, mf.keterangan);
      assert(ln.status === "unmatched" && !(ln.suggestions || []).length, `status ${ln.status}, usulan ${(ln.suggestions || []).length}`);
      return `${x.notice} · ${t} · sisa tagihan ${k.so} ${rp(sisaAwal)}`;
    });

  await r.step(2, "Finance", "Pada baris SETORAN TUNAI CDM klik [[Titipkan]] → periksa dialog → [[Titipkan dana]]",
    `Dialog "Titipkan dana ini?" menyebut ${rp(k.nominal)}; pesan "Dana dititipkan (jurnal Dr Bank / Cr Titipan terbit)."; status baris "Dititipkan", "Sisa ${rp(k.nominal)}"`, async () => {
      await r.tid(`recon-holding-${ln.id}`).click();
      await r.tid("recon-holding-confirm").waitFor();
      await r.shot("konfirmasi-titipkan", { locator: r.tid("recon-holding-confirm").locator(".modal-card") });
      const msg = await kb.konfirmasi(r, "recon-holding-confirm");
      assert(msg.includes(rp(k.nominal)), `dialog: ${msg}`);
      const t = await kb.tunggu(r, "recon-notice", /Dana dititipkan/);
      await rk.saring(r, c);
      await rk.tungguStatus(r, ln.id, /^Dititipkan$/);
      const row = await kb.isi(r.tid(`recon-line-${ln.id}`));
      assert(row.includes(`Sisa ${rp(k.nominal)}`), `baris: ${row}`);
      await kb.sorot(r.tid(`recon-line-${ln.id}`));
      await r.shot("dana-dititipkan", { locator: r.tid("recon-lines-table") });
      await kb.lepas(r.tid(`recon-line-${ln.id}`));
      return t;
    });

  await r.step(3, "Finance", `Tab [[Dana Titipan]] → baris SETORAN TUNAI CDM → [[Alokasikan]] → *Pelanggan* ${k.pelanggan} → isi nominal ${rp(k.nominal)} pada pesanan ${k.so} → *Alasan* "Dikonfirmasi pelanggan lewat bukti transfer" → *Catatan* → [[Alokasikan]]`,
    `Pesan "Titipan dialokasikan ${rp(k.nominal)} · sisa titipan Rp 0."; baris titipan sudah dialokasikan ${rp(k.nominal)}, sisa Rp 0`, async () => {
      await r.tid("recon-tab-holding").click();
      await r.tid(`recon-holding-row-${ln.id}`).waitFor();
      await kb.shotSorot(r, "dana-titipan", r.tid(`recon-allocate-${ln.id}`), { locator: r.tid("recon-holding-table") });
      // Daftar pelanggan dimuat SESUDAH pop-up terbuka; kotak pilihan yang diklik sebelum daftar datang terbuka kosong.
      const muat = r.page.waitForResponse((res) => /\/api\/customers(\?|$)/.test(res.url()), { timeout: 30000 });
      await r.tid(`recon-allocate-${ln.id}`).click();
      await r.tid("recon-allocate-modal").waitFor();
      await muat;
      await r.idle(300);
      await bk.pilih(r, "recon-allocate-customer", k.customer_id, `Latihan ${c.NO}`);
      await r.tid(`recon-allocate-order-${k.so_id}`).waitFor();
      await r.tid(`recon-allocate-amount-${k.so_id}`).fill(String(k.nominal).replace(".", ","));
      await bk.pilih(r, "recon-allocate-reason", "customer_confirmation");
      await r.tid("recon-allocate-note").fill(`Bukti transfer setoran CDM dikirim pelanggan — Latihan ${c.NO}`);
      await kb.shotSorot(r, "form-alokasi", r.tid("recon-allocate-submit"), { locator: r.tid("recon-allocate-modal") });
      await r.tid("recon-allocate-submit").click();
      const t = await kb.tunggu(r, "recon-notice", /Titipan dialokasikan/);
      assert(t.includes(rp(k.nominal)) && /sisa titipan Rp\s*0(?!\d|[.,]\d)/.test(t), `pesan: ${t}`);
      await r.tid("recon-allocate-modal").waitFor({ state: "detached" });
      const row = await kb.isi(r.tid(`recon-holding-row-${ln.id}`));
      await r.shot("titipan-dialokasikan", { locator: r.tid("recon-holding-table") });
      return `${t} · ${row}`;
    });

  await r.step(4, "Finance", "Cek buku: jurnal titipan & jurnal alokasi; sisa tagihan pesanan",
    `Jurnal titipan: Bank Debit / 2-1950 Titipan Kredit ${rp(k.nominal)}; jurnal alokasi: 2-1950 Titipan Debit / Piutang Kredit ${rp(k.nominal)}; sisa tagihan ${k.so} turun ${rp(k.nominal)}`, async () => {
      ln = rk.baris(c, mf.keterangan);
      assert(Math.abs(Number(ln.holding_remaining)) < 0.01, `sisa titipan ${ln.holding_remaining}`);
      const kas = kb.kas(ln.holding.cash_txn_id);
      assert(kas && kas.direction === "in" && Math.abs(kas.amount - k.nominal) < 0.01 && kas.account_id === c.bca.id, "kas titipan");
      const jeT = kb.seimbang(kb.jurnal("cash_transaction", kas.id), "jurnal titipan");
      const titipan = jeT.lines.find((l) => Number(l.credit) > 0);
      assert(/^2-/.test(titipan.account_code) && Math.abs(titipan.credit - k.nominal) < 0.01, `jurnal titipan: ${kb.teksJurnal(jeT)}`);
      const jeA = mongo(`return db.journal_entries.find({source_type:"bank_holding_alloc",source_id:{$regex:"^${ln.id}:"},
        status:{$ne:"void"}},{_id:0,id:1,number:1,lines:{account_code:1,account_name:1,debit:1,credit:1}}).toArray()`);
      kb.seimbang(jeA, "jurnal alokasi titipan");
      assert(jeA.length === 1 && kb.adaBaris(jeA[0], titipan.account_code, "D", k.nominal), `jurnal alokasi: ${jeA.map(kb.teksJurnal).join(" | ")}`);
      const sisa = await sisaPesanan();
      assert(Math.abs((sisaAwal - sisa) - k.nominal) < 0.01, `sisa tagihan ${k.so}: ${rp(sisaAwal)} → ${rp(sisa)}`);
      return `${kb.teksJurnal(jeT)} || ${kb.teksJurnal(jeA[0])} || sisa ${k.so} ${rp(sisaAwal)} → ${rp(sisa)}`;
    });

  await r.finish();
})();
