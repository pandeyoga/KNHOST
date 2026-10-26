/**
 * SettingsGroupView — fase 3 · P2 (keputusan pemilik P16-K1): Pusat Pengaturan DIKUNCI ke kelompok registri satu
 * domain (`settings-cfg-*`, peta di `config/configGroupViews.js`).
 *
 * KENAPA: dulu "aturan penerimaan barang" ada di Pusat Pengaturan (23 kelompok di kolom kiri) sedangkan "Penerimaan &
 * OCR" tab Pengaturan lain — dua tempat untuk satu urusan. Kini Pengaturan › Gudang & Mutu memuat keduanya. Mesinnya
 * SAMA dengan "Semua pengaturan" (`useSettingsBrowser` + `SettingsBrowser` dari SettingsHub) — tidak ada form kedua.
 * Pencarian di sini hanya di kelompok layar ini; pencarian lintas semua kelompok, kesehatan & riwayat tetap di
 * Pengaturan › Integrasi & Sistem › Semua pengaturan.
 *
 * Deep link `openConfig({ key, group })` mendarat di sini bila kelompoknya milik layar ini (hooks/useDeepLinks.js).
 */
import { SlidersHorizontal } from "lucide-react";
import DesktopOnlyNotice from "../../../components/DesktopOnlyNotice";
import LinkCard from "../../../components/LinkCard";
import DivisionsView from "../../designer/DivisionsView";
import { COMMISSION_LINK, SettingsBrowser, SettingsNotice, useSettingsBrowser } from "../config/SettingsHub";
import { CONFIG_GROUP_VIEWS } from "../config/configGroupViews";

export default function SettingsGroupView({
  view, currentUser, selectedEntity, entities = [],
  focusKey = "", focusGroup = "", focusNonce = 0, onFocusConsumed,
}) {
  const cfg = CONFIG_GROUP_VIEWS[view] || { groups: [] };
  const s = useSettingsBrowser({
    selectedEntity, groupIds: cfg.groups, excludeKeys: cfg.excludeKeys || null,
    focusKey, focusGroup, focusNonce, onFocusConsumed,
  });
  const names = s.groups.map((g) => g.label).join(" · ");

  return (
    <div className="cfg-hub cfg-group-view" data-testid={`settings-group-${view}`}>
      <DesktopOnlyNotice testId="settings-desktop-notice" what="Pengaturan" />
      <p className="cfg-group-intro" data-testid="settings-group-intro">
        <SlidersHorizontal size={13} className="mr-1 inline align-[-2px] text-[#0058CC]" aria-hidden="true" />
        Aturan sistem untuk domain ini{names ? <> — <b>{names}</b></> : null}. Bisa dijelaskan, dicoba dulu, dijadwalkan,
        dan dilihat riwayatnya per kartu.
      </p>
      <SettingsNotice s={s} />
      <SettingsBrowser s={s} entities={entities} groupNav="chips"
        excludeLink={cfg.excludeKeys ? COMMISSION_LINK : null}
        searchPlaceholder="Cari di kelompok ini… (pencarian lintas semua kelompok ada di Semua pengaturan)" />
      {view === "settings-cfg-rnd" && (
        <DivisionsView section="team" currentUser={currentUser} selectedEntity={selectedEntity} />
      )}
      <LinkCard testId="settings-all-link" what="Pencarian lintas semua kelompok, kesehatan & riwayat perubahan"
        where="Pengaturan › Integrasi & Sistem › Semua pengaturan" view="settings-config" hideWhenDenied />
    </div>
  );
}
