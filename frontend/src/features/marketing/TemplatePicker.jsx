/** TemplatePicker — pilih template konten untuk mengisi form post baru; hapus template milik sendiri. */
import { useEffect, useState } from "react";
import { LayoutTemplate, Trash2 } from "lucide-react";
import { KNSelect } from "../../components/KNSelect";
import { askConfirm } from "@/services/confirmService";
import { mktApi } from "./marketingShared";

export default function TemplatePicker({ value, onApply, currentUser }) {
  const [rows, setRows] = useState([]);
  const load = () => mktApi.templates().then(setRows).catch(() => setRows([]));
  useEffect(() => { load(); }, []);
  const cur = rows.find((t) => t.id === value);
  const canDelete = cur && (["admin", "manager"].includes(currentUser?.role) || cur.created_by_id === currentUser?.id);

  const remove = async () => {
    const ok = await askConfirm({ title: `Hapus template "${cur.name}"?`, danger: true, testId: "mkt-template-delete-confirm" });
    if (!ok) return;
    await mktApi.deleteTemplate(cur.id);
    onApply(null);
    load();
  };

  if (!rows.length) return <p className="text-[10.5px] text-[#8E8E93]" data-testid="mkt-template-empty"><LayoutTemplate size={11} className="mr-1 inline" />Belum ada template — buka rincian konten lalu "Simpan sebagai template".</p>;
  return (
    <div className="flex items-center gap-2 rounded-lg border border-dashed border-[#C7D2FE] bg-[#F5F7FF] px-2.5 py-1.5" data-testid="mkt-template-picker">
      <LayoutTemplate size={13} className="shrink-0 text-[#3730A3]" />
      <span className="shrink-0 text-[11px] font-semibold text-[#3730A3]">Mulai dari template</span>
      <KNSelect data-testid="mkt-template-select" className="field !w-full" value={value || ""}
        onValueChange={(v) => onApply(rows.find((t) => t.id === v) || null)}
        options={[{ value: "", label: "— kosong —" }, ...rows.map((t) => ({ value: t.id, label: `${t.name}${t.used_count ? ` · dipakai ${t.used_count}×` : ""}` }))]} />
      {canDelete && <button type="button" onClick={remove} className="shrink-0 rounded-full p-1 text-[#C0392B] hover:bg-white" title="Hapus template" data-testid="mkt-template-delete"><Trash2 size={12} /></button>}
    </div>
  );
}
