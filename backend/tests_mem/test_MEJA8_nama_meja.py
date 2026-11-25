"""MEJA-8 — nama tunggal di keluaran server."""
from __future__ import annotations
import ast
from pathlib import Path
import pytest

pytestmark = pytest.mark.anyio
ROOT = Path(__file__).resolve().parents[1]
USANG = ("Meja Finance", "Meja Admin Sample", "Meja Admin Gudang")


async def test_label_meja(klien, kepala_admin):
    assert (await klien.get("/api/finance/desk", headers=kepala_admin)).json()["desk_label"] == "Meja Keuangan"
    smp = (await klien.get("/api/sample-orders/desk", headers=kepala_admin)).json()
    assert smp["title"] == "Meja Sample" and any("Meja Keuangan" in x for x in smp["not_my_desk"])
    import role_registry as reg
    assert {c["view"]: c["label"] for c in reg.HOME_CHOICES}["warehouse-admin-desk"] == "Meja Gudang"


def test_judul_meja_saya_tunggal():
    """R9 — judul meja di layar Meja Saya selalu "Meja Saya", apa pun jenis mejanya."""
    from services import role_desk_service as svc
    assert set(svc.LABEL.values()) == {"Meja Saya"}


@pytest.mark.parametrize("rel", ["services/work_desk_service.py", "routers/sample_orders.py", "role_registry.py",
                                 "services/dispatch_payment_gate.py", "config_catalog_core.py"])
def test_tanpa_nama_usang_di_teks_tampil(rel):
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    doc = {id(n.body[0].value) for n in ast.walk(tree)
           if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
           and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    teks = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc]
    assert [t for t in teks if any(u in t for u in USANG)] == []
