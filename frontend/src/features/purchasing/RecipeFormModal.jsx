import { useState } from "react";
import MoneyInput from "@/components/MoneyInput";
import { GitBranch, X, Save, Calculator, ArrowRight } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import ProductSelect, { STAGE_LABELS } from "../../components/ProductSelect";
import MakloonSelect from "../../components/MakloonSelect";
import useProcessTypes from "../../hooks/useProcessTypes";
import { formatQty } from "../../utils/formatters";
import { overlayDismiss } from "@/utils/overlayDismiss";

const STAGE_OPTS = Object.entries(STAGE_LABELS).map(([value, label]) => ({ value, label }));
const TARIFF_UNITS = [{ value: "output", label: "per Output" }, { value: "input", label: "per Input" }, { value: "roll", label: "per Roll" }];
// UAT 24 Okt (audit UI tahap 2) — G4-23: nama manusia untuk variabel rumus (dulu snake_case mentah).
const RECIPE_VARS = [
  { code: "input_qty", label: "Jumlah bahan" },
  { code: "yield_factor", label: "Rendemen" },
  { code: "waste_pct", label: "Susut (%)" },
  { code: "byproduct_pct", label: "Barang sisa (%)" },
  { code: "gramasi", label: "Gramasi" },
  { code: "lebar", label: "Lebar" },
];

