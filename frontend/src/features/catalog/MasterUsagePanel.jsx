import { useCallback, useEffect, useState } from "react";
import { Link2 } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { askConfirm } from "../../services/confirmService";
import { HelpTip } from "../../components/ListPageParts";

/**
 * P01 IMP-14 — dipakai di mana + kebijakan hapus master (Admin/MD; hanya bila belum dipakai).
 *
 * Pola UI 16 Nov (M22): dulu satu blok di tengah rincian SKU berisi "Dipakai di", teks kebijakan panjang ("boleh dihapus
 * permanen oleh pemegang akses …"), dan tombol merah "Hapus permanen". Kini dipecah:
 *  · `useMasterUsage` — data pemakaian + aksi hapus (dipanggil kepala rincian untuk butir menu "Lainnya");
 *  · `MasterUsageLine` — SATU baris kecil "Dipakai di: …"; teks kebijakan pindah ke ikon "?".
 */
export function useMasterUsage(kind, id, enabled = true) {
  const [info, setInfo] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    setInfo(null); setErr("");
    if (enabled && id) axios.get(`${API}/master/usage/${kind}/${id}`).then((r) => setInfo(r.data)).catch((e) => setErr(e?.response?.data?.detail || "Gagal memuat jejak pemakaian."));
  }, [kind, id, enabled]);
  const purge = useCallback(async (onPurged) => {
    if (!info) return;
    if (!await askConfirm({ title: "Hapus permanen?", message: `${info.name} belum pernah dipakai dan akan dihapus permanen.`, confirmLabel: "Hapus", danger: true })) return;
    try { await axios.delete(`${API}/master/${kind}/${id}/purge`); onPurged?.(); }
    catch (e) { const d = e?.response?.data?.detail; setErr(typeof d === "object" ? d.message : d || "Gagal menghapus."); }
  }, [info, kind, id]);
  return { info, err, purge };
}

export function MasterUsageLine({ kind, info, err }) {
  if (err) return <p data-testid={`master-usage-error-${kind}`} className="mt-1 text-fs-12 text-kn-danger-text">{err}</p>;
  if (!info) return null;
  return (
    <p data-testid={`master-usage-${kind}`} className="mt-1 flex flex-wrap items-center gap-x-2 text-fs-12 text-kn-text-2">
      <span className="inline-flex items-center gap-1 font-semibold text-kn-neutral"><Link2 size={12} aria-hidden="true" />Dipakai di:</span>
      {info.refs.length ? info.refs.map((r) => <span key={r.collection} data-testid={`master-usage-ref-${r.collection}`}>{r.label} <b className="text-kn-text">{r.count}</b></span>)
        : <span data-testid="master-usage-none">belum dipakai</span>}
      <HelpTip text={info.policy} testId="master-usage-policy" label="Kebijakan hapus master" />
    </p>
  );
}
