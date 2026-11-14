import { apiErrorText } from "../../utils/apiError";
import { useRef, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { ReceiptText, CheckCircle2, XCircle, Send, Printer, Pencil, RotateCcw, Paperclip, Trash2, HandCoins, Undo2 } from "lucide-react";
import { formatCurrency, formatDate } from "../../utils/formatters";
import ConfirmModal from "../../components/ConfirmModal";
import { STL_STATUS, StatusPill, fmtDate, printSettlement } from "./pettyCashShared";
import { can } from "../../config/roles";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyDelete, moneyPost } from "../../utils/moneyRequest";
import { confirmMoney, rupiahText } from "../../utils/moneyConfirm";
import { askConfirm } from "../../services/confirmService";
import { BudgetCheckNotice } from "../../components/BudgetCheckNotice";
import { JournalStatusBar } from "../../components/JournalStatusBadge";   // PK-18 — status jurnal LPJ
import { AttachmentThumb } from "../../components/AttachmentThumb";
import MediaLightbox from "../../components/MediaLightbox";
import { formatPeriodId } from "../../components/KNMonthPicker";
import { entityShortById } from "../../utils/entityLabel";
import SettlementCashModal from "./SettlementCashModal";   // PK-24 — pop-up kas: bayar reimburse / terima sisa

/**
 * SettlementDetail — rincian Laporan Pertanggungjawaban (LPJ) + aksi + cetak.
 *
 * Fase 3 · P4 (L-03/L-07) — isi pop-up `DetailModal framed`; rincian pengeluaran `.data-table` di wadah gulir.
 * PK-24 (SL-09, FY-14, FY-19, IA-05):
 *  · LPJ hanya bisa diubah & dilampiri selagi DRAF (tombol **Ubah**, bagian **Lampiran**); Setujui/Tolak hanya untuk LPJ
 *    DIAJUKAN; LPJ ditolak → **Perbaiki & Ajukan Lagi** (hanya pembuatnya; server `POST …/reopen`).
 *  · Ringkasan: **Sisa Harus Dikembalikan** (sisa terbuka) → **Sisa Dikembalikan · {nomor kas}** sesudah diterima;
 *    **Kekurangan Dana** bila pengeluaran melebihi uang muka. Sebelum disetujui: **Sisa Uang Muka** (belum ada
 *    kewajiban kembali).
 *  · Aksi kas (pemegang `cash_settlement.pay`): **Terima Pengembalian Sisa** dan **Bayar Reimburse** — bilah sendiri di
 *    badan kartu, pop-up `SettlementCashModal` (Jenis kas · Rekening · Tanggal) + konfirmasi nominal, karyawan,
 *    rekening, PT. Lencana jurnal PK-18 di bilah sendiri.
 */
