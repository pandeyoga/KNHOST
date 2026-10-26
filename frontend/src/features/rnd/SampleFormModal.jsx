/**
 * SampleFormModal — buat permintaan Labdip / Handfeel / Proofing.
 * 1 sample = 1 SPESIFIKASI (wajib; menggantikan tab Spesifikasi terpisah) — selalu dibuat baru bersama sample:
 *   1) Spesifikasi produk target (WAJIB, ikut jenis) · 2) Brief untuk supplier (+ pesanan) · 3) Kapan dibutuhkan.
 * Uji bertahap di kain yang sama → tambah JENIS ke permintaan yang sama (tombol "Tambah jenis" di rincian), bukan permintaan baru.
 */
import { useEffect, useState } from "react";
import { Beaker, CalendarClock, FlaskConical, Package } from "lucide-react";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import KNDatePicker from "../../components/KNDatePicker";
import useCatalogMasters from "../../hooks/useCatalogMasters";
import axios, { API } from "../../services/apiClient";
import { createSample, listColors, listDesigns, listSamples, rndMeta, sampleTypes } from "./rndApi";
import { errMsg, typeTone } from "./rndMeta";
import SampleSpecFields, { EMPTY_SPEC, buildSpecPayload, specProblems, toTarget } from "./SampleSpecFields";
import { emptyColor } from "./ColorTargetsEditor";
import ExistingSkuSection from "./ExistingSkuSection";
import { measurementMeta, typeLabel, typeMeta } from "./sampleTypeMeta";
import { REASON_MIN_LENGTH } from "../../services/confirmService";

const listBaseFabrics = () => axios.get(`${API}/rnd/base-fabrics`).then((r) => r.data?.items || []);
// UAT 24 Okt (audit UI tahap 2) — G5-44: contoh isian per jenis (dulu Handfeel/Proofing/Uji ulang memakai contoh labdip
// "Labdip Katun Combed…", "ΔE 1.5").
const PLACEHOLDERS = {
  labdip: { title: "mis. Labdip Katun Combed 150 gsm — biru dongker", brief: "mis. Cocokkan warna target maksimal ΔE 1,5, kirim swatch 3 meter" },
  handfeel: { title: "mis. Handfeel Rayon Twill 180 gsm", brief: "mis. Rasa lembut & jatuh seperti kain acuan, gramasi 180 gsm ± 5%, kirim 3 meter" },
  proofing: { title: "mis. Proofing motif Kawung — katun 150 gsm", brief: "mis. Cetak satu repeat penuh sesuai desain, kirim foto hasil cetak + 1 meter" },
  existing: { title: "mis. Uji ulang SKU dari supplier baru", brief: "mis. Bandingkan dengan SKU aktif (warna & rasa kain), kirim 3 meter" },
  other: { title: "mis. Sample kain katun 150 gsm", brief: "mis. Jelaskan yang harus dicocokkan supplier & jumlah kiriman" },
};
const hasAcc = (s, code) => s.status === "decided" || (s.rounds || []).some((r) => r.result === "acc" && (!r.type_code || r.type_code === code));

