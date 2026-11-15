/**
 * IncentiveSheetsView — KM-T3 · SDM › Kinerja & Insentif › **Lembar Insentif** (view `incentive-sheets`).
 *
 * Daftar dokumen keputusan insentif per PT: saringan "Periode bayar" dan "Status", cari nomor/judul, berhalaman dengan
 * jumlah total. Nomor membuka rincian (`IncentiveSheetDetail`, pop-up baku). "Buat lembar" memakai pop-up baku
 * (`FormModal`: Periode bayar, Judul (opsional)); mati saat "Semua PT" dengan petunjuk "Pilih satu PT dulu." (L4) atau
 * tanpa izin `incentive.prepare` — alasannya tertulis di samping tombol.
 *
 * Sumber: GET/POST /api/incentive/sheets (membaca: `incentive.view`, juga penyiap `incentive.prepare` dan pemutus
 * `incentive.approve`). Dibuka dari Pusat Persetujuan (antrean "Lembar insentif menunggu pengesahan") dengan preset
 * `{status: "submitted"}`; dibuka dari Capaian dengan `focusDoc` lembar yang baru dibuat.
 *
 * Lebar tabel (kartu ±750 px di layar 1024): 7 kolom tanpa kolom aksi (nomor = tautan), judul kolom boleh dua baris,
 * total tanpa "Rp" (keterangan di atas tabel); nama penyiap/pemutus boleh turun baris.
 *
 * KM-T5 — tautan "Skema insentif lama (arsip)" dicabut: jenjang komisi otomatis kini di Target & Aturan › "Komisi otomatis
 * (cara lama)" (hanya PT yang belum beralih ke Lembar Insentif).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { ClipboardList, Plus, Search } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import EntityScopeBanner from "../../components/EntityScopeBanner";
import ErrorNotice from "../../components/ErrorNotice";
import FilterChips from "../../components/FilterChips";
import FormModal from "../../components/FormModal";
import KNPager from "../../components/KNPager";
import KNSelect from "../../components/KNSelect";
import useIntentKey from "../../hooks/useIntentKey";
import useViewPreset from "../../hooks/useViewPreset";
import { moneyPost } from "../../utils/moneyRequest";
import { canCurrent } from "../../config/roles";
import { useEntityScope } from "../../context/EntityScopeContext";
import { entityFullById } from "../../utils/entityLabel";
import { apiErrorText } from "../../utils/apiError";
import { formatPeriod, todayWib } from "../../utils/formatters";
import { pilihanPeriode } from "./IncentiveSetupView";
import IncentiveSheetDetail, { STATUS_PILIHAN, StatusLembar, angka, labelStatusLembar } from "./IncentiveSheetDetail";

export const TEKS_KOSONG = "Belum ada lembar insentif untuk saringan ini.";
export const TEKS_SEMUA_PT = "Pilih satu PT dulu.";
export const TEKS_TANPA_IZIN = "Membuat lembar butuh akses Siapkan lembar insentif di modul Kinerja & Insentif.";
const UKURAN_HALAMAN = 25;

/** Alasan "Buat lembar" mati — ditulis di samping tombol. "" = boleh. */
export function alasanBuat({ canWrite, canPrepare }) {
  if (!canWrite) return TEKS_SEMUA_PT;
  if (!canPrepare) return TEKS_TANPA_IZIN;
  return "";
}

/** Periode bayar bawaan pop-up "Buat lembar": bulan berjalan (WIB). */
export const periodeBayarBawaan = () => String(todayWib()).slice(0, 7);

