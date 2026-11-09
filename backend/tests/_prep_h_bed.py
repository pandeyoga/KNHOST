"""PREP-H — perlengkapan uji gate V2 bersama (`test_prep_h_*`): gudang bergate + reader IN/OUT ber-profil V2 +
dokumen aktif berisi roll bertag, lalu lintasan lewat endpoint DEVICE sungguhan (envelope simulator D1).
Residu dibuang lewat sidik `_id` (`poc_stock_guard`), saldo & nomor urut dipulihkan."""
import copy
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from pymongo import MongoClient

from services import rfid_v2_envelope as env
from services.rfid_ingest_service import hash_device_key
from services.rfid_v2_common import digest

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
API, V2 = f"{BASE}/api", f"{BASE}/api/rfid/v2"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
FIXTURE = json.loads((Path(__file__).parent / "fixtures/u300_contract.json").read_text())["DeviceConfig"]
LIMITS = {"max_events": 100, "max_body_bytes": 512000, "max_queue_bytes": 64000000}   # templat commissioning
TRACKED = ["inventory_rolls", "inventory_movements", "inventory_lots", "audit_logs", "notifications", "rfid_tags",
           "rfid_devices", "putaway_orders", "warehouses", "warehouse_transfers", "shipments", "sales_orders",
           "doc_refs", "wms_tasks", "makloon_orders", "repair_orders", "rfid_reads"]


