/** L03 LN-033 — Pemenuhan produksi per item: jalur supplier (PR→PO) atau makloon (PR→MKO), status & dokumen. */
import { useCallback, useEffect, useState } from "react";
import { Factory, Loader2, PackageCheck, RefreshCw } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import { fmtNum, docStatus } from "./SpecialOrderShared";

const STATUS = {
  ready: ["Siap direalisasi", "#0058CC", "#EAF2FF"], blocked: ["Belum bisa", "#8A5A00", "#FFF6E0"],
  realized: ["Terealisasi", "#1B7F4B", "#E9F7EF"], waiting_material: ["Menunggu bahan", "#B45309", "#FFF1E6"],
  needs_data: ["Data master kurang", "#B45309", "#FFF1E6"], error: ["Gagal — bisa diulang", "#C0392B", "#FDECEC"],
};
const MODE = { supplier: "Supplier", makloon: "Makloon", both: "Supplier atau makloon", unmapped: "Belum diatur" };

function Pill({ status, testId }) {
  const [label, fg, bg] = STATUS[status] || [status, "#6B6B73", "#F2F2F4"];
  return <span className="rounded-full px-2 py-0.5 text-[10.5px] font-bold" style={{ color: fg, background: bg }} data-testid={testId}>{label}</span>;
}

function DocRow({ d }) {
  return (
    <p className="text-[11px]" data-testid={`od-ful-doc-${d.id}`}>
      <b className="font-mono">{d.type === "po" ? "PO" : "MKO"} {d.number}</b> · {d.partner_name || "-"} · {docStatus(d.status)}
      {" · "}rencana {fmtNum(d.quantity)} {d.unit}
      {d.type === "mko" && d.expected_output_qty ? ` · estimasi hasil ${fmtNum(d.expected_output_qty)}` : ""}
      {` · diterima ${fmtNum(d.received_qty || 0)}`}
      {d.type === "mko" && d.material_required ? ` · bahan dicadangkan ${fmtNum(d.material_reserved)}/${fmtNum(d.material_required)}` : ""}
      {d.material_shortage > 0 && <b className="text-[#B45309]"> · kurang bahan {fmtNum(d.material_shortage)}</b>}
    </p>
  );
}

function RouteEditor({ n, can, busy, onSave }) {
  const [route, setRoute] = useState(n.route || n.effective_route || "");
  const [reason, setReason] = useState("");
  const deviation = n.default_route && route && route !== n.default_route;
  const locked = n.active_docs.length > 0;
  if (!can.choose_route) return null;
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-2">
      <KNSelect className="field !w-52 !py-1 text-[11px]" value={route} onValueChange={setRoute} disabled={locked || busy} placeholder="Pilih jalur"
        data-testid={`od-ful-route-select-${n.key}`} options={[{ value: "purchase", label: "Supplier (PR → PO)" }, { value: "makloon", label: "Makloon (PR → MKO)" }]} />
      {(deviation || ["both", "unmapped"].includes(n.source_mode)) && !locked && (
        <input className="input !w-64 !py-1 text-[11px]" placeholder={deviation ? "alasan menyimpang dari default (wajib)" : "alasan memilih jalur"}
          value={reason} onChange={(e) => setReason(e.target.value)} data-testid={`od-ful-route-reason-${n.key}`} />
      )}
      {!locked && (
        <button type="button" className="secondary-button !py-1 text-[11px]" disabled={busy || !route || route === n.route || (deviation && !reason.trim())}
          onClick={() => onSave(n.key, route, reason)} data-testid={`od-ful-route-save-${n.key}`}>Simpan jalur</button>
      )}
      {locked && <span className="text-[10.5px] text-[#6B6B73]" data-testid={`od-ful-route-locked-${n.key}`}>Ganti jalur: batalkan dokumen aktif dulu (tombol di bawah) atau amandemen di modul PO/Order Makloon.</span>}
    </div>
  );
}

function CancelDocs({ n, can, busy, onCancel }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  if (!can.cancel || n.active_docs.length === 0) return null;
  const submit = async () => { await onCancel(n.key, reason.trim()); setOpen(false); setReason(""); };
  if (!open) return <button type="button" className="secondary-button mt-1.5 !py-1 text-[11px]" onClick={() => setOpen(true)} data-testid={`od-ful-cancel-open-${n.key}`}>Batalkan dokumen aktif</button>;
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-2">
      <input className="field w-64 text-[11px]" placeholder="Alasan pembatalan (min. 5 karakter)" value={reason} onChange={(e) => setReason(e.target.value)} data-testid={`od-ful-cancel-reason-${n.key}`} />
      <button type="button" className="secondary-button !py-1 text-[11px] text-[#C0392B]" disabled={busy || reason.trim().length < 5}
        onClick={submit} data-testid={`od-ful-cancel-submit-${n.key}`}>Batalkan {n.active_docs.map((d) => d.number || d.id).join(", ")}</button>
      <button type="button" className="text-[11px] text-[#6B6B73]" onClick={() => setOpen(false)} data-testid={`od-ful-cancel-close-${n.key}`}>Tutup</button>
    </div>
  );
}