export default function IncentiveSheetsView({ focusDoc, onClearFocus }) {
  const { canWrite, selectedEntity, entities } = useEntityScope();
  const canPrepare = canCurrent("incentive", "prepare");
  const pt = entityFullById(entities, selectedEntity, "PT ini");
  const [periode, setPeriode] = useState("");
  const [status, setStatus] = useState("");
  const [cari, setCari] = useState("");
  const [cariAktif, setCariAktif] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading");
  const [err, setErr] = useState("");
  const [openId, setOpenId] = useState("");
  const [buat, setBuat] = useState(false);
  const [form, setForm] = useState({ pay_period: periodeBayarBawaan(), title: "" });
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState("");
  const intent = useIntentKey("isheet-new");

  useViewPreset("incentive-sheets", (p) => { if (p.status !== undefined) { setStatus(p.status || ""); setPage(1); } });
  useEffect(() => {
    if (focusDoc?.focus_id && (!focusDoc.focus_type || focusDoc.focus_type === "incentive_sheet")) {
      setOpenId(focusDoc.focus_id);
      onClearFocus?.();
    }
  }, [focusDoc, onClearFocus]);
  useEffect(() => {
    const t = setTimeout(() => { setCariAktif(cari.trim()); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [cari]);

  const load = useCallback(async () => {
    setState("loading");
    try {
      const r = await axios.get(`${API}/incentive/sheets`, { params: {
        pay_period: periode || undefined, status: status || undefined, q: cariAktif || undefined, page, page_size: UKURAN_HALAMAN } });
      setData(r.data); setErr(""); setState("ready");
    } catch (e) { setErr(apiErrorText(e) || ""); setState("error"); }
  }, [periode, status, cariAktif, page]);
  useEffect(() => { load(); }, [load, selectedEntity]);

  const alasan = alasanBuat({ canWrite, canPrepare });
  const items = data?.items || [];
  const opsiPeriode = useMemo(() => [{ value: "", label: "Semua periode" }, ...pilihanPeriode("month", periodeBayarBawaan())], []);
  const chips = [{ key: "all", label: "Semua" }, ...STATUS_PILIHAN.map((s) => ({ key: s, label: labelStatusLembar(s) }))];
  const simpan = async () => {
    if (!form.pay_period) { setFormErr("Pilih periode bayar."); return; }
    setBusy(true); setFormErr("");
    const body = { pay_period: form.pay_period, title: (form.title || "").trim() };
    try {
      const r = await intent.send(body, (k) => moneyPost(`${API}/incentive/sheets`, body, k));
      setBuat(false); setOpenId(r.data?.id || ""); await load();
    } catch (e) { setFormErr(apiErrorText(e) || "Lembar gagal dibuat."); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-4" data-testid="incentive-sheets-view">
      <EntityScopeBanner testId="isheets-scope" />
      <div className="section-card" data-testid="isheets-card">
        <div className="section-head"><h2 className="flex items-center gap-2"><ClipboardList size={16} className="text-kn-action" aria-hidden="true" />Lembar Insentif</h2></div>
        <div className="section-body space-y-3">
          <p className="text-fs-12 text-kn-text-2">Satu lembar per periode bayar berisi nominal insentif per sales dan komponen. Nominal diketik orang; angka dasar dipotret saat baris dibuat.</p>
          <div className="flex flex-wrap items-center gap-2" data-testid="isheets-actions">
            <button type="button" className="primary-button btn-sm whitespace-nowrap" data-testid="isheets-create" disabled={!!alasan}
              onClick={() => { setForm({ pay_period: periodeBayarBawaan(), title: "" }); setFormErr(""); setBuat(true); }}>
              <Plus size={13} aria-hidden="true" /> Buat lembar</button>
            {alasan && <span className="text-fs-12 text-kn-text-2" data-testid="isheets-create-why">{alasan}</span>}
          </div>
          <div className="flex flex-wrap items-end gap-3" data-testid="isheets-filters">
            <div className="w-[190px]"><label className="field-label">Periode bayar</label>
              <KNSelect data-testid="isheets-period" value={periode} className="field" options={opsiPeriode}
                onValueChange={(v) => { setPeriode(v || ""); setPage(1); }} /></div>
            <label className="relative block w-full max-w-[260px]">
              <span className="field-label">Cari</span>
              <Search size={13} className="absolute bottom-2.5 left-2 text-kn-text-2" aria-hidden="true" />
              <input data-testid="isheets-search" className="field pl-7" placeholder="Nomor atau judul" aria-label="Cari nomor atau judul"
                value={cari} onChange={(e) => setCari(e.target.value)} />
            </label>
          </div>
          <FilterChips testId="isheets-status" ariaLabel="Saringan status" value={status || "all"} options={chips}
            onChange={(v) => { setStatus(!v || v === "all" ? "" : v); setPage(1); }} />
        </div>
        {state === "loading" ? (
          <div className="section-pad text-fs-13 text-kn-text-2" role="status" data-testid="isheets-loading">Memuat lembar insentif…</div>
        ) : state === "error" ? (
          <div className="section-pad"><ErrorNotice testId="isheets-error" message={`Lembar insentif gagal dimuat. ${err}`.trim()} onRetry={load} /></div>
        ) : items.length === 0 ? (
          <div className="section-pad text-center text-fs-13 text-kn-text-2" data-testid="isheets-empty">{TEKS_KOSONG}</div>
        ) : (
          <>
            <p className="px-3 pb-1 text-fs-12 text-kn-text-2">Total dalam rupiah · klik nomor untuk membuka lembar.</p>
            <div className="overflow-x-auto">
              <table className="data-table head-wrap w-full" data-testid="isheets-table">
                <thead><tr>
                  <th>Nomor</th><th>Periode bayar</th><th>Status</th><th className="text-right">Baris</th>
                  <th className="text-right">Total</th><th>Penyiap</th><th>Pemutus</th>
                </tr></thead>
                <tbody>
                  {items.map((s) => (
                    <tr key={s.id} data-testid={`isheets-row-${s.id}`}>
                      <td className="min-w-[128px]">
                        <button type="button" className="link-button font-mono text-left" data-testid={`isheets-open-${s.id}`}
                          aria-label={`Buka lembar ${s.number}`} onClick={() => setOpenId(s.id)}>{s.number}</button>
                        {s.title && <span className="block max-w-[200px] break-words text-fs-12 text-kn-text-2">{s.title}</span>}
                        {data?.all_pt && <span className="block text-fs-12 text-kn-text-2">{entityFullById(entities, s.entity_id, "")}</span>}
                      </td>
                      <td className="whitespace-nowrap">{formatPeriod(s.pay_period, { short: true })}</td>
                      <td><StatusLembar status={s.status} testId={`isheets-row-status-${s.id}`} /></td>
                      <td className="text-right tabular-nums">{s.totals?.lines ?? (s.lines || []).length}</td>
                      <td className="text-right tabular-nums">{angka(s.totals?.amount || 0)}</td>
                      <td className="min-w-[96px] break-words">{s.prepared_by?.name || "—"}</td>
                      <td className="min-w-[96px] break-words">{s.approved_by?.name || <span className="text-kn-text-2">—</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-kn-divider px-3 py-2 text-fs-12 text-kn-text-2">
              <span data-testid="isheets-count">{items.length} dari {data?.total ?? items.length} lembar</span>
            </div>
            <KNPager page={page} pageSize={UKURAN_HALAMAN} total={data?.total || 0} onChange={setPage} testId="isheets-pager" />
          </>
        )}
      </div>
      <FormModal open={buat} onClose={() => setBuat(false)} title="Buat Lembar Insentif" subtitle={pt} icon={ClipboardList}
        testId="isheets-form" onSubmit={simpan} submitLabel="Buat Lembar" busy={busy} error={formErr}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div><label className="field-label">Periode bayar <span className="req">*</span></label>
            <KNSelect data-testid="isheets-form-period" value={form.pay_period} className="field" options={pilihanPeriode("month", form.pay_period)}
              onValueChange={(v) => setForm((f) => ({ ...f, pay_period: v }))} />
            <p className="mt-1 text-fs-12 text-kn-text-2">Bulan penggajian yang akan memuat lembar ini.</p></div>
          <div><label className="field-label">Judul (opsional)</label>
            <input data-testid="isheets-form-title" className="field" maxLength={120} value={form.title}
              placeholder="Contoh: Insentif Oktober + Triwulan III" onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} /></div>
        </div>
      </FormModal>
      {openId && <IncentiveSheetDetail sheetId={openId} onClose={() => { setOpenId(""); load(); }} onChanged={() => {}} />}
    </div>
  );
}
