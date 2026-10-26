/**
 * UAT 24 Okt (P15) — gabung beberapa PR (supplier & lokasi tujuan sama) menjadi SATU PO.
 *  · MergeSuggestions — saran kelompok PR dari server (supplier preferensi / supplier layak untuk semua barang).
 *  · MergeModal — pratinjau baris hasil lebur (SKU kembar = satu baris, alokasi per PR) lalu buat PO.
 */
import { useEffect, useMemo, useState } from "react";
import { Layers, Merge, X } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import { formatCurrency, formatDate, formatQty } from "../../utils/formatters";
import { isGroupEntityPartner } from "../../components/GroupEntityBadge";

const openLines = (pr) => (pr.items || []).filter((it) => it.fulfillment_mode !== "makloon" && it.product_id
  && Number(it.quantity || 0) - Number(it.realized_qty || 0) > 0.0005);
export const canMerge = (pr) => ["approved", "converted"].includes(pr.status) && openLines(pr).length > 0;

export function MergeSuggestions({ entityId, onPick, reloadKey, canAct = true }) {
  const [groups, setGroups] = useState(null);
  useEffect(() => {
    axios.get(`${API}/purchase-requisitions/merge-suggestions`, { params: entityId && entityId !== "all" ? { entity_id: entityId } : {} })
      .then((r) => setGroups(r.data?.groups || [])).catch(() => setGroups([]));
  }, [entityId, reloadKey]);
  if (!groups || !groups.length) return null;
  return (
    <section className="section-card !p-3" data-testid="pr-merge-suggestions">
      <p className="mb-2 flex items-center gap-1.5 text-[12px] font-bold text-[#1C1C1E]"><Layers size={13} className="text-[#0058CC]" /> Saran gabung PR → 1 PO</p>
      <div className="grid gap-2 md:grid-cols-2">
        {groups.slice(0, 6).map((g) => (
          // UAT 24 Okt (audit UI tahap 2) — G4-10: kunci kelompok = supplier + GUDANG tujuan; dulu hanya nama
          // lokasi yang tampil sehingga dua saran tampak identik. Kini gudang tujuan ikut ditulis.
          <div key={`${g.entity_id}-${g.supplier_id}-${g.warehouse_id}`} className="rounded-lg border border-[#EFF0F2] p-2.5 text-[11.5px]" data-testid={`pr-merge-group-${g.supplier_id}-${g.warehouse_id}`}>
            <p className="font-semibold">{g.supplier_code ? `${g.supplier_code} · ` : ""}{g.supplier_name} → {g.site_name}
              {g.warehouse_name && g.warehouse_name !== g.site_name ? <span className="font-normal text-[#6B6B73]"> · gudang {g.warehouse_name}</span> : null}</p>
            <p className="text-[#6B6B73]">{g.pr_count} PR · est. {formatCurrency(g.est_value)}{g.needed_from ? ` · butuh ${formatDate(g.needed_from)}${g.needed_to && g.needed_to !== g.needed_from ? ` – ${formatDate(g.needed_to)}` : ""}` : ""}
              {g.shared_sku ? " · ada SKU sama (dilebur 1 baris)" : ""}</p>
            <p className="mt-0.5 font-mono text-[10.5px] text-[#3C3C43]">{g.prs.map((p) => p.number).join(" · ")}</p>
            {canAct ? (
              <button type="button" className="secondary-button mt-1.5 !h-7 !text-[11px]" data-testid={`pr-merge-pick-${g.supplier_id}-${g.warehouse_id}`}
                onClick={() => onPick?.(g)}><Merge size={12} /> Gabung kelompok ini</button>
            ) : <p className="mt-1 text-[11px] text-[#6B6B73]" data-testid={`pr-merge-hint-${g.supplier_id}-${g.warehouse_id}`}>Teruskan ke Purchasing — PO gabungan dibuat pemegang hak buat PO.</p>}
          </div>
        ))}
      </div>
    </section>
  );
}

