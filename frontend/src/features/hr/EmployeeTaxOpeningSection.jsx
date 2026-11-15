/**
 * EmployeeTaxOpeningSection — PY-T3 (PY-12) · kartu karyawan › Saldo awal pajak {tahun}.
 *
 * Untuk PT yang mulai memakai penggajian di tengah tahun: jumlah masa pajak tahun itu yang dibayar di luar sistem, bruto,
 * iuran pensiun (JHT + JP karyawan), dan PPh 21 yang sudah dipotong. Hitung ulang pajak masa terakhir (Desember atau
 * bulan keluar) menambahkan angka ini sebelum menghitung pajak setahun. Hanya tampil bagi pemegang izin melihat data
 * pribadi karyawan; menyimpan butuh izin mengatur penggajian. Saldo awal terkunci sesudah slip masa pajak terakhir tahun
 * itu diposting (server 409).
 *
 * Sumber: GET/PUT /api/hr/employees/{id}/tax-opening?year= (PT aktif). Keadaan memuat · galat (+ Coba lagi) dibedakan;
 * tombol mati menulis alasannya di sampingnya.
 */
import { useCallback, useEffect, useState } from "react";
import { Landmark, RefreshCw, Save } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import KNSelect from "../../components/KNSelect";
import MoneyInput from "../../components/MoneyInput";
import { askConfirm } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, todayWib } from "../../utils/formatters";
import { entityFullById } from "../../utils/entityLabel";
import { can } from "../../config/roles";
import { useEntityScope } from "../../context/EntityScopeContext";

export const KETERANGAN_SALDO = "Isi sekali bila penggajian mulai dipakai di tengah tahun, supaya hitung ulang pajak akhir tahun benar.";

/** Galat isian saldo awal; "" = siap kirim. */
export function galatSaldoAwal(f) {
  const m = Number(f?.months);
  if (!Number.isInteger(m) || m < 1 || m > 11) return "Jumlah masa harus 1 sampai 11.";
  for (const [k, label] of [["tax_gross", "Bruto"], ["pension_deduction", "Iuran pensiun"], ["pph21_withheld", "PPh 21 sudah dipotong"]]) {
    const v = Number(f?.[k] === "" || f?.[k] === undefined || f?.[k] === null ? 0 : f[k]);
    if (!Number.isFinite(v) || v < 0) return `${label} harus rupiah, tidak negatif.`;
  }
  return "";
}

/** Alasan tombol Simpan mati (ditulis di samping tombol). */
export function alasanSimpanSaldo({ canWrite, canManage }) {
  if (!canWrite) return "Pilih satu PT dulu untuk mengisi saldo awal pajak.";
  if (!canManage) return "Mengisi saldo awal pajak butuh izin mengatur penggajian.";
  return "";
}

const kosong = () => ({ months: "", tax_gross: "", pension_deduction: "", pph21_withheld: "", note: "" });

