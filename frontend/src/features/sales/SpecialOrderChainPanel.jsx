/** SpecialOrderChainPanel — lini masa fase OD + rantai dokumen (OD ↔ Permintaan Desain ↔ Sample ↔ SKU ↔ PR ↔ SO) + referensi pelanggan. */
import { useState } from "react";
import { CheckCircle2, Circle, ExternalLink, Image as ImageIcon, Send, Upload } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ProductColorChip from "../../components/ProductColorChip";
import AttachmentGallery from "../../components/AttachmentThumb";   // UAT 24 Okt (P17)
import { openRnd } from "../rnd/rndDeepLink";
import { SAMPLE_STATUS_META } from "../rnd/rndMeta";
import { docStatus } from "./SpecialOrderShared";
import { formatDate } from "../../utils/formatters";

const TYPE_LABEL = { printing: "Kain printing", labdip: "Warna khusus (labdip)", handfeel: "Handfeel", proofing: "Proofing" };

export default function SpecialOrderChainPanel({ order, canEdit, canRoute = canEdit, onChanged }) {
  const ch = order.chain || {};
  const phases = ch.phases || [];
  const idx = Math.max(0, phases.findIndex(([k]) => k === ch.phase));
  const parallel = ch.phase_parallel || [];
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const routed = !!(order.design_request_id || (order.sample_ids || []).length);
  const approved = !["draft", "pending_approval", "cancelled"].includes(order.status);

  const upload = async (files) => {
    setBusy(true); setMsg("");
    try {
      for (const file of files) { const fd = new FormData(); fd.append("file", file); await axios.post(`${API}/special-orders/${order.id}/references`, fd); }
      setMsg(`${files.length} referensi terunggah.`); onChanged?.();
    } catch (e) { setMsg(e.response?.data?.detail || "Unggah gagal."); } finally { setBusy(false); }
  };
  const route = async () => {
    setBusy(true); setMsg("");
    try { await axios.post(`${API}/special-orders/${order.id}/route`); setMsg("Diteruskan ke Desainer / R&D."); onChanged?.(); }
    catch (e) { setMsg(e.response?.data?.detail || "Gagal meneruskan."); } finally { setBusy(false); }
  };

  return (
    <div className="grid gap-3" data-testid="od-chain-panel">
      {/* M14/M15 (pemilik 16 Nov) — dulu 13 lencana tahap berderet mendatar + "Rantai dokumen" terpisah. Kini SATU lini
          masa VERTIKAL: tiap tahap = status (✓ selesai · ● berjalan · ○ belum), tanggal & pelaku / "menunggu sejak …",
          dokumen tahap itu (rantai dokumen dilebur ke sini), dan aksi HANYA di tahap yang berjalan. */}
      <section className="section-card !p-3" data-testid="od-chain">
        <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-fs-12 text-kn-text-2" data-testid="od-request-meta">
          <span className="font-bold text-kn-text">Lini masa</span>
          <span>Tipe: {(order.request_types || []).length === 0 ? <i>belum ditentukan (OD lama)</i>
            : order.request_types.map((t) => TYPE_LABEL[t] || t).join(", ")}</span>
          <span>· Detail: {order.detail_level === "full" ? "spesifikasi lengkap" : "hanya referensi"}</span>
          {order.reference_notes ? <span>· {order.reference_notes}</span> : null}
        </div>
        {order.spec && Object.values(order.spec).some(Boolean) && (
          <p className="mb-2 text-fs-12 text-kn-text" data-testid="od-spec-summary">
            Spesifikasi: {[order.spec.fabric_type, order.spec.gramasi && `${order.spec.gramasi} gsm`, order.spec.lebar && `lebar ${order.spec.lebar} cm`, order.spec.sku_hint && `SKU ${order.spec.sku_hint}`, order.spec.color_new_note && `warna baru: ${order.spec.color_new_note}`].filter(Boolean).join(" · ") || "—"}
          </p>
        )}
        {(order.routing_errors || []).length > 0 && <p className="mb-2 text-fs-12 text-kn-danger-text" data-testid="od-routing-errors">{order.routing_errors.join(" · ")}</p>}
        <PhaseTimeline order={order} ch={ch} phases={phases} idx={idx} parallel={parallel}
          action={approved && !routed && canRoute ? (   /* POST /route → order.approve */
            <button className="primary-button btn-sm" disabled={busy} data-testid="od-route-button" onClick={route}><Send size={12} /> Teruskan ke Desainer / R&amp;D</button>
          ) : null} />
      </section>

      <section className="section-card !p-3" data-testid="od-references">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="text-[10.5px] font-bold uppercase tracking-wide text-[#8E8E93]">Referensi pelanggan · {(order.references || []).length}</p>
          {canEdit && (
            <label className="secondary-button cursor-pointer !py-1 text-[11px]" data-testid="od-reference-upload-label">
              <Upload size={12} /> Unggah foto / pattern / swatch
              <input type="file" accept="image/*,.pdf" multiple className="hidden" data-testid="od-reference-upload" onChange={(e) => { const fs = Array.from(e.target.files || []); if (fs.length) upload(fs); e.target.value = ""; }} />
            </label>
          )}
        </div>
        {msg && <p className="mb-2 text-[11px] text-[#0058CC]" data-testid="od-reference-msg">{msg}</p>}
        {(order.references || []).length === 0 ? (
          <p className="flex items-center justify-center gap-1 rounded-lg border border-dashed border-[#D9D9DE] py-5 text-[11px] text-[#9A9BA3]"><ImageIcon size={14} /> belum ada referensi — unggah foto swatch / pattern dari pelanggan</p>
        ) : (
          /* UAT 24 Okt (P17) — referensi dibuka di lightbox halaman ini (dulu URL mentah di tab baru → 403 di PT lain). */
          <AttachmentGallery size={88} showName testId="od-reference"
            items={order.references.map((r) => ({ url: `${API}/special-orders/${order.id}/references/${r.id}`, filename: r.filename,
              content_type: r.content_type, caption: r.caption }))} />
        )}
      </section>
    </div>
  );
}

