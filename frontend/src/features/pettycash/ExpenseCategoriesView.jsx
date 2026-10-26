/**
 * ExpenseCategoriesView — Pengaturan › Keuangan & Pajak › **Kategori Beban** (pemetaan kategori pengeluaran kas
 * kecil → akun COA; dipakai saat posting GL pertanggungjawaban: Dr beban per kategori / Cr Kas Kecil).
 *
 * Fase 3 · P2 (D-02, keputusan pemilik 26 Okt) — dulu DUA editor untuk koleksi `expense_categories`:
 *   · layar ini (pemilih akun COA, hanya lapisan global, tanpa baris baru);
 *   · Master per Badan Usaha kind `expense-categories` (global + salinan per PT + baris baru, akun diketik bebas).
 * Kini satu layar: tabel berlapis (`EntityMasterKindPanel`) + pemilih akun COA (`/gl/accounts`, akun beban 6-xxxx).
 * Master per Badan Usaha hanya menautkan ke sini. RBAC sama: tulis = cash_settlement.manage (dihitung server).
 *
 * Data kembar (Q5): kategori aktif di lapisan yang sama yang memakai akun SAMA (mis. "Office Supplies" & "ATK" →
 * 6-4100) hanya DIPERINGATKAN — tidak dihapus/digabung otomatis sampai pemilik mengizinkan pembersihan data.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import LinkCard from "../../components/LinkCard";
import DesktopOnlyNotice from "../../components/DesktopOnlyNotice";
import EntityMasterKindPanel from "../settings/masters/EntityMasterKindPanel";

/** Kelompok kategori aktif yang memakai akun sama di lapisan yang sama (global / satu badan usaha). */
export function sharedAccountGroups(rows) {
  const by = {};
  (rows || []).filter((r) => r.active !== false && r.account_code).forEach((r) => {
    const k = `${r.entity_scope === "global" ? "global" : r.entity_id}::${r.account_code}`;
    (by[k] = by[k] || []).push(r);
  });
  return Object.values(by).filter((list) => list.length > 1)
    .map((list) => ({ account: list[0].account_code, labels: list.map((r) => r.label || r.code) }));
}

export default function ExpenseCategoriesView({ selectedEntity, entities = [] }) {
  const [accounts, setAccounts] = useState([]);
  const [rows, setRows] = useState([]);

  const loadSide = useCallback(async () => {
    const [a, c] = await Promise.all([
      axios.get(`${API}/gl/accounts`).catch(() => ({ data: [] })),
      axios.get(`${API}/entity-masters/expense-categories`, { params: { include_inactive: false } }).catch(() => ({ data: {} })),
    ]);
    setAccounts(Array.isArray(a.data) ? a.data : (a.data?.items || []));
    setRows(c.data?.rows || []);
  }, []);
  useEffect(() => { loadSide(); }, [loadSide, selectedEntity]);

  // Akun beban yang postable (kode 6-xxxx) untuk pemetaan; akun tersimpan di luar daftar tetap tampil berlabel.
  const accountOptions = useMemo(() => accounts
    .filter((a) => (a.is_postable ?? a.is_active ?? true) && String(a.code || "").startsWith("6"))
    .map((a) => ({ value: a.code, label: `${a.code} · ${a.name}` })), [accounts]);
  const twins = useMemo(() => sharedAccountGroups(rows), [rows]);
  const accName = (code) => accounts.find((a) => a.code === code)?.name || "";

  return (
    <div data-testid="expense-categories-view" className="grid gap-3">
      <DesktopOnlyNotice testId="settings-desktop-notice" what="Pengaturan" />
      <EntityMasterKindPanel kind="expense-categories" entities={entities} selectedEntity={selectedEntity}
        testId="excat-panel" showRibbon includeInactive onChanged={loadSide}
        fieldOptions={{ account_code: accountOptions.length ? accountOptions : undefined }}
        hintOverride="Akun beban yang di-debit saat pertanggungjawaban (LPJ) disetujui; kredit selalu ke Kas Kecil. Ganti akun berlaku untuk LPJ berikutnya — jurnal lama tidak berubah. Tiap badan usaha boleh punya akun tujuan sendiri."
        notice={<>
          {twins.length > 0 && (
            <div className="flex items-start gap-2 rounded-md border border-[#F5C97B] bg-[#FFF7E6] px-3 py-2 text-[11.5px] text-[#8C4A00]"
              data-testid="excat-twin-warning">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              <span>
                <b>Kemungkinan kategori kembar:</b>{" "}
                {twins.map((t) => `${t.labels.join(" & ")} → ${t.account}${accName(t.account) ? ` (${accName(t.account)})` : ""}`).join("; ")}.
                {" "}Data tidak diubah otomatis — pembersihan menunggu keputusan pemilik.
              </span>
            </div>
          )}
          <LinkCard testId="excat-mapping-link" what="Pemetaan akun per fitur (penjualan, pembelian, kas)"
            where="Pengaturan › Keuangan & Pajak › Pemetaan Akun" view="gl-account-mappings" hideWhenDenied />
        </>} />
    </div>
  );
}
