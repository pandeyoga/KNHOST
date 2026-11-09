/**
 * DocNumber — FIX-8 (B1b UI-58 · KN_37 §8a): nomor dokumen dengan SATU skema TAMPILAN `[PT] NOMOR`.
 *
 * Masalah: dua skema nomor tersimpan hidup berdampingan — per PT (`KSC/PO-00166`, `KSC/GRN-00023`) dan skema grup
 * tanpa PT (`PRET-00070`, `SRET-00167`, `PR-00209`). Dari nomor saja tidak terbaca PT pemiliknya, dan satu baris
 * bisa memuat "SRET-00167 · KSC/SO-00001". Keputusan FIX-8: **tampilan saja** — nomor tersimpan TIDAK diubah.
 * Keduanya kini tampil sama: lencana kode PT + nomor. Kode PT diambil dari awalan nomor (`KSC/…`) atau, bila nomor
 * tanpa awalan, dari `entityId` dokumen (konteks login, `entityCodeFromCtx`). Nomor tersimpan utuh ada di `title`
 * (disalin/dicari pengguna apa adanya). PT tak dikenal → tanpa lencana (tidak pernah id).
 *
 * Props: number · entityId · entityCode (bila layar sudah tahu kodenya) · testId · className.
 */
import { entityCodeFromCtx } from "../utils/entityLabel";

const PREFIXED = /^([A-Z0-9]{2,12})\/(.+)$/;

/** "KSC/PO-00166" → {pt: "KSC", no: "PO-00166"}; "PRET-00070" → {pt: "", no: "PRET-00070"}. */
export function splitDocNumber(number) {
  const s = String(number || "").trim();
  const m = PREFIXED.exec(s);
  return m ? { pt: m[1], no: m[2] } : { pt: "", no: s };
}

/** Teks satu baris skema tampilan: "KSC · PO-00166" (dipakai di teks/konfirmasi). Kosong → "—". */
export function docNumberText(number, entityId = "") {
  if (!number) return "—";
  const { pt, no } = splitDocNumber(number);
  const code = pt || entityCodeFromCtx(entityId);
  return code ? `${code} · ${no}` : no;
}

export default function DocNumber({ number, entityId = "", entityCode = "", testId, className = "" }) {
  if (!number) return <span className={className} data-testid={testId}>—</span>;
  const { pt, no } = splitDocNumber(number);
  const code = pt || entityCode || entityCodeFromCtx(entityId);
  return (
    <span className={`kn-docno${className ? ` ${className}` : ""}`} title={String(number)} data-testid={testId}
      data-docno={String(number)}>
      {code ? <span className="kn-docno-pt" title={`PT pemilik dokumen: ${code}`}>{code}</span> : null}
      {/* Pemisah tak terlihat: teks elemen = nomor tersimpan apa adanya ("KSC/PO-00166") untuk nomor berawalan PT —
          salin-tempel, pencarian peramban, dan uji berbasis teks tidak berubah; nomor tanpa awalan → "KSC · PRET-…". */}
      {code ? <span className="sr-only">{pt ? "/" : " · "}</span> : null}
      <span className="kn-docno-no">{no}</span>
    </span>
  );
}

export { DocNumber };
