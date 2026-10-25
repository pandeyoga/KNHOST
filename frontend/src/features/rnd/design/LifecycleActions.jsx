/** LifecycleActions — tombol aksi sesuai status & peran (desainer vs penilai) + dialog catatan/nilai/ACC/hold.
 *  Nilai HANYA diberikan sekali, di dialog ACC (keputusan pemilik 2026-09). */
import { useState } from "react";
import { overlayDismiss } from "@/utils/overlayDismiss";   // INV-UI-01
import { useEscapeClose } from "@/utils/escapeLayers";
import { Archive, CheckCircle2, Eye, GitBranch, PackageCheck, PauseCircle, PlayCircle, Rocket, RotateCcw, Send, Undo2, X } from "lucide-react";
import { designLifecycle, designNewVersion, holdDesign, releaseDesignHold } from "../rndApi";
import { errMsg, roundLabel } from "../rndMeta";
import ScoreInput from "./ScoreInput";
import ProductPicker from "./ProductPicker";

const ACTIONS = {
  submit: { label: "Ajukan untuk review", icon: Send, side: "designer", cls: "primary-button" },
  start_review: { label: "Mulai review", icon: Eye, side: "assessor", cls: "primary-button" },
  approve: { label: "Setujui (ACC) + nilai akhir", icon: CheckCircle2, side: "assessor", cls: "primary-button", needScore: true },
  request_revision: { label: "Minta revisi", icon: RotateCcw, side: "assessor", cls: "secondary-button", needNote: true },
  submit_final: { label: "Serahkan berkas final", icon: PackageCheck, side: "designer", cls: "primary-button" },
  return_final: { label: "Kembalikan berkas final", icon: RotateCcw, side: "assessor", cls: "secondary-button", needNote: true },
  activate: { label: "Aktifkan untuk produksi", icon: Rocket, side: "assessor", cls: "primary-button" },
  archive: { label: "Arsipkan", icon: Archive, side: "assessor", cls: "secondary-button", needNote: true },
  reopen: { label: "Buka kembali", icon: Undo2, side: "assessor", cls: "secondary-button" },
  new_version: { label: "Buat versi baru", icon: GitBranch, side: "designer", cls: "secondary-button", needNote: true },
  hold: { label: "Tahan desain", icon: PauseCircle, side: "holder", cls: "secondary-button !border-[#F2B48A] !text-[#B24A00]", needNote: true },
  release_hold: { label: "Lepas penahanan", icon: PlayCircle, side: "holder", cls: "primary-button !bg-[#B24A00]" },
};

// 23 Okt — kalimat hasil yang manusiawi (dulu "<label tombol> berhasil." → "Ajukan untuk review berhasil.").
const DONE_MSG = {
  submit: "Desain diajukan untuk review — menunggu penilai.", start_review: "Review dimulai.",
  approve: "Desain disetujui (ACC).", request_revision: "Revisi diminta — desain kembali ke desainer.",
  submit_final: "Berkas final diserahkan.", return_final: "Berkas final dikembalikan ke desainer.",
  activate: "Desain aktif untuk produksi.", archive: "Desain diarsipkan.", reopen: "Desain dibuka kembali.",
  new_version: "Versi baru dibuat.", hold: "Desain ditahan.", release_hold: "Penahanan desain dilepas.",
};

// UAT 24 Okt (audit UI tahap 2) — G5-42: deskripsi singkat di kepala dialog (dulu dialog tanpa × & deskripsi).
const DLG_DESC = {
  submit: "Ronde ini masuk antrean penilai.",
  start_review: "Tandai bahwa penilaian desain ini sedang berjalan.",
  approve: "Nilai akhir diberikan sekali dan menjadi nilai KPI desainer.",
  request_revision: "Desain kembali ke desainer bersama catatan Anda.",
  submit_final: "Mockup & file desain asli diserahkan ke penilai.",
  return_final: "Berkas final kembali ke desainer untuk dilengkapi.",
  activate: "Desain dipakai untuk produksi.",
  archive: "Desain disimpan sebagai arsip dan keluar dari daftar aktif.",
  reopen: "Desain arsip dibuka kembali.",
  new_version: "Versi baru dibuat dari desain aktif.",
  hold: "Desain ditahan sementara.",
  release_hold: "Penahanan desain dilepas.",
};

const BY_STATUS = {
  draft: ["submit", "archive"],
  revision: ["submit", "archive"],
  pending_approval: ["start_review", "approve", "request_revision", "archive"],
  in_review: ["approve", "request_revision", "archive"],
  approved: ["submit_final", "hold", "archive"],
  final_submitted: ["activate", "return_final", "hold", "archive"],
  active: ["new_version", "hold", "archive"],
  archived: ["reopen"], retired: ["reopen"],
};

