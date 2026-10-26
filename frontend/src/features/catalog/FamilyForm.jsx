import { useState } from "react";
import { Layers3, Save } from "lucide-react";
import { AxisEditor, presetAxes } from "./AxisEditor";
import { catalogApi, catalogError } from "./catalogApi";
import KNSelect from "../../components/KNSelect";
import DecimalInput from "../../components/DecimalInput";
import BaseFabricPicker from "../../components/BaseFabricPicker";
import FormModal from "../../components/FormModal";
import FormSection from "../../components/FormSection";
import useDomainEnums from "../../hooks/useDomainEnums";
import useCatalogMasters from "../../hooks/useCatalogMasters";

/** Ringkasan sumbu varian untuk bagian terlipat & kaki form: "Asal (3) × Warna (5) · 15 kombinasi". */
export function axesSummary(axes) {
  const list = (axes || []).filter((a) => a && a.label);
  if (!list.length) return "Belum ada atribut — produk satu varian";
  const combos = list.reduce((n, a) => n * Math.max(1, (a.options || []).length), 1);
  const empty = list.filter((a) => !(a.options || []).length).length;
  return `${list.map((a) => `${a.label} (${(a.options || []).length})`).join(" × ")} · ${combos.toLocaleString("id-ID")} kombinasi`
    + (empty ? ` · ${empty} atribut belum berpilihan` : "");
}

/**
 * FamilyForm — Induk produk baru / Ubah induk produk.
 *
 * Fase 4 · R4 (L-10) — dulu satu dinding isian ±1.600 px (dialog Radix) dengan semua sumbu varian terbuka. Kini
 * `FormModal` (kepala & kaki TETAP, layar penuh 1 kolom di HP) + `FormSection` bernomor: 1 Identitas · 2 Bahan &
 * satuan · 3 Deskripsi & kain dasar · 4 Atribut & pilihan varian (TERLIPAT, dengan ringkasan). Melipat hanya
 * menyembunyikan tampilan — isian tetap terpasang (keputusan pemilik: form tidak diringkas). Kaki = ringkasan
 * kombinasi + Batal/Simpan yang selalu terlihat. Galat validasi membuka bagian yang bermasalah.
 */
