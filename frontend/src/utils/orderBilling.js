// PK-32 (K-14) — NILAI TAGIHAN pesanan = grand total + Σ tagihan tambahan nota debit (`extra_billing_lines[].gross`).
// Sama dengan server (`customer_service._order_grand_total`): `grand_total` dan `items[]` pesanan tidak pernah diubah
// nota; tagihan tambahan berdiri sendiri. Dipakai kepala rincian pesanan, sisa tagihan, dan jadwal bayar.
export function extraBillingLines(order) {
  return Array.isArray(order?.extra_billing_lines) ? order.extra_billing_lines.filter(Boolean) : [];
}

export function extraBillingTotal(order) {
  return extraBillingLines(order).reduce((s, x) => s + Number(x?.gross || 0), 0);
}

export function billingTotal(order) {
  const base = Number(order?.grand_total ?? order?.total_amount ?? 0);
  return base + extraBillingTotal(order);
}
