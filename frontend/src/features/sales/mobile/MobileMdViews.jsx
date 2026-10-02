/**
 * Layar HP untuk MD / Merchandiser (cermin menu web peran `md`, ROLE_NAV):
 *  - MobileMdDesk            : Meja MD (/md/desk) — antrean desain, sample/labdip, PR bahan, SPK tanpa acuan.
 *  - MobileDesignRequests    : permintaan desain — ajukan, tugaskan desainer, ACC / minta revisi, batalkan.
 *  - MobileRndSamples        : sample & labdip — putaran per supplier, nilai putaran (ACC/revisi/tolak), putuskan pemenang.
 *  - MobileMdProducts        : master produk — cari, detail + stok per gudang, ubah harga/nama.
 *  - MobilePurchaseRequisitions : PR bahan — daftar, buat (langsung ajukan), ajukan draf.
 *  - MobilePoWatch           : pantau PO (hanya-lihat).
 * Endpoint & wewenang sama dengan layar desktop (RoleDesk, DesignRequests, RnD, Katalog, PR).
 */
import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ChevronDown, ChevronRight, ClipboardList, Plus, RefreshCw, Search, Trash2, Palette, FlaskConical, FileStack } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import KNSelect from "../../../components/KNSelect";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import { askReason } from "../../../services/confirmService";
import { ageTone, badgeClass, badgeLabel, mdDesk, rowLink } from "../../sales_admin/workDeskApi";
import { errText } from "./MobileSalesFlows";

