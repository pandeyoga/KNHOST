import { useState } from "react";
import { ChevronDown, Crop, Focus, Layers, MessageCircleOff, ScanLine, SunMedium } from "lucide-react";

const TIPS = [
  [ScanLine, "Kamera tegak lurus di atas kertas", "Pegang ponsel sejajar kertas, jangan miring dari samping."],
  [Crop, "Seluruh kertas masuk bingkai", "Kop, nomor SJ, tabel barang, total, dan tanda tangan harus terlihat."],
  [SunMedium, "Terang merata", "Hindari bayangan tangan dan pantulan lampu di atas kertas karbon."],
  [Focus, "Tunggu sampai tajam", "Ketuk layar di tabel angka, tahan ponsel diam 1 detik, baru potret."],
  [MessageCircleOff, "Jangan pakai foto dari WhatsApp", "WhatsApp mengecilkan foto sehingga angka sering salah baca. Foto langsung dari sini."],
  [Layers, "Satu halaman per foto", "SJ dan packing list boleh beberapa foto; urutkan sesuai halaman."],
];
const KEY = "kn.grn.photoTips.collapsed";

/** Tips singkat sebelum memotret surat jalan — foto lurus & tajam = hasil baca otomatis lebih tepat. */
export default function GrnPhotoTips() {
  const [open, setOpen] = useState(() => localStorage.getItem(KEY) !== "1");
  const toggle = () => setOpen((o) => { localStorage.setItem(KEY, o ? "1" : "0"); return !o; });
  return (
    <div data-testid="grn-photo-tips" className="rounded-xl border border-[#D8E6FF] bg-[#F7FAFF]">
      <button type="button" data-testid="grn-photo-tips-toggle" onClick={toggle} className="flex w-full items-center justify-between px-3 py-2 text-left">
        <span className="text-[11.5px] font-bold text-[#0B3B8C]">Tips foto surat jalan agar terbaca tepat</span>
        <ChevronDown size={14} className={`text-[#0B3B8C] transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <ul className="grid gap-2 px-3 pb-3 sm:grid-cols-2" data-testid="grn-photo-tips-list">
          {TIPS.map(([Icon, title, body], i) => (
            <li key={title} data-testid={`grn-photo-tip-${i}`} className="flex gap-2 rounded-lg bg-white p-2 shadow-[0_1px_0_#E8EEF8]">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#EAF1FF] text-[#0058CC]"><Icon size={14} /></span>
              <span className="text-[10.5px] leading-snug text-[#3C3C43]"><b className="block text-[11px] text-[#1C1C1E]">{title}</b>{body}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
