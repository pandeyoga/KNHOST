/**
 * R6.2 — FixedAssetsParts — komponen pendukung FixedAssetsView (dipisah agar file < 500 baris).
 * Berisi: AssetStatusPill, FaKpi, AddAssetDialog, ScheduleDialog, DisposeDialog, TransferAssetDialog.
 *
 * Fase 3 · P4 (L-03) — tiga pop-up `.modal-card` buatan sendiri (+ dialog Pindah PT dari FixedAssetsView) kini
 * memakai cangkang baku: form → `FormModal` (Esc/klik-latar aman, kepala & kaki tetap, layar penuh di HP),
 * jadwal penyusutan (rincian) → `DetailModal framed`. Isian & testid tidak berubah.
 */
import MoneyInput from "../../components/MoneyInput";
import KNDatePicker from "@/components/KNDatePicker";
import { useState } from "react";
import {
  X, Plus, RefreshCw, PackageMinus, CalendarClock, TrendingUp, TrendingDown, Building2,
  CheckCircle2, Hourglass, ArrowRightLeft, Clock,
} from "lucide-react";
import { formatCurrency, formatDate, todayWib } from "../../utils/formatters";
import { parseDecimal } from "../../utils/decimalInput";
import KNSelect from "../../components/KNSelect";
import FormModal from "../../components/FormModal";
import DetailModal from "../../components/DetailModal";
import JournalStatusBadge, {
  JournalStatusBar, hasJournalBadge, journalStatusLabel,
} from "../../components/JournalStatusBadge";   // PK-18
import CashAccountField, { cashAccountBlocked, cashAccountBlockReason } from "../../components/CashAccountField";   // PK-23
import { entityFullById } from "../../utils/entityLabel";
import { docStatusLabel } from "../../utils/docStatus";
import { kpiValueParts } from "./financeShared";

// PK-42 (UX-18) — satu pemformat tanggal WIB bersama ("23 Okt 2026"); dulu zona perangkat & tahun dua angka.
export const fmtDate = (s) => formatDate(s);

// PK-23 — status = ikon + teks + warna (KN_37 §8); label lewat `docStatusLabel` (peta lokal didahulukan). Label DUA
// KATA karena `.status-pill` memakai `text-transform: capitalize`.
const ASSET_STATUS_LABEL = {
  active: "Aktif", fully_depreciated: "Habis Susut", disposed: "Dilepas",
  // FASE E-7 (E7g) — aset yang sudah pindah ke badan usaha lain. Tanpa baris ini pil jatuh ke cadangan "Aktif"
  // (hijau) sehingga layar penjual mengaku masih memegang aset yang haknya sudah berpindah.
  transferred: "Pindah PT",
  transferring: "Sedang Dipindah", disposing: "Sedang Dilepas",   // PK-23 — klaim yang belum selesai
};
const STATUS_TONE = {
  active: ["pill-success", CheckCircle2], fully_depreciated: ["pill-warning", Hourglass],
  disposed: ["pill-muted", PackageMinus], transferred: ["pill-info", ArrowRightLeft],
  transferring: ["status-pending", Clock], disposing: ["status-pending", Clock],
};

export function AssetStatusPill({ asset }) {
  const st = STATUS_TONE[asset?.status] ? asset.status : "active";
  const [cls, Icon] = STATUS_TONE[st];
  return (
    <span className="inline-flex flex-col items-start gap-1">
      <span className={`status-pill ${cls} inline-flex items-center gap-1 whitespace-nowrap`}
        data-testid={`asset-status-${asset?.id}`}>
        <Icon size={12} aria-hidden="true" /> {docStatusLabel(st, ASSET_STATUS_LABEL)}
      </span>
      {/* PK-18 — jurnal perolehan yang gagal/diproses tampil di daftar; yang terbit cukup di rincian */}
      {["failed", "pending"].includes(asset?.gl_status) && (
        <JournalStatusBadge status={asset.gl_status} error={asset.gl_error} testId={`asset-journal-${asset?.id}`} />
      )}
    </span>
  );
}

