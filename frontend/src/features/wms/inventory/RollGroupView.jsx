/**
 * RollGroupView — FIX-5 (B4 §3.8 "penampil ribuan roll", pertanyaan pemilik 9 Nov: "roll bisa sangat banyak — ada
 * cara lebih mudah melihatnya?"). Roll dikelompokkan DI SERVER (`/inventory/roll-groups`):
 *   Produk  ›  Lot  ›  Lokasi (gudang · alamat bin)  ›  Roll (berhalaman, 50 per muat)
 * Semua tingkat tertutup bawaan; tiap kelompok menyebut jumlah roll, total panjang, min–maks panjang, jumlah
 * lot/lokasi dan jumlah roll per STATUS roll (bukan angka "Tersedia" — itu tetap satu layanan angka stok, FIX-2).
 * Saringan = saringan tab Roll yang sama (PT, lokasi kerja, gudang, lini, status cek, kata cari).
 */
import { useCallback, useEffect, useState } from "react";
import { ChevronRight, ChevronDown, Package, Layers, MapPin } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { apiErrorText } from "../../../utils/apiError";
import { formatQty, RollStatusBadge, rollStatusLabel } from "./inventoryConstants";

const PAGE = 50;
const fmtLen = (v, unit) => `${formatQty(v)} ${unit === "campuran" ? "(satuan campuran)" : unit || ""}`.trim();

function StatusSummary({ counts }) {
  const parts = Object.entries(counts || {}).sort((a, b) => b[1] - a[1]);
  if (!parts.length) return null;
  return (
    <span className="text-[11px] text-[#6B6B73]">
      {parts.slice(0, 4).map(([st, n]) => `${rollStatusLabel(st)} ${formatQty(n)}`).join(" · ")}
      {parts.length > 4 ? ` · +${parts.length - 4} status lain` : ""}
    </span>
  );
}

function useGroups(params, enabled) {
  const [state, setState] = useState({ rows: [], total: 0, page: 1, loading: false, error: "", meta: {} });
  const load = useCallback(async (page = 1, append = false) => {
    setState((s) => ({ ...s, loading: true, error: "" }));
    try {
      const { data } = await axios.get(`${API}/inventory/roll-groups`, { params: { ...params, page, page_size: PAGE } });
      setState((s) => ({ rows: append ? [...s.rows, ...data.groups] : data.groups, total: data.total, page,
        loading: false, error: "", meta: { roll_total: data.roll_total, length_total: data.length_total, scope: data.scope } }));
    } catch (e) {
      setState((s) => ({ ...s, loading: false, error: apiErrorText(e, "Gagal memuat kelompok roll") }));
    }
  }, [JSON.stringify(params)]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (enabled) load(1); }, [enabled, load]);
  return { ...state, more: () => load(state.page + 1, true), reload: () => load(1) };
}

function MoreButton({ shown, total, loading, onClick, testId }) {
  if (shown >= total) return null;
  return (
    <button type="button" data-testid={testId} disabled={loading} onClick={onClick}
      className="secondary-button mt-1 text-[12px]">
      {loading ? "Memuat…" : `Tampilkan ${formatQty(Math.min(PAGE, total - shown))} lagi (${formatQty(shown)} dari ${formatQty(total)})`}
    </button>
  );
}

