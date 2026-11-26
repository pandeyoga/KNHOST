/**
 * useSalesCashMode (LB-T8, R15 M3) — apakah akun ini boleh menerima uang TUNAI baru di kwitansi
 * (`pembayaran.sales_terima_tunai`: kas_langsung | titipan | dilarang). Sumber: `GET /cash-holdings/me/summary` (milik
 * sendiri, dipakai pula form kwitansi). Server mengecualikan tunai baru dari pagar "pakai Lapor bayar" dan tetap
 * menolak tunai bila pengaturannya `dilarang`; hook ini hanya menentukan tombol ditampilkan atau tidak.
 * Gagal dibaca (mode kosong) = tombol ditampilkan — server yang memutus.
 * → `{ ready, mode, cashAllowed }`.
 */
import { useEffect, useState } from "react";
import axios, { API } from "../../../services/apiClient";

export default function useSalesCashMode(enabled = true) {
  const [st, setSt] = useState({ ready: !enabled, mode: "" });
  useEffect(() => {
    if (!enabled) { setSt({ ready: true, mode: "" }); return undefined; }
    let alive = true;
    axios.get(`${API}/cash-holdings/me/summary`)
      .then((r) => { if (alive) setSt({ ready: true, mode: String(r.data?.mode || "") }); })
      .catch(() => { if (alive) setSt({ ready: true, mode: "" }); });
    return () => { alive = false; };
  }, [enabled]);
  return { ...st, cashAllowed: st.mode !== "dilarang" };
}
