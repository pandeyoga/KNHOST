/**
 * OrderReleaseSummary — Trial 22 Okt 2026 (E8/E10, keputusan pemilik). Satu ringkasan yang SAMA di HP sales, detail SO
 * desktop, dan meja: di mana pesanan ini sebelum masuk gudang.
 *
 * Aturan tampilan (supaya tidak membingungkan):
 * - satu label status: "Menunggu ACC harga" → "Harga ditolak · pilih langkah" → "Dikirim ke gudang"; kata
 *   "Disetujui/Dikonfirmasi" tidak dipakai selama harga belum diputus;
 * - harga khusus SELALU berpasangan "normal → diminta" + dua total berlabel (harga normal / bila disetujui);
 * - akibatnya ditulis terang (belum masuk gudang, belum dikabarkan ke pelanggan) dan batas booking stok selalu tampil.
 */
import { CheckCircle2, Circle, Clock, Hourglass, Info, PauseCircle, XCircle } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";

const PRE_RELEASE = ["reserved", "waiting_approval", "waiting_stock", "draft", "approved"];

const fmtWib = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("id-ID", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
};

export function releaseView(order) {
  const pa = order?.pending_approvals || [];
  const sp = pa.filter((p) => p.type === "special_price" && ["pending", "rejected", "approved"].includes(p.status));
  const rel = order?.release || {};
  const pending = pa.filter((p) => p.status === "pending");
  const rejected = pa.filter((p) => p.status === "rejected");
  let label = "Menunggu diperiksa Admin Sales"; let tone = "warn";
  if (rejected.length) { label = "Harga ditolak · pilih langkah"; tone = "danger"; }
  else if (rel.requested && rel.hold) { label = "Ditahan Admin Sales"; tone = "warn"; }
  else if (pending.some((p) => p.type === "special_price")) label = "Menunggu ACC harga";
  else if (pending.length) label = "Menunggu ACC Manajer";
  else if (order?.status === "waiting_stock") label = "Menunggu stok";
  else if (rel.requested) label = "Sudah diperiksa · siap dilepas";
  return { sp, pending, rejected, rel, label, tone };
}

function Step({ state, children, testId }) {
  const Icon = state === "done" ? CheckCircle2 : state === "wait" ? Clock : state === "bad" ? XCircle : state === "hold" ? PauseCircle : Circle;
  const color = state === "done" ? "#1B7F4B" : state === "wait" || state === "hold" ? "#9A5B00" : state === "bad" ? "#C0392B" : "#8E8E93";
  return (
    <p data-testid={testId} className="flex items-start gap-1.5 text-[11px]" style={{ color: state === "todo" ? "#6B6B73" : "#1C1C1E" }}>
      <Icon size={13} className="mt-0.5 shrink-0" style={{ color }} /> <span>{children}</span>
    </p>
  );
}

export default function OrderReleaseSummary({ order }) {
  if (!order || order.order_type === "sample" || !PRE_RELEASE.includes(order.status)) return null;
  const { sp, pending, rejected, rel, label, tone } = releaseView(order);
  const items = order.items || [];
  const qtyOf = (pid) => items.filter((it) => it.product_id === pid).reduce((s, it) => s + Number(it.quantity || 0), 0);
  const openSp = sp.filter((p) => p.status !== "approved");
  const saving = openSp.reduce((s, p) => s + (Number(p.normal_price || 0) - Number(p.requested_price || 0)) * qtyOf(p.product_id), 0);
  const ratio = Number(order.total_amount || 0) > 0 ? Number(order.grand_total || 0) / Number(order.total_amount) : 1;
  const grand = Number(order.grand_total || order.total_amount || 0);
  const spState = rejected.some((p) => p.type === "special_price") ? "bad" : openSp.length ? "wait" : "done";
  const toneCls = tone === "danger" ? "border-[#F5C2C2] bg-[#FDE2E2] text-[#9B1C1C]" : "border-[#FFE2B8] bg-[#FFF7EC] text-[#9A5B00]";
  return (
    <div data-testid="order-release-summary" className="mb-2 rounded-lg border border-[#EFF0F2] bg-white p-2.5">
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <span className="text-[11.5px] font-bold text-[#1C1C1E]">Sebelum masuk gudang</span>
        <span data-testid="order-release-label" className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${toneCls}`}>{label}</span>
      </div>
      <div className="space-y-0.5">
        <Step state="done" testId="order-release-step-created">Pesanan dibuat · stok dibooking</Step>
        {sp.length > 0 && (
          <Step state={spState} testId="order-release-step-price">
            Harga khusus · {spState === "bad" ? "DITOLAK — sales pilih langkah" : spState === "wait" ? "menunggu Manajer" : "disetujui"}
          </Step>
        )}
        {pending.some((p) => p.type !== "special_price") && <Step state="wait">Persetujuan Manajer (nilai/makloon) · menunggu</Step>}
        <Step state={rel.requested ? (rel.hold ? "hold" : "done") : "wait"} testId="order-release-step-review">
          {rel.requested ? (rel.hold ? `Diperiksa ${rel.by || ""} · DITAHAN` : `Diperiksa ${rel.by || "Admin Sales"}`) : "Diperiksa Admin Sales · menunggu"}
        </Step>
        <Step state="todo" testId="order-release-step-warehouse">
          Dikirim ke gudang {rel.requested && !rel.hold ? "(otomatis sesudah semua ACC beres)" : ""}
        </Step>
      </div>
      {openSp.length > 0 && (
        <div data-testid="order-release-prices" className="mt-2 space-y-1 rounded-md border border-[#FFE2B8] bg-[#FFFBF3] p-2">
          {openSp.map((p) => (
            <p key={p.id} className="flex flex-wrap items-center justify-between gap-1 text-[11px] tabular-nums">
              <span className="min-w-0 truncate">{p.product_name} · {qtyOf(p.product_id)} {items.find((it) => it.product_id === p.product_id)?.unit || ""}</span>
              <span>Normal {formatCurrency(p.normal_price)} → diminta <b className="text-[#9A5B00]">{formatCurrency(p.requested_price)}</b>
                <span className={`ml-1 rounded px-1 text-[9.5px] font-bold ${p.status === "rejected" ? "bg-[#FDE2E2] text-[#9B1C1C]" : "bg-[#FFF3D6] text-[#9A5B00]"}`}>
                  {p.status === "rejected" ? "ditolak" : "menunggu"}</span></span>
            </p>
          ))}
          <p className="flex justify-between border-t border-[#F3E2C0] pt-1 text-[11px]"><span>Total harga normal</span><b className="tabular-nums" data-testid="order-release-total-normal">{formatCurrency(grand)}</b></p>
          <p className="flex justify-between text-[11px]"><span>Total bila disetujui</span><b className="tabular-nums text-[#9A5B00]" data-testid="order-release-total-requested">≈ {formatCurrency(Math.max(grand - saving * ratio, 0))}</b></p>
        </div>
      )}
      <p className="mt-1.5 flex items-start gap-1 text-[10.5px] text-[#6B6B73]">
        <Info size={11} className="mt-0.5 shrink-0" />
        Belum masuk gudang dan belum dikabarkan ke pelanggan sampai semua keputusan beres.
      </p>
      {order.reservation_expires_at && (
        <p data-testid="order-release-booking" className="mt-0.5 flex items-start gap-1 text-[10.5px] font-semibold text-[#9A5B00]">
          <Hourglass size={11} className="mt-0.5 shrink-0" /> Booking stok berakhir {fmtWib(order.reservation_expires_at)} bila belum dilepas ke gudang
        </p>
      )}
    </div>
  );
}
