/**
 * EntityDetailDrawer (FASE E-3) — lihat & UBAH badan usaha yang sudah jalan.
 *
 * Menutup cacat lama: badan usaha hanya bisa dibuat, tidak bisa dikoreksi — padahal
 * alamat dan kop surat sering berubah. Yang TIDAK boleh berubah (kode dokumen setelah
 * ada dokumen terbit) tetap dikunci, tetapi alasannya DIJELASKAN beserta dokumen
 * pertamanya, bukan hanya dinonaktifkan tanpa keterangan.
 *
 * KP-T1 (KP-01, KP-02, KP-23) — "Awal tahun fiskal" (tidak dibaca mesin) dibuang. Bagian baru: **Pajak** (status PKP +
 * tindakan "Ubah status PKP" bertanggal berlaku, beralasan, dengan pratinjau dampak; jadwal bisa dibatalkan),
 * **Tahun buku & mata uang** (nilai Pusat Pengaturan yang dipakai mesin + sumbernya; diubah lewat editor baku pada
 * lapisan PT), **Grup & konsolidasi** (PT induk + persen kepemilikan).
 *
 * KP-T2 — bagian "Kesiapan" memakai `EntityCompletionSteps` (16 butir bernomor, tombol Lengkapi yang mengganti PT
 * aktif lalu membuka layar tujuan, Ulangi penyiapan) — satu sumber tautan & teks dengan wizard dan tab Kesiapan.
 *
 * KP-T6 — Profil PT = satu sumber identitas kop surat: isian baru **Nama di kop surat** (kosong = nama legal),
 * **Slogan**, **Situs web** (dulu teks terpisah di perancang dokumen).
 */
import { useCallback, useEffect, useState } from "react";
import { X, Save, Loader2, Lock, History, ClipboardCheck,
  ShieldCheck, Building2, CalendarClock, Landmark, Network } from "lucide-react";

import ErrorNotice from "../../../components/ErrorNotice";
import LocationFields, { locationSummary } from "../../../components/LocationFields";
import { formatDateId } from "../../../components/KNDatePicker";
import { auditActionInfo } from "../../../config/auditLabels";
import { can } from "../../../config/roles";
import { askConfirm } from "../../../services/confirmService";
import { getEntity, patchEntity, getReadiness, getEntityAudit, errText, cancelTaxStatus, fiscalYearText,
  NPWP_MESSAGE, npwpValid, profileSettingItems, sourceText, TAX_STATUS_LABEL } from "./entityApi";
import TaxStatusDialog from "./TaxStatusDialog";
import ProfileSettingDialog from "./ProfileSettingDialog";
import EntityCompletionSteps from "./EntityCompletionSteps";

const EDITABLE = [
  ["legal_name", "Nama legal"],
  ["short_name", "Nama singkat"],
  ["print_name", "Nama di kop surat", "Kosongkan untuk memakai nama legal."],   // KP-T6
  ["owner_name", "Nama pemilik (perorangan)"],
  ["business_label", "Label usaha (perorangan)"],
  ["address", "Alamat"],
  ["phone", "Telepon"],
  ["email", "Email"],
  ["website", "Situs web"],                                                       // KP-T6
  ["tagline", "Slogan"],                                                          // KP-T6
  ["npwp", "NPWP"],
  ["logo_url", "URL logo (kop surat)"],
];
// UAT 24 Okt (audit UI tahap 2, G5-25) — isian perorangan dulu tampil juga untuk PT; tombol simpan di tengah kartu.
// Jenis perorangan sama dengan wizard buat (EntityWizard PERSONAL_TYPES). KP-T1 — "Awal tahun fiskal" dibuang.
const PERSONAL_TYPES = ["Perorangan", "UD"];
const PERSONAL_FIELDS = ["owner_name", "business_label"];
// Fase 4 · R6 (G5-25) — "Kota" dulu teks bebas karena PATCH badan usaha tidak menerima kode wilayah; kini server
// menerimanya (entity_lifecycle_service.LOCATION_FIELDS) sehingga form ubah memakai pemilih wilayah yang sama dengan
// wizard buat. Bila satu isian lokasi berubah, SEMUA isian lokasi dikirim (server menormalkan satu set utuh).
const LOC_KEYS = ["country", "country_code", "province", "province_code", "city", "city_code", "district",
  "district_code", "postal_code"];
