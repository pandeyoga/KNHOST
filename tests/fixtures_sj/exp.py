import asyncio, json, sys, io
from pathlib import Path
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv; load_dotenv("/app/backend/.env")
from PIL import Image
from services.goods_receipt_ocr_service import ocr_config, _jpeg_part
from services.ocr_openai_client import extract
async def one(f, rot, scale, cfg):
    img = Image.open(f)
    if rot: img = img.rotate(rot, expand=True)
    if scale != 1: img = img.resize((img.width*scale, img.height*scale), Image.LANCZOS)
    r = await extract([_jpeg_part(img, 2048)], 1, model="gpt-6-sol", reasoning_effort="low", max_output_tokens=6000, extract_packing_list=True)
    d = r["data"]
    return f"== {Path(f).name} rot={rot} x{scale} in={r['usage']['input']}\n" + json.dumps({"header": d["header"], "lines": d["lines"], "totals": d["totals"]}, ensure_ascii=False)[:2500]
async def main():
    cfg = await ocr_config("")
    f = sys.argv[1]
    res = await asyncio.gather(*[one(f, r, s, cfg) for r, s in [(0,1),(90,1),(90,2),(-90,2)]])
    print("\n".join(res))
asyncio.run(main())
