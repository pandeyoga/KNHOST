/**
 * BankAccountChangesPanel (PM-T1) — "Perubahan menunggu persetujuan" di Rekening & Saldo.
 *
 * Perubahan rekening yang butuh orang kedua (`kontrol.ubah_rekening`) belum berlaku sampai diputus pemegang
 * `cash.approve` yang BUKAN pengajunya. Konfirmasi menyebut nama rekening, PT, dan nilai lama → baru (N5); Tolak
 * meminta alasan. Tidak ada yang menunggu → bagian ini tidak tampil (satu keadaan kosong saja di layar).
 * Sumber: `GET /api/bank-account-changes?status=menunggu` (berhalaman), `POST …/{id}/decision`.
 * Kas & Bank 3 (Tugas 4a) — bidang mentah berlabel: jenis kas ("Kas kasir"), dana tetap & saldo awal (Rp), lokasi (nama
 * lokasi kerja dari `GET /warehouse-sites`, dimuat hanya bila ada perubahan lokasi), jenis rekening ("Kas tunai").
 */
import React, { useCallback, useEffect, useState } from "react";
import { Check, Clock3, Plus, X } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyPost } from "../../utils/moneyRequest";
import { apiErrorText } from "../../utils/apiError";
import { askConfirm, askReason, REASON_MIN_LENGTH } from "../../services/confirmService";
import { formatCurrency, formatDate } from "../../utils/formatters";
import { usePaymentMethods } from "../../config/paymentMethods";
import { ACCOUNT_KIND_OPTIONS, purposeLabel } from "./BankAccountForm";
import { labelJenisKas } from "./jenisKas";

const PAGE_SIZE = 50;

const UANG = new Set(["dana_tetap", "opening_balance"]);
const kosong = (v) => v === null || v === undefined || v === "";

/** Kas & Bank 3 — nama lokasi kerja untuk perubahan `location_id`: `null` = belum dimuat (atau tidak perlu),
 *  `{ nama: {id: nama}, gagal }`. Dimuat sekali, hanya bila `perlu`. */
function useNamaLokasi(perlu) {
  const [lokasi, setLokasi] = useState(null);
  useEffect(() => {
    if (!perlu || lokasi) return undefined;
    let hidup = true;
    axios.get(`${API}/warehouse-sites`)
      .then((r) => { if (hidup) setLokasi({ nama: Object.fromEntries((r.data?.sites || []).map((x) => [x.id, x.name])), gagal: false }); })
      .catch(() => { if (hidup) setLokasi({ nama: {}, gagal: true }); });
    return () => { hidup = false; };
  }, [perlu, lokasi]);
  return lokasi;
}

export function useChangeValueText(lokasi = null) {
  const pm = usePaymentMethods("");
  return useCallback((field, v) => {
    if (UANG.has(field) && !kosong(v) && Number.isFinite(Number(v))) return formatCurrency(Number(v));
    if (kosong(v)) return "—";
    if (field === "cash_type") return labelJenisKas(v);
    if (field === "account_type") return ACCOUNT_KIND_OPTIONS.find((o) => o.value === v)?.label || String(v);
    if (field === "location_id") {
      if (!lokasi) return "memuat nama lokasi…";
      if (lokasi.nama[v]) return lokasi.nama[v];
      return lokasi.gagal ? "lokasi kerja (nama belum bisa dimuat)" : "lokasi tidak dikenal";
    }
    if (typeof v === "boolean") return v ? "Ya" : "Tidak";
    if (Array.isArray(v)) {
      if (!v.length) return "—";
      if (field === "purposes") return v.map(purposeLabel).join(", ");
      if (field === "payment_method_codes" || field === "default_receiving_methods") return v.map(pm.labelOf).join(", ");
      return v.join(", ");
    }
    return String(v);
  }, [pm, lokasi]);
}

function ChangeLines({ row, text }) {
  return (
    <ul className="grid gap-0.5" data-testid={`bank-change-lines-${row.id}`}>
      {(row.label_changes || row.changes || []).map((c) => (
        <li key={c.field} className="text-fs-13 text-kn-text">
          <span className="font-semibold">{c.label || c.field}</span>{": "}
          {row.action === "buat" ? text(c.field, c.to) : <>{text(c.field, c.from)} → <b>{text(c.field, c.to)}</b></>}
        </li>
      ))}
    </ul>
  );
}

