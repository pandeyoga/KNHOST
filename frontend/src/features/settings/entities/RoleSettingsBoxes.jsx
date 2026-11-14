/**
 * RoleSettingsBoxes — kotak pengaturan peran di kolom kanan editor peran (dipisah dari `RoleEditorDrawer.jsx`, PR-T6,
 * supaya berkas editor di bawah batas ukuran):
 *  · `CrossEntityBox` — akses semua PT (keputusan owner 2026-10-21); "Bawaan" = `cross_entity_default` server
 *    (peran kustom: nilai EFEKTIF peran dasarnya, PR-T6).
 *  · `AssignableBox` — PR-T1, peran yang akunnya boleh dikelola pemegang peran ini (hanya Admin yang mengubah).
 */
export function CrossEntityBox({ cross, disabled, role, onChange }) {
  return (
    <label className={`flex items-start gap-2 rounded-md border border-kn-divider p-2 ${cross ? "bg-kn-action-soft" : "bg-white"}`}
           data-testid="role-editor-cross-entity">
      <input type="checkbox" className="mt-0.5" checked={cross} disabled={disabled} data-testid="role-editor-cross-entity-toggle"
             onChange={(e) => onChange?.(e.target.checked)} />
      <span className="text-fs-12 text-kn-text">
        <b>Akses semua PT (lintas PT)</b><br />
        {cross ? "Akun peran ini membuka SEMUA PT aktif, termasuk yang baru dibuat."
               : "Akun peran ini hanya membuka PT yang ditugaskan per akun (tab Akun & Akses)."}
        {role && role.cross_entity_default !== undefined && (
          <span className="block text-kn-text-2" data-testid="role-editor-cross-entity-default">
            Bawaan: {role.cross_entity_default ? "aktif" : "mati"}{role.custom ? " (mengikuti peran dasar)" : ""}.
          </span>
        )}
      </span>
    </label>
  );
}

export function AssignableBox({ roles, assignable, canEdit, disabled, onToggle }) {
  return (
    <div className="rounded-md border border-kn-divider bg-white p-2.5" data-testid="role-editor-assignable">
      <p className="kicker mb-0.5">Boleh mengelola akun dengan peran</p>
      <p className="mb-1.5 text-fs-12 text-kn-text-2">
        Pemegang peran ini hanya bisa membuat, mengubah, dan mereset sandi akun yang perannya dicentang di sini.
        Kosong = tidak bisa mengelola akun siapa pun.
      </p>
      {!canEdit && <p className="mb-1 text-fs-12 text-kn-text-2" data-testid="role-editor-assignable-readonly">Hanya Admin yang bisa mengubah daftar ini.</p>}
      <div className="grid gap-0.5">
        {(roles || []).filter((r) => !r.locked).map((r) => (
          <label key={r.id} className="flex items-center gap-1.5 text-fs-12 text-kn-text">
            <input type="checkbox" checked={assignable.has(r.id)} disabled={!canEdit || disabled}
                   data-testid={`role-editor-assignable-${r.id}`} onChange={() => onToggle?.(r.id)} />
            {r.label}
          </label>
        ))}
      </div>
    </div>
  );
}
