/**
 * MobileOrderJourney — perjalanan pesanan (US12) di HP: pesan → verifikasi → setuju →
 * konfirmasi → ambil → kirim → terima, plus posisi bayar. Hanya-baca; tidak butuh
 * akses layar gudang. Endpoint sama dengan panel desktop (`/sales-orders/{id}/journey`).
 */
import { useEffect, useState } from "react";
import { CheckCircle2, Circle, Loader2 } from "lucide-react";
import { formatCurrency, formatDate, formatDateTime } from "../../../utils/formatters";
import { orderJourney } from "../../sales_admin/workDeskApi";

// tanggal bisnis (mis. tanggal bayar) tanpa jam → tanggal saja; stempel waktu → tanggal + jam WIB.
const fmt = (s) => (!s ? "" : String(s).length <= 10 ? formatDate(`${s}T00:00:00+07:00`) : formatDateTime(s));
// Langkah TAGIHAN berjalan sejajar dengan langkah proses (bisa lunas sebelum dikirim) → tidak dipakai menilai "dilewati".
const MONEY_STEPS = ["ditagih", "dibayar"];

export default function MobileOrderJourney({ orderId }) {
  const [j, setJ] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    orderJourney(orderId).then(setJ).catch((e) => setErr(e?.response?.data?.detail || "Perjalanan pesanan tidak bisa dimuat."));
  }, [orderId]);
  if (err) return <p className="py-2 text-[11px] text-[#C0392B]" data-testid={`m-journey-error-${orderId}`}>{String(err)}</p>;
  if (!j) return <p className="py-2 text-[11px] m-muted"><Loader2 size={12} className="mr-1 inline animate-spin" />Memuat perjalanan…</p>;
  const steps = j.steps || [];
  // UAT 24 Okt (audit UI tahap 2) — G2-20: SO batal tidak lagi menampilkan progres "11%"; langkah proses yang
  // belum selesai padahal langkah SESUDAHNYA sudah selesai (mis. verifikasi Admin Sales saat SO sudah disetujui)
  // ditandai "dilewati" dan bukan lagi langkah aktif. Urutan dari server, penilaian hanya tampilan.
  const isDone = (s) => s.done || s.state === "done";
  const cancelled = steps.some((s) => s.state === "cancelled");
  const proc = steps.filter((s) => !MONEY_STEPS.includes(s.key));
  const lastDone = proc.reduce((m, s, i) => (isDone(s) ? i : m), -1);
  const skipped = new Set(proc.filter((s, i) => i < lastDone && !isDone(s)).map((s) => s.key));
  const currentKey = cancelled ? "" : ((proc.find((s, i) => i > lastDone && !isDone(s)) || steps.find((s) => !isDone(s)) || {}).key || "");
  return (
    <div className="mt-2 rounded-xl border border-[#EFF0F2] bg-white p-2.5" data-testid={`m-journey-${orderId}`}>
      <div className="mb-1.5 flex items-center justify-between">
        <p className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Perjalanan pesanan</p>
        {cancelled
          ? <span className="text-[11px] font-bold text-[#C0392B]" data-testid={`m-journey-cancelled-${orderId}`}>Dibatalkan</span>
          : <span className="text-[11px] font-bold tabular-nums text-[#0058CC]">{Math.round(j.progress?.percent || 0)}%</span>}
      </div>
      {!cancelled && <div className="mb-2 h-1.5 overflow-hidden rounded-full bg-[#EFF0F2]"><div className="h-full rounded-full bg-[#0058CC]" style={{ width: `${Math.min(100, j.progress?.percent || 0)}%` }} /></div>}
      {steps.map((s, i) => {
        const done = isDone(s);
        const current = s.key === currentKey;
        const skip = skipped.has(s.key);
        return (
          <div key={s.key} className="flex gap-2" data-testid={`m-journey-step-${orderId}-${s.key}`}>
            <div className="flex flex-col items-center">
              {done ? <CheckCircle2 size={15} className="text-[#1B7F4B]" /> : <Circle size={15} className={current ? "text-[#0058CC]" : "text-[#C7C7CC]"} />}
              {i < steps.length - 1 && <span className={`w-px flex-1 ${done ? "bg-[#BFE6CE]" : "bg-[#E5E5EA]"}`} />}
            </div>
            <div className="min-w-0 flex-1 pb-2">
              <p className={`text-[12px] font-semibold ${done ? "text-[#1C1C1E]" : current ? "text-[#0058CC]" : "text-[#8E8E93]"}`}>{s.label}
                {skip && <span className="ml-1 rounded bg-[#F2F3F5] px-1 text-[10px] font-semibold text-[#6B6B73]" data-testid={`m-journey-skipped-${orderId}-${s.key}`}>dilewati</span>}</p>
              {skip ? <p className="text-[10.5px] m-muted">Tidak dilakukan sebelum langkah berikutnya selesai.</p>
                : cancelled && !done ? null
                  : (s.detail || s.at) && <p className="text-[10.5px] m-muted">{[s.detail, fmt(s.at), s.by].filter(Boolean).join(" · ")}</p>}
            </div>
          </div>
        );
      })}
      {/* Cek UI UAT v3 — pesanan ambil sendiri: kode pickup dibagikan sales ke pelanggan (dulu hanya terlihat Admin Gudang). */}
      {(j.logistics || []).filter((l) => l.mode === "self_pickup" && l.pickup_code).map((l) => (
        <p key={l.id} className="mb-1 rounded-lg bg-[#F5EEFB] px-2 py-1.5 text-[11.5px] text-[#6B219A]" data-testid={`m-journey-pickup-code-${l.id}`}>
          Kode pickup <b className="font-mono tracking-widest">{l.pickup_code}</b>{l.pickup_date ? ` · ambil ${l.pickup_date}` : ""} · {l.status_label}
        </p>
      ))}
      <div className="mt-1 grid grid-cols-2 gap-2 border-t border-[#EFF0F2] pt-2 text-[11px]">
        <div><p className="m-muted">Sudah dibayar</p><p className="font-bold tabular-nums text-[#1B7F4B]">{formatCurrency(j.paid_total)}</p></div>
        <div className="text-right"><p className="m-muted">Sisa tagihan</p><p className="font-bold tabular-nums text-[#C0392B]" data-testid={`m-journey-outstanding-${orderId}`}>{formatCurrency(j.outstanding)}</p></div>
      </div>
    </div>
  );
}
