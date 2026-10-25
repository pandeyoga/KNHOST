import { useEffect, useState } from "react";
import axios, { API } from "../../../services/apiClient";
import FormModal from "../../../components/FormModal";
import LoadingLine from "../../../components/LoadingLine";
import { formatDateTime } from "../../../utils/formatters";

export function MappingHistory({ mkey, label, entityId, onClose }) {
  const [rows, setRows] = useState(null);
  useEffect(() => {
    axios.get(`${API}/gl/account-mappings/history`, { params: { key: mkey, ...(entityId ? { entity_id: entityId } : { entity_id: "" }) } })
      .then((r) => setRows(r.data || [])).catch(() => setRows([]));
  }, [mkey, entityId]);
  return (
    <FormModal open onClose={onClose} title={label ? `Riwayat perubahan akun · ${label}` : "Riwayat perubahan akun"} testId="glmap-history-modal">
      {rows === null ? <LoadingLine />
        : rows.length === 0 ? <p className="text-[12px] text-[#6B6B73]" data-testid="glmap-history-empty">Belum ada perubahan.</p>
        : <div className="divide-y divide-[#EFF0F2] text-[12px]">{rows.map((h) => (
          <div key={h.id} className="py-2" data-testid={`glmap-history-row-${h.id}`}>
            <p><b>{h.from_code}</b> → <b>{h.to_code}</b> {h.action === "reset" && <span className="text-[#6B6B73]">(dikembalikan)</span>}</p>
            <p className="text-[#6B6B73]">{h.by} · {formatDateTime(h.at)} · {h.scope_type === "entity" ? "khusus PT" : "global"}</p>
            <p className="italic">“{h.reason}”</p>
          </div>))}</div>}
    </FormModal>
  );
}
