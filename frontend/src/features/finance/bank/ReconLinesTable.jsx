/**
 * FASE G-8 — ReconLinesTable: daftar mutasi bank dengan SKOR + ALASANNYA, usulan
 * 1-klik, gabung N:1 (beberapa mutasi → satu transaksi buku), titipan dana, dan
 * abaikan/lepas.
 *
 * Prinsip layar ini: pengguna harus tahu KENAPA sistem menganggap sesuatu cocok.
 * Karena itu skor selalu ditampilkan bersama daftar alasan berpoin.
 *
 * Fase 4 · R2 (L-03) — pop-up "Gabung ke 1 transaksi" `.modal-card` buatan sendiri → `FormModal` baku (layar penuh
 * di HP). Testid tetap (`recon-group-modal`, `recon-group-cand-*`, `recon-group-error`).
 *
 * PM-T3 — mutasi yang memuat kode bayar pesanan (`pay_code_hits`) diberi lencana "Kode bayar {kode}"; bila pesanan itu
 * belum punya kwitansi yang menunggu dicocokkan, tombol **Catat sebagai kwitansi** (MN-T3: semua mutasi masuk belum cocok; `onRecordReceipt`) membuka
 * form kwitansi terisi. Lencana & tombol ada di sel Keterangan (kolom Tindakan tidak melebar).
 *
 * F1 (kwitansi otomatis dari mutasi) — penanda `f1` baris: kartu → alasan berkalimat di sel Keterangan
 * (`recon-f1-reason-{id}`); kwitansi dibatalkan → tanda "tidak diproses otomatis lagi" (`recon-f1-voided-{id}`); kwitansi
 * otomatis jalur B/C (`match_type` `auto_receipt`) → lencana "Kwitansi otomatis" (`recon-f1-auto-{id}`), kwitansi dicatat
 * dari mutasi → "Kwitansi dari mutasi". "Batalkan kwitansi" (`recon-f1-void-{id}`, `onVoidReceipt` — pemanggil hanya
 * memberikannya kepada pemegang `ar_receipt.void` + `cash.create`) untuk kwitansi yang LAHIR dari mutasi (R8).
 */
import { useMemo, useState } from "react";
import {
  Link2, Unlink, EyeOff, Eye, ArrowDownLeft, ArrowUpRight, PiggyBank, Info, Layers,
  Receipt, Percent, Hash, FilePlus2, AlertTriangle, XCircle,
} from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { formatCurrency, formatDate } from "../../../utils/formatters";
import { AskKnButton } from "../../../components/AskKnButton";
import ErrorNotice from "../../../components/ErrorNotice";
import StatusBadge from "../../../components/StatusBadge";
import FormModal from "../../../components/FormModal";
import { apiErrorText } from "../../../utils/apiError";
import { askConfirm } from "../../../services/confirmService";
import ReconPayablePicker from "./ReconPayablePicker";   // MN-T3 — pilih dokumen, bayar lewat satu form Bayar pemasok
import { can } from "../../../config/roles";
import useListSearch from "@/hooks/useListSearch";
import { confirmMoney } from "../../../utils/moneyConfirm";   // pelatihan 18 Nov — `02` N5 (aksi uang berkonfirmasi)
import { useEntityScope } from "../../../context/EntityScopeContext";
import { badgeLabel } from "../../sales_admin/workDeskApi";
import { kwitansiDariMutasi } from "./bankLineReceiptApi";

// PK-42 (UX-18) — satu pemformat tanggal WIB bersama (`utils/formatters`); dulu zona perangkat / bentuk sendiri.
const fmtDate = (s) => formatDate(s);

const STATUS_PILL = {
  unmatched: ["bg-[#FFF4E5] text-[#B26A00]", "Perlu keputusan"],
  matched: ["bg-[#EAF7EE] text-[#1B7F4B]", "Tercocok"],
  ignored: ["bg-[#F0F0F2] text-[#8E8E93]", "Diabaikan"],
  holding: ["bg-[#E8F1FF] text-[#0058CC]", "Dititipkan"],
};

