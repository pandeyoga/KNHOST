"""Kartu Warna Pelanggan (PDF) — swatch, kode, versi supplier per warna + kop badan usaha aktif."""
from typing import Tuple

from jinja2 import Environment

from db import db
from core_utils import now_iso
from services.color_service import hex_to_rgb, list_customer_colors
from services.pdf_engine import render_pdf
from services.pdf_service import get_branding
from services.pdf_resolvers import fmt_date

_env = Environment(autoescape=True)
_TMPL = _env.from_string("""<!doctype html><html><head><meta charset="utf-8"><style>
@page { size:A4; margin:16mm 14mm 18mm;
  @bottom-left { content:"{{ branding.company_name }} · Kartu Warna {{ customer.name }}"; font-size:7.5pt; color:#888; }
  @bottom-right { content:"Hal. " counter(page) " / " counter(pages); font-size:7.5pt; color:#888; } }
body { font-family: 'DejaVu Sans', Arial, sans-serif; color:#1c1c1e; font-size:9pt; }
.kop { display:flex; align-items:center; gap:12px; border-bottom:3px solid #1c1c1e; padding-bottom:8px; }
.kop img { max-width:60px; max-height:60px; }
.co { font-size:15pt; font-weight:800; }
.addr { font-size:8pt; color:#555; }
h1 { font-size:17pt; margin:14px 0 2px; letter-spacing:.5px; text-transform:uppercase; }
.sub { color:#555; font-size:9pt; margin-bottom:10px; }
.sub b { color:#1c1c1e; }
table.grid { width:100%; border-collapse:separate; border-spacing:8px; margin:0 -8px; }
td.cell { width:33.3%; vertical-align:top; border:1px solid #d8d8dc; border-radius:6px; padding:0; }
td.empty { border:none; }
.sw { height:78px; border-radius:5px 5px 0 0; }
.info { padding:7px 8px 8px; }
.code { font-weight:800; font-size:10.5pt; }
.name { color:#444; margin-top:1px; }
.hex { font-family:'DejaVu Sans Mono', monospace; font-size:7.5pt; color:#777; margin-top:3px; }
.sup { margin-top:5px; border-top:1px dashed #d8d8dc; padding-top:4px; font-size:7.8pt; }
.sup .lbl { text-transform:uppercase; font-size:6.8pt; letter-spacing:.4px; color:#999; }
.sup div { margin-top:1px; }
.note { margin-top:12px; font-size:7.8pt; color:#777; border-left:3px solid #d8d8dc; padding-left:7px; }
</style></head><body>
<div class="kop">
  {% if branding.logo_src %}<img src="{{ branding.logo_src }}"/>{% endif %}
  <div><div class="co">{{ branding.company_name }}</div>
  <div class="addr">{{ branding.address }}{% if branding.phone %} · Telp {{ branding.phone }}{% endif %}{% if branding.email %} · {{ branding.email }}{% endif %}</div></div>
</div>
<h1>Kartu Warna Pelanggan</h1>
<div class="sub">Untuk <b>{{ customer.name }}</b>{% if customer.code %} ({{ customer.code }}){% endif %} · {{ colors|length }} warna · dicetak {{ printed }}</div>
<table class="grid">
{% for row in rows %}<tr>{% for c in row %}{% if c %}<td class="cell">
  <div class="sw" style="background-color: {{ c.hex }};"></div>
  <div class="info">
    <div class="code">{{ c.code }}</div>
    <div class="name">{{ c.name }}{% if c.factory_name %} · {{ c.factory_name }}{% endif %}</div>
    <div class="hex">{{ c.hex }}{% if c.rgb %} · RGB {{ c.rgb }}{% endif %}{% if c.system %} · {{ c.system }}{% endif %}</div>
    <div class="sup"><div class="lbl">Versi supplier</div>
      {% for s in c.supplier_versions %}<div><b>{{ s.supplier_name }}</b>: {{ s.supplier_color_name }} {{ s.supplier_color_code }}</div>
      {% else %}<div style="color:#999">Belum ada versi supplier</div>{% endfor %}
    </div>
  </div></td>{% else %}<td class="empty"></td>{% endif %}{% endfor %}</tr>
{% endfor %}
</table>
<div class="note">Warna pada layar dan cetakan dapat berbeda dari kain sebenarnya. Acuan akhir adalah lab dip fisik yang telah disetujui.</div>
</body></html>""")


async def render_customer_color_card(customer_id: str, entity_id: str) -> Tuple[bytes, str]:
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0, "id": 1, "name": 1, "code": 1, "entity_id": 1}) or {}
    groups = await list_customer_colors(None, customer_id)
    colors = groups[0]["colors"] if groups else []
    for c in colors:
        rgb = hex_to_rgb(c.get("hex", ""))
        c["rgb"] = ", ".join(str(x) for x in rgb) if rgb else ""
    rows = [(colors[i:i + 3] + [None, None])[:3] for i in range(0, len(colors), 3)]
    branding = await get_branding(entity_id or customer.get("entity_id"))
    html = _TMPL.render(branding=branding, customer=customer, colors=colors, rows=rows, printed=fmt_date(now_iso()))
    pdf, _ = render_pdf(html)
    return pdf, f"kartu-warna-{(customer.get('code') or customer_id)}.pdf"

