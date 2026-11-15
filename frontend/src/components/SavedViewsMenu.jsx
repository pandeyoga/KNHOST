/**
 * SavedViewsMenu — FIX-8 (K-B4-12 · B4 §3.4 [6–8] · KN_37 §6b): tombol "Tampilan: … ▾" daftar gudang.
 *
 * Isi menu: tampilan saya · dibagikan ke peran/PT saya · "Tampilan standar" · simpan perubahan (tanda `*` bila
 * berbeda dari tampilan aktif) · simpan sebagai baru (+ jadikan bawaan; admin: bagikan ke peran/PT) · jadikan bawaan ·
 * hapus · pilihan KOLOM (bila layar memberi `columns`). Esc menutup lapisan teratas saja (INV-UI-10). Gagal = bilah
 * `ErrorNotice` menempel. Cakupan PT/lokasi TIDAK ikut tampilan (bilah "Lokasi: … ▾" tetap berlaku).
 *
 * Props: sv (hasil `useSavedViews`) · columns [{key,label}] + hidden (kunci tersembunyi) + onColumnsChange ·
 * shareRoles [{value,label}] · shareEntities [{value,label}] · testId.
 */
import { useEffect, useRef, useState } from "react";
import { Bookmark, BookmarkCheck, ChevronDown, Loader2, Star, Trash2 } from "lucide-react";
import { useEscapeClose } from "../utils/escapeLayers";
import { askConfirm } from "../services/confirmService";
import { notifySuccess } from "../utils/feedback";
import ErrorNotice from "./ErrorNotice";

