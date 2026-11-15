/**
 * IntercoChargesPanel — KM-T4 (K-26) · **Tagihan insentif antar-PT** (bagian tab Antar-PT › Pinjaman Antar-PT).
 *
 * Sales yang menjual di PT lain dibayar gaji PT induknya. Saat gaji PT induk diposting, insentif dari Lembar Insentif PT
 * lain menjadi tagihan: PT penagih (yang menggaji) menagih PT tertagih (pemilik lembar). Tagihan lahir dari posting gaji,
 * bukan dari layar ini; di sini tagihan dibaca dan pelunasannya dicatat (`interco.settle`, pelaku bertugas di PT tertagih).
 *
 * Tabel 7 kolom (Nomor · Dari PT · Kepada PT · Nominal · Sisa · Status · Aksi): ±750 px isi + bantalan pada kartu 1024 px
 * (±760) untuk nominal sampai 9 digit; lebih lebar → tabel bergeser dan kolom aksi menempel (`col-sticky-end`). Judul kolom
 * boleh dua baris (`head-wrap`), angka uang tanpa "Rp" (keterangan di judul), status = ikon + teks + warna. Pelunasan:
 * pop-up baku `FormModal` (nominal, tanggal `KNDatePicker`, rekening kedua PT) + konfirmasi yang menyebut nominal dan kedua
 * PT (N5); kirim lewat `moneyPost` + `useIntentKey` (N4).
 */
import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Clock, HandCoins, Search, Wallet, XCircle } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import FormModal from "../../../components/FormModal";
import KNSelect from "../../../components/KNSelect";
import KNDatePicker from "../../../components/KNDatePicker";
import KNPager from "../../../components/KNPager";
import MoneyInput from "../../../components/MoneyInput";
import ErrorNotice from "../../../components/ErrorNotice";
import useIntentKey from "../../../hooks/useIntentKey";
import { moneyPost } from "../../../utils/moneyRequest";
import { askConfirm } from "../../../services/confirmService";
import { apiErrorText } from "../../../utils/apiError";
import { canCurrent } from "../../../config/roles";
import { formatCurrency, todayWib } from "../../../utils/formatters";

/** Status tagihan = ikon + teks + warna, kelas `status-*` yang ADA di `styles/components.css`. */
export const STATUS_TAGIHAN = {
  pending: { cls: "status-pending", Icon: Clock, label: "Menunggu jurnal gaji" },
  open: { cls: "status-shipped", Icon: Wallet, label: "Belum lunas" },
  settled: { cls: "status-done", Icon: CheckCircle2, label: "Lunas" },
  cancelled: { cls: "status-cancelled", Icon: XCircle, label: "Dibatalkan" },
};
const PILIHAN_STATUS = [{ value: "", label: "Semua status" },
  ...Object.entries(STATUS_TAGIHAN).map(([value, m]) => ({ value, label: m.label }))];
const UKURAN = 25;

export const angkaRp = (v) => Math.round(Number(v || 0)).toLocaleString("id-ID");

/** Kalimat konfirmasi pelunasan (N5): nominal dan kedua PT. */
export function teksKonfirmasiLunas(c, nominal) {
  return `Catat pelunasan ${formatCurrency(nominal)} untuk tagihan ${c?.number || ""}: kas keluar dari `
    + `${c?.to_entity_name || "PT tertagih"} dan masuk ke ${c?.from_entity_name || "PT penagih"}. Jurnal terbit di buku kedua PT.`;
}

/** Alasan tombol "Catat pelunasan" mati (ditulis di samping, bukan tooltip). "" = boleh. */
export function alasanLunas(c, { canSettle, allowed }) {
  if (c?.status !== "open") return "";
  if (!canSettle) return "Butuh akses Catat pelunasan antar-PT.";
  if (allowed && !allowed.includes(c.to_entity_id)) return `Dicatat oleh ${c.to_entity_name || "PT tertagih"}.`;
  return "";
}

export function StatusTagihan({ status, testId }) {
  const m = STATUS_TAGIHAN[status] || STATUS_TAGIHAN.open;
  const { Icon } = m;
  return (
    <span className={`status-pill ${m.cls} inline-flex items-center gap-1 whitespace-nowrap`} data-testid={testId}>
      <Icon size={12} aria-hidden="true" />{m.label}
    </span>
  );
}

