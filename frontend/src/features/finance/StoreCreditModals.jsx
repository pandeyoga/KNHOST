/**
 * Pop-up Store Credit — Pakai saldo, Sesuaikan saldo, Batalkan entri (dipakai StoreCreditView).
 *
 * Fase 4 · R2 (L-03) — diekstrak dari `StoreCreditView.jsx`; cangkang `Modal` buatan sendiri (`div fixed inset-0
 * z-[120]`, tanpa Esc/klik latar) → `FormModal` baku (Esc lewat tumpukan lapisan, klik latar gestur utuh, layar penuh
 * di HP). Isian, teks & testid tetap (`sc-*-modal`, `sc-*-modal-close`, `sc-*-cancel`, `sc-*-submit`, `sc-*-error`);
 * galat tetap di DALAM pop-up. Pilihan Tambah/Kurangi kini `aria-pressed` (saklar), aksen ungu → biru baku.
 */
import { useEffect, useState } from "react";
import {
  AlertTriangle, ArrowDownCircle, CheckCircle2, Loader2, Minus, Plus, RotateCcw, TicketPercent,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import MoneyInput from "../../components/MoneyInput";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency } from "../../utils/formatters";

function ErrBox({ testId, children }) {
  return (
    <div role="alert" className="flex items-center gap-1.5 rounded-md bg-[#FCEBEA] px-3 py-2 text-[12px] text-[#C0392B]" data-testid={testId}>
      <AlertTriangle size={13} className="shrink-0" /> {children}
    </div>
  );
}

function Footer({ prefix, onClose, onSubmit, busy, disabled, danger = false, icon: Icon, label }) {
  return (
    <div className="flex items-center justify-end gap-2">
      <button type="button" className="secondary-button" onClick={onClose} disabled={busy} data-testid={`${prefix}-cancel`}>Batal</button>
      <button type="button" className={danger ? "danger-button" : "primary-button"} onClick={onSubmit} disabled={busy || disabled}
        data-testid={`${prefix}-submit`}>
        {busy ? <Loader2 size={14} className="animate-spin" /> : <Icon size={14} />} {label}
      </button>
    </div>
  );
}

