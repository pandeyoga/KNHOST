/**
 * DocTemplateForm — isian template dokumen dasar (kop, kolom tabel, kertas, tanda tangan, urutan bagian).
 *
 * Fase 3 · P2 (D-01) — diekstrak dari tab "Template Dokumen" AdminView (form paling lengkap untuk koleksi
 * `document_templates`) supaya dipakai layar utama Template Dokumen › "Kop & tata letak dasar" di atas tabel
 * berlapis global → badan usaha (`EntityMasterKindPanel kind="document-templates"`). L-10: bagian bernomor
 * (`FormSection`), bagian yang jarang diubah bisa dilipat — isian tetap terpasang (form HP = form desktop).
 * Testid `admin-template-*` & `template-section-*` dipertahankan.
 *
 *   <DocTemplateForm values={values} setValues={setValues} />   // `columns` & `section_order` = array
 */
import { useEffect, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import FormSection from "../../components/FormSection";

export const DOC_TYPE_LABEL = { surat_jalan: "Surat Jalan", invoice: "Faktur (Invoice)" };
export const SECTION_LABEL = {
  header: "Kop surat", customer: "Data pelanggan", items: "Daftar barang", allocation: "Alokasi roll",
  signature: "Tanda tangan", footer: "Catatan kaki",
};
export const DEFAULT_SECTION_ORDER = ["header", "customer", "items", "allocation", "signature", "footer"];
export const EMPTY_TEMPLATE = {
  document_type: "surat_jalan", name: "", header: "Kain Nusantara", footer: "", columns: ["SKU", "Nama Barang", "Qty", "Unit"],
  logo_url: "", paper_size: "A4", orientation: "portrait", margin_mm: 12, signature_left: "Dibuat Oleh",
  signature_right: "Disetujui Oleh", section_order: DEFAULT_SECTION_ORDER,
};

const splitCols = (t) => String(t || "").split(",").map((c) => c.trim()).filter(Boolean);
const L = "grid gap-1 text-[11px] font-semibold text-[#3C3C43]";

export default function DocTemplateForm({ values, setValues, lockType = false }) {
  const v = { ...EMPTY_TEMPLATE, ...(values || {}) };
  const order = Array.isArray(v.section_order) && v.section_order.length ? v.section_order : DEFAULT_SECTION_ORDER;
  const [colsText, setColsText] = useState(() => (Array.isArray(v.columns) ? v.columns.join(", ") : String(v.columns || "")));
  // Ganti baris yang disunting → teks kolom ikut baris itu.
  useEffect(() => {
    setColsText(Array.isArray(values?.columns) ? values.columns.join(", ") : String(values?.columns || ""));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [values?.id]);
  const set = (k, val) => setValues({ ...v, [k]: val });
  const move = (section, dir) => {
    const next = [...order];
    const i = next.indexOf(section);
    const j = i + dir;
    if (j < 0 || j >= next.length) return;
    [next[i], next[j]] = [next[j], next[i]];
    set("section_order", next);
  };
  const input = (key, label, ph, extra = {}) => (
    <label key={key} className={`${L} ${extra.wide ? "sm:col-span-2" : ""}`}>{label}{extra.required ? " *" : ""}
      <input data-testid={`admin-template-${key}-input`} className="field" placeholder={ph}
        type={extra.number ? "number" : "text"} min={extra.number ? 0 : undefined} value={v[key] ?? ""}
        onChange={(e) => set(key, extra.number ? Number(e.target.value) : e.target.value)} />
    </label>
  );

  return (
    <div className="grid gap-3" data-testid="doc-template-form">
      <FormSection number={1} title="Jenis & nama" required testId="tpl-sec-id">
        <div className="grid gap-2 sm:grid-cols-2">
          <label className={L}>Tipe dokumen *
            <KNSelect data-testid="admin-template-document_type-input" className="field" value={v.document_type} disabled={lockType}
              options={[...Object.entries(DOC_TYPE_LABEL).map(([value, label]) => ({ value, label })),
                ...(v.document_type && !DOC_TYPE_LABEL[v.document_type] ? [{ value: v.document_type, label: v.document_type }] : [])]}
              onValueChange={(val) => set("document_type", val)} />
          </label>
          {input("name", "Nama template", "mis. Template SJ Standar", { required: true })}
        </div>
      </FormSection>
      <FormSection number={2} title="Kop & catatan kaki" testId="tpl-sec-head">
        <div className="grid gap-2 sm:grid-cols-2">
          {input("header", "Kop / header", "mis. Kain Nusantara")}
          {input("footer", "Catatan kaki", "mis. Terima kasih")}
          {input("logo_url", "Alamat (URL) logo", "mis. https://…/logo.png", { wide: true })}
        </div>
      </FormSection>
      <FormSection number={3} title="Tabel & tanda tangan" testId="tpl-sec-table">
        <div className="grid gap-2 sm:grid-cols-2">
          <label className={`${L} sm:col-span-2`}>Kolom tabel (pisahkan dengan koma)
            <input data-testid="admin-template-columns-input" className="field" placeholder="mis. SKU, Nama Barang, Qty, Unit"
              value={colsText} onChange={(e) => { setColsText(e.target.value); set("columns", splitCols(e.target.value)); }} />
          </label>
          {input("signature_left", "Tanda tangan kiri", "mis. Dibuat Oleh")}
          {input("signature_right", "Tanda tangan kanan", "mis. Disetujui Oleh")}
        </div>
      </FormSection>
      <FormSection number={4} title="Kertas" collapsible defaultOpen={false} testId="tpl-sec-paper"
        summary={`${v.paper_size || "A4"} · ${v.orientation === "landscape" ? "mendatar" : "tegak"} · margin ${v.margin_mm ?? 12} mm`}>
        <div className="grid gap-2 sm:grid-cols-3">
          <label className={L}>Ukuran kertas
            <KNSelect data-testid="admin-template-paper_size-input" className="field" value={v.paper_size}
              options={[{ value: "A4", label: "A4" }, { value: "A5", label: "A5" }, { value: "Letter", label: "Letter" }, { value: "F4", label: "F4 / Folio" }]}
              onValueChange={(val) => set("paper_size", val)} />
          </label>
          <label className={L}>Orientasi
            <KNSelect data-testid="admin-template-orientation-input" className="field" value={v.orientation}
              options={[{ value: "portrait", label: "Tegak (portrait)" }, { value: "landscape", label: "Mendatar (landscape)" }]}
              onValueChange={(val) => set("orientation", val)} />
          </label>
          {input("margin_mm", "Margin (mm)", "mis. 12", { number: true })}
        </div>
      </FormSection>
      <FormSection number={5} title="Urutan bagian dokumen" collapsible defaultOpen={false} testId="tpl-sec-order"
        summary={order.map((s) => SECTION_LABEL[s] || s).join(" → ")}>
        <div data-testid="template-section-order-editor" className="grid gap-1.5">
          {/* G5-19 — ▲ nonaktif di baris pertama, ▼ di baris terakhir. */}
          {order.map((section, idx) => (
            <div key={section} data-testid={`template-section-${section}`}
              className="flex items-center justify-between rounded-md border border-[#EFF0F2] bg-white px-2 py-1 text-[12px] font-semibold">
              <span>{SECTION_LABEL[section] || section}</span>
              <span className="flex gap-1">
                <button type="button" aria-label="Naik" data-testid={`template-section-${section}-up-button`}
                  className="icon-button disabled:opacity-30" disabled={idx === 0} onClick={() => move(section, -1)}><ChevronUp size={13} /></button>
                <button type="button" aria-label="Turun" data-testid={`template-section-${section}-down-button`}
                  className="icon-button disabled:opacity-30" disabled={idx === order.length - 1} onClick={() => move(section, 1)}><ChevronDown size={13} /></button>
              </span>
            </div>
          ))}
        </div>
      </FormSection>
    </div>
  );
}
