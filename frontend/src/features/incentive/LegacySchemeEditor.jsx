/**
 * LegacySchemeEditor — KM-T5 · jenjang komisi otomatis per sales & bulan (bagian **Komisi otomatis (cara lama)** di
 * SDM › Kinerja & Insentif › Target & Aturan).
 *
 * Dipindah dari bagian "Skema Insentif / Tier" `features/crm/IncentiveSchemeEditor.jsx` (KN_17 §6.2; tab tersembunyi
 * "Skema (Arsip)"). Bagian TARGET berkas lama dihapus: target per sales per PT per jenis periode diatur di bagian Target
 * layar yang sama (`PUT /api/incentive/targets`, KM-T1) — pilihan "Tipe Periode" lama tidak pernah mengubah periode yang
 * disimpan. Jenjang dipakai mesin komisi strategi `achievement_tiered` (`sales_force_service._compute_commission_tiered`)
 * untuk PT yang belum beralih ke Lembar Insentif.
 *
 * Sumber: `GET /api/sales-users` (daftar sales PT), `GET`/`POST /api/sales-incentives`. Lihat = `sales_force.view`
 * (gerbang di `IncentiveSetupView`), simpan = `sales_force.update` (`canCurrent`, sama dengan izin endpoint).
 */
import { useEffect, useState } from "react";
import { Award, Plus, Save, Trash2 } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import { canCurrent } from "../../config/roles";
import { bulanIni, pilihanBulan } from "./MyIncentiveCard";

export const TEKS_TANPA_UBAH = "Menyimpan jenjang komisi butuh akses Ubah di modul Pengawasan Tim Sales & Kredit.";
const BASIS = [
  { value: "collection", label: "Pencairan (uang tertagih)" },
  { value: "sales", label: "Penjualan" },
  { value: "tiered", label: "Bertingkat (capaian target)" },
];

export function jenjangBawaan() {
  return [
    { min_achievement: 0, rate: 1.0 },
    { min_achievement: 80, rate: 1.5 },
    { min_achievement: 100, rate: 2.5 },
    { min_achievement: 120, rate: 3.5 },
  ];
}
const skemaKosong = () => ({ basis: "collection", tiers: jenjangBawaan(), bonus_new_customer: 0, bonus_focus_product: 0,
  notes: "" });

/** Jenjang terurut naik menurut capaian minimum; angka negatif → pesan galat (string), selain itu "". */
export function periksaJenjang(tiers) {
  return (tiers || []).some((t) => Number(t.min_achievement) < 0 || Number(t.rate) < 0)
    ? "Capaian minimum dan rate tidak boleh negatif." : "";
}

