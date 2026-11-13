/**
 * PK-12 — satu pintu kirim untuk form uang. Menambahkan header `Idempotency-Key` bila `key` terisi, sehingga klik
 * ganda / kirim ulang sesudah koneksi putus diputar ulang server (backend/idempotency.py), bukan membuat dokumen kedua.
 *
 * Pakai bersama `useIntentKey`:
 *   const intent = useIntentKey("kas");
 *   await intent.send(body, (k) => moneyPost(`${API}/cash-transactions`, body, k));
 *
 * Penjaga `scripts/guardrails/verify_money_idempotency.py` memerahkan `axios.post|put|patch|delete` langsung ke jalur
 * uang di luar berkas ini.
 */
import axios from "../services/apiClient";

export function withKey(config, key) {
  if (!key) return config || {};
  const c = config || {};
  return { ...c, headers: { ...(c.headers || {}), "Idempotency-Key": key } };
}

export const moneyPost = (url, body, key, config) => axios.post(url, body, withKey(config, key));
export const moneyPut = (url, body, key, config) => axios.put(url, body, withKey(config, key));
export const moneyPatch = (url, body, key, config) => axios.patch(url, body, withKey(config, key));
export const moneyDelete = (url, key, config) => axios.delete(url, withKey(config, key));
