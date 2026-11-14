import { AlertCircle, ArrowLeftRight, Check } from "lucide-react";
import { formatQty } from "../utils/formatters";
import { modeMeta } from "../utils/fulfillment";
import { canSeeSourcing } from "../utils/sourcingVisibility";

/** PK-30 (IC-09) — alasan baku Permintaan Internal dari keranjang (dibaca Admin Sales di antreannya). */
export const INTERNAL_REQUEST_REASON = "Stok PT sendiri tidak cukup — diminta dari keranjang penjualan";

/** `reqStatus` = `{status: "requesting"|"requested"|"error", number?, message?}` (bentuk teks lama tetap dibaca). */
const reqOf = (reqStatus) => (typeof reqStatus === "string" ? { status: reqStatus } : (reqStatus || {}));

/**
 * Info ketersediaan/fulfillment (ATP) per baris cart + tombol **Buat Permintaan Internal** bila stok diambil dari PT
 * lain (PK-30: dulu "Minta Transfer" lewat jalur transfer harga pokok yang kini ditutup).
 * Dipisah dari CartPanel agar file tetap ramping (compliance < 500 baris).
 */
export function FulfillmentInfo({ line, loading, reqStatus, onRequestTransfer }) {
  // 2026-10 — sales cukup memilih barang; alokasi/sumber stok diputus Admin Sales.
  if (!canSeeSourcing()) return null;
  if (!line) {
    if (loading) {
      return <p className="mt-2 text-[10px] text-[#8E8E93]">Mengecek ketersediaan (ATP)…</p>;
    }
    return null;
  }
  const meta = modeMeta(line.primary_mode);
  const bo = line.breakdown?.backorder || 0;
  const ic = line.breakdown?.inter_company || 0;
  const source = (line.cross_entity || [])[0];
  const req = reqOf(reqStatus);
  return (
    <div
      data-testid={`cart-item-fulfillment-${line.product_id}`}
      className="mt-2 rounded-md border border-[#EFF0F2] bg-white p-2"
    >
      <div className="flex items-center justify-between gap-2">
        <span
          data-testid={`cart-item-mode-${line.product_id}`}
          data-mode={line.primary_mode}
          className={`status-pill ${meta.cls}`}
        >
          {line.primary_mode === "inter_company" && <ArrowLeftRight size={11} />}
          {meta.label}
        </span>
        <span className="text-[10px] text-[#6B6B73] tabular-nums">
          Bisa dijanjikan <span className="font-bold text-[#1C1C1E]">{formatQty(line.own_atp)}</span>
        </span>
      </div>
      {/* Poin 15 — perjelas: Tersedia sekarang + Akan datang = Bisa dijanjikan (ATP) */}
      <div className="mt-1.5 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[10px] text-[#6B6B73] tabular-nums">
        <span>Tersedia sekarang <span className="font-semibold text-[#126E2C]">{formatQty(line.own_available)}</span></span>
        <span className="text-[#C7C7CC]">+</span>
        <span>Akan datang <span className="font-semibold text-[#8C4A00]">{formatQty(line.own_incoming)}</span></span>
        <span className="text-[#C7C7CC]">=</span>
        <span>Bisa dijanjikan <span className="font-bold text-[#1C1C1E]">{formatQty(line.own_atp)}</span></span>
        {ic > 0 && (
          <span className="ml-1">· Dari PT lain <span className="font-semibold text-[#6B219A]">{formatQty(ic)}</span></span>
        )}
      </div>
      {bo > 0 && (
        <p className="mt-1 text-[10px] font-semibold text-[#A8221A] tabular-nums">
          Backorder (menunggu barang masuk) {formatQty(bo)} {line.unit}
        </p>
      )}
      <p className="mt-1 text-[10px] leading-snug text-[#8E8E93]">{line.explanation}</p>
      {line.primary_mode === "inter_company" && ic > 0 && source && (
        <div className="mt-2">
          {req.status === "requested" ? (
            <p
              data-testid={`transfer-requested-${line.product_id}`}
              className="flex items-center gap-1 rounded-md bg-kn-action-soft px-2 py-1.5 text-fs-12 font-semibold text-kn-action"
            >
              <Check size={12} className="flex-shrink-0" /> Permintaan Internal {req.number} dibuat — menunggu Admin Sales.
            </p>
          ) : (
            <>
              <button
                type="button"
                data-testid={`request-transfer-${line.product_id}`}
                disabled={req.status === "requesting" || !onRequestTransfer}
                onClick={() => onRequestTransfer && onRequestTransfer(line)}
                className="secondary-button btn-sm flex w-full items-center justify-center gap-1.5"
              >
                <ArrowLeftRight size={12} />
                {req.status === "requesting"
                  ? "Memproses…"
                  : `Buat Permintaan Internal (${formatQty(ic)} ${line.unit})`}
              </button>
              {req.status === "error" && (
                <p data-testid={`transfer-request-error-${line.product_id}`}
                  className="mt-1 flex items-center gap-1 text-fs-12 font-semibold text-kn-danger-text">
                  <AlertCircle size={12} className="flex-shrink-0" /> Permintaan gagal dibuat: {req.message || "coba lagi"}
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
