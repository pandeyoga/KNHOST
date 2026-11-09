import axios from "axios";

import { toast } from "../hooks/use-toast";
import { isScopeBlockedError, WRITE_BLOCK_TITLE } from "../utils/writeScope";
import { docEntityFor, allowedEntityIds } from "./docEntityRegistry";

// SEC-2 — kirim/terima HttpOnly session cookie (same-origin via ingress)
axios.defaults.withCredentials = true;

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const setAuthToken = (token) => {
  if (token) axios.defaults.headers.common.Authorization = `Bearer ${token}`;
  else delete axios.defaults.headers.common.Authorization;
};

// Multi-Entity (F0-B): konteks entitas aktif dikirim via header X-Entity-Id.
// Nilai "all" = mode oversight lintas-PT (hanya dihormati untuk role admin/manager).
export const setActiveEntity = (entityId) => {
  if (entityId) axios.defaults.headers.common["X-Entity-Id"] = entityId;
  else delete axios.defaults.headers.common["X-Entity-Id"];
};

/**
 * FASE E-3 (user story 7) — satu jaring pengaman untuk pagar mode gabungan.
 *
 * Server menolak pembuatan data selagi pengguna berada di mode "Semua Entitas"
 * (`entity_write_guard.py` → 409). Tanpa penangan pusat, penolakan itu akan
 * muncul berbeda-beda di ~50 layar (atau bahkan senyap di layar yang lupa
 * menampilkan galat). Interseptor ini menjamin: **selalu** ada pesan yang
 * menjelaskan sebabnya + isyarat ke pita pemilih badan usaha, di layar mana pun.
 *
 * Galat tetap DILEMPARKAN ULANG supaya layar bisa menampilkan galatnya sendiri
 * (aturan INV-UI-03: kegagalan backend tidak boleh senyap).
 */
axios.interceptors.response.use(
  (res) => res,
  (err) => {
    if (isScopeBlockedError(err)) {
      toast({
        title: WRITE_BLOCK_TITLE,
        description: err.response.data.detail,
        variant: "destructive",
      });
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("kn:scope-blocked"));
      }
    }
    return Promise.reject(err);
  },
);

/* ── FIX-1 (audit WMS-RFID 9 Nov, K-B1-01) — cakupan LOKASI KERJA ───────────────────────────────────────────────
 * Bilah cakupan ("Lokasi: Soreang ▾") menyetel header `X-Location-Scope` untuk SEMUA permintaan: '' = lokasi kerja
 * akun (bawaan), 'all' = semua lokasi (aksi eksplisit, hanya akun tak berpagar), 'site:<id>' / 'wh:<id>'. Server
 * memakainya HANYA sebagai saringan tampilan daftar tugas & stok/roll WMS-RFID; pagar keras petugas `warehouse`
 * tetap di server (pilihan di luar lokasinya diabaikan). */
export const LOCATION_SCOPE_HEADER = "X-Location-Scope";
export const setLocationScope = (value) => {
  if (value) axios.defaults.headers.common[LOCATION_SCOPE_HEADER] = value;
  else delete axios.defaults.headers.common[LOCATION_SCOPE_HEADER];
};

/* ── FIX-1 (K-B1-02, B2a D1) — daftar pekerjaan fisik LINTAS PT ───────────────────────────────────────────────────
 * Daftar tugas/PA/transfer/opname/pengiriman kini memuat dokumen semua PT yang ditugaskan di gedung yang sama. Aksi
 * & detail sebuah dokumen dikirim ATAS NAMA PT DOKUMEN itu (header X-Entity-Id), jadi pagar entitas server yang
 * ketat tetap berlaku tanpa pengguna harus berganti PT. Daftar memanggil `rememberDocEntities(rows)`; interseptor
 * mencocokkan id dokumen pada path URL. Hanya PT yang ada di penugasan akun yang dipakai (server tetap memeriksa).
 * Registrinya modul murni `docEntityRegistry.js` (komponen mengimpornya langsung — tidak ikut di-mock uji layar). */
export { rememberDocEntities, forgetDocEntities, docEntityOf } from "./docEntityRegistry";
axios.interceptors.request.use((config) => {
  const ent = docEntityFor(config?.url);
  if (!ent) return config;
  const current = config.headers?.get ? config.headers.get("X-Entity-Id") : config.headers?.["X-Entity-Id"];
  const deflt = axios.defaults.headers.common["X-Entity-Id"];
  // Header eksplisit per permintaan (berbeda dari bawaan) dihormati — mis. antrean offline membawa PT saat direkam.
  if (current && current !== deflt) return config;
  if (ent === current || !allowedEntityIds().includes(ent)) return config;
  if (config.headers?.set) config.headers.set("X-Entity-Id", ent);
  else config.headers = { ...(config.headers || {}), "X-Entity-Id": ent };
  return config;
});

export default axios;
