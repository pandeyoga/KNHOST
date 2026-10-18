import { Plus, Trash2, Save, MapPin, Layers } from "lucide-react";
import NodeRulesEditor from "./NodeRulesEditor";
import { TERMS, uid, fmtUnits } from "./locUtils";

// Editor pohon Zona → Lemari/Rak → Tingkat → Bin. ID node dipertahankan saat ganti nama/pindah.
export default function StructureEditor({ zones, setZones, occByBin, canEdit, saving, onSave }) {
  const update = (fn) => setZones((prev) => { const n = JSON.parse(JSON.stringify(prev)); fn(n); return n; });
  const addZone = () => update((n) => n.push({ id: uid("zone"), name: `${TERMS.zone} ${String.fromCharCode(65 + n.length)}`, racks: [] }));
  return (
    <div className="space-y-3" data-testid="lp-structure-editor">
      <div className="flex flex-wrap justify-between items-center gap-2">
        <p className="text-[11.5px] text-[#6B6B73]">
          {canEdit ? "Kapasitas = jumlah roll per bin. Kosong = belum diatur (tanpa batas)." : "Hanya Admin Gudang, Manajer, atau Admin yang dapat mengubah struktur & kapasitas."}
        </p>
        {canEdit && (
          <div className="flex gap-2">
            <button data-testid="lp-add-zone" onClick={addZone}
              className="flex items-center gap-1 text-[12px] font-semibold text-[#0058CC] hover:underline"><Plus size={14} /> Tambah {TERMS.zone}</button>
            <button data-testid="lp-save-structure" onClick={onSave} disabled={saving}
              className="flex items-center gap-1 rounded-lg bg-[#0058CC] text-white px-4 py-1.5 text-[12px] font-semibold disabled:opacity-50 transition-opacity">
              <Save size={14} /> {saving ? "Menyimpan…" : "Simpan Struktur"}
            </button>
          </div>
        )}
      </div>
      {zones.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-10 text-center text-[12px] text-[#6B6B73]"><MapPin size={22} className="text-[#8E8E93]" />Belum ada zona.</div>
      ) : zones.map((z, zi) => (
        <div key={z.id} data-testid={`lp-zone-${zi}`} className="rounded-xl border border-[#EFF0F2] bg-white p-3">
          <NodeRow node={z} kind="zone" depthLabel={TERMS.zone} canEdit={canEdit} testId={`lp-zone-${zi}`}
            onChange={(v) => update((n) => { n[zi] = { ...n[zi], ...v }; })} onDelete={() => update((n) => n.splice(zi, 1))}
            onAdd={() => update((n) => n[zi].racks.push({ id: uid("rack"), name: `${TERMS.rack} ${n[zi].racks.length + 1}`, levels: [] }))} addLabel={TERMS.rack} />
          <div className="pl-3 mt-2 space-y-2 border-l-2 border-[#F0F0F2]">
            {(z.racks || []).map((r, ri) => (
              <div key={r.id} className="rounded-lg bg-[#FAFAFB] p-2">
                <NodeRow node={r} kind="rack" depthLabel={TERMS.rack} canEdit={canEdit} testId={`lp-rack-${zi}-${ri}`}
                  onChange={(v) => update((n) => { n[zi].racks[ri] = { ...n[zi].racks[ri], ...v }; })}
                  onDelete={() => update((n) => n[zi].racks.splice(ri, 1))}
                  onAdd={() => update((n) => n[zi].racks[ri].levels.push({ id: uid("level"), name: `${TERMS.level} ${n[zi].racks[ri].levels.length + 1}`, bins: [] }))} addLabel={TERMS.level} />
                <div className="pl-3 mt-1 space-y-1.5">
                  {(r.levels || []).map((l, li) => (
                    <LevelBlock key={l.id} level={l} path={[zi, ri, li]} update={update} occByBin={occByBin} canEdit={canEdit} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function LevelBlock({ level, path: [zi, ri, li], update, occByBin, canEdit }) {
  const lv = (n) => n[zi].racks[ri].levels[li];
  return (
    <div className="rounded bg-white border border-[#EFF0F2] p-2">
      <NodeRow node={level} kind="level" depthLabel={TERMS.level} canEdit={canEdit} testId={`lp-level-${zi}-${ri}-${li}`} icon={Layers}
        onChange={(v) => update((n) => { n[zi].racks[ri].levels[li] = { ...lv(n), ...v }; })}
        onDelete={() => update((n) => n[zi].racks[ri].levels.splice(li, 1))}
        onAdd={() => update((n) => lv(n).bins.push({ id: uid("bin"), code: `BIN-${uid("").slice(-4).toUpperCase()}`, capacity_rolls: null }))} addLabel={TERMS.bin} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-1.5 pl-3 mt-1">
        {(level.bins || []).map((b, bi) => (
          <BinRow key={b.id} bin={b} occ={occByBin[b.id]} canEdit={canEdit} testId={`lp-bin-${b.id}`}
            onChange={(v) => update((n) => { lv(n).bins[bi] = { ...lv(n).bins[bi], ...v }; })}
            onDelete={() => update((n) => lv(n).bins.splice(bi, 1))} />
        ))}
      </div>
    </div>
  );
}

function NodeRow({ node, depthLabel, canEdit, testId, onChange, onDelete, onAdd, addLabel, icon: Icon }) {
  return (
    <div className="flex flex-wrap items-start gap-2">
      <span className="mt-0.5 rounded bg-[#F0F0F2] px-1.5 py-0.5 text-[9.5px] font-bold uppercase text-[#6B6B73]">{Icon ? <Icon size={10} className="inline mr-0.5" /> : null}{depthLabel}</span>
      <input value={node.name || ""} disabled={!canEdit} onChange={(e) => onChange({ name: e.target.value })} data-testid={`${testId}-name`}
        className="font-semibold text-[12.5px] bg-transparent outline-none border-b border-transparent focus:border-[#0058CC] min-w-[140px]" />
      <NodeRulesEditor node={node} testId={testId} onChange={(v) => canEdit && onChange({ function: v.function, rules: v.rules })} />
      {canEdit && <button data-testid={`${testId}-add`} onClick={onAdd} className="text-[11px] text-[#0058CC] font-semibold hover:underline flex items-center gap-0.5"><Plus size={11} /> {addLabel}</button>}
      {canEdit && <button data-testid={`${testId}-delete`} onClick={onDelete} className="ml-auto text-[#C0341D] hover:bg-[#FBE9E7] rounded p-1"><Trash2 size={12} /></button>}
    </div>
  );
}

function BinRow({ bin, occ, canEdit, testId, onChange, onDelete }) {
  return (
    <div data-testid={testId} className="flex flex-wrap items-center gap-2 rounded bg-[#F5F5F7] px-2 py-1">
      <input value={bin.code || ""} disabled={!canEdit} onChange={(e) => onChange({ code: e.target.value })} data-testid={`${testId}-code`}
        placeholder="Kode Bin" className="text-[11px] font-mono font-semibold bg-transparent outline-none w-28 border-b border-transparent focus:border-[#0058CC]" />
      <label className="text-[10px] text-[#8E8E93] flex items-center gap-1">kap.
        <input type="number" min="0" disabled={!canEdit} value={bin.capacity_rolls || ""} placeholder="—" data-testid={`${testId}-capacity`}
          onChange={(e) => onChange({ capacity_rolls: e.target.value === "" ? null : Math.max(0, parseInt(e.target.value, 10) || 0) })}
          className="text-[11px] tabular-nums bg-white rounded w-14 px-1 border border-[#E5E5EA] outline-none" /> roll
      </label>
      <span className="text-[10px] text-[#6B6B73]" data-testid={`${testId}-occupied`}>{occ ? `${occ.roll_count} roll · ${fmtUnits(occ.occupied_by_unit)}` : "kosong"}</span>
      <NodeRulesEditor node={bin} testId={testId} onChange={(v) => canEdit && onChange({ function: v.function, rules: v.rules })} />
      {canEdit && <button data-testid={`${testId}-delete`} onClick={onDelete} className="ml-auto text-[#C0341D] hover:bg-[#FBE9E7] rounded p-0.5"><Trash2 size={11} /></button>}
    </div>
  );
}
