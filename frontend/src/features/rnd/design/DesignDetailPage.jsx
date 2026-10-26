/**
 * DesignDetailPage — halaman satu desain: stepper siklus hidup, kotak progres ronde (Pengajuan awal → Revisi N → ACC → Final),
 * aksi sesuai peran, tab Ringkasan · Ronde & Nilai · Final (warna + mockup) · Timeline · Umpan Balik · Referensi.
 *
 * Fase 3 · P6 (D-09) — isi unik galeri showcase lama (`DesignShowcaseModal`): kepemilikan white/customer label,
 * klaim pelanggan, data pemakaian & tautan desain → induk kini tab **Kepemilikan & Pemakaian** di sini (desain ACC),
 * sehingga mode Galeri dan Master membuka rincian yang sama.
 */
import DesignImage from "./DesignImage";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Pencil, RefreshCw } from "lucide-react";
import ErrorNotice from "../../../components/ErrorNotice";
import OkNotice from "../../../components/OkNotice";
import { getDesign, patchDesign, studioMeta } from "../rndApi";
import { DESIGN_LIFECYCLE_STEPS, DESIGN_STATUS_META, errMsg, fmtScore } from "../rndMeta";
import DesignFormModal from "../DesignFormModal";
import LifecycleActions from "./LifecycleActions";
import RoundsTimeline from "./RoundsTimeline";
import HistoryPanel from "./HistoryPanel";
import ProofingPanel from "./ProofingPanel";
import FeedbackThread from "./FeedbackThread";
import FilesPanel from "./FilesPanel";
import FinalPanel from "./FinalPanel";
import ProductPicker from "./ProductPicker";
import RoundsProgress, { RoundBadge } from "./RoundsProgress";
import { ScoreBadge } from "./ScoreInput";
import { HoldBadge, OriginBadge, ProofingBadge } from "./DesignBadges";
import { can, roleIs } from "../../../config/roles";
import DesignOwnershipPanel from "../../hr/DesignOwnershipPanel";
import { ACC_STATUSES } from "./designFilters";

const TABS = [
  ["summary", "Ringkasan"], ["final", "Final: Mockup & File Asli"],
  ["proofing", "Proofing R&D"], ["ownership", "Kepemilikan & Pemakaian"], ["history", "Riwayat"], ["feedback", "Umpan Balik"], ["refs", "Referensi"],
];
const API = process.env.REACT_APP_BACKEND_URL;

