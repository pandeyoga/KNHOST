/**
 * WarehouseProfileDrawer (FASE R0) — konfigurasi profil GEDUNG:
 * lokasi (site), peran (roles), rules penyimpanan (kategori/grade), gate fisik.
 * Semua configurable oleh user (keputusan pemilik: fungsi gudang bisa berubah).
 *
 * PREP-C (8 Nov 2026) — data lokasi & gedung belum tervalidasi, jadi semua diatur di sini: peran Inspeksi & Gudang
 * Bahan, mode pencatatan stok (per roll bertag / kuantitas), bentuk penyimpanan (rak / petak lantai), aturan artikel
 * & PT pemilik (AND), gate per gedung (punya gate, mode gate/handheld, pasangan IN/OUT, tata letak, clear zone).
 */
import { useEffect, useState } from "react";
import { Save, MapPin, Shield, Layers, Building2, Boxes } from "lucide-react";
import FormModal from "../../../components/FormModal";
import KNSelect from "../../../components/KNSelect";
import { errText, listGateDevices, listTemplates, patchWarehouse, WH_ROLES } from "./warehouseApi";
import { STOCK_MODES, STORAGE_FORMS, gatePayload, normalizeGate, toggleIn } from "./warehouseProfileUtils";
import WarehouseGateSection from "./WarehouseGateSection";
import useDomainEnums from "../../../hooks/useDomainEnums";
const RULE_MODES = [
  { value: "none", label: "Tanpa aturan (semua barang boleh)" },
  { value: "category", label: "Per kategori kain (master ERP)" },
  { value: "grade", label: "Per grade (mis. gedung retur)" },
  { value: "combined", label: "Gabungan — kategori, grade, jenis kain, artikel & PT (semua wajib)" },
];
const FABRICS = ["woven", "knit"];
const head = "mb-1 flex items-center gap-1 text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]";

