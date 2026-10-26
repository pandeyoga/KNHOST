/**
 * MyApprovalsView (PS-20 / D-14) — layar lama **Pusat Persetujuan › Persetujuan Saya** (`my-approvals`).
 *
 * Fase 3 · P3 (D-06): isinya kini panel `MyApprovalsPanel` yang juga dirender sebagai tab "Matriks divisi" di
 * Pusat Persetujuan (layar utama). Berkas ini tinggal pembungkus tipis untuk rute cadangan `activeView ===
 * "my-approvals"` (deep link, notifikasi, uji) sampai P8 mengaktifkan alias `my-approvals` → `approval-inbox`
 * {tab:"matrix"}.
 */
import MyApprovalsPanel from "./MyApprovalsPanel";

export default function MyApprovalsView({ currentUser, selectedEntity, onNavigate }) {
  return <MyApprovalsPanel currentUser={currentUser} selectedEntity={selectedEntity} onNavigate={onNavigate} />;
}
