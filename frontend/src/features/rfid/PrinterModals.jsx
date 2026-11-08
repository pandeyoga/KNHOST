/**
 * PREP-F — pop-up printer label RFID (semua lewat `FormModal` baku):
 *  · ResolvePrintItemModal — keputusan atas label tidak pasti/gagal/bertentangan (izin approve, alasan + bukti wajib)
 *  · RollTagActionModal    — "Cetak ulang teks" (EPC tetap, tanpa tulis chip) vs "Ganti tag" (EPC baru; tag lama
 *                            dipensiunkan & tidak pernah dipakai ulang)
 *  · PrinterProfileModal   — profil printer (dpi, offset, posisi inlay, laporan encode) + pratinjau langsung
 */
import { useEffect, useState } from "react";
import { ClipboardCheck, Printer, Settings2, Tag } from "lucide-react";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import axios, { API } from "../../services/apiClient";
import { canCurrent } from "../../config/roles";
import LabelPreview from "./LabelPreview";
import {
  EVIDENCE_TYPES, FOLLOW_UP_REASON, REPLACE_REASONS, REPRINT_REASONS, RESOLVE_ACTIONS, RESULT_TEXT,
  actionsFor, epcTail, evidenceRequired,
} from "./printerLabels";

const errText = (e, f) => {
  const d = e?.response?.data?.detail;
  return (d && (d.message || (typeof d === "string" ? d : ""))) || f;
};

export function ResolvePrintItemModal({ row, onClose, onDone }) {
  const options = actionsFor(row).map((a) => ({ value: a, label: RESOLVE_ACTIONS[a] }));
  const [action, setAction] = useState(options[0]?.value || "");
  const [evidence, setEvidence] = useState(evidenceRequired(row?.kind, options[0]?.value) || "visual_check");
  const [ref, setRef] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const forced = evidenceRequired(row?.kind, action);
  useEffect(() => { if (forced) setEvidence(forced); }, [forced]);
  if (!row) return null;
  const submit = async () => {
    if (note.trim().length < 5) { setErr("Catatan alasan wajib diisi (min. 5 huruf)."); return; }
    setBusy(true); setErr("");
    try {
      const { data } = await axios.post(`${API}/rfid/print-jobs/${row.job_id}/items/${row.item_id}/resolve`,
        { action, note: note.trim(), evidence_type: evidence, evidence_ref: ref.trim() });
      onDone?.(data);
    } catch (e) { setErr(errText(e, "Gagal menyimpan keputusan.")); } finally { setBusy(false); }
  };
  return (
    <FormModal open onClose={onClose} title={`Tinjau label ${row.roll_no || ""}`} icon={ClipboardCheck}
      subtitle={`${FOLLOW_UP_REASON[row.reason] || row.reason} · job ${row.job_number}`} testId="print-resolve"
      onSubmit={submit} submitLabel="Simpan keputusan" busy={busy} error={err} submitTestId="print-resolve-submit"
      submitDisabled={note.trim().length < 5 || !action}>
      <div className="space-y-3 text-[12px]">
        <div className="rounded-lg bg-[#F7F7F9] p-2 text-[11.5px]" data-testid="print-resolve-facts">
          EPC <span className="font-mono">{row.epc || "—"}</span> · cetak {RESULT_TEXT[row.print_status] || "—"} ·
          chip {RESULT_TEXT[row.encode_status] || "—"}
          {row.evidence?.detail ? <div className="mt-1 text-[#6B6B73]">Bukti printer: {row.evidence.detail}</div> : null}
          {row.chip_written && (
            <div className="mt-1 font-semibold text-[#C0341D]" data-testid="print-resolve-chip-written">
              Chip SUDAH tertulis walau cetak gagal — musnahkan label fisiknya agar EPC ini tidak beredar.</div>)}
        </div>
        <label className="block">Keputusan
          <KNSelect data-testid="print-resolve-action" value={action} onValueChange={setAction} options={options} />
        </label>
        <p className="text-[11px] text-[#6B6B73]" data-testid="print-resolve-hint">
          {action === "confirm_success" && "Tag diaktifkan dan roll naik ke tahap Tag Dicetak. Label RFID wajib sudah terbaca handheld/reader (pindai dulu lewat sesi verifikasi)."}
          {action === "confirm_failed" && "Label dianggap tidak sah. EPC-nya dipensiunkan (tidak pernah dipakai lagi); roll kembali tanpa tag."}
          {action === "reprint" && "Label lama dianggap tidak sah, EPC lama dipensiunkan, dan job baru dengan EPC BARU dibuat untuk roll ini."}
          {action === "close" && "Item gagal ditutup tanpa cetak ulang (mis. roll ditangani lewat jalur lain)."}
        </p>
        <label className="block">Bukti
          <KNSelect data-testid="print-resolve-evidence" value={evidence} onValueChange={setEvidence}
            options={forced ? EVIDENCE_TYPES.filter((o) => o.value === forced) : EVIDENCE_TYPES} />
        </label>
        <label className="block">Rujukan bukti (opsional)
          <input className="field w-full" data-testid="print-resolve-ref" value={ref} maxLength={120}
            placeholder="No. sesi verifikasi / foto / catatan printer" onChange={(e) => setRef(e.target.value)} />
        </label>
        <label className="block">Catatan alasan (wajib)
          <textarea className="field h-16 w-full" data-testid="print-resolve-note" value={note} maxLength={500}
            onChange={(e) => setNote(e.target.value)} placeholder="Apa yang dicek dan hasilnya" />
        </label>
      </div>
    </FormModal>
  );
}

