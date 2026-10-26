/**
 * myApprovalsParts — potongan tampilan panel **Matriks divisi** (dulu layar "Persetujuan Saya", PS-20 / D-14).
 * Diekstrak dari `MyApprovalsView.jsx` saat penggabungan D-06 (fase 3 · P3) supaya panel & berkasnya < 500 baris.
 */
import { FileCheck2, Layers3, ShoppingBag, ClipboardCheck, Factory, ShieldCheck, ScrollText, Users2 } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";
import { actorLabel } from "../../utils/actorLabel";
import { roleLabel } from "../../config/roles";

export const STAGE_META = {
  design_acc: { label: "ACC Desain", icon: FileCheck2, fg: "#6B219A", bg: "#F3E9FA" },
  sample_acc: { label: "ACC Sample", icon: Layers3, fg: "#0E7490", bg: "#E0F2FE" },
  po_custom: { label: "PO Custom", icon: ShoppingBag, fg: "#B45309", bg: "#FEF3C7" },
  purchase_request: { label: "Permintaan Pembelian", icon: ClipboardCheck, fg: "#1B7F4B", bg: "#E9F7EF" },
  makloon_claim: { label: "Klaim Selisih Makloon", icon: Factory, fg: "#A8221A", bg: "#FDECEA" },
};

// Audit UI 24 Okt (001) — catatan jejak keputusan sample kadang berisi KODE alasan (backend menulis
// `reason_code` sebagai catatan bila catatan kosong — routers/rnd.py `amx.record(... note=payload.note or
// payload.reason_code)`). Label sama dengan `DECISION_REASONS` di services/rnd_sample_service.py.
const DECISION_REASON_LABEL = {
  warna_paling_dekat: "Warna paling dekat dengan target",
  mutu_terbaik: "Mutu/handfeel terbaik",
  harga_terbaik: "Harga terbaik pada mutu setara",
  lead_time: "Lead time paling cepat",
  kapasitas: "Kapasitas produksi memadai",
  permintaan_pelanggan: "Diminta pelanggan",
};
const noteLabel = (n) => DECISION_REASON_LABEL[String(n || "").trim()] || n;

const MODE_TONE = {
  enforce: "bg-[#E9F7EF] text-[#1B7F4B]",
  warn: "bg-[#FEF3C7] text-[#B45309]",
  off: "bg-[#F5F5F7] text-[#8E8E93]",
};

export function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("id-ID",
      { day: "2-digit", month: "short", year: "2-digit" });
  } catch { return "—"; }
}

function fmtWaktu(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("id-ID",
      { timeZone: "Asia/Jakarta", day: "2-digit", month: "short",
        hour: "2-digit", minute: "2-digit" });
  } catch { return "—"; }
}

/** Kartu ringkas satu tahap (juga berfungsi sebagai saringan). */
export function StageCard({ stage, count, active, onClick }) {
  const meta = STAGE_META[stage] || {};
  const Icon = meta.icon || ShieldCheck;
  return (
    <button type="button" onClick={onClick} aria-pressed={active}
      data-testid={`my-approvals-stage-${stage}`}
      className={`rounded-xl border p-3 text-left transition-colors ${
        active ? "border-[#0058CC] bg-[#EFF4FF]" : "border-[#E5E5EA] bg-white hover:border-[#0058CC]"}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex min-w-0 items-center gap-1.5 text-[12px] font-bold text-[#1C1C1E]">
          <Icon size={13} style={{ color: meta.fg }} /> {meta.label || stage}
        </span>
        <span className="rounded-full px-2 py-0.5 text-[10.5px] font-bold"
          style={{ background: meta.bg, color: meta.fg }}
          data-testid={`my-approvals-count-${stage}`}>{count}</span>
      </div>
      <p className="mt-1 text-[10.5px] text-[#6B6B73]">menunggu keputusan</p>
    </button>
  );
}

/** Rantai tingkat persetujuan (mis. Manager → Direksi). */
// UAT 24 Okt (audit UI tahap 2, G5-22) — dua gaya untuk hal yang sama ("Tingkat 1/1 · Manager" pil abu vs
// "○ 1. Manager" oranye): kini satu bentuk pil + istilah Indonesia.
const levelText = (t) => String(t || "").replace(/\bManager\b/g, "Manajer").replace(/\bOwner\b/g, "Pemilik");
export function ChainPills({ chain = [], level = 1, total = 1, label = "" }) {
  if (!chain.length) {
    return (
      <span className="inline-block rounded-full bg-[#FFF4E5] px-2 py-0.5 text-[10px] font-semibold text-[#B45309]">
        ○ {level}/{total}{label ? `. ${levelText(label)}` : ""}
      </span>
    );
  }
  return (
    <span className="flex flex-wrap items-center gap-1">
      {chain.map((lv) => (
        <span key={lv.level}
          className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ${
            lv.status === "approved"
              ? "bg-[#E9F7EF] text-[#1B7F4B]"
              : "bg-[#FFF4E5] text-[#B45309]"}`}>
          {lv.status === "approved" ? "✓ " : "○ "}{lv.level}. {levelText(lv.label)}
        </span>
      ))}
    </span>
  );
}

