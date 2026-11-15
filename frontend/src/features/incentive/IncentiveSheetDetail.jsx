/**
 * IncentiveSheetDetail — KM-T3 · rincian satu **Lembar Insentif** (pop-up baku `DetailModal`, INV-UI-08).
 *
 * Lembar = dokumen keputusan insentif satu PT untuk satu periode bayar. Nominal DIKETIK penyiap (tidak ada angka
 * usulan dari sistem); angka dasar tiap baris dipotret server saat baris dibuat dan tidak berubah sesudah lembar
 * disahkan. Bila data sumber berubah sesudah dipotret, baris menampilkan "Berubah sejak dipotret: …" — bahan baris
 * penyesuaian di lembar berikutnya, bukan perubahan otomatis.
 *
 * Tombol menurut status dan izin (`canCurrent`, bukan nama peran): Draf → Tambah baris · Tambah penyesuaian · Segarkan
 * angka dasar · Simpan nominal · Ajukan · Batalkan (`incentive.prepare`); Diajukan → Sahkan (boleh mengoreksi nominal
 * dengan catatan) · Kembalikan (`incentive.approve`); semua status → Ekspor Excel. Tombol mati selalu disertai alasan
 * tertulis. Sahkan meminta konfirmasi yang menyebut banyak baris, total, dan PT (N5); Kembalikan & Batalkan meminta
 * alasan. Semua tulisan lewat `moneyRequest` + `useIntentKey` (N4: klik ganda / kirim ulang = satu tulisan).
 *
 * Lebar tabel (pop-up `xl`, ±990 px di layar 1024): 8 kolom tanpa kolom aksi — tombol buka-tutup di sel Sales, hapus
 * baris di rincian baris; judul kolom boleh dua baris (`head-wrap`), angka uang tanpa "Rp" (keterangan di atas tabel).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Ban, CheckCircle2, ChevronDown, ChevronRight, Clock, Download, FilePen, Plus, RefreshCw,
  Search, Send, Trash2, Undo2, Wallet, X, XCircle } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import DetailModal from "../../components/DetailModal";
import ErrorNotice from "../../components/ErrorNotice";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyDelete, moneyPatch, moneyPost } from "../../utils/moneyRequest";
import { askConfirm, askReason } from "../../services/confirmService";
import { canCurrent } from "../../config/roles";
import { useEntityScope } from "../../context/EntityScopeContext";
import { entityFullById } from "../../utils/entityLabel";
import { apiErrorText } from "../../utils/apiError";
import { docStatusLabel } from "../../utils/docStatus";
import { formatCurrency, formatDateTime, formatDecimal, formatPeriod, todayWib } from "../../utils/formatters";
import { pilihanPeriode } from "./IncentiveSetupView";

// ── Pembantu bersama (dipakai juga daftar lembar dan tombol di Capaian) ─────────────────────────────────────────────
/** Label lokal status lembar (didahulukan sebelum peta bersama `docStatusLabel`). */
const LABEL_STATUS = { draft: "Draf", submitted: "Diajukan", approved: "Disahkan", paid: "Dibayarkan", cancelled: "Dibatalkan" };
/** Status = ikon + teks + warna (KN_37 §8) memakai kelas `status-*` yang ADA di `styles/components.css`. */
export const STATUS_LEMBAR = {
  draft: { cls: "status-draft", Icon: FilePen },
  submitted: { cls: "status-pending", Icon: Clock },
  approved: { cls: "status-done", Icon: CheckCircle2 },
  paid: { cls: "status-shipped", Icon: Wallet },
  cancelled: { cls: "status-cancelled", Icon: XCircle },
};
export const STATUS_PILIHAN = ["draft", "submitted", "approved", "paid", "cancelled"];
export const labelStatusLembar = (s) => docStatusLabel(s, LABEL_STATUS);

export function StatusLembar({ status, testId }) {
  const m = STATUS_LEMBAR[status] || STATUS_LEMBAR.draft;
  const { Icon } = m;
  return (
    <span className={`status-pill ${m.cls} whitespace-nowrap`} data-testid={testId}>
      <Icon size={12} aria-hidden="true" />{labelStatusLembar(status)}
    </span>
  );
}

/** Angka uang di sel tabel tanpa "Rp" (keterangan di atas tabel): 800000000 → "800.000.000"; kosong → "—". */
export const angka = (v) => (v === null || v === undefined || v === "" ? "—" : Math.round(Number(v)).toLocaleString("id-ID"));
/** Persen satu desimal berkoma: 86.2 → "86,2 %"; kosong → "—". */
export const persen = (v) => (v === null || v === undefined ? "—" : `${formatDecimal(v, 1, 1)} %`);
/** Isian nominal berpemisah ribuan; negatif hanya untuk baris penyesuaian. "" = kosong. */
export function tampilNominal(v) {
  if (v === "" || v === null || v === undefined || v === "-") return v === "-" ? "-" : "";
  const n = Number(v);
  if (Number.isNaN(n)) return "";
  return `${n < 0 ? "-" : ""}${Math.abs(Math.round(n)).toLocaleString("id-ID")}`;
}
export function bacaNominal(teks, bolehNegatif) {
  const s = String(teks || "").trim();
  const neg = bolehNegatif && s.startsWith("-");
  const d = s.replace(/[^\d]/g, "");
  if (!d) return neg ? "-" : "";
  return String((neg ? -1 : 1) * Number(d));
}

