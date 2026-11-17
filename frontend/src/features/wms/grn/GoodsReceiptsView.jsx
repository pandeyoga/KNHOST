import { useCallback, useEffect, useMemo, useState } from "react";
import { can } from "../../../config/roles";
import { PackageOpen, Plus, Settings } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { rememberDocEntities } from "../../../services/docEntityRegistry";
import EntityBadge from "../../../components/EntityBadge";
import { ErrorBox, GrnStatusBadge } from "./GrnBits";
import GrnCreateWizard from "./GrnCreateWizard";
import GrnDetail from "./GrnDetail";
import SupplierVariancePanel from "./SupplierVariancePanel";
import InboundScanInterface from "../InboundScanInterface";
import useReceivingMode from "../../../hooks/useReceivingMode";
import { ListToolbar, PageHeader, SearchInput } from "../../../components/ListPageParts";   // pola UI 16 Nov
import { STATUS, errText, grnApi } from "./grnApi";
import { formatDateTime } from "../../../utils/formatters";
import EmptyState, { isForbidden } from "../../../components/EmptyState";   // FIX-8 — memuat/kosong/saringan/galat/tanpa izin
import DocNumber, { docEntityId } from "../../../components/DocNumber";   // FIX-8 (UI-58) — nomor dokumen satu skema tampilan
import PageTabs from "../../../components/PageTabs";
import { OpsCount, OpsList, OpsRow, OpsSelect, OpsSplit, warehouseOptions } from "../OpsListParts";   // pola UI M26
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
  // Pola UI gelombang Gudang (M26) — Jenis ▾ (pemasok/makloon) & Gudang ▾ seperti Barang Keluar: menyaring kedatangan
  // yang sudah dimuat (server hanya menyaring status & kata cari).
  const [kindF, setKindF] = useState("");
  const [whF, setWhF] = useState("");
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
  const visible = useMemo(() => (rows || []).filter((r) => (!kindF || r.partner_type === kindF) && (!whF || r.warehouse_id === whF)),
    [rows, kindF, whF]);
  const whOptions = useMemo(() => warehouseOptions(rows, whF), [rows, whF]);
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
  const clientFilter = Boolean(kindF || whF);
  const listKind = rows && !visible.length
    ? (loadErr ? (isForbidden(loadErr) ? "forbidden" : "error") : (status || q || clientFilter) ? "filtered" : "empty")
    : rows === null ? "loading" : null;
  return (
    <div className="space-y-3 p-4 pb-28 lg:p-0 lg:pb-4" data-testid="goods-receipts-view">
      {/* Pola UI gelombang Gudang (M26, pemilik 16 Nov) — kepala satu baris + ? (keterangan tidak dipajang); tombol
          "Kedatangan baru" pindah ke ujung kanan bilah daftar (dekat daftarnya), satu tombol buat per layar. */}
      <PageHeader icon={PackageOpen} title="Barang Masuk" testId="grn-header"
        help="Kedatangan: foto Surat Jalan dibaca otomatis (OCR), lalu hitung fisik & rekonsiliasi dengan PO. Selisih Supplier: rekap selisih kedatangan per pemasok. Scan Terima per PO: penerimaan mode lama (scan per PO) untuk PT yang belum memakai Kedatangan."
        actions={canOcrSettings && (
          <a data-testid="grn-open-ocr-settings" href="?view=settings-receiving-ocr" title="Profil SJ, Sample Uji OCR, Biaya OCR & Mode Penerimaan ada di Pengaturan › Gudang, Pembelian & Produksi › Penerimaan Barang"
            className="secondary-button btn-sm"><Settings size={14} /> Pengaturan OCR</a>
        )} />
      {/* Fase 3 · P5 (L-01/L-04) — tab layar = PageTabs baku (satu baris bergulir di HP, tab aktif terlihat).
          Testid lama `grn-view-tab-*` dipertahankan. */}
      <PageTabs className="!mb-0" value={tab} onChange={setTab} ariaLabel="Tab Barang Masuk"
        tabs={tabs.map(([k, l]) => ({ key: k, label: l, testId: `grn-view-tab-${k}` }))} />
      <ErrorBox text={err} />
      {tab === "variance" ? <SupplierVariancePanel onOpenGrn={setOpenId} /> : tab === "legacy" ? (
        <div data-testid="grn-legacy-inbound">
          <InboundScanInterface user={currentUser} focusPoId={legacyPo} onFocusConsumed={() => setLegacyPo("")} onOpenPO={onOpenPO}
            onOpenDocument={onOpenDocument} />
        </div>
      ) : (<>
        {/* Bilah daftar sama dengan Barang Keluar & Cutting: Cari → Status ▾ → Jenis ▾ → Gudang ▾ → jumlah · Unduh ·
            Kedatangan baru. Dulu chip status + ruang kosong di tengah; kartu berpetak tiga kolom. Status = saringan
            server (nilai sama dengan chip lama); jenis mitra & gudang menyaring kedatangan yang sudah dimuat. */}
        <ListToolbar testId="grn-filter-bar" actions={(
          <>
            <ExportMenu dataset="goods_receipts" label="kedatangan" scope="work" testId="grn-export"
              filters={[status && ["status", "in", status.split(",")], kindF && ["partner_type", "eq", kindF],
                whF && ["warehouse_id", "eq", whF]]} search={q} sort={[{ key: "created_at", dir: "desc" }]} />
            {canCreateGrn && (
              <button data-testid="grn-new-button" className="primary-button" onClick={() => setWizard({})}><Plus size={14} /> Kedatangan baru</button>
            )}
          </>
        )}>
          <SearchInput value={q} onChange={setQ} placeholder="Nomor GRN / SJ / mitra" testId="grn-search"
            className="min-w-[220px] flex-1 sm:max-w-[320px]" />
          <OpsSelect testId="grn-status" label="Status kedatangan" value={status} onChange={setStatus} width="min-w-[160px]"
            options={FILTERS.map(([v, l]) => ({ value: v, label: v ? l : "Semua status" }))} />
          <OpsSelect testId="grn-kind" label="Jenis mitra" value={kindF} onChange={setKindF}
            options={[{ value: "", label: "Semua mitra" }, { value: "supplier", label: "Pemasok" }, { value: "makloon", label: "Makloon" }]} />
          <OpsSelect testId="grn-wh" label="Gudang" value={whF} onChange={setWhF} width="min-w-[170px]"
            searchable={whOptions.length > 9} options={whOptions} />
          <OpsCount testId="grn-count">{rows ? `${clientFilter ? visible.length : (meta?.total ?? rows.length)} kedatangan` : "Memuat…"}</OpsCount>
        </ListToolbar>
        {/* Rincian kedatangan = halaman sendiri (hitung fisik, foto, rekonsiliasi terlalu lebar untuk panel samping). */}
        <OpsSplit testId="grn-split">
          <OpsList testId="grn-list" footer={(
            <ListLimitNote meta={meta} noun="kedatangan" onMore={loadMore} loading={moreBusy} testId="grn-list-limit"
              hint={clientFilter ? "saringan jenis mitra & gudang hanya atas kedatangan yang sudah dimuat." : ""} />
          )}>
            {listKind ? (
              /* FIX-8 (B4 §3.10) — 403 = "tanpa akses", galat lain = "gagal memuat", saringan aktif = "tidak ada yang
                 cocok" (+ Reset), bukan satu teks "Belum ada kedatangan" untuk semuanya. */
              <EmptyState compact testId={rows === null ? "grn-list-loading" : "grn-list-empty"} what="kedatangan"
                error={loadErr} onRetry={load} kind={listKind}
                title={listKind === "filtered" && status && !q && !clientFilter ? `Belum ada kedatangan berstatus ${STATUS[status.split(",")[0]]?.label || "ini"}.` : undefined}
                text={listKind === "empty" ? "Catat barang yang tiba lewat tombol Kedatangan baru: foto Surat Jalan dibaca otomatis (OCR), lalu hitung fisik & rekonsiliasi dengan PO." : undefined}
                onReset={() => { setStatus(""); setQ(""); setKindF(""); setWhF(""); }} />
            ) : visible.map((r) => (
              <OpsRow key={r.id} testId={`grn-card-${r.id}`} onOpen={() => setOpenId(r.id)}
                title={(
                  <>
                    <DocNumber number={r.number} entityId={docEntityId(r)} className="font-mono" testId={`grn-number-${r.id}`} />
                    {r.work_entity_id && <EntityBadge entityId={r.work_entity_id} />}
                  </>
                )}
                status={<GrnStatusBadge status={r.status} />}
                lines={[
                  r.partner_name,
                  // FIX-1 (B1 UI-38) — baris menyebut gudang tujuan & PT pemilik (dulu tanpa gudang).
                  <span data-testid={`grn-card-wh-${r.id}`}>{r.warehouse_name || "Gudang belum diisi"}</span>,
                  <>{r.dn_number ? <>SJ <span className="font-mono">{r.dn_number}</span></> : "Nomor SJ belum diisi"} · {r.lines} baris · {r.pages} halaman</>,
                ]}
                aside={(
                  <>
                    {r.open_blockers > 0 && <span className="block font-semibold text-kn-danger-text">{r.open_blockers} selisih pemblokir</span>}
                    <span className="block">{formatDateTime(r.created_at)} · {r.created_by}</span>
                  </>
                )} />
            ))}
          </OpsList>
        </OpsSplit>
      </>)}
      {wizard && <GrnCreateWizard preset={wizard} onClose={() => setWizard(null)} onCreated={(g) => { setWizard(null); setOpenId(g.id); }} />}
    </div>
  );
}
