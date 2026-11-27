/**
 * deskDedupe — satu baris hanya di satu kartu (spek meja gelombang 1 §5.6).
 * Berjalan di FRONTEND dan hanya di antara kartu yang benar-benar terlihat pengguna.
 */

const bulat2 = (n) => Math.round(n * 100) / 100;
const nilai = (r) => Number(r?.value) || 0;

/**
 * Meja Keuangan: pesanan lewat jatuh tempo ada di "Uang masuk" dan "Piutang lewat jatuh tempo" — tampilkan hanya di
 * Piutang; baris Piutang itu mendapat aksi tambahan "Terima pembayaran" (baris uang masuknya) di pop-up.
 * Dipanggil SETELAH penyaringan izin: tanpa salah satu kartu, tidak ada yang berubah. Masukan tidak diubah.
 * F1 — baris mutasi bank (`ref_type` `bank_statement_line`, antrean `mutasi_berkode`) membawa `order_id` pesanan kode
 * bayarnya, tetapi BUKAN baris "Terima pembayaran" pelanggan: tidak ikut dipindah ke Piutang.
 */
const ikutDedupe = (r) => r?.ref_type !== "bank_statement_line";
export function dedupeFinanceGroups(groups) {
  const list = Array.isArray(groups) ? groups : [];
  const piutang = list.find((g) => g.id === "piutang_lewat_tempo");
  const masuk = list.find((g) => g.id === "uang_masuk");
  if (!piutang || !masuk) return list;

  const idPiutang = new Set((piutang.rows || []).map((r) => r.order_id || r.ref_id).filter(Boolean));
  const kembar = new Map();   // order_id → baris uang masuk
  for (const r of masuk.rows || []) {
    if (ikutDedupe(r) && r.order_id && idPiutang.has(r.order_id) && !kembar.has(r.order_id)) kembar.set(r.order_id, r);
  }
  if (kembar.size === 0) return list;

  const sisa = (masuk.rows || []).filter((r) => !(ikutDedupe(r) && r.order_id && idPiutang.has(r.order_id)));
  const terhapus = (masuk.rows || []).length - sisa.length;
  const masukBaru = {
    ...masuk, rows: sisa, shown: sisa.length,
    count: Math.max(0, (Number(masuk.count) || 0) - terhapus),
    total_value: bulat2(sisa.reduce((s, r) => s + nilai(r), 0)),
    oldest_age_days: Math.max(0, ...sisa.map((r) => Number(r.age_days) || 0)),
  };
  const piutangBaru = {
    ...piutang,
    rows: (piutang.rows || []).map((r) => {
      const pasangan = kembar.get(r.order_id || r.ref_id);
      return pasangan ? { ...r, _moreActions: [...(r._moreActions || []), { label: "Terima pembayaran", row: pasangan }] } : r;
    }),
  };
  return list
    .map((g) => (g === masuk ? masukBaru : g === piutang ? piutangBaru : g))
    .filter((g) => g !== masukBaru || masukBaru.rows.length > 0 || masukBaru.count > 0);
}

/** "Giliran saya" tidak mengulang dokumen yang sudah ada di antrean khusus peran; kartunya tetap ada walau kosong. */
export function dedupeTurnQueue(queues) {
  const list = Array.isArray(queues) ? queues : [];
  const kunci = (r) => `${r.ref_type}:${r.ref_id}`;
  const lain = new Set();
  for (const q of list) if (q.id !== "giliran_saya") for (const r of q.rows || []) lain.add(kunci(r));
  return list.map((q) => {
    if (q.id !== "giliran_saya") return q;
    const rows = (q.rows || []).filter((r) => !lain.has(kunci(r)));
    const hapus = (q.rows || []).length - rows.length;
    if (hapus === 0) return q;
    return { ...q, rows, count: Math.max(0, (Number(q.count) || 0) - hapus) };
  });
}