/** PK-23 — alasan aksi Pindah PT / Lepas tidak tersedia (sama dengan penolakan server); "" = tersedia. */
export function assetActionBlock(a) {
  const tr = a?.transfer || {};
  if (a?.status === "transferred") return `Aset ini sudah dipindahkan ke ${tr.to_entity_name || "PT lain"}.`;
  if (a?.status === "transferring") {
    return `Pindah ke ${tr.intent?.plan?.to_entity_name || "PT lain"} sedang diproses; bila jurnalnya gagal, ulangi dari `
      + "Keuangan › Posting Gagal.";
  }
  if (a?.status === "disposing") return "Pelepasan aset ini sedang diproses.";
  if (["failed", "pending"].includes(a?.gl_status)) {
    return "Jurnal perolehan belum terbit — ulangi di Keuangan › Posting Gagal.";
  }
  return "";
}

export function FaKpi({ label, value, hint, icon: Icon, tone = "text-kn-text", testId }) {
  // PK-23 — angka tidak pernah dipotong: tanpa `truncate`; hanya awalan "Rp" yang boleh turun baris
  // (`kpiValueParts`, sama dengan KpiCard Keuangan). Di HP ikon disembunyikan supaya angka mendapat ruang.
  return (
    <div className="section-card section-pad" data-testid={testId}>
      <div className="flex items-start gap-3">
        <div className="hidden w-9 h-9 rounded-lg bg-kn-action-soft items-center justify-center shrink-0 sm:flex">
          <Icon size={17} className="text-kn-action" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <p className="text-fs-12 font-bold uppercase tracking-wide text-kn-text-2">{label}</p>
          <p className={`text-fs-16 font-bold tabular-nums ${tone}`} data-testid={`${testId}-value`}>
            {kpiValueParts(value)}
          </p>
          {hint && <p className="text-fs-12 text-kn-text-2">{hint}</p>}
        </div>
      </div>
    </div>
  );
}

/* ── Tambah Aset ─────────────────────────────────────────────────────────── */
// PK-23 (FY-03) — sumber dana WAJIB dipilih (tanpa bawaan). Pilihan yang akun lawannya belum ditetapkan di Pemetaan
// Akun tampil mati dengan alasannya (dari server: `meta.funding_sources`). Sumber kas/bank → isian Rekening.
const FUNDING_FALLBACK = [
  { value: "kas", label: "Dibayar dari kas/bank", available: true, reason: "" },
  { value: "hutang", label: "Dibeli secara hutang", available: true, reason: "" },
  { value: "saldo_awal", label: "Saldo awal (aset lama)", available: true, reason: "" },
];

