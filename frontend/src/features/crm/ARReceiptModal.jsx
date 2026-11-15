/**
 * ARReceiptModal (EPIC3B) — Catat penerimaan pembayaran customer + alokasi ke order.
 * POST /api/ar-receipts. Mode Otomatis (FIFO) atau Manual (per order).
 *
 * Fase 4 · R1 — pop-up baku `FormModal` (dulu `.modal-card` buatan sendiri): layar penuh di HP (≤ 640 px), kepala &
 * tombol Simpan tetap terlihat, galat simpan tampil di kaki pop-up. Form ini juga dipakai aplikasi HP Sales
 * (`sales/mobile/MobileArReceipt`) — keputusan pemilik: form input HP = form desktop (tanggal terima, deposit,
 * mode alokasi, selisih bayar). Alur khusus HP diteruskan lewat props, bukan dengan memangkas isian:
 *   · `offline`  — simpan lewat antrean offline HP (`offlinePost`, kunci idempotensi sama) bila sinyal putus.
 *   · `testId`   — akar pop-up (bawaan `ar-receipt-modal`; isian tetap ber-testid `ar-receipt-*`).
 * `onDone(pesan, kwitansi)` — argumen kedua baru (data kwitansi dari server; `null` bila masuk antrean offline).
 *
 * PM-T3 — rekening penerima (`ReceiptPaymentFields`: dari rekening tujuan pesanan yang dialokasi atau bawaan PT), nomor
 * referensi (bertanda wajib bila `payment.wajib_nomor_referensi` menyala untuk PT ini), jatuh tempo giro, tautan bukti,
 * dan catatan alasan bila rekening ≠ instruksi bayar pesanan. Simpan meminta konfirmasi yang menyebut nominal, PT, dan
 * rekening (`02` N5). `preset` = { amount, accountId, reference, date } — form dibuka dari mutasi bank berkode bayar
 * (Rekonsiliasi Bank › "Catat kwitansi dari mutasi ini").
 *
 * PM-T4 — teks bantu tunai mengikuti mode tunai yang berlaku untuk akun ini di PT aktif (`GET /cash-holdings/me/summary`,
 * pengaturan `pembayaran.sales_terima_tunai`; pemegang kas selalu kas langsung): `titipan` → "Uang tunai ini dicatat
 * sebagai titipan di tangan Anda sampai disetor ke kasir atau bank." dan tanpa isian rekening; `dilarang` → pilihan
 * tunai tidak ditawarkan. Gagal dimuat (mis. HP luring) → tampilan lama; server tetap memutus.
 */
import KNDatePicker from "@/components/KNDatePicker";
import { useCallback, useEffect, useMemo, useState } from "react";
import MoneyInput from "@/components/MoneyInput";
import { Wallet, Scale } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import FormModal from "../../components/FormModal";
import { formatCurrency } from "../../utils/formatters";
import { apiErrorText } from "../../utils/apiError";
import { offlinePost } from "../../utils/offlineQueue";
// FASE G-3 — selisih pembayaran: setiap kurang/lebih bayar wajib punya keputusan berlabel.
import PaymentVarianceDialog from "../finance/payments/PaymentVarianceDialog";
import { assessVariance, directionMeta, varianceMeta } from "../finance/payments/paymentApi";

// PM-T1 — pilihan cara bayar dari daftar induk (master "Cara Bayar", per PT); titipan dipakai lewat kotak deposit.
import { usePaymentMethods } from "../../config/paymentMethods";
// PK-20 + PM-T3 — kas wajib berekening: rekening penerima PT kwitansi yang melayani cara bayarnya, referensi, instruksi.
import ReceiptPaymentFields, { receiptBlockReason } from "./ReceiptPaymentFields";
import { useEntityScope } from "../../context/EntityScopeContext";
import { askConfirm } from "../../services/confirmService";
import { entityShortById } from "../../utils/entityLabel";
import { TEKS_TITIPAN } from "../finance/cashholding/cashHoldingShared";
const LABEL = "text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]";

