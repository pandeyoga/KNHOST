/**
 * BudgetParts (R6.3) — komponen pendukung BudgetView (dipisah agar file < 500 baris).
 * Berisi: DIM_TABS, BudgetFormModal, BudgetTable, BudgetRulesPanel, AlertsStrip, UnbudgetedPanel.
 *
 * PK-39 (FY-10/11/12, K-12) — tabel baku (`data-table head-wrap`, kolom aksi lekat kanan): kolom **PT** pada mode
 * gabungan, petunjuk "Komitmen", dokumen penyumbang komitmen & realisasi di bawah kunci, status ikon + teks + warna,
 * tombol **Riwayat**. Panel Kebijakan: mode hanya-baca dari Pusat Pengaturan (`budget.mode`) + tautan "Ubah di
 * Pusat Pengaturan" bagi pemegang `budget.configure`; sakelar lain (ambang, belum ada pagu, titik PO) tetap di sini.
 */
import MoneyInput from "../../components/MoneyInput";
import { useState } from "react";
import {
  Save, Trash2, AlertTriangle, ShieldAlert, ShieldCheck, ShieldOff, ClipboardList, Pencil, History, CheckCircle2,
  Settings2, XOctagon,
} from "lucide-react";
import KNSelect from "../../components/KNSelect";
import FormModal from "../../components/FormModal";
import { openConfig } from "../settings/config/configDeepLink";
import { sourceLabel } from "./glSourceLabels";
import { FC, Panel, Progress, fmtPct, formatCurrency } from "./financeShared";

export const DIM_TABS = [
  { value: "account", label: "Per Akun COA" },
  { value: "category", label: "Per Kategori Beban" },
];

export const MONTH_OPTS = [
  { value: "0", label: "Tahunan" }, { value: "1", label: "Januari" }, { value: "2", label: "Februari" },
  { value: "3", label: "Maret" }, { value: "4", label: "April" }, { value: "5", label: "Mei" },
  { value: "6", label: "Juni" }, { value: "7", label: "Juli" }, { value: "8", label: "Agustus" },
  { value: "9", label: "September" }, { value: "10", label: "Oktober" }, { value: "11", label: "November" },
  { value: "12", label: "Desember" },
];

// Status baris: ikon + teks + warna (bukan warna saja).
const STATUS_META = {
  ok: { cls: "status-done", Icon: CheckCircle2, label: "Aman" },
  warning: { cls: "status-pending", Icon: AlertTriangle, label: "Waspada" },
  over: { cls: "status-rejected", Icon: XOctagon, label: "Melampaui" },
};

// PK-39 — label mode dari server (`rules.mode_label`, pilihan registry `budget.mode`); ini hanya cadangan tampilan.
export const MODE_LABEL = { off: "Mati", warn: "Peringatkan", block: "Tolak bila melampaui" };
const UNBUDGETED_LABEL = { allow: "izinkan", warn: "peringatkan", block: "tolak" };
const MODE_META = {
  off: { icon: ShieldOff, cls: "bg-kn-neutral-soft text-kn-text-2", hint: "Anggaran hanya dipantau; transaksi tidak diperiksa." },
  warn: { icon: ShieldCheck, cls: "bg-kn-warning-soft text-kn-warning-text",
    hint: "Transaksi yang melampaui tetap jalan dengan peringatan dan jejak." },
  block: { icon: ShieldAlert, cls: "bg-kn-danger-soft text-kn-danger-text",
    hint: "Transaksi yang melampaui ditolak sampai pagu dinaikkan." },
};
export const COMMITMENT_HINT = "Sisa PO yang belum diterima + LPJ yang belum disetujui";

