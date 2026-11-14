/**
 * KP-T3 — "Jenjang yang berlaku": untuk satu PT, jenjang persetujuan yang SUNGGUH dipakai mesin per jenis dokumen
 * (`GET /api/approval-rules/effective` — fungsi pemilih aturan yang sama dengan mesin), dengan peringatan dari server
 * (celah, tumpang tindih, aturan PT yang lebih longgar dari grup, peran tidak dikenal).
 *
 * Aturan khusus PT menggantikan SEMUA aturan grup untuk jenis dokumen yang sama — kartu menyebut sumbernya dan
 * membuka daftar aturan grup yang tidak dipakai, supaya pemilik tidak mengira jenjang grup masih berlaku.
 */
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Layers } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import { useEntityScope } from "../../context/EntityScopeContext";
import { SOURCE_BADGE, tierLines, tierRange, roleLabel } from "./approvalRulesConstants";

function TierCard({ dt }) {
  const [showUnused, setShowUnused] = useState(false);
  const badge = SOURCE_BADGE[dt.source] || SOURCE_BADGE.kosong;
  const lines = tierLines(dt);
  const unused = dt.unused_group_rules || [];
  return (
    <div className="rounded-lg border border-[#E5E5EA] p-3" data-testid={`tier-card-${dt.doc_type}`}>
      <div className="flex items-center justify-between gap-2 mb-2">
        <p className="text-sm font-semibold">{dt.label}</p>
        <span className={`feature-badge ${badge.cls}`} data-testid={`tier-source-${dt.doc_type}`}>
          {badge.label}
        </span>
      </div>
      {dt.source === "kosong" || lines.length === 0 ? (
        <p className="text-xs text-muted" data-testid={`tier-empty-${dt.doc_type}`}>Belum ada aturan untuk PT ini.</p>
      ) : (
        <ul className="grid gap-1 text-sm tabular-nums" data-testid={`tier-lines-${dt.doc_type}`}>
          {lines.map((l) => (
            <li key={l.key}>
              {l.text}
              {l.unknown && (
                <span className="ml-1 text-xs text-[#A8221A]">(peran tidak dikenal — diperlakukan sebagai Manajer)</span>
              )}
            </li>
          ))}
        </ul>
      )}
      {(dt.warnings || []).map((w, i) => (
        <div key={`${w.code}-${i}`} className="notice-bar warning mt-2 text-xs"
          data-testid={`tier-warning-${dt.doc_type}-${w.code}`}>
          <AlertTriangle size={13} /> <span>{w.message}</span>
        </div>
      ))}
      {dt.source === "pt" && unused.length > 0 && (
        <div className="mt-2">
          <button type="button" className="text-xs font-semibold text-[#1F5FBF] underline"
            data-testid={`tier-unused-toggle-${dt.doc_type}`} onClick={() => setShowUnused((v) => !v)}>
            {showUnused
              ? "Sembunyikan aturan grup yang tidak dipakai"
              : `Lihat ${unused.length} aturan grup yang tidak dipakai`}
          </button>
          {showUnused && (
            <ul className="mt-1 grid gap-0.5 text-xs text-muted" data-testid={`tier-unused-${dt.doc_type}`}>
              {unused.map((r) => (
                <li key={r.rule_id}>
                  {tierRange(r.min_amount, r.max_amount)} — {r.required_role
                    ? (r.required_role_label || roleLabel(r.required_role)) : "tanpa persetujuan"}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

export default function ApprovalEffectiveTiers({ reloadKey = 0 }) {
  const { entities, selectedEntity } = useEntityScope();
  const [entityId, setEntityId] = useState(selectedEntity && selectedEntity !== "all" ? selectedEntity : "");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (selectedEntity && selectedEntity !== "all") setEntityId(selectedEntity);
  }, [selectedEntity]);

  const load = useCallback(async () => {
    if (!entityId) { setData(null); return; }
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get(`${API}/approval-rules/effective`, { params: { entity_id: entityId } });
      setData(res.data && Array.isArray(res.data.doc_types) ? res.data : { doc_types: [] });
    } catch (e) {
      setError(e);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [entityId]);

  useEffect(() => { load(); }, [load, reloadKey]);

  const options = (entities || []).map((e) => ({ value: e.id, label: e.code ? `${e.name} (${e.code})` : e.name }));
  const docTypes = data?.doc_types || [];
  return (
    <section className="section-card mb-4" data-testid="approval-effective-tiers">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h3 className="text-base font-semibold flex items-center gap-2"><Layers size={15} /> Jenjang yang berlaku</h3>
        <div className="min-w-[240px]">
          <KNSelect data-testid="approval-effective-entity" className="form-select" value={entityId}
            onValueChange={setEntityId} options={options} placeholder="Pilih PT" />
        </div>
      </div>
      {!entityId ? (
        <p className="text-sm text-muted" data-testid="approval-effective-pick">
          Pilih PT untuk melihat jenjang yang berlaku.
        </p>
      ) : error ? (
        <ErrorNotice message={error} onRetry={load} testId="approval-effective-error" />
      ) : loading || !data ? (
        <div className="grid gap-3 md:grid-cols-3" data-testid="approval-effective-loading">
          {[0, 1, 2].map((i) => <div key={i} className="h-28 rounded-lg bg-[#F0F0F3] animate-pulse" />)}
        </div>
      ) : docTypes.length === 0 ? (
        <p className="text-sm text-muted" data-testid="approval-effective-empty">Belum ada aturan untuk PT ini.</p>
      ) : (
        <div className="grid gap-3 md:grid-cols-3">
          {docTypes.map((dt) => <TierCard key={dt.doc_type} dt={dt} />)}
        </div>
      )}
    </section>
  );
}
