// D3 — Apakah pengaturan NASKAH dokumen benar-benar mengubah cetakan? (Pengaturan › Dokumen & Notifikasi › Template
// Dokumen). Uji pada Faktur Komersial pesanan peserta:
//   1. Desainer PDF (aturan semua PT): teks penutup bertoken + teks footer + judul → cetak ulang → teks muncul, token terisi.
//   2. Aturan khusus satu PT (Sukacita): teks pembuka → hanya faktur Sukacita yang berubah; faktur PT lain tidak.
//   3. Masukan salah: token tak dikenal ditolak dengan pesan jelas; lapisan PT tidak boleh mengubah tata letak.
//   4. Izin: Finance tidak boleh menyimpan; Manajer boleh lewat server tetapi tab Desainer hanya untuk Admin.
//   5. Kembalikan → cetakan sama persis dengan sebelum uji (selain stempel "Dicetak").
//   6. "Kop & tata letak dasar" (template dokumen lama) — mengubah footer hanya memengaruhi tombol cetak lama
//      ("Faktur (PPN)" / "Surat Jalan" di rincian pesanan), BUKAN PDF Pusat Dokumen. Dikembalikan persis.
// Semua perubahan DIKEMBALIKAN di akhir (juga bila langkah gagal). Sebelum/sesudah: hasil/D3/{sebelum,sesudah}.json.
//
//   KN_PESERTA=81 node docs/pelatihan/2026-11-18_keuangan/uji/dokumen/D3_template_naskah.js
const fs = require("fs");
const path = require("path");
const { Run, api, assert, kartu, peserta, mongo, sleep } = require("../lib");
const dk = require("./dokumen_lib");
const kb = require("../kasbank_lib");

const NO = peserta("81");
const PT = "ent_ksc";
const PENUTUP = "Mohon transfer ke {{rekening_bank}} dan tulis nomor {{nomor}} pada berita transfer.";
const FOOTER = 'Kain Nusantara & Mitra — "Terima kasih atas kepercayaan Anda"';
const JUDUL = "Faktur Penjualan";
const PEMBUKA_PT = "Khusus Sukacita: barang yang sudah dipotong tidak dapat dikembalikan.";
const LEGACY_FOOTER = "UJI D3 — footer template dasar";

