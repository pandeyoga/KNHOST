/**
 * IncentiveRatesEditor (EPIC4) — Pengaturan › Penjualan › **Komisi & Insentif**.
 *
 * Fase 3 · P2 (D-03, keputusan pemilik 26 Okt) — tarif insentif dulu di TIGA tempat: tabel tarif (layar ini),
 * kunci bawaan `commission.*` (Pusat Pengaturan › Harga, Diskon & Komisi — di sini hanya kartu "pindah rumah") dan
 * Master per Badan Usaha kind `incentive-rates` (baca-saja). Kini satu layar:
 *   1. "Bawaan komisi" = Pusat Pengaturan yang DIKUNCI ke kunci `commission.*` (strategi, satuan, ambang, mekanik,
 *      batas margin) — mesin yang sama (`useSettingsBrowser`), bukan form kedua; layar pengaturan lain
 *      menyembunyikan kunci ini + menautkan ke sini, sehingga tidak tampil ganda.
 *   2. Tabel tarif per entitas × kategori (DATA master). Kategori tanpa ambang/mekanik memakai bawaan di atas.
 * L-03: form tarif yang dulu panel tetap di kolom kiri → pop-up `FormModal` (di HP layar penuh, isian lengkap).
 * Manage rate: admin/manager (server).
 */
import { useCallback, useEffect, useState } from "react";
import MoneyInput from "@/components/MoneyInput";
import { Trash2, Pencil, RefreshCw, Percent, Plus, SlidersHorizontal } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import FormModal from "../../components/FormModal";
import DesktopOnlyNotice from "../../components/DesktopOnlyNotice";
import { formatCurrency } from "../../utils/formatters";
import { entityFullById, entityOptions } from "../../utils/entityLabel";
import { askReason } from "@/services/confirmService";
import useUomConversions from "../../hooks/useUomConversions";
import { uomSelectOptions } from "../../utils/uomCatalog";
import { SettingsBrowser, SettingsNotice, useSettingsBrowser } from "../settings/config/SettingsHub";
import { COMMISSION_PREFIX } from "../settings/config/configGroupViews";

