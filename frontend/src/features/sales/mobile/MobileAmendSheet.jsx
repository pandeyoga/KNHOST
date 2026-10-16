import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, CheckCircle2, Loader2, Minus, Plus, RotateCcw } from "lucide-react";
import MoneyInput from "../../../components/MoneyInput";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import { errText, listReasons, previewAmendment, proposeAmendment, statusMeta } from "../../finance/amendments/amendmentApi";

const EPS = 0.0001;
const FIELDS = ["quantity", "price", "discount_percent"];
const num = (v) => Math.max(Number(v) || 0, 0);

function draft(order) {
  return (order.items || []).map((it) => {
    const orig = { quantity: Number(it.quantity || 0), price: Number(it.price || 0), discount_percent: Number(it.discount_percent || 0) };
    return { product_id: it.product_id, name: it.product_name || it.sku || it.product_id, unit: it.unit || "", orig, ...orig };
  });
}

// Alasan dipilih otomatis dari jenis perubahan (tetap bisa diganti) → koreksi cukup dua ketukan.
function autoReason(changes) {
  const f = new Set(changes.map((c) => c.field));
  if (f.has("price")) return "price_correction";
  if (f.has("discount_percent")) return "discount_grant";
  return f.has("quantity") ? "qty_adjustment" : "";
}

function ItemRow({ row, onChange, onReset }) {
  const dirty = FIELDS.some((f) => Math.abs(row[f] - row.orig[f]) > EPS);
  const tid = `m-amd-item-${row.product_id}`;
  return (
    <div className={`m-card space-y-2 p-3 ${dirty ? "ring-1 ring-[#FFB020]" : ""}`} data-testid={tid}>
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-bold">{row.name}</p>
          <p className="text-[10.5px] m-muted">semula {formatQty(row.orig.quantity)} {row.unit} × {formatCurrency(row.orig.price)}{row.orig.discount_percent ? ` · disc ${formatQty(row.orig.discount_percent)}%` : ""}</p>
        </div>
        {dirty && <button onClick={onReset} className="text-[#0058CC]" aria-label="Kembalikan" data-testid={`${tid}-reset`}><RotateCcw size={15} /></button>}
      </div>
      <div className="flex items-center gap-2">
        <span className="w-14 text-[11px] font-semibold m-muted">Jumlah</span>
        <button className="m-press grid h-9 w-9 place-items-center rounded-lg bg-[#F2F3F5]" onClick={() => onChange("quantity", num(row.quantity - 1))} data-testid={`${tid}-minus`}><Minus size={15} /></button>
        <input type="number" inputMode="decimal" min="0" step="any" className="field !py-2 text-center tabular-nums" value={row.quantity}
          onChange={(e) => onChange("quantity", num(e.target.value))} data-testid={`${tid}-qty`} />
        <button className="m-press grid h-9 w-9 place-items-center rounded-lg bg-[#F2F3F5]" onClick={() => onChange("quantity", row.quantity + 1)} data-testid={`${tid}-plus`}><Plus size={15} /></button>
      </div>
      <div className="grid grid-cols-[1fr_88px] gap-2">
        <label className="block"><span className="text-[10.5px] font-semibold m-muted">Harga satuan</span>
          <MoneyInput testId={`${tid}-price`} className="field !py-2 tabular-nums" value={row.price} onChange={(v) => onChange("price", num(v))} /></label>
        <label className="block"><span className="text-[10.5px] font-semibold m-muted">Diskon %</span>
          <input type="number" inputMode="decimal" min="0" max="100" step="any" className="field !py-2 tabular-nums" value={row.discount_percent}
            onChange={(e) => onChange("discount_percent", Math.min(num(e.target.value), 100))} data-testid={`${tid}-disc`} /></label>
      </div>
    </div>
  );
}

