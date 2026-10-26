import { useEffect, useMemo, useState } from "react";
import { MapPin, RefreshCw, Radar, Radio, PackageX, AlertTriangle, ClipboardCheck } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import LinkCard from "../../components/LinkCard";
import { useAppNav } from "../../context/AppNavContext";
import useListSearch from "@/hooks/useListSearch";
import axios, { API } from "../../services/apiClient";
import { Stat, EmptyBox, Pill, SectionCard, RfidHeader, fmtTime, useWarehouses } from "./rfidShared";

const STATE_COLOR = { tracked: "green", unseen: "gray", drift: "red" };

export default function RfidLocationsView({ currentUser, selectedEntity }) {
  const { whId, setWhId, whOpts } = useWarehouses();
  const nav = useAppNav();
  const [items, setItems] = useState([]);
  const srch = useListSearch(items, null, { testId: "rfid-loc", placeholder: "Cari EPC / produk / roll / bin…" });
  const [readers, setReaders] = useState([]);
  const [readerId, setReaderId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState("");

  const load = async () => {
    setLoading(true); setError(null);
    try {
      const params = whId ? { warehouse_id: whId } : {};
      const [l, d] = await Promise.all([
        axios.get(`${API}/rfid/locations`, { params }),
        axios.get(`${API}/rfid/devices`, { params }),
      ]);
      setItems(l.data.items || []);
      const rdrs = (d.data.devices || []).filter((x) => x.type !== "gate");
      setReaders(rdrs);
      if (rdrs.length && !rdrs.find((r) => r.id === readerId)) setReaderId(rdrs[0].id);
    } catch (e) { setError(e.response?.data?.detail || e.message || "Gagal memuat lokasi RFID"); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [whId, selectedEntity]); // eslint-disable-line

  const flash = (m) => { setMsg(m); setTimeout(() => setMsg(""), 2500); };
  const sweep = async () => {
    if (!readerId) { setError("Pilih pembaca dulu"); return; }
    setBusy(true); setError(null);
    try { const r = await axios.post(`${API}/rfid/reader/scan`, { device_id: readerId }); flash(`${r.data.scanned} tag terbaca oleh pembaca.`); await load(); }
    catch (e) { setError(e.response?.data?.detail || "Gagal memindai area"); } finally { setBusy(false); }
  };

  const counts = useMemo(() => ({
    total: items.length,
    tracked: items.filter((i) => i.state === "tracked").length,
    unseen: items.filter((i) => i.state === "unseen").length,
    drift: items.filter((i) => i.state === "drift").length,
  }), [items]);
  const readerOpts = readers.map((r) => ({ value: r.id, label: [r.code, r.location, r.warehouse_name].filter(Boolean).join(" · ") }));

  return (
    <div data-testid="rfid-locations-view" className="space-y-4">
      <RfidHeader icon={MapPin} title="Lokasi RFID" subtitle="Lokasi terakhir tiap tag terbaca + pencocokan dengan bin yang ditetapkan.">
        <KNSelect data-testid="rfid-loc-wh" value={whId} onValueChange={setWhId} options={whOpts}
          className="field !py-1 !px-2 text-[12px] w-auto" placeholder="Gudang" />
        <button data-testid="rfid-loc-refresh" onClick={load}
          className="flex items-center gap-1 rounded-lg border border-[#EFF0F2] bg-white px-3 py-1.5 text-[12px] font-semibold hover:bg-[#F5F5F7]">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Muat ulang
        </button>
      </RfidHeader>

      {error && <ErrorNotice message={error} onRetry={load} />}
      {msg && <div className="rounded-lg bg-[#E7F7EC] text-[#1B7E3B] text-[12px] font-semibold px-3 py-2">{msg}</div>}

      {/* Fase 3 · P5 — D-15: tab "Stock Opname (RFID)" dulu alur opname KEDUA di sini. Kini satu alur di Operasi
          Gudang › Stock Opname (metode "Sapu RFID"); di sini hanya tautan, membawa gudang yang sedang dipilih. */}
      <LinkCard testId="rfid-loc-opname-link" what="Stock opname RFID (sapu handheld)"
        where="Operasi Gudang › Stok, Transfer & Opname › Stock Opname" view="operations" tab="cycle"
        preset={{ tab: "cycle", method: "rfid", warehouse: whId }} label="Buka Stock Opname"
        icon={ClipboardCheck} />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat icon={Radio} label="Total Tag" value={counts.total} color="#0058CC" loading={loading} />
        <Stat icon={Radar} label="Terlacak" value={counts.tracked} color="#34C759" loading={loading} testId="rfid-loc-tracked" />
        <Stat icon={PackageX} label="Belum Terbaca" value={counts.unseen} color="#8E8E93" loading={loading} />
        <Stat icon={AlertTriangle} label="Beda Gudang (Drift)" value={counts.drift} color="#C0341D" loading={loading} testId="rfid-loc-drift" />
      </div>

      {/* UAT 24 Okt (audit UI tahap 2) — dulu "Pilih reader" hanya placeholder tanpa penjelasan, tombol Pindai mati tanpa
          alasan, dan tabel lokasi tag (31 baris) ada di dalam kartu "Simulasi Pindai Area". Kini dua kartu terpisah. */}
      <SectionCard title="Simulasi Pindai Area (Pembaca Tetap)">
        {!loading && readers.length === 0 ? (
          <p data-testid="rfid-loc-no-reader" className="text-[12px] text-[#6B6B73]">
            Belum ada pembaca tetap di gudang ini — pindai area butuh pembaca.{" "}
            {/* Fase 3 · P8 (D-29) — dulu tautan mentah `?view=cs-rfid-devices` (muat ulang halaman); kini jalur navigasi
                bersama ke Pengaturan › Integrasi & Sistem › Perangkat tab RFID, hanya bila peran boleh membukanya. */}
            {nav.canOpen("settings-devices") ? (
              <button type="button" data-testid="rfid-loc-devices-link" className="font-semibold text-[#0058CC] underline"
                onClick={() => nav.go("settings-devices", { preset: { tab: "rfid" } })}>Buat di Perangkat RFID</button>
            ) : (
              <span data-testid="rfid-loc-devices-readonly">Pembaca ditambahkan Admin di Pengaturan › Integrasi &amp; Sistem › Perangkat.</span>
            )}
          </p>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <KNSelect data-testid="rfid-loc-reader" value={readerId} onValueChange={setReaderId} options={readerOpts}
              className="field !py-1 !px-2 text-[12px] w-64 max-w-full" placeholder="Pilih pembaca" />
            <button data-testid="rfid-loc-sweep" disabled={busy || !readerId} onClick={sweep}
              title={!readerId ? "Pilih pembaca dulu" : "Baca semua tag di jangkauan pembaca ini"}
              className="primary-button flex items-center gap-1">
              <Radar size={14} /> Pindai
            </button>
          </div>
        )}
      </SectionCard>

      <SectionCard title="Lokasi Tag">
        {srch.toolbar}
        {loading ? <div className="h-16 bg-[#F5F5F7] rounded animate-pulse" />
          : srch.shown.length === 0 ? <EmptyBox icon={MapPin} text={items.length ? "Tidak ada tag yang cocok dengan pencarian." : "Belum ada tag. Encode roll di menu Tag RFID dulu."} />
            : (
              <div className="overflow-x-auto">
                <table className="w-full text-[12px]">
                  <thead><tr className="text-left text-[11px] text-[#8E8E93] border-b border-[#EFF0F2]">
                    <th className="py-2 pr-2">EPC</th><th className="pr-2">Produk</th><th className="pr-2">Roll</th>
                    <th className="pr-2">Bin Ditetapkan</th><th className="pr-2">Terakhir Terbaca</th><th className="pr-2 text-right">Status</th>
                  </tr></thead>
                  <tbody>
                    {srch.pageRows.map((i) => (
                      <tr key={i.tag_id} data-testid={`rfid-loc-row-${i.tag_id}`} className="border-b border-[#F5F5F7] hover:bg-[#FAFAFB]">
                        <td className="py-2 pr-2 font-mono font-semibold text-[11px]">{i.epc}</td>
                        <td className="pr-2">{i.product_name || "—"}<span className="text-[#8E8E93]"> · {i.sku}</span></td>
                        <td className="pr-2">{i.roll_no || "—"}</td>
                        <td className="pr-2">{i.assigned_bin_code || <span className="text-[#8E8E93]">belum ditempatkan ke rak</span>}</td>
                        <td className="pr-2 text-[#6B6B73]">{i.last_seen_at ? `${i.last_seen_location || "?"} · ${fmtTime(i.last_seen_at)}` : "—"}</td>
                        <td className="pr-2 text-right"><Pill color={STATE_COLOR[i.state] || "gray"}>{i.state_label}</Pill></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
      </SectionCard>
    </div>
  );
}
