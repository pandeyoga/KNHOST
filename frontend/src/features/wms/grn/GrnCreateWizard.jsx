import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Camera, PackagePlus, Trash2 } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { KNSelect } from "../../../components/KNSelect";
import FormModal from "../../../components/FormModal";
import { Field } from "./GrnBits";
import GrnPhotoTips from "./GrnPhotoTips";
import GrnPhotoQuality from "./GrnPhotoQuality";
import { askConfirm } from "../../../services/confirmService";
import { errText, grnApi, photoCheck, shrinkImage, sha256Hex } from "./grnApi";
import { pageBad, quickCheck } from "./photoQuality";

/** Wizard buat GRN: (1) mitra & gudang, (2) foto SJ multi-halaman. `preset` = {partner_type, partner_id, warehouse_id, po_ids}.
 *  Fase 4 · R3 (L-03) — lapisan `fixed inset-0` buatan sendiri → FormModal baku (layar penuh di HP, Esc berlapis,
 *  latar tidak membuang isian, galat di kaki pop-up). Testid `grn-wizard`, `grn-wizard-close` tetap. */
export default function GrnCreateWizard({ preset, onClose, onCreated }) {
  const [step, setStep] = useState(1);
  const [ptype, setPtype] = useState(preset?.partner_type || "supplier");
  const [partners, setPartners] = useState([]);
  const [partnerId, setPartnerId] = useState(preset?.partner_id || "");
  const [warehouses, setWarehouses] = useState([]);
  const [whId, setWhId] = useState(preset?.warehouse_id || "");
  const [docIds, setDocIds] = useState(preset?.po_ids || []);
  const [pages, setPages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [reading, setReading] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => { grnApi.partners(ptype).then(setPartners).catch((e) => setErr(errText(e))); }, [ptype]);
  useEffect(() => { axios.get(`${API}/warehouses`).then((r) => setWarehouses(r.data || [])).catch(() => {}); }, []);
  const partner = partners.find((p) => p.partner_id === partnerId);
  useEffect(() => {
    if (partner && !whId && partner.open_docs[0]?.warehouse_id) setWhId(partner.open_docs[0].warehouse_id);
  }, [partner, whId]);
  // UAT 24 Okt (P9.3) — barang PO selalu diterima di gudang penerimaan PO-nya (server juga memaksa ini). Dulu
  // gudang bisa diganti di sini tetapi diabaikan saat posting → GRN menunjuk gudang yang salah.
  const docWh = [...new Set((partner?.open_docs || []).filter((d) => docIds.includes(d.id)).map((d) => d.warehouse_id).filter(Boolean))];
  const lockedWh = ptype === "supplier" && docWh.length === 1 ? docWh[0] : "";
  useEffect(() => { if (lockedWh && lockedWh !== whId) setWhId(lockedWh); }, [lockedWh, whId]);

  const prepare = async (f) => {
    const s = await shrinkImage(f);
    const originalSha = await sha256Hex(f);   // KN-E30 — hash berkas ASLI (sebelum dikecilkan)
    const isImg = s.file.type.startsWith("image/");
    return { ...s, originalSha, key: `${Date.now()}-${Math.random()}`, preview: isImg ? URL.createObjectURL(s.file) : "",
      quick: isImg ? await quickCheck(s.file) : { issues: [] }, ai: isImg ? { status: "checking" } : null };
  };
  // Cek AI (terpotong/terbaca) berjalan di latar; hasil menempel ke halaman lewat key.
  const runAi = (pg) => pg.ai && photoCheck(pg.file)
    .then((r) => setPages((ps) => ps.map((x) => (x.key === pg.key ? { ...x, ai: { ...r, status: r.checked ? "done" : "off" } } : x))))
    .catch(() => setPages((ps) => ps.map((x) => (x.key === pg.key ? { ...x, ai: { status: "error" } } : x))));
  const addFiles = async (list) => {
    const out = [];
    for (const f of Array.from(list || [])) out.push(await prepare(f));
    setPages((p) => [...p, ...out]);
    out.forEach(runAi);
  };
  const retake = async (key, f) => {
    const pg = await prepare(f);
    setPages((ps) => ps.map((x) => (x.key === key ? pg : x)));
    runAi(pg);
  };
  const move = (i, d) => setPages((p) => { const n = [...p]; const j = i + d; if (j < 0 || j >= n.length) return p; [n[i], n[j]] = [n[j], n[i]]; return n; });
  const toggleDoc = (id) => setDocIds((d) => (d.includes(id) ? d.filter((x) => x !== id) : [...d, id]));

  const submit = async () => {
    const bad = pages.filter(pageBad).length;
    if (bad && !(await askConfirm({ title: "Ada foto yang kurang baik", message: `${bad} foto terdeteksi buram, gelap, atau terpotong — hasil baca otomatis bisa salah. Sebaiknya foto ulang. Tetap kirim?`, confirmLabel: "Tetap kirim" }))) return;
    setBusy(true); setErr("");
    try {
      let g = await grnApi.create({ partner_type: ptype, partner_id: partnerId, warehouse_id: whId,
        po_ids: ptype === "supplier" ? docIds : [], mko_ids: ptype === "makloon" ? docIds : [] });
      for (const pg of pages) g = (await grnApi.upload(g.id, pg.file, g.version, pg.originalSha)).grn;
      // Foto SJ dari HP → langsung dibaca otomatis (bila OCR aktif) supaya draf roll terlihat tanpa langkah tambahan.
      if (pages.length && g.ocr_enabled && g.status === "draft") {
        setReading(true);
        try { g = await grnApi.post(g.id, "read", { expected_version: g.version }); }
        catch (e) { setErr(errText(e, "Baca otomatis gagal — bisa diulang dari detail.")); }
        finally { setReading(false); }
      }
      onCreated(g);
    } catch (e) { setErr(errText(e, "Gagal membuat kedatangan.")); } finally { setBusy(false); }
  };

  const footer = (
    <div className="flex justify-between gap-2">
      {step === 2 ? <button type="button" className="secondary-button" onClick={() => setStep(1)} data-testid="grn-wizard-back">Kembali</button> : <span />}
      {step === 1
        ? <button type="button" className="primary-button" disabled={!partnerId || !whId} onClick={() => setStep(2)} data-testid="grn-wizard-next">Lanjut</button>
        : <button type="button" className="primary-button" disabled={busy} onClick={submit} data-testid="grn-wizard-submit">{reading ? "Membaca surat jalan…" : busy ? "Menyimpan…" : "Buat kedatangan"}</button>}
    </div>
  );

  return (
    <FormModal open onClose={onClose} title="Kedatangan barang baru" subtitle={`Langkah ${step} dari 2`}
      icon={PackagePlus} testId="grn-wizard" busy={busy} error={err} footer={footer}>
      <div className="space-y-3">
        {step === 1 ? (<>
          <div className="flex gap-1 rounded-lg bg-[#F2F2F7] p-0.5 text-[11px] font-semibold">
            {["supplier", "makloon"].map((t) => (
              <button key={t} data-testid={`grn-wizard-type-${t}`} onClick={() => { setPtype(t); setPartnerId(""); setDocIds([]); }}
                className={`flex-1 rounded-md py-1.5 ${ptype === t ? "bg-white text-[#0058CC] shadow-sm" : "text-[#6B6B73]"}`}>
                {t === "supplier" ? "Supplier (PO)" : "Makloon (MKO)"}
              </button>
            ))}
          </div>
          <Field label="Mitra pengirim" hint="Hanya mitra yang punya dokumen terbuka menunggu barang di badan usaha aktif.">
            <KNSelect data-testid="grn-wizard-partner" value={partnerId} onValueChange={(v) => { setPartnerId(v); setDocIds([]); }}
              options={partners.map((p) => ({ value: p.partner_id, label: `${p.partner_name} · ${p.open_docs.length} ${ptype === "supplier" ? "PO" : "MKO"} terbuka` }))}
              placeholder={partners.length ? "Pilih mitra…" : "Tidak ada mitra dengan dokumen terbuka"} />
          </Field>
          {partner && (
            <div data-testid="grn-wizard-docs" className="flex flex-wrap gap-1.5">
              {partner.open_docs.map((d) => (
                <button key={d.id} data-testid={`grn-wizard-doc-${d.id}`} onClick={() => toggleDoc(d.id)}
                  className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${docIds.includes(d.id) ? "border-[#0058CC] bg-[#EEF4FF] text-[#0058CC]" : "border-[#E5E5EA] text-[#3C3C43]"}`}>
                  {d.number}
                </button>
              ))}
            </div>
          )}
          <Field label="Gudang penerima">
            {lockedWh ? (
              <p data-testid="grn-wizard-warehouse-locked" className="rounded-lg bg-[#F2F7FF] px-3 py-2 text-[12px] text-[#004099]">
                {(warehouses.find((w) => w.id === lockedWh) || {}).name || "Gudang penerimaan PO"} — mengikuti lokasi kirim PO
              </p>
            ) : (
              <KNSelect data-testid="grn-wizard-warehouse" value={whId} onValueChange={setWhId}
                options={warehouses.map((w) => ({ value: w.id, label: w.name }))} placeholder="Pilih gudang…" />
            )}
            {ptype === "supplier" && docWh.length > 1 && (
              <p className="mt-1 text-[11px] text-[#A8221A]" data-testid="grn-wizard-warehouse-mixed">PO terpilih dikirim ke gudang berbeda — catat kedatangan terpisah per lokasi.</p>
            )}
          </Field>
        </>) : (<>
          <GrnPhotoTips />
          <label className="flex cursor-pointer flex-col items-center gap-1 rounded-xl border-2 border-dashed border-[#CFE0FF] bg-[#F5F9FF] p-5 text-[12px] font-semibold text-[#0058CC]">
            <Camera size={20} /> Foto surat jalan (boleh beberapa halaman / PDF)
            <input data-testid="grn-wizard-files" type="file" accept="image/*,application/pdf" capture="environment" multiple className="hidden"
              onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }} />
          </label>
          {pages.map((p, i) => (
            <div key={p.key} data-testid={`grn-wizard-page-${i + 1}`} className={`flex items-start gap-2 rounded-lg border p-2 ${pageBad(p) ? "border-[#F5C2C0] bg-[#FFF8F8]" : "border-[#EFF0F2]"}`}>
              {p.preview ? <img src={p.preview} alt="" className="h-16 w-16 shrink-0 rounded object-cover" /> : <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded bg-[#F2F2F7] text-[10px]">PDF</span>}
              <div className="min-w-0 flex-1 space-y-1 text-[11px]">
                <p className="font-semibold">Halaman {i + 1}</p>
                <GrnPhotoQuality page={p} index={i} onRetake={(f) => retake(p.key, f)} />
              </div>
              <button onClick={() => move(i, -1)} aria-label="Naik"><ArrowUp size={14} /></button>
              <button onClick={() => move(i, 1)} aria-label="Turun"><ArrowDown size={14} /></button>
              <button onClick={() => setPages((ps) => ps.filter((x) => x.key !== p.key))} data-testid={`grn-wizard-page-remove-${i + 1}`} aria-label="Hapus"><Trash2 size={14} className="text-[#B4231F]" /></button>
            </div>
          ))}
          {!pages.length && <p className="text-[11px] text-[#6B6B73]">Foto boleh menyusul — Anda tetap bisa mengisi surat jalan secara manual.</p>}
        </>)}
      </div>
    </FormModal>
  );
}
