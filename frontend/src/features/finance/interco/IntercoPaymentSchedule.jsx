import { useEffect, useState } from "react";
import { CalendarClock, Info, SlidersHorizontal } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { SettingsBrowser, SettingsNotice, useSettingsBrowser } from "../../settings/config/SettingsHub";
import { formatCurrency, formatDate } from "../../../utils/formatters";
import { docStatusLabel } from "../../../utils/docStatus";
import { stripInternalCodes } from "../../../utils/cleanText";
import { STATUS_LABEL } from "./intercoApi";

// 23 Okt — formatter baku (dulu toLocaleString tanpa batas desimal → "Rp 20.998,967").
const rp = (v) => formatCurrency(v);
const errText = (e) => e.response?.data?.detail?.message || e.response?.data?.detail || e.message;

// LN-024 KLX-03 — cutoff, tanggal bayar & acuan periode dapat dikonfigurasi (semua PT atau per PT pembayar).
// KF-T2 — dulu `CutoffForm` yang menulis `PUT /api/settings` langsung (tanpa riwayat) dan selalu mengirim
// `allow_netting=false` / `require_full_payment=true`. Kini kartu Pusat Pengaturan yang DIKUNCI ke kunci
// `interco_payment.*` (mesin yang sama dengan Pengaturan: lapisan semua PT / per PT pembayar, riwayat, jadwal). Bagian ini
// hanya tampil bagi yang boleh membaca kuncinya; tombol simpan mengikuti `can_edit` dari server (`entity.update`).
export const PAYMENT_RULE_GROUPS = ["antar-entitas"];
export const PAYMENT_RULE_KEYS = ["interco_payment."];

function PaymentRules({ selectedEntity, entities, onChanged }) {
  const base = useSettingsBrowser({ selectedEntity, groupIds: PAYMENT_RULE_GROUPS, includeKeys: PAYMENT_RULE_KEYS });
  if (base.denied || (!base.loading && !base.error && base.groups.length === 0)) return null;
  // Jadwal di bawah dihitung ulang sesudah aturan berubah.
  const after = (fn) => async (...args) => { const res = await fn(...args); onChanged(); return res; };
  const s = { ...base, onSave: after(base.onSave), onReset: after(base.onReset), onClearEntity: after(base.onClearEntity) };
  return (
    <section className="section-card" data-testid="interco-payment-rules">
      <div className="section-head">
        <div className="flex items-center gap-2"><SlidersHorizontal size={14} className="text-kn-action" /><h2>Aturan jadwal bayar</h2></div>
      </div>
      <div className="section-body cfg-hub cfg-group-view">
        <p className="cfg-group-intro">
          Tanggal tutup, tanggal bayar, tanggal acuan, pengingat, serta boleh-tidaknya saling hapus dan pelunasan
          sebagian — untuk semua PT, atau khusus satu PT pembayar.
        </p>
        <SettingsNotice s={s} />
        <SettingsBrowser s={s} entities={entities} groupNav="chips" searchPlaceholder="Cari aturan jadwal bayar…" />
      </div>
    </section>
  );
}

