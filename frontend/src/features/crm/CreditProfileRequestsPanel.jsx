/**
 * CreditProfileRequestsPanel (CR-T1) — antrean "Pengajuan perubahan kredit" di Keuangan › Piutang › Kredit & Plafon,
 * di bawah panel izin lewat batas kredit. Menampilkan pengajuan `diajukan` PT aktif (mode "Semua PT": semua PT yang
 * ditugaskan) dengan tombol yang sama seperti kartu pelanggan: Setujui / Tolak (`credit_profile.approve`), Batalkan
 * (pengaju). Pengaju sendiri saat aturan dua orang → tombol mati + alasan tertulis. CR-T5 memindahkan antrean ini.
 * Sumber: `GET /api/credit-profile-requests?status=diajukan` (50 terbaru; jumlah total ditulis).
 */
import { useCallback, useEffect, useState } from "react";
import { Check, CircleSlash, Clock3, ShieldCheck, X } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import EntityScopeBanner from "../../components/EntityScopeBanner";
import useListSearch from "../../hooks/useListSearch";
import { apiErrorText } from "../../utils/apiError";
import { can } from "../../config/roles";
import { formatDate } from "../../utils/formatters";
import { ChangeLines, useCreditRequestActions } from "./creditProfileUi";

const PAGE_SIZE = 50;
const entityLabel = (e) => e?.short_name || e?.legal_name || "PT";

export default function CreditProfileRequestsPanel({ currentUser }) {
  const perms = currentUser?.permissions;
  const canView = can(perms, "credit_profile", "view");
  const canApprove = can(perms, "credit_profile", "approve");
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const srch = useListSearch(rows, (r) => `${r.customer_name} ${r.number} ${r.requested_by} ${r.reason} ${entityLabel(r.entity)}`,
    { testId: "credit-requests", placeholder: "Cari pelanggan / nomor / pengaju…" });

  const load = useCallback(async () => {
    if (!canView) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/credit-profile-requests`, { params: { status: "diajukan", page: 1, page_size: PAGE_SIZE } });
      setRows(r.data?.items || []);
      setTotal(Number(r.data?.total || 0));
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Pengajuan perubahan kredit belum bisa dimuat."));
    } finally {
      setLoading(false);
    }
  }, [canView]);
  useEffect(() => { load(); }, [load]);
  const actions = useCreditRequestActions({ onDone: (m) => { setNotice(m); load(); }, onError: (m) => { setError(m); load(); } });

  if (!canView) return null;
  return (
    <div className="section-card mt-3" data-testid="credit-requests-panel">
      <div className="section-head">
        <div className="flex items-center gap-2">
          <ShieldCheck size={16} className="text-kn-action" aria-hidden="true" />
          <h2>Pengajuan perubahan kredit</h2>
          <span className="status-pill bg-kn-warning-soft text-kn-warning-text" data-testid="credit-requests-count">
            <Clock3 size={12} aria-hidden="true" />{total} menunggu
          </span>
        </div>
      </div>
      <div className="section-body">
        <EntityScopeBanner testId="credit-requests-scope" className="mb-2" />
        {notice && (
          <div className="notice-bar success mb-2" data-testid="credit-requests-notice" role="status">
            <span>{notice}</span><button type="button" className="icon-button" aria-label="Tutup" onClick={() => setNotice("")}><X size={14} /></button>
          </div>
        )}
        <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="credit-requests-error" />
        {!canApprove && total > 0 && (
          <p className="mb-2 text-fs-12 text-kn-text-2" data-testid="credit-requests-readonly">
            Pengajuan ini berlaku setelah diputus pemegang akses memutus pengajuan kredit.
          </p>
        )}
        {loading && !rows.length ? (
          <p className="py-6 text-center text-fs-13 text-kn-text-2" data-testid="credit-requests-loading">Memuat pengajuan perubahan kredit…</p>
        ) : !rows.length ? (
          !error && <p className="py-6 text-center text-fs-13 text-kn-text-2" data-testid="credit-requests-empty">Tidak ada pengajuan perubahan kredit yang menunggu keputusan.</p>
        ) : (
          <>
            {srch.toolbar}
            <div className="overflow-x-auto">
              <table className="data-table head-wrap w-full" data-testid="credit-requests-table">
                <thead>
                  <tr>
                    <th>Pelanggan</th><th>PT</th><th>Perubahan (lama → baru)</th><th>Diajukan</th>
                    <th className="col-sticky-end">Keputusan</th>
                  </tr>
                </thead>
                <tbody>
                  {srch.pageRows.map((r) => {
                    const ctx = { customerName: r.customer_name, entityName: entityLabel(r.entity) };
                    return (
                      <tr key={r.id} data-testid={`credit-request-row-${r.id}`}>
                        <td className="font-semibold">{r.customer_name}<br /><span className="text-fs-12 font-normal text-kn-text-2">{r.number}</span></td>
                        <td>{entityLabel(r.entity)}</td>
                        <td><ChangeLines req={r} /><p className="mt-0.5 text-fs-12 text-kn-text-2">Alasan: {r.reason}</p></td>
                        <td className="whitespace-nowrap">{r.requested_by}<br /><span className="text-fs-12 text-kn-text-2">{formatDate(r.created_at)}</span></td>
                        <td className="col-sticky-end">
                          <div className="flex flex-wrap items-center gap-1.5">
                            {canApprove && (
                              <>
                                <button type="button" className="primary-button btn-sm" data-testid={`credit-request-approve-${r.id}`}
                                  disabled={Boolean(r.blocked_reason) || actions.busyId === r.id} onClick={() => actions.approve(r, ctx)}>
                                  <Check size={13} aria-hidden="true" />Setujui
                                </button>
                                <button type="button" className="danger-button btn-sm" data-testid={`credit-request-reject-${r.id}`}
                                  disabled={Boolean(r.blocked_reason) || actions.busyId === r.id} onClick={() => actions.reject(r, ctx)}>
                                  <X size={13} aria-hidden="true" />Tolak
                                </button>
                              </>
                            )}
                            {(canApprove || r.can_cancel) && (
                              <button type="button" className="secondary-button btn-sm" data-testid={`credit-request-cancel-${r.id}`}
                                disabled={actions.busyId === r.id} onClick={() => actions.cancel(r, ctx)}>
                                <CircleSlash size={13} aria-hidden="true" />Batalkan
                              </button>
                            )}
                          </div>
                          {!canApprove && !r.can_cancel && (
                            <span className="text-fs-12 text-kn-text-2">Menunggu pemutus</span>
                          )}
                          {canApprove && r.blocked_reason && (
                            <p className="mt-1 max-w-[220px] text-fs-12 text-kn-text-2" data-testid={`credit-request-blocked-${r.id}`}>
                              Anda yang mengajukan — rekan lain yang memutus.
                            </p>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {total > rows.length && (
              <p className="mt-2 text-fs-12 text-kn-text-2" data-testid="credit-requests-more">
                Menampilkan {rows.length} dari {total} pengajuan (terbaru dulu). Putuskan yang tampil untuk melihat sisanya.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
