import { apiErrorText } from "../../utils/apiError";
import MoneyInput from "../../components/MoneyInput";
import KNDatePicker from "@/components/KNDatePicker";
import KNMonthPicker from "@/components/KNMonthPicker";
import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { Plus, Trash2, ReceiptText } from "lucide-react";
import { formatCurrency, todayWib } from "../../utils/formatters";
import KNSelect from "../../components/KNSelect";
import FormModal from "../../components/FormModal";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyPatch, moneyPost } from "../../utils/moneyRequest";

/**
 * SettlementForm — Buat / Ubah Laporan Pertanggungjawaban atas PD yang sudah dicairkan.
 * Baris pengeluaran (tanggal/uraian/kategori/nominal) → ringkasan per kategori + sisa/kurang dana (BE hitung ulang &
 * posting GL saat disetujui).
 *
 * Fase 3 · P4 (L-03) — FormModal ukuran lg (layar penuh di HP). Kaki memakai `footer` (bukan <form>): Enter di baris
 * pengeluaran tidak menyimpan LPJ.
 * PK-24 (FY-14) — `record` = mode ubah, HANYA untuk LPJ draf (server menolak LPJ yang sudah diajukan); `resubmit` = LPJ
 * ditolak yang baru dibuka lagi: simpan lalu ajukan lagi ("Perbaiki & Ajukan Lagi"). Isian **Periode** = pilihan bulan
 * (`YYYY-MM`; dulu teks bebas "mis. Juli 2026").
 */
const emptyLine = () => ({ date: todayWib(), description: "", category: "petty_cash_lain", amount: "" });
const RX_BULAN = /^\d{4}-(0[1-9]|1[0-2])$/;

