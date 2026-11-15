/**
 * CustomerBillingTab (CR-T5) — tab **Tagihan** kartu pelanggan: jadwal tagihan terbuka satu PT (kolom seperti rincian
 * umur piutang CR-T2: Pesanan · Tagihan · Jatuh tempo · Nilai · Dibayar · Sisa · Telat) + nota denda pelanggan itu
 * (`PenaltyPanel` baku, tombol mengikuti izin `penalty.*`).
 *
 * Sumber: `GET /api/customers/{id}/billing-schedule?entity_id=` (`payment_plan.view`) dan
 * `GET /api/penalties?customer_id=` (`penalty.view`); bagian tanpa izin tidak dimuat. Lebar tabel ±650 px (Pesanan 100 ·
 * Tagihan 120 · Jatuh tempo 90 · Nilai 90 · Dibayar 90 · Sisa 90 · Telat 70). Memuat / galat / kosong dibedakan.
 *
 * Juga: `CustomerOverrideSection` — bagian **Izin kredit** di tab Kredit (dulu tab "Override Kredit").
 *
 * MN-T3 — `show`: "schedule" (bagian kartu "Tagihan & Jadwal"), "penalty" (bagian "Denda & Kasus"), bawaan keduanya.
 */
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, ShieldAlert, XCircle } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatDate } from "../../utils/formatters";
import { docStatusLabel } from "../../utils/docStatus";
import { can } from "../../config/roles";
import { openTrace } from "../documents/trace/traceDeepLink";
import PenaltyPanel from "../finance/payments/PenaltyPanel";
import { SCOPE_LABEL } from "./creditOverrideUi";   // CR-T3 — lingkup izin kredit

const Money = ({ v, strong }) => <span className={`whitespace-nowrap tabular-nums ${strong ? "font-semibold" : ""}`}>{formatCurrency(v)}</span>;

function Late({ days }) {
  if (days > 0) {
    return (
      <span className="status-pill status-rejected inline-flex items-center gap-1 whitespace-nowrap">
        <AlertTriangle size={12} aria-hidden="true" />{days}
      </span>
    );
  }
  return <span className="whitespace-nowrap text-kn-text-2">{days === 0 ? "0" : `${-days} lagi`}</span>;
}