/** Pil status penegakan matriks (mode, cakupan, pemisahan tugas, ambang Direksi, peran saya). */
export function EnforcementPills({ cfg = {}, actorRole }) {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5" data-testid="my-approvals-enforcement">
      <span className={`rounded-full px-2 py-0.5 text-[10.5px] font-bold ${MODE_TONE[cfg.mode] || MODE_TONE.off}`}>
        Penegakan: {cfg.mode_label || "—"}
      </span>
      <span className="rounded-full bg-[#EFF4FF] px-2 py-0.5 text-[10.5px] font-semibold text-[#0058CC]">
        Cakupan: {cfg.scope_label || "—"}
      </span>
      <span className="rounded-full bg-[#F3E9FA] px-2 py-0.5 text-[10.5px] font-semibold text-[#6B219A]">
        Pemisahan tugas: {cfg.sod ? "aktif" : "nonaktif"}
      </span>
      <span className="rounded-full bg-[#FEF3C7] px-2 py-0.5 text-[10.5px] font-semibold text-[#B45309]">
        PO Custom → Direksi ≥ {formatCurrency(cfg.po_custom_direksi_min || 0)}
      </span>
      <span className="rounded-full bg-[#EEF1F5] px-2 py-0.5 text-[10.5px] font-semibold text-[#4A4B52]">
        <Users2 size={10} className="mr-1 inline" />
        Anda: {actorRole || "—"}
      </span>
    </div>
  );
}

/** Jejak persetujuan (siapa memutus apa, termasuk percobaan yang ditolak sistem). */
export function ApprovalLogSection({ rows = [], onlyViolations, onToggleViolations }) {
  return (
    <section className="section-card">
      <div className="section-head flex-wrap gap-y-1.5">
        <div className="flex items-center gap-2">
          <ScrollText size={15} className="text-[#6B219A]" />
          <h2>Jejak Persetujuan</h2>
        </div>
        <label className="flex items-center gap-1.5 text-[11px] text-[#4A4B52]">
          <input type="checkbox" checked={onlyViolations}
            data-testid="my-approvals-log-violations"
            onChange={(e) => onToggleViolations(e.target.checked)} />
          hanya percobaan yang ditolak
        </label>
      </div>
      <div className="section-body">
        {rows.length === 0 ? (
          <p className="py-6 text-center text-[12px] text-[#9A9BA3]"
            data-testid="my-approvals-log-empty">Belum ada jejak keputusan.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-[12px]"
              data-testid="my-approvals-log">
              <thead>
                <tr className="text-[10px] uppercase text-[#8E8E93]">
                  <th className="py-1.5 pr-3 font-bold">Waktu (WIB)</th>
                  <th className="py-1.5 pr-3 font-bold">Tahap</th>
                  <th className="py-1.5 pr-3 font-bold">Dokumen</th>
                  <th className="py-1.5 pr-3 font-bold">Oleh</th>
                  <th className="py-1.5 font-bold">Hasil</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F4F5F7]">
                {rows.map((r) => (
                  <tr key={r.id} data-testid={`my-approvals-log-row-${r.id}`}>
                    <td className="py-2 pr-3 text-[11px] text-[#6B6B73]">{fmtWaktu(r.created_at)}</td>
                    <td className="py-2 pr-3 text-[11.5px] font-semibold text-[#1C1C1E]">
                      {r.stage_label}
                      <span className="ml-1 text-[10px] font-normal text-[#8E8E93]">
                        tingkat {r.level}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-[11.5px]">{r.doc_number || "—"}</td>
                    <td className="py-2 pr-3 text-[11.5px]">
                      {actorLabel(r.actor_name)}
                      {r.actor_role && <span className="ml-1 text-[11px] text-[#8E8E93]">({roleLabel(r.actor_role)})</span>}
                    </td>
                    <td className="py-2 text-[11.5px]">
                      <span className={`rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${
                        r.violation ? "bg-[#FDECEA] text-[#C0392B]" : "bg-[#E9F7EF] text-[#1B7F4B]"}`}>
                        {r.outcome || r.action}
                      </span>
                      {r.note && (
                        <div className="mt-0.5 max-w-[360px] text-[11px] text-[#8E8E93]">{noteLabel(r.note)}</div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
