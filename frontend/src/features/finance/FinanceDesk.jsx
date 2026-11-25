/**
 * FinanceDesk — Keuangan › Beranda Keuangan › **Perlu Tindakan** (MN-T2; dulu "Meja Finance" FASE E-8 apa adanya).
 *
 * SATU daftar berkelompok. Tiap kelompok tampil hanya bila pengguna memegang izin modul sumbernya (`PERLU_TINDAKAN`)
 * DAN kelompok itu berisi; tiap baris punya satu tombol. Aksi di tempat (`IN_PLACE`): terbitkan Faktur Pajak, terima
 * pembayaran lewat satu form `ReceivePaymentModal` (MN-T3), dan "Bayar" hutang jatuh tempo yang membuka kartu pemasok
 * (tagihannya dibayar dari sana dengan satu form `PaySupplierModal`). Aksi lain membuka pop-up rincian baris dulu.
 * MN-T3 — nama pelanggan baris "Uang masuk perlu dicatat" membuka kartu pelanggan. Sumber angka:
 *  · antrean meja `GET /api/finance/desk` (`payment_variance.decide`) — uang masuk, selisih bayar, faktur pajak, nota
 *    kredit, hutang (PO) jatuh tempo ≤ 7 hari, denda, piutang lewat jatuh tempo, sample berbayar, retur;
 *  · papan hutang `GET /api/home/finance` (`contra_bon.view` / `vendor_bill.view`, PK-17) — kontrabon menunggu
 *    verifikasi/ACC/sengketa, tagihan pemasok menunggu ACC (`approval_backlog_service`, INV-HOME-01);
 *  · `GET /api/finance/posting-failures` (`accounting.view`) — posting gagal (lencana yang sama di menu Tutup Buku).
 * Keadaan: memuat · galat per sumber (kotak merah + Coba lagi; TIDAK pernah berbunyi "tidak ada yang perlu ditindak")
 * · kosong "Tidak ada yang perlu ditindak hari ini." hanya bila semua sumber terbaca dan semua kelompok kosong.
 * Uang muka pesanan belum dikirim (dulu antrean pantau di meja ini) = kolom di Piutang › Titipan & Saldo Kredit.
 *
 * Meja gelombang 1 (spek 2026-11-25 §5.1) — kerangka `DeskFrame` (judul halaman + ikon ?, muat ulang global, pemulihan
 * gulir). Meja ini SUDAH tab hub Beranda Keuangan, jadi tidak menggambar tab Antrean/Pantau sendiri (R4: tanpa tab
 * tingkat ketiga): Pantau (kartu retur internal + Pelacak SO) adalah tab hub saudara `finance-desk-pantau` yang
 * merender komponen ini dengan `tab="pantau"`. Tab itu tampil dengan syarat izin yang sama dengan tab meja
 * (`access_modules.VIEW_ACTION_REQUIREMENTS`: `payment_variance.decide`); di sana hanya antrean meja (untuk daftar
 * "Bukan wewenang" di ikon ?) yang dimuat, bukan papan hutang & posting gagal.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { compareFilledQueues } from "../sales_admin/deskQueueOrder";   // perapian Meja Finance 14 Nov: urutan kelompok
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import EntityScopeBanner from "../../components/EntityScopeBanner";
import { apiErrorText } from "../../utils/apiError";
import { can } from "../../config/roles";
import { useAppNav } from "../../context/AppNavContext";
import { toast } from "@/hooks/use-toast";
import { boardRowLink } from "../../config/waitingBoards";
import DeskQueueCard, { DeskQueueCardSkeleton, inPlaceOf } from "../sales_admin/DeskQueueCard";
import SoTrackerCard from "../sales_admin/SoTrackerCard";
import ReturnDeskSummaryCard, { returnSummaryHasContent, useReturnDeskSummary } from "../home/ReturnDeskSummaryCard";
import DeskFrame, { DESK_GRID_CLASS } from "../desks/DeskFrame";
import { markDeskReturn } from "../desks/deskSession";
import { dedupeFinanceGroups } from "../desks/deskDedupe";
import { financeDesk, issueTaxInvoice, rowLink, soTrackerLink } from "../sales_admin/workDeskApi";
import ReceivePaymentModal from "./payments/ReceivePaymentModal";
import TaxIssueDialog from "./TaxIssueDialog";
import { CustomerCardLink } from "./cards/partyCards";

export const TEKS_KOSONG = "Tidak ada yang perlu ditindak hari ini.";
const POSTING_ROWS = 20;

/**
 * Kelompok Perlu Tindakan, urut tampil. `izin` = salah satu cukup (modul sumber datanya / layar penanganannya);
 * `queues` = id antrean `/finance/desk`; `boards` = kunci papan `/home/finance`; `posting` = daftar posting gagal.
 */
