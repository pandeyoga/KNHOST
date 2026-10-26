/**
 * MakloonClaimsView (FASE D · PS-11 · D-09) — KOTAK MASUK KLAIM SELISIH MAKLOON.
 * Manajer/admin memutuskan tindakan (potong bon / ganti rugi / terima) di satu layar,
 * plus skor mitra (rata-rata selisih & nilai klaim) untuk evaluasi kemitraan.
 */
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Award, CheckCircle2, Clock, Loader2, RefreshCw, Scale, Wallet } from "lucide-react";
import { PageHeader, MetricRow, SearchBox, StatusTabs } from "../../../components/ListPageParts";
import axios, { API } from "../../../services/apiClient";
import EntityBadge from "../../../components/EntityBadge";
import ErrorNotice from "../../../components/ErrorNotice";
import LinkCard from "../../../components/LinkCard";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import MakloonClaimPanel from "./MakloonClaimPanel";
import { claimStats, CLAIM_STATUS_META, listClaims, partnerScorecard } from "./makloonApi";

const FILTERS = [
  { key: "", label: "Semua" },
  { key: "open", label: "Selisih Terbuka" },
  { key: "pending_approval", label: "Menunggu Persetujuan" },
  { key: "approved", label: "Disetujui" },
  { key: "rejected", label: "Ditolak" },
];

export default function MakloonClaimsView({ currentUser, selectedEntity }) {
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState({});
  const [score, setScore] = useState([]);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      const [c, s, sc] = await Promise.all([
        listClaims({ ...params, ...(status ? { status } : {}) }),
        claimStats(params).catch(() => ({})),
        partnerScorecard(params).catch(() => []),
      ]);
      setRows(Array.isArray(c) ? c : []);
      setStats(s || {});
      setScore(Array.isArray(sc) ? sc : []);
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat daftar klaim makloon.");
    } finally {
      setLoading(false);
    }
  }, [selectedEntity, status]);
  useEffect(() => { load(); }, [load]);

  const filtered = rows.filter((r) => {
    const term = q.trim().toLowerCase();
    if (!term) return true;
    return [r.mko_number, r.makloon_name, r.output_name].some((v) => (v || "").toLowerCase().includes(term));
  });

  return (
    <div data-testid="makloon-claims-view" className="view-container">
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="claims-error" />
      <PageHeader icon={Scale} title={<span data-testid="makloon-claims-title">Klaim Selisih Makloon</span>}
        subtitle="Hasil makloon di luar toleransi kontrak — putuskan potong bon, ganti rugi, atau terima; lalu nilai kinerja mitra."
        actions={<button className="secondary-button" onClick={load} data-testid="claims-refresh"><RefreshCw size={13} /> Muat ulang</button>} />
      <MetricRow testId="claims-stats" items={[
        { label: "Total klaim", value: String(stats.total ?? 0), icon: Scale },
        { label: "Selisih terbuka", value: String(stats.open ?? 0), icon: AlertTriangle, tone: "#B26A00" },
        { label: "Menunggu persetujuan", value: String(stats.pending_approval ?? 0), icon: Clock },
        { label: "Disetujui", value: String(stats.approved ?? 0), icon: CheckCircle2, tone: "#1B7F4B" },
        { label: "Nilai disetujui", value: formatCurrency(stats.approved_amount || 0), icon: Wallet, tone: "#1B7F4B" },
      ]} />
      <SearchBox value={q} onChange={setQ} testId="claims-search" placeholder="Cari no. pesanan / mitra / produk…" />
      <StatusTabs groupTestId="claims-filters" value={status} onChange={setStatus} testId={(k) => `claims-filter-${k || "all"}`}
        tabs={FILTERS.map((f) => ({ ...f, count: f.key ? stats[f.key] : 0 }))} />

      <div className="grid gap-2.5">
          {loading ? (
            <div className="loading-state"><Loader2 size={22} className="spin" /><p>Memuat klaim…</p></div>
          ) : filtered.length === 0 ? (
            <div className="empty-state" data-testid="claims-empty">
              <Scale size={30} style={{ opacity: 0.3 }} />
              <p className="font-semibold">Tidak ada klaim pada filter ini.</p>
              <p className="text-sm text-muted">Selisih hasil makloon masih dalam toleransi kontrak.</p>
            </div>
          ) : filtered.map((r) => {
            const meta = CLAIM_STATUS_META[r.claim?.status] || CLAIM_STATUS_META.none;
            return (
              <div key={`${r.mko_id}-${r.step_seq}`} className="section-card section-pad"
                data-testid={`claim-row-${r.mko_id}-${r.step_seq}`}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-[12px] font-semibold">
                      <span className="font-mono">{r.mko_number}</span> · langkah {r.step_seq} · {r.process_type}
                    </p>
                    <p className="text-[10.5px] text-[#6B6B73] flex items-center gap-1">
                      <EntityBadge entityId={r.entity_id} /> {r.makloon_name} · {r.output_name}
                      {" "}· hasil {formatQty(r.actual_output_qty)} / estimasi {formatQty(r.expected_output_qty)} {r.output_unit}
                      {r.contract_number ? ` · kontrak ${r.contract_number}` : ""}
                    </p>
                  </div>
                  <span className={`status-pill ${meta.cls}`}>{meta.label}</span>
                </div>
                <MakloonClaimPanel mkoId={r.mko_id} step={{ seq: r.step_seq, claim: r.claim, variance: { ...r.claim, expected_qty: r.expected_output_qty, actual_qty: r.actual_output_qty, unit: r.output_unit } }}
                  currentUser={currentUser} onDone={load} onError={setError} />
              </div>
            );
          })}
      </div>

      {/* Fase 3 · P5 — D-22: tabel "Skor Mitra Makloon" dulu tampil juga di sini; kini satu layar Kinerja Mitra
          Makloon (skor + rekap susut & klaim). Peran yang belum boleh membuka layar itu melihat ringkasan satu baris. */}
      <LinkCard testId="makloon-claims-score-link" icon={Award} what="Skor mitra makloon"
        where="Pesanan Pembelian › Kinerja Mitra Makloon" view="makloon-claim-recap" label="Lihat skor mitra"
        summary={score.length ? `${score.length} mitra dinilai` : "belum ada penerimaan makloon untuk dinilai"} />

    </div>
  );
}
