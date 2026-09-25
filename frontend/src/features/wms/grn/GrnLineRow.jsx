import { useState } from "react";
import { BookPlus, CheckCircle2, Pencil, Trash2 } from "lucide-react";
import { KNSelect } from "../../../components/KNSelect";
import { LineDoubtRow, writtenQty } from "./GrnOcrBits";
import { grnApi } from "./grnApi";

export const tgtKey = (t) => (t ? (t.type === "po_task" ? `po_task:${t.task_id}` : `mko_step:${t.mko_id}:${t.step_seq}`) : "");
export const tgtBody = (k) => {
  if (!k) return null;
  const [type, a, b] = k.split(":");
  return type === "po_task" ? { type, task_id: a } : { type, mko_id: a, step_seq: Number(b) };
};
export const ROLE_OPTIONS = [{ value: "output", label: "Output" }, { value: "byproduct", label: "Barang sisa" }];
const num = (v) => (v === "" || v == null ? null : Number(v));
const VIA = { profile: "riwayat SJ mitra", supplier_sku: "kode barang supplier", supplier_name: "nama barang supplier",
  internal_name: "nama internal KN (cadangan)", supplier_color: "warna supplier", supplier_color_code: "kode warna supplier", internal_color: "warna internal" };
const parseRolls = (text, unit, prev, lot) => text.split(/[\n;]+|,(?!\d{1,2}\b)/).map((x) => x.trim()).filter(Boolean)
  .map((x, i) => ({ length: Number(x.replace(",", ".")), length_unit: unit, lot: prev[i]?.lot || lot, grade: prev[i]?.grade || "" }))
  .filter((r) => r.length > 0);
const COLS = 14;

function lineState(ln) {
  const uom = ln.checks?.uom;
  const doubt = ["ambiguous", "mismatch"].includes(ln.checks?.qty_parse);
  const unchecked = ln.read?.source === "ocr" && !ln.verified;
  if (ln.decision === "reject_line") return ["Ditolak", "bg-[#F2F2F7] text-[#6B6B73]"];
  if (!ln.is_non_stock && !ln.target) return ["Pilih target", "bg-[#FDECEC] text-[#B4231F]"];
  if (doubt) return ["Angka ragu", "bg-[#FDECEC] text-[#B4231F]"];
  if (ln.role === "") return ["Output / sisa?", "bg-[#FDECEC] text-[#B4231F]"];
  if (!ln.is_non_stock && uom === "uom_unknown") return ["Satuan?", "bg-[#FDECEC] text-[#B4231F]"];
  if (unchecked) return ["Belum dicek", "bg-[#FFF6E5] text-[#B26A00]"];
  return [ln.is_non_stock ? "Non-stok" : "Siap", "bg-[#E7F6F3] text-[#0F766E]"];
}

/** Nama & warna di SJ = VERSI SUPPLIER; tampilkan jembatan ke produk KN dan dasar pencocokannya. */
function MappingCaption({ ln }) {
  const v = ln.match?.via || {};
  const how = [VIA[v.name_via], VIA[v.color_via]].filter(Boolean).join(" + ");
  const sup = [ln.read?.description, ln.read?.color].filter(Boolean).join(" · ");
  return (
    <span data-testid={`grn-line-mapping-${ln.line_no}`} className="mt-0.5 block text-[10px] leading-snug text-[#6B6B73]">
      SJ: <span className="font-mono">{sup || "-"}</span> → KN: <b className="text-[#1C1C1E]">{ln.target.product_name}</b>
      {ln.match?.method === "manual" ? " · dipilih manual" : how ? ` · via ${how}` : ln.match?.method === "single_line" ? " · satu-satunya baris PO" : ""}
    </span>
  );
}

