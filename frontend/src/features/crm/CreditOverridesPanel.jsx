import { useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { ShieldCheck, Check, XCircle, Clock3, CheckCircle2, Ban } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";
import useListSearch from "@/hooks/useListSearch";
import ConfirmModal from "../../components/ConfirmModal";
import { fmtDate } from "./crmUtils";
import { can } from "../../config/roles";
import { docStatusLabel } from "../../utils/docStatus";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyPost } from "../../utils/moneyRequest";
import { apiErrorText } from "../../utils/apiError";
import { SCOPE_LABEL } from "./creditOverrideUi";

/** Status izin: ikon + teks + warna (kelas `status-pill` yang ada). Izin disetujui yang lewat masa berlaku = Kedaluwarsa. */
function IzinStatus({ row }) {
  const st = row.status === "approved" && row.expired ? "expired" : row.status;
  const meta = {
    pending: ["status-pending", Clock3], approved: ["status-done", CheckCircle2], rejected: ["status-rejected", XCircle],
    cancelled: ["status-cancelled", Ban], expired: ["status-expired", Ban],
  }[st] || ["status-draft", Clock3];
  const Icon = meta[1];
  return <span className={`status-pill ${meta[0]} whitespace-nowrap`} data-testid={`override-status-${row.id}`}><Icon size={11} aria-hidden="true" /> {docStatusLabel(st)}</span>;
}

