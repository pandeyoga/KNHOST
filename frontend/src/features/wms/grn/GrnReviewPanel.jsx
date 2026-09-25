import { useEffect, useState } from "react";
import { CheckCircle2, Plus, Save } from "lucide-react";
import { KNSelect } from "../../../components/KNSelect";
import useDomainEnums from "../../../hooks/useDomainEnums";
import { askReason } from "../../../services/confirmService";
import { ErrorBox, Field, inputCls } from "./GrnBits";
import GrnPhotoPane from "./GrnPhotoPane";
import GrnLineRow, { ROLE_OPTIONS, VerifySummary, tgtBody, tgtKey } from "./GrnLineRow";
import { GrnDraftActions, GrnExtractionNotice } from "./GrnOcrBits";
import { errText, grnApi } from "./grnApi";

const EMPTY = { item_code: "", description: "", po_ref: "", qty: "", unit: "", rolls: "", weight_kg: "", weight_basis: "", grade: "", lot: "", target: "", is_non_stock: false, role: "output" };
const num = (v) => (v === "" || v == null ? null : Number(v));

function DnForm({ grn, run, busy }) {
  const [dn, setDn] = useState(grn.dn || {});
  const [dirty, setDirty] = useState(false);
  // Isian yang belum disimpan TIDAK ditimpa saat dokumen berubah (mis. hasil "Isi manual").
  useEffect(() => { if (!dirty) setDn(grn.dn || {}); }, [grn.dn, dirty]);
  const set = (k) => (e) => { setDirty(true); setDn((d) => ({ ...d, [k]: e.target.value })); };
  const hd = new Set((grn.extraction?.header_diff || []).map((d) => d.field));
  const warn = (f) => (hd.has(f) ? " !border-[#E5B34A] !bg-[#FFF6E0]" : "");
  const save = async () => { if (await run(() => grnApi.patch(grn.id, "dn", { expected_version: grn.version, number: dn.number || "", date: dn.date || "",
    supplier_name_printed: dn.supplier_name_printed || "", recipient_name: dn.recipient_name || "", vehicle_plate: dn.vehicle_plate || "",
    po_refs: String(dn.po_refs_text ?? (dn.po_refs || []).join(", ")).split(",").map((s) => s.trim()).filter(Boolean) }))) setDirty(false); };
  const pending = grn.dn?.source === "ocr" && !grn.dn?.verified;
  return (
    <div data-testid="grn-dn-form" className={`grid grid-cols-2 gap-2 rounded-xl border p-3 ${pending ? "border-[#F1D08A] bg-[#FFFCF5]" : "border-[#EFF0F2]"}`}>
      {pending && <p data-testid="grn-dn-pending" className="col-span-2 text-[11px] font-semibold text-[#8A5300]">Kepala SJ diisi dari baca otomatis — cocokkan dengan foto, perbaiki bila salah, lalu konfirmasi.</p>}
      <Field label="Nomor surat jalan *"><input data-testid="grn-dn-number" className={`${inputCls} font-mono${warn("dn_number")}`} value={dn.number || ""} onChange={set("number")} /></Field>
      <Field label="Tanggal kirim"><input data-testid="grn-dn-date" type="date" className={`${inputCls}${warn("dn_date")}`} value={dn.date || ""} onChange={set("date")} /></Field>
      <Field label="Nama pengirim tercetak"><input data-testid="grn-dn-supplier-printed" className={inputCls} value={dn.supplier_name_printed || ""} onChange={set("supplier_name_printed")} /></Field>
      <Field label="Penerima"><input data-testid="grn-dn-recipient" className={inputCls} value={dn.recipient_name || ""} onChange={set("recipient_name")} /></Field>
      <Field label="Nomor PO di SJ (pisah koma)"><input data-testid="grn-dn-po-refs" className={`${inputCls}${warn("po_refs")}`} value={dn.po_refs_text ?? (dn.po_refs || []).join(", ")} onChange={set("po_refs_text")} /></Field>
      <Field label="Plat kendaraan"><input data-testid="grn-dn-plate" className={inputCls} value={dn.vehicle_plate || ""} onChange={set("vehicle_plate")} /></Field>
      <div className="col-span-2 flex items-center justify-between gap-2">
        <span className="text-[10.5px] text-[#0F766E]" data-testid="grn-dn-verified">{grn.dn?.verified ? <><CheckCircle2 size={11} className="mr-0.5 inline" />Dikonfirmasi {grn.dn.verified_by}{(grn.dn.corrected_fields || []).length ? ` · dikoreksi: ${grn.dn.corrected_fields.join(", ")}` : ""}</> : ""}</span>
        <button data-testid="grn-dn-save" className={pending ? "primary-button" : "secondary-button"} disabled={busy} onClick={save}>{pending ? <><CheckCircle2 size={13} /> Konfirmasi kepala SJ</> : <><Save size={13} /> Simpan kepala SJ</>}</button>
      </div>
    </div>
  );
}

