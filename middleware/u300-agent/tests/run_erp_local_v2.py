#!/usr/bin/env python3
"""Uji integrasi agent 0.5 (Java) → ERP lokal V2 (kontrak 2.1). HANYA untuk backend uji sementara (bukan produksi).

Langkah: login admin → pilih perangkat gate → terbitkan device key (rotasi) → terbitkan profil 2.1 commissioned dari
docs/device-config.template.json (nilai uji: region 63, daya 15 dBm, sensor_stuck_ms 12 s) → cari SJ aktif gudang
perangkat dengan roll bertag yang belum lewat (binding manual sementara hanya untuk membaca roll, lalu dilepas — ERP
memakai auto-cocok) → kompilasi & jalankan tests/ErpLocalV2Test.java (HTTP lokal; HTTPS tidak dipakai).

  python tests/run_erp_local_v2.py --base-url http://127.0.0.1:18091 --email admin@kainnusantara.id \\
      --password demo12345 --tool-root <folder android-build>

Hanya pustaka standar. Menolak base URL non-lokal.
"""
import argparse
import copy
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def call(method, url, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return res.status, json.loads(res.read() or b"null")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read() or b"null")
        except ValueError:
            return exc.code, None


def strip(value):
    if isinstance(value, dict):
        return {k: strip(v) for k, v in value.items() if not k.startswith("_")}
    if isinstance(value, list):
        return [strip(v) for v in value]
    return value


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--tool-root", required=True)
    p.add_argument("--device-id")
    p.add_argument("--min-rolls", type=int, default=6)
    a = p.parse_args()
    host = urllib.parse.urlparse(a.base_url).hostname
    if host not in ("127.0.0.1", "localhost"):
        sys.exit("Base URL wajib lokal (backend uji).")
    base = a.base_url.rstrip("/")
    st, login = call("POST", f"{base}/api/auth/login", {"email": a.email, "password": a.password})
    assert st == 200, f"login {st}"
    auth = {"Authorization": "Bearer " + login["token"]}
    st, devs = call("GET", f"{base}/api/rfid/devices", headers=auth)
    assert st == 200, f"devices {st}"
    gates = [d for d in devs["devices"] if d.get("type") in ("gate", "fixed_reader") and (not a.device_id or d["id"] == a.device_id)]
    assert gates, "Tidak ada perangkat gate"
    dev = gates[0]
    st, key = call("POST", f"{base}/api/rfid/devices/{dev['id']}/api-key?regenerate=true", headers=auth)
    assert st == 200, f"api-key {st} {key}"
    tpl = strip(json.loads((ROOT / "docs/device-config.template.json").read_text(encoding="utf-8")))
    cfg = copy.deepcopy(tpl)
    version = "uji-e-" + time.strftime("%Y%m%d%H%M%S")
    gate_id = "GATE-UJI-E"
    cfg.update(device_id=dev["id"], warehouse_id=dev["warehouse_id"], site_id="site-uji-e", config_version=version,
               hardware_profile_id="kn-u300-uji-e", server_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    prm = cfg["hardware_profile"]["parameters"]
    prm["commissioned"] = True
    prm["radio"].update(region_code=63, antenna_power_dbm={"1": 15, "2": 15, "3": 15})
    prm["agent_tuning"]["sensor_stuck_ms"] = 12000
    cfg["hardware_profile"]["firmware_version"] = "uji-integrasi"
    g = cfg["logical_gates"][0]
    g.update(logical_gate_id=gate_id, warehouse_id=dev["warehouse_id"], site_id="site-uji-e", direction="out")
    st, res = call("PUT", f"{base}/api/rfid/v2/ops/devices/{dev['id']}/config", cfg, auth)
    assert st == 200, f"publish profil {st} {res}"
    print(f"Profil {version} terbit untuk {dev['id']} ({dev['warehouse_id']})")
    st, gs = call("GET", f"{base}/api/rfid/v2/device/gate-state?logical_gate_id={gate_id}", headers={"X-Device-Key": key["api_key"]})
    if st == 200 and gs.get("latched"):   # kunci gate dari putaran uji sebelumnya
        st, ack = call("POST", f"{base}/api/rfid/v2/ops/devices/{dev['id']}/gate-latch/acknowledge",
                       {"logical_gate_id": gate_id, "latch_id": gs["latch_id"], "note": "uji integrasi paket E: lepas kunci putaran sebelumnya"}, auth)
        assert st == 200, f"ack kunci {st} {ack}"
        print("Kunci gate putaran sebelumnya dilepas (pengakuan admin).")
    st, tags = call("GET", f"{base}/api/rfid/tags?status=active", headers=auth)
    epc_of = {t["roll_id"]: t["epc"] for t in tags.get("tags", []) if t.get("roll_id") and t.get("epc")}
    chosen = None
    for typ in ("shipment", "wh_transfer", "putaway"):
        st, src = call("GET", f"{base}/api/rfid/v2/ops/devices/{dev['id']}/sources?source_type={typ}&direction=out", headers=auth)
        for cand in (src or {}).get("sources", []):
            st, session = call("GET", f"{base}/api/rfid/v2/ops/doc-sessions/{typ}/{cand['id']}?direction=out", headers=auth)
            if st == 200 and (session or {}).get("passed", 0) > 0:   # roll sudah lewat di putaran sebelumnya → dokumen lain
                continue
            st, bind = call("POST", f"{base}/api/rfid/v2/ops/devices/{dev['id']}/manifest",
                            {"logical_gate_id": gate_id, "direction": "out", "source_type": typ, "source_id": cand["id"]}, auth)
            if st != 200:
                continue
            epcs = [epc_of[r] for r in bind.get("roll_ids", []) if r in epc_of]
            call("DELETE", f"{base}/api/rfid/v2/ops/devices/{dev['id']}/manifest?logical_gate_id={gate_id}", headers=auth)
            if len(epcs) >= 2 and (chosen is None or len(epcs) > len(chosen[2])):
                chosen = (typ, cand["id"], epcs)
            if chosen and len(chosen[2]) >= a.min_rolls:
                break
        if chosen and len(chosen[2]) >= a.min_rolls:
            break
    assert chosen, "Tidak ada dokumen aktif dengan ≥ 2 roll bertag di gudang perangkat"
    print(f"Dokumen uji: {chosen[0]} {chosen[1]} — {len(chosen[2])} roll bertag")
    tools = Path(a.tool_root)
    jar = tools / "json-20240303.jar"
    out = ROOT / "tests/build/erp-local"
    out.mkdir(parents=True, exist_ok=True)
    src = ROOT / "app/src/main/java/id/kubusteknologi/kn/u300"
    files = [str(f) for f in (src / "core").glob("*.java")] + [str(src / n) for n in ("Json.java", "Config.java", "Api.java", "DecisionPolicy.java", "Telemetry.java")]
    files.append(str(ROOT / "tests/ErpLocalV2Test.java"))
    subprocess.run([str(tools / "jdk/bin/javac"), "-encoding", "UTF-8", "-cp", str(jar), "-d", str(out), *files], check=True)
    env = {**os.environ, "KN_TEST_DEVICE_KEY": key["api_key"]}
    r = subprocess.run([str(tools / "jdk/bin/java"), "-cp", f"{out}{os.pathsep}{jar}", "id.kubusteknologi.kn.u300.ErpLocalV2Test",
                        base, gate_id, ",".join(chosen[2][:12])], env=env)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