function CatalogRow({ grn, ln, onDone }) {
  const [sku, setSku] = useState(ln.read?.item_code || "");
  const [name, setName] = useState(ln.read?.description || "");
  const [msg, setMsg] = useState("");
  const inp = "rounded border border-[#E5E5EA] px-1.5 py-1 text-[11px] focus:border-[#0058CC] focus:outline-none";
  const save = async () => {
    try {
      const r = await grnApi.saveCatalog(grn.id, ln.line_no, { expected_version: grn.version, supplier_sku: sku.trim(), supplier_item_name: name.trim() });
      setMsg(r.existing ? "Sudah ada di Katalog Supplier." : "Tersimpan ke Katalog Supplier — SJ berikutnya dikenali lewat kode/nama ini.");
      setTimeout(onDone, 1500);
    } catch (e) { const dt = e?.response?.data?.detail; setMsg(typeof dt === "string" ? dt : dt?.message || "Gagal menyimpan."); }
  };
  return (
    <tr data-testid={`grn-line-catalog-form-${ln.line_no}`} className="bg-[#F6F3FD] text-[11px]">
      <td />
      <td colSpan={COLS - 1} className="px-2 py-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">Simpan ke Katalog Supplier untuk {ln.target.product_name}:</span>
          <input data-testid={`grn-catalog-sku-${ln.line_no}`} className={`${inp} w-40 font-mono`} placeholder="Kode barang supplier" value={sku} onChange={(e) => setSku(e.target.value)} />
          <input data-testid={`grn-catalog-name-${ln.line_no}`} className={`${inp} w-64`} placeholder="Nama barang versi supplier" value={name} onChange={(e) => setName(e.target.value)} />
          <button data-testid={`grn-catalog-save-${ln.line_no}`} disabled={!sku.trim()} className="primary-button !py-1 disabled:opacity-40" onClick={save}>Simpan</button>
          <button className="text-[#6B6B73]" onClick={onDone}>Batal</button>
          {msg && <span data-testid={`grn-catalog-msg-${ln.line_no}`} className="text-[10.5px] text-[#6B4FBB]">{msg}</span>}
        </div>
      </td>
    </tr>
  );
}

/** Ubah hasil baca per baris: OCR hanya usulan — semua isian bisa dikoreksi manusia. */
function LineEditRow({ ln, gradeOptions, onSave, onCancel }) {
  const d = ln.declared || {};
  const [f, setF] = useState({ item_code: ln.read?.item_code || "", description: ln.read?.description || "", po_ref: ln.read?.po_ref || "",
    qty: d.qty ?? "", unit: d.unit || "", rolls: d.rolls ?? "", weight_kg: d.weight_kg ?? "", grade: d.grade || "", lot: d.lot || "", is_non_stock: !!ln.is_non_stock,
    pl: (ln.expected_rolls || []).map((r) => r.length ?? "").join("\n"), pl_unit: (ln.expected_rolls || [])[0]?.length_unit || "" });
  const plBefore = (ln.expected_rolls || []).map((r) => r.length ?? "").join("\n");
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e?.target ? (e.target.type === "checkbox" ? e.target.checked : e.target.value) : e }));
  const inp = "w-full rounded border border-[#E5E5EA] px-1.5 py-1 text-[11px] focus:border-[#0058CC] focus:outline-none";
  const n = ln.line_no;
  const save = () => onSave({ item_code: f.item_code, description: f.description, po_ref: f.po_ref, is_non_stock: f.is_non_stock,
    declared: { qty: num(f.qty), unit: f.unit, rolls: num(f.rolls), weight_kg: num(f.weight_kg), weight_basis: d.weight_basis || null, grade: f.grade, lot: f.lot },
    ...(f.pl !== plBefore ? { expected_rolls: parseRolls(f.pl, f.pl_unit, ln.expected_rolls || [], f.lot) } : {}) });
  return (
    <tr data-testid={`grn-line-edit-form-${n}`} className="bg-[#F4F8FF] text-[11px]">
      <td className="px-2 py-2 align-top font-semibold">{n}</td>
      <td colSpan={COLS - 1} className="px-2 py-2">
        <div className="grid grid-cols-6 gap-2">
          <input data-testid={`grn-edit-code-${n}`} className={inp} placeholder="Kode" value={f.item_code} onChange={set("item_code")} />
          <input data-testid={`grn-edit-desc-${n}`} className={`${inp} col-span-2`} placeholder="Deskripsi" value={f.description} onChange={set("description")} />
          <input data-testid={`grn-edit-po-${n}`} className={inp} placeholder="PO di baris" value={f.po_ref} onChange={set("po_ref")} />
          <input data-testid={`grn-edit-qty-${n}`} type="number" className={`${inp} font-mono`} placeholder="Qty" value={f.qty} onChange={set("qty")} />
          <input data-testid={`grn-edit-unit-${n}`} className={inp} placeholder="Satuan (yard/meter/kg)" value={f.unit} onChange={set("unit")} />
          <input data-testid={`grn-edit-rolls-${n}`} type="number" className={inp} placeholder="Roll" value={f.rolls} onChange={set("rolls")} />
          <input data-testid={`grn-edit-kg-${n}`} type="number" className={inp} placeholder="Kg" value={f.weight_kg} onChange={set("weight_kg")} />
          <KNSelect data-testid={`grn-edit-grade-${n}`} value={f.grade} onValueChange={set("grade")} options={gradeOptions} placeholder="Grade" searchable={false} />
          <input data-testid={`grn-edit-lot-${n}`} className={inp} placeholder="Lot" value={f.lot} onChange={set("lot")} />
          <label className="flex items-center gap-1 font-semibold"><input data-testid={`grn-edit-nonstock-${n}`} type="checkbox" checked={f.is_non_stock} onChange={set("is_non_stock")} /> Non-stok</label>
          <div className="col-span-4 flex gap-2">
            <textarea data-testid={`grn-edit-pl-${n}`} rows={2} className={`${inp} font-mono`} placeholder="Packing list: panjang per roll (satu per baris atau pisahkan dengan ;)" value={f.pl} onChange={set("pl")} />
            <input data-testid={`grn-edit-pl-unit-${n}`} className={`${inp} !w-20`} placeholder="yd / m" value={f.pl_unit} onChange={set("pl_unit")} />
          </div>
          <div className="col-span-2 flex items-center justify-end gap-2">
            <button data-testid={`grn-edit-cancel-${n}`} className="text-[11px] font-semibold text-[#6B6B73]" onClick={onCancel}>Batal</button>
            <button data-testid={`grn-edit-save-${n}`} className="primary-button !py-1" onClick={save}>Simpan & tandai dicek</button>
          </div>
        </div>
        {ln.read?.source === "ocr" && <p className="mt-1 text-[10px] text-[#6B6B73]">Dibaca otomatis: <span className="font-mono">{writtenQty(ln) || "-"}</span>{ln.read?.row_text ? <> · baris tercetak <span className="font-mono">"{ln.read.row_text}"</span></> : null}</p>}
      </td>
    </tr>
  );
}

