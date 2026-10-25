/**
 * useSessionSync — sinkronisasi sesi/izin/peran yang dulu ditulis langsung di `App.js`.
 *
 * Fase 3 · P1 — DIEKSTRAK apa adanya dari App.js (batas 500 baris, KN_00 GATE 2) supaya penambahan
 * jalur navigasi alias tidak membuat App.js makin gemuk. Perilaku TIDAK berubah:
 *  1. FASE E-8 — segarkan izin saat sesi dipulihkan dari localStorage (`/auth/me`).
 *  2. PERAN KUSTOM & IZIN HIDUP — daftarkan peran kustom (`/roles`) + segarkan tiap 60 dtk & saat
 *     editor peran menyimpan (`kn:roles-changed`).
 *  3. Peran kustom baru terdaftar → arahkan ke berandanya, KECUALI alamat menyebut layar sah.
 *  4. Landing per peran DETERMINISTIK saat pengguna berganti (bukan saat berpindah view).
 */
import { useEffect, useRef, useState } from "react";
import axios, { API } from "../services/apiClient";
import { registerDynamicRoles, ROLE_REGISTRY } from "../config/roles";
import { defaultNavIdForRole, defaultViewForRole, resolveDeepLinkTarget } from "../config/navigationConfig";

export default function useSessionSync({ token, user, setUser, setEntityContext, setEntities, setActiveView, setActiveNavId }) {
  // FASE E-8 — SEGARKAN IZIN saat sesi dipulihkan dari localStorage.
  // Sejak tombol dinyalakan oleh `can(user.permissions, …)`, profil lama yang
  // tersimpan SEBELUM peran baru ada (atau setelah admin mengubah matriks izin)
  // membuat tombol yang sah ikut hilang tanpa alasan. `/auth/me` mengembalikan
  // izin efektif + label peran terbaru, jadi satu panggilan menutup selisih itu.
  useEffect(() => {
    if (!token) return;
    let alive = true;
    (async () => {
      try {
        const r = await axios.get(`${API}/auth/me`);
        if (!alive || !r?.data?.id) return;
        setUser((prev) => {
          const next = {
            ...(prev || {}), ...r.data,
            permissions: r.data.permissions || {},
            role_label: r.data.role_label || prev?.role_label || "",
          };
          localStorage.setItem("kn_user", JSON.stringify(next));
          return next;
        });
        if (r.data.entity_context) {
          setEntityContext(r.data.entity_context);
          localStorage.setItem("kn_entity_ctx", JSON.stringify(r.data.entity_context));
          if (Array.isArray(r.data.entity_context.entities)) setEntities(r.data.entity_context.entities);
        }
      } catch {
        /* token kedaluwarsa → gate auth di bawah yang menangani */
      }
    })();
    return () => { alive = false; };
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  // PERAN KUSTOM & IZIN HIDUP — daftarkan peran kustom dari server ke registry
  // navigasi, lalu segarkan izin/peran tiap 60 detik (tanpa login ulang) dan saat
  // admin menyimpan perubahan di layar "Peran & Hak Akses".
  const [rolesVersion, setRolesVersion] = useState(0);
  useEffect(() => {
    if (!token) return undefined;
    let alive = true;
    const refresh = async () => {
      try {
        const [rolesRes, meRes] = await Promise.all([
          axios.get(`${API}/roles`), axios.get(`${API}/auth/me`),
        ]);
        if (!alive) return;
        const changed = registerDynamicRoles(rolesRes?.data?.roles || []);
        if (changed) setRolesVersion((v) => v + 1);
        if (meRes?.data?.id) {
          setUser((prev) => {
            const nextPerms = meRes.data.permissions || {};
            if (prev && JSON.stringify(prev.permissions || {}) === JSON.stringify(nextPerms)
                && JSON.stringify(prev.hidden_views || []) === JSON.stringify(meRes.data.hidden_views || [])
                && prev.role === meRes.data.role && prev.role_label === meRes.data.role_label && !changed) return prev;
            const next = { ...(prev || {}), ...meRes.data, permissions: nextPerms,
              role_label: meRes.data.role_label || prev?.role_label || "" };
            localStorage.setItem("kn_user", JSON.stringify(next));
            return next;
          });
        }
      } catch { /* sesi kedaluwarsa ditangani gate auth */ }
    };
    refresh();
    const id = setInterval(refresh, 60000);
    const onRolesChanged = () => refresh();
    window.addEventListener("kn:roles-changed", onRolesChanged);
    return () => { alive = false; clearInterval(id); window.removeEventListener("kn:roles-changed", onRolesChanged); };
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps
  // Peran kustom baru terdaftar setelah state awal dihitung → arahkan ke berandanya,
  // KECUALI alamat menyebut layar yang sah untuk peran ini (deep-link menang).
  useEffect(() => {
    if (!rolesVersion || !user?.role || !ROLE_REGISTRY[user.role]?.custom) return;
    const wanted = new URLSearchParams(window.location.search).get("view");
    if (wanted && resolveDeepLinkTarget(wanted, user.role)) return;
    setActiveView(defaultViewForRole(user.role));
    setActiveNavId(defaultNavIdForRole(user.role));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rolesVersion]);

  // Landing per peran: DETERMINISTIK saat pengguna berganti.
  // `login()` sudah mengarahkan ke halaman depan peran, tetapi pengguna bisa juga
  // berganti TANPA melewati jalur itu (pulih sesi dari localStorage milik akun lain,
  // tukar akun di tab yang sama, atau sesi disuntik oleh alat uji). Tanpa penjaga ini
  // layar peran SEBELUMNYA bisa tertinggal di depan mata — mis. manajer mendarat di
  // "Operasi Gudang". Deep-link tidak terganggu: efek hanya jalan saat `user.id`
  // benar-benar berubah, bukan saat berpindah view.
  const lastUserIdRef = useRef(user?.id || "");
  useEffect(() => {
    const id = user?.id || "";
    if (!id) { lastUserIdRef.current = ""; return; }
    if (id === lastUserIdRef.current) return;
    const firstLoad = lastUserIdRef.current === "";
    lastUserIdRef.current = id;
    if (firstLoad) return;   // state awal sudah dihitung dari peran tersimpan
    setActiveView(defaultViewForRole(user.role));
    setActiveNavId(defaultNavIdForRole(user.role));
  }, [user?.id, user?.role]); // eslint-disable-line react-hooks/exhaustive-deps

  return { rolesVersion };
}
