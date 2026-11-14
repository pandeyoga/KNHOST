/**
 * PettyCashView (MN-T1) — Keuangan › Kas & Bank › "Kas Kecil" (dulu hub Kas & Aset › Kas Kecil, tiga tab). PEMBUNGKUS
 * tiga layar lama yang dirender UTUH (isi tidak diubah; satu layar bertahap = MN-T2): chip "Pengajuan dana"
 * (`cash-advances`, GET /api/cash-advances — `cash_advance.view`), "Pertanggungjawaban" (`settlements`,
 * GET /api/cash-advance-settlements — `cash_settlement.view`), "Hutang reimburse" (`reimburse-payables`,
 * GET /api/cash-advance-settlements/reimburse-payables — `accounting.view`). Alamat lama = alias di
 * `config/viewAliases.js` dengan preset `{ bagian }`; rute cadangan id lama tetap di AppViewRouter. Chip tampil menurut
 * izin endpoint layarnya dan menu yang disembunyikan peran (`hidden_views` / `ROLE_NAV.remove` atas id lama).
 */
import { useState } from "react";
import FilterChips from "../../components/FilterChips";
import useViewPreset from "../../hooks/useViewPreset";
import { can, navExplicitlyHidden } from "../../config/roles";
import CashAdvancesView from "./CashAdvancesView";
import SettlementsView from "./SettlementsView";
import ReimbursePayablesView from "./ReimbursePayablesView";

export const PETTY_CASH_PARTS = [
  { key: "pengajuan", label: "Pengajuan dana", id: "cash-advances", izin: [["cash_advance", "view"]] },
  { key: "pertanggungjawaban", label: "Pertanggungjawaban", id: "settlements", izin: [["cash_settlement", "view"]] },
  { key: "reimburse", label: "Hutang reimburse", id: "reimburse-payables", izin: [["accounting", "view"]] },
];

export default function PettyCashView({ currentUser, selectedEntity, entities }) {
  const perms = currentUser?.permissions || {};
  const parts = PETTY_CASH_PARTS.filter((b) => !navExplicitlyHidden(currentUser?.role, b.id)
    && b.izin.some(([r, a]) => can(perms, r, a)));
  const [part, setPart] = useState("");
  const preset = useViewPreset("petty-cash", (p) => { if (p.bagian) setPart(p.bagian); });
  const wanted = part || preset?.bagian || "";
  const active = parts.some((b) => b.key === wanted) ? wanted : parts[0]?.key;

  return (
    <div className="grid gap-3" data-testid="petty-cash-view">
      <FilterChips testId="petty-cash-bagian" ariaLabel="Bagian" value={active} onChange={setPart}
        options={parts.map((b) => ({ key: b.key, label: b.label }))} />
      {active === "pengajuan" && <CashAdvancesView currentUser={currentUser} selectedEntity={selectedEntity} entities={entities} />}
      {active === "pertanggungjawaban" && <SettlementsView currentUser={currentUser} selectedEntity={selectedEntity} entities={entities} />}
      {active === "reimburse" && <ReimbursePayablesView selectedEntity={selectedEntity} entities={entities} />}
      {!parts.length && (
        <div className="empty-state" data-testid="petty-cash-no-access">
          Anda belum punya akses untuk melihat kas kecil. Minta Admin menambahkan akses &apos;Kas Kecil (pengajuan dana
          &amp; pertanggungjawaban)&apos;.
        </div>
      )}
    </div>
  );
}
