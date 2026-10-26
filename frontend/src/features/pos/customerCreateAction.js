/**
 * customerCreateAction — aksi "Pelanggan Baru" untuk POS/checkout/aplikasi HP (diekstrak dari `hooks/useAppActions.js`,
 * fase 3 · P3 D-05, supaya hook itu tidak makin panjang).
 *
 * D-05: "Pelanggan Baru" kini memakai form LENGKAP `crm/CustomerFormModal` (lewat `pos/CreateCustomerModal`) yang
 * MENYIMPAN SENDIRI. Pemanggil itu menyerahkan pelanggan yang sudah tersimpan (ber-`id`) → di sini cukup dipilih di
 * keranjang + daftar dimuat ulang. Jalur lama (objek form tanpa `id`) tetap ada untuk kompatibilitas.
 */
import axios, { API } from "../../services/apiClient";

export function makeCreateCustomer({ entityValue, setSelectedCustomer, setSelectedAddress, setNotice, loadAll }) {
  return async (form) => {
    if (form?.id) {
      setSelectedCustomer(form);
      setSelectedAddress((form.addresses || []).find((a) => a.is_primary)?.id || form.addresses?.[0]?.id || "");
      setNotice(`Pelanggan ${form.name} aktif dan siap dipakai.`);
      try { await loadAll(); } catch { /* daftar dimuat ulang pada siklus berikutnya */ }
      return form;
    }
    if (!form.name || !form.pic_name || !form.phone || !form.city || !form.address) {
      setNotice("Lengkapi data customer baru terlebih dahulu.");
      return undefined;
    }
    if ((form.country_code || "ID") === "ID" && (!form.province_code || !form.city_code || !form.postal_code)) {
      setNotice("Alamat belum lengkap: pilih provinsi, kota/kabupaten, dan kode pos yang valid.");
      return undefined;
    }
    try {
      const response = await axios.post(`${API}/customers`, { ...form, entity_id: entityValue });
      setSelectedCustomer(response.data);
      setSelectedAddress(response.data.addresses[0].id);
      setNotice(`Customer ${response.data.name} aktif dan siap dipakai.`);
      await loadAll();
      return response.data;
    } catch (error) {
      setNotice(error.response?.data?.detail || "Gagal membuat customer.");
      return undefined;
    }
  };
}