export default function DesignDetailPage({ designId, currentUser, onBack, onChanged }) {
  const [d, setD] = useState(null);
  const [meta, setMeta] = useState(null);
  const [tab, setTab] = useState("summary");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [edit, setEdit] = useState(false);

  const role = currentUser?.role;
  const canAssess = roleIs(role, ["admin", "manager"]);
  const canEdit = canAssess || can(currentUser?.permissions, "design_request", "deliver") || can(currentUser?.permissions, "rnd", "manage");   // Sisir lanjutan gerbang peran (2026-10-21) — = _perm_manage server
  const canHold = can(currentUser?.permissions, "rnd", "hold") || meta?.hold?.can_hold === true;
  const canRelease = can(currentUser?.permissions, "design_request", "release_hold") || meta?.hold?.can_release === true;
  const canPaper = canEdit && (can(currentUser?.permissions, "design_request", "paper_check") || meta?.can_paper_check === true);

  const load = useCallback(async () => {
    try { setD(await getDesign(designId)); setError(""); }
    catch (e) { setError(errMsg(e, "Gagal memuat desain.")); }
  }, [designId]);
  useEffect(() => { load(); studioMeta().then(setMeta).catch(() => {}); }, [load]);

  const done = (msg) => { setOk(msg || ""); setError(""); load(); onChanged?.(); };
  const fail = (msg) => { setError(msg); setOk(""); };

  if (!d) {
    return (
      <div data-testid="design-detail-loading">
        <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="design-detail-error" />
        <div className="h-40 animate-pulse rounded-lg bg-[#F5F5F7]" />
      </div>
    );
  }
  const st = DESIGN_STATUS_META[d.status] || DESIGN_STATUS_META.draft;
  const stepIdx = d.status === "revision" ? 1 : DESIGN_LIFECYCLE_STEPS.findIndex((s) => s.key === d.status);
  const minAcc = meta?.code?.acc_min_score ?? 1.5;
  const cover = (d.files || []).find((f) => (f.kind || "artwork") === "artwork" && (f.version || 1) === d.version)
    || (d.files || []).find((f) => (f.kind || "artwork") === "artwork");
  const uploadOpen = canEdit && ["draft", "revision"].includes(d.status);
  const canEditHead = canEdit && !["archived", "retired", "active"].includes(d.status);
  const patternName = d.category_name || d.category_code;
  const designCatName = d.design_category_name || d.design_category_code;
  const metaParts = [
    patternName && ["pattern", <>Pattern <b>{patternName}</b></>],
    designCatName && ["design", <>Design <b>{designCatName}</b></>],
    d.created_by && ["by", <>desainer <b>{d.created_by}</b></>],
    d.final_score !== null && d.final_score !== undefined && ["score", <>nilai ACC final <b>{fmtScore(d.final_score)}</b> ({d.rounds?.find((r) => r.version === d.approved_version)?.label || `v${d.approved_version}`})</>],
  ].filter(Boolean);

  return (
    <div data-testid="design-detail-page" className="space-y-3">
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="design-detail-error" />
      <OkNotice message={ok} onDismiss={() => setOk("")} testId="design-detail-ok" />

      <div className="section-card">
        <div className="section-body">
          {/* UAT 24 Okt (audit UI tahap 2) — G5-07: kepala bertata letak HP. Dulu 3 kolom dalam satu baris flex-wrap
              → di 390 px kode "DSN-GEN-001" pecah per huruf & tertutup tombol ⟳/Ubah, metadata satu kata per baris.
              Sekarang < 640 px: tombol kembali + aksi kecil di baris atas, info selebar layar, aksi siklus di bawah. */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
            <div className="flex items-center justify-between gap-2 sm:contents">
              <button className="secondary-button !py-1.5 sm:order-1" onClick={onBack} data-testid="design-detail-back"><ArrowLeft size={13} /> Daftar</button>
              <div className="flex gap-1.5 sm:hidden">
                <button className="secondary-button !py-1.5" onClick={load} title="Muat ulang" aria-label="Muat ulang" data-testid="design-detail-refresh-m"><RefreshCw size={13} /></button>
                {canEditHead && (
                  <button className="secondary-button !py-1.5 text-[11.5px]" onClick={() => setEdit(true)} data-testid="design-detail-edit-m"><Pencil size={13} /> Ubah</button>
                )}
              </div>
            </div>
            <div className="flex min-w-0 flex-1 items-start gap-3 sm:order-2">
              <div className="h-16 w-16 shrink-0 overflow-hidden rounded-lg border border-[#E5E5EA] bg-[#F5F5F7] sm:h-20 sm:w-20">
                {cover ? <DesignImage src={`${API}/api/design-gallery/${d.id}/files/${cover.id}`} alt={d.title} className="h-full w-full object-cover" />
                  : <span className="flex h-full items-center justify-center text-[9.5px] text-[#9A9BA3]">tanpa berkas</span>}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="whitespace-nowrap font-mono text-[16px] font-bold" data-testid="design-detail-code">{d.code}</h2>
                  {/* G5-68: satu lencana status di kepala; ronde hanya bila sudah ada revisi (progres ronde ada di bawah),
                      nilai tanpa label "ACC" kedua. */}
                  {(d.revision_count || 0) > 0 && <RoundBadge design={d} testId="design-detail-round" />}
                  <span className={`status-pill ${st.cls}`} data-testid="design-detail-status">{st.label}</span>
                  <HoldBadge design={d} size="lg" testId="design-detail-hold" />
                  <OriginBadge design={d} size="lg" testId="design-detail-origin" />
                  <ProofingBadge design={d} size="lg" testId="design-detail-proofing" />
                  {d.final_score !== null && d.final_score !== undefined && <ScoreBadge value={d.final_score} testId="design-detail-score" />}
                </div>
                <p className="text-[13px] font-semibold" data-testid="design-detail-title">{d.title}</p>
                {(d.special_order_number || d.parent_design_id) && (
                  <p className="mt-0.5 text-[10.5px] text-[#6B6B73]" data-testid="design-detail-origin-ref">
                    {d.special_order_number && <>Pesanan khusus <b>{d.special_order_number}</b></>}
                    {d.special_order_number && d.parent_design_id && " · "}
                    {d.parent_design_id && <>induk desain <b>{d.parent_design_code || d.parent_design_id}</b></>}
                  </p>
                )}
                {d.request_number && (
                  <p className="mt-0.5 inline-flex items-center gap-1 rounded-full bg-[#F1E9F7] px-2 py-0.5 text-[10.5px] font-semibold text-[#6B219A]" data-testid="design-detail-request">
                    Dari permintaan {d.request_number} — status permintaan mengikuti desain ini
                  </p>
                )}
                {/* G5-68: bagian kosong disembunyikan (dulu "Pattern — · Design — · desainer …"). */}
                {metaParts.length > 0 && (
                  <p className="text-[10.5px] text-[#6B6B73]" data-testid="design-detail-meta">
                    {metaParts.map(([k, node], i) => <span key={k}>{i > 0 && " · "}{node}</span>)}
                  </p>
                )}
              </div>
            </div>
            <div className="flex flex-col gap-2 sm:order-3 sm:items-end">
              <div className="hidden gap-1.5 sm:flex">
                <button className="secondary-button !py-1.5" onClick={load} title="Muat ulang" aria-label="Muat ulang" data-testid="design-detail-refresh"><RefreshCw size={13} /></button>
                {canEditHead && (
                  <button className="secondary-button !py-1.5 text-[11.5px]" onClick={() => setEdit(true)} data-testid="design-detail-edit"><Pencil size={13} /> Ubah</button>
                )}
              </div>
              <LifecycleActions design={d} canAssess={canAssess} canEdit={canEdit} canHold={canHold} canRelease={canRelease} minAcc={minAcc} onDone={done} onError={fail} />
            </div>
          </div>

          {d.on_hold && (
            <div className="mt-3 rounded-lg border border-[#F2B48A] bg-[#FFF1E6] px-3 py-2 text-[11.5px] text-[#B24A00]" data-testid="design-detail-hold-banner">
              <b>DITAHAN</b> sejak {d.hold?.at ? new Date(d.hold.at).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" }) : "—"} oleh <b>{d.hold?.by}</b> — “{d.hold?.reason}”.
              Desain ini <b>tidak bisa masuk proofing R&amp;D</b> dan tidak bisa diaktifkan sampai penahanan dilepas.
            </div>
          )}

          <ol className="mt-3 flex items-center gap-1 overflow-x-auto" data-testid="design-lifecycle-stepper">
            {DESIGN_LIFECYCLE_STEPS.map((s, i) => {
              const state = d.status === "revision" && i === 1 ? "warn" : i < stepIdx ? "done" : i === stepIdx ? "cur" : "todo";
              const cls = { done: "bg-[#1A7A3A] text-white", cur: "bg-[#0058CC] text-white", warn: "bg-[#C62828] text-white", todo: "bg-[#F5F5F7] text-[#8E8E93]" }[state];
              return (
                <li key={s.key} className="flex items-center gap-1" data-testid={`design-step-${s.key}`}>
                  <span className={`whitespace-nowrap rounded-full px-2.5 py-1 text-[10.5px] font-semibold ${cls}`}>
                    {i + 1}. {state === "warn" ? "Perlu Revisi" : s.label}
                  </span>
                  {i < DESIGN_LIFECYCLE_STEPS.length - 1 && <span className="h-px w-4 bg-[#D9D9DE]" />}
                </li>
              );
            })}
            {["archived", "retired"].includes(d.status) && <li className="rounded-full bg-[#6B6B73] px-2.5 py-1 text-[10.5px] font-semibold text-white">Diarsipkan</li>}
          </ol>

          <div className="mt-3">
            <p className="mb-1 text-[10.5px] font-bold uppercase text-[#8E8E93]">Progres ronde · {d.revision_count || 0}× revisi</p>
            <RoundsProgress design={d} />
          </div>
          {d.status === "revision" && d.reject_reason && (
            <div className="mt-2 rounded-lg bg-[#FDF3F2] px-3 py-2 text-[11.5px] text-[#C62828]" data-testid="design-detail-revision-note">
              <b>Catatan revisi penilai:</b> {d.reject_reason} — unggah hasil revisi di bawah, lalu <b>Ajukan</b>.
            </div>
          )}
        </div>
      </div>

      <div className="section-card section-pad">
        {/* G5-07: tab bergulir horizontal (dulu patah 3 baris di HP) + bayangan tepi kanan sebagai penanda gulir. */}
        <div className="relative">
        <div className="flex gap-1 overflow-x-auto whitespace-nowrap border-b border-[#EFF0F2] px-3 pt-2" data-testid="design-detail-tabs">
          {TABS.filter(([k]) => k !== "ownership" || ACC_STATUSES.includes(d.status)).map(([k, l]) => (
            <button key={k} onClick={() => setTab(k)} data-testid={`design-tab-${k}`}
              className={`-mb-px shrink-0 border-b-2 px-3 py-2 text-[11.5px] font-semibold ${tab === k ? "border-[#6B219A] text-[#6B219A]" : "border-transparent text-[#6B6B73] hover:text-[#1C1C1E]"}`}>
              {l}
              {k === "feedback" && d.feedback_count > 0 && <span className="ml-1 rounded-full bg-[#0058CC] px-1.5 text-[9px] text-white">{d.feedback_count}</span>}
              {k === "final" && d.status === "approved" && <span className="ml-1 rounded-full bg-[#C62828] px-1.5 text-[9px] text-white">wajib</span>}
              {k === "proofing" && (d.proofing?.samples?.length || 0) > 0 && <span className="ml-1 rounded-full bg-[#6B219A] px-1.5 text-[9px] text-white">{d.proofing.samples.length}</span>}
              {k === "history" && <span className="ml-1 rounded-full bg-[#F5F5F7] px-1.5 text-[9px] text-[#6B6B73]">{(d.timeline || []).length}</span>}
            </button>
          ))}
        </div>
        <span aria-hidden="true" className="pointer-events-none absolute right-0 top-0 h-full w-6 bg-gradient-to-l from-white to-transparent sm:hidden" />
        </div>
        <div className="section-body">
          {tab === "summary" && <Summary d={d} canEdit={uploadOpen} canAssess={canAssess} canPaper={canPaper} onDone={done} onError={fail} />}
          {tab === "final" && <FinalPanel design={d} canEdit={canEdit} onDone={done} onError={fail} />}
          {tab === "proofing" && <ProofingPanel design={d} />}
          {tab === "ownership" && (
            <div data-testid="design-ownership-tab">
              <DesignOwnershipPanel d={d} currentUser={currentUser} onChanged={() => done("")} />
            </div>
          )}
          {tab === "history" && <HistoryPanel design={d} />}
          {tab === "feedback" && <FeedbackThread design={d} currentUser={currentUser} canWrite={canEdit} onDone={done} onError={fail} />}
          {tab === "refs" && <FilesPanel design={d} kind="reference" canEdit={canEdit} onDone={done} onError={fail} />}
        </div>
      </div>

      {edit && (
        <DesignFormModal mode="edit" design={d} canManageMaster={canAssess} onClose={() => setEdit(false)}
          onSaved={() => { setEdit(false); done("Desain diperbarui."); }} />
      )}
    </div>
  );
}

function Summary({ d, canEdit, canAssess, canPaper, onDone, onError }) {
  const [editProd, setEditProd] = useState(false);
  const [prods, setProds] = useState(d.recommended_products || []);
  const saveProds = async () => {
    try { await patchDesign(d.id, { recommended_product_ids: prods.map((p) => p.id) }); setEditProd(false); onDone?.("Peruntukan produk disimpan."); }
    catch (e) { onError?.(errMsg(e, "Gagal menyimpan peruntukan produk.")); }
  };
  const accDone = ["approved", "final_submitted", "active"].includes(d.status);
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="space-y-3 lg:col-span-2">
        <div>
          <p className="mb-2 text-[10.5px] font-bold uppercase text-[#8E8E93]">Perjalanan ronde · {d.revision_count || 0}× revisi · nilai diberikan sekali saat ACC</p>
          <RoundsTimeline design={d} canEdit={canEdit} canPaper={canPaper} onDone={onDone} onError={onError} />
        </div>
        <div>
          <p className="mb-1 text-[10.5px] font-bold uppercase text-[#8E8E93]">Cerita / catatan</p>
          <p className="whitespace-pre-wrap text-[12px] text-[#3C3C43]" data-testid="design-detail-story">{d.story || "—"}</p>
        </div>
      </div>
      <div className="space-y-3 text-[12px]">
        <Info label="Peruntukan produk (ditetapkan penilai saat ACC)">
          {editProd ? (
            <div className="space-y-1.5">
              <ProductPicker value={prods} onChange={setProds} testId="design-detail-products-picker" />
              <div className="flex gap-1.5">
                <button className="primary-button !py-1 text-[10.5px]" onClick={saveProds} data-testid="design-detail-products-save">Simpan</button>
                <button className="secondary-button !py-1 text-[10.5px]" onClick={() => setEditProd(false)}>Batal</button>
              </div>
            </div>
          ) : (
            <>
              {(d.recommended_products || []).length ? (
                <div className="flex flex-wrap gap-1" data-testid="design-detail-products">
                  {d.recommended_products.map((p) => <span key={p.id} className="rounded-full bg-[#EEF4FF] px-2 py-0.5 text-[10.5px] text-[#0058CC]"><b>{p.sku}</b> {p.name}</span>)}
                </div>
              ) : <span className="text-[#9A9BA3]" data-testid="design-detail-products-empty">{accDone ? "belum ditetapkan" : "ditentukan penilai saat ACC"}</span>}
              {canAssess && accDone && (
                <button className="mt-1 block text-[10.5px] text-[#6B219A] underline" onClick={() => { setProds(d.recommended_products || []); setEditProd(true); }}
                  data-testid="design-detail-products-edit">atur peruntukan</button>
              )}
            </>
          )}
        </Info>
        <Info label="Berkas final">
          Mockup {d.final?.mockup_files ?? 0}/1 · File desain asli {d.final?.source_files ?? 0}/1
        </Info>
        {/* G5-68: bagian kosong disembunyikan (dulu "Repeat — · 0 screen"). */}
        {(d.repeat_cm || Number(d.screen_count) > 0) && (
          <Info label="Spesifikasi cetak">
            {[d.repeat_cm && `repeat ${d.repeat_cm} cm`, Number(d.screen_count) > 0 && `${d.screen_count} screen`].filter(Boolean).join(" · ")}
          </Info>
        )}
        <Info label="Tag">
          <div className="flex flex-wrap gap-1" data-testid="design-detail-tags">
            {(d.tags || []).map((t) => <span key={t} className="rounded-full bg-[#F1E9F7] px-2 py-0.5 text-[10.5px] text-[#6B219A]">{t}</span>)}
            {!(d.tags || []).length && <span className="text-[#9A9BA3]">—</span>}
          </div>
        </Info>
        <Info label="Lini">{d.line_code || "semua lini"}</Info>
      </div>
    </div>
  );
}

function Info({ label, children }) {
  return (
    <div>
      <p className="mb-1 text-[10.5px] font-bold uppercase text-[#8E8E93]">{label}</p>
      <div>{children}</div>
    </div>
  );
}
