import asyncio, os, sys, io, base64, json
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv; load_dotenv("/app/backend/.env")
from PIL import Image
from openai import AsyncOpenAI
c = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
PROMPT = sys.argv[1] if len(sys.argv) > 1 else "Photo of a printed document. How many degrees must the image be rotated CLOCKWISE so the main printed text reads normally left-to-right, top-to-bottom?"
SCHEMA = {"type":"object","properties":{"rotate_cw":{"type":"integer","enum":[0,90,180,270]}},"required":["rotate_cw"],"additionalProperties":False}
async def one(f, model, eff):
    img = Image.open(f).convert("RGB"); img.thumbnail((1024,1024)); b = io.BytesIO(); img.save(b, "JPEG", quality=80)
    r = await c.responses.create(model=model, store=False, max_output_tokens=4000, reasoning={"effort":eff}, instructions=PROMPT,
        input=[{"role":"user","content":[{"type":"input_image","image_url":"data:image/jpeg;base64,"+base64.b64encode(b.getvalue()).decode(),"detail":"high"}]}],
        text={"format":{"type":"json_schema","name":"orient","schema":SCHEMA,"strict":True}})
    return json.loads(r.output_text)["rotate_cw"], r.usage.output_tokens
async def main():
    for model, eff in [("gpt-6-luna","low"),("gpt-6-luna","medium"),("gpt-6-sol","low")]:
        for i in (1,4,5):
            res = await asyncio.gather(*[one(f"sj{i}.jpeg", model, eff) for _ in range(3)])
            print(model, eff, f"sj{i}", res)
asyncio.run(main())