function NeedCard({ n, can, busy, onSave, onRealize, onCancel }) {
  return (
    <div className="rounded-lg border border-[#EFF0F2] p-2.5" data-testid={`od-ful-item-${n.key}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[12px] font-semibold">Item {n.line_no} · {n.description || n.product_name || "-"} {n.product_sku && <span className="font-mono text-[11px] text-[#6B6B73]">({n.product_sku})</span>}</p>
        <Pill status={n.status} testId={`od-ful-status-${n.key}`} />
      </div>
      <p className="mt-0.5 text-[11px] text-[#6B6B73]" data-testid={`od-ful-route-info-${n.key}`}>
        {fmtNum(n.quantity)} {n.unit} · sumber master <b>{MODE[n.source_mode] || n.source_mode}</b>
        {" · "}jalur <b>{n.route ? (n.route === "purchase" ? "Supplier" : "Makloon") : n.default_route ? `${n.default_route === "purchase" ? "Supplier" : "Makloon"} (default)` : "belum dipilih"}</b>
        {n.state?.deviation && <span className="text-[#B45309]"> · menyimpang dari default: {n.state.reason}</span>}
        {n.supplier_name && ` · supplier pemenang uji ${n.supplier_name}`}
      </p>
      {n.blockers.length > 0 && n.status !== "realized" && <ul className="mt-1 list-disc pl-4 text-[11px] text-[#8A5A00]" data-testid={`od-ful-blockers-${n.key}`}>{n.blockers.map((b) => <li key={b}>{b}</li>)}</ul>}
      {n.error && n.status !== "realized" && <p className="mt-1 text-[11px] text-[#C0392B]" data-testid={`od-ful-error-${n.key}`}>{n.error}</p>}
      {(n.warnings || []).map((w) => <p key={w} className="mt-1 text-[11px] text-[#B45309]" data-testid={`od-ful-warning-${n.key}`}>{w}</p>)}
      {n.pr && <p className="mt-1 text-[11px]" data-testid={`od-ful-pr-${n.key}`}>PR <b className="font-mono">{n.pr.number}</b> · {docStatus(n.pr.status)}</p>}
      {n.docs.map((d) => <DocRow key={d.id} d={d} />)}
      {n.history_docs.length > 0 && <p className="mt-1 text-[10.5px] text-[#9A9BA3]" data-testid={`od-ful-history-${n.key}`}>Riwayat: {n.history_docs.map((d) => `${d.type.toUpperCase()} ${d.number || d.id} (${docStatus(d.status || "cancelled")})`).join(", ")}</p>}
      <RouteEditor n={n} can={can} busy={busy} onSave={onSave} />
      <CancelDocs n={n} can={can} busy={busy} onCancel={onCancel} />
      {can.realize && ["ready", "error", "needs_data"].includes(n.status) && (
        <button type="button" className="primary-button mt-1.5 !py-1 text-[11px]" disabled={busy} onClick={() => onRealize(n.key)} data-testid={`od-ful-realize-${n.key}`}>
          {busy ? <Loader2 size={12} className="spin" /> : <PackageCheck size={12} />} {n.status === "ready" ? "Realisasi pengadaan" : "Ulangi realisasi"}
        </button>
      )}
    </div>
  );
}

export default function SpecialOrderFulfillmentPanel({ order, onUpdated }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const show = !["draft", "pending_approval", "cancelled"].includes(order.status);
  const load = useCallback(() => {
    axios.get(`${API}/special-orders/${order.id}/fulfillment`).then((r) => setData(r.data)).catch((e) => setErr(e.response?.data?.detail || "Gagal memuat pemenuhan."));
  }, [order.id]);
  useEffect(() => { if (show) load(); }, [show, load, order.updated_at]);
  if (!show) return null;
  if (!data) return err ? <section className="section-card !p-3" data-testid="od-fulfillment"><p className="text-[11px] text-[#C0392B]" data-testid="od-ful-error">{err}</p></section> : null;
  const act = async (fn) => {
    setBusy(true); setErr("");
    try { const r = await fn(); setData(r.data.fulfillment); const o = await axios.get(`${API}/special-orders/${order.id}`); onUpdated?.(o.data); }
    catch (e) { setErr(e.response?.data?.detail || "Aksi gagal."); load(); } finally { setBusy(false); }
  };
  const onSave = (key, route, reason) => act(() => axios.post(`${API}/special-orders/${order.id}/fulfillment/${key}/route`, { route, reason }));
  const onRealize = (key) => act(() => axios.post(`${API}/special-orders/${order.id}/fulfillment/${key}/realize`, {}));
  const onCancel = (key, reason) => act(() => axios.post(`${API}/special-orders/${order.id}/fulfillment/${key}/cancel`, { reason }));
  return (
    <section className="section-card !p-3" data-testid="od-fulfillment">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="flex items-center gap-1 text-[10.5px] font-bold uppercase tracking-wide text-[#8E8E93]"><Factory size={12} /> Pemenuhan produksi per item</p>
        <button type="button" className="secondary-button !py-0.5 text-[11px]" onClick={load} data-testid="od-ful-refresh"><RefreshCw size={11} /> Muat ulang</button>
      </div>
      <p className="mb-2 text-[11px] text-[#6B6B73]">Rilis master ≠ pengadaan. Harga terkunci tidak berarti PO/MKO sudah lahir — status di bawah per item.</p>
      {err && <p className="mb-2 text-[11px] text-[#C0392B]" data-testid="od-ful-error">{err}</p>}
      <div className="grid gap-2">{data.items.map((n) => <NeedCard key={n.key} n={n} can={data.can || {}} busy={busy} onSave={onSave} onRealize={onRealize} onCancel={onCancel} />)}</div>
    </section>
  );
}
