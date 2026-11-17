/**
 * apPartyApi (S5, pelatihan keuangan 18 Nov — permintaan pemilik "hutang piutang per pihak") — pembantu murni layar
 * Keuangan › Hutang › Hutang per Pemasok dan form "Bayar beberapa tagihan" (dipakai juga uji jest).
 *
 * Server: `GET /vendor-bills/payables/by-supplier` (daftar) dan `/vendor-bills/payables/by-supplier/{id}` (rincian),
 * keduanya `vendor_bill.view` (`backend/services/ap_party_service.py`). Bayar = pintu yang SUDAH ADA,
 * `POST /vendor-bills/{id}/pay` (PK-05), satu kunci idempoten per tagihan.
 */
import { useRef } from "react";
import { formatCurrency } from "../../../utils/formatters";
import { cekNominalBayar, rpSen } from "../payments/PaySupplierModal";

export const AP_BUCKETS = [
  { key: "not_due", label: "Belum jatuh tempo" },
  { key: "1-30", label: "1–30 hari" },
  { key: "31-60", label: "31–60 hari" },
  { key: "61-90", label: "61–90 hari" },
  { key: ">90", label: "> 90 hari" },
];

/** Kolom umur dari server (`aging_labels`); cadangan = judul baku yang sama dengan Hutang › Tagihan. */
export function apBucketColumns(labels) {
  const src = Array.isArray(labels) && labels.length ? labels : AP_BUCKETS;
  return src.filter((b) => AP_BUCKETS.some((x) => x.key === b.key));
}

/** Saringan daftar (dropdown + kartu angka). */
export const SARINGAN = [
  { value: "semua", label: "Semua pemasok" },
  { value: "lewat", label: "Lewat jatuh tempo" },
  { value: "lewat60", label: "Lewat lebih dari 60 hari" },
  { value: "kontrabon", label: "Ada tagihan di kontrabon" },
  { value: "potongan", label: "Ada potongan belum dipakai" },
];

export const URUTAN = [
  { value: "telat", label: "Urut: lewat jatuh tempo terbesar" },
  { value: "sisa", label: "Urut: sisa hutang terbesar" },
  { value: "jatuh_tempo", label: "Urut: jatuh tempo terdekat" },
  { value: "nama", label: "Urut: nama pemasok" },
];

const potongan = (r) => Number(r.advance || 0) + Number(r.debit_notes || 0);
const lewat60 = (r) => Number(r.aging?.["61-90"] || 0) + Number(r.aging?.[">90"] || 0);

/** Baris yang tampil: cari (nama pemasok / PT) + saringan + urutan. Tidak mengubah larik asal. */
export function filterSupplierRows(rows, { q = "", saring = "semua", urut = "telat" } = {}) {
  const kata = String(q || "").trim().toLowerCase();
  let out = (rows || []).filter((r) => !kata
    || `${r.supplier_name || ""} ${r.entity_label || ""}`.toLowerCase().includes(kata));
  if (saring === "lewat") out = out.filter((r) => Number(r.overdue || 0) > 0.005);
  if (saring === "lewat60") out = out.filter((r) => lewat60(r) > 0.005);
  if (saring === "kontrabon") out = out.filter((r) => Number(r.held_count || 0) > 0);
  if (saring === "potongan") out = out.filter((r) => potongan(r) > 0.005);
  const by = {
    telat: (a, b) => b.overdue - a.overdue || b.outstanding - a.outstanding,
    sisa: (a, b) => b.outstanding - a.outstanding,
    jatuh_tempo: (a, b) => String(a.nearest_due || "9999").localeCompare(String(b.nearest_due || "9999")),
    nama: (a, b) => String(a.supplier_name || "").localeCompare(String(b.supplier_name || ""), "id"),
  }[urut] || (() => 0);
  return [...out].sort((a, b) => by(a, b) || String(a.supplier_name || "").localeCompare(String(b.supplier_name || ""), "id"));
}

