/**
 * MkoIssueRollPicker — pop-up Issue makloon, mode "Pilih roll".
 *
 * Kasus klien: 20 roll Esmica Blue dikirim ke mitra untuk dicelup hitam. Mode lama ("Berdasarkan jumlah") membiarkan
 * sistem memilih roll sendiri (FEFO + belah roll) — roll yang dimuat ke truk bisa berbeda dengan yang dicatat keluar,
 * sehingga gate OUT merah dan stok "hilang". Di sini petugas mencentang roll, atau memindai/menempel nomor roll /
 * EPC tag RFID (satu atau banyak sekaligus); qty issue = Σ panjang roll terpilih (dihitung ulang server).
 *
 * Daftar & alasan "tertahan" datang dari server (`GET /makloon-orders/{id}/steps/{seq}/issue-rolls`) — aturan yang
 * SAMA dengan validasi issue, jadi layar tidak menawarkan roll yang lalu ditolak. Galat muat tampil di DALAM pop-up
 * (ErrorNotice + Coba lagi). `onChange` = setter state induk (mendukung pembaruan fungsional).
 */
import { useCallback, useEffect, useState } from "react";
import { ScanLine } from "lucide-react";
import ErrorNotice from "../../../components/ErrorNotice";
import QtyDual from "../../../components/QtyDual";
import { formatQty } from "../../../utils/formatters";
import { fetchIssueRolls } from "./makloonApi";

/** Bentuk kanonik EPC (sama dengan `services/epc.py`): tanpa pemisah, huruf besar. */
export const canonCode = (s) => String(s || "").trim().replace(/[\s\-:_.]/g, "").toUpperCase();

/** Teks pindai/tempel (boleh banyak kode, dipisah spasi/baris/koma) → {hit: id roll, miss: kode tak cocok}. */
export function matchCodes(text, rolls) {
  const codes = String(text || "").split(/[\s,;]+/).map((c) => c.trim()).filter(Boolean);
  const hit = [];
  const miss = [];
  codes.forEach((c) => {
    const up = c.toUpperCase();
    const cc = canonCode(c);
    const r = (rolls || []).find((x) => String(x.roll_no || "").toUpperCase() === up || x.id === c
      || (x.epc && canonCode(x.epc) === cc));
    if (r) hit.push(r.id); else miss.push(c);
  });
  return { hit: Array.from(new Set(hit)), miss };
}