export default function SettlementForm({ categories, preselectPd, selectedEntity, record = null, resubmit = false,
  onCancel, onSaved }) {
  const isEdit = !!record;
  const [advances, setAdvances] = useState([]);
  const [pdId, setPdId] = useState(record?.cash_advance_id || preselectPd?.id || "");
  const [divisi, setDivisi] = useState(record?.divisi || "");
  const [periode, setPeriode] = useState(isEdit ? (RX_BULAN.test(record?.periode || "") ? record.periode : "") : todayWib().slice(0, 7));
  const [catatan, setCatatan] = useState(record?.catatan || "");
  const [lines, setLines] = useState(isEdit && (record.expense_lines || []).length
    ? record.expense_lines.map((l) => ({ date: l.date || todayWib(), description: l.description || "", category: l.category || "petty_cash_lain", amount: l.amount ?? "" }))
    : [emptyLine()]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  // PK-12 — simpan LPJ ber-Idempotency-Key (kirim ulang isi sama setelah koneksi putus tidak membuat LPJ kedua).
  const intent = useIntentKey(isEdit ? "stle" : "stl");
  const intentSubmit = useIntentKey("stls");
  const periodeLama = isEdit && record?.periode && !RX_BULAN.test(record.periode) ? record.periode : "";

  useEffect(() => { if (!isEdit) loadAdvances(); }, [selectedEntity]); // eslint-disable-line

  async function loadAdvances() {
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      const res = await axios.get(`${API}/cash-advances`, { params });
      const all = Array.isArray(res.data) ? res.data : [];
      setAdvances(all.filter((a) => ["disbursed", "settled"].includes(a.status)));
    } catch (e) { /* non-blocking */ }
  }

  const selectedPd = advances.find((a) => a.id === pdId) || (preselectPd?.id === pdId ? preselectPd : null);
  const danaDiterima = isEdit ? Number(record.total_pettycash) || 0 : Number(selectedPd?.total_amount) || 0;
  const totalPengeluaran = useMemo(() => lines.reduce((s, l) => s + (Number(l.amount) || 0), 0), [lines]);
  const sisa = danaDiterima - totalPengeluaran;

  const catTotals = useMemo(() => {
    const m = {};
    lines.forEach((l) => { const a = Number(l.amount) || 0; if (a > 0) m[l.category] = (m[l.category] || 0) + a; });
    return m;
  }, [lines]);

  const catOptions = categories.filter((c) => c.active !== false).map((c) => ({ value: c.code, label: c.label }));
  const catLabel = (code) => categories.find((c) => c.code === code)?.label || code;

  function updLine(i, k, v) { setLines(lines.map((l, idx) => (idx === i ? { ...l, [k]: v } : l))); }
  function addLine() { setLines([...lines, emptyLine()]); }
  function rmLine(i) { setLines(lines.length > 1 ? lines.filter((_, idx) => idx !== i) : lines); }

  async function submit() {
    setErr("");
    if (!pdId) { setErr("Pilih PD yang akan dipertanggungjawabkan."); return; }
    const clean = lines
      .filter((l) => (Number(l.amount) || 0) > 0)
      .map((l) => ({ date: l.date, description: l.description || "", category: l.category, amount: Number(l.amount) || 0 }));
    if (clean.length === 0) { setErr("Minimal 1 baris pengeluaran dengan nominal > 0."); return; }
    setBusy(true);
    try {
      let res;
      if (isEdit) {
        // Periode lama berupa teks bebas tidak ditimpa bila bulannya belum dipilih.
        const body = { divisi, expense_lines: clean, catatan, ...(periode ? { periode } : {}) };
        res = await intent.send({ id: record.id, ...body },
          (k) => moneyPatch(`${API}/cash-advance-settlements/${record.id}`, body, k));
        if (resubmit) {
          res = await intentSubmit.send({ id: record.id, aksi: "submit" },
            (k) => moneyPost(`${API}/cash-advance-settlements/${record.id}/submit`, {}, k));
        }
      } else {
        const body = { cash_advance_id: pdId, divisi, periode, expense_lines: clean, catatan };
        res = await intent.send(body, (k) => moneyPost(`${API}/cash-advance-settlements`, body, k));
      }
      onSaved(res.data);
    } catch (e) {
      setErr(apiErrorText(e, "Gagal menyimpan pertanggungjawaban."));
    } finally { setBusy(false); }
  }

  const label = !isEdit ? "Simpan LPJ" : resubmit ? "Simpan & Ajukan Lagi" : "Simpan Perubahan";
  const footer = (
    <div className="flex justify-end gap-2">
      <button type="button" className="btn-secondary" onClick={onCancel} disabled={busy}>Batal</button>
      <button type="button" data-testid="stl-submit" className="btn-primary whitespace-nowrap" onClick={submit} disabled={busy}>{busy ? "Menyimpan…" : label}</button>
    </div>
  );
  const title = !isEdit ? "Buat Pertanggungjawaban (LPJ)" : resubmit ? `Perbaiki & Ajukan Lagi ${record.number}` : `Ubah ${record.number}`;

  return (
    <FormModal open onClose={onCancel} size="lg" icon={ReceiptText} testId="stl-form" busy={busy} footer={footer}
      title={title}>
        <div className="grid gap-3">
          {err && <div className="notice-bar danger" data-testid="stl-form-error"><span>{err}</span><button type="button" onClick={() => setErr("")}>×</button></div>}
          {resubmit && (record.last_rejected_reason || record.rejected_reason) && (
            <div className="notice-bar warning" data-testid="stl-form-rejected">
              <span>Alasan ditolak: {record.last_rejected_reason || record.rejected_reason}</span>
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Pengajuan Dana (PD)" req>
              {isEdit ? (
                <input data-testid="stl-pd-locked" className="form-input bg-kn-neutral-soft" readOnly
                  value={`${record.cash_advance_number || "PD"} · ${formatCurrency(record.total_pettycash)}`} />
              ) : (
                <KNSelect data-testid="stl-pd-select" className="form-input" value={pdId} onValueChange={setPdId}
                  placeholder="Pilih PD yang sudah dicairkan"
                  options={advances.map((a) => ({ value: a.id, label: `${a.number} · ${a.kegiatan || a.divisi || ""} · ${formatCurrency(a.total_amount)}` }))} />
              )}
            </Field>
            <Field label="Divisi">
              <input data-testid="stl-divisi" className="form-input" value={divisi} onChange={(e) => setDivisi(e.target.value)} placeholder={selectedPd?.divisi || "Divisi"} />
            </Field>
            <Field label="Periode">
              <KNMonthPicker data-testid="stl-periode" value={periode} onChange={setPeriode} className="w-full"
                placeholder={periodeLama ? `Tertulis "${periodeLama}" — pilih bulannya` : "Pilih bulan"} />
            </Field>
            <Field label="Dana Diterima (dari PD)">
              <input data-testid="stl-dana" className="form-input bg-kn-neutral-soft" value={formatCurrency(danaDiterima)} readOnly />
            </Field>
          </div>

          {/* Expense lines */}
          {/* UAT 24 Okt (audit UI tahap 2) — G1-41: kolom tanggal 120→160px (dulu "Min, 25 Okt…" terpotong tanpa tahun). */}
          <div className="rounded-md border border-[#EFF0F2] overflow-x-auto">
            <div className="min-w-[640px] grid grid-cols-[160px_1.5fr_1fr_130px_36px] bg-[#FAFBFC] px-3 py-1.5 text-[10px] font-bold uppercase text-[#6B6B73]">
              <span>Tanggal</span><span>Uraian</span><span>Kategori</span><span className="text-right">Nominal</span><span></span>
            </div>
            {lines.map((l, i) => (
              <div key={i} data-testid={`stl-line-${i}`} className="min-w-[640px] grid grid-cols-[160px_1.5fr_1fr_130px_36px] items-center gap-1 px-3 py-2 border-t border-[#F4F5F7]">
                <KNDatePicker data-testid={`stl-line-date-${i}`} value={l.date} onChange={(v) => updLine(i, "date", v)} clearable={false} />
                <input data-testid={`stl-line-desc-${i}`} className="form-input" value={l.description} onChange={(e) => updLine(i, "description", e.target.value)} placeholder="Uraian pengeluaran" />
                <KNSelect data-testid={`stl-line-cat-${i}`} className="form-input" value={l.category} onValueChange={(v) => updLine(i, "category", v)} options={catOptions} />
                <MoneyInput testId={`stl-line-amount-${i}`} className="form-input text-right" value={l.amount} placeholder="0" onChange={(v) => updLine(i, "amount", v)} />
                <button type="button" className="icon-button text-red-500" onClick={() => rmLine(i)} aria-label="Hapus"><Trash2 size={14} /></button>
              </div>
            ))}
            <div className="px-3 py-2 border-t border-[#EFF0F2] bg-[#FAFBFC]">
              <button type="button" data-testid="stl-add-line" className="btn-secondary btn-xs" onClick={addLine}><Plus size={13} /> Tambah Baris</button>
            </div>
          </div>

          {/* Summary per category + sisa/kurang */}
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-md border border-[#EFF0F2] p-3">
              <p className="text-[10px] font-bold uppercase text-[#6B6B73] mb-1.5">Ringkasan per Kategori</p>
              {Object.keys(catTotals).length === 0 ? <p className="text-[11.5px] text-[#9A9BA3]">Belum ada pengeluaran.</p> : (
                <div className="space-y-1">
                  {Object.entries(catTotals).map(([c, a]) => (
                    <div key={c} className="flex justify-between text-[11.5px]"><span className="text-[#3C3C43]">{catLabel(c)}</span><span className="font-semibold tabular-nums">{formatCurrency(a)}</span></div>
                  ))}
                </div>
              )}
            </div>
            <div className="rounded-md border border-[#EFF0F2] p-3 space-y-1.5">
              <Row k="Total Pengeluaran" v={formatCurrency(totalPengeluaran)} testId="stl-total-pengeluaran" />
              <Row k="Dana Diterima" v={formatCurrency(danaDiterima)} />
              <div className="border-t border-[#EFF0F2] pt-1.5">
                {/* PK-24 (FY-19) — sisa baru menjadi kewajiban kembali sesudah LPJ disetujui. */}
                <Row k={sisa >= 0 ? "Sisa Uang Muka (dikembalikan sesudah disetujui)" : "Kekurangan Dana"} v={formatCurrency(Math.abs(sisa))} strong tone={sisa >= 0 ? "text-kn-success-text" : "text-kn-danger-text"} testId="stl-sisa" />
              </div>
            </div>
          </div>

          <Field label="Catatan">
            <textarea data-testid="stl-catatan" className="form-input" rows="2" value={catatan} onChange={(e) => setCatatan(e.target.value)} placeholder="Keterangan tambahan..." />
          </Field>
        </div>
    </FormModal>
  );
}

function Field({ label, req, children }) {
  return (<div className="grid gap-1.5"><label className="text-fs-12 font-bold uppercase text-kn-text-2">{label}{req && <span className="req"> *</span>}</label>{children}</div>);
}
function Row({ k, v, strong, tone, testId }) {
  return (<div className="flex justify-between gap-2 text-fs-12"><span className="text-kn-text">{k}</span><span data-testid={testId} className={`font-bold tabular-nums ${tone || ""}`}>{v}</span></div>);
}
