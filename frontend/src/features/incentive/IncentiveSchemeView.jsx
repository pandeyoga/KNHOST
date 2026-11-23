/**
 * IncentiveSchemeView — KA-9 · SDM › Kinerja & Insentif › **Skema & Tarif** (view `incentive-scheme`).
 *
 * Satu tempat untuk komisi sales per PT (rancangan `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md`
 * §6.5–§6.7; dulu tersebar di Target & Aturan › "Komisi otomatis (cara lama)" dan Pengaturan). Urutan bagian = urutan
 * menyiapkan: 1. Sumber insentif (`SchemeSourcePicker`, kunci `hr.payroll_commission_mode`, berlaku mulai + riwayat) ·
 * 2. Tarif komisi Kategori → Artikel → Varian (`ArticleRatesTable`; pengguna baru cukup mengisi tarif kategori; pop-up
 * tarif "Berlaku untuk" PT ini / Semua PT — R15) · 3. Pengali harga · 4. Pengali capaian · 5. Batas margin · Lanjutan
 * (tertutup: `commission.strategy`, R15). 3–5 dan Lanjutan = Pusat Pengaturan tertanam (`useSettingsBrowser` +
 * `includeKeys`, `SettingsBrowser embedded`: tanpa cari/pemilih cakupan per bagian; cakupan = PT halaman, ditulis sekali —
 * R16). `commission.incentive_unit` tidak ditampilkan. Lalu Akrual komisi bulanan (`KartuAkrual`) · Jenjang komisi per
 * sales (`LegacySchemeEditor`, hanya bila `commission.strategy` = `achievement_tiered`) · Simulasi (`SchemeSimulation`).
 *
 * PT = pemilih PT di kepala aplikasi (D-14). Tanpa `sales_force.view` = kalimat izin, tanpa panggilan API. "Semua PT" =
 * kalimat "Pilih satu PT …" + daftar tarif Semua PT yang bisa diubah lewat pop-up tarif yang sama (`GroupRatesList`, R15;
 * rute pohon tarif menolak "Semua PT") + bagian 3–5 dan Lanjutan pada cakupan ATURAN GRUP (`BagianPengaturanGrup`; Pusat
 * Pengaturan menyembunyikan `commission.*` dan menautkan ke tab ini, jadi di sinilah nilai grup komisi diubah). Mode PT & daftar sales dari `GET /api/incentive/targets` (`commission_mode`,
 * `roster`; 403 = kalimat izin modul Kinerja & Insentif — R16). Deep link kunci `commission.*` (`COMMISSION_HOME`)
 * membuka bagian yang memuat kuncinya (`bagianUntukKunci`); di cabang tanpa isi, permintaan fokus langsung dilepas.
 * Tinjauan akhir: T9 — bagian tertanam memakai `focusWithoutSearch` (kartu dibuka & digulir, tanpa "Hasil pencarian
 * “commission.…”"); M3/M5 — bagian 3 meneruskan `caps.global_write` (pilihan/ubah tarif Semua PT) dan
 * `commission.price_basis` (petunjuk pita artikel) ke pop-up tarif dan daftar tarif Semua PT.
 */
import { useCallback, useEffect, useState } from "react";
import { Calculator, ChevronDown, ChevronRight, Coins, Gauge, Percent, Settings2, Shield, SlidersHorizontal, Wallet } from "lucide-react";
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
import GroupRatesList from "./GroupRatesList";
import KartuAkrual from "./KartuAkrual";
import LegacySchemeEditor from "./LegacySchemeEditor";
import SchemeSimulation from "./SchemeSimulation";
import SchemeSourcePicker from "./SchemeSourcePicker";
import { TEKS_BERLAKU } from "./RateFormModal";
import { komisiOtomatisJalan } from "./incentiveModes";

export const TEKS_SEMUA_PT = "Pilih satu PT di pemilih PT (kanan atas) untuk mengatur sumber insentif, tarif per PT, "
  + "nilai khusus PT, dan simulasi. Di mode Semua PT yang bisa diubah: tarif Semua PT dan aturan grup bagian 3–5 (di bawah).";
export const TEKS_STRATEGI_LANJUTAN = "Skema tarif per artikel di atas hanya dipakai bila cara menghitung komisi = "
  + "“Per SKU (tarif per barang)”.";
