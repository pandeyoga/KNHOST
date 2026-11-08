#!/usr/bin/env python3
"""Audit B3b (2026-11-09) — sensus elemen form & fitur daftar dari keluaran `b3b_fe_census.js`.

HANYA MEMBACA. Menghitung per berkas cakupan WMS-RFID:
  * pembungkus form (FormModal / DetailModal / ConfirmModal / Dialog / Sheet / inline)
  * keluarga kelas tombol (primary-button, secondary-button, btn-*, <Button size>, Tailwind bg-[#hex] buatan sendiri)
  * keluarga kelas isian (.field, .form-input, .input, Tailwind mentah) & isian tanpa label (placeholder saja)
  * komponen pemilih terikat id vs <input>/<textarea> teks
  * fitur daftar: PaginationBar / KNPager / exportConfig / kotak cari / FilterChips / StatusTabs / OptionTabs
Keluaran: tabel Markdown (stdout) + ringkasan total.

    python scripts/audit/b3b_form_census.py <census.json>
"""
import json
import re
import sys
from collections import Counter

SCOPE_FE = re.compile(
    r"^(features/(wms|rfid|inspections|transfers|mobile|logistics|samples)/|"
    r"features/inventory/(registration|lots|CycleCount|UnknownRollForm|RollCountPanel|RollReconcileTable)|"
    r"features/purchasing/(Makloon|makloon/|PurchaseReturns|ReturnDetailPanel|RollPickerModal)|"
    r"features/admin/(po/|PurchaseOrderManagement)|features/sales/(SalesReturns|Return)|"
    r"features/settings/(ReceivingOcrSettings|devices/|masters/GradeMasterView|config/Setting)|"
    r"features/manager/EscalationManagement|features/finance/interco/IntercoReturn)"
)
PICKERS = {"KNSelect", "ProductSelect", "BaseFabricPicker", "MakloonSelect", "QcRequestPicker", "LocationFields",
           "SiteSelect", "RollPicker", "KNDatePicker", "KNDateTimePicker", "KNMonthPicker", "KNTimePicker",
           "PantoneFinder", "VariantAxisPicker", "LineFilter", "UomInputConvert", "Checkbox", "Switch"}
TEXTUAL = {"Input", "input", "Textarea", "textarea", "DecimalInput", "MoneyInput"}
WRAPPERS = ("FormModal", "DetailModal", "ConfirmModal", "Dialog", "DialogContent", "Sheet", "SheetContent", "Drawer",
            "DetailDrawer", "DetailPopup")


def btn_family(b):
    cls = str(b.get("className") or "")
    if b.get("tag") == "Button":
        return f"<Button size={b.get('size') or 'default'}>"
    if "primary-button" in cls:
        return "primary-button"
    if "secondary-button" in cls:
        return "secondary-button"
    if "danger-button" in cls or "destructive" in cls:
        return "danger-button"
    if re.search(r"\bbtn(-[a-z]+)?\b", cls):
        return "btn-*"
    if "icon-button" in cls or "ghost" in cls:
        return "icon/ghost"
    if re.search(r"bg-\[#", cls) or re.search(r"border-\[#", cls):
        return "Tailwind hex buatan sendiri"
    if not cls:
        return "tanpa kelas"
    return "lain"


def input_family(c):
    cls = str(c["attrs"].get("className") or "")
    if c["tag"] not in ("input", "textarea", "select"):
        return None
    t = str(c["attrs"].get("type") or "text")
    if t in ("checkbox", "radio", "file", "hidden"):
        return None
    if re.search(r"\bfield\b", cls):
        return ".field"
    if "form-input" in cls:
        return ".form-input"
    if re.search(r"(^|\s)input(\s|$)", cls):
        return ".input"
    if "rounded" in cls or "border" in cls:
        return "Tailwind mentah"
    return "tanpa kelas"