export function AddAssetDialog({ meta, entities = [], selectedEntity, busy, error = "", onCancel, onSubmit }) {
  const cats = meta?.categories || ["Peralatan & Mesin"];
  const catAcc = meta?.category_account || {};
  const accounts = meta?.asset_accounts || [];
  const funding = Array.isArray(meta?.funding_sources) && meta.funding_sources.length
    ? meta.funding_sources : FUNDING_FALLBACK;
  // PK-23 (N1) — PT = PT yang sedang dipilih (tombol Tambah mati di "Semua PT"); server memeriksanya lagi.
  const entityId = selectedEntity && selectedEntity !== "all" ? selectedEntity : (entities[0]?.id || "");

  const [form, setForm] = useState({
    name: "", category: cats[0], acquisition_cost: "", acquisition_date: todayWib(),
    useful_life_months: 60, salvage_value: "", gl_account_asset: catAcc[cats[0]] || "", notes: "",
    funding_source: "", account_id: "",
  });
  const [accState, setAccState] = useState("");
  const [localErr, setLocalErr] = useState("");
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const onCategory = (c) => setForm((f) => ({ ...f, category: c, gl_account_asset: catAcc[c] || f.gl_account_asset }));

  const biaya = parseFloat(form.acquisition_cost || 0) || 0;
  const salvage = parseFloat(form.salvage_value || 0) || 0;
  const life = parseInt(form.useful_life_months || 0, 10) || 0;
  const monthly = life > 0 && biaya > salvage ? Math.round(((biaya - salvage) / life) * 100) / 100 : 0;
  const salvageBad = form.salvage_value !== "" && biaya > 0 && salvage >= biaya;
  const isKas = form.funding_source === "kas";

  function submit() {
    if (!form.name.trim()) { setLocalErr("Nama aset wajib diisi."); return; }
    if (biaya <= 0) { setLocalErr("Harga perolehan harus lebih besar dari 0."); return; }
    if (life <= 0) { setLocalErr("Masa manfaat (bulan) harus lebih besar dari 0."); return; }
    if (salvage < 0 || salvage >= biaya) { setLocalErr("Nilai residu harus ≥ 0 dan < harga perolehan."); return; }
    if (!form.funding_source) { setLocalErr("Pilih sumber dana perolehan aset."); return; }
    setLocalErr("");
    onSubmit({
      name: form.name.trim(), category: form.category, acquisition_cost: biaya,
      acquisition_date: form.acquisition_date, useful_life_months: life, salvage_value: salvage,
      entity_id: entityId, gl_account_asset: form.gl_account_asset, notes: form.notes.trim(),
      funding_source: form.funding_source, account_id: isKas ? form.account_id : "",
    });
  }

  // UAT 24 Okt (audit UI tahap 2) — G1-25: Simpan nonaktif sampai Nama & Harga Perolehan & masa manfaat terisi.
  // PK-23 — juga sampai sumber dana dipilih dan (kas/bank) rekeningnya bisa ditentukan; alasannya ditulis di bawah.
  const accBlocked = isKas && cashAccountBlocked(accState, form.account_id);
  const cannotSave = salvageBad || !form.name.trim() || biaya <= 0 || life <= 0 || !form.funding_source || accBlocked;
  const saveReason = !form.name.trim() || biaya <= 0 || life <= 0 ? "Isi nama, harga perolehan, dan masa manfaat."
    : salvageBad ? "Nilai residu harus lebih kecil dari harga perolehan."
      : !form.funding_source ? "Pilih sumber dana perolehan."
        : accBlocked ? cashAccountBlockReason(accState) : "";
  return (
    <FormModal open onClose={onCancel} title="Tambah Aset Tetap" icon={Plus} size="md"
      subtitle="Perolehan dijurnal otomatis: debit akun aset, kredit sesuai sumber dana."
      testId="add-asset-dialog" onSubmit={submit} busy={busy} error={error}
      submitDisabled={cannotSave} submitLabel="Simpan Aset"
      submitTestId="add-asset-submit-btn" cancelTestId="add-asset-cancel-btn">
        {localErr && <div className="notice-bar danger mb-2" data-testid="add-asset-error"><span>{localErr}</span></div>}

        <div className="grid gap-3">
          <p className="text-fs-12 text-kn-text-2" data-testid="asset-entity-line">
            PT pemilik aset: <b className="text-kn-text">{entityFullById(entities, entityId)}</b>
          </p>
          <label className="grid gap-1">
            <span className="field-label">Nama Aset *</span>
            <input data-testid="asset-name-input" className="field" value={form.name}
              placeholder="Mesin Tenun Otomatis TX-200" onChange={(e) => set("name", e.target.value)} />
          </label>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1">
              <span className="field-label">Kategori</span>
              <KNSelect data-testid="asset-category-select" className="field" value={form.category}
                onValueChange={onCategory} aria-label="Kategori aset"
                options={cats.map((c) => ({ value: c, label: c }))} />
            </label>
            <label className="grid gap-1">
              <span className="field-label">Akun Aset</span>
              <KNSelect data-testid="asset-account-select" className="field" value={form.gl_account_asset}
                onValueChange={(v) => set("gl_account_asset", v)} aria-label="Akun aset"
                placeholder="(akun kategori)"
                options={accounts.map((a) => ({ value: a.code, label: `${a.code} · ${a.name}` }))} />
            </label>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1">
              <span className="field-label">Harga Perolehan (Rp) *</span>
              <MoneyInput testId="asset-cost-input" className="field" value={form.acquisition_cost} placeholder="mis. 12.000.000"
                onChange={(v) => set("acquisition_cost", v)} />
            </label>
            <label className="grid gap-1">
              <span className="field-label">Tanggal Perolehan</span>
              <KNDatePicker data-testid="asset-date-input" value={form.acquisition_date}
                onChange={(v) => set("acquisition_date", v)} clearable={false} />
            </label>
          </div>

          <fieldset className="grid gap-1.5" data-testid="asset-funding">
            <legend className="field-label">Sumber Dana *</legend>
            {funding.map((f) => (
              <label key={f.value} data-testid={`asset-funding-row-${f.value}`}
                className={`flex items-start gap-2 rounded-md border border-kn-divider px-3 py-2 ${f.available
                  ? "cursor-pointer" : "cursor-not-allowed bg-kn-neutral-soft"}`}>
                <input type="radio" name="asset-funding" className="mt-0.5" value={f.value}
                  data-testid={`asset-funding-${f.value}`} checked={form.funding_source === f.value}
                  disabled={!f.available} onChange={() => set("funding_source", f.value)} />
                <span className="grid">
                  <span className={`text-fs-13 ${f.available ? "text-kn-text" : "text-kn-text-2"}`}>{f.label}</span>
                  {!f.available && (
                    <span className="text-fs-12 text-kn-text-2" data-testid={`asset-funding-reason-${f.value}`}>
                      {f.reason || "Akun lawannya belum ditetapkan di Pemetaan Akun."}
                    </span>
                  )}
                </span>
              </label>
            ))}
          </fieldset>
          {isKas && (
            <CashAccountField entityId={entityId} value={form.account_id} onChange={(v) => set("account_id", v)}
              onState={setAccState} testId="asset-cash-account" />
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1">
              <span className="field-label">Masa Manfaat (bulan) *</span>
              <input data-testid="asset-life-input" className="field tabular-nums" type="number" min={1}
                value={form.useful_life_months} onChange={(e) => set("useful_life_months", e.target.value)} />
            </label>
            <label className="grid gap-1">
              <span className="field-label">Nilai Residu (Rp)</span>
              <MoneyInput testId="asset-salvage-input" className="field" value={form.salvage_value} placeholder="opsional"
                invalid={salvageBad} hint={salvageBad ? "Residu harus lebih kecil dari harga perolehan" : undefined}
                onChange={(v) => set("salvage_value", v)} />
            </label>
          </div>

          <label className="grid gap-1">
            <span className="field-label">Catatan</span>
            <input data-testid="asset-notes-input" className="field" value={form.notes}
              placeholder="opsional" onChange={(e) => set("notes", e.target.value)} />
          </label>

          <div className="rounded-md border border-kn-divider bg-kn-neutral-soft px-3 py-2">
            <p className="text-fs-12 text-kn-text-2">
              Estimasi penyusutan bulanan:{" "}
              <b className="tabular-nums text-kn-text" data-testid="asset-monthly-preview">{formatCurrency(monthly)}</b>
              {life > 0 ? ` selama ${life} bulan; bulan terakhir mengambil seluruh sisanya` : ""}
            </p>
          </div>
          {cannotSave && saveReason && (
            <p className="text-fs-12 text-kn-text-2" data-testid="add-asset-save-reason">Simpan aktif sesudah: {saveReason}</p>
          )}
        </div>
    </FormModal>
  );
}

/* ── Jadwal Penyusutan ───────────────────────────────────────────────────── */
export function ScheduleDialog({ asset, loading, onClose }) {
  const schedule = asset?.schedule || [];
  const entries = asset?.depreciation_entries || [];
  const postedCount = schedule.filter((r) => r.posted).length;

  // Rincian (baca-saja) → DetailModal framed; tombol tutup di kepala tetap (testid lama), tabel bergulir di dalam.
  return (
    <DetailModal onClose={onClose} framed showClose={false} size="lg" label="Jadwal penyusutan aset"
      testId="schedule-dialog">
        <div className="flex items-start justify-between gap-2 mb-3">
          <div>
            <h3 className="modal-title flex items-center gap-1.5">
              <CalendarClock size={16} className="text-kn-action" aria-hidden="true" /> Jadwal Penyusutan · {asset?.number}
            </h3>
            <p className="modal-subtitle">
              {asset?.name} · perolehan {formatCurrency(asset?.acquisition_cost)} · residu {formatCurrency(asset?.salvage_value)} ·
              {" "}{asset?.useful_life_months} bulan · terposting {postedCount}/{schedule.length}
            </p>
          </div>
          <button data-testid="schedule-close-btn" className="icon-button" onClick={onClose} aria-label="Tutup"><X size={15} /></button>
        </div>
        {hasJournalBadge(asset?.gl_status) && (   /* PK-18 — jurnal perolehan, di bilahnya sendiri */
          <div className="mb-2"><JournalStatusBar doc={asset} testId="schedule-journal-status" /></div>
        )}

        {asset?.disposal && (
          <div className="notice-bar success mb-2" data-testid="schedule-disposal-info">
            <span>
              Dilepas {fmtDate(asset.disposal.date)} · nilai jual {formatCurrency(asset.disposal.proceeds)} ·
              nilai buku {formatCurrency(asset.disposal.book_value)} ·{" "}
              <b>{asset.disposal.result === "gain" ? "Laba" : asset.disposal.result === "loss" ? "Rugi" : "Impas"} {formatCurrency(Math.abs(asset.disposal.gain_loss || 0))}</b>
              {asset.disposal.je_number ? ` · JE ${asset.disposal.je_number}` : ""}
            </span>
          </div>
        )}

        {loading ? (
          <div className="grid gap-2" data-testid="schedule-loading">
            {[0, 1, 2, 3, 4].map((i) => <div key={i} className="h-8 bg-kn-neutral-soft rounded animate-pulse" />)}
          </div>
        ) : schedule.length === 0 ? (
          <div className="py-8 text-center text-fs-12 text-kn-text-2" data-testid="schedule-empty">
            Jadwal penyusutan belum tersedia untuk aset ini.
          </div>
        ) : (
          <div className="table-wrap max-h-[46vh] overflow-auto">
            <table className="data-table head-wrap" data-testid="schedule-table">
              <thead>
                <tr>
                  <th>Periode</th>
                  <th className="text-right">Penyusutan</th>
                  <th className="text-right">Akumulasi</th>
                  <th className="text-right">Nilai Buku</th>
                  <th>Status</th>
                  <th>Jurnal</th>
                </tr>
              </thead>
              <tbody>
                {schedule.map((r) => {
                  const je = entries.find((e) => e.period === r.period);
                  // PK-23 — entri yang jurnalnya gagal/diproses BUKAN "terjurnal" (register belum memakainya)
                  const [cls, Icon, teks] = r.posted ? ["pill-success", CheckCircle2, "Terjurnal"]
                    : ["failed", "pending"].includes(r.gl_status) ? ["status-pending", Clock, journalStatusLabel(r.gl_status)]
                      : ["pill-muted", CalendarClock, "Rencana"];
                  return (
                    <tr key={r.period} data-testid={`schedule-row-${r.period}`}>
                      <td className="font-semibold text-kn-text whitespace-nowrap">{r.period}</td>
                      <td className="text-right tabular-nums">{formatCurrency(r.amount)}</td>
                      <td className="text-right tabular-nums text-kn-warning-text">{formatCurrency(r.accumulated)}</td>
                      <td className="text-right tabular-nums font-semibold">{formatCurrency(r.book_value)}</td>
                      <td>
                        <span className={`status-pill ${cls} inline-flex items-center gap-1 whitespace-nowrap`}>
                          <Icon size={12} aria-hidden="true" /> {teks}
                        </span>
                      </td>
                      <td className="text-fs-12 text-kn-text-2 whitespace-nowrap">{je?.je_number || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
    </DetailModal>
  );
}

/* ── Disposal ────────────────────────────────────────────────────────────── */
export function DisposeDialog({ asset, busy, error = "", onCancel, onSubmit }) {
  const [proceeds, setProceeds] = useState("");
  const [date, setDate] = useState(todayWib());
  const [note, setNote] = useState("");

  const bookValue = Math.round((asset?.book_value || 0) * 100) / 100;
  const pv = parseDecimal(proceeds);
  const p = Number.isFinite(pv) ? pv : 0;
  const gainLoss = Math.round((p - bookValue) * 100) / 100;
  const isGain = gainLoss > 0.01;
  const isLoss = gainLoss < -0.01;

  // Tombol konfirmasi berwarna bahaya → kaki sendiri (`footer`), bukan tombol Simpan baku.
  const footer = (
    <div className="flex items-center justify-end gap-2">
      <button type="button" data-testid="dispose-cancel-btn" className="secondary-button" onClick={onCancel} disabled={busy}>Batal</button>
      <button type="button" data-testid="dispose-submit-btn" className="danger-button" disabled={busy}
        onClick={() => onSubmit({ proceeds: p, date, note: note.trim() })}>
        {busy ? <RefreshCw size={14} className="animate-spin" /> : <PackageMinus size={14} />} Konfirmasi Pelepasan
      </button>
    </div>
  );
  return (
    <FormModal open onClose={onCancel} title={`Lepas Aset · ${asset?.number || ""}`} icon={PackageMinus} size="md"
      subtitle={`${asset?.name || ""} · nilai buku saat ini ${formatCurrency(bookValue)}`}
      testId="dispose-dialog" busy={busy} error={error} footer={footer}>
        <div className="grid gap-3">
          <label className="grid gap-1">
            <span className="field-label">Nilai Jual (Rp)</span>
            <MoneyInput testId="dispose-proceeds-input" className="field tabular-nums" value={proceeds} placeholder="0"
              onChange={setProceeds} />
          </label>
          <label className="grid gap-1">
            <span className="field-label">Tanggal Pelepasan</span>
            <KNDatePicker data-testid="dispose-date-input" value={date} onChange={setDate} clearable={false} />
          </label>
          <label className="grid gap-1">
            <span className="field-label">Catatan</span>
            <input data-testid="dispose-note-input" className="field" value={note}
              placeholder="opsional" onChange={(e) => setNote(e.target.value)} />
          </label>

          <div className={`rounded-md border border-kn-divider px-3 py-2.5 ${isLoss ? "bg-kn-danger-soft" : isGain ? "bg-kn-success-soft" : "bg-kn-neutral-soft"}`}>
            <p className="text-fs-12 font-bold uppercase tracking-wide text-kn-text-2 mb-1">Pratinjau Laba/Rugi Pelepasan</p>
            <p className="text-fs-12 text-kn-neutral tabular-nums">
              {formatCurrency(p)} <span className="text-kn-text-2">(nilai jual)</span> − {formatCurrency(bookValue)} <span className="text-kn-text-2">(nilai buku)</span> =
            </p>
            <p className={`text-fs-16 font-bold tabular-nums ${isLoss ? "text-kn-danger-text" : isGain ? "text-kn-success-text" : "text-kn-text"}`}
              data-testid="dispose-preview-gainloss">
              {isGain && <TrendingUp size={15} className="inline mr-1" />}
              {isLoss && <TrendingDown size={15} className="inline mr-1" />}
              {formatCurrency(gainLoss)} · {isGain ? "Laba" : isLoss ? "Rugi" : "Impas"}
            </p>
            <p className="text-fs-12 text-kn-text-2 mt-1">
              Jurnal: Dr 1-2900 Akumulasi {formatCurrency(asset?.accumulated_depreciation)} + Dr Kas {formatCurrency(p)}
              {isLoss ? ` + Dr 6-9500 Rugi ${formatCurrency(Math.abs(gainLoss))}` : ""} / Cr {asset?.gl_account_asset} {formatCurrency(asset?.acquisition_cost)}
              {isGain ? ` + Cr 4-9100 Laba ${formatCurrency(gainLoss)}` : ""}
            </p>
          </div>
        </div>
    </FormModal>
  );
}

/* ── Pindah aset ke badan usaha lain (FASE E-7 · E7g; dulu `.modal-card` di FixedAssetsView) ──────────── */
export function TransferAssetDialog({ asset, entities = [], busy, error = "", onCancel, onSubmit }) {
  const [to, setTo] = useState("");
  const [price, setPrice] = useState("");
  const [reason, setReason] = useState("");
  const submit = () => onSubmit({ to_entity_id: to, transfer_price: price ? Number(price) : null, reason });
  return (
    <FormModal open onClose={onCancel} title="Pindah Aset ke PT Lain" icon={Building2} size="md"
      testId="asset-transfer-modal" onSubmit={submit} busy={busy} error={error}
      submitDisabled={!to || reason.trim().length < 5} submitLabel={busy ? "Memproses…" : "Pindahkan Aset"}
      submitTestId="asset-transfer-submit">
      <p className="text-fs-12 leading-relaxed text-kn-text-2">
        <b>{asset.number} · {asset.name}</b> — nilai buku sekarang{" "}
        <b>{formatCurrency(asset.book_value)}</b> (akumulasi penyusutan{" "}
        {formatCurrency(asset.accumulated_depreciation)}). Aset akan lahir kembali
        di PT penerima dengan <b>masa manfaat SISA</b>, akumulasi penyusutan di
        PT ini dihapus lewat jurnal, dan bila harga pindah di atas nilai buku,
        labanya <b>dieliminasi di konsolidasi</b> (menjual ke PT sendiri bukan laba grup).
      </p>
      <div className="grid gap-3 mt-3">
        <div>
          <label className="field-label">PT Penerima *</label>
          <KNSelect data-testid="asset-transfer-to" className="field" value={to}
            onValueChange={setTo} aria-label="PT tujuan pindah aset"
            placeholder="— Pilih PT —"
            options={(entities || [])
              .filter((en) => en.id !== asset.entity_id && (en.status || "active") === "active")
              .map((en) => ({ value: en.id, label: en.short_name || en.legal_name || en.id }))} />
        </div>
        <div>
          <label className="field-label">
            Harga Pindah <span className="font-normal normal-case text-kn-text-2">(kosong = nilai buku)</span>
          </label>
          <MoneyInput testId="asset-transfer-price" className="field" value={price} onChange={(v) => setPrice(v)} />
        </div>
        <div>
          <label className="field-label">Alasan Pindah *</label>
          <input data-testid="asset-transfer-reason" className="field" value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="mis. mesin dipakai produksi PT itu mulai bulan depan" />
        </div>
        {(!to || reason.trim().length < 5) && (
          <p className="text-fs-12 text-kn-text-2" data-testid="asset-transfer-submit-reason">
            Pindahkan Aset aktif sesudah PT penerima dipilih dan alasan diisi (minimal 5 huruf).
          </p>
        )}
        <p className="text-fs-12 text-kn-text-2">
          Jurnal di kedua PT diperiksa dulu; bila salah satu belum bisa diterbitkan (periode tertutup, akun nonaktif),
          tidak ada yang berubah.
        </p>
      </div>
    </FormModal>
  );
}
