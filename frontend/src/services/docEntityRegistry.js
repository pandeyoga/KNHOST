/**
 * FIX-1 (audit WMS-RFID 9 Nov · K-B1-02, B2a D1) — registri "id dokumen → PT dokumen" untuk daftar pekerjaan fisik
 * LINTAS PT (tugas gudang, Putaway Order, transfer, opname, kedatangan). Daftar memanggil `rememberDocEntities(rows)`;
 * interseptor `apiClient` memakai `docEntityFor(url)` supaya aksi & detail dokumen dikirim atas nama PT dokumennya.
 * Modul murni (tanpa axios) — aman dipakai komponen yang diuji dengan apiClient tiruan. Dikosongkan saat logout.
 */
const docEntities = new Map();
const MAX_DOC_ENTITIES = 5000;

export const allowedEntityIds = () => {
  try { return JSON.parse(localStorage.getItem("kn_entity_ctx") || "null")?.allowed_entity_ids || []; } catch { return []; }
};

export const docEntityOf = (r) => (r && (r.work_entity_id || r.owner_entity_id || r.entity_id)) || "";

export function rememberDocEntities(rows, pick = docEntityOf, idOf = (r) => r?.id) {
  (Array.isArray(rows) ? rows : []).forEach((r) => {
    const id = idOf(r); const ent = pick(r);
    if (id && ent) docEntities.set(String(id), String(ent));
  });
  while (docEntities.size > MAX_DOC_ENTITIES) docEntities.delete(docEntities.keys().next().value);
  return rows;
}

export const forgetDocEntities = () => docEntities.clear();

export function docEntityFor(url) {
  if (!docEntities.size) return "";
  const path = String(url || "").split("?")[0];
  for (const seg of path.split("/")) {
    const ent = seg && docEntities.get(seg);
    if (ent) return ent;
  }
  return "";
}
