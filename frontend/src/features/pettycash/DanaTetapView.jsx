/**
 * DanaTetapView — Kas & Bank bagian 3 (Tugas 4a): Keuangan › Kas & Bank › Kas Kecil › **Dana tetap** (rancangan §5.2,
 * §5.4, §7.8 butir 1 dan 4).
 *
 * Sumber: `GET /api/kas-kecil/dana-tetap?entity_id=` (izin `cash.view`) — posisi per rekening kas kecil aktif berdana
 * tetap: dana tetap, saldo buku, sisa panjar di tangan karyawan (`panjar_belum_lpj`: dicairkan − belanja LPJ disetujui −
 * sisa yang sudah dikembalikan, ketetapan R3), usulan isi ulang, isi ulang yang masih terbuka; `tanpa_dana_tetap` =
 * rekening kas kecil yang belum memakai dana tetap (kalimat + tautan ke Rekening & Saldo, tempat dana tetap diatur).
 * Templat daftar (`04_POLA_UI` §2.A): judul satu baris (+ ?) · tabel · aksi baris di kolom kanan. Klik baris = pop-up
 * `DetailModal` rincian: dokumen sejak isi ulang terakhir (pengaruh tiap baris ke usulan, jumlahnya), sisa panjar per
 * pencairan (keadaan: belum LPJ / sisa belum dikembalikan), panjar lama tanpa rekening, riwayat Pindah Dana isi ulang, dan
 * kalimat "saldo buku + sisa panjar + usulan = dana tetap" bila berlaku. Nomor Pindah Dana = `DocLink` → pratinjau PDN.
 * Aksi "Isi ulang" (izin `cash.create`) = pop-up `IsiUlangModal` (hasil = toast); tombol nonaktif dengan kalimat server
 * (`alasan_isi_ulang`) bila isi ulang terbuka masih ada atau tidak perlu — satu isi ulang terbuka per rekening.
 */
import { useCallback, useEffect, useState } from "react";
import { Coins, RefreshCcw, RefreshCw } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";
import { notifySuccess } from "../../utils/feedback";
import { formatCurrency, formatDate, formatDateTime } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";
import ResponsiveTable from "../../components/ResponsiveTable";
import DetailModal from "../../components/DetailModal";
import EntityBadge from "../../components/EntityBadge";
import StatusBadge from "../../components/StatusBadge";
import EmptyState from "../../components/EmptyState";
import { HelpTip } from "../../components/ListPageParts";
import { can } from "../../config/roles";
import { useAppNav } from "../../context/AppNavContext";
import DocLink from "../documents/preview/DocLink";
import { statusPindahDana } from "../finance/fundtransfer/fundTransferShared";
import IsiUlangModal from "./IsiUlangModal";

export const TEKS_BANTU = "Dana tetap = batas uang kas kecil per rekening. Usulan isi ulang = dana tetap − saldo buku − "
  + "sisa panjar di tangan karyawan, yaitu pengeluaran yang sudah dipertanggungjawabkan sejak isi ulang terakhir. Isi ulang "
  + "mencatat Pindah Dana dari rekening bank atau kas besar sebesar usulan itu (dihitung sistem). Satu isi ulang terbuka "
  + "per rekening. Dana tetap diatur di Rekening & Saldo › Ubah rekening.";
export const TEKS_KOSONG = "Belum ada rekening kas kecil yang memakai dana tetap. Atur dana tetap di Rekening & Saldo › "
  + "Ubah rekening.";

const sen = (n) => Math.round((Number(n) || 0) * 100);
const tandaRp = (n) => `${Number(n) < 0 ? "−" : "+"}${formatCurrency(Math.abs(Number(n) || 0))}`;

function PdnLink({ d, entityId, perms, testId }) {
  return (
    <DocLink docType="fund_transfer" docId={d.id} number={d.number} entityId={entityId} perms={perms}
      className="font-mono font-semibold" testId={testId} />
  );
}

