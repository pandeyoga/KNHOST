/**
 * Layar HP untuk MD / Merchandiser (cermin menu web peran `md`, ROLE_NAV):
 *  - MobileMdDesk            : Meja MD (/md/desk) — antrean desain, sample/labdip, PR bahan, SPK tanpa acuan.
 *  - MobileDesignRequests    : permintaan desain — ajukan, tugaskan desainer, ACC / minta revisi, batalkan.
 *  - MobileRndSamples        : sample & labdip — putaran per supplier, nilai putaran (ACC/revisi/tolak), putuskan pemenang.
 *  - MobileMdProducts        : master produk — cari, detail + stok per gudang, ubah harga/nama.
 *  - MobilePurchaseRequisitions : PR bahan — daftar, buat (form desktop PrCreateModal), ajukan draf.
 *  - MobilePoWatch           : pantau PO (hanya-lihat).
 * Endpoint & wewenang sama dengan layar desktop (RoleDesk, DesignRequests, RnD, Katalog, PR).
 */
import AttachmentGallery from "../../../components/AttachmentThumb";
import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, ClipboardList, Plus, RefreshCw, Search, Palette, FlaskConical, FileStack } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import KNSelect from "../../../components/KNSelect";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import { askConfirm, askReason } from "../../../services/confirmService";
import KNDatePicker from "../../../components/KNDatePicker";
import { ageTone, badgeLabel, mdDesk, rowLink } from "../../sales_admin/workDeskApi";
import { errText } from "./MobileSalesFlows";
import { STATUS_STYLE as PR_STATUS_STYLE } from "../../purchasing/prConstants";
import ErrorNotice from "../../../components/ErrorNotice";
import DesignRequestCreateModal from "../../design/DesignRequestCreateModal";
import { Back, Chips, Field, Notice, Pill, fmtDate, list } from "./mdMobileParts";
import PrCreateModal from "../../purchasing/PrCreateModal";
import { MobileMdProducts } from "./MobileMdProducts";

