// K08 — Nomor & naskah dokumen: format nomor per jenis dokumen per PT (Pengaturan › Dokumen & Notifikasi › Penomoran
// Dokumen — dibaca, tidak diubah) dan naskah cetak (Template Dokumen › Desainer PDF): pelatih (Admin) menambah teks
// penutup KHUSUS Sukacita pada Kwitansi, peserta (Finance) mencetak kwitansi dan melihat teksnya, lalu pelatih
// mengembalikan ("Kembali ke aturan semua PT"). Naskah dipotret sebelum, dikembalikan di `finally`, dibuktikan sama, dan
// kwitansi tercetak sama persis dengan sebelum peragaan (selain stempel "Dicetak").
//   node docs/pelatihan/2026-11-18_keuangan/uji/konfigurasi/K08_nomor_naskah_dokumen.js     (bawaan peserta 11)
const fs = require("fs");
const { api, assert, peserta, akunPeserta, mongo } = require("../lib");
const dk = require("../dokumen/dokumen_lib");
const k = require("./konfig_lib");

const JENIS = "ar_receipt";
const PENUTUP = "Simpan kwitansi {{nomor}} ini sebagai bukti pembayaran yang sah.";
const potretNaskah = () => k.tanpaWaktu({
  pdf_templates: mongo(`return db.pdf_templates.find({},{_id:0}).sort({doc_type:1,entity_id:1}).toArray()`),
  doc_number_formats: mongo(`return db.doc_number_formats.find({},{_id:0}).sort({kind:1,entity_id:1}).toArray()`),
});

