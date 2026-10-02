/** Pengingat go-live: jumlah roll stok awal yang belum ber-HPP (hilang sendiri saat semua terisi). */
import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import axios, { API } from "../services/apiClient";

export default function OpeningCostBanner({ onNavigate, selectedEntity }) {
  const [total, setTotal] = useState(0);
  useEffect(() => {
    axios.get(`${API}/inventory/rolls-without-cost`, { params: { limit: 1 } })
      .then((r) => setTotal(r.data?.total || 0)).catch(() => setTotal(0));
  }, [selectedEntity]);
  if (!total) return null;
  return (
    <div data-testid="opening-cost-banner" className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#F1D08A] bg-[#FFF6E0] px-4 py-3">
      <div className="flex items-center gap-2 min-w-0">
        <AlertTriangle size={16} className="shrink-0 text-[#B26A00]" />
        <p className="text-[12.5px] text-[#7A5B00]">
          <b data-testid="opening-cost-banner-count">{total}</b> roll stok awal belum punya HPP — laba & nilai persediaan belum benar sampai semuanya diisi (syarat go-live).
        </p>
      </div>
      <button type="button" data-testid="opening-cost-banner-goto" className="secondary-button"
        onClick={() => onNavigate && onNavigate("operations")}>Lengkapi HPP →</button>
    </div>
  );
}