export default function GrnLineRow({ grn, ln, targets, gradeOptions, run }) {
  const [edit, setEdit] = useState(false);
  const [cat, setCat] = useState(false);
  const d = ln.declared || {};
  const [status, tone] = lineState(ln);
  const patch = (body) => run(() => grnApi.patch(grn.id, `lines/${ln.line_no}`, { expected_version: grn.version, ...body }));
  const n = ln.line_no;
  const ocr = ln.read?.source === "ocr";
  const isMko = ln.target?.type === "mko_step";
  if (edit) return <LineEditRow ln={ln} gradeOptions={gradeOptions} onCancel={() => setEdit(false)} onSave={async (b) => { if (await patch(b)) setEdit(false); }} />;
  return (<>
    <tr data-testid={`grn-line-row-${n}`} className={`border-t border-[#EFF0F2] text-[11px] ${ocr && !ln.verified ? "bg-[#FFFCF5]" : ""}`}>
      <td className="px-2 py-1.5">{n}</td>
      <td className="px-2">{ln.read?.item_code}</td>
      <td className="px-2">{ln.read?.description}</td>
      <td className="px-2 font-mono">{ln.read?.po_ref}</td>
      <td className="px-2 font-mono text-[10.5px] text-[#6B6B73]" data-testid={`grn-line-written-${n}`}>{writtenQty(ln) || "-"}</td>
      <td className="px-2 font-mono tabular-nums" data-testid={`grn-line-qty-${n}`}>{d.qty ?? "-"}</td>
      <td className="px-2">{d.unit}</td>
      <td className="px-2 tabular-nums">{d.rolls ?? "-"}</td>
      <td className="px-2 tabular-nums">{d.weight_kg ?? "-"}{d.weight_basis ? ` (${d.weight_basis === "net" ? "netto" : d.weight_basis === "gross" ? "bruto" : "?"})` : ""}</td>
      <td className="px-2">{d.grade}</td>
      <td className="px-2">{d.lot}</td>
      <td className="px-2">
        <KNSelect data-testid={`grn-line-target-${n}`} value={tgtKey(ln.target)} onValueChange={(v) => patch({ target: tgtBody(v) })}
          options={targets.map((t) => ({ value: tgtKey(t), label: t.type === "po_task" ? `${t.po_number} · ${t.product_name}` : `${t.mko_number}/${t.step_seq} · ${t.product_name}` }))} placeholder="-" />
        {isMko && !ln.is_non_stock && (
          <div className={`mt-1 rounded ${ln.role === "" ? "ring-1 ring-[#E5B34A]" : ""}`}>
            <KNSelect data-testid={`grn-line-role-${n}`} value={ln.role || ""} onValueChange={(v) => patch({ role: v })} options={ROLE_OPTIONS} placeholder="Output atau barang sisa?" searchable={false} />
          </div>
        )}
        {ocr && ln.target && <MappingCaption ln={ln} />}
        {(ln.expected_rolls || []).length > 0 && (
          <span data-testid={`grn-line-pl-${n}`} className="mt-0.5 block text-[10px] font-semibold text-[#0058CC]">
            Packing list: {ln.expected_rolls.length} roll · {Math.round(ln.expected_rolls.reduce((a, r) => a + (r.length || 0), 0) * 100) / 100} {ln.expected_rolls[0]?.length_unit || ""}
          </span>
        )}
        {ln.checks?.role_question && ln.role === "" && <span data-testid={`grn-line-role-question-${n}`} className="block text-[10px] text-[#B26A00]">{ln.checks.role_question}</span>}
        {ln.converted && <span className="text-[10px] text-[#6B6B73]">= {ln.converted.qty} {ln.converted.unit}</span>}
        {ln.checks?.uom_message && <span className="block text-[10px] text-[#B4231F]">{ln.checks.uom_message}</span>}
      </td>
      <td className="px-2">
        <span data-testid={`grn-line-status-${n}`} className={`whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-semibold ${tone}`}>{status}</span>
        {ln.corrected && <span data-testid={`grn-line-corrected-${n}`} className="mt-0.5 block text-[9.5px] font-semibold text-[#0058CC]">Dikoreksi: {(ln.corrected_fields || []).join(", ")}</span>}
      </td>
      <td className="whitespace-nowrap px-2">
        {ocr && !ln.verified && ln.decision !== "reject_line" && (
          <button data-testid={`grn-line-verify-${n}`} className="mr-2 inline-flex items-center gap-0.5 text-[10.5px] font-semibold text-[#0F766E]" onClick={() => patch({ verified: true })}><CheckCircle2 size={12} /> Sesuai foto</button>
        )}
        <button data-testid={`grn-line-edit-${n}`} className="mr-2" aria-label="Ubah baris" onClick={() => setEdit(true)}><Pencil size={12} className="text-[#0058CC]" /></button>
        {grn.partner_type === "supplier" && ocr && ln.target?.type === "po_task" && !["supplier_sku", "profile"].includes(ln.match?.via?.name_via) && (
          <button data-testid={`grn-line-catalog-${n}`} className="mr-2" aria-label="Simpan ke Katalog Supplier" title="Simpan nama barang versi supplier ke Katalog Supplier" onClick={() => setCat((x) => !x)}><BookPlus size={12} className="text-[#6B4FBB]" /></button>
        )}
        <button data-testid={`grn-line-toggle-${n}`} className="text-[10.5px] font-semibold text-[#0058CC]"
          onClick={() => patch({ decision: ln.decision === "reject_line" ? "accept" : "reject_line" })}>
          {ln.decision === "reject_line" ? "Terima" : "Tolak"}
        </button>
        <button data-testid={`grn-line-delete-${n}`} className="ml-2" aria-label="Hapus baris"
          onClick={() => run(() => grnApi.del(grn.id, `lines/${n}`, { expected_version: grn.version }))}><Trash2 size={12} className="text-[#B4231F]" /></button>
      </td>
    </tr>
    <LineDoubtRow ln={ln} colSpan={COLS - 1} onPick={(declared) => patch({ declared })} />
    {cat && <CatalogRow grn={grn} ln={ln} onDone={() => setCat(false)} />}
  </>);
}

