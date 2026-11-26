/**
 * ReceivePaymentModal (MN-T3) — SATU form "Terima pembayaran pelanggan" untuk semua titik masuk (Perlu Tindakan,
 * Piutang, kartu pelanggan, detail pesanan, gerbang kirim, Rekonsiliasi Bank, HP sales). Dulu `crm/ARReceiptModal`
 * (EPIC3B · PK-19 · PM-T3 · PM-T4); berkas lama mengekspor ulang komponen ini sampai serah-terima (b).
 *
 * Tanda tangan: `{ customerId?, customerName?, preselectOrderId?, bankLineId?, amountHint?, onClose, onDone }`.
 *  · Tanpa `customerId` form dibuka dengan langkah **Pilih pelanggan** (mis. mutasi bank tanpa kode bayar).
 *  · `preselectOrderId` → alokasi "Atur sendiri" terisi untuk pesanan itu (paling banyak sisa tagihannya).
 *  · `bankLineId` (+ `amountHint`, `preset.accountId/date/reference`) → sesudah kwitansi tersimpan, kas kwitansinya
 *    ditautkan ke baris mutasi itu (`POST /bank-reconciliation/lines/{id}/match`); kwitansi menjadi terverifikasi bank.
 *  · Kompatibel dengan pemanggil lama: `preset`, `offline` (antrean HP), `testId`, `onError`.
 *
 * Isian: Pelanggan · Nominal diterima · Tanggal terima · Cara bayar · Rekening penerima (PM-T3 `ReceiptPaymentFields`)
 * · Pakai titipan · Alokasi ke tagihan ("Tertua dulu" · "Atur sendiri") · Catatan. Banner "PT: {nama PT}".
 * Tombol "Simpan kwitansi" → konfirmasi "Catat penerimaan Rp {nominal} dari {pelanggan} ke {rekening} untuk {nama PT}?"
 * ("Ya, simpan" / "Batal", `02` N5). Mode Semua PT: tombol mati + "Pilih satu PT untuk mencatat pembayaran." (L4).
 * Kunci idempotensi dari `useIntentKey` (N4); klik ganda ditahan; galat server tampil di dalam pop-up.
 * Selisih bayar: dialog selisih yang ada (`PaymentVarianceDialog`, FASE G-3). Isi permintaan = `receiptBody` (dibagi
 * dengan uji lapis B lewat `__tests__/fixtures/mnt3_isi_form.json`).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Building2, Scale, Wallet } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import KNDatePicker from "../../../components/KNDatePicker";
import KNSelect from "../../../components/KNSelect";
import MoneyInput from "../../../components/MoneyInput";
import ErrorNotice from "../../../components/ErrorNotice";
import FormModal from "../../../components/FormModal";
import FilterChips from "../../../components/FilterChips";
import { formatCurrency, todayWib } from "../../../utils/formatters";
import { heldMoney } from "../../../utils/parseMoney";
import { apiErrorText } from "../../../utils/apiError";
import { offlinePost } from "../../../utils/offlineQueue";
import { moneyPost } from "../../../utils/moneyRequest";
import useIntentKey from "../../../hooks/useIntentKey";
import PaymentVarianceDialog from "./PaymentVarianceDialog";
import { assessVariance, directionMeta, varianceMeta } from "./paymentApi";
import { usePaymentMethods } from "../../../config/paymentMethods";
import ReceiptPaymentFields, { receiptBlockReason } from "../../crm/ReceiptPaymentFields";
import { useEntityScope } from "../../../context/EntityScopeContext";
import { askConfirm } from "../../../services/confirmService";
import { entityShortById } from "../../../utils/entityLabel";
import { TEKS_TITIPAN } from "../cashholding/cashHoldingShared";

export const TEKS_PILIH_PT = "Pilih satu PT untuk mencatat pembayaran.";
export const ALOKASI = [{ key: "auto", label: "Tertua dulu" }, { key: "manual", label: "Atur sendiri" }];

// Tanggal LOKAL (WIB) — toISOString polos = UTC: 00.00–07.00 WIB jadi tanggal kemarin.
// P23 (15 Nov, dipindah dari ARReceiptModal saat integrasi) — tanggal bawaan = hari ini WIB, bukan zona perangkat:
// di peramban berzona UTC pukul 00.00–07.00 WIB kwitansi dulu tercatat kemarin.
const today = () => todayWib();

/** Isi `POST /api/ar-receipts` dari keadaan form (satu pembentuk — dipakai form dan uji kontrak). */
export function receiptBody({ customerId, amount, method, date, notes = "", depositUse = 0, accountId = "",
  reference = "", giroDue = "", proofUrl = "", mismatchNote = "", mismatch = false, needsAccount = true,
  needsDueDate = false, allocations = null, variance = null }) {
  const body = {
    customer_id: customerId, amount, method, receipt_date: new Date(date).toISOString(), notes,
    use_deposit_amount: depositUse,
    ...(needsAccount && accountId ? { account_id: accountId } : {}),
    ...(String(reference || "").trim() ? { reference_no: String(reference).trim() } : {}),
    ...(needsDueDate && giroDue ? { giro_due_date: giroDue } : {}),
    ...(String(proofUrl || "").trim() ? { proof_url: String(proofUrl).trim() } : {}),
    ...(mismatch ? { mismatch_note: String(mismatchNote || "").trim() } : {}),
  };
  if (variance) body.variance = variance;
  if (allocations) body.allocations = allocations;
  return body;
}

