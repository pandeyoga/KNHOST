/** CampaignCostsModal — COMM-04: realisasi biaya kampanye (jurnal Beban Pemasaran) + anggaran vs realisasi. */
import { useEffect, useState } from "react";
import { Wallet, Ban } from "lucide-react";
import FormModal from "../../components/FormModal";
import { Field } from "../rnd/RndField";
import KNSelect from "../../components/KNSelect";
import KNDatePicker from "../../components/KNDatePicker";
import { mktApi, fmtN } from "./marketingShared";
import useIntentKey from "../../hooks/useIntentKey";
import CampaignBillsSection, { BillForm, RejectModal } from "./CampaignBillsSection";

const errText = (e, fb) => { const d = e.response?.data?.detail; return (typeof d === "string" ? d : d?.message) || fb; };
const today = () => new Date().toISOString().slice(0, 10);

export default function CampaignCostsModal({ campaign, canPost, canVoid = canPost, canCreateBill, canApproveBill, currentUserId, onClose, onChanged }) {
  const [data, setData] = useState(null);
  const [f, setF] = useState({ date: today(), description: "", amount: "", cash_type: "kas_besar", vendor_name: "" });
  const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const [voiding, setVoiding] = useState(null);
  const [addingBill, setAddingBill] = useState(false);
  const [rejecting, setRejecting] = useState(null);
  const refresh = () => { load(); onChanged(); };
  const intent = useIntentKey("mcc");
  const load = () => mktApi.costs(campaign.id).then(setData).catch((e) => setErr(errText(e, "Gagal memuat biaya.")));
  useEffect(() => { load(); }, [campaign.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));
  const submit = async () => {
    setBusy(true); setErr("");
    try { const body = { ...f, amount: Number(f.amount || 0) }; await intent.send(body, (k) => mktApi.recordCost(campaign.id, body, k)); setF((s) => ({ ...s, description: "", amount: "", vendor_name: "" })); await load(); onChanged(); }
    catch (e) { setErr(errText(e, "Gagal mencatat biaya.")); } finally { setBusy(false); }
  };
  return (
    <>
    <FormModal open title={`Biaya kampanye · ${campaign.name}`} subtitle="Biaya dijurnal saat uang keluar: Dr Beban Pemasaran / Cr Kas-Bank. Anggaran tidak dijurnal." icon={Wallet}
      onClose={onClose} onSubmit={canPost ? submit : undefined} busy={busy} error={err} submitLabel="Catat & posting biaya" testId="mkt-costs-modal" submitTestId="mkt-cost-submit" cancelTestId="mkt-costs-close">
      <div className="grid gap-3">
        <BudgetSummary data={data} />
        {canPost && <CostForm f={f} set={set} />}
        <CostList rows={data?.costs || []} canVoid={canVoid} onVoid={setVoiding} />
        <CampaignBillsSection campaign={campaign} bills={data?.bills || []} canCreate={canCreateBill} canApprove={canApproveBill} currentUserId={currentUserId} onChanged={refresh} onAdd={() => setAddingBill(true)} onReject={setRejecting} />
      </div>
    </FormModal>
    {addingBill && <BillForm campaign={campaign} onClose={() => setAddingBill(false)} onDone={() => { setAddingBill(false); refresh(); }} />}
    {rejecting && <RejectModal campaign={campaign} bill={rejecting} onClose={() => setRejecting(null)} onDone={() => { setRejecting(null); refresh(); }} />}
    {voiding && <VoidCostModal campaignId={campaign.id} cost={voiding} onClose={() => setVoiding(null)} onDone={() => { setVoiding(null); load(); onChanged(); }} />}
    </>
  );
}

function BudgetSummary({ data }) {
  if (!data) return <p className="text-[11px] text-[#8E8E93]">Memuat…</p>;
  const cells = [["Anggaran", data.budget, "mkt-cost-budget"], ["Realisasi", data.realized, "mkt-cost-realized"], ["Sisa anggaran", data.remaining, "mkt-cost-remaining"]];
  return (
    <div className="grid gap-1">
    <div className="grid grid-cols-3 gap-2" data-testid="mkt-cost-summary">
      {cells.map(([l, v, t]) => (
        <div key={t} className={`rounded-lg p-2 ${t === "mkt-cost-remaining" && data.over_budget ? "bg-[#FDECEC]" : "bg-[#FAFBFC]"}`}>
          <p className="text-[9.5px] font-bold uppercase tracking-wide text-[#8E8E93]">{l}</p>
          <p className={`text-[13px] font-bold ${t === "mkt-cost-remaining" && data.over_budget ? "text-[#C0392B]" : ""}`} data-testid={t}>Rp {fmtN(v)}</p>
        </div>
      ))}
    </div>
    <p className="text-[10.5px] text-[#6B6B73]" data-testid="mkt-cost-breakdown">Kas langsung Rp {fmtN(data.realized_direct)} · tagihan vendor disetujui Rp {fmtN(data.realized_bills)}{data.pending_bills ? ` · menunggu persetujuan Rp ${fmtN(data.pending_bills)} (belum dihitung)` : ""}</p>
    </div>
  );
}

