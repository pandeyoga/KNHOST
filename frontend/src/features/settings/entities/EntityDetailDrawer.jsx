/**
 * EntityDetailDrawer (FASE E-3) — lihat & UBAH badan usaha yang sudah jalan.
 *
 * Menutup cacat lama: badan usaha hanya bisa dibuat, tidak bisa dikoreksi — padahal
 * alamat dan kop surat sering berubah. Yang TIDAK boleh berubah (kode dokumen setelah
 * ada dokumen terbit) tetap dikunci, tetapi alasannya DIJELASKAN beserta dokumen
 * pertamanya, bukan hanya dinonaktifkan tanpa keterangan.
 */
import { useCallback, useEffect, useState } from "react";
import { X, Save, Loader2, Lock, History, ClipboardCheck, ExternalLink,
  ShieldCheck, Building2 } from "lucide-react";

import ErrorNotice from "../../../components/ErrorNotice";
import KNSelect from "../../../components/KNSelect";
import LocationFields, { locationSummary } from "../../../components/LocationFields";
import { auditActionInfo } from "../../../config/auditLabels";
import { getEntity, patchEntity, getReadiness, getEntityAudit, errText } from "./entityApi";

const EDITABLE = [
  ["legal_name", "Nama legal"],
  ["short_name", "Nama singkat"],
  ["owner_name", "Nama pemilik (perorangan)"],
  ["business_label", "Label usaha (perorangan)"],
  ["address", "Alamat"],
  ["phone", "Telepon"],
  ["email", "Email"],
  ["npwp", "NPWP"],
  ["logo_url", "URL logo (kop surat)"],
  ["fiscal_year_start", "Awal tahun fiskal"],
];
// UAT 24 Okt (audit UI tahap 2, G5-25) — isian perorangan dulu tampil juga untuk PT; awal tahun fiskal teks bebas
// "MM-DD"; tombol simpan di tengah kartu. Jenis perorangan sama dengan wizard buat (EntityWizard PERSONAL_TYPES).
const PERSONAL_TYPES = ["Perorangan", "UD"];
const PERSONAL_FIELDS = ["owner_name", "business_label"];
// Fase 4 · R6 (G5-25) — "Kota" dulu teks bebas karena PATCH badan usaha tidak menerima kode wilayah; kini server
// menerimanya (entity_lifecycle_service.LOCATION_FIELDS) sehingga form ubah memakai pemilih wilayah yang sama dengan
// wizard buat. Bila satu isian lokasi berubah, SEMUA isian lokasi dikirim (server menormalkan satu set utuh).
const LOC_KEYS = ["country", "country_code", "province", "province_code", "city", "city_code", "district",
  "district_code", "postal_code"];
const pickLoc = (o = {}) => Object.fromEntries(LOC_KEYS.map((k) => [k, o[k] || ""]));
const FORM_KEYS = [...EDITABLE.map(([k]) => k), ...LOC_KEYS];
const BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
  "November", "Desember"];
