/**
 * exportSpec.js — FIX-4 (audit WMS-RFID 9 Nov · K-B4-07 · K-B3b-04 · EXP-01) — pembangun spesifikasi tombol
 * baku "Unduh" (komponen `ExportMenu`) untuk mesin Pusat Export (`POST /api/export-center/quick`).
 *
 * Aturan yang dijamin (dipakai SEMUA daftar, jadi diuji sekali di Jest):
 *  1. Saringan daftar = kondisi Pusat Export (`{field, cmp, value}`) yang digabung DAN; nilai kosong DIABAIKAN
 *     (chip "Semua" tidak menyaring apa pun) — sama dengan daftar yang sedang dilihat.
 *  2. Kotak cari = teks `search`; server mencari di jalur yang SAMA dengan endpoint daftarnya (registry dataset,
 *     termasuk nama produk/gudang/PT yang diselesaikan ke id) — bukan daftar kolom dari klien.
 *  3. Cakupan: `work` (daftar pekerjaan fisik FIX-1: lokasi tampilan + semua PT ditugaskan), `active` (PT aktif),
 *     `all` (semua PT ditugaskan); `locationView` menambah saringan tampilan lokasi (layar stok, FIX-1 K-I3).
 *     Pilihan lokasi sendiri ikut header `X-Location-Scope` yang sudah dipasang `apiClient` — tidak diulang di sini.
 *
 * Sengaja TANPA import supaya murah diuji.
 */
export const QUICK_MAX_ROWS = 50000;
export const EXPORT_FORMATS = [
  { key: "xlsx", label: "Excel (.xlsx)", hint: "Bawaan — kolom berformat + lembar Ringkasan (saringan & cakupan)." },
  { key: "csv", label: "CSV (titik-koma)", hint: "Untuk Excel wilayah Indonesia: pemisah ;, desimal koma." },
];

const isEmpty = (v) => v === undefined || v === null || v === "" || (Array.isArray(v) && v.length === 0);

/** Satu kondisi: `["status", "in", ["a","b"]]` atau `{field, cmp, value}`; `null`/kosong diabaikan. */
export function toCondition(f) {
  if (!f) return null;
  if (!Array.isArray(f) && f.items) {               // grup bersarang {op: "or"|"and", items: [...]}
    const items = f.items.map(toCondition).filter(Boolean);
    return items.length ? { op: f.op === "or" ? "or" : "and", items } : null;
  }
  const [field, cmp = "eq", value] = Array.isArray(f) ? f : [f.field, f.cmp || "eq", f.value];
  if (!field) return null;
  if (cmp === "empty" || cmp === "not_empty") return { field, cmp };
  if (isEmpty(value)) return null;
  if (cmp === "in") {
    const list = (Array.isArray(value) ? value : String(value).split(",")).map((x) => String(x).trim()).filter(Boolean);
    return list.length ? { field, cmp, value: list } : null;
  }
  return { field, cmp, value };
}

/** Saringan → pohon filter Pusat Export (`{op:"and", items}`) atau `null` bila tanpa saringan. */
export function buildExportFilter({ filters = [] } = {}) {
  const items = (filters || []).map(toCondition).filter(Boolean);
  return items.length ? { op: "and", items } : null;
}

/** Badan permintaan `POST /export-center/quick`. */
export function buildExportSpec({
  dataset, format = "xlsx", label = "", scope = "active", filters, search, sort, dateRange, entityId,
  locationView = false, columns,
} = {}) {
  const body = { dataset, format, label: String(label || "").slice(0, 60), entity_scope: scope || "active" };
  const filter = buildExportFilter({ filters });
  if (filter) body.filter = filter;
  const text = String((search && typeof search === "object" ? search.text : search) || "").trim();
  if (text) body.search = text.slice(0, 100);
  if (Array.isArray(columns) && columns.length) body.columns = columns;
  if (Array.isArray(sort) && sort.length) body.sort = sort.filter((s) => s && s.key).map((s) => ({ key: s.key, dir: s.dir === "desc" ? "desc" : "asc" }));
  if (dateRange?.field && (dateRange.from || dateRange.to)) {
    body.date_field = dateRange.field;
    if (dateRange.from) body.date_from = dateRange.from;
    if (dateRange.to) body.date_to = dateRange.to;
  }
  if (entityId && entityId !== "all") body.entity_id = entityId;
  if (locationView) body.location_view = true;
  return body;
}

/** Nama berkas cadangan bila server tidak mengirim Content-Disposition: `kedatangan_20261109_1405.xlsx` (WIB). */
export function exportFileName(label, format, now = new Date()) {
  const wib = new Date(now.getTime() + 7 * 3600 * 1000);
  const p = (n) => String(n).padStart(2, "0");
  const stamp = `${wib.getUTCFullYear()}${p(wib.getUTCMonth() + 1)}${p(wib.getUTCDate())}_${p(wib.getUTCHours())}${p(wib.getUTCMinutes())}`;
  const stem = String(label || "data").trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) || "data";
  return `${stem}_${stamp}.${format === "csv" ? "csv" : "xlsx"}`;
}

/** Nama berkas dari header `Content-Disposition` (filename= atau filename*=UTF-8''…). */
export function fileNameFromDisposition(header) {
  const h = String(header || "");
  const star = /filename\*=UTF-8''([^;]+)/i.exec(h);
  if (star) { try { return decodeURIComponent(star[1].trim()); } catch { /* jatuh ke filename= */ } }
  const plain = /filename="?([^";]+)"?/i.exec(h);
  return plain ? plain[1].trim() : "";
}
