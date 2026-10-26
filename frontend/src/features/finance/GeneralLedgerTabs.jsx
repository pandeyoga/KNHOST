/**
 * GeneralLedgerTabs — tab "Neraca Saldo" & "Buku Besar" layar Jurnal & Buku Besar.
 * Fase 3 · P4 — diekstrak apa adanya dari GeneralLedger.jsx supaya berkas utama di bawah batas 500 baris
 * (GeneralLedger mendapat DesktopOnlyNotice L-04 kelas C). Perilaku tidak berubah.
 */
import { apiErrorText } from "../../utils/apiError";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Scale, BookOpen } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import { formatCurrency, formatDate } from "../../utils/formatters";

const fmtDate = (iso) => formatDate(iso);

// ─── NERACA SALDO TAB ────────────────────────────────────────────────────────
export function TrialBalanceTab({ refreshKey, onError, onDrill }) {
  const [tb, setTb] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/gl/trial-balance`);
      setTb(res.data || null);
    } catch (e) {
      onError(apiErrorText(e, "Gagal memuat neraca saldo."));
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => { load(); }, [load, refreshKey]);

  if (loading) return <div className="grid gap-2" data-testid="gl-trial-loading">{[0, 1, 2, 3, 4].map((i) => <div key={i} className="h-9 bg-[#F5F5F7] rounded animate-pulse" />)}</div>;
  if (!tb || (tb.rows || []).length === 0) return <div data-testid="gl-trial-empty" className="py-12 text-center text-[12px] text-[#8E8E93]"><Scale size={26} className="mx-auto mb-2 text-gray-300" />Belum ada saldo. Posting jurnal terlebih dahulu.</div>;

  return (
    <div data-testid="gl-trial">
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
              <tr key={r.code} data-testid={`gl-trial-row-${r.code}`} onClick={() => onDrill(r.code)} className="border-b border-[#F5F5F7] last:border-0 cursor-pointer hover:bg-[#FBF8FE]">
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
      <p className="mt-2 text-[11px] text-[#9A9BA3]">Klik baris akun untuk melihat Buku Besar (rincian mutasi).</p>
    </div>
  );
}

// ─── BUKU BESAR TAB ──────────────────────────────────────────────────────────
export function LedgerTab({ accounts, refreshKey, code, setCode, onError }) {
  const [ledger, setLedger] = useState(null);
  const [loading, setLoading] = useState(false);

  const postableOptions = useMemo(
    () => accounts.filter((a) => a.is_postable).map((a) => ({ value: a.code, label: `${a.code} — ${a.name}` })),
    [accounts]);

  const load = useCallback(async (c) => {
    if (!c) { setLedger(null); return; }
    setLoading(true);
    try {
      const res = await axios.get(`${API}/gl/accounts/${c}/ledger`);
      setLedger(res.data || null);
    } catch (e) {
      onError(apiErrorText(e, "Gagal memuat buku besar."));
      setLedger(null);
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => { if (code) load(code); }, [code, load, refreshKey]);

  return (
    <div data-testid="gl-ledger">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-[320px] max-w-full">
          <KNSelect data-testid="gl-ledger-account" className="field py-1.5 text-[12px]" value={code || ""} onValueChange={setCode}
            placeholder="Pilih akun untuk dilihat" options={postableOptions} searchable />
        </div>
        {ledger && <span className="ml-auto text-[12px] text-[#6B6B73]">Saldo akhir: <b className="tabular-nums">{formatCurrency(ledger.balance)}</b></span>}
      </div>

      {!code ? (
        <div data-testid="gl-ledger-prompt" className="py-12 text-center text-[12px] text-[#8E8E93]"><BookOpen size={26} className="mx-auto mb-2 text-gray-300" />Pilih akun untuk menampilkan buku besar.</div>
      ) : loading ? (
        <div className="grid gap-2" data-testid="gl-ledger-loading">{[0, 1, 2].map((i) => <div key={i} className="h-9 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
      ) : !ledger || (ledger.lines || []).length === 0 ? (
        <div data-testid="gl-ledger-empty" className="py-10 text-center text-[12px] text-[#8E8E93]">Belum ada mutasi pada akun ini.</div>
      ) : (
        <div className="overflow-auto rounded-md border border-[#EFF0F2]">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-left text-[10px] font-bold uppercase text-[#8E8E93] bg-[#FAFBFC] border-b border-[#EFF0F2]">
                <th className="px-3 py-2">Tanggal</th>
                <th className="px-3 py-2">No / Keterangan</th>
                <th className="px-3 py-2 text-right">Debit</th>
                <th className="px-3 py-2 text-right">Kredit</th>
                <th className="px-3 py-2 text-right">Saldo</th>
              </tr>
            </thead>
            <tbody>
              {ledger.lines.map((l, i) => (
                <tr key={`${l.entry_id}-${i}`} data-testid={`gl-ledger-row-${l.number}`} className="border-b border-[#F5F5F7] last:border-0">
                  <td className="px-3 py-2 text-[#3C3C43]">{fmtDate(l.date)}</td>
                  <td className="px-3 py-2"><span className="font-mono text-[10px] text-[#9A9BA3]">{l.number}</span><br />{l.description}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-[#1B7F4B]">{l.debit > 0 ? formatCurrency(l.debit) : "—"}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-[#C0392B]">{l.credit > 0 ? formatCurrency(l.credit) : "—"}</td>
                  <td className="px-3 py-2 text-right tabular-nums font-semibold">{formatCurrency(l.running_balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
