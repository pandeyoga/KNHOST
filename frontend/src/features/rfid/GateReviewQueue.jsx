/**
 * PREP-D2 — Antrean periksa admin gudang untuk gate V2 (AUD-MW-10, K-RFID-09/10). Tab di Monitor Gerbang.
 * Daftar lintasan kuning & merah + sesi dokumen yang ditutup dengan roll kurang, per gudang/gate, dengan saring
 * status/hasil/jenis. Klik baris → rincian (DetailModal) berisi bukti per roll dan tindakan.
 * Merah = pelanggaran (gate terkunci) · Kuning = perlu diperiksa, barang jalan, gate tidak terkunci.
 * PREP-H — muat ulang otomatis 30 dtk (berhenti saat tab tersembunyi, mundur saat galat) + jumlah transaksi gudang
 * gate yang masih menunggu / gagal (pekerja latar).
 */
import { useCallback, useEffect, useState } from "react";
import { ClipboardCheck, RefreshCw } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import DetailModal from "../../components/DetailModal";
import axios, { API } from "../../services/apiClient";
import { EmptyBox, Pill, SectionCard, fmtTime } from "./rfidShared";
import GateReviewDetail from "./GateReviewDetail";
import usePolling from "./usePolling";
import { CASE_KIND, CASE_STATUS, CASE_VERDICT, DIRECTION, VERDICT, codesText, errorText } from "./u300Labels";

const KINDS = [{ value: "", label: "Semua jenis" }, ...Object.entries(CASE_KIND).map(([value, label]) => ({ value, label }))];

