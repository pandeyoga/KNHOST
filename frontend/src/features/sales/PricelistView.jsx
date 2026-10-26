/**
 * PricelistView (F1a → FASE E-4 · E4.7) — HARGA JUAL PER BADAN USAHA.
 *
 * Keputusan pemilik #4: harga master GLOBAL + **override per badan usaha**, dan
 * "UI override harus jelas, nilai yang berasal dari global WAJIB berlabel".
 *
 * Karena itu layar ini menampilkan TIGA angka bersebelahan, bukan satu:
 *      Harga global   ·   Harga badan usaha ini   ·   Harga efektif (+ lencana asal)
 * Tanpa itu, pengguna melihat satu angka dan tidak tahu apakah ia sedang mengubah
 * harga seluruh grup atau harga satu badan usaha saja — kesalahan yang mahal.
 *
 * Yang bisa dilakukan di sini:
 *   · **Set harga** badan usaha (dengan masa berlaku; record lama ditutup otomatis)
 *   · **Kembalikan ke global** — melepas override tanpa menghapus riwayat
 *   · **Riwayat harga** per produk (termasuk yang terjadwal & kadaluarsa)
 *   · **Ekspor/impor CSV** lewat server (satu permintaan, laporan galat per SKU)
 *
 * Urutan harga di pesanan/POS: harga khusus disetujui → pelanggan → badan usaha →
 * global. Layar ini mengelola lapisan **badan usaha**; lapisan pelanggan ada di
 * "Harga per Pelanggan".
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Tag, RefreshCw, Search, Plus, History, X, Download, Upload,
  CheckCircle2, AlertTriangle, Building2, RotateCcw, CalendarClock, ArrowUp, ArrowDown,
} from "lucide-react";
import { SetPriceModal, HistoryModal, fmtDate } from "./PricelistModals";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import usePagedRows from "@/hooks/usePagedRows";
import EntityBadge from "../../components/EntityBadge";
import EntityRequiredNotice from "../../components/EntityRequiredNotice";
import { entityShortById } from "../../utils/entityLabel";
import usePriceEntity, { isActiveEntity } from "./usePriceEntity";
import { formatCurrency, todayWib } from "../../utils/formatters";
import { can } from "../../config/roles";

// Lencana ASAL harga — sengaja memakai kata yang sama dengan POS/keranjang
// (`hooks/useEffectivePrices.PRICE_SOURCE_META`) supaya pengguna tidak perlu
// menerjemahkan istilah dua kali.
const SOURCE_META = {
  entity: { label: "Badan usaha ini", tone: "bg-[#F3E9FA] text-[#6B219A]" },
  global: { label: "Global", tone: "bg-[#F5F5F7] text-[#6B6B73]" },
  // Produk yang BELUM punya harga jual sama sekali (mis. barang sisa / kain grey).
  // Dulu ditampilkan sebagai "Rp 0 · Global" — pembacaan yang berbahaya karena
  // seolah-olah harga jualnya memang nol dan boleh dipakai di pesanan/POS.
  none: { label: "Belum ada harga", tone: "bg-[#FDEDE7] text-[#C0392B]" },
};

/** Angka rupiah, tetapi 0/kosong ditulis apa adanya: belum ditetapkan. */
function PriceCell({ value }) {
  if (value == null || Number(value) === 0) {
    return <span className="text-[10.5px] font-normal italic text-[#C0392B]">belum ditetapkan</span>;
  }
  return <>{formatCurrency(value)}</>;
}

