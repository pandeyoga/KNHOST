/**
 * MkoStepModals — pop-up aksi per langkah Order Makloon: Issue bahan, Terima hasil, Catat jasa (FASE T).
 *
 * Fase 4 · R3 (L-03) — dulu tiga lapisan `fixed inset-0` buatan sendiri di `MakloonOrderDetailPanel.jsx`
 * (berkas itu 693 baris). Kini diekstrak ke sini dan memakai `FormModal` baku: layar penuh di HP (isian TIDAK
 * diringkas — sama dengan desktop), Esc berlapis (dropdown KNSelect menutup dirinya saja), latar tidak membuang
 * isian, galat aksi tampil di kaki pop-up (bukan di bilah halaman yang tertutup lapisan). Testid isian & tombol
 * (`mko-issue-*`, `mko-recv-*`, `mko-service-*`, `mko-*-confirm`) dan `mko-*-modal` dipertahankan.
 *
 * Kontrak `onConfirm`: async; galat DILEMPAR (Error.message / respons axios) → ditampilkan di pop-up.
 */
import { useState } from "react";
import { PackageCheck, Plus, Send, Trash2, Wrench } from "lucide-react";
import FormModal from "../../../components/FormModal";
import KNSelect from "../../../components/KNSelect";
import MoneyInput from "../../../components/MoneyInput";
import useDomainEnums from "../../../hooks/useDomainEnums";
import useUomConversions from "../../../hooks/useUomConversions";
import { formatQty } from "../../../utils/formatters";
import { uomSelectOptions } from "../../../utils/uomCatalog";   // FASE U — satuan dari master

function FieldR({ label, children }) {
  return <label className="block"><span className="mb-1 block text-[10.5px] font-semibold text-[#6B6B73]">{label}</span>{children}</label>;
}

