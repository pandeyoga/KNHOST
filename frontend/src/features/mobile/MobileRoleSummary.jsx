/**
 * Tab Ringkas HP per peran — keputusan pemilik K-12 (26 Okt).
 *
 * Dulu tab Ringkas Desainer & Admin Sample berisi angka gudang/penjualan (`/dashboard`: stok 4 satuan, roll,
 * pelanggan) — tidak satu pun angka pekerjaannya sendiri. Kini:
 *  · Desainer     → DSR berjalan, tenggat dekat / lewat tenggat, revisi menunggu
 *                   (sumber: ringkasan server `GET /design-requests` — hanya permintaan yang ditugaskan ke dia).
 *  · Admin Sample → antrean pesanan sample (SOS) per tahap + menunggu persetujuan bayar
 *                   (sumber: `GET /sample-orders/desk` — antrean yang sama dengan Meja Admin Sample).
 * Peran lain tetap memakai panel lama (`KpiPanel` di MobileOpsApp).
 */
import { useEffect, useState } from "react";
import { ChevronRight, Loader2 } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { roleIs } from "../../config/roles";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { apiErrorText } from "../../utils/apiError";

/** Jenis ringkasan untuk peran ini — "" = pakai panel umum. */
export function roleSummaryKind(role) {
  if (roleIs(role, ["designer"])) return "designer";
  if (roleIs(role, ["sample_admin"])) return "sample_admin";
  return "";
}

/** Kartu angka desainer dari `summary` permintaan desain (server). Kunci yang tak dikirim server lama dilewati. */
export function designerTiles(s = {}) {
  const days = Number(s.due_soon_days) || 3;
  return [
    { key: "open", label: "DSR berjalan", value: s.open, unit: "permintaan",
      hint: "Ditugaskan ke Anda dan belum ACC/batal" },
    { key: "overdue", label: "Lewat tenggat", value: s.overdue, unit: "permintaan", tone: Number(s.overdue) > 0 ? "danger" : "" },
    { key: "due_soon", label: `Tenggat ≤ ${days} hari`, value: s.due_soon, unit: "permintaan",
      tone: Number(s.due_soon) > 0 ? "warning" : "" },
    { key: "revision", label: "Revisi menunggu", value: s.revision, unit: "permintaan",
      hint: "Diminta revisi — giliran Anda", tone: Number(s.revision) > 0 ? "warning" : "" },
    { key: "delivered", label: "Menunggu keputusan", value: s.delivered, unit: "permintaan",
      hint: "Hasil sudah diserahkan, menunggu ACC/revisi" },
  ].filter((t) => t.value !== undefined && t.value !== null);
}

// Label pendek antrean Meja Admin Sample (server mengirim kalimat panjang; id antrean = sumber yang sama).
const SAMPLE_QUEUE_LABEL = {
  bayar_sampel: "Menunggu persetujuan bayar",
  siap_gudang: "Siap diteruskan ke gudang",
  di_gudang: "Dipotong / disiapkan gudang",
  kirim_ambil: "Dikirim / siap diambil",
  selesai: "Selesai (7 hari)",
};

/** Kartu angka Admin Sample dari `queues` Meja Admin Sample (server). */
export function sampleAdminTiles(desk = {}) {
  return (desk.queues || []).map((q) => ({
    key: q.id,
    label: SAMPLE_QUEUE_LABEL[q.id] || q.label,
    value: Number(q.count) || 0,
    unit: "pesanan",
    hint: q.id === "bayar_sampel" && Number(q.total_value) > 0 ? `Nilai ${formatCurrency(q.total_value)}` : "",
    tone: q.id === "bayar_sampel" && Number(q.count) > 0 ? "warning" : "",
  }));
}

const TONE = { danger: "text-[#C0392B]", warning: "text-[#B25E00]" };

const SOURCE = {
  designer: {
    url: "/design-requests", params: { mine: true, page: 1, page_size: 1 }, pick: (d) => d?.summary || {},
    tiles: designerTiles, title: "Pekerjaan desain saya",
    caption: "Sumber: Permintaan Desain (DSR) yang ditugaskan ke Anda, di badan usaha yang Anda pegang.",
    open: ["designer-hub", "design-requests"], openLabel: "Buka Permintaan Desain",
  },
  sample_admin: {
    url: "/sample-orders/desk", params: {}, pick: (d) => d || {},
    tiles: sampleAdminTiles, title: "Antrean pesanan sample (SOS)",
    caption: "Sumber: Meja Admin Sample — antrean per tahap yang sama dengan layar desktop.",
    open: ["sample-admin-desk", "sample-admin-desk"], openLabel: "Buka Meja Admin Sample",
  },
};

export default function MobileRoleSummary({ kind, selectedEntity, onOpen, desktop }) {
  const src = SOURCE[kind];
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!src) return;
    const params = { ...src.params, ...(selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {}) };
    axios.get(`${API}${src.url}`, { params })
      .then((r) => { setData(src.pick(r.data)); setErr(""); })
      .catch((e) => { setData({}); setErr(apiErrorText(e, "Ringkasan tidak bisa dimuat.")); });
  }, [src, selectedEntity]);
  if (!src) return null;
  if (!data) return <div className="p-6 text-center text-sm"><Loader2 className="animate-spin inline" size={16} /> Memuat…</div>;
  const tiles = src.tiles(data);
  return (
    <>
      <div className="px-4 pt-3 text-[12px] font-semibold uppercase tracking-wide text-[#6E6E73]" data-testid="mo-role-kpi-title">{src.title}</div>
      {err && <div className="notice-bar warning m-3 text-xs" data-testid="mo-role-kpi-error">{err}</div>}
      {tiles.length ? (
        <div className="grid grid-cols-2 gap-2 p-3" data-testid={`mo-role-kpi-${kind}`}>
          {tiles.map((t) => (
            <div key={t.key} className="m-card p-3" data-testid={`mo-role-kpi-${t.key}`}>
              <div className="text-[11px] text-[#6E6E73]">{t.label}</div>
              <div className={`text-xl font-bold tabular-nums ${TONE[t.tone] || ""}`}>
                {formatQty(t.value)}<span className="ml-1 text-[11px] font-semibold text-[#6E6E73]">{t.unit}</span>
              </div>
              {t.hint && <div className="mt-0.5 text-[11px] text-[#6E6E73]">{t.hint}</div>}
            </div>
          ))}
        </div>
      ) : !err && <div className="p-8 text-center text-sm text-[#6E6E73]" data-testid="mo-role-kpi-empty">Belum ada angka pekerjaan untuk ditampilkan.</div>}
      <p className="px-4 text-[11px] text-[#6E6E73]" data-testid="mo-role-kpi-source">{src.caption}</p>
      {onOpen && (
        <div className="px-3 pt-2">
          <button type="button" className="secondary-button w-full justify-center" data-testid="mo-role-kpi-open"
            onClick={() => onOpen(src.open[0], src.open[1])}>
            {src.openLabel} <ChevronRight size={14} />
          </button>
        </div>
      )}
      {desktop}
    </>
  );
}
