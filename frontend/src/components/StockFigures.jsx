/**
 * StockFigures (FIX-2, audit 9 Nov 2026 — B1 UI-06/07/40, B3a §10, B4 ADS-1…7) — SATU komponen "dua angka" stok.
 *
 * Keinginan pemilik: "user bisa melihat jelas stok dari semua bahkan multi entitas sampai barang yang akan datang,
 * tetapi banyaknya angka membuat pusing — angka lain muncul ketika lihat detail." Maka setiap layar stok hanya
 * menampilkan DUA angka "Tersedia":
 *   · LOKAL  — cakupan kerja pengguna (PT aktif × site kerja / lokasi jualan POS),
 *   · GLOBAL — benar-benar total semua PT & semua gudang aktif,
 * masing-masing ROLL dulu lalu panjang + satuan (`QtyDual`). Klik/ketuk → rincian (`DetailModal` baku): per lokasi
 * (site → gedung), per PT, per status, akan datang, dan ATP — angka dari SATU layanan server
 * (`GET /api/stock/figures/{product_id}`, `backend/services/stock_figures.py`). FE TIDAK menjumlah ulang stok;
 * satu-satunya penjumlahan adalah varian satu keluarga (satuan sama) untuk kartu katalog (`sumFigures`).
 *
 * Istilah mengikuti KN_32 (Tersedia · Dipesan · Dialokasikan · Karantina · Dalam Perjalanan · Stok Fisik).
 * Ukuran: huruf ≥ 12 px di desktop; `size="lg"` (HP) ≥ 14 px dan target sentuh ≥ 48 px (B4).
 */
import { useEffect, useMemo, useState } from "react";
import { ChevronRight, Info, MapPin, Globe2 } from "lucide-react";
import axios, { API } from "../services/apiClient";
import DetailModal from "./DetailModal";
import QtyDual from "./QtyDual";
import { formatQty } from "../utils/formatters";

const STATE_TEXT = { habis: "Habis", rendah: "Stok rendah", ada: "Tersedia" };
const STATE_CLS = { habis: "text-[#A8221A]", rendah: "text-[#8C4A00]", ada: "text-[#126E2C]" };
export const FIGURE_HINTS = {
  local: "Tersedia di cakupan kerja Anda: PT aktif × lokasi kerja (POS: lokasi jualan; gudang: lokasi tugas).",
  global: "Tersedia benar-benar total: semua PT dan semua gudang aktif.",
  available: "Tersedia = roll siap jual dikurangi panjang dipesan potong, reservasi, tahan QC/karantina, dan cadangan makloon.",
};

/** Satu aturan status angka (dipakai bila server tidak mengirim `state`, mis. hasil penjumlahan varian).
 *  Ambang = `low_stock_qty` kiriman server (`stock_availability.LOW_STOCK_QTY`); 100 hanya cadangan bila tak ada. */
export function stateOf(qty, lowQty = 100) {
  const q = Number(qty || 0);
  if (q <= 0.001) return "habis";
  return q < Number(lowQty || 100) ? "rendah" : "ada";
}

/** Status angka LOKAL/GLOBAL satu baris papan stok (`/inventory/status-board` → `stock_figures`) — satu aturan untuk
 *  chip "Habis di cakupan saya" / "Habis di grup" di desktop & HP (B1 UI-40). `fallbackQty` hanya bila server lama. */
export function figureState(row, kind, fallbackQty = 0) {
  return row?.stock_figures?.[kind]?.state || stateOf(fallbackQty, row?.stock_figures?.low_stock_qty);
}

/** Jumlahkan dua angka beberapa varian SATU keluarga (satuan sama). `variants[].stock_figures` dari server;
 *  varian kembar yang digabung (`merged_members`) ikut dijumlah. Mengembalikan null bila tidak ada data. */
