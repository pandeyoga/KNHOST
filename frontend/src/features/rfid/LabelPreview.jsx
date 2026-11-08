/**
 * PREP-F — pratinjau PERKIRAAN label (SVG) dari tata letak yang sama dengan ZPL (`/rfid/printers/label-preview`).
 * Bukan render printer: font printer & posisi inlay sebenarnya dibuktikan saat uji meja CP30EN.
 * QR digambar sebagai kotak bertanda (bukan kode QR asli) — ukurannya sama dengan perhitungan modul × pembesaran.
 */
export default function LabelPreview({ layout, testId = "label-preview", maxWidth = 420 }) {
  if (!layout) return null;
  const W = layout.width_dots || 560;
  const H = layout.height_dots || 176;
  const ox = layout.offset_x_dots || 0;
  const oy = layout.offset_y_dots || 0;
  return (
    <figure className="space-y-1" data-testid={testId}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Pratinjau label ${layout.width_mm} × ${layout.height_mm} mm`}
        style={{ width: "100%", maxWidth, background: "#fff", border: "1px solid #D1D1D6", borderRadius: 6 }}>
        <rect x="0" y="0" width={W} height={H} fill="#fff" />
        <g transform={`translate(${ox},${oy})`}>
          {(layout.elements || []).map((e, i) => (e.type === "qr" ? (
            <g key={i} data-testid={`${testId}-qr`}>
              <rect x={e.x} y={e.y} width={e.size} height={e.size} fill="#fff" stroke="#1C1C1E" strokeWidth="3" />
              <rect x={e.x + 6} y={e.y + 6} width={e.size / 4} height={e.size / 4} fill="#1C1C1E" />
              <rect x={e.x + e.size - 6 - e.size / 4} y={e.y + 6} width={e.size / 4} height={e.size / 4} fill="#1C1C1E" />
              <rect x={e.x + 6} y={e.y + e.size - 6 - e.size / 4} width={e.size / 4} height={e.size / 4} fill="#1C1C1E" />
              <text x={e.x + e.size / 2} y={e.y + e.size / 2 + 6} fontSize={Math.max(10, e.size / 9)} textAnchor="middle"
                fill="#6B6B73">QR</text>
            </g>
          ) : (
            <text key={i} x={e.x} y={e.y + e.h * 0.82} fontSize={e.h}
              fontFamily="Arial Narrow, Arial, sans-serif" fontWeight={e.role === "roll_no" || e.role === "title" ? 700 : 500}
              fill="#1C1C1E" data-testid={`${testId}-${e.role}`}>{e.text}</text>
          )))}
        </g>
      </svg>
      <figcaption className="text-[10.5px] text-[#6B6B73]" data-testid={`${testId}-caption`}>
        {layout.width_mm} × {layout.height_mm} mm · {layout.dpi} dpi = {W} × {H} dot
        {layout.rfid ? " · menulis EPC ke chip" : " · tanpa tulis chip"}
        {layout.epc_display ? ` · EPC ${layout.epc_display}` : ""}
      </figcaption>
      {(layout.warnings || []).length > 0 && (
        <ul className="text-[10.5px] text-[#8C4A00]" data-testid={`${testId}-warnings`}>
          {layout.warnings.map((w) => <li key={w}>⚠ {w}</li>)}
        </ul>
      )}
    </figure>
  );
}
