import { useEffect, useState } from "react";
import { AlertTriangle, Lock } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import axios, { API } from "../../services/apiClient";
import { usePaymentMethods } from "../../config/paymentMethods";

/** Teks satu rekening penerima: "{bank} {nomor} a.n. {atas nama}" (sama dengan instruksi bayar di dokumen). */
export const accountText = (a) => {
  if (!a) return "";
  const head = [a.bank_name, a.account_number].map((x) => String(x || "").trim()).filter(Boolean).join(" ");
  const holder = String(a.holder_name || "").trim();
  if (head && holder) return `${head} a.n. ${holder}`;
  return head || holder || String(a.name || "");
};

export const PESAN_REKENING_KOSONG =
  "Belum ada rekening penerimaan untuk cara bayar ini — minta Finance mengaturnya di Kas & Bank.";

/**
 * PM-T2 — "Cara bayar" + "Rekening tujuan" di checkout (desktop & keranjang HP memakai `CheckoutDrawer` yang sama).
 * Cara bayar dari daftar induk PM-T1 (`usePaymentMethods("masuk", PT)`); rekening dari `GET /api/bank-accounts/receiving`
 * PT pesanan (rekening PT lain tidak pernah muncul). Rekening terisi otomatis dari bawaan, terkunci bila hanya satu, dan
 * tersembunyi bila cara bayar tidak butuh rekening bank. `required` = pengaturan PT mewajibkan cara bayar.
 */
export default function CheckoutPaymentDestination({ entityId = "", value, onChange, required = false }) {
  const method = value?.method || "";
  const account = value?.account || "";
  const pm = usePaymentMethods("masuk", entityId);
  const row = pm.methods.find((m) => m.code === method) || null;
  const needsBank = row?.needs_account === "bank";
  const [accounts, setAccounts] = useState({ key: "", rows: [], loading: false, failed: false });
  const key = `${entityId}|${method}`;

  useEffect(() => {
    if (!needsBank) { setAccounts({ key, rows: [], loading: false, failed: false }); return undefined; }
    let alive = true;
    setAccounts({ key, rows: [], loading: true, failed: false });
    const params = { method };
    if (entityId && entityId !== "all") params.entity_id = entityId;
    axios.get(`${API}/bank-accounts/receiving`, { params })
      .then((r) => { if (alive) setAccounts({ key, rows: Array.isArray(r.data) ? r.data : [], loading: false, failed: false }); })
      .catch(() => { if (alive) setAccounts({ key, rows: [], loading: false, failed: true }); });
    return () => { alive = false; };
  }, [key, needsBank]); // eslint-disable-line react-hooks/exhaustive-deps

  // Bawaan: rekening yang dipilih tidak ada di daftar PT/cara bayar ini → rekening bawaan (atau satu-satunya).
  const rows = accounts.key === key ? accounts.rows : [];
  useEffect(() => {
    if (!needsBank) { if (account) onChange({ method, account: "" }); return; }
    if (accounts.key !== key || accounts.loading) return;
    if (rows.some((a) => a.id === account)) return;
    const pick = rows.find((a) => a.is_default) || (rows.length === 1 ? rows[0] : null);
    const next = pick ? pick.id : "";
    if (next !== account) onChange({ method, account: next });
  }, [accounts, needsBank]); // eslint-disable-line react-hooks/exhaustive-deps

  const methodOptions = [...(required ? [] : [{ value: "", label: "Belum ditentukan" }]), ...pm.options];
  const locked = rows.length === 1;

  return (
    <div className="grid gap-2" data-testid="checkout-payment-destination">
      <div>
        <span className="field-label">Cara bayar{required ? " *" : ""}</span>
        <KNSelect data-testid="payment-method-select" className="field" value={method}
          placeholder="Pilih cara bayar" options={methodOptions}
          onValueChange={(v) => onChange({ method: v, account: "" })} />
        {required && !method && (
          <p data-testid="payment-method-required" className="mt-1 text-fs-12 text-kn-warning-text">
            PT ini mewajibkan cara bayar dipilih sebelum pesanan dibuat.
          </p>
        )}
      </div>
      {needsBank && (
        <div data-testid="receiving-account-field">
          <span className="field-label">Rekening tujuan</span>
          {accounts.loading || accounts.key !== key ? (
            <p className="text-fs-12 text-kn-text-2" data-testid="receiving-account-loading">Memuat rekening…</p>
          ) : accounts.failed ? (
            <p className="flex items-start gap-1.5 text-fs-12 text-kn-warning-text" data-testid="receiving-account-failed">
              <AlertTriangle size={13} className="mt-0.5 shrink-0" />
              Daftar rekening gagal dimuat. Pesanan tetap bisa dibuat — rekening bawaan PT diisi otomatis.
            </p>
          ) : rows.length === 0 ? (
            <p className="flex items-start gap-1.5 text-fs-12 text-kn-warning-text" data-testid="receiving-account-empty">
              <AlertTriangle size={13} className="mt-0.5 shrink-0" /> {PESAN_REKENING_KOSONG}
            </p>
          ) : (
            <>
              <KNSelect data-testid="receiving-account-select" className="field" value={account} disabled={locked}
                placeholder="Pilih rekening tujuan" onValueChange={(v) => onChange({ method, account: v })}
                options={rows.map((a) => ({ value: a.id, label: accountText(a) }))} />
              {locked && (
                <p className="mt-1 flex items-center gap-1 text-fs-12 text-kn-text-2" data-testid="receiving-account-locked">
                  <Lock size={12} /> Satu-satunya rekening penerimaan PT ini untuk cara bayar ini.
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
