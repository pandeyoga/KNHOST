/**
 * Approval Rules Settings — matriks ambang persetujuan per jenis dokumen.
 * Skema TUNGGAL = skema mesin: {doc_type, entity_id, min_amount, max_amount,
 * required_role, sort, active, is_percent}.
 *
 * Fase 3 · P2 (D-04, keputusan pemilik 26 Okt) — Pengaturan › Persetujuan › Aturan Persetujuan:
 *  · SATU jalan aktif/nonaktif: tombol "Nonaktifkan/Aktifkan" + dialog konfirmasi (centang "Aktif" di form dicabut;
 *    lencana status hanya label, tanpa ikon sampah);
 *  · manajer MEMBACA aturan di sini (dulu hanya lewat Master per Badan Usaha, yang kini menautkan ke sini) — tombol
 *    buat/ubah/nonaktifkan hanya untuk izin settings.manage (server tetap penjaga: GET = settings.view);
 *  · L-02: kepala halaman baku (`PageHeader`) + tabel di `section-card`; L-04 kelas C: banner desktop di HP.
 */
import { useState, useEffect } from "react";
import axios, { API } from "../../services/apiClient";
import {
  AlertCircle, CheckCircle2, Edit2, Eye, Loader2, Plus, Power, Settings, X
} from "lucide-react";
import ApprovalRuleForm from "./ApprovalRuleForm";
import FormModal from "../../components/FormModal";
import DesktopOnlyNotice from "../../components/DesktopOnlyNotice";
import { PageHeader } from "../../components/ListPageParts";
import { docTypeLabel, fmtRange, roleLabel } from "./approvalRulesConstants";
import { askConfirm } from "@/services/confirmService";
import { useEntityScope } from "../../context/EntityScopeContext";
import { can } from "../../config/roles";

const EMPTY_FORM = {
  doc_type: "sales_order",
  min_amount: "",
  max_amount: "",
  required_role: "manager",
  sort: 1,
  active: true,
  description: "",
  entity_id: "all",
};

