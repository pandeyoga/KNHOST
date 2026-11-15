import { useCallback, useEffect, useState } from "react";
import { can } from "../../../config/roles";
import { Plus, Settings } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { rememberDocEntities } from "../../../services/docEntityRegistry";
import EntityBadge from "../../../components/EntityBadge";
import { ErrorBox, GrnStatusBadge } from "./GrnBits";
import GrnCreateWizard from "./GrnCreateWizard";
import GrnDetail from "./GrnDetail";
import SupplierVariancePanel from "./SupplierVariancePanel";
import InboundScanInterface from "../InboundScanInterface";
import useReceivingMode from "../../../hooks/useReceivingMode";
import { SearchBox } from "../../../components/ListControls";
import { STATUS, errText, grnApi } from "./grnApi";
import { formatDateTime } from "../../../utils/formatters";
import EmptyState, { isForbidden } from "../../../components/EmptyState";   // FIX-8 — memuat/kosong/saringan/galat/tanpa izin
import DocNumber, { docEntityId } from "../../../components/DocNumber";   // FIX-8 (UI-58) — nomor dokumen satu skema tampilan
import PageTabs from "../../../components/PageTabs";
import FilterChips from "../../../components/FilterChips";
import ExportMenu from "../../../components/ExportMenu";   // FIX-4 — tombol baku Unduh (Excel/CSV, Pusat Export)
import ListLimitNote, { metaFromHeaders } from "../ListLimitNote";   // FIX-5 (LST-01)

const FILTERS = [["", "Semua"], ["draft,review", "Tinjau SJ"], ["counting", "Hitung"], ["reconcile,closing", "Rekonsiliasi"], ["closed", "Ditutup"], ["rejected,cancelled", "Batal/Tolak"]];
const mkoPreset = () => {
  const q = new URLSearchParams(window.location.search);
  return q.get("mko") ? { partner_type: "makloon", partner_id: q.get("makloon") || "", warehouse_id: q.get("wh") || "", po_ids: [q.get("mko")] } : null;
};