/** Kalimat konfirmasi N5 (persis spesifikasi). */
export const receiptConfirmText = ({ amount, customer, account, pt }) =>
  `Catat penerimaan ${formatCurrency(amount)} dari ${customer || "pelanggan"} ke ${account} untuk ${pt}?`;

function CustomerStep({ value, onPick }) {
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState("");
  const load = useCallback(async () => {
    setErr("");
    try {
      const r = await axios.get(`${API}/customers`, { params: { limit: 500, with_credit: false } });
      setRows(Array.isArray(r.data) ? r.data : r.data?.items || []);
    } catch (e) { setErr(apiErrorText(e, "Daftar pelanggan belum bisa dimuat.")); setRows([]); }
  }, []);
  useEffect(() => { load(); }, [load]);
  const options = useMemo(() => (rows || []).map((c) => ({ value: c.id, label: c.code ? `${c.name} · ${c.code}` : c.name })),
    [rows]);
  return (
    <div className="space-y-2" data-testid="ar-receipt-pick-customer">
      <ErrorNotice message={err} onRetry={load} testId="ar-receipt-customers-error" />
      <label className="field-label" htmlFor="ar-receipt-customer">Pelanggan *</label>
      <KNSelect id="ar-receipt-customer" data-testid="ar-receipt-customer" className="field" searchable value={value}
        placeholder={rows === null ? "Memuat pelanggan…" : "Pilih pelanggan"} options={options}
        onValueChange={(v) => onPick(v, (rows || []).find((c) => c.id === v)?.name || "")} />
      <p className="text-fs-12 text-kn-text-2">Pilih pelanggan pemilik uang ini dulu; tagihan terbukanya tampil sesudahnya.</p>
    </div>
  );
}

