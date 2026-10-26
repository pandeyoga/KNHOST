/** R1/R3 — Modal penyelesaian retur (settle). inspected → refund/credit/nego settled.
 *  Empat outcome + partial per item (kecualikan item / sebagian qty).
 *  R3 — untuk outcome yang mengembalikan barang ke stok (refund/store_credit),
 *  user memilih LOKASI gudang penerimaan (return_warehouse_id). Kepemilikan (owner)
 *  tetap = entitas SO agar rekonsiliasi subledger↔GL persediaan aman; perpindahan
 *  kepemilikan lintas-PT dilakukan via aksi "Transfer Kepemilikan" di panel karantina. */
import { useState, useEffect } from "react";
import axios, { API } from "../../services/apiClient";
import { CheckCircle2, Loader2, X, Wallet, Coins, Percent, Warehouse, Info, Repeat, Receipt } from "lucide-react";
import { fmtNum } from "./ReturnShared";
import KNSelect from "../../components/KNSelect";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { apiErrorText } from "../../utils/apiError";

// UAT 23 Okt — "Tukar Barang" jadi pilihan keputusan sendiri (dulu hanya lewat tipe pengajuan "Penggantian"):
// di server = Store Credit + retur menjadi tipe penggantian → Admin Sales membuat pesanan pengganti.
const OUTCOMES = [
  { value: "refund", label: "Pengembalian Dana", desc: "Kembalikan dana (tunai/piutang) + barang masuk stok", icon: Wallet },
  { value: "store_credit", label: "Store Credit", desc: "Tambah saldo pelanggan (potong bon) + barang masuk stok", icon: Coins },
  { value: "exchange", label: "Tukar Barang", desc: "Nilai jadi saldo untuk pesanan pengganti (barang sama) + barang masuk stok", icon: Repeat },
  { value: "nego", label: "Nego (Diskon)", desc: "Nota Kredit cutloss/diskon tanpa gerak stok", icon: Percent },
];
const TYPE_LABEL = { retur: "Retur", bs: "BS", komplain: "Komplain", garansi: "Garansi", penggantian: "Penggantian" };

/** UAT 23 Okt — nilai keputusan SEBELUM diselesaikan (dulu modal tanpa rupiah sama sekali): Nota Kredit, pembagiannya,
 *  barang ke stok, dan jurnal — dihitung server dengan fungsi yang sama dengan penyelesaian (`/settle-preview`). */
