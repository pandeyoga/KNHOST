/**
 * FASE G-6b — Wizard **RETUR ANTAR-PT** (setelah barangnya sudah berpindah).
 *
 * Pembatalan sengaja ditolak begitu barang berpindah; jalan resminya adalah retur.
 * Layar ini hanya menawarkan baris yang MASIH bisa diretur (jumlah asal − yang sudah
 * diretur), memaksa alasan tercatat, dan menunjukkan dampak uangnya sebelum disimpan.
 *
 * 23 Okt (permintaan pemilik) — roll yang dipilih membawa alasan, kondisi, checklist & foto PER ROLL (bentuk sama
 * dengan retur pelanggan & supplier), dan pop-up memakai `FormModal` standar (dulu overlay buatan sendiri yang
 * tertutup saat dropdown/klik di luar kartu — isian hilang).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Undo2, AlertTriangle, PackageCheck } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import FormModal from "../../../components/FormModal";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import { apiErrorText } from "../../../utils/apiError";
import { PickedRollClaims, claimDetails, emptyClaim, pickedClaimErrors } from "../../sales/ReturnRollClaims";

export default function IntercoReturnModal({ doc, onClose, onCreated }) {
  const [info, setInfo] = useState(null);
  const [qty, setQty] = useState({});
  // E9.4 — roll yang DIPILIH per produk. Kalau kosong, mesin mengutamakan roll hasil
  // retur pelanggan (lot RTN-…) sebelum FEFO biasa — tetapi memilih sendiri jauh lebih
  // jujur: yang dikembalikan ke PT penjual harus barang yang MEMANG diretur pelanggan.
  const [pickedRolls, setPickedRolls] = useState({});
  const [claims, setClaims] = useState({});           // { product_id: { roll_id: klaim } }
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setBusy(true); setErr("");
    try {
      const r = await axios.get(`${API}/interco/transactions/${doc.id}/returnable`);
      setInfo(r.data);
    } catch (e) { setErr(apiErrorText(e)); }
    finally { setBusy(false); }
  }, [doc.id]);

  useEffect(() => { load(); }, [load]);

  const lines = useMemo(
    () => (info?.lines || []).filter((l) => l.qty_returnable > 0), [info]);

  const totals = useMemo(() => {
    const sub = lines.reduce(
      (a, l) => a + (parseFloat(qty[l.product_id] || 0) || 0) * l.unit_price, 0);
    const rate = info?.tax_apply ? (info?.tax_rate || 0) : 0;
    const tax = Math.round(sub * rate) / 100;
    return { sub: Math.round(sub * 100) / 100, tax, total: Math.round((sub + tax) * 100) / 100 };
  }, [lines, qty, info]);

  const picked = lines.filter((l) => (parseFloat(qty[l.product_id] || 0) || 0) > 0);
  const overflow = lines.some(
    (l) => (parseFloat(qty[l.product_id] || 0) || 0) > l.qty_returnable + 0.0001);
  const rollsOf = (l) => (l.rolls || []).filter((r) => (pickedRolls[l.product_id] || []).includes(r.roll_id))
    .map((r) => ({ roll_id: r.roll_id, roll_no: r.roll_no, lot: r.lot, remaining: Number(r.qty || 0), unit: r.unit || l.unit }));
  const rollErrs = picked.flatMap((l) => pickedClaimErrors(rollsOf(l), claims[l.product_id] || {}));
  const canSubmit = picked.length > 0 && reason.trim().length >= 5 && !overflow && !busy && !rollErrs.length;

  // Memilih roll = menentukan jumlahnya. Menyimpan dua angka yang bisa berbeda
  // (jumlah vs roll) hanya melahirkan dokumen yang tidak cocok dengan barangnya.
  const toggleRoll = (line, roll) => {
    const cur = pickedRolls[line.product_id] || [];
    const next = cur.includes(roll.roll_id) ? cur.filter((x) => x !== roll.roll_id) : [...cur, roll.roll_id];
    const sum = (line.rolls || []).filter((r) => next.includes(r.roll_id)).reduce((a, r) => a + Number(r.qty || 0), 0);
    setPickedRolls((s) => ({ ...s, [line.product_id]: next }));
    setQty((q) => ({ ...q, [line.product_id]: next.length ? String(Math.round(sum * 100) / 100) : "" }));
    setClaims((c) => {
      const mine = { ...(c[line.product_id] || {}) };
      if (next.includes(roll.roll_id)) mine[roll.roll_id] = mine[roll.roll_id] || emptyClaim({ remaining: roll.qty });
      else delete mine[roll.roll_id];
      return { ...c, [line.product_id]: mine };
    });
  };

  const submit = async () => {
    if (!canSubmit) {
      setErr(rollErrs.length ? `Periksa isian roll: ${rollErrs.join("; ")}`
        : reason.trim().length < 5 ? "Alasan retur wajib diisi (minimal 5 huruf)." : "Isi jumlah retur minimal satu barang.");
      return;
    }
    setBusy(true); setErr("");
    try {
      const r = await axios.post(`${API}/interco/returns`, {
        interco_id: doc.id,
        items: picked.map((l) => ({
          product_id: l.product_id,
          quantity: parseFloat(qty[l.product_id]),
          roll_ids: pickedRolls[l.product_id] || [],
          roll_details: claimDetails(claims[l.product_id]),
        })),
        reason: reason.trim(),
        notes: notes.trim(),
      });
      // Foto bukti per roll diunggah sesudah dokumen kembar ada (tersimpan di keduanya).
      const retId = r.data?.returner?.id;
      const uploads = picked.flatMap((l) => Object.entries(claims[l.product_id] || {})
        .flatMap(([rid, c]) => (c.files || []).map((f) => [f, rid])));
      for (const [f, rid] of uploads) {
        const fd = new FormData(); fd.append("file", f); fd.append("roll_id", rid);
        await axios.post(`${API}/interco/returns/${retId}/attachments`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      }
      onCreated?.(r.data);
    } catch (e) { setErr(apiErrorText(e)); }
    finally { setBusy(false); }
  };

  return (
    <FormModal open onClose={onClose} size="lg" icon={Undo2} testId="interco-return-modal"
      title="Retur Antar-PT"
      subtitle={`atas ${info?.origin_number || doc.number} · ${info?.buyer_entity_name || ""} → ${info?.seller_entity_name || ""}`}
      onSubmit={submit} submitLabel="Buat Retur" busy={busy} error={err}
      submitDisabled={!info?.can_return || !picked.length}
      submitTestId="interco-return-submit" cancelTestId="interco-return-cancel-btn">
      <div className="space-y-4">
        {info && !info.can_return && (
          <div className="flex items-start gap-2 rounded-lg bg-[#FFF4E5] px-3 py-2.5 text-[13px] text-[#8A5300]"
               data-testid="interco-return-blocked">
            <AlertTriangle size={15} className="mt-0.5 shrink-0" />
            <span>{info.blocked_reason}</span>
          </div>
        )}

        {info?.can_return && (
          <>
            <div className="space-y-3" data-testid="interco-return-lines">
              {lines.map((l) => {
                const v = qty[l.product_id] || "";
                const bad = (parseFloat(v || 0) || 0) > l.qty_returnable + 0.0001;
                const mine = pickedRolls[l.product_id] || [];
                return (
                  <div key={l.product_id} className="rounded-lg border border-[#E5E5EA]" data-testid={`interco-return-line-${l.product_id}`}>
                    <div className="flex flex-wrap items-start justify-between gap-2 border-b border-[#EFF0F2] bg-[#FAFBFC] px-3 py-2">
                      <div className="min-w-0">
                        <p className="truncate text-[12.5px] font-semibold text-[#1C1C1E]">{l.product_name}</p>
                        <p className="text-[11px] text-[#6B6B73]">{l.sku} · harga internal {formatCurrency(l.unit_price)}/{l.unit}</p>
                      </div>
                      <div className="flex items-end gap-3 text-[11.5px] tabular-nums">
                        <span className="text-[#6B6B73]">dikirim {formatQty(l.qty_total)} · sudah diretur {formatQty(l.qty_returned)} {l.unit}</span>
                        <label className="text-[10.5px] font-semibold uppercase tracking-wide text-[#6B6B73]">Retur sekarang
                          <input type="number" min="0" step="0.01" max={l.qty_returnable} value={v}
                            disabled={mine.length > 0} title={mine.length ? "Qty = total roll yang dipilih" : ""}
                            onChange={(e) => setQty((s) => ({ ...s, [l.product_id]: e.target.value }))}
                            data-testid={`interco-return-qty-${l.product_id}`}
                            className={`form-input mt-1 block w-28 text-right tabular-nums ${bad ? "!border-[#A8221A]" : ""}`}
                            placeholder={`maks ${formatQty(l.qty_returnable)}`} />
                        </label>
                      </div>
                    </div>
                    <div className="space-y-2 px-3 py-2">
                      <p className="text-[10.5px] font-semibold uppercase tracking-wide text-[#6B6B73]">Roll yang dikirim balik</p>
                      {(l.rolls || []).length === 0 ? (
                        <span className="text-[11px] text-[#8E8E93]">Tidak ada roll tersedia di gudang.</span>
                      ) : (
                        <div className="flex max-h-32 flex-wrap gap-1.5 overflow-y-auto" data-testid={`interco-return-rolls-${l.product_id}`}>
                          {(l.rolls || []).map((rr) => {
                            const on = mine.includes(rr.roll_id);
                            return (
                              <label key={rr.roll_id} data-testid={`interco-return-roll-${rr.roll_id}`}
                                className={`inline-flex cursor-pointer items-center gap-1.5 rounded border px-1.5 py-1 text-[11px] ${
                                  on ? "border-[#0058CC] bg-[#EAF2FF]" : "border-[#E5E5EA] bg-white"}`}>
                                <input type="checkbox" checked={on} onChange={() => toggleRoll(l, rr)} />
                                <span className="font-mono">{rr.roll_no || rr.roll_id.slice(-6)}</span>
                                <span className="text-[#6E6E73]">{rr.lot}</span>
                                <span className="tabular-nums">{formatQty(rr.qty)} {rr.unit}</span>
                                {rr.grade ? <span className="text-[#8E8E93]">gr {rr.grade}</span> : null}
                                {rr.is_customer_return && (
                                  <span className="inline-flex items-center gap-0.5 rounded border border-[#F5C9A6] bg-[#FFF7EF] px-1 py-0.5 text-[9.5px] text-[#8C4A00]">
                                    <PackageCheck size={9} /> retur pelanggan
                                  </span>
                                )}
                              </label>
                            );
                          })}
                        </div>
                      )}
                      {l.warning && (
                        <p data-testid={`interco-return-warning-${l.product_id}`}
                           className="rounded border border-[#F1D9AE] bg-[#FFF4E5] px-1.5 py-1 text-[10.5px] leading-snug text-[#8A5300]">
                          {l.warning}
                        </p>
                      )}
                      <p className="text-[10px] text-[#8E8E93]">
                        di gudang {formatQty(l.qty_on_hand || 0)} {l.unit} · dari retur pelanggan {formatQty(l.qty_from_customer_return || 0)} {l.unit}
                      </p>
                      <PickedRollClaims rolls={rollsOf(l)} claims={claims[l.product_id] || {}} testId={`interco-return-claims-${l.product_id}`}
                        onChange={(next) => setClaims((c) => ({ ...c, [l.product_id]: next }))} />
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3" data-testid="interco-return-totals">
              <Box label="Nilai barang" value={formatCurrency(totals.sub)} />
              <Box label={`PPN ${info.tax_apply ? `${info.tax_rate}%` : "—"}`} value={formatCurrency(totals.tax)} />
              <Box label="Utang antar-PT berkurang" value={formatCurrency(totals.total)} />
            </div>

            <div className="space-y-2">
              <label className="form-label" htmlFor="interco-return-reason">Alasan retur <span className="req">*</span> (minimal 5 huruf)</label>
              <textarea id="interco-return-reason" rows={2} value={reason} onChange={(e) => setReason(e.target.value)}
                data-testid="interco-return-reason" placeholder="mis. warna kain tidak sesuai contoh yang disetujui"
                className="form-input w-full" />
              <label className="form-label" htmlFor="interco-return-notes">Catatan (opsional)</label>
              <input id="interco-return-notes" value={notes} onChange={(e) => setNotes(e.target.value)}
                data-testid="interco-return-notes" className="form-input w-full" />
            </div>

            <p className="text-[11px] text-[#8E8E93]">
              Retur terbit sebagai <b>draf</b>. Sebelum disetujui, pemegang izin bisa menerima/menolak per roll. Jurnal
              pembalik di dua buku baru terbit setelah <b>disetujui rekan lain</b> (pembuat ≠ penyetuju), dan barangnya baru
              keluar dari gudang pembeli setelah <b>tugas gudang</b> arah balik disetujui.
            </p>
          </>
        )}
      </div>
    </FormModal>
  );
}

function Box({ label, value }) {
  return (
    <div className="rounded-lg border border-[#E5E5EA] bg-white p-3">
      <div className="text-[10px] uppercase tracking-wide text-[#8E8E93]">{label}</div>
      <div className="mt-1 text-[15px] font-semibold text-[#1D1D1F] tabular-nums">{value}</div>
    </div>
  );
}
