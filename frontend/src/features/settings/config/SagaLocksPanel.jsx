/**
 * SagaLocksPanel — kunci saga (`saga_lock`) yang MENGGANTUNG (T-01 Opsi B, INV-ATOMIC-01).
 * Sebuah aksi multi-koleksi diklaim lalu mati di tengah → dokumennya terkunci: aksi ulang
 * ditolak 409 supaya tidak menulis dua kali. Admin memeriksa data hilir lalu melepas kunci.
 */
import { useCallback, useEffect, useState } from "react";
import { Lock, LockOpen, Loader2, RefreshCw, ShieldCheck } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import ErrorNotice from "../../../components/ErrorNotice";
import { notifySuccess } from "../../../utils/feedback";
import { askReason } from "../../../services/confirmService";
import { errMsg } from "./configApi";

const COLL_LABEL = {
  wms_tasks: "Tugas gudang", sales_orders: "Pesanan penjualan", warehouse_transfers: "Transfer gudang",
  cycle_count_sessions: "Stock opname", purchase_returns: "Retur Pembelian", sales_returns: "Retur Penjualan",
  putaway_orders: "Perintah putaway", vendor_bills: "Tagihan supplier",
  payment_variance_decisions: "Keputusan selisih bayar", ar_receipts: "Kwitansi pembayaran", sample_requests: "Permintaan sampel", crm_leads: "Prospek (lead)", period_closings: "Tutup buku periode",
  product_categories: "Kategori produk", special_orders: "Pesanan khusus", esign_requests: "Permintaan tanda tangan", tax_invoices_in: "Faktur pajak masukan", landed_cost_vouchers: "Voucher landed cost",
  makloon_orders: "Order makloon", rfid_verify_sessions: "Sesi verifikasi RFID", product_templates: "Template produk", rfqs: "RFQ", products: "Produk", business_entities: "Badan usaha",
};

export default function SagaLocksPanel() {
  const [rows, setRows] = useState(null);
  const [busy, setBusy] = useState(false);
  const [releasing, setReleasing] = useState("");
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setBusy(true); setErr("");
    try {
      const { data } = await axios.get(`${API}/saga-locks`);
      setRows(Array.isArray(data) ? data : []);
    } catch (e) { setErr(errMsg(e, "Gagal memuat kunci saga.")); }
    finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const release = async (r) => {
    const key = `${r.collection}/${r.id}`;
    setReleasing(key); setErr("");
    try {
      // GN-11 — periksa dulu: kunci masih aktif? efek apa yang sudah terposting?
      const { data: ins } = await axios.get(`${API}/saga-locks/${r.collection}/${r.id}/inspect`);
      if (ins.active) { setErr("Kunci masih aktif (proses mungkin masih berjalan) — tunggu 5 menit atau sampai tercatat gagal."); return; }
      const fx = ins.effects || [];
      const reason = await askReason({
        title: `Lepas kunci "${r.saga_lock?.action}" pada ${r.id}?`,
        message: fx.length
          ? `EFEK SUDAH TERPOSTING: ${fx.map((e) => `${e.count} ${e.collection} (${e.samples.join(", ")})`).join(" · ")}. Aksi ulang bisa menggandakan — lanjut hanya bila sudah dikompensasi/diperiksa.`
          : "Tidak ditemukan efek hilir sesudah kunci diklaim. Aksi dapat dijalankan ulang sesudah kunci dilepas.",
        reasonLabel: "Alasan pelepasan (min. 10 karakter)", reasonRequired: true, reasonMinLength: 10,
        confirmLabel: fx.length ? "Saya sudah memeriksa — lepas" : "Lepas kunci", danger: fx.length > 0,
        testId: "saga-lock-release-confirm",
      });
      if (reason === null) return;
      await axios.post(`${API}/saga-locks/${r.collection}/${r.id}/release`,
        { reason, acknowledge_effects: fx.length > 0, lock_token: ins.lock?.token });
      notifySuccess("Kunci dilepas", `${r.id} dapat diproses ulang.`);
      load();
    } catch (e) { setErr(errMsg(e, "Gagal melepas kunci.")); }
    finally { setReleasing(""); }
  };

  const n = rows?.length || 0;
  return (
    <section className="cfg-health" data-testid="saga-locks-panel">
      <ErrorNotice message={err} onRetry={load} />
      <div className={`cfg-health-verdict ${n ? "bad" : "good"}`} data-testid="saga-locks-verdict">
        {n ? <Lock size={20} /> : <ShieldCheck size={20} />}
        <div>
          <h3>{n ? `${n} kunci saga menggantung` : "Tidak ada kunci saga yang menggantung"}</h3>
          <p>
            Aksi multi-koleksi (selesaikan GR, batalkan SO, setujui transfer, reversal retur, …) diklaim
            dulu lalu dicabut saat selesai. Kunci yang tersisa berarti prosesnya mati di tengah: aksi ulang
            ditolak 409 agar tidak menulis dua kali. Periksa data hilir, lalu lepas kunci bila aman.
          </p>
        </div>
        <button className="btn-secondary btn-sm" onClick={load} disabled={busy} data-testid="saga-locks-refresh">
          {busy ? <Loader2 size={13} className="spin" /> : <RefreshCw size={13} />} Periksa ulang
        </button>
      </div>

      {rows && n > 0 ? (
        <table className="data-table cfg-health-table" data-testid="saga-locks-table">
          <thead>
            <tr><th>Dokumen</th><th>Aksi</th><th>Diklaim</th><th>Status dokumen</th><th> </th></tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const key = `${r.collection}/${r.id}`;
              const lk = r.saga_lock || {};
              return (
                <tr key={key} data-testid={`saga-lock-row-${r.id}`}>
                  <td><b>{COLL_LABEL[r.collection] || r.collection}</b><br /><code className="cfg-key">{r.id}</code></td>
                  <td>
                    <code className="cfg-key">{lk.action}</code>
                    {lk.error ? <p className="cfg-hint-sm" data-testid={`saga-lock-error-${r.id}`}>Gagal: {lk.error}</p> : null}
                  </td>
                  <td>
                    {lk.started_at ? new Date(lk.started_at).toLocaleString("id-ID") : "—"}
                    {lk.by ? <><br /><span className="cfg-hint-sm">oleh {lk.by}</span></> : null}
                  </td>
                  <td><span className="badge-orange">{r.status || "—"}</span></td>
                  <td>
                    <button className="btn-secondary btn-sm" onClick={() => release(r)}
                      disabled={releasing === key} data-testid={`saga-lock-release-${r.id}`}>
                      {releasing === key ? <Loader2 size={13} className="spin" /> : <LockOpen size={13} />} Lepas kunci
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
