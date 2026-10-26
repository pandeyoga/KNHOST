/**
 * SampleSpecPanel — blok SPESIFIKASI di rincian sample (1 sample = 1 spesifikasi).
 * Ada spesifikasi → ringkasan lengkap + ubah (MD, sebelum ACC). Belum ada (data lama) → peringatan + "Lengkapi spesifikasi".
 *
 * Fase 3 · P6 (D-24c) — "Ubah" membuka `SpecFormModal` mode ubah (form yang SAMA dengan Spesifikasi Baru;
 * dulu `EditSpecModal` 6 isian). Warna & desain dikunci (`lockLinks`) karena ronde sample berjalan di atasnya.
 */
import { useEffect, useState } from "react";
import { AlertTriangle, ClipboardList, Pencil, Save } from "lucide-react";
import FormModal from "../../components/FormModal";
import { formatCurrency } from "../../utils/formatters";
import axios, { API } from "../../services/apiClient";
import { listColors, listDesigns, listSpecs, sampleTypes as fetchTypes } from "./rndApi";
import { errMsg, fabricLabel, SPEC_STATUS_META, variantText } from "./rndMeta";
import { Footer } from "./RndField";
import SampleSpecFields, { EMPTY_SPEC, buildSpecPayload, specProblems } from "./SampleSpecFields";
import SpecFormModal from "./SpecFormModal";


