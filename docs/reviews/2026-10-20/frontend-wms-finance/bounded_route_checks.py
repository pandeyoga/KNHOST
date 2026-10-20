"""Read-only checks for bounded dynamic URL families inspected in source."""
from pathlib import Path
import hashlib
import json
import re

OUT = Path(__file__).resolve().parent
raw = (OUT / "openapi-8020-8dab.json").read_bytes()
api = json.loads(raw.decode("utf-8-sig"))["paths"]
rows = []

def check(method, template, source, note="Bounded values inspected in source; no request executed"):
    def norm(x):
        return re.sub(r"\{[^{}]+\}", "{}", x).rstrip("/")
    matches = [p for p in api if norm(p) == norm(template)]
    if not matches:
        matches = [p for p in api if re.fullmatch(re.sub(r"\\\{[^{}]+\\\}", r"[^/]+", re.escape(p)), template)]
    okay = [p for p in matches if method.lower() in api[p]]
    rows.append({"method": method, "path_template": template, "source": source,
                 "status": "method_path_present" if okay else "manual_candidate",
                 "openapi_paths": okay or matches, "note": note})

for name in ["shifts", "geofences", "devices"]:
    check("GET", f"/api/hr/{name}", "src/features/hr/AttendanceSetupView.jsx:18-22,62")
    check("POST", f"/api/hr/{name}", "src/features/hr/AttendanceSetupView.jsx:18-22,92")
    check("PATCH", f"/api/hr/{name}/{{id}}", "src/features/hr/AttendanceSetupView.jsx:18-22,91")
    check("DELETE", f"/api/hr/{name}/{{id}}", "src/features/hr/AttendanceSetupView.jsx:18-22,98")
for action in ["clock-in", "clock-out"]:
    check("POST", f"/api/hr/attendance/{action}", "src/features/hr/EmployeeSelfService.jsx:54,99-109", "Manual dismissal of wildcard collision: action is clock-in/clock-out, not attendance row ID")
for group in ["landed-costs", "vendor-bills"]:
    for action in ["submit", "approve", "reject", "cancel", "pay"]:
        check("POST", f"/api/{group}/{{id}}/{action}", f"src/features/purchasing/{'LandedCostDetailPanel' if group=='landed-costs' else 'VendorBillDetailPanel'}.jsx:35-52")
for action in ["submit", "approve", "reject", "ship-to-supplier", "supplier-accept", "supplier-reject", "goods-back"]:
    check("POST", f"/api/purchase-returns/{{id}}/{action}", "src/features/purchasing/PurchaseReturns.jsx:214-255")
for action in ["submit", "approve", "cancel"]:
    check("POST", f"/api/purchase-requisitions/{{id}}/{action}", "src/features/purchasing/PurchaseRequisitionDetailPanel.jsx:36-39,158-170")
for action in ["assign", "note", "reject", "reopen"]:
    check("POST", f"/api/finance-cases/{{id}}/{action}", "src/features/finance/cases/CaseDetailPanel.jsx:47,251,270,312,342")
for action in ["disburse", "cancel", "repay"]:
    check("POST", f"/api/interco/loans/{{id}}/{action}", "src/features/finance/interco/IntercoLoansPanel.jsx:64,144,149,198")
for action in ["approve", "warehouse-task"]:
    check("POST", f"/api/interco/returns/{{id}}/{action}", "src/features/finance/interco/IntercoReturnInbox.jsx:14,34,36")
for group, actions, source in [
    ("cash-advances", ["submit", "approve", "reject", "disburse"], "src/features/pettycash/CashAdvanceDetail.jsx:41,69,71,150,168"),
    ("cash-advance-settlements", ["submit", "pay-reimburse", "approve", "reject"], "src/features/pettycash/SettlementsView.jsx:167,184-195,238"),
    ("design-requests", ["assign", "approve", "submit", "reject", "cancel"], "src/features/sales/mobile/MobileMdViews.jsx:154-189"),
]:
    for action in actions:
        check("POST", f"/api/{group}/{{id}}/{action}", source)
for action in ["read", "lines/{n}/scan-label", "lines/{n}/rolls", "finish-count", "cancel", "manual-entry", "discrepancies/{key}/resolve", "reopen-count", "mko-partial", "return-to-reconcile", "close", "lines", "reject", "start-count"]:
    check("POST", f"/api/goods-receipts/{{id}}/{action}", "src/features/wms/grn/grnApi.js:66; callers GrnCreateWizard/CountPanel/Detail/OcrBits/ReconPanel/ReviewPanel")
for action in ["lines/{n}", "dn"]:
    check("PATCH", f"/api/goods-receipts/{{id}}/{action}", "src/features/wms/grn/grnApi.js:67; callers GrnLineCard/LineRow/ReviewPanel")
for action in ["rolls/{roll_id}", "lines/{n}"]:
    check("DELETE", f"/api/goods-receipts/{{id}}/{action}", "src/features/wms/grn/grnApi.js:68; GrnCountPanel.jsx:66; GrnLineCard.jsx:50; GrnLineRow.jsx:204", "Manual dismissal: helper path argument contains multiple segments, not one route parameter")
for group in ["price-approvals", "sales-returns", "purchase-returns"]:
    for action in ["approve", "reject"]:
        check("POST", f"/api/{group}/{{id}}/{action}", "src/features/approvals/ApprovalDecisionModal.jsx:66-68")
for group in ["inbound", "outbound"]:
    check("POST", f"/api/{group}/tasks/{{id}}/resolve-escalation", "src/features/manager/EscalationManagement.jsx:76-80")
for route in ["inbound/tasks", "outbound/tasks", "transfers", "dashboard", "notifications/unread-count", "settings/effective", "rnd/meta"]:
    check("GET", f"/api/{route}", "Source inventory query suffix families: params/eq starts ? or empty; query does not change route path")
check("POST", "/api/notifications/read-all", "src/hooks/useAppActions.js:740")
check("POST", "/api/scheduler/jobs/all/run", "src/features/admin/scheduler/SchedulerView.jsx:117; backend/routers/scheduler.py:46", "Backend explicitly implements job_id=='all'; dynamic route accepts this literal")
check("GET", "/api/enums/entity_type", "src/features/settings/entities/entityApi.js:102; backend/routers/enums.py:111", "Generic enum route accepts registry enum name; fallback GET /enums also exists")

report = {"baseline_sha": "8dab383f764df80737bfe02f887422b3fd72aa70", "openapi_sha256": hashlib.sha256(raw).hexdigest(),
          "method": "Finite dynamic choices traced from source and compared with OpenAPI; no API request or mutation",
          "checks": rows, "check_count": len(rows), "candidates": [x for x in rows if x["status"] != "method_path_present"]}
(OUT / "bounded-route-checks-8dab.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"checks": len(rows), "candidates": report["candidates"]}, ensure_ascii=False, indent=2))
