/**
 * ReturnStepper — peta alur retur jual dalam satu baris (2026-06; 23 Okt: 5 langkah).
 *
 * Aturan alurnya (dari `services/return_service.py` + `return_state.py`):
 *   draft → pending_approval → approved → inspecting → inspected
 *         → settle (refund / store credit / nego)  |  rejected / cancelled.
 * 23 Okt (permintaan pemilik) — "Pengembalian barang" jadi langkah sendiri antara ACC dan QC: status dokumen
 * tetap `approved`/`inspecting`, tetapi langkahnya DIBACA dari data nyata (sudah dikirim/dijemput? berapa roll
 * sudah discan terima?). QC per roll dikerjakan di SPK (menu Kualitas).
 */
import { Check, X } from "lucide-react";
import { receiptOf } from "./ReturnShipmentPanel";

const STEPS = [
  { key: "draft", label: "Draf", hint: "Lengkapi roll, alasan & foto per roll, lalu kirim untuk persetujuan." },
  { key: "approval", label: "Persetujuan", hint: "Terima/tolak per roll, lalu Manajer menyetujui." },
  { key: "return", label: "Pengembalian barang", hint: "Barang dikirim/dijemput dari pelanggan lalu discan terima gudang per roll." },
  { key: "inspection", label: "QC per roll", hint: "Petugas QC memeriksa tiap roll di SPK (menu Kualitas)." },
  { key: "settlement", label: "Penyelesaian", hint: "Pilih outcome: refund, store credit, atau nego." },
];

export function returnStage(ret) {
  const status = ret?.status;
  if (status === "draft") return 0;
  if (status === "pending_approval") return 1;
  if (status === "approved" || status === "inspecting") return receiptOf(ret).complete ? 3 : 2;
  if (status === "inspected") return 4;
  if (["refund_settled", "credit_settled", "nego_settled"].includes(status)) return 5;
  return 0;
}

function nextHint(ret) {
  const st = ret.status;
  if (st === "draft") return "Langkah berikutnya: kirim untuk persetujuan.";
  if (st === "pending_approval") return "Langkah berikutnya: putuskan per roll (Terima/Tolak) lalu Setujui / Tolak.";
  if (st === "approved" || st === "inspecting") {
    const r = receiptOf(ret);
    if (!r.complete) {
      if (!ret.shipped_to_store_at) return "Langkah berikutnya: catat cara barang kembali & tandai saat dikirim/dijemput (panel Pengembalian barang).";
      return `Barang dalam perjalanan — gudang scan terima tiap roll saat tiba${r.rolls.length ? ` (${r.received}/${r.rolls.length} diterima)` : ""}.`;
    }
    if (!ret.inspection_id) return "Langkah berikutnya: terbitkan SPK QC (kartu QC retur) lalu tugaskan petugas QC.";
    return `Langkah berikutnya: QC per roll di SPK ${ret.inspection_number || ""} — menu Kualitas › SPK Inspeksi.`;
  }
  if (st === "inspected") return "Langkah berikutnya: pilih outcome (refund / store credit / nego) — tombol \"Selesaikan\".";
  return "";
}

export default function ReturnStepper({ ret, status, draftDiscarded = false }) {
  const doc = ret || { status };
  const dead = doc.status === "rejected" || doc.status === "cancelled";
  const stage = returnStage(doc);
  const hint = dead ? "" : nextHint(doc);

  return (
    <div className="section-card mb-3 !p-3" data-testid="return-stepper">
      <div className="flex flex-wrap items-center gap-1.5">
        {STEPS.map((s, i) => {
          const done = stage > i;
          const now = !dead && stage === i;
          return (
            <div key={s.key} className="flex items-center gap-1.5" title={s.hint}>
              <span data-testid={`return-step-${s.key}`}
                className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-bold transition-colors ${
                  done ? "border-[#BFE3CC] bg-[#EAF7EF] text-[#1B7F4B]"
                    : now ? "border-[#0058CC] bg-[#0058CC] text-white"
                      : "border-[#E5E5EA] bg-white text-[#8E8E93]"}`}>
                {done ? <Check size={11} /> : <span className="tabular-nums">{i + 1}</span>}
                {s.label}
              </span>
              {i < STEPS.length - 1 && <span className="text-[#C7C7CC]">→</span>}
            </div>
          );
        })}
        {dead && (
          <span data-testid="return-step-dead"
            className="flex items-center gap-1.5 rounded-full border border-[#F3C1C1] bg-[#FDF0F0] px-2.5 py-1 text-[11px] font-bold text-[#C62828]">
            <X size={11} /> {doc.status === "rejected" ? "Ditolak" : draftDiscarded ? "Draf dibuang" : "Dibatalkan (reversal)"}
          </span>
        )}
      </div>
      {hint && (
        <p className="mt-1.5 text-[11px] text-[#6B6B73]" data-testid="return-stepper-hint">{hint}</p>
      )}
    </div>
  );
}
