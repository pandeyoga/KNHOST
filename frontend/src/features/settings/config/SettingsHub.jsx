/**
 * SettingsHub — **PUSAT PENGATURAN** (FASE G-0, frontend).
 *
 * Menyelesaikan 5 masalah nyata yang dikonfirmasi audit 2026-07-26:
 *   1. Konfigurasi tersebar di **13 permukaan editor** dengan 13 bentuk API → satu pintu.
 *   2. **31 aturan tersembunyi** (dipakai mesin, tanpa UI) → SEMUA setting di registry dirender otomatis.
 *   3. **6 tombol palsu** (UI tanpa pembaca kode) → tab Kesehatan Konfigurasi.
 *   4. Tak ada penjelasan/jejak/riwayat → tiap kartu punya "Artinya", "Kalau diubah", contoh angka,
 *      "Kenapa nilainya begini?", "Coba dulu", "Riwayat".
 *   5. Tak ada berlaku-sejak → setiap perubahan bisa dijadwalkan.
 *
 * IA: kelompok disusun berdasarkan **PERTANYAAN BISNIS** (bukan nama modul).
 *
 * Fase 3 · P2 (keputusan pemilik P16-K1) — layar ini kini "Semua pengaturan" (Pengaturan › Integrasi & Sistem).
 * Mesinnya diekspor (`useSettingsBrowser` + `SettingsBrowser`) supaya tiap kelompok menu domain merender Pusat
 * Pengaturan yang DIKUNCI ke kelompok registrinya (`SettingsGroupView` / `settings-cfg-*`) dan Komisi & Insentif
 * merender kunci `commission.*` (D-03) — satu mesin, tanpa salinan form. Kunci komisi disembunyikan di tempat lain
 * (+ tautan) supaya tidak tampil ganda. Tab "Koreksi Harga" pindah ke Produk & Harga (`price-corrections`).
 * Sumber data: /api/config/registry · /effective · /explain · /simulate · /values · /values/reset · /history · /health
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  SlidersHorizontal, ShieldCheck, History, Loader2, RefreshCw, Lock, Sparkles, Wand2,
} from "lucide-react";
import PageTabs from "../../../components/PageTabs";
import LinkCard from "../../../components/LinkCard";
import DesktopOnlyNotice from "../../../components/DesktopOnlyNotice";
import { SettingsNotice } from "./SettingsScopeBar";
import SettingsBrowser from "./SettingsBrowser";
import ConfigHealthPanel from "./ConfigHealthPanel";
import SagaLocksPanel from "./SagaLocksPanel";
import DataHygienePanel from "./DataHygienePanel";
import LocationBacklogPanel from "./LocationBacklogPanel";
import { ChangeHistoryDrawer, ChangeHistoryInline } from "./ConfigDrawers";
import { cleanCfgText, configApi, errMsg, formatValue } from "./configApi";
import { groupForKey, resolveGroupId, sectionForKey } from "./configDeepLink";
import { COMMISSION_PREFIX } from "./configGroupViews";
import { entityShortById } from "../../../utils/entityLabel";
import { can, canCurrent } from "../../../config/roles";
import { askConfirm, askReason } from "../../../services/confirmService";

const TABS = [
  { k: "settings", label: "Pengaturan", icon: SlidersHorizontal },
  { k: "health", label: "Kesehatan Pengaturan", icon: ShieldCheck, perm: ["settings", "view"] },
  { k: "history", label: "Riwayat Perubahan", icon: History },
  { k: "saga", label: "Kunci Proses", icon: Lock, adminOnly: true },
  { k: "hygiene", label: "Kebersihan Data", icon: Sparkles },
];

/** Kunci komisi (D-03) disembunyikan dari Semua pengaturan & Aturan Penjualan — rumahnya Komisi & Insentif. */
export const COMMISSION_EXCLUDE = [COMMISSION_PREFIX];
export const COMMISSION_LINK = {
  testId: "cfg-commission-link", what: "Bawaan komisi sales", view: "incentive-rates",
  where: "SDM › Kinerja & Insentif › Target & Aturan",   // MN-T1 — dulu Pengaturan › Penjualan › Komisi & Insentif
};

