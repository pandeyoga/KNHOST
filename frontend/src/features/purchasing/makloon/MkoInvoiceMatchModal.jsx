// MP-T4b (K-78) — PT bersakelar "jasa jadi hutang saat faktur": hasil makloon yang diterima mencatat jasa ke GR/IR
// (belum hutang). Saat faktur mitra datang, bagian Pembelian mencocokkannya di sini: nilai jasa harus sama dengan nilai
// yang diterima (sesudah potongan klaim); PPN dari faktur. Server menerbitkan Dr GR/IR + PPN Masukan / Cr Hutang.
import { useState } from "react";
import { FileCheck2 } from "lucide-react";
import FormModal from "../../../components/FormModal";
import axios, { API } from "../../../services/apiClient";
import { formatCurrency } from "../../../utils/formatters";

export default function MkoInvoiceMatchModal({ mkoId, bill, onClose, onDone }) {
  const expected = Number(bill.net_amount || 0);
  const [no, setNo] = useState("");
  const [date, setDate] = useState("");
  const [net, setNet] = useState(String(expected));
  const [ppn, setPpn] = useState("0");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const total = (parseFloat(net) || 0) + (parseFloat(ppn) || 0);
  const submit = async () => {
    setErr("");
    if (!no.trim()) { setErr("Isi nomor faktur mitra."); return; }
    setBusy(true);
    try {
      await axios.post(`${API}/makloon-orders/${mkoId}/steps/${bill.step_seq}/service-invoice`, {
        supplier_invoice_no: no.trim(), invoice_date: date, net_amount: parseFloat(net) || 0, ppn_amount: parseFloat(ppn) || 0,
      });
      onDone?.();
    } catch (e) {
      const d = e.response?.data?.detail;
      setErr(typeof d === "string" ? d : "Faktur gagal dicocokkan.");
    } finally { setBusy(false); }
  };
  return (
    <FormModal open onClose={onClose} size="md" icon={FileCheck2} testId="mko-invoice-modal" busy={busy} error={err}
      title={`Cocokkan faktur — ${bill.bill_number}`}
      subtitle={`Nilai jasa yang diterima langkah ${bill.step_seq} (sesudah potongan klaim): ${formatCurrency(expected)}. Hutang ke ${bill.supplier_name || "mitra"} lahir saat faktur dicocokkan.`}
      onSubmit={submit} submitLabel="Cocokkan" submitTestId="mko-invoice-confirm">
      <div className="grid gap-3">
        <label className="text-fs-12 font-semibold">No. faktur mitra *
          <input className="field mt-1" data-testid="mko-invoice-no" value={no} onChange={(e) => setNo(e.target.value)} placeholder="mis. INV/2026/11/045" />
        </label>
        <label className="text-fs-12 font-semibold">Tanggal faktur
          <input className="field mt-1" type="date" data-testid="mko-invoice-date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <div className="grid grid-cols-2 gap-2">
          <label className="text-fs-12 font-semibold">Nilai jasa di faktur (tanpa PPN) *
            <input className="field mt-1" inputMode="decimal" data-testid="mko-invoice-net" value={net} onChange={(e) => setNet(e.target.value)} />
          </label>
          <label className="text-fs-12 font-semibold">PPN di faktur
            <input className="field mt-1" inputMode="decimal" data-testid="mko-invoice-ppn" value={ppn} onChange={(e) => setPpn(e.target.value)} />
          </label>
        </div>
        <p className="text-fs-12 text-kn-text-2">Total hutang: <span className="font-semibold tabular-nums">{formatCurrency(total)}</span></p>
      </div>
    </FormModal>
  );
}
