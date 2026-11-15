/**
 * CustomerCardSections (MN-T3) — bagian baru **kartu pelanggan** (`Customer360Panel`): kepala empat angka, Pembayaran,
 * dan Kasus. Tiap bagian memanggil endpoint layar sumbernya sendiri (izin satu tempat) hanya bila bagiannya ada di
 * `sections_allowed` jawaban `…/360`; memuat / galat / kosong dibedakan, galat satu bagian tidak mengosongkan bagian lain.
 *
 *  · Kepala: "Eksposur" · "Plafon" (`GET /customers/{id}/exposure`, angka mesin = kotak Eksposur CR-T5) · "Lewat jatuh
 *    tempo" · "Titipan & saldo kredit" (`GET /customers/{id}/balance`, saldo tersimpan CR-T2). PT = PT aktif; mode
 *    Semua PT = PT pemilik data pelanggan, ditulis labelnya (N3, tanpa menjumlah lintas PT).
 *  · Pembayaran: `GET /ar-receipts?customer_id` (berhalaman, jumlah total), `GET /ar-receipts/deposit`,
 *    `GET /store-credit/ledger?customer_id` (`ar_receipt.view`).
 *  · Kasus: `GET /finance-cases?customer_id` (`finance_case.view`).
 * Lebar tabel (kartu ±864 px; halaman CRM 1280 px kolom kanan ±686 px): kwitansi 5 kolom ±590 px; kasus 4 kolom ±500 px.
 */
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CalendarClock, Scale, Wallet } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { MetricRow } from "../../components/ListPageParts";
import PagedRows from "../../components/PagedRows";
import { formatCurrency, formatDate } from "../../utils/formatters";
import { DocPill, SectionState } from "../finance/cards/partyCards";

const PAGE = 10;

export function CustomerCardHead({ customer, selectedEntity, entityLabel }) {
  const eid = selectedEntity && selectedEntity !== "all" ? selectedEntity : customer?.entity_id || "";
  const [state, setState] = useState({ loading: true, error: false, exposure: null, balance: null });
  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: false }));
    try {
      const params = eid ? { entity_id: eid } : {};
      const [ex, bal] = await Promise.all([
        axios.get(`${API}/customers/${customer.id}/exposure`, { params }),
        axios.get(`${API}/customers/${customer.id}/balance`, { params }),
      ]);
      setState({ loading: false, error: false, exposure: ex.data, balance: bal.data });
    } catch { setState({ loading: false, error: true, exposure: null, balance: null }); }
  }, [customer.id, eid]);
  useEffect(() => { load(); }, [load]);
  const row = (k) => (state.exposure?.rows || []).find((r) => r.key === k) || {};
  const b = state.balance || {};
  const titipan = (Number(b.deposit_balance) || 0) + (Number(b.store_credit_balance) || 0);
  const plafon = row("plafon");
  return (
    <div data-testid="customer-card-head">
      <SectionState loading={state.loading && !state.exposure} error={state.error} onRetry={load} testId="customer-card-head">
        <MetricRow testId="customer-card-metrics" items={[
          { label: "Eksposur", value: formatCurrency(row("eksposur").amount || 0), icon: Scale, testId: "customer-card-exposure" },
          { label: "Plafon", value: plafon.amount === null || plafon.amount === undefined ? (plafon.note || "tanpa batas") : formatCurrency(plafon.amount),
            icon: Wallet, testId: "customer-card-limit" },
          { label: "Lewat jatuh tempo", value: formatCurrency(b.overdue_amount || 0), icon: AlertTriangle,
            hint: Number(b.days_overdue) > 0 ? `telat terlama ${b.days_overdue} hari` : "", testId: "customer-card-overdue" },
          { label: "Titipan & saldo kredit", value: formatCurrency(titipan), icon: CalendarClock, testId: "customer-card-deposit" },
        ]} />
        {entityLabel && <p className="mt-1 text-fs-12 text-kn-text-2" data-testid="customer-card-head-pt">Angka untuk {entityLabel}.</p>}
      </SectionState>
    </div>
  );
}