/* ── Form tambah anggaran ────────────────────────────────────────────────── */
// Fase 3 · P4 (L-03) — dulu form INLINE (`BudgetFormRow`) yang diselipkan di atas tabel; kini pop-up FormModal.
// Isian sama (akun/kategori, periode, nominal, catatan); galat simpan tampil di dalam pop-up.
export function BudgetFormModal({ open, dimension, keys, busy = false, error = "", onSubmit, onCancel }) {
  const [form, setForm] = useState({ key: "", month: "0", amount: "", note: "" });
  const opts = dimension === "account"
    ? (keys.accounts || []).map((a) => ({ value: a.code, label: `${a.code} · ${a.name}` }))
    : (keys.categories || []).map((c) => ({ value: c.code, label: `${c.label} (${c.account_code || "—"})` }));
  const close = () => { setForm({ key: "", month: "0", amount: "", note: "" }); onCancel(); };
  const submit = async () => {
    const ok = await onSubmit(form);
    if (ok) setForm({ key: "", month: "0", amount: "", note: "" });
  };
  return (
    <FormModal open={open} onClose={close} size="md" icon={Save} testId="budget-form"
      title={`Anggaran baru · ${DIM_TABS.find((t) => t.value === dimension)?.label || ""}`}
      onSubmit={submit} busy={busy} error={error} submitLabel="Simpan"
      submitDisabled={!form.key || !form.amount}
      submitTestId="budget-form-submit" cancelTestId="budget-form-cancel">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className="field-label">{dimension === "account" ? "Akun COA" : "Kategori Beban"}</label>
          <KNSelect data-testid="budget-form-key" className="field" value={form.key}
            onValueChange={(v) => setForm((f) => ({ ...f, key: v }))} options={opts}
            placeholder={dimension === "account" ? "Pilih akun…" : "Pilih kategori…"} />
        </div>
        <div>
          <label className="field-label">Periode</label>
          <KNSelect data-testid="budget-form-month" className="field" value={form.month}
            onValueChange={(v) => setForm((f) => ({ ...f, month: v }))} options={MONTH_OPTS} />
        </div>
        <div>
          <label className="field-label">Nominal (Rp)</label>
          <MoneyInput testId="budget-form-amount" className="field" value={form.amount} placeholder="0"
            onChange={(v) => setForm((f) => ({ ...f, amount: v }))} />
        </div>
        <div className="sm:col-span-2">
          <label className="field-label">Catatan</label>
          <input data-testid="budget-form-note" className="field" value={form.note}
            placeholder="Catatan (opsional)" onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))} />
        </div>
      </div>
    </FormModal>
  );
}

/* ── Dokumen penyumbang angka (penelusuran) ─────────────────────────────────── */
function DocLine({ label, docs, testId }) {
  if (!docs || docs.length === 0) return null;
  const teks = docs.map((d) => `${d.ref || sourceLabel(d.source_type)} ${formatCurrency(d.amount)}`).join(" · ");
  return (
    <span className="block text-fs-12 text-kn-text-2 truncate max-w-[320px]" title={teks} data-testid={testId}>
      {label}: {docs.slice(0, 3).map((d) => d.ref || sourceLabel(d.source_type)).join(", ")}
      {docs.length > 3 ? ` +${docs.length - 3}` : ""}
    </span>
  );
}