// Cek UI UAT v3 — tanggal LOKAL (dulu toISOString = UTC: 00.00–07.00 WIB jadi tanggal kemarin).
function today() { const d = new Date(); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10); }

export default function ARReceiptModal({ customerId, customerName, preselectOrderId, onClose, onDone, onError,
  offline = false, testId = "ar-receipt-modal", preset = null }) {
  const [openOrders, setOpenOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const newKey = () => (window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`);
  const [requestId, setRequestId] = useState(newKey);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [mode, setMode] = useState("auto"); // auto (FIFO) | manual
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("transfer");
  const pm = usePaymentMethods("masuk");
  const { selectedEntity, entities } = useEntityScope();   // PK-20 — kwitansi dibukukan di PT kepala aplikasi (PK-09)
  // PM-T3 — isian uang masuk + keadaan pemeriksaannya (alasan tombol simpan mati ditulis di samping tombol).
  const [pay, setPay] = useState(() => ({
    accountId: preset?.accountId || "", accountTouched: Boolean(preset?.accountId), reference: preset?.reference || "",
    giroDue: "", proofUrl: "", mismatchNote: "" }));
  const [payState, setPayState] = useState(null);
  const [refRequired, setRefRequired] = useState(false);
  // PM-T4 — mode tunai akun ini di PT aktif: "kas_langsung" | "titipan" | "dilarang" ("" = belum/tidak termuat).
  const [tunaiMode, setTunaiMode] = useState("");
  const methodOptions = useMemo(() => pm.methods.filter((m) => m.needs_account !== "tidak")
    .filter((m) => !(tunaiMode === "dilarang" && m.needs_account === "kas"))
    .map((m) => ({ value: m.code, label: m.name })), [pm.methods, tunaiMode]);
  // Cara bayar yang tidak aktif untuk PT ini tidak boleh tetap terpilih (mis. QRIS dimatikan khusus PT).
  useEffect(() => {
    if (methodOptions.length && !methodOptions.some((o) => o.value === method)) setMethod(methodOptions[0].value);
  }, [methodOptions, method]);
  const [date, setDate] = useState(() => (preset?.date ? String(preset.date).slice(0, 10) : today()));
  const [notes, setNotes] = useState("");
  const [alloc, setAlloc] = useState({}); // order_id -> amount
  const [busy, setBusy] = useState(false);
  const [deposit, setDeposit] = useState(0);
  const [useDeposit, setUseDeposit] = useState(false);
  const [depositAmt, setDepositAmt] = useState("");
  // FASE G-3 — takaran selisih (server-side) + keputusan yang dipilih petugas.
  const [assessment, setAssessment] = useState(null);
  const [assessing, setAssessing] = useState(false);
  const [reasons, setReasons] = useState([]);
  const [showVariance, setShowVariance] = useState(false);
  const [variance, setVariance] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ro, rd] = await Promise.all([
        axios.get(`${API}/ar-receipts/open-orders`, { params: { customer_id: customerId } }),
        axios.get(`${API}/ar-receipts/deposit`, { params: { customer_id: customerId } }).catch(() => ({ data: {} })),
      ]);
      const list = Array.isArray(ro.data) ? ro.data : [];
      const pre = preselectOrderId && list.find((o) => o.order_id === preselectOrderId);
      // Cek UI UAT v3 (S2) — pesanan asal tampil paling atas (dulu terselip di antara ratusan pesanan terbuka).
      setOpenOrders(pre ? [pre, ...list.filter((o) => o !== pre)] : list);
      setDeposit(Number(rd.data?.deposit_balance || 0));
      if (pre) {
        setMode("manual");
        // PM-T3 — dari mutasi bank: nominal mutasi (paling banyak sisa tagihan pesanan itu).
        const take = preset?.amount ? Math.min(Number(preset.amount) || 0, Number(pre.outstanding) || 0) : pre.outstanding;
        setAlloc({ [pre.order_id]: take });
        setAmount(String(take));
      } else if (preset?.amount) {
        setAmount(String(preset.amount));
      } else {
        const total = list.reduce((s, o) => s + Number(o.outstanding || 0), 0);
        setAmount(String(total));
      }
      setLoadError("");
    } catch (e) {
      setLoadError(apiErrorText(e, "Gagal memuat order terbuka."));
    } finally { setLoading(false); }
  }, [customerId, preselectOrderId]);

  useEffect(() => { load(); }, [load]);

  // PM-T3 — tanda wajib "No. referensi" mengikuti pengaturan PT (server tetap menolak bila kosong).
  useEffect(() => {
    let alive = true;
    const params = selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {};
    axios.get(`${API}/settings/effective`, { params })
      .then((r) => { if (alive) setRefRequired(Boolean(r.data?.payment?.wajib_nomor_referensi)); })
      .catch(() => { if (alive) setRefRequired(false); });
    return () => { alive = false; };
  }, [selectedEntity]);
  useEffect(() => {
    let alive = true;
    axios.get(`${API}/cash-holdings/me/summary`)
      .then((r) => { if (alive) setTunaiMode(String(r.data?.mode || "")); })
      .catch(() => { if (alive) setTunaiMode(""); });
    return () => { alive = false; };
  }, [selectedEntity]);

  useEffect(() => {
    (async () => {
      try { setReasons((await varianceMeta("", customerId)).reasons || []); }
      catch { setReasons([]); }
    })();
  }, [customerId]);

  const allocTotal = useMemo(
    () => Object.values(alloc).reduce((s, v) => s + (Number(v) || 0), 0),
    [alloc]
  );
  const effectiveAmount = mode === "manual" ? allocTotal : Number(amount) || 0;
  const depositUse = useDeposit ? Math.min(Number(depositAmt) || 0, deposit) : 0;
  const totalFunds = effectiveAmount + depositUse;
  // PM-T3 — pesanan yang akan menerima alokasi (manual = yang diisi; otomatis = pratinjau FIFO seperti server): bahan
  // rekening penerima bawaan dan peringatan "Tidak sesuai instruksi bayar pesanan".
  const allocatedOrders = useMemo(() => {
    if (mode === "manual") return openOrders.filter((o) => Number(alloc[o.order_id]) > 0);
    let sisa = totalFunds;
    const out = [];
    for (const o of openOrders) {
      if (sisa <= 0.01) break;
      const take = Math.min(sisa, Number(o.outstanding) || 0);
      if (take > 0.01) { out.push(o); sisa -= take; }
    }
    return out;
  }, [mode, openOrders, alloc, totalFunds]);
  const methodRow = pm.methods.find((m) => m.code === method) || null;
  // PM-T4 — tunai yang dicatat sebagai titipan di tangan pencatat: tanpa kas (tanpa rekening) sampai disetor.
  const titipan = tunaiMode === "titipan" && effectiveAmount > 0 && pm.isCash(method);
  const needsAccount = effectiveAmount > 0 && !titipan;   // deposit saja = tanpa kas baru (tanpa rekening)

  // Takar selisih setiap kali nominal / alokasi berubah (debounce) — angka `seharusnya`
  // dihitung server dari tagihan yang jatuh tempo, bukan dari sisi layar.
  useEffect(() => {
    if (!customerId || totalFunds <= 0) { setAssessment(null); return undefined; }
    const t = setTimeout(async () => {
      setAssessing(true);
      try {
        const body = {
          customer_id: customerId,
          amount: effectiveAmount,
          use_deposit_amount: depositUse,
          allocations: mode === "manual"
            ? Object.entries(alloc).filter(([, v]) => Number(v) > 0)
              .map(([order_id, v]) => ({ order_id, amount: Number(v) }))
            : [],
        };
        setAssessment(await assessVariance(body));
      } catch { setAssessment(null); }
      finally { setAssessing(false); }
    }, 450);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customerId, effectiveAmount, depositUse, mode, JSON.stringify(alloc)]);

  useEffect(() => { setVariance(null); }, [effectiveAmount, depositUse, mode]);

  function setAllocFor(orderId, value, max) {
    const v = Math.min(Math.max(Number(value) || 0, 0), max);
    setAlloc((p) => ({ ...p, [orderId]: v }));
  }

  async function submit(vpayload) {
    if (totalFunds <= 0) { setError("Jumlah pembayaran harus lebih dari 0."); return; }
    const vp = vpayload || variance;
    // FASE G-3 — kalau uangnya tidak pas, keputusannya diambil DULU (tidak ada yang senyap).
    if (assessment?.needs_decision && !vp) { setShowVariance(true); return; }
    const body = {
      customer_id: customerId,
      amount: effectiveAmount,
      method,
      receipt_date: new Date(date).toISOString(),
      notes,
      use_deposit_amount: depositUse,
      ...(needsAccount && pay.accountId ? { account_id: pay.accountId } : {}),
      ...(pay.reference.trim() ? { reference_no: pay.reference.trim() } : {}),
      ...(methodRow?.needs_due_date && pay.giroDue ? { giro_due_date: pay.giroDue } : {}),
      ...(pay.proofUrl.trim() ? { proof_url: pay.proofUrl.trim() } : {}),
      ...((payState?.mismatch || []).length ? { mismatch_note: pay.mismatchNote.trim() } : {}),
    };
    if (vp) body.variance = vp;
    if (mode === "manual") {
      body.allocations = Object.entries(alloc)
        .filter(([, v]) => Number(v) > 0)
        .map(([order_id, v]) => ({ order_id, amount: Number(v) }));
      if (body.allocations.length === 0) { setError("Isi alokasi minimal satu order."); return; }
    }
    // N5 — konfirmasi uang masuk menyebut nominal, PT, dan rekening penerima.
    const pt = entityShortById(entities, selectedEntity, "PT aktif");
    const rek = titipan ? "titipan tunai di tangan Anda (belum masuk kas)"
      : needsAccount ? (payState?.accountLabel || "rekening bawaan PT") : "deposit pelanggan (tanpa uang baru)";
    const ok = await askConfirm({
      title: `Catat pembayaran ${formatCurrency(totalFunds)}?`,
      message: `Dari ${customerName || "pelanggan"} untuk ${pt}, masuk ke ${rek}.`,
      confirmLabel: "Ya, catat pembayaran",
      testId: "ar-receipt-confirm",
    });
    if (!ok) return;
    setBusy(true); setError("");
    try {
      let data;
      if (offline) {
        // HP — sinyal putus: kwitansi masuk antrean HP dengan kunci yang SAMA (dikirim sekali saat online).
        const r = await offlinePost(`${API}/ar-receipts`, body,
          { idempotencyKey: requestId, label: `Kwitansi ${customerName} ${formatCurrency(totalFunds)}` });
        if (r.queued) {
          onDone?.("Offline — kwitansi tersimpan di HP, dikirim saat sinyal kembali (tanpa dobel).", null);
          return;
        }
        data = r.data;
      } else {
        // L02 LN-023-T03 — satu kunci per dialog: klik ganda / retry jaringan tidak membuat kwitansi dobel.
        data = (await axios.post(`${API}/ar-receipts`, body, { headers: { "Idempotency-Key": requestId } })).data;
      }
      const v = data?.variance || {};
      const extra = v.decision_number
        ? ` Selisih diputus: ${v.reason_label || v.decision_kind} (${v.decision_number}).`
        : (v.needs_decision
          ? ` Selisihnya masuk antrean Selisih Bayar untuk diputus.${
            v.decision_error ? ` Catatan: ${v.decision_error}` : ""}`
          : "");
      onDone?.(`Pembayaran ${data?.number || ""} (${formatCurrency(data?.applied_total ?? data?.amount)}) dicatat untuk ${customerName}.${extra}`, data);
    } catch (e) {
      // Respons gagal (4xx) ikut tersimpan pada kunci — percobaan berikutnya memakai kunci baru.
      if (e.response) setRequestId(newKey());
      const msg = apiErrorText(e, "Gagal mencatat pembayaran.");
      setError(msg); onError?.(msg);
    } finally { setBusy(false); }
  }

  const blockReason = (needsAccount || titipan) ? receiptBlockReason(payState) : "";
  const accBlocked = Boolean(blockReason);
  const cashHint = titipan ? TEKS_TITIPAN
    : pm.isCash(method)
      ? `${pm.labelOf(method)} → masuk Kas Kecil (per PT).`
      : `${pm.labelOf(method)} → masuk Kas Besar (bank).`;

  const footer = (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="min-w-0 text-[12px]">
        <span className="text-[#6B6B73]">Total dibayar: </span>
        <span data-testid="ar-receipt-total" className="font-bold tabular-nums text-[#1B7F4B]">{formatCurrency(totalFunds)}</span>
        {depositUse > 0 && <span className="text-[10.5px] text-[#6B6B73] ml-1">(kas {formatCurrency(effectiveAmount)} + deposit {formatCurrency(depositUse)})</span>}
        {assessment?.direction && assessment.direction !== "none" && (
          <span className="ml-2 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase"
            style={{ background: directionMeta(assessment.direction).bg,
              color: directionMeta(assessment.direction).fg }}
            data-testid="ar-receipt-variance-badge">
            {directionMeta(assessment.direction).label}
          </span>
        )}
      </div>
      <div className="ml-auto flex items-center gap-2">
        {accBlocked && (
          <span className="text-fs-12 text-kn-text-2" data-testid="ar-receipt-account-reason">{blockReason}</span>
        )}
        <button type="button" onClick={onClose} className="secondary-button" disabled={busy} data-testid="ar-receipt-cancel">Batal</button>
        <button type="button" data-testid="ar-receipt-submit" disabled={busy || totalFunds <= 0 || accBlocked} onClick={() => submit()} className="primary-button">
          {busy ? "Menyimpan..." : "Simpan Pembayaran"}
        </button>
      </div>
    </div>
  );

  return (
    <>
      <FormModal open onClose={onClose} title={`Catat Pembayaran · ${customerName || ""}`} icon={Wallet} size="md"
        testId={testId} busy={busy || showVariance} error={error} footer={footer}>
        {/* `busy` saat dialog selisih terbuka: Esc / klik latar tidak menutup form di bawahnya (isian tidak hilang). */}
        <div className="space-y-3">
          <ErrorNotice message={loadError} onRetry={load} onDismiss={() => setLoadError("")} testId="ar-receipt-error" />

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <div>
              <label className={LABEL}>Cara bayar</label>
              <KNSelect data-testid="ar-receipt-method" className="field" value={method} onValueChange={setMethod} options={methodOptions} />
            </div>
            <div>
              <label className={LABEL}>Tanggal</label>
              <KNDatePicker data-testid="ar-receipt-date" value={date} onChange={setDate} clearable={false} />
            </div>
          </div>
          {titipan ? (
            <p className="flex items-start gap-1.5 rounded-md bg-kn-warning-soft px-2 py-1.5 text-fs-12 text-kn-warning-text"
              data-testid="ar-receipt-cash-hint">
              <Wallet size={13} className="mt-0.5 shrink-0" aria-hidden="true" />{cashHint}
            </p>
          ) : (
            <p className="text-[10.5px] text-[#9A9BA3] -mt-1" data-testid="ar-receipt-cash-hint">{cashHint}</p>
          )}
          {(needsAccount || titipan) && (
            <ReceiptPaymentFields entityId={selectedEntity} method={method} methodRow={methodRow} titipan={titipan}
              orders={allocatedOrders} refRequired={refRequired} value={pay} onChange={setPay} onState={setPayState} />
          )}

          {deposit > 0 && (
            <div className="rounded-md border border-[#E6F6EC] bg-[#F2FBF5] px-3 py-2" data-testid="ar-receipt-deposit-box">
              <label className="flex items-center gap-2 text-[12px] font-semibold text-[#1B7F4B] cursor-pointer">
                <input type="checkbox" data-testid="ar-receipt-use-deposit" checked={useDeposit}
                  onChange={(e) => { setUseDeposit(e.target.checked); if (e.target.checked && !depositAmt) setDepositAmt(String(deposit)); }} />
                Pakai deposit pelanggan (tersedia {formatCurrency(deposit)})
              </label>
              {useDeposit && (
                <MoneyInput testId="ar-receipt-deposit-amount" className="field mt-2 py-1 text-[12px]"
                  value={depositAmt} placeholder="0"
                  onChange={(v) => setDepositAmt(String(Math.min(Math.max(Number(v) || 0, 0), deposit)))} />
              )}
            </div>
          )}

          <div className="tab-bar" role="group" aria-label="Mode alokasi">
            <button type="button" data-testid="ar-receipt-mode-auto" aria-pressed={mode === "auto"} className={`tab-button ${mode === "auto" ? "active" : ""}`} onClick={() => setMode("auto")}>Otomatis (FIFO)</button>
            <button type="button" data-testid="ar-receipt-mode-manual" aria-pressed={mode === "manual"} className={`tab-button ${mode === "manual" ? "active" : ""}`} onClick={() => setMode("manual")}>Manual per Pesanan</button>
          </div>

          {mode === "auto" ? (
            <div>
              <label className={LABEL}>Jumlah Diterima</label>
              <MoneyInput testId="ar-receipt-amount" className="field" value={amount} onChange={(v) => setAmount(v)} placeholder="0" />
              <p className="text-[10.5px] text-[#9A9BA3] mt-1">Dialokasikan otomatis ke pesanan terbuka tertua lebih dulu.</p>
            </div>
          ) : null}

          <div className="rounded-md border border-[#EFF0F2] overflow-hidden">
            <div className="px-3 py-1.5 bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73] border-b border-[#EFF0F2] flex justify-between">
              <span>Pesanan Terbuka</span><span>{openOrders.length} pesanan</span>
            </div>
            {loading ? (
              <div className="py-8 text-center text-[12px] text-[#6B6B73]" data-testid="ar-receipt-loading">Memuat...</div>
            ) : openOrders.length === 0 ? (
              <div className="py-8 text-center text-[12px] text-[#6B6B73]" data-testid="ar-receipt-no-orders">Tidak ada pesanan terbuka. 🎉</div>
            ) : (
              <div className="divide-y divide-[#EFF0F2] max-h-[240px] overflow-y-auto">
                {openOrders.map((o) => (
                  <div key={o.order_id} data-testid={`ar-receipt-order-${o.order_id}`} className="flex items-center gap-2 px-3 py-2 text-[12px]">
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-[#0058CC]">
                        {o.number}
                        {/* Pesanan asal (dibuka dari SO / HP) ditandai — dulu hanya di form HP. */}
                        {preselectOrderId && o.order_id === preselectOrderId && (
                          <span className="ml-1 rounded bg-[#EAF2FF] px-1 text-[10px] font-semibold" data-testid="ar-receipt-order-focus">dibuka</span>
                        )}
                      </p>
                      <p className="text-[10px] text-[#6B6B73] tabular-nums">Belum Lunas {formatCurrency(o.outstanding)}</p>
                      {/* PM-T3 — instruksi bayar pesanan (rekening tujuan & kode bayar PM-T2) */}
                      {(o.receiving_account?.account_number || o.payment_code) && (
                        <p className="text-fs-12 text-kn-text-2" data-testid={`ar-receipt-instruction-${o.order_id}`}>
                          {o.receiving_account?.account_number
                            ? `Instruksi: ${o.receiving_account.bank_name || ""} ${o.receiving_account.account_number}`.trim() : "Instruksi bayar"}
                          {o.payment_code ? ` · kode ${o.payment_code}` : ""}
                        </p>
                      )}
                    </div>
                    {mode === "manual" ? (
                      <MoneyInput testId={`ar-receipt-alloc-${o.order_id}`} className="field w-36 py-1 text-[12px]"
                        value={alloc[o.order_id] ?? ""} placeholder="0" aria-label={`Alokasi ke ${o.number}`}
                        onChange={(v) => setAllocFor(o.order_id, v, o.outstanding)} />
                    ) : (
                      <span className="text-[11px] text-[#9A9BA3] tabular-nums">{formatCurrency(o.outstanding)}</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className={LABEL}>Catatan</label>
            <input data-testid="ar-receipt-notes" className="field" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Catatan tambahan (opsional)" />
          </div>

          {/* FASE G-3 — pengingat selisih pembayaran SEBELUM disimpan (tidak ada kejutan) */}
          {assessment && totalFunds > 0 && (
            <div data-testid="ar-receipt-variance-hint"
              className={`flex items-start gap-2 rounded-md border px-3 py-2 ${
                assessment.needs_decision
                  ? "border-[#F5D9A8] bg-[#FFF9E6]"
                  : assessment.direction === "rounding"
                    ? "border-[#DCDDE1] bg-[#F7F7F9]"
                    : "border-[#CFEEDC] bg-[#F2FBF5]"}`}>
              <Scale size={14} className="mt-0.5 shrink-0 text-[#6B6B73]" />
              <div className="min-w-0 flex-1">
                {assessment.needs_decision ? (
                  <p className="text-[11.5px] font-semibold text-[#8A6D00]">
                    {Number(assessment.delta) < 0 ? "Kurang" : "Lebih"} bayar{" "}
                    <b className="tabular-nums">{formatCurrency(Math.abs(Number(assessment.delta || 0)))}</b>{" "}
                    dari {assessment.boundary_label || "tagihan jatuh tempo"}{" "}
                    ({formatCurrency(assessment.boundary ?? assessment.expected)}) — akan diminta
                    keputusan saat disimpan.
                  </p>
                ) : assessment.direction === "rounding" ? (
                  <p className="text-[11.5px] text-[#4A4B52]">
                    Selisih {formatCurrency(Math.abs(Number(assessment.delta || 0)))} masih di dalam
                    toleransi {formatCurrency(assessment.tolerance)} — akan diselesaikan otomatis
                    sebagai pembulatan (tetap tercatat).
                  </p>
                ) : (
                  <p className="text-[11.5px] text-[#1B7F4B]">
                    Nominal sesuai tagihan — tidak ada selisih yang perlu diputuskan.
                  </p>
                )}
                {variance && (
                  <p className="mt-0.5 text-[10.5px] font-semibold text-[#0058CC]"
                    data-testid="ar-receipt-variance-chosen">
                    Keputusan dipilih: {variance.kind} · alasan {variance.reason_code}
                    {" · "}
                    <button type="button" className="underline"
                      onClick={() => setShowVariance(true)}>ubah</button>
                  </p>
                )}
                {assessing && <p className="text-[10px] text-[#9A9BA3]">menghitung selisih…</p>}
              </div>
              {assessment.needs_decision && !variance && (
                <button type="button" className="secondary-button !py-1 shrink-0"
                  data-testid="ar-receipt-variance-open" onClick={() => setShowVariance(true)}>
                  Putuskan
                </button>
              )}
            </div>
          )}
        </div>
      </FormModal>

      {showVariance && assessment && (
        <PaymentVarianceDialog assessment={assessment} reasons={reasons} busy={busy}
          error="" submitLabel="Lanjutkan & simpan pembayaran"
          onCancel={() => setShowVariance(false)}
          onConfirm={(payload) => {
            setVariance(payload);
            setShowVariance(false);
            submit(payload);
          }} />
      )}
    </>
  );
}