const fmtTgl = (iso) => (iso ? formatDate(iso) : "");
const sejak = (iso) => {
  if (!iso) return "";
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  return Number.isFinite(d) ? (d < 1 ? "< 1 hari" : `${d} hari`) : "";
};

/** Kapan & oleh siapa tahap `k` terjadi: status_history (status) atau dokumen tahapnya (tahap turunan). */
function phaseEvent(k, order, ch) {
  const hist = [...(order.status_history || [])].reverse().find((h) => h.status === k);
  if (hist) return { at: hist.timestamp || hist.at, by: hist.user_name || hist.user || "" };
  const samples = ch.samples || [];
  if (k === "design" && ch.design_request) return { at: ch.design_request.created_at, by: ch.design_request.assigned_to_name || "" };
  if (k === "sampling" && samples[0]) return { at: samples[0].created_at, by: "" };
  if (k === "sample_ready") { const s = samples.find((x) => x.finished_at || x.delivered_at); return s ? { at: s.finished_at || s.delivered_at, by: "" } : null; }
  if (k === "customer_review") { const d = (order.customer_decisions || []).slice(-1)[0]; return d ? { at: d.at || d.timestamp, by: d.by || d.user_name || "" } : null; }
  if (k === "pricing" && order.pricing?.locked_at) return { at: order.pricing.locked_at, by: order.pricing.locked_by || "" };
  return null;
}

/** Dokumen milik tahap `k` (dulu kartu "Rantai dokumen" terpisah). */
function PhaseDocs({ k, order, ch }) {
  const samples = ch.samples || [];
  if (k === "design") {
    if (!ch.design_request) return (order.request_types || []).includes("printing") ? <Doc muted>Permintaan desain lahir saat OD disetujui</Doc> : null;
    return (
      <Doc testId="od-node-design">
        Permintaan desain <b className="font-mono">{ch.design_request.number}</b> · {ch.design_request.status_label || docStatus(ch.design_request.status)}
        {ch.design && <> · desain <b className="font-mono">{ch.design.code}</b> ({docStatus(ch.design.status)})</>}
      </Doc>
    );
  }
  if (k === "sampling" || k === "sample_ready") {
    if (k === "sample_ready") return null;   // satu daftar sample di tahap sampling
    if (!samples.length) return <Doc muted>{(order.request_types || []).includes("printing") ? "Proofing dibuat MD setelah desain ACC" : "Sample lahir saat OD disetujui"}</Doc>;
    return (
      <div data-testid="od-node-samples">
        {samples.map((x) => (
          <button key={x.id} type="button" className="block text-left text-fs-12 hover:underline" data-testid={`od-sample-${x.id}`}
            onClick={() => openRnd({ view: "rnd-samples", sampleId: x.id, sampleNumber: x.number })}>
            Sample <b className="font-mono">{x.number}</b> · {x.customer_revised ? <span className="font-semibold text-kn-warning-text" data-testid={`od-sample-revised-${x.id}`}>ditolak pelanggan (revisi)</span> : ((SAMPLE_STATUS_META[x.status] || {}).label || x.status)} · {(x.sample_types || []).join("+")}
            {x.decision?.supplier_name ? ` · pemenang ${x.decision.supplier_name}` : ""} <ExternalLink size={10} className="inline text-kn-action" />
          </button>
        ))}
      </div>
    );
  }
  if (k === "pricing") {
    if (!(ch.products || []).length) return <Doc muted>SKU produk lahir saat sampling ACC</Doc>;
    return (
      <div data-testid="od-node-products">
        {ch.products.map((p) => (
          <Doc key={p.id}>SKU <b className="font-mono">{p.sku}</b> {p.name} <ProductColorChip product={p} compact />
            {p.exclusive_customer_name ? <span className="ml-1 status-pill pill-warning" data-testid={`od-product-exclusive-${p.id}`}>Eksklusif: {p.exclusive_customer_name}</span> : null}</Doc>
        ))}
      </div>
    );
  }
  if (k === "confirmed") {
    const prs = (ch.prs || []).length ? ch.prs : (ch.pr ? [ch.pr] : []);
    if (!prs.length && !(ch.po || []).length) return null;
    return (
      <div data-testid="od-node-purchasing">
        {prs.map((p) => <Doc key={p.id} testId={`od-pr-${p.id}`}>PR <b className="font-mono">{p.number}</b> · {docStatus(p.status)}</Doc>)}
        {(ch.po || []).map((p) => <Doc key={p.id} testId={`od-po-${p.id}`}>PO <b className="font-mono">{p.po_number}</b> · {p.supplier_name} · {docStatus(p.status)}</Doc>)}
      </div>
    );
  }
  if (k === "in_production" && ch.so) {
    return <Doc testId="od-node-so">SO <b className="font-mono">{ch.so.order_number || ch.so.number}</b> · {docStatus(ch.so.status)}</Doc>;
  }
  return null;
}

