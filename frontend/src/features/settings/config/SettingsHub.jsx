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
  SlidersHorizontal, ShieldCheck, History, Loader2, RefreshCw, ChevronRight, Lock, Sparkles, Wand2,
} from "lucide-react";
import ErrorNotice from "../../../components/ErrorNotice";
import PageTabs from "../../../components/PageTabs";
import FilterChips from "../../../components/FilterChips";
import LinkCard from "../../../components/LinkCard";
import DesktopOnlyNotice from "../../../components/DesktopOnlyNotice";
import SettingCard from "./SettingCard";
import SettingsScopeBar, { SettingsNotice } from "./SettingsScopeBar";
import ConfigHealthPanel from "./ConfigHealthPanel";
import SagaLocksPanel from "./SagaLocksPanel";
import DataHygienePanel from "./DataHygienePanel";
import LocationBacklogPanel from "./LocationBacklogPanel";
import {
  WhyThisValueDrawer, SimulatorPanel, ChangeHistoryDrawer, ChangeHistoryInline,
} from "./ConfigDrawers";
import { configApi, errMsg, idNum, weightSetSummaries } from "./configApi";
import { LEGACY_DEEPLINK, groupForKey } from "./configDeepLink";
import { COMMISSION_PREFIX } from "./configGroupViews";
import { entityShortById } from "../../../utils/entityLabel";
import { can } from "../../../config/roles";

const TABS = [
  { k: "settings", label: "Pengaturan", icon: SlidersHorizontal },
  { k: "health", label: "Kesehatan Konfigurasi", icon: ShieldCheck, perm: ["settings", "view"] },
  { k: "history", label: "Riwayat Perubahan", icon: History },
  { k: "saga", label: "Kunci Proses", icon: Lock, adminOnly: true },
  { k: "hygiene", label: "Kebersihan Data", icon: Sparkles },
];

/** Kunci komisi (D-03) disembunyikan dari Semua pengaturan & Aturan Penjualan — rumahnya Komisi & Insentif. */
export const COMMISSION_EXCLUDE = [COMMISSION_PREFIX];
export const COMMISSION_LINK = {
  testId: "cfg-commission-link", what: "Bawaan komisi sales", view: "incentive-rates",
  where: "Pengaturan › Penjualan › Komisi & Insentif",
};

/** Deep-link kelompok editor lama (definisi di `configDeepLink.js`, re-export agar impor lama tidak patah). */
export { LEGACY_DEEPLINK, SettingsNotice };

const byPrefix = (list, key) => (list || []).some((p) => String(key || "").startsWith(p));

/**
 * Mesin data Pusat Pengaturan. `groupIds` mengunci kelompok (layar domain); `includeKeys`/`excludeKeys` = prefiks
 * kunci yang ditampilkan/disembunyikan. Pencarian di layar terkunci hanya mencari di kelompoknya sendiri.
 */