export function sumFigures(variants = []) {
  const members = variants.flatMap((v) => v?.merged_members || [v]);
  const withFig = members.filter((m) => m && m.stock_figures);
  if (!withFig.length) return null;
  const low = withFig[0].stock_figures.low_stock_qty;
  const acc = { unit: withFig[0].stock_figures.unit || "", low_stock_qty: low,
    local: { qty: 0, rolls: 0 }, global: { qty: 0, rolls: 0 } };
  for (const m of withFig) {
    for (const k of ["local", "global"]) {
      acc[k].qty += Number(m.stock_figures[k]?.qty || 0);
      acc[k].rolls += Number(m.stock_figures[k]?.rolls || 0);
    }
  }
  for (const k of ["local", "global"]) {
    acc[k].qty = Math.round(acc[k].qty * 100) / 100;
    acc[k].state = stateOf(acc[k].qty, low);
  }
  return acc;
}

/** Dua angka untuk satu KELUARGA produk (kartu katalog POS/HP). LOKAL = stok di lokasi jualan pilihan (`siteStock`
 *  dari `/pos/site-stock`, definisi tunggal yang sama) bila ada, selain itu `stock_figures.local`; GLOBAL =
 *  `stock_figures.global`. Mengembalikan {local, global, unit, localLabel, badge}. */
export function figuresForGroup(group, { siteStock = null, siteName = "", entityName = "" } = {}) {
  const variants = group?.variants || [];
  const sum = sumFigures(variants);
  const unit = sum?.unit || group?.base?.base_unit || "meter";
  const low = sum?.low_stock_qty;
  let local = sum?.local || null;
  if (!local && group?.totalOwn !== null && group?.totalOwn !== undefined) {   // server lama tanpa `stock_figures`
    local = { qty: Number(group.totalOwn || 0), rolls: Number(group.totalOwnRolls || 0), state: stateOf(group.totalOwn, low) };
  }
  let localLabel = entityName || "PT saya";
  if (siteStock) {
    const qty = Math.round(variants.reduce((t, v) => t + Number(siteStock[v.id]?.own_qty || 0), 0) * 100) / 100;
    const rolls = variants.reduce((t, v) => t + Number(siteStock[v.id]?.rolls || 0), 0);
    local = { qty, rolls, state: stateOf(qty, low) };
    localLabel = [siteName || "Lokasi ini", entityName].filter(Boolean).join(" · ");
  }
  const global = sum?.global || { qty: Number(group?.totalAvailable || 0), rolls: Number(group?.totalRolls || 0),
    state: stateOf(group?.totalAvailable, low) };
  // Lencana kartu: tombol jual hanya mati bila GLOBAL habis (stok PT/lokasi lain tetap bisa dipenuhi Admin Sales).
  let badge = { key: "ada", text: "Tersedia", pill: "status-confirmed" };
  if (global.state === "habis") badge = { key: "habis", text: "Habis", pill: "status-cancelled" };
  else if (local && local.state === "habis") badge = { key: "lokal_habis", text: "Habis di lokasi ini", pill: "status-waiting_approval" };
  else if (local && local.state === "rendah") badge = { key: "rendah", text: "Stok rendah", pill: "status-waiting_approval" };
  return { local, global, unit, localLabel, badge };
}

function FigureLine({ kind, fig, unit, label, big, testId }) {
  const Icon = kind === "local" ? MapPin : Globe2;
  const state = fig?.state || stateOf(fig?.qty);
  return (
    <div className="flex items-baseline justify-between gap-2" data-testid={testId}>
      <span className={`inline-flex min-w-0 items-center gap-1 ${big ? "text-[14px]" : "text-[12px]"} text-[#6B6B73]`}
        title={FIGURE_HINTS[kind]}>
        <Icon size={big ? 14 : 12} className="shrink-0" aria-hidden="true" />
        <span className="truncate">{label}</span>
      </span>
      <span className={`shrink-0 text-right ${big ? "text-[16px]" : "text-[13px]"} ${kind === "local" ? STATE_CLS[state] : "text-[#1C1C1E]"}`}>
        {fig ? <QtyDual rolls={fig.rolls ?? null} measure={fig.qty ?? 0} unit={unit} testId={testId ? `${testId}-qty` : ""} />
          : <span className="text-[#6B6B73]">—</span>}
      </span>
    </div>
  );
}

