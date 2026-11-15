/**
 * CashHoldingsView — PM-T4 (PM-06, K-36) · Keuangan › Kas & Bank › Titipan Sales.
 *
 * Tunai yang diterima sales di lapangan (bila PT memilih `pembayaran.sales_terima_tunai = titipan`) tercatat sebagai
 * titipan di tangan sales sampai setorannya diterima di sini. Dua bagian:
 *   · "Setoran menunggu diterima" — GET /api/cash-deposits (bawaan `diajukan`); tombol **Terima setoran** (pop-up
 *     "Masuk ke rekening" + konfirmasi yang menyebut nominal, PT, rekening, dan penyetor — `02` N5) dan **Tolak**
 *     (alasan wajib). POST /api/cash-deposits/{id}/receive | /reject (`cash_holding.approve`), kunci idempotensi `02` N4.
 *   · "Titipan belum disetor" — GET /api/cash-holdings (ringkasan `holders` per orang + rincian berhalaman), saringan
 *     "Lewat tenggat" dan kotak cari.
 * Mode "Semua PT": tombol mati dengan alasan tertulis di sampingnya. Memuat / galat / kosong dibedakan (`02` L4).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { HandCoins, RefreshCw, Users, X } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import EntityScopeBanner from "../../../components/EntityScopeBanner";
import ErrorNotice from "../../../components/ErrorNotice";
import FormModal from "../../../components/FormModal";
import KNPager from "../../../components/KNPager";
import { SearchBox } from "../../../components/ListControls";
import CashAccountField, { cashAccountBlocked, cashAccountBlockReason, cashAccountLabel } from "../../../components/CashAccountField";
import { askConfirm, askReason } from "../../../services/confirmService";
import { apiErrorText } from "../../../utils/apiError";
import { formatCurrency, formatDate } from "../../../utils/formatters";
import { entityShortById } from "../../../utils/entityLabel";
import { moneyPost } from "../../../utils/moneyRequest";
import useIntentKey from "../../../hooks/useIntentKey";
import { canCurrent } from "../../../config/roles";
import { useEntityScope } from "../../../context/EntityScopeContext";
import {
  OVERDUE_LOOK, TEKS_SEMUA_PT, TEKS_SETORAN_SENDIRI, TEKS_TANPA_IZIN_TERIMA, ageText, cashHoldingStatus,
} from "./cashHoldingShared";

const PAGE_SIZE = 20;

function StatusPill({ status, testId }) {
  const st = cashHoldingStatus(status);
  const Icon = st.icon;
  return (
    <span className={`status-pill whitespace-nowrap ${st.cls}`} data-testid={testId}>
      <Icon size={12} aria-hidden="true" />{st.label}
    </span>
  );
}

function OverduePill({ testId }) {
  const Icon = OVERDUE_LOOK.icon;
  return (
    <span className={`status-pill whitespace-nowrap ${OVERDUE_LOOK.cls}`} data-testid={testId}>
      <Icon size={12} aria-hidden="true" />{OVERDUE_LOOK.label}
    </span>
  );
}

/** Alasan tombol Terima/Tolak mati (ditulis, bukan tooltip); "" = boleh. */
export function alasanTidakBisaTerima({ canWrite, canApprove }) {
  if (!canWrite) return TEKS_SEMUA_PT;
  if (!canApprove) return TEKS_TANPA_IZIN_TERIMA;
  return "";
}

