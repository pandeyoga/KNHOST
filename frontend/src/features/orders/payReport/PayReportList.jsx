/**
 * PayReportList (LB-T7) — daftar laporan bayar satu pesanan: status, nominal, tanggal, pelapor, bukti (blob lewat
 * `useBlobUrl`, tanpa token di URL), alasan tolak. Pemegang `payment_report.decide` (Finance) mendapat Terima dan Tolak
 * di baris yang masih `menunggu`; pelapor (`payment_report.create`) mendapat "unggah ulang" bila bukti belum ada.
 *
 * Props: `{ reports, canDecide, canCreate, onChanged, testPrefix }` — `canDecide`/`canCreate` sudah memuat izin pengguna
 * DAN bendera server (`bisa_putuskan`/`bisa_lapor`); server tetap memeriksa ulang. `onChanged()` memuat ulang pesanan.
 *
 * Terima: pratinjau "Kwitansi Rp … ke rekening … akan diterbitkan" → `askConfirm` → `POST terima` (kunci idempotensi
 * per laporan). Hasil `waiting_bank` → "Menunggu cocok mutasi bank". Galat 409 server (sedang diproses, melebihi sisa,
 * tanpa bukti) tampil di bilah galat daftar ini. Tolak: `askReason` (alasan ≥ 5 huruf); batal = tidak ada permintaan.
 */
import { useRef, useState } from "react";
import { CheckCircle2, Paperclip, XCircle } from "lucide-react";
import ErrorNotice from "../../../components/ErrorNotice";
import StatusBadge from "../../../components/StatusBadge";
import { formatCurrency, formatDate } from "../../../utils/formatters";
import { apiErrorText } from "../../../utils/apiError";
import { notifySuccess } from "../../../utils/feedback";
import { askConfirm, askReason } from "../../../services/confirmService";
import useIntentKey from "../../../hooks/useIntentKey";
import { fileNameOf, kindOf, useBlobUrl } from "../../../hooks/useBlobUrl";
import { ALASAN_MIN, attachmentUrl, proofProblem, terima, tolak, uploadProof } from "./payReportApi";

export const STATUS_LAPORAN = {
  menunggu: { label: "Menunggu dicek", tone: "warning" },
  memproses: { label: "Sedang diproses Finance", tone: "info" },
  diterima: { label: "Diterima", tone: "success" },
  ditolak: { label: "Ditolak", tone: "danger" },
};

/** Kalimat pratinjau konfirmasi Terima (satu bentuk, dipakai layar dan uji). */
export const terimaPreviewText = (r) =>
  `Kwitansi ${formatCurrency(r.amount)} ke rekening ${r.account_name || "tujuan laporan"} akan diterbitkan` +
  `${r.order_number ? ` untuk pesanan ${r.order_number}` : ""}. Lanjutkan?`;

function Bukti({ report, att, testId }) {
  const url = attachmentUrl(report.id, att.id);
  const { src, status } = useBlobUrl(url);
  const kind = kindOf(att);
  const nama = fileNameOf(att);
  if (status === "loading") return <span className="text-fs-12 text-kn-text-2">Memuat bukti…</span>;
  if (status === "error" || !src) return <span className="text-fs-12 text-kn-danger-text">Bukti {nama} gagal dimuat.</span>;
  if (kind === "image") {
    return (
      <a href={src} target="_blank" rel="noreferrer" title={nama}>
        <img src={src} alt={`Bukti ${nama}`} data-testid={testId} className="max-h-32 rounded-md border border-kn-divider" />
      </a>
    );
  }
  return (
    <a href={src} target="_blank" rel="noreferrer" data-testid={testId} className="link-button inline-flex items-center gap-1 text-fs-12">
      <Paperclip size={12} aria-hidden="true" /> {nama}
    </a>
  );
}

