import { useEffect, useMemo, useState } from "react";
import { ChevronDown, Search, ShieldAlert, ShieldCheck, UserRound, X } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import CreditOverrideRequest from "../../pos/CreditOverrideRequest";
import { overlayDismiss } from "../../../utils/overlayDismiss";

/**
 * Trial 22 Okt 2026 (E2/E3, permintaan pemilik) — HP Sales memilih PELANGGAN DULU, seperti POS desktop
 * (`pos-customer-select`). Dulu pelanggan baru dipilih di langkah 1 checkout: harga pelanggan/harga khusus dan status
 * kredit baru terlihat di akhir. Kini dipilih di atas katalog: katalog langsung memakai harga pelanggan, dan pelanggan
 * yang kreditnya lewat batas / diblokir langsung ditandai TIDAK BISA MEMBELI (kecuali izin kredit disetujui Manajer).
 */
export function useCreditStatus(customerId, amount = 0) {
  const [credit, setCredit] = useState(null);
  useEffect(() => {
    if (!customerId) { setCredit(null); return undefined; }
    let alive = true;
    const t = setTimeout(() => {
      axios.get(`${API}/customers/${customerId}/credit-status`, { params: { amount: Number(amount) || 0 } })
        .then((r) => { if (alive) setCredit(r.data); }).catch(() => { if (alive) setCredit(null); });
    }, 300);
    return () => { alive = false; clearTimeout(t); };
  }, [customerId, amount]);
  return credit;
}

export default function MobileCustomerBar({ customers = [], selectedCustomer, onSelect, amount = 0 }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const credit = useCreditStatus(selectedCustomer?.id, amount);
  const blocked = !!credit?.blocked && !credit?.has_approved_override;
  const list = useMemo(() => {
    const t = q.toLowerCase().trim();
    return customers.filter((c) => !t || [c.name, c.city, c.code].filter(Boolean).join(" ").toLowerCase().includes(t)).slice(0, 80);
  }, [customers, q]);
  const chip = !credit ? null : blocked
    ? { cls: "bg-[#FDECEA] text-[#9B1C13]", text: "Kredit terblokir", Icon: ShieldAlert }
    : credit.has_approved_override ? { cls: "bg-[#EAF7EE] text-[#1B7E3B]", text: "Izin kredit disetujui", Icon: ShieldCheck }
      : credit.level === "warning" ? { cls: "bg-[#FFF3D6] text-[#9A5B00]", text: "Mendekati limit", Icon: ShieldAlert }
        : { cls: "bg-[#EAF7EE] text-[#1B7E3B]", text: "Kredit aman", Icon: ShieldCheck };
  return (
    <div data-testid="m-customer-bar" className="mt-2">
      <button type="button" data-testid="m-customer-pick" onClick={() => setOpen(true)}
        className={`flex w-full items-center gap-2 rounded-xl border px-3 py-2 text-left ${selectedCustomer ? "border-[#CBDFFF] bg-[#F2F7FF]" : "border-dashed border-[#0058CC] bg-white"}`}>
        <UserRound size={15} className="shrink-0 text-[#0058CC]" />
        <span className="min-w-0 flex-1">
          <span className="block text-[10px] font-semibold uppercase tracking-wide text-[#6B6B73]">Pelanggan</span>
          <span data-testid="m-customer-name" className="block truncate text-[12.5px] font-semibold text-[#1C1C1E]">
            {selectedCustomer ? `${selectedCustomer.name}${selectedCustomer.city ? ` · ${selectedCustomer.city}` : ""}` : "Pilih pelanggan dulu — harga & kredit ikut pelanggan"}
          </span>
        </span>
        {chip && (
          <span data-testid="m-customer-credit" className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${chip.cls}`}>
            <chip.Icon size={11} /> {chip.text}
          </span>
        )}
        <ChevronDown size={15} className="shrink-0 text-[#8E8E93]" />
      </button>
      {blocked && (
        <div data-testid="m-customer-blocked" className="mt-1.5 rounded-lg border border-[#F1B0AB] bg-[#FDECEA] px-3 py-2 text-[11px] text-[#9B1C13]">
          <b>Pelanggan ini tidak bisa membeli</b> — {(credit.reasons || []).join("; ") || "kredit lewat batas / diblokir"}.
          Checkout terkunci sampai izin kredit disetujui Manajer.
          <div className="mt-1.5"><CreditOverrideRequest customer={selectedCustomer} amount={amount} /></div>
        </div>
      )}
      {open && (
        <div className="fixed inset-0 z-50 flex items-end bg-black/40" data-testid="m-customer-sheet" {...overlayDismiss(() => setOpen(false))}>
          <div className="max-h-[80vh] w-full overflow-hidden rounded-t-2xl bg-white" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-[#EFF0F2] px-4 py-3">
              <p className="text-[14px] font-bold">Pilih pelanggan</p>
              <button type="button" aria-label="Tutup" onClick={() => setOpen(false)}><X size={18} /></button>
            </div>
            <div className="px-4 py-2">
              <div className="flex items-center gap-2 rounded-xl bg-[#F2F3F5] px-3 py-2">
                <Search size={14} className="text-[#8E8E93]" />
                <input data-testid="m-customer-search" autoFocus value={q} onChange={(e) => setQ(e.target.value)}
                  placeholder="Cari nama / kota…" className="w-full bg-transparent text-[13px] outline-none" />
              </div>
            </div>
            <div className="max-h-[60vh] overflow-y-auto pb-4">
              {list.map((c) => (
                <button key={c.id} type="button" data-testid={`m-customer-option-${c.id}`}
                  onClick={() => { onSelect?.(c); setOpen(false); setQ(""); }}
                  className={`flex w-full items-center justify-between px-4 py-2.5 text-left text-[13px] ${selectedCustomer?.id === c.id ? "bg-[#F2F7FF] font-semibold text-[#0058CC]" : ""}`}>
                  <span className="min-w-0 truncate">{c.name}</span>
                  <span className="ml-2 shrink-0 text-[11px] text-[#8E8E93]">{c.city || ""}</span>
                </button>
              ))}
              {list.length === 0 && <p className="px-4 py-6 text-center text-[12px] text-[#8E8E93]">Pelanggan tidak ditemukan.</p>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
