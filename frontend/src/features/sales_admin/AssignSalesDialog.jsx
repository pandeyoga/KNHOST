import { useEffect, useState } from "react";
import { UserCog } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import { apiErrorText } from "../../utils/apiError";
import { CONTOH_ALASAN, TEKS_GAGAL_PINDAH, TEKS_PILIH_SALES, reassignCustomer, salesTujuanOptions } from "../crm/customerReassign";

/**
 * AssignSalesDialog — tetapkan sales penanggung jawab pelanggan DI MEJA (Meja gelombang 2, Task 8).
 * customer: { id, name, assigned_sales_id?, entity_id? }. Pemanggil hanya memasangnya bila pengguna memegang
 * `sales_force.assign` (izin server `POST /customers/{id}/reassign`). Daftar sales = `GET /sales-users` (ikut PT pelanggan).
 * Pilihan sales wajib; alasan wajib di meja (kartu pelanggan menjadikannya opsional). Galat tampil di dalam pop-up
 * (`<testId>-error`); sukses → `onDone(pesan)`.
 */
export default function AssignSalesDialog({ customer, onClose, onDone, testId = "assign-sales-dialog" }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sid, setSid] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    let aktif = true;
    const params = customer?.entity_id ? { entity_id: customer.entity_id } : undefined;
    axios.get(`${API}/sales-users`, params ? { params } : undefined)
      .then((r) => { if (aktif) setUsers(Array.isArray(r?.data) ? r.data : []); })
      .catch((e) => { if (aktif) setErr(apiErrorText(e, "Daftar sales tidak bisa dimuat.")); })
      .finally(() => { if (aktif) setLoading(false); });
    return () => { aktif = false; };
  }, [customer?.id, customer?.entity_id]);

  const kirim = async () => {
    if (busy) return;
    if (!sid) { setErr(TEKS_PILIH_SALES); return; }
    setBusy(true); setErr("");
    try {
      await reassignCustomer(customer.id, { assigned_sales_id: sid, reason: reason.trim() });
      onDone?.(`${customer.name || "Pelanggan"} ditetapkan ke ${users.find((u) => u.id === sid)?.name || "sales baru"}.`);
    } catch (e) { setErr(apiErrorText(e, TEKS_GAGAL_PINDAH)); }
    finally { setBusy(false); }
  };

  return (
    <FormModal open onClose={onClose} size="sm" icon={UserCog} title="Tetapkan sales"
      subtitle={customer?.name || ""} testId={testId} busy={busy} error={err}
      submitLabel={busy ? "Menyimpan…" : "Tetapkan"} submitDisabled={loading} onSubmit={kirim}>
      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-fs-12 font-medium text-kn-text-2">Sales penanggung jawab</label>
          <KNSelect value={sid} onValueChange={setSid} className="field" data-testid="assign-sales-select"
            placeholder={loading ? "Memuat sales…" : "Pilih sales tujuan"} options={salesTujuanOptions(users, customer?.assigned_sales_id)} />
        </div>
        <div>
          <label className="mb-1 block text-fs-12 font-medium text-kn-text-2" htmlFor={`${testId}-alasan`}>Alasan (opsional)</label>
          <input id={`${testId}-alasan`} data-testid="assign-sales-reason" value={reason} onChange={(e) => setReason(e.target.value)}
            className="field" placeholder={CONTOH_ALASAN} />
        </div>
      </div>
    </FormModal>
  );
}
