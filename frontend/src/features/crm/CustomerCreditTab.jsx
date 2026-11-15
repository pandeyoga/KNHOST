/**
 * CustomerCreditTab (CR-T1) — tab "Kredit" kartu pelanggan: profil kredit pelanggan di SATU PT, diubah hanya lewat
 * pengajuan (`docs/blueprint/unit/CR-T1.md`, bagian Layar).
 *
 *  · Banner PT (L4) + pemilih PT bila pengguna ditugaskan di lebih dari satu PT (bilah sendiri, bukan kepala kartu).
 *  · Baris hanya-baca nilai yang DIPAKAI mesin, masing-masing berlencana asal "ikut PT" / "khusus" (L6). Plafon khusus
 *    yang lewat tanggalnya ditulis "Plafon khusus berakhir {tanggal} — sekarang memakai bawaan PT".
 *  · "Ajukan perubahan" (`credit_profile.update`) membuka pop-up baku; tombol mati dengan alasan TERTULIS bila masih ada
 *    pengajuan terbuka.
 *  · Pengajuan terbuka: blok "Menunggu keputusan" (lama → baru) — Setujui/Tolak (`credit_profile.approve`), Batalkan
 *    (pengaju sendiri atau pemutus); pengaju sendiri saat wajib dua orang → tombol mati + alasan tertulis.
 *  · "Riwayat perubahan kredit" (20 pengajuan terakhir yang sudah diputus). Memuat / kosong / galat dibedakan, galat di
 *    dalam tab.
 *  · CR-T4 — bagian "Aturan denda" (`CustomerPenaltyRule`): nilai denda yang berlaku beserta asalnya; diubah lewat
 *    "Ajukan perubahan" yang sama (pilihan Ikut PT · Khusus · Bebas denda).
 * Sumber: `GET /api/customers/{id}/credit-profile?entity_id=`.
 */
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, CircleSlash, Clock3, Paperclip, Send, X } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import EntityScopeBanner from "../../components/EntityScopeBanner";
import KNSelect from "../../components/KNSelect";
import { apiErrorText } from "../../utils/apiError";
import { can } from "../../config/roles";
import { formatCurrency, formatDate } from "../../utils/formatters";
import CreditProfileRequestModal from "./CreditProfileRequestModal";
import CustomerPenaltyRule from "./CustomerPenaltyRule";
import { ChangeLines, RequestStatusPill, SourcePill, useCreditRequestActions, valueText } from "./creditProfileUi";

const entityLabel = (e) => e?.short_name || e?.legal_name || "PT";

/** Baris profil yang berlaku: [kunci uji, label, nilai, asal]. */
function rowsOf(eff, terms) {
  // Plafon 0 = tanpa batas: ditulis kata, bukan "Rp 0" (angka nol tidak mendominasi kartu).
  const limitText = Number(eff.credit_limit) > 0 ? formatCurrency(eff.credit_limit) : "Tanpa batas";
  const khusus = (src) => (src === "khusus" ? "khusus" : src === "data_lama" ? "data_lama" : "bawaan_pt");
  const blokir = eff.credit_status === "blokir_manual";
  const rows = [
    ["limit", "Plafon kredit", limitText, eff.limit_source],
    ["valid-until", "Berlaku sampai", eff.limit_mode === "khusus" ? valueText("limit_valid_until", eff.limit_valid_until) : "—",
      eff.limit_mode === "khusus" ? "khusus" : "bawaan_pt"],
    // CR-T3 — termin di luar daftar kini ditolak gerbang kredit saat pesanan dibuat (tanda "belum dipakai" dicabut)
    ["terms", "Termin yang diizinkan", valueText("allowed_term_codes", eff.allowed_term_codes, terms),
      (eff.allowed_term_codes || []).length ? "khusus" : "bawaan_pt"],
    ["default-term", "Termin bawaan", valueText("default_term_code", eff.default_term_code, terms),
      eff.default_term_code ? "khusus" : "bawaan_pt", true],
    ["block-days", "Tahan pesanan bila telat lebih dari", `${eff.overdue_block_days ?? 0} hari`, khusus(eff.block_days_source)],
    ["status", "Status kredit", valueText("credit_status", eff.credit_status), blokir ? khusus(eff.status_source) : "bawaan_pt"],
  ];
  if (blokir) rows.push(["block-reason", "Alasan blokir", eff.block_reason || "—", khusus(eff.status_source)]);
  if (eff.credit_group_id) rows.push(["group", "Kelompok kredit lintas PT", eff.credit_group_id, "khusus", true]);
  return rows;
}

