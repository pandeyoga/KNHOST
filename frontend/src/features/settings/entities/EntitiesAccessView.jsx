/**
 * EntitiesAccessView (FASE E-3) — SATU PINTU untuk badan usaha & hak akses.
 *
 * KP-T9 — layar ini kini dibuka SATU BAGIAN per tab hub (prop `only`, AppViewRouter): Pengaturan › Perusahaan (PT) ›
 * Profil PT (`entities`) · Kesiapan PT (`readiness`); Pengaturan › Pengguna & Hak Akses › Akun (`accounts`) · Peran & Hak
 * Akses (`roles`) · Cek Peran (`role-reality`). Dengan `only` bilah tab dalam tidak dirender; isi tiap bagian tidak
 * berubah. Preset navigasi dibaca dari id tab hub bagian itu (`PART_VIEW`).
 *
 * Mengganti tab "Entities" dan "Users" lama di Master Data. Tab lama DIHAPUS
 * (bukan dibiarkan hidup berdampingan) supaya tidak ada dua pintu yang bisa
 * saling bertentangan — dulu formulir lama bisa mengetik `home_entity_id` bebas
 * sehingga bertentangan dengan data HR.
 *
 * Tiga tab:
 *   Badan Usaha · Akun & Akses · Kesiapan
 *
 * KP-T2 — tombol "Lengkapi" (`EntityCompletionSteps`) membuka layar ini lewat preset navigasi `{tab, entity_id}`:
 * tab tujuan dipilih dan, untuk tab Badan Usaha, detail PT itu dibuka. Wizard tidak menutup setelah simpan — ia
 * menampilkan langkah "Lengkapi PT"; Selesai menutup dan membuka detail PT baru.
 */
import { useCallback, useEffect, useState } from "react";
import { can } from "../../../config/roles";
import { Building2, Users, ClipboardCheck, Plus, RefreshCw, UserCheck, ShieldCheck } from "lucide-react";

import ErrorNotice from "../../../components/ErrorNotice";
import PageTabs from "../../../components/PageTabs";
import { HelpTip } from "../../../components/ListPageParts";
import DesktopOnlyNotice from "../../../components/DesktopOnlyNotice";
import EntityList from "./EntityList";
import EntityWizard from "./EntityWizard";
import EntityDetailDrawer from "./EntityDetailDrawer";
import AccountList from "./AccountList";
import RoleRealityPanel from "./RoleRealityPanel";
import RoleAccessPanel from "./RoleAccessPanel";
import EntityReadinessPanel from "./EntityReadinessPanel";
import { listEntities, errText } from "./entityApi";
import useViewPreset from "../../../hooks/useViewPreset";
import { useAppNav } from "../../../context/AppNavContext";

// PR-T6 — `need` = izin yang membuka tab (tanpa izin tab tidak tampil; dulu tampil lalu 403).
const TABS = [
  { key: "entities", label: "Badan Usaha", icon: Building2 },
  { key: "accounts", label: "Akun & Akses", icon: Users, need: ["user", "view"] },
  // Peran kustom & tingkat akses per modul — diatur admin dari layar ini.
  { key: "roles", label: "Peran & Hak Akses", icon: ShieldCheck, need: ["permission", "view"] },
  // Utang migrasi (ii) E-8 — tab ini menjawab "peran siapa yang tidak cocok dengan
  // pekerjaannya", dihitung dari jejak nyata. Letaknya SETELAH "Akun & Akses"
  // karena ia menilai isi tab itu.
  { key: "role-reality", label: "Cek Peran", icon: UserCheck, need: ["permission", "view"] },
  { key: "readiness", label: "Kesiapan", icon: ClipboardCheck },
];

/** KP-T9 — bagian → id tab hub yang merendernya (preset navigasi & tautan antarbagian). */
export const PART_VIEW = { entities: "settings-pt-profile", readiness: "settings-pt-readiness", accounts: "settings-accounts",
  roles: "permission-matrix", "role-reality": "settings-role-check" };