const list = (d) => (Array.isArray(d) ? d : d?.items || []);
const fmtDate = (s) => (s ? new Date(s).toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" }) : "-");

function Chips({ items, value, onChange, prefix }) {
  return (
    <div className="no-scrollbar flex gap-2 overflow-x-auto py-1">
      {items.map(([id, label]) => (
        <button key={id || "all"} onClick={() => onChange(id)} data-testid={`${prefix}-${id || "all"}`}
          className={`h-9 shrink-0 whitespace-nowrap rounded-full border px-3 text-[12px] font-semibold ${value === id ? "border-[#0058CC] bg-[#0058CC] text-white" : "border-[#E5E5EA] bg-white text-[#3A3A3C]"}`}>{label}</button>
      ))}
    </div>
  );
}
const Pill = ({ label, tone = "mute", testId }) => <span className={`shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-bold ${badgeClass(tone)}`} data-testid={testId}>{label}</span>;
const Back = ({ label, onClick, testId }) => <button className="m-subpage-back" onClick={onClick} data-testid={testId}><ArrowLeft size={17} /> {label}</button>;
const Notice = ({ msg, testId }) => (msg ? <div className={`notice-bar ${msg.ok ? "success" : "danger"} text-xs`} data-testid={testId}>{msg.text}</div> : null);

/* ───────────── Meja MD ───────────── */

const DESK_ICON = { desain: Palette, sample: FlaskConical, pr: FileStack };

export function MobileMdDesk({ selectedEntity, onOpenRow }) {
  const [desk, setDesk] = useState(null);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState({});
  const [loading, setLoading] = useState(true);
  const load = () => {
    setLoading(true);
    mdDesk(selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {})
      .then((d) => { setDesk(d); setErr(""); }).catch((e) => setErr(errText(e, "Gagal memuat Meja MD."))).finally(() => setLoading(false));
  };
  useEffect(load, [selectedEntity]); // eslint-disable-line react-hooks/exhaustive-deps
  const queues = desk?.queues || [];
  const total = queues.reduce((s, q) => s + (q.count || 0), 0);
  const oldest = Math.max(0, ...queues.map((q) => q.oldest_age_days || 0));
  return (
    <div className="space-y-3" data-testid="m-md-desk">
      <div className="flex items-center justify-between px-0.5">
        <div className="flex items-center gap-2"><ClipboardList size={16} className="text-[#0058CC]" /><h2 className="m-section-title">Meja MD</h2></div>
        <button onClick={load} aria-label="Muat ulang" data-testid="m-md-desk-refresh"><RefreshCw size={15} className={`text-[#6B6B73] ${loading ? "animate-spin" : ""}`} /></button>
      </div>
      {err && <div className="notice-bar danger text-xs" data-testid="m-md-desk-error">{err}</div>}
      <div className="grid grid-cols-2 gap-2">
        <div className="m-card p-3" data-testid="m-md-metric-open"><p className="text-[10px] font-bold uppercase text-[#8E8E93]">Perlu ditindak</p><p className="text-[20px] font-bold tabular-nums">{total}</p></div>
        <div className="m-card p-3" data-testid="m-md-metric-oldest"><p className="text-[10px] font-bold uppercase text-[#8E8E93]">Umur tertua</p><p className="text-[20px] font-bold">{oldest ? `${oldest} hari` : "hari ini"}</p></div>
      </div>
      <p className="px-0.5 text-[11px] m-muted">Desain → sample/labdip → spesifikasi & produk → PR bahan. Baris dibuka langsung di layar HP-nya.</p>
      {loading && !desk && <div className="h-16 animate-pulse rounded-xl bg-[#ECEDF0]" />}
      {queues.map((q) => {
        const Icon = DESK_ICON[q.id] || ClipboardList;
        const isOpen = open[q.id] ?? (q.count || 0) > 0;
        return (
          <div key={q.id} className="m-card overflow-hidden" data-testid={`m-md-queue-${q.id}`}>
            <button className="m-press flex w-full items-center gap-2.5 p-3 text-left" onClick={() => setOpen({ ...open, [q.id]: !isOpen })} data-testid={`m-md-queue-toggle-${q.id}`}>
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-[#EAF2FF]"><Icon size={16} className="text-[#0058CC]" /></span>
              <span className="min-w-0 flex-1"><span className="block text-[13px] font-bold">{q.label}</span>{q.value_kind === "money" && <span className="text-[10.5px] m-muted tabular-nums">{formatCurrency(q.total_value || 0)}</span>}</span>
              <span className="rounded-full bg-[#EAF2FF] px-2 py-0.5 text-[11px] font-bold text-[#0058CC]" data-testid={`m-md-count-${q.id}`}>{q.count || 0}</span>
              <ChevronDown size={16} className={`text-[#8E8E93] transition-transform ${isOpen ? "rotate-180" : ""}`} />
            </button>
            {isOpen && (
              <div className="border-t border-[#F2F3F5] px-3">
                {(q.rows || []).length === 0 && <p className="py-4 text-center text-[11.5px] m-muted">Antrean bersih.</p>}
                {(q.rows || []).map((r) => {
                  const age = ageTone(r.age_days);
                  return (
                    <button key={`${r.ref_type}-${r.ref_id}`} className="m-list-row m-press w-full text-left" onClick={() => onOpenRow(r, q)} data-testid={`m-md-row-${q.id}-${r.ref_id}`}>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-1.5"><span className="text-[12px] font-bold text-[#0058CC]">{r.number}</span>{r.badge && <Pill label={badgeLabel(r.badge)} tone={r.badge} />}<span className={`rounded-full border px-1.5 py-0.5 text-[9.5px] font-bold ${age.cls}`}>{age.label}</span></div>
                        <p className="truncate text-[12.5px] font-semibold">{r.title}</p>
                        {r.subtitle && <p className="truncate text-[10.5px] m-muted">{r.subtitle}</p>}
                      </div>
                      <ChevronRight size={16} className="text-[#C7C7CC]" />
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
export const mdRowTarget = (row, queue) => {
  if (row.ref_type === "design_request") return { tab: "design", id: row.ref_id };
  if (row.ref_type === "md_sample" || row.ref_type === "rnd_sample") return { tab: "sample", id: row.ref_id };
  if (row.ref_type === "purchase_requisition") return { tab: "more", sub: "pr", id: row.ref_id };
  const l = rowLink(row, queue?.id, "md");
  return { full: l };
};

/* ───────────── Permintaan desain ───────────── */

const DSR_TONE = { submitted: "menunggu", assigned: "reserved", in_progress: "in_progress", delivered: "pending", revision: "partial", approved: "approved", cancelled: "cancelled", draft: "draft" };

function DesignCreate({ meta, onBack, onDone }) {
  const [customers, setCustomers] = useState([]);
  const [f, setF] = useState({ target_type: "motif", category_code: "", brief: "", due_date: "", customer_id: "", assigned_to: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  useEffect(() => { axios.get(`${API}/customers`).then((r) => setCustomers(list(r.data))).catch(() => {}); }, []);
  const cats = (meta?.categories?.[f.target_type === "motif" ? "pattern" : f.target_type] || meta?.categories?.pattern || []);
  const submit = async () => {
    setBusy(true); setErr("");
    try { const r = await axios.post(`${API}/design-requests`, { ...f, source: f.customer_id ? "customer" : "internal", submit_now: true }); onDone(`${r.data?.number || "Permintaan desain"} diajukan.`); }
    catch (e) { setErr(errText(e, "Gagal mengajukan permintaan desain.")); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-2" data-testid="m-dsr-create">
      <Back label="Permintaan desain" onClick={onBack} testId="m-dsr-create-back" />
      <div className="m-card space-y-2 p-3">
        <Chips items={(meta?.target_types || []).map((t) => [t.id, t.label])} value={f.target_type} onChange={(v) => setF({ ...f, target_type: v, category_code: "" })} prefix="m-dsr-type" />
        <KNSelect value={f.category_code} onValueChange={(v) => setF({ ...f, category_code: v })} options={cats.map((c) => ({ value: c.code, label: c.name }))} placeholder="Kategori" data-testid="m-dsr-category" />
        <KNSelect value={f.customer_id} onValueChange={(v) => setF({ ...f, customer_id: v })} options={[{ value: "", label: "— Internal (tanpa pelanggan) —" }, ...customers.map((c) => ({ value: c.id, label: c.name }))]} placeholder="Pelanggan (opsional)" data-testid="m-dsr-customer" />
        <textarea className="field" rows={4} placeholder="Brief: motif, warna, referensi, pemakaian… *" value={f.brief} onChange={(e) => setF({ ...f, brief: e.target.value })} data-testid="m-dsr-brief" />
        <KNSelect value={f.assigned_to} onValueChange={(v) => setF({ ...f, assigned_to: v })} options={[{ value: "", label: "— Tugaskan nanti —" }, ...(meta?.designers || []).map((d) => ({ value: d.id, label: d.name }))]} placeholder="Desainer (opsional)" data-testid="m-dsr-designer" />
        <label className="block text-[11.5px] font-semibold text-[#4A4B53]">Tenggat<input type="date" className="field mt-1" value={f.due_date} onChange={(e) => setF({ ...f, due_date: e.target.value })} data-testid="m-dsr-due" /></label>
        {err && <div className="notice-bar danger text-xs" data-testid="m-dsr-create-error">{err}</div>}
        <button className="primary-button w-full py-3" disabled={busy || f.brief.trim().length < 5} onClick={submit} data-testid="m-dsr-submit">{busy ? "Mengirim…" : "Ajukan permintaan desain"}</button>
      </div>
    </div>
  );
}

function DesignDetail({ id, meta, onBack }) {
  const [d, setD] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [assign, setAssign] = useState({ assigned_to: "", due_date: "" });
  const load = () => axios.get(`${API}/design-requests/${id}`).then((r) => setD(r.data)).catch((e) => setMsg({ ok: false, text: errText(e, "Gagal memuat.") }));
  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  const act = async (path, body, okText) => {
    setBusy(true); setMsg(null);
    try { await axios.post(`${API}/design-requests/${id}/${path}`, body); await load(); setMsg({ ok: true, text: okText }); }
    catch (e) { setMsg({ ok: false, text: errText(e, "Aksi gagal.") }); } finally { setBusy(false); }
  };
  const withReason = async (path, title, okText) => { const reason = await askReason({ title, danger: path !== "approve" }); if (reason) act(path, { reason, note: reason }, okText); };
  if (!d) return <div className="space-y-2"><Back label="Permintaan desain" onClick={onBack} testId="m-dsr-back" />{msg ? <Notice msg={msg} /> : <p className="text-xs m-muted">Memuat…</p>}</div>;
  const open = !["approved", "cancelled"].includes(d.status);
  return (
    <div className="space-y-2" data-testid="m-dsr-detail">
      <Back label="Permintaan desain" onClick={onBack} testId="m-dsr-back" />
      <div className="m-card p-4">
        <div className="flex items-start justify-between gap-2"><p className="text-[15px] font-bold">{d.number}</p><Pill label={d.status_label || d.status} tone={DSR_TONE[d.status]} testId="m-dsr-status" /></div>
        <p className="text-[12px] text-[#3C3C43]">{d.target_label} · {d.category_name || "-"}{d.customer_name ? ` · ${d.customer_name}` : ""}</p>
        <p className="mt-2 whitespace-pre-wrap text-[12.5px]">{d.brief || "-"}</p>
        <p className="mt-2 text-[11px] m-muted">Diminta {d.requested_by} · {fmtDate(d.requested_at)}{d.assigned_name ? ` · desainer ${d.assigned_name}` : ""}{d.due_date ? ` · tenggat ${fmtDate(d.due_date)}` : ""}{d.is_overdue ? " · TERLAMBAT" : ""}</p>
        {d.so_number && <p className="text-[11px] m-muted">Untuk pesanan {d.so_number}</p>}
        {(d.color_targets || []).length > 0 && <p className="mt-1 text-[11px]">Target warna: {d.color_targets.map((c) => c.name || c.code || c.hex).join(", ")}</p>}
        {(d.designs || []).length > 0 && <p className="mt-1 text-[11px] text-[#1B7F4B]">Desain terkirim: {d.designs.map((x) => x.code || x.title).join(", ")}</p>}
        {d.reject_reason && <p className="mt-1 text-[11px] text-[#C0392B]">Catatan revisi: {d.reject_reason}</p>}
      </div>
      <Notice msg={msg} testId="m-dsr-msg" />
      {["submitted", "assigned", "revision"].includes(d.status) && (
        <div className="m-card space-y-2 p-3" data-testid="m-dsr-assign">
          <p className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">{d.assigned_to ? "Tugaskan ulang" : "Tugaskan desainer"}</p>
          <KNSelect value={assign.assigned_to} onValueChange={(v) => setAssign({ ...assign, assigned_to: v })} options={(meta?.designers || []).map((x) => ({ value: x.id, label: x.name }))} placeholder="Pilih desainer" data-testid="m-dsr-assign-designer" />
          <input type="date" className="field" value={assign.due_date} onChange={(e) => setAssign({ ...assign, due_date: e.target.value })} data-testid="m-dsr-assign-due" />
          <button className="primary-button w-full py-2.5" disabled={busy || !assign.assigned_to} onClick={() => act("assign", assign, "Desainer ditugaskan.")} data-testid="m-dsr-assign-submit">Tugaskan</button>
        </div>
      )}
      {d.status === "delivered" && (
        <div className="grid grid-cols-2 gap-2" data-testid="m-dsr-decide">
          <button className="primary-button py-3" disabled={busy} onClick={() => act("approve", { note: "" }, "Desain di-ACC.")} data-testid="m-dsr-approve">ACC desain</button>
          <button className="secondary-button py-3" disabled={busy} onClick={() => withReason("reject", "Minta revisi — apa yang perlu diubah?", "Dikembalikan untuk revisi.")} data-testid="m-dsr-reject">Minta revisi</button>
        </div>
      )}
      {d.status === "draft" && <button className="primary-button w-full py-3" disabled={busy} onClick={() => act("submit", {}, "Diajukan.")} data-testid="m-dsr-submit-draft">Ajukan</button>}
      {open && <button className="w-full py-2 text-[12px] font-semibold text-[#C0392B]" disabled={busy} onClick={() => withReason("cancel", `Batalkan ${d.number}?`, "Permintaan dibatalkan.")} data-testid="m-dsr-cancel">Batalkan permintaan</button>}
      {(d.history || []).length > 0 && (
        <div className="m-card p-3" data-testid="m-dsr-history">
          <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Riwayat</p>
          {d.history.slice().reverse().slice(0, 12).map((h, i) => <p key={i} className="text-[11px]"><b>{h.label || badgeLabel(h.status || h.action)}</b> · {fmtDate(h.at || h.timestamp)} · {h.by || h.user}{h.note ? ` — ${h.note}` : ""}</p>)}
        </div>
      )}
    </div>
  );
}

export function MobileDesignRequests({ focusId }) {
  const [meta, setMeta] = useState(null);
  const [rows, setRows] = useState(null);
  const [status, setStatus] = useState("");
  const [sel, setSel] = useState(focusId || null);
  const [create, setCreate] = useState(false);
  const [msg, setMsg] = useState(null);
  const load = () => axios.get(`${API}/design-requests`).then((r) => setRows(list(r.data))).catch((e) => { setRows([]); setMsg({ ok: false, text: errText(e, "Gagal memuat permintaan desain.") }); });
  useEffect(() => { axios.get(`${API}/design-requests/meta`).then((r) => setMeta(r.data)).catch(() => {}); load(); }, []);
  useEffect(() => { if (focusId) setSel(focusId); }, [focusId]);
  if (create) return <DesignCreate meta={meta} onBack={() => setCreate(false)} onDone={(t) => { setCreate(false); setMsg({ ok: true, text: t }); load(); }} />;
  if (sel) return <DesignDetail id={sel} meta={meta} onBack={() => { setSel(null); load(); }} />;
  const shown = (rows || []).filter((r) => !status || r.status === status);
  return (
    <div className="space-y-2" data-testid="m-design-requests">
      <button className="primary-button flex w-full items-center justify-center gap-2 py-3" onClick={() => setCreate(true)} data-testid="m-dsr-new"><Plus size={16} /> Permintaan desain baru</button>
      <Chips items={[["", "Semua"], ...(meta?.statuses || []).map((s) => [s.id, s.label])]} value={status} onChange={setStatus} prefix="m-dsr-filter" />
      <Notice msg={msg} testId="m-dsr-list-msg" />
      {rows === null && <p className="text-xs m-muted">Memuat…</p>}
      {rows && shown.length === 0 && <p className="py-8 text-center text-xs m-muted" data-testid="m-dsr-empty">Tidak ada permintaan desain.</p>}
      {shown.map((r) => (
        <button key={r.id} className="m-card m-press w-full p-3 text-left" onClick={() => setSel(r.id)} data-testid={`m-dsr-${r.id}`}>
          <div className="flex items-center justify-between gap-2"><span className="text-[12.5px] font-bold text-[#0058CC]">{r.number}</span><Pill label={r.status_label || r.status} tone={DSR_TONE[r.status]} /></div>
          <p className="truncate text-[12px]">{r.brief || r.target_label}</p>
          <p className="text-[10.5px] m-muted">{r.category_name || r.target_label}{r.customer_name ? ` · ${r.customer_name}` : ""}{r.assigned_name ? ` · ${r.assigned_name}` : ""}{r.due_date ? ` · tenggat ${fmtDate(r.due_date)}` : ""}{r.is_overdue ? " · terlambat" : ""}</p>
        </button>
      ))}
    </div>
  );
}

/* ───────────── Sample & labdip ───────────── */

const SMP_STATUS = { draft: ["Draf", "draft"], sent: ["Dikirim ke supplier", "reserved"], in_progress: ["Berjalan", "in_progress"], assessed: ["Siap diputus", "pending"], decided: ["Diputus", "approved"], cancelled: ["Batal", "cancelled"] };
const RESULT = { acc: ["ACC", "approved"], revisi: ["Revisi", "partial"], tolak: ["Tolak", "rejected"] };

function RoundAssess({ sample, round, onDone }) {
  const [f, setF] = useState({ result: "acc", score: "", note: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const submit = async () => {
    setBusy(true); setErr("");
    try { await axios.post(`${API}/rnd/samples/${sample.id}/rounds/${round.id}/assess`, { ...f, score: f.score === "" ? null : Number(f.score) }); onDone("Putaran dinilai."); }
    catch (e) { setErr(errText(e, "Gagal menilai putaran.")); } finally { setBusy(false); }
  };
  return (
    <div className="mt-2 space-y-2 rounded-xl border border-[#CBDFFF] bg-[#F7FAFF] p-2.5" data-testid={`m-smp-assess-${round.id}`}>
      <div className="grid grid-cols-3 gap-1.5">
        {Object.entries(RESULT).map(([k, [l]]) => (
          <button key={k} onClick={() => setF({ ...f, result: k })} data-testid={`m-smp-assess-${round.id}-${k}`}
            className={`h-9 rounded-lg border text-[12px] font-semibold ${f.result === k ? "border-[#0058CC] bg-[#0058CC] text-white" : "border-[#E5E5EA] bg-white"}`}>{l}</button>
        ))}
      </div>
      <input type="number" inputMode="decimal" className="field" placeholder="Skor 0–100 (opsional)" value={f.score} onChange={(e) => setF({ ...f, score: e.target.value })} data-testid={`m-smp-assess-${round.id}-score`} />
      <textarea className="field" rows={2} placeholder="Catatan (warna, handfeel, tahan cuci…)" value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} data-testid={`m-smp-assess-${round.id}-note`} />
      {err && <div className="notice-bar danger text-xs">{err}</div>}
      <button className="primary-button w-full py-2.5" disabled={busy || (f.result !== "acc" && !f.note.trim())} onClick={submit} data-testid={`m-smp-assess-${round.id}-submit`}>Simpan penilaian</button>
    </div>
  );
}

function SampleDecide({ sample, reasons, onDone }) {
  const cands = (sample.participants || []).filter((p) => p.status === "acc" || p.last_result === "acc");
  const [f, setF] = useState({ supplier_id: cands[0]?.supplier_id || "", reason_code: "", note: "", price: "", moq: "", lead_time_days: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await axios.post(`${API}/rnd/samples/${sample.id}/decide`, { ...f, price: Number(f.price || 0), moq: Number(f.moq || 0), lead_time_days: Number(f.lead_time_days || 0), supplier_uom: sample.unit || "" });
      onDone("Pemenang sample diputus.");
    } catch (e) { setErr(errText(e, "Gagal memutus sample.")); } finally { setBusy(false); }
  };
  return (
    <div className="m-card space-y-2 p-3" data-testid="m-smp-decide">
      <p className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Putuskan pemenang</p>
      <p className="text-[10.5px] m-muted">Mengikuti matriks persetujuan divisi — bila tahap ini wewenang manajer, server menolak dan dokumen tetap menunggu di Meja manajer.</p>
      {cands.length === 0 && <p className="text-[11.5px] text-[#8A5300]" data-testid="m-smp-decide-none">Belum ada supplier dengan hasil ACC — nilai putaran atau minta putaran baru dulu.</p>}
      {cands.map((p) => (
        <button key={p.supplier_id} onClick={() => setF({ ...f, supplier_id: p.supplier_id })} data-testid={`m-smp-decide-supplier-${p.supplier_id}`}
          className={`w-full rounded-lg border p-2 text-left text-[12px] ${f.supplier_id === p.supplier_id ? "border-[#0058CC] bg-[#F7FAFF]" : "border-[#E5E5EA]"}`}>
          <b>{p.supplier_name}</b> <span className="m-muted">· skor terbaik {p.best_score ?? "-"} · {p.rounds} putaran</span>
        </button>
      ))}
      {cands.length > 0 && <>
      <KNSelect value={f.reason_code} onValueChange={(v) => setF({ ...f, reason_code: v })} options={(reasons || []).map((r) => ({ value: r.value, label: r.label }))} placeholder="Alasan memilih *" data-testid="m-smp-decide-reason" />
      <div className="grid grid-cols-3 gap-2">
        <input type="number" inputMode="decimal" className="field" placeholder="Harga" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} data-testid="m-smp-decide-price" />
        <input type="number" inputMode="decimal" className="field" placeholder="MOQ" value={f.moq} onChange={(e) => setF({ ...f, moq: e.target.value })} data-testid="m-smp-decide-moq" />
        <input type="number" inputMode="numeric" className="field" placeholder="Lead (hr)" value={f.lead_time_days} onChange={(e) => setF({ ...f, lead_time_days: e.target.value })} data-testid="m-smp-decide-lead" />
      </div>
      <textarea className="field" rows={2} placeholder="Catatan" value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} data-testid="m-smp-decide-note" />
      {err && <div className="notice-bar danger text-xs" data-testid="m-smp-decide-error">{err}</div>}
      <button className="primary-button w-full py-3" disabled={busy || !f.supplier_id || !f.reason_code} onClick={submit} data-testid="m-smp-decide-submit">{busy ? "Menyimpan…" : "Putuskan pemenang"}</button>
      </>}
    </div>
  );
}

function SampleDetail({ id, reasons, onBack }) {
  const [s, setS] = useState(null);
  const [msg, setMsg] = useState(null);
  const [assess, setAssess] = useState(null);
  const load = () => axios.get(`${API}/rnd/samples/${id}`).then((r) => setS(r.data)).catch((e) => setMsg({ ok: false, text: errText(e, "Gagal memuat sample.") }));
  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  const done = (t) => { setAssess(null); setMsg({ ok: true, text: t }); load(); };
  if (!s) return <div className="space-y-2"><Back label="Sample & labdip" onClick={onBack} testId="m-smp-back" />{msg ? <Notice msg={msg} /> : <p className="text-xs m-muted">Memuat…</p>}</div>;
  const [sl, st] = SMP_STATUS[s.status] || [s.status, "mute"];
  return (
    <div className="space-y-2" data-testid="m-smp-detail">
      <Back label="Sample & labdip" onClick={onBack} testId="m-smp-back" />
      <div className="m-card p-4">
        <div className="flex items-start justify-between gap-2"><p className="text-[15px] font-bold">{s.number}</p><Pill label={sl} tone={st} testId="m-smp-status" /></div>
        <p className="text-[12.5px] font-semibold">{s.title}</p>
        {s.spec_summary && <p className="text-[11.5px] m-muted">{typeof s.spec_summary === "string" ? s.spec_summary : JSON.stringify(s.spec_summary)}</p>}
        <p className="mt-1 text-[11px] m-muted">{s.qty_requested ? `${formatQty(s.qty_requested)} ${s.unit || ""} · ` : ""}target {fmtDate(s.target_date)}{s.design_code ? ` · desain ${s.design_code}` : ""}{s.cost_total ? ` · biaya ${formatCurrency(s.cost_total)}` : ""}</p>
        {s.decision?.supplier_name && <p className="mt-1 text-[12px] text-[#1B7F4B]" data-testid="m-smp-winner">Pemenang: <b>{s.decision.supplier_name}</b>{s.decision.price ? ` · ${formatCurrency(s.decision.price)}` : ""}</p>}
      </div>
      <Notice msg={msg} testId="m-smp-msg" />
      <div className="m-card p-3" data-testid="m-smp-participants">
        <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Supplier peserta</p>
        {(s.participants || []).map((p) => (
          <div key={p.supplier_id} className="flex items-center justify-between py-1 text-[12px]"><span className="min-w-0 flex-1 truncate">{p.supplier_name}</span><span className="m-muted">{p.rounds} putaran · skor {p.best_score ?? "-"}</span>{p.last_result && <span className="ml-2"><Pill label={(RESULT[p.last_result] || [p.last_result])[0]} tone={(RESULT[p.last_result] || [])[1]} /></span>}</div>
        ))}
      </div>
      {(s.rounds || []).map((r) => {
        const canAssess = !["assessed", "cancelled"].includes(r.status) && !r.result && s.status !== "decided";
        return (
          <div key={r.id} className="m-card p-3" data-testid={`m-smp-round-${r.id}`}>
            <div className="flex items-center justify-between gap-2 text-[12px]"><b>{r.supplier_name} · {r.type_code} #{r.round_no}</b>{r.result ? <Pill label={(RESULT[r.result] || [r.result])[0]} tone={(RESULT[r.result] || [])[1]} /> : <Pill label={badgeLabel(r.status)} tone={r.status} />}</div>
            <p className="text-[10.5px] m-muted">Kirim {fmtDate(r.sent_at)}{r.received_at ? ` · diterima ${fmtDate(r.received_at)}` : ""}{r.due_date ? ` · tenggat ${fmtDate(r.due_date)}` : ""}{r.score != null ? ` · skor ${r.score}` : ""}{r.cost ? ` · ${formatCurrency(r.cost)}` : ""}</p>
            {r.measurements && Object.keys(r.measurements).length > 0 && <p className="text-[10.5px]">{Object.entries(r.measurements).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(" · ")}</p>}
            {r.note && <p className="text-[11px]">{r.note}</p>}
            {(r.attachments || []).length > 0 && <p className="text-[10.5px] m-muted">{r.attachments.length} lampiran foto</p>}
            {canAssess && (assess === r.id ? <RoundAssess sample={s} round={r} onDone={done} /> :
              <button className="secondary-button mt-2 w-full py-2 text-[12px]" onClick={() => setAssess(r.id)} data-testid={`m-smp-assess-open-${r.id}`}>Nilai putaran ini</button>)}
          </div>
        );
      })}
      {["assessed", "in_progress", "sent"].includes(s.status) && <SampleDecide sample={s} reasons={reasons} onDone={(t) => { setMsg({ ok: true, text: t }); load(); }} />}
    </div>
  );
}

export function MobileRndSamples({ focusId }) {
  const [rows, setRows] = useState(null);
  const [meta, setMeta] = useState(null);
  const [status, setStatus] = useState("");
  const [sel, setSel] = useState(focusId || null);
  const [q, setQ] = useState("");
  const load = () => axios.get(`${API}/rnd/samples`).then((r) => setRows(list(r.data))).catch(() => setRows([]));
  useEffect(() => { axios.get(`${API}/rnd/meta`).then((r) => setMeta(r.data)).catch(() => {}); load(); }, []);
  useEffect(() => { if (focusId) setSel(focusId); }, [focusId]);
  if (sel) return <SampleDetail id={sel} reasons={meta?.reasons} onBack={() => { setSel(null); load(); }} />;
  const shown = (rows || []).filter((r) => (!status || r.status === status) && (!q || `${r.number} ${r.title}`.toLowerCase().includes(q.toLowerCase())));
  return (
    <div className="space-y-2" data-testid="m-rnd-samples">
      <div className="m-card flex items-center gap-2 px-3 py-2"><Search size={15} className="m-muted" /><input className="w-full bg-transparent text-sm outline-none" placeholder="Cari nomor / judul sample" value={q} onChange={(e) => setQ(e.target.value)} data-testid="m-smp-search" /></div>
      <Chips items={[["", "Semua"], ["assessed", "Siap diputus"], ["sent", "Dikirim"], ["in_progress", "Berjalan"], ["decided", "Diputus"], ["cancelled", "Batal"]]} value={status} onChange={setStatus} prefix="m-smp-filter" />
      {rows === null && <p className="text-xs m-muted">Memuat…</p>}
      {rows && shown.length === 0 && <p className="py-8 text-center text-xs m-muted" data-testid="m-smp-empty">Tidak ada sample.</p>}
      {shown.map((r) => {
        const [sl, st] = SMP_STATUS[r.status] || [r.status, "mute"];
        return (
          <button key={r.id} className="m-card m-press w-full p-3 text-left" onClick={() => setSel(r.id)} data-testid={`m-smp-${r.id}`}>
            <div className="flex items-center justify-between gap-2"><span className="text-[12.5px] font-bold text-[#0058CC]">{r.number}</span><Pill label={sl} tone={st} /></div>
            <p className="truncate text-[12px]">{r.title}</p>
            <p className="text-[10.5px] m-muted">{(r.participants || []).length} supplier · {(r.rounds || []).length} putaran · target {fmtDate(r.target_date)}{r.decision?.supplier_name ? ` · menang ${r.decision.supplier_name}` : ""}</p>
          </button>
        );
      })}
    </div>
  );
}

/* ───────────── Produk ───────────── */

function ProductDetail({ product, canEdit, onBack, onSaved }) {
  const [sb, setSb] = useState(null);
  const [edit, setEdit] = useState(false);
  const [f, setF] = useState({ name: product.name || "", price: product.price ?? "" });
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { axios.get(`${API}/products/${product.id}/stock-breakdown`).then((r) => setSb(r.data)).catch(() => setSb({})); }, [product.id]);
  const save = async () => {
    setBusy(true); setMsg(null);
    try { const r = await axios.patch(`${API}/products/${product.id}`, { data: { name: f.name, price: Number(f.price) } }); setMsg({ ok: true, text: "Produk diperbarui." }); setEdit(false); onSaved?.(r.data); }
    catch (e) { setMsg({ ok: false, text: errText(e, "Gagal menyimpan produk.") }); } finally { setBusy(false); }
  };
  const bal = sb?.balances || sb?.warehouses || [];
  return (
    <div className="space-y-2" data-testid="m-md-product-detail">
      <Back label="Produk" onClick={onBack} testId="m-md-product-back" />
      <div className="m-card p-4">
        {product.image && <img src={product.image} alt={product.name} className="mb-2 h-40 w-full rounded-xl object-cover" />}
        <p className="text-[15px] font-bold" data-testid="m-md-product-name">{product.name}</p>
        <p className="text-[11.5px] m-muted">{product.sku} · {product.category || "-"} · {product.fabric_type || ""}</p>
        <p className="mt-1 text-[16px] font-bold tabular-nums" data-testid="m-md-product-price">{formatCurrency(product.price)} <span className="text-[11px] font-normal m-muted">/ {product.base_unit}</span></p>
        <p className="text-[11.5px]">Tersedia {formatQty(product.available_qty)} {product.base_unit}</p>
        {canEdit && !edit && <button className="secondary-button mt-2 w-full py-2.5 text-[12px]" onClick={() => setEdit(true)} data-testid="m-md-product-edit">Ubah nama / harga dasar</button>}
        {edit && (
          <div className="mt-2 space-y-2" data-testid="m-md-product-form">
            <input className="field" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="m-md-product-form-name" />
            <input type="number" inputMode="decimal" className="field" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} data-testid="m-md-product-form-price" />
            <p className="text-[10.5px] m-muted">Perubahan harga dasar tercatat di audit; harga per pelanggan/PT tetap lewat daftar harga.</p>
            <div className="grid grid-cols-2 gap-2"><button className="secondary-button py-2.5" onClick={() => setEdit(false)} data-testid="m-md-product-form-cancel">Batal</button><button className="primary-button py-2.5" disabled={busy || !f.name.trim() || !(Number(f.price) >= 0)} onClick={save} data-testid="m-md-product-form-save">Simpan</button></div>
          </div>
        )}
      </div>
      <Notice msg={msg} testId="m-md-product-msg" />
      <div className="m-card p-3" data-testid="m-md-product-stock">
        <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Stok per gudang</p>
        {sb === null && <p className="text-xs m-muted">Memuat…</p>}
        {sb && bal.length === 0 && <p className="text-xs m-muted">Belum ada stok.</p>}
        {bal.map((b, i) => <div key={i} className="flex justify-between py-0.5 text-[12px]"><span>{b.warehouse_name || b.warehouse_id}</span><span className="tabular-nums">{formatQty(b.available_qty ?? b.quantity)} {product.base_unit}</span></div>)}
      </div>
    </div>
  );
}

export function MobileMdProducts({ canEdit }) {
  const [rows, setRows] = useState(null);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [sel, setSel] = useState(null);
  useEffect(() => { axios.get(`${API}/products`).then((r) => setRows(list(r.data))).catch(() => setRows([])); }, []);
  const cats = useMemo(() => [...new Set((rows || []).map((p) => p.category).filter(Boolean))], [rows]);
  if (sel) return <ProductDetail product={sel} canEdit={canEdit} onBack={() => setSel(null)} onSaved={(p) => { setSel((c) => ({ ...c, ...p })); setRows((r) => r.map((x) => (x.id === p.id ? { ...x, ...p } : x))); }} />;
  const shown = (rows || []).filter((p) => (!cat || p.category === cat) && (!q || `${p.name} ${p.sku}`.toLowerCase().includes(q.toLowerCase())));
  return (
    <div className="space-y-2" data-testid="m-md-products">
      <div className="m-card flex items-center gap-2 px-3 py-2"><Search size={15} className="m-muted" /><input className="w-full bg-transparent text-sm outline-none" placeholder="Cari produk / SKU" value={q} onChange={(e) => setQ(e.target.value)} data-testid="m-md-products-search" /></div>
      <Chips items={[["", "Semua"], ...cats.map((c) => [c, c])]} value={cat} onChange={setCat} prefix="m-md-products-cat" />
      {rows === null && <p className="text-xs m-muted">Memuat…</p>}
      {shown.map((p) => (
        <button key={p.id} className="m-card m-press flex w-full items-center gap-3 p-2.5 text-left" onClick={() => setSel(p)} data-testid={`m-md-product-${p.id}`}>
          {p.image ? <img src={p.image} alt="" className="h-12 w-12 shrink-0 rounded-lg object-cover" /> : <span className="h-12 w-12 shrink-0 rounded-lg bg-[#F2F3F5]" />}
          <div className="min-w-0 flex-1"><p className="truncate text-[13px] font-bold">{p.name}</p><p className="text-[10.5px] m-muted">{p.sku} · {p.category}</p></div>
          <div className="text-right"><p className="text-[12.5px] font-bold tabular-nums">{formatCurrency(p.price)}</p><p className="text-[10px] m-muted">{formatQty(p.available_qty)} {p.base_unit}</p></div>
        </button>
      ))}
    </div>
  );
}

/* ───────────── PR bahan & PO ───────────── */

function PrCreate({ onBack, onDone }) {
  const [products, setProducts] = useState([]);
  const [lines, setLines] = useState([{ product_id: "", quantity: "", est_price: "" }]);
  const [f, setF] = useState({ reason: "", needed_by_date: "", notes: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  useEffect(() => { axios.get(`${API}/products`).then((r) => setProducts(list(r.data))).catch(() => {}); }, []);
  const setLine = (i, p) => setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...p } : l)));
  const valid = f.reason.trim() && lines.every((l) => l.product_id && Number(l.quantity) > 0);
  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const items = lines.map((l) => { const p = products.find((x) => x.id === l.product_id); return { product_id: l.product_id, quantity: Number(l.quantity), unit: p?.base_unit || "meter", est_price: Number(l.est_price || 0) }; });
      const r = await axios.post(`${API}/purchase-requisitions`, { ...f, items, submit_now: true });
      onDone(`${r.data?.number || "PR"} diajukan${r.data?.status === "approved" ? " & langsung disetujui" : " — menunggu persetujuan"}.`);
    } catch (e) { setErr(errText(e, "Gagal membuat PR.")); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-2" data-testid="m-pr-create">
      <Back label="Permintaan pembelian" onClick={onBack} testId="m-pr-create-back" />
      <div className="m-card space-y-2 p-3">
        {lines.map((l, i) => (
          <div key={i} className="space-y-1.5 rounded-xl border border-[#EFF0F2] p-2" data-testid={`m-pr-line-${i}`}>
            {products.length === 0 ? <div className="field text-[#8E8E93]" data-testid={`m-pr-product-loading-${i}`}>Memuat produk…</div> :
              <KNSelect value={l.product_id} onValueChange={(v) => setLine(i, { product_id: v })} options={products.map((p) => ({ value: p.id, label: `${p.sku} — ${p.name}` }))} placeholder="Pilih bahan / produk" data-testid={`m-pr-product-${i}`} />}
            <div className="flex gap-2">
              <input type="number" inputMode="decimal" className="field flex-1" placeholder="Jumlah" value={l.quantity} onChange={(e) => setLine(i, { quantity: e.target.value })} data-testid={`m-pr-qty-${i}`} />
              <input type="number" inputMode="decimal" className="field flex-1" placeholder="Est. harga" value={l.est_price} onChange={(e) => setLine(i, { est_price: e.target.value })} data-testid={`m-pr-price-${i}`} />
              {lines.length > 1 && <button className="px-1 text-[#C0392B]" onClick={() => setLines((ls) => ls.filter((_, j) => j !== i))} aria-label="Hapus baris"><Trash2 size={16} /></button>}
            </div>
          </div>
        ))}
        <button className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#0058CC]" onClick={() => setLines((ls) => [...ls, { product_id: "", quantity: "", est_price: "" }])} data-testid="m-pr-add-line"><Plus size={13} /> Tambah baris</button>
        <input className="field" placeholder="Alasan kebutuhan *" value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} data-testid="m-pr-reason" />
        <label className="block text-[11.5px] font-semibold text-[#4A4B53]">Dibutuhkan tanggal<input type="date" className="field mt-1" value={f.needed_by_date} onChange={(e) => setF({ ...f, needed_by_date: e.target.value })} data-testid="m-pr-date" /></label>
        <textarea className="field" rows={2} placeholder="Catatan" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} data-testid="m-pr-notes" />
        {err && <div className="notice-bar danger text-xs" data-testid="m-pr-create-error">{err}</div>}
        <button className="primary-button w-full py-3" disabled={busy || !valid} onClick={submit} data-testid="m-pr-submit">{busy ? "Mengirim…" : "Ajukan PR"}</button>
      </div>
    </div>
  );
}

export function MobilePurchaseRequisitions({ focusId }) {
  const [rows, setRows] = useState(null);
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(focusId || null);
  const [create, setCreate] = useState(false);
  const [msg, setMsg] = useState(null);
  const load = () => axios.get(`${API}/purchase-requisitions`).then((r) => setRows(list(r.data))).catch(() => setRows([]));
  useEffect(() => { load(); }, []);
  const submitDraft = async (pr) => {
    try { await axios.post(`${API}/purchase-requisitions/${pr.id}/submit`); setMsg({ ok: true, text: `${pr.number} diajukan.` }); load(); }
    catch (e) { setMsg({ ok: false, text: errText(e, "Gagal mengajukan PR.") }); }
  };
  if (create) return <PrCreate onBack={() => setCreate(false)} onDone={(t) => { setCreate(false); setMsg({ ok: true, text: t }); load(); }} />;
  const shown = (rows || []).filter((r) => !status || r.status === status);
  return (
    <div className="space-y-2" data-testid="m-purchase-requisitions">
      <button className="primary-button flex w-full items-center justify-center gap-2 py-3" onClick={() => setCreate(true)} data-testid="m-pr-new"><Plus size={16} /> Buat PR bahan</button>
      <Chips items={[["", "Semua"], ["draft", "Draf"], ["pending_approval", "Menunggu"], ["approved", "Disetujui"], ["converted", "Jadi PO"], ["rejected", "Ditolak"]]} value={status} onChange={setStatus} prefix="m-pr-filter" />
      <Notice msg={msg} testId="m-pr-msg" />
      {rows === null && <p className="text-xs m-muted">Memuat…</p>}
      {rows && shown.length === 0 && <p className="py-8 text-center text-xs m-muted" data-testid="m-pr-empty">Tidak ada PR.</p>}
      {shown.map((r) => (
        <div key={r.id} className="m-card overflow-hidden" data-testid={`m-pr-${r.id}`}>
          <button className="m-press flex w-full items-start gap-2 p-3 text-left" onClick={() => setOpen(open === r.id ? null : r.id)}>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-1.5"><span className="text-[12.5px] font-bold text-[#0058CC]">{r.number}</span><Pill label={badgeLabel(r.status)} tone={r.status} /></div>
              <p className="truncate text-[12px]">{r.reason || "-"}</p>
              <p className="text-[10.5px] m-muted">{(r.items || []).length} baris · {fmtDate(r.created_at)}{r.po_number ? ` · ${r.po_number}` : ""}</p>
            </div>
            <span className="text-[12px] font-bold tabular-nums">{formatCurrency(r.total_est_amount)}</span>
          </button>
          {open === r.id && (
            <div className="border-t border-[#EFF0F2] bg-[#FAFBFC] px-3 py-2.5 text-[12px]" data-testid={`m-pr-detail-${r.id}`}>
              {(r.items || []).map((it, i) => <div key={i} className="flex justify-between py-0.5"><span className="min-w-0 flex-1 truncate">{it.product_name || it.description}</span><span className="tabular-nums">{formatQty(it.quantity)} {it.unit}</span></div>)}
              {r.reject_reason && <p className="mt-1 text-[11px] text-[#C0392B]">Ditolak: {r.reject_reason}</p>}
              {r.status === "draft" && <button className="primary-button mt-2 w-full py-2.5 text-[12px]" onClick={() => submitDraft(r)} data-testid={`m-pr-submit-draft-${r.id}`}>Ajukan PR</button>}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export function MobilePoWatch() {
  const [rows, setRows] = useState(null);
  useEffect(() => { axios.get(`${API}/purchase-orders`).then((r) => setRows(list(r.data))).catch(() => setRows([])); }, []);
  return (
    <div className="space-y-2" data-testid="m-po-watch">
      <p className="rounded-xl border border-[#CBDFFF] bg-[#F2F7FF] px-3 py-2 text-[11px] text-[#31465F]">Hanya-lihat: pantau PO bahan dari PR Anda. Pembuatan & persetujuan PO di tim Pembelian.</p>
      {rows === null && <p className="text-xs m-muted">Memuat…</p>}
      {rows && rows.length === 0 && <p className="py-8 text-center text-xs m-muted">Belum ada PO.</p>}
      {(rows || []).map((p) => (
        <div key={p.id} className="m-card p-3" data-testid={`m-po-${p.id}`}>
          <div className="flex items-center justify-between gap-2"><span className="text-[12.5px] font-bold text-[#0058CC]">{p.po_number}</span><Pill label={badgeLabel(p.status || p.approval_status)} tone={p.status || p.approval_status} /></div>
          <p className="truncate text-[12px]">{p.supplier_name || "-"}{p.pr_number ? ` · dari ${p.pr_number}` : ""}</p>
          <p className="text-[10.5px] m-muted">{(p.items || []).length} baris · kirim {fmtDate(p.expected_delivery_date)} · {formatCurrency(p.grand_total)}</p>
        </div>
      ))}
    </div>
  );
}
