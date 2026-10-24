/** Klaim retur PER ROLL (permintaan pemilik 23 Okt): tiap roll punya qty, kondisi, alasan, checklist
 *  (hangtag hilang / sudah dipotong) dan foto bukti sendiri — satu SKU bisa berisi roll yang sudah
 *  dipotong dan yang masih utuh, sehingga pemutus bisa menolak roll tertentu saja.
 *  Dipakai form retur pelanggan desktop & HP (CreateReturnForm), retur ke supplier (PurchaseReturns) dan
 *  retur antar-PT (IntercoReturnModal) — satu bentuk isian untuk ketiga jenis retur. */
import { useEffect, useState } from "react";
import { Camera, Paperclip, X } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import { formatQty } from "../../utils/formatters";
import { lengthAlt } from "../../utils/uom";   // 23 Okt — padanan yard↔meter (pesanan sering bermeter)

export const CONDITION_OPTIONS = [{ value: "ok", label: "Baik" }, { value: "damaged", label: "Rusak" }];

export const emptyClaim = (roll) => ({ qty: String(roll.remaining), condition: "ok", reason: "", hangtag_missing: false,
  cut_by_customer: false, files: [] });

/** UAT 24 Okt (P17) — pratinjau kecil berkas lokal sebelum diunggah (foto: gambar; lainnya ikon). */
function LocalThumb({ file }) {
  const [src, setSrc] = useState("");
  useEffect(() => {
    if (!file || !String(file.type || "").startsWith("image/") || typeof URL.createObjectURL !== "function") return undefined;
    const u = URL.createObjectURL(file);
    setSrc(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);
  return src ? <img src={src} alt={file.name || "foto"} className="h-5 w-5 rounded object-cover" /> : <Paperclip size={10} />;
}

/** Pemilih foto: kamera HP langsung (capture) + pilih berkas; foto ditambahkan ke daftar, bukan menimpa. */
export function PhotoPicker({ files = [], onChange, testId, compact = false }) {
  const add = (list) => onChange([...files, ...list]);
  return (
    <div className="flex flex-wrap items-center gap-1.5" data-testid={testId}>
      <label className="inline-flex cursor-pointer items-center gap-1 rounded-md border border-[#0058CC] px-2 py-1 text-[11.5px] font-semibold text-[#0058CC]">
        <Camera size={12} /> {compact ? "Foto" : "Ambil foto"}
        <input type="file" accept="image/*" capture="environment" className="hidden" data-testid={`${testId}-camera`}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) add([f]); e.target.value = ""; }} />
      </label>
      <label className="inline-flex cursor-pointer items-center gap-1 rounded-md border border-[#E5E5EA] px-2 py-1 text-[11.5px] font-semibold text-[#3C3C43]">
        <Paperclip size={12} /> Pilih berkas
        <input type="file" accept="image/*,.pdf" multiple className="hidden" data-testid={`${testId}-input`}
          onChange={(e) => { add(Array.from(e.target.files || [])); e.target.value = ""; }} />
      </label>
      {files.map((f, i) => (
        <span key={`${f.name}-${i}`} className="inline-flex items-center gap-1 rounded-full border border-[#E1E4EA] bg-white px-2 py-0.5 text-[10.5px]">
          <LocalThumb file={f} />{f.name || `foto-${i + 1}.jpg`}
          <button type="button" aria-label="Hapus foto" data-testid={`${testId}-remove-${i}`} className="text-[#A8221A]"
            onClick={() => onChange(files.filter((_, j) => j !== i))}><X size={10} /></button>
        </span>
      ))}
    </div>
  );
}

/** Isian satu roll: (qty) · kondisi · alasan wajib · checklist · foto. `qtyEditable=false` = qty roll utuh
 *  (retur supplier & antar-PT mengirim balik roll yang dipilih). */