export default function CashHoldingsView({ currentUser = null }) {
  const { canWrite, selectedEntity, entities } = useEntityScope();
  const canApprove = canCurrent("cash_holding", "approve");
  const myId = currentUser?.id || "";
  const pt = entityShortById(entities, selectedEntity, "PT ini");
  const params = useMemo(() => (selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {}),
    [selectedEntity]);

  // ── Setoran menunggu diterima ──
  const [deps, setDeps] = useState({ items: [], total: 0, amount_total: 0 });
  const [depState, setDepState] = useState("loading");
  const [depErr, setDepErr] = useState("");
  const [depPage, setDepPage] = useState(1);
  const loadDeps = useCallback(async () => {
    setDepState("loading");
    try {
      const r = await axios.get(`${API}/cash-deposits`, { params: { ...params, status: "diajukan", page: depPage,
        page_size: PAGE_SIZE } });
      setDeps(r.data || { items: [], total: 0 }); setDepErr(""); setDepState("ready");
    } catch (e) { setDepErr(apiErrorText(e) || ""); setDepState("error"); }
  }, [params, depPage]);

  // ── Titipan belum disetor ──
  const [hold, setHold] = useState({ items: [], total: 0, holders: [] });
  const [holdState, setHoldState] = useState("loading");
  const [holdErr, setHoldErr] = useState("");
  const [holdPage, setHoldPage] = useState(1);
  const [overdue, setOverdue] = useState(false);
  const [search, setSearch] = useState("");
  const [holder, setHolder] = useState(null);   // {holder_user_id, holder_name} — rincian satu orang
  const loadHold = useCallback(async () => {
    setHoldState("loading");
    try {
      const r = await axios.get(`${API}/cash-holdings`, { params: {
        ...params, page: holdPage, page_size: PAGE_SIZE, ...(overdue ? { overdue: "true" } : {}),
        ...(search.trim() ? { q: search.trim() } : {}), ...(holder ? { holder_user_id: holder.holder_user_id } : {}) } });
      setHold(r.data || { items: [], total: 0, holders: [] }); setHoldErr(""); setHoldState("ready");
    } catch (e) { setHoldErr(apiErrorText(e) || ""); setHoldState("error"); }
  }, [params, holdPage, overdue, search, holder]);

  useEffect(() => { loadDeps(); }, [loadDeps]);
  useEffect(() => { loadHold(); }, [loadHold]);
  useEffect(() => { setDepPage(1); setHoldPage(1); setHolder(null); }, [selectedEntity]);
  const muatUlang = () => { loadDeps(); loadHold(); };

  // ── Terima / tolak ──
  const [target, setTarget] = useState(null);
  const [acc, setAcc] = useState("");
  const [accState, setAccState] = useState("");
  const [accRow, setAccRow] = useState(null);
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState("");
  const [msg, setMsg] = useState("");
  const [actErr, setActErr] = useState("");
  const intent = useIntentKey("setoran");
  const alasan = alasanTidakBisaTerima({ canWrite, canApprove });

  const bukaTerima = (d) => { setTarget(d); setAcc(""); setAccRow(null); setFormErr(""); };
  const terima = async () => {
    if (!target) return;
    const nominal = formatCurrency(target.amount);
    const rek = accRow ? cashAccountLabel(accRow) : "rekening terpilih";
    const ok = await askConfirm({
      title: `Terima setoran ${nominal}?`,
      message: `Setoran ${target.number} dari ${target.holder_name || "penyetor"} untuk ${pt}, masuk ke ${rek}. `
        + "Kas masuk dan jurnalnya dibuat; titipan penyetor berkurang.",
      confirmLabel: "Ya, terima setoran",
      testId: "cth-receive-confirm",
    });
    if (!ok) return;
    setBusy(true); setFormErr("");
    try {
      const body = { account_id: acc };
      const r = await intent.send({ id: target.id, ...body },
        (k) => moneyPost(`${API}/cash-deposits/${target.id}/receive`, body, k));
      const d = r.data || {};
      setTarget(null);
      setMsg(d.gl_status === "failed"
        ? `Setoran ${d.number || ""} diterima, tetapi jurnal kasnya gagal — ulangi dari Posting Gagal.`
        : `Setoran ${d.number || ""} (${nominal}) diterima ke ${rek}.`);
      muatUlang();
    } catch (e) {
      setFormErr(apiErrorText(e, "Setoran gagal diterima."));
    } finally { setBusy(false); }
  };
  const tolak = async (d) => {
    const reason = await askReason({
      title: `Tolak setoran ${d.number}?`,
      message: `Setoran ${formatCurrency(d.amount)} dari ${d.holder_name || "penyetor"} (${pt}) ditolak. Titipannya tetap `
        + "tercatat di tangan penyetor.",
      reasonLabel: "Alasan penolakan",
      reasonPlaceholder: "Contoh: uang belum diserahkan / nominal tidak sama",
      confirmLabel: "Tolak setoran",
      danger: true,
      testId: "cth-reject-confirm",
    });
    if (reason === null) return;
    setActErr("");
    try {
      const body = { reason };
      await intent.send({ id: d.id, ...body }, (k) => moneyPost(`${API}/cash-deposits/${d.id}/reject`, body, k));
      setMsg(`Setoran ${d.number} ditolak.`);
      muatUlang();
    } catch (e) { setActErr(apiErrorText(e, "Setoran gagal ditolak.")); }
  };

  const depRows = deps.items || [];
  const holders = hold.holders || [];
  const holdRows = hold.items || [];

  return (
    <div className="space-y-4" data-testid="cth-view">
      <EntityScopeBanner testId="cth-scope" />
      {msg && (
        <div className="notice-bar success" data-testid="cth-msg">
          <span className="text-fs-12">{msg}</span>
          <button type="button" className="icon-button" aria-label="Tutup" onClick={() => setMsg("")}>×</button>
        </div>
      )}
      <ErrorNotice message={actErr} onDismiss={() => setActErr("")} testId="cth-action-error" />

      {/* ── Setoran menunggu diterima ── */}
      <div className="section-card" data-testid="cth-deposits">
        <div className="section-head">
          <h2 className="flex items-center gap-2"><HandCoins size={16} className="text-kn-action" aria-hidden="true" />Setoran menunggu diterima</h2>
          <button type="button" data-testid="cth-refresh" onClick={muatUlang} className="secondary-button btn-sm ml-auto whitespace-nowrap">
            <RefreshCw size={13} aria-hidden="true" /> Muat ulang</button>
        </div>
        <div className="section-body space-y-2">
          <p className="text-fs-12 text-kn-text-2">
            Tunai yang diterima sales dan diserahkan ke kasir. Terima setoran sesudah uangnya dihitung: kas masuk ke rekening
            yang dipilih dan titipan penyetor berkurang.
          </p>
          {alasan && <p className="text-fs-12 text-kn-text-2" data-testid="cth-receive-why">{alasan}</p>}
          {depState === "loading" ? (
            <p className="py-4 text-center text-fs-12 text-kn-text-2" role="status" data-testid="cth-deposits-loading">Memuat setoran…</p>
          ) : depState === "error" ? (
            <ErrorNotice message={`Setoran tidak bisa dimuat. ${depErr}`.trim()} onRetry={loadDeps} testId="cth-deposits-error" />
          ) : depRows.length === 0 ? (
            <p className="py-6 text-center text-fs-12 text-kn-text-2" data-testid="cth-deposits-empty">Tidak ada setoran yang menunggu diterima.</p>
          ) : (
            <>
              <div className="table-wrap">
                <table className="data-table head-wrap" data-testid="cth-deposits-table">
                  <thead><tr>
                    <th>No. setoran</th><th>Penyetor</th><th className="text-right">Jumlah</th><th>Umur</th><th>Catatan</th>
                    <th className="col-sticky-end text-right">Aksi</th>
                  </tr></thead>
                  <tbody>
                    {depRows.map((d) => {
                      const sendiri = Boolean(myId) && d.holder_user_id === myId;
                      const mati = Boolean(alasan) || sendiri;
                      return (
                        <tr key={d.id} data-testid={`cth-deposit-row-${d.id}`}>
                          <td className="font-mono whitespace-nowrap">{d.number}</td>
                          <td className="whitespace-nowrap">{d.holder_name || "—"}</td>
                          <td className="text-right tabular-nums whitespace-nowrap">{formatCurrency(d.amount)}</td>
                          <td className="whitespace-nowrap">{ageText(d.created_at)}</td>
                          <td className="max-w-[220px] break-words text-fs-12 text-kn-text-2">{d.note || "—"}</td>
                          <td className="col-sticky-end text-right">
                            <div className="flex flex-wrap items-center justify-end gap-1.5">
                              {sendiri && <span className="text-fs-12 text-kn-text-2" data-testid={`cth-deposit-own-${d.id}`}>{TEKS_SETORAN_SENDIRI}</span>}
                              <button type="button" className="primary-button btn-sm whitespace-nowrap" disabled={mati}
                                data-testid={`cth-receive-${d.id}`} onClick={() => bukaTerima(d)}>Terima setoran</button>
                              <button type="button" className="secondary-button btn-sm whitespace-nowrap" disabled={Boolean(alasan)}
                                data-testid={`cth-reject-${d.id}`} onClick={() => tolak(d)}>Tolak</button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2 text-fs-12 text-kn-text-2">
                <span data-testid="cth-deposits-count">{deps.total || 0} setoran · {formatCurrency(deps.amount_total || 0)}</span>
                <KNPager page={depPage} pageSize={PAGE_SIZE} total={deps.total || 0} onChange={setDepPage} testId="cth-deposits-pager" />
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Titipan belum disetor ── */}
      <div className="section-card" data-testid="cth-holdings">
        <div className="section-head">
          <h2 className="flex items-center gap-2"><Users size={16} className="text-kn-warning-text" aria-hidden="true" />Titipan belum disetor</h2>
        </div>
        <div className="section-body space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <SearchBox value={search} onChange={(v) => { setSearch(v); setHoldPage(1); }}
              placeholder="Cari nomor titipan / kwitansi / pelanggan / pemegang…" testId="cth-search" />
            <label className="inline-flex items-center gap-1.5 whitespace-nowrap text-fs-12 text-kn-text" data-testid="cth-overdue">
              <input type="checkbox" checked={overdue} onChange={(e) => { setOverdue(e.target.checked); setHoldPage(1); }}
                data-testid="cth-overdue-toggle" />
              Lewat tenggat
            </label>
            {holder && (
              <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="cth-holder-clear"
                onClick={() => { setHolder(null); setHoldPage(1); }}>
                Pemegang: {holder.holder_name || "—"} <X size={12} aria-hidden="true" />
              </button>
            )}
          </div>
          {holdState === "loading" ? (
            <p className="py-4 text-center text-fs-12 text-kn-text-2" role="status" data-testid="cth-holdings-loading">Memuat titipan…</p>
          ) : holdState === "error" ? (
            <ErrorNotice message={`Titipan tidak bisa dimuat. ${holdErr}`.trim()} onRetry={loadHold} testId="cth-holdings-error" />
          ) : holdRows.length === 0 ? (
            <p className="py-6 text-center text-fs-12 text-kn-text-2" data-testid="cth-holdings-empty">
              {overdue ? "Tidak ada titipan tunai yang lewat tenggat." : search.trim()
                ? `Tidak ada titipan yang cocok dengan “${search.trim()}”.` : "Tidak ada titipan tunai."}
            </p>
          ) : (
            <>
              {!holder && holders.length > 0 && (
                <div className="table-wrap">
                  <table className="data-table head-wrap" data-testid="cth-holders-table">
                    <thead><tr>
                      <th>Pemegang</th><th className="text-right">Kwitansi</th><th className="text-right">Belum disetor</th>
                      <th>Terima paling lama</th><th>Lewat tenggat</th><th className="col-sticky-end text-right">Rincian</th>
                    </tr></thead>
                    <tbody>
                      {holders.map((g) => (
                        <tr key={g.holder_user_id} data-testid={`cth-holder-row-${g.holder_user_id}`}>
                          <td className="whitespace-nowrap font-semibold">{g.holder_name || "—"}</td>
                          <td className="text-right tabular-nums">{g.count}</td>
                          <td className="text-right tabular-nums whitespace-nowrap">{formatCurrency(g.held_total)}</td>
                          <td className="whitespace-nowrap">{formatDate(g.oldest_received_at)} · {ageText(g.oldest_received_at)}</td>
                          <td>{g.overdue_count > 0
                            ? <span className="inline-flex items-center gap-1"><OverduePill testId={`cth-holder-overdue-${g.holder_user_id}`} /><span className="tabular-nums text-fs-12">{g.overdue_count}</span></span>
                            : <span className="text-kn-text-2">—</span>}</td>
                          <td className="col-sticky-end text-right">
                            <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid={`cth-holder-open-${g.holder_user_id}`}
                              onClick={() => { setHolder(g); setHoldPage(1); }}>Lihat kwitansi</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {holder && (
                <div className="table-wrap">
                  <table className="data-table head-wrap" data-testid="cth-holdings-table">
                    <thead><tr>
                      <th>No. titipan</th><th>Kwitansi</th><th>Pelanggan</th><th>Diterima</th>
                      <th className="text-right">Jumlah</th><th className="text-right">Belum disetor</th><th>Status</th>
                    </tr></thead>
                    <tbody>
                      {holdRows.map((h) => (
                        <tr key={h.id} data-testid={`cth-holding-row-${h.id}`}>
                          <td className="font-mono whitespace-nowrap">{h.number}</td>
                          <td className="font-mono whitespace-nowrap">{h.receipt_number}</td>
                          <td className="max-w-[200px] break-words">{h.customer_name || "—"}</td>
                          <td className="whitespace-nowrap">{formatDate(h.received_at)}</td>
                          <td className="text-right tabular-nums whitespace-nowrap">{formatCurrency(h.amount)}</td>
                          <td className="text-right tabular-nums whitespace-nowrap">{formatCurrency(h.outstanding)}</td>
                          <td><div className="flex flex-wrap gap-1">
                            <StatusPill status={h.status} testId={`cth-holding-status-${h.id}`} />
                            {h.overdue && <OverduePill testId={`cth-holding-overdue-${h.id}`} />}
                          </div></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="flex flex-wrap items-center justify-between gap-2 text-fs-12 text-kn-text-2">
                <span data-testid="cth-holdings-count">
                  {holder ? `${hold.total || 0} kwitansi titipan ${holder.holder_name || ""}`.trim()
                    : `${holders.length} pemegang · ${hold.total || 0} kwitansi titipan`}
                </span>
                {holder && <KNPager page={holdPage} pageSize={PAGE_SIZE} total={hold.total || 0} onChange={setHoldPage} testId="cth-holdings-pager" />}
              </div>
            </>
          )}
        </div>
      </div>

      <FormModal open={Boolean(target)} onClose={() => setTarget(null)} title={`Terima setoran ${target?.number || ""}`}
        subtitle={pt} icon={HandCoins} testId="cth-receive-form" onSubmit={terima} submitLabel="Terima setoran"
        busy={busy} submitDisabled={cashAccountBlocked(accState, acc)} error={formErr}>
        {target && (
          <div className="space-y-3">
            <dl className="grid grid-cols-2 gap-2 text-fs-12">
              <div><dt className="text-kn-text-2">Penyetor</dt><dd className="font-semibold" data-testid="cth-receive-holder">{target.holder_name || "—"}</dd></div>
              <div><dt className="text-kn-text-2">Jumlah</dt><dd className="font-bold tabular-nums" data-testid="cth-receive-amount">{formatCurrency(target.amount)}</dd></div>
            </dl>
            <CashAccountField entityId={selectedEntity} value={acc} onChange={setAcc} onState={setAccState} onAccount={setAccRow}
              label="Masuk ke rekening" testId="cth-receive-account" />
            {cashAccountBlocked(accState, acc) && (
              <p className="text-fs-12 text-kn-danger-text" data-testid="cth-receive-account-why">{cashAccountBlockReason(accState)}</p>
            )}
          </div>
        )}
      </FormModal>
    </div>
  );
}