/** Konfirmasi Sahkan (N5): nomor, banyak baris, total, nama PT, dan akibatnya. */
export function teksKonfirmasiSahkan(sheet, pt, total) {
  const n = sheet?.totals?.lines ?? (sheet?.lines || []).length;
  return `Sahkan lembar ${sheet?.number || ""}? ${n} baris · total ${formatCurrency(total ?? sheet?.totals?.amount ?? 0)} · ${pt}. `
    + "Setelah disahkan, lembar tidak bisa diubah; koreksi dibuat sebagai penyesuaian di lembar berikutnya.";
}

/** "Berubah sejak dipotret: Omzet bersih −Rp 50.000.000" (uang) atau "… Realisasi harga −1,2 poin" (persen). */
export function teksBerubah(d) {
  if (!d) return "";
  const diff = d.diff;
  if (diff === null || diff === undefined) return `Berubah sejak dipotret: ${d.label} (sekarang ${d.field.endsWith("_pct") ? persen(d.current) : formatCurrency(d.current)})`;
  const tanda = diff < 0 ? "−" : "+";
  const nilai = d.field.endsWith("_pct") ? `${formatDecimal(Math.abs(diff), 1, 1)} poin` : formatCurrency(Math.abs(diff));
  return `Berubah sejak dipotret: ${d.label} ${tanda}${nilai}`;
}

/** Alasan tombol tulis mati — ditulis di samping tombol (bukan tooltip). "" = boleh. */
export function alasanLembar({ canWrite, status, canPrepare, canApprove }) {
  if (!canWrite) return "Pilih satu PT dulu.";
  if (status === "draft" && !canPrepare) return "Mengubah lembar butuh akses Siapkan lembar insentif di modul Kinerja & Insentif.";
  if (status === "submitted" && !canApprove) return "Menunggu pengesahan oleh pemegang akses Sahkan lembar insentif.";
  if (status === "approved" || status === "paid") return "Lembar sudah disahkan — koreksi dibuat sebagai baris penyesuaian di lembar berikutnya.";
  if (status === "cancelled") return "Lembar sudah dibatalkan.";
  return "";
}

/** Alasan "Ajukan" mati pada lembar draf yang boleh diubah. "" = boleh. */
export function alasanAjukan(sheet, adaPerubahan) {
  const lines = sheet?.lines || [];
  if (!lines.length) return "Tambahkan minimal satu baris sebelum mengajukan.";
  if (adaPerubahan) return "Simpan nominal dulu.";
  if (lines.some((x) => x.amount === null || x.amount === undefined)) return "Isi nominal semua baris sebelum mengajukan.";
  if (lines.some((x) => x.is_adjustment && !String(x.note || "").trim())) return "Beri catatan pada semua baris penyesuaian.";
  return "";
}

/** Pilihan periode dasar untuk jenis periode komponen (`month` · `quarter` · `year`). */
export function pilihanDasar(jenis, cur = "") {
  const bawaan = jenis === "quarter" ? "" : String(todayWib()).slice(0, jenis === "year" ? 4 : 7);
  return pilihanPeriode(jenis || "month", cur || bawaan);
}
/** Riwayat lembar: aksi → kalimat. */
export const AKSI_RIWAYAT = { create: "Dibuat", submit: "Diajukan", approve: "Disahkan", return: "Dikembalikan ke penyiap",
  cancel: "Dibatalkan", refresh: "Angka dasar disegarkan", paid: "Dibayarkan lewat gaji" };
const JENIS_DASAR = [{ value: "month", label: "Bulan" }, { value: "quarter", label: "Triwulan" }, { value: "year", label: "Tahun" }];
const RINCIAN = [["Target omzet", "target_sales", "uang"], ["Omzet", "omzet", "uang"], ["Retur", "retur", "uang"],
  ["Omzet bersih", "omzet_bersih", "uang"], ["% capaian omzet", "pct_omzet", "pct"], ["Target pencairan", "target_collection", "uang"],
  ["Uang masuk", "uang_masuk", "uang"], ["% capaian pencairan", "pct_pencairan", "pct"], ["Realisasi harga", "realisasi_harga_pct", "pct"],
  ["Di bawah harga acuan", "porsi_bawah_acuan_pct", "pct"], ["Margin", "margin_pct", "pct"]];

