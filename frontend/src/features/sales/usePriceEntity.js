/**
 * usePriceEntity — badan usaha untuk layar HARGA (Harga per Badan Usaha, Harga per Pelanggan), fase 3 · P3 (D-14).
 *
 * Keputusan pemilik D-14: pemilih PT di KEPALA aplikasi (`EntitySwitcher`) satu-satunya sumber. Dulu dua layar ini
 * punya pemilih PT lokal (`pl-entity-select`, `cpl-entity-select`) sehingga layar bisa menyunting harga PT A
 * sementara kepala bertuliskan PT B. Kini:
 *   · header = satu PT → PT itu;
 *   · header "Semua" & akun bisa berganti PT → "" (layar menampilkan `EntityRequiredNotice`, memilih PT di kartu =
 *     mengganti PT di header);
 *   · akun satu-PT (tidak bisa berganti, `canWrite` tetap true) → PT aktif pertama (perilaku lama, tak terpengaruh).
 */
import { useEntityScope } from "../../context/EntityScopeContext";

export const isActiveEntity = (e) => e && e.status !== "inactive" && e.status !== "archived";

export default function usePriceEntity(selectedEntity, entities = []) {
  const { canWrite } = useEntityScope();
  const header = selectedEntity && selectedEntity !== "all" ? selectedEntity : "";
  if (header) return header;
  return canWrite ? ((entities || []).find(isActiveEntity)?.id || "") : "";
}
