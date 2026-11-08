"""Create an internal handover archive; never upload vendor binaries automatically."""
from pathlib import Path
import hashlib
import json
import zipfile

root = Path(__file__).resolve().parent
apk = root / "delivery/KN-U300-Agent-0.4.0-lab-debug.apk"
assert apk.is_file(), "Build/copy APK first"
assert "BUILD SUCCESSFUL" in (root / "build-debug.log").read_text(encoding="utf-8-sig"), "Final build must pass"

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

files = []
for p in root.rglob("*"):
    if not p.is_file():
        continue
    if p.suffix.lower() in {".p12", ".jks", ".keystore", ".pem", ".key"}:
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
    "version": "0.4.0-lab",
    "hardware": "Chainway U300",
    "application_id": "id.kubusteknologi.kn.u300.agent",
    "status": "LAB_NOT_PRODUCTION_APPROVED",
    "build": "PASS",
    "host_assertions_passed": 121,
    "schema_payload_types_passed": 6,
    "negative_schema_checks_passed": 2,
    "apk_signature": "PASS_V2_DEBUG",
    "hardware_test": "NOT_RUN",
    "android_runtime_test": "NOT_RUN",
    "erp_integration_test": "PASS_LOCAL_ROUTER_MONGO_AND_JAVA_HTTPS",
    "erp_baseline": "055f7ea0f852582867b3ab063d28e7e41f67f410",
    "erp_assertions_passed": 53,
    "java_erp_https_assertions_passed": 9,
    "full_android_lint": "PASS_0_ERRORS_1_COMPATIBILITY_WARNING",
    "snapshot_integrity_cases_passed": 5,
    "android_instrumentation_apk": "COMPILED_NOT_RUN",
    "automatic_retention": "NOT_IMPLEMENTED_PENDING_APPROVAL",
    "vendor_sdk_distribution": "INTERNAL_ONLY_REVIEW_VENDOR_LICENSE_BEFORE_PUBLICATION",
    "files": {str(p.relative_to(root)).replace("\\", "/"): {"sha256": digest(p), "bytes": p.stat().st_size} for p in sorted(files)},
}
handover = root / "HANDOVER.json"
handover.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
files.append(handover)
hashes = root / "SHA256SUMS.txt"
hashes.write_text("\n".join(f"{digest(p)}  {p.relative_to(root).as_posix()}" for p in sorted(files))+"\n", encoding="utf-8")
files.append(hashes)
archive = root.parent / "KN_U300_Agent_0.4.0_LAB_2026-10-19.zip"
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(files):
        z.write(p, f"U300_Agent/{p.relative_to(root).as_posix()}")
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert len(z.namelist()) == len(set(z.namelist()))
archive.with_suffix(".zip.sha256").write_text(f"{digest(archive)}  {archive.name}\n", encoding="utf-8")
print(json.dumps({"archive":str(archive),"files":len(files),"bytes":archive.stat().st_size,"apk_sha256":digest(apk),"zip_sha256":digest(archive)}, indent=2))