export default function PricelistView({ entities = [], selectedEntity, currentUser }) {
  const canManage = can(currentUser?.permissions, "pricelist", "manage");   // Sisir gerbang peran (2026-10-20) — tulis daftar harga
  const activeList = entities.filter(isActiveEntity);
  // Fase 3 · P3 (D-14) — PT = PT di kepala aplikasi (pemilih lokal `pl-entity-select` dihapus); header "Semua" →
  // kartu "Pilih badan usaha" yang mengganti header.
  const entityId = usePriceEntity(selectedEntity, entities);
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [priceModal, setPriceModal] = useState(null);    // { row }
  const [historyRow, setHistoryRow] = useState(null);    // { row }
  const [busyRow, setBusyRow] = useState("");
  const [onlyOverride, setOnlyOverride] = useState(false);

  const entityName = entityShortById(activeList, entityId);

  const load = useCallback(async () => {
    if (!entityId) { setRows([]); setSummary(null); setLoading(false); return; }
    setLoading(true); setError("");
    try {
      const res = await axios.get(`${API}/pricelist`, { params: { entity_id: entityId, search } });
      setRows(res.data?.rows || []);
      setSummary(res.data?.summary || null);
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat pricelist.");
    } finally {
      setLoading(false);
    }
  }, [entityId, search]);

  useEffect(() => { load(); }, [load]);

  const shown = useMemo(
    () => (onlyOverride ? rows.filter((r) => r.entity_price != null) : rows),
    [rows, onlyOverride]);
  const pgShown = usePagedRows(shown, { pageSize: 25, testId: "pricelist-pager" });

  // Produk tanpa harga jual di lapisan mana pun — wajib terlihat, bukan disembunyikan
  // sebagai "Rp 0" yang seolah-olah harga sah.
  const noPriceCount = useMemo(
    () => rows.filter((r) => r.effective_price == null || Number(r.effective_price) === 0).length,
    [rows]);

  const exportCsv = async () => {
    setError("");
    try {
      const res = await axios.get(`${API}/pricelist/export`, {
        params: { entity_id: entityId, only_with_price: false }, responseType: "blob",
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `harga-${entityName}-${todayWib()}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal mengunduh CSV harga.");
    }
  };

  const importCsv = async (file) => {
    if (!file) return;
    setNotice(""); setError("");
    try {
      const text = await file.text();
      const res = await axios.post(`${API}/pricelist/import`, { entity_id: entityId, csv_text: text });
      const d = res.data || {};
      setNotice(`Impor selesai: ${d.applied || 0} harga diterapkan${d.skipped ? `, ${d.skipped} dilewati` : ""}.`);
      if ((d.errors || []).length) setError(d.errors.slice(0, 5).join(" "));
      load();
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal membaca berkas CSV.");
    }
  };

  const revertToGlobal = async (row) => {
    setNotice(""); setError(""); setBusyRow(row.product_id);
    try {
      const res = await axios.delete(`${API}/pricelist/override/${row.product_id}`,
        { params: { entity_id: entityId } });
      setNotice(`${row.product_name} kembali memakai harga global ${formatCurrency(res.data?.global_price || row.global_price)}.`);
      load();
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal mengembalikan ke harga global.");
    } finally {
      setBusyRow("");
    }
  };

  // D-14 — header "Semua badan usaha": harga berlaku per PT → pilih PT di kartu (= mengganti PT di kepala aplikasi).
  if (!entityId) {
    return (
      <div data-testid="pricelist-view">
        <EntityRequiredNotice what="harga per badan usaha" testId="pl-entity-required"
          reason="Harga khusus badan usaha berlaku per PT. Pilihan Anda mengganti badan usaha di kepala aplikasi (berlaku di semua layar)." />
      </div>
    );
  }

  return (
    <div data-testid="pricelist-view">
      <div className="mb-3 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi testId="pl-kpi-products" label="Produk" value={summary?.products ?? rows.length} icon={Tag} />
        <Kpi testId="pl-kpi-override" label={`Harga khusus ${entityName}`}
          value={summary?.with_entity_price ?? 0} icon={Building2} tone="text-[#6B219A]" />
        <Kpi testId="pl-kpi-global" label="Ikut harga global"
          value={summary?.following_global ?? 0} icon={Tag} tone="text-[#8E8E93]" />
        <div className="section-card" data-testid="pl-kpi-entity">
          <div className="section-body flex items-center gap-3 py-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#F3EAFB]">
              <Building2 size={17} className="text-[#6B219A]" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">Badan usaha</p>
              <EntityBadge entityId={entityId} entities={entities} />
              {summary?.scheduled > 0 && (
                <p data-testid="pl-kpi-scheduled" className="mt-0.5 text-[10px] font-semibold text-[#0058CC]">
                  <CalendarClock size={9} className="inline" /> {summary.scheduled} harga terjadwal
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="section-card">
        <div className="section-head flex-wrap gap-2">
          <div className="flex flex-wrap items-center gap-2">
            {/* D-14 — tanpa pemilih PT lokal: PT mengikuti kepala aplikasi (lencana di kartu "Badan usaha"). */}
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#9A9BA3]" />
              <input data-testid="pl-search" className="field w-[220px] py-1.5 pl-8 text-[12px]"
                placeholder="Cari SKU / nama / kategori"
                value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
            <label className="flex cursor-pointer items-center gap-1.5 text-[11.5px] text-[#3C3C43]">
              <input data-testid="pl-filter-override" type="checkbox" checked={onlyOverride}
                onChange={(e) => setOnlyOverride(e.target.checked)} />
              Hanya yang punya harga khusus
            </label>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button data-testid="pl-export" className="btn-secondary inline-flex items-center gap-1 px-3 py-1.5 text-[12px]"
              onClick={exportCsv}><Download size={13} /> Ekspor</button>
            {canManage && (
              <label data-testid="pl-import" className="btn-secondary inline-flex cursor-pointer items-center gap-1 px-3 py-1.5 text-[12px]">
                <Upload size={13} /> Impor
                <input type="file" accept=".csv" className="hidden"
                  onChange={(e) => { importCsv(e.target.files?.[0]); e.target.value = ""; }} />
              </label>
            )}
            <button data-testid="pl-refresh" className="icon-button" onClick={load} aria-label="Muat ulang">
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            </button>
          </div>
        </div>
        <div className="section-body">
          <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="pl-error" />
          {notice && (
            <div data-testid="pl-notice"
              className="mb-3 flex items-center gap-2 rounded-md border border-[#BDE5CC] bg-[#E6F6EC] px-3 py-2 text-[12px] text-[#1B7F4B]">
              <CheckCircle2 size={14} />{notice}
              <button className="ml-auto" onClick={() => setNotice("")} aria-label="Tutup"><X size={13} /></button>
            </div>
          )}
          <p className="mb-2 text-[11px] text-[#8E8E93]" data-testid="pl-explainer">
            Harga <b>global</b> berlaku untuk semua badan usaha. Harga <b>{entityName}</b> menimpanya
            hanya untuk badan usaha ini. Pesanan &amp; POS memakai kolom <b>harga efektif</b>.
          </p>
          {!loading && noPriceCount > 0 && (
            <p data-testid="pl-noprice-hint"
              className="mb-2 flex items-center gap-1.5 rounded-md border border-[#F5C97B] bg-[#FFF7E6] px-2.5 py-1.5 text-[11px] text-[#8C4A00]">
              <AlertTriangle size={12} />
              <span>
                <b>{noPriceCount} produk</b> belum punya harga jual — baik global maupun {entityName}.
                Tetapkan harganya sebelum produk itu dipakai di pesanan atau POS.
              </span>
            </p>
          )}

          {loading ? (
            <div className="grid gap-2" data-testid="pl-loading">
              {[0, 1, 2, 3, 4].map((i) => <div key={i} className="h-10 animate-pulse rounded bg-[#F5F5F7]" />)}
            </div>
          ) : shown.length === 0 ? (
            <div data-testid="pl-empty" className="py-12 text-center text-[12px] text-[#8E8E93]">
              <Tag size={26} className="mx-auto mb-2 text-gray-300" />
              {onlyOverride ? `Belum ada harga khusus untuk ${entityName}.` : "Tidak ada produk."}
            </div>
          ) : (
            /* Audit UI 24 Okt (014, HP) — tabel diberi lebar minimum: dulu kolom Produk terjepit 1 kata/baris dan
               tombol aksi keluar layar; kini tabel digeser utuh di dalam wadahnya. */
            <div className="overflow-auto rounded-md border border-[#EFF0F2]">
              <table className="w-full min-w-[900px] text-[12px]">
                <thead>
                  <tr className="whitespace-nowrap border-b border-[#EFF0F2] bg-[#FAFBFC] text-left text-[10.5px] font-bold uppercase text-[#8E8E93]">
                    <th className="px-3 py-2">SKU</th>
                    <th className="px-3 py-2">Produk</th>
                    <th className="px-3 py-2 text-right">Harga global</th>
                    <th className="px-3 py-2 text-right">Harga {entityName}</th>
                    <th className="px-3 py-2 text-right">Harga efektif</th>
                    <th className="px-3 py-2 text-center">Asal</th>
                    <th className="px-3 py-2 text-right">Aksi</th>
                  </tr>
                </thead>
                <caption className="caption-bottom px-3 py-2">{shown.length > 25 && pgShown.pager}</caption>
                <tbody>
                  {pgShown.pageRows.map((r) => {
                    const has = r.entity_price != null;
                    // Tanpa harga efektif = belum ada harga jual di lapisan mana pun.
                    const noPrice = r.effective_price == null || Number(r.effective_price) === 0;
                    const sm = noPrice ? SOURCE_META.none : (SOURCE_META[r.price_source] || SOURCE_META.global);
                    return (
                      <tr key={r.product_id} data-testid={`pl-row-${r.product_id}`}
                        className="border-b border-[#F5F5F7] last:border-0 hover:bg-[#FBF8FE]">
                        <td className="whitespace-nowrap px-3 py-2 font-mono text-[11px] text-[#6B6B73]">{r.sku}</td>
                        <td className="min-w-[200px] px-3 py-2">
                          <span className="font-medium text-[#1C1C1E]">{r.product_name}</span>
                          <span className="block text-[11px] text-[#8E8E93]">
                            {r.category} · per {r.base_unit}
                            {r.scheduled_count > 0 && (
                              <span data-testid={`pl-scheduled-${r.product_id}`} className="ml-1 font-semibold text-[#0058CC]">
                                · {r.scheduled_count} terjadwal
                              </span>
                            )}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums text-[#6B6B73]"
                          data-testid={`pl-global-${r.product_id}`}>
                          <PriceCell value={r.global_price} />
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums" data-testid={`pl-entity-${r.product_id}`}>
                          {has ? (
                            <>
                              <span className="font-semibold text-[#6B219A]">{formatCurrency(r.entity_price)}</span>
                              <span className={`block text-[9.5px] font-semibold ${
                                r.diff_vs_global > 0 ? "text-[#1B7F4B]" : r.diff_vs_global < 0 ? "text-[#C0392B]" : "text-[#8E8E93]"}`}>
                                {r.diff_vs_global > 0 ? <ArrowUp size={8} className="inline" />
                                  : r.diff_vs_global < 0 ? <ArrowDown size={8} className="inline" /> : null}
                                {r.diff_vs_global === 0 ? "sama dengan global"
                                  : `${formatCurrency(Math.abs(r.diff_vs_global))} lebih ${r.diff_vs_global > 0 ? "mahal" : "murah"}`}
                                {r.valid_until ? ` · s.d. ${fmtDate(r.valid_until)}` : ""}
                              </span>
                            </>
                          ) : (
                            <span className="text-[11px] text-[#9A9BA3]">ikut global</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right font-semibold tabular-nums text-[#1C1C1E]"
                          data-testid={`pl-eff-${r.product_id}`}>
                          <PriceCell value={r.effective_price} />
                        </td>
                        <td className="px-3 py-2 text-center">
                          <span data-testid={`pl-source-${r.product_id}`}
                            className={`rounded px-1.5 py-0.5 text-[9px] font-bold ${sm.tone}`}>{sm.label}</span>
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 text-right">
                          <button data-testid={`pl-history-${r.product_id}`} className="icon-button" title="Riwayat harga"
                            onClick={() => setHistoryRow(r)}><History size={14} /></button>
                          {canManage && has && (
                            <button data-testid={`pl-revert-${r.product_id}`}
                              className="secondary-button ml-1 text-[11px]" disabled={busyRow === r.product_id}
                              title="Lepas harga khusus, kembali ke harga global"
                              onClick={() => revertToGlobal(r)}>
                              <RotateCcw size={12} /> Ke global
                            </button>
                          )}
                          {canManage && (
                            <button data-testid={`pl-setprice-${r.product_id}`}
                              className="secondary-button ml-1 !py-1 text-[11px]" onClick={() => setPriceModal(r)}>
                              <Plus size={12} /> {has ? "Ubah harga" : "Atur harga"}
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {priceModal && (
        <SetPriceModal row={priceModal} entityId={entityId} entityName={entityName}
          onClose={() => setPriceModal(null)}
          onSaved={() => { setPriceModal(null); setNotice(`Harga ${priceModal.product_name} tersimpan untuk ${entityName}.`); load(); }}
          onError={setError} />
      )}
      {historyRow && (
        <HistoryModal row={historyRow} entityId={entityId} entities={entities} canManage={canManage}
          onClose={() => setHistoryRow(null)} onChanged={() => { load(); }} />
      )}
    </div>
  );
}

function Kpi({ label, value, icon: Icon, tone = "", testId }) {
  return (
    <div className="section-card" data-testid={testId}>
      <div className="section-body flex items-center gap-3 py-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#F3EAFB]">
          <Icon size={17} className="text-[#6B219A]" />
        </div>
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p>
          <p className={`truncate text-[17px] font-bold tabular-nums ${tone || "text-[#1C1C1E]"}`}
            data-testid={`${testId}-value`}>{value}</p>
        </div>
      </div>
    </div>
  );
}
