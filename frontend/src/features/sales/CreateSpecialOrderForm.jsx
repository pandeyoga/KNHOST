/**
 * CreateSpecialOrderForm — INTAKE pesanan khusus (Special Order) terstruktur.
 * Pelanggan minta produk custom: referensi fisik/pattern/warna/handfeel → tipe permintaan menentukan routing
 * otomatis saat disetujui (printing → Desainer + R&D proofing; labdip/handfeel → R&D) dengan spesifikasi diwarisi.
 */
import { useEffect, useState } from "react";
import useUomConversions from "../../hooks/useUomConversions";   // INV-UOM-02 — satuan dari master
import { Camera, ImagePlus, Palette, Sparkles, X } from "lucide-react";
import FormModal from "../../components/FormModal";
import KNDatePicker from "../../components/KNDatePicker";
import KNSelect from "../../components/KNSelect";
import axios, { API } from "../../services/apiClient";
import { listColors } from "../rnd/rndApi";
import { Field, Hint } from "../rnd/RndField";
import SpecialOrderItemsEditor, { blankItem, itemProblems } from "./SpecialOrderItemsEditor";

const ARTWORK_OK = ["approved", "final_submitted", "active"];

export default function CreateSpecialOrderForm({ token, onCreated, onCancel }) {
  const { unitOptions: _uomOpts } = useUomConversions();   // INV-UOM-02
  const uomAllOptions = _uomOpts();
  const [customers, setCustomers] = useState([]);
  const [colors, setColors] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [cats, setCats] = useState({ pattern: [], design: [] });
  const [artworks, setArtworks] = useState([]);
  const [items, setItems] = useState([blankItem()]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [refFiles, setRefFiles] = useState([]);   // gambar referensi (swatch/pattern/foto kain) — diunggah sesudah OD tersimpan
  const addRefs = (list) => setRefFiles((cur) => [...cur, ...Array.from(list || [])].slice(0, 10));
  const [f, setF] = useState({
    customer_id: "", title: "", request_types: [], detail_level: "reference", reference_notes: "",
    template_id: "", fabric_type: "woven", gramasi: "", lebar: "", color_id: "", color_new_note: "", sku_hint: "", spec_notes: "",
    quantity: "", unit: "meter", target_price: "", expected_delivery: "", notes: "", submit: true,
    pattern_category_code: "", design_category_code: "",
  });
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const anyPrinting = items.some((it) => it.request_types.includes("printing"));

  useEffect(() => {
    const H = token ? { headers: { Authorization: `Bearer ${token}` } } : {};
    axios.get(`${API}/customers`, { params: { limit: 500, for_order: true, with_credit: false }, ...H }).then((r) => setCustomers(Array.isArray(r.data) ? r.data : r.data?.items || [])).catch(() => {});
    listColors().then((c) => setColors(Array.isArray(c) ? c : c?.items || [])).catch(() => {});
    axios.get(`${API}/product-templates`, H).then((r) => setTemplates(Array.isArray(r.data) ? r.data : r.data?.items || [])).catch(() => {});
    axios.get(`${API}/design-requests/meta`, H).then((r) => setCats({ pattern: r.data?.categories?.pattern || [], design: r.data?.categories?.design || [] })).catch(() => {});
    axios.get(`${API}/design-gallery`, { params: { on_hold: "no" }, ...H }).then((r) => setArtworks((Array.isArray(r.data) ? r.data : []).filter((d) => ARTWORK_OK.includes(d.status) && !d.on_hold))).catch(() => {});
  }, [token]);

  const full = f.detail_level === "full";
  const problems = [];
  if (!f.customer_id) problems.push("pelanggan");
  if (!f.title.trim()) problems.push("judul");
  items.forEach((it, i) => problems.push(...itemProblems(it, i)));
  if (!f.expected_delivery) problems.push("tenggat");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const payload = {
        customer_id: f.customer_id, title: f.title, detail_level: f.detail_level, reference_notes: f.reference_notes,
        spec: full ? { template_id: f.template_id, fabric_type: f.fabric_type, gramasi: f.gramasi === "" ? null : Number(f.gramasi), lebar: f.lebar === "" ? null : Number(f.lebar),
          color_id: f.color_id, color_new_note: f.color_new_note, sku_hint: f.sku_hint, notes: f.spec_notes }
          : { color_id: f.color_id, color_new_note: f.color_new_note },
        items: items.map(({ key, ...it }) => ({ ...it, quantity: Number(it.quantity), target_price: Number(it.target_price || 0) })),
        expected_delivery: f.expected_delivery, notes: f.notes, submit_for_approval: f.submit,
        pattern_category_code: f.pattern_category_code, design_category_code: f.design_category_code,
      };
      const res = await axios.post(`${API}/special-orders`, payload, token ? { headers: { Authorization: `Bearer ${token}` } } : undefined);
      const failed = [];
      for (const file of refFiles) {
        const fd = new FormData(); fd.append("file", file, file.name || `referensi-${Date.now()}.jpg`);
        try { await axios.post(`${API}/special-orders/${res.data.id}/references`, fd, { headers: { "Content-Type": "multipart/form-data" } }); }
        catch (e) { failed.push(file.name || "foto"); }
      }
      onCreated(failed.length ? { ...res.data, _refs_failed: failed } : res.data);
    } catch (e) { setErr(e.response?.data?.detail || e.message); setBusy(false); }
  };

  return (
    <FormModal open onClose={onCancel} size="lg" testId="special-order-form" icon={Sparkles} error={err}
      title="Pesanan Khusus Baru" subtitle="Permintaan produk custom dari pelanggan — diteruskan otomatis ke Desainer / R&D setelah disetujui"
      onSubmit={submit} submitLabel="Simpan pesanan khusus" busy={busy} submitDisabled={problems.length > 0} submitTestId="special-order-save">
      <div className="grid gap-3">
        <Step n={1} title="Pelanggan & permintaan">
          <div className="grid gap-2.5 sm:grid-cols-2">
            <Field label="Pelanggan *">
              <KNSelect data-testid="od-customer" className="field" value={f.customer_id} searchable
                options={[{ value: "", label: "— pilih pelanggan —" }, ...customers.map((c) => ({ value: c.id, label: `${c.name}${c.code ? ` · ${c.code}` : ""}` }))]}
                onValueChange={(v) => set("customer_id", v)} />
            </Field>
            <Field label="Judul permintaan *"><input className="field" data-testid="od-title" value={f.title} onChange={(e) => set("title", e.target.value)} placeholder="mis. Kain seragam navy motif kawung" /></Field>
          </div>
          {anyPrinting && (
            <div className="mt-2.5 grid gap-2.5 sm:grid-cols-2" data-testid="od-design-categories">
              <Field label="Kategori Pattern (desain)">
                <KNSelect data-testid="od-pattern-category" className="field" value={f.pattern_category_code}
                  options={[{ value: "", label: "— otomatis (kategori pertama aktif) —" }, ...cats.pattern.map((c) => ({ value: c.code, label: `${c.code} · ${c.name}` }))]}
                  onValueChange={(v) => set("pattern_category_code", v)} />
              </Field>
              <Field label="Kategori Design">
                <KNSelect data-testid="od-design-category" className="field" value={f.design_category_code}
                  options={[{ value: "", label: "— otomatis (kategori pertama aktif) —" }, ...cats.design.map((c) => ({ value: c.code, label: `${c.code} · ${c.name}` }))]}
                  onValueChange={(v) => set("design_category_code", v)} />
              </Field>
            </div>
          )}
        </Step>

        <Step n={2} title="Item & sumber desain">
          <SpecialOrderItemsEditor items={items} onChange={setItems} templates={templates} artworks={artworks} colors={colors} unitOptions={uomAllOptions} />
          <Hint>Printing → Desainer (atau langsung proofing bila artwork ACC dipilih) · Labdip/Handfeel → R&amp;D. Setiap dokumen turunan tertaut ke item-nya.</Hint>
        </Step>

        <Step n={3} title="Referensi pelanggan">
          <div className="grid gap-2.5 sm:grid-cols-[260px_1fr]">
            <Field label="Tingkat detail">
              <KNSelect data-testid="od-detail-level" className="field" value={f.detail_level}
                options={[{ value: "reference", label: "Hanya referensi (foto / kain fisik)" }, { value: "full", label: "Spesifikasi lengkap" }]} onValueChange={(v) => set("detail_level", v)} />
            </Field>
            <Field label="Catatan referensi fisik / pattern / warna / pegangan">
              <input className="field" data-testid="od-reference-notes" value={f.reference_notes} onChange={(e) => set("reference_notes", e.target.value)} placeholder="mis. Pelanggan kirim swatch navy & contoh motif, diterima 19 Sep" />
            </Field>
          </div>
          <Hint>Foto swatch / pattern / kain fisik diunggah di rincian pesanan setelah disimpan (bisa banyak) — otomatis ikut ke Desainer &amp; R&amp;D.</Hint>
        </Step>

        <Step n={4} title={full ? "Spesifikasi produk (lengkap)" : "Spesifikasi produk (ringkas — sisanya diisi R&D)"}>
          <div className={`grid gap-2.5 sm:grid-cols-2 ${full ? "lg:grid-cols-3" : ""}`}>
            {full && (
              <>
                <Field label="Induk produk basis (opsional)">
                  <KNSelect data-testid="od-template" className="field" value={f.template_id} searchable
                    options={[{ value: "", label: "— produk benar-benar baru —" }, ...templates.map((t) => ({ value: t.id, label: t.name }))]} onValueChange={(v) => set("template_id", v)} />
                </Field>
                <Field label="Jenis kain"><KNSelect data-testid="od-fabric" className="field" value={f.fabric_type} options={[{ value: "woven", label: "Woven (tenun)" }, { value: "knit", label: "Knit (rajut)" }]} onValueChange={(v) => set("fabric_type", v)} /></Field>
                <Field label="Gramasi (gsm)"><input className="field" type="number" data-testid="od-gramasi" value={f.gramasi} onChange={(e) => set("gramasi", e.target.value)} /></Field>
                <Field label="Lebar (cm)"><input className="field" type="number" data-testid="od-lebar" value={f.lebar} onChange={(e) => set("lebar", e.target.value)} /></Field>
                <Field label="SKU usulan"><input className="field" data-testid="od-sku" value={f.sku_hint} onChange={(e) => set("sku_hint", e.target.value.toUpperCase())} /></Field>
              </>
            )}
            <Field label="Warna target dari Pustaka Warna">
              <KNSelect data-testid="od-color" className="field" value={f.color_id} searchable
                options={[{ value: "", label: "— belum ada / warna baru —" }, ...colors.map((c) => ({ value: c.id, label: `${c.code} · ${c.name}` }))]} onValueChange={(v) => set("color_id", v)} />
            </Field>
            <Field label="Bila warna baru: catatan dari swatch pelanggan">
              <input className="field" data-testid="od-color-new" value={f.color_new_note} onChange={(e) => set("color_new_note", e.target.value)} placeholder="mis. navy kebiruan, lebih gelap dari KN-BLU-01" />
            </Field>
            {full && <Field label="Catatan spesifikasi"><input className="field" data-testid="od-spec-notes" value={f.spec_notes} onChange={(e) => set("spec_notes", e.target.value)} /></Field>}
          </div>
        </Step>

        <Step n={5} title="Gambar referensi (opsional)">
          <div className="flex flex-wrap items-center gap-2" data-testid="od-refs">
            <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-[#0058CC] bg-white px-3 py-1.5 text-[11.5px] font-semibold text-[#0058CC]" data-testid="od-ref-camera">
              <Camera size={13} /> Ambil foto
              <input type="file" accept="image/*" capture="environment" className="hidden" data-testid="od-ref-camera-input" onChange={(e) => { addRefs(e.target.files); e.target.value = ""; }} />
            </label>
            <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-[#E5E5EA] bg-white px-3 py-1.5 text-[11.5px] font-semibold text-[#3C3C43]" data-testid="od-ref-pick">
              <ImagePlus size={13} /> Pilih gambar
              <input type="file" accept="image/*,.pdf" multiple className="hidden" data-testid="od-ref-input" onChange={(e) => { addRefs(e.target.files); e.target.value = ""; }} />
            </label>
            <Hint>Foto swatch / pattern / kain fisik pelanggan — ikut ke Desainer & R&D. Maks 10.</Hint>
          </div>
          {refFiles.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2" data-testid="od-ref-list">
              {refFiles.map((file, i) => (
                <span key={`${file.name}-${i}`} className="relative inline-block">
                  {file.type?.startsWith("image/")
                    ? <img src={URL.createObjectURL(file)} alt={file.name} className="h-16 w-16 rounded-lg border border-[#E5E5EA] object-cover" />
                    : <span className="flex h-16 w-16 items-center justify-center rounded-lg border border-[#E5E5EA] bg-white p-1 text-center text-[9px]">{file.name}</span>}
                  <button type="button" className="absolute -right-1.5 -top-1.5 rounded-full bg-[#C62828] p-0.5 text-white" data-testid={`od-ref-remove-${i}`}
                    onClick={() => setRefFiles((cur) => cur.filter((_, j) => j !== i))} aria-label="Hapus gambar"><X size={10} /></button>
                </span>
              ))}
            </div>
          )}
        </Step>

        <Step n={6} title="Tenggat & catatan">
          <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Tenggat kirim *"><KNDatePicker data-testid="od-delivery" value={f.expected_delivery} onChange={(v) => set("expected_delivery", v)} /></Field>
            <Field label="Catatan pesanan" wide><input className="field" data-testid="od-notes" value={f.notes} onChange={(e) => set("notes", e.target.value)} /></Field>
          </div>
          <label className="mt-2 flex items-center gap-2 text-[11.5px]">
            <input type="checkbox" checked={f.submit} onChange={(e) => set("submit", e.target.checked)} data-testid="od-submit-approval" /> Langsung ajukan untuk persetujuan Manajer
          </label>
          {problems.length > 0 && <p className="mt-1 text-[11px] text-[#A8221A]" data-testid="od-problems">Belum lengkap: <b>{problems.join(", ")}</b>.</p>}
        </Step>
      </div>
    </FormModal>
  );
}

function Step({ n, title, children }) {
  return (
    <section className="rounded-xl border border-[#EFF0F2] bg-[#FAFBFC] p-3">
      <p className="mb-2 flex items-center gap-2 text-[12px] font-bold text-[#1C1C1E]">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#0058CC] text-[10px] text-white">{n}</span>{title}
      </p>
      {children}
    </section>
  );
}
