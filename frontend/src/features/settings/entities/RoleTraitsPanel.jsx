/**
 * RoleTraitsPanel — PR-T4: bagian "Sifat peran" di editor peran (kolom kanan, di bawah "Akses semua badan usaha").
 * Empat isian yang dulu melekat pada nama peran dasar: data yang terlihat, halaman awal, kategori kerja, dan
 * notifikasi peran lain yang ikut diterima. Nilai yang tidak disimpan = turunan ("Mengikuti …").
 *
 * `draft` = perubahan yang belum disimpan: { kunci: nilai } atau { kunci: null } (= kembali ke turunan).
 */
import KNSelect from "../../../components/KNSelect";

export const TRAIT_KEYS = ["data_scope", "home_view", "kategori_kerja", "notify_like"];
export const SCOPE_OPTIONS = [
  { value: "milik_sendiri", label: "Milik sendiri" },
  { value: "tim", label: "Milik sendiri dan timnya" },
  { value: "semua", label: "Semua di PT yang boleh dibuka" },
];
export const CATEGORY_OPTIONS = [
  { value: "", label: "Tidak ada" },
  { value: "sales", label: "Sales" },
  { value: "sopir", label: "Sopir" },
  { value: "desainer", label: "Desainer" },
  { value: "gudang", label: "Petugas gudang" },
  { value: "pengawas", label: "Pengawas" },
];
export const CATEGORY_EFFECT = {
  "": "Tidak ikut daftar pilih sales, sopir, maupun desainer, dan tidak punya Meja Saya.",
  sales: "Akun muncul di daftar pilih sales dan boleh menjadi penanggung jawab pelanggan; pesanan buatannya tercatat "
    + "atas namanya; ikut papan peringkat, komisi, dan akrual insentif; dibatasi produk eksklusif dan tahap "
    + "tersembunyi; Meja Sales.",
  sopir: "Akun bisa ditugaskan sebagai pengemudi; Meja Pengemudi.",
  desainer: "Akun bisa ditugaskan permintaan desain; Meja Desainer.",
  gudang: "Dibatasi lokasi kerja akun bila pengaturan lokasi kerja aktif; boleh meminta daftar seluruh gudang; "
    + "dataset ekspor gudang; Meja Operator Gudang.",
  pengawas: "Tidak menerima notifikasi giliran pelaksana; boleh meminta daftar seluruh gudang; Meja Manajer.",
};
export const TRAIT_LABEL = {
  data_scope: "Data yang terlihat", home_view: "Halaman awal", kategori_kerja: "Kategori kerja",
  notify_like: "Ikut menerima notifikasi untuk",
};
const FOLLOW = "__ikut__";
const NEEDS_ACCESS = "Butuh akses yang belum dimiliki peran ini";
const PROFILE_HOME = "hr-my-profile";

const sameList = (a, b) => JSON.stringify([...(a || [])].sort()) === JSON.stringify([...(b || [])].sort());
const same = (k, a, b) => (k === "notify_like" ? sameList(a, b) : (a ?? "") === (b ?? ""));

/** Daftar pilihan halaman awal (dari server; peran baru memakai daftar peran mana pun). */
export function homeChoicesOf(role, roles) {
  return role?.home_choices || (roles || []).find((r) => r.home_choices)?.home_choices || [];
}

/** Bolehkah halaman awal `view` dipilih dengan izin `perms` dan kategori `category` (sama dengan server). */
export function homeAllowed(choice, perms, category) {
  if (!choice) return false;
  if (choice.needs_category && !category) return false;
  if (!choice.requires) return true;
  const [res, act] = choice.requires;
  const acts = (perms || {})[res] || [];
  return acts.includes(act) || acts.includes("*");
}

/** PR-T6 — peran kustom yang peran dasarnya sedang diganti di editor (belum disimpan). */
const baseChanged = (role, baseRole) => Boolean(role?.custom) && baseRole !== undefined && baseRole !== (role.base_role || "");

/** Nilai turunan (tanpa simpanan): peran yang disunting → `traits_default`; peran baru — atau peran kustom yang peran
 *  dasarnya sedang diganti (PR-T6) — → peran dasar. */
