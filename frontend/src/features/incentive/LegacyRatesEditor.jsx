/**
 * LegacyRatesEditor — KM-T5 · bagian **Komisi otomatis (cara lama)** di SDM › Kinerja & Insentif › Target & Aturan.
 *
 * Dipindah dari `features/crm/IncentiveRatesEditor.jsx` (tab "Komisi Otomatis", dulu Pengaturan › Penjualan › Komisi &
 * Insentif; EPIC4, D-03). Hanya dipasang `IncentiveSetupView` untuk PT yang sakelar insentifnya
 * (`hr.payroll_commission_mode`) masih komisi otomatis — bukan `sheet` (Lembar Insentif) dan bukan `off`. Isinya tidak
 * berubah:
 *   1. "Bawaan komisi" = Pusat Pengaturan yang DIKUNCI ke kunci `commission.*` (mesin `useSettingsBrowser`; layar
 *      pengaturan lain menyembunyikan kunci ini dan menautkan ke sini — `COMMISSION_HOME`).
 *   2. Tarif per PT × kategori (DATA master `incentive_rates`, `GET/POST/PATCH/DELETE /api/incentive-rates`). Kategori tanpa
 *      ambang/mekanik memakai bawaan di atas. Form tarif = pop-up `FormModal`.
 * Lihat = `sales_force.view` (gerbang di `IncentiveSetupView`); tombol ubah = `sales_force.update`, hapus =
 * `sales_force.delete` (`canCurrent`, sama dengan izin endpoint-nya). KM-T4 (KM-07) — tanpa isian "Satuan".
 */
import { useCallback, useEffect, useState } from "react";
import MoneyInput from "@/components/MoneyInput";
import { Trash2, Pencil, RefreshCw, Percent, Plus, SlidersHorizontal } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import FormModal from "../../components/FormModal";
import { formatCurrency } from "../../utils/formatters";
import { entityFullById, entityOptions } from "../../utils/entityLabel";
import { askReason } from "@/services/confirmService";
import { canCurrent } from "../../config/roles";
import { SettingsBrowser, SettingsNotice, useSettingsBrowser } from "../settings/config/SettingsHub";
import { COMMISSION_PREFIX } from "../settings/config/configGroupViews";

export const TEKS_TANPA_UBAH = "Mengubah tarif komisi butuh akses Ubah di modul Pengawasan Tim Sales & Kredit.";
const THRESHOLD_TYPES = [
  { value: "pct", label: "% diskon" },
  { value: "rp_per_unit", label: "Rp / unit" },
];
const MECHANICS = [
  { value: "tier_factor", label: "Faktor (komisi × faktor)" },
  { value: "potong_rp", label: "Potong Rp/unit" },
  { value: "cutoff", label: "Cutoff (komisi 0)" },
];
const EMPTY = {
  entity_id: "all", category: "", per_unit_amount: 0,
  discount_threshold_type: "pct", discount_threshold: 10, discount_mechanic: "tier_factor",
  discount_factor: 0.5, discount_potong_rp: 0, margin_cap_pct: 50, status: "active",
};
const COMMISSION_KEYS = [COMMISSION_PREFIX];
const COMMISSION_GROUPS = ["harga-diskon"];

/** D-03 — bawaan komisi (`commission.*`) di layar yang sama dengan tarifnya. */
function CommissionDefaults({ selectedEntity, entities, focusKey, focusGroup, focusNonce, onFocusConsumed }) {
  const s = useSettingsBrowser({
    selectedEntity, groupIds: COMMISSION_GROUPS, includeKeys: COMMISSION_KEYS,
    focusKey, focusGroup, focusNonce, onFocusConsumed,
  });
  return (
    <section className="section-card" data-testid="incentive-commission-defaults">
      <div className="section-head">
        <h3 className="flex items-center gap-2"><SlidersHorizontal size={14} className="text-kn-action" aria-hidden="true" />Bawaan komisi</h3>
      </div>
      <div className="section-body cfg-hub cfg-group-view">
        <p className="cfg-group-intro">
          Strategi, satuan dasar, ambang & mekanik potongan, serta batas margin yang berlaku untuk kategori yang tidak
          punya tarif sendiri. Bisa dijelaskan, dicoba dulu, dijadwalkan, dan dilihat riwayatnya per kartu.
        </p>
        <SettingsNotice s={s} />
        <SettingsBrowser s={s} entities={entities} groupNav="chips" searchPlaceholder="Cari bawaan komisi…" />
      </div>
    </section>
  );
}

