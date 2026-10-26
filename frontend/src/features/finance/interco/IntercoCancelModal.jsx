/**
 * FASE G-6 — **BATALKAN TRANSAKSI ANTAR-PT** (wajib ber-alasan).
 *
 * Kenapa ada layar sendiri: transaksi yang sudah dikonfirmasi punya jurnal di DUA
 * buku. Membatalkannya berarti **menerbitkan jurnal pembalik** — dan itu tidak
 * boleh terjadi tanpa sebab yang tercatat (pola G-1: koreksi ber-alasan).
 *
 * Fase 3 · P4 (L-03) — overlay `fixed inset-0` buatan sendiri → `FormModal` baku (Esc/klik latar lewat tumpukan
 * lapisan, layar penuh di HP). Isian & tombol (merah = aksi berdampak) tidak berubah.
 */
import { useState } from "react";
import { Undo2, AlertTriangle } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import FormModal from "../../../components/FormModal";
import { apiErrorText } from "../../../utils/apiError";
import { formatCurrency } from "../../../utils/formatters";

export default function IntercoCancelModal({ doc, onClose, onCancelled }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  if (!doc) return null;

  const perluAlasan = doc.status !== "draft";
  const kurang = perluAlasan && reason.trim().length < 5;

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const r = await axios.post(
        `${API}/interco/transactions/${doc.id}/cancel`, { note: reason.trim() });
      onCancelled?.(r.data);
    } catch (e) {
      setErr(apiErrorText(e));
    } finally { setBusy(false); }
  };

  return (
    <FormModal open onClose={onClose} size="sm" icon={Undo2} testId="interco-cancel-modal" busy={busy}
      title={perluAlasan ? "Batalkan Transaksi Antar-PT" : "Batalkan Draf Antar-PT"}
      subtitle={`${doc.number} · ${formatCurrency(doc.grand_total)}`}
      footer={(
        <div className="flex items-center justify-end gap-2">
          <button type="button" onClick={onClose} data-testid="interco-cancel-abort" className="secondary-button"
            disabled={busy}>
            Tidak, kembali
          </button>
          <button type="button" onClick={submit} disabled={busy || kurang} data-testid="interco-cancel-submit"
            className="danger-button">
            {/* UAT 24 Okt (audit UI tahap 2) — G1-29: draf belum berjurnal → tidak menyebut "balik jurnal". */}
            {busy ? "Membatalkan…" : perluAlasan ? "Batalkan & Balik Jurnal" : "Batalkan Draf"}
          </button>
        </div>
      )}>
      <div className="space-y-3">
        {!perluAlasan && (
          <p className="text-[12px] text-[#6E6E73]" data-testid="interco-cancel-draft-note">
            Dokumen masih draf — belum ada jurnal, jadi tidak ada yang dibalik.
          </p>
        )}
        {perluAlasan && (
          <div className="flex items-start gap-2 rounded-lg bg-[#FFF7E6] border border-[#FFE1A8] px-3 py-2.5 text-[12px] text-[#8A5A00]">
            <AlertTriangle size={14} className="mt-0.5 shrink-0" />
            <span>
              Transaksi ini sudah dikonfirmasi, jadi jurnalnya akan <b>dibalik di kedua
              buku PT</b> (pendapatan, piutang &amp; utang antar-PT kembali nol) dan
              entri eliminasi grup ikut dihapus. Alasan wajib dicatat.
            </span>
          </div>
        )}
        <div>
          <label className="block text-xs font-medium text-[#3C3C43] mb-1">
            Alasan pembatalan {perluAlasan ? <span className="text-[#C0392B]">*</span> : <span className="text-[#8E8E93]">(opsional)</span>}
          </label>
          <textarea
            data-testid="interco-cancel-reason"
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Contoh: salah PT pembeli — diterbitkan ulang ke CV Kanda"
            className="textarea w-full"
          />
          {kurang && (
            <p className="text-[11px] text-[#C0392B] mt-1">
              Minimal 5 huruf supaya jejak koreksinya berguna saat diaudit.
            </p>
          )}
        </div>
        {err && (
          <div data-testid="interco-cancel-error"
               className="rounded-lg bg-[#FDEDE7] border border-[#F7C3B4] text-[#9B1C1C] text-[12px] px-3 py-2">
            {err}
          </div>
        )}
      </div>
    </FormModal>
  );
}
