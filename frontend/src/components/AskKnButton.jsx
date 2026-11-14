import { PenLine, Sparkles } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "./ui/dropdown-menu";
import { canCurrent } from "../config/roles";

export const PENDING_KEY = "kn_tanya_pending";

export const PRESETS = {
  customer: ["Kenapa penjualan pelanggan ini naik/turun 3 bulan terakhir?", "Berapa piutang pelanggan ini dan mana yang lewat jatuh tempo?", "Produk apa yang paling sering dibeli pelanggan ini 12 bulan terakhir?", "Seberapa besar risiko pelanggan ini berhenti order?"],
  product: ["Bagaimana tren penjualan produk ini 12 minggu terakhir?", "Berapa perkiraan kebutuhan produk ini 6 minggu ke depan dan perlu pesan ulang berapa?", "Siapa pelanggan terbesar produk ini 12 bulan terakhir?"],
  sales_order: ["Pesanan ini tertahan di mana dan apa yang perlu dilakukan?", "Bagaimana status pembayaran dan sisa tagihan pesanan ini?"],
  purchase_order: ["PO ini sudah sampai tahap apa dan apakah terlambat?", "Bagaimana performa tepat waktu supplier PO ini?"],
  goods_receipt: ["Apa saja selisih penerimaan ini dibanding surat jalan?", "Bagaimana riwayat selisih & QC supplier penerimaan ini?"],
  sales_return: ["Kenapa retur ini terjadi dan sampai tahap apa penanganannya?", "Berapa nilai retur pelanggan ini 6 bulan terakhir?", "Apa yang perlu dilakukan selanjutnya untuk retur ini?"],
  purchase_return: ["Apa alasan retur ini dan apakah nota debitnya sudah terbit?", "Berapa sering kita meretur ke supplier ini 6 bulan terakhir?"],
  vendor_bill: ["Berapa sisa tagihan ini dan apa status pembayarannya?", "Berapa total hutang ke supplier ini dan mana yang segera jatuh tempo?", "Bagaimana kinerja supplier tagihan ini (tepat waktu & kualitas)?"],
  makloon_order: ["Order makloon ini sudah sampai tahap apa dan apa yang tertahan?", "Bagaimana hasil/susut tiap tahap order ini dibanding toleransi?", "Order makloon apa saja yang masih berjalan dan mana yang terlambat?"],
  // AG-T3 — layar keuangan: Buku Besar (jurnal), Piutang (pelanggan), Kas & Bank (mutasi), Tutup Buku (periode).
  journal_entry: ["Jurnal ini berasal dari dokumen apa dan akun apa saja yang terkena?", "Apakah ada jurnal pembalik untuk jurnal ini?"],
  ar_receipt: ["Berapa piutang pelanggan ini dan mana yang lewat jatuh tempo?", "Kapan pelanggan ini terakhir membayar dan berapa?", "Siapkan catatan tindak lanjut penagihan untuk pelanggan ini."],
  bank_line: ["Transaksi kas mana yang paling cocok dengan mutasi ini?", "Siapkan kartu pencocokan untuk mutasi ini."],
  period: ["Apa saja yang masih menahan tutup buku periode ini?", "Dokumen apa yang jurnalnya masih gagal di periode ini?"],
};
/** AG-T3 — jenis konteks keuangan: dibuka di mode Keuangan Tanya KN dan tampil menurut izin `ai_finance.view`. */
export const FINANCE_CONTEXT_TYPES = new Set(["journal_entry", "ar_receipt", "bank_line", "period"]);

// PR-T7 (#23) — tombol mengikuti izin `ai.view` (= gerbang asisten di server), bukan daftar tujuh nama peran: peran
// kustom berizin kini melihatnya, peran yang izinnya dicabut tidak. AG-T3 — konteks keuangan juga menuntut
// `ai_finance.view` (Asisten Keuangan), bukan daftar nama peran.
function canAsk(type) {
  if (!canCurrent("ai", "view")) return false;
  return FINANCE_CONTEXT_TYPES.has(type) ? canCurrent("ai_finance", "view") : true;
}

/** Tombol "Tanya KN" di halaman detail: membuka asisten dengan konteks halaman ini. */
export function AskKnButton({ type, id, label, className = "secondary-button", buttonLabel = "Tanya KN" }) {
  if (!id || !canAsk(type)) return null;
  const go = (question) => {
    const mode = FINANCE_CONTEXT_TYPES.has(type) ? "keuangan" : undefined;
    sessionStorage.setItem(PENDING_KEY, JSON.stringify({ question, context: { type, id, label: label || id }, mode }));
    const ent = new URLSearchParams(window.location.search).get("entity");
    window.location.assign(`/?view=tanya-kn${ent ? `&entity=${encodeURIComponent(ent)}` : ""}&tab=chat`);
  };
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" className={className} data-testid={`ask-kn-${type}`}><Sparkles size={13} aria-hidden="true" /> {buttonLabel}</button>
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
