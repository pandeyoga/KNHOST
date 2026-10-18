/** SpecialOrderItemsPanel — L03 LN-030: item, sumber desain, dokumen turunan per item, dan redesign. */
import { useState } from "react";
import { GitBranch, Layers } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import FormModal from "../../components/FormModal";

export default function SpecialOrderItemsPanel({ order, canEdit, onCreated }) {
  const [dlg, setDlg] = useState(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const items = order.chain?.items || order.items || [];
  const legacyRedesign = !items.length && !!order.chain?.design;
  const ref = order.redesign_of || {};

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const r = await axios.post(`${API}/special-orders/${order.id}/redesign`, { item_id: dlg.item_id || "", reason });
      setDlg(null); setReason(""); onCreated && onCreated(r.data);
    } catch (e) { setErr(e.response?.data?.detail || e.message); }
    finally { setBusy(false); }
  };

  if (!items.length && !legacyRedesign && !ref.number && !(order.redesigns || []).length) return null;
  return (
    <section className="mb-3 rounded-lg border border-[#EDEEF1] bg-white p-3" data-testid="special-order-items-panel">
      <p className="mb-2 flex items-center gap-1.5 text-[12px] font-bold"><Layers size={14} /> Item & sumber desain ({items.length || 1})</p>
      {ref.number && (
        <p className="mb-2 rounded bg-[#FDECEC] px-2 py-1 text-[11px] text-[#A8221A]" data-testid="special-order-redesign-of">
          Redesign dari <b>{ref.number}</b> · artwork asal <b>{ref.design_code || ref.design_id}</b> — {ref.reason}
        </p>
      )}
      <div className="grid gap-1.5">
        {items.map((it) => <ItemLine key={it.id} it={it} canEdit={canEdit} onRedesign={() => { setDlg({ item_id: it.id, label: it.description }); setErr(""); }} />)}
      </div>
      {legacyRedesign && canEdit && (
        <button className="secondary-button mt-1 text-[11px]" data-testid="special-order-redesign-legacy" onClick={() => setDlg({ item_id: "", label: order.title })}>
          <GitBranch size={12} /> Ubah motif (redesign)
        </button>
      )}
      {(order.redesigns || []).length > 0 && (
        <p className="mt-2 text-[11px] text-[#6B6B73]" data-testid="special-order-redesigns">
          Redesign lanjutan: {(order.redesigns || []).map((r) => r.number).join(", ")}
        </p>
      )}
      {dlg && (
        <FormModal open size="sm" icon={GitBranch} title="Ubah motif = pesanan khusus baru" error={err}
          subtitle={`Item: ${dlg.label || "—"}. Proofing pesanan ini tidak diubah; redesign dibuat sebagai pesanan baru berlabel Redesign dengan tautan asal.`}
          onClose={() => setDlg(null)} onSubmit={submit} busy={busy} submitDisabled={reason.trim().length < 5}
          submitLabel="Buat pesanan redesign" testId="redesign-modal" submitTestId="redesign-submit">
          <textarea className="textarea w-full" rows={3} data-testid="redesign-reason" value={reason} onChange={(e) => setReason(e.target.value)}
            placeholder="Alasan perubahan motif (min. 5 karakter)…" />
        </FormModal>
      )}
    </section>
  );
}

function ItemLine({ it, canEdit, onRedesign }) {
  const dr = it.design_request;
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded border border-[#F0F0F3] bg-[#FAFBFC] px-2 py-1.5" data-testid={`special-order-item-${it.line_no}`}>
      <div className="min-w-0 text-[11.5px]">
        <p className="font-semibold">{it.line_no}. {it.description} · {it.quantity} {it.unit}</p>
        <p className="text-[10.5px] text-[#6B6B73]" data-testid={`special-order-item-source-${it.line_no}`}>
          {it.source_type_label}{it.source_label ? ` — ${it.source_label}` : ""} · {(it.request_types || []).join(", ")}
        </p>
        <p className="text-[10.5px] text-[#6B6B73]" data-testid={`special-order-item-links-${it.line_no}`}>
          {dr ? `Desain ${dr.number} (${dr.status})` : ""}{dr && (it.samples || []).length ? " · " : ""}
          {(it.samples || []).map((s) => `${s.number} ${(s.sample_types || []).join("/")}`).join(" · ")}
          {!dr && !(it.samples || []).length && "Dokumen turunan dibuat saat pesanan disetujui"}
        </p>
      </div>
      {canEdit && it.can_redesign && (
        <button className="secondary-button !py-1 text-[11px]" data-testid={`special-order-item-redesign-${it.line_no}`} onClick={onRedesign}>
          <GitBranch size={12} /> Ubah motif
        </button>
      )}
    </div>
  );
}