export default function ApprovalRulesSettings({ currentUser }) {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [formData, setFormData] = useState(EMPTY_FORM);

  const token = localStorage.getItem("kn_token");
  const isAdmin = can(currentUser?.permissions, "settings", "manage");   // Sisir gerbang peran (2026-10-20) — tulis /approval-rules = settings.manage
  const auth = { headers: { Authorization: `Bearer ${token}` } };
  const { entities } = useEntityScope();
  const entityName = (id) => {
    const e = entities.find((x) => x.id === id);
    return e ? (e.code ? `${e.name} (${e.code})` : e.name) : id;
  };

  useEffect(() => {
    loadRules();
  }, []); // eslint-disable-line

  async function loadRules() {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/approval-rules`, auth);
      setRules(res.data || []);
      setError(null);
    } catch (e) {
      setError("Gagal memuat rules: " + (e.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  }

  function resetForm() {
    setFormData(EMPTY_FORM);
    setEditingRule(null);
    setShowCreateForm(false);
  }

  function handleEdit(rule) {
    setFormData({
      doc_type: rule.doc_type || "sales_order",
      min_amount: rule.min_amount ?? "",
      max_amount: rule.max_amount ?? "",
      required_role: rule.required_role || "",
      sort: rule.sort ?? 1,
      active: rule.active !== false,
      description: rule.description || "",
      entity_id: rule.entity_id || "all",
    });
    setEditingRule(rule);
    setShowCreateForm(true);
  }

  function buildPayload() {
    const min = parseFloat(formData.min_amount);
    return {
      doc_type: formData.doc_type,
      min_amount: Number.isNaN(min) ? 0 : min,
      max_amount: formData.max_amount === "" || formData.max_amount === null
        ? null : parseFloat(formData.max_amount),
      required_role: formData.required_role || "",
      sort: parseInt(formData.sort) || 1,
      active: !!formData.active,
      description: formData.description || "",
      entity_id: formData.entity_id || "all",
    };
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const payload = buildPayload();
    if (payload.max_amount !== null && payload.max_amount <= payload.min_amount) {
      return setError("Nilai maksimal harus lebih besar dari nilai minimal");
    }
    try {
      if (editingRule) {
        await axios.patch(`${API}/approval-rules/${editingRule.id}`, payload, auth);
        setNotice("Aturan berhasil diupdate!");
      } else {
        await axios.post(`${API}/approval-rules`, payload, auth);
        setNotice("Aturan berhasil dibuat!");
      }
      resetForm();
      loadRules();
    } catch (e) {
      setError("Gagal menyimpan: " + (e.response?.data?.detail || e.message));
    }
  }

  async function handleDelete(rule) {
    const ok = await askConfirm({
      title: `Nonaktifkan aturan ${docTypeLabel(rule.doc_type)} (${fmtRange(rule)})?`,
      message: "Mesin persetujuan berhenti membaca aturan ini; dokumen pada rentang tersebut tidak lagi otomatis meminta persetujuan.",
      confirmLabel: "Nonaktifkan Aturan",
      danger: true,
      testId: "approval-rule-delete-confirm",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/approval-rules/${rule.id}`, auth);
      setNotice("Aturan dinonaktifkan.");
      loadRules();
    } catch (e) {
      setError("Gagal menonaktifkan: " + (e.response?.data?.detail || e.message));
    }
  }

  // G5-20 — badge "Aktif" dulu langsung PATCH sekali klik (tanpa konfirmasi) sementara ikon sampah membuka dialog
  // "Nonaktifkan aturan". Kini satu tombol ⏻: aktif → dialog nonaktifkan; nonaktif → dialog aktifkan.
  async function toggleActive(rule) {
    if (rule.active !== false) { await handleDelete(rule); return; }
    const ok = await askConfirm({
      title: `Aktifkan aturan ${docTypeLabel(rule.doc_type)} (${fmtRange(rule)})?`,
      message: "Mesin persetujuan kembali membaca aturan ini untuk dokumen baru pada rentang tersebut.",
      confirmLabel: "Aktifkan Aturan",
    });
    if (!ok) return;
    try {
      await axios.patch(`${API}/approval-rules/${rule.id}`,
        { active: rule.active === false }, auth);
      loadRules();
    } catch (e) {
      setError("Gagal mengubah status: " + (e.response?.data?.detail || e.message));
    }
  }

  return (
    <div data-testid="approval-rules-settings" className="view-container">
      <DesktopOnlyNotice testId="settings-desktop-notice" what="Pengaturan" />
      {notice && (
        <div className="notice-bar success">
          <CheckCircle2 size={14} /> {notice}
          <button onClick={() => setNotice(null)}><X size={12} /></button>
        </div>
      )}

      {error && (
        <div className="notice-bar danger">
          <AlertCircle size={14} /> {error}
          <button onClick={() => setError(null)}><X size={12} /></button>
        </div>
      )}

      <PageHeader icon={Settings} title="Aturan Persetujuan" testId="approval-rules-head"
        subtitle="Rentang nilai dokumen & peran yang berwenang memutuskan — dibaca langsung oleh mesin persetujuan"
        actions={isAdmin && !showCreateForm ? (
          <button data-testid="create-rule-btn" className="primary-button" onClick={() => setShowCreateForm(true)}>
            <Plus size={14} /> Buat Aturan Baru
          </button>
        ) : null} />
      {!isAdmin && (
        <div className="notice-bar" data-testid="approval-rules-readonly">
          <Eye size={14} /> Mode baca — mengubah aturan persetujuan butuh izin kelola pengaturan.
        </div>
      )}

      <FormModal
        open={showCreateForm && isAdmin}
        onClose={resetForm}
        title={editingRule ? "Ubah Aturan Persetujuan" : "Aturan Persetujuan Baru"}
        subtitle="Rentang nilai dokumen & peran yang berwenang memutuskan"
        icon={Settings}
        size="lg"
        testId="rule-form-modal"
      >
        <ApprovalRuleForm
          variant="modal"
          formData={formData}
          setFormData={setFormData}
          onSubmit={handleSubmit}
          onCancel={resetForm}
          editingRule={editingRule}
        />
      </FormModal>

      {loading ? (
        <div className="loading-state">
          <Loader2 size={24} className="spin" />
          <p>Memuat aturan persetujuan…</p>
        </div>
      ) : rules.length === 0 ? (
        <div className="empty-state">
          <Settings size={32} style={{ opacity: 0.3 }} />
          <p>Belum ada aturan persetujuan.</p>
          {isAdmin && !showCreateForm && (
            <button className="primary-button" onClick={() => setShowCreateForm(true)}>
              <Plus size={14} /> Buat Aturan Pertama
            </button>
          )}
        </div>
      ) : (
        <section className="section-card">
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Jenis Dokumen</th>
                <th>Cakupan</th>
                <th>Rentang Nilai</th>
                <th>Peran Penyetuju</th>
                <th className="text-center">Urutan</th>
                <th>Status</th>
                {isAdmin && <th className="text-right">Aksi</th>}
              </tr>
            </thead>
            <tbody>
              {rules.map(rule => (
                <tr key={rule.id} data-testid={`rule-row-${rule.id}`}>
                  <td>
                    <span className="feature-badge badge-blue">
                      {docTypeLabel(rule.doc_type)}
                    </span>
                    {rule.description && (
                      <div className="text-xs text-muted">{rule.description}</div>
                    )}
                  </td>
                  <td className="text-sm">
                    {(!rule.entity_id || rule.entity_id === "all") ? "Semua entitas" : entityName(rule.entity_id)}
                  </td>
                  <td className="font-mono text-sm tabular-nums whitespace-nowrap">
                    {fmtRange(rule)}
                  </td>
                  <td>
                    {rule.required_role ? (
                      <span className="feature-badge badge-purple">{roleLabel(rule.required_role)}</span>
                    ) : (
                      <span className="text-xs text-muted">Tanpa persetujuan (otomatis)</span>
                    )}
                  </td>
                  <td className="text-center tabular-nums">{rule.sort}</td>
                  <td>
                    <span
                      data-testid={`toggle-rule-${rule.id}`}
                      className={`status-pill ${rule.active !== false ? "pill-success" : "pill-muted"}`}
                    >
                      {rule.active !== false ? "Aktif" : "Nonaktif"}
                    </span>
                  </td>
                  {isAdmin && (
                  <td>
                    <div className="flex justify-end gap-2">
                      <button
                        data-testid={`edit-rule-${rule.id}`}
                        className="icon-button"
                        title="Ubah aturan"
                        aria-label="Ubah aturan"
                        onClick={() => handleEdit(rule)}
                      >
                        <Edit2 size={14} />
                      </button>
                      {/* D-04 — satu-satunya jalan aktif/nonaktif (dialog konfirmasi di toggleActive). */}
                      <button
                        data-testid={`delete-rule-${rule.id}`}
                        className={`secondary-button text-[11px] ${rule.active !== false ? "!text-[#C0392B]" : ""}`}
                        onClick={() => toggleActive(rule)}
                      >
                        <Power size={12} /> {rule.active !== false ? "Nonaktifkan" : "Aktifkan"}
                      </button>
                    </div>
                  </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </section>
      )}
    </div>
  );
}
