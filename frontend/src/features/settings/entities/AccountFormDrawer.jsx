/**
 * AccountFormDrawer (FASE E-3 / E2.1–E2.2) — buat & ubah akun.
 *
 * Aturan yang DITAMPILKAN, bukan disembunyikan:
 *  · Kalau akun ditautkan ke karyawan HR, badan usaha utamanya HANYA-BACA dan
 *    diambil dari HR — supaya penggajian dan hak akses tidak pernah bertentangan.
 *  · Peran yang tidak lintas PT terkunci di PT-nya; penugasan tambahan harus disebut satu per
 *    satu (bukan “semua PT” diam-diam). PR-T6: "lintas PT" dibaca dari nilai peran di server
 *    (`GET /api/roles` → `cross_entity`), bukan daftar tertulis Admin/Manajer.
 *  · Mengubah peran/penugasan MENCABUT sesi — dikatakan sebelum disimpan supaya
 *    admin tidak bingung kenapa orangnya tiba-tiba diminta masuk lagi.
 */
import { useEffect, useMemo, useState } from "react";
import { X, Save, Loader2, UserCog, Info, Search, Link2, Star } from "lucide-react";

import KNSelect from "../../../components/KNSelect";
import { AccountLocationScope } from "./AccountLocationScope";
import AccountRoleSummary from "./AccountRoleSummary";
import useDomainEnums from "../../../hooks/useDomainEnums";
import { entityFull } from "../../../utils/entityLabel";
import { askConfirm } from "../../../services/confirmService";
import { createUser, patchUser, availableEmployees, ROLE_OPTIONS, publicRoles,
  errText, manageableRoles } from "./entityApi";