export function SettleValuePanel({ pv, err, busy }) {
  if (err) return <p className="mt-3 rounded-md bg-[#FDECEC] px-2.5 py-1.5 text-[12px] text-[#A8221A]" data-testid="settle-preview-error">{err}</p>;
  if (!pv) return busy ? <p className="mt-3 text-[11.5px] text-[#6B6B73]" data-testid="settle-preview-loading">Menghitung nilai keputusan…</p> : null;
  if (pv.blocked) return <p className="notice-bar mt-3 text-[11.5px]" data-testid="settle-preview-blocked">{pv.blocked}</p>;
  const billed = pv.split.some((x) => x.kind === "source_bill");
  return (
    <div className={`mt-3 rounded-lg border border-[#DCE6F5] bg-[#F8FBFF] p-3 text-[12px] ${busy ? "opacity-60" : ""}`} data-testid="settle-preview">
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-semibold text-[#1B4F9C]"><Receipt size={13} className="mr-1 inline" />Nilai Nota Kredit</span>
        <span className="text-[15px] font-bold tabular-nums" data-testid="settle-preview-gross">{formatCurrency(pv.gross_amount)}</span>
      </div>
      <ul className="mt-1.5 space-y-0.5 text-[11.5px] text-[#3F4652]">
        {pv.lines.map((l, i) => (
          <li key={i} className="flex justify-between gap-3" data-testid={`settle-preview-line-${i}`}>
            <span>{l.roll_no ? <b>{l.roll_no} · {l.outcome_label} · </b> : null}{l.product_name} · {formatQty(l.quantity)} {l.unit} × {formatCurrency(l.unit_price)}</span>
            <span className="tabular-nums">{formatCurrency(l.line_total)}</span>
          </li>))}
        <li className="flex justify-between border-t border-[#E4ECF7] pt-1"><span>DPP</span><span className="tabular-nums">{formatCurrency(pv.net_amount)}</span></li>
        <li className="flex justify-between"><span>PPN (rasio PPN SO asal)</span><span className="tabular-nums">{formatCurrency(pv.ppn_amount)}</span></li>
      </ul>
      <p className="mt-2 font-semibold">Ke mana nilainya</p>
      <ul className="space-y-0.5 text-[11.5px]" data-testid="settle-preview-split">
        {pv.split.map((x) => (
          <li key={x.kind} className="flex justify-between gap-3"><span>{x.label}</span><span className="font-semibold tabular-nums">{formatCurrency(x.amount)}</span></li>))}
        {pv.source_bill_checked && !billed && <li className="text-[#6B6B73]">{pv.order_number || "SO asal"} sudah lunas — tidak ada tagihan yang dipotong.</li>}
      </ul>
      <p className="mt-2 text-[11.5px] text-[#3F4652]" data-testid="settle-preview-stock">
        {pv.post_stock
          ? <>Barang masuk stok (karantina){pv.cogs_amount != null && <> — nilai persediaan kembali {formatCurrency(pv.cogs_amount)} (WAC)</>}.</>
          : "Tanpa gerak stok — barang tidak masuk stok."}
      </p>
      <details className="mt-2" data-testid="settle-preview-journal">
        <summary className="cursor-pointer text-[11.5px] font-semibold text-[#0058CC]">Lihat jurnal yang akan terbentuk</summary>
        <table className="mt-1.5 w-full text-[11px]">
          <thead><tr className="text-left text-[#6B6B73]"><th className="font-semibold">Akun</th><th className="text-right font-semibold">Debit</th><th className="text-right font-semibold">Kredit</th></tr></thead>
          <tbody>
            {pv.journal.map((j, i) => (
              <tr key={i}>
                <td className="py-0.5">{j.account_code} {j.account_name}</td>
                <td className="text-right tabular-nums">{j.debit ? formatCurrency(j.debit) : ""}</td>
                <td className="text-right tabular-nums">{j.credit ? formatCurrency(j.credit) : ""}</td>
              </tr>))}
          </tbody>
        </table>
        {pv.cost_hidden && <p className="mt-1 text-[10.5px] text-[#6B6B73]">Baris persediaan/HPP hanya terlihat oleh Manajer/Admin.</p>}
      </details>
      <p className="mt-1.5 text-[10.5px] text-[#6B6B73]">{pv.basis}. Angka resmi = Nota Kredit saat diselesaikan.</p>
    </div>
  );
}

export default function ReturnSettleModal({ ret, open, onClose, onSettle }) {
  // Cek UI UAT v3 (S15) — retur Penggantian (tukar barang) = Store Credit: nilainya jadi saldo yang dipakai pesanan
  // pengganti (panel "Pesanan pengganti"). Dulu default Pengembalian Dana tanpa petunjuk → pengguna mencari outcome "Tukar".
  const isSwap = ret.return_type === "penggantian";
  const [outcome, setOutcome] = useState(isSwap ? "exchange" : "refund");
  const apiOutcome = outcome === "exchange" ? "store_credit" : outcome;
  const [notes, setNotes] = useState("");
  const [decisionNote, setDecisionNote] = useState("");   // L08 LN-081 — bukti keputusan di luar sistem
  const [payout, setPayout] = useState("store_credit");   // KLR-10 — nego: customer pilih refund / saldo
  const physLocs = Object.values(ret.roll_locations || {});
  const physNames = [...new Set(physLocs.map((l) => l.warehouse_name || l.to_warehouse_name).filter(Boolean))];
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");   // FE-07 — pesan gagal tampil DI modal; input tetap
  const [warehouses, setWarehouses] = useState([]);
  const [returnWarehouseId, setReturnWarehouseId] = useState("");
  const [cashAccounts, setCashAccounts] = useState([]);
  const [refundAccount, setRefundAccount] = useState("");
  const [decisions, setDecisions] = useState(() =>
    (ret.items || []).map((it) => ({ include: true, settle_qty: it.quantity_returned ?? 0 })));

  // R3 — daftar gudang; R5.3 — daftar akun Kas/Bank untuk refund tunai
  useEffect(() => {
    if (!open) return;
    let active = true;
    (async () => {
      try {
        const res = await axios.get(`${API}/warehouses`);
        const list = Array.isArray(res.data) ? res.data : (res.data?.items || []);
        if (active) setWarehouses(list);
      } catch { if (active) setWarehouses([]); }
      try {
        const res2 = await axios.get(`${API}/gl/cash-accounts`);
        if (active) setCashAccounts(Array.isArray(res2.data) ? res2.data : []);
      } catch { if (active) setCashAccounts([]); }
    })();
    return () => { active = false; };
  }, [open]);

  const itemDecisions = () => decisions.map((d, i) => ({
    index: i,
    outcome: d.include ? "" : "reject",
    settle_qty: d.include ? (parseFloat(d.settle_qty) || 0) : -1,
  }));
  const refundAcc = outcome === "refund" || (outcome === "nego" && payout === "refund") ? refundAccount : "";

  // Nilai keputusan dihitung ulang tiap pilihan berubah (jeda singkat supaya tidak memanggil server per ketikan).
  const [pv, setPv] = useState(null);
  const [pvErr, setPvErr] = useState("");
  const [pvBusy, setPvBusy] = useState(false);
  const pvKey = JSON.stringify([apiOutcome, outcome === "exchange", itemDecisions(), outcome === "nego" ? payout : "", refundAcc]);
  useEffect(() => {
    if (!open) return undefined;
    let alive = true;
    setPvBusy(true);
    const t = setTimeout(async () => {
      const [o, exchange, item_decisions, po, acc] = JSON.parse(pvKey);
      try {
        const r = await axios.post(`${API}/sales-returns/${ret.id}/settle-preview`,
          { outcome: o, exchange, item_decisions, payout: po, refund_account_code: acc });
        if (alive) { setPv(r.data); setPvErr(""); }
      } catch (e) {
        if (alive) { setPv(null); setPvErr(apiErrorText(e, "Nilai keputusan belum bisa dihitung.")); }
      } finally { if (alive) setPvBusy(false); }
    }, 300);
    return () => { alive = false; clearTimeout(t); };
  }, [open, ret.id, pvKey]);

  if (!open) return null;
  const upd = (i, patch) => setDecisions((d) => d.map((x, idx) => (idx === i ? { ...x, ...patch } : x)));
  const movesStock = apiOutcome === "refund" || apiOutcome === "store_credit";

  async function confirm() {
    setBusy(true); setErr("");
    try {
      const failed = await onSettle(ret, apiOutcome, itemDecisions(), notes, movesStock && !physLocs.length ? returnWarehouseId : "",
                     refundAcc, decisionNote, outcome === "nego" ? payout : "", outcome === "exchange");
      if (failed) { setErr(failed); return; }
      onClose();
    } finally { setBusy(false); }
  }

  const anyIncluded = decisions.some((d) => d.include && (parseFloat(d.settle_qty) || 0) > 0);
  const ownerName = ret.entity_short_name || ret.entity_name || ret.entity_id || "entitas SO";

  return (
    <div className="modal-overlay" data-testid="settle-modal">
      <div className="modal-card" style={{ maxWidth: 760 }}>
        <div className="flex items-center justify-between mb-1">
          <h3 className="modal-title">Selesaikan Retur {ret.number}</h3>
          <button className="icon-button" onClick={onClose}><X size={15} /></button>
        </div>
        <p className="modal-subtitle">Pilih outcome & item yang diselesaikan (bisa sebagian / kecualikan item).</p>

        {/* Outcome selector */}
        <div className="grid grid-cols-2 gap-2 my-3 sm:grid-cols-4">
          {OUTCOMES.map((o) => {
            const Icon = o.icon; const active = outcome === o.value;
            return (
              <button key={o.value} type="button" data-testid={`settle-outcome-${o.value}`}
                onClick={() => setOutcome(o.value)}
                className={`text-left rounded-md border p-2.5 transition ${active
                  ? "border-[#0058CC] bg-[#EAF2FF]" : "border-[#EFF0F2] bg-white hover:border-[#C9CDD4]"}`}>
                <div className="flex items-center gap-1.5 font-semibold text-[12px]">
                  <Icon size={13} className={active ? "text-[#0058CC]" : "text-[#6B6B73]"} /> {o.label}
                </div>
                <div className="text-[10px] text-[#6B6B73] mt-1 leading-snug">{o.desc}</div>
              </button>
            );
          })}
        </div>

        {outcome === "exchange" && (
          <div className="notice-bar mb-3 text-[11.5px]" data-testid="settle-swap-hint">
            {/* notice-bar = flex: isi dibungkus satu blok supaya teks tebal tidak pecah jadi kolom */}
            <div>
              <b>Tukar barang</b>: nilai retur menjadi saldo pelanggan, lalu Admin Sales membuat <b>pesanan pengganti</b>
              {" "}(artikel/warna sama, harga transaksi asal) di panel "Pesanan pengganti". Pengganti <b>lebih banyak</b> → selisihnya
              ditagih; <b>lebih sedikit</b> → sisa saldo tetap milik pelanggan.
              {!isSwap && <span className="mt-1 block text-[#8C4A00]" data-testid="settle-swap-type-change">
                Tipe retur ini berubah dari <b>{TYPE_LABEL[ret.return_type] || ret.return_type}</b> menjadi <b>Penggantian</b> (tercatat di riwayat).</span>}
            </div>
          </div>
        )}
        {isSwap && (outcome === "refund" || outcome === "nego") && (
          <div className="notice-bar mb-3 text-[11.5px] text-[#A8221A]" data-testid="settle-swap-warning">
            <div>Retur ini diajukan sebagai <b>Penggantian</b> (tukar barang). Outcome ini tidak membuat pesanan pengganti.</div>
          </div>
        )}

        {/* R3 — Lokasi gudang penerimaan (owner tetap = entitas SO) */}
        {movesStock && physLocs.length > 0 && (
          <div className="rounded-md border border-[#E4ECF7] bg-[#F6FAFF] p-2.5 mb-3 text-[11.5px]" data-testid="settle-physical-location">
            <Warehouse size={13} className="inline mr-1" /> Roll masuk karantina di <b>lokasi fisik hasil scan</b>: {physNames.join(", ") || "—"}.
            Untuk memindah barang, scan Kirim → Tiba di panel Perjalanan Retur.
          </div>
        )}
        {movesStock && !physLocs.length && (
          <div className="rounded-md border border-[#E4ECF7] bg-[#F6FAFF] p-2.5 mb-3" data-testid="settle-destination">
            <label className="flex items-center gap-1.5 text-[12px] font-semibold text-[#1B4F9C] mb-1.5">
              <Warehouse size={13} /> Lokasi Gudang Penerimaan Retur
            </label>
            <KNSelect className="field w-full" data-testid="settle-return-warehouse"
              value={returnWarehouseId} onValueChange={setReturnWarehouseId}
              aria-label="Gudang tujuan roll retur"
              placeholder="Default cerdas (gudang pengiriman SO)"
              options={[
                { value: "", label: "Default cerdas (gudang pengiriman SO)" },
                ...warehouses.map((w) => ({
                  value: w.id,
                  label: `${w.name || w.code || w.id}${w.city ? ` — ${w.city}` : ""}`,
                })),
              ]} />
            <div className="flex items-start gap-1 text-[10.5px] text-[#5B6472] mt-1.5 leading-snug">
              <Info size={12} className="mt-[1px] shrink-0" />
              <span>Roll retur masuk <b>karantina</b> di lokasi ini. Kepemilikan tetap pada <b>{ownerName}</b>;
                pindah kepemilikan lintas-PT dilakukan setelah release via aksi <b>Transfer Kepemilikan</b>.</span>
            </div>
          </div>
        )}

        {/* R5.3 — Akun Kas/Bank untuk refund TUNAI (hanya relevan bila order dibayar tunai) */}
        {outcome === "refund" && (
          <div className="rounded-md border border-[#E7E1F5] bg-[#F8F5FE] p-2.5 mb-3" data-testid="settle-refund-account-box">
            <label className="flex items-center gap-1.5 text-[12px] font-semibold text-[#6B219A] mb-1.5">
              <Coins size={13} /> Akun Kas/Bank Pengembalian Dana Tunai
            </label>
            <KNSelect className="field w-full" data-testid="settle-refund-account"
              value={refundAccount} onValueChange={setRefundAccount}
              aria-label="Akun kas/bank untuk pengembalian dana tunai"
              placeholder="Default — 1-1100 Kas Besar / Bank"
              options={[
                { value: "", label: "Default — 1-1100 Kas Besar / Bank" },
                ...cashAccounts.map((a) => ({ value: a.code, label: `${a.code} — ${a.name}` })),
              ]} />
            <div className="flex items-start gap-1 text-[10.5px] text-[#5B6472] mt-1.5 leading-snug">
              <Info size={12} className="mt-[1px] shrink-0" />
              <span>Berlaku bila retur berasal dari penjualan <b>tunai</b> → dana keluar dari akun ini &
                tercatat sebagai <b>kas keluar</b>. Penjualan kredit otomatis mengurangi piutang (tanpa kas).</span>
            </div>
          </div>
        )}

        {/* Per-item decisions */}
        <div className="section-card" style={{ margin: 0 }}>
          <table className="data-table">
            <thead>
              <tr><th>Sertakan</th><th>Produk</th><th>Qty Retur</th><th>Qty Diselesaikan</th></tr>
            </thead>
            <tbody>
              {(ret.items || []).map((it, i) => (
                <tr key={i} data-testid={`settle-item-${i}`}>
                  <td>
                    <input type="checkbox" data-testid={`settle-include-${i}`}
                      checked={decisions[i].include} onChange={(e) => upd(i, { include: e.target.checked })} />
                  </td>
                  <td>{it.product_name || it.product_id}</td>
                  <td className="font-mono">{fmtNum(it.quantity_returned)} {it.unit}</td>
                  <td style={{ maxWidth: 110 }}>
                    <input data-testid={`settle-qty-${i}`} type="number" min="0" max={it.quantity_returned}
                      className="field tabular-nums" disabled={!decisions[i].include}
                      value={decisions[i].settle_qty} onChange={(e) => upd(i, { settle_qty: e.target.value })} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <SettleValuePanel pv={pv} err={pvErr} busy={pvBusy} />

        {outcome === "nego" && (
          <div className="mt-3 flex flex-wrap items-center gap-4 text-xs" data-testid="settle-nego-payout">
            <span className="font-semibold">Kompensasi untuk customer (KLR-10):</span>
            {[["store_credit", "Jadi saldo"], ["refund", "Refund tunai"], ["", "Kurangi piutang SO asal saja"]].map(([v, l]) => (
              <label key={v || "ar"} className="inline-flex items-center gap-1">
                <input type="radio" name="nego-payout" data-testid={`settle-payout-${v || "ar"}`} checked={payout === v} onChange={() => setPayout(v)} /> {l}
              </label>))}
            <span className="text-[#6B6B73]">Tagihan SO asal yang belum lunas dipotong dulu; utang SO lain tidak ikut dipotong.</span>
          </div>
        )}
        <input data-testid="settle-decision-note" className="field mt-3 w-full"
          placeholder="Bukti keputusan (mis. ACC Pak Budi via WA 12/10, nego disepakati Rp …)"
          value={decisionNote} onChange={(e) => setDecisionNote(e.target.value)} />
        <textarea data-testid="settle-notes" className="textarea mt-3" rows={2}
          placeholder="Catatan penyelesaian (opsional)..." value={notes} onChange={(e) => setNotes(e.target.value)} />

        <p className="mt-2 text-[10.5px] text-[#5B6472]" data-testid="settle-cost-basis-note">
          Basis nilai barang kembali (pembalikan HPP ke stok) = <b>WAC</b> produk yang sudah
          <b> termasuk landed cost</b> (freight/duty/handling) untuk barang impor — bukan harga PO mentah.
        </p>

        {err && <p role="alert" className="mt-2 rounded-md bg-[#FDECEC] px-2.5 py-1.5 text-[12px] text-[#A8221A]" data-testid="settle-error">{err}</p>}
        <div className="modal-actions">
          <button className="secondary-button" onClick={onClose}>Batal</button>
          <button data-testid="confirm-settle-btn" className="primary-button" disabled={busy || !anyIncluded}
            onClick={confirm}>
            {busy ? <Loader2 size={13} className="spin" /> : <CheckCircle2 size={13} />} Selesaikan ({OUTCOMES.find((o) => o.value === outcome)?.label || outcome})
          </button>
        </div>
      </div>
    </div>
  );
}
