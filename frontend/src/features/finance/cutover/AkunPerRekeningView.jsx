/**
 * AkunPerRekeningView — Kas & Bank bagian 1 (Tugas 6) · Keuangan › Kas & Bank › Akun per rekening (view
 * `kas-per-rekening`; tab tersembunyi yang dibuka dari Rekening & Saldo, antrean persetujuan, dan Posting Gagal).
 *
 * Alat pindah saldo kas per PT ke akun buku besar per rekening (spesifikasi §5.3): pratinjau tabel tanpa tulisan
 * (`GET /api/kas-per-rekening/{PT}/pratinjau`), tombol **Siapkan** (pop-up `SiapkanModal`; nonaktif dengan alasan
 * tertulis bila PT sudah aktif, usulan masih menunggu, atau ada posting kas gagal/tertunda — dengan tautan ke Posting
 * Gagal), dan daftar usulan PT itu (`GET /api/kas-per-rekening/usulan`) dengan **Setujui** (pop-up `SetujuiModal`: angka
 * dihitung ulang, sidik yang dilihat dikirim) / **Tolak** (`askReason`) / **Lanjutkan** (usulan yang terhenti) dan
 * tautan ke jurnalnya. Semua rute `accounting.manage` (izin, bukan peran); tanpa izin itu layar hanya memberi tahu.
 * Satu PT: mode "Semua PT" menampilkan petunjuk memilih PT.
 *
 * Tinjauan akhir: PT yang sudah aktif (I1) → keadaan sesudah pindah: saldo akun tiap rekening vs buku kasnya (selisih =
 * pemeriksa "saldo per rekening = buku kas") dan angka yang dipindah saat disetujui. Posting tertunda (Minor 1) dirinci
 * per jenis dengan nomor dokumen + arahan, tombol hanya ke layar yang benar-benar mendaftarnya (Posting Gagal / Proses
 * Gaji). Muat bertumpuk (ganti PT cepat, Minor 5): hanya jawaban permintaan terakhir yang dipakai.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { ExternalLink, Landmark, RefreshCw } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import ErrorNotice from "../../../components/ErrorNotice";
import EntityScopeBanner from "../../../components/EntityScopeBanner";
import StatusBadge from "../../../components/StatusBadge";
import { ListToolbar, PageHeader } from "../../../components/ListPageParts";
import { can } from "../../../config/roles";
import { useAppNav } from "../../../context/AppNavContext";
import { useEntityScope } from "../../../context/EntityScopeContext";
import { askConfirm, askReason } from "../../../services/confirmService";
import { apiErrorText } from "../../../utils/apiError";
import { entityShortById } from "../../../utils/entityLabel";
import { notifySuccess } from "../../../utils/feedback";
import { formatCurrency, formatDate, formatDateTime } from "../../../utils/formatters";
import JournalDetailModal from "../JournalDetailModal";
import { sourceLabel } from "../glSourceLabels";
import { SetujuiModal, SiapkanModal } from "./PindahSaldoModals";
import { KasTanpaRekening, TabelAkunLama, TabelJurnal, TabelRekening } from "./PindahSaldoTables";
import { ALASAN_MIN, alasanTidakBisaSiapkan, rekeningBerselisih, statusUsulan, tombolTertunda } from "./cutoverShared";

export const TEKS_BANTU = "Sebelum memakai akun buku besar per rekening, saldo kas tiap rekening dipindah dari akun kas "
  + "lama (1-1100 / 1-1110) ke akun rekening masing-masing. Pratinjau di bawah tidak menulis apa pun. Siapkan membuat "
  + "sub-akun rekening dan usulan; orang lain menyetujuinya — angka dihitung ulang saat itu, jurnalnya bertanggal hari "
  + "persetujuan, lalu kas baru PT masuk akun rekening. Sekali per PT.";

export default function AkunPerRekeningView({ currentUser, selectedEntity }) {
  const perms = currentUser?.permissions;
  const canManage = can(perms, "accounting", "manage");
  const canJournal = can(perms, "accounting", "view");
  const { go, canOpen } = useAppNav();
  const { entities = [] } = useEntityScope() || {};
  const scoped = Boolean(selectedEntity) && selectedEntity !== "all";
  const pt = entityShortById(entities, selectedEntity, "PT ini");
  const [pv, setPv] = useState(null);
  const [usulan, setUsulan] = useState([]);
  const [state, setState] = useState("memuat");   // memuat | siap | galat
  const [err, setErr] = useState("");
  const [aksiErr, setAksiErr] = useState("");
  const [siapkan, setSiapkan] = useState(false);
  const [setujui, setSetujui] = useState(null);
  const [jurnal, setJurnal] = useState(null);
  const [sibuk, setSibuk] = useState("");
  const muatKe = useRef(0);   // nomor permintaan muat terakhir (jawaban permintaan lama dibuang)

  const load = useCallback(async () => {
    if (!scoped || !canManage) return;
    const ke = ++muatKe.current;
    setState("memuat");
    try {
      const [p, u] = await Promise.all([
        axios.get(`${API}/kas-per-rekening/${selectedEntity}/pratinjau`),
        axios.get(`${API}/kas-per-rekening/usulan`, { params: { entity_id: selectedEntity, page_size: 20 } }),
      ]);
      if (ke !== muatKe.current) return;
      setPv(p.data || null);
      setUsulan(u.data?.items || []);
      setErr("");
      setState("siap");
    } catch (e) {
      if (ke !== muatKe.current) return;
      setPv(null);
      setUsulan([]);
      setErr(apiErrorText(e, "Pindah saldo kas belum bisa dimuat."));
      setState("galat");
    }
  }, [scoped, canManage, selectedEntity]);
  useEffect(() => {   // PT berganti: angka PT sebelumnya tidak ditampilkan dengan label PT baru
    setPv(null);
    setUsulan([]);
  }, [selectedEntity]);
  useEffect(() => { load(); }, [load]);

  async function tolak(u) {
    const alasan = await askReason({
      title: `Tolak ${u.label}?`, danger: true, reasonLabel: "Alasan penolakan", reasonMinLength: ALASAN_MIN,
      message: `Usulan pindah saldo ${formatCurrency(u.total_dipindah)} di ${pt} ditolak. Saldo tidak dipindah dan PT tetap `
        + "memakai akun kas lama; sub-akun rekening buatan sistem yang sudah dibuat tetap ada (kosong), akun bagan PT "
        + "pilihan Finance dilepas lagi seperti sebelum dipilih.",
      confirmLabel: "Tolak usulan", testId: "ps-reject-reason" });
    if (alasan === null || alasan === undefined) return;
    await kirimAksi(u, "tolak", { alasan }, `Usulan ${u.label} ditolak.`);
  }

  async function lanjutkan(u) {
    const ok = await askConfirm({ title: `Lanjutkan ${u.label}?`, confirmLabel: "Lanjutkan", testId: "ps-resume-confirm",
      message: `Persetujuan pindah saldo ${pt} terhenti di tengah. Lanjutkan dari langkah terakhir yang tersimpan.` });
    if (ok) await kirimAksi(u, "setujui", { sidik: "", selisih_diperiksa: false }, `Pindah saldo ${pt} dilanjutkan.`);
  }

  async function kirimAksi(u, aksi, body, pesan) {
    setSibuk(u.id);
    setAksiErr("");
    try {
      await axios.post(`${API}/kas-per-rekening/usulan/${u.id}/${aksi}`, body);
      notifySuccess(pesan);
    } catch (e) {
      setAksiErr(apiErrorText(e, "Usulan pindah saldo belum bisa diproses."));
    } finally {
      setSibuk("");
      await load();
    }
  }

  async function bukaJurnal(id) {
    setAksiErr("");
    try { setJurnal((await axios.get(`${API}/gl/journal/${id}`)).data); }
    catch (e) { setAksiErr(apiErrorText(e, "Jurnal pindah saldo belum bisa dimuat.")); }
  }

  const header = <PageHeader icon={Landmark} title="Akun per rekening" help={TEKS_BANTU} testId="ps-header" />;
  if (!canManage) {
    return (
      <div className="space-y-3" data-testid="kas-per-rekening-view">
        {header}
        <p className="section-card section-pad text-fs-13 text-kn-text-2" data-testid="ps-no-access">
          Anda belum punya akses untuk memindah saldo kas ke akun per rekening. Minta Admin menambahkan akses
          &apos;Akuntansi&apos; tingkat kelola.
        </p>
      </div>
    );
  }
  if (!scoped) {
    return (
      <div className="space-y-3" data-testid="kas-per-rekening-view">
        {header}
        <p className="section-card section-pad text-fs-13 text-kn-text-2" data-testid="ps-pick-entity">
          Pilih satu PT di kanan atas untuk melihat pindah saldo kas ke akun per rekening.
        </p>
      </div>
    );
  }

  const alasan = alasanTidakBisaSiapkan(pv, { canManage });
  const berselisih = pv?.aktif ? rekeningBerselisih(pv) : [];
  return (
    <div className="space-y-3" data-testid="kas-per-rekening-view">
      {header}
      <EntityScopeBanner testId="ps-scope" />
      <ErrorNotice message={aksiErr} onDismiss={() => setAksiErr("")} testId="ps-action-error" />
      <ListToolbar testId="ps-toolbar"
        count={pv ? (
          <span data-testid="ps-mode">
            {pv.aktif ? `${pt} memakai akun per rekening sejak ${formatDate(pv.aktif_sejak)}`
                + (pv.pindah_saldo?.journal_number ? ` · dipindah ${formatCurrency(pv.total_dipindah)} (jurnal ${pv.pindah_saldo.journal_number})` : "")
              : `${pt} belum memakai akun per rekening · total dipindah ${formatCurrency(pv.total_dipindah)}`}
          </span>) : null}
        actions={(
          <div className="flex flex-wrap items-center gap-2">
            {alasan && state === "siap" && <span className="text-fs-12 text-kn-text-2" data-testid="ps-prepare-why">{alasan}</span>}
            <button type="button" className="icon-button" aria-label="Muat ulang" title="Muat ulang" data-testid="ps-refresh"
              onClick={load}><RefreshCw size={14} className={state === "memuat" ? "animate-spin" : ""} /></button>
            <button type="button" className="primary-button whitespace-nowrap" data-testid="ps-prepare"
              disabled={Boolean(alasan) || state !== "siap"} onClick={() => setSiapkan(true)}>Siapkan pindah saldo</button>
          </div>
        )} />

      {state === "galat" ? (
        <ErrorNotice message={err} onRetry={load} testId="ps-error" />
      ) : state === "memuat" && !pv ? (
        <p className="section-card section-pad text-fs-13 text-kn-text-2" role="status" data-testid="ps-loading">Menghitung pratinjau…</p>
      ) : pv ? (
        <>
          {Number(pv.posting_gagal) > 0 && !pv.aktif && (
            <PostingTertunda pv={pv} go={go} canOpen={canOpen} />
          )}
          {pv.aktif && pv.usulan?.status === "memproses" && (
            <div className="notice-bar warning text-fs-13" data-testid="ps-active-unfinished">
              <span>Pindah saldo {pt} belum selesai — lanjutkan dari daftar usulan di bawah; selisih di bawah hilang
                sesudah jurnal pindah saldonya terbit.</span>
            </div>
          )}
          {pv.aktif && pv.usulan?.status !== "memproses" && (
            <div className={`notice-bar ${berselisih.length ? "warning" : "success"} text-fs-13`} data-testid="ps-active-check">
              <span>{berselisih.length
                ? `${berselisih.length} rekening berselisih dengan buku kasnya: ${berselisih.map((r) => `${r.nama} ${formatCurrency(r.selisih)}`).join("; ")}. Periksa jurnal yang menyentuh akun rekening tanpa dokumen kas.`
                : "Saldo akun buku besar tiap rekening sama dengan saldo buku kasnya."}</span>
            </div>
          )}
          <Bagian judul={pv.aktif ? "Rekening — saldo akun dan buku kas" : "Rekening"} testId="ps-sec-accounts">
            <TabelRekening pv={pv} /><KasTanpaRekening pv={pv} />
          </Bagian>
          <Bagian judul="Akun kas lama" testId="ps-sec-old"><TabelAkunLama pv={pv} /></Bagian>
          {!pv.aktif && <Bagian judul="Jurnal yang akan dibuat" testId="ps-sec-journal"><TabelJurnal pv={pv} /></Bagian>}
        </>
      ) : null}

      <Bagian judul="Usulan pindah saldo" testId="ps-sec-proposals">
        <DaftarUsulan rows={usulan} sibuk={sibuk} canJournal={canJournal} onSetujui={setSetujui} onTolak={tolak}
          onLanjutkan={lanjutkan} onJurnal={bukaJurnal} />
      </Bagian>

      <SiapkanModal open={siapkan && Boolean(pv)} pv={pv} entityId={selectedEntity} pt={pt} onClose={() => setSiapkan(false)}
        onDone={async (u) => { setSiapkan(false); notifySuccess(`Usulan ${u?.label || "pindah saldo"} disiapkan — menunggu persetujuan orang lain.`); await load(); }} />
      {setujui && (
        <SetujuiModal key={setujui.id} usulan={setujui} entityId={selectedEntity} pt={pt} onClose={() => setSetujui(null)}
          onDone={async (u) => {
            setSetujui(null);
            notifySuccess(`Pindah saldo ${pt} disetujui${u?.journal_number ? ` — jurnal ${u.journal_number}` : ""}.`);
            await load();
          }} />
      )}
      {jurnal && (
        <JournalDetailModal je={jurnal} sourceMeta={(c) => ({ label: sourceLabel(c), tone: "bg-kn-neutral-soft text-kn-text-2" })}
          entities={entities} selectedEntity={selectedEntity} onClose={() => setJurnal(null)} />
      )}
    </div>
  );
}

/** Posting kas gagal/tertunda per jenis: jumlah, nomor dokumen (jenis yang tidak tampil di Posting Gagal), arahan, dan
 *  tombol ke layar yang mendaftarnya (tinjauan akhir Minor 1). */
