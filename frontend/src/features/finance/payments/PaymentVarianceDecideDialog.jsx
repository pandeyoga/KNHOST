/**
 * PaymentVarianceDecideDialog — putuskan selisih bayar satu kwitansi (Meja gelombang 2, Task 7).
 * Satu sumber untuk antrean Selisih Bayar (`PaymentVarianceQueue`) dan Meja Keuangan: memuat penilaian + blok selisih
 * tersimpan, lalu mengirim `decideVariance` dengan kunci intent `pv-putus`. Tampilannya `PaymentVarianceDialog`.
 * Galat muat/kirim tampil di dalam pop-up.
 *
 * props: receiptId · receiptNumber · entityId (opsional, untuk daftar alasan) · onClose · onDone(msg)
 *        onStale() (opsional) — selisih ternyata sudah diputus: pemanggil memuat ulang daftarnya.
 */
import { useEffect, useState } from "react";
import { Scale } from "lucide-react";
import FormModal from "../../../components/FormModal";
import useIntentKey from "../../../hooks/useIntentKey";
import PaymentVarianceDialog from "./PaymentVarianceDialog";
import { decideVariance, errText, varianceByReceipt, varianceMeta } from "./paymentApi";

const STORED_KEYS = ["expected", "funds", "capacity", "boundary", "boundary_label", "delta", "direction", "explain"];

export default function PaymentVarianceDecideDialog({ receiptId, receiptNumber = "", entityId = "", onClose, onDone, onStale }) {
  const [assessment, setAssessment] = useState(null);
  const [reasons, setReasons] = useState([]);
  const [loadErr, setLoadErr] = useState("");
  const [stale, setStale] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const intent = useIntentKey("pv-putus");

  useEffect(() => {
    let batal = false;
    (async () => {
      try {
        const [res, meta] = await Promise.all([
          varianceByReceipt(receiptId),
          varianceMeta(entityId || "").catch(() => ({})),
        ]);
        if (batal) return;
        if (!res.assessment) { setStale(true); onStale?.(); return; }
        // G1-12: satu sumber angka — rincian/batas/arah dari blok selisih yang tersimpan di kwitansi (sama dengan tabel).
        const v = res.variance || {};
        const stored = {};
        STORED_KEYS.forEach((k) => {
          if (v[k] !== undefined && v[k] !== null && v[k] !== "" && !(Array.isArray(v[k]) && v[k].length === 0)) stored[k] = v[k];
        });
        setReasons(meta.reasons || []);
        setAssessment({ ...res.assessment, ...stored });
      } catch (e) { if (!batal) setLoadErr(errText(e, "Gagal memuat rincian selisih.")); }
    })();
    return () => { batal = true; };
  }, [receiptId, entityId]);

  const confirm = async (payload) => {
    setBusy(true); setErr("");
    try {
      await intent.send({ id: receiptId, ...payload }, (k) => decideVariance(receiptId, payload, k));
      onDone?.(`Selisih ${receiptNumber} diputuskan.`.replace("  ", " "));
    } catch (e) { setErr(errText(e, "Keputusan gagal disimpan.")); }
    finally { setBusy(false); }
  };

  if (assessment) {
    return (
      <PaymentVarianceDialog assessment={assessment} reasons={reasons} busy={busy} error={err}
        submitLabel="Simpan keputusan" onCancel={onClose} onConfirm={confirm} />
    );
  }
  // Belum ada penilaian: memuat / galat / sudah diputus — pop-up sederhana, bukan layar kosong.
  return (
    <FormModal open onClose={onClose} size="sm" icon={Scale} title="Putuskan selisih bayar" subtitle={receiptNumber}
      testId="pv-decide-load" error={loadErr}
      footer={<div className="flex justify-end"><button type="button" className="secondary-button" onClick={onClose}
        data-testid="pv-decide-load-close">Tutup</button></div>}>
      <p className="text-fs-13 text-kn-text-2" data-testid="pv-decide-load-text">
        {stale ? "Selisih kwitansi ini sudah diputus atau tidak lagi memerlukan keputusan." : loadErr ? "" : "Memuat rincian selisih…"}
      </p>
    </FormModal>
  );
}
