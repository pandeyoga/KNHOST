/**
 * EntityMastersView (FASE E-4 · E4d) — MASTER PER BADAN USAHA.
 *
 * KENAPA SATU LAYAR UNTUK BANYAK MASTER
 * Keputusan pemilik #6: semua master yang dulu "bersama" harus bisa berbeda per badan usaha. Aturan yang sama
 * (**global → badan usaha**, override menang, global tak boleh diubah dari konteks satu badan usaha) cukup ditulis
 * SEKALI — kini di `EntityMasterKindPanel` (tabel berlapis satu jenis master).
 *
 * Fase 3 · P2 (keputusan pemilik 26 Okt, D-01..D-04 + P16-K1 "Master Data"):
 *  · Jenis master yang punya RUMAH DOMAIN (Template Dokumen, Kategori Beban, Komisi & Insentif, Aturan Persetujuan,
 *    Kebijakan Retur) tidak lagi ditampilkan sebagai tabel kedua di sini — cukup KARTU TAUTAN ke layar utamanya
 *    (di sana tabel berlapis yang sama + form terlengkap). Kode mentah & dua editor untuk satu data hilang.
 *  · Kepala layar memuat INDEKS master per domain (Produk, Kategori, Satuan, Gudang, Pemasok, …) — "di mana master X?"
 *    terjawab dari sini.
 *  · L-06: tabel lebar → `ResponsiveTable` (kolom aksi menempel kanan, kartu di HP), ubah baris lewat pop-up.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronRight, Database, Layers3, RefreshCw } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import ErrorNotice from "../../../components/ErrorNotice";
import LinkCard from "../../../components/LinkCard";
import DesktopOnlyNotice from "../../../components/DesktopOnlyNotice";
import { useAppNav } from "../../../context/AppNavContext";
import { entityShortById } from "../../../utils/entityLabel";
import { apiErrorText } from "../../../utils/apiError";
import EntityMasterKindPanel, { EntityScopeRibbon } from "./EntityMasterKindPanel";

/** Fase 3 · P2 — jenis master yang dikelola di layar domainnya: di sini hanya TAUTAN (bukan tabel kedua). */
export const DOMAIN_HOME = {
  "document-templates": { view: "pdf-templates", preset: { tab: "dasar" }, where: "Pengaturan › Dokumen & Cetak › Template Dokumen" },
  "expense-categories": { view: "expense-categories", where: "Pengaturan › Keuangan & Pajak › Kategori Beban" },
  "incentive-rates": { view: "incentive-rates", where: "Pengaturan › Penjualan › Komisi & Insentif" },
  "approval-rules": { view: "approval-rules", where: "Pengaturan › Persetujuan › Aturan Persetujuan" },
  "sales-return-policies": { view: "return-policies", where: "Pengaturan › Penjualan › Kebijakan Retur" },
};
// Editor lengkap yang tetap DIPASANGKAN dengan tabel berlapis di sini (bukan duplikat — cakupannya berbeda).
const FULL_EDITOR = {
  "process-stages": { view: "domain-registry", where: "Pengaturan › Master Data › Registri Domain" },
};
/** Indeks master per domain (kepala layar). Hanya yang boleh dibuka peran aktif yang tampil. */
const DOMAIN_INDEX = [
  ["md-products", "Produk & Varian"], ["md-categories", "Kategori"], ["md-uoms", "Satuan & Konversi"],
  ["color-library", "Pustaka Warna"], ["md-warehouses", "Gudang"], ["suppliers", "Pemasok"], ["makloons", "Mitra Makloon"],
  ["customers-crm", "Pelanggan"], ["grade-master", "Master Grade Mutu"], ["domain-registry", "Registri Domain"],
];

function DomainIndex() {
  const { go, canOpen } = useAppNav();
  const items = DOMAIN_INDEX.filter(([v]) => canOpen(v));
  if (!items.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-[11.5px]" data-testid="em-domain-index">
      <span className="font-semibold text-[#6B6B73]">Master di domainnya:</span>
      {items.map(([v, label]) => (
        <button key={v} type="button" className="secondary-button !px-2 !py-1 text-[11px]" data-testid={`em-domain-${v}`}
          onClick={() => go(v)}>{label}</button>
      ))}
    </div>
  );
}

