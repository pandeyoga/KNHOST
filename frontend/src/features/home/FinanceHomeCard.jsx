/**
 * FinanceHomeCard (MN-T2) — kartu ringkas **Keuangan** di Beranda Admin (Control Tower) dan Dasbor Manajer, pengganti
 * kartu-kartu keuangan yang dulu dihitung sendiri-sendiri di tiap beranda (rancangan `01` §3 butir 7).
 *
 * Tiga angka dari endpoint yang SAMA dengan tab Beranda Keuangan › Posisi (`GET /api/finance/tower`, `accounting.view`),
 * jadi angkanya tidak bisa berselisih dengan layar itu: Kas & bank (`cash.total`, saldo buku besar akun kas & bank),
 * Piutang lewat jatuh tempo (`ar.overdue`, semua pelanggan — sumber sama dengan layar Piutang, K-01), Hutang belum
 * dibayar (`ap.outstanding`, tagihan pemasok belum lunas). Tautan "Buka Beranda Keuangan". Tanpa izin → tidak
 * digambar; gagal memuat → galat + Coba lagi (bukan angka nol).
 */
import { useCallback, useEffect, useState } from "react";
import { ChevronRight, Landmark, Receipt, Truck, Wallet } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import { MetricRow } from "../../components/ListPageParts";
import { canCurrent } from "../../config/roles";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency } from "../../utils/formatters";

export default function FinanceHomeCard({ selectedEntity = "all", onNavigate, testId = "home-finance-card", className = "" }) {
  const boleh = canCurrent("accounting", "view");
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!boleh) return;
    setState("loading");
    try {
      const params = selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {};
      const r = await axios.get(`${API}/finance/tower`, { params });
      setData(r.data || null); setError(""); setState("ready");
    } catch (e) {
      if (e?.response?.status === 403) { setState("denied"); return; }
      setData(null); setError(apiErrorText(e, "Ringkasan keuangan tidak bisa dimuat.")); setState("error");
    }
  }, [boleh, selectedEntity]);
  useEffect(() => { load(); }, [load]);

  if (!boleh || state === "denied") return null;
  const isi = (v) => (state === "ready" ? formatCurrency(Number(v) || 0) : "—");

  return (
    <section className={`section-card ${className}`.trim()} data-testid={testId}>
      <div className="section-head">
        <div className="flex min-w-0 items-center gap-2">
          <Landmark size={15} aria-hidden="true" className="text-kn-action" />
          <h2>Keuangan</h2>
        </div>
        {onNavigate && (
          <button type="button" className="link-button inline-flex items-center gap-1 whitespace-nowrap"
            data-testid={`${testId}-open`} onClick={() => onNavigate("finance-tower")}>
            Buka Beranda Keuangan <ChevronRight size={12} aria-hidden="true" /></button>
        )}
      </div>
      <div className="section-body grid gap-2">
        {state === "error" ? (
          <ErrorNotice testId={`${testId}-error`} message={error} onRetry={load} />
        ) : (
          <MetricRow testId={`${testId}-metrics`} items={[
            { label: "Kas & bank", value: isi(data?.cash?.total), icon: Wallet, testId: `${testId}-cash`,
              hint: "Saldo buku besar akun kas & bank" },
            { label: "Piutang lewat jatuh tempo", value: isi(data?.ar?.overdue), icon: Receipt, testId: `${testId}-ar-overdue`,
              hint: "Semua pelanggan · sama dengan layar Piutang" },
            { label: "Hutang belum dibayar", value: isi(data?.ap?.outstanding), icon: Truck, testId: `${testId}-ap`,
              hint: "Tagihan pemasok belum lunas" },
          ]} />
        )}
      </div>
    </section>
  );
}