export const PERLU_TINDAKAN = [
  { key: "uang_masuk", label: "Uang masuk perlu dicatat", izin: [["ar_receipt", "create"]],
    queues: ["uang_masuk", "bayar_sebelum_kirim"],
    hint: "Catat kwitansi lalu alokasikan ke tagihan; termasuk pesanan CBD/DP yang tertahan menunggu bayar." },
  { key: "selisih_bayar", label: "Selisih bayar perlu diputus", izin: [["payment_variance", "decide"]],
    queues: ["selisih_bayar"], hint: "Lebih/kurang bayar yang belum diputus. Di luar batas kewenangan → manajer." },
  { key: "faktur_pajak", label: "Faktur pajak perlu terbit", izin: [["tax_invoice", "create"]],
    queues: ["siap_faktur_pajak"], hint: "Pesanan ber-PPN yang belum punya faktur pajak keluaran aktif." },
  { key: "nota_kredit", label: "Nota kredit perlu ditinjau", izin: [["finance_amendment", "review_credit_note"]],
    queues: ["nota_batal_item"], hint: "Nota kredit batal item pesanan khusus menunggu tinjauan: koreksi nilai, terbitkan, atau batalkan." },
  { key: "hutang_jatuh_tempo", label: "Hutang jatuh tempo", izin: [["vendor_bill", "view"]],
    queues: ["hutang_jatuh_tempo"], boards: ["vendor_bill"],
    hint: "Pesanan pembelian belum lunas yang lewat / ≤ 7 hari menuju jatuh tempo, dan tagihan pemasok menunggu ACC." },
  { key: "kontrabon", label: "Kontrabon menunggu", izin: [["contra_bon", "view"]],
    boards: ["contra_bon_verify", "contra_bon_approve", "contra_bon_dispute"],
    hint: "Kontrabon menunggu verifikasi berkas, persetujuan, atau penyelesaian sengketa — pemasok belum bisa dibayar." },
  { key: "posting_gagal", label: "Posting gagal", izin: [["accounting", "view"]], posting: true, view: "posting-failures",
    hint: "Dokumen yang jurnalnya gagal tercatat; perbaiki penyebabnya lalu ulang di Tutup Buku › Posting Gagal." },
  { key: "denda", label: "Denda perlu diterbitkan", izin: [["penalty", "issue"]], queues: ["denda_draft"],
    hint: "Nota denda hasil hitungan sistem; pembebasan → manajer." },
  { key: "piutang_lewat_tempo", label: "Piutang lewat jatuh tempo", izin: [["accounting", "view"], ["penalty", "issue"]],
    queues: ["jatuh_tempo"], hint: "Tagihan pelanggan yang sudah melewati tanggal jatuh tempo." },
  { key: "sample_bayar", label: "Sample berbayar menunggu ACC bayar", izin: [["sample_order", "approve_payment"]],
    queues: ["sample_acc_bayar"], hint: "Pastikan pembayaran atau kesepakatan bayar ada, lalu setujui." },
  { key: "retur_nilai", label: "Retur selesai QC — putuskan nilai", izin: [["sales_return", "decide_compensation"]],
    queues: ["retur_putus_nilai"], hint: "Barang retur sudah diperiksa QC: putuskan kompensasi atau lanjutkan penyelesaian." },
];

export const bolehKelompok = (perms, g) => g.izin.some(([r, a]) => can(perms, r, a));

const boardRows = (b) => (b?.rows || []).map((r) => ({
  ref_type: b.key, ref_id: r.id, number: r.number || "—", title: r.title || "—", subtitle: r.note || b.label || "",
  value: Number(r.amount) || 0, age_days: Number(r.days_waiting) || 0, badge: "", action: "Buka", action_kind: "open",
  row_key: `${b.key}-${r.id}`, _link: boardRowLink(b, r),
}));

