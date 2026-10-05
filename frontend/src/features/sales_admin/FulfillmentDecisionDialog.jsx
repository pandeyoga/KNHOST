/**
 * FulfillmentDecisionDialog — 2026-10 · RENCANA PEMENUHAN per baris (keputusan pemilik).
 * Admin Sales membagi kekurangan tiap baris: stok sendiri · transfer dari PT lain (bisa >1) ·
 * PO ke supplier (lewat PR) · tunggu barang datang. Penuh atau sebagian; sisa tetap backorder.
 */
import { useCallback, useEffect, useState } from "react";
import { ExternalLink, PackageSearch } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import { formatQty } from "../../utils/formatters";
import { apiErrorText } from "../../utils/apiError";
import { fulfillmentPlan, fulfillmentPlanDecide } from "./workDeskApi";
import FulfillmentLineCard from "./FulfillmentLineCard";
import InternalPriceModal from "../interco_prices/InternalPriceModal";
import { internalPriceRequest } from "../interco_prices/internalPriceApi";

const initLine = (ln) => {
  const ic = {};
  const ready = new Set((ln.other_entities || []).filter((o) => o.price_ready !== false).map((o) => o.entity_id));
  (ln.proposal || []).forEach((p) => { if (ready.has(p.entity_id)) ic[p.entity_id] = Math.min(p.qty, ln.backorder_qty); });
  return { stock: 0, reorder: 0, wait: 0, ic };
};