function Row({ r, canDecide, canCreate, onAct, busyId }) {
  const retryRef = useRef(null);
  const st = STATUS_LAPORAN[r.status] || { label: r.status, tone: "neutral" };
  const atts = r.attachments || [];
  const noProof = r.status === "menunggu" && atts.length === 0;
  const busy = busyId === r.id;
  const tp = `pay-report-${r.id}`;
  return (
    <li className="space-y-1.5 rounded-md border border-kn-divider bg-white p-2.5" data-testid={tp}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-fs-13 font-semibold text-kn-text">
          {r.number} · <span className="tabular-nums">{formatCurrency(r.amount)}</span>
        </p>
        <StatusBadge tone={st.tone} label={st.label} testId={`${tp}-status`} />
      </div>
      <p className="text-fs-12 text-kn-text-2">
        Transfer {formatDate(r.transfer_date)} · {r.account_name || "rekening"}{r.reference_no ? ` · ref ${r.reference_no}` : ""}
        {r.created_by_name ? ` · dilapor ${r.created_by_name}` : ""}
      </p>
      {r.note && <p className="text-fs-12 text-kn-text-2">Catatan: {r.note}</p>}
      {r.instruction_mismatch && r.mismatch_note && (
        <p className="text-fs-12 text-kn-warning-text">Rekening berbeda dari instruksi — alasan: {r.mismatch_note}</p>
      )}
      {atts.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {atts.map((a) => <Bukti key={a.id} report={r} att={a} testId={`${tp}-proof-${a.id}`} />)}
        </div>
      )}
      {noProof && (
        <div className="space-y-1" data-testid={`${tp}-noproof`}>
          <p className="text-fs-12 font-semibold text-kn-warning-text">Bukti belum terunggah — unggah ulang</p>
          {canCreate && (
            <input ref={retryRef} type="file" className="field" data-testid={`${tp}-retry-file`} disabled={busy}
              accept="image/jpeg,image/png,image/webp,image/gif,application/pdf"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) onAct("unggah", r, f); e.target.value = ""; }} />
          )}
        </div>
      )}
      {r.status === "ditolak" && r.reason && (
        <p className="text-fs-12 text-kn-danger-text" data-testid={`${tp}-reason`}>Alasan ditolak: {r.reason}</p>
      )}
      {r.status === "diterima" && r.receipt_number && (
        <p className="text-fs-12 text-kn-success-text">Kwitansi {r.receipt_number}</p>
      )}
      {canDecide && r.status === "menunggu" && (
        <div className="flex flex-wrap gap-2">
          <button type="button" className="primary-button btn-sm" disabled={busy} data-testid={`${tp}-terima`}
            onClick={() => onAct("terima", r)}><CheckCircle2 size={13} aria-hidden="true" /> Terima</button>
          <button type="button" className="secondary-button btn-sm" disabled={busy} data-testid={`${tp}-tolak`}
            onClick={() => onAct("tolak", r)}><XCircle size={13} aria-hidden="true" /> Tolak</button>
        </div>
      )}
    </li>
  );
}

export default function PayReportList({ reports = [], canDecide = false, canCreate = false, onChanged }) {
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const intent = useIntentKey("lbk");
  const inFlight = useRef(false);
  const list = Array.isArray(reports) ? reports : [];
  if (list.length === 0) return null;

  const act = async (kind, r, file) => {
    if (inFlight.current) return;
    setError(""); setInfo("");
    try {
      if (kind === "terima") {
        if (!(await askConfirm({ title: "Terima laporan bayar", message: terimaPreviewText(r),
          confirmLabel: "Ya, terbitkan kwitansi", cancelLabel: "Batal", testId: "pay-report-confirm" }))) return;
        inFlight.current = true; setBusyId(r.id);
        const out = await intent.send({ t: "terima", id: r.id }, (k) => terima(r.id, k));
        const bank = out.waiting_bank ? "Menunggu cocok mutasi bank" : "";
        const lepas = out.released ? "Pesanan dilepas ke gudang." : "";
        notifySuccess(`Kwitansi ${out.receipt_number || ""} terbit`, [lepas, bank].filter(Boolean).join(" "));
        setInfo([`Kwitansi ${out.receipt_number || ""} diterbitkan.`, lepas, bank].filter(Boolean).join(" "));
      } else if (kind === "tolak") {
        const reason = await askReason({ title: `Tolak laporan ${r.number}?`, danger: true, reasonLabel: "Alasan menolak",
          reasonMinLength: ALASAN_MIN, confirmLabel: "Tolak laporan", testId: "pay-report-reason" });
        if (reason === null) return;
        inFlight.current = true; setBusyId(r.id);
        await intent.send({ t: "tolak", id: r.id, reason }, (k) => tolak(r.id, reason, k));
        notifySuccess("Laporan bayar ditolak", `${r.number} — pelapor diberi tahu alasannya.`);
      } else {
        const p = proofProblem(file);
        if (p) { setError(p); return; }
        inFlight.current = true; setBusyId(r.id);
        await intent.send({ t: "unggah", id: r.id, n: file.name, s: file.size }, (k) => uploadProof(r.id, file, k));
        notifySuccess("Bukti terunggah", r.number);
      }
      onChanged?.();
    } catch (e) {
      setError(apiErrorText(e, "Aksi belum bisa diproses."));
      onChanged?.();   // 409 "sudah diputus / sedang diproses" — muat ulang supaya keadaan baris benar
    } finally { inFlight.current = false; setBusyId(""); }
  };

  return (
    <div className="space-y-2" data-testid="pay-report-list">
      <p className="text-fs-12 font-bold uppercase tracking-wide text-kn-text-2">Laporan bayar</p>
      <ErrorNotice message={error} onDismiss={() => setError("")} testId="pay-report-error" />
      {info && <p className="notice-bar info text-fs-12" data-testid="pay-report-notice">{info}</p>}
      <ul className="space-y-2">
        {list.map((r) => <Row key={r.id} r={r} canDecide={canDecide} canCreate={canCreate} onAct={act} busyId={busyId} />)}
      </ul>
    </div>
  );
}
