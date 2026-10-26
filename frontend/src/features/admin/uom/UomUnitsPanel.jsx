/**
 * UomUnitsPanel — tabel tunggal **Satuan & faktor** di Produk & Harga › Satuan & Konversi (fase 3 · P2, D-21).
 *
 * KENAPA: satuan dulu tampil di DUA daftar — "Daftar Satuan (UOM)" (AdminView tab uoms: kode MTR/YRD + faktor ke
 * dasar) dan "Aturan Konversi" (yard → meter 0,9144) — dengan nama berbeda (MTR vs meter) dan faktor yang bisa
 * tidak sama. Kini satu baris per satuan: kode & nama SERAGAM dari katalog server (`useUomConversions`, benih +
 * master), dimensi, faktor ke satuan dasar dan SUMBER faktornya (master satuan / aturan konversi / satuan dasar).
 * Aksi "Satuan baru" (form lengkap dari AdminView, kini `FormModal`) dan "Ubah faktor". Aturan faktor tetap yang
 * sudah tampil sebagai faktor satuan di sini tidak diulang di tabel aturan (`usedRuleIds`).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Pencil, Plus, Ruler } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import KNSelect from "../../../components/KNSelect";
import FormModal from "../../../components/FormModal";
import ResponsiveTable from "../../../components/ResponsiveTable";
import { invalidateUomCache } from "../../../hooks/useUomConversions";
import { apiErrorText } from "../../../utils/apiError";

const fmt = (v) => (v === null || v === undefined || v === "" ? "—"
  : Number(v).toLocaleString("id-ID", { maximumFractionDigits: 6 }));
const EMPTY_UOM = { code: "", name: "", base_type: "length", factor_to_base: 1, precision: 2, aliases: "", factor_per_document: false };
const low = (s) => String(s || "").trim().toLowerCase();

/** Baris tabel: satu per satuan katalog. Faktor: master `uoms` → aturan tetap ke satuan dasar → satuan dasar. */
export function buildUnitRows(units = [], unitsMaster = [], rules = [], dimensions = []) {
  const masterOf = (u) => unitsMaster.find((m) => [m.code, m.name, ...(m.aliases || [])].map(low).includes(low(u.code)));
  // Satuan dasar per dimensi = baris master aktif berfaktor 1 (MTR → "meter", KG → "kg", PCS → "pcs").
  const baseOf = {};
  unitsMaster.filter((m) => Number(m.factor_to_base) === 1 && (m.status || "active") === "active").forEach((m) => {
    const word = low((m.aliases || [])[0] || m.code);
    if (!baseOf[m.base_type]) baseOf[m.base_type] = word;
  });
  const dimLabel = Object.fromEntries((dimensions || []).map((d) => [d.value, d.label]));
  const used = new Set();
  const rows = units.map((u) => {
    const m = masterOf(u);
    const base = baseOf[u.dimension] || "";
    let factor = null; let source = "—"; let rule = null;
    if (base && low(u.code) === base) { factor = 1; source = "Satuan dasar"; }
    else if (m && Number(m.factor_to_base) > 0) { factor = Number(m.factor_to_base); source = "Master satuan"; }
    else {
      rule = rules.find((r) => r.kind === "fixed" && r.status === "active" && low(r.from_unit) === low(u.code)
        && (!base || low(r.to_unit) === base));
      if (rule) { factor = Number(rule.factor); source = "Aturan konversi"; used.add(rule.id); }
      else if (rules.some((r) => r.kind === "pack" && low(r.from_unit) === low(u.code))) source = "Per produk (kemasan)";
    }
    return { id: u.code, code: u.code, label: u.label || u.code, dimension: dimLabel[u.dimension] || u.dimension || "—",
      base, factor, source, master: m || null, rule, aliases: u.aliases || [] };
  });
  return { rows, usedRuleIds: used };
}

