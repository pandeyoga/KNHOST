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
} from "lucide-react";
import { formatCurrency, todayWib } from "../../utils/formatters";
import KNSelect from "../../components/KNSelect";
import FormModal from "../../components/FormModal";
import DetailModal from "../../components/DetailModal";

export const fmtDate = (s) => {
  if (!s) return "—";
  try {
    const d = new Date(String(s).length <= 10 ? `${s}T00:00:00` : s);
    return d.toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "2-digit" });
  } catch { return s; }
};

const STATUS_MAP = {
  active: ["pill-success", "Aktif"],
  fully_depreciated: ["pill-warning", "Habis Susut"],
  disposed: ["pill-muted", "Dilepas"],
  // FASE E-7 (E7g) — aset yang sudah pindah ke badan usaha lain. Tanpa baris ini pil
  // jatuh ke cadangan "Aktif" (hijau) sehingga layar penjual mengaku masih memegang
  // aset yang haknya sudah berpindah. Label dibuat DUA KATA karena `.status-pill`
  // memakai `text-transform: capitalize` — kalimat panjang jadi "Pindah Ke PT Lain".
  transferred: ["pill-info", "Pindah PT"],
};

export function AssetStatusPill({ asset }) {
  const [cls, label] = STATUS_MAP[asset?.status] || STATUS_MAP.active;
  return (
    <span className={`status-pill ${cls}`} data-testid={`asset-status-${asset?.id}`}>{label}</span>
  );
}

export function FaKpi({ label, value, hint, icon: Icon, tone = "", testId }) {
  return (
    <div className="section-card" data-testid={testId}>
      <div className="section-body flex items-center gap-3 py-3">
        <div className="w-9 h-9 rounded-lg bg-[#EAF1FF] flex items-center justify-center shrink-0">
          <Icon size={17} className="text-[#0058CC]" />
        </div>
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p>
          <p className={`text-[16px] font-bold tabular-nums truncate ${tone || "text-[#1C1C1E]"}`}
            data-testid={`${testId}-value`}>{value}</p>
          {hint && <p className="text-[10px] text-[#9A9BA3] truncate">{hint}</p>}
        </div>
      </div>
    </div>
  );
}