export function IssueModal({ step, warehouses, defaultWh, busy, onClose, onConfirm }) {
  // Stok bahan MILIK entitas SPK per gudang (dihitung server) — gudang tanpa stok
  // tetap tampil tetapi diberi tanda, supaya 409 "stok tidak cukup" tidak jadi kejutan.
  const stockByWh = Object.fromEntries((step.source_stock || []).map((r) => [r.warehouse_id, r.available_qty]));
  const need = parseFloat(step.input_qty) || 0;
  const hasStock = (id) => (stockByWh[id] || 0) + 0.01 >= need;
  const firstOk = (step.source_stock || []).find((r) => r.available_qty + 0.01 >= need)?.warehouse_id;
  const [wh, setWh] = useState((defaultWh && hasStock(defaultWh) ? defaultWh : firstOk) || defaultWh || (warehouses[0]?.id || ""));
  const [err, setErr] = useState("");
  const [docUom, setDocUom] = useState("");
  const [docQty, setDocQty] = useState("");
  // Memuat katalog satuan (dan membagikannya ke penyimpan modul). Dipanggil DI SINI,
  // bukan mengandalkan layar lain sudah memanggilnya: pemilih yang bergantung pada
  // urutan kunjungan layar akan tampak "hanya berisi satu pilihan" secara acak.
  const { loading: uomLoading } = useUomConversions();
  const opts = warehouses.map((w) => ({
    value: w.id,
    label: `${w.name} (${w.code}) · tersedia ${formatQty(stockByWh[w.id] || 0)} ${step.input_unit || ""}`,
  }));
  const selectedStock = stockByWh[wh] || 0;
  const insufficient = !!wh && !hasStock(wh);
  // FASE U — satuan surat jalan mitra dari MASTER satuan. Dulu 7 nilai diketik di
  // sini; satuan yang ditambah pemilik (mis. `panel`) tidak pernah bisa dipilih,
  // sehingga penerimaan hasil makloon dalam satuan itu harus dikonversi manual di
  // kepala petugas — tempat kesalahan paling mahal dan paling tak terlacak.
  const uomOpts = [
    { value: "", label: uomLoading ? "Memuat satuan…" : `Pakai satuan sistem (${step.input_unit || "unit"})` },
    ...uomSelectOptions({ dimensions: ["length", "weight", "count"],
      extra: [step.input_unit].filter(Boolean) }),
  ];
  const submit = async () => {
    setErr("");
    try { await onConfirm(wh, docUom, docQty); } catch (e) { setErr(e.message || "Gagal issue ke makloon."); }
  };

  return (
    <FormModal open onClose={onClose} size="sm" icon={Send} title="Issue Bahan ke Makloon" testId="mko-issue-modal"
      onSubmit={submit} busy={busy} error={err} submitDisabled={!wh || insufficient}
      submitTestId="mko-issue-confirm" submitLabel={busy ? "Memproses…" : "Issue Sekarang"}>
      <div className="space-y-3">
        <p className="text-[12px] text-[#3C3C43]">Keluarkan <b>{formatQty(step.input_qty)} {step.input_unit}</b> {step.input_name} ke <b>{step.makloon_name}</b>. Stok berpindah ke bucket <b>Di Makloon (WIP-Vendor)</b>.</p>
        <FieldR label="Gudang Sumber Bahan">
          <KNSelect data-testid="mko-issue-warehouse" className="field" value={wh} onValueChange={setWh} options={opts} />
        </FieldR>
        {wh && (
          <p data-testid="mko-issue-stock-hint"
            className={`rounded-md px-2.5 py-1.5 text-[11px] ${insufficient ? "bg-[#FDECEA] text-[#A8221A]" : "bg-[#E6F4EA] text-[#1B7F4B]"}`}>
            {insufficient
              ? <>Stok tersedia di gudang ini hanya <b>{formatQty(selectedStock)} {step.input_unit}</b>, butuh <b>{formatQty(need)} {step.input_unit}</b> — pilih gudang lain atau terima/transfer bahan lebih dulu. Stok berkurang dari bucket <b>Tersedia</b> hanya setelah issue berhasil.</>
              : <>Stok tersedia <b>{formatQty(selectedStock)} {step.input_unit}</b> — cukup. Setelah issue, <b>{formatQty(need)} {step.input_unit}</b> pindah dari Tersedia ke <b>Di Makloon</b> dan hilang dari ATP.</>}
          </p>
        )}
        <div className="rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-2.5">
          <p className="mb-1.5 text-[10.5px] font-semibold text-[#6B6B73]">Satuan surat jalan mitra (opsional — sistem mengonversi & menyimpan jejaknya)</p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <KNSelect data-testid="mko-issue-doc-uom" className="field" value={docUom} onValueChange={setDocUom} options={uomOpts} />
            <input data-testid="mko-issue-doc-qty" className="field" value={docQty} onChange={(e) => setDocQty(e.target.value)}
              placeholder="Qty sesuai dokumen mitra" disabled={!docUom} />
          </div>
        </div>
      </div>
    </FormModal>
  );
}

