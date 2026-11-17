// V3 — VARIASI teks rekening koran yang DITEMPEL di Rekonsiliasi Bank (F10, Impor mutasi bank → Pratinjau): bentuk tanggal,
// nominal, arah (kolom DB/CR · minus · akhiran · kolom debet/kredit), pemisah (koma · TAB · titik koma · spasi), baris
// kosong, tanpa judul kolom, baris rusak, impor ganda; lalu ringkasan (rekening vs buku, selisih) dihitung ULANG.
//   KN_PESERTA=64 node docs/pelatihan/2026-11-18_keuangan/uji/variasi/V3_rekonsiliasi.js
// Hanya SATU impor (1 baris berketerangan "VARIASI LATIHAN NN …", Rp 1.234,50) + satu impor ulang (harus dilewati).
const { Run, api, assert, peserta, akunPeserta, rp, mongo, sleep } = require("../lib.js");
const kb = require("../kasbank_lib.js");
const { bersihkanHasil } = require("../piutang_lib");
const v = require("./vlib");

const NO = peserta("64");
const t = v.tabel("V3");
const L = "Rekonsiliasi Bank · Impor (tempel)";
const H = "Tanggal,Keterangan,Cabang,Jumlah,DB/CR,Saldo";

(async () => {
  bersihkanHasil("V3");
  const r = await new Run("V3", "Variasi teks rekening koran — Rekonsiliasi Bank").start();
  const me = akunPeserta(NO);
  const tgl = kb.hariIni();
  const [yy, mm, dd] = tgl.iso.split("-");
  const BLN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"][Number(mm) - 1];
  const tglId = new Date(`${tgl.iso}T00:00:00+07:00`).toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric", timeZone: "Asia/Jakarta" });
  try {
    const bca = await kb.rekening(me, "BCA Operasional KSC");
    const fmts = await (await api(me)).get("/bank-reconciliation/formats", kb.KSC);
    const fBca = fmts.find((f) => f.bank_code === "bca" && (f.file_kind || "csv") === "csv");
    await r.login(me);
    await kb.menu(r, "bank-reconciliation");
    await kb.pilih(r, "recon-account-select", bca.id);
    await r.tid("recon-summary").waitFor();

    const bukaImpor = async (tpl) => {
      if (!(await r.tid("recon-import-panel").count())) {
        await r.tid("recon-import-toggle").click();
        await r.tid("recon-import-panel").waitFor();
      }
      await kb.pilih(r, "recon-format-select", tpl === "auto" ? "empty" : fBca.id);   // nilai kosong = "Kenali otomatis"
    };
    /** Tempel teks → Pratinjau → { baris: [[tanggal, nominal, arah]], teks, galat: [..] } dari tabel pratinjau di LAYAR. */
    const pratinjau = async (teks, tpl = "bca") => {
      await bukaImpor(tpl);
      await r.tid("recon-raw").fill(teks);
      await r.tid("recon-preview-btn").click();
      await r.page.waitForFunction(() => document.querySelector('[data-testid="recon-preview"]')
        || (document.querySelector('[data-testid="recon-import-error"]')?.innerText || "").trim(), null, { timeout: 15000 });
      await sleep(200);
      if (!(await r.tid("recon-preview").count())) return { baris: [], teks: "", galat: [await kb.teks(r, "recon-import-error")] };
      const rows = await r.tid("recon-preview").locator("tbody tr").evaluateAll((trs) => trs.map((tr) =>
        [...tr.querySelectorAll("td")].map((td) => td.innerText.replace(/\s+/g, " ").trim())));
      const galat = await r.tid("recon-preview").locator('[data-testid^="recon-preview-error-"]').allInnerTexts();
      return { baris: rows.map((c) => [c[0], c[3], c[4]]), teks: (await kb.teks(r, "recon-preview")).split("Tanggal")[0], galat };
    };
    const harap1 = (arah = "Masuk", nom = "Rp 1.500.000") => [[tglId, nom, arah]];
    const sama = (a, b) => JSON.stringify(a) === JSON.stringify(b);

    const kasus = [
      ["Tanggal dd/mm/yyyy (contoh panduan)", `${tgl.bca},TRSF A,0000,"1.500.000,00",CR,0`, "bca", harap1(), "lulus", ""],
      ["Tanggal yyyy-mm-dd", `${tgl.iso},TRSF A,0000,"1.500.000,00",CR,0`, "bca", harap1(), "lulus", ""],
      ["Tanggal dd-mm-yyyy", `${dd}-${mm}-${yy},TRSF A,0000,"1.500.000,00",CR,0`, "bca", harap1(), "lulus", ""],
      ["Tanggal '17 Nov 2026'", `${dd} ${BLN} ${yy},TRSF A,0000,"1.500.000,00",CR,0`, "bca", harap1(), "lulus", ""],
      ["Tanggal tanpa tahun dd/mm (gaya BCA)", `${dd}/${mm},TRSF A,0000,"1.500.000,00",CR,0`, "bca", harap1(), "lulus", ""],
      ["Nominal 1500000", `${tgl.bca},TRSF A,0000,1500000,DB,0`, "bca", harap1("Keluar"), "lulus", ""],
      ["Nominal 1.500.000 tanpa kutip", `${tgl.bca},TRSF A,0000,1.500.000,CR,0`, "bca", harap1(), "lulus", ""],
      ["Nominal '1,500,000.00' (gaya Inggris)", `${tgl.bca},TRSF A,0000,"1,500,000.00",CR,0`, "bca", harap1(), "diperbaiki",
        "Dulu ditolak 'Nominal tidak terbaca / nol' (template BCA berdesimal koma)."],
      ["Nominal '3240090.00' (titik desimal)", `${tgl.bca},TRSF A,0000,1500000.00,CR,0`, "bca", harap1(), "diperbaiki",
        "Dulu template BCA membuang titik → Rp 150.000.000 (×100, tanpa peringatan)."],
      ["Nominal bertanda minus tanpa DB/CR", `${tgl.bca},TRSF A,0000,"-1.500.000,00",,0`, "bca", harap1("Keluar"), "lulus", "Minus = uang keluar."],
      ["Akhiran DB di kolom nominal", `${tgl.bca},TRSF A,0000,"1.500.000,00 DB",,0`, "bca", harap1("Keluar"), "lulus", ""],
      ["Nominal ber-'Rp'", `${tgl.bca},TRSF A,0000,"Rp 1.500.000,00",CR,0`, "bca", harap1(), "lulus", ""],
    ];
    for (const [isian, baris, tpl, harap, hasil, catatan] of kasus) {
      await v.kasus(r, t, { layar: L, isian, masukan: `${H}\n${baris}`, harap: `Pratinjau 1 baris: ${harap[0].join(" · ")}`, hasil, catatan }, async () => {
        const p = await pratinjau(`${H}\n${baris}`, tpl);
        assert(sama(p.baris, harap) && !p.galat.length, `${JSON.stringify(p.baris)} · galat ${p.galat.join(" | ")}`);
        return `${p.teks} · ${JSON.stringify(p.baris[0])}`;
      });
    }
    const sep = (d) => [H.split(",").join(d), [tgl.bca, "TRSF A", "0000", "1.500.000,00", "DB", "0"].join(d),
      [tgl.bca, "BIAYA ADM", "0000", "15.000,00", "DB", "0"].join(d)].join("\n");
    const dua = [[tglId, "Rp 1.500.000", "Keluar"], [tglId, "Rp 15.000", "Keluar"]];
    for (const [isian, teks] of [["Pemisah TAB (salin dari Excel / KlikBCA)", sep("\t")], ["Pemisah titik koma ;", sep(";")],
      ["Kolom dipisah spasi berderet (salin dari PDF)", sep("    ")]]) {
      await v.kasus(r, t, { layar: L, isian, masukan: teks.replace(/\t/g, "⇥"), harap: "Pratinjau 2 baris keluar (1.500.000 & 15.000)",
        hasil: "diperbaiki", catatan: "Dulu setiap baris ditolak 'Tanggal tidak terbaca' (template BCA ber-koma membaca seluruh baris sebagai satu kolom)." }, async () => {
        const p = await pratinjau(teks);
        assert(sama(p.baris, dua) && !p.galat.length, `${JSON.stringify(p.baris)} · ${p.galat.join(" | ")}`);
        return `${p.teks}`;
      });
    }
    await v.kasus(r, t, { layar: L, isian: "Baris kosong di tengah & akhir", masukan: `${H}\n\n<baris>\n\n`, harap: "Baris kosong dilewati tanpa galat",
      hasil: "lulus" }, async () => {
      const p = await pratinjau(`${H}\n\n${tgl.bca},TRSF A,0000,"1.500.000,00",CR,0\n\n\n`);
      assert(sama(p.baris, harap1()) && !p.galat.length, JSON.stringify(p));
      return p.teks;
    });
    await v.kasus(r, t, { layar: L, isian: "Kolom Debet/Kredit terpisah (gaya Mandiri) + 'Kenali otomatis'",
      masukan: "Tanggal,Keterangan,Debet,Kredit,Saldo / …,,\"1.500.000,00\",0", harap: "Dikenali template Mandiri; 1 baris Masuk 1.500.000", hasil: "lulus" }, async () => {
      const p = await pratinjau(`Tanggal,Keterangan,Debet,Kredit,Saldo\n${tgl.bca},TRSF A,,"1.500.000,00",0`, "auto");
      assert(sama(p.baris, harap1()) && /Mandiri/.test(p.teks), JSON.stringify(p));
      return p.teks;
    });
    await v.kasus(r, t, { layar: L, isian: "Kolom Debet/Kredit terpisah dengan template BCA (template salah)",
      masukan: "Tanggal,Keterangan,Debet,Kredit,Saldo + template BCA", harap: "Ditolak dengan arahan: kolom nominal tidak ditemukan, pilih template yang cocok",
      hasil: "diperbaiki", catatan: "Dulu 'Nominal tidak terbaca / nol' per baris tanpa menyebut kolom/template." }, async () => {
      const p = await pratinjau(`Tanggal,Keterangan,Debet,Kredit,Saldo\n${tgl.bca},TRSF A,,"1.500.000,00",0`);
      assert(!p.baris.length && p.galat.some((g) => /Judul kolom/.test(g) && /nominal/.test(g) && /template/.test(g)), JSON.stringify(p));
      return p.galat[0];
    });
    await v.kasus(r, t, { layar: L, isian: "Tanpa baris judul kolom", masukan: "<hanya baris data>",
      harap: "Ditolak dengan arahan 'Baris judul kolom tidak dikenali …'", hasil: "diperbaiki",
      catatan: "Dulu pratinjau diam-diam 'Terbaca 0 baris' (baris data dipakai sebagai judul) tanpa alasan." }, async () => {
      const p = await pratinjau(`${tgl.bca},TRSF A,0000,"1.500.000,00",CR,0`);
      assert(!p.baris.length && p.galat.some((g) => /judul kolom tidak dikenali/i.test(g)), JSON.stringify(p));
      return p.galat[0];
    });
    await v.kasus(r, t, { layar: L, isian: "Campuran baris benar & rusak", masukan: "tanggal 31/02, nominal 'abc', koma desimal tanpa kutip, 1 baris benar",
      harap: "Pratinjau 1 baris; SETIAP baris yang dilewati disebut nomor & alasannya (isi selnya)", hasil: "diperbaiki",
      catatan: "Dulu hanya satu contoh galat yang tampil." }, async () => {
      const p = await pratinjau([H, `31/02/${yy},TRSF A,0000,"1.500.000,00",CR,0`, `${tgl.bca},TRSF B,0000,"abc",CR,0`,
        `${tgl.bca},TRSF C,0000,1.500.000,00,CR,0`, `${tgl.bca},TRSF D,0000,"20.000,00",DB,0`].join("\n"));
      assert(sama(p.baris, [[tglId, "Rp 20.000", "Keluar"]]) && p.galat.length === 3, JSON.stringify(p));
      assert(/31\/02/.test(p.galat[0]) && /abc/.test(p.galat[1]) && /tanda kutip/.test(p.galat[2]), p.galat.join(" | "));
      return p.galat.join(" | ");
    });

    // ── Impor sungguhan (1 baris) + impor ulang ───────────────────────────────────────────────────────────────────
    const ket = `VARIASI LATIHAN ${NO} ${Date.now() % 100000}`;
    const teks = `${H}\n${tgl.bca},${ket},0000,"1.234,50",DB,0`;
    await v.kasus(r, t, { layar: L, isian: "Impor 1 baris (nominal sen)", masukan: `1.234,50 DB · '${ket}'`,
      harap: "'1 baris baru, 0 dilewati'; tersimpan keluar 1234.5, tanggal hari ini", hasil: "lulus" }, async () => {
      await pratinjau(teks);
      await r.tid("recon-import-submit").click();
      const n = await kb.tunggu(r, "recon-notice", /Impor/);
      assert(/1 baris baru, 0 dilewati/.test(n), n);
      const ln = mongo(`return db.bank_statement_lines.findOne({bank_account_id:"${bca.id}",description:"${ket}"},{_id:0,amount:1,direction:1,stmt_date:1})`);
      assert(ln && ln.amount === 1234.5 && ln.direction === "out" && ln.stmt_date === tgl.iso, JSON.stringify(ln));
      return n;
    });
    await v.kasus(r, t, { layar: L, isian: "Impor ULANG teks yang sama", masukan: "(tempel lagi teks yang sama → Impor)",
      harap: "'0 baris baru, 1 dilewati (sudah pernah masuk)'; tidak ada baris ganda", hasil: "lulus" }, async () => {
      await pratinjau(teks);
      await r.tid("recon-import-submit").click();
      const n = await kb.tunggu(r, "recon-notice", /0 baris baru/);
      assert(/1 dilewati/.test(n), n);
      const c = mongo(`return db.bank_statement_lines.countDocuments({bank_account_id:"${bca.id}",description:"${ket}"})`);
      assert(c === 1, `baris ganda: ${c}`);
      return n;
    });

    // ── Ringkasan: dihitung ulang dari mutasi & buku ──────────────────────────────────────────────────────────────
    await v.kasus(r, t, { layar: "Rekonsiliasi Bank · Ringkasan", isian: "Rekening (bersih) · Buku (bersih) · Selisih", masukan: "(BCA Operasional KSC, tanpa saringan periode)",
      harap: "Rekening = Σ mutasi masuk − keluar (bukan 'diabaikan'); Buku = Σ kas masuk − keluar (tidak anulir, rekening ini + kas lama tanpa rekening bila rekening tunggal); Selisih = Rekening − Buku; sama dengan kartu di layar",
      hasil: "lulus" }, async () => {
      const hit = mongo(`const a=db.bank_accounts.findOne({id:"${bca.id}"});
        let si=0,so=0; db.bank_statement_lines.find({bank_account_id:a.id,status:{$ne:"ignored"}}).forEach(l=>{ if(l.direction==="in") si+=l.amount; else so+=l.amount; });
        const tunggal=db.bank_accounts.countDocuments({entity_id:a.entity_id,cash_type:a.cash_type,is_active:{$ne:false},status:{$ne:"inactive"}})===1;
        const q=tunggal?{status:{$ne:"void"},$or:[{account_id:a.id},{account_id:{$in:["",null]},cash_type:a.cash_type,entity_id:a.entity_id},{account_id:{$exists:false},cash_type:a.cash_type,entity_id:a.entity_id}]}:{account_id:a.id,status:{$ne:"void"}};
        let bi=0,bo=0; db.cash_transactions.find(q).forEach(x=>{ if(x.direction==="in") bi+=x.amount; else bo+=x.amount; });
        const r2=(n)=>Math.round(n*100)/100; return {stmt:r2(si-so), book:r2(bi-bo), diff:r2((si-so)-(bi-bo))};`);
      const sm = await (await api(me)).get(`/bank-reconciliation/summary?bank_account_id=${bca.id}`, kb.KSC);
      assert(Math.abs(sm.statement.net - hit.stmt) < 0.01 && Math.abs(sm.book.net - hit.book) < 0.01 && Math.abs(sm.difference - hit.diff) < 0.01,
        `layanan ${JSON.stringify({ s: sm.statement.net, b: sm.book.net, d: sm.difference })} ≠ hitung ${JSON.stringify(hit)}`);
      if (await r.tid("recon-import-panel").count()) await r.tid("recon-import-panel").getByRole("button", { name: "Batal" }).click();
      await r.tid("recon-refresh").click().catch(() => {});
      await r.idle(800);
      const kartu = await kb.isi(r.tid("recon-summary"));
      for (const n of [hit.stmt, hit.book, hit.diff]) assert(kartu.includes(rp(Math.abs(n)).replace("Rp ", "")), `kartu tanpa ${rp(n)}: ${kartu.slice(0, 300)}`);
      return `rekening ${rp(hit.stmt)} · buku ${rp(hit.book)} · selisih ${rp(hit.diff)} (layanan = hitung ulang = layar)`;
    });
  } catch (e) {
    r.note("berhenti: " + e.message);
  }
  t.simpan();
  await r.finish();
})();
