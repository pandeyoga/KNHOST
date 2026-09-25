import { useEffect, useState } from "react";
import { ArrowLeft, XCircle } from "lucide-react";
import { askReason } from "../../../services/confirmService";
import { ErrorBox, GrnStatusBadge, GrnStepper } from "./GrnBits";
import GrnCountPanel from "./GrnCountPanel";
import GrnReconPanel from "./GrnReconPanel";
import GrnReviewPanel from "./GrnReviewPanel";
import { errText, grnApi } from "./grnApi";

const REVIEW_ROLES = ["admin", "manager", "warehouse_admin"];
const COUNT_ROLES = ["admin", "warehouse", "warehouse_admin"];
const TAB_FOR = { draft: "review", reading: "review", review: "review", counting: "count", reconcile: "recon", closing: "recon", closed: "recon", rejected: "review", cancelled: "review" };

export default function GrnDetail({ grnId, user, onBack }) {
  const [grn, setGrn] = useState(null);
  const [tab, setTab] = useState("review");
  const [err, setErr] = useState("");
  const role = user?.role;
  const canReview = REVIEW_ROLES.includes(role);
  const canCount = COUNT_ROLES.includes(role);
  useEffect(() => { grnApi.get(grnId).then((g) => { setGrn(g); setTab(TAB_FOR[g.status]); }).catch((e) => setErr(errText(e, "Kedatangan tidak ditemukan."))); }, [grnId]);
  useEffect(() => {
    if (grn?.status !== "reading") return undefined;
    const t = setInterval(() => grnApi.get(grnId).then((g) => { if (g.status !== "reading") { setGrn(g); setTab(TAB_FOR[g.status]); } }).catch(() => {}), 5000);
    return () => clearInterval(t);
  }, [grn?.status, grnId]);
  const onChange = (g) => { if (g?.id) { setGrn(g); setTab((t) => (TAB_FOR[g.status] !== TAB_FOR[grn?.status] ? TAB_FOR[g.status] : t)); } };
  if (!grn) return <div className="p-4"><ErrorBox text={err} /></div>;
  const cancel = async () => {
    const reason = await askReason({ title: "Batalkan kedatangan?", message: "Roll yang sudah dihitung di kedatangan ini ikut dibatalkan.", reasonLabel: "Alasan pembatalan", confirmLabel: "Batalkan" });
    if (!reason) return;
    try { onChange(await grnApi.post(grn.id, "cancel", { expected_version: grn.version, reason })); } catch (e) { setErr(errText(e)); }
  };
  const tabs = [["review", "Surat jalan"], ["count", "Hitung"], ["recon", "Rekonsiliasi"]].filter(([k]) => canReview || k === "count" || (k === "recon" && grn.status === "closed"));
  return (
    <div className="space-y-3" data-testid="grn-detail">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[#EFF0F2] bg-white p-3">
        <div className="flex items-center gap-3">
          <button onClick={onBack} data-testid="grn-detail-back" aria-label="Kembali"><ArrowLeft size={16} /></button>
          <div>
            <p className="font-mono text-[15px] font-bold" data-testid="grn-detail-number">{grn.number}</p>
            <p className="text-[11px] text-[#6B6B73]">{grn.partner_name} · SJ <span className="font-mono">{grn.dn?.number || "-"}</span></p>
          </div>
          <GrnStatusBadge status={grn.status} testId="grn-detail-status" />
        </div>
        <GrnStepper status={grn.status} />
        {["draft", "reading", "review", "counting"].includes(grn.status) && COUNT_ROLES.includes(role) && (
          <button data-testid="grn-cancel" className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#B4231F]" onClick={cancel}><XCircle size={13} /> Batalkan</button>
        )}
      </div>
      {(grn.reject_reason || grn.cancel_reason) && <p className="rounded-lg bg-[#F2F2F7] px-3 py-2 text-[11px]">Alasan: {grn.reject_reason || grn.cancel_reason}</p>}
      <div className="flex gap-1 rounded-lg bg-[#F2F2F7] p-0.5 text-[11px] font-semibold">
        {tabs.map(([k, label]) => (
          <button key={k} data-testid={`grn-tab-${k}`} onClick={() => setTab(k)} className={`flex-1 rounded-md py-1.5 ${tab === k ? "bg-white text-[#0058CC] shadow-sm" : "text-[#6B6B73]"}`}>{label}</button>
        ))}
      </div>
      <ErrorBox text={err} />
      {tab === "review" && canReview && <GrnReviewPanel grn={grn} onChange={onChange} canReview={canReview} />}
      {tab === "count" && <GrnCountPanel grn={grn} onChange={onChange} canCount={canCount} />}
      {tab === "recon" && <GrnReconPanel grn={grn} onChange={onChange} canReview={canReview} canClose={canReview} />}
    </div>
  );
}