export function useSettingsBrowser({
  selectedEntity, groupIds = null, includeKeys = null, excludeKeys = null,
  focusKey = "", focusGroup = "", focusNonce = 0, onFocusConsumed,
}) {
  const allowKey = (groupIds || []).join("|");
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
  const [notice, setNotice] = useState(null);     // {msg, tone}
  const [why, setWhy] = useState(null);
  const [sim, setSim] = useState(null);           // {entry, draft}
  const [hist, setHist] = useState(null);         // {entry} | {} = semua
  const cardRefs = useRef({});
  const counts = useRef(null);                    // id kelompok → jumlah kunci yang tampil (sesudah saringan kunci)

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

  const ctx = useMemo(
    () => ({ entity_id: scopeType === "entity" ? scopeId : (selectedEntity || "") }),
    [scopeType, scopeId, selectedEntity]
  );

  useEffect(() => {
    const t = window.setTimeout(() => setTerm(q.trim()), 280);
    return () => window.clearTimeout(t);
  }, [q]);

  /* muat katalog grup + peta kesehatan sekali (Audit UI 097 — katalog TIDAK menunggu peta kesehatan) */
  useEffect(() => {
    let alive = true;
    configApi.health().then((hp) => {
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
        if (alive) { setError(errMsg(e, "Gagal memuat katalog pengaturan.")); setLoading(false); }
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
    let g = focusGroup || groupForKey(key);
    if (allow && g && !allow.has(g)) g = "";
    if (g) setGroup(g);
    setLockedGroup(!key && g && (!allow || allow.size > 1) ? g : "");
    setQ(key); setTerm(key);            // lewati debounce: hasil harus langsung muncul
    setPendingScroll(key); setHighlight(key);
    if (typeof onFocusConsumed === "function") onFocusConsumed();
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [focusNonce]);

  useEffect(() => {
    if (!highlight) return undefined;
    const t = window.setTimeout(() => setHighlight(""), 8000);
    return () => window.clearTimeout(t);
  }, [highlight]);

  const load = useCallback(async () => {
    if (!group && !term) return;
    setLoading(true);
    setError("");
    try {
      const d = await configApi.effective({
        ...(term ? { q: term } : { group }),
        entity_id: ctx.entity_id || "",
      });
      const rows = (d.items || []).filter((it) => !allow || !it.group || allow.has(it.group));
      const kept = rows.filter((it) => keyOk(it.key));
      setHiddenCount(rows.length - kept.length);
      setItems(kept);
      if (d.groups?.length) setGroups(d.groups);
    } catch (e) {
      setError(errMsg(e, "Gagal memuat nilai pengaturan."));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [group, term, ctx.entity_id, allow, keyOk]);

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
  const onReset = async (item) => {
    try {
      await configApi.reset({ key: item.key, scope_type: scopeType, scope_id: scopeId });
      flash(`“${item.label}” dikembalikan ke bawaan sistem.`);
      await load();
    } catch (e) { flash(errMsg(e, "Gagal mengembalikan ke default."), "err"); }
  };
  // FASE E-4 (E4.6) — cabut nilai khusus badan usaha → kembali mewarisi nilai global (BUKAN reset ke bawaan kode).
  const onClearEntity = async (item) => {
    if (!scopeId) return;
    try {
      const res = await configApi.clear({ key: item.key, scope_type: "entity", scope_id: scopeId });
      flash(`“${item.label}” kembali mengikuti nilai ${res?.source_label_now || "Global"}.`);
      await load();
    } catch (e) { flash(errMsg(e, "Gagal mengembalikan ke nilai global."), "err"); }
  };

  return {
    groups, group, setGroup, items, hiddenCount, q, setQ, term, scopeType, setScopeType, scopeId, setScopeId,
    health, caps, loading, error, notice, setNotice, why, setWhy, sim, setSim, hist, setHist, cardRefs,
    highlight, lockedGroup, setLockedGroup, ctx, load, onSave, onReset, onClearEntity, locked: !!allow,
  };
}

/**
 * Tampilan daftar setting (cari · cakupan · kelompok · kartu). `groupNav`: "side" (kolom kiri, Semua pengaturan)
 * atau "chips" (FilterChips — layar domain; tingkat ke-3 = chip, bukan tab, aturan L-01). `excludeLink` = LinkCard
 * yang tampil bila ada kunci disembunyikan (mis. kunci komisi → Komisi & Insentif).
 */
export function SettingsBrowser({ s, entities = [], groupNav = "side", excludeLink = null, searchPlaceholder = "" }) {
  const scopeName = useMemo(
    () => (s.scopeType === "entity" && s.scopeId ? entityShortById(entities, s.scopeId) : "Global"),
    [s.scopeType, s.scopeId, entities]);
  const { items, term, groups, group, caps } = s;
  const activeGroup = groups.find((g) => g.id === group);
  const notUsedCount = items.filter((i) => i.status === "not_used").length;
  const weightSets = useMemo(() => weightSetSummaries(items), [items]);
  const shownGroups = groups.filter((g) => !s.lockedGroup || g.id === s.lockedGroup);
  const pickGroup = (id) => { s.setGroup(id); s.setQ(""); };

  return (
    <>
      <SettingsScopeBar s={s} entities={entities} scopeName={scopeName} searchPlaceholder={searchPlaceholder} />

      {groupNav === "chips" && groups.length > 1 ? (
        <FilterChips testId="cfg-group-chips" chipTestId={(k) => `cfg-group-${k}`} ariaLabel="Kelompok pengaturan"
          value={term ? null : group} onChange={(k) => k && pickGroup(k)}
          options={shownGroups.map((g) => ({ key: g.id, label: g.label, count: g.count, title: g.question }))} />
      ) : null}

      <div className={groupNav === "side" ? "cfg-body" : "cfg-body cfg-body-single"}>
        {groupNav === "side" ? (
          <aside className="cfg-groupnav" data-testid="cfg-group-nav">
            <h4>Kelompok</h4>
            {s.lockedGroup && (
              <button type="button" className="cfg-link-btn" data-testid="cfg-group-show-all"
                onClick={() => s.setLockedGroup("")}>Tampilkan semua kelompok</button>
            )}
            {shownGroups.map((g) => (
              <button key={g.id} className={`cfg-group-btn ${group === g.id && !term ? "active" : ""}`}
                onClick={() => pickGroup(g.id)} data-testid={`cfg-group-${g.id}`} title={g.question}>
                <span className="cfg-group-label">{g.label}</span>
                <span className="cfg-group-count">{g.count}</span>
                <ChevronRight size={13} />
              </button>
            ))}
          </aside>
        ) : null}

        <section className="cfg-list">
          <ErrorNotice message={s.error} onRetry={s.load} />
          {excludeLink && s.hiddenCount > 0 ? (
            <LinkCard {...excludeLink} summary={`${s.hiddenCount} pengaturan`} />
          ) : null}

          {term ? (
            <div className="cfg-result-head" data-testid="cfg-search-result-head">
              <h3>Hasil pencarian “{term}”</h3>
              <p>
                {items.length} pengaturan cocok — {s.locked ? "di kelompok layar ini" : "dari seluruh kelompok"}.{" "}
                <button className="cfg-link-btn" onClick={() => s.setQ("")} data-testid="cfg-back-to-group">
                  Kembali ke kelompok
                </button>
              </p>
            </div>
          ) : activeGroup ? (
            <div className="cfg-result-head" data-testid="cfg-group-head">
              <h3>{activeGroup.label}</h3>
              <p className="cfg-question">Kelompok ini menjawab: <b>{activeGroup.question}</b></p>
              <p className="cfg-hint-sm">
                {activeGroup.count} pengaturan{notUsedCount ? ` · ${notUsedCount} ditandai tidak dipakai` : ""}
              </p>
            </div>
          ) : null}

          {s.loading ? <p className="cfg-hint">Memuat pengaturan…</p> : null}
          {!s.loading && items.length === 0 ? (
            <p className="cfg-empty" data-testid="cfg-empty">
              {term ? `Tidak ada pengaturan yang cocok dengan “${term}”. Coba kata lain, mis. “denda”, “PPN”, “lot”.`
                : "Belum ada pengaturan di kelompok ini."}
            </p>
          ) : null}

          {/* Keputusan pemilik K-08 (26 Okt) — kelompok bobot ditampilkan sebagai porsi dari 100%. */}
          {!s.loading && weightSets.map((w) => (
            <div key={w.id} className={`cfg-notice info ${w.total === 100 ? "" : "!bg-[#FFF4E5] !text-[#8A5300]"}`}
              data-testid={`cfg-weight-total-${w.id}`}>
              <SlidersHorizontal size={15} />
              <span>
                <b>{w.label}:</b>{" "}
                {w.parts.map((p) => `${p.name} ${idNum(p.value)}%`).join(" + ")} ={" "}
                <b data-testid={`cfg-weight-total-${w.id}-sum`}>{idNum(w.total)}%</b>
                {w.total === 100 ? "."
                  : w.total > 0
                    ? ` — bukan 100%, jadi sistem menyetarakannya ke 100%: ${w.parts.map((p) => `${p.name} ${idNum(p.share, 1)}%`).join(" + ")}. Sesuaikan agar jumlahnya 100%.`
                    : " — semua bobot 0, nilai tidak bisa dihitung."}
              </span>
            </div>
          ))}

          <div className="cfg-cards">
            {items.map((item) => (
              // Pembungkus fokus deep-link — testid SENGAJA beda dari kartunya (`cfg-card-<key>` di SettingCard).
              <div key={item.key} ref={(el) => { s.cardRefs.current[item.key] = el; }}
                className={s.highlight === item.key ? "cfg-card-focus" : ""}
                data-testid={`cfg-card-wrap-${item.key}`} data-focused={s.highlight === item.key ? "1" : "0"}>
                <SettingCard item={item} scopeType={s.scopeType} scopeId={s.scopeId} scopeLabel={scopeName}
                  wiring={s.health[item.key]} canEdit={item.can_edit !== false}
                  onSave={s.onSave} onReset={s.onReset} onClearEntity={s.onClearEntity}
                  onWhy={(it) => s.setWhy(it)} onSimulate={(it, draft) => s.setSim({ entry: it, draft })}
                  onHistory={(it) => s.setHist({ entry: it })} />
              </div>
            ))}
          </div>
        </section>
      </div>

      {s.why ? <WhyThisValueDrawer entry={s.why} ctx={s.ctx} onClose={() => s.setWhy(null)} /> : null}
      {s.sim ? <SimulatorPanel entry={s.sim.entry} ctx={s.ctx} draftValue={s.sim.draft} onClose={() => s.setSim(null)} /> : null}
      {s.hist ? <ChangeHistoryDrawer entry={s.hist.entry} onClose={() => s.setHist(null)} /> : null}
    </>
  );
}

export default function SettingsHub({
  currentUser, selectedEntity, entities = [], focusKey = "", focusGroup = "", focusNonce = 0, onFocusConsumed,
}) {
  // Sisir gerbang peran (2026-10-20): tab Kunci Saga & aksi Data Hygiene tetap khusus Admin (server require_role admin).
  const isAdmin = currentUser?.role === "admin";
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
          <p className="cfg-hint">
            Seluruh perubahan konfigurasi, terbaru dulu. Data bersifat <b>append-only</b>: nilai lama tidak pernah
            ditimpa sehingga selalu bisa ditelusuri dan dipulihkan.
          </p>
          <button className="btn-secondary btn-sm self-start" onClick={() => s.setHist({})} data-testid="cfg-open-all-history">
            <History size={14} /> Buka riwayat lengkap
          </button>
          <ChangeHistoryInline />
          {s.hist ? <ChangeHistoryDrawer entry={s.hist.entry} onClose={() => s.setHist(null)} /> : null}
        </section>
      ) : null}
    </div>
  );
}
