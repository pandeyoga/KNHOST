/**
 * POCreateMenu — tombol "Buat PO" + menu cara pengadaan (diekstrak dari PurchaseOrderManagement, fase 3 · P5,
 * supaya berkas induk di bawah batas 500 baris). Perilaku & testid sama; menu menutup saat klik di luar / Esc
 * (dulu lapisan `fixed inset-0` tak terlihat — pola pop-up buatan sendiri, INV-UI-11).
 *   onPick("finished") · onPick("buy_process") · onPick("process_only")
 */
import { useEffect, useRef, useState } from "react";
import { Plus, ChevronDown, Boxes, ShoppingBag, GitBranch } from "lucide-react";
import { useEscapeClose } from "@/utils/escapeLayers";

const MODES = [
  { key: "finished", testId: "mode-finished-goods", icon: ShoppingBag, title: "Beli Barang Jadi",
    hint: "Beli putus barang jadi dari supplier (PO standar)." },
  { key: "buy_process", testId: "mode-raw-process", icon: Boxes, title: "Beli Bahan + Proses Makloon",
    hint: "Beli bahan baku lalu kirim langsung ke makloon (barang setengah jadi di mitra)." },
  { key: "process_only", testId: "mode-process-only", icon: GitBranch, title: "Proses Makloon Saja",
    hint: "Bahan dari stok sendiri, kirim ke makloon (sama dengan menu Order Makloon)." },
];

export default function POCreateMenu({ onPick }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  // Esc lewat tumpukan lapisan bersama (INV-UI-10), klik di luar menutup menu.
  useEscapeClose(open, () => setOpen(false));
  useEffect(() => {
    if (!open) return undefined;
    const away = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);
  return (
    <div className="relative" ref={ref}>
      <button data-testid="create-po-button" onClick={() => setOpen((o) => !o)} className="primary-button"
        aria-haspopup="menu" aria-expanded={open}>
        <Plus size={13} /> Buat PO <ChevronDown size={13} />
      </button>
      {open && (
        <div data-testid="procure-mode-menu" role="menu"
          className="absolute right-0 z-30 mt-1 w-72 max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-[#EFF0F2] bg-white py-1 shadow-2xl">
          <p className="px-3 pb-1 pt-1.5 text-[11px] font-bold uppercase tracking-wide text-[#8E8E93]">Cara pengadaan</p>
          {MODES.map(({ key, testId, icon: Icon, title, hint }) => (
            <button key={key} data-testid={testId} role="menuitem" className="flex w-full items-start gap-2.5 px-3 py-2 text-left hover:bg-[#F5F8FF]"
              onClick={() => { setOpen(false); onPick?.(key); }}>
              <Icon size={15} className="mt-0.5 shrink-0 text-[#0058CC]" />
              <span><span className="block text-[12.5px] font-semibold text-[#1B2733]">{title}</span><span className="block text-[11px] text-[#6B6B73]">{hint}</span></span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