/** Ringkasan mekanik diskon satu tarif: "×0,5 bila diskon ≥ 10%" · "−Rp 200 …" · "Komisi 0 …". */
export function teksDiskon(r) {
  const efek = r.discount_mechanic === "cutoff" ? "Komisi 0"
    : r.discount_mechanic === "potong_rp" ? `−${formatCurrency(r.discount_potong_rp)}`
      : `×${String(r.discount_factor).replace(".", ",")}`;
  const ambang = r.discount_threshold_type === "pct" ? `${String(r.discount_threshold).replace(".", ",")}%`
    : formatCurrency(r.discount_threshold);
  return `${efek} bila diskon ≥ ${ambang}`;
}

export default function LegacyRatesEditor({
  selectedEntity, entities: scopeEntities = [], focusKey = "", focusGroup = "", focusNonce = 0, onFocusConsumed,
}) {
  const canUpdate = canCurrent("sales_force", "update");
  const canDelete = canCurrent("sales_force", "delete");
  const [rows, setRows] = useState([]);
  const [cats, setCats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState(null);           // null = pop-up tertutup
  const [editingId, setEditingId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [entities, setEntities] = useState([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r, c, e] = await Promise.all([
        axios.get(`${API}/incentive-rates`),
        axios.get(`${API}/product-categories`),
        axios.get(`${API}/entities`),
      ]);
      setRows(Array.isArray(r.data) ? r.data : []);
      setCats((Array.isArray(c.data) ? c.data : []).filter((x) => x.status === "active"));
      setEntities(Array.isArray(e.data) ? e.data : []);
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Tarif komisi belum bisa dimuat.");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const closeForm = () => { setForm(null); setEditingId(null); setFormError(""); };
  const openCreate = () => { setEditingId(null); setForm({ ...EMPTY }); setFormError(""); };
  const startEdit = (r) => { setEditingId(r.id); setForm({ ...EMPTY, ...r }); setFormError(""); };
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  const save = async () => {
    if (!String(form.category).trim()) { setFormError("Kategori wajib diisi."); return; }
    setSaving(true); setFormError("");
    const payload = {
      ...form,
      per_unit_amount: Number(form.per_unit_amount) || 0,
      discount_threshold: Number(form.discount_threshold) || 0,
      // Isian yang tidak berlaku untuk mekanik terpilih tidak dikirim berubah (nilai lama dipertahankan server).
      discount_factor: Number(form.discount_factor) || 0,
      discount_potong_rp: Number(form.discount_potong_rp) || 0,
      margin_cap_pct: Number(form.margin_cap_pct) || 0,
    };
    delete payload.incentive_unit;   // KM-T4 — dokumen lama boleh masih membawa satuan; tidak dikirim
    try {
      if (editingId) await axios.patch(`${API}/incentive-rates/${editingId}`, { data: payload });
      else await axios.post(`${API}/incentive-rates`, payload);
      closeForm(); await load();
      setNotice("Tarif komisi tersimpan.");
    } catch (e) {
      setFormError(e.response?.data?.detail || "Gagal menyimpan tarif.");
    } finally { setSaving(false); }
  };

  const remove = async (r) => {
    // Berdampak UANG: tarif ini yang dipakai menghitung komisi sales.
    const reason = await askReason({
      title: `Hapus tarif komisi ${r.category}?`,
      message: "Perhitungan komisi berikutnya untuk kategori ini akan memakai tarif lain "
        + "(atau nol bila tidak ada tarif pengganti).",
      reasonLabel: "Alasan penghapusan",
      confirmLabel: "Hapus Tarif",
      danger: true,
      testId: "incentive-rate-delete-confirm",
    });
    if (reason === null) return;
    try { await axios.delete(`${API}/incentive-rates/${r.id}`, { params: { reason } }); await load(); }
    catch (e) { setError(e.response?.data?.detail || "Gagal menghapus tarif."); }
  };

  const catOptions = cats.length
    ? cats.map((c) => ({ value: c.name, label: c.name }))
    : ["Batik", "Tenun", "Lurik", "Songket", "Ulos", "Jumputan", "Endek"].map((n) => ({ value: n, label: n }));
  const entityOpts = [{ value: "all", label: "Semua PT" }, ...entityOptions(entities)];

  return (
    <div data-testid="incentive-rates-editor" className="grid gap-3">
      {notice && <div className="notice-bar success" data-testid="incentive-notice"><span className="text-fs-12">{notice}</span></div>}

      <CommissionDefaults selectedEntity={selectedEntity} entities={scopeEntities.length ? scopeEntities : entities}
        focusKey={focusKey} focusGroup={focusGroup} focusNonce={focusNonce} onFocusConsumed={onFocusConsumed} />

      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="incentive-error" />

      <section className="section-card">
        <div className="section-head">
          <h3 className="flex items-center gap-2"><Percent size={14} className="text-kn-action" aria-hidden="true" />Tarif komisi per PT × kategori {rows.length > 0 ? `(${rows.length})` : ""}</h3>
        </div>
        <div className="section-body space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            {canUpdate
              ? <button type="button" data-testid="rate-create-button" className="primary-button btn-sm whitespace-nowrap" onClick={openCreate}><Plus size={14} aria-hidden="true" /> Tarif Baru</button>
              : <span className="text-fs-12 text-kn-text-2" data-testid="rate-why">{TEKS_TANPA_UBAH}</span>}
            <button type="button" data-testid="rate-refresh-button" className="secondary-button btn-sm whitespace-nowrap" onClick={load}><RefreshCw size={13} className={loading ? "animate-spin" : ""} aria-hidden="true" /> Muat ulang</button>
          </div>
          {loading ? (
            <div className="grid gap-2" data-testid="rate-loading">{[0, 1, 2].map((i) => <div key={i} className="h-9 bg-kn-neutral-soft rounded animate-pulse" />)}</div>
          ) : rows.length === 0 ? (
            <div className="py-6 text-center text-fs-13 text-kn-text-2" data-testid="rate-empty">Belum ada tarif komisi.</div>
          ) : (
            <div className="table-container">
              <table className="data-table head-wrap" data-testid="rate-table">
                <thead>
                  <tr>
                    <th>PT</th><th>Kategori</th><th className="text-right">Tarif</th><th>Diskon</th>
                    <th className="text-right">Batas margin</th><th className="text-right col-sticky-end">Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id} data-testid={`rate-row-${r.id}`}>
                      <td className="min-w-[96px] break-words text-fs-12 text-kn-text-2">{r.entity_id === "all" ? "Semua PT" : entityFullById(entities, r.entity_id)}</td>
                      <td className="font-semibold break-words">{r.category}</td>
                      <td className="text-right tabular-nums"><span className="whitespace-nowrap">{formatCurrency(r.per_unit_amount)}</span><span className="block text-fs-12 text-kn-text-2">/satuan dasar</span></td>
                      <td className="min-w-[120px] break-words text-fs-12 text-kn-text-2 tabular-nums">{teksDiskon(r)}</td>
                      <td className="text-right tabular-nums">{r.margin_cap_pct}%</td>
                      <td className="col-sticky-end">
                        <div className="flex items-center justify-end gap-1">
                          {canUpdate && <button type="button" data-testid={`rate-edit-${r.id}`} className="icon-button" onClick={() => startEdit(r)} aria-label="Ubah tarif"><Pencil size={13} /></button>}
                          {canDelete && <button type="button" data-testid={`rate-delete-${r.id}`} className="icon-button" onClick={() => remove(r)} aria-label="Hapus tarif"><Trash2 size={13} className="text-kn-danger-text" /></button>}
                          {!canUpdate && !canDelete && <span className="text-fs-12 text-kn-text-2">—</span>}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      <FormModal open={!!form} onClose={closeForm} testId="rate-form" icon={Percent} size="md"
        title={editingId ? "Ubah Tarif" : "Tarif Baru"} subtitle="Tarif komisi per satuan jual untuk satu kategori produk."
        onSubmit={save} busy={saving} error={formError}
        submitLabel={saving ? "Menyimpan..." : editingId ? "Simpan Perubahan" : "Simpan Tarif"}
        submitTestId="rate-save-button" cancelTestId="incentive-cancel-edit">
        {form && (
          <div className="grid gap-2 sm:grid-cols-2">
            <L label="PT">
              <KNSelect data-testid="rate-entity-input" className="field" value={form.entity_id} onValueChange={(v) => set({ entity_id: v })} options={entityOpts} placeholder="Pilih PT" />
            </L>
            <L label="Kategori *">
              <KNSelect data-testid="rate-category-input" className="field" value={form.category} onValueChange={(v) => set({ category: v })} options={catOptions} placeholder="Pilih kategori" />
            </L>
            <L label="Tarif (Rp per satuan dasar)"><MoneyInput testId="rate-per-unit-input" className="field" value={form.per_unit_amount} onChange={(v) => set({ per_unit_amount: v })} /></L>
            <L label="Ambang diskon (basis)"><KNSelect data-testid="rate-threshold-type" className="field" value={form.discount_threshold_type} onValueChange={(v) => set({ discount_threshold_type: v })} options={THRESHOLD_TYPES} /></L>
            <L label="Ambang"><input data-testid="rate-threshold-input" type="number" className="field" value={form.discount_threshold} onChange={(e) => set({ discount_threshold: e.target.value })} /></L>
            <L label="Mekanik diskon"><KNSelect data-testid="rate-mechanic-input" className="field" value={form.discount_mechanic} onValueChange={(v) => set({ discount_mechanic: v })} options={MECHANICS} /></L>
            {/* G2-26 — isian mengikuti mekanik: Faktor → faktor; Potong → Rp/satuan; Cutoff → keduanya tidak berlaku. */}
            {form.discount_mechanic === "tier_factor" && (
              <L label="Faktor komisi (× komisi)"><input data-testid="rate-factor-input" type="number" step="0.1" min="0" className="field" value={form.discount_factor} onChange={(e) => set({ discount_factor: e.target.value })} /></L>
            )}
            {form.discount_mechanic === "potong_rp" && (
              <L label="Potong (Rp per satuan dasar)"><MoneyInput testId="rate-potong-input" className="field" value={form.discount_potong_rp} onChange={(v) => set({ discount_potong_rp: v })} /></L>
            )}
            {form.discount_mechanic === "cutoff" && (
              <p className="self-end text-fs-12 text-kn-text-2" data-testid="rate-cutoff-note">Diskon di atas ambang → komisi baris itu 0.</p>
            )}
            <L label="Batas margin komisi (%)"><input data-testid="rate-margin-cap-input" type="number" className="field" value={form.margin_cap_pct} onChange={(e) => set({ margin_cap_pct: e.target.value })} /></L>
          </div>
        )}
      </FormModal>
    </div>
  );
}

function L({ label, children }) {
  return (
    <div>
      <label className="field-label">{label}</label>
      {children}
    </div>
  );
}