export function RedeemModal({ row, onClose, onDone }) {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [amount, setAmount] = useState("");
  const [orderId, setOrderId] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await axios.get(`${API}/store-credit/open-orders`, { params: { customer_id: row.customer_id } });
        const list = Array.isArray(res.data) ? res.data : [];
        setOrders(list);
        if (list.length) { setOrderId(list[0].order_id); }
      } catch (e) { setErr(apiErrorText(e, "Gagal memuat order AR.")); }
      finally { setLoading(false); }
    })();
  }, [row.customer_id]);

  const target = orders.find((o) => o.order_id === orderId);
  const maxRedeem = Math.min(row.balance || 0, target?.outstanding || 0);

  const submit = async () => {
    setErr(""); setOk("");
    const amt = Math.round(parseFloat(amount || "0"));
    if (!amt || amt <= 0) { setErr("Masukkan jumlah > 0."); return; }
    if (amt > (row.balance || 0) + 0.5) { setErr("Melebihi saldo store credit."); return; }
    setBusy(true);
    try {
      const body = { customer_id: row.customer_id, entity_id: row.entity_id || undefined, amount: amt };
      if (orderId) body.allocations = [{ order_id: orderId, amount: amt }];
      const res = await axios.post(`${API}/store-credit/redeem`, body);
      setOk(`Berhasil dipakai ${formatCurrency(res.data?.applied_amount)} (${res.data?.number}).`);
      setTimeout(onDone, 900);
    } catch (e) { setErr(apiErrorText(e, "Gagal memakai store credit.")); }
    finally { setBusy(false); }
  };

  return (
    <FormModal open onClose={onClose} size="sm" icon={ArrowDownCircle} testId="sc-redeem-modal" busy={busy}
      title={`Pakai Store Credit — ${row.customer_name || ""}`}
      footer={<Footer prefix="sc-redeem" onClose={onClose} onSubmit={submit} busy={busy} disabled={orders.length === 0}
        icon={ArrowDownCircle} label="Pakai Saldo" />}>
      <div className="space-y-3">
        <div className="rounded-md bg-[#EFF4FF] px-3 py-2 text-[12px]">Saldo tersedia: <b className="tabular-nums text-[#0058CC]" data-testid="sc-redeem-balance">{formatCurrency(row.balance)}</b></div>
        {err && <ErrBox testId="sc-redeem-error">{err}</ErrBox>}
        {ok && <div className="flex items-center gap-1.5 rounded-md bg-[#E6F6EC] px-3 py-2 text-[12px] text-[#1B7F4B]" data-testid="sc-redeem-ok"><CheckCircle2 size={13} /> {ok}</div>}
        <div>
          <label className="text-[11px] font-semibold text-[#6B6B73]">Pesanan piutang tujuan</label>
          {loading ? <div className="h-9 bg-[#F5F5F7] rounded animate-pulse mt-1" /> : orders.length === 0 ? (
            <div className="mt-1 rounded-md border border-dashed border-[#E5E5EA] p-3 text-[12px] text-[#8E8E93]" data-testid="sc-redeem-no-orders">Tidak ada pesanan piutang terbuka untuk pelanggan ini.</div>
          ) : (
            <KNSelect data-testid="sc-redeem-order" className="field w-full mt-1" value={orderId}
              onValueChange={setOrderId} aria-label="Pesanan untuk penukaran store credit"
              options={orders.map((o) => ({
                value: o.order_id,
                // "outstanding" (Inggris) sebelumnya lolos audit bahasa karena terpotong
                // antar-ekspresi JSX; setelah jadi satu template literal, gate
                // `audit_i18n_id` langsung menangkapnya. Diterjemahkan.
                label: `${o.number} — belum lunas ${formatCurrency(o.outstanding)}`,
              }))} />
          )}
        </div>
        <div>
          <label className="text-[11px] font-semibold text-[#6B6B73]">Jumlah dipakai</label>
          <div className="flex items-center gap-2 mt-1">
            <div className="w-full"><MoneyInput testId="sc-redeem-amount" className="field w-full" placeholder="0" value={amount} onChange={setAmount} /></div>
            <button data-testid="sc-redeem-max" type="button" className="secondary-button py-1.5 px-2 text-[11px] whitespace-nowrap" onClick={() => setAmount(String(Math.round(maxRedeem)))} disabled={maxRedeem <= 0}>Maks</button>
          </div>
          {target && <p className="text-[10.5px] text-[#9A9BA3] mt-1">Maks utk pesanan ini: {formatCurrency(maxRedeem)}</p>}
        </div>
      </div>
    </FormModal>
  );
}