const THRESHOLD_TYPES = [
  { value: "pct", label: "% diskon" },
  { value: "rp_per_unit", label: "Rp / unit" },
];
const HIDDEN_UNITS = ["cm", "mm", "km", "dm", "inch", "in", "ft", "feet", "g", "gr", "gram", "mg", "ton", "ons"];
const MECHANICS = [
  { value: "tier_factor", label: "Faktor (komisi × faktor)" },
  { value: "potong_rp", label: "Potong Rp/unit" },
  { value: "cutoff", label: "Cutoff (komisi 0)" },
];
const EMPTY = {
  // Audit UI 111 — bawaan "yard" (seluruh matriks memakai /yard; dulu bawaan "Meter (m)").
  entity_id: "all", category: "", incentive_unit: "yard", per_unit_amount: 0,
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
        <div className="flex items-center gap-2"><SlidersHorizontal size={14} className="text-[#0058CC]" /><h2>Bawaan komisi</h2></div>
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

export default function IncentiveRatesEditor({
  selectedEntity, entities: scopeEntities = [], focusKey = "", focusGroup = "", focusNonce = 0, onFocusConsumed,
}) {
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
  // FASE U — satuan insentif dari MASTER satuan (produk per `panel` tetap bisa diberi tarif).
  useUomConversions();
  // UAT 24 Okt (audit UI tahap 2) — G2-26: satuan ukur yang tidak pernah dipakai menjual kain tidak ditawarkan.
  const unitOpts = uomSelectOptions({
    dimensions: ["length", "weight", "count"],
    extra: [form?.incentive_unit].filter(Boolean),
  }).filter((o) => !HIDDEN_UNITS.includes(o.value) || o.value === String(form?.incentive_unit || "").toLowerCase());

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
      setError(e.response?.data?.detail || "Gagal memuat tarif insentif.");
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
    try {
      if (editingId) await axios.patch(`${API}/incentive-rates/${editingId}`, { data: payload });
      else await axios.post(`${API}/incentive-rates`, payload);
      closeForm(); await load();
      setNotice("Tarif insentif tersimpan.");
    } catch (e) {
      setFormError(e.response?.data?.detail || "Gagal menyimpan tarif.");
    } finally { setSaving(false); }
  };

  const remove = async (r) => {
    // Berdampak UANG: tarif ini yang dipakai menghitung komisi sales.
    const reason = await askReason({
      title: `Hapus tarif insentif ${r.category}?`,
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
  // `/api/entities` tak punya field `name` — dulu opsi & kolom menampilkan `ent_ksc`.
  const entityOpts = [{ value: "all", label: "Semua entitas" }, ...entityOptions(entities)];

  return (
    <div data-testid="incentive-rates-editor" className="grid gap-3">
      <DesktopOnlyNotice testId="settings-desktop-notice" what="Pengaturan" />
      {notice && <div className="px-3 py-2 rounded-md bg-[#E6F6EC] text-[#1B7F4B] text-[12px] font-semibold" data-testid="incentive-notice">{notice}</div>}

      <CommissionDefaults selectedEntity={selectedEntity} entities={scopeEntities.length ? scopeEntities : entities}
        focusKey={focusKey} focusGroup={focusGroup} focusNonce={focusNonce} onFocusConsumed={onFocusConsumed} />

      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="incentive-error" />

      <section className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2"><Percent size={14} className="text-[#0058CC]" /><h2>Tarif per entitas × kategori {rows.length > 0 ? `(${rows.length})` : ""}</h2></div>
          <div className="ml-auto flex items-center gap-2">
            <button data-testid="rate-create-button" className="primary-button" onClick={openCreate}><Plus size={14} /> Tarif Baru</button>
            <button data-testid="rate-refresh-button" className="icon-button" onClick={load} aria-label="Muat ulang"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
          </div>
        </div>
        <div className="section-body">
          {loading ? (
            <div className="grid gap-2" data-testid="rate-loading">{[0, 1, 2, 3].map((i) => <div key={i} className="h-9 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
          ) : rows.length === 0 ? (
            <div className="py-10 text-center text-[12px] text-[#8E8E93]" data-testid="rate-empty">Belum ada tarif insentif.</div>
          ) : (
            <div className="table-container">
              <table className="data-table" data-testid="rate-table">
                <thead>
                  <tr>
                    <th>Entitas</th><th>Kategori</th><th className="text-right">Tarif</th><th>Diskon</th>
                    <th className="text-right">Batas Margin</th><th className="text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id} data-testid={`rate-row-${r.id}`}>
                      <td className="text-[11px] text-[#6B6B73]">{r.entity_id === "all" ? "Semua" : entityFullById(entities, r.entity_id)}</td>
                      <td className="font-semibold">{r.category}</td>
                      <td className="text-right tabular-nums">{formatCurrency(r.per_unit_amount)}<span className="text-[10px] text-[#9A9BA3]">/{r.incentive_unit}</span></td>
                      <td className="text-[11px] text-[#6B6B73] tabular-nums">{r.discount_mechanic === "cutoff" ? "Komisi 0" : r.discount_mechanic === "potong_rp" ? `−${formatCurrency(r.discount_potong_rp)}` : `×${String(r.discount_factor).replace(".", ",")}`} bila diskon ≥ {r.discount_threshold_type === "pct" ? `${String(r.discount_threshold).replace(".", ",")}%` : formatCurrency(r.discount_threshold)}</td>
                      <td className="text-right tabular-nums">{r.margin_cap_pct}%</td>
                      <td>
                        <div className="flex items-center justify-end gap-1">
                          <button data-testid={`rate-edit-${r.id}`} className="icon-button" onClick={() => startEdit(r)} aria-label="Ubah tarif"><Pencil size={13} /></button>
                          <button data-testid={`rate-delete-${r.id}`} className="icon-button" onClick={() => remove(r)} aria-label="Hapus tarif"><Trash2 size={13} className="text-[#D14343]" /></button>
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
            <L label="Entitas">
              <KNSelect data-testid="rate-entity-input" className="field" value={form.entity_id} onValueChange={(v) => set({ entity_id: v })} options={entityOpts} placeholder="Pilih entitas" />
            </L>
            <L label="Kategori *">
              <KNSelect data-testid="rate-category-input" className="field" value={form.category} onValueChange={(v) => set({ category: v })} options={catOptions} placeholder="Pilih kategori" />
            </L>
            <L label="Tarif (Rp/satuan)"><MoneyInput testId="rate-per-unit-input" className="field" value={form.per_unit_amount} onChange={(v) => set({ per_unit_amount: v })} /></L>
            <L label="Satuan"><KNSelect data-testid="rate-unit-input" className="field" value={form.incentive_unit} onValueChange={(v) => set({ incentive_unit: v })} options={unitOpts} /></L>
            <L label="Ambang diskon (basis)"><KNSelect data-testid="rate-threshold-type" className="field" value={form.discount_threshold_type} onValueChange={(v) => set({ discount_threshold_type: v })} options={THRESHOLD_TYPES} /></L>
            <L label="Ambang"><input data-testid="rate-threshold-input" type="number" className="field" value={form.discount_threshold} onChange={(e) => set({ discount_threshold: e.target.value })} /></L>
            <L label="Mekanik diskon"><KNSelect data-testid="rate-mechanic-input" className="field" value={form.discount_mechanic} onValueChange={(v) => set({ discount_mechanic: v })} options={MECHANICS} /></L>
            {/* G2-26 — isian mengikuti mekanik: Faktor → faktor; Potong → Rp/satuan; Cutoff → keduanya tidak berlaku. */}
            {form.discount_mechanic === "tier_factor" && (
              <L label="Faktor komisi (× komisi)"><input data-testid="rate-factor-input" type="number" step="0.1" min="0" className="field" value={form.discount_factor} onChange={(e) => set({ discount_factor: e.target.value })} /></L>
            )}
            {form.discount_mechanic === "potong_rp" && (
              <L label={`Potong (Rp/${form.incentive_unit || "satuan"})`}><MoneyInput testId="rate-potong-input" className="field" value={form.discount_potong_rp} onChange={(v) => set({ discount_potong_rp: v })} /></L>
            )}
            {form.discount_mechanic === "cutoff" && (
              <p className="self-end text-[11px] text-[#6B6B73]" data-testid="rate-cutoff-note">Diskon di atas ambang → komisi baris itu 0.</p>
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
      <label className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">{label}</label>
      {children}
    </div>
  );
}