function useLoad(fetcher, deps) {
  const [st, setSt] = useState({ loading: true, error: false, data: null });
  const load = useCallback(async () => {
    setSt((s) => ({ ...s, loading: true, error: false }));
    try { setSt({ loading: false, error: false, data: await fetcher() }); }
    catch { setSt({ loading: false, error: true, data: null }); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { load(); }, [load]);
  return { ...st, reload: load };
}

export function CustomerPaymentsSection({ customerId, selectedEntity }) {
  const [page, setPage] = useState(1);
  const params = selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {};
  const rc = useLoad(async () => (await axios.get(`${API}/ar-receipts`, {
    params: { customer_id: customerId, page, page_size: PAGE, ...params } })).data, [customerId, page, selectedEntity]);
  const dep = useLoad(async () => (await axios.get(`${API}/ar-receipts/deposit`, { params: { customer_id: customerId } })).data,
    [customerId]);
  const sc = useLoad(async () => (await axios.get(`${API}/store-credit/ledger`, {
    params: { customer_id: customerId, ...params } })).data || [], [customerId, selectedEntity]);
  const items = rc.data?.items || [];
  const total = Number(rc.data?.total || 0);
  const pages = Math.max(1, Math.ceil(total / PAGE));
  return (
    <div className="space-y-3" data-testid="customer-card-payments">
      <div>
        <div className="mb-1 flex items-center justify-between gap-2">
          <h4 className="text-fs-13 font-bold">Kwitansi</h4>
          {!rc.loading && !rc.error && <span className="text-fs-12 text-kn-text-2" data-testid="customer-card-receipts-total">{total} kwitansi</span>}
        </div>
        <SectionState loading={rc.loading} error={rc.error} empty={!items.length} onRetry={rc.reload} testId="customer-card-receipts">
          <div className="table-wrap">
            <table className="data-table head-wrap" data-testid="customer-card-receipts-table">
              <thead><tr><th>Nomor</th><th>Tanggal</th><th>Cara bayar</th><th>Status</th><th className="text-right">Nominal</th></tr></thead>
              <tbody>
                {items.map((r) => (
                  <tr key={r.id} data-testid={`customer-card-receipt-${r.id}`}>
                    <td className="whitespace-nowrap font-semibold">{r.number}</td>
                    <td className="whitespace-nowrap">{formatDate(r.receipt_date || r.created_at)}</td>
                    <td>{r.method_label || r.method || "—"}</td>
                    <td><DocPill status={r.status === "void" ? "void" : "posted"} label={r.status === "void" ? "Dibatalkan" : "Tercatat"} /></td>
                    <td className="whitespace-nowrap text-right tabular-nums">{formatCurrency(r.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {pages > 1 && (
            <div className="mt-1 flex items-center justify-end gap-2 text-fs-12" data-testid="customer-card-receipts-pager">
              <span className="tabular-nums text-kn-text-2">Halaman {page} / {pages}</span>
              <button type="button" className="secondary-button btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Sebelumnya</button>
              <button type="button" className="secondary-button btn-sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Berikutnya</button>
            </div>
          )}
        </SectionState>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-md border border-kn-divider p-3" data-testid="customer-card-deposit-box">
          <p className="field-label">Titipan pelanggan</p>
          <SectionState loading={dep.loading} error={dep.error} onRetry={dep.reload} testId="customer-card-deposit-state">
            <p className="whitespace-nowrap text-fs-16 font-bold tabular-nums">{formatCurrency(dep.data?.deposit_balance || 0)}</p>
          </SectionState>
        </div>
        <div className="rounded-md border border-kn-divider p-3" data-testid="customer-card-store-credit">
          <p className="field-label">Saldo kredit (mutasi)</p>
          <SectionState loading={sc.loading} error={sc.error} empty={!(sc.data || []).length} onRetry={sc.reload} testId="customer-card-store-credit-state">
            <ul className="divide-y divide-kn-divider text-fs-12">
              {(sc.data || []).slice(0, 5).map((m, i) => (
                <li key={m.id || i} className="flex justify-between gap-2 py-1">
                  <span className="min-w-0 truncate">{formatDate(m.created_at)} · {m.note || m.kind || "Mutasi"}</span>
                  <span className="whitespace-nowrap tabular-nums">{formatCurrency(m.amount)}</span>
                </li>
              ))}
            </ul>
            <p className="text-fs-12 text-kn-text-2">{(sc.data || []).length} mutasi</p>
          </SectionState>
        </div>
      </div>
    </div>
  );
}

export function CustomerCasesSection({ customerId }) {
  const cs = useLoad(async () => (await axios.get(`${API}/finance-cases`, { params: { customer_id: customerId } })).data || [],
    [customerId]);
  const rows = cs.data || [];
  return (
    <div data-testid="customer-card-cases">
      <div className="mb-1 flex items-center justify-between gap-2">
        <h4 className="text-fs-13 font-bold">Kasus keuangan</h4>
        {!cs.loading && !cs.error && <span className="text-fs-12 text-kn-text-2">{rows.length} kasus</span>}
      </div>
      <SectionState loading={cs.loading} error={cs.error} empty={!rows.length} onRetry={cs.reload} testId="customer-card-cases-state">
        <div className="table-wrap">
          <table className="data-table head-wrap" data-testid="customer-card-cases-table">
            <thead><tr><th>Nomor</th><th>Jenis</th><th>Status</th><th className="text-right">Nilai</th></tr></thead>
            <tbody>
              <PagedRows rows={rows} pageSize={PAGE} testId="customer-card-cases-pager">{(c) => (
                <tr key={c.id} data-testid={`customer-card-case-${c.id}`}>
                  <td className="whitespace-nowrap font-semibold">{c.number}</td>
                  <td>{c.case_type_label || c.case_type}</td>
                  <td><DocPill status={c.status} /></td>
                  <td className="whitespace-nowrap text-right tabular-nums">{formatCurrency(c.amount)}</td>
                </tr>
              )}</PagedRows>
            </tbody>
          </table>
        </div>
      </SectionState>
    </div>
  );
}
