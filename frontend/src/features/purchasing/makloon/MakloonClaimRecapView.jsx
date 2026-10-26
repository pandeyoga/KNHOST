import { useCallback, useEffect, useState } from "react";
import { Download, Loader2, RefreshCw, Scale } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import KNSelect from "../../../components/KNSelect";
import KNDatePicker from "@/components/KNDatePicker";
import { MetricRow, PageHeader } from "../../../components/ListPageParts";
import useViewPreset from "../../../hooks/useViewPreset";
import MakloonPartnerScorePanel from "./MakloonPartnerScorePanel";

const SETTLE = { potong_bon: "Potong tagihan jasa", tagih_ganti: "Tagih ganti rugi", terima_catatan: "Diterima (catatan)" };
const STATUS = { posted: "Dibukukan", pending_approval: "Menunggu persetujuan", rejected: "Ditolak", approved: "Disetujui" };
const PAGE = 200;   // AUD-MKL-02 — rincian per halaman; ringkasan & Excel tetap utuh


/** L01 — Rekap susut, klaim & potongan tagihan per mitra makloon (penagihan & evaluasi).
 *  Fase 3 · P5 — D-22: layar ini kini **Kinerja Mitra Makloon** — rekap susut & klaim + bagian "Skor mitra"
 *  (klik mitra → skor proses per mitra). Skor dulu juga tampil di Klaim Selisih Makloon & tab "Skor Mitra"
 *  detail Mitra Makloon; keduanya kini tautan ke sini (preset `{ partner }`). Bagian rekap digerbang izin
 *  endpoint-nya: peran tanpa izin rekap (403) hanya melihat skor mitra. */
