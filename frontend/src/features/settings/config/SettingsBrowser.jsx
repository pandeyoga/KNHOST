/**
 * SettingsBrowser — tampilan daftar Pengaturan (cari · cakupan · kelompok · saringan · sub-judul · kartu).
 *
 * Dipakai "Semua pengaturan", layar domain `settings-cfg-*` dan Komisi & Insentif; kelompok berupa chip (tingkat ke-3 =
 * chip, bukan tab — aturan L-01). Mesin datanya `useSettingsBrowser` (SettingsHub.jsx).
 *
 * KF-T4 (KF-UX-11/12/13/15/17) — kartu disusun di bawah SUB-JUDUL kelompoknya (`section`); sub-judul "Lanjutan (teknis)"
 * tertutup bawaan; kartu ringkas satu baris (label · nilai · asal · risiko) terbuka saat diklik; kunci yang tidak dipakai
 * dikumpulkan di bawah. Saringan: Semua · Sudah diubah · Risiko tinggi · Persetujuan · Pengingat & batas waktu ·
 * Toleransi selisih (di "Semua pengaturan" tiga saringan tema berlaku lintas kelompok). Tiap kelompok punya tautan
 * "Riwayat perubahan kelompok ini".
 *
 * KA-9 (R16) — `embedded` (awalan testid, mis. "scheme-price"): mode tertanam di layar domain yang memuat beberapa daftar
 * terkunci sekaligus (tab Skema & Tarif). Tanpa bilah cari/cakupan (`SettingsScopeBar`), tanpa kepala kelompok & chip;
 * cakupan = PT dari pemilih PT halaman (ditulis sekali oleh layar itu); testid bagian/kosong/galat memakai awalan itu
 * supaya tidak kembar. Bawaan (`embedded` kosong) = perilaku lama untuk semua layar lain.
 */
import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, History, ShieldCheck, SlidersHorizontal } from "lucide-react";
import ErrorNotice from "../../../components/ErrorNotice";
import FilterChips from "../../../components/FilterChips";
import LinkCard from "../../../components/LinkCard";
import SettingCard from "./SettingCard";
import SettingsScopeBar from "./SettingsScopeBar";
import { WhyThisValueDrawer, SimulatorPanel, ChangeHistoryDrawer } from "./ConfigDrawers";
import { CARD_FILTERS, cardFilterOk, idNum, weightSetSummaries } from "./configApi";
import { HelpTip } from "../../../components/ListPageParts";
import { CONFIG_GROUPS } from "./configDeepLink";
import { entityShortById } from "../../../utils/entityLabel";

/** Susun butir menjadi [{ id, label, advanced, items }] menurut sub-judul kelompoknya (urutan registry). */
function bySection(items, sections) {
  const out = (sections || []).map((x) => ({ ...x, items: [] }));
  const idx = new Map(out.map((x) => [x.id, x]));
  const lain = { id: "_lain", label: "Lainnya", advanced: false, items: [] };
  items.forEach((it) => (idx.get(it.section) || lain).items.push(it));
  return [...out, lain].filter((x) => x.items.length);
}

function Section({ s, sec, entities, scopeName, defaultOpen, peers, tid = "cfg" }) {
  const [open, setOpen] = useState(defaultOpen);
  useEffect(() => { if (defaultOpen) setOpen(true); }, [defaultOpen]);
  const cards = (
    <div className="cfg-cards">
      {sec.items.map((item) => (
        // Pembungkus fokus deep-link — testid SENGAJA beda dari kartunya (`cfg-card-<key>` di SettingCard).
        <div key={item.key} ref={(el) => { s.cardRefs.current[item.key] = el; }}
          className={s.highlight === item.key ? "cfg-card-focus" : ""}
          data-testid={`cfg-card-wrap-${item.key}`} data-focused={s.highlight === item.key ? "1" : "0"}>
          <SettingCard item={item} scopeType={s.scopeType} scopeId={s.scopeId} scopeLabel={scopeName}
            wiring={s.health[item.key]} canEdit={item.can_edit !== false}
            onSave={s.onSave} onReset={s.onReset} onClearEntity={s.onClearEntity}
            onWhy={(it) => s.setWhy(it)} onSimulate={(it, draft) => s.setSim({ entry: it, draft })}
            onHistory={(it) => s.setHist({ entry: it })}
            onCancelScheduled={s.onCancelScheduled} entities={entities}
            collapsible open={s.openKeys.has(item.key)} onToggle={s.toggleOpen} onDirty={s.onDirty}
            onPickEntity={s.pickEntity} restore={s.restore} peers={peers} />
        </div>
      ))}
    </div>
  );
  if (!sec.advanced) {
    return (
      <section className="cfg-section" data-testid={`${tid}-section-${sec.id}`}>
        <h4 className="cfg-section-title">{sec.label}</h4>
        {cards}
      </section>
    );
  }
  return (
    <section className="cfg-section cfg-section-adv" data-testid={`${tid}-section-${sec.id}`}>
      <button type="button" className="cfg-section-toggle" onClick={() => setOpen((v) => !v)} aria-expanded={open}
        data-testid={`${tid}-section-toggle-${sec.id}`}>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span>Lanjutan (teknis): {sec.label}</span>
        <span className="cfg-group-count">{sec.items.length}</span>
      </button>
      {open ? cards : null}
    </section>
  );
}

