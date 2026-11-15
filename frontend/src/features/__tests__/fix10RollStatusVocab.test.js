/**
 * FIX-10 (audit 9 Nov 2026 B3a SSOT-1) — kosakata status ROLL di FE selaras `backend/services/roll_state.STATUSES`.
 * Gagal di dasar (status `wip` tanpa label ranah roll → jatuh ke kode mentah / label umum), lulus sesudah.
 * Keselarasan penuh registry ⇔ STATUSES ⇔ label FE dikunci di sisi server (`test_fix10_roll_state.py`).
 */
import { DOMAIN_LABELS, statusLabel, statusTone } from "../../utils/statusVocab";

// Salinan kosakata `roll_state.STATUSES` (19 status) — bila server menambah status, uji server memerah lebih dulu.
const ROLL_STATUSES = [
  "receiving", "quarantine", "available", "reserved", "committed", "picked", "packed", "hold", "wip", "blocked",
  "damaged", "in_transit_transfer", "in_transit_sales", "in_transit_inbound", "in_transit_intercompany", "subcon",
  "delivered", "consumed", "returned_supplier",
];

describe("FIX-10 — kosakata status roll", () => {
  test("semua status roll punya label ranah roll (tidak pernah kode mentah)", () => {
    for (const s of ROLL_STATUSES) {
      expect(DOMAIN_LABELS.roll[s]).toBeTruthy();
      expect(statusLabel(s, "roll")).not.toBe(s);
    }
  });

  test("wip = istilah layar yang sudah ada (Stok WIP), nada kategori", () => {
    expect(statusLabel("wip", "roll")).toBe("WIP (Proses)");
    expect(statusTone("wip", "roll")).toBe("special");
  });

  test("`allocated` bukan status roll (status alokasi SO)", () => {
    expect(DOMAIN_LABELS.roll.allocated).toBeUndefined();
  });

  test("istilah lama tidak berubah (K-13)", () => {
    expect(statusLabel("available", "roll")).toBe("Tersedia");
    expect(statusLabel("hold", "roll")).toBe("Ditahan");
    expect(statusLabel("subcon", "roll")).toBe("Di Makloon");
  });
});