// ── Pop-up tambah baris / penyesuaian ───────────────────────────────────────────────────────────────────────────────
function FormBaris({ open, onClose, sheet, penyesuaian, onSaved }) {
  const [opsi, setOpsi] = useState({ sales: [], components: [] });
  const [form, setForm] = useState({});
  const [rujukan, setRujukan] = useState([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const intent = useIntentKey(penyesuaian ? "isheet-adj" : "isheet-line");
  useEffect(() => {
    if (!open) return;
    setForm({ sales_id: "", component_id: "", jenis: "month", periode: "", amount: "", note: "", ref: "" });
    setErr(""); setRujukan([]);
    axios.get(`${API}/incentive/sheets/options`).then((r) => setOpsi(r.data || { sales: [], components: [] }))
      .catch((e) => setErr(apiErrorText(e) || "Pilihan sales dan komponen gagal dimuat."));
  }, [open]);
  useEffect(() => {
    if (!open || !penyesuaian || !form.sales_id) { setRujukan([]); return; }
    axios.get(`${API}/incentive/sheets/adjustable-lines`, { params: { sales_id: form.sales_id } })
      .then((r) => setRujukan(r.data?.items || [])).catch((e) => setErr(apiErrorText(e) || "Baris rujukan gagal dimuat."));
  }, [open, penyesuaian, form.sales_id]);
  const komp = (opsi.components || []).find((c) => c.id === form.component_id);
  const jenisTetap = komp && komp.basis_period_type !== "free" ? komp.basis_period_type : "";
  const jenis = jenisTetap || form.jenis || "month";
  const ref = rujukan.find((x) => x.line_id === form.ref);
  const ubah = (p) => setForm((f) => ({ ...f, ...p }));
  const simpan = async () => {
    setErr("");
    let body;
    if (penyesuaian) {
      if (!form.sales_id || !ref) { setErr("Pilih sales dan baris lembar yang disesuaikan."); return; }
      if (!String(form.note || "").trim()) { setErr("Catatan wajib untuk baris penyesuaian."); return; }
      body = { sales_id: ref.sales_id, component_id: ref.component_id, basis_period_type: ref.basis_period_type,
        basis_period: ref.basis_period, is_adjustment: true, adjusts: { sheet_id: ref.sheet_id, line_id: ref.line_id },
        amount: form.amount === "" || form.amount === "-" ? null : Number(form.amount), note: form.note.trim() };
    } else {
      if (!form.sales_id || !form.component_id || !form.periode) { setErr("Isi sales, komponen, dan periode dasar."); return; }
      body = { sales_id: form.sales_id, component_id: form.component_id, basis_period_type: jenis, basis_period: form.periode,
        amount: form.amount === "" ? null : Number(form.amount), note: String(form.note || "").trim() };
    }
    setBusy(true);
    try {
      const r = await intent.send(body, (k) => moneyPost(`${API}/incentive/sheets/${sheet.id}/lines`, body, k));
      onSaved?.(r.data); onClose?.();
    } catch (e) { setErr(apiErrorText(e) || "Baris gagal ditambahkan."); } finally { setBusy(false); }
  };
  const salesOpts = (opsi.sales || []).map((s) => ({ value: s.id, label: s.name }));
  return (
    <FormModal open={open} onClose={onClose} title={penyesuaian ? "Tambah Baris Penyesuaian" : "Tambah Baris"}
      subtitle={`Lembar ${sheet?.number || ""} · angka dasar dipotret saat baris disimpan`} icon={penyesuaian ? Undo2 : Plus}
      testId={penyesuaian ? "isheet-adj-form" : "isheet-line-form"} onSubmit={simpan} busy={busy} error={err}
      submitLabel={penyesuaian ? "Simpan Penyesuaian" : "Simpan Baris"}>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div><label className="field-label">Sales <span className="req">*</span></label>
          <KNSelect data-testid="isheet-form-sales" value={form.sales_id || ""} className="field" options={salesOpts} searchable
            placeholder="Pilih sales" onValueChange={(v) => ubah({ sales_id: v, ref: "" })} /></div>
        {penyesuaian ? (
          <div className="sm:col-span-2"><label className="field-label">Baris yang disesuaikan <span className="req">*</span></label>
            <KNSelect data-testid="isheet-form-ref" value={form.ref || ""} className="field" placeholder="Pilih baris lembar yang sudah disahkan"
              emptyText={form.sales_id ? "Sales ini belum punya baris di lembar yang disahkan." : "Pilih sales dulu."}
              options={rujukan.map((x) => ({ value: x.line_id, label: `${x.sheet_number} · ${x.component_name} · ${x.basis_label} · ${formatCurrency(x.amount)}` }))}
              onValueChange={(v) => ubah({ ref: v })} /></div>
        ) : (
          <>
            <div><label className="field-label">Komponen <span className="req">*</span></label>
              <KNSelect data-testid="isheet-form-comp" value={form.component_id || ""} className="field" placeholder="Pilih komponen"
                emptyText="Belum ada komponen aktif. Tambahkan di tab Target & Aturan."
                options={(opsi.components || []).map((c) => ({ value: c.id, label: `${c.name} (${c.basis_label})` }))}
                onValueChange={(v) => ubah({ component_id: v, periode: "" })} /></div>
            {!jenisTetap && (
              <div><label className="field-label">Jenis periode dasar</label>
                <KNSelect data-testid="isheet-form-type" value={jenis} className="field" options={JENIS_DASAR}
                  onValueChange={(v) => ubah({ jenis: v, periode: "" })} /></div>
            )}
            <div><label className="field-label">Periode dasar <span className="req">*</span></label>
              <KNSelect data-testid="isheet-form-period" value={form.periode || ""} className="field" placeholder="Pilih periode"
                options={pilihanDasar(jenis, form.periode)} onValueChange={(v) => ubah({ periode: v })} /></div>
          </>
        )}
        <div><label className="field-label">Nominal (Rp)</label>
          <input data-testid="isheet-form-amount" className="field text-right tabular-nums" inputMode="numeric"
            value={tampilNominal(form.amount)} onChange={(e) => ubah({ amount: bacaNominal(e.target.value, penyesuaian) })}
            placeholder={penyesuaian ? "Contoh: -500.000" : "Boleh diisi nanti"} aria-label="Nominal" />
          <p className="mt-1 text-fs-12 text-kn-text-2">{penyesuaian ? "Negatif = mengurangi insentif yang sudah disahkan." : "Diketik orang; sistem tidak mengusulkan angka."}</p></div>
        <div className={penyesuaian ? "" : "sm:col-span-2"}><label className="field-label">Catatan {penyesuaian && <span className="req">*</span>}</label>
          <input data-testid="isheet-form-note" className="field" value={form.note || ""} maxLength={500}
            onChange={(e) => ubah({ note: e.target.value })} placeholder={penyesuaian ? "Contoh: retur 25 Okt" : ""} /></div>
      </div>
    </FormModal>
  );
}

// ── Rincian lembar ───────────────────────────────────────────────────────────────────────────────────────────────────
export default function IncentiveSheetDetail({ sheetId, onClose, onChanged }) {
  const { canWrite, entities } = useEntityScope();
  const canPrepare = canCurrent("incentive", "prepare");
  const canApprove = canCurrent("incentive", "approve");
  const [sheet, setSheet] = useState(null);
  const [state, setState] = useState("loading");
  const [err, setErr] = useState("");
  const [edit, setEdit] = useState({});
  const [koreksi, setKoreksi] = useState({});
  const [buka, setBuka] = useState(() => new Set());
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const [actErr, setActErr] = useState("");
  const [form, setForm] = useState("");
  const [cari, setCari] = useState("");
  const kunciSimpan = useIntentKey("isheet-save");
  const kunciAksi = useIntentKey("isheet-act");

  const load = useCallback(async () => {
    setState("loading");
    try {
      const r = await axios.get(`${API}/incentive/sheets/${sheetId}`);
      setSheet(r.data); setErr(""); setState("ready"); setEdit({}); setKoreksi({});
    } catch (e) { setErr(apiErrorText(e) || ""); setState("error"); }
  }, [sheetId]);
  useEffect(() => { if (sheetId) load(); }, [load, sheetId]);

  const terima = (data, pesan = "") => {
    setSheet((s) => ({ ...data, drift: data.drift || (s?.drift || []).filter((d) => (data.lines || []).some((x) => x.id === d.line_id)) }));
    setEdit({}); setKoreksi({}); setMsg(pesan); onChanged?.(data);
  };
  const status = sheet?.status || "draft";
  const pt = entityFullById(entities, sheet?.entity_id, "PT ini");
  const alasan = alasanLembar({ canWrite, status, canPrepare, canApprove });
  const bisaUbah = status === "draft" && !alasan;
  const bisaPutus = status === "submitted" && !alasan;
  const lines = useMemo(() => sheet?.lines || [], [sheet]);
  const drift = useMemo(() => {
    const by = {};
    (sheet?.drift || []).forEach((d) => { (by[d.line_id] = by[d.line_id] || []).push(d); });
    return by;
  }, [sheet]);
  const kotor = Object.keys(edit).filter((id) => {
    const x = lines.find((l) => l.id === id);
    if (!x) return false;
    const e = edit[id];
    const amt = e.amount === undefined ? x.amount : (e.amount === "" || e.amount === "-" ? null : Number(e.amount));
    return amt !== x.amount || (e.note !== undefined && e.note !== (x.note || ""));
  });
  const dikoreksi = Object.keys(koreksi).filter((id) => {
    const x = lines.find((l) => l.id === id);
    const v = koreksi[id]?.amount;
    return x && v !== undefined && v !== "" && v !== "-" && Number(v) !== Number(x.amount);
  });
  const totalKoreksi = lines.reduce((s, x) => s + Number(dikoreksi.includes(x.id) ? koreksi[x.id].amount : (x.amount || 0)), 0);
  const ajukanAlasan = bisaUbah ? alasanAjukan(sheet, kotor.length > 0) : "";
  const tampil = useMemo(() => {
    const qq = cari.trim().toLowerCase();
    return qq ? lines.filter((x) => `${x.sales_name} ${x.component_name} ${x.basis_label}`.toLowerCase().includes(qq)) : lines;
  }, [lines, cari]);
  const togel = (id) => setBuka((b) => { const n = new Set(b); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  const jalan = async (nama, fn) => {
    setBusy(nama); setActErr(""); setMsg("");
    try { await fn(); } catch (e) { setActErr(apiErrorText(e) || "Aksi gagal."); } finally { setBusy(""); }
  };
  const simpanNominal = () => jalan("simpan", async () => {
    let data = sheet;
    for (const id of kotor) {
      const x = lines.find((l) => l.id === id);
      const e = edit[id];
      const body = {};
      if (e.amount !== undefined) body.amount = e.amount === "" || e.amount === "-" ? null : Number(e.amount);
      if (e.note !== undefined) body.note = e.note;
      const r = await kunciSimpan.send({ id, ...body }, (k) => moneyPatch(`${API}/incentive/sheets/${sheet.id}/lines/${x.id}`, body, k));
      data = r.data;
    }
    terima(data, `${kotor.length} nominal tersimpan.`);
  });
  const aksi = (nama, path, body, pesan) => jalan(nama, async () => {
    const r = await kunciAksi.send({ nama, path, body }, (k) => moneyPost(`${API}/incentive/sheets/${sheet.id}/${path}`, body, k));
    // segarkan menjawab `{changed, sheet}`: potret kini = angka terbaru, jadi tidak ada lagi yang "berubah sejak dipotret"
    const data = r.data?.sheet ? { ...r.data.sheet, drift: [] } : r.data;
    terima(data, typeof pesan === "function" ? pesan(r.data) : pesan);
  });
  const segarkan = () => aksi("segarkan", "refresh", {}, (d) => {
    const n = (d?.changed || []).length;
    return n ? `${n} baris berubah — potret mengikuti angka terbaru.` : "Tidak ada angka dasar yang berubah.";
  });
  const ajukan = async () => {
    const ok = await askConfirm({ title: `Ajukan lembar ${sheet.number}?`,
      message: `${lines.length} baris · total ${formatCurrency(sheet.totals?.amount || 0)} · ${pt}. Sesudah diajukan, nominal tidak bisa diubah kecuali lembar dikembalikan pemutus.`,
      confirmLabel: "Ajukan" });
    if (ok) aksi("ajukan", "submit", {}, "Lembar diajukan untuk disahkan.");
  };
  const sahkan = async () => {
    const tanpaCatatan = dikoreksi.filter((id) => !String(koreksi[id]?.note || "").trim());
    if (tanpaCatatan.length) { setActErr("Beri catatan untuk setiap nominal yang dikoreksi."); return; }
    const ok = await askConfirm({ title: `Sahkan lembar ${sheet.number}?`, message: teksKonfirmasiSahkan(sheet, pt, totalKoreksi),
      confirmLabel: "Sahkan" });
    if (!ok) return;
    const corrections = dikoreksi.map((id) => ({ line_id: id, amount: Number(koreksi[id].amount), note: koreksi[id].note.trim() }));
    aksi("sahkan", "approve", { corrections }, "Lembar disahkan.");
  };
  const kembalikan = async () => {
    const reason = await askReason({ title: `Kembalikan lembar ${sheet.number}?`,
      message: "Lembar kembali menjadi draf supaya penyiap bisa memperbaikinya.", confirmLabel: "Kembalikan" });
    if (reason) aksi("kembalikan", "return", { reason }, "Lembar dikembalikan ke penyiap.");
  };
  const batalkan = async () => {
    const reason = await askReason({ title: `Batalkan lembar ${sheet.number}?`,
      message: "Lembar draf dibatalkan dan tidak dipakai lagi. Baris yang sama bisa dibuat di lembar lain.", confirmLabel: "Batalkan lembar",
      danger: true });
    if (reason) aksi("batalkan", "cancel", { reason }, "Lembar dibatalkan.");
  };
  const hapusBaris = async (x) => {
    const ok = await askConfirm({ title: "Hapus baris ini?", message: `${x.sales_name} · ${x.component_name} · ${x.basis_label}`,
      confirmLabel: "Hapus baris", danger: true });
    if (!ok) return;
    jalan("hapus", async () => {
      const r = await kunciAksi.send({ hapus: x.id }, (k) => moneyDelete(`${API}/incentive/sheets/${sheet.id}/lines/${x.id}`, k));
      terima(r.data, "Baris dihapus.");
    });
  };
  const ekspor = () => jalan("ekspor", async () => {
    const r = await axios.get(`${API}/incentive/sheets/${sheet.id}/export`, { responseType: "blob" });
    const m = /filename="([^"]+)"/.exec(String(r.headers?.["content-disposition"] || ""));
    const url = URL.createObjectURL(r.data);
    const a = document.createElement("a");
    a.href = url; a.download = m ? m[1] : `lembar-insentif-${todayWib()}.xlsx`; a.click();
    URL.revokeObjectURL(url);
  });

  const nilaiEdit = (x) => (edit[x.id]?.amount !== undefined ? edit[x.id].amount : (x.amount ?? ""));
  const catatanEdit = (x) => (edit[x.id]?.note !== undefined ? edit[x.id].note : (x.note || ""));
  const ubahEdit = (x, p) => setEdit((e) => ({ ...e, [x.id]: { ...(e[x.id] || {}), ...p } }));
  const ubahKoreksi = (x, p) => setKoreksi((k) => ({ ...k, [x.id]: { ...(k[x.id] || {}), ...p } }));

  return (
    <DetailModal open onClose={onClose} size="xl" label={`Lembar insentif ${sheet?.number || ""}`} testId="isheet-modal" showClose={false}>
      <div className="section-card flex max-h-[calc(100dvh-2rem)] flex-col" data-testid="isheet-detail">
        <div className="section-head">
          <h2 className="min-w-0 break-words" data-testid="isheet-title">Lembar insentif {sheet?.number || ""}</h2>
          <button type="button" className="icon-button" aria-label="Tutup" title="Tutup (Esc)" data-testid="isheet-close" onClick={onClose}>
            <X size={16} aria-hidden="true" /></button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {state === "loading" ? (
            <div className="section-pad text-fs-13 text-kn-text-2" role="status" data-testid="isheet-loading">Memuat lembar insentif…</div>
          ) : state === "error" ? (
            <div className="section-pad"><ErrorNotice testId="isheet-error" message={`Lembar insentif gagal dimuat. ${err}`.trim()} onRetry={load} /></div>
          ) : (
            <>
              <div className="section-body space-y-3">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-fs-13" data-testid="isheet-meta">
                  <StatusLembar status={status} testId="isheet-status" />
                  <span>{pt}</span>
                  <span>Periode bayar <b>{formatPeriod(sheet.pay_period)}</b></span>
                  {sheet.title && <span className="break-words">{sheet.title}</span>}
                  <span className="text-kn-text-2">Penyiap {sheet.prepared_by?.name || "—"}{sheet.approved_by?.name ? ` · Pemutus ${sheet.approved_by.name}` : ""}</span>
                </div>
                <p className="text-fs-14 font-semibold tabular-nums" data-testid="isheet-total">
                  {lines.length} baris · total {formatCurrency(sheet.totals?.amount || 0)}
                  {dikoreksi.length > 0 && <span className="ml-2 text-fs-13 font-normal text-kn-warning-text">setelah koreksi {formatCurrency(totalKoreksi)}</span>}
                </p>
                <div className="flex flex-wrap items-center gap-2" data-testid="isheet-actions">
                  {status === "draft" && (
                    <>
                      <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="isheet-add" disabled={!bisaUbah || !!busy} onClick={() => setForm("baris")}>
                        <Plus size={13} aria-hidden="true" /> Tambah baris</button>
                      <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="isheet-add-adj" disabled={!bisaUbah || !!busy} onClick={() => setForm("penyesuaian")}>
                        <Undo2 size={13} aria-hidden="true" /> Tambah penyesuaian</button>
                      <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="isheet-refresh" disabled={!bisaUbah || !!busy || !lines.length} onClick={segarkan}>
                        <RefreshCw size={13} aria-hidden="true" /> Segarkan angka dasar</button>
                      {kotor.length > 0 && (
                        <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="isheet-save" disabled={!!busy} onClick={simpanNominal}>
                          {busy === "simpan" ? "Menyimpan…" : `Simpan nominal (${kotor.length})`}</button>)}
                      <button type="button" className="primary-button btn-sm whitespace-nowrap" data-testid="isheet-submit" disabled={!bisaUbah || !!busy || !!ajukanAlasan} onClick={ajukan}>
                        <Send size={13} aria-hidden="true" /> Ajukan</button>
                      <button type="button" className="danger-button btn-sm whitespace-nowrap" data-testid="isheet-cancel" disabled={!bisaUbah || !!busy} onClick={batalkan}>
                        <Ban size={13} aria-hidden="true" /> Batalkan</button>
                    </>
                  )}
                  {status === "submitted" && (
                    <>
                      <button type="button" className="primary-button btn-sm whitespace-nowrap" data-testid="isheet-approve" disabled={!bisaPutus || !!busy} onClick={sahkan}>
                        <CheckCircle2 size={13} aria-hidden="true" /> Sahkan</button>
                      <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="isheet-return" disabled={!bisaPutus || !!busy} onClick={kembalikan}>
                        <Undo2 size={13} aria-hidden="true" /> Kembalikan</button>
                    </>
                  )}
                  <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="isheet-export" disabled={!!busy} onClick={ekspor}>
                    <Download size={13} aria-hidden="true" /> {busy === "ekspor" ? "Mengekspor…" : "Ekspor Excel"}</button>
                  {alasan && <span className="text-fs-12 text-kn-text-2" data-testid="isheet-why">{alasan}</span>}
                  {!alasan && ajukanAlasan && <span className="text-fs-12 text-kn-text-2" data-testid="isheet-submit-why">{ajukanAlasan}</span>}
                  {bisaPutus && <span className="text-fs-12 text-kn-text-2" data-testid="isheet-correct-hint">Ubah nominal di tabel untuk mengoreksi; catatan wajib.</span>}
                </div>
                {msg && <div className="notice-bar success" role="status" data-testid="isheet-msg"><span className="text-fs-12">{msg}</span></div>}
                {actErr && <ErrorNotice testId="isheet-act-error" message={actErr} />}
              </div>
              {lines.length === 0 ? (
                <div className="section-pad text-center text-fs-13 text-kn-text-2" data-testid="isheet-empty">
                  Belum ada baris. {bisaUbah ? "Tambah baris untuk tiap sales dan komponen yang diputuskan." : ""}</div>
              ) : (
                <>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-3 pb-2">
                    <label className="relative block w-full max-w-[260px]">
                      <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-kn-text-2" aria-hidden="true" />
                      <input data-testid="isheet-search" className="field pl-7" placeholder="Cari sales atau komponen" aria-label="Cari sales atau komponen"
                        value={cari} onChange={(e) => setCari(e.target.value)} />
                    </label>
                    <span className="text-fs-12 text-kn-text-2" data-testid="isheet-count">{tampil.length} dari {lines.length} baris</span>
                  </div>
                  <p className="px-3 pb-1 text-fs-12 text-kn-text-2">Angka dasar dalam rupiah, dipotret saat baris dibuat · klik nama sales untuk rincian potret.</p>
                  <div className="overflow-x-auto">
                    <table className="data-table head-wrap w-full" data-testid="isheet-table">
                      <thead><tr>
                        <th className="min-w-[120px]">Sales</th><th className="min-w-[100px]">Komponen</th><th>Periode dasar</th>
                        <th className="text-right">Omzet / target</th><th className="text-right">Cair / target</th>
                        <th className="text-right">Realisasi harga</th><th className="text-right min-w-[128px]">Nominal</th><th className="min-w-[128px]">Catatan</th>
                      </tr></thead>
                      <tbody>
                        {tampil.map((x) => {
                          const s = x.snapshot || {};
                          const terbuka = buka.has(x.id);
                          const dr = drift[x.id] || [];
                          return [
                            <tr key={x.id} data-testid={`isheet-row-${x.id}`}>
                              <td className="break-words">
                                <button type="button" className="link-button flex items-start gap-1 text-left" aria-expanded={terbuka}
                                  data-testid={`isheet-toggle-${x.id}`} onClick={() => togel(x.id)}>
                                  {terbuka ? <ChevronDown size={14} className="mt-0.5 shrink-0" aria-hidden="true" /> : <ChevronRight size={14} className="mt-0.5 shrink-0" aria-hidden="true" />}
                                  <span>{x.sales_name}</span></button>
                                {dr.length > 0 && <span className="flex items-center gap-1 text-fs-12 text-kn-warning-text" data-testid={`isheet-drift-flag-${x.id}`}>
                                  <AlertTriangle size={11} aria-hidden="true" />Berubah sejak dipotret</span>}
                              </td>
                              <td className="break-words">{x.component_name}
                                {x.is_adjustment && <span className="block text-fs-12 text-kn-special-text">Penyesuaian atas {x.adjusts?.sheet_number || "—"}</span>}</td>
                              <td className="whitespace-nowrap">{x.basis_label}</td>
                              <td className="text-right tabular-nums">{angka(s.omzet_bersih)}<span className="block text-fs-12 text-kn-text-2">/ {s.target_sales ? angka(s.target_sales) : "—"}</span></td>
                              <td className="text-right tabular-nums">{angka(s.uang_masuk)}<span className="block text-fs-12 text-kn-text-2">/ {s.target_collection ? angka(s.target_collection) : "—"}</span></td>
                              <td className="text-right tabular-nums">{persen(s.realisasi_harga_pct)}</td>
                              <td className="text-right">
                                {bisaUbah ? (
                                  <input className="field w-32 text-right tabular-nums" inputMode="numeric" data-testid={`isheet-amount-${x.id}`}
                                    aria-label={`Nominal ${x.sales_name} ${x.component_name} ${x.basis_label}`} placeholder="Ketik nominal"
                                    value={tampilNominal(nilaiEdit(x))} onChange={(e) => ubahEdit(x, { amount: bacaNominal(e.target.value, x.is_adjustment) })} />
                                ) : bisaPutus ? (
                                  <input className="field w-32 text-right tabular-nums" inputMode="numeric" data-testid={`isheet-correct-${x.id}`}
                                    aria-label={`Koreksi nominal ${x.sales_name} ${x.component_name} ${x.basis_label}`}
                                    value={tampilNominal(koreksi[x.id]?.amount !== undefined ? koreksi[x.id].amount : x.amount)}
                                    onChange={(e) => ubahKoreksi(x, { amount: bacaNominal(e.target.value, x.is_adjustment) })} />
                                ) : (
                                  <span className="tabular-nums whitespace-nowrap" data-testid={`isheet-amount-text-${x.id}`}>{x.amount === null || x.amount === undefined ? "—" : formatCurrency(x.amount)}</span>
                                )}
                                {x.amount_prepared !== undefined && x.amount_prepared !== null && x.amount_prepared !== x.amount && (
                                  <span className="block text-fs-12 text-kn-text-2 whitespace-nowrap">penyiap {formatCurrency(x.amount_prepared)}</span>)}
                              </td>
                              <td className="break-words">
                                {bisaUbah ? (
                                  <input className="field w-full min-w-[120px]" data-testid={`isheet-note-${x.id}`} maxLength={500}
                                    aria-label={`Catatan ${x.sales_name}`} value={catatanEdit(x)} placeholder={x.is_adjustment ? "Wajib" : ""}
                                    onChange={(e) => ubahEdit(x, { note: e.target.value })} />
                                ) : bisaPutus && dikoreksi.includes(x.id) ? (
                                  <input className="field w-full min-w-[120px]" data-testid={`isheet-correct-note-${x.id}`} maxLength={500}
                                    aria-label={`Catatan koreksi ${x.sales_name}`} placeholder="Catatan koreksi (wajib)"
                                    value={koreksi[x.id]?.note || ""} onChange={(e) => ubahKoreksi(x, { note: e.target.value })} />
                                ) : (
                                  <>{x.note || <span className="text-kn-text-2">—</span>}
                                    {x.approver_note && <span className="block text-fs-12 text-kn-text-2">Catatan pemutus: {x.approver_note}</span>}</>
                                )}
                              </td>
                            </tr>,
                            terbuka && (
                              <tr key={`${x.id}-rinci`} className="bg-kn-neutral-soft" data-testid={`isheet-rinci-${x.id}`}>
                                <td colSpan={8}>
                                  <div className="space-y-2">
                                    <p className="text-fs-12 text-kn-text-2" data-testid={`isheet-taken-${x.id}`}>
                                      Dipotret {formatDateTime(s.taken_at)} · definisi versi {s.definition_version ?? "—"} · periode {x.basis_label}</p>
                                    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-4">
                                      {RINCIAN.filter(([, f]) => f !== "margin_pct" || s.margin_pct !== undefined).map(([lbl, f, jenis]) => (
                                        <div key={f}><dt className="text-fs-12 text-kn-text-2">{lbl}</dt>
                                          <dd className="text-fs-13 tabular-nums">{jenis === "pct" ? persen(s[f]) : formatCurrency(s[f] || 0)}</dd></div>))}
                                    </dl>
                                    {(s.catatan_data || []).length > 0 && (
                                      <ul className="text-fs-12 text-kn-warning-text">{s.catatan_data.map((c) => <li key={c.code}>{c.text}</li>)}</ul>)}
                                    {dr.map((d) => (
                                      <div key={d.field} className="notice-bar warning" data-testid={`isheet-drift-${x.id}-${d.field}`}>
                                        <AlertTriangle size={14} aria-hidden="true" /><span className="text-fs-12">{teksBerubah(d)} — bahan baris penyesuaian, potret tidak berubah.</span></div>))}
                                    {bisaUbah && (
                                      <button type="button" className="danger-button btn-sm whitespace-nowrap" data-testid={`isheet-del-${x.id}`} disabled={!!busy} onClick={() => hapusBaris(x)}>
                                        <Trash2 size={13} aria-hidden="true" /> Hapus baris</button>)}
                                  </div>
                                </td>
                              </tr>
                            ),
                          ];
                        })}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
              {(sheet.history || []).length > 0 && (
                <div className="section-body border-t border-kn-divider" data-testid="isheet-history">
                  <p className="text-fs-12 font-semibold text-kn-text">Riwayat</p>
                  <ul className="mt-1 space-y-0.5 text-fs-12 text-kn-text-2">
                    {sheet.history.slice().reverse().slice(0, 12).map((h, i) => (
                      <li key={`${h.at}-${i}`}>{formatDateTime(h.at)} · {h.by_name || "—"} · {AKSI_RIWAYAT[h.action] || labelStatusLembar(h.to_status)}{h.reason ? ` — ${h.reason}` : ""}</li>))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      </div>
      <FormBaris open={form === "baris"} onClose={() => setForm("")} sheet={sheet} penyesuaian={false} onSaved={(d) => terima(d, "Baris ditambahkan dan angka dasarnya dipotret.")} />
      <FormBaris open={form === "penyesuaian"} onClose={() => setForm("")} sheet={sheet} penyesuaian onSaved={(d) => terima(d, "Baris penyesuaian ditambahkan.")} />
    </DetailModal>
  );
}
