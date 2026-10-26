import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle, XCircle, Package, Truck, Eye } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import { apiErrorText } from "../../utils/apiError";
import { notifySuccess } from "../../utils/feedback";
import { PageHeader } from "../../components/ListPageParts";
import FilterChips from "../../components/FilterChips";
import FormModal from "../../components/FormModal";
import { formatQty } from "../../utils/formatters";

/**
 * ManagerEscalationDashboard
 * 
 * Manager dashboard untuk resolve escalated inbound & outbound tasks.
 * Manager bisa adjust qty atau investigate issue.
 *
 * Fase 4 · R3 (L-02/L-03) — kepala = PageHeader baku; saringan jenis = FilterChips (testid `filter-type-*` tetap);
 * pop-up "Selesaikan Eskalasi" = FormModal (layar penuh di HP, Esc berlapis, galat di kaki pop-up).
 */
export default function ManagerEscalationDashboard({ user }) {
  const [escalatedTasks, setEscalatedTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedTask, setSelectedTask] = useState(null);
  const [filterType, setFilterType] = useState("all");
  
  // Resolve state
  const [showResolveModal, setShowResolveModal] = useState(false);
  // FASE P5 — galat penyelesaian tampil DI DALAM pop-up penyelesaian. Kalau ditaruh di
  // bilah halaman, ia tertutup pop-up itu sendiri → manajer hanya melihat tombol yang
  // "tidak jalan" padahal backend menolak dengan alasan yang jelas.
  const [resolveError, setResolveError] = useState("");
  const [resolveData, setResolveData] = useState({
    adjusted_qty: null,
    resolution_notes: ""
  });

  useEffect(() => {
    fetchEscalatedTasks();
  }, [filterType]);

  const fetchEscalatedTasks = async () => {
    setLoading(true);
    try {
      // Fetch both inbound and outbound escalated tasks
      const [inboundRes, outboundRes] = await Promise.all([
        axios.get(`${API}/inbound/tasks?status=escalated`),
        axios.get(`${API}/outbound/tasks?status=escalated`)
      ]);
      
      const inbound = inboundRes.data.map(t => ({ ...t, task_type: "inbound" }));
      const outbound = outboundRes.data.map(t => ({ ...t, task_type: "outbound" }));
      
      let combined = [...inbound, ...outbound];
      
      if (filterType !== "all") {
        combined = combined.filter(t => t.task_type === filterType);
      }
      
      setEscalatedTasks(combined);
      setError("");
    } catch (error) {
      setError(error.response?.data?.detail || "Gagal memuat tugas eskalasi.");
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async () => {
    if (!selectedTask) return;

    if (!resolveData.resolution_notes.trim()) {
      setResolveError("Tulis dulu catatan penyelesaiannya — catatan ini yang menjelaskan "
        + "kepada gudang & audit mengapa jumlahnya disesuaikan.");
      return;
    }
    setResolveError("");

    try {
      const endpoint = selectedTask.task_type === "inbound"
        ? `${API}/inbound/tasks/${selectedTask.id}/resolve-escalation`
        : `${API}/outbound/tasks/${selectedTask.id}/resolve-escalation`;
      
      await axios.post(endpoint, null, {
        params: {
          adjusted_qty: resolveData.adjusted_qty,
          resolution_notes: resolveData.resolution_notes
        }
      });
      
      notifySuccess("Eskalasi diselesaikan", "Tugas dilanjutkan kembali oleh gudang.");
      setShowResolveModal(false);
      setSelectedTask(null);
      setResolveData({ adjusted_qty: null, resolution_notes: "" });
      fetchEscalatedTasks();
    } catch (error) {
      setResolveError(apiErrorText(error, "Gagal menyelesaikan eskalasi."));
    }
  };

  const handleReopen = async (task) => {
    try {
      await axios.post(`${API}/outbound/tasks/${task.id}/reopen-escalation`);
      notifySuccess("Klaim dilepas", "Eskalasi kembali terbuka dan bisa diselesaikan lagi.");
      fetchEscalatedTasks();
    } catch (err) {
      setError(apiErrorText(err, "Gagal membuka kembali eskalasi."));
    }
  };

  const closeResolve = () => {
    setShowResolveModal(false);
    setSelectedTask(null);
    setResolveError("");
    setResolveData({ adjusted_qty: null, resolution_notes: "" });
  };

  const isHanging = (task) => task.escalation?.status === "resolving";
  const hangingCount = escalatedTasks.filter(isHanging).length;

  const getTaskTypeBadge = (type) => {
    return type === "inbound" ? (
      <span className="bg-green-100 text-green-700 text-xs font-semibold px-2 py-1 rounded-full flex items-center gap-1">
        <Package size={12} />
        Barang Masuk
      </span>
    ) : (
      <span className="bg-orange-100 text-orange-700 text-xs font-semibold px-2 py-1 rounded-full flex items-center gap-1">
        <Truck size={12} />
        Barang Keluar
      </span>
    );
  };

  return (
    <div data-testid="escalation-dashboard" className="space-y-4">
      <PageHeader icon={AlertTriangle} title="Eskalasi Gudang" subtitle="Tinjau & selesaikan tugas yang dieskalasi"
        testId="escalation-header"
        actions={(
          <>
            {hangingCount > 0 && (
              <span data-testid="escalation-hanging-count" className="status-pill pill-warning">
                {hangingCount} Menggantung
              </span>
            )}
            {/* Audit UI 127 — merah (bahaya) hanya bila memang ada tugas tereskalasi. */}
            <span data-testid="escalation-count" className={`status-pill ${escalatedTasks.length ? "pill-danger" : "pill-muted"}`}>
              {escalatedTasks.length} Tugas
            </span>
          </>
        )} />

      <FilterChips testId="filter-type" value={filterType} onChange={(v) => setFilterType(v || "all")} ariaLabel="Jenis tugas"
        options={[{ key: "all", label: "Semua" }, { key: "inbound", label: "Barang Masuk" }, { key: "outbound", label: "Barang Keluar" }]} />

      {/* Tasks List */}
      <ErrorNotice message={error} onRetry={fetchEscalatedTasks} onDismiss={() => setError("")} testId="escalation-error" />
      <div className="grid gap-3">
        {loading ? (
          <div className="text-center py-8">Memuat…</div>
        ) : escalatedTasks.length === 0 ? (
          <div className="text-center py-8 text-[#3C3C43]">
            <CheckCircle size={48} className="mx-auto mb-2 text-green-400" />
            <p>Tidak ada tugas yang dieskalasi</p>
            <p className="text-xs mt-1">Semua tugas berjalan lancar!</p>
          </div>
        ) : (
          escalatedTasks.map((task) => (
            <div
              key={task.id}
              data-testid={`escalated-task-${task.id}`}
              className="section-card section-pad"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    {getTaskTypeBadge(task.task_type)}
                    <span className="text-sm font-bold text-[#007AFF]">
                      {task.task_type === "inbound" ? task.po_number : task.order_number}
                    </span>
                  </div>
                  <p className="text-xs text-[#3C3C43]">{task.sku} - {task.product_name}</p>
                  {task.task_type === "inbound" && (
                    <p className="text-xs text-[#3C3C43] mt-1">Gudang: {task.warehouse_name}</p>
                  )}
                  {task.task_type === "outbound" && (
                    <p className="text-xs text-[#3C3C43] mt-1">
                      Pelanggan: {task.customer_name} | Gudang: {task.warehouse_name}
                    </p>
                  )}
                </div>
                <span
                  data-testid={`escalation-status-${task.id}`}
                  className={`text-xs font-semibold px-3 py-1 rounded-full ${isHanging(task) ? "bg-amber-100 text-amber-800" : "bg-red-100 text-red-700"}`}
                >
                  {isHanging(task) ? "MENGGANTUNG (resolving)" : "ESCALATED"}
                </span>
              </div>

              {isHanging(task) && (
                <div data-testid={`escalation-hanging-${task.id}`} className="bg-amber-50 border border-amber-300 rounded-lg p-3 mb-3 text-sm">
                  <p className="font-semibold text-amber-800">Penyelesaian terhenti di tengah</p>
                  <p className="text-amber-700 text-xs mt-1">
                    Diklaim {task.escalation.resolving_at ? new Date(task.escalation.resolving_at).toLocaleString("id-ID") : "—"} tetapi
                    tidak pernah selesai (proses mati / koneksi putus). Roll mungkin sudah dilepas sebagian — periksa
                    stok pesanan sebelum membuka kembali.
                  </p>
                </div>
              )}

              {/* Qty Info */}
              <div className="bg-[#FFF3CD] border border-[#FFC107] rounded-lg p-3 mb-3">
                <p className="text-sm font-semibold text-[#856404] mb-1">Qty Issue:</p>
                {task.task_type === "inbound" ? (
                  <p className="text-sm text-[#856404]">
                    Diharapkan: {formatQty(task.expected_qty)} {task.unit} | Diterima: {formatQty(task.received_qty || 0)} {task.unit}
                  </p>
                ) : (
                  <p className="text-sm text-[#856404]">
                    Diharapkan: {formatQty(task.quantity)} {task.unit} | Diambil: {formatQty(task.picked_qty || 0)} {task.unit}
                  </p>
                )}
              </div>

              {/* Escalation Info */}
              {task.escalation && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-3 text-sm">
                  <p className="font-semibold text-red-700 mb-1">Alasan:</p>
                  <p className="text-red-600">{task.escalation.reason}</p>
                  <p className="text-[#3C3C43] text-xs mt-2">
                    Escalated by: {task.escalation.escalated_by} | {new Date(task.escalation.escalated_at).toLocaleString('id-ID')}
                  </p>
                </div>
              )}

              {/* Action Button */}
              {isHanging(task) ? (
                <button
                  data-testid={`reopen-task-${task.id}`}
                  onClick={() => handleReopen(task)}
                  className="secondary-button w-full justify-center"
                >
                  <XCircle size={14} />
                  Buka Kembali Eskalasi (lepas klaim)
                </button>
              ) : (
              <button
                data-testid={`resolve-task-${task.id}`}
                onClick={() => {
                  setSelectedTask(task);
                  setResolveError("");
                  setShowResolveModal(true);
                }}
                className="primary-button w-full justify-center"
              >
                <Eye size={14} />
                Tinjau & Selesaikan
              </button>
              )}
            </div>
          ))
        )}
      </div>

      {/* Resolve Modal */}
      <FormModal open={showResolveModal && Boolean(selectedTask)} onClose={closeResolve} size="md" icon={CheckCircle}
        title="Selesaikan Eskalasi" testId="escalation-resolve-modal" onSubmit={handleResolve} error={resolveError}
        submitTestId="escalation-resolve-submit" submitLabel="Selesaikan & Lanjutkan Tugas">
        {selectedTask && (
          <>
            {/* Task Info */}
            <div className="bg-[#F2F2F7] rounded-lg p-3 mb-4">
              <div className="flex items-center gap-2 mb-2">
                {getTaskTypeBadge(selectedTask.task_type)}
                <span className="text-sm font-bold">
                  {selectedTask.task_type === "inbound" ? selectedTask.po_number : selectedTask.order_number}
                </span>
              </div>
              <p className="text-sm">{selectedTask.sku} - {selectedTask.product_name}</p>
              <p className="text-xs text-[#3C3C43] mt-1">Gudang: {selectedTask.warehouse_name}</p>
            </div>

            {/* Qty Mismatch */}
            <div className="bg-[#FFF3CD] border border-[#FFC107] rounded-lg p-3 mb-4">
              <p className="text-sm font-semibold text-[#856404]">Status Qty:</p>
              {selectedTask.task_type === "inbound" ? (
                <div className="text-sm text-[#856404] mt-1">
                  <p>Diharapkan: <strong>{formatQty(selectedTask.expected_qty)} {selectedTask.unit}</strong></p>
                  <p>Diterima: <strong>{formatQty(selectedTask.received_qty || 0)} {selectedTask.unit}</strong></p>
                  <p className="text-red-600 font-semibold mt-1">
                    Selisih: {formatQty((selectedTask.expected_qty - (selectedTask.received_qty || 0)))} {selectedTask.unit}
                  </p>
                </div>
              ) : (
                <div className="text-sm text-[#856404] mt-1">
                  <p>Diharapkan: <strong>{formatQty(selectedTask.quantity)} {selectedTask.unit}</strong></p>
                  <p>Sudah Diambil: <strong>{formatQty(selectedTask.picked_qty || 0)} {selectedTask.unit}</strong></p>
                  <p className="text-red-600 font-semibold mt-1">
                    Selisih: {formatQty((selectedTask.quantity - (selectedTask.picked_qty || 0)))} {selectedTask.unit}
                  </p>
                </div>
              )}
            </div>

            {/* Escalation Reason */}
            {selectedTask.escalation && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
                <p className="text-sm font-semibold text-red-700">Alasan Eskalasi:</p>
                <p className="text-sm text-red-600 mt-1">{selectedTask.escalation.reason}</p>
                <p className="text-xs text-[#3C3C43] mt-2">
                  By: {selectedTask.escalation.escalated_by} on {new Date(selectedTask.escalation.escalated_at).toLocaleString('id-ID')}
                </p>
              </div>
            )}

            {/* Resolve Form */}
            <div className="space-y-3 mb-4">
              <div>
                <label className="block text-sm font-medium mb-2">
                  Adjusted Qty (opsional - kosongkan jika tidak adjust)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={resolveData.adjusted_qty || ""}
                  onChange={(e) => setResolveData({ ...resolveData, adjusted_qty: e.target.value ? parseFloat(e.target.value) : null })}
                  className="field w-full"
                  placeholder={`Saat ini: ${formatQty(selectedTask.task_type === "inbound" ? selectedTask.expected_qty : selectedTask.quantity)}`}
                />
                <p className="text-xs text-[#3C3C43] mt-1">
                  Adjust qty jika setelah investigasi memang ada perubahan legitimate (shortage, damage, etc)
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">
                  Catatan Penyelesaian * (wajib)
                </label>
                <textarea
                  value={resolveData.resolution_notes}
                  onChange={(e) => setResolveData({ ...resolveData, resolution_notes: e.target.value })}
                  className="field w-full"
                  rows="4"
                  placeholder="Jelaskan hasil pemeriksaan dan tindakan yang diambil..."
                />
                <p className="text-xs text-[#3C3C43] mt-1">
                  Contoh: "Konfirmasi dengan supplier, barang shortage 10m. Qty disesuaikan ke actual received."
                </p>
              </div>
            </div>
          </>
        )}
      </FormModal>
    </div>
  );
}
