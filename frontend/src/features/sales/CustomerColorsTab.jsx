/** CustomerColorsTab — sub-tab "Warna Pelanggan": warna milik pelanggan + warna produk eksklusif, dikelompokkan per pelanggan. */
import { useEffect, useMemo, useState } from "react";
import { Crown, FileDown, KeyRound, Layers, Lock, Package, Search, Sparkles, Users } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import KNSelect from "../../components/KNSelect";
import axios, { API } from "../../services/apiClient";
import { lifecycleMeta } from "../rnd/rndMeta";
import ColorUseRequestModal from "./ColorUseRequestModal";
import ColorUseRequestsPanel from "./ColorUseRequestsPanel";
import { blobError, downloadColorCard } from "./colorCard";

export default function CustomerColorsTab({ onOpenLinks, reloadKey, canApprove }) {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [customer, setCustomer] = useState("");
  const [asking, setAsking] = useState(null); // {color, ownerId, ownerName}
  const [notice, setNotice] = useState("");
  const [bump, setBump] = useState(0);

  const load = () => {
    setLoading(true);
    axios.get(`${API}/color-library/customer-colors`).then((r) => { setGroups(Array.isArray(r.data) ? r.data : []); setError(""); })
      .catch((e) => setError(e.response?.data?.detail || "Gagal memuat warna pelanggan.")).finally(() => setLoading(false));
  };
  useEffect(load, [reloadKey, bump]);

  const shown = useMemo(() => {
    const s = q.trim().toLowerCase();
    return groups.filter((g) => !customer || g.customer_id === customer).map((g) => ({
      ...g, colors: g.colors.filter((c) => !s || `${c.code} ${c.name} ${c.factory_name || ""} ${g.customer_name} ${c.products.map((p) => p.sku).join(" ")}`.toLowerCase().includes(s)),
    })).filter((g) => g.colors.length);
  }, [groups, q, customer]);
  const total = shown.reduce((n, g) => n + g.colors.length, 0);

  return (
    <div data-testid="customer-colors-tab">
      <div className="section-head flex-wrap gap-2">
        <div className="relative min-w-[200px] flex-1">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#9A9BA3]" />
          <input data-testid="customer-color-search" className="field w-full pl-8" placeholder="Cari kode/nama warna, pelanggan, SKU…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <KNSelect data-testid="customer-color-customer-filter" className="field w-[240px]" value={customer} onValueChange={setCustomer} searchable
          options={[{ value: "", label: "Semua pelanggan" }, ...groups.map((g) => ({ value: g.customer_id, label: g.customer_name }))]} />
      </div>
      <div className="section-body grid gap-4">
        <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="customer-color-error" />
        {notice && <p className="rounded-lg bg-[#DCFCE7] px-3 py-2 text-[11.5px] font-semibold text-[#166534]" data-testid="customer-color-notice">{notice}</p>}
        <ColorUseRequestsPanel canApprove={canApprove} reloadKey={`${reloadKey}-${bump}`} onChanged={() => setBump((b) => b + 1)} />
        <p className="text-[11px] text-[#6B6B73]" data-testid="customer-color-count">
          <b>{total}</b> warna dari <b>{shown.length}</b> pelanggan. Warna <b>milik pelanggan</b> & warna yang <b>hanya</b> dipakai produk eksklusif dipisah dari Warna Internal.
        </p>
        {loading ? <div className="h-24 animate-pulse rounded-lg bg-[#F5F5F7]" /> : shown.length === 0 ? (
          <div className="py-14 text-center text-[12px] text-[#8E8E93]" data-testid="customer-color-empty">
            <Users size={28} className="mx-auto mb-2 text-gray-300" />Belum ada warna pelanggan. Warna muncul di sini saat ditandai milik pelanggan atau dipakai produk eksklusif (hasil pesanan khusus).
          </div>
        ) : shown.map((g) => <CustomerGroup key={g.customer_id} group={g} onOpenLinks={onOpenLinks} onError={setError}
          onAsk={(color) => setAsking({ color, ownerId: g.customer_id, ownerName: g.customer_name })} />)}
      </div>
      {asking && <ColorUseRequestModal {...asking} onClose={() => setAsking(null)}
        onDone={(msg) => { setAsking(null); setNotice(msg); setBump((b) => b + 1); }} />}
    </div>
  );
}

function CustomerGroup({ group, onOpenLinks, onAsk, onError }) {
  const [busy, setBusy] = useState(false);
  const download = async () => {
    setBusy(true);
    try { await downloadColorCard(group.customer_id, group.customer_name); } catch (e) { onError(await blobError(e, "Gagal membuat kartu warna.")); }
    setBusy(false);
  };
  return (
    <section className="rounded-xl border border-[#EFF0F2]" data-testid={`customer-color-group-${group.customer_id}`}>
      <header className="flex items-center gap-2 border-b border-[#EFF0F2] bg-[#FAFBFC] px-3 py-2">
        <Users size={13} className="text-[#B45309]" />
        <h3 className="text-[12.5px] font-bold text-[#1C1C1E]">{group.customer_name}</h3>
        <span className="rounded bg-[#FEF3C7] px-1.5 text-[10px] font-bold text-[#92400E]">{group.colors.length} warna</span>
        <button type="button" onClick={download} disabled={busy} data-testid={`customer-color-card-pdf-${group.customer_id}`}
          className="ml-auto inline-flex items-center gap-1 rounded-md border border-[#E5E5EA] bg-white px-2 py-1 text-[10.5px] font-semibold text-[#1C1C1E] hover:bg-[#F5F5F7] disabled:opacity-50">
          <FileDown size={12} /> {busy ? "Menyiapkan…" : "Kartu Warna (PDF)"}
        </button>
      </header>
      <div className="grid grid-cols-1 gap-2.5 p-2.5 sm:grid-cols-2 xl:grid-cols-3">
        {group.colors.map((c) => <CustomerColorCard key={c.id} c={c} customerId={group.customer_id} onOpenLinks={onOpenLinks} onAsk={onAsk} />)}
      </div>
    </section>
  );
}

