import { useEffect, useState } from "react";
import { Send } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import KNDatePicker from "../../components/KNDatePicker";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, todayWib } from "../../utils/formatters";
import { moneyMessage } from "../../utils/moneyConfirm";
import { useEntityScope } from "../../context/EntityScopeContext";

/**
 * TaxIssueDialog — pratinjau + konfirmasi TERBIT FAKTUR PAJAK (Meja gelombang 1, Task 9).
 *
 * Satu pop-up untuk semua jalur terbit: draf di layar Faktur Pajak, baris antrean Meja Keuangan, dan
 * rincian pesanan. Pemanggil mengirim `submit(body)` yang memanggil endpoint layar asalnya; galat dari
 * `submit` tampil DI DALAM pop-up (`<testId>-error`) dan pop-up tetap terbuka. Angka hanya dari `target`
 * (tanpa hitungan di sisi layar); baris NPWP hanya tampil bila `target.npwp` terisi.
 *
 * target: { kind: "draft" | "order", id, number, orderNumber, customerName, npwp, entityId, dpp, ppnAmount,
 *           total, kodeTransaksi, fakturDate, nsfp, isRetur }
 */
export default function TaxIssueDialog({ target, submit, onClose, onDone, testId = "fkt-modal" }) {
  const {
    kind = "draft", number = "", orderNumber = "", customerName = "", npwp = "", entityId = "",
    dpp = null, ppnAmount = 0, total = null, kodeTransaksi = "", fakturDate = "", nsfp = "", isRetur = false,
  } = target || {};
  const isOrder = kind === "order";
  const { entities } = useEntityScope();
  const [dateVal, setDateVal] = useState(isOrder ? todayWib() : String(fakturDate || "").slice(0, 10));
  const [kodeVal, setKodeVal] = useState(kodeTransaksi || "");
  const [nsfpVal, setNsfpVal] = useState(nsfp || "");
  const [kodeList, setKodeList] = useState([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!entityId) return undefined;
    let aktif = true;
    axios.get(`${API}/settings/effective`, { params: { entity_id: entityId } })
      .then((r) => {
        const list = r?.data?.tax?.kode_transaksi_diizinkan;
        if (aktif && Array.isArray(list)) setKodeList(list);
      })
      .catch(() => { /* pilihan tetap bawaan; server menolak kode di luar daftar PT */ });
    return () => { aktif = false; };
  }, [entityId]);

  const kodeOpsi = (() => {
    const dasar = kodeTransaksi && !kodeList.includes(kodeTransaksi) ? [kodeTransaksi, ...kodeList] : kodeList;
    const opsi = dasar.map((k) => ({ value: k, label: k }));
    if (isOrder) return [{ value: "", label: "Bawaan (ditentukan sistem)" }, ...opsi];
    return opsi.length ? opsi : [{ value: kodeTransaksi || "", label: kodeTransaksi || "—" }];
  })();

  const kirim = async () => {
    if (busy) return;
    setBusy(true);
    setErr("");
    try {
      const body = { faktur_date: dateVal || null, kode_transaksi: kodeVal || null, nsfp: nsfpVal.trim() || null };
      const faktur = await submit(body);
      onDone?.(faktur);
    } catch (e) {
      setErr(apiErrorText(e, "Gagal menerbitkan Faktur Pajak."));
    } finally {
      setBusy(false);
    }
  };

  const judul = isOrder ? "Terbitkan Faktur Pajak" : (isRetur ? "Terbitkan Dokumen Pajak Retur" : "Terbitkan Draf Faktur");
  const baris = [
    ["Pesanan", orderNumber || "—"],
    ["Pelanggan", customerName || "—"],
    npwp ? ["NPWP", npwp] : null,
    dpp != null ? ["DPP", formatCurrency(dpp)] : null,
    ["PPN", formatCurrency(ppnAmount)],
    total != null ? ["Total", formatCurrency(total)] : null,
  ].filter(Boolean);

  return (
    <FormModal open onClose={onClose} size="sm" icon={Send} title={judul}
      subtitle={`${number} · ${orderNumber || "—"}`} testId={testId} busy={busy} error={err}
      footer={(
        <div className="flex justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose} disabled={busy}>Batal</button>
          <button type="button" data-testid={`${testId}-submit`} className="primary-button whitespace-nowrap"
            disabled={busy} onClick={kirim}>
            {busy ? "Memproses…" : "Terbitkan"}
          </button>
        </div>
      )}>
      <div className="space-y-2" data-testid="fkt-issue-form">
        <dl className="rounded-md border border-kn-border px-3 py-2 text-fs-13 space-y-1" data-testid="fkt-issue-preview">
          {baris.map(([k, v]) => (
            <div key={k} className="flex justify-between gap-3">
              <dt className="text-kn-text-2">{k}</dt>
              <dd className="text-right tabular-nums">{v}</dd>
            </div>
          ))}
        </dl>
        <label className="field-label">Tanggal faktur</label>
        <KNDatePicker data-testid="fkt-issue-date" value={dateVal} onChange={(v) => setDateVal(v || "")}
          placeholder="Tanggal faktur" />
        <p className="text-fs-12 text-kn-text-2">
          {isOrder ? "Bawaan = hari ini." : "Bawaan = tanggal surat jalan / nota kreditnya."} Masa pajak yang sudah ditandai dilaporkan ditolak.
        </p>
        <label className="field-label mt-2">Kode transaksi</label>
        <KNSelect data-testid="fkt-kode-select" value={kodeVal} onValueChange={setKodeVal} className="field w-full"
          options={kodeOpsi} />
        <label className="field-label mt-2" htmlFor="fkt-issue-nsfp">NSFP (boleh menyusul)</label>
        <input id="fkt-issue-nsfp" data-testid="fkt-issue-nsfp" value={nsfpVal} onChange={(e) => setNsfpVal(e.target.value)}
          placeholder="0100123456789012" className="field w-full tabular-nums" />
        <p className="rounded-md bg-kn-neutral-soft px-3 py-2 text-fs-13" data-testid="fkt-issue-confirm">
          {moneyMessage({
            effect: `${isRetur ? "Dokumen pajak retur" : "Faktur"} ${number || orderNumber} diterbitkan; PPN-nya ${isRetur ? "mengurangi" : "masuk"} rekap PPN keluaran masa tanggal faktur.`,
            amount: ppnAmount, entityId, entities,
          })}
        </p>
      </div>
    </FormModal>
  );
}
