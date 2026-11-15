import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, ExternalLink, Hourglass, Loader2, Repeat, UserCheck, Wand2, XCircle } from "lucide-react";
import { useAppNav } from "../../context/AppNavContext";
import { useEntityScope } from "../../context/EntityScopeContext";
import { toast } from "../../hooks/use-toast";
import { askConfirm } from "../../services/confirmService";
import { docStatusLabel } from "../../utils/docStatus";
import { entityShortById } from "../../utils/entityLabel";
import { formatCurrency, formatDate, formatDateTime } from "../../utils/formatters";
import { kpiValueParts } from "../finance/financeShared";
import { confirmAction, dismissAction, fetchAction, secondAction } from "./tanyaApi";

// AG-T1 — status kartu = ikon + teks + warna (KN_37 §1 butir 3). `failed` dan `expired` tidak bisa diulang.
// Label lewat `docStatusLabel` (peta lokal kartu didahulukan) → kode status tak dikenal tidak pernah tampil mentah.
const STATUS_LABEL = {
  pending: "Menunggu persetujuan", running: "Sedang diproses", confirmed: "Sudah disetujui", dismissed: "Diabaikan",
  failed: "Gagal", expired: "Kedaluwarsa",
};
// AG-T3 — label status kartu golongan A/B (spesifikasi): Menunggu · Sedang diproses · Berhasil · Gagal · Diabaikan ·
// Kedaluwarsa · Diganti. Dipakai juga tab "Tindakan" (`TanyaActions`).
export const CARD_STATUS_LABEL = {
  pending: "Menunggu", running: "Sedang diproses", confirmed: "Berhasil", failed: "Gagal", dismissed: "Diabaikan",
  expired: "Kedaluwarsa", superseded: "Diganti", awaiting_second: "Menunggu orang kedua",   // AG-T5
};
const STATUS_TONE = {
  pending: { Icon: Clock3, tone: "bg-kn-warning-soft text-kn-warning-text" },
  running: { Icon: Loader2, tone: "bg-kn-action-soft text-kn-action", spin: true },
  confirmed: { Icon: CheckCircle2, tone: "bg-kn-success-soft text-kn-success-text" },
  dismissed: { Icon: XCircle, tone: "bg-kn-neutral-soft text-kn-neutral" },
  failed: { Icon: AlertTriangle, tone: "bg-kn-danger-soft text-kn-danger-text" },
  expired: { Icon: Hourglass, tone: "bg-kn-neutral-soft text-kn-neutral" },
  superseded: { Icon: Repeat, tone: "bg-kn-neutral-soft text-kn-neutral" },
  awaiting_second: { Icon: UserCheck, tone: "bg-kn-warning-soft text-kn-warning-text" },   // AG-T5
};

/** Pil status kartu: ikon + teks + warna (KN_37 §1 butir 3); kode tak dikenal tidak tampil mentah (`docStatusLabel`). */
export function StatusPill({ status, labels = STATUS_LABEL, testId = "tanya-action-pill" }) {
  const s = STATUS_TONE[status] || { Icon: Clock3, tone: "bg-kn-neutral-soft text-kn-neutral" };
  const { Icon } = s;
  return (
    <span className={`status-pill ${s.tone}`} data-testid={testId}>
      <Icon size={12} aria-hidden="true" className={s.spin ? "animate-spin" : ""} />{docStatusLabel(status, labels)}
    </span>
  );
}

function PoLines({ pos, qty, setQty, editable }) {
  return pos.map((po, pi) => (
    <div key={pi} className="tanya-action-po" data-testid={`tanya-action-po-${pi}`}>
      <div className="tanya-action-po-head">{po.supplier_name} · gudang {po.warehouse_name}</div>
      {po.items.map((it, ii) => (
        <div key={ii} className="tanya-action-line">
          <span className="tanya-action-name">{it.product_name}</span>
          {editable ? (
            <input type="number" min="0" step="any" className="tanya-action-qty" value={qty[`${pi}-${ii}`] ?? it.quantity}
              aria-label={`Jumlah ${it.product_name}`}
              onChange={(e) => setQty((q) => ({ ...q, [`${pi}-${ii}`]: e.target.value }))} data-testid={`tanya-action-qty-${pi}-${ii}`} />
          ) : <b>{it.quantity}</b>}
          <span className="tanya-action-unit">{it.unit} × {formatCurrency(it.price)}</span>
        </div>
      ))}
    </div>
  ));
}

