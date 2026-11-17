/**
 * CustomerCreditView (MN-T2) — Keuangan › Piutang › **Titipan & Saldo Kredit**: SATU tabel per pelanggan (dulu dua layar:
 * Uang Muka Pelanggan dan Saldo Kredit, dibungkus chip oleh MN-T1).
 *
 * Sumber (tidak digabung di server — `02` D1, satu angka satu pemilik; label sumber di kepala kolom):
 *  · `GET /api/ar/advance-report` (`accounting.view` / `penalty.issue`) → "Uang muka pesanan belum dikirim" (+ pesanan
 *    penyumbangnya) dan "Deposit" (`customers.deposit_balance`: satu angka per pelanggan, tanpa PT, tanpa riwayat);
 *  · `GET /api/store-credit` (`ar_receipt.view`) → "Saldo kredit" per PT (buku saldo kredit, ada riwayat
 *    `GET /api/store-credit/ledger`).
 * Kolom yang sumbernya tidak boleh dibaca peran ini tidak ditampilkan (keterangan di atas tabel), bukan diisi 0.
 * Baris dibuka (tombol panah di sel Pelanggan): pesanan penyumbang uang muka + saldo kredit per PT beserta riwayatnya.
 * Aksi saldo kredit — "Pakai saldo" (`ar_receipt.create`), "Sesuaikan" & "Balik" (`ar_receipt.void`) — per PT, pop-up
 * baku `StoreCreditModals.jsx`. Mode Semua PT: aksi mati dengan petunjuk "Pilih satu PT untuk mengubah saldo." (N3).
 *
 * Lebar tabel (cek layar MN-T2; kartu ±740 px di 1024 / ±1010 px di 1280): Pelanggan ±183 (≥ 1280 px ±223) · empat
 * kolom rupiah ±118 · Umur tertua ±84 (≥ 1280 px saja; di bawahnya ditulis di sel Pelanggan) → 1024: ±655 px · 1280:
 * ±779 px. Tanpa kolom aksi di baris utama (aksi per PT di rincian baris).
 */
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowDownCircle, Ban, ChevronDown, ChevronRight, Clock3, Gift, History, PackageOpen, RefreshCw, RotateCcw, TicketPercent,
  Wallet,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatDate, formatDateTime } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";
import FilterSelect from "../../components/FilterSelect";   // pola UI 16 Nov — saringan dropdown (dulu FilterChips)
import KNPager from "../../components/KNPager";
import { SearchBox } from "../../components/ListControls";
import EntityBadge from "../../components/EntityBadge";
import EntityScopeBanner from "../../components/EntityScopeBanner";
import useViewPreset from "../../hooks/useViewPreset";
import { can } from "../../config/roles";
import { AdjustModal, RedeemModal, ReverseModal } from "./StoreCreditModals";
import { bucketForDays, bucketMeta } from "./agingBuckets";

export const PAGE_SIZE = 25;
export const TEKS_KOSONG = "Tidak ada titipan maupun saldo kredit.";
export const PETUNJUK_SATU_PT = "Pilih satu PT untuk mengubah saldo.";
export const SARINGAN = [
  { key: "semua", label: "Semua" },
  { key: "uang_muka", label: "Punya uang muka", test: (r) => r.uang_muka > 0 },
  { key: "deposit", label: "Punya deposit", test: (r) => r.deposit > 0 },
  { key: "saldo_kredit", label: "Punya saldo kredit", test: (r) => r.saldo_kredit > 0 },
];
/** `preset.bagian` alias lama (MN-T1) → saringan. */
export const BAGIAN_KE_SARINGAN = { titipan: "uang_muka", saldo: "saldo_kredit" };
const STATUS_PESANAN = {
  draft: "Draf", waiting_approval: "Menunggu persetujuan", approved: "Disetujui", confirmed: "Dikonfirmasi",
  partially_picked: "Sebagian diambil", picked: "Diambil", partially_shipped: "Dikirim sebagian",
};
const JENIS_MUTASI = {
  issue: { label: "Terbit", cls: "status-done", icon: Gift },
  redeem: { label: "Pakai", cls: "status-shipped", icon: ArrowDownCircle },
  adjust: { label: "Sesuai", cls: "status-pending", icon: TicketPercent },
  reversal: { label: "Pembalikan", cls: "status-draft", icon: RotateCcw },
};
const r2 = (v) => Math.round((Number(v) || 0) * 100) / 100;

