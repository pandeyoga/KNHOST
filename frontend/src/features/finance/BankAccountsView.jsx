/**
 * BankAccountsView (EPIC7-B) — Kas & Bank: multi-akun + ledger + rekonsiliasi.
 * Akses admin/manager (permission "cash"). Sumber: /api/bank-accounts (+ /ledger, /reconcile).
 */
import { apiErrorText } from "../../utils/apiError";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  RefreshCw, Plus, Landmark, Wallet, CheckCircle2, Circle, X, Banknote, ArrowDownLeft, ArrowUpRight, ListChecks,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import useListSearch from "@/hooks/useListSearch";
import { formatCurrency, formatDate } from "../../utils/formatters";
import DetailModal from "../../components/DetailModal";
import AuditHistoryPanel from "../../components/AuditHistoryPanel";
import { can } from "../../config/roles";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import MoneyInput from "@/components/MoneyInput";

const ACCOUNT_TYPE_OPTIONS = [
  { value: "bank", label: "Rekening bank" },
  { value: "cash", label: "Kas tunai" },
];

// UAT 24 Okt (audit UI tahap 2) — G1-15: tanggal tampilan satu format ("25 Okt 2026", WIB) via formatDate.
const fmtDate = (iso) => formatDate(iso);

const EMPTY_FORM = { name: "", account_type: "bank", bank_name: "", account_number: "", opening_balance: "" };