function LineForm({ grn, targets, gradeOptions, run }) {
  const [f, setF] = useState(EMPTY);
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e?.target ? (e.target.type === "checkbox" ? e.target.checked : e.target.value) : e }));
  const add = () => run(async () => {
    const r = await grnApi.post(grn.id, "lines", { expected_version: grn.version, item_code: f.item_code, description: f.description, po_ref: f.po_ref,
      is_non_stock: f.is_non_stock, target: f.is_non_stock ? null : tgtBody(f.target), role: f.role || "output",
      declared: { qty: num(f.qty), unit: f.unit, rolls: num(f.rolls), weight_kg: num(f.weight_kg), weight_basis: f.weight_basis || null, grade: f.grade, lot: f.lot } });
    setF(EMPTY);
    return r;
  });
  const opts = targets.map((t) => ({ value: tgtKey(t), label: t.type === "po_task" ? `${t.po_number} · ${t.product_name} (${t.unit})` : `${t.mko_number} langkah ${t.step_seq} · ${t.product_name}` }));
  return (
    <div data-testid="grn-line-form" className="grid grid-cols-6 gap-2 rounded-xl border border-dashed border-[#CFE0FF] bg-[#F9FBFF] p-3">
      <Field label="Kode"><input data-testid="grn-line-code" className={inputCls} value={f.item_code} onChange={set("item_code")} /></Field>
      <div className="col-span-2"><Field label="Deskripsi"><input data-testid="grn-line-desc" className={inputCls} value={f.description} onChange={set("description")} /></Field></div>
      <Field label="PO di baris"><input data-testid="grn-line-po-ref" className={inputCls} value={f.po_ref} onChange={set("po_ref")} /></Field>
      <Field label="Qty tertulis"><input data-testid="grn-line-qty" type="number" className={`${inputCls} font-mono`} value={f.qty} onChange={set("qty")} /></Field>
      <Field label="Satuan"><input data-testid="grn-line-unit" placeholder="yd / m / kg" className={inputCls} value={f.unit} onChange={set("unit")} /></Field>
      <Field label="Roll"><input data-testid="grn-line-rolls" type="number" className={inputCls} value={f.rolls} onChange={set("rolls")} /></Field>
      <Field label="Kg"><input data-testid="grn-line-kg" type="number" className={inputCls} value={f.weight_kg} onChange={set("weight_kg")} /></Field>
      <Field label="Bruto/Netto">
        <KNSelect data-testid="grn-line-basis" value={f.weight_basis} onValueChange={set("weight_basis")} searchable={false}
          options={[{ value: "net", label: "Netto" }, { value: "gross", label: "Bruto" }, { value: "unknown", label: "Tidak tertulis" }]} placeholder="-" />
      </Field>
      <Field label="Grade"><KNSelect data-testid="grn-line-grade" value={f.grade} onValueChange={set("grade")} options={gradeOptions} placeholder="-" searchable={false} /></Field>
      <Field label="Lot"><input data-testid="grn-line-lot" className={inputCls} value={f.lot} onChange={set("lot")} /></Field>
      <label className="flex items-end gap-1 pb-2 text-[11px] font-semibold"><input data-testid="grn-line-nonstock" type="checkbox" checked={f.is_non_stock} onChange={set("is_non_stock")} /> Non-stok</label>
      {grn.partner_type === "makloon" && <Field label="Peran"><KNSelect data-testid="grn-line-role" value={f.role} onValueChange={set("role")} options={ROLE_OPTIONS} searchable={false} /></Field>}
      <div className={grn.partner_type === "makloon" ? "col-span-4" : "col-span-5"}><Field label="Target (tugas PO / langkah MKO)">
        <KNSelect data-testid="grn-line-target" value={f.target} onValueChange={set("target")} options={opts} placeholder={f.is_non_stock ? "Tidak perlu target" : "Pilih target…"} disabled={f.is_non_stock} />
      </Field></div>
      <div className="flex items-end"><button data-testid="grn-line-add" className="primary-button w-full justify-center" onClick={add}><Plus size={13} /> Baris</button></div>
    </div>
  );
}