/** Modul akses yang membuka bagian ber-`need` (kalimat bila bagian dibuka tanpa izin). */
const PART_MODULE = { accounts: "Akun Pengguna", roles: "Peran & Hak Akses", "role-reality": "Peran & Hak Akses" };
/** Isi ikon ? (dulu pita penjelas permanen di atas setiap bagian). */
const INTRO = "Satu grup, beberapa PT — buku keuangan, pajak, harga, dan pelanggan tiap PT terpisah. Karyawan hanya "
  + "melihat data PT tempat dia ditugaskan. PT utama akun diambil dari data karyawan (HR) supaya penggajian dan hak "
  + "akses tidak pernah bertentangan.";

export default function EntitiesAccessView({ currentUser, selectedEntity, onNavigate, initialTab = "entities", only = "" }) {
  const perms = currentUser?.permissions;
  const nav = useAppNav();
  const part = TABS.some((t) => t.key === only) ? only : "";
  const allowed = TABS.filter((t) => !t.need || can(perms, t.need[0], t.need[1]));   // PR-T6
  const tabs = part ? allowed.filter((t) => t.key === part) : allowed;
  const [tabState, setTab] = useState(part || initialTab);
  const tab = tabs.some((t) => t.key === tabState) ? tabState : (tabs[0]?.key || (part ? "" : "entities"));
  const [entities, setEntities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [wizardOpen, setWizardOpen] = useState(false);
  const [detailId, setDetailId] = useState("");
  const [flash, setFlash] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  // FE-04 — izin efektif per aksi (badan usaha / matriks peran), bukan nama peran Admin.
  const canCreateEntity = can(perms, "entity", "create");
  const canEditEntity = can(perms, "entity", "update");
  const canEditRoles = can(perms, "permission", "update");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // status=all: layar pengelolaan HARUS bisa melihat yang terarsip juga,
      // berbeda dari pemilih entitas yang hanya menampilkan yang aktif.
      const rows = await listEntities({ status: "all", with_readiness: true });
      setEntities(rows);
      setError("");
    } catch (e) {
      setError(errText(e, "Gagal memuat daftar badan usaha."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load, reloadKey]);

  const refreshAll = () => setReloadKey((k) => k + 1);

  // KP-T2 — tautan "Lengkapi" dari daftar kesiapan: tab tujuan (+ detail PT untuk tab Badan Usaha). Detail hanya dibuka
  // bila PT itu memang PT aktif (preset juga diterapkan ulang saat layar dipasang ulang karena ganti PT).
  // KP-T9 — dengan `only`, preset dibaca dari id tab hub bagian ini (mis. Profil PT `{entity_id}` dari "Lengkapi").
  useViewPreset(part ? PART_VIEW[part] : "entities-access", (p) => {
    const want = part || p.tab;
    if (!part && p.tab && TABS.some((t) => t.key === p.tab)) setTab(p.tab);
    setWizardOpen(false);
    setDetailId(want === "entities" && p.entity_id && p.entity_id === selectedEntity ? p.entity_id : "");
  });
  // Tombol "buka Akun" dari Peran & Hak Akses: tab dalam bila layar utuh, tab hub Akun bila dibuka per bagian.
  const openAccounts = part
    ? (nav.canOpen(PART_VIEW.accounts) ? () => nav.go(PART_VIEW.accounts) : undefined)
    : (tabs.some((t) => t.key === "accounts") ? () => setTab("accounts") : undefined);

  // Pola UI 16 Nov (M43) — Peran & Hak Akses punya bilah daftarnya sendiri (cari · ? · muat ulang · + Buat Peran Baru);
  // bilah atas layar ini tidak dirender di bagian itu supaya tombol muat ulang tidak sendirian di satu baris.
  const ownToolbar = tab === "roles";
  return (
    <div data-testid="entities-access-view">
      <DesktopOnlyNotice testId="settings-desktop-notice" what="Pengaturan" />

      {/* Fase 3 · P2 (L-01) — pil buatan sendiri → PageTabs baku (tingkat 2); testid `entities-access-tab-<key>` tetap.
          KP-T9 — dibuka per bagian (`only`): tanpa bilah tab dalam, tombol tetap di bilahnya sendiri.
          Pola UI 16 Nov (M43) — pita penjelas "Satu grup, beberapa PT …" pindah ke ikon ? di bilah yang sama. */}
      {!part || !ownToolbar ? (
        <div className="mb-3 flex flex-wrap items-center gap-1.5">
          {!part && (
            <div className="min-w-0 flex-1">
              <PageTabs testId="entities-access-tabs" tabTestId={(k) => `entities-access-tab-${k}`} value={tab} onChange={setTab}
                ariaLabel="Badan Usaha & Akses" tabs={tabs.map((t) => ({ key: t.key, label: t.label, icon: t.icon }))} />
            </div>
          )}
          <HelpTip text={INTRO} testId="entities-access-intro" label="Tentang PT & hak akses" />
          <div className="ml-auto flex items-center gap-2">
            {tab === "entities" && canCreateEntity && (
              <button
                type="button"
                className="primary-button"
                data-testid="entity-add-button"
                onClick={() => setWizardOpen(true)}
              >
                <Plus size={14} /> Tambah PT
              </button>
            )}
            {!ownToolbar && (
              <button
                type="button"
                className="icon-button"
                data-testid="entities-access-refresh"
                aria-label="Muat ulang"
                onClick={refreshAll}
              >
                <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
              </button>
            )}
          </div>
        </div>
      ) : null}

      {flash && (
        <div className="notice-bar success !py-1.5 mb-2" data-testid="entities-access-flash">
          <span className="text-[11.5px]">{flash}</span>
        </div>
      )}
      <ErrorNotice
        message={error}
        onRetry={refreshAll}
        onDismiss={() => setError("")}
        testId="entities-access-error"
      />

      {tab === "entities" && (
        <EntityList
          entities={entities}
          loading={loading}
          canManage={canEditEntity}
          onOpen={(id) => setDetailId(id)}
          onChanged={(msg) => { setFlash(msg); refreshAll(); }}
          onError={setError}
        />
      )}

      {tab === "accounts" && (
        <AccountList
          entities={entities}
          currentUser={currentUser}
          selectedEntity={selectedEntity}
          onChanged={(msg) => { setFlash(msg); refreshAll(); }}
          onError={setError}
        />
      )}

      {part && !tab && (
        <p className="section-card section-pad flex items-center gap-2 text-fs-13 text-kn-text-2" data-testid="entities-access-no-part">
          <ShieldCheck size={14} aria-hidden="true" className="shrink-0 text-kn-text-2" />
          Anda belum punya akses untuk membuka bagian ini. Minta Admin menambahkan akses &lsquo;{PART_MODULE[part]}&rsquo;.
        </p>
      )}

      {tab === "roles" && (
        <RoleAccessPanel
          canManage={canEditRoles}
          onChanged={(msg) => { setFlash(msg); window.dispatchEvent(new CustomEvent("kn:roles-changed")); }}
          onError={setError}
          onOpenAccounts={openAccounts}
        />
      )}

      {tab === "role-reality" && (
        <RoleRealityPanel
          canManage={canEditRoles}
          onChanged={(msg) => { setFlash(msg); refreshAll(); }}
          onError={setError}
        />
      )}

      {tab === "readiness" && (
        <EntityReadinessPanel
          entities={entities}
          selectedEntity={selectedEntity}
          canManage={canEditEntity}
          onError={setError}
        />
      )}

      {wizardOpen && (
        <EntityWizard
          entities={entities}
          canManage={canEditEntity}
          onClose={() => setWizardOpen(false)}
          onCreated={(ent) => {
            // KP-T2 — wizard tetap terbuka (langkah "Lengkapi PT"); daftar dimuat ulang supaya PT baru ikut tampil.
            setFlash(
              `Badan usaha “${ent.legal_name || ent.name}” dibuat. Nomor dokumennya akan ` +
              `berawalan ${ent.provisioning?.number_preview || ent.doc_prefix}.`
            );
            refreshAll();
          }}
          onDone={(ent) => {
            setWizardOpen(false);
            if (ent?.id) setDetailId(ent.id);
          }}
        />
      )}

      {detailId && (
        <EntityDetailDrawer
          entityId={detailId}
          canManage={canEditEntity}
          onClose={() => setDetailId("")}
          onChanged={(msg) => { setFlash(msg); refreshAll(); }}
          onNavigate={onNavigate}
        />
      )}
    </div>
  );
}