export default function EmployeeTaxOpeningSection({ employee, currentUser }) {
  const { canWrite, selectedEntity, entities } = useEntityScope();
  const canManage = can(currentUser?.permissions, "hr", "manage_payroll");
  const thisYear = Number(String(todayWib()).slice(0, 4)) || new Date().getFullYear();
  const [year, setYear] = useState(thisYear);
  const [form, setForm] = useState(kosong());
  const [saved, setSaved] = useState(null);
  const [state, setState] = useState("loading");
  const [err, setErr] = useState("");
  const [formErr, setFormErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const empId = employee?.id;
  const pt = entityFullById(entities, canWrite ? selectedEntity : employee?.entity_id, "PT karyawan");
  const alasan = alasanSimpanSaldo({ canWrite, canManage });
  const yearOpts = [thisYear - 1, thisYear].map((y) => ({ value: String(y), label: String(y) }));

  const load = useCallback(async () => {
    if (!empId) return;
    setState("loading");
    try {
      const r = await axios.get(`${API}/hr/employees/${empId}/tax-opening`, { params: { year } });
      const d = r.data || null;
      setSaved(d);
      setForm(d ? { months: String(d.months), tax_gross: d.tax_gross, pension_deduction: d.pension_deduction,
        pph21_withheld: d.pph21_withheld, note: d.note || "" } : kosong());
      setErr(""); setFormErr(""); setState("ready");
    } catch (e) { setErr(apiErrorText(e) || ""); setState("error"); }
  }, [empId, year]);
  useEffect(() => { load(); }, [load]);

  const ubah = (patch) => setForm((f) => ({ ...f, ...patch }));
  async function simpan() {
    const g = galatSaldoAwal(form);
    if (g) { setFormErr(g); return; }
    const body = { year, months: Number(form.months), tax_gross: Number(form.tax_gross || 0),
      pension_deduction: Number(form.pension_deduction || 0), pph21_withheld: Number(form.pph21_withheld || 0),
      note: String(form.note || "").trim() };
    const ok = await askConfirm({ title: `Simpan saldo awal pajak ${year}?`, confirmLabel: "Simpan",
      message: `${employee?.name || "Karyawan"} di ${pt}: ${body.months} masa di luar sistem, bruto ${formatCurrency(body.tax_gross)}, PPh 21 sudah dipotong ${formatCurrency(body.pph21_withheld)}. Angka ini dipakai saat pajak setahun dihitung ulang.` });
    if (!ok) return;
    setBusy(true);
    try {
      await axios.put(`${API}/hr/employees/${empId}/tax-opening`, body);
      setMsg(`Saldo awal pajak ${year} tersimpan.`); await load();
    } catch (e) { setFormErr(apiErrorText(e) || "Saldo awal gagal disimpan."); }
    finally { setBusy(false); }
  }

  return (
    <div className="section-card" data-testid="emp-tax-opening">
      <div className="section-head flex-wrap gap-2">
        <h3 className="flex items-center gap-2" data-testid="emp-tax-opening-title"><Landmark size={14} className="text-kn-action" aria-hidden="true" />Saldo awal pajak {year}</h3>
        <button type="button" data-testid="emp-tax-opening-refresh" onClick={load} className="secondary-button btn-sm ml-auto whitespace-nowrap"><RefreshCw size={13} /> Muat ulang</button>
      </div>
      {state === "loading" ? (
        <div className="section-pad text-fs-13 text-kn-text-2" role="status">Memuat saldo awal pajak…</div>
      ) : state === "error" ? (
        <div className="section-pad"><ErrorNotice testId="emp-tax-opening-error" message={`Saldo awal pajak tidak bisa dimuat. ${err}`.trim()} onRetry={load} /></div>
      ) : (
        <div className="section-body space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-fs-12 font-semibold text-kn-text-2">Tahun pajak</span>
            <div className="w-24"><KNSelect data-testid="emp-tax-opening-year" value={String(year)} onValueChange={(v) => setYear(Number(v))} className="field" options={yearOpts} aria-label="Tahun pajak" /></div>
          </div>
          <p className="text-fs-12 text-kn-text-2" data-testid="emp-tax-opening-note">{KETERANGAN_SALDO}</p>
          {msg && <p className="text-fs-12 text-kn-text" role="status" data-testid="emp-tax-opening-msg">{msg}</p>}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div><label className="field-label" htmlFor="emp-tax-opening-months">Jumlah masa di luar sistem</label>
              <input id="emp-tax-opening-months" data-testid="emp-tax-opening-months" className="field tabular-nums" inputMode="numeric" value={form.months} onChange={(e) => ubah({ months: e.target.value.replace(/[^\d]/g, "") })} placeholder="1–11" disabled={!!alasan} /></div>
            <div><label className="field-label">Bruto</label>
              <MoneyInput testId="emp-tax-opening-gross" value={form.tax_gross} onChange={(v) => ubah({ tax_gross: v })} className="field tabular-nums" disabled={!!alasan} /></div>
            <div><label className="field-label">Iuran pensiun</label>
              <MoneyInput testId="emp-tax-opening-pension" value={form.pension_deduction} onChange={(v) => ubah({ pension_deduction: v })} className="field tabular-nums" disabled={!!alasan} />
              <span className="text-fs-12 text-kn-text-2">JHT + JP yang dipotong dari karyawan.</span></div>
            <div><label className="field-label">PPh 21 sudah dipotong</label>
              <MoneyInput testId="emp-tax-opening-pph" value={form.pph21_withheld} onChange={(v) => ubah({ pph21_withheld: v })} className="field tabular-nums" disabled={!!alasan} /></div>
            <div className="sm:col-span-2"><label className="field-label" htmlFor="emp-tax-opening-text">Catatan</label>
              <input id="emp-tax-opening-text" data-testid="emp-tax-opening-text" className="field" value={form.note} onChange={(e) => ubah({ note: e.target.value })} placeholder="Contoh: Januari–Juni dibayar lewat aplikasi lama" maxLength={300} disabled={!!alasan} /></div>
          </div>
          {formErr && <p className="text-fs-12 text-kn-danger-text" role="alert" data-testid="emp-tax-opening-form-error">{formErr}</p>}
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" data-testid="emp-tax-opening-save" disabled={!!alasan || busy} onClick={simpan} className="primary-button btn-sm whitespace-nowrap"><Save size={13} /> {busy ? "Menyimpan…" : "Simpan"}</button>
            {alasan && <span className="text-fs-12 text-kn-text-2" data-testid="emp-tax-opening-why">{alasan}</span>}
            {saved && <span className="text-fs-12 text-kn-text-2" data-testid="emp-tax-opening-saved">Terakhir diubah {saved.updated_by || "—"}.</span>}
          </div>
        </div>
      )}
    </div>
  );
}
