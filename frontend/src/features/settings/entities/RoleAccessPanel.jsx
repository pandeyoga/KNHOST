/**
 * RoleAccessPanel — tab "Peran & Hak Akses": daftar peran (bawaan + kustom),
 * jumlah akun, ringkasan tingkat akses, dan pintu ke editor.
 *
 * Pola UI 16 Nov (`docs/blueprint/04_POLA_UI.md`, pemilik M43): SATU bilah daftar (cari · jumlah · (?) · muat ulang ·
 * + Buat Peran Baru) — dua bilah penjelasan panjang pindah ke ikon ?, tombol muat ulang tidak lagi sendirian di satu
 * baris. Daftar padat: satu baris per peran (nama (?) · lencana · jumlah akun & tingkat · aksi), bukan kartu bertumpuk.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, Lock, Users, Pencil, Copy, RefreshCw } from "lucide-react";

import RoleEditorDrawer from "./RoleEditorDrawer";
import { HelpTip, ListToolbar, SearchInput } from "../../../components/ListPageParts";
import { accessModules, accessRolesFull, errText } from "./entityApi";

const NO_MANAGE_HINT = "Peran Anda tidak diberi wewenang mengelola akun/peran ini.";
const BANTUAN = "Peran menentukan modul mana yang boleh dilihat dan dikelola. Tingkat per modul: Tidak ada (menu "
  + "tersembunyi) · Lihat saja (baca tanpa tombol ubah) · Semua aksi; bila hanya sebagian aksi yang diberikan, modul "
  + "berlencana Sebagian (rinciannya di \"Rinci\"). Notifikasi mengikuti pengaturan ini — pengguna hanya menerima "
  + "pemberitahuan untuk layar yang boleh dibukanya. Buat peran kustom bila peran bawaan tidak pas — misalnya \"Staf "
  + "Penagihan\" yang hanya butuh piutang & pelanggan.";

function RoleRow({ role, onOpen, onDuplicate, reserveAction = false }) {
  const lv = Object.values(role.levels || {});
  const n = (k) => lv.filter((x) => x.level === k && !x.partial).length;   // PR-T5 — sebagian dihitung terpisah
  const partial = lv.filter((x) => x.partial).length;
  const open = () => onOpen(role);
  return (
    <div role="button" tabIndex={0} data-testid={`role-card-${role.id}`} onClick={open}
         onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } }}
         className="cfg-row cfg-row-wrap cursor-pointer hover:bg-kn-neutral-soft">
      <span className="cfg-row-name">
        <span className="cfg-row-title" data-testid={`role-card-label-${role.id}`}>{role.label}</span>
        <span onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()} role="presentation">
          <HelpTip text={role.description || ""} testId={`role-card-help-${role.id}`} label={`Tentang peran ${role.label}`} />
        </span>
        <span className={role.custom ? "badge-purple" : "badge-muted"} data-testid={`role-card-kind-${role.id}`}>
          {role.custom ? "Kustom" : "Bawaan"}
        </span>
        {role.locked && <span className="badge-red"><Lock size={11} /> dikunci</span>}
        {role.modified && <span className="badge-orange" data-testid={`role-card-modified-${role.id}`}><Pencil size={11} /> diubah dari bawaan</span>}
        {role.cross_entity && <span className="badge-blue" data-testid={`role-card-cross-${role.id}`}>Semua PT</span>}
        {role.base_role_label && <span className="text-fs-12 text-kn-text-2">peran dasar: {role.base_role_label}</span>}
        {role.can_manage === false && !role.locked && (
          <span className="text-fs-12 text-kn-text-2" data-testid={`role-card-no-manage-${role.id}`}>· {NO_MANAGE_HINT}</span>
        )}
      </span>
      <span className="cfg-role-meta">
        <span className="inline-flex items-center gap-1 text-kn-text" data-testid={`role-card-users-${role.id}`}>
          <Users size={12} aria-hidden="true" /> {role.users} akun
        </span>
        <span className="text-kn-success-text" data-testid={`role-card-count-manage-${role.id}`}>{n("manage")} semua aksi</span>
        <span className="text-kn-warning-text" data-testid={`role-card-count-partial-${role.id}`}>{partial} sebagian</span>
        <span className="text-kn-action" data-testid={`role-card-count-view-${role.id}`}>{n("view")} lihat</span>
        <span className="text-kn-text-2" data-testid={`role-card-count-none-${role.id}`}>{n("none")} tidak ada</span>
      </span>
      <span className="cfg-row-tags">
        {onDuplicate && (
          <button type="button" className="icon-button btn-sm" title="Duplikat peran ini" aria-label={`Duplikat ${role.label}`}
                  data-testid={`role-card-duplicate-${role.id}`}
                  onClick={(e) => { e.stopPropagation(); onDuplicate(role); }}>
            <Copy size={13} />
          </button>
        )}
        {/* Kolom aksi tetap selebar tombol supaya angka baris lain sejajar (mis. Admin yang tidak bisa diduplikat). */}
        {!onDuplicate && reserveAction && <span className="cfg-row-spacer" aria-hidden="true" />}
      </span>
    </div>
  );
}