/* ── Tambah Aset ─────────────────────────────────────────────────────────── */
export function AddAssetDialog({ meta, entities = [], selectedEntity, busy, error = "", onCancel, onSubmit }) {
  const cats = meta?.categories || ["Peralatan & Mesin"];
  const catAcc = meta?.category_account || {};
  const accounts = meta?.asset_accounts || [];
  const defaultEntity = selectedEntity && selectedEntity !== "all"
    ? selectedEntity : (entities[0]?.id || "");

  const [form, setForm] = useState({
    name: "", category: cats[0], acquisition_cost: "", acquisition_date: todayWib(),
    useful_life_months: 60, salvage_value: "", entity_id: defaultEntity,
    gl_account_asset: catAcc[cats[0]] || "", notes: "",
  });
  const [localErr, setLocalErr] = useState("");
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const onCategory = (c) => setForm((f) => ({ ...f, category: c, gl_account_asset: catAcc[c] || f.gl_account_asset }));

  const biaya = parseFloat(form.acquisition_cost || 0) || 0;
  const salvage = parseFloat(form.salvage_value || 0) || 0;
  const life = parseInt(form.useful_life_months || 0, 10) || 0;
  const monthly = life > 0 && biaya > salvage ? Math.round(((biaya - salvage) / life) * 100) / 100 : 0;
  const salvageBad = form.salvage_value !== "" && biaya > 0 && salvage >= biaya;

  function submit() {
    if (!form.name.trim()) { setLocalErr("Nama aset wajib diisi."); return; }
    if (biaya <= 0) { setLocalErr("Harga perolehan harus lebih besar dari 0."); return; }
    if (life <= 0) { setLocalErr("Masa manfaat (bulan) harus lebih besar dari 0."); return; }
    if (salvage < 0 || salvage >= biaya) { setLocalErr("Nilai residu harus ≥ 0 dan < harga perolehan."); return; }
    setLocalErr("");
    onSubmit({
      name: form.name.trim(), category: form.category, acquisition_cost: biaya,
      acquisition_date: form.acquisition_date, useful_life_months: life, salvage_value: salvage,
      entity_id: form.entity_id, gl_account_asset: form.gl_account_asset, notes: form.notes.trim(),
    });
  }

  // UAT 24 Okt (audit UI tahap 2) — G1-25: Simpan nonaktif sampai Nama & Harga Perolehan & masa manfaat terisi.
  const cannotSave = salvageBad || !form.name.trim() || biaya <= 0 || life <= 0;
  return (
    <FormModal open onClose={onCancel} title="Tambah Aset Tetap" icon={Plus} size="md"
      subtitle="Perolehan otomatis diposting ke GL: Dr akun aset / Cr Kas-Bank."
      testId="add-asset-dialog" onSubmit={submit} busy={busy} error={error}
      submitDisabled={cannotSave} submitLabel="Simpan Aset"
      submitTestId="add-asset-submit-btn" cancelTestId="add-asset-cancel-btn">
        {localErr && <div className="notice-bar danger mb-2" data-testid="add-asset-error"><span>{localErr}</span></div>}

        <div className="grid gap-3">
          <label className="grid gap-1">
            <span className="text-[11px] font-semibold text-[#3C3C43]">Nama Aset *</span>
            <input data-testid="asset-name-input" className="field" value={form.name}
              placeholder="Mesin Tenun Otomatis TX-200" onChange={(e) => set("name", e.target.value)} />
          </label>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1">
              <span className="text-[11px] font-semibold text-[#3C3C43]">Kategori</span>
              <KNSelect data-testid="asset-category-select" className="field" value={form.category}
                onValueChange={onCategory} aria-label="Kategori aset"
                options={cats.map((c) => ({ value: c, label: c }))} />
            </label>
            <label className="grid gap-1">
              <span className="text-[11px] font-semibold text-[#3C3C43]">Akun GL Aset</span>
              <KNSelect data-testid="asset-account-select" className="field" value={form.gl_account_asset}
                onValueChange={(v) => set("gl_account_asset", v)} aria-label="Akun GL aset"
                placeholder="(default kategori)"
                options={accounts.map((a) => ({ value: a.code, label: `${a.code} · ${a.name}` }))} />
            </label>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1">
              <span className="text-[11px] font-semibold text-[#3C3C43]">Harga Perolehan (Rp) *</span>
              <MoneyInput testId="asset-cost-input" className="field" value={form.acquisition_cost} placeholder="mis. 12.000.000"
                onChange={(v) => set("acquisition_cost", v)} />
            </label>
            <label className="grid gap-1">
              <span className="text-[11px] font-semibold text-[#3C3C43]">Tanggal Perolehan</span>
              <KNDatePicker data-testid="asset-date-input" value={form.acquisition_date}
                onChange={(v) => set("acquisition_date", v)} clearable={false} />
            </label>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1">
              <span className="text-[11px] font-semibold text-[#3C3C43]">Masa Manfaat (bulan) *</span>
              <input data-testid="asset-life-input" className="field tabular-nums" type="number" min={1}
                value={form.useful_life_months} onChange={(e) => set("useful_life_months", e.target.value)} />
            </label>
            <label className="grid gap-1">
              <span className="text-[11px] font-semibold text-[#3C3C43]">Nilai Residu (Rp)</span>
              <MoneyInput testId="asset-salvage-input" className="field" value={form.salvage_value} placeholder="opsional"
                invalid={salvageBad} hint={salvageBad ? "Residu harus lebih kecil dari harga perolehan" : undefined}
                onChange={(v) => set("salvage_value", v)} />
            </label>
          </div>

          {entities.length > 1 && (
            <label className="grid gap-1">
              <span className="text-[11px] font-semibold text-[#3C3C43]">Entitas (PT)</span>
              <KNSelect data-testid="asset-entity-select" className="field" value={form.entity_id}
                onValueChange={(v) => set("entity_id", v)} aria-label="Badan usaha pemilik aset"
                options={entities.map((en) => ({
                  value: en.id, label: en.short_name || en.legal_name,
                }))} />
            </label>
          )}

          <label className="grid gap-1">
            <span className="text-[11px] font-semibold text-[#3C3C43]">Catatan</span>
            <input data-testid="asset-notes-input" className="field" value={form.notes}
              placeholder="opsional" onChange={(e) => set("notes", e.target.value)} />
          </label>

          <div className="rounded-md bg-[#F7F8FA] border border-[#EFF0F2] px-3 py-2">
            <p className="text-[11px] text-[#6B6B73]">
              Estimasi penyusutan bulanan:{" "}
              <b className="tabular-nums text-[#1C1C1E]" data-testid="asset-monthly-preview">{formatCurrency(monthly)}</b>
              {life > 0 ? ` selama ${life} bulan` : ""}
            </p>
          </div>
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
              <CalendarClock size={16} className="text-[#0058CC]" /> Jadwal Penyusutan · {asset?.number}
            </h3>
            <p className="modal-subtitle">
              {asset?.name} · perolehan {formatCurrency(asset?.acquisition_cost)} · residu {formatCurrency(asset?.salvage_value)} ·
              {" "}{asset?.useful_life_months} bulan · terposting {postedCount}/{schedule.length}
            </p>
          </div>
          <button data-testid="schedule-close-btn" className="icon-button" onClick={onClose} aria-label="Tutup"><X size={15} /></button>
        </div>

        {asset?.disposal && (
          <div className="notice-bar success mb-2" data-testid="schedule-disposal-info">
            <span>
              Dilepas {fmtDate(asset.disposal.date)} · proceeds {formatCurrency(asset.disposal.proceeds)} ·
              nilai buku {formatCurrency(asset.disposal.book_value)} ·{" "}
              <b>{asset.disposal.result === "gain" ? "Laba" : asset.disposal.result === "loss" ? "Rugi" : "Impas"} {formatCurrency(Math.abs(asset.disposal.gain_loss || 0))}</b>
              {asset.disposal.je_number ? ` · JE ${asset.disposal.je_number}` : ""}
            </span>
          </div>
        )}

        {loading ? (
          <div className="grid gap-2" data-testid="schedule-loading">
            {[0, 1, 2, 3, 4].map((i) => <div key={i} className="h-8 bg-[#F5F5F7] rounded animate-pulse" />)}
          </div>
        ) : schedule.length === 0 ? (
          <div className="py-8 text-center text-[12px] text-[#8E8E93]" data-testid="schedule-empty">
            Jadwal penyusutan belum tersedia untuk aset ini.
          </div>
        ) : (
          <div className="table-wrap max-h-[46vh] overflow-auto">
            <table className="data-table" data-testid="schedule-table">
              <thead className="sticky top-0">
                <tr className="text-left text-[10px] font-bold uppercase text-[#8E8E93] bg-[#FAFBFC] border-b border-[#EFF0F2]">
                  <th className="px-3 py-2">Periode</th>
                  <th className="px-3 py-2 text-right">Penyusutan</th>
                  <th className="px-3 py-2 text-right">Akumulasi</th>
                  <th className="px-3 py-2 text-right">Nilai Buku</th>
                  <th className="px-3 py-2 text-center">Status</th>
                  <th className="px-3 py-2">Jurnal</th>
                </tr>
              </thead>
              <tbody>
                {schedule.map((r) => {
                  const je = entries.find((e) => e.period === r.period);
                  return (
                    <tr key={r.period} data-testid={`schedule-row-${r.period}`}
                      className={`border-b border-[#F5F5F7] last:border-0 ${r.posted ? "bg-[#F6FBF7]" : ""}`}>
                      <td className="px-3 py-2 font-semibold text-[#1C1C1E]">{r.period}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(r.amount)}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-[#B45309]">{formatCurrency(r.accumulated)}</td>
                      <td className="px-3 py-2 text-right tabular-nums font-semibold">{formatCurrency(r.book_value)}</td>
                      <td className="px-3 py-2 text-center">
                        <span className={`status-pill ${r.posted ? "pill-success" : "pill-muted"}`}>
                          {r.posted ? "Terposting" : "Rencana"}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-[11px] text-[#6B6B73]">{je?.je_number || "—"}</td>
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
  const p = parseFloat(proceeds || 0) || 0;
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
            <span className="text-[11px] font-semibold text-[#3C3C43]">Nilai Jual / Proceeds (Rp)</span>
            <input data-testid="dispose-proceeds-input" className="field tabular-nums" type="number" min={0}
              value={proceeds} placeholder="0" onChange={(e) => setProceeds(e.target.value)} />
          </label>
          <label className="grid gap-1">
            <span className="text-[11px] font-semibold text-[#3C3C43]">Tanggal Pelepasan</span>
            <KNDatePicker data-testid="dispose-date-input" value={date} onChange={setDate} clearable={false} />
          </label>
          <label className="grid gap-1">
            <span className="text-[11px] font-semibold text-[#3C3C43]">Catatan</span>
            <input data-testid="dispose-note-input" className="field" value={note}
              placeholder="opsional" onChange={(e) => setNote(e.target.value)} />
          </label>

          <div className={`rounded-md border px-3 py-2.5 ${isLoss ? "bg-[#FCEBEA] border-[#F0B5AE]" : isGain ? "bg-[#E6F6EC] border-[#B9E4C7]" : "bg-[#F7F8FA] border-[#EFF0F2]"}`}>
            <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93] mb-1">Pratinjau Laba/Rugi Pelepasan</p>
            <p className="text-[12px] text-[#3C3C43] tabular-nums">
              {formatCurrency(p)} <span className="text-[#8E8E93]">(proceeds)</span> − {formatCurrency(bookValue)} <span className="text-[#8E8E93]">(nilai buku)</span> =
            </p>
            <p className={`text-[18px] font-bold tabular-nums ${isLoss ? "text-[#C0392B]" : isGain ? "text-[#1B7F4B]" : "text-[#1C1C1E]"}`}
              data-testid="dispose-preview-gainloss">
              {isGain && <TrendingUp size={15} className="inline mr-1" />}
              {isLoss && <TrendingDown size={15} className="inline mr-1" />}
              {formatCurrency(gainLoss)} · {isGain ? "Laba" : isLoss ? "Rugi" : "Impas"}
            </p>
            <p className="text-[10.5px] text-[#6B6B73] mt-1">
              JE: Dr 1-2900 Akumulasi {formatCurrency(asset?.accumulated_depreciation)} + Dr Kas {formatCurrency(p)}
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
    <FormModal open onClose={onCancel} title="Pindah Aset ke Badan Usaha Lain" icon={Building2} size="md"
      testId="asset-transfer-modal" onSubmit={submit} busy={busy} error={error}
      submitDisabled={!to || reason.trim().length < 5} submitLabel={busy ? "Memproses…" : "Pindahkan Aset"}
      submitTestId="asset-transfer-submit">
      <p className="text-[12px] leading-relaxed text-[#6B6B73]">
        <b>{asset.number} · {asset.name}</b> — nilai buku sekarang{" "}
        <b>{formatCurrency(asset.book_value)}</b> (akumulasi penyusutan{" "}
        {formatCurrency(asset.accumulated_depreciation)}). Aset akan lahir kembali
        di badan usaha penerima dengan <b>masa manfaat SISA</b>, akumulasi penyusutan di
        badan usaha ini dihapus lewat jurnal, dan bila harga pindah di atas nilai buku,
        labanya <b>dieliminasi di konsolidasi</b> (menjual ke PT sendiri bukan laba grup).
      </p>
      <div className="grid gap-3 mt-3">
        <div>
          <label className="mb-1 block text-[11px] font-semibold text-[#4A4B53]">Badan Usaha Penerima *</label>
          <KNSelect data-testid="asset-transfer-to" className="field" value={to}
            onValueChange={setTo} aria-label="Badan usaha tujuan pindah aset"
            placeholder="— Pilih badan usaha —"
            options={(entities || [])
              .filter((en) => en.id !== asset.entity_id && (en.status || "active") === "active")
              .map((en) => ({ value: en.id, label: en.short_name || en.legal_name || en.id }))} />
        </div>
        <div>
          <label className="mb-1 block text-[11px] font-semibold text-[#4A4B53]">
            Harga Pindah <span className="font-normal text-[#9A9BA3]">(kosong = nilai buku)</span>
          </label>
          <MoneyInput testId="asset-transfer-price" className="field" value={price} onChange={(v) => setPrice(v)} />
        </div>
        <div>
          <label className="mb-1 block text-[11px] font-semibold text-[#4A4B53]">Alasan Pindah *</label>
          <input data-testid="asset-transfer-reason" className="field" value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="mis. mesin dipakai produksi badan usaha itu mulai bulan depan" />
        </div>
      </div>
    </FormModal>
  );
}