export default function WarehouseProfileDrawer({ warehouse, sites = [], categories = [], entities = [], onClose, onSaved }) {
  const [siteId, setSiteId] = useState(warehouse.site_id || "");
  const [roles, setRoles] = useState(warehouse.roles || []);
  const { options: enumOptions } = useDomainEnums();
  const activeGrades = enumOptions("grade").map((o) => o.value);
  const rules0 = warehouse.storage_rules || {};
  const [ruleMode, setRuleMode] = useState(rules0.mode || "none");
  const [cats, setCats] = useState(rules0.categories || []);
  const [grades, setGrades] = useState(rules0.grades || []);
  const [fabrics, setFabrics] = useState(rules0.fabric_types || []);
  const [tplIds, setTplIds] = useState(rules0.template_ids || []);
  const [owners, setOwners] = useState(rules0.owner_entity_ids || []);
  const [stockMode, setStockMode] = useState(warehouse.stock_mode || "roll_tagged");
  const [storageForm, setStorageForm] = useState(warehouse.storage_form || "rack");
  const [gate, setGate] = useState(() => normalizeGate(warehouse.gate_config));
  const [devices, setDevices] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    listGateDevices(warehouse.id).then(setDevices).catch(() => setDevices([]));
    listTemplates().then(setTemplates).catch(() => setTemplates([]));
  }, [warehouse.id]);

  const toggle = (list, setList, val) => setList(toggleIn(list, val));
  const combined = ruleMode === "combined";

  const save = async () => {
    setSaving(true); setError("");
    try {
      await patchWarehouse(warehouse.id, {
        site_id: siteId,
        roles,
        stock_mode: stockMode,
        storage_form: storageForm,
        storage_rules: { mode: ruleMode, categories: cats, grades, fabric_types: combined ? fabrics : [],
          template_ids: combined ? tplIds : [], owner_entity_ids: combined ? owners : [] },
        gate_config: gatePayload(gate),
      });
      onSaved(`Profil ${warehouse.name} tersimpan.`);
    } catch (e) { setError(errText(e, "Gagal menyimpan profil gudang.")); }
    finally { setSaving(false); }
  };

  const siteOpts = [{ value: "", label: "— Tanpa lokasi —" },
    ...sites.map((s) => ({ value: s.id, label: `${s.name}${s.city ? ` (${s.city})` : ""}` }))];
  const tplName = Object.fromEntries(templates.map((t) => [t.id, t.name]));
  const tplOpts = templates.filter((t) => !tplIds.includes(t.id)).map((t) => ({ value: t.id, label: t.name }));

  // Fase 3 · P5 (L-03) — dulu laci `div fixed inset-0` buatan sendiri (tanpa Esc/klik-latar baku); kini FormModal
  // baku — layar penuh di HP, tombol Simpan di kaki tetap. Isian sama.
  return (
    <FormModal open onClose={onClose} title={`Profil Gedung · ${warehouse.name}`} icon={Building2} size="md"
      subtitle="Lokasi, peran gedung, mode stok, aturan penyimpanan & gate RFID" testId="wh-profile-drawer"
      busy={saving} error={error}
      footer={(
        <div className="flex justify-end gap-2">
          <button type="button" data-testid="wh-profile-close" className="secondary-button" onClick={onClose} disabled={saving}>Tutup</button>
          <button type="button" data-testid="wh-profile-save" className="primary-button" onClick={save} disabled={saving}>
            <Save size={14} /> {saving ? "Menyimpan…" : "Simpan Profil"}
          </button>
        </div>
      )}>
        <div className="space-y-4">
          <section>
            <p className={head}><MapPin size={12} /> Lokasi (Site)</p>
            <KNSelect data-testid="wh-profile-site" value={siteId} onValueChange={setSiteId}
              options={siteOpts} className="field text-[12px]" placeholder="Pilih lokasi" />
          </section>

          <section>
            <p className={head}><Layers size={12} /> Peran Gedung (boleh lebih dari satu)</p>
            <div className="grid grid-cols-2 gap-1.5">
              {WH_ROLES.map((r) => (
                <button key={r.key} type="button" data-testid={`wh-profile-role-${r.key}`}
                  onClick={() => toggle(roles, setRoles, r.key)}
                  className={`rounded-md border px-2 py-1.5 text-left text-[12px] font-semibold ${
                    roles.includes(r.key) ? "border-[#0058CC] bg-[#EAF2FF] text-[#0058CC]" : "border-[#E5E5EA] bg-white text-[#6B6B73]"}`}>
                  {r.label}
                </button>
              ))}
            </div>
            {roles.includes("storage") && roles.some((r) => ["transit", "central_inbound"].includes(r)) && (
              <p data-testid="wh-profile-single-note" className="mt-1 text-[10.5px] text-[#6B6B73]">
                Gedung tunggal (transit + simpan): roll baru langsung tercatat tersimpan — cukup penempatan bin, tanpa
                Putaway Order antar gedung.
              </p>
            )}
          </section>

          <section className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <label className="block">
              <span className={head}><Boxes size={12} /> Mode pencatatan stok</span>
              <KNSelect data-testid="wh-profile-stock-mode" value={stockMode} onValueChange={setStockMode}
                options={STOCK_MODES} className="field text-[12px]" />
            </label>
            <label className="block">
              <span className={head}><Boxes size={12} /> Bentuk penyimpanan</span>
              <KNSelect data-testid="wh-profile-storage-form" value={storageForm} onValueChange={setStorageForm}
                options={STORAGE_FORMS} className="field text-[12px]" />
            </label>
            <p className="text-[10.5px] text-[#8E8E93] sm:col-span-2">Bin tetap berarti alamat simpan & kapasitas = jumlah roll, baik di rak maupun petak lantai. Bentuk per zona bisa diatur di struktur lokasi.</p>
          </section>

          <section>
            <p className={head}><Shield size={12} /> Aturan Penyimpanan</p>
            <KNSelect data-testid="wh-profile-rulemode" value={ruleMode} onValueChange={setRuleMode}
              options={RULE_MODES} className="field text-[12px]" />
            {["category", "combined"].includes(ruleMode) && (
              <div className="mt-2 grid grid-cols-2 gap-1" data-testid="wh-profile-categories">
                {categories.map((c) => (
                  <label key={c.id} className="flex items-center gap-1.5 rounded px-1.5 py-1 text-[12px] hover:bg-[#F5F5F7]">
                    <input type="checkbox" checked={cats.includes(c.name)}
                      data-testid={`wh-profile-cat-${c.id}`}
                      onChange={() => toggle(cats, setCats, c.name)} />
                    {c.name}
                  </label>
                ))}
                <p className="col-span-2 text-[10.5px] text-[#8E8E93]">Kosong = semua kategori boleh. Centang untuk membatasi.</p>
              </div>
            )}
            {["grade", "combined"].includes(ruleMode) && (
              <div className="mt-2 flex flex-wrap gap-1.5" data-testid="wh-profile-grades">
                {[...activeGrades, ...grades.filter((g) => !activeGrades.includes(g))].map((g) => (
                  <button key={g} type="button" data-testid={`wh-profile-grade-${g}`}
                    onClick={() => toggle(grades, setGrades, g)}
                    className={`rounded-md border px-3 py-1.5 text-[12px] font-bold ${
                      grades.includes(g) ? "border-[#6B219A] bg-[#F3E9FA] text-[#6B219A]" : "border-[#E5E5EA] bg-white text-[#6B6B73]"}`}>
                    {g}
                  </button>
                ))}
              </div>
            )}
            {combined && (
              <div className="mt-2 space-y-2">
                <div className="flex flex-wrap gap-1.5" data-testid="wh-profile-fabrics">
                  {FABRICS.map((f) => (
                    <button key={f} type="button" data-testid={`wh-profile-fabric-${f}`}
                      onClick={() => toggle(fabrics, setFabrics, f)}
                      className={`rounded-md border px-3 py-1.5 text-[12px] font-bold ${
                        fabrics.includes(f) ? "border-[#6B219A] bg-[#F3E9FA] text-[#6B219A]" : "border-[#E5E5EA] bg-white text-[#6B6B73]"}`}>
                      {f}
                    </button>
                  ))}
                  <p className="self-center text-[10.5px] text-[#8E8E93]">Kosong = semua jenis kain.</p>
                </div>
                <div data-testid="wh-profile-templates">
                  <KNSelect data-testid="wh-profile-template-add" value="" options={tplOpts} placeholder="+ Batasi ke artikel…"
                    onValueChange={(v) => v && setTplIds([...tplIds, v])} className="field text-[12px]" />
                  <div className="mt-1 flex flex-wrap gap-1">
                    {tplIds.map((t) => (
                      <button key={t} type="button" data-testid={`wh-profile-template-${t}`} onClick={() => toggle(tplIds, setTplIds, t)}
                        className="rounded border border-[#0058CC] bg-[#EEF4FF] px-2 py-0.5 text-[11px] font-semibold text-[#0058CC]">
                        {tplName[t] || t} ×
                      </button>
                    ))}
                    {!tplIds.length && <span className="text-[10.5px] text-[#8E8E93]">Kosong = semua artikel.</span>}
                  </div>
                </div>
                <div className="flex flex-wrap gap-1.5" data-testid="wh-profile-owners">
                  {entities.map((e) => (
                    <button key={e.id} type="button" data-testid={`wh-profile-owner-${e.id}`}
                      onClick={() => toggle(owners, setOwners, e.id)}
                      className={`rounded-md border px-2 py-1 text-[11.5px] font-semibold ${
                        owners.includes(e.id) ? "border-[#1B7F4B] bg-[#E6F6EC] text-[#1B7F4B]" : "border-[#E5E5EA] bg-white text-[#6B6B73]"}`}>
                      {e.short_name || e.legal_name || e.name || "PT tanpa nama"}
                    </button>
                  ))}
                  <p className="self-center text-[10.5px] text-[#8E8E93]">PT pemilik roll yang boleh disimpan — kosong = semua PT (gedung dipakai bersama).</p>
                </div>
              </div>
            )}
          </section>

          <WarehouseGateSection gate={gate} setGate={setGate} devices={devices} quantityMode={stockMode === "quantity"} />
        </div>
    </FormModal>
  );
}