export function AdjustModal({ row, onClose, onDone }) {
  const [dir, setDir] = useState("plus");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    setErr("");
    const amt = Math.round(parseFloat(amount || "0"));
    if (!amt || amt <= 0) { setErr("Masukkan jumlah > 0."); return; }
    const signed = dir === "plus" ? amt : -amt;
    setBusy(true);
    try {
      await axios.post(`${API}/store-credit/adjust`, {
        customer_id: row.customer_id, entity_id: row.entity_id || undefined, amount: signed, note,
      });
      setTimeout(onDone, 400);
    } catch (e) { setErr(apiErrorText(e, "Gagal menyesuaikan saldo.")); setBusy(false); }
  };

  const dirCls = (on, tone) => `flex-1 rounded-md border py-2 text-[12px] font-semibold flex items-center justify-center gap-1 ${on ? tone : "border-[#EFF0F2] text-[#6B6B73]"}`;
  return (
    <FormModal open onClose={onClose} size="sm" icon={TicketPercent} testId="sc-adjust-modal" busy={busy}
      title={`Sesuaikan Saldo — ${row.customer_name || ""}`}
      footer={<Footer prefix="sc-adjust" onClose={onClose} onSubmit={submit} busy={busy} icon={TicketPercent} label="Simpan" />}>
      <div className="space-y-3">
        {err && <ErrBox testId="sc-adjust-error">{err}</ErrBox>}
        <div className="flex gap-2" role="group" aria-label="Arah penyesuaian">
          <button type="button" data-testid="sc-adjust-plus" aria-pressed={dir === "plus"} className={dirCls(dir === "plus", "border-[#1B7F4B] bg-[#E6F6EC] text-[#1B7F4B]")} onClick={() => setDir("plus")}><Plus size={13} /> Tambah</button>
          <button type="button" data-testid="sc-adjust-minus" aria-pressed={dir === "minus"} className={dirCls(dir === "minus", "border-[#C0392B] bg-[#FCEBEA] text-[#C0392B]")} onClick={() => setDir("minus")}><Minus size={13} /> Kurangi</button>
        </div>
        <div>
          <label className="text-[11px] font-semibold text-[#6B6B73]">Jumlah</label>
          <MoneyInput testId="sc-adjust-amount" className="field w-full mt-1" placeholder="0" value={amount} onChange={setAmount} />
        </div>
        <div>
          <label className="text-[11px] font-semibold text-[#6B6B73]">Alasan / catatan</label>
          <input data-testid="sc-adjust-note" className="field w-full mt-1" placeholder="mis. koreksi, kompensasi, kadaluarsa..." value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
      </div>
    </FormModal>
  );
}

export function ReverseModal({ entry, typeLabel, onClose, onDone }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const isRedeem = entry.type === "redeem";

  const submit = async () => {
    setErr("");
    setBusy(true);
    try {
      await axios.post(`${API}/store-credit/entries/${entry.id}/reverse`, { reason });
      setTimeout(onDone, 400);
    } catch (e) {
      setErr(apiErrorText(e, "Gagal membatalkan entri store credit."));
      setBusy(false);
    }
  };

  return (
    <FormModal open onClose={onClose} size="sm" icon={RotateCcw} testId="sc-reverse-modal" busy={busy}
      title="Batalkan / Balikkan Store Credit"
      footer={<Footer prefix="sc-reverse" onClose={onClose} onSubmit={submit} busy={busy} danger icon={RotateCcw} label="Batalkan Entri" />}>
      <div className="space-y-3">
        {err && <ErrBox testId="sc-reverse-error">{err}</ErrBox>}
        <div className="rounded-md bg-[#FFF4E5] px-3 py-2 text-[12px] text-[#8C4A00]">
          {isRedeem
            ? "Membatalkan pemakaian ini akan mengembalikan saldo store credit dan outstanding order terkait, serta membalik jurnalnya."
            : "Membatalkan penyesuaian ini akan membalik jurnal dan mengembalikan saldo. Ditolak bila membuat saldo negatif."}
        </div>
        <div className="rounded-md border border-[#EFF0F2] px-3 py-2 text-[12px]">
          <div className="flex justify-between gap-2"><span className="text-[#8E8E93]">Jenis</span><b>{typeLabel || entry.type}</b></div>
          <div className="flex justify-between gap-2"><span className="text-[#8E8E93]">Referensi</span><b>{entry.ref_number || "—"}</b></div>
          <div className="flex justify-between gap-2"><span className="text-[#8E8E93]">Nilai</span><b className="tabular-nums">{formatCurrency(entry.amount)}</b></div>
        </div>
        <div>
          <label className="text-[11px] font-semibold text-[#6B6B73]">Alasan pembatalan</label>
          <input data-testid="sc-reverse-reason" className="field w-full mt-1" placeholder="mis. salah input, dobel, koreksi..." value={reason} onChange={(e) => setReason(e.target.value)} />
        </div>
      </div>
    </FormModal>
  );
}
