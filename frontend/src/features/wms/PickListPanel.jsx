/**
 * Cek UI UAT v3 (2026-10-21) — "Roll yang harus diambil" di panel Ambil & Kirim (Barang Keluar).
 * Dulu panel hanya punya kolom scan: staf harus mencetak Surat Pengambilan Barang di layar lain untuk tahu roll mana.
 * Kini roll teralokasi tampil (nomor, LOT, lokasi, panjang, sudah diambil/belum) + reservasi potong yang belum dipotong;
 * [Ambil] mengisi kolom scan dengan roll itu. Surat Pengambilan Barang tetap bisa dicetak dari sini.
 */
import { useEffect, useState } from "react";
import { CheckCircle2, Scissors } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { formatQty } from "../../utils/formatters";
import DocumentActionsBar from "../documents/DocumentActionsBar";

export default function PickListPanel({ task, onPick }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    if (!task?.id) return undefined;
    let live = true;
    axios.get(`${API}/outbound/tasks/${task.id}/pick-list`).then((r) => { if (live) setData(r.data); }).catch(() => setData(null));
    return () => { live = false; };
  }, [task?.id, task?.picked_qty]);
  if (!data) return null;
  const rolls = data.rolls || [];
  const cuts = data.pending_cuts || [];
  return (
    <div className="rounded-lg border border-[#EFF0F2] p-2" data-testid="outbound-pick-list">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <span className="text-[10.5px] font-bold uppercase tracking-wide text-[#6B6B73]">Roll yang harus diambil</span>
        {task.order_id && (
          <DocumentActionsBar docType="picking_list" sourceId={task.order_id} number={task.order_number}
                              label="Surat Pengambilan Barang" compact autoCheckSignature={false} />
        )}
      </div>
      {cuts.length > 0 && (
        <p className="mb-1 flex items-center gap-1 rounded bg-[#FFF7EC] px-2 py-1 text-[10.5px] text-[#8C4A00]" data-testid="outbound-pick-cuts">
          <Scissors size={11} /> Potong dulu: {cuts.map((c) => `${c.roll_no} (${formatQty(c.qty)} ${data.unit})`).join(", ")}
        </p>
      )}
      {rolls.length === 0 ? (
        <p className="text-[10.5px] text-[#8E8E93]">Belum ada roll teralokasi di gudang ini.</p>
      ) : (
        <ul className="divide-y divide-[#F2F3F5]">
          {rolls.map((r) => (
            <li key={r.id} className="flex items-center justify-between gap-2 py-1 text-[11px]" data-testid={`outbound-pick-roll-${r.roll_no}`}>
              <span>
                <b>{r.roll_no}</b> · LOT {r.lot || "—"} · lokasi {r.bin_code || r.location_code || r.bin_id || "—"} · {formatQty(r.length_remaining)} {r.unit || data.unit}
              </span>
              {r.picked ? (
                <span className="inline-flex items-center gap-1 text-[10.5px] font-semibold text-[#1B7F4B]"><CheckCircle2 size={11} /> sudah diambil</span>
              ) : (
                <button type="button" className="secondary-button !py-0.5 !text-[10.5px]" data-testid={`outbound-pick-take-${r.roll_no}`}
                        onClick={() => onPick?.(r.roll_no)}>Ambil</button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