export default function StockFigures({
  local = null, global = null, unit = "", localLabel = "", globalLabel = "Total grup (semua PT)", productIds = [],
  productLabels = {}, siteId = "", size = "md", title = "Tersedia", showState = false, testId = "stock-figures",
  className = "",
}) {
  const [open, setOpen] = useState(false);
  const big = size === "lg";
  const ids = (productIds || []).filter(Boolean);
  const state = local?.state || stateOf(local?.qty);
  const body = (
    <>
      <div className="flex items-center justify-between gap-2">
        <span className={`inline-flex items-center gap-1 font-semibold ${big ? "text-[14px]" : "text-[12px]"} text-[#1C1C1E]`}
          title={FIGURE_HINTS.available}>
          {title} <Info size={big ? 14 : 12} className="text-[#6B6B73]" aria-hidden="true" />
          {showState && (
            <span data-testid={`${testId}-state`} className={`ml-1 font-semibold ${STATE_CLS[state]}`}>· {STATE_TEXT[state]}</span>
          )}
        </span>
        {ids.length > 0 && <ChevronRight size={big ? 18 : 14} className="text-[#6B6B73]" aria-hidden="true" />}
      </div>
      <FigureLine kind="local" fig={local} unit={unit} label={localLabel || "Cakupan saya"} big={big} testId={`${testId}-local`} />
      <FigureLine kind="global" fig={global} unit={unit} label={globalLabel} big={big} testId={`${testId}-global`} />
    </>
  );
  return (
    <>
      {ids.length > 0 ? (
        <button type="button" data-testid={testId}
          className={`grid w-full gap-0.5 rounded-lg border border-[#E5E5EA] bg-white px-2.5 py-1.5 text-left hover:border-[#0058CC] ${big ? "min-h-[48px]" : ""} ${className}`}
          aria-label={`${title}: lihat rincian stok`} onClick={(e) => { e.stopPropagation(); setOpen(true); }}>
          {body}
        </button>
      ) : (
        <div data-testid={testId} className={`grid gap-0.5 rounded-lg border border-[#E5E5EA] bg-white px-2.5 py-1.5 ${className}`}>{body}</div>
      )}
      {open && (
        // Klik di dalam pop-up tidak boleh merambat ke baris/kartu induk (mis. baris papan stok yang bisa dibuka-tutup).
        <span onClick={(e) => e.stopPropagation()} role="presentation">
          <StockFiguresDetail productIds={ids} productLabels={productLabels} siteId={siteId} big={big}
            onClose={() => setOpen(false)} testId={`${testId}-detail`} />
        </span>
      )}
    </>
  );
}

const SOURCE_TEXT = { po: "PO terbuka", transfer: "Transfer dalam perjalanan", interco: "Antar-PT", makloon: "Makloon berjalan",
  return: "Retur belum diterima" };

function Section({ title, hint, children, testId }) {
  return (
    <section className="mt-3" data-testid={testId}>
      <h3 className="mb-1 flex items-center gap-1 text-[13px] font-bold text-[#1C1C1E]">{title}
        {hint && <span title={hint} aria-label={hint} className="inline-flex"><Info size={12} className="text-[#6B6B73]" /></span>}</h3>
      {children}
    </section>
  );
}

function Qty({ rolls, qty, unit }) {
  return <QtyDual rolls={rolls ?? null} measure={qty ?? 0} unit={unit} />;
}

