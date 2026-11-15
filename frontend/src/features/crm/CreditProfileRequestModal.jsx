/**
 * CreditProfileRequestModal (CR-T1) — pop-up baku "Ajukan perubahan kredit" dari tab Kredit kartu pelanggan.
 *
 * Isian = baris profil yang tampil di tab (plafon, berlaku sampai, termin, tahan pesanan, status & alasan blokir) +
 * "Alasan pengajuan" (wajib, ≥ 5 huruf) + "Lampiran (tautan)". CR-T4 — bagian "Aturan denda": Ikut PT · Khusus (tarif,
 * dasar hitung, batas atas, hari tenggang; kosong = ikut PT) · Bebas denda (alasan + berlaku sampai, keduanya wajib).
 * Hanya isian yang BERUBAH dari nilai yang berlaku yang
 * dikirim (`POST /api/customers/{id}/credit-profile-requests`). Pemegang `credit_profile.approve` di PT yang aturannya
 * "cukup satu orang" melihat tombol kedua "Ajukan & setujui" (konfirmasi menyebut pelanggan, PT, plafon baru).
 * Galat server tampil di dalam pop-up (INV-UI-03); isian pengguna tidak dihapus.
 */
import { useEffect, useMemo, useState } from "react";
import { Loader2, ShieldCheck, Send } from "lucide-react";
import FormModal from "../../components/FormModal";
import FormSection from "../../components/FormSection";
import KNSelect from "../../components/KNSelect";
import KNDatePicker from "../../components/KNDatePicker";
import MoneyInput from "../../components/MoneyInput";
import { API } from "../../services/apiClient";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyPost } from "../../utils/moneyRequest";
import { apiErrorText } from "../../utils/apiError";
import { askConfirm } from "../../services/confirmService";
import { parseDecimal } from "../../utils/decimalInput";
import { formatCurrency } from "../../utils/formatters";
import { CREDIT_STATUS_OPTIONS, LIMIT_MODE_OPTIONS, confirmSummary } from "./creditProfileUi";
import {
  FIELD_WORD, PenaltyRuleFields, RULE_MODE_OPTIONS, formFromRule, normRule, numbersFromForm, ruleFromForm,
} from "../finance/payments/penaltyRuleUi";

const MIN_LETTERS = 5;   // K-14 — dihitung HURUF, sama dengan server (input_rules.count_letters)
const countLetters = (t) => (String(t || "").match(/\p{L}/gu) || []).length;
const todayWib = () => new Date(Date.now() + 7 * 3600 * 1000).toISOString().slice(0, 10);

/** Nilai awal isian = nilai yang BERLAKU (profil efektif server). */
export function baseOf(eff) {
  return {
    limit_mode: eff?.limit_mode || "ikut_pt",
    credit_limit: eff?.khusus_credit_limit ?? null,
    limit_valid_until: eff?.limit_valid_until || "",
    allowed_term_codes: [...(eff?.allowed_term_codes || [])],
    default_term_code: eff?.default_term_code || "",
    overdue_block_days: eff?.block_days_source === "bawaan_pt" ? null : (eff?.overdue_block_days ?? null),
    credit_status: eff?.credit_status || "normal",
    block_reason: eff?.block_reason || "",
    penalty_rule: normRule(eff?.penalty_rule),   // CR-T4 — null = ikut PT
  };
}

const same = (a, b) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);

