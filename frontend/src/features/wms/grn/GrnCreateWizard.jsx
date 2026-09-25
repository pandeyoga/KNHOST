import { useEffect, useState } from "react";
import { AlertTriangle, ArrowDown, ArrowUp, Camera, Trash2, X } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { KNSelect } from "../../../components/KNSelect";
import { ErrorBox, Field } from "./GrnBits";
import { MIN_SHORT_SIDE, errText, grnApi, shrinkImage } from "./grnApi";

/** Wizard buat GRN: (1) mitra & gudang, (2) foto SJ multi-halaman. `preset` = {partner_type, partner_id, warehouse_id, po_ids}. */
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
  const [err, setErr] = useState("");

  useEffect(() => { grnApi.partners(ptype).then(setPartners).catch((e) => setErr(errText(e))); }, [ptype]);
  useEffect(() => { axios.get(`${API}/warehouses`).then((r) => setWarehouses(r.data || [])).catch(() => {}); }, []);
  const partner = partners.find((p) => p.partner_id === partnerId);
  useEffect(() => {
    if (partner && !whId && partner.open_docs[0]?.warehouse_id) setWhId(partner.open_docs[0].warehouse_id);
  }, [partner, whId]);

  const addFiles = async (list) => {
    const out = [];
    for (const f of Array.from(list || [])) {
      const s = await shrinkImage(f);
      out.push({ ...s, key: `${Date.now()}-${Math.random()}`, preview: s.file.type.startsWith("image/") ? URL.createObjectURL(s.file) : "",
        small: s.width > 0 && Math.min(s.width, s.height) < MIN_SHORT_SIDE });
    }
    setPages((p) => [...p, ...out]);
  };
  const move = (i, d) => setPages((p) => { const n = [...p]; const j = i + d; if (j < 0 || j >= n.length) return p; [n[i], n[j]] = [n[j], n[i]]; return n; });
  const toggleDoc = (id) => setDocIds((d) => (d.includes(id) ? d.filter((x) => x !== id) : [...d, id]));

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      let g = await grnApi.create({ partner_type: ptype, partner_id: partnerId, warehouse_id: whId,
        po_ids: ptype === "supplier" ? docIds : [], mko_ids: ptype === "makloon" ? docIds : [] });
      for (const pg of pages) g = (await grnApi.upload(g.id, pg.file, g.version)).grn;
      onCreated(g);
    } catch (e) { setErr(errText(e, "Gagal membuat kedatangan.")); } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" data-testid="grn-wizard">
      <div className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-[#EFF0F2] px-4 py-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Langkah {step} dari 2</p>
            <h3 className="text-[15px] font-bold">Kedatangan barang baru</h3>
          </div>
          <button onClick={onClose} data-testid="grn-wizard-close" aria-label="Tutup"><X size={16} /></button>
        </div>
        <div className="space-y-3 p-4">
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
              <KNSelect data-testid="grn-wizard-warehouse" value={whId} onValueChange={setWhId}
                options={warehouses.map((w) => ({ value: w.id, label: w.name }))} placeholder="Pilih gudang…" />
            </Field>
          </>) : (<>
            <label className="flex cursor-pointer flex-col items-center gap-1 rounded-xl border-2 border-dashed border-[#CFE0FF] bg-[#F5F9FF] p-5 text-[12px] font-semibold text-[#0058CC]">
              <Camera size={20} /> Foto surat jalan (boleh beberapa halaman / PDF)
              <input data-testid="grn-wizard-files" type="file" accept="image/*,application/pdf" capture="environment" multiple className="hidden"
                onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }} />
            </label>
            {pages.map((p, i) => (
              <div key={p.key} data-testid={`grn-wizard-page-${i + 1}`} className="flex items-center gap-2 rounded-lg border border-[#EFF0F2] p-2">
                {p.preview ? <img src={p.preview} alt="" className="h-12 w-12 rounded object-cover" /> : <span className="flex h-12 w-12 items-center justify-center rounded bg-[#F2F2F7] text-[10px]">PDF</span>}
                <div className="flex-1 text-[11px]">
                  <p className="font-semibold">Halaman {i + 1}</p>
                  {p.small && <p className="flex items-center gap-1 text-[#B4231F]"><AlertTriangle size={11} /> Foto terlalu kecil — kemungkinan dari WhatsApp. Ambil ulang dengan kamera aplikasi.</p>}
                </div>
                <button onClick={() => move(i, -1)} aria-label="Naik"><ArrowUp size={14} /></button>
                <button onClick={() => move(i, 1)} aria-label="Turun"><ArrowDown size={14} /></button>
                <button onClick={() => setPages((ps) => ps.filter((x) => x.key !== p.key))} data-testid={`grn-wizard-page-remove-${i + 1}`} aria-label="Hapus"><Trash2 size={14} className="text-[#B4231F]" /></button>
              </div>
            ))}
            {!pages.length && <p className="text-[11px] text-[#6B6B73]">Foto boleh menyusul — Anda tetap bisa mengisi surat jalan secara manual.</p>}
          </>)}
          <ErrorBox text={err} />
        </div>
        <div className="flex justify-between gap-2 border-t border-[#EFF0F2] px-4 py-3">
          {step === 2 ? <button className="secondary-button" onClick={() => setStep(1)} data-testid="grn-wizard-back">Kembali</button> : <span />}
          {step === 1
            ? <button className="primary-button" disabled={!partnerId || !whId} onClick={() => setStep(2)} data-testid="grn-wizard-next">Lanjut</button>
            : <button className="primary-button" disabled={busy} onClick={submit} data-testid="grn-wizard-submit">{busy ? "Menyimpan…" : "Buat kedatangan"}</button>}
        </div>
      </div>
    </div>
  );
}