export function RollTagActionModal({ roll, mode: initialMode = "reprint", onClose, onDone }) {
  const canReplace = canCurrent("wms", "approve");
  const canReprint = canCurrent("wms", "print");
  const [mode, setMode] = useState(initialMode === "replace" && canReplace ? "replace" : canReprint ? "reprint" : "replace");
  const reasons = mode === "replace" ? REPLACE_REASONS : REPRINT_REASONS;
  const [reason, setReason] = useState(reasons[0].value);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState(null);
  useEffect(() => { setReason((mode === "replace" ? REPLACE_REASONS : REPRINT_REASONS)[0].value); }, [mode]);
  if (!roll) return null;
  const modeOpts = [
    ...(canReprint ? [{ value: "reprint", label: "Cetak ulang teks (EPC tetap, chip tidak ditulis)" }] : []),
    ...(canReplace ? [{ value: "replace", label: "Ganti tag (EPC baru, tag lama dipensiunkan)" }] : []),
  ];
  const submit = async () => {
    if (note.trim().length < 5) { setErr("Catatan alasan wajib diisi (min. 5 huruf)."); return; }
    setBusy(true); setErr("");
    try {
      const url = mode === "replace" ? `${API}/rfid/rolls/${roll.roll_id || roll.id}/replace-tag`
        : `${API}/rfid/rolls/${roll.roll_id || roll.id}/reprint-label`;
      const { data } = await axios.post(url, { reason_code: reason, note: note.trim() });
      setResult(mode === "replace"
        ? `Job ${data.job?.job_number} dibuat · EPC baru ${data.new_tag?.epc}${data.old_tag ? ` · EPC lama ${data.old_tag.epc} dipensiunkan` : ""}.`
        : `Job ${data.job_number} dibuat · label teks dengan EPC tetap ${epcTail((data.items || [])[0]?.epc)}.`);
      onDone?.(data);
    } catch (e) { setErr(errText(e, "Gagal membuat job cetak.")); } finally { setBusy(false); }
  };
  if (!modeOpts.length) return null;
  return (
    <FormModal open onClose={onClose} title={`Label & tag roll ${roll.roll_no || ""}`} icon={mode === "replace" ? Tag : Printer}
      subtitle={roll.epc ? `EPC sekarang ${roll.epc}` : "Roll belum punya tag aktif"} testId="roll-tag-action"
      onSubmit={result ? null : submit} submitLabel={mode === "replace" ? "Ganti tag" : "Cetak ulang teks"}
      busy={busy} error={err} submitTestId="roll-tag-action-submit" cancelLabel={result ? "Tutup" : "Batal"}
      submitDisabled={note.trim().length < 5}>
      <div className="space-y-3 text-[12px]">
        <label className="block">Jenis tindakan
          <KNSelect data-testid="roll-tag-action-mode" value={mode} onValueChange={setMode} options={modeOpts} />
        </label>
        <p className="rounded-lg bg-[#F7F7F9] p-2 text-[11px] text-[#3C3C43]" data-testid="roll-tag-action-hint">
          {mode === "replace"
            ? "Untuk tag rusak/hilang/salah tempel. Sistem membuat EPC baru yang belum pernah terbit; tag lama dipensiunkan dan EPC-nya tidak pernah dipakai lagi. Bukti verifikasi lama gugur — verifikasi ulang dengan handheld sesudah label baru ditempel. Stok, pemilik, dan tahap roll tidak berubah."
            : "Untuk teks label yang rusak sementara chip masih baik. Label baru TIDAK menulis chip; identitas roll (EPC) tetap. Bila media printer berinlay RFID, chip label baru kosong — tempel menimpa label lama."}
        </p>
        <label className="block">Alasan
          <KNSelect data-testid="roll-tag-action-reason" value={reason} onValueChange={setReason} options={reasons} />
        </label>
        <label className="block">Catatan alasan (wajib)
          <textarea className="field h-16 w-full" data-testid="roll-tag-action-note" value={note} maxLength={500}
            onChange={(e) => setNote(e.target.value)} />
        </label>
        {result && <div className="rounded-lg bg-[#E7F7EC] p-2 font-semibold text-[#1B7E3B]" data-testid="roll-tag-action-result">{result}</div>}
      </div>
    </FormModal>
  );
}

