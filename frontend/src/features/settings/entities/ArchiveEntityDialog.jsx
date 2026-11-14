/**
 * ArchiveEntityDialog (FASE E-3 / E1.6) — arsipkan badan usaha dengan MATA TERBUKA.
 *
 * Prinsipnya: jangan pernah menutup badan usaha lalu membuat pengguna bertanya-tanya
 * kenapa layarnya kosong. Dialog ini memuat PRATINJAU DAMPAK dari server dulu
 * (pengguna aktif, dokumen terbuka, saldo hidup, periode belum tutup); tombol
 * “Arsipkan” baru aktif kalau bersih. Bila memang harus dipaksa, alasan WAJIB dan
 * hanya admin yang boleh — sama seperti aturan servernya, jadi tidak ada kejutan.
 *
 * KP-T2 (KP-22) — daftar centang **Sebelum mengarsipkan** = `checks` server (pengguna, dokumen, saldo, karyawan,
 * periode) — persis yang diperiksa saat arsip. Baris yang belum beres menyebut jumlah dan contohnya (dokumen per jenis
 * + tiga nomor; saldo per jenis dalam rupiah berpemisah ribuan).
 */
import { useEffect, useState } from "react";
import { AlertTriangle, Archive, Loader2, X, Users, FileText, Wallet, CalendarClock, CheckCircle2, XCircle,
  UserCheck } from "lucide-react";

import { getDeactivationImpact, archiveEntity, errText, errBlockers } from "./entityApi";
import { formatCurrency } from "../../../utils/formatters";

const ICONS = { pengguna: Users, dokumen: FileText, saldo: Wallet, karyawan: UserCheck, periode: CalendarClock };

/** KP-T2 — rincian baris yang belum beres dari data terstruktur (jumlah + contoh; nominal berpemisah ribuan). */
function CheckDetail({ check, impact }) {
  if (check.ok) return <p className="text-fs-12 text-kn-text-2">{check.detail}</p>;
  if (check.key === "dokumen" && (impact?.open_documents || []).length) {
    return (
      <ul className="grid gap-0.5 text-fs-12 text-kn-text" data-testid="entity-archive-check-docs">
        {impact.open_documents.map((d) => (
          <li key={d.collection}>
            {d.label}: <b className="tabular-nums">{d.count}</b>
            {(d.examples || []).length > 0 && <span className="text-kn-text-2"> — mis. {d.examples.join(", ")}</span>}
          </li>
        ))}
      </ul>
    );
  }
  if (check.key === "saldo" && (impact?.balances || []).length) {
    return (
      <ul className="grid gap-0.5 text-fs-12 text-kn-text" data-testid="entity-archive-check-balances">
        {impact.balances.map((b) => (
          <li key={b.key} className="flex justify-between gap-2" data-testid={`entity-archive-balance-${b.key}`}>
            <span>{b.label}</span>
            <b className="tabular-nums">{b.unit ? `${b.amount.toLocaleString("id-ID")} ${b.unit}` : formatCurrency(b.amount)}</b>
          </li>
        ))}
      </ul>
    );
  }
  return <p className="text-fs-12 text-kn-text">{check.detail}</p>;
}

