/**
 * RoleEditorDrawer — buat / ubah / lihat peran & tingkat aksesnya per modul.
 * 3 tingkat per modul, "Peran dasar" dan "Salin hak akses dari…" (dua kontrol terpisah, PR-T6), panel Ringkasan
 * peran dari pratinjau server, pratinjau menu, riwayat perubahan, dan ringkasan perubahan sebelum disimpan.
 * Mode baca (PR-T6): pelaku tanpa `permission.update` — semua isian mati, tanpa tombol simpan/hapus/kembalikan/pindah.
 *
 * Pola UI 16 Nov (`docs/blueprint/04_POLA_UI.md`, pemilik M43 — foto 36): hak akses = MATRIKS tanpa gulir mendatar
 * (baris = modul berkelompok, kolom = Tidak ada · Lihat saja · Semua aksi · Rinci; baris "Semua modul" di atasnya),
 * ringkasan peran SATU baris (rincian per modul di "Rincian"), peringatan masing-masing satu baris kecil, keterangan
 * panjang di ikon ? judul. Isi kiriman simpan, cek versi (409), dan izin tidak berubah.
 */
import { useCallback, useMemo, useRef, useState } from "react";
import { useEscapeClose } from "@/utils/escapeLayers";
import { X, Save, Loader2, ShieldCheck, Trash2, RotateCcw, Info, Lock } from "lucide-react";

import PageTabs from "../../../components/PageTabs";
import { HelpTip } from "../../../components/ListPageParts";
import RoleModuleRow, { LEVELS, levelLabel, partialLabel } from "./RoleModuleRow";
import RoleMenuPreview from "./RoleMenuPreview";
import RoleAccountsList from "./RoleAccountsList";
import RoleDangerDialog from "./RoleDangerDialog";
import RoleNotifPreview from "./RoleNotifPreview";
import RoleAdvancedPanel from "./RoleAdvancedPanel";
import RoleNavTree, { titleOf } from "./RoleNavTree";
import RoleTraitsPanel, { traitChangeLines, traitPayload } from "./RoleTraitsPanel";
import RoleSummaryPanel from "./RoleSummaryPanel";
import RoleHistoryTab from "./RoleHistoryTab";
import RoleBaseControls, { AccountsReviewDialog, BaseChangeDialog, baseLabelOf } from "./RoleBaseControls";
import { AssignableBox, CrossEntityBox } from "./RoleSettingsBoxes";
import useRolePreview, { previewBody } from "./useRolePreview";
import { actionDiff, applyLevel, levelOf, levelsAvailable, moduleActionsChanged, sensitiveAdded, setResource, toggleAction } from "./roleAccessUtil";
import { createAccessRole, patchAccessRole, deleteAccessRole, resetAccessRole, followBaseAccessRole, previewAccessRole, errText } from "./entityApi";

const permsOf = (src) => {
  const out = {};
  Object.entries(src?.permissions || {}).forEach(([r, acts]) => { if (acts?.length) out[r] = [...acts]; });
  return out;
};
const levelsFromPerms = (perms, modules) => Object.fromEntries(modules.map((m) => [m.id, levelOf(perms, m)]));

