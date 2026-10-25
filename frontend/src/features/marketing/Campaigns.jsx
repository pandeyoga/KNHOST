/** Campaigns — kampanye/tema konten (periode, platform, target) + ringkasan post & performa. */
import { useEffect, useState } from "react";
import apiErrorText from "../../utils/apiError";
import { Flag, Plus, Pencil, Wallet } from "lucide-react";
import CampaignCostsModal from "./CampaignCostsModal";
import CampaignBudgetChart from "./CampaignBudgetChart";
import FormModal from "../../components/FormModal";
import { Field } from "../rnd/RndField";
import KNSelect from "../../components/KNSelect";
import KNDatePicker from "../../components/KNDatePicker";
import { SearchBox } from "../../components/ListControls";
import { mktApi, PLATFORM_STYLE, fmtN, STATUS_STYLE } from "./marketingShared";
import { can } from "../../config/roles";
import { formatDate } from "../../utils/formatters";
import MoneyInput from "../../components/MoneyInput";

const COLORS = ["#0058CC", "#C13584", "#1B7F4B", "#B45309", "#6D28D9", "#C0392B", "#0F766E"];

export default function Campaigns({ currentUser }) {
  const [rows, setRows] = useState([]);
  const [editing, setEditing] = useState(null);
  const [costing, setCosting] = useState(null);
  const [q, setQ] = useState("");
  const shown = rows.filter((c) => !q.trim() || `${c.name || ""} ${c.title || ""} ${c.description || ""}`.toLowerCase().includes(q.trim().toLowerCase()));
  // Sisir gerbang peran (2026-10-20): buat = marketing.create; ubah & ajukan tagihan = marketing.update;
  // catat biaya = accounting.create; anulir biaya = accounting.void; ACC tagihan = peran Finance/Manager/Admin
  // (aturan server BILL_APPROVER_ROLES) + accounting.view atau vendor_bill.approve.
  const perms = currentUser?.permissions;
  const canCreate = can(perms, "marketing", "create");
  const canEdit = can(perms, "marketing", "update");
  const canPostCost = can(perms, "accounting", "create");
  const canVoidCost = can(perms, "accounting", "void");
  const canApproveBill = ["admin", "manager", "finance"].includes(currentUser?.role)
    && (can(perms, "accounting", "view") || can(perms, "vendor_bill", "approve"));
  const load = () => mktApi.campaigns().then(setRows).catch(() => {});
  useEffect(() => { load(); }, []);
  return (
    <div className="grid gap-3" data-testid="mkt-campaigns">
      <div className="flex items-center justify-between">
        <p className="text-[12px] text-[#6B6B73]">Kampanye mengelompokkan konten dalam satu tema & periode (mis. "Lebaran 2027", "Launching Koleksi Navy").</p>
        {canCreate && <button type="button" className="primary-button !py-1.5 text-[11px]" onClick={() => setEditing({})} data-testid="mkt-new-campaign"><Plus size={13} /> Kampanye baru</button>}
      </div>
      <SearchBox value={q} onChange={setQ} placeholder="Cari kampanye…" testId="mkt-campaigns-search" />
      {shown.length === 0 && <p className="rounded-xl border border-dashed border-[#D9D9DE] p-6 text-center text-[12px] text-[#9A9BA3]" data-testid="mkt-campaigns-empty">{q ? "Tidak ada kampanye yang cocok." : "Belum ada kampanye."}</p>}
      <CampaignBudgetChart version={rows} />
      <div className="grid gap-2 md:grid-cols-2">
        {shown.map((c) => (
          <div key={c.id} className="rounded-xl border border-[#EFF0F2] bg-white p-3" data-testid={`mkt-campaign-${c.id}`} style={{ borderLeft: `4px solid ${c.color || "#0058CC"}` }}>
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-[13px] font-bold">{c.name} {c.status === "archived" && <span className="ml-1 rounded-full bg-[#F2F2F7] px-2 py-px text-[10px] text-[#6B6B73]">arsip</span>}</p>
                {/* G5-67: tanggal Indonesia & tanpa titik menggantung bila tema kosong (dulu "· 2026-10-01 → 2026-10-31"). */}
                <p className="text-[11px] text-[#6B6B73]">{[c.theme, c.start_date && `${formatDate(c.start_date)} – ${c.end_date ? formatDate(c.end_date) : "…"}`].filter(Boolean).join(" · ")}</p>
              </div>
              <div className="flex gap-1">
                <button type="button" className="secondary-button !py-0.5 text-[10.5px]" onClick={() => setCosting(c)} data-testid={`mkt-campaign-costs-${c.id}`}><Wallet size={11} /> Biaya</button>
                {canEdit && <button type="button" className="secondary-button !py-0.5 text-[10.5px]" onClick={() => setEditing(c)} data-testid={`mkt-campaign-edit-${c.id}`}><Pencil size={11} /> Ubah</button>}
              </div>
            </div>
            {c.goal && <p className="mt-1 text-[11px]"><b>Tujuan:</b> {c.goal}</p>}
            <div className="mt-1 flex flex-wrap gap-1">{(c.platforms || []).map((p) => <span key={p} className="rounded-full px-1.5 py-px text-[9.5px] font-bold" style={{ background: PLATFORM_STYLE[p]?.bg, color: PLATFORM_STYLE[p]?.fg }}>{PLATFORM_STYLE[p]?.label || p}</span>)}</div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] sm:grid-cols-4">
              <Stat label="Konten" value={c.posts_total} sub={Object.entries(c.post_counts || {}).map(([k, v]) => `${STATUS_STYLE[k]?.label || k} ${v}`).join(" · ")} />
              <Stat label="Jangkauan" value={fmtN(c.reach_total)} />
              <Stat label="Interaksi" value={fmtN(c.engagement_total)} />
              <Stat label="Realisasi biaya" value={`Rp ${fmtN(c.cost_realized)}`} sub={c.budget ? `dari anggaran Rp ${fmtN(c.budget)}` : "tanpa anggaran"} testId={`mkt-campaign-realized-${c.id}`} warn={c.budget > 0 && c.cost_realized > c.budget} />
            </div>
          </div>
        ))}
      </div>
      {costing && <CampaignCostsModal campaign={costing} canPost={canPostCost} canVoid={canVoidCost} canCreateBill={canEdit} canApproveBill={canApproveBill} currentUserId={currentUser?.id} onClose={() => setCosting(null)} onChanged={load} />}
      {editing && <CampaignForm campaign={editing.id ? editing : null} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
    </div>
  );
}

function Stat({ label, value, sub, testId, warn }) {
  return <div className={`rounded-lg p-1.5 ${warn ? "bg-[#FDECEC]" : "bg-[#FAFBFC]"}`}><p className="text-[9.5px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p><p className={`text-[13px] font-bold ${warn ? "text-[#C0392B]" : ""}`} data-testid={testId}>{value ?? 0}</p>{sub && <p className="truncate text-[9.5px] text-[#8E8E93]" title={sub}>{sub}</p>}</div>;
}

function CampaignForm({ campaign, onClose, onSaved }) {
  const [f, setF] = useState({ name: campaign?.name || "", theme: campaign?.theme || "", goal: campaign?.goal || "", start_date: campaign?.start_date || "", end_date: campaign?.end_date || "", platforms: campaign?.platforms || [], budget: campaign?.budget || "", color: campaign?.color || COLORS[0], status: campaign?.status || "active", notes: campaign?.notes || "" });
  const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));
  const submit = async () => {
    setBusy(true); setErr("");
    try { if (campaign) await mktApi.updateCampaign(campaign.id, { ...f, budget: Number(f.budget || 0) }); else await mktApi.createCampaign({ ...f, budget: Number(f.budget || 0) }); onSaved(); }
    catch (e) { setErr(apiErrorText(e, "Gagal menyimpan kampanye.")); } finally { setBusy(false); }
  };
  return (
    <FormModal open title={campaign ? "Ubah kampanye" : "Kampanye baru"} icon={Flag} onClose={onClose} onSubmit={submit} busy={busy} error={err} testId="mkt-campaign-form" submitTestId="mkt-campaign-submit">
      <div className="grid gap-3">
        <Field label="Nama kampanye *"><input className="field w-full" value={f.name} onChange={(e) => set("name", e.target.value)} placeholder="mis. Lebaran 2027" data-testid="mkt-c-name" /></Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Tema"><input className="field w-full" value={f.theme} onChange={(e) => set("theme", e.target.value)} placeholder="Koleksi warna hangat & motif klasik" data-testid="mkt-c-theme" /></Field>
          <Field label="Tujuan"><input className="field w-full" value={f.goal} onChange={(e) => set("goal", e.target.value)} placeholder="+500 pengikut, 50 prospek DM" data-testid="mkt-c-goal" /></Field>
          <Field label="Mulai"><KNDatePicker className="w-full" value={f.start_date} onChange={(v) => set("start_date", v)} data-testid="mkt-c-start" /></Field>
          <Field label="Selesai"><KNDatePicker className="w-full" value={f.end_date} min={f.start_date || undefined} onChange={(v) => set("end_date", v)} data-testid="mkt-c-end" /></Field>
          <Field label="Anggaran (Rp)"><MoneyInput className="field w-full" value={f.budget} onChange={(v) => set("budget", v)} testId="mkt-c-budget" placeholder="mis. 5.000.000" /></Field>
          <Field label="Status"><KNSelect className="field w-full" value={f.status} onValueChange={(v) => set("status", v)} data-testid="mkt-c-status" options={[{ value: "active", label: "Aktif" }, { value: "archived", label: "Arsip" }]} /></Field>
        </div>
        <Field label="Platform">
          <div className="flex flex-wrap gap-1.5">{Object.entries(PLATFORM_STYLE).map(([c, p]) => <button key={c} type="button" data-testid={`mkt-c-platform-${c}`} onClick={() => set("platforms", f.platforms.includes(c) ? f.platforms.filter((x) => x !== c) : [...f.platforms, c])} className={`rounded-full border px-3 py-1 text-[11px] font-bold ${f.platforms.includes(c) ? "border-transparent" : "border-[#E5E5EA] bg-white text-[#6B6B73]"}`} style={f.platforms.includes(c) ? { background: p.bg, color: p.fg } : undefined}>{p.label}</button>)}</div>
        </Field>
        <Field label="Warna penanda"><div className="flex gap-1.5">{COLORS.map((c) => <button key={c} type="button" onClick={() => set("color", c)} className={`h-6 w-6 rounded-full border-2 ${f.color === c ? "border-[#111]" : "border-transparent"}`} style={{ background: c }} data-testid={`mkt-c-color-${c.slice(1)}`} />)}</div></Field>
        <Field label="Catatan"><input className="field w-full" value={f.notes} onChange={(e) => set("notes", e.target.value)} data-testid="mkt-c-notes" /></Field>
      </div>
    </FormModal>
  );
}
