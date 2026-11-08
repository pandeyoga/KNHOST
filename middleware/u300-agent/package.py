"""Manifest serah-terima internal (HANDOVER.json + SHA256SUMS.txt); arsip zip hanya bila --zip. Tidak mengunggah apa pun.

Angka hasil uji diisi dari laporan validasi (docs/05_VALIDASI.md) — perbarui VALIDATION bila tes dijalankan ulang.
"""
from pathlib import Path
import hashlib
import json
import sys
import zipfile

root = Path(__file__).resolve().parent
VERSION = "0.5.0-lab"
apk = root / f"delivery/KN-U300-Agent-{VERSION.replace('-lab', '')}-lab-debug.apk"
assert apk.is_file(), "Build/copy APK first"

VALIDATION = {
    "contract_version": "2.1.0",
    "build": "PASS",
    "apk_signature": "PASS_V2_DEBUG",
    "full_android_lint": "PASS_0_ERRORS_1_COMPATIBILITY_WARNING",
    "android_instrumentation_apk": "COMPILED_NOT_RUN",
    "host_assertions_passed": 396,
    "host_assertions_by_test": {"SafetyTest": 27, "CoreTest": 91, "PassageMachineTest": 52, "HostTest": 44,
                                "PipelineTest": 83, "DecisionPolicyTest": 75, "TransportTest": 24},
    "schema_fixture_payloads_passed": 21,
    "schema_types_covered": 9,
    "negative_schema_checks_passed": 9,
    "template_schema_check": "PASS",
    "snapshot_integrity_cases_passed": 9,
    "erp_local_v2_java_assertions_passed": 41,
    "erp_local_v2_transport": "HTTP_LOCAL_BACKEND_SNAPSHOT_kn_test_trial_2026-11-08",
    "hardware_test": "NOT_RUN",
    "android_runtime_test": "NOT_RUN",
    "bench_test_k_rfid_03": "PREPARED_NOT_RUN",
}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

files = []
for p in root.rglob("*"):
    if not p.is_file():
        continue
    if p.suffix.lower() in {".p12", ".jks", ".keystore", ".pem", ".key", ".log", ".zip"}:
        continue
    rel = p.relative_to(root)
    if any(part in {".gradle", "build", "__pycache__"} for part in rel.parts):
        continue
    if p.name in {"local.properties", "HANDOVER.json", "SHA256SUMS.txt"}:
        continue
    files.append(p)

manifest = {
    "project": "ERP Kain Nussantara",
    "production_it": "PT Kubus Teknologi Indonesia",
    "version": VERSION,
    "version_code": 5,
    "date": "2026-11-09",
    "hardware": "Chainway U300",
    "application_id": "id.kubusteknologi.kn.u300.agent",
    "status": "LAB_NOT_PRODUCTION_APPROVED",
    **VALIDATION,
    "automatic_retention": "NOT_IMPLEMENTED_PENDING_APPROVAL",
    "calibration": "ALL_PARAMETERS_INITIAL_K-RFID-03_05_08_OPEN",
    "vendor_sdk_distribution": "INTERNAL_ONLY_REVIEW_VENDOR_LICENSE_BEFORE_PUBLICATION",
    "files": {str(p.relative_to(root)).replace("\\", "/"): {"sha256": digest(p), "bytes": p.stat().st_size} for p in sorted(files)},
}
handover = root / "HANDOVER.json"
handover.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
files.append(handover)
hashes = root / "SHA256SUMS.txt"
hashes.write_text("\n".join(f"{digest(p)}  {p.relative_to(root).as_posix()}" for p in sorted(files)) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"files": len(files), "apk_sha256": digest(apk)}, indent=2))
if "--zip" in sys.argv:
    files.append(hashes)
    archive = root.parent / f"KN_U300_Agent_{VERSION}_2026-11-09.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(files):
            z.write(p, f"U300_Agent/{p.relative_to(root).as_posix()}")
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
    print(f"Arsip: {archive} (jangan di-commit / jangan dipublikasikan)")