export const TEKS_TANPA_LIHAT = "Melihat skema & tarif komisi butuh akses Lihat di modul Pengawasan Tim Sales & Kredit.";
export const TEKS_SUMBER_TANPA_IZIN = "Melihat sumber insentif butuh akses Lihat di modul Kinerja & Insentif.";
export const TEKS_SALES_TANPA_IZIN = "Memilih sales untuk simulasi butuh akses Lihat di modul Kinerja & Insentif.";
export const TEKS_GRUP_TERKUNCI = "Aturan grup hanya dapat diubah peran lintas PT. Pilih satu PT di pemilih PT untuk "
  + "mengubah nilai khusus PT Anda.";
export const TEKS_TARIF_TIDAK_DIPAKAI = "PT ini tidak memakai komisi otomatis, jadi tarif dan pengali di bawah tidak dipakai "
  + "sampai sumber insentif diubah ke Komisi otomatis atau Keduanya dibayar.";

/** Kunci Pusat Pengaturan per bagian (prefiks `includeKeys`). R15 — `commission.strategy` di bagian Lanjutan (tertutup);
 *  `commission.incentive_unit` tidak ditampilkan di mana pun. */
export const KUNCI_BAGIAN = {
  harga: ["commission.price_basis", "commission.price_bands", "commission.price_source_rules", "commission.discount_"],
  capaian: ["commission.achievement_multiplier", "commission.achievement_basis", "commission.achievement_tiers"],
  batas: ["commission.default_margin_cap_pct"],
  lanjutan: ["commission.strategy"],
};
const KUNCI_BATAS = "commission.default_margin_cap_pct";
const KUNCI_DASAR_HARGA = "commission.price_basis";
const INFO_AWAL = { lintasPt: null, dasarHarga: "" };
const KUNCI_STRATEGI = "commission.strategy";
const STRATEGI_ARSIP = "achievement_tiered";

/** Bagian yang memuat kunci `key` ("harga" | "capaian" | "batas" | "lanjutan"), "" bila kunci tidak tampil di tab ini. */
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

/** Pusat Pengaturan tertanam, dikunci ke kunci satu bagian (nilai PT aktif; berlaku mulai, alasan, riwayat per kartu ikut).
 *  R16 — `embedded`: tanpa kotak cari & pemilih cakupan per bagian; testid berawalan `testIdPrefix` (tidak kembar). */
function PengaturanBagian({ s, entities, testIdPrefix }) {
  // R16 — tautan "PT dengan nilai sendiri" (cakupan grup) memindah SELURUH tab ke PT itu lewat pemilih PT halaman, bukan
  // diam-diam memindah satu bagian.
  const { pickEntity } = useEntityScope();
  return (
    <div className="cfg-hub cfg-group-view">
      <SettingsNotice s={s} testId={`${testIdPrefix}-notice`} />
      <SettingsBrowser s={s} entities={entities} groupNav="chips" embedded={testIdPrefix} onPickEntity={pickEntity} />
    </div>
  );
}

