"""Audit B1b — kerangka halaman untuk layar yang belum dihitung B1 (HANYA BACA). Penanda = `b1_skeleton.MARKERS`.

Pakai: PYTHONUTF8=1 python scripts/audit/b1b_skeleton.py
Menambah kolom `table` (tabel mentah), `ResponsiveTable`, `askConfirm` (konfirmasi baku), dan `limit` (angka batas di
panggilan daftar) supaya sel matriks yang dikunjungi B1b punya pembanding statis.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from b1_skeleton import MARKERS, ROOT  # noqa: E402

SCREENS = {
    "inventory-lots (Lot & Silsilah)": "inventory/lots/LotsView.jsx",
    "production (BOM in-house)": "production/ProductionView.jsx",
    "md-warehouses (Data Gudang)": "wms/warehouses/WarehouseMasterView.jsx",
    "logistics (Pengiriman)": "logistics/LogisticsView.jsx",
    "cs-rfid-lokasi": "rfid/RfidLocationsView.jsx",
    "repair-orders": "wms/repair/RepairOrdersView.jsx",
    "returns (Retur Pelanggan)": "sales/SalesReturns.jsx",
    "interco (Antar-PT / Retur Antar-PT)": "finance/interco/IntercoView.jsx",
    "purchase-returns": "purchasing/PurchaseReturns.jsx",
    "my-desk / Meja Gudang": "desks/RoleDesk.jsx",
    "sample-admin-desk": "samples/SampleAdminDesk.jsx",
    "makloon-orders": "purchasing/MakloonOrdersView.jsx",
    "makloon-claim-recap": "purchasing/makloon/MakloonClaimRecapView.jsx",
    "makloon-claims": "purchasing/makloon/MakloonClaimsView.jsx",
    "purchase-requisitions": "purchasing/PurchaseRequisitions.jsx",
    "contra-bons": "purchasing/contrabon/ContraBonsView.jsx",
    "cs-stock-analytics": "inventory/StockAnalyticsView.jsx",
    "grade-master": "settings/masters/GradeMasterView.jsx",
    "settings-receiving-ocr": "settings/ReceivingOcrSettings.jsx",
    "escalations": "manager/EscalationManagement.jsx",
}
EXTRA = {
    "table": r"<table\b", "ResponsiveTable": r"\bResponsiveTable\b", "askConfirm": r"\baskConfirm\b|ConfirmModal",
    "limit": r"limit[:=]\s*\d+|limit=\d+",
}


def main():
    marks = {**MARKERS, **EXTRA}
    cols = list(marks)
    print("| Layar | Berkas | " + " | ".join(cols) + " |")
    print("|---|---|" + "---|" * len(cols))
    for name, rel in SCREENS.items():
        p = ROOT / rel
        if not p.exists():
            hits = sorted(ROOT.rglob(Path(rel).name))
            if not hits:
                print(f"| {name} | {rel} (TIDAK ADA) |")
                continue
            p = hits[0]
            rel = p.relative_to(ROOT).as_posix()
        src = p.read_text(encoding="utf-8")
        src = re.sub(r"\{/\*.*?\*/\}|/\*.*?\*/", " ", src, flags=re.S)
        src = re.sub(r"(?m)^\s*//.*$", "", src)
        vals = [str(len(re.findall(marks[c], src))) for c in cols]
        print(f"| {name} | `{rel}` | " + " | ".join(vals) + " |")


if __name__ == "__main__":
    main()
