/**
 * InspectionDetailPanel — FASE I · isi pop-up rincian **SPK Inspeksi & QC**.
 *
 * Semua aksi hidup di sini supaya daftar tetap sederhana: menugaskan petugas,
 * memulai pemeriksaan, mengisi hasil per baris, MELEPAS TAHANAN (manajer),
 * menutup dengan keputusan, dan membuka kembali — dua yang terakhir wajib ber-alasan.
 *
 * Tombol yang bukan wewenang peran ini **tidak dirender** — bukan dirender lalu
 * ditolak server (pelajaran “layar mati” dari `audit_sales_roles_ux`).
 *
 * Angka yang ditampilkan di sini adalah RINGKASAN dari dokumen; poin cacat & grade
 * dihitung mesin 4-point di server (§3.4 rencana MD-ERP) dan tidak pernah dihitung
 * ulang di layar — dua angka untuk satu fakta adalah kelas cacat yang paling sering
 * menipu di repo ini.
 */
import { useState } from "react";
import { can } from "../../config/roles";
import {
  CheckCircle2, FlaskConical, Lock, Play, RotateCcw, User,
} from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import KNSelect from "../../components/KNSelect";
import QtyDual from "../../components/QtyDual";
import { askConfirm, askReason } from "../../services/confirmService";
import { notifySuccess } from "../../utils/feedback";
import { formatDate } from "../../utils/formatters";
import DocumentActionsBar from "../documents/DocumentActionsBar";
import InspectLineModal from "./InspectLineModal";
import InspectSheetGrid from "./InspectSheetGrid";
// Fase 4 · R3 — panel ini dipecah (658 → <500 baris) tanpa mengubah perilaku: tabel baris + bagian tanpa aksi.
import InspectionLinesTable from "./InspectionLinesTable";
import { InspectionHistory, localTs, Qc4Picker, Row } from "./InspectionDetailParts";
import {
  apiText, assignInspection, finishInspection, INS_DECISION_LABEL,
  INS_KIND_LABEL, INS_STATUS_CLASS, INS_STATUS_LABEL, MD_QUALITY_KINDS,
  createQc4point, rejectHold, releaseHold, reopenInspection, startInspection,
} from "./inspectionsApi";

