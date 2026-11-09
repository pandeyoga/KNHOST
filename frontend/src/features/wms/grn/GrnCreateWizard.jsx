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
import { rememberDocEntities } from "../../../services/docEntityRegistry";   // FIX-6 (D9) — GRN PT lain

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
  // FIX-6 (keputusan pemilik 10 Nov, D9) — satu SJ supplier untuk beberapa PT → GRN per PT pemilik.
  const [multiPt, setMultiPt] = useState(false);
  const [arrival, setArrival] = useState(null);   // {sites:[{site_id, site_name, pos:[…]}]}
  const [arrPoIds, setArrPoIds] = useState([]);
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
  useEffect(() => {
    if (!multiPt || !partnerId || ptype !== "supplier") { setArrival(null); return; }
    grnApi.arrivalCandidates(partnerId).then(setArrival).catch((e) => setErr(errText(e)));
  }, [multiPt, partnerId, ptype]);
  const arrSite = (arrival?.sites || []).find((s) => s.pos.some((p) => arrPoIds.includes(p.id)))?.site_id;
  const toggleArrPo = (id) => setArrPoIds((d) => (d.includes(id) ? d.filter((x) => x !== id) : [...d, id]));
  const arrPts = [...new Set((arrival?.sites || []).flatMap((s) => s.pos).filter((p) => arrPoIds.includes(p.id)).map((p) => p.entity_name || p.entity_id))];

  const submit = async () => {
    const bad = pages.filter(pageBad).length;
    if (bad && !(await askConfirm({ title: "Ada foto yang kurang baik", message: `${bad} foto terdeteksi buram, gelap, atau terpotong — hasil baca otomatis bisa salah. Sebaiknya foto ulang. Tetap kirim?`, confirmLabel: "Tetap kirim" }))) return;
    setBusy(true); setErr("");
    if (multiPt) {
      try {
        const res = await grnApi.createArrival({ partner_id: partnerId, po_ids: arrPoIds });
        rememberDocEntities(res.grns || []);   // unggah & detail GRN PT lain atas nama PT pemilik GRN itu
        let first = null;
        for (const g0 of res.grns || []) {
          let g = g0;
          for (const pg of pages) g = (await grnApi.upload(g.id, pg.file, g.version, pg.originalSha)).grn;
          if (!first) first = g;
        }
        onCreated(first);
      } catch (e) { setErr(errText(e, "Gagal membuat kedatangan lintas PT.")); } finally { setBusy(false); }
      return;
    }
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
        ? <button type="button" className="primary-button" disabled={!partnerId || (multiPt ? !arrPoIds.length : !whId)} onClick={() => setStep(2)} data-testid="grn-wizard-next">Lanjut</button>
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
          {ptype === "supplier" && partner && (
            <label className="flex items-center gap-2 text-fs-12 text-kn-text-2" data-testid="grn-wizard-multipt-label">
              <input type="checkbox" data-testid="grn-wizard-multipt" checked={multiPt}
                onChange={(e) => { setMultiPt(e.target.checked); setArrPoIds([]); }} />
              Satu surat jalan berisi barang beberapa PT — pisahkan menjadi kedatangan per PT
            </label>
          )}
          {multiPt && arrival && (
            <div data-testid="grn-wizard-arrival" className="space-y-2">
              {(arrival.sites || []).map((s) => (
                <div key={s.site_id || "none"} className="space-y-1">
                  <p className="text-fs-12 font-semibold text-kn-text-2">Lokasi: {s.site_name}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {s.pos.map((p) => {
                      const off = arrSite && arrSite !== s.site_id;
                      return (
                        <label key={p.id} data-testid={`grn-wizard-arr-po-${p.id}`} className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-fs-12 ${off ? "opacity-50" : ""}`}>
                          <input type="checkbox" disabled={off} checked={arrPoIds.includes(p.id)} onChange={() => toggleArrPo(p.id)} />
                          {p.number} · {p.entity_name || p.entity_id} · {p.warehouse_name}
                        </label>
                      );
                    })}
                  </div>
                </div>
              ))}
              {!(arrival.sites || []).length && <p className="text-fs-12 text-kn-text-2">Tidak ada PO terbuka supplier ini di PT penugasan Anda.</p>}
              {arrPts.length > 0 && (
                <p data-testid="grn-wizard-arrival-summary" className="text-fs-12 text-kn-text-2">
                  Akan dibuat {arrPts.length} kedatangan (satu per PT): {arrPts.join(", ")} — foto SJ yang sama dilampirkan ke masing-masing.
                </p>
              )}
            </div>
          )}
          {partner && !multiPt && (
            <div data-testid="grn-wizard-docs" className="flex flex-wrap gap-1.5">
              {partner.open_docs.map((d) => (
                <button key={d.id} data-testid={`grn-wizard-doc-${d.id}`} onClick={() => toggleDoc(d.id)}
                  className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${docIds.includes(d.id) ? "border-[#0058CC] bg-[#EEF4FF] text-[#0058CC]" : "border-[#E5E5EA] text-[#3C3C43]"}`}>
                  {d.number}
                </button>
              ))}
            </div>
          )}
          {!multiPt && <Field label="Gudang penerima">
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
          </Field>}
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