function Impact({ preview, previewing, error, hasChange }) {
  if (!hasChange) return <p className="rounded-xl border border-dashed border-[#D1D1D6] p-3 text-center text-[12px] m-muted" data-testid="m-amd-no-change">Ubah jumlah, harga, atau diskon — dampaknya dihitung server.</p>;
  if (error) return <div className="notice-bar danger text-xs" data-testid="m-amd-error">{error}</div>;
  if (!preview) return <p className="flex items-center justify-center gap-2 p-3 text-[12px] m-muted"><Loader2 size={14} className="animate-spin" /> Menghitung dampak…</p>;
  const d = Number(preview.impact?.delta || 0);
  return (
    <div className="m-card space-y-1.5 p-3 text-[12px]" data-testid="m-amd-impact">
      <div className="flex justify-between"><span className="m-muted">Nilai sekarang</span><span className="tabular-nums">{formatCurrency(preview.impact?.amount_before)}</span></div>
      <div className="flex justify-between font-bold"><span>Setelah koreksi</span><span className="tabular-nums">{formatCurrency(preview.impact?.amount_after)}</span></div>
      <div className="flex justify-between"><span className="m-muted">Selisih</span><span className={`tabular-nums font-bold ${d < 0 ? "text-[#C0392B]" : "text-[#1A7A3A]"}`} data-testid="m-amd-delta">{d > 0 ? "+" : ""}{formatCurrency(d)}{previewing ? " …" : ""}</span></div>
      <p className="border-t border-[#EFF0F2] pt-1.5 text-[11px] m-muted">{preview.method_label}</p>
      <p className={`text-[11px] font-semibold ${preview.requires_approval ? "text-[#9A5B00]" : "text-[#1A7A3A]"}`} data-testid="m-amd-approval">
        {preview.requires_approval ? `Perlu persetujuan ${preview.required_role || "manager"}.` : "Langsung diterapkan setelah diajukan."}
      </p>
    </div>
  );
}

function Result({ result, onClose }) {
  const meta = statusMeta(result.status);
  const waiting = result.status === "pending_approval";
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center" data-testid="m-amd-result">
      <CheckCircle2 size={44} className="text-[#1A7A3A]" />
      <p className="text-[16px] font-bold">Amandemen {result.number}</p>
      <span className="rounded px-2 py-1 text-[11px] font-bold uppercase" style={{ background: meta.bg, color: meta.fg }} data-testid="m-amd-result-status">{meta.label}</span>
      <p className="text-[12.5px] text-[#3C3C43]" data-testid="m-amd-result-message">
        {waiting ? `Menunggu persetujuan ${result.required_role || "manager"}. Nilai pesanan belum berubah sampai diputuskan.`
          : `Koreksi diterapkan (${result.method_label}). Selisih ${formatCurrency(Math.abs(Number(result.impact?.delta || 0)))}.`}
      </p>
      <button className="primary-button mt-2 w-full py-3" onClick={() => onClose(true)} data-testid="m-amd-result-done">Selesai</button>
    </div>
  );
}

