import { useState } from "react";
import { PackageCheck } from "lucide-react";
import FormModal from "../../components/FormModal";
import { KNSelect } from "../../components/KNSelect";
import { apiErrorText } from "../../utils/apiError";
import { receiveCut, receiveOrderCuts } from "./sampleApi";

// Hanya gudang yang boleh dipakai pemilik roll (bersama, atau khusus untuk PT itu).
export const destFor = (locs, owner) => (locs || []).filter((l) => !owner || l.sharing_mode !== "dedicated" || (l.entity_ids || []).includes(owner));

/**
 * CuttingReceiveDialog — terima hasil potong di tempat (Meja gelombang 1, Task 15).
 * row: baris antrean (ref_id = id tugas, order_id, number, warehouse_id, roll_owner_entity_id).
 * siblings: jumlah baris potong pesanan yang sama menunggu diterima (> 1 → boleh terima semuanya sekaligus).
 * Galat tampil di dalam pop-up; sukses → `onDone(pesan)` (toast + muat ulang oleh pemanggil).
 */
export default function CuttingReceiveDialog({ row, locations = [], siblings = 1, onClose, onDone, onChanged }) {
  const options = destFor(locations, row.roll_owner_entity_id).map((l) => ({ value: l.id, label: l.name }));
  const [dest, setDest] = useState(row.warehouse_id || "");
  const [all, setAll] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const kirim = async () => {
    if (busy) return;
    setBusy(true); setErr("");
    try {
      if (all) {
        const res = await receiveOrderCuts(row.order_id, dest);
        if ((res?.failed || []).length) {
          setErr(`${res.received} diterima; gagal: ${res.failed.map((f) => `${f.product_name} (${f.error})`).join("; ")}`);
          onChanged?.();
          return;
        }
        onDone?.(`${row.number}: ${res?.received ?? siblings} potongan diterima.`);
      } else {
        const res = await receiveCut(row.ref_id, dest);
        // FIX-3b (CUT-3, K-B2b-10) — lokasi Admin Cutting di gedung lain → transfer dibuat; roll tidak dipindah langsung.
        if (res?.transfer_required) onDone?.(res.message || `Transfer ${res.transfer?.code || ""} dibuat — terima lagi setelah barang tiba.`);
        else onDone?.(`${row.number}: hasil potong diterima.`);
      }
    } catch (e) {
      setErr(apiErrorText(e, all ? "Gagal menerima hasil potong pesanan ini." : "Gagal menerima hasil potong."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <FormModal open onClose={onClose} size="sm" icon={PackageCheck} title="Terima hasil potong"
      subtitle={[row.number, row.title].filter(Boolean).join(" · ")} testId="cutting-receive" busy={busy} error={err}
      footer={(
        <div className="flex justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose} disabled={busy}>Batal</button>
          <button type="button" data-testid="cutting-receive-submit" className="primary-button whitespace-nowrap"
            disabled={busy || !dest} onClick={kirim}>{busy ? "Memproses…" : "Terima hasil potong"}</button>
        </div>
      )}>
      <div className="space-y-3">
        <label className="grid gap-1 text-fs-13 text-kn-text">
          <span className="text-fs-12 text-kn-text-2">Lokasi tujuan</span>
          <KNSelect data-testid="cutting-dest" aria-label="Lokasi tujuan" className="field" value={dest}
            onValueChange={setDest} options={options} />
        </label>
        {siblings > 1 && (
          <label className="flex items-center gap-2 text-fs-13 text-kn-text">
            <input type="checkbox" data-testid="cutting-receive-all" checked={all} onChange={(e) => setAll(e.target.checked)} />
            {`Terima semua potongan ${row.number} (${siblings} baris)`}
          </label>
        )}
      </div>
    </FormModal>
  );
}
