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
export function notifDocTarget(n) {
  const d = n?.doc;
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
