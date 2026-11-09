import { AskKnButton } from "../../../components/AskKnButton";
import { useEffect, useState } from "react";
import { can } from "../../../config/roles";
import { FlaskConical, PackageCheck, XCircle } from "lucide-react";
import { askReason, askText } from "../../../services/confirmService";
import { ErrorBox, GrnStatusBadge, GrnStepper } from "./GrnBits";
import GrnCountPanel from "./GrnCountPanel";
import GrnReconPanel from "./GrnReconPanel";
import GrnReviewPanel from "./GrnReviewPanel";
import GrnOcrDraft from "./GrnOcrDraft";
import { errText, grnApi, sampleApi } from "./grnApi";
import { DetailHeader } from "../../../components/DetailParts";   // FIX-8 (UI-60) — kepala detail sebaris baku
import EmptyState, { isForbidden } from "../../../components/EmptyState";
import DocNumber from "../../../components/DocNumber";

const STEP_NO = { review: 1, count: 2, recon: 3 };
const STEP_TITLE = { review: "Periksa surat jalan", count: "Hitung roll fisik", recon: "Rekonsiliasi & tutup" };
const TAB_FOR = { draft: "review", reading: "review", review: "review", counting: "count", reconcile: "recon", closing: "recon", closed: "recon", rejected: "review", cancelled: "review" };

