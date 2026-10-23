/** SpecialOrderItemsEditor — L03 LN-030: beberapa item per Pesanan Khusus, masing-masing dengan sumber desainnya. */
import { Plus, Trash2 } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import { Field } from "../rnd/RndField";

export const SOURCE_OPTS = [
  { value: "parent_product", label: "Induk produk (custom warna)" },
  { value: "approved_artwork", label: "Motif/artwork ACC (belum produk)" },
  { value: "customer_reference", label: "Referensi / desain pelanggan" },
];
const TYPES = [{ value: "printing", label: "Printing" }, { value: "labdip", label: "Labdip" }, { value: "handfeel", label: "Handfeel" }];

export const blankItem = () => ({
  key: Math.random().toString(36).slice(2), source_type: "customer_reference", description: "", request_types: [],
  source_template_id: "", source_design_id: "", color_id: "", quantity: "", unit: "meter", target_price: "", notes: "",
});

export function itemProblems(it, i) {
  const p = [];
  if (!it.quantity || Number(it.quantity) <= 0) p.push(`jumlah item ${i + 1}`);
  if (it.request_types.length === 0) p.push(`jenis uji item ${i + 1}`);
  if (it.source_type === "parent_product" && !it.source_template_id) p.push(`induk produk item ${i + 1}`);
  if (it.source_type === "approved_artwork" && !it.source_design_id) p.push(`artwork item ${i + 1}`);
  return p;
}

export default function SpecialOrderItemsEditor({ items, onChange, templates, artworks, colors, unitOptions }) {
  const upd = (idx, k, v) => onChange(items.map((it, i) => (i === idx ? { ...it, [k]: v } : it)));
  const toggle = (idx, t) => {
    const cur = items[idx].request_types;
    upd(idx, "request_types", cur.includes(t) ? cur.filter((x) => x !== t) : [...cur, t]);
  };
  return (
    <div className="grid gap-2" data-testid="od-items">
      {items.map((it, idx) => (
        <ItemRow key={it.key} it={it} idx={idx} upd={upd} toggle={toggle} templates={templates} artworks={artworks}
          colors={colors} unitOptions={unitOptions} canRemove={items.length > 1}
          onRemove={() => onChange(items.filter((_, i) => i !== idx))} />
      ))}
      <button type="button" className="secondary-button w-fit text-[11.5px]" data-testid="od-item-add"
        onClick={() => onChange([...items, blankItem()])}><Plus size={13} /> Tambah item</button>
    </div>
  );
}

function ItemRow({ it, idx, upd, toggle, templates, artworks, colors, unitOptions, canRemove, onRemove }) {
  const n = idx + 1;
  return (
    <div className="rounded-lg border border-[#E5E5EA] bg-white p-2.5" data-testid={`od-item-${n}`}>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[11.5px] font-bold">Item {n}</span>
        {canRemove && <button type="button" className="text-[#A8221A]" onClick={onRemove} data-testid={`od-item-remove-${n}`}><Trash2 size={13} /></button>}
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Sumber desain *">
          <KNSelect data-testid={`od-item-source-${n}`} className="field" value={it.source_type} options={SOURCE_OPTS}
            onValueChange={(v) => upd(idx, "source_type", v)} />
        </Field>
        {it.source_type === "parent_product" && (
          <Field label="Induk produk *">
            <KNSelect data-testid={`od-item-template-${n}`} className="field" value={it.source_template_id} searchable
              options={[{ value: "", label: "— pilih induk —" }, ...templates.map((t) => ({ value: t.id, label: t.name }))]}
              onValueChange={(v) => upd(idx, "source_template_id", v)} />
          </Field>
        )}
        {it.source_type === "approved_artwork" && (
          <Field label="Artwork ACC (HOLD tidak tampil) *">
            <KNSelect data-testid={`od-item-artwork-${n}`} className="field" value={it.source_design_id} searchable
              options={[{ value: "", label: artworks.length ? "— pilih artwork —" : "— belum ada artwork ACC —" },
                ...artworks.map((d) => ({ value: d.id, label: `${d.code || "tanpa kode"} · ${d.title}` }))]}
              onValueChange={(v) => upd(idx, "source_design_id", v)} />
          </Field>
        )}
        <Field label="Deskripsi item">
          <input className="field" data-testid={`od-item-desc-${n}`} value={it.description} onChange={(e) => upd(idx, "description", e.target.value)} placeholder="mis. Rayon motif kawung navy" />
        </Field>
        <Field label="Warna target">
          <KNSelect data-testid={`od-item-color-${n}`} className="field" value={it.color_id} searchable
            options={[{ value: "", label: "— belum ada / warna baru —" }, ...colors.map((c) => ({ value: c.id, label: `${c.code} · ${c.name}` }))]}
            onValueChange={(v) => upd(idx, "color_id", v)} />
        </Field>
        <Field label="Jumlah *"><input className="field" type="number" min="0" data-testid={`od-item-qty-${n}`} value={it.quantity} onChange={(e) => upd(idx, "quantity", e.target.value)} /></Field>
        <Field label="Satuan"><KNSelect data-testid={`od-item-unit-${n}`} className="field" value={it.unit} options={unitOptions} onValueChange={(v) => upd(idx, "unit", v)} /></Field>
        <Field label="Target harga / satuan (Rp)"><input className="field" type="number" min="0" data-testid={`od-item-price-${n}`} value={it.target_price} onChange={(e) => upd(idx, "target_price", e.target.value)} /></Field>
      </div>
      {/* 23 Okt — chip jenis uji diberi label (dulu tiga chip tanpa keterangan apa yang dipilih). */}
      <p className="field-label mt-2">Jenis uji / pekerjaan * <span className="font-normal normal-case text-[#9A9BA3]">(boleh lebih dari satu)</span></p>
      <div className="mt-1 flex flex-wrap gap-1.5" role="group" aria-label="Jenis uji" data-testid={`od-item-types-${n}`}>
        {TYPES.map((t) => {
          const on = it.request_types.includes(t.value);
          return (
            <button key={t.value} type="button" data-testid={`od-item-type-${n}-${t.value}`} onClick={() => toggle(idx, t.value)} aria-pressed={on}
              className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold transition-colors ${on ? "border-[#0058CC] bg-[#EFF4FF] text-[#0058CC]" : "border-[#E5E5EA] text-[#6B6B73]"}`}>
              {t.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