/* ── Tabel rincian ─────────────────────────────────────────────────────── */
export function BudgetTable({ rows, showEntity = false, onEdit, onDelete, onHistory }) {
  const rid = (r) => (showEntity ? `${r.entity_id}-${r.key}` : r.key);
  return (
    <>
      <div className="table-wrap">
        <table className="data-table head-wrap" data-testid="budget-table">
          <thead>
            <tr>
              {showEntity && <th data-testid="budget-col-entity">PT</th>}
              <th>Kunci Anggaran</th>
              <th className="text-right">Anggaran</th>
              <th className="text-right" title={COMMITMENT_HINT} data-testid="budget-col-committed">Komitmen</th>
              <th className="text-right">Realisasi</th>
              <th className="text-right">Sisa</th>
              <th className="w-[130px]">Terpakai (realisasi + komitmen)</th>
              <th>Status</th>
              <th className="text-right col-sticky-end">Aksi</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const st = STATUS_META[r.status] || STATUS_META.ok;
              return (
                <tr key={r.id} data-testid={`budget-row-${rid(r)}`}>
                  {showEntity && <td className="whitespace-nowrap" data-testid={`budget-entity-${rid(r)}`}>{r.entity_name || "—"}</td>}
                  <td>
                    <span className="text-fs-12 text-kn-text-2 mr-1.5">{r.key}</span>
                    <span className="font-semibold">{r.label}</span>
                    {r.month > 0 && <span className="ml-1.5 text-fs-12 text-kn-special-text">bln {r.month}</span>}
                    <DocLine label="terikat" docs={r.commitment_docs} testId={`budget-cdocs-${rid(r)}`} />
                    <DocLine label="realisasi" docs={r.actual_docs} testId={`budget-adocs-${rid(r)}`} />
                  </td>
                  <td className="text-right tabular-nums font-semibold">{formatCurrency(r.budget)}</td>
                  <td className="text-right tabular-nums" data-testid={`budget-committed-${rid(r)}`}>
                    {r.committed > 0 ? formatCurrency(r.committed) : "—"}
                  </td>
                  <td className="text-right tabular-nums" data-testid={`budget-actual-${rid(r)}`}>{formatCurrency(r.actual)}</td>
                  <td className={`text-right tabular-nums font-semibold ${r.remaining >= 0 ? "text-kn-success-text" : "text-kn-danger-text"}`}
                    data-testid={`budget-remaining-${rid(r)}`}>{formatCurrency(r.remaining)}</td>
                  <td>
                    <Progress pct={r.spent_pct}
                      color={r.status === "over" ? FC.expense : r.status === "warning" ? FC.amber : FC.revenue} />
                    <span className="text-fs-12 text-kn-text-2">
                      {fmtPct(r.spent_pct)} (realisasi {fmtPct(r.used_pct)})
                    </span>
                  </td>
                  <td>
                    <span className={`status-pill ${st.cls}`} data-testid={`budget-status-${rid(r)}`}>
                      <st.Icon size={12} /> {st.label}
                    </span>
                  </td>
                  <td className="text-right whitespace-nowrap col-sticky-end">
                    <button type="button" data-testid={`budget-history-${rid(r)}`} onClick={() => onHistory(r)}
                      className="icon-button" aria-label="Riwayat" title="Riwayat pagu"><History size={13} /></button>
                    <button type="button" data-testid={`budget-edit-${rid(r)}`} onClick={() => onEdit(r)}
                      className="icon-button" aria-label="Ubah" title="Ubah pagu"><Pencil size={13} /></button>
                    <button type="button" data-testid={`budget-delete-${rid(r)}`} onClick={() => onDelete(r)}
                      className="icon-button text-kn-danger-text" aria-label="Hapus" title="Hapus pagu"><Trash2 size={13} /></button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-1.5 text-fs-12 text-kn-text-2" data-testid="budget-committed-hint">
        <b>Komitmen</b> = {COMMITMENT_HINT.toLowerCase()}. <b>Realisasi</b> = jurnal tahun ini: beban dan pendapatan dari
        jurnalnya, akun persediaan = penerimaan barang dikurangi retur beli, kategori beban = LPJ pada bulan jurnalnya.
      </p>
    </>
  );
}

/* ── Panel kebijakan (rules) ───────────────────────────────────────────── */
export function BudgetRulesPanel({ rules, isAdmin, onSave, defaultAccount }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(null);
  const cur = rules || {};
  const meta = MODE_META[cur.mode] || MODE_META.warn;
  const Icon = meta.icon;
  const d = draft || {
    warn_threshold_pct: String(cur.warn_threshold_pct ?? 85),
    unbudgeted_action: cur.unbudgeted_action || "allow",
    enforce_po_create: cur.enforce_po_create !== false,
    enforce_po_approve: cur.enforce_po_approve !== false,
  };
  const set = (k, v) => setDraft({ ...d, [k]: v });

  return (
    <div className="section-card mb-3" data-testid="budget-rules-panel">
      {/* Bilah 1 — mode (hanya-baca, dari Pusat Pengaturan) */}
      <div className="px-4 py-2.5 flex flex-wrap items-center gap-2" data-testid="budget-rules-mode-bar">
        <span className={`status-pill ${meta.cls}`} data-testid="budget-rules-mode">
          <Icon size={13} /> Bila melampaui anggaran: {cur.mode_label || MODE_LABEL[cur.mode] || MODE_LABEL.warn}
        </span>
        <span className="text-fs-12 text-kn-text-2" data-testid="budget-rules-mode-source">
          diatur di {cur.mode_source || "Pusat Pengaturan"} · {meta.hint}
        </span>
        {isAdmin && (
          <button type="button" data-testid="budget-rules-open-config" className="link-button text-fs-12"
            onClick={() => openConfig({ key: "budget.mode" })}>
            <Settings2 size={12} /> Ubah di Pusat Pengaturan
          </button>
        )}
      </div>
      {/* Bilah 2 — sakelar lain yang masih diatur di layar ini */}
      <div className="px-4 py-2.5 flex flex-wrap items-center gap-2 border-t border-kn-divider" data-testid="budget-rules-other">
        <span className="text-fs-12 text-kn-text-2">
          Ambang waspada {cur.warn_threshold_pct ?? 85}% · belum ada pagu: {UNBUDGETED_LABEL[cur.unbudgeted_action || "allow"] || cur.unbudgeted_action}
          {" "}· PO diperiksa saat dibuat {cur.enforce_po_create === false ? "tidak" : "ya"}, saat disetujui {cur.enforce_po_approve === false ? "tidak" : "ya"}
          {cur.is_default ? " · (bawaan)" : ""}
        </span>
        {isAdmin && (
          <button type="button" data-testid="budget-rules-toggle" className="secondary-button btn-sm ml-auto"
            onClick={() => { setOpen((v) => !v); setDraft(null); }}>
            {open ? "Tutup" : "Atur Sakelar"}
          </button>
        )}
      </div>
      {open && isAdmin && (
        <div className="px-4 py-3 border-t border-kn-divider grid md:grid-cols-3 gap-3 items-end"
          data-testid="budget-rules-form">
          <div>
            <label className="field-label">Ambang waspada (%)</label>
            <input type="number" min="0" max="100" data-testid="budget-rules-threshold"
              className="field" value={d.warn_threshold_pct}
              onChange={(e) => set("warn_threshold_pct", e.target.value)} />
          </div>
          <div>
            <label className="field-label">Bila belum ada pagu</label>
            <KNSelect data-testid="budget-rules-unbudgeted" className="field"
              value={d.unbudgeted_action} onValueChange={(v) => set("unbudgeted_action", v)} options={[
                { value: "allow", label: "Izinkan" },
                { value: "warn", label: "Peringatkan" },
                { value: "block", label: "Tolak" },
              ]} />
          </div>
          <div>
            <button type="button" data-testid="budget-rules-save" className="primary-button btn-sm"
              onClick={async () => {
                const okSave = await onSave({
                  warn_threshold_pct: Number(d.warn_threshold_pct),
                  unbudgeted_action: d.unbudgeted_action,
                  enforce_po_create: d.enforce_po_create, enforce_po_approve: d.enforce_po_approve,
                });
                if (okSave) { setOpen(false); setDraft(null); }
              }}>
              <Save size={13} /> Simpan Sakelar
            </button>
          </div>
          <label className="flex items-center gap-2 text-fs-12">
            <input type="checkbox" data-testid="budget-rules-po-create" checked={d.enforce_po_create}
              onChange={(e) => set("enforce_po_create", e.target.checked)} />
            Periksa saat PO dibuat
          </label>
          <label className="flex items-center gap-2 text-fs-12">
            <input type="checkbox" data-testid="budget-rules-po-approve" checked={d.enforce_po_approve}
              onChange={(e) => set("enforce_po_approve", e.target.checked)} />
            Periksa saat PO disetujui
          </label>
          <p className="text-fs-12 text-kn-text-2">
            PO tanpa tanda anggaran dibebankan ke akun {defaultAccount || "persediaan"} (Persediaan).
          </p>
        </div>
      )}
    </div>
  );
}

/* ── Strip alert & komitmen tanpa anggaran ─────────────────────────────────── */
export function AlertsStrip({ alerts, showEntity = false }) {
  const over = (alerts || []).filter((a) => a.status === "over");
  const warn = (alerts || []).filter((a) => a.status === "warning");
  if (over.length === 0 && warn.length === 0) return null;
  return (
    <div className="notice-bar warning mb-3 items-start" data-testid="budget-alerts">
      <AlertTriangle size={13} className="mt-0.5 shrink-0" />
      <div className="grid gap-1 w-full">
        <b className="text-fs-12">{over.length} pos melampaui pagu · {warn.length} pos mendekati batas</b>
        <div className="grid md:grid-cols-2 gap-1">
          {[...over, ...warn].slice(0, 6).map((a) => (
            <div key={`${a.entity_id}-${a.dimension}-${a.key}-${a.month}`} data-testid={`budget-alert-${a.key}`}
              className="flex items-center justify-between gap-2 text-fs-12">
              <span className="truncate">
                <b className={a.status === "over" ? "text-kn-danger-text" : "text-kn-warning-text"}>{a.label}</b>
                <span className="text-kn-text-2"> ({a.key}{a.month > 0 ? ` · bln ${a.month}` : ""}{showEntity && a.entity_name ? ` · ${a.entity_name}` : ""})</span>
              </span>
              <span className="tabular-nums whitespace-nowrap">
                sisa <b className={a.remaining >= 0 ? "text-kn-success-text" : "text-kn-danger-text"}>{formatCurrency(a.remaining)}</b>
                {" · "}{fmtPct(a.spent_pct)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// UAT 24 Okt (audit UI tahap 2) — G1-19: kartu dulu "1-1300 · akun" tanpa nama akun.
export function UnbudgetedPanel({ items, dimension, keys = null, showEntity = false }) {
  const nameOf = (k) => (dimension === "account"
    ? (keys?.accounts || []).find((a) => a.code === k)?.name
    : (keys?.categories || []).find((c) => c.code === k)?.label) || "";
  if (!items || items.length === 0) return null;
  return (
    <Panel title="Komitmen Tanpa Anggaran (perlu ditetapkan pagu)" icon={ClipboardList}
      testId="budget-unbudgeted" className="mt-3">
      <div className="grid md:grid-cols-2 gap-2">
        {items.map((u) => (
          <div key={`${u.entity_id}-${u.dimension}-${u.key}`} data-testid={`budget-unbudgeted-${u.key}`}
            className="flex items-center justify-between gap-2 rounded-md border border-kn-divider px-2.5 py-2 text-fs-12">
            <span className="truncate">
              <b>{u.key}</b>
              <span> · {u.label || nameOf(u.key) || (dimension === "account" ? "akun" : "kategori")}</span>
              {showEntity && u.entity_name && <span className="text-kn-text-2"> · {u.entity_name}</span>}
              {(u.docs || []).length > 0 && (
                <span className="block text-kn-text-2 truncate">
                  {(u.docs || []).map((x) => x.ref).slice(0, 4).join(", ")}
                </span>
              )}
            </span>
            <span className="tabular-nums font-semibold text-kn-warning-text whitespace-nowrap">
              {formatCurrency(u.committed)}
            </span>
          </div>
        ))}
      </div>
    </Panel>
  );
}