export function RollClaimFields({ claim: c, onChange, testId: rt, unit, remaining, qtyEditable = true, cutLabel = "Sudah dipotong pelanggan" }) {
  const over = qtyEditable && (parseFloat(c.qty) || 0) > remaining + 0.001;
  return (
    <div className="mt-2 space-y-2 pl-5">
      <div className={`grid gap-2 ${qtyEditable ? "sm:grid-cols-[120px_130px_minmax(0,1fr)]" : "sm:grid-cols-[130px_minmax(0,1fr)]"}`}>
        {qtyEditable && (
          <label className="text-[10.5px] font-semibold uppercase tracking-wide text-[#6B6B73]">Qty ({unit})
            <input type="number" min="0.01" step="0.01" max={remaining} value={c.qty} data-testid={`${rt}-qty`}
              onChange={(e) => onChange({ qty: e.target.value })}
              className={`form-input mt-1 text-right tabular-nums ${over ? "!border-[#A8221A]" : ""}`} />
          </label>
        )}
        <div className="text-[10.5px] font-semibold uppercase tracking-wide text-[#6B6B73]">Kondisi
          <KNSelect className="form-select mt-1" value={c.condition} searchable={false} data-testid={`${rt}-condition`}
            onValueChange={(v) => onChange({ condition: v })} options={CONDITION_OPTIONS} />
        </div>
        <label className="text-[10.5px] font-semibold uppercase tracking-wide text-[#6B6B73]">Alasan roll ini *
          <input value={c.reason} placeholder="mis. noda di 10 yard awal" data-testid={`${rt}-reason`}
            onChange={(e) => onChange({ reason: e.target.value })} className="form-input mt-1" />
        </label>
      </div>
      {over && <p className="text-[11px] font-semibold text-[#A8221A]">Melebihi sisa roll ({formatQty(remaining)} {unit}).</p>}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12px] text-[#3C3C43]">
        <label className="inline-flex items-center gap-1.5">
          <input type="checkbox" checked={c.hangtag_missing} data-testid={`${rt}-hangtag`}
            onChange={(e) => onChange({ hangtag_missing: e.target.checked })} /> Hangtag hilang
        </label>
        <label className="inline-flex items-center gap-1.5">
          <input type="checkbox" checked={c.cut_by_customer} data-testid={`${rt}-cut`}
            onChange={(e) => onChange({ cut_by_customer: e.target.checked })} /> {cutLabel}
        </label>
        <PhotoPicker compact files={c.files} onChange={(files) => onChange({ files })} testId={`${rt}-photo`} />
      </div>
    </div>
  );
}

/** Roll yang SUDAH dipilih (lewat pemilih roll lain) → isian per roll tanpa centang & tanpa qty (roll utuh). */
export function PickedRollClaims({ rolls, claims, onChange, testId, cutLabel = "Roll sudah dipotong" }) {
  if (!rolls.length) return null;
  return (
    <div className="divide-y divide-[#F2F3F5] rounded-md border border-[#EFF0F2] bg-[#FAFBFC]" data-testid={testId}>
      {rolls.map((r) => {
        const rt = `${testId}-roll-${r.roll_id}`;
        const c = claims[r.roll_id] || emptyClaim(r);
        return (
          <div key={r.roll_id} className="px-3 py-2" data-testid={rt}>
            <p className="flex flex-wrap items-center gap-x-2 text-[12px]">
              <span className="font-mono font-semibold text-[#1C1C1E]">{r.roll_no || r.roll_id}</span>
              <span className="text-[11px] text-[#6B6B73]">{[r.lot, `${formatQty(r.remaining)} ${r.unit || ""}`].filter(Boolean).join(" · ")}</span>
            </p>
            <RollClaimFields claim={c} testId={rt} unit={r.unit} remaining={r.remaining} qtyEditable={false} cutLabel={cutLabel}
              onChange={(patch) => onChange({ ...claims, [r.roll_id]: { ...c, ...patch } })} />
          </div>
        );
      })}
    </div>
  );
}

/** Detail per roll untuk API (tanpa qty & berkas). */
export const claimDetails = (claims) => Object.fromEntries(Object.entries(claims || {}).map(([rid, c]) => {
  const { qty, files, ...d } = c;
  return [rid, d];
}));

/** Alasan per roll wajib (retur supplier & antar-PT) — pesan salah, kosong = valid. */
export const pickedClaimErrors = (rolls, claims) => rolls
  .filter((r) => ((claims[r.roll_id] || {}).reason || "").trim().length < 3)
  .map((r) => `${r.roll_no || r.roll_id}: isi alasan roll ini`);

