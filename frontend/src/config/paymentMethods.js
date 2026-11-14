/**
 * PM-T1 — SATU daftar cara bayar untuk semua layar "dibayar lewat apa" (kwitansi desktop & HP, bayar tagihan pemasok,
 * kontrabon, voucher biaya masuk, uang muka, selisih bayar, pelunasan antar-PT). Sumbernya master berlapis "Cara Bayar"
 * (Pengaturan › Keuangan & Pajak) lewat `GET /api/payment-methods?direction=&entity_id=` — cara bayar yang dimatikan
 * untuk satu PT tidak muncul di layar mana pun untuk PT itu. Layar mengirim KODE kanonik; label = `name` master.
 *
 * Ini satu-satunya berkas layar yang boleh menulis kosakata cara bayar (penjaga `scripts/guardrails/
 * verify_payment_vocab.py`). Daftar cadangan di bawah hanya dipakai sebelum daftar server termuat atau bila gagal
 * dimuat; server tetap menolak cara bayar yang tidak aktif untuk PT itu.
 */
import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../services/apiClient";

/** Benih server yang aktif (`backend/services/payment_method_service.BENIH`) — cadangan saja. */
export const FALLBACK_METHODS = [
  { code: "transfer", name: "Transfer bank", needs_account: "bank", needs_reference: true, needs_due_date: false, directions: ["masuk", "keluar"] },
  { code: "cash", name: "Tunai", needs_account: "kas", needs_reference: false, needs_due_date: false, directions: ["masuk", "keluar"] },
  { code: "giro", name: "Giro / cek", needs_account: "bank", needs_reference: true, needs_due_date: true, directions: ["masuk", "keluar"] },
  { code: "qris", name: "QRIS", needs_account: "bank", needs_reference: true, needs_due_date: false, directions: ["masuk"] },
  { code: "deposit", name: "Titipan / saldo kredit", needs_account: "tidak", needs_reference: false, needs_due_date: false, directions: ["masuk"] },
];

/** Kata lama yang tersimpan di dokumen sebelum PM-T1 → kode kanonik (alias benih). */
export const LEGACY_ALIASES = { tunai: "cash", kontan: "cash", cek: "giro", kartu: "edc", titipan: "deposit" };

/** Kode kanonik dari kode/kata lama (huruf kecil); kosong → `fallback`. */
export const canonicalMethod = (value, fallback = "") => {
  const v = String(value || "").trim().toLowerCase();
  if (!v) return fallback;
  return LEGACY_ALIASES[v] || v;
};

const fallbackFor = (direction) => FALLBACK_METHODS.filter((m) => !direction || m.directions.includes(direction));

const cache = new Map();
const inflight = new Map();
const keyOf = (direction, entityId) => `${direction || ""}|${entityId || ""}`;

/** Muat (sekali per arah × PT) daftar cara bayar aktif. Gagal → `null` (layar memakai cadangan). */
export function loadPaymentMethods(direction = "", entityId = "", { force = false } = {}) {
  const key = keyOf(direction, entityId);
  if (!force && cache.has(key)) return Promise.resolve(cache.get(key));
  if (!force && inflight.has(key)) return inflight.get(key);
  const params = {};
  if (direction) params.direction = direction;
  if (entityId && entityId !== "all") params.entity_id = entityId;
  const p = Promise.resolve()
    .then(() => axios.get(`${API}/payment-methods`, { params }))
    .then((r) => {
      if (!r || !Array.isArray(r.data)) return null;   // jawaban bukan daftar → pakai cadangan
      cache.set(key, r.data);
      return r.data;
    })
    .catch(() => null)
    .finally(() => inflight.delete(key));
  inflight.set(key, p);
  return p;
}

/** Buang cache (mis. sesudah master Cara Bayar diubah). */
export const invalidatePaymentMethods = () => cache.clear();

/** Pilihan KNSelect dari baris cara bayar. */
export const paymentMethodOptions = (rows) => (rows || []).map((m) => ({ value: m.code, label: m.name }));

/**
 * `usePaymentMethods(arah, entityId)` — arah `masuk` (penerimaan) / `keluar` (pembayaran); `entityId` = PT dokumen
 * (kosong = PT aktif). Hasil: `methods` (baris), `options` (KNSelect), `loaded`, `failed`, `labelOf(kode)`,
 * `isCash(kode)` (cara bayar ber-rekening kas), `has(kode)`.
 */
export function usePaymentMethods(direction = "", entityId = "") {
  const key = keyOf(direction, entityId);
  const [state, setState] = useState(() => ({ key, rows: cache.get(key) || null, failed: false }));
  useEffect(() => {
    let alive = true;
    if (state.key !== key) setState({ key, rows: cache.get(key) || null, failed: false });
    loadPaymentMethods(direction, entityId).then((rows) => {
      if (alive) setState({ key, rows, failed: rows === null });
    });
    return () => { alive = false; };
  }, [key]);  // eslint-disable-line react-hooks/exhaustive-deps
  return useMemo(() => {
    const rows = (state.key === key && state.rows) || null;
    const methods = rows || fallbackFor(direction);
    const byCode = Object.fromEntries(methods.map((m) => [m.code, m]));
    const all = Object.fromEntries(FALLBACK_METHODS.map((m) => [m.code, m]));
    return {
      methods,
      options: paymentMethodOptions(methods),
      loaded: Boolean(rows),
      failed: state.key === key && state.failed,
      has: (code) => Boolean(byCode[canonicalMethod(code)]),
      labelOf: (code) => (byCode[canonicalMethod(code)] || all[canonicalMethod(code)] || {}).name || String(code || "—"),
      isCash: (code) => (byCode[canonicalMethod(code)] || all[canonicalMethod(code)] || {}).needs_account === "kas",
    };
  }, [state, key, direction]);
}

export default usePaymentMethods;