/** Ringkasan validasi manual: OCR hanya baca cepat; keputusan tetap di pengguna. */
export function VerifySummary({ grn }) {
  const ocrLines = (grn.lines || []).filter((ln) => ln.read?.source === "ocr" && ln.decision !== "reject_line");
  const dnOcr = grn.dn?.source === "ocr";
  if (!ocrLines.length && !dnOcr) return null;
  const done = ocrLines.filter((ln) => ln.verified).length;
  const all = done === ocrLines.length && (!dnOcr || grn.dn?.verified);
  return (
    <div data-testid="grn-verify-summary" className={`rounded-xl border p-3 text-[11px] ${all ? "border-[#BFE5DC] bg-[#F0FAF7] text-[#0F766E]" : "border-[#F1D08A] bg-[#FFF9EC] text-[#8A5300]"}`}>
      <p className="font-semibold">{all ? "Semua hasil baca sudah dicek pengguna." : "Hasil baca otomatis hanya usulan — cocokkan dengan foto, perbaiki bila salah."}</p>
      <p className="mt-0.5">
        Kepala SJ: <b data-testid="grn-verify-dn">{!dnOcr || grn.dn?.verified ? "dikonfirmasi" : "belum dikonfirmasi"}</b> · Baris dicek:{" "}
        <b data-testid="grn-verify-count">{done}/{ocrLines.length}</b>. Hitung fisik baru bisa dimulai setelah semuanya dicek.
      </p>
    </div>
  );
}