/** Jumlah per kolom untuk baris yang tampil (baris total di kaki tabel). */
export function sumSupplierRows(rows) {
  const sen = (v) => Math.round(Number(v || 0) * 100);
  const t = { outstanding: 0, overdue: 0, potongan: 0, bill_count: 0, aging: Object.fromEntries(AP_BUCKETS.map((b) => [b.key, 0])) };
  for (const r of rows || []) {
    t.outstanding += sen(r.outstanding);
    t.overdue += sen(r.overdue);
    t.potongan += sen(potongan(r));
    t.bill_count += Number(r.bill_count || 0);
    for (const b of AP_BUCKETS) t.aging[b.key] += sen(r.aging?.[b.key]);
  }
  const rp = (v) => v / 100;
  return { outstanding: rp(t.outstanding), overdue: rp(t.overdue), potongan: rp(t.potongan), bill_count: t.bill_count,
    aging: Object.fromEntries(Object.entries(t.aging).map(([k, v]) => [k, rp(v)])) };
}

export { potongan as potonganOf };

/** Tagihan yang boleh dicentang untuk dibayar langsung: bersisa dan TIDAK dipegang kontrabon aktif (PK-05). */
export const bisaDibayarLangsung = (b) => Number(b?.outstanding || 0) > 0.005 && !b?.contra_bon;

/**
 * Periksa isian form "Bayar beberapa tagihan". `amounts` = { bill_id: angka } (sudah dibaca dari teks isian).
 * Hasil: `{ items: [{ bill, amount, blok, info }], total, blok }` — `blok` = alasan tombol mati (pertama yang ditemui).
 */
export function cekBayarBanyak(bills, amounts, { accountId = "", allPt = false } = {}) {
  const items = (bills || []).map((bill) => {
    const amount = Number(amounts?.[bill.bill_id]) || 0;
    const cek = cekNominalBayar({ amount, outstanding: bill.outstanding, tolerance: bill.payment_tolerance, type: "vendor_bill" });
    const blok = amount <= 0 ? `Isi nominal untuk ${bill.bill_number}.` : cek.blok ? `${bill.bill_number}: ${cek.blok}` : "";
    return { bill, amount, blok, info: cek.info ? `${bill.bill_number}: ${cek.info}` : "" };
  });
  const total = Math.round(items.reduce((s, it) => s + it.amount * 100, 0)) / 100;
  const blok = allPt ? "Pilih satu PT untuk mencatat pembayaran."
    : !items.length ? "Centang minimal satu tagihan."
      : (items.find((it) => it.blok) || {}).blok || (!accountId ? "Pilih rekening atau kas sumber pembayaran." : "");
  return { items, total, blok };
}

/** Kalimat konfirmasi N5 (nominal total, pemasok, rekening, PT) untuk bayar beberapa tagihan sekaligus. */
export const bayarBanyakConfirmText = ({ count, total, supplier, account, pt }) =>
  `Bayar ${count} tagihan senilai ${rpSen(total)} ke ${supplier || "pemasok"} dari ${account} untuk ${pt}? `
  + "Tiap tagihan dicatat sebagai pembayaran sendiri (satu kas keluar dan satu jurnal per tagihan).";

/** Isi `POST /vendor-bills/{id}/pay` satu tagihan (bentuk sama dengan form Bayar pemasok). */
export function payBodyFor({ amount, method, paidAt, accountId, notes = "", billNumber = "" }) {
  const catatan = String(notes || "").trim();
  return { amount: Number(amount), method, paid_at: paidAt, bank_account_id: accountId,
    notes: catatan || (billNumber ? `Bayar beberapa tagihan sekaligus — ${billNumber}` : "") };
}

/**
 * Kunci idempoten PER TAGIHAN untuk satu niat "bayar beberapa sekaligus": isi sama (kirim ulang sesudah jaringan putus)
 * → kunci sama; sukses / ditolak 4xx / isi berubah → kunci baru. Pola yang sama dengan `useIntentKey`, satu per id.
 */
