#!/usr/bin/env python3
"""PREP-D1 — simulator lintasan gate U300 V2 tanpa perangkat (kontrak 2.1). Untuk paket E (agent 0.5) & UAT.

Dua mode (hanya pustaka standar Python; pembangun envelope = backend/services/rfid_v2_envelope.py, murni):

1) `device` — jalur reader SUNGGUHAN lewat HTTP + X-Device-Key (sama dengan agent): ambil profil, kirim
   GpiEdge + TagSummary, lalu close; cetak keputusan ERP. EPC dokumen/asing/latar diberikan lewat argumen.
     python scripts/rfid_v2_simulate.py device --base-url http://localhost:8001 --device-key dk_... \\
         --scenario full_load --doc-epc E2...01 --doc-epc E2...02 [--extra-epc E2...] [--background-epc E2...]

2) `ops` — login pengguna admin lalu panggil endpoint simulator ERP (memilih dokumen aktif gudang otomatis):
     python scripts/rfid_v2_simulate.py ops --base-url http://localhost:8001 --email admin@kainnusantara.id \\
         --password demo12345 --device-id <id perangkat> --scenario partial_trip [--source-type shipment --source-id ...]

Skenario: full_load, partial_trip, reversed, reversed_with_rolls, empty, foreign_roll, quarantine_roll,
background_tag, overflow (khusus mode ops), sensor_fault. Keluar 0 bila verdict sesuai harapan, 2 bila tidak.
Lintasan mode `device` TIDAK ditandai simulasi (memang lewat jalur reader); pakai di lingkungan uji.
"""
import argparse
import importlib.util
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENVELOPE = Path(__file__).resolve().parents[1] / "backend/services/rfid_v2_envelope.py"


def load_envelope():
    spec = importlib.util.spec_from_file_location("rfid_v2_envelope", ENVELOPE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def call(method, url, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            return res.status, json.loads(res.read() or b"null")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read() or b"null")
        except ValueError:
            return exc.code, None


def run_device(args, env):
    base = args.base_url.rstrip("/") + "/api/rfid/v2"
    key = {"X-Device-Key": args.device_key}
    status, cfg = call("GET", f"{base}/device/config", headers=key)
    if status != 200:
        print(json.dumps({"step": "config", "status": status, "body": cfg}, ensure_ascii=False, indent=2))
        return 1
    g = cfg["logical_gates"][0]
    if args.scenario == "overflow":
        print("Skenario overflow butuh kapasitas lintasan kecil — jalankan lewat mode ops.")
        return 1
    built = env.build_passage(scenario=args.scenario, gate_id=g["logical_gate_id"], config_version=cfg["config_version"],
                              hardware_profile_id=cfg["hardware_profile_id"], direction=g["direction"],
                              antennas=g["antenna_ids"], doc_epcs=args.doc_epc, extra_strong=args.extra_epc,
                              background_epcs=args.background_epc)
    for body in built["batches"]:
        status, res = call("POST", f"{base}/events", body, key)
        if status != 200:
            print(json.dumps({"step": "events", "status": status, "body": res}, ensure_ascii=False, indent=2))
            return 1
    status, decision = call("POST", f"{base}/passages/{built['passage_id']}/close", built["close"],
                            {**key, "Idempotency-Key": "close-" + built["passage_id"]})
    print(json.dumps({"scenario": args.scenario, "expected": built["expected"], "status": status, "decision": decision},
                     ensure_ascii=False, indent=2))
    return 0 if status == 200 and decision.get("verdict") == built["expected"] else 2


def run_ops(args):
    base = args.base_url.rstrip("/")
    status, login = call("POST", f"{base}/api/auth/login", {"email": args.email, "password": args.password})
    if status != 200:
        print(f"Login gagal ({status}).")
        return 1
    body = {"scenario": args.scenario}
    if args.source_type and args.source_id:
        body.update(source_type=args.source_type, source_id=args.source_id)
    status, res = call("POST", f"{base}/api/rfid/v2/ops/devices/{args.device_id}/simulate", body,
                       {"Authorization": "Bearer " + login["token"]})
    print(json.dumps({"status": status, "result": res}, ensure_ascii=False, indent=2))
    return 0 if status == 200 and res.get("as_expected") else 2


def main():
    env = load_envelope()
    p = argparse.ArgumentParser(description="Simulator lintasan gate U300 V2 (kontrak 2.1)")
    sub = p.add_subparsers(dest="mode", required=True)
    d = sub.add_parser("device", help="jalur reader (X-Device-Key)")
    o = sub.add_parser("ops", help="endpoint simulator ERP (login admin)")
    for x in (d, o):
        x.add_argument("--base-url", default="http://localhost:8001")
        x.add_argument("--scenario", required=True, choices=sorted(env.SCENARIOS))
    d.add_argument("--device-key", required=True)
    d.add_argument("--doc-epc", action="append", default=[])
    d.add_argument("--extra-epc", action="append", default=[], help="EPC kuat di luar dokumen (asing/karantina)")
    d.add_argument("--background-epc", action="append", default=[], help="EPC latar (in_background=true)")
    o.add_argument("--email", required=True)
    o.add_argument("--password", required=True)
    o.add_argument("--device-id", required=True)
    o.add_argument("--source-type")
    o.add_argument("--source-id")
    args = p.parse_args()
    return run_device(args, env) if args.mode == "device" else run_ops(args)


if __name__ == "__main__":
    sys.exit(main())
