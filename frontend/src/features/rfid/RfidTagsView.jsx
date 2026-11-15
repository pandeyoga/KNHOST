import { useEffect, useState } from "react";
import { Tag, RefreshCw, Trash2, Zap, Boxes, Radio, PackageSearch, Printer } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import useListSearch from "@/hooks/useListSearch";
import axios, { API } from "../../services/apiClient";
import { q, fmtTime, Stat, EmptyBox, SectionCard, RfidHeader, useWarehouses } from "./rfidShared";
import PageTabs from "../../components/PageTabs";
import ResponsiveTable from "../../components/ResponsiveTable";
import RfidPrintVerifyPanel from "./RfidPrintVerifyPanel";
import PrinterQueuePanel from "./PrinterQueuePanel";
import { RollTagActionModal } from "./PrinterModals";
import { canCurrent } from "../../config/roles";
import { reprintRollLabel } from "../../utils/rollLabels";
import { askConfirm } from "../../services/confirmService";
import { docStatusLabel } from "../../utils/docStatus";
import ExportMenu from "../../components/ExportMenu";   // FIX-4 — tombol baku Unduh (Excel/CSV, Pusat Export)
import ListLimitNote from "../wms/ListLimitNote";   // FIX-5 (B3b LST-01)

export default function RfidTagsView({ currentUser, selectedEntity }) {
  const [tab, setTab] = useState("tags");
  const { whId, setWhId, whOpts, warehouses } = useWarehouses();
  const [summary, setSummary] = useState(null);
  const [tags, setTags] = useState([]);
  // FIX-5 (B3b LST-01) — label tab dulu "(1000)" = panjang potongan server; kini jumlah sungguhan + "Muat berikutnya".
  const [tagMeta, setTagMeta] = useState(null);
  const [tagMoreBusy, setTagMoreBusy] = useState(false);
  const srch = useListSearch(tags, null, { testId: "rfid-tags", placeholder: "Cari EPC / SKU / produk / roll…" });
  const [untagged, setUntagged] = useState([]);
  const [untagMeta, setUntagMeta] = useState(null);   // FIX-7 (B3b LST-01) — jumlah sungguhan roll belum ber-tag
  const [untagMoreBusy, setUntagMoreBusy] = useState(false);
  // UAT 24 Okt (audit UI tahap 2) — tab Belum Ber-tag dulu merender 500 kartu sekaligus tanpa cari/paginasi.
  const srchU = useListSearch(untagged, ["roll_no", "sku", "product_name", "lot"], { testId: "rfid-untagged", placeholder: "Cari roll / SKU / produk / lot…" });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState("");
  // PREP-F — cetak ulang teks (EPC tetap) vs ganti tag (EPC baru) untuk tag aktif; tombol mengikuti izin.
  const [tagAction, setTagAction] = useState(null);
  const canTagAction = canCurrent("wms", "print") || canCurrent("wms", "approve");
  // Cetak ulang label QR roll (rusak/hilang) — data roll segar dari /rfid/lookup.
  const reprintByCode = async (code) => {
    if (!code) return;
    setBusy(true);
    try {
      const { data } = await axios.get(`${API}/rfid/lookup`, { params: { code, record: false } });
      await reprintRollLabel(data.roll, data.product_name);
      const { data: p } = await axios.post(`${API}/rfid/rolls/${data.roll.id}/label-prints`, { channel: "browser" });
      setMsg(`Label ${data.roll?.roll_no} dicetak (cetak ke-${p.print_seq}${p.reprint ? ", ulang" : ""}) · qty terkini ${p.qty} ${p.unit || ""}${p.epc ? ` · EPC tetap ${p.epc}` : ""}.`);
    }
    catch (e) { setError(e); } finally { setBusy(false); }
  };

  const load = async () => {
    setLoading(true); setError(null);
    try {
      const params = whId ? { warehouse_id: whId } : {};
      const [s, t, u] = await Promise.all([
        axios.get(`${API}/rfid/summary`, { params }),
        axios.get(`${API}/rfid/tags`, { params: { ...params, status: "active" } }),
        axios.get(`${API}/rfid/untagged-rolls`, { params }),
      ]);
      setSummary(s.data); setTags(t.data.tags || []); setUntagged(u.data.rolls || []);
      setUntagMeta(u.data.total !== undefined ? { total: u.data.total, truncated: !!u.data.truncated,
        shown: (u.data.rolls || []).length, skip: 0 } : null);
      setTagMeta(t.data.total !== undefined ? { total: t.data.total, truncated: !!t.data.truncated,
        shown: (t.data.tags || []).length, skip: 0 } : null);
    } catch (e) { setError(e.response?.data?.detail || e.message || "Gagal memuat data RFID"); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [whId, selectedEntity]); // eslint-disable-line
  const loadMoreTags = async () => {
    setTagMoreBusy(true);
    try {
      const t = await axios.get(`${API}/rfid/tags`, { params: { ...(whId ? { warehouse_id: whId } : {}), status: "active",
        skip: tags.length } });
      const next = [...tags, ...(t.data.tags || [])];
      setTags(next);
      setTagMeta({ total: t.data.total, truncated: !!t.data.truncated, shown: next.length, skip: 0 });
    } catch (e) { setError(e.response?.data?.detail || e.message || "Gagal memuat tag"); } finally { setTagMoreBusy(false); }
  };

  const loadMoreUntagged = async () => {   // FIX-7 (B3b LST-01) — dulu 500 roll tanpa tanda
    setUntagMoreBusy(true);
    try {
      const u = await axios.get(`${API}/rfid/untagged-rolls`, { params: { ...(whId ? { warehouse_id: whId } : {}), skip: untagged.length } });
      const seen = new Set(untagged.map((r) => r.id));
      const next = [...untagged, ...(u.data.rolls || []).filter((r) => !seen.has(r.id))];
      setUntagged(next);
      setUntagMeta({ total: u.data.total, truncated: next.length < u.data.total, shown: next.length, skip: 0 });
    } catch (e) { setError(e.response?.data?.detail || e.message || "Gagal memuat roll"); } finally { setUntagMoreBusy(false); }
  };

  const flash = (m) => { setMsg(m); setTimeout(() => setMsg(""), 2500); };
  const encode = async (rollId) => {
    setBusy(true); setError(null);
    try { await axios.post(`${API}/rfid/tags/encode`, { roll_id: rollId }); flash("Tag RFID ter-encode."); await load(); }
    catch (e) { setError(e.response?.data?.detail || "Gagal encode tag"); } finally { setBusy(false); }
  };
  // UAT 24 Okt (audit UI tahap 2) — Auto-Encode & Pensiunkan dulu langsung POST/DELETE sekali klik (aksi massal
  // tak bisa dibatalkan). Server meng-encode paling banyak 200 roll per klik (rfid_service.auto_encode cap=200).
  const whName = whId ? (warehouses.find((w) => w.id === whId)?.name || "gudang terpilih") : "semua gudang";
  const autoEncode = async () => {
    const total = Math.max(summary?.untagged_rolls ?? 0, untagged.length);
    const n = Math.min(total, 200);
    const totalTxt = total >= 5000 ? "5.000+" : total.toLocaleString("id-ID");
    if (!(await askConfirm({
      title: `Encode otomatis ${n.toLocaleString("id-ID")} roll di ${whName}?`,
      message: `Tag RFID baru dibuat untuk setiap roll tanpa tag (paling banyak 200 roll per klik; ${totalTxt} roll belum ber-tag). Encode massal tidak bisa dibatalkan sekaligus — tiap tag harus dipensiunkan satu per satu.`,
      danger: true, confirmLabel: "Encode otomatis",
    }))) return;
    setBusy(true); setError(null);
    try { const r = await axios.post(`${API}/rfid/tags/auto-encode`, { warehouse_id: whId || null }); flash(`${r.data.encoded} roll ter-encode otomatis.`); await load(); }
    catch (e) { setError(e.response?.data?.detail || "Gagal encode otomatis"); } finally { setBusy(false); }
  };
  const retire = async (t) => {
    if (!(await askConfirm({
      title: `Pensiunkan tag ${t.epc}?`,
      message: `Tag dilepas dari roll ${t.roll_no || "—"}${t.product_name ? ` (${t.product_name})` : ""}; roll kembali ke daftar Belum Ber-tag.`,
      danger: true, confirmLabel: "Pensiunkan",
    }))) return;
    setBusy(true); setError(null);
    try { await axios.delete(`${API}/rfid/tags/${t.id}`); flash("Tag dipensiunkan (roll kembali tanpa tag)."); await load(); }
    catch (e) { setError(e.response?.data?.detail || "Gagal memensiunkan tag"); } finally { setBusy(false); }
  };

  return (
    <div data-testid="rfid-tags-view" className="space-y-4">
      <RfidHeader icon={Tag} testId="rfid-tags-header" title="Tag RFID" subtitle="Pasangkan (encode) tag EPC ke roll fisik. Memasang tag tidak mengubah stok.">
        <KNSelect data-testid="rfid-tags-wh" value={whId} onValueChange={setWhId} options={whOpts}
          className="field !py-1 !px-2 text-[12px] w-auto" placeholder="Gudang" />
        <button type="button" data-testid="rfid-tags-refresh" onClick={load} className="secondary-button">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Muat ulang
        </button>
      </RfidHeader>

      {error && <ErrorNotice message={error} onRetry={load} />}
      {msg && <div className="rounded-lg bg-[#E7F7EC] text-[#1B7E3B] text-[12px] font-semibold px-3 py-2">{msg}</div>}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat icon={Tag} label="Total Tag" value={summary?.tags_total ?? 0} color="#0058CC" loading={loading} testId="rfid-stat-total" />
        <Stat icon={Radio} label="Tag Aktif" value={summary?.tags_active ?? 0} color="#34C759" loading={loading} testId="rfid-stat-active" />
        {/* Audit UI 095 — server menghitung paling banyak 5.000 roll (rfid_service.summary); tandai "5.000+" agar tidak terbaca sebagai angka pasti. */}
        <Stat icon={Boxes} label="Roll Belum Ber-tag" value={(summary?.untagged_rolls ?? 0) >= 5000 ? "5.000+" : (summary?.untagged_rolls ?? 0).toLocaleString("id-ID")} color="#FF9500" loading={loading} testId="rfid-stat-untagged" />
        <Stat icon={PackageSearch} label="Pembaca Aktif" value={`${summary?.devices_online ?? 0}/${summary?.devices_total ?? 0}`} color="#5856D6" loading={loading} />
      </div>

      {/* Fase 4 · R3 (L-01/L-02) — tab buatan sendiri (TabBtn) → PageTabs baku; testid `rfid-tab-*` tetap. */}
      <PageTabs value={tab} onChange={setTab} testId="rfid-tab" ariaLabel="Tag RFID" tabs={[
        { key: "tags", label: `Tag Aktif${(tagMeta?.total ?? tags.length) ? ` (${(tagMeta?.total ?? tags.length).toLocaleString("id-ID")})` : ""}` },
        { key: "untagged", label: `Belum Ber-tag${untagged.length ? ` (${(summary?.untagged_rolls ?? 0) > untagged.length ? `${untagged.length} dari ${summary.untagged_rolls >= 5000 ? "5.000+" : summary.untagged_rolls.toLocaleString("id-ID")}` : untagged.length})` : ""}` },
        { key: "print", label: "Cetak & Verifikasi" },
        { key: "printers", label: "Antrean Printer" },
      ]} />

      {tab === "print" ? (
        <RfidPrintVerifyPanel whId={whId} selectedEntity={selectedEntity} onChanged={load} />
      ) : tab === "printers" ? (
        <PrinterQueuePanel whId={whId} isAdmin={currentUser?.role === "admin"} />
      ) : tab === "tags" ? (
        <SectionCard title="Daftar Tag RFID Aktif" right={
          <ExportMenu dataset="rfid_tags" label="tag-rfid-aktif" testId="rfid-tags-export" search={srch.q}
            filters={[["status", "eq", "active"], whId && ["warehouse_id", "eq", whId]]} sort={[{ key: "encoded_at", dir: "desc" }]} />}>
          {srch.searchBox}
          <ListLimitNote meta={tagMeta} noun="tag" onMore={loadMoreTags} loading={tagMoreBusy}
            hint="pencarian di sini hanya mencakup tag yang sudah dimuat." testId="rfid-tags-limit" />
          {/* Fase 4 · R3 (L-07) — `<table>` mentah → ResponsiveTable (`.data-table` di desktop, kartu di HP 390 px);
              testid baris `rfid-tag-row-<id>` & pager `rfid-tags-pager` tetap. */}
          {loading ? <div className="h-16 bg-[#F5F5F7] rounded animate-pulse" />
            : srch.shown.length === 0 ? <EmptyBox icon={Tag} text="Belum ada tag aktif. Encode roll di tab 'Belum Ber-tag'." />
              : (
                <ResponsiveTable testId="rfid-tag" rows={srch.pageRows} rowKey="id" footer={srch.pager}
                  columns={[
                    { key: "epc", header: "EPC", mobile: "title", className: "font-mono font-semibold text-[11px]" },
                    { key: "sku", header: "SKU", mobile: "subtitle" },
                    { key: "product_name", header: "Produk", priority: 1 },
                    { key: "roll", header: "Roll / Lot", priority: 2, render: (t) => `${t.roll_no} · ${t.lot || "—"}` },
                    { key: "last_seen", header: "Terakhir Terbaca", priority: 3, className: "text-[#6B6B73]",
                      render: (t) => (t.last_seen_at ? `${fmtTime(t.last_seen_at)} @ ${t.last_seen_location || "?"}` : "belum terbaca") },
                  ]}
                  actions={(t) => (
                    <span className="inline-flex justify-end gap-1 whitespace-nowrap">
                      <button type="button" data-testid={`rfid-reprint-${t.id}`} disabled={busy} onClick={() => reprintByCode(t.roll_id || t.roll_no)}
                        className="inline-flex items-center gap-1 text-[#0058CC] hover:bg-[#EAF2FF] rounded px-2 py-1 disabled:opacity-40" title="Cetak ulang label QR">
                        <Printer size={13} /> Label
                      </button>
                      {canTagAction && (
                        <button type="button" data-testid={`rfid-tag-action-${t.id}`} disabled={busy}
                          onClick={() => setTagAction({ roll_id: t.roll_id, roll_no: t.roll_no, epc: t.epc })}
                          className="inline-flex items-center gap-1 text-[#0058CC] hover:bg-[#EAF2FF] rounded px-2 py-1 disabled:opacity-40"
                          title="Cetak ulang teks label / ganti tag RFID">
                          <Tag size={13} /> Ganti/Cetak
                        </button>)}
                      <button type="button" data-testid={`rfid-retire-${t.id}`} disabled={busy} onClick={() => retire(t)}
                        className="inline-flex items-center gap-1 text-[#C0341D] hover:bg-[#FBE9E7] rounded px-2 py-1 disabled:opacity-40">
                        <Trash2 size={13} /> Pensiunkan
                      </button>
                    </span>
                  )} />
              )}
        </SectionCard>
      ) : (
        <SectionCard title="Roll Fisik Belum Ber-tag" right={
          <button type="button" data-testid="rfid-auto-encode" disabled={busy || untagged.length === 0} onClick={autoEncode}
            className="primary-button disabled:opacity-40">
            <Zap size={14} /> Encode Otomatis
          </button>}>
          {loading ? <div className="h-16 bg-[#F5F5F7] rounded animate-pulse" />
            : untagged.length === 0 ? <EmptyBox icon={Radio} text="Semua roll fisik sudah ber-tag RFID." />
              : (
                <div className="space-y-2">
                  <div className="kn-list-toolbar">
                    {srchU.toolbar}
                    <ExportMenu dataset="inventory_rolls" label="roll-belum-bertag" testId="rfid-untagged-export" search={srchU.q}
                      filters={[["rfid_tag_id", "empty"], ["length_remaining", "gt", 0], whId && ["warehouse_id", "eq", whId],
                        ["status", "in", ["available", "reserved", "committed", "picked", "packed", "hold", "wip", "quarantine", "blocked", "damaged"]]]} />
                  </div>
                  <ListLimitNote meta={untagMeta} noun="roll" onMore={loadMoreUntagged} loading={untagMoreBusy}
                    hint="pencarian di sini hanya mencakup roll yang sudah dimuat." testId="rfid-untagged-limit" />
                  {srchU.shown.length === 0 && <EmptyBox icon={PackageSearch} text="Tidak ada roll yang cocok dengan pencarian." />}
                  {srchU.pageRows.map((r) => (
                    <div key={r.id} data-testid={`rfid-untagged-${r.id}`} className="flex flex-wrap items-center gap-2 rounded-lg bg-[#FAFAFB] p-2">
                      <div className="flex-1 min-w-[200px]">
                        <p className="text-[12px] font-semibold">{r.roll_no} · {r.sku || "—"}</p>
                        <p className="text-[11px] text-[#6B6B73]">{r.product_name} — {q(r.length_remaining)} {r.unit} · Lot {r.lot || "—"} · {docStatusLabel(r.status)}</p>
                      </div>
                      <button data-testid={`rfid-untagged-reprint-${r.id}`} disabled={busy} onClick={() => reprintByCode(r.id)}
                        className="flex items-center gap-1 rounded-lg border border-[#0058CC] text-[#0058CC] px-3 py-1.5 text-[12px] font-semibold disabled:opacity-40" title="Cetak ulang label QR">
                        <Printer size={13} /> Label
                      </button>
                      <button data-testid={`rfid-encode-${r.id}`} disabled={busy} onClick={() => encode(r.id)}
                        className="flex items-center gap-1 rounded-lg bg-[#0058CC] text-white px-3 py-1.5 text-[12px] font-semibold disabled:opacity-40">
                        <Tag size={13} /> Encode
                      </button>
                    </div>
                  ))}
                </div>
              )}
        </SectionCard>
      )}
      {tagAction && <RollTagActionModal roll={tagAction} onClose={() => setTagAction(null)} onDone={() => load()} />}
    </div>
  );
}
