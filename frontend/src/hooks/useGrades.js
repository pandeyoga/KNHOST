/**
 * useGrades — FIX-8 (B1b UI-49 · B3b FRM-18): daftar grade aktif dari Master Grade Mutu UNTUK PEMILIH grade, dengan
 * galat yang TERLIHAT. Dulu tiga pemilih (lembar inspeksi, rincian baris inspeksi, inspeksi roll) menelan galat
 * `.catch(() => setGrades([]))`: peran gudang ditolak 403 "grade_master.view" lalu pemilihnya kosong tanpa kabar —
 * pengguna mengira memang tidak ada grade. Kini galat dibawa (`error`) dan `GradeLoadNote` menulis alasannya.
 */
import { createElement, useEffect, useState } from "react";
import axios, { API } from "../services/apiClient";
import EmptyState, { isForbidden } from "../components/EmptyState";

export const activeGrades = (rows) => (rows || []).filter((g) => g.active !== false);

export default function useGrades() {
  const [state, setState] = useState({ grades: [], error: null, loading: true });
  useEffect(() => {
    let live = true;
    axios.get(`${API}/master/grades`)
      .then((r) => { if (live) setState({ grades: activeGrades(r.data), error: null, loading: false }); })
      .catch((e) => { if (live) setState({ grades: [], error: e, loading: false }); });
    return () => { live = false; };
  }, []);
  return state;
}

/** Catatan satu baris di dekat pemilih grade bila daftar grade gagal dimuat (403 → "tanpa akses", bukan kosong). */
export function GradeLoadNote({ error, testId = "grade-load-note" }) {
  if (!error) return null;
  const forbidden = isForbidden(error);
  return createElement(EmptyState, {
    compact: true, testId, error, what: "daftar grade",
    kind: forbidden ? "forbidden" : "error",
    title: forbidden ? "Daftar grade tidak bisa dimuat — Anda tidak punya akses ke Master Grade Mutu." : "Daftar grade gagal dimuat.",
    text: forbidden
      ? "Pilihan grade kosong bukan berarti tidak ada grade. Minta admin menambah izin lihat Master Grade, atau biarkan grade diisi saran sistem."
      : undefined,
  });
}