function Reminders({ items }) {
  return (
    <ul className="tanya-action-list">
      {items.map((r) => (
        <li key={r.customer_id} data-testid={`tanya-action-reminder-${r.customer_id}`}>
          <b>{r.customer}</b> → {r.sales || "Anda"}
          {r.orders ? ` · ${r.orders.length} SO · ${formatCurrency(r.outstanding)} · terlama ${r.max_days_overdue} hari` : ` · order terakhir ${r.last_order}`}
        </li>
      ))}
    </ul>
  );
}

/** Hasil kartu yang sudah tidak menunggu: disetujui, diabaikan, sedang diproses, gagal, atau kedaluwarsa. */
function Outcome({ doc }) {
  const done = doc.result || [];
  if (doc.status === "failed") return (
    <div className="tanya-action-outcome failed" data-testid="tanya-action-status" role="status">
      <p data-testid="tanya-action-error">Gagal: {doc.error || "proses berhenti tanpa keterangan."}</p>
      {done.length > 0 && <p data-testid="tanya-action-partial">Sudah dibuat sebelum gagal: {done.join(", ")}</p>}
      <p className="tanya-action-hint">Kartu ini tidak bisa diulang. Minta asisten menyiapkan draf baru untuk sisanya.</p>
    </div>
  );
  if (doc.status === "expired") return (
    <div className="tanya-action-outcome" data-testid="tanya-action-status" role="status">
      <p>Draf ini sudah kedaluwarsa. Minta asisten menyiapkannya lagi.</p>
    </div>
  );
  if (doc.status === "running") return (
    <div className="tanya-action-outcome" data-testid="tanya-action-status" role="status">
      <p>Tindakan sedang dijalankan.{done.length ? ` Sudah dibuat: ${done.join(", ")}` : ""}</p>
    </div>
  );
  return done.length > 0 ? (
    <div className="tanya-action-outcome" data-testid="tanya-action-status">
      <p>{doc.type === "draft_po" ? "PO dibuat" : "Terkirim"}: {done.join(", ")}</p>
    </div>
  ) : null;
}

const ISO_TANGGAL = /^\d{4}-\d{2}-\d{2}(T|$)/;

/** Nilai sel rencana: rupiah utuh (pola `kpiValueParts`), tanggal "15 Nov 2026" (bukan ISO mentah), teks apa adanya,
 *  kosong = "—". */
function PlanValue({ row, value }) {
  if (value === null || value === undefined || value === "") return <span className="tanya-plan-empty">—</span>;
  if (row.kind === "money" && typeof value === "number") return <span className="tabular-nums">{kpiValueParts(formatCurrency(value))}</span>;
  if (row.kind === "date" && ISO_TANGGAL.test(String(value))) return <span className="whitespace-nowrap">{formatDate(value)}</span>;
  return <span>{String(value)}</span>;
}