/**
 * Gabung dua sumber menjadi satu baris per pelanggan. `adv` = `rows` laporan uang muka (atau null bila tidak berizin);
 * `sc` = ringkasan saldo kredit per (pelanggan, PT) (atau null). Jumlah = uang muka + deposit + saldo kredit.
 */
export function gabungPelanggan(adv, sc) {
  const peta = new Map();
  const ambil = (id, nama) => {
    if (!peta.has(id)) {
      peta.set(id, { customer_id: id, customer_name: nama || "—", uang_muka: 0, deposit: 0, saldo_kredit: 0, jumlah: 0,
        oldest_days: 0, orders: [], saldo_pt: [] });
    }
    const r = peta.get(id);
    if (nama && (!r.customer_name || r.customer_name === "—")) r.customer_name = nama;
    return r;
  };
  for (const c of adv || []) {
    const r = ambil(c.customer_id, c.customer_name);
    r.uang_muka = r2(r.uang_muka + (Number(c.advance_orders) || 0));
    r.deposit = r2(r.deposit + (Number(c.deposit_balance) || 0));
    r.oldest_days = Math.max(r.oldest_days, Number(c.oldest_days) || 0);
    r.orders = r.orders.concat(c.orders || []);
  }
  for (const s of sc || []) {
    const r = ambil(s.customer_id, s.customer_name);
    r.saldo_kredit = r2(r.saldo_kredit + (Number(s.balance) || 0));
    r.saldo_pt.push(s);
  }
  return [...peta.values()].map((r) => ({ ...r, jumlah: r2(r.uang_muka + r.deposit + r.saldo_kredit) }))
    .sort((a, b) => b.jumlah - a.jumlah || String(a.customer_name).localeCompare(String(b.customer_name)));
}

