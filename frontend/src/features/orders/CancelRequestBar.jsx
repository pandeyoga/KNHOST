import { useState } from "react";
import { Hourglass } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatDateTime } from "../../utils/formatters";
import { can } from "../../config/roles";
import { alasanPersetujuan, rincianHasil } from "./cancelRequestUtil";

/** BTP-2/6 — bilah "menunggu persetujuan" di rincian pesanan: siapa mengajukan, alasan, kapan. Setujui/Tolak untuk
 *  pemegang `order.approve_cancel` (bukan pengaju; aturan nominal & sales pemilik ditegakkan server), Tarik untuk
 *  pengaju atau pemegang `order.cancel`. `userId` = id akun aktif (menyembunyikan tombol yang pasti ditolak server). */
export default function CancelRequestBar({ order, perms, userId = "", onDone }) {
  const req = order?.cancel_request;
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!req || req.status !== "pending") return null;

  const pengaju = Boolean(userId) && req.requested_by_id === userId;
  const bolehMemutus = can(perms, "order", "approve_cancel") && !pengaju;
  const bolehTarik = pengaju || can(perms, "order", "cancel");
  const jenis = req.action === "close_remaining" ? "tutup sisa" : "pembatalan";
  const alasan = alasanPersetujuan(req.approval_basis, order);

  // I3 — Setujui menjalankan aksinya: hasil eksekusi (`result` — titipan, galat titipan, dokumen pemenuhan) ikut
  // ditampilkan, sama dengan dialog batal/tutup sisa langsung.
  async function jalan(path, body, ok, denganHasil = false) {
    setBusy(true); setError("");
    try {
      const res = await (body === undefined ? axios.post(`${API}/sales-orders/${order.id}/cancel-request/${path}`)
        : axios.post(`${API}/sales-orders/${order.id}/cancel-request/${path}`, body));
      onDone?.(`${order.number}: ${ok}${denganHasil ? rincianHasil(res?.data?.result, req.action) : ""}`);
    } catch (e) { setError(apiErrorText(e, "Aksi gagal. Muat ulang lalu coba lagi.")); }
    finally { setBusy(false); }
  }

  return (
    <div className="notice-bar warning flex-col items-stretch gap-1.5" data-testid="cancel-request-bar">
      <div className="flex items-center gap-1.5 text-[12px] font-bold"><Hourglass size={13} /> Menunggu persetujuan {jenis}</div>
      <p className="text-[11px]">
        Diajukan {req.requested_by || "-"}{req.requested_at ? `, ${formatDateTime(req.requested_at)}` : ""}
        {Number(req.amount) > 0 ? ` · nilai ${formatCurrency(req.amount)}` : ""}.
        {" "}Alasan: {req.reason || "-"}.{alasan.length ? ` Perlu persetujuan karena ${alasan.join(" dan ")}.` : ""}
        {" "}Stok tetap dipesan dan pengiriman ditahan sampai diputus.
      </p>
      {error && <p className="text-[11px] text-[#9B1C1C]" data-testid="cancel-request-error">{error}</p>}
      {bolehMemutus && (
        <textarea data-testid="cancel-request-note" className="field w-full" rows={2}
          placeholder="Catatan keputusan (wajib bila menolak)" value={note} onChange={(e) => setNote(e.target.value)} />
      )}
      <div className="flex flex-wrap justify-end gap-2">
        {bolehMemutus && (
          <>
            <button data-testid="cancel-request-reject" className="secondary-button text-red-600"
              disabled={busy || note.trim().length < 1}
              onClick={() => jalan("decision", { decision: "reject", note: note.trim() }, "permintaan ditolak, pesanan berjalan seperti biasa.")}>
              Tolak
            </button>
            <button data-testid="cancel-request-approve" className="primary-button" disabled={busy}
              onClick={() => jalan("decision", { decision: "approve", note: note.trim() }, `permintaan ${jenis} disetujui dan dijalankan.`, true)}>
              Setujui
            </button>
          </>
        )}
        {bolehTarik && (
          <button data-testid="cancel-request-withdraw" className="secondary-button" disabled={busy}
            onClick={() => jalan("withdraw", undefined, "permintaan ditarik, pesanan berjalan seperti biasa.")}>
            Tarik
          </button>
        )}
      </div>
    </div>
  );
}
