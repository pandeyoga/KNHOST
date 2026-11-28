/**
 * Isi pratinjau Opname Kas `OPK-` (Kas & Bank bagian 3, Tugas 4b): fakta opname (PT, status, rekening + jenis kas,
 * dihitung oleh/pada, catatan, perlakuan + karyawan, putusan + alasan), rincian pecahan bila ada, angka yang dipotret
 * (saldo buku, uang fisik, selisih), kas penyesuaian yang terbit sesudah disetujui (nomor, tanggal, arah, jurnal), kalimat
 * kontrol dua orang untuk pembuka, dan riwayat (`jejak`).
 * Data dari `GET /cash-counts/{id}` (opname + `kas` + `kontrol` bila menunggu). Hanya-baca: Hitung / Setujui / Tolak /
 * Batal ada di Kas & Bank › Opname Kas ("Buka layar penuh", registri `cash_count`). Kas penyesuaian tidak punya pratinjau
 * sendiri → teks; nomor jurnalnya membuka Buku Besar.
 */
import StatusBadge from "../../../../components/StatusBadge";
import { useAppNav } from "../../../../context/AppNavContext";
import { useEntityScope } from "../../../../context/EntityScopeContext";
import { entityShortById } from "../../../../utils/entityLabel";
import { formatCurrency, formatDate, formatDateTime } from "../../../../utils/formatters";
import { JEJAK_LABEL, MENUNGGU, jenisKas, selisihTeks, statusOpname } from "../../../finance/cashcount/cashCountShared";
import { keteranganKasPengajuan } from "./CashOutRequestPreview";
import { PreviewFacts, PreviewLines, PreviewTotals } from "../previewParts";

const KOLOM_PECAHAN = [
  { key: "nilai", label: "Pecahan", render: (p) => <span className="tabular-nums">{formatCurrency(p.nilai)}</span> },
  { key: "lembar", label: "Lembar", align: "right", render: (p) => <span className="tabular-nums">{p.lembar}</span> },
  { key: "subtotal", label: "Jumlah", align: "right",
    render: (p) => <span className="tabular-nums">{formatCurrency(p.subtotal ?? (Number(p.nilai) || 0) * (Number(p.lembar) || 0))}</span> },
];

const olehPada = (oleh, pada) => (oleh ? `${oleh}${pada ? ` · ${formatDateTime(pada)}` : ""}` : "");

/** Nomor jurnal kas penyesuaian sebagai tautan ke Buku Besar (pola `JournalStatusBadge`); tanpa id jurnal → teks biasa. */
function JurnalKas({ kas }) {
  const { openDocument } = useAppNav();
  const teks = keteranganKasPengajuan(kas);
  if (kas.status === "void" || kas.gl_status === "failed" || !kas.journal_number || !kas.journal_entry_id) return teks;
  return (
    <button type="button" className="link-button font-mono" data-testid="doc-preview-opk-journal" title="Buka jurnalnya di Buku Besar"
      onClick={() => openDocument({ view: "general-ledger", focus_type: "journal_entry", focus_id: kas.journal_entry_id })}>
      {teks}
    </button>
  );
}

