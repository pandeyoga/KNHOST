/**
 * SettingsScopeBar — bagian atas daftar Pusat Pengaturan: pemberitahuan hak (K-11 / hak terbatas), cari, pilihan
 * "Berlaku untuk" (Semua PT (aturan grup) / Satu PT) + pita "nilai SIAPA yang sedang diubah" (FASE E-4 · E4.6), dan
 * pita simpan/galat. KF-T4 — istilah glosarium (PT, aturan grup); satu peringatan bila PT belum dipilih; berganti
 * cakupan dengan draf yang belum disimpan meminta konfirmasi (`s.confirmLeave`).
 *
 * Fase 3 · P2 — diekstrak dari `SettingsHub.jsx` (batas 500 baris) karena dipakai bersama oleh "Semua pengaturan",
 * layar domain `settings-cfg-*` dan Komisi & Insentif. Perilaku & testid TIDAK berubah.
 */
import { useMemo } from "react";
import { AlertTriangle, Building2, CheckCircle2, Globe2, Search, ShieldCheck, X } from "lucide-react";
import KNSelect from "../../../components/KNSelect";
import { SCOPE_LABEL } from "./configApi";
import { entityOptions } from "../../../utils/entityLabel";

/** Pita notifikasi simpan/galat. */
export function SettingsNotice({ s }) {
  if (!s.notice) return null;
  return (
    <div className={`cfg-notice ${s.notice.tone}`} data-testid="cfg-notice">
      {s.notice.tone === "err" ? <AlertTriangle size={15} /> : <CheckCircle2 size={15} />}
      <span>{s.notice.msg}</span>
      <button className="icon-button" onClick={() => s.setNotice(null)} aria-label="Tutup"><X size={14} /></button>
    </div>
  );
}

export default function SettingsScopeBar({ s, entities = [], scopeName = "Semua PT", searchPlaceholder = "" }) {
  const entityOpts = useMemo(() => entityOptions(entities), [entities]);
  const { caps, items } = s;
  const editableShown = items.filter((i) => i.can_edit !== false).length;
  return (
    <>
      {/* KF-T1 — tanpa `settings.view` server hanya mengirim pengaturan yang menjadi wewenang peran (bisa diubah). */}
      {!caps.settings_view && caps.read_scope ? (
        <div className="cfg-notice info" data-testid="cfg-read-scope">
          <ShieldCheck size={15} />
          <span>
            Anda hanya melihat pengaturan <b>{caps.read_scope}</b> — yaitu aturan yang termasuk wewenang peran Anda.
            {items.length > 0 ? ` Yang bisa Anda ubah di daftar ini: ${editableShown} dari ${items.length} pengaturan.` : ""}
          </span>
        </div>
      ) : caps.settings_view && !caps.settings_manage ? (
        <div className="cfg-notice info" data-testid="cfg-limited-rights">
          <ShieldCheck size={15} />
          <span>
            Anda dapat <b>melihat semua aturan</b> beserta penjelasannya. Yang bisa Anda <b>ubah</b> hanya aturan yang
            menjadi wewenang peran Anda
            {items.length > 0 ? ` — di daftar ini ${editableShown} dari ${items.length} pengaturan` : ""}
            . Sisanya tampil terkunci, bukan disembunyikan, supaya Anda tetap tahu aturan apa yang sedang dipakai sistem.
          </span>
        </div>
      ) : null}

      <div className="cfg-toolbar">
        <label className="cfg-search-wrap">
          <Search size={15} />
          <input className="form-input" value={s.q} onChange={(e) => s.setQ(e.target.value)} data-testid="cfg-search"
            placeholder={searchPlaceholder || "Cari pengaturan… coba “denda”, “toleransi”, “PPN”, “persetujuan”"} />
          {s.q ? (
            <button className="icon-button" onClick={() => s.setQ("")} aria-label="Kosongkan pencarian"
              data-testid="cfg-search-clear"><X size={13} /></button>
          ) : null}
        </label>
        <div className="cfg-scope-box" data-testid="cfg-scope-box">
          <span className="cfg-scope-caption"><Building2 size={13} /> Berlaku untuk</span>
          <KNSelect value={s.scopeType} className="field cfg-select-sm" data-testid="cfg-scope-type"
            onValueChange={async (v) => {
              if (s.confirmLeave && !(await s.confirmLeave())) return;
              s.setScopeType(v); if (v === "global") s.setScopeId("");
            }}
            options={[
              // IX-06 — aturan grup hanya untuk peran lintas PT (keputusan server)
              { value: "global", label: caps.global_write ? SCOPE_LABEL.global : `${SCOPE_LABEL.global} — khusus peran lintas PT`,
                disabled: !caps.global_write },
              { value: "entity", label: SCOPE_LABEL.entity },
            ]} />
          {s.scopeType === "entity" ? (
            <KNSelect value={s.scopeId} options={entityOpts} placeholder="Pilih PT…"
              onValueChange={async (v) => { if (s.confirmLeave && !(await s.confirmLeave())) return; s.setScopeId(v); }}
              className="field cfg-select-sm" data-testid="cfg-scope-entity" />
          ) : null}
        </div>
      </div>

      {/* FASE E-4 (E4.6) / KF-T4 — pita konteks: nilai SIAPA yang sedang diubah (satu peringatan saja). */}
      <div data-testid="cfg-scope-ribbon"
        className={`cfg-scope-ribbon ${s.scopeType === "entity" ? "is-entity" : "is-global"}`}>
        {s.scopeType === "entity" ? <Building2 size={13} /> : <Globe2 size={13} />}
        <span>
          {s.scopeType === "entity" && s.scopeId ? (
            <>Anda sedang mengubah nilai khusus <b>{scopeName}</b>. PT lain tidak terpengaruh.</>
          ) : s.scopeType === "entity" ? (
            <span data-testid="cfg-scope-need-entity">Pilih PT dulu supaya perubahan tersimpan pada PT yang benar.</span>
          ) : (
            <>Anda sedang mengubah <b>aturan grup</b> — berlaku untuk semua PT yang tidak punya nilai sendiri.</>
          )}
        </span>
      </div>
    </>
  );
}