(async () => {
  const k = kartu(NO);
  const so = k["a_dasar:so_lunas"];
  const r = await new Run("D3", "Naskah dokumen bisa diubah, berlaku per PT, dan bisa dikembalikan").start();
  const admin = await api("admin");
  const fin = await api(`finance.latih${NO}`);
  const mgr = await api("manager");
  const lain = mongo(`return db.sales_orders.findOne({entity_id:{$ne:"${PT}"},status:{$in:["done","shipped"]}},{_id:0,id:1,number:1,entity_id:1})`);
  const rows = () => mongo(`return db.pdf_templates.find({},{_id:0}).sort({doc_type:1,entity_id:1}).toArray()`);
  const legacy = () => mongo(`return db.document_templates.findOne({id:"tmpl_inv_default"},{_id:0})`);
  const sebelum = { pdf_templates: rows(), document_templates_inv: legacy() };
  fs.writeFileSync(path.join(r.dir, "sebelum.json"), JSON.stringify(sebelum, null, 2));
  const cetak = async (nama, sid = so.so_id) => dk.simpan(r, nama, await dk.unduhApi(admin, `/pdf/render/invoice/${sid}?format=pdf`));
  const bersih = (t) => dk.rata(t).replace(/Dicetak \d{2} \w{3} \d{4}( [\d.]+ WIB)?/g, "").trim();
  const t0 = await cetak("00-faktur-sebelum");
  const t0lain = await cetak("00-faktur-pt-lain-sebelum", lain.id);
  r.note(`Sebelum uji: pdf_templates ${sebelum.pdf_templates.length} baris; faktur ${so.so} & ${lain.number} dicetak sebagai pembanding`);

  try {
    // ── 1. Desainer PDF — aturan semua PT ───────────────────────────────────────────────────────────────────────
    await r.step(1, "Admin", "Pengaturan › Dokumen & Notifikasi › Template Dokumen › tab [[Desainer PDF]] → Jenis dokumen [[Faktur Komersial]], Berlaku untuk [[Semua PT]] → bagian [[Naskah]]: isi *Teks penutup* (klik token {{rekening_bank}} & {{nomor}}) → bagian [[Layout]]: *Judul dokumen* → bagian [[Footer]]: *Teks Footer* → [[Simpan]]",
      "Pesan hijau 'Template tersimpan'; pratinjau menampilkan teks penutup dengan rekening & nomor faktur terisi", async () => {
        await r.login("admin");
        await r.go("pdf-templates");
        await r.tid("doc-templates-tabs-desainer").click();
        await r.tid("pdf-template-designer").waitFor();
        await kb.pilih(r, "pdf-doctype-select", "invoice");
        await r.idle(500);
        await r.tid("pdf-tab-naskah").click();
        await r.tid("pdf-closing-note").fill(PENUTUP);
        await r.tid("pdf-tab-layout").click();
        await r.tid("pdf-title-override").fill(JUDUL);
        await r.tid("pdf-tab-footer").click();
        await r.tid("pdf-footer-text").fill(FOOTER);
        await r.tid("pdf-save-template").click();
        await r.tid("pdf-msg").waitFor({ timeout: 15000 });
        const msg = await r.text("pdf-msg");
        await sleep(1500);
        await r.shot("desainer-tersimpan", { full: true });
        return msg;
      });
    await r.step(2, "Admin", `Cetak ulang Faktur ${so.so} (Pusat Dokumen › Unduh PDF)`,
      "Judul, teks penutup (rekening bank PT & nomor faktur terisi) dan footer tercetak persis; isi lain tidak berubah", async () => {
        const d = await cetak("01-faktur-naskah-semua-pt");
        const t = dk.rata(d.text);
        const masalah = dk.cekFormat(d);
        // {{rekening_bank}} = rekening tujuan pesanan, lalu rekening BAWAAN penerimaan transfer PT (Pengaturan › Rekening);
        // tanpa keduanya kosong (aturan yang tertulis di layar naskah).
        const bawaan = mongo(`const a=db.bank_accounts.findOne({entity_id:"${PT}",default_receiving_methods:"transfer"},{_id:0,bank_name:1,account_number:1,name:1});
          return a ? a.bank_name+" "+a.account_number : ""`);
        const re = bawaan ? new RegExp(`Mohon transfer ke ${bawaan}.* dan tulis nomor KSC/INV-\\d+ pada berita transfer\\.`)
          : /Mohon transfer ke dan tulis nomor KSC\/INV-\d+ pada berita transfer\./;
        if (!re.test(t)) masalah.push("teks penutup/token tidak terisi sesuai aturan");
        if (!bawaan) r.note("PERLU PENGATURAN: PT Sukacita belum punya rekening BAWAAN penerimaan transfer → {{rekening_bank}} tercetak kosong (\"Mohon transfer ke dan …\"). Tetapkan bawaan di Pengaturan › Rekening sebelum memakai token ini.");
        if (!t.includes(FOOTER)) masalah.push(`footer tidak tercetak persis (dapat: ${(/Kain Nusantara[^\n]*/.exec(d.text) || [""])[0]})`);
        if (!/FAKTUR PENJUALAN/.test(d.text)) masalah.push("judul tidak berubah");
        dk.wajib(masalah, "faktur sesudah naskah");
        return (/Mohon transfer[^\n]*/.exec(d.text) || [""])[0].trim();
      });

    // ── 2. Aturan khusus satu PT ────────────────────────────────────────────────────────────────────────────────
    await r.step(3, "Admin", "Berlaku untuk [[Hanya Sukacita Textile]] → [[Naskah]] *Teks pembuka* → [[Simpan]]",
      "Pesan 'Aturan khusus Sukacita Textile tersimpan — PT lain tidak berubah.'", async () => {
        await kb.pilih(r, "pdf-entity-select", PT);
        await kb.pilih(r, "pdf-scope-select", "pt");
        await r.idle(600);
        await r.tid("pdf-tab-naskah").click();
        await r.tid("pdf-intro-text").fill(PEMBUKA_PT);
        await r.tid("pdf-save-template").click();
        await r.tid("pdf-msg").waitFor({ timeout: 15000 });
        const msg = await r.text("pdf-msg");
        await r.shot("desainer-khusus-pt", { full: true });
        assert(/PT lain tidak berubah/.test(msg), msg);
        return msg;
      });
    await r.step(4, "Admin", `Cetak faktur ${so.so} (Sukacita) dan ${lain.number} (PT lain)`,
      "Teks pembuka hanya di faktur Sukacita; faktur PT lain tetap memakai naskah semua PT", async () => {
        const a = await cetak("02-faktur-khusus-pt");
        const b = await cetak("02-faktur-pt-lain", lain.id);
        assert(dk.rata(a.text).includes(PEMBUKA_PT), "pembuka khusus PT tidak tercetak di faktur Sukacita");
        assert(!dk.rata(b.text).includes(PEMBUKA_PT), "pembuka khusus Sukacita ikut tercetak di faktur PT lain");
        assert(dk.rata(b.text).includes(FOOTER), "faktur PT lain kehilangan footer semua PT");
        return `Sukacita: ada · ${lain.number}: tidak ada (footer semua PT tetap ada)`;
      });

    // ── 3. Masukan salah ────────────────────────────────────────────────────────────────────────────────────────
    await r.step(5, "Admin", "Ketik token salah {{nomer}} di Teks penutup (Semua PT) → [[Simpan]]",
      "Peringatan kuning token tidak dikenal saat mengetik; simpan ditolak dengan pesan berisi daftar token yang sah", async () => {
        await kb.pilih(r, "pdf-scope-select", "all");
        await r.idle(600);
        await r.tid("pdf-tab-naskah").click();
        await r.tid("pdf-closing-note").fill("Nomor {{nomer}}");
        await r.tid("pdf-closing-note-unknown").waitFor({ timeout: 8000 });
        const warn = await r.text("pdf-closing-note-unknown");
        await r.tid("pdf-save-template").click();
        await r.tid("pdf-err").waitFor({ timeout: 10000 });
        const err = await r.text("pdf-err");
        await r.shot("token-salah", { full: true });
        assert(/tidak dikenal/i.test(err) && /\{\{nomor\}\}/.test(err), err);
        const row = mongo(`return db.pdf_templates.findOne({doc_type:"invoice",entity_id:"all"},{_id:0,config:1})`);
        assert(row.config.closing_note === PENUTUP, "naskah tersimpan berubah walau ditolak");
        return `${warn} | ${err.slice(0, 160)}`;
      });
    await r.step(6, "Admin", "API: lapisan PT mencoba mengubah ukuran kertas",
      "Ditolak 400 'Bagian ini hanya bisa diatur untuk semua PT: Ukuran kertas.'", async () => {
        try { await admin.call("PUT", `/pdf/templates/invoice?entity_id=${PT}`, { config: { paper_size: "A5" } }); }
        catch (e) { assert(e.status === 400 && /hanya bisa diatur untuk semua PT/.test(JSON.stringify(e.detail)), e.message); return String(e.detail); }
        throw new Error("lapisan PT boleh mengubah kertas");
      });

    // ── 4. Izin ─────────────────────────────────────────────────────────────────────────────────────────────────
    await r.step(7, "Finance/Manajer", "Finance mencoba menyimpan naskah; Manajer membuka Template Dokumen",
      "Finance 403; Manajer boleh menyimpan lewat server (izin pdf_template.manage) — dicatat bila tab Desainer tidak tampil", async () => {
        let f = 0;
        try { await fin.call("PUT", "/pdf/templates/invoice", { config: { footer_text: "x" } }); } catch (e) { f = e.status; }
        assert(f === 403, `Finance → ${f}`);
        const m = await mgr.get("/pdf/templates/invoice");
        await r.login("manager");
        await r.go("pdf-templates");
        await r.tid("doc-templates-view").waitFor();
        const tab = await r.tid("doc-templates-tabs-desainer").isVisible().catch(() => false);
        await r.shot("manajer-template-dokumen", { full: false });
        r.note(`Manajer: GET template ${m.doc_type} OK (izin pdf_template); tab Desainer PDF ${tab ? "tampil" : "TIDAK tampil (dikunci nama peran admin)"}`);
        return `Finance PUT → 403 · Manajer tab Desainer ${tab ? "tampil" : "tidak tampil"}`;
      });

    // ── 6. Template dasar lama ──────────────────────────────────────────────────────────────────────────────────
    await r.step(8, "Admin", "Kop & tata letak dasar: ubah footer 'Template Invoice Standard' → cetak lewat tombol lama vs Pusat Dokumen",
      "Tombol lama 'Faktur (PPN)' memakai footer baru; PDF Pusat Dokumen TIDAK terpengaruh (dua editor untuk dua jalur cetak)", async () => {
        await admin.patch("/document-templates/tmpl_inv_default", { data: { footer: LEGACY_FOOTER } });
        const html = (await (await fetch(`${require("../lib").API}/documents/preview/${so.so_id}?document_type=invoice`,
          { headers: { Authorization: `Bearer ${admin.token}` } })).text());
        fs.writeFileSync(path.join(r.dir, "03-cetak-lama-faktur.html"), html);
        const pdf = await cetak("03-faktur-pdf-setelah-ubah-dasar");
        const diLama = html.includes(LEGACY_FOOTER);
        const diPdf = dk.rata(pdf.text).includes(LEGACY_FOOTER);
        r.note(`Footer template dasar: tombol cetak lama ${diLama ? "BERUBAH" : "tidak berubah"} · PDF Pusat Dokumen ${diPdf ? "berubah" : "TIDAK berubah"}`);
        assert(diLama, "footer template dasar tidak muncul di cetak lama");
        return `cetak lama: ${diLama} · PDF: ${diPdf}`;
      });
  } finally {
    // ── 5. Kembalikan semuanya ──────────────────────────────────────────────────────────────────────────────────
    await r.step(9, "Admin", "Kembalikan: [[Kembalikan ke bawaan]] untuk lapisan Sukacita & Semua PT; footer template dasar ke teks asal",
      "pdf_templates & template dasar sama dengan sebelum uji; faktur tercetak sama persis dengan sebelum uji", async () => {
        for (const row of rows()) {
          const before = sebelum.pdf_templates.find((x) => x.doc_type === row.doc_type && x.entity_id === row.entity_id);
          const q = row.entity_id && row.entity_id !== "all" ? `?entity_id=${row.entity_id}` : "";
          if (!before) await admin.call("DELETE", `/pdf/templates/${row.doc_type}${q}`);
          else await admin.call("PUT", `/pdf/templates/${row.doc_type}${q}`, { config: before.config });
        }
        const L = sebelum.document_templates_inv;
        await admin.patch("/document-templates/tmpl_inv_default", { data: { footer: L.footer } });
        if (!("updated_at" in L)) mongo(`db.document_templates.updateOne({id:"tmpl_inv_default"},{$unset:{updated_at:""}}); return 1`);
        const sesudah = { pdf_templates: rows(), document_templates_inv: legacy() };
        fs.writeFileSync(path.join(r.dir, "sesudah.json"), JSON.stringify(sesudah, null, 2));
        assert(JSON.stringify(sesudah.pdf_templates) === JSON.stringify(sebelum.pdf_templates), "pdf_templates belum kembali");
        assert(JSON.stringify(sesudah.document_templates_inv) === JSON.stringify(sebelum.document_templates_inv), "template dasar belum kembali");
        const t1 = await cetak("04-faktur-sesudah-dikembalikan");
        const t1lain = await cetak("04-faktur-pt-lain-sesudah", lain.id);
        assert(bersih(t1.text) === bersih(t0.text), "faktur Sukacita berbeda dengan sebelum uji");
        assert(bersih(t1lain.text) === bersih(t0lain.text), "faktur PT lain berbeda dengan sebelum uji");
        return `pdf_templates ${sesudah.pdf_templates.length} baris (sebelum ${sebelum.pdf_templates.length}); faktur identik dengan sebelum uji`;
      });
  }
  await r.finish();
})();
