/**
 * entityApi.js — lapisan API untuk layar "Badan Usaha & Akses" (FASE E-3).
 *
 * Satu berkas supaya komponen tidak menyebar URL. Semua pesan galat dikembalikan
 * apa adanya dari server (server sudah berbahasa Indonesia & menuntun), sehingga
 * layar tidak perlu mengarang kalimat sendiri.
 */
import axios, { API } from "../../../services/apiClient";
// FASE E-8 (E8.1) — pilihan peran & daftar peran lintas-entitas TIDAK lagi ditulis
// di sini. Sumber tunggal: `config/roles.js` (cermin `backend/role_registry.py`),
// supaya peran baru muncul otomatis di formulir akun tanpa menyunting layar.
import { ROLE_OPTIONS as REG_ROLE_OPTIONS, CROSS_ENTITY_ROLES as REG_CROSS_ROLES }
  from "../../../config/roles";

/** Ubah galat axios menjadi kalimat manusia (mendukung detail berbentuk objek). */
export function errText(err, fallback = "Terjadi kesalahan.") {
  const d = err?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (d && typeof d === "object") {
    const parts = [d.message || "", ...(d.blockers || []), d.hint || ""].filter(Boolean);
    if (parts.length) return parts.join(" · ");
  }
  return err?.response?.data?.detail ? String(err.response.data.detail) : (err?.message || fallback);
}

/** Penghalang terstruktur (dipakai dialog arsip agar bisa ditampilkan sebagai daftar). */
export function errBlockers(err) {
  const d = err?.response?.data?.detail;
  if (d && typeof d === "object" && Array.isArray(d.blockers)) return d.blockers;
  return [];
}

// ─── Badan usaha ───────────────────────────────────────────────
export const listEntities = (params = {}) =>
  axios.get(`${API}/entities`, { params }).then((r) => r.data || []);

export const countEntities = (params = {}) =>
  axios.get(`${API}/entities/count`, { params }).then((r) => r.data?.count || 0);

export const getEntity = (id) =>
  axios.get(`${API}/entities/${id}`).then((r) => r.data || null);

export const createEntity = (body) =>
  axios.post(`${API}/entities`, body).then((r) => r.data);

export const patchEntity = (id, data) =>
  axios.patch(`${API}/entities/${id}`, { data }).then((r) => r.data);

export const getReadiness = (id) =>
  axios.get(`${API}/entities/${id}/readiness`).then((r) => r.data);

// KP-T2 — ulangi langkah penyiapan PT (bagan akun, penanda lapisan, pemasok antar-PT); jawaban memuat kesiapan baru.
export const retryProvisioning = (id) =>
  axios.post(`${API}/entities/${id}/provisioning/retry`).then((r) => r.data);

export const getDeactivationImpact = (id) =>
  axios.get(`${API}/entities/${id}/deactivation-impact`).then((r) => r.data);

export const archiveEntity = (id, { reason = "", force = false } = {}) =>
  axios.post(`${API}/entities/${id}/archive`, { reason, force }).then((r) => r.data);

export const reactivateEntity = (id) =>
  axios.post(`${API}/entities/${id}/reactivate`).then((r) => r.data);

export const getEntityAudit = (id) =>
  axios.get(`${API}/entities/${id}/audit`).then((r) => r.data || []);

// ─── KP-T1 — status PKP bertanggal + profil PT dari Pusat Pengaturan ─────────────────────────────────
export const taxStatusPreview = (id, { to, effectiveDate, npwp = "" }) =>
  axios.get(`${API}/entities/${id}/tax-status/preview`,
    { params: { to, effective_date: effectiveDate, ...(npwp ? { npwp } : {}) } }).then((r) => r.data);

export const changeTaxStatus = (id, body) =>
  axios.post(`${API}/entities/${id}/tax-status`, body).then((r) => r.data);

export const cancelTaxStatus = (id) =>
  axios.delete(`${API}/entities/${id}/tax-status/pending`).then((r) => r.data);

/** Kunci registry yang menjadi sumber tunggal tahun buku & mata uang PT (lapisan PT). */
export const PROFILE_KEYS = { currency: "finance.base_currency", fiscalYear: "finance.fiscal_year_end_month" };

/** Entri + nilai efektif dua kunci profil PT ({currency, fiscalYear}); tanpa `entityId` = nilai grup.
 *  Gagal (mis. 403 tanpa akses baca pengaturan) → dilempar; layar memutuskan tampil hanya-baca. */
export const profileSettingItems = (entityId = "") =>
  axios.get(`${API}/config/effective`, { params: { group: "keuangan-dasar", ...(entityId ? { entity_id: entityId } : {}) } })
    .then((r) => {
      const items = r.data?.items || [];
      const pick = (k) => items.find((i) => i.key === k) || null;
      return { currency: pick(PROFILE_KEYS.currency), fiscalYear: pick(PROFILE_KEYS.fiscalYear) };
    });

/** Simpan satu kunci profil PT pada lapisan PT (jalur baku Pusat Pengaturan). */
export const saveProfileSetting = (entityId, key, value, reason = "") =>
  axios.put(`${API}/config/values`, { items: [{ key, value, scope_type: "entity", scope_id: entityId, reason }] })
    .then((r) => r.data);

export const BULAN_ID = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September",
  "Oktober", "November", "Desember"];