export const FamilyForm = ({ template, onClose, onSaved, axisConfig = null }) => {
  const { options, fieldRules, fieldLabels } = useDomainEnums();
  const [f, setF] = useState({ name: template?.name || "", category: template?.category || "", fabric_type: template?.fabric_type || "woven", stage: template?.stage || "finished", motif: template?.motif || "Polos", base_unit: template?.base_unit || "meter", base_price: template?.base_price ?? "", gramasi: template?.gramasi ?? "", lebar: template?.lebar ?? "", yarn_count: template?.yarn_count || "", yarn_count_system: template?.yarn_count_system || "", description: template?.description || "", sku_prefix: template?.sku_prefix || "", base_fabric_template_id: template?.base_fabric_template_id || "", base_fabric_name: template?.base_fabric_name || "" });
  const locked = (template?.variant_count || 0) > 0;
  const masters = useCatalogMasters({ current: { category: f.category, motif: f.motif, base_unit: f.base_unit } });
  const [axes, setAxes] = useState(template ? (template.axes || []).map(a => ({ ...a, options: a.options.map(o => ({ ...o, locked })) })) : presetAxes(axisConfig));
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const [axesOpen, setAxesOpen] = useState(false);
  const [extraOpen, setExtraOpen] = useState(!!(template?.description || template?.base_fabric_template_id));
  const set = (k, v) => setF(p => ({ ...p, [k]: v }));
  const submit = async e => {
    e?.preventDefault?.(); setError("");
    if (!f.name.trim()) { setError("Nama induk wajib diisi."); return; }
    if (!f.category) { setError("Pilih kategori dari Master Kategori."); return; }
    const missing = fieldRules(f.stage, f.fabric_type).required.filter(k => !f[k] || (["gramasi", "lebar"].includes(k) && !(Number(String(f[k]).replace(",", ".")) > 0)));
    if (missing.length) { setError(`Lengkapi ${missing.map(k => fieldLabels[k] || k).join(", ")}.`); return; }
    if (axes.some(a => !a.options.length)) { setAxesOpen(true); setError(`Atribut ${axes.filter(a => !a.options.length).map(a => a.label).join(", ")} memerlukan minimal satu pilihan (atau hapus atributnya).`); return; }
    setBusy(true);
    try { const body = { ...f, axes: axes.map(a => ({ ...a, options: a.options.map(({ locked, ...o }) => o) })) }; const res = await catalogApi.save(template?.id, body); onSaved(res.id); }
    catch (e) { setError(catalogError(e)); } finally { setBusy(false); }
  };
  const summary = axesSummary(axes);
  const extraSummary = [f.description ? "deskripsi terisi" : "tanpa deskripsi", f.base_fabric_name ? `kain dasar ${f.base_fabric_name}` : "tanpa kain dasar"].join(" · ");
  const lbl = "space-y-1 text-xs font-semibold";
  return <FormModal open onClose={onClose} busy={busy} error={error} size="lg" icon={Layers3} testId="family-form-dialog"
    title={template ? "Ubah induk produk" : "Induk produk baru"}
    subtitle={locked ? "SKU sudah terbentuk — tahap, jenis kain, satuan & struktur atribut terkunci; pilihan baru masih bisa ditambah." : "Isi identitas & bahan, lalu atur atribut varian (bagian 4)."}
    onSubmit={submit}
    footer={<div className="flex flex-wrap items-center justify-between gap-2">
      <p data-testid="family-form-summary" className="min-w-0 text-[11px] text-[#6B6B73]"><b className="text-[#1C1C1E]">{f.name.trim() || "Induk baru"}</b> · {summary}</p>
      <div className="ml-auto flex gap-2"><button type="button" data-testid="family-cancel" className="secondary-button" onClick={onClose} disabled={busy}>Batal</button><button data-testid="family-save" type="submit" className="primary-button" disabled={busy}><Save size={14} />{busy ? "Menyimpan…" : "Simpan induk"}</button></div>
    </div>}>
    <div className="space-y-3" data-testid="family-form">
      <FormSection number={1} title="Identitas produk" required testId="family-sec-identity">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {[["name", "Nama produk *"], ["sku_prefix", "Prefix SKU (huruf/angka, kosong = otomatis dari nama)"]].map(([k, l]) => <label key={k} className={lbl}>{l}<input data-testid={`family-${k}`} className="field" value={f[k]} onChange={e => set(k, k === "sku_prefix" ? e.target.value.toUpperCase().replace(/[^A-Z0-9-]/g, "") : e.target.value)} required={k === "name"} /></label>)}
          {[["category", "Kategori (Master Kategori) *", [{ value: "", label: "— pilih kategori —" }, ...masters.categoryOptions]], ["motif", "Motif (dari Master Desain / motif terpakai)", masters.motifOptions]].map(([k, l, opts]) => <label key={k} className={lbl}>{l}<KNSelect data-testid={`family-${k}`} className="field" searchable value={f[k]} options={opts} onValueChange={v => set(k, v)} /></label>)}
        </div>
      </FormSection>
      <FormSection number={2} title="Bahan & satuan" testId="family-sec-material"
        subtitle={locked ? "Tahap, jenis kain & satuan terkunci karena SKU sudah terbentuk." : ""}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {[["stage", "Tahap bahan", options("stage")], ["fabric_type", "Jenis kain", options("fabric_type")], ["base_unit", "Satuan dasar (Master Satuan)", masters.unitOptions]].map(([k, l, opts]) => <label key={k} className={lbl}>{l}<KNSelect data-testid={`family-${k}`} className="field" searchable value={f[k]} options={opts} disabled={locked} onValueChange={v => set(k, v)} /></label>)}
          {[["base_price", "Harga dasar / satuan"], ["gramasi", "Gramasi (gsm)"], ["lebar", "Lebar dasar (meter)"]].map(([k, l]) => <label key={k} className={lbl}>{l}<DecimalInput data-testid={`family-${k}`} className="field" min={0} value={f[k]} onChange={v => set(k, v)} /></label>)}
          {f.stage === "yarn" && <><label className={lbl}>Nomor benang<input data-testid="family-yarn-count" className="field" value={f.yarn_count} onChange={e => set("yarn_count", e.target.value)} /></label><label className={lbl}>Sistem nomor benang<KNSelect data-testid="family-yarn-system" className="field" value={f.yarn_count_system} options={options("yarn_count_system")} onValueChange={v => set("yarn_count_system", v)} /></label></>}
        </div>
      </FormSection>
      <FormSection number={3} title="Deskripsi & kain dasar" subtitle="opsional" collapsible open={extraOpen} onToggle={setExtraOpen}
        summary={extraSummary} testId="family-sec-extra">
        <div className="space-y-3">
          <label className={`block ${lbl}`}>Deskripsi<textarea data-testid="family-description" className="field min-h-20" value={f.description} onChange={e => set("description", e.target.value)} /></label>
          <div className={lbl}><span>Kain dasar dari master data <span className="font-normal text-[#6B6B73]">(mis. kain polos woven yang menjadi bahan printing; kosong = tidak ada)</span></span>
            <BaseFabricPicker testId="family-base-fabric" value={f.base_fabric_template_id} valueName={f.base_fabric_name} excludeId={template?.id || ""} onChange={tpl => setF(p => ({ ...p, base_fabric_template_id: tpl?.id || "", base_fabric_name: tpl?.name || "" }))} /></div>
        </div>
      </FormSection>
      <FormSection number={4} title="Atribut & pilihan varian" collapsible open={axesOpen} onToggle={setAxesOpen}
        summary={summary} testId="family-sec-axes">
        <AxisEditor axes={axes} onChange={setAxes} structuralLocked={locked} axisConfig={axisConfig} embedded />
      </FormSection>
    </div>
  </FormModal>;
};