// Audit UI 24 Okt — badge "WAJIB" di judul bagian dihapus: isian wajib sudah bertanda *.
function Section({ step, icon: Icon, title, hint, children, testId }) {
  return (
    <section className="rounded-xl border border-[#EFF0F2] bg-[#FAFBFC] p-3" data-testid={testId}>
      <div className="mb-2.5 flex items-start gap-2">
        <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#0058CC] text-[10px] font-bold text-white">{step}</span>
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-[12px] font-bold text-[#1C1C1E]">
            <Icon size={13} className="text-[#6B6B73]" /> {title}
          </p>
          {hint && <p className="text-[11px] text-[#6B6B73]">{hint}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}

export default function SampleFormModal({ selectedEntity, prefill, lockType = "", purpose = "", onClose, onSaved }) {
  const [colors, setColors] = useState([]);
  const [designs, setDesigns] = useState([]);
  // UAT 24 Okt (P4.2/P4.3/P4.8) — handfeel induk (labdip produk baru), warna labdip berkelompok, kain dasar lolos.
  const [handfeels, setHandfeels] = useState([]);
  const [parentId, setParentId] = useState(prefill?.parent_sample_id || "");
  // Keputusan pemilik K-16 (26 Okt) — labdip produk baru TANPA handfeel ACC boleh, dengan peringatan + alasan wajib.
  const [skipParent, setSkipParent] = useState(false);
  const [skipReason, setSkipReason] = useState("");
  const [colorTargets, setColorTargets] = useState(prefill?.color_id ? [{ ...emptyColor(), color_id: prefill.color_id }] : [emptyColor()]);
  const [passed, setPassed] = useState(null);
  const [policy, setPolicy] = useState({});
  const [types, setTypes] = useState([]);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [f, setF] = useState({
    sample_types: prefill?.sample_types || (prefill?.sample_type ? [prefill.sample_type] : (lockType ? [lockType] : [])),
    title: "", brief: "",
    color_id: prefill?.color_id || "", design_id: prefill?.design_id || "",
    so_id: prefill?.so_id || "", line_code: prefill?.line_code || "",
    target_date: "", qty_requested: "3", unit: "meter",
  });
  const [touched, setTouched] = useState(false);
  const set = (k, v) => { setTouched(true); setF((p) => ({ ...p, [k]: v })); };
  const masters = useCatalogMasters({ current: { base_unit: f.unit } });
  const [catalog, setCatalog] = useState({});
  const [sp, setSp] = useState(EMPTY_SPEC);
  const [mode, setMode] = useState(purpose === "revalidation" ? "existing" : "new");
  const [existing, setExisting] = useState(null);
  const [reval, setReval] = useState({ supplierId: "", reason: "" });
  const isExisting = mode === "existing";
  useEffect(() => {   // UAT 24 Okt (P5.2) — SKU yang diuji ulang terisi dari tautan "Uji ulang SKU ini"
    if (!prefill?.product?.id) return;
    setMode("existing");
    setExisting(prefill.product);
  }, [prefill?.product]);

  useEffect(() => {
    const params = selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {};
    listColors().then((c) => setColors(Array.isArray(c) ? c : c?.items || [])).catch(() => {});
    listDesigns().then((d) => setDesigns(Array.isArray(d) ? d : d?.items || [])).catch(() => {});
    rndMeta(params).then((m) => setPolicy(m?.policy || {})).catch(() => {});
    listSamples({ ...params, sample_type: "handfeel", purpose: "new_development", limit: 200 })
      .then((r) => setHandfeels((r?.items || []).filter((s) => hasAcc(s, "handfeel")))).catch(() => {});
  }, [selectedEntity]);

  useEffect(() => {
    const p = {};
    if (selectedEntity && selectedEntity !== "all") p.entity_id = selectedEntity;
    if (f.line_code) p.line = f.line_code;
    sampleTypes(p).then((rows) => setTypes(Array.isArray(rows) ? rows : [])).catch(() => {});
  }, [selectedEntity, f.line_code]);

  useEffect(() => {
    if (f.sample_types.length || types.length === 0) return;
    if (prefill?.need_design !== undefined) {
      const hit = types.find((t) => Boolean(t.requires_design) === Boolean(prefill.need_design));
      if (hit) setF((p) => ({ ...p, sample_types: [hit.value] }));   // otomatis, bukan isian pengguna
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [types]);

  const toggleType = (code) => setF((p) => ({
    ...p, sample_types: p.sample_types.includes(code) ? p.sample_types.filter((x) => x !== code) : [...p.sample_types, code],
  }));

  const needDesign = f.sample_types.some((c) => typeMeta(c, types).requires_design);
  const isLabdip = f.sample_types.includes("labdip");
  const needParent = isLabdip && !f.sample_types.includes("handfeel") && policy.require_stage_chain !== false && !prefill?.special_order_id;
  useEffect(() => {
    if (needDesign && passed === null && policy.require_stage_chain !== false) {
      listBaseFabrics().then((rows) => setPassed(new Set(rows.map((t) => t.id)))).catch(() => setPassed(new Set()));
    }
  }, [needDesign, passed, policy.require_stage_chain]);
  const skipOk = skipParent && skipReason.trim().length >= REASON_MIN_LENGTH;
  const problems = [...specProblems({ sp, catalog, f, sampleTypes: f.sample_types, types, colorTargets: isLabdip ? colorTargets : null }),
    ...(needParent && !parentId && !skipParent ? ["sampel handfeel induk yang ACC (labdip produk baru)"] : []),
    ...(needParent && !parentId && skipParent && !skipOk ? [`alasan lanjut tanpa handfeel ACC (minimal ${REASON_MIN_LENGTH} huruf)`] : [])];
  const titleOk = f.title.trim().length > 0;
  const typesOk = f.sample_types.length > 0;
  // K-14 (26 Okt) — alasan minimum seragam 5 huruf (server `rnd_revalidation_service.prepare` sama).
  const existingOk = !!existing && typesOk && !!reval.supplierId && reval.reason.trim().length >= REASON_MIN_LENGTH;
  const canSave = isExisting ? existingOk : titleOk && typesOk && problems.length === 0;

  const submit = async () => {
    setErr(""); setSaving(true);
    try {
      const base = {
        sample_types: f.sample_types, title: f.title, brief: f.brief, so_id: f.so_id,
        target_date: f.target_date, qty_requested: f.qty_requested || 0, unit: f.unit,
      };
      const targets = isLabdip ? colorTargets.map(toTarget) : [];
      const created = await createSample(isExisting ? {
        ...base, product_id: existing.id, unit: existing.base_unit || f.unit,
        revalidation_supplier_id: reval.supplierId, revalidation_reason: reval.reason,
      } : {
        ...base, color_target: targets[0] || (f.color_id ? { color_id: f.color_id } : {}), color_targets: targets,
        design_id: needDesign ? f.design_id : "", line_code: f.line_code, parent_sample_id: needParent || parentId ? parentId : "",
        chain_override_reason: needParent && !parentId && skipParent ? skipReason.trim() : "",
        special_order_id: prefill?.special_order_id || "",
        spec: buildSpecPayload({ sp, catalog, f, sampleTypes: f.sample_types, colorTargets: isLabdip ? colorTargets : null }),
      });
      onSaved?.(created);
    } catch (e) {
      setErr(errMsg(e, "Gagal membuat permintaan sample."));
      setSaving(false);
    }
  };

  const lockLabel = lockType ? typeLabel(lockType, types).split(" (")[0] : "";
  const ph = isExisting ? PLACEHOLDERS.existing
    : PLACEHOLDERS[lockType || f.sample_types[0]] || PLACEHOLDERS.other;
  // G5-44: subjudul per tujuan — uji ulang TIDAK membuat SKU/spesifikasi baru (dulu "saat ACC … SKU lahir" untuk semua).
  const subtitle = (purpose === "revalidation" || isExisting)
    ? "Uji ulang SKU yang sudah aktif — tidak membuat SKU atau spesifikasi baru."
    : "Setiap permintaan lahir bersama SPESIFIKASI produk target-nya — saat ACC, spesifikasi ikut ACC dan SKU lahir di master.";
  const autoTitle = () => {
    if (f.title.trim()) return;
    const parts = [f.sample_types.map((c) => typeLabel(c, types).split(" (")[0]).join("+"), catalog.template_name || sp.base_fabric_name,
      sp.gramasi && `${sp.gramasi} gsm`, colorTargets.length > 1 ? `${colorTargets.length} warna` : (colorTargets[0]?.name || colors.find((c) => c.id === (colorTargets[0]?.color_id || f.color_id))?.name)].filter(Boolean);
    if (parts.length > 1) set("title", parts.join(" — "));
  };

  return (
    <FormModal open onClose={onClose} title={purpose === "revalidation" ? "Uji Ulang SKU" : lockType ? `Sample ${lockLabel} Baru` : "R&D Produk Baru"}
      subtitle={subtitle}
      icon={Beaker} size="lg" testId="sample-form-modal"
      onSubmit={submit} submitLabel={isExisting ? "Simpan Uji Tambahan" : "Simpan Permintaan + Spesifikasi"} busy={saving} error={err}
      submitDisabled={!canSave} submitTestId="sample-form-save">
      <div className="grid gap-3">
        {prefill?.source_label && (
          <div className="rounded-lg bg-[#F2F7FF] px-3 py-2 text-[11.5px] text-[#004099]" data-testid="sample-form-prefill">
            Diisi otomatis dari <b>{prefill.source_label}</b>.
          </div>
        )}

        {!purpose && (!lockType || lockType !== "proofing") ? (
          <div className="flex gap-1.5" data-testid="sample-mode-picker">
            {[["new", "Pengembangan baru (spesifikasi baru)"], ["existing", "Uji tambahan SKU existing"]].map(([v, l]) => (
              <button key={v} type="button" data-testid={`sample-mode-${v}`} onClick={() => setMode(v)}
                className={`rounded-full px-3 py-1 text-[11px] font-semibold transition-[background-color,color] ${mode === v ? "bg-[#0058CC] text-white" : "bg-[#F2F3F5] text-[#3C3C43]"}`}>{l}</button>
            ))}
          </div>
        ) : null}

        <Section step={1} icon={Package} title={isExisting ? "SKU aktif yang diuji ulang" : "Spesifikasi produk target"} testId="sample-section-spec"
          hint={isExisting ? "Pilih jenis uji, SKU aktif, lalu supplier yang diuji ulang beserta alasannya. Tidak ada SKU atau spesifikasi baru yang dibuat." : "Isinya menyesuaikan jenis: labdip → warna target · proofing → desain ACC · handfeel → konstruksi kain. Pilih lebih dari satu jenis bila kain yang sama diuji bertahap — spesifikasinya tetap satu."}>
          <div className="mb-3">
            <span className="mb-1 block text-[10.5px] font-semibold text-[#6B6B73]">Jenis sampling * (boleh lebih dari satu)</span>
            <div className="flex flex-wrap gap-1.5" data-testid="sample-type-picker">
              {types.length === 0 && <span className="text-[11.5px] text-[#8C4A00]" data-testid="sample-type-empty">Belum ada jenis sampling aktif. Tambahkan di Pengaturan → Master → Jenis Sampling.</span>}
              {types.map((t) => {
                const on = f.sample_types.includes(t.value);
                const tone = typeTone(t.value);
                const locked = lockType && t.value === lockType;
                return (
                  <button key={t.value} type="button" data-testid={`sample-type-${t.value}`} onClick={() => { if (!locked) toggleType(t.value); }}
                    title={locked ? "Jenis utama tab ini — tidak bisa dilepas" : (t.notes || "")}
                    className={`rounded-full border px-3 py-1 text-[11px] font-medium transition-[background-color,border-color,color] ${locked ? "cursor-default" : ""}`}
                    style={on ? { background: tone.fg, borderColor: tone.fg, color: "#fff" } : { background: "#fff", borderColor: "#E5E5EA", color: "#3C3C43" }}>
                    {t.label}{t.requires_design ? " · wajib desain" : ""}{locked ? " · utama" : ""}
                  </button>
                );
              })}
            </div>
            {typesOk && (
              <p className="mt-1 text-[10.5px] text-[#6B6B73]" data-testid="sample-type-summary">
                Hasil ukur: {f.sample_types.map((c) => `${typeLabel(c, types).split(" (")[0]} → ${(typeMeta(c, types).measurement_fields || []).map((x) => measurementMeta(x).label).join(", ") || "foto + catatan"}`).join(" · ")}
              </p>
            )}
          </div>

          {isExisting ? <ExistingSkuSection product={existing} onPick={setExisting} supplierId={reval.supplierId} reason={reval.reason}
            onRevalChange={(patch) => setReval((p) => ({ ...p, ...patch }))} /> : (
            <>
              {needParent && (
                <label className="mb-2.5 block" data-testid="sample-parent-wrap">
                  <span className="mb-1 block text-[10.5px] font-semibold text-[#6B6B73]">Sampel handfeel induk (ACC) * — urutan produk baru: handfeel → labdip → produk</span>
                  <KNSelect data-testid="sample-parent" className="field" value={parentId} searchable
                    options={[{ value: "", label: handfeels.length ? "— pilih handfeel yang sudah ACC —" : "— belum ada handfeel ACC (buat handfeel dulu) —" },
                      ...handfeels.map((s) => ({ value: s.id, label: `${s.number} · ${s.title}${s.status === "decided" ? " · pemenang dipilih" : " · ada ronde ACC"}` }))]}
                    onValueChange={setParentId} />
                  {parentId && <span className="mt-1 block text-[10.5px] text-[#1B7F4B]">Konstruksi kain (jenis, gramasi, lebar, benang) diwarisi dari handfeel induk saat disimpan.</span>}
                  {/* G5-44: jalan keluar bila belum ada handfeel ACC (dulu isian wajib buntu tanpa tautan). */}
                  {!handfeels.length && (
                    <span className="mt-1 block text-[10.5px] text-[#8C4A00]" data-testid="sample-parent-empty-hint">
                      Belum ada sample handfeel yang ACC.{" "}
                      {types.some((t) => t.value === "handfeel") && (
                        <button type="button" className="link-button" data-testid="sample-parent-add-handfeel" onClick={() => toggleType("handfeel")}>
                          Uji handfeel sekalian di permintaan ini
                        </button>
                      )}
                      {" "}atau buat sample Handfeel dulu lewat menu R&amp;D › Handfeel.
                    </span>
                  )}
                </label>
              )}
              {needParent && !parentId && (
                <div className="mb-2.5" data-testid="sample-parent-skip-wrap">
                  <label className="flex items-center gap-2 text-[11.5px] font-semibold text-[#3C3C43]">
                    <input type="checkbox" data-testid="sample-parent-skip" checked={skipParent}
                      onChange={(e) => { setTouched(true); setSkipParent(e.target.checked); }} />
                    Lanjut tanpa handfeel ACC
                  </label>
                  {skipParent && (
                    <div className="mt-1.5 rounded-lg border border-[#F2B48A] bg-[#FFF4E5] p-2.5" data-testid="sample-parent-skip-warning">
                      <p className="text-[11px] text-[#8A5300]">
                        <b>Peringatan:</b> labdip tanpa handfeel ACC berisiko — konstruksi kain (rasa, gramasi, lebar) belum
                        teruji, sehingga warna yang ACC bisa bergeser bila kainnya nanti diganti. Alasan wajib diisi dan
                        tercatat di riwayat sample.
                      </p>
                      <label className="mt-1.5 block">
                        <span className="mb-1 block text-[10.5px] font-semibold text-[#6B6B73]">Alasan lanjut tanpa handfeel ACC *</span>
                        <textarea className="field" rows={2} data-testid="sample-parent-skip-reason" value={skipReason}
                          onChange={(e) => { setTouched(true); setSkipReason(e.target.value); }}
                          placeholder="mis. kain sama dengan produk berjalan, pelanggan hanya minta warna baru" />
                      </label>
                      {skipReason.trim().length > 0 && !skipOk && (
                        <span className="mt-1 block text-[10.5px] text-[#B45309]" data-testid="sample-parent-skip-hint">
                          Minimal {REASON_MIN_LENGTH} huruf.
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )}
              <SampleSpecFields sp={sp} setSp={(v) => { setTouched(true); setSp(v); }} catalog={catalog} setCatalog={setCatalog} f={f} set={set}
                sampleTypes={f.sample_types} types={types} colors={colors} designs={designs}
                colorTargets={colorTargets} setColorTargets={(v) => { setTouched(true); setColorTargets(v); }} maxColors={Number(policy.labdip_max_colors) || 10}
                passedFabrics={policy.require_stage_chain === false ? null : passed} />
            </>
          )}
          {/* Audit UI 24 Okt (039) — dulu merah "Belum lengkap" sejak form dibuka. Kini panduan netral; merah hanya
              setelah pengguna mulai mengisi bagian ini (judul/brief/warna/spesifikasi berubah). */}
          {!isExisting && problems.length > 0 && typesOk && (
            <p className={`mt-2 text-[11px] ${touched ? "text-[#A8221A]" : "text-[#6B6B73]"}`} data-testid="sample-spec-problems">
              {touched ? "Belum lengkap" : "Agar bisa disimpan, lengkapi"}: <b>{problems.join(", ")}</b>.
            </p>
          )}
        </Section>

        <Section step={2} icon={FlaskConical} title="Brief untuk supplier" testId="sample-section-what"
          hint="Judul terisi otomatis dari spesifikasi bila dikosongkan lalu diklik di luar kolom.">
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            <label className="block sm:col-span-2">
              <span className="mb-1 block text-[10.5px] font-semibold text-[#6B6B73]">Judul permintaan {isExisting ? "(otomatis bila kosong)" : "*"}</span>
              <input className="field" data-testid="sample-title-input" value={f.title} onChange={(e) => set("title", e.target.value)} onBlur={autoTitle}
                placeholder={ph.title} />
            </label>
            <label className="block">
              <span className="mb-1 block text-[10.5px] font-semibold text-[#6B6B73]">Jumlah diminta</span>
              <input className="field" type="number" min="0" step="any" inputMode="decimal" data-testid="sample-qty-input" value={f.qty_requested}
                onChange={(e) => set("qty_requested", e.target.value)} placeholder="3" />
            </label>
            <label className="block">
              <span className="mb-1 block text-[10.5px] font-semibold text-[#6B6B73]">Satuan</span>
              <KNSelect data-testid="sample-unit-input" className="field" value={f.unit} options={masters.unitOptions} onValueChange={(v) => set("unit", v)} />
            </label>
            {/* UAT 24 Okt (P4.5) — tautan pesanan pelanggan hanya bila sampel lahir dari pesanan (terisi otomatis). */}
            {f.so_id && (
              <p className="sm:col-span-2 text-[11px] text-[#004099]" data-testid="sample-so">Untuk pesanan pelanggan: <b>{prefill?.so_number || prefill?.source_label || f.so_id}</b> (terisi otomatis)</p>
            )}
            <label className="block sm:col-span-2">
              <span className="mb-1 block text-[10.5px] font-semibold text-[#6B6B73]">Brief untuk supplier</span>
              <textarea className="field" rows={3} data-testid="sample-brief-input" value={f.brief} onChange={(e) => set("brief", e.target.value)}
                placeholder={ph.brief} />
            </label>
          </div>
        </Section>

        <Section step={3} icon={CalendarClock} title="Kapan dibutuhkan" hint="Tenggat tiap round mengikuti SLA bila dikosongkan." testId="sample-section-when">
          <label className="block sm:w-1/2">
            <span className="mb-1 block text-[10.5px] font-semibold text-[#6B6B73]">Target tanggal selesai</span>
            <KNDatePicker data-testid="sample-target-date" value={f.target_date} onChange={(v) => set("target_date", v)} placeholder="Pilih tanggal" />
          </label>
        </Section>
      </div>
    </FormModal>
  );
}
