/**
 * notifDocTarget — buka DOKUMEN yang dituju notifikasi, bukan hanya layarnya (fase 4 · R6, G5-09).
 *
 * Server kini menambahkan `doc = { ref_type, ref_id, number, label }` pada notifikasi yang dokumennya bisa
 * dikenali (nota kredit batal item → SO yang dikoreksi; notifikasi desain → rincian desain). Bentuknya sama dengan
 * hasil `/documents/resolve`, jadi tujuan layarnya memakai peta yang sudah ada (`docLinkTarget`); desain dibuka
 * lewat kanal R&D (`openRnd`) karena layar Desain & Pattern menerima fokus dari sana.
 *
 * Dipakai penangan klik notifikasi (desktop: `App.js` onNavigate; HP: lembar notifikasi):
 *   if (openNotifDocument(n, openDocument)) return;   // dokumen dibuka
 *   navigateTo(n.link);                                // selain itu: layar saja, seperti dulu
 */
import { docLinkTarget } from "../sales_admin/workDeskApi";
import { openRnd } from "../rnd/rndDeepLink";

/** { link } untuk `openDocument`, { rnd } untuk `openRnd`, atau null bila notifikasi tak menunjuk dokumen. */
// Notifikasi Lapor Bayar (LB-T3..T5) membawa `link = "/?view=orders&id=<id pesanan>"` — bukan id layar, jadi dibaca sebagai
// dokumen pesanan (rincian pesanan tempat Lapor bayar / Terima / Tolak berada).
const LINK_PESANAN = /^\/?\?(?:[^#]*&)?view=orders&(?:[^#]*&)?id=([^&#]+)/;
// F1 — notifikasi tanpa dokumen yang menunjuk LAYAR (bukan id layar polos): ringkasan impor mutasi → Meja Keuangan
// (antrean "Mutasi berkode perlu dicek"). `bayar_masuk_mutasi` membawa tautan pesanan (`LINK_PESANAN`) seperti Lapor Bayar.
const LAYAR_JENIS = { ringkasan_mutasi_otomatis: "finance-desk" };
// Kas & Bank 2 (Tugas 4) — pengajuan kas keluar diajukan/diputus. Server melampirkan `doc` (`notification_doc_ref`); bila
// tidak (lookup gagal), id pengajuan diambil dari `ref` (`<id>` · `<id>:<hasil>`, tanpa akhiran `#<penerima>`).
// Kas & Bank 3 (Tugas 4b) — opname kas menunggu keputusan / diputus → opnamenya (`ref` = `<id>#…` · `<id>:<hasil>#…`).
const JENIS_PENGAJUAN_KAS = { kas_keluar_diajukan: "cash_out_request", kas_keluar_diputus: "cash_out_request",
  opname_kas_menunggu: "cash_count", opname_kas_diputus: "cash_count" };
const idDariRef = (ref) => String(ref || "").split("#", 1)[0].split(":", 1)[0];

export function notifDocTarget(n) {
  if (!n?.doc && LAYAR_JENIS[n?.type]) return { link: { view: LAYAR_JENIS[n.type] } };
  let d = n?.doc;
  if (!d && typeof n?.link === "string") {
    const m = LINK_PESANAN.exec(n.link);
    if (m) d = { ref_type: "sales_order", ref_id: decodeURIComponent(m[1]), number: "" };
  }
  if (!d && JENIS_PENGAJUAN_KAS[n?.type] && idDariRef(n.ref)) {
    d = { ref_type: JENIS_PENGAJUAN_KAS[n.type], ref_id: idDariRef(n.ref), number: "" };
  }
  if (!d || !d.ref_id || !d.ref_type) return null;
  if (d.ref_type === "design") return { rnd: { view: "rnd-designs", designId: d.ref_id } };
  const link = docLinkTarget(d);
  return link ? { link } : null;
}

/** Buka dokumennya bila bisa. true = sudah ditangani (pemanggil tidak perlu navigasi ke layar). */
export function openNotifDocument(n, openDocument) {
  const t = notifDocTarget(n);
  if (!t) return false;
  if (t.rnd) { openRnd(t.rnd); return true; }
  if (typeof openDocument !== "function") return false;
  openDocument(t.link);
  return true;
}