export default function SettingsBrowser({ s, entities = [], groupNav = "side", excludeLink = null, searchPlaceholder = "",
  embedded = "" }) {
  const tid = embedded || "cfg";
  const scopeName = useMemo(
    () => (s.scopeType === "entity" && s.scopeId ? entityShortById(entities, s.scopeId) : "Semua PT"),
    [s.scopeType, s.scopeId, entities]);
  useEffect(() => { if (s.setEntities) s.setEntities(entities); }, [entities, s]);
  const { items, term, groups, group } = s;
  const activeGroup = groups.find((g) => g.id === group);
  const shown = items.filter((i) => cardFilterOk(i, s.filter));
  const aktif = shown.filter((i) => i.status !== "not_used");
  const tidakDipakai = shown.filter((i) => i.status === "not_used");
  const weightSets = useMemo(() => weightSetSummaries(items), [items]);
  // PY-T3 — butir lain yang termuat (kunci → butir) untuk keterangan kunci pasangan di kartu (`SettingKeyExtra`).
  const peers = useMemo(() => Object.fromEntries(items.map((i) => [i.key, i])), [items]);
  const shownGroups = groups.filter((g) => !s.lockedGroup || g.id === s.lockedGroup);
  const crossTheme = !s.locked && !term && ["persetujuan", "pengingat", "toleransi"].includes(s.filter);
  const sectionsOf = (gid) => (groups.find((g) => g.id === gid)?.sections
    || CONFIG_GROUPS.find((g) => g.id === gid)?.sections || []);
  // Hasil cari / tema lintas kelompok: per kelompok; selain itu per sub-judul kelompok aktif.
  const blocks = term || crossTheme
    ? CONFIG_GROUPS.map((g) => ({ id: g.id, label: g.label, advanced: false, items: aktif.filter((i) => i.group === g.id) }))
      .filter((b) => b.items.length)
    : bySection(aktif, sectionsOf(group));

  return (
    <>
      {!embedded && <SettingsScopeBar s={s} entities={entities} scopeName={scopeName} searchPlaceholder={searchPlaceholder} />}

      {/* KF-T4 — kelompok selalu FilterChips (tingkat ke-3 = chip, aturan L-01); dulu "Semua pengaturan" memakai kolom
          tombol buatan sendiri (`cfg-group-btn`, ratchet verify_page_tabs). `groupNav` dipertahankan untuk pemanggil lama. */}
      {!embedded && s.lockedGroup ? (
        <button type="button" className="cfg-link-btn" data-testid="cfg-group-show-all"
          onClick={() => s.setLockedGroup("")}>Tampilkan semua kelompok</button>
      ) : null}
      {!embedded && groups.length > 1 ? (
        <FilterChips testId="cfg-group-chips" chipTestId={(k) => `cfg-group-${k}`} ariaLabel="Kelompok pengaturan"
          value={term || crossTheme ? null : group} onChange={(k) => k && s.pickGroup(k)}
          options={shownGroups.map((g) => ({ key: g.id, label: g.label, count: g.count, title: g.question }))} />
      ) : null}

      <div className="cfg-body cfg-body-single" data-testid={groupNav === "side" ? "cfg-group-nav" : undefined}>
        <section className="cfg-list">
          {s.denied ? (
            <div className="cfg-notice info" data-testid={`${tid}-denied`}>
              <ShieldCheck size={15} />
              <span>{s.denied}</span>
            </div>
          ) : <ErrorNotice message={s.error} onRetry={s.load} testId={embedded ? `${tid}-error` : undefined} />}
          {term ? (
            <div className="cfg-result-head" data-testid="cfg-search-result-head">
              <h3>Hasil pencarian “{term}”</h3>
              <p>
                {shown.length} pengaturan cocok — {s.locked ? "di kelompok layar ini" : "dari seluruh kelompok"}.{" "}
                <button className="cfg-link-btn" onClick={() => s.setQ("")} data-testid="cfg-back-to-group">
                  Kembali ke kelompok
                </button>
              </p>
            </div>
          ) : crossTheme ? (
            <div className="cfg-result-head" data-testid="cfg-theme-head">
              <h3>{(CARD_FILTERS.find((f) => f.key === s.filter) || {}).label} — semua kelompok</h3>
              <p className="cfg-hint-sm">{shown.length} pengaturan</p>
            </div>
          ) : activeGroup && !embedded ? (
            // Pola UI 16 Nov (M43) — kepala kelompok SATU baris: nama · ? (pertanyaan kelompok) · jumlah · riwayat.
            <div className="cfg-group-line" data-testid="cfg-group-head">
              <b>{activeGroup.label}</b>
              <HelpTip text={activeGroup.question ? `Kelompok ini menjawab: ${activeGroup.question}` : ""}
                testId="cfg-group-question" label="Isi kelompok ini" />
              <span className="cfg-hint-sm">
                {activeGroup.count} pengaturan{tidakDipakai.length ? ` · ${tidakDipakai.length} tidak dipakai` : ""}
              </span>
              <button type="button" className="cfg-link-btn" onClick={() => s.setHist({ group: activeGroup.id,
                label: activeGroup.label })} data-testid="cfg-group-history">
                <History size={12} /> Riwayat perubahan
              </button>
            </div>
          ) : null}

          {/* Saringan tampilan (Semua · Sudah diubah · Risiko tinggi · tema) kini dropdown di bilah atas (SettingsScopeBar). */}

          {s.loading ? <p className="cfg-hint">Memuat pengaturan…</p> : null}
          {!s.loading && shown.length === 0 ? (
            <p className="cfg-empty" data-testid={`${tid}-empty`}>
              {term ? `Tidak ada pengaturan yang cocok dengan “${term}”. Coba kata lain, mis. “denda”, “PPN”, “lot”.`
                : s.filter !== "all" ? "Tidak ada pengaturan yang cocok dengan saringan ini."
                  : "Belum ada pengaturan di kelompok ini."}
            </p>
          ) : null}

          {/* Keputusan pemilik K-08 (26 Okt) — kelompok bobot ditampilkan sebagai porsi dari 100%. */}
          {!s.loading && weightSets.map((w) => (
            <div key={w.id} className={`cfg-notice info ${w.total === 100 ? "" : "cfg-notice-warn"}`}
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

          {!s.loading && blocks.map((sec) => (
            <Section key={sec.id} s={s} sec={sec} entities={entities} scopeName={scopeName} peers={peers} tid={tid}
              defaultOpen={s.section === sec.id || sec.items.some((i) => i.key === s.highlight)} />
          ))}
          {!s.loading && tidakDipakai.length ? (
            <Section s={s} entities={entities} scopeName={scopeName} defaultOpen={false} peers={peers} tid={tid}
              sec={{ id: "tidak-dipakai", label: "Tidak dipakai sistem", advanced: false, items: tidakDipakai }} />
          ) : null}
          {/* Pengaturan yang diatur di layar lain — di bawah daftar, tidak menghalangi isi (pola UI 16 Nov). */}
          {excludeLink && s.hiddenCount > 0 ? (
            <LinkCard {...excludeLink} summary={`${s.hiddenCount} pengaturan`} />
          ) : null}
        </section>
      </div>

      {s.why ? <WhyThisValueDrawer entry={s.why} ctx={s.ctx} onClose={() => s.setWhy(null)} /> : null}
      {s.sim ? <SimulatorPanel entry={s.sim.entry} ctx={s.ctx} draftValue={s.sim.draft} onClose={() => s.setSim(null)} /> : null}
      {s.hist ? (
        <ChangeHistoryDrawer entry={s.hist.entry} group={s.hist.group} groupLabel={s.hist.label} entities={entities}
          onClose={() => s.setHist(null)}
          onRestore={s.hist.entry && s.hist.entry.can_edit !== false ? (row) => {
            s.setRestore({ key: s.hist.entry.key, value: row.value, nonce: Date.now() });
            s.setHist(null);
          } : null} />
      ) : null}
    </>
  );
}
