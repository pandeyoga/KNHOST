/**
 * Pola UI 16 Nov (M20/M22) — tombol menu kecil katalog: "Alat data master ▾" di bilah daftar dan "Lainnya ▾" di kepala
 * rincian (aksi jarang & aksi hapus tidak dipajang sebagai tombol merah di tengah halaman).
 *
 * Rupa dan perilaku SAMA dengan menu Unduh baku (`ExportMenu`, kelas `kn-export-*`): klik di luar menutup, Esc menutup
 * lapisan teratas saja (`useEscapeClose`, INV-UI-10). Butir yang tidak bisa dipakai tetap tampil NONAKTIF dengan alasan
 * tertulis (`hint`), bukan disembunyikan diam-diam. Butir `false`/`null` dibuang; tanpa butir → tombol tidak dirender.
 *
 * items: [{ key, label, hint?, icon?, testId?, danger?, disabled?, onSelect }] · `labelClass` = kelas teks label (mis. hanya ikon
 * di layar sempit: "hidden 2xl:inline"; nama tetap di `aria-label` & tooltip).
 */
import { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { useEscapeClose } from "../../utils/escapeLayers";

export function CatalogMenu({ label, labelClass = "", icon: Icon, items, testId, title }) {
  const [open, setOpen] = useState(false);
  const boxRef = useRef(null);
  useEscapeClose(open, () => setOpen(false));
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);
  const shown = (items || []).filter(Boolean);
  if (!shown.length) return null;
  return (
    <div className="kn-export" ref={boxRef} data-testid={testId}>
      <button type="button" className="secondary-button btn-sm" data-testid={testId ? `${testId}-button` : undefined}
        aria-haspopup="menu" aria-expanded={open} aria-label={label} title={title || label} onClick={() => setOpen((v) => !v)}>
        {Icon && <Icon size={14} aria-hidden="true" />}<span className={labelClass || undefined}>{label}</span><ChevronDown size={14} aria-hidden="true" />
      </button>
      {open && (
        <div className="kn-export-menu" role="menu" data-testid={testId ? `${testId}-menu` : undefined}>
          {shown.map((it) => (
            <button key={it.key} type="button" role="menuitem" data-testid={it.testId}
              className={`kn-export-item${it.danger ? " catalog-menu-danger" : ""}`}
              disabled={!!it.disabled} aria-disabled={it.disabled || undefined}
              onClick={() => { setOpen(false); it.onSelect?.(); }}>
              {it.icon && <it.icon size={16} aria-hidden="true" className="mt-0.5 shrink-0" />}
              <span><b>{it.label}</b>{it.hint && <small>{it.hint}</small>}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default CatalogMenu;
