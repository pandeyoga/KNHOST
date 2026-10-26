/**
 * FASE G-8 — ReconMatchModal: kandidat transaksi buku BERPERINGKAT + alasan skor,
 * dengan dua mode: cocok satu-satu (1:1) atau **pecah** satu transfer ke beberapa
 * transaksi buku (1:N).
 *
 * Fase 4 · R2 — L-03: `.modal-card` buatan sendiri → `FormModal` baku (layar penuh di HP; tombol simpan pecahan di
 * kaki yang menempel). L-01: tombol-toggle mode (`primary`/`secondary` bergantian) → `FilterChips`
 * (`recon-mode-single`/`recon-mode-split` tetap). Testid lain tetap.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link2, RefreshCw, Split, Info } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { formatCurrency } from "../../../utils/formatters";
import ErrorNotice from "../../../components/ErrorNotice";
import FilterChips from "../../../components/FilterChips";
import FormModal from "../../../components/FormModal";
import { apiErrorText } from "../../../utils/apiError";

const fmtDate = (s) => {
  if (!s) return "—";
  try {
    return new Date(String(s).length <= 10 ? `${s}T00:00:00` : s)
      .toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "2-digit" });
  } catch { return s; }
};

export default function ReconMatchModal({ line, onClose, onDone, onError }) {
  const [data, setData] = useState(null);
  const [mode, setMode] = useState("single");        // single | split
  const [alloc, setAlloc] = useState({});            // txn_id -> nominal
  const [busy, setBusy] = useState("");
  // INV-UI-03 — modal WAJIB menampilkan penolakannya sendiri: bilah error layar
  // induk berada di belakang lapisan modal ini, jadi tak terlihat pengguna.
  const [mErr, setMErr] = useState("");

  const load = useCallback(async () => {
    setBusy("load");
    try {
      const r = await axios.get(`${API}/bank-reconciliation/lines/${line.id}/candidates`,
        { params: { limit: 25 } });
      setData(r.data);
    } catch (e) { setMErr(apiErrorText(e)); onError?.(e); } finally { setBusy(""); }
  }, [line.id, onError]);

  useEffect(() => { load(); }, [load]);

  const allocTotal = useMemo(
    () => Object.values(alloc).reduce((a, v) => a + (Number(v) || 0), 0), [alloc]);
  const remaining = Number(line.amount || 0) - allocTotal;
  const allocCount = useMemo(
    () => Object.values(alloc).filter((v) => Number(v) > 0).length, [alloc]);

  async function doSingle(txnId, score) {
    setBusy(txnId);
    try {
      await axios.post(`${API}/bank-reconciliation/lines/${line.id}/match`, { txn_id: txnId });
      onDone(`Mutasi ditautkan${score ? ` (skor ${Number(score).toFixed(0)})` : ""}.`);
    } catch (e) { setMErr(apiErrorText(e)); onError?.(e); } finally { setBusy(""); }
  }

  async function doSplit() {
    const allocations = Object.entries(alloc)
      .filter(([, v]) => Number(v) > 0)
      .map(([txn_id, v]) => ({ txn_id, amount: Number(v) }));
    setBusy("split");
    try {
      const r = await axios.post(`${API}/bank-reconciliation/lines/${line.id}/match-split`,
        { allocations });
      onDone(`Satu transfer dipecah ke ${allocations.length} transaksi buku `
        + `(${formatCurrency(r.data.allocated_total)}).`);
    } catch (e) { setMErr(apiErrorText(e)); onError?.(e); } finally { setBusy(""); }
  }

  const cands = data?.candidates || [];

  return (
    <FormModal open onClose={onClose} size="lg" icon={Link2} title="Cocokkan mutasi bank"
      subtitle={(
        <>
          {fmtDate(line.stmt_date)} · {line.direction === "in" ? "Masuk" : "Keluar"}{" "}
          <b>{formatCurrency(line.amount)}</b> — {line.description || "tanpa keterangan"}
        </>
      )}
      testId="recon-match-modal" busy={!!busy && busy !== "load"}
      footer={mode === "split" ? (
        <div className="flex flex-wrap justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose}>Batal</button>
          <button type="button" data-testid="recon-split-submit" className="primary-button"
            disabled={allocCount < 2 || remaining < -0.01 || busy === "split"}
            onClick={doSplit}>
            {busy === "split" ? <RefreshCw size={14} className="spin" /> : <Split size={14} />}
            Simpan pemecahan ({allocCount} transaksi)
          </button>
        </div>
      ) : null}>
      {mErr && (
        <ErrorNotice message={mErr} onDismiss={() => setMErr("")}
          testId="recon-match-error" />
      )}
      {data && (
        <p className="text-[11px] text-[#8E8E93]">
          Ambang otomatis {Number(data.auto_min).toFixed(0)} · ambang usulan{" "}
          {Number(data.suggest_min).toFixed(0)}
          {data.rule_applied ? " · aturan tersimpan ikut menambah poin" : ""}
        </p>
      )}

      <FilterChips className="mt-2" ariaLabel="Cara mencocokkan" value={mode} onChange={setMode}
        options={[
          { key: "single", label: "Satu transaksi", testId: "recon-mode-single" },
          { key: "split", label: "Pecah ke beberapa transaksi", icon: Split, testId: "recon-mode-split" },
        ]} />

      {mode === "split" && (
        <div className="mt-2 rounded border border-[#CBDCF7] bg-[#F2F7FF] px-3 py-2 text-[11px]"
          data-testid="recon-split-info">
          Isi nominal pada transaksi yang dilunasi transfer ini. Total alokasi tidak boleh
          melebihi nominal mutasi. Sisa belum dialokasikan:{" "}
          <b className={remaining < -0.01 ? "text-[#C0392B]" : "text-[#1B7F4B]"}>
            {formatCurrency(remaining)}
          </b>
        </div>
      )}

      <div className="mt-2 rounded border border-[#EFF0F2] sm:max-h-[340px] sm:overflow-auto">
        {busy === "load" ? (
          <div className="p-4 text-center text-[12px] text-[#8E8E93]">
            <RefreshCw size={14} className="spin inline" /> Menghitung kandidat…
          </div>
        ) : cands.length === 0 ? (
          <div className="p-4 text-center text-[12px] text-[#8E8E93]">
            Tidak ada transaksi buku yang layak (arah dana, nominal, atau tanggalnya terlalu jauh).
            Anda bisa menitipkan dana ini bila pengirimnya belum diketahui.
          </div>
        ) : cands.map((t) => (
          <div key={t.id} data-testid={`recon-cand-${t.id}`}
            className="px-3 py-2 border-b border-[#F5F5F7] last:border-0">
            <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5">
              <div className="min-w-0">
                <p className="text-[12px] truncate">
                  <b>{t.number}</b> · {fmtDate(t.txn_date)}{" "}
                  <span className="text-[#8E8E93]">{t.description || ""}</span>
                </p>
                <p className="text-[10px] text-[#8E8E93]">
                  Nominal {formatCurrency(t.amount)} · sisa {formatCurrency(t.outstanding)}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                  t.score >= (data?.auto_min || 80) ? "bg-[#EAF7EE] text-[#1B7F4B]"
                    : t.score >= (data?.suggest_min || 60) ? "bg-[#FFF4E5] text-[#B26A00]"
                      : "bg-[#F0F0F2] text-[#8E8E93]"}`}>
                  skor {Number(t.score).toFixed(0)}
                </span>
                {mode === "single" ? (
                  <button data-testid={`recon-pick-cand-${t.id}`} className="primary-button"
                    disabled={busy === t.id} onClick={() => doSingle(t.id, t.score)}>
                    Tautkan
                  </button>
                ) : (
                  <input data-testid={`recon-alloc-${t.id}`} type="number" min={0}
                    max={Number(t.outstanding)} step={1000} className="input-field w-[140px]"
                    placeholder="Nominal"
                    value={alloc[t.id] ?? ""}
                    onChange={(e) => setAlloc((cur) => ({ ...cur, [t.id]: e.target.value }))} />
                )}
              </div>
            </div>
            {(t.explain || []).length > 0 && (
              <p className="mt-1 flex items-start gap-1 text-[10px] text-[#6B6B73]">
                <Info size={10} className="mt-0.5 shrink-0" />
                {(t.explain || []).map((e) => `${e.label} (+${Number(e.points).toFixed(0)})`)
                  .join(" · ")}
              </p>
            )}
          </div>
        ))}
      </div>
    </FormModal>
  );
}
