/**
 * IncentiveSetupView — KM-T1 · SDM › Kinerja & Insentif › Target & Aturan (view `incentive-setup`).
 *
 * Tiga bagian per PT: **Target** (per sales, per jenis periode — bulan, triwulan, tahun; tiap jenis angka tersendiri),
 * **Komponen insentif** (daftar per PT, pop-up baku), **Definisi angka** (empat pilihan Pusat Pengaturan, hanya baca,
 * berversi) beserta kartu **Pencocokan angka** (omzet vs buku besar, pencairan vs kas masuk; daftar penyebab selisih).
 *
 * Sumber: GET/PUT /api/incentive/targets · POST /api/incentive/targets/copy · GET/POST/PATCH /api/incentive/components ·
 * GET /api/incentive/definitions/current · GET /api/incentive/reconciliation?period · POST /api/incentive/facts/rebuild.
 * Lihat = `incentive.view`; ubah = `incentive.configure` (`can`, bukan nama peran). Mode "Semua PT" hanya baca: tombol
 * simpan mati dan alasannya tertulis di samping tombol (L4). Memuat · galat · kosong dibedakan per bagian.
 *
 * KM-T4 — kartu **Kesiapan beralih ke Lembar Insentif** (`GET /api/incentive/switch-readiness`, `incentive.configure`):
 * cara insentif yang berlaku di PT ini dan empat butir periksa (ikon + teks + warna). Tidak ada tombol alih di sini —
 * sakelarnya diubah di Pusat Pengaturan (tautan "Ubah di Pusat Pengaturan"; titik henti H5: pemilik yang menyalakan).
 *
 * KA-9 — bagian **Komisi otomatis (cara lama)** (KM-T5: akrual bulanan, bawaan komisi, tarif per kategori, jenjang
 * per sales) dicabut dari layar ini: semuanya kini di tab **Skema & Tarif** (`incentive-scheme`,
 * `IncentiveSchemeView`), termasuk alias `incentive-rates` / `incentive-schemes` dan deep link kunci `commission.*`.
 * Di sini tinggal kartu tautan ke tab itu.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, CircleSlash, Copy, Layers, Pencil, Plus, RefreshCw, Scale, Search, Settings2, Target } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import EntityScopeBanner from "../../components/EntityScopeBanner";
import ErrorNotice from "../../components/ErrorNotice";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import LinkCard from "../../components/LinkCard";
import { askConfirm } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatDate, formatPeriod, todayWib } from "../../utils/formatters";
import { entityFullById } from "../../utils/entityLabel";
import { canCurrent } from "../../config/roles";
import { useEntityScope } from "../../context/EntityScopeContext";
import { openConfig } from "../settings/config/configDeepLink";
import { MODE_KEDUANYA, MODE_LEMBAR } from "./incentiveModes";

export const TEKS_SEMUA_PT = "Pilih satu PT untuk mengatur target.";
export const TEKS_TANPA_IZIN = "Mengatur target dan komponen butuh akses Konfigurasi di modul Kinerja & Insentif.";
export const KETERANGAN_TARGET = "Target triwulan dan tahun adalah angka tersendiri, tidak dijumlah dari target bulanan.";
export const KOSONG_KOMPONEN = "Belum ada komponen. Tambahkan mis. Insentif Bulanan.";
export const TEKS_PENCOCOKAN_SEMUA_PT = "Pencocokan angka dihitung per PT. Pilih satu PT di pemilih PT (kanan atas).";
const JENIS = [{ value: "month", label: "Bulan" }, { value: "quarter", label: "Triwulan" }, { value: "year", label: "Tahun" }];
const ROMAWI = ["I", "II", "III", "IV"];
const BASIS = [{ value: "month", label: "Bulanan" }, { value: "quarter", label: "Triwulanan" },
  { value: "year", label: "Tahunan" }, { value: "free", label: "Bebas" }];
const KOLOM = [{ value: "omzet", label: "Omzet" }, { value: "pencairan", label: "Pencairan" }, { value: "harga", label: "Kualitas harga" }];

/** Alasan tombol ubah mati (ditulis di samping tombol — bukan tooltip). "" = boleh. */
export function alasanTidakBisaAtur({ canWrite, canConfigure }) {
  if (!canWrite) return TEKS_SEMUA_PT;
  if (!canConfigure) return TEKS_TANPA_IZIN;
  return "";
}

/** Label periode untuk manusia: "Oktober 2026" · "Triwulan IV 2026" · "Tahun buku 2026". */
export function labelPeriode(type, p) {
  if (!p) return "—";
  if (type === "quarter") { const q = Number(String(p).slice(-1)); return `Triwulan ${ROMAWI[q - 1] || q} ${String(p).slice(0, 4)}`; }
  if (type === "year") return `Tahun buku ${p}`;
  return formatPeriod(p);
}

