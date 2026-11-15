/**
 * GeneralLedgerTabs — tab "Neraca Saldo" & "Buku Besar" layar Jurnal & Buku Besar.
 * Fase 3 · P4 — diekstrak apa adanya dari GeneralLedger.jsx supaya berkas utama di bawah batas 500 baris
 * (GeneralLedger mendapat DesktopOnlyNotice L-04 kelas C). Perilaku tidak berubah.
 * PK-16 — banner PT dipasang SEKALI di GeneralLedger (di atas KPI, berlaku untuk kedua tab ini). Gagal memuat →
 * data dikosongkan dan area angka tidak menulis "belum ada saldo/mutasi" (galatnya di bilah galat induk + Coba lagi).
 * PK-43 (UX-13) — Buku Besar berentang (**Dari** dan **Sampai**, `start` dan `as_of` server): bila Dari diisi, baris pertama
 * **Saldo awal** dan mutasi urut tanggal (lama → baru) dengan saldo berjalan dari saldo awal. Tiap baris mutasi membuka
 * rincian jurnalnya (yang bisa membuka dokumen sumbernya).
 * MN-T3 (bagian E) — Neraca Saldo ber-tanggal **Per tanggal** (`as_of`); klik baris akun → preset
 * `{tab: "ledger", code, end: tanggal neraca saldo}` (buku besar akun itu sampai tanggal itu). Mode Semua PT → petunjuk
 * "Pilih satu PT untuk menelusuri angka ini." (baris total tidak bisa diklik).
 */
import { apiErrorText } from "../../utils/apiError";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Scale, BookOpen } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import KNDatePicker from "../../components/KNDatePicker";
import { formatCurrency, formatDate } from "../../utils/formatters";
import JournalDetailModal from "./JournalDetailModal";
import { TraceNotice, traceDecision } from "./traceLedger";
import useJournalActions from "./useJournalActions";

const fmtDate = (iso) => formatDate(iso);

