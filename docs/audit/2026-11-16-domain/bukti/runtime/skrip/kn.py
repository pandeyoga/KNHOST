import requests, json, sys
B="http://localhost:8001/api"
_tok={}
def tok(role="admin"):
    em={"whadmin":"whadmin"}.get(role,role)+"@kainnusantara.id"
    if role not in _tok:
        r=requests.post(B+"/auth/login",json={"email":em,"password":"demo12345"}); _tok[role]=r.json()["token"]
    return _tok[role]
def call(m,p,role="admin",body=None,show=350,ent=None,q=None):
    h={"Authorization":"Bearer "+tok(role)}
    if ent: h["X-Entity-Id"]=ent
    r=requests.request(m,B+p,headers=h,json=body,params=q)
    try: j=r.json()
    except Exception: j=r.text
    print(f"[{role}] {m} {p} -> {r.status_code} {json.dumps(j,default=str,ensure_ascii=False)[:show]}")
    return r.status_code,j
def db():
    import os
    from dotenv import load_dotenv; load_dotenv('/app/backend/.env')
    from pymongo import MongoClient
    return MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