const postingRows = (items) => (items || []).map((it) => ({
  ref_type: it.kind, ref_id: it.id, number: it.number || "—", title: it.kind_label || "Dokumen",
  subtitle: it.error || "", value: Number(it.amount) || 0, age_days: 0, badge: "", action: "Buka", action_kind: "open",
  row_key: `${it.kind}-${it.id}`, _view: "posting-failures",
}));

/** Susun kelompok tampil dari tiga sumber + izin. Kelompok tanpa baris tidak dikembalikan. */
export function susunKelompok(perms, { desk, boards, posting }, canOpen = () => true) {
  const qmap = Object.fromEntries((desk?.queues || []).map((q) => [q.id, q]));
  const bmap = Object.fromEntries((boards?.waiting_boards || []).map((b) => [b.key, b]));
  const out = [];
  for (const g of PERLU_TINDAKAN) {
    if (!bolehKelompok(perms, g)) continue;
    if (g.view && !canOpen(g.view)) continue;
    const rows = []; let count = 0; let oldest = 0;
    for (const id of g.queues || []) {
      const q = qmap[id];
      if (!q) continue;
      rows.push(...(q.rows || []).map((r) => ({ ...r, _queue: id })));
      count += Number(q.count) || 0;
      oldest = Math.max(oldest, Number(q.oldest_age_days) || 0);
    }
    for (const k of g.boards || []) {
      const b = bmap[k];
      if (!b) continue;
      const br = boardRows(b);
      rows.push(...br);
      count += Number(b.count) || 0;
      oldest = Math.max(oldest, ...br.map((r) => r.age_days), 0);
    }
    if (g.posting && posting) {
      rows.push(...postingRows(posting.items));
      count += Number(posting.total) || 0;
    }
    if (count <= 0 && rows.length === 0) continue;
    out.push({ id: g.key, label: g.label, hint: g.hint, count, shown: rows.length,
      total_value: Math.round(rows.reduce((s, r) => s + (Number(r.value) || 0), 0) * 100) / 100,
      value_kind: "money", value_label: "Nilai", oldest_age_days: oldest, action_label: "Buka", rows });
  }
  return out;
}

const DESK_KEY = "finance";
const P = "fin-desk";
const IN_PLACE = inPlaceOf(["issue_tax", "receipt", "supplier_card"]);
const HELP = (
  <>
    Pekerjaan uang yang menunggu Anda, dikelompokkan per jenis. Kelompok hanya tampil bila Anda berhak atas modulnya
    dan ada isinya; tiap baris membuka layar penanganannya.
  </>
);

