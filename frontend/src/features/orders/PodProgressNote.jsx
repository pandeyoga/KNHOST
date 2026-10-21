/**
 * F-06 (keputusan owner Q-01a) — SO "Dikirim": tampilkan berapa Surat Jalan yang sudah ber-bukti terima (POD).
 * SO tertutup otomatis begitu semua SJ ber-POD di Logistik; tombol manual tetap untuk SO tanpa alur Logistik.
 */
import { useEffect, useState } from "react";
import { PackageCheck } from "lucide-react";
import axios, { API } from "../../services/apiClient";

export default function PodProgressNote({ orderId }) {
  const [p, setP] = useState(null);
  useEffect(() => {
    if (!orderId) return undefined;
    let live = true;
    axios.get(`${API}/sales-orders/${orderId}/pod-progress`).then((r) => { if (live) setP(r.data); }).catch(() => {});
    return () => { live = false; };
  }, [orderId]);
  if (!p || !p.total) return null;
  return (
    <div className="flex items-start gap-2 rounded-md border border-[#D6E4FF] bg-[#F2F7FF] px-2.5 py-1.5 text-[11px] text-[#0B3D91]"
         data-testid="order-pod-progress">
      <PackageCheck size={13} className="mt-0.5 shrink-0" />
      <span>
        Bukti terima (POD): <b data-testid="order-pod-count">{p.with_pod} dari {p.total}</b> Surat Jalan.
        {" "}Pesanan tertutup otomatis saat semua Surat Jalan ber-POD di Logistik.
        {p.missing?.length > 0 && <> Belum: {p.missing.join(", ")}.</>}
      </span>
    </div>
  );
}
