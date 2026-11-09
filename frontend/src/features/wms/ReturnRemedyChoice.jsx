/**
 * FIX-6 (keputusan pemilik 10 Nov 2026, D2) — TOLAK QC + RETUR KE SUPPLIER: penyelesaian dipilih PER KASUS.
 * Wajib dipilih & beralasan (K-14, ≥ 5 huruf; ditegakkan juga di server) setiap kali disposisi roll ditolak =
 * "retur ke supplier". Dipakai antrean karantina (QCInspection) dan tutup SPK penerimaan (InspectionDetailPanel).
 */
export const REMEDY_OPTIONS = [
  { value: "replace", label: "Ganti barang",
    hint: "PO dibuka lagi dengan tugas terima sisa sebesar qty yang diretur; tagihan supplier tetap." },
  { value: "bill_cut", label: "Potong tagihan",
    hint: "PO ditutup kurang; tagihan supplier dikurangi (Nota Debit) dengan jurnal pembalik GR-IR." },
];

const letters = (t) => (String(t || "").match(/\p{L}/gu) || []).length;

/** Kalimat galat (kosong = sah). */
export function remedyProblem(remedy, reason) {
  if (!REMEDY_OPTIONS.some((o) => o.value === remedy)) return "Pilih penyelesaian retur ke supplier: Ganti barang atau Potong tagihan.";
  if (letters(reason) < 5) return "Alasan pilihan retur ke supplier wajib diisi (minimal 5 huruf).";
  return "";
}

export default function ReturnRemedyChoice({ value, reason, onChange, onReason, testId = "return-remedy" }) {
  return (
    <div className="grid gap-1.5" data-testid={testId}>
      <span className="text-fs-12 font-semibold text-kn-text-2">Penyelesaian retur ke supplier *</span>
      <div className="grid gap-1" role="radiogroup" aria-label="Penyelesaian retur ke supplier">
        {REMEDY_OPTIONS.map((o) => (
          <label key={o.value} className="flex items-start gap-2 text-fs-12 text-kn-text">
            <input type="radio" name={`${testId}-choice`} value={o.value} checked={value === o.value}
              onChange={() => onChange(o.value)} data-testid={`${testId}-${o.value}`} className="mt-0.5" />
            <span><b>{o.label}</b> — {o.hint}</span>
          </label>
        ))}
      </div>
      <input data-testid={`${testId}-reason`} className="form-input" value={reason || ""}
        placeholder="Alasan pilihan (minimal 5 huruf) *" onChange={(e) => onReason(e.target.value)} />
    </div>
  );
}
