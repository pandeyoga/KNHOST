/**
 * traceLedger (MN-T3 bagian E) — telusur angka laporan → buku besar akun (kontrak PK-43 apa adanya): preset
 * `{tab: "ledger", code, start?, end?, from, fromTab}` ke Jurnal & Buku Besar, tombol kembali dan "Buka Dokumen Sumber"
 * sudah dipasang PK-43. Dipakai Arus Kas, Perubahan Ekuitas, Anggaran, Konsolidasi (Neraca Saldo memakai aturan yang
 * sama di layar Buku Besar sendiri — `TrialBalanceTab`).
 *
 *  · Mode Semua PT: klik angka → "Pilih satu PT untuk menelusuri angka ini." (tidak membuka buku besar gabungan).
 *  · Baris milik PT lain dari PT aktif (Konsolidasi): "Pindah ke {nama PT} untuk menelusuri angka ini."
 *  · Peran yang tidak boleh membuka Jurnal & Buku Besar: angka tampil sebagai teks biasa (bukan tombol mati).
 *  · Baris ringkasan (total, laba kotor, laba bersih) dan baris tanpa kode akun tidak dirender sebagai tautan.
 */
import { useState } from "react";
import { Info } from "lucide-react";
import { useAppNav } from "../../context/AppNavContext";

export const TEKS_PILIH_PT_TELUSUR = "Pilih satu PT untuk menelusuri angka ini.";
export const teksPindahPt = (nama) => `Pindah ke ${nama || "PT itu"} untuk menelusuri angka ini.`;

/** Keputusan telusur murni (diuji jest): `{ preset }` untuk dibuka, atau `{ notice }` untuk ditampilkan. */
export function traceDecision({ code, range = {}, selectedEntity, rowEntityId = "", rowEntityLabel = "", from, fromTab }) {
  if (!code) return null;
  if (!selectedEntity || selectedEntity === "all") return { notice: TEKS_PILIH_PT_TELUSUR };
  if (rowEntityId && rowEntityId !== selectedEntity) return { notice: teksPindahPt(rowEntityLabel || rowEntityId) };
  const r = Object.fromEntries(Object.entries(range || {}).filter(([, v]) => v));
  return { preset: { tab: "ledger", code, ...r, ...(from ? { from } : {}), ...(fromTab ? { fromTab } : {}) } };
}

export function useLedgerTrace({ from, fromTab, selectedEntity }) {
  const { go, canOpen } = useAppNav();
  const [notice, setNotice] = useState("");
  const enabled = canOpen("general-ledger");
  const trace = (code, range, rowEntityId = "", rowEntityLabel = "") => {
    const d = traceDecision({ code, range, selectedEntity, rowEntityId, rowEntityLabel, from, fromTab });
    if (!d) return;
    if (d.notice) { setNotice(d.notice); return; }
    setNotice("");
    go("general-ledger", { preset: d.preset });
  };
  return { enabled, trace, notice, clear: () => setNotice("") };
}

/** Angka/baris yang bisa diklik — `link-button` bila telusur berlaku, teks biasa bila tidak. */
export function TraceValue({ enabled, onClick, children, testId, title = "Lihat mutasi akun ini di buku besar", className = "" }) {
  if (!enabled) return <span className={className}>{children}</span>;
  return (
    <button type="button" className={`link-button tabular-nums ${className}`.trim()} data-testid={testId} title={title}
      onClick={(e) => { e.stopPropagation(); onClick(); }}>
      {children}
    </button>
  );
}

export function TraceNotice({ notice, onDismiss, testId = "trace-notice" }) {
  if (!notice) return null;
  return (
    <div className="notice-bar info mb-2 text-fs-12" role="status" data-testid={testId}>
      <Info size={13} aria-hidden="true" /><span>{notice}</span>
      <button type="button" onClick={onDismiss} aria-label="Tutup">×</button>
    </div>
  );
}