/** Satu produk: daftar roll terkirim; roll dicentang → isian per roll muncul di bawahnya. */
export default function ReturnRollClaims({ product, rolls, claims, onChange, testId }) {
  const set = (rid, patch) => onChange({ ...claims, [rid]: { ...claims[rid], ...patch } });
  const toggle = (r) => {
    if (claims[r.roll_id]) {
      const next = { ...claims };
      delete next[r.roll_id];
      onChange(next);
    } else onChange({ ...claims, [r.roll_id]: emptyClaim(r) });
  };
  const total = Object.entries(claims).reduce((s, [, c]) => s + (parseFloat(c.qty) || 0), 0);
  return (
    <div className="rounded-lg border border-[#E5E5EA] bg-white" data-testid={testId}>
      <div className="flex flex-wrap items-start justify-between gap-2 border-b border-[#EFF0F2] px-3 py-2">
        <div className="min-w-0">
          <p className="truncate text-[12.5px] font-semibold text-[#1C1C1E]">{product.product_name || product.sku}</p>
          <p className="text-[11px] text-[#6B6B73]">{product.sku}{product.color ? ` · ${product.color}` : ""}</p>
        </div>
        <p className="text-right text-[11.5px] text-[#6B6B73]" data-testid={`${testId}-total`}>
          Diklaim <b className="tabular-nums text-[#1C1C1E]">{formatQty(total)} {product.unit}</b>
          {lengthAlt(total, product.unit) && <span className="tabular-nums"> {lengthAlt(total, product.unit)}</span>}
          <span className="block text-[10.5px]">sisa bisa diretur {formatQty(product.max)} {product.unit} {lengthAlt(product.max, product.unit)}</span>
        </p>
      </div>
      <div className="divide-y divide-[#F2F3F5]">
        {rolls.map((r) => {
          const c = claims[r.roll_id];
          const rt = `${testId}-roll-${r.roll_id}`;
          return (
            <div key={r.roll_id} className={`px-3 py-2 ${c ? "bg-[#F7FAFF]" : ""}`} data-testid={rt}>
              <label className="flex cursor-pointer flex-wrap items-center gap-x-2 gap-y-0.5 text-[12px]">
                <input type="checkbox" checked={!!c} onChange={() => toggle(r)} data-testid={`${rt}-check`} />
                <span className="font-mono font-semibold text-[#1C1C1E]">{r.roll_no || r.roll_id}</span>
                <span className="text-[11px] text-[#6B6B73]">{r.shipment_no} · sisa {formatQty(r.remaining)} {r.unit} {lengthAlt(r.remaining, r.unit)}</span>
              </label>
              {c && <RollClaimFields claim={c} testId={rt} unit={r.unit} remaining={r.remaining}
                onChange={(patch) => set(r.roll_id, patch)} />}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Ubah klaim per roll (state form) → baris retur API: qty = jumlah klaim roll, detail per roll ikut. */
export function claimsToItem(product, claims) {
  const ids = Object.keys(claims);
  const roll_qtys = Object.fromEntries(ids.map((rid) => [rid, Math.round((parseFloat(claims[rid].qty) || 0) * 100) / 100]));
  const roll_details = claimDetails(claims);
  return {
    product_id: product.product_id, product_name: product.product_name, unit: product.unit,
    quantity_returned: Math.round(Object.values(roll_qtys).reduce((a, q) => a + q, 0) * 100) / 100,
    roll_ids: ids, roll_qtys, roll_details, reason: "",
    condition: ids.some((rid) => claims[rid].condition === "damaged") ? "damaged" : "ok",
  };
}

/** Pesan salah per roll sebelum dikirim (qty, sisa, alasan). Kosong = valid. */
export function claimErrors(product, rolls, claims) {
  const byId = Object.fromEntries(rolls.map((r) => [r.roll_id, r]));
  const errs = [];
  Object.entries(claims).forEach(([rid, c]) => {
    const r = byId[rid] || {};
    const q = parseFloat(c.qty) || 0;
    const no = r.roll_no || rid;
    if (q <= 0) errs.push(`${no}: qty harus lebih dari 0`);
    else if (q > (r.remaining || 0) + 0.001) errs.push(`${no}: qty melebihi sisa ${formatQty(r.remaining)} ${r.unit}`);
    if ((c.reason || "").trim().length < 3) errs.push(`${no}: isi alasan roll ini`);
  });
  return errs;
}