export default function CreditProfileRequestModal({ open, data, canApprove, onClose, onSaved }) {
  const eff = useMemo(() => data?.effective || {}, [data]);
  const base = useMemo(() => baseOf(eff), [eff]);
  const [f, setF] = useState(base);
  const [limitText, setLimitText] = useState("");
  const [blockDaysText, setBlockDaysText] = useState("");
  const [reason, setReason] = useState("");
  const [attachment, setAttachment] = useState("");
  const [pen, setPen] = useState(() => formFromRule(eff.penalty_rule));   // CR-T4 — isian aturan denda (teks)
  const [tried, setTried] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const aju = useIntentKey("aju-kredit");
  const putus = useIntentKey("putus-kredit");

  useEffect(() => {
    if (!open) return;
    setF(base);
    setLimitText(base.credit_limit === null ? "" : String(base.credit_limit));
    setBlockDaysText(base.overdue_block_days === null ? "" : String(base.overdue_block_days));
    setReason(""); setAttachment(""); setTried(false); setError("");
    setPen(formFromRule(eff.penalty_rule));
  }, [open, base, eff]);

  const terms = data?.term_options || [];
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));
  const limitNum = limitText === "" ? null : parseDecimal(limitText);
  const blockDays = blockDaysText === "" ? null : Number(blockDaysText);
  const next = {
    ...f,
    credit_limit: f.limit_mode === "khusus" ? limitNum : base.credit_limit,
    limit_valid_until: f.limit_mode === "khusus" ? f.limit_valid_until : base.limit_valid_until,
    overdue_block_days: f.overdue_block_days === null ? null : blockDays,
    block_reason: f.credit_status === "blokir_manual" ? f.block_reason : "",
    penalty_rule: ruleFromForm(pen),
  };
  const changes = Object.fromEntries(Object.entries(next).filter(([k, v]) => !same(v, base[k])));
  const newLimit = "credit_limit" in changes ? Number(changes.credit_limit || 0) : null;
  const dc = data?.dual_control || {};
  const overCap = Number(dc.batas_nominal || 0) > 0 && newLimit !== null && newLimit > Number(dc.batas_nominal);
  const canSelf = canApprove && !dc.dua_orang && !overCap;

  const missing = [
    !Object.keys(changes).length && "ubah minimal satu isian",
    f.limit_mode === "khusus" && (limitNum === null || !Number.isFinite(limitNum) || limitNum < 0) && "plafon khusus",
    f.overdue_block_days !== null && (!Number.isInteger(blockDays) || blockDays < 0) && "jumlah hari tahan pesanan",
    f.credit_status === "blokir_manual" && countLetters(f.block_reason) < MIN_LETTERS && "alasan blokir",
    ...(pen.mode === "khusus" ? numbersFromForm(pen).bad.map((k) => FIELD_WORD[k]) : []),
    pen.mode === "bebas" && countLetters(pen.reason) < MIN_LETTERS && "alasan bebas denda",
    pen.mode === "bebas" && !pen.valid_until && "tanggal berakhir bebas denda",
    countLetters(reason) < MIN_LETTERS && "alasan pengajuan",
  ].filter(Boolean);

  async function submit(selfApprove) {
    setTried(true);
    setError("");
    if (missing.length) return;
    if (selfApprove) {
      const ok = await askConfirm({ title: "Ajukan dan setujui sendiri?",
        message: confirmSummary({ changes: Object.entries(changes).map(([field, to]) => ({ field, from: base[field], to })) },
          { customerName: data?.customer?.name, entityName: data?.entity?.short_name || data?.entity?.legal_name, terms }),
        confirmLabel: "Ajukan & setujui", testId: "credit-self-approve-confirm" });
      if (!ok) return;
    }
    setBusy(true);
    try {
      const body = { entity_id: data?.entity?.id, changes, reason: reason.trim(), attachment_url: attachment.trim() };
      const r = await aju.send(body, (k) => moneyPost(`${API}/customers/${data.customer.id}/credit-profile-requests`, body, k));
      if (!selfApprove) { onSaved?.("Pengajuan perubahan kredit dikirim dan menunggu keputusan."); return; }
      const dec = { decision: "approve", note: "Diajukan dan disetujui sendiri (aturan PT: cukup satu orang)." };
      try {
        await putus.send(dec, (k) => moneyPost(`${API}/credit-profile-requests/${r.data.id}/decision`, dec, k));
        onSaved?.("Perubahan kredit diajukan, disetujui, dan langsung berlaku.");
      } catch (e) {
        onSaved?.(`Pengajuan tersimpan, tetapi belum disetujui: ${apiErrorText(e, "coba setujui dari kartu Menunggu keputusan.")}`);
      }
    } catch (e) {
      setError(apiErrorText(e, "Pengajuan perubahan kredit belum tersimpan."));
    } finally {
      setBusy(false);
    }
  }

  if (!open) return null;
  const ptName = data?.entity?.short_name || data?.entity?.legal_name || "PT";
  const bawaanPt = Number(eff.default_credit_limit || 0);
  return (
    <FormModal open onClose={onClose} size="md" testId="credit-request-modal" busy={busy} error={error} icon={ShieldCheck}
      title="Ajukan perubahan kredit" subtitle={`${data?.customer?.name || ""} · ${ptName}`}
      footer={(
        <div className="flex flex-wrap items-center justify-end gap-2">
          {tried && missing.length > 0 && (
            <p className="w-full text-fs-12 font-semibold text-kn-danger-text" data-testid="credit-request-missing">Lengkapi: {missing.join(", ")}.</p>
          )}
          <button type="button" className="secondary-button" disabled={busy} onClick={() => !busy && onClose?.()}
            data-testid="credit-request-cancel">Batal</button>
          {canSelf && (
            <button type="button" className="secondary-button" disabled={busy} onClick={() => submit(true)}
              data-testid="credit-request-submit-approve"><ShieldCheck size={13} aria-hidden="true" />Ajukan &amp; setujui</button>
          )}
          <button type="button" className="primary-button" disabled={busy} onClick={() => submit(false)} data-testid="credit-request-submit">
            {busy ? <Loader2 size={13} className="animate-spin" aria-hidden="true" /> : <Send size={13} aria-hidden="true" />}
            {busy ? "Mengirim..." : "Ajukan perubahan"}
          </button>
        </div>
      )}>
      <FormSection number={1} title="Plafon kredit" testId="credit-request-section-limit">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Jenis plafon">
            <KNSelect value={f.limit_mode} onValueChange={(v) => set("limit_mode", v)} className="field"
              data-testid="credit-request-limit-mode" options={LIMIT_MODE_OPTIONS} />
            <p className="mt-0.5 text-fs-12 text-kn-text-2">
              Plafon bawaan {ptName}: {bawaanPt > 0 ? formatCurrency(bawaanPt) : "tanpa batas"}.
            </p>
          </Field>
          {f.limit_mode === "khusus" && (
            <>
              <Field label="Plafon kredit (Rp)" req>
                <MoneyInput testId="credit-request-limit" value={limitText} onChange={(v) => setLimitText(v)} className="field" placeholder="Rp 0" />
              </Field>
              <Field label="Berlaku sampai" optional hint="Kosong = tanpa batas waktu. Lewat tanggal ini plafon kembali ke bawaan PT.">
                <KNDatePicker data-testid="credit-request-valid-until" value={f.limit_valid_until} min={todayWib()}
                  onChange={(v) => set("limit_valid_until", v || "")} />
              </Field>
            </>
          )}
        </div>
      </FormSection>

      <FormSection number={2} title="Termin pembayaran" testId="credit-request-section-terms"
        subtitle="Termin di luar daftar ditolak saat pesanan dibuat. Termin bawaan belum dipakai saat pesanan dibuat.">
        <div className="grid gap-2">
          <p className="text-fs-12 text-kn-text-2">Tidak ada yang dicentang = semua termin aktif PT boleh.</p>
          <div className="flex flex-wrap gap-x-3 gap-y-2">
            {terms.map((t) => (
              <label key={t.code} className="flex items-center gap-1.5 text-fs-13 cursor-pointer" data-testid={`credit-request-term-${t.code}`}>
                <input type="checkbox" checked={f.allowed_term_codes.includes(t.code)}
                  onChange={() => set("allowed_term_codes", f.allowed_term_codes.includes(t.code)
                    ? f.allowed_term_codes.filter((c) => c !== t.code) : [...f.allowed_term_codes, t.code])} />
                {t.name}
              </label>
            ))}
            {terms.length === 0 && <span className="text-fs-12 text-kn-text-2">PT ini belum punya syarat pembayaran aktif.</span>}
          </div>
          <Field label="Termin bawaan" optional>
            <KNSelect value={f.default_term_code} onValueChange={(v) => set("default_term_code", v)} className="field"
              data-testid="credit-request-default-term"
              options={[{ value: "", label: "— Tidak ada —" },
                ...terms.filter((t) => !f.allowed_term_codes.length || f.allowed_term_codes.includes(t.code))
                  .map((t) => ({ value: t.code, label: t.name }))]} />
          </Field>
        </div>
      </FormSection>

      <FormSection number={3} title="Tahan pesanan & status" testId="credit-request-section-block">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Tahan pesanan bila telat lebih dari">
            <label className="flex items-center gap-1.5 text-fs-13 cursor-pointer" data-testid="credit-request-block-follow">
              <input type="checkbox" checked={f.overdue_block_days === null}
                onChange={(e) => {
                  set("overdue_block_days", e.target.checked ? null : (eff.default_overdue_block_days ?? 0));
                  if (!e.target.checked) setBlockDaysText(String(eff.default_overdue_block_days ?? 0));
                }} />
              Ikut PT ({eff.default_overdue_block_days ?? 0} hari)
            </label>
            {f.overdue_block_days !== null && (
              <input type="number" min={0} step={1} className="field mt-1" data-testid="credit-request-block-days"
                value={blockDaysText} onChange={(e) => setBlockDaysText(e.target.value)} placeholder="hari" />
            )}
          </Field>
          <Field label="Status kredit">
            <KNSelect value={f.credit_status} onValueChange={(v) => set("credit_status", v)} className="field"
              data-testid="credit-request-status" options={CREDIT_STATUS_OPTIONS} />
          </Field>
          {f.credit_status === "blokir_manual" && (
            <div className="sm:col-span-2">
              <Field label="Alasan blokir" req hint={`Minimal ${MIN_LETTERS} huruf — tampil di kartu pelanggan dan pemeriksaan kredit pesanan.`}>
                <input className="field" data-testid="credit-request-block-reason" value={f.block_reason}
                  onChange={(e) => set("block_reason", e.target.value)} placeholder="mis. tunggakan lama belum diselesaikan" />
              </Field>
            </div>
          )}
        </div>
      </FormSection>

      <FormSection number={4} title="Aturan denda" testId="credit-request-section-penalty"
        subtitle="Dipakai usulan denda keterlambatan pelanggan ini di PT ini. Rencana bayar satu pesanan bisa menimpanya.">
        <div className="grid gap-3">
          <Field label="Aturan denda">
            <KNSelect value={pen.mode} onValueChange={(v) => setPen((s) => ({ ...s, mode: v }))} className="field"
              data-testid="credit-request-penalty-mode" options={RULE_MODE_OPTIONS} />
          </Field>
          {pen.mode === "khusus" && (
            <PenaltyRuleFields value={pen} testPrefix="credit-request-penalty" hint="Kosong = ikut aturan PT."
              bad={tried ? numbersFromForm(pen).bad : []} onChange={(k, v) => setPen((s) => ({ ...s, [k]: v }))} />
          )}
          {pen.mode === "bebas" && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Alasan" req hint={`Minimal ${MIN_LETTERS} huruf — tampil di kartu pelanggan.`}>
                <input className="field" data-testid="credit-request-penalty-reason" value={pen.reason}
                  onChange={(e) => setPen((s) => ({ ...s, reason: e.target.value }))} placeholder="mis. kesepakatan direksi" />
              </Field>
              <Field label="Berlaku sampai" req hint="Sesudah tanggal ini denda kembali ikut aturan PT.">
                <KNDatePicker data-testid="credit-request-penalty-until" value={pen.valid_until} min={todayWib()}
                  onChange={(v) => setPen((s) => ({ ...s, valid_until: v || "" }))} />
              </Field>
            </div>
          )}
        </div>
      </FormSection>

      <FormSection number={5} title="Dasar pengajuan" testId="credit-request-section-reason" required>
        <div className="grid gap-3">
          <Field label="Alasan pengajuan" req hint={`Minimal ${MIN_LETTERS} huruf — dibaca pemutus dan tercatat di riwayat.`}>
            <textarea className="field" rows={2} data-testid="credit-request-reason" value={reason}
              onChange={(e) => setReason(e.target.value)} placeholder="mis. naik kelas grosir, pembayaran lancar 6 bulan" />
          </Field>
          <Field label="Lampiran (tautan)" optional>
            <input className="field" data-testid="credit-request-attachment" value={attachment}
              onChange={(e) => setAttachment(e.target.value)} placeholder="https://…" />
          </Field>
        </div>
      </FormSection>
    </FormModal>
  );
}

function Field({ label, req = false, optional = false, hint, children }) {
  return (
    <div>
      <label className="mb-1 block text-fs-12 font-semibold text-kn-text">{label}{req && <span className="text-kn-danger-text"> *</span>}
        {optional && !req && <span className="font-normal text-kn-text-2"> (opsional)</span>}</label>
      {children}
      {hint && <p className="mt-0.5 text-fs-12 text-kn-text-2">{hint}</p>}
    </div>
  );
}