export default function CustomerCreditView({ currentUser, selectedEntity = "all", onOpenDocument, saringanAwal = "" }) {
  const perms = currentUser?.permissions || {};
  const bacaTitipan = can(perms, "accounting", "view") || can(perms, "penalty", "issue");
  const bacaSaldo = can(perms, "ar_receipt", "view");
  const bolehPakai = can(perms, "ar_receipt", "create");
  const bolehUbah = can(perms, "ar_receipt", "void");
  const semuaPt = !selectedEntity || selectedEntity === "all";

  const [pilihan, setPilihan] = useState(null);
  const [page, setPage] = useState(1);
  const preset = useViewPreset("customer-credit", (p) => {
    if (p.saringan || p.bagian) { setPilihan(p.saringan || BAGIAN_KE_SARINGAN[p.bagian] || "semua"); setPage(1); }
  });
  const saringan = pilihan || preset?.saringan || BAGIAN_KE_SARINGAN[preset?.bagian] || saringanAwal || "semua";
  const [adv, setAdv] = useState(null);
  const [sc, setSc] = useState(null);
  const [state, setState] = useState("loading");
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState({});
  const [redeemFor, setRedeemFor] = useState(null);
  const [adjustFor, setAdjustFor] = useState(null);
  const [reverseFor, setReverseFor] = useState(null);
  const [mutasi, setMutasi] = useState({});   // `${customer}|${entity}` → {state, rows}

  const load = useCallback(async () => {
    if (!bacaTitipan && !bacaSaldo) return;
    setState("loading");
    const params = semuaPt ? {} : { entity_id: selectedEntity };
    try {
      const [a, s] = await Promise.all([
        bacaTitipan ? axios.get(`${API}/ar/advance-report`, { params }) : Promise.resolve(null),
        bacaSaldo ? axios.get(`${API}/store-credit`, { params }) : Promise.resolve(null),
      ]);
      setAdv(a ? (a.data?.rows || []) : null);
      setSc(s ? (Array.isArray(s.data) ? s.data : []) : null);
      setError(""); setState("ready"); setMutasi({});
    } catch (e) {
      setError(apiErrorText(e, "Titipan & saldo kredit tidak bisa dimuat.")); setState("error");
    }
  }, [bacaTitipan, bacaSaldo, semuaPt, selectedEntity]);
  useEffect(() => { load(); }, [load]);

  const muatMutasi = useCallback(async (row) => {
    const k = `${row.customer_id}|${row.entity_id || ""}`;
    setMutasi((m) => ({ ...m, [k]: { state: "loading", rows: [] } }));
    try {
      const r = await axios.get(`${API}/store-credit/ledger`, { params: { customer_id: row.customer_id,
        entity_id: row.entity_id || undefined } });
      setMutasi((m) => ({ ...m, [k]: { state: "ready", rows: Array.isArray(r.data) ? r.data : [] } }));
    } catch (e) {
      setMutasi((m) => ({ ...m, [k]: { state: "error", rows: [], error: apiErrorText(e, "Riwayat tidak bisa dimuat.") } }));
    }
  }, []);

  const semua = useMemo(() => gabungPelanggan(adv, sc), [adv, sc]);
  const cari = q.trim().toLowerCase();
  const cocokCari = useMemo(() => semua.filter((r) => !cari || String(r.customer_name || "").toLowerCase().includes(cari)),
    [semua, cari]);
  const aturan = SARINGAN.find((x) => x.key === saringan) || SARINGAN[0];
  const rows = cocokCari.filter((r) => !aturan.test || aturan.test(r));
  const halaman = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const total = (k) => r2(rows.reduce((s, r) => s + r[k], 0));

  if (!bacaTitipan && !bacaSaldo) {
    return (
      <div className="empty-state" data-testid="customer-credit-no-access">
        Anda belum punya akses untuk melihat titipan maupun saldo kredit pelanggan. Minta Admin menambahkan akses
        &apos;Uang Masuk, Piutang &amp; Faktur Pajak&apos;.
      </div>
    );
  }

  const toggle = (r) => {
    const buka = !open[r.customer_id];
    setOpen((s) => ({ ...s, [r.customer_id]: buka }));
    if (buka) r.saldo_pt.forEach((p) => { if (!mutasi[`${p.customer_id}|${p.entity_id || ""}`]) muatMutasi(p); });
  };
  const sesudahUbah = (row) => { load().then(() => row && muatMutasi(row)); };
  const kolom = 1 + (bacaTitipan ? 2 : 0) + (bacaSaldo ? 1 : 0) + 1 + (bacaTitipan ? 1 : 0);

  return (
    <div className="grid gap-3" data-testid="customer-credit-view">
      <EntityScopeBanner testId="cc-scope" />
      <section className="section-card">
        <div className="section-head">
          <div className="flex min-w-0 items-center gap-2">
            <Wallet size={15} aria-hidden="true" className="text-kn-action" />
            <h2 data-testid="cc-title">Titipan &amp; Saldo Kredit</h2>
          </div>
          <button type="button" data-testid="cc-refresh" className="icon-button" onClick={load} aria-label="Muat ulang">
            <RefreshCw size={14} className={state === "loading" ? "animate-spin" : ""} /></button>
        </div>
        <div className="section-body grid gap-3">
          <p className="text-fs-12 text-kn-text-2">
            Uang pelanggan yang dipegang perusahaan: uang muka pesanan yang barangnya belum dikirim, deposit (kelebihan
            bayar yang belum dialokasikan), dan saldo kredit (mis. dari retur).</p>
          {(!bacaTitipan || !bacaSaldo) && (
            <p className="text-fs-12 text-kn-text-2" data-testid="cc-partial-note">
              {!bacaTitipan ? "Kolom uang muka dan deposit tidak ditampilkan: butuh akses laporan piutang (akuntansi)."
                : "Kolom saldo kredit tidak ditampilkan: butuh akses lihat penerimaan pembayaran."}</p>
          )}
          <SearchBox value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Cari pelanggan…" testId="cc-search" />
          <FilterSelect testId="cc-filter" ariaLabel="Saring titipan" value={saringan}
            onChange={(k) => { setPilihan(k); setPage(1); }}
            options={SARINGAN.filter((x) => (x.key === "saldo_kredit" ? bacaSaldo : x.key === "semua" || bacaTitipan))
              .map((x) => ({ key: x.key, label: x.label,
                count: state === "ready" ? cocokCari.filter((r) => !x.test || x.test(r)).length : undefined }))} />
        </div>
      </section>

      {state === "error" && <ErrorNotice testId="cc-error" message={error} onRetry={load} />}
      {state === "loading" && !adv && !sc && (
        <div className="section-card section-pad text-fs-13 text-kn-text-2" role="status" data-testid="cc-loading">Memuat…</div>
      )}
      {state === "ready" && rows.length === 0 && (
        <div className="section-card section-pad text-center text-fs-13 text-kn-text-2" data-testid="cc-empty">
          {cari || saringan !== "semua" ? "Tidak ada pelanggan yang cocok dengan saringan ini." : TEKS_KOSONG}</div>
      )}
      {state === "ready" && rows.length > 0 && (
        <section className="section-card overflow-hidden" data-testid="cc-list">
          <div className="overflow-x-auto">
            <table className="data-table head-wrap w-full" data-testid="cc-table">
              <thead>
                <tr>
                  <th>Pelanggan</th>
                  {bacaTitipan && <th className="text-right">Uang muka pesanan belum dikirim</th>}
                  {bacaTitipan && (
                    <th className="text-right">Deposit
                      <span className="block font-normal normal-case tracking-normal text-kn-text-2" data-testid="cc-head-deposit">
                        Satu angka per pelanggan, tanpa PT</span></th>)}
                  {bacaSaldo && (
                    <th className="text-right">Saldo kredit
                      <span className="block font-normal normal-case tracking-normal text-kn-text-2" data-testid="cc-head-saldo">
                        Per PT, ada riwayat</span></th>)}
                  <th className="text-right">Jumlah</th>
                  {bacaTitipan && <th className="hidden text-right xl:table-cell">Umur tertua</th>}
                </tr>
              </thead>
              <tbody>
                {halaman.map((r) => (
                  <Fragment key={r.customer_id}>
                    <tr data-testid={`cc-row-${r.customer_id}`}>
                      <td>
                        <button type="button" className="link-button max-w-[160px] text-left font-semibold xl:max-w-[200px]"
                          aria-expanded={!!open[r.customer_id]} data-testid={`cc-toggle-${r.customer_id}`}
                          onClick={() => toggle(r)} title={r.customer_name}>
                          {open[r.customer_id] ? <ChevronDown size={13} aria-hidden="true" className="shrink-0" />
                            : <ChevronRight size={13} aria-hidden="true" className="shrink-0" />}
                          <span className="truncate">{r.customer_name}</span>
                        </button>
                        {bacaTitipan && r.oldest_days > 0 && (
                          <span className="block text-fs-12 text-kn-text-2 xl:hidden">tertua {r.oldest_days} hari</span>)}
                      </td>
                      {bacaTitipan && <td className="text-right tabular-nums" data-testid={`cc-advance-${r.customer_id}`}>{formatCurrency(r.uang_muka)}</td>}
                      {bacaTitipan && <td className="text-right tabular-nums" data-testid={`cc-deposit-${r.customer_id}`}>{formatCurrency(r.deposit)}</td>}
                      {bacaSaldo && <td className="text-right tabular-nums" data-testid={`cc-credit-${r.customer_id}`}>{formatCurrency(r.saldo_kredit)}</td>}
                      <td className="text-right font-bold tabular-nums" data-testid={`cc-total-${r.customer_id}`}>{formatCurrency(r.jumlah)}</td>
                      {bacaTitipan && (
                        <td className="hidden text-right text-kn-text-2 xl:table-cell">{r.oldest_days > 0 ? `${r.oldest_days} hari` : (r.orders.length ? "< 1 hari" : "—")}</td>)}
                    </tr>
                    {open[r.customer_id] && (
                      <tr data-testid={`cc-detail-${r.customer_id}`}>
                        <td colSpan={kolom} className="bg-kn-neutral-soft">
                          <div className="grid gap-3">
                            {bacaTitipan && <PesananUangMuka orders={r.orders} onOpenDocument={onOpenDocument} />}
                            {bacaSaldo && (
                              <SaldoKreditPerPt baris={r.saldo_pt} mutasi={mutasi} semuaPt={semuaPt}
                                bolehPakai={bolehPakai} bolehUbah={bolehUbah} onRetry={muatMutasi}
                                onRedeem={setRedeemFor} onAdjust={setAdjustFor} onReverse={setReverseFor} />
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-fs-12 text-kn-text-2">
            <span data-testid="cc-total">
              {rows.length} pelanggan
              {bacaTitipan && ` · uang muka ${formatCurrency(total("uang_muka"))} · deposit ${formatCurrency(total("deposit"))}`}
              {bacaSaldo && ` · saldo kredit ${formatCurrency(total("saldo_kredit"))}`}
            </span>
            <KNPager page={page} pageSize={PAGE_SIZE} total={rows.length} onChange={setPage} testId="cc-pager" />
          </div>
        </section>
      )}

      {redeemFor && (
        <RedeemModal row={redeemFor} onClose={() => setRedeemFor(null)}
          onDone={() => { const row = redeemFor; setRedeemFor(null); sesudahUbah(row); }} />
      )}
      {adjustFor && (
        <AdjustModal row={adjustFor} onClose={() => setAdjustFor(null)}
          onDone={() => { const row = adjustFor; setAdjustFor(null); sesudahUbah(row); }} />
      )}
      {reverseFor && (
        <ReverseModal entry={reverseFor.entry} typeLabel={JENIS_MUTASI[reverseFor.entry.type]?.label}
          onClose={() => setReverseFor(null)}
          onDone={() => { const row = reverseFor.row; setReverseFor(null); sesudahUbah(row); }} />
      )}
    </div>
  );
}

function PesananUangMuka({ orders, onOpenDocument }) {
  return (
    <div className="grid gap-1" data-testid="cc-orders">
      <p className="flex items-center gap-1.5 text-fs-12 font-bold text-kn-text">
        <PackageOpen size={13} aria-hidden="true" /> Pesanan penyumbang uang muka</p>
      {orders.length === 0 ? (
        <p className="text-fs-12 text-kn-text-2">Tidak ada pesanan belum dikirim yang sudah dibayar di muka.</p>
      ) : (
        <table className="data-table w-full bg-white">
          <thead><tr><th>Pesanan</th><th className="text-right">Uang muka</th><th className="text-right">Umur</th></tr></thead>
          <tbody>
            {orders.map((o) => {
              const b = bucketMeta(bucketForDays(o.age_days));
              return (
                <tr key={o.order_id} data-testid={`cc-order-${o.order_id}`}>
                  <td>
                    <button type="button" className="link-button font-semibold" data-testid={`cc-order-open-${o.order_id}`}
                      onClick={() => onOpenDocument?.({ view: "orders", nav_id: "sales-orders", focus_type: "sales_order",
                        focus_id: o.order_id, number: o.order_number })}>{o.order_number}</button>
                    <span className="block text-fs-12 text-kn-text-2">
                      {STATUS_PESANAN[o.status] || "Belum dikirim"} · pendapatan diakui {o.revenue_recognized_pct ?? 0}%
                      {(o.receipts || []).length ? ` · kwitansi ${(o.receipts || []).map((x) => x.receipt_number).filter(Boolean).join(", ")}` : ""}</span>
                  </td>
                  <td className="text-right tabular-nums">{formatCurrency(o.advance_unrecognized)}
                    <span className="block text-fs-12 text-kn-text-2">dari {formatCurrency(o.grand_total)}</span></td>
                  <td className="text-right">
                    <span className="status-pill" style={{ background: b.bg, color: b.tone }}><Clock3 size={12} aria-hidden="true" />{b.label}</span>
                    <span className="block whitespace-nowrap text-fs-12 text-kn-text-2">{o.age_days} hari · sejak {formatDate(o.oldest_receipt_date) || "—"}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

function SaldoKreditPerPt({ baris, mutasi, semuaPt, bolehPakai, bolehUbah, onRetry, onRedeem, onAdjust, onReverse }) {
  return (
    <div className="grid gap-2" data-testid="cc-credit-detail">
      <p className="flex items-center gap-1.5 text-fs-12 font-bold text-kn-text">
        <History size={13} aria-hidden="true" /> Saldo kredit per PT dan riwayatnya</p>
      {baris.length === 0 && <p className="text-fs-12 text-kn-text-2">Pelanggan ini tidak punya saldo kredit.</p>}
      {semuaPt && baris.length > 0 && (bolehPakai || bolehUbah) && (
        <p className="text-fs-12 text-kn-text-2" data-testid="cc-one-pt-hint">{PETUNJUK_SATU_PT}</p>)}
      {baris.map((p) => {
        const k = `${p.customer_id}|${p.entity_id || ""}`;
        const m = mutasi[k] || { state: "loading", rows: [] };
        return (
          <div key={k} className="rounded-md border border-kn-divider bg-white" data-testid={`cc-credit-pt-${p.entity_id || "x"}`}>
            <div className="flex flex-wrap items-center gap-2 px-3 py-2">
              {p.entity_id && <EntityBadge entityId={p.entity_id} />}
              <span className="text-fs-13">Saldo <b className="tabular-nums">{formatCurrency(p.balance)}</b></span>
              <span className="text-fs-12 text-kn-text-2">{p.entries || 0} transaksi · terakhir {formatDateTime(p.last_at) || "—"}</span>
              <span className="ml-auto inline-flex flex-wrap items-center gap-2">
                {bolehPakai && (
                  <button type="button" className="primary-button btn-sm whitespace-nowrap" data-testid={`cc-redeem-${p.customer_id}`}
                    disabled={semuaPt || (Number(p.balance) || 0) <= 0}
                    title={semuaPt ? PETUNJUK_SATU_PT : (Number(p.balance) || 0) <= 0 ? "Saldo kredit tidak positif." : undefined}
                    onClick={() => onRedeem(p)}><ArrowDownCircle size={13} aria-hidden="true" /> Pakai saldo</button>)}
                {bolehUbah && (
                  <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid={`cc-adjust-${p.customer_id}`}
                    disabled={semuaPt} title={semuaPt ? PETUNJUK_SATU_PT : undefined}
                    onClick={() => onAdjust(p)}><TicketPercent size={13} aria-hidden="true" /> Sesuaikan</button>)}
              </span>
            </div>
            {m.state === "loading" && <p className="px-3 pb-2 text-fs-12 text-kn-text-2">Memuat riwayat…</p>}
            {m.state === "error" && <div className="px-3 pb-2"><ErrorNotice message={m.error} onRetry={() => onRetry(p)} /></div>}
            {m.state === "ready" && m.rows.length === 0 && <p className="px-3 pb-2 text-fs-12 text-kn-text-2">Belum ada transaksi.</p>}
            {m.state === "ready" && m.rows.length > 0 && (
              <table className="data-table w-full" data-testid={`cc-ledger-${p.customer_id}`}>
                <thead><tr><th>Waktu</th><th>Jenis</th><th className="text-right">Nilai</th><th className="text-right">Saldo</th>
                  {bolehUbah && <th className="col-sticky-end text-right">Aksi</th>}</tr></thead>
                <tbody>
                  {m.rows.map((e) => {
                    const j = JENIS_MUTASI[e.type] || { label: "Lainnya", cls: "status-draft", icon: History };
                    const Icon = j.icon;
                    const batal = e.status === "void" || e.reversed;
                    const bisaBalik = ["adjust", "redeem"].includes(e.type) && !batal;
                    return (
                      <tr key={e.id} data-testid={`cc-ledger-row-${e.id}`} className={batal ? "opacity-60" : ""}>
                        <td className="whitespace-nowrap text-kn-text-2">{formatDateTime(e.created_at)}</td>
                        <td>
                          <span className={`status-pill ${j.cls}`}><Icon size={12} aria-hidden="true" />{j.label}</span>
                          {batal && <span className="status-pill status-cancelled ml-1"><Ban size={12} aria-hidden="true" />Dibatalkan</span>}
                          <span className="block max-w-[200px] truncate text-fs-12 text-kn-text-2" title={e.note}>
                            {[e.ref_number, e.note].filter(Boolean).join(" · ") || "—"}</span>
                        </td>
                        <td className={`text-right tabular-nums font-semibold ${batal ? "line-through" : ""}`}>
                          {(Number(e.amount) || 0) >= 0 ? "+" : ""}{formatCurrency(e.amount)}</td>
                        <td className="text-right tabular-nums">{formatCurrency(e.balance_after)}</td>
                        {bolehUbah && (
                          <td className="col-sticky-end text-right">
                            {bisaBalik ? (
                              <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid={`cc-reverse-${e.id}`}
                                disabled={semuaPt} title={semuaPt ? PETUNJUK_SATU_PT : undefined}
                                onClick={() => onReverse({ entry: e, row: p })}><RotateCcw size={13} aria-hidden="true" /> Balik</button>
                            ) : e.type === "issue" && !batal ? (
                              <span className="text-fs-12 text-kn-text-2">lewat retur</span>
                            ) : <span className="text-fs-12 text-kn-text-2">—</span>}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        );
      })}
    </div>
  );
}