export default function DanaTetapView({ currentUser, selectedEntity = "all" }) {
  const perms = currentUser?.permissions || {};
  const bolehIsi = can(perms, "cash", "create");
  const { go, canOpen } = useAppNav();
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading");   // loading | ready | error
  const [error, setError] = useState("");
  const [rinci, setRinci] = useState(null);        // posisi yang rinciannya dibuka
  const [isi, setIsi] = useState(null);            // posisi yang sedang diisi ulang
  const scoped = Boolean(selectedEntity) && selectedEntity !== "all";

  const load = useCallback(async () => {
    setState("loading");
    try {
      const params = scoped ? { entity_id: selectedEntity } : {};
      const r = await axios.get(`${API}/kas-kecil/dana-tetap`, { params });
      setData(r.data || null); setError(""); setState("ready");
    } catch (e) {
      setData(null); setError(apiErrorText(e, "Posisi dana tetap tidak bisa dimuat.")); setState("error");
    }
  }, [scoped, selectedEntity]);
  useEffect(() => { load(); }, [load]);

  const rows = data?.items || [];
  const tanpa = Number(data?.tanpa_dana_tetap) || 0;
  const keRekening = canOpen("bank-accounts") ? () => go("bank-accounts") : null;

  const onSaved = async (doc) => {
    setIsi(null);
    const menunggu = doc?.status === "menunggu_persetujuan";
    notifySuccess(`Isi ulang ${doc?.number || ""} dicatat — ${statusPindahDana(doc?.status).label.toLowerCase()}.`
      + (menunggu ? " Setujui di Kas & Bank › Pindah Dana." : ""));
    await load();
  };

  return (
    <div className="grid gap-3" data-testid="dt-view">
      <section className="section-card" data-testid="dt-list">
        <div className="section-head">
          <div className="flex min-w-0 items-center gap-2">
            <Coins size={15} aria-hidden="true" className="text-kn-action" />
            <h2 data-testid="dt-title">Dana tetap</h2>
            <HelpTip text={TEKS_BANTU} testId="dt-help" />
            {rows.length > 0 && <span className="text-fs-12 text-kn-text-2" data-testid="dt-count">{rows.length} rekening</span>}
          </div>
          <button type="button" data-testid="dt-refresh" className="icon-button" onClick={load} aria-label="Muat ulang">
            <RefreshCw size={14} className={state === "loading" ? "animate-spin" : ""} /></button>
        </div>
        <div className="section-body grid gap-2">
          {tanpa > 0 && (
            <p className="text-fs-12 text-kn-text-2" data-testid="dt-none-note">
              {tanpa} rekening kas kecil belum memakai dana tetap.{" "}
              {keRekening && (
                <button type="button" className="link-button" data-testid="dt-none-link" onClick={keRekening}>
                  Atur di Rekening &amp; Saldo</button>
              )}
            </p>
          )}
          {state === "error" ? <ErrorNotice testId="dt-error" message={error} onRetry={load} /> : (
            <ResponsiveTable testId="dt-table" rows={rows} rowKey="account_id" rowTestId={(r) => `dt-row-${r.account_id}`}
              loading={state === "loading" && !data} empty={<span data-testid="dt-empty">{TEKS_KOSONG}</span>}
              onRowClick={(r) => setRinci(r)} stickyActions
              columns={[
                { key: "account_name", header: "Rekening", mobile: "title", render: (r) => (
                  <span className="block min-w-0">
                    <button type="button" className="link-button text-left font-bold" data-testid={`dt-open-${r.account_id}`}
                      onClick={(e) => { e.stopPropagation(); setRinci(r); }}>{r.account_name}</button>
                    {!scoped && r.entity_id && <span className="mt-0.5 block"><EntityBadge entityId={r.entity_id} /></span>}
                  </span>) },
                { key: "dana_tetap", header: "Dana tetap", align: "right", priority: 1, render: (r) => (
                  <span className="tabular-nums whitespace-nowrap" data-testid={`dt-dana-${r.account_id}`}>{formatCurrency(r.dana_tetap)}</span>) },
                { key: "saldo_buku", header: "Saldo buku", align: "right", priority: 2, render: (r) => (
                  <span className="tabular-nums whitespace-nowrap" data-testid={`dt-saldo-${r.account_id}`}>{formatCurrency(r.saldo_buku)}</span>) },
                { key: "panjar_belum_lpj", header: "Sisa panjar", align: "right", priority: 3, render: (r) => (
                  <span className="tabular-nums whitespace-nowrap" data-testid={`dt-panjar-${r.account_id}`}>{formatCurrency(r.panjar_belum_lpj)}</span>) },
                { key: "usulan_isi_ulang", header: "Usulan isi ulang", align: "right", priority: 0, render: (r) => (
                  <span className={`tabular-nums whitespace-nowrap font-bold ${Number(r.usulan_isi_ulang) > 0 ? "text-kn-text" : "text-kn-text-2"}`}
                    data-testid={`dt-usulan-${r.account_id}`}>{formatCurrency(r.usulan_isi_ulang)}</span>) },
                { key: "isi_ulang", header: "Isi ulang", mobile: "field", priority: 4, render: (r) => {
                  const m = r.isi_ulang_menunggu;
                  if (m) {
                    const st = statusPindahDana(m.status);
                    return (
                      <span className="block min-w-0">
                        <PdnLink d={m} entityId={r.entity_id} perms={perms} testId={`dt-pending-${r.account_id}`} />
                        <span className="mt-0.5 block"><StatusBadge status={m.status} label={st.label} tone={st.tone} icon={st.icon} /></span>
                      </span>);
                  }
                  if (r.sejak) {
                    return <span className="whitespace-nowrap text-fs-12 text-kn-text-2">Terakhir {formatDate(r.sejak.tanggal || r.sejak.created_at)}</span>;
                  }
                  return <span className="text-fs-12 text-kn-text-2">Belum pernah</span>;
                } },
              ]}
              actions={bolehIsi ? (r) => (
                <div className="flex flex-col items-end gap-1">
                  <button type="button" className="primary-button btn-sm whitespace-nowrap" data-testid={`dt-refill-${r.account_id}`}
                    disabled={!r.bisa_isi_ulang} onClick={(e) => { e.stopPropagation(); setIsi(r); }}>
                    <RefreshCcw size={13} aria-hidden="true" /> Isi ulang</button>
                  {!r.bisa_isi_ulang && r.alasan_isi_ulang && (
                    <span className="max-w-[240px] whitespace-normal break-words text-left text-fs-12 text-kn-text-2" data-testid={`dt-refill-reason-${r.account_id}`}>
                      {r.alasan_isi_ulang}</span>
                  )}
                </div>
              ) : undefined}
            />
          )}
        </div>
      </section>

      {rinci && (
        <DetailModal framed size="lg" label={`Dana tetap ${rinci.account_name}`} testId="dt-detail-modal" onClose={() => setRinci(null)}>
          <RincianDanaTetap pos={rinci} perms={perms} />
        </DetailModal>
      )}
      {isi && (
        <IsiUlangModal open accountId={isi.account_id} accountName={isi.account_name} onClose={() => setIsi(null)} onSaved={onSaved} />
      )}
    </div>
  );
}