function PostingTertunda({ pv, go, canOpen }) {
  const rincian = pv.posting_gagal_rincian || [];
  const tombol = tombolTertunda(rincian).filter((t) => canOpen(t.view));
  return (
    <div className="notice-bar warning text-fs-13" data-testid="ps-pending-postings">
      <div className="grid gap-1">
        <span>{pv.posting_gagal} posting kas gagal atau tertunda harus selesai dulu sebelum pindah saldo disiapkan.</span>
        {rincian.length > 0 && (
          <ul className="grid gap-0.5" data-testid="ps-pending-list">
            {rincian.map((x) => (
              <li key={x.jenis} data-testid={`ps-pending-${x.jenis}`}>
                <b>{x.label}: {x.jumlah}</b>
                {(x.contoh || []).length > 0 && <span className="font-mono"> ({x.contoh.join(", ")})</span>}
                {x.arahan && <span> — {x.arahan}.</span>}
              </li>
            ))}
          </ul>
        )}
        {tombol.length > 0 && (
          <span className="flex flex-wrap gap-3">
            {tombol.map((t) => (
              <button key={t.view} type="button" className="link-button" data-testid={`ps-open-${t.view}`} onClick={() => go(t.view)}>
                {t.label} <ExternalLink size={12} aria-hidden="true" className="inline" />
              </button>
            ))}
          </span>
        )}
      </div>
    </div>
  );
}