// Fase 3 · P7 — layar Produk diekstrak ke MobileMdProducts.jsx (batas 500 baris); diekspor ulang supaya impor lama tetap jalan.
export { MobileMdProducts };

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
        <div className="m-card p-3" data-testid="m-md-metric-oldest"><p className="text-[10px] font-bold uppercase text-[#8E8E93]">Umur tertua</p><p className="text-[20px] font-bold">{oldest ? `${oldest} hari` : "< 1 hari"}</p></div>
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
  // G5-59 — dialog batal dulu bertombol generik "Konfirmasi"; "ACC desain" langsung menulis tanpa konfirmasi.
  const withReason = async (path, title, okText, confirmLabel) => { const reason = await askReason({ title, danger: path !== "approve", confirmLabel }); if (reason) act(path, { reason, note: reason }, okText); };
  const approve = async () => {
    if (!(await askConfirm({ title: `ACC desain ${d.number}?`, message: "Desain yang dikirim desainer disetujui dan permintaan ditutup.", confirmLabel: "ACC desain" }))) return;
    act("approve", { note: "" }, "Desain di-ACC.");
  };
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
          <Field label="Tenggat"><KNDatePicker value={assign.due_date} onChange={(v) => setAssign({ ...assign, due_date: v || "" })} data-testid="m-dsr-assign-due" /></Field>
          <button className="primary-button w-full py-2.5" disabled={busy || !assign.assigned_to} onClick={() => act("assign", assign, "Desainer ditugaskan.")} data-testid="m-dsr-assign-submit">Tugaskan</button>
        </div>
      )}
      {d.status === "delivered" && (
        <div className="grid grid-cols-2 gap-2" data-testid="m-dsr-decide">
          <button className="primary-button py-3" disabled={busy} onClick={approve} data-testid="m-dsr-approve">ACC desain</button>
          <button className="secondary-button py-3" disabled={busy} onClick={() => withReason("reject", "Minta revisi — apa yang perlu diubah?", "Dikembalikan untuk revisi.", "Minta revisi")} data-testid="m-dsr-reject">Minta revisi</button>
        </div>
      )}
      {d.status === "draft" && <button className="primary-button w-full py-3" disabled={busy} onClick={() => act("submit", {}, "Diajukan.")} data-testid="m-dsr-submit-draft">Ajukan</button>}
      {open && <button className="w-full py-2 text-[12px] font-semibold text-[#C0392B]" disabled={busy} onClick={() => withReason("cancel", `Batalkan ${d.number}?`, "Permintaan dibatalkan.", "Batalkan permintaan")} data-testid="m-dsr-cancel">Batalkan permintaan</button>}
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
  if (sel) return <DesignDetail id={sel} meta={meta} onBack={() => { setSel(null); load(); }} />;
  const shown = (rows || []).filter((r) => !status || r.status === status);
  return (
    <div className="space-y-2" data-testid="m-design-requests">
      <button className="primary-button flex w-full items-center justify-center gap-2 py-3" onClick={() => setCreate(true)} data-testid="m-dsr-new"><Plus size={16} /> Permintaan desain baru</button>
      {/* Fase 3 · P7 (D-27) — form HP ringkas diganti form DESKTOP `DesignRequestCreateModal` (isian lengkap: sumber,
          pesanan/pelanggan, kategori pattern + design, brief, warna target, gambar referensi, desainer, tenggat);
          di HP FormModal tampil layar penuh 1 kolom. */}
      <DesignRequestCreateModal open={create} meta={meta || undefined} testId="m-dsr-create" onClose={() => setCreate(false)}
        onCreated={(doc) => { setCreate(false); setMsg({ ok: true, text: `${doc?.number || "Permintaan desain"} diajukan.` }); load(); }} />
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
            {/* UAT 24 Okt (P17) — foto bukti putaran tampil & bisa dibuka di HP (dulu hanya "N lampiran foto"). */}
            {(r.attachments || []).length > 0 && <div className="mt-1"><AttachmentGallery size={44} testId={`m-smp-proof-${r.id}`}
              items={r.attachments.map((a) => ({ url: `${API}/rnd/samples/${s.id}/rounds/${r.id}/attachments/${a.id}`, filename: a.filename, content_type: a.content_type }))} /></div>}
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
  const [loadErr, setLoadErr] = useState(null);
  const load = () => axios.get(`${API}/rnd/samples`).then((r) => setRows(list(r.data))).catch((e) => { setRows([]); setLoadErr(e); });
  useEffect(() => { axios.get(`${API}/rnd/meta`).then((r) => setMeta(r.data)).catch(() => {}); load(); }, []);
  useEffect(() => { if (focusId) setSel(focusId); }, [focusId]);
  if (sel) return <SampleDetail id={sel} reasons={meta?.reasons} onBack={() => { setSel(null); load(); }} />;
  const shown = (rows || []).filter((r) => (!status || r.status === status) && (!q || `${r.number} ${r.title}`.toLowerCase().includes(q.toLowerCase())));
  return (
    <div className="space-y-2" data-testid="m-rnd-samples">
      {loadErr && <ErrorNotice message={loadErr} onRetry={() => { setLoadErr(""); load(); }} testId="m-smp-load-error" />}
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

/* ───────────── PR bahan & PO ───────────── */

// Fase 4 · R1 — form HP ringkas `PrCreate` (barang, jumlah, est. harga, alasan, tanggal, catatan; selalu langsung
// diajukan) DIGANTI form desktop `purchasing/PrCreateModal` (keputusan pemilik: form input HP tidak diringkas): pemilih
// artikel → warna (nama KN / supplier), pemenuhan beli/makloon, roll, lokasi kirim, supplier preferensi (disaring ke yang
// berkontrak / terdaftar, bisa "Tampilkan semua"), alasan jalur restock, "Langsung ajukan" opsional, total estimasi.
// Data master dimuat SAMA dengan desktop (`PurchaseRequisitions.loadMasters`: /products, /warehouses, /suppliers;
// gagal = daftar kosong) — bedanya hanya waktunya: saat "Buat PR bahan" pertama diketuk (hemat kuota HP).
const PR_STATUS_TEXT = { approved: "diajukan & langsung disetujui", pending_approval: "diajukan — menunggu persetujuan", draft: "tersimpan sebagai draf" };
export const prCreatedText = (pr) => `${pr?.number || "PR"} ${PR_STATUS_TEXT[pr?.status] || "tersimpan"}.`;

// Fase 4 · R1 (permintaan koordinator, temuan R7) — PR bisa terealisasi ke PO ATAU Order Makloon (mis. PR-00005 Kanda →
// Order Makloon). Nomor dokumen diambil dari data realisasi baris yang dikirim server (`items[].realizations[]`: jenis +
// `ref_number`; realisasi PO batal diabaikan — sama dengan panel Pemenuhan & Realisasi desktop). "Belum tercatat" hanya
// bila memang tidak ada nomor (dulu HP selalu menulis "nomor PO belum tercatat" walau realisasinya Order Makloon).
export function prRealizationDocs(pr) {
  const docs = [];
  (pr?.items || []).forEach((it) => (it.realizations || []).forEach((x) => {
    if (x.voided || !x.ref_number) return;
    const label = `${x.type === "makloon_order" ? "Order Makloon" : "PO"} ${x.ref_number}`;
    if (!docs.includes(label)) docs.push(label);
  }));
  if (!docs.length && pr?.po_number) docs.push(`PO ${pr.po_number}`);
  return docs;
}
export function prRealizationText(pr) {
  const docs = prRealizationDocs(pr);
  if (docs.length) return ` · ${docs.join(", ")}`;
  if (pr?.status !== "converted") return "";
  const makloonOnly = (pr.makloon_order_ids || []).length > 0 && !(pr.po_ids || []).length;
  return makloonOnly ? " · nomor Order Makloon belum tercatat" : " · nomor PO belum tercatat";
}

function usePrMasters(wanted) {
  const [masters, setMasters] = useState(null);
  useEffect(() => {
    if (!wanted || masters) return;
    Promise.all(["products", "warehouses", "suppliers"].map((p) => axios.get(`${API}/${p}`).catch(() => ({ data: [] }))))
      .then(([p, w, s]) => setMasters({ products: list(p.data), warehouses: list(w.data), suppliers: list(s.data) }));
  }, [wanted, masters]);
  return masters;
}

export function MobilePurchaseRequisitions({ focusId, selectedEntity }) {
  const [rows, setRows] = useState(null);
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(focusId || null);
  const [create, setCreate] = useState(false);
  const [msg, setMsg] = useState(null);
  const [loadErr, setLoadErr] = useState(null);
  const masters = usePrMasters(create);
  const load = () => axios.get(`${API}/purchase-requisitions`).then((r) => setRows(list(r.data))).catch((e) => { setRows([]); setLoadErr(e); });
  useEffect(() => { load(); }, []);
  const submitDraft = async (pr) => {
    try { await axios.post(`${API}/purchase-requisitions/${pr.id}/submit`); setMsg({ ok: true, text: `${pr.number} diajukan.` }); load(); }
    catch (e) { setMsg({ ok: false, text: errText(e, "Gagal mengajukan PR.") }); }
  };
  const shown = (rows || []).filter((r) => !status || r.status === status);
  return (
    <div className="space-y-2" data-testid="m-purchase-requisitions">
      {loadErr && <ErrorNotice message={loadErr} onRetry={() => { setLoadErr(""); load(); }} testId="m-pr-load-error" />}
      <button className="primary-button flex w-full items-center justify-center gap-2 py-3" disabled={create && !masters} onClick={() => setCreate(true)} data-testid="m-pr-new">
        <Plus size={16} /> {create && !masters ? "Memuat data PR…" : "Buat PR bahan"}
      </button>
      {create && masters && (
        <PrCreateModal products={masters.products} warehouses={masters.warehouses} suppliers={masters.suppliers}
          selectedEntity={selectedEntity} onCancel={() => setCreate(false)}
          onCreated={(pr) => { setCreate(false); setMsg({ ok: true, text: prCreatedText(pr) }); load(); }} />
      )}
      <Chips items={[["", "Semua"], ["draft", "Draf"], ["pending_approval", "Menunggu"], ["approved", "Disetujui"], ["converted", "Jadi PO"], ["rejected", "Ditolak"]]} value={status} onChange={setStatus} prefix="m-pr-filter" />
      <Notice msg={msg} testId="m-pr-msg" />
      {rows === null && <p className="text-xs m-muted">Memuat…</p>}
      {rows && shown.length === 0 && <p className="py-8 text-center text-xs m-muted" data-testid="m-pr-empty">Tidak ada PR.</p>}
      {shown.map((r) => (
        <div key={r.id} className="m-card overflow-hidden" data-testid={`m-pr-${r.id}`}>
          <button className="m-press flex w-full items-start gap-2 p-3 text-left" onClick={() => setOpen(open === r.id ? null : r.id)}>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-1.5"><span className="text-[12.5px] font-bold text-[#0058CC]">{r.number}</span><Pill label={PR_STATUS_STYLE[r.status]?.label || badgeLabel(r.status)} tone={r.status} /></div>
              {/* G5-60 — judul dulu terpotong tepat di nomor pembeda ("…SORD-261024-0…"); kini 2 baris & nomor tak patah. */}
              <p className="line-clamp-2 break-words text-[12px]">{r.reason || "-"}</p>
              <p className="text-[11px] m-muted" data-testid={`m-pr-meta-${r.id}`}>{(r.items || []).length} baris · {fmtDate(r.created_at)}{prRealizationText(r)}</p>
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
  const [loadErr, setLoadErr] = useState(null);
  const load = () => axios.get(`${API}/purchase-orders`).then((r) => setRows(list(r.data))).catch((e) => { setRows([]); setLoadErr(e); });
  useEffect(() => { load(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="space-y-2" data-testid="m-po-watch">
      {loadErr && <ErrorNotice message={loadErr} onRetry={() => { setLoadErr(""); load(); }} testId="m-po-load-error" />}
      <p className="rounded-xl border border-[#CBDFFF] bg-[#F2F7FF] px-3 py-2 text-[11px] text-[#31465F]">Hanya-lihat: pantau PO bahan dari PR Anda. Pembuatan & persetujuan PO di tim Pembelian.</p>
      {rows === null && <p className="text-xs m-muted">Memuat…</p>}
      {rows && rows.length === 0 && <p className="py-8 text-center text-xs m-muted">Belum ada PO.</p>}
      {(rows || []).map((p) => (
        <div key={p.id} className="m-card p-3" data-testid={`m-po-${p.id}`}>
          <div className="flex items-center justify-between gap-2"><span className="text-[12.5px] font-bold text-[#0058CC]">{p.po_number}</span><Pill label={badgeLabel(p.status || p.approval_status)} tone={p.status || p.approval_status} /></div>
          <p className="truncate text-[12px]">{p.supplier_name || "-"}{p.pr_number ? ` · dari ${p.pr_number}` : ""}</p>
          <p className="text-[10.5px] m-muted">{[`${(p.items || []).length} baris`, p.expected_delivery_date ? `kirim ${fmtDate(p.expected_delivery_date)}` : "", formatCurrency(p.grand_total)].filter(Boolean).join(" · ")}</p>
        </div>
      ))}
    </div>
  );
}
