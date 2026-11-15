/**
 * PenaltyPanel — FASE G-2 · daftar & keputusan **nota denda keterlambatan**.
 *
 * Denda lahir sebagai USULAN (draft, tanpa jurnal) supaya masih bisa dinegosiasikan.
 * Panel ini memberi jalan resmi untuk keputusannya: **Terbitkan** · **Bebaskan** ·
 * **Ubah Nominal** · **Catat Pembayaran** — dua yang di tengah WAJIB memilih label
 * alasan, sehingga tidak ada denda yang hilang diam-diam.
 *
 * Fase 4 · R2 (L-03) — dialog keputusan `.modal-card` buatan sendiri → `FormModal` baku (Esc, klik latar gestur
 * utuh, layar penuh di HP); galat tetap di DALAM pop-up (`penalty-dialog-error`). "Terbitkan" (menjurnal piutang
 * denda) kini dikonfirmasi dulu lewat `askConfirm`. Testid tetap (`penalty-dialog`, `penalty-dialog-*`).
 *
 * CR-T4 — tiap nota menulis "Aturan dari: PT · pelanggan · rencana" (asal unsur aturan, `policy_snapshot.sources`);
 * nota beberapa pelanggan dikelompokkan per pelanggan (judul kelompok: nama, jumlah nota, Σ nominal). Bentuk nota tetap
 * PK-08: satu nota per baris tagihan per bulan.
 */
import MoneyInput from "../../../components/MoneyInput";
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, BadgeDollarSign, Ban, Loader2, PencilLine, Receipt, Send } from "lucide-react";
import KNSelect from "../../../components/KNSelect";
import FormModal from "../../../components/FormModal";
import { askConfirm } from "../../../services/confirmService";
import { openTrace } from "../../documents/trace/traceDeepLink";
import {
  adjustPenalty, errText, fetchMeta, issuePenalty, money, payPenalty, penaltyAccounts, penaltyMeta, waivePenalty,
} from "./paymentApi";
import { can } from "../../../config/roles";
import useIntentKey from "../../../hooks/useIntentKey";
import { sourceText } from "./penaltyRuleUi";

/** CR-T4 — nota per pelanggan, urut nama (nota tanpa nama pelanggan dikelompokkan terakhir). */
function groupByCustomer(rows) {
  const map = new Map();
  rows.forEach((p) => {
    const key = p.customer_id || p.customer_name || "";
    if (!map.has(key)) map.set(key, { key, name: p.customer_name || "Tanpa nama pelanggan", rows: [] });
    map.get(key).rows.push(p);
  });
  return [...map.values()].sort((a, b) => (a.key ? 0 : 1) - (b.key ? 0 : 1) || a.name.localeCompare(b.name, "id"));
}