export default function UomUnitsPanel({ catalog, rules = [], canCreate, canEdit, onEditRule, onChanged }) {
  const [uoms, setUoms] = useState([]);               // baris master lengkap (punya `id`) untuk ubah faktor
  const [modal, setModal] = useState(null);           // { mode: "create"|"factor", data }
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const loadUoms = useCallback(async () => {
    try { const r = await axios.get(`${API}/uoms`); setUoms(Array.isArray(r.data) ? r.data : []); } catch (_) { /* baca-saja */ }
  }, []);
  useEffect(() => { loadUoms(); }, [loadUoms]);

  const { rows } = useMemo(() => buildUnitRows(catalog?.units || [], catalog?.units_master || [], rules,
    catalog?.dimensions || []), [catalog, rules]);
  const idOfMaster = (m) => uoms.find((u) => low(u.code) === low(m?.code))?.id || "";

  const save = async () => {
    setBusy(true); setErr("");
    try {
      if (modal.mode === "create") {
        const d = modal.data;
        await axios.post(`${API}/uoms`, { ...d, aliases: String(d.aliases || "").split(",").map((a) => a.trim()).filter(Boolean) });
      } else {
        await axios.patch(`${API}/uoms/${modal.data.id}`, { data: { factor_to_base: Number(modal.data.factor_to_base) } });
      }
      setModal(null);
      invalidateUomCache();
      await loadUoms();
      await onChanged?.();
    } catch (e) { setErr(apiErrorText(e, "Gagal menyimpan satuan.")); } finally { setBusy(false); }
  };
  const editFactor = (r) => {
    if (r.source === "Aturan konversi" && r.rule) { onEditRule?.(r.rule); return; }
    const id = idOfMaster(r.master);
    if (id) { setErr(""); setModal({ mode: "factor", data: { id, code: r.code, factor_to_base: r.factor ?? "" } }); }
  };
  const set = (patch) => setModal((m) => ({ ...m, data: { ...m.data, ...patch } }));
  const d = modal?.data || {};

  return (
    <div className="rounded-md border border-[#EFF0F2] bg-white" data-testid="uom-units-panel">
      <div className="flex flex-wrap items-center gap-2 border-b border-[#EFF0F2] bg-[#FAFBFC] px-2.5 py-1.5">
        <Ruler size={12} className="text-[#0058CC]" />
        <span className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Satuan &amp; faktor</span>
        <span className="text-[11px] text-[#8E8E93]">— satu baris per satuan; nama sama di seluruh layar</span>
        {canCreate && (
          <button data-testid="uom-unit-add" className="primary-button ml-auto !px-2 !py-1 !text-[11px]"
            onClick={() => { setErr(""); setModal({ mode: "create", data: { ...EMPTY_UOM } }); }}>
            <span className="flex items-center gap-1"><Plus size={11} /> Satuan baru</span>
          </button>
        )}
      </div>
      <ResponsiveTable testId="uom-unit" rows={rows} rowKey="code" stickyActions
        empty="Katalog satuan belum termuat."
        columns={[
          { key: "code", header: "Kode", mobile: "title", render: (r) => <b className="font-mono text-[11.5px]">{r.code}</b> },
          { key: "label", header: "Nama", mobile: "subtitle" },
          { key: "dimension", header: "Dimensi" },
          { key: "factor", header: "Faktor ke satuan dasar", align: "right", priority: 1,
            render: (r) => (r.factor === null ? "—" : r.factor === 1 && r.source === "Satuan dasar"
              ? <span className="text-[#6B6B73]">satuan dasar</span> : `1 ${r.code} = ${fmt(r.factor)} ${r.base}`.trim()) },
          { key: "source", header: "Sumber", mobile: "badge",
            render: (r) => <span className="status-pill pill-muted whitespace-nowrap" data-testid={`uom-unit-source-${r.code}`}>{r.source}</span> },
        ]}
        actions={canEdit ? (r) => ((r.source === "Master satuan" && idOfMaster(r.master)) || (r.source === "Aturan konversi") ? (
          <button type="button" className="secondary-button !px-2 !py-1 text-[11px]" data-testid={`uom-unit-factor-${r.code}`}
            onClick={() => editFactor(r)}><Pencil size={11} /> Ubah faktor</button>
        ) : null) : null} />

      <FormModal open={!!modal} onClose={() => setModal(null)} testId="uom-unit-form" icon={Ruler} size="md"
        title={modal?.mode === "create" ? "Satuan Baru" : `Ubah faktor · ${d.code || ""}`}
        subtitle={modal?.mode === "create" ? "Satuan untuk stok, PO, SO dan POS. Faktor ke satuan dasar menentukan konversi tetap."
          : "Faktor ke satuan dasar dipakai semua dokumen baru; dokumen lama tidak berubah."}
        onSubmit={save} busy={busy} error={err}
        submitDisabled={modal?.mode === "create" ? (!d.code || !d.name || !(Number(d.factor_to_base) > 0)) : !(Number(d.factor_to_base) > 0)}
        submitLabel={modal?.mode === "create" ? "Simpan Satuan" : "Simpan Faktor"} submitTestId="admin-create-uom-button">
        {modal?.mode === "create" ? (
          <div className="grid gap-2.5" data-testid="admin-uom-form">
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="grid gap-1 text-[11px] font-semibold text-[#3C3C43]">Kode satuan *
                <input data-testid="admin-uom-code-input" className="field" placeholder="mis. PANEL" value={d.code} onChange={(e) => set({ code: e.target.value.toUpperCase() })} /></label>
              <label className="grid gap-1 text-[11px] font-semibold text-[#3C3C43]">Nama satuan *
                <input data-testid="admin-uom-name-input" className="field" placeholder="mis. Panel" value={d.name} onChange={(e) => set({ name: e.target.value })} /></label>
              <label className="grid gap-1 text-[11px] font-semibold text-[#3C3C43]">Dimensi *
                <KNSelect data-testid="admin-uom-base_type-input" className="field" value={d.base_type} placeholder="Pilih dimensi"
                  onValueChange={(v) => set({ base_type: v })}
                  options={(catalog?.dimensions || []).filter((x) => ["length", "weight", "count"].includes(x.value))
                    .map((x) => ({ value: x.value, label: x.label }))} /></label>
              <label className="grid gap-1 text-[11px] font-semibold text-[#3C3C43]">Faktor ke satuan dasar *
                <input data-testid="admin-uom-factor_to_base-input" className="field" type="number" step="any" min="0" placeholder="mis. 0.9144 untuk yard" value={d.factor_to_base} onChange={(e) => set({ factor_to_base: Number(e.target.value) })} /></label>
              <label className="grid gap-1 text-[11px] font-semibold text-[#3C3C43]">Angka desimal
                <input data-testid="admin-uom-precision-input" className="field" type="number" min="0" max="6" value={d.precision} onChange={(e) => set({ precision: Number(e.target.value) })} /></label>
              <label className="grid gap-1 text-[11px] font-semibold text-[#3C3C43]">Alias (dipisah koma)
                <input data-testid="admin-uom-aliases-input" className="field" placeholder="mis. panel, pnl"
                  title="Kata satuan yang tersimpan di dokumen. Tanpa alias, satuan ini tidak akan dikenali dokumen yang sudah ada."
                  value={d.aliases} onChange={(e) => set({ aliases: e.target.value })} /></label>
            </div>
            <label className="flex items-center gap-2 text-[11.5px] text-[#3C3C43]">
              <input data-testid="admin-uom-factor-per-document-input" type="checkbox" checked={!!d.factor_per_document}
                onChange={(e) => set({ factor_per_document: e.target.checked })} />
              Faktor berbeda per dokumen (mis. panjang 1 panel berbeda tiap pesanan)
            </label>
          </div>
        ) : (
          <label className="grid gap-1 text-[11px] font-semibold text-[#3C3C43]">Faktor ke satuan dasar *
            <input data-testid="uom-unit-factor-input" className="field" type="number" step="any" min="0" value={d.factor_to_base}
              onChange={(e) => set({ factor_to_base: e.target.value })} />
          </label>
        )}
      </FormModal>
    </div>
  );
}
