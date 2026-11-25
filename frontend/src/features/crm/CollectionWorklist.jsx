import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { Receipt, AlertTriangle, PhoneCall, BellRing, BellOff, CheckCircle2, Wallet } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import FormModal from "../../components/FormModal";
import { apiErrorText } from "../../utils/apiError";
import { can } from "../../config/roles";
import { KpiTile, fmtDate } from "./crmUtils";
import ReceivePaymentModal from "../finance/payments/ReceivePaymentModal";   // MN-T3 — satu form terima pembayaran
import { CustomerCardLink } from "../finance/cards/partyCards";
import DocLink from "../documents/preview/DocLink";   // Meja gelombang 2 — nomor pesanan membuka rincian barang
import ARReceiptsHistory from "./ARReceiptsHistory";
import FocusNotice from "../../components/FocusNotice";
import useFocusDoc from "../../hooks/useFocusDoc";
import { markReminded } from "./collectionMark";   // satu jalur tandai-diingatkan (juga Meja Keuangan & HP)
import { PromiseFields, promiseError } from "./promiseUi";   // CR-T5 — janji bayar wajib bertanggal & bernominal

/** Collection worklist + reminder (KN_17 §7 / owner 4b). */
export default function CollectionWorklist({ currentUser, selectedEntity, focusDoc, onClearFocus }) {
  // FASE E-8 (E8.2) — mencatat UANG MASUK adalah wewenang peran `finance`. Dulu
  // tombolnya muncul untuk siapa pun yang bisa membuka worklist (termasuk sales),
  // lalu server menolak 403 di dalam modal — penolakan yang tak pernah dilihat
  // pengguna sebagai "bukan tugas saya", melainkan sebagai "sistemnya rusak".
  const canTakeMoney = can(currentUser?.permissions || {}, "ar_receipt", "create");
  // Pelatihan 18 Nov (V9) — "Tandai sudah diingatkan" & "Catat tindak lanjut" (termasuk janji bayar) disimpan server
  // dengan izin `order.update` (routers/crm.py). Dulu kedua ikon tampil untuk Finance lalu ditolak 403 saat disimpan.
  const canFollowUp = can(currentUser?.permissions || {}, "order", "update");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [mode, setMode] = useState("reminders"); // reminders (jatuh tempo<=60h) | overdue
  const [fu, setFu] = useState(null);
  const [marking, setMarking] = useState("");
  const [payRow, setPayRow] = useState(null);
  const [receiptRefresh, setReceiptRefresh] = useState(0);
  // PK-44 (IA-04) — tautan kwitansi (Jejak / Dokumen Terkait): riwayat kwitansi mencari nomornya + menyorot barisnya.
  const [receiptFocus, setReceiptFocus] = useState(null);
  const fokus = useFocusDoc(focusDoc, "ar_receipt", async (id, fd) => {
    const r = await axios.get(`${API}/ar-receipts/${id}`);
    setReceiptFocus({ id, number: r.data?.number || fd.number || "", nonce: fd.nonce || Date.now() });
  }, onClearFocus);

  useEffect(() => { load(); }, [selectedEntity]); // eslint-disable-line

  async function load() {
    setLoading(true);
    try {
      const params = { days_ahead: 60 };
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      const r = await axios.get(`${API}/collection-reminders`, { params });
      setRows(Array.isArray(r.data) ? r.data : []);
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat reminder penagihan.");
    } finally { setLoading(false); }
  }

  async function mark(row) {
    setMarking(row.order_id);
    try {
      await markReminded(row);
      setNotice(`${row.customer_name} ditandai sudah diingatkan.`);
      load();
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal menandai reminder.");
    } finally { setMarking(""); }
  }

  const view = useMemo(() => (mode === "overdue" ? rows.filter((r) => r.overdue) : rows), [rows, mode]);
  const totals = useMemo(() => ({
    outstanding: rows.reduce((s, r) => s + Number(r.outstanding || 0), 0),
    overdue: rows.filter((r) => r.overdue).reduce((s, r) => s + Number(r.outstanding || 0), 0),
    needReminder: rows.filter((r) => (r.overdue || r.due_soon) && !r.reminded).length,
  }), [rows]);

  return (
    <div data-testid="collection-worklist">
      {notice && <div className="notice-bar success" data-testid="collection-notice"><span>{notice}</span><button onClick={() => setNotice("")}>×</button></div>}
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="collection-error" />
      <FocusNotice {...fokus} testId="collection-focus-notice" />

      <div className="grid grid-cols-3 gap-3 mb-3">
        <KpiTile label="Total Tagihan (AR)" value={formatCurrency(totals.outstanding)} testId="collection-total" />
        <KpiTile label="Jatuh Tempo (Lewat Tempo)" value={formatCurrency(totals.overdue)} tone="text-[#C0392B]" testId="collection-overdue" />
        <KpiTile label="Perlu Diingatkan" value={totals.needReminder} sub={`${rows.length} tagihan aktif`} tone={totals.needReminder > 0 ? "text-[#B45309]" : ""} testId="collection-need-reminder" />
      </div>

      <div className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2"><Receipt size={16} className="text-[#0058CC]" /><h2 data-testid="collection-title">Reminder Penagihan</h2></div>
          <div className="tab-bar">
            <button data-testid="collection-mode-reminders" className={`tab-button ${mode === "reminders" ? "active" : ""}`} onClick={() => setMode("reminders")}>Semua aktif</button>
            <button data-testid="collection-mode-overdue" className={`tab-button ${mode === "overdue" ? "active" : ""}`} onClick={() => setMode("overdue")}>Lewat Jatuh Tempo</button>
          </div>
        </div>
        <div className="section-body">
          <div className="rounded-md border border-[#EFF0F2] overflow-hidden">
            <div className="grid grid-cols-[1.2fr_92px_120px_104px_80px_120px] px-3 py-1.5 bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73] border-b border-[#EFF0F2]">
              <span>Pelanggan</span><span>Pesanan</span><span>Belum Lunas</span><span>Jatuh Tempo</span><span>Telat</span><span>Aksi</span>
            </div>
            {loading ? (
              <div className="py-10 text-center text-[12px] text-[#6B6B73]" data-testid="collection-loading">Memuat...</div>
            ) : view.length === 0 ? (
              <div className="py-12 text-center text-[12px] text-[#6B6B73]" data-testid="collection-empty">Tidak ada tagihan {mode === "overdue" ? "overdue" : "aktif"}. 🎉</div>
            ) : (
              <div className="divide-y divide-[#EFF0F2] max-h-[540px] overflow-y-auto">
                {view.map((r) => (
                  <div key={r.order_id} data-testid={`collection-row-${r.order_id}`} className="grid grid-cols-[1.2fr_92px_120px_104px_80px_120px] items-center px-3 py-2.5 text-[11.5px]">
                    <div className="min-w-0">
                      <p className="font-semibold truncate"><CustomerCardLink id={r.customer_id} name={r.customer_name}
                        perms={currentUser?.permissions} testId={`collection-card-${r.order_id}`} /></p>
                      <p className="text-[10px] text-[#6B6B73]">{r.sales_name}{r.reminded && <span className="ml-1 text-[#1E8E5A]">· diingatkan</span>}</p>
                    </div>
                    <span className="min-w-0 break-words font-semibold">
                      <DocLink docType="sales_order" docId={r.order_id} number={r.order_number} entityId={r.entity_id}
                        perms={currentUser?.permissions} testId={`collection-order-${r.order_id}`} />
                    </span>
                    <span className="tabular-nums font-semibold">{formatCurrency(r.outstanding)}</span>
                    <span className="text-[#6B6B73]">{fmtDate(r.due_date)}</span>
                    <span>{r.overdue ? (
                      <span className="status-pill pill-danger inline-flex items-center gap-1"><AlertTriangle size={10} /> {r.days_late}h</span>
                    ) : <span className="status-pill pill-muted">{Math.abs(r.days_late)}h lagi</span>}</span>
                    <div className="flex gap-1">
                      {r.reminded ? (
                        <span className="icon-button text-[#1E8E5A]" title="Sudah diingatkan" data-testid={`collection-reminded-${r.order_id}`}><CheckCircle2 size={15} /></span>
                      ) : canFollowUp && (
                        <button data-testid={`collection-mark-${r.order_id}`} disabled={marking === r.order_id}
                          onClick={() => mark(r)} className="icon-button text-[#B45309]" title="Tandai sudah diingatkan">
                          {marking === r.order_id ? <BellOff size={15} /> : <BellRing size={15} />}
                        </button>
                      )}
                      {canTakeMoney && (
                        <button data-testid={`collection-pay-${r.order_id}`} onClick={() => setPayRow(r)} className="icon-button text-[#1B7F4B]" title="Terima pembayaran" aria-label="Terima pembayaran"><Wallet size={14} /></button>
                      )}
                      {canFollowUp && (
                        <button data-testid={`collection-followup-${r.order_id}`} onClick={() => setFu(r)} className="icon-button text-[#0058CC]" title="Catat tindak lanjut" aria-label="Catat tindak lanjut"><PhoneCall size={14} /></button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <p className="text-[10.5px] text-[#9A9BA3] mt-2">Menampilkan tagihan lewat tempo + akan jatuh tempo ≤ 60 hari. Pengingat bersifat sesuai permintaan (tanpa kirim ke luar).</p>
        </div>
      </div>

      <ARReceiptsHistory refreshKey={receiptRefresh} selectedEntity={selectedEntity} currentUser={currentUser} focus={receiptFocus}
        onChanged={(m) => { setNotice(m); setReceiptRefresh((k) => k + 1); load(); }} />

      {payRow && <ReceivePaymentModal customerId={payRow.customer_id} customerName={payRow.customer_name}
        preselectOrderId={payRow.order_id} onClose={() => setPayRow(null)}
        onDone={(m) => { setPayRow(null); setNotice(m); setReceiptRefresh((k) => k + 1); load(); }} />}

      {fu && <WorklistFollowup row={fu} onClose={() => setFu(null)}
        onDone={(m) => { setFu(null); setNotice(m); load(); }} />}
    </div>
  );
}

// PK-42 (UX-09) — pop-up baku `FormModal` (dulu `modal-overlay` buatan sendiri): galat (catatan kosong, server menolak)
// tampil DI DALAM pop-up yang sedang dibuka, bukan di halaman di belakangnya; Esc/klik latar seragam.
const FOLLOWUP_OUTCOMES = [{ value: "contacted", label: "Dihubungi" }, { value: "promised", label: "Dijanjikan bayar" },
  { value: "paid", label: "Sudah bayar" }, { value: "no_response", label: "Tak respon" }, { value: "escalated", label: "Eskalasi" }];

export function WorklistFollowup({ row, onClose, onDone }) {
  const [note, setNote] = useState("");
  const [outcome, setOutcome] = useState("contacted");
  const [promiseDate, setPromiseDate] = useState("");
  const [promiseAmount, setPromiseAmount] = useState(row.outstanding ? String(row.outstanding) : "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  async function save() {
    if (busy) return;
    if (!note.trim()) { setErr("Catatan wajib diisi."); return; }
    const janji = outcome === "promised" ? promiseError(promiseDate, promiseAmount) : "";
    if (janji) { setErr(janji); return; }
    setBusy(true);
    setErr("");
    try {
      await axios.post(`${API}/customers/${row.customer_id}/followups`, {
        customer_id: row.customer_id, order_id: row.order_id, note, outcome,
        ...(outcome === "promised" ? { promise_date: promiseDate, promise_amount: Number(promiseAmount) } : {}) });
      onDone?.(`Tindak lanjut untuk ${row.customer_name} dicatat.`);
    } catch (e) {
      setErr(apiErrorText(e, "Gagal menyimpan tindak lanjut."));
    } finally { setBusy(false); }
  }
  return (
    <FormModal open onClose={onClose} title={`Tindak Lanjut Penagihan — ${row.customer_name}`} icon={PhoneCall} size="sm"
      subtitle={`Pesanan ${row.order_number} · ${formatCurrency(row.outstanding)}${row.overdue ? ` · telat ${row.days_late} hari` : ""}`}
      testId="worklist-followup-modal" submitTestId="worklist-followup-submit" cancelTestId="worklist-followup-cancel"
      onSubmit={save} submitLabel="Simpan" busy={busy} error={err}>
      <div className="space-y-3">
        <div>
          <label className="field-label" htmlFor="worklist-followup-note">Catatan <span className="req">*</span></label>
          <textarea id="worklist-followup-note" data-testid="worklist-followup-note" value={note}
            onChange={(e) => { setNote(e.target.value); if (err) setErr(""); }} className="field" rows="3"
            placeholder="Hasil kontak penagihan..." />
        </div>
        <div>
          <label className="field-label">Hasil</label>
          <KNSelect value={outcome} onValueChange={setOutcome} className="field" data-testid="worklist-followup-outcome"
            options={FOLLOWUP_OUTCOMES} />
        </div>
        {outcome === "promised" && (
          <PromiseFields date={promiseDate} amount={promiseAmount} onDate={setPromiseDate} onAmount={setPromiseAmount}
            testIdPrefix="worklist-followup-promise" />
        )}
      </div>
    </FormModal>
  );
}
