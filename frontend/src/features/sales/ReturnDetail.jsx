/** Sub-fase 1.11 — Return detail panel with approve/reject/upload.
 *  23 Okt (keluhan pemilik: halaman retur kacau, panel tumpang tindih) — isi dikelompokkan ke TAB: Ringkasan (roll,
 *  langkah aktif: pengembalian barang & QC SPK, lampiran, keluhan, nota kredit) · Logistik & perjalanan · Kebijakan &
 *  keputusan · Stok & rantai · Riwayat. Panel tab non-aktif disembunyikan (bukan dilepas) supaya isian/data tidak
 *  hilang saat berpindah tab. Modal tolak/pembalikan memakai ConfirmModal standar. */
import { can, canSeeGrade } from "../../config/roles";
import { useState, useRef, useEffect } from "react";
import { AskKnButton } from "../../components/AskKnButton";
import axios, { API } from "../../services/apiClient";
import {
  AlertCircle, Check, CheckCircle2, FileText, Loader2,
  Paperclip, Receipt, RotateCcw, Upload, X, XCircle,
} from "lucide-react";
import { ReturnTypeBadge, ReturnStatusPill, OUTCOME_LABEL, fmtDate } from "./ReturnShared";
import { formatCurrency } from "../../utils/formatters";
import ReturnTimeline from "../../components/ReturnTimeline";
import ConfirmModal from "../../components/ConfirmModal";
import { StatusTabs } from "../../components/ListControls";
import ReturnShipmentPanel from "./ReturnShipmentPanel"; // 23 Okt — tahap Pengembalian barang
import ReturnStepper from "./ReturnStepper";           // UI/UX 2026-06 — peta alur + langkah berikutnya
import ReturnSpkPanel from "./ReturnSpkPanel";       // 23 Okt — QC retur lewat SPK per roll (menu Kualitas)
import ReturnSettleModal from "./ReturnSettleModal";
import ReturnRollSettleModal from "./ReturnRollSettleModal";          // UAT 23 Okt — penyelesaian per roll
import ReturnRollSettlementsPanel from "./ReturnRollSettlementsPanel";
import ReturnQuarantinePanel from "./ReturnQuarantinePanel";
import ReturnChainPanel from "./ReturnChainPanel";
import ReturnGradeLossPanel from "./ReturnGradeLossPanel";
import ReturnDispositionPanel from "./ReturnDispositionPanel";
import ReturnJourneyPanel from "./ReturnJourneyPanel";   // FASE I.F — keluhan + milestone
import ReturnTimelinePanel from "./ReturnTimelinePanel"; // L08 LN-081 — satu timeline per jalur
import ReturnEligibilityPanel from "./ReturnEligibilityPanel";
import ReturnExceptionsPanel from "./ReturnExceptionsPanel"; // 2026-06 — jendela retur tampak
import ReturnCompensationPanel from "./ReturnCompensationPanel"; // LN-092 — cutloss & diskon
import ReturnReplacementPanel from "./ReturnReplacementPanel";   // LN-090 — pesanan pengganti
import ReturnLogisticsPanel from "./ReturnLogisticsPanel";       // LN-091 KLR-11 — penanggung ongkir
import DocumentActionsBar from "../documents/DocumentActionsBar";
import { DetailHeader, Panel, Cell } from "../../components/DetailParts";
import ReturnRollsPanel from "./ReturnRollsPanel";   // 23 Okt — detail & keputusan PER ROLL

const TERMINAL = ["refund_settled", "credit_settled", "nego_settled", "settled", "rejected", "cancelled"];

