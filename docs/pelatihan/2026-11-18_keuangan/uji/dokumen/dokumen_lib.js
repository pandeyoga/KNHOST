// Pembantu audit DOKUMEN CETAK (Pelatihan Keuangan 18 Nov 2026) — dipakai D1/D2/D3.
//
// Satu dokumen = satu PDF yang diunduh (lewat tombol layar atau API) → teks (`pdftotext -layout`) + gambar halaman
// (`pdftoppm -r 80`) di `hasil/<kode>/` → dicocokkan dengan database (nomor, tanggal, pihak, baris, total, terbilang).
//
//   const dk = require("./dokumen_lib");
//   const pdf = await dk.unduhApi(sesi, "/pdf/render/invoice/so_…?format=pdf");
//   const d = dk.simpan(run, "faktur-SO86", pdf);      // { pdf, txt, png[], text, info }
//   dk.cekFormat(d);                                    // A4, uang gaya Indonesia, tanpa label Inggris, tanpa "Rp" terpotong
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { API } = require("../lib");

const BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
const BULAN_PANJANG = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
  "November", "Desember"];

/** Nominal → sen bulat (setengah ke atas). */
const sen = (n) => Math.round(Math.abs(Number(n || 0)) * 100 + 1e-6);

/** "Rp 3.381.337,50" / "Rp 3.381.337" — format yang HARUS tercetak (sen hanya bila nominalnya bersen). */
function rpCetak(n) {
  const s = sen(n);
  const rupiah = Math.floor(s / 100);
  const c = s % 100;
  const body = rupiah.toLocaleString("id-ID") + (c ? "," + String(c).padStart(2, "0") : "");
  return (Number(n) < 0 && s ? "-" : "") + "Rp " + body;
}