export function MergeModal({ prs, suppliers, presetSupplier = "", presetSupplierLabel = "", onClose, onDone }) {
  const prefs = [...new Set(prs.map((p) => p.preferred_supplier_id).filter(Boolean))];
  const [supplierId, setSupplierId] = useState(presetSupplier || (prefs.length === 1 ? prefs[0] : ""));
  // G4-10 — opsi "SUP-xxxx · Nama", tanpa badan usaha grup (PO ke PT grup ditolak server) & supplier nonaktif.
  // Supplier saran yang tidak ada di daftar termuat tetap ditampilkan (dulu pop-up terbuka dengan supplier kosong).
  const supplierOptions = useMemo(() => {
    const opts = (suppliers || []).filter((s) => !isGroupEntityPartner(s) && s.status !== "inactive")
      .map((s) => ({ value: s.id, label: s.code ? `${s.code} · ${s.name}` : s.name }));
    if (presetSupplier && !opts.some((o) => o.value === presetSupplier)) {
      opts.unshift({ value: presetSupplier, label: presetSupplierLabel || presetSupplier });
    }
    return opts;
  }, [suppliers, presetSupplier, presetSupplierLabel]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const rows = useMemo(() => {
    const m = new Map();
    prs.forEach((pr) => openLines(pr).forEach((it) => {
      const k = it.product_id;
      const r = m.get(k) || { product_id: k, sku: it.sku, name: it.product_name, unit: it.unit, qty: 0, from: [] };
      const q = Number(it.quantity || 0) - Number(it.realized_qty || 0);
      r.qty += q;
      r.from.push(`${pr.number} (${formatQty(q)})`);
      if (r.unit !== it.unit) r.unitMismatch = true;
      m.set(k, r);
    }));
    return [...m.values()];
  }, [prs]);
  const sites = [...new Set(prs.map((p) => p.ship_to_site_name || p.warehouse_name || "—"))];
  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const r = await axios.post(`${API}/purchase-requisitions/realize-many`, {
        pr_refs: prs.map((p) => ({ pr_id: p.id, line_nos: [] })), supplier_id: supplierId });
      onDone?.(r.data);
    } catch (e) { setErr(e?.response?.data?.detail || "Gagal membuat PO gabungan."); }
    finally { setBusy(false); }
  };
  return (
    <div className="modal-overlay" data-testid="pr-merge-modal" onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
      <div className="modal-card max-w-2xl" role="dialog" aria-modal="true">
        <div className="mb-2 flex items-start justify-between gap-2">
          <div>
            <p className="modal-title">Gabung {prs.length} PR menjadi 1 PO</p>
            <p className="text-[11.5px] text-[#6B6B73]">{prs.map((p) => p.number).join(" · ")} · tujuan {sites.join(" / ")}</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Tutup"><X size={16} /></button>
        </div>
        {sites.length > 1 && <p className="mb-2 rounded bg-[#FDECEC] px-2 py-1 text-[11px] text-[#9B1C1C]" data-testid="pr-merge-site-warn">PR dikirim ke lokasi berbeda — satu PO hanya untuk satu lokasi; server akan menolak.</p>}
        <label className="mb-2 block">
          <span className="field-label">Supplier *</span>
          <KNSelect data-testid="pr-merge-supplier" className="field" value={supplierId} searchable onValueChange={setSupplierId}
            options={supplierOptions} placeholder="Pilih supplier" />
        </label>
        <div className="max-h-[280px] overflow-y-auto rounded-lg border border-[#EFF0F2]">
          <table className="data-table text-[11.5px]" data-testid="pr-merge-preview">
            <thead><tr><th>Barang</th><th className="text-right">Qty PO</th><th>Dari PR</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.product_id} data-testid={`pr-merge-row-${r.product_id}`}>
                  <td><span className="font-mono">{r.sku}</span> {r.name}{r.unitMismatch && <span className="ml-1 text-[#A8221A]">· satuan beda</span>}</td>
                  <td className="text-right tabular-nums">{formatQty(r.qty)} {r.unit}</td>
                  <td className="text-[10.5px] text-[#6B6B73]">{r.from.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-1 text-[10.5px] text-[#6B6B73]">SKU yang sama dari beberapa PR dilebur jadi satu baris PO; tiap PR mencatat realisasi sebesar bagiannya.</p>
        <div className="mt-2"><ErrorNotice message={err} testId="pr-merge-error" /></div>
        <div className="mt-3 flex justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose}>Batal</button>
          <button type="button" className="primary-button" data-testid="pr-merge-submit" disabled={busy || !supplierId || rows.some((r) => r.unitMismatch)}
            onClick={submit}><Merge size={13} /> Buat 1 PO</button>
        </div>
      </div>
    </div>
  );
}
