/**
 * MobileInternalRequests — Permintaan Internal (PIN) versi HP.
 * Sales/Admin Sales MENGAJUKAN barang dari PT lain; yang berwenang (`meta.can_decide`,
 * mis. Admin Sales) langsung MENINDAK di HP: pilih PT sumber → jadikan transaksi
 * antar-PT, atau tolak. Server & aturan sama dengan layar desktop InternalRequestsView.
 */
import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Plus, Trash2, ChevronDown, ArrowLeftRight } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import KNSelect from "../../../components/KNSelect";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import { askConfirm, askReason } from "../../../services/confirmService";
import {
  PIN_STATUS_CLASS, PIN_STATUS_LABEL, cancelInternalRequest, convertInternalRequest, createInternalRequest,
  internalRequestSources, listInternalRequests, pinMeta, productAvailability, rejectInternalRequest,
} from "../../internal_requests/internalRequestsApi";

const errText = (e, fb) => { const d = e?.response?.data?.detail; return (d && (d.message || (typeof d === "string" ? d : JSON.stringify(d)))) || fb; };
const FILTERS = [["", "Semua"], ["submitted", "Antrean"], ["converted", "Jadi antar-PT"], ["rejected", "Ditolak"], ["cancelled", "Batal"]];
const fmtDate = (s) => (s ? new Date(s).toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" }) : "-");

function DecidePanel({ req, onDone }) {
  const [cands, setCands] = useState(null);
  const [pick, setPick] = useState("");
  const [submitNow, setSubmitNow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  useEffect(() => {
    internalRequestSources(req.id).then((d) => { const c = d.candidates || []; setCands(c); const ok = c.find((x) => x.can_fulfill); if (ok) setPick(ok.entity_id); })
      .catch((e) => { setCands([]); setErr(errText(e, "Gagal memuat PT sumber.")); });
  }, [req.id]);
  const convert = async () => {
    if (!pick) { setErr("Pilih badan usaha sumber dulu."); return; }
    setBusy(true); setErr("");
    try {
      const res = await convertInternalRequest(req.id, { source_entity_id: pick, submit_now: submitNow });
      onDone(`${req.number} menjadi transaksi antar-PT ${res.request?.interco_number_buyer || ""} ⇄ ${res.request?.interco_number_seller || ""}.`);
    } catch (e) { setErr(errText(e, "Gagal mengubah menjadi transaksi antar-PT.")); } finally { setBusy(false); }
  };
  const reject = async () => {
    const reason = await askReason({ title: `Tolak ${req.number}?`, danger: true });
    if (!reason) return;
    setBusy(true); setErr("");
    try { await rejectInternalRequest(req.id, reason); onDone(`${req.number} ditolak.`); }
    catch (e) { setErr(errText(e, "Gagal menolak.")); } finally { setBusy(false); }
  };
  return (
    <div className="mt-2 space-y-2 rounded-xl border border-[#CBDFFF] bg-[#F7FAFF] p-2.5" data-testid={`m-pin-decide-${req.id}`}>
      <p className="text-[11px] font-bold uppercase tracking-wide text-[#0058CC]">Tindak — pilih PT sumber</p>
      {cands === null && <p className="text-xs m-muted">Memuat kandidat…</p>}
      {(cands || []).map((c) => (
        <button key={c.entity_id} type="button" onClick={() => setPick(c.entity_id)} data-testid={`m-pin-source-${req.id}-${c.entity_id}`}
          className={`w-full rounded-lg border p-2 text-left text-[12px] ${pick === c.entity_id ? "border-[#0058CC] bg-white" : "border-[#E5E5EA] bg-white/60"}`}>
          <div className="flex items-center justify-between gap-2"><b className="truncate">{c.entity_name}</b>
            <span className={`rounded-full px-1.5 py-0.5 text-[9.5px] font-bold ${c.can_fulfill ? "bg-[#E6F6EC] text-[#1B7F4B]" : "bg-[#FFF4E5] text-[#8A5300]"}`}>{c.can_fulfill ? "Bisa dipenuhi" : c.stock_enough ? "Harga belum siap" : "Stok kurang"}</span></div>
          {(c.lines || []).map((l) => <p key={l.product_id} className="text-[10.5px] m-muted">{l.product_name}: butuh {formatQty(l.needed)} · ada {formatQty(l.available)} {l.unit}</p>)}
          {c.price_preview > 0 && <p className="text-[10.5px] tabular-nums">Perkiraan nilai {formatCurrency(c.price_preview)}</p>}
          {(c.price_issues || []).length > 0 && <p className="text-[10.5px] text-[#8A5300]">{c.price_issues.join(" · ")}</p>}
        </button>
      ))}
      <label className="flex items-center gap-2 text-[12px]"><input type="checkbox" checked={submitNow} onChange={(e) => setSubmitNow(e.target.checked)} data-testid={`m-pin-submit-now-${req.id}`} /> Langsung ajukan transaksi antar-PT</label>
      {err && <div className="notice-bar danger text-xs" data-testid={`m-pin-decide-error-${req.id}`}>{err}</div>}
      <div className="flex gap-2">
        <button className="primary-button flex-1 py-2.5 text-[12px]" disabled={busy || !pick} onClick={convert} data-testid={`m-pin-convert-${req.id}`}><ArrowLeftRight size={13} className="mr-1 inline" /> Jadikan antar-PT</button>
        <button className="danger-button flex-1 py-2.5 text-[12px]" disabled={busy} onClick={reject} data-testid={`m-pin-reject-${req.id}`}>Tolak</button>
      </div>
    </div>
  );
}

function PinCard({ req, meta, user, open, onToggle, onChanged }) {
  const [decide, setDecide] = useState(false);
  const isOpen = (meta?.open_statuses || ["submitted"]).includes(req.status);
  const mine = req.requested_by_id === user?.id || req.created_by === user?.id;
  const cancel = async () => {
    const reason = await askReason({ title: `Batalkan ${req.number}?`, danger: true });
    if (!reason) return;
    try { await cancelInternalRequest(req.id, reason); onChanged(`${req.number} dibatalkan.`); } catch (e) { onChanged(errText(e, "Gagal membatalkan."), true); }
  };
  return (
    <div className="m-card overflow-hidden" data-testid={`m-pin-${req.id}`}>
      <button className="m-press flex w-full items-start gap-2 p-3 text-left" onClick={onToggle}>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[12.5px] font-bold text-[#0058CC]">{req.number}</span>
            <span className={`rounded-full border px-1.5 py-0.5 text-[9.5px] font-bold ${PIN_STATUS_CLASS[req.status] || ""}`}>{PIN_STATUS_LABEL[req.status] || req.status}</span>
          </div>
          <p className="truncate text-[12px] text-[#3C3C43]">{req.reason || "-"}</p>
          <p className="text-[10.5px] m-muted">{(req.items || []).length} barang{req.needed_date ? ` · perlu ${fmtDate(req.needed_date)}` : ""}{req.source_entity_name ? ` · dari ${req.source_entity_name}` : ""}</p>
        </div>
        <div className="flex flex-col items-end"><span className="text-[12px] font-bold tabular-nums">{formatCurrency(req.est_value)}</span><ChevronDown size={15} className={`mt-1 text-[#8E8E93] transition-transform ${open ? "rotate-180" : ""}`} /></div>
      </button>
      {open && (
        <div className="border-t border-[#EFF0F2] bg-[#FAFBFC] px-3 py-2.5 text-[12px]" data-testid={`m-pin-detail-${req.id}`}>
          {(req.items || []).map((it) => (
            <div key={it.product_id} className="flex justify-between py-0.5"><span className="min-w-0 flex-1 truncate">{it.product_name}</span><span className="tabular-nums">{formatQty(it.quantity)} {it.unit}</span></div>
          ))}
          {req.source_order_number && <p className="mt-1 text-[11px] m-muted">Untuk pesanan {req.source_order_number}</p>}
          {req.interco_number_buyer && <p className="mt-1 text-[11px] text-[#1B7F4B]">Transaksi antar-PT: {req.interco_number_buyer} ⇄ {req.interco_number_seller}</p>}
          {req.decision_reason && <p className="mt-1 text-[11px] text-[#C0392B]">Alasan: {req.decision_reason}</p>}
          {isOpen && (
            <div className="mt-2 flex gap-2">
              {meta?.can_decide && <button className="primary-button flex-1 py-2 text-[12px]" onClick={() => setDecide((v) => !v)} data-testid={`m-pin-decide-toggle-${req.id}`}>{decide ? "Tutup" : "Tindak"}</button>}
              {(mine || meta?.can_decide) && <button className="secondary-button flex-1 py-2 text-[12px]" onClick={cancel} data-testid={`m-pin-cancel-${req.id}`}>Batalkan</button>}
            </div>
          )}
          {isOpen && decide && <DecidePanel req={req} onDone={(m) => { setDecide(false); onChanged(m); }} />}
        </div>
      )}
    </div>
  );
}

function PinCreate({ onBack, onDone }) {
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [lines, setLines] = useState([{ product_id: "", quantity: "", notes: "" }]);
  const [avail, setAvail] = useState({});
  const [f, setF] = useState({ reason: "", needed_date: "", notes: "", source_order_id: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  useEffect(() => {
    axios.get(`${API}/products`).then((r) => setProducts(Array.isArray(r.data) ? r.data : r.data.items || [])).catch(() => {});
    axios.get(`${API}/sales-orders`, { params: { limit: 50 } }).then((r) => setOrders(Array.isArray(r.data) ? r.data : r.data.items || [])).catch(() => {});
  }, []);
  const setLine = (i, patch) => setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  const pickProduct = (i, pid) => {
    setLine(i, { product_id: pid });
    if (pid && !avail[pid]) productAvailability(pid).then((a) => setAvail((m) => ({ ...m, [pid]: a }))).catch(() => {});
  };
  const valid = lines.every((l) => l.product_id && Number(l.quantity) > 0) && f.reason.trim();
  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const doc = await createInternalRequest({ ...f, items: lines.map((l) => ({ product_id: l.product_id, quantity: Number(l.quantity), notes: l.notes })) });
      onDone(`${doc.number || "Permintaan"} diajukan — menunggu ditindak Admin Sales/manajer.`);
    } catch (e) { setErr(errText(e, "Gagal mengajukan permintaan.")); } finally { setBusy(false); }
  };
  const productOpts = useMemo(() => products.map((p) => ({ value: p.id, label: `${p.sku} — ${p.name}` })), [products]);
  return (
    <div className="space-y-2" data-testid="m-pin-create">
      <button className="m-subpage-back" onClick={onBack} data-testid="m-pin-create-back"><ArrowLeft size={17} /> Permintaan internal</button>
      <div className="m-card space-y-2 p-3">
        <p className="text-[11.5px] m-muted">Minta barang dari badan usaha lain dalam grup saat stok sendiri kurang. PT sumber dipilih oleh yang menindak.</p>
        {lines.map((l, i) => {
          const a = avail[l.product_id];
          return (
            <div key={i} className="space-y-1.5 rounded-xl border border-[#EFF0F2] p-2" data-testid={`m-pin-line-${i}`}>
              {productOpts.length === 0 ? <div className="field text-[#8E8E93]" data-testid={`m-pin-product-loading-${i}`}>Memuat barang…</div> :
                <KNSelect value={l.product_id} onValueChange={(v) => pickProduct(i, v)} options={productOpts} placeholder="Pilih barang" data-testid={`m-pin-product-${i}`} />}
              {a && <p className="text-[10.5px] m-muted" data-testid={`m-pin-avail-${i}`}>Stok sendiri {formatQty(a.own_available)} · PT lain {formatQty(a.other_entities_available)} {a.product?.base_unit || ""}</p>}
              <div className="flex gap-2">
                <input type="number" inputMode="decimal" className="field flex-1" placeholder="Jumlah" value={l.quantity} onChange={(e) => setLine(i, { quantity: e.target.value })} data-testid={`m-pin-qty-${i}`} />
                {lines.length > 1 && <button className="px-2 text-[#C0392B]" onClick={() => setLines((ls) => ls.filter((_, j) => j !== i))} aria-label="Hapus baris" data-testid={`m-pin-remove-${i}`}><Trash2 size={16} /></button>}
              </div>
            </div>
          );
        })}
        <button className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#0058CC]" onClick={() => setLines((ls) => [...ls, { product_id: "", quantity: "", notes: "" }])} data-testid="m-pin-add-line"><Plus size={13} /> Tambah barang</button>
        <input className="field" placeholder="Alasan permintaan *" value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} data-testid="m-pin-reason" />
        <KNSelect value={f.source_order_id} onValueChange={(v) => setF({ ...f, source_order_id: v })} placeholder="Untuk pesanan (opsional)"
          options={[{ value: "", label: "— Tanpa pesanan (stok sendiri) —" }, ...orders.map((s) => ({ value: s.id, label: `${s.number} · ${s.customer_name || ""}` }))]} data-testid="m-pin-order" />
        <label className="block text-[11.5px] font-semibold text-[#4A4B53]">Dibutuhkan tanggal
          <input type="date" className="field mt-1" value={f.needed_date} onChange={(e) => setF({ ...f, needed_date: e.target.value })} data-testid="m-pin-date" />
        </label>
        <textarea className="field" rows={2} placeholder="Catatan" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} data-testid="m-pin-notes" />
        {err && <div className="notice-bar danger text-xs" data-testid="m-pin-create-error">{err}</div>}
        <button className="primary-button w-full py-3" disabled={busy || !valid} onClick={submit} data-testid="m-pin-submit">{busy ? "Mengirim…" : "Ajukan permintaan"}</button>
      </div>
    </div>
  );
}

export default function MobileInternalRequests({ user, focusId }) {
  const [rows, setRows] = useState(null);
  const [meta, setMeta] = useState(null);
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(focusId || null);
  const [create, setCreate] = useState(false);
  const [msg, setMsg] = useState(null);
  const load = () => listInternalRequests(status ? { status } : {}).then((d) => setRows(Array.isArray(d) ? d : d.items || [])).catch((e) => { setRows([]); setMsg({ ok: false, text: errText(e, "Gagal memuat permintaan.") }); });
  useEffect(() => { pinMeta().then(setMeta).catch(() => setMeta({})); }, []);
  useEffect(() => { setRows(null); load(); }, [status]); // eslint-disable-line react-hooks/exhaustive-deps
  const changed = (text, bad) => { setMsg({ ok: !bad, text }); load(); };
  if (create) return <PinCreate onBack={() => setCreate(false)} onDone={(t) => { setCreate(false); changed(t); }} />;
  return (
    <div className="space-y-2" data-testid="m-internal-requests">
      <button className="primary-button flex w-full items-center justify-center gap-2 py-3" onClick={() => setCreate(true)} data-testid="m-pin-new"><Plus size={16} /> Ajukan permintaan internal</button>
      <div className="no-scrollbar flex gap-2 overflow-x-auto py-1">
        {FILTERS.map(([id, label]) => (
          <button key={id || "all"} onClick={() => setStatus(id)} data-testid={`m-pin-filter-${id || "all"}`}
            className={`h-9 shrink-0 whitespace-nowrap rounded-full border px-3 text-[12px] font-semibold ${status === id ? "border-[#0058CC] bg-[#0058CC] text-white" : "border-[#E5E5EA] bg-white text-[#3A3A3C]"}`}>{label}</button>
        ))}
      </div>
      {msg && <div className={`notice-bar ${msg.ok ? "success" : "danger"} text-xs`} data-testid="m-pin-msg">{msg.text}</div>}
      {rows === null && <p className="text-xs m-muted" data-testid="m-pin-loading">Memuat permintaan…</p>}
      {rows && rows.length === 0 && <p className="py-8 text-center text-xs m-muted" data-testid="m-pin-empty">Belum ada permintaan internal.</p>}
      {(rows || []).map((r) => <PinCard key={r.id} req={r} meta={meta} user={user} open={open === r.id} onToggle={() => setOpen(open === r.id ? null : r.id)} onChanged={changed} />)}
    </div>
  );
}
