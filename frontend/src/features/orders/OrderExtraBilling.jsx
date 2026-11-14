/**
 * PK-32 (K-14) — bagian **Tagihan tambahan** di rincian pesanan: baris tagihan dari nota debit amandemen
 * (`extra_billing_lines`). Kolom Nota Debit · Keterangan · Nilai · Jatuh tempo; total tagihan = nilai tagihan
 * (grand total + tagihan tambahan). Tidak tampil bila pesanan tidak punya tagihan tambahan.
 */
import { ReceiptText } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";
import { billingTotal, extraBillingLines, extraBillingTotal } from "../../utils/orderBilling";

function tanggal(iso) {
  if (!iso) return "—";
  const [y, m, d] = String(iso).slice(0, 10).split("-");
  return y && m && d ? `${d}/${m}/${y}` : String(iso);
}

export default function OrderExtraBilling({ order }) {
  const rows = extraBillingLines(order);
  if (!rows.length) return null;
  return (
    <section className="section-card" data-testid="order-extra-billing">
      <div className="section-head">
        <p className="flex items-center gap-1.5 text-fs-12 font-bold uppercase tracking-wide text-kn-text-2">
          <ReceiptText size={13} className="text-kn-action" aria-hidden="true" /> Tagihan tambahan
        </p>
      </div>
      <div className="section-body space-y-2">
        <div className="overflow-x-auto">
          <table className="data-table head-wrap w-full text-fs-13">
            <thead>
              <tr>
                <th>Nota Debit</th>
                <th>Keterangan</th>
                <th className="text-right">Nilai</th>
                <th>Jatuh tempo</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((x) => (
                <tr key={x.id || x.debit_note_id} data-testid={`order-extra-billing-row-${x.debit_note_id}`}>
                  <td className="whitespace-nowrap font-semibold text-kn-action">{x.debit_note_number || "—"}</td>
                  <td className="break-words">{x.description || "—"}</td>
                  <td className="whitespace-nowrap text-right tabular-nums">{formatCurrency(x.gross)}</td>
                  <td className="whitespace-nowrap">{tanggal(x.due_date)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 text-fs-13">
          <span className="text-kn-text-2">Tagihan tambahan {formatCurrency(extraBillingTotal(order))}</span>
          <span className="font-bold text-kn-text" data-testid="order-extra-billing-total">
            Total tagihan {formatCurrency(billingTotal(order))}
          </span>
        </div>
      </div>
    </section>
  );
}
