/**
 * ReconPayablePicker (MN-T3) — Rekonsiliasi Bank › baris mutasi KELUAR belum cocok › "Bayar pemasok".
 *
 * Pengganti `ReconContraBonModal` (FASE G-7 US8, form bayar sendiri — dihapus MN-T3 (b)). Pop-up ini hanya MEMILIH
 * dokumen yang dilunasi mutasi itu: kontrabon yang pantas (`GET /contra-bons/bank-line-candidates/{line}`, nominal
 * tepat dulu) atau tagihan pemasok terposting yang masih bersisa (`GET /vendor-bills?status=posted`, PT mutasi).
 * Membayarnya lewat SATU form `PaySupplierModal` dengan `bankLineId` (nominal, tanggal, rekening = mutasi; kontrabon →
 * server membuat kas dan menautkan baris; tagihan → kas pembayaran ditautkan ke baris).
 * Tombol "Pilih" hanya bagi pemegang izin bayar dokumen itu (`contra_bon.pay` / `vendor_bill.pay`).
 * Lebar daftar (pop-up `lg` 896 px): satu baris = nomor · pemasok · sisa + lencana selisih + tombol (membungkus di HP).
 */
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Receipt, CheckCircle2 } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { formatCurrency, formatDate } from "../../../utils/formatters";
import ErrorNotice from "../../../components/ErrorNotice";
import FormModal from "../../../components/FormModal";
import FilterChips from "../../../components/FilterChips";
import { apiErrorText } from "../../../utils/apiError";
import { can } from "../../../config/roles";
import PaySupplierModal from "../payments/PaySupplierModal";

const near = (a, b) => Math.abs(Number(a || 0) - Number(b || 0)) < 0.5;

export default function ReconPayablePicker({ line, perms, onClose, onDone, onError }) {
  const canCb = can(perms, "contra_bon", "pay") && can(perms, "contra_bon", "view");
  const canVb = can(perms, "vendor_bill", "pay") && can(perms, "vendor_bill", "view");
  const [kind, setKind] = useState(canCb ? "contra_bon" : "vendor_bill");
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState("");
  const [target, setTarget] = useState(null);

  const load = useCallback(async () => {
    setRows(null); setErr("");
    try {
      if (kind === "contra_bon") {
        const r = await axios.get(`${API}/contra-bons/bank-line-candidates/${line.id}`);
        setRows((r.data?.candidates || []).map((c) => ({ id: c.id, number: c.number, supplier: c.supplier_name,
          outstanding: c.outstanding, exact: c.exact, note: `${c.status_label || ""} · ${c.bills_count} faktur` })));
      } else {
        const params = { status: "posted", ...(line.entity_id && line.entity_id !== "all" ? { entity_id: line.entity_id } : {}) };
        const r = await axios.get(`${API}/vendor-bills`, { params });
        const list = (Array.isArray(r.data) ? r.data : r.data?.items || [])
          .map((b) => ({ id: b.id, number: b.bill_number, supplier: b.supplier_name, outstanding: b.financials?.outstanding ?? 0,
            exact: near(b.financials?.outstanding, line.amount), note: b.po_number ? `PO ${b.po_number}` : "" }))
          .filter((b) => Number(b.outstanding) > 0.01)
          .sort((a, b) => Number(b.exact) - Number(a.exact) || Math.abs(a.outstanding - line.amount) - Math.abs(b.outstanding - line.amount));
        setRows(list);
      }
    } catch (e) { setErr(apiErrorText(e)); setRows([]); onError?.(e); }
  }, [kind, line, onError]);
  useEffect(() => { load(); }, [load]);

  const options = [canCb && { key: "contra_bon", label: "Kontrabon" }, canVb && { key: "vendor_bill", label: "Tagihan pemasok" }]
    .filter(Boolean);

  if (target) {
    return (
      <PaySupplierModal target={target} bankLineId={line.id}
        preset={{ amount: line.amount, date: line.stmt_date, accountId: line.bank_account_id }}
        onClose={() => setTarget(null)}
        onPaid={(_, msg) => { setTarget(null); onDone?.(msg); }} onError={onError} />
    );
  }
  return (
    <FormModal open onClose={onClose} size="lg" icon={Receipt} title="Bayar pemasok dari mutasi ini" testId="recon-payable-picker"
      subtitle={`${formatDate(line.stmt_date)} · dana keluar ${formatCurrency(line.amount)} — ${line.description || "tanpa keterangan"}`}>
      <ErrorNotice message={err} onRetry={load} onDismiss={() => setErr("")} testId="recon-payable-error" />
      {options.length > 1 && (
        <FilterChips testId="recon-payable-kind" ariaLabel="Jenis dokumen" value={kind} onChange={setKind} options={options}
          chipTestId={(k) => `recon-payable-kind-${k}`} />
      )}
      <p className="mt-2 text-fs-12 text-kn-text-2">Pilih dokumen yang dilunasi mutasi ini; nominal, tanggal, dan rekening mengikuti mutasi.</p>
      <div className="mt-2 rounded-md border border-kn-divider">
        {rows === null ? (
          <p className="p-4 text-center text-fs-12 text-kn-text-2" data-testid="recon-payable-loading">Mencari dokumen yang pantas…</p>
        ) : rows.length === 0 ? (
          <p className="p-4 text-center text-fs-12 text-kn-text-2" data-testid="recon-payable-empty">
            {kind === "contra_bon" ? "Tidak ada kontrabon yang siap dibayar. Setujui kontrabonnya lebih dulu di Keuangan › Hutang › Kontrabon."
              : "Tidak ada tagihan pemasok terposting yang masih bersisa."}
          </p>
        ) : rows.map((r) => (
          <div key={r.id} data-testid={`recon-payable-${r.id}`} className="flex flex-wrap items-center justify-between gap-2 border-b border-kn-divider px-3 py-2 last:border-0">
            <div className="min-w-0">
              <p className="truncate text-fs-13"><b>{r.number}</b> · {r.supplier}</p>
              <p className="text-fs-12 text-kn-text-2">{r.note} · sisa <span className="whitespace-nowrap">{formatCurrency(r.outstanding)}</span></p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <span className={`status-pill ${r.exact ? "status-done" : "status-pending"} inline-flex items-center gap-1`}>
                {r.exact ? <CheckCircle2 size={12} aria-hidden="true" /> : <AlertTriangle size={12} aria-hidden="true" />}
                {r.exact ? "nominal tepat" : `selisih ${formatCurrency(Math.abs(Number(r.outstanding) - Number(line.amount)))}`}
              </span>
              <button type="button" className="primary-button btn-sm whitespace-nowrap" data-testid={`recon-payable-pick-${r.id}`}
                onClick={() => setTarget({ type: kind, id: r.id })}>Pilih</button>
            </div>
          </div>
        ))}
      </div>
    </FormModal>
  );
}