export default function LifecycleActions({ design, canAssess, canEdit, canHold = false, canRelease = false, minAcc = 1.5, onDone, onError }) {
  const [dlg, setDlg] = useState(null);
  const [note, setNote] = useState("");
  const [score, setScore] = useState(null);
  const [products, setProducts] = useState([]);
  const [busy, setBusy] = useState(false);
  // 23 Okt — galat dialog tampil DI DALAM dialog. Dulu dikirim ke bilah galat halaman yang tertutup lapisan gelap
  // dialog: "Catatan wajib diisi" / "Beri nilai akhir" tak terlihat → tombol terasa mati.
  const [dlgErr, setDlgErr] = useState("");
  const status = design.status || "draft";
  const fin = design.final || {};
  useEscapeClose(!!dlg, () => setDlg(null), busy);
  // G5-42: "Ajukan untuk review" tidak bisa dijalankan tanpa berkas di ronde berjalan (alasan terlihat).
  const roundFiles = design.rounds?.find((r) => r.version === design.version)?.file_count
    ?? (design.files || []).filter((f) => (f.kind || "artwork") === "artwork" && (f.version || 1) === (design.version || 1)).length;
  const submitBlocked = roundFiles === 0;

  const base = design.on_hold ? ["release_hold", "archive"] : (BY_STATUS[status] || []);
  const visible = base.filter((a) => {
    const m = ACTIONS[a];
    if (a === "release_hold") return canRelease;
    if (m.side === "holder") return canHold;
    return m.side === "assessor" ? canAssess : canEdit;
  });

  const open = (a) => {
    setDlg({ action: a }); setNote(""); setScore(null); setDlgErr("");
    setProducts(design.recommended_products || []);
  };

  const run = async () => {
    const a = dlg.action;
    const m = ACTIONS[a];
    if (m.needNote && !note.trim()) { setDlgErr("Catatan wajib diisi."); return; }
    if (m.needScore && score === null) { setDlgErr("Beri nilai akhir (0–2) — nilai hanya diberikan saat ACC."); return; }
    setBusy(true); setDlgErr("");
    try {
      if (a === "new_version") await designNewVersion(design.id, { note });
      else if (a === "hold") await holdDesign(design.id, note);
      else if (a === "release_hold") await releaseDesignHold(design.id, note);
      else {
        const body = { note, score: m.needScore ? score : undefined };
        if (a === "approve") { body.recommended_product_ids = products.map((p) => p.id); }
        await designLifecycle(design.id, a.replace(/_/g, "-"), body);
      }
      setDlg(null);
      onDone?.(DONE_MSG[a] || `${m.label} selesai.`);
    } catch (e) { setDlgErr(errMsg(e, "Aksi gagal.")); } finally { setBusy(false); }
  };

  if (!visible.length) return null;
  const A = dlg ? ACTIONS[dlg.action] : null;
  // G5-42: satu tombol utama saja (dulu "Mulai review" & "Setujui" sama-sama primary berdampingan).
  const firstPrimary = visible.find((a) => ACTIONS[a].cls.startsWith("primary-button"));
  const clsOf = (a) => (ACTIONS[a].cls.startsWith("primary-button") && a !== firstPrimary ? "secondary-button" : ACTIONS[a].cls);
  const close = () => { if (!busy) setDlg(null); };
  return (
    <div className="flex flex-wrap gap-1.5" data-testid="design-lifecycle-actions">
      {visible.map((a) => {
        const m = ACTIONS[a]; const Icon = m.icon;
        const blocked = a === "submit" && submitBlocked;
        return (
          <button key={a} className={`${clsOf(a)} !py-1.5 text-[11.5px]`} onClick={() => open(a)} data-testid={`design-action-${a}`}
            disabled={blocked} title={blocked ? "Unggah minimal satu berkas desain di ronde ini dulu." : undefined}>
            <Icon size={13} /> {m.label}
          </button>
        );
      })}
      {visible.includes("submit") && submitBlocked && (
        <p className="w-full text-[10.5px] text-[#B26A00]" data-testid="design-action-submit-blocked">
          Belum ada berkas di {roundLabel(design.version)} — unggah berkas desain dulu sebelum mengajukan.
        </p>
      )}
      {dlg && (
        <div className="fixed inset-0 z-[190] flex items-center justify-center bg-black/50 p-4" {...overlayDismiss(close)} data-testid="design-action-dialog">
          <div role="dialog" aria-modal="true" aria-label={A.label} className="max-h-[90vh] w-full max-w-[560px] overflow-y-auto rounded-xl bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 z-10 flex items-start justify-between gap-3 border-b border-[#EFF0F2] bg-white px-4 py-3">
              <div className="min-w-0">
                <h3 className="text-[13.5px] font-bold leading-tight text-[#1C1C1E]" data-testid="design-action-title">{A.label}</h3>
                <p className="mt-0.5 text-[11px] leading-snug text-[#6B6B73]">
                  <span className="whitespace-nowrap font-mono font-semibold">{design.code}</span> · {roundLabel(design.version)}{DLG_DESC[dlg.action] ? ` — ${DLG_DESC[dlg.action]}` : ""}
                </p>
              </div>
              <button type="button" className="icon-button flex-shrink-0" aria-label="Tutup" onClick={close} data-testid="design-action-close"><X size={14} /></button>
            </div>
            <div className="space-y-3 p-4">
            <DialogHint action={dlg.action} design={design} fin={fin} />
            {dlg.action === "approve" && (
              <div>
                <p className="mb-1 text-[10.5px] font-semibold text-[#6B6B73]">Peruntukan produk (ditentukan penilai)</p>
                <ProductPicker value={products} onChange={setProducts} testId="design-approve-products" />
              </div>
            )}
            {A.needScore && (
              <div>
                <p className="mb-1 text-[10.5px] font-semibold text-[#6B6B73]">Nilai akhir desain * (sekali, saat ACC — menjadi nilai KPI desainer)</p>
                <ScoreInput value={score} onChange={setScore} minAcc={minAcc} testId="design-action-score" />
              </div>
            )}
            <div>
              <p className="mb-1 text-[10.5px] font-semibold text-[#6B6B73]">
                {dlg.action === "new_version" ? "Apa yang berubah pada versi ini? *"
                  : dlg.action === "request_revision" ? "Catatan revisi untuk desainer *"
                    : dlg.action === "return_final" ? "Apa yang kurang pada berkas final? *"
                      : dlg.action === "archive" ? "Alasan pengarsipan *"
                        : dlg.action === "hold" ? "Alasan hold * (terlihat oleh R&D saat proofing ditolak)" : "Catatan (opsional)"}
              </p>
              <textarea className="field" rows={3} value={note} onChange={(e) => setNote(e.target.value)} data-testid="design-action-note"
                placeholder={dlg.action === "request_revision" ? "mis. warna latar terlalu gelap, repeat belum rapi"
                  : dlg.action === "hold" ? "mis. menunggu keputusan MD / bahan belum tersedia" : ""} />
            </div>
            {dlgErr && <p className="notice-bar danger !mb-0" role="alert" data-testid="design-action-error">{dlgErr}</p>}
            <div className="flex justify-end gap-2">
              <button className="secondary-button" onClick={close} disabled={busy}>Batal</button>
              <button className="primary-button" onClick={run} disabled={busy || (A.needScore && score === null)} data-testid="design-action-confirm"
                title={A.needScore && score === null ? "Pilih nilai akhir dulu" : undefined}>
                {busy ? "Memproses…" : A.label}
              </button>
            </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DialogHint({ action, design, fin }) {
  const box = (cls, children, testId) => <p className={`rounded-lg px-3 py-2 text-[11.5px] ${cls}`} data-testid={testId}>{children}</p>;
  if (action === "submit") return box("bg-[#F2F7FF] text-[#004099]", <>
    <b>{roundLabel(design.version)}</b> ({design.rounds?.find((r) => r.version === design.version)?.file_count ?? 0} berkas) akan masuk antrean penilai. Pastikan semua berkas ronde ini sudah diunggah.</>);
  if (action === "request_revision") return box("bg-[#FDF3F2] text-[#C62828]", <>
    Ronde <b>{roundLabel(design.version + 1)}</b> dibuka otomatis. <b>Tidak ada nilai</b> pada revisi — nilai diberikan sekali saat ACC.</>);
  if (action === "submit_final") return box(fin.complete ? "bg-[#EAF7EF] text-[#1A7A3A]" : "bg-[#FDF3F2] text-[#C62828]", <>
    Mockup {fin.mockup_files}/1 · File desain asli {fin.source_files ?? 0}/1.{fin.complete ? " Lengkap — siap diserahkan." : " Belum lengkap — unggah dulu di tab Final."}</>, "design-submit-final-check");
  if (action === "new_version") return box("bg-[#F2F7FF] text-[#004099]", <>
    v{design.version} → <b>v{design.version + 1}</b>. Status kembali <b>Draf</b>; unggah berkas baru lalu ajukan lagi.</>);
  if (action === "hold") return box("bg-[#FFF1E6] text-[#B24A00]", <>
    Selama <b>DITAHAN</b>, desain ini <b>tidak bisa dipakai permintaan proofing R&D</b> dan tidak bisa diaktifkan untuk produksi. Label DITAHAN tampil di daftar & bisa disaring.</>, "design-hold-hint");
  if (action === "release_hold") return box("bg-[#EAF7EF] text-[#1A7A3A]", <>
    Ditahan sejak <b>{design.hold?.at ? new Date(design.hold.at).toLocaleString("id-ID") : "—"}</b> oleh <b>{design.hold?.by}</b>: “{design.hold?.reason}”. Setelah dilepas, desain kembali bisa masuk proofing.</>, "design-release-hold-hint");
  return null;
}