export default function CashCountPreview({ doc }) {
  const { entities } = useEntityScope() || {};
  const st = statusOpname(doc.status);
  const jejak = Array.isArray(doc.jejak) ? doc.jejak : [];
  const pecahan = (Array.isArray(doc.pecahan) ? doc.pecahan : []).map((p, i) => ({ ...p, id: `pecahan-${i}` }));
  const kas = doc.kas || null;
  const menunggu = doc.status === MENUNGGU;
  const tunggu = menunggu && doc.kontrol?.ditolak ? doc.kontrol.pesan : "";
  const perlakuan = doc.perlakuan_label
    ? `${doc.perlakuan_label}${doc.karyawan_nama ? ` · ${doc.karyawan_nama}${doc.karyawan_kode ? ` (${doc.karyawan_kode})` : ""}` : ""}`
    : "";
  return (
    <div className="grid gap-3" data-testid="doc-preview-cash-count">
      {doc.terbit_error && menunggu && (
        <p className="notice-bar warning text-fs-12" data-testid="doc-preview-opk-publish-error">Kas belum terbit: {doc.terbit_error}</p>
      )}
      <PreviewFacts testId="doc-preview-opk-facts" items={[
        { key: "entity", label: "PT", content: doc.entity_id ? entityShortById(entities || [], doc.entity_id, "") : "" },
        { key: "status", label: "Status", content: <StatusBadge status={doc.status} label={st.label} tone={st.tone} icon={st.icon}
          testId="doc-preview-status" /> },
        { key: "account", label: "Rekening", content: [doc.account_name, jenisKas(doc)].filter(Boolean).join(" · ") },
        { key: "counted", label: "Dihitung", content: olehPada(doc.penghitung?.name || doc.created_by, doc.dihitung_pada) },
        { key: "date", label: "Tanggal kas", content: doc.tanggal ? formatDate(doc.tanggal) : "" },
        { key: "note", label: "Catatan", content: doc.catatan },
        { key: "treatment", label: "Perlakuan", content: perlakuan },
        { key: "approver", label: "Disetujui", content: olehPada(doc.disetujui_oleh, doc.disetujui_pada) },
        { key: "rejecter", label: "Ditolak", content: olehPada(doc.ditolak_oleh, doc.ditolak_pada) },
        { key: "reject_reason", label: "Alasan tolak", content: doc.alasan_tolak },
        // Gelombang perbaikan akhir — Batal opname disetujui (siapa/kapan juga di riwayat `jejak` aksi "batal").
        { key: "cancel_reason", label: "Alasan batal", content: doc.status === "batal" ? doc.alasan_batal : "" },
      ]} />
      {tunggu && <p className="text-fs-12 text-kn-text-2" data-testid="doc-preview-opk-control">{tunggu}</p>}
      {pecahan.length > 0 && (
        <PreviewLines testId="doc-preview-opk-denoms" columns={KOLOM_PECAHAN} rows={pecahan} />
      )}
      {kas ? (
        <PreviewFacts testId="doc-preview-opk-cash" items={[
          { key: "number", label: "Kas penyesuaian", content: <span className="font-mono">{kas.number || "—"}</span> },
          { key: "direction", label: "Arah", content: kas.direction === "in" ? "Kas masuk" : kas.direction === "out" ? "Kas keluar" : "" },
          { key: "date", label: "Tanggal", content: kas.txn_date ? formatDate(kas.txn_date) : "" },
          { key: "journal", label: "Jurnal", content: <JurnalKas kas={kas} /> },
        ]} />
      ) : (
        <p className="text-fs-12 text-kn-text-2" data-testid="doc-preview-opk-cash-empty">
          {menunggu ? "Kas penyesuaian dan jurnalnya terbit sesudah selisihnya disetujui orang kedua."
            : Math.abs(Number(doc.selisih) || 0) < 0.005 ? "Tanpa selisih — tidak ada kas atau jurnal."
              : "Tidak ada kas yang tercatat."}
        </p>
      )}
      <PreviewTotals testId="doc-preview-opk-totals" rows={[
        { label: "Saldo buku saat dihitung", value: formatCurrency(Number(doc.saldo_buku) || 0) },
        { label: "Uang fisik", value: formatCurrency(Number(doc.jumlah_fisik) || 0) },
        { label: "Selisih", value: selisihTeks(doc), strong: true },
      ]} />
      {jejak.length > 0 && (
        <ol className="grid gap-1 border-t border-kn-divider pt-2" data-testid="doc-preview-opk-history">
          {jejak.map((j, i) => (
            <li key={`${j.aksi}-${i}`} className="text-fs-12 text-kn-text-2">
              <span className="font-semibold text-kn-text">{JEJAK_LABEL[j.aksi] || j.aksi}</span>
              {j.oleh ? ` · ${j.oleh}` : ""}{j.pada ? ` · ${formatDateTime(j.pada)}` : ""}{j.catatan ? ` — ${j.catatan}` : ""}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
