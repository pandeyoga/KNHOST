/** Dualisme nama & warna: versi KN (ERP) + versi SUPPLIER — dipakai di baris PR/PO/GRN & R&D. */
export function supplierAliasText(it) {
  const name = it?.supplier_item_name || it?.supplier_alias?.name || "";
  const color = it?.supplier_color || it?.supplier_alias?.color || "";
  return [name, color && `warna ${color}`].filter(Boolean).join(" · ");
}

export function DualName({ item, name, testId, className = "" }) {
  const kn = name ?? (item?.product_name || item?.name || item?.description || "");
  const knColor = item?.kn_color || item?.color_name || "";
  const sup = supplierAliasText(item);
  return (
    <div className={`min-w-0 ${className}`} data-testid={testId}>
      <p className="truncate text-[12px] font-semibold text-[#1C1C1E]" title={kn}>
        <span className="mr-1 rounded bg-[#EEF4FF] px-1 text-[9.5px] font-bold text-[#0058CC]">KN</span>{kn}
        {knColor && !kn.includes(knColor) ? <span className="font-normal text-[#6B6B73]"> · warna {knColor}</span> : null}
      </p>
      <p className="truncate text-[11px] text-[#6B6B73]" title={sup || "Nama versi supplier belum diisi"}>
        <span className="mr-1 rounded bg-[#FFF4E5] px-1 text-[9.5px] font-bold text-[#8C4A00]">SUP</span>
        {sup || <span className="italic text-[#B4B4BB]">nama versi supplier belum diisi</span>}
      </p>
    </div>
  );
}
