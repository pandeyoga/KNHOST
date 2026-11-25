import { ExternalLink } from "lucide-react";
import DetailModal from "../../components/DetailModal";
import { useEntityScope } from "../../context/EntityScopeContext";
import { entityShortById } from "../../utils/entityLabel";
import { formatCurrency, formatQty, formatDate, formatDateTime } from "../../utils/formatters";
import { ageText, badgeLabel, fmtWhen } from "../sales_admin/workDeskApi";
import DeskBadge from "./DeskBadge";
import { panelFor } from "./deskPanels";

const CARA_TERIMA = { kirim: "Dikirim", ambil: "Diambil" };
const isi = (v) => v !== undefined && v !== null && v !== "";

function valueText(row, queue) {
  if (!isi(row.value)) return "";
  const kind = queue.value_kind;
  if (kind === "count") return "";
  if (kind === "qty") return `${formatQty(row.value)} ${row.unit || ""}`.trim();
  return formatCurrency(Number(row.value) || 0);
}

function buildFields(row, queue, pt) {
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

const TH = "px-2 py-1 text-left text-fs-12 font-medium text-kn-text-2";
const TD = "px-2 py-1 text-fs-13 text-kn-text align-top";

function GenericPanel({ row, queue, p, pt }) {
  const fields = buildFields(row, queue, pt);
  const orderLines = Array.isArray(row.order_lines) ? row.order_lines : [];
  const lines = Array.isArray(row.lines) ? row.lines : [];
  return (
    <div className="grid gap-3">
      <dl className="grid gap-2">
        {fields.map((x) => (
          <div key={x.key} data-testid={`${p}-detail-field-${x.key}`} className="grid gap-0.5 sm:grid-cols-[10rem_1fr] sm:gap-3">
            <dt className="text-fs-12 text-kn-text-2">{x.label}</dt>
            <dd className="text-fs-13 text-kn-text">{x.content}</dd>
          </div>
        ))}
      </dl>
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

/** Pop-up rincian umum baris meja; jenis dokumen yang punya panel di registri memakai panelnya. */
export default function DeskRowDetail({ row, queue: queueProp, testPrefix = "desk", inPlace = () => false, onAction, onOpenFull, onClose }) {
  const queue = queueProp || {};
  const p = testPrefix;
  const { entities } = useEntityScope();
  const pt = entityShortById(entities, row.entity_id, "");
  const ptShown = row.entity_id ? pt : "";
  const Panel = panelFor(row.ref_type);
  const sub = [ptShown, badgeLabel(row.badge), isi(row.age_days) || row.age_kind === "overdue" ? ageText(row) : ""].filter(Boolean).join(" · ");
  const run = (r) => { onClose && onClose(); onAction && onAction(r, queue); };
  const more = Array.isArray(row._moreActions) ? row._moreActions : [];

  return (
    <DetailModal framed size="md" testId={`${p}-detail`} label={`Rincian ${row.number}`} onClose={onClose}>
      <div className="grid gap-3">
        <div className="pr-6">
          <h2 data-testid={`${p}-detail-title`} className="text-fs-16 font-semibold text-kn-text break-words">{`${row.number} · ${row.title}`}</h2>
          {sub && <p data-testid={`${p}-detail-subtitle`} className="text-fs-12 text-kn-text-2">{sub}</p>}
        </div>
        {Panel
          ? <Panel row={row} queue={queue} onAction={onAction} onClose={onClose} onOpenFull={onOpenFull} />
          : <GenericPanel row={row} queue={queue} p={p} pt={ptShown} />}
        <div className="flex flex-wrap items-center gap-2 border-t border-kn-divider pt-3">
          {row.action && (
            <button type="button" className="primary-button btn-sm" data-testid={`${p}-detail-action`} onClick={() => run(row)}>
              {row.action}
              {!inPlace(row) && <ExternalLink size={14} className="ml-1" data-testid={`${p}-detail-action-nav`} title="Pindah ke layar lain" aria-hidden="true" />}
            </button>
          )}
          {more.map((a, i) => (
            <button key={i} type="button" className="secondary-button btn-sm" data-testid={`${p}-detail-action-${i}`} onClick={() => run(a.row)}>{a.label}</button>
          ))}
          {onOpenFull && (
            <button type="button" className="link-button" data-testid={`${p}-detail-open-full`}
              onClick={() => { onClose && onClose(); onOpenFull(row, queue); }}>Buka layar penuh</button>
          )}
        </div>
      </div>
    </DetailModal>
  );
}
