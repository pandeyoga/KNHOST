import { useEffect, useState } from "react";
import { AlertTriangle, Package, RefreshCw, X } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { rememberDocEntities } from "../../services/docEntityRegistry";
import ErrorNotice from "../../components/ErrorNotice";
import { apiErrorText } from "../../utils/apiError";
import { notifySuccess } from "../../utils/feedback";
import FormModal from "../../components/FormModal";
import GRCatchWeightModal from "./inbound/GRCatchWeightModal";
import InboundTaskPanel, { TaskBadge } from "./inbound/InboundTaskPanel";
import { hasRolls, rollsText } from "../../components/QtyDual";
import useReceivingUom from "../../hooks/useReceivingUom";
import { formatQty } from "../../utils/formatters";
import RollLabelActions from "../../components/RollLabelActions";
import { kgPerBaseUnit } from "../../utils/uom";
import { parseDecimal } from "../../utils/decimalInput";
import ScanLabelStatsCard from "./inbound/ScanLabelStatsCard";
import { askReason, askText } from "../../services/confirmService";
import useReceivingMode from "../../hooks/useReceivingMode";
import { can } from "../../config/roles";
import ExportMenu from "../../components/ExportMenu";   // FIX-4 — tombol baku Unduh (Excel/CSV, Pusat Export)
import ListLimitNote, { metaFromHeaders } from "./ListLimitNote";   // FIX-7 (B3b LST-01)
import { ListToolbar, SearchInput } from "../../components/ListPageParts";
import EmptyState, { listStateKind } from "../../components/EmptyState";
import { OpsCount, OpsList, OpsRow, OpsSelect, OpsSplit, warehouseOptions } from "./OpsListParts";   // pola UI M26

function MiniBar({ pct, status }) {
  const color = status === 'completed' ? 'bg-[#34C759]' : status === 'escalated' ? 'bg-red-400' : 'bg-[#007AFF]';
  return (
    <div className="h-1 w-full rounded-full bg-gray-200 overflow-hidden">
      <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  );
}

const EMPTY_SCAN = { doc_uom: "", doc_qty: "", batch: "", lot: "", dye_lot: "",
                     grade: "A", roll_id: "", bin_id: "" };

