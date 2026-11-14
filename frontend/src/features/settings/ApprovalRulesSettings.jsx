/**
 * Pengaturan › Persetujuan › Aturan Persetujuan.
 *
 * KP-T4 — SATU tabel kebijakan untuk semua antrean (`docs/blueprint/unit/KP-T4.md`): per PT, per jenis dokumen
 * (berkelompok Penjualan, Pembelian, Keuangan, Gudang, R&D, SDM) siapa yang boleh menyetujui, mulai nominal berapa, dan
 * siapa saja yang lolos (peran tercantum DAN memegang izinnya). Semua pintu persetujuan bertanya ke tabel yang sama
 * (`services/approval_policy_service.py`).
 *
 * Isi layar KP-T3 (tabel `approval_rules` + "Jenjang yang berlaku") digantikan: jalur tulis lama dimatikan server (410).
 * Tombol: **Ubah** (pop-up baku, alasan wajib), **Buat aturan khusus PT ini**, **Kembali ke aturan grup** (alasan
 * wajib), **Coba nilai**. Mengubah butuh izin kelola pengaturan; lapisan "Semua PT" hanya untuk peran lintas PT (server).
 */
import { useCallback, useEffect, useState } from "react";
import { Eye, Settings } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import DesktopOnlyNotice from "../../components/DesktopOnlyNotice";
import OkNotice from "../../components/OkNotice";
import { PageHeader } from "../../components/ListPageParts";
import { askReason } from "@/services/confirmService";
import { useEntityScope } from "../../context/EntityScopeContext";
import { can } from "../../config/roles";
import ApprovalPoliciesView from "./ApprovalPoliciesView";
import ApprovalPolicyEditor from "./ApprovalPolicyEditor";

export default function ApprovalRulesSettings({ currentUser }) {
  const canEdit = can(currentUser?.permissions, "settings", "manage");
  const { entities } = useEntityScope();
  const [roles, setRoles] = useState([]);
  const [editor, setEditor] = useState(null);   // {kind, entityId, mode}
  const [reloadKey, setReloadKey] = useState(0);
  const [ok, setOk] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!canEdit) return;
    axios.get(`${API}/approval-policies/kinds`)
      .then((r) => setRoles(Array.isArray(r.data?.roles) ? r.data.roles : []))
      .catch(() => setRoles([]));
  }, [canEdit]);

  const namaPT = useCallback((id) => {
    if (!id || id === "all") return "Semua PT (aturan grup)";
    const e = (entities || []).find((x) => x.id === id);
    return e ? (e.code ? `${e.name} (${e.code})` : e.name) : "PT terpilih";
  }, [entities]);

  const kembaliKeGrup = async (kind, entityId) => {
    const reason = await askReason({
      title: "Kembali ke aturan grup",
      message: `Aturan khusus ${namaPT(entityId)} untuk ${kind.label} dihapus; PT ini kembali memakai aturan grup.`,
      confirmLabel: "Kembali ke aturan grup", testId: "appol-reset-confirm",
    });
    if (!reason) return;
    setError("");
    try {
      await axios.delete(`${API}/approval-policies/${kind.doc_kind}`, { params: { entity_id: entityId, reason } });
      setOk(`${kind.label}: ${namaPT(entityId)} kembali memakai aturan grup.`);
      setReloadKey((k) => k + 1);
    } catch (e) {
      const d = e?.response?.data?.detail;
      setError(typeof d === "string" ? d : "Gagal mengembalikan ke aturan grup.");
    }
  };

  const renderActions = (kind, data) => {
    if (!canEdit) return null;
    const entityId = data?.entity_id || "all";
    if (entityId === "all") {
      return (
        <button type="button" className="btn-secondary btn-sm" data-testid={`appol-edit-${kind.doc_kind}`}
          onClick={() => setEditor({ kind, entityId, mode: kind.source === "grup" ? "edit" : "create" })}>Ubah</button>
      );
    }
    if (kind.source === "pt") {
      return (
        <>
          <button type="button" className="btn-secondary btn-sm" data-testid={`appol-edit-${kind.doc_kind}`}
            onClick={() => setEditor({ kind, entityId, mode: "edit" })}>Ubah</button>
          <button type="button" className="btn-ghost btn-sm" data-testid={`appol-reset-${kind.doc_kind}`}
            onClick={() => kembaliKeGrup(kind, entityId)}>Kembali ke aturan grup</button>
        </>
      );
    }
    return (
      <button type="button" className="btn-secondary btn-sm" data-testid={`appol-create-${kind.doc_kind}`}
        onClick={() => setEditor({ kind, entityId, mode: "create" })}>Buat aturan khusus PT ini</button>
    );
  };

  return (
    <div className="page-shell" data-testid="approval-rules-settings">
      <DesktopOnlyNotice />
      <PageHeader icon={Settings} title="Aturan Persetujuan" testId="approval-rules-head"
        subtitle="Siapa menyetujui apa, mulai nominal berapa — per PT, untuk semua antrean persetujuan" />
      {!canEdit && (
        <div className="notice-bar" data-testid="approval-rules-readonly">
          <Eye size={14} /> Mode baca — mengubah aturan persetujuan butuh izin kelola pengaturan.
        </div>
      )}
      <OkNotice message={ok} onDismiss={() => setOk("")} testId="appol-ok" />
      {error && <div className="notice-bar danger" data-testid="appol-action-error">{error}</div>}
      <section className="section-card">
        <ApprovalPoliciesView renderActions={renderActions} reloadKey={reloadKey} />
      </section>
      <ApprovalPolicyEditor open={!!editor} kind={editor?.kind} entityId={editor?.entityId}
        entityLabel={namaPT(editor?.entityId)} mode={editor?.mode} roles={roles}
        onClose={() => setEditor(null)}
        onSaved={(res) => {
          setEditor(null);
          setOk(`${res?.label || "Aturan"} tersimpan untuk ${namaPT(res?.entity_id || editor?.entityId)}.`);
          setReloadKey((k) => k + 1);
        }} />
    </div>
  );
}
