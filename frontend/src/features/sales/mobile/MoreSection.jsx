import { useState } from "react";
import { ChevronDown } from "lucide-react";

const KEY = "kn_m_more_open";
const read = () => { try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch { return {}; } };

/** Kelompok menu Lainnya yang bisa dibuka/tutup; status diingat per perangkat. */
export default function MoreSection({ id, title, count, defaultOpen = false, children }) {
  const [open, setOpen] = useState(() => read()[id] ?? defaultOpen);
  const toggle = () => { const next = !open; setOpen(next); localStorage.setItem(KEY, JSON.stringify({ ...read(), [id]: next })); };
  return (
    <div className="m-card overflow-hidden" data-testid={`mobile-more-section-${id}`}>
      <button type="button" className="m-press flex w-full items-center gap-2 px-4 py-3 text-left" onClick={toggle} aria-expanded={open}
        data-testid={`mobile-more-section-toggle-${id}`}>
        <span className="flex-1 text-[12px] font-bold uppercase tracking-wide text-[#3C3C43]">{title}</span>
        {count != null && <span className="rounded-full bg-[#F2F3F5] px-2 py-0.5 text-[10.5px] font-bold text-[#6B6B73]">{count}</span>}
        <ChevronDown size={16} className={`text-[#8E8E93] transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <div className="border-t border-[#F2F3F5] px-4" data-testid={`mobile-more-section-body-${id}`}>{children}</div>}
    </div>
  );
}