const pickLoc = (o = {}) => Object.fromEntries(LOC_KEYS.map((k) => [k, o[k] || ""]));
const GROUP_KEYS = ["is_group", "ownership_pct"];   // KP-T1 — bagian Grup & konsolidasi (ikut tombol Simpan)
const FORM_KEYS = [...EDITABLE.map(([k]) => k), ...LOC_KEYS, ...GROUP_KEYS];
const OWNERSHIP_MESSAGE = "Persen kepemilikan harus lebih dari 0 dan paling banyak 100.";

/** Pelatihan 18 Nov (K03) — riwayat badan usaha butuh izin `audit.view`. Tanpa izin itu drawer dulu tetap memanggil
 * riwayat (403 di konsol) lalu menulis "Belum ada perubahan tercatat" — menyesatkan bagi Manajer. Sesi tanpa data izin
 * (komponen lama) = perilaku lama; server tetap menegakkan. */
export function izinAuditSesi() {
  let u = null;
  try { u = JSON.parse(localStorage.getItem("kn_user") || "null"); } catch { u = null; }
  if (!u || !u.permissions) return true;
  return can(u.permissions, "audit", "view");
}

function fmtTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("id-ID",
      { day: "2-digit", month: "short", year: "2-digit", hour: "2-digit", minute: "2-digit" });
  } catch { return "—"; }
}

