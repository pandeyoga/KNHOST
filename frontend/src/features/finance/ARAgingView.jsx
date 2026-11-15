/**
 * ARAgingView (EPIC7-A) — Piutang / Accounts Receivable Aging.
 * Akses admin/manager. Sumber: GET /api/ar/aging (+ /ar/aging/{customer_id}).
 * PK-41 — kolom umur dari `bucket_labels` server (batas `ar.aging_buckets` PT; kolom pertama "Belum jatuh tempo"),
 * umur per surat jalan, dan baris pencocokan "Piutang tercatat · Saldo akun piutang · Selisih" di bawah total.
 *
 * FASE G-3 (permintaan #2 pemilik) — kolom denda **tidak lagi angka mati**:
 *   • estimasi tetap ditampilkan (informasional, dari kebijakan bunga & tenggang);
 *   • di sampingnya muncul **nota denda NYATA** (FASE G-2) yang bisa diklik ke dokumennya
 *     — lengkap status usulan / terbit / dibebaskan / dibayar;
 *   • yang belum pernah dibuatkan nota ditandai jelas, dan bisa **dibuatkan sekarang**
 *     lewat tombol “Buat Nota Denda” (nota lahir sebagai usulan, belum menyentuh buku besar).
 *
 * PK-43 (UX-15) — dari rincian pelanggan orang langsung mencatat pembayaran (form kwitansi baku `ARReceiptModal`, sama
 * dengan Penagihan & Meja Finance); sesudah tersimpan: pemberitahuan sukses dari form, lalu daftar dan rincian dimuat
 * ulang (sisa piutang pelanggan langsung turun).
 */
import { apiErrorText } from "../../utils/apiError";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  RefreshCw, Search, Wallet, AlertTriangle, TrendingDown, Clock3, Users,
  BadgeDollarSign, Loader2, Receipt, Building2 } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import { formatCurrency } from "../../utils/formatters";
import { CreditStatusPill } from "../crm/crmUtils";
import { MetricRow } from "../../components/ListPageParts";
import ARAgingDetail from "./ARAgingDetail";
// Fase 3 · P4 (D-12 B) — kelompok umur dari util bersama (sama dengan Uang Muka Pelanggan). PK-41 — judul dari server.
import { bucketColumns } from "./agingBuckets";
// INV-ROLE-01 — wewenang dibaca dari IZIN, bukan dari daftar nama peran.
import { can } from "../../config/roles";
import DetailModal from "../../components/DetailModal";
import ReceivePaymentModal, { TEKS_PILIH_PT } from "./payments/ReceivePaymentModal";   // MN-T3 — satu form terima pembayaran
import { CustomerCardLink } from "./cards/partyCards";   // MN-T3 — nama pelanggan → kartu pelanggan

// PK-41 — nada sel per kolom umur (kunci tetap; judul kolom dari server).
const WARN_KEYS = new Set(["b1_30", "b31_60"]);
const DANGER_KEYS = new Set(["b61_90", "b90_plus"]);

const BASE_LABEL = {   // CR-T4 — kata sama dengan form aturan denda (`payments/penaltyRuleUi`)
  installment: "sisa tagihan yang telat",
  outstanding: "seluruh sisa pesanan",
};

import PagedRows from "@/components/PagedRows";