function RollRows({ base, product, lot, loc }) {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const load = async (p) => {
    setLoading(true); setError("");
    try {
      const params = { ...base, product_id: product, lot: lot || "__none__", warehouse_id: loc.warehouse_id,
        bin_id: loc.bin_id || "", scope: "physical", page: p, page_size: PAGE };
      delete params.location_view;
      const { data } = await axios.get(`${API}/inventory/rolls`, { params });
      setRows((prev) => (p === 1 ? data.items : [...prev, ...data.items]));
      setTotal(data.total); setPage(p);
    } catch (e) { setError(apiErrorText(e, "Gagal memuat roll")); } finally { setLoading(false); }
  };
  useEffect(() => { load(1); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="ml-6 mt-1 mb-2" data-testid={`rg-rolls-${loc.warehouse_id}-${loc.bin_id || "none"}`}>
      {error && <p className="text-[12px] font-semibold text-[#C0341D]">{error}</p>}
      <table className="w-full text-[12px]">
        <thead>
          <tr className="text-left text-[11px] text-[#6B6B73]">
            <th className="py-1 pr-3 font-semibold">Nomor roll</th>
            <th className="py-1 pr-3 font-semibold text-right">Panjang</th>
            <th className="py-1 pr-3 font-semibold">Grade</th>
            <th className="py-1 pr-3 font-semibold">Dye lot</th>
            <th className="py-1 font-semibold">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[#F2F2F5]">
          {rows.map((r) => (
            <tr key={r.id} data-testid={`rg-roll-${r.id}`}>
              <td className="py-1 pr-3 font-mono font-semibold">{r.roll_no}</td>
              <td className="py-1 pr-3 text-right tabular-nums">{formatQty(r.length_remaining)} {r.unit}</td>
              <td className="py-1 pr-3">{r.grade || "—"}</td>
              <td className="py-1 pr-3">{r.dye_lot || "—"}</td>
              <td className="py-1"><RollStatusBadge status={r.status} /></td>
            </tr>
          ))}
          {loading && !rows.length && <tr><td colSpan={5} className="py-2 text-[#6B6B73]">Memuat roll…</td></tr>}
        </tbody>
      </table>
      <MoreButton shown={rows.length} total={total} loading={loading} onClick={() => load(page + 1)}
        testId={`rg-rolls-more-${loc.warehouse_id}-${loc.bin_id || "none"}`} />
    </div>
  );
}

function LocationRows({ base, product, lot }) {
  const g = useGroups({ ...base, level: "location", product_id: product, lot: lot ?? "" }, true);
  const [open, setOpen] = useState({});
  return (
    <div className="ml-6 border-l border-[#E5E5EA] pl-3" data-testid={`rg-locations-${product}-${lot || "none"}`}>
      {g.error && <p className="text-[12px] font-semibold text-[#C0341D]">{g.error}</p>}
      {g.rows.map((loc) => {
        const k = `${loc.warehouse_id}|${loc.bin_id}`;
        return (
          <div key={k}>
            <button type="button" onClick={() => setOpen((o) => ({ ...o, [k]: !o[k] }))}
              data-testid={`rg-loc-${loc.warehouse_id}-${loc.bin_id || "none"}`}
              className="flex w-full flex-wrap items-center gap-x-3 gap-y-0.5 rounded px-1 py-1.5 text-left hover:bg-[#F5F5F7]">
              {open[k] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              <MapPin size={13} className="text-[#6B6B73]" />
              <span className="text-[12.5px] font-semibold">{loc.warehouse_name || loc.warehouse_id}</span>
              <span className="text-[12px] text-[#3A3A3C]">{loc.bin_id ? `Bin ${loc.bin_code || loc.bin_id}` : "Belum ditempatkan ke bin"}</span>
              <span className="text-[12px] tabular-nums">{formatQty(loc.roll_count)} roll · {fmtLen(loc.total_length, loc.unit)}</span>
              <StatusSummary counts={loc.status_counts} />
            </button>
            {open[k] && <RollRows base={base} product={product} lot={lot} loc={loc} />}
          </div>
        );
      })}
      {g.loading && !g.rows.length && <p className="py-1 text-[12px] text-[#6B6B73]">Memuat lokasi…</p>}
      <MoreButton shown={g.rows.length} total={g.total} loading={g.loading} onClick={g.more}
        testId={`rg-locations-more-${product}-${lot || "none"}`} />
    </div>
  );
}

function LotRows({ base, product }) {
  const g = useGroups({ ...base, level: "lot", product_id: product }, true);
  const [open, setOpen] = useState({});
  return (
    <div className="ml-6 border-l border-[#E5E5EA] pl-3" data-testid={`rg-lots-${product}`}>
      {g.error && <p className="text-[12px] font-semibold text-[#C0341D]">{g.error}</p>}
      {g.rows.map((lt) => {
        const k = lt.lot || "";
        return (
          <div key={k || "__none__"}>
            <button type="button" onClick={() => setOpen((o) => ({ ...o, [k]: !o[k] }))}
              data-testid={`rg-lot-${product}-${k || "none"}`}
              className="flex w-full flex-wrap items-center gap-x-3 gap-y-0.5 rounded px-1 py-1.5 text-left hover:bg-[#F5F5F7]">
              {open[k] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              <Layers size={13} className="text-[#6B6B73]" />
              <span className="text-[12.5px] font-semibold">Lot {lt.lot || "(tanpa lot)"}</span>
              <span className="text-[12px] tabular-nums">{formatQty(lt.roll_count)} roll · {fmtLen(lt.total_length, lt.unit)}</span>
              <span className="text-[11.5px] text-[#6B6B73] tabular-nums">panjang {formatQty(lt.min_length)}–{formatQty(lt.max_length)}</span>
              <span className="text-[11.5px] text-[#6B6B73]">{formatQty(lt.location_count || 0)} lokasi{lt.grades?.length ? ` · grade ${lt.grades.join("/")}` : ""}</span>
              <StatusSummary counts={lt.status_counts} />
            </button>
            {open[k] && <LocationRows base={base} product={product} lot={k} />}
          </div>
        );
      })}
      {g.loading && !g.rows.length && <p className="py-1 text-[12px] text-[#6B6B73]">Memuat lot…</p>}
      <MoreButton shown={g.rows.length} total={g.total} loading={g.loading} onClick={g.more} testId={`rg-lots-more-${product}`} />
    </div>
  );
}

export default function RollGroupView({ params, search }) {
  const base = { ...params, ...(search ? { q: search } : {}) };
  const g = useGroups({ ...base, level: "product" }, true);
  const [open, setOpen] = useState({});
  return (
    <div className="bg-white rounded-xl border border-[#EFF0F2] p-3" data-testid="roll-group-view">
      <p className="mb-2 text-[12px] text-[#3A3A3C]" data-testid="rg-summary">
        {g.loading && !g.rows.length ? "Memuat kelompok roll…" : (
          <>Stok fisik di gudang: <b>{formatQty(g.meta.roll_total || 0)} roll</b> dalam <b>{formatQty(g.total)} produk</b>.
            {" "}Buka produk → lot → lokasi untuk melihat rollnya.</>
        )}
      </p>
      {g.error && <p className="text-[12px] font-semibold text-[#C0341D]" data-testid="rg-error">{g.error}</p>}
      {!g.loading && !g.error && g.rows.length === 0 && (
        <p className="py-6 text-center text-[12px] text-[#6B6B73]" data-testid="rg-empty">Tidak ada roll fisik untuk saringan ini.</p>
      )}
      <div className="divide-y divide-[#F2F2F5]">
        {g.rows.map((p) => (
          <div key={p.product_id}>
            <button type="button" onClick={() => setOpen((o) => ({ ...o, [p.product_id]: !o[p.product_id] }))}
              data-testid={`rg-product-${p.product_id}`}
              className="flex w-full flex-wrap items-center gap-x-3 gap-y-0.5 px-1 py-2 text-left hover:bg-[#F5F5F7]">
              {open[p.product_id] ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
              <Package size={14} className="text-[#0058CC]" />
              <span className="text-[13px] font-semibold">{p.product_name || p.product_id}</span>
              <span className="font-mono text-[11.5px] text-[#6B6B73]">{p.sku}</span>
              <span className="text-[12.5px] tabular-nums font-semibold">{formatQty(p.roll_count)} roll</span>
              <span className="text-[12px] tabular-nums">{fmtLen(p.total_length, p.unit)}</span>
              <span className="text-[11.5px] text-[#6B6B73]">{formatQty(p.lot_count)} lot · {formatQty(p.warehouse_count)} gudang</span>
              <StatusSummary counts={p.status_counts} />
            </button>
            {open[p.product_id] && <LotRows base={base} product={p.product_id} />}
          </div>
        ))}
      </div>
      <MoreButton shown={g.rows.length} total={g.total} loading={g.loading} onClick={g.more} testId="rg-products-more" />
    </div>
  );
}
