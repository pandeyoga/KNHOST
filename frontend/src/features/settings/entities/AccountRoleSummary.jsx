/**
 * AccountRoleSummary — PR-T6: ringkasan peran yang dipilih di formulir akun (`GET /api/access/roles/{id}/summary`,
 * izin `user.view`): halaman awal, data yang terlihat, PT, dan jumlah modul per tingkat; tautan **Lihat hak peran ini**
 * membuka editor peran dalam mode baca (hanya bagi pemegang `permission.view`).
 */
import { useEffect, useState } from "react";
import { Eye } from "lucide-react";

import RoleEditorDrawer from "./RoleEditorDrawer";
import { SummarySkeleton, levelCounts, ptText } from "./RoleSummaryPanel";
import { accessModules, accessRoleSummary, accessRolesFull, errText } from "./entityApi";

function RoleViewer({ roleId, onClose }) {
  const [state, setState] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    Promise.all([accessRolesFull(), accessModules()])
      .then(([full, m]) => { if (alive) setState({ roles: full.roles, modules: m.modules || [],
        labels: { resource_labels: m.resource_labels || {}, action_labels: m.action_labels || {} } }); })
      .catch((e) => { if (alive) setError(errText(e, "Hak peran tidak bisa dimuat.")); });
    return () => { alive = false; };
  }, [roleId]);
  const role = state?.roles.find((r) => r.id === roleId);
  if (error) return <p className="text-fs-12 text-kn-danger-text" data-testid="account-role-viewer-error">{error}</p>;
  if (!role) return null;
  return (
    <RoleEditorDrawer role={role} roles={state.roles} modules={state.modules} labels={state.labels} canManage={false}
                      onClose={onClose} onSaved={onClose} onRefresh={() => {}} onError={() => {}} />
  );
}

export default function AccountRoleSummary({ roleId, canViewRoles }) {
  const [summary, setSummary] = useState(null);
  const [failed, setFailed] = useState(false);
  const [viewing, setViewing] = useState(false);
  useEffect(() => {
    let alive = true;
    setSummary(null); setFailed(false);
    if (!roleId) return undefined;
    Promise.resolve().then(() => accessRoleSummary(roleId))
      .then((s) => { if (alive) setSummary(s || null); })
      .catch(() => { if (alive) setFailed(true); });
    return () => { alive = false; };
  }, [roleId]);
  if (!roleId) return null;
  const n = levelCounts(summary?.modules);
  return (
    <div className="rounded-md border border-kn-divider bg-white p-2" data-testid="account-role-summary">
      {!summary && !failed && <SummarySkeleton testId="account-role-summary-loading" />}
      {failed && <p className="text-fs-12 text-kn-text-2" data-testid="account-role-summary-error">Ringkasan tidak bisa dimuat.</p>}
      {summary && (
        <ul className="space-y-0.5 text-fs-12 text-kn-text" data-testid="account-role-summary-body">
          <li>Halaman awal: <b>{summary.home?.label}</b></li>
          <li>Data yang terlihat: <b>{summary.data_scope?.label}</b></li>
          <li>{ptText(summary.cross_entity)}</li>
          <li data-testid="account-role-summary-counts">
            Modul: {n.manage} semua aksi · {n.partial} sebagian · {n.view} lihat saja
          </li>
        </ul>
      )}
      {canViewRoles && (
        <button type="button" className="secondary-button btn-sm mt-1.5" data-testid="account-role-summary-open" onClick={() => setViewing(true)}>
          <Eye size={12} /> Lihat hak peran ini
        </button>
      )}
      {viewing && <RoleViewer roleId={roleId} onClose={() => setViewing(false)} />}
    </div>
  );
}