export default function AccountFormDrawer({ user, entities = [], selectedEntity,
  onClose, onSaved, onError, canViewRoles = false, canConfigureAi = false }) {
  const editing = Boolean(user?.id);
  const [form, setForm] = useState(() => ({
    name: user?.name || "",
    email: user?.email || "",
    phone: user?.phone || "",
    role: user?.role || "",   // PR-T6 — tanpa pilihan awal pada akun baru (dulu Sales); wajib dipilih
    password: "",
    employee_id: user?.employee_id || "",
    home_entity_id: user?.home_entity_id
      || (selectedEntity && selectedEntity !== "all" ? selectedEntity : (entities[0]?.id || "")),
    allowed_entity_ids: user?.allowed_entity_ids || [],
    // FASE L — lini produk yang boleh dikerjakan. KOSONG = SEMUA LINI (bawaan).
    allowed_line_codes: user?.allowed_line_codes || [],
    location_site_ids: user?.location_site_ids || [],
    location_warehouse_ids: user?.location_warehouse_ids || [],
  }));
  // AG-T2 (K-45) — sakelar Asisten Keuangan per akun; hanya pemegang `ai.configure` yang bisa mengubahnya.
  const savedAiFinance = Boolean(user?.ai_finance?.enabled);
  const [aiFinance, setAiFinance] = useState(savedAiFinance);
  // AG-T3 — golongan kartu tindakan per akun: `B` = boleh menyetujui kartu uang masuk (kwitansi, pencocokan bank,
  // alokasi titipan, ulang jurnal gagal). Tetap butuh izin & sakelar PT; diubah pemegang `ai.configure`.
  const savedClassB = (user?.ai_finance?.classes || []).includes("B");
  const [classB, setClassB] = useState(savedClassB);
  const [empQuery, setEmpQuery] = useState("");
  const [employees, setEmployees] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // UAT 24 Okt (audit UI tahap 2, G5-24) — kotak merah "Nama wajib diisi / Email wajib diisi" dulu sudah tampil saat
  // form baru dibuka. Kini galat muncul setelah pengguna mencoba menyimpan.
  const [tried, setTried] = useState(false);

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  // PR-T6 — daftar peran server: lintas PT (`cross_entity`) dan peran dasar peran kustom untuk label pilihan.
  const [serverRoles, setServerRoles] = useState(null);
  useEffect(() => {
    let alive = true;
    Promise.resolve().then(() => publicRoles()).then((r) => { if (alive) setServerRoles(r || []); })
      .catch(() => { if (alive) setServerRoles([]); });
    return () => { alive = false; };
  }, []);
  const roleRow = (serverRoles || []).find((r) => r.id === form.role);
  const isCross = Boolean(roleRow?.cross_entity);
  // PR-T1 — pilihan peran hanya yang boleh dikelola pelaku (null = semua). Peran akun yang sedang diubah tetap
  // tampil supaya isian tidak kosong.
  const [allowedRoles, setAllowedRoles] = useState(null);
  useEffect(() => {
    let alive = true;
    manageableRoles()
      .then((r) => { if (alive) setAllowedRoles(r.all ? null : new Set(r.roles || [])); })
      .catch(() => { if (alive) setAllowedRoles(null); });
    return () => { alive = false; };
  }, []);
  const baseName = (id) => (serverRoles || []).find((r) => r.id === id)?.label || id;
  const roleOptions = ((serverRoles && serverRoles.length)
    ? serverRoles.map((r) => ({ value: r.id, label: r.custom && r.base_role ? `${r.label} · peran dasar ${baseName(r.base_role)}` : r.label }))
    : ROLE_OPTIONS.map((r) => ({ value: r.value, label: r.label })))
    .filter((r) => !allowedRoles || allowedRoles.has(r.value) || (editing && r.value === user?.role));
  useEffect(() => {
    if (!editing && allowedRoles && form.role && !allowedRoles.has(form.role)) set({ role: "" });
  }, [allowedRoles]);   // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let alive = true;
    availableEmployees({ q: empQuery, entity_id: "" })
      .then((rows) => { if (alive) setEmployees(rows); })
      .catch(() => { if (alive) setEmployees([]); });
    return () => { alive = false; };
  }, [empQuery]);

  const linkedEmployee = useMemo(
    () => employees.find((e) => e.id === form.employee_id) || user?.employee || null,
    [employees, form.employee_id, user]
  );
  const homeFromHr = Boolean(form.employee_id && linkedEmployee?.entity_id);
  const effectiveHome = homeFromHr ? linkedEmployee.entity_id : form.home_entity_id;

  const willRevoke = editing && (
    form.role !== user.role
    || effectiveHome !== user.home_entity_id
    || JSON.stringify([...(form.allowed_entity_ids || [])].sort())
       !== JSON.stringify([...(user.allowed_entity_ids || [])].sort())
    // FASE L — mengubah hak lini juga mencabut sesi (hak baca berubah).
    || JSON.stringify([...(form.allowed_line_codes || [])].sort())
       !== JSON.stringify([...(user.allowed_line_codes || [])].sort())
    || Boolean(form.password)
  );

  const errors = useMemo(() => {
    const out = [];
    if (!form.name.trim()) out.push("Nama wajib diisi.");
    if (!form.email.trim()) out.push("Email wajib diisi (dipakai untuk masuk).");
    if (!form.role) out.push("Peran wajib dipilih.");
    if (!editing && !form.password) out.push("Sandi awal wajib diisi.");
    if (form.password && form.password.length < 8) {
      out.push("Sandi minimal 8 karakter.");
    }
    if (!effectiveHome) out.push("Badan usaha utama wajib dipilih.");
    return out;
  }, [form, editing, effectiveHome]);

  // PR-T6 — melepas / mengganti tautan karyawan yang sudah tersimpan meminta konfirmasi.
  const chooseEmployee = async (id) => {
    const saved = editing ? (user?.employee_id || "") : "";
    if (saved && form.employee_id === saved && id !== saved) {
      const name = linkedEmployee?.name || user?.employee?.name || "karyawan ini";
      const ok = await askConfirm({ title: `Lepas tautan ke ${name}?`,
        message: "Data karyawan lama tidak lagi menunjuk akun ini setelah disimpan.", confirmLabel: "Ya, lepas" });
      if (!ok) return;
    }
    set({ employee_id: id });
  };

  const toggleAllowed = (id) => {
    setForm((f) => {
      const cur = new Set(f.allowed_entity_ids || []);
      if (cur.has(id)) cur.delete(id); else cur.add(id);
      return { ...f, allowed_entity_ids: Array.from(cur) };
    });
  };

  // FASE L — pilihan lini datang dari MASTER (`/api/enums` → product_line), bukan
  // daftar hardcode: lini keempat yang ditambah pemilik langsung bisa diberikan
  // ke akun tanpa perubahan kode.
  const { options } = useDomainEnums();
  const lineOptions = useMemo(() => options("product_line"), [options]);

  const toggleLine = (code) => {
    setForm((f) => {
      const cur = new Set(f.allowed_line_codes || []);
      if (cur.has(code)) cur.delete(code); else cur.add(code);
      return { ...f, allowed_line_codes: Array.from(cur) };
    });
  };

  const submit = async () => {
    if (errors.length) { setTried(true); return; }
    setBusy(true);
    setError("");
    try {
      if (editing) {
        const data = {
          name: form.name, email: form.email, phone: form.phone, role: form.role,
          employee_id: form.employee_id,
          ...(homeFromHr ? {} : { home_entity_id: form.home_entity_id }),
          ...(isCross ? {} : { allowed_entity_ids: form.allowed_entity_ids }),
          allowed_line_codes: form.allowed_line_codes || [],   // FASE L
          location_site_ids: form.location_site_ids || [], location_warehouse_ids: form.location_warehouse_ids || [],
          ...(form.password ? { password: form.password } : {}),
          ...(canConfigureAi && (aiFinance !== savedAiFinance || classB !== savedClassB) ? { ai_finance: {
            ...(aiFinance !== savedAiFinance ? { enabled: aiFinance } : {}),
            ...(classB !== savedClassB ? { classes: classB ? ["B"] : [] } : {}) } } : {}),
        };
        const res = await patchUser(user.id, data);
        onSaved?.(
          `Akun ${res.name} diperbarui.`
          + (res.sessions_revoked
            ? ` ${res.sessions_revoked} sesi dicabut (${(res.revoke_reasons || []).join(", ")}) —`
              + " dia perlu masuk lagi."
            : "")
        );
      } else {
        const res = await createUser({
          name: form.name, email: form.email, phone: form.phone, role: form.role,
          password: form.password,
          employee_id: form.employee_id,
          home_entity_id: form.home_entity_id,
          allowed_entity_ids: form.allowed_entity_ids,
          allowed_line_codes: form.allowed_line_codes || [],   // FASE L
          location_site_ids: form.location_site_ids || [], location_warehouse_ids: form.location_warehouse_ids || [],
        });
        onSaved?.(
          // INV-UI-02 — nama badan usaha lewat helper bersama; id teknis (`ent_ksc`)
          // TIDAK BOLEH muncul ke pengguna walau sebagai cadangan.
          `Akun ${res.name} dibuat di ${entityFull(res.home_entity)}.`
          + (res.home_from_hr ? " Badan usaha utamanya diambil dari data karyawan (HR)." : "")
        );
      }
    } catch (e) {
      setError(errText(e, "Gagal menyimpan akun."));
      onError?.(errText(e, "Gagal menyimpan akun."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-overlay" data-testid="account-form-drawer"
         onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
      <div className="modal-card" style={{ maxWidth: 620, width: "94vw" }}>
        <div className="flex items-start gap-2 border-b border-[#EFF0F2] px-4 py-3">
          <UserCog size={16} className="mt-0.5 text-[#0058CC]" />
          <div className="min-w-0 flex-1">
            <h3 className="text-[13.5px] font-bold">
              {editing ? `Ubah Akun · ${user.name}` : "Buat Akun Baru"}
            </h3>
            <p className="text-[11px] text-[#6B6B73]">
              Akun menentukan data badan usaha mana yang boleh dilihat orang ini.
            </p>
          </div>
          <button type="button" className="icon-button" aria-label="Tutup"
                  data-testid="account-form-close" onClick={onClose}>
            <X size={14} />
          </button>
        </div>

        <div className="space-y-2.5 p-4" style={{ maxHeight: "62vh", overflowY: "auto" }}>
          <div className="grid gap-2.5 sm:grid-cols-2">
            <div className="grid gap-1">
              <label className="kicker">Nama <span className="text-[#C0392B]">*</span></label>
              <input className="field" data-testid="account-form-name"
                     value={form.name} onChange={(e) => set({ name: e.target.value })} />
            </div>
            <div className="grid gap-1">
              <label className="kicker">Email untuk masuk <span className="text-[#C0392B]">*</span></label>
              <input className="field" data-testid="account-form-email"
                     value={form.email} onChange={(e) => set({ email: e.target.value })} />
            </div>
            <div className="grid gap-1">
              <label className="kicker">Telepon / WhatsApp (opsional)</label>
              <input className="field" data-testid="account-form-phone"
                     value={form.phone} onChange={(e) => set({ phone: e.target.value })} />
            </div>
            <div className="grid gap-1">
              <label className="kicker">{editing ? "Sandi baru (opsional)" : <>Sandi awal <span className="text-[#C0392B]">*</span></>}</label>
              <input className="field" type="password" data-testid="account-form-password"
                     placeholder={editing ? "biarkan kosong = tidak diubah" : "minimal 8 karakter"}
                     value={form.password}
                     onChange={(e) => set({ password: e.target.value })} />
            </div>
          </div>

          <div className="grid gap-1">
            <label className="kicker">Peran <span className="text-kn-danger-text">*</span></label>
            <KNSelect className="field" data-testid="account-form-role" placeholder="Pilih peran…"
                      value={form.role} onValueChange={(v) => set({ role: v })} options={roleOptions} />
            {allowedRoles && (
              <p className="text-[10px] text-[#8E8E93]" data-testid="account-form-role-limited">
                Hanya peran yang boleh Anda kelola yang ditampilkan.
              </p>
            )}
            {form.role && (
              <p className="text-fs-12 text-kn-text-2" data-testid="account-form-cross">
                {isCross ? "Peran ini membuka semua PT aktif." : "Peran ini hanya membuka PT yang dicentang di bawah."}
              </p>
            )}
            <AccountRoleSummary roleId={form.role} canViewRoles={canViewRoles} />
          </div>

          {/* E2.1 — taut karyawan HR */}
          <div className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2.5"
               data-testid="account-form-hr">
            <div className="mb-1.5 flex items-center gap-1.5">
              <Link2 size={13} className="text-[#0058CC]" />
              <p className="kicker !mb-0">Tautkan ke karyawan (HR)</p>
            </div>
            <div className="relative mb-1.5">
              <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-[#9A9BA3]" />
              <input className="field !pl-7 !py-1 !text-[12px]" data-testid="account-form-hr-search"
                     placeholder="Cari nama karyawan…" value={empQuery}
                     onChange={(e) => setEmpQuery(e.target.value)} />
            </div>
            <div className="max-h-28 overflow-auto">
              <button type="button" data-testid="account-form-hr-none"
                      onClick={() => chooseEmployee("")}
                      className={`mb-1 w-full rounded-md border px-2 py-1 text-left text-[11px] ${
                        !form.employee_id ? "border-[#0058CC] bg-[#EAF2FF] font-semibold"
                          : "border-[#E5E5EA] bg-white"}`}>
                Tidak ditautkan (isi badan usaha manual)
              </button>
              {form.employee_id && linkedEmployee && !employees.some((e) => e.id === form.employee_id) && (
                <button type="button" data-testid="account-form-hr-linked"
                        className="mb-1 w-full rounded-md border border-[#0058CC] bg-[#EAF2FF] px-2 py-1 text-left text-[11px] font-semibold">
                  {[linkedEmployee.code, linkedEmployee.name].filter(Boolean).join(" · ")}
                  <span className="ml-1 text-[10px] font-normal text-[#6B6B73]">(tertaut ke akun ini)</span>
                </button>
              )}
              {employees.map((e) => (
                <button key={e.id} type="button" data-testid={`account-form-hr-${e.id}`}
                        onClick={() => chooseEmployee(e.id)}
                        className={`mb-1 w-full rounded-md border px-2 py-1 text-left text-[11px] ${
                          form.employee_id === e.id
                            ? "border-[#0058CC] bg-[#EAF2FF] font-semibold"
                            : "border-[#E5E5EA] bg-white"}`}>
                  {e.code} · {e.name}
                  <span className="ml-1 text-[10px] text-[#6B6B73]">({e.entity_name})</span>
                </button>
              ))}
              {employees.length === 0 && (
                <p className="text-[10.5px] text-[#8E8E93]" data-testid="account-form-hr-empty">
                  Tidak ada karyawan tanpa akun yang cocok. Tambahkan karyawan lewat menu SDM
                  bila perlu.
                </p>
              )}
            </div>
            {!form.employee_id && (
              <p className="mt-1 flex items-start gap-1 text-[10.5px] text-[#B45309]">
                <Info size={11} className="mt-0.5 shrink-0" />
                Akun tanpa tautan HR berisiko: badan usaha akun bisa berbeda dari data
                penggajian. Tautkan bila orangnya memang karyawan.
              </p>
            )}
          </div>

          {/* Badan usaha utama */}
          <div className="grid gap-1" data-testid="account-form-home">
            <label className="kicker">Badan usaha utama <span className="text-[#C0392B]">*</span></label>
            {homeFromHr ? (
              <div className="flex items-center gap-2 rounded-md border border-[#BFE3CC] bg-[#EEF9F1] px-2.5 py-1.5"
                   data-testid="account-form-home-locked">
                <Star size={12} className="text-[#1B7F4B]" />
                <span className="text-[11.5px] font-semibold text-[#1C1C1E]">
                  {entities.find((x) => x.id === effectiveHome)?.legal_name || effectiveHome}
                </span>
                <span className="ml-auto text-[10px] text-[#1B7F4B]">
                  diisi otomatis dari HR — tidak bisa diubah di sini
                </span>
              </div>
            ) : (
              <KNSelect className="field" data-testid="account-form-home-select"
                        value={form.home_entity_id}
                        onValueChange={(v) => set({
                          home_entity_id: v,
                          allowed_entity_ids: Array.from(
                            new Set([...(form.allowed_entity_ids || []), v])) })}
                        options={entities.map((e) => ({
                          value: e.id, label: e.legal_name || e.short_name }))}
                        placeholder="Pilih badan usaha…" />
            )}
          </div>

          {/* Penugasan tambahan (hanya untuk peran non-lintas) */}
          {!isCross && (
            <div className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2.5"
                 data-testid="account-form-allowed">
              <p className="kicker mb-1">Badan usaha tambahan yang boleh diakses</p>
              <div className="flex flex-wrap gap-1.5">
                {entities.map((e) => {
                  const isHome = e.id === effectiveHome;
                  const on = isHome || (form.allowed_entity_ids || []).includes(e.id);
                  return (
                    <button key={e.id} type="button"
                            data-testid={`account-form-allowed-${e.id}`}
                            disabled={isHome}
                            onClick={() => toggleAllowed(e.id)}
                            className={`rounded-md border px-2 py-1 text-[11px] font-semibold disabled:opacity-70 ${
                              on ? "border-[#0058CC] bg-[#EAF2FF] text-[#0058CC]"
                                 : "border-[#E5E5EA] bg-white text-[#6B6B73]"}`}>
                      {isHome && <Star size={9} className="mr-1 inline" />}
                      {e.short_name || e.legal_name}
                    </button>
                  );
                })}
              </div>
              <p className="mt-1 text-[10px] text-[#8E8E93]">
                Badan usaha utama (★) selalu termasuk. Yang tidak dipilih benar-benar TIDAK
                terlihat oleh orang ini — termasuk pesanan, pelanggan, stok, dan laporannya.
              </p>
            </div>
          )}

          {/* FASE L — LINI PRODUK yang boleh dikerjakan. Ditaruh SESUDAH penugasan
              badan usaha karena urutannya memang begitu di kepala admin: "orang ini
              di PT mana" → "mengerjakan lini apa". Kosong = SEMUA lini (bawaan). */}
          <div className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2.5"
               data-testid="account-form-lines">
            <p className="kicker mb-1">Lini produk yang boleh diakses</p>
            {lineOptions.length === 0 ? (
              <p className="text-[10.5px] text-[#8E8E93]" data-testid="account-form-lines-empty">
                Belum ada master Lini Produk. Tambahkan di Pengaturan → Master → Lini Produk.
              </p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                <button type="button" data-testid="account-form-line-all"
                        onClick={() => set({ allowed_line_codes: [] })}
                        className={`rounded-md border px-2 py-1 text-[11px] font-semibold ${
                          (form.allowed_line_codes || []).length === 0
                            ? "border-[#0058CC] bg-[#EAF2FF] text-[#0058CC]"
                            : "border-[#E5E5EA] bg-white text-[#6B6B73]"}`}>
                  Semua lini
                </button>
                {lineOptions.map((o) => {
                  const on = (form.allowed_line_codes || []).includes(o.value);
                  return (
                    <button key={o.value} type="button"
                            data-testid={`account-form-line-${o.value}`}
                            onClick={() => toggleLine(o.value)}
                            className={`rounded-md border px-2 py-1 text-[11px] font-semibold ${
                              on ? "border-[#6B219A] bg-[#F3E9FA] text-[#6B219A]"
                                 : "border-[#E5E5EA] bg-white text-[#6B6B73]"}`}>
                      {o.label}
                    </button>
                  );
                })}
              </div>
            )}
            <p className="mt-1 text-[10px] text-[#8E8E93]">
              Kosong (<b>Semua lini</b>) adalah bawaannya. Bila dipilih, orang ini hanya
              melihat produk, pesanan, roll, dan pekerjaan lini itu — dan ditolak saat
              menambahkan kain lini lain ke dokumen. Data lama yang belum bergolong lini
              tetap terlihat, jadi tidak ada layar yang mendadak kosong.
            </p>
          </div>

          {editing && (
            // Cek layar 14 Nov — gaya blok sama dengan tetangganya (judul `kicker`, latar abu), tanpa hex baru.
            <div className="form-subsection" data-testid="account-form-ai-finance">
              <p className="kicker mb-1">Asisten keuangan (Tanya KN)</p>
              <label className="flex items-center gap-2">
                <input type="checkbox" role="switch" className="h-4 w-4" data-testid="account-form-ai-finance-switch"
                       checked={aiFinance} disabled={!canConfigureAi}
                       onChange={(e) => setAiFinance(e.target.checked)} />
                <span className="text-fs-13 font-semibold text-kn-text">Boleh bertanya soal keuangan</span>
                <span className="text-fs-12 text-kn-text-2" data-testid="account-form-ai-finance-state">
                  {aiFinance ? "Menyala" : "Mati"}
                </span>
              </label>
              <p className="mt-1 text-fs-12 text-kn-text-2">
                Mati = akun ini tidak bisa bertanya soal keuangan lewat Tanya KN.
              </p>
              <label className="mt-2 flex items-center gap-2">
                <input type="checkbox" role="switch" className="h-4 w-4" data-testid="account-form-ai-class-b"
                       checked={classB} disabled={!canConfigureAi}
                       onChange={(e) => setClassB(e.target.checked)} />
                <span className="text-fs-13 font-semibold text-kn-text">Boleh menyetujui kartu uang masuk</span>
                <span className="text-fs-12 text-kn-text-2" data-testid="account-form-ai-class-b-state">
                  {classB ? "Menyala" : "Mati"}
                </span>
              </label>
              <p className="mt-1 text-fs-12 text-kn-text-2">
                Kartu kwitansi, pencocokan bank, alokasi titipan, dan ulang jurnal yang disiapkan asisten. Juga butuh
                akses &apos;Siapkan dan setujui tindakan&apos; dan pengaturan PT yang menyala.
              </p>
              {!canConfigureAi && (
                <p className="mt-1 text-fs-12 text-kn-text-2" data-testid="account-form-ai-finance-readonly">
                  Hanya-baca: yang bisa menyalakan adalah pemegang akses pengaturan asisten (Asisten Tanya KN).
                </p>
              )}
            </div>
          )}

          <AccountLocationScope role={form.role} siteIds={form.location_site_ids || []}
                                warehouseIds={form.location_warehouse_ids || []} onChange={set} />

          {willRevoke && (
            <div className="flex items-start gap-1.5 rounded-md border border-[#F0C88A] bg-[#FEF7EC] p-2.5"
                 data-testid="account-form-revoke-warning">
              <Info size={13} className="mt-0.5 shrink-0 text-[#8C4A00]" />
              <p className="text-[11px] text-[#3C3C43]">
                Perubahan ini <b>mencabut sesi</b> {user?.name} sehingga dia harus masuk lagi.
                Ini disengaja: tanpa itu, tab yang masih terbuka tetap memakai hak akses lama.
              </p>
            </div>
          )}

          {tried && errors.length > 0 && (
            <ul className="space-y-1 rounded-md border border-[#F0B5AE] bg-[#FCEBEA] p-2.5"
                data-testid="account-form-errors">
              {errors.map((e, i) => (
                <li key={i} className="text-[11px] text-[#A8221A]">• {e}</li>
              ))}
            </ul>
          )}
          {error && (
            <div className="notice-bar danger !py-1.5" data-testid="account-form-error">
              <span className="text-[11.5px]">{error}</span>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-[#EFF0F2] px-4 py-3">
          <button type="button" className="secondary-button" data-testid="account-form-cancel"
                  onClick={onClose}>Batal</button>
          <button type="button" className="primary-button" data-testid="account-form-submit"
                  disabled={busy} onClick={submit}>
            {busy ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
            {editing ? "Simpan Perubahan" : "Buat Akun"}
          </button>
        </div>
      </div>
    </div>
  );
}