export default function PenaltyPanel({ rows = [], currentUser, entityId = "", onChanged }) {
  const [reasons, setReasons] = useState([]);
  const [dialog, setDialog] = useState(null);   // {kind:'waive'|'adjust'|'pay', row}
  const [reasonCode, setReasonCode] = useState("");
  const [note, setNote] = useState("");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  // PK-08 — rekening penerima (wajib) + kunci idempotensi per niat bayar.
  const [accounts, setAccounts] = useState([]);
  const [accountId, setAccountId] = useState("");
  const payIntent = useIntentKey("pnl");
  // PK-12 — keputusan denda lain juga berkunci Idempotency-Key, satu instans per aksi.
  const issueIntent = useIntentKey("pnl-terbit");
  const waiveIntent = useIntentKey("pnl-bebas");
  const adjustIntent = useIntentKey("pnl-ubah");
  const openPay = async (p) => {
    setErr(""); setAccountId("");
    setAmount(String(Math.max(0, Number(p.amount || 0) - Number(p.paid_amount || 0))));
    setDialog({ kind: "pay", row: p });
    try {
      const list = await penaltyAccounts(p.entity_id || entityId);
      setAccounts(list);
      if (list.length === 1) setAccountId(list[0].id);
    } catch { setAccounts([]); }
  };

  // Sisir gerbang peran (2026-10-20): satu izin per aksi = endpoint /penalties/{id}/issue|adjust|waive|pay.
  const canIssue = can(currentUser?.permissions, "penalty", "issue");
  const canAdjust = can(currentUser?.permissions, "penalty", "adjust");
  const canWaive = can(currentUser?.permissions, "penalty", "waive");
  const canPay = can(currentUser?.permissions, "penalty", "pay");

  useEffect(() => {
    (async () => {
      try { setReasons((await fetchMeta(entityId)).reasons || []); }
      catch { setReasons([]); }
    })();
  }, [entityId]);

  const act = useCallback(async (kind, row) => {
    if (kind === "issue" && !(await askConfirm({
      title: `Terbitkan denda ${row.number}?`,
      message: `Denda ${money(row.amount)} diterbitkan dan dijurnal ke piutang denda pelanggan.`,
      confirmLabel: "Terbitkan",
    }))) return;
    setBusy(row.id); setErr("");
    try {
      if (kind === "issue") {
        await issueIntent.send({ id: row.id, aksi: "issue" }, (key) => issuePenalty(row.id, key));
      }
      if (kind === "waive") {
        const body = { reason_code: reasonCode, note };
        await waiveIntent.send({ id: row.id, aksi: "waive", ...body }, (key) => waivePenalty(row.id, body, key));
      }
      if (kind === "adjust") {
        const body = { amount: Number(amount || 0), reason_code: reasonCode, note };
        await adjustIntent.send({ id: row.id, aksi: "adjust", ...body }, (key) => adjustPenalty(row.id, body, key));
      }
      if (kind === "pay") {
        const body = { amount: Number(amount || 0), account_id: accountId, method: "transfer" };
        await payIntent.send({ id: row.id, ...body }, (key) => payPenalty(row.id, body, key));
      }
      setDialog(null); setReasonCode(""); setNote(""); setAmount("");
      if (onChanged) onChanged();
    } catch (e) { setErr(errText(e, "Aksi denda gagal.")); }
    finally { setBusy(""); }
  }, [reasonCode, note, amount, accountId, payIntent, issueIntent, waiveIntent, adjustIntent, onChanged]);

  if (!rows.length) {
    return (
      <div data-testid="penalty-panel-empty"
        className="rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-3 text-center">
        <BadgeDollarSign size={20} className="mx-auto mb-1 text-[#C4C5CC]" />
        <p className="text-[11.5px] font-semibold text-[#3C3C43]">Belum ada denda keterlambatan.</p>
        <p className="text-[10.5px] text-[#6B6B73]">
          Usulan denda dibuat otomatis saat baris jadwal melewati jatuh tempo + masa tenggang.
        </p>
      </div>
    );
  }

  return (
    <div data-testid="penalty-panel" className="space-y-1.5">
      {err && !dialog && <div className="notice-bar danger !py-1.5" data-testid="penalty-error">
        <span className="text-[11.5px]">{err}</span></div>}
      {groupByCustomer(rows).map((g, gi, groups) => (
        <div key={g.key || `g${gi}`} className="space-y-1.5" data-testid={`penalty-group-${gi}`}>
          {groups.length > 1 && (
            <div className="flex flex-wrap items-center justify-between gap-2 pt-1" data-testid={`penalty-group-head-${gi}`}>
              <span className="text-fs-13 font-bold text-kn-text">{g.name}</span>
              <span className="text-fs-12 text-kn-text-2 tabular-nums">
                {g.rows.length} nota · {money(g.rows.reduce((a, r) => a + Number(r.amount || 0), 0))}
              </span>
            </div>
          )}
          {g.rows.map((p) => {
            const meta = penaltyMeta(p.status);
            const asal = sourceText(p.policy_snapshot?.sources);
            return (
              <div key={p.id} data-testid={`penalty-row-${p.id}`}
                className="rounded-md border border-[#EFF0F2] bg-white px-2.5 py-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <button type="button" data-testid={`penalty-trace-${p.id}`}
                        onClick={() => openTrace({ docType: "penalty", docId: p.id, number: p.number })}
                        className="text-[11.5px] font-bold text-[#0058CC] hover:underline">
                        {p.number}
                      </button>
                      <span className="rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide"
                        style={{ background: meta.bg, color: meta.fg }}>{meta.label}</span>
                    </div>
                    <p className="truncate text-[10.5px] text-[#6B6B73]">
                      {p.line_label} · jatuh tempo {(p.due_date || "").slice(0, 10)} · telat {p.days_late} hari
                      {Number(p.days_prior || 0) > 0 ? ` (${p.billable_days} hari di nota ini)` : ""}
                      {p.reason_label ? ` · ${p.reason_label}` : ""}
                    </p>
                    {(p.explain || []).length > 0 && (
                      <p className="truncate text-[9.5px] text-[#9A9BA3]" title={(p.explain || []).join(" · ")}>
                        {(p.explain || [])[2] || (p.explain || [])[0]}
                      </p>
                    )}
                    {asal && (
                      <p className="text-fs-12 text-kn-text-2" data-testid={`penalty-source-${p.id}`}>Aturan dari: {asal}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[12.5px] font-bold tabular-nums" data-testid={`penalty-amount-${p.id}`}>
                      {money(p.amount)}
                    </span>
                    {canIssue && p.status === "draft" && (
                      <button type="button" className="secondary-button !py-1" data-testid={`penalty-issue-${p.id}`}
                        disabled={busy === p.id} onClick={() => act("issue", p)}>
                        {busy === p.id ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />} Terbitkan
                      </button>
                    )}
                    {(canAdjust || canWaive) && ["draft", "issued", "adjusted"].includes(p.status) && (
                      <>
                        {canAdjust && <button type="button" className="secondary-button !py-1" data-testid={`penalty-adjust-${p.id}`}
                          onClick={() => { setErr(""); setDialog({ kind: "adjust", row: p }); setAmount(String(p.amount)); }}>
                          <PencilLine size={12} /> Ubah Nominal
                        </button>}
                        {canWaive && <button type="button" className="secondary-button !py-1" data-testid={`penalty-waive-${p.id}`}
                          onClick={() => { setErr(""); setDialog({ kind: "waive", row: p }); }}>
                          <Ban size={12} /> Bebaskan
                        </button>}
                      </>
                    )}
                    {canPay && ["issued", "adjusted"].includes(p.status) && (
                      <button type="button" className="secondary-button !py-1" data-testid={`penalty-pay-${p.id}`}
                        onClick={() => openPay(p)}>
                        <Receipt size={12} /> Catat Bayar
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ))}

      {dialog && (
        <FormModal open onClose={() => setDialog(null)} size="sm" testId="penalty-dialog" busy={busy !== ""}
          icon={dialog.kind === "waive" ? Ban : dialog.kind === "adjust" ? PencilLine : Receipt}
          title={`${dialog.kind === "waive" ? "Bebaskan Denda"
            : dialog.kind === "adjust" ? "Ubah Nominal Denda" : "Catat Pembayaran Denda"} · ${dialog.row.number}`}
          subtitle={dialog.kind === "pay"
            ? "Pembayaran akan dijurnal: Kas/Bank naik, Piutang Denda turun."
            : "Keputusan ini tercatat lengkap dengan alasan & nama pemutus. Denda yang sudah berjurnal dikoreksi lewat jurnal pembalik (tidak dihapus)."}
          footer={(
            <div className="flex justify-end gap-2">
              <button type="button" className="secondary-button" onClick={() => setDialog(null)}
                disabled={busy !== ""} data-testid="penalty-dialog-cancel">Batal</button>
              <button type="button" className="primary-button" data-testid="penalty-dialog-submit"
                disabled={busy !== "" || (dialog.kind !== "pay" && !reasonCode) || (dialog.kind === "pay" && !accountId)}
                onClick={() => act(dialog.kind, dialog.row)}>
                {busy ? <Loader2 size={13} className="animate-spin" /> : null} Simpan keputusan
              </button>
            </div>
          )}>
          <div className="space-y-2">
            {dialog.kind !== "waive" && (
              <div className="grid gap-1">
                <label className="kicker">Nominal</label>
                <MoneyInput testId="penalty-dialog-amount" className="field tabular-nums" value={amount} onChange={(v) => setAmount(v)} />
                {dialog.kind === "pay" && (
                  <p className="text-[10.5px] text-[#6B6B73]" data-testid="penalty-dialog-paid-info">
                    Sudah dibayar {money(dialog.row.paid_amount || 0)} · sisa {money(Math.max(0, Number(dialog.row.amount || 0) - Number(dialog.row.paid_amount || 0)))}
                  </p>
                )}
              </div>
            )}
            {dialog.kind === "pay" && (
              <div className="grid gap-1">
                <label className="kicker">Rekening penerima (wajib)</label>
                <KNSelect value={accountId} onValueChange={setAccountId} className="field"
                  data-testid="penalty-dialog-account" placeholder="Pilih rekening…"
                  options={accounts.map((a) => ({ value: a.id, label: `${a.name}${a.account_number ? ` · ${a.account_number}` : ""}` }))} />
                {!accountId && (
                  <p className="flex items-center gap-1 text-[10.5px] text-[#8C4A00]" data-testid="penalty-dialog-account-hint">
                    <AlertTriangle size={11} /> Pilih rekening penerima dulu.
                  </p>
                )}
              </div>
            )}
            {dialog.kind !== "pay" && (
              <div className="grid gap-1">
                <label className="kicker">Label alasan (wajib)</label>
                <KNSelect value={reasonCode} onValueChange={setReasonCode} className="field"
                  data-testid="penalty-dialog-reason" placeholder="Pilih alasan…"
                  options={reasons.map((r) => ({ value: r.code, label: r.label }))} />
              </div>
            )}
            {dialog.kind !== "pay" && (
              <div className="grid gap-1">
                <label className="kicker">Catatan</label>
                <textarea className="field" rows={2} value={note} data-testid="penalty-dialog-note"
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Mis. hasil pembicaraan dengan pelanggan…" />
              </div>
            )}
            {err && <div className="notice-bar danger !py-1.5" data-testid="penalty-dialog-error"><span className="text-[11.5px]">{err}</span></div>}
            {dialog.kind !== "pay" && !reasonCode && (
              <p className="flex items-center gap-1 text-[10.5px] text-[#8C4A00]">
                <AlertTriangle size={11} /> Pilih label alasan dulu — server akan menolak tanpa alasan.
              </p>
            )}
          </div>
        </FormModal>
      )}
    </div>
  );
}
