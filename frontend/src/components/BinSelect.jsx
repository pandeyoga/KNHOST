/**
 * BinSelect (FIX-3a — audit B3b INP-01/02/05, G-FORM-01) — pemilih BIN dari struktur gudang, terikat id.
 *
 * Dulu isian bin di Scan Terima, opname per item, dan stok awal berupa teks bebas: kode rak yang benar ("A1-01")
 * tersimpan apa adanya padahal stok mencatat id bin, sehingga expected 0 → roll surplus + jurnal di alamat fiktif.
 * Komponen ini memuat bin dari `GET /warehouses/{id}/locations` (sumber yang sama dengan opname per roll) dan
 * mengirim `bin_id` kanonik; server tetap memvalidasi (resolve_bin).
 *
 * Props: warehouseId, value, onChange(binId), allowEmpty (bawaan true: "Tanpa bin"), emptyLabel, disabled,
 *        className, data-testid.
 */
import { useEffect, useMemo, useState } from "react";
import KNSelect from "./KNSelect";
import axios, { API } from "../services/apiClient";

export default function BinSelect({ warehouseId, value, onChange, allowEmpty = true, emptyLabel = "Tanpa bin (tempatkan nanti)",
  disabled = false, className = "field", placeholder = "Pilih bin…", ...rest }) {
  const [bins, setBins] = useState(null);
  useEffect(() => {
    let live = true;
    if (!warehouseId) { setBins([]); return undefined; }
    setBins(null);
    axios.get(`${API}/warehouses/${warehouseId}/locations`)
      .then((r) => { if (live) setBins(r.data?.bins || []); })
      .catch(() => { if (live) setBins([]); });
    return () => { live = false; };
  }, [warehouseId]);
  const options = useMemo(() => [
    ...(allowEmpty ? [{ value: "", label: emptyLabel }] : []),
    ...(bins || []).map((b) => ({ value: b.bin_id, label: b.path ? `${b.code} — ${b.path}` : b.code })),
  ], [bins, allowEmpty, emptyLabel]);
  return (
    <KNSelect {...rest} value={value || ""} onValueChange={onChange} options={options} className={className}
      placeholder={bins === null ? "Memuat bin…" : placeholder} disabled={disabled || !warehouseId}
      emptyText={warehouseId ? "Gudang ini belum punya struktur bin" : "Pilih gudang dulu"} searchable />
  );
}
