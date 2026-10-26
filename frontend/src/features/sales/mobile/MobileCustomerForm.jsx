import { useEffect, useState } from "react";
import axios, { API } from "../../../services/apiClient";
import CustomerFormModal from "../../crm/CustomerFormModal";

/**
 * Tambah / ubah pelanggan dari HP — fase 3 · P7 (D-05 HP, keputusan pemilik "form input HP tidak diringkas").
 *
 * Dulu form HP sendiri 6 isian (nama, PIC, HP, email, wilayah, jalan; "segmen, kebijakan lot & limit kredit bisa
 * dilengkapi nanti") untuk TAMBAH dan lembar 5 isian untuk UBAH. Kini PEMBUNGKUS tipis `crm/CustomerFormModal` — form
 * LENGKAP yang sama dengan Manajemen Pelanggan desktop (segmen, sales penanggung jawab & tim, kebijakan lot, profil
 * bayar, limit kredit, NPWP, alamat terstruktur); di HP FormModal tampil layar penuh 1 kolom.
 *
 * Props: `user` · `selectedEntity` · `customer` (ada = mode ubah) · `onClose` · `onCreated(customer)` (tambah)
 *   · `onSaved(customer)` (ubah). Testid: pop-up `m-customer-form` (`-body`, `-missing`, `-error`, `-cancel`),
 *   tombol simpan `m-customer-form-submit`.
 */
export default function MobileCustomerForm({ user, selectedEntity, customer = null, onClose, onCreated, onSaved }) {
  // Daftar sales untuk "Sales penanggung jawab" (akun non-sales) & tim co-sales — sumber sama dengan CRM (ikut PT).
  const [salesUsers, setSalesUsers] = useState([]);
  useEffect(() => {
    let live = true;
    const params = selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {};
    axios.get(`${API}/sales-users`, { params })
      .then((r) => { if (live) setSalesUsers(Array.isArray(r.data) ? r.data : []); })
      .catch(() => { /* tidak menghalangi: sales tetap bisa menyimpan pelanggan miliknya */ });
    return () => { live = false; };
  }, [selectedEntity]);
  return (
    <CustomerFormModal open editTarget={customer} currentUser={user} salesUsers={salesUsers} selectedEntity={selectedEntity}
      testId="m-customer-form" submitTestId="m-customer-form-submit" onClose={onClose}
      onSaved={(c, isEdit) => { if (isEdit) onSaved?.(c); else onCreated?.(c); }} />
  );
}