export default function EntityDetailDrawer({ entityId, canManage, onClose, onChanged,
  onNavigate }) {
  const [entity, setEntity] = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [audit, setAudit] = useState([]);
  const [auditDenied, setAuditDenied] = useState(false);
  const [form, setForm] = useState({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [profile, setProfile] = useState(null);       // KP-T1 — entri registry tahun buku & mata uang (lapisan PT)
  const [taxOpen, setTaxOpen] = useState(false);
  const [profileEdit, setProfileEdit] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [e, r] = await Promise.all([getEntity(entityId), getReadiness(entityId)]);
      setEntity(e);
      setReadiness(r);
      setForm(Object.fromEntries(FORM_KEYS.map((k) => [k, k === "ownership_pct"
        ? String(e?.[k] ?? "") : (e?.[k] ?? "")])));
      setError("");
      // Riwayat audit boleh gagal (mis. peran tanpa izin audit) tanpa merusak layar.
      if (izinAuditSesi()) {
        getEntityAudit(entityId).then((rows) => { setAudit(rows); setAuditDenied(false); })
          .catch((err) => { setAudit([]); setAuditDenied(err?.response?.status === 403); });
      } else { setAudit([]); setAuditDenied(true); }
      // KP-T1 — tanpa akses baca pengaturan: nilai tetap tampil (dari jawaban PT), tombol Ubah disembunyikan.
      profileSettingItems(entityId).then(setProfile).catch(() => setProfile(null));
    } catch (e) {
      setError(errText(e, "Gagal memuat detail badan usaha."));
    } finally {
      setLoading(false);
    }
  }, [entityId]);

  useEffect(() => { load(); }, [load]);

  const prefixLocked = entity?.prefix_lock?.locked;
  const firstDoc = entity?.prefix_lock?.first_document;
  const canWrite = Boolean(canManage) && entity?.status === "active";
  const taxHistory = entity?.tax_status_history || [];
  const lastTax = taxHistory.length ? taxHistory[taxHistory.length - 1] : null;
  const pendingTax = entity?.tax_status_pending || null;

  const cancelPending = async () => {
    const ok = await askConfirm({
      title: "Batalkan jadwal status PKP?",
      message: `Perubahan menjadi ${TAX_STATUS_LABEL[pendingTax?.to] || ""} mulai ${formatDateId(pendingTax?.effective_date)} `
        + "dibatalkan. Status PKP sekarang tidak berubah.",
      confirmLabel: "Batalkan jadwal", danger: true, testId: "entity-detail-tax-cancel-confirm",
    });
    if (!ok) return;
    setBusy(true);
    setError("");
    try {
      await cancelTaxStatus(entityId);
      setSaved("Jadwal perubahan status PKP dibatalkan.");
      await load();
      onChanged?.("Jadwal perubahan status PKP dibatalkan.");
    } catch (e) {
      setError(errText(e, "Gagal membatalkan jadwal."));
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setBusy(true);
    setError("");
    setSaved("");
    try {
      const dirty = Object.fromEntries(
        Object.entries(form).filter(([k, v]) => String(entity?.[k] ?? "") !== String(v)));
      if (LOC_KEYS.some((k) => k in dirty)) Object.assign(dirty, pickLoc(form));
      if (!Object.keys(dirty).length) {
        setSaved("Tidak ada perubahan untuk disimpan.");
        return;
      }
      // KP-T1 — pola sama dengan server (pesan sama); persen kepemilikan dikirim sebagai angka.
      if ("npwp" in dirty && String(dirty.npwp).trim() && !npwpValid(dirty.npwp)) {
        setError(NPWP_MESSAGE);
        return;
      }
      if ("ownership_pct" in dirty) {
        const pct = Number(dirty.ownership_pct);
        if (String(dirty.ownership_pct).trim() === "" || !Number.isFinite(pct) || pct <= 0 || pct > 100) {
          setError(OWNERSHIP_MESSAGE);
          return;
        }
        dirty.ownership_pct = pct;
      }
      await patchEntity(entityId, dirty);
      setSaved("Perubahan tersimpan.");
      await load();
      onChanged?.(`Badan usaha “${form.legal_name || entity?.short_name}” diperbarui.`);
    } catch (e) {
      setError(errText(e, "Gagal menyimpan perubahan."));
    } finally {
      setBusy(false);
    }
  };

  const savePrefix = async (value) => {
    setBusy(true);
    setError("");
    try {
      await patchEntity(entityId, { doc_prefix: value.toUpperCase() });
      setSaved("Kode dokumen diperbarui — nomor berikutnya memakai kode baru.");
      await load();
      onChanged?.("Kode dokumen badan usaha diperbarui.");
    } catch (e) {
      setError(errText(e, "Gagal mengubah kode dokumen."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-overlay" data-testid="entity-detail-drawer"
         onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
      <div className="modal-card" style={{ maxWidth: 760, width: "95vw" }}>
        <div className="flex items-start gap-2 border-b border-[#EFF0F2] px-4 py-3">
          <Building2 size={16} className="mt-0.5 text-[#0058CC]" />
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-[13.5px] font-bold" data-testid="entity-detail-title">
              {entity?.legal_name || entity?.short_name || "Badan Usaha"}
            </h3>
            <p className="flex flex-wrap items-center gap-2 text-[11px] text-[#6B6B73]">
              <span data-testid="entity-detail-type">{entity?.type || "—"}</span>
              <span className="font-mono" data-testid="entity-detail-prefix">
                {entity?.doc_prefix}
              </span>
              {entity?.is_pkp ? (
                <span className="inline-flex items-center gap-1 text-[#1B7F4B]">
                  <ShieldCheck size={11} /> PKP
                </span>
              ) : <span>non-PKP</span>}
              {entity?.status !== "active" && (
                <span className="inline-flex items-center gap-1 rounded bg-[#FDF3E7] px-1.5 text-[10px] font-bold text-[#8C4A00]"
                      data-testid="entity-detail-archived">
                  <Lock size={9} /> Terarsip — tidak menerima transaksi baru
                </span>
              )}
            </p>
          </div>
          <button type="button" className="icon-button" aria-label="Tutup"
                  data-testid="entity-detail-close" onClick={onClose}>
            <X size={14} />
          </button>
        </div>

        <div className="space-y-3 p-4" style={{ maxHeight: "64vh", overflowY: "auto" }}>
          <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")}
                       testId="entity-detail-error" />
          {saved && (
            <div className="notice-bar success !py-1.5" data-testid="entity-detail-saved">
              <span className="text-[11.5px]">{saved}</span>
            </div>
          )}

          {loading ? (
            <div className="grid gap-2" data-testid="entity-detail-loading">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="h-9 animate-pulse rounded bg-[#F5F5F7]" />
              ))}
            </div>
          ) : (
            <>
              {/* Identitas & kontak */}
              <div className="section-card">
                <div className="section-body py-3">
                  <p className="kicker mb-2">Identitas & kontak</p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {EDITABLE.filter(([key]) => PERSONAL_TYPES.includes(entity?.type)
                      || !PERSONAL_FIELDS.includes(key)).map(([key, label, hint]) => (
                      <div key={key} className="grid gap-1">
                        <label className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">
                          {label}
                        </label>
                        <input
                          className="field"
                          data-testid={`entity-detail-${key}-input`}
                          disabled={!canManage || entity?.status !== "active"}
                          value={form[key] ?? ""}
                          placeholder={key === "print_name" ? (entity?.legal_name || "") : undefined}
                          onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                        />
                        {hint && <p className="text-fs-12 text-kn-text-2" data-testid={`entity-detail-${key}-hint`}>{hint}</p>}
                      </div>
                    ))}
                  </div>
                  <div className="mt-2 grid grid-cols-1 gap-1" data-testid="entity-detail-location">
                    <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">Lokasi</p>
                    {canManage && entity?.status === "active" ? (
                      <LocationFields testId="entity-detail-loc" compact required={false} labelStyle="caps" value={pickLoc(form)}
                        onChange={(patch) => setForm((f) => ({ ...f, ...patch }))} />
                    ) : (
                      <p className="text-[12px] text-[#1C1C1E]" data-testid="entity-detail-location-text">
                        {locationSummary(entity || {}) || "—"}
                      </p>
                    )}
                    {entity?.city && !entity?.city_code && !form.city_code && (
                      <p className="text-[10.5px] text-[#8C4A00]" data-testid="entity-detail-location-legacy">
                        Kota tersimpan “{entity.city}” masih teks lama (belum terverifikasi) — pilih provinsi &amp;
                        kota dari daftar untuk memverifikasinya.
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* KP-T1 — Pajak: status PKP yang dibaca mesin + tindakan bertanggal berlaku */}
              <div className="section-card" data-testid="entity-detail-tax">
                <div className="section-body py-3">
                  <div className="mb-2 flex items-center gap-2">
                    <ShieldCheck size={14} className="text-kn-action" />
                    <p className="kicker !mb-0">Pajak</p>
                  </div>
                  <p className="text-fs-13 text-kn-text" data-testid="entity-detail-tax-status">
                    Status: <b>{TAX_STATUS_LABEL[entity?.default_tax_mode] || "—"}</b>
                  </p>
                  <p className="text-fs-12 text-kn-text-2" data-testid="entity-detail-tax-since">
                    {lastTax ? `Berlaku sejak ${formatDateId(lastTax.effective_date)} — ${lastTax.reason}`
                      : "Sejak PT dibuat (belum pernah diubah)."}
                  </p>
                  {pendingTax && (
                    <p className="mt-1 flex flex-wrap items-center gap-2 rounded-md bg-kn-warning-soft px-2.5 py-1.5 text-fs-12 text-kn-warning-text"
                       data-testid="entity-detail-tax-pending">
                      <CalendarClock size={13} />
                      Akan menjadi {TAX_STATUS_LABEL[pendingTax.to] || pendingTax.to} mulai {formatDateId(pendingTax.effective_date)}
                      {canWrite && (
                        <button type="button" className="link-button" data-testid="entity-detail-tax-cancel"
                                disabled={busy} onClick={cancelPending}>
                          Batalkan jadwal
                        </button>
                      )}
                    </p>
                  )}
                  {canWrite && !pendingTax && (
                    <button type="button" className="secondary-button mt-2" data-testid="entity-detail-tax-change"
                            onClick={() => setTaxOpen(true)}>
                      Ubah status PKP
                    </button>
                  )}
                </div>
              </div>

              {/* KP-T1 — Tahun buku & mata uang: nilai Pusat Pengaturan yang dipakai mesin (lapisan PT) */}
              <div className="section-card" data-testid="entity-detail-profile">
                <div className="section-body py-3">
                  <div className="mb-2 flex items-center gap-2">
                    <Landmark size={14} className="text-kn-action" />
                    <p className="kicker !mb-0">Tahun buku &amp; mata uang</p>
                  </div>
                  {[
                    { id: "fiscal", item: profile?.fiscalYear,
                      text: `Tahun buku: ${fiscalYearText(entity?.fiscal_year_end_month)}`,
                      source: entity?.fiscal_year_end_month_source },
                    { id: "currency", item: profile?.currency,
                      text: `Mata uang pembukuan: ${(profile?.currency?.options || []).find(
                        (o) => o.value === entity?.base_currency)?.label || entity?.base_currency || "—"}`,
                      source: entity?.base_currency_source },
                  ].map((row) => (
                    <div key={row.id} className="flex flex-wrap items-center gap-2 border-b border-kn-divider py-1.5 last:border-0"
                         data-testid={`entity-detail-profile-${row.id}`}>
                      <span className="text-fs-13 text-kn-text">{row.text}</span>
                      <span className="text-fs-12 text-kn-text-2">({sourceText(row.source)})</span>
                      {canWrite && row.item?.can_edit && (
                        <button type="button" className="link-button ml-auto" data-testid={`entity-detail-profile-${row.id}-edit`}
                                onClick={() => setProfileEdit(row.item)}>
                          Ubah
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* KP-T1 — Grup & konsolidasi (K-10) */}
              <div className="section-card" data-testid="entity-detail-group">
                <div className="section-body py-3">
                  <div className="mb-2 flex items-center gap-2">
                    <Network size={14} className="text-kn-action" />
                    <p className="kicker !mb-0">Grup &amp; konsolidasi</p>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <div className="grid gap-1">
                      <label className="flex items-center gap-2 text-fs-13 text-kn-text">
                        <input type="checkbox" data-testid="entity-detail-is_group-input" disabled={!canWrite}
                               checked={Boolean(form.is_group)}
                               onChange={(e) => setForm((f) => ({ ...f, is_group: e.target.checked }))} />
                        PT induk (konsolidasi)
                      </label>
                      <p className="text-fs-12 text-kn-text-2">
                        PT induk tidak ikut dijumlahkan sebagai baris di laporan konsolidasi dan tidak muncul di
                        pilihan PT pada tutup buku.
                      </p>
                    </div>
                    <div className="grid gap-1">
                      <label className="kicker">Persen kepemilikan (%)</label>
                      <input className="field" type="number" min="0.01" max="100" step="0.01"
                             data-testid="entity-detail-ownership_pct-input"
                             disabled={!canWrite || Boolean(form.is_group)}
                             value={form.ownership_pct ?? ""}
                             onChange={(e) => setForm((f) => ({ ...f, ownership_pct: e.target.value }))} />
                      <p className="text-fs-12 text-kn-text-2">
                        Dipakai Konsolidasi Grup: bagian non-pengendali = laba dan ekuitas PT ini × (100 % − persen ini).
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Penomoran + kunci prefix */}
              <div className="section-card">
                <div className="section-body py-3">
                  <p className="kicker mb-2">Penomoran dokumen</p>
                  {prefixLocked ? (
                    <div className="flex items-start gap-1.5 rounded-md border border-[#F0C88A] bg-[#FEF7EC] p-2.5"
                         data-testid="entity-detail-prefix-locked">
                      <Lock size={13} className="mt-0.5 shrink-0 text-[#8C4A00]" />
                      <div>
                        <p className="text-[11.5px] font-bold text-[#1C1C1E]">
                          Kode dokumen <span className="font-mono">{entity?.doc_prefix}</span> terkunci
                        </p>
                        <p className="text-[11px] text-[#3C3C43]">
                          {entity?.prefix_lock?.reason}
                        </p>
                        {firstDoc && (
                          <p className="mt-1 text-[10.5px] text-[#6B6B73]"
                             data-testid="entity-detail-first-doc">
                            Dokumen pertama: <b>{firstDoc.number}</b> ({firstDoc.label})
                            {firstDoc.created_at ? ` · ${fmtTime(firstDoc.created_at)}` : ""}
                          </p>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-wrap items-end gap-2"
                         data-testid="entity-detail-prefix-editable">
                      <div className="grid gap-1">
                        <label className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">
                          Kode dokumen (masih bisa diubah — belum ada dokumen terbit)
                        </label>
                        <input className="field font-mono" defaultValue={entity?.doc_prefix}
                               data-testid="entity-detail-prefix-input"
                               id={`prefix-${entityId}`} />
                      </div>
                      {canManage && (
                        <button type="button" className="secondary-button"
                                data-testid="entity-detail-prefix-save"
                                disabled={busy}
                                onClick={() => savePrefix(
                                  document.getElementById(`prefix-${entityId}`)?.value || "")}>
                          Simpan kode
                        </button>
                      )}
                    </div>
                  )}
                  {/* G5-25 — dulu "Contoh nomor berikutnya: KSC/SO-00001" padahal sudah KSC/SO-00505 (bukan penghitung nyata). */}
                  <p className="mt-2 text-[10.5px] text-[#6B6B73]">
                    Format nomor dokumen:{" "}
                    <b className="font-mono">{entity?.doc_prefix}/SO-nnnnn</b> (nomor urut per jenis dokumen)
                  </p>
                </div>
              </div>

              {/* Kesiapan — KP-T2: satu komponen dengan langkah "Lengkapi PT" wizard dan tab Kesiapan */}
              <div className="section-card">
                <div className="section-body py-3">
                  <div className="mb-2 flex items-center gap-2">
                    <ClipboardCheck size={14} className="text-kn-special-text" />
                    <p className="kicker !mb-0">Kesiapan</p>
                    <span className="ml-auto text-fs-12 font-bold tabular-nums text-kn-text"
                          data-testid="entity-detail-readiness-percent">
                      {readiness?.percent ?? 0}% ({readiness?.ready ?? 0}/{readiness?.total ?? 0})
                    </span>
                  </div>
                  <EntityCompletionSteps entityId={entityId} data={readiness} canRetry={canWrite}
                    onUpdated={(r) => { if (r) setReadiness(r); else load(); }}
                    testId="entity-detail-completion" />
                </div>
              </div>

              {/* Riwayat perubahan */}
              <div className="section-card">
                <div className="section-body py-3">
                  <div className="mb-2 flex items-center gap-2">
                    <History size={14} className="text-[#0058CC]" />
                    <p className="kicker !mb-0">Riwayat perubahan</p>
                  </div>
                  {auditDenied ? (
                    <p className="text-fs-12 text-kn-text-2" data-testid="entity-detail-audit-denied">
                      Riwayat perubahan hanya bisa dibaca pemegang akses Riwayat Audit.
                    </p>
                  ) : audit.length === 0 ? (
                    <p className="text-[11px] text-[#8E8E93]" data-testid="entity-detail-audit-empty">
                      Belum ada perubahan tercatat untuk badan usaha ini.
                    </p>
                  ) : (
                    <div className="grid gap-1" data-testid="entity-detail-audit">
                      {audit.slice(0, 12).map((a) => (
                        <p key={a.id} className="flex flex-wrap gap-2 border-b border-[#F5F5F7] py-1 text-[11px] last:border-0">
                          <span className="font-semibold text-[#1C1C1E]" title={a.action}>{auditActionInfo(a.action).label}</span>
                          <span className="text-[#6B6B73]">oleh {a.actor}</span>
                          <span className="ml-auto text-[10px] text-[#9A9BA3] tabular-nums">
                            {fmtTime(a.timestamp)}
                          </span>
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
        {taxOpen && entity && (
          <TaxStatusDialog entity={entity} onClose={() => setTaxOpen(false)}
            onSaved={async (res) => {
              setTaxOpen(false);
              const msg = res?.tax_status_pending
                ? "Perubahan status PKP dijadwalkan." : "Status PKP diperbarui.";
              setSaved(msg);
              await load();
              onChanged?.(msg);
            }} />
        )}
        {profileEdit && (
          <ProfileSettingDialog entityId={entityId} entityName={entity?.legal_name || entity?.short_name}
            item={profileEdit} onClose={() => setProfileEdit(null)}
            onSaved={async () => {
              setProfileEdit(null);
              setSaved("Pengaturan PT diperbarui.");
              await load();
              onChanged?.("Pengaturan PT diperbarui.");
            }} />
        )}
        {!loading && canManage && entity?.status === "active" && (
          <div className="flex justify-end gap-2 border-t border-[#EFF0F2] px-4 py-3">
            <button type="button" className="secondary-button" data-testid="entity-detail-cancel" onClick={onClose}>Tutup</button>
            <button type="button" className="primary-button"
                    data-testid="entity-detail-save"
                    disabled={busy} onClick={save}>
              {busy ? <Loader2 size={13} className="animate-spin" />
                    : <Save size={13} />} Simpan Perubahan
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
