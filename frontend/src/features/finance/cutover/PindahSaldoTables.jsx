/**
 * PindahSaldoTables — Kas & Bank bagian 1 (Tugas 6): tabel pratinjau pindah saldo kas per PT (spesifikasi §5.3 butir 1).
 * Hanya-baca, dari `GET /api/kas-per-rekening/{entity_id}/pratinjau`: per rekening akun tujuan (sub-akun yang akan
 * dibuat atau akun bagan PT pilihan), saldo buku kas, akun asal saldo, selisih; kas lama tanpa rekening; akun kas lama
 * (saldo · dipindah · sisa); baris jurnal yang akan dibuat. Dipakai layar Akun per rekening dan pop-up Setujui.
 *
 * PT yang sudah aktif (`pv.aktif`, tinjauan akhir I1): keadaan SESUDAH pindah — per rekening saldo akun rekening vs
 * saldo buku kasnya (selisih = akun − buku kas, pemeriksa "saldo per rekening = buku kas"), angka yang dipindah saat
 * disetujui; akun kas lama = saldo sekarang. Kolom "Dipindah dari" / "Sisa" (hitungan pindah) tidak dipakai di sana.
 */
import { formatCurrency } from "../../../utils/formatters";
import { jenisKas } from "./cutoverShared";

const rp = (v) => formatCurrency(Number(v) || 0);

export function AkunTujuan({ r }) {
  return (
    <span data-testid={`ps-target-${r.id}`}>
      <span className="font-mono">{r.akun_tujuan}</span>{r.akun_tujuan_nama ? ` · ${r.akun_tujuan_nama}` : ""}
      {r.akun_tujuan_baru && <span className="block text-fs-12 text-kn-text-2">sub-akun baru, dibuat saat disiapkan</span>}
    </span>
  );
}

function DaftarAsal({ asal }) {
  if (!(asal || []).length) return <span className="text-kn-text-2">—</span>;
  return (
    <ul className="grid gap-0.5">
      {asal.map((a) => (
        <li key={a.akun} className="text-fs-12">
          <span className="font-mono">{a.akun}</span>{a.nama ? ` ${a.nama}` : ""} · <span className="tabular-nums">{rp(a.jumlah)}</span>
        </li>
      ))}
    </ul>
  );
}

function SelSelisih({ r, testId }) {
  const selisih = Number(r.selisih) || 0;
  const ada = Math.abs(selisih) >= 0.005;
  return (
    <td className={`text-right tabular-nums ${ada ? "font-semibold text-kn-warning-text" : "text-kn-text-2"}`}
      data-testid={`${testId}-diff-${r.id}`}>
      {ada ? rp(selisih) : "—"}
    </td>
  );
}