export default function LegacySchemeEditor() {
  const canUpdate = canCurrent("sales_force", "update");
  const [salesUsers, setSalesUsers] = useState([]);
  const [salesId, setSalesId] = useState("");
  const [period, setPeriod] = useState(bulanIni());
  const [scheme, setScheme] = useState(skemaKosong());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    axios.get(`${API}/sales-users`).then((r) => {
      const list = Array.isArray(r.data) ? r.data : [];
      setSalesUsers(list);
      if (list.length) setSalesId((cur) => cur || list[0].id);
    }).catch((e) => setError(e.response?.data?.detail || "Daftar sales belum bisa dimuat."));
  }, []);

  async function loadScheme() {
    if (!salesId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/sales-incentives`, { params: { sales_id: salesId, period } });
      const s = (r.data || [])[0];
      setScheme(s ? {
        basis: s.basis || "collection",
        tiers: (s.tiers && s.tiers.length ? s.tiers : jenjangBawaan()).map((x) => ({
          min_achievement: Number(x.min_achievement) || 0, rate: Number(x.rate) || 0 })),
        bonus_new_customer: s.bonus_new_customer || 0, bonus_focus_product: s.bonus_focus_product || 0,
        notes: s.notes || "",
      } : skemaKosong());
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Jenjang komisi belum bisa dimuat.");
    } finally { setLoading(false); }
  }
  useEffect(() => { loadScheme(); }, [salesId, period]); // eslint-disable-line react-hooks/exhaustive-deps

  async function save() {
    const salah = periksaJenjang(scheme.tiers);
    if (salah) { setError(salah); return; }
    setSaving(true);
    try {
      const tiers = [...scheme.tiers]
        .map((t) => ({ min_achievement: Number(t.min_achievement) || 0, rate: Number(t.rate) || 0 }))
        .sort((a, b) => a.min_achievement - b.min_achievement);
      await axios.post(`${API}/sales-incentives`, {
        sales_id: salesId, period, basis: scheme.basis, tiers,
        bonus_new_customer: Number(scheme.bonus_new_customer) || 0,
        bonus_focus_product: Number(scheme.bonus_focus_product) || 0,
        notes: scheme.notes,
      });
      setScheme((s) => ({ ...s, tiers }));
      setNotice("Jenjang komisi tersimpan.");
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal menyimpan jenjang komisi.");
    } finally { setSaving(false); }
  }

  const ubahJenjang = (idx, key, val) => setScheme((s) => ({
    ...s, tiers: s.tiers.map((t, i) => (i === idx ? { ...t, [key]: val } : t)) }));

  return (
    <section className="section-card" data-testid="legacy-scheme-editor">
      <div className="section-head">
        <h3 className="flex items-center gap-2"><Award size={14} className="text-kn-action" aria-hidden="true" />Jenjang komisi per sales</h3>
      </div>
      <div className="section-body space-y-3">
        {notice && <div className="notice-bar success" data-testid="legacy-scheme-notice"><span className="text-fs-12">{notice}</span></div>}
        <ErrorNotice message={error} onRetry={loadScheme} onDismiss={() => setError("")} testId="legacy-scheme-error" />
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-[220px]"><label className="field-label">Sales</label>
            <KNSelect data-testid="legacy-scheme-sales" value={salesId} onValueChange={setSalesId} className="field"
              placeholder="Pilih sales" options={salesUsers.map((s) => ({ value: s.id, label: s.name }))} /></div>
          <div className="w-[200px]"><label className="field-label">Bulan</label>
            <KNSelect data-testid="legacy-scheme-month" value={period} onValueChange={(v) => v && setPeriod(v)} className="field"
              options={pilihanBulan(bulanIni())} /></div>
          <div className="w-[220px]"><label className="field-label">Basis komisi</label>
            <KNSelect data-testid="legacy-scheme-basis" value={scheme.basis} className="field" options={BASIS}
              onValueChange={(v) => setScheme((s) => ({ ...s, basis: v }))} /></div>
        </div>
        {loading ? (
          <p className="text-fs-13 text-kn-text-2" role="status" data-testid="legacy-scheme-loading">Memuat jenjang…</p>
        ) : !salesId ? (
          <p className="text-fs-13 text-kn-text-2" data-testid="legacy-scheme-nosales">Belum ada sales di PT ini.</p>
        ) : (
          <>
            <div className="table-container">
              <table className="data-table head-wrap" data-testid="legacy-scheme-tiers">
                <thead><tr><th>Capaian minimum (%)</th><th>Rate komisi (%)</th><th className="text-right col-sticky-end">Aksi</th></tr></thead>
                <tbody>
                  {scheme.tiers.length === 0 ? (
                    <tr><td colSpan={3} className="text-center text-fs-13 text-kn-text-2" data-testid="legacy-scheme-empty">Belum ada jenjang. Mesin memakai jenjang bawaan bila kosong.</td></tr>
                  ) : scheme.tiers.map((t, i) => (
                    <tr key={i} data-testid={`legacy-tier-${i}`}>
                      <td><input type="number" min="0" step="1" className="field" disabled={!canUpdate} value={t.min_achievement}
                        data-testid={`legacy-tier-min-${i}`} onChange={(e) => ubahJenjang(i, "min_achievement", e.target.value)} /></td>
                      <td><input type="number" min="0" step="0.1" className="field" disabled={!canUpdate} value={t.rate}
                        data-testid={`legacy-tier-rate-${i}`} onChange={(e) => ubahJenjang(i, "rate", e.target.value)} /></td>
                      <td className="text-right col-sticky-end">
                        {canUpdate ? <button type="button" className="icon-button" aria-label="Hapus jenjang" data-testid={`legacy-tier-remove-${i}`}
                          onClick={() => setScheme((s) => ({ ...s, tiers: s.tiers.filter((_, k) => k !== i) }))}><Trash2 size={14} className="text-kn-danger-text" /></button>
                          : <span className="text-fs-12 text-kn-text-2">—</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Angka label="Bonus per pelanggan baru (Rp)" value={scheme.bonus_new_customer} disabled={!canUpdate}
                testId="legacy-bonus-new" onChange={(v) => setScheme((s) => ({ ...s, bonus_new_customer: v }))} />
              <Angka label="Bonus per produk fokus (Rp)" value={scheme.bonus_focus_product} disabled={!canUpdate}
                testId="legacy-bonus-focus" onChange={(v) => setScheme((s) => ({ ...s, bonus_focus_product: v }))} />
            </div>
            <div><label className="field-label">Catatan</label>
              <textarea data-testid="legacy-scheme-notes" rows="2" className="field" disabled={!canUpdate} value={scheme.notes}
                onChange={(e) => setScheme((s) => ({ ...s, notes: e.target.value }))} placeholder="Opsional…" /></div>
            <div className="flex flex-wrap items-center gap-2">
              {canUpdate ? (
                <>
                  <button type="button" data-testid="legacy-tier-add" className="secondary-button btn-sm whitespace-nowrap"
                    onClick={() => setScheme((s) => ({ ...s, tiers: [...s.tiers, { min_achievement: 0, rate: 0 }] }))}><Plus size={13} aria-hidden="true" /> Tambah jenjang</button>
                  <button type="button" data-testid="legacy-scheme-save" disabled={saving || !salesId} onClick={save}
                    className="primary-button btn-sm whitespace-nowrap"><Save size={13} aria-hidden="true" /> {saving ? "Menyimpan…" : "Simpan jenjang"}</button>
                </>
              ) : <span className="text-fs-12 text-kn-text-2" data-testid="legacy-scheme-why">{TEKS_TANPA_UBAH}</span>}
            </div>
          </>
        )}
      </div>
    </section>
  );
}

function Angka({ label, value, onChange, testId, disabled }) {
  return (
    <div>
      <label className="field-label">{label}</label>
      <input type="number" min="0" className="field" data-testid={testId} disabled={disabled}
        value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}