const DPI = [{ value: "203", label: "203 dpi (8 dot/mm)" }, { value: "300", label: "300 dpi (11,8 dot/mm)" }];
const ERROR_MODES = [{ value: "N", label: "Lanjut ke label berikut (N)" }, { value: "P", label: "Jeda printer (P)" },
  { value: "E", label: "Mode galat (E)" }];
const REPORTS = [{ value: "hv", label: "Baca balik EPC (^RFR + ^HV)" }, { value: "rv", label: "Laporan hasil encode (^RVE)" },
  { value: "hv+rv", label: "Keduanya" }, { value: "none", label: "Tanpa laporan (hanya status printer)" }];
const NUM_FIELDS = [
  ["label_width_mm", "Lebar label (mm)"], ["label_height_mm", "Tinggi label (mm)"],
  ["offset_x_dots", "Geser kanan (dot, ^LH)"], ["offset_y_dots", "Geser bawah (dot, ^LH)"],
  ["label_top", "Label top (−120..120, ^LT)"], ["rfid_tries", "Percobaan encode (1–10)"],
];

export function PrinterProfileModal({ deviceId, isAdmin = false, onClose, onSaved }) {
  const [data, setData] = useState(null);
  const [p, setP] = useState(null);
  const [conn, setConn] = useState({ host: "", port: 9100, note: "" });
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  useEffect(() => {
    axios.get(`${API}/rfid/printers/${deviceId}/profile`).then((r) => {
      setData(r.data); setP(r.data.profile); setConn({ host: "", port: 9100, note: "", ...(r.data.connection || {}) });
    }).catch((e) => setErr(errText(e, "Gagal memuat profil printer.")));
  }, [deviceId]);
  useEffect(() => {
    if (!p) return undefined;
    const t = setTimeout(() => {
      axios.post(`${API}/rfid/printers/label-preview`, { profile: p })
        .then((r) => { setPreview(r.data); setErr(""); })
        .catch((e) => setErr(errText(e, "Profil tidak valid.")));
    }, 300);
    return () => clearTimeout(t);
  }, [p]);
  const set = (k, v) => setP((x) => ({ ...x, [k]: v }));
  const save = async () => {
    setBusy(true); setErr("");
    try {
      const { data: d } = await axios.put(`${API}/rfid/printers/${deviceId}/profile`,
        { profile: p, connection: { ...conn, port: Number(conn.port) || 9100 } });
      setData(d); onSaved?.(d);
    } catch (e) { setErr(errText(e, "Gagal menyimpan profil.")); } finally { setBusy(false); }
  };
  return (
    <FormModal open onClose={onClose} size="lg" icon={Settings2} testId="printer-profile"
      title={`Profil printer ${data?.name || ""}`} subtitle={data ? `Sidik profil ${data.profile_key} · kalibrasi saat uji meja` : "Memuat…"}
      onSubmit={isAdmin && p ? save : null} submitLabel="Simpan profil" busy={busy} error={err}
      submitTestId="printer-profile-save">
      {!p ? <div className="text-[12px] text-[#6B6B73]">Memuat profil…</div> : (
        <div className="grid gap-3 text-[12px] sm:grid-cols-2">
          {!isAdmin && <p className="sm:col-span-2 text-[11px] text-[#8C4A00]" data-testid="printer-profile-readonly">
            Hanya admin yang bisa mengubah profil; Anda melihat pratinjau.</p>}
          <label className="block">Resolusi
            <KNSelect data-testid="printer-profile-dpi" value={String(p.dpi)} onValueChange={(v) => set("dpi", Number(v))}
              options={DPI} disabled={!isAdmin} />
          </label>
          <label className="block">Laporan encode dari printer
            <KNSelect data-testid="printer-profile-report" value={p.encode_report} onValueChange={(v) => set("encode_report", v)}
              options={REPORTS} disabled={!isAdmin} />
          </label>
          {NUM_FIELDS.map(([k, label]) => (
            <label key={k} className="block">{label}
              <input type="number" className="field w-full" data-testid={`printer-profile-${k}`} value={p[k] ?? ""}
                disabled={!isAdmin} onChange={(e) => set(k, e.target.value === "" ? "" : Number(e.target.value))} />
            </label>
          ))}
          <label className="block">Posisi inlay (^RS, kosong = bawaan printer)
            <input className="field w-full" data-testid="printer-profile-rfid_position" value={p.rfid_position || ""}
              disabled={!isAdmin} placeholder="mis. F0 / B4 / 0" onChange={(e) => set("rfid_position", e.target.value)} />
          </label>
          <label className="block">Bila encode gagal
            <KNSelect data-testid="printer-profile-error-mode" value={p.rfid_error_mode} disabled={!isAdmin}
              onValueChange={(v) => set("rfid_error_mode", v)} options={ERROR_MODES} />
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" data-testid="printer-profile-confirm-without" checked={!!p.confirm_without_readback}
              disabled={!isAdmin} onChange={(e) => set("confirm_without_readback", e.target.checked)} />
            Tanpa laporan encode: anggap chip tertulis bila printer tidak melapor galat
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" data-testid="printer-profile-media-rfid" checked={!!p.media_rfid} disabled={!isAdmin}
              onChange={(e) => set("media_rfid", e.target.checked)} />
            Media berinlay RFID
          </label>
          <label className="block">IP printer (dicatat; dipakai connector)
            <input className="field w-full" data-testid="printer-profile-host" value={conn.host} disabled={!isAdmin}
              onChange={(e) => setConn((c) => ({ ...c, host: e.target.value }))} placeholder="192.168.x.x" />
          </label>
          <label className="block">Port
            <input type="number" className="field w-full" data-testid="printer-profile-port" value={conn.port} disabled={!isAdmin}
              onChange={(e) => setConn((c) => ({ ...c, port: e.target.value }))} />
          </label>
          <div className="sm:col-span-2">
            <LabelPreview layout={preview?.layout} testId="printer-profile-preview" />
            {preview?.zpl && (
              <details className="mt-1 text-[11px]"><summary className="cursor-pointer text-[#0058CC]">ZPL contoh</summary>
                <pre className="max-h-40 overflow-auto rounded bg-[#F7F7F9] p-2 font-mono text-[10.5px]" data-testid="printer-profile-zpl">{preview.zpl}</pre>
              </details>)}
          </div>
        </div>
      )}
    </FormModal>
  );
}
