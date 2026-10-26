/**
 * StockOpnameTab — tab "Stock Opname" di Operasi Gudang (fase 3 · P5, D-15).
 *
 * KENAPA ADA: dulu ada DUA alur stock opname — sesi hitung fisik di sini (mengubah stok lewat persetujuan
 * manajer) dan tab "Stock Opname (RFID)" di Lokasi RFID (sapu handheld, laporan saja). Petugas tidak tahu
 * mana yang "resmi". Kini satu tempat dengan dua METODE:
 *  · "Hitung fisik" (`CycleCount`) — satu-satunya jalan yang MENGUBAH stok (sesudah disetujui);
 *  · "Sapu RFID" (`rfid/CycleCountPanel`) — laporan akurasi saja, stok TIDAK diubah. Hanya untuk peran yang
 *    dulu bisa membuka menu RFID (`canOpen("cs-rfid-lokasi")`: admin, warehouse, + `hidden_views` peran
 *    kustom dipatuhi lewat SSOT menu) — tidak ada peran yang mendapat akses baru.
 * Lokasi RFID kini hanya menautkan ke sini (`operations` {tab:"cycle", method:"rfid", warehouse}).
 */
import { ClipboardCheck, Radar } from "lucide-react";
import FilterChips from "../../components/FilterChips";
import KNSelect from "../../components/KNSelect";
import { useAppNav } from "../../context/AppNavContext";
import CycleCount from "../inventory/CycleCount";
import CycleCountPanel from "../rfid/CycleCountPanel";

export default function StockOpnameTab({
  method = "count", onMethodChange, warehouseId = "", onWarehouseChange, warehouses = [],
  selectedEntity, cycleKey, cycleCountProps = {},
}) {
  const { canOpen } = useAppNav();
  const rfidAllowed = canOpen("cs-rfid-lokasi");
  // Tautan ke sesi opname tertentu (Meja Gudang/papan) selalu membuka metode Hitung fisik.
  const active = method === "rfid" && rfidAllowed && !cycleCountProps.focusSessionId ? "rfid" : "count";
  const whOpts = [{ value: "", label: "Pilih gudang" }].concat(
    (warehouses || []).map((w) => ({ value: w.id, label: [w.name, w.city].filter(Boolean).join(" — ") })));

  return (
    <div data-testid="wms-opname-tab" className="grid grid-cols-[minmax(0,1fr)] gap-3">
      {rfidAllowed && (
        <div className="flex flex-wrap items-center gap-2" data-testid="wms-opname-method-row">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-[#8E8E93]">Metode</span>
          <FilterChips testId="wms-opname-method" ariaLabel="Metode stock opname" value={active}
            onChange={(k) => onMethodChange?.(k)}
            options={[
              { key: "count", label: "Hitung fisik (mengubah stok lewat persetujuan)", icon: ClipboardCheck },
              { key: "rfid", label: "Sapu RFID (laporan saja)", icon: Radar },
            ]} />
        </div>
      )}

      {active === "rfid" ? (
        <section className="section-card" data-testid="wms-opname-rfid">
          <div className="section-head max-sm:!flex-col max-sm:!items-start max-sm:gap-2">
            <div className="min-w-0">
              <span className="kicker">Stock Opname · Sapu RFID</span>
              <h2>Laporan akurasi tag per gudang</h2>
            </div>
            <KNSelect data-testid="wms-opname-rfid-wh" value={warehouseId} onValueChange={(v) => onWarehouseChange?.(v)}
              options={whOpts} className="field !py-1 !px-2 text-[12px] w-64 max-w-full" placeholder="Pilih gudang" />
          </div>
          <div className="section-body grid gap-2">
            <p className="text-[11.5px] text-[#6B6B73]">
              Sapu RFID hanya MELAPORKAN tag yang terbaca/hilang — stok tidak berubah. Selisih yang perlu dikoreksi
              dihitung ulang lewat metode <b>Hitung fisik</b> (disetujui manajer) atau ditindaklanjuti lewat inspeksi.
            </p>
            <CycleCountPanel whId={warehouseId} selectedEntity={selectedEntity} />
          </div>
        </section>
      ) : (
        <CycleCount key={cycleKey} {...cycleCountProps} />
      )}
    </div>
  );
}