export default function EntityMastersView({ entities = [], selectedEntity = "all" }) {
  const activeList = useMemo(
    () => (entities || []).filter((e) => e.status !== "inactive" && e.status !== "archived"), [entities]);
  const groupMode = !selectedEntity || selectedEntity === "all";
  const entityLabel = groupMode ? "Semua Badan Usaha" : entityShortById(activeList, selectedEntity);
  const [groups, setGroups] = useState([]);
  const [kind, setKind] = useState("payment-terms");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadGroups = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/entity-masters`);
      setGroups(Array.isArray(res.data) ? res.data : []);
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat daftar master."));
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { loadGroups(); }, [loadGroups, selectedEntity]);

  const spec = groups.find((g) => g.kind === kind) || {};
  const home = DOMAIN_HOME[kind];
  const full = FULL_EDITOR[kind];

  return (
    <div data-testid="entity-masters-view" className="grid gap-4">
      <DesktopOnlyNotice testId="settings-desktop-notice" what="Master per Badan Usaha" />
      <ErrorNotice message={error} onRetry={loadGroups} onDismiss={() => setError("")} testId="em-error-groups" />
      <EntityScopeRibbon groupMode={groupMode} entityLabel={entityLabel} />
      <DomainIndex />

      <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
        {/* Kolom kiri — jenis master */}
        <section className="section-card self-start">
          <div className="section-head">
            <div className="flex min-w-0 items-center gap-2">
              <Layers3 size={15} className="text-[#0058CC]" />
              <span className="kicker">Master</span>
              <h2 data-testid="em-groups-title">Kelompok</h2>
            </div>
            <button data-testid="em-refresh-groups" className="icon-button" onClick={loadGroups} aria-label="Muat ulang kelompok">
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            </button>
          </div>
          <div className="section-body">
            {loading && !groups.length ? (
              <div className="grid gap-2" data-testid="em-groups-loading">
                {[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="h-12 animate-pulse rounded bg-[#F5F5F7]" />)}
              </div>
            ) : groups.length === 0 ? (
              <p data-testid="em-groups-empty" className="py-6 text-center text-[12px] text-[#8E8E93]">
                Belum ada master berlapis yang terdaftar.
              </p>
            ) : (
              <div className="grid gap-1.5">
                {groups.map((g) => {
                  const on = g.kind === kind;
                  return (
                    <button key={g.kind} type="button" data-testid={`em-group-${g.kind}`} onClick={() => setKind(g.kind)}
                      aria-pressed={on}
                      className={`flex items-start gap-2 rounded-md border px-2.5 py-2 text-left transition-colors ${
                        on ? "border-[#0058CC] bg-[#EAF2FF]" : "border-[#E5E5EA] bg-white hover:border-[#0058CC]"}`}>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[12.5px] font-bold text-[#1C1C1E]">{g.label}</span>
                        <span className="block text-[10.5px] text-[#6B6B73]">
                          <span data-testid={`em-count-global-${g.kind}`}>{g.global} global</span>{" · "}
                          <span data-testid={`em-count-entity-${g.kind}`}>{g.entity} khusus</span>
                          {DOMAIN_HOME[g.kind] ? " · dikelola di layar domain" : !g.manage ? " · dikelola di layar sendiri" : ""}
                        </span>
                      </span>
                      <ChevronRight size={14} className={on ? "text-[#0058CC]" : "text-[#C7C7CC]"} />
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </section>

        {/* Kolom kanan — tautan rumah domain, atau tabel berlapis jenis ini */}
        {home ? (
          <section className="section-card self-start" data-testid="em-domain-home">
            <div className="section-head">
              <div className="flex min-w-0 items-center gap-2">
                <Database size={15} className="text-[#0058CC]" />
                <span className="kicker">{entityLabel}</span>
                <h2 data-testid="em-rows-title">{spec.label || kind}</h2>
              </div>
            </div>
            <div className="section-body">
              <LinkCard testId={`em-home-${kind}`} what={spec.label || "Master ini"} where={home.where}
                view={home.view} preset={home.preset}
                summary={spec.global !== undefined ? `${spec.global} global · ${spec.entity} khusus badan usaha` : null}
                readOnlyText={`${spec.label || "Master ini"} dikelola di ${home.where} (khusus peran yang berwenang).`} />
              <p className="mt-2 text-[11px] text-[#6B6B73]">
                Di sana tersedia lapisan yang sama (Global → khusus badan usaha) beserta form lengkapnya — satu data,
                satu tempat mengubah.
              </p>
            </div>
          </section>
        ) : (
          <EntityMasterKindPanel key={kind} kind={kind} entities={entities} selectedEntity={selectedEntity}
            onChanged={loadGroups}
            notice={full ? (
              <LinkCard testId="em-full-editor-link" what="Editor lengkap" where={full.where} view={full.view}
                label="Buka editor lengkap" />
            ) : null} />
        )}
      </div>
    </div>
  );
}
