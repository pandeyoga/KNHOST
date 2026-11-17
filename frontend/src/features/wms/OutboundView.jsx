import { Truck } from "lucide-react";
import { PageHeader } from "../../components/ListPageParts";
import OutboundScanInterface from "./OutboundScanInterface";

/** Operasi Gudang › Barang Keluar — setara dengan Barang Masuk (satu level hub).
 *  Pola UI gelombang Gudang (M26) — kepala satu baris + ? (dulu kartu berkicker + dua baris keterangan); bilah daftar,
 *  daftar, dan panel rincian sama dengan Barang Masuk & Cutting (`OpsListParts`). */
export default function OutboundView({ user, focusDoc, onClearFocus }) {
  return (
    <div className="space-y-3" data-testid="wms-outbound-view">
      <PageHeader icon={Truck} title="Barang Keluar" testId="outbound-header"
        help="Ambil & kirim pesanan penjualan: buka tugas, scan barcode roll di panel tugas, lalu kirim — Surat Jalan terbit otomatis. Potong sample/catalogue & potong roll ada di tab Cutting; paket sample muncul di sini setelah diterima Admin Cutting." />
      <OutboundScanInterface user={user}
        focusTaskId={focusDoc?.focus_type === "wms_task" ? focusDoc.focus_id : ""}
        onFocusConsumed={onClearFocus} />
    </div>
  );
}
