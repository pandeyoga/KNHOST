/**
 * FASE G-7 ↔ G-8 · US8 — **bayar kontrabon dari baris mutasi bank**.
 *
 * Alurnya sengaja dibalik dari kebiasaan: petugas melihat uang KELUAR di rekening,
 * lalu menunjuk kontrabon mana yang dilunasinya. Sistem membuat transaksi kasnya,
 * membayar kontrabon, lalu MENAUTKAN barisnya — rekonsiliasi langsung beres tanpa
 * pindah layar. Kandidat diurutkan: nominal tepat lebih dulu.
 *
 * INV-UI-03 aturan C: modal ini menulis lewat axios, jadi punya bilah error sendiri.
 *
 * Fase 4 · R2 (L-03) — `.modal-card` buatan sendiri → `FormModal` baku (layar penuh di HP). "Bayar & tautkan"
 * membayar kontrabon (uang keluar) → kini dikonfirmasi dulu lewat `askConfirm` (P-01). Testid tetap.
 */
import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Receipt, CheckCircle2 } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { formatCurrency } from "../../../utils/formatters";
import ErrorNotice from "../../../components/ErrorNotice";
import FormModal from "../../../components/FormModal";
import { askConfirm } from "../../../services/confirmService";
import { apiErrorText } from "../../../utils/apiError";

const fmtDate = (s) => {
  if (!s) return "—";
  try {
    return new Date(String(s).length <= 10 ? `${s}T00:00:00` : s)
      .toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "2-digit" });
  } catch { return s; }
};

export default function ReconContraBonModal({ line, onClose, onDone, onError }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState("load");
  const [mErr, setMErr] = useState("");

  const load = useCallback(async () => {
    setBusy("load");
    try {
      const r = await axios.get(`${API}/contra-bons/bank-line-candidates/${line.id}`);
      setData(r.data);
      setMErr("");
    } catch (e) { setMErr(apiErrorText(e)); onError?.(e); } finally { setBusy(""); }
  }, [line.id, onError]);

  useEffect(() => { load(); }, [load]);

  async function pay(cb) {
    if (!(await askConfirm({
      title: `Bayar kontrabon ${cb.number}?`,
      message: `${cb.supplier_name || "Supplier"} dibayar ${formatCurrency(line.amount)} dari mutasi ini; sistem membuat `
        + "transaksi kas keluar dan menautkan baris mutasinya.",
      confirmLabel: "Bayar & tautkan",
    }))) return;
    setBusy(cb.id);
    try {
      const r = await axios.post(`${API}/contra-bons/${cb.id}/pay-from-bank-line/${line.id}`, {
        note: "Dibayar dari baris mutasi bank",
      });
      const updated = r.data || {};
      onDone(`Kontrabon ${updated.number || cb.number} dibayar `
        + `${formatCurrency(line.amount)} dan baris mutasi ini otomatis tertaut ke transaksi kasnya`
        + (updated.status === "paid" ? " — kontrabon LUNAS." : "."));
    } catch (e) { setMErr(apiErrorText(e)); onError?.(e); } finally { setBusy(""); }
  }

  const cands = data?.candidates || [];

  return (
    <FormModal open onClose={onClose} size="lg" icon={Receipt} title="Bayar kontrabon dari mutasi ini"
      subtitle={(
        <>
          {fmtDate(line.stmt_date)} · dana keluar <b>{formatCurrency(line.amount)}</b> —{" "}
          {line.description || "tanpa keterangan"}
        </>
      )}
      testId="recon-contrabon-modal" busy={!!busy && busy !== "load"}>
      {mErr && (
        <ErrorNotice message={mErr} onRetry={load} onDismiss={() => setMErr("")}
          testId="recon-contrabon-error" />
      )}
      <p className="text-[11px] text-[#8E8E93]">
        Hanya kontrabon yang sudah <b>disetujui</b> atau <b>dijadwalkan bayar</b> dan masih
        punya sisa yang bisa dilunasi dari sini.
      </p>

      <div className="mt-2 rounded border border-[#EFF0F2] sm:max-h-[340px] sm:overflow-auto">
        {busy === "load"
          ? (
            <div className="p-4 text-center text-[12px] text-[#8E8E93]">
              <RefreshCw size={14} className="spin inline" /> Mencari kontrabon yang pantas…
            </div>
          )
          : cands.length === 0
            ? (
              <div className="p-4 text-center text-[12px] text-[#8E8E93]"
                data-testid="recon-contrabon-empty">
                Tidak ada kontrabon yang siap dibayar. Setujui kontrabonnya lebih dulu di
                Pembelian → Hutang Supplier → Kontrabon.
              </div>
            )
            : cands.map((c) => (
              <div key={c.id} data-testid={`recon-cb-cand-${c.id}`}
                className="border-b border-[#F5F5F7] px-3 py-2 last:border-0">
                <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5">
                  <div className="min-w-0">
                    <p className="truncate text-[12px]">
                      <b>{c.number}</b> · {c.supplier_name}{" "}
                      <span className="text-[#8E8E93]">({c.bills_count} faktur)</span>
                    </p>
                    <p className="text-[10px] text-[#8E8E93]">
                      {c.status_label} · sisa {formatCurrency(c.outstanding)}
                      {c.planned_payment_date ? ` · rencana ${fmtDate(c.planned_payment_date)}` : ""}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                      c.exact ? "bg-[#EAF7EE] text-[#1B7F4B]" : "bg-[#FFF4E5] text-[#B26A00]"}`}>
                      {c.exact ? "nominal tepat" : `selisih ${formatCurrency(c.amount_diff)}`}
                    </span>
                    <button data-testid={`recon-cb-pay-${c.id}`} className="primary-button"
                      disabled={!!busy} onClick={() => pay(c)}>
                      {busy === c.id
                        ? <RefreshCw size={13} className="spin" />
                        : <CheckCircle2 size={13} />}
                      Bayar & tautkan
                    </button>
                  </div>
                </div>
              </div>
            ))}
      </div>
    </FormModal>
  );
}