export default function ReturnDetail({
  ret, token, canApprove, currentUser,
  onApprove, onReject, onSubmit, onCancelDraft, onSettle, onReverse, onBack, onOpenDocument,
  onAttachmentUploaded, notice, onClearNotice, onNavigate, onReturnChanged,
  error = null, onClearError, busyAction = "",
}) {
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [showSettleModal, setShowSettleModal] = useState(false);
  const [showReverseModal, setShowReverseModal] = useState(false);
  const [reverseErr, setReverseErr]           = useState("");
  const [tab, setTab]                         = useState("ringkasan");
  const [uploading, setUploading]             = useState(false);
  const [localError, setLocalError]           = useState(null);
  const [rejectErr, setRejectErr]             = useState("");
  const [creditNote, setCreditNote]           = useState(null);
  // UI/UX 2026-06 — versi detail dari server membawa NILAI per item
  // (`unit_price_est`/`line_total_est` dari harga SO) + `estimated_value`.
  const [enriched, setEnriched]               = useState(null);
  const fileRef = useRef(null);
  const isTerminal = TERMINAL.includes(ret.status);
  // FE-04 — dulu hanya status (semua pengguna melihat Tolak); POST /reject → sales_return.reject.
  const canReject = ["pending_approval", "approved", "inspecting", "inspected"].includes(ret.status)
    && can(currentUser?.permissions, "sales_return", "reject");
  const isSettled = ["refund_settled", "credit_settled", "nego_settled", "settled"].includes(ret.status);
  // UAT 23 Okt — penyelesaian PER ROLL bila semua baris menunjuk roll klaim (retur lama tanpa roll = per barang).
  const rollMode = (ret.items || []).length > 0 && (ret.items || []).every((it) => (it.roll_ids || []).length > 0);
  const claimRolls = (ret.items || []).reduce((a, it) => a + (it.roll_ids || []).length, 0);
  const settledRolls = Object.keys(ret.roll_outcomes || {}).length;
  // F-11-layar (keputusan pemilik 2026-10-21) — Gudang/QC membuka retur lewat `wms.scan`/`qc.inspect`
  // tanpa `sales_return.view`: server membuang field uang; layar menyembunyikan panel uang/keputusan
  // dan tiap tombol mengikuti izin endpoint-nya (FE-04).
  const perms = currentUser?.permissions;
  const fullView = can(perms, "sales_return", "view");
  const canUpdate = can(perms, "sales_return", "update");
  const canScan = canUpdate || can(perms, "wms", "scan");
  const canInspect = canUpdate || can(perms, "qc", "inspect");

  // F3 — ambil detail Nota Kredit bila retur sudah menghasilkan credit note.
  useEffect(() => {
    let active = true;
    async function loadEnriched() {
      try {
        const res = await axios.get(`${API}/sales-returns/${ret.id}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (active) setEnriched(res.data);
      } catch (_) { /* estimasi nilai opsional — layar tetap terbaca */ }
    }
    loadEnriched();
    return () => { active = false; };
  }, [ret?.id, ret?.status, ret?.updated_at, token]);   // keputusan roll mengubah qty & estimasi

  useEffect(() => {
    let active = true;
    async function loadCN() {
      if (!fullView || (!ret?.credit_note_id && !ret?.credit_note_number)) { setCreditNote(null); return; }
      try {
        const res = await axios.get(`${API}/credit-notes`, {
          headers: { Authorization: `Bearer ${token}` },
          params: { return_id: ret.id },
        });
        const items = res.data?.items || [];
        if (active) setCreditNote(items[0] || null);
      } catch (_) { /* best-effort: chip ringkas tetap tampil dari field ret */ }
    }
    loadCN();
    return () => { active = false; };
  }, [ret?.id, ret?.credit_note_id, ret?.credit_note_number, token, fullView]);

  async function uploadFile(file) {
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await axios.post(
        `${API}/sales-returns/${ret.id}/attachments`,
        fd,
        { headers: { Authorization: `Bearer ${token}`, "Content-Type": "multipart/form-data" } }
      );
      const updated = await axios.get(`${API}/sales-returns/${ret.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      onAttachmentUploaded(updated.data);
    } catch (e) {
      setLocalError("Upload gagal: " + (e.response?.data?.detail || e.message));
    } finally { setUploading(false); }
  }

  const attachments = (ret.attachments || []).filter(a => !a.is_deleted);

  // R2 — refresh dokumen retur (dipakai setelah release/scrap roll karantina).
  async function refetchReturn() {
    try {
      const updated = await axios.get(`${API}/sales-returns/${ret.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      onAttachmentUploaded(updated.data);
    } catch (_) { /* best-effort */ }
  }

  // R5.4 — reversal/koreksi retur yang sudah settled (galat tampil DI DALAM dialog; dialog tetap terbuka).
  async function submitReverse(reason) {
    setReverseErr("");
    try {
      await onReverse(ret, reason);
      setShowReverseModal(false);
    } catch (e) {
      setReverseErr("Gagal pembalikan: " + (e.response?.data?.detail || e.message));
    }
  }
  const detailRet = enriched?.items?.length ? { ...ret, items: enriched.items } : ret;   // + nomor roll & SKU
  const showShipment = ["approved", "inspecting"].includes(ret.status) || !!ret.return_shipment;
  const TABS = [
    { key: "ringkasan", label: "Ringkasan" },
    { key: "logistik", label: "Logistik & perjalanan" },
    ...(fullView ? [{ key: "keputusan", label: "Kebijakan & keputusan" }, { key: "stok", label: "Stok & rantai" }] : []),
    { key: "riwayat", label: "Riwayat" },
  ];

  return (
    <div data-testid="return-detail-view" className="view-container">

      {notice && (
        <div className="notice-bar success" data-testid="return-notice">
          <CheckCircle2 size={14} /> {notice}
          <button onClick={onClearNotice}><X size={12} /></button>
        </div>
      )}
      {error && (
        <div className="notice-bar danger" data-testid="return-action-error">
          <AlertCircle size={14} /> {error}
          {onClearError && <button onClick={onClearError}><X size={12} /></button>}
        </div>
      )}
      {localError && (
        <div className="notice-bar danger">
          <AlertCircle size={14} /> {localError}
          <button onClick={() => setLocalError(null)}><X size={12} /></button>
        </div>
      )}

      <DetailHeader onBack={onBack} backLabel="Kembali ke Daftar Retur" backTestId="return-back-btn"
        icon={RotateCcw} title={ret.number} titleTestId="return-number"
        badges={<><ReturnTypeBadge type={ret.return_type} /><ReturnStatusPill status={ret.status} /></>}
        subtitle={<>
          Pesanan: <strong>{ret.order_number}</strong>
          {ret.customer_name && <> · Pelanggan: <strong>{ret.customer_name}</strong></>}
          {" "}· Dibuat: {fmtDate(ret.created_at)} oleh {ret.created_by || "-"}
        </>}
        actions={<>
          {fullView && <AskKnButton type="sales_return" id={ret.id} label={ret.number} />}
          {ret.status === "draft" && (
            <button data-testid="submit-return-btn" className="secondary-button" disabled={!!busyAction} onClick={() => onSubmit(ret)}>
              <FileText size={13} /> Kirim untuk Persetujuan
            </button>
          )}
          {ret.status === "draft" && onCancelDraft && (
            <button data-testid="cancel-draft-return-btn" className="secondary-button" disabled={!!busyAction} onClick={() => onCancelDraft(ret)}>
              <XCircle size={13} /> Buang Draf
            </button>
          )}
          {ret.status === "pending_approval" && canApprove && (
            <button data-testid="approve-return-btn" className="primary-button" disabled={!!busyAction} onClick={() => onApprove(ret)}>
              <Check size={13} /> Setujui (Manager)
            </button>
          )}
          {ret.status === "inspected" && canApprove && (
            <button data-testid="open-settle-btn" className="primary-button" disabled={!!busyAction} onClick={() => setShowSettleModal(true)}>
              <Receipt size={13} /> {rollMode && settledRolls ? `Selesaikan roll berikutnya (${settledRolls}/${claimRolls} sudah)` : "Selesaikan (Pilih Outcome)"}
            </button>
          )}
          {canReject && (
            <button data-testid="reject-return-btn" className="danger-button" disabled={!!busyAction} onClick={() => { setRejectErr(""); setShowRejectModal(true); }}>
              <X size={13} /> Tolak
            </button>
          )}
          {ret.status === "approved" && (
            <div className="info-chip success">
              <CheckCircle2 size={13} /> Disetujui oleh {ret.approved_by} · {fmtDate(ret.approved_at)}
            </div>
          )}
          {["refund_settled", "credit_settled", "nego_settled", "settled"].includes(ret.status) && (
            <div className="info-chip success" data-testid="return-outcome-chip">
              <CheckCircle2 size={13} /> Selesai{ret.outcome ? `: ${OUTCOME_LABEL[ret.outcome] || ret.outcome}` : ""}
              {ret.settled_by ? ` · oleh ${ret.settled_by}` : ""}
            </div>
          )}
          {isSettled && canApprove && (
            <button data-testid="reverse-return-btn" className="danger-button" onClick={() => { setReverseErr(""); setShowReverseModal(true); }}>
              <RotateCcw size={13} /> Batal / Pembalikan
            </button>
          )}
          {ret.credit_note_number && (
            <div className="info-chip success" data-testid="return-credit-note-chip">
              <Receipt size={13} /> Nota Kredit: {ret.credit_note_number}
            </div>
          )}
          {ret.status === "rejected" && (
            <div className="info-chip danger">
              <XCircle size={13} /> Ditolak oleh {ret.rejected_by} · Alasan: {ret.reject_reason}
            </div>
          )}
          {ret.status === "cancelled" && !ret.reversed && (
            <div className="info-chip danger" data-testid="return-draft-discarded-chip">
              <XCircle size={13} /> Draf dibuang{ret.cancelled_by ? ` oleh ${ret.cancelled_by}` : ""}
            </div>
          )}
          {ret.status === "cancelled" && ret.reversed && (
            <div className="info-chip danger" data-testid="return-reversed-chip">
              <RotateCcw size={13} /> Dibatalkan (Pembalikan){ret.reversed_by ? ` oleh ${ret.reversed_by}` : ""}
              {ret.reversal_reason ? ` · ${ret.reversal_reason}` : ""}
            </div>
          )}
        </>} />

      {fullView && (
        <DocumentActionsBar docType="sales_return" sourceId={ret.id} entityId={ret.entity_id}
          number={ret.number} label="Nota Retur Jual" esignable={false} currentUser={currentUser}
          className="mb-3 rounded-lg border border-[#EDEEF1] bg-[#FAFBFC] px-2.5 py-2" />
      )}

      {/* UI/UX 2026-06 — SEDANG DI MANA dokumen ini & APA langkah berikutnya (23 Okt: 5 langkah, dibaca dari data). */}
      <ReturnStepper ret={detailRet} draftDiscarded={ret.status === "cancelled" && !ret.reversed} />
      <EvidenceBanner ev={enriched?.evidence} hasFiles={attachments.length > 0} />

      <StatusTabs tabs={TABS} value={tab} onChange={setTab} testIdPrefix="return-tab" />

      {/* ── RINGKASAN: roll yang diretur + langkah yang sedang berjalan ── */}
      <div hidden={tab !== "ringkasan"} className="mt-3 space-y-3" data-testid="return-tabpanel-ringkasan">
        {showShipment && <ReturnShipmentPanel ret={detailRet} canEdit={canScan && !isTerminal} onChanged={refetchReturn} />}

        {/* R2 — QC retur lewat SPK per roll: layar ini menugaskan & melihat; pemeriksaan diisi di menu Kualitas. */}
        {canSeeGrade(currentUser) && (canInspect || fullView) && <ReturnSpkPanel ret={ret} currentUser={currentUser} onOpenDocument={onOpenDocument} onChanged={refetchReturn} />}

        <div className="grid items-start gap-3 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <div className="space-y-2">
            <ReturnRollsPanel ret={ret} items={detailRet.items || []} fullView={fullView}
              estimatedValue={enriched?.estimated_value}
              canDecide={["draft", "pending_approval"].includes(ret.status) && can(perms, "sales_return", "decide_rolls")}
              onChanged={refetchReturn} />
            {ret.notes && <div className="section-notes"><strong>Catatan:</strong> {ret.notes}</div>}
          </div>

          <Panel icon={Paperclip} title="Lampiran bukti" testId="return-attachments-panel"
            right={canUpdate && !isTerminal && (
              <button data-testid="upload-attachment-btn" className="link-button"
                onClick={() => fileRef.current?.click()} disabled={uploading}>
                {uploading ? <Loader2 size={12} className="spin" /> : <Upload size={12} />} Unggah
              </button>
            )}>
            <input ref={fileRef} type="file" accept="image/*,.pdf" style={{ display: "none" }}
              data-testid="attachment-file-input"
              onChange={e => { if (e.target.files[0]) uploadFile(e.target.files[0]); e.target.value = ""; }} />
            {attachments.length === 0 ? (
              <div className="empty-state small">
                <Paperclip size={18} style={{ opacity: 0.3 }} />
                <p>Belum ada lampiran.</p>
                {canUpdate && !isTerminal && (
                  <button className="link-button" onClick={() => fileRef.current?.click()}>+ Unggah foto / dokumen</button>
                )}
              </div>
            ) : (
              <div className="attachments-grid">
                {attachments.map(att => (
                  <div key={att.id} className="attachment-chip" data-testid={`attachment-${att.id}`}>
                    <Paperclip size={11} />
                    {/* Keputusan owner 2026-10-21 — Gudang/QC boleh mengunduh FOTO/VIDEO bukti keluhan (server: sama). */}
                    {fullView || /^(image|video)\//.test(att.content_type || "") ? (
                      <a href={`${API}/sales-returns/${ret.id}/attachments/${att.id}/download`}
                        target="_blank" rel="noreferrer" className="link-button">{att.filename}</a>
                    ) : <span>{att.filename}</span>}
                    {att.roll_id && <span className="text-[10.5px] text-[#6B6B73]">· roll {(detailRet.items || []).map((it) => (it.roll_nos || {})[att.roll_id]).find(Boolean) || ""}</span>}
                    <span className="text-muted text-xs tabular-nums">{(att.size / 1024).toFixed(0)} KB</span>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>

        {/* FASE I.F — sebab keluhan (master) + pengiriman pengganti (jalur keluar). */}
        <ReturnJourneyPanel ret={ret} canEdit={canUpdate && ret.status !== "cancelled" && (!isTerminal || canApprove)}
          onChanged={(fresh) => onReturnChanged?.(fresh)} />

        {/* F3 — Nota Kredit (Credit Note) hasil retur yang sudah di-approve */}
        {fullView && (creditNote || ret.credit_note_number) && (
          <Panel icon={Receipt} title="Nota kredit" testId="return-credit-note-section">
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              <Cell label="Nomor CN"><span className="font-mono" data-testid="credit-note-number">{creditNote?.number || ret.credit_note_number}</span></Cell>
              <Cell label="Nilai bruto" tone="#0058CC"><span className="tabular-nums" data-testid="credit-note-gross">{formatCurrency(creditNote?.gross_amount ?? ret.credit_note_amount)}</span></Cell>
              <Cell label="DPP / PPN"><span className="tabular-nums">{formatCurrency(creditNote?.net_amount)} / {formatCurrency(creditNote?.ppn_amount)}</span></Cell>
              <Cell label="Penyelesaian">
                <span className={`feature-badge ${creditNote?.settlement === "cash" ? "badge-green" : "badge-blue"}`}>
                  {{ cash: "Refund Tunai", ar: "Pengurang Piutang", store_credit: "Store Credit", nego: "Diskon Nego" }[creditNote?.settlement] || "Pengurang Piutang"}
                </span>
              </Cell>
            </div>
            {creditNote?.cogs_amount > 0 && (
              <div className="section-notes tabular-nums" data-testid="credit-note-cogs">
                Pembalikan HPP (barang kembali ke stok): {formatCurrency(creditNote.cogs_amount)}
              </div>
            )}
            <div className="section-notes text-muted">
              Posting GL otomatis: Dr Pendapatan{creditNote?.ppn_amount > 0 ? " + Dr PPN Keluaran" : ""} / Cr {creditNote?.settlement === "cash" ? "Kas" : "Piutang"}
              {creditNote?.cogs_amount > 0 ? " · Dr Persediaan / Cr HPP" : ""}.
            </div>
          </Panel>
        )}
      </div>

      {/* ── LOGISTIK & PERJALANAN: biaya kirim, scan per roll antar-gudang ── */}
      <div hidden={tab !== "logistik"} className="mt-3 space-y-3" data-testid="return-tabpanel-logistik">
        {fullView && <ReturnLogisticsPanel key={`${ret.id}-${ret.status}`} ret={ret} onChanged={refetchReturn} />}
        <ReturnTimelinePanel ret={ret} canEdit={canScan && !isTerminal} onChanged={refetchReturn} />
      </div>

      {/* ── KEBIJAKAN & KEPUTUSAN: kelayakan, pengecualian, kompensasi, pengganti, disposisi ── */}
      {fullView && (
        <div hidden={tab !== "keputusan"} className="mt-3 space-y-3" data-testid="return-tabpanel-keputusan">
          <ReturnEligibilityPanel ret={ret} />
          <ReturnExceptionsPanel ret={ret} canApprove={canApprove} onChanged={refetchReturn} />
          <ReturnRollSettlementsPanel ret={ret} canApprove={canApprove} canShip={canApprove || canScan} onChanged={refetchReturn} />
          <ReturnCompensationPanel ret={ret} canApprove={canApprove} onChanged={refetchReturn} />
          <ReturnReplacementPanel ret={ret} onChanged={refetchReturn} onNavigate={onNavigate} />
          <ReturnDispositionPanel ret={ret} canApprove={canApprove} onChanged={refetchReturn} />
        </div>
      )}

      {/* ── STOK & RANTAI: karantina, susut grade, rantai retur pelanggan → antar-PT → supplier ── */}
      {fullView && (
        <div hidden={tab !== "stok"} className="mt-3 space-y-3" data-testid="return-tabpanel-stok">
          <ReturnQuarantinePanel ret={ret} canApprove={canApprove} onReleased={refetchReturn} onNavigate={onNavigate} />
          {canSeeGrade(currentUser) && <ReturnGradeLossPanel ret={ret} />}
          <ReturnChainPanel docId={ret.id} />
        </div>
      )}

      {/* ── RIWAYAT ── */}
      <div hidden={tab !== "riwayat"} className="mt-3" data-testid="return-tabpanel-riwayat">
        <ReturnTimeline ret={ret} variant="sales" />
      </div>

      {rollMode ? (
        <ReturnRollSettleModal ret={ret} open={showSettleModal} onClose={() => setShowSettleModal(false)} onDone={refetchReturn} />
      ) : (
        <ReturnSettleModal ret={ret} open={showSettleModal}
          onClose={() => setShowSettleModal(false)} onSettle={onSettle} />
      )}

      <ConfirmModal
        open={showRejectModal}
        title={`Tolak retur ${ret.number}?`}
        message="Retur ditolak seluruhnya. Untuk menolak sebagian, pakai Terima/Tolak per roll sebelum ACC."
        confirmLabel="Tolak Retur" danger withReason reasonMinLength={5}
        reasonLabel="Alasan penolakan" reasonPlaceholder="Alasan penolakan…"
        error={rejectErr}
        onConfirm={async (reason) => {
          const err = await onReject(ret, reason);
          if (err) { setRejectErr(err); return; }   // FE-07 — gagal: dialog & alasan tetap
          setShowRejectModal(false);
        }}
        onCancel={() => setShowRejectModal(false)}
        testId="reject-modal" />

      <ConfirmModal
        open={showReverseModal}
        title={`Batal / Pembalikan retur ${ret.number}?`}
        message={"Membalik jurnal (GL), menghapus roll retur yang masuk stok, membatalkan refund kas & store credit, serta "
          + "membatalkan Nota Kredit. Riwayat tetap tersimpan. Ditolak bila roll retur sudah dilepas dari karantina, sudah "
          + "dipesan/terpakai, atau saldo store credit sudah dipakai."}
        confirmLabel="Lakukan Pembalikan" danger withReason reasonMinLength={5}
        reasonLabel="Alasan pembatalan / koreksi" reasonPlaceholder="Alasan pembatalan / koreksi…"
        error={reverseErr}
        onConfirm={submitReverse}
        onCancel={() => { setShowReverseModal(false); setReverseErr(""); }}
        testId="reverse-modal" />
    </div>
  );
}

const EVIDENCE_STAGE_LABEL = { submit: "diajukan", approve: "disetujui", inspect: "inspeksi diselesaikan", settle: "diselesaikan" };

/** L08 LN-080-T03 — tahap yang menunggu bukti foto menurut kebijakan badan usaha. */
function EvidenceBanner({ ev, hasFiles }) {
  const missing = hasFiles ? [] : (ev?.missing_for || []);
  if (!missing.length) return null;
  return (
    <div className="notice-bar warning mb-3" data-testid="return-evidence-missing">
      <AlertCircle size={14} />
      Bukti foto wajib sebelum retur {missing.map((s) => EVIDENCE_STAGE_LABEL[s] || s).join(" / ")}.
      Unggah minimal satu foto di panel Lampiran bukti.
    </div>
  );
}
