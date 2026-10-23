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