// ─── NERACA SALDO TAB ────────────────────────────────────────────────────────
const pad2 = (n) => String(n).padStart(2, "0");
const todayLocal = () => { const d = new Date(); return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`; };

export function TrialBalanceTab({ refreshKey, onError, onDrill, selectedEntity, initialAsOf = "" }) {
  const [tb, setTb] = useState(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [asOf, setAsOf] = useState(initialAsOf || todayLocal());
  const [notice, setNotice] = useState("");
  const drill = (code) => {
    const d = traceDecision({ code, range: { end: asOf }, selectedEntity });
    if (!d) return;
    if (d.notice) { setNotice(d.notice); return; }
    setNotice("");
    onDrill(d.preset);
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/gl/trial-balance`, { params: asOf ? { as_of: asOf } : {} });
      setTb(res.data || null);
      setFailed(false);
    } catch (e) {
      onError(apiErrorText(e, "Gagal memuat neraca saldo."));
      setTb(null);   // PK-16 (RP-04) — tidak ada angka dari permintaan sebelumnya
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [onError, asOf]);

  useEffect(() => { load(); }, [load, refreshKey]);

  const asOfBar = (
    <div className="mb-2 flex flex-wrap items-end gap-2" data-testid="gl-trial-asof-bar">
      <div><label className="field-label">Per tanggal</label>
        <KNDatePicker data-testid="gl-trial-asof" value={asOf} onChange={(v) => setAsOf(v || todayLocal())} clearable={false} /></div>
    </div>
  );
  if (loading) return <>{asOfBar}<div className="grid gap-2" data-testid="gl-trial-loading">{[0, 1, 2, 3, 4].map((i) => <div key={i} className="h-9 bg-[#F5F5F7] rounded animate-pulse" />)}</div></>;
  if (failed) return asOfBar;
  if (!tb || (tb.rows || []).length === 0) return <>{asOfBar}<div data-testid="gl-trial-empty" className="py-12 text-center text-[12px] text-[#8E8E93]"><Scale size={26} className="mx-auto mb-2 text-gray-300" />Belum ada saldo. Posting jurnal terlebih dahulu.</div></>;

  return (
    <div data-testid="gl-trial">
      {asOfBar}
      <TraceNotice notice={notice} onDismiss={() => setNotice("")} testId="gl-trial-trace-notice" />
      <div className="overflow-auto rounded-md border border-[#EFF0F2]">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="text-left text-[10px] font-bold uppercase text-[#8E8E93] bg-[#FAFBFC] border-b border-[#EFF0F2]">
              <th className="px-3 py-2">Kode</th>
              <th className="px-3 py-2">Nama Akun</th>
              <th className="px-3 py-2">Tipe</th>
              <th className="px-3 py-2 text-right">Debit</th>
              <th className="px-3 py-2 text-right">Kredit</th>
            </tr>
          </thead>
          <tbody>
            {tb.rows.map((r) => (
              <tr key={r.code} data-testid={`gl-trial-row-${r.code}`} onClick={() => drill(r.code)} className="border-b border-[#F5F5F7] last:border-0 cursor-pointer hover:bg-[#FBF8FE]">
                <td className="px-3 py-2 font-mono font-semibold text-[#3C3C43] tabular-nums">{r.code}</td>
                <td className="px-3 py-2 text-[#1C1C1E]">{r.name}</td>
                <td className="px-3 py-2 text-[10px] text-[#9A9BA3]">{r.type_label}</td>
                <td className="px-3 py-2 text-right tabular-nums">{r.debit_balance > 0 ? formatCurrency(r.debit_balance) : "—"}</td>
                <td className="px-3 py-2 text-right tabular-nums">{r.credit_balance > 0 ? formatCurrency(r.credit_balance) : "—"}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="bg-[#FAFBFC] border-t-2 border-[#E4E4EA] font-bold">
              <td className="px-3 py-2.5" colSpan={3}>TOTAL {tb.balanced ? "✓ Seimbang" : "⚠ Tidak Seimbang"}</td>
              <td className="px-3 py-2.5 text-right tabular-nums" data-testid="gl-trial-total-debit">{formatCurrency(tb.total_debit)}</td>
              <td className="px-3 py-2.5 text-right tabular-nums" data-testid="gl-trial-total-credit">{formatCurrency(tb.total_credit)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="mt-2 text-fs-12 text-kn-text-2">Klik baris akun untuk melihat Buku Besar akun itu sampai tanggal neraca saldo.</p>
    </div>
  );
}

// ─── BUKU BESAR TAB ──────────────────────────────────────────────────────────
export function LedgerTab({ accounts, refreshKey, code, setCode, onError, range = { start: "", end: "" }, setRange,
  entities = [], selectedEntity, sourceMeta, onChanged, onOpenDocument }) {
  const [ledger, setLedger] = useState(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [entry, setEntry] = useState(null);
  const [opening, setOpening] = useState("");
  const { voidEntry, reverseEntry } = useJournalActions(() => { setEntry(null); onChanged?.(); });
  const start = range?.start || "";
  const end = range?.end || "";

  const postableOptions = useMemo(
    () => accounts.filter((a) => a.is_postable).map((a) => ({ value: a.code, label: `${a.code} — ${a.name}` })),
    [accounts]);

  const load = useCallback(async (c) => {
    if (!c) { setLedger(null); return; }
    setLoading(true);
    try {
      const params = {};
      if (start) params.start = start;
      if (end) params.as_of = end;
      const res = await axios.get(`${API}/gl/accounts/${c}/ledger`, { params });
      setLedger(res.data || null);
      setFailed(false);
    } catch (e) {
      onError(apiErrorText(e, "Gagal memuat buku besar."));
      setLedger(null);
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [onError, start, end]);

  useEffect(() => { if (code) load(code); }, [code, load, refreshKey]);

  const openEntry = async (l) => {
    setOpening(l.entry_id);
    try {
      const res = await axios.get(`${API}/gl/journal/${l.entry_id}`);
      setEntry(res.data || null);
    } catch (e) {
      onError(apiErrorText(e, "Rincian jurnal gagal dimuat."));
    } finally { setOpening(""); }
  };

  // Dengan "Dari": urut tanggal lama → baru (baris pertama saldo awal); tanpa: terbaru dulu (seperti sebelumnya).
  const lines = useMemo(() => {
    const ls = ledger?.lines || [];
    return start ? [...ls].reverse() : ls;
  }, [ledger, start]);
  const hasOpening = Boolean(start && ledger && ledger.opening_balance !== undefined);
  const setPart = (k) => (v) => setRange?.({ start, end, [k]: v || "" });

  return (
    <div data-testid="gl-ledger">
      <div className="flex flex-wrap items-end gap-2 mb-3">
        <label className="w-[320px] max-w-full">
          <span className="field-label">Akun</span>
          <KNSelect data-testid="gl-ledger-account" className="field py-1.5 text-fs-12" value={code || ""} onValueChange={setCode}
            placeholder="Pilih akun untuk dilihat" options={postableOptions} searchable />
        </label>
        <label className="w-[170px]">
          <span className="field-label">Dari</span>
          <KNDatePicker data-testid="gl-ledger-start" value={start} max={end || undefined} onChange={setPart("start")} />
        </label>
        <label className="w-[170px]">
          <span className="field-label">Sampai</span>
          <KNDatePicker data-testid="gl-ledger-end" value={end} min={start || undefined} onChange={setPart("end")} />
        </label>
        {ledger && (
          <span className="ml-auto pb-2 text-fs-12 text-kn-text-2" data-testid="gl-ledger-balance">
            {hasOpening && <>Saldo awal <b className="tabular-nums text-kn-text">{formatCurrency(ledger.opening_balance)}</b> · </>}
            Saldo akhir <b className="tabular-nums text-kn-text">{formatCurrency(ledger.balance)}</b>
          </span>
        )}
      </div>

      {!code ? (
        <div data-testid="gl-ledger-prompt" className="py-12 text-center text-fs-12 text-kn-text-2"><BookOpen size={26} className="mx-auto mb-2 text-kn-text-2" />Pilih akun untuk menampilkan buku besar.</div>
      ) : loading ? (
        <div className="grid gap-2" data-testid="gl-ledger-loading">{[0, 1, 2].map((i) => <div key={i} className="h-9 bg-kn-neutral-soft rounded animate-pulse" />)}</div>
      ) : failed ? null : !ledger || (lines.length === 0 && !hasOpening) ? (
        <div data-testid="gl-ledger-empty" className="py-10 text-center text-fs-12 text-kn-text-2">
          {start || end ? "Tidak ada mutasi pada rentang ini." : "Belum ada mutasi pada akun ini."}
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Tanggal</th>
                <th>No / Keterangan</th>
                <th className="text-right">Debit</th>
                <th className="text-right">Kredit</th>
                <th className="text-right">Saldo</th>
              </tr>
            </thead>
            <tbody>
              {hasOpening && (
                <tr data-testid="gl-ledger-opening" className="bg-kn-neutral-soft">
                  <td>{fmtDate(start)}</td>
                  <td className="font-semibold">Saldo awal</td>
                  <td className="text-right">—</td>
                  <td className="text-right">—</td>
                  <td className="text-right tabular-nums font-semibold">{formatCurrency(ledger.opening_balance)}</td>
                </tr>
              )}
              {lines.map((l, i) => (
                <tr key={`${l.entry_id}-${i}`} data-testid={`gl-ledger-row-${l.number}`} className="cursor-pointer"
                  onClick={() => openEntry(l)} title="Buka rincian jurnal">
                  <td>{fmtDate(l.date)}</td>
                  <td>
                    <button type="button" className="link-button font-mono" aria-label={`Buka rincian jurnal ${l.number}`}
                      disabled={opening === l.entry_id} onClick={(e) => { e.stopPropagation(); openEntry(l); }}>{l.number}</button>
                    <span className="block">{l.description}</span>
                  </td>
                  <td className="text-right tabular-nums text-kn-success-text">{l.debit > 0 ? formatCurrency(l.debit) : "—"}</td>
                  <td className="text-right tabular-nums text-kn-danger-text">{l.credit > 0 ? formatCurrency(l.credit) : "—"}</td>
                  <td className="text-right tabular-nums font-semibold">{formatCurrency(l.running_balance)}</td>
                </tr>
              ))}
              {hasOpening && lines.length === 0 && (
                <tr><td colSpan={5} className="py-6 text-center text-kn-text-2" data-testid="gl-ledger-empty">Tidak ada mutasi pada rentang ini.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      {entry && <JournalDetailModal je={entry} sourceMeta={sourceMeta} entities={entities} selectedEntity={selectedEntity}
        onClose={() => setEntry(null)} onVoid={voidEntry} onReverse={reverseEntry} onOpenDocument={onOpenDocument} />}
    </div>
  );
}