export default function GateReviewQueue({ whId, devices = [] }) {
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("open");
  const [verdict, setVerdict] = useState("");
  const [kind, setKind] = useState("");
  const [deviceId, setDeviceId] = useState("");
  const [openId, setOpenId] = useState(null);
  // FIX-7 (B3b LST-09) — kursor `next_before` dari server kini dipakai: "Muat lebih lama" menambah 100 kasus berikutnya
  // (dulu baris ke-101 dst. tak terjangkau tanpa tanda). Halaman pertama tetap dimuat ulang otomatis; kasus lama yang
  // sudah dimuat disimpan terpisah (`older`) sampai saringan berubah.
  const [nextBefore, setNextBefore] = useState(null);
  const [older, setOlder] = useState([]);
  const [olderNext, setOlderNext] = useState(null);
  const [olderBusy, setOlderBusy] = useState(false);
  const filterParams = useCallback(() => {
    const params = { status, limit: 100 };
    if (whId) params.warehouse_id = whId;
    if (verdict) params.verdict = verdict;
    if (kind) params.kind = kind;
    if (deviceId) params.device_id = deviceId;
    return params;
  }, [whId, status, verdict, kind, deviceId]);
  useEffect(() => { setOlder([]); setOlderNext(null); }, [filterParams]);
  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const params = { status, limit: 100 };
      if (whId) params.warehouse_id = whId;
      if (verdict) params.verdict = verdict;
      if (kind) params.kind = kind;
      if (deviceId) params.device_id = deviceId;
      const [r, s] = await Promise.all([
        axios.get(`${API}/rfid/v2/ops/reviews`, { params }),
        axios.get(`${API}/rfid/v2/ops/reviews/summary`, { params: whId ? { warehouse_id: whId } : {} }),
      ]);
      setRows(r.data.reviews || []); setSummary(s.data); setError("");
      setNextBefore(r.data.next_before || null);
      return true;
    } catch (e) { setError(errorText(e)); return false; } finally { setLoading(false); }
  }, [whId, status, verdict, kind, deviceId]);
  useEffect(() => { load(); }, [load]);
  usePolling(async () => { if (!(await load(true))) throw new Error("antrean"); },
    { intervalMs: 30000, maxMs: 120000, immediate: false, enabled: !openId }, [load]);
  const loadOlder = async () => {
    const before = older.length ? olderNext : nextBefore;
    if (!before) return;
    setOlderBusy(true);
    try {
      const r = await axios.get(`${API}/rfid/v2/ops/reviews`, { params: { ...filterParams(), before } });
      setOlder((prev) => [...prev, ...(r.data.reviews || [])]);
      setOlderNext(r.data.next_before || null);
    } catch (e) { setError(errorText(e)); } finally { setOlderBusy(false); }
  };
  const shownIds = new Set(rows.map((c) => c.case_id));
  const allRows = [...rows, ...older.filter((c) => !shownIds.has(c.case_id))];
  const hasOlder = older.length ? !!olderNext : !!nextBefore;
  const txn = summary?.txn;
  const devOpts = [{ value: "", label: "Semua gate" }, ...devices.map((d) => ({ value: d.id, label: d.code || d.name }))];
  return (
    <SectionCard testId="gate-review-queue" title="Antrean periksa gate"
      right={<button type="button" className="secondary-button !py-1 text-[12px]" onClick={() => load()} disabled={loading}>
        <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Muat ulang</button>}>
      <div className="space-y-3">
        <p className="text-[11px] text-[#6B6B73]" data-testid="gate-review-summary">
          Terbuka {summary?.open ?? "—"} · merah {summary?.red ?? "—"} · kuning {summary?.review ?? "—"}.
          {" "}Kuning = barang jalan, gate tidak terkunci; roll yang cocok sudah dicatat, sisanya menunggu keputusan di sini.</p>
        {txn && (txn.pending + txn.processing + txn.error + txn.gave_up > 0) && (
          <p className="text-fs-12 text-kn-warning-text" data-testid="gate-review-txn">
            Transaksi gudang gate: {txn.pending + txn.processing} sedang diproses · {txn.error} gagal (diulang otomatis)
            {txn.gave_up ? ` · ${txn.gave_up} perlu "Ulangi transaksi"` : ""}.</p>
        )}
        <div className="flex flex-wrap gap-2">
          <KNSelect data-testid="gate-review-status" value={status} onValueChange={setStatus} options={CASE_STATUS}
            className="field !py-1 !px-2 text-[12px] w-auto" />
          <KNSelect data-testid="gate-review-verdict-filter" value={verdict} onValueChange={setVerdict} options={CASE_VERDICT}
            className="field !py-1 !px-2 text-[12px] w-auto" />
          <KNSelect data-testid="gate-review-kind" value={kind} onValueChange={setKind} options={KINDS}
            className="field !py-1 !px-2 text-[12px] w-auto" />
          <KNSelect data-testid="gate-review-device" value={deviceId} onValueChange={setDeviceId} options={devOpts}
            className="field !py-1 !px-2 text-[12px] w-auto" />
        </div>
        {error && <ErrorNotice message={error} onRetry={() => load()} />}
        {!loading && allRows.length === 0 ? (
          <EmptyBox icon={ClipboardCheck} text="Tidak ada lintasan yang perlu diperiksa untuk saringan ini." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[12px]" data-testid="gate-review-list">
              <thead><tr className="text-[11px] text-[#6B6B73]">
                <th className="p-2">Waktu</th><th className="p-2">Gate / sumber</th><th className="p-2">Hasil</th>
                <th className="p-2">Alasan</th><th className="p-2">Roll perlu tindakan</th><th className="p-2" />
              </tr></thead>
              <tbody>
                {allRows.map((c) => {
                  const v = VERDICT[c.verdict] || VERDICT.UNKNOWN;
                  const todo = (c.rolls || []).filter((r) => ["open", "rescan"].includes(r.state)).length;
                  return (
                    <tr key={c.case_id} className="border-t border-[#EFF0F2] align-top" data-testid={`gate-review-row-${c.case_id}`}>
                      <td className="p-2">{fmtTime(c.created_at)}{c.simulated && <div><Pill color="purple">simulasi</Pill></div>}</td>
                      <td className="p-2">{c.device_name || CASE_KIND[c.kind]}
                        <div className="text-[10px] text-[#6B6B73]">{DIRECTION[c.direction] || ""} · {(c.sources || []).map((s) => s.display_ref).join(", ") || "tanpa dokumen"}</div></td>
                      <td className="p-2"><Pill color={v.color}>{v.short}</Pill>
                        {c.latch_open && <div className="text-[10px] font-semibold text-[#C0341D]">gate terkunci</div>}
                        {c.status !== "open" && <div className="text-[10px] text-[#1B7E3B]">selesai</div>}</td>
                      <td className="p-2 text-[11px]">{codesText(c.reason_codes) || "—"}</td>
                      <td className="p-2">{todo}</td>
                      <td className="p-2"><button type="button" className="secondary-button !py-1 text-[11px]"
                        data-testid={`gate-review-open-${c.case_id}`} onClick={() => setOpenId(c.case_id)}>Periksa</button></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {hasOlder && !loading && (
          <div data-testid="gate-review-more" role="status"
            className="flex flex-wrap items-center gap-2 rounded-lg border border-kn-divider bg-kn-warning-soft px-3 py-2 text-fs-12 text-kn-warning-text">
            <span>Menampilkan {allRows.length} kasus terbaru — masih ada kasus yang lebih lama untuk saringan ini.</span>
            <button type="button" className="secondary-button btn-sm ml-auto" disabled={olderBusy} onClick={loadOlder}
              data-testid="gate-review-more-btn">{olderBusy ? "Memuat…" : "Muat lebih lama"}</button>
          </div>
        )}
      </div>
      {openId && (
        <DetailModal open onClose={() => setOpenId(null)} size="xl" label="Rincian antrean periksa gate"
          testId="gate-review-modal" showClose={false}>
          <GateReviewDetail caseId={openId} onClose={() => setOpenId(null)} onChanged={() => load()} />
        </DetailModal>
      )}
    </SectionCard>
  );
}