function CostForm({ f, set }) {
  return (
    <div className="grid gap-2 rounded-xl border border-[#EFF0F2] p-3 sm:grid-cols-2" data-testid="mkt-cost-form">
      <Field label="Tanggal keluar *"><KNDatePicker value={f.date} onChange={(v) => set("date", v)} clearable={false} data-testid="mkt-cost-date" /></Field>
      <Field label="Nominal (Rp) *"><input type="number" min="0" className="field w-full" value={f.amount} onChange={(e) => set("amount", e.target.value)} data-testid="mkt-cost-amount" /></Field>
      <Field label="Uraian *"><input className="field w-full" value={f.description} onChange={(e) => set("description", e.target.value)} placeholder="mis. Iklan Instagram minggu 1" data-testid="mkt-cost-description" /></Field>
      <Field label="Vendor / penerima"><input className="field w-full" value={f.vendor_name} onChange={(e) => set("vendor_name", e.target.value)} data-testid="mkt-cost-vendor" /></Field>
      <Field label="Dibayar dari"><KNSelect className="field w-full" value={f.cash_type} onValueChange={(v) => set("cash_type", v)} data-testid="mkt-cost-cash-type" options={[{ value: "kas_besar", label: "Kas Besar / Bank" }, { value: "kas_kecil", label: "Kas Kecil" }]} /></Field>
    </div>
  );
}

function CostList({ rows, canVoid, onVoid }) {
  if (!rows.length) return <p className="rounded-xl border border-dashed border-[#D9D9DE] p-4 text-center text-[12px] text-[#9A9BA3]" data-testid="mkt-costs-empty">Belum ada realisasi biaya.</p>;
  return (
    <div className="grid gap-1.5" data-testid="mkt-costs-list">
      {rows.map((c) => (
        <div key={c.id} className={`flex items-center justify-between gap-2 rounded-lg border border-[#EFF0F2] p-2 text-[11.5px] ${c.status === "void" ? "opacity-60" : ""}`} data-testid={`mkt-cost-row-${c.id}`}>
          <div className="min-w-0">
            <p className="truncate font-bold">{c.number} · {c.description}</p>
            <p className="text-[10.5px] text-[#6B6B73]">{c.date} · {c.cash_type === "kas_kecil" ? "Kas Kecil" : "Kas Besar/Bank"}{c.vendor_name ? ` · ${c.vendor_name}` : ""} · JE {c.journal_entry_number || "—"}{c.status === "void" ? ` · batal (pembalik ${c.void_journal_entry_number || "—"}): ${c.void_reason}` : ""}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <span className={`font-bold ${c.status === "void" ? "line-through" : ""}`} data-testid={`mkt-cost-amount-${c.id}`}>Rp {fmtN(c.amount)}</span>
            {canVoid && c.status === "posted" && <button type="button" className="secondary-button !py-0.5 text-[10.5px]" onClick={() => onVoid(c)} data-testid={`mkt-cost-void-${c.id}`}><Ban size={11} /> Batalkan</button>}
          </div>
        </div>
      ))}
    </div>
  );
}

function VoidCostModal({ campaignId, cost, onClose, onDone }) {
  const [reason, setReason] = useState(""); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const submit = async () => {
    setBusy(true); setErr("");
    try { await mktApi.voidCost(campaignId, cost.id, { reason }); onDone(); }
    catch (e) { setErr(errText(e, "Gagal membatalkan biaya.")); } finally { setBusy(false); }
  };
  return (
    <FormModal open title={`Batalkan ${cost.number}`} subtitle="Jurnal pembalik dibuat di periode berjalan; kas keluar ikut dibatalkan." icon={Ban}
      onClose={onClose} onSubmit={submit} busy={busy} error={err} submitLabel="Batalkan biaya" testId="mkt-cost-void-modal" submitTestId="mkt-cost-void-submit" cancelTestId="mkt-cost-void-cancel">
      <Field label="Alasan pembatalan *"><input className="field w-full" value={reason} onChange={(e) => setReason(e.target.value)} data-testid="mkt-cost-void-reason" /></Field>
    </FormModal>
  );
}
