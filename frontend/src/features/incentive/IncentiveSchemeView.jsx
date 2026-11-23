/**
 * IncentiveSchemeView — KA-9 · SDM › Kinerja & Insentif › **Skema & Tarif** (view `incentive-scheme`).
 *
 * Satu tempat untuk komisi sales per PT (rancangan `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md`
 * §6.5–§6.7; dulu tersebar di Target & Aturan › "Komisi otomatis (cara lama)" dan Pengaturan). Urutan bagian = urutan
 * menyiapkan: 1. Sumber insentif (`SchemeSourcePicker`, kunci `hr.payroll_commission_mode`) · 2. Tarif komisi
 * Kategori → Artikel → Varian (`ArticleRatesTable`; pengguna baru cukup mengisi tarif kategori) · 3. Pengali harga ·
 * 4. Pengali capaian · 5. Batas margin (3–5 = Pusat Pengaturan tertanam per bagian, `useSettingsBrowser` + `includeKeys`;
 * `commission.incentive_unit` dan `commission.strategy` tidak ditampilkan) · Akrual komisi bulanan (`KartuAkrual`) ·
 * Jenjang komisi per sales (`LegacySchemeEditor`, hanya bila `commission.strategy` = `achievement_tiered`) · Simulasi
 * (`SchemeSimulation`).
 *
 * PT = pemilih PT di kepala aplikasi (D-14). "Semua PT" = hanya kalimat "Pilih satu PT …" (keputusan R14: rute tarif
 * menolak "Semua PT"); tanpa `sales_force.view` = kalimat izin; keduanya TANPA panggilan API. Mode PT & daftar sales dari
 * `GET /api/incentive/targets` (`commission_mode`, `roster`). Deep link kunci `commission.*` (`COMMISSION_HOME`) membuka
 * bagian yang memuat kuncinya (`bagianUntukKunci`).
 */
import { useCallback, useEffect, useState } from "react";
import { Calculator, Coins, Gauge, Percent, Shield, SlidersHorizontal, Wallet } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import EntityRequiredNotice from "../../components/EntityRequiredNotice";
import EntityScopeBanner from "../../components/EntityScopeBanner";
import ErrorNotice from "../../components/ErrorNotice";
import { HelpTip } from "../../components/ListPageParts";
import { apiErrorText } from "../../utils/apiError";
import { entityFullById, entityShortById } from "../../utils/entityLabel";
import { canCurrent } from "../../config/roles";
import { useEntityScope } from "../../context/EntityScopeContext";
import { SettingsBrowser, SettingsNotice, useSettingsBrowser } from "../settings/config/SettingsHub";
import { groupForKey } from "../settings/config/configDeepLink";
import ArticleRatesTable from "./ArticleRatesTable";
import KartuAkrual from "./KartuAkrual";
import LegacySchemeEditor from "./LegacySchemeEditor";
import SchemeSimulation from "./SchemeSimulation";
import SchemeSourcePicker from "./SchemeSourcePicker";
import { TEKS_BERLAKU } from "./RateFormModal";
import { komisiOtomatisJalan } from "./incentiveModes";

export const TEKS_SEMUA_PT = "Pilih satu PT di pemilih PT (kanan atas) untuk melihat dan mengatur skema & tarif komisi. "
  + "Sumber insentif, tarif, dan pengali berlaku per PT.";
export const TEKS_TANPA_LIHAT = "Melihat skema & tarif komisi butuh akses Lihat di modul Pengawasan Tim Sales & Kredit.";
export const TEKS_TARIF_TIDAK_DIPAKAI = "PT ini tidak memakai komisi otomatis, jadi tarif dan pengali di bawah tidak dipakai "
  + "sampai sumber insentif diubah ke Komisi otomatis atau Keduanya dibayar.";

/** Kunci Pusat Pengaturan per bagian (prefiks `includeKeys`). */
export const KUNCI_BAGIAN = {
  harga: ["commission.price_basis", "commission.price_bands", "commission.price_source_rules", "commission.discount_"],
  capaian: ["commission.achievement_multiplier", "commission.achievement_basis", "commission.achievement_tiers"],
  batas: ["commission.default_margin_cap_pct"],
};
const KUNCI_BATAS = "commission.default_margin_cap_pct";
const KUNCI_STRATEGI = "commission.strategy";

