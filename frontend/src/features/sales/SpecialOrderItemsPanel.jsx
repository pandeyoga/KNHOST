/** SpecialOrderItemsPanel — L03 LN-030: item, sumber desain, dokumen turunan per item, dan redesign.
 *  FE-01 lanjutan (keputusan owner 2026-10-21): batal per item — item batal tetap tampil (dicoret + alasan). */
import { useState } from "react";
import { Ban, GitBranch, Layers } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import FormModal from "../../components/FormModal";
import { docStatus } from "./SpecialOrderShared";

const ITEM_CANCEL_BLOCKED = ["cancelled", "shipped", "done"];

export default function SpecialOrderItemsPanel({ order, canEdit, onCreated, canCancelItem = false, onItemCancelled }) {
  const [dlg, setDlg] = useState(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const items = order.chain?.items || order.items || [];
  const legacyRedesign = !items.length && !!order.chain?.design;
  const ref = order.redesign_of || {};
  const activeCount = items.filter((it) => it.status !== "cancelled").length;
  // Sama dengan aturan server: OD belum batal/terkirim/selesai dan masih ada item aktif lain. Sesudah SO pun boleh
  // (keputusan owner) — syarat baris SO (belum terbit/dipick) diperiksa server dan alasannya tampil di modal.
  const cancelOpen = canCancelItem && !ITEM_CANCEL_BLOCKED.includes(order.status) && activeCount > 1;
  const [cancelDlg, setCancelDlg] = useState(null);
  const [cancelReason, setCancelReason] = useState("");

  const submitCancel = async () => {
    setBusy(true); setErr("");
    try {
      const r = await axios.post(`${API}/special-orders/${order.id}/items/${cancelDlg.id}/cancel`, { reason: cancelReason.trim() });
      setCancelDlg(null); setCancelReason("");
      onItemCancelled && onItemCancelled(r.data);
    } catch (e) { setErr(e.response?.data?.detail || e.message); }
    finally { setBusy(false); }
  };

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
    // 23 Okt — judul panel seragam dengan panel lain di halaman ini (kapital kecil abu, `section-card`).
    <section className="section-card mb-3 !p-3" data-testid="special-order-items-panel">
      <p className="mb-2 flex items-center gap-1 text-[10.5px] font-bold uppercase tracking-wide text-[#8E8E93]"><Layers size={12} /> Item & sumber desain · {items.length ? activeCount : 1}
        {items.length > activeCount ? ` aktif · ${items.length - activeCount} batal` : ""}</p>
      {ref.number && (
        <p className="mb-2 rounded bg-[#FDECEC] px-2 py-1 text-[11px] text-[#A8221A]" data-testid="special-order-redesign-of">
          Redesign dari <b>{ref.number}</b> · artwork asal <b>{ref.design_code || ref.design_id}</b> — {ref.reason}
        </p>
      )}
      <div className="grid gap-1.5">
        {items.map((it) => <ItemLine key={it.id} it={it} canEdit={canEdit} onRedesign={() => { setDlg({ item_id: it.id, label: it.description }); setErr(""); }}
          canCancel={cancelOpen && it.status !== "cancelled"} onCancel={() => { setCancelDlg(it); setCancelReason(""); setErr(""); }} />)}
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
      {cancelDlg && (
        <FormModal open size="sm" icon={Ban} title={`Batalkan item ${cancelDlg.line_no}`} error={err}
          subtitle={`${cancelDlg.description || "—"} · ${cancelDlg.quantity} ${cancelDlg.unit}. Item lain tidak berubah. PO/MKO yang belum `
            + "berjalan, sample R&D, dan permintaan desain item ini ikut dibatalkan; harga terkunci item lain tetap."
            + (order.linked_sales_order_id ? ` Baris di SO ${order.linked_sales_order_number || ""} ikut dibatalkan (reservasi dilepas, total dihitung ulang).` : "")
            + " MD diberi tahu."}
          onClose={() => setCancelDlg(null)} onSubmit={submitCancel} busy={busy} submitDisabled={cancelReason.trim().length < 5}
          submitLabel="Batalkan item" testId="od-item-cancel-modal" submitTestId="od-item-cancel-submit">
          <textarea className="textarea w-full" rows={3} data-testid="od-item-cancel-reason" value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)} placeholder="Alasan pembatalan item (min. 5 karakter)…" />
        </FormModal>
      )}
    </section>
  );
}

function ItemLine({ it, canEdit, onRedesign, canCancel, onCancel }) {
  const dr = it.design_request;
  const off = it.status === "cancelled";
  return (
    <div className={`flex flex-wrap items-center justify-between gap-2 rounded border px-2 py-1.5 ${off ? "border-[#F3D6D3] bg-[#FDF6F5]" : "border-[#F0F0F3] bg-[#FAFBFC]"}`}
      data-testid={`special-order-item-${it.line_no}`}>
      <div className="min-w-0 text-[11.5px]">
        <p className={`font-semibold ${off ? "text-[#8E8E93] line-through" : ""}`}>{it.line_no}. {it.description} · {it.quantity} {it.unit}</p>
        {off && (
          <p className="text-[10.5px] font-semibold text-[#A8221A]" data-testid={`special-order-item-cancelled-${it.line_no}`}>
            Dibatalkan{it.cancelled_by ? ` oleh ${it.cancelled_by}` : ""}{it.cancelled_at ? ` · ${String(it.cancelled_at).slice(0, 10)}` : ""} — {it.cancel_reason}
          </p>
        )}
        <p className="text-[10.5px] text-[#6B6B73]" data-testid={`special-order-item-source-${it.line_no}`}>
          {it.source_type_label}{it.source_label ? ` — ${it.source_label}` : ""} · {(it.request_types || []).join(", ")}
        </p>
        <p className="text-[10.5px] text-[#6B6B73]" data-testid={`special-order-item-links-${it.line_no}`}>
          {dr ? `Desain ${dr.number} (${docStatus(dr.status)})` : ""}{dr && (it.samples || []).length ? " · " : ""}
          {(it.samples || []).map((s) => `${s.number} ${(s.sample_types || []).join("/")}`).join(" · ")}
          {!dr && !(it.samples || []).length && "Dokumen turunan dibuat saat pesanan disetujui"}
        </p>
      </div>
      <div className="flex items-center gap-1">
        {canEdit && it.can_redesign && (
          <button className="secondary-button !py-1 text-[11px]" data-testid={`special-order-item-redesign-${it.line_no}`} onClick={onRedesign}>
            <GitBranch size={12} /> Ubah motif
          </button>
        )}
        {canCancel && (
          <button className="secondary-button !py-1 text-[11px] !text-[#A8221A]" data-testid={`special-order-item-cancel-${it.line_no}`} onClick={onCancel}>
            <Ban size={12} /> Batalkan item
          </button>
        )}
      </div>
    </div>
  );
}
