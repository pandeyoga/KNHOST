import { PenLine, Sparkles } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "./ui/dropdown-menu";

const AI_ROLES = ["admin", "manager", "sales_admin", "finance", "md", "warehouse_admin", "sales"];
export const PENDING_KEY = "kn_tanya_pending";

const PRESETS = {
  customer: ["Kenapa penjualan pelanggan ini naik/turun 3 bulan terakhir?", "Berapa piutang pelanggan ini dan mana yang lewat jatuh tempo?", "Produk apa yang paling sering dibeli pelanggan ini 12 bulan terakhir?", "Seberapa besar risiko pelanggan ini berhenti order?"],
  product: ["Bagaimana tren penjualan produk ini 12 minggu terakhir?", "Berapa perkiraan kebutuhan produk ini 6 minggu ke depan dan perlu pesan ulang berapa?", "Siapa pelanggan terbesar produk ini 12 bulan terakhir?"],
  sales_order: ["Pesanan ini tertahan di mana dan apa yang perlu dilakukan?", "Bagaimana status pembayaran dan sisa tagihan pesanan ini?"],
  purchase_order: ["PO ini sudah sampai tahap apa dan apakah terlambat?", "Bagaimana performa tepat waktu supplier PO ini?"],
  goods_receipt: ["Apa saja selisih penerimaan ini dibanding surat jalan?", "Bagaimana riwayat selisih & QC supplier penerimaan ini?"],
  sales_return: ["Kenapa retur ini terjadi dan sampai tahap apa penanganannya?", "Berapa nilai retur pelanggan ini 6 bulan terakhir?", "Apa yang perlu dilakukan selanjutnya untuk retur ini?"],
  purchase_return: ["Apa alasan retur ini dan apakah nota debitnya sudah terbit?", "Berapa sering kita meretur ke supplier ini 6 bulan terakhir?"],
  vendor_bill: ["Berapa sisa tagihan ini dan apa status pembayarannya?", "Berapa total hutang ke supplier ini dan mana yang segera jatuh tempo?", "Bagaimana kinerja supplier tagihan ini (tepat waktu & kualitas)?"],
  makloon_order: ["Order makloon ini sudah sampai tahap apa dan apa yang tertahan?", "Bagaimana hasil/susut tiap tahap order ini dibanding toleransi?", "Order makloon apa saja yang masih berjalan dan mana yang terlambat?"],
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
        <DropdownMenuSeparator />
        <DropdownMenuItem className="text-[12px] font-medium" onSelect={() => go("")} data-testid={`ask-kn-${type}-custom`}>
          <PenLine size={13} className="mr-1.5" /> Tulis pertanyaan sendiri…
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