export default function BankAccountChangesPanel({ entityParam = "", canApprove = false, reloadKey = 0, onDecided }) {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [err, setErr] = useState("");
  const [busyId, setBusyId] = useState("");
  const intent = useIntentKey("rekputus");
  const perluLokasi = rows.some((r) => (r.label_changes || r.changes || []).some((c) => c.field === "location_id"));
  const text = useChangeValueText(useNamaLokasi(perluLokasi));

  const load = useCallback(async () => {
    try {
      const params = { status: "menunggu", page: 1, page_size: PAGE_SIZE };
      if (entityParam && entityParam !== "all") params.entity_id = entityParam;
      const r = await axios.get(`${API}/bank-account-changes`, { params });
      setRows(r.data?.items || []);
      setTotal(Number(r.data?.total || 0));
      setErr("");
    } catch (e) {
      setRows([]);
      setTotal(0);
      setErr(apiErrorText(e, "Gagal memuat perubahan rekening yang menunggu persetujuan."));
    }
  }, [entityParam]);
  useEffect(() => { load(); }, [load, reloadKey]);

  const summary = (row) => (
    <>
      Rekening <strong>{row.account_name || "baru"}</strong> · <strong>{row.entity_name}</strong>
      <br />
      {(row.label_changes || row.changes || []).map((c) => (
        <React.Fragment key={c.field}>
          {c.label || c.field}: {row.action === "buat" ? text(c.field, c.to) : `${text(c.field, c.from)} → ${text(c.field, c.to)}`}
          <br />
        </React.Fragment>
      ))}
    </>
  );

  const decide = async (row, decision) => {
    let note = "";
    if (decision === "approve") {
      const ok = await askConfirm({
        title: row.action === "buat" ? "Setujui rekening baru?" : "Setujui perubahan rekening?",
        message: summary(row), confirmLabel: "Setujui", testId: "bank-change-approve-confirm" });
      if (!ok) return;
    } else {
      const alasan = await askReason({
        title: "Tolak perubahan rekening?", message: summary(row), confirmLabel: "Tolak", danger: true,
        reasonLabel: "Alasan penolakan", reasonRequired: true, reasonMinLength: REASON_MIN_LENGTH,
        testId: "bank-change-reject-confirm" });
      if (alasan === null || alasan === undefined) return;
      note = alasan;
    }
    setBusyId(row.id);
    try {
      const body = { decision, note };
      await intent.send(body, (key) => moneyPost(`${API}/bank-account-changes/${row.id}/decision`, body, key));
      await load();
      onDecided?.(decision === "approve" ? `Perubahan rekening ${row.account_name || ""} disetujui dan berlaku.`
        : `Perubahan rekening ${row.account_name || ""} ditolak.`);
    } catch (e) {
      setErr(apiErrorText(e, "Gagal memutus perubahan rekening."));
      await load();
    } finally {
      setBusyId("");
    }
  };

  if (!total && !err) return null;
  return (
    <div className="section-card mb-3" data-testid="bank-changes">
      <div className="section-head">
        <div className="flex items-center gap-2">
          <Clock3 size={16} className="text-kn-warning-text" aria-hidden="true" />
          <h2>Perubahan menunggu persetujuan</h2>
          <span className="status-pill bg-kn-warning-soft text-kn-warning-text" data-testid="bank-changes-count">
            <Clock3 size={12} aria-hidden="true" />{total} menunggu
          </span>
        </div>
      </div>
      <div className="section-body">
        <ErrorNotice message={err} onRetry={load} onDismiss={() => setErr("")} testId="bank-changes-error" />
        {!canApprove && total > 0 && (
          <p className="mb-2 text-fs-12 text-kn-text-2" data-testid="bank-changes-readonly">
            Perubahan ini berlaku setelah disetujui pemegang akses menyetujui perubahan rekening.
          </p>
        )}
        {rows.length > 0 && (
          <div className="overflow-x-auto">
            <table className="data-table head-wrap w-full" data-testid="bank-changes-table">
              <thead>
                <tr>
                  <th>Rekening</th>
                  <th>PT</th>
                  <th>Perubahan (lama → baru)</th>
                  <th>Diajukan</th>
                  {canApprove && <th className="col-sticky-end">Keputusan</th>}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} data-testid={`bank-change-row-${row.id}`}>
                    <td className="font-semibold">
                      {row.account_name || "—"}
                      {row.action === "buat" && (
                        <span className="ml-1 status-pill bg-kn-action-soft text-kn-action"><Plus size={12} aria-hidden="true" />Rekening baru</span>
                      )}
                    </td>
                    <td>{row.entity_name}</td>
                    <td>
                      <ChangeLines row={row} text={text} />
                      {row.reason && <p className="mt-0.5 text-fs-12 text-kn-text-2">Catatan: {row.reason}</p>}
                    </td>
                    <td className="whitespace-nowrap">{row.requested_by}<br /><span className="text-fs-12 text-kn-text-2">{formatDate(row.created_at)}</span></td>
                    {canApprove && (
                      <td className="col-sticky-end">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <button type="button" className="primary-button btn-sm" data-testid={`bank-change-approve-${row.id}`}
                            disabled={Boolean(row.blocked_reason) || busyId === row.id} onClick={() => decide(row, "approve")}>
                            <Check size={13} aria-hidden="true" />Setujui
                          </button>
                          <button type="button" className="danger-button btn-sm" data-testid={`bank-change-reject-${row.id}`}
                            disabled={Boolean(row.blocked_reason) || busyId === row.id} onClick={() => decide(row, "reject")}>
                            <X size={13} aria-hidden="true" />Tolak
                          </button>
                        </div>
                        {row.blocked_reason && (
                          <p className="mt-1 max-w-[220px] text-fs-12 text-kn-text-2" data-testid={`bank-change-blocked-${row.id}`}>
                            Anda yang mengajukan — rekan lain yang memutus.
                          </p>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {total > rows.length && (
          <p className="mt-2 text-fs-12 text-kn-text-2" data-testid="bank-changes-more">
            Menampilkan {rows.length} dari {total} perubahan (terbaru dulu). Putuskan yang tampil untuk melihat sisanya.
          </p>
        )}
      </div>
    </div>
  );
}
