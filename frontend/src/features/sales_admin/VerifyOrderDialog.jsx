/**
 * VerifyOrderDialog — FASE E-8 (E8.13 · US17) · **VERIFIKASI ADMINISTRATIF**.
 *
 * Trial 22 Okt (E8, keputusan pemilik) — dialog ini kini **Periksa & lepas ke gudang** dalam satu tombol: kelengkapan
 * diverifikasi, gerbang persetujuan diajukan, dan pesanan dilepas ke gudang (yang masih menunggu ACC Manajer dilepas
 * otomatis sesudah ACC). "Tahan dulu" = diperiksa tetapi belum dilepas.
 *
 * Verifikasi bukan sekadar checklist: Admin harus MELIHAT data yang diperiksanya.
 * Karena itu dialog ini dua kolom di layar besar — kiri DATA PESANAN (pelanggan,
 * alamat, termin, baris barang + kondisi stok, total), kanan DAFTAR PERIKSA.
 *
 * Batas wewenang ditulis apa adanya: baris **kredit** ditandai TIDAK menghalangi —
 * penahanan kredit adalah keputusan manajer, bukan hasil verifikasi Anda.
 */
import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle, CheckCircle2, ClipboardCheck, ExternalLink, Info, XCircle,
} from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import { apiErrorText } from "../../utils/apiError";
import { useEscapeClose } from "../../utils/escapeLayers";
import OrderPreviewCard from "./OrderPreviewCard";
import { releaseMessage, reviewRelease, verificationPreview } from "./workDeskApi";