export default function CustomerCreditTab({ customer, currentUser, selectedEntity, onChanged }) {
  const perms = currentUser?.permissions;
  const canUpdate = can(perms, "credit_profile", "update");
  const canApprove = can(perms, "credit_profile", "approve");
  const startEntity = selectedEntity && selectedEntity !== "all" ? selectedEntity : (customer?.entity_id || "");
  const [entityId, setEntityId] = useState(startEntity);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/customers/${customer.id}/credit-profile`, { params: entityId ? { entity_id: entityId } : {} });
      setData(r.data);
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Profil kredit belum bisa dimuat."));
    } finally {
      setLoading(false);
    }
  }, [customer?.id, entityId]);
  useEffect(() => { load(); }, [load]);

  const done = useCallback(async (msg) => { setNotice(msg); setActionError(""); await load(); onChanged?.(); }, [load, onChanged]);
  const actions = useCreditRequestActions({ onDone: done, onError: (m) => { setActionError(m); load(); } });

  if (loading && !data) {
    return <p className="py-8 text-center text-fs-13 text-kn-text-2" data-testid="customer-credit-loading">Memuat profil kredit…</p>;
  }
  if (!data) {
    return <ErrorNotice message={error || "Profil kredit belum bisa dimuat."} onRetry={load} testId="customer-credit-error" />;
  }

  const eff = data.effective || {};
  const terms = data.term_options || [];
  const pending = data.pending_request;
  const history = data.history || [];
  const options = data.entity_options || [];
  const ctx = { customerName: customer?.name, entityName: entityLabel(data.entity), terms };
  const mine = pending && pending.requested_by_id === currentUser?.id;
  const scopeMeta = { mode: "single", entity_ids: [data.entity?.id], entities: [data.entity || {}], eliminated: false, label: "" };

  return (
    <div data-testid="customer-credit-tab">
      {notice && (
        <div className="notice-bar success mb-2" data-testid="customer-credit-notice" role="status">
          <span>{notice}</span><button type="button" className="icon-button" aria-label="Tutup" onClick={() => setNotice("")}><X size={14} /></button>
        </div>
      )}
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="customer-credit-error" />
      <ErrorNotice message={actionError} onDismiss={() => setActionError("")} testId="customer-credit-action-error" />

      <EntityScopeBanner meta={scopeMeta} testId="customer-credit-scope" className="mb-2" />
      {options.length > 1 && (
        <div className="mb-3 flex flex-wrap items-center gap-2" data-testid="customer-credit-entity-bar">
          <span className="text-fs-12 font-semibold text-kn-text-2">Profil kredit di PT</span>
          <KNSelect value={data.entity?.id || entityId} onValueChange={setEntityId} className="field max-w-[260px]"
            data-testid="customer-credit-entity" options={options.map((e) => ({ value: e.id, label: entityLabel(e) }))} />
        </div>
      )}

      <section className="mb-3" aria-labelledby="customer-credit-effective-title">
        <h4 id="customer-credit-effective-title" className="mb-1.5 text-fs-13 font-bold text-kn-text">Profil kredit yang berlaku</h4>
        {eff.limit_source === "kedaluwarsa" && (
          <p className="mb-2 flex items-start gap-1.5 rounded-lg border border-kn-divider bg-kn-warning-soft px-3 py-2 text-fs-12 text-kn-warning-text"
            data-testid="customer-credit-expired">
            <AlertTriangle size={14} aria-hidden="true" className="mt-0.5 shrink-0" />
            Plafon khusus berakhir {formatDate(eff.limit_valid_until)} — sekarang memakai bawaan PT.
          </p>
        )}
        {eff.data_lama && (
          <p className="mb-2 text-fs-12 text-kn-text-2" data-testid="customer-credit-legacy">
            Nilai bertanda “data lama” dibaca dari data pelanggan sebelum profil kredit dipindahkan; pengajuan pertama menyimpannya di profil.
          </p>
        )}
        <dl className="divide-y divide-kn-divider rounded-lg border border-kn-divider" data-testid="customer-credit-rows">
          {rowsOf(eff, terms).map(([key, label, value, source, unused]) => (
            <div key={key} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2" data-testid={`customer-credit-row-${key}`}>
              <dt className="min-w-[180px] flex-1 text-fs-12 text-kn-text-2">{label}</dt>
              <dd className="flex flex-wrap items-center gap-2 text-fs-13 font-semibold text-kn-text">
                <span data-testid={`customer-credit-value-${key}`}>{value}</span>
                <SourcePill source={source} testId={`customer-credit-source-${key}`} />
                {unused && <span className="text-fs-12 font-normal text-kn-text-2">belum dipakai saat pesanan dibuat</span>}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      {/* CR-T4 — aturan denda yang dipakai mesin untuk pelanggan ini di PT ini (ikut PT / khusus pelanggan / bebas). */}
      <CustomerPenaltyRule customerId={customer?.id} entityId={data.entity?.id || entityId} currentUser={currentUser}
        reloadKey={data} />

      {canUpdate && (
        <div className="mb-3 flex flex-wrap items-center gap-2" data-testid="customer-credit-actions">
          <button type="button" className="primary-button" disabled={Boolean(pending)} onClick={() => setShowForm(true)}
            data-testid="customer-credit-request" aria-describedby={pending ? "customer-credit-request-why" : undefined}>
            <Send size={13} aria-hidden="true" />Ajukan perubahan
          </button>
          {pending && (
            <span id="customer-credit-request-why" className="text-fs-12 text-kn-text-2" data-testid="customer-credit-request-why">
              Masih ada pengajuan yang menunggu keputusan — putuskan atau batalkan dulu.
            </span>
          )}
        </div>
      )}
      {!canUpdate && (
        <p className="mb-3 text-fs-12 text-kn-text-2" data-testid="customer-credit-readonly">
          Perubahan plafon dan blokir diajukan oleh pemegang akses mengajukan perubahan kredit.
        </p>
      )}

      {pending && (
        <section className="mb-3 rounded-lg border border-kn-divider" data-testid="customer-credit-pending" aria-labelledby="customer-credit-pending-title">
          <div className="flex flex-wrap items-center gap-2 border-b border-kn-divider px-3 py-2">
            <h4 id="customer-credit-pending-title" className="text-fs-13 font-bold text-kn-text">Menunggu keputusan</h4>
            <RequestStatusPill status="diajukan" testId="customer-credit-pending-status" />
          </div>
          <div className="px-3 py-2">
            <p className="mb-1.5 text-fs-12 text-kn-text-2">
              {pending.number} · diajukan {pending.requested_by} · {formatDate(pending.created_at)}
            </p>
            <ChangeLines req={pending} terms={terms} testId="customer-credit-pending-changes" />
            <p className="mt-1.5 text-fs-13 text-kn-text">Alasan: {pending.reason}</p>
            {pending.attachment_url && (
              <a className="link-button mt-1 inline-flex items-center gap-1 text-fs-12" href={pending.attachment_url} target="_blank" rel="noreferrer"
                data-testid="customer-credit-pending-attachment"><Paperclip size={12} aria-hidden="true" />Lampiran</a>
            )}
          </div>
          {(canApprove || mine) && (
            <div className="flex flex-wrap items-center gap-2 border-t border-kn-divider px-3 py-2" data-testid="customer-credit-pending-actions">
              {canApprove && (
                <>
                  <button type="button" className="primary-button btn-sm" data-testid="customer-credit-approve"
                    disabled={Boolean(pending.blocked_reason) || actions.busyId === pending.id} onClick={() => actions.approve(pending, ctx)}>
                    <Check size={13} aria-hidden="true" />Setujui
                  </button>
                  <button type="button" className="danger-button btn-sm" data-testid="customer-credit-reject"
                    disabled={Boolean(pending.blocked_reason) || actions.busyId === pending.id} onClick={() => actions.reject(pending, ctx)}>
                    <X size={13} aria-hidden="true" />Tolak
                  </button>
                </>
              )}
              <button type="button" className="secondary-button btn-sm" data-testid="customer-credit-cancel"
                disabled={actions.busyId === pending.id} onClick={() => actions.cancel(pending, ctx)}>
                <CircleSlash size={13} aria-hidden="true" />Batalkan pengajuan
              </button>
              {canApprove && pending.blocked_reason && (
                <span className="text-fs-12 text-kn-text-2" data-testid="customer-credit-blocked">
                  Anda yang mengajukan — rekan lain yang memutus (aturan dua orang di PT ini).
                </span>
              )}
            </div>
          )}
          {!canApprove && !mine && (
            <p className="border-t border-kn-divider px-3 py-2 text-fs-12 text-kn-text-2" data-testid="customer-credit-pending-wait">
              <Clock3 size={12} aria-hidden="true" className="mr-1 inline" />Berlaku setelah diputus pemegang akses memutus pengajuan kredit.
            </p>
          )}
        </section>
      )}

      <section aria-labelledby="customer-credit-history-title">
        <h4 id="customer-credit-history-title" className="mb-1.5 text-fs-13 font-bold text-kn-text">Riwayat perubahan kredit</h4>
        {history.length === 0 ? (
          <p className="py-4 text-center text-fs-13 text-kn-text-2" data-testid="customer-credit-history-empty">Belum ada perubahan kredit.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table head-wrap w-full" data-testid="customer-credit-history">
              <thead>
                <tr><th>Tanggal</th><th>Pengaju</th><th>Pemutus</th><th>Perubahan</th><th>Alasan</th></tr>
              </thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.id} data-testid={`customer-credit-history-${h.id}`}>
                    <td className="whitespace-nowrap">{formatDate(h.decided_at || h.created_at)}<br /><span className="text-fs-12 text-kn-text-2">{h.number}</span></td>
                    <td>{h.requested_by}</td>
                    <td><RequestStatusPill status={h.status} /><br /><span className="text-fs-12">{h.decided_by}</span></td>
                    <td><ChangeLines req={h} terms={terms} /></td>
                    <td className="text-fs-12">{h.reason}{h.decision_note ? <><br /><span className="text-kn-text-2">Catatan: {h.decision_note}</span></> : null}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <CreditProfileRequestModal open={showForm} data={data} canApprove={canApprove}
        onClose={() => setShowForm(false)} onSaved={(msg) => { setShowForm(false); done(msg); }} />
    </div>
  );
}

