import TransferManagement from "../wms/TransferManagement";

/**
 * Transfer Antar-Entitas (Sub-fase 1.5 — Inter-Company Transfer Flow, KN_15 §7).
 *
 * Fase 3 · P5 — D-16: daftar antar-PT tersendiri (kartu ungu + tombol "Setujui & pindahkan kepemilikan" bergaya
 * lain) DILEBUR ke satu daftar Transfer di Operasi Gudang. Transfer antar-PT dulu tampil dua kali (di sini dan di
 * daftar antar gudang). Berkas ini kini pembungkus tipis untuk rute cadangan `interco-transfers` (deep link lama,
 * notifikasi, papan): daftar yang SAMA dengan saringan Jenis "Antar PT". Setujui/Tolak ada di pop-up rincian
 * (`TransferDetailModal`, izin `transfer.approve`/`transfer.reject`; server tetap penjaga terakhir).
 */
export default function InterCompanyTransfers({ currentUser = {} }) {
  return (
    <div data-testid="interco-transfers-view" className="section-card">
      <div className="section-body">
        <TransferManagement user={currentUser} initialKind="inter_entity" />
      </div>
    </div>
  );
}