/** Bagian yang memuat kunci `key` ("harga" | "capaian" | "batas"), "" bila kunci tidak tampil di tab ini. */
export function bagianUntukKunci(key) {
  return Object.keys(KUNCI_BAGIAN).find((b) => KUNCI_BAGIAN[b].some((p) => String(key || "").startsWith(p))) || "";
}

function Bagian({ nomor, icon: Icon, judul, help, testId, children }) {
  return (
    <section className="section-card" data-testid={testId}>
      <div className="section-head">
        <h2 className="flex items-center gap-2">
          {Icon && <Icon size={16} className="text-kn-action" aria-hidden="true" />}
          {nomor ? `${nomor}. ${judul}` : judul}
          {help && <HelpTip text={help} testId={`${testId}-help`} />}
        </h2>
      </div>
      <div className="section-body space-y-2">{children}</div>
    </section>
  );
}

/** Pusat Pengaturan tertanam, dikunci ke kunci satu bagian (nilai PT aktif; berlaku mulai, alasan, riwayat ikut). */
function PengaturanBagian({ s, entities }) {
  return (
    <div className="cfg-hub cfg-group-view">
      <SettingsNotice s={s} />
      <SettingsBrowser s={s} entities={entities} groupNav="chips" searchPlaceholder="Cari pengaturan di bagian ini…" />
    </div>
  );
}

export default function IncentiveSchemeView({ focusKey = "", focusGroup = "", focusNonce = 0, onFocusConsumed } = {}) {
  const { canWrite, selectedEntity, entities } = useEntityScope();
  const lihat = canCurrent("sales_force", "view");
  const siap = lihat && canWrite;
  if (!lihat) {
    return (
      <div className="space-y-4" data-testid="incentive-scheme-view">
        <p className="text-fs-13 text-kn-text-2" data-testid="scheme-no-access">{TEKS_TANPA_LIHAT}</p>
      </div>
    );
  }
  if (!siap) {
    return (
      <div className="space-y-4" data-testid="incentive-scheme-view">
        <EntityRequiredNotice what="skema & tarif komisi" reason={TEKS_SEMUA_PT} when testId="scheme-all-pt" />
      </div>
    );
  }
  // `key` = PT: berganti PT memasang ulang seluruh isi (cakupan Pusat Pengaturan tertanam dipilih saat dipasang).
  return <IsiSkema key={selectedEntity} entityId={selectedEntity} entities={entities}
    cfgFocus={{ focusKey, focusGroup, focusNonce, onFocusConsumed }} />;
}

