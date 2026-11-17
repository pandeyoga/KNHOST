/**
 * KP-T4 — Aturan Persetujuan: SATU tabel kebijakan untuk semua antrean (`docs/blueprint/unit/KP-T4.md`).
 *
 * Satu layar menjawab "siapa menyetujui apa, mulai nominal berapa" per PT: jenis dokumen berkelompok (Penjualan,
 * Pembelian, Keuangan, Gudang, R&D, SDM), per jenis lencana sumber aturan dan tabel Jenjang · Mulai dari · Sampai di
 * bawah · Yang boleh menyetujui · Siapa saja yang lolos (peran tercantum DAN memegang izinnya).
 * "Coba nilai" menanyakan server jenjang dan siapa yang lolos untuk satu nominal.
 *
 * Pola UI 16 Nov (`docs/blueprint/04_POLA_UI.md` §2.D, pemilik M43): daftar padat, SATU baris per jenis dokumen —
 * nama (?) · ringkasan jenjang/ambang · asal aturan · Ubah. Baris dibuka di tempat: tabel jenjang, peringatan satu baris
 * kecil, aksi lanjutan, dan isian ubah (`renderEditor`). "Coba nilai" = SATU penguji di bilah atas (jenis ▾ · nominal ·
 * Coba), bukan isian di tiap kartu. Dulu: satu kartu bertabel per jenis + lencana "Aturan bawaan (belum disimpan)".
 *
 * Baca: `GET /api/approval-policies` (+ `/check`), izin `settings.view`. Nilai yang tampil = nilai yang dipakai mesin
 * (`services/approval_policy_service.py`, dipanggil semua pintu persetujuan).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Building2, ChevronDown, ChevronRight, FlaskConical } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import MoneyInput from "../../components/MoneyInput";
import { HelpTip } from "../../components/ListPageParts";
import { useEntityScope } from "../../context/EntityScopeContext";
import { useAppNav } from "../../context/AppNavContext";
import { entityOptions } from "../../utils/entityLabel";
import { parseDecimal } from "../../utils/decimalInput";
import {
  SOURCE_BADGE, approverText, fmtAngka, fmtBatasAtas, groupKinds, issueCount, passingText, ruleSummary, tableRows,
} from "./approvalPolicyHelpers";

export const SEMUA_PT = "all";

const BANTUAN = "Siapa menyetujui apa, mulai nominal berapa — per PT, untuk semua antrean persetujuan. Tiap baris satu "
  + "jenis dokumen; buka baris untuk melihat jenjangnya. \"Yang lolos\" = peran tercantum yang juga memegang akses "
  + "modulnya. Coba nilai: pilih jenis dokumen dan nominal untuk melihat jenjang dan siapa yang lolos.";

/** Penjelasan satu jenis (ikon ? di nama): catatan server + arti kolom "yang lolos". */
function kindHelp(kind) {
  return [kind.note, kind.permission_label
    ? `Yang lolos = peran tercantum yang juga memegang akses ${kind.permission_label}.` : ""].filter(Boolean).join(" ");
}