export default function MkoIssueRollPicker({ mkoId, step, warehouseId, picked, onChange }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [scan, setScan] = useState("");
  const [scanMsg, setScanMsg] = useState("");

  const load = useCallback(async () => {
    if (!mkoId || !warehouseId) return;
    setLoading(true); setErr("");
    try {
      const d = await fetchIssueRolls(mkoId, step.seq, warehouseId);
      setData(d);
      // Ganti gudang → centang roll gudang lama dibuang (roll itu bukan stok gudang sumber yang baru).
      const ok = new Set((d.rolls || []).map((r) => r.id));
      onChange((cur) => cur.filter((id) => ok.has(id)));
    } catch (e) {
      setData(null);
      setErr(e?.response?.data?.detail || e?.message || "Gagal memuat roll bahan di gudang ini.");
    } finally { setLoading(false); }
  }, [mkoId, step.seq, warehouseId, onChange]);   // onChange = setter state induk (stabil)
  useEffect(() => { load(); }, [load]);

  const rolls = data?.rolls || [];
  const blocked = data?.blocked || [];
  const unit = data?.unit || step.input_unit || "";
  const chosen = new Set(picked);
  const total = rolls.filter((r) => chosen.has(r.id)).reduce((a, r) => a + Number(r.length_remaining || 0), 0);
  const plan = Number(step.input_qty || 0);
  const deviates = picked.length > 0 && plan > 0 && Math.abs(total - plan) > 0.01;
  const toggle = (id) => onChange((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));

  const applyScan = () => {
    const { hit, miss } = matchCodes(scan, rolls);
    if (hit.length) onChange((cur) => Array.from(new Set([...cur, ...hit])));
    const why = miss.map((c) => {
      const b = blocked.find((x) => x.id === matchCodes(c, blocked).hit[0]);
      return b ? `${c}: ${b.reason}` : `${c}: tidak ada di gudang sumber untuk bahan ini`;
    });
    setScanMsg([hit.length ? `${hit.length} roll dicentang.` : "", ...why].filter(Boolean).join(" · "));
    setScan("");
  };

  return (
    <div className="rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-2.5" data-testid="mko-issue-roll-picker">
      <label className="block">
        <span className="mb-1 block text-[10.5px] font-semibold text-[#6B6B73]">Pindai/tempel nomor roll atau EPC</span>
        <div className="flex gap-1.5">
          <input data-testid="mko-issue-scan" className="field flex-1" value={scan} placeholder="mis. RL-00061 atau E200-…"
            onChange={(e) => setScan(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); applyScan(); } }} />
          <button type="button" data-testid="mko-issue-scan-apply" className="secondary-button !px-2.5"
            disabled={!scan.trim() || loading} onClick={applyScan}><ScanLine size={13} /> Centang</button>
        </div>
      </label>
      {scanMsg && <p data-testid="mko-issue-scan-msg" className="mt-1 text-[10.5px] text-[#3C3C43]">{scanMsg}</p>}
      {err && <div className="mt-2"><ErrorNotice message={err} onRetry={load} testId="mko-issue-rolls-error" /></div>}
      <div className="mt-2 flex items-center justify-between text-[10.5px] text-[#6B6B73]">
        <span>{loading ? "Memuat roll…" : `${rolls.length} roll tersedia${blocked.length ? ` · ${blocked.length} tertahan` : ""}`}</span>
        <span className="flex gap-2">
          <button type="button" className="font-semibold text-[#0058CC]" data-testid="mko-issue-pick-all"
            disabled={!rolls.length} onClick={() => onChange(rolls.map((r) => r.id))}>Pilih semua</button>
          <button type="button" className="font-semibold text-[#6B6B73]" data-testid="mko-issue-pick-none"
            disabled={!picked.length} onClick={() => onChange([])}>Kosongkan</button>
        </span>
      </div>
      <div className="mt-1 max-h-56 overflow-auto rounded border border-[#EFF0F2] bg-white p-1.5" data-testid="mko-issue-rolls">
        {rolls.map((r) => (
          <label key={r.id} className="flex items-center gap-2 py-0.5 text-[11.5px]">
            <input type="checkbox" checked={chosen.has(r.id)} data-testid={`mko-issue-roll-${r.id}`}
              onChange={() => toggle(r.id)} />
            <span className="flex-1 min-w-0 truncate">
              <b>{r.roll_no || r.id}</b>{r.lot ? ` · LOT ${r.lot}` : ""}{r.grade ? ` · ${r.grade}` : ""}
              {r.epc && <span className="text-[9.5px] text-[#9A9BA3]"> · EPC {r.epc}</span>}
            </span>
            <span className="tabular-nums">{formatQty(r.length_remaining)} {r.unit || unit}</span>
          </label>
        ))}
        {!loading && !rolls.length && !err && (
          <p className="py-1 text-[11px] text-[#6B6B73]">Tidak ada roll bahan ini yang bebas di gudang sumber.</p>
        )}
      </div>
      <p data-testid="mko-issue-pick-total"
        className={`mt-1.5 text-[11px] ${deviates ? "text-[#B26A00]" : "text-[#1B7F4B]"}`}>
        Terpilih <QtyDual rolls={picked.length} measure={total} unit={unit} className="font-semibold" />
        {plan > 0 && <> (rencana {formatQty(plan)} {unit})</>}
        {deviates && <> — berbeda dari rencana; estimasi hasil langkah ini disesuaikan otomatis.</>}
      </p>
    </div>
  );
}
