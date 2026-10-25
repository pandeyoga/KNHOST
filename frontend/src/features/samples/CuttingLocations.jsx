import { useEffect, useState } from "react";
import ErrorNotice from "../../components/ErrorNotice";
import { apiErrorText } from "../../utils/apiError";
import { cuttingLocations, setCuttingCaps } from "./sampleApi";

const CAPS = [["standard", "Standar"], ["hanger", "Hanger"], ["catalogue", "Katalog"]];

/** L06 LN-061 — kemampuan cutting per lokasi (aturan yang SAMA dipakai API pembuatan sample). */
export default function CuttingLocations({ canEdit }) {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const load = () => cuttingLocations().then(setRows).catch((e) => setError(apiErrorText(e, "Gagal memuat lokasi.")));
  useEffect(() => { load(); }, []);
  const toggle = async (w, cap) => {
    const caps = w.cutting_caps.includes(cap) ? w.cutting_caps.filter((c) => c !== cap) : [...w.cutting_caps, cap];
    try { await setCuttingCaps(w.id, caps); await load(); } catch (e) { setError(apiErrorText(e, "Gagal menyimpan.")); }
  };
  return (
    <section data-testid="cutting-locations" className="section-card overflow-x-auto">
      <ErrorNotice message={error} onDismiss={() => setError("")} testId="cutting-locations-error" />
      <p className="px-3 pt-2 text-[11.5px] text-[#6B6B73]">Centang jenis sample yang boleh dipotong di tiap lokasi. Mis. lokasi yang hanya standar tidak otomatis bisa katalog.</p>
      <table className="w-full min-w-[480px] text-[12px]">
        <thead><tr className="border-b border-[#EFF0F2] text-left text-[10px] uppercase tracking-wide text-[#8E8E93]">
          <th className="px-3 py-2">Lokasi</th>{CAPS.map(([k, l]) => <th key={k} className="px-3 py-2 text-center">{l}</th>)}</tr></thead>
        <tbody>
          {rows.map((w) => (
            <tr key={w.id} data-testid={`cutting-loc-${w.id}`} className="border-b border-[#F2F3F5]">
              {/* UAT 24 Okt (audit UI tahap 2) — G2-32: keterangan mengikuti centang (dulu "belum diatur" di samping
                  kotak yang semuanya tercentang — lokasi tanpa aturan memang bawaannya boleh semua jenis). */}
              <td className="px-3 py-2"><p className="font-semibold">{w.name}</p>
                <p className="text-[10px] text-[#8E8E93]" data-testid={`cutting-loc-note-${w.id}`}>
                  {!w.configured ? "Bawaan: semua jenis boleh (belum pernah diubah)"
                    : w.cutting_caps.length === 0 ? "Tidak menerima potong sample"
                      : `${w.cutting_caps.length} dari ${CAPS.length} jenis diizinkan`}
                </p></td>
              {CAPS.map(([k]) => (
                <td key={k} className="px-3 py-2 text-center">
                  <input type="checkbox" data-testid={`cutting-cap-${w.id}-${k}`} checked={w.cutting_caps.includes(k)} disabled={!canEdit}
                    onChange={() => toggle(w, k)} className="h-4 w-4 accent-[#0058CC]" />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
