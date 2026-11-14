/**
 * EntityScopeBanner (PK-16 · K-15 · UX-06/UX-07/UX-14) — "angka ini milik PT mana?" di laporan & form uang.
 *
 * KENAPA ADA: laporan keuangan dan form uang dulu tidak menyebut PT. Dalam mode "Semua PT" Laba-Rugi menjumlah buku
 * tiap PT, sehingga jual antar-PT ikut terhitung dua kali (pendapatan gabungan 70 jt, ke pihak luar 50 jt) tanpa satu
 * kata pun di layar. Keputusan K-15: angka gabungan = PENJUMLAHAN (belum dieliminasi), dan itu ditulis terang dengan
 * jalan ke Konsolidasi Grup. Form uang menyebut buku PT yang menerima catatannya.
 *
 *   <EntityScopeBanner meta={data?.scope_meta} />                    // laporan; tanpa `meta` → konteks kepala aplikasi
 *   <EntityScopeBanner variant="form" testId="cash-form-scope" />     // form uang
 *
 * Props: `meta` (isi `scope_meta` server: `{mode, entity_ids, entities:[{id, short_name, legal_name}], eliminated,
 *   label}`; kosong → dihitung dari `useEntityScope()`) · `variant` ("report" bawaan | "form") · `testId` (bawaan
 *   "entity-scope-banner"; gabungan menambah `${testId}-combined`, tautan `${testId}-consolidation`) ·
 *   `onOpenConsolidation` (opsional; bawaan `useAppNav().go("consolidation")` bila peran boleh membukanya) ·
 *   `className` (pengganti jarak bawah bawaan).
 *
 * Aturan: id PT TIDAK PERNAH ditampilkan — nama diambil dari `scope_meta`, lalu daftar PT di konteks, lalu
 * "Entitas aktif" (`utils/entityLabel.js`). "Satu PT" = satu PT dalam cakupan hasil hitung (ASUMSI spesifikasi PK-16),
 * jadi akun satu-PT yang memilih "Semua PT" tetap melihat banner satu PT. Elemen akar `<span>` supaya banner boleh
 * dipasang di kepala pop-up (`FormModal` `subtitle` = `<p>`).
 */
import { AlertTriangle, Building2 } from "lucide-react";
import { useEntityScope } from "../context/EntityScopeContext";
import { useAppNav } from "../context/AppNavContext";
import { entityFull, entityShort } from "../utils/entityLabel";

const UNKNOWN = "Entitas aktif";
const CONSOLIDATION_PATH = "Akuntansi & Pajak › Laporan › Konsolidasi Grup";

/** Nama yang sama dengan id teknis dianggap tidak ada (server jatuh ke id bila dokumen PT tanpa nama). */
const named = (v, id) => (v && v !== id ? String(v) : "");
const usable = (list) => (list || []).filter((e) => e && e.id && e.id !== "all" && e.status !== "archived");

/** `scope_meta` setara server, dihitung dari PT di kepala aplikasi (dipakai bila jawaban server belum/tidak ada). */
export function scopeMetaFromContext(selectedEntity, entities) {
  const all = !selectedEntity || selectedEntity === "all";
  const list = usable(entities);
  const picked = !all
    ? [(entities || []).find((e) => e && e.id === selectedEntity) || { id: selectedEntity }]
    : list;
  return {
    mode: all && list.length !== 1 ? "combined" : "single",
    entity_ids: picked.map((e) => e.id),
    entities: picked.map((e) => ({ id: e.id, short_name: entityShort(e, ""), legal_name: entityFull(e, "") })),
    eliminated: false,
    label: "",
  };
}

/** `meta` server bila ada; selain itu konteks. Dipakai layar untuk banner DAN nama berkas unduhan. */
export function useScopeMeta(meta) {
  const { selectedEntity, entities } = useEntityScope();
  return meta && meta.mode ? meta : scopeMetaFromContext(selectedEntity, entities);
}

function fullName(e, ctxList) {
  if (!e) return UNKNOWN;
  const ctx = (ctxList || []).find((x) => x && x.id === e.id);
  return named(e.legal_name, e.id) || (ctx ? entityFull(ctx, "") : "") || named(e.short_name, e.id) || UNKNOWN;
}

function shortName(e, ctxList) {
  const ctx = (ctxList || []).find((x) => x && x.id === e.id);
  return named(e.short_name, e.id) || (ctx ? entityShort(ctx, "") : "") || named(e.legal_name, e.id) || UNKNOWN;
}

/**
 * Bagian nama berkas unduhan: nama pendek PT (aman untuk nama berkas) atau `gabungan`.
 *   `laba-rugi_${scopeFileTag(scope)}_${awal}_${akhir}.csv` → "laba-rugi_KSC_2026-10-01_2026-10-31.csv"
 */
export function scopeFileTag(meta, ctxEntities = []) {
  if (!meta || meta.mode === "combined") return "gabungan";
  const e = (meta.entities || [])[0];
  const raw = e ? shortName(e, ctxEntities) : "";
  const safe = String(raw === UNKNOWN ? "" : raw).normalize("NFKD").replace(/[^\w.-]+/g, "-").replace(/^-+|-+$/g, "");
  return safe || "pt";
}

export default function EntityScopeBanner({
  meta, variant = "report", testId = "entity-scope-banner", onOpenConsolidation, className = "mb-3",
}) {
  const { selectedEntity, entities } = useEntityScope();
  const { go, canOpen } = useAppNav();
  const scope = meta && meta.mode ? meta : scopeMetaFromContext(selectedEntity, entities);
  const combined = scope.mode === "combined";
  const isForm = variant === "form";
  const ents = scope.entities || [];
  const tone = combined
    ? "border-kn-divider bg-kn-warning-soft text-kn-warning-text"
    : "border-kn-divider bg-kn-neutral-soft text-kn-neutral";
  const Icon = combined ? AlertTriangle : Building2;
  const openConsolidation = onOpenConsolidation
    || (canOpen("consolidation") ? () => go("consolidation") : null);

  let body;
  if (combined && isForm) {
    body = (
      <span data-testid={`${testId}-combined`}>
        Mode Semua PT hanya untuk melihat. Pilih satu PT di kepala aplikasi sebelum menyimpan.
      </span>
    );
  } else if (combined) {
    const names = ents.map((e) => shortName(e, entities)).join(", ");
    body = (
      <span data-testid={`${testId}-combined`}>
        <b>Penjumlahan semua PT</b>{names ? ` (${names})` : ""} — transaksi antar-PT <b>belum</b> dieliminasi.
        {" "}Untuk angka grup, buka{" "}
        {openConsolidation ? (
          <button type="button" className="link-button" data-testid={`${testId}-consolidation`}
            title={CONSOLIDATION_PATH} onClick={openConsolidation}>Konsolidasi Grup</button>
        ) : (
          <b data-testid={`${testId}-consolidation-readonly`} title={CONSOLIDATION_PATH}>Konsolidasi Grup</b>
        )}.
      </span>
    );
  } else {
    const name = fullName(ents[0], entities);
    body = (
      <span data-testid={`${testId}-single`}>
        {isForm ? "Dicatat di buku " : "Angka untuk "}<b>{name}</b>
      </span>
    );
  }

  return (
    <span role="note" data-testid={testId} data-scope-mode={combined ? "combined" : "single"} data-variant={variant}
      className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-fs-12 ${tone} ${className}`.trim()}>
      <Icon size={14} aria-hidden="true" className="mt-0.5 shrink-0" />
      {body}
    </span>
  );
}
