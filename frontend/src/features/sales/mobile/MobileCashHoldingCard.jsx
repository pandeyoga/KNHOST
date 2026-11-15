/**
 * MobileCashHoldingCard — PM-T4 (K-36) · kartu "Titipan Saya" di Beranda HP sales.
 *
 * Tunai yang diterima sales dicatat sebagai titipan di tangannya (bila PT memilih `pembayaran.sales_terima_tunai =
 * titipan`) sampai setorannya diterima kasir/Finance. Kartu: total dipegang, jumlah kwitansi, batas, tenggat terdekat,
 * dan tombol **Setor** → pop-up "Jumlah disetor" (terisi total yang bisa disetor) + "Catatan" → POST /api/cash-deposits
 * (kunci idempotensi, klik ganda = satu setoran) → "Setoran diajukan. Serahkan uangnya ke kasir."
 * Sumber: GET /api/cash-holdings/me/summary (milik sendiri). Kartu tidak tampil bila PT memakai kas langsung dan tidak
 * ada titipan; galat dibedakan (Coba lagi). Tombol Setor mati dengan alasan tertulis di sampingnya.
 */
import { useCallback, useEffect, useState } from "react";
import { HandCoins, Wallet } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import ErrorNotice from "../../../components/ErrorNotice";
import FormModal from "../../../components/FormModal";
import MoneyInput from "../../../components/MoneyInput";
import { apiErrorText } from "../../../utils/apiError";
import { formatCurrency, formatDateTime } from "../../../utils/formatters";
import { moneyPost } from "../../../utils/moneyRequest";
import useIntentKey from "../../../hooks/useIntentKey";
import { canCurrent } from "../../../config/roles";
import { OVERDUE_LOOK, TEKS_SEMUA_PT, TEKS_SETORAN_DIAJUKAN } from "../../finance/cashholding/cashHoldingShared";

/** Kartu ditampilkan? (PT memakai titipan, atau masih ada titipan / setoran yang menunggu). */
export function showCashHoldingCard(s) {
  if (!s) return false;
  return s.mode === "titipan" || Number(s.held_total) > 0 || Number(s.pending_total) > 0;
}

/** Alasan tombol Setor mati (ditulis di samping tombol); "" = boleh. */
export function alasanTidakBisaSetor(s, canCreate) {
  if (!s?.entity_id) return TEKS_SEMUA_PT;
  if (!canCreate) return "Mengajukan setoran butuh akses setoran titipan.";
  if (Number(s.available) <= 0) {
    return Number(s.pending_total) > 0 ? "Semua titipan sudah diajukan — tunggu kasir menerimanya."
      : "Tidak ada titipan yang bisa disetor.";
  }
  return "";
}

