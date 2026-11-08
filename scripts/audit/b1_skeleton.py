"""Audit B1 — kerangka halaman per layar (HANYA BACA). Hitung penanda kerangka baku vs buatan sendiri.

Pakai: PYTHONUTF8=1 python scripts/audit/b1_skeleton.py
Penanda: section-card/section-head/kicker (kerangka baku), MetricRow (KPI baku), tab-bar/tab-button & PageTabs
(tab baku), tab garis-bawah buatan sendiri (`border-b-2 -mb-px`), SearchBox/ListControls/FilterChips (kontrol daftar
baku), PaginationBar/usePagedRows (halaman), ekspor (`csvExport`/`downloadCsv`), dan judul (h2/h3).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "features"
SCREENS = {
    "goods-receipts (GRN)": "wms/grn/GoodsReceiptsView.jsx",
    "GRN detail": "wms/grn/GrnDetail.jsx",
    "GRN buat (wizard/OCR)": "wms/grn/GrnCreateWizard.jsx",
    "qc-inspection (antrean QC)": "wms/QCInspection.jsx",
    "Kualitas (hub QC)": "inspections/QcHubView.jsx",
    "inspections (SPK)": "inspections/InspectionsView.jsx",
    "wms-outbound": "wms/OutboundScanInterface.jsx",
    "wms-cutting": "wms/CuttingOpsView.jsx",
    "repair-orders": "wms/repair/RepairOrdersView.jsx",
    "wms-locations (Lokasi Rak)": "wms/LocationPutawayView.jsx",
    "operations › Stok": "wms/InventoryStockView.jsx",
    "operations › Transfer": "wms/TransferManagement.jsx",
    "operations › Opname": "wms/StockOpnameTab.jsx",
    "operations (kerangka)": "wms/OperationsView.jsx",
    "inventory-board": "inventory/InventoryStatusBoard.jsx",
    "stock-buckets": "inventory/StockBucketsView.jsx",
    "cs-rfid-gate": "rfid/RfidGateMonitorView.jsx",
    "cs-rfid-tags": "rfid/RfidTagsView.jsx",
    "cs-rfid-lokasi": "rfid/RfidLocationsView.jsx",
    "Perangkat RFID": "rfid/RfidDevicesView.jsx",
    "logistics": "logistics/LogisticsView.jsx",
}
MARKERS = {
    "section-card": r"section-card", "section-head": r"section-head", "kicker": r"\bkicker\b",
    "h2": r"<h2", "h3": r"<h3", "MetricRow": r"MetricRow|MetricCard", "tab-bar": r"tab-bar|tab-button",
    "PageTabs": r"\bPageTabs\b", "tab-garis-sendiri": r"border-b-2[^\"']*-mb-px|-mb-px[^\"']*border-b-2",
    "SearchBox": r"\bSearchBox\b", "ListControls": r"ListControls", "FilterChips": r"\bFilterChips\b",
    "pager": r"PaginationBar|usePagedRows|KNPager", "ekspor": r"csvExport|downloadCsv|exportCsv|Unduh CSV|Ekspor",
    "ErrorNotice": r"\bErrorNotice\b", "primary-button": r"primary-button", "secondary-button": r"secondary-button",
    "tombol-oranye-sendiri": r"bg-\[#FF9500\]", "text-[<12px]": r"text-\[(?:8|9|10|11)(?:\.5)?px\]",
}


def main():
    cols = list(MARKERS)
    print("| Layar | Berkas | " + " | ".join(cols) + " |")
    print("|---|---|" + "---|" * len(cols))
    for name, rel in SCREENS.items():
        p = ROOT / rel
        if not p.exists():
            print(f"| {name} | {rel} (TIDAK ADA) |")
            continue
        src = p.read_text(encoding="utf-8")
        src = re.sub(r"\{/\*.*?\*/\}|/\*.*?\*/", " ", src, flags=re.S)
        src = re.sub(r"(?m)^\s*//.*$", "", src)
        vals = [str(len(re.findall(MARKERS[c], src))) for c in cols]
        print(f"| {name} | `{rel}` | " + " | ".join(vals) + " |")


if __name__ == "__main__":
    main()