/** Pita simpan/galat + mesin tampilan daftar (re-export agar impor lama — `SettingsGroupView`, uji — tidak patah).
 *  KF-T4 — `LEGACY_DEEPLINK` dihapus: kelompok kunci dibaca dari `configKeyIndex.json` (`configDeepLink.js`). */
export { SettingsNotice, SettingsBrowser };

const byPrefix = (list, key) => (list || []).some((p) => String(key || "").startsWith(p));

/**
 * Mesin data Pusat Pengaturan. `groupIds` mengunci kelompok (layar domain); `includeKeys`/`excludeKeys` = prefiks
 * kunci yang ditampilkan/disembunyikan. Pencarian di layar terkunci hanya mencari di kelompoknya sendiri.
 */
export function useSettingsBrowser({
  selectedEntity, groupIds = null, includeKeys = null, excludeKeys = null,
  focusKey = "", focusGroup = "", focusSection = "", focusNonce = 0, onFocusConsumed,
}) {
  // KF-T4 — layar yang mengunci id kelompok LAMA (Komisi & Insentif `harga-diskon`, Kebijakan Retur `retur`, Jadwal Bayar
  // antar-PT `antar-entitas`) tetap jalan: id lama diterjemahkan ke kelompok barunya (`GROUP_ALIASES`).
  const allowKey = (groupIds || []).flatMap((g) => [g, resolveGroupId(g).group]).filter(Boolean).join("|");
  const allow = useMemo(() => (allowKey ? new Set(allowKey.split("|")) : null), [allowKey]);
  const keyOk = useCallback((key) => (!includeKeys || byPrefix(includeKeys, key)) && !byPrefix(excludeKeys, key),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [(includeKeys || []).join("|"), (excludeKeys || []).join("|")]);
  const [groups, setGroupsRaw] = useState([]);
  const [group, setGroup] = useState("");
  const [items, setItems] = useState([]);
  const [hiddenCount, setHiddenCount] = useState(0);
  const [q, setQ] = useState("");
  const [term, setTerm] = useState("");           // q yang sudah di-debounce
  // FASE E-4 (E4.6) — scope BAWAAN = badan usaha aktif, bukan global (pita di atas kartu menyebut nilai siapa).
  const singleEntity = selectedEntity && selectedEntity !== "all" ? selectedEntity : "";
  const [scopeType, setScopeType] = useState(singleEntity ? "entity" : "global");
  const [scopeId, setScopeId] = useState(singleEntity);
  const [health, setHealth] = useState({});       // key -> row wiring
  // Kemampuan NYATA user menurut server (GET /api/config/registry → caps), bukan tebakan dari role.
  const [caps, setCaps] = useState({ settings_manage: false, impact_apply: false });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // KF-T1 — server menolak membaca (403): keadaan kosong berpesan, bukan galat merah + "Coba lagi".
  const [denied, setDenied] = useState("");
  const [notice, setNotice] = useState(null);     // {msg, tone}
  const [why, setWhy] = useState(null);
  const [sim, setSim] = useState(null);           // {entry, draft}
  const [hist, setHist] = useState(null);         // {entry} | {group} | {} = semua
  const cardRefs = useRef({});
  const counts = useRef(null);                    // id kelompok → jumlah kunci yang tampil (sesudah saringan kunci)
  // KF-T4 — saringan kartu (Semua · Sudah diubah · Risiko tinggi · tiga tema), kartu ringkas yang terbuka, kartu
  // berdraf (peringatan meninggalkan kelompok), sub-judul tujuan tautan, dan "Pulihkan nilai ini" dari riwayat.
  const entitiesRef = useRef([]);                 // nama PT untuk kalimat dialog (diisi SettingsBrowser)
  const [filter, setFilter] = useState("all");
  const [openKeys, setOpenKeys] = useState(() => new Set());
  const dirtyKeys = useRef(new Set());
  const [section, setSection] = useState("");
  const [restore, setRestore] = useState(null);
  const onDirty = useCallback((key, d) => { if (d) dirtyKeys.current.add(key); else dirtyKeys.current.delete(key); }, []);
  const toggleOpen = useCallback((key) => setOpenKeys((cur) => {
    const n = new Set(cur);
    if (n.has(key)) n.delete(key); else n.add(key);
    return n;
  }), []);

  // Kelompok yang boleh tampil di layar ini, dengan jumlah kunci SESUDAH saringan prefiks.
  const setGroups = useCallback((list) => setGroupsRaw((list || [])
    .filter((g) => !allow || allow.has(g.id))
    .map((g) => (counts.current && counts.current[g.id] !== undefined ? { ...g, count: counts.current[g.id] } : g))
    .filter((g) => !counts.current || g.count > 0 || !(includeKeys || excludeKeys))), [allow, includeKeys, excludeKeys]);

  const flash = useCallback((msg, tone = "ok") => {
    setNotice({ msg, tone });
    window.clearTimeout(flash._t);
    flash._t = window.setTimeout(() => setNotice(null), tone === "err" ? 7000 : 4500);
  }, []);

  // KF-T4 (KF-UX-09) — cakupan grup = nilai grup TANPA lapisan PT (dulu tetap dihitung untuk PT aktif).
  const ctx = useMemo(
    () => ({ entity_id: scopeType === "entity" ? scopeId : "" }),
    [scopeType, scopeId]
  );

  useEffect(() => {
    const t = window.setTimeout(() => setTerm(q.trim()), 280);
    return () => window.clearTimeout(t);
  }, [q]);

  /* muat katalog grup + peta kesehatan sekali (Audit UI 097 — katalog TIDAK menunggu peta kesehatan) */
  useEffect(() => {
    let alive = true;
    // Fase 4 · R5 — `/config/health` dijaga `settings.view`: peran baca-saja (sales/Admin Sales di "Semua pengaturan",
    // layar Pengaturan domain) dulu menembaknya di latar → 403 ×2 per layar. Hanya dipanggil bila izinnya ada; tanpa
    // peta kesehatan kartu tetap tampil (lencana wiring memang hanya untuk pemegang izin).
    if (canCurrent("settings", "view")) configApi.health().then((hp) => {
      if (!alive) return;
      const map = {};
      (hp.rows || []).forEach((r) => { map[r.key] = r; });
      setHealth(map);
    }).catch(() => {});
    (async () => {
      try {
        const reg = await configApi.registry();
        if (!alive) return;
        if (Array.isArray(reg.entries) && (includeKeys || excludeKeys)) {
          const c = {};
          reg.entries.filter((e) => keyOk(e.key)).forEach((e) => { c[e.group] = (c[e.group] || 0) + 1; });
          counts.current = c;
        }
        setGroups(reg.groups || []);
        setCaps(reg.caps || { settings_manage: false, impact_apply: false });
        if (reg.caps && !reg.caps.global_write && singleEntity) { setScopeType("entity"); setScopeId(singleEntity); }
        const first = (reg.groups || []).find((g) => (!allow || allow.has(g.id))
          && (!counts.current || counts.current[g.id] > 0));
        if (!first) setLoading(false);
        // Fungsional: deep-link yang sudah menetapkan kelompok sebelum registry selesai tidak boleh ditimpa.
        else setGroup((cur) => cur || first.id);
      } catch (e) {
        if (!alive) return;
        if (e?.response?.status === 403) setDenied(errMsg(e, "Anda belum punya akses untuk melihat pengaturan."));
        else setError(errMsg(e, "Gagal memuat katalog pengaturan."));
        setLoading(false);
      }
    })();
    return () => { alive = false; };
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, []);

  /* ── Deep-link dari layar lain (event global `kn-open-config`) ───────────
   * `focusNonce` berubah tiap permintaan; parent membersihkan state-nya (onFocusConsumed) sesudah diserap.
   * UAT 24 Okt (G5-61) — deep-link berisi kelompok saja MENYARING daftar kelompok (+ "Tampilkan semua kelompok"). */
  const [highlight, setHighlight] = useState("");
  const [pendingScroll, setPendingScroll] = useState("");
  const [lockedGroup, setLockedGroup] = useState("");

  useEffect(() => {
    if (!focusNonce) return;
    const key = focusKey || "";
    // KF-T4 — id kelompok lama diterjemahkan (`GROUP_ALIASES`); sub-judul tujuan ikut dibuka.
    const tujuan = focusGroup ? resolveGroupId(focusGroup) : { group: groupForKey(key), section: sectionForKey(key) };
    let g = tujuan.group;
    if (allow && g && !allow.has(g)) g = "";
    if (g) setGroup(g);
    setSection(focusSection || tujuan.section || "");
    setLockedGroup(!key && g && (!allow || allow.size > 1) ? g : "");
    setQ(key); setTerm(key);            // lewati debounce: hasil harus langsung muncul
    setPendingScroll(key); setHighlight(key);
    if (key) setOpenKeys((cur) => new Set([...cur, key]));
    if (typeof onFocusConsumed === "function") onFocusConsumed();
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [focusNonce]);

  useEffect(() => {
    if (!highlight) return undefined;
    const t = window.setTimeout(() => setHighlight(""), 8000);
    return () => window.clearTimeout(t);
  }, [highlight]);

  // KF-T4 — di "Semua pengaturan" saringan tema berlaku lintas kelompok (semua kunci dimuat lalu disaring).
  const crossTheme = !allow && !term && ["persetujuan", "pengingat", "toleransi"].includes(filter);
  const load = useCallback(async () => {
    if (!group && !term && !crossTheme) return;
    setLoading(true);
    setError("");
    try {
      const d = await configApi.effective({
        ...(term ? { q: term } : crossTheme ? {} : { group }),
        entity_id: ctx.entity_id || "",
        ...(scopeType === "global" ? { scope: "global" } : {}),
      });
      const rows = (d.items || []).filter((it) => !allow || !it.group || allow.has(it.group));
      const kept = rows.filter((it) => keyOk(it.key));
      setHiddenCount(rows.length - kept.length);
      setItems(kept);
      if (d.groups?.length) setGroups(d.groups);
    } catch (e) {
      if (e?.response?.status === 403) setDenied(errMsg(e, "Anda belum punya akses untuk melihat pengaturan."));
      else setError(errMsg(e, "Gagal memuat nilai pengaturan."));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [group, term, ctx.entity_id, scopeType, crossTheme, allow, keyOk]);

  useEffect(() => { load(); }, [load]);

  /* scroll ke kartu yang dituju deep-link setelah data siap */
  useEffect(() => {
    if (!pendingScroll || loading) return;
    const el = cardRefs.current[pendingScroll];
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      setPendingScroll("");
    }
  }, [pendingScroll, loading, items]);

  const onSave = async (payload) => {
    try {
      await configApi.save([payload]);
      flash(payload.effective_from
        ? `Tersimpan. Perubahan akan berlaku mulai ${String(payload.effective_from).slice(0, 10)}.`
        : "Tersimpan dan langsung berlaku di mesin.");
      await load();
      return true;
    } catch (e) {
      flash(errMsg(e, "Gagal menyimpan."), "err");
      return false;
    }
  };
  // KF-T4 (KF-12) — "Pakai nilai bawaan sistem" (grup) / "… untuk PT ini" (nilai khusus PT berisi bawaan). Dialog
  // menyebut akibatnya; alasan wajib bila kunci berisiko tinggi (server menolak tanpa alasan).
  const ptName = (id) => entityShortById(entitiesRef.current, id, "PT ini");
  const onReset = async (item, level = scopeType) => {
    const bawaan = formatValue(item, item.default);
    const label = cleanCfgText(item.label);
    const forPt = level === "entity" && scopeId;
    const reason = await askReason({
      title: forPt ? "Pakai nilai bawaan sistem untuk PT ini" : "Pakai nilai bawaan sistem",
      message: forPt
        ? `Nilai bawaan sistem (${bawaan}) disimpan sebagai nilai khusus ${ptName(scopeId)}. Sesudah itu `
          + `${ptName(scopeId)} tidak lagi mengikuti perubahan nilai grup.`
        : `Nilai grup '${label}' kembali ke bawaan sistem (${bawaan}). Berlaku untuk semua PT yang tidak punya nilai `
          + "sendiri.",
      reasonLabel: "Alasan", reasonRequired: !!item.requires_reason,
      confirmLabel: "Pakai nilai bawaan", cancelLabel: "Batal", testId: "cfg-reset-confirm",
    });
    if (reason === null) return false;
    try {
      await configApi.reset({ key: item.key, scope_type: forPt ? "entity" : "global", scope_id: forPt ? scopeId : "",
        reason });
      flash(`“${label}” memakai nilai bawaan sistem.`);
      await load();
      return true;
    } catch (e) { flash(errMsg(e, "Gagal memakai nilai bawaan sistem."), "err"); return false; }
  };
  // FASE E-4 (E4.6) / KF-T4 — "Ikuti nilai grup": cabut nilai khusus PT → kembali mengikuti nilai grup.
  const onClearEntity = async (item) => {
    if (!scopeId) return false;
    let grup = "";
    try {
      const ex = await configApi.explain({ key: item.key });
      grup = formatValue(item, ex?.stored_value ?? ex?.value);
    } catch (e) { grup = ""; }
    const label = cleanCfgText(item.label);
    const pt = ptName(scopeId);
    const reason = await askReason({
      title: "Ikuti nilai grup",
      message: `'${label}' untuk ${pt} kembali mengikuti nilai grup${grup ? ` (${grup})` : ""}. Nilai khusus ${pt} `
        + `(${formatValue(item, item.overridden_by ? item.stored_value : item.value)}) dicabut.`,
      reasonLabel: "Alasan", reasonRequired: !!item.requires_reason,
      confirmLabel: "Ikuti nilai grup", cancelLabel: "Batal", testId: "cfg-clear-confirm",
    });
    if (reason === null) return false;
    try {
      await configApi.clear({ key: item.key, scope_type: "entity", scope_id: scopeId, reason });
      flash(`“${label}” untuk ${pt} kembali mengikuti nilai grup.`);
      await load();
      return true;
    } catch (e) { flash(errMsg(e, "Gagal mengikuti nilai grup."), "err"); return false; }
  };
  // KF-T4 — meninggalkan kelompok / cakupan dengan draf: tanya dulu.
  const confirmLeave = async () => {
    const n = dirtyKeys.current.size;
    if (!n) return true;
    const ok = await askConfirm({
      title: "Tinggalkan perubahan?", message: `Ada perubahan yang belum disimpan pada ${n} pengaturan. Tinggalkan?`,
      confirmLabel: "Tinggalkan", cancelLabel: "Tetap di sini", testId: "cfg-leave-confirm",
    });
    if (ok) dirtyKeys.current.clear();
    return ok;
  };
  const pickGroup = async (id) => {
    if (id === group && !term) return;
    if (!(await confirmLeave())) return;
    setGroup(id); setQ(""); setSection("");
  };
  const pickEntity = (id) => { setScopeType("entity"); setScopeId(id); };

  // KF-T3 — batalkan satu perubahan berjadwal (nilai yang berlaku sekarang tidak berubah). Alasan wajib bila kuncinya
  // berisiko tinggi (sama dengan aturan server).
  const onCancelScheduled = async (item, sched) => {
    const reason = await askReason({
      title: "Batalkan jadwal",
      message: "Batalkan perubahan terjadwal ini? Nilai yang berlaku sekarang tidak berubah.",
      reasonLabel: "Alasan pembatalan",
      reasonRequired: !!item.requires_reason,
      confirmLabel: "Batalkan jadwal",
      cancelLabel: "Kembali",
      danger: true,
      testId: "cfg-sched-cancel-confirm",
    });
    if (reason === null) return false;
    try {
      await configApi.cancelScheduled({ id: sched.id, reason });
      flash("Jadwal dibatalkan.");
      await load();
      return true;
    } catch (e) {
      flash(errMsg(e, "Gagal membatalkan jadwal."), "err");
      return false;
    }
  };

  return {
    groups, group, setGroup, items, hiddenCount, q, setQ, term, scopeType, setScopeType, scopeId, setScopeId,
    health, caps, loading, error, denied, notice, setNotice, why, setWhy, sim, setSim, hist, setHist, cardRefs,
    highlight, lockedGroup, setLockedGroup, ctx, load, onSave, onReset, onClearEntity, onCancelScheduled,
    locked: !!allow,
    // KF-T4
    filter, setFilter, openKeys, toggleOpen, onDirty, section, setSection, restore, setRestore, pickGroup,
    pickEntity, confirmLeave, setEntities: (list) => { entitiesRef.current = list || []; },
  };
}

export default function SettingsHub({
  currentUser, selectedEntity, entities = [], focusKey = "", focusGroup = "", focusNonce = 0, onFocusConsumed,
}) {
  // PR-T7 (#22b sisa) — tab Kunci Saga (`/saga-locks`) & aksi Data Hygiene (run/revert/unlock) = `system_tools.configure`
  // (server sejak PR-T2; dulu nama peran Admin). Tombol simpan per kunci sudah dari `can_edit` server (KF-T1).
  const isAdmin = can(currentUser?.permissions, "system_tools", "configure");
  // UAT 24 Okt (G5-15) — tab ber-izin (Kesehatan = settings.view) hanya untuk peran pemegangnya. Izin belum termuat → tampil.
  const permOk = (t) => !t.perm || !currentUser?.permissions || can(currentUser.permissions, t.perm[0], t.perm[1]);
  const [tab, setTab] = useState("settings");
  const s = useSettingsBrowser({
    selectedEntity, excludeKeys: COMMISSION_EXCLUDE, focusKey, focusGroup, focusNonce,
    onFocusConsumed: () => { setTab("settings"); onFocusConsumed?.(); },
  });

  return (
    <div className="cfg-hub" data-testid="settings-hub">
      <DesktopOnlyNotice testId="settings-desktop-notice" what="Pengaturan" />
      <header className="cfg-hub-head">
        <div>
          <p className="cfg-sub-lead">
            Semua aturan yang dipakai sistem ada di sini — bisa dicari, dijelaskan, dicoba dulu, dijadwalkan, dan dilihat
            riwayatnya. Tidak perlu developer. Aturan per domain juga tersedia di menu Pengaturan masing-masing.
          </p>
        </div>
        <button className="btn-secondary btn-sm" onClick={s.load} disabled={s.loading} data-testid="cfg-refresh">
          {s.loading ? <Loader2 size={13} className="spin" /> : <RefreshCw size={13} />} Muat ulang
        </button>
      </header>

      {/* L-01 — tab tingkat-2 baku (dulu `.tab-pills` buatan sendiri); testid `cfg-tab-<k>` dipertahankan. */}
      <PageTabs testId="cfg-tabs" value={tab} onChange={setTab} ariaLabel="Tab Pusat Pengaturan"
        tabs={TABS.filter((t) => (!t.adminOnly || isAdmin) && permOk(t))
          .map((t) => ({ key: t.k, label: t.label, icon: t.icon, testId: `cfg-tab-${t.k}` }))} />

      <SettingsNotice s={s} />
      {s.caps.impact_apply ? (
        <LinkCard testId="cfg-price-corrections-link" icon={Wand2} what="Koreksi Harga & Daftar Dampak"
          where="Produk & Harga › Koreksi Harga" view="price-corrections" hideWhenDenied />
      ) : null}

      {tab === "settings" ? <SettingsBrowser s={s} entities={entities} excludeLink={COMMISSION_LINK} /> : null}

      {tab === "health" ? (
        <ConfigHealthPanel onOpenSetting={(row) => { setTab("settings"); s.setGroup(row.group); s.setQ(row.key); }} />
      ) : null}
      {tab === "saga" && isAdmin ? <SagaLocksPanel /> : null}
      {tab === "hygiene" ? <><DataHygienePanel isAdmin={isAdmin} /><LocationBacklogPanel canEdit /></> : null}
      {tab === "history" ? (
        <section className="cfg-history-tab" data-testid="cfg-history-tab">
          <p className="cfg-hint">Semua perubahan pengaturan, terbaru dulu. Nilai lama tidak pernah dihapus.</p>
          <ChangeHistoryInline entities={entities} groups={s.groups} />
        </section>
      ) : null}
    </div>
  );
}