export default function IntercoPaymentSchedule({ selectedEntity, entities = [] }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const load = () => axios.get(`${API}/interco/payment-schedule`).then((r) => setData(r.data)).catch((e) => setErr(errText(e)));
  useEffect(() => { load(); }, []);
  if (err) return <p className="text-sm text-[#C62828]" data-testid="interco-schedule-error">{err}</p>;
  if (!data) return <div className="h-24 rounded-xl bg-[#F5F5F7] animate-pulse" />;
  const pending = data.cutoff_status !== "configured";
  return (
    <div data-testid="interco-schedule-panel" className="space-y-4">
      <div className={`rounded-xl border p-3 text-[12.5px] flex gap-2 ${pending ? "border-[#F5E0C3] bg-[#FDF6EC] text-[#8A4B08]" : "border-[#BFE3CC] bg-[#F2FBF5] text-[#1B7F4B]"}`}
           data-testid="interco-cutoff-status">
        <Info size={15} className="shrink-0 mt-0.5" />
        <div>
          {/* UAT 24 Okt (audit UI tahap 2) — G1-10: tanpa kode keputusan (KLX-03) di teks pengguna. */}
          {pending ? stripInternalCodes(data.note) : <>Cutoff tanggal <b>{data.config.cutoff_day}</b> · bayar tanggal <b>{data.config.payment_day || "akhir bulan"}</b> · acuan periode <b>{data.basis_label}</b> (dapat diubah).</>}
          {/* KF-T2 — kalimat mengikuti aturan yang dipakai mesin (dulu ditulis tetap "dinonaktifkan"). */}
          <p className="mt-1" data-testid="interco-schedule-rules">
            {data.config?.require_full_payment === false ? "Pelunasan sebagian diperbolehkan" : "Pembayaran penuh per transaksi"},
            saling hapus antar tagihan <b>{data.netting === "allowed" ? "diizinkan" : "dinonaktifkan"}</b>. Saldo setiap PT dihitung sendiri-sendiri.
          </p>
          {/* G1-31 — dasar angka disebut: sisa per dokumen terbuka (nilai − pelunasan − retur); umur = sejak tanggal dokumen. */}
          <p className="mt-1 text-[11.5px] opacity-80" data-testid="interco-schedule-basis">Sisa = nilai dokumen − pelunasan − retur, per dokumen yang sudah dikonfirmasi (draf tidak dihitung). Umur dihitung dari tanggal dokumen.</p>
          {/* Keputusan pemilik K-07 (26 Okt) — jadwal ini RINCIAN per dokumen (bruto); angka utama = posisi bersih. */}
          <p className="mt-1 text-[11.5px] font-semibold" data-testid="interco-schedule-detail-label">Rincian per dokumen (bruto, sebelum netting dua arah). Angka utama utang antar-PT = posisi bersih di tab Saldo Antar-PT &amp; kartu ringkasan.</p>
        </div>
      </div>
      <PaymentRules selectedEntity={selectedEntity} entities={entities} onChanged={load} />
      <div className="flex flex-wrap gap-2">
        {data.pairs.map((p) => (
          <div key={`${p.payer_entity_id}>${p.payee_entity_id}`} className="rounded-lg border border-[#E5E5EA] bg-white px-3 py-2 text-[12px]"
               data-testid={`interco-pair-${p.payer_entity_id}-${p.payee_entity_id}`}>
            <b>{p.payer_entity_name}</b> → {p.payee_entity_name}: {p.count} transaksi · {rp(p.remaining)}
          </div>
        ))}
      </div>
      <div className="overflow-x-auto rounded-xl border border-[#E5E5EA] bg-white">
        <table className="min-w-full text-[12.5px]">
          <thead className="bg-[#F7F7F9] text-left text-[#3A3A3C]">
            <tr>{["No. (PT pembayar)", "Pembayar → Penerima", "Status", "Diterima", "Ditagih", "Sisa (bayar penuh)", "Umur dokumen", "Periode bayar"].map((h) => <th key={h} className="px-3 py-2 font-semibold whitespace-nowrap">{h}</th>)}</tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.interco_id} className="border-t border-[#F0F0F3]" data-testid={`interco-schedule-row-${r.interco_id}`}>
                {/* G1-31 — utang dibaca dari sisi PT pembayar: nomor dokumen pembayar (KSC/IC-…), nomor penjual di tooltip. */}
                <td className="px-3 py-2 font-mono whitespace-nowrap" title={r.counterpart_number ? `Nomor PT penerima: ${r.number}` : undefined}>{r.counterpart_number || r.number}</td>
                <td className="px-3 py-2">{r.payer_entity_name} → {r.payee_entity_name}</td>
                <td className="px-3 py-2">{docStatusLabel(r.status, STATUS_LABEL)}</td>
                <td className="px-3 py-2">{formatDate(r.received_at) || "—"}</td>
                <td className="px-3 py-2">{formatDate(r.invoiced_at) || "—"}</td>
                <td className="px-3 py-2 text-right tabular-nums">{rp(r.remaining)}</td>
                <td className="px-3 py-2 tabular-nums">{r.age_days ?? "—"} hari</td>
                <td className="px-3 py-2" data-testid={`interco-schedule-period-${r.interco_id}`}>
                  {r.period ? <span className="inline-flex items-center gap-1"><CalendarClock size={12} /> {formatDate(r.pay_date)}</span>
                            : <span className="text-[#B45309]">Menunggu pengaturan cutoff</span>}
                </td>
              </tr>
            ))}
            {!data.rows.length && <tr><td colSpan={8} className="px-3 py-6 text-center text-[#8E8E93]">Tidak ada utang antar-PT terbuka.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