function Doc({ children, muted = false, testId }) {
  return <p className={`text-fs-12 ${muted ? "text-kn-text-2" : "text-kn-text"}`} data-testid={testId}>{children}</p>;
}

function PhaseTimeline({ order, ch, phases, idx, parallel, action }) {
  const done = phases.slice(0, idx);
  const [showDone, setShowDone] = useState(done.length <= 3);
  const cancelled = ["cancelled", "rejected"].includes(order.status);
  const rows = phases.map(([k, label], i) => ({ k, label, i,
    state: cancelled && i >= idx ? "skip" : i < idx ? "done" : i === idx ? "now" : parallel.includes(k) ? "parallel" : "todo" }));
  const visible = rows.filter((r) => showDone || r.state !== "done");
  return (
    <ol className="relative" data-testid="od-phases">
      {!showDone && done.length > 0 && (
        <li className="mb-1 pl-7">
          <button type="button" className="link-button text-fs-12" data-testid="od-phases-show-done" onClick={() => setShowDone(true)}>
            {done.length} tahap selesai — lihat
          </button>
        </li>
      )}
      {visible.map((r, n) => {
        const ev = phaseEvent(r.k, order, ch);
        const last = n === visible.length - 1;
        const dot = r.state === "done" ? <CheckCircle2 size={16} className="text-kn-success-text" />
          : r.state === "now" ? <span className="block h-3.5 w-3.5 rounded-full bg-kn-action ring-4 ring-kn-action-soft" />
            : r.state === "parallel" ? <span className="block h-3 w-3 rounded-full border-2 border-kn-action bg-white" />
              : <Circle size={14} className="text-kn-divider" />;
        return (
          <li key={r.k} className="relative flex gap-3 pb-3" data-testid={`od-phase-${r.k}`} data-state={r.state}>
            {!last && <span className="absolute left-[7px] top-5 bottom-0 w-px bg-kn-divider" aria-hidden="true" />}
            <span className="relative z-10 mt-0.5 flex w-4 shrink-0 justify-center">{dot}</span>
            <div className="min-w-0 flex-1">
              <p className={`text-fs-13 ${r.state === "now" ? "font-bold text-kn-text" : r.state === "done" ? "font-semibold text-kn-text" : "text-kn-text-2"}`}>
                {r.label}
                {r.state === "parallel" && <span className="ml-1 text-fs-12 font-normal text-kn-action">· berjalan bersamaan</span>}
                {r.state === "skip" && <span className="ml-1 text-fs-12 font-normal">· tidak dilanjutkan</span>}
              </p>
              {r.state === "done" && ev?.at && (
                <p className="text-fs-12 text-kn-text-2">{fmtTgl(ev.at)}{ev.by ? ` · ${ev.by}` : ""}</p>
              )}
              {r.state === "now" && (
                <p className="text-fs-12 text-kn-warning-text" data-testid="od-phase-now-wait">
                  {ev?.at ? `Berjalan sejak ${fmtTgl(ev.at)} (${sejak(ev.at)})` : "Tahap berjalan"}{ev?.by ? ` · ${ev.by}` : ""}
                </p>
              )}
              {(r.state === "done" || r.state === "now" || r.state === "parallel") && <PhaseDocs k={r.k} order={order} ch={ch} />}
              {r.state === "now" && action && <div className="mt-1.5">{action}</div>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