function IsiSkema({ entityId, entities, cfgFocus }) {
  const pt = entityFullById(entities, entityId, "PT ini");
  const ptPendek = entityShortById(entities, entityId, "pt");
  const [sakelar, setSakelar] = useState({ state: "loading", mode: "", roster: [], err: "" });
  const [strategi, setStrategi] = useState("");

  // Deep link kunci komisi → hanya bagian yang memuat kuncinya menerima fokus; kunci yang tidak tampil (strategi,
  // satuan) langsung dilepas supaya permintaan fokus tidak menggantung.
  const bagianFokus = bagianUntukKunci(cfgFocus.focusKey);
  const fokus = (b) => (bagianFokus === b ? cfgFocus : {});
  useEffect(() => {
    if (cfgFocus.focusNonce && !bagianFokus && cfgFocus.onFocusConsumed) cfgFocus.onFocusConsumed();
  }, [cfgFocus.focusNonce]); // eslint-disable-line react-hooks/exhaustive-deps
  const grup = [groupForKey(KUNCI_BAGIAN.harga[0])].filter(Boolean);
  const harga = useSettingsBrowser({ selectedEntity: entityId, groupIds: grup, includeKeys: KUNCI_BAGIAN.harga, ...fokus("harga") });
  const capaian = useSettingsBrowser({ selectedEntity: entityId, groupIds: grup, includeKeys: KUNCI_BAGIAN.capaian, ...fokus("capaian") });
  const batas = useSettingsBrowser({ selectedEntity: entityId, groupIds: grup, includeKeys: KUNCI_BAGIAN.batas, ...fokus("batas") });
  const bawaanBatas = (batas.items || []).find((i) => i.key === KUNCI_BATAS)?.value;

  const muatSakelar = useCallback(async () => {
    setSakelar((s) => ({ ...s, state: "loading" }));
    try {
      const r = await axios.get(`${API}/incentive/targets`, { params: { period_type: "month" } });
      setSakelar({ state: "ready", mode: r.data?.commission_mode || "", roster: r.data?.roster || [], err: "" });
    } catch (e) { setSakelar({ state: "error", mode: "", roster: [], err: apiErrorText(e) || "" }); }
  }, []);
  useEffect(() => { muatSakelar(); }, [muatSakelar, entityId]);
  useEffect(() => {
    let hidup = true;
    axios.get(`${API}/config/explain`, { params: { key: KUNCI_STRATEGI, entity_id: entityId } })
      .then((r) => { if (hidup) setStrategi(r.data?.value || ""); })
      .catch(() => { if (hidup) setStrategi(""); });
    return () => { hidup = false; };
  }, [entityId]);

  const mode = sakelar.mode;
  const otomatis = sakelar.state === "ready" && komisiOtomatisJalan(mode);
  return (
    <div className="space-y-4" data-testid="incentive-scheme-view">
      <EntityScopeBanner testId="scheme-scope" />

      <Bagian nomor={1} icon={Wallet} judul="Sumber insentif" testId="scheme-source-card"
        help="Dari mana insentif sales PT ini dibayar lewat gaji: komisi otomatis dari tarif, Lembar Insentif yang disahkan pimpinan, atau keduanya.">
        {sakelar.state === "loading" ? (
          <p className="text-fs-13 text-kn-text-2" role="status" data-testid="scheme-source-loading">Memuat sumber insentif…</p>
        ) : sakelar.state === "error" ? (
          <ErrorNotice testId="scheme-source-load-error" message={`Sumber insentif tidak bisa dimuat. ${sakelar.err}`.trim()} onRetry={muatSakelar} />
        ) : (
          <SchemeSourcePicker entityId={entityId} pt={pt} mode={mode} onSaved={muatSakelar} />
        )}
      </Bagian>

      <Bagian nomor={2} icon={Coins} judul="Tarif komisi" testId="scheme-rates-card"
        help="Tarif rupiah per satuan dasar barang (yard). Urutan pencarian: tarif varian → tarif artikel → tarif kategori. Tanpa tarif di ketiganya, baris pesanan itu tidak berkomisi.">
        {sakelar.state === "ready" && !otomatis && (
          <p className="text-fs-12 text-kn-warning-text" data-testid="scheme-rates-unused">{TEKS_TARIF_TIDAK_DIPAKAI}</p>
        )}
        <p className="text-fs-12 text-kn-text-2" data-testid="scheme-rates-effective">{TEKS_BERLAKU}</p>
        <ArticleRatesTable entityId={entityId} pt={pt} ptPendek={ptPendek} bawaanBatas={bawaanBatas} />
      </Bagian>

      <Bagian nomor={3} icon={SlidersHorizontal} judul="Pengali harga" testId="scheme-price-card"
        help="Komisi dikalikan menurut seberapa jauh harga jual di bawah harga acuan (atau menurut diskon baris, cara lama). Artikel boleh punya pita sendiri di pop-up tarifnya.">
        <PengaturanBagian s={harga} entities={entities} />
      </Bagian>

      <Bagian nomor={4} icon={Gauge} judul="Pengali capaian" testId="scheme-achievement-card"
        help="Opsional: komisi bulan itu dikalikan menurut capaian target bulanan sales.">
        <PengaturanBagian s={capaian} entities={entities} />
      </Bagian>

      <Bagian nomor={5} icon={Shield} judul="Batas margin" testId="scheme-cap-card"
        help="Bawaan batas margin untuk tarif baru. Batas tiap tarif tampil dan diubah di baris tarifnya (bagian 2).">
        <PengaturanBagian s={batas} entities={entities} />
      </Bagian>

      {otomatis && (
        <Bagian icon={Percent} judul="Akrual komisi bulanan" testId="scheme-accrual-card"
          help="Membukukan beban komisi otomatis bulan itu ke buku PT (Beban Insentif Penjualan / Hutang Insentif Penjualan).">
          <KartuAkrual canWrite mode={mode} pt={pt} />
        </Bagian>
      )}

      {strategi === "achievement_tiered" && <LegacySchemeEditor />}

      <Bagian icon={Calculator} judul="Simulasi" testId="scheme-sim-card"
        help="Coba dulu: komisi seorang sales pada satu bulan dengan aturan sekarang dibanding dengan tarif percobaan. Tidak menyimpan apa pun.">
        <SchemeSimulation entityId={entityId} roster={sakelar.state === "ready" ? sakelar.roster : null} />
      </Bagian>
    </div>
  );
}
