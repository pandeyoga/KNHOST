"""Audit B1 — matriks cakupan menu/tab × peran × desktop/HP (HANYA BACA kode; menulis ke --out saja).

Visibilitas desktop dihitung dari kode (`b1_nav_matrix.role_can_see` = tiruan `roleCanSee`). Status kunjungan
peramban & nomor temuan dibaca dari berkas JSON anotasi (`--notes`, opsional) berbentuk
{"<view>": {"<peran>": {"D": "V|T:UI-03|X", "HP": "..."}}}. Tanpa anotasi semua sel tampil = "K".

Legenda sel: K = tampil menurut kode (belum dikunjungi) · V = dikunjungi, tidak ada temuan baru ·
T:UI-nn = dikunjungi, ada temuan · X = gagal diverifikasi (stack mati/403) · – = tidak tampil menurut kode.

Pakai: PYTHONUTF8=1 python scripts/audit/b1_matrix_report.py --out <folder> [--notes notes.json]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from b1_nav_matrix import DEFAULT_OUT, HUB_TABS, parse_nav, role_can_see  # noqa: E402

ROLES = ["admin", "manager", "warehouse_admin", "warehouse", "sales", "sales_admin", "finance", "md",
         "md_quality", "qc", "sample_admin", "driver"]
# Menu/hub dalam cakupan B1 (urut = urutan bacaan laporan).
SCOPE = [
    ("Gudang & Logistik", "gudang", ["wms-operations", "stock-atp", "production", "wms-locations", "md-warehouses",
                                      "logistics", "rfid-hub", "escalations"]),
    ("(lepas)", None, ["quality-hub", "returns-hub", "warehouse-admin-desk", "my-desk", "sample-admin-desk"]),
    ("Pembelian", "pembelian", ["purchase-orders", "sourcing", "accounts-payable"]),
    ("Akuntansi & Pajak", "akuntansi", ["interco-transactions"]),
    ("(lepas)", None, ["analytics"]),
    ("Penjualan", "penjualan", ["sales", "products-pricing"]),
    ("Pengaturan", "settings-hub", ["settings-warehouse", "settings-system"]),
]
# Tab yang relevan gudang di hub yang lebih luas (tab lain dilewati supaya matriks tidak membengkak).
TAB_FILTER = {
    "purchase-orders": {"makloon-orders", "makloon-claims", "makloon-claim-recap"},
    "sourcing": {"purchase-requisitions"},
    "accounts-payable": {"contra-bons"},
    "analytics": {"cs-stock-analytics"},
    "products-pricing": {"md-products"},
    "settings-system": {"settings-devices"},
}
# Aplikasi HP per peran (MobileAppSwitch.jsx:46-56).
HP_APP = {"md": "MobileMdApp", "sales": "MobileSalesApp", "sales_admin": "MobileSalesApp",
          "warehouse": "MobileWarehouseApp", "warehouse_admin": "MobileWarehouseApp", "driver": "MobileWarehouseApp"}


def entries_by_id():
    out = {}
    for e in parse_nav():
        if e["type"] == "standalone":
            out[e["id"]] = (None, e)
        else:
            for it in e["items"]:
                out.setdefault(it["id"], (e, it))
    return out


def rows():
    idx = entries_by_id()
    res = []
    for glabel, gid, ids in SCOPE:
        for mid in ids:
            grp, it = idx[mid]
            tabs = [t for t in HUB_TABS.get(it.get("hub") or "", []) if not t["hidden"]]
            if mid in TAB_FILTER:
                tabs = [t for t in tabs if t["view"] in TAB_FILTER[mid]]
            targets = [(t["label"], t["view"], t["roles"]) for t in tabs] or [(it["label"], it.get("view") or mid, None)]
            for tlabel, view, troles in targets:
                vis = {}
                for r in ROLES:
                    own = role_can_see(grp["roles"], r, grp["groupId"]) if grp else True
                    menu = own and role_can_see(it["roles"], r, it["id"])
                    tab_ok = role_can_see(troles, r, view) if troles is not None or tabs else True
                    vis[r] = bool(menu and tab_ok)
                res.append({"group": glabel, "menu": it["label"], "tab": tlabel if tabs else "", "view": view, "vis": vis})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--notes", default="")
    a = ap.parse_args()
    notes = json.loads(Path(a.notes).read_text(encoding="utf-8")) if a.notes else {}
    abbr = {"admin": "adm", "manager": "mgr", "warehouse_admin": "wha", "warehouse": "wh", "sales": "sls",
            "sales_admin": "sla", "finance": "fin", "md": "md", "md_quality": "mdq", "qc": "qc",
            "sample_admin": "sma", "driver": "drv"}
    data = rows()
    lines = []
    for mode, title in (("D", "Desktop (1440 px)"), ("HP", "HP (390 × 844)")):
        lines += [f"### {title}", "", "| Grup › Menu › Tab (view) | " + " | ".join(abbr[r] for r in ROLES) + " |",
                  "|---|" + "---|" * len(ROLES)]
        for row in data:
            cells = []
            for r in ROLES:
                n = (notes.get(row["view"]) or {}).get(r) or {}
                if mode == "D":
                    cells.append(n.get("D") or ("K" if row["vis"][r] else "–"))
                    continue
                hp_default = "–"
                if row["vis"][r]:
                    full = HP_APP.get(r) is None or row["view"] in ("goods-receipts", "inspections", "makloon-orders", "md-products")
                    hp_default = "K·p" if full else "K·d"
                cells.append(n.get("HP") or hp_default)
            name = f"{row['group']} › {row['menu']}" + (f" › {row['tab']}" if row["tab"] else "") + f" (`{row['view']}`)"
            lines.append(f"| {name} | " + " | ".join(cells) + " |")
        lines.append("")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "matrix_cells.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
