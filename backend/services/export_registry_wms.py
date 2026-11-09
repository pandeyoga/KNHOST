"""FIX-4 (audit WMS-RFID 9 Nov 2026 · EXP-01/EXP-05 · K-B4-07 · K-B3b-04) — dataset Pusat Export untuk dokumen
WMS-RFID yang dulu belum terpetakan, supaya setiap daftar gudang bisa diunduh Excel/CSV lewat SATU mesin (Pusat Export)
dengan saringan & cakupan pengguna.

Aturan dataset di berkas ini:
  * izin dataset = izin LIHAT layar daftarnya (mis. `wms.view` untuk RFID) — ekspor tidak pernah melebihi daftar;
  * kolom id mentah hanya sebagai kolom SARINGAN (`default=False`, EXP-04) — berkas bawaan memakai nama/nomor;
  * `shared=True` = koleksi tanpa pemilik PT (perangkat, lintasan gerbang): cakupan baris = lokasi saja (= daftarnya);
  * `location_fields` = field gudang untuk koleksi yang TIDAK ada di `location_scope.WAREHOUSE_FIELDS` (pagar keras
    petugas berpagar + saringan tampilan lokasi diterapkan mesin export, sama dengan daftarnya).

Antrean periksa gate V2 (`rfid_v2_reviews`) SENGAJA belum dipetakan: hak lihat per kasus diperiksa per dokumen sumber
(`rfid_v2_review._case_access`) dan tidak bisa dinyatakan sebagai saringan kueri tanpa keputusan cakupan baru (sisa FIX-4).
"""
from typing import Any, Dict, List

from services.export_registry import C, ENTITY_JOIN, WAREHOUSE_JOIN
from services.export_registry_more import S

WMS = ("wms", "view")

