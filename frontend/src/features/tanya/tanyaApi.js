import axios, { API } from "../../services/apiClient";

export const fetchStatus = () => axios.get(`${API}/ai/status`).then((r) => r.data);
export const fetchTemplates = () => axios.get(`${API}/ai/templates`).then((r) => r.data);
export const runTemplate = (id, params) =>
  axios.post(`${API}/ai/templates/${id}/run`, { params }).then((r) => r.data);
export const fetchResult = (id) => axios.get(`${API}/ai/results/${id}`).then((r) => r.data);
export const sendFeedback = (payload) => axios.post(`${API}/ai/feedback`, payload).then((r) => r.data);
export const fetchSessions = (q = "") =>
  axios.get(`${API}/ai/sessions`, { params: { q } }).then((r) => (Array.isArray(r.data) ? r.data : []));
export const fetchSession = (id) => axios.get(`${API}/ai/sessions/${id}`).then((r) => r.data);
export const deleteSession = (id) => axios.delete(`${API}/ai/sessions/${id}`).then((r) => r.data);
export const fetchNarrative = (templateId, resultIds) =>
  axios.post(`${API}/ai/narrative`, { template_id: templateId, result_ids: resultIds }).then((r) => r.data);
export const fetchMyTemplates = () => axios.get(`${API}/ai/my-templates`).then((r) => (Array.isArray(r.data) ? r.data : []));
export const createMyTemplate = (body) => axios.post(`${API}/ai/my-templates`, body).then((r) => r.data);
export const deleteMyTemplate = (id) => axios.delete(`${API}/ai/my-templates/${id}`).then((r) => r.data);
export const fetchSchedules = () => axios.get(`${API}/ai/schedules`).then((r) => (Array.isArray(r.data) ? r.data : []));
export const createSchedule = (body) => axios.post(`${API}/ai/schedules`, body).then((r) => r.data);
export const updateSchedule = (id, body) => axios.patch(`${API}/ai/schedules/${id}`, body).then((r) => r.data);
export const deleteSchedule = (id) => axios.delete(`${API}/ai/schedules/${id}`).then((r) => r.data);
export const runScheduleNow = (id) => axios.post(`${API}/ai/schedules/${id}/run`).then((r) => r.data);
export const fetchScheduleRuns = () => axios.get(`${API}/ai/schedule-runs`).then((r) => (Array.isArray(r.data) ? r.data : []));
export const fetchScheduleRun = (id) => axios.get(`${API}/ai/schedule-runs/${id}`).then((r) => r.data);

function saveBlob(data, title) {
  const url = URL.createObjectURL(new Blob([data]));
  const a = document.createElement("a");
  a.href = url;
  a.download = `${(title || "tanya-kn").replace(/[^\w-]+/g, "-").toLowerCase()}.xlsx`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function downloadXlsx(resultId, title) {
  const res = await axios.get(`${API}/ai/results/${resultId}/export.xlsx`, { responseType: "blob" });
  saveBlob(res.data, title);
}

/** Seluruh jawaban (semua tabel/grafik) → satu file Excel, satu sheet per hasil. */
export async function downloadAnswerXlsx(resultIds, title) {
  const res = await axios.get(`${API}/ai/export.xlsx`, { params: { ids: resultIds.join(",") }, responseType: "blob" });
  saveBlob(res.data, title);
}

function parseEvents(text) {
  return text
    .split("\n\n")
    .filter((c) => c.startsWith("data: "))
    .map((c) => {
      try { return JSON.parse(c.slice(6)); } catch { return null; }
    })
    .filter(Boolean);
}

/** Pesan galat chat yang jelas: body galat berupa TEKS (responseType text) → urai JSON {detail}, atau sebut kode HTTP. */
export function chatErrorText(e) {
  const res = e?.response;
  if (!res) return e?.code === "ECONNABORTED" ? "Waktu habis menunggu jawaban server." : "Tidak ada respons dari server (koneksi/proxy terputus).";
  let body = res.data;
  if (typeof body === "string") { try { body = JSON.parse(body); } catch { /* teks biasa */ } }
  const detail = typeof body === "object" && body ? body.detail : String(body || "").replace(/<[^>]+>/g, " ").trim().slice(0, 160);
  return `HTTP ${res.status}${detail ? ` — ${typeof detail === "string" ? detail : JSON.stringify(detail)}` : ""}`;
}

/** Chat SSE lewat XHR axios (tanpa fetch mentah) — hanya potongan baru yang diurai, event diteruskan bertahap. */
export async function askChat(payload, onEvent) {
  let offset = 0;
  const consume = (txt, final) => {
    const cut = txt.lastIndexOf("\n\n");
    const end = final ? txt.length : cut < 0 ? 0 : cut + 2;
    if (end <= offset) return;
    parseEvents(txt.slice(offset, end)).forEach(onEvent);
    offset = end;
  };
  const res = await axios.post(`${API}/ai/chat`, payload, {
    responseType: "text",
    onDownloadProgress: (e) => consume(e.event?.target?.responseText || "", false),
  });
  consume(typeof res.data === "string" ? res.data : "", true);
}

export const fetchUsageDaily = (params) => axios.get(`${API}/ai/usage/daily`, { params }).then((r) => r.data);
export const fetchAction = (id) => axios.get(`${API}/ai/actions/${id}`).then((r) => r.data);
export const confirmAction = (id, edits) => axios.post(`${API}/ai/actions/${id}/confirm`, { edits }).then((r) => r.data);
export const dismissAction = (id) => axios.post(`${API}/ai/actions/${id}/dismiss`).then((r) => r.data);
export const fetchInsights = () => axios.get(`${API}/ai/insights`).then((r) => (Array.isArray(r.data) ? r.data : []));
export const scanInsights = () => axios.post(`${API}/ai/insights/scan`).then((r) => r.data);
