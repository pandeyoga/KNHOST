/**
 * FundTransferForm — Kas & Bank bagian 1 (Tugas 6): satu pop-up `FormModal` "Pindah Dana" (spesifikasi §5.2, §5.4).
 *
 * Rekening asal & tujuan dari `GET /api/bank-accounts?entity_id=` (rekening aktif PT di kepala aplikasi), nominal,
 * biaya transfer (dibebankan ke rekening asal), tanggal kirim, tanggal terima (kosong = sekali jalan; lebih akhir =
 * dana dalam perjalanan, dicatat Terima belakangan), catatan. Ringkasan di atas tombol kirim menyebut nominal, biaya,
 * rekening, dan PT (`02_STANDAR` N5) — tidak ada pop-up kedua. Kirim `POST /api/fund-transfers` lewat `moneyPost` +
 * `useIntentKey` (awalan `/api/fund-transfers` berkunci idempotensi, N4). Galat server tampil di dalam pop-up.
 */
import { useEffect, useMemo, useState } from "react";
import { ArrowRightLeft } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import FormModal from "../../../components/FormModal";
import KNSelect from "../../../components/KNSelect";
import KNDatePicker from "../../../components/KNDatePicker";
import MoneyInput from "@/components/MoneyInput";
import EntityScopeBanner from "../../../components/EntityScopeBanner";
import useIntentKey from "../../../hooks/useIntentKey";
import { moneyPost } from "../../../utils/moneyRequest";
import { apiErrorText } from "../../../utils/apiError";
import { formatCurrency, formatDate, todayWib } from "../../../utils/formatters";
import { badanPindahDana, labelRekening, validasiPindahDana } from "./fundTransferShared";

const KOSONG = { rekening_asal_id: "", rekening_tujuan_id: "", nominal: "", biaya: "", tanggal_kirim: "",
  tanggal_terima: "", catatan: "" };