export default function GrnDetail({ grnId, user, onBack }) {
  const [grn, setGrn] = useState(null);
  const [tab, setTab] = useState("review");
  const [err, setErr] = useState("");
  const [sampled, setSampled] = useState(false);
  const role = user?.role;
  // FE-04 — izin efektif per aksi (review / count / close dipisah seperti di server).
  const canReview = can(user?.permissions, "goods_receipt", "review");
  const canCount = can(user?.permissions, "goods_receipt", "count");
  const canClose = can(user?.permissions, "goods_receipt", "close");
  const [loadErr, setLoadErr] = useState(null);
  useEffect(() => { grnApi.get(grnId).then((g) => { setGrn(g); setTab(TAB_FOR[g.status]); }).catch((e) => { setErr(errText(e, "Kedatangan tidak ditemukan.")); setLoadErr(e); }); }, [grnId]);
  useEffect(() => {
    if (grn?.status !== "reading") return undefined;
    const t = setInterval(() => grnApi.get(grnId).then((g) => { if (g.status !== "reading") { setGrn(g); setTab(TAB_FOR[g.status]); } }).catch(() => {}), 5000);
    return () => clearInterval(t);
  }, [grn?.status, grnId]);
  const onChange = (g) => { if (g?.id) { setGrn(g); setTab((t) => (TAB_FOR[g.status] !== TAB_FOR[grn?.status] ? TAB_FOR[g.status] : t)); } };
  // FIX-8 (B4 §3.10) — sebelum data datang: "Memuat kedatangan…" (dulu layar kosong); 403 = tanpa akses.
  if (!grn) {
    return (
      <div className="p-4" data-testid="grn-detail-state">
        {onBack && <DetailHeader onBack={onBack} backLabel="Kembali ke daftar Kedatangan" backTestId="grn-detail-back" title="Kedatangan" />}
        <EmptyState kind={loadErr ? (isForbidden(loadErr) ? "forbidden" : "error") : "loading"}
          what="kedatangan" error={loadErr} testId="grn-detail-loading" />
      </div>
    );
  }
  const cancel = async () => {
    const reason = await askReason({ title: "Batalkan kedatangan?", message: "Roll yang sudah dihitung di kedatangan ini ikut dibatalkan.", reasonLabel: "Alasan pembatalan", confirmLabel: "Batalkan" });
    if (!reason) return;
    try { onChange(await grnApi.post(grn.id, "cancel", { expected_version: grn.version, reason })); } catch (e) { setErr(errText(e)); }
  };
  const makeSample = async () => {
    const label = await askText({ title: "Jadikan sample uji OCR?", message: "Foto SJ dan isian yang sudah Anda cek disimpan sebagai jawaban benar untuk mengukur ketepatan baca. Koreksi Anda juga jadi petunjuk AI untuk SJ mitra ini berikutnya.", reasonLabel: "Nama sample (boleh kosong)", reasonRequired: false, reasonPlaceholder: `${grn.partner_name} ${grn.dn?.number || ""}`.trim(), confirmLabel: "Simpan sample" });
    if (label === null) return;
    try { await sampleApi.fromGrn(grn.id, label || `${grn.partner_name} ${grn.dn?.number || ""}`.trim()); setSampled(true); } catch (e) { setErr(errText(e)); }
  };
  const canSample = canReview && (grn.files || []).length > 0 && ["review", "counting", "reconcile", "closing", "closed"].includes(grn.status);
  const tabs = [["review", "Surat jalan"], ["count", "Hitung"], ["recon", "Rekonsiliasi"]].filter(([k]) => canReview || k === "count" || (k === "recon" && grn.status === "closed"));
  return (
    <div className="space-y-3" data-testid="grn-detail">
      {/* FIX-8 (B1b UI-60, B4 §3.7) — GRN = dokumen kerja bertahap → halaman detail sebaris dengan kepala baku
          `DetailHeader` (bilah "Kembali ke daftar …" ≥ 32 px, dulu ikon panah 16 × 16), sama dengan Perbaikan/Retur/
          Makloon; "Batalkan" (merusak) dipisah di ujung kanan, tidak bersebelahan dengan "Tanya KN". */}
      <div className="rounded-xl border border-[#EFF0F2] bg-white p-3">
        <DetailHeader onBack={onBack} backLabel="Kembali ke daftar Kedatangan" backTestId="grn-detail-back" icon={PackageCheck}
          title={<span data-testid="grn-detail-number" className="font-mono"><DocNumber number={grn.number} entityId={grn.entity_id} /></span>}
          badges={<><GrnStatusBadge status={grn.status} testId="grn-detail-status" /><AskKnButton type="goods_receipt" id={grn.id} label={grn.number} /></>}
          subtitle={<>{grn.partner_name}{grn.dn?.number ? <> · SJ <span className="font-mono">{grn.dn.number}</span></> : " · nomor SJ belum diisi"}</>}
          actions={canSample ? (sampled
            ? <span data-testid="grn-sample-saved" className="text-[11px] font-semibold text-[#0F766E]">Tersimpan sebagai sample uji</span>
            : <button type="button" data-testid="grn-make-sample" className="secondary-button btn-sm" onClick={makeSample}><FlaskConical size={13} /> Jadikan sample uji</button>) : null}
          dangerActions={["draft", "reading", "review", "counting"].includes(grn.status) && canCount ? (
            <button type="button" data-testid="grn-cancel" className="danger-button btn-sm" onClick={cancel}><XCircle size={13} /> Batalkan</button>
          ) : null} />
        <div className="mt-2"><GrnStepper status={grn.status} /></div>
      </div>
      {(grn.reject_reason || grn.cancel_reason) && <p className="rounded-lg bg-[#F2F2F7] px-3 py-2 text-[11px]">Alasan: {grn.reject_reason || grn.cancel_reason}</p>}
      {/* UAT 24 Okt (P16.1) — tab langkah standar (`tab-bar`) + isi langkah dalam kartu putih ber-judul. */}
      <div className="tab-bar !mb-0" role="tablist">
        {tabs.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} data-testid={`grn-tab-${k}`} onClick={() => setTab(k)}
            className={`tab-button ${tab === k ? "active" : ""}`}><span className="text-[10.5px] font-bold text-[#8E8E93]">{STEP_NO[k]}</span> {label}</button>
        ))}
      </div>
      <ErrorBox text={err} />
      {(!canReview || tab !== "review") && <GrnOcrDraft grn={grn} />}
      <section className="section-card" data-testid={`grn-step-${tab}`}>
        <div className="section-head"><h2><span className="kicker">Langkah {STEP_NO[tab]}</span>{STEP_TITLE[tab]}</h2></div>
        <div className="section-body">
          {tab === "review" && canReview && <GrnReviewPanel grn={grn} onChange={onChange} canReview={canReview} />}
          {tab === "count" && <GrnCountPanel grn={grn} onChange={onChange} canCount={canCount} />}
          {tab === "recon" && <GrnReconPanel grn={grn} onChange={onChange} canReview={canReview} canClose={canClose} />}
        </div>
      </section>
    </div>
  );
}
