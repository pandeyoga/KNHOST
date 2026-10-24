/**
 * UAT 24 Okt (P6.1) — tag desain di master produk: kode desain · kategori pattern · kategori design (+ kepemilikan).
 * Dipilih dari Galeri Desain (bukan ketik bebas); semua varian induk ikut tersalin → filter POS & Pusat Export.
 */
import { useEffect, useState } from "react";
import { Lock, Palette } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";

const ACC = ["approved", "final_submitted", "active"];

export default function FamilyDesignBar({ family, canEdit, onChanged }) {
  const v = (family.variants || []).find((x) => x.design_id) || {};
  const [designs, setDesigns] = useState(null);
  const [pick, setPick] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open || designs) return;
    axios.get(`${API}/design-gallery`).then((r) => setDesigns((r.data || []).filter((d) => ACC.includes(d.status)))).catch(() => setDesigns([]));
  }, [open, designs]);
  async function act(fn) {
    setBusy(true); setErr("");
    try { await fn(); setOpen(false); setPick(""); await onChanged?.(); }
    catch (e) { setErr(e?.response?.data?.detail || "Gagal menyimpan desain."); }
    finally { setBusy(false); }
  }
  return (
    <div className="mb-2 flex flex-wrap items-center gap-2 rounded-lg border border-[#EFF0F2] bg-white px-3 py-2 text-[11.5px]" data-testid="catalog-family-design">
      <Palette size={13} className="text-[#6B219A]" />
      {v.design_id ? (
        <>
          <span>Desain <b className="font-mono" data-testid="catalog-family-design-code">{v.design_code || "—"}</b>{v.design_title ? ` · ${v.design_title}` : ""}</span>
          {v.pattern_category_name && <span className="rounded bg-[#F1E9F7] px-1.5 py-0.5 text-[10px] text-[#6B219A]">Pattern: {v.pattern_category_name}</span>}
          {v.design_category_name && <span className="rounded bg-[#F1E9F7] px-1.5 py-0.5 text-[10px] text-[#6B219A]">Design: {v.design_category_name}</span>}
          {v.exclusive_source === "design" && (
            <span className="inline-flex items-center gap-1 rounded bg-[#B45309] px-1.5 py-0.5 text-[10px] font-bold text-white"><Lock size={9} /> Customer label · {v.exclusive_customer_name}</span>
          )}
        </>
      ) : <span className="text-[#6B6B73]">Belum bertaut desain (kode desain & kategorinya kosong di POS/export).</span>}
      {canEdit && !open && (
        <button type="button" className="ml-auto text-[11px] font-bold text-[#0058CC]" data-testid="catalog-family-design-edit" onClick={() => setOpen(true)}>
          {v.design_id ? "Ganti desain" : "Pilih desain"}
        </button>
      )}
      {canEdit && open && (
        <div className="flex w-full flex-wrap items-center gap-2">
          <div className="min-w-[260px] flex-1">
            <KNSelect data-testid="catalog-family-design-select" className="field" value={pick} searchable onValueChange={setPick}
              placeholder={designs ? "Pilih desain ACC" : "Memuat desain…"}
              options={(designs || []).map((d) => ({ value: d.id, label: `${d.code} · ${d.title}${d.ownership === "customer" ? ` (milik ${d.owner_customer_name})` : ""}` }))} />
          </div>
          <button type="button" className="primary-button !h-8" disabled={busy || !pick} data-testid="catalog-family-design-save"
            onClick={() => act(() => axios.post(`${API}/design-gallery/${pick}/products`, { template_id: family.id }))}>Simpan</button>
          {v.design_id && (
            <button type="button" className="secondary-button !h-8" disabled={busy} data-testid="catalog-family-design-unlink"
              onClick={() => act(() => axios.post(`${API}/design-gallery-products/unlink`, { template_id: family.id }))}>Lepas desain</button>
          )}
          <button type="button" className="secondary-button !h-8" onClick={() => setOpen(false)}>Batal</button>
        </div>
      )}
      {err && <p className="w-full text-[11px] text-[#A8221A]" data-testid="catalog-family-design-error">{err}</p>}
    </div>
  );
}