export default function FundTransferForm({ open, onClose, onSaved, entityId, entityLabel = "" }) {
  const [form, setForm] = useState(KOSONG);
  const [rekening, setRekening] = useState([]);
  const [muat, setMuat] = useState("memuat");   // memuat | siap | galat
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const intent = useIntentKey("pdn");
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  useEffect(() => {
    if (!open) return undefined;
    let hidup = true;
    setForm({ ...KOSONG, tanggal_kirim: todayWib() });
    setErr("");
    setMuat("memuat");
    axios.get(`${API}/bank-accounts`, { params: { entity_id: entityId } })
      .then((r) => {
        if (!hidup) return;
        const list = (Array.isArray(r.data) ? r.data : []).filter((a) => a.is_active !== false && a.entity_id === entityId);
        setRekening(list);
        setMuat("siap");
      })
      .catch((e) => { if (hidup) { setRekening([]); setMuat("galat"); setErr(apiErrorText(e, "Rekening PT ini belum bisa dimuat.")); } });
    return () => { hidup = false; };
  }, [open, entityId]);

  const opsi = useMemo(() => rekening.map((a) => ({
    value: a.id, label: `${labelRekening(a)} · saldo ${formatCurrency(a.balance)}` })), [rekening]);
  const nama = (id) => rekening.find((a) => a.id === id)?.name || "";
  const nominal = Number(form.nominal) || 0;
  const biaya = Number(form.biaya) || 0;
  const duaTahap = Boolean(form.tanggal_terima) && form.tanggal_terima > (form.tanggal_kirim || "");
  const siap = form.rekening_asal_id && form.rekening_tujuan_id && nominal > 0;

  async function simpan() {
    if (busy) return;
    const salah = validasiPindahDana(form);
    if (salah) { setErr(salah); return; }
    setBusy(true);
    setErr("");
    const body = badanPindahDana(form, entityId);
    try {
      const r = await intent.send(body, (k) => moneyPost(`${API}/fund-transfers`, body, k));
      onSaved?.(r.data);
    } catch (e) {
      setErr(apiErrorText(e, "Pindah Dana belum bisa dicatat."));
    } finally { setBusy(false); }
  }

  return (
    <FormModal open={open} onClose={onClose} title="Pindah Dana" icon={ArrowRightLeft} size="md" testId="ft-form"
      subtitle={`Pindah uang antar rekening ${entityLabel || "PT ini"} — setor tunai, isi kas kecil, antar bank.`}
      onSubmit={simpan} submitLabel="Pindahkan dana" submitTestId="ft-form-submit" cancelTestId="ft-form-cancel"
      busy={busy} error={err} submitDisabled={muat !== "siap" || rekening.length < 2}>
      <div className="grid gap-3">
        <EntityScopeBanner variant="form" testId="ft-form-scope" className="" />
        {muat === "siap" && rekening.length < 2 && (
          <p className="text-fs-12 text-kn-text-2" data-testid="ft-form-no-accounts">
            Pindah Dana butuh dua rekening aktif di PT ini. Tambahkan rekening di Rekening &amp; Saldo.
          </p>
        )}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="field-label">Dari rekening <span className="req">*</span></label>
            <KNSelect data-testid="ft-form-from" className="field" value={form.rekening_asal_id} placeholder="Pilih rekening asal"
              options={opsi} onValueChange={(v) => set({ rekening_asal_id: v,
                ...(v && v === form.rekening_tujuan_id ? { rekening_tujuan_id: "" } : {}) })} />
          </div>
          <div>
            <label className="field-label">Ke rekening <span className="req">*</span></label>
            <KNSelect data-testid="ft-form-to" className="field" value={form.rekening_tujuan_id} placeholder="Pilih rekening tujuan"
              options={opsi.filter((o) => o.value !== form.rekening_asal_id)} onValueChange={(v) => set({ rekening_tujuan_id: v })} />
          </div>
          <div>
            <label className="field-label">Nominal (Rp) <span className="req">*</span></label>
            <MoneyInput testId="ft-form-amount" value={form.nominal} onChange={(v) => set({ nominal: v })} placeholder="0" />
          </div>
          <div>
            <label className="field-label">Biaya transfer (Rp)</label>
            <MoneyInput testId="ft-form-fee" value={form.biaya} onChange={(v) => set({ biaya: v })} placeholder="0" />
            <p className="mt-1 text-fs-12 text-kn-text-2">Dipotong dari rekening asal, dicatat sebagai beban bank.</p>
          </div>
          <div>
            <label className="field-label">Tanggal kirim</label>
            <KNDatePicker data-testid="ft-form-send-date" value={form.tanggal_kirim} clearable={false}
              onChange={(v) => set({ tanggal_kirim: v, ...(form.tanggal_terima && v && form.tanggal_terima < v ? { tanggal_terima: "" } : {}) })} />
          </div>
          <div>
            <label className="field-label">Tanggal terima</label>
            <KNDatePicker data-testid="ft-form-receive-date" value={form.tanggal_terima} min={form.tanggal_kirim}
              placeholder="Sama dengan tanggal kirim" onChange={(v) => set({ tanggal_terima: v })} />
            <p className="mt-1 text-fs-12 text-kn-text-2">
              Kosongkan bila uang sampai hari itu juga. Isi bila uang tiba belakangan — catat Terima saat dana masuk.
            </p>
          </div>
        </div>
        <div>
          <label className="field-label">Catatan</label>
          <input data-testid="ft-form-note" className="field" maxLength={500} value={form.catatan}
            onChange={(e) => set({ catatan: e.target.value })} placeholder="mis. Setor tunai hasil toko ke BCA" />
        </div>
        {siap && (
          <p className="rounded-md border border-kn-divider px-3 py-2 text-fs-13 text-kn-text" data-testid="ft-form-summary">
            <b className="tabular-nums">{formatCurrency(nominal)}</b> dipindah dari <b>{nama(form.rekening_asal_id)}</b> ke{" "}
            <b>{nama(form.rekening_tujuan_id)}</b> di {entityLabel || "PT ini"}
            {biaya > 0 ? <>; biaya transfer <b className="tabular-nums">{formatCurrency(biaya)}</b> dibebankan ke rekening asal</> : null}.
            {duaTahap ? ` Dana dalam perjalanan sampai diterima ${formatDate(form.tanggal_terima)}.` : ""}
          </p>
        )}
      </div>
    </FormModal>
  );
}
