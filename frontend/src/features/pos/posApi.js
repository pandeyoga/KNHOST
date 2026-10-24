import { useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";

/** F-4b — POS advanced recommendation API helpers (dihitung dari histori sales_orders).
 *  UAT 24 Okt (P12) — terlaris berjendela waktu & disaring untuk pelanggan aktif; unggulan; rekomendasi per pelanggan. */
export async function fetchBestSellers(entityId, limit = 10, customerId = "") {
  const { data } = await axios.get(`${API}/pos/best-sellers`, { params: { entity_id: entityId || undefined, limit, customer_id: customerId || undefined } });
  return Array.isArray(data) ? data : [];
}

export async function fetchFeatured(entityId, customerId = "", limit = 12) {
  const { data } = await axios.get(`${API}/pos/featured`, { params: { entity_id: entityId || undefined, customer_id: customerId || undefined, limit } });
  return Array.isArray(data) ? data : [];
}

export async function fetchRecommendations(customerId, entityId, limit = 10) {
  if (!customerId) return [];
  const { data } = await axios.get(`${API}/pos/recommendations`, { params: { customer_id: customerId, entity_id: entityId || undefined, limit } });
  return Array.isArray(data) ? data : [];
}

const HL_DEFAULT = { best_sellers: { enabled: true, window_days: 90 }, reorder: { enabled: true }, fbt: { enabled: true },
  featured: { enabled: true }, recommendation: { enabled: true } };
const hlCache = new Map();

/** Sorotan POS mana yang menyala untuk PT ini (Pusat Pengaturan › Tampilan, kunci `pos.*`). */
export function usePosHighlights(entityId) {
  const key = entityId || "";
  const [cfg, setCfg] = useState(hlCache.get(key) || HL_DEFAULT);
  useEffect(() => {
    let on = true;
    axios.get(`${API}/pos/highlights-config`, { params: { entity_id: entityId && entityId !== "all" ? entityId : undefined } })
      .then((r) => { hlCache.set(key, r.data); if (on) setCfg(r.data); }).catch(() => {});
    return () => { on = false; };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return cfg;
}

export async function fetchFrequentlyBoughtTogether(productId, entityId, limit = 6) {
  if (!productId) return [];
  const { data } = await axios.get(`${API}/pos/frequently-bought-together`, { params: { product_id: productId, entity_id: entityId || undefined, limit } });
  return Array.isArray(data) ? data : [];
}

export async function fetchSubstitutes(productId, entityId, limit = 6) {
  if (!productId) return [];
  const { data } = await axios.get(`${API}/pos/substitutes`, { params: { product_id: productId, entity_id: entityId || undefined, limit } });
  return Array.isArray(data) ? data : [];
}

/** Normalisasi baris rekomendasi -> objek product yang dipahami addToCart(). */
export function recToProduct(r) {
  return {
    id: r.product_id,
    name: r.product_name,
    sku: r.sku,
    price: r.price,
    image: r.image,
    base_unit: r.base_unit,
    category: r.category,
    color: r.color,
    grade: r.grade,
    available_qty: r.available_qty,
  };
}
