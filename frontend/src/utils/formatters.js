export const formatCurrency = (value) => new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(value || 0);

export const formatQty = (value) => new Intl.NumberFormat("id-ID", { maximumFractionDigits: 2 }).format(value || 0);
// Stempel waktu server (ISO UTC) → "YYYY-MM-DD HH:mm" waktu lokal peramban (WIB). Dulu riwayat memotong string UTC
// sehingga aksi pukul 05.30 WIB tampil "22:30" hari sebelumnya. String tanpa zona waktu dibiarkan apa adanya.
export const formatStamp = (v) => {
  const s = String(v || "");
  if (!/[zZ]|[+-]\d{2}:?\d{2}$/.test(s)) return s.slice(0, 16).replace("T", " ");
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s.slice(0, 16).replace("T", " ");
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
};

// 23 Okt — tanggal/jam tampilan BAKU berzona WIB (zona bisnis yang dipakai server: tenggat, "hari ini", jurnal).
// Dulu tiap layar memformat sendiri dengan zona perangkat → tenggat jendela retur bisa beda sehari antar-layar.
const WIB = "Asia/Jakarta";
/** "YYYY-MM-DD" hari ini menurut WIB — nilai bawaan isian tanggal. 23 Okt: banyak form memakai
 *  `new Date().toISOString().slice(0, 10)` (= tanggal UTC) → sebelum 07.00 WIB terisi tanggal KEMARIN. */
export const todayWib = () => new Date().toLocaleDateString("sv-SE", { timeZone: WIB });
const _validDate = (v) => { if (!v) return null; const d = new Date(v); return Number.isNaN(d.getTime()) ? null : d; };
/** "23 Okt 2026" (WIB). Kosong/tak sah → "—". */
export const formatDate = (v) => {
  const d = _validDate(v);
  return d ? d.toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric", timeZone: WIB }) : "—";
};
/** "23 Okt 2026 01.47 WIB". Kosong/tak sah → "—". */
export const formatDateTime = (v) => {
  const d = _validDate(v);
  return d ? `${d.toLocaleString("id-ID", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: WIB })} WIB` : "—";
};
/** "YYYY-MM-DD" menurut WIB dari stempel waktu ISO — untuk pengelompokan/ekspor. 23 Okt: `.slice(0, 10)` pada
 *  stempel UTC menghasilkan tanggal KEMARIN untuk aksi sebelum 07.00 WIB. Kosong/tak sah → "". */
export const wibDate = (v) => {
  const d = _validDate(v);
  return d ? d.toLocaleDateString("sv-SE", { timeZone: WIB }) : "";
};

// UAT 24 Okt (audit UI tahap 2) — G0-14 · P-06: formatter bersama untuk persen, periode, Rupiah ringkas & desimal.
// Dulu tiap layar memakai `toFixed` (titik desimal: "32.4%", "150.0 jt") dan periode ISO mentah ("2026-10").
const BULAN_PANJANG = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"];
const BULAN_PENDEK = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
/** Angka sah atau null (null/undefined/""/NaN/Infinity → null). */
const _num = (v) => {
  if (v === null || v === undefined || v === "" || typeof v === "boolean") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};
/** Hindari "-0" setelah pembulatan. */
const _noNegZero = (n, digits) => (Math.abs(n) < 0.5 * 10 ** -digits ? 0 : n);

/** Persen id-ID: formatPct(32.4) → "32,4%"; formatPct(0.75, 2) → "0,75%"; formatPct(12, 1, { trim: true }) → "12%".
 *  `v` sudah dalam satuan persen (bukan rasio 0–1). Kosong/tak sah → "—". */
export const formatPct = (v, digits = 1, { trim = false } = {}) => {
  const n = _num(v);
  if (n === null) return "—";
  const s = _noNegZero(n, digits).toLocaleString("id-ID", { minimumFractionDigits: trim ? 0 : digits, maximumFractionDigits: digits });
  return `${s}%`;
};

/** Periode bulan "YYYY-MM" (atau tanggal "YYYY-MM-DD…") → "Oktober 2026"; `{ short: true }` → "Okt 2026".
 *  Kosong → "—"; format lain dikembalikan apa adanya. */
export const formatPeriod = (v, { short = false } = {}) => {
  if (v === null || v === undefined || v === "") return "—";
  const m = /^(\d{4})-(\d{2})/.exec(String(v));
  const idx = m ? Number(m[2]) - 1 : -1;
  if (!m || idx < 0 || idx > 11) return String(v);
  return `${(short ? BULAN_PENDEK : BULAN_PANJANG)[idx]} ${m[1]}`;
};

/** Rupiah ringkas id-ID tanpa ".0": 150000000 → "150 jt"; 1400000000 → "1,4 M"; 12500 → "12,5 rb"; 950 → "950".
 *  Satuan: rb (ribu) · jt (juta) · M (miliar) · T (triliun). `{ rp: true }` → awalan "Rp ". Kosong/tak sah → "—". */
export const formatCompactIDR = (v, { rp = false, digits = 1 } = {}) => {
  const n = _num(v);
  if (n === null) return "—";
  const units = [[1e12, "T"], [1e9, "M"], [1e6, "jt"], [1e3, "rb"]];
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  const pre = rp ? "Rp " : "";
  for (let i = 0; i < units.length; i += 1) {
    const [base, suffix] = units[i];
    if (abs >= base) {
      let scaled = Number((abs / base).toFixed(digits));
      let unit = suffix;
      // 999.960.000 → "1.000 jt" → naik satuan jadi "1 M".
      if (scaled >= 1000 && i > 0) { scaled = Number((abs / units[i - 1][0]).toFixed(digits)); unit = units[i - 1][1]; }
      return `${sign}${pre}${scaled.toLocaleString("id-ID", { maximumFractionDigits: digits })} ${unit}`;
    }
  }
  return `${sign}${pre}${Math.round(abs).toLocaleString("id-ID")}`;
};

/** Desimal id-ID (koma, pemisah ribuan) pengganti `toFixed`: formatDecimal(1234.5) → "1.234,5";
 *  formatDecimal(0.756, 2) → "0,76"; formatDecimal(3, 2, 2) → "3,00". Kosong/tak sah → "—". */
export const formatDecimal = (v, max = 2, min = 0) => {
  const n = _num(v);
  if (n === null) return "—";
  return _noNegZero(n, max).toLocaleString("id-ID", { minimumFractionDigits: Math.min(min, max), maximumFractionDigits: max });
};
