/**
 * StoreCreditView (R5.2) — Store Credit / Saldo Kredit Pelanggan.
 * Ledger saldo store credit per pelanggan (issue dari retur, redeem ke order AR, adjust manual).
 * Sumber: /api/store-credit (ringkasan), /store-credit/ledger, /store-credit/open-orders,
 *          POST /store-credit/redeem, /store-credit/adjust.
 * Akses admin/manager/sales (redeem); adjust admin/manager.
 *
 * Fase 4 · R2 (L-03) — pop-up Pakai/Sesuaikan/Batalkan diekstrak ke `StoreCreditModals.jsx` (FormModal baku).
 */
import { apiErrorText } from "../../utils/apiError";
import { useCallback, useEffect, useMemo, useState } from "react";
import { can } from "../../config/roles";
import {
  RefreshCw, Search, Wallet, Users, X, Gift, ArrowDownCircle,
  History, TicketPercent, RotateCcw, Ban,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import { formatCurrency } from "../../utils/formatters";
import DetailModal from "../../components/DetailModal";
import { AdjustModal, RedeemModal, ReverseModal } from "./StoreCreditModals";
import EntityBadge from "../../components/EntityBadge";

function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString("id-ID", { day: "2-digit", month: "short", year: "2-digit", hour: "2-digit", minute: "2-digit" }); }
  catch { return "—"; }
}

const TYPE_META = {
  issue: { label: "Terbit", cls: "bg-[#E6F6EC] text-[#1B7F4B]", icon: Gift },
  redeem: { label: "Pakai", cls: "bg-[#EAF1FF] text-[#0058CC]", icon: ArrowDownCircle },
  adjust: { label: "Sesuai", cls: "bg-[#FDF3E7] text-[#B45309]", icon: TicketPercent },
  reversal: { label: "Pembalikan", cls: "bg-[#F3EAFB] text-[#6B219A]", icon: RotateCcw },
};

import PagedRows from "@/components/PagedRows";

