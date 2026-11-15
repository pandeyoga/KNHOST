/**
 * creditProfileUi (CR-T1) — potongan bersama tab Kredit kartu pelanggan (`CustomerCreditTab`) dan antrean pengajuan
 * (`CreditProfileRequestsPanel`): label & nilai isian profil kredit, lencana asal nilai (L6: "ikut PT" / "khusus"),
 * daftar perubahan lama → baru, dan aksi putus/batal (konfirmasi menyebut pelanggan, PT, plafon baru — N5; kunci
 * idempotensi — N4). Teks untuk manusia saja: id teknis & nama isian tidak pernah tampil (L1).
 */
import { useCallback, useState } from "react";
import { Building2, Check, CircleSlash, Clock3, History, UserCog, X } from "lucide-react";
import { API } from "../../services/apiClient";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyPost } from "../../utils/moneyRequest";
import { apiErrorText } from "../../utils/apiError";
import { askConfirm, askReason, REASON_MIN_LENGTH } from "../../services/confirmService";
import { formatCurrency, formatDate } from "../../utils/formatters";
import { docStatusLabel } from "../../utils/docStatus";
import { ruleText } from "../finance/payments/penaltyRuleUi";

export const FIELD_LABEL = {
  limit_mode: "Jenis plafon", credit_limit: "Plafon kredit", limit_valid_until: "Berlaku sampai",
  allowed_term_codes: "Termin yang diizinkan", default_term_code: "Termin bawaan",
  overdue_block_days: "Tahan pesanan bila telat lebih dari", credit_status: "Status kredit",
  block_reason: "Alasan blokir", penalty_rule: "Aturan denda", credit_group_id: "Kelompok kredit",
};
export const LIMIT_MODE_OPTIONS = [
  { value: "ikut_pt", label: "Ikut plafon bawaan PT" },
  { value: "khusus", label: "Plafon khusus pelanggan ini" },
  { value: "tanpa_batas", label: "Tanpa batas" },
];
export const CREDIT_STATUS_OPTIONS = [
  { value: "normal", label: "Normal" },
  { value: "blokir_manual", label: "Diblokir manual" },
];

const termName = (code, terms) => (terms || []).find((t) => t.code === code)?.name || code;

/** Nilai isian profil kredit sebagai teks untuk manusia. */
export function valueText(field, v, terms = []) {
  if (field === "limit_mode") return (LIMIT_MODE_OPTIONS.find((o) => o.value === v) || {}).label || (v ? String(v) : "Ikut plafon bawaan PT");
  if (field === "credit_limit") return v === null || v === undefined || v === "" ? "—" : formatCurrency(Number(v));
  if (field === "limit_valid_until") return v ? formatDate(v) : "Tanpa batas waktu";
  if (field === "allowed_term_codes") return Array.isArray(v) && v.length ? v.map((c) => termName(c, terms)).join(", ") : "Semua termin aktif PT";
  if (field === "default_term_code") return v ? termName(v, terms) : "—";
  if (field === "overdue_block_days") return v === null || v === undefined ? "Ikut PT" : `${v} hari`;
  if (field === "credit_status") return (CREDIT_STATUS_OPTIONS.find((o) => o.value === v) || {}).label || (v ? String(v) : "Normal");
  if (field === "penalty_rule") return ruleText(v);   // CR-T4 — "Khusus: tarif 1 % per bulan" / "Bebas denda s.d. …"
  if (v === null || v === undefined || v === "") return "—";
  return String(v);
}

const SOURCE = {
  khusus: { label: "khusus", Icon: UserCog, cls: "bg-kn-action-soft text-kn-action" },
  tanpa_batas: { label: "khusus", Icon: UserCog, cls: "bg-kn-action-soft text-kn-action" },
  bawaan_pt: { label: "ikut PT", Icon: Building2, cls: "bg-kn-neutral-soft text-kn-neutral" },
  kedaluwarsa: { label: "ikut PT", Icon: Building2, cls: "bg-kn-neutral-soft text-kn-neutral" },
  data_lama: { label: "data lama", Icon: History, cls: "bg-kn-warning-soft text-kn-warning-text" },
};

/** Lencana asal nilai yang dipakai mesin (ikon + teks + warna). */
export function SourcePill({ source, testId }) {
  const s = SOURCE[source] || SOURCE.bawaan_pt;
  const { Icon } = s;
  return (
    <span className={`status-pill ${s.cls}`} data-testid={testId} data-source={source}>
      <Icon size={12} aria-hidden="true" />{s.label}
    </span>
  );
}