function CustomerColorCard({ c, customerId, onOpenLinks, onAsk }) {
  const shared = c.general_products_count > 0;
  return (
    <div className="flex overflow-hidden rounded-lg border border-[#E5E5EA] bg-white" data-testid={`customer-color-card-${customerId}-${c.id}`}>
      <div className="w-14 shrink-0" style={{ backgroundColor: c.hex }} />
      <div className="min-w-0 flex-1 p-2">
        <div className="flex items-center justify-between gap-1">
          <span className="truncate text-[11.5px] font-bold">{c.code}</span>
          <span className="shrink-0 font-mono text-[9.5px] text-[#9A9BA3]">{c.hex}</span>
        </div>
        <p className="truncate text-[10.5px] text-[#6B6B73]">{c.name}{c.factory_name ? ` · pabrik: ${c.factory_name}` : ""}</p>
        <div className="mt-1 flex flex-wrap gap-1">
          {c.owned && <span className="inline-flex items-center gap-0.5 rounded bg-[#FEF3C7] px-1.5 py-px text-[9.5px] font-bold text-[#92400E]" data-testid={`customer-color-owned-${c.id}`}><Crown size={9} /> Milik pelanggan</span>}
          {c.owned && <span className="inline-flex items-center gap-0.5 rounded bg-[#FEE2E2] px-1.5 py-px text-[9.5px] font-bold text-[#991B1B]" data-testid={`customer-color-locked-${c.id}`} title="Produk umum / pelanggan lain butuh izin manajer"><Lock size={9} /> Terkunci</span>}
          {c.exclusive_source?.kind === "auto" && <span className="inline-flex items-center gap-0.5 rounded bg-[#F3E8FF] px-1.5 py-px text-[9.5px] font-bold text-[#6B21A8]" data-testid={`customer-color-auto-${c.id}`} title={`Ditandai otomatis saat labdip ${c.exclusive_source.sample_number || ""} disetujui`}><Sparkles size={9} /> Otomatis{c.exclusive_source.special_order_number ? ` · ${c.exclusive_source.special_order_number}` : ""}</span>}
          {c.products.length > 0 && <span className="inline-flex items-center gap-0.5 rounded bg-[#EEF4FF] px-1.5 py-px text-[9.5px] font-bold text-[#0058CC]"><Package size={9} /> {c.products.length} produk eksklusif</span>}
          {shared && <span className="rounded bg-[#F5F5F7] px-1.5 py-px text-[9.5px] font-bold text-[#6B6B73]" data-testid={`customer-color-shared-${c.id}`} title="Warna ini juga dipakai produk umum, jadi tetap tampil di Warna Internal">juga dipakai {c.general_products_count} produk umum</span>}
        </div>
        {c.products.map((p) => (
          <p key={p.id} className="mt-1 text-[10.5px] leading-snug" data-testid={`customer-color-product-${p.id}`}>
            <b className="font-mono">{p.sku}</b> <span style={{ color: lifecycleMeta(p.lifecycle).tone }}>{lifecycleMeta(p.lifecycle).label}</span>
            {p.special_order_number ? <span className="text-[#6B6B73]"> · {p.special_order_number}</span> : null}
            {p.supplier_colors.map((s) => <span key={s.supplier_name} className="block text-[#6B219A]">{s.supplier_name}: {s.supplier_color_name} {s.supplier_color_code}</span>)}
          </p>
        ))}
        {c.owned && (c.grants || []).length > 0 && (
          <p className="mt-1 text-[10px] text-[#166534]" data-testid={`customer-color-grants-${c.id}`}>Diizinkan untuk: {c.grants.map((g) => g.target_customer_name || "produk umum").join(", ")}</p>
        )}
        <div className="mt-1 flex flex-wrap gap-1">
          <button type="button" onClick={() => onOpenLinks(c.id, "")} data-testid={`customer-color-links-${customerId}-${c.id}`}
            className="inline-flex items-center gap-1 rounded px-1.5 py-px text-[9.5px] font-bold text-[#0058CC] hover:bg-[#EEF4FF]">
            <Layers size={9} /> keterkaitan
          </button>
          {c.owned && (
            <button type="button" onClick={() => onAsk(c)} data-testid={`customer-color-ask-${c.id}`}
              className="inline-flex items-center gap-1 rounded px-1.5 py-px text-[9.5px] font-bold text-[#B45309] hover:bg-[#FEF3C7]">
              <KeyRound size={9} /> minta izin pakai{c.pending_requests_count ? ` · ${c.pending_requests_count} menunggu` : ""}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
