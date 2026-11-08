/**
 * WarehouseGateSection (PREP-C · K-GDG-01, K-RFID-04) — gate per gedung: punya gate atau tidak, mode konfirmasi
 * gerak (gate/handheld), pasangan gate IN/OUT (perangkat dari Pengaturan RFID), tata letak pasangan & catatan
 * clear zone (masih terbuka — diisi bila sudah diukur). Gedung tanpa gate = handheld.
 */
import { Plus, Trash2, DoorOpen } from "lucide-react";
import KNSelect from "../../../components/KNSelect";
import { CONFIRM_MODES, GATE_LAYOUTS, needsArbitration } from "./warehouseProfileUtils";

export default function WarehouseGateSection({ gate, setGate, devices = [], quantityMode = false }) {
  const ins = devices.filter((d) => d.direction !== "out");
  const outs = devices.filter((d) => d.direction !== "in");
  const devOpts = (rows) => [{ value: "", label: "— belum tertaut —" },
    ...rows.map((d) => ({ value: d.id, label: `${d.code} · ${d.name || ""}`.trim() }))];
  const setPair = (i, patch) => setGate({ ...gate, pairs: gate.pairs.map((p, j) => (j === i ? { ...p, ...patch } : p)) });
  const addPair = () => setGate({ ...gate, pairs: [...gate.pairs, { id: "", name: `Gate ${gate.pairs.length + 1}`,
    in_device_id: "", out_device_id: "", layout: "", clear_zone_note: "" }] });

  return (
    <section data-testid="wh-profile-gate">
      <p className="mb-1 flex items-center gap-1 text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]"><DoorOpen size={12} /> Gate RFID & konfirmasi gerak</p>
      {quantityMode && (
        <p data-testid="wh-profile-gate-na" className="mb-1.5 rounded bg-[#FFF4E5] px-2 py-1 text-[11px] font-semibold text-[#8C4A00]">
          Gedung mode kuantitas tanpa tag — gate & handheld RFID tidak berlaku. Pengaturan di bawah disimpan untuk nanti.
        </p>
      )}
      <button type="button" data-testid="wh-profile-gate-toggle"
        onClick={() => setGate({ ...gate, has_gate: !gate.has_gate, confirm_mode: gate.has_gate ? "handheld" : "gate" })}
        className={`w-full rounded-md border px-3 py-2 text-left text-[12px] ${
          gate.has_gate ? "border-[#1B7F4B] bg-[#E6F6EC]" : "border-[#E5E5EA] bg-white"}`}>
        <span className="block font-bold">{gate.has_gate ? "Punya gate fisik (IN & OUT)" : "Tanpa gate fisik — handheld saja"}</span>
        <span className="block text-[10.5px] text-[#6B6B73]">
          {gate.has_gate ? "Lintasan gate mencatat gerak; handheld menjadi cadangan untuk tag tak terbaca."
            : "Gerak barang dikonfirmasi lewat scan handheld (mis. Gudang Jakarta)."}
        </span>
      </button>
      {gate.has_gate && (
        <div className="mt-2 space-y-2">
          <label className="block text-[10.5px] font-semibold uppercase text-[#6B6B73]">Mode konfirmasi gerak
            <KNSelect data-testid="wh-profile-confirm-mode" value={gate.confirm_mode} options={CONFIRM_MODES}
              onValueChange={(v) => setGate({ ...gate, confirm_mode: v })} className="field mt-0.5 text-[12px]" />
          </label>
          {gate.pairs.map((p, i) => (
            <div key={p.id || `new-${i}`} data-testid={`wh-gate-pair-${i}`} className="space-y-1.5 rounded-md border border-[#E5E5EA] p-2">
              <div className="flex items-center gap-2">
                <input data-testid={`wh-gate-pair-name-${i}`} className="field flex-1 !py-1 text-[12px]" value={p.name}
                  onChange={(e) => setPair(i, { name: e.target.value })} aria-label="Nama pasangan gate" />
                <button type="button" data-testid={`wh-gate-pair-del-${i}`} aria-label="Hapus pasangan gate"
                  onClick={() => setGate({ ...gate, pairs: gate.pairs.filter((_, j) => j !== i) })}
                  className="rounded p-1 text-[#C0341D] hover:bg-[#FBE9E7]"><Trash2 size={13} /></button>
              </div>
              <div className="grid grid-cols-2 gap-1.5">
                <KNSelect data-testid={`wh-gate-pair-in-${i}`} value={p.in_device_id} options={devOpts(ins)}
                  onValueChange={(v) => setPair(i, { in_device_id: v })} className="field !py-1 text-[11.5px]" placeholder="Gate IN" />
                <KNSelect data-testid={`wh-gate-pair-out-${i}`} value={p.out_device_id} options={devOpts(outs)}
                  onValueChange={(v) => setPair(i, { out_device_id: v })} className="field !py-1 text-[11.5px]" placeholder="Gate OUT" />
              </div>
              <KNSelect data-testid={`wh-gate-pair-layout-${i}`} value={p.layout} options={GATE_LAYOUTS}
                onValueChange={(v) => setPair(i, { layout: v })} className="field !py-1 text-[11.5px]" />
              <input data-testid={`wh-gate-pair-note-${i}`} className="field w-full !py-1 text-[11.5px]" maxLength={300}
                value={p.clear_zone_note} onChange={(e) => setPair(i, { clear_zone_note: e.target.value })}
                placeholder="Catatan clear zone / jarak rak terdekat (opsional)" />
            </div>
          ))}
          <button type="button" data-testid="wh-gate-pair-add" onClick={addPair}
            className="flex items-center gap-1 text-[12px] font-semibold text-[#0058CC] hover:underline"><Plus size={13} /> Tambah pasangan gate</button>
          {!devices.length && (
            <p className="text-[10.5px] text-[#8E8E93]">Belum ada reader gate terdaftar di gedung ini — daftarkan di Pengaturan RFID → Perangkat.</p>
          )}
          {needsArbitration(gate) && (
            <p data-testid="wh-gate-arbitration" className="rounded bg-[#EAF2FF] px-2 py-1 text-[10.5px] text-[#0058CC]">
              Pasangan IN/OUT berdampingan butuh aturan penengah antar-gate; efek sekat wajib dibuktikan uji lapangan.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
