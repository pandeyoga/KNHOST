/**
 * RoleAccessPanel — tab "Peran & Hak Akses": daftar peran (bawaan + kustom),
 * jumlah akun, ringkasan tingkat akses, dan pintu ke editor.
 */
import { useCallback, useEffect, useState } from "react";
import { Plus, ShieldCheck, Lock, Users, Sparkles, Pencil, Copy } from "lucide-react";

import RoleEditorDrawer from "./RoleEditorDrawer";
import useListSearch from "@/hooks/useListSearch";
import { accessModules, accessRolesFull, errText } from "./entityApi";

const NO_MANAGE_HINT = "Peran Anda tidak diberi wewenang mengelola akun/peran ini.";

function RoleCard({ role, onOpen, onDuplicate }) {
  const lv = Object.values(role.levels || {});
  const n = (k) => lv.filter((x) => x.level === k && !x.partial).length;   // PR-T5 — sebagian dihitung terpisah
  const partial = lv.filter((x) => x.partial).length;
  return (
    <div role="button" tabIndex={0} data-testid={`role-card-${role.id}`} onClick={() => onOpen(role)}
         onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onOpen(role); } }}
         className="flex cursor-pointer flex-col gap-1.5 rounded-xl border border-[#EFF0F2] bg-white p-3 text-left transition-colors hover:border-[#0058CC]/50">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-[12.5px] font-bold text-[#1C1C1E]" data-testid={`role-card-label-${role.id}`}>{role.label}</p>
          <p className="line-clamp-2 text-[10.5px] text-[#6B6B73]">{role.description || "—"}</p>
        </div>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[9.5px] font-semibold ${
          role.custom ? "bg-[#F3E9FA] text-[#6B219A]" : "bg-[#F2F2F7] text-[#6B6B73]"}`}
              data-testid={`role-card-kind-${role.id}`}>
          {role.custom ? "Kustom" : "Bawaan"}
        </span>
        {onDuplicate && (
          <button type="button" className="icon-button shrink-0" title="Duplikat peran ini" aria-label={`Duplikat ${role.label}`}
                  data-testid={`role-card-duplicate-${role.id}`}
                  onClick={(e) => { e.stopPropagation(); onDuplicate(role); }}>
            <Copy size={12} />
          </button>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
        <span className="inline-flex items-center gap-1 rounded-full border border-[#E5E5EA] px-2 py-0.5 font-semibold text-[#3A3A3C]" data-testid={`role-card-users-${role.id}`}>
          <Users size={10} /> {role.users} akun
        </span>
        <span className="rounded-full bg-[#EEF9F1] px-2 py-0.5 font-semibold text-[#1B7F4B]" data-testid={`role-card-count-manage-${role.id}`}>{n("manage")} semua aksi</span>
        <span className="rounded-full bg-kn-warning-soft px-2 py-0.5 font-semibold text-kn-warning-text" data-testid={`role-card-count-partial-${role.id}`}>{partial} sebagian</span>
        <span className="rounded-full bg-[#EAF2FF] px-2 py-0.5 font-semibold text-[#0058CC]" data-testid={`role-card-count-view-${role.id}`}>{n("view")} lihat</span>
        <span className="rounded-full bg-[#F2F2F7] px-2 py-0.5 font-semibold text-[#6B6B73]" data-testid={`role-card-count-none-${role.id}`}>{n("none")} tidak ada</span>
        {role.locked && <span className="inline-flex items-center gap-0.5 rounded-full bg-[#FCEBEA] px-2 py-0.5 font-semibold text-[#A8221A]"><Lock size={9} /> dikunci</span>}
        {role.modified && <span className="inline-flex items-center gap-0.5 rounded-full bg-[#FEF7EC] px-2 py-0.5 font-semibold text-[#8C4A00]" data-testid={`role-card-modified-${role.id}`}><Pencil size={9} /> diubah dari bawaan</span>}
        {role.cross_entity && <span className="inline-flex items-center gap-0.5 rounded-full bg-[#F2F7FF] px-2 py-0.5 font-semibold text-[#0058CC]" data-testid={`role-card-cross-${role.id}`}>Semua PT</span>}
        {role.base_role_label && <span className="text-kn-text-2">peran dasar: {role.base_role_label}</span>}
      </div>
      {role.can_manage === false && !role.locked && (
        <p className="text-fs-12 text-kn-text-2" data-testid={`role-card-no-manage-${role.id}`}>{NO_MANAGE_HINT}</p>
      )}
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

  const customs = roles.filter((r) => r.custom);
  const builtins = roles.filter((r) => !r.custom);
  const pgBuilt = useListSearch(builtins, (r) => [r.label, r.name, r.id, r.description], { testId: "role-builtin", pageSize: 18, placeholder: "Cari peran…" });

  return (
    <div data-testid="role-access-panel">
      <div className="mb-3 flex flex-wrap items-start gap-2 rounded-md border border-[#C9DBF7] bg-[#F2F7FF] px-3 py-2">
        <ShieldCheck size={14} className="mt-0.5 text-[#0058CC]" />
        <div className="min-w-0 flex-1">
          <p className="text-[11.5px] font-bold text-[#1C1C1E]">Peran menentukan modul mana yang boleh dilihat dan dikelola.</p>
          <p className="text-[10.5px] text-[#6B6B73]">
            Tingkat per modul: <b>Tidak ada</b> (menu tersembunyi) · <b>Lihat saja</b> (baca tanpa tombol ubah) · <b>Semua aksi</b>;
            bila hanya sebagian aksi yang diberikan, modul berlencana <b>Sebagian</b> (rinciannya di "Atur rinci").
            Notifikasi mengikuti pengaturan ini — pengguna hanya menerima pemberitahuan untuk layar yang boleh dibukanya.
            Buat peran kustom bila peran bawaan tidak pas — misalnya "Staf Penagihan" yang hanya butuh piutang & pelanggan.
          </p>
        </div>
        {canManage && (
          <button type="button" className="primary-button" data-testid="role-create-button" onClick={() => setEditor({})}>
            <Plus size={14} /> Buat Peran Baru
          </button>
        )}
      </div>

      {loading && <p className="text-fs-12 text-kn-text-2" data-testid="role-access-loading">Memuat peran…</p>}

      {!loading && (
        <>
          <div className="mb-1.5 flex items-center gap-1.5">
            <Sparkles size={12} className="text-[#6B219A]" />
            <p className="kicker !mb-0">Peran kustom ({customs.length})</p>
          </div>
          {customs.length === 0 ? (
            <div className="mb-4 rounded-xl border border-dashed border-[#E5E5EA] bg-[#FAFBFC] px-4 py-5 text-center" data-testid="role-custom-empty">
              <p className="text-[11.5px] font-semibold text-[#1C1C1E]">Belum ada peran kustom.</p>
              <p className="text-[10.5px] text-[#8E8E93]">Klik "Buat Peran Baru", salin dari peran bawaan yang paling mirip, lalu sesuaikan modulnya.</p>
            </div>
          ) : (
            <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3" data-testid="role-custom-grid">
              {customs.map((r) => <RoleCard key={r.id} role={r} onOpen={setEditor} onDuplicate={duplicate} />)}
            </div>
          )}
          <p className="kicker mb-1.5">Peran bawaan sistem ({builtins.length}) — hak aksesnya bisa disesuaikan</p>
          {pgBuilt.toolbar}
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3" data-testid="role-builtin-grid">
            {pgBuilt.pageRows.map((r) => <RoleCard key={r.id} role={r} onOpen={setEditor} onDuplicate={r.locked ? null : duplicate} />)}
          </div>
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
