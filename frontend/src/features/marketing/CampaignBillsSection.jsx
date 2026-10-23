/** CampaignBillsSection — tagihan vendor kampanye tanpa PO: dibuat Marketing/Admin, disetujui Finance/Manager. */
import { useEffect, useState } from "react";
import { Check, X, Plus } from "lucide-react";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import KNDatePicker from "../../components/KNDatePicker";
import { Field } from "../rnd/RndField";
import { mktApi, fmtN } from "./marketingShared";
import useIntentKey from "../../hooks/useIntentKey";
import { todayWib } from "../../utils/formatters";

const errText = (e, fb) => { const d = e.response?.data?.detail; return (typeof d === "string" ? d : d?.message) || fb; };
const today = () => todayWib();
const STATUS = { pending_approval: ["Menunggu persetujuan", "bg-[#FFF6E5] text-[#B26A00]"], posted: ["Disetujui · belum dibayar", "bg-[#EEF4FF] text-[#0058CC]"], paid: ["Lunas", "bg-[#E7F6F3] text-[#0F766E]"], cancelled: ["Ditolak/batal", "bg-[#F2F2F7] text-[#6B6B73]"] };

export default function CampaignBillsSection({ campaign, bills, canCreate, canApprove, currentUserId, onChanged, onAdd, onReject }) {
  const [err, setErr] = useState("");
  const approve = async (b) => {
    setErr("");
    try { await mktApi.approveBill(campaign.id, b.id); onChanged(); } catch (e) { setErr(errText(e, "Gagal menyetujui tagihan.")); }
  };
  return (
    <div className="grid gap-1.5" data-testid="mkt-bills-section">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Tagihan vendor (tanpa PO)</p>
        {canCreate && <button type="button" className="secondary-button !py-0.5 text-[10.5px]" onClick={onAdd} data-testid="mkt-bill-add"><Plus size={11} /> Tagihan vendor</button>}
      </div>
      {err && <p className="text-[11px] text-[#C0392B]" data-testid="mkt-bill-error">{err}</p>}
      {!bills.length && <p className="text-[11px] text-[#9A9BA3]" data-testid="mkt-bills-empty">Belum ada tagihan vendor.</p>}
      {bills.map((b) => {
        const [label, cls] = STATUS[b.status] || [b.status, ""];
        const mine = b.created_by_id && b.created_by_id === currentUserId;
        return (
          <div key={b.id} className="flex items-center justify-between gap-2 rounded-lg border border-[#EFF0F2] p-2 text-[11.5px]" data-testid={`mkt-bill-row-${b.id}`}>
            <div className="min-w-0">
              <p className="truncate font-bold">{b.bill_number} · {b.supplier_name}{b.supplier_invoice_no ? ` · inv ${b.supplier_invoice_no}` : ""}</p>
              <p className="text-[10.5px] text-[#6B6B73]">{b.notes} · <span className={`rounded-full px-1.5 py-0.5 text-[9.5px] font-semibold ${cls}`} data-testid={`mkt-bill-status-${b.id}`}>{label}</span>{b.status === "posted" ? " · bayar di menu Hutang Supplier" : ""}{b.rejection_reason ? ` · ${b.rejection_reason}` : ""}</p>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <span className="font-bold" data-testid={`mkt-bill-amount-${b.id}`}>Rp {fmtN(b.grand_total)}</span>
              {canApprove && b.status === "pending_approval" && !mine && (<>
                <button type="button" className="secondary-button !py-0.5 text-[10.5px]" onClick={() => approve(b)} data-testid={`mkt-bill-approve-${b.id}`}><Check size={11} /> Setujui</button>
                <button type="button" className="secondary-button !py-0.5 text-[10.5px]" onClick={() => onReject(b)} data-testid={`mkt-bill-reject-${b.id}`}><X size={11} /> Tolak</button>
              </>)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function BillForm({ campaign, onClose, onDone }) {
  const [vendors, setVendors] = useState([]);
  const [f, setF] = useState({ supplier_id: "", supplier_invoice_no: "", bill_date: today(), due_date: "", description: "", amount: "", ppn_amount: "" });
  const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const intent = useIntentKey("mvb");
  useEffect(() => { mktApi.vendorOptions().then(setVendors).catch(() => setVendors([])); }, []);
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));
  const submit = async () => {
    setBusy(true); setErr("");
    const body = { ...f, amount: Number(f.amount || 0), ppn_amount: Number(f.ppn_amount || 0) };
    try { await intent.send(body, (k) => mktApi.createBill(campaign.id, body, k)); onDone(); }
    catch (e) { setErr(errText(e, "Gagal membuat tagihan.")); } finally { setBusy(false); }
  };
  return (
    <FormModal open title="Tagihan vendor kampanye" subtitle="Belum dijurnal sampai disetujui Finance/Manager: Dr Beban Pemasaran / Cr Hutang Usaha." icon={Plus}
      onClose={onClose} onSubmit={submit} busy={busy} error={err} submitLabel="Ajukan tagihan" testId="mkt-bill-modal" submitTestId="mkt-bill-submit" cancelTestId="mkt-bill-cancel">
      <div className="grid gap-2 sm:grid-cols-2">
        <Field label="Vendor *"><KNSelect className="field w-full" value={f.supplier_id} onValueChange={(v) => set("supplier_id", v)} placeholder="Pilih vendor" data-testid="mkt-bill-vendor" options={vendors.map((v) => ({ value: v.id, label: v.name }))} /></Field>
        <Field label="No. invoice vendor"><input className="field w-full" value={f.supplier_invoice_no} onChange={(e) => set("supplier_invoice_no", e.target.value)} data-testid="mkt-bill-invoice" /></Field>
        <Field label="Uraian *"><input className="field w-full" value={f.description} onChange={(e) => set("description", e.target.value)} placeholder="mis. Iklan Meta Oktober" data-testid="mkt-bill-description" /></Field>
        <Field label="Nominal sebelum PPN (Rp) *"><input type="number" min="0" className="field w-full" value={f.amount} onChange={(e) => set("amount", e.target.value)} data-testid="mkt-bill-amount" /></Field>
        <Field label="PPN Masukan (Rp)"><input type="number" min="0" className="field w-full" value={f.ppn_amount} onChange={(e) => set("ppn_amount", e.target.value)} data-testid="mkt-bill-ppn" /></Field>
        <Field label="Tanggal tagihan"><KNDatePicker value={f.bill_date} onChange={(v) => set("bill_date", v)} clearable={false} data-testid="mkt-bill-date" /></Field>
        <Field label="Jatuh tempo"><KNDatePicker value={f.due_date} onChange={(v) => set("due_date", v)} data-testid="mkt-bill-due" /></Field>
      </div>
    </FormModal>
  );
}

export function RejectModal({ campaign, bill, onClose, onDone }) {
  const [reason, setReason] = useState(""); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const submit = async () => {
    setBusy(true); setErr("");
    try { await mktApi.rejectBill(campaign.id, bill.id, { reason }); onDone(); } catch (e) { setErr(errText(e, "Gagal menolak tagihan.")); } finally { setBusy(false); }
  };
  return (
    <FormModal open title={`Tolak ${bill.bill_number}`} icon={X} onClose={onClose} onSubmit={submit} busy={busy} error={err} submitLabel="Tolak tagihan" testId="mkt-bill-reject-modal" submitTestId="mkt-bill-reject-submit" cancelTestId="mkt-bill-reject-cancel">
      <Field label="Alasan penolakan * (min. 5 karakter)"><input className="field w-full" value={reason} onChange={(e) => setReason(e.target.value)} data-testid="mkt-bill-reject-reason" /></Field>
      {reason.trim().length > 0 && reason.trim().length < 5 && <p className="text-[11px] text-[#B26A00]" data-testid="mkt-bill-reject-hint">Alasan minimal 5 karakter.</p>}
    </FormModal>
  );
}
