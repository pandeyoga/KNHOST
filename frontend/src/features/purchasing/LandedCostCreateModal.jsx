import { useEffect, useMemo, useState } from "react";
import KNDatePicker from "@/components/KNDatePicker";
import MoneyInput from "@/components/MoneyInput";
import axios, { API } from "../../services/apiClient";
import { Ship, Plus, Trash2, Layers, Loader2 } from "lucide-react";
import FormModal from "@/components/FormModal";
import { formatCurrency, formatQty } from "../../utils/formatters";
import KNSelect from "../../components/KNSelect";

/**
 * LandedCostCreateModal (Fase 5.4) — buat voucher landed cost dari 1+ PO.
 * Preview alokasi dihitung client-side (panduan); kebenaran final = server saat approve.
 *
 * Audit UI 24 Okt (033): kaki modal distandarkan lewat FormModal (Batal · Simpan Draf ·
 * Kirim di kanan), galat tampil di dalam modal, istilah Inggris diganti.
 */
const BASIS_OPTIONS = [
  { value: "value", label: "Proporsional Nilai (biaya × panjang)" },
  { value: "quantity", label: "Proporsional Kuantitas (panjang)" },
];
const CATEGORY_OPTIONS = [
  { value: "freight", label: "Ongkos Angkut" },
  { value: "duty", label: "Bea Masuk" },
  { value: "insurance", label: "Asuransi" },
  { value: "handling", label: "Bongkar Muat" },
  { value: "other", label: "Lainnya" },
];

const round2 = (x) => Math.round((Number(x) || 0) * 100) / 100;

function previewAllocation(rolls, totalCost, basis) {
  const list = (rolls || []).filter((r) => Number(r.length || 0) > 0);
  const n = list.length;
  let eff = basis === "quantity" ? "quantity" : "value";
  const wf = (r, b) => (b === "value" ? Number(r.base_unit_cost || 0) * Number(r.length || 0) : Number(r.length || 0));
  let weights = list.map((r) => wf(r, eff));
  let tw = weights.reduce((s, w) => s + w, 0);
  if (eff === "value" && tw <= 0) { eff = "quantity"; weights = list.map((r) => wf(r, "quantity")); tw = weights.reduce((s, w) => s + w, 0); }
  if (tw <= 0) { weights = list.map(() => 1); tw = n || 1; }
  let running = 0;
  const allocations = list.map((r, i) => {
    const ln = Number(r.length || 0);
    let alloc;
    if (i === n - 1) alloc = round2(totalCost - running);
    else { alloc = round2(totalCost * (weights[i] / tw)); running = round2(running + alloc); }
    const perUnit = ln > 0 ? alloc / ln : 0;
    const cur = Number(r.current_unit_cost || 0);
    return { ...r, alloc_amount: alloc, per_unit: perUnit, new_unit_cost: cur + perUnit };
  });
  return { basis: eff, allocations };
}

