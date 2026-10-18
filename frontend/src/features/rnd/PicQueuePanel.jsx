/** L03 LN-034 — antrean "Menunggu keputusan PIC": uji ulang GAGAL yang belum diputus tindak lanjutnya. */
import { useEffect, useState } from "react";
import { Gavel } from "lucide-react";
import { picQueue } from "./rndApi";

export default function PicQueuePanel({ refreshKey, onOpen }) {
  const [items, setItems] = useState(null);
  useEffect(() => {
    picQueue().then((r) => setItems(r?.items || [])).catch(() => setItems(null));
  }, [refreshKey]);
  if (!items) return null;
  return (
    <div className="section-card section-pad" data-testid="pic-queue-panel">
      <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-[#C0392B]">
        <Gavel size={13} /> Menunggu keputusan PIC <span className="rounded-full bg-[#FDEDE7] px-1.5 tabular-nums" data-testid="pic-queue-count">{items.length}</span>
      </p>
      {items.length === 0 ? (
        <p className="mt-1 text-[11px] text-[#8E8E93]" data-testid="pic-queue-empty">Tidak ada uji ulang gagal yang menunggu keputusan.</p>
      ) : (
        <ul className="mt-1.5 divide-y divide-[#F2F3F5]">
          {items.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center gap-2 py-1.5 text-[11.5px]" data-testid={`pic-queue-row-${s.id}`}>
              <b>{s.number}</b>
              <span className="font-mono text-[10.5px]">{s.product_sku}</span>
              <span>{s.revalidation?.supplier_name}</span>
              <span className="text-[10.5px] text-[#6B6B73]">siklus {s.revalidation?.cycle_no} · {(s.sample_types || []).join("+")}</span>
              <span className="line-clamp-1 max-w-[260px] text-[10.5px] text-[#A8221A]">{s.decision?.note}</span>
              <button className="link-button ml-auto" data-testid={`pic-queue-open-${s.id}`} onClick={() => onOpen(s.id)}>Buka</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
