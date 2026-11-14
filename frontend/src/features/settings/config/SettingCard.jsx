/**
 * SettingCard — kartu satu setting di Pusat Pengaturan.
 *
 * Menjawab kebingungan user dengan menampilkan 5 hal SEKALIGUS, bukan hanya field kosong:
 *   1. Label awam + nilai efektif  2. "Artinya:"  3. "Kalau diubah:"
 *   4. Contoh angka konkret        5. Badge lapisan asal + status sambungan
 * Plus 4 aksi: Kenapa nilainya begini? · Coba dulu · Riwayat · Berlaku sejak.
 *
 * KF-T3 (L6) — nilai yang tampil = nilai yang DIPAKAI MESIN. Bila aturan lain menimpanya (`item.overridden_by`, mis.
 * PT bukan PKP → tarif PPN 0), kartu menulis siapa yang menimpa dan nilai tersimpan yang tidak dipakai. Tiap baris
 * jadwal menyebut cakupannya dan bisa dibatalkan (`onCancelScheduled`) oleh yang boleh mengubah kunci itu.
 *
 * KF-T4 (KF-12, KF-UX) — tombol "Default" dihapus. Pengembali nilai berarti persis seperti labelnya:
 *   · Satu PT, PT punya nilai sendiri → **Ikuti nilai grup** (cabut nilai PT; `onClearEntity`)
 *   · Satu PT, PT mengikuti grup → keterangan "Mengikuti nilai grup" (tanpa tombol)
 *   · Satu PT, nilai ≠ bawaan → tautan **Pakai nilai bawaan sistem untuk PT ini** (`onReset(item, "entity")`)
 *   · Semua PT, nilai ≠ bawaan → **Pakai nilai bawaan sistem** (`onReset(item, "global")`)
 * Dialog konfirmasi + alasan ada di `useSettingsBrowser` (SettingsHub). Simpan mati sampai alasan terisi bila wajib;
 * draf/alasan/jadwal dikosongkan saat cakupan berganti. `collapsible` = kartu ringkas satu baris yang terbuka saat
 * diklik (daftar di SettingsBrowser); tanpa itu kartu selalu terbuka.
 */
import { useEffect, useState } from "react";
import {
  Layers, FlaskConical, History, Save, RotateCcw, Info, Zap,
  CalendarClock, ShieldAlert, Ban, ChevronDown, ChevronUp, ChevronRight, ExternalLink, Lightbulb,
} from "lucide-react";
import SettingEditor from "./SettingEditor";
import { ScopedRulesSummary } from "./ScopedRulesSection";   // KF-T5
import KNDateTimePicker from "@/components/KNDateTimePicker";
import { formatDateTime } from "../../../utils/formatters";
import { entityShortById } from "../../../utils/entityLabel";
import { useAppNav } from "../../../context/AppNavContext";
import { askConfirm } from "../../../services/confirmService";
import { openConfig } from "./configDeepLink";
import {
  cleanCfgText, formatValue, isDeprecatedSetting, LAYER_TONE, RISK_LABEL, SCOPE_CAN, WIRING_LABEL, WIRING_TONE,
} from "./configApi";

/** KF-T3 — cakupan satu baris jadwal untuk manusia: "Semua PT" atau nama PT (bukan id). */
const SCHED_SCOPE = { customer: "Pelanggan tertentu", supplier: "Pemasok tertentu", product: "Produk tertentu",
  document: "Dokumen tertentu" };
function scheduleScopeLabel(s, entities = []) {
  if (!s?.scope_type || s.scope_type === "global") return "Semua PT";
  if (s.scope_type === "entity") return entityShortById(entities, s.scope_id, "PT");
  return SCHED_SCOPE[s.scope_type] || "Cakupan khusus";
}

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/** KF-T4 — lencana asal: "Bawaan sistem" · "Aturan grup" · "Khusus {nama PT}". */
export function originLabel(item, scopeLabel = "") {
  const l = item.source_layer;
  if (l === "code_default") return "Bawaan sistem";
  if (l === "global" || l === "legacy_global") return "Aturan grup";
  if (l === "entity" || l === "legacy_entity") return scopeLabel ? `Khusus ${scopeLabel}` : "Khusus PT";
  return item.source_label || "";
}