export default function ARAgingView({ selectedEntity, currentUser, focusDoc, onClearFocus }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [onlyOverdue, setOnlyOverdue] = useState(false);
  const [selected, setSelected] = useState(null);   // customer_id
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");   // CR-T2 — galat muat rincian dibedakan dari "kosong"
  const [accruing, setAccruing] = useState("");
  const [flash, setFlash] = useState("");
  const [payFor, setPayFor] = useState(null);   // PK-43 — { orderId } form kwitansi yang sedang dibuka
  const [rowPay, setRowPay] = useState(null);   // MN-T3 — { id, name } dari tombol baris
  const [paidMsg, setPaidMsg] = useState("");    // PK-43 — pemberitahuan sukses dari form kwitansi (di rincian)

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      const res = await axios.get(`${API}/ar/aging`, { params });
      setData(res.data || null);
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat data piutang (AR aging)."));
    } finally {
      setLoading(false);
    }
  }, [selectedEntity]);

  useEffect(() => { load(); }, [load]);

  // Deep-link dari Meja Finance (jatuh tempo): saring ke pelanggan + buka rinciannya.
  useEffect(() => {
    if (focusDoc?.focus_type !== "customer" || !focusDoc.focus_id) return;
    if (focusDoc.number) setQ(focusDoc.number);
    openDetail(focusDoc.focus_id);
    onClearFocus?.();
  }, [focusDoc?.focus_id]); // eslint-disable-line

  const openDetail = useCallback(async (cid) => {
    setSelected(cid);
    setDetail(null);
    setDetailError("");
    setDetailLoading(true);
    try {
      const res = await axios.get(`${API}/ar/aging/${cid}`);
      setDetail(res.data || null);
    } catch {
      setDetail(null);
      setDetailError("Rincian piutang pelanggan ini gagal dimuat. Periksa koneksi lalu coba lagi.");
    } finally {
      setDetailLoading(false);
    }
  }, []);

  // FASE G-3 — ubah estimasi denda menjadi NOTA DENDA nyata (usulan, belum berjurnal).
  const accrue = useCallback(async (cid) => {
    setAccruing(cid);
    setFlash("");
    try {
      const res = await axios.post(`${API}/ar/aging/${cid}/accrue-penalties`);
      const n = res.data?.count || 0;
      setDetail(res.data?.detail || null);
      setSelected(cid);
      setFlash(n > 0
        ? `${n} nota denda siap: ${(res.data.penalties || []).map((p) => p.number).join(", ")}. Nota masih USULAN — belum menyentuh buku besar.`
        : "Tidak ada denda yang layak dibuatkan nota (masih dalam tenggang, di bawah minimum, atau kebijakan denda dimatikan).");
      await load();
    } catch (e) {
      setError(apiErrorText(e, "Gagal membuat nota denda."));
    } finally { setAccruing(""); }
  }, [load]);

  const totals = data?.totals || {};
  const cols = useMemo(() => bucketColumns(data?.bucket_labels), [data]);
  const dendaRate = data?.config?.denda_rate_pct_per_month || 0;
  const penaltyPolicy = data?.penalty_policy || {};

  const rows = useMemo(() => {
    let r = data?.customers || [];
    const term = q.trim().toLowerCase();
    if (term) r = r.filter((c) => `${c.customer_name} ${c.assigned_sales_name}`.toLowerCase().includes(term));
    if (onlyOverdue) r = r.filter((c) => (c.overdue || 0) > 0.01);
    return r;
  }, [data, q, onlyOverdue]);

  // UAT 24 Okt (audit UI tahap 2) — G1-01: baris TOTAL mengikuti cari/chip "Hanya Lewat Jatuh Tempo".
  // Tanpa saring → total server (semua pelanggan); dengan saring → jumlah baris yang tampil + total semua di bawahnya.
  const filtered = !!q.trim() || onlyOverdue;
  const foot = useMemo(() => {
    if (!filtered) return totals;
    const sum = (k) => rows.reduce((a, c) => a + Number(c[k] || 0), 0);
    return { current: sum("current"), b1_30: sum("b1_30"), b31_60: sum("b31_60"), b61_90: sum("b61_90"),
      b90_plus: sum("b90_plus"), total: sum("outstanding"), penalty_actual: sum("penalty_actual"), denda: sum("denda") };
  }, [filtered, rows, totals]);

  // G1-51 — persen kecil (> 0 tetapi < 0,5%) tidak dibulatkan menjadi "0%".
  const overdueRaw = totals.total > 0 ? (totals.overdue / totals.total) * 100 : 0;
  const overduePct = overdueRaw > 0 && overdueRaw < 1 ? "<1" : Math.round(overdueRaw);
  /**
   * INV-ROLE-01 (AUDIT PERAN 2026-08-15) — dulu `["admin","manager"].includes(role)`.
   * Peran `finance` justru pemegang izin `penalty.issue` (E8.1b: "denda perlu
   * diterbitkan" ada di Meja Finance), tetapi daftar nama peran ini menyembunyikan
   * tombolnya — server mengizinkan, layar melarang. Wewenang dibaca dari IZIN.
   */
  const canAccrue = can(currentUser?.permissions || {}, "penalty", "issue");
  // MN-T3 — tombol "Terima pembayaran" per baris pelanggan (= POST /ar-receipts); Semua PT → mati + alasan di atas tabel.
  const canReceive = can(currentUser?.permissions || {}, "ar_receipt", "create");
  const allPt = !selectedEntity || selectedEntity === "all";

  return (
    <div data-testid="ar-aging-view">
      {/* FASE E-0 (L9 · user story 10) — laporan piutang WAJIB menyebut entitasnya.
          Dulu `entity_id` selalu "all" dan total KSC/Kanda identik (dua PT dicampur). */}
      {data && (
        <div
          data-testid="ar-aging-entity-banner"
          className={`mb-3 flex flex-wrap items-center gap-2 rounded-md border px-3 py-2 ${
            data.is_consolidated
              ? "border-[#F0C88A] bg-[#FEF7EC]"
              : "border-[#C9DBF7] bg-[#F2F7FF]"
          }`}
        >
          <Building2 size={14} className={data.is_consolidated ? "text-[#8C4A00]" : "text-[#0058CC]"} />
          <span className="text-[11.5px] font-bold text-[#1C1C1E]" data-testid="ar-aging-entity-name">
            {data.is_consolidated ? "Mode Gabungan" : "Entitas"}: {data.entity_name || "—"}
          </span>
          <span className="text-[10.5px] text-[#6B6B73]">
            {data.is_consolidated
              ? "Angka di bawah adalah GABUNGAN beberapa badan usaha — bukan piutang satu PT."
              : "Seluruh angka di bawah milik badan usaha ini saja."}
          </span>
        </div>
      )}

      {/* KPI — Fase 3 · P4 (L-08): MetricRow baku (nol netral) menggantikan kartu KPI ungu buatan sendiri. */}
      <div className="mb-3">
        <MetricRow testId="ar-kpi" items={[
          { label: "Total Belum Lunas", value: formatCurrency(totals.total), icon: Wallet, testId: "ar-kpi-total" },
          { label: `Jatuh Tempo (${overduePct}%)`, value: formatCurrency(totals.overdue), icon: AlertTriangle, tone: "#C0392B", testId: "ar-kpi-overdue" },
          { label: "Belum jatuh tempo", value: formatCurrency(totals.current), icon: Clock3, tone: "#1B7F4B", testId: "ar-kpi-current" },
          { label: `Est. Denda (${dendaRate}%/bln)`, value: formatCurrency(totals.denda), icon: TrendingDown, tone: "#B45309", testId: "ar-kpi-denda" },
          { label: `Nota Denda (${totals.penalty_docs || 0} dok)`, value: formatCurrency(totals.penalty_actual), icon: BadgeDollarSign, tone: "#0058CC", testId: "ar-kpi-denda-doc" },
        ]} />
      </div>
      {/* Keputusan pemilik K-01 (26 Okt) — label sumber: layar operasional = sub-buku; Neraca = buku besar Piutang Usaha. */}
      <p className="mb-2 text-[11px] text-[#6B6B73]" data-testid="ar-source-label">
        Sumber angka: <b>sub-buku piutang</b> — semua dokumen penjualan belum lunas, semua pelanggan (sama dengan Control
        Tower, Beranda & Dasbor Keuangan). Neraca di Laporan Keuangan memakai saldo buku besar Piutang Usaha (hanya yang
        sudah diakui saat kirim) — lihat "Piutang tercatat (buku besar)" di bawah.
      </p>
      <LedgerExposureStrip totals={totals} />

      {/* Aging bucket strip */}
      <div className="section-card mb-3">
        <div className="section-body py-3">
          <div className="flex items-center gap-2 mb-2">
            <TrendingDown size={15} className="text-[#6B219A]" />
            <h3 className="text-[12px] font-bold text-[#1C1C1E]">Sebaran Umur Piutang</h3>
            <span className="text-[10.5px] text-[#9A9BA3] ml-auto" data-testid="ar-aging-customers">{totals.customers || 0} pelanggan · {totals.orders || 0} pesanan</span>
          </div>
          <AgingBar totals={totals} cols={cols} />
        </div>
      </div>

      {/* Master table */}
      <div className="section-card">
        <div className="section-head flex-wrap gap-2">
          <div className="flex items-center gap-2"><Wallet size={16} className="text-[#6B219A]" /><h2 data-testid="ar-aging-title">Piutang per Pelanggan</h2></div>
          <div className="flex flex-wrap items-center gap-2 ml-auto">
            <button
              data-testid="ar-aging-overdue-toggle"
              className={`text-[11px] font-semibold rounded-md px-2.5 py-1.5 border transition-colors ${onlyOverdue ? "bg-[#FCEBEA] border-[#F0B5AE] text-[#C0392B]" : "bg-white border-[#EFF0F2] text-[#6B6B73] hover:border-[#C9DBF7]"}`}
              onClick={() => setOnlyOverdue((v) => !v)}
            >
              {onlyOverdue ? "Hanya Lewat Jatuh Tempo ✓" : "Hanya Lewat Jatuh Tempo"}
            </button>
            <div className="relative">
              <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-[#9A9BA3]" />
              <input data-testid="ar-aging-search" className="field !pl-7 !py-1 !text-[12px]" placeholder="Cari pelanggan / sales..." value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            <button data-testid="ar-aging-refresh" className="icon-button" onClick={load} aria-label="Muat ulang" title="Muat ulang"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
          </div>
        </div>
        <div className="section-body">
          <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="ar-aging-error" />
          {flash && (
            <div className="notice-bar success !py-1.5 mb-2" data-testid="ar-aging-flash">
              <span className="text-[11.5px]">{flash}</span>
            </div>
          )}
          {loading ? (
            <div className="grid gap-2" data-testid="ar-aging-loading">{[0, 1, 2, 3, 4].map((i) => <div key={i} className="h-10 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
          ) : rows.length === 0 ? (
            <div data-testid="ar-aging-empty" className="py-12 text-center text-[12px] text-[#8E8E93]">
              <Users size={26} className="mx-auto mb-2 text-gray-300" />
              {onlyOverdue ? "Tidak ada piutang jatuh tempo. 🎉" : "Tidak ada piutang terbuka."}
            </div>
          ) : (
            /* Fase 3 · P4 (L-07) — tabel mentah → `.table-wrap` + `.data-table` baku. Kepala kelompok umur dari util
               bersama (D-12). Di HP tabel bergulir di dalam wadahnya; pesan kosong & pager di luar wadah gulir. */
            <div className="table-wrap">
              {canReceive && allPt && <p className="px-3 py-2 text-fs-12 text-kn-text-2" data-testid="ar-aging-receive-scope-note">{TEKS_PILIH_PT}</p>}
              <table className="data-table head-wrap min-w-[860px]" data-testid="ar-aging-table">
                <thead>
                  <tr>
                    <th>Pelanggan</th>
                    {cols.map((b) => <th key={b.key} className="text-right" data-testid={`ar-aging-col-${b.key}`}>{b.label}</th>)}
                    <th className="text-right">Belum Lunas</th>
                    <th className="text-right">Denda</th>
                    <th className="text-center">Kredit</th>
                    {canReceive && <th className="text-right col-sticky-end">Aksi</th>}
                  </tr>
                </thead>
                <tbody>
                  <PagedRows rows={rows} testId="ar-aging-pager">{(c) => (
                    <tr
                      key={c.customer_id}
                      data-testid={`ar-aging-row-${c.customer_id}`}
                      className={`cursor-pointer ${selected === c.customer_id ? "bg-[#EFF4FF]" : ""}`}
                      onClick={() => openDetail(c.customer_id)}
                    >
                      <td className="px-3 py-2">
                        <p className="font-semibold text-[#1C1C1E]"><CustomerCardLink id={c.customer_id} name={c.customer_name}
                          perms={currentUser?.permissions} testId={`ar-aging-card-${c.customer_id}`} /></p>
                        <p className="text-[10px] text-[#9A9BA3]">{c.assigned_sales_name || "—"}{c.oldest_days > 0 ? ` · telat ${c.oldest_days} hr` : ""}</p>
                      </td>
                      {cols.map((b) => <Cell key={b.key} v={c[b.key]} warn={WARN_KEYS.has(b.key)} danger={DANGER_KEYS.has(b.key)} />)}
                      <td className="px-3 py-2 text-right tabular-nums font-bold text-[#1C1C1E]">{formatCurrency(c.outstanding)}</td>
                      <td className="px-3 py-2 text-right" data-testid={`ar-denda-cell-${c.customer_id}`}>
                        {(c.penalty_docs || 0) > 0 ? (
                          <button type="button" className="group text-right"
                            data-testid={`ar-denda-link-${c.customer_id}`}
                            onClick={(e) => { e.stopPropagation(); openDetail(c.customer_id); }}>
                            <span className="block font-bold tabular-nums text-[#0058CC] group-hover:underline">
                              {formatCurrency(c.penalty_actual)}
                            </span>
                            <span className="block text-[9.5px] text-[#6B6B73]">
                              {c.penalty_docs} nota{(c.denda_undocumented || 0) > 0.01
                                ? ` · est. +${formatCurrency(c.denda_undocumented)}` : ""}
                            </span>
                          </button>
                        ) : (c.denda || 0) > 0.01 ? (
                          <div className="flex flex-col items-end gap-0.5">
                            <span className="tabular-nums text-[#B45309]">{formatCurrency(c.denda)}</span>
                            <span className="text-[9.5px] font-semibold text-[#9A9BA3]">est. — belum jadi nota</span>
                            {canAccrue && (
                              <button type="button" data-testid={`ar-denda-accrue-${c.customer_id}`}
                                className="secondary-button !py-0.5 !px-1.5 !text-[10px]"
                                disabled={accruing === c.customer_id}
                                onClick={(e) => { e.stopPropagation(); accrue(c.customer_id); }}>
                                {accruing === c.customer_id
                                  ? <Loader2 size={10} className="animate-spin" />
                                  : <Receipt size={10} />} Buat Nota
                              </button>
                            )}
                          </div>
                        ) : <span className="text-[#C7C7CC]">—</span>}
                      </td>
                      <td className="px-3 py-2 text-center"><CreditStatusPill status={c.credit_status} testId={`ar-credit-${c.customer_id}`} /></td>
                      {canReceive && (
                        <td className="px-3 py-2 text-right col-sticky-end">
                          <button type="button" className="primary-button btn-sm whitespace-nowrap" disabled={allPt}
                            data-testid={`ar-aging-receive-${c.customer_id}`}
                            onClick={(e) => { e.stopPropagation(); setRowPay({ id: c.customer_id, name: c.customer_name }); }}>
                            Terima pembayaran
                          </button>
                        </td>
                      )}
                    </tr>
                  )}</PagedRows>
                </tbody>
                <tfoot>
                  <tr className="bg-[#FAFBFC] border-t border-[#EFF0F2] text-[11px] font-bold">
                    <td className="px-3 py-2 text-[#6B6B73] uppercase text-[10px]" data-testid="ar-aging-total-label">
                      {filtered ? `Total yang tampil (${rows.length} pelanggan)` : "Total"}
                    </td>
                    {cols.map((b) => <td key={b.key} className="px-3 py-2 text-right tabular-nums">{formatCurrency(foot[b.key])}</td>)}
                    <td className="px-3 py-2 text-right tabular-nums" data-testid="ar-aging-total">{formatCurrency(foot.total)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-[#0058CC]" data-testid="ar-aging-denda-total">
                      {formatCurrency(foot.penalty_actual)}
                      <span className="block text-[9.5px] font-semibold text-[#B45309]">
                        est. {formatCurrency(foot.denda)}
                      </span>
                    </td>
                    <td className="px-3 py-2" />
                    {canReceive && <td className="px-3 py-2 col-sticky-end" />}
                  </tr>
                  {filtered && (
                    <tr className="bg-[#FAFBFC] text-[10.5px] text-[#6B6B73]" data-testid="ar-aging-total-all-row">
                      <td className="px-3 py-1.5 uppercase text-[10px]">Total semua pelanggan</td>
                      <td colSpan={cols.length} />
                      <td className="px-3 py-1.5 text-right tabular-nums" data-testid="ar-aging-total-all">{formatCurrency(totals.total)}</td>
                      <td colSpan={canReceive ? 3 : 2} />
                    </tr>
                  )}
                </tfoot>
              </table>
            </div>
          )}
          <ReconciliationLine rec={data?.reconciliation} />
          <p className="text-[10.5px] text-[#9A9BA3] mt-2">
            Umur dihitung per surat jalan: tanggal surat jalan + termin pembayaran; bagian pesanan yang belum dikirim
            belum jatuh tempo. Kolom <b>Denda</b> menampilkan
            <b> nota denda nyata</b> (dokumen yang bisa ditagih/dinegosiasikan); angka{" "}
            <i>est.</i> adalah taksiran {dendaRate}%/bulan yang <b>belum</b> dibuatkan nota.
            Taksiran dihitung dengan aturan yang sama dengan nota denda (harian, dasar{" "}
            <b>{BASE_LABEL[penaltyPolicy.base] || "aturan PT"}</b>
            {Number(penaltyPolicy.grace_days || 0) > 0 ? `, tenggang ${penaltyPolicy.grace_days} hari` : ""}); pelanggan
            dengan aturan denda khusus atau rencana bayar beraturan denda sendiri memakai aturannya.
          </p>
        </div>
      </div>

      {/* FASE P7 — rincian tampil sebagai POP-UP. Dulu dirender sebagai saudara di bawah
          tabel: setelah mengklik baris tidak ada perubahan yang terlihat karena panelnya
          berada di bawah tabel ringkasan + catatan kaki (di luar pandangan). */}
      {selected && (
        <DetailModal onClose={() => { setSelected(null); setDetail(null); setPaidMsg(""); }}
          label="Rincian piutang pelanggan" testId="ar-aging-detail-modal">
          <ARAgingDetail
            detail={detail}
            customerId={selected}
            loading={detailLoading}
            error={detailError}
            currentUser={currentUser}
            accruing={accruing === selected}
            onAccrue={() => accrue(selected)}
            onRefresh={() => openDetail(selected)}
            onClose={() => { setSelected(null); setDetail(null); setPaidMsg(""); }}
            selectedEntity={selectedEntity}
            onPay={(orderId = "") => setPayFor({ orderId })}
            notice={paidMsg}
          />
        </DetailModal>
      )}
      {rowPay && (
        <ReceivePaymentModal customerId={rowPay.id} customerName={rowPay.name} onClose={() => setRowPay(null)}
          onDone={(m) => { setRowPay(null); setFlash(m || "Pembayaran dicatat."); load(); }} />
      )}
      {selected && payFor && (
        <ReceivePaymentModal customerId={selected} customerName={detail?.customer_name || ""}
          preselectOrderId={payFor.orderId || undefined} onClose={() => setPayFor(null)}
          onDone={(m) => { setPayFor(null); setPaidMsg(m || "Pembayaran dicatat."); setFlash(m || "Pembayaran dicatat.");
            load(); openDetail(selected); }} />
      )}
    </div>
  );
}

function Cell({ v, warn, danger }) {
  const tone = (v || 0) <= 0.01 ? "text-[#C7C7CC]" : danger ? "text-[#C0392B]" : warn ? "text-[#B45309]" : "text-[#3C3C43]";
  return <td className={`px-3 py-2 text-right tabular-nums ${tone}`}>{(v || 0) > 0.01 ? formatCurrency(v) : "—"}</td>;
}

function AgingBar({ totals, cols }) {
  const total = totals.total || 0;
  return (
    <div data-testid="ar-aging-bar">
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-[#F2F2F7]">
        {cols.map((b) => {
          const v = totals[b.key] || 0;
          const pct = total > 0 ? (v / total) * 100 : 0;
          if (pct <= 0) return null;
          return <div key={b.key} title={`${b.label}: ${formatCurrency(v)}`} style={{ width: `${pct}%`, background: b.tone }} />;
        })}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        {cols.map((b) => (
          <span key={b.key} className="flex items-center gap-1.5 text-[10.5px] text-[#6B6B73]" data-testid={`ar-bucket-${b.key}`}>
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: b.tone }} />
            {b.label}: <b className="tabular-nums text-[#1C1C1E]">{formatCurrency(totals[b.key])}</b>
          </span>
        ))}
      </div>
    </div>
  );
}

// Audit UI 24 Okt (128): definisi dari server memuat kode akun mentah ("saldo 1-1200") —
// layar memakai kalimat sendiri tanpa kode akun.
const AR_DEFS_UI = {
  ar_ledger: "Nilai surat jalan yang sudah dijurnal dikurangi pembayaran — dicocokkan dengan saldo akun piutang di bawah tabel.",
  exposure: "Nilai pesanan yang belum dikirim/diakui; belum masuk buku besar piutang.",
};

function LedgerExposureStrip({ totals }) {
  const d = AR_DEFS_UI;
  return (
    <div className="section-card mb-3" data-testid="ar-ledger-exposure">
      <div className="section-body py-2.5 grid gap-2 sm:grid-cols-2 text-[11.5px]">
        <div title={d.ar_ledger}>
          <span className="font-bold text-[#0058CC]">Piutang tercatat (buku besar): </span>
          <span className="tabular-nums font-bold" data-testid="ar-ledger-total">{formatCurrency(totals.ar_ledger || 0)}</span>
          <p className="text-[11px] text-[#8E8E93]">{d.ar_ledger}</p>
        </div>
        <div title={d.exposure}>
          <span className="font-bold text-[#6B6B73]">Pesanan belum dikirim (eksposur): </span>
          <span className="tabular-nums font-bold" data-testid="ar-exposure-total">{formatCurrency(totals.exposure || 0)}</span>
          <p className="text-[11px] text-[#8E8E93]">{d.exposure}</p>
        </div>
      </div>
    </div>
  );
}

/** PK-41 — pencocokan piutang tercatat dengan saldo akun piutang (angka utuh, tidak dipatah). */
function ReconciliationLine({ rec }) {
  if (!rec) return null;
  const money = (v, testId) => (
    <b className="whitespace-nowrap tabular-nums text-kn-text" data-testid={testId}>{formatCurrency(v || 0)}</b>
  );
  const beda = rec.difference != null && Math.abs(Number(rec.difference)) >= 0.005;
  return (
    <div className="mt-2 rounded-md border border-kn-divider bg-kn-neutral-soft px-3 py-2 text-fs-12 text-kn-text-2"
      data-testid="ar-aging-reconciliation">
      <p className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
        <span>Piutang tercatat</span>{" "}{money(rec.ar_ledger_total, "ar-rec-ledger")}
        {rec.gl_balance != null && (
          <>
            {" "}<span aria-hidden="true">·</span>{" "}<span>Saldo akun piutang</span>{" "}{money(rec.gl_balance, "ar-rec-gl")}
            {" "}<span aria-hidden="true">·</span>{" "}<span>Selisih</span>{" "}
            <b className={`whitespace-nowrap tabular-nums ${beda ? "text-kn-danger-text" : "text-kn-success-text"}`}
              data-testid="ar-rec-diff">{formatCurrency(rec.difference || 0)}</b>
          </>
        )}
      </p>
      {rec.note && <p className="mt-0.5" data-testid="ar-rec-note">{rec.note}</p>}
    </div>
  );
}
