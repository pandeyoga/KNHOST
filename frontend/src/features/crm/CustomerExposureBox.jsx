/**
 * CustomerExposureBox (CR-T5, K-31) — kotak **Eksposur** kartu pelanggan, pengganti empat ubin "Kontrol Kredit".
 *
 * Baris berlabel tetap (unit): Piutang barang terkirim · Pesanan belum dikirim · Giro belum cair · Titipan & saldo
 * kredit · Eksposur · Plafon · Sisa plafon, dan terpisah "Denda belum dibayar (tidak mengurangi plafon)". Nilai = yang
 * DIPAKAI mesin (L6, `GET /api/customers/{id}/exposure`): baris yang tidak dihitung ditulis "tidak dihitung". Angka
 * rata kanan, `whitespace-nowrap` (sisa plafon negatif "-Rp …" tidak patah). Memuat / galat dibedakan.
 */
import { useCallback, useEffect, useState } from "react";
import { CreditCard } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency } from "../../utils/formatters";

const SIGN = { "-": "−", "=": "", "+": "", "": "" };

function Amount({ row }) {
  if (row.amount === null || row.amount === undefined) return <span className="text-kn-text-2">{row.note || "—"}</span>;
  const neg = Number(row.amount) < 0;
  return (
    <span className={`whitespace-nowrap tabular-nums ${neg ? "text-kn-danger-text" : ""}`}>
      {row.counted && SIGN[row.sign] ? `${SIGN[row.sign]} ` : ""}{formatCurrency(row.amount)}
    </span>
  );
}

export default function CustomerExposureBox({ customerId, selectedEntity, children }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const entityId = selectedEntity && selectedEntity !== "all" ? selectedEntity : "";
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/customers/${customerId}/exposure`, { params: entityId ? { entity_id: entityId } : {} });
      setData(r.data); setError("");
    } catch (e) {
      setError(apiErrorText(e, "Eksposur kredit belum bisa dimuat."));
    } finally { setLoading(false); }
  }, [customerId, entityId]);
  useEffect(() => { load(); }, [load]);

  const pt = data?.entity?.short_name || data?.entity?.legal_name || "";
  return (
    <div className="section-card" data-testid="customer-exposure">
      <div className="section-head">
        <div className="flex min-w-0 items-center gap-2">
          <CreditCard size={14} aria-hidden="true" className="text-kn-action" />
          <h3 className="text-fs-13 font-bold">Eksposur</h3>
        </div>
        {pt && <span className="text-fs-12 text-kn-text-2" data-testid="customer-exposure-pt">{pt}</span>}
      </div>
      <div className="section-body">
        {error ? <ErrorNotice message={error} onRetry={load} testId="customer-exposure-error" />
          : loading && !data ? <p className="py-3 text-fs-12 text-kn-text-2" data-testid="customer-exposure-loading">Memuat eksposur…</p>
            : (
              <>
                <dl className="grid gap-1 text-fs-13" data-testid="customer-exposure-rows">
                  {(data?.rows || []).map((r) => (
                    <div key={r.key} data-testid={`customer-exposure-${r.key}`}
                      className={`flex items-baseline justify-between gap-3 ${r.key === "eksposur" ? "border-t border-kn-divider pt-1 font-bold" : ""}`}>
                      <dt className={r.counted ? "text-kn-text" : "text-kn-text-2"}>{r.label}</dt>
                      <dd className="text-right">
                        <Amount row={r} />
                        {!r.counted && r.amount !== null && r.amount !== undefined && (
                          <span className="block text-fs-12 text-kn-text-2" data-testid={`customer-exposure-${r.key}-note`}>{r.note}</span>
                        )}
                      </dd>
                    </div>
                  ))}
                </dl>
                {data?.penalty && (
                  <div className="mt-2 flex items-baseline justify-between gap-3 border-t border-kn-divider pt-2 text-fs-12"
                    data-testid="customer-exposure-penalty">
                    <span className="text-kn-text-2">{data.penalty.label}</span>
                    <span className="whitespace-nowrap tabular-nums">{formatCurrency(data.penalty.amount)}</span>
                  </div>
                )}
                {data?.note && <p className="mt-1 text-fs-12 text-kn-text-2">{data.note}</p>}
              </>
            )}
      </div>
      {children}
    </div>
  );
}