export default function MobileCashHoldingCard({ selectedEntity = "all", onMessage }) {
  const [s, setS] = useState(null);
  const [state, setState] = useState("loading");   // loading | ready | error
  const [err, setErr] = useState("");
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState("");
  const [msg, setMsg] = useState("");
  const intent = useIntentKey("setor-titipan");
  const canCreate = canCurrent("cash_holding", "create");

  const load = useCallback(async () => {
    setState("loading");
    try {
      const r = await axios.get(`${API}/cash-holdings/me/summary`);
      setS(r.data || null); setErr(""); setState("ready");
    } catch (e) { setErr(apiErrorText(e, "Titipan tunai tidak bisa dimuat.")); setState("error"); }
  }, []);
  useEffect(() => { load(); }, [load, selectedEntity]);

  if (state === "error") {
    return <ErrorNotice message={err} onRetry={load} testId="m-cth-error" />;
  }
  if (state !== "ready" || !showCashHoldingCard(s)) return null;

  const alasan = alasanTidakBisaSetor(s, canCreate);
  const avail = Number(s.available) || 0;
  const buka = () => { setAmount(String(avail)); setNote(""); setFormErr(""); setOpen(true); };
  const setor = async () => {
    const n = Number(amount) || 0;
    if (n <= 0) { setFormErr("Jumlah disetor harus lebih dari 0."); return; }
    if (n > avail + 0.005) { setFormErr(`Jumlah melebihi tunai yang bisa disetor (${formatCurrency(avail)}).`); return; }
    setBusy(true); setFormErr("");
    try {
      const body = { amount: n, note: note.trim() };
      await intent.send(body, (k) => moneyPost(`${API}/cash-deposits`, body, k));
      setOpen(false);
      setMsg(TEKS_SETORAN_DIAJUKAN);
      onMessage?.(TEKS_SETORAN_DIAJUKAN);
      await load();
    } catch (e) {
      setFormErr(apiErrorText(e, "Setoran gagal diajukan."));
    } finally { setBusy(false); }
  };
  const OIcon = OVERDUE_LOOK.icon;

  return (
    <div className="m-card p-4" data-testid="m-cth-card">
      <div className="flex items-center gap-2">
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-kn-warning-soft">
          <Wallet size={16} className="text-kn-warning-text" aria-hidden="true" />
        </span>
        <h3 className="text-fs-14 font-bold">Titipan Saya</h3>
        {Number(s.overdue_count) > 0 && (
          <span className={`status-pill ml-auto whitespace-nowrap ${OVERDUE_LOOK.cls}`} data-testid="m-cth-overdue">
            <OIcon size={12} aria-hidden="true" />{OVERDUE_LOOK.label} · {s.overdue_count}
          </span>
        )}
      </div>
      <p className="mt-2 text-fs-12 m-muted">Tunai dari pelanggan yang belum disetor</p>
      <p className="text-fs-24 font-bold tabular-nums" data-testid="m-cth-held">{formatCurrency(s.held_total)}</p>
      <dl className="mt-2 grid grid-cols-2 gap-2 text-fs-12">
        <div><dt className="m-muted">Kwitansi</dt><dd className="font-semibold tabular-nums" data-testid="m-cth-count">{s.count}</dd></div>
        <div><dt className="m-muted">Batas</dt><dd className="font-semibold tabular-nums" data-testid="m-cth-limit">
          {Number(s.limit) > 0 ? formatCurrency(s.limit) : "Tanpa batas"}</dd></div>
        <div className="col-span-2"><dt className="m-muted">Tenggat setor terdekat</dt><dd className="font-semibold" data-testid="m-cth-due">
          {s.oldest_due_at ? formatDateTime(s.oldest_due_at) : "Tanpa tenggat"}</dd></div>
      </dl>
      {Number(s.pending_total) > 0 && (
        <p className="mt-2 rounded-md bg-kn-action-soft px-2 py-1.5 text-fs-12 text-kn-action" data-testid="m-cth-pending">
          Sudah diajukan {formatCurrency(s.pending_total)} — serahkan uangnya ke kasir.
        </p>
      )}
      {msg && <div className="notice-bar success mt-2 text-fs-12" data-testid="m-cth-msg">{msg}</div>}
      <button type="button" className="primary-button btn-touch mt-3 w-full justify-center" disabled={Boolean(alasan)}
        onClick={buka} data-testid="m-cth-deposit">
        <HandCoins size={16} aria-hidden="true" /> Setor
      </button>
      {alasan && <p className="mt-1 text-fs-12 m-muted" data-testid="m-cth-deposit-why">{alasan}</p>}

      <FormModal open={open} onClose={() => setOpen(false)} title="Setor titipan tunai" icon={HandCoins}
        testId="m-cth-form" onSubmit={setor} submitLabel="Ajukan setoran" busy={busy} error={formErr}>
        <div className="space-y-3">
          <div>
            <label className="field-label" htmlFor="m-cth-amount">Jumlah disetor <span className="req">*</span></label>
            <MoneyInput id="m-cth-amount" testId="m-cth-form-amount" className="field kn-input-touch" value={amount}
              onChange={(v) => setAmount(v)} placeholder="0" />
            <p className="mt-1 text-fs-12 m-muted">Bisa disetor: {formatCurrency(avail)}. Titipan tertua disetor lebih dulu.</p>
          </div>
          <div>
            <label className="field-label" htmlFor="m-cth-note">Catatan</label>
            <input id="m-cth-note" data-testid="m-cth-form-note" className="field kn-input-touch" value={note}
              maxLength={500} placeholder="Contoh: diserahkan ke kasir kantor" onChange={(e) => setNote(e.target.value)} />
          </div>
        </div>
      </FormModal>
    </div>
  );
}
