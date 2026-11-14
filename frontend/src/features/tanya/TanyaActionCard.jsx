import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, Hourglass, Loader2, Wand2, XCircle } from "lucide-react";
import { useEntityScope } from "../../context/EntityScopeContext";
import { toast } from "../../hooks/use-toast";
import { docStatusLabel } from "../../utils/docStatus";
import { entityShortById } from "../../utils/entityLabel";
import { formatCurrency, formatDateTime } from "../../utils/formatters";
import { confirmAction, dismissAction, fetchAction } from "./tanyaApi";

// AG-T1 — status kartu = ikon + teks + warna (KN_37 §1 butir 3). `failed` dan `expired` tidak bisa diulang.
// Label lewat `docStatusLabel` (peta lokal kartu didahulukan) → kode status tak dikenal tidak pernah tampil mentah.
const STATUS_LABEL = {
  pending: "Menunggu persetujuan", running: "Sedang diproses", confirmed: "Sudah disetujui", dismissed: "Diabaikan",
  failed: "Gagal", expired: "Kedaluwarsa",
};
const STATUS_TONE = {
  pending: { Icon: Clock3, tone: "bg-kn-warning-soft text-kn-warning-text" },
  running: { Icon: Loader2, tone: "bg-kn-action-soft text-kn-action", spin: true },
  confirmed: { Icon: CheckCircle2, tone: "bg-kn-success-soft text-kn-success-text" },
  dismissed: { Icon: XCircle, tone: "bg-kn-neutral-soft text-kn-neutral" },
  failed: { Icon: AlertTriangle, tone: "bg-kn-danger-soft text-kn-danger-text" },
  expired: { Icon: Hourglass, tone: "bg-kn-neutral-soft text-kn-neutral" },
};

function StatusPill({ status }) {
  const s = STATUS_TONE[status] || { Icon: Clock3, tone: "bg-kn-neutral-soft text-kn-neutral" };
  const { Icon } = s;
  return (
    <span className={`status-pill ${s.tone}`} data-testid="tanya-action-pill">
      <Icon size={12} aria-hidden="true" className={s.spin ? "animate-spin" : ""} />{docStatusLabel(status, STATUS_LABEL)}
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

/** Kartu draf tindakan dari AI (blok kn-action). Baru dijalankan setelah pengguna menekan Setujui. */
export function TanyaActionCard({ proposalId }) {
  const { selectedEntity, entities, canWrite } = useEntityScope();
  const [doc, setDoc] = useState(null);
  const [qty, setQty] = useState({});
  const [busy, setBusy] = useState(false);
  useEffect(() => { fetchAction(proposalId).then(setDoc).catch(() => setDoc({ missing: true })); }, [proposalId]);
  if (!doc) return <div className="tanya-stream-block"><Loader2 className="h-4 w-4 animate-spin inline" /> Memuat draf…</div>;
  if (doc.missing) return null;
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