export default function MakloonClaimRecapView({ selectedEntity }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [denied, setDenied] = useState(false);
  const [loadedOnce, setLoadedOnce] = useState(false);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [partner, setPartner] = useState("");
  const [offset, setOffset] = useState(0);
  const [focusPartner, setFocusPartner] = useState("");
  useViewPreset("makloon-claim-recap", (p) => { if (p.partner) setFocusPartner(p.partner); });

  const download = async () => {
    setBusy(true); setErr("");
    try {
      const res = await axios.get(`${API}/makloon-claims/recap.xlsx`, { params: { date_from: from, date_to: to, makloon_id: partner }, responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url; a.download = `rekap_klaim_mitra_${from || "awal"}_${to || "sekarang"}.xlsx`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { setErr("Gagal mengunduh Excel rekap."); }
    finally { setBusy(false); }
  };

  const load = useCallback(async () => {
    setBusy(true); setErr("");
    try {
      const { data: d } = await axios.get(`${API}/makloon-claims/recap`, {
        params: { date_from: from, date_to: to, makloon_id: partner, rows_offset: offset, rows_limit: PAGE } });
      setData(d); setDenied(false);
    } catch (e) {
      if (e.response?.status === 403) setDenied(true);
      else setErr(e.response?.data?.detail || "Gagal memuat rekap.");
    }
    finally { setBusy(false); setLoadedOnce(true); }
  }, [from, to, partner, offset]);
  useEffect(() => { load(); }, [load, selectedEntity]);
  // halaman di luar jangkauan (mis. ganti badan usaha) → kembali ke halaman pertama
  useEffect(() => { if (data && offset > 0 && offset >= (data.rows_total || 0)) setOffset(0); }, [data, offset]);

  const [partnerOpts, setPartnerOpts] = useState([]);
  useEffect(() => { if (data && !partner && !from && !to) setPartnerOpts(data.partners || []); }, [data, partner, from, to]);
  const t = data?.totals || {};
  const rows = (data?.rows || []).filter((r) => !partner || r.makloon_id === partner);
  const total = data?.rows_total ?? rows.length;
  const first = total ? (data?.rows_offset || 0) + 1 : 0;
  const last = (data?.rows_offset || 0) + (data?.rows || []).length;
  return (
    <section className="view-container" data-testid="makloon-claim-recap">
      {/* UAT 24 Okt (audit UI tahap 2) — G4-25: kerangka sama dengan tab saudara (PageHeader + kartu
          penyaring berlabel + MetricRow); nilai 0 tidak lagi merah/hijau.
          Fase 4 · R3 (L-07/L-08) — dua tabel rekap = `.data-table` baku dalam `.table-container` (dulu tabel mentah). */}
      <PageHeader icon={Scale} title={<span data-testid="recap-title">Kinerja Mitra Makloon</span>}
        subtitle="Skor mitra (hasil vs target, klaim, yield proses) dan rekap susut, piutang klaim & potongan tagihan per mitra dalam periode."
        actions={denied ? null : <>
          <button className="secondary-button" onClick={download} disabled={busy} data-testid="recap-download-xlsx">
            <Download size={13} /> Unduh Excel
          </button>
          <button className="secondary-button" onClick={load} disabled={busy} data-testid="recap-reload">
            {busy ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />} Muat ulang
          </button>
        </>} />
      {/* Skor mitra dirender sesudah rekap dimuat sekali (urutan muat stabil; 403 rekap tetap menampilkan skor). */}
      {loadedOnce && (
        <MakloonPartnerScorePanel selectedEntity={selectedEntity} focusPartner={focusPartner}
          onFocusConsumed={() => setFocusPartner("")} />
      )}
      {denied ? (
        <p className="section-card section-pad text-[12px] text-[#6B6B73]" data-testid="recap-denied">
          Rekap susut &amp; klaim (beban, piutang klaim, potongan tagihan) hanya untuk peran berizin keuangan / persetujuan
          susut makloon. Skor mitra di atas tetap bisa dipakai.
        </p>
      ) : (<>
      <div className="section-card section-pad">
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
          <label className="block">
            <span className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Dari tanggal</span>
            <KNDatePicker data-testid="recap-from" placeholder="Awal" value={from} onChange={(v) => { setFrom(v || ""); setOffset(0); }} />
          </label>
          <label className="block">
            <span className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Sampai tanggal</span>
            <KNDatePicker data-testid="recap-to" placeholder="Sekarang" min={from} value={to} onChange={(v) => { setTo(v || ""); setOffset(0); }} />
          </label>
          <label className="block">
            <span className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Mitra makloon</span>
            <KNSelect className="field" value={partner} onValueChange={(v) => { setPartner(v); setOffset(0); }} data-testid="recap-partner"
              aria-label="Mitra makloon" options={[{ value: "", label: "Semua mitra" }, ...partnerOpts.map((p) => ({ value: p.makloon_id, label: p.makloon_name }))]} />
          </label>
        </div>
      </div>
      {err && <p className="text-[12px] text-[#C0392B]" data-testid="recap-error">{err}</p>}
      <MetricRow items={[
        { label: "Beban susut wajar", value: formatCurrency(t.loss_expense || 0), testId: "recap-kpi-expense" },
        { label: "Piutang klaim mitra", value: formatCurrency(t.receivable_total || 0), testId: "recap-kpi-receivable", tone: Number(t.receivable_total) > 0 ? "#A8221A" : undefined },
        { label: "Dipotong dari tagihan", value: formatCurrency(t.deducted_total || 0), testId: "recap-kpi-deducted", tone: Number(t.deducted_total) > 0 ? "#0A7A3B" : undefined },
        { label: "Susut menunggu", value: String(t.loss_pending || 0), testId: "recap-kpi-loss-pending" },
        { label: "Klaim selisih menunggu", value: String(t.variance_pending || 0), testId: "recap-kpi-variance-pending" },
      ]} />
      <div className="table-container">
        <table className="data-table" data-testid="recap-partner-table">
          <thead>
            <tr><th className="px-3 py-2">Mitra</th><th className="px-3 py-2 text-right">Kejadian susut</th><th className="px-3 py-2 text-right">Qty susut</th>
              <th className="px-3 py-2 text-right">Beban wajar</th><th className="px-3 py-2 text-right">Piutang klaim</th><th className="px-3 py-2 text-right">Dipotong tagihan</th>
              <th className="px-3 py-2 text-right">Klaim selisih</th><th className="px-3 py-2 text-right">Menunggu</th></tr>
          </thead>
          <tbody>
            {(data?.partners || []).filter((p) => !partner || p.makloon_id === partner).map((p) => (
              <tr key={p.makloon_id} className="border-t border-[#F0F0F3]" data-testid={`recap-partner-${p.makloon_id}`}>
                <td className="px-3 py-2 font-semibold">{p.makloon_name}</td>
                <td className="px-3 py-2 text-right tabular-nums">{p.loss_events}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatQty(p.loss_qty)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(p.loss_expense)}</td>
                <td className={`px-3 py-2 text-right tabular-nums ${Number(p.receivable_total) > 0 ? "text-[#A8221A]" : ""}`}>{formatCurrency(p.receivable_total)}</td>
                <td className={`px-3 py-2 text-right tabular-nums ${Number(p.deducted_total) > 0 ? "text-[#0A7A3B]" : ""}`}>{formatCurrency(p.deducted_total)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{p.variance_claims} · {formatCurrency(p.variance_claim_amount)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{p.loss_pending + p.variance_pending}</td>
              </tr>
            ))}
            {data && !(data.partners || []).length && <tr><td colSpan={8} className="px-3 py-6 text-center text-[#8E8E93]" data-testid="recap-empty">Belum ada susut atau klaim mitra pada periode ini.</td></tr>}
          </tbody>
        </table>
      </div>
      {total > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-[11.5px] text-[#636366]" data-testid="recap-rows-paging">
          <span className="mr-auto" data-testid="recap-rows-range">
            Rincian {first.toLocaleString("id-ID")}–{last.toLocaleString("id-ID")} dari {total.toLocaleString("id-ID")} kejadian
            {total > PAGE ? " · Excel memuat semua rincian" : ""}
          </span>
          <button className="secondary-button !py-1 text-[11.5px]" disabled={busy || offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE))} data-testid="recap-rows-prev">Sebelumnya</button>
          <button className="secondary-button !py-1 text-[11.5px]" disabled={busy || last >= total}
            onClick={() => setOffset(offset + PAGE)} data-testid="recap-rows-next">Berikutnya</button>
        </div>
      )}
      <div className="table-container">
        <table className="data-table text-[11.5px]" data-testid="recap-rows-table">
          <thead>
            <tr><th className="px-3 py-2">Tanggal</th><th className="px-3 py-2">Jenis</th><th className="px-3 py-2">No. Order Makloon</th><th className="px-3 py-2">Mitra</th>
              <th className="px-3 py-2 text-right">Qty</th><th className="px-3 py-2 text-right">Beban</th><th className="px-3 py-2 text-right">Klaim</th>
              <th className="px-3 py-2">Penyelesaian</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Alasan</th></tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={`${r.mko_id}-${r.step_seq}-${i}`} className="border-t border-[#F0F0F3]" data-testid={`recap-row-${i}`}>
                <td className="whitespace-nowrap px-3 py-1.5">{r.at ? new Date(r.at).toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" }) : "—"}</td>
                <td className="px-3 py-1.5">{r.kind === "susut" ? "Susut/hilang" : "Selisih hasil"}</td>
                <td className="whitespace-nowrap px-3 py-1.5 font-semibold" title={`Langkah ${r.step_seq}`}>{r.mko_number} · langkah {r.step_seq}</td>
                <td className="px-3 py-1.5">{r.makloon_name}</td>
                <td className="px-3 py-1.5 text-right tabular-nums">{r.qty != null ? `${formatQty(r.qty)} ${r.unit}` : "—"}</td>
                <td className="px-3 py-1.5 text-right tabular-nums">{formatCurrency(r.expense || 0)}</td>
                <td className="px-3 py-1.5 text-right tabular-nums">{formatCurrency(r.claim || 0)}</td>
                <td className="px-3 py-1.5">{SETTLE[r.settle] || "—"}</td>
                <td className="px-3 py-1.5">{STATUS[r.status] || r.status}</td>
                <td className="max-w-[260px] truncate px-3 py-1.5" title={r.reason}>{r.reason}</td>
              </tr>
            ))}
            {data && rows.length === 0 && <tr><td colSpan={10} className="px-3 py-6 text-center text-[#8E8E93]">Belum ada rincian kejadian pada periode ini.</td></tr>}
          </tbody>
        </table>
      </div>
      </>)}
    </section>
  );
}