export default function SettingCard({
  item, scopeType, scopeId, scopeLabel = "", wiring, canEdit, onSave, onReset,
  onClearEntity, onWhy, onSimulate, onHistory, onCancelScheduled, entities = [],
  collapsible = false, open: openProp, onToggle, onDirty, onPickEntity, restore,
}) {
  const nav = useAppNav();
  const [draft, setDraft] = useState(undefined);
  const [reason, setReason] = useState("");
  const [effFrom, setEffFrom] = useState("");
  const [showSched, setShowSched] = useState(false);
  const [showMore, setShowMore] = useState(false);
  const [busy, setBusy] = useState(false);

  // G5-61 — setting usang berlabel "(Lama) … TIDAK DIPAKAI LAGI" dulu tetap berlencana hijau "Aktif & tersambung".
  const notUsed = isDeprecatedSetting(item);
  // KF-T3 — yang diubah adalah nilai TERSIMPAN; bila ditimpa aturan lain, nilai tampil (mesin) ≠ nilai tersimpan.
  const over = item.overridden_by || null;
  const baseValue = over ? item.stored_value : item.value;
  const dirty = draft !== undefined && !same(draft, baseValue);
  const editAt = item.edit_at || null;   // KF-T4 — diubah di layar lain (kartu tanpa editor)
  const editable = canEdit && !notUsed && !editAt;
  const wStatus = notUsed ? "NOT_USED" : (wiring?.wiring_status || "OK");
  const globalOnly = (item.scopes || []).length === 1 && (item.scopes || [])[0] === "global";
  // FASE E-4 (E4.6) — apakah nilai yang tampil BENAR-BENAR milik PT ini?
  const ownedByEntity = scopeType === "entity" && Boolean(scopeId) && !globalOnly
    && ["entity", "legacy_entity"].includes(item.source_layer);
  const inheritedGlobal = scopeType === "entity" && Boolean(scopeId) && !globalOnly && !ownedByEntity;
  // KF-T4 — kunci hanya-grup disimpan pada aturan grup walau bilah cakupan menunjuk satu PT.
  const saveScope = globalOnly ? { scope_type: "global", scope_id: "" } : { scope_type: scopeType, scope_id: scopeId };
  const forPt = scopeType === "entity" && !globalOnly;
  const notDefault = !same(baseValue, item.default);
  const reasonMissing = !!item.requires_reason && !reason.trim();
  const expanded = !collapsible || !!openProp;
  // KF-T3 — penimpa terdaftar (server `config_overrides`): tautan ke kunci lain atau ke layar sumbernya.
  const overLink = over?.link || {};
  const canOpenSource = Boolean(overLink.key) || Boolean(overLink.view && nav.canOpen(overLink.view));
  const openSource = () => {
    if (overLink.key) openConfig({ key: overLink.key });
    else if (overLink.view) nav.go(overLink.view);
  };

  // KF-T4 (KF-UX-23) — draf, alasan, dan jadwal milik cakupan lama dikosongkan saat cakupan berganti.
  useEffect(() => {
    setDraft(undefined); setReason(""); setEffFrom(""); setShowSched(false);
  }, [scopeType, scopeId]);
  // KF-T4 — "Pulihkan nilai ini" dari riwayat mengisi draf (penyimpanan tetap lewat Simpan).
  useEffect(() => {
    if (restore && restore.key === item.key) setDraft(restore.value);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [restore?.nonce]);
  useEffect(() => {
    if (typeof onDirty === "function") onDirty(item.key, dirty);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dirty, item.key]);

  const scopeName = forPt ? (scopeLabel || "PT ini") : "Semua PT";
  const submit = async () => {
    if (item.risk === "high") {
      const ok = await askConfirm({
        title: "Ubah pengaturan berisiko tinggi?",
        message: `Ubah '${cleanCfgText(item.label)}'? Dari ${formatValue(item, baseValue)} menjadi `
          + `${formatValue(item, draft)} untuk ${scopeName}. ${cleanCfgText(item.impact)}`,
        confirmLabel: "Ubah", cancelLabel: "Batal", danger: true, testId: `cfg-confirm-save-${item.key}`,
      });
      if (!ok) return;
    }
    setBusy(true);
    const ok = await onSave({
      key: item.key, value: draft, ...saveScope, reason, effective_from: effFrom,
    });
    setBusy(false);
    if (ok) { setDraft(undefined); setReason(""); setEffFrom(""); setShowSched(false); }
  };
  const goEditAt = () => { if (editAt?.view) nav.go(editAt.view, { preset: editAt.preset || undefined }); };

  const valueText = formatValue(item, item.value);
  const origin = originLabel(item, scopeLabel);
  const head = (
    <header className="cfg-card-head">
      <div className="cfg-card-title">
        {collapsible ? (
          <button type="button" className="cfg-card-toggle" onClick={() => onToggle && onToggle(item.key)}
            aria-expanded={expanded} data-testid={`cfg-card-toggle-${item.key}`}>
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
        ) : null}
        {/* G5-61 — kunci teknis pindah ke "Detail teknis" + tooltip. */}
        <h3 data-testid={`cfg-card-label-${item.key}`} title={item.key}
          onClick={collapsible ? () => onToggle && onToggle(item.key) : undefined}
          className={collapsible ? "cursor-pointer" : ""}>{cleanCfgText(item.label)}</h3>
        {collapsible && !expanded ? (
          <span className="cfg-card-compact-val" data-testid={`cfg-compact-value-${item.key}`}>{valueText}</span>
        ) : null}
      </div>
      <div className="cfg-card-badges">
        <span className={`badge-${LAYER_TONE[item.source_layer] || "muted"}`}
          title="Asal nilai yang berlaku sekarang" data-testid={`cfg-layer-badge-${item.key}`}>
          {origin}
        </span>
        {expanded ? (
          <span className={`badge-${WIRING_TONE[wStatus]}`} title="Tersambung ke sistem?"
            data-testid={`cfg-wiring-badge-${item.key}`}>
            {WIRING_LABEL[wStatus]}
          </span>
        ) : null}
        {dirty ? <span className="badge-orange" data-testid={`cfg-dirty-badge-${item.key}`}>belum disimpan</span> : null}
        {item.risk !== "low" ? (
          <span className={`badge-${item.risk === "high" ? "red" : "orange"}`}>
            <ShieldAlert size={11} /> {RISK_LABEL[item.risk]}
          </span>
        ) : null}
      </div>
    </header>
  );
  if (!expanded) {
    return (
      <article className={`cfg-card cfg-card-compact ${notUsed ? "not-used" : ""} ${dirty ? "dirty" : ""}`}
        data-testid={`cfg-card-${item.key}`}>
        {head}
      </article>
    );
  }

  return (
    <article className={`cfg-card ${notUsed ? "not-used" : ""} ${dirty ? "dirty" : ""}`}
      data-testid={`cfg-card-${item.key}`}>
      {head}

      <div className="cfg-value-row">
        <span className="cfg-value-label">Nilai berlaku sekarang</span>
        <span className="cfg-value" data-testid={`cfg-value-${item.key}`}>{valueText}</span>
        {over ? (
          <span className="badge-red" data-testid={`cfg-overridden-${item.key}`}
            title="Nilai ini ditentukan aturan lain, bukan nilai yang tersimpan">Ditimpa</span>
        ) : null}
        {inheritedGlobal ? (
          <span className="badge-muted" data-testid={`cfg-inherited-${item.key}`}>Mengikuti nilai grup</span>
        ) : null}
      </div>
      {over ? (
        <p className="cfg-override-box" data-testid={`cfg-override-note-${item.key}`}>
          <span>
            Ditimpa oleh: {over.label}. Nilai yang tersimpan ({formatValue(item, item.stored_value)}) tidak dipakai.
          </span>
          {canOpenSource ? (
            <button type="button" className="cfg-link-btn" onClick={openSource}
              data-testid={`cfg-override-open-${item.key}`}>
              Buka sumbernya
            </button>
          ) : null}
        </p>
      ) : null}
      {/* KF-T4 (KF-UX-09) — cakupan grup: PT yang punya nilai sendiri; klik = pindah ke cakupan PT itu. */}
      {scopeType === "global" && (item.entity_overrides || []).length ? (
        <p className="cfg-hint-sm" data-testid={`cfg-entity-overrides-${item.key}`}>
          PT dengan nilai sendiri:{" "}
          {item.entity_overrides.map((o, i) => (
            <span key={o.entity_id}>
              {i ? ", " : ""}
              <button type="button" className="cfg-link-btn" onClick={() => onPickEntity && onPickEntity(o.entity_id)}
                data-testid={`cfg-entity-override-${item.key}-${o.entity_id}`}>
                {o.entity_label} = {formatValue(item, o.value)}
              </button>
            </span>
          ))}
        </p>
      ) : null}
      {globalOnly ? (
        <p className="cfg-hint-sm" data-testid={`cfg-global-only-${item.key}`}>
          Satu nilai untuk seluruh grup — tidak dibedakan per PT.
          {scopeType === "entity" && editable ? " Mengubah di sini berlaku untuk semua PT." : ""}
        </p>
      ) : null}

      <p className="cfg-help"><Info size={13} /> <span><b>Artinya:</b> {cleanCfgText(item.help)}</span></p>
      <p className="cfg-impact"><Zap size={13} /> <span><b>Kalau diubah:</b> {cleanCfgText(item.impact)}</span></p>
      {item.example ? (
        <p className="cfg-example" data-testid={`cfg-example-${item.key}`}>
          <Lightbulb size={13} /> <span><b>Contoh:</b> {cleanCfgText(item.example)}</span>
        </p>
      ) : null}
      <p className="cfg-hint-sm" data-testid={`cfg-scope-can-${item.key}`}>
        Bisa dibedakan untuk: {(item.scopes || []).map((sc) => SCOPE_CAN[sc] || sc).join(" · ")}
      </p>
      {/* KF-T5 — kunci berlapis pelanggan/barang menyebut jumlah yang diatur khusus. */}
      <ScopedRulesSummary item={item} />

      {notUsed ? (
        <div className="cfg-notused-box" data-testid={`cfg-notused-${item.key}`}>
          <Ban size={14} />
          <div>
            <b>Pengaturan ini TIDAK dipakai sistem saat ini.</b>
            <p>{cleanCfgText(item.not_used_reason || item.help)}</p>
          </div>
        </div>
      ) : null}

      <button className="cfg-more-toggle" onClick={() => setShowMore((v) => !v)}
        data-testid={`cfg-more-${item.key}`}>
        {showMore ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        {showMore ? "Sembunyikan detail teknis" : "Detail teknis"}
      </button>
      {showMore ? (
        <div className="cfg-more">
          <p className="cfg-hint-sm">Kunci teknis: <code className="cfg-key">{item.key}</code></p>
          {(item.consumers || []).length ? (
            <p className="cfg-hint-sm">
              Dipakai oleh: {item.consumers.map((c) => <code key={c}>{c}</code>)}
            </p>
          ) : null}
          {(item.related || []).length ? (
            <p className="cfg-hint-sm">Terkait: {item.related.join(" · ")}</p>
          ) : null}
        </div>
      ) : null}

      {(item.scheduled || []).length > 0 ? (
        <div className="cfg-sched-list" data-testid={`cfg-scheduled-${item.key}`}>
          {/* KF-T3 — satu baris per jadwal: nilai · mulai (WIB) · cakupan, + Batalkan jadwal bagi yang boleh mengubah. */}
          {item.scheduled.map((s, i) => (
            <div key={s.id || i} className="cfg-sched-box" data-testid={`cfg-sched-row-${item.key}-${i}`}>
              <CalendarClock size={13} />
              <span className="cfg-sched-text">
                Terjadwal: <b>{formatValue(item, s.value)}</b> mulai {formatDateTime(s.effective_from)}
                {" · "}{scheduleScopeLabel(s, entities)}
              </span>
              {canEdit && s.id && onCancelScheduled ? (
                <button type="button" className="cfg-link-btn" disabled={busy}
                  onClick={() => onCancelScheduled(item, s)} data-testid={`cfg-sched-cancel-${item.key}-${i}`}>
                  Batalkan jadwal
                </button>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      {editAt && !notUsed ? (
        <p className="cfg-readonly" data-testid={`cfg-edit-at-${item.key}`}>
          <button type="button" className="cfg-link-btn" onClick={goEditAt} data-testid={`cfg-edit-at-link-${item.key}`}>
            <ExternalLink size={12} /> Ubah di {editAt.label || "layarnya sendiri"}
          </button>
        </p>
      ) : editable ? (
        <div className="cfg-edit-zone">
          <div className="cfg-edit-row">
            <SettingEditor
              entry={item}
              value={draft !== undefined ? draft : baseValue}
              onChange={setDraft}
              disabled={busy}
            />
            <div className="cfg-edit-actions">
              <button className="btn-primary btn-sm" disabled={!dirty || busy || reasonMissing}
                onClick={submit} data-testid={`cfg-save-${item.key}`}
                title={reasonMissing && dirty ? "Isi alasan dulu — pengaturan ini berisiko tinggi" : undefined}>
                <Save size={13} /> {busy ? "Menyimpan…" : "Simpan"}
              </button>
              {ownedByEntity ? (
                <button className="btn-secondary btn-sm" disabled={busy}
                  onClick={() => onClearEntity && onClearEntity(item)}
                  data-testid={`cfg-clear-entity-${item.key}`}
                  title={`Cabut nilai khusus ${scopeLabel || "PT ini"} — kembali mengikuti nilai grup`}>
                  <RotateCcw size={13} /> Ikuti nilai grup
                </button>
              ) : null}
              {!forPt && notDefault && onReset ? (
                <button className="btn-secondary btn-sm" disabled={busy}
                  onClick={() => onReset(item, "global")} data-testid={`cfg-reset-${item.key}`}>
                  <RotateCcw size={13} /> Pakai nilai bawaan sistem
                </button>
              ) : null}
            </div>
          </div>
          {forPt && notDefault && onReset ? (
            <button type="button" className="cfg-link-btn" disabled={busy}
              onClick={() => onReset(item, "entity")} data-testid={`cfg-reset-${item.key}`}>
              Pakai nilai bawaan sistem untuk PT ini
            </button>
          ) : null}
          {dirty ? (
            <div className="cfg-dirty-box" data-testid={`cfg-dirty-${item.key}`}>
              <p className="cfg-dirty-line">
                Akan berubah: <b>{formatValue(item, baseValue)}</b> →{" "}
                <b className="cfg-new">{formatValue(item, draft)}</b>
                {" "}untuk <b>{scopeName}</b>
              </p>
              <p className="cfg-hint-sm" data-testid={`cfg-dirty-scope-note-${item.key}`}>
                {forPt
                  ? `Hanya ${scopeLabel || "PT ini"} yang terpengaruh — PT lain tidak berubah.`
                  : "Berlaku untuk semua PT yang tidak punya nilai sendiri."}
              </p>
              <input
                className="form-input cfg-input-wide"
                placeholder={item.requires_reason
                  ? "Alasan perubahan (WAJIB — pengaturan berisiko tinggi)"
                  : "Alasan perubahan (opsional, sangat dianjurkan)"}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                data-testid={`cfg-reason-${item.key}`}
              />
              <button className="cfg-link-btn" onClick={() => setShowSched((v) => !v)}
                data-testid={`cfg-sched-toggle-${item.key}`}>
                <CalendarClock size={12} /> {showSched ? "Berlaku sekarang" : "Jadwalkan berlaku sejak…"}
              </button>
              {showSched ? (
                <label className="cfg-sched-field">
                  <span>Berlaku sejak</span>
                  <KNDateTimePicker
                    value={effFrom} onChange={setEffFrom} placeholder="Sekarang (langsung berlaku)"
                    data-testid={`cfg-efffrom-${item.key}`} />
                  <em>Sebelum tanggal ini, nilai lama tetap dipakai mesin.</em>
                  {/* PK-46 — kunci bertanggal (tabel PPh 21): dibaca menurut tanggal periode, bukan tanggal hitung. */}
                  {item.bertanggal ? (
                    <em data-testid={`cfg-efffrom-bertanggal-${item.key}`}>
                      Slip dengan periode sebelum tanggal ini tetap memakai tabel lama.
                    </em>
                  ) : null}
                </label>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : (
        <p className="cfg-readonly" data-testid={`cfg-readonly-${item.key}`}>
          {notUsed ? "Tidak bisa diubah karena tidak dipakai sistem."
            : `Hanya pemegang akses '${item.permission_label || "Pengaturan, Pengguna & Hak Akses"}' yang boleh mengubah pengaturan ini.`}
        </p>
      )}

      <footer className="cfg-card-foot">
        <button className="cfg-link-btn" onClick={() => onWhy(item)}
          data-testid={`cfg-why-${item.key}`}>
          <Layers size={13} /> Kenapa nilainya begini?
        </button>
        {item.simulate ? (
          <button className="cfg-link-btn" onClick={() => onSimulate(item, dirty ? draft : undefined)}
            data-testid={`cfg-sim-${item.key}`}>
            <FlaskConical size={13} /> Coba dulu
          </button>
        ) : null}
        <button className="cfg-link-btn" onClick={() => onHistory(item)}
          data-testid={`cfg-hist-${item.key}`}>
          <History size={13} /> Riwayat
        </button>
      </footer>
    </article>
  );
}