WMS_RFID: List[Dict[str, Any]] = [
    S("putaway_orders", "Perintah Simpan ke Rak (PA)", "Gudang & Logistik", "putaway_orders", WMS,
      "pa_number:No. PA|status:Status|from_warehouse_name:Gudang asal|to_warehouse_name:Gudang tujuan|item_count:Jumlah roll:n"
      "|total_qty:Total qty:n|btg_number:No. BTG|arrived_count:Roll tiba:n|exception_count:Pengecualian:n"
      "|created_at:Dibuat:t|created_by:Dibuat oleh|dispatched_at:Diberangkatkan:t|confirmed_at:Dikonfirmasi:t"
      "|owner_entity_id:ID badan usaha pemilik",
      "created_at:Tanggal dibuat:t|dispatched_at:Tanggal berangkat:t",
      joins=[ENTITY_JOIN("owner_entity_id")],
      extra=[C("from_warehouse_id", "ID gudang asal (saringan)", default=False),
             C("to_warehouse_id", "ID gudang tujuan (saringan)", default=False)],
      search_fields=["pa_number", "from_warehouse_name", "to_warehouse_name", "btg_number"]),
    S("repair_orders", "Perbaikan Roll (celup/finishing ulang)", "Gudang & Logistik", "repair_orders", ("repair_order", "view"),
      "number:No. perbaikan|kind_label:Jenis|status_label:Status|partner_name:Mitra|cost_estimate:Perkiraan biaya:m"
      "|created_at:Dibuat:t|entity_id:ID badan usaha",
      extra=[C("status", "Kode status", default=False), C("kind", "Kode jenis", default=False)],
      search_fields=["number", "partner_name", "lines.roll_no", "lines.sku"]),   # = repair_order_service.list_orders
    S("rfid_print_jobs", "Job Cetak Label RFID/QR", "Gudang & Logistik", "rfid_print_jobs", WMS,
      "job_number:No. job|kind:Jenis|status:Status|warehouse_name:Gudang|item_count:Jumlah label:n|printed_via:Dicetak lewat"
      "|created_at:Dibuat:t|created_by:Dibuat oleh|printed_at:Dicetak:t|verified_at:Diverifikasi:t"
      "|owner_entity_id:ID badan usaha pemilik",
      joins=[ENTITY_JOIN("owner_entity_id")],
      extra=[C("warehouse_id", "ID gudang (saringan)", default=False)], search_fields=["job_number", "warehouse_name"]),
    S("rfid_incidents", "Insiden RFID (alarm gerbang)", "Gudang & Logistik", "rfid_incidents", WMS,
      "created_at:Pertama:t|last_at:Terakhir:t|epc:EPC|roll_no:No. roll|sku:SKU|product_name:Produk|device_name:Perangkat"
      "|read_type:Jenis baca|reason:Sebab|severity:Tingkat|status:Status|hits:Jumlah kejadian:n|ack_by:Diakui oleh"
      "|resolved_by:Diselesaikan oleh",
      "created_at:Tanggal insiden:t", joins=[WAREHOUSE_JOIN],
      extra=[C("warehouse_id", "ID gudang (saringan)", default=False)],
      location_fields=("warehouse_id",),
      search_fields=["epc", "roll_no", "sku", "product_name", "device_name", "reason"]),
    S("rfid_devices", "Perangkat RFID (reader/gate/printer)", "Gudang & Logistik", "rfid_devices", WMS,
      "code:Kode|name:Nama|type:Jenis|direction:Arah|warehouse_name:Gudang|location:Lokasi|status:Status"
      "|enabled:Aktif:b|last_heartbeat:Detak terakhir:t|created_at:Didaftarkan:t", joins=[],
      extra=[C("warehouse_id", "ID gudang (saringan)", default=False)], location_fields=("warehouse_id",),
      search_fields=["code", "name", "location"], shared=True),
    S("rfid_passages", "Lintasan Gerbang RFID", "Gudang & Logistik", "rfid_passages", WMS,
      "started_at:Mulai:t|last_at:Terakhir:t|device_name:Gerbang|direction:Arah|verdict:Hasil|red_count:Merah:n"
      "|green_count:Hijau:n|info_count:Info:n|acknowledged_at:Diakui:t",
      "started_at:Waktu lintasan:t", joins=[WAREHOUSE_JOIN],
      extra=[C("device_id", "ID perangkat (saringan)", default=False),
             C("warehouse_id", "ID gudang (saringan)", default=False)],
      location_fields=("warehouse_id",), search_fields=["device_name", "epcs"], shared=True),
    S("rfid_cycle_counts", "Opname RFID (hasil)", "Gudang & Logistik", "rfid_cycle_counts", WMS,
      "cc_number:No. opname|warehouse_name:Gudang|expected_count:Diharapkan:n|found_count:Ditemukan:n"
      "|missing_count:Hilang:n|extra_count:Asing/salah lokasi:n|accuracy_pct:Akurasi %:n|simulated:Simulasi:b"
      "|created_at:Selesai:t|created_by:Oleh", "created_at:Tanggal opname:t", joins=[],
      extra=[C("warehouse_id", "ID gudang (saringan)", default=False)], location_fields=("warehouse_id",),
      search_fields=["cc_number", "warehouse_name"], shared=True, scope_all_field="scope_entity_ids"),
]

#: Dataset yang boleh diunduh peran `warehouse` (petugas gudang) — keputusan K-B3b-04: dataset GUDANG yang izin lihatnya
#: ia punya. Daftar putih (bukan per kelompok) supaya dataset bernilai uang/HPP di kelompok gudang (mis. Riwayat Nilai
#: Roll) tidak ikut terbuka hanya karena kelompoknya "Gudang".
WAREHOUSE_ROLE_DATASETS = frozenset({
    "goods_receipts", "wms_tasks", "inventory_rolls", "inventory_movements", "inventory_balances", "inventory_lots",
    "warehouse_transfers", "warehouses", "warehouse_sites", "cycle_count_sessions", "inspections", "rfid_tags",
    "rfid_reads", "shipments", "logistics_deliveries", "makloon_orders",
    "putaway_orders", "repair_orders", "rfid_print_jobs", "rfid_incidents", "rfid_devices", "rfid_passages",
    "rfid_cycle_counts",
})
