/**
 * PREP-A (K-OPN-06) — petunjuk "SKU X digantikan oleh Y" di pemilih produk dokumen BARU.
 *
 * SKU tergantikan (kode salah / duplikat) tidak lagi ditawarkan backend (`GET /products`). Bila pengguna
 * mengetik SKU lamanya dan tidak ada hasil, komponen ini menanyakan `GET /master-governance/supersede-hint`
 * lalu menampilkan pengganti + tombol pilih (bila penggantinya ada di daftar yang boleh dipilih).
 * Petunjuk bersifat opsional: bila panggilan gagal, daftar utama tetap bekerja (tanpa petunjuk).
 */
import { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";
import axios, { API } from "../services/apiClient";

/** Pencocokan lokal (data sudah memuat `superseded_by_sku`, mis. katalog POS dari /dashboard). */
export function localSupersedeHints(query, products = []) {
  const q = String(query || "").trim().toLowerCase();
  if (q.length < 2) return [];
  const byId = new Map(products.map((p) => [p.id, p]));
  return products
    .filter((p) => p.superseded_by && [p.sku, p.legacy_sku].some((s) => String(s || "").toLowerCase() === q))
    .slice(0, 5)
    .map((p) => {
      const t = byId.get(p.superseded_by);
      return { product_id: p.id, sku: p.sku, name: p.name,
        superseded_by: t ? { id: t.id, sku: t.sku, name: t.name, status: t.status } : (p.superseded_by_sku ? { id: p.superseded_by, sku: p.superseded_by_sku, name: "" } : null) };
    });
}

export function SupersedeHintList({ hints = [], pickable = [], onPick, testId = "supersede-hint" }) {
  if (!hints.length) return null;
  const pickMap = new Map((pickable || []).map((p) => [p.id, p]));
  return (
    <div data-testid={testId} className="space-y-1 rounded-lg bg-[#FFF6E5] px-3 py-2 text-left text-[11.5px] text-[#8C4A00]">
      {hints.map((h) => {
        const t = h.superseded_by;
        const target = t && pickMap.get(t.id);
        return (
          <div key={h.product_id} data-testid={`${testId}-${h.sku}`} className="flex flex-wrap items-center gap-1.5">
            <span>SKU <b className="font-mono">{h.sku}</b> {t ? <>digantikan oleh <b className="font-mono">{t.sku}</b>{t.name ? ` — ${t.name}` : ""}</> : "sudah digantikan (pengganti tidak ditemukan)"}.</span>
            {target && onPick && (
              <button type="button" data-testid={`${testId}-pick-${t.sku}`} className="secondary-button !py-0.5 text-[11px]" onClick={() => onPick(target)}>
                <ArrowRight size={12} /> Pilih {t.sku}
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** Versi yang bertanya ke server (pemilih yang datanya TIDAK memuat SKU tergantikan). */
export default function SupersedeHint({ query, pickable = [], onPick, testId = "supersede-hint" }) {
  const [hints, setHints] = useState([]);
  useEffect(() => {
    const q = String(query || "").trim();
    if (q.length < 2) { setHints([]); return undefined; }
    let live = true;
    const t = setTimeout(() => {
      axios.get(`${API}/master-governance/supersede-hint`, { params: { q } })
        .then((r) => { if (live) setHints(Array.isArray(r.data) ? r.data : []); })
        .catch(() => { if (live) setHints([]); });   // petunjuk opsional — daftar utama tidak terganggu
    }, 250);
    return () => { live = false; clearTimeout(t); };
  }, [query]);
  return <SupersedeHintList hints={hints} pickable={pickable} onPick={onPick} testId={testId} />;
}
