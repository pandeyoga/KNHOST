/**
 * SettingsGroupView — fase 3 · P2 (keputusan pemilik P16-K1): Pusat Pengaturan DIKUNCI ke kelompok registri satu
 * domain (`settings-cfg-*`, peta di `config/configGroupViews.js`).
 *
 * KENAPA: dulu "aturan penerimaan barang" ada di Pusat Pengaturan (23 kelompok di kolom kiri) sedangkan "Penerimaan &
 * OCR" tab Pengaturan lain — dua tempat untuk satu urusan. Kini Pengaturan › Gudang, Pembelian & Produksi memuat keduanya. Mesinnya
 * SAMA dengan "Semua pengaturan" (`useSettingsBrowser` + `SettingsBrowser` dari SettingsHub) — tidak ada form kedua.
 * Pencarian di sini hanya di kelompok layar ini; pencarian lintas semua kelompok, kesehatan & riwayat tetap di
 * Pengaturan › Sistem › Cari Semua Pengaturan. KP-T9 (KP-29) — di bawah daftar kartu: tautan ke pengaturan yang tinggal
 * di layar lain (`SettingsLinkCards`, peta `SETTINGS_LINKS`).
 *
 * Deep link `openConfig({ key, group })` mendarat di sini bila kelompoknya milik layar ini (hooks/useDeepLinks.js).
 */
import { useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import useViewPreset from "../../../hooks/useViewPreset";
import DesktopOnlyNotice from "../../../components/DesktopOnlyNotice";
import LinkCard from "../../../components/LinkCard";
import DivisionsView from "../../designer/DivisionsView";
import { COMMISSION_LINK, SettingsBrowser, SettingsNotice, useSettingsBrowser } from "../config/SettingsHub";
import { CONFIG_GROUP_VIEWS } from "../config/configGroupViews";
import SettingsLinkCards from "./SettingsLinkCards";

/** KF-T4 — dua layar lama yang kini alias (`config/viewAliases.js`): rute cadangan merender layar tujuannya pada
 *  sub-judul yang dulu jadi isinya. */
export const CFG_VIEW_ALIASES = {
  "settings-cfg-documents": { view: "settings-cfg-approval", section: "rujukan-dokumen" },
  "settings-cfg-notify": { view: "settings-cfg-approval", section: "pemberitahuan" },
};

export default function SettingsGroupView({
  view: viewProp, currentUser, selectedEntity, entities = [],
  focusKey = "", focusGroup = "", focusNonce = 0, onFocusConsumed,
}) {
  const alias = CFG_VIEW_ALIASES[viewProp] || null;
  const view = alias ? alias.view : viewProp;
  const cfg = CONFIG_GROUP_VIEWS[view] || { groups: [] };
  // KF-T4 — preset `{ section }` (alias / tautan) membuka sub-judul yang dituju.
  const [presetSection, setPresetSection] = useState(alias ? alias.section : "");
  const [presetNonce, setPresetNonce] = useState(alias ? 1 : 0);
  useViewPreset(view, (p) => { if (p.section) { setPresetSection(p.section); setPresetNonce((n) => n + 1); } });
  const s = useSettingsBrowser({
    selectedEntity, groupIds: cfg.groups, excludeKeys: cfg.excludeKeys || null,
    focusKey, focusGroup, focusSection: focusKey || focusGroup ? "" : presetSection,
    focusNonce: focusNonce || (presetNonce ? -presetNonce : 0), onFocusConsumed,
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
        excludeLink={cfg.excludeLink || (cfg.excludeKeys ? COMMISSION_LINK : null)}
        searchPlaceholder="Cari di kelompok ini… (pencarian lintas semua kelompok ada di Cari Semua Pengaturan)" />
      {view === "settings-cfg-rnd" && (
        <DivisionsView section="team" currentUser={currentUser} selectedEntity={selectedEntity} />
      )}
      <SettingsLinkCards view={view} />
      <LinkCard testId="settings-all-link" what="Pencarian lintas semua kelompok, kesehatan & riwayat perubahan"
        where="Pengaturan › Sistem › Cari Semua Pengaturan" view="settings-config" hideWhenDenied />
    </div>
  );
}