/** Pilihan periode di sekitar periode berjalan `cur` (jenis `type`). */
export function pilihanPeriode(type, cur) {
  const y = Number(String(cur || todayWib()).slice(0, 4)) || new Date().getFullYear();
  const out = [];
  if (type === "quarter") {
    for (let yy = y - 1; yy <= y + 1; yy += 1) for (let q = 1; q <= 4; q += 1) out.push(`${yy}-Q${q}`);
  } else if (type === "year") {
    for (let yy = y - 2; yy <= y + 1; yy += 1) out.push(String(yy));
  } else {
    const m0 = Number(String(cur || todayWib()).slice(5, 7)) || 1;
    for (let k = -12; k <= 3; k += 1) {
      const idx = y * 12 + (m0 - 1) + k;
      out.push(`${Math.floor(idx / 12)}-${String((idx % 12) + 1).padStart(2, "0")}`);
    }
  }
  if (cur && !out.includes(cur)) out.push(cur);
  return out.sort().reverse().map((v) => ({ value: v, label: labelPeriode(type, v) }));
}

/** Angka isian dengan pemisah ribuan (L4); simpan sebagai string digit. */
const tampilAngka = (v) => (v === "" || v == null ? "" : Number(v).toLocaleString("id-ID"));
const digit = (s) => String(s || "").replace(/[^\d]/g, "");

/** Baris tabel target = daftar sales PT ∪ target yang sudah tersimpan. */
export function barisTarget(roster, items) {
  const by = {};
  (items || []).forEach((t) => { by[t.sales_id] = t; });
  const rows = (roster || []).map((s) => ({ sales_id: s.id, sales_name: s.name, ...(by[s.id] || {}) }));
  (items || []).filter((t) => !(roster || []).some((s) => s.id === t.sales_id))
    .forEach((t) => rows.push({ ...t }));
  return rows.map((r) => ({
    sales_id: r.sales_id, sales_name: r.sales_name || "—", entity_id: r.entity_id || "",
    target_sales_amount: r.target_sales_amount == null ? "" : String(Math.round(Number(r.target_sales_amount))),
    target_collection_amount: r.target_collection_amount == null ? "" : String(Math.round(Number(r.target_collection_amount))),
    target_new_customers: r.target_new_customers == null ? "" : String(r.target_new_customers),
    notes: r.notes || "", saved: !!r.id, dirty: false,
  }));
}

/** Bulan tanpa omzet, kwitansi, dan kas masuk — tampil satu kalimat, bukan deretan Rp 0. */
export function kosongBulan(rec) {
  const om = rec?.omzet || {};
  const pc = rec?.pencairan || {};
  return !om.pesanan && [om.fakta, om.buku, pc.dialokasikan, pc.belum_dialokasikan, pc.kwitansi, pc.kas]
    .every((v) => Math.abs(Number(v) || 0) < 0.5);
}

function StatusCocok({ ok, selisih, testId }) {
  const Icon = ok ? CheckCircle2 : AlertTriangle;
  return (
    <span data-testid={testId} className={`status-pill ${ok ? "status-done" : "status-rejected"}`}>
      <Icon size={12} aria-hidden="true" />{ok ? "Cocok" : `Selisih ${formatCurrency(Math.abs(Number(selisih) || 0))}`}
    </span>
  );
}

function Angka({ label, value, testId }) {
  return (
    <div><dt className="text-kn-text-2">{label}</dt>
      <dd className="text-fs-14 font-semibold tabular-nums" data-testid={testId}>{formatCurrency(value)}</dd></div>
  );
}

function DaftarPenyebab({ rows, total, render, testId }) {
  if (!rows || rows.length === 0) return null;
  return (
    <div className="mt-2" data-testid={testId}>
      <p className="text-fs-12 font-semibold text-kn-text">Penyebab selisih</p>
      <ul className="mt-1 space-y-1 text-fs-12 text-kn-text-2">
        {rows.slice(0, 10).map((r, i) => <li key={i} className="break-words">{render(r)}</li>)}
      </ul>
      {total > Math.min(rows.length, 10) && <p className="text-fs-12 text-kn-text-2 mt-1">dan {total - Math.min(rows.length, 10)} lainnya.</p>}
    </div>
  );
}