export default function CustomerBillingTab({ customer, currentUser, selectedEntity, show = "both" }) {
  const perms = currentUser?.permissions;
  const canPlan = can(perms, "payment_plan", "view") && show !== "penalty";
  const canPenalty = can(perms, "penalty", "view") && show !== "schedule";
  const entityId = selectedEntity && selectedEntity !== "all" ? selectedEntity : (customer?.entity_id || "");
  const [sched, setSched] = useState(null);
  const [pens, setPens] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [a, b] = await Promise.all([
        canPlan ? axios.get(`${API}/customers/${customer.id}/billing-schedule`, { params: { entity_id: entityId || undefined } })
          : Promise.resolve(null),
        canPenalty ? axios.get(`${API}/penalties`, { params: { customer_id: customer.id, entity_id: entityId || undefined } })
          : Promise.resolve(null),
      ]);
      setSched(a?.data || null);
      setPens(b?.data?.items || []);
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Tagihan pelanggan belum bisa dimuat."));
    } finally { setLoading(false); }
  }, [customer?.id, entityId, canPlan, canPenalty]);
  useEffect(() => { load(); }, [load]);

  if (loading && !sched && !pens) {
    return <p className="py-6 text-center text-fs-13 text-kn-text-2" data-testid="customer-billing-loading">Memuat tagihan…</p>;
  }
  if (error) return <ErrorNotice message={error} onRetry={load} testId="customer-billing-error" />;
  const rows = sched?.items || [];
  return (
    <div data-testid="customer-billing-tab" className="grid gap-3">
      {canPlan && (
        <section aria-labelledby="customer-billing-schedule-title">
          <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
            <h4 id="customer-billing-schedule-title" className="text-fs-13 font-bold text-kn-text">Jadwal tagihan</h4>
            {rows.length > 0 && (
              <span className="text-fs-12 text-kn-text-2">{sched.total} tagihan terbuka · sisa <Money v={sched.totals?.outstanding} /></span>
            )}
          </div>
          {rows.length === 0 ? (
            <p className="py-3 text-fs-12 text-kn-text-2" data-testid="customer-billing-empty">Tidak ada tagihan terbuka.</p>
          ) : (
            <div className="table-wrap">
              <table className="data-table head-wrap" data-testid="customer-billing-table">
                <thead>
                  <tr>
                    <th>Pesanan</th><th>Tagihan</th><th>Jatuh tempo</th><th className="text-right">Nilai</th>
                    <th className="text-right">Dibayar</th><th className="text-right">Sisa</th>
                    <th className="text-right col-sticky-end">Telat (hari)</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((ln) => (
                    <tr key={`${ln.order_id}:${ln.line_id || ln.seq}`} data-testid={`customer-billing-row-${ln.order_id}-${ln.seq}`}>
                      <td className="whitespace-nowrap">
                        <button type="button" className="link-button font-semibold"
                          onClick={() => openTrace({ docType: "sales_order", docId: ln.order_id, number: ln.order_number })}>
                          {ln.order_number}
                        </button>
                      </td>
                      <td className="min-w-[110px]">
                        <span className="font-medium">{ln.kind_label}{ln.label && ln.label !== ln.kind_label ? ` · ${ln.label}` : ""}</span>
                        {(ln.journal_ids || [])[0] && (
                          <button type="button" className="link-button block text-fs-12"
                            onClick={() => openTrace({ docType: "journal_entry", docId: ln.journal_ids[0], number: (ln.journal_numbers || [])[0] })}>
                            Jurnal {(ln.journal_numbers || [])[0] || ""}
                          </button>
                        )}
                      </td>
                      <td className="whitespace-nowrap">{ln.due_date ? formatDate(ln.due_date) : "—"}</td>
                      <td className="text-right"><Money v={ln.amount} /></td>
                      <td className="text-right"><Money v={ln.paid_amount} /></td>
                      <td className="text-right"><Money v={ln.outstanding} strong /></td>
                      <td className="text-right col-sticky-end"><Late days={ln.days_late} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
      {canPenalty && (
        <section aria-labelledby="customer-billing-penalty-title">
          <h4 id="customer-billing-penalty-title" className="mb-1 text-fs-13 font-bold text-kn-text">Nota denda</h4>
          <PenaltyPanel rows={pens || []} currentUser={currentUser} entityId={entityId} onChanged={load} />
        </section>
      )}
    </div>
  );
}

const OV_STATUS = { approved: ["status-done", CheckCircle2], rejected: ["status-rejected", XCircle] };

function OverrideStatus({ status }) {
  const [cls, Icon] = OV_STATUS[status] || ["status-pending", Clock3];
  return (
    <span className={`status-pill ${cls} inline-flex items-center gap-1`}>
      <Icon size={12} aria-hidden="true" />{docStatusLabel(status)}
    </span>
  );
}

/** Bagian "Izin kredit" di tab Kredit — riwayat izin kredit pelanggan (dulu tab "Override Kredit" / "Izin Kredit"):
 *  lingkup, sisa, masa berlaku, pemakaian (CR-T3). */
export function CustomerOverrideSection({ rows = [] }) {
  return (
    <section className="mt-3" aria-labelledby="customer-override-title" data-testid="customer-override-section">
      <h4 id="customer-override-title" className="mb-1.5 flex items-center gap-1.5 text-fs-13 font-bold text-kn-text">
        <ShieldAlert size={14} aria-hidden="true" />Izin kredit
      </h4>
      {rows.length === 0 ? (
        <p className="text-fs-12 text-kn-text-2" data-testid="customer-override-empty">Belum ada izin kredit.</p>
      ) : (
        <ul className="divide-y divide-kn-divider rounded-lg border border-kn-divider">
          {rows.map((ov) => (
            <li key={ov.id} className="flex flex-wrap items-start justify-between gap-2 px-3 py-2 text-fs-13"
              data-testid={`customer-override-${ov.id}`}>
              <div className="min-w-0">
                <p className="break-words">{ov.reason_label || ov.reason}{ov.reason_label && ov.reason && ov.reason !== ov.reason_label ? ` — ${ov.reason}` : ""}</p>
                {/* CR-T3 — lingkup, sisa, masa berlaku, dan jejak pemakaian izin */}
                <p className="text-fs-12 text-kn-text-2">
                  <Money v={ov.amount} /> · {SCOPE_LABEL[ov.scope === "pesanan" ? "pesanan" : "pelanggan"]}{ov.order_number ? ` ${ov.order_number}` : ""}
                  {" "}· sisa <Money v={ov.remaining_amount ?? (ov.consumed ? 0 : ov.amount)} />
                  {ov.valid_until ? ` · berlaku sampai ${formatDate(ov.valid_until)}` : ""} · {ov.requested_by} · {formatDate(ov.created_at)}
                </p>
                {(ov.used_by || []).map((u) => (
                  <p key={u.order_id} className="text-fs-12 text-kn-text-2">Dipakai pesanan {u.order_number || u.order_id} · <Money v={u.amount} /> · {formatDate(u.at)}</p>
                ))}
              </div>
              <OverrideStatus status={ov.status} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
