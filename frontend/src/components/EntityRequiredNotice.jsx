/**
 * EntityRequiredNotice — "Pilih badan usaha" yang MENGUBAH HEADER (fase 3 · P1, dipakai D-14).
 *
 * KENAPA ADA: beberapa layar (Tutup Buku, Buka Periode, Harga per BU) punya pemilih PT LOKAL selain pemilih di
 * kepala aplikasi. Dua pemilih = dua jawaban untuk "PT mana yang sedang saya lihat?" — layar bisa menghitung PT A
 * sementara kepala bertuliskan PT B. Keputusan D-14: pemilih di header (`EntitySwitcher`) satu-satunya sumber.
 * Saat header di mode "Semua badan usaha", layar yang butuh satu PT menampilkan kartu ini; tombol PT di kartu
 * memanggil `useEntityScope().pickEntity` = mengganti PT di HEADER (berlaku untuk semua layar).
 *
 *   if (!canWrite) return <EntityRequiredNotice what="tutup buku" testId="closing-entity-required" />;
 *   // atau cukup taruh di atas isi — komponen ini `return null` bila satu PT sudah dipilih:
 *   <EntityRequiredNotice what="harga per badan usaha" />
 *
 * Tampil bila (bawaan) akun bisa berganti PT DAN header di mode gabungan (`!canWrite` dari EntityScopeContext).
 * Akun satu-PT tidak pernah melihatnya. `when` (boolean) menimpa syarat bawaan.
 * Props: `what` (teks tujuan, mis. "tutup buku") · `reason` (kalimat penjelas pengganti) · `when` · `testId`
 *   (bawaan "entity-required"; tombol PT `${testId}-pick-<id>`) · `className`.
 */
import { Building2 } from "lucide-react";
import { useEntityScope } from "../context/EntityScopeContext";
import { entityFull, entityShort } from "../utils/entityLabel";

export default function EntityRequiredNotice({ what = "layar ini", reason = "", when, testId = "entity-required", className = "" }) {
  const { entities, canWrite, pickEntity } = useEntityScope();
  const needs = typeof when === "boolean" ? when : !canWrite;
  if (!needs) return null;
  const list = (entities || []).filter((e) => e && e.id && e.id !== "all" && e.status !== "archived");
  return (
    <div className={`entity-required ${className}`.trim()} role="status" data-testid={testId}>
      <Building2 size={16} aria-hidden="true" className="entity-required-icon" />
      <div className="entity-required-body">
        <p className="entity-required-title">Pilih badan usaha untuk {what}</p>
        <p className="entity-required-text">
          {reason || "Angka dan tindakan di sini berlaku per badan usaha. Pilihan Anda mengganti badan usaha di kepala aplikasi (berlaku di semua layar)."}
        </p>
        {list.length > 0 && (
          <div className="entity-required-picks" data-testid={`${testId}-picks`}>
            {list.map((e) => (
              <button key={e.id} type="button" className="secondary-button" title={`Pindah ke ${entityFull(e)}`}
                data-testid={`${testId}-pick-${e.id}`} onClick={() => pickEntity(e.id)}>
                <Building2 size={12} aria-hidden="true" /> {entityShort(e)}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