/** Penguji "Coba nilai" bersama — satu untuk semua jenis dokumen. */
function useCobaNilai(kinds, entityId) {
  const [kindId, setKindId] = useState("");
  const [nilai, setNilai] = useState("");
  const [hasil, setHasil] = useState(null);   // {label, amount, hasAmount, levels}
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const kind = kinds.find((k) => k.doc_kind === kindId) || null;
  useEffect(() => { setHasil(null); setError(null); }, [kindId, entityId]);
  const coba = async () => {
    if (!kind) return;
    setBusy(true);
    setError(null);
    try {
      const amount = kind.has_amount ? (parseDecimal(String(nilai || "0")) || 0) : 0;
      const r = await axios.get(`${API}/approval-policies/check`,
        { params: { doc_kind: kind.doc_kind, entity_id: entityId, amount } });
      setHasil({ label: kind.label, amount, hasAmount: !!kind.has_amount, levels: r.data?.levels || [] });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  return { kind, kindId, setKindId, nilai, setNilai, hasil, error, busy, coba };
}

function CobaNilaiControls({ t, kinds }) {
  const opsi = useMemo(() => kinds.map((k) => ({ value: k.doc_kind, label: k.label })), [kinds]);
  return (
    <div className="cfg-try" data-testid="appol-try">
      <span className="cfg-scope-caption"><FlaskConical size={13} /> Coba nilai</span>
      <KNSelect data-testid="appol-try-kind" className="field cfg-select-sm" value={t.kindId} onValueChange={t.setKindId}
        options={opsi} placeholder="Pilih jenis dokumen" aria-label="Jenis dokumen yang dicoba" />
      {t.kind?.has_amount ? (
        <span className="cfg-try-money">
          <MoneyInput value={t.nilai} onChange={t.setNilai} showPreview={false} testId="appol-try-amount"
            placeholder="Nominal" aria-label="Nominal dokumen (Rp)" />
        </span>
      ) : null}
      <button type="button" className="btn-secondary btn-sm" onClick={t.coba} disabled={t.busy || !t.kind}
        data-testid="appol-try-btn">Coba</button>
    </div>
  );
}

function CobaNilaiHasil({ t }) {
  if (t.error) return <ErrorNotice message={t.error} onRetry={t.coba} testId="appol-try-error" />;
  if (!t.hasil) return null;
  const judul = `${t.hasil.label}${t.hasil.hasAmount ? ` · Rp ${fmtAngka(t.hasil.amount)}` : ""}`;
  if (t.hasil.levels.length === 0) {
    return <p className="cfg-try-result" data-testid="appol-try-none"><b>{judul}:</b> nilai ini tidak butuh persetujuan.</p>;
  }
  return (
    <ul className="cfg-try-result" data-testid="appol-try-result">
      <li><b>{judul}:</b></li>
      {t.hasil.levels.map((lv) => (
        <li key={lv.level}>
          Jenjang {lv.level} — {lv.label}: <b>{lv.who.length ? lv.who.join(", ") : "belum ada yang lolos"}</b>
        </li>
      ))}
    </ul>
  );
}

function KindTable({ kind }) {
  const rows = tableRows(kind);
  return (
    <div className="table-container">
      <table className="data-table">
        <thead>
          <tr>
            <th>Jenjang</th>
            {kind.has_amount && <th className="text-right">Mulai dari (Rp)</th>}
            {kind.has_amount && <th className="text-right">Sampai di bawah (Rp)</th>}
            <th>Yang boleh menyetujui</th>
            <th>Siapa saja yang lolos</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} data-testid={`appol-row-${kind.doc_kind}-${r.level}`}>
              <td>{r.first ? `${r.level} · ${r.label}` : ""}</td>
              {kind.has_amount && <td className="text-right tabular-nums">{fmtAngka(r.tier.min_amount)}</td>}
              {kind.has_amount && <td className="text-right tabular-nums">{fmtBatasAtas(r.tier.max_amount)}</td>}
              <td>{approverText(r.tier)}</td>
              <td>
                {passingText(r.tier)}
                {(r.tier.no_permission_labels || []).map((l) => (
                  <div key={l} className="text-fs-12 text-kn-warning-text" data-testid={`appol-noperm-${kind.doc_kind}`}>
                    {l}: belum punya akses {kind.permission_label}
                  </div>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Satu baris jenis dokumen (daftar padat). `editor` = isian ubah di tempat (menggantikan tabel selama dibuka). */
export function KindRow({ kind, open, onToggle, actions = null, detailActions = null, editor = null }) {
  const badge = SOURCE_BADGE[kind.source] || SOURCE_BADGE.bawaan;
  const masalah = issueCount(kind);
  const terbuka = open || Boolean(editor);
  return (
    <div data-testid={`appol-card-${kind.doc_kind}`}>
      <div className={`cfg-row${terbuka ? " is-open" : ""}`}>
        <button type="button" className="cfg-card-toggle" aria-expanded={terbuka} onClick={onToggle}
          aria-label={`${terbuka ? "Tutup" : "Buka"} rincian ${kind.label}`} data-testid={`appol-toggle-${kind.doc_kind}`}>
          {terbuka ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
        <span className="cfg-row-name">
          <span className="cfg-row-title">{kind.label}</span>
          <HelpTip text={kindHelp(kind)} testId={`appol-help-${kind.doc_kind}`} label={`Tentang ${kind.label}`} />
          {masalah > 0 ? (
            <span className="badge-orange" data-testid={`appol-issues-${kind.doc_kind}`}
              title="Ada peringatan atau peran tercantum yang belum punya akses — buka baris untuk melihat">
              <AlertTriangle size={11} /> {masalah} perlu dicek
            </span>
          ) : null}
        </span>
        <span className="cfg-row-val" data-testid={`appol-summary-${kind.doc_kind}`}>{ruleSummary(kind)}</span>
        <span className="cfg-row-tags">
          <span className={badge.cls} title={badge.title} data-testid={`appol-source-${kind.doc_kind}`}>{badge.label}</span>
          {actions}
        </span>
      </div>
      {terbuka ? (
        <div className="cfg-row-body" data-testid={`appol-detail-${kind.doc_kind}`}>
          {editor || (
            <>
              <KindTable kind={kind} />
              {(kind.warnings || []).map((w, i) => (
                <p key={`${w.code}-${i}`} className="cfg-row-line warn" data-testid={`appol-warning-${kind.doc_kind}-${w.code}`}>
                  <AlertTriangle size={12} /> <span>{w.message}</span>
                </p>
              ))}
              {detailActions}
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}

export default function ApprovalPoliciesView({
  renderActions = null, renderDetailActions = null, renderEditor = null, reloadKey = 0, onData = null,
}) {
  const { entities, selectedEntity } = useEntityScope();
  const { go, canOpen } = useAppNav();
  const [entityId, setEntityId] = useState(selectedEntity && selectedEntity !== SEMUA_PT ? selectedEntity : SEMUA_PT);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openKinds, setOpenKinds] = useState(() => new Set());

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await axios.get(`${API}/approval-policies`, { params: { entity_id: entityId } });
      setData(r.data);
      if (onData) onData(r.data);
    } catch (e) {
      setError(e);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [entityId, onData]);

  useEffect(() => { load(); }, [load, reloadKey]);

  const opsi = useMemo(() => [{ value: SEMUA_PT, label: "Semua PT (aturan grup)" },
    ...entityOptions(entities).filter((o) => o.value && o.value !== SEMUA_PT)], [entities]);
  const kinds = useMemo(() => data?.kinds || [], [data]);
  const groups = groupKinds(kinds);
  const coba = useCobaNilai(kinds, data?.entity_id || entityId);
  // Membuka baris juga memilih jenis itu di penguji "Coba nilai" (sama seperti daftar pengaturan: boleh beberapa terbuka).
  const toggle = (k) => {
    const buka = !openKinds.has(k.doc_kind);
    setOpenKinds((cur) => {
      const n = new Set(cur);
      if (n.has(k.doc_kind)) n.delete(k.doc_kind); else n.add(k.doc_kind);
      return n;
    });
    if (buka) coba.setKindId(k.doc_kind);
  };

  return (
    <div className="cfg-group-view" data-testid="approval-policies-view">
      <div className="cfg-toolbar">
        <div className="cfg-scope-box">
          <span className="cfg-scope-caption"><Building2 size={13} /> Berlaku untuk</span>
          <KNSelect data-testid="appol-entity" className="field cfg-select-sm" value={entityId}
            onValueChange={setEntityId} options={opsi} placeholder="Pilih PT" aria-label="Berlaku untuk" />
        </div>
        {kinds.length ? <CobaNilaiControls t={coba} kinds={kinds} /> : null}
      </div>
      <CobaNilaiHasil t={coba} />
      <div className="cfg-group-line">
        <b>Siapa menyetujui apa</b>
        <HelpTip text={BANTUAN} testId="appol-help" label="Tentang aturan persetujuan" />
        {data ? <span className="cfg-hint-sm">{kinds.length} jenis dokumen</span> : null}
        <span className="cfg-hint-sm" data-testid="appol-dual-note">
          · Jumlah orang &amp; menyetujui dokumen sendiri:{" "}
          {canOpen && canOpen("settings-dual-control") ? (
            <button type="button" className="cfg-link-btn" data-testid="appol-dual-link"
              onClick={() => go("settings-dual-control")}>Kontrol Dua Orang</button>
          ) : <b>Kontrol Dua Orang</b>}
        </span>
      </div>
      {error ? (
        <ErrorNotice message={error} onRetry={load} testId="appol-error" />
      ) : loading || !data ? (
        <div className="grid gap-2" data-testid="appol-loading">
          {[0, 1, 2].map((i) => <div key={i} className="h-10 rounded-lg bg-kn-neutral-soft animate-pulse" />)}
        </div>
      ) : groups.length === 0 ? (
        <p className="text-fs-13 text-kn-text-2" data-testid="appol-empty">Belum ada jenis dokumen.</p>
      ) : (
        groups.map((g) => (
          <section key={g.group} className="cfg-section" data-testid={`appol-group-${g.group}`}>
            <h4 className="cfg-section-title">{g.group}</h4>
            <div className="cfg-rows">
              {g.items.map((k) => (
                <KindRow key={k.doc_kind} kind={k} open={openKinds.has(k.doc_kind)} onToggle={() => toggle(k)}
                  actions={renderActions ? renderActions(k, data, load) : null}
                  detailActions={renderDetailActions ? renderDetailActions(k, data, load) : null}
                  editor={renderEditor ? renderEditor(k, data) : null} />
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  );
}
