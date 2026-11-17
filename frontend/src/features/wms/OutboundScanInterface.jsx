import { useEffect, useMemo, useRef, useState } from "react";
import DispatchPaymentGatePanel from "../orders/DispatchPaymentGatePanel";
import PickListPanel from "./PickListPanel";
import { dualLen } from "../../components/RollPicker";
import {
  Scan, Truck, CheckCircle, AlertTriangle,
  Camera, CameraOff, FileText, Send, X, RefreshCw,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { rememberDocEntities } from "../../services/docEntityRegistry";
import EntityBadge from "../../components/EntityBadge";
import ErrorNotice from "../../components/ErrorNotice";
import { apiErrorText } from "../../utils/apiError";
import { notifySuccess } from "../../utils/feedback";
import { askConfirm } from "../../services/confirmService";
import FormModal from "../../components/FormModal";
import { openLogistics } from "../logistics/logisticsDeepLink";
import { formatQty } from "../../utils/formatters";
import { Badge, MiniBar } from "./OutboundScanBadges";
import LoadingCheckPanel from "./LoadingCheckPanel";
import SampleCutPanel from "./SampleCutPanel";
import { TaskTakeoverButton } from "./TaskTakeoverButton";
import { useLocationScope } from "./LocationScopeBadge";
import ExportMenu from "../../components/ExportMenu";   // FIX-4 — tombol baku Unduh (Excel/CSV, Pusat Export)
import EmptyState, { listStateKind } from "../../components/EmptyState";   // FIX-8 — keadaan daftar baku
import DocNumber, { docEntityId } from "../../components/DocNumber";   // FIX-8 (UI-58) — nomor dokumen satu skema tampilan
import StatusBadge from "../../components/StatusBadge";   // FIX-8 — lencana baku
import { ListToolbar, SearchInput } from "../../components/ListPageParts";   // FIX-8 — satu kotak cari baku
import { OpsCount, OpsList, OpsRow, OpsSelect, OpsSplit, warehouseOptions } from "./OpsListParts";   // pola UI M26
import SavedViewsMenu from "../../components/SavedViewsMenu";   // FIX-8 (K-B4-12) — tampilan tersimpan
import useSavedViews from "../../hooks/useSavedViews";
import { ROLE_OPTIONS } from "../../config/roles";
import ListLimitNote, { metaFromHeaders } from "./ListLimitNote";   // FIX-7 (B3b LST-01)

const BASE_OUT_VIEW = { filters: {}, sort: null, columns: [], mode: "" };

export default function OutboundScanInterface({ user, focusTaskId = "", onFocusConsumed }) {
  const locScope = useLocationScope();   // FIX-3b (B3b K-B3b-08) — "Ambil alih tugas" untuk supervisor lokasi
  const [tasks, setTasks] = useState([]);
  const [listMeta, setListMeta] = useState(null);     // FIX-7 — jumlah sungguhan dari server (header X-Total-Count)
  const [moreBusy, setMoreBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [fetched, setFetched] = useState(false);
  const [error, setError] = useState("");
  const [selectedTask, setSelectedTask] = useState(null);
  const [filterStatus, setFilterStatus] = useState("all");
  // Trial 22 Okt (F2) — pencarian & filter (dulu hanya chip status): no. pesanan, pelanggan, produk/SKU, gudang, jenis.
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("all");
  const [whFilter, setWhFilter] = useState("");
  const [loadErr, setLoadErr] = useState(null);   // FIX-8 (UI-49) — galat muat (403 ≠ "tidak ada tugas")
  // FIX-8 (K-B4-12) — tampilan tersimpan daftar tugas keluar: status, gudang, jenis (SO/Sample). Cakupan tidak ikut.
  const outViewHook = useSavedViews("wms.outbound_tasks", {
    state: { filters: { status: filterStatus, warehouse_id: whFilter, kind }, sort: null, columns: [], mode: "" },
    base: BASE_OUT_VIEW,
    apply: (st) => { setFilterStatus(st.filters.status || "all"); setWhFilter(st.filters.warehouse_id || ""); setKind(st.filters.kind || "all"); },
  });

  const [cameraActive, setCameraActive] = useState(false);
  const [scanValue, setScanValue] = useState("");
  const [scanData, setScanData] = useState({ actual_qty: 0, batch: "", lot: "", roll_id: "", bin_id: "" });
  const [rollCode, setRollCode] = useState("");
  const [rollInfo, setRollInfo] = useState(null);

  /** Cari roll fisik dari kode scan/ketik → jumlah/lot/batch/bin diturunkan dari master roll (tidak diketik).
   *  Roll yang benar untuk tugas ini adalah roll yang DICADANGKAN untuk pesanannya (status reserved/
   *  committed/…), jadi pencarian tidak dibatasi status "available"; kelayakan dicek sama seperti server. */
  const SHIPPABLE = ["committed", "packed", "picked", "reserved"];
  // Uji alur A1 (pelatihan 18 Nov) — klik [Kirim Pengambilan] juga memicu onBlur kotak kode roll → pencarian roll kedua
  // yang jawabannya tiba SESUDAH pengambilan tercatat, lalu kotak hijau "Roll …" + data scan muncul lagi (klik ulang =
  // ditolak server). Nomor urut pencarian: jawaban yang sudah usang (ada pencarian/pengambilan lebih baru) diabaikan.
  const resolveSeq = useRef(0);
  const resolveRoll = async (code) => {
    const q = String(code || "").trim();
    if (!q) return;
    const seq = ++resolveSeq.current;
    try {
      const res = await axios.get(`${API}/inventory/rolls`, { params: { q, limit: 20, ...(selectedTask?.product_id ? { product_id: selectedTask.product_id } : {}) } });
      if (seq !== resolveSeq.current) return;
      const list = Array.isArray(res.data) ? res.data : (res.data?.items || []);
      const roll = list.find(r => String(r.roll_no || "").toLowerCase() === q.toLowerCase() || r.id === q);
      if (!roll) { setRollInfo(null); setError(`Roll "${q}" tidak ditemukan untuk produk tugas ini (${selectedTask?.sku || selectedTask?.product_name || "-"}).`); return; }
      const problems = [];
      if (selectedTask?.warehouse_id && roll.warehouse_id !== selectedTask.warehouse_id) problems.push(`ada di gudang ${roll.warehouse_name || "lain"}, bukan ${selectedTask.warehouse_name || "gudang tugas"}`);
      if (selectedTask?.entity_id && roll.owner_entity_id && roll.owner_entity_id !== selectedTask.entity_id) problems.push(`milik ${roll.owner_entity_name || "PT lain"}`);
      if ((roll.reserved_ref || {}).id !== selectedTask?.order_id || !SHIPPABLE.includes(roll.status)) problems.push(`belum dicadangkan untuk pesanan ini (status ${roll.status || "-"})`);
      if (problems.length) { setRollInfo(null); setError(`Roll ${roll.roll_no || q} tidak bisa diambil: ${problems.join("; ")}.`); return; }
      setRollInfo(roll);
      setScanData({ actual_qty: Number(roll.length_remaining) || 0, batch: roll.batch || "", lot: roll.lot || "", roll_id: roll.id, bin_id: roll.bin_id || roll.location_code || "" });
      setError("");
    } catch (e) { setError(apiErrorText(e, "Gagal mencari roll.")); }
  };

  const [showEscalateModal, setShowEscalateModal] = useState(false);
  const [escalationReason, setEscalationReason] = useState("");
  // FASE P5 — galat eskalasi tampil DI DALAM pop-upnya. Kalau dikirim ke bilah halaman,
  // ia tertutup pop-up itu sendiri dan operator hanya melihat tombol yang "tidak jalan".
  const [escalateError, setEscalateError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [shipQty, setShipQty] = useState("");          // Sub-fase 1.8 — qty kirim parsial
  const [lastShipment, setLastShipment] = useState(null);

  useEffect(() => { fetchTasks(); }, [filterStatus]);

  // Deep-link dari Meja Admin Gudang ("Buka WMS") — sorot & buka tugas yang diklik.
  useEffect(() => {
    if (!focusTaskId || loading || !fetched) return;
    const t = tasks.find((x) => x.id === focusTaskId);
    if (t) {
      setSelectedTask(t);
      setTimeout(() => document.querySelector(`[data-testid="outbound-task-${t.id}"]`)?.scrollIntoView({ block: "center" }), 50);
    } else if (filterStatus !== "scheduled") {
      // Cek UI UAT v3 — tugas "Ambil di Gudang" yang masih ditahan tidak ada di daftar "Semua": dulu [Kerjakan]
      // dari Meja Saya membuka layar tanpa tugas terpilih. Kini pindah ke filter Terjadwal lalu memilihnya.
      axios.get(`${API}/outbound/tasks`, { params: { status: "scheduled" } })
        .then((r) => { if ((r.data || []).some((x) => x.id === focusTaskId)) setFilterStatus("scheduled"); else onFocusConsumed?.(); })
        .catch(() => onFocusConsumed?.());
      return;
    }
    onFocusConsumed?.();
  }, [focusTaskId, tasks, loading, fetched]); // eslint-disable-line

  // Cek UI UAT v3 (S2) — respons aksi (scan-pick/rilis/kirim/potong) = tugas mentah tanpa pengayaan daftar
  // (nama pelanggan, status bayar CBD/DP). Dulu menggantikan tugas terpilih → "Customer:" kosong & panel
  // "Tertahan bayar" hilang tepat saat barang siap dikirim. Kini digabung ke data yang sudah diperkaya.
  const withEnrichment = (prev, next) => (next && prev && prev.id === next.id ? { ...prev, ...next } : next);

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const params = filterStatus !== "all" ? `?status=${filterStatus}` : "";
      const res = await axios.get(`${API}/outbound/tasks${params}`);
      // FIX-1 (K-B1-02) — antrean lintas PT di gedung lokasi kerja: aksi tugas dikirim atas nama PT tugasnya.
      setTasks(rememberDocEntities(res.data));
      setListMeta(metaFromHeaders(res, (res.data || []).length));
      setSelectedTask((cur) => (cur ? res.data.find((t) => t.id === cur.id) || cur : cur));
      setError("");
      setLoadErr(null);
    } catch (e) { setError(e.response?.data?.detail || "Gagal memuat outbound task."); setLoadErr(e); }
    finally { setLoading(false); setFetched(true); }
  };

  // FIX-7 (B3b LST-01) — dulu 200 tugas terbaru tanpa tanda; kini "Muat berikutnya" dari server (skip = sudah dimuat).
  const loadMoreTasks = async () => {
    setMoreBusy(true);
    try {
      const res = await axios.get(`${API}/outbound/tasks`, {
        params: { ...(filterStatus !== "all" ? { status: filterStatus } : {}), skip: tasks.length } });
      const seen = new Set(tasks.map((t) => t.id));
      const next = [...tasks, ...rememberDocEntities(res.data || []).filter((t) => !seen.has(t.id))];
      setTasks(next);
      const m = metaFromHeaders(res, next.length);
      setListMeta(m ? { ...m, shown: next.length, skip: 0 } : null);
    } catch (e) { setError(apiErrorText(e, "Gagal memuat tugas berikutnya.")); } finally { setMoreBusy(false); }
  };

  const startCamera = async () => {
    try {
      const { BrowserMultiFormatReader } = await import("@zxing/browser");
      const reader = new BrowserMultiFormatReader();
      const el = document.getElementById("outbound-video-compact");
      if (!el) return;
      await reader.decodeFromVideoDevice(null, el, (result) => {
        if (result) { setScanValue(result.getText()); setRollCode(result.getText()); resolveRoll(result.getText()); stopCamera(); }
      });
      setCameraActive(true);
    } catch { setError("Gagal membuka kamera. Beri izin kamera pada peramban, atau ketik kode roll secara manual."); }
  };

  const stopCamera = () => {
    const el = document.getElementById("outbound-video-compact");
    if (el?.srcObject) { el.srcObject.getTracks().forEach(t => t.stop()); el.srcObject = null; }
    setCameraActive(false);
  };

  const handleScanPick = async () => {
    if (!selectedTask || !scanData.roll_id || scanData.actual_qty <= 0) {
      setError("Scan roll terlebih dahulu — jumlah diambil mengikuti panjang roll, tidak diketik manual.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await axios.post(`${API}/outbound/tasks/${selectedTask.id}/scan-pick`, null, { params: scanData });
      resolveSeq.current += 1;   // pencarian roll yang masih berjalan (onBlur) tidak boleh mengisi ulang form
      setTasks(prev => prev.map(t => t.id === selectedTask.id ? withEnrichment(t, res.data) : t));
      setSelectedTask((cur) => withEnrichment(cur, res.data));
      setScanData({ actual_qty: 0, batch: "", lot: "", roll_id: "", bin_id: "" });
      setScanValue(""); setRollCode(""); setRollInfo(null);
      setError("");
      notifySuccess("Pengambilan tercatat",
        `Terkumpul ${formatQty(res.data?.picked_qty || 0)} dari ${formatQty(res.data?.quantity || 0)} ${res.data?.unit || ""}.`);
    } catch (e) { setError(apiErrorText(e, "Gagal mencatat pengambilan.")); }
    finally { setSubmitting(false); }
  };

  const handleDispatch = async (partial = false) => {
    if (!selectedTask) return;
    const picked = Number(selectedTask.picked_qty || 0);
    const shipped = Number(selectedTask.shipped_qty || 0);
    const maxShip = Math.round((Math.min(picked, selectedTask.quantity) - shipped) * 100) / 100;
    if (maxShip <= 0) {
      setError("Belum ada jumlah ter-pick yang siap dikirim. Lakukan pengambilan dulu sebelum mengirim.");
      return;
    }
    let qty = maxShip;
    if (partial) {
      qty = Number(shipQty);
      if (!qty || qty <= 0 || qty > maxShip + 0.01) {
        setError(`Jumlah kirim harus antara 1 dan ${formatQty(maxShip)} ${selectedTask.unit || ""}.`);
        return;
      }
    }
    const ok = await askConfirm({
      title: `Kirim ${formatQty(qty)} ${selectedTask.unit || ""}?`,
      message: `Surat jalan diterbitkan dan stok keluar dari ${selectedTask.warehouse_name || "gudang"}`
        + `${qty < maxShip - 0.001 ? " (pengiriman sebagian — sisanya tetap bisa dikirim menyusul)" : ""}.`,
      confirmLabel: "Kirim Sekarang",
      testId: "outbound-dispatch-confirm",
    });
    if (!ok) return;
    setSubmitting(true);
    try {
      const res = await axios.post(`${API}/outbound/tasks/${selectedTask.id}/dispatch`, null,
        qty < maxShip - 0.001 ? { params: { ship_qty: qty } } : {});
      const sj = res.data?.shipment?.shipment_no;
      setShipQty("");
      setLastShipment(res.data?.shipment || null);
      await fetchTasks();
      setSelectedTask((cur) => withEnrichment(cur, res.data?.task || null));
      setError("");
      notifySuccess("Barang terkirim", sj ? `No. Surat Jalan: ${sj}` : "Surat jalan sudah diterbitkan.");
    } catch (e) { setError(apiErrorText(e, "Gagal mengirim barang.")); }
    finally { setSubmitting(false); }
  };

  // Trial 22 Okt (F1) — potong sample/catalogue dikerjakan di tab Cutting; paket sample baru tampil di sini setelah
  // hasil potong DITERIMA Admin Cutting (siap kirim). Dulu tugas potong bercampur dengan tugas ambil SO.
  const readyToShip = (t) => Math.round((Math.min(Number(t.picked_qty || 0), Number(t.quantity || 0)) - Number(t.shipped_qty || 0)) * 100) / 100 > 0;
  const visibleTasks = useMemo(() => {
    const term = q.toLowerCase().trim();
    return (tasks || []).filter((t) => {
      const smp = t.task_subtype === "sample_cut";
      if (smp && !(Number(t.picked_qty || 0) > 0 && t.cutting_handoff?.received_at)) return false;
      if (kind === "so" && smp) return false;
      if (kind === "sample" && !smp) return false;
      if (whFilter && t.warehouse_id !== whFilter) return false;
      if (!term) return true;
      return [t.order_number, t.customer_name, t.product_name, t.sku, t.warehouse_name].filter(Boolean).join(" ").toLowerCase().includes(term);
    });
  }, [tasks, q, kind, whFilter]);
  const warehousesInList = useMemo(() => warehouseOptions(tasks, whFilter), [tasks, whFilter]);
  // Trial 22 Okt (A2) — semua tugas pesanan ini di gudang ini yang siap kirim → SATU Surat Jalan.
  const siblingsReady = selectedTask ? (tasks || []).filter((t) => t.order_id === selectedTask.order_id
    && t.warehouse_id === selectedTask.warehouse_id && !["dispatched", "cancelled", "escalated"].includes(t.status) && readyToShip(t)) : [];
  const handleDispatchBatch = async () => {
    const ok = await askConfirm({
      title: `Kirim ${siblingsReady.length} baris ${selectedTask.order_number} sekaligus?`,
      message: `Semua tugas pesanan ini di ${selectedTask.warehouse_name || "gudang ini"} yang siap kirim keluar bersama dengan SATU nomor Surat Jalan.`,
      confirmLabel: "Kirim Sekarang", testId: "outbound-dispatch-batch-confirm",
    });
    if (!ok) return;
    setSubmitting(true);
    try {
      const { data } = await axios.post(`${API}/outbound/so/${selectedTask.order_id}/dispatch-batch`, null, { params: { warehouse_id: selectedTask.warehouse_id } });
      setLastShipment((data.shipments || [])[0] || null);
      await fetchTasks();
      setError("");
      notifySuccess("Barang terkirim", `No. Surat Jalan: ${data.shipment_no} · ${data.lines} baris · ${formatQty(data.qty)} ${data.unit || ""}`);
    } catch (e) { setError(apiErrorText(e, "Gagal mengirim barang.")); }
    finally { setSubmitting(false); }
  };

  const handleRelease = async () => {
    if (!selectedTask) return;
    const ok = await askConfirm({
      title: "Rilis tugas pengambilan ini?",
      message: "Tugas masuk ke antrean pengambilan sekarang sehingga petugas gudang bisa mulai mengambil barang.",
      confirmLabel: "Rilis ke Antrean",
      testId: "outbound-release-confirm",
    });
    if (!ok) return;
    setSubmitting(true);
    try {
      const res = await axios.post(`${API}/outbound/tasks/${selectedTask.id}/release`);
      await fetchTasks();
      setSelectedTask((cur) => withEnrichment(cur, res.data));
      setError("");
      notifySuccess("Tugas dirilis", "Sudah masuk antrean pengambilan.");
    } catch (e) { setError(apiErrorText(e, "Gagal merilis tugas.")); }
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
      await axios.post(`${API}/outbound/tasks/${selectedTask.id}/escalate`, null, {
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

  const handleViewSuratJalan = (orderId, warehouseId) => {
    const url = warehouseId
      ? `${API}/outbound/so/${orderId}/surat-jalan?warehouse_id=${warehouseId}`
      : `${API}/outbound/so/${orderId}/surat-jalan`;
    window.open(url, '_blank');
  };

  const FILTERS = ["all", "scheduled", "created", "picking", "packing", "staging", "partially_shipped", "escalated"];
  const FILTER_LABELS = { all: "Semua", scheduled: "Terjadwal (Ambil)", created: "Siap diambil", picking: "Pengambilan", packing: "Pengemasan", staging: "Siap muat", partially_shipped: "Parsial", escalated: "Dieskalasi" };

  const filtered = filterStatus !== "all" || kind !== "all" || Boolean(whFilter) || Boolean(q.trim());
  const listKind = listStateKind({ loading: loading || !fetched, error: loadErr, count: visibleTasks.length, filtered });
  return (
    <div data-testid="outbound-scan-panel" className="flex flex-col gap-3">
      <ErrorNotice message={error} onRetry={fetchTasks} onDismiss={() => setError("")} testId="outbound-scan-error" />
      {/* Pola UI gelombang Gudang (M26, pemilik 16 Nov) — SATU bilah daftar seperti Barang Masuk & Cutting:
          Cari → Status ▾ → Jenis ▾ → Gudang ▾ → jumlah · Muat ulang/Tampilan/Unduh di kanan. Dulu dua baris: deret chip
          status oranye + jumlah, lalu cari + chip jenis biru + dropdown gudang, ditambah baris keterangan (kini di ?). */}
      <ListToolbar testId="outbound-filters" actions={(
        <>
          <button type="button" className="icon-button" onClick={fetchTasks} aria-label="Muat ulang" title="Muat ulang"
            data-testid="outbound-refresh"><RefreshCw size={14} /></button>
          <SavedViewsMenu sv={outViewHook} testId="outbound-views" shareRoles={ROLE_OPTIONS} />
          <ExportMenu dataset="wms_tasks" label="tugas-barang-keluar" scope="work" testId="outbound-export" search={q}
            filters={[["flow_type", "eq", "outbound"], filterStatus !== "all" && ["status", "eq", filterStatus],
              whFilter && ["warehouse_id", "eq", whFilter],
              kind === "so" ? ["task_subtype", "ne", "sample_cut"]
                : { op: "or", items: [kind !== "sample" && ["task_subtype", "ne", "sample_cut"],
                  { op: "and", items: [["task_subtype", "eq", "sample_cut"], ["picked_qty", "gt", 0], ["cutting_received_at", "not_empty"]] }] }]}
            sort={[{ key: "created_at", dir: "desc" }]} />
        </>
      )}>
        <SearchInput testId="outbound-search" value={q} onChange={setQ} placeholder="Cari no. pesanan, pelanggan, produk, SKU…"
          className="min-w-[220px] flex-1 sm:max-w-[320px]" />
        <OpsSelect testId="outbound-status" label="Status" value={filterStatus} onChange={(v) => setFilterStatus(v || "all")}
          width="min-w-[170px]" options={FILTERS.map((s) => ({ value: s, label: s === "all" ? "Semua status" : FILTER_LABELS[s] }))} />
        <OpsSelect testId="outbound-kind" label="Jenis" value={kind} onChange={(v) => setKind(v || "all")}
          options={[{ value: "all", label: "Semua jenis" }, { value: "so", label: "Pesanan (SO)" }, { value: "sample", label: "Sample" }]} />
        <OpsSelect testId="outbound-wh" label="Gudang" value={whFilter} onChange={setWhFilter}
          width="min-w-[170px]" searchable={warehousesInList.length > 9} options={warehousesInList} />
        <OpsCount testId="outbound-task-count">{fetched ? `${visibleTasks.length} tugas` : "Memuat…"}</OpsCount>
      </ListToolbar>

      {/* Daftar selebar layar; panel Ambil & Kirim terbuka di kanan saat tugas dipilih (dulu panel kosong "Pilih tugas
          dari daftar" selalu memakan dua pertiga layar). */}
      <OpsSplit open={Boolean(selectedTask)} testId="outbound-split">
        <OpsList testId="outbound-task-list" footer={(
          <ListLimitNote meta={listMeta} noun="tugas" onMore={loadMoreTasks} loading={moreBusy}
            hint="cari & saringan di layar hanya atas tugas yang sudah dimuat." testId="outbound-limit" />
        )}>
          {/* FIX-8 (B4 §3.10 · UI-49/UI-50) — memuat · kosong · saringan kosong (+ Reset) · galat · tanpa akses */}
          {listKind ? (
            <EmptyState compact what="tugas barang keluar" icon={Truck} error={loadErr} onRetry={fetchTasks} kind={listKind}
              title={listKind === "empty" ? "Tidak ada tugas barang keluar" : undefined}
              onReset={() => { setFilterStatus("all"); setKind("all"); setWhFilter(""); setQ(""); }} testId="outbound-list-state" />
          ) : visibleTasks.map((task) => {
            const pct = task.quantity ? Math.min((task.picked_qty || 0) / task.quantity * 100, 100) : 0;
            return (
              <OpsRow key={task.id} testId={`outbound-task-${task.id}`} selected={selectedTask?.id === task.id}
                onOpen={() => { setSelectedTask(task); stopCamera(); }}
                title={(
                  <>
                    <DocNumber number={task.order_number} entityId={docEntityId(task)} />
                    {task.task_subtype === "sample_cut" && <StatusBadge tone="special" icon="tag" testId={`outbound-task-sample-${task.id}`}>SAMPEL</StatusBadge>}
                    {task.work_entity_id && <span data-testid={`outbound-task-pt-${task.id}`}><EntityBadge entityId={task.work_entity_id} /></span>}
                  </>
                )}
                status={<Badge status={task.status} />}
                lines={[
                  task.customer_name,
                  task.sku,
                  task.warehouse_name,
                  (task.payment_hold?.blocked || Number(task.so_backorder_qty || 0) > 0) && (
                    <span className="inline-flex flex-wrap gap-1">
                      {task.payment_hold?.blocked && (
                        <StatusBadge tone="danger" icon="lock" testId={`outbound-task-payment-hold-${task.id}`}>
                          Tertahan bayar · {task.payment_hold.term_code}
                        </StatusBadge>
                      )}
                      {Number(task.so_backorder_qty || 0) > 0 && (
                        <StatusBadge tone="info" icon="clock" testId={`outbound-task-backorder-${task.id}`}>
                          SO masih kurang {formatQty(task.so_backorder_qty)} {task.unit} · backorder
                        </StatusBadge>
                      )}
                    </span>
                  ),
                ]}
                aside={(
                  <>
                    <MiniBar pct={pct} status={task.status} />
                    <span className="mt-0.5 flex justify-between gap-2 tabular-nums">
                      <span>{formatQty(task.picked_qty || 0)}/{formatQty(task.quantity)} {task.unit}</span>
                      <span className="font-semibold text-kn-neutral">{pct.toFixed(0)}%</span>
                    </span>
                  </>
                )} />
            );
          })}
        </OpsList>

        {/* RIGHT: Pick Panel */}
        {selectedTask && (
          <div className="kn-ops-panel" data-testid="outbound-task-panel">
            <div className="kn-ops-panel-head">
              <div className="flex items-center gap-2">
                <span className="text-fs-13 font-bold text-kn-text">Ambil & Kirim</span>
                <Badge status={selectedTask.status} />
              </div>
              <button type="button" className="icon-button" aria-label="Tutup panel tugas" data-testid="outbound-panel-close"
                onClick={() => { stopCamera(); setSelectedTask(null); }}>
                <X size={14} />
              </button>
            </div>

            <div className="p-3 space-y-3">
              {/* Info bar */}
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-[#FFF8EE] rounded-lg p-2">
                  <p className="text-[10px] text-[#6B6B73] uppercase font-semibold">SO</p>
                  <p className="text-[12px] font-bold text-[#FF9500]">{selectedTask.order_number}</p>
                </div>
                <div className="bg-[#FFF8EE] rounded-lg p-2">
                  <p className="text-[10px] text-[#6B6B73] uppercase font-semibold">Gudang</p>
                  <p className="text-[11px] font-semibold truncate">{selectedTask.warehouse_name}</p>
                </div>
                <div className="bg-[#FFF8EE] rounded-lg p-2">
                  <p className="text-[10px] text-[#6B6B73] uppercase font-semibold">Progress</p>
                  <p className="text-[12px] font-bold">{formatQty(selectedTask.picked_qty || 0)}<span className="text-[10px] text-[#6B6B73]">/{formatQty(selectedTask.quantity)}</span></p>
                </div>
              </div>

              <div className="bg-[#FAFBFC] rounded-lg p-2">
                <p className="text-[11px] text-[#3C3C43] font-medium">{selectedTask.product_name}</p>
                <p className="text-[10.5px] text-[#6B6B73]">SKU: {selectedTask.sku} · Customer: {selectedTask.customer_name}</p>
              </div>
              {!["dispatched", "cancelled", "completed"].includes(selectedTask.status) && (
                <TaskTakeoverButton task={selectedTask} scope={locScope} onDone={fetchTasks} />
              )}

              {/* Escalation info */}
              {selectedTask.status === 'escalated' && selectedTask.escalation && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-2 text-[11px]">
                  <p className="font-semibold text-red-700">Escalated: {selectedTask.escalation.escalated_by}</p>
                  <p className="text-red-600">{selectedTask.escalation.reason}</p>
                  {selectedTask.escalation.status === 'resolved' && (
                    <p className="text-green-700 mt-1 inline-flex items-center gap-1"><CheckCircle size={12} /> Resolved: {selectedTask.escalation.resolution_notes}</p>
                  )}
                </div>
              )}

              {/* Order Pengambilan — task di-hold sampai tanggal ambil */}
              {selectedTask.status === 'scheduled' && (
                <div data-testid="outbound-scheduled-hold" className="rounded-lg border border-purple-200 bg-purple-50 p-3 text-[11.5px]">
                  <p className="font-semibold text-purple-700">Pengambilan terjadwal — pengambilan ditahan.</p>
                  <p className="mt-0.5 text-purple-600">Barang baru disiapkan pada/ setelah tanggal ambil{selectedTask.hold_until ? ` (${selectedTask.hold_until})` : ""}. Rilis manual bila ingin siapkan lebih awal.</p>
                  <button data-testid="release-scheduled-btn" disabled={submitting} onClick={handleRelease}
                    className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-purple-600 px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-50">
                    <CheckCircle size={12} /> Rilis ke Pengambilan Sekarang
                  </button>
                </div>
              )}

              {/* §3-C — permintaan potong sample: pindai roll induk + panjang aktual menggantikan scan-pick */}
              {selectedTask.task_subtype === "sample_cut" && Number(selectedTask.picked_qty || 0) <= 0 && !['dispatched', 'escalated', 'scheduled'].includes(selectedTask.status) && (
                <SampleCutPanel task={selectedTask} onCut={(t) => { setTasks(prev => prev.map(x => x.id === t.id ? withEnrichment(x, t) : x)); setSelectedTask((cur) => withEnrichment(cur, t)); }} />
              )}

              {/* Camera + Form */}
              {!['dispatched', 'escalated', 'scheduled'].includes(selectedTask.status) && !(selectedTask.task_subtype === "sample_cut" && Number(selectedTask.picked_qty || 0) <= 0) && (
                <>
                  {selectedTask.task_subtype !== "sample_cut" && (<>
                  {/* Cek UI UAT v3 — roll yang harus diambil langsung di panel (dulu harus cetak picking list di layar lain) */}
                  <PickListPanel task={selectedTask} onPick={(no) => { setRollCode(no); resolveRoll(no); }} />
                  <div className="flex items-center gap-2">
                    <button onClick={cameraActive ? stopCamera : startCamera}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium ${cameraActive ? 'bg-red-500 text-white' : 'bg-[#FFF8EE] text-[#FF9500] border border-[#FF9500]/30'}`}>
                      {cameraActive ? <><CameraOff size={12} /> Stop</> : <><Camera size={12} /> Camera</>}
                    </button>
                    {scanValue && <span className="text-[11px] text-green-700 font-medium inline-flex items-center gap-1"><CheckCircle size={11} /> {scanValue}</span>}
                  </div>
                  <video id="outbound-video-compact"
                    className={`w-full rounded-lg border border-[#FF9500]/30 ${cameraActive ? 'block' : 'hidden'}`}
                    style={{ maxHeight: '160px' }} />

                  {/* Aturan gudang: TIDAK ada ketik manual jumlah/lot/batch — semua diturunkan dari ROLL yang di-scan. */}
                  <div className="grid grid-cols-3 gap-2">
                    <div className="col-span-3">
                      <label className="block text-[10px] font-semibold text-[#6B6B73] mb-1">Kode roll (scan / ketik lalu Enter)</label>
                      <input type="text" data-testid="outbound-roll-code" value={rollCode}
                        onChange={e => setRollCode(e.target.value)}
                        onKeyDown={e => { if (e.key === "Enter") resolveRoll(rollCode); }}
                        onBlur={() => rollCode && resolveRoll(rollCode)}
                        className="w-full border border-[#E5E5EA] rounded-lg px-2 py-1.5 text-sm" placeholder="Scan QR/RFID atau ketik nomor roll" />
                    </div>
                    {rollInfo ? (
                      <div className="col-span-3 rounded-lg border border-[#34C759]/40 bg-[#F0FFF4] p-2 text-[11px]" data-testid="outbound-roll-info">
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                          <span className="font-bold text-[#1C1C1E]">Roll {rollInfo.roll_no}</span>
                          <span data-testid="outbound-roll-dual" className="tabular-nums font-semibold text-[#0058CC]">{dualLen(rollInfo.length_remaining, selectedTask?.unit || "meter")}</span>
                          <span>Lot {rollInfo.lot || "—"}</span>
                          {rollInfo.dye_lot && rollInfo.dye_lot !== rollInfo.lot && <span>Dye {rollInfo.dye_lot}</span>}
                          <span>Bin {rollInfo.bin_id || rollInfo.location_code || "—"}</span>
                          {rollInfo.grade && <span>Grade {rollInfo.grade}</span>}
                        </div>
                        <p className="mt-1 text-[#6B6B73]">Jumlah diambil = panjang roll (SSOT roll). Untuk ambil sebagian, potong roll di modul potong terlebih dahulu.</p>
                      </div>
                    ) : (
                      <p className="col-span-3 text-[10.5px] text-[#8E8E93]" data-testid="outbound-roll-hint">Scan roll untuk mengisi jumlah, lot, batch, dan bin secara otomatis.</p>
                    )}
                  </div>

                  <div className="flex gap-2">
                    <button onClick={handleScanPick} disabled={submitting}
                      data-testid={`scan-task-${selectedTask.id}`}
                      className="flex-1 bg-[#FF9500] hover:bg-[#CC7700] text-white rounded-lg px-3 py-2 text-[12px] font-semibold flex items-center justify-center gap-1.5 disabled:opacity-50">
                      <CheckCircle size={13} /> Kirim Pengambilan
                    </button>
                    <button onClick={() => { setEscalateError(""); setShowEscalateModal(true); }}
                      className="bg-red-50 border border-red-300 text-red-600 hover:bg-red-100 rounded-lg px-3 py-2 text-[12px] font-semibold flex items-center gap-1.5">
                      <AlertTriangle size={13} /> Eskalasi
                    </button>
                  </div>
                  </>)}
                  {selectedTask.task_subtype === "sample_cut" && (
                    <p data-testid={`outbound-sample-cut-info-${selectedTask.id}`} className="rounded-lg border border-[#BFE6CC] bg-[#F1FBF4] p-2 text-[11px] text-[#126E2C]">
                      Sample sudah dipotong dari <b>{selectedTask.parent_roll_no}</b> → <b>{selectedTask.child_roll_no}</b> ({formatQty(selectedTask.picked_qty)} {selectedTask.unit}).{" "}
                      {selectedTask.cutting_handoff?.received_at
                        ? <>Diterima Admin Cutting ({selectedTask.cutting_handoff.received_by}) — siap dikirim di bawah.</>
                        : <b className="text-[#9A5B00]">Belum diterima Admin Cutting — kirim akan ditolak; serahkan dulu (Pesanan Sample › Meja Cutting).</b>}
                    </p>
                  )}

                  {Number(selectedTask.so_backorder_qty || 0) > 0 && (
                    <p data-testid={`outbound-backorder-info-${selectedTask.id}`} className="rounded-lg border border-[#CBDFFF] bg-[#F2F7FF] p-2 text-[11px] text-[#31465F]">
                      Tugas ini hanya bagian yang sudah ada stoknya. SO {selectedTask.order_number} masih kurang <b>{formatQty(selectedTask.so_backorder_qty)} {selectedTask.unit}</b> (backorder
                      menunggu barang masuk) — sisa itu muncul sebagai tugas ambil baru setelah stok tiba, jadi pesanan belum selesai walau tugas ini terkirim penuh.
                    </p>
                  )}
                  {/* Sub-fase 1.8 — Dispatch (mendukung pengiriman PARSIAL) */}
                  {(() => {
                    const picked = Number(selectedTask.picked_qty || 0);
                    const shipped = Number(selectedTask.shipped_qty || 0);
                    const maxShip = Math.round((Math.min(picked, selectedTask.quantity) - shipped) * 100) / 100;
                    if (maxShip <= 0) return null;
                    const hold = selectedTask.payment_hold;          // F-10 — termin CBD/DP
                    const held = !!hold?.blocked;
                    return (
                      <>
                      {hold && (
                        <DispatchPaymentGatePanel key={`${selectedTask.order_id}:${hold.paid || 0}:${hold.released?.at || ""}`}
                          orderId={selectedTask.order_id} currentUser={user} initial={hold} testPrefix="outbound-gate"
                          onChanged={(g) => { setTasks((prev) => prev.map((x) => x.order_id === selectedTask.order_id ? { ...x, payment_hold: g } : x)); setSelectedTask((t) => ({ ...t, payment_hold: g })); }} />
                      )}
                      <LoadingCheckPanel orderId={selectedTask.order_id} warehouseId={selectedTask.warehouse_id} soNumber={selectedTask.so_number || selectedTask.order_number} />
                      <div data-testid="dispatch-panel" className="rounded-lg border border-[#BFE6CC] bg-[#F1FBF4] p-2.5 space-y-2">
                        <div className="flex items-center justify-between text-[10.5px]">
                          <span className="text-[#6B6B73]">Siap dikirim: <strong className="text-[#1C7A3E] tabular-nums">{formatQty(maxShip)} {selectedTask.unit}</strong></span>
                          {shipped > 0 && <span className="text-[#B23B14]">Sudah dikirim: {formatQty(shipped)}</span>}
                        </div>
                        <p data-testid="dispatch-whole-roll-hint" className="text-[10px] text-[#6B6B73]">
                          Kirim sebagian = sejumlah roll UTUH yang sudah diambil (roll tidak dipecah saat kirim — potong lewat Antrean Potong).
                        </p>
                        <div className="flex gap-2">
                          <input type="number" min="0" max={maxShip} step="any"
                            data-testid="dispatch-qty-input"
                            value={shipQty} onChange={(e) => setShipQty(e.target.value)}
                            placeholder={`Maks ${maxShip}`}
                            className="w-24 border border-[#BFE6CC] rounded-lg px-2 py-1.5 text-[12px] tabular-nums" />
                          <button onClick={() => handleDispatch(true)} disabled={submitting || held}
                            title={held ? hold.message : undefined}
                            data-testid={`dispatch-partial-${selectedTask.id}`}
                            className="bg-[#FF9500] hover:bg-[#CC7700] text-white rounded-lg px-3 py-1.5 text-[11.5px] font-semibold flex items-center gap-1.5 disabled:opacity-50">
                            <Send size={12} /> Kirim Sebagian
                          </button>
                          <button onClick={() => handleDispatch(false)} disabled={submitting || held}
                            title={held ? hold.message : undefined}
                            data-testid={`dispatch-all-${selectedTask.id}`}
                            className="flex-1 bg-[#34C759] hover:bg-[#28A745] text-white rounded-lg px-3 py-1.5 text-[11.5px] font-semibold flex items-center justify-center gap-1.5 disabled:opacity-50">
                            <Send size={12} /> Kirim Semua ({formatQty(maxShip)})
                          </button>
                        </div>
                        {siblingsReady.length > 1 && (
                          <button onClick={handleDispatchBatch} disabled={submitting || held} data-testid={`dispatch-batch-${selectedTask.id}`}
                            className="mt-2 w-full rounded-lg border border-[#34C759] bg-white px-3 py-1.5 text-[11.5px] font-semibold text-[#1C7A3E] disabled:opacity-50">
                            <Send size={12} className="mr-1 inline" /> Kirim semua tugas {selectedTask.order_number} di gudang ini — 1 Surat Jalan ({siblingsReady.length} baris)
                          </button>
                        )}
                      </div>
                      </>
                    );
                  })()}
                </>
              )}

              {['dispatched', 'partially_shipped'].includes(selectedTask.status) && (
                <div className={`rounded-lg p-3 border ${selectedTask.status === 'dispatched' ? 'bg-green-50 border-green-200' : 'bg-[#FFF3EA] border-[#FFD2B5]'}`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className={`text-[12px] font-semibold ${selectedTask.status === 'dispatched' ? 'text-green-700' : 'text-[#B23B14]'}`}>
                        {selectedTask.status === 'dispatched' ? 'Terkirim Penuh!' : 'Terkirim Sebagian'}
                      </p>
                      <p className="text-[11px] text-[#6B6B73]">
                        {formatQty(selectedTask.shipped_qty || 0)} / {formatQty(selectedTask.quantity)} {selectedTask.unit} terkirim
                        {lastShipment?.shipment_no && <span className="ml-1 font-semibold text-[#0058CC]">· {lastShipment.shipment_no}</span>}
                      </p>
                    </div>
                    <button onClick={() => handleViewSuratJalan(selectedTask.order_id, selectedTask.warehouse_id)}
                      data-testid={`view-surat-jalan-${selectedTask.id}`}
                      className="flex items-center gap-1.5 bg-[#007AFF] text-white rounded-lg px-3 py-1.5 text-[11px] font-semibold">
                      <FileText size={12} /> Surat Jalan
                    </button>
                    {lastShipment?.id && !lastShipment?.logistics_id && (
                      <button onClick={() => openLogistics({ createFromShipmentId: lastShipment.id })}
                        data-testid={`create-delivery-${selectedTask.id}`} title="Lanjut ke Logistik: buat pengiriman untuk SJ ini"
                        className="ml-2 flex items-center gap-1.5 bg-[#1F7A45] text-white rounded-lg px-3 py-1.5 text-[11px] font-semibold">
                        Buat Pengiriman
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </OpsSplit>

      {/* Escalate Modal — Fase 4 · R3 (L-03): FormModal baku (layar penuh di HP, Esc berlapis, galat di kaki pop-up).
          Testid `outbound-escalate-reason` / `-submit` tetap. */}
      <FormModal open={showEscalateModal} onClose={() => setShowEscalateModal(false)} size="sm" icon={AlertTriangle}
        title="Eskalasi ke Manager" testId="outbound-escalate-modal" onSubmit={handleEscalate} busy={submitting}
        error={escalateError} submitTestId="outbound-escalate-submit" submitLabel="Eskalasi">
        <textarea value={escalationReason} onChange={(e) => setEscalationReason(e.target.value)}
          data-testid="outbound-escalate-reason" className="field w-full" rows="3"
          placeholder="Alasan eskalasi (contoh: Stok fisik hanya 40m, sistem 50m)" />
      </FormModal>
    </div>
  );
}