export function makeBatchKeys(prefix = "vbpay") {
  const map = new Map();
  const keyFor = (id, payload) => {
    const body = JSON.stringify(payload);
    const cur = map.get(id);
    if (cur && cur.body === body) return cur.key;
    const key = `${prefix}-${id}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    map.set(id, { body, key });
    return key;
  };
  const done = (id) => map.delete(id);
  return { keyFor, done };
}

export function useBatchKeys(prefix = "vbpay") {
  const ref = useRef(null);
  if (!ref.current) ref.current = makeBatchKeys(prefix);
  return ref.current;
}

/**
 * Bayar tagihan satu per satu lewat pintu yang ada (`post(url, body, key)` = `moneyPost`). Satu tagihan gagal tidak
 * menghentikan yang lain; hasil per tagihan: `{ bill_id, bill_number, amount, ok, status, outstanding, message }`.
 */
export async function bayarBerurutan({ items, base, keys, post, api, errText = (e) => String(e?.message || e) }) {
  const out = [];
  for (const it of items) {
    const body = payBodyFor({ ...base, amount: it.amount, billNumber: it.bill.bill_number });
    const key = keys.keyFor(it.bill.bill_id, body);
    try {
      const r = await post(`${api}/vendor-bills/${it.bill.bill_id}/pay`, body, key);
      keys.done(it.bill.bill_id);
      const d = r?.data || {};
      out.push({ bill_id: it.bill.bill_id, bill_number: it.bill.bill_number, amount: it.amount, ok: true,
        status: d.status || "", outstanding: Number(d.financials?.outstanding ?? 0),
        message: `${d.status === "paid" ? "Lunas" : "Dibayar sebagian"}${d.warning ? ` — ${d.warning}` : ""}` });
    } catch (e) {
      if (e?.response && e.response.status < 500) keys.done(it.bill.bill_id);
      out.push({ bill_id: it.bill.bill_id, bill_number: it.bill.bill_number, amount: it.amount, ok: false,
        status: "", outstanding: Number(it.bill.outstanding || 0), message: errText(e) });
    }
  }
  return out;
}

/** Ringkasan hasil untuk pesan sesudah bayar. */
export function ringkasHasil(results) {
  const ok = (results || []).filter((r) => r.ok);
  const gagal = (results || []).filter((r) => !r.ok);
  const total = ok.reduce((s, r) => s + Number(r.amount || 0), 0);
  if (!gagal.length) return `${ok.length} tagihan dibayar, total ${formatCurrency(total)}.`;
  if (!ok.length) return `Tidak ada tagihan yang terbayar: ${gagal.length} gagal.`;
  return `${ok.length} tagihan dibayar (total ${formatCurrency(total)}); ${gagal.length} gagal — lihat rinciannya.`;
}

/** Kolom CSV rekap hutang per pemasok dan rekap tagihan satu pemasok (utils/csvExport). */
export const CSV_PEMASOK = [
  { key: "supplier_name", header: "Pemasok" },
  { key: "entity_label", header: "PT" },
  { key: "bill_count", header: "Tagihan terbuka", type: "int" },
  ...AP_BUCKETS.map((b) => ({ header: b.label, type: "num", get: (r) => Number(r.aging?.[b.key] || 0) })),
  { key: "outstanding", header: "Sisa hutang", type: "num" },
  { key: "nearest_due", header: "Jatuh tempo terdekat", type: "date" },
  { key: "advance", header: "Uang muka ke pemasok", type: "num" },
  { key: "debit_notes", header: "Nota debit belum dipotong", type: "num" },
];

export const CSV_TAGIHAN = [
  { key: "bill_number", header: "Nomor tagihan" },
  { key: "supplier_invoice_no", header: "Faktur pemasok" },
  { key: "po_number", header: "PO" },
  { key: "bill_date", header: "Tanggal", type: "date" },
  { key: "due_date", header: "Jatuh tempo", type: "date" },
  { key: "aging_label", header: "Umur" },
  { key: "grand_total", header: "Total", type: "num" },
  { key: "amount_paid", header: "Dibayar", type: "num" },
  { key: "outstanding", header: "Sisa", type: "num" },
  // Review S5 (R-S5-03) — tanpa izin lihat kontrabon server hanya mengirim fakta "dipegang" (nomor & status kosong).
  { header: "Kontrabon", get: (b) => (!b.contra_bon ? ""
    : b.contra_bon.number ? `${b.contra_bon.number} (${b.contra_bon.status_label})` : "Ya") },
];
