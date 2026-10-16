import OutboundScanInterface from "./OutboundScanInterface";

/** Operasi Gudang › Barang Keluar — setara dengan Barang Masuk (satu level hub). */
export default function OutboundView({ user, focusDoc, onClearFocus }) {
  return (
    <div className="section-card" data-testid="wms-outbound-view">
      <div className="section-head">
        <div className="flex items-center gap-2 min-w-0">
          <span className="kicker">Barang Keluar</span>
          <h2>Pengambilan & Pengiriman Pesanan Penjualan</h2>
        </div>
        <span className="text-[11px] text-[#6B6B73]">Scan barcode di formulir tugas di bawah</span>
      </div>
      <div className="section-body">
        <OutboundScanInterface user={user}
          focusTaskId={focusDoc?.focus_type === "wms_task" ? focusDoc.focus_id : ""}
          onFocusConsumed={onClearFocus} />
      </div>
    </div>
  );
}
