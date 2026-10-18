import { Plus, X, Brackets } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import KNDatePicker from "../../components/KNDatePicker";

const TYPE_CMPS = {
  string: ["eq", "ne", "contains", "not_contains", "starts", "in", "empty", "not_empty"],
  number: ["eq", "ne", "gt", "gte", "lt", "lte", "empty", "not_empty"],
  money: ["eq", "ne", "gt", "gte", "lt", "lte", "empty", "not_empty"],
  date: ["eq", "gt", "gte", "lt", "lte", "empty", "not_empty"],
  datetime: ["gt", "gte", "lt", "lte", "empty", "not_empty"],
  bool: ["eq"],
};
export const emptyGroup = (op = "and") => ({ op, items: [] });

function Condition({ node, cols, labels, onChange, onRemove, path }) {
  const col = cols.find((c) => c.key === node.field) || cols[0];
  const cmps = TYPE_CMPS[col?.type] || TYPE_CMPS.string;
  const noValue = ["empty", "not_empty"].includes(node.cmp);
  return (
    <div data-testid={`export-cond-${path}`} className="flex flex-wrap items-center gap-1.5">
      <div className="w-48"><KNSelect data-testid={`export-cond-field-${path}`} value={node.field}
        options={cols.map((c) => ({ value: c.key, label: c.label }))}
        onValueChange={(v) => onChange({ ...node, field: v, cmp: (TYPE_CMPS[cols.find((c) => c.key === v)?.type] || ["eq"])[0] })} /></div>
      <div className="w-36"><KNSelect data-testid={`export-cond-cmp-${path}`} value={node.cmp} searchable={false}
        options={cmps.map((c) => ({ value: c, label: labels[c] || c }))} onValueChange={(v) => onChange({ ...node, cmp: v })} /></div>
      {!noValue && (col?.type === "bool"
        ? <div className="w-28"><KNSelect data-testid={`export-cond-value-${path}`} value={String(node.value ?? "true")} searchable={false}
            options={[{ value: "true", label: "Ya" }, { value: "false", label: "Tidak" }]} onValueChange={(v) => onChange({ ...node, value: v })} /></div>
        : ["date", "datetime"].includes(col?.type)
        ? <KNDatePicker data-testid={`export-cond-value-${path}`} value={node.value || ""} onChange={(v) => onChange({ ...node, value: v || "" })} />
        : <input data-testid={`export-cond-value-${path}`} className="field w-44 text-[12.5px]" value={node.value ?? ""}
                 type={["number", "money"].includes(col?.type) ? "number" : "text"}
                 placeholder={node.cmp === "in" ? "nilai1, nilai2" : "nilai"} onChange={(e) => onChange({ ...node, value: e.target.value })} />)}
      <button type="button" data-testid={`export-cond-remove-${path}`} onClick={onRemove} className="p-1 text-[#8E8E93] hover:text-[#C0341D]"><X size={14} /></button>
    </div>
  );
}

export default function FilterGroup({ node, cols, labels, onChange, onRemove, depth = 0, path = "0" }) {
  const set = (i, child) => onChange({ ...node, items: node.items.map((x, j) => (j === i ? child : x)) });
  const drop = (i) => onChange({ ...node, items: node.items.filter((_, j) => j !== i) });
  const addCond = () => onChange({ ...node, items: [...node.items, { field: cols[0]?.key, cmp: "eq", value: "" }] });
  const addGroup = () => onChange({ ...node, items: [...node.items, emptyGroup(node.op === "and" ? "or" : "and")] });
  return (
    <div data-testid={`export-group-${path}`}
         className={`space-y-2 ${depth ? "rounded-lg border border-dashed border-[#D0D0D5] bg-[#FAFAFB] p-2.5" : ""}`}>
      <div className="flex items-center gap-2 text-[12px]">
        {depth > 0 && <span className="font-mono text-[#8E8E93]">(</span>}
        <span className="text-[#6B6B73]">Gabungkan dengan</span>
        {["and", "or"].map((op) => (
          <button key={op} type="button" data-testid={`export-group-op-${path}-${op}`} onClick={() => onChange({ ...node, op })}
                  className={`px-2 py-0.5 rounded-md font-bold text-[11px] ${node.op === op ? "bg-[#0058CC] text-white" : "bg-[#F0F0F3] text-[#3A3A3C]"}`}>
            {op === "and" ? "DAN" : "ATAU"}
          </button>
        ))}
        {onRemove && <button type="button" data-testid={`export-group-remove-${path}`} onClick={onRemove}
                             className="ml-auto text-[11px] text-[#C0341D] font-semibold">Hapus kurung</button>}
      </div>
      {node.items.map((it, i) => (it.items
        ? <FilterGroup key={i} node={it} cols={cols} labels={labels} depth={depth + 1} path={`${path}-${i}`}
                       onChange={(c) => set(i, c)} onRemove={() => drop(i)} />
        : <Condition key={i} node={it} cols={cols} labels={labels} path={`${path}-${i}`} onChange={(c) => set(i, c)} onRemove={() => drop(i)} />))}
      <div className="flex gap-3 text-[12px]">
        <button type="button" data-testid={`export-add-cond-${path}`} onClick={addCond} disabled={!cols.length}
                className="inline-flex items-center gap-1 text-[#0058CC] font-semibold"><Plus size={13} /> Kondisi</button>
        {depth < 3 && <button type="button" data-testid={`export-add-group-${path}`} onClick={addGroup}
                className="inline-flex items-center gap-1 text-[#0058CC] font-semibold"><Brackets size={13} /> Kurung</button>}
      </div>
    </div>
  );
}