const SATUAN = ["", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan", "sepuluh", "sebelas"];
function _tb(n) {
  if (n < 12) return SATUAN[n];
  if (n < 20) return `${_tb(n - 10)} belas`;
  if (n < 100) return `${_tb(Math.floor(n / 10))} puluh ${_tb(n % 10)}`.trim();
  if (n < 200) return `seratus ${_tb(n - 100)}`.trim();
  if (n < 1000) return `${_tb(Math.floor(n / 100))} ratus ${_tb(n % 100)}`.trim();
  if (n < 2000) return `seribu ${_tb(n - 1000)}`.trim();
  if (n < 1e6) return `${_tb(Math.floor(n / 1000))} ribu ${_tb(n % 1000)}`.trim();
  if (n < 1e9) return `${_tb(Math.floor(n / 1e6))} juta ${_tb(n % 1e6)}`.trim();
  if (n < 1e12) return `${_tb(Math.floor(n / 1e9))} miliar ${_tb(n % 1e9)}`.trim();
  return `${_tb(Math.floor(n / 1e12))} triliun ${_tb(n % 1e12)}`.trim();
}
/** Terbilang pembanding (ditulis terpisah dari kode aplikasi): "Tiga juta … rupiah lima puluh sen". */
function terbilang(n) {
  const s = sen(n);
  const w = _tb(Math.floor(s / 100)).replace(/\s+/g, " ").trim();
  let out = w ? `${w} rupiah` : "nol rupiah";
  if (s % 100) out += ` ${_tb(s % 100).replace(/\s+/g, " ").trim()} sen`;
  return out[0].toUpperCase() + out.slice(1);
}

/** Tanggal ISO → "17 Nov 2026" (WIB). */
function tgl(iso) {
  if (!iso) return "";
  const d = new Date(/T/.test(iso) ? iso : `${iso}T00:00:00+07:00`);
  const w = new Date(d.getTime() + 7 * 3600 * 1000);
  return `${String(w.getUTCDate()).padStart(2, "0")} ${BULAN[w.getUTCMonth()]} ${w.getUTCFullYear()}`;
}

/** "17 November 2026" (gaya cetak sisi peramban, `toLocaleDateString id-ID long`). */
function tglPanjang(iso) {
  const d = new Date(/T/.test(iso) ? iso : `${iso}T00:00:00+07:00`);
  const w = new Date(d.getTime() + 7 * 3600 * 1000);
  return `${String(w.getUTCDate()).padStart(2, "0")} ${BULAN_PANJANG[w.getUTCMonth()]} ${w.getUTCFullYear()}`;
}

/** Angka qty gaya Indonesia: 121.85 → "121,85". */
const qty = (n) => Number(n || 0).toLocaleString("id-ID", { maximumFractionDigits: 2 });

async function unduhApi(sesi, p) {
  const r = await fetch(API + p, { headers: { Authorization: `Bearer ${sesi.token}` } });
  const b = Buffer.from(await r.arrayBuffer());
  if (!r.ok) {
    const e = new Error(`GET ${p} → ${r.status}: ${b.toString().slice(0, 300)}`);
    e.status = r.status; throw e;
  }
  return b;
}

/** Simpan PDF + teks + gambar halaman ke `run.dir` dengan nama `nama`. */
function simpan(run, nama, buf) {
  const base = path.join(run.dir, nama);
  fs.writeFileSync(base + ".pdf", buf);
  execFileSync("pdftotext", ["-layout", base + ".pdf", base + ".txt"]);
  for (const f of fs.readdirSync(run.dir)) if (f.startsWith(nama + "-") && f.endsWith(".png")) fs.unlinkSync(path.join(run.dir, f));
  execFileSync("pdftoppm", ["-r", "80", "-png", base + ".pdf", base]);
  const info = execFileSync("pdfinfo", [base + ".pdf"]).toString();
  const png = fs.readdirSync(run.dir).filter((f) => f.startsWith(nama + "-") && f.endsWith(".png")).sort();
  return { nama, pdf: base + ".pdf", txt: base + ".txt", png, text: fs.readFileSync(base + ".txt", "utf8"), info,
    halaman: Number((/Pages:\s+(\d+)/.exec(info) || [])[1] || 0) };
}

/** Teks satu baris (spasi dirapatkan) — untuk pencarian frasa yang terbungkus di beberapa baris kolom. */
const rata = (t) => t.replace(/\s+/g, " ");

/** Kalimat terbilang yang tercetak (bisa terbungkus dua baris). */
function terbilangTercetak(text) {
  const m = /Terbilang:\s*([\s\S]*?)(?:\n\s*\n|Catatan:|$)/.exec(text);
  if (!m) return "";
  const t = rata(m[1]).trim();
  const k = /^(.*?\brupiah)( [a-z ]+? sen)?\b/.exec(t);   // kalimat berakhir di "rupiah" / "… sen"
  return k ? k[1] + (k[2] || "") : t;
}

// Label Inggris yang TIDAK boleh tercetak sebagai judul/label dokumen (pelanggan & pemasok membaca Bahasa Indonesia).
const LABEL_INGGRIS = [/\bINVOICE\b/, /Official Receipt/i, /Vendor Bill/i, /Payment Voucher/i, /Received Voucher/i,
  /GRAND TOTAL/i, /Prepared By/i, /Sales Quotation/i, /Customer & Tujuan/i, /Term Pembayaran/i, /\bPetty Cash\b/i];
const BULAN_INGGRIS = /\b\d{1,2} (Oct|Dec|May|Aug|October|December|August)\b/;

/** Cek format umum; kembalikan daftar masalah (kosong = lulus). `opsi.a4=false` untuk dokumen non-A4. */
function cekFormat(d, opsi = {}) {
  const masalah = [];
  if (opsi.a4 !== false && !/Page size:\s+59[5-6](\.\d+)? x 84[1-3](\.\d+)? pts \(A4\)/.test(d.info)) masalah.push(`bukan A4: ${(/Page size:.*/.exec(d.info) || [""])[0]}`);
  for (const re of LABEL_INGGRIS) if (re.test(d.text)) masalah.push(`label Inggris ${re}`);
  if (BULAN_INGGRIS.test(d.text)) masalah.push("bulan berbahasa Inggris");
  if (/Rp\s*$/m.test(d.text)) masalah.push("\"Rp\" terpisah dari angkanya (kolom terlalu sempit)");
  const salah = (d.text.match(/Rp ?[0-9][0-9.,]*/g) || []).filter((x) => !/^-?Rp \d{1,3}(\.\d{3})*(,\d{2})?$/.test(x));
  if (salah.length) masalah.push(`format uang bukan gaya Indonesia: ${[...new Set(salah)].slice(0, 4).join(" | ")}`);
  if (/\{\{\s*[a-z_]+\s*\}\}/.test(d.text)) masalah.push("token naskah {{…}} tercetak mentah");
  if (/&amp;|&#34;|&lt;/.test(d.text)) masalah.push("entitas HTML tercetak mentah");
  return masalah;
}

/** `harus` = daftar frasa yang wajib ada (dibandingkan pada teks rata); kembalikan yang hilang. Frasa berbentuk
 *  `{kata: "DENIM TENCEL TAUPE A"}` cukup bila SEMUA katanya ada (sel tabel sempit membungkus nama ke beberapa baris). */
function hilang(d, harus) {
  const t = rata(d.text).toLowerCase();   // judul dicetak KAPITAL (CSS) — bandingkan tanpa beda huruf besar/kecil
  return harus.filter((h) => {
    if (!h) return false;
    if (typeof h === "object") return !String(h.kata).toLowerCase().split(/\s+/).every((w) => t.includes(w));
    return !t.includes(rata(String(h)).toLowerCase());
  }).map((h) => (typeof h === "object" ? h.kata : h));
}

/** Gagal dengan pesan gabungan bila ada masalah. */
function wajib(masalah, konteks) {
  if (masalah.length) throw new Error(`${konteks}: ${masalah.join("; ")}`);
}

/** Identitas kop PT dari Profil PT (sumber kebenaran kop). */
function profilPt(mongo, eid) {
  return mongo(`const e=db.business_entities.findOne({id:${JSON.stringify(eid)}},{_id:0,legal_name:1,print_name:1,short_name:1,npwp:1,address:1,city:1});
    return {nama:(e.print_name||e.legal_name||e.short_name), npwp:e.npwp||"", alamat:[e.address,e.city].filter(Boolean).join(", ")}`);
}

module.exports = { rpCetak, terbilang, tgl, tglPanjang, qty, unduhApi, simpan, rata, terbilangTercetak, cekFormat, hilang,
  wajib, profilPt, LABEL_INGGRIS, sen };