export default function ReceivePaymentModal({ customerId: customerIdProp = "", customerName: customerNameProp = "",
  preselectOrderId, bankLineId = "", amountHint, onClose, onDone, onError, offline = false,
  testId = "ar-receipt-modal", preset = null, cashOnly = false }) {
  const [picked, setPicked] = useState({ id: customerIdProp || "", name: customerNameProp || "" });
  const customerId = customerIdProp || picked.id;
  const customerName = customerNameProp || picked.name;
  const hintAmount = amountHint ?? preset?.amount;
  const [openOrders, setOpenOrders] = useState([]);
  const [loading, setLoading] = useState(Boolean(customerId));
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [mode, setMode] = useState("auto");
  const [amount, setAmount] = useState(hintAmount ? String(hintAmount) : "");
  // Uji variasi isian (pelatihan 18 Nov) — kolom Nominal diterima sudah bisa diketik selagi tagihan terbuka dimuat.
  // Dulu isian otomatis (sisa tagihan) sesudah muat MENIMPA ketikan ("50.000" lalu bercampur jadi "832.500"). Kini
  // isian otomatis hanya bila pengguna belum menyentuh kolom itu (`amountTouched`); ketikannya yang dipakai.
  const amountTouched = useRef(false);
  const amountNow = useRef(amount);
  const ketikNominal = (v) => { amountTouched.current = true; amountNow.current = v; setAmount(v); };
  const [method, setMethod] = useState("transfer");
  const pm = usePaymentMethods("masuk");
  const { selectedEntity, entities } = useEntityScope();
  const allPt = !selectedEntity || selectedEntity === "all";
  const ptName = entityShortById(entities, selectedEntity, "PT aktif");
  const [pay, setPay] = useState(() => ({
    accountId: preset?.accountId || "", accountTouched: Boolean(preset?.accountId), reference: preset?.reference || "",
    giroDue: "", proofUrl: "", mismatchNote: "" }));
  const [payState, setPayState] = useState(null);
  const [refRequired, setRefRequired] = useState(false);
  const [tunaiMode, setTunaiMode] = useState("");
  const methodOptions = useMemo(() => pm.methods.filter((m) => m.needs_account !== "tidak")
    .filter((m) => !(tunaiMode === "dilarang" && m.needs_account === "kas"))
    .filter((m) => !cashOnly || m.needs_account === "kas")   // LB-T8 — pesanan tertahan bayar: non-pemutus hanya boleh uang tunai baru
    .map((m) => ({ value: m.code, label: m.name })), [pm.methods, tunaiMode, cashOnly]);
  useEffect(() => {
    if (methodOptions.length && !methodOptions.some((o) => o.value === method)) setMethod(methodOptions[0].value);
  }, [methodOptions, method]);
  const [date, setDate] = useState(() => (preset?.date ? String(preset.date).slice(0, 10) : today()));
  const [notes, setNotes] = useState("");
  const [alloc, setAlloc] = useState({});
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const intent = useIntentKey("arrc");
  const matchIntent = useIntentKey("arrcbank");
  const [deposit, setDeposit] = useState(0);
  const [useDeposit, setUseDeposit] = useState(false);
  const [depositAmt, setDepositAmt] = useState("");
  const [assessment, setAssessment] = useState(null);
  const [assessing, setAssessing] = useState(false);
  const [reasons, setReasons] = useState([]);
  const [showVariance, setShowVariance] = useState(false);
  const [variance, setVariance] = useState(null);

  const load = useCallback(async () => {
    if (!customerId) { setLoading(false); return; }
    setLoading(true);
    try {
      const [ro, rd] = await Promise.all([
        axios.get(`${API}/ar-receipts/open-orders`, { params: { customer_id: customerId } }),
        axios.get(`${API}/ar-receipts/deposit`, { params: { customer_id: customerId } }).catch(() => ({ data: {} })),
      ]);
      const list = Array.isArray(ro.data) ? ro.data : [];
      const pre = preselectOrderId && list.find((o) => o.order_id === preselectOrderId);
      setOpenOrders(pre ? [pre, ...list.filter((o) => o !== pre)] : list);
      setDeposit(Number(rd.data?.deposit_balance || 0));
      const diketik = amountTouched.current ? heldMoney(amountNow.current) : NaN;
      if (amountTouched.current) {
        // Nominal sudah diketik: tidak ditimpa. Pesanan yang dibuka & nominal ≤ sisanya → "Atur sendiri" ke pesanan itu
        // sebesar ketikan; selain itu tetap "Tertua dulu" dengan ketikan (lebih bayar → dialog selisih seperti biasa).
        if (pre && diketik > 0 && diketik <= (Number(pre.outstanding) || 0) + 0.005) {
          setMode("manual");
          setAlloc({ [pre.order_id]: diketik });
        }
      } else if (pre) {
        setMode("manual");
        // S3 (pelatihan 18 Nov) — termin DP: isian bawaan = yang DITAGIH sekarang (uang muka, `due_now` server — angka
        // baris Penagihan), bukan seluruh sisa pesanan yang belum dikirim.
        const ditagih = Number(pre.due_now) > 0 ? Math.min(Number(pre.due_now), Number(pre.outstanding) || 0) : pre.outstanding;
        const take = hintAmount ? Math.min(Number(hintAmount) || 0, Number(pre.outstanding) || 0) : ditagih;
        setAlloc({ [pre.order_id]: take });
        setAmount(String(take));
      } else if (hintAmount) {
        setAmount(String(hintAmount));
      } else {
        setAmount(String(list.reduce((s, o) => s + Number(o.outstanding || 0), 0)));
      }
      setLoadError("");
    } catch (e) {
      setLoadError(apiErrorText(e, "Tagihan terbuka pelanggan belum bisa dimuat."));
    } finally { setLoading(false); }
  }, [customerId, preselectOrderId, hintAmount]);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    let alive = true;
    const params = !allPt ? { entity_id: selectedEntity } : {};
    axios.get(`${API}/settings/effective`, { params })
      .then((r) => { if (alive) setRefRequired(Boolean(r.data?.payment?.wajib_nomor_referensi)); })
      .catch(() => { if (alive) setRefRequired(false); });
    return () => { alive = false; };
  }, [selectedEntity, allPt]);
  useEffect(() => {
    let alive = true;
    axios.get(`${API}/cash-holdings/me/summary`)
      .then((r) => { if (alive) setTunaiMode(String(r.data?.mode || "")); })
      .catch(() => { if (alive) setTunaiMode(""); });
    return () => { alive = false; };
  }, [selectedEntity]);
  useEffect(() => {
    if (!customerId) return;
    (async () => {
      try { setReasons((await varianceMeta("", customerId)).reasons || []); } catch { setReasons([]); }
    })();
  }, [customerId]);

  // Uji variasi isian (pelatihan 18 Nov) — nominal dibaca `heldMoney` (teks kanonik MoneyInput / angka); dulu
  // `Number("3374122,5")` = NaN → Rp 0 padahal pratinjau kotak menampilkan Rp 3.374.123.
  const allocTotal = useMemo(() => Object.values(alloc).reduce((s, v) => s + (heldMoney(v) || 0), 0), [alloc]);
  const depositWanted = useDeposit && !cashOnly ? Math.min(heldMoney(depositAmt) || 0, deposit) : 0;
  // Pelatihan 18 Nov (F04) — "Atur sendiri": angka per tagihan = yang DILUNASI (uang baru + titipan). Dulu titipan
  // ditambahkan DI LUAR alokasi (uang = Σ alokasi, titipan = dana lebih) → pesanan tidak bertambah lunas, titipan
  // kembali utuh, dan kwitansi terbaca "lebih bayar" sebesar titipan. Kini titipan dipakai lebih dulu dan uang baru =
  // Σ alokasi − titipan. "Tertua dulu" tidak berubah: nominal = uang baru, titipan menambah dana.
  const depositUse = mode === "manual" ? Math.min(depositWanted, allocTotal) : depositWanted;
  const effectiveAmount = mode === "manual"
    ? Math.round(Math.max(allocTotal - depositUse, 0) * 100) / 100 : Math.round((heldMoney(amount) || 0) * 100) / 100;
  const totalFunds = effectiveAmount + depositUse;
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
  const titipan = tunaiMode === "titipan" && effectiveAmount > 0 && pm.isCash(method);
  const needsAccount = effectiveAmount > 0 && !titipan;

  useEffect(() => {
    if (!customerId || totalFunds <= 0) { setAssessment(null); return undefined; }
    const t = setTimeout(async () => {
      setAssessing(true);
      try {
        setAssessment(await assessVariance({
          customer_id: customerId, amount: effectiveAmount, use_deposit_amount: depositUse,
          allocations: mode === "manual" ? Object.entries(alloc).filter(([, v]) => Number(v) > 0)
            .map(([order_id, v]) => ({ order_id, amount: Number(v) })) : [],
        }));
      } catch { setAssessment(null); } finally { setAssessing(false); }
    }, 450);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customerId, effectiveAmount, depositUse, mode, JSON.stringify(alloc)]);
  useEffect(() => { setVariance(null); }, [effectiveAmount, depositUse, mode]);

  function setAllocFor(orderId, value, max) {
    setAlloc((p) => ({ ...p, [orderId]: Math.min(Math.max(heldMoney(value) || 0, 0), max) }));
  }

  async function linkBankLine(rc) {
    if (!bankLineId || !rc?.cash_txn_id) return "";
    try {
      const b = { txn_id: rc.cash_txn_id };
      await matchIntent.send({ line: bankLineId, ...b },
        (k) => moneyPost(`${API}/bank-reconciliation/lines/${bankLineId}/match`, b, k));
      return ` Mutasi ditautkan ke kwitansi ${rc.number || ""} — kwitansi terverifikasi bank.`;
    } catch (e) {
      return ` Mutasi bank belum tertaut: ${apiErrorText(e, "coba tautkan di Rekonsiliasi.")}`;
    }
  }

  async function submit(vpayload) {
    if (inFlight.current || busy) return;   // klik ganda: satu niat saja
    if (allPt) { setError(TEKS_PILIH_PT); return; }
    if (totalFunds <= 0) { setError("Nominal diterima harus lebih dari 0."); return; }
    const vp = vpayload || variance;
    if (assessment?.needs_decision && !vp) { setShowVariance(true); return; }
    const allocations = mode === "manual" ? Object.entries(alloc).filter(([, v]) => Number(v) > 0)
      .map(([order_id, v]) => ({ order_id, amount: Number(v) })) : null;
    if (mode === "manual" && !allocations.length) { setError("Isi alokasi minimal satu tagihan."); return; }
    const body = receiptBody({
      customerId, amount: effectiveAmount, method, date, notes, depositUse, accountId: pay.accountId,
      reference: pay.reference, giroDue: pay.giroDue, proofUrl: pay.proofUrl, mismatchNote: pay.mismatchNote,
      mismatch: (payState?.mismatch || []).length > 0, needsAccount, needsDueDate: Boolean(methodRow?.needs_due_date),
      allocations, variance: vp || null,
    });
    const rek = titipan ? "titipan tunai di tangan Anda (belum masuk kas)"
      : needsAccount ? (payState?.accountLabel || "rekening bawaan PT") : "titipan pelanggan (tanpa uang baru)";
    inFlight.current = true;
    try {
      const ok = await askConfirm({
        title: "Simpan kwitansi",
        message: receiptConfirmText({ amount: totalFunds, customer: customerName, account: rek, pt: ptName }),
        confirmLabel: "Ya, simpan", cancelLabel: "Batal", testId: "ar-receipt-confirm",
      });
      if (!ok) return;
      setBusy(true); setError("");
      let data;
      if (offline) {
        const r = await offlinePost(`${API}/ar-receipts`, body,
          { idempotencyKey: intent.keyFor(body), label: `Kwitansi ${customerName} ${formatCurrency(totalFunds)}` });
        if (r.queued) {
          onDone?.("Offline — kwitansi tersimpan di HP, dikirim saat sinyal kembali (tanpa dobel).", null);
          return;
        }
        intent.done();
        data = r.data;
      } else {
        data = (await intent.send(body, (k) => moneyPost(`${API}/ar-receipts`, body, k))).data;
      }
      const v = data?.variance || {};
      const extra = v.decision_number
        ? ` Selisih diputus: ${v.reason_label || v.decision_kind} (${v.decision_number}).`
        : (v.needs_decision
          ? ` Selisihnya masuk antrean Selisih Bayar untuk diputus.${v.decision_error ? ` Catatan: ${v.decision_error}` : ""}`
          : "");
      const bank = await linkBankLine(data);
      // Pelatihan 18 Nov (F04) — lebih bayar: dulu pesan hanya menyebut yang teralokasi (Rp 1.971.027) padahal uang yang
      // diterima Rp 2.000.000; kini nominal diterima + rinciannya (melunasi tagihan · jadi titipan pelanggan).
      const sisaTitipan = Number(data?.unapplied_amount || 0);
      const diterima = sisaTitipan > 0.01 ? (data?.total_funds ?? data?.amount) : (data?.applied_total ?? data?.amount);
      const rinci = sisaTitipan > 0.01
        ? ` ${formatCurrency(data?.applied_total || 0)} melunasi tagihan, ${formatCurrency(sisaTitipan)} menjadi titipan pelanggan.` : "";
      onDone?.(`Kwitansi ${data?.number || ""} (${formatCurrency(diterima)}) dicatat untuk ${customerName}.${rinci}${extra}${bank}`, data);
    } catch (e) {
      const msg = apiErrorText(e, "Kwitansi belum bisa disimpan.");
      setError(msg); onError?.(msg);
    } finally { setBusy(false); inFlight.current = false; }
  }

  const blockReason = (needsAccount || titipan) ? receiptBlockReason(payState) : "";
  // Tombol mati selalu beralasan tertulis di sampingnya (KN_37).
  const reason = allPt ? TEKS_PILIH_PT : !customerId ? "Pilih pelanggan dulu." : (!loading && totalFunds < 0)
    ? "Nominal tidak boleh minus." : (!loading && totalFunds <= 0) ? "Isi nominal diterima." : blockReason;
  const cashHint = titipan ? TEKS_TITIPAN
    : pm.isCash(method) ? `${pm.labelOf(method)} → masuk Kas Kecil (per PT).` : `${pm.labelOf(method)} → masuk Kas Besar (bank).`;
  const dir = assessment?.direction && assessment.direction !== "none" ? directionMeta(assessment.direction) : null;

  const footer = (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="min-w-0 text-fs-12">
        <span className="text-kn-text-2">Total diterima: </span>
        <span data-testid="ar-receipt-total" className="whitespace-nowrap font-bold tabular-nums text-kn-success-text">{formatCurrency(totalFunds)}</span>
        {depositUse > 0 && <span className="ml-1 text-kn-text-2">(uang {formatCurrency(effectiveAmount)} + titipan {formatCurrency(depositUse)})</span>}
        {dir && <span className="status-pill status-pending ml-2" data-testid="ar-receipt-variance-badge"><Scale size={12} aria-hidden="true" />{dir.label}</span>}
      </div>
      <div className="ml-auto flex flex-wrap items-center justify-end gap-2">
        {reason && <span className="text-fs-12 text-kn-text-2"
          data-testid={allPt ? "ar-receipt-scope-note" : reason === blockReason ? "ar-receipt-account-reason" : "ar-receipt-reason"}>{reason}</span>}
        <button type="button" onClick={onClose} className="secondary-button btn-sm whitespace-nowrap" disabled={busy} data-testid="ar-receipt-cancel">Batal</button>
        <button type="button" data-testid="ar-receipt-submit" className="primary-button btn-sm whitespace-nowrap"
          disabled={busy || !customerId || totalFunds <= 0 || Boolean(reason)} onClick={() => submit()}>
          {busy ? "Menyimpan…" : "Simpan kwitansi"}
        </button>
      </div>
    </div>
  );

  return (
    <>
      <FormModal open onClose={onClose} title={customerName ? `Terima pembayaran · ${customerName}` : "Terima pembayaran pelanggan"}
        icon={Wallet} size="md" testId={testId} busy={busy || showVariance} error={error} footer={footer}>
        <div className="space-y-3">
          <p className="notice-bar info text-fs-12" data-testid="ar-receipt-pt">
            <Building2 size={13} aria-hidden="true" />PT: {allPt ? "Semua PT" : ptName}
          </p>
          {!customerId ? (
            <CustomerStep value={picked.id} onPick={(id, name) => setPicked({ id, name })} />
          ) : (
            <>
              <ErrorNotice message={loadError} onRetry={load} onDismiss={() => setLoadError("")} testId="ar-receipt-error" />
              <p className="text-fs-13" data-testid="ar-receipt-customer-name"><span className="text-kn-text-2">Pelanggan: </span><b>{customerName || "—"}</b></p>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <div>
                  <label className="field-label">Nominal diterima</label>
                  {mode === "auto"
                    ? <MoneyInput testId="ar-receipt-amount" className="field" value={amount} onChange={ketikNominal} placeholder="0" />
                    : <p className="field flex items-center tabular-nums" data-testid="ar-receipt-amount-manual">{formatCurrency(effectiveAmount)}</p>}
                  {mode === "manual" && depositUse > 0 && (
                    <p className="text-fs-12 text-kn-text-2" data-testid="ar-receipt-amount-manual-note">
                      Σ alokasi {formatCurrency(allocTotal)} − titipan {formatCurrency(depositUse)}
                    </p>
                  )}
                </div>
                <div>
                  <label className="field-label">Tanggal terima</label>
                  <KNDatePicker data-testid="ar-receipt-date" value={date} onChange={setDate} clearable={false} />
                </div>
                <div>
                  <label className="field-label">Cara bayar</label>
                  <KNSelect data-testid="ar-receipt-method" className="field" value={method} onValueChange={setMethod} options={methodOptions} />
                </div>
              </div>
              {titipan ? (
                <p className="notice-bar warning text-fs-12" data-testid="ar-receipt-cash-hint">
                  <Wallet size={13} className="shrink-0" aria-hidden="true" />{cashHint}
                </p>
              ) : <p className="text-fs-12 text-kn-text-2" data-testid="ar-receipt-cash-hint">{cashHint}</p>}
              {(needsAccount || titipan) && (
                <ReceiptPaymentFields entityId={selectedEntity} method={method} methodRow={methodRow} titipan={titipan}
                  orders={allocatedOrders} refRequired={refRequired} value={pay} onChange={setPay} onState={setPayState} />
              )}
              {deposit > 0 && !cashOnly && (   // LB-T8 R16: pesanan tertahan bayar + non-pemutus = HANYA tunai baru tanpa titipan (server 409 bila titipan dipakai)
                <div className="rounded-md border border-kn-divider bg-kn-success-soft px-3 py-2" data-testid="ar-receipt-deposit-box">
                  <label className="flex cursor-pointer items-center gap-2 text-fs-12 font-semibold text-kn-success-text">
                    <input type="checkbox" data-testid="ar-receipt-use-deposit" checked={useDeposit}
                      onChange={(e) => { setUseDeposit(e.target.checked); if (e.target.checked && !depositAmt) setDepositAmt(String(deposit)); }} />
                    Pakai titipan (tersedia {formatCurrency(deposit)})
                  </label>
                  {useDeposit && (
                    <MoneyInput testId="ar-receipt-deposit-amount" className="field mt-2" value={depositAmt} placeholder="0"
                      onChange={(v) => setDepositAmt(String(Math.min(Math.max(heldMoney(v) || 0, 0), deposit)))} />
                  )}
                </div>
              )}
              <div>
                <label className="field-label">Alokasi ke tagihan</label>
                <FilterChips testId="ar-receipt-mode" ariaLabel="Alokasi ke tagihan" value={mode} onChange={setMode}
                  options={ALOKASI} chipTestId={(k) => `ar-receipt-mode-${k}`} />
                {mode === "auto" && <p className="mt-1 text-fs-12 text-kn-text-2">Dialokasikan ke tagihan terbuka tertua lebih dulu.</p>}
              </div>
              <div className="overflow-hidden rounded-md border border-kn-divider">
                <div className="flex justify-between border-b border-kn-divider bg-kn-neutral-soft px-3 py-1.5 text-fs-12 font-semibold text-kn-text-2">
                  <span>Tagihan terbuka</span><span>{openOrders.length} pesanan</span>
                </div>
                {loading ? (
                  <div className="py-6 text-center text-fs-12 text-kn-text-2" data-testid="ar-receipt-loading">Memuat…</div>
                ) : openOrders.length === 0 ? (
                  <div className="py-6 text-center text-fs-12 text-kn-text-2" data-testid="ar-receipt-no-orders">Belum ada tagihan terbuka.</div>
                ) : (
                  <div className="max-h-[240px] divide-y divide-kn-divider overflow-y-auto">
                    {openOrders.map((o) => (
                      <div key={o.order_id} data-testid={`ar-receipt-order-${o.order_id}`} className="flex items-center gap-2 px-3 py-2 text-fs-12">
                        <div className="min-w-0 flex-1">
                          <p className="font-semibold text-kn-action">
                            {o.number}
                            {preselectOrderId && o.order_id === preselectOrderId && (
                              <span className="status-pill status-shipped ml-1" data-testid="ar-receipt-order-focus">dibuka</span>
                            )}
                          </p>
                          <p className="tabular-nums text-kn-text-2">Belum lunas {formatCurrency(o.outstanding)}</p>
                          {Number(o.due_now) > 0 && Number(o.due_now) < Number(o.outstanding) - 0.005 && (
                            <p className="tabular-nums font-semibold text-kn-warning-text" data-testid={`ar-receipt-due-now-${o.order_id}`}>
                              Ditagih sekarang (uang muka) {formatCurrency(o.due_now)}
                            </p>
                          )}
                          {(o.receiving_account?.account_number || o.payment_code) && (
                            <p className="text-kn-text-2" data-testid={`ar-receipt-instruction-${o.order_id}`}>
                              {o.receiving_account?.account_number
                                ? `Instruksi: ${o.receiving_account.bank_name || ""} ${o.receiving_account.account_number}`.trim() : "Instruksi bayar"}
                              {o.payment_code ? ` · kode ${o.payment_code}` : ""}
                            </p>
                          )}
                        </div>
                        {mode === "manual" ? (
                          <MoneyInput testId={`ar-receipt-alloc-${o.order_id}`} className="field w-36" value={alloc[o.order_id] ?? ""}
                            placeholder="0" aria-label={`Alokasi ke ${o.number}`} onChange={(v) => setAllocFor(o.order_id, v, o.outstanding)} />
                        ) : (
                          <span className="whitespace-nowrap tabular-nums text-kn-text-2">{formatCurrency(o.outstanding)}</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div>
                <label className="field-label">Catatan</label>
                <input data-testid="ar-receipt-notes" className="field" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Opsional" />
              </div>
              {assessment && totalFunds > 0 && (
                <div data-testid="ar-receipt-variance-hint"
                  className={`flex items-start gap-2 rounded-md px-3 py-2 ${assessment.needs_decision ? "notice-bar warning" : "bg-kn-neutral-soft"}`}>
                  <Scale size={14} className="mt-0.5 shrink-0 text-kn-text-2" aria-hidden="true" />
                  <div className="min-w-0 flex-1 text-fs-12">
                    {assessment.needs_decision ? (
                      <p className="font-semibold">
                        {Number(assessment.delta) < 0 ? "Kurang" : "Lebih"} bayar{" "}
                        <b className="tabular-nums">{formatCurrency(Math.abs(Number(assessment.delta || 0)))}</b>{" "}
                        dari {assessment.boundary_label || "tagihan jatuh tempo"} ({formatCurrency(assessment.boundary ?? assessment.expected)}) — akan diminta keputusan saat disimpan.
                      </p>
                    ) : assessment.direction === "rounding" ? (
                      <p>Selisih {formatCurrency(Math.abs(Number(assessment.delta || 0)))} masih di dalam toleransi {formatCurrency(assessment.tolerance)} — diselesaikan otomatis sebagai pembulatan (tetap tercatat).</p>
                    ) : (
                      <p className="text-kn-success-text">Nominal sesuai tagihan — tidak ada selisih yang perlu diputuskan.</p>
                    )}
                    {variance && (
                      <p className="mt-0.5 font-semibold text-kn-action" data-testid="ar-receipt-variance-chosen">
                        Keputusan dipilih: {variance.kind} · alasan {variance.reason_code}{" · "}
                        <button type="button" className="link-button" onClick={() => setShowVariance(true)}>ubah</button>
                      </p>
                    )}
                    {assessing && <p className="text-kn-text-2">menghitung selisih…</p>}
                  </div>
                  {assessment.needs_decision && !variance && (
                    <button type="button" className="secondary-button btn-sm shrink-0 whitespace-nowrap" data-testid="ar-receipt-variance-open"
                      onClick={() => setShowVariance(true)}>Putuskan</button>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </FormModal>
      {showVariance && assessment && (
        <PaymentVarianceDialog assessment={assessment} reasons={reasons} busy={busy}
          error="" submitLabel="Lanjutkan & simpan kwitansi"
          onCancel={() => setShowVariance(false)}
          onConfirm={(payload) => { setVariance(payload); setShowVariance(false); submit(payload); }} />
      )}
    </>
  );
}