export default function SampleSpecPanel({ sample, canEdit, onChanged, types = [] }) {
  // UAT 24 Okt (audit UI tahap 2) — G5-45: satu sumber spesifikasi. Kepala rincian menyebut "dari KSC/SPEC-…" tetapi
  // kartu ini berbunyi "Belum ada spesifikasi — data lama" bila server tak menyertakan `spec`. Kini: bila nomor
  // spesifikasi tercatat, kartunya dicari lewat nomor itu; bila tetap tidak ketemu, kalimatnya jujur menyebut nomornya.
  const [found, setFound] = useState(null);
  const [lookup, setLookup] = useState("");   // "" | "loading" | "missing"
  const wantNumber = !sample.spec && (sample.spec_number || "");
  useEffect(() => {
    if (!wantNumber) { setFound(null); setLookup(""); return undefined; }
    let alive = true;
    setLookup("loading");
    listSpecs({ q: wantNumber, limit: 5 })
      .then((r) => {
        const hit = (r?.items || []).find((x) => x.number === wantNumber) || null;
        if (alive) { setFound(hit); setLookup(hit ? "" : "missing"); }
      })
      .catch(() => { if (alive) setLookup("missing"); });
    return () => { alive = false; };
  }, [wantNumber]);
  const spec = sample.spec || found || null;
  const [modal, setModal] = useState(""); // "complete" | "edit"
  const editable = canEdit && spec && ["draft", "review"].includes(spec.status);
  const t = spec?.target || {};
  const md = sample.master_data || {};

  return (
    <div className="section-card section-pad" data-testid="sample-spec-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-[#9A9BA3]"><ClipboardList size={12} /> Spesifikasi produk target</p>
        {spec && (
          <span className="flex items-center gap-1.5">
            <span className="font-mono text-[11px] text-[#6B6B73]" data-testid="sample-spec-number">{spec.number}</span>
            <span className={`status-pill ${(SPEC_STATUS_META[spec.status] || {}).cls || "pill-muted"}`} data-testid="sample-spec-status">{(SPEC_STATUS_META[spec.status] || {}).label || spec.status}</span>
            {editable && <button className="secondary-button !px-2 !py-1 text-[10.5px]" data-testid="sample-spec-edit-button" onClick={() => setModal("edit")}><Pencil size={11} /> Ubah</button>}
          </span>
        )}
      </div>

      {!spec && lookup === "loading" ? (
        <div className="mt-2 h-10 animate-pulse rounded-lg bg-[#F2F2F5]" data-testid="sample-spec-loading" />
      ) : !spec && wantNumber ? (
        <div className="mt-2 rounded-lg border border-[#F5C26B] bg-[#FFF8EE] px-3 py-2" data-testid="sample-spec-missing">
          <p className="flex items-center gap-1.5 text-[11.5px] text-[#8C4A00]"><AlertTriangle size={13} /> Spesifikasi <b className="font-mono">{wantNumber}</b> tercatat pada permintaan ini, tetapi rinciannya tidak dapat dimuat (data lama / di badan usaha lain). Buka lewat R&amp;D › Spesifikasi Produk.</p>
        </div>
      ) : !spec ? (
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[#F5C26B] bg-[#FFF8EE] px-3 py-2" data-testid="sample-spec-missing">
          <p className="flex items-center gap-1.5 text-[11.5px] text-[#8C4A00]"><AlertTriangle size={13} /> <b>Belum ada spesifikasi</b> — data lama. Tanpa spesifikasi, SKU produk tidak bisa lahir saat ACC.</p>
          {canEdit && <button className="primary-button !py-1.5 text-[11px]" data-testid="sample-spec-complete-button" onClick={() => setModal("complete")}>Lengkapi spesifikasi</button>}
        </div>
      ) : (
        <dl className="mt-2 grid grid-cols-1 gap-x-4 gap-y-1.5 text-[11.5px] sm:grid-cols-2 lg:grid-cols-3" data-testid="sample-spec-summary">
          <Row k="Induk produk">{md.template?.name || (spec.template_id ? spec.template_id : "— produk konsep mandiri")}</Row>
          <Row k="Kombinasi varian">{variantText(spec.variant_attrs) || "—"}</Row>
          <Row k="Jenis kain">{fabricLabel(t.fabric_type) || "—"}</Row>
          <Row k="Gramasi">{t.gramasi ? `${t.gramasi} gsm` : "—"}</Row>
          <Row k="Lebar">{t.lebar ? `${t.lebar} cm` : "—"}</Row>
          <Row k="Satuan">{spec.base_unit || sample.unit || "—"}</Row>
          {(t.yarn_count || t.epi || t.ppi) && <Row k="Konstruksi">{[t.yarn_count && `${t.yarn_count}${t.yarn_count_system ? ` ${t.yarn_count_system}` : ""}`, t.epi && `EPI ${t.epi}`, t.ppi && `PPI ${t.ppi}`].filter(Boolean).join(" · ")}</Row>}
          <Row k="Warna target (KN)">{spec.color_target?.name ? `${spec.color_target.code} · ${spec.color_target.name}` : "—"}</Row>
          <Row k="Nama versi supplier">{sample.decision?.supplier_item_name || "— (diisi saat ACC pemenang)"}</Row>
          <Row k="Warna versi supplier">{sample.decision?.supplier_color_name || sample.decision?.supplier_color_code
            ? [sample.decision.supplier_color_name, sample.decision.supplier_color_code].filter(Boolean).join(" · ") : "— (diisi saat ACC pemenang)"}</Row>
          <Row k="Desain">{spec.design_code || sample.design_code ? `${spec.design_code || sample.design_code} v${spec.design_version || sample.design_version || 1}` : "—"}</Row>
          <Row k="Kain dasar">{spec.base_fabric_name || "—"}</Row>
          <Row k="SKU usulan">{spec.sku_hint || "otomatis saat ACC"}</Row>
          <Row k="Target harga">{Number(spec.target_price) > 0 ? formatCurrency(spec.target_price) : "—"}</Row>
          <Row k="Produk lahir">{spec.product_sku ? <b className="font-mono">{spec.product_sku}</b> : "belum (saat ACC pemenang)"}</Row>
          {spec.notes && <Row k="Catatan" wide>{spec.notes}</Row>}
        </dl>
      )}
      {/* 23 Okt — OD dari HP tidak membawa gramasi/lebar; dulu baru ketahuan SETELAH pemenang dipilih (SKU tak lahir). */}
      {spec && !spec.product_sku && (!t.gramasi || !t.lebar) && (
        <p className="mt-2 flex items-center gap-1.5 rounded-lg border border-[#F5C26B] bg-[#FFF8EE] px-3 py-1.5 text-[11px] text-[#8C4A00]" data-testid="sample-spec-incomplete">
          <AlertTriangle size={12} /> Lengkapi <b>{[!t.gramasi && "gramasi", !t.lebar && "lebar"].filter(Boolean).join(" & ")}</b> sebelum memilih pemenang — tanpa itu SKU produk tidak lahir otomatis saat ACC.
        </p>
      )}

      {modal === "complete" && <CompleteSpecModal sample={sample} onClose={() => setModal("")} onDone={() => { setModal(""); onChanged?.(); }} />}
      {modal === "edit" && (
        <SpecFormModal spec={spec} types={types} lockLinks templateName={md.template?.name || ""}
          onClose={() => setModal("")} onSaved={() => { setModal(""); onChanged?.(); }} />
      )}
    </div>
  );
}

function Row({ k, children, wide }) {
  return (
    <div className={`flex items-start justify-between gap-2 border-b border-[#F2F2F5] py-1 ${wide ? "sm:col-span-2 lg:col-span-3" : ""}`}>
      <dt className="shrink-0 text-[#6B6B73]">{k}</dt><dd className="text-right font-semibold text-[#1C1C1E]">{children}</dd>
    </div>
  );
}

function CompleteSpecModal({ sample, onClose, onDone }) {
  const [types, setTypes] = useState([]);
  const [colors, setColors] = useState([]);
  const [designs, setDesigns] = useState([]);
  const [catalog, setCatalog] = useState({});
  const [sp, setSp] = useState(EMPTY_SPEC);
  const [f, setF] = useState({ title: sample.title || "", unit: sample.unit || "meter", line_code: sample.line_code || "",
    color_id: sample.color_target?.color_id || "", design_id: sample.design_id || "", so_id: sample.so_id || "" });
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const sampleTypes = sample.sample_types || [];
  useEffect(() => {
    fetchTypes({}).then((r) => setTypes(Array.isArray(r) ? r : [])).catch(() => {});
    listColors().then((c) => setColors(Array.isArray(c) ? c : c?.items || [])).catch(() => {});
    listDesigns().then((d) => setDesigns(Array.isArray(d) ? d : d?.items || [])).catch(() => {});
  }, []);
  const problems = specProblems({ sp, catalog, f, sampleTypes, types });
  const save = async () => {
    setBusy(true); setErr("");
    try {
      await axios.post(`${API}/rnd/samples/${sample.id}/spec`, buildSpecPayload({ sp, catalog, f, sampleTypes }));
      onDone();
    } catch (e) { setErr(errMsg(e, "Gagal menyimpan spesifikasi.")); setBusy(false); }
  };
  return (
    <FormModal open onClose={onClose} size="lg" testId="sample-spec-complete-modal" icon={ClipboardList} error={err}
      title={`Lengkapi spesifikasi · ${sample.number}`} subtitle="Spesifikasi produk target untuk permintaan ini — wajib agar SKU bisa lahir saat ACC"
      footer={<Footer onClose={onClose} onConfirm={save} busy={busy} disabled={problems.length > 0} icon={Save} testId="sample-spec-complete-save" confirmLabel="Simpan spesifikasi" />}>
      <div className="grid gap-3">
        <SampleSpecFields sp={sp} setSp={setSp} catalog={catalog} setCatalog={setCatalog} f={f} set={set}
          sampleTypes={sampleTypes} types={types} colors={colors} designs={designs} testPrefix="complete-spec" />
        {problems.length > 0 && <p className="text-[11px] text-[#A8221A]" data-testid="complete-spec-problems">Belum lengkap: <b>{problems.join(", ")}</b>.</p>}
      </div>
    </FormModal>
  );
}
