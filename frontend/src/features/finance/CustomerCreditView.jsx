/**
 * CustomerCreditView (MN-T1) — Keuangan › Piutang › "Titipan & Saldo Kredit". PEMBUNGKUS dua layar lama yang dirender
 * UTUH (isi tidak diubah; penyatuan isi = MN-T2): chip "Titipan pelanggan" = Uang Muka Pelanggan (`advance-report`,
 * GET /api/ar/advance-report — `accounting.view` atau `penalty.issue`) dan "Saldo kredit" = Saldo Kredit
 * (`store-credit`, GET /api/store-credit — `ar_receipt.view`). Alamat lama = alias di `config/viewAliases.js` dengan
 * preset `{ bagian }`; rute cadangan id lama tetap di AppViewRouter. Chip tampil menurut izin endpoint layarnya dan
 * menu yang disembunyikan peran (`hidden_views` / `ROLE_NAV.remove` atas id lama).
 */
import { useState } from "react";
import FilterChips from "../../components/FilterChips";
import useViewPreset from "../../hooks/useViewPreset";
import { can, navExplicitlyHidden } from "../../config/roles";
import AdvanceReportView from "./AdvanceReportView";
import StoreCreditView from "./StoreCreditView";

export const CUSTOMER_CREDIT_PARTS = [
  { key: "titipan", label: "Titipan pelanggan", id: "advance-report", izin: [["accounting", "view"], ["penalty", "issue"]] },
  { key: "saldo", label: "Saldo kredit", id: "store-credit", izin: [["ar_receipt", "view"]] },
];

export default function CustomerCreditView({ currentUser, selectedEntity, onOpenDocument }) {
  const perms = currentUser?.permissions || {};
  const parts = CUSTOMER_CREDIT_PARTS.filter((b) => !navExplicitlyHidden(currentUser?.role, b.id)
    && b.izin.some(([r, a]) => can(perms, r, a)));
  const [part, setPart] = useState("");
  const preset = useViewPreset("customer-credit", (p) => { if (p.bagian) setPart(p.bagian); });
  const wanted = part || preset?.bagian || "";
  const active = parts.some((b) => b.key === wanted) ? wanted : parts[0]?.key;

  return (
    <div className="grid gap-3" data-testid="customer-credit-view">
      <FilterChips testId="customer-credit-bagian" ariaLabel="Bagian" value={active} onChange={setPart}
        options={parts.map((b) => ({ key: b.key, label: b.label }))} />
      {active === "titipan" && <AdvanceReportView selectedEntity={selectedEntity} onOpenDocument={onOpenDocument} />}
      {active === "saldo" && <StoreCreditView selectedEntity={selectedEntity} currentUser={currentUser} />}
      {!parts.length && (
        <div className="empty-state" data-testid="customer-credit-no-access">
          Anda belum punya akses untuk melihat titipan maupun saldo kredit pelanggan. Minta Admin menambahkan akses
          &apos;Uang Masuk, Piutang &amp; Faktur Pajak&apos;.
        </div>
      )}
    </div>
  );
}