export default function RoleEditorDrawer({ role, template, roles, modules, labels, canEditAssignable = false, canFollow = false, canManage = true, onClose, onSaved, onRefresh, onError, onOpenAccounts }) {
  const editing = Boolean(role?.id);
  const locked = Boolean(role?.locked);
  // PR-T1 — server menolak mengubah peran yang lebih luas dari peran pelaku (atau peran pelaku sendiri).
  const blocked = editing && !locked && role.can_manage === false;
  const viewOnly = editing && !canManage;   // PR-T6 — tanpa `permission.update`: mode baca
  const readOnly = locked || blocked || viewOnly;
  const originalAssignable = useMemo(() => new Set(role?.assignable_roles || []), [role]);
  const [assignable, setAssignable] = useState(() => new Set(role?.assignable_roles || []));
  const assignableChanged = [...new Set([...assignable, ...originalAssignable])].some((v) => assignable.has(v) !== originalAssignable.has(v));
  const toggleAssignable = (id) => setAssignable((a) => { const n = new Set(a); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const custom = editing ? Boolean(role.custom) : true;
  const originalPerms = useMemo(() => permsOf(role || template), [role, template]);
  const original = useMemo(() => Object.fromEntries(Object.entries(levelsFromPerms(originalPerms, modules)).map(([k, v]) => [k, v.level])), [originalPerms, modules]);
  const initLabel = role?.label || (template ? `${template.label} (salinan)` : "");
  const initDesc = role?.description || template?.description || "";
  const [label, setLabel] = useState(initLabel);
  const [description, setDescription] = useState(initDesc);
  const initBase = role?.base_role || (template ? (template.custom ? template.base_role : template.id) : "") || "";
  const [baseRole, setBaseRole] = useState(initBase);
  const baseChanged = editing && custom && baseRole !== (role.base_role || "");
  const [baseAsk, setBaseAsk] = useState(null);   // PR-T6 — {to, before, after} konfirmasi ganti peran dasar
  const [perms, setPerms] = useState(originalPerms);
  const originalHidden = useMemo(() => new Set(role?.hidden_views || template?.hidden_views || []), [role, template]);
  const [hidden, setHidden] = useState(() => new Set(role?.hidden_views || template?.hidden_views || []));
  const hiddenChanged = [...new Set([...hidden, ...originalHidden])].filter((v) => hidden.has(v) !== originalHidden.has(v));
  const toggleView = (id) => setHidden((h) => { const n = new Set(h); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const setViews = (ids, show) => setHidden((h) => { const n = new Set(h); ids.forEach((id) => (show ? n.delete(id) : n.add(id))); return n; });
  // Keputusan owner 2026-10-21 — akses SEMUA PT dapat diatur per peran (bawaan & kustom); peran baru mengikuti peran
  // dasarnya sampai admin mengubahnya.
  const initCross = Boolean(role ? role.cross_entity : template?.cross_entity);
  const [cross, setCross] = useState(initCross);
  const [crossTouched, setCrossTouched] = useState(false);
  const crossChanged = cross !== initCross;
  // PR-T4 — sifat peran (cakupan data, halaman awal, kategori kerja, alamat notifikasi): perubahan yang belum disimpan.
  const [traitsDraft, setTraitsDraft] = useState({});
  const traitsOut = traitPayload({ role: editing ? role : null, draft: traitsDraft });
  const traitsChanged = Object.keys(traitsOut).length > 0;
  const traitLines = traitChangeLines({ role: editing ? role : null, baseRole, roles, draft: traitsDraft });
  const [advanced, setAdvanced] = useState({});   // moduleId → true (panel lanjutan terbuka)
  const [confirm, setConfirm] = useState(false);
  const [danger, setDanger] = useState(null);   // null | "delete" | "reset" | "follow"
  const [review, setReview] = useState(null);   // PR-T6 — {accounts, msg} sesudah lintas PT dimatikan
  const [tab, setTab] = useState("akses");
  // PR-T9 — izin baru peran dasar yang belum diikuti peran kustom ini.
  const pendingCount = editing ? (role.pending_from_base_count || 0) : 0;
  const pendingList = Object.entries((editing && role.pending_from_base) || {}).map(([res, acts]) =>
    `${labels?.resource_labels?.[res] || res}: ${(acts || []).map((a) => labels?.action_labels?.[`${res}.${a}`]
      || labels?.action_labels?.[a] || a).join(", ")}`).join("; ");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [discard, setDiscard] = useState(false);
  const [conflict, setConflict] = useState(false);
  const levelInfo = useMemo(() => levelsFromPerms(perms, modules), [perms, modules]);
  const levels = useMemo(() => Object.fromEntries(Object.entries(levelInfo).map(([k, v]) => [k, v.level])), [levelInfo]);
  // PR-T6 — SATU pratinjau server (±500 ms sesudah perubahan terakhir): ringkasan peran, menu tambahan peran bawaan,
  // notifikasi giliran.
  const previewInput = { roleId: editing ? role.id : "", custom, baseRole, perms, traits: traitsOut, cross };
  const preview = useRolePreview(previewInput, { enabled: !locked });
  const summary = preview.data?.summary || null;

  const groups = useMemo(() => {
    const out = [];
    for (const m of modules) {
      let g = out.find((x) => x.name === m.group);
      if (!g) { g = { name: m.group, items: [] }; out.push(g); }
      g.items.push(m);
    }
    return out;
  }, [modules]);

  const changes = modules.filter((m) => moduleActionsChanged(perms, originalPerms, m));
  // PR-T5 — ringkasan empat keadaan (sebagian tidak lagi dihitung sebagai "semua aksi").
  const isPartial = (m) => Boolean(levelInfo[m.id]?.partial);
  const counts = [
    { id: "manage", label: "semua aksi", tone: "text-kn-success-text", n: modules.filter((m) => levels[m.id] === "manage" && !isPartial(m)).length },
    { id: "partial", label: "sebagian", tone: "text-kn-warning-text", n: modules.filter(isPartial).length },
    { id: "view", label: "lihat", tone: "text-kn-action", n: modules.filter((m) => levels[m.id] === "view").length },
    { id: "none", label: "tidak ada", tone: "text-kn-text-2", n: modules.filter((m) => levels[m.id] === "none").length },
  ];
  // PR-T5 — aksi berisiko yang DITAMBAHKAN simpan ini (kalimat akibat dari `sensitive_actions` server).
  const riskyAdded = sensitiveAdded(perms, originalPerms, modules);
  const rl = labels?.resource_labels || {};
  const al = labels?.action_labels || {};
  const actLabel = (res, a) => al[`${res}.${a}`] || al[a] || a;
  const diffText = (m) => actionDiff(perms, originalPerms, m).map(({ resource, added, removed }) =>
    `${rl[resource] || resource}: ${[added.map((a) => `+${actLabel(resource, a)}`).join(", "),
      removed.map((a) => `−${actLabel(resource, a)}`).join(", ")].filter(Boolean).join(" · ")}`);
  const stateText = (m, lvl, info) => (info?.partial ? partialLabel(info.held, info.total) : levelLabel(lvl, m));
  const nameError = custom && label.trim().length < 2 ? "Nama peran minimal 2 karakter." : "";
  const managesAccounts = ["create", "update"].some((a) => (perms?.user || []).includes(a));
  const anyChange = changes.length > 0 || hiddenChanged.length > 0 || crossChanged || assignableChanged || traitsChanged || baseChanged;
  const canSave = !readOnly && !nameError && (anyChange || (!editing) || label !== role?.label || description !== (role?.description || ""));

  const dirty = !readOnly && (anyChange || label !== initLabel || description !== initDesc);
  const requestClose = () => { if (busy) return; if (dirty) setDiscard(true); else onClose?.(); };
  // Fase 3 · P1 — INV-UI-10: Esc lewat tumpukan lapisan bersama (dropdown di dalam laci menutup dirinya saja).
  // Urutan tutup tetap: dialog buang-perubahan → konfirmasi → dialog bahaya → laci. Callback stabil (ref) supaya
  // entri tumpukan tidak dipasang ulang tiap render (urutan lapisan terjaga). Dialog ConfirmModal menutup dirinya sendiri.
  const escRef = useRef(null);
  escRef.current = () => {
    if (baseAsk || review) return;
    if (discard) setDiscard(false); else if (confirm) setConfirm(false); else if (danger) setDanger(null); else requestClose();
  };
  const onEscape = useCallback(() => escRef.current?.(), []);
  useEscapeClose(true, onEscape);

  // PR-T6 — "Salin hak akses dari…" hanya menyalin centang (dulu juga menetapkan peran dasar & lintas PT).
  const copyFrom = (rid) => {
    const src = roles.find((r) => r.id === rid);
    if (src) setPerms(permsOf(src));
  };
  // PR-T6 — "Peran dasar": peran baru langsung; peran yang sudah ada lewat konfirmasi berisi sifat yang mengikutinya.
  const chooseBase = (to) => {
    if (to === baseRole) return;
    if (!editing) {
      setBaseRole(to);
      if (!crossTouched) setCross(Boolean(roles.find((r) => r.id === to)?.cross_entity));   // ikut peran dasar
      return;
    }
    setBaseAsk({ to, before: summary?.follows_base || [], after: null });
    Promise.resolve().then(() => previewAccessRole(previewBody({ ...previewInput, baseRole: to })))
      .then((r) => setBaseAsk((a) => (a && a.to === to ? { ...a, after: r?.summary?.follows_base || [] } : a)))
      .catch(() => setBaseAsk((a) => (a && a.to === to ? { ...a, after: [] } : a)));
  };
  // PR-T5 — modul yang tidak punya tingkat itu (mis. "Lihat saja" pada modul sakelar) dibiarkan apa adanya.
  const setAll = (lvl) => setPerms((p) => modules.reduce((acc, m) => (levelsAvailable(m).includes(lvl) ? applyLevel(acc, m, lvl) : acc), p));
  const setModuleLevel = (m, lvl) => setPerms((p) => applyLevel(p, m, lvl));
  const onToggleAction = (m) => (res, act) => setPerms((p) => toggleAction(p, m, res, act));
  const onSetResource = (m) => (res, all) => setPerms((p) => setResource(p, m, res, all));

  const submit = async () => {
    setBusy(true); setError("");
    try {
      let res;
      if (editing) {
        res = await patchAccessRole(role.id, {
          ...(custom ? { label: label.trim(), description: description.trim() } : {}),
          permissions: perms, hidden_views: [...hidden], expected_version: role.version,
          ...(crossChanged ? { cross_entity: cross } : {}),
          ...(baseChanged ? { base_role: baseRole } : {}),
          ...(canEditAssignable && assignableChanged ? { assignable_roles: [...assignable] } : {}),
          ...(traitsChanged ? { traits: traitsOut } : {}),
        });
        const msg = `Hak akses peran “${res.label}” disimpan. ${res.users} akun terpengaruh — berlaku otomatis dalam ≤1 menit.`;
        if ((res.accounts_to_review || []).length) { setConfirm(false); setReview({ accounts: res.accounts_to_review, msg }); return; }
        onSaved?.(msg);
      } else {
        // PR-T6 (PR-UX-37) — menu tersembunyi ikut dalam satu panggilan pembuatan.
        res = await createAccessRole({ label: label.trim(), description: description.trim(), base_role: baseRole, permissions: perms,
          ...(hidden.size ? { hidden_views: [...hidden] } : {}),
          ...(crossTouched ? { cross_entity: cross } : {}), ...(traitsChanged ? { traits: traitsOut } : {}) });
        if (canEditAssignable && managesAccounts && assignable.size) res = await patchAccessRole(res.id, { assignable_roles: [...assignable] });
        onSaved?.(`Peran “${res.label}” dibuat. Berikan ke akun lewat tab Akun & Akses.`);
      }
    } catch (e) {
      setConflict(e.response?.status === 409 && e.response?.data?.detail?.code === "ROLE_VERSION_CONFLICT");
      setError(errText(e, "Gagal menyimpan peran.")); onError?.(errText(e, "Gagal menyimpan peran.")); setConfirm(false);
    } finally { setBusy(false); }
  };

  const remove = async () => {
    setBusy(true);
    try { await deleteAccessRole(role.id); onSaved?.(`Peran “${role.label}” dihapus.`); }
    catch (e) { setError(errText(e, "Gagal menghapus peran.")); setDanger(null); }
    finally { setBusy(false); }
  };

  const followBase = async () => {
    setBusy(true);
    try {
      const res = await followBaseAccessRole(role.id, []);
      const n = Object.values(res.added || {}).reduce((t, a) => t + a.length, 0);
      onSaved?.(`Peran “${role.label}” kini mengikuti ${n} izin baru peran dasar.`);
    } catch (e) { setError(errText(e, "Gagal mengikuti izin peran dasar.")); setDanger(null); }
    finally { setBusy(false); }
  };

  const reset = async () => {
    setBusy(true);
    try { await resetAccessRole(role.id); onSaved?.(`Peran “${role.label}” dikembalikan ke bawaan: izin, menu, dan akses lintas PT.`); }
    catch (e) { setError(errText(e, "Gagal mengembalikan bawaan.")); setDanger(null); }
    finally { setBusy(false); }
  };

  const templateBase = template ? (template.custom ? template.base_role : template.id) : "";
  const title = editing
    ? `${viewOnly ? "Lihat Hak Akses" : "Hak Akses"} · ${role.label}`
    : (template ? `Duplikat Peran · ${template.label} (${templateBase ? `peran dasar: ${baseLabelOf(roles, templateBase)}` : "tanpa peran dasar"})` : "Buat Peran Baru");
  const accountsTotal = editing ? (role.users || 0) + (role.users_inactive || 0) : 0;
  const deleteHint = editing && custom && !role.deletable
    ? `Masih dipakai ${accountsTotal} akun (${role.users_inactive || 0} nonaktif) — pindahkan akunnya dulu.` : "";
  // Pola UI 16 Nov (M43) — keterangan judul & kotak "berlaku otomatis" dulu dipajang terbuka; kini di ikon ? judul.
  const headHelp = [
    !custom && role?.description ? String(role.description).replace(/\.?\s*$/, ".") : "",
    viewOnly ? "Anda bisa melihat hak peran ini, tetapi tidak mengubahnya."
      : "Pilih tingkat akses tiap modul. Perubahan berlaku untuk semua akun dengan peran ini.",
    "Tingkat: Tidak ada (menu tersembunyi) · Lihat saja (baca tanpa tombol ubah) · Semua aksi; Sebagian = hanya sebagian "
      + "aksi (atur di Rinci).",
    "Perubahan berlaku otomatis untuk yang sedang masuk (paling lama 1 menit atau saat muat ulang) — tidak perlu "
      + "keluar-masuk lagi. Notifikasi ikut menyesuaikan: hanya layar yang boleh dibuka yang muncul di lonceng, dan "
      + "\"giliran Anda\" dikirim ke peran yang memegang wewenangnya.",
  ].filter(Boolean).join(" ");

  return (
    <div className="modal-overlay" data-testid="role-editor-drawer"
         onClick={(e) => { if (e.target === e.currentTarget) requestClose(); }}>
      {/* Pola UI 16 Nov — kepala, tab, dan kaki tetap; hanya isi yang bergulir (dulu dua bilah gulir bertumpuk). */}
      <div className="modal-card flex flex-col" style={{ maxWidth: 1080, width: "96vw", overflow: "hidden" }}>
        <div className="flex items-center gap-2 border-b border-kn-divider px-4 py-2.5">
          <ShieldCheck size={16} className="shrink-0 text-kn-action" aria-hidden="true" />
          <h3 className="min-w-0 text-fs-14 font-bold" data-testid="role-editor-title">{title}</h3>
          {editing && !custom && <span className="badge-muted" data-testid="role-editor-builtin-badge">bawaan sistem</span>}
          {locked && <span className="badge-red"><Lock size={11} /> dikunci</span>}
          <HelpTip text={headHelp} testId="role-editor-help" label="Tentang editor hak akses" />
          <button type="button" className="icon-button ml-auto shrink-0" aria-label="Tutup" data-testid="role-editor-close" onClick={requestClose}><X size={14} /></button>
        </div>
        {editing && (
          <div className="px-4 pt-2">
            <PageTabs testId="role-editor-tabs" value={tab} onChange={setTab} ariaLabel="Editor peran"
                      tabs={[{ key: "akses", label: "Hak akses" }, { key: "riwayat", label: "Riwayat" }]} />
          </div>
        )}

        {tab === "riwayat" && editing ? (
          <div className="min-h-0 flex-1 p-4" style={{ overflowY: "auto" }}><RoleHistoryTab roleId={role.id} /></div>
        ) : (
        <div className="cfg-mx-scroll grid min-h-0 flex-1 content-start gap-3 p-4 lg:grid-cols-[minmax(0,1fr)_280px]" style={{ overflowY: "auto" }}>
          <div className="min-w-0 space-y-2">
            {custom && (
              <div className="grid gap-2 sm:grid-cols-2">
                <div className="grid gap-1">
                  <label className="kicker" htmlFor="role-editor-label">Nama peran</label>
                  <input className="field" id="role-editor-label" data-testid="role-editor-label" value={label} placeholder="mis. Staf Penagihan" disabled={readOnly}
                         onChange={(e) => setLabel(e.target.value)} />
                </div>
                <div className="grid gap-1">
                  <label className="kicker" htmlFor="role-editor-description">Keterangan singkat (opsional)</label>
                  <input className="field" id="role-editor-description" data-testid="role-editor-description" value={description} placeholder="Untuk siapa peran ini?" disabled={readOnly}
                         onChange={(e) => setDescription(e.target.value)} />
                </div>
              </div>
            )}

            {/* Pola UI 16 Nov (M43) — peringatan masing-masing SATU baris kecil (dulu kotak berparagraf). */}
            {blocked && (
              <p className="cfg-role-line warn" data-testid="role-editor-no-manage">
                <Lock size={12} aria-hidden="true" /> Peran Anda tidak diberi wewenang mengelola akun/peran ini. Peran ini hanya bisa diubah Admin.
              </p>
            )}
            {locked && (
              <p className="cfg-role-line err" data-testid="role-editor-locked">
                <Lock size={12} aria-hidden="true" /> Peran Admin selalu punya semua akses dan tidak bisa diubah, supaya tidak ada yang terkunci keluar dari sistem.
              </p>
            )}
            {pendingCount > 0 && (
              <p className="cfg-role-line" data-testid="role-editor-pending-base">
                <Info size={12} className="text-kn-action" aria-hidden="true" />
                <span>Peran dasar {role.base_role_label || role.base_role} mendapat {pendingCount} izin baru yang belum diikuti peran ini.</span>
                {canFollow && !readOnly && (
                  <button type="button" className="secondary-button btn-sm" data-testid="role-editor-follow-base" disabled={busy}
                          onClick={() => setDanger("follow")}>
                    Ikuti peran dasar
                  </button>
                )}
              </p>
            )}
            {!locked && (custom || !readOnly) && (
              <RoleBaseControls custom={custom} roleId={role?.id} baseRole={baseRole} roles={roles} disabled={readOnly || busy}
                                onChooseBase={chooseBase} onCopy={copyFrom} />
            )}
            {/* PR-T6 — "Ringkasan peran" dari pratinjau server; kini satu baris + "Rincian". */}
            {!locked && (
              <RoleSummaryPanel summary={summary} loading={preview.loading} error={preview.error && !summary} onRetry={preview.retry}
                                header={(
                                  <span className="inline-flex flex-wrap items-center gap-x-2 font-semibold" data-testid="role-editor-summary">
                                    {counts.map((c) => (
                                      <span key={c.id} data-testid={`role-editor-count-${c.id}`} className={c.tone}>
                                        {c.n} {c.label}
                                      </span>
                                    ))}
                                  </span>
                                )} />
            )}

            <div className="cfg-mx" data-testid="role-editor-matrix">
              <div className="cfg-mx-row cfg-mx-head">
                <span>Modul</span>
                <span className="cfg-mx-levels">
                  {LEVELS.map((l) => <span key={l.id} className="cfg-mx-cell">{l.label}</span>)}
                </span>
                <span className="cfg-mx-cell">Rinci</span>
              </div>
              {!readOnly && (
                <div className="cfg-mx-row cfg-mx-all" data-testid="role-editor-all">
                  <span className="inline-flex items-center gap-1">
                    Semua modul
                    <HelpTip text="Menyetel satu tingkat untuk semua modul sekaligus. Modul yang tidak punya tingkat itu (mis. modul sakelar tanpa Lihat saja) dibiarkan apa adanya."
                             testId="role-editor-all-help" label="Tentang Semua modul" />
                  </span>
                  <span className="cfg-mx-levels">
                    {LEVELS.map((l) => (
                      <span key={l.id} className="cfg-mx-cell">
                        <button type="button" data-testid={`role-editor-all-${l.id}`} onClick={() => setAll(l.id)}
                                className="secondary-button btn-sm" aria-label={`Jadikan semua modul: ${l.label}`}
                                title={`Jadikan semua modul: ${l.label}`} disabled={busy}>
                          Semua
                        </button>
                      </span>
                    ))}
                  </span>
                  <span />
                </div>
              )}
              {groups.map((g) => (
                <div key={g.name} data-testid={`role-editor-group-${g.name}`}>
                  <p className="cfg-mx-group">{g.name}</p>
                  {g.items.map((m) => (
                    <RoleModuleRow key={m.id} module={m} value={levels[m.id]} original={original[m.id]}
                                   dirty={moduleActionsChanged(perms, originalPerms, m)}
                                   originalLabel={stateText(m, original[m.id], levelsFromPerms(originalPerms, [m])[m.id])}
                                   partial={levelInfo[m.id]?.partial} held={levelInfo[m.id]?.held}
                                   total={levelInfo[m.id]?.total} disabled={readOnly || busy}
                                   onChange={(v) => setModuleLevel(m, v)}
                                   advanced={!!advanced[m.id]}
                                   onToggleAdvanced={readOnly ? null : () => setAdvanced((s) => ({ ...s, [m.id]: !s[m.id] }))}>
                      <div className="space-y-2">
                        <RoleNavTree module={m} hidden={hidden} original={originalHidden} disabled={readOnly || busy}
                                     off={levels[m.id] === "none"} onToggle={toggleView} onSetMany={setViews} />
                        <RoleAdvancedPanel module={m} perms={perms} original={originalPerms} labels={labels} disabled={readOnly || busy}
                                           onToggle={onToggleAction(m)} onSetResource={onSetResource(m)} />
                      </div>
                    </RoleModuleRow>
                  ))}
                </div>
              ))}
            </div>
          </div>

          <div className="cfg-role-side min-w-0 space-y-2">
            <div className="rounded-md border border-kn-divider bg-white p-2.5" data-testid="role-editor-settings">
              <CrossEntityBox cross={cross} disabled={readOnly || busy} role={editing && !locked ? role : null}
                              onChange={(v) => { setCross(v); setCrossTouched(true); }} />
              <RoleTraitsPanel role={editing ? role : null} baseRole={baseRole} roles={roles} perms={perms}
                               draft={traitsDraft} onChange={setTraitsDraft} disabled={readOnly || busy} />
              {editing && <RoleAccountsList role={role} roles={roles} canMove={!readOnly} onMoved={onRefresh} onError={onError} />}
              {!locked && (
                <RoleNotifPreview roleId={editing ? role.id : ""} baseRole={baseRole} permissions={perms}
                                  saved={(editing ? role.turn_alerts : template?.turn_alerts) || []}
                                  alerts={preview.data ? (preview.data.turn_alerts || []) : null} loading={preview.loading} />
              )}
              {baseRole && custom && <p className="mt-1 text-fs-12 text-kn-text-2">Menu warisan mengikuti peran dasar: <b>{baseLabelOf(roles, baseRole)}</b>.</p>}
            </div>
            {managesAccounts && !locked && (
              <AssignableBox roles={roles} assignable={assignable} canEdit={canEditAssignable} disabled={busy || readOnly}
                             onToggle={toggleAssignable} />
            )}
            <RoleMenuPreview modules={modules} levels={levels} baseRole={editing ? (custom ? baseRole : "") : baseRole} perms={perms} hidden={hidden}
                             builtinId={editing && !custom ? role.id : ""} navAdded={preview.data?.nav_added || []} />
          </div>
        </div>
        )}

        {error && <div className="notice-bar danger !py-1.5 mx-4 mb-2" data-testid="role-editor-error"><span className="text-fs-12">{error}</span>
          {conflict && <button type="button" className="secondary-button btn-sm ml-2" data-testid="role-editor-reload" onClick={() => onRefresh?.()}>Muat ulang versi terbaru</button>}</div>}

        <div className="flex flex-wrap items-center gap-2 border-t border-kn-divider px-4 py-3">
          {editing && custom && !viewOnly && (
            <>
              <button type="button" className="danger-button" data-testid="role-editor-delete" disabled={busy || !role.deletable || blocked}
                      title={deleteHint} onClick={() => setDanger("delete")}>
                <Trash2 size={13} /> Hapus peran
              </button>
              {deleteHint && <span className="text-fs-12 text-kn-text-2" data-testid="role-editor-delete-hint">{deleteHint}</span>}
            </>
          )}
          {editing && !custom && !locked && !viewOnly && role.modified && (
            <button type="button" className="secondary-button" data-testid="role-editor-reset" disabled={busy || blocked} onClick={() => setDanger("reset")}>
              <RotateCcw size={13} /> Kembalikan ke bawaan
            </button>
          )}
          <div className="ml-auto flex gap-2">
            <button type="button" className="secondary-button" data-testid="role-editor-cancel" onClick={requestClose}>{viewOnly ? "Tutup" : "Batal"}</button>
            {!viewOnly && (
              <button type="button" className="primary-button" data-testid="role-editor-save" disabled={busy || !canSave} onClick={() => setConfirm(true)}>
                {busy ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                {editing ? "Simpan Perubahan" : "Buat Peran"}
              </button>
            )}
          </div>
        </div>

        {danger && (
          <RoleDangerDialog kind={danger} roleLabel={role.label} busy={busy} extra={{ list: pendingList }}
                            onCancel={() => setDanger(null)}
                            onConfirm={danger === "delete" ? remove : (danger === "follow" ? followBase : reset)} />
        )}
        {baseAsk && (
          <BaseChangeDialog ask={baseAsk} roles={roles} onCancel={() => setBaseAsk(null)}
                            onConfirm={() => { setBaseRole(baseAsk.to); setBaseAsk(null); }} />
        )}
        {review && (
          <AccountsReviewDialog accounts={review.accounts}
                                onClose={() => { const m = review.msg; setReview(null); onSaved?.(m); }}
                                onOpenAccounts={onOpenAccounts ? () => { const m = review.msg; setReview(null); onSaved?.(m); onOpenAccounts(); } : null} />
        )}

        {discard && (
          <div className="modal-overlay" data-testid="role-editor-discard" onClick={(e) => { if (e.target === e.currentTarget) setDiscard(false); }}>
            <div className="modal-card p-4" style={{ maxWidth: 420, width: "92vw" }}>
              <h4 className="text-[13px] font-bold">Buang perubahan yang belum disimpan?</h4>
              <p className="mt-1 text-fs-12 text-kn-text-2" data-testid="role-editor-discard-summary">
                {changes.length} modul dan {hiddenChanged.length} menu/tab berubah{label !== initLabel || description !== initDesc ? ", nama/keterangan juga diubah" : ""}. Pilihan Anda akan hilang bila ditutup.
              </p>
              <div className="mt-3 flex justify-end gap-2">
                <button type="button" className="secondary-button" data-testid="role-editor-discard-keep" autoFocus onClick={() => setDiscard(false)}>Lanjut mengedit</button>
                <button type="button" className="danger-button" data-testid="role-editor-discard-confirm" onClick={() => { setDiscard(false); onClose?.(); }}>Buang &amp; tutup</button>
              </div>
            </div>
          </div>
        )}

        {confirm && (
          <div className="modal-overlay" data-testid="role-editor-confirm" onClick={(e) => { if (e.target === e.currentTarget) setConfirm(false); }}>
            <div className="modal-card" style={{ maxWidth: 520, width: "92vw" }}>
              <div className="border-b border-kn-divider px-4 py-3">
                <h4 className="text-[13px] font-bold">Periksa sebelum menyimpan</h4>
                <p className="text-fs-12 text-kn-text-2">
                  {editing ? `${role.users} akun berperan “${role.label}” akan langsung mengikuti hak baru.` : `Peran “${label.trim()}” akan dibuat dengan akses berikut.`}
                </p>
              </div>
              <div className="max-h-64 overflow-auto p-4">
                {editing && !anyChange && <p className="text-fs-12 text-kn-text-2">Hanya nama/keterangan yang berubah.</p>}
                {baseChanged && (
                  <p className="mb-1 text-fs-12" data-testid="role-editor-confirm-base">
                    Peran dasar: {baseLabelOf(roles, role.base_role)} → <b>{baseLabelOf(roles, baseRole)}</b> (hak akses tidak berubah)
                  </p>
                )}
                {traitLines.map((t) => (
                  <p key={t.key} className="mb-1 text-fs-12" data-testid={`role-editor-confirm-trait-${t.key}`}>{t.text}</p>
                ))}
                {crossChanged && (
                  <p className="mb-1 text-fs-12" data-testid="role-editor-confirm-cross">
                    Akses semua PT: {initCross ? "aktif" : "mati"} → <b>{cross ? "aktif" : "mati"}</b>
                  </p>
                )}
                {hiddenChanged.length > 0 && (
                  <p className="mb-1 text-fs-12" data-testid="role-editor-confirm-tabs">Menu/tab: {hiddenChanged.map((v) => `${titleOf(v)} → ${hidden.has(v) ? "disembunyikan" : "ditampilkan"}`).join(" · ")}</p>
                )}
                <ul className="space-y-1">
                  {(editing ? changes : modules.filter((m) => levels[m.id] !== "none")).map((m) => (
                    <li key={m.id} className="text-fs-12 text-kn-text" data-testid={`role-editor-confirm-${m.id}`}>
                      <b>{m.label}</b>: {editing ? `${stateText(m, original[m.id], levelsFromPerms(originalPerms, [m])[m.id])} → ` : ""}<span className="font-semibold text-kn-action">{stateText(m, levels[m.id], levelInfo[m.id])}</span>
                      {/* PR-T5 — aksi yang ditambah & dicabut per halaman: "{halaman}: +aksi, +aksi · −aksi". */}
                      {diffText(m).map((t) => (
                        <span key={t} className="block pl-2 text-fs-12 text-kn-text" data-testid={`role-editor-confirm-diff-${m.id}`}>{t}</span>
                      ))}
                    </li>
                  ))}
                </ul>
                {riskyAdded.length > 0 && (
                  <p className="mt-2 text-fs-12 font-semibold text-kn-warning-text" data-testid="role-editor-confirm-sensitive">
                    Perhatian — peran ini akan bisa: {riskyAdded.join("; ")}.
                  </p>
                )}
              </div>
              <div className="flex justify-end gap-2 border-t border-kn-divider px-4 py-3">
                <button type="button" className="secondary-button" data-testid="role-editor-confirm-cancel" onClick={() => setConfirm(false)}>Periksa lagi</button>
                <button type="button" className="primary-button" data-testid="role-editor-confirm-save" disabled={busy} onClick={submit}>
                  {busy ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} Ya, simpan
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
