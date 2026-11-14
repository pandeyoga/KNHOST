/**
 * SettingsLinkCards — KP-T9 (KP-29): kartu tautan ke pengaturan yang tinggal di layar lain di luar grup Pengaturan
 * (jadwal bayar antar-PT, rekening & kas, syarat pembayaran, gudang, WhatsApp kirim dokumen). Daftar per layar di
 * `config/configGroupViews.js` `SETTINGS_LINKS`; tiap kartu = `LinkCard` `hideWhenDenied` (peran yang tidak boleh
 * membuka layar tujuan tidak melihat kartunya). Tidak merender apa pun bila tidak ada kartu yang boleh dibuka.
 */
import { ExternalLink } from "lucide-react";
import LinkCard from "../../../components/LinkCard";
import { useAppNav } from "../../../context/AppNavContext";
import { SETTINGS_LINKS } from "../config/configGroupViews";

export default function SettingsLinkCards({ view }) {
  const { canOpen } = useAppNav();
  const links = (SETTINGS_LINKS[view] || []).filter((l) => canOpen(l.view));
  if (!links.length) return null;
  return (
    <section className="mt-3 grid gap-2" data-testid="settings-links" aria-label="Pengaturan terkait di menu lain">
      <p className="text-fs-12 font-semibold text-kn-text-2">Pengaturan terkait di menu lain</p>
      {links.map((l) => (
        <LinkCard key={l.view} testId={`cfg-link-${l.view}`} icon={ExternalLink} what={l.what} where={l.where}
          view={l.view} hideWhenDenied />
      ))}
    </section>
  );
}
