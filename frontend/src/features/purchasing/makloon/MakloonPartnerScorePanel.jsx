/**
 * MakloonPartnerScorePanel — bagian "Skor mitra" di Kinerja Mitra Makloon (fase 3 · P5, D-22).
 *
 * Dulu skor mitra tampil di TIGA tempat: kartu "Skor Mitra Makloon" di Klaim Selisih Makloon, tab "Skor Mitra" di
 * detail Mitra Makloon (360°), dan rekap susut & klaim — tiap tempat dengan potongan metrik berbeda. Kini satu
 * layar: tabel skor (turunan klaim, `/makloon-partners/scorecard`), klik mitra → pop-up skor PROSES per mitra
 * (`/makloons/{id}/scorecard`: yield realisasi, pencapaian yield, input/output — dulu di tab 360°).
 * Dua tempat lama kini kartu tautan ke sini. `focusPartner` (preset dari tautan 360°) membuka pop-up mitra itu.
 */
import { useEffect, useState } from "react";
import { Award, BarChart3 } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import DetailModal from "../../../components/DetailModal";
import ResponsiveTable from "../../../components/ResponsiveTable";
import { formatCurrency, formatPct, formatQty } from "../../../utils/formatters";
import { partnerScorecard } from "./makloonApi";
import { isZeroMetric } from "../../../components/ListPageParts";

const pct = (v) => (v == null ? "—" : formatPct(Number(v) * 100));   // P-06 — koma desimal id-ID

// Fase 4 · R3 (L-08) — nilai 0 (mis. selisih "0%") tampil NETRAL, bukan hijau/merah (sama dengan MetricRow baku).
function Kpi({ label, value, tone = "#1C1C1E", testId }) {
  return (
    <div className="rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-2" data-testid={testId}>
      <p className="text-[9.5px] font-bold uppercase text-[#8E8E93]">{label}</p>
      <p className="text-[15px] font-bold tabular-nums leading-tight" style={{ color: isZeroMetric(value) ? "#8E8E93" : tone }}>{value ?? "—"}</p>
    </div>
  );
}

function PartnerDetail({ partner, onClose }) {
  const [card, setCard] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let alive = true;
    axios.get(`${API}/makloons/${partner.makloon_id}/scorecard`)
      .then((r) => { if (alive) setCard(r.data); })
      .catch((e) => { if (alive) setErr(e.response?.data?.detail || "Gagal memuat skor proses mitra."); });
    return () => { alive = false; };
  }, [partner.makloon_id]);
  const sc = card?.metrics || {};
  return (
    <DetailModal onClose={onClose} size="md" framed label={`Skor mitra ${partner.makloon_name || ""}`.trim()}
      testId="mkl-partner-score-modal">
      <div className="grid gap-3">
        <div>
          <p className="text-[10px] font-bold uppercase text-[#0058CC]">Skor mitra makloon</p>
          <h3 className="text-[15px] font-bold" data-testid="mkl-partner-score-name">{partner.makloon_name || partner.makloon_id}</h3>
        </div>
        <section className="grid gap-1.5">
          <p className="text-[11px] font-bold uppercase text-[#6B6B73]">Hasil terima vs target (klaim)</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Kpi label="Langkah selesai" value={partner.steps} />
            <Kpi label="Rata-rata selisih" value={formatPct(partner.avg_variance_pct, 2, { trim: true })}
              tone={(partner.avg_variance_pct ?? 0) < 0 ? "#C0392B" : "#1B7F4B"} />
            <Kpi label="Sesuai target" value={formatPct(partner.on_target_pct, 1, { trim: true })} />
            <Kpi label="Klaim" value={partner.claims} />
            <Kpi label="Nilai klaim" value={formatCurrency(partner.claim_amount || 0)} />
          </div>
        </section>
        <section className="grid gap-1.5" data-testid="mkl-partner-score-process">
          <p className="text-[11px] font-bold uppercase text-[#6B6B73]">Proses (yield)</p>
          {err ? <p className="text-[12px] text-[#C0392B]">{err}</p>
            : !card ? <p className="text-[12px] text-[#6B6B73]">Memuat…</p>
            : !card.has_data ? (
              <p className="py-4 text-center text-[11.5px] text-[#9A9BA3]">Belum ada data proses (mulai terisi setelah Order Makloon dijalankan).</p>
            ) : (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                <Kpi label="Total Pesanan" value={sc.total_orders} />
                <Kpi label="Langkah Diterima" value={sc.received_steps} />
                <Kpi label="Yield Realisasi" value={pct(sc.realized_yield)} tone="#0058CC" />
                <Kpi label="Pencapaian Yield" value={pct(sc.yield_attainment)} />
                <Kpi label="Total Input" value={formatQty(sc.total_input_qty)} />
                <Kpi label="Total Output" value={formatQty(sc.total_output_qty)} />
              </div>
            )}
        </section>
      </div>
    </DetailModal>
  );
}

const COLUMNS = [
  { key: "makloon_name", header: "Mitra", mobile: "title", render: (s) => <span className="font-semibold">{s.makloon_name || s.makloon_id}</span> },
  { key: "steps", header: "Langkah selesai", align: "right", priority: 3 },
  { key: "avg_variance_pct", header: "Rata-rata selisih", align: "right", priority: 1,
    render: (s) => <span className={(s.avg_variance_pct ?? 0) < 0 ? "text-[#C0392B]" : "text-[#1B7F4B]"}>{formatPct(s.avg_variance_pct, 2, { trim: true })}</span> },
  { key: "on_target_pct", header: "Sesuai target", align: "right", priority: 2, render: (s) => formatPct(s.on_target_pct, 1, { trim: true }) },
  { key: "claims", header: "Klaim", align: "right", priority: 4 },
  { key: "claim_amount", header: "Nilai klaim", align: "right", priority: 5, render: (s) => formatCurrency(s.claim_amount || 0) },
];

export default function MakloonPartnerScorePanel({ selectedEntity, focusPartner = "", onFocusConsumed }) {
  const [rows, setRows] = useState(null);
  const [open, setOpen] = useState(null);
  useEffect(() => {
    const params = selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {};
    partnerScorecard(params).then((r) => setRows(Array.isArray(r) ? r : [])).catch(() => setRows([]));
  }, [selectedEntity]);
  // Tautan "Skor mitra" dari detail Mitra Makloon (360°) → langsung buka pop-up mitra itu.
  useEffect(() => {
    if (!focusPartner || rows === null) return;
    setOpen(rows.find((r) => r.makloon_id === focusPartner) || { makloon_id: focusPartner, makloon_name: "" });
    onFocusConsumed?.();
  }, [focusPartner, rows]); // eslint-disable-line

  return (
    <div className="section-card" data-testid="mkl-partner-score">
      <div className="section-head">
        <h3 className="flex items-center gap-2 text-[12.5px] font-bold"><Award size={14} className="text-[#0058CC]" /> Skor mitra</h3>
        <span className="flex items-center gap-1 text-[11px] text-[#6B6B73]"><BarChart3 size={12} /> klik mitra untuk skor proses</span>
      </div>
      <div className="section-body">
        <ResponsiveTable testId="partner-scorecard" rows={rows || []} rowKey="makloon_id" loading={rows === null}
          rowTestId={(s) => `scorecard-row-${s.makloon_id}`} columns={COLUMNS} onRowClick={setOpen}
          empty={<span data-testid="scorecard-empty">Belum ada penerimaan makloon untuk dinilai.</span>} />
      </div>
      {open && <PartnerDetail partner={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
