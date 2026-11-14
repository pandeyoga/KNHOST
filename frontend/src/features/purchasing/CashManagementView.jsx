import { useEffect, useMemo, useState } from "react";
import MoneyInput from "@/components/MoneyInput";
import axios, { API } from "../../services/apiClient";
import { Wallet, Plus, ArrowDownCircle, ArrowUpCircle, Ban, X, Building2 } from "lucide-react";
import { formatCurrency, formatDate } from "../../utils/formatters";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import { usePagedList } from "../../hooks/usePagedList";
import PaginationBar from "../../components/PaginationBar";
import { SearchBox } from "../../components/ListControls";
import FormModal from "../../components/FormModal";
import { askReason } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";
import { can } from "../../config/roles";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyPost } from "../../utils/moneyRequest";
import EntityScopeBanner from "../../components/EntityScopeBanner";
import EntityGatedButton from "../../components/EntityGatedButton";   // PK-42 (UX-05)
import FocusNotice from "../../components/FocusNotice";
import { BudgetPreview } from "../../components/BudgetCheckNotice";   // PK-39 — pratinjau anggaran kas keluar
import useFocusDoc, { gulirKe } from "../../hooks/useFocusDoc";
import CashAccountField, { cashAccountBlocked, cashAccountBlockReason } from "../../components/CashAccountField";   // PK-20

/**
 * CashManagementView (Fase 3 — Pengelolaan Kas).
 * Kas kecil (per entitas) + kas besar (gabungan). Catat kas masuk/keluar + saldo.
 * Koleksi kanonik: cash_transactions (prefix cash_).
 *
 * PK-16 (UX-07, UX-14) — ringkasan saldo menyebut PT angkanya (`scope_meta` /cash-transactions/summary); gagal
 * memuat → data dikosongkan. Form "Catat Transaksi Kas": isian "Entitas" beserta pilihan bawaan berisi nama PT yang
 * ditulis mati DIHAPUS; `entity_id` tidak dikirim — server memakai PT di kepala aplikasi (D-14, PK-09). Banner
 * varian form menyebut buku PT penerima catatan.
 *
 * PK-42 (UX-12, UX-05, UX-18) — daftar berhalaman di server (`usePagedList`, 50 per halaman, cari nomor / keterangan /
 * kategori di server) dengan "Menampilkan a–b dari N transaksi"; dulu ≤ 500 baris dimuat lalu dipotong diam-diam.
 * Lencana tab dari `summary.counts` (jumlah di server, bukan baris yang termuat). Tombol Catat mati di mode Semua PT.
 * Tanggal lewat `formatDate` (WIB).
 */
const EMPTY_FORM = {
  cash_type: "kas_kecil", direction: "out", amount: "",
  category: "operasional", description: "", account_id: "",   // PK-20 — rekening wajib (tunggal → otomatis)
};
const CATEGORIES = [
  { value: "operasional", label: "Operasional" },
  { value: "pembelian", label: "Pembelian" },
  { value: "gaji", label: "Gaji / Upah" },
  { value: "transfer", label: "Transfer / Top-up" },
  { value: "modal", label: "Setoran Modal" },
  { value: "lain", label: "Lain-lain" },
];
const CATEGORY_LABEL = { ...Object.fromEntries(CATEGORIES.map((c) => [c.value, c.label])), penagihan: "Penagihan" };
const categoryLabel = (c) => {
  if (!c) return "—";
  const s = String(c);
  return CATEGORY_LABEL[s] || (s.charAt(0).toUpperCase() + s.slice(1)).replace(/_/g, " ");
};

