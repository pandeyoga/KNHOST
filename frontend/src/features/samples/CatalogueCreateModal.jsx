import { useEffect, useState } from "react";
import { BookOpen } from "lucide-react";
import FormModal from "../../components/FormModal";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";
import { cataloguePreview, createCatalogueOrder } from "./sampleApi";

const rows = (d) => (Array.isArray(d) ? d : d?.items || []);

/** L06 LN-060 — Pesanan Sampel Catalogue: 1 yd tiap warna TERSEDIA + 2 yd satu warna soft (komponen terpisah). */
export default function CatalogueCreateModal({ open, onClose, entityId, onCreated }) {
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
    axios.get(`${API}/customers`, { params: { with_credit: false } }).then((r) => setCustomers(rows(r.data))).catch(() => {});
    axios.get(`${API}/product-templates`, { params: { fabric_type: "woven", limit: 500 } }).then((r) => setTemplates(rows(r.data))).catch(() => {});
  }, [open]);
  useEffect(() => {
    if (!form.template_id) { setPreview(null); return; }
    cataloguePreview({ template_id: form.template_id, soft_product_id: form.soft || undefined })
      .then((p) => { setPreview(p); setErr(""); })
      .catch((e) => { setPreview(null); setErr(apiErrorText(e, "Komposisi catalogue tidak bisa disusun.")); });
  }, [form.template_id, form.soft]);

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
    } catch (e) { setErr(apiErrorText(e, "Gagal membuat catalogue.")); } finally { setBusy(false); }
  };

  return (
    <FormModal open={open} onClose={onClose} title="Sampel Catalogue" subtitle="1 yard tiap warna tersedia + 2 yard satu warna soft"
      icon={BookOpen} testId="catalogue-create" onSubmit={submit} submitLabel="Buat Pesanan Catalogue" busy={busy} error={err}>
      <div className="grid gap-3 text-[12px]">
        <label className="grid gap-1"><span className="field-label">Pelanggan</span>
          <select data-testid="catalogue-customer" className="field" value={form.customer_id} onChange={(e) => set("customer_id", e.target.value)}>
            <option value="">— pilih —</option>{customers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select></label>
        <label className="grid gap-1"><span className="field-label">Artikel (woven, yard)</span>
          <select data-testid="catalogue-template" className="field" value={form.template_id} onChange={(e) => setForm((f) => ({ ...f, template_id: e.target.value, soft: "" }))}>
            <option value="">— pilih —</option>{templates.map((t) => <option key={t.id} value={t.id}>{t.name || t.code || t.id}</option>)}
          </select></label>
        <div className="grid grid-cols-2 gap-2">
          {["free", "paid"].map((b) => (
            <button key={b} type="button" data-testid={`catalogue-billing-${b}`} onClick={() => set("billing", b)}
              className={`rounded-md border px-2 py-1.5 font-semibold transition-colors ${form.billing === b ? "border-[#9A5B00] bg-[#FFF3D6] text-[#9A5B00]" : "border-[#E5E5EA] bg-white"}`}>
              {b === "free" ? "Gratis" : "Berbayar"}</button>
          ))}
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