export default function InspectionDetailPanel({ doc, meta, currentUser, onChanged, onClose }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [assignee, setAssignee] = useState(doc.assigned_to || "");
  const [bagian, setBagian] = useState(doc.bagian && doc.bagian !== "Bagian Inspect" ? doc.bagian : "Bagian Inspeksi");
  const [decision, setDecision] = useState("");
  const [lineOpen, setLineOpen] = useState(null);
  const [linePart, setLinePart] = useState("");
  const isRandom = doc.kind === "random_check";
  // Trial 22 Okt (E9) — SPK QC 4-point tersendiri; SPK penerimaan baru = MD Quality saja (`md_only`).
  const isQc4 = doc.kind === "qc_4point";
  const mdOnly = Boolean(doc.md_only);
  // F-14 (keputusan owner Q-03a) — SPK penerimaan PO: keputusan ini SEKALIGUS memutus karantina.
  const isPoReceipt = doc.kind === "po_receipt" && Boolean(doc.task_id);
  const [disposition, setDisposition] = useState("");
  const [rejectedRolls, setRejectedRolls] = useState([]);
  const isMdKind = (meta?.md_quality_kinds || MD_QUALITY_KINDS).includes(doc.kind);
  const canAssign = can(currentUser?.permissions, "inspection", "assign");   // FE-04
  // 23 Okt — SPK retur pelanggan: petugas QC (`qc.release`) menutupnya = QC retur selesai; uang tetap diputus Manajer.
  const isReturnCustomer = doc.kind === "return_customer";
  const canDecide = can(currentUser?.permissions, "inspection", "decide") || ((isRandom || isPoReceipt || isQc4 || isReturnCustomer) && Boolean(meta?.can_qc_release))
    // UAT 24 Okt (P11.6, keputusan pemilik) — MD Quality boleh menutup SPK MD-nya sendiri.
    || (mdOnly && Boolean(meta?.can_md_quality_decide));
  // P11.2 — SPK QC 4-point untuk SEBAGIAN roll kedatangan (null = pemilih tertutup).
  const [qc4Pick, setQc4Pick] = useState(null);
  const sampling = doc.sampling || {};
  const canInspectAll = Boolean(meta?.can_inspect_all);   // Sisir lanjutan gerbang peran (2026-10-21) — hanya dari server (tanpa tebakan nama peran saat meta belum ada)
  const canMdq = isMdKind && Boolean(meta?.can_md_quality);
  const canQc = Boolean(meta?.can_qc) || canInspectAll;
  const canInspect = canInspectAll || canQc;
  const canReleaseHold = !isRandom && (Boolean(meta?.can_release_hold)
    || (isMdKind && Boolean(meta?.can_md_quality_decide)));
  // Ambang panjang alasan datang dari SERVER (`policy.min_reason_length`), bukan
  // ditebak layar: server menolak alasan pendek dengan 400, jadi pop-up harus
  // memakai angka yang SAMA — kalau tidak, tombolnya bisa ditekan untuk aturan
  // yang sudah pasti ditolak. Cadangan 15 hanya untuk meta yang belum termuat.
  const minAlasan = Number(meta?.policy?.min_reason_length) || 15;

  const summary = doc.summary || {};
  const lines = doc.lines || [];
  const open = ["draft", "assigned", "in_progress"].includes(doc.status);
  const decisionOptions = (meta?.decisions || []).length
    ? meta.decisions
    : Object.entries(INS_DECISION_LABEL).map(([value, label]) => ({ value, label }));

  async function run(fn, pesan) {
    setBusy(true); setErr("");
    try {
      const fresh = await fn();
      notifySuccess("Berhasil", pesan);
      onChanged?.(fresh);
      return fresh;
    } catch (e) {
      setErr(apiText(e, "Aksi gagal."));
      return null;
    } finally { setBusy(false); }
  }

  const needsDisposition = isPoReceipt && ["tolak", "terima_sebagian"].includes(decision);
  const partialMissing = isPoReceipt && decision === "terima_sebagian"
    && (rejectedRolls.length === 0 || rejectedRolls.length >= (doc.lines || []).length);
  const quarantineExtra = () => (isPoReceipt
    ? { reject_disposition: needsDisposition ? disposition : "", rejected_roll_ids: decision === "terima_sebagian" ? rejectedRolls : [] }
    : {});
  const toggleRejected = (rid) => setRejectedRolls((cur) => (cur.includes(rid) ? cur.filter((x) => x !== rid) : [...cur, rid]));
  // B1 (keputusan pemilik 26 Okt) — "Diterima seluruhnya" padahal masih ada roll ditahan/gagal QC: bawaan PERINGATAN
  // (dialog), setelan Pusat Pengaturan `qc.accept_all_with_hold_action` = blokir → tombol mati + alasan. Daftar roll
  // dari server (`held_rolls`, termasuk tahanan QC 4-point yang menunggu lepas karantina); cadangan dari baris.
  const heldRolls = Array.isArray(doc.held_rolls) ? doc.held_rolls
    : lines.filter((ln) => ln.hold || ((isQc4 || isRandom) && ln.decision === "tolak"))
      .map((ln) => ({ line_id: ln.id, roll_no: ln.roll_no || ln.sku || "", reason: ln.hold_reason || "" }));
  const acceptHoldBlocked = (meta?.policy?.accept_all_with_hold_action || "peringatkan") === "blokir";
  const acceptAllWithHeld = decision === "terima" && heldRolls.length > 0;
  const heldNos = heldRolls.slice(0, 6).map((h) => h.roll_no || "—").join(", ") + (heldRolls.length > 6 ? " …" : "");

  async function tutupDenganKeputusan() {
    if (!decision) return;
    if (needsDisposition && !disposition) { setErr("Pilih tindakan untuk roll yang ditolak: retur ke supplier atau barang rusak."); return; }
    if (partialMissing) { setErr("Diterima sebagian: centang roll yang DITOLAK (minimal satu, tidak semuanya)."); return; }
    if (acceptAllWithHeld) {
      if (acceptHoldBlocked) {
        setErr(`${heldRolls.length} roll masih ditahan (${heldNos}) — pengaturan QC memblokir "Diterima seluruhnya". Pilih "Diterima sebagian"/"Ditolak" atau putus tahanannya dulu.`);
        return;
      }
      const ok = await askConfirm({
        title: "Terima seluruhnya walau ada roll ditahan?",
        message: `${heldRolls.length} roll masih ditahan/gagal QC: ${heldNos}. Keputusan "Diterima seluruhnya" TIDAK melepas tahanan itu — roll tetap ditahan sampai diputus (lepas/tolak) di rincian SPK atau antrean barang ditahan. Jumlahnya dicatat di SPK.`,
        confirmLabel: "Tetap terima seluruhnya",
        cancelLabel: "Kembali",
      });
      if (!ok) return;
    }
    // “Tolak” WAJIB ber-alasan dan alasannya tersimpan DI DOKUMEN (bukan hanya di
    // jejak audit yang tak pernah dibaca orang yang sedang bertanya).
    if (decision === "tolak") {
      const alasan = await askReason({
        title: "Tolak hasil inspeksi",
        message: `Sebutkan alasan penolakan ${doc.number}. Alasan ini dibaca supplier/mitra dan menjadi dasar klaim.`,
        confirmLabel: "Tolak & tutup SPK",
        reasonMinLength: minAlasan,
      });
      if (!alasan) return;
      await run(() => finishInspection(doc.id, decision, alasan, quarantineExtra()), "SPK ditutup: ditolak.");
      return;
    }
    await run(() => finishInspection(doc.id, decision, "", quarantineExtra()),
      `SPK ditutup: ${INS_DECISION_LABEL[decision] || decision}.`);
  }

  async function bukaKembali() {
    const alasan = await askReason({
      title: "Buka kembali SPK inspeksi",
      message: `Mengapa keputusan pada ${doc.number} dianulir? Alasan wajib — keputusan yang dibatalkan tanpa alasan menghapus jejak tanggung jawab.`,
      confirmLabel: "Buka kembali",
      reasonMinLength: minAlasan,
    });
    if (!alasan) return;
    await run(() => reopenInspection(doc.id, alasan), "SPK dibuka kembali.");
  }

  async function lepasTahanan(line) {
    const alasan = await askReason({
      title: "Lepas tahanan barang",
      message: `Barang ${line.roll_no || line.sku || "ini"} ditahan karena ${line.hold_reason || "selisih terhadap sample"}. Sebutkan dasar keputusan Anda — inilah satu-satunya catatan mengapa barang yang menyimpang tetap masuk gudang.`,
      confirmLabel: "Lepas tahanan",
      reasonMinLength: minAlasan,
    });
    if (!alasan) return;
    await run(() => releaseHold(doc.id, line.id, alasan), "Tahanan dilepas.");
  }

  async function tolakBarang(line) {
    const alasan = await askReason({
      title: "Tolak barang yang ditahan",
      message: `Barang ${line.roll_no || line.sku || "ini"} DITOLAK MD Quality dan tetap ditahan. Sebutkan alasannya — dibaca supplier/mitra sebagai dasar klaim.`,
      confirmLabel: "Tolak barang",
      reasonMinLength: minAlasan,
    });
    if (!alasan) return;
    await run(() => rejectHold(doc.id, line.id, alasan), "Barang ditolak MD Quality.");
  }

  function bukaBaris(ln, part) {
    setLinePart(part);
    setLineOpen(ln);
  }

  return (
    <div data-testid="ins-detail-panel" className="grid gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p data-testid="ins-detail-number" className="text-[13.5px] font-bold text-[#1C1C1E]">
            {doc.number}
          </p>
          <p className="text-[11px] text-[#6B6B73]">
            {INS_KIND_LABEL[doc.kind] || doc.kind}
            {doc.ref_doc_number ? ` · sumber ${doc.ref_doc_number}` : ""}
            {doc.supplier_name ? ` · ${doc.supplier_name}` : ""}
            {doc.customer_name ? ` · ${doc.customer_name}` : ""}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span data-testid="ins-detail-status"
            className={`status-pill ${INS_STATUS_CLASS[doc.status] || "pill-muted"}`}>
            {INS_STATUS_LABEL[doc.status] || doc.status}
          </span>
          {summary.hold ? (
            <span data-testid="ins-detail-hold-badge" className="status-pill pill-danger">
              <Lock size={9} className="mr-0.5 inline" />{summary.hold} barang ditahan
            </span>
          ) : null}
        </div>
      </div>

      {err && <ErrorNotice message={err} onDismiss={() => setErr("")} testId="ins-detail-error" />}

      {mdOnly && (
        <div data-testid="ins-md-only-note" className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[#E5DDF3] bg-[#F7F2FF] px-3 py-2 text-[11.5px] text-[#4B2A7A]">
          <span>SPK ini khusus <b>MD Quality</b> (warna & handfeel). <b>QC 4-point</b> dikerjakan di SPK tersendiri — boleh kapan
            saja; roll yang ditolak QC ditahan.</span>
          {canQc && qc4Pick === null && (
            <button data-testid="ins-create-qc4" className="secondary-button !h-8" disabled={busy}
              onClick={() => setQc4Pick(lines.filter((ln) => ln.roll_id).map((ln) => ln.roll_id))}>
              Buat SPK QC 4-point
            </button>
          )}
        </div>
      )}
      {mdOnly && canQc && qc4Pick !== null && (
        <Qc4Picker lines={lines} pick={qc4Pick} setPick={setQc4Pick} busy={busy}
          onSubmit={async () => {
            const fresh = await run(() => createQc4point({ inspection_id: doc.id, roll_ids: qc4Pick }),
              `SPK QC 4-point dibuat untuk ${qc4Pick.length} roll.`);
            if (fresh) setQc4Pick(null);
          }} />
      )}
      {(isQc4 || isRandom) && canQc && (
        <InspectSheetGrid doc={doc} meta={meta} editable={["assigned", "in_progress"].includes(doc.status)}
          onSaved={(fresh) => { notifySuccess("Berhasil", "Lembar inspect tersimpan."); onChanged?.(fresh); }} />
      )}

      {/* Acuan penilaian — tanpa menyebut NAMA sample-nya, kolom “warna sesuai?”
          hanya berisi pendapat yang tidak bisa diperiksa ulang siapa pun. */}
      <div className="section-card section-pad">
        <div className="flex items-start gap-2">
          <FlaskConical size={14} className="mt-0.5 shrink-0 text-[#6B219A]" />
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wide text-[#9A9BA3]">
              Acuan penilaian
            </p>
            <p data-testid="ins-detail-baseline" className="mt-0.5 text-[11.5px] text-[#3C3C43]">
              {doc.baseline_sample_number
                ? `Sample ${doc.baseline_sample_number}${doc.baseline_color ? ` · ${doc.baseline_color}` : ""}`
                : "Belum ada sample yang di-ACC untuk barang ini — hasil warna & handfeel dicatat sebagai pengamatan, bukan pembandingan."}
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <div className="section-card section-pad">
          <Row label="Tanggal SPK" testId="ins-detail-spk-date">{doc.spk_date ? formatDate(doc.spk_date) : "—"}</Row>
          <Row label="Petugas inspect" testId="ins-detail-officer">
            {doc.assigned_name || "Belum ditugaskan"}
          </Row>
          <Row label="Bagian" testId="ins-detail-bagian">{doc.bagian === "Bagian Inspect" ? "Bagian Inspeksi" : (doc.bagian || "—")}</Row>
          <Row label="Mulai diperiksa" testId="ins-detail-started">
            {localTs(doc.started_at) || "—"}
          </Row>
          <Row label="Selesai" testId="ins-detail-finished">
            {localTs(doc.finished_at) || "—"}
          </Row>
        </div>
        <div className="section-card section-pad">
          <Row label="Barang diperiksa" testId="ins-detail-qty">
            <QtyDual rolls={summary.rolls} measure={summary.measure} unit={summary.unit}
              testId="ins-detail-qty-dual" />
          </Row>
          <Row label="Baris sudah diperiksa" testId="ins-detail-inspected">
            {summary.inspected || 0} dari {summary.lines || 0}
          </Row>
          {sampling.part && (
            <Row label={sampling.part === "md_quality" ? "Dicek MD Quality" : "Diperiksa QC 4-point"} testId="ins-detail-sampling">
              <span className={sampling.checked >= sampling.required ? "text-[#1B7F4B]" : "text-[#8A5300]"}>
                {sampling.checked}/{sampling.total} roll dicek (wajib {sampling.required})
              </span>
              {sampling.part === "md_quality" && sampling.total > sampling.checked && (
                <span className="block text-[10.5px] font-normal text-[#6B6B73]">roll yang tidak dicek lolos bertanda “MDQ sampling”</span>
              )}
              {sampling.part === "qc" && sampling.total > sampling.checked && (
                <span className="block text-[10.5px] font-normal text-[#6B6B73]">roll yang tidak dicek dikeluarkan dari SPK saat ditutup</span>
              )}
            </Row>
          )}
          <Row label="Total poin cacat" testId="ins-detail-points">
            {summary.points_total ? summary.points_total : "—"}
          </Row>
          <Row label="Selisih warna / handfeel" testId="ins-detail-mismatch">
            {summary.color_mismatch || 0} / {summary.handfeel_mismatch || 0}
          </Row>
          <Row label="Keputusan" testId="ins-detail-decision">
            {doc.decision_label || "Belum diputuskan"}
          </Row>
        </div>
      </div>

      {doc.reject_reason ? (
        <div className="section-card section-pad border-l-2 border-l-[#FF3B30]">
          <p className="text-[11px] font-bold uppercase tracking-wide text-[#9A9BA3]">
            Alasan penolakan
          </p>
          <p data-testid="ins-detail-reject-reason" className="mt-0.5 text-[11.5px] text-[#3C3C43]">
            {doc.reject_reason}
          </p>
        </div>
      ) : null}

      {/* ── BARIS PEMERIKSAAN ── */}
      <InspectionLinesTable doc={doc} lines={lines} open={open} busy={busy} mdOnly={mdOnly} isMdKind={isMdKind}
        isRandom={isRandom} isQc4={isQc4} canMdq={canMdq} canQc={canQc} canInspectAll={canInspectAll}
        canReleaseHold={canReleaseHold} onOpenLine={bukaBaris} onRelease={lepasTahanan} onReject={tolakBarang} />

      {/* ── AKSI ── */}
      <div className="section-card section-pad grid gap-2">
        <p className="text-[11px] font-bold uppercase tracking-wide text-[#9A9BA3]">Tindakan</p>

        {canAssign && open && (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_160px_auto] sm:items-end">
            <label className="block">
              <span className="field-label">Tugaskan ke petugas inspect</span>
              <KNSelect data-testid="ins-assign-select" value={assignee}
                onValueChange={setAssignee} options={meta?.officers || []}
                className="field" placeholder="Pilih petugas" />
            </label>
            <label className="block">
              <span className="field-label">Bagian</span>
              <input data-testid="ins-assign-bagian" className="field" value={bagian}
                onChange={(e) => setBagian(e.target.value)} placeholder="mis. Bagian Inspeksi" />
            </label>
            <button data-testid="ins-assign-button" className="primary-button"
              disabled={busy || !assignee}
              onClick={() => run(() => assignInspection(doc.id, assignee, bagian),
                                 "SPK ditugaskan.")}>
              <User size={13} /> Tugaskan
            </button>
          </div>
        )}

        {doc.status === "draft" && (canMdq || canInspect) && (
          <p className="rounded-md bg-[#FFF7EC] px-2 py-1 text-[11px] text-[#8C4A00]" data-testid="ins-draft-hint">
            SPK belum ditugaskan — tugaskan petugas inspect dulu; hasil MD Quality / QC baru bisa diisi sesudahnya.
          </p>
        )}
        <div className="flex flex-wrap items-end gap-2">
          {/* UAT 24 Okt (audit UI tahap 2) — dulu aktif pada SPK draf tanpa petugas lalu ditolak server. */}
          {canInspect && ["draft", "assigned"].includes(doc.status) && (
            <button data-testid="ins-start-button" className="secondary-button" disabled={busy || !doc.assigned_to}
              title={!doc.assigned_to ? "Tugaskan petugas inspect dulu" : undefined}
              onClick={() => run(() => startInspection(doc.id), "Pemeriksaan dimulai.")}>
              <Play size={13} /> Mulai periksa
            </button>
          )}

          {canDecide && ["assigned", "in_progress"].includes(doc.status) && (
            <>
              <label className="block w-60">
                <span className="field-label">Keputusan akhir</span>
                <KNSelect data-testid="ins-decision-select" value={decision}
                  onValueChange={setDecision} options={decisionOptions}
                  className="field" placeholder="Pilih keputusan" />
              </label>
              {needsDisposition && (
                <label className="block w-64">
                  <span className="field-label">Roll ditolak dijadikan</span>
                  <KNSelect data-testid="ins-reject-disposition" value={disposition} onValueChange={setDisposition}
                    options={[{ value: "return", label: "Retur ke supplier (Nota Debit)" },
                              { value: "damaged", label: "Barang rusak (simpan di gudang)" }]}
                    className="field" placeholder="Pilih tindakan" />
                </label>
              )}
              <button data-testid="ins-finish-button" className="primary-button"
                disabled={busy || !decision || (needsDisposition && !disposition) || partialMissing
                  || (acceptAllWithHeld && acceptHoldBlocked)}
                title={acceptAllWithHeld && acceptHoldBlocked ? "Pengaturan QC memblokir 'Diterima seluruhnya' selama masih ada roll ditahan" : undefined}
                onClick={tutupDenganKeputusan}>
                <CheckCircle2 size={13} /> Tutup SPK
              </button>
              {acceptAllWithHeld && (
                <p data-testid="ins-held-warning"
                  className={`w-full rounded-md px-2 py-1 text-[11px] ${acceptHoldBlocked ? "bg-[#FDECEA] text-[#9B1C1C]" : "bg-[#FFF7EC] text-[#8C4A00]"}`}>
                  {heldRolls.length} roll masih ditahan/gagal QC ({heldNos}). “Diterima seluruhnya” tidak melepas tahanannya
                  {acceptHoldBlocked ? " — diblokir pengaturan QC: pilih “Diterima sebagian”/“Ditolak” atau putus tahanannya dulu."
                    : " — Anda akan diminta konfirmasi."}
                </p>
              )}
              {isPoReceipt && (
                <p className="w-full text-[10.5px] text-[#4A4A52]" data-testid="ins-quarantine-note">
                  Keputusan ini langsung memutus karantina: roll diterima → stok tersedia (grade hasil 4-point),
                  roll ditolak → retur ke supplier atau barang rusak. Tidak ada keputusan kedua di antrean karantina.
                </p>
              )}
              {isPoReceipt && decision === "terima_sebagian" && (
                <div className="w-full rounded-md border border-[#EFF0F2] p-2" data-testid="ins-reject-rolls">
                  <p className="mb-1 text-[10.5px] font-semibold text-[#6B6B73]">Centang roll yang DITOLAK:</p>
                  <div className="flex flex-wrap gap-x-4 gap-y-1">
                    {lines.filter((ln) => ln.roll_id).map((ln) => (
                      <label key={ln.id} className="inline-flex items-center gap-1 text-[11px]">
                        <input type="checkbox" data-testid={`ins-reject-roll-${ln.id}`}
                          checked={rejectedRolls.includes(ln.roll_id)} onChange={() => toggleRejected(ln.roll_id)} />
                        {ln.roll_no} · {ln.quantity} {ln.unit}{ln.grade_after ? ` · grade ${ln.grade_after}` : ""}
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {doc.quarantine_result && (
            <p className="w-full rounded-md bg-[#F1FBF4] px-2 py-1 text-[11px] text-[#126E2C]" data-testid="ins-quarantine-result">
              Karantina diputus: diterima {doc.quarantine_result.accepted_qty}
              {doc.quarantine_result.rejected_qty > 0 && <> · ditolak {doc.quarantine_result.rejected_qty}
                {doc.quarantine_result.purchase_return?.number ? ` → retur ${doc.quarantine_result.purchase_return.number}` : " (barang rusak)"}</>}
            </p>
          )}

          {canDecide && doc.status === "done" && !isRandom && !doc.quarantine_result && (
            <button data-testid="ins-reopen-button" className="secondary-button" disabled={busy}
              onClick={bukaKembali}>
              <RotateCcw size={13} /> Buka kembali
            </button>
          )}

        </div>

        {/* Cetak / tanda tangan lewat PLATFORM DOKUMEN (G-4) — bukan mesin PDF sendiri.
            UAT 24 Okt (audit UI tahap 2): SPK draf (belum ada petugas) belum bisa dicetak/ditandatangani/dikirim. */}
        <div className="border-t border-[#EFF0F2] pt-2">
          {doc.status === "draft" ? (
            <p data-testid="ins-doc-actions-draft" className="text-[11px] text-[#8E8E93]">
              Cetak, tanda tangan, dan kirim SPK tersedia setelah petugas ditugaskan.
            </p>
          ) : (
            <DocumentActionsBar docType="inspection_spk" sourceId={doc.id}
              entityId={doc.entity_id} number={doc.number} currentUser={currentUser} />
          )}
        </div>
        <div className="flex justify-end border-t border-[#EFF0F2] pt-2">
          <button data-testid="ins-detail-close" className="secondary-button" onClick={onClose}>
            Tutup
          </button>
        </div>
      </div>

      {/* ── RIWAYAT ── */}
      <InspectionHistory doc={doc} />

      <InspectLineModal
        open={Boolean(lineOpen)} onClose={() => setLineOpen(null)}
        doc={doc} line={lineOpen} meta={meta} part={linePart}
        onSaved={(fresh) => { setLineOpen(null); onChanged?.(fresh); }}
      />
    </div>
  );
}
