import { Sparkles } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger } from "./ui/dropdown-menu";

const AI_ROLES = ["admin", "manager", "sales_admin", "finance", "md", "warehouse_admin", "sales"];
export const PENDING_KEY = "kn_tanya_pending";

const PRESETS = {
  customer: ["Kenapa penjualan pelanggan ini naik/turun 3 bulan terakhir?", "Berapa piutang pelanggan ini dan mana yang lewat jatuh tempo?", "Produk apa yang paling sering dibeli pelanggan ini?", "Seberapa besar risiko pelanggan ini berhenti order?"],
  product: ["Bagaimana tren penjualan produk ini 12 minggu terakhir?", "Berapa perkiraan kebutuhan produk ini 6 minggu ke depan dan perlu pesan ulang berapa?", "Siapa pelanggan terbesar produk ini?"],
  sales_order: ["Pesanan ini tertahan di mana dan apa yang perlu dilakukan?", "Bagaimana status pembayaran pesanan ini?"],
  purchase_order: ["PO ini sudah sampai tahap apa dan apakah terlambat?", "Bagaimana performa tepat waktu supplier PO ini?"],
  goods_receipt: ["Apa saja selisih penerimaan ini dibanding surat jalan?", "Bagaimana riwayat selisih & QC supplier penerimaan ini?"],
};

function canAsk() {
  try { return AI_ROLES.includes(JSON.parse(localStorage.getItem("kn_user") || "null")?.role); } catch { return false; }
}

/** Tombol "Tanya KN" di halaman detail: membuka asisten dengan konteks halaman ini. */
export function AskKnButton({ type, id, label, className = "secondary-button" }) {
  if (!id || !canAsk()) return null;
  const go = (question) => {
    sessionStorage.setItem(PENDING_KEY, JSON.stringify({ question, context: { type, id, label: label || id } }));
    const ent = new URLSearchParams(window.location.search).get("entity");
    window.location.assign(`/?view=tanya-kn${ent ? `&entity=${encodeURIComponent(ent)}` : ""}&tab=chat`);
  };
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" className={className} data-testid={`ask-kn-${type}`}><Sparkles size={13} /> Tanya KN</button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="max-w-[320px]">
        <DropdownMenuLabel className="text-[11px]">Tanyakan tentang {label || id}</DropdownMenuLabel>
        {(PRESETS[type] || []).map((q, i) => (
          <DropdownMenuItem key={i} className="text-[12px]" onSelect={() => go(q)} data-testid={`ask-kn-${type}-q-${i}`}>{q}</DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
