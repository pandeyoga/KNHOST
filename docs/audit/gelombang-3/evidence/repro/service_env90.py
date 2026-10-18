"""Original-service audit context without importing the entire HTTP app.

Only a unique task-owned localhost DB is used. run_isolated.py records original
source arcs and enforces the outbound boundary. Direct fixtures are labelled;
service observations are not relabelled public producer/browser verification.
"""
import os,sys,uuid
from pathlib import Path
REPO=Path(os.environ['KNHOST_REPO']);sys.path[:0]=[str(REPO/'backend'),str(REPO)]
DBNAME='knhost_audit_services90_'+uuid.uuid4().hex
os.environ.update(DB_NAME=DBNAME,MONGO_URL='mongodb://127.0.0.1:27919/?serverSelectionTimeoutMS=3000',PYTHON_DOTENV_DISABLED='1',KN_DEMO_DATA='false')
from db import db,client
async def setup(template=False):
 assert db.name==DBNAME and await db.users.count_documents({})==0
 await client.admin.command('ping')
 if template:
  src=client['knhost_audit_native90_template']
  assert await src.users.count_documents({})>0
  for name in await src.list_collection_names():
   docs=await src[name].find({}).to_list(None)
   if docs:await db[name].insert_many(docs)
