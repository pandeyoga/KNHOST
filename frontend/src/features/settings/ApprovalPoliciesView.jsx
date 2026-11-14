/**
 * KP-T4 — Aturan Persetujuan: SATU tabel kebijakan untuk semua antrean (`docs/blueprint/unit/KP-T4.md`).
 *
 * Satu layar menjawab "siapa menyetujui apa, mulai nominal berapa" per PT: jenis dokumen berkelompok (Penjualan,
 * Pembelian, Keuangan, Gudang, R&D, SDM), per jenis satu kartu ber-lencana sumber aturan dan tabel Jenjang · Mulai dari
 * · Sampai di bawah · Yang boleh menyetujui · Siapa saja yang lolos (peran tercantum DAN memegang izinnya).
 * "Coba nilai" menanyakan server jenjang dan siapa yang lolos untuk satu nominal.
 *
 * Baca: `GET /api/approval-policies` (+ `/check`), izin `settings.view`. Nilai yang tampil = nilai yang dipakai mesin
 * (`services/approval_policy_service.py`, dipanggil semua pintu persetujuan).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, FlaskConical, Layers } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import MoneyInput from "../../components/MoneyInput";
import { useEntityScope } from "../../context/EntityScopeContext";
import { useAppNav } from "../../context/AppNavContext";
import { entityOptions } from "../../utils/entityLabel";
import { parseDecimal } from "../../utils/decimalInput";
import {
  SOURCE_BADGE, approverText, fmtAngka, fmtBatasAtas, groupKinds, passingText, tableRows,
} from "./approvalPolicyHelpers";

export const SEMUA_PT = "all";

function CobaNilai({ kind, entityId }) {
  const [nilai, setNilai] = useState("");
  const [hasil, setHasil] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const coba = async () => {
    setBusy(true);
    setError(null);
    try {
      const amount = kind.has_amount ? (parseDecimal(String(nilai || "0")) || 0) : 0;
      const r = await axios.get(`${API}/approval-policies/check`,
        { params: { doc_kind: kind.doc_kind, entity_id: entityId, amount } });
      setHasil(r.data);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="mt-2" data-testid={`appol-try-${kind.doc_kind}`}>
      <div className="flex flex-wrap items-end gap-2">
        {kind.has_amount && (
          <label className="text-fs-12">
            <span className="block text-kn-text-2 mb-1">Nominal dokumen (Rp)</span>
            <MoneyInput value={nilai} onChange={setNilai} className="field" testId={`appol-try-amount-${kind.doc_kind}`} />
          </label>
        )}
        <button type="button" className="btn-secondary btn-sm" onClick={coba} disabled={busy}
          data-testid={`appol-try-btn-${kind.doc_kind}`}>
          <FlaskConical size={13} /> Coba nilai
        </button>
      </div>
      {error && <ErrorNotice message={error} onRetry={coba} testId={`appol-try-error-${kind.doc_kind}`} />}
      {hasil && (
        hasil.levels.length === 0 ? (
          <p className="text-fs-12 text-kn-text-2 mt-1" data-testid={`appol-try-none-${kind.doc_kind}`}>
            Nilai ini tidak butuh persetujuan.
          </p>
        ) : (
          <ul className="text-fs-12 mt-1 grid gap-0.5" data-testid={`appol-try-result-${kind.doc_kind}`}>
            {hasil.levels.map((lv) => (
              <li key={lv.level}>
                Jenjang {lv.level} — {lv.label}: <b>{lv.who.length ? lv.who.join(", ") : "belum ada yang lolos"}</b>
              </li>
            ))}
          </ul>
        )
      )}
    </div>
  );
}

export function KindCard({ kind, entityId, actions = null }) {
  const badge = SOURCE_BADGE[kind.source] || SOURCE_BADGE.bawaan;
  const rows = tableRows(kind);
  return (
    <section className="section-card mt-3" data-testid={`appol-card-${kind.doc_kind}`}>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <h4 className="text-fs-13 font-semibold">{kind.label}</h4>
        <div className="flex items-center gap-2">
          <span className={`feature-badge ${badge.cls}`} data-testid={`appol-source-${kind.doc_kind}`}>{badge.label}</span>
          {actions}
        </div>
      </div>
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
      {(kind.warnings || []).map((w, i) => (
        <div key={`${w.code}-${i}`} className="notice-bar warning mt-2 text-fs-12"
          data-testid={`appol-warning-${kind.doc_kind}-${w.code}`}>
          <AlertTriangle size={13} /> <span>{w.message}</span>
        </div>
      ))}
      {kind.note && <p className="text-fs-12 text-kn-text-2 mt-1">{kind.note}</p>}
      <CobaNilai kind={kind} entityId={entityId} />
    </section>
  );
}

export default function ApprovalPoliciesView({ renderActions = null, reloadKey = 0, onData = null }) {
  const { entities, selectedEntity } = useEntityScope();
  const { go, canOpen } = useAppNav();
  const [entityId, setEntityId] = useState(selectedEntity && selectedEntity !== SEMUA_PT ? selectedEntity : SEMUA_PT);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
  const groups = groupKinds(data?.kinds || []);

  return (
    <div data-testid="approval-policies-view">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <h3 className="text-base font-semibold flex items-center gap-2"><Layers size={15} /> Siapa menyetujui apa</h3>
        <div className="min-w-[260px]">
          <KNSelect data-testid="appol-entity" className="form-select" value={entityId}
            onValueChange={setEntityId} options={opsi} placeholder="Pilih PT" />
        </div>
      </div>
      <p className="text-fs-12 text-kn-text-2 mb-2" data-testid="appol-dual-note">
        Jumlah orang dan boleh-tidaknya menyetujui dokumen sendiri diatur di{" "}
        {canOpen && canOpen("settings-dual-control") ? (
          <button type="button" className="btn-ghost btn-sm" data-testid="appol-dual-link"
            onClick={() => go("settings-dual-control")}>Kontrol Dua Orang</button>
        ) : <b>Kontrol Dua Orang</b>}.
      </p>
      {error ? (
        <ErrorNotice message={error} onRetry={load} testId="appol-error" />
      ) : loading || !data ? (
        <div className="grid gap-3" data-testid="appol-loading">
          {[0, 1, 2].map((i) => <div key={i} className="h-24 rounded-lg bg-kn-neutral-soft animate-pulse" />)}
        </div>
      ) : groups.length === 0 ? (
        <p className="text-fs-13 text-kn-text-2" data-testid="appol-empty">Belum ada jenis dokumen.</p>
      ) : (
        groups.map((g) => (
          <div key={g.group} className="mt-3" data-testid={`appol-group-${g.group}`}>
            <h3 className="text-fs-13 font-semibold text-kn-text-2 uppercase">{g.group}</h3>
            {g.items.map((k) => (
              <KindCard key={k.doc_kind} kind={k} entityId={data.entity_id}
                actions={renderActions ? renderActions(k, data, load) : null} />
            ))}
          </div>
        ))
      )}
    </div>
  );
}
