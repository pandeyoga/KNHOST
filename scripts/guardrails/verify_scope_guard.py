#!/usr/bin/env python3
"""verify_scope_guard.py — GUARDRAIL **G-SCOPE-01** (usulan audit B3b §8, FIX-1 9 Nov 2026).

Kelas bug: endpoint `…/{id}…` di router WMS-RFID membaca/menulis dokumen hanya lewat `find_one({"id": …})` tanpa
pemeriksa cakupan PT/lokasi → pengguna PT A / lokasi Soreang membuka dokumen PT B / Jakarta bila tahu id-nya
(FRM-23 `/inbound/qc/tasks/{id}/rolls`, SCP-1 lima endpoint roll RFID, tag-history, riwayat perbaikan roll).

Cek STATIK (AST): setiap fungsi rute ber-parameter path di router cakupan WMS-RFID wajib memanggil salah satu penjaga
yang dikenal (langsung atau lewat helper modul berawalan `_`): `assert_entity_access`, `assert_active_entity_access`,
`guard_doc`, `location_scope.*`, pemuat dokumen bertanda cakupan (`_guard*`, `_load_session`, `_session`, `_qc_task`,
`_roll*`, `pa._get`/layanan PA bercakupan, `rps.*`/`rfid.*` bercakupan `resolve_scope_ids`), atau `require_role`
(infrastruktur admin). Pengecualian SENGAJA dicatat di `ALLOW` beserta alasannya.
Pelengkap RUNTIME: `backend/tests/test_fix1_cakupan.py::test_g_scope_01_sweep_get_by_id` (sapuan OpenAPI, id milik
PT & lokasi lain → 403/404).

CARA PAKAI
    python scripts/guardrails/verify_scope_guard.py            # gate (exit 1 bila ada endpoint tanpa penjaga)
    python scripts/guardrails/verify_scope_guard.py --self-test # bukti-merah: pola bocor HARUS tertangkap
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ROUTERS = ROOT / "backend" / "routers"
SCOPE_ROUTERS = [
    "wms.py", "putaway_orders.py", "transfers.py", "cycle_count.py", "initial_registration.py", "qc_inspection.py",
    "inspections.py", "warehouses.py", "rfid.py", "rfid_printers.py", "inventory.py", "inbound_receiving.py",
    "inbound_receiving_extra.py", "inbound_scan_label.py", "outbound_picking.py", "outbound_picking_extra.py",
    "logistics.py", "goods_receipts.py", "cutting.py", "repair_orders.py",
]
GUARD_RE = re.compile(
    r"assert_entity_access|assert_active_entity_access|guard_doc|location_scope\.|_assert_\w+\(|_guard\w*\(|"
    r"_load_session\(|_session\(|_qc_task\(|_roll\w*\(|pa\._get\(|resolve_scope_ids\(|_scope\(request\)|"
    r"require_role\(|_guarded\(|ctx\.can_access\(|can_access\(|_act\(|_doc_scope\(|_grn\(|_load\(|"
    r"resolve_list_scope\(|resolve_work_scope\(|"
    # kanal PERANGKAT (X-Device-Key) — identitas = perangkat terdaftar di gedungnya, bukan sesi pengguna
    r"_device\(request\)|ing\.authenticate\(")
# Endpoint ber-parameter path yang SENGAJA tanpa penjaga dokumen — WAJIB beralasan.
ALLOW = {
    ("warehouses.py", "get_warehouse_gate_policy"): "kebijakan gate gedung = konfigurasi gedung, bukan dokumen PT",
    ("rfid.py", "get_gate_status"): "status perangkat gate (daring/kunci) = konfigurasi perangkat, tanpa dokumen PT",
    ("rfid_printers.py", "get_printer_profile"): "profil printer = konfigurasi perangkat, tanpa dokumen PT",
    ("inbound_receiving.py", "complete_inbound_receiving"):
        "penjaga di layanan: complete_task(ctx=…) → assert_entity_access(task, wms_tasks) (PT + lokasi)",
    ("goods_receipts.py", "get_dn_profile"): "param = id mitra; profil dibaca per PT aktif pemanggil",
    ("goods_receipts.py", "patch_dn_profile"): "param = id mitra; profil ditulis per PT aktif pemanggil",
    ("cutting.py", "set_caps"): "kemampuan potong lokasi = konfigurasi (izin sample_order.cutting_config)",
}
G, R, B, X = "\033[92m", "\033[91m", "\033[1m", "\033[0m"


def _route_path(dec):
    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in (
            "get", "post", "put", "patch", "delete") and dec.args and isinstance(dec.args[0], ast.Constant):
        return dec.func.attr, str(dec.args[0].value)
    return None


def scan_source(name: str, src: str):
    tree = ast.parse(src)
    helpers = {n.name: ast.get_source_segment(src, n) or "" for n in tree.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("_")}
    bad = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        routes = [r for r in (_route_path(d) for d in node.decorator_list) if r]
        if not routes or not any("{" in p for _, p in routes):
            continue
        if (name, node.name) in ALLOW:
            continue
        body = ast.get_source_segment(src, node) or ""
        called = set(re.findall(r"\b(_\w+)\(", body))
        text = body + "".join(helpers.get(c, "") for c in called)
        if not GUARD_RE.search(text):
            bad.append((name, node.name, routes[0][0].upper(), routes[0][1]))
    return bad


def main() -> int:
    if "--self-test" in sys.argv:
        leak = ('from fastapi import APIRouter\nrouter = APIRouter()\n'
                '@router.get("/x/{task_id}/rolls")\nasync def f(task_id: str, request):\n'
                '    task = await db.wms_tasks.find_one({"id": task_id})\n    return task\n')
        ok = ('@router.get("/x/{task_id}/plan")\nasync def g(task_id, request):\n'
              '    return await _qc_task(task_id, request)\n')
        caught = scan_source("demo.py", leak)
        clean = scan_source("demo.py", "from fastapi import APIRouter\nrouter = APIRouter()\n" + ok)
        if caught and not clean:
            print(f"{G}[SELF-TEST OK]{X} pola bocor tertangkap, pola berpenjaga lolos")
            return 0
        print(f"{R}[SELF-TEST GAGAL]{X} caught={caught} clean={clean}")
        return 1
    bad = []
    for name in SCOPE_ROUTERS:
        p = ROUTERS / name
        if p.exists():
            bad += scan_source(name, p.read_text(encoding="utf-8"))
    print(f"{B}G-SCOPE-01 — endpoint /{{id}} WMS-RFID wajib berpenjaga cakupan{X} ({len(SCOPE_ROUTERS)} router)")
    for name, fn, meth, path in bad:
        print(f"  {R}[TANPA PENJAGA]{X} {name}:{fn} {meth} {path}")
    if bad:
        print(f"{R}MERAH{X}: {len(bad)} endpoint tanpa pemeriksa cakupan PT/lokasi")
        return 1
    print(f"{G}HIJAU{X}: semua endpoint ber-parameter path memanggil penjaga (pengecualian beralasan: {len(ALLOW)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
