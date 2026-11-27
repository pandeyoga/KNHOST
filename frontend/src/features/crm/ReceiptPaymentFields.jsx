/**
 * PM-T3 — isian uang masuk di form kwitansi (desktop & HP memakai `ARReceiptModal` yang sama): "Rekening penerima",
 * "No. referensi", "Jatuh tempo giro", "Bukti (tautan)", dan peringatan "Tidak sesuai instruksi bayar pesanan" beserta
 * isian wajib "Catatan alasan".
 *
 * Rekening dari `GET /api/bank-accounts/receiving?method=&entity_id=` (rekening aktif PT kwitansi yang dipakai menerima
 * uang pelanggan dan melayani cara bayar itu — rekening PT lain tidak pernah muncul). Terisi otomatis: rekening tujuan
 * pesanan yang dialokasi (instruksi bayar PM-T2) bila semua pesanan menunjuk rekening yang sama, lalu rekening bawaan PT,
 * lalu satu-satunya rekening. Pilihan pengguna tidak ditimpa. Server memeriksa ulang semuanya (`periksa_uang_masuk`).
 *
 * PM-T4 — `titipan` (tunai yang dicatat sebagai titipan di tangan pencatat sampai disetor): tanpa isian rekening (belum
 * ada kas); "Tidak sesuai instruksi" = pesanan berinstruksi rekening yang tidak menerima tunai di PT ini.
 *
 * F1 — `lockAccount` (kwitansi dari mutasi bank): rekening = rekening mutasi (server mengisinya dari baris mutasi), jadi
 * pilihan terkunci dan tidak diisi otomatis; peringatan "tidak sesuai instruksi" + catatan wajib tetap berlaku.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Lock } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import KNDatePicker from "../../components/KNDatePicker";
import axios, { API } from "../../services/apiClient";
import { accountText } from "../pos/CheckoutPaymentDestination";

export const MISMATCH_NOTE_MIN = 5;
export const PESAN_REKENING_KOSONG =
  "Belum ada rekening penerimaan untuk cara bayar ini — minta Finance mengaturnya di Kas & Bank.";

/** Rekening tujuan (instruksi bayar) pesanan yang tidak diikuti rekening penerima terpilih. */
export function mismatchOrders(orders, accountId) {
  if (!accountId) return [];
  return (orders || []).filter((o) => o?.receiving_account_id && o.receiving_account_id !== accountId);
}

/**
 * Alasan tombol simpan dimatikan (teks tampil di samping tombol), atau "" bila boleh disimpan.
 * `state` = { status: "memuat"|"siap"|"kosong"|"gagal"|"tanpa" (cara bayar tanpa rekening), accountId, needsReference,
 *             refRequired, reference,
 *             needsDueDate, giroDue, mismatch: [..], mismatchNote, methodName }
 */
export function receiptBlockReason(state) {
  if (!state) return "";
  if (state.status === "memuat") return "Memuat rekening penerima…";
  if (state.status === "kosong") return PESAN_REKENING_KOSONG;
  if (state.status === "siap" && !state.accountId) return "Pilih rekening penerima.";
  if (state.refRequired && state.needsReference && !String(state.reference || "").trim()) {
    return `Isi nomor referensi (wajib untuk ${state.methodName || "cara bayar ini"}).`;
  }
  if (state.refRequired && state.needsDueDate && !state.giroDue) return "Isi jatuh tempo giro.";
  if ((state.mismatch || []).length && String(state.mismatchNote || "").trim().length < MISMATCH_NOTE_MIN) {
    return "Isi catatan alasan — rekening berbeda dari instruksi bayar pesanan.";
  }
  return "";
}

