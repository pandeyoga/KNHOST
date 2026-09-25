import time, datetime
from pymongo import MongoClient
db=MongoClient("mongodb://localhost:27017")["test_database"]
seen=set(str(d["_id"]) for d in db.audit_logs.find({},{"_id":1}))
end=time.time()+300
while time.time()<end:
    for d in db.audit_logs.find({},{"_id":1,"action":1,"actor":1,"entity_type":1}):
        k=str(d["_id"])
        if k not in seen:
            seen.add(k); print(datetime.datetime.utcnow().strftime("%H:%M:%S"), d.get("action"), d.get("actor"), d.get("entity_type"), flush=True)
    time.sleep(0.5)
