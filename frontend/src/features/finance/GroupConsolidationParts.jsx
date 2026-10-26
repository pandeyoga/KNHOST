/**
 * GroupConsolidationParts — panel & pop-up Konsolidasi Grup (diekstrak dari GroupConsolidationView, batas 500 baris).
 *
 * Fase 3 · P4:
 *  · L-03 — pop-up Tambah Eliminasi & Deteksi Kandidat (`div fixed inset-0` buatan sendiri, tanpa Esc/klik-latar,
 *    galat tampil di halaman di belakang pop-up) → FormModal baku (layar penuh di HP, galat di dalam pop-up).
 *  · L-07 — tabel baris jurnal eliminasi → `.data-table` baku.
 *  · L-08 — bilah 4 tombol (Sinkron Antar-PT · Sinkron Pasangan Jurnal · Deteksi Otomatis · Tambah Eliminasi) →
 *    satu aksi utama "Tambah Eliminasi" + tombol "Alat eliminasi (3)" yang membuka panel lipat berisi tiga alat
 *    sinkron/deteksi beserta penjelasannya (dulu hanya di tooltip). Testid tombol lama dipertahankan.
 *    Aksen ungu #6B219A → biru standar.
 */
import { useState } from "react";
import KNDatePicker from "@/components/KNDatePicker";
import {
  Plus, Trash2, Wand2, ScissorsLineDashed, ArrowRightLeft, Link2, ChevronDown, Wrench,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";
import KNSelect from "../../components/KNSelect";
import FormModal from "../../components/FormModal";
import { formatCurrency, formatDate } from "../../utils/formatters";
import { stripInternalCodes } from "../../utils/cleanText";

// UAT 24 Okt (audit UI tahap 2) — G1-06: judul/catatan entri eliminasi lama masih memuat kode fase/invarian
// ("Auto G-6:", "(FASE G-6)", "(INV-IC-02/INV-IC-03)", "Auto-generated"); dibersihkan saat render.
const elimName = (n) => stripInternalCodes(n || "")
  .replace(/^Auto\s*:?\s*/i, "")
  .replace(/^Eliminasi antar-PT\b/i, "Eliminasi otomatis antar-PT")
  .replace(/^Eliminasi IC transfer\b/i, "Eliminasi otomatis transfer antar-PT");
const elimNote = (n) => stripInternalCodes(n || "")
  .replace(/Auto-generated dari intercompany transfer JE pair/i, "Dibuat otomatis dari pasangan jurnal transfer antar-PT")
  .replace(/Auto-generated dari/i, "Dibuat otomatis dari");

const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export function EliminationsPanel({ elims, onAdd, onDetect, onDelete, onSyncG6, onSyncPairs, busy }) {
  const autoG6 = elims.filter((e) => e.source_g6_pair_id).length;
  const [toolsOpen, setToolsOpen] = useState(false);
  return (
    <div data-testid="cons-elim-panel">
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <h4 className="text-[12px] font-bold text-[#1C1C1E]">Entri Eliminasi Intercompany</h4>
        {autoG6 > 0 && (
          <span data-testid="cons-elim-g6-count"
                className="text-[10px] font-bold rounded-full px-1.5 py-0.5 bg-[#EFF4FF] text-[#0058CC]">
            {autoG6} otomatis dari transaksi antar-PT
          </span>
        )}
        <div className="ml-auto flex items-center gap-2 flex-wrap">
          <button type="button" data-testid="cons-elim-tools-toggle" aria-expanded={toolsOpen}
                  className="secondary-button" onClick={() => setToolsOpen((v) => !v)}>
            <Wrench size={13} /> Alat eliminasi (3)
            <ChevronDown size={13} className={`transition-transform ${toolsOpen ? "rotate-180" : ""}`} />
          </button>
          <button data-testid="cons-elim-add" className="primary-button" onClick={onAdd}><Plus size={13} /> Tambah Eliminasi</button>
        </div>
      </div>
      {toolsOpen && (
        <div className="mb-3 grid gap-2 rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2.5 sm:grid-cols-3" data-testid="cons-elim-tools">
          <ToolButton testId="cons-sync-g6-btn" icon={ArrowRightLeft} label="Sinkron Antar-PT" onClick={onSyncG6} disabled={busy}
            hint="Sinkronkan eliminasi margin (unrealized profit) dari transaksi antar-PT." />
          <ToolButton testId="cons-sync-pairs-btn" icon={Link2} label="Sinkron Pasangan Jurnal" onClick={onSyncPairs} disabled={busy}
            hint="Sinkronkan eliminasi dari pasangan jurnal transfer antar-PT lama (nilai perolehan)." />
          <ToolButton testId="cons-detect-btn" icon={Wand2} label="Deteksi Otomatis" onClick={onDetect} disabled={busy}
            hint="Cari akun ber-saldo antar-PT dan jadikan draf eliminasi." />
        </div>
      )}
      {elims.length === 0 ? (
        <div data-testid="cons-elim-empty" className="py-10 text-center text-[12px] text-[#8E8E93]">
          <ScissorsLineDashed size={26} className="mx-auto mb-2 text-gray-300" />Belum ada entri eliminasi. Transaksi antar-PT akan mengisi ini sendiri; untuk data lama pakai "Sinkron Antar-PT", "Deteksi Otomatis", atau "Tambah Eliminasi".
        </div>
      ) : (
        <div className="space-y-2">
          {elims.map((el) => (
            <div key={el.id} data-testid={`cons-elim-${el.id}`} className="rounded-md border border-[#EFF0F2] p-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[12px] font-bold text-[#1C1C1E]">{elimName(el.name)}</span>
                <span className="text-[10px] text-[#9A9BA3]">Efektif {formatDate(el.effective_date)}</span>
                <span className={`text-[10px] font-bold rounded-full px-1.5 py-0.5 ${el.balanced ? "bg-[#E6F6EC] text-[#1B7F4B]" : "bg-[#FDEDE7] text-[#C0392B]"}`}>{el.balanced ? "Seimbang" : "Tidak seimbang"}</span>
                {el.source_g6_pair_id && (
                  <span data-testid={`cons-elim-auto-g6-${el.id}`}
                        title="Dijaga otomatis dari transaksi antar-PT — ikut berubah saat transaksinya dilunasi/dibatalkan"
                        className="text-[10px] font-bold rounded-full px-1.5 py-0.5 bg-[#EFF4FF] text-[#0058CC]">
                    Otomatis
                  </span>
                )}
                {/* FASE E-7 (E7.3) — keputusan pemilik: HPP taksiran BOLEH, tetapi tidak
                    boleh tampil sebagai angka telanjang. Entri yang HPP-nya belum
                    diposting ditandai di sini + alasannya ada di catatan. */}
                {el.g6_cost_estimated && (
                  <span data-testid={`cons-elim-cost-estimated-${el.id}`}
                        title={el.g6_cost_estimate_reason || "HPP penjual belum diposting"}
                        className="text-[10px] font-bold rounded-full px-1.5 py-0.5 bg-[#FFF4E5] text-[#8A5300]">
                    HPP TAKSIRAN
                  </span>
                )}
                <span className="text-[11px] text-[#6B6B73] ml-auto tabular-nums">{formatCurrency(el.total_debit || 0)}</span>
                {el.source_g6_pair_id ? (
                  <span className="text-[10px] text-[#9A9BA3]" title="Dikelola sistem: ikut transaksi antar-PT-nya (batalkan transaksinya bila ingin hilang)">
                    dikelola sistem
                  </span>
                ) : (
                  <button data-testid={`cons-elim-del-${el.id}`} className="text-[#C9C9CE] hover:text-[#C0392B]" onClick={() => onDelete(el)} disabled={busy} aria-label="Hapus"><Trash2 size={13} /></button>
                )}
              </div>
              {el.note && <p className="text-[11px] text-[#6B6B73] mt-0.5">{elimNote(el.note)}</p>}
              <div className="mt-2 table-wrap !shadow-none">
                <table className="data-table text-[11.5px]" data-testid={`cons-elim-lines-${el.id}`}>
                  <thead><tr><th>Akun</th><th className="text-right">Debit</th><th className="text-right">Kredit</th></tr></thead>
                  <tbody>
                    {(el.lines || []).map((l, i) => (
                      <tr key={i}>
                        <td><span className="font-mono text-[10px] text-[#9A9BA3] mr-1">{l.account_code}</span>{l.account_name}</td>
                        <td className="text-right tabular-nums">{l.debit > 0 ? formatCurrency(l.debit) : "—"}</td>
                        <td className="text-right tabular-nums">{l.credit > 0 ? formatCurrency(l.credit) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function EliminationModal({ initial, accounts, entities, onClose, onSaved }) {
  const [name, setName] = useState(initial.name || "Eliminasi Intercompany");
  const [effDate, setEffDate] = useState(() => ymd(new Date()));
  const [note, setNote] = useState("");
  const [lines, setLines] = useState(initial.lines || [{ account_code: "", debit: 0, credit: 0, description: "" }, { account_code: "", debit: 0, credit: 0, description: "" }]);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  // G1-34 — tanpa opsi "—"; placeholder menjelaskan isian (opsional).
  const entOpts = entities.filter((e) => !e.is_group).map((e) => ({ value: e.id, label: e.short_name || e.id }));
  const [entFrom, setEntFrom] = useState("");
  const [entTo, setEntTo] = useState("");

  const setLine = (i, k, v) => setLines((ls) => ls.map((l, idx) => idx === i ? { ...l, [k]: v } : l));
  const addLine = () => setLines((ls) => [...ls, { account_code: "", debit: 0, credit: 0, description: "" }]);
  const rmLine = (i) => setLines((ls) => ls.filter((_, idx) => idx !== i));

  const totalD = lines.reduce((s, l) => s + (Number(l.debit) || 0), 0);
  const totalC = lines.reduce((s, l) => s + (Number(l.credit) || 0), 0);
  const balanced = Math.abs(totalD - totalC) < 0.5 && totalD > 0;

  const save = async () => {
    const clean = lines.filter((l) => l.account_code && ((Number(l.debit) || 0) > 0 || (Number(l.credit) || 0) > 0));
    if (clean.length === 0) { setErr("Minimal satu baris eliminasi dengan akun & nominal."); return; }
    setSaving(true); setErr("");
    try {
      await axios.post(`${API}/finance/consolidation/eliminations`, {
        name, effective_date: effDate, note, entity_from: entFrom || null, entity_to: entTo || null,
        lines: clean.map((l) => ({ account_code: l.account_code, debit: Number(l.debit) || 0, credit: Number(l.credit) || 0, description: l.description })),
      });
      onSaved();
    } catch (e) { setErr(apiErrorText(e, "Gagal menyimpan eliminasi.")); setSaving(false); }
  };

  return (
    <FormModal open onClose={onClose} size="lg" icon={ScissorsLineDashed} testId="cons-elim-modal"
      title="Tambah Eliminasi Intercompany" subtitle="Adjustment grup — jurnal per-PT tidak berubah."
      onSubmit={save} submitLabel={saving ? "Menyimpan…" : "Simpan Eliminasi"} submitTestId="cons-form-save"
      busy={saving} submitDisabled={!balanced} error={err}>
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Nama" required><input data-testid="cons-form-name" className="field" value={name} onChange={(e) => setName(e.target.value)} /></Field>
            <Field label="Tanggal Efektif" required><KNDatePicker data-testid="cons-form-date" value={effDate} onChange={setEffDate} /></Field>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Badan usaha dari (opsional)"><KNSelect className="field" value={entFrom} onValueChange={setEntFrom} options={entOpts} placeholder="Pilih badan usaha" /></Field>
            <Field label="Badan usaha ke (opsional)"><KNSelect className="field" value={entTo} onValueChange={setEntTo} options={entOpts} placeholder="Pilih badan usaha" /></Field>
          </div>
          <Field label="Catatan (opsional)"><input data-testid="cons-form-note" className="field" value={note} onChange={(e) => setNote(e.target.value)} /></Field>

          <div className="rounded-md border border-[#EFF0F2]">
            <div className="flex items-center px-2 py-1.5 bg-[#FAFBFC] border-b border-[#EFF0F2]">
              <span className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">Baris Jurnal Eliminasi <span className="text-[#C0392B]">*</span></span>
              <button type="button" data-testid="cons-form-addline" className="ml-auto text-[11px] text-[#0058CC] font-semibold inline-flex items-center gap-1" onClick={addLine}><Plus size={12} /> Baris</button>
            </div>
            <div className="p-2 space-y-2">
              <div className="grid grid-cols-12 gap-1.5 px-0.5 text-[9.5px] font-bold uppercase tracking-wide text-[#8E8E93]" data-testid="cons-form-line-head">
                <span className="col-span-5">Akun</span><span className="col-span-2 text-right">Debit</span>
                <span className="col-span-2 text-right">Kredit</span><span className="col-span-2">Keterangan</span><span className="col-span-1" />
              </div>
              {lines.map((l, i) => (
                <div key={i} className="grid grid-cols-12 gap-1.5 items-center" data-testid={`cons-form-line-${i}`}>
                  <div className="col-span-5"><KNSelect data-testid={`cons-form-line-acct-${i}`} className="field !py-1 text-[11px]" value={l.account_code} onValueChange={(v) => setLine(i, "account_code", v)} options={accounts} placeholder="Pilih akun" searchable /></div>
                  <input data-testid={`cons-form-line-debit-${i}`} type="number" className="field !py-1 text-[11px] col-span-2 tabular-nums" placeholder="Debit" value={l.debit || ""} onChange={(e) => setLine(i, "debit", e.target.value)} />
                  <input data-testid={`cons-form-line-credit-${i}`} type="number" className="field !py-1 text-[11px] col-span-2 tabular-nums" placeholder="Kredit" value={l.credit || ""} onChange={(e) => setLine(i, "credit", e.target.value)} />
                  <input className="field !py-1 text-[11px] col-span-2" aria-label="Keterangan baris" value={l.description || ""} onChange={(e) => setLine(i, "description", e.target.value)} />
                  <button type="button" className="col-span-1 text-[#C9C9CE] hover:text-[#C0392B] flex justify-center" onClick={() => rmLine(i)} aria-label="Hapus baris"><Trash2 size={13} /></button>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-3 px-3 py-2 border-t border-[#EFF0F2] text-[11px]">
              <span className="text-[#6B6B73]">Total Debit: <b className="tabular-nums">{formatCurrency(totalD)}</b></span>
              <span className="text-[#6B6B73]">Total Kredit: <b className="tabular-nums">{formatCurrency(totalC)}</b></span>
              <span data-testid="cons-form-balance" className={`ml-auto font-bold rounded-full px-2 py-0.5 ${balanced ? "bg-[#E6F6EC] text-[#1B7F4B]" : "bg-[#FDEDE7] text-[#C0392B]"}`}>{balanced ? "Seimbang ✓" : "Belum seimbang"}</span>
            </div>
          </div>
        </div>
    </FormModal>
  );
}

export function DetectModal({ detect, onClose, onUse }) {
  const cands = detect?.candidates || [];
  return (
    <FormModal open onClose={onClose} size="md" icon={Wand2} testId="cons-detect-modal" title="Deteksi Kandidat Intercompany"
      footer={(
        <div className="flex items-center justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose}>Tutup</button>
          <button type="button" data-testid="cons-detect-use" className="primary-button" onClick={onUse}
            disabled={(detect?.suggested_lines || []).length === 0}>Jadikan Draf Eliminasi</button>
        </div>
      )}>
          <p className="text-[11px] text-[#8E8E93] mb-3">Terdeteksi {detect?.detected_accounts || 0} akun ber-keyword intercompany. Kandidat dengan saldo per-PT:</p>
          {cands.length === 0 ? (
            <div data-testid="cons-detect-empty" className="py-8 text-center text-[12px] text-[#8E8E93]">
              Tidak ada akun/saldo intercompany terdeteksi. Beri nama akun mengandung kata "Intercompany"/"Antar-PT" agar terdeteksi otomatis.
            </div>
          ) : (
            <div className="space-y-2">
              {cands.map((c) => (
                <div key={c.account_code} data-testid={`cons-cand-${c.account_code}`} className="rounded-md border border-[#EFF0F2] p-2.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] text-[#9A9BA3]">{c.account_code}</span>
                    <span className="text-[12px] font-bold text-[#1C1C1E]">{c.account_name}</span>
                    <span className="text-[11px] text-[#6B6B73] ml-auto tabular-nums">Net {formatCurrency(c.total_net)}</span>
                  </div>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {c.per_entity.map((p) => (
                      <span key={p.entity_id} className="text-[10px] rounded-full px-2 py-0.5 bg-[#F3F3F5] text-[#6B6B73]">{p.short_name}: <b className="tabular-nums">{formatCurrency(p.balance)}</b></span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
    </FormModal>
  );
}

function ToolButton({ testId, icon: Icon, label, hint, onClick, disabled }) {
  return (
    <div className="grid gap-1">
      <button type="button" data-testid={testId} className="secondary-button justify-start" onClick={onClick} disabled={disabled}>
        <Icon size={13} /> {label}
      </button>
      <p className="text-[10.5px] leading-snug text-[#6B6B73]">{hint}</p>
    </div>
  );
}

function Field({ label, required = false, children }) {
  return (<label className="block"><span className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93] block mb-1">{label}{required && <span className="text-[#C0392B]"> *</span>}</span>{children}</label>);
}