/** Operasi Gudang → Barang Masuk: Kedatangan (SJ & OCR) · Selisih Supplier · Scan Terima PO (mode lama). */
export default function GoodsReceiptsView({ currentUser, selectedEntity, focusDoc, onClearFocus, onOpenPO, onOpenDocument }) {
  const [tab, setTab] = useState("list");
  const [rows, setRows] = useState(null);   // 23 Okt — null = sedang dimuat (dulu [] → "Belum ada kedatangan" saat memuat)
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [openId, setOpenId] = useState(() => new URLSearchParams(window.location.search).get("grn") || "");
  const [wizard, setWizard] = useState(mkoPreset);
  const [legacyPo, setLegacyPo] = useState("");
  const [err, setErr] = useState("");
  const [loadErr, setLoadErr] = useState(null);   // FIX-8 (B1b UI-49) — galat muat daftar (403 ≠ "belum ada")
  const { isGrn, entityOf } = useReceivingMode();
  const grnOnly = selectedEntity && selectedEntity !== "all" && isGrn(selectedEntity) && !(entityOf(selectedEntity)?.legacy_in_flight || []).length;
  // PR-T7 (#20) — tab "Scan Terima per PO" (mode lama) = `wms.update` (POST /inbound/tasks/* — pemindaian terima);
  // pintasan Pengaturan OCR = boleh membuka salah satu tab layar tujuannya (`ReceivingOcrSettings`): goods_receipt.review
  // (Profil SJ, Sample Uji OCR) · .approve (Biaya OCR) · .configure (Mode Penerimaan). Dulu daftar nama peran.
  const showLegacy = can(currentUser?.permissions, "wms", "update") && !grnOnly;
  const canOcrSettings = ["review", "approve", "configure"].some((a) => can(currentUser?.permissions, "goods_receipt", a));
  const canCreateGrn = can(currentUser?.permissions, "goods_receipt", "create");   // FE-04 — POST /goods-receipts
  // FIX-1 (K-B1-02) — kedatangan lintas PT di gedung lokasi kerja: buka/aksi GRN dikirim atas nama PT GRN.
  // FIX-5 (B3b LST-01) — dulu 100 kedatangan terbaru dipotong diam-diam (angka chip = baris termuat): kini jumlah
  // sungguhan dari server + "Muat berikutnya".
  const [meta, setMeta] = useState(null);
  const [moreBusy, setMoreBusy] = useState(false);
  const load = useCallback(() => grnApi.listPage({ status, q }).then(({ rows: r, res }) => {
    const list = rememberDocEntities(r);
    setRows(list);
    setMeta(metaFromHeaders(res, list.length, 0));
    setLoadErr(null);
  }).catch((e) => { setErr(errText(e)); setLoadErr(e); setRows((r) => r || []); }), [status, q]);
  const loadMore = async () => {
    setMoreBusy(true);
    try {
      const { rows: r, res } = await grnApi.listPage({ status, q, skip: (rows || []).length });
      const list = rememberDocEntities(r);
      const next = [...(rows || []), ...list];
      setRows(next);
      setMeta(metaFromHeaders(res, next.length, 0));
    } catch (e) { setErr(errText(e)); } finally { setMoreBusy(false); }
  };
  useEffect(() => { if (!openId) load(); }, [load, openId, selectedEntity]);
  useEffect(() => {
    if (!focusDoc?.focus_id) return;
    if (focusDoc.focus_type === "goods_receipt") setOpenId(focusDoc.focus_id);
    if (focusDoc.focus_type === "purchase_order" && focusDoc.tab === "inbound" && showLegacy) {
      setTab("legacy"); setLegacyPo(focusDoc.focus_id);
    } else if (focusDoc.focus_type === "purchase_order" && focusDoc.tab === "inbound" && !canCreateGrn && onOpenDocument) {
      // PK-44 — tautan tugas terima (Jejak Dokumen) = PO induknya. Peran yang tidak memindai terima dan tidak membuat
      // kedatangan dibuka di rincian PO-nya (bukan wizard kedatangan baru yang pasti ditolak).
      onOpenDocument({ view: "purchasing", focus_type: "purchase_order", focus_id: focusDoc.focus_id, origin: focusDoc.origin });
    } else if (focusDoc.focus_type === "purchase_order") {
      axios.get(`${API}/purchase-orders/${focusDoc.focus_id}`).then((r) => setWizard({
        partner_type: "supplier", partner_id: r.data.supplier_id, warehouse_id: r.data.warehouse_id, po_ids: [r.data.id],
      })).catch((e) => setErr(errText(e)));
    }
    onClearFocus?.();
  }, [focusDoc, onClearFocus]); // eslint-disable-line react-hooks/exhaustive-deps

  if (openId) return <div className="p-4 pb-28 lg:p-0 lg:pb-4"><GrnDetail grnId={openId} user={currentUser} onBack={() => setOpenId("")} /></div>;
  const tabs = [["list", "Kedatangan (SJ & OCR)"], ["variance", "Selisih Supplier"], ...(showLegacy ? [["legacy", "Scan Terima per PO"]] : [])];
  return (
    <div className="space-y-3 p-4 pb-28 lg:p-0 lg:pb-4" data-testid="goods-receipts-view">
      {/* Fase 3 · P5 (L-01/L-04) — tab layar = PageTabs baku (satu baris bergulir di HP, tab aktif terlihat);
          status = FilterChips. Testid lama `grn-view-tab-*` / `grn-filter-*` dipertahankan. */}
      <div className="flex flex-wrap items-end justify-between gap-2">
        <PageTabs className="!mb-0 min-w-0 flex-1" value={tab} onChange={setTab} ariaLabel="Tab Barang Masuk"
          tabs={tabs.map(([k, l]) => ({ key: k, label: l, testId: `grn-view-tab-${k}` }))} />
        <div className="flex items-center gap-2 pb-1">
          {canOcrSettings && (
            <a data-testid="grn-open-ocr-settings" href="?view=settings-receiving-ocr" title="Profil SJ, Sample Uji OCR, Biaya OCR & Mode Penerimaan ada di Pengaturan › Gudang, Pembelian & Produksi › Penerimaan Barang"
              className="secondary-button !py-1 text-[11px]"><Settings size={12} /> Pengaturan OCR</a>
          )}
          {canCreateGrn && tab === "list" && (
            <button data-testid="grn-new-button" className="primary-button" onClick={() => setWizard({})}><Plus size={13} /> Kedatangan baru</button>
          )}
        </div>
      </div>
      <ErrorBox text={err} />
      {tab === "variance" ? <SupplierVariancePanel onOpenGrn={setOpenId} /> : tab === "legacy" ? (
        <div className="section-card" data-testid="grn-legacy-inbound">
          <div className="section-head">
            <div className="flex items-center gap-2 min-w-0">
              <span className="kicker">Scan Terima PO</span>
              <h2>Penerimaan per Pesanan Pembelian (scan per PO)</h2>
            </div>
            <span className="text-[11px] text-[#6B6B73]">Scan barcode di formulir tugas di bawah</span>
          </div>
          <div className="section-body">
            <InboundScanInterface user={currentUser} focusPoId={legacyPo} onFocusConsumed={() => setLegacyPo("")} onOpenPO={onOpenPO}
              onOpenDocument={onOpenDocument} />
          </div>
        </div>
      ) : (<>
        {/* UAT 24 Okt (audit UI 052) — filter status berbentuk chip, bukan tab-bar kedua yang kembar dengan tab layar
            di atasnya (dulu terlihat seperti dua baris tab yang sama). */}
        <div className="flex flex-wrap items-center gap-2" data-testid="grn-filter-bar">
          <SearchBox value={q} onChange={setQ} placeholder="Nomor GRN / SJ / mitra" testId="grn-search" />
          <span className="text-[11px] font-semibold text-[#6B6B73]">Status:</span>
          <FilterChips className="min-w-0 max-w-full" ariaLabel="Status kedatangan" value={status || "all"}
            onChange={(k) => setStatus(k === "all" ? "" : k)} chipTestId={(k) => `grn-filter-${k}`}
            options={FILTERS.map(([v, l]) => ({ key: v || "all", label: l,
              count: (status || "all") === (v || "all") && rows ? (meta?.total ?? rows.length) : undefined }))} />
          <ExportMenu dataset="goods_receipts" label="kedatangan" scope="work" testId="grn-export" className="ml-auto"
            filters={[status && ["status", "in", status.split(",")]]} search={q} sort={[{ key: "created_at", dir: "desc" }]} />
        </div>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3" data-testid="grn-list">
          {rows === null && <div className="col-span-full"><EmptyState kind="loading" what="kedatangan" compact testId="grn-list-loading" /></div>}
          {(rows || []).map((r) => (
            <button key={r.id} data-testid={`grn-card-${r.id}`} onClick={() => setOpenId(r.id)}
              className="rounded-xl border border-[#EFF0F2] bg-white p-3 text-left transition-shadow hover:shadow-md">
              <div className="flex items-center justify-between">
                <DocNumber number={r.number} entityId={docEntityId(r)} className="font-mono text-[12px]" testId={`grn-number-${r.id}`} />
                <GrnStatusBadge status={r.status} />
              </div>
              <p className="mt-1 text-[12px] font-semibold">{r.partner_name}</p>
              {/* FIX-1 (B1 UI-38) — kartu menyebut gudang tujuan & PT pemilik (dulu tanpa gudang). */}
              <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[11px] text-[#3A3B42]" data-testid={`grn-card-wh-${r.id}`}>
                {r.warehouse_name || "Gudang belum diisi"}{r.work_entity_id && <EntityBadge entityId={r.work_entity_id} />}
              </p>
              <p className="text-[10.5px] text-[#6B6B73]">{r.dn_number ? <>SJ <span className="font-mono">{r.dn_number}</span></> : "Nomor SJ belum diisi"} · {r.lines} baris · {r.pages} halaman</p>
              {r.open_blockers > 0 && <p className="mt-1 text-[10.5px] font-semibold text-[#B4231F]">{r.open_blockers} selisih pemblokir</p>}
              <p className="mt-1 text-[10px] text-[#8E8E93]">{formatDateTime(r.created_at)} · {r.created_by}</p>
            </button>
          ))}
          <div className="col-span-full"><ListLimitNote meta={meta} noun="kedatangan" onMore={loadMore} loading={moreBusy} testId="grn-list-limit" /></div>
          {rows && !rows.length && (
            <div className="col-span-full w-full">
              {/* FIX-8 (B4 §3.10) — 403 = "tanpa akses", galat lain = "gagal memuat", saringan aktif = "tidak ada yang cocok"
                  (+ Reset), bukan satu teks "Belum ada kedatangan" untuk semuanya. */}
              <EmptyState testId="grn-list-empty" what="kedatangan" error={loadErr} onRetry={load}
                kind={loadErr ? (isForbidden(loadErr) ? "forbidden" : "error") : (status || q) ? "filtered" : "empty"}
                title={!loadErr && status ? `Belum ada kedatangan berstatus ${STATUS[status.split(",")[0]]?.label || "ini"}.` : undefined}
                text={!loadErr && !status && !q ? "Catat barang yang tiba: foto Surat Jalan dibaca otomatis (OCR), lalu hitung fisik & rekonsiliasi dengan PO." : undefined}
                onReset={() => { setStatus(""); setQ(""); }}
                actionLabel={canCreateGrn ? "Kedatangan baru" : undefined} onAction={canCreateGrn ? () => setWizard({}) : undefined} />
            </div>
          )}
        </div>
      </>)}
      {wizard && <GrnCreateWizard preset={wizard} onClose={() => setWizard(null)} onCreated={(g) => { setWizard(null); setOpenId(g.id); }} />}
    </div>
  );
}
