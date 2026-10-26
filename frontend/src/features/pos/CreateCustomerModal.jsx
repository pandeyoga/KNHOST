import { useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";
import CustomerFormModal from "../crm/CustomerFormModal";

/**
 * CreateCustomerModal — "Pelanggan Baru" dari POS / checkout / aplikasi HP sales.
 *
 * Fase 3 · P3 (D-05, keputusan pemilik): dulu quick-add 5 isian (nama, PIC, HP, wilayah, jalan) dengan kebijakan
 * lot, segmen, tim sales & profil bayar "diatur nanti di Manajemen Pelanggan" — dan akun non-sales (admin/manajer)
 * selalu ditolak server karena tidak bisa memilih sales penanggung jawab. Kini PEMBUNGKUS tipis
 * `crm/CustomerFormModal` (form LENGKAP yang sama dengan CRM; di HP layar penuh 1 kolom), `variant="pos"`.
 *
 * Props: `open` · `onClose` · `user` · `selectedEntity` (pelanggan lahir di PT header; kosong = PT aktif server)
 *   · `onCreated(customer)` — pelanggan yang SUDAH tersimpan (mis. langsung dipilih di keranjang)
 *   · `onCreateCustomer` — nama lama (kompatibel): dipanggil dengan pelanggan yang sudah tersimpan bila
 *     `onCreated` tidak diberikan; `useAppActions.createCustomer` mengenali objek ber-`id` dan hanya memilihnya.
 *   · `testId` (bawaan "create-customer": pop-up, `-body`, `-close`, `-missing`, `-error` sama dengan testid lama;
 *     tombol simpan `create-customer-button`).
 */
export default function CreateCustomerModal({
  open, onClose, onCreated, onCreateCustomer, user = null, selectedEntity = "all", testId = "create-customer",
}) {
  const [salesUsers, setSalesUsers] = useState([]);

  // Daftar sales untuk "Sales penanggung jawab" (non-sales) & tim co-sales — sumber sama dengan CRM (ikut PT).
  useEffect(() => {
    if (!open) return undefined;
    let live = true;
    const params = selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {};
    axios.get(`${API}/sales-users`, { params })
      .then((r) => { if (live) setSalesUsers(Array.isArray(r.data) ? r.data : []); })
      .catch(() => { /* non-blocking: sales tetap bisa membuat pelanggan miliknya */ });
    return () => { live = false; };
  }, [open, selectedEntity]);

  const done = onCreated || onCreateCustomer;
  return (
    <CustomerFormModal open={open} editTarget={null} currentUser={user} salesUsers={salesUsers}
      selectedEntity={selectedEntity} variant="pos" testId={testId} submitTestId="create-customer-button"
      onClose={onClose}
      onSaved={async (customer) => { await done?.(customer); onClose?.(); }} />
  );
}