export function ReceiveModal({ step, warehouses, defaultWh, mkoNumber, busy, onClose, onConfirm }) {
  const [outQty, setOutQty] = useState(String(step.expected_output_qty || ""));
  const [byQty, setByQty] = useState(String(step.expected_byproduct_qty || 0));
  const [tariff, setTariff] = useState("");
  const [aux, setAux] = useState(String(step.aux_cost || 0));
  const [ppn, setPpn] = useState("0");
  const [wh, setWh] = useState(defaultWh || (warehouses[0]?.id || ""));
  const [err, setErr] = useState("");
  const [invNo, setInvNo] = useState("");
  const [docUom, setDocUom] = useState("");
  const [docQty, setDocQty] = useState("");
  const [colors, setColors] = useState(String(step.colors || ""));
  const [repeats, setRepeats] = useState(String(step.repeats || ""));
  const { options: gradeOptions } = useDomainEnums();   // GRN Fase 0.4 — grade dari SSOT
  const [rolls, setRolls] = useState([{ lot: `${step.output_sku || "OUT"}-${mkoNumber}-1`, length: String(step.expected_output_qty || ""), grade: "A", dye_lot: "" }]);
  const whOpts = warehouses.map((w) => ({ value: w.id, label: `${w.name} (${w.code})` }));
  // FASE U — satuan dari MASTER (lihat alasan di `IssueModal`).
  useUomConversions();
  const uomOpts = [
    { value: "", label: `Satuan sistem (${step.output_unit || "unit"})` },
    ...uomSelectOptions({ dimensions: ["length", "weight", "count"],
      extra: [step.output_unit].filter(Boolean) }),
  ];

  const totalRolls = rolls.reduce((a, r) => a + (parseFloat(r.length) || 0), 0);
  const setRoll = (i, k, v) => setRolls((p) => p.map((r, idx) => (idx === i ? { ...r, [k]: v } : r)));
  const usingDoc = Boolean(docUom) && parseFloat(docQty) > 0;

  const submit = async () => {
    setErr("");
    const oq = parseFloat(outQty) || 0;
    if (!usingDoc && oq <= 0) { setErr("Qty output harus > 0."); return; }
    if (rolls.some((r) => !r.lot.trim())) { setErr("Setiap roll wajib punya nomor LOT."); return; }
    if (!usingDoc && Math.abs(totalRolls - oq) > 0.5) { setErr(`Total panjang roll (${formatQty(totalRolls)}) harus = qty output (${formatQty(oq)}).`); return; }
    try {
      const body = {
        actual_output_qty: usingDoc ? 0 : oq, actual_byproduct_qty: parseFloat(byQty) || 0,
        tariff: parseFloat(tariff) || 0, aux_cost: parseFloat(aux) || 0, ppn: parseFloat(ppn) || 0,
        output_warehouse_id: wh, supplier_invoice_no: invNo,
        colors: parseInt(colors, 10) || 0, repeats: parseInt(repeats, 10) || 0,
        byproduct_lot: `SISA-${mkoNumber}-${step.seq}`,
        rolls: rolls.map((r) => ({ lot: r.lot.trim(), length: parseFloat(r.length) || 0, grade: r.grade || "A", dye_lot: (r.dye_lot || "").trim() })),
      };
      if (usingDoc) { body.output_uom = docUom; body.output_doc_qty = parseFloat(docQty); }
      setErr(""); await onConfirm(body);
    } catch (e) { setErr(e.message || "Gagal terima hasil makloon."); }   // 23 Okt — dulu "sudah tampil" di BELAKANG modal
  };

  return (
    <FormModal open onClose={onClose} size="md" icon={PackageCheck} title="Terima Hasil Makloon" testId="mko-receive-modal"
      onSubmit={submit} busy={busy} error={err}
      submitTestId="mko-receive-confirm" submitLabel={busy ? "Memproses…" : "Terima & Catat"}>
      <div className="space-y-3">
        <div className="rounded-lg border border-[#DCE9FF] bg-[#F5F9FF] px-3 py-2 text-[11.5px] text-[#0058CC]">
          Estimasi sistem: <b>{formatQty(step.expected_output_qty)} {step.output_unit}</b>
          {step.tolerance_pct != null && <> · toleransi selisih <b>{step.tolerance_pct}%</b></>}
          {step.contract_number && <> · kontrak <b>{step.contract_number}</b> (ongkos jasa dihitung otomatis bila dikosongkan)</>}
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <FieldR label={`Qty Output (${step.output_unit || "unit"})`}><input data-testid="mko-recv-output-qty" type="number" className="field" value={outQty} onChange={(e) => setOutQty(e.target.value)} disabled={usingDoc} /></FieldR>
          <FieldR label={`Qty Barang Sisa (${step.input_unit || "unit"})`}><input data-testid="mko-recv-byproduct-qty" type="number" className="field" value={byQty} onChange={(e) => setByQty(e.target.value)} /></FieldR>
          <FieldR label="Gudang Terima"><KNSelect data-testid="mko-recv-warehouse" className="field" value={wh} onValueChange={setWh} options={whOpts} /></FieldR>
          <FieldR label="Ongkos Jasa (kosong = dari kontrak)"><MoneyInput testId="mko-recv-tariff" className="field" value={tariff} placeholder="otomatis" onChange={(v) => setTariff(v)} /></FieldR>
          <FieldR label="Bahan Pembantu (Rp)"><MoneyInput testId="mko-recv-aux" className="field" value={aux} onChange={(v) => setAux(v)} /></FieldR>
          <FieldR label="PPN (Rp)"><MoneyInput testId="mko-recv-ppn" className="field" value={ppn} onChange={(v) => setPpn(v)} /></FieldR>
          <FieldR label="Jumlah warna (screen)"><input data-testid="mko-recv-colors" type="number" className="field" value={colors} onChange={(e) => setColors(e.target.value)} /></FieldR>
          <FieldR label="Jumlah repeat"><input data-testid="mko-recv-repeats" type="number" className="field" value={repeats} onChange={(e) => setRepeats(e.target.value)} /></FieldR>
          <FieldR label="No. Faktur Makloon"><input data-testid="mko-recv-invoice" className="field" value={invNo} onChange={(e) => setInvNo(e.target.value)} placeholder="mis. INV-MKL-001" /></FieldR>
        </div>

        <div className="rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-2.5">
          <p className="mb-1.5 text-[10.5px] font-semibold text-[#6B6B73]">Laporan mitra dalam satuan lain (mis. kg untuk kain rajut) — sistem mengonversi & menyimpan jejaknya</p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <KNSelect data-testid="mko-recv-doc-uom" className="field" value={docUom} onValueChange={setDocUom} options={uomOpts} />
            <input data-testid="mko-recv-doc-qty" className="field" value={docQty} onChange={(e) => setDocQty(e.target.value)}
              placeholder="Qty sesuai dokumen mitra" disabled={!docUom} />
          </div>
          {usingDoc && <p className="mt-1 text-[10.5px] text-[#B26A00]">Qty output diambil dari hasil konversi — pastikan total panjang roll sama dengan hasil konversi.</p>}
        </div>

        <div className="rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-3">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-[11px] font-bold uppercase text-[#6B6B73]">Roll Output (LOT manual wajib)</p>
            <button data-testid="mko-recv-add-roll" type="button" className="secondary-button !py-1 !px-2 text-[11px]" onClick={() => setRolls((p) => [...p, { lot: `${step.output_sku || "OUT"}-${mkoNumber}-${p.length + 1}`, length: "", grade: "A", dye_lot: "" }])}><Plus size={12} /> Roll</button>
          </div>
          <div className="space-y-1.5" data-testid="mko-recv-rolls">
            {rolls.map((r, i) => (
              <div key={i} className="grid grid-cols-[1fr_1fr_auto] items-center gap-1.5 rounded-md border border-[#EFF0F2] bg-white p-1.5 sm:grid-cols-[1.4fr_0.9fr_0.7fr_1fr_auto] sm:border-0 sm:bg-transparent sm:p-0">
                <input data-testid={`mko-recv-roll-lot-${i}`} className="field col-span-3 !py-1.5 text-[11.5px] sm:col-span-1" placeholder="No. LOT" value={r.lot} onChange={(e) => setRoll(i, "lot", e.target.value)} />
                <input data-testid={`mko-recv-roll-len-${i}`} type="number" className="field !py-1.5 text-[11.5px]" placeholder="Panjang" value={r.length} onChange={(e) => setRoll(i, "length", e.target.value)} />
                <KNSelect data-testid={`mko-recv-roll-grade-${i}`} className="field !py-1.5 text-[11.5px] text-left" value={r.grade} onValueChange={(v) => setRoll(i, "grade", v)} options={gradeOptions("grade")} />
                <button type="button" aria-label="Hapus roll" className="icon-button text-red-400 hover:text-red-600 sm:order-last" disabled={rolls.length <= 1} onClick={() => setRolls((p) => p.filter((_, idx) => idx !== i))}><Trash2 size={13} /></button>
                <input data-testid={`mko-recv-roll-dyelot-${i}`} className="field col-span-3 !py-1.5 text-[11.5px] sm:col-span-1" placeholder="Dye lot" value={r.dye_lot} onChange={(e) => setRoll(i, "dye_lot", e.target.value)} />
              </div>
            ))}
          </div>
          <p className={`mt-1.5 text-[10.5px] ${!usingDoc && Math.abs(totalRolls - (parseFloat(outQty) || 0)) > 0.5 ? "text-[#C0392B]" : "text-[#1B7F4B]"}`}>Total roll: {formatQty(totalRolls)} {usingDoc ? "(harus = hasil konversi)" : `/ output ${formatQty(parseFloat(outQty) || 0)}`}</p>
        </div>
      </div>
    </FormModal>
  );
}

/**
 * RecordServiceModal (FASE T) — selesaikan langkah JASA MURNI.
 *
 * Sengaja TIDAK punya kolom "qty hasil" maupun daftar roll: tidak ada kain baru yang
 * lahir dan qty kainnya tidak berubah (diambil dari `input_qty` langkah). Menyediakan
 * kolom itu akan mengundang petugas "mengisi hasil" untuk pekerjaan yang tidak
 * menghasilkan kain, lalu selisih palsu muncul di klaim.
 */
export function RecordServiceModal({ step, mkoNumber, busy, onClose, onConfirm }) {
  const [tariff, setTariff] = useState("");
  const [aux, setAux] = useState(String(step.aux_cost || 0));
  const [ppn, setPpn] = useState("0");
  const [invNo, setInvNo] = useState("");
  const [colors, setColors] = useState(String(step.colors || ""));
  const [repeats, setRepeats] = useState(String(step.repeats || ""));
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");

  const submit = async () => {
    setErr("");
    if (!step.makloon_id) {
      setErr("Mitra makloon belum dipilih untuk langkah ini — tagihan jasa tidak punya "
        + "pemilik. Pilih mitranya lebih dulu (Pengaturan → Mitra Makloon bila belum ada).");
      return;
    }
    try {
      await onConfirm({
        tariff: parseFloat(tariff) || 0,
        aux_cost: parseFloat(aux) || 0,
        ppn: parseFloat(ppn) || 0,
        supplier_invoice_no: invNo,
        colors: parseInt(colors, 10) || 0,
        repeats: parseInt(repeats, 10) || 0,
        note,
      });
    } catch (e) {
      // Galat aksi tampil DI DALAM pop-up ini; bilah halaman tertutup pop-up sendiri.
      setErr(e.response?.data?.detail || e.message || "Gagal mencatat jasa langkah ini.");
    }
  };

  return (
    <FormModal open onClose={onClose} size="md" icon={Wrench} testId="mko-service-modal"
      title={`Catat Jasa — ${step.stage_label || step.stage_code || "langkah jasa"}`}
      onSubmit={submit} busy={busy} error={err}
      submitTestId="mko-service-confirm" submitLabel={busy ? "Memproses…" : "Catat Jasa & Terbitkan Tagihan"}>
      <div className="space-y-3">
        {/* Fase 4 · R3 (L-08) — aksen ungu → biru baku. */}
        <div className="rounded-lg border border-[#DCE9FF] bg-[#F5F9FF] px-3 py-2 text-[11.5px] text-[#0058CC]">
          Tahap ini <b>tidak mengubah kain</b>. {formatQty(step.input_qty)} {step.input_unit} {step.input_name}
          {" "}tetap di gudang — tidak ada roll baru, tidak ada perpindahan stok.
          Yang lahir: <b>tagihan jasa {step.makloon_name || "mitra"}</b> + jurnal WIP.
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <FieldR label="Ongkos Jasa (kosong = dari kontrak/basis)">
            <MoneyInput testId="mko-service-tariff" className="field" value={tariff} placeholder="otomatis" onChange={(v) => setTariff(v)} />
          </FieldR>
          <FieldR label="Biaya Lain (Rp)">
            <MoneyInput testId="mko-service-aux" className="field" value={aux}
              onChange={(v) => setAux(v)} />
          </FieldR>
          <FieldR label="PPN (Rp)">
            <MoneyInput testId="mko-service-ppn" className="field" value={ppn} onChange={(v) => setPpn(v)} />
          </FieldR>
          <FieldR label="Jumlah warna (kasa per warna)">
            <input data-testid="mko-service-colors" type="number" className="field" value={colors}
              onChange={(e) => setColors(e.target.value)} />
          </FieldR>
          <FieldR label="Jumlah repeat">
            <input data-testid="mko-service-repeats" type="number" className="field" value={repeats}
              onChange={(e) => setRepeats(e.target.value)} />
          </FieldR>
          <FieldR label="No. Faktur Mitra">
            <input data-testid="mko-service-invoice" className="field" value={invNo}
              onChange={(e) => setInvNo(e.target.value)} placeholder={`mis. INV-KASA-${step.seq}`} />
          </FieldR>
        </div>
        <FieldR label="Catatan (opsional)">
          <input data-testid="mko-service-note" className="field" value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={`mis. 3 kasa motif untuk ${mkoNumber}`} />
        </FieldR>
        {step.tariff_basis && (
          <p className="text-[10.5px] text-[#6B6B73]">
            Basis tarif langkah ini: <b>{step.tariff_basis}</b>
            {step.contract_number && <> · kontrak <b>{step.contract_number}</b></>}
            {" "}— kosongkan ongkos jasa agar dihitung sistem.
          </p>
        )}
      </div>
    </FormModal>
  );
}
