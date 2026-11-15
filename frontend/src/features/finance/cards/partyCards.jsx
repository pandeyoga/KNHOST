/**
 * partyCards (MN-T3) — pembuka bersama **kartu pelanggan** dan **kartu pemasok** (pop-up rincian di atas layar mana pun).
 *
 *  · `PartyCardHost` — dipasang SEKALI di `AppViewRouter` (di dalam `AppNavProvider`): membaca `useAppNav().card` dan
 *    merender `Customer360Panel`/`Supplier360Panel` varian "card" di `PartyCardDrawer`.
 *  · `openCustomerCard(id)` / `openSupplierCard(id)` dari `useAppNav()` membuka kartu dari baris mana pun (nama pelanggan
 *    di tab Piutang, Beranda Keuangan, detail pesanan; nama pemasok di Hutang › Tagihan & Kontrabon, detail PO).
 *  · `CustomerCardLink` / `SupplierCardLink` — nama sebagai tautan pembuka kartu; tanpa izin lihat (`customer.view` /
 *    `supplier.view`) atau di luar penyedia navigasi → teks biasa (bukan tombol mati).
 *  · `DocPill` — status dokumen = ikon + teks + warna (kelas `status-*` yang ADA di `styles/components.css`).
 *  · `SectionState` — memuat / galat "Bagian ini tidak bisa dimuat. Coba lagi." / kosong "Belum ada data." per bagian.
 *
 * Kartu adalah panel samping, BUKAN tab hub: bagian-bagiannya memakai chip (`FilterChips`), sehingga tidak menjadi tab
 * tingkat ketiga (INV-UI-14).
 */
import { lazy, Suspense } from "react";
import { AlertTriangle, CheckCircle2, CircleDashed, Clock3, Send, XCircle } from "lucide-react";
import DetailModal from "../../../components/DetailModal";
import { useAppNav } from "../../../context/AppNavContext";
import { can } from "../../../config/roles";
import ErrorNotice from "../../../components/ErrorNotice";
import { docStatusLabel } from "../../../utils/docStatus";

const Customer360Panel = lazy(() => import("../../crm/Customer360Panel"));
const Supplier360Panel = lazy(() => import("../../purchasing/Supplier360Panel"));

export const TEKS_GALAT_BAGIAN = "Bagian ini tidak bisa dimuat. Coba lagi.";
export const TEKS_KOSONG_BAGIAN = "Belum ada data.";

const TONE = {
  paid: ["status-paid", CheckCircle2], done: ["status-done", CheckCircle2], lunas: ["status-paid", CheckCircle2],
  posted: ["status-shipped", Send], approved: ["status-approved", Send], scheduled: ["status-shipped", Clock3],
  verified: ["status-approved", Send], applied: ["status-shipped", Send], open: ["status-pending", Clock3],
  in_progress: ["status-pending", Clock3], issued: ["status-shipped", Send], partial: ["status-pending", Clock3],
  pending_approval: ["status-pending", Clock3], submitted: ["status-pending", Clock3], disputed: ["status-rejected", AlertTriangle],
  draft: ["status-draft", CircleDashed], cancelled: ["status-cancelled", XCircle], rejected: ["status-rejected", XCircle],
  waived: ["status-draft", CircleDashed], void: ["status-cancelled", XCircle], resolved: ["status-done", CheckCircle2],
};

export function DocPill({ status, label, testId }) {
  const [cls, Icon] = TONE[String(status || "").toLowerCase()] || ["status-draft", CircleDashed];
  return (
    <span className={`status-pill ${cls} inline-flex items-center gap-1`} data-testid={testId}>
      <Icon size={12} aria-hidden="true" />{label || docStatusLabel(status)}
    </span>
  );
}

export function SectionState({ loading, error, empty, onRetry, testId, children }) {
  if (error) return <ErrorNotice message={TEKS_GALAT_BAGIAN} onRetry={onRetry} testId={`${testId}-error`} />;
  if (loading) return <p className="py-4 text-center text-fs-12 text-kn-text-2" role="status" data-testid={`${testId}-loading`}>Memuat…</p>;
  if (empty) return <p className="py-4 text-center text-fs-12 text-kn-text-2" data-testid={`${testId}-empty`}>{TEKS_KOSONG_BAGIAN}</p>;
  return children;
}

/** Wadah kartu = pop-up rincian baku `DetailModal` (Esc, klik latar INV-UI-01, kunci gulir, layar penuh ≤ 640 px).
 *  Lebar `lg` = 896 px (isi 864 px sesudah bantalan) di layar 1024 dan 1280 px. */
export function PartyCardDrawer({ open = true, onClose, label = "Kartu", testId = "party-card", children }) {
  return (
    <DetailModal open={open} onClose={onClose} size="lg" framed label={label} testId={testId}>
      {children}
    </DetailModal>
  );
}

export function PartyCardHost({ currentUser, selectedEntity }) {
  const { card, closeCard } = useAppNav();
  if (!card) return null;
  const isCustomer = card.type === "customer";
  return (
    <PartyCardDrawer onClose={closeCard} label={isCustomer ? "Kartu pelanggan" : "Kartu pemasok"}
      testId={isCustomer ? "customer-card" : "supplier-card"}>
      <Suspense fallback={<p className="py-6 text-center text-fs-12 text-kn-text-2">Memuat kartu…</p>}>
        {isCustomer ? (
          <Customer360Panel key={`${card.id}-${card.nonce}`} variant="card" customerId={card.id} currentUser={currentUser}
            salesUsers={[]} selectedEntity={selectedEntity} onBack={closeCard} />
        ) : (
          <Supplier360Panel key={`${card.id}-${card.nonce}`} variant="card" supplierId={card.id} currentUser={currentUser}
            selectedEntity={selectedEntity} onBack={closeCard} />
        )}
      </Suspense>
    </PartyCardDrawer>
  );
}

function CardLink({ id, name, kind, perms, testId, className = "" }) {
  const nav = useAppNav();
  const resource = kind === "customer" ? "customer" : "supplier";
  const open = kind === "customer" ? nav.openCustomerCard : nav.openSupplierCard;
  if (!id || !nav.cardsEnabled || !can(perms, resource, "view")) {
    return <span className={className} data-testid={testId ? `${testId}-text` : undefined}>{name || "—"}</span>;
  }
  return (
    <button type="button" className={`link-button text-left ${className}`.trim()} data-testid={testId}
      title={kind === "customer" ? "Buka kartu pelanggan" : "Buka kartu pemasok"}
      onClick={(e) => { e.stopPropagation(); open(id); }}>
      {name || "—"}
    </button>
  );
}

export const CustomerCardLink = (p) => <CardLink {...p} kind="customer" />;
export const SupplierCardLink = (p) => <CardLink {...p} kind="supplier" />;
