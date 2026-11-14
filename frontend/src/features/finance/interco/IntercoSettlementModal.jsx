/**
 * FASE G-6 — pop-up **Pelunasan Antar-PT** (US6): satu dokumen melunasi beberapa tagihan antar-PT satu pasangan PT.
 * Metode bawaan `transfer` (F-08); netting hanya saling hapus IC-AR/IC-AP dan server menolaknya bila melebihi piutang
 * balik yang terbuka.
 *
 * PK-43 (UX-08) — kandidat dimuat dari server (`GET /interco/payment-schedule`, utang antar-PT per transaksi untuk
 * pasangan pembayar → penerima) setiap PT berubah; dulu disaring dari daftar halaman induk yang dimuat untuk PT aktif,
 * sehingga saat PT aktif adalah PEMBAYAR kandidatnya kosong. Isian baru: tanggal pelunasan (bawaan hari ini WIB) dan
 * rekening PT pembayar (wajib untuk transfer/tunai; tersembunyi untuk netting). Kirim: kunci idempotensi + penahan klik
 * ganda (`02` N4) dan konfirmasi yang menyebut jumlah, nominal, kedua PT, dan tanggal (N5).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { HandCoins } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import FormModal from "../../../components/FormModal";
import { KNSelect } from "../../../components/KNSelect";
import KNDatePicker from "../../../components/KNDatePicker";
import MoneyInput from "../../../components/MoneyInput";
import ErrorNotice from "../../../components/ErrorNotice";
import { SearchBox } from "../../../components/ListControls";
import { formatCurrency, formatDate, todayWib } from "../../../utils/formatters";
import { apiErrorText } from "../../../utils/apiError";
import { moneyPost } from "../../../utils/moneyRequest";
import useIntentKey from "../../../hooks/useIntentKey";
import { askConfirm } from "../../../services/confirmService";
import { usePaymentMethods } from "../../../config/paymentMethods";   // PM-T1 — daftar induk cara bayar
import { fmtDate } from "./intercoApi";

export const SETTLE_EMPTY = "Tidak ada tagihan antar-PT yang terbuka untuk pasangan PT ini.";

const sisaOf = (r) => Number(r?.outstanding ?? r?.remaining ?? 0);

export default function IntercoSettlementModal({
  entities = [], presetPayerEntityId = "", presetPayeeEntityId = "", onClose, onCreated,
}) {
  const [payer, setPayer] = useState(presetPayerEntityId);
  const [payee, setPayee] = useState(presetPayeeEntityId);
  const [method, setMethod] = useState("transfer");
  const [date, setDate] = useState(() => todayWib());
  const [account, setAccount] = useState("");
  const [accounts, setAccounts] = useState([]);
  const [rows, setRows] = useState([]);
  const [fullOnly, setFullOnly] = useState(true);
  const [loading, setLoading] = useState(false);
  const [loadErr, setLoadErr] = useState("");
  const [selected, setSelected] = useState({});   // {interco_id: nominal teks}
  const [notes, setNotes] = useState("");
  const [cari, setCari] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  // PK-12 — satu niat pelunasan = satu Idempotency-Key (kirim ulang tidak melunasi dua kali).
  const intent = useIntentKey("ic-stl");
  const payMethods = usePaymentMethods("keluar", payer);
  const methodOptions = payMethods.methods.filter((m) => m.needs_account === "bank" || m.needs_account === "kas")
    .map((m) => ({ value: m.code, label: m.name }));
  const isNetting = method === "netting";

  const nameOf = (id) => {
    const e = entities.find((x) => x.id === id) || {};
    return e.short_name || e.legal_name || e.name || "";
  };
  const entOptions = entities.map((e) => ({ value: e.id, label: e.short_name || e.legal_name || e.name || e.id }));
  const pairReady = Boolean(payer && payee && payer !== payee);

  const loadCandidates = useCallback(async () => {
    setSelected({}); setRows([]); setLoadErr(""); setCari("");
    if (!pairReady) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/interco/payment-schedule`,
        { params: { payer_entity_id: payer, payee_entity_id: payee } });
      setRows(Array.isArray(r.data?.rows) ? r.data.rows : []);
      setFullOnly(r.data?.config?.require_full_payment !== false);
    } catch (e) {
      setLoadErr(apiErrorText(e, "Tagihan antar-PT gagal dimuat."));
    } finally { setLoading(false); }
  }, [payer, payee, pairReady]);

  useEffect(() => { loadCandidates(); }, [loadCandidates]);

  // Rekening PT pembayar (kas besar/bank aktif; server menolak Kas Kecil untuk pelunasan antar-PT).
  useEffect(() => {
    let alive = true;
    setAccounts([]); setAccount("");
    if (!payer) return () => { alive = false; };
    axios.get(`${API}/bank-accounts`, { params: { entity_id: payer } }).then((b) => {
      if (!alive) return;
      const acc = (Array.isArray(b.data) ? b.data : []).filter((a) => a.entity_id === payer
        && a.is_active !== false && a.status !== "inactive" && a.cash_type !== "kas_kecil");
      setAccounts(acc);
      setAccount(acc[0]?.id || "");
    }).catch(() => { if (alive) setAccounts([]); });
    return () => { alive = false; };
  }, [payer]);

  const toggle = (r) => setSelected((prev) => {
    const nxt = { ...prev };
    if (r.interco_id in nxt) delete nxt[r.interco_id];
    else nxt[r.interco_id] = String(sisaOf(r));
    return nxt;
  });
  const picks = useMemo(() => Object.entries(selected)
    .map(([id, v]) => ({ interco_id: id, applied_amount: Number(v) || 0 }))
    .filter((p) => p.applied_amount > 0), [selected]);
  const total = picks.reduce((s, p) => s + p.applied_amount, 0);
  const term = cari.trim().toLowerCase();
  const shown = term ? rows.filter((r) => `${r.number || ""} ${r.counterpart_number || ""}`.toLowerCase().includes(term)) : rows;

  const reason = !payer || !payee ? "Pilih PT pembayar dan PT penerima."
    : payer === payee ? "PT pembayar dan PT penerima harus berbeda."
      : !date ? "Isi tanggal pelunasan."
        : picks.length === 0 ? "Centang minimal satu tagihan yang mau dilunasi."
          : !isNetting && !account ? `${nameOf(payer) || "PT pembayar"} belum punya rekening bank aktif — tambahkan di Keuangan › Kas & Bank.`
            : "";

  const submit = async () => {
    if (reason || busy) return;
    const ok = await askConfirm({
      title: "Terbitkan pelunasan antar-PT?",
      message: `Lunasi ${picks.length} tagihan senilai ${formatCurrency(total)} dari ${nameOf(payer)} ke ${nameOf(payee)} `
        + `pada ${formatDate(date)}?`,
      confirmLabel: "Terbitkan Pelunasan",
      testId: "interco-settle-confirm",
    });
    if (!ok) return;
    setBusy(true); setErr("");
    const body = {
      payer_entity_id: payer, payee_entity_id: payee, transactions: picks, method, settle_date: date,
      bank_account_id: isNetting ? "" : account, notes,
    };
    try {
      await intent.send(body, (k) => moneyPost(`${API}/interco/settlements`, body, k));
      onCreated?.();
    } catch (e) { setErr(apiErrorText(e, "Pelunasan antar-PT gagal diterbitkan.")); }
    finally { setBusy(false); }
  };

  return (
    <FormModal open onClose={onClose} size="lg" icon={HandCoins} testId="interco-settle-modal" busy={busy}
      title="Pelunasan Antar-PT"
      subtitle="Pilih tagihan antar-PT yang mau dilunasi PT pembayar. Satu dokumen boleh memuat beberapa tagihan; rinciannya tetap per tagihan."
      footer={(
        <div className="flex flex-wrap items-center justify-end gap-2">
          {reason && <span className="text-fs-12 text-kn-text-2" data-testid="interco-settle-reason">{reason}</span>}
          <button type="button" onClick={onClose} data-testid="interco-settle-cancel" className="secondary-button"
            disabled={busy}>Batal</button>
          <button type="button" onClick={submit} disabled={busy || Boolean(reason)} data-testid="interco-settle-submit"
            className="primary-button">{busy ? "Menerbitkan…" : "Terbitkan Pelunasan"}</button>
        </div>
      )}>
      <div className="space-y-4">
        {err && <ErrorNotice message={err} onDismiss={() => setErr("")} testId="interco-settle-error" />}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <label className="block">
            <span className="field-label">PT pembayar <span className="text-kn-danger-text">*</span></span>
            <KNSelect value={payer} onValueChange={setPayer} options={entOptions.filter((o) => o.value !== payee)}
              placeholder="Pilih PT pembayar" data-testid="interco-settle-payer" />
          </label>
          <label className="block">
            <span className="field-label">PT penerima <span className="text-kn-danger-text">*</span></span>
            <KNSelect value={payee} onValueChange={setPayee} options={entOptions.filter((o) => o.value !== payer)}
              placeholder="Pilih PT penerima" data-testid="interco-settle-payee" />
          </label>
          <label className="block">
            <span className="field-label">Tanggal pelunasan <span className="text-kn-danger-text">*</span></span>
            <KNDatePicker value={date} onChange={setDate} clearable={false} data-testid="interco-settle-date" />
          </label>
          <label className="block">
            <span className="field-label">Cara bayar <span className="text-kn-danger-text">*</span></span>
            <KNSelect value={method} onValueChange={setMethod} options={methodOptions} data-testid="interco-settle-method" />
          </label>
          {!isNetting && (
            <label className="block md:col-span-2">
              <span className="field-label">Rekening {nameOf(payer) || "PT pembayar"} <span className="text-kn-danger-text">*</span></span>
              <KNSelect value={account} onValueChange={setAccount} data-testid="interco-settle-account"
                options={accounts.map((a) => ({ value: a.id, label: a.name || a.account_name || a.id }))}
                placeholder={accounts.length ? "Pilih rekening" : "Belum ada rekening bank aktif"} />
            </label>
          )}
        </div>

        {rows.length > 0 && (
          <SearchBox value={cari} onChange={setCari} placeholder="Cari nomor tagihan…" testId="interco-settle-search" />
        )}
        {loadErr && <ErrorNotice message={loadErr} onRetry={loadCandidates} testId="interco-settle-load-error" />}
        {!loadErr && (
          <div className="table-wrap">
            <table className="data-table head-wrap" data-testid="interco-settle-candidates">
              <thead>
                <tr>
                  <th className="w-10"><span className="sr-only">Pilih</span></th>
                  <th>Nomor</th>
                  <th>Tanggal</th>
                  <th>Jatuh Tempo</th>
                  <th className="text-right">Total</th>
                  <th className="text-right">Sisa</th>
                  <th className="text-right">Dilunasi</th>
                </tr>
              </thead>
              <tbody>
                {loading && [0, 1, 2].map((i) => (
                  <tr key={`sk${i}`} data-testid="interco-settle-loading">
                    <td colSpan={7}><div className="h-5 animate-pulse rounded bg-kn-neutral-soft" /></td>
                  </tr>
                ))}
                {!loading && shown.length === 0 && (
                  <tr><td colSpan={7} className="py-6 text-center text-kn-text-2" data-testid="interco-settle-empty">
                    {!pairReady ? "Pilih PT pembayar dan PT penerima dulu."
                      : rows.length ? `Tidak ada tagihan yang cocok dengan “${cari.trim()}”.` : SETTLE_EMPTY}
                  </td></tr>
                )}
                {!loading && shown.map((r) => {
                  const id = r.interco_id;
                  const checked = id in selected;
                  const bisa = r.settleable !== false;
                  return (
                    <tr key={id} data-testid={`interco-settle-cand-${id}`}>
                      <td>
                        <input type="checkbox" checked={checked} disabled={!bisa} aria-label={`Pilih ${r.number}`}
                          onChange={() => toggle(r)} data-testid={`interco-settle-check-${id}`} />
                      </td>
                      <td className="font-semibold text-kn-text">
                        {r.number}
                        {!bisa && r.settle_block_reason && (
                          <span className="block text-fs-12 font-normal text-kn-warning-text"
                            data-testid={`interco-settle-block-${id}`}>{r.settle_block_reason}</span>
                        )}
                      </td>
                      <td>{fmtDate(r.doc_date)}</td>
                      <td>{r.due_date ? fmtDate(r.due_date) : "—"}</td>
                      <td className="text-right tabular-nums">{formatCurrency(r.grand_total)}</td>
                      <td className="text-right tabular-nums">{formatCurrency(sisaOf(r))}</td>
                      <td className="text-right">
                        {!checked ? <span className="text-kn-text-2">—</span>
                          : fullOnly ? (
                            <span className="tabular-nums font-semibold" data-testid={`interco-settle-amount-${id}`}>
                              {formatCurrency(Number(selected[id]) || 0)}</span>
                          ) : (
                            <MoneyInput value={selected[id]} testId={`interco-settle-amount-${id}`} className="field w-36"
                              onChange={(v) => setSelected((p) => ({ ...p, [id]: v }))} />
                          )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-kn-neutral-soft px-3 py-2 text-fs-13">
          <span className="text-kn-text-2" data-testid="interco-settle-count">
            {picks.length} tagihan dipilih{fullOnly ? " · dibayar penuh per tagihan (pengaturan jadwal bayar antar-PT)" : ""}
          </span>
          <span className="text-kn-text">Total <b className="tabular-nums" data-testid="interco-settle-total">{formatCurrency(total)}</b></span>
        </div>

        <label className="block">
          <span className="field-label">Catatan</span>
          <textarea className="field" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)}
            data-testid="interco-settle-notes" />
        </label>
      </div>
    </FormModal>
  );
}