// ── Bagian 1 — Target ────────────────────────────────────────────────────────────────────────────────────────────
function BagianTarget({ canWrite, canConfigure, entity, entities, pt, onSakelar }) {
  const [jenis, setJenis] = useState("month");
  const [periode, setPeriode] = useState("");
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading");
  const [err, setErr] = useState("");
  const [rows, setRows] = useState([]);
  const [cari, setCari] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [saveErr, setSaveErr] = useState("");

  const load = useCallback(async () => {
    setState("loading");
    try {
      const r = await axios.get(`${API}/incentive/targets`, { params: { period_type: jenis, period: periode || undefined } });
      setData(r.data); setRows(barisTarget(r.data?.roster, r.data?.items)); setErr(""); setState("ready");
      if (!periode && r.data?.period) setPeriode(r.data.period);
      if (onSakelar) onSakelar(r.data);   // KA-9 — tautan ke tab Skema & Tarif tampil sesudah target termuat
    } catch (e) { setErr(apiErrorText(e) || ""); setState("error"); }
  }, [jenis, periode]);
  useEffect(() => { load(); }, [load, entity]);

  const alasan = alasanTidakBisaAtur({ canWrite, canConfigure });
  const ubah = (sid, patch) => setRows((rs) => rs.map((r) => (r.sales_id === sid ? { ...r, ...patch, dirty: true } : r)));
  const tampil = useMemo(() => {
    const q = cari.trim().toLowerCase();
    return q ? rows.filter((r) => r.sales_name.toLowerCase().includes(q)) : rows;
  }, [rows, cari]);
  const kotor = rows.filter((r) => r.dirty);

  const simpan = async () => {
    setBusy(true); setSaveErr(""); setMsg("");
    let ok = 0;
    const gagal = [];
    for (const r of kotor) {
      try {
        await axios.put(`${API}/incentive/targets`, {
          sales_id: r.sales_id, period_type: data.period_type, period: data.period,
          target_sales_amount: Number(r.target_sales_amount || 0), target_collection_amount: Number(r.target_collection_amount || 0),
          target_new_customers: Number(r.target_new_customers || 0), notes: r.notes || "" });
        ok += 1;
      } catch (e) { gagal.push(`${r.sales_name}: ${apiErrorText(e) || "gagal disimpan"}`); }
    }
    setBusy(false);
    if (ok) setMsg(`${ok} target ${labelPeriode(data.period_type, data.period)} tersimpan untuk ${pt}.`);
    if (gagal.length) setSaveErr(gagal.join(" · "));
    await load();
  };
  const salin = async () => {
    const dari = labelPeriode(data.period_type, data.previous_period);
    const ke = labelPeriode(data.period_type, data.period);
    const ok = await askConfirm({ title: `Salin target ${dari} ke ${ke}?`,
      message: `Target ${dari} di ${pt} disalin ke ${ke}. Sales yang sudah punya target ${ke} dilewati.`, confirmLabel: "Salin target" });
    if (!ok) return;
    setBusy(true); setSaveErr(""); setMsg("");
    try {
      const r = await axios.post(`${API}/incentive/targets/copy`, { period_type: data.period_type, from_period: data.previous_period, to_period: data.period });
      setMsg(`${r.data?.copied || 0} target disalin dari ${dari}; ${r.data?.skipped || 0} dilewati karena sudah ada.`);
      await load();
    } catch (e) { setSaveErr(apiErrorText(e) || "Target gagal disalin."); } finally { setBusy(false); }
  };

  return (
    <div className="section-card" data-testid="ins-target">
      <div className="section-head"><h2 className="flex items-center gap-2"><Target size={16} className="text-kn-action" aria-hidden="true" />Target</h2></div>
      <div className="section-body space-y-3">
        <p className="text-fs-12 text-kn-text-2" data-testid="ins-target-note">{KETERANGAN_TARGET}</p>
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-[160px]"><label className="field-label">Jenis periode</label>
            <KNSelect data-testid="ins-target-type" value={jenis} className="field" options={JENIS}
              onValueChange={(v) => { setJenis(v); setPeriode(""); }} /></div>
          <div className="w-[200px]"><label className="field-label">Periode</label>
            <KNSelect data-testid="ins-target-period" value={periode} className="field" options={pilihanPeriode(jenis, periode || (data?.period_type === jenis ? data?.period : ""))}
              onValueChange={setPeriode} /></div>
          {data?.bounds && <span className="text-fs-12 text-kn-text-2 pb-2" data-testid="ins-target-bounds">{formatDate(data.bounds.start)} – {formatDate(data.bounds.end)}</span>}
        </div>
        <div className="flex flex-wrap items-center gap-2" data-testid="ins-target-actions">
          <button type="button" data-testid="ins-target-save" className="primary-button btn-sm whitespace-nowrap"
            disabled={!!alasan || busy || kotor.length === 0 || state !== "ready"} onClick={simpan}>Simpan</button>
          <button type="button" data-testid="ins-target-copy" className="secondary-button btn-sm whitespace-nowrap"
            disabled={!!alasan || busy || state !== "ready"} onClick={salin}><Copy size={13} aria-hidden="true" /> Salin dari periode sebelumnya</button>
          {alasan && <span className="text-fs-12 text-kn-text-2" data-testid="ins-target-why">{alasan}</span>}
          {!alasan && state === "ready" && <span className="text-fs-12 text-kn-text-2" data-testid="ins-target-dirty">
            {kotor.length > 0 ? `${kotor.length} baris belum disimpan` : "Belum ada perubahan — ubah angka di tabel lalu Simpan."}</span>}
        </div>
        {msg && <div className="notice-bar success" data-testid="ins-target-msg"><span className="text-fs-12">{msg}</span></div>}
        {saveErr && <ErrorNotice testId="ins-target-save-error" message={saveErr} />}
      </div>
      {state === "loading" ? (
        <div className="section-pad text-fs-13 text-kn-text-2" role="status" data-testid="ins-target-loading">Memuat target…</div>
      ) : state === "error" ? (
        <div className="section-pad"><ErrorNotice testId="ins-target-error" message={`Target tidak bisa dimuat. ${err}`.trim()} onRetry={load} /></div>
      ) : rows.length === 0 ? (
        <div className="section-pad text-center text-fs-13 text-kn-text-2" data-testid="ins-target-empty">
          {data?.all_pt ? `Belum ada target ${labelPeriode(data.period_type, data.period)} di PT mana pun.` : `Belum ada sales di ${pt}.`}</div>
      ) : (
        <>
          <div className="px-3 pb-2">
            <label className="relative block w-full max-w-[280px]">
              <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-kn-text-2" aria-hidden="true" />
              <input data-testid="ins-target-search" className="field pl-7" placeholder="Cari sales" value={cari} onChange={(e) => setCari(e.target.value)} aria-label="Cari sales" />
            </label>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table head-wrap w-full" data-testid="ins-target-table">
              <thead><tr><th>Sales</th><th className="text-right">Target omzet</th><th className="text-right">Target pencairan</th>
                <th className="text-right">Target pelanggan baru</th><th>Catatan</th></tr></thead>
              <tbody>
                {tampil.map((r) => (
                  <tr key={`${r.entity_id}:${r.sales_id}`} data-testid={`ins-target-row-${r.sales_id}`}>
                    <td className="min-w-[150px] break-words">{r.sales_name}{data?.all_pt && r.entity_id ? <span className="block text-fs-12 text-kn-text-2">{entityFullById(entities, r.entity_id, "")}</span> : null}</td>
                    <td className="text-right"><input data-testid={`ins-target-sales-${r.sales_id}`} className="field w-36 text-right tabular-nums" inputMode="numeric"
                      disabled={!!alasan} value={tampilAngka(r.target_sales_amount)} onChange={(e) => ubah(r.sales_id, { target_sales_amount: digit(e.target.value) })} aria-label={`Target omzet ${r.sales_name}`} /></td>
                    <td className="text-right"><input data-testid={`ins-target-coll-${r.sales_id}`} className="field w-36 text-right tabular-nums" inputMode="numeric"
                      disabled={!!alasan} value={tampilAngka(r.target_collection_amount)} onChange={(e) => ubah(r.sales_id, { target_collection_amount: digit(e.target.value) })} aria-label={`Target pencairan ${r.sales_name}`} /></td>
                    <td className="text-right"><input data-testid={`ins-target-new-${r.sales_id}`} className="field w-20 text-right tabular-nums" inputMode="numeric"
                      disabled={!!alasan} value={r.target_new_customers} onChange={(e) => ubah(r.sales_id, { target_new_customers: digit(e.target.value) })} aria-label={`Target pelanggan baru ${r.sales_name}`} /></td>
                    <td className="min-w-[160px]"><input data-testid={`ins-target-notes-${r.sales_id}`} className="field w-full"
                      disabled={!!alasan} value={r.notes} onChange={(e) => ubah(r.sales_id, { notes: e.target.value })} aria-label={`Catatan ${r.sales_name}`} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-kn-divider px-3 py-2 text-fs-12 text-kn-text-2">
            <span data-testid="ins-target-count">{tampil.length} dari {rows.length} sales · {rows.filter((r) => r.saved).length} bertarget</span>
          </div>
        </>
      )}
    </div>
  );
}

// ── Bagian 2 — Komponen insentif ─────────────────────────────────────────────────────────────────────────────────────
const KOSONG_FORM = { code: "", name: "", basis_period_type: "month", columns: ["omzet", "pencairan"], taxable: true, is_active: true };

function BagianKomponen({ canWrite, canConfigure, entity, pt }) {
  const [items, setItems] = useState([]);
  const [state, setState] = useState("loading");
  const [err, setErr] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(KOSONG_FORM);
  const [editId, setEditId] = useState("");
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState("");
  const load = useCallback(async () => {
    setState("loading");
    try { const r = await axios.get(`${API}/incentive/components`); setItems(r.data?.items || []); setErr(""); setState("ready"); }
    catch (e) { setErr(apiErrorText(e) || ""); setState("error"); }
  }, []);
  useEffect(() => { load(); }, [load, entity]);
  const alasan = alasanTidakBisaAtur({ canWrite, canConfigure });
  const buka = (c) => {
    setEditId(c ? c.id : ""); setFormErr("");
    setForm(c ? { code: c.code, name: c.name, basis_period_type: c.basis_period_type, columns: c.columns || [], taxable: c.taxable !== false, is_active: c.is_active !== false } : KOSONG_FORM);
    setOpen(true);
  };
  const ubah = (patch) => setForm((f) => ({ ...f, ...patch }));
  const togKolom = (v) => ubah({ columns: form.columns.includes(v) ? form.columns.filter((x) => x !== v) : [...form.columns, v] });
  const simpan = async () => {
    if (!form.code.trim() || !form.name.trim()) { setFormErr("Isi kode dan nama komponen."); return; }
    if (!form.columns.length) { setFormErr("Pilih minimal satu angka yang ditampilkan."); return; }
    setBusy(true);
    try {
      if (editId) await axios.patch(`${API}/incentive/components/${editId}`, form);
      else await axios.post(`${API}/incentive/components`, form);
      setOpen(false); await load();
    } catch (e) { setFormErr(apiErrorText(e) || "Komponen gagal disimpan."); } finally { setBusy(false); }
  };
  return (
    <div className="section-card" data-testid="ins-comp">
      <div className="section-head"><h2 className="flex items-center gap-2"><Layers size={16} className="text-kn-action" aria-hidden="true" />Komponen insentif</h2></div>
      <div className="section-body space-y-2">
        <p className="text-fs-12 text-kn-text-2">Jenis insentif yang dipakai {pt}, mis. insentif bulanan atau triwulanan. Nominalnya diputuskan di lembar insentif, bukan di sini.</p>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" data-testid="ins-comp-add" className="primary-button btn-sm whitespace-nowrap" disabled={!!alasan} onClick={() => buka(null)}>
            <Plus size={13} aria-hidden="true" /> Tambah komponen</button>
          {alasan && <span className="text-fs-12 text-kn-text-2" data-testid="ins-comp-why">{alasan === TEKS_SEMUA_PT ? "Pilih satu PT untuk menambah komponen." : alasan}</span>}
        </div>
      </div>
      {state === "loading" ? (
        <div className="section-pad text-fs-13 text-kn-text-2" role="status" data-testid="ins-comp-loading">Memuat komponen…</div>
      ) : state === "error" ? (
        <div className="section-pad"><ErrorNotice testId="ins-comp-error" message={`Komponen tidak bisa dimuat. ${err}`.trim()} onRetry={load} /></div>
      ) : items.length === 0 ? (
        <div className="section-pad text-center text-fs-13 text-kn-text-2" data-testid="ins-comp-empty">{KOSONG_KOMPONEN}</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="data-table head-wrap w-full" data-testid="ins-comp-table">
            <thead><tr><th>Kode</th><th>Nama</th><th>Periode dasar</th><th>Angka yang ditampilkan</th><th>Aktif</th><th className="col-sticky-end"><span className="sr-only">Aksi</span></th></tr></thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id} data-testid={`ins-comp-row-${c.code}`}>
                  <td className="font-mono whitespace-nowrap">{c.code}</td>
                  <td className="min-w-[140px] break-words">{c.name}</td>
                  <td className="whitespace-nowrap">{c.basis_label || "—"}</td>
                  <td className="min-w-[140px]">{(c.columns_label || []).join(", ") || "—"}</td>
                  <td><span className={`status-pill ${c.is_active ? "status-done" : "status-draft"}`} data-testid={`ins-comp-active-${c.code}`}>
                    {c.is_active ? <CheckCircle2 size={12} aria-hidden="true" /> : <CircleSlash size={12} aria-hidden="true" />}{c.is_active ? "Aktif" : "Nonaktif"}</span></td>
                  <td className="col-sticky-end text-right">
                    <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid={`ins-comp-edit-${c.code}`} disabled={!!alasan} onClick={() => buka(c)}>
                      <Pencil size={12} aria-hidden="true" /> Ubah</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <FormModal open={open} onClose={() => setOpen(false)} title={editId ? "Ubah Komponen Insentif" : "Tambah Komponen Insentif"} subtitle={pt}
        icon={Layers} testId="ins-comp-form" onSubmit={simpan} submitLabel="Simpan Komponen" busy={busy} error={formErr}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div><label className="field-label">Kode <span className="req">*</span></label>
            <input data-testid="ins-comp-form-code" className="field font-mono" value={form.code} maxLength={24}
              onChange={(e) => ubah({ code: e.target.value.toUpperCase() })} placeholder="Contoh: IB" />
            <p className="text-fs-12 text-kn-text-2 mt-1">Huruf besar, angka, garis bawah, atau tanda hubung. Unik di {pt}.</p></div>
          <div><label className="field-label">Nama <span className="req">*</span></label>
            <input data-testid="ins-comp-form-name" className="field" value={form.name} onChange={(e) => ubah({ name: e.target.value })} placeholder="Contoh: Insentif Bulanan" /></div>
          <div><label className="field-label">Periode dasar <span className="req">*</span></label>
            <KNSelect data-testid="ins-comp-form-basis" value={form.basis_period_type} className="field" options={BASIS} onValueChange={(v) => ubah({ basis_period_type: v })} /></div>
          <div><span className="field-label">Angka yang ditampilkan <span className="req">*</span></span>
            <div className="flex flex-wrap gap-3 pt-1">
              {KOLOM.map((k) => (
                <label key={k.value} className="flex items-center gap-1 text-fs-13">
                  <input type="checkbox" data-testid={`ins-comp-form-col-${k.value}`} checked={form.columns.includes(k.value)} onChange={() => togKolom(k.value)} />{k.label}</label>))}
            </div></div>
          <label className="flex items-center gap-2 text-fs-13"><input type="checkbox" data-testid="ins-comp-form-taxable" checked={form.taxable} onChange={(e) => ubah({ taxable: e.target.checked })} />Kena pajak (masuk penghasilan bruto PPh 21)</label>
          <label className="flex items-center gap-2 text-fs-13"><input type="checkbox" data-testid="ins-comp-form-active" checked={form.is_active} onChange={(e) => ubah({ is_active: e.target.checked })} />Aktif</label>
        </div>
      </FormModal>
    </div>
  );
}

// ── Bagian 3 — Definisi angka & pencocokan ───────────────────────────────────────────────────────────────────────────
function BagianDefinisi({ canWrite, canConfigure, entity, pt }) {
  const [def, setDef] = useState(null);
  const [defState, setDefState] = useState("loading");
  const [defErr, setDefErr] = useState("");
  const [bulan, setBulan] = useState(String(todayWib()).slice(0, 7));
  const [rec, setRec] = useState(null);
  const [recState, setRecState] = useState("loading");
  const [recErr, setRecErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const loadDef = useCallback(async () => {
    setDefState("loading");
    try { const r = await axios.get(`${API}/incentive/definitions/current`); setDef(r.data); setDefErr(""); setDefState("ready"); }
    catch (e) { setDefErr(apiErrorText(e) || ""); setDefState("error"); }
  }, []);
  const loadRec = useCallback(async () => {
    setRecState("loading");
    try { const r = await axios.get(`${API}/incentive/reconciliation`, { params: { period: bulan } }); setRec(r.data); setRecErr(""); setRecState("ready"); }
    catch (e) { setRecErr(apiErrorText(e) || ""); setRecState("error"); }
  }, [bulan]);
  useEffect(() => { loadDef(); }, [loadDef, entity]);
  useEffect(() => { loadRec(); }, [loadRec, entity]);
  const alasan = alasanTidakBisaAtur({ canWrite, canConfigure });
  const bangunUlang = async () => {
    const ok = await askConfirm({ title: `Bangun ulang angka insentif sejak ${formatPeriod(bulan)}?`,
      message: `Fakta omzet dan pencairan ${pt} dihitung ulang dari pesanan, surat jalan, nota kredit, dan kwitansi sejak awal ${formatPeriod(bulan)}. Dokumen sumber tidak berubah.`,
      confirmLabel: "Bangun ulang" });
    if (!ok) return;
    setBusy(true); setMsg("");
    try {
      const r = await axios.post(`${API}/incentive/facts/rebuild`, { date_from: `${bulan}-01` });
      setMsg(`Dibangun ulang: ${r.data?.rows_shipment || 0} baris omzet, ${r.data?.rows_collection || 0} baris pencairan.`);
      await loadRec();
    } catch (e) { setRecErr(apiErrorText(e) || "Bangun ulang gagal."); setRecState("error"); } finally { setBusy(false); }
  };
  const om = rec?.omzet;
  const pc = rec?.pencairan;
  return (
    <>
      <div className="section-card" data-testid="ins-def">
        <div className="section-head"><h2 className="flex items-center gap-2"><Settings2 size={16} className="text-kn-action" aria-hidden="true" />Definisi angka</h2></div>
        {defState === "loading" ? (
          <div className="section-pad text-fs-13 text-kn-text-2" role="status" data-testid="ins-def-loading">Memuat definisi…</div>
        ) : defState === "error" ? (
          <div className="section-pad"><ErrorNotice testId="ins-def-error" message={`Definisi angka tidak bisa dimuat. ${defErr}`.trim()} onRetry={loadDef} /></div>
        ) : def?.all_pt ? (
          <div className="section-pad text-fs-13 text-kn-text-2" data-testid="ins-def-all">Definisi angka berlaku per PT. Pilih satu PT di pemilih PT (kanan atas).</div>
        ) : (
          <div className="section-body space-y-2">
            <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2" data-testid="ins-def-list">
              {(def?.items || []).map((i) => (
                <div key={i.field} className="rounded-md border border-kn-divider px-3 py-2">
                  <dt className="text-fs-12 text-kn-text-2">{i.label}</dt>
                  <dd className="text-fs-14 font-semibold text-kn-text" data-testid={`ins-def-${i.field}`}>{i.value_label}</dd>
                </div>))}
            </dl>
            <div className="flex flex-wrap items-center gap-3 text-fs-12 text-kn-text-2">
              <span data-testid="ins-def-version">Berlaku sejak {formatDate(def?.effective_from)} (versi {def?.version})</span>
              {canConfigure && (
                <button type="button" data-testid="ins-def-open-config" className="link-button text-fs-12" onClick={() => openConfig({ key: "insentif.dasar_omzet" })}>
                  <Settings2 size={12} aria-hidden="true" /> Ubah di Pusat Pengaturan</button>)}
            </div>
          </div>
        )}
      </div>

      <div className="section-card" data-testid="ins-rec">
        <div className="section-head"><h2 className="flex items-center gap-2"><Scale size={16} className="text-kn-action" aria-hidden="true" />Pencocokan angka</h2></div>
        <div className="section-body space-y-3">
          <p className="text-fs-12 text-kn-text-2">Omzet sales harus sama dengan pendapatan di buku besar, dan pencairan ditambah uang yang belum dialokasikan harus sama dengan kas masuk dari kwitansi.</p>
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-[200px]"><label className="field-label">Bulan</label>
              <KNSelect data-testid="ins-rec-month" value={bulan} className="field" options={pilihanPeriode("month", bulan)} onValueChange={setBulan} /></div>
            <button type="button" data-testid="ins-rec-refresh" className="secondary-button btn-sm whitespace-nowrap" onClick={loadRec}><RefreshCw size={13} aria-hidden="true" /> Muat ulang</button>
            <button type="button" data-testid="ins-rec-rebuild" className="secondary-button btn-sm whitespace-nowrap" disabled={!!alasan || busy} onClick={bangunUlang}>Bangun ulang angka</button>
            {alasan && <span className="text-fs-12 text-kn-text-2" data-testid="ins-rec-why">{alasan === TEKS_SEMUA_PT ? "Pilih satu PT untuk membangun ulang angka." : alasan}</span>}
          </div>
          {msg && <div className="notice-bar success" data-testid="ins-rec-msg"><span className="text-fs-12">{msg}</span></div>}
          {recState === "loading" ? (
            <div className="text-fs-13 text-kn-text-2" role="status" data-testid="ins-rec-loading">Mencocokkan angka…</div>
          ) : recState === "error" ? (
            <ErrorNotice testId="ins-rec-error" message={`Pencocokan tidak bisa dihitung. ${recErr}`.trim()} onRetry={loadRec} />
          ) : rec?.all_pt ? (
            <p className="text-fs-13 text-kn-text-2" data-testid="ins-rec-all">{TEKS_PENCOCOKAN_SEMUA_PT}</p>
          ) : kosongBulan(rec) ? (
            <p className="text-fs-13 text-kn-text-2" data-testid="ins-rec-empty">Belum ada omzet, kwitansi, atau kas masuk di {pt} pada {formatPeriod(bulan)}.</p>
          ) : (
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              <div className="rounded-md border border-kn-divider p-3" data-testid="ins-rec-omzet">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                  <h3 className="text-fs-14 font-bold text-kn-text">Omzet vs buku besar</h3>
                  <StatusCocok ok={om?.ok} selisih={om?.selisih} testId="ins-rec-omzet-status" />
                </div>
                <dl className="grid grid-cols-2 gap-2 text-fs-12">
                  <Angka label="Omzet terkirim (semua sales)" value={om?.fakta} testId="ins-rec-omzet-fakta" />
                  <Angka label="Pendapatan di buku besar" value={om?.buku} testId="ins-rec-omzet-buku" />
                </dl>
                <DaftarPenyebab rows={om?.penyebab} total={om?.jumlah_penyebab} testId="ins-rec-omzet-sebab"
                  render={(r) => <><span className="font-mono">{r.so_number || "Pesanan tanpa nomor"}</span> — {r.sebab} (selisih {formatCurrency(Math.abs(r.selisih))})</>} />
              </div>
              <div className="rounded-md border border-kn-divider p-3" data-testid="ins-rec-pencairan">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                  <h3 className="text-fs-14 font-bold text-kn-text">Pencairan vs kas masuk</h3>
                  <StatusCocok ok={pc?.ok} selisih={Math.abs(Number(pc?.selisih) || 0) >= 1 ? pc?.selisih : pc?.selisih_kas} testId="ins-rec-pencairan-status" />
                </div>
                <dl className="grid grid-cols-2 gap-2 text-fs-12">
                  <Angka label="Dialokasikan ke pesanan" value={pc?.dialokasikan} testId="ins-rec-pc-alokasi" />
                  <Angka label="Kas belum dialokasikan" value={pc?.belum_dialokasikan} testId="ins-rec-pc-belum" />
                  <Angka label="Kwitansi" value={pc?.kwitansi} testId="ins-rec-pc-kwitansi" />
                  <Angka label="Kas masuk" value={pc?.kas} testId="ins-rec-pc-kas" />
                </dl>
                <DaftarPenyebab rows={pc?.penyebab} total={pc?.jumlah_penyebab} testId="ins-rec-pencairan-sebab"
                  render={(r) => <><span className="font-mono">{r.receipt_number || "Tanpa kwitansi"}</span> — {r.sebab}</>} />
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

/** KM-T4 — butir kesiapan beralih: ikon + teks + warna (kelas `status-*` yang ada). */
/** KM-T4 / KA-9 — kalimat ringkas kartu Kesiapan menurut sakelar PT (konstanta mode `incentiveModes.js`). */
export function ringkasanKesiapan(mode, siap) {
  if (mode === MODE_LEMBAR) return "PT ini sudah memakai Lembar Insentif.";
  if (mode === MODE_KEDUANYA) return "PT ini sudah memakai Lembar Insentif bersama komisi otomatis (keduanya dibayar).";
  return siap ? "Semua butir siap. Pemilik bisa mengalihkan PT ini di Pusat Pengaturan."
    : "Selesaikan butir yang belum siap sebelum PT ini dialihkan.";
}

export function ButirKesiapan({ c }) {
  const Icon = c.ok ? CheckCircle2 : AlertTriangle;
  return (
    <li className="flex items-start gap-2" data-testid={`ins-ready-${c.code}`} data-ok={c.ok ? "1" : "0"}>
      <span className={`status-pill ${c.ok ? "status-done" : "status-pending"} inline-flex shrink-0 items-center gap-1 whitespace-nowrap`}>
        <Icon size={12} aria-hidden="true" />{c.ok ? "Siap" : "Belum"}</span>
      <span className="text-fs-13 text-kn-text">{c.text}</span>
    </li>
  );
}

function BagianKesiapan({ canWrite, canConfigure, entity }) {
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading");
  const [err, setErr] = useState("");
  const load = useCallback(async () => {
    if (!canWrite) { setState("all"); return; }
    setState("loading");
    try { const r = await axios.get(`${API}/incentive/switch-readiness`); setData(r.data); setErr(""); setState("ready"); }
    catch (e) { setErr(apiErrorText(e) || ""); setState("error"); }
  }, [canWrite]);
  useEffect(() => { if (canConfigure) load(); }, [load, entity, canConfigure]);
  if (!canConfigure) return null;
  const siap = (data?.checks || []).every((c) => c.ok);
  return (
    <div className="section-card" data-testid="ins-ready">
      <div className="section-head"><h2 className="flex items-center gap-2"><CheckCircle2 size={16} className="text-kn-action" aria-hidden="true" />Kesiapan beralih ke Lembar Insentif</h2></div>
      {state === "all" ? (
        <div className="section-pad text-fs-13 text-kn-text-2" data-testid="ins-ready-all">Kesiapan dihitung per PT. Pilih satu PT di pemilih PT (kanan atas).</div>
      ) : state === "loading" ? (
        <div className="section-pad text-fs-13 text-kn-text-2" role="status" data-testid="ins-ready-loading">Memeriksa kesiapan…</div>
      ) : state === "error" ? (
        <div className="section-pad"><ErrorNotice testId="ins-ready-error" message={`Kesiapan tidak bisa diperiksa. ${err}`.trim()} onRetry={load} /></div>
      ) : (
        <div className="section-body space-y-3">
          <p className="text-fs-13 text-kn-text" data-testid="ins-ready-mode">Cara insentif sales masuk penggajian di PT ini: <b>{data?.mode_label}</b></p>
          <ul className="space-y-2" data-testid="ins-ready-list">{(data?.checks || []).map((c) => <ButirKesiapan key={c.code} c={c} />)}</ul>
          <div className="flex flex-wrap items-center gap-3 text-fs-12 text-kn-text-2">
            <span data-testid="ins-ready-summary">{ringkasanKesiapan(data?.mode, siap)}</span>
            <button type="button" data-testid="ins-ready-open-config" className="link-button text-fs-12"
              onClick={() => openConfig({ key: "hr.payroll_commission_mode" })}>
              <Settings2 size={12} aria-hidden="true" /> Ubah di Pusat Pengaturan</button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── KA-9 — tautan ke tab Skema & Tarif (dulu bagian "Komisi otomatis (cara lama)") ───────────────────────────────────
function TautanSkema({ sakelar }) {
  if (!sakelar) return null;
  return (
    <LinkCard testId="ins-scheme-link" what="Sumber insentif, tarif komisi, pengali, dan akrual komisi"
      where="SDM › Kinerja & Insentif › Skema & Tarif" view="incentive-scheme" hideWhenDenied />
  );
}

export default function IncentiveSetupView() {
  const { canWrite, selectedEntity, entities } = useEntityScope();
  const canConfigure = canCurrent("incentive", "configure");
  const pt = entityFullById(entities, selectedEntity, "PT ini");
  const [sakelar, setSakelar] = useState(null);
  const props = { canWrite, canConfigure, entity: selectedEntity, entities, pt };
  return (
    <div className="space-y-4" data-testid="incentive-setup-view">
      <EntityScopeBanner testId="ins-scope" />
      <BagianTarget {...props} onSakelar={setSakelar} />
      <BagianKomponen {...props} />
      <BagianDefinisi {...props} />
      <BagianKesiapan {...props} />
      <TautanSkema sakelar={sakelar} />
    </div>
  );
}