/** RecipeFormModal (M1) — buat/ubah resep konversi + preview forecast inline. */
export default function RecipeFormModal({ editTarget, makloons = [], selectedEntity, onClose, onSaved, onError }) {
  // FASE T (4a) — jenis proses dari registry hidup: `screen`/`rajut`/`pre_treatment`
  // dulu tidak ada di daftar hardcode, jadi resepnya tidak bisa dibuat dari layar ini.
  const { options: processOptions } = useProcessTypes();
  const PROC_OPTS = processOptions();
  const isEdit = !!editTarget;
  const [f, setF] = useState(() => ({
    name: editTarget?.name || "", process_type: editTarget?.process_type || "tenun",
    input_product_id: editTarget?.input_product_id || "", input_name: editTarget?.input_name || "", input_stage: editTarget?.input_stage || "yarn",
    output_product_id: editTarget?.output_product_id || "", output_name: editTarget?.output_name || "", output_stage: editTarget?.output_stage || "grey",
    byproduct_product_id: editTarget?.byproduct_product_id || "", byproduct_name: editTarget?.byproduct_name || "",
    yield_factor: editTarget?.yield_factor != null ? String(editTarget.yield_factor) : "1",
    waste_pct: editTarget?.waste_pct != null ? String(editTarget.waste_pct) : "0",
    byproduct_pct: editTarget?.byproduct_pct != null ? String(editTarget.byproduct_pct) : "0",
    default_makloon_id: editTarget?.default_makloon_id || "", default_makloon_name: editTarget?.default_makloon_name || "",
    // G4-23 — nol = kosong (dulu "0" memunculkan pratinjau "Rp 0" ganda di bawah dua isian).
    default_tariff: Number(editTarget?.default_tariff) ? String(editTarget.default_tariff) : "",
    tariff_unit: editTarget?.tariff_unit || "output",
    aux_cost_default: Number(editTarget?.aux_cost_default) ? String(editTarget.aux_cost_default) : "",
    formula: editTarget?.formula || "", notes: editTarget?.notes || "",
    entity_id: editTarget?.entity_id || (selectedEntity && selectedEntity !== "all" ? selectedEntity : ""),
  }));
  const [saving, setSaving] = useState(false);
  const [modalErr, setModalErr] = useState("");   // galat tampil di modal ini
  const [testQty, setTestQty] = useState("100");
  const [preview, setPreview] = useState(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const runForecast = async () => {
    try {
      const res = await axios.post(`${API}/process-recipes/forecast`, {
        input_qty: parseFloat(testQty) || 0, yield_factor: parseFloat(f.yield_factor) || 0,
        waste_pct: parseFloat(f.waste_pct) || 0, byproduct_pct: parseFloat(f.byproduct_pct) || 0, formula: f.formula,
      });
      setPreview(res.data);
    } catch (e) { setModalErr(e.response?.data?.detail || "Gagal menghitung forecast."); }
  };

  const save = async () => {
    if (!f.name.trim()) { setModalErr("Nama resep wajib diisi."); return; }
    if (!f.input_product_id || !f.output_product_id) { setModalErr("Produk input & output wajib dipilih."); return; }
    setSaving(true);
    const payload = {
      name: f.name, process_type: f.process_type,
      input_product_id: f.input_product_id, input_stage: f.input_stage,
      output_product_id: f.output_product_id, output_stage: f.output_stage,
      byproduct_product_id: f.byproduct_product_id,
      yield_factor: parseFloat(f.yield_factor) || 0, waste_pct: parseFloat(f.waste_pct) || 0,
      byproduct_pct: parseFloat(f.byproduct_pct) || 0, default_makloon_id: f.default_makloon_id,
      default_tariff: parseFloat(f.default_tariff) || 0, tariff_unit: f.tariff_unit,
      aux_cost_default: parseFloat(f.aux_cost_default) || 0, formula: f.formula, notes: f.notes, entity_id: f.entity_id,
    };
    try {
      if (isEdit) await axios.patch(`${API}/process-recipes/${editTarget.id}`, { data: payload });
      else await axios.post(`${API}/process-recipes`, payload);
      onSaved?.();
    } catch (e) { setModalErr(e.response?.data?.detail || "Gagal menyimpan resep."); setSaving(false); }
  };

  return (
    <div data-testid="recipe-form-modal" className="fixed inset-0 z-[160] flex items-center justify-center bg-black/50 p-4" {...overlayDismiss(onClose)}>
      <div className="flex max-h-[92vh] w-full max-w-[680px] flex-col overflow-hidden rounded-xl bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-[#EFF0F2] px-4 py-3">
          <h2 className="flex items-center gap-2 text-[15px] font-bold"><GitBranch size={16} className="text-[#0058CC]" /> {isEdit ? "Ubah Resep Konversi" : "Buat Resep Konversi"}</h2>
          <button className="icon-button" onClick={onClose} aria-label="Tutup"><X size={18} /></button>
        </div>
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Nama Resep" req><input data-testid="recipe-name-input" className="field" value={f.name} onChange={set("name")} placeholder="Tenun: Benang → Grey" /></Field>
            <Field label="Jenis Proses"><KNSelect data-testid="recipe-process-type" className="field" value={f.process_type} onValueChange={(v) => setF({ ...f, process_type: v })} options={PROC_OPTS} /></Field>
          </div>

          <div className="rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-3">
            <div className="grid grid-cols-[1fr_auto_1fr] items-end gap-2">
              {/* UAT 24 Okt (audit UI tahap 2) — G4-23: satu label per pemilih (dulu dua pemilih di bawah satu
                  label MAJUSCULE); gaya label sama dengan isian lain. */}
              <div className="space-y-1.5">
                <p className="text-[12px] font-semibold text-[#1C1C1E]">Bahan masuk</p>
                <Field label="Tahap bahan"><KNSelect data-testid="recipe-input-stage" className="field" value={f.input_stage} onValueChange={(v) => setF({ ...f, input_stage: v })} options={STAGE_OPTS} /></Field>
                <Field label="Produk bahan" req><ProductSelect triggerTestId="recipe-input-product" stage={f.input_stage} value={f.input_product_id} valueName={f.input_name}
                  onSelect={(p) => setF({ ...f, input_product_id: p.id, input_name: `${p.name} (${p.sku})` })} label="Pilih produk bahan…" /></Field>
              </div>
              <ArrowRight size={18} className="mb-2 text-[#0058CC]" />
              <div className="space-y-1.5">
                <p className="text-[12px] font-semibold text-[#1C1C1E]">Hasil</p>
                <Field label="Tahap hasil"><KNSelect data-testid="recipe-output-stage" className="field" value={f.output_stage} onValueChange={(v) => setF({ ...f, output_stage: v })} options={STAGE_OPTS} /></Field>
                <Field label="Produk hasil" req><ProductSelect triggerTestId="recipe-output-product" stage={f.output_stage} value={f.output_product_id} valueName={f.output_name}
                  onSelect={(p) => setF({ ...f, output_product_id: p.id, output_name: `${p.name} (${p.sku})` })} label="Pilih produk hasil…" /></Field>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <Field label="Rendemen (hasil per 1 bahan)"><input data-testid="recipe-yield" type="number" step="0.01" className="field" value={f.yield_factor} onChange={set("yield_factor")} /></Field>
            <Field label="Susut (%)"><input data-testid="recipe-waste" type="number" step="0.1" className="field" value={f.waste_pct} onChange={set("waste_pct")} /></Field>
            <Field label="Barang Sisa (%)"><input data-testid="recipe-byproduct" type="number" step="0.1" className="field" value={f.byproduct_pct} onChange={set("byproduct_pct")} /></Field>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Makloon Default">
              <MakloonSelect triggerTestId="recipe-makloon" processType={f.process_type} value={f.default_makloon_id} valueName={f.default_makloon_name}
                onSelect={(m) => setF({ ...f, default_makloon_id: m.id, default_makloon_name: m.name })} label="Pilih makloon default…" />
            </Field>
            <Field label="Produk Barang Sisa (opsional)">
              <ProductSelect triggerTestId="recipe-byproduct-product" value={f.byproduct_product_id} valueName={f.byproduct_name}
                onSelect={(p) => setF({ ...f, byproduct_product_id: p.id, byproduct_name: `${p.name} (${p.sku})` })} label="Pilih produk sisa…" />
            </Field>
            <Field label="Tarif Jasa Default (Rp)"><MoneyInput testId="recipe-tariff" className="field" value={f.default_tariff} onChange={(v) => set("default_tariff")({ target: { value: v } })} /></Field>
            <Field label="Basis Tarif"><KNSelect data-testid="recipe-tariff-unit" className="field" value={f.tariff_unit} onValueChange={(v) => setF({ ...f, tariff_unit: v })} options={TARIFF_UNITS} /></Field>
            <Field label="Biaya Bahan Pembantu (Rp)"><MoneyInput testId="recipe-aux" className="field" value={f.aux_cost_default} onChange={(v) => set("aux_cost_default")({ target: { value: v } })} /></Field>
          </div>

          <Field label="Rumus perkiraan hasil (opsional — untuk pengguna lanjutan)">
            <input data-testid="recipe-formula" className="field font-mono text-[11px]" value={f.formula} onChange={set("formula")}
              placeholder="Kosongkan untuk rumus baku: bahan × rendemen − susut" />
          </Field>
          {/* G4-23 — variabel rumus berlabel manusia (klik untuk menyisipkan; nama teknis di tooltip). */}
          <div className="-mt-1.5 flex flex-wrap items-center gap-1" data-testid="recipe-formula-vars">
            <span className="text-[11px] text-[#8E8E93]">Kosong = jumlah bahan × rendemen × (1 − susut). Sisipkan:</span>
            {RECIPE_VARS.map((v) => (
              <button key={v.code} type="button" title={`Nama di rumus: ${v.code}`} data-testid={`recipe-formula-var-${v.code}`}
                className="rounded-full border border-[#D9E8FF] bg-white px-2 py-[1px] text-[11px] font-semibold text-[#0058CC] hover:border-[#0058CC]"
                onClick={() => setF({ ...f, formula: `${(f.formula || "").trimEnd()}${f.formula?.trim() ? " " : ""}${v.code}` })}>
                {v.label}
              </button>
            ))}
          </div>
          {/* Preview forecast inline */}
          <div className="rounded-lg border border-dashed border-[#0058CC]/40 bg-[#EAF2FF]/40 p-3">
            <div className="flex items-end gap-2">
              <Field label="Uji jumlah bahan"><input data-testid="recipe-test-qty" type="number" className="field w-28" value={testQty} onChange={(e) => setTestQty(e.target.value)} /></Field>
              <button data-testid="recipe-forecast-btn" type="button" className="secondary-button mb-0.5" onClick={runForecast}><Calculator size={13} /> Hitung Estimasi</button>
              {preview && (
                <div className="mb-0.5 flex-1 text-[11.5px]" data-testid="recipe-forecast-result">
                  Output ≈ <b className="tabular-nums text-[#0058CC]">{formatQty(preview.expected_output)}</b> · Sisa ≈ <b className="tabular-nums">{formatQty(preview.expected_byproduct)}</b>
                  {preview.warnings?.length > 0 && <span className="ml-1 text-[#B45309]">({preview.warnings[0]})</span>}
                </div>
              )}
            </div>
          </div>

          <Field label="Catatan"><textarea data-testid="recipe-notes" className="field" rows="2" value={f.notes} onChange={set("notes")} /></Field>
        </div>
        {modalErr && <p className="notice-bar danger mx-4 !mb-0" role="alert" data-testid="recipe-form-error">{modalErr}</p>}
        <div className="flex justify-end gap-2 border-t border-[#EFF0F2] px-4 py-3">
          <button className="secondary-button" onClick={onClose}>Batal</button>
          <button data-testid="recipe-form-save" className="primary-button" disabled={saving} onClick={save}><Save size={14} /> {saving ? "Menyimpan…" : "Simpan"}</button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, req, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">{label} {req && <span className="text-[#D14343]">*</span>}</span>
      {children}
    </label>
  );
}
