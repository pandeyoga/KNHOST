import { useState } from "react";
import { Truck } from "lucide-react";
import MobileShell from "./MobileShell";
import DriverTodayPanel from "../logistics/DriverTodayPanel";
import DeliveryDetailModal from "../logistics/DeliveryDetailModal";
import { linkView } from "./notifText";

/**
 * MobileDriverApp — aplikasi HP SOPIR (FIX-1, audit B1 UI-23 · keputusan K-B1-08: "Pengiriman saja").
 *
 * Dulu sopir mendapat aplikasi HP GUDANG (Masuk/Keluar/Sample/Pindai) yang seluruh tabnya memanggil endpoint ber-izin
 * `wms.view` → tiga tab menampilkan "Permission ditolak: wms.view" mentah. Izin sopir hanya `logistics` (lihat &
 * perbarui), jadi aplikasinya kini hanya berisi pekerjaannya: daftar pengiriman hari ini milik sopir (urutan rute bisa
 * disusun) → buka satu pengiriman untuk foto muat, posisi, tahapan, dan bukti terima (POD). Komponen sama dengan layar
 * desktop Pengiriman (`DriverTodayPanel` + `DeliveryDetailModal`), jadi isian HP = desktop.
 */
export default function MobileDriverApp(props) {
  const [openId, setOpenId] = useState(null);
  const [tick, setTick] = useState(0);
  const openFull = (navId, view, opts) => { if (props.onOpenFull) props.onOpenFull(navId, view, opts); else props.onNavigate?.(navId, view); };
  const openNotif = (n) => { const view = linkView(n); if (!view) return false; openFull(view, view); return true; };
  const tabs = [
    {
      id: "delivery", label: "Pengiriman", icon: Truck,
      render: () => (
        <div className="p-3 space-y-3" data-testid="mobile-driver-deliveries">
          <DriverTodayPanel params={{}} onOpen={setOpenId} refreshKey={tick} />
          <button type="button" className="secondary-button w-full py-3" data-testid="mobile-driver-open-full"
            onClick={() => openFull("logistics", "logistics")}>Buka semua pengiriman saya</button>
        </div>
      ),
    },
  ];
  return (
    <>
      <MobileShell {...props} tabs={tabs} initialTab="delivery" testId="mobile-driver-app" onOpenNotif={openNotif} />
      {openId && (
        <DeliveryDetailModal id={openId} canManage={false} canUpdate canOpenOrder={false}
          onClose={() => setOpenId(null)} onChanged={() => setTick((n) => n + 1)} />
      )}
    </>
  );
}
