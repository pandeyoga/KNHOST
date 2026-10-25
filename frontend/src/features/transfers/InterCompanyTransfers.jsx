import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import {
  ArrowLeftRight, RefreshCw, Check, X, Clock3, PackageCheck, Building2, Search,
} from "lucide-react";
import { formatQty } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";
import LineFilter from "../../components/LineFilter";   // FASE L
import QtyDual from "../../components/QtyDual";      // FASE U — dua satuan
import { docStatusLabel } from "../../utils/docStatus";
import { askConfirm, askReason } from "../../services/confirmService";

/**
 * Transfer Antar-Entitas (Sub-fase 1.5 — Inter-Company Transfer Flow, KN_15 §7).
 * List + approve (pindah kepemilikan B→E) + reject permintaan transfer inter-company.
 */
export default function InterCompanyTransfers({ currentUser = {} }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [lineFilter, setLineFilter] = useState("");   // FASE L
  const [search, setSearch] = useState("");
  const [busyId, setBusyId] = useState("");

  const canApprove = ["manager", "admin"].includes((currentUser.role || "").toLowerCase());

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await axios.get(`${API}/transfers`, {
        params: { transfer_kind: "inter_entity", ...(lineFilter ? { line: lineFilter } : {}) },
      });
      setRows(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat transfer antar-entitas.");
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [lineFilter]);

  // UAT 24 Okt (audit UI tahap 2) — setujui (memindah kepemilikan & membuat jurnal antar-PT) dulu sekali klik;
  // tolak memakai textarea inline tanpa label/minimal alasan. Keduanya kini lewat dialog standar.
  const itemSummary = (t) => (t.items || []).map((it) => `${it.product_name || it.sku} ${formatQty(it.qty)} ${it.unit || ""}`.trim()).join(", ");
  const approve = async (t) => {
    const id = t.id;
    if (!(await askConfirm({
      title: `Setujui transfer ${t.code}?`,
      message: `Kepemilikan barang pindah dari ${t.source_entity_name || "badan usaha asal"} ke ${t.dest_entity_name || "badan usaha tujuan"}: ${itemSummary(t) || "—"}. Jurnal antar-PT dibuat otomatis.`,
      confirmLabel: "Setujui & pindahkan",
    }))) return;
    setBusyId(id);
    try {
      await axios.post(`${API}/transfers/${id}/approve`, { approved_by: currentUser.name || "Manager" });
      await load();
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal menyetujui transfer.");
    } finally {
      setBusyId("");
    }
  };

  const reject = async (t) => {
    const id = t.id;
    const reason = await askReason({
      title: `Tolak transfer ${t.code}?`,
      message: `Permintaan dari ${t.dest_entity_name || "badan usaha tujuan"} ditolak; barang tetap milik ${t.source_entity_name || "badan usaha asal"}.`,
      reasonLabel: "Alasan penolakan", reasonMinLength: 5, danger: true, confirmLabel: "Tolak transfer",
    });
    if (reason === null) return;
    setBusyId(id);
    try {
      await axios.post(`${API}/transfers/${id}/reject`, {
        rejected_by: currentUser.name || "Manager",
        reason: reason.trim(),
      });
      await load();
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal menolak transfer.");
    } finally {
      setBusyId("");
    }
  };

  const filtered = useMemo(() => rows.filter((r) => {
    if (filter !== "all" && r.status !== filter) return false;
    const hay = `${r.code} ${r.source_entity_name} ${r.dest_entity_name} ${(r.items || []).map((i) => i.product_name).join(" ")}`.toLowerCase();
    return hay.includes(search.toLowerCase());
  }), [rows, filter, search]);

  const counts = useMemo(() => ({
    all: rows.length,
    waiting_approval: rows.filter((r) => r.status === "waiting_approval").length,
    completed: rows.filter((r) => r.status === "completed").length,
  }), [rows]);

  const FILTERS = [
    { id: "all", label: "Semua" },
    { id: "waiting_approval", label: "Menunggu" },
    { id: "completed", label: "Selesai" },
    { id: "rejected", label: "Ditolak" },
  ];

  return (
    <div data-testid="interco-transfers-view" className="grid gap-4">
      <section className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2 min-w-0">
            <ArrowLeftRight size={15} className="text-[#6B219A]" />
            <span className="kicker">Persediaan</span>
            <h2 data-testid="interco-title">Transfer Antar-Entitas</h2>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 rounded-md border border-[#E5E5EA] bg-white px-2 py-1.5 min-w-[180px]">
              <Search size={14} className="text-[#6B6B73]" />
              <input
                data-testid="interco-search"
                className="w-full bg-transparent text-[13px] outline-none"
                placeholder="Cari kode / produk..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <button data-testid="interco-refresh" className="icon-button" onClick={load} aria-label="Muat ulang">
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            </button>
          </div>
        </div>
        <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="interco-error" />
        <div className="px-4 pt-2">
          <LineFilter value={lineFilter} onChange={setLineFilter} storageKey="interco-transfers"
                      allowed={currentUser?.allowed_line_codes} testId="interco-line-filter" />
        </div>
        <div className="tab-bar px-4">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              data-testid={`interco-filter-${f.id}`}
              onClick={() => setFilter(f.id)}
              className={`tab-button ${filter === f.id ? "active" : ""}`}
            >
              {f.label}
              {f.id === "waiting_approval" && counts.waiting_approval > 0 && (
                <span className="ml-1 rounded-full bg-[#FF9500] px-1.5 text-[9px] text-white">{counts.waiting_approval}</span>
              )}
            </button>
          ))}
          {!canApprove && (
            <span className="ml-auto text-[10px] text-[#8E8E93]">Hanya manager/admin yang dapat menyetujui.</span>
          )}
        </div>
      </section>

      {error && (
        <div data-testid="interco-error" className="rounded-md border border-[#F3C7C2] bg-[#FDF1F0] p-3 text-[12px] text-[#A8221A]">
          {error}
        </div>
      )}

      <section className="grid gap-3">
        {loading && (
          <div data-testid="interco-loading" className="section-card animate-pulse p-8 text-center text-[13px] text-[#6B6B73]">
            Memuat transfer…
          </div>
        )}
        {!loading && filtered.length === 0 && (
          <div data-testid="interco-empty" className="section-card p-10 text-center text-[13px] text-[#6B6B73]">
            Belum ada transfer antar-entitas.
          </div>
        )}
        {!loading && filtered.map((t) => (
          <article
            key={t.id}
            data-testid={`interco-card-${t.id}`}
            className="section-card p-0 overflow-hidden"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#EFF0F2] bg-[#FAFBFC] px-4 py-2.5">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-bold uppercase tracking-wide text-[#6B219A]">{t.code}</span>
                <span className={`status-pill status-${t.status}`} data-testid={`interco-status-${t.id}`}>
                  {t.status === "waiting_approval" && <Clock3 size={11} />}
                  {t.status === "completed" && <PackageCheck size={11} />}
                  {docStatusLabel(t.status)}
                </span>
              </div>
              <div className="flex items-center gap-2 text-[12px] font-semibold">
                <span className="flex items-center gap-1 rounded-md bg-[#FFF4E5] px-2 py-1 text-[#8C4A00]">
                  <Building2 size={12} /> {t.source_entity_name}
                </span>
                <ArrowLeftRight size={13} className="text-[#6B219A]" />
                <span className="flex items-center gap-1 rounded-md bg-[#E9F7EE] px-2 py-1 text-[#126E2C]">
                  <Building2 size={12} /> {t.dest_entity_name}
                </span>
              </div>
            </div>

            <div className="px-4 py-3">
              {/* UI/UX 2026-06 — table-fixed + lebar kolom eksplisit: kolom Qty/Lot sejajar antar kartu; padding th/td konsisten */}
              <table className="w-full table-fixed text-[12.5px]">
                <thead>
                  <tr className="text-left text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">
                    <th className="px-2 py-1.5 pl-0">Produk</th>
                    <th className="w-[170px] px-2 py-1.5 text-right">Qty</th>
                    <th className="w-[220px] px-2 py-1.5 pr-0 pl-4">Lot</th>
                  </tr>
                </thead>
                <tbody>
                  {(t.items || []).map((it, idx) => (
                    <tr key={idx} className="border-t border-[#F4F5F7]">
                      <td className="truncate px-2 py-1.5 pl-0" title={it.product_name}>
                        <span className="text-[10px] font-bold uppercase text-[#0058CC]">{it.sku}</span>{" "}
                        <span className="font-medium">{it.product_name}</span>
                      </td>
                      <td className="whitespace-nowrap px-2 py-1.5 text-right font-semibold tabular-nums"><QtyDual rolls={it.qty_rolls} measure={it.qty} unit={it.unit} /></td>
                      <td className="truncate px-2 py-1.5 pr-0 pl-4 text-[#6B6B73]" title={(it.lots || []).join(", ")}>{(it.lots || []).join(", ") || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-[#8E8E93]">
                <span>Diminta: <span className="font-medium text-[#3C3C43]">{t.requested_by || "—"}</span></span>
                {t.linked_order_id && <span title={t.linked_order_id}>SO: <span className="font-medium text-[#3C3C43]">{t.linked_order_number || "terkait pesanan penjualan"}</span></span>}
                {t.approved_by && <span>Disetujui: <span className="font-medium text-[#3C3C43]">{t.approved_by}</span></span>}
                {t.rejected_reason && <span className="text-[#A8221A]">Alasan tolak: {t.rejected_reason}</span>}
              </div>

              {t.status === "waiting_approval" && canApprove && (
                <div className="mt-3 border-t border-[#EFF0F2] pt-3">
                    <div className="flex gap-2">
                      <button
                        data-testid={`interco-approve-${t.id}`}
                        disabled={busyId === t.id}
                        onClick={() => approve(t)}
                        className="primary-button flex items-center gap-1.5"
                      >
                        <Check size={14} /> {busyId === t.id ? "Memproses…" : "Setujui & pindahkan kepemilikan"}
                      </button>
                      <button
                        data-testid={`interco-reject-${t.id}`}
                        disabled={busyId === t.id}
                        onClick={() => reject(t)}
                        className="flex items-center gap-1 rounded-md border border-[#E5E5EA] px-4 py-1.5 text-[12px] font-semibold text-[#A8221A] disabled:opacity-50"
                      >
                        <X size={14} /> Tolak
                      </button>
                    </div>
                </div>
              )}
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