export default function SettlementDetail({ stl, currentUser, entities, catLabels, onChanged, onEdit, flash }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [reject, setReject] = useState(false);
  const [kas, setKas] = useState("");          // "" | "return" | "reimburse"
  const [lihat, setLihat] = useState(-1);      // indeks lampiran di pratinjau
  const fileRef = useRef(null);
  // PK-12 — satu kunci idempotensi per aksi (ajukan / setujui & posting / tolak / buka lagi).
  const intents = {
    submit: useIntentKey("stls"), approve: useIntentKey("stla"),
    reject: useIntentKey("stlr"), reopen: useIntentKey("stlo"),
  };
  const perms = currentUser?.permissions;
  const entityName = entityShortById(entities, stl.entity_id);
  const karyawan = stl.dibuat_oleh || stl.created_by || "karyawan";

  // Gerbang = izin (cash_settlement.submit/update/approve/reject/pay), bukan nama peran.
  const isDraft = stl.status === "draft";
  const canSubmit = isDraft && can(perms, "cash_settlement", "submit");
  const canEdit = isDraft && can(perms, "cash_settlement", "update") && !!onEdit;
  const canAttach = isDraft && can(perms, "cash_settlement", "update");
  const canApprove = stl.status === "submitted" && can(perms, "cash_settlement", "approve");
  const canReject = stl.status === "submitted" && can(perms, "cash_settlement", "reject");
  const canPay = can(perms, "cash_settlement", "pay");
  const isCreator = stl.created_by_id ? stl.created_by_id === currentUser?.id : stl.created_by === currentUser?.name;
  const canReopen = stl.status === "rejected" && can(perms, "cash_settlement", "update") && isCreator && !!onEdit;
  const reopenHint = stl.status === "rejected" && can(perms, "cash_settlement", "update") && !isCreator
    ? `Pembuat LPJ (${stl.created_by || "pembuatnya"}) yang bisa memperbaiki dan mengajukannya lagi.` : "";

  const sr = stl.sisa_dikembalikan || {};
  const hr = stl.hutang_reimburse || {};
  const remainderOpen = sr.status === "open" && Number(sr.amount) > 0;
  const reimburseOpen = hr.status === "open" && Number(hr.amount) > 0;
  const sisa = Number(stl.sisa_kurang_dana) || 0;
  const attachments = stl.attachments || [];
  const attUrl = (a) => `${API}/cash-advance-settlements/${stl.id}/attachments/${a.id}`;
  const attItems = attachments.map((a) => ({ url: attUrl(a), filename: a.filename, content_type: a.content_type }));

  async function act(path, body, okMsg) {
    setBusy(true); setErr("");
    try {
      const b = body || {};
      const res = await intents[path].send({ id: stl.id, aksi: path, ...b },
        (k) => moneyPost(`${API}/cash-advance-settlements/${stl.id}/${path}`, b, k));
      const msg = typeof okMsg === "function" ? okMsg(res.data) : okMsg;
      flash(msg); onChanged(res.data);
      return res.data;
    } catch (e) { setErr(apiErrorText(e, "Aksi gagal.")); return null; } finally { setBusy(false); }
  }

  // PK-13 (FY-17) — setujui & posting bertanya dulu dengan nominal & PT.
  async function approve() {
    const ok = await confirmMoney({
      title: `Setujui dan posting ${stl.number}?`,
      effect: "Pengeluaran dijurnal ke beban. Sesudah diposting, isi pertanggungjawaban tidak bisa diubah.",
      amount: stl.total_pengeluaran, entityId: stl.entity_id, entities,
      confirmLabel: "Setujui & Posting", testId: "stl-approve-confirm",
    });
    if (ok) {
      await act("approve", {}, (d) => (d?.status === "approved"
        ? `${stl.number} disetujui, tetapi jurnalnya gagal: ${d.gl_error || "lihat Posting Gagal"}. Ulangi dari Keuangan › Posting Gagal.`
        : `${stl.number} disetujui & diposting ke GL.`));
    }
  }

  async function reopen() {
    const d = await act("reopen", {}, `${stl.number} dibuka lagi sebagai draf — perbaiki isinya lalu ajukan.`);
    if (d) onEdit(d, { resubmit: true });
  }

  async function upload(file) {
    if (!file) return;
    setBusy(true); setErr("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      // Lampiran bukan aksi uang: tanpa Idempotency-Key (isi multipart berbeda tiap unggah).
      await moneyPost(`${API}/cash-advance-settlements/${stl.id}/attachments`, fd, "");
      flash(`Bukti ${file.name} dilampirkan.`);
      await muatUlang();
    } catch (e) { setErr(apiErrorText(e, "Lampiran gagal diunggah.")); } finally { setBusy(false); }
  }

  async function muatUlang() {
    try { onChanged((await axios.get(`${API}/cash-advance-settlements/${stl.id}`)).data); }
    catch (e) { setErr(apiErrorText(e, "Rincian LPJ gagal dimuat ulang.")); }
  }

  async function removeAtt(a) {
    const ok = await askConfirm({
      title: `Hapus lampiran ${a.filename}?`, message: "Berkas bukti ini dihapus dari LPJ.", danger: true,
      confirmLabel: "Hapus Lampiran", testId: "stl-att-delete-confirm",
    });
    if (!ok) return;
    setBusy(true); setErr("");
    try {
      await moneyDelete(`${API}/cash-advance-settlements/${stl.id}/attachments/${a.id}`, "");
      flash(`Lampiran ${a.filename} dihapus.`);
      await muatUlang();
    } catch (e) { setErr(apiErrorText(e, "Lampiran gagal dihapus.")); } finally { setBusy(false); }
  }

  // FY-19 — baris ringkasan sisa mengikuti keadaan sebenarnya (dulu "Sisa Dikembalikan" untuk setiap LPJ bersisa).
  let sisaRow;
  if (sisa < 0) sisaRow = { k: "Kekurangan Dana", v: Math.abs(sisa), tone: "text-kn-danger-text" };
  else if (sr.status === "returned") sisaRow = { k: `Sisa Dikembalikan · ${sr.cash_txn_number || "kas"}`, v: Number(sr.amount) || 0, tone: "text-kn-success-text" };
  else if (remainderOpen) sisaRow = { k: "Sisa Harus Dikembalikan", v: Number(sr.amount) || 0, tone: "text-kn-warning-text" };
  else sisaRow = { k: "Sisa Uang Muka", v: sisa, tone: "text-kn-text" };

  return (
    <div data-testid="stl-detail" className="grid gap-4">
      <section className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2 min-w-0">
            <ReceiptText size={15} className="text-kn-action" />
            <h2 data-testid="stl-detail-number">{stl.number}</h2>
            <StatusPill status={stl.status} map={STL_STATUS} testId="stl-detail-status" />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button data-testid="stl-print" className="btn-secondary btn-sm whitespace-nowrap" onClick={() => printSettlement(stl, entityName, catLabels)}><Printer size={13} /> Cetak LPJ</button>
            {canEdit && <button data-testid="stl-edit-btn" className="btn-secondary btn-sm whitespace-nowrap" onClick={() => onEdit(stl, { resubmit: false })} disabled={busy}><Pencil size={13} /> Ubah</button>}
            {canSubmit && <button data-testid="stl-submit-btn" className="btn-primary btn-sm whitespace-nowrap" onClick={() => act("submit", {}, `${stl.number} diajukan.`)} disabled={busy}><Send size={13} /> Ajukan</button>}
            {canApprove && <button data-testid="stl-approve-btn" className="btn-primary btn-sm whitespace-nowrap" onClick={approve} disabled={busy}><CheckCircle2 size={13} /> Setujui & Posting GL</button>}
            {canReject && <button data-testid="stl-reject-btn" className="btn-danger btn-sm whitespace-nowrap" onClick={() => setReject(true)} disabled={busy}><XCircle size={13} /> Tolak</button>}
            {canReopen && <button data-testid="stl-reopen-btn" className="btn-primary btn-sm whitespace-nowrap" onClick={reopen} disabled={busy}><RotateCcw size={13} /> Perbaiki & Ajukan Lagi</button>}
          </div>
        </div>
        {err && <div className="notice-bar danger mx-3 mb-3" data-testid="stl-detail-error"><span>{err}</span><button onClick={() => setErr("")}>×</button></div>}

        <div className="section-body grid gap-4">
          <JournalStatusBar doc={stl} testId="stl-journal" />
          {/* PK-39 (K-12) — peringatan anggaran dari ajukan/setujui (tersimpan di LPJ); mode tolak → galat di atas. */}
          <BudgetCheckNotice check={stl.budget_check} testId="stl-budget-check" />
          {reopenHint && <p className="text-fs-12 text-kn-text-2" data-testid="stl-reopen-hint">{reopenHint}</p>}
          {stl.status === "rejected" && stl.rejected_reason && (
            <p className="text-fs-12 text-kn-danger-text" data-testid="stl-rejected-reason">Alasan ditolak: {stl.rejected_reason}</p>
          )}

          {/* Aksi kas di bilahnya sendiri (bukan kepala kartu): sisa uang muka & hutang reimburse. */}
          {remainderOpen && (
            <div className="flex flex-wrap items-center gap-2 rounded-md bg-kn-warning-soft px-3 py-2 text-fs-12 text-kn-warning-text" data-testid="stl-remainder-bar">
              <span className="min-w-0 flex-1">
                Sisa uang muka <b>{rupiahText(sr.amount)}</b> harus dikembalikan {karyawan}.
                {!canPay && " Penerimaannya dicatat pemegang izin bayar kas kecil."}
              </span>
              {canPay && (
                <button data-testid="stl-return-btn" className="btn-primary btn-sm whitespace-nowrap" disabled={busy}
                  onClick={() => setKas("return")}><Undo2 size={13} /> Terima Pengembalian Sisa {rupiahText(sr.amount)}</button>
              )}
            </div>
          )}
          {reimburseOpen && (
            <div className="flex flex-wrap items-center gap-2 rounded-md bg-kn-action-soft px-3 py-2 text-fs-12 text-kn-text" data-testid="stl-reimburse-bar">
              <span className="min-w-0 flex-1">
                Kelebihan pengeluaran <b>{rupiahText(hr.amount)}</b> harus dibayar ke {karyawan}.
                {!canPay && " Pembayarannya oleh pemegang izin bayar kas kecil."}
              </span>
              {canPay && (
                <button data-testid="stl-pay-reimburse-btn" className="btn-primary btn-sm whitespace-nowrap" disabled={busy}
                  onClick={() => setKas("reimburse")}><HandCoins size={13} /> Bayar Reimburse {rupiahText(hr.amount)}</button>
              )}
            </div>
          )}
          {hr.status === "paid" && (
            <p data-testid="stl-reimburse-paid" className="text-fs-12 font-semibold text-kn-success-text">
              Reimburse dibayar · {hr.cash_txn_number}</p>)}

          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 text-fs-12">
            <Meta k="Ref. PD" v={stl.cash_advance_number || "—"} />
            <Meta k="PT" v={entityName} />
            <Meta k="Divisi" v={stl.divisi || "—"} />
            <Meta k="Periode" v={stl.periode ? formatPeriodId(stl.periode) : "—"} />
            <Meta k="Dibuat oleh" v={stl.dibuat_oleh || "—"} />
            {stl.journal_entry_number && <Meta k="Jurnal GL" v={stl.journal_entry_number} />}
            {stl.disetujui_oleh && <Meta k="Disetujui" v={stl.disetujui_oleh} />}
          </div>

          <div>
            <div className="table-wrap">
              <table className="data-table" data-testid="stl-detail-lines">
                <thead>
                  <tr><th>Tanggal</th><th>Uraian</th><th>Kategori</th><th className="text-right">Nominal</th></tr>
                </thead>
                <tbody>
                  {(stl.expense_lines || []).map((l, i) => (
                    <tr key={i} data-testid={`stl-detail-line-${i}`}>
                      <td className="whitespace-nowrap">{fmtDate(l.date)}</td>
                      <td>{l.description || "—"}</td>
                      <td>{catLabels[l.category] || l.category}</td>
                      <td className="text-right tabular-nums font-semibold">{formatCurrency(l.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {/* Ringkasan di LUAR wadah gulir (P-05): tetap terbaca di HP walau tabel digeser. */}
            <div className="mt-2 rounded-md border border-kn-divider bg-kn-neutral-soft px-3 py-2 grid gap-1">
              <RowLine k="Total Pengeluaran" v={formatCurrency(stl.total_pengeluaran)} testId="stl-detail-total" />
              <RowLine k="Dana Diterima (PD)" v={formatCurrency(stl.total_pettycash)} />
              <RowLine k={sisaRow.k} v={formatCurrency(sisaRow.v)} strong tone={sisaRow.tone} testId="stl-detail-sisa" labelTestId="stl-detail-sisa-label" />
            </div>
          </div>

          {/* PK-24 (FY-14) — bukti pengeluaran; unggah & hapus hanya saat draf. */}
          <div className="grid gap-2" data-testid="stl-attachments">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-fs-13 font-semibold text-kn-text">Lampiran bukti ({attachments.length})</h3>
              {canAttach && (
                <>
                  <input ref={fileRef} type="file" accept="image/*,application/pdf" className="hidden" data-testid="stl-attach-input"
                    onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ""; }} />
                  <button type="button" data-testid="stl-attach-btn" className="btn-secondary btn-sm whitespace-nowrap" disabled={busy}
                    onClick={() => fileRef.current?.click()}><Paperclip size={13} /> Unggah Bukti</button>
                </>
              )}
            </div>
            {attachments.length === 0 ? (
              <p className="text-fs-12 text-kn-text-2" data-testid="stl-attachments-empty">
                {canAttach ? "Belum ada bukti. Unggah foto nota atau PDF (paling besar 10 MB)." : "Tidak ada lampiran bukti."}
              </p>
            ) : (
              <ul className="grid gap-2 sm:grid-cols-2">
                {attachments.map((a, i) => (
                  <li key={a.id} data-testid={`stl-att-${a.id}`} className="flex items-center gap-2 rounded-md border border-kn-divider px-2 py-1.5">
                    <AttachmentThumb size={36} item={attItems[i]} onOpen={() => setLihat(i)} testId={`stl-att-thumb-${a.id}`} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-fs-13 text-kn-text">{a.filename}</span>
                      <span className="block truncate text-fs-12 text-kn-text-2">{ukuran(a.size)} · {a.uploaded_by || "—"} · {formatDate(a.uploaded_at)}</span>
                    </span>
                    {canAttach && (
                      <button type="button" className="icon-button" aria-label={`Hapus lampiran ${a.filename}`} disabled={busy}
                        data-testid={`stl-att-delete-${a.id}`} onClick={() => removeAtt(a)}><Trash2 size={14} /></button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
          {stl.catatan && <p className="text-fs-12 text-kn-text"><b>Catatan:</b> {stl.catatan}</p>}
        </div>
      </section>

      <ConfirmModal open={reject} title={`Tolak ${stl.number}`} message="Berikan alasan penolakan LPJ. Pembuatnya bisa memperbaiki dan mengajukannya lagi."
        confirmLabel="Tolak LPJ" danger withReason reasonLabel="Alasan" reasonPlaceholder="mis. Bukti tidak lengkap"
        onConfirm={async (reason) => { setReject(false); await act("reject", { note: reason }, `${stl.number} ditolak.`); }}
        onCancel={() => setReject(false)} testId="stl-reject-modal" />

      {kas && (
        <SettlementCashModal mode={kas} entities={entities} onClose={() => setKas("")}
          stl={{ id: stl.id, number: stl.number, entity_id: stl.entity_id, employee: karyawan,
            amount: kas === "return" ? sr.amount : hr.amount }}
          onDone={(d) => {
            setKas("");
            flash(kas === "return"
              ? `Sisa uang muka ${stl.number} diterima (${d?.sisa_dikembalikan?.cash_txn_number || "kas masuk"}).`
              : `Kelebihan LPJ ${stl.number} dibayar ke karyawan (hutang reimburse dilunasi dari kas).`);
            onChanged(d);
          }} />
      )}
      {lihat >= 0 && <MediaLightbox items={attItems} index={lihat} onClose={() => setLihat(-1)} testId="stl-att-lightbox" />}
    </div>
  );
}

function ukuran(n) {
  const b = Number(n) || 0;
  if (b >= 1024 * 1024) return `${(b / (1024 * 1024)).toLocaleString("id-ID", { maximumFractionDigits: 1 })} MB`;
  return `${Math.max(1, Math.round(b / 1024)).toLocaleString("id-ID")} KB`;
}
function Meta({ k, v }) {
  return (<div className="flex gap-2"><span className="text-kn-text-2 w-24 shrink-0">{k}</span><span className="font-semibold min-w-0 break-words">{v}</span></div>);
}
function RowLine({ k, v, strong, tone, testId, labelTestId }) {
  return (<div className="flex justify-between gap-2 text-fs-12"><span className="text-kn-text" data-testid={labelTestId}>{k}</span><span data-testid={testId} className={`tabular-nums ${strong ? "font-bold" : "font-semibold"} ${tone || ""}`}>{v}</span></div>);
}