(async () => {
  const no = peserta("11");
  const r = await k.mulai("K08", "Nomor & naskah dokumen");
  const admin = await api("admin");
  const fin = await api(akunPeserta(no));
  const kw = mongo(`return db.ar_receipts.find({entity_id:"${k.KSC}",status:{$nin:["void","cancelled"]}},{_id:0,id:1,number:1}).sort({created_at:-1}).limit(1).toArray()[0]`);
  assert(kw, "belum ada kwitansi Sukacita untuk dicetak");
  const sebelum = potretNaskah();
  k.simpanJson(r, "sebelum.json", sebelum);
  const bersih = (t) => dk.rata(t).replace(/Dicetak \d{2} \w{3} \d{4}( [\d.]+ WIB)?/g, "").trim();
  const cetak = async (nama) => dk.simpan(r, nama, await dk.unduhApi(fin, `/pdf/render/${JENIS}/${kw.id}?format=pdf`));
  const k0 = await cetak("00-kwitansi-sebelum");
  r.note(`Kwitansi pembanding ${kw.number} · pdf_templates ${sebelum.pdf_templates.length} baris · format nomor ${sebelum.doc_number_formats.length} baris`);
  let diubah = false;

  await r.step(1, "Admin (pelatih)", "Buka Pengaturan › Dokumen & Notifikasi › tab [[Penomoran Dokumen]] (lapisan Sukacita) → baca kelompok Keuangan",
    "Tiap jenis dokumen: contoh nomor berikutnya (mis. KSC/AR-000xx untuk Kwitansi), awalan, lebar angka, sisipan tanggal, mulai lagi dari 1, deret, sumber; Faktur Komersial terkunci (nomornya mengikuti pesanan)", async () => {
      await r.login("admin");
      await r.go("settings-doc-numbering", `&entity=${k.KSC}`);
      await r.tid("docnum-view").waitFor();
      await r.tid("docnum-group-Keuangan").waitFor({ timeout: 20000 });
      await r.idle(800);
      const next = await r.text("docnum-next-ar");
      const angka = (s) => Number(String(s).replace(/^.*-/, ""));
      assert(next.startsWith("KSC/AR-") && angka(next) > angka(kw.number), `nomor kwitansi berikutnya ${next} (terakhir ${kw.number})`);
      const inv = await r.tid("docnum-locked-inv").count() ? await r.text("docnum-locked-inv") : "";
      const rows = [];
      for (const kind of ["ar", "cash", "je", "cb", "fkt"]) {
        if (await r.tid(`docnum-row-${kind}`).count()) rows.push((await r.text(`docnum-row-${kind}`)).slice(0, 80));
      }
      await k.potret(r, r.tid("docnum-row-ar"), "penomoran-keuangan");
      return `berikutnya ${next} (terakhir ${kw.number}) · faktur: ${inv || "-"} · ${rows.join(" | ")}`;
    });

  await r.step(2, "Admin (pelatih)", "Klik [[Ubah]] pada baris Kwitansi → baca pratinjau → [[Batal]]",
    "Pop-up 'Ubah format nomor · Kwitansi' menampilkan awalan, lebar angka, sisipan tanggal, mulai lagi dari 1 dan pratinjau nomor; ditutup tanpa menyimpan (mengubah format di tengah tahun = keputusan pemilik)", async () => {
      await r.tid("docnum-edit-ar").click();
      await r.tid("docnum-edit").waitFor();
      await r.tid("docnum-edit-preview").waitFor();
      await r.idle(600);
      const pv = (await r.text("docnum-edit-preview"));
      await k.potret(r, r.tid("docnum-edit-preview"), "ubah-format-nomor");
      await r.tid("docnum-edit-cancel").click();
      await r.tid("docnum-edit").waitFor({ state: "detached", timeout: 8000 });
      return pv.slice(0, 200);
    });

  try {
    await r.step(3, "Admin (pelatih)", "Tab [[Template Dokumen]] → [[Desainer PDF]] → *Jenis Dokumen* Kwitansi · *PT* Sukacita Textile · *Berlaku untuk* Hanya Sukacita Textile → bagian [[Naskah]] → *Teks penutup* → [[Simpan Template]]",
      "Pesan 'Aturan khusus Sukacita Textile tersimpan — PT lain tidak berubah.'; pratinjau memuat teks penutup dengan nomor kwitansi terisi", async () => {
        await k.klikPotret(r, r.tid("hub-tab-pdf-templates"), "tab-template-dokumen");
        await r.tid("doc-templates-view").waitFor();
        await r.tid("doc-templates-tabs-desainer").click();
        await r.tid("pdf-template-designer").waitFor();
        await k.pilihNilai(r, "pdf-doctype-select", JENIS);
        await r.idle(500);
        await k.pilihNilai(r, "pdf-entity-select", k.KSC);
        await k.pilihNilai(r, "pdf-scope-select", "pt");
        await r.idle(600);
        await r.tid("pdf-tab-naskah").click();
        await r.tid("pdf-closing-note").fill(PENUTUP);
        await k.potret(r, r.tid("pdf-save-template"), "naskah-penutup");
        await r.tid("pdf-save-template").click();
        diubah = true;
        await r.tid("pdf-msg").waitFor({ timeout: 15000 });
        const msg = await r.text("pdf-msg");
        assert(/PT lain tidak berubah/.test(msg), `pesan simpan: ${msg}`);
        await r.idle(1200);
        await r.shot("naskah-tersimpan", { full: true });
        const row = mongo(`return db.pdf_templates.findOne({doc_type:"${JENIS}",entity_id:"${k.KSC}"},{_id:0,config:1})`);
        assert(row && row.config && row.config.closing_note === PENUTUP, "naskah khusus Sukacita tidak tersimpan");
        return msg;
      });

    await r.step(4, "Finance", `Masuk dengan akun peserta → Pusat Dokumen › Cetak PDF & Label: jenis [[Kwitansi]], cari ${kw.number}, klik ikon [[Unduh PDF]]`,
      `Kwitansi memuat kalimat 'Simpan kwitansi ${kw.number} ini sebagai bukti pembayaran yang sah.' — token {{nomor}} terisi nomor kwitansi`, async () => {
        await r.login(akunPeserta(no));
        await r.go("document-center");
        await r.tid("document-center").waitFor();
        await k.pilihNilai(r, "dc-doctype-select", JENIS);
        await r.tid("dc-search").fill(kw.number);
        await r.tid(`dc-row-${kw.id}`).waitFor({ timeout: 20000 });
        await k.potret(r, r.tid(`dc-download-${kw.id}`), "pusat-dokumen-kwitansi");
        const [dl] = await Promise.all([r.page.waitForEvent("download"), r.tid(`dc-download-${kw.id}`).click()]);
        const d = dk.simpan(r, "01-kwitansi-dengan-naskah", fs.readFileSync(await dl.path()));
        const harap = PENUTUP.replace("{{nomor}}", kw.number);
        assert(dk.rata(d.text).includes(harap), `teks penutup tidak tercetak: ${(/Simpan kwitansi[^\n]*/.exec(d.text) || ["(tidak ada)"])[0]}`);
        return harap;
      });
  } finally {
    await r.step(5, "Admin (pelatih)", "Kembali ke Desainer PDF (Kwitansi · Hanya Sukacita) → klik [[Kembali ke aturan semua PT]] → [[Kembalikan]]",
      "Pesan 'Sukacita kembali mengikuti aturan semua PT.'; naskah & format nomor tersimpan sama persis dengan sebelum peragaan; kwitansi tercetak sama dengan sebelum (selain stempel 'Dicetak')", async () => {
        if (diubah) {
          await r.login("admin");
          await r.go("pdf-templates", `&entity=${k.KSC}`);
          await r.tid("doc-templates-tabs-desainer").click();
          await r.tid("pdf-template-designer").waitFor();
          await k.pilihNilai(r, "pdf-doctype-select", JENIS);
          await r.idle(500);
          await k.pilihNilai(r, "pdf-entity-select", k.KSC);
          await k.pilihNilai(r, "pdf-scope-select", "pt");
          await r.idle(800);
          await k.klikPotret(r, r.tid("pdf-reset-default"), "kembali-ke-semua-pt");
          await r.tid("confirm-modal-confirm").waitFor();
          await r.tid("confirm-modal-confirm").click();
          await r.tid("pdf-msg").waitFor({ timeout: 15000 }).catch(() => {});
          if (mongo(`return db.pdf_templates.countDocuments({doc_type:"${JENIS}",entity_id:"${k.KSC}"})`)
              && !sebelum.pdf_templates.some((x) => x.doc_type === JENIS && x.entity_id === k.KSC)) {
            await admin.call("DELETE", `/pdf/templates/${JENIS}?entity_id=${k.KSC}`);   // cadangan bila layar gagal
          }
        }
        const sesudah = potretNaskah();
        k.simpanJson(r, "sesudah.json", sesudah);
        assert(JSON.stringify(sesudah) === JSON.stringify(sebelum), `naskah/format berubah: ${k.beda(sebelum, sesudah)}`);
        const k1 = await cetak("02-kwitansi-sesudah");
        assert(bersih(k1.text) === bersih(k0.text), "kwitansi sesudah dikembalikan berbeda dengan sebelum peragaan");
        await r.shot("desainer-kembali");
        return `pdf_templates ${sesudah.pdf_templates.length} baris = sebelum · kwitansi ${kw.number} identik dengan sebelum`;
      });
  }
  await r.finish();
})();
