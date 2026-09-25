/** Unduh Kartu Warna Pelanggan (PDF) — dipakai tab Warna Pelanggan & profil pelanggan CRM. */
import axios, { API } from "../../services/apiClient";

export async function downloadColorCard(customerId, customerName) {
  const r = await axios.get(`${API}/color-library/customer-colors/${customerId}/card`, { responseType: "blob" });
  const url = URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `kartu-warna-${(customerName || customerId).replace(/\s+/g, "-").toLowerCase()}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

export async function blobError(e, fallback) {
  const d = e?.response?.data;
  if (d instanceof Blob) {
    try { return JSON.parse(await d.text()).detail || fallback; } catch { return fallback; }
  }
  return d?.detail || fallback;
}