export default function LandedCostCreateModal({ open, pos, selectedEntity, onClose, onCreated, onError }) {
  const [selectedPoIds, setSelectedPoIds] = useState([]);
  const [poQ, setPoQ] = useState("");   // G4-26 — cari PO (dulu daftar centang 140 px tanpa cari)
  const [rolls, setRolls] = useState([]);
  const [loadingCtx, setLoadingCtx] = useState(false);
  const [provider, setProvider] = useState("");
  const [invNo, setInvNo] = useState("");
  const [basis, setBasis] = useState("value");
  const [voucherDate, setVoucherDate] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState([{ category: "freight", description: "", amount: "" }]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  // G4-26 — PO yang sudah dicentang selalu tampil walau tidak cocok dengan kata cari.
  const shownPos = useMemo(() => {
    const t = poQ.trim().toLowerCase();
    const list = pos || [];
    return t ? list.filter((p) => selectedPoIds.includes(p.id)
      || `${p.po_number} ${p.supplier_name || ""}`.toLowerCase().includes(t)) : list;
  }, [pos, poQ, selectedPoIds]);
  const fail = (m) => { setErr(m); onError?.(m); };

  useEffect(() => { if (!open) reset(); }, [open]);

  function reset() {
    setSelectedPoIds([]); setPoQ(""); setRolls([]); setProvider(""); setInvNo("");
    setBasis("value"); setVoucherDate(""); setDueDate(""); setNotes("");
    setLines([{ category: "freight", description: "", amount: "" }]);
    setErr("");
  }

  async function togglePo(id) {
    const next = selectedPoIds.includes(id) ? selectedPoIds.filter((x) => x !== id) : [...selectedPoIds, id];
    setSelectedPoIds(next);
    await loadRolls(next);
  }

  async function loadRolls(poIds) {
    if (!poIds.length) { setRolls([]); return; }
    setLoadingCtx(true);
    try {
      const results = await Promise.all(
        poIds.map((id) => axios.get(`${API}/purchase-orders/${id}/landed-cost-context`).then((r) => r.data).catch(() => null)));
      const merged = [];
      for (const ctx of results) {
        if (ctx && Array.isArray(ctx.rolls)) {
          for (const r of ctx.rolls) merged.push({ ...r, po_number: ctx.po_number });
        }
      }
      setRolls(merged);
    } catch (e) {
      fail(e.response?.data?.detail || "Gagal memuat roll PO.");
    } finally { setLoadingCtx(false); }
  }

  const totalCost = useMemo(() => round2(lines.reduce((s, l) => s + (Number(l.amount) || 0), 0)), [lines]);
  const preview = useMemo(() => previewAllocation(rolls, totalCost, basis), [rolls, totalCost, basis]);
  const totalBaseValue = useMemo(() => round2(rolls.reduce((s, r) => s + Number(r.base_value || 0), 0)), [rolls]);

  function updateLine(i, patch) { setLines((arr) => arr.map((l, idx) => (idx === i ? { ...l, ...patch } : l))); }
  function addLine() { setLines((arr) => [...arr, { category: "other", description: "", amount: "" }]); }
  function removeLine(i) { setLines((arr) => (arr.length > 1 ? arr.filter((_, idx) => idx !== i) : arr)); }

  async function submit(now) {
    if (!selectedPoIds.length) { fail("Pilih minimal 1 PO."); return; }
    const costLines = lines.filter((l) => Number(l.amount) > 0)
      .map((l) => ({ category: l.category, description: l.description, amount: Number(l.amount) }));
    if (!costLines.length) { fail("Minimal 1 baris biaya dengan nominal > 0."); return; }
    if (!rolls.length) { fail("PO terpilih belum punya roll diterima (GR). Selesaikan penerimaan dulu."); return; }
    setErr("");
    setBusy(true);
    try {
      const body = {
        po_ids: selectedPoIds, provider_name: provider, supplier_invoice_no: invNo,
        basis, cost_lines: costLines, voucher_date: voucherDate || undefined,
        due_date: dueDate || undefined, notes, submit_now: now,
        entity_id: (selectedEntity && selectedEntity !== "all") ? selectedEntity : undefined,
      };
      const r = await axios.post(`${API}/landed-costs`, body);
      onCreated?.(r.data);
      reset();
    } catch (e) {
      fail(e.response?.data?.detail || "Gagal membuat dokumen biaya masuk.");
    } finally { setBusy(false); }
  }

  if (!open) return null;

  const footer = (
    <div className="flex flex-wrap items-center justify-end gap-2">
      <button type="button" data-testid="lc-create-close" onClick={onClose} disabled={busy} className="secondary-button">Batal</button>
      <button type="button" data-testid="lc-save-draft" onClick={() => submit(false)} disabled={busy} className="secondary-button">Simpan Draf</button>
      <button type="button" data-testid="lc-submit-now" onClick={() => submit(true)} disabled={busy} className="primary-button">
        {busy && <Loader2 size={13} className="animate-spin" />} Kirim ke Manajer
      </button>
    </div>
  );

  return (
    <FormModal open={open} onClose={onClose} size="lg" icon={Ship} busy={busy}
      testId="landed-cost-create-modal"
      title="Buat Biaya Masuk"
      subtitle="Ongkos angkut, bea, asuransi & bongkar muat dibebankan ke HPP roll setelah disetujui manajer."
      error={err} footer={footer}>
        <div className="space-y-3">
          {/* PO selection */}
          <Field label={`Pesanan Pembelian (bisa lebih dari satu)${selectedPoIds.length ? ` · ${selectedPoIds.length} dipilih` : ""}`} req>
            {pos.length > 6 && (
              <input data-testid="lc-po-search" className="field mb-1.5" value={poQ} onChange={(e) => setPoQ(e.target.value)}
                placeholder="Cari nomor PO / supplier…" aria-label="Cari PO" />
            )}
            <div className="rounded-md border border-[#EFF0F2] max-h-[220px] overflow-y-auto p-1" data-testid="lc-po-list">
              {pos.length === 0 && <p className="text-[11px] text-[#9A9BA3] px-2 py-2">Tidak ada PO diterima yang bisa dibebani.</p>}
              {pos.length > 0 && shownPos.length === 0 && <p className="text-[11px] text-[#9A9BA3] px-2 py-2">Tidak ada PO yang cocok dengan “{poQ.trim()}”.</p>}
              {shownPos.map((p) => (
                <label key={p.id} data-testid={`lc-po-option-${p.id}`}
                       className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-[#FAFBFC] cursor-pointer text-[11.5px]">
                  <input type="checkbox" checked={selectedPoIds.includes(p.id)} onChange={() => togglePo(p.id)} />
                  <span className="font-semibold text-[#0058CC]">{p.po_number}</span>
                  <span className="text-[#6B6B73] truncate">· {p.supplier_name}</span>
                </label>
              ))}
            </div>
          </Field>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Field label="Penyedia Jasa">
              <input data-testid="lc-provider-input" value={provider} onChange={(e) => setProvider(e.target.value)}
                className="field" placeholder="mis. Forwarder / Bea Cukai" />
            </Field>
            <Field label="No. Faktur Penyedia">
              <input data-testid="lc-invoice-input" value={invNo} onChange={(e) => setInvNo(e.target.value)}
                className="field" placeholder="opsional — mencegah faktur tercatat dua kali" />
            </Field>
            <Field label="Basis Alokasi">
              <KNSelect data-testid="lc-basis-select" value={basis} onValueChange={setBasis} className="field" options={BASIS_OPTIONS} />
            </Field>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Field label="Tanggal Dokumen">
              <KNDatePicker data-testid="lc-voucher-date" value={voucherDate} onChange={setVoucherDate} />
            </Field>
            <Field label="Jatuh Tempo">
              <KNDatePicker data-testid="lc-due-date" value={dueDate} onChange={setDueDate} />
            </Field>
            <Field label="Catatan">
              <input value={notes} onChange={(e) => setNotes(e.target.value)} className="field" placeholder="opsional" />
            </Field>
          </div>

          {/* Cost lines */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="field-label !mb-0">Baris Biaya Tambahan <span className="req">*</span></label>
              <button type="button" data-testid="lc-add-line" onClick={addLine} className="secondary-button !px-2 !py-1 text-[11px]"><Plus size={11} /> Tambah</button>
            </div>
            <div className="rounded-md border border-[#EFF0F2] overflow-x-auto">
             <div className="min-w-[520px]">
              <div className="grid grid-cols-[150px_1fr_140px_36px] whitespace-nowrap px-2.5 py-1.5 bg-[#FAFBFC] text-[11px] font-bold uppercase text-[#6B6B73] border-b border-[#EFF0F2]">
                <span>Kategori</span><span>Deskripsi</span><span className="text-right">Nominal (Rp)</span><span></span>
              </div>
              {lines.map((l, i) => (
                <div key={i} data-testid={`lc-line-${i}`} className="grid grid-cols-[150px_1fr_140px_36px] gap-1 items-center px-2.5 py-1.5 border-b border-[#EFF0F2] last:border-0">
                  <KNSelect data-testid={`lc-line-category-${i}`} value={l.category} onValueChange={(v) => updateLine(i, { category: v })} className="field" options={CATEGORY_OPTIONS} />
                  <input data-testid={`lc-line-desc-${i}`} value={l.description} onChange={(e) => updateLine(i, { description: e.target.value })} className="field" placeholder="keterangan" />
                  <MoneyInput testId={`lc-line-amount-${i}`} value={l.amount} onChange={(v) => updateLine(i, { amount: v })} className="field text-right" placeholder="0" />
                  <button type="button" data-testid={`lc-line-remove-${i}`} onClick={() => removeLine(i)} className="icon-button !w-7 !h-7" title="Hapus"><Trash2 size={13} className="text-red-500" /></button>
                </div>
              ))}
              <div className="grid grid-cols-[150px_1fr_140px_36px] px-2.5 py-1.5 bg-[#FAFBFC] border-t border-[#EFF0F2]">
                <span className="text-[11px] font-bold uppercase text-[#6B6B73] col-span-2 text-right pr-2">Total Biaya</span>
                <span className="text-[12px] font-bold tabular-nums text-right" data-testid="lc-total-cost">{formatCurrency(totalCost)}</span>
                <span></span>
              </div>
             </div>
            </div>
          </div>

          {/* Allocation preview */}
          {loadingCtx && <div className="py-4 text-center text-[12px] text-[#6B6B73]">Memuat roll...</div>}
          {!loadingCtx && selectedPoIds.length > 0 && (
            <div className="rounded-md border border-[#EFF0F2] overflow-hidden" data-testid="lc-alloc-preview">
              <div className="flex items-center justify-between px-3 py-2 bg-[#FAFBFC] border-b border-[#EFF0F2]">
                <div className="flex items-center gap-1.5">
                  <Layers size={13} className="text-[#0058CC]" />
                  <span className="text-[11px] font-bold text-[#3C3C43]">Pratinjau Alokasi — {rolls.length} roll · basis {preview.basis === "quantity" ? "kuantitas" : "nilai"}</span>
                </div>
                <span className="text-[11px] text-[#6B6B73]">Nilai dasar: {formatCurrency(totalBaseValue)}</span>
              </div>
              {rolls.length === 0 ? (
                <div className="py-4 text-center text-[11.5px] text-amber-600">PO terpilih belum punya roll diterima (GR).</div>
              ) : (
                <div className="max-h-[200px] overflow-auto">
                 <div className="min-w-[600px]">
                  <div className="grid grid-cols-[90px_1.4fr_80px_100px_100px_110px] whitespace-nowrap px-2.5 py-1 bg-white text-[11px] font-bold uppercase text-[#9A9BA3] border-b border-[#EFF0F2] sticky top-0">
                    <span>Roll</span><span>Produk</span><span className="text-right">Panjang</span><span className="text-right">HPP Kini</span><span className="text-right">+ Biaya/unit</span><span className="text-right">HPP Baru</span>
                  </div>
                  {preview.allocations.map((a, i) => (
                    <div key={a.roll_id} data-testid={`lc-alloc-row-${i}`} className="grid grid-cols-[90px_1.4fr_80px_100px_100px_110px] items-center px-2.5 py-1 border-b border-[#F2F3F5] last:border-0 text-[11px]">
                      <span className="font-mono">{a.roll_no}</span>
                      <span className="truncate">{a.product_name}</span>
                      <span className="tabular-nums text-right">{formatQty(a.length)}</span>
                      <span className="tabular-nums text-right text-[#6B6B73]">{formatCurrency(a.current_unit_cost)}</span>
                      <span className="tabular-nums text-right text-[#0058CC]">+{formatCurrency(a.per_unit)}</span>
                      <span className="tabular-nums text-right font-semibold">{formatCurrency(a.new_unit_cost)}</span>
                    </div>
                  ))}
                 </div>
                </div>
              )}
            </div>
          )}
        </div>
    </FormModal>
  );
}

function Field({ label, req, children }) {
  return (
    <div>
      <label className="field-label">{label} {req && <span className="req">*</span>}</label>
      {children}
    </div>
  );
}
