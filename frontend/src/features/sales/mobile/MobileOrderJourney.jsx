/**
 * MobileOrderJourney — perjalanan pesanan (US12) di HP: pesan → verifikasi → setuju →
 * konfirmasi → ambil → kirim → terima, plus posisi bayar. Hanya-baca; tidak butuh
 * akses layar gudang. Endpoint sama dengan panel desktop (`/sales-orders/{id}/journey`).
 */
import { useEffect, useState } from "react";
import { CheckCircle2, Circle, Loader2 } from "lucide-react";
import { formatCurrency } from "../../../utils/formatters";
import { orderJourney } from "../../sales_admin/workDeskApi";

const fmt = (s) => (s ? new Date(s).toLocaleString("id-ID", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "");

export default function MobileOrderJourney({ orderId }) {
  const [j, setJ] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    orderJourney(orderId).then(setJ).catch((e) => setErr(e?.response?.data?.detail || "Perjalanan pesanan tidak bisa dimuat."));
  }, [orderId]);
  if (err) return <p className="py-2 text-[11px] text-[#C0392B]" data-testid={`m-journey-error-${orderId}`}>{String(err)}</p>;
  if (!j) return <p className="py-2 text-[11px] m-muted"><Loader2 size={12} className="mr-1 inline animate-spin" />Memuat perjalanan…</p>;
  const steps = j.steps || [];
  return (
    <div className="mt-2 rounded-xl border border-[#EFF0F2] bg-white p-2.5" data-testid={`m-journey-${orderId}`}>
      <div className="mb-1.5 flex items-center justify-between">
        <p className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Perjalanan pesanan</p>
        <span className="text-[11px] font-bold tabular-nums text-[#0058CC]">{Math.round(j.progress?.percent || 0)}%</span>
      </div>
      <div className="mb-2 h-1.5 overflow-hidden rounded-full bg-[#EFF0F2]"><div className="h-full rounded-full bg-[#0058CC]" style={{ width: `${Math.min(100, j.progress?.percent || 0)}%` }} /></div>
      {steps.map((s, i) => {
        const done = s.done || s.state === "done";
        const current = s.key === j.current_step;
        return (
          <div key={s.key} className="flex gap-2" data-testid={`m-journey-step-${orderId}-${s.key}`}>
            <div className="flex flex-col items-center">
              {done ? <CheckCircle2 size={15} className="text-[#1B7F4B]" /> : <Circle size={15} className={current ? "text-[#0058CC]" : "text-[#C7C7CC]"} />}
              {i < steps.length - 1 && <span className={`w-px flex-1 ${done ? "bg-[#BFE6CE]" : "bg-[#E5E5EA]"}`} />}
            </div>
            <div className="min-w-0 flex-1 pb-2">
              <p className={`text-[12px] font-semibold ${done ? "text-[#1C1C1E]" : current ? "text-[#0058CC]" : "text-[#8E8E93]"}`}>{s.label}</p>
              {(s.detail || s.at) && <p className="text-[10.5px] m-muted">{[s.detail, fmt(s.at), s.by].filter(Boolean).join(" · ")}</p>}
            </div>
          </div>
        );
      })}
      <div className="mt-1 grid grid-cols-2 gap-2 border-t border-[#EFF0F2] pt-2 text-[11px]">
        <div><p className="m-muted">Sudah dibayar</p><p className="font-bold tabular-nums text-[#1B7F4B]">{formatCurrency(j.paid_total)}</p></div>
        <div className="text-right"><p className="m-muted">Sisa tagihan</p><p className="font-bold tabular-nums text-[#C0392B]" data-testid={`m-journey-outstanding-${orderId}`}>{formatCurrency(j.outstanding)}</p></div>
      </div>
    </div>
  );
}
