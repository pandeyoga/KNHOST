import axios, { API } from "../../services/apiClient";

export const internalPriceAccess = () => axios.get(`${API}/interco/prices/access`).then((r) => r.data);
export const internalPriceSummary = () => axios.get(`${API}/interco/prices/summary`).then((r) => r.data);
export const internalPriceMissing = (params) => axios.get(`${API}/interco/prices/missing`, { params }).then((r) => r.data);
export const internalPriceBulk = (body) => axios.post(`${API}/interco/prices/bulk`, body).then((r) => r.data);
export const internalPriceRequest = (body) => axios.post(`${API}/interco/prices/request`, body).then((r) => r.data);