export default function StoreCreditView({ selectedEntity, currentUser }) {
  const canAdjust = can(currentUser?.permissions, "ar_receipt", "void");   // FE-04 — POST /store-credit/adjust
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState(null);        // {customer_id, entity_id, customer_name, balance}
  const [ledger, setLedger] = useState([]);
  const [ledgerLoading, setLedgerLoading] = useState(false);
  const [redeemFor, setRedeemFor] = useState(null);
  const [adjustFor, setAdjustFor] = useState(null);
  const [reverseFor, setReverseFor] = useState(null);   // ledger entry to reverse (R5.4)

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      const res = await axios.get(`${API}/store-credit`, { params });
      setRows(Array.isArray(res.data) ? res.data : []);
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat data store credit."));
    } finally {
      setLoading(false);
    }
  }, [selectedEntity]);

  useEffect(() => { load(); }, [load]);

  const openLedger = useCallback(async (row) => {
    setSelected(row);
    setLedger([]);
    setLedgerLoading(true);
    try {
      const res = await axios.get(`${API}/store-credit/ledger`, {
        params: { customer_id: row.customer_id, entity_id: row.entity_id || undefined },
      });
      setLedger(Array.isArray(res.data) ? res.data : []);
    } catch { setLedger([]); } finally { setLedgerLoading(false); }
  }, []);

  const totals = useMemo(() => {
    const total = rows.reduce((s, r) => s + (r.balance || 0), 0);
    return { total: Math.round(total), customers: rows.length };
  }, [rows]);

  const filtered = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return rows;
    return rows.filter((r) => `${r.customer_name} ${r.customer_id}`.toLowerCase().includes(t));
  }, [rows, q]);

  const afterMutation = () => { load(); if (selected) openLedger(selected); };

  return (
    <div data-testid="store-credit-view">
      {/* KPI */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 mb-3">
        {/* Audit UI 24 Okt (132): kartu ketiga dulu hanya kode akun "2-1450" — diganti metrik nyata. */}
        <Kpi testId="sc-kpi-total" label="Total Saldo (Kewajiban)" value={formatCurrency(totals.total)} icon={Wallet} tone="text-[#6B219A]" />
        <Kpi testId="sc-kpi-customers" label="Pelanggan ber-Saldo" value={String(totals.customers)} icon={Users} />
        <Kpi testId="sc-kpi-info" label="Rata-rata per Pelanggan" value={totals.customers ? formatCurrency(totals.total / totals.customers) : "—"} icon={TicketPercent} tone="text-[#0058CC]" />
      </div>

      <div className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2"><Wallet size={16} className="text-[#6B219A]" /><h2 data-testid="sc-title">Saldo Kredit Pelanggan (Store Credit)</h2></div>
          <div className="flex items-center gap-2 ml-auto">
            <div className="relative">
              <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-[#9A9BA3]" />
              <input data-testid="sc-search" className="field !pl-7 !py-1 !text-[12px]" placeholder="Cari pelanggan..." value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            <button data-testid="sc-refresh" className="icon-button" onClick={load} aria-label="Refresh"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
          </div>
        </div>
        <div className="section-body">
          <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="sc-error" />
          {loading ? (
            <div className="grid gap-2" data-testid="sc-loading">{[0, 1, 2, 3].map((i) => <div key={i} className="h-10 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
          ) : filtered.length === 0 ? (
            <div data-testid="sc-empty" className="py-12 text-center text-[12px] text-[#8E8E93]">
              <Gift size={26} className="mx-auto mb-2 text-gray-300" />
              Belum ada saldo store credit. Saldo terbit saat retur jual diselesaikan sebagai <b>Store Credit</b>.
            </div>
          ) : (
            <div className="overflow-auto rounded-md border border-[#EFF0F2]">
              <table className="w-full text-[12px]" data-testid="sc-table">
                <thead>
                  <tr className="text-left text-[10px] font-bold uppercase text-[#8E8E93] bg-[#FAFBFC] border-b border-[#EFF0F2]">
                    <th className="px-3 py-2">Pelanggan</th>
                    <th className="px-3 py-2">Entitas</th>
                    <th className="px-3 py-2 text-center">Transaksi</th>
                    <th className="px-3 py-2">Terakhir</th>
                    <th className="px-3 py-2 text-right">Saldo</th>
                    <th className="px-3 py-2 text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  <PagedRows rows={filtered} testId="store-credit-pager">{(r) => (
                    <tr key={`${r.customer_id}-${r.entity_id}`} data-testid={`sc-row-${r.customer_id}`}
                        className={`border-b border-[#F5F5F7] last:border-0 hover:bg-[#FAFBFF] ${selected?.customer_id === r.customer_id ? "bg-[#F3EAFB]" : ""}`}>
                      <td className="px-3 py-2 font-semibold text-[#1C1C1E] cursor-pointer" onClick={() => openLedger(r)}>{r.customer_name || r.customer_id}</td>
                      {/* INV-UI-02 — dulu mencetak `r.entity_id` MENTAH, sehingga kolom
                          "Entitas" berisi `ent_ksc` di layar. `EntityBadge` menerjemahkan
                          id menjadi nama pendek badan usaha (KSC / Kanda). */}
                      <td className="px-3 py-2 text-[#6B6B73]">
                        {r.entity_id ? <EntityBadge entityId={r.entity_id} /> : "—"}
                      </td>
                      <td className="px-3 py-2 text-center text-[#6B6B73]">{r.entries || 0}</td>
                      <td className="px-3 py-2 text-[#6B6B73]">{fmtDate(r.last_at)}</td>
                      <td className="px-3 py-2 text-right tabular-nums font-bold text-[#1B7F4B]" data-testid={`sc-balance-${r.customer_id}`}>{formatCurrency(r.balance)}</td>
                      <td className="px-3 py-2 text-right whitespace-nowrap">
                        <button data-testid={`sc-history-${r.customer_id}`} className="secondary-button py-1 px-2 text-[11px] mr-1" onClick={() => openLedger(r)}><History size={12} /> Mutasi</button>
                        <button data-testid={`sc-redeem-btn-${r.customer_id}`} className="primary-button py-1 px-2 text-[11px]" disabled={(r.balance || 0) <= 0} onClick={() => setRedeemFor(r)}><ArrowDownCircle size={12} /> Pakai</button>
                      </td>
                    </tr>
                  )}</PagedRows>
                </tbody>
              </table>
            </div>
          )}
          <p className="text-[11px] text-[#9A9BA3] mt-2">Saldo kredit = kewajiban perusahaan ke pelanggan. <b>Pakai</b> mengurangi saldo & melunasi piutang pesanan. Berlaku untuk pesanan dari <b>POS, Pesanan Penjualan, & Faktur</b>.</p>
        </div>
      </div>

      {/* Drill-down ledger — POP-UP (FASE P7) */}
      {selected && (
        <DetailModal onClose={() => { setSelected(null); setLedger([]); }}
          label="Mutasi store credit" testId="sc-ledger-modal">
          <LedgerPanel
            row={selected} ledger={ledger} loading={ledgerLoading} canAdjust={canAdjust}
            onClose={() => { setSelected(null); setLedger([]); }}
            onRedeem={() => setRedeemFor(selected)}
            onAdjust={() => setAdjustFor(selected)}
            onReverse={(entry) => setReverseFor(entry)}
          />
        </DetailModal>
      )}

      {redeemFor && (
        <RedeemModal row={redeemFor} onClose={() => setRedeemFor(null)}
                     onDone={() => { setRedeemFor(null); afterMutation(); }} />
      )}
      {adjustFor && (
        <AdjustModal row={adjustFor} onClose={() => setAdjustFor(null)}
                     onDone={() => { setAdjustFor(null); afterMutation(); }} />
      )}
      {reverseFor && (
        <ReverseModal entry={reverseFor} typeLabel={TYPE_META[reverseFor.type]?.label} onClose={() => setReverseFor(null)}
                      onDone={() => { setReverseFor(null); afterMutation(); }} />
      )}
    </div>
  );
}

function LedgerPanel({ row, ledger, loading, canAdjust, onClose, onRedeem, onAdjust, onReverse }) {
  return (
    <div className="section-card mt-3" data-testid="sc-ledger-panel">
      <div className="section-head">
        <div className="flex items-center gap-2">
          <History size={15} className="text-[#6B219A]" />
          <h2>{row.customer_name || "Riwayat Store Credit"}</h2>
          <span className="text-[11px] text-[#6B6B73]">· Saldo <b className="tabular-nums text-[#1B7F4B]">{formatCurrency(row.balance)}</b></span>
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <button data-testid="sc-ledger-redeem" className="primary-button py-1 px-2.5 text-[11px]" disabled={(row.balance || 0) <= 0} onClick={onRedeem}><ArrowDownCircle size={13} /> Pakai Saldo</button>
          {canAdjust && <button data-testid="sc-ledger-adjust" className="secondary-button py-1 px-2.5 text-[11px]" onClick={onAdjust}><TicketPercent size={13} /> Sesuaikan</button>}
          <button data-testid="sc-ledger-close" className="icon-button" onClick={onClose} aria-label="Tutup"><X size={14} /></button>
        </div>
      </div>
      <div className="section-body">
        {loading ? (
          <div className="grid gap-2" data-testid="sc-ledger-loading">{[0, 1, 2].map((i) => <div key={i} className="h-9 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
        ) : ledger.length === 0 ? (
          <div className="py-8 text-center text-[12px] text-[#8E8E93]" data-testid="sc-ledger-empty">Belum ada transaksi.</div>
        ) : (
          <div className="overflow-auto rounded-md border border-[#EFF0F2]">
            <table className="w-full text-[12px]" data-testid="sc-ledger-table">
              <thead>
                <tr className="text-left text-[10px] font-bold uppercase text-[#8E8E93] bg-[#FAFBFC] border-b border-[#EFF0F2]">
                  <th className="px-3 py-2">Waktu</th>
                  <th className="px-3 py-2">Jenis</th>
                  <th className="px-3 py-2">Referensi</th>
                  <th className="px-3 py-2">Catatan</th>
                  <th className="px-3 py-2 text-right">Nilai</th>
                  <th className="px-3 py-2 text-right">Saldo</th>
                  {canAdjust && <th className="px-3 py-2 text-right">Aksi</th>}
                </tr>
              </thead>
              <tbody>
                {ledger.map((e) => {
                  const m = TYPE_META[e.type] || { label: e.type, cls: "bg-gray-100 text-gray-600", icon: History };
                  const Icon = m.icon;
                  const pos = (e.amount || 0) >= 0;
                  const isVoid = e.status === "void" || e.reversed;
                  // R5.4 — hanya adjust & redeem yang bisa dibatalkan langsung; issue → via reversal retur.
                  const canReverse = ["adjust", "redeem"].includes(e.type) && !isVoid;
                  return (
                    <tr key={e.id} data-testid={`sc-ledger-row-${e.id}`} className={`border-b border-[#F5F5F7] last:border-0 ${isVoid ? "opacity-60" : ""}`}>
                      <td className="px-3 py-2 text-[#6B6B73] whitespace-nowrap">{fmtDate(e.created_at)}</td>
                      <td className="px-3 py-2">
                        <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold ${m.cls}`}><Icon size={11} /> {m.label}</span>
                        {isVoid && <span className="ml-1 inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[9px] font-bold bg-[#F1F1F3] text-[#8E8E93]" data-testid={`sc-ledger-void-${e.id}`}><Ban size={9} /> dibatalkan</span>}
                      </td>
                      <td className="px-3 py-2 text-[#0058CC] font-medium">{e.ref_number || "—"}</td>
                      <td className="px-3 py-2 text-[#6B6B73] max-w-[200px] truncate" title={e.note}>{e.note || "—"}</td>
                      <td className={`px-3 py-2 text-right tabular-nums font-bold ${pos ? "text-[#1B7F4B]" : "text-[#C0392B]"} ${isVoid ? "line-through" : ""}`}>{pos ? "+" : ""}{formatCurrency(e.amount)}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-[#1C1C1E]">{formatCurrency(e.balance_after)}</td>
                      {canAdjust && (
                        <td className="px-3 py-2 text-right whitespace-nowrap">
                          {canReverse ? (
                            <button data-testid={`sc-reverse-btn-${e.id}`} className="secondary-button py-1 px-2 text-[11px] text-[#6B219A] border-[#E6D3F5] hover:bg-[#F3EAFB]"
                                    onClick={() => onReverse(e)}><RotateCcw size={12} /> Batalkan</button>
                          ) : e.type === "issue" && !isVoid ? (
                            <span className="text-[10px] text-[#9A9BA3]" title="Store credit terbit dari retur — batalkan lewat pembalikan retur sumbernya">via retur</span>
                          ) : (
                            <span className="text-[10px] text-[#C7C7CC]">—</span>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function Kpi({ label, value, icon: Icon, tone = "", testId }) {
  return (
    <div className="section-card" data-testid={testId}>
      <div className="section-body flex items-center gap-3 py-3">
        <div className="w-9 h-9 rounded-lg bg-[#F3EAFB] flex items-center justify-center"><Icon size={17} className="text-[#6B219A]" /></div>
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p>
          <p className={`text-[17px] font-bold tabular-nums truncate ${tone || "text-[#1C1C1E]"}`} data-testid={`${testId}-value`}>{value}</p>
        </div>
      </div>
    </div>
  );
}