export default function ArchiveEntityDialog({ entity, onClose, onDone }) {
  const [impact, setImpact] = useState(null);
  const [loading, setLoading] = useState(true);
  const [reason, setReason] = useState("");
  const [force, setForce] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [blockers, setBlockers] = useState([]);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const d = await getDeactivationImpact(entity.id);
        if (alive) setImpact(d);
      } catch (e) {
        if (alive) setError(errText(e, "Gagal memuat pratinjau dampak."));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [entity.id]);

  const submit = async () => {
    setBusy(true);
    setError("");
    setBlockers([]);
    try {
      const res = await archiveEntity(entity.id, { reason, force });
      onDone?.(
        `“${entity.legal_name || entity.short_name}” diarsipkan. ` +
        `${res.sessions_revoked || 0} sesi pengguna dicabut — badan usaha ini tidak bisa ` +
        "lagi menerima transaksi baru, tetapi datanya tetap bisa dibaca."
      );
    } catch (e) {
      setError(errText(e, "Gagal mengarsipkan badan usaha."));
      setBlockers(errBlockers(e));
    } finally {
      setBusy(false);
    }
  };

  const clean = impact?.can_archive;

  return (
    <div className="modal-overlay" data-testid="entity-archive-dialog"
         onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
      <div className="modal-card" style={{ maxWidth: 640, width: "94vw" }}>
        <div className="flex items-start gap-2 border-b border-[#EFF0F2] px-4 py-3">
          <Archive size={16} className="mt-0.5 text-[#8C4A00]" />
          <div className="min-w-0 flex-1">
            <h3 className="text-[13.5px] font-bold">
              Arsipkan “{entity.legal_name || entity.short_name}”?
            </h3>
            <p className="text-[11px] text-[#6B6B73]">
              Badan usaha yang diarsipkan <b>tidak bisa lagi menerima transaksi baru</b>.
              Data lamanya tetap tersimpan dan bisa dibaca, jadi ini bukan penghapusan.
            </p>
          </div>
          <button type="button" className="icon-button" aria-label="Tutup"
                  data-testid="entity-archive-close" onClick={onClose}>
            <X size={14} />
          </button>
        </div>

        <div className="space-y-3 p-4">
          {loading ? (
            <div className="grid gap-2" data-testid="entity-archive-loading">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-9 animate-pulse rounded bg-[#F5F5F7]" />
              ))}
            </div>
          ) : (
            <>
              <div
                data-testid="entity-archive-verdict"
                className={`rounded-md border px-3 py-2 ${
                  clean ? "border-[#BFE3CC] bg-[#EEF9F1]" : "border-[#F0C88A] bg-[#FEF7EC]"
                }`}
              >
                <p className="flex items-center gap-1.5 text-[11.5px] font-bold text-[#1C1C1E]">
                  {clean ? "Aman diarsipkan — tidak ada yang tertinggal."
                         : "Belum bisa diarsipkan — masih ada yang belum beres (lihat daftar di bawah)."}
                </p>
              </div>

              {/* KP-T2 — daftar centang yang sama dengan pemeriksaan server */}
              <div className="rounded-md border border-kn-divider p-2.5" data-testid="entity-archive-checks">
                <p className="kicker mb-1.5">Sebelum mengarsipkan</p>
                <ul className="grid gap-1.5">
                  {(impact?.checks || []).map((c) => {
                    const Icon = ICONS[c.key] || AlertTriangle;
                    return (
                      <li key={c.key} className="flex items-start gap-2" data-testid={`entity-archive-check-${c.key}`}
                          data-ok={c.ok ? "ya" : "tidak"}>
                        {c.ok
                          ? <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-kn-success-text" aria-label="Beres" />
                          : <XCircle size={14} className="mt-0.5 shrink-0 text-kn-danger-text" aria-label="Belum beres" />}
                        <div className="min-w-0 flex-1">
                          <p className="flex items-center gap-1.5 text-fs-13 font-bold text-kn-text">
                            <Icon size={12} className="shrink-0 text-kn-text-2" /> {c.label}
                          </p>
                          <CheckDetail check={c} impact={impact} />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </div>

              <div className="grid gap-2 sm:grid-cols-2">
                <div className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2.5"
                     data-testid="entity-archive-users">
                  <p className="kicker">Pengguna aktif</p>
                  <p className="text-[15px] font-bold tabular-nums">
                    {(impact?.active_users || []).length}
                  </p>
                  <p className="text-[10px] text-[#6B6B73]">
                    {(impact?.home_users || []).length} di antaranya berbadan-usaha utama di sini
                    {(impact?.home_users || []).length > 0
                      ? " — sesinya akan dicabut dan mereka tidak bisa masuk lagi"
                      : ""}
                  </p>
                </div>
                <div className="rounded-md border border-kn-divider bg-kn-neutral-soft p-2.5"
                     data-testid="entity-archive-employees">
                  <p className="kicker">Karyawan terdaftar</p>
                  <p className="text-fs-16 font-bold tabular-nums">{impact?.employees ?? 0}</p>
                  <p className="text-fs-12 text-kn-text-2">Karyawan yang belum berhenti di PT ini (data SDM)</p>
                </div>
              </div>

              {impact?.first_document && (
                <p className="text-[10.5px] text-[#6B6B73]" data-testid="entity-archive-first-doc">
                  Badan usaha ini sudah menerbitkan dokumen — yang pertama:{" "}
                  <b>{impact.first_document.number}</b> ({impact.first_document.label}).
                  Karena itu kode dokumennya tidak bisa diubah lagi.
                </p>
              )}

              {!clean && (
                <div className="rounded-md border border-[#F0B5AE] bg-[#FCEBEA] p-2.5">
                  <label className="flex items-start gap-2 text-[11.5px] font-semibold text-[#A8221A]">
                    <input
                      type="checkbox"
                      data-testid="entity-archive-force"
                      checked={force}
                      onChange={(e) => setForce(e.target.checked)}
                      className="mt-0.5"
                    />
                    <span>
                      Saya tetap ingin mengarsipkan sekarang (paksa). Hanya admin, dan
                      alasannya dicatat di jejak audit.
                    </span>
                  </label>
                  {force && (
                    <textarea
                      className="field mt-2"
                      rows={2}
                      data-testid="entity-archive-reason"
                      placeholder="Alasan (wajib) — mis. badan usaha digabung ke PT lain per 1 Januari…"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                  )}
                </div>
              )}

              {error && (
                <div className="notice-bar danger !py-1.5" data-testid="entity-archive-error">
                  <span className="text-[11.5px]">{error}</span>
                </div>
              )}
              {blockers.length > 0 && (
                <ul className="space-y-1" data-testid="entity-archive-error-blockers">
                  {blockers.map((b, i) => (
                    <li key={i} className="text-[11px] text-[#A8221A]">• {b}</li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-[#EFF0F2] px-4 py-3">
          <button type="button" className="secondary-button"
                  data-testid="entity-archive-cancel" onClick={onClose}>
            Batal
          </button>
          <button
            type="button"
            className="danger-button"
            data-testid="entity-archive-submit"
            disabled={busy || loading || (!clean && (!force || !reason.trim()))}
            onClick={submit}
          >
            {busy ? <Loader2 size={13} className="animate-spin" /> : <Archive size={13} />}
            {clean ? "Arsipkan" : "Arsipkan (paksa)"}
          </button>
        </div>
      </div>
    </div>
  );
}