export function derivedTraits({ role, baseRole, roles }) {
  if (role?.traits_default && !baseChanged(role, baseRole)) return role.traits_default;
  const base = (roles || []).find((r) => r.id === baseRole);
  if (base?.traits) return { ...base.traits, notify_like: base.custom ? (base.traits.notify_like || []) : [base.id] };
  return { data_scope: "semua", home_view: PROFILE_HOME, kategori_kerja: "", notify_like: [] };
}

/** Nilai yang tampil di editor: draft → simpanan → turunan. `isDerived[k]` = tampil "Mengikuti …". */
export function shownTraits({ role, baseRole, roles, draft }) {
  const derived = derivedTraits({ role, baseRole, roles });
  const stored = new Set(role?.traits_overridden || []);
  const values = {};
  const isDerived = {};
  TRAIT_KEYS.forEach((k) => {
    if (k in (draft || {})) {
      values[k] = draft[k] === null ? derived[k] : draft[k];
      isDerived[k] = draft[k] === null;
    } else {
      values[k] = role?.traits ? (stored.has(k) ? role.traits[k] : derived[k]) : derived[k];
      isDerived[k] = !stored.has(k);
    }
  });
  return { values, isDerived, derived };
}

/** Isi `traits` yang dikirim: hanya kunci yang benar-benar berubah (nilai baru, atau null untuk melepas simpanan). */
export function traitPayload({ role, draft }) {
  const stored = new Set(role?.traits_overridden || []);
  const out = {};
  Object.entries(draft || {}).forEach(([k, v]) => {
    if (v === null) { if (stored.has(k)) out[k] = null; return; }
    if (!stored.has(k) || !same(k, v, role?.traits?.[k])) out[k] = v;
  });
  return out;
}

export function traitValueLabel(key, value, { roles, choices } = {}) {
  if (key === "data_scope") return SCOPE_OPTIONS.find((o) => o.value === value)?.label || value || "—";
  if (key === "kategori_kerja") return CATEGORY_OPTIONS.find((o) => o.value === (value || ""))?.label || value;
  if (key === "home_view") return (choices || []).find((c) => c.view === value)?.label || value || "—";
  const names = (value || []).map((id) => (roles || []).find((r) => r.id === id)?.label || id);
  return names.length ? names.join(", ") : "Tidak ada";
}

/** Baris dialog "Periksa sebelum menyimpan": "{Label}: {lama} → {baru}" per sifat yang nilainya berubah. */
export function traitChangeLines({ role, baseRole, roles, draft }) {
  const choices = homeChoicesOf(role, roles);
  const now = shownTraits({ role, baseRole, roles, draft: {} }).values;
  const next = shownTraits({ role, baseRole, roles, draft }).values;
  return TRAIT_KEYS.filter((k) => k in (draft || {}) && !same(k, now[k], next[k])).map((k) => ({
    key: k,
    text: `${TRAIT_LABEL[k]}: ${traitValueLabel(k, now[k], { roles, choices })} → ${traitValueLabel(k, next[k], { roles, choices })}`,
  }));
}

function followText({ role, baseRole, roles }) {
  if (role && !role.custom) return "Mengikuti bawaan sistem";
  const base = role && baseRole === undefined ? role.base_role : baseRole;
  const label = (roles || []).find((r) => r.id === base)?.label;
  return label ? `Mengikuti ${label}` : "Mengikuti bawaan";
}

