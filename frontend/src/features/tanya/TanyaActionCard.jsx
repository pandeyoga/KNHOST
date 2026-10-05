import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, Wand2, XCircle } from "lucide-react";
import { Button } from "../../components/ui/button";
import { toast } from "../../hooks/use-toast";
import { formatCurrency } from "../../utils/formatters";
import { confirmAction, dismissAction, fetchAction } from "./tanyaApi";

const STATUS = { confirmed: "Sudah disetujui", dismissed: "Diabaikan", running: "Sedang diproses…" };

function PoLines({ pos, qty, setQty, editable }) {
  return pos.map((po, pi) => (
    <div key={pi} className="tanya-action-po" data-testid={`tanya-action-po-${pi}`}>
      <div className="tanya-action-po-head">{po.supplier_name} · gudang {po.warehouse_name}</div>
      {po.items.map((it, ii) => (
        <div key={ii} className="tanya-action-line">
          <span className="tanya-action-name">{it.product_name}</span>
          {editable ? (
            <input type="number" min="0" step="any" className="tanya-action-qty" value={qty[`${pi}-${ii}`] ?? it.quantity}
              onChange={(e) => setQty((q) => ({ ...q, [`${pi}-${ii}`]: e.target.value }))} data-testid={`tanya-action-qty-${pi}-${ii}`} />
          ) : <b>{it.quantity}</b>}
          <span className="tanya-action-unit">{it.unit} × {formatCurrency(it.price)}</span>
        </div>
      ))}
    </div>
  ));
}

function Reminders({ items }) {
  return (
    <ul className="tanya-action-list">
      {items.map((r) => (
        <li key={r.customer_id} data-testid={`tanya-action-reminder-${r.customer_id}`}>
          <b>{r.customer}</b> → {r.sales || "Anda"}
          {r.orders ? ` · ${r.orders.length} SO · ${formatCurrency(r.outstanding)} · terlama ${r.max_days_overdue} hari` : ` · order terakhir ${r.last_order}`}
        </li>
      ))}
    </ul>
  );
}

/** Kartu draf tindakan dari AI (blok kn-action). Baru dijalankan setelah pengguna menekan Setujui. */
export function TanyaActionCard({ proposalId }) {
  const [doc, setDoc] = useState(null);
  const [qty, setQty] = useState({});
  const [busy, setBusy] = useState(false);
  useEffect(() => { fetchAction(proposalId).then(setDoc).catch(() => setDoc({ missing: true })); }, [proposalId]);
  if (!doc) return <div className="tanya-stream-block"><Loader2 className="h-4 w-4 animate-spin inline" /> Memuat draf…</div>;
  if (doc.missing) return null;
  const pending = doc.status === "pending";
  const edits = () => ({ pos: (doc.payload.pos || []).map((po, pi) => ({ items: po.items.map((it, ii) => ({ quantity: Number(qty[`${pi}-${ii}`] ?? it.quantity) })) })) });
  const act = async (fn, okMsg) => {
    setBusy(true);
    try { const d = await fn(); setDoc(d); toast({ title: okMsg }); }
    catch (e) { toast({ title: "Gagal", description: e?.response?.data?.detail || "", variant: "destructive" }); }
    finally { setBusy(false); }
  };
  return (
    <section className={`tanya-action ${doc.status}`} data-testid={`tanya-action-${proposalId}`}>
      <div className="tanya-kicker"><Wand2 className="h-4 w-4" /> Draf tindakan · {doc.title}</div>
      {doc.reason && <p className="tanya-note" data-testid="tanya-action-reason">{doc.reason}</p>}
      {doc.type === "draft_po" ? <PoLines pos={doc.payload.pos} qty={qty} setQty={setQty} editable={pending} /> : <Reminders items={doc.payload.reminders} />}
      {pending ? (
        <div className="tanya-answer-actions">
          <Button size="sm" disabled={busy} onClick={() => act(() => confirmAction(proposalId, doc.type === "draft_po" ? edits() : null), "Tindakan dijalankan")} data-testid="tanya-action-confirm">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />} {doc.type === "draft_po" ? "Setujui & buat PO" : "Setujui & kirim ke sales"}
          </Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => act(() => dismissAction(proposalId), "Draf diabaikan")} data-testid="tanya-action-dismiss">
            <XCircle className="h-4 w-4" /> Abaikan
          </Button>
        </div>
      ) : (
        <div className="tanya-action-status" data-testid="tanya-action-status">
          {STATUS[doc.status] || doc.status}{doc.result?.length ? `: ${doc.result.join(", ")}` : ""}
        </div>
      )}
    </section>
  );
}