/** Koreksi pesanan dari HP: ubah angka → alasan terpilih otomatis → "Ajukan koreksi". */
export default function MobileAmendSheet({ order, onClose }) {
  const [rows, setRows] = useState(() => draft(order));
  const [reasons, setReasons] = useState([]);
  const [reason, setReason] = useState("");
  const [manualReason, setManualReason] = useState(false);
  const [note, setNote] = useState("");
  const [preview, setPreview] = useState(null);
  const [previewing, setPreviewing] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => { listReasons("sales_order").then(setReasons).catch(() => setReasons([])); }, []);
  const changes = useMemo(() => rows.flatMap((r) => FIELDS.filter((f) => Math.abs(r[f] - r.orig[f]) > EPS)
    .map((f) => ({ product_id: r.product_id, field: f, to: r[f] }))), [rows]);
  const hasChange = changes.length > 0;
  useEffect(() => { if (!manualReason) setReason(autoReason(changes)); }, [changes, manualReason]);
  const body = useMemo(() => ({ doc_type: "sales_order", doc_id: order.id, reason_code: reason, changes }), [order.id, reason, changes]);

  useEffect(() => {
    if (!hasChange) { setPreview(null); setError(""); return undefined; }
    let alive = true;
    setPreviewing(true);
    const t = setTimeout(() => previewAmendment(body)
      .then((pv) => { if (alive) { setPreview(pv); setError(""); } })
      .catch((e) => { if (alive) { setPreview(null); setError(errText(e, "Gagal menghitung dampak.")); } })
      .finally(() => { if (alive) setPreviewing(false); }), 400);
    return () => { alive = false; clearTimeout(t); };
  }, [body, hasChange]);

  const noteMin = Number(preview?.policy?.require_note_above || 0);
  const noteRequired = noteMin > 0 && Math.abs(Number(preview?.impact?.delta || 0)) >= noteMin;
  const canSubmit = reason && preview && !error && !previewing && !busy && !(noteRequired && !note.trim());
  const setField = (i, f, v) => setRows((arr) => arr.map((r, j) => (j === i ? { ...r, [f]: v } : r)));

  const submit = async () => {
    if (!canSubmit) return;
    setBusy(true); setError("");
    try { setResult(await proposeAmendment({ ...body, note: note.trim(), attachments: [] })); }
    catch (e) { setError(errText(e, "Gagal mengirim koreksi.")); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-[140] flex flex-col bg-[#F2F2F7]" data-testid="m-amd-sheet">
      <div className="m-subpage-head">
        <button className="m-subpage-back" onClick={() => onClose(!!result)} data-testid="m-amd-close"><ArrowLeft size={17} /> {result ? "Tutup" : "Batal"}</button>
        <span className="m-subpage-title">Koreksi {order.number}</span>
      </div>
      {result ? <Result result={result} onClose={onClose} /> : (<>
        <div className="flex-1 space-y-3 overflow-y-auto p-3 pb-28">
          <div className="m-card p-3 text-[12px]" data-testid="m-amd-order">
            <p className="font-bold">{order.customer_name}</p>
            <p className="m-muted">Nilai sekarang <b className="tabular-nums text-[#1C1C1E]">{formatCurrency(order.grand_total ?? order.total_amount)}</b> · koreksi jadi dokumen amandemen bernomor.</p>
          </div>
          {rows.map((r, i) => <ItemRow key={r.product_id} row={r} onChange={(f, v) => setField(i, f, v)} onReset={() => setRows((a) => a.map((x, j) => (j === i ? { ...x, ...x.orig } : x)))} />)}
          <div className="m-card p-3" data-testid="m-amd-reasons">
            <p className="mb-2 text-[11.5px] font-semibold">Alasan {!manualReason && hasChange && <span className="font-normal m-muted">· dipilih otomatis</span>}</p>
            <div className="flex flex-wrap gap-1.5">
              {reasons.map((r) => (
                <button key={r.code} onClick={() => { setReason(r.code); setManualReason(true); }} data-testid={`m-amd-reason-${r.code}`}
                  className={`rounded-full border px-3 py-1.5 text-[11.5px] font-semibold ${reason === r.code ? "border-[#0058CC] bg-[#0058CC] text-white" : "border-[#E5E5EA] bg-white"}`}>{r.label}</button>
              ))}
            </div>
          </div>
          <textarea rows="2" className="field" value={note} onChange={(e) => setNote(e.target.value)} data-testid="m-amd-note"
            placeholder={noteRequired ? "Penjelasan wajib (koreksi melewati ambang)" : "Catatan (opsional)"} />
          <Impact preview={preview} previewing={previewing} error={error} hasChange={hasChange} />
        </div>
        <div className="fixed inset-x-0 bottom-0 border-t border-[#E5E5EA] bg-white p-3" style={{ paddingBottom: "calc(12px + env(safe-area-inset-bottom))" }}>
          <button className="primary-button w-full py-3" disabled={!canSubmit} onClick={submit} data-testid="m-amd-submit">
            {busy ? "Mengirim…" : hasChange ? "Ajukan koreksi" : "Ubah angka dulu"}
          </button>
        </div>
      </>)}
    </div>
  );
}
