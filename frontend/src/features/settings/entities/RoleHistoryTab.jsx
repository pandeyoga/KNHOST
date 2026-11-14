/**
 * RoleHistoryTab — PR-T6: tab "Riwayat" di editor peran. Dibaca dari `GET /api/access/roles/{id}/history`
 * (selisih potret sebelum/sesudah di jejak audit): Waktu (WIB) · Oleh · Perubahan · Akun terdampak.
 */
import { useCallback, useEffect, useState } from "react";
import { RotateCcw } from "lucide-react";

import { formatDateTime } from "../../../utils/formatters";
import { SummarySkeleton } from "./RoleSummaryPanel";
import { accessRoleHistory, errText } from "./entityApi";

const MAX_LIST = 8;

function ChangeCell({ item }) {
  const lines = [
    ...(item.added || []).map((t) => `+ ${t}`),
    ...(item.removed || []).map((t) => `− ${t}`),
    ...(item.other || []),
  ];
  const shown = lines.slice(0, MAX_LIST);
  return (
    <div>
      <p className="font-semibold">{item.action_label}</p>
      {shown.map((t) => <p key={t} className="text-kn-text-2">{t}</p>)}
      {lines.length > MAX_LIST && <p className="text-kn-text-2">dan {lines.length - MAX_LIST} perubahan lain</p>}
    </div>
  );
}

export default function RoleHistoryTab({ roleId }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    setItems(null); setError("");
    Promise.resolve().then(() => accessRoleHistory(roleId))
      .then((rows) => setItems(rows || []))
      .catch((e) => { setItems([]); setError(errText(e, "Riwayat tidak bisa dimuat.")); });
  }, [roleId]);
  useEffect(() => { load(); }, [load]);

  if (items === null) return <SummarySkeleton testId="role-history-loading" />;
  if (error) {
    return (
      <div className="flex flex-wrap items-center gap-2" data-testid="role-history-error">
        <p className="text-fs-12 text-kn-danger-text">{error}</p>
        <button type="button" className="secondary-button btn-sm" onClick={load}><RotateCcw size={12} /> Coba lagi</button>
      </div>
    );
  }
  if (items.length === 0) {
    return <p className="text-fs-12 text-kn-text-2" data-testid="role-history-empty">Belum ada perubahan tercatat.</p>;
  }
  return (
    <div className="overflow-auto" data-testid="role-history">
      <table className="w-full text-left text-fs-12 text-kn-text">
        <thead>
          <tr className="border-b border-kn-divider text-kn-text-2">
            <th className="py-1 pr-2 font-semibold">Waktu (WIB)</th>
            <th className="py-1 pr-2 font-semibold">Oleh</th>
            <th className="py-1 pr-2 font-semibold">Perubahan</th>
            <th className="py-1 font-semibold">Akun terdampak</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it, i) => (
            <tr key={`${it.at}-${i}`} className="border-b border-kn-divider align-top" data-testid="role-history-row">
              <td className="py-1 pr-2 whitespace-nowrap">{formatDateTime(it.at)}</td>
              <td className="py-1 pr-2">{it.actor || "—"}</td>
              <td className="py-1 pr-2"><ChangeCell item={it} /></td>
              <td className="py-1">{it.users}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
