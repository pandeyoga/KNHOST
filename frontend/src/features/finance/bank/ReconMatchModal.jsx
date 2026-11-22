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
import { formatCurrency, formatDate } from "../../../utils/formatters";
import MoneyInput from "../../../components/MoneyInput";
import { parseDecimal, toDecimalText } from "../../../utils/decimalInput";
import ErrorNotice from "../../../components/ErrorNotice";
import FilterChips from "../../../components/FilterChips";
import FormModal from "../../../components/FormModal";
import { apiErrorText } from "../../../utils/apiError";
import useIntentKey from "../../../hooks/useIntentKey";
import { moneyPost } from "../../../utils/moneyRequest";

// PK-42 (UX-18) — satu pemformat tanggal WIB bersama ("23 Okt 2026"); dulu zona perangkat & tahun dua angka.
const fmtDate = (s) => formatDate(s);
// PK-42 — nominal alokasi (teks `MoneyInput`, koma desimal boleh) → angka; kosong/tak sah → 0.
const amt = (v) => { const n = parseDecimal(v); return Number.isFinite(n) ? n : 0; };

export default function ReconMatchModal({ line, onClose, onDone, onError }) {
  const [data, setData] = useState(null);
  const [mode, setMode] = useState("single");        // single | split
  const [alloc, setAlloc] = useState({});            // txn_id -> nominal
  const [busy, setBusy] = useState("");
  // INV-UI-03 — modal WAJIB menampilkan penolakannya sendiri: bilah error layar
  // induk berada di belakang lapisan modal ini, jadi tak terlihat pengguna.
  const [mErr, setMErr] = useState("");
  // PK-12 — cocokkan 1:1 dan pecah 1:N ber-Idempotency-Key (satu kunci per aksi).
  const matchIntent = useIntentKey("brmatch");
  const splitIntent = useIntentKey("brsplit");

  // Uji rekonsiliasi R4 (18 Nov) — mode pecah meminta kandidat `split`: transaksi yang LEBIH KECIL dari transfer
  // (dulu kandidat hanya transaksi bernominal ≈ transfer, sehingga kwitansi-kwitansi pecahannya tidak pernah tampil).
  const load = useCallback(async () => {
    setBusy("load");
    try {
      const r = await axios.get(`${API}/bank-reconciliation/lines/${line.id}/candidates`,
        { params: { limit: 25, mode } });
      setData(r.data);
    } catch (e) { setMErr(apiErrorText(e)); onError?.(e); } finally { setBusy(""); }
  }, [line.id, mode, onError]);

  useEffect(() => { load(); }, [load]);

  const allocTotal = useMemo(
    () => Object.values(alloc).reduce((a, v) => a + amt(v), 0), [alloc]);
  const remaining = Number(line.amount || 0) - allocTotal;
  const allocCount = useMemo(
    () => Object.values(alloc).filter((v) => amt(v) > 0).length, [alloc]);

  async function doSingle(txnId, score) {
    setBusy(txnId);
    try {
      const body = { txn_id: txnId };
      await matchIntent.send({ id: line.id, ...body },
        (k) => moneyPost(`${API}/bank-reconciliation/lines/${line.id}/match`, body, k));
      onDone(`Mutasi ditautkan${score ? ` (skor ${Number(score).toFixed(0)})` : ""}.`);
    } catch (e) { setMErr(apiErrorText(e)); onError?.(e); } finally { setBusy(""); }
  }

  async function doSplit() {
    const allocations = Object.entries(alloc)
      .filter(([, v]) => amt(v) > 0)
      .map(([txn_id, v]) => ({ txn_id, amount: amt(v) }));
    setBusy("split");
    try {
      const body = { allocations };
      const r = await splitIntent.send({ id: line.id, ...body },
        (k) => moneyPost(`${API}/bank-reconciliation/lines/${line.id}/match-split`, body, k));
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
          <button type="button" className="secondary-button" onClick={onClose} disabled={busy === "split"}>Batal</button>
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

      {/* Uji rekonsiliasi R4 (18 Nov) — kombinasi transaksi yang sisanya PAS menutup transfer (server `combos`);
          satu klik mengisi alokasinya, orang tetap memeriksa lalu menekan Simpan pemecahan. */}
      {mode === "split" && (data?.combos || []).map((c, i) => (
        <div key={c.txn_ids.join("-")} data-testid={`recon-split-combo-${i}`}
          className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded border border-[#BFE5CC] bg-[#EAF7EE] px-3 py-2 text-[11px]">
          <span>
            <b>Kombinasi pas:</b>{" "}
            {c.numbers.map((n, j) => `${n} (${formatCurrency(c.amounts[j])})`).join(" + ")}
            {" = "}<b>{formatCurrency(c.total)}</b>
          </span>
          <button type="button" className="secondary-button btn-sm" data-testid={`recon-split-combo-fill-${i}`}
            onClick={() => setAlloc(Object.fromEntries(c.txn_ids.map((id, j) => [id, toDecimalText(c.amounts[j], 2)])))}>
            Isi alokasi
          </button>
        </div>
      ))}

      <div className="mt-2 rounded border border-[#EFF0F2] sm:max-h-[340px] sm:overflow-auto">
        {busy === "load" ? (
          <div className="p-4 text-center text-[12px] text-[#8E8E93]">
            <RefreshCw size={14} className="spin inline" /> Menghitung kandidat…
          </div>
        ) : cands.length === 0 ? (
          <div className="p-4 text-center text-[12px] text-[#8E8E93]" data-testid="recon-cand-empty">
            Tidak ada transaksi buku yang layak (arah dana, nominal, atau tanggalnya terlalu jauh).
            {mode === "single"
              ? " Bila satu transfer ini melunasi beberapa transaksi, pilih “Pecah ke beberapa transaksi”."
              : ""}{" "}
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
                  <div className="w-[160px]">
                    <MoneyInput testId={`recon-alloc-${t.id}`} className="input-field" placeholder="Nominal"
                      aria-label={`Nominal alokasi ${t.number || ""}`.trim()}
                      value={alloc[t.id] ?? ""}
                      onChange={(v) => setAlloc((cur) => ({ ...cur, [t.id]: v }))} />
                  </div>
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
