/**
 * AmendmentProposeModal — FASE G-1 · "Ajukan Amandemen" untuk Sales Order.
 *
 * KENAPA LAYAR INI ADA
 * --------------------
 * Sebelumnya dokumen finansial hanya punya dua pilihan yang sama-sama buruk:
 * tidak bisa dikoreksi sama sekali (koreksi lari ke WhatsApp / langsung database),
 * atau bisa diubah tanpa jejak. Layar ini adalah jalan tengahnya: pengguna boleh
 * mengusulkan angka baru, TAPI setiap usulan wajib punya label alasan, dampak yang
 * dihitung server, dan (bila melewati ambang) persetujuan orang lain.
 *
 * KEJUJURAN YANG DITEGAKKAN DI SINI
 * ---------------------------------
 * 1. Angka dampak TIDAK dihitung di browser. Setiap perubahan dikirim ke
 *    `POST /amendments/preview` dan yang ditampilkan adalah jawaban mesin harga
 *    yang sama dengan yang dipakai saat menyimpan — jadi pratinjau tidak bisa
 *    berbeda dari hasil.
 * 2. Tombol "Ajukan" MATI selama pratinjau belum berhasil. Kalau server bilang
 *    perubahan ini tidak berdampak (mis. diskon sedang dinonaktifkan di Pusat
 *    Pengaturan), pesannya ditampilkan apa adanya + pintasan memperbaikinya.
 *    Tombol yang "berhasil" tanpa efek apa pun adalah tombol palsu.
 * 3. Setelah terkirim, layar menyatakan dengan jelas apakah koreksi langsung
 *    diterapkan atau menunggu persetujuan siapa — bukan sekadar "tersimpan".
 *
 * Fase 4 · R1 — pop-up baku `FormModal` (dulu `.modal-card` ×2 buatan sendiri): layar penuh di HP, kepala & tombol
 * Ajukan tetap terlihat. Form yang SAMA dipakai aplikasi HP Sales (`sales/mobile/MobileAmendSheet`) — keputusan
 * pemilik: form input HP = form desktop (HP kini juga punya diskon tingkat pesanan & tautan bukti). Alur khusus HP
 * lewat props: `autoReason` (label alasan dipilih otomatis dari jenis perubahan, tetap bisa diganti) dan `testId`
 * (akar pop-up; isian tetap `amd-*`). Baris dokumen diekstrak ke `AmendmentItemRows.jsx`.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle, CheckCircle2, ExternalLink, FileEdit, Link2, Loader2, Plus, Trash2,
} from "lucide-react";
import KNSelect from "../../../components/KNSelect";
import FormModal from "../../../components/FormModal";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import { openConfig } from "../../settings/config/configDeepLink";
import AmendmentImpactCard from "./AmendmentImpactCard";
import AmendmentItemRows, { AMD_FIELDS, EPS, autoReasonFor, clampPct } from "./AmendmentItemRows";
import {
  errText, listReasons, previewAmendment, proposeAmendment, statusMeta,
} from "./amendmentApi";

const LABEL = "block text-[10.5px] font-semibold text-[#6B6B73] mb-1";

function buildDraft(order) {
  return (order.items || []).map((it) => ({
    product_id: it.product_id,
    sku: it.sku || "",
    product_name: it.product_name || it.sku || it.product_id,
    unit: it.unit || "",
    quantity: Number(it.quantity || 0),
    price: Number(it.price || 0),
    discount_percent: Number(it.discount_percent || 0),
    orig: {
      quantity: Number(it.quantity || 0),
      price: Number(it.price || 0),
      discount_percent: Number(it.discount_percent || 0),
    },
  }));
}

/** Hasil pengajuan — menyatakan jelas: langsung diterapkan atau menunggu persetujuan siapa. */
function AmendmentResult({ result, onClose, testId }) {
  const meta = statusMeta(result.status);
  const waiting = result.status === "pending_approval";
  return (
    <FormModal open onClose={onClose} testId={testId} icon={CheckCircle2} size="md"
      title={`Amandemen ${result.number}`} subtitle={`${result.doc_number || ""} · ${result.reason_label || ""}`}
      footer={(
        <div className="flex justify-end">
          <button type="button" className="primary-button" data-testid="amd-result-done" onClick={onClose}>Selesai</button>
        </div>
      )}>
      <div className="space-y-2.5" data-testid="amd-result">
        <span data-testid="amd-result-status" className="inline-block rounded px-2 py-1 text-[10px] font-bold uppercase tracking-wide"
          style={{ background: meta.bg, color: meta.fg }}>
          {meta.label}
        </span>
        <p data-testid="amd-result-message" className="text-[12px] leading-relaxed text-[#3C3C43]">
          {waiting
            ? `Usulan terkirim dan MENUNGGU persetujuan ${result.required_role || "manager"}. Nilai dokumen belum berubah sampai keputusan keluar.`
            : `Koreksi sudah diterapkan (${result.method_label}). Dampak ${formatCurrency(Math.abs(Number(result.impact?.delta || 0)))}.`}
        </p>
        {(result.result_refs || []).length > 0 && (
          <div data-testid="amd-result-refs" className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2.5 space-y-1">
            <p className="text-[10px] font-bold uppercase text-[#6B6B73]">Dokumen yang dihasilkan</p>
            {(result.result_refs || []).map((r, i) => (
              <p key={i} className="text-[11px] text-[#3C3C43]">
                <b className="text-[#0058CC]">{r.doc_number}</b> · {r.doc_type} {r.note ? `· ${r.note}` : ""}
              </p>
            ))}
          </div>
        )}
      </div>
    </FormModal>
  );
}