/** Persetujuan izin kredit (KN_17 §5.2 / S37; CR-T3 — lingkup, sisa, masa berlaku, alasan). */
export default function CreditOverridesPanel({ currentUser }) {
  // CR-T3 — daftar dibaca pemegang `credit_override.view` (setara `customer.view` lama); memutus `credit_override.approve`.
  const canDecide = can(currentUser?.permissions, "credit_override", "approve");
  const [rows, setRows] = useState([]);
  const srch = useListSearch(rows, null, { testId: "overrides", placeholder: "Cari pelanggan / pemohon / alasan…" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState("pending");
  const [confirm, setConfirm] = useState(null); // {row, decision}
  const intent = useIntentKey("putus-izin-kredit");

  const canView = can(currentUser?.permissions, "credit_override", "view");
  useEffect(() => { if (canView) load(); else setLoading(false); }, [tab, canView]); // eslint-disable-line

  async function load() {
    setLoading(true);
    try {
      const params = tab !== "all" ? { status: tab } : {};
      const r = await axios.get(`${API}/credit-overrides`, { params });
      setRows(Array.isArray(r.data) ? r.data : []);
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat izin kredit."));
    } finally { setLoading(false); }
  }

  async function decide(row, decision, reason) {
    const body = { decision, reason };
    try {
      await intent.send(body, (k) => moneyPost(`${API}/credit-overrides/${row.id}/decision`, body, k));
      setConfirm(null);
      setNotice(`Izin kredit ${row.customer_name} ${decision === "approve" ? "disetujui" : "ditolak"}.`);
      load();
    } catch (e) {
      setConfirm(null);
      setError(apiErrorText(e, "Gagal memproses keputusan."));
    }
  }

  const TABS = [
    { key: "pending", label: "Menunggu" },
    { key: "approved", label: "Disetujui" },
    { key: "rejected", label: "Ditolak" },
    { key: "all", label: "Semua" },
  ];
  const cRow = confirm?.row;
  const ptName = (r) => r?.entity_name || "PT pesanan";

  // CR-T3 — daftar izin kredit dijaga `credit_override.view`; pembaca pelanggan tanpa izin itu tidak memanggil endpointnya.
  if (!canView) {
    return (
      <div className="section-card section-pad mb-3 text-fs-12 text-kn-text-2" data-testid="credit-overrides-no-access">
        Daftar izin kredit hanya untuk pemegang akses melihat izin kredit (modul Pengawasan Tim Sales &amp; Kredit).
      </div>
    );
  }
  return (
    <div data-testid="credit-overrides-panel">
      {notice && <div className="notice-bar success" data-testid="override-notice"><span>{notice}</span><button onClick={() => setNotice("")}>×</button></div>}
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="override-list-error" />

      <div className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2"><ShieldCheck size={16} className="text-kn-action" aria-hidden="true" /><h2 data-testid="overrides-title">Izin Kredit</h2></div>
        </div>
        <div className="section-body">
          <div className="tab-bar mb-3">
            {TABS.map((t) => (
              <button key={t.key} data-testid={`override-tab-${t.key}`} className={`tab-button ${tab === t.key ? "active" : ""}`} onClick={() => setTab(t.key)}>{t.label}</button>
            ))}
          </div>
          {loading ? (
            <div className="py-10 text-center text-fs-12 text-kn-text-2" data-testid="overrides-loading">Memuat...</div>
          ) : rows.length === 0 ? (
            <div className="py-12 text-center text-fs-12 text-kn-text-2" data-testid="overrides-empty">
              Tidak ada izin kredit{tab !== "all" ? ` berstatus ${(TABS.find((t) => t.key === tab)?.label || "").toLowerCase()}` : ""}.
            </div>
          ) : (
            <>
              {srch.toolbar}
              <div className="table-wrap overflow-x-auto">
                <table className="data-table head-wrap w-full text-fs-12" data-testid="overrides-table">
                  <thead>
                    <tr>
                      <th>Pelanggan</th><th>Lingkup</th><th className="text-right">Nominal</th><th className="text-right">Sisa</th>
                      <th>Berlaku sampai</th><th>Alasan</th><th>Pemohon</th><th>Status</th><th className="col-sticky-end">Keputusan</th>
                    </tr>
                  </thead>
                  <tbody>
                    {srch.pageRows.map((r) => (
                      <tr key={r.id} data-testid={`override-row-${r.id}`}>
                        <td className="min-w-[150px]"><p className="font-semibold">{r.customer_name}</p><p className="text-kn-text-2">{ptName(r)}</p></td>
                        <td data-testid={`override-scope-${r.id}`}>{SCOPE_LABEL[r.scope === "pesanan" ? "pesanan" : "pelanggan"]}{r.order_number ? <span className="block text-kn-text-2">{r.order_number}</span> : null}</td>
                        <td className="text-right tabular-nums font-semibold">{formatCurrency(r.amount)}</td>
                        <td className="text-right tabular-nums" data-testid={`override-remaining-${r.id}`}>{r.status === "approved" ? formatCurrency(r.remaining_amount) : "—"}</td>
                        <td data-testid={`override-valid-${r.id}`}>{r.status !== "approved" ? "—" : r.valid_until ? fmtDate(r.valid_until) : "Tanpa batas"}</td>
                        <td className="min-w-[140px]"><p>{r.reason_label || "—"}</p>{r.reason && r.reason !== r.reason_label ? <p className="text-kn-text-2">{r.reason}</p> : null}</td>
                        <td><p>{r.requested_by}</p><p className="text-kn-text-2">{fmtDate(r.created_at)}</p></td>
                        <td><IzinStatus row={r} /></td>
                        <td className="col-sticky-end">
                          {r.status === "pending" && canDecide ? (
                            <div className="flex gap-1">
                              <button data-testid={`override-approve-${r.id}`} onClick={() => setConfirm({ row: r, decision: "approve" })} className="secondary-button btn-sm whitespace-nowrap"><Check size={13} aria-hidden="true" /> Setujui</button>
                              <button data-testid={`override-reject-${r.id}`} onClick={() => setConfirm({ row: r, decision: "reject" })} className="secondary-button btn-sm whitespace-nowrap"><XCircle size={13} aria-hidden="true" /> Tolak</button>
                            </div>
                          ) : r.status === "pending" ? (
                            <span className="text-kn-text-2">Menunggu pemutus izin kredit</span>
                          ) : <span className="text-kn-text-2">{r.decided_by || "—"}</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>

      <ConfirmModal
        open={!!confirm}
        title={confirm?.decision === "approve" ? "Setujui izin kredit" : "Tolak izin kredit"}
        message={cRow ? `${confirm.decision === "approve" ? "Setujui" : "Tolak"} izin kredit ${cRow.customer_name} di ${ptName(cRow)} sebesar ${formatCurrency(cRow.amount)} (lingkup ${SCOPE_LABEL[cRow.scope === "pesanan" ? "pesanan" : "pelanggan"].toLowerCase()})?` : ""}
        confirmLabel={confirm?.decision === "approve" ? "Setujui" : "Tolak"}
        danger={confirm?.decision === "reject"}
        withReason
        reasonLabel="Catatan keputusan"
        onConfirm={(reason) => decide(confirm.row, confirm.decision, reason)}
        onCancel={() => setConfirm(null)}
        testId="override-decision-confirm"
      />
    </div>
  );
}