// PK-42 — butir CSV di "Unduh ▾" = kolom yang terlihat di layar (INV-UI-07).
const CASH_CSV_COLUMNS = [
  { key: "number", header: "Nomor" },
  { key: "txn_date", header: "Tanggal", type: "date" },
  { key: "description", header: "Keterangan" },
  { header: "Kategori", get: (t) => categoryLabel(t.category) },
  { header: "Jenis kas", get: (t) => (t.cash_type === "kas_besar" ? "Kas Besar" : "Kas Kecil") },
  { header: "Arah", get: (t) => (t.direction === "in" ? "Masuk" : "Keluar") },
  { key: "amount", header: "Nominal", type: "num" },
];

const REF_LABEL = {
  ar_receipt: "kwitansi piutang", customer_advance: "uang muka pelanggan", sales_return: "retur penjualan",
  vendor_bill_payment: "pembayaran tagihan supplier", purchase_return: "retur pembelian", interco_settlement: "pelunasan antar-PT",
  cash_advance: "pengajuan dana", petty_cash_settlement: "LPJ kas kecil", refund: "pengembalian dana",
};

export default function CashManagementView({ currentUser, selectedEntity, focusDoc, onClearFocus }) {
  const [summary, setSummary] = useState({ kas_kecil: {}, kas_besar: {}, kas_kecil_per_entity: {} });
  const [entities, setEntities] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [filter, setFilter] = useState("all"); // all | kas_kecil | kas_besar
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  // PK-12 — satu niat = satu Idempotency-Key; tombol mati selama menunggu jawaban (klik ganda tidak mencatat dua kali).
  const [saving, setSaving] = useState(false);
  const [accState, setAccState] = useState("memuat");
  const [voidingId, setVoidingId] = useState("");
  const createIntent = useIntentKey("kas");
  const voidIntent = useIntentKey("kasv");

  // Sisir gerbang peran (2026-10-20): catat = cash.create, anulir = cash.delete.
  const canCreate = can(currentUser?.permissions, "cash", "create");
  const canVoid = can(currentUser?.permissions, "cash", "delete");

  // PK-42 — daftar berhalaman di server; saringan jenis kas & cari ikut kueri (kembali ke halaman 1 saat berubah).
  const scoped = !!selectedEntity && selectedEntity !== "all";
  const listParams = useMemo(() => ({
    ...(scoped ? { entity_id: selectedEntity } : {}),
    ...(filter !== "all" ? { cash_type: filter } : {}),
  }), [scoped, selectedEntity, filter]);
  const paged = usePagedList("/cash-transactions", { pageSize: 50, params: listParams, search });

  useEffect(() => { loadAll(); }, [selectedEntity]); // eslint-disable-line

  // Muat ulang ringkasan + daftar (sesudah catat / anulir / "Coba lagi"). Pemuatan pertama daftar dijalankan hook.
  async function reloadAll() {
    await Promise.all([loadAll(), paged.refresh()]);
  }

  async function loadAll() {
    try {
      const params = scoped ? { entity_id: selectedEntity } : {};
      const [sRes, eRes] = await Promise.all([
        axios.get(`${API}/cash-transactions/summary`, { params }),
        axios.get(`${API}/entities`).catch(() => ({ data: [] })),
      ]);
      setSummary(sRes.data || { kas_kecil: {}, kas_besar: {}, kas_kecil_per_entity: {} });
      setEntities(Array.isArray(eRes.data) ? eRes.data : []);
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat data kas."));
      // PK-16 (RP-04) — saldo dari permintaan sebelumnya tidak boleh tertinggal di layar.
      setSummary({ kas_kecil: {}, kas_besar: {}, kas_kecil_per_entity: {} });
    }
  }

  async function handleSubmit() {
    if (saving) return;
    if (!form.amount || Number(form.amount) <= 0) { setError("Nominal harus lebih dari 0."); return; }
    setSaving(true);
    try {
      const payload = { ...form, amount: Number(form.amount) };
      if (!payload.account_id) delete payload.account_id;
      const res = await createIntent.send(payload, (k) => moneyPost(`${API}/cash-transactions`, payload, k));
      // PK-39 — peringatan anggaran (mode Peringatkan) ikut di bilah pemberitahuan; mode Tolak → 400 di pop-up.
      const bWarn = (res.data.budget_check?.warnings || []).join(" ");
      setNotice(`Transaksi ${res.data.number} (${res.data.direction === "in" ? "masuk" : "keluar"}) dicatat.`
        + (bWarn ? ` Peringatan anggaran: ${bWarn}` : ""));
      setShowForm(false);
      setForm(EMPTY_FORM);
      await reloadAll();
    } catch (e) {
      setError(apiErrorText(e, "Gagal mencatat transaksi kas."));
    } finally {
      setSaving(false);
    }
  }

  // UAT 24 Okt (audit UI tahap 2) — G1-20: anulir meminta ALASAN (dikirim & dicatat server) dan menyebut dampaknya.
  // Kas turunan dokumen lain (kwitansi piutang, uang muka, retur, AP) ditolak server — tombolnya dinonaktifkan
  // dengan penjelasan, bukan dialog yang berakhir galat.
  // PK-20 — kas manual kini ber-`ref_type="manual"` (rujukan = kunci permintaan): tetap kas manual, boleh dianulir di sini.
  const derivedFrom = (t) => (t.ref_type === "manual" ? ""
    : (t.ref_type || t.ref_id ? (t.ref_number || REF_LABEL[t.ref_type] || "dokumen lain") : ""));

  async function handleVoid(t) {
    const dir = t.direction === "in" ? "masuk" : "keluar";
    const reason = await askReason({
      danger: true,
      title: `Anulir ${t.number}?`,
      message: `Kas ${dir} ${formatCurrency(t.amount)} (${t.cash_type === "kas_besar" ? "Kas Besar" : "Kas Kecil"}`
        + `${t.description ? ` · ${t.description}` : ""}) dibatalkan dan jurnal pembalik dibuat; saldo kas berubah. `
        + "Tindakan tidak dapat dibatalkan.",
      reasonLabel: "Alasan anulir",
      reasonPlaceholder: "Mis. salah input nominal — dicatat ulang sebagai KSC/CASH-…",
      confirmLabel: "Anulir Transaksi",
      testId: "cash-void-modal",
    });
    if (reason === null) return;
    setVoidingId(t.id);
    try {
      await voidIntent.send({ id: t.id, aksi: "void", reason },
        (k) => moneyPost(`${API}/cash-transactions/${t.id}/void`, { reason }, k));
      setNotice(`Transaksi ${t.number} dianulir.`);
      await reloadAll();
    } catch (e) {
      setError(apiErrorText(e, "Gagal menganulir transaksi."));
    } finally {
      setVoidingId("");
    }
  }

  const entityName = (id) => {
    if (id === "all") return "Gabungan";
    return entities.find((e) => e.id === id)?.short_name || entities.find((e) => e.id === id)?.legal_name || id || "—";
  };
  const showPerEntity = Object.keys(summary.kas_kecil_per_entity || {}).length > 1;
  // PK-42 — lencana tab = jumlah di server (`summary.counts`); belum ada → tanpa angka (bukan 0 yang menyesatkan).
  const cashCount = (k) => summary.counts?.[k];
  // PK-42 (UX-18) — satu pemformat tanggal WIB bersama ("23 Okt 2026").
  const fmtDate = (s) => formatDate(s);
  const txns = paged.items;
  // PK-44 (IA-04) — tautan dokumen: transaksi kas tidak punya panel rincian → dicari lewat kotak cari SERVER (nomornya;
  // halaman yang dimuat tidak harus memuatnya) lalu barisnya disorot. Tidak ada → "Dokumen … tidak ditemukan di PT ini."
  const [sorot, setSorot] = useState("");
  const fokus = useFocusDoc(focusDoc, "cash_transaction", async (id, fd) => {
    const params = { ...(scoped ? { entity_id: selectedEntity } : {}), q: fd.number || id, page: 1, page_size: 20 };
    const r = await axios.get(`${API}/cash-transactions`, { params });
    const list = Array.isArray(r.data) ? r.data : (r.data?.items || []);
    const t = list.find((x) => x.id === id);
    if (!t) return false;
    setFilter("all"); setSearch(t.number || fd.number || ""); setSorot(id);
    gulirKe(`cash-row-${id}`, 700);
    return true;
  }, onClearFocus);

  return (
    <div data-testid="cash-management-view">
      {notice && <div className="notice-bar success" data-testid="cash-notice"><span>{notice}</span><button onClick={() => setNotice("")}><X size={13} /></button></div>}
      <ErrorNotice message={error} onRetry={reloadAll} onDismiss={() => setError("")} testId="cash-error" />
      <FocusNotice {...fokus} testId="cash-focus-notice" />
      <EntityScopeBanner meta={summary.scope_meta} />

      {/* FASE E-7 (E7.4) — kas tingkat grup DIHAPUS (setiap uang wajib milik satu badan
          usaha). Sisa data lama tidak disembunyikan: ia ditegur di sini, dengan perintah
          migrasinya, supaya tidak ada saldo yatim yang diam-diam hilang dari laporan. */}
      {(summary.group_cash_pending?.transactions > 0 || summary.group_cash_pending?.accounts > 0) && (
        <div className="notice-bar warning mb-3" data-testid="cash-group-pending">
          <span>
            <b>Masih ada kas tingkat grup</b>: {summary.group_cash_pending.transactions} transaksi
            {summary.group_cash_pending.accounts > 0
              ? ` dan ${summary.group_cash_pending.accounts} rekening`
              : ""} belum punya pemilik badan usaha
            (nilai bersih {formatCurrency(summary.group_cash_pending.net_amount || 0)}).
            Selama belum dipetakan, laporan keuangan tiap badan usaha belum utuh.
            Minta admin menjalankan{" "}
            <code className="rounded bg-white/60 px-1">python scripts/migrate_e7_group_cash.py --report</code>{" "}
            lalu <code className="rounded bg-white/60 px-1">--apply</code>. Baris yang tidak
            bisa dibuktikan pemiliknya otomatis menjadi kasus di <b>Pusat Kasus Keuangan</b>.
          </span>
        </div>
      )}

      {/* K-02 (26 Okt) — label sumber: kartu di layar ini = catatan transaksi kas; angka utama "Kas & Bank" = buku besar. */}
      <p className="mb-1.5 text-[11px] text-[#6B6B73]" data-testid="cash-source-label">
        Saldo di kartu ini = saldo awal rekening + transaksi kas yang tercatat (masuk − keluar). Angka utama &ldquo;Kas &amp;
        Bank&rdquo; = saldo buku besar akun kas &amp; bank (Rekening &amp; Saldo, Dasbor Keuangan) — bisa berbeda karena jurnal
        kas manual di buku besar.
      </p>
      {/* Summary cards — Fase 3 · P4 (D-13 B): kartu "Kas Kecil per Entitas" hanya bila ADA lebih dari satu PT di
          datanya. Dengan satu PT (atau header memilih satu PT) isinya = kartu "Kas Kecil" → angka ganda, disembunyikan. */}
      <div className={`grid gap-3 sm:grid-cols-2 mb-3 ${showPerEntity ? "lg:grid-cols-3" : ""}`.trim()}>
        <SummaryCard testId="cash-besar-card" title="Kas Besar / Bank"
          sub={scoped ? entityName(selectedEntity) : "Semua PT"}
          balance={summary.kas_besar?.balance} inAmt={summary.kas_besar?.in} outAmt={summary.kas_besar?.out} tone="rgba(0,88,204,.10)" />
        <SummaryCard testId="cash-kecil-card" title="Kas Kecil" sub={scoped ? entityName(selectedEntity) : "Semua PT"} balance={summary.kas_kecil?.balance} inAmt={summary.kas_kecil?.in} outAmt={summary.kas_kecil?.out} tone="rgba(107,33,154,.10)" />
        {showPerEntity && <div data-testid="cash-per-entity-card" className="section-card">
          <div className="section-body">
            <p className="text-fs-12 font-bold uppercase text-kn-text-2 mb-1.5">Kas Kecil per PT</p>
            {Object.keys(summary.kas_kecil_per_entity || {}).length === 0 ? (
              <p className="text-[11.5px] text-[#9A9BA3]">Belum ada data.</p>
            ) : (
              <div className="space-y-1.5">
                {Object.entries(summary.kas_kecil_per_entity).map(([eid, v]) => (
                  <div key={eid} className="flex items-center justify-between text-[11.5px]">
                    <span className="flex items-center gap-1 text-[#3C3C43]"><Building2 size={11} />{entityName(eid)}</span>
                    <span className="font-bold tabular-nums">{formatCurrency(v.balance)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>}
      </div>

      {/* Header + filter */}
      <div className="section-card mb-3">
        <div className="section-head">
          <div className="flex items-center gap-2 min-w-0">
            <Wallet size={16} className="text-[#0058CC]" />
            <h2 data-testid="cash-title">Pengelolaan Kas</h2>
          </div>
          {canCreate && (
            <EntityGatedButton selectedEntity={selectedEntity} what="mencatat transaksi kas" data-testid="create-cash-button"
              onClick={() => { setShowForm(!showForm); setForm({ ...EMPTY_FORM }); }} className="primary-button">
              <Plus size={13} /> Catat Transaksi
            </EntityGatedButton>
          )}
        </div>
        <div className="section-body">
          <div className="tab-bar">
            {[{ k: "all", l: "Semua" }, { k: "kas_kecil", l: "Kas Kecil" }, { k: "kas_besar", l: "Kas Besar" }].map((t) => (
              <button key={t.k} data-testid={`cash-filter-${t.k}`} className={`tab-button ${filter === t.k ? "active" : ""}`} onClick={() => setFilter(t.k)}>
                {t.l}{cashCount(t.k) != null && <span className="tab-badge" data-testid={`cash-filter-count-${t.k}`}>{cashCount(t.k)}</span>}
              </button>
            ))}
            {filter === "kas_kecil" && <a href="?view=cash-advances" data-testid="cash-link-petty" className="ml-2 self-center text-fs-12 font-semibold text-kn-action hover:underline">Pengajuan & LPJ Kas Kecil →</a>}
          </div>
        </div>
      </div>

      {/* Create form */}
      {/* FASE P4 — pencatatan kas menjadi POP-UP (dulu menyelip di antara ringkasan
          saldo dan daftar transaksi). Logika form tidak diubah. */}
      <FormModal
        open={showForm && canCreate}
        onClose={() => setShowForm(false)}
        title="Catat Transaksi Kas"
        subtitle="Kas kecil (tunai) atau kas besar/bank — masuk & keluar"
        icon={Wallet}
        size="md"
        testId="cash-form"
        onSubmit={handleSubmit}
        submitLabel="Catat Transaksi"
        submitTestId="submit-cash-button"
        cancelTestId="cancel-cash-button"
        busy={saving}
        error={error}
        submitDisabled={cashAccountBlocked(accState, form.account_id)}
      >
        <div className="space-y-3">
            {/* PK-16 — menggantikan isian "Entitas": catatan masuk ke buku PT di kepala aplikasi. */}
            <EntityScopeBanner variant="form" testId="cash-form-scope" className="" />
            <div className="grid grid-cols-2 gap-3">
              <Field label="Jenis Kas">
                <KNSelect data-testid="cash-type-select" value={form.cash_type} onValueChange={(v) => setForm({ ...form, cash_type: v })} className="field"
                  options={[{ value: "kas_kecil", label: "Kas Kecil (tunai)" }, { value: "kas_besar", label: "Kas Besar / Bank (transfer)" }]} />
              </Field>
              <Field label="Arah">
                <KNSelect data-testid="cash-direction-select" value={form.direction} onValueChange={(v) => setForm({ ...form, direction: v })} className="field"
                  options={[{ value: "out", label: "Keluar (pengeluaran)" }, { value: "in", label: "Masuk (penerimaan)" }]} />
              </Field>
              <Field label="Nominal (Rp)" req>
                <MoneyInput testId="cash-amount-input" value={form.amount} onChange={(v) => setForm({ ...form, amount: v })} className="field" placeholder="0" />
              </Field>
              <Field label="Kategori">
                <KNSelect data-testid="cash-category-select" value={form.category} onValueChange={(v) => setForm({ ...form, category: v })} className="field" options={CATEGORIES} searchable={false} />
              </Field>
            </div>
            <CashAccountField entityId={selectedEntity} cashType={form.cash_type} value={form.account_id}
              onChange={(v) => setForm((f) => ({ ...f, account_id: v }))} onState={setAccState} testId="cash-account" />
            {cashAccountBlocked(accState, form.account_id) && accState !== "kosong" && (
              <p className="text-fs-12 text-kn-text-2" data-testid="cash-account-reason">{cashAccountBlockReason(accState)}</p>
            )}
            <Field label="Deskripsi">
              <input data-testid="cash-description-input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="field" placeholder="Keterangan transaksi..." />
            </Field>
            {form.direction === "out" && showForm && (
              <BudgetPreview entityId={selectedEntity} source="cash_out" category={form.category}
                amount={form.amount} date={form.txn_date || ""} testId="cash-budget-preview" />
            )}
        </div>
      </FormModal>

      {/* Transactions table — PK-42: tabel baku (`data-table`) di wadah gulir, kolom aksi lekat di kanan; cari di
          server; pager baku "Menampilkan a–b dari N transaksi" + Unduh. Memuat / galat / kosong dibedakan. */}
      <div className="section-card" data-testid="cash-list">
        <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2" data-testid="cash-txn-toolbar">
          <SearchBox value={search} onChange={(v) => { setSearch(v); if (!v) setSorot(""); }} placeholder="Cari nomor / keterangan / kategori…" testId="cash-txn-search" />
        </div>
        {paged.error ? (
          <div className="px-3 pb-3">
            <ErrorNotice message={paged.error} onRetry={paged.refresh} testId="cash-list-error" />
          </div>
        ) : paged.loading && txns.length === 0 ? (
          <div className="py-10 text-center text-fs-12 text-kn-text-2" data-testid="cash-list-loading">Memuat transaksi kas...</div>
        ) : txns.length === 0 ? (
          <div className="py-12 text-center text-fs-12 text-kn-text-2" data-testid="cash-list-empty">
            <Wallet className="mx-auto mb-2 text-kn-text-2" size={28} aria-hidden="true" />
            <p>{search.trim() ? `Tidak ada transaksi kas yang cocok dengan “${search.trim()}”.` : "Belum ada transaksi kas."}</p>
          </div>
        ) : (
          <div className="overflow-x-auto border-t border-kn-divider">
            <table className="data-table head-wrap" data-testid="cash-table">
              <thead>
                <tr>
                  <th>Nomor</th><th>Tanggal</th><th>Keterangan / Kategori</th><th>Jenis / PT</th>
                  <th className="text-right">Nominal</th><th className="col-sticky-end text-right">Aksi</th>
                </tr>
              </thead>
              <tbody>
                {txns.map((t) => (
                  <tr key={t.id} data-testid={`cash-row-${t.id}`} className={t.id === sorot ? "row-focus" : undefined}>
                    <td className="font-mono whitespace-nowrap font-bold text-kn-action">{t.number}</td>
                    <td className="whitespace-nowrap text-kn-text-2" data-testid={`cash-row-date-${t.id}`}>{fmtDate(t.txn_date)}</td>
                    <td className="min-w-[200px]">
                      <p className="font-semibold">{t.description || "—"}</p>
                      <p className="text-fs-12 text-kn-text-2">{categoryLabel(t.category)}</p>
                    </td>
                    <td className="whitespace-nowrap">
                      <p>{t.cash_type === "kas_besar" ? "Kas Besar" : "Kas Kecil"}</p>
                      <p className="text-fs-12 text-kn-text-2">{entityName(t.entity_id)}</p>
                    </td>
                    <td className="text-right whitespace-nowrap">
                      <span className={`inline-flex items-center justify-end gap-1 font-bold tabular-nums ${t.direction === "in" ? "text-kn-success-text" : "text-kn-danger-text"}`}>
                        {t.direction === "in"
                          ? <ArrowDownCircle size={13} aria-label="Masuk" />
                          : <ArrowUpCircle size={13} aria-label="Keluar" />}
                        {t.direction === "in" ? "+" : "−"}{formatCurrency(t.amount)}
                      </span>
                    </td>
                    <td className="col-sticky-end text-right">
                      {canVoid && t.status !== "void" && (derivedFrom(t) ? (
                        // Alasan tertulis (bukan tombol mati bertooltip): kas turunan dianulir lewat dokumen asalnya.
                        <span className="inline-block max-w-[180px] text-left text-fs-12 text-kn-text-2" data-testid={`void-cash-note-${t.id}`}>
                          Anulir lewat {derivedFrom(t)}
                        </span>
                      ) : (
                        <button type="button" data-testid={`void-cash-${t.id}`} onClick={() => handleVoid(t)}
                          disabled={voidingId === t.id} className="icon-button text-kn-danger-text"
                          title={`Anulir ${t.number}`} aria-label={`Anulir ${t.number}`}><Ban size={13} /></button>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!paged.error && paged.total > 0 && (
          <div className="px-3 pb-3">
            <PaginationBar page={paged.page} pageSize={paged.pageSize} total={paged.total} hasMore={paged.hasMore}
              loading={paged.loading} onPrev={paged.prev} onNext={paged.next} testId="cash-pager" label="transaksi"
              exportConfig={{ columns: CASH_CSV_COLUMNS, rows: txns, fetchAll: paged.fetchAll, filename: "transaksi-kas" }}
              exportSpec={{ dataset: "cash_transactions", label: "transaksi-kas", search,
                filters: [["cash_type", "eq", filter !== "all" ? filter : ""], ["status", "ne", "void"]],
                sort: [{ key: "txn_date", dir: "desc" }] }} />
          </div>
        )}
      </div>

    </div>
  );
}

function SummaryCard({ testId, title, sub, balance, inAmt, outAmt, tone }) {
  return (
    <div data-testid={testId} className="section-card">
      <div className="section-body">
        <div className="flex items-center justify-between mb-1">
          <p className="text-[11px] font-bold uppercase text-[#6B6B73]">{title}</p>
          <span className="text-[11px] text-[#9A9BA3]">{sub}</span>
        </div>
        <p className="text-[18px] sm:text-[20px] font-bold tabular-nums break-words" style={{ color: "#0F1115" }}>{formatCurrency(balance)}</p>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px]">
          <span className="text-green-700 tabular-nums">Masuk {formatCurrency(inAmt)}</span>
          <span className="text-red-600 tabular-nums">Keluar {formatCurrency(outAmt)}</span>
        </div>
        <div className="mt-2 h-1 rounded-full" style={{ background: tone }} />
      </div>
    </div>
  );
}

function Field({ label, req, children }) {
  return (
    <div>
      <label className="field-label">
        {label} {req && <span className="req">*</span>}
      </label>
      {children}
    </div>
  );
}