function PlanTable({ plan }) {
  const rows = plan?.rows || [];
  return (
    <div className="tanya-plan" data-testid="tanya-card-plan">
      <div className="tanya-kicker">Rencana</div>
      {rows.length > 0 && (
        <table className="data-table head-wrap tanya-plan-table">
          <thead><tr><th>Hal</th><th>Sekarang</th><th>Sesudah</th></tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} data-testid={`tanya-card-row-${i}`}>
                <td>{r.label}</td>
                <td><PlanValue row={r} value={r.before} /></td>
                <td><PlanValue row={r} value={r.after} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {plan?.note && <p className="tanya-action-hint" data-testid="tanya-card-note">{plan.note}</p>}
    </div>
  );
}

/** Hasil kartu golongan A/B sesudah tidak menunggu lagi. */
function CardOutcome({ doc }) {
  const { go, canOpen } = useAppNav();
  const res = doc.result || {};
  const d = res.document || null;
  if (doc.status === "confirmed") {
    const link = d?.link || {};
    return (
      <div className="tanya-action-outcome" data-testid="tanya-card-outcome" role="status">
        <p data-testid="tanya-card-success">Berhasil — {[d?.label, d?.number].filter(Boolean).join(" ")}</p>
        {res.gl_status === "posted" && <p data-testid="tanya-card-gl">Jurnal: terposting</p>}
        {res.gl_status === "failed" && (
          <p data-testid="tanya-card-gl">
            Jurnal gagal — lihat{" "}
            {canOpen("posting-failures")
              ? <button type="button" className="link-button" onClick={() => go("posting-failures")}>Posting Gagal</button>
              : "Posting Gagal"}
          </p>
        )}
        {link.view && canOpen(link.view) && (
          <div>
            <button type="button" className="secondary-button btn-sm" data-testid="tanya-card-open"
              onClick={() => go(link.view, { preset: link.tab ? { tab: link.tab } : undefined,
                focus: link.focus_id ? { type: link.focus_type, id: link.focus_id, number: link.number || d?.number } : undefined })}>
              <ExternalLink size={14} aria-hidden="true" /> Buka dokumen
            </button>
          </div>
        )}
      </div>
    );
  }
  const teks = {
    failed: `Gagal: ${doc.error || res.message || "proses berhenti tanpa keterangan."}`,
    expired: "Kedaluwarsa", superseded: "Diganti kartu yang lebih baru", dismissed: "Diabaikan",
    running: "Sedang diproses…",
  }[doc.status];
  if (!teks) return null;
  return (
    <div className={`tanya-action-outcome ${doc.status === "failed" ? "failed" : ""}`} data-testid="tanya-card-outcome" role="status">
      <p data-testid="tanya-card-result">{teks}</p>
      {doc.status === "failed" && (
        <p className="tanya-action-hint">Kartu ini tidak bisa diulang. Minta asisten menyiapkan kartu baru bila masih perlu.</p>
      )}
    </div>
  );
}

/** AG-T5 — baris "Menunggu orang kedua · disetujui {pembuat}, {tanggal jam} WIB" (semua yang membuka kartu). */
function FirstLine({ doc }) {
  if (!doc.first_by?.name || !["awaiting_second", "running", "confirmed", "failed", "dismissed", "expired"].includes(doc.status)) return null;
  const tunggu = doc.status === "awaiting_second";
  return (
    <p className="tanya-action-meta" data-testid="tanya-card-first">
      {tunggu ? "Menunggu orang kedua · " : ""}disetujui {doc.first_by.name}, {formatDateTime(doc.first_at)}
      {doc.second_by?.name ? ` · orang kedua ${doc.second_by.name}, ${formatDateTime(doc.second_at)}` : ""}
    </p>
  );
}

/**
 * AG-T5 — kartu golongan C yang menunggu orang kedua. Orang kedua (`can_second`): rencana + alasan pembuat, isian
 * "Alasan" (wajib saat menolak), "Setujui dan jalankan" (konfirmasi nominal, PT, pembuat) dan "Tolak". Selain itu
 * alasan tertulis kenapa tidak bisa memutus (`second_block`); pembuat bisa menarik kartunya ("Abaikan").
 */
function SecondPanel({ doc, proposalId, ptName, onDone }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const plan = doc.plan || {};
  const run = async (fn, okMsg) => {
    setBusy(true);
    try {
      const d = await fn();
      onDone(d);
      if (d.status === "failed") toast({ title: "Tindakan gagal", description: d.error || "", variant: "destructive" });
      else toast({ title: okMsg });
    } catch (e) {
      toast({ title: "Gagal", description: e?.response?.data?.detail || "", variant: "destructive" });
      if ([403, 409].includes(e?.response?.status)) fetchAction(proposalId).then(onDone).catch(() => {});
    } finally { setBusy(false); }
  };
  const approve = async () => {
    if (!(await askConfirm({
      title: "Jalankan kartu tindakan?",
      message: `Jalankan ${doc.title} sebesar ${formatCurrency(Number(plan.amount) || 0)} untuk ${ptName} atas permintaan ${doc.first_by?.name || doc.user_name || "pembuat kartu"}?`,
      confirmLabel: "Ya, jalankan", cancelLabel: "Batal", testId: "tanya-card-second-confirm",
    }))) return;
    await run(() => secondAction(proposalId, "approve", reason.trim()), "Kartu dijalankan");
  };
  const rejectOk = reason.trim().length >= 10;
  return (
    <div className="tanya-card-second" data-testid="tanya-card-second">
      {doc.reason && <p className="tanya-note" data-testid="tanya-card-maker-reason">Alasan pembuat: {doc.reason}</p>}
      {doc.can_second ? (<>
        <div className="tanya-card-fields">
          <label className="tanya-card-field">
            <span>Alasan</span>
            <input type="text" className="input-field" placeholder="Wajib diisi bila menolak (minimal 10 huruf)."
              value={reason} maxLength={500} disabled={busy} onChange={(e) => setReason(e.target.value)}
              data-testid="tanya-card-second-reason" />
          </label>
        </div>
        <div className="tanya-answer-actions tanya-action-buttons">
          <button type="button" className="primary-button btn-sm" disabled={busy} data-testid="tanya-card-second-approve"
            onClick={approve}>
            {busy ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <CheckCircle2 size={14} aria-hidden="true" />}
            Setujui dan jalankan
          </button>
          <button type="button" className="secondary-button btn-sm" disabled={busy || !rejectOk} data-testid="tanya-card-second-reject"
            onClick={() => run(() => secondAction(proposalId, "reject", reason.trim()), "Kartu ditolak")}>
            <XCircle size={14} aria-hidden="true" /> Tolak
          </button>
          {!rejectOk && <p className="tanya-action-hint" data-testid="tanya-card-second-hint">Tulis alasan (minimal 10 huruf) untuk menolak.</p>}
        </div>
      </>) : (
        <div className="tanya-answer-actions tanya-action-buttons">
          {doc.is_maker && (
            <button type="button" className="secondary-button btn-sm" disabled={busy} data-testid="tanya-action-dismiss"
              onClick={() => run(() => dismissAction(proposalId), "Kartu ditarik")}>
              <XCircle size={14} aria-hidden="true" /> Abaikan
            </button>
          )}
          <p className="tanya-action-hint" data-testid="tanya-card-second-block">
            {doc.is_maker ? "Kartu ini dijalankan sesudah orang lain yang berwenang menyetujuinya." : doc.second_block}
          </p>
        </div>
      )}
    </div>
  );
}

const EDIT_INPUT = { date: "date", text: "text" };

/**
 * AG-T3 — kartu tindakan golongan A/B: rencana sebelum → sesudah, isian alasan / ketik ulang nominal menurut tingkat,
 * tombol "Setujui dan jalankan" (mati beralasan tertulis) dan "Abaikan". Server menjalankan endpoint layar tepat sekali.
 */
function ActionCardV2({ doc, setDoc, proposalId, onChanged }) {
  const { selectedEntity, entities, canWrite } = useEntityScope();
  const [reason, setReason] = useState("");
  const [retype, setRetype] = useState("");
  const [edits, setEdits] = useState({});
  const [busy, setBusy] = useState(false);
  const pending = doc.status === "pending";
  const plan = doc.plan || {};
  const ptName = doc.entity_name || entityShortById(entities, doc.entity_id, "PT kartu");
  const needReason = doc.risk === "medium" || doc.risk === "high";
  const needRetype = doc.risk === "high";
  const combined = !canWrite || selectedEntity === "all";
  const wrongPt = !combined && selectedEntity !== doc.entity_id;
  const digits = (v) => String(v || "").replace(/\D/g, "");
  const reasonOk = !needReason || reason.trim().length >= 10;
  const retypeOk = !needRetype || (digits(retype) !== "" && digits(retype) === digits(plan.confirm_text));
  let blocked = "";
  if (combined) blocked = "Pilih satu PT untuk menyetujui kartu.";
  else if (wrongPt) blocked = `Pindah ke ${ptName} untuk menyetujui.`;
  else if (!reasonOk && !retypeOk) blocked = "Tulis alasan (minimal 10 huruf) dan ketik ulang nominal untuk menyetujui.";
  else if (!reasonOk) blocked = "Tulis alasan (minimal 10 huruf) untuk menyetujui.";
  else if (!retypeOk) blocked = "Ketik ulang nominal persis seperti di kartu untuk menyetujui.";
  const done = (d) => { setDoc(d); onChanged?.(d); };
  const run = async (fn, okMsg) => {
    setBusy(true);
    try {
      const d = await fn();
      done(d);
      if (d.status === "failed") toast({ title: "Tindakan gagal", description: d.error || "", variant: "destructive" });
      else if (d.status === "awaiting_second") toast({ title: "Kartu menunggu persetujuan orang kedua" });   // AG-T5
      else toast({ title: okMsg });
    } catch (e) {
      toast({ title: "Gagal", description: e?.response?.data?.detail || "", variant: "destructive" });
      if (e?.response?.status === 409) fetchAction(proposalId).then(done).catch(() => {});   // status terkini
    } finally { setBusy(false); }
  };
  const approve = async () => {
    if (Number(plan.amount) > 0 && !(await askConfirm({
      title: "Jalankan kartu tindakan?",
      message: `Jalankan ${doc.title} sebesar ${formatCurrency(Number(plan.amount))} untuk ${ptName}?`,
      confirmLabel: "Ya, jalankan", cancelLabel: "Batal", testId: "tanya-card-confirm-modal",
    }))) return;
    const ed = Object.fromEntries(Object.entries(edits).filter(([k, v]) => v !== undefined && v !== (doc.args || {})[k]));
    await run(() => confirmAction(proposalId, Object.keys(ed).length ? ed : null, { reason: reason.trim(), retype }),
      "Kartu dijalankan");
  };
  return (
    <section className={`tanya-action ${doc.status}`} data-testid={`tanya-action-${proposalId}`}>
      <div className="tanya-action-head">
        <div className="tanya-kicker"><Wand2 className="h-4 w-4" aria-hidden="true" /> Kartu tindakan · {doc.title}</div>
        <StatusPill status={doc.status} labels={CARD_STATUS_LABEL} />
      </div>
      <p className="tanya-action-meta" data-testid="tanya-action-meta">
        PT: {ptName}{(pending || doc.status === "awaiting_second") && doc.expires_at ? ` · berlaku sampai ${formatDateTime(doc.expires_at)}` : ""}
      </p>
      {plan.summary && <p className="tanya-note" data-testid="tanya-card-summary">{plan.summary}</p>}
      <PlanTable plan={plan} />
      <FirstLine doc={doc} />
      {pending && (doc.editable || []).length > 0 && (
        <div className="tanya-card-fields" data-testid="tanya-card-edits">
          {(doc.editable || []).map((e) => (
            <label key={e.path} className="tanya-card-field">
              <span>{e.label}</span>
              <input type={EDIT_INPUT[e.kind] || "text"} className="input-field" disabled={busy}
                value={edits[e.path] ?? (doc.args || {})[e.path] ?? ""} data-testid={`tanya-card-edit-${e.path}`}
                onChange={(ev) => setEdits((x) => ({ ...x, [e.path]: ev.target.value }))} />
            </label>
          ))}
        </div>
      )}
      {pending && (needReason || needRetype) && (
        <div className="tanya-card-fields">
          {needReason && (
            <label className="tanya-card-field">
              <span>Alasan</span>
              <input type="text" className="input-field" placeholder="Mengapa tindakan ini dilakukan?" value={reason}
                maxLength={500} disabled={busy} onChange={(e) => setReason(e.target.value)} data-testid="tanya-card-reason" />
            </label>
          )}
          {needRetype && (
            <label className="tanya-card-field">
              <span>Ketik ulang nominal</span>
              <input type="text" inputMode="numeric" className="input-field" placeholder={`Ketik ${plan.confirm_text} untuk menyetujui.`}
                value={retype} disabled={busy} onChange={(e) => setRetype(e.target.value)} data-testid="tanya-card-retype" />
            </label>
          )}
        </div>
      )}
      {pending ? (
        <div className="tanya-answer-actions tanya-action-buttons">
          <button type="button" className="primary-button btn-sm" disabled={busy || !!blocked} data-testid="tanya-action-confirm"
            onClick={approve}>
            {busy ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <CheckCircle2 size={14} aria-hidden="true" />}
            Setujui dan jalankan
          </button>
          <button type="button" className="secondary-button btn-sm" disabled={busy} data-testid="tanya-action-dismiss"
            onClick={() => run(() => dismissAction(proposalId), "Kartu diabaikan")}>
            <XCircle size={14} aria-hidden="true" /> Abaikan
          </button>
          {blocked && <p className="tanya-action-hint" data-testid="tanya-action-pt-hint">{blocked}</p>}
          {doc.second_preview && (
            <p className="tanya-action-hint" data-testid="tanya-card-second-preview">
              Kartu ini akan menunggu persetujuan orang kedua sebelum dijalankan.
            </p>
          )}
        </div>
      ) : doc.status === "awaiting_second"
        ? <SecondPanel doc={doc} proposalId={proposalId} ptName={ptName} onDone={done} />
        : <CardOutcome doc={doc} />}
    </section>
  );
}

/** Kartu tindakan dari AI (blok kn-action, juga tab "Tindakan"). Baru dijalankan setelah pengguna menekan Setujui. */
export function TanyaActionCard({ proposalId, initial = null, onChanged }) {
  const { selectedEntity, entities, canWrite } = useEntityScope();
  const [doc, setDoc] = useState(initial);
  const [qty, setQty] = useState({});
  const [busy, setBusy] = useState(false);
  useEffect(() => { fetchAction(proposalId).then(setDoc).catch(() => setDoc({ missing: true })); }, [proposalId]);
  if (!doc) return <div className="tanya-stream-block"><Loader2 className="h-4 w-4 animate-spin inline" /> Memuat kartu…</div>;
  if (doc.missing) return null;
  if (doc.class) return <ActionCardV2 doc={doc} setDoc={setDoc} proposalId={proposalId} onChanged={onChanged} />;
  const pending = doc.status === "pending";
  const ptName = doc.entity_name || entityShortById(entities, doc.entity_id, "PT kartu");
  // AG-T1 — kartu hanya bisa disetujui saat PT aktif = PT kartu. Akun satu-PT (`canWrite` selalu benar) tidak pernah
  // berada di mode gabungan, jadi "Semua PT" di kepala aplikasi berarti PT rumahnya sendiri.
  const wrongPt = !canWrite || (selectedEntity !== "all" && selectedEntity !== doc.entity_id);
  const edits = () => ({ pos: (doc.payload.pos || []).map((po, pi) => ({ items: po.items.map((it, ii) => ({ quantity: Number(qty[`${pi}-${ii}`] ?? it.quantity) })) })) });
  const act = async (fn, okMsg) => {
    setBusy(true);
    try {
      const d = await fn();
      setDoc(d);
      if (d.status === "failed") toast({ title: "Tindakan gagal", description: d.message || d.error || "", variant: "destructive" });
      else toast({ title: okMsg });
    } catch (e) {
      toast({ title: "Gagal", description: e?.response?.data?.detail || "", variant: "destructive" });
      if (e?.response?.status === 409) fetchAction(proposalId).then(setDoc).catch(() => {});   // tampilkan status terkini
    } finally { setBusy(false); }
  };
  return (
    <section className={`tanya-action ${doc.status}`} data-testid={`tanya-action-${proposalId}`}>
      <div className="tanya-action-head">
        <div className="tanya-kicker"><Wand2 className="h-4 w-4" aria-hidden="true" /> Draf tindakan · {doc.title}</div>
        <StatusPill status={doc.status} />
      </div>
      <p className="tanya-action-meta" data-testid="tanya-action-meta">
        PT: {ptName}{pending && doc.expires_at ? ` · berlaku sampai ${formatDateTime(doc.expires_at)}` : ""}
      </p>
      {doc.reason && <p className="tanya-note" data-testid="tanya-action-reason">{doc.reason}</p>}
      {doc.type === "draft_po" ? <PoLines pos={doc.payload.pos} qty={qty} setQty={setQty} editable={pending} /> : <Reminders items={doc.payload.reminders} />}
      {pending ? (
        <div className="tanya-answer-actions tanya-action-buttons">
          <button type="button" className="primary-button btn-sm" disabled={busy || wrongPt} data-testid="tanya-action-confirm"
            onClick={() => act(() => confirmAction(proposalId, doc.type === "draft_po" ? edits() : null), "Tindakan dijalankan")}>
            {busy ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <CheckCircle2 size={14} aria-hidden="true" />}
            {doc.type === "draft_po" ? "Setujui & buat PO" : "Setujui & kirim ke sales"}
          </button>
          <button type="button" className="secondary-button btn-sm" disabled={busy} data-testid="tanya-action-dismiss"
            onClick={() => act(() => dismissAction(proposalId), "Draf diabaikan")}>
            <XCircle size={14} aria-hidden="true" /> Abaikan
          </button>
          {wrongPt && <p className="tanya-action-hint" data-testid="tanya-action-pt-hint">Pindah ke {ptName} untuk menyetujui.</p>}
        </div>
      ) : <Outcome doc={doc} />}
    </section>
  );
}