export default function GrnReviewPanel({ grn, onChange, canReview }) {
  const [targets, setTargets] = useState([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const { options } = useDomainEnums();
  const gradeOptions = options("grade");
  useEffect(() => { if (canReview) grnApi.targets(grn.id).then(setTargets).catch(() => setTargets([])); }, [grn.id, canReview]);
  const run = async (fn) => {
    setErr(""); setBusy(true);
    try { const r = await fn(); onChange(r?.grn || r); return true; } catch (e) { setErr(errText(e)); return false; } finally { setBusy(false); }
  };
  const reject = async () => {
    const reason = await askReason({ title: "Tolak kedatangan ini?", message: "Barang tidak diterima di pintu gudang.", reasonLabel: "Alasan penolakan", confirmLabel: "Tolak" });
    if (reason) run(() => grnApi.post(grn.id, "reject", { expected_version: grn.version, reason }));
  };
  return (
    <div className="grid gap-3 lg:grid-cols-[minmax(0,4fr)_minmax(0,8fr)]" data-testid="grn-review-panel">
      <GrnPhotoPane grn={grn} />
      <div className="space-y-3">
        <ErrorBox text={err} />
        {["draft", "reading"].includes(grn.status) && <GrnDraftActions grn={grn} run={run} busy={busy} />}
        {grn.status !== "draft" && <GrnExtractionNotice grn={grn} />}
        {grn.status === "review" && canReview && <VerifySummary grn={grn} />}
        {canReview && !["draft", "reading"].includes(grn.status) && <DnForm grn={grn} run={run} busy={busy} />}
        {grn.status === "review" && canReview && (<>
          <div className="overflow-x-auto rounded-xl border border-[#EFF0F2]">
            <table className="w-full text-left" data-testid="grn-lines-table">
              <thead className="bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73]">
                <tr>{["No", "Kode", "Deskripsi", "PO", "Tertulis", "Qty", "Satuan", "Roll", "Kg", "Grade", "Lot", "Target", "Status", ""].map((h) => <th key={h} className="px-2 py-1.5">{h}</th>)}</tr>
              </thead>
              <tbody>{(grn.lines || []).map((ln) => <GrnLineRow key={ln.line_no} grn={grn} ln={ln} targets={targets} gradeOptions={gradeOptions} run={run} />)}</tbody>
            </table>
            {!(grn.lines || []).length && <p className="p-3 text-[11px] text-[#6B6B73]">Belum ada baris. Salin baris barang dari surat jalan di bawah.</p>}
          </div>
          <LineForm grn={grn} targets={targets} gradeOptions={gradeOptions} run={run} />
          <div className="flex justify-end gap-2">
            <button data-testid="grn-reject" className="secondary-button" onClick={reject}>Tolak kedatangan</button>
            <button data-testid="grn-start-count" className="primary-button" disabled={busy} onClick={() => run(() => grnApi.post(grn.id, "start-count", { expected_version: grn.version }))}>Mulai hitung fisik</button>
          </div>
        </>)}
      </div>
    </div>
  );
}