/** Isi pop-up rincian posisi dana tetap satu rekening (hanya-baca; data dari daftar posisi). */
export function RincianDanaTetap({ pos, perms }) {
  const rincian = pos.rincian || [];
  const panjar = pos.panjar || [];
  const riwayat = pos.riwayat || [];
  const lama = pos.panjar_tanpa_rekening || {};
  return (
    <div className="grid gap-3" data-testid="dt-detail">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 pr-6">
        <h2 className="text-fs-16 font-bold text-kn-text">Dana tetap {pos.account_name}</h2>
        <span className="text-fs-12 text-kn-text-2">Dihitung {formatDateTime(pos.dihitung_pada)}</span>
      </div>
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[["Dana tetap", pos.dana_tetap], ["Saldo buku", pos.saldo_buku], ["Sisa panjar", pos.panjar_belum_lpj],
          ["Usulan isi ulang", pos.usulan_isi_ulang]].map(([l, v], i) => (
          <div key={l} className="rounded-md border border-kn-divider px-2.5 py-1.5">
            <dt className="text-fs-12 text-kn-text-2">{l}</dt>
            <dd className={`tabular-nums ${i === 3 ? "text-fs-14 font-bold" : "text-fs-13 font-semibold"} text-kn-text`}>{formatCurrency(v)}</dd>
          </div>
        ))}
      </dl>
      {sen(pos.saldo_buku) + sen(pos.panjar_belum_lpj) + sen(pos.usulan_isi_ulang) === sen(pos.dana_tetap) && (
        <p className="text-fs-12 text-kn-text-2" data-testid="dt-detail-identity">
          Saldo buku + sisa panjar di tangan karyawan + usulan isi ulang = dana tetap {formatCurrency(pos.dana_tetap)}.
        </p>
      )}
      {!pos.bisa_isi_ulang && pos.alasan_isi_ulang && (
        <p className="text-fs-12 text-kn-text-2" data-testid="dt-detail-reason">{pos.alasan_isi_ulang}</p>
      )}

      <section className="grid gap-1.5">
        <h3 className="text-fs-13 font-semibold text-kn-text" data-testid="dt-detail-since">
          {pos.sejak ? `Sejak isi ulang terakhir ${pos.sejak.number} · ${formatDate(pos.sejak.tanggal || pos.sejak.created_at)}`
            : "Sejak awal (belum pernah diisi ulang)"}
        </h3>
        {rincian.length === 0 ? (
          <EmptyState compact kind="empty" title="Belum ada pengeluaran atau pengembalian sejak isi ulang terakhir."
            testId="dt-detail-empty" />
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table w-full" data-testid="dt-detail-rincian">
              <thead><tr><th>Tanggal</th><th>Jenis</th><th>Nomor</th><th>Keterangan</th><th className="text-right">Pengaruh ke usulan</th></tr></thead>
              <tbody>
                {rincian.map((r, i) => (
                  <tr key={`${r.kas_id || r.ref_id}-${i}`} data-testid={`dt-detail-row-${i}`}>
                    <td className="whitespace-nowrap">{formatDate(r.tanggal)}</td>
                    <td className="whitespace-nowrap">{r.label}</td>
                    <td className="whitespace-nowrap">
                      {r.ref_type === "fund_transfer" && r.ref_id ? (
                        <DocLink docType="fund_transfer" docId={r.ref_id} number={r.nomor} entityId={pos.entity_id} perms={perms}
                          className="font-mono" testId={`dt-detail-ref-${i}`} />
                      ) : <span className="font-mono">{r.nomor || "—"}</span>}
                    </td>
                    <td className="min-w-[160px]">
                      {r.keterangan || "—"}
                      {r.jenis === "lpj" && Number(r.pengeluaran) > 0 && (
                        <span className="block text-fs-12 text-kn-text-2">Belanja {formatCurrency(r.pengeluaran)} dari panjar {formatCurrency(r.panjar ?? r.nominal)}</span>
                      )}
                    </td>
                    <td className={`whitespace-nowrap text-right tabular-nums ${Number(r.pengaruh) < 0 ? "text-kn-success-text" : "text-kn-text"}`}>
                      {tandaRp(r.pengaruh)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr data-testid="dt-detail-total">
                  <td colSpan={4} className="font-semibold">Jumlah</td>
                  <td className="text-right tabular-nums font-bold">{formatCurrency(pos.total_rincian)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
        {pos.rincian_terpotong && (
          <p className="text-fs-12 text-kn-text-2" data-testid="dt-detail-cut">Menampilkan 500 baris terbaru; jumlah dihitung dari semua baris.</p>
        )}
      </section>

      <section className="grid gap-1.5" data-testid="dt-detail-panjar">
        <h3 className="text-fs-13 font-semibold text-kn-text">Sisa panjar di tangan karyawan</h3>
        {panjar.length === 0 ? (
          <EmptyState compact kind="empty" title="Tidak ada sisa panjar dari rekening ini." testId="dt-detail-panjar-empty" />
        ) : (
          <ul className="grid gap-1">
            {panjar.map((pj) => (
              <li key={pj.kas_id || pj.cash_advance_id} className="flex flex-wrap justify-between gap-2 text-fs-13"
                data-testid={`dt-detail-advance-${pj.cash_advance_id}`}>
                <span className="min-w-0">
                  <span className="font-mono font-semibold">{pj.nomor || "—"}</span> · {pj.kegiatan || "—"} · {pj.pemohon || "—"}
                  <span className="block text-fs-12 text-kn-text-2">
                    {pj.keadaan_label || "Belum LPJ"} · dicairkan {formatDate(pj.tanggal)}
                    {pj.lpj_nomor ? ` · ${pj.lpj_nomor}` : ""}
                  </span>
                </span>
                <span className="text-right tabular-nums">
                  {formatCurrency(pj.sisa ?? pj.nominal)}
                  {pj.sisa !== undefined && Number(pj.sisa) !== Number(pj.nominal) && (
                    <span className="block text-fs-12 text-kn-text-2">dari panjar {formatCurrency(pj.nominal)}</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
        {Number(lama.jumlah) > 0 && (
          <p className="text-fs-12 text-kn-warning-text" data-testid="dt-detail-old-advances">
            {lama.jumlah} panjar lama tanpa rekening ({formatCurrency(lama.total)}{lama.nomor?.length ? ` · ${lama.nomor.join(", ")}` : ""})
            tidak dihitung ke rekening mana pun.
          </p>
        )}
      </section>

      <section className="grid gap-1.5" data-testid="dt-detail-history">
        <h3 className="text-fs-13 font-semibold text-kn-text">Riwayat isi ulang</h3>
        {riwayat.length === 0 ? (
          <EmptyState compact kind="empty" title="Belum pernah diisi ulang." testId="dt-detail-history-empty" />
        ) : (
          <ul className="grid gap-1">
            {riwayat.map((d) => {
              const st = statusPindahDana(d.status);
              return (
                <li key={d.id} className="flex flex-wrap items-center justify-between gap-2 text-fs-13">
                  <span className="inline-flex flex-wrap items-center gap-1.5">
                    <PdnLink d={d} entityId={pos.entity_id} perms={perms} testId={`dt-history-${d.id}`} />
                    <span className="text-kn-text-2">{formatDate(d.tanggal || d.created_at)}{d.rekening_asal_nama ? ` · dari ${d.rekening_asal_nama}` : ""}</span>
                  </span>
                  <span className="inline-flex items-center gap-2">
                    <span className="tabular-nums">{formatCurrency(d.nominal)}</span>
                    <StatusBadge status={d.status} label={st.label} tone={st.tone} icon={st.icon} />
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
