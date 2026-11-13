import axios, { API } from "../../services/apiClient";
import { moneyPost } from "../../utils/moneyRequest";

export const internalPriceAccess = () => axios.get(`${API}/interco/prices/access`).then((r) => r.data);
export const internalPriceSummary = () => axios.get(`${API}/interco/prices/summary`).then((r) => r.data);
export const internalPriceMissing = (params) => axios.get(`${API}/interco/prices/missing`, { params }).then((r) => r.data);
// PK-12 — tulis lewat pintu uang; `key` = Idempotency-Key dari `useIntentKey` pemanggil.
export const internalPriceBulk = (body, key) => moneyPost(`${API}/interco/prices/bulk`, body, key).then((r) => r.data);
export const internalPriceRequest = (body, key) => moneyPost(`${API}/interco/prices/request`, body, key).then((r) => r.data);