export default function SavedViewsMenu({
  sv, columns = [], hidden = [], onColumnsChange, shareRoles = [], shareEntities = [], testId = "saved-views",
}) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(null);   // {name, isDefault, roles:Set, ents:Set, sharedDefault}
  const boxRef = useRef(null);
  useEscapeClose(open, () => { setOpen(false); setForm(null); });
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) { setOpen(false); setForm(null); } };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  if (!sv) return null;
  const mine = sv.views.filter((v) => v.mine);
  const shared = sv.views.filter((v) => !v.mine);
  const active = sv.active;
  const label = active ? active.name : "Tampilan standar";

  const pick = (id) => { sv.select(id); setOpen(false); setForm(null); };
  const toggleCol = (key) => {
    const set = new Set(hidden);
    if (set.has(key)) set.delete(key); else set.add(key);
    onColumnsChange?.([...set]);
  };
  const submitNew = async (e) => {
    e.preventDefault();
    const name = (form?.name || "").trim();
    if (!name) return;
    const share = (form.roles.size || form.ents.size)
      ? { roles: [...form.roles], entity_ids: [...form.ents], is_default: Boolean(form.sharedDefault) } : null;
    const ok = await sv.saveAs(name, { isDefault: form.isDefault, share });
    if (ok) { notifySuccess("Tampilan disimpan", `“${name}” bisa dipilih lagi kapan saja.`); setForm(null); setOpen(false); }
  };
  const removeActive = async () => {
    if (!active) return;
    const yes = await askConfirm({ title: `Hapus tampilan “${active.name}”?`,
      message: active.shared ? "Tampilan ini dibagikan — penerimanya tidak akan melihatnya lagi." : "Saringan di layar tidak berubah.",
      confirmLabel: "Hapus tampilan", danger: true });
    if (yes && await sv.remove(active.id)) notifySuccess("Tampilan dihapus", active.name);
  };
  const flip = (k, val) => setForm((f) => {
    const s = new Set(f[k]);
    if (s.has(val)) s.delete(val); else s.add(val);
    return { ...f, [k]: s };
  });

  return (
    <div className="kn-views" ref={boxRef} data-testid={testId}>
      <button type="button" className="secondary-button btn-sm" data-testid={`${testId}-button`}
        aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((v) => !v)}
        title="Simpan & pakai lagi kombinasi saringan, urutan, dan kolom daftar ini">
        {active ? <BookmarkCheck size={14} /> : <Bookmark size={14} />}
        <span>Tampilan: {label}</span>
        {sv.dirty && <span className="kn-views-dirty" data-testid={`${testId}-dirty`} title="Saringan/kolom berbeda dari tampilan ini">*</span>}
        {sv.loading || sv.busy ? <Loader2 size={14} className="animate-spin" /> : <ChevronDown size={14} />}
      </button>
      {open && (
        <div className="kn-views-menu" role="menu" data-testid={`${testId}-menu`}>
          <button type="button" role="menuitem" className={`kn-views-item${!active ? " is-active" : ""}`}
            data-testid={`${testId}-standard`} onClick={() => { sv.reset(); setOpen(false); }}>
            Tampilan standar <small>tanpa saringan</small>
          </button>
          {mine.length > 0 && <div className="kn-views-head">Tampilan saya</div>}
          {mine.map((v) => (
            <button key={v.id} type="button" role="menuitem" data-testid={`${testId}-item-${v.id}`}
              className={`kn-views-item${v.id === sv.activeId ? " is-active" : ""}`} onClick={() => pick(v.id)}>
              {v.is_default ? <Star size={13} aria-label="bawaan" /> : <Bookmark size={13} aria-hidden="true" />}
              <span>{v.name}</span>{v.shared && <small>dibagikan</small>}
            </button>
          ))}
          {shared.length > 0 && <div className="kn-views-head">Dibagikan ke peran/PT</div>}
          {shared.map((v) => (
            <button key={v.id} type="button" role="menuitem" data-testid={`${testId}-item-${v.id}`}
              className={`kn-views-item${v.id === sv.activeId ? " is-active" : ""}`} onClick={() => pick(v.id)}>
              {v.share?.is_default ? <Star size={13} aria-label="bawaan bersama" /> : <Bookmark size={13} aria-hidden="true" />}
              <span>{v.name}</span><small>{v.applies_to_me ? (v.owner_name || "admin") : "tidak berlaku untuk Anda"}</small>
            </button>
          ))}
          <div className="kn-views-sep" />
          {active && sv.dirty && active.can_edit && (
            <button type="button" role="menuitem" className="kn-views-item" data-testid={`${testId}-save`}
              disabled={sv.busy} onClick={async () => { if (await sv.saveActive()) { notifySuccess("Tampilan diperbarui", active.name); setOpen(false); } }}>
              Simpan perubahan ke “{active.name}”
            </button>
          )}
          {!form && (
            <button type="button" role="menuitem" className="kn-views-item" data-testid={`${testId}-new`}
              onClick={() => setForm({ name: "", isDefault: false, roles: new Set(), ents: new Set(), sharedDefault: false })}>
              Simpan sebagai tampilan baru…
            </button>
          )}
          {form && (
            <form className="kn-views-form" onSubmit={submitNew} data-testid={`${testId}-form`}>
              <label className="field-label" htmlFor={`${testId}-name`}>Nama tampilan *</label>
              <input id={`${testId}-name`} className="field" maxLength={60} required autoFocus value={form.name}
                data-testid={`${testId}-name`} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
              <label className="flex items-center gap-2 text-fs-13">
                <input type="checkbox" checked={form.isDefault} data-testid={`${testId}-default`}
                  onChange={(e) => setForm((f) => ({ ...f, isDefault: e.target.checked }))} />
                Jadikan bawaan saya saat membuka daftar ini
              </label>
              {sv.canShare && (shareRoles.length > 0 || shareEntities.length > 0) && (
                <fieldset data-testid={`${testId}-share`}>
                  <legend className="field-label">Bagikan (admin) — kosongkan untuk pribadi</legend>
                  {shareRoles.length > 0 && <div className="kn-views-cols">
                    {shareRoles.map((r) => (
                      <label key={r.value}><input type="checkbox" checked={form.roles.has(r.value)}
                        onChange={() => flip("roles", r.value)} data-testid={`${testId}-role-${r.value}`} />{r.label}</label>
                    ))}
                  </div>}
                  {shareEntities.length > 0 && <div className="kn-views-cols">
                    {shareEntities.map((e) => (
                      <label key={e.value}><input type="checkbox" checked={form.ents.has(e.value)}
                        onChange={() => flip("ents", e.value)} data-testid={`${testId}-pt-${e.value}`} />{e.label}</label>
                    ))}
                  </div>}
                  <label className="flex items-center gap-2 text-fs-13">
                    <input type="checkbox" checked={form.sharedDefault} disabled={!form.roles.size && !form.ents.size}
                      onChange={(e) => setForm((f) => ({ ...f, sharedDefault: e.target.checked }))} />
                    Jadikan bawaan untuk penerima
                  </label>
                </fieldset>
              )}
              <div className="flex justify-end gap-2">
                <button type="button" className="ghost-button btn-sm" onClick={() => setForm(null)}>Batal</button>
                <button type="submit" className="primary-button btn-sm" disabled={sv.busy || !form.name.trim()}
                  data-testid={`${testId}-submit`}>Simpan</button>
              </div>
            </form>
          )}
          {active && active.mine && (
            <button type="button" role="menuitem" className="kn-views-item" data-testid={`${testId}-set-default`}
              disabled={sv.busy} onClick={() => sv.setDefault(active.id, !active.is_default)}>
              <Star size={13} /> {active.is_default ? "Lepas sebagai bawaan saya" : "Jadikan bawaan saya"}
            </button>
          )}
          {active && active.can_edit && (
            <button type="button" role="menuitem" className="kn-views-item" data-testid={`${testId}-delete`}
              disabled={sv.busy} onClick={removeActive}>
              <Trash2 size={13} /> Hapus “{active.name}”
            </button>
          )}
          {columns.length > 0 && (
            <>
              <div className="kn-views-sep" />
              <div className="kn-views-head">Kolom</div>
              <div className="kn-views-cols" data-testid={`${testId}-columns`}>
                {columns.map((c) => (
                  <label key={c.key}>
                    <input type="checkbox" checked={!hidden.includes(c.key)} onChange={() => toggleCol(c.key)}
                      data-testid={`${testId}-col-${c.key}`} />
                    {c.label}
                  </label>
                ))}
              </div>
            </>
          )}
        </div>
      )}
      {sv.error && (
        <div className="kn-export-notice">
          <ErrorNotice message={sv.error} onRetry={() => sv.reload()} onDismiss={sv.clearError} testId={`${testId}-error`} />
        </div>
      )}
    </div>
  );
}
