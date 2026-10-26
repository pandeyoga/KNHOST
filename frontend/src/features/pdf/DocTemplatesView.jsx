/**
 * DocTemplatesView — Pengaturan › Dokumen & Cetak › **Template Dokumen** (`pdf-templates`, fase 3 · P2, D-01).
 *
 * KENAPA: template dokumen dulu diurus di EMPAT tempat — Template PDF (desainer), Template Dokumen Dasar (AdminView
 * tab templates), Master per Badan Usaha (kind `document-templates`, koleksi SAMA dengan Template Dasar) dan kartu
 * "template aktif" di Pusat Cetak. Satu data diedit dua layar. Kini satu layar dengan dua tab:
 *   · "Kop & tata letak dasar" — tabel berlapis global → badan usaha (`EntityMasterKindPanel`, aturan lapisan sama
 *     dengan Master per Badan Usaha) + form terlengkap dari AdminView (`DocTemplateForm`) + Pratinjau;
 *   · "Desainer PDF" — `PdfTemplateDesigner` (tetap khusus admin, seperti dulu).
 * Alias `?view=doc-templates-basic` → tab dasar. Hak tulis dijaga server (izin `template`): manajer membaca.
 */
import { useState } from "react";
import { Eye, FileText, LayoutTemplate, Palette } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import PageTabs from "../../components/PageTabs";
import DetailModal from "../../components/DetailModal";
import DesktopOnlyNotice from "../../components/DesktopOnlyNotice";
import useViewPreset from "../../hooks/useViewPreset";
import { apiErrorText } from "../../utils/apiError";
import { roleCanSee } from "../../config/roles";
import EntityMasterKindPanel from "../settings/masters/EntityMasterKindPanel";
import DocTemplateForm from "../admin/DocTemplateForm";
import PdfTemplateDesigner from "./PdfTemplateDesigner";

export default function DocTemplatesView({ currentUser, selectedEntity, entities = [], orders = [], initialTab = "" }) {
  // Fase 3 · P8 (§1.1 butir 6) — "Desainer PDF" = layar lama `pdf-templates` (tab admin saja): gerbang lewat id itu supaya
  // peran kustom bermodul Admin (katalog akses memuat `pdf-templates`) tidak kehilangan desainernya. Manajer tetap tidak.
  const designerAllowed = roleCanSee(["admin"], currentUser?.role, "pdf-templates");
  const pick = (t) => (t === "desainer" && designerAllowed ? "desainer" : "dasar");
  const [tab, setTab] = useState(() => pick(initialTab));
  useViewPreset("pdf-templates", (p) => { if (p.tab) setTab(pick(p.tab)); });
  const [preview, setPreview] = useState(null);    // { name, html, error }
  const sampleOrder = (orders || [])[0] || null;

  const openPreview = async (row) => {
    setPreview({ name: row.name, html: "", error: "", loading: true });
    try {
      const r = await axios.post(`${API}/document-templates/${row.id}/preview`, { source_id: sampleOrder.id }, { responseType: "text" });
      setPreview({ name: row.name, html: r.data, error: "" });
    } catch (e) {
      setPreview({ name: row.name, html: "", error: apiErrorText(e, "Gagal memuat pratinjau template.") });
    }
  };

  return (
    <div className="grid gap-3" data-testid="doc-templates-view">
      <DesktopOnlyNotice testId="settings-desktop-notice" what="Template Dokumen" />
      <PageTabs testId="doc-templates-tabs" value={tab} onChange={setTab} ariaLabel="Template Dokumen"
        tabs={[
          { key: "dasar", label: "Kop & tata letak dasar", icon: LayoutTemplate },
          { key: "desainer", label: "Desainer PDF", icon: Palette, hidden: !designerAllowed },
        ]} />

      {tab === "desainer" && designerAllowed ? (
        <PdfTemplateDesigner currentUser={currentUser} selectedEntity={selectedEntity} entities={entities} />
      ) : (
        <EntityMasterKindPanel kind="document-templates" entities={entities} selectedEntity={selectedEntity}
          testId="doc-templates-basic-panel" showRibbon
          hintOverride="Kop surat, kolom tabel, kertas, tanda tangan dan urutan bagian untuk cetak dasar Surat Jalan / Faktur. Tiap badan usaha boleh punya salinan sendiri (nama, alamat, logo)."
          renderForm={({ mode, values, setValues }) => (
            <DocTemplateForm values={values} setValues={setValues} lockType={mode === "edit"} />
          )}
          rowActions={(r) => (sampleOrder && r.is_active !== false ? (
            <button type="button" className="secondary-button text-[11px]" data-testid={`doc-template-preview-${r.id}`}
              title={`Pratinjau memakai pesanan ${sampleOrder.number || ""}`} onClick={() => openPreview(r)}>
              <Eye size={12} /> Pratinjau
            </button>
          ) : null)} />
      )}

      <DetailModal open={!!preview} onClose={() => setPreview(null)} framed size="lg" label="Pratinjau template"
        testId="doc-template-preview">
        <div className="mb-2 flex items-center gap-2 pr-6">
          <FileText size={15} className="text-[#0058CC]" />
          <h3 className="text-[13.5px] font-bold">Pratinjau · {preview?.name || "Template"}</h3>
        </div>
        {preview?.error ? (
          <p className="rounded-md border border-[#FCA5A5] bg-[#FEF2F2] px-2.5 py-1.5 text-[11.5px] font-semibold text-[#B91C1C]"
            data-testid="doc-template-preview-error">{preview.error}</p>
        ) : preview?.loading ? (
          <p className="py-8 text-center text-[12px] text-[#6B6B73]">Memuat pratinjau…</p>
        ) : (
          <iframe data-testid="template-live-preview-frame" title="Pratinjau template"
            className="h-[60dvh] w-full rounded-md border border-[#EFF0F2] bg-white" srcDoc={preview?.html || ""} />
        )}
      </DetailModal>
    </div>
  );
}
