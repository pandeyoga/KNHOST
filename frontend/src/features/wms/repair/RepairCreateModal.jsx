/** UAT 24 Okt (P7) — buat dokumen Perbaikan: pilih roll yang ada, jenis (perbaikan / celup ulang / finishing ulang),
 *  pelaksana (internal / mitra makloon), biaya (tarif per satuan / per roll / borongan + biaya lain). */
import { useEffect, useState } from "react";
import { Plus, Search, Trash2, Wrench } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import FormModal from "../../../components/FormModal";
import KNSelect from "../../../components/KNSelect";
import { formatCurrency, formatQty } from "../../../utils/formatters";

export const KIND_OPTIONS = [
  { value: "perbaikan", label: "Perbaikan cacat" },
  { value: "celup_ulang", label: "Celup ulang (re-dye)" },
  { value: "finishing_ulang", label: "Finishing ulang" },
];
const BASIS_OPTIONS = [{ value: "per_unit", label: "per satuan (yard/meter/kg)" }, { value: "per_roll", label: "per roll" },
  { value: "lumpsum", label: "borongan" }];
const ROLL_STATUS = { available: "tersedia", quarantine: "karantina", damaged: "rusak", blocked: "diblokir", hold: "ditahan" };

export default function RepairCreateModal({ onClose, onCreated, preset = {} }) {
  const [f, setF] = useState({ kind: "perbaikan", partner_type: "internal", partner_id: "", target_color: "", target_dye_lot: "",
    target_product_id: "", notes: "", basis: "per_unit", rate: "", ...preset });
  const [others, setOthers] = useState([]);
  const [q, setQ] = useState("");
  const [cands, setCands] = useState([]);
  const [picked, setPicked] = useState(preset.rolls || []);
  const [makloons, setMakloons] = useState([]);
  const [tq, setTq] = useState("");
  const [targets, setTargets] = useState([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  useEffect(() => { axios.get(`${API}/makloons`, { params: { status: "active" } }).then((r) => setMakloons(r.data || [])).catch(() => setMakloons([])); }, []);
  useEffect(() => {
    const t = setTimeout(() => axios.get(`${API}/repair-orders/candidate-rolls`, { params: { q } })
      .then((r) => setCands(r.data || [])).catch((e) => setErr(e.response?.data?.detail || "Gagal memuat roll.")), 250);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => {
    if (f.kind !== "celup_ulang" || tq.trim().length < 2) { setTargets([]); return undefined; }
    const t = setTimeout(() => axios.get(`${API}/repair-orders/target-products`, { params: { q: tq } }).then((r) => setTargets(r.data || [])).catch(() => {}), 250);
    return () => clearTimeout(t);
  }, [tq, f.kind]);
  const toggle = (r) => setPicked((p) => (p.some((x) => x.id === r.id) ? p.filter((x) => x.id !== r.id) : [...p, r]));
  const qtySum = picked.reduce((s, r) => s + Number(r.length_remaining || 0), 0);
  const rate = Number(f.rate || 0);
  const est = (f.basis === "per_unit" ? rate * qtySum : f.basis === "per_roll" ? rate * picked.length : rate)
    + others.reduce((s, o) => s + Number(o.amount || 0), 0);
  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const r = await axios.post(`${API}/repair-orders`, {
        kind: f.kind, partner_type: f.partner_type, partner_id: f.partner_id, roll_ids: picked.map((x) => x.id),
        cost: { basis: f.basis, rate, other_costs: others.filter((o) => Number(o.amount) > 0).map((o) => ({ label: o.label, amount: Number(o.amount) })) },
        target_color: f.target_color, target_dye_lot: f.target_dye_lot, target_product_id: f.target_product_id, notes: f.notes,
        source_type: preset.source_type || "", source_id: preset.source_id || "" });
      onCreated?.(r.data);
    } catch (e) { setErr(e.response?.data?.detail || "Gagal membuat dokumen perbaikan."); } finally { setBusy(false); }
  };
  return (
    <FormModal open onClose={onClose} title="Perbaikan baru" subtitle="Roll yang dipilih keluar dari stok jual saat dikirim, kembali saat diterima"
      icon={Wrench} testId="repair-create" size="lg" onSubmit={submit} submitLabel="Buat dokumen (Draf)" busy={busy} submitDisabled={!picked.length} error={err}>
      <div className="grid gap-3 sm:grid-cols-2">
        <label><span className="field-label">Jenis</span>
          <KNSelect data-testid="repair-kind" className="field" value={f.kind} options={KIND_OPTIONS} searchable={false} onValueChange={(v) => set("kind", v)} /></label>
        <label><span className="field-label">Pelaksana</span>
          <KNSelect data-testid="repair-partner-type" className="field" value={f.partner_type} searchable={false} onValueChange={(v) => set("partner_type", v)}
            options={[{ value: "internal", label: "Internal (gudang / produksi sendiri)" }, { value: "makloon", label: "Mitra makloon" }]} /></label>
        {f.partner_type === "makloon" && (
          <label className="sm:col-span-2"><span className="field-label">Mitra makloon *</span>
            <KNSelect data-testid="repair-partner" className="field" value={f.partner_id} searchable onValueChange={(v) => set("partner_id", v)}
              options={makloons.map((m) => ({ value: m.id, label: m.name }))} placeholder="Pilih mitra" /></label>
        )}
        {f.kind === "celup_ulang" && (<>
          <label><span className="field-label">Warna tujuan *</span>
            <input className="field" data-testid="repair-target-color" value={f.target_color} onChange={(e) => set("target_color", e.target.value)} placeholder="mis. Navy 19-4052" /></label>
          <label><span className="field-label">Dye lot baru</span>
            <input className="field" data-testid="repair-target-lot" value={f.target_dye_lot} onChange={(e) => set("target_dye_lot", e.target.value)} placeholder="boleh diisi saat terima" /></label>
          <label className="sm:col-span-2"><span className="field-label">SKU tujuan (bila warna berganti → roll anak ber-SKU baru)</span>
            <input className="field" data-testid="repair-target-search" value={tq} onChange={(e) => { setTq(e.target.value); set("target_product_id", ""); }} placeholder="ketik kode/nama SKU (kosong = SKU sama)" />
            {targets.length > 0 && !f.target_product_id && (
              <span className="mt-1 flex flex-wrap gap-1">{targets.map((t) => (
                <button key={t.id} type="button" className="rounded-full border border-[#D9D9DE] px-2 py-0.5 text-[10.5px] hover:border-[#0058CC]"
                  onClick={() => { set("target_product_id", t.id); setTq(t.sku); }}>{t.sku}</button>))}</span>)}
          </label>
        </>)}
      </div>
      <div className="mt-3">
        <span className="field-label">Roll yang dikirim * ({picked.length} dipilih · {formatQty(qtySum)})</span>
        <div className="search-box"><Search size={14} /><input data-testid="repair-roll-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="cari nomor roll / SKU / lot" /></div>
        <div className="mt-1 max-h-56 overflow-y-auto rounded-lg border border-[#EFF0F2]" data-testid="repair-roll-candidates">
          {cands.length === 0 ? <p className="p-3 text-[11px] text-[#8E8E93]">Tidak ada roll yang bisa dikirim (roll harus milik PT ini, di gudang, tidak dicadangkan).</p> : cands.map((r) => (
            <label key={r.id} className="flex items-center gap-2 border-b border-[#F2F2F5] px-2 py-1.5 text-[11.5px] last:border-0">
              <input type="checkbox" checked={picked.some((x) => x.id === r.id)} onChange={() => toggle(r)} data-testid={`repair-roll-${r.id}`} />
              <span className="font-mono font-semibold">{r.roll_no}</span>
              <span className="min-w-0 flex-1 truncate">{r.sku} · {r.product_name}</span>
              <span className="tabular-nums">{formatQty(r.length_remaining)} {r.unit}</span>
              <span className="rounded bg-[#F1F2F4] px-1.5 text-[10px]">{ROLL_STATUS[r.status] || r.status} · {r.grade || "-"}</span>
            </label>))}
        </div>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <label><span className="field-label">Dasar biaya</span>
          <KNSelect data-testid="repair-basis" className="field" value={f.basis} options={BASIS_OPTIONS} searchable={false} onValueChange={(v) => set("basis", v)} /></label>
        <label><span className="field-label">Tarif (Rp)</span>
          <input type="number" min="0" className="field" data-testid="repair-rate" value={f.rate} onChange={(e) => set("rate", e.target.value)} /></label>
        <div><span className="field-label">Perkiraan biaya</span><p className="py-1.5 text-[13px] font-bold tabular-nums" data-testid="repair-estimate">{formatCurrency(est)}</p></div>
      </div>
      <div className="mt-2 space-y-1.5">
        {others.map((o, i) => (
          <div key={i} className="flex gap-2">
            <input className="field" value={o.label} onChange={(e) => setOthers((xs) => xs.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))} placeholder="mis. ongkos kirim" />
            <input type="number" min="0" className="field !w-40" value={o.amount} onChange={(e) => setOthers((xs) => xs.map((x, j) => (j === i ? { ...x, amount: e.target.value } : x)))} />
            <button type="button" aria-label="Hapus biaya" onClick={() => setOthers((xs) => xs.filter((_, j) => j !== i))}><Trash2 size={14} className="text-[#A8221A]" /></button>
          </div>))}
        <button type="button" className="link-button text-[11.5px]" onClick={() => setOthers((xs) => [...xs, { label: "Ongkos kirim", amount: "" }])} data-testid="repair-add-cost"><Plus size={12} /> Biaya lain</button>
      </div>
      <label className="mt-2 block"><span className="field-label">Catatan</span>
        <textarea className="field min-h-16" value={f.notes} onChange={(e) => set("notes", e.target.value)} data-testid="repair-notes" placeholder="cacat apa, permintaan khusus ke mitra…" /></label>
      <p className="mt-1 text-[10.5px] text-[#6B6B73]">Biaya dikapitalisasi ke nilai roll hasil saat diterima; tagihan mitra dicatat lewat Tagihan Supplier.</p>
    </FormModal>
  );
}
