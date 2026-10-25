import { useEffect, useState } from "react";
import { BookOpen } from "lucide-react";
import FormModal from "../../components/FormModal";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";
import { KNSelect } from "../../components/KNSelect";
import { cataloguePreview, catalogueTemplates, createCatalogueOrder } from "./sampleApi";

const rows = (d) => (Array.isArray(d) ? d : d?.items || []);

/** L06 LN-060 — Pesanan Sample Katalog: 1 yd tiap warna TERSEDIA + 2 yd satu warna soft (komponen terpisah).
 *  UAT 24 Okt (audit UI tahap 2) — G2-19: satu istilah "Katalog" (dulu tombol "Sample Katalog" membuka pop-up
 *  "Sample Catalogue" bertombol "Buat Pesanan Catalogue"); * pada Pelanggan/Artikel; pilihan skema standar. */
export default function CatalogueCreateModal({ open, onClose, entityId, onCreated, initialTemplateId = "", initialCustomerId = "" }) {
  const [customers, setCustomers] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [form, setForm] = useState({ customer_id: "", template_id: "", soft: "", billing: "free" });
  const [preview, setPreview] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    if (!open) return;
    setErr(""); setPreview(null);
    if (initialTemplateId || initialCustomerId) setForm((f) => ({ ...f, template_id: initialTemplateId || f.template_id, customer_id: initialCustomerId || f.customer_id, soft: "" }));
    axios.get(`${API}/customers`, { params: { with_credit: false, for_order: true } }).then((r) => setCustomers(rows(r.data))).catch(() => {});
    catalogueTemplates(entityId ? { entity_id: entityId } : {}).then((r) => setTemplates(rows(r))).catch(() => setTemplates([]));
  }, [open, entityId, initialTemplateId, initialCustomerId]);
  useEffect(() => {
    if (!form.template_id) { setPreview(null); return undefined; }
    let live = true;
    cataloguePreview({ template_id: form.template_id, soft_product_id: form.soft || undefined, ...(entityId ? { entity_id: entityId } : {}) })
      .then((p) => { if (live) { setPreview(p); setErr(""); } })
      .catch((e) => { if (live) { setPreview(null); setErr(apiErrorText(e, "Komposisi katalog tidak bisa disusun.")); } });
    return () => { live = false; };
  }, [form.template_id, form.soft, entityId]);

  const submit = async () => {
    const cust = customers.find((c) => c.id === form.customer_id);
    if (!cust || !preview?.soft) { setErr("Pilih pelanggan, artikel, dan warna soft."); return; }
    setBusy(true);
    try {
      const so = await createCatalogueOrder({
        customer_id: cust.id, shipping_address_id: cust.addresses?.[0]?.id || "", entity_id: entityId,
        order_type: "sample", sample_billing: form.billing, items: [],
        catalogue: { template_id: form.template_id, soft_product_id: form.soft } });
      onCreated?.(so); onClose();
    } catch (e) { setErr(apiErrorText(e, "Gagal membuat pesanan katalog.")); } finally { setBusy(false); }
  };

  return (
    <FormModal open={open} onClose={onClose} title="Sample Katalog Baru" subtitle="1 yard tiap warna tersedia + 2 yard satu warna soft"
      icon={BookOpen} testId="catalogue-create" onSubmit={submit} submitLabel="Buat Pesanan Katalog" busy={busy} error={err}>
      <div className="grid gap-3 text-[12px]">
        <label className="grid gap-1"><span className="field-label">Pelanggan <span className="text-red-500">*</span></span>
          <KNSelect data-testid="catalogue-customer" aria-label="Pelanggan" placeholder="— Pilih pelanggan —" value={form.customer_id}
            onValueChange={(v) => { if (v) set("customer_id", v); }} options={customers.map((c) => ({ value: c.id, label: c.name }))} /></label>
        <label className="grid gap-1"><span className="field-label">Artikel (woven, yard) <span className="text-red-500">*</span></span>
          <KNSelect data-testid="catalogue-template" aria-label="Artikel" placeholder={templates.length ? "— Pilih artikel —" : "Tidak ada artikel ber-stok di badan usaha ini"}
            value={form.template_id} onValueChange={(v) => { if (v) setForm((f) => ({ ...f, template_id: v, soft: "" })); }}
            options={templates.map((t) => ({ value: t.id, label: t.name || t.code || t.id }))} /></label>
        <div className="grid gap-1">
          <span className="field-label">Skema biaya</span>
          <div className="inline-flex w-full rounded-lg border border-[#E5E5EA] bg-[#F5F5F7] p-0.5" role="radiogroup" aria-label="Skema biaya">
            {["free", "paid"].map((b) => (
              <button key={b} type="button" role="radio" aria-checked={form.billing === b} data-testid={`catalogue-billing-${b}`} onClick={() => set("billing", b)}
                className={`flex-1 rounded-md px-2 py-1.5 font-semibold transition-colors ${form.billing === b ? "bg-white text-[#0058CC] shadow-sm" : "text-[#6B6B73]"}`}>
                {b === "free" ? "Gratis" : "Berbayar"}</button>
            ))}
          </div>
        </div>
        {preview && <CataloguePreview preview={preview} soft={form.soft} onSoft={(v) => set("soft", v)} />}
      </div>
    </FormModal>
  );
}

function CataloguePreview({ preview, soft, onSoft }) {
  return (
    <div data-testid="catalogue-preview" className="rounded-md border border-[#F3D9A4] bg-[#FFF9EC] p-2.5">
      <p className="text-[11px] text-[#6B6B73]">{preview.colors_available} dari {preview.colors_total} warna tersedia
        {preview.unavailable?.length ? ` · tidak tersedia: ${preview.unavailable.join(", ")}` : ""}</p>
      <ul className="mt-1.5 grid gap-1">
        {preview.base.map((c) => (
          <li key={c.product_id} className="flex items-center justify-between gap-2">
            <span>{c.color || c.product_name} <span className="text-[#8E8E93]">· dasar 1 yd</span></span>
            <button type="button" data-testid={`catalogue-soft-${c.product_id}`} onClick={() => onSoft(c.product_id)}
              className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${soft === c.product_id ? "border-[#9A5B00] bg-[#9A5B00] text-white" : "border-[#F3D9A4] bg-white text-[#9A5B00]"}`}>
              {soft === c.product_id ? "Soft +2 yd" : "Jadikan soft"}</button>
          </li>
        ))}
      </ul>
      <p data-testid="catalogue-total" className="mt-2 text-right text-[12px] font-bold">Total {preview.soft ? preview.total_qty : preview.base.length} yd
        {!preview.soft && <span className="font-normal text-[#B23B14]"> · pilih warna soft (+2 yd)</span>}</p>
    </div>
  );
}
