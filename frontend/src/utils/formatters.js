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