export default function RoleTraitsPanel({ role, baseRole, roles, perms, draft, onChange, disabled }) {
  const { values, isDerived, derived } = shownTraits({ role, baseRole, roles, draft });
  const choices = homeChoicesOf(role, roles);
  const follow = followText({ role, baseRole, roles });
  const set = (k, v) => onChange?.({ ...(draft || {}), [k]: v === FOLLOW ? null : v });
  const builtins = (roles || []).filter((r) => !r.custom && !r.locked && r.id !== role?.id);
  const homeOptions = choices.map((c) => {
    const ok = homeAllowed(c, perms, values.kategori_kerja);
    return { value: c.view, label: ok ? c.label : `${c.label} · ${NEEDS_ACCESS}`, disabled: !ok && c.view !== values.home_view };
  });
  const withFollow = (opts, key) => [
    { value: FOLLOW, label: `${follow} (${traitValueLabel(key, derived[key], { roles, choices })})` }, ...opts];
  const selectValue = (k) => (isDerived[k] ? FOLLOW : (values[k] ?? ""));
  // Hanya halaman awal yang DISIMPAN jatuh ke Profil Saya bila syaratnya tidak terpenuhi (sama dengan server).
  const homeBlocked = !isDerived.home_view
    && !homeAllowed(choices.find((c) => c.view === values.home_view), perms, values.kategori_kerja);

  return (
    <div className="mt-2 space-y-2 rounded-md border border-kn-divider p-2" data-testid="role-editor-traits">
      <p className="kicker">Sifat peran</p>
      <div className="grid gap-1" data-testid="role-traits-data-scope">
        <label className="text-fs-12 font-semibold text-kn-text">Data yang terlihat</label>
        <KNSelect className="field" data-testid="role-traits-data-scope-select" disabled={disabled}
                  value={selectValue("data_scope")} options={withFollow(SCOPE_OPTIONS, "data_scope")}
                  onValueChange={(v) => set("data_scope", v)} />
        <p className="text-fs-12 text-kn-text-2">Berlaku untuk pelanggan, pesanan, pengajuan harga, prospek, pengiriman, dan permintaan desain.</p>
      </div>
      <div className="grid gap-1" data-testid="role-traits-home">
        <label className="text-fs-12 font-semibold text-kn-text">Halaman awal</label>
        <KNSelect className="field" data-testid="role-traits-home-select" disabled={disabled}
                  value={selectValue("home_view")} options={withFollow(homeOptions, "home_view")}
                  onValueChange={(v) => set("home_view", v)} />
        <p className="text-fs-12 text-kn-text-2">Layar pertama setelah masuk.</p>
        {homeBlocked && (
          <p className="text-fs-12 text-kn-warning-text" data-testid="role-traits-home-blocked">
            {NEEDS_ACCESS} — akun peran ini akan mendarat di Profil Saya.
          </p>
        )}
      </div>
      <div className="grid gap-1" data-testid="role-traits-category">
        <label className="text-fs-12 font-semibold text-kn-text">Kategori kerja</label>
        <KNSelect className="field" data-testid="role-traits-category-select" disabled={disabled}
                  value={selectValue("kategori_kerja")} options={withFollow(CATEGORY_OPTIONS, "kategori_kerja")}
                  onValueChange={(v) => set("kategori_kerja", v)} />
        <p className="text-fs-12 text-kn-text-2" data-testid="role-traits-category-effect">{CATEGORY_EFFECT[values.kategori_kerja || ""]}</p>
      </div>
      <div className="grid gap-1" data-testid="role-traits-notify">
        <span className="text-fs-12 font-semibold text-kn-text">Ikut menerima notifikasi untuk</span>
        <label className="flex items-center gap-1.5 text-fs-12 text-kn-text-2">
          <input type="checkbox" checked={isDerived.notify_like} disabled={disabled || isDerived.notify_like}
                 data-testid="role-traits-notify-follow" onChange={() => set("notify_like", FOLLOW)} />
          {follow} ({traitValueLabel("notify_like", derived.notify_like, { roles })})
        </label>
        <div className="grid grid-cols-2 gap-0.5">
          {builtins.map((r) => (
            <label key={r.id} className="flex items-center gap-1.5 text-fs-12 text-kn-text">
              <input type="checkbox" disabled={disabled} data-testid={`role-traits-notify-${r.id}`}
                     checked={(values.notify_like || []).includes(r.id)}
                     onChange={(e) => set("notify_like", e.target.checked
                       ? [...new Set([...(values.notify_like || []), r.id])]
                       : (values.notify_like || []).filter((x) => x !== r.id))} />
              {r.label}
            </label>
          ))}
        </div>
        <p className="text-fs-12 text-kn-text-2">Notifikasi giliran tetap mengikuti izin.</p>
      </div>
      {TRAIT_KEYS.some((k) => isDerived[k]) && (
        <p className="text-fs-12 text-kn-text-2" data-testid="role-traits-follow-note">
          Isian bertanda “{follow}” ikut berubah bila sumbernya diubah.
        </p>
      )}
    </div>
  );
}
