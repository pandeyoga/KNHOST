/**
 * Isi pratinjau kontrabon: fakta, total, lalu gabungan baris barang semua faktur di dalamnya (dikelompokkan per faktur).
 * Kontrabon sendiri tidak membawa baris barang, jadi tiap faktur dimuat lewat `loadVendorBill` (docLoaders)
 * (PT dokumen ikut diingat), paralel, paling banyak 20 faktur. Satu faktur gagal → galat hanya di kelompoknya.
 */
import { useEffect, useMemo, useState } from "react";
import ErrorNotice from "../../../../components/ErrorNotice";
import { useEntityScope } from "../../../../context/EntityScopeContext";
import { entityShortById } from "../../../../utils/entityLabel";
import { formatCurrency, formatDate } from "../../../../utils/formatters";
import { DocPill, SupplierCardLink } from "../../../finance/cards/partyCards";
import { loadVendorBill } from "../docLoaders";
import { PreviewFacts, PreviewLines, PreviewTotals } from "../previewParts";
import { kolomBarangTagihan } from "./VendorBillPreview";

export const BATAS_FAKTUR = 20;

/** Muat faktur kontrabon (maks `BATAS_FAKTUR`) paralel; hasil per faktur `{ loading } | { doc } | { error }`. */
function useFakturKontrabon(bills, entityId) {
  const [hasil, setHasil] = useState({});
  const kunci = bills.map((b) => b.bill_id).join("|");
  useEffect(() => {
    let batal = false;
    setHasil({});
    Promise.allSettled(bills.map((b) => loadVendorBill(b.bill_id, { entityId }))).then((rs) => {
      if (batal) return;
      const next = {};
      rs.forEach((r, i) => { next[bills[i].bill_id] = r.status === "fulfilled" ? { doc: r.value } : { error: r.reason }; });
      setHasil(next);
    });
    return () => { batal = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kunci, entityId]);
  return hasil;
}

export default function ContraBonPreview({ doc, push, canPush, currentUser }) {
  const { entities } = useEntityScope();
  const perms = currentUser?.permissions;
  const semua = useMemo(() => (Array.isArray(doc.bills) ? doc.bills.filter((b) => b && b.bill_id) : []), [doc.bills]);
  const bills = useMemo(() => semua.slice(0, BATAS_FAKTUR), [semua]);
  const hasil = useFakturKontrabon(bills, doc.entity_id);
  const t = doc.totals || {};
  const bisaBuka = canPush("vendor_bill");

  return (
    <div className="grid gap-3" data-testid="doc-preview-contra-bon">
      <PreviewFacts items={[
        { key: "supplier", label: "Pemasok", content: doc.supplier_name
          ? <SupplierCardLink id={doc.supplier_id} name={doc.supplier_name} perms={perms} testId="doc-preview-supplier" /> : "" },
        { key: "entity", label: "PT", content: doc.entity_id ? entityShortById(entities, doc.entity_id, "") : "" },
        { key: "status", label: "Status", content: doc.status ? <DocPill status={doc.status} label={doc.status_label} testId="doc-preview-status" /> : "" },
        { key: "cycle", label: "Siklus", content: doc.cycle_date ? formatDate(doc.cycle_date) : "" },
        { key: "due", label: "Jatuh tempo", content: doc.due_date ? formatDate(doc.due_date) : "" },
      ]} />
      <div className="grid gap-3" data-testid="doc-preview-cb-bills">
        {!bills.length && <PreviewLines columns={kolomBarangTagihan} rows={[]} empty="Belum ada faktur." testId="doc-preview-cb-empty" />}
        {bills.map((b) => {
          const h = hasil[b.bill_id];
          const nomor = b.bill_number || (h && h.doc && h.doc.bill_number) || "—";
          return (
            <section key={b.bill_id} className="grid gap-1" data-testid={`doc-preview-cb-group-${b.bill_id}`}>
              <h3 className="text-fs-13 font-semibold text-kn-text">
                {bisaBuka ? (
                  <button type="button" className="link-button text-left" data-testid={`doc-preview-cb-bill-${b.bill_id}`}
                    title="Lihat ringkasan tagihan"
                    onClick={() => push({ docType: "vendor_bill", docId: b.bill_id, number: b.bill_number, ...(doc.entity_id ? { entityId: doc.entity_id } : {}) })}>
                    {nomor}
                  </button>
                ) : <span data-testid={`doc-preview-cb-bill-${b.bill_id}-text`}>{nomor}</span>}
              </h3>
              {!h && <p className="text-fs-12 text-kn-text-2">Memuat baris faktur…</p>}
              {h && h.error && <ErrorNotice message={h.error} testId={`doc-preview-cb-bill-error-${b.bill_id}`} />}
              {h && h.doc && <PreviewLines columns={kolomBarangTagihan} rows={Array.isArray(h.doc.items) ? h.doc.items : []} testId={`doc-preview-cb-lines-${b.bill_id}`} />}
            </section>
          );
        })}
        {semua.length > BATAS_FAKTUR && (
          <p className="text-fs-12 text-kn-text-2" data-testid="doc-preview-cb-cap">{`Tampil ${BATAS_FAKTUR} faktur pertama dari ${semua.length}.`}</p>
        )}
      </div>
      <PreviewTotals rows={[
        { label: "Total faktur", value: t.bills_total != null ? formatCurrency(t.bills_total) : "" },
        { label: "Potongan", value: Number(t.deductions_total) > 0 ? `− ${formatCurrency(t.deductions_total)}` : "" },
        { label: "Nilai bersih", value: t.net_payable != null ? formatCurrency(t.net_payable) : "", strong: true },
        { label: "Sudah dibayar", value: t.paid_total != null ? formatCurrency(t.paid_total) : "" },
      ]} />
    </div>
  );
}
