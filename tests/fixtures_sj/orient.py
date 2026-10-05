import os as _o; EFF=_o.environ.get("EFF","low"); DET=_o.environ.get("DET","low")
import asyncio, os, sys, io, base64, json
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv; load_dotenv("/app/backend/.env")
from PIL import Image
from openai import AsyncOpenAI
c = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
SCHEMA = {"type":"object","properties":{"rotate_cw":{"type":"integer","enum":[0,90,180,270]}},"required":["rotate_cw"],"additionalProperties":False}
async def one(f, model):
    img = Image.open(f).convert("RGB"); img.thumbnail((768,768)); b = io.BytesIO(); img.save(b, "JPEG", quality=80)
    r = await c.responses.create(model=model, store=False, max_output_tokens=3000, reasoning={"effort":EFF},
        instructions="Photo of a printed document. How many degrees must the image be rotated CLOCKWISE so the main printed text reads normally left-to-right, top-to-bottom?",
        input=[{"role":"user","content":[{"type":"input_image","image_url":"data:image/jpeg;base64,"+base64.b64encode(b.getvalue()).decode(),"detail":DET}]}],
        text={"format":{"type":"json_schema","name":"orient","schema":SCHEMA,"strict":True}})
    return f"{f[-10:]} {EFF} {DET} {r.status} {r.output_text} in={r.usage.input_tokens} out={r.usage.output_tokens}"
async def main():
    print("\n".join(await asyncio.gather(*[one(f"/app/tests/fixtures_sj/sj{i}.jpeg", m) for i in range(1,6) for m in ("gpt-6-luna",)])))
asyncio.run(main())