export default function VerifyOrderDialog({
  orderId, orderNumber, customerName, onClose, onVerified, onOpenFull,
}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [hold, setHold] = useState(false);
  useEscapeClose(true, onClose);

  const load = useCallback(async () => {
    setLoading(true);
    try { setData(await verificationPreview(orderId)); setError(""); }
    catch (e) { setError(apiErrorText(e, "Gagal memuat daftar periksa.")); }
    finally { setLoading(false); }
  }, [orderId]);

  useEffect(() => { load(); }, [load]);

  async function submit() {
    setBusy(true); setError("");
    try {
      const res = await reviewRelease(orderId, note, hold);
      onVerified?.(releaseMessage(res, orderNumber), res);
    } catch (e) {
      setError(apiErrorText(e, "Gagal memeriksa & melepas pesanan."));
      load();
    } finally { setBusy(false); }
  }

  const checks = Array.isArray(data?.checks) ? data.checks : [];
  const gaps = Array.isArray(data?.blocking_gaps) ? data.blocking_gaps : [];
  const warnings = Array.isArray(data?.warnings) ? data.warnings : [];
  const sudah = data?.verification?.status === "verified";
  // Sudah diverifikasi (mis. data lama) tetap boleh dilepas lewat tombol yang sama.
  const bisa = !!data?.verifiable && !!data?.ready;

  return (
    <div className="modal-overlay" data-testid="verify-dialog"
         onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}
           style={{ maxWidth: 1020, maxHeight: "90vh", overflowY: "auto" }}>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex min-w-0 items-start gap-2">
            <ClipboardCheck size={17} className="mt-0.5 shrink-0 text-[#0058CC]" />
            <div className="min-w-0">
              <p className="modal-title" data-testid="verify-dialog-title">
                Periksa & lepas ke gudang · {orderNumber}
              </p>
              <p className="modal-subtitle">
                {customerName} · cocokkan data pesanan (kiri) dengan daftar periksa (kanan). Harga khusus & nilai
                tetap diputus manajer — bila masih menunggu, pesanan dilepas <b>otomatis</b> sesudah ACC.
              </p>
            </div>
          </div>
          {onOpenFull && (
            <button data-testid="verify-open-full" onClick={onOpenFull}
                    className="inline-flex shrink-0 items-center gap-1 rounded-full border border-[#CBDFFF] bg-[#F2F7FF] px-2.5 py-1 text-[10.5px] font-bold text-[#0058CC] hover:bg-[#EAF2FF]">
              <ExternalLink size={11} /> Buka Pesanan Lengkap
            </button>
          )}
        </div>

        <ErrorNotice message={error} onDismiss={() => setError("")} testId="verify-error" />

        {loading ? (
          <div className="py-10 text-center text-[12px] text-[#6B6B73]" data-testid="verify-loading">
            Memuat data pesanan & daftar periksa…
          </div>
        ) : (
          <div className="mt-3 grid items-start gap-3 lg:grid-cols-[1.15fr_1fr]">
            {/* ── KIRI: data pesanan yang sedang diperiksa ── */}
            <OrderPreviewCard preview={data?.order_preview} testPrefix="verify-preview" />

            {/* ── KANAN: hasil pemeriksaan ── */}
            <div className="grid gap-2">
              {sudah && (
                <div data-testid="verify-already"
                     className="rounded-lg border border-[#BFE6CE] bg-[#E6F6EC] px-3 py-2">
                  <p className="text-[11.5px] font-bold text-[#1B7F4B]">
                    Sudah diverifikasi oleh {data.verification.by}
                    {data.verification.by_role ? ` (${data.verification.by_role})` : ""}
                  </p>
                  <p className="text-[10.5px] text-[#31624A]">
                    {(data.verification.at || "").slice(0, 16).replace("T", " ")}
                    {data.verification.note ? ` · ${data.verification.note}` : ""}
                  </p>
                </div>
              )}

              {gaps.length > 0 && (
                <div data-testid="verify-gaps"
                     className="rounded-lg border border-[#F5C9BC] bg-[#FDEDE7] px-3 py-2">
                  <p className="text-[11.5px] font-bold text-[#C0392B]">
                    Belum bisa diverifikasi — lengkapi dulu:
                  </p>
                  <ul className="mt-0.5 list-disc pl-4 text-[11px] text-[#8C2E1F]">
                    {gaps.map((g) => <li key={g}>{g}</li>)}
                  </ul>
                  <p className="mt-1 text-[10.5px] text-[#8C2E1F]">
                    Perbaiki lewat “Buka Pesanan Lengkap”, lalu buka dialog ini lagi.
                  </p>
                </div>
              )}

              {gaps.length === 0 && warnings.length > 0 && (
                <div data-testid="verify-warnings"
                     className="rounded-lg border border-[#F5D9A8] bg-[#FFF4E5] px-3 py-2">
                  <p className="text-[11.5px] font-bold text-[#8A5300]">
                    Boleh diverifikasi, tapi catat ini: {warnings.join(" · ")}
                  </p>
                </div>
              )}

              <div className="divide-y divide-[#F4F5F7] rounded-lg border border-[#EFF0F2]"
                   data-testid="verify-checklist">
                <div className="bg-[#FAFBFC] px-3 py-1.5">
                  <p className="text-[10.5px] font-bold uppercase tracking-wide text-[#6B6B73]">
                    Daftar Periksa
                  </p>
                </div>
                {checks.map((c) => <CheckRow key={c.id} check={c} />)}
                {checks.length === 0 && (
                  <p className="px-3 py-6 text-center text-[11.5px] text-[#6B6B73]">
                    Tidak ada daftar periksa untuk pesanan ini.
                  </p>
                )}
              </div>

              {!sudah && (
                <textarea data-testid="verify-note" className="field" rows={2}
                  value={note} onChange={(e) => setNote(e.target.value)}
                  placeholder="Catatan pemeriksaan (opsional) — mis. alamat dikonfirmasi lewat telepon" />
              )}
              {bisa && (
                <label data-testid="verify-hold" className="flex items-start gap-2 rounded-lg border border-[#EFF0F2] px-3 py-2 text-[11.5px]">
                  <input type="checkbox" className="mt-0.5" checked={hold} onChange={(e) => setHold(e.target.checked)} />
                  <span><b>Tahan dulu</b> — sudah diperiksa, tetapi jangan dilepas ke gudang sekarang (mis. pelanggan minta
                    kirim ditunda). Lepas nanti dari antrean "Ditahan".</span>
                </label>
              )}
            </div>
          </div>
        )}

        <div className="modal-actions">
          <button className="btn-secondary" data-testid="verify-cancel" onClick={onClose}>
            {bisa ? "Batal" : "Tutup"}
          </button>
          {(bisa || !sudah) && (
            <button data-testid="verify-submit" className="btn-primary"
                    disabled={busy || loading || !bisa}
                    title={!data?.verifiable
                      ? "Pesanan ini sudah dilepas ke gudang / ditutup."
                      : gaps.length > 0
                        ? `Lengkapi dulu: ${gaps.join(" · ")}`
                        : ""}
                    onClick={submit}>
              {busy ? "Memproses…" : hold ? "Periksa & tahan" : "Periksa & lepas ke gudang"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function CheckRow({ check }) {
  const ok = !!check.ok;
  const blocking = !!check.blocking;
  const Icon = ok ? CheckCircle2 : blocking ? XCircle : AlertTriangle;
  const color = ok ? "#1B7F4B" : blocking ? "#C0392B" : "#8A5300";

  return (
    <div className="flex items-start gap-2 px-3 py-2" data-testid={`verify-check-${check.id}`}>
      <Icon size={14} className="mt-0.5 shrink-0" style={{ color }} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <p className="text-[12px] font-semibold text-[#1C1C1E]">{check.label}</p>
          {!blocking && (
            <span className="rounded-full border border-[#E2E2E7] bg-[#F2F2F5] px-1.5 py-0.5 text-[9.5px] font-bold text-[#6E6E73]"
                  data-testid={`verify-nonblocking-${check.id}`}>
              tidak menghalangi
            </span>
          )}
        </div>
        <p className="text-[11px]" style={{ color: ok ? "#4F5058" : color }}>
          {check.detail}
        </p>
        {check.hint && (
          <p className="mt-0.5 flex items-start gap-1 text-[10.5px] text-[#9A9BA3]">
            <Info size={10} className="mt-0.5 shrink-0" /> {check.hint}
          </p>
        )}
      </div>
    </div>
  );
}