/** Panel rincian (pop-up baku DetailModal). Dipisah agar bisa dipakai layar yang membuka rincian sendiri. */
export function StockFiguresDetail({ productIds = [], productLabels = {}, siteId = "", onClose, big = false,
  testId = "stock-figures-detail" }) {
  const [pid, setPid] = useState(productIds[0] || "");
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!pid) return undefined;
    let alive = true;
    setData(null); setErr("");
    axios.get(`${API}/stock/figures/${pid}`, { params: siteId ? { site_id: siteId } : {} })
      .then((r) => { if (alive) setData(r.data); })
      .catch((e) => { if (alive) setErr(e?.response?.data?.detail || "Rincian stok tidak bisa dimuat — coba lagi."); });
    return () => { alive = false; };
  }, [pid, siteId]);
  const unit = data?.unit || "";
  const txt = big ? "text-[14px]" : "text-[12px]";
  const statusRows = useMemo(() => {
    if (!data) return [];
    const g = Object.fromEntries((data.global_status || []).map((r) => [r.key, r]));
    return (data.local_status || []).map((r) => ({ ...r, g: g[r.key] || {} }))
      .filter((r) => r.qty > 0.004 || (r.g.qty || 0) > 0.004 || r.key === "available");
  }, [data]);
  return (
    <DetailModal open onClose={onClose} size="lg" label="Rincian stok" testId={testId} framed>
      <div className={`p-4 ${txt}`}>
        <h2 className="text-[16px] font-bold">Rincian stok{data ? ` — ${data.product_name}` : ""}</h2>
        {data?.sku && <p className="text-[12px] text-[#6B6B73]">{data.sku} · satuan {unit || "—"}</p>}
        {productIds.length > 1 && (
          <div className="mt-2 flex flex-wrap gap-1.5" data-testid={`${testId}-variants`}>
            {productIds.map((id) => (
              <button key={id} type="button" onClick={() => setPid(id)}
                className={`rounded-full border px-2.5 py-1 text-[12px] ${big ? "min-h-[48px]" : ""} ${id === pid ? "border-[#0058CC] bg-[#E8F1FF] font-semibold text-[#0058CC]" : "border-[#E5E5EA]"}`}>
                {productLabels[id] || id}
              </button>
            ))}
          </div>
        )}
        {err && <p className="mt-3 rounded-md bg-[#FDECEA] px-3 py-2 text-[#A8221A]" role="alert">{err}</p>}
        {!data && !err && <p className="mt-3 text-[#6B6B73]">Memuat rincian…</p>}
        {data && (
          <>
            <div className="mt-3 grid gap-2 sm:grid-cols-2" data-testid={`${testId}-pair`}>
              <div className="rounded-lg bg-[#F5F9FF] p-3" title={data.definitions?.local}>
                <p className="flex items-center gap-1 font-semibold text-[#0058CC]"><MapPin size={13} /> LOKAL · {data.scope?.label}</p>
                <p className="mt-1 text-[16px] font-bold"><Qty rolls={data.local.rolls} qty={data.local.qty} unit={unit} /></p>
                <p className="text-[12px] text-[#6B6B73]">Stok Fisik <Qty rolls={data.on_hand?.local?.rolls} qty={data.on_hand?.local?.qty} unit={unit} /></p>
              </div>
              <div className="rounded-lg bg-[#F5F5F7] p-3" title={data.definitions?.global}>
                <p className="flex items-center gap-1 font-semibold"><Globe2 size={13} /> GLOBAL · semua PT & gudang aktif</p>
                <p className="mt-1 text-[16px] font-bold"><Qty rolls={data.global.rolls} qty={data.global.qty} unit={unit} /></p>
                <p className="text-[12px] text-[#6B6B73]">Stok Fisik <Qty rolls={data.on_hand?.global?.rolls} qty={data.on_hand?.global?.qty} unit={unit} /></p>
              </div>
            </div>

            <Section title="Per status" hint={data.definitions?.on_hand} testId={`${testId}-status`}>
              <table className="w-full">
                <thead><tr className="text-left text-[12px] text-[#6B6B73]"><th className="py-1">Status</th><th className="py-1 text-right">Lokal</th><th className="py-1 text-right">Global</th></tr></thead>
                <tbody>
                  {statusRows.map((r) => (
                    <tr key={r.key} className="border-t border-[#F2F2F7]" title={r.hint}>
                      <td className="py-1">{r.label}</td>
                      <td className="py-1 text-right"><Qty rolls={r.rolls} qty={r.qty} unit={unit} /></td>
                      <td className="py-1 text-right"><Qty rolls={r.g.rolls} qty={r.g.qty} unit={unit} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>

            <Section title="Per lokasi (site → gedung)" testId={`${testId}-sites`}>
              {(data.by_site || []).length === 0 && <p className="text-[#6B6B73]">Belum ada stok di gudang aktif.</p>}
              {(data.by_site || []).map((s) => (
                <div key={s.site_id || "none"} className="mt-1 rounded-md border border-[#EFF0F2] p-2">
                  <p className="flex justify-between gap-2 font-semibold">
                    <span>{s.site_name}{s.local ? " · lokasi Anda" : ""}</span>
                    <Qty rolls={s.available_rolls} qty={s.available_qty} unit={unit} />
                  </p>
                  {(s.warehouses || []).map((w) => (
                    <div key={w.warehouse_id} className="mt-0.5 flex flex-wrap justify-between gap-x-3 text-[12px] text-[#3A3A3C]">
                      <span>{w.name}</span>
                      <span>
                        Tersedia <Qty rolls={w.available_rolls} qty={w.available_qty} unit={unit} />
                        {w.reserved_qty + w.committed_qty > 0.004 && <> · Dipesan {formatQty(w.reserved_qty + w.committed_qty)}</>}
                        {w.hold_qty > 0.004 && <> · Ditahan/QC {formatQty(w.hold_qty)}</>}
                        {w.wip_qty > 0.004 && <> · Proses {formatQty(w.wip_qty)}</>}
                        {w.makloon_reserved_qty > 0.004 && <> · Cadangan makloon {formatQty(w.makloon_reserved_qty)}</>}
                      </span>
                    </div>
                  ))}
                </div>
              ))}
            </Section>

            <Section title="Per PT pemilik" testId={`${testId}-entities`}>
              <table className="w-full">
                <tbody>
                  {(data.by_entity || []).map((e) => (
                    <tr key={e.entity_id} className="border-t border-[#F2F2F7]">
                      <td className="py-1">{e.entity_name}{e.own ? " · PT aktif" : ""}{!e.visible ? " · angka saja" : ""}</td>
                      <td className="py-1 text-right"><Qty rolls={e.available_rolls} qty={e.available_qty} unit={unit} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>

            <Section title="Akan datang" hint={data.definitions?.incoming} testId={`${testId}-incoming`}>
              {(data.incoming || []).length === 0 && <p className="text-[#6B6B73]">Tidak ada barang yang sedang datang.</p>}
              {(data.incoming || []).map((r, i) => (
                <div key={`${r.source}-${r.doc_id}-${i}`} className="flex flex-wrap justify-between gap-x-3 border-t border-[#F2F2F7] py-1">
                  <span>
                    <b>{SOURCE_TEXT[r.source] || r.label}</b>{r.tentative ? " (draf)" : ""} {r.number || ""}
                    <span className="text-[#6B6B73]"> · {r.owner_entity_name}{r.warehouse_name ? ` → ${r.warehouse_name}` : ""}
                      {r.warehouse_id && !r.warehouse_active ? " (gudang non-aktif)" : ""}{r.eta ? ` · ETA ${r.eta}` : ""}</span>
                  </span>
                  <span>{r.rolls ? `${formatQty(r.rolls)} roll · ` : ""}{formatQty(r.qty)} {unit}
                    <span className="ml-1 text-[12px] text-[#6B6B73]">{r.in_atp ? "· masuk ATP" : "· info"}</span></span>
                </div>
              ))}
            </Section>

            <Section title={`ATP (horizon ${data.atp?.horizon_days ?? "—"} hari)`} hint={data.definitions?.atp} testId={`${testId}-atp`}>
              {["local", "global"].map((k) => {
                const a = data.atp?.[k] || {};
                return (
                  <p key={k} className="flex flex-wrap justify-between gap-x-3 border-t border-[#F2F2F7] py-1">
                    <span className="font-semibold">{k === "local" ? "Lokal" : "Global"}</span>
                    <span>{formatQty(a.available)} + datang {formatQty(a.incoming_in_horizon)} − menunggu {formatQty(a.pending_demand)} = <b>{formatQty(a.atp)} {unit}</b></span>
                  </p>
                );
              })}
            </Section>
            <p className="mt-3 text-[12px] text-[#6B6B73]">{data.definitions?.available}</p>
          </>
        )}
      </div>
    </DetailModal>
  );
}