export default function FinanceDesk({ currentUser, selectedEntity = "all", onOpenDocument, tab = "antrean" }) {
  const perms = currentUser?.permissions || {};
  const { go, canOpen, openSupplierCard, cardsEnabled } = useAppNav();
  const pantauTab = tab === "pantau";
  // Tab Pantau hanya memuat antrean meja (untuk ikon ?); kartu retur internal & Pelacak SO memuat datanya sendiri.
  const pakaiDesk = can(perms, "payment_variance", "decide");
  const pakaiPapan = !pantauTab && (can(perms, "contra_bon", "view") || can(perms, "vendor_bill", "view"));
  const pakaiPosting = !pantauTab && can(perms, "accounting", "view") && canOpen("posting-failures");
  const [src, setSrc] = useState({ desk: null, boards: null, posting: null });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(true);
  const [refreshingId, setRefreshingId] = useState("");
  const [tick, setTick] = useState(0);
  const busyRef = "";   // aksi terbit faktur kini di pop-up (TaxIssueDialog); tak ada baris yang "sibuk" di antrean
  const [payRow, setPayRow] = useState(null);
  const [issueRow, setIssueRow] = useState(null);   // { row, qid } — pop-up pratinjau terbit faktur pajak

  // `quiet` — muat ulang sesudah aksi: halaman tidak dikosongkan, hanya kartu terkait bertanda (`refreshingId`).
  const load = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setLoading(true);
    const params = selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {};
    const tugas = {
      desk: pakaiDesk ? financeDesk(params) : null,
      boards: pakaiPapan ? axios.get(`${API}/home/finance`, { params }).then((r) => r.data) : null,
      posting: pakaiPosting ? axios.get(`${API}/finance/posting-failures`, { params: { page: 1, page_size: POSTING_ROWS } })
        .then((r) => r.data) : null,
    };
    const hasil = await Promise.all(Object.entries(tugas).map(async ([k, p]) => {
      if (!p) return [k, null, ""];
      try { return [k, await p, ""]; } catch (e) {
        // PK-17 — 403 = peran ini memang tidak berhak atas sumber itu: kelompoknya tidak digambar, bukan galat.
        if (e?.response?.status === 403) return [k, null, ""];
        return [k, null, apiErrorText(e, "gagal dimuat")];
      }
    }));
    setSrc(Object.fromEntries(hasil.map(([k, d]) => [k, d])));
    setErrors(Object.fromEntries(hasil.filter(([, , e]) => e).map(([k, , e]) => [k, e])));
    if (!quiet) setLoading(false);
  }, [selectedEntity, pakaiDesk, pakaiPapan, pakaiPosting]);
  useEffect(() => { load(); }, [load]);

  const groups = useMemo(() => dedupeFinanceGroups(susunKelompok(perms, src, canOpen).map((g) => ({ ...g, rows: g.rows.map((r) => {
    if (r.action_kind === "receipt") {
      return { ...r, action: "Terima pembayaran", _titleNode: <CustomerCardLink id={r.ref_id} name={r.title} perms={perms}
        testId={`fin-desk-customer-${r.row_key || r.ref_id}`} /> };
    }
    if (r._queue === "hutang_jatuh_tempo" && r.supplier_id && cardsEnabled && can(perms, "supplier", "view")) {
      return { ...r, action: "Bayar", action_kind: "supplier_card" };
    }
    return r;
  }) })))
    // Hapus ganda (§5.6) — sesudah penyaringan izin kelompok (`susunKelompok`): hanya antar kartu yang terlihat.
    // Perapian Meja Finance (14 Nov, cabang gifted-cori `01ce23b`): kelompok berisi diurutkan umur tertua → nilai →
    // jumlah; seri mengikuti urutan `PERLU_TINDAKAN`. Kelompok kosong memang tidak tampil (MN-T2), jadi lipatan
    // "antrean kosong" dari perapian itu tidak dipakai.
    .map((g, i) => ({ g, i })).sort((x, y) => compareFilledQueues(x.g, y.g) || x.i - y.i).map((x) => x.g),
  [perms, src, canOpen, cardsEnabled]);

  async function reloadQueue(queueId) {
    setRefreshingId(queueId || "");
    try { await load({ quiet: true }); } finally { setRefreshingId(""); }
  }
  function done(msg, queueId) {
    toast({ title: msg });
    reloadQueue(queueId);
  }

  function open(link) {
    markDeskReturn(DESK_KEY);
    onOpenDocument?.(link);
  }

  /** Layar penanganan baris (aksi pindah layar & "Buka layar penuh"). */
  function navigate(row) {
    if (row._view) { markDeskReturn(DESK_KEY); go(row._view, { preset: { from: { view: "finance-desk" } } }); return; }
    if (row._link) { open(row._link); return; }
    open(rowLink(row, row._queue, DESK_KEY));
  }

  function handleAction(row, queue) {
    const qid = queue?.id || "";
    if (row.action_kind === "issue_tax") { setIssueRow({ row, qid }); return; }
    if (row.action_kind === "receipt") {
      setPayRow({ customer_id: row.ref_id, customer_name: row.title, order_id: row.order_id, qid });
      return;
    }
    if (row.action_kind === "supplier_card") { openSupplierCard(row.supplier_id); return; }
    navigate(row);
  }

  const reloadAll = () => { load(); setTick((t) => t + 1); };
  const SUMBER = { desk: "antrean uang masuk & pajak", boards: "antrean hutang pemasok", posting: "posting gagal",
    aksi: "aksi" };
  const galat = Object.entries(errors);
  const adaSumber = pakaiDesk || pakaiPapan || pakaiPosting;

  const antrean = pantauTab ? null : loading && groups.length === 0 ? (
    <div data-testid={`${P}-loading`} className={DESK_GRID_CLASS}>
      {[0, 1, 2, 3].map((i) => <DeskQueueCardSkeleton key={i} testPrefix={P} index={i} />)}
    </div>
  ) : groups.length === 0 ? (
    !galat.length && (
      <div className="section-card section-pad text-center text-fs-13 text-kn-text-2" data-testid={`${P}-empty`}>
        {adaSumber ? TEKS_KOSONG : "Anda belum punya akses ke antrean keuangan. Minta Admin menambahkan akses yang sesuai."}
      </div>
    )
  ) : (
    <div className={DESK_GRID_CLASS} data-testid={`${P}-groups`}>
      {groups.map((g) => (
        <DeskQueueCard key={g.id} queue={g} busyRef={busyRef} loading={loading || refreshingId === g.id}
          testPrefix={P} rowTestPrefix={`${P}-${g.id}`} stateKey={`${DESK_KEY}:${g.id}`} inPlace={IN_PLACE}
          onAction={handleAction} onOpenFull={(row) => navigate(row)} />
      ))}
    </div>
  );

  // Meja gelombang 1 (§5.1) — kartu retur internal (dulu di atas meja, AppViewRouter) dan Pelacak SO (izin `order.view`).
  // Pantau "kosong" diputuskan dari yang benar-benar tampil: kartu retur hanya bila berizin DAN ada isinya.
  const retSummary = useReturnDeskSummary(selectedEntity, {
    enabled: pantauTab && (can(perms, "sales_return", "view") || can(perms, "interco", "view")), refreshKey: tick,
  });
  const returns = pantauTab && returnSummaryHasContent(retSummary) && (
    <ReturnDeskSummaryCard key="returns" selectedEntity={selectedEntity} summary={retSummary}
      onNavigate={(t) => { markDeskReturn(DESK_KEY); go(t); }} />
  );
  const tracker = pantauTab && can(perms, "order", "view") && (
    <SoTrackerCard key="tracker" desk="finance" selectedEntity={selectedEntity} testPrefix={P} refreshKey={tick}
      showRefresh={false}
      onOpen={(r) => open(soTrackerLink(r))} onOpenFull={(r) => open(soTrackerLink(r))} />
  );
  const pantau = returns || tracker ? (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-3">{returns}{tracker}</div>
  ) : null;

  return (
    <div data-testid="finance-desk" className="grid grid-cols-[minmax(0,1fr)] gap-3">
      <EntityScopeBanner testId="fin-desk-scope" />
      {!pantauTab && galat.map(([k, msg]) => (
        <ErrorNotice key={k} testId={`fin-desk-error-${k}`} onRetry={() => load()}
          onDismiss={k === "aksi" ? () => setErrors((x) => { const n = { ...x }; delete n.aksi; return n; }) : undefined}
          message={k === "aksi" ? msg : `Daftar ${SUMBER[k]} tidak bisa dimuat. ${msg}`} />
      ))}

      <DeskFrame deskKey={DESK_KEY} testPrefix={P} help={HELP} notMine={src.desk?.not_my_desk || []}
        tabsInHub tab={pantauTab ? "pantau" : "antrean"} antrean={antrean} pantau={pantau}
        pantauLoading={retSummary === undefined} ready={!loading} onReload={reloadAll} />

      {issueRow && (
        <TaxIssueDialog
          target={{ kind: "order", id: issueRow.row.ref_id, number: issueRow.row.number, orderNumber: issueRow.row.number,
            customerName: issueRow.row.title, npwp: issueRow.row.customer_npwp || "", entityId: issueRow.row.entity_id,
            dpp: issueRow.row.dpp ?? null, ppnAmount: issueRow.row.ppn_amount, total: issueRow.row.value ?? null }}
          submit={(body) => issueTaxInvoice(issueRow.row.ref_id, body)}
          onClose={() => setIssueRow(null)}
          onDone={(f) => {
            const { row, qid } = issueRow;
            setIssueRow(null);
            done(`Faktur Pajak ${f?.number || ""} diterbitkan untuk ${row.number}.`, qid);
          }} />
      )}

      {payRow && (
        <ReceivePaymentModal
          customerId={payRow.customer_id}
          customerName={payRow.customer_name}
          preselectOrderId={payRow.order_id}
          onClose={() => setPayRow(null)}
          onDone={(msg) => { const qid = payRow.qid; setPayRow(null); done(msg || "Kwitansi tercatat.", qid); }}
        />
      )}
    </div>
  );
}
