import { useState } from "react";
import { HandCoins, Undo2 } from "lucide-react";
import { API } from "../../services/apiClient";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import KNDatePicker from "@/components/KNDatePicker";
import CashAccountField, { cashAccountBlocked, cashAccountBlockReason, cashAccountLabel } from "../../components/CashAccountField";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyPost } from "../../utils/moneyRequest";
import { confirmMoney, rupiahText } from "../../utils/moneyConfirm";
import { entityFullById } from "../../utils/entityLabel";
import { apiErrorText } from "../../utils/apiError";
import { todayWib } from "../../utils/formatters";

/**
 * SettlementCashModal (PK-24 · SL-09, IA-05) — satu pop-up baku untuk dua aksi kas atas LPJ:
 *
 *  · `mode="return"`    — **Terima Pengembalian Sisa**: kas MASUK sisa uang muka dari karyawan
 *                          (`POST /cash-advance-settlements/{id}/return-remainder`, izin `cash_settlement.pay`).
 *  · `mode="reimburse"` — **Bayar Reimburse**: kas KELUAR melunasi kelebihan pengeluaran karyawan
 *                          (`POST /cash-advance-settlements/{id}/pay-reimburse`, izin `cash_settlement.pay`).
 *
 * Isian: Jenis kas · Rekening (`CashAccountField`, rekening tunggal PT terisi otomatis) · Tanggal. Simpan meminta
 * konfirmasi yang menyebut nominal, karyawan, rekening, dan PT (`02` N5); kirim ber-Idempotency-Key (N4). Dipakai
 * rincian LPJ (`SettlementDetail`; di panel Kas Kecil sejak MN-T2 — daftar Hutang Reimburse lama dihapus).
 *
 *   <SettlementCashModal mode="return" stl={{ id, number, entity_id, amount, employee }} entities={…}
 *     onClose={…} onDone={(lpj) => …} />
 */
const JENIS_KAS = [{ value: "kas_kecil", label: "Kas Kecil (tunai)" }, { value: "kas_besar", label: "Bank (transfer)" }];

const MODE = {
  return: {
    path: "return-remainder", icon: Undo2, intent: "stlk", testId: "stl-return-modal", confirmTestId: "stl-return-confirm",
    title: (s) => `Terima Pengembalian Sisa ${s.number}`, submit: "Terima Pengembalian", cashType: "kas_kecil",
    subtitle: (s) => `Sisa uang muka ${rupiahText(s.amount)} dari ${s.employee} masuk ke kas; uang muka LPJ ini menjadi nol.`,
  },
  reimburse: {
    path: "pay-reimburse", icon: HandCoins, intent: "stlp", testId: "stl-reimburse-modal",
    confirmTestId: "stl-reimburse-confirm", title: (s) => `Bayar Reimburse ${s.number}`, submit: "Bayar Reimburse",
    cashType: "kas_besar",
    subtitle: (s) => `Kelebihan pengeluaran ${rupiahText(s.amount)} dibayar ke ${s.employee}.`,
  },
};

export default function SettlementCashModal({ mode, stl, entities = [], onClose, onDone }) {
  const m = MODE[mode];
  const [cashType, setCashType] = useState(m.cashType);
  const [accountId, setAccountId] = useState("");
  const [accState, setAccState] = useState("memuat");
  const [account, setAccount] = useState(null);
  const [tanggal, setTanggal] = useState(todayWib());
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const intent = useIntentKey(m.intent);
  const blocked = cashAccountBlocked(accState, accountId);
  const karyawan = stl.employee || "karyawan";

  async function submit() {
    setErr("");
    const rekening = account ? cashAccountLabel(account) : "rekening terpilih";
    const pt = entityFullById(entities, stl.entity_id);
    const ok = mode === "return"
      ? await confirmMoney({
        title: `Terima ${rupiahText(stl.amount)} dari ${karyawan} ke ${rekening} · ${pt}?`,
        effect: "Kas masuk ke rekening ini dan uang muka karyawan pada LPJ ini menjadi nol.",
        amount: stl.amount, entityId: stl.entity_id, entities, confirmLabel: m.submit, testId: m.confirmTestId,
      })
      : await confirmMoney({
        title: `Bayar reimburse ${stl.number}?`,
        effect: `Kas keluar untuk melunasi kelebihan pengeluaran ${karyawan} dari ${rekening}.`,
        amount: stl.amount, entityId: stl.entity_id, entities, confirmLabel: m.submit, testId: m.confirmTestId,
      });
    if (!ok) return;
    const body = { cash_type: cashType, ...(accountId ? { account_id: accountId } : {}), ...(tanggal ? { txn_date: tanggal } : {}) };
    setBusy(true);
    try {
      const res = await intent.send({ id: stl.id, aksi: m.path, ...body },
        (k) => moneyPost(`${API}/cash-advance-settlements/${stl.id}/${m.path}`, body, k));
      onDone?.(res.data);
    } catch (e) {
      setErr(apiErrorText(e, mode === "return" ? "Pengembalian sisa gagal dicatat." : "Pembayaran reimburse gagal."));
    } finally { setBusy(false); }
  }

  return (
    <FormModal open onClose={onClose} size="sm" icon={m.icon} testId={m.testId} title={m.title(stl)}
      subtitle={m.subtitle({ ...stl, employee: karyawan })} busy={busy} error={err} submitLabel={m.submit}
      submitTestId={`${m.testId}-submit`} submitDisabled={blocked} onSubmit={submit}>
      <div className="grid gap-3">
        <div className="grid gap-1.5">
          <label className="text-fs-12 font-bold uppercase tracking-wide text-kn-text-2">Jenis kas</label>
          <KNSelect data-testid={`${m.testId}-cashtype`} className="field" value={cashType} onValueChange={setCashType}
            options={JENIS_KAS} />
        </div>
        <CashAccountField entityId={stl.entity_id} cashType={cashType} value={accountId} onChange={setAccountId}
          onState={setAccState} onAccount={setAccount} testId={`${m.testId}-account`} />
        <div className="grid gap-1.5">
          <label className="text-fs-12 font-bold uppercase tracking-wide text-kn-text-2">Tanggal</label>
          <KNDatePicker data-testid={`${m.testId}-date`} value={tanggal} onChange={setTanggal} clearable={false} />
        </div>
        {blocked && accState !== "kosong" && (
          <p className="text-fs-12 text-kn-text-2" data-testid={`${m.testId}-reason`}>{cashAccountBlockReason(accState)}</p>
        )}
      </div>
    </FormModal>
  );
}