export default function RoleAccessPanel({ canManage, onChanged, onError, onOpenAccounts }) {
  const [roles, setRoles] = useState([]);
  const [modules, setModules] = useState([]);
  const [labels, setLabels] = useState({});
  const [loading, setLoading] = useState(true);
  const [canEditAssignable, setCanEditAssignable] = useState(false);
  const [editor, setEditor] = useState(null);   // null | {} (baru) | {template} (duplikat) | role
  const [q, setQ] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [full, m] = await Promise.all([accessRolesFull(), accessModules()]);
      const r = full.roles;
      setRoles(r); setModules(m.modules || []); setCanEditAssignable(full.canEditAssignable);
      setLabels({ resource_labels: m.resource_labels || {}, action_labels: m.action_labels || {} });
      return r;
    } catch (e) { onError?.(errText(e, "Gagal memuat daftar peran.")); return null; }
    finally { setLoading(false); }
  }, [onError]);

  useEffect(() => { load(); }, [load]);

  const duplicate = canManage ? (r) => setEditor({ template: r }) : null;
  const refreshEditor = async (msg) => {
    onChanged?.(msg);
    const list = await load();
    const cur = list?.find((x) => x.id === editor?.id);
    setEditor(cur || null);
  };

  const term = q.trim().toLowerCase();
  const shown = useMemo(() => (term ? roles.filter((r) => [r.label, r.name, r.id, r.description]
    .some((v) => String(v || "").toLowerCase().includes(term))) : roles), [roles, term]);
  const customs = shown.filter((r) => r.custom);
  const builtins = shown.filter((r) => !r.custom);

  return (
    <div data-testid="role-access-panel">
      <ListToolbar testId="role-toolbar" count={loading ? null : `${shown.length} peran`}
        actions={(
          <>
            <button type="button" className="icon-button" data-testid="role-access-refresh" aria-label="Muat ulang daftar peran"
                    title="Muat ulang" onClick={() => load()}>
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            </button>
            {canManage && (
              <button type="button" className="primary-button btn-sm" data-testid="role-create-button" onClick={() => setEditor({})}>
                <Plus size={14} /> Buat Peran Baru
              </button>
            )}
          </>
        )}>
        <SearchInput value={q} onChange={setQ} placeholder="Cari peran…" testId="role-search" />
        <HelpTip text={BANTUAN} testId="role-access-help" label="Tentang peran & hak akses" />
      </ListToolbar>

      {loading && <p className="text-fs-12 text-kn-text-2" data-testid="role-access-loading">Memuat peran…</p>}

      {!loading && (
        <>
          <section className="cfg-section">
            <h4 className="cfg-section-title">Peran kustom ({customs.length})</h4>
            {customs.length === 0 ? (
              <p className="cfg-readonly-line" data-testid="role-custom-empty">
                {term ? "Tidak ada peran kustom yang cocok." : "Belum ada peran kustom — klik \"Buat Peran Baru\", salin dari peran bawaan yang paling mirip, lalu sesuaikan modulnya."}
              </p>
            ) : (
              <div className="cfg-rows" data-testid="role-custom-grid">
                {customs.map((r) => <RoleRow key={r.id} role={r} onOpen={setEditor} onDuplicate={duplicate} />)}
              </div>
            )}
          </section>
          <section className="cfg-section">
            <h4 className="cfg-section-title">
              Peran bawaan sistem ({builtins.length}) <span className="font-normal text-kn-text-2">· hak aksesnya bisa disesuaikan</span>
            </h4>
            <div className="cfg-rows" data-testid="role-builtin-grid">
              {builtins.map((r) => <RoleRow key={r.id} role={r} onOpen={setEditor} onDuplicate={r.locked ? null : duplicate}
                                            reserveAction={Boolean(duplicate)} />)}
            </div>
          </section>
        </>
      )}

      {editor && (
        <RoleEditorDrawer key={`${editor.id || editor.template?.id || "new"}:${editor.version || ""}`}
                          role={editor.id ? editor : null} template={editor.template || null} roles={roles} modules={modules} labels={labels}
                          canEditAssignable={canEditAssignable} canFollow={canManage} canManage={canManage}
                          onOpenAccounts={onOpenAccounts ? () => { setEditor(null); onOpenAccounts(); } : undefined}
                          onClose={() => setEditor(null)}
                          onSaved={(msg) => { setEditor(null); onChanged?.(msg); load(); }}
                          onRefresh={refreshEditor}
                          onError={onError} />
      )}
    </div>
  );
}