/** "Januari–Desember" untuk bulan akhir 12; "April–Maret" untuk bulan akhir 3. */
export function fiscalYearText(endMonth) {
  const end = Number(endMonth) || 12;
  return `${BULAN_ID[end % 12]}–${BULAN_ID[end - 1]}`;
}

/** Sumber nilai pengaturan dalam bahasa sehari-hari. */
export const sourceText = (layer) => (["entity", "legacy_entity"].includes(layer)
  ? "khusus PT ini" : "mengikuti pengaturan grup");

export const NPWP_MESSAGE = "NPWP harus 15 atau 16 digit angka. Periksa kembali nomor yang diketik.";

/** Sama dengan server (`entity_lifecycle_service.npwp_valid`): 15/16 digit setelah titik, strip, spasi dibuang. */
export const npwpValid = (v) => /^(\d{15}|\d{16})$/.test(String(v || "").trim().replace(/[.\-\s]/g, ""));

export const TAX_STATUS_LABEL = { ppn: "PKP (memungut PPN)", non_ppn: "Non-PKP (tanpa PPN)" };

// ─── Akun ────────────────────────────────────────────────────
export const listUsers = (params = {}) =>
  axios.get(`${API}/users`, { params }).then((r) => r.data);

export const createUser = (body) =>
  axios.post(`${API}/users`, body).then((r) => r.data);

export const patchUser = (id, data) =>
  axios.patch(`${API}/users/${id}`, { data }).then((r) => r.data);

export const deactivateUser = (id) =>
  axios.delete(`${API}/users/${id}`).then((r) => r.data);

export const reactivateUser = (id) =>
  axios.post(`${API}/users/${id}/reactivate`).then((r) => r.data);

export const resetUserPassword = (id, newPassword) =>
  axios.post(`${API}/users/${id}/reset-password`, { new_password: newPassword })
    .then((r) => r.data);

export const revokeUserSessions = (id) =>
  axios.post(`${API}/users/${id}/revoke-sessions`).then((r) => r.data);

export const availableEmployees = (params = {}) =>
  axios.get(`${API}/hr-employees-available`, { params }).then((r) => r.data || []);

// ─── Cek Kenyataan Peran (utang migrasi (ii) E-8) ───────────────────
// Laporan dihitung ulang di server setiap kali dibuka: peran usulan HARUS lahir
// dari jejak terbaru, bukan dari angka yang pernah disimpan.
export const roleReality = (params = {}) =>
  axios.get(`${API}/access/role-reality`, { params }).then((r) => r.data || {});

export const applyRoleReality = (id, role, note = "") =>
  axios.post(`${API}/access/role-reality/${id}/apply`, { role, note })
    .then((r) => r.data);

// ─── Enum jenis badan usaha (E1.1) ─────────────────────────────────
export const entityTypes = () =>
  axios.get(`${API}/enums/entity_type`).then((r) => r.data?.values || [])
    .catch(() => axios.get(`${API}/enums`)
      .then((r) => r.data?.enums?.entity_type?.values || []));

export const ROLE_OPTIONS = REG_ROLE_OPTIONS;

export const CROSS_ROLES = REG_CROSS_ROLES;

// ─── Peran & Hak Akses (peran kustom, 3 tingkat per modul) ──────────────────
export const accessModules = () =>
  axios.get(`${API}/access/modules`).then((r) => r.data || { modules: [], levels: {} });

export const accessRoles = () =>
  axios.get(`${API}/access/roles`).then((r) => r.data?.roles || []);

// PR-T1 — daftar peran + bolehkah pelaku mengubah "Boleh mengelola akun dengan peran".
export const accessRolesFull = () =>
  axios.get(`${API}/access/roles`).then((r) => ({ roles: r.data?.roles || [], canEditAssignable: Boolean(r.data?.can_edit_assignable) }));

// PR-T1 — peran yang boleh diberikan pelaku saat membuat/mengubah akun ({all, roles}).
export const manageableRoles = () =>
  axios.get(`${API}/users/manageable-roles`).then((r) => r.data || { all: false, roles: [] });

export const accessRole = (id) =>
  axios.get(`${API}/access/roles/${id}`).then((r) => r.data);

export const createAccessRole = (body) =>
  axios.post(`${API}/access/roles`, body).then((r) => r.data);

export const patchAccessRole = (id, body) =>
  axios.patch(`${API}/access/roles/${id}`, body).then((r) => r.data);

// PR-T9 — peran kustom mengikuti izin baru peran dasarnya ([] = semua yang tertunda).
export const followBaseAccessRole = (id, resources = []) =>
  axios.post(`${API}/access/roles/${id}/follow-base`, resources.length ? { resources } : {}).then((r) => r.data);

export const resetAccessRole = (id) =>
  axios.post(`${API}/access/roles/${id}/reset`).then((r) => r.data);

export const deleteAccessRole = (id) =>
  axios.delete(`${API}/access/roles/${id}`).then((r) => r.data);

export const previewAccessRole = (body) =>
  axios.post(`${API}/access/roles/preview`, body).then((r) => r.data);

export const moveAccessRoleUsers = (id, toRole) =>
  axios.post(`${API}/access/roles/${id}/move-users`, { to_role: toRole }).then((r) => r.data);

export const publicRoles = () =>
  axios.get(`${API}/roles`).then((r) => r.data?.roles || []);