export default function ReceiptPaymentFields({
  entityId = "", method = "", methodRow = null, orders = [], refRequired = false, value, onChange, onState,
  titipan = false, lockAccount = false,
}) {
  const v = value || {};
  // Cara bayar belum dikenal (daftar induk belum termuat) → tetap minta daftar rekening untuk kode itu (server memutus).
  const needsAccount = methodRow ? ["bank", "kas"].includes(methodRow.needs_account) : Boolean(method);
  const [list, setList] = useState({ key: "", rows: [], loading: false, failed: false });
  const key = `${entityId}|${method}`;
  const touched = useRef(Boolean(v.accountTouched));

  useEffect(() => {
    if (!method || !needsAccount) { setList({ key, rows: [], loading: false, failed: false }); return undefined; }
    let alive = true;
    setList({ key, rows: [], loading: true, failed: false });
    const params = { method };
    if (entityId && entityId !== "all") params.entity_id = entityId;
    axios.get(`${API}/bank-accounts/receiving`, { params })
      .then((r) => { if (alive) setList({ key, rows: Array.isArray(r.data) ? r.data : [], loading: false, failed: false }); })
      .catch(() => { if (alive) setList({ key, rows: [], loading: false, failed: true }); });
    return () => { alive = false; };
  }, [key, needsAccount]); // eslint-disable-line react-hooks/exhaustive-deps

  const rows = list.key === key ? list.rows : [];
  const tujuan = useMemo(() => [...new Set((orders || []).map((o) => o?.receiving_account_id).filter(Boolean))],
    [orders]);

  // Isi otomatis rekening penerima (instruksi pesanan → bawaan PT → satu-satunya); pilihan pengguna tidak ditimpa.
  useEffect(() => {
    if (lockAccount || titipan || !needsAccount || list.key !== key || list.loading) return;
    if (touched.current && rows.some((a) => a.id === v.accountId)) return;
    const instr = tujuan.length === 1 ? rows.find((a) => a.id === tujuan[0]) : null;
    const pick = instr || rows.find((a) => a.is_default) || (rows.length === 1 ? rows[0] : null);
    const next = pick ? pick.id : "";
    if (next !== (v.accountId || "")) onChange({ ...v, accountId: next });
  }, [list, tujuan.join("|"), needsAccount]); // eslint-disable-line react-hooks/exhaustive-deps

  const status = (titipan || !needsAccount) ? "tanpa"
    : (list.key !== key || list.loading) ? "memuat" : list.failed ? "gagal" : rows.length === 0 ? "kosong" : "siap";
  const listReady = list.key === key && !list.loading && !list.failed;
  const beda = titipan
    ? (listReady ? (orders || []).filter((o) => o?.receiving_account_id && !rows.some((a) => a.id === o.receiving_account_id)) : [])
    : mismatchOrders(orders, v.accountId);
  const chosen = rows.find((a) => a.id === v.accountId) || null;

  useEffect(() => {
    onState?.({ status, accountId: v.accountId || "", accountLabel: chosen ? `${chosen.name} · ${accountText(chosen)}` : "",
      needsReference: Boolean(methodRow?.needs_reference), refRequired, reference: v.reference || "",
      needsDueDate: Boolean(methodRow?.needs_due_date), giroDue: v.giroDue || "", mismatch: beda,
      mismatchNote: v.mismatchNote || "", methodName: methodRow?.name || "" });
  }, [status, v.accountId, v.reference, v.giroDue, v.mismatchNote, beda.length, refRequired, methodRow?.code, chosen?.id, titipan]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (patch) => onChange({ ...v, ...patch });
  const refLabel = `No. referensi${refRequired && methodRow?.needs_reference ? " *" : ""}`;
  const locked = rows.length === 1 || lockAccount;

  return (
    <div className="grid gap-2" data-testid="ar-receipt-payment-fields">
      {needsAccount && !titipan && (
        <div data-testid="ar-receipt-account-field">
          <span className="field-label">Rekening penerima</span>
          {status === "memuat" ? (
            <p className="text-fs-12 text-kn-text-2" data-testid="ar-receipt-account-loading">Memuat rekening…</p>
          ) : status === "gagal" ? (
            <p className="flex items-start gap-1.5 text-fs-12 text-kn-warning-text" data-testid="ar-receipt-account-failed">
              <AlertTriangle size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
              Daftar rekening gagal dimuat. Pembayaran tetap bisa disimpan — rekening bawaan PT dipakai server.
            </p>
          ) : status === "kosong" ? (
            <p className="flex items-start gap-1.5 text-fs-12 text-kn-danger-text" data-testid="ar-receipt-account-empty">
              <AlertTriangle size={13} className="mt-0.5 shrink-0" aria-hidden="true" /> {PESAN_REKENING_KOSONG}
            </p>
          ) : (
            <>
              <KNSelect data-testid="ar-receipt-account" className="field" value={v.accountId || ""} disabled={locked}
                placeholder="Pilih rekening penerima"
                onValueChange={(id) => { touched.current = true; set({ accountId: id, accountTouched: true }); }}
                options={rows.map((a) => ({ value: a.id, label: `${a.name} · ${accountText(a)}` }))} />
              {locked && (
                <p className="mt-1 flex items-center gap-1 text-fs-12 text-kn-text-2" data-testid="ar-receipt-account-locked">
                  <Lock size={12} aria-hidden="true" />
                  {lockAccount ? "Rekening mutasi bank — kwitansi masuk ke rekening ini."
                    : "Satu-satunya rekening penerimaan PT ini untuk cara bayar ini."}
                </p>
              )}
            </>
          )}
        </div>
      )}

      {beda.length > 0 && (
        <div className="rounded-md border border-kn-divider bg-kn-warning-soft px-3 py-2" data-testid="ar-receipt-mismatch">
          {beda.map((o) => (
            <p key={o.order_id} className="flex items-start gap-1.5 text-fs-12 font-semibold text-kn-warning-text">
              <AlertTriangle size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
              Tidak sesuai instruksi bayar pesanan {o.number}
              {accountText(o.receiving_account) ? ` (${accountText(o.receiving_account)})` : ""}
            </p>
          ))}
          <label className="field-label mt-2 block" htmlFor="ar-receipt-mismatch-note">Catatan alasan *</label>
          <textarea id="ar-receipt-mismatch-note" data-testid="ar-receipt-mismatch-note" className="field" rows={2}
            value={v.mismatchNote || ""} placeholder="Contoh: pelanggan salah transfer ke rekening lain"
            onChange={(e) => set({ mismatchNote: e.target.value })} />
        </div>
      )}

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <div>
          <label className="field-label" htmlFor="ar-receipt-reference">{refLabel}</label>
          <input id="ar-receipt-reference" data-testid="ar-receipt-reference" className="field" value={v.reference || ""}
            maxLength={80} placeholder="Nomor transaksi di bukti transfer" onChange={(e) => set({ reference: e.target.value })} />
        </div>
        {methodRow?.needs_due_date ? (
          <div>
            <span className="field-label">{`Jatuh tempo giro${refRequired ? " *" : ""}`}</span>
            <KNDatePicker data-testid="ar-receipt-giro-due" value={v.giroDue || ""} onChange={(d) => set({ giroDue: d || "" })} />
          </div>
        ) : (
          <div>
            <label className="field-label" htmlFor="ar-receipt-proof">Bukti (tautan)</label>
            <input id="ar-receipt-proof" data-testid="ar-receipt-proof" className="field" type="url" value={v.proofUrl || ""}
              maxLength={500} placeholder="https://…" onChange={(e) => set({ proofUrl: e.target.value })} />
          </div>
        )}
      </div>
      {methodRow?.needs_due_date && (
        <div>
          <label className="field-label" htmlFor="ar-receipt-proof">Bukti (tautan)</label>
          <input id="ar-receipt-proof" data-testid="ar-receipt-proof" className="field" type="url" value={v.proofUrl || ""}
            maxLength={500} placeholder="https://…" onChange={(e) => set({ proofUrl: e.target.value })} />
        </div>
      )}
    </div>
  );
}