export function TabelRekening({ pv, testId = "ps-accounts" }) {
  const rows = pv?.rekening || [];
  if (!rows.length) return <p className="text-fs-13 text-kn-text-2" data-testid={`${testId}-empty`}>PT ini belum punya rekening.</p>;
  const aktif = Boolean(pv?.aktif);
  return (
    <div className="overflow-x-auto">
      <table className="data-table head-wrap w-full" data-testid={testId}>
        <thead>{aktif ? (
          <tr>
            <th>Rekening</th><th>Akun buku besar</th><th className="text-right">Saldo akun</th>
            <th className="text-right">Saldo buku kas</th><th>Dipindah saat disetujui</th>
            <th className="text-right">Selisih akun − buku kas</th>
          </tr>
        ) : (
          <tr>
            <th>Rekening</th><th>Akun buku besar tujuan</th><th className="text-right">Saldo buku kas</th>
            <th>Dipindah dari</th><th className="text-right">Selisih</th>
          </tr>
        )}</thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} data-testid={`${testId}-row-${r.id}`}>
              <td className="min-w-[160px]">
                <span className="font-semibold">{r.nama}</span>
                <span className="block text-fs-12 text-kn-text-2">{jenisKas(r.cash_type)}{r.aktif === false ? " · nonaktif" : ""}</span>
              </td>
              <td className="min-w-[180px]">
                {aktif && !r.akun_tujuan ? <span className="text-kn-text-2" data-testid={`ps-target-${r.id}`}>Belum punya akun rekening</span> : <AkunTujuan r={r} />}
              </td>
              {aktif && <td className="text-right tabular-nums" data-testid={`${testId}-gl-${r.id}`}>{rp(r.saldo_akun_tujuan)}</td>}
              <td className="text-right tabular-nums">{rp(r.saldo_buku)}</td>
              <td className="min-w-[160px]"><DaftarAsal asal={r.asal} /></td>
              <SelSelisih r={r} testId={testId} />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Kas lama tanpa rekening: ikut rekening tunggal jenisnya, atau tetap di akun kas lama (disebut terang-terangan). */
export function KasTanpaRekening({ pv }) {
  const k = pv?.kas_tanpa_rekening || {};
  const tunggal = k.tunggal || [];
  const tetap = Number(k.tetap) || 0;
  if (!tunggal.length && Math.abs(tetap) < 0.005) return null;
  return (
    <ul className="grid gap-1 text-fs-13" data-testid="ps-unlinked">
      {tunggal.map((t) => (
        <li key={t.cash_type} data-testid={`ps-unlinked-sole-${t.cash_type}`}>
          {t.jumlah_kas} kas lama {jenisKas(t.cash_type).toLowerCase()} tanpa rekening ({rp(t.jumlah)}) ikut rekening
          {" "}<b>{t.rekening_nama}</b> — satu-satunya rekening jenis itu; kasnya ditautkan ke rekening itu saat disetujui.
        </li>
      ))}
      {Math.abs(tetap) >= 0.005 && (
        <li data-testid="ps-unlinked-stay">
          <b className="tabular-nums">{rp(tetap)}</b> tetap di akun kas lama — kas lama tanpa rekening
          {(k.tetap_rincian || []).length > 0 && ` (${k.tetap_rincian.map((x) => `${jenisKas(x.cash_type).toLowerCase()} ${rp(x.jumlah)}, ${x.rekening_aktif} rekening aktif`).join("; ")})`}.
        </li>
      )}
    </ul>
  );
}

export function TabelAkunLama({ pv }) {
  const rows = pv?.akun_lama || [];
  if (!rows.length) return null;
  if (pv?.aktif) {
    return (
      <div className="overflow-x-auto">
        <table className="data-table w-full" data-testid="ps-old-accounts">
          <thead><tr><th>Akun kas lama</th><th className="text-right">Dipindah saat disetujui</th>
            <th className="text-right">Saldo sekarang</th></tr></thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.akun} data-testid={`ps-old-${a.akun}`}>
                <td><span className="font-mono">{a.akun}</span>{a.nama ? ` · ${a.nama}` : ""}</td>
                <td className="text-right tabular-nums">{rp(a.dipindah)}</td>
                <td className="text-right tabular-nums">{rp(a.saldo)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-1 text-fs-12 text-kn-text-2">Saldo sekarang = kas yang dicatat tanpa dokumen kas rekening dan kas
          lama tanpa rekening; tetap di akun lama.</p>
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="data-table w-full" data-testid="ps-old-accounts">
        <thead><tr><th>Akun kas lama</th><th className="text-right">Saldo</th><th className="text-right">Dipindah</th>
          <th className="text-right">Sisa</th></tr></thead>
        <tbody>
          {rows.map((a) => (
            <tr key={a.akun} data-testid={`ps-old-${a.akun}`}>
              <td><span className="font-mono">{a.akun}</span>{a.nama ? ` · ${a.nama}` : ""}</td>
              <td className="text-right tabular-nums">{rp(a.saldo)}</td>
              <td className="text-right tabular-nums">{rp(a.dipindah)}</td>
              <td className="text-right tabular-nums">{rp(a.sisa)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-1 text-fs-12 text-kn-text-2">Sisa = kas yang dicatat tanpa dokumen kas rekening; tetap di akun lama.</p>
    </div>
  );
}

export function TabelJurnal({ pv }) {
  const rows = pv?.baris_jurnal || [];
  if (!rows.length) return <p className="text-fs-13 text-kn-text-2" data-testid="ps-journal-empty">Tidak ada saldo yang perlu dipindah.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="data-table w-full" data-testid="ps-journal">
        <thead><tr><th>Akun</th><th>Keterangan</th><th className="text-right">Debit</th><th className="text-right">Kredit</th></tr></thead>
        <tbody>
          {rows.map((b, i) => (
            <tr key={`${b.account_code}-${i}`}>
              <td className="whitespace-nowrap"><span className="font-mono">{b.account_code}</span>{b.account_name ? ` · ${b.account_name}` : ""}</td>
              <td className="text-fs-12 text-kn-text-2">{b.description}</td>
              <td className="text-right tabular-nums">{b.debit ? rp(b.debit) : ""}</td>
              <td className="text-right tabular-nums">{b.credit ? rp(b.credit) : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