export default function AmendmentProposeModal({ order, currentUser, onClose, onDone, autoReason = false,
  testId = "amd-propose-modal" }) {
  const origOrderDisc = Number(order.order_discount_percent || 0);

  const [reasons, setReasons] = useState([]);
  const [reasonCode, setReasonCode] = useState("");
  const [manualReason, setManualReason] = useState(false);
  const [rows, setRows] = useState(() => buildDraft(order));
  const [orderDisc, setOrderDisc] = useState(origOrderDisc);
  const [note, setNote] = useState("");
  const [attachments, setAttachments] = useState([]);
  const [attName, setAttName] = useState("");
  const [attUrl, setAttUrl] = useState("");

  const [preview, setPreview] = useState(null);
  const [previewErr, setPreviewErr] = useState("");
  const [previewing, setPreviewing] = useState(false);
  const [submitErr, setSubmitErr] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const errRef = useRef(null);

  useEffect(() => {
    let alive = true;
    listReasons("sales_order")
      .then((rs) => { if (alive) setReasons(rs); })
      .catch(() => { if (alive) setReasons([]); });
    return () => { alive = false; };
  }, []);

  // ── Perubahan yang diusulkan (diturunkan dari draft, bukan disimpan ganda) ──
  const changes = useMemo(() => {
    const out = [];
    for (const r of rows) {
      for (const f of AMD_FIELDS) {
        if (Math.abs(Number(r[f] || 0) - Number(r.orig[f] || 0)) > EPS) {
          out.push({ product_id: r.product_id, field: f, to: Number(r[f] || 0) });
        }
      }
    }
    return out;
  }, [rows]);

  const discChanged = Math.abs(clampPct(orderDisc) - origOrderDisc) > EPS;
  const hasChange = changes.length > 0 || discChanged;

  // HP (`autoReason`) — alasan mengikuti jenis perubahan sampai pengguna memilih sendiri.
  useEffect(() => {
    if (autoReason && !manualReason) setReasonCode(autoReasonFor(changes, discChanged, reasons));
  }, [autoReason, manualReason, changes, discChanged, reasons]);

  const body = useMemo(() => ({
    doc_type: "sales_order",
    doc_id: order.id,
    reason_code: reasonCode,
    changes,
    order_discount_percent: clampPct(orderDisc),
  }), [order.id, reasonCode, changes, orderDisc]);

  // ── Pratinjau: dampak dihitung SERVER, di-debounce agar tidak membanjiri API ──
  useEffect(() => {
    if (!hasChange) { setPreview(null); setPreviewErr(""); return undefined; }
    let alive = true;
    setPreviewing(true);
    const t = setTimeout(async () => {
      try {
        const pv = await previewAmendment(body);
        if (!alive) return;
        setPreview(pv);
        setPreviewErr("");
      } catch (e) {
        if (!alive) return;
        setPreview(null);
        setPreviewErr(errText(e, "Gagal menghitung dampak koreksi."));
      } finally {
        if (alive) setPreviewing(false);
      }
    }, 450);
    return () => { alive = false; clearTimeout(t); };
  }, [body, hasChange]);

  const setField = useCallback((idx, field, value) => {
    setRows((arr) => arr.map((r, i) => (i === idx ? { ...r, [field]: value } : r)));
  }, []);

  const resetRow = useCallback((idx) => {
    setRows((arr) => arr.map((r, i) => (i === idx ? { ...r, ...r.orig } : r)));
  }, []);

  const selectedReason = reasons.find((r) => r.code === reasonCode);
  const absDelta = Math.abs(Number(preview?.impact?.delta || 0));
  const noteThreshold = Number(preview?.policy?.require_note_above || 0);
  const noteRequired = noteThreshold > 0 && absDelta >= noteThreshold;
  const noteMissing = noteRequired && !note.trim();

  const canSubmit = !!reasonCode && !!preview && !previewErr && !previewing
    && !submitting && !noteMissing;

  async function handleSubmit() {
    if (!canSubmit) return;
    setSubmitting(true);
    setSubmitErr("");
    try {
      const row = await proposeAmendment({ ...body, note: note.trim(), attachments });
      setResult(row);
      onDone?.(row);
    } catch (e) {
      setSubmitErr(errText(e, "Gagal mengirim usulan amandemen."));
    } finally {
      setSubmitting(false);
    }
  }

  function addAttachment() {
    const url = attUrl.trim();
    if (!url) return;
    setAttachments((a) => [...a, { name: attName.trim() || url, url }]);
    setAttName("");
    setAttUrl("");
  }

  // Pesan server yang menunjuk ke Pusat Pengaturan diberi pintasan nyata.
  const blockingMsg = previewErr || submitErr;
  const configShortcut = blockingMsg && blockingMsg.includes("Pusat Pengaturan")
    ? (blockingMsg.includes("Harga, Diskon") ? "harga-diskon" : "amandemen")
    : "";
  // Galat selalu terlihat — di HP (layar penuh) bilahnya bisa di atas lipatan saat pengguna menekan Ajukan.
  useEffect(() => {
    if (blockingMsg) errRef.current?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
  }, [blockingMsg]);

  if (result) return <AmendmentResult result={result} onClose={onClose} testId={testId} />;

  const footer = (
    <div className="flex flex-wrap items-center justify-end gap-2">
      <span className="mr-auto text-[10.5px] text-[#8E8E93]">
        Diusulkan oleh <b>{currentUser?.name || currentUser?.email || "—"}</b>
      </span>
      <button type="button" className="secondary-button" data-testid="amd-propose-cancel" onClick={onClose} disabled={submitting}>
        Batal
      </button>
      <button type="button" className="primary-button" data-testid="amd-propose-submit" onClick={handleSubmit} disabled={!canSubmit}
        title={!reasonCode ? "Pilih label alasan dulu" : (!preview ? "Dampak harus terhitung dulu" : "")}>
        {submitting ? "Mengirim…" : "Ajukan Amandemen"}
      </button>
    </div>
  );

  return (
    <FormModal open onClose={onClose} testId={testId} icon={FileEdit} size="lg" busy={submitting} footer={footer}
      title="Ajukan Amandemen"
      subtitle={<>{order.number} · {order.customer_name} · nilai sekarang{" "}
        <b className="tabular-nums">{formatCurrency(order.grand_total ?? order.total_amount)}</b></>}>
      <div data-testid="amd-principle-banner"
        className="flex items-start gap-2 rounded-md border border-[#D6E4FF] bg-[#F5F9FF] px-2.5 py-2 text-[11.5px] text-[#0058CC]">
        <AlertTriangle size={14} className="mt-0.5 shrink-0" />
        <span>
          Tidak ada perubahan angka secara diam-diam. Koreksi ini akan menjadi <b>dokumen amandemen
          bernomor</b> berisi alasan, dampak, pengusul, dan jejak ke dokumen asal.
        </span>
      </div>

      {preview?.issued && (
        <div data-testid="amd-issued-banner"
          className="mt-2 flex items-start gap-2 rounded-md border border-[#FFE2B8] bg-[#FFF7EC] px-2.5 py-2 text-[11.5px] text-[#9A5B00]">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>
            Dokumen ini <b>sudah terbit</b> ({preview.issued_reason}). Angka dokumen asal tidak akan
            diubah — koreksinya diterbitkan sebagai <b>{preview.method_label}</b>.
          </span>
        </div>
      )}

      {blockingMsg && (
        <div data-testid="amd-propose-error" ref={errRef} role="alert"
          className="mt-2 rounded-md border border-red-200 bg-red-50 px-2.5 py-2 text-[11.5px] text-red-700">
          <p>{blockingMsg}</p>
          {configShortcut && (
            <button type="button" data-testid="amd-open-config"
              onClick={() => { onClose?.(); openConfig({ group: configShortcut }); }}
              className="mt-1.5 inline-flex items-center gap-1 text-[11px] font-bold text-[#0058CC] hover:underline">
              Buka Pusat Pengaturan <ExternalLink size={11} />
            </button>
          )}
        </div>
      )}

      <div className="mt-3 space-y-3">
        {/* Label alasan — WAJIB, dan penjelasannya ikut tampil */}
        <div>
          <label className={LABEL}>
            Label alasan koreksi <span className="req">*</span>
          </label>
          <KNSelect data-testid="amd-reason-select" value={reasonCode}
            onValueChange={(v) => { setReasonCode(v); setManualReason(true); }}
            className="field" placeholder="Pilih alasan koreksi"
            options={[{ value: "", label: "— Pilih alasan koreksi —" },
              ...reasons.map((r) => ({ value: r.code, label: r.label }))]} />
          {autoReason && !manualReason && reasonCode && (
            <p data-testid="amd-reason-auto" className="mt-1 text-[10.5px] text-[#6B6B73]">
              Dipilih otomatis dari jenis perubahan — bisa diganti.
            </p>
          )}
          {selectedReason && (
            <p data-testid="amd-reason-help" className="mt-1 text-[10.5px] leading-snug text-[#6B6B73]">
              {selectedReason.help}
              {selectedReason.affects_master && (
                <b className="text-[#9A5B00]"> · Alasan ini menyangkut data master.</b>
              )}
            </p>
          )}
        </div>

        {/* Baris dokumen — nilai semula selalu terlihat di sebelah nilai baru */}
        <AmendmentItemRows rows={rows} onField={setField} onReset={resetRow} />

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div>
            <label className={LABEL} htmlFor={`${testId}-order-discount`}>
              Diskon pesanan (%) · semula {formatQty(origOrderDisc)}%
            </label>
            <input id={`${testId}-order-discount`} data-testid="amd-order-discount" type="number" min="0" max="100" step="any"
              inputMode="decimal" value={orderDisc}
              onChange={(e) => setOrderDisc(clampPct(e.target.value))} className="field tabular-nums" />
          </div>
          <div>
            <label className={LABEL} htmlFor={`${testId}-note`}>
              Penjelasan tertulis {noteRequired && <span className="req">*</span>}
            </label>
            <textarea id={`${testId}-note`} data-testid="amd-note" rows="2" value={note} onChange={(e) => setNote(e.target.value)}
              className="field" placeholder="Kronologi singkat: apa yang keliru dan kenapa dikoreksi" />
            {noteRequired && (
              <p data-testid="amd-note-required" className="mt-1 text-[10.5px] font-semibold text-[#9A5B00]">
                Koreksi sebesar {formatCurrency(absDelta)} melewati ambang {formatCurrency(noteThreshold)} —
                penjelasan tertulis wajib diisi.
              </p>
            )}
          </div>
        </div>

        {/* Tautan bukti — disimpan apa adanya pada dokumen amandemen */}
        <div className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2.5">
          <p className="text-[10px] font-bold uppercase text-[#6B6B73] mb-1.5">Tautan bukti (opsional)</p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_2fr_auto]">
            <input data-testid="amd-att-name" value={attName} onChange={(e) => setAttName(e.target.value)}
              className="field" placeholder="Nama bukti" aria-label="Nama bukti" />
            <input data-testid="amd-att-url" value={attUrl} onChange={(e) => setAttUrl(e.target.value)}
              className="field" placeholder="https:// … (email, chat, berkas)" aria-label="Tautan bukti" />
            <button type="button" data-testid="amd-att-add" className="secondary-button !px-3" onClick={addAttachment}
              aria-label="Tambah tautan bukti">
              <Plus size={13} /><span className="sm:hidden">Tambah bukti</span>
            </button>
          </div>
          {attachments.length > 0 && (
            <div className="mt-2 space-y-1" data-testid="amd-att-list">
              {attachments.map((a, i) => (
                <div key={i} className="flex items-center gap-2 rounded bg-white px-2 py-1 border border-[#EFF0F2]">
                  <Link2 size={11} className="text-[#0058CC] shrink-0" />
                  <span className="text-[10.5px] truncate flex-1">{a.name}</span>
                  <button type="button" data-testid={`amd-att-remove-${i}`} className="text-red-400 hover:text-red-600"
                    aria-label={`Hapus bukti ${a.name}`}
                    onClick={() => setAttachments((arr) => arr.filter((_, j) => j !== i))}>
                    <Trash2 size={11} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Dampak — dihitung server, bukan ditebak browser */}
        <div>
          <p className="text-[10px] font-bold uppercase text-[#6B6B73] mb-1.5">
            Dampak koreksi {previewing && <Loader2 size={11} className="inline animate-spin text-[#0058CC]" />}
          </p>
          {!hasChange ? (
            <p data-testid="amd-no-change" className="rounded-md border border-dashed border-[#E5E5EA] px-2.5 py-3 text-center text-[11px] text-[#6B6B73]">
              Ubah salah satu angka di atas untuk melihat dampaknya. Selama belum ada perubahan,
              tidak ada yang perlu diamandemen.
            </p>
          ) : preview ? (
            <AmendmentImpactCard data={preview} testId="amd-preview-impact" />
          ) : (
            <p className="rounded-md border border-dashed border-[#E5E5EA] px-2.5 py-3 text-center text-[11px] text-[#6B6B73]">
              {previewing ? "Menghitung dampak…" : "Dampak belum bisa dihitung — lihat pesan di atas."}
            </p>
          )}
        </div>
      </div>
    </FormModal>
  );
}