const REQ_STATUS = {
  diajukan: { label: "Menunggu keputusan", Icon: Clock3, cls: "bg-kn-warning-soft text-kn-warning-text" },
  disetujui: { label: "Disetujui", Icon: Check, cls: "bg-kn-success-soft text-kn-success-text" },
  ditolak: { label: "Ditolak", Icon: X, cls: "bg-kn-danger-soft text-kn-danger-text" },
  dibatalkan: { label: "Dibatalkan", Icon: CircleSlash, cls: "bg-kn-neutral-soft text-kn-neutral" },
};

const REQ_LABEL = Object.fromEntries(Object.entries(REQ_STATUS).map(([k, v]) => [k, v.label]));

export function RequestStatusPill({ status, testId }) {
  const s = REQ_STATUS[status] || REQ_STATUS.diajukan;
  const { Icon } = s;
  return (
    <span className={`status-pill ${s.cls}`} data-testid={testId}>
      <Icon size={12} aria-hidden="true" />{docStatusLabel(status, REQ_LABEL)}
    </span>
  );
}

/** Daftar perubahan "Isian: lama → baru". */
export function ChangeLines({ req, terms = [], testId }) {
  return (
    <ul className="grid gap-0.5" data-testid={testId}>
      {(req?.changes || []).map((c) => (
        <li key={c.field} className="text-fs-13 text-kn-text">
          <span className="font-semibold">{FIELD_LABEL[c.field] || c.label || "Isian"}</span>{": "}
          {valueText(c.field, c.from, terms)} → <b>{valueText(c.field, c.to, terms)}</b>
        </li>
      ))}
    </ul>
  );
}

/** Plafon baru dari pengajuan (untuk konfirmasi), atau null bila plafon tidak diubah. */
export function newLimitOf(req) {
  const c = (req?.changes || []).find((x) => x.field === "credit_limit");
  return c ? Number(c.to || 0) : null;
}

export function confirmSummary(req, { customerName, entityName, terms }) {
  const limit = newLimitOf(req);
  return (
    <>
      Pelanggan <strong>{customerName || req?.customer_name}</strong> · <strong>{entityName || "PT"}</strong>
      <br />
      {limit === null ? "Plafon tidak berubah." : <>Plafon baru: <strong>{formatCurrency(limit)}</strong></>}
      <br />
      {(req?.changes || []).filter((c) => c.field !== "credit_limit").map((c) => (
        <span key={c.field}>{FIELD_LABEL[c.field] || "Isian"}: {valueText(c.field, c.from, terms)} → {valueText(c.field, c.to, terms)}<br /></span>
      ))}
    </>
  );
}

/**
 * Aksi Setujui / Tolak / Batalkan satu pengajuan. `onDone(pesan)` sesudah berhasil; galat dikembalikan lewat `onError`.
 */
export function useCreditRequestActions({ onDone, onError }) {
  const intent = useIntentKey("kredit");
  const [busyId, setBusyId] = useState("");
  const run = useCallback(async (req, body, path, okText) => {
    setBusyId(req.id);
    try {
      await intent.send(body, (key) => moneyPost(`${API}/credit-profile-requests/${req.id}/${path}`, body, key));
      onDone?.(okText);
    } catch (e) {
      onError?.(apiErrorText(e, "Pengajuan perubahan kredit belum diproses."));
    } finally {
      setBusyId("");
    }
  }, [intent, onDone, onError]);

  const approve = useCallback(async (req, ctx) => {
    const ok = await askConfirm({ title: "Setujui perubahan kredit?", message: confirmSummary(req, ctx),
      confirmLabel: "Setujui", testId: "credit-request-approve-confirm" });
    if (ok) await run(req, { decision: "approve", note: "" }, "decision", `Perubahan kredit ${req.customer_name || ""} disetujui dan berlaku.`);
  }, [run]);
  const reject = useCallback(async (req, ctx) => {
    const note = await askReason({ title: "Tolak perubahan kredit?", message: confirmSummary(req, ctx), confirmLabel: "Tolak",
      danger: true, reasonLabel: "Alasan penolakan", reasonMinLength: REASON_MIN_LENGTH, testId: "credit-request-reject-confirm" });
    if (note !== null && note !== undefined) await run(req, { decision: "reject", note }, "decision", `Pengajuan kredit ${req.customer_name || ""} ditolak.`);
  }, [run]);
  const cancel = useCallback(async (req, ctx) => {
    const reason = await askReason({ title: "Batalkan pengajuan perubahan kredit?", message: confirmSummary(req, ctx),
      confirmLabel: "Batalkan pengajuan", danger: true, reasonLabel: "Alasan pembatalan", reasonMinLength: REASON_MIN_LENGTH,
      testId: "credit-request-cancel-confirm" });
    if (reason !== null && reason !== undefined) await run(req, { reason }, "cancel", "Pengajuan perubahan kredit dibatalkan.");
  }, [run]);
  return { approve, reject, cancel, busyId };
}
