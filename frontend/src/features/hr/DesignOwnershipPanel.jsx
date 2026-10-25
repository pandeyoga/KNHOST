/**
 * UAT 24 Okt (P1 + P6) — Kepemilikan desain (white label / customer label), klaim pelanggan, data pemakaian
 * (siapa membeli, berapa SO, qty, repeat) dan tautan desain → induk/SKU.
 * Keputusan klaim oleh Manajer (P1-K1); pembeli lama tetap boleh repeat dari stok yang ada.
 */
import { useCallback, useEffect, useState } from "react";
import { Lock, Tag, Users } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import KNSelect from "../../components/KNSelect";
import { can } from "../../config/roles";
import { formatQty } from "../../utils/formatters";
import { notifySuccess } from "../../utils/feedback";

const fmtDate = (iso) => (iso ? String(iso).slice(0, 10) : "—");
const fmtRp = (n) => `Rp ${Number(n || 0).toLocaleString("id-ID", { maximumFractionDigits: 0 })}`;
const errText = (e, fb) => e?.response?.data?.detail || fb;

export function OwnershipBadge({ d, testId }) {
  const customer = d?.ownership === "customer";
  return (
    <span data-testid={testId} title={customer ? `Hanya untuk ${d.owner_customer_name}` : "Bebas dijual ke siapa saja"}
      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold ${customer ? "bg-[#B45309] text-white" : "bg-[#EEF1F4] text-[#3C3C43]"}`}>
      {customer ? <Lock size={9} /> : <Tag size={9} />}
      {customer ? `Customer label · ${d.owner_customer_name || "pelanggan"}` : "White label"}
      {d?.claim_pending && <span className="ml-1 rounded bg-[#FFF4E0] px-1 text-[#8A5300]">klaim menunggu</span>}
    </span>
  );
}

export default function DesignOwnershipPanel({ d, currentUser, onChanged }) {
  const perms = currentUser?.permissions;
  const canClaim = can(perms, "design_ownership", "claim");
  const canDecide = can(perms, "design_ownership", "decide");
  const canLink = can(perms, "product", "update");
  const [usage, setUsage] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [form, setForm] = useState({ mode: "", customer_id: "", reason: "", template_id: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const loadUsage = useCallback(() => {
    axios.get(`${API}/design-gallery/${d.id}/usage`).then((r) => setUsage(r.data)).catch(() => setUsage(null));
  }, [d.id]);
  useEffect(() => { loadUsage(); }, [loadUsage]);
  useEffect(() => {
    if (!form.mode) return;
    if ((form.mode === "claim" || form.mode === "customer") && !customers.length) {
      axios.get(`${API}/customers`, { params: { for_order: true, entity_id: d.entity_id || undefined } })
        .then((r) => setCustomers(Array.isArray(r.data) ? r.data : r.data?.items || [])).catch(() => {});
    }
    if (form.mode === "link" && !templates.length) {
      axios.get(`${API}/product-templates`).then((r) => setTemplates(Array.isArray(r.data) ? r.data : r.data?.items || [])).catch(() => {});
    }
  }, [form.mode, customers.length, templates.length, d.entity_id]);

  async function run(fn, msg) {
    setBusy(true); setErr("");
    try {
      const fresh = await fn();
      notifySuccess("Berhasil", msg);
      setForm({ mode: "", customer_id: "", reason: "", template_id: "" });
      loadUsage();
      if (fresh && fresh.id) onChanged?.(fresh);
    } catch (e) { setErr(errText(e, "Aksi gagal.")); }
    finally { setBusy(false); }
  }
  const post = (path, body) => axios.post(`${API}/design-gallery/${d.id}${path}`, body).then((r) => r.data);
  const pending = d.pending_claims || [];
  const custOpts = customers.map((c) => ({ value: c.id, label: `${c.name}${c.code ? ` · ${c.code}` : ""}` }));

  return (
    <div className="grid gap-2" data-testid="design-ownership-panel">
      <div className="flex flex-wrap items-center gap-2">
        <OwnershipBadge d={d} testId="design-ownership-badge" />
        <span data-testid="design-produced-badge"
          className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${d.produced ? "bg-[#E8F6EE] text-[#1B7F4B]" : "bg-[#F2F2F5] text-[#6B6B73]"}`}>
          {d.produced_label || (d.produced ? "Sudah diproduksi" : "Belum diproduksi")}
        </span>
        {d.ownership === "customer" && d.ownership_source_label && (
          <span className="text-[10.5px] text-[#6B6B73]">dari {d.ownership_source_label}</span>
        )}
      </div>
      {err && <ErrorNotice message={err} onDismiss={() => setErr("")} testId="design-ownership-error" />}

      {pending.map((c) => (
        <div key={c.id} data-testid={`design-claim-${c.id}`} className="rounded-lg border border-[#F0D9A8] bg-[#FFF9EC] px-3 py-2 text-[11.5px]">
          <p><b>{c.customer_name}</b> mengajukan klaim · oleh {c.by} · {fmtDate(c.at)}</p>
          <p className="text-[#6B6B73]">“{c.reason}”</p>
          {canDecide && (
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <input className="field !h-8 min-w-[200px] flex-1" placeholder="Alasan keputusan (wajib bila menolak)" data-testid={`design-claim-reason-${c.id}`}
                value={form.mode === `decide-${c.id}` ? form.reason : ""} onChange={(e) => setForm({ ...form, mode: `decide-${c.id}`, reason: e.target.value })} />
              <button className="primary-button !h-8" disabled={busy} data-testid={`design-claim-approve-${c.id}`}
                onClick={() => run(() => post(`/claims/${c.id}/decide`, { approve: true, reason: form.mode === `decide-${c.id}` ? form.reason : "" }),
                  "Klaim disetujui — desain kini customer label.")}>Setujui</button>
              <button className="secondary-button !h-8" disabled={busy} data-testid={`design-claim-reject-${c.id}`}
                onClick={() => run(() => post(`/claims/${c.id}/decide`, { approve: false, reason: form.mode === `decide-${c.id}` ? form.reason : "" }),
                  "Klaim ditolak.")}>Tolak</button>
            </div>
          )}
        </div>
      ))}

      <div className="flex flex-wrap gap-2 text-[11px] font-bold">
        {canClaim && d.ownership !== "customer" && !pending.length && (
          <button type="button" className="secondary-button !h-8" data-testid="design-claim-open" onClick={() => setForm({ ...form, mode: "claim" })}>Ajukan klaim pelanggan</button>
        )}
        {canDecide && d.ownership !== "customer" && (
          <button type="button" className="secondary-button !h-8" data-testid="design-set-customer-open" onClick={() => setForm({ ...form, mode: "customer" })}>Tetapkan customer label</button>
        )}
        {canDecide && d.ownership === "customer" && (
          <button type="button" className="secondary-button !h-8" data-testid="design-release-open" onClick={() => setForm({ ...form, mode: "white" })}>Lepas jadi white label</button>
        )}
        {canLink && (
          <button type="button" className="secondary-button !h-8" data-testid="design-link-open" onClick={() => setForm({ ...form, mode: "link" })}>Tautkan induk produk</button>
        )}
      </div>

      {["claim", "customer", "white"].includes(form.mode) && (
        <div className="grid gap-2 rounded-lg border border-[#E5E5EA] p-2.5" data-testid="design-ownership-form">
          {form.mode !== "white" && (
            <KNSelect data-testid="design-ownership-customer" className="field" value={form.customer_id} searchable
              onValueChange={(v) => setForm({ ...form, customer_id: v })} options={custOpts} placeholder="Pilih pelanggan" />
          )}
          <input className="field" data-testid="design-ownership-reason" value={form.reason}
            placeholder={form.mode === "claim" ? "Alasan klaim (dibaca Manajer)" : "Alasan keputusan"}
            onChange={(e) => setForm({ ...form, reason: e.target.value })} />
          <div className="flex justify-end gap-2">
            <button type="button" className="secondary-button !h-8" onClick={() => setForm({ mode: "", customer_id: "", reason: "", template_id: "" })}>Batal</button>
            <button type="button" className="primary-button !h-8" data-testid="design-ownership-submit"
              disabled={busy || (form.mode !== "white" && !form.customer_id) || form.reason.trim().length < 5}
              onClick={() => (form.mode === "claim"
                ? run(() => post("/claims", { customer_id: form.customer_id, reason: form.reason }), "Klaim terkirim ke Manajer.")
                : form.mode === "customer"
                  ? run(() => post("/ownership/customer", { customer_id: form.customer_id, reason: form.reason }), "Desain kini customer label.")
                  : run(() => post("/ownership/white", { reason: form.reason }), "Desain kini white label."))}>
              {form.mode === "claim" ? "Kirim klaim" : "Simpan"}
            </button>
          </div>
        </div>
      )}

      {form.mode === "link" && (
        <div className="grid gap-2 rounded-lg border border-[#E5E5EA] p-2.5" data-testid="design-link-form">
          <p className="text-[11px] text-[#6B6B73]">Semua varian induk ini memakai desain ini: kode desain, kategori &amp; tag ikut tersalin ke SKU (filter POS &amp; Pusat Export).</p>
          <KNSelect data-testid="design-link-template" className="field" value={form.template_id} searchable
            onValueChange={(v) => setForm({ ...form, template_id: v })}
            options={templates.map((t) => ({ value: t.id, label: `${t.name}${t.sku_prefix ? ` · ${t.sku_prefix}` : ""}` }))} placeholder="Pilih induk produk" />
          <div className="flex justify-end gap-2">
            <button type="button" className="secondary-button !h-8" onClick={() => setForm({ mode: "", customer_id: "", reason: "", template_id: "" })}>Batal</button>
            <button type="button" className="primary-button !h-8" data-testid="design-link-submit" disabled={busy || !form.template_id}
              onClick={() => run(() => post("/products", { template_id: form.template_id }), "Induk produk ditautkan ke desain.")}>Tautkan</button>
          </div>
        </div>
      )}

      <div data-testid="design-usage">
        <p className="mb-1 flex items-center gap-1 text-[10.5px] font-bold uppercase tracking-wide text-[#8E8E93]"><Users size={11} /> Pemakaian (pembeli SKU ber-desain ini)</p>
        {!usage ? <p className="text-[11px] text-[#9A9BA3]">Memuat…</p> : (
          <>
            <p className="text-[11px] text-[#6B6B73]" data-testid="design-usage-summary">
              {/* G5-40: "0 repeat" → kalimat Indonesia, disembunyikan bila nol. */}
              {usage.products.length} SKU · {usage.orders} SO · {usage.customers.length} pelanggan{Number(usage.repeat_customers) > 0 ? ` · ${usage.repeat_customers} pelanggan beli ulang` : ""}
            </p>
            {usage.customers.length > 0 && (
              <table className="mt-1 w-full text-[11px]">
                <thead><tr className="text-left text-[#8E8E93]"><th className="py-0.5">Pelanggan</th><th className="text-right">SO</th><th className="text-right">Qty</th><th className="text-right">Nilai</th><th className="text-right">SO terakhir</th></tr></thead>
                <tbody>
                  {usage.customers.map((c) => (
                    <tr key={c.customer_id || c.customer_name} className="border-t border-[#F2F2F5]" data-testid={`design-usage-row-${c.customer_id}`}>
                      <td className="py-0.5">{c.customer_name}{c.repeat && <span className="ml-1 rounded bg-[#E8F0FF] px-1 text-[9.5px] font-bold text-[#0058CC]">beli ulang</span>}</td>
                      <td className="text-right tabular-nums">{c.orders}</td>
                      <td className="text-right tabular-nums">{Object.entries(c.qty_by_unit || {}).map(([u, q]) => `${formatQty(q)} ${u}`).join(" + ")}</td>
                      <td className="text-right tabular-nums">{fmtRp(c.value)}</td>
                      <td className="text-right">{c.last_order_number} · {fmtDate(c.last_order_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {usage.products.length > 0 && (
              <p className="mt-1 text-[10.5px] text-[#6B6B73]">SKU: {usage.products.slice(0, 8).map((p) => p.sku).join(", ")}{usage.products.length > 8 ? ` +${usage.products.length - 8}` : ""}</p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
