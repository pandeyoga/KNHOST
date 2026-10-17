import axios, { API } from "../../services/apiClient";

export const listSampleOrders = (params = {}) => axios.get(`${API}/sample-orders`, { params }).then((r) => r.data);
export const sampleStats = (params = {}) => axios.get(`${API}/sample-orders/stats/summary`, { params }).then((r) => r.data);
export const sampleDesk = (params = {}) => axios.get(`${API}/sample-orders/desk`, { params }).then((r) => r.data);
export const approveSamplePayment = (id, note = "") => axios.post(`${API}/sample-orders/${id}/approve-payment`, { note }).then((r) => r.data);
export const confirmSampleOrder = (id) => axios.post(`${API}/sample-orders/${id}/confirm`).then((r) => r.data);
export const cancelSampleOrder = (id, note = "") => axios.post(`${API}/sample-orders/${id}/cancel`, { note }).then((r) => r.data);
// L06 — catalogue, Meja Cutting & kemampuan lokasi
export const cataloguePreview = (params) => axios.get(`${API}/sample-orders/catalogue/preview`, { params }).then((r) => r.data);
export const changeCatalogueSoft = (id, product_id) => axios.post(`${API}/sample-orders/${id}/catalogue/soft`, { product_id }).then((r) => r.data);
export const cuttingDesk = (params = {}) => axios.get(`${API}/cutting/desk`, { params }).then((r) => r.data);
export const receiveCut = (taskId, to_warehouse_id = "") => axios.post(`${API}/cutting/tasks/${taskId}/receive`, { to_warehouse_id }).then((r) => r.data);
export const cuttingLocations = () => axios.get(`${API}/cutting/locations`).then((r) => r.data);
export const setCuttingCaps = (wid, caps) => axios.put(`${API}/cutting/locations/${wid}`, { caps }).then((r) => r.data);
export const createCatalogueOrder = (payload) => axios.post(`${API}/sales-orders`, payload).then((r) => r.data);
