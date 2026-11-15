/**
 * FinanceDesk — Keuangan › Beranda Keuangan › **Perlu Tindakan** (MN-T2; dulu "Meja Finance" FASE E-8 apa adanya).
 *
 * SATU daftar berkelompok. Tiap kelompok tampil hanya bila pengguna memegang izin modul sumbernya (`PERLU_TINDAKAN`)
 * DAN kelompok itu berisi; tiap baris punya satu tombol yang membuka layar penanganannya (dua dikerjakan langsung di
 * sini seperti dulu: terbitkan Faktur Pajak dan catat kwitansi lewat `ARReceiptModal`). Sumber angka tidak berubah:
 *  · antrean meja `GET /api/finance/desk` (`payment_variance.decide`) — uang masuk, selisih bayar, faktur pajak, nota
 *    kredit, hutang (PO) jatuh tempo ≤ 7 hari, denda, piutang lewat jatuh tempo, sample berbayar, retur;
 *  · papan hutang `GET /api/home/finance` (`contra_bon.view` / `vendor_bill.view`, PK-17) — kontrabon menunggu
 *    verifikasi/ACC/sengketa, tagihan pemasok menunggu ACC (`approval_backlog_service`, INV-HOME-01);
 *  · `GET /api/finance/posting-failures` (`accounting.view`) — posting gagal (lencana yang sama di menu Tutup Buku).
 * Keadaan: memuat · galat per sumber (kotak merah + Coba lagi; TIDAK pernah berbunyi "tidak ada yang perlu ditindak")
 * · kosong "Tidak ada yang perlu ditindak hari ini." hanya bila semua sumber terbaca dan semua kelompok kosong.
 * Uang muka pesanan belum dikirim (dulu antrean pantau di meja ini) = kolom di Piutang › Titipan & Saldo Kredit.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { ListChecks, RefreshCw } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import EntityScopeBanner from "../../components/EntityScopeBanner";
import { apiErrorText } from "../../utils/apiError";
import { can } from "../../config/roles";
import { useAppNav } from "../../context/AppNavContext";
import { boardRowLink } from "../../config/waitingBoards";
import DeskQueueCard from "../sales_admin/DeskQueueCard";
import SoTrackerCard from "../sales_admin/SoTrackerCard";
import { financeDesk, issueTaxInvoice, rowLink, soTrackerLink } from "../sales_admin/workDeskApi";
import ARReceiptModal from "../crm/ARReceiptModal";

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

export default function FinanceDesk({ currentUser, selectedEntity = "all", onOpenDocument }) {
  const perms = currentUser?.permissions || {};
  const { go, canOpen } = useAppNav();
  const pakaiDesk = can(perms, "payment_variance", "decide");
  const pakaiPapan = can(perms, "contra_bon", "view") || can(perms, "vendor_bill", "view");
  const pakaiPosting = can(perms, "accounting", "view") && canOpen("posting-failures");
  const [src, setSrc] = useState({ desk: null, boards: null, posting: null });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState("");
  const [busyRef, setBusyRef] = useState("");
  const [payRow, setPayRow] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
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
    setLoading(false);
  }, [selectedEntity, pakaiDesk, pakaiPapan, pakaiPosting]);
  useEffect(() => { load(); }, [load]);

  const groups = useMemo(() => susunKelompok(perms, src, canOpen), [perms, src, canOpen]);

  function flash(msg) { setToast(msg); setTimeout(() => setToast(""), 5000); }

  async function doIssueTax(row) {
    setBusyRef(row.ref_id);
    try {
      const res = await issueTaxInvoice(row.ref_id);
      flash(`Faktur Pajak ${res?.number || ""} diterbitkan untuk ${row.number}.`);
      await load();
    } catch (e) {
      setErrors((x) => ({ ...x, aksi: apiErrorText(e, "Gagal menerbitkan Faktur Pajak.") }));
    } finally { setBusyRef(""); }
  }

  function handleAction(row) {
    if (row.action_kind === "issue_tax") { doIssueTax(row); return; }
    if (row.action_kind === "receipt") {
      setPayRow({ customer_id: row.ref_id, customer_name: row.title, order_id: row.order_id });
      return;
    }
    if (row._view) { go(row._view, { preset: { from: { view: "finance-desk" } } }); return; }
    if (row._link) { onOpenDocument?.(row._link); return; }
    onOpenDocument?.(rowLink(row, row._queue, "finance"));
  }

  const SUMBER = { desk: "antrean uang masuk & pajak", boards: "antrean hutang pemasok", posting: "posting gagal",
    aksi: "aksi" };
  const galat = Object.entries(errors);
  const totalItems = groups.reduce((s, g) => s + g.count, 0);
  const adaSumber = pakaiDesk || pakaiPapan || pakaiPosting;

  return (
    <div data-testid="finance-desk" className="grid grid-cols-[minmax(0,1fr)] gap-3">
      {toast && (
        <div className="notice-bar success" data-testid="fin-desk-toast">
          <span>{toast}</span><button type="button" onClick={() => setToast("")} aria-label="Tutup">×</button>
        </div>
      )}
      <EntityScopeBanner testId="fin-desk-scope" />
      <section className="section-card">
        <div className="section-head">
          <div className="flex min-w-0 items-center gap-2">
            <ListChecks size={15} aria-hidden="true" className="text-kn-action" />
            <h2 data-testid="fin-desk-title">Perlu Tindakan</h2>
            {!loading && totalItems > 0 && (
              <span className="text-fs-12 text-kn-text-2" data-testid="fin-desk-summary">
                {totalItems} dokumen · {groups.length} kelompok</span>
            )}
          </div>
          <button type="button" data-testid="fin-desk-refresh" className="icon-button" onClick={load} aria-label="Muat ulang">
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
        </div>
        <p className="section-body text-fs-12 text-kn-text-2">
          Pekerjaan uang yang menunggu Anda, dikelompokkan per jenis. Kelompok hanya tampil bila Anda berhak atas
          modulnya dan ada isinya; tiap baris membuka layar penanganannya.</p>
      </section>

      {galat.map(([k, msg]) => (
        <ErrorNotice key={k} testId={`fin-desk-error-${k}`} onRetry={load}
          onDismiss={k === "aksi" ? () => setErrors((x) => { const n = { ...x }; delete n.aksi; return n; }) : undefined}
          message={k === "aksi" ? msg : `Daftar ${SUMBER[k]} tidak bisa dimuat. ${msg}`} />
      ))}

      {loading && groups.length === 0 ? (
        <div className="section-card section-pad text-center text-fs-13 text-kn-text-2" role="status" data-testid="fin-desk-loading">
          Menyusun daftar pekerjaan…</div>
      ) : groups.length === 0 ? (
        !galat.length && (
          <div className="section-card section-pad text-center text-fs-13 text-kn-text-2" data-testid="fin-desk-empty">
            {adaSumber ? TEKS_KOSONG : "Anda belum punya akses ke antrean keuangan. Minta Admin menambahkan akses yang sesuai."}
          </div>
        )
      ) : (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-3" data-testid="fin-desk-groups">
          {groups.map((g) => (
            <DeskQueueCard key={g.id} queue={g} busyRef={busyRef} loading={loading}
              testPrefix="fin-desk" rowTestPrefix={`fin-desk-${g.id}`} onAction={handleAction} />
          ))}
        </div>
      )}

      {pakaiDesk && (
        <SoTrackerCard desk="finance" selectedEntity={selectedEntity} testPrefix="fin-desk" onOpen={(r) => onOpenDocument?.(soTrackerLink(r))} />
      )}

      {payRow && (
        <ARReceiptModal
          customerId={payRow.customer_id}
          customerName={payRow.customer_name}
          preselectOrderId={payRow.order_id}
          onClose={() => setPayRow(null)}
          onDone={(msg) => { setPayRow(null); flash(msg || "Kwitansi tercatat."); load(); }}
        />
      )}
    </div>
  );
}