class Bed:
    def __init__(self, label):
        self.tag = uuid.uuid4().hex[:8]
        self.label = label
        t = self.tag
        self.site = f"site_TEST_{label}_{t}"
        self.wh_src, self.wh_gate, self.wh_other = (f"wh_TEST_{label}_{t}_{k}" for k in ("src", "gate", "other"))
        self.dev = {k: f"dev_TEST_{label}_{t}_{k}" for k in ("in", "out")}
        self.keys = {k: f"dk_TEST_{label}_{t}_{k}" for k in self.dev}
        self.n = 0
        self._ids = self._stock = None

    def nx(self):
        self.n += 1
        return self.n

    def setup(self):
        from poc_stock_guard import snapshot_new_ids, snapshot_stock
        self._stock = snapshot_stock(["inventory_balances", "number_sequences"])
        assert self._stock.get("__enabled__"), "restore harus aktif (DB uji)"
        names = [c for c in DB.list_collection_names() if c.startswith("rfid_v2")] + TRACKED
        self._ids = snapshot_new_ids(sorted(set(names)))
        gate_cfg = {"has_gate": True, "physical_gate": True, "confirm_mode": "gate",
                    "pairs": [{"in_device_id": self.dev["in"], "out_device_id": self.dev["out"], "layout": "terpisah"}]}
        for wid, code, roles, gc in ((self.wh_src, "S", ["transit", "receiving"], None), (self.wh_gate, "G", ["storage"], gate_cfg),
                                     (self.wh_other, "O", ["storage"], None)):
            DB.warehouses.insert_one({"id": wid, "name": f"Uji {self.label} {code}{self.tag}", "code": f"{self.label}{code}{self.tag}",
                                      "roles": roles, "site_id": self.site, "sharing_mode": "shared", "active": True,
                                      "gate_config": gc or {"has_gate": False}})
        for k in self.dev:
            DB.rfid_devices.insert_one({"id": self.dev[k], "code": f"{self.label}-{k}-{self.tag}", "name": f"Gate Uji {self.label} {k}",
                                        "type": "gate", "direction": k, "warehouse_id": self.wh_gate, "enabled": True,
                                        "status": "online", "api_key_hash": hash_device_key(self.keys[k])})
            cfg = copy.deepcopy(FIXTURE)
            cfg.update(device_id=self.dev[k], warehouse_id=self.wh_gate, site_id=self.site, config_version="h-v1",
                       limits=dict(LIMITS))
            g = cfg["logical_gates"][0]
            g.update(logical_gate_id="G1", warehouse_id=self.wh_gate, site_id=self.site, direction=k,
                     antenna_ids=["1", "2", "3"], completion_basis="document_session")
            cfg.pop("server_time", None)
            DB.rfid_v2_configs.insert_one({"_id": digest([self.dev[k], "h-v1"]), "config": cfg, "actor_id": "uji", "at": "x",
                                           "device_id": self.dev[k]})
            DB.rfid_devices.update_one({"id": self.dev[k]}, {"$set": {"v2_config_version": "h-v1", "protocol": "v2"}})

    def teardown(self):
        from poc_stock_guard import purge_new_ids, restore_stock
        purge_new_ids(self._ids, verbose=False)
        restore_stock(self._stock)

    def product(self):
        p = DB.products.find_one({"status": {"$ne": "inactive"}, "base_unit": "meter"}, {"_id": 0, "id": 1})
        assert p, "data acuan tanpa produk meter"
        return p["id"]

    def rolls(self, n, wh=None, status="available", **extra):
        pid, out, rows, tags = self.product(), [], [], []
        for _ in range(n):
            i = self.nx()
            rid, tid, epc = f"roll_TEST_{self.label}_{self.tag}_{i}", f"tag_TEST_{self.label}_{self.tag}_{i}", f"E2A1{self.tag.upper()}{i:012X}"
            tags.append({"id": tid, "epc": epc, "roll_id": rid, "status": "active", "warehouse_id": wh or self.wh_src,
                         "created_at": "2026-11-01T00:00:00+00:00"})
            rows.append({"id": rid, "roll_no": f"{self.label}{self.tag}{i}", "product_id": pid, "warehouse_id": wh or self.wh_src,
                         "owner_entity_id": ENT, "status": status, "length_remaining": 30.0, "length_initial": 30.0, "unit": "meter",
                         "grade": "A", "lot": "L-H", "rfid_tag_id": tid, "bin_id": None, "active_movement": None,
                         "length_reserved": 0, "length_reservations": [],
                         "journey": {"stage": "tag_verified", "verified_tag_id": tid, "routing": "store",
                                     "updated_at": "2026-11-02T00:00:00+00:00"}, **extra})
            out.append({"id": rid, "epc": epc, "roll_no": f"{self.label}{self.tag}{i}"})
        if rows:
            DB.rfid_tags.insert_many(tags)
            DB.inventory_rolls.insert_many(rows)
        return out

    def transfer(self, n, dest=None):
        tid = f"trf_TEST_{self.label}_{self.tag}_{self.nx()}"
        rs = self.rolls(n, status="in_transit_transfer", reserved_ref={"type": "wh_transfer", "id": tid})
        DB.warehouse_transfers.insert_one({
            "id": tid, "code": f"TRF-{self.label}-{self.tag}-{self.nx()}", "status": "dispatched", "transfer_kind": "warehouse",
            "source_warehouse_id": self.wh_src, "dest_warehouse_id": dest or self.wh_gate, "owner_entity_id": ENT,
            "entity_id": ENT, "created_at": datetime.now(timezone.utc).isoformat(),
            "items": [{"product_id": self.product(), "unit": "meter",
                       "rolls": [{"roll_id": r["id"], "roll_no": r["roll_no"], "length": 30.0} for r in rs]}]})
        return tid, rs

    def shipment(self, n, so_status="in_progress"):
        so, sid = f"so_TEST_{self.label}_{self.tag}_{self.nx()}", f"shp_TEST_{self.label}_{self.tag}_{self.nx()}"
        DB.sales_orders.insert_one({"id": so, "number": so, "status": so_status, "entity_id": ENT})
        rs = self.rolls(n, wh=self.wh_gate, status="in_transit_sales", reserved_ref={"type": "sales_order", "id": so})
        DB.shipments.insert_one({"id": sid, "shipment_no": f"SJ-{self.label}-{self.tag}-{self.nx()}", "order_id": so,
                                 "warehouse_id": self.wh_gate, "status": "dispatched", "entity_id": ENT,
                                 "created_at": datetime.now(timezone.utc).isoformat(),
                                 "rolls": [{"roll_id": r["id"]} for r in rs]})
        return sid, rs

    def build(self, k, epcs, scenario="full_load", extra=()):
        return env.build_passage(scenario=scenario, gate_id="G1", config_version="h-v1",
                                 hardware_profile_id=FIXTURE["hardware_profile_id"], direction=k, antennas=["1", "2", "3"],
                                 doc_epcs=epcs, extra_strong=extra, batch_size=400)

    def send_events(self, k, built, lat=None):
        for body in built["batches"]:
            t0 = time.perf_counter()
            r = requests.post(f"{V2}/events", headers={"X-Device-Key": self.keys[k]}, json=body, timeout=60)
            if lat is not None:
                lat.append((time.perf_counter() - t0) * 1000)
            assert r.status_code == 200, r.text

    @staticmethod
    def prepare_close(built):
        if "_close_body" not in built:   # close dikirim "sekarang"; close ulang wajib isi yang sama (CLOSE_CONFLICT)
            built["_close_body"] = {**built["close"],
                                    "closing_captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
        return built["_close_body"]

    def close(self, k, built, timeout=90):
        hdr = {"X-Device-Key": self.keys[k], "Idempotency-Key": "c-" + built["passage_id"]}
        return requests.post(f"{V2}/passages/{built['passage_id']}/close", json=self.prepare_close(built), timeout=timeout,
                             headers=hdr)

    def pid(self, k, local):
        return digest([self.dev[k], local])

    def wait_state(self, pid, states=("done", "error"), timeout=60):
        end = time.time() + timeout
        while time.time() < end:
            row = DB.rfid_v2_passages.find_one({"_id": pid}, {"gate_txn_state": 1, "gate_txn_attempts": 1, "gate_txn_next_at": 1,
                                                              "gate_txn_gave_up": 1, "gate_txn_error": 1})
            if row and row.get("gate_txn_state") in states:
                return row
            time.sleep(0.05)
        raise AssertionError(f"lintasan {pid} tidak mencapai {states} dalam {timeout} dtk")