export default function InboundScanInterface({ user, focusPoId = "", onFocusConsumed, onOpenPO, onOpenDocument }) {
  const { isGrn, data: modeData } = useReceivingMode();
  const grnEntities = (modeData?.entities || []).filter((e) => e.mode === "grn");
  const [tasks, setTasks] = useState([]);
  const shownTasks = tasks.filter((t) => !isGrn(t.entity_id) || t.legacy_in_flight);   // GRN Fase 7
  const canOverride = can(user?.permissions, "wms", "approve");
  const [loading, setLoading] = useState(false);
  const [fetched, setFetched] = useState(false);
  const [error, setError] = useState("");
  const [selectedTask, setSelectedTask] = useState(null);
  const [filterStatus, setFilterStatus] = useState("all");
  // Pola UI gelombang Gudang (M26) — cari & saringan gudang di layar (atas tugas termuat), sama dengan Barang Keluar.
  const [q, setQ] = useState("");
  const [whFilter, setWhFilter] = useState("");
  const [loadErr, setLoadErr] = useState(null);   // galat muat daftar (403 ≠ "tidak ada tugas")
  const term = q.toLowerCase().trim();
  const visibleTasks = shownTasks.filter((t) => (!whFilter || t.warehouse_id === whFilter) && (!term
    || [t.po_number, t.supplier_name, t.product_name, t.sku, t.warehouse_name].filter(Boolean).join(" ").toLowerCase().includes(term)));
  const whOptions = warehouseOptions(shownTasks, whFilter);

  const [cameraActive, setCameraActive] = useState(false);
  const [scanData, setScanData] = useState(EMPTY_SCAN);

  const [showEscalateModal, setShowEscalateModal] = useState(false);
  const [escalationReason, setEscalationReason] = useState("");
  // FASE P5 — galat eskalasi tampil DI DALAM pop-upnya (lihat OutboundScanInterface).
  const [escalateError, setEscalateError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Fase 8 (Catch-weight) — entri roll saat Goods Receipt (panjang m + berat kg per roll).
  const [products, setProducts] = useState({});
  const [showGRModal, setShowGRModal] = useState(false);
  const [grRolls, setGrRolls] = useState([]);
  // FASE C (D-10/D-27) — identitas lot batch penerimaan + kebijakan penegakan
  const [lotFields, setLotFields] = useState({ supplier_lot: "", lot_number: "", shade_ref: "", supplier_dn: "" });
  const [lotSettings, setLotSettings] = useState(null);
  const [lotResult, setLotResult] = useState(null);   // {lots:[], warnings:[]}
  const round2 = (n) => Math.round((Number(n) + Number.EPSILON) * 100) / 100;
  // FASE B/C — berat per BASE UNIT produk (yard ≠ meter) → prefill GR sama dgn server.
  const kgPerMeter = (p) => kgPerBaseUnit(p);

  // FASE F-1 — opsi satuan (termasuk satuan supplier) + pratinjau konversi dari server
  const uom = useReceivingUom(selectedTask?.id);

  useEffect(() => {
    axios.get(`${API}/products`).then((r) => {
      const m = {};
      (r.data || []).forEach((p) => { m[p.id] = p; });
      setProducts(m);
    }).catch(() => { /* opsional */ });
  }, []);

  useEffect(() => { fetchTasks(); }, [filterStatus]);

  // Jembatan PO → Gudang ("Terima Barang" di detail PO): pilih tugas penerimaan PO itu
  // yang masih terbuka (bila semua selesai, tugas terbaru) lalu gulir ke barisnya.
  useEffect(() => {
    if (!focusPoId || loading || !fetched) return;
    const mine = shownTasks.filter((x) => x.po_id === focusPoId);
    const t = mine.find((x) => !["completed", "put_away"].includes(x.status)) || mine[0];
    if (t) {
      selectTask(t);
      setTimeout(() => document.querySelector(`[data-testid="inbound-task-${t.id}"]`)?.scrollIntoView({ block: "center" }), 50);
    } else if (shownTasks.length) {
      setError("Belum ada tugas penerimaan untuk PO ini — PO mungkin belum disetujui.");
    }
    onFocusConsumed?.();
  }, [focusPoId, tasks, loading, fetched]); // eslint-disable-line

  // FASE C — kebijakan penegakan lot (warn/block) ditarik sekali untuk form GR
  useEffect(() => {
    axios.get(`${API}/lots/settings`).then((r) => setLotSettings(r.data))
      .catch(() => setLotSettings({ enforcement_mode: "warn", require_supplier_lot: true,
                                    require_dye_lot: true }));
  }, []);

  // FASE F-1 — satuan default mengikuti kebijakan server (`prefer` → satuan supplier)
  useEffect(() => {
    const def = uom.options?.default_uom;
    if (def) setScanData((prev) => (prev.doc_uom ? prev : { ...prev, doc_uom: def }));
  }, [uom.options]);

  // pratinjau live setiap qty/satuan berubah (debounce di hook)
  useEffect(() => {
    if (!selectedTask) return;
    uom.runPreview(scanData.doc_uom, scanData.doc_qty);
  }, [scanData.doc_uom, scanData.doc_qty, selectedTask?.id]);   // eslint-disable-line react-hooks/exhaustive-deps

  const [listMeta, setListMeta] = useState(null);   // FIX-7 — jumlah sungguhan (header server)
  const [moreBusy, setMoreBusy] = useState(false);
  const loadMoreTasks = async () => {   // FIX-7 (B3b LST-01) — dulu 200 tugas terbaru tanpa tanda
    setMoreBusy(true);
    try {
      const res = await axios.get(`${API}/inbound/tasks`, {
        params: { ...(filterStatus !== "all" ? { status: filterStatus } : {}), skip: tasks.length } });
      const seen = new Set(tasks.map((t) => t.id));
      const next = [...tasks, ...rememberDocEntities(res.data || []).filter((t) => !seen.has(t.id))];
      setTasks(next);
      const m = metaFromHeaders(res, next.length);
      setListMeta(m ? { ...m, shown: next.length, skip: 0 } : null);
    } catch (e) { setError(apiErrorText(e, "Gagal memuat tugas berikutnya.")); } finally { setMoreBusy(false); }
  };
  const fetchTasks = async () => {
    setLoading(true);
    try {
      const params = filterStatus !== "all" ? `?status=${filterStatus}` : "";
      const res = await axios.get(`${API}/inbound/tasks${params}`);
      setTasks(rememberDocEntities(res.data));   // FIX-1 — tugas lintas PT: aksi atas nama PT tugas
      setListMeta(metaFromHeaders(res, (res.data || []).length));
      setError("");
      setLoadErr(null);
    } catch (e) { setError(e.response?.data?.detail || "Gagal memuat inbound task."); setLoadErr(e); }
    finally { setLoading(false); setFetched(true); }
  };

  const selectTask = (task) => {
    stopCamera();
    setSelectedTask(task);
    setScanData({ ...EMPTY_SCAN, doc_uom: "" });
  };

  const startCamera = async () => {
    try {
      const { BrowserMultiFormatReader } = await import("@zxing/browser");
      const reader = new BrowserMultiFormatReader();
      const el = document.getElementById("inbound-video-compact");
      if (!el) return;
      await reader.decodeFromVideoDevice(null, el, (result) => {
        // GRN Fase 0.9 — hasil kamera masuk ke kolom Roll ID (dulu disimpan di state yang tak pernah dikirim).
        if (result) { setScanData((prev) => ({ ...prev, roll_id: result.getText() })); stopCamera(); }
      });
      setCameraActive(true);
    } catch { setError("Gagal membuka kamera. Beri izin kamera pada peramban, atau ketik kode roll secara manual."); }
  };

  const stopCamera = () => {
    const el = document.getElementById("inbound-video-compact");
    if (el?.srcObject) { el.srcObject.getTracks().forEach(t => t.stop()); el.srcObject = null; }
    setCameraActive(false);
  };

  const handleScanReceive = async (overrideReason = "") => {
    if (!selectedTask) return;
    const qty = parseDecimal(scanData.doc_qty);   // FIX-3a (INP-10) — koma desimal Indonesia
    if (!Number.isFinite(qty) || qty <= 0) {
      setError("Masukkan jumlah yang diterima (lebih besar dari 0) sebelum menyimpan penerimaan.");
      return;
    }
    const docUom = scanData.doc_uom || uom.options?.task_uom || "";
    setSubmitting(true);
    try {
      // FASE F-1 — server yang mengonversi ke satuan PO & menyimpan jejaknya (D-07).
      const res = await axios.post(`${API}/inbound/tasks/${selectedTask.id}/scan-receive`, {
        product_id: selectedTask.product_id,
        doc_uom: docUom, doc_qty: qty,
        batch: scanData.batch, lot: scanData.lot, dye_lot: scanData.dye_lot,
        grade: scanData.grade, roll_id: scanData.roll_id, bin_id: scanData.bin_id,
        ...(overrideReason ? { variance_override_reason: overrideReason } : {}),
      });
      setTasks(prev => prev.map(t => t.id === selectedTask.id ? res.data : t));
      setSelectedTask(res.data);
      setScanData({ ...EMPTY_SCAN, doc_uom: docUom });
      uom.clearPreview();
      uom.reload();
      setError("");
      notifySuccess("Penerimaan tercatat",
        `Diterima ${formatQty(res.data?.received_qty || 0)} dari ${formatQty(res.data?.expected_qty || 0)} ${res.data?.unit || ""}.`);
    } catch (e) { setError(apiErrorText(e, "Gagal mencatat penerimaan.")); }
    finally { setSubmitting(false); }
  };

  // Fase 8 — buka modal entri roll catch-weight; prefilled 1 roll dari qty diterima.
  // FASE SL — bila roll sudah lahir dari SCAN LABEL, tidak ada yang perlu diketik ulang:
  // GR ditutup langsung dan server memfinalkan roll hasil scan (SSOT).
  const openComplete = () => {
    if (!selectedTask) return;
    if ((selectedTask.qty_rolls_scanned || 0) > 0) { submitCompleteScanned(); return; }
    if ((selectedTask.received_qty || 0) < selectedTask.expected_qty && selectedTask.status !== "qc_check") {
      setError(`Jumlah diterima (${formatQty(selectedTask.received_qty || 0)} ${selectedTask.unit || ""}) `
        + `masih di bawah pesanan (${formatQty(selectedTask.expected_qty)} ${selectedTask.unit || ""}). `
        + `Terima sisanya, atau eskalasi ke manajer bila barangnya memang kurang.`);
      return;
    }
    const isKg = (selectedTask.unit || "").toLowerCase() === "kg";
    const kgm = kgPerMeter(products[selectedTask.product_id]);
    const recv = Number(selectedTask.received_qty) || 0;
    setGrRolls([{
      length: isKg ? (kgm > 0 ? round2(recv / kgm) : 0) : recv,
      weight: isKg ? recv : (kgm > 0 ? round2(recv * kgm) : 0),
      dye_lot: selectedTask.dye_lot || "",
      grade: "A",
    }]);
    setShowGRModal(true);
  };

  const submitCompleteScanned = async () => {
    // LN-014 — roll hasil scan: tanyakan SJ supplier bila belum tercatat (mode warn/block).
    const sjMode = uom.options?.supplier_dn_mode || "warn";
    let supplierDn = "";
    if (selectedTask.po_id && sjMode !== "off" && !(uom.options?.supplier_dn_known || []).length) {
      const v = await askText({ title: "Nomor SJ supplier", reasonLabel: "Nomor surat jalan supplier",
        message: sjMode === "block" ? "Wajib diisi sebelum penerimaan diselesaikan."
          : "Disarankan diisi supaya lot baru membawa SJ asal. Kosongkan bila memang tidak ada.",
        reasonRequired: sjMode === "block", confirmLabel: "Selesaikan penerimaan" });
      if (v === null) return;
      supplierDn = v.trim();
    }
    setSubmitting(true);
    try {
      const res = await axios.post(`${API}/inbound/tasks/${selectedTask.id}/complete`, supplierDn ? { supplier_dn: supplierDn } : {});
      setLotResult({ lots: res.data?.lots || [], warnings: res.data?.lot_warnings || [], rolls: res.data?.created_rolls || [],
        task: selectedTask, variance: res.data?.receipt_variance || null });
      fetchTasks();
      setSelectedTask(null);
      setError("");
      notifySuccess("Penerimaan selesai", `${(res.data?.created_rolls || []).length} roll hasil scan masuk ${res.data?.status === "qc_pending" ? "karantina QC" : "stok"}.`);
    } catch (e) { setError(apiErrorText(e, "Gagal menyelesaikan penerimaan.")); }
    finally { setSubmitting(false); }
  };

  const onTaskUpdated = (t) => {
    if (!t) return;
    setSelectedTask(t);
    setTasks((prev) => prev.map((x) => (x.id === t.id ? { ...x, ...t } : x)));
  };

  const submitComplete = async (overrideReason = "") => {
    if (!selectedTask) return;
    setSubmitting(true);
    try {
      const rolls = grRolls.map((r) => ({
        length: Number(r.length) || 0,
        weight: Number(r.weight) || 0,
        dye_lot: r.dye_lot || "",
        grade: r.grade || "A",
      }));
      // FASE C — identitas lot batch dikirim bersama rincian roll
      const res = await axios.post(`${API}/inbound/tasks/${selectedTask.id}/complete`, {
        rolls,
        supplier_lot: lotFields.supplier_lot || "",
        lot_number: lotFields.lot_number || "",
        shade_ref: lotFields.shade_ref || "",
        supplier_dn: lotFields.supplier_dn || "",
        ...(overrideReason ? { variance_override_reason: overrideReason } : {}),
      });
      setLotResult({ lots: res.data?.lots || [], warnings: res.data?.lot_warnings || [], rolls: res.data?.created_rolls || [], task: selectedTask });
      setShowGRModal(false);
      setGrRolls([]);
      setLotFields({ supplier_lot: "", lot_number: "", shade_ref: "", supplier_dn: "" });
      fetchTasks();
      setSelectedTask(null);
      setError("");
      notifySuccess("Barang masuk gudang",
        `${(res.data?.lots || []).length || 1} lot terbentuk dari ${rolls.length} roll.`);
    } catch (e) {
      const msg = apiErrorText(e, "Gagal menyelesaikan penerimaan.");
      // GRN Fase 0.6 — selisih konversi memblokir: pemegang wms.approve boleh lanjut dengan alasan.
      if (!overrideReason && canOverride && e.response?.status === 400 && /alasan override/i.test(msg)) {
        setSubmitting(false);
        const reason = await askReason({ title: "Lanjutkan walau selisih di luar batas?", message: msg,
          reasonLabel: "Alasan override (tercatat di audit)", confirmLabel: "Lanjutkan" });
        if (reason) submitComplete(reason);
        return;
      }
      setError(msg);
    }
    finally { setSubmitting(false); }
  };

  const handleEscalate = async () => {
    if (!escalationReason.trim()) {
      setEscalateError("Tulis dulu alasan eskalasinya — manajer memakai catatan ini untuk memutuskan.");
      return;
    }
    setEscalateError("");
    setSubmitting(true);
    try {
      await axios.post(`${API}/inbound/tasks/${selectedTask.id}/escalate`, null, {
        params: { reason: escalationReason }
      });
      setShowEscalateModal(false);
      setEscalationReason("");
      fetchTasks();
      setSelectedTask(null);
      notifySuccess("Dieskalasi ke manajer", "Tugas menunggu keputusan manajer.");
    } catch (e) { setEscalateError(apiErrorText(e, "Gagal mengeskalasi tugas.")); }
    finally { setSubmitting(false); }
  };

  const FILTERS = ["all", "waiting_goods", "receiving", "qc_check", "escalated"];
  const FILTER_LABELS = { all: "Semua", waiting_goods: "Menunggu barang", receiving: "Sedang diterima", qc_check: "Cek QC", escalated: "Dieskalasi" };
  const listKind = listStateKind({ loading: loading || !fetched, error: loadErr, count: visibleTasks.length,
    filtered: filterStatus !== "all" || Boolean(whFilter) || Boolean(q.trim()) });

  return (
    <div data-testid="inbound-scan-panel" className="flex flex-col gap-3">
      <ErrorNotice message={error} onRetry={fetchTasks} onDismiss={() => setError("")} testId="inbound-scan-error" />
      {/* FASE C — hasil pembentukan lot setelah penerimaan + peringatan kelengkapan */}
      {lotResult && (
        <div data-testid="gr-lot-result"
          className={`rounded-md border px-2.5 py-2 ${lotResult.warnings.length
            ? "border-amber-200 bg-amber-50" : "border-emerald-200 bg-emerald-50"}`}>
          <div className="flex items-start gap-2">
            <div className="min-w-0 flex-1">
              <p className="text-[11.5px] font-semibold text-[#1C1C1E]">
                Penerimaan selesai · lot terbentuk:{" "}
                {(lotResult.lots || []).map((l) => l.lot_number).join(", ") || "—"}
              </p>
              {(lotResult.warnings || []).map((w) => (
                <p key={w} className="text-[10.5px] text-amber-800">⚠ {w}</p>
              ))}
              {lotResult.variance?.note && (
                <p data-testid="gr-receipt-variance" className="text-[10.5px] font-semibold text-[#B26A00]">
                  Catatan selisih ke purchasing: {lotResult.variance.note}
                </p>
              )}
              {!lotResult.warnings.length && (
                <p className="text-[10.5px] text-emerald-700">
                  Identitas lot lengkap — traceability & recall siap dipakai.
                </p>
              )}
              {(lotResult.rolls || []).length > 0 && (
                <RollLabelActions rolls={lotResult.rolls} ctx={{ product_name: lotResult.task?.product_name, po_number: lotResult.task?.po_number, warehouse_id: lotResult.task?.warehouse_id }}
                  source={`inbound:${lotResult.task?.id || ""}`} testPrefix="gr-labels" />
              )}
            </div>
            <button data-testid="gr-lot-result-close" className="text-[#6B6B73]"
              onClick={() => setLotResult(null)}><X size={14} /></button>
          </div>
        </div>
      )}
      {grnEntities.length > 0 && (
        <div data-testid="inbound-grn-mode-banner" className="flex items-center justify-between gap-3 rounded-xl border border-[#BFE5DC] bg-[#F0FAF7] px-3 py-2 text-[11.5px] text-[#0F766E]">
          <span><b>{grnEntities.map((e) => e.entity_name).join(", ")}</b> memakai Kedatangan Barang. Tugas baru diterima lewat layar Kedatangan (surat jalan → hitung fisik); di sini hanya tugas lama yang sudah berjalan.</span>
          <a data-testid="inbound-grn-open" href="?view=goods-receipts" className="primary-button whitespace-nowrap !py-1">Buka Kedatangan Barang</a>
        </div>
      )}
      {/* Pola UI gelombang Gudang (M26, pemilik 16 Nov) — bilah daftar sama dengan Kedatangan, Barang Keluar & Cutting:
          Cari → Status ▾ → Gudang ▾ → jumlah · Muat ulang/Unduh di kanan (dulu deret chip status hijau + tombol muat ulang
          di kepala daftar). Cari & gudang menyaring tugas yang sudah dimuat. */}
      <ListToolbar testId="inbound-filters" actions={(
        <>
          <button type="button" className="icon-button" onClick={fetchTasks} aria-label="Muat ulang" title="Muat ulang"
            data-testid="inbound-refresh"><RefreshCw size={14} /></button>
          <ExportMenu dataset="wms_tasks" label="tugas-barang-masuk" scope="work" testId="inbound-export" search={q}
            filters={[["flow_type", "eq", "inbound"], ["source_type", "eq", "purchase_order"],
              filterStatus !== "all" && ["status", "eq", filterStatus], whFilter && ["warehouse_id", "eq", whFilter]]}
            sort={[{ key: "created_at", dir: "desc" }]} />
        </>
      )}>
        <SearchInput testId="inbound-search" value={q} onChange={setQ} placeholder="Cari no. PO, pemasok, produk, SKU…"
          className="min-w-[220px] flex-1 sm:max-w-[320px]" />
        <OpsSelect testId="inbound-status" label="Status" value={filterStatus} onChange={(v) => setFilterStatus(v || "all")}
          width="min-w-[170px]" options={FILTERS.map((s) => ({ value: s, label: s === "all" ? "Semua status" : FILTER_LABELS[s] }))} />
        <OpsSelect testId="inbound-wh" label="Gudang" value={whFilter} onChange={setWhFilter}
          width="min-w-[170px]" searchable={whOptions.length > 9} options={whOptions} />
        <OpsCount testId="inbound-task-count">{fetched ? `${visibleTasks.length} tugas` : "Memuat…"}</OpsCount>
      </ListToolbar>

      <OpsSplit open={Boolean(selectedTask)} testId="inbound-split">
        <OpsList testId="inbound-task-list" footer={(
          <ListLimitNote meta={listMeta} noun="tugas" onMore={loadMoreTasks} loading={moreBusy}
            hint={q.trim() || whFilter ? "cari & saringan gudang hanya atas tugas yang sudah dimuat." : undefined} testId="inbound-limit" />
        )}>
          {listKind ? (
            <EmptyState compact what="tugas barang masuk" icon={Package} error={loadErr} onRetry={fetchTasks} kind={listKind}
              title={listKind === "empty" ? "Tidak ada tugas barang masuk" : undefined}
              onReset={() => { setFilterStatus("all"); setWhFilter(""); setQ(""); }} testId="inbound-list-state" />
          ) : visibleTasks.map((task) => {
            const pct = task.expected_qty ? Math.min((task.received_qty || 0) / task.expected_qty * 100, 100) : 0;
            return (
              <OpsRow key={task.id} testId={`inbound-task-${task.id}`} selected={selectedTask?.id === task.id}
                onOpen={() => selectTask(task)}
                title={task.po_number}
                status={<TaskBadge status={task.status} />}
                lines={[
                  task.supplier_name,
                  [task.sku, task.product_name].filter(Boolean).join(" · "),
                  task.warehouse_name,
                  // FASE F-1 — satuan supplier terlihat langsung di daftar
                  task.supplier_uom && task.supplier_uom !== task.unit && (
                    <span data-testid={`inbound-task-supplier-uom-${task.id}`} className="font-semibold text-kn-action">
                      surat jalan: {task.supplier_sku || "-"} · per {task.supplier_uom}
                    </span>
                  ),
                ]}
                aside={(
                  <>
                    <MiniBar pct={pct} status={task.status} />
                    <span className="mt-0.5 flex justify-between gap-2 tabular-nums">
                      <span>
                        {formatQty(task.received_qty || 0)}/{formatQty(task.expected_qty)} {task.unit}
                        {/* FASE U — DUA SATUAN di daftar tugas gudang: petugas mencocokkan
                            surat jalan supplier per GULUNGAN, jadi jumlah roll harus
                            terlihat sebelum tugas dibuka. `rollsText` = satu-satunya
                            aturan "layak ditulis atau tidak" (dokumen lama → kosong,
                            bukan "0 roll"). Rencana dari PO (`expected_rolls`) diganti
                            hasil nyata (`qty_rolls`) begitu roll benar-benar lahir. */}
                        {hasRolls(task.qty_rolls)
                          ? <span className="ml-1 text-kn-success-text">· {rollsText(task.qty_rolls)} diterima</span>
                          : (hasRolls(task.expected_rolls)
                            ? <span className="ml-1">· rencana {rollsText(task.expected_rolls)}</span>
                            : null)}
                      </span>
                      <span className="font-semibold text-kn-neutral">{pct.toFixed(0)}%</span>
                    </span>
                  </>
                )} />
            );
          })}
        </OpsList>

        {/* RIGHT: Scan Panel — hanya saat tugas dibuka (dulu panel kosong "Pilih tugas dari daftar"). */}
        {selectedTask && (
          <InboundTaskPanel
            task={selectedTask}
            scanData={scanData}
            setScanData={setScanData}
            uom={uom}
            cameraActive={cameraActive}
            canOverride={canOverride}
            onStartCamera={startCamera}
            onStopCamera={stopCamera}
            onClose={() => { stopCamera(); setSelectedTask(null); }}
            onScanReceive={handleScanReceive}
            onComplete={openComplete}
            onEscalate={() => { setEscalateError(""); setShowEscalateModal(true); }}
            submitting={submitting}
            onOpenPO={onOpenPO}
            onTaskUpdated={onTaskUpdated}
            onOpenDocument={onOpenDocument}
          />
        )}
      </OpsSplit>

      {/* Escalate Modal — Fase 4 · R3 (L-03): FormModal baku (layar penuh di HP, Esc berlapis, galat di kaki pop-up).
          Testid `inbound-escalate-reason` / `-submit` tetap. */}
      <FormModal open={showEscalateModal} onClose={() => setShowEscalateModal(false)} size="sm" icon={AlertTriangle}
        title="Eskalasi ke Manager" testId="inbound-escalate-modal" onSubmit={handleEscalate} busy={submitting}
        error={escalateError} submitTestId="inbound-escalate-submit" submitLabel="Eskalasi">
        <textarea value={escalationReason} onChange={(e) => setEscalationReason(e.target.value)}
          data-testid="inbound-escalate-reason" className="field w-full" rows="3"
          placeholder="Alasan escalation (contoh: Qty kurang 10m dari PO)" />
      </FormModal>

      {/* FASE SL P2 — laporan kualitas label per supplier */}
      <ScanLabelStatsCard />


      {/* Fase 8 — Goods Receipt: entri roll catch-weight (panjang m + berat kg) */}
      {showGRModal && selectedTask && (
        <GRCatchWeightModal
          task={selectedTask}
          product={products[selectedTask.product_id]}
          rolls={grRolls}
          setRolls={setGrRolls}
          onSubmit={() => submitComplete()}
          tolPct={uom.options?.line_qty_tolerance_pct ?? 2}
          onClose={() => setShowGRModal(false)}
          submitting={submitting}
          error={error}
          lotFields={lotFields}
          setLotFields={setLotFields}
          lotSettings={lotSettings}
          sjMode={uom.options?.supplier_dn_mode || "warn"}
          sjKnown={uom.options?.supplier_dn_known || []}
        />
      )}
    </div>
  );
}
