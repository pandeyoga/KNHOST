/**
 * CustomerPenaltyRule (CR-T4) — bagian "Aturan denda" di tab Kredit kartu pelanggan (`docs/blueprint/unit/CR-T4.md`).
 *
 *  · Nilai yang DIPAKAI mesin denda untuk (pelanggan, PT) beserta asalnya (L6): lencana "ikut PT" (aturan grup / PT)
 *    atau "khusus pelanggan" (profil kredit). Sumber: `GET /api/customers/{id}/penalty-policy?entity_id=`.
 *  · Pelanggan bebas denda → lencana "Bebas denda s.d. {tanggal}" + alasannya; bebas denda yang sudah lewat ditulis
 *    "berakhir … — sekarang ikut PT".
 *  · Mengubahnya = "Ajukan perubahan" tab Kredit (pengajuan perubahan kredit), bukan Pusat Pengaturan.
 *  · Tanpa izin melihat denda: kalimat penjelas, tanpa permintaan ke server. Memuat / galat dibedakan, galat di dalam
 *    bagian (tombol "Coba lagi").
 */
import { useCallback, useEffect, useState } from "react";
import { BadgeCheck, Building2, CalendarClock, UserCog } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import { can } from "../../config/roles";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatDate } from "../../utils/formatters";
import { BASE_LABEL } from "../finance/payments/penaltyRuleUi";

const MODE_LABEL = { draft: "Usulan denda (belum berjurnal)", auto: "Langsung terbit (berjurnal)", off: "Tidak ada denda" };
const pct = (v) => `${String(Number(v || 0)).replace(".", ",")} %`;

function OriginPill({ source, testId }) {
  const khusus = source === "pelanggan";
  const Icon = khusus ? UserCog : Building2;
  return (
    <span className={`status-pill ${khusus ? "bg-kn-action-soft text-kn-action" : "bg-kn-neutral-soft text-kn-neutral"}`}
      data-testid={testId} data-source={source}>
      <Icon size={12} aria-hidden="true" />{khusus ? "khusus pelanggan" : "ikut PT"}
    </span>
  );
}

/** Baris yang tampil: [kunci uji, label, nilai, asal]. */
function rowsOf(eff, src) {
  return [
    ["mode", "Perlakuan denda", MODE_LABEL[eff.mode] || "—", src.mode],
    ["rate", "Tarif denda", `${pct(eff.rate_pct_per_month)} per bulan`, src.rate_pct_per_month],
    ["base", "Dasar hitung", BASE_LABEL[eff.base] || "—", src.base],
    ["cap", "Batas atas", Number(eff.cap_pct) > 0 ? `${pct(eff.cap_pct)} dari dasar` : "Tanpa batas", src.cap_pct],
    ["grace", "Hari tenggang", `${Number(eff.grace_days || 0)} hari`, src.grace_days],
    ["min", "Denda paling kecil yang dibuatkan nota", formatCurrency(Number(eff.min_amount || 0)), src.min_amount],
  ];
}

export default function CustomerPenaltyRule({ customerId, entityId, currentUser, reloadKey }) {
  const canView = can(currentUser?.permissions, "penalty", "view");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!canView || !customerId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/customers/${customerId}/penalty-policy`, { params: entityId ? { entity_id: entityId } : {} });
      setData(r.data);
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Aturan denda belum bisa dimuat."));
    } finally {
      setLoading(false);
    }
  }, [canView, customerId, entityId]);
  useEffect(() => { load(); }, [load, reloadKey]);

  return (
    <section className="mb-3" aria-labelledby="customer-penalty-title" data-testid="customer-penalty-rule">
      <h4 id="customer-penalty-title" className="mb-1.5 text-fs-13 font-bold text-kn-text">Aturan denda</h4>
      {!canView && (
        <p className="text-fs-12 text-kn-text-2" data-testid="customer-penalty-noaccess">
          Aturan denda tampil bagi pemegang akses melihat denda.
        </p>
      )}
      {canView && loading && !data && (
        <p className="py-3 text-center text-fs-13 text-kn-text-2" data-testid="customer-penalty-loading">Memuat aturan denda…</p>
      )}
      {canView && <ErrorNotice message={error} onRetry={load} testId="customer-penalty-error" />}
      {canView && data && (
        <>
          {data.waiver && (
            <div className="mb-2 flex flex-wrap items-center gap-2" data-testid="customer-penalty-waiver">
              <span className="status-pill status-done" data-testid="customer-penalty-waiver-badge">
                <BadgeCheck size={12} aria-hidden="true" />Bebas denda s.d. {formatDate(data.waiver.valid_until)}
              </span>
              <span className="text-fs-12 text-kn-text-2">Alasan: {data.waiver.reason}</span>
            </div>
          )}
          {!data.waiver && data.expired_waiver && (
            <p className="mb-2 flex items-start gap-1.5 rounded-lg border border-kn-divider bg-kn-warning-soft px-3 py-2 text-fs-12 text-kn-warning-text"
              data-testid="customer-penalty-expired">
              <CalendarClock size={14} aria-hidden="true" className="mt-0.5 shrink-0" />
              Bebas denda berakhir {data.expired_waiver.valid_until ? formatDate(data.expired_waiver.valid_until) : "—"} — sekarang ikut PT.
            </p>
          )}
          <dl className="divide-y divide-kn-divider rounded-lg border border-kn-divider" data-testid="customer-penalty-rows">
            {rowsOf(data.effective || {}, data.sources || {}).map(([key, label, value, source]) => (
              <div key={key} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2" data-testid={`customer-penalty-row-${key}`}>
                <dt className="min-w-[180px] flex-1 text-fs-12 text-kn-text-2">{label}</dt>
                <dd className="flex flex-wrap items-center gap-2 text-fs-13 font-semibold text-kn-text">
                  <span data-testid={`customer-penalty-value-${key}`}>{value}</span>
                  <OriginPill source={source} testId={`customer-penalty-source-${key}`} />
                </dd>
              </div>
            ))}
          </dl>
          <p className="mt-1.5 text-fs-12 text-kn-text-2" data-testid="customer-penalty-how">
            Diubah lewat pengajuan perubahan kredit di tab ini. Rencana bayar satu pesanan bisa punya aturan denda sendiri.
          </p>
        </>
      )}
    </section>
  );
}
