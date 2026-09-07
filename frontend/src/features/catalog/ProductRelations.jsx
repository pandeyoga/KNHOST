import { useEffect, useState } from "react";
import { FlaskConical, ArrowUpRight } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { openRnd } from "../rnd/rndDeepLink";
import { catalogError } from "./catalogApi";
export const ProductRelations = ({ product, caps, onCreate }) => {
  const [rows, setRows] = useState(null); const [error, setError] = useState("");
  useEffect(() => { let live = true; setRows(null); setError(""); axios.get(`${API}/products/${product.id}/catalog-relations`).then(r => { if (live) setRows(r.data); }).catch(e => { if (live) setError(catalogError(e)); }); return () => { live = false; }; }, [product.id]);
  return <section data-testid="catalog-relations" className="space-y-4"><h3 className="font-semibold">Asal produk & keputusan R&D</h3>
    {error && <p data-testid="relations-error" role="alert" className="text-sm text-red-700">{error}</p>}
    {!rows && !error && <p data-testid="relations-loading">Memuat hubungan…</p>}
    {rows?.specs.map(s => <button data-testid={`relations-spec-${s.id}`} key={s.id} className="flex w-full items-center justify-between gap-3 rounded-md border p-4 text-left" onClick={() => openRnd({ view: "rnd-specs", specId: s.id })}><span><strong className="text-sm">{s.number}</strong><span className="mt-1 block text-xs text-gray-500">{s.title} · {s.status} · {s.lifecycle}</span></span><ArrowUpRight size={16} /></button>)}
    {rows && !rows.specs.length && <p data-testid="relations-empty" className="text-sm text-gray-500">Belum ada spesifikasi R&D terkait varian ini.</p>}
    {rows && <p data-testid="relations-sample-count" className="text-sm">{rows.sample_count} permintaan sampel dalam entitas aktif.</p>}
    {caps.rnd_create && !product.spec_id && product.lifecycle && product.lifecycle !== "produksi" && <button data-testid="relations-create-spec" className="primary-button" onClick={onCreate}><FlaskConical size={14} />Buat spesifikasi untuk varian ini</button>}
  </section>;
};