function FormLunas({ charge, onClose, onDone }) {
  const [amount, setAmount] = useState(String(charge?.outstanding || ""));
  const [date, setDate] = useState(todayWib());
  const [akunDari, setAkunDari] = useState({ list: [], id: "" });
  const [akunKe, setAkunKe] = useState({ list: [], id: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const intent = useIntentKey("icc-lunas");
  useEffect(() => {
    let hidup = true;
    const muat = (eid, set) => axios.get(`${API}/bank-accounts`, { params: { entity_id: eid } }).then((b) => {
      if (!hidup) return;
      const list = (Array.isArray(b.data) ? b.data : []).filter((a) => a.entity_id === eid && a.is_active !== false
        && a.status !== "inactive" && a.cash_type !== "kas_kecil");
      set({ list, id: list[0]?.id || "" });
    }).catch(() => { if (hidup) set({ list: [], id: "" }); });
    muat(charge.to_entity_id, setAkunDari);
    muat(charge.from_entity_id, setAkunKe);
    return () => { hidup = false; };
  }, [charge]);
  const nominal = Number(amount || 0);
  const kirim = async () => {
    if (!(nominal > 0)) { setErr("Isi nominal pelunasan."); return; }
    if (nominal > Number(charge.outstanding || 0)) { setErr(`Nominal melebihi sisa tagihan (${formatCurrency(charge.outstanding)}).`); return; }
    const ok = await askConfirm({ title: `Catat pelunasan ${charge.number}?`, message: teksKonfirmasiLunas(charge, nominal),
      confirmLabel: "Catat pelunasan" });
    if (!ok) return;
    setBusy(true); setErr("");
    const body = { amount: nominal, date, account_id_from: akunDari.id, account_id_to: akunKe.id };
    try {
      const r = await intent.send({ id: charge.id, ...body }, (k) => moneyPost(`${API}/interco/charges/${charge.id}/settle`, body, k));
      onDone(r.data);
    } catch (e) { setErr(apiErrorText(e) || "Pelunasan gagal dicatat."); } finally { setBusy(false); }
  };
  const opsi = (list) => list.map((a) => ({ value: a.id, label: `${a.name}${a.account_number ? ` · ${a.account_number}` : ""}` }));
  return (
    <FormModal open onClose={onClose} title={`Catat pelunasan ${charge.number}`} icon={HandCoins} testId="icc-settle-form"
      subtitle={`${charge.to_entity_name} membayar ${charge.from_entity_name} · sisa ${formatCurrency(charge.outstanding)}`}
      onSubmit={kirim} submitLabel="Catat pelunasan" busy={busy} error={err}>
      <div className="grid gap-3 sm:grid-cols-2">
        <div><label className="field-label">Nominal (Rp) <span className="req">*</span></label>
          <MoneyInput testId="icc-settle-amount" className="field" value={amount} onChange={(v) => setAmount(String(v ?? ""))} /></div>
        <div><label className="field-label">Tanggal bayar <span className="req">*</span></label>
          <KNDatePicker value={date} onChange={setDate} clearable={false} data-testid="icc-settle-date" /></div>
        <div><label className="field-label">Rekening {charge.to_entity_name} (keluar)</label>
          {akunDari.list.length ? (
            <KNSelect data-testid="icc-settle-from" className="field" value={akunDari.id} options={opsi(akunDari.list)}
              onValueChange={(v) => setAkunDari((s) => ({ ...s, id: v }))} />
          ) : <p className="text-fs-12 text-kn-text-2" data-testid="icc-settle-from-auto">Rekening Bank utama PT ini dipakai.</p>}</div>
        <div><label className="field-label">Rekening {charge.from_entity_name} (masuk)</label>
          {akunKe.list.length ? (
            <KNSelect data-testid="icc-settle-to" className="field" value={akunKe.id} options={opsi(akunKe.list)}
              onValueChange={(v) => setAkunKe((s) => ({ ...s, id: v }))} />
          ) : <p className="text-fs-12 text-kn-text-2" data-testid="icc-settle-to-auto">Rekening Bank utama PT ini dipakai.</p>}</div>
      </div>
    </FormModal>
  );
}

export default function IntercoChargesPanel({ entityId = "", allowedEntityIds = null, focusId = "" }) {
  const [data, setData] = useState({ items: [], total: 0, outstanding_total: 0 });
  const [state, setState] = useState("loading");
  const [err, setErr] = useState("");
  const [status, setStatus] = useState("");
  const [cari, setCari] = useState("");
  const [page, setPage] = useState(1);
  const [lunas, setLunas] = useState(null);
  const [msg, setMsg] = useState("");
  const canSettle = canCurrent("interco", "settle");

  const load = useCallback(async () => {
    setState("loading");
    try {
      const params = { page, page_size: UKURAN, ...(status ? { status } : {}), ...(cari.trim() ? { q: cari.trim() } : {}),
        ...(entityId && entityId !== "all" ? { entity_id: entityId } : {}) };
      const r = await axios.get(`${API}/interco/charges`, { params });
      setData(r.data || { items: [], total: 0 }); setErr(""); setState("ready");
    } catch (e) { setErr(apiErrorText(e) || ""); setState("error"); }
  }, [page, status, cari, entityId]);
  useEffect(() => { load(); }, [load]);

  const items = data.items || [];
  return (
    <section className="section-card" data-testid="icc-panel">
      <div className="section-head"><h3>Tagihan insentif antar-PT</h3></div>
      <div className="section-body space-y-3">
        <p className="text-fs-12 text-kn-text-2">
          Insentif sales yang dibayar gaji PT induknya untuk Lembar Insentif PT lain. Tagihan lahir saat gaji PT induk
          diposting; PT pemilik lembar melunasinya. Sisanya termasuk saldo non-dagang dan dieliminasi di Konsolidasi Grup.
        </p>
        <div className="flex flex-wrap items-center gap-2" data-testid="icc-toolbar">
          <label className="relative block w-full max-w-[240px]">
            <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-kn-text-2" aria-hidden="true" />
            <input className="field pl-7" data-testid="icc-search" placeholder="Cari nomor tagihan atau gaji" aria-label="Cari nomor tagihan atau gaji"
              value={cari} onChange={(e) => { setCari(e.target.value); setPage(1); }} />
          </label>
          <div className="w-full max-w-[200px]"><KNSelect data-testid="icc-status-filter" className="field" value={status}
            options={PILIHAN_STATUS} onValueChange={(v) => { setStatus(v); setPage(1); }} /></div>
          <span className="text-fs-12 text-kn-text-2" data-testid="icc-count">{items.length} dari {data.total || 0} tagihan
            {data.outstanding_total ? ` · sisa terbuka ${formatCurrency(data.outstanding_total)}` : ""}</span>
        </div>
        {msg && <div className="notice-bar success" role="status" data-testid="icc-msg"><span className="text-fs-12">{msg}</span></div>}
        {state === "loading" ? (
          <div className="section-pad text-fs-13 text-kn-text-2" role="status" data-testid="icc-loading">Memuat tagihan antar-PT…</div>
        ) : state === "error" ? (
          <ErrorNotice testId="icc-error" message={`Tagihan antar-PT gagal dimuat. ${err}`.trim()} onRetry={load} />
        ) : items.length === 0 ? (
          <div className="section-pad text-center text-fs-13 text-kn-text-2" data-testid="icc-empty">Belum ada tagihan insentif antar-PT untuk saringan ini.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table head-wrap w-full" data-testid="icc-table">
              <thead><tr>
                <th>Nomor</th><th>Dari PT</th><th>Kepada PT</th><th className="text-right">Nominal (Rp)</th>
                <th className="text-right">Sisa (Rp)</th><th>Status</th><th className="col-sticky-end text-right">Aksi</th>
              </tr></thead>
              <tbody>
                {items.map((c) => {
                  const alasan = alasanLunas(c, { canSettle, allowed: allowedEntityIds });
                  return (
                    <tr key={c.id} data-testid={`charge-row-${c.id}`} className={c.id === focusId ? "row-focus" : ""}>
                      <td className="whitespace-nowrap"><span className="font-semibold">{c.number}</span>
                        <span className="block text-fs-12 text-kn-text-2">Gaji {c.source?.run_number || "—"}</span></td>
                      <td className="break-words">{c.from_entity_name}</td>
                      <td className="break-words">{c.to_entity_name}</td>
                      <td className="text-right tabular-nums">{angkaRp(c.amount)}</td>
                      <td className="text-right tabular-nums font-semibold">{angkaRp(c.outstanding)}</td>
                      <td><StatusTagihan status={c.status} testId={`charge-status-${c.id}`} /></td>
                      <td className="col-sticky-end text-right">
                        {c.status === "open" && !alasan && (
                          <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid={`charge-settle-${c.id}`}
                            onClick={() => setLunas(c)}><HandCoins size={13} aria-hidden="true" /> Catat pelunasan</button>)}
                        {alasan && <span className="text-fs-12 text-kn-text-2" data-testid={`charge-why-${c.id}`}>{alasan}</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {(data.total || 0) > UKURAN && <KNPager page={page} pageSize={UKURAN} total={data.total} onChange={setPage} testId="icc-pager" />}
      </div>
      {lunas && (
        <FormLunas charge={lunas} onClose={() => setLunas(null)}
          onDone={(c) => { setLunas(null); setMsg(`Pelunasan ${c.number} dicatat — sisa ${formatCurrency(c.outstanding)}.`); load(); }} />
      )}
    </section>
  );
}