function Bagian({ judul, testId, children }) {
  return (
    <div className="section-card" data-testid={testId}>
      <div className="section-head"><h2>{judul}</h2></div>
      <div className="section-body grid gap-2">{children}</div>
    </div>
  );
}

function DaftarUsulan({ rows, sibuk, canJournal, onSetujui, onTolak, onLanjutkan, onJurnal }) {
  if (!rows.length) return <p className="text-fs-13 text-kn-text-2" data-testid="ps-proposals-empty">Belum ada usulan pindah saldo untuk PT ini.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="data-table head-wrap w-full" data-testid="ps-proposals">
        <thead><tr><th>Usulan</th><th>Status</th><th>Disiapkan</th><th>Diputus</th><th className="text-right">Dipindah</th>
          <th>Jurnal</th><th className="col-sticky-end text-right">Aksi</th></tr></thead>
        <tbody>
          {rows.map((u) => {
            const st = statusUsulan(u.status);
            const ditolak = u.kontrol?.ditolak ? (u.kontrol.pesan || "Rekan lain yang berwenang yang menyetujui.") : "";
            const mati = sibuk === u.id;
            return (
              <tr key={u.id} data-testid={`ps-proposal-${u.id}`}>
                <td className="min-w-[160px] font-semibold">{u.label}</td>
                <td><StatusBadge status={u.status} label={st.label} tone={st.tone} icon={st.icon} testId={`ps-proposal-status-${u.id}`} />
                  {u.alasan_tolak && <span className="block text-fs-12 text-kn-text-2">{u.alasan_tolak}</span>}</td>
                <td className="whitespace-nowrap">{u.disiapkan_oleh || "—"}<span className="block text-fs-12 text-kn-text-2">{formatDateTime(u.disiapkan_pada)}</span></td>
                <td className="whitespace-nowrap">{u.disetujui_oleh || u.ditolak_oleh || "—"}
                  {(u.disetujui_pada || u.ditolak_pada) && <span className="block text-fs-12 text-kn-text-2">{formatDateTime(u.disetujui_pada || u.ditolak_pada)}</span>}</td>
                <td className="text-right tabular-nums">{formatCurrency(u.total_dipindah)}</td>
                <td className="whitespace-nowrap">
                  {u.journal_entry_id && canJournal ? (
                    <button type="button" className="link-button font-mono" data-testid={`ps-proposal-journal-${u.id}`}
                      onClick={() => onJurnal(u.journal_entry_id)}>{u.journal_number || "Lihat jurnal"}</button>
                  ) : (u.journal_number || "—")}
                </td>
                <td className="col-sticky-end text-right">
                  {u.status === "menunggu" && (
                    <div className="flex flex-col items-end gap-1">
                      <div className="flex flex-wrap justify-end gap-1.5">
                        <button type="button" className="primary-button btn-sm" data-testid={`ps-approve-${u.id}`}
                          disabled={mati || Boolean(ditolak)} onClick={() => onSetujui(u)}>Setujui</button>
                        <button type="button" className="danger-button btn-sm" data-testid={`ps-reject-${u.id}`}
                          disabled={mati} onClick={() => onTolak(u)}>Tolak</button>
                      </div>
                      {/* Sel aksi `text-right` mewarisi `white-space: nowrap` (components.css, kolom angka): kalimat alasan
                          wajib dibungkus sendiri, kalau tidak tabel melebar dan kalimatnya terpotong di tepi kanan. */}
                      {ditolak && <span className="max-w-[260px] whitespace-normal break-words text-left text-fs-12 text-kn-text-2" data-testid={`ps-approve-why-${u.id}`}>{ditolak}</span>}
                    </div>
                  )}
                  {u.status === "memproses" && (
                    <button type="button" className="primary-button btn-sm" data-testid={`ps-resume-${u.id}`} disabled={mati}
                      onClick={() => onLanjutkan(u)}>Lanjutkan</button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