export default function FulfillmentDecisionDialog({ orderId, orderNumber, customerName, onClose, onDecided, onOpenFull }) {
  const [data, setData] = useState(null);
  const [plan, setPlan] = useState({});
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [priceTarget, setPriceTarget] = useState(null);
  const [requested, setRequested] = useState({});

  const load = useCallback(async (keepError = false) => {
    setLoading(true);
    try {
      const res = await fulfillmentPlan(orderId);
      setData(res);
      setPlan(Object.fromEntries((res.lines || []).map((ln) => [ln.product_id, initLine(ln)])));
      if (!keepError) setError("");
    } catch (e) { setError(apiErrorText(e, "Gagal memuat rencana pemenuhan.")); }
    finally { setLoading(false); }
  }, [orderId]);

  async function onPrice(kind, ln, o) {
    const target = { productId: ln.product_id, sku: ln.sku, productName: ln.product_name, unit: ln.unit,
      sellerId: o.entity_id, sellerName: o.entity_name, buyerId: data?.entity_id, buyerName: data?.entity_name,
      note: `Dari rencana pemenuhan ${orderNumber}` };
    if (kind === "create") { setPriceTarget(target); return; }
    try {
      const res = await internalPriceRequest({ seller_entity_id: o.entity_id, buyer_entity_id: data?.entity_id,
        product_id: ln.product_id, order_id: orderId });
      setRequested((cur) => ({ ...cur, [`${ln.product_id}-${o.entity_id}`]: true }));
      setNotice(res.message);
    } catch (e) { setError(apiErrorText(e, "Gagal mengirim permintaan harga internal.")); }
  }
  useEffect(() => { load(); }, [load]);

  const lines = data?.lines || [];
  const history = data?.decisions || [];
  const total = (p) => (p ? p.stock + p.reorder + p.wait + Object.values(p.ic).reduce((s, v) => s + v, 0) : 0);
  const anyQty = lines.some((ln) => total(plan[ln.product_id]) > 0);
  const over = lines.find((ln) => total(plan[ln.product_id]) > ln.backorder_qty + 0.01);

  async function submit() {
    setBusy(true); setError("");
    try {
      const body = {
        note,
        lines: lines.map((ln) => {
          const p = plan[ln.product_id];
          return { product_id: ln.product_id, stock_qty: p.stock, reorder_qty: p.reorder, wait_qty: p.wait,
            interco: Object.entries(p.ic).filter(([, q]) => q > 0).map(([entity_id, qty]) => ({ entity_id, qty })) };
        }),
      };
      const res = await fulfillmentPlanDecide(orderId, body);
      onDecided?.(`${res?.order_number || orderNumber}: ${res?.decision?.summary || "rencana pemenuhan tercatat."}`);
    } catch (e) { setError(apiErrorText(e, "Gagal menjalankan rencana pemenuhan.")); load(true); }
    finally { setBusy(false); }
  }

  return (
    <div className="modal-overlay" data-testid="fulfill-dialog" onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 920, maxHeight: "92vh", overflowY: "auto" }}>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex min-w-0 items-start gap-2">
            <PackageSearch size={17} className="mt-0.5 shrink-0 text-[#B23B14]" />
            <div className="min-w-0">
              <p className="modal-title" data-testid="fulfill-dialog-title">Rencana pemenuhan {orderNumber}</p>
              <p className="modal-subtitle">
                {customerName} · entitas penjual {data?.entity_name || "—"}. Bagi kekurangan tiap baris — penuh atau sebagian; sisa tetap backorder.
              </p>
            </div>
          </div>
          {onOpenFull && (
            <button data-testid="fulfill-open-full" onClick={onOpenFull}
              className="inline-flex shrink-0 items-center gap-1 rounded-full border border-[#CBDFFF] bg-[#F2F7FF] px-2.5 py-1 text-[10.5px] font-bold text-[#0058CC]">
              <ExternalLink size={11} /> Buka Pesanan Lengkap
            </button>
          )}
        </div>
        <ErrorNotice message={error} onDismiss={() => setError("")} testId="fulfill-error" />
        {notice && <p data-testid="fulfill-notice" className="mt-2 rounded-lg bg-[#EAF7EF] px-3 py-2 text-[11.5px] font-semibold text-[#1B7F4B]">{notice}</p>}
        {loading ? (
          <div className="py-10 text-center text-[12px] text-[#6B6B73]" data-testid="fulfill-loading">Menghitung kekurangan & sumber…</div>
        ) : !lines.length ? (
          <p className="py-8 text-center text-[12px] text-[#6B6B73]" data-testid="fulfill-no-shortage">Tidak ada kekurangan aktif pada pesanan ini.</p>
        ) : (
          <div className="mt-3 space-y-3">
            {lines.map((ln) => (
              <FulfillmentLineCard key={ln.product_id} line={ln} value={plan[ln.product_id]}
                canSetPrice={!!data?.can_set_internal_price} onPrice={onPrice} requested={requested}
                onChange={(v) => setPlan((cur) => ({ ...cur, [ln.product_id]: v }))} />
            ))}
            <textarea data-testid="fulfill-note" className="field w-full text-[12px]" rows={2} placeholder="Catatan (opsional)"
              value={note} onChange={(e) => setNote(e.target.value)} />
            {over && <p data-testid="fulfill-over" className="text-[11px] font-semibold text-[#C0392B]">{over.product_name}: total rencana melebihi kekurangan {formatQty(over.backorder_qty)}.</p>}
            <div className="flex justify-end gap-2">
              <button className="secondary-button" data-testid="fulfill-cancel" onClick={onClose}>Batal</button>
              <button className="primary-button" data-testid="fulfill-submit" disabled={busy || !anyQty || !!over} onClick={submit}>
                {busy ? "Menjalankan…" : "Jalankan rencana"}
              </button>
            </div>
          </div>
        )}
        {history.length > 0 && (
          <div className="mt-3 rounded-lg border border-[#EFF0F2] bg-[#FAFAFB] p-2.5" data-testid="fulfill-history">
            <p className="text-[10px] font-bold uppercase text-[#9A9BA3]">Riwayat keputusan</p>
            {history.slice().reverse().map((d, i) => (
              <p key={i} className="mt-1 text-[11px] text-[#3C3C43]">{(d.at || "").slice(0, 16).replace("T", " ")} · {d.by || "—"} · {d.summary}</p>
            ))}
          </div>
        )}
      </div>
      {priceTarget && (
        <InternalPriceModal target={priceTarget} onClose={() => setPriceTarget(null)}
          onSaved={() => { setPriceTarget(null); setNotice(`Harga internal ${priceTarget.sku} tersimpan — transfer sekarang bisa dijalankan.`); load(); }} />
      )}
    </div>
  );
}