def main():
    census = json.load(open(sys.argv[1], encoding="utf-8"))
    tot_btn, tot_inp, tot_wrap = Counter(), Counter(), Counter()
    rows = []
    tot = Counter()
    for f, rec in sorted(census["files"].items()):
        if not SCOPE_FE.match(f) or "controls" not in rec:
            continue
        ctl = rec["controls"]
        if not ctl and not rec["buttons"]:
            continue
        bf = Counter(btn_family(b) for b in rec["buttons"])
        inf = Counter(x for x in (input_family(c) for c in ctl) if x)
        wr = Counter(l["tag"] for l in rec["layout"] if l["tag"] in WRAPPERS)
        n_pick = sum(1 for c in ctl if c["tag"] in PICKERS or c["tag"].endswith(("Select", "Picker")))
        n_text = sum(1 for c in ctl if c["tag"] in TEXTUAL and str(c["attrs"].get("type") or "text") not in ("checkbox", "radio", "file", "hidden"))
        n_num = sum(1 for c in ctl if c["tag"] in ("input", "Input") and str(c["attrs"].get("type")) == "number")
        n_num_nomin = sum(1 for c in ctl if c["tag"] in ("input", "Input") and str(c["attrs"].get("type")) == "number" and "min" not in c["attrs"])
        n_dec = sum(1 for c in ctl if c["tag"] == "DecimalInput")
        n_labels = sum(1 for l in rec["layout"] if l["tag"] in ("label", "Label"))
        n_req_star = sum(1 for l in rec["layout"] if l["tag"] in ("label", "Label") and "*" in str(l["attrs"].get("text") or ""))
        n_ph_star = sum(1 for c in ctl if "*" in str(c["attrs"].get("placeholder") or ""))
        n_required = sum(1 for c in ctl if "required" in c["attrs"])
        n_maxlen = sum(1 for c in ctl if "maxLength" in c["attrs"])
        n_ph_only = sum(1 for c in ctl if c["tag"] in TEXTUAL and c["attrs"].get("placeholder") and not c["attrs"].get("aria-label"))
        lay = Counter(l["tag"] for l in rec["layout"])
        lst = {
            "PaginationBar": lay.get("PaginationBar", 0), "KNPager": lay.get("KNPager", 0),
            "exportConfig": rec["flags"].get("exportConfig", 0), "cari": rec["flags"].get("placeholderCari", 0) + lay.get("SearchBox", 0),
            "FilterChips": lay.get("FilterChips", 0), "TableFilter": lay.get("TableFilter", 0),
        }
        rows.append((f, sum(wr.values()) and ", ".join(f"{k}×{v}" for k, v in wr.items()) or "inline",
                     len(ctl), n_pick, n_text, n_num, n_num_nomin, n_dec, n_labels, n_req_star + n_ph_star, n_required,
                     n_maxlen, ", ".join(f"{k}×{v}" for k, v in bf.most_common()),
                     ", ".join(f"{k}×{v}" for k, v in inf.most_common()), lst))
        tot_btn.update(bf)
        tot_inp.update(inf)
        tot_wrap.update(wr)
        tot.update({"files": 1, "controls": len(ctl), "pickers": n_pick, "text": n_text, "number": n_num,
                    "number_nomin": n_num_nomin, "decimal": n_dec, "labels": n_labels, "required_attr": n_required,
                    "maxlength": n_maxlen, "star": n_req_star + n_ph_star, "ph_star": n_ph_star,
                    "PaginationBar": lst["PaginationBar"], "KNPager": lst["KNPager"], "exportConfig": 1 if lst["exportConfig"] else 0})
    print("| Berkas | Pembungkus | #kontrol | #pemilih | #teks | #number (tanpa min) | #DecimalInput | #label | #tanda * | #required | #maxLength | Tombol (keluarga) | Isian (kelas) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| `{r[0]}` | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} ({r[6]}) | {r[7]} | {r[8]} | {r[9]} | {r[10]} | {r[11]} | {r[12]} | {r[13]} |")
    print("\n**Total**:", dict(tot))
    print("**Keluarga tombol**:", dict(tot_btn.most_common()))
    print("**Kelas isian**:", dict(tot_inp.most_common()))
    print("**Pembungkus**:", dict(tot_wrap.most_common()))


if __name__ == "__main__":
    main()
