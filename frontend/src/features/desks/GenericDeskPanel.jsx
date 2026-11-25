/**
 * Panel umum baris meja (gelombang 1): bidang ringkas baris + barang pesanan/kurang. Dipisah dari `DeskRowDetail` agar
 * `DeskDocPanel` memakai pembangun bidang yang sama (tanpa siklus impor `DeskRowDetail` ↔ `deskPanels`).
 */
import DeskBadge from "./DeskBadge";
import { formatCurrency, formatQty, formatDate, formatDateTime } from "../../utils/formatters";
import { ageText, fmtWhen } from "../sales_admin/workDeskApi";

const CARA_TERIMA = { kirim: "Dikirim", ambil: "Diambil" };
const isi = (v) => v !== undefined && v !== null && v !== "";

function valueText(row, queue) {
  if (!isi(row.value)) return "";
  const kind = queue.value_kind;
  if (kind === "count") return "";
  if (kind === "qty") return `${formatQty(row.value)} ${row.unit || ""}`.trim();
  return formatCurrency(Number(row.value) || 0);
}

export function buildFields(row, queue, pt) {
  const overdue = row.age_kind === "overdue";
  const f = [];
  const add = (key, label, content) => { if (content !== "" && content !== null && content !== undefined && content !== false) f.push({ key, label, content }); };
  add("subtitle", "Keterangan", row.subtitle ? <span className="whitespace-pre-line break-words">{row.subtitle}</span> : "");
  add("badge", "Status", row.badge ? <DeskBadge badge={row.badge} /> : "");
  add("entity_id", "PT", pt);
  add("value", queue.value_label || "Nilai", valueText(row, queue));
  add("age", overdue ? "Lewat jatuh tempo" : "Menunggu", isi(row.age_days) || overdue ? ageText(row) : "");
  add("at", overdue ? "Jatuh tempo" : "Masuk", row.at ? fmtWhen(row.at) : "");
  add("sales_name", "Sales", row.sales_name);
  add("customer_city", "Kota", row.customer_city);
  add("booking_until", "Batas cadangan", row.booking_until ? formatDateTime(row.booking_until) : "");
  add("payment_due_date", "Jatuh tempo bayar", row.payment_due_date ? formatDate(row.payment_due_date) : "");
  add("order_number", "Pesanan", row.order_number);
  add("fulfillment_method", "Cara terima", CARA_TERIMA[row.fulfillment_method] || "");
  add("revision_count", "Revisi", isi(row.revision_count) ? String(row.revision_count) : "");
  return f;
}

const TH = "px-2 py-1 text-left text-fs-12 font-semibold text-kn-text-2";
const TD = "px-2 py-1 text-fs-13 text-kn-text align-top";

/** Daftar bidang (dl). `except` = kunci bidang yang disembunyikan. */
export function FieldList({ row, queue, p, pt, except = [] }) {
  const fields = buildFields(row, queue, pt).filter((x) => !except.includes(x.key));
  return (
    <dl className="grid gap-2">
      {fields.map((x) => (
        <div key={x.key} data-testid={`${p}-detail-field-${x.key}`} className="grid gap-0.5 sm:grid-cols-[10rem_1fr] sm:gap-3">
          <dt className="text-fs-12 text-kn-text-2">{x.label}</dt>
          <dd className="text-fs-13 text-kn-text">{x.content}</dd>
        </div>
      ))}
    </dl>
  );
}

/** `except` = bidang yang sudah ada di judul pop-up; `withOrderLines=false` = tabel barang-per-gudang tidak diulang (sudah di pratinjau). */
export function GenericPanel({ row, queue, p = "desk", pt = "", except = [], withOrderLines = true }) {
  const orderLines = withOrderLines && Array.isArray(row.order_lines) ? row.order_lines : [];
  const lines = Array.isArray(row.lines) ? row.lines : [];
  return (
    <div className="grid gap-3">
      <FieldList row={row} queue={queue} p={p} pt={pt} except={except} />
      {orderLines.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full" data-testid={`${p}-detail-lines`}>
            <thead><tr><th className={TH}>Barang</th><th className={TH}>Jumlah</th><th className={TH}>Gudang</th></tr></thead>
            <tbody>
              {orderLines.map((l, i) => (
                <tr key={i} data-testid={`${p}-detail-line-${i}`} className="border-t border-kn-divider">
                  <td className={`${TD} break-words`}>{l.product_name}{l.sku ? ` · ${l.sku}` : ""}</td>
                  <td className={`${TD} tabular-nums`}>{`${formatQty(l.quantity)} ${l.unit || ""}`.trim()}</td>
                  <td className={TD}>{l.warehouse || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {lines.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full" data-testid={`${p}-detail-shortage`}>
            <thead><tr><th className={TH}>Barang kurang</th><th className={TH}>Jumlah</th></tr></thead>
            <tbody>
              {lines.map((l, i) => (
                <tr key={i} data-testid={`${p}-detail-shortage-${i}`} className="border-t border-kn-divider">
                  <td className={`${TD} break-words`}>{l.product_name}</td>
                  <td className={`${TD} tabular-nums`}>{`${formatQty(l.backorder_qty)} ${l.unit || ""}`.trim()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

