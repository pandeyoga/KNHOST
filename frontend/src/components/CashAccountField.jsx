/**
 * CashAccountField (PK-20 · SL-11) — isian **Rekening** untuk form yang melahirkan kas.
 *
 * Server mewajibkan rekening pada setiap transaksi kas (`cash_ledger.create_cash`): rekening AKTIF milik PT dokumen,
 * atau rekening tunggal PT untuk jenis kasnya. Isian ini menawarkan rekening yang sama dari `GET /api/bank-accounts`:
 *
 *   <CashAccountField entityId={pt} cashType="kas_besar" value={acc} onChange={setAcc} onState={setAccState} />
 *   tombol simpan: disabled={... || cashAccountBlocked(accState, acc)}
 *
 * Keadaan (`onState`): "memuat" · "kosong" (PT belum punya rekening jenis itu — pesan + simpan mati) · "tunggal"
 * (satu rekening: terisi otomatis & terkunci) · "pilih" (lebih dari satu: wajib dipilih) · "galat" (daftar gagal dimuat:
 * pesan tampil, simpan TIDAK dimatikan — server tetap menolak bila rekening tak bisa ditentukan) · "tanpa_pt".
 * Label opsi "{nama rekening} · {bank} {nomor}". `cashType` kosong = semua jenis.
 * PK-24 — `onAccount` (opsional) menerima dokumen rekening terpilih (atau null) untuk kalimat konfirmasi
 * ("… ke {nama rekening} · {PT}?").
 * Kas & Bank 3 — jenis kas rekening mengenal `kas_kasir` (uang tunai pelanggan): rekening kasir BUKAN kas kecil, jadi
 * hanya ditawarkan di pemilih tanpa jenis atau berjenis `kas_kasir` (bukan di pencairan PD, sisa LPJ, kas manual kas
 * kecil, refund kas kecil). Jenisnya dari bidang server `cash_type` (`jenisKas.jenisKasRekening`).
 */
import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../services/apiClient";
import KNSelect from "./KNSelect";
import { apiErrorText } from "../utils/apiError";
import { useEntityScope } from "../context/EntityScopeContext";
import { entityShort } from "../utils/entityLabel";
import { JENIS_KAS_JUDUL, jenisKasRekening } from "../features/finance/jenisKas";

/** Label jenis untuk kalimat isian ("Satu-satunya rekening {jenis} …"); kas besar = rekening bank/transfer. */
export const CASH_TYPE_LABEL = { kas_kasir: JENIS_KAS_JUDUL.kas_kasir, kas_kecil: JENIS_KAS_JUDUL.kas_kecil, kas_besar: "Bank" };

/** Jenis kas rekening — sama dengan `bank_service.account_cash_type` (master rekening, bukan transaksi): `kas_kasir`,
 *  `kas_kecil`, atau `kas_besar` bila tersimpan; selain itu dari jenis rekening (tunai = kas kecil, bank = kas besar). */
export const accountCashType = jenisKasRekening;

export function cashAccountLabel(a) {
  const bank = [a?.bank_name, a?.account_number].filter(Boolean).join(" ");
  return `${a?.name || "Rekening"}${bank ? ` · ${bank}` : ""}`;
}

const aktif = (a) => a && a.is_active !== false && a.status !== "inactive";

/** Simpan dimatikan selama daftar dimuat, PT tanpa rekening jenis itu, atau ada pilihan tetapi belum dipilih.
 *  "galat" dan "tanpa_pt" tidak mematikan: server yang menentukan (rekening tunggal) atau menolak dengan pesannya. */
export function cashAccountBlocked(state, value) {
  return state === "memuat" || state === "kosong" || (state === "pilih" && !value);
}

/** Alasan tombol simpan mati (ditulis di samping tombol — tombol mati tidak boleh hanya bertooltip). */
export function cashAccountBlockReason(state) {
  if (state === "memuat") return "Memuat rekening…";
  if (state === "kosong") return "PT ini belum punya rekening untuk jenis kas ini.";
  if (state === "pilih") return "Pilih rekening dulu.";
  return "";
}

export default function CashAccountField({ entityId, cashType = "", value, onChange, onState, onAccount,
  label = "Rekening", testId = "cash-account", className = "" }) {
  const { entities } = useEntityScope();
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState("");
  const ptName = entityShort((entities || []).find((e) => e && e.id === entityId), "PT ini");
  const scoped = !!entityId && entityId !== "all";

  useEffect(() => {
    let mati = false;
    setRows(null); setErr("");
    if (!scoped) return undefined;
    Promise.resolve()
      .then(() => axios.get(`${API}/bank-accounts`, { params: { entity_id: entityId } }))
      .then((r) => {
        if (!Array.isArray(r?.data)) throw new Error("Daftar rekening gagal dimuat.");
        if (!mati) setRows(r.data);
      })
      .catch((e) => { if (!mati) { setErr(apiErrorText(e, "Daftar rekening gagal dimuat.")); setRows([]); } });
    return () => { mati = true; };
  }, [entityId, scoped]);

  const options = useMemo(() => (rows || [])
    .filter((a) => aktif(a) && a.entity_id === entityId && (!cashType || accountCashType(a) === cashType))
    .map((a) => ({ value: a.id, label: cashAccountLabel(a) })), [rows, entityId, cashType]);

  let state = "pilih";
  if (!scoped) state = "tanpa_pt";
  else if (rows === null) state = "memuat";
  else if (err) state = "galat";
  else if (options.length === 0) state = "kosong";
  else if (options.length === 1) state = "tunggal";

  useEffect(() => { onState?.(state); }, [state]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { onAccount?.((rows || []).find((a) => a.id === value) || null); }, [rows, value]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (state === "tunggal" && value !== options[0].value) onChange?.(options[0].value);
    else if ((state === "pilih" || state === "kosong") && value && !options.some((o) => o.value === value)) onChange?.("");
  }, [state, options, value]); // eslint-disable-line react-hooks/exhaustive-deps

  const jenis = CASH_TYPE_LABEL[cashType] || "kas/bank";
  return (
    <div className={className} data-testid={testId}>
      <label className="text-fs-12 font-bold uppercase tracking-wide text-kn-text-2">{label}</label>
      <KNSelect data-testid={`${testId}-select`} className="field" value={value || ""}
        onValueChange={(v) => onChange?.(v)} options={options} disabled={state !== "pilih"}
        placeholder={state === "memuat" ? "Memuat rekening…" : "Pilih rekening"} />
      {state === "tunggal" && (
        <p className="mt-1 text-fs-12 text-kn-text-2" data-testid={`${testId}-sole`}>
          Satu-satunya rekening {jenis} {ptName}
        </p>
      )}
      {state === "kosong" && (
        <p className="mt-1 text-fs-12 text-kn-danger-text" data-testid={`${testId}-none`}>
          Belum ada rekening {jenis} untuk {ptName}. Tambahkan di Kas &amp; Bank › Rekening &amp; Saldo.
        </p>
      )}
      {state === "galat" && (
        <p className="mt-1 text-fs-12 text-kn-warning-text" data-testid={`${testId}-error`}>
          {err} Rekening ditentukan server bila {ptName} hanya punya satu rekening {jenis}.
        </p>
      )}
      {state === "tanpa_pt" && (
        <p className="mt-1 text-fs-12 text-kn-text-2" data-testid={`${testId}-no-entity`}>
          Pilih PT di kepala aplikasi untuk memilih rekening.
        </p>
      )}
    </div>
  );
}