const pad2 = (n) => String(n).padStart(2, "0");

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
  const [form, setForm] = useState({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [e, r] = await Promise.all([getEntity(entityId), getReadiness(entityId)]);
      setEntity(e);
      setReadiness(r);
      setForm(Object.fromEntries(FORM_KEYS.map((k) => [k, e?.[k] ?? ""])));
      setError("");
      // Riwayat audit boleh gagal (mis. peran tanpa izin audit) tanpa merusak layar.
      getEntityAudit(entityId).then(setAudit).catch(() => setAudit([]));
    } catch (e) {
      setError(errText(e, "Gagal memuat detail badan usaha."));
    } finally {
      setLoading(false);
    }
  }, [entityId]);

  useEffect(() => { load(); }, [load]);

  const prefixLocked = entity?.prefix_lock?.locked;
  const firstDoc = entity?.prefix_lock?.first_document;

  const save = async () => {
    setBusy(true);
    setError("");
    setSaved("");
    try {
      const dirty = Object.fromEntries(
        Object.entries(form).filter(([k, v]) => (entity?.[k] ?? "") !== v));
      if (LOC_KEYS.some((k) => k in dirty)) Object.assign(dirty, pickLoc(form));
      if (!Object.keys(dirty).length) {
        setSaved("Tidak ada perubahan untuk disimpan.");
        return;
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
                    {EDITABLE.filter(([key]) => key !== "fiscal_year_start"
                      && (PERSONAL_TYPES.includes(entity?.type) || !PERSONAL_FIELDS.includes(key))).map(([key, label]) => (
                      <div key={key} className="grid gap-1">
                        <label className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">
                          {label}
                        </label>
                        <input
                          className="field"
                          data-testid={`entity-detail-${key}-input`}
                          disabled={!canManage || entity?.status !== "active"}
                          value={form[key] ?? ""}
                          onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                        />
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
                  {(() => {
                    const [mm, dd] = String(form.fiscal_year_start || "01-01").split("-");
                    const off = !canManage || entity?.status !== "active";
                    const setFy = (m, d) => setForm((f) => ({ ...f, fiscal_year_start: `${pad2(m)}-${pad2(d)}` }));
                    return (
                      <div className="mt-2 grid gap-1" data-testid="entity-detail-fiscal_year_start-input">
                        <label className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">Awal tahun fiskal</label>
                        <div className="flex gap-2">
                          <div className="w-24"><KNSelect className="field" disabled={off} value={String(Number(dd) || 1)}
                            onValueChange={(v) => setFy(Number(mm) || 1, v)} testId="entity-detail-fy-day"
                            options={Array.from({ length: 31 }, (_, i) => ({ value: String(i + 1), label: String(i + 1) }))} /></div>
                          <div className="w-40"><KNSelect className="field" disabled={off} value={String(Number(mm) || 1)}
                            onValueChange={(v) => setFy(v, Number(dd) || 1)} testId="entity-detail-fy-month"
                            options={BULAN.map((b, i) => ({ value: String(i + 1), label: b }))} /></div>
                        </div>
                      </div>
                    );
                  })()}
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

              {/* Kesiapan singkat */}
              <div className="section-card">
                <div className="section-body py-3">
                  <div className="mb-2 flex items-center gap-2">
                    <ClipboardCheck size={14} className="text-[#6B219A]" />
                    <p className="kicker !mb-0">Kesiapan</p>
                    <span className="ml-auto text-[11px] font-bold tabular-nums"
                          data-testid="entity-detail-readiness-percent">
                      {readiness?.percent ?? 0}% ({readiness?.ready ?? 0}/{readiness?.total ?? 0})
                    </span>
                  </div>
                  <div className="grid gap-1.5">
                    {(readiness?.items || []).map((it) => (
                      <div key={it.key}
                           data-testid={`entity-detail-readiness-${it.key}`}
                           className="flex flex-wrap items-center gap-2 rounded-md border border-[#EFF0F2] px-2.5 py-1.5">
                        <span className={`h-2 w-2 shrink-0 rounded-full ${
                          it.ready ? "bg-[#1B7F4B]" : "bg-[#C0392B]"}`} />
                        <span className="text-[11.5px] font-semibold text-[#1C1C1E]">{it.label}</span>
                        <span className="text-[10.5px] text-[#6B6B73]">{it.detail}</span>
                        {!it.ready && it.view && onNavigate && (
                          <button type="button"
                                  data-testid={`entity-detail-goto-${it.key}`}
                                  className="ml-auto inline-flex items-center gap-1 text-[10.5px] font-bold text-[#0058CC] hover:underline"
                                  onClick={() => onNavigate(it.view)}>
                            Lengkapi <ExternalLink size={10} />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Riwayat perubahan */}
              <div className="section-card">
                <div className="section-body py-3">
                  <div className="mb-2 flex items-center gap-2">
                    <History size={14} className="text-[#0058CC]" />
                    <p className="kicker !mb-0">Riwayat perubahan</p>
                  </div>
                  {audit.length === 0 ? (
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