export default function IncentiveSchemeView({ focusKey = "", focusGroup = "", focusNonce = 0, onFocusConsumed } = {}) {
  const { canWrite, selectedEntity, entities } = useEntityScope();
  const lihat = canCurrent("sales_force", "view");
  const siap = lihat && canWrite;
  const [infoGrup, setInfoGrup] = useState(INFO_AWAL);   // M3/M5 — kemampuan tarif grup & dasar harga aturan grup
  // R16 — cabang tanpa izin tidak punya bagian pengaturan: permintaan fokus dilepas. ("Semua PT" punya bagian pengaturan
  // grup — fokusnya diteruskan ke sana.)
  useEffect(() => {
    if (focusNonce && !lihat && onFocusConsumed) onFocusConsumed();
  }, [focusNonce, lihat]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!lihat) {
    return (
      <div className="space-y-4" data-testid="incentive-scheme-view">
        <p className="text-fs-13 text-kn-text-2" data-testid="scheme-no-access">{TEKS_TANPA_LIHAT}</p>
      </div>
    );
  }
  if (!siap) {
    // R15 — rute pohon tarif menolak "Semua PT"; tarif tingkat grup tetap bisa diubah lewat pop-up yang sama.
    return (
      <div className="space-y-4" data-testid="incentive-scheme-view">
        <EntityRequiredNotice what="skema & tarif komisi" reason={TEKS_SEMUA_PT} when testId="scheme-all-pt" />
        <Bagian icon={Coins} judul="Tarif Semua PT" testId="scheme-group-rates-card"
          help="Tarif tingkat grup: berlaku untuk setiap PT yang tidak punya tarif sendiri di tingkat yang sama. Tarif baru untuk Semua PT dibuat dari satu PT (pop-up tarif › Berlaku untuk: Semua PT).">
          <GroupRatesList bolehUbahGrup={infoGrup.lintasPt} dasarHarga={infoGrup.dasarHarga} />
        </Bagian>
        <BagianPengaturanGrup entities={entities} cfgFocus={{ focusKey, focusGroup, focusNonce, onFocusConsumed }}
          onInfo={setInfoGrup} />
      </div>
    );
  }
  // `key` = PT: berganti PT memasang ulang seluruh isi (cakupan Pusat Pengaturan tertanam dipilih saat dipasang).
  return <IsiSkema key={selectedEntity} entityId={selectedEntity} entities={entities}
    cfgFocus={{ focusKey, focusGroup, focusNonce, onFocusConsumed }} />;
}

/** Cara menghitung komisi (`commission.strategy`) yang berlaku: PT (`entityId`) atau aturan grup ("all"). Label dari opsi
 *  registri (bukan kode mentah); galat baca ditulis (R16). */
function useStrategi(entityId) {
  const [strategi, setStrategi] = useState("");
  const [opsi, setOpsi] = useState([]);
  const [err, setErr] = useState("");
  const [muat, setMuat] = useState(0);
  useEffect(() => {
    let hidup = true;
    axios.get(`${API}/config/explain`, { params: { key: KUNCI_STRATEGI, entity_id: entityId === "all" ? "" : entityId } })
      .then((r) => { if (hidup) { setStrategi(r.data?.value || ""); setOpsi(r.data?.entry?.options || []); setErr(""); } })
      .catch((e) => { if (hidup) { setStrategi(""); setErr(apiErrorText(e) || ""); } });
    return () => { hidup = false; };
  }, [entityId, muat]);
  return { strategi, setStrategi, label: opsi.find((o) => o.value === strategi)?.label || "", err,
    ulang: () => setMuat((n) => n + 1) };
}

/** R15 — bagian tertutup "Lanjutan": `commission.strategy` (Pusat Pengaturan tertanam). Mesin pengaturan baru dipasang saat
 *  dibuka; deep link ke kunci strategi membukanya. Nilai yang termuat diteruskan ke induk (jenjang arsip tampil/hilang). */
