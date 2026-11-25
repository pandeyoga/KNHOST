/**
 * CustomerQueuePanel (Meja gelombang 2, Task 8) — panel pop-up antrean `pelanggan_tanpa_sales` (Meja Admin Sales).
 * Baris ber-`ref_type` customer berarti dua hal di meja berbeda (pelanggan tanpa sales vs uang masuk), jadi panel ini
 * dikunci ke ANTREAN (`queue:pelanggan_tanpa_sales`), bukan ke jenis dokumen. Isi: fakta pelanggan dari baris
 * (kode · kota · PT · umur) + nama pelanggan sebagai tautan kartu pelanggan (teks biasa tanpa izin `customer.view`).
 * Aksi "Tetapkan sales" ada di kaki pop-up (`DeskRowDetail`).
 */
import { CustomerCardLink } from "../finance/cards/partyCards";
import { GenericPanel } from "./GenericDeskPanel";
import { permsOf } from "./deskPerms";

// Kode & nama sudah ada di judul pop-up; lencana/PT/umur di subjudul.
const DI_JUDUL = ["badge", "entity_id", "age"];

export default function CustomerQueuePanel({ row, queue, currentUser, testPrefix = "desk", pt = "" }) {
  const perms = permsOf(currentUser);
  return (
    <div className="grid gap-3" data-testid={`${testPrefix}-customer-panel`}>
      <div className="grid gap-0.5 sm:grid-cols-[10rem_1fr] sm:gap-3">
        <span className="text-fs-12 text-kn-text-2">Pelanggan</span>
        <span className="text-fs-13 text-kn-text">
          <CustomerCardLink id={row.ref_id} name={row.title} perms={perms} testId={`${testPrefix}-customer-card-link`} />
        </span>
      </div>
      <GenericPanel row={row} queue={queue} p={testPrefix} pt={pt} except={DI_JUDUL} />
    </div>
  );
}
