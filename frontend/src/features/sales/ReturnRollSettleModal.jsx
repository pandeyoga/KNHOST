/** UAT 23 Okt (permintaan pemilik) — Selesaikan retur PER ROLL: outcome campuran & boleh bertahap.
 *  Tiap roll: Pengembalian Dana / Store Credit / Tukar Barang (roll kembali ke stok, qty aktual QC) · Cutloss (qty cacat
 *  catatan MD; potongan baik kembali ke pelanggan) · Diskon (nominal Finance) · Tolak klaim. Roll yang belum siap dibiarkan
 *  "Belum diputus" dan diputus di penyelesaian berikutnya. Nilai, pembagian dana & jurnal dihitung server
 *  (`/roll-settlement/preview` — fungsi yang sama dengan penyimpanan). */
import { useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { CheckCircle2, Loader2, X, Info } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { apiErrorText } from "../../utils/apiError";
import { SettleValuePanel } from "./ReturnSettleModal";

const NEGO = ["cutloss", "discount"];
const qty = (v, unit) => (v ? `${formatQty(v)} ${unit || ""}` : "—");

export default function ReturnRollSettleModal({ ret, open, onClose, onDone }) {
  const [state, setState] = useState(null);
  const [loadErr, setLoadErr] = useState("");
  const [dec, setDec] = useState({});
  const [payout, setPayout] = useState("store_credit");
  const [cashAccounts, setCashAccounts] = useState([]);
  const [refundAccount, setRefundAccount] = useState("");
  const [decisionNote, setDecisionNote] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [pv, setPv] = useState(null);
  const [pvErr, setPvErr] = useState("");
  const [pvBusy, setPvBusy] = useState(false);

  useEffect(() => {
    if (!open) return undefined;
    let alive = true;
    setState(null); setLoadErr(""); setDec({}); setErr(""); setPv(null);
    (async () => {
      try {
        const [r, acc] = await Promise.all([
          axios.get(`${API}/sales-returns/${ret.id}/roll-settlement`),
          axios.get(`${API}/gl/cash-accounts`).catch(() => ({ data: [] })),
        ]);
        if (!alive) return;
        setState(r.data);
        setCashAccounts(Array.isArray(acc.data) ? acc.data : []);
      } catch (e) { if (alive) setLoadErr(apiErrorText(e, "Data roll retur gagal dimuat.")); }
    })();
    return () => { alive = false; };
  }, [open, ret.id]);

  const chosen = Object.entries(dec).filter(([, v]) => v).map(([roll_id, outcome]) => ({ roll_id, outcome }));
  const hasNego = chosen.some((d) => NEGO.includes(d.outcome));
  const hasRefund = chosen.some((d) => d.outcome === "refund") || (hasNego && payout === "refund");
  const pvKey = JSON.stringify([chosen, hasNego ? payout : "", hasRefund ? refundAccount : ""]);
  useEffect(() => {
    const [rolls, po, acc] = JSON.parse(pvKey);
    if (!open || !rolls.length) { setPv(null); setPvErr(""); setPvBusy(false); return undefined; }
    let alive = true;
    setPvBusy(true);
    const t = setTimeout(async () => {
      try {
        const r = await axios.post(`${API}/sales-returns/${ret.id}/roll-settlement/preview`, { rolls, payout: po, refund_account_code: acc });
        if (alive) { setPv(r.data); setPvErr(""); }
      } catch (e) {
        if (alive) { setPv(null); setPvErr(apiErrorText(e, "Nilai penyelesaian belum bisa dihitung.")); }
      } finally { if (alive) setPvBusy(false); }
    }, 300);
    return () => { alive = false; clearTimeout(t); };
  }, [open, ret.id, pvKey]);

  if (!open) return null;
  const rows = state?.rows || [];
  const pvRoll = Object.fromEntries((pv?.rolls || []).map((r) => [r.roll_id, r]));
  const openRows = rows.filter((r) => !r.settled?.outcome);

  async function confirm() {
    setBusy(true); setErr("");
    try {
      await axios.post(`${API}/sales-returns/${ret.id}/roll-settlement`, {
        rolls: chosen, payout: hasNego ? payout : "", refund_account_code: hasRefund ? refundAccount : "",
        decision_note: decisionNote, notes,
      });
      if (onDone) await onDone();
      onClose();
    } catch (e) {
      setErr(apiErrorText(e, "Penyelesaian gagal disimpan."));
    } finally { setBusy(false); }
  }

  return (
    <div className="modal-overlay" data-testid="roll-settle-modal">
      <div className="modal-card" style={{ maxWidth: 1040 }}>
        <div className="mb-1 flex items-center justify-between">
          <h3 className="modal-title">Selesaikan Retur {ret.number} — per roll</h3>
          <button className="icon-button" onClick={onClose}><X size={15} /></button>
        </div>
        <p className="modal-subtitle">
          Pilih outcome tiap roll. Roll yang belum siap biarkan <b>Belum diputus</b> — diputus di penyelesaian berikutnya.
        </p>
        {loadErr && <p className="mt-2 rounded-md bg-[#FDECEC] px-2.5 py-1.5 text-[12px] text-[#A8221A]" data-testid="roll-settle-load-error">{loadErr}</p>}
        {!state && !loadErr && <p className="mt-3 text-[12px] text-[#6B6B73]"><Loader2 size={13} className="spin mr-1 inline" />Memuat roll…</p>}

        {state && (
          <div className="section-card mt-3 overflow-x-auto" style={{ margin: 0 }}>
            <table className="data-table" data-testid="roll-settle-table">
              <thead>
                <tr><th>Roll</th><th>Barang</th><th>QC aktual</th><th>Outcome</th>
                  <th className="text-right">Ke stok</th><th className="text-right">Dipotong</th>
                  <th className="text-right">Kembali ke pelanggan</th><th className="text-right">Nilai (DPP)</th></tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const done = r.settled?.outcome;
                  const p = done ? r.settled : pvRoll[r.roll_id];
                  const off = (r.options || []).filter((o) => !o.ok);
                  return (
                    <tr key={r.roll_id} data-testid={`roll-settle-row-${r.roll_no}`} className={done ? "opacity-70" : ""}>
                      <td className="font-mono text-[12px] font-semibold">{r.roll_no}</td>
                      <td className="text-[12px]">{r.product_name}</td>
                      <td className="text-[12px] tabular-nums">{qty(r.actual_qty, r.unit)}{r.grade ? ` · ${r.grade}` : ""}</td>
                      <td style={{ minWidth: 190 }}>
                        {done ? (
                          <span className="text-[12px] font-semibold text-[#1A7F37]" data-testid={`roll-settle-done-${r.roll_no}`}>
                            <CheckCircle2 size={12} className="mr-1 inline" />P{r.settled.seq} · {r.settled.outcome_label}
                          </span>
                        ) : (
                          <>
                            <KNSelect data-testid={`roll-settle-outcome-${r.roll_no}`} searchable={false} value={dec[r.roll_id] || ""}
                              onValueChange={(v) => setDec((d) => ({ ...d, [r.roll_id]: v }))}
                              options={[{ value: "", label: "Belum diputus" }, ...(r.options || []).filter((o) => o.ok).map((o) => ({ value: o.value, label: o.label }))]} />
                            {off.length > 0 && (
                              <p className="mt-0.5 text-[10px] leading-snug text-[#8A8F98]" title={off.map((o) => `${o.label}: ${o.why}`).join("\n")}>
                                <Info size={10} className="mr-0.5 inline" />Belum bisa: {off.map((o) => o.label).join(", ")}
                              </p>
                            )}
                          </>
                        )}
                      </td>
                      <td className="text-right text-[12px] tabular-nums">{p ? qty(p.qty_stock, r.unit) : "—"}</td>
                      <td className="text-right text-[12px] tabular-nums">{p ? qty(p.qty_cut, r.unit) : "—"}{p?.qty_cut && r.cut_treatment ? ` (${r.cut_treatment === "bs" ? "BS" : "dibuang"})` : ""}</td>
                      <td className="text-right text-[12px] tabular-nums">{p ? qty(p.qty_back, r.unit) : "—"}</td>
                      <td className="text-right text-[12px] tabular-nums">{p ? formatCurrency(p.credit_amount) : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!openRows.length && <p className="p-2 text-[12px] text-[#1A7F37]">Semua roll sudah diputus.</p>}
          </div>
        )}

        {hasNego && (
          <div className="mt-3 flex flex-wrap items-center gap-4 text-xs" data-testid="roll-settle-payout">
            <span className="font-semibold">Kompensasi cutloss/diskon:</span>
            {[["store_credit", "Jadi saldo"], ["refund", "Refund tunai"], ["", "Kurangi piutang SO asal saja"]].map(([v, l]) => (
              <label key={v || "ar"} className="inline-flex items-center gap-1">
                <input type="radio" name="roll-payout" data-testid={`roll-settle-payout-${v || "ar"}`} checked={payout === v} onChange={() => setPayout(v)} /> {l}
              </label>))}
          </div>
        )}
        {hasRefund && (
          <div className="mt-3 w-full max-w-md text-xs" data-testid="roll-settle-refund-account">
            <span className="field-label">Akun Kas/Bank pengembalian dana</span>
            <KNSelect className="field w-full" value={refundAccount} onValueChange={setRefundAccount} searchable={false}
              options={[{ value: "", label: "Default — 1-1100 Kas Besar / Bank" }, ...cashAccounts.map((a) => ({ value: a.code, label: `${a.code} — ${a.name}` }))]} />
          </div>
        )}

        <SettleValuePanel pv={pv} err={pvErr} busy={pvBusy} />

        <input data-testid="roll-settle-decision-note" className="field mt-3 w-full"
          placeholder="Bukti keputusan (mis. ACC Pak Budi via WA 12/10)" value={decisionNote} onChange={(e) => setDecisionNote(e.target.value)} />
        <textarea className="textarea mt-3" rows={2} placeholder="Catatan penyelesaian (opsional)..." value={notes} onChange={(e) => setNotes(e.target.value)} />

        {err && <p role="alert" className="mt-2 rounded-md bg-[#FDECEC] px-2.5 py-1.5 text-[12px] text-[#A8221A]" data-testid="roll-settle-error">{err}</p>}
        <div className="modal-actions">
          <button className="secondary-button" onClick={onClose}>Batal</button>
          <button data-testid="roll-settle-confirm" className="primary-button" disabled={busy || !chosen.length || !!pv?.blocked || pvBusy || !pv}
            onClick={confirm}>
            {busy ? <Loader2 size={13} className="spin" /> : <CheckCircle2 size={13} />} Simpan penyelesaian ({chosen.length} roll)
          </button>
        </div>
      </div>
    </div>
  );
}
