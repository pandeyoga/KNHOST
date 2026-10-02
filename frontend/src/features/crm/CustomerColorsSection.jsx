/** CustomerColorsSection — warna eksklusif pelanggan di profil CRM (Customer 360) + unduh Kartu Warna PDF. */
import { useEffect, useState } from "react";
import { Crown, FileDown, Lock, Package, Palette, Sparkles } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import { blobError, downloadColorCard } from "../sales/colorCard";

export default function CustomerColorsSection({ customerId, customerName }) {
  const [colors, setColors] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setColors(null);
    axios.get(`${API}/color-library/customer-colors`, { params: { customer_id: customerId } })
      .then((r) => setColors((r.data || [])[0]?.colors || []))
      .catch((e) => { setColors([]); setError(e.response?.status === 403 ? "" : (e.response?.data?.detail || "Gagal memuat warna pelanggan.")); });
  }, [customerId]);

  const download = async () => {
    setBusy(true); setError("");
    try { await downloadColorCard(customerId, customerName); } catch (e) { setError(await blobError(e, "Gagal membuat kartu warna.")); }
    setBusy(false);
  };

  return (
    <div className="section-card mt-3" data-testid="customer-360-colors">
      <div className="section-head">
        <div className="flex items-center gap-2">
          <Palette size={14} className="text-[#B45309]" />
          <h3 className="text-[12.5px] font-bold">Warna Eksklusif</h3>
          <span className="tab-badge" data-testid="customer-360-colors-count">{colors ? colors.length : "…"}</span>
        </div>
        <button type="button" data-testid="customer-360-color-card-pdf" onClick={download} disabled={busy || !colors?.length} className="secondary-button text-[11px]">
          <FileDown size={13} /> {busy ? "Menyiapkan…" : "Kartu Warna (PDF)"}
        </button>
      </div>
      <div className="section-body">
        <ErrorNotice message={error} onDismiss={() => setError("")} testId="customer-360-colors-error" />
        {colors === null ? <div className="h-16 animate-pulse rounded-lg bg-[#F5F5F7]" /> : colors.length === 0 ? (
          <p className="py-4 text-center text-[11.5px] text-[#8E8E93]" data-testid="customer-360-colors-empty">Belum ada warna eksklusif untuk pelanggan ini.</p>
        ) : (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
            {colors.map((c) => <ColorTile key={c.id} c={c} />)}
          </div>
        )}
      </div>
    </div>
  );
}

function ColorTile({ c }) {
  return (
    <div className="flex overflow-hidden rounded-lg border border-[#E5E5EA]" data-testid={`customer-360-color-${c.id}`}>
      <div className="w-12 shrink-0" style={{ backgroundColor: c.hex }} />
      <div className="min-w-0 flex-1 p-2 text-[10.5px]">
        <p className="truncate text-[11.5px] font-bold">{c.code} <span className="font-mono text-[9.5px] font-normal text-[#9A9BA3]">{c.hex}</span></p>
        <p className="truncate text-[#6B6B73]">{c.name}</p>
        <div className="mt-1 flex flex-wrap gap-1">
          {c.owned && <span className="inline-flex items-center gap-0.5 rounded bg-[#FEF3C7] px-1 text-[9px] font-bold text-[#92400E]"><Crown size={8} /> Milik</span>}
          {c.owned && <span className="inline-flex items-center gap-0.5 rounded bg-[#FEE2E2] px-1 text-[9px] font-bold text-[#991B1B]" title="Tidak bisa dipakai produk umum / pelanggan lain tanpa izin manajer"><Lock size={8} /> Terkunci</span>}
          {c.exclusive_source?.kind === "auto" && <span className="inline-flex items-center gap-0.5 rounded bg-[#F3E8FF] px-1 text-[9px] font-bold text-[#6B21A8]" title={`Ditandai otomatis dari ${c.exclusive_source.sample_number || "labdip"}`}><Sparkles size={8} /> Otomatis</span>}
          {c.products.length > 0 && <span className="inline-flex items-center gap-0.5 rounded bg-[#EEF4FF] px-1 text-[9px] font-bold text-[#0058CC]"><Package size={8} /> {c.products.map((p) => p.sku).join(", ")}</span>}
        </div>
        {(c.supplier_versions || []).map((s) => <p key={s.supplier_name} className="truncate text-[#6B219A]">{s.supplier_name}: {s.supplier_color_name} {s.supplier_color_code}</p>)}
      </div>
    </div>
  );
}
