import { AskKnButton } from "../../components/AskKnButton";
/**
 * MakloonOrderDetailPanel (M3) — detail order makloon + aksi lifecycle.
 * Issue bahan → WIP-at-vendor, Terima hasil (roll + LOT manual), costing, timeline, cancel.
 */
import { useCallback, useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";
import {
  Boxes, ArrowRight, PackageCheck, Send, XCircle,
  Factory, Clock, Receipt, Wallet, Layers, TriangleAlert, Wrench,
} from "lucide-react";
import { formatCurrency, formatDateTime, formatQty } from "../../utils/formatters";
import useProcessTypes from "../../hooks/useProcessTypes";
import { MATERIAL_FLOW_BADGE } from "../../constants/makloonVocab";
import ConfirmModal from "../../components/ConfirmModal";
import DocumentActionsBar from "../documents/DocumentActionsBar";
import { DetailHeader, Panel, Cell, Timeline } from "../../components/DetailParts";
import MakloonClaimPanel from "./makloon/MakloonClaimPanel";
import MakloonPartialReceipts from "./makloon/MakloonPartialReceipts";
import MakloonReturnMaterial, { MakloonReturnHistory } from "./makloon/MakloonReturnMaterial";
import MakloonLossList from "./makloon/MakloonLossList";
import MakloonMaterialLedger from "./makloon/MakloonMaterialLedger";
import { can } from "../../config/roles";
import { recordService } from "./makloon/makloonApi";
import { IssueModal, ReceiveModal, RecordServiceModal } from "./makloon/MkoStepModals";   // Fase 4 · R3 (L-03)
import { MKO_STATUS } from "./mkoStatus";
import QtyDual from "../../components/QtyDual";      // FASE U — dua satuan
import useReceivingMode from "../../hooks/useReceivingMode";

const STEP_STATUS = {
  pending: { label: "Menunggu Issue", cls: "pill-muted" },
  issued: { label: "Di Makloon (WIP)", cls: "pill-info" },
  received: { label: "Diterima", cls: "pill-success" },
  cancelled: { label: "Batal", cls: "pill-danger" },
  returned: { label: "Bahan Diretur", cls: "pill-muted" },
};
/** FASE T — langkah jasa murni tidak pernah "di makloon": kainnya tidak pergi. */
const stepStatusMeta = (s) => {
  if (s.status === "issued" && s.awaiting_return) return { label: "Menunggu Retur Bahan", cls: "pill-warning" };
  const base = STEP_STATUS[s.status] || STEP_STATUS.pending;
  if (s.material_flow === "service_only" && s.status === "pending") {
    return { label: "Menunggu Catat Jasa", cls: "pill-muted" };
  }
  return base;
};
// UAT 24 Okt (audit UI tahap 2) — jam riwayat ber-WIB baku; teks riwayat lama memuat kode mode mentah.
const fmtDT = (s) => formatDateTime(s);
const MODE_TEXT = { process_only: "Proses saja", buy_process: "Beli + Proses" };
const timelineText = (s) => String(s || "").replace(/\((process_only|buy_process)\)/g, (m, k) => `(${MODE_TEXT[k]})`);

export default function MakloonOrderDetailPanel({ mkoId, currentUser, onBack, onError }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [warehouses, setWarehouses] = useState([]);
  const [busy, setBusy] = useState(false);
  const [issueStep, setIssueStep] = useState(null);
  const [receiveStep, setReceiveStep] = useState(null);
  const { isGrn } = useReceivingMode();
  const [serviceStep, setServiceStep] = useState(null);   // FASE T — Catat Jasa
  const [showCancel, setShowCancel] = useState(false);
  const { labelOf: processLabel } = useProcessTypes();

  // Sisir gerbang peran (2026-10-20): kirim bahan = makloon_order.issue, terima/catat jasa = makloon_order.receive,
  // batal = makloon_order.cancel (sama dengan endpoint).
  // UAT 24 Okt (audit UI tahap 2) — G4-15: order DIBATALKAN tidak lagi menawarkan Issue/Terima/Catat Jasa.
  const orderLive = data?.status !== "cancelled";
  const canIssue = can(currentUser?.permissions, "makloon_order", "issue") && orderLive;
  const canReceive = can(currentUser?.permissions, "makloon_order", "receive") && orderLive;
  const canManage = can(currentUser?.permissions, "makloon_order", "cancel");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/makloon-orders/${mkoId}`);
      setData(r.data);
    } catch (e) { onError?.(e.response?.data?.detail || "Gagal memuat order."); onBack?.(); }
    finally { setLoading(false); }
  }, [mkoId]); // eslint-disable-line
  useEffect(() => { load(); }, [load]);
  useEffect(() => { axios.get(`${API}/warehouses`).then((r) => setWarehouses(Array.isArray(r.data) ? r.data : [])).catch(() => {}); }, []);

  async function doIssue(step, whId, docUom, docQty) {
    setBusy(true);
    try {
      const body = { step_seq: step.seq, from_warehouse_id: whId };
      if (docUom && parseFloat(docQty) > 0) { body.doc_uom = docUom; body.doc_qty = parseFloat(docQty); }
      await axios.post(`${API}/makloon-orders/${mkoId}/issue`, body);
      setIssueStep(null); await load();
    } catch (e) { throw new Error(e.response?.data?.detail || "Gagal issue ke makloon."); }   // 23 Okt — tampil di modal
    finally { setBusy(false); }
  }
  async function doReceive(step, body) {
    setBusy(true);
    try {
      await axios.post(`${API}/makloon-orders/${mkoId}/receive`, { step_seq: step.seq, ...body });
      setReceiveStep(null); await load();
    } catch (e) { throw new Error(e.response?.data?.detail || "Gagal terima hasil makloon."); }   // 23 Okt — tampil di modal
    finally { setBusy(false); }
  }
  /**
   * FASE T — selesaikan langkah JASA MURNI (mis. pembuatan kasa/screen).
   * Tidak ada roll yang lahir dan qty kain tidak berubah; yang lahir hanya tagihan
   * mitra + jurnal WIP. Sengaja aksi TERPISAH dari "Terima Hasil": memakai satu tombol
   * untuk dua arti akan mengundang petugas mengisi "hasil" untuk pekerjaan yang tidak
   * menghasilkan kain.
   */
  async function doRecordService(step, body) {
    setBusy(true);
    try {
      await recordService(mkoId, { step_seq: step.seq, ...body });
      setServiceStep(null); await load();
    }   // galat diteruskan ke modal jasa (ditampilkan di dalamnya)
    finally { setBusy(false); }
  }
  async function doCancel(reason) {
    setBusy(true);
    // G4-15 — alasan dari pengguna (dulu teks tetap "Dibatalkan dari detail").
    try { await axios.post(`${API}/makloon-orders/${mkoId}/cancel`, { reason }); setShowCancel(false); await load(); }
    catch (e) { onError?.(e.response?.data?.detail || "Gagal membatalkan order."); setShowCancel(false); }
    finally { setBusy(false); }
  }

  if (loading && !data) return <div className="section-card py-12 text-center text-[12px] text-[#6B6B73]" data-testid="mko-detail-loading">Memuat pesanan…</div>;
  if (!data) return null;
  const st = MKO_STATUS[data.status] || MKO_STATUS.draft;
  const c = data.costing || {};
  const canCancel = canManage && !["completed", "cancelled"].includes(data.status) && !(data.steps || []).some((s) => s.status === "received");

  return (
    <div data-testid="mko-detail-panel" className="view-container">
      <DetailHeader onBack={onBack} backLabel="Kembali ke Daftar Order Makloon" backTestId="mko-detail-back"
        icon={Boxes} title={data.mko_number} titleTestId="mko-detail-number"
        badges={<>
          <span className={`status-pill ${st.cls}`} data-testid="mko-detail-status">{st.label}</span>
          <span className="feature-badge">{data.mode === "buy_process" ? "Beli + Proses" : "Proses Saja"}</span>
          {data.po_number && <span className="feature-badge badge-blue">PO {data.po_number}</span>}
        </>}
        subtitle={<span className="inline-flex flex-wrap items-center gap-1.5">{data.material_name} <ArrowRight size={11} /> <strong>{data.final_output_name || "—"}</strong> · {formatQty(data.material_qty)} {data.material_unit}</span>}
        actions={<>
          <AskKnButton type="makloon_order" id={data.id} label={data.mko_number} />
          {canCancel && <button data-testid="mko-cancel-button" onClick={() => setShowCancel(true)} className="secondary-button !border-[#F1CFCB] !text-[#C0392B]"><XCircle size={13} /> Batalkan Pesanan</button>}
        </>} />

      {/* G4-15 — SPK order batal: tanpa Tanda Tangan & Kirim WA (pratinjau/unduh tetap untuk arsip).
          Kirim WA disembunyikan lewat kelas karena DocumentActionsBar belum punya prop untuk itu
          (diminta ke pemilik komponen dokumen — lihat laporan G4). */}
      <DocumentActionsBar docType="makloon_spk" sourceId={data.id} entityId={data.entity_id}
        number={data.mko_number} label="SPK Makloon" esignable={orderLive} currentUser={currentUser} onChanged={load}
        className={`rounded-lg border border-[#EDEEF1] bg-[#FAFBFC] px-2.5 py-2 ${orderLive ? "" : "[&_[data-testid=doc-act-wa]]:hidden"}`} />
      {!orderLive && (
        <p className="text-[11px] text-[#6B6B73]" data-testid="mko-cancelled-note">
          Order ini dibatalkan{data.cancel_reason ? `: ${data.cancel_reason}` : ""} — SPK tidak bisa ditandatangani atau dikirim.
        </p>
      )}

      {/* FASE T (keputusan 3b) — peringatan yang tidak memblokir TETAP terlihat di sini.
          Peringatan itu tersimpan di dokumen saat SPK lahir; kalau hanya muncul sebagai
          toast di layar pembuatnya, petugas yang MENGERJAKAN SPK tak pernah melihatnya. */}
      {(data.warnings || []).length > 0 && (
        <div className="rounded-lg border border-[#F5D9A8] bg-[#FFF8EC] px-3 py-2"
          data-testid="mko-detail-warnings">
          <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase text-[#8C4A00]">
            <TriangleAlert size={12} /> Perhatian pada SPK ini
          </p>
          <ul className="mt-1 space-y-1 text-[11.5px] text-[#8C4A00]">
            {data.warnings.map((w, i) => (
              <li key={`ow${i}`} data-testid={`mko-detail-warning-${i}`}>• {w}</li>
            ))}
          </ul>
        </div>
      )}
      <MakloonMaterialLedger mkoId={data.id} version={data.updated_at} />
      {/* T7 — hasil kurang dari estimasi: SPK "Sebagian" sampai klaim selisih diputus. */}
      {data.completion_hold?.message && (
        <div className="rounded-lg border border-[#F3C6BF] bg-[#FDECEA] px-3 py-2"
          data-testid="mko-completion-hold">
          <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase text-[#A8221A]">
            <TriangleAlert size={12} /> SPK belum bisa selesai — klaim selisih menunggu keputusan
          </p>
          <p className="mt-1 text-[11.5px] text-[#A8221A]">{data.completion_hold.message}</p>
        </div>
      )}


      <div className="grid grid-cols-1 items-start gap-3 lg:grid-cols-[300px_1fr]">
        {/* Ringkasan & Costing */}
        <div className="space-y-3">
          <Panel icon={Wallet} title="Costing (HPP)">
            <div className="grid grid-cols-2 gap-2" data-testid="mko-costing">
              <Cell label="Biaya bahan">{formatCurrency(c.material_cost || 0)}</Cell>
              <Cell label="Ongkos jasa">{formatCurrency(c.service_cost || 0)}</Cell>
              <Cell label="Bahan pembantu">{formatCurrency(c.aux_cost || 0)}</Cell>
              <Cell label="HPP output" tone="#0058CC">{formatCurrency(c.hpp_output || 0)}</Cell>
              <Cell label="HPP / unit" tone="#1B7F4B">{formatCurrency(c.hpp_per_unit || 0)}</Cell>
              <Cell label="Est. output">{formatQty(data.forecast?.expected_finished_qty || 0)}</Cell>
            </div>
          </Panel>
          {/* FASE D (PS-04) — HPP BERJENJANG per langkah */}
          {(c.steps || []).length > 0 && (
            <Panel icon={Factory} title="HPP berjenjang">
              <div>
                <table className="w-full text-[11px]" data-testid="mko-tiered-costing">
                  <thead>
                    <tr className="text-left text-[9.5px] uppercase text-[#6B6B73]">
                      <th className="py-1">Lgk</th><th>Proses</th><th className="text-right">Hasil</th><th className="text-right">HPP/unit</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#EFF0F2]">
                    {(c.steps || []).map((cs) => (
                      <tr key={cs.seq} data-testid={`mko-costing-step-${cs.seq}`}>
                        <td className="py-1.5">{cs.seq}</td>
                        <td className="truncate">{cs.process_type}<br /><span className="text-[9.5px] text-[#9A9BA3]">{cs.makloon_name}</span></td>
                        <td className="text-right tabular-nums">{formatQty(cs.actual_output_qty || cs.expected_output_qty || 0)} {cs.output_unit}</td>
                        <td className="text-right tabular-nums font-semibold">{formatCurrency(cs.hpp_per_unit || 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}
          <Panel icon={Clock} title={`Riwayat · ${(data.timeline || []).length}`}>
            <Timeline testId="mko-timeline" items={(data.timeline || []).slice().reverse().map((t) => ({ title: timelineText(t.note || t.event), meta: fmtDT(t.at) }))} />
          </Panel>
          {(data.service_bills || []).length > 0 && (
            <Panel icon={Receipt} title="Tagihan jasa">
              <div className="divide-y divide-[#EFF0F2]" data-testid="mko-service-bills">
                {data.service_bills.map((b) => (
                  <div key={b.id} className="flex items-center justify-between py-1.5 text-[11.5px]">
                    <div><p className="font-semibold">{b.bill_number}</p><p className="text-[10px] text-[#6B6B73]">{b.supplier_name} · step {b.step_seq}</p></div>
                    <span className="tabular-nums font-semibold">{formatCurrency(b.grand_total || 0)}</span>
                  </div>
                ))}
              </div>
            </Panel>
          )}
        </div>

        {/* Steps */}
        <Panel icon={Factory} title={`Langkah proses · ${(data.steps || []).length}`} className="self-start">
          <div className="space-y-2.5">
            {(data.steps || []).map((s, idx) => {
              const ss = stepStatusMeta(s);
              const prevReceived = idx === 0 || (data.steps[idx - 1]?.status === "received");
              // FASE T — aliran kain menentukan AKSI: `service_only` diselesaikan lewat
              // "Catat Jasa" (kain tidak keluar gudang), sisanya lewat Issue → Terima.
              const serviceOnly = s.material_flow === "service_only";
              const noTransform = s.changes_stage === false;
              return (
                <div key={s.seq} data-testid={`mko-step-${s.seq}`} className="rounded-lg border border-[#EFF0F2] p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-[12px] font-semibold flex items-center gap-1.5">
                        <span className="rounded bg-[#EAF2FF] px-1.5 text-[10.5px] font-bold text-[#0058CC]">Langkah {s.seq}</span>
                        {s.stage_label || processLabel(s.process_type)} · {s.makloon_name || "—"}
                      </p>
                      <p className="mt-0.5 text-[10.5px] text-[#6B6B73] flex items-center gap-1">
                        {s.input_name || s.input_sku}
                        {noTransform ? (
                          <span className="text-[#6B219A]">· kain tetap (tidak berubah)</span>
                        ) : (
                          <><ArrowRight size={10} /> {s.output_name || s.output_sku || "—"}</>
                        )}
                      </p>
                    </div>
                    <span className={`status-pill ${ss.cls}`}>{ss.label}</span>
                  </div>
                  {/* FASE T — arti tahap terlihat di kartu: kain berubah? kain dikirim? */}
                  {(s.stage_code || s.material_flow) && (
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[10px]"
                      data-testid={`mko-step-stage-${s.seq}`}>
                      <Layers size={11} className="text-[#6B219A]" />
                      {s.stage_code && (
                        <span className="rounded bg-[#F3E9FA] px-1.5 py-0.5 font-semibold text-[#6B219A]">
                          Tahap {s.stage_code}
                        </span>
                      )}
                      <span className={`rounded px-1.5 py-0.5 font-semibold ${
                        noTransform ? "bg-[#F3E9FA] text-[#6B219A]" : "bg-[#EAF2FF] text-[#0058CC]"}`}
                        data-testid={`mko-step-transform-${s.seq}`}>
                        {noTransform ? "Tidak mengubah kain" : "Mengubah tahap kain"}
                      </span>
                      {s.material_flow && (
                        <span className="rounded bg-[#F3F4F6] px-1.5 py-0.5 font-semibold text-[#3C3C43]"
                          data-testid={`mko-step-flow-${s.seq}`}>
                          {MATERIAL_FLOW_BADGE[s.material_flow] || s.material_flow}
                        </span>
                      )}
                    </div>
                  )}
                  <div className="mt-2 grid grid-cols-3 gap-2 text-[11px]">
                    <MiniStat label="Input" node={<QtyDual rolls={s.qty_rolls} measure={s.input_qty} unit={s.input_unit || ""} compact />} />
                    <MiniStat label={s.status === "received" ? "Output Aktual" : "Est. Output"} node={<QtyDual rolls={s.status === "received" ? s.qty_rolls_out : null} measure={s.status === "received" ? s.actual_output_qty : s.expected_output_qty} unit={s.output_unit || ""} compact />} />
                    <MiniStat label={s.status === "received" ? "Sisa Aktual" : "Est. Sisa"} value={formatQty(s.status === "received" ? s.actual_byproduct_qty : s.expected_byproduct_qty)} />
                  </div>
                  {s.status === "issued" && <p className="mt-1.5 text-[10.5px] text-[#0058CC]">Di makloon: <b>{formatQty(s.subcon_qty)} {s.input_unit}</b> · nilai bahan {formatCurrency(Number(s.material_value || 0) - (s.material_returns || []).reduce((t, r) => t + Number(r.value || 0), 0) - (s.material_losses || []).filter((x) => x.status === "posted").reduce((t, x) => t + Number(x.value || 0), 0))}</p>}
                  {s.status === "received" && (
                    <div className="mt-1.5 text-[10.5px] text-[#6B6B73]">
                      HPP output: <b className="text-[#0058CC]">{formatCurrency(s.output_value)}</b>
                      {s.actual_byproduct_qty > 0 && <> · sisa {formatQty(s.actual_byproduct_qty)} {s.input_unit} (kredit {formatCurrency(s.byproduct_value || 0)})</>}
                      <br />Roll: {(s.lots || []).map((l) => `${l.lot} (${formatQty(l.length)})`).join(", ") || "—"}
                      {s.receive_uom_trail && (
                        <><br />Dokumen mitra: {formatQty(s.receive_uom_trail.doc_qty)} {s.receive_uom_trail.doc_uom} → {formatQty(s.receive_uom_trail.base_qty)} {s.receive_uom_trail.base_uom} (faktor {s.receive_uom_trail.factor})</>
                      )}
                    </div>
                  )}
                  <MakloonPartialReceipts step={s} mkoId={data.id} onChanged={load} />
                  {/* FASE D — dasar perhitungan (kontrak · susut · tarif) terlihat & bisa diaudit */}
                  <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[10px]" data-testid={`mko-step-basis-${s.seq}`}>
                    {s.contract_number && <span className="rounded bg-[#EAF2FF] px-1.5 py-0.5 font-semibold text-[#0058CC]">Kontrak {s.contract_number}</span>}
                    {s.tariff_basis && <span className="rounded bg-[#F3F4F6] px-1.5 py-0.5 font-semibold text-[#3C3C43]">Basis tarif: {s.tariff_basis}</span>}
                    <span className="rounded bg-[#F3F4F6] px-1.5 py-0.5 text-[#3C3C43]">Susut {formatQty(s.shrinkage_pct ?? s.waste_pct ?? 0)}% ({s.shrinkage_source || "—"})</span>
                    <span className="rounded bg-[#F3F4F6] px-1.5 py-0.5 text-[#3C3C43]">Toleransi {formatQty(s.tolerance_pct ?? 0)}%</span>
                    {s.tariff > 0 && <span className="rounded bg-[#E6F4EA] px-1.5 py-0.5 font-semibold text-[#1B7F4B]">Ongkos {formatCurrency(s.tariff)}</span>}
                  </div>
                  {(s.estimate?.explain?.length > 0 || s.tariff_actual?.explain?.length > 0) && (
                    <details className="mt-1.5" data-testid={`mko-step-explain-${s.seq}`}>
                      <summary className="cursor-pointer text-[10.5px] font-semibold text-[#0058CC]">Lihat rumus & angka antara</summary>
                      <ul className="mt-1 space-y-0.5 text-[10.5px] text-[#3C3C43]">
                        {(s.estimate?.explain || []).map((l, i) => <li key={`e${i}`}>• {l}</li>)}
                        {((s.tariff_actual || s.tariff_plan)?.explain || []).map((l, i) => <li key={`t${i}`} className="text-[#1B7F4B]">• {l}</li>)}
                      </ul>
                    </details>
                  )}
                  {s.status === "received" && (
                    <MakloonClaimPanel mkoId={mkoId} step={s} currentUser={currentUser}
                      onDone={load} onError={onError} />
                  )}
                  {canIssue && s.status === "pending" && prevReceived && !serviceOnly && (
                    <button data-testid={`issue-step-${s.seq}`} onClick={() => setIssueStep(s)} className="primary-button mt-2 !py-1.5 text-[11.5px]"><Send size={12} /> Issue ke Makloon</button>
                  )}
                  {/* FASE T — langkah jasa murni: kain TIDAK boleh bergerak, jadi tombolnya
                      "Catat Jasa". Dulu petugas hanya melihat "Issue ke Makloon", menekannya,
                      lalu ditolak 409 tanpa jalan keluar. */}
                  {canReceive && s.status === "pending" && prevReceived && serviceOnly && (
                    <div className="mt-2">
                      <button data-testid={`record-service-step-${s.seq}`} onClick={() => setServiceStep(s)}
                        className="primary-button !py-1.5 text-[11.5px]">
                        <Wrench size={12} /> Catat Jasa
                      </button>
                      <p className="mt-1 text-[10.5px] text-[#6B6B73]">
                        Kain tidak dikeluarkan dari gudang — yang dicatat hanya biaya jasa
                        mitra. Tidak ada roll baru yang lahir.
                      </p>
                    </div>
                  )}
                  {(canIssue || canReceive) && s.status === "pending" && !prevReceived && (
                    <p className="mt-2 text-[10.5px] text-[#9A9BA3]">Menunggu langkah sebelumnya diterima.</p>
                  )}
                  {s.status === "issued" && s.awaiting_return && (
                    <MakloonReturnMaterial mkoId={data.id} step={s} canAct={can(currentUser?.permissions, "makloon_order", "cancel")}
                      canLoss={can(currentUser?.permissions, "makloon_order", "record_loss")}
                      canTol={can(currentUser?.permissions, "supplier_contract", "update")} onDone={load} onError={onError} />
                  )}
                  {s.status === "returned" && (
                    <p className="mt-1.5 text-[10.5px] text-[#6B6B73]" data-testid={`mko-step-returned-${s.seq}`}>Retur {formatQty(s.returned_qty)} {s.input_unit} dicatat {fmtDT(s.returned_at)} — {s.return_reason}</p>
                  )}
                  {(s.material_losses || []).length > 0 && (
                    <MakloonLossList mkoId={data.id} step={s} currentUser={currentUser} onDone={load} onError={onError} />
                  )}
                  {s.status === "returned" && (
                    <MakloonReturnHistory step={s} />
                  )}
                  {canReceive && s.status === "issued" && !s.awaiting_return && (
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      {!isGrn(data.entity_id) && <button data-testid={`receive-step-${s.seq}`} onClick={() => setReceiveStep(s)} className="primary-button !py-1.5 text-[11.5px]"><PackageCheck size={12} /> Terima Hasil</button>}
                      <a data-testid={`receive-step-grn-${s.seq}`} className="secondary-button !py-1.5 text-[11.5px]"
                        href={`?view=goods-receipts&mko=${data.id}&makloon=${s.makloon_id || ""}&wh=${s.from_warehouse_id || data.target_warehouse_id || ""}&entity=${data.entity_id || ""}`}>
                        <PackageCheck size={12} /> Terima lewat Kedatangan (SJ)
                      </a>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </Panel>
      </div>

      {issueStep && <IssueModal step={issueStep} warehouses={warehouses} defaultWh={data.from_warehouse_id} busy={busy}
        onClose={() => setIssueStep(null)} onConfirm={(wh, docUom, docQty) => doIssue(issueStep, wh, docUom, docQty)} />}
      {receiveStep && <ReceiveModal step={receiveStep} warehouses={warehouses} defaultWh={data.target_warehouse_id || data.from_warehouse_id}
        mkoNumber={data.mko_number} busy={busy} onClose={() => setReceiveStep(null)} onConfirm={(body) => doReceive(receiveStep, body)} />}
      {serviceStep && <RecordServiceModal step={serviceStep} mkoNumber={data.mko_number} busy={busy}
        onClose={() => setServiceStep(null)} onConfirm={(body) => doRecordService(serviceStep, body)} />}
      <ConfirmModal open={showCancel} title={`Batalkan ${data.mko_number}?`}
        message="Cadangan bahan yang belum dikirim dilepas. Bahan yang sudah dikirim tetap tercatat di mitra (WIP tetap) sampai retur bahan dicatat."
        confirmLabel="Batalkan Pesanan" danger withReason reasonLabel="Alasan pembatalan" reasonPlaceholder="mis. kebutuhan batal / ganti mitra"
        onConfirm={doCancel} onCancel={() => setShowCancel(false)} testId="mko-cancel-modal" />
    </div>
  );
}

function MiniStat({ label, value, node = null }) {
  // FASE U — `node` dipakai bila nilainya komponen (mis. <QtyDual/> dua satuan);
  // `value` (teks) tetap didukung supaya pemanggil lama tidak berubah.
  return <div><p className="text-[9.5px] font-semibold uppercase text-[#9A9BA3]">{label}</p><p className="text-[11.5px] font-semibold tabular-nums">{node || value}</p></div>;
}
