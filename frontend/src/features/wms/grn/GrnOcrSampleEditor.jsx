import { useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import { ErrorBox, inputCls } from "./GrnBits";
import { errText, sampleApi } from "./grnApi";

const UNITS = ["yard", "meter", "kg", "pcs"];
const blank = () => ({ description: "", qty: "", unit: "yard", rolls: "", po_ref: "", is_non_stock: false });

/** Ubah kunci jawaban sampel: nomor & tanggal SJ + baris (qty, satuan, roll, PO). */
export default function GrnOcrSampleEditor({ sample, onClose, onSaved }) {
  const a = sample.answer || {};
  const [label, setLabel] = useState(sample.label || "");
  const [dn, setDn] = useState(a.dn_number || "");
  const [date, setDate] = useState(a.dn_date || "");
  const [lines, setLines] = useState((a.lines || []).map((l) => ({ ...blank(), ...l, qty: l.qty ?? "", rolls: l.rolls ?? "", po_ref: l.po_ref || "" })));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (i, k, v) => setLines((ls) => ls.map((l, j) => (j === i ? { ...l, [k]: v } : l)));
  const save = async () => {
    setBusy(true); setErr("");
    try { onSaved(await sampleApi.patch(sample.id, { label, answer: { dn_number: dn, dn_date: date, supplier_name: a.supplier_name, lines } })); } catch (e) { setErr(errText(e)); } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center bg-black/30 sm:items-center sm:p-4" data-testid="ocr-sample-editor">
      <div className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-t-2xl bg-white shadow-xl sm:rounded-2xl">
        <div className="flex items-center justify-between border-b border-[#EFF0F2] px-4 py-3">
          <div><p className="text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Kunci jawaban</p><h3 className="text-[15px] font-bold">Apa yang BENAR tertulis di SJ ini?</h3></div>
          <button onClick={onClose} aria-label="Tutup" data-testid="ocr-sample-editor-close"><X size={16} /></button>
        </div>
        <div className="space-y-3 p-4 text-[11px]">
          <div className="grid gap-2 sm:grid-cols-3">
            <label className="sm:col-span-3"><span className="font-semibold">Nama sampel</span><input data-testid="ocr-sample-label" className={inputCls} value={label} onChange={(e) => setLabel(e.target.value)} /></label>
            <label className="sm:col-span-2"><span className="font-semibold">Nomor SJ</span><input data-testid="ocr-sample-dn" className={`${inputCls} font-mono`} value={dn} onChange={(e) => setDn(e.target.value)} /></label>
            <label><span className="font-semibold">Tanggal SJ</span><input data-testid="ocr-sample-date" type="date" className={inputCls} value={date} onChange={(e) => setDate(e.target.value)} /></label>
          </div>
          <div className="space-y-2" data-testid="ocr-sample-lines">
            <div className="hidden grid-cols-[1fr_90px_90px_60px_130px_50px_24px] gap-1 text-[10px] font-bold uppercase text-[#6B6B73] sm:grid"><span>Barang</span><span>Qty</span><span>Satuan</span><span>Roll</span><span>No. PO</span><span>Non-stok</span><span /></div>
            {lines.map((l, i) => (
              <div key={i} data-testid={`ocr-sample-line-${i}`} className="grid grid-cols-3 gap-1 rounded-lg border border-[#EFF0F2] p-2 sm:grid-cols-[1fr_90px_90px_60px_130px_50px_24px] sm:items-center sm:border-0 sm:p-0">
                <input className={`${inputCls} col-span-3 sm:col-span-1`} placeholder="Barang" value={l.description} onChange={(e) => set(i, "description", e.target.value)} />
                <input data-testid={`ocr-sample-line-qty-${i}`} type="number" inputMode="decimal" placeholder="Qty" className={`${inputCls} font-mono`} value={l.qty} onChange={(e) => set(i, "qty", e.target.value)} />
                <select data-testid={`ocr-sample-line-unit-${i}`} className={inputCls} value={l.unit} onChange={(e) => set(i, "unit", e.target.value)}>{UNITS.map((u) => <option key={u}>{u}</option>)}</select>
                <input type="number" inputMode="numeric" placeholder="Roll" className={`${inputCls} font-mono`} value={l.rolls} onChange={(e) => set(i, "rolls", e.target.value)} />
                <input className={`${inputCls} col-span-2 font-mono sm:col-span-1`} value={l.po_ref} placeholder="No. PO, mis. 7460/CST/0726" onChange={(e) => set(i, "po_ref", e.target.value)} />
                <label className="flex items-center justify-center gap-1 text-[10.5px]"><input type="checkbox" checked={l.is_non_stock} onChange={(e) => set(i, "is_non_stock", e.target.checked)} /><span className="sm:hidden">Non-stok</span></label>
                <button aria-label="Hapus baris" data-testid={`ocr-sample-line-remove-${i}`} className="col-span-3 flex items-center justify-end gap-1 text-[10.5px] text-[#B4231F] sm:col-span-1" onClick={() => setLines((ls) => ls.filter((_, j) => j !== i))}><Trash2 size={13} /><span className="sm:hidden">Hapus baris</span></button>
              </div>
            ))}
          </div>
          <button data-testid="ocr-sample-line-add" className="inline-flex items-center gap-1 font-semibold text-[#0058CC]" onClick={() => setLines((ls) => [...ls, blank()])}><Plus size={13} /> Tambah baris</button>
          <p className="text-[10.5px] text-[#6B6B73]">Isi PO hanya bila nomor PO tertulis di baris itu. Kosongkan tanggal bila memang tidak jelas di foto — field kosong tidak dinilai.</p>
          <ErrorBox text={err} />
        </div>
        <div className="flex justify-end gap-2 border-t border-[#EFF0F2] px-4 py-3">
          <button className="secondary-button" onClick={onClose}>Batal</button>
          <button className="primary-button" data-testid="ocr-sample-save" disabled={busy} onClick={save}>{busy ? "Menyimpan…" : "Simpan jawaban"}</button>
        </div>
      </div>
    </div>
  );
}
