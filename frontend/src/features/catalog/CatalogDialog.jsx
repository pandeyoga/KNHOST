import FormModal from "../../components/FormModal";

/**
 * CatalogDialog — pop-up katalog (Tambah varian, SKU baru/ubah, Tautkan SKU lama).
 *
 * Fase 4 · R4 (L-03) — kini pembungkus tipis `FormModal` baku (dulu dialog Radix sendiri z-210 dengan kepala
 * berbeda): Esc/klik latar lewat tumpukan lapisan bersama, layar penuh 1 kolom di HP, rupa kepala sama dengan pop-up
 * lain. Isi (form + tombol) tetap milik pemanggil — FormModal tanpa `onSubmit` supaya tidak ada form di dalam form.
 * Testid `${testId}`, `${testId}-title`, `${testId}-close` tetap.
 */
export const CatalogDialog = ({ title, children, onClose, busy = false, testId = "catalog-dialog", icon = null, size = "lg" }) => (
  <FormModal open onClose={onClose} busy={busy} title={title} icon={icon} size={size} testId={testId}>
    {children}
  </FormModal>
);
