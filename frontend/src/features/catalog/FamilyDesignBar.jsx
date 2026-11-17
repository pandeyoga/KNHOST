/**
 * UAT 24 Okt (P6.1) — tag desain di master produk: kode desain · kategori pattern · kategori design (+ kepemilikan).
 * Dipilih dari Galeri Desain (bukan ketik bebas); semua varian induk ikut tersalin → filter POS & Pusat Export.
 *
 * Pola UI 16 Nov (M22): SATU baris kecil di ringkasan induk. Dulu bilah sendiri dengan teks teknis "kode desain &
 * kategorinya kosong di POS/export" untuk semua peran. Kini peringatan mutu data = "Belum bertaut desain" + tautan
 * "Pilih desain" HANYA bagi yang bisa memperbaikinya; penjelasan dampaknya di ikon "?". Yang tidak bisa mengubah dan
 * induknya belum bertaut desain tidak melihat baris ini.
 */
import { useEffect, useState } from "react";
import { Palette } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import StatusBadge from "../../components/StatusBadge";
import { HelpTip } from "../../components/ListPageParts";

const ACC = ["approved", "final_submitted", "active"];

export default function FamilyDesignBar({ family, canEdit, onChanged }) {
  const v = (family.variants || []).find((x) => x.design_id) || {};
  const [designs, setDesigns] = useState(null);
  const [pick, setPick] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [loadErr, setLoadErr] = useState("");
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open || designs) return;
    axios.get(`${API}/design-gallery`).then((r) => setDesigns((r.data || []).filter((d) => ACC.includes(d.status))))
      .catch((e) => { setDesigns([]); setLoadErr(e?.response?.data?.detail || "Gagal memuat daftar desain."); });
  }, [open, designs]);
  async function act(fn) {
    setBusy(true); setErr("");
    try { await fn(); setOpen(false); setPick(""); await onChanged?.(); }
    catch (e) { setErr(e?.response?.data?.detail || "Gagal menyimpan desain."); }
    finally { setBusy(false); }
  }
  if (!v.design_id && !canEdit) return null;
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-fs-12 text-kn-text-2" data-testid="catalog-family-design">
      <Palette size={13} className="text-kn-action" aria-hidden="true" />
      {v.design_id ? (
        <>
          <span>Desain <b className="font-mono text-kn-text" data-testid="catalog-family-design-code">{v.design_code || "—"}</b>{v.design_title ? ` · ${v.design_title}` : ""}</span>
          {v.pattern_category_name && <span>· Pattern: <b className="text-kn-text">{v.pattern_category_name}</b></span>}
          {v.design_category_name && <span>· Design: <b className="text-kn-text">{v.design_category_name}</b></span>}
          {v.exclusive_source === "design" && (
            <StatusBadge tone="warning" icon="lock" label={`Customer label · ${v.exclusive_customer_name || "pelanggan"}`} testId="catalog-family-design-exclusive" />
          )}
        </>
      ) : (
        <span className="inline-flex items-center gap-1 text-kn-warning-text" data-testid="catalog-family-design-missing">
          Belum bertaut desain
          <HelpTip testId="catalog-family-design-help" label="Kenapa desain perlu ditautkan"
            text="Tanpa desain, kode desain serta kategori pattern & design produk ini kosong di POS dan di Pusat Export, jadi tidak bisa disaring atau dilaporkan per desain." />
        </span>
      )}
      {canEdit && !open && (
        <button type="button" className="link-button" data-testid="catalog-family-design-edit" onClick={() => setOpen(true)}>
          {v.design_id ? "Ganti desain" : "Pilih desain"}
        </button>
      )}
      {canEdit && open && (
        <div className="flex w-full flex-wrap items-center gap-2">
          <div className="min-w-[260px] flex-1">
            <KNSelect data-testid="catalog-family-design-select" className="field" value={pick} searchable onValueChange={setPick}
              placeholder={designs ? "Pilih desain ACC" : "Memuat desain…"}
              emptyText={loadErr || "Belum ada desain ACC"}
              options={(designs || []).map((d) => ({ value: d.id, label: `${d.code} · ${d.title}${d.ownership === "customer" ? ` (milik ${d.owner_customer_name})` : ""}` }))} />
          </div>
          <button type="button" className="primary-button btn-sm" disabled={busy || !pick} data-testid="catalog-family-design-save"
            onClick={() => act(() => axios.post(`${API}/design-gallery/${pick}/products`, { template_id: family.id }))}>Simpan</button>
          {v.design_id && (
            <button type="button" className="secondary-button btn-sm" disabled={busy} data-testid="catalog-family-design-unlink"
              onClick={() => act(() => axios.post(`${API}/design-gallery-products/unlink`, { template_id: family.id }))}>Lepas desain</button>
          )}
          <button type="button" className="secondary-button btn-sm" onClick={() => setOpen(false)}>Batal</button>
        </div>
      )}
      {err && <p className="w-full text-fs-12 text-kn-danger-text" data-testid="catalog-family-design-error">{err}</p>}
    </div>
  );
}
