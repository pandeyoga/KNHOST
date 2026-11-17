/**
 * Pengaturan › Persetujuan › Aturan Persetujuan.
 *
 * KP-T4 — SATU tabel kebijakan untuk semua antrean (`docs/blueprint/unit/KP-T4.md`): per PT, per jenis dokumen
 * (berkelompok Penjualan, Pembelian, Keuangan, Gudang, R&D, SDM) siapa yang boleh menyetujui, mulai nominal berapa, dan
 * siapa saja yang lolos (peran tercantum DAN memegang izinnya). Semua pintu persetujuan bertanya ke tabel yang sama
 * (`services/approval_policy_service.py`).
 *
 * Isi layar KP-T3 (tabel `approval_rules` + "Jenjang yang berlaku") digantikan: jalur tulis lama dimatikan server (410).
 * Mengubah butuh izin kelola pengaturan; lapisan "Semua PT" hanya untuk peran lintas PT (server).
 *
 * Pola UI 16 Nov (`docs/blueprint/04_POLA_UI.md` §2.D, pemilik M43): tab hub sudah menamai layar — tanpa kepala halaman
 * kedua. Tiap baris punya SATU tombol **Ubah** yang membuka isian di tempat; pada PT yang masih mengikuti aturan grup,
 * Ubah = membuat aturan khusus PT ini (judul isian menyebutnya). **Kembali ke aturan grup** (alasan wajib) ada di baris
 * yang dibuka. Dulu: tombol "Buat aturan khusus PT ini" di tiap kartu dan pop-up yang menutupi daftar.
 */
import { useCallback, useEffect, useState } from "react";
import { Eye } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import DesktopOnlyNotice from "../../components/DesktopOnlyNotice";
import OkNotice from "../../components/OkNotice";
import { askReason } from "@/services/confirmService";
import { useEntityScope } from "../../context/EntityScopeContext";
import { can } from "../../config/roles";
import ApprovalPoliciesView from "./ApprovalPoliciesView";
import ApprovalPolicyEditor from "./ApprovalPolicyEditor";

/** Mode isian untuk satu jenis pada lapisan terpilih: "edit" (aturan lapisan ini sudah ada) atau "create". */
export function editMode(kind, entityId) {
  if (entityId === "all") return kind.source === "grup" ? "edit" : "create";
  return kind.source === "pt" ? "edit" : "create";
}

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

  const sedangDiubah = (kind, data) => Boolean(editor) && editor.kind.doc_kind === kind.doc_kind
    && editor.entityId === (data?.entity_id || "all");

  // Satu tombol di baris: Ubah. Pada PT yang masih ikut aturan grup/bawaan, Ubah membuat aturan khusus PT ini.
  const renderActions = (kind, data) => {
    if (!canEdit || sedangDiubah(kind, data)) return null;
    const entityId = data?.entity_id || "all";
    const mode = editMode(kind, entityId);
    const buatKhusus = entityId !== "all" && mode === "create";
    return (
      <button type="button" className="btn-secondary btn-sm"
        data-testid={buatKhusus ? `appol-create-${kind.doc_kind}` : `appol-edit-${kind.doc_kind}`}
        title={buatKhusus ? "Buat aturan khusus PT ini (PT lain tetap mengikuti aturan grup)" : undefined}
        onClick={() => { setOk(""); setEditor({ kind, entityId, mode }); }}>Ubah</button>
    );
  };

  // Di baris yang dibuka: keterangan lapisan + "Kembali ke aturan grup" untuk aturan khusus PT.
  const renderDetailActions = (kind, data) => {
    const entityId = data?.entity_id || "all";
    if (entityId === "all") return null;
    if (kind.source === "pt") {
      return canEdit ? (
        <div className="cfg-row-actions">
          <button type="button" className="ghost-button btn-sm" data-testid={`appol-reset-${kind.doc_kind}`}
            onClick={() => kembaliKeGrup(kind, entityId)}>Kembali ke aturan grup</button>
        </div>
      ) : null;
    }
    return (
      <p className="cfg-row-line" data-testid={`appol-follow-${kind.doc_kind}`}>
        {namaPT(entityId)} mengikuti {kind.source === "grup" ? "aturan grup" : "aturan bawaan sistem"}
        {canEdit ? ". Ubah = membuat aturan khusus PT ini; PT lain tidak terpengaruh." : "."}
      </p>
    );
  };

  const renderEditor = (kind, data) => (sedangDiubah(kind, data) ? (
    <ApprovalPolicyEditor open kind={editor.kind} entityId={editor.entityId}
      entityLabel={namaPT(editor.entityId)} mode={editor.mode} roles={roles}
      onClose={() => setEditor(null)}
      onSaved={(res) => {
        setEditor(null);
        setOk(`${res?.label || "Aturan"} tersimpan untuk ${namaPT(res?.entity_id || editor?.entityId)}.`);
        setReloadKey((k) => k + 1);
      }} />
  ) : null);

  return (
    <div className="page-shell" data-testid="approval-rules-settings">
      <DesktopOnlyNotice />
      {!canEdit && (
        <p className="cfg-readonly-line mb-2" data-testid="approval-rules-readonly">
          <Eye size={13} aria-hidden="true" /> Hanya baca — mengubah aturan persetujuan butuh izin kelola pengaturan.
        </p>
      )}
      <OkNotice message={ok} onDismiss={() => setOk("")} testId="appol-ok" />
      {error && <div className="notice-bar danger" data-testid="appol-action-error">{error}</div>}
      <ApprovalPoliciesView renderActions={renderActions} renderDetailActions={renderDetailActions}
        renderEditor={renderEditor} reloadKey={reloadKey} />
    </div>
  );
}
