/**
 * DevicesView — Pengaturan › Integrasi & Sistem › **Perangkat** (`settings-devices`, fase 3 · P2, D-29).
 *
 * KENAPA: dulu ada dua menu "Perangkat" — tab Perangkat di Shift & Geofence (mesin absen) dan "Perangkat RFID"
 * di Pengaturan › Gudang. Pemilik mencari perangkat di satu tempat; keputusan Q2 menaruh layar gabungan di
 * Integrasi & Sistem. Isinya komponen LAMA tanpa salinan:
 *   · tab "Mesin absen"  = `AttendanceSetupView only="device"` (izin hr.manage_attendance; admin + manajer);
 *   · tab "RFID (pembaca/gerbang)" = `RfidDevicesView embedded` — hanya admin, sama seperti `cs-rfid-devices` dulu.
 * Alamat lama `?view=cs-rfid-devices` = alias ke tab RFID (`viewAliases.js`); Shift & Geofence menautkan ke sini.
 */
import { useState } from "react";
import { Cpu, Fingerprint, Wifi } from "lucide-react";
import PageTabs from "../../../components/PageTabs";
import DesktopOnlyNotice from "../../../components/DesktopOnlyNotice";
import useViewPreset from "../../../hooks/useViewPreset";
import { roleCanSee } from "../../../config/roles";
import AttendanceSetupView from "../../hr/AttendanceSetupView";
import RfidDevicesView from "../../rfid/RfidDevicesView";

export default function DevicesView({ currentUser, selectedEntity, initialTab = "" }) {
  // Tab RFID tetap khusus admin (peran `cs-rfid-devices` dulu: admin saja; tulis perangkat RFID = admin di server).
  // Fase 3 · P8 (§1.1 butir 6) — gerbang per bagian memakai id layar LAMA lewat `roleCanSee`, supaya peran kustom
  // (katalog akses: Operasi Gudang memuat `cs-rfid-devices`, SDM memuat `hr-attendance-setup`) dan `hidden_views`-nya
  // tetap berlaku seperti di layar lama. Peran bawaan: sama seperti sebelumnya (RFID admin; Mesin absen admin+manajer).
  const role = currentUser?.role;
  const rfidAllowed = roleCanSee(["admin"], role, "cs-rfid-devices");
  const absenAllowed = roleCanSee(["admin", "manager"], role, "hr-attendance-setup") || !rfidAllowed;
  const pick = (t) => ((t === "rfid" && rfidAllowed) || !absenAllowed ? "rfid" : "absen");
  const [tab, setTab] = useState(() => pick(initialTab));
  useViewPreset("settings-devices", (p) => { if (p.tab) setTab(pick(p.tab)); });

  return (
    <div className="grid grid-cols-1 gap-3" data-testid="settings-devices-view">   {/* kolom minmax(0,1fr): baris panjang tidak melebarkan halaman di HP */}
      <DesktopOnlyNotice testId="settings-desktop-notice" what="Pengaturan" />
      <p className="text-[12px] text-[#3C3C43]" data-testid="settings-devices-intro">
        <Cpu size={13} className="mr-1 inline align-[-2px] text-[#0058CC]" aria-hidden="true" />
        Semua perangkat yang tersambung ke sistem di satu tempat: mesin absen karyawan dan pembaca/gerbang RFID gudang.
      </p>
      <PageTabs testId="devices-tabs" value={tab} onChange={setTab} ariaLabel="Jenis perangkat"
        tabs={[
          { key: "absen", label: "Mesin absen", icon: Fingerprint, hidden: !absenAllowed },
          { key: "rfid", label: "RFID (pembaca/gerbang)", icon: Wifi, hidden: !rfidAllowed },
        ]} />
      {(tab === "rfid" && rfidAllowed) || !absenAllowed
        ? <RfidDevicesView currentUser={currentUser} embedded />
        : <AttendanceSetupView currentUser={currentUser} selectedEntity={selectedEntity} only="device" />}
    </div>
  );
}