export default function BankAccountsView({ selectedEntity, currentUser }) {
  const canAudit = can(currentUser?.permissions, "audit", "view");
  const [detailTab, setDetailTab] = useState("ledger");
  const [accounts, setAccounts] = useState([]);
  const srch = useListSearch(accounts, null, { testId: "bank-accounts", pageSize: 24, placeholder: "Cari nama / bank / nomor rekening…" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);     // account id
  const [ledger, setLedger] = useState(null);
  const [ledgerLoading, setLedgerLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  // Keputusan pemilik K-02 (26 Okt) — angka utama "Kas & Bank" = saldo buku besar akun kas+bank; kartu rekening =
  // rincian. Posisi buku besar dimuat terpisah: bila gagal (mis. izin), kartu rekening tetap tampil.
  const [position, setPosition] = useState(null);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      const [res, pos] = await Promise.all([
        axios.get(`${API}/bank-accounts`, { params }),
        axios.get(`${API}/bank-accounts/position`, { params }).catch(() => ({ data: null })),
      ]);
      setAccounts(Array.isArray(res.data) ? res.data : []);
      setPosition(pos?.data && typeof pos.data.gl_total === "number" ? pos.data : null);
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat akun kas/bank."));
    } finally {
      setLoading(false);
    }
  }, [selectedEntity]);

  useEffect(() => { load(); }, [load]);

  const openLedger = useCallback(async (id, silent = false) => {
    setSelected(id);
    if (!silent) { setLedger(null); setLedgerLoading(true); setDetailTab("ledger"); }
    try {
      const res = await axios.get(`${API}/bank-accounts/${id}/ledger`);
      setLedger(res.data || null);
    } catch {
      if (!silent) setLedger(null);
    } finally {
      if (!silent) setLedgerLoading(false);
    }
  }, []);

  const toggleReconcile = async (txn) => {
    const next = !txn.reconciled;
    // optimistic update agar tombol langsung berubah
    setLedger((prev) => prev ? {
      ...prev,
      transactions: prev.transactions.map((t) => t.id === txn.id ? { ...t, reconciled: next } : t),
    } : prev);
    try {
      await axios.post(`${API}/cash-transactions/${txn.id}/reconcile`, { reconciled: next });
      await load();                       // sinkron saldo kartu
      await openLedger(selected, true);   // silent refresh (tanpa flash skeleton)
    } catch (err) {
      setError(apiErrorText(err, "Gagal memperbarui rekonsiliasi."));
      await openLedger(selected, true);   // revert dari server
    }
  };

  const [formErr, setFormErr] = useState("");
  const closeForm = () => { setShowForm(false); setForm(EMPTY_FORM); setFormErr(""); };
  const submitForm = async (e) => {
    e?.preventDefault?.();
    if (!form.name.trim()) { setFormErr("Nama akun wajib diisi."); return; }
    setSaving(true);
    try {
      await axios.post(`${API}/bank-accounts`, {
        ...form, opening_balance: Number(form.opening_balance || 0),
      });
      closeForm();
      await load();
    } catch (err) {
      setFormErr(apiErrorText(err, "Gagal membuat akun."));
    } finally {
      setSaving(false);
    }
  };

  const summary = useMemo(() => {
    const total = accounts.reduce((s, a) => s + (a.balance || 0), 0);
    const bank = accounts.filter((a) => a.account_type === "bank").reduce((s, a) => s + (a.balance || 0), 0);
    const cash = accounts.filter((a) => a.account_type === "cash").reduce((s, a) => s + (a.balance || 0), 0);
    const unrec = accounts.reduce((s, a) => s + (a.unreconciled_count || 0), 0);
    return { total, bank, cash, unrec, count: accounts.length };
  }, [accounts]);

  const gap = position ? Math.round((position.gl_total - summary.total) * 100) / 100 : 0;
  const unlinked = position?.unlinked || { count: 0, net: 0 };

  return (
    <div data-testid="bank-accounts-view">
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-1.5">
        {/* K-02 — angka utama: saldo buku besar akun kas & bank (= Dasbor Keuangan & Proyeksi Arus Kas). */}
        <Kpi testId="bank-kpi-gl" label="Kas & Bank (buku besar)" value={position ? formatCurrency(position.gl_total) : "—"}
          icon={Banknote} tone="text-[#0058CC]" sub="Angka utama · saldo buku besar akun kas & bank" />
        <Kpi testId="bank-kpi-total" label="Total Saldo Rekening" value={formatCurrency(summary.total)} icon={Landmark}
          sub="Rincian per rekening di bawah" />
        <Kpi testId="bank-kpi-bank" label="Saldo Bank" value={formatCurrency(summary.bank)} icon={Landmark} tone="text-[#0058CC]" sub="Rekening bank" />
        <Kpi testId="bank-kpi-cash" label="Saldo Kas" value={formatCurrency(summary.cash)} icon={Wallet} tone="text-[#1B7F4B]" sub="Kas tunai" />
        <Kpi testId="bank-kpi-unrec" label="Mutasi Belum Dicocokkan" value={summary.unrec} icon={ListChecks} tone={summary.unrec > 0 ? "text-[#B45309]" : ""} />
      </div>
      {position && Math.abs(gap) >= 1 && (
        <p className="mb-1.5 rounded-md border border-[#F0D9B8] bg-[#FDF6EC] px-3 py-2 text-[11.5px] text-[#8A4B08]" data-testid="bank-gap-label">
          Selisih buku besar vs total saldo rekening: <b className="tabular-nums">{formatCurrency(gap)}</b>.
          {unlinked.count > 0
            ? <> {unlinked.count} transaksi kas belum tertaut ke rekening mana pun (bersih <b className="tabular-nums">{formatCurrency(unlinked.net)}</b>) — tercatat di buku besar & Transaksi Kas, tidak di kartu rekening.</>
            : null}
          {" "}Sisa selisih (bila ada) berasal dari jurnal kas manual atau saldo awal buku besar yang tidak tercatat sebagai mutasi rekening.
        </p>
      )}
      {/* Audit UI 24 Okt (060↔061): angka di sini = saldo awal + mutasi yang TERTAUT ke
          rekening. Transaksi kas yang dicatat tanpa rekening hanya muncul di Transaksi Kas,
          jadi kedua layar bisa berbeda — dijelaskan terang-terangan, bukan disamarkan. */}
      <p className="mb-3 text-[11px] text-[#6B6B73]" data-testid="bank-balance-basis">
        Saldo per akun = saldo awal + mutasi yang tertaut ke akun tersebut. Transaksi kas yang
        dicatat tanpa memilih rekening hanya terhitung di tab Transaksi Kas.
      </p>

      <div className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2"><Landmark size={16} className="text-[#0058CC]" /><h2 data-testid="bank-title">Akun Kas & Bank</h2></div>
          <div className="flex items-center gap-2 ml-auto">
            <button data-testid="bank-add-toggle" className="primary-button" onClick={() => setShowForm(true)}>
              <Plus size={14} /> Tambah Akun
            </button>
            <button data-testid="bank-refresh" className="icon-button" onClick={load} aria-label="Muat ulang" title="Muat ulang"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
          </div>
        </div>
        <div className="section-body">
          <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="bank-error" />

          {/* Audit UI 24 Okt (060): form inline + segmented ungu → FormModal standar. */}
          <FormModal open={showForm} onClose={closeForm} title="Tambah Akun Kas / Bank"
            subtitle="Rekening bank atau kas tunai milik badan usaha aktif." icon={Landmark}
            testId="bank-add-form" onSubmit={submitForm} submitLabel="Simpan Akun"
            submitTestId="bank-form-submit" busy={saving} error={formErr}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="field-label">Nama Akun <span className="req">*</span></label>
                <input data-testid="bank-form-name" className="field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="mis. BCA Operasional" />
              </div>
              <div>
                <label className="field-label">Jenis <span className="req">*</span></label>
                <KNSelect data-testid="bank-form-type" value={form.account_type} options={ACCOUNT_TYPE_OPTIONS}
                  onValueChange={(v) => setForm({ ...form, account_type: v || "bank" })} />
              </div>
              {form.account_type === "bank" && (
                <>
                  <div>
                    <label className="field-label">Nama Bank</label>
                    <input data-testid="bank-form-bankname" className="field" value={form.bank_name} onChange={(e) => setForm({ ...form, bank_name: e.target.value })} placeholder="mis. BCA" />
                  </div>
                  <div>
                    <label className="field-label">No. Rekening</label>
                    <input data-testid="bank-form-accountno" className="field tabular-nums" value={form.account_number} onChange={(e) => setForm({ ...form, account_number: e.target.value })} placeholder="0123456789" />
                  </div>
                </>
              )}
              {/* G1-48 — urutan isian Jenis → Bank → No. Rek → Saldo awal (dulu saldo awal menyela detail bank). */}
              <div>
                <label className="field-label">Saldo Awal</label>
                <MoneyInput testId="bank-form-opening" value={form.opening_balance} onChange={(v) => setForm({ ...form, opening_balance: v })} placeholder="0" />
              </div>
            </div>
          </FormModal>

          {srch.toolbar}
          {loading ? (
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-3" data-testid="bank-loading">{[0, 1, 2].map((i) => <div key={i} className="h-28 bg-[#F5F5F7] rounded-lg animate-pulse" />)}</div>
          ) : srch.shown.length === 0 ? (
            <div data-testid="bank-empty" className="py-12 text-center text-[12px] text-[#8E8E93]">
              <Landmark size={26} className="mx-auto mb-2 text-gray-300" />Belum ada akun. Klik “Tambah Akun”.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="bank-cards">
              {srch.pageRows.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  data-testid={`bank-card-${a.id}`}
                  onClick={() => openLedger(a.id)}
                  className={`text-left rounded-xl border p-3.5 transition-all hover:shadow-md ${selected === a.id ? "border-[#0058CC] ring-1 ring-[#0058CC]/30 bg-[#F5F9FF]" : "border-[#EFF0F2] bg-white"} ${a.is_active === false ? "opacity-60" : ""}`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`w-7 h-7 rounded-lg flex items-center justify-center ${a.account_type === "bank" ? "bg-[#E7F0FF] text-[#0058CC]" : "bg-[#E6F6EC] text-[#1B7F4B]"}`}>
                      {a.account_type === "bank" ? <Landmark size={15} /> : <Wallet size={15} />}
                    </span>
                    <div className="min-w-0">
                      <p className="font-bold text-[13px] text-[#1C1C1E] truncate">{a.name}</p>
                      {/* G1-48 — bagian kosong tidak ditulis "-"; akun nonaktif diredupkan & berlabel. */}
                      <p className="text-[11px] text-[#9A9BA3] truncate">{a.account_type === "bank" ? [a.bank_name || "Bank", a.account_number].filter(Boolean).join(" · ") : "Kas tunai"}{a.is_active === false ? " · nonaktif" : ""}</p>
                      {a.cash_type && (a.account_type !== "bank" || a.cash_type === "kas_kecil") && (
                        <span data-testid={`bank-cash-type-${a.id}`} className="inline-block mt-0.5 text-[11px] font-semibold rounded-full px-1.5 py-0.5 bg-[#EFF4FF] text-[#0058CC]">
                          {a.cash_type === "kas_kecil" ? "Kas kecil" : "Kas besar"}
                        </span>
                      )}
                      {/* FASE E-7 (E7.4) — rekening tingkat grup sudah tidak sah lagi.
                          Ditandai TERANG-TERANGAN supaya dipetakan, bukan dipakai lagi. */}
                      {["all", "", null, undefined].includes(a.entity_id) && (
                        <span data-testid={`bank-group-flag-${a.id}`}
                          title="Rekening tingkat grup — setiap rekening wajib milik satu badan usaha (jalankan scripts/migrate_e7_group_cash.py)"
                          className="mt-0.5 inline-block rounded border border-[#F5D9A8] bg-[#FFF4E5] px-1.5 py-[1px] text-[9.5px] font-bold text-[#8A5300]">
                          KAS GRUP — perlu dipetakan
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="text-[20px] font-bold tabular-nums text-[#1C1C1E] mt-1">{formatCurrency(a.balance)}</p>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[#6B6B73] mt-1.5">
                    <span className="inline-flex items-center gap-1 text-[#1B7F4B]"><ArrowDownLeft size={12} />{formatCurrency(a.inflow)}</span>
                    <span className="inline-flex items-center gap-1 text-[#C0392B]"><ArrowUpRight size={12} />{formatCurrency(a.outflow)}</span>
                    <span className="ml-auto">{a.txn_count} transaksi{a.unreconciled_count > 0 ? ` · ${a.unreconciled_count} belum dicocokkan` : ""}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {selected && (
        <DetailModal onClose={() => { setSelected(null); setLedger(null); }}
          label="Mutasi rekening bank" testId="bank-ledger-modal">
          {/* UAT 24 Okt (audit UI tahap 2) — G1-04: tab Mutasi/Riwayat dulu melayang di atas latar buram (di luar
              kartu putih) dan tab Riwayat tidak punya tombol tutup. Sekarang kepala + tab + isi satu kartu. */}
          <LedgerPanel
            ledger={ledger}
            loading={ledgerLoading}
            onClose={() => { setSelected(null); setLedger(null); }}
            onToggle={toggleReconcile}
            tabs={canAudit ? (
              <div className="tab-bar px-3" data-testid="bank-detail-tabs">
                <button data-testid="bank-detail-tab-ledger" className={`tab-button ${detailTab === "ledger" ? "active" : ""}`} onClick={() => setDetailTab("ledger")}>Mutasi</button>
                <button data-testid="bank-detail-tab-history" className={`tab-button ${detailTab === "history" ? "active" : ""}`} onClick={() => setDetailTab("history")}>Riwayat Perubahan</button>
              </div>
            ) : null}
          >
            {detailTab === "history" && canAudit
              ? <AuditHistoryPanel entityType="bank_account" entityId={selected} testIdPrefix="bank-history" />
              : null}
          </LedgerPanel>
        </DetailModal>
      )}
    </div>
  );
}

function LedgerPanel({ ledger, loading, onClose, onToggle, tabs = null, children = null }) {
  return (
    <div className="section-card" data-testid="bank-ledger">
      <div className="section-head">
        <div className="flex items-center gap-2">
          <Banknote size={15} className="text-[#0058CC]" />
          <h2>{ledger?.name || "Buku Akun"}</h2>
          {ledger && <span className="text-[11px] text-[#6B6B73]">· Saldo <b className="tabular-nums">{formatCurrency(ledger.balance)}</b> · Terekonsiliasi <b className="tabular-nums">{formatCurrency(ledger.reconciled_balance)}</b></span>}
        </div>
        <button data-testid="bank-ledger-close" className="icon-button ml-auto" onClick={onClose} aria-label="Tutup"><X size={14} /></button>
      </div>
      {tabs}
      <div className="section-body">
        {children || (loading ? (
          <div className="grid gap-2" data-testid="bank-ledger-loading">{[0, 1, 2].map((i) => <div key={i} className="h-9 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
        ) : !ledger || (ledger.transactions || []).length === 0 ? (
          <div className="py-8 text-center text-[12px] text-[#8E8E93]" data-testid="bank-ledger-empty">Belum ada transaksi pada akun ini.</div>
        ) : (
          <div className="overflow-auto rounded-md border border-[#EFF0F2]">
            <table className="w-full min-w-[620px] text-[12px]">
              <thead>
                <tr className="whitespace-nowrap text-left text-[11px] font-bold uppercase text-[#8E8E93] bg-[#FAFBFC] border-b border-[#EFF0F2]">
                  <th className="px-3 py-2">Tanggal</th>
                  <th className="px-3 py-2">No / Deskripsi</th>
                  <th className="px-3 py-2 text-right">Masuk</th>
                  <th className="px-3 py-2 text-right">Keluar</th>
                  <th className="px-3 py-2 text-right">Saldo</th>
                  <th className="px-3 py-2 text-center">Rekonsiliasi</th>
                </tr>
              </thead>
              <tbody>
                {ledger.transactions.map((t) => (
                  <tr key={t.id} data-testid={`bank-ledger-row-${t.id}`} className="border-b border-[#F5F5F7] last:border-0">
                    <td className="px-3 py-2 text-[#3C3C43]">{fmtDate(t.txn_date)}</td>
                    <td className="px-3 py-2"><span className="font-mono text-[11px] text-[#9A9BA3]">{t.number}</span><br />{t.description}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-[#1B7F4B]">{t.direction === "in" ? formatCurrency(t.amount) : "—"}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-[#C0392B]">{t.direction === "out" ? formatCurrency(t.amount) : "—"}</td>
                    <td className="px-3 py-2 text-right tabular-nums font-semibold">{formatCurrency(t.running_balance)}</td>
                    <td className="px-3 py-2 text-center">
                      <button
                        data-testid={`bank-reconcile-${t.id}`}
                        onClick={() => onToggle(t)}
                        className={`inline-flex items-center gap-1 text-[10.5px] font-semibold rounded-full px-2 py-0.5 border ${t.reconciled ? "bg-[#E6F6EC] border-[#BDE5CC] text-[#1B7F4B]" : "bg-white border-[#E4E4EA] text-[#8E8E93] hover:border-[#C9DBF7]"}`}
                      >
                        {t.reconciled ? <CheckCircle2 size={12} /> : <Circle size={12} />}{t.reconciled ? "Terekonsiliasi" : "Tandai"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  );
}

function Kpi({ label, value, icon: Icon, tone = "", testId, sub = "" }) {
  // Audit UI 24 Okt (060 HP): nilai dulu `truncate` → "Rp 775.00…". Di HP ikon disembunyikan
  // dan angka boleh turun baris, tidak pernah dipotong. K-02 — `sub` = label sumber/cakupan angka.
  return (
    <div className="section-card" data-testid={testId}>
      <div className="section-body flex items-center gap-3 py-3">
        <div className="hidden w-9 h-9 flex-shrink-0 rounded-lg bg-[#EFF4FF] items-center justify-center sm:flex"><Icon size={17} className="text-[#0058CC]" /></div>
        <div className="min-w-0">
          <p className="text-[11px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p>
          <p className={`text-[15px] sm:text-[17px] font-bold tabular-nums break-words ${tone || "text-[#1C1C1E]"}`} data-testid={`${testId}-value`}>{value}</p>
          {sub && <p className="text-[10.5px] leading-tight text-[#8E8E93]" data-testid={`${testId}-sub`}>{sub}</p>}
        </div>
      </div>
    </div>
  );
}