const KIND_LABEL = { "1:1": "satu-satu", "1:N": "1 transfer → banyak", "N:1": "banyak → 1" };
function ScoreBadge({ score, explain, testId }) {
  const [open, setOpen] = useState(false);
  const s = Number(score || 0);
  const tone = s >= 80 ? "bg-[#EAF7EE] text-[#1B7F4B]"
    : s >= 60 ? "bg-[#FFF4E5] text-[#B26A00]" : "bg-[#F0F0F2] text-[#8E8E93]";
  return (
    <div className="relative">
      <button type="button" data-testid={testId} onClick={() => setOpen((v) => !v)}
        className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold ${tone}`}>
        {s ? s.toFixed(0) : "—"} <Info size={10} />
      </button>
      {open && (
        <div className="absolute z-20 mt-1 w-[260px] rounded-lg border border-[#E5E5EA] bg-white p-2 shadow-lg"
          data-testid={`${testId}-explain`}>
          <p className="text-[10px] font-bold uppercase text-[#8E8E93] mb-1">Alasan skor</p>
          {(explain || []).length === 0 ? (
            <p className="text-[11px] text-[#8E8E93]">Belum dihitung — tekan “Cocokkan otomatis”.</p>
          ) : (explain || []).map((e, i) => (
            <div key={i} className="flex items-start justify-between gap-2 text-[11px] py-0.5">
              <span className="text-[#1C1C1E]">{e.label}</span>
              <span className="font-semibold text-[#0058CC] tabular-nums">
                +{Number(e.points || 0).toFixed(0)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ReconLinesTable({ lines, busy, onAction, onOpenMatch, onReload,
  onError, onNotify, onRecordReceipt = null, recordBlockReason = "", perms = {}, canEdit = true, onVoidReceipt = null }) {
  // Uji peran kustom 18 Nov (agen A) — cocokkan/lepas/abaikan/titipkan/biaya & bunga bank = `cash.create` di server
  // (routers/bank_reconciliation.py). Pemegang lihat saja (`canEdit=false`) tidak lagi melihat tombol yang pasti 403.
  // MN-T3 — "Bayar pemasok" dari mutasi keluar hanya bagi pemegang izin bayar dokumennya.
  const canPaySupplier = (can(perms, "contra_bon", "pay") && can(perms, "contra_bon", "view"))
    || (can(perms, "vendor_bill", "pay") && can(perms, "vendor_bill", "view"));
  const srch = useListSearch(lines || [], null, { testId: "recon-lines", pageSize: 50, placeholder: "Cari keterangan / nominal / status…" });
  const [picked, setPicked] = useState([]);
  const [groupTxn, setGroupTxn] = useState(null);   // { candidates, total }
  // FASE G-7 US8 — baris dana KELUAR bisa langsung melunasi satu kontrabon.
  const [cbLine, setCbLine] = useState(null);
  // INV-UI-03 — modal WAJIB menampilkan penolakannya sendiri: bilah error layar
  // induk berada di belakang lapisan modal ini, jadi tak terlihat pengguna.
  const [mErr, setMErr] = useState("");

  const selectable = useMemo(
    () => (lines || []).filter((l) => l.status === "unmatched"), [lines]);
  const pickedLines = useMemo(
    () => selectable.filter((l) => picked.includes(l.id)), [selectable, picked]);
  const pickedTotal = useMemo(
    () => pickedLines.reduce((a, l) => a + Number(l.amount || 0), 0), [pickedLines]);

  function toggle(id) {
    setPicked((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }

  async function openGroup() {
    setMErr("");
    try {
      const first = pickedLines[0];
      // Uji rekonsiliasi R5 (18 Nov) — kandidat `group` dinilai terhadap TOTAL mutasi terpilih (dulu terhadap nominal
      // mutasi pertama saja, sehingga transaksi yang menampung semua bagiannya tidak pernah tampil).
      const r = await axios.get(`${API}/bank-reconciliation/lines/${first.id}/candidates`,
        { params: { limit: 25, mode: "group", total: pickedTotal } });
      setGroupTxn({ candidates: r.data?.candidates || [], total: pickedTotal });
    } catch (e) { setMErr(apiErrorText(e)); onError?.(e); }
  }

  async function doGroup(txnId) {
    try {
      const r = await axios.post(`${API}/bank-reconciliation/match-group`,
        { line_ids: pickedLines.map((l) => l.id), txn_id: txnId });
      onNotify(`${r.data.lines} mutasi digabung ke transaksi ${r.data.txn_number} `
        + `(${formatCurrency(r.data.allocated_total)}).`);
      setPicked([]); setGroupTxn(null);
      await onReload();
    } catch (e) { setMErr(apiErrorText(e)); onError?.(e); }
  }

  // Pelatihan 18 Nov (`02_STANDAR` N5) — tiga tombol baris yang MELAHIRKAN kas + jurnal baru (biaya bank, bunga bank,
  // titipkan) dulu langsung memposting sekali klik. Kini bertanya dulu dengan nominal, PT, dan jurnal yang terbit.
  const { entities = [] } = useEntityScope() || {};
  const JURNAL_BARIS = {
    charge: {
      title: "Catat biaya bank?", confirmLabel: "Catat biaya bank", action: "book-charge", body: { kind: "charge" },
      effect: (l) => `Mutasi keluar "${l.description || "tanpa keterangan"}" dibukukan sebagai biaya administrasi bank: `
        + "kas keluar dari rekening ini dan jurnal Dr Beban Adm Bank / Cr Bank.",
      done: "Biaya bank dibukukan (Dr Beban Adm Bank / Cr Bank).",
    },
    interest: {
      title: "Catat bunga bank?", confirmLabel: "Catat bunga bank", action: "book-charge", body: { kind: "interest" },
      effect: (l) => `Mutasi masuk "${l.description || "tanpa keterangan"}" dibukukan sebagai bunga · jasa giro: `
        + "kas masuk ke rekening ini dan jurnal Dr Bank / Cr Pendapatan Bunga.",
      done: "Bunga · jasa giro dibukukan (Dr Bank / Cr Pendapatan Bunga).",
    },
    holding: {
      title: "Titipkan dana ini?", confirmLabel: "Titipkan dana", action: "holding", body: { note: "" },
      effect: (l) => `Dana masuk "${l.description || "tanpa keterangan"}" belum diketahui pengirimnya: dicatat sebagai `
        + "titipan dana (kas masuk dan jurnal Dr Bank / Cr Titipan) sampai dialokasikan.",
      done: "Dana dititipkan (jurnal Dr Bank / Cr Titipan terbit).",
    },
  };
  async function jurnalBaris(l, jenis) {
    const j = JURNAL_BARIS[jenis];
    const ok = await confirmMoney({ title: j.title, effect: j.effect(l), amount: l.amount, entityId: l.entity_id,
      entities, confirmLabel: j.confirmLabel, testId: `recon-${jenis}-confirm` });
    if (!ok) return;
    await onAction(l.id, j.action, j.body, j.done);
  }

  async function acceptSuggestion(line, sug) {
    await onAction(line.id, "match", { txn_id: sug.id },
      `Mutasi ditautkan ke ${sug.number} (skor ${Number(sug.score).toFixed(0)}).`);
  }

  return (
    <>
      {pickedLines.length >= 2 && (
        <div className="mb-2 flex items-center justify-between gap-3 rounded-lg border border-[#CBDCF7] bg-[#F2F7FF] px-3 py-2"
          data-testid="recon-group-bar">
          <span className="text-[12px] text-[#1C1C1E]">
            <b>{pickedLines.length} mutasi</b> dipilih · total{" "}
            <b>{formatCurrency(pickedTotal)}</b> — bisa digabung ke SATU transaksi buku.
          </span>
          <div className="flex gap-2">
            <button className="secondary-button" data-testid="recon-group-clear"
              onClick={() => setPicked([])}>Bersihkan</button>
            <button className="primary-button" data-testid="recon-group-open" onClick={openGroup}>
              <Layers size={14} /> Gabung ke 1 transaksi
            </button>
          </div>
        </div>
      )}

      <div className="rounded-lg border border-[#E5E5EA] overflow-x-auto" data-testid="recon-lines-table">
        {srch.toolbar}
        <table className="w-full text-[12px]">
          <thead>
            <tr className="text-left text-[10px] font-bold uppercase text-[#8E8E93] bg-[#FAFBFC] border-b border-[#EFF0F2]">
              <th className="px-2 py-2 w-8"> </th>
              <th className="px-3 py-2">Tanggal</th>
              <th className="px-3 py-2">Keterangan</th>
              <th className="px-3 py-2 text-right">Nominal</th>
              <th className="px-3 py-2">Skor</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Transaksi buku</th>
              <th className="px-3 py-2 text-right">Tindakan</th>
            </tr>
          </thead>
          <tbody>
            {srch.shown.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-center text-[#8E8E93]">
                  Belum ada mutasi untuk akun ini. Tekan “Impor mutasi bank” untuk menempel
                  atau mengunggah rekening koran.
                </td>
              </tr>
            ) : srch.pageRows.map((l) => {
              const [pill, plabel] = STATUS_PILL[l.status] || STATUS_PILL.unmatched;
              const sugs = l.suggestions || [];
              const f1 = l.f1 || {};
              const dariMutasi = kwitansiDariMutasi(l);
              return (
                <tr key={l.id} data-testid={`recon-line-${l.id}`}
                  className="border-b border-[#F5F5F7] last:border-0 align-top">
                  <td className="px-2 py-2">
                    {canEdit && l.status === "unmatched" && (
                      <input type="checkbox" data-testid={`recon-pick-${l.id}`}
                        checked={picked.includes(l.id)} onChange={() => toggle(l.id)} />
                    )}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">{fmtDate(l.stmt_date)}</td>
                  <td className="px-3 py-2 max-w-[260px]">
                    <p className="truncate" title={l.description}>{l.description || "—"}</p>
                    {l.counterparty && (
                      <p className="text-[10px] text-[#8E8E93] truncate">Pihak: {l.counterparty}</p>
                    )}
                    {l.ref && <p className="text-[10px] text-[#0058CC]">Referensi: {l.ref}</p>}
                    {/* PM-T3 — kode bayar pesanan di berita transfer */}
                    {(l.pay_code_hits || []).length > 0 && (
                      <div className="mt-1 flex flex-wrap items-center gap-1" data-testid={`recon-paycodes-${l.id}`}>
                        {(l.pay_code_hits || []).map((h) => (
                          <span key={h.code} className="status-pill bg-kn-special-soft text-kn-special-text"
                            data-testid={`recon-paycode-${l.id}-${h.code}`}
                            title={`Pesanan ${h.order_number || ""}${h.customer_name ? ` · ${h.customer_name}` : ""}`}>
                            <Hash size={12} aria-hidden="true" />Kode bayar {h.code}
                          </span>
                        ))}
                      </div>
                    )}
                    {/* F1 — mutasi berkode yang tidak cocok sempurna: alasan kartunya (antrean "Mutasi berkode perlu dicek"). */}
                    {l.status === "unmatched" && f1.status === "kartu" && (
                      <p className="mt-1 flex items-start gap-1 text-fs-12 text-kn-warning-text" data-testid={`recon-f1-reason-${l.id}`}>
                        <AlertTriangle size={12} className="mt-0.5 shrink-0" aria-hidden="true" />
                        <span className="min-w-0 break-words whitespace-normal">
                          <b>{badgeLabel(f1.alasan_kode) || "Perlu dicek"}:</b> {f1.alasan || "belum bisa menjadi kwitansi otomatis."}
                        </span>
                      </p>
                    )}
                    {f1.status === "dibatalkan" && (
                      <p className="mt-1 text-fs-12 text-kn-text-2 whitespace-normal break-words" data-testid={`recon-f1-voided-${l.id}`}>
                        {f1.alasan || "Kwitansi dari mutasi ini dibatalkan."} Tidak diproses otomatis lagi.
                      </p>
                    )}
                    {/* MN-T3 — tiap mutasi MASUK belum cocok: "Catat sebagai kwitansi" (form Terima pembayaran; pelanggan &
                        pesanan terisi dari kode bayar bila ada, selain itu langkah Pilih pelanggan). PM-T3 tetap: bila
                        semua pesanan berkode bayar di mutasi ini sudah punya kwitansi menunggu → cocokkan saja (tanpa tombol). */}
                    {l.status === "unmatched" && l.direction === "in" && onRecordReceipt
                      && !((l.pay_code_hits || []).length && (l.pay_code_hits || []).every((h) => h.has_open_receipt)) && (
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <button type="button" className="secondary-button btn-sm whitespace-nowrap"
                          data-testid={`recon-record-receipt-${l.id}`} disabled={Boolean(recordBlockReason)}
                          onClick={() => onRecordReceipt(l, (l.pay_code_hits || []).find((h) => !h.has_open_receipt) || null)}>
                          <FilePlus2 size={12} aria-hidden="true" /> Catat sebagai kwitansi
                        </button>
                        {recordBlockReason && (
                          <span className="text-fs-12 text-kn-text-2" data-testid={`recon-record-receipt-reason-${l.id}`}>
                            {recordBlockReason}
                          </span>
                        )}
                      </div>
                    )}
                    {canEdit && sugs.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1" data-testid={`recon-suggestions-${l.id}`}>
                        {sugs.map((s) => (
                          <button key={s.id} data-testid={`recon-accept-${l.id}-${s.id}`}
                            className="rounded border border-[#CBDCF7] bg-[#F2F7FF] px-1.5 py-0.5 text-[10px] text-[#0058CC] hover:bg-[#E4EEFC]"
                            disabled={busy === l.id + "match"}
                            onClick={() => acceptSuggestion(l, s)}>
                            Terima usulan: {s.number} · {formatCurrency(s.amount)} (skor{" "}
                            {Number(s.score).toFixed(0)})
                          </button>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums whitespace-nowrap">
                    <span className={`inline-flex items-center gap-1 ${
                      l.direction === "in" ? "text-[#1B7F4B]" : "text-[#C0392B]"}`}>
                      {l.direction === "in" ? <ArrowDownLeft size={12} /> : <ArrowUpRight size={12} />}
                      {formatCurrency(l.amount)}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <ScoreBadge score={l.score} explain={l.score_explain}
                      testId={`recon-score-${l.id}`} />
                  </td>
                  <td className="px-3 py-2">
                    <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold ${pill}`}
                      data-testid={`recon-status-${l.id}`}>{plabel}</span>
                    {l.match_kind && (
                      <p className="mt-0.5 text-[10px] text-[#8E8E93]">
                        {l.match_type === "charge"
                          ? `${l.charge?.label || "Biaya bank"} · akun ${l.charge?.account_code || ""}`
                          : `${KIND_LABEL[l.match_kind] || l.match_kind}${
                            l.match_type === "auto" ? " · otomatis" : ""}`}
                      </p>
                    )}
                    {l.status === "matched" && dariMutasi && (
                      <div className="mt-0.5">
                        {l.match_type === "auto_receipt"
                          ? <StatusBadge tone="success" icon="check" label="Kwitansi otomatis" testId={`recon-f1-auto-${l.id}`} />
                          : <StatusBadge tone="info" icon="check" label="Kwitansi dari mutasi" testId={`recon-f1-manual-${l.id}`} />}
                      </div>
                    )}
                    {l.status === "holding" && (
                      <p className="mt-0.5 text-[10px] text-[#0058CC]">
                        Sisa {formatCurrency(l.holding_remaining || 0)}
                      </p>
                    )}
                  </td>
                  <td className="px-3 py-2 text-[11px]">
                    {(l.matched_txns || []).length > 0 ? (l.matched_txns || []).map((t) => (
                      <p key={t.id} className="text-[#1B7F4B]">
                        {t.number} · {formatCurrency(t.allocated)}
                      </p>
                    )) : l.status === "holding" ? (
                      <p className="text-[#0058CC]">{l.holding?.cash_number || "titipan"}</p>
                    ) : <span className="text-[#C7C7CC]">—</span>}
                  </td>
                  <td className="px-3 py-2 text-right whitespace-nowrap">
                    {canEdit && l.status === "matched" && (
                      <button data-testid={`recon-unmatch-${l.id}`} className="link-button"
                        style={{ color: "#B4231F" }} disabled={busy === l.id + "unmatch"}
                        onClick={async () => {
                          // Uji adversarial 18 Nov (O3, N5): melepas baris biaya/bunga bank MEMBATALKAN kas & jurnalnya
                          // (pembalik terbit) — dulu tanpa konfirmasi, padahal mencatatnya bertanya dulu.
                          const kasBank = ["charge", "interest"].includes(l.match_type) || !!l.charge?.cash_txn_id;
                          if (kasBank && !(await askConfirm({
                            title: "Lepas dan batalkan pembukuan biaya/bunga bank?",
                            message: `Baris ${formatCurrency(l.amount)} kembali ke antrean; transaksi kas `
                              + `${l.charge?.cash_number || ""} dan jurnalnya dibatalkan (jurnal pembalik terbit).`,
                            confirmLabel: "Lepas & batalkan", danger: true,
                          }))) return;
                          onAction(l.id, "unmatch", {}, kasBank ? "Tautan dilepas; kas & jurnal biaya/bunga bank dibatalkan."
                            : "Tautan dilepas.");
                        }}>
                        <Unlink size={12} /> Lepas
                      </button>
                    )}
                    {/* F1 §5.6 — kwitansi yang lahir dari mutasi ini: lepas + batal dalam satu permintaan (alasan wajib). */}
                    {onVoidReceipt && dariMutasi && (
                      <button type="button" data-testid={`recon-f1-void-${l.id}`} className="link-button ml-2 text-kn-danger-text"
                        disabled={busy === l.id + "void-receipt"} onClick={() => onVoidReceipt(l)}>
                        <XCircle size={12} aria-hidden="true" /> Batalkan kwitansi
                      </button>
                    )}
                    {canEdit && l.status === "ignored" && (
                      <button data-testid={`recon-unignore-${l.id}`} className="link-button"
                        disabled={busy === l.id + "unignore"}
                        onClick={() => onAction(l.id, "unignore", {}, "Baris dikembalikan ke antrean.")}>
                        <Eye size={12} /> Batal abaikan
                      </button>
                    )}
                    {l.status === "unmatched" && (
                      <div className="flex items-center gap-2 justify-end flex-wrap">
                        {canEdit && (
                          <button data-testid={`recon-matchbtn-${l.id}`} className="link-button"
                            onClick={() => onOpenMatch(l)}>
                            <Link2 size={12} /> Cocokkan
                          </button>
                        )}
                        {canEdit && l.direction === "in" && (
                          <button data-testid={`recon-holding-${l.id}`} className="link-button"
                            style={{ color: "#0058CC" }} disabled={busy === l.id + "holding"}
                            onClick={() => jurnalBaris(l, "holding")}>
                            <PiggyBank size={12} /> Titipkan
                          </button>
                        )}
                        {/* Baris yang MEMANG tidak ada di buku: biaya adm bank & bunga/jasa
                            giro. Tanpa jalur ini satu-satunya pilihan adalah "Abaikan",
                            sehingga bebannya hilang dari laba rugi dan selisih rekening vs
                            buku tidak pernah bisa nol. */}
                        {l.direction === "out" ? (
                          <>
                            {canEdit && (
                              <button data-testid={`recon-charge-${l.id}`} className="link-button"
                                style={{ color: "#B26A00" }} disabled={busy === l.id + "book-charge"}
                                onClick={() => jurnalBaris(l, "charge")}>
                                <Receipt size={12} /> Catat biaya bank
                              </button>
                            )}
                            {/* FASE G-7 US8 + MN-T3 — uang keluar untuk pemasok: tunjuk kontrabon/tagihannya, lalu satu form
                                Bayar pemasok (kas lahir + baris mutasi tertaut). */}
                            {canPaySupplier && (
                              <button data-testid={`recon-contrabon-${l.id}`} className="link-button"
                                onClick={() => setCbLine(l)}>
                                <Receipt size={12} /> Bayar pemasok
                              </button>
                            )}
                          </>
                        ) : canEdit && (
                          <button data-testid={`recon-interest-${l.id}`} className="link-button"
                            style={{ color: "#1B7F4B" }} disabled={busy === l.id + "book-charge"}
                            onClick={() => jurnalBaris(l, "interest")}>
                            <Percent size={12} /> Catat bunga bank
                          </button>
                        )}
                        {canEdit && (
                          <button data-testid={`recon-ignore-${l.id}`} className="link-button"
                            style={{ color: "#8E8E93" }} disabled={busy === l.id + "ignore"}
                            onClick={() => onAction(l.id, "ignore", { note: "" }, "Baris diabaikan.")}>
                            <EyeOff size={12} /> Abaikan
                          </button>
                        )}
                        {/* AG-T3 — tanya asisten soal mutasi ini (Asisten Keuangan; tampil menurut izin). */}
                        <AskKnButton type="bank_line" id={l.id} label={`${formatDate(l.stmt_date)} · ${l.description || ""}`}
                          buttonLabel="Tanya asisten" className="link-button" />
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {groupTxn && (
        <FormModal open onClose={() => setGroupTxn(null)} icon={Layers}
          title={`Gabung ${pickedLines.length} mutasi ke satu transaksi buku`}
          subtitle={(
            <>
              Total mutasi terpilih <b>{formatCurrency(groupTxn.total)}</b> — pilih transaksi buku
              yang nilainya mencukupi.
            </>
          )}
          testId="recon-group-modal">
          {mErr && (
            <ErrorNotice message={mErr} onDismiss={() => setMErr("")}
              testId="recon-group-error" />
          )}
          <div className="rounded border border-[#EFF0F2] sm:max-h-[320px] sm:overflow-auto">
            {groupTxn.candidates.length === 0 ? (
              <div className="p-4 text-center text-[12px] text-[#8E8E93]">
                Tidak ada transaksi buku yang cocok arah & rentang tanggalnya.
              </div>
            ) : groupTxn.candidates.map((t) => (
              <button type="button" key={t.id} data-testid={`recon-group-cand-${t.id}`}
                className="flex w-full flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-[#F5F5F7] px-3 py-2 text-left hover:bg-[#F7F8FA]"
                disabled={Number(t.outstanding) + 0.01 < groupTxn.total}
                onClick={() => doGroup(t.id)}>
                <span className="min-w-0 text-[12px]">
                  <b>{t.number}</b> · {fmtDate(t.txn_date)}{" "}
                  <span className="text-[#8E8E93]">{t.description || ""}</span>
                  {/* Uji rekonsiliasi R5 — alasan teratas (mis. "Sisa transaksi pas sama dengan total mutasi terpilih"). */}
                  {(t.explain || []).length > 0 && (
                    <span className="block text-[10px] text-[#6B6B73]">
                      {t.explain.map((e) => `${e.label} (+${Number(e.points).toFixed(0)})`).join(" · ")}
                    </span>
                  )}
                </span>
                <span className="text-[12px] font-semibold whitespace-nowrap">
                  sisa {formatCurrency(t.outstanding)}
                  {t.score !== undefined && <span className="ml-2 text-[10px] text-[#8E8E93]">skor {Number(t.score).toFixed(0)}</span>}
                </span>
              </button>
            ))}
          </div>
        </FormModal>
      )}
      {cbLine && (
        <ReconPayablePicker line={cbLine} perms={perms} onClose={() => setCbLine(null)}
          onDone={(note) => { setCbLine(null); onNotify(note); onReload?.(); }}
          onError={onError} />
      )}
    </>
  );
}