function BagianLanjutan({ entityId, entities, grup, strategi, labelStrategi, stratErr, onRetry, onStrategi, cfgFocus }) {
  const fokusDiSini = bagianUntukKunci(cfgFocus.focusKey) === "lanjutan";
  const [buka, setBuka] = useState(fokusDiSini);
  useEffect(() => { if (cfgFocus.focusNonce && fokusDiSini) setBuka(true); }, [cfgFocus.focusNonce, fokusDiSini]);
  return (
    <section className="section-card" data-testid="scheme-advanced">
      <div className="section-head">
        <button type="button" className="ghost-button text-left" aria-expanded={buka} data-testid="scheme-advanced-toggle"
          onClick={() => setBuka((v) => !v)}>
          {buka ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
          <Settings2 size={14} className="text-kn-action" aria-hidden="true" />
          <span className="font-bold text-kn-text">Lanjutan</span>
          <span className="font-normal text-kn-text-2">{strategi && labelStrategi ? `· Cara menghitung komisi: ${labelStrategi}` : ""}</span>
        </button>
      </div>
      {stratErr && (
        <div className="section-pad">
          <ErrorNotice testId="scheme-strategy-error" message={`Cara menghitung komisi PT ini tidak bisa dibaca. ${stratErr}`.trim()}
            onRetry={onRetry} />
        </div>
      )}
      {buka && (
        <div className="section-body space-y-2">
          <p className="text-fs-12 text-kn-text-2" data-testid="scheme-advanced-help">{TEKS_STRATEGI_LANJUTAN}</p>
          <PengaturanStrategi entityId={entityId} entities={entities} grup={grup} onStrategi={onStrategi} cfgFocus={cfgFocus} />
        </div>
      )}
    </section>
  );
}

function PengaturanStrategi({ entityId, entities, grup, onStrategi, cfgFocus }) {
  const s = useSettingsBrowser({ selectedEntity: entityId, groupIds: grup, includeKeys: KUNCI_BAGIAN.lanjutan,
    focusWithoutSearch: true, ...(bagianUntukKunci(cfgFocus.focusKey) === "lanjutan" ? cfgFocus : {}) });
  const nilai = (s.items || []).find((i) => i.key === KUNCI_STRATEGI)?.value;
  useEffect(() => { if (nilai) onStrategi(nilai); }, [nilai]); // eslint-disable-line react-hooks/exhaustive-deps
  // nilai mentah tidak pernah tampil di kepala bagian — label dibaca dari opsi registri (`useStrategi`).
  return <PengaturanBagian s={s} entities={entities} testIdPrefix="scheme-advanced-cfg" />;
}

/** Deep link kunci komisi → hanya bagian yang memuat kuncinya menerima fokus; kunci yang tidak tampil (satuan) langsung
 *  dilepas supaya permintaan fokus tidak menggantung. */
function useFokusKomisi(cfgFocus) {
  const bagianFokus = bagianUntukKunci(cfgFocus.focusKey);
  useEffect(() => {
    if (cfgFocus.focusNonce && !bagianFokus && cfgFocus.onFocusConsumed) cfgFocus.onFocusConsumed();
  }, [cfgFocus.focusNonce]); // eslint-disable-line react-hooks/exhaustive-deps
  return (b) => (bagianFokus === b ? cfgFocus : {});
}

/** Bagian 3–5 pada satu cakupan (`selectedEntity` = PT, atau "all" = aturan grup). Mengembalikan mesin ⑤ (bawaan batas) dan
 *  `onInfo({ lintasPt, dasarHarga })`: kemampuan menulis aturan/tarif grup (`caps.global_write`; null = belum termuat) dan
 *  dasar pengali harga cakupan ini (`commission.price_basis`) — dipakai pop-up tarif (tinjauan akhir M3, M5). */
function BagianPengali({ selectedEntity, entities, grup, fokus, kalimatCakupan, onBatas, onInfo }) {
  // T9 — bagian tertanam tanpa kotak cari: tautan dalam membuka & menggulir kartunya, bukan menulis kunci mentah.
  const harga = useSettingsBrowser({ selectedEntity, groupIds: grup, includeKeys: KUNCI_BAGIAN.harga, focusWithoutSearch: true,
    ...fokus("harga") });
  const capaian = useSettingsBrowser({ selectedEntity, groupIds: grup, includeKeys: KUNCI_BAGIAN.capaian, focusWithoutSearch: true,
    ...fokus("capaian") });
  const batas = useSettingsBrowser({ selectedEntity, groupIds: grup, includeKeys: KUNCI_BAGIAN.batas, focusWithoutSearch: true,
    ...fokus("batas") });
  const bawaanBatas = (batas.items || []).find((i) => i.key === KUNCI_BATAS)?.value;
  useEffect(() => { if (onBatas) onBatas(bawaanBatas); }, [bawaanBatas]); // eslint-disable-line react-hooks/exhaustive-deps
  const lintasPt = harga.loading ? null : harga.caps?.global_write === true;
  const dasarHarga = (harga.items || []).find((i) => i.key === KUNCI_DASAR_HARGA)?.value || "";
  useEffect(() => { if (onInfo) onInfo({ lintasPt, dasarHarga }); }, [lintasPt, dasarHarga]); // eslint-disable-line react-hooks/exhaustive-deps
  // R16 — aturan grup hanya untuk peran lintas PT (`caps.global_write`, sama dengan hub Pusat Pengaturan): kartu hanya baca.
  const grupTerkunci = selectedEntity === "all" && !harga.loading && !harga.denied && !harga.caps?.global_write;
  return (
    <>
      <Bagian nomor={3} icon={SlidersHorizontal} judul="Pengali harga" testId="scheme-price-card"
        help="Komisi dikalikan menurut seberapa jauh harga jual di bawah harga acuan (atau menurut diskon baris, cara lama). Artikel boleh punya pita sendiri di pop-up tarifnya.">
        <p className="text-fs-12 text-kn-text-2" data-testid="scheme-settings-scope">{kalimatCakupan}</p>
        {grupTerkunci && <p className="text-fs-12 text-kn-warning-text" data-testid="scheme-group-readonly">{TEKS_GRUP_TERKUNCI}</p>}
        <PengaturanBagian s={harga} entities={entities} testIdPrefix="scheme-price-cfg" />
      </Bagian>

      <Bagian nomor={4} icon={Gauge} judul="Pengali capaian" testId="scheme-achievement-card"
        help="Opsional: komisi bulan itu dikalikan menurut capaian target bulanan sales.">
        <PengaturanBagian s={capaian} entities={entities} testIdPrefix="scheme-achievement-cfg" />
      </Bagian>

      <Bagian nomor={5} icon={Shield} judul="Batas margin" testId="scheme-cap-card"
        help="Bawaan batas margin untuk tarif baru. Batas tiap tarif tampil dan diubah di baris tarifnya (bagian 2).">
        <PengaturanBagian s={batas} entities={entities} testIdPrefix="scheme-cap-cfg" />
      </Bagian>
    </>
  );
}

/** Mode "Semua PT" — bagian 3–5 dan Lanjutan pada cakupan aturan grup (nilai untuk PT yang tidak punya nilai sendiri),
 *  boleh diubah menurut izin kunci di registri. */
function BagianPengaturanGrup({ entities, cfgFocus, onInfo }) {
  const fokus = useFokusKomisi(cfgFocus);
  const st = useStrategi("all");
  const grup = [groupForKey(KUNCI_BAGIAN.harga[0])].filter(Boolean);
  return (
    <>
      <BagianPengali selectedEntity="all" entities={entities} grup={grup} fokus={fokus} onInfo={onInfo}
        kalimatCakupan={<>Bagian 3–5 dan Lanjutan di bawah adalah <b>aturan grup (Semua PT)</b>: berlaku untuk setiap PT yang tidak punya nilai sendiri. Nilai khusus satu PT diubah sesudah memilih PT itu.</>} />
      <BagianLanjutan entityId="all" entities={entities} grup={grup} strategi={st.strategi} labelStrategi={st.label}
        stratErr={st.err} onRetry={st.ulang} onStrategi={st.setStrategi} cfgFocus={cfgFocus} />
    </>
  );
}

function IsiSkema({ entityId, entities, cfgFocus }) {
  const pt = entityFullById(entities, entityId, "PT ini");
  const ptPendek = entityShortById(entities, entityId, "pt");
  const [sakelar, setSakelar] = useState({ state: "loading", mode: "", roster: [], err: "" });
  const st = useStrategi(entityId);
  const strategi = st.strategi;

  const fokus = useFokusKomisi(cfgFocus);
  const grup = [groupForKey(KUNCI_BAGIAN.harga[0])].filter(Boolean);
  const [bawaanBatas, setBawaanBatas] = useState(undefined);   // ⑤ — isian awal batas margin tarif baru
  const [info, setInfo] = useState(INFO_AWAL);                 // M3/M5 — "Semua PT" di pop-up tarif & petunjuk pita

  /** `diam` = muat ulang sesudah menyimpan: kartu tidak berganti "Memuat…" (pesan simpan & kartu akrual tetap). */
  const muatSakelar = useCallback(async (diam = false) => {
    if (!diam) setSakelar((s) => ({ ...s, state: "loading" }));
    try {
      const r = await axios.get(`${API}/incentive/targets`, { params: { period_type: "month" } });
      setSakelar({ state: "ready", mode: r.data?.commission_mode || "", roster: r.data?.roster || [], err: "" });
    } catch (e) {
      // R16 — peran tanpa `incentive.view`: kalimat izin, bukan galat.
      setSakelar({ state: e?.response?.status === 403 ? "denied" : "error", mode: "", roster: [], err: apiErrorText(e) || "" });
    }
  }, []);
  useEffect(() => { muatSakelar(); }, [muatSakelar, entityId]);

  const mode = sakelar.mode;
  const otomatis = sakelar.state === "ready" && komisiOtomatisJalan(mode);
  const labelStrategi = st.label;
  return (
    <div className="space-y-4" data-testid="incentive-scheme-view">
      <EntityScopeBanner testId="scheme-scope" />

      <Bagian nomor={1} icon={Wallet} judul="Sumber insentif" testId="scheme-source-card"
        help="Dari mana insentif sales PT ini dibayar lewat gaji: komisi otomatis dari tarif, Lembar Insentif yang disahkan pimpinan, atau keduanya.">
        {sakelar.state === "loading" ? (
          <p className="text-fs-13 text-kn-text-2" role="status" data-testid="scheme-source-loading">Memuat sumber insentif…</p>
        ) : sakelar.state === "denied" ? (
          <p className="text-fs-13 text-kn-text-2" data-testid="scheme-source-denied">{TEKS_SUMBER_TANPA_IZIN}</p>
        ) : sakelar.state === "error" ? (
          <ErrorNotice testId="scheme-source-load-error" message={`Sumber insentif tidak bisa dimuat. ${sakelar.err}`.trim()} onRetry={() => muatSakelar()} />
        ) : (
          <SchemeSourcePicker entityId={entityId} pt={pt} mode={mode} onSaved={() => muatSakelar(true)} />
        )}
      </Bagian>

      <Bagian nomor={2} icon={Coins} judul="Tarif komisi" testId="scheme-rates-card"
        help="Tarif rupiah per satuan dasar barang (yard). Urutan pencarian: tarif varian → tarif artikel → tarif kategori. Tanpa tarif di ketiganya, baris pesanan itu tidak berkomisi.">
        {sakelar.state === "ready" && !otomatis && (
          <p className="text-fs-12 text-kn-warning-text" data-testid="scheme-rates-unused">{TEKS_TARIF_TIDAK_DIPAKAI}</p>
        )}
        {strategi === STRATEGI_ARSIP && (
          <p className="text-fs-12 text-kn-warning-text" data-testid="scheme-rates-strategy">
            {`Cara menghitung komisi PT ini “${labelStrategi || "Berjenjang dari pencapaian target"}”: tarif di bawah tidak dipakai. Ubah di bagian Lanjutan.`}</p>
        )}
        <p className="text-fs-12 text-kn-text-2" data-testid="scheme-rates-effective">{TEKS_BERLAKU}</p>
        <ArticleRatesTable entityId={entityId} pt={pt} ptPendek={ptPendek} bawaanBatas={bawaanBatas}
          bolehSemuaPt={info.lintasPt === true} dasarHarga={info.dasarHarga} />
      </Bagian>

      <BagianPengali selectedEntity={entityId} entities={entities} grup={grup} fokus={fokus} onBatas={setBawaanBatas} onInfo={setInfo}
        kalimatCakupan={<>Pengaturan bagian 3–5 dan Lanjutan berlaku untuk <b>{pt}</b> (pemilih PT di kanan atas). Aturan grup (Semua PT) diubah dengan memilih "Semua PT" di pemilih PT.</>} />

      {otomatis && (
        <Bagian icon={Percent} judul="Akrual komisi bulanan" testId="scheme-accrual-card"
          help="Membukukan beban komisi otomatis bulan itu ke buku PT (Beban Insentif Penjualan / Hutang Insentif Penjualan).">
          <KartuAkrual canWrite mode={mode} pt={pt} />
        </Bagian>
      )}

      {strategi === STRATEGI_ARSIP && <LegacySchemeEditor />}

      <BagianLanjutan entityId={entityId} entities={entities} grup={grup} strategi={strategi} labelStrategi={labelStrategi}
        stratErr={st.err} onRetry={st.ulang} onStrategi={st.setStrategi} cfgFocus={cfgFocus} />

      <Bagian icon={Calculator} judul="Simulasi" testId="scheme-sim-card"
        help="Coba dulu: komisi seorang sales pada satu bulan dengan aturan sekarang dibanding dengan tarif percobaan. Tidak menyimpan apa pun.">
        <SchemeSimulation entityId={entityId} roster={sakelar.state === "ready" ? sakelar.roster : null}
          rosterAlasan={sakelar.state === "denied" ? TEKS_SALES_TANPA_IZIN : ""} />
      </Bagian>
    </div>
  );
}
