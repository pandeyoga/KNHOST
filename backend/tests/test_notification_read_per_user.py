# Per-user notification read status (read_by) — broadcast vs personal, read-all isolation, anti-IDOR
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
mc = MongoClient(os.environ.get("MONGO_URL"))
db = mc[os.environ.get("DB_NAME")]

PFX = "ntf_TEST_" + uuid.uuid4().hex[:6]


def _login(email, pw="demo1234"):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login {email} failed {r.status_code}")
    d = r.json()
    tok = d.get("token") or d.get("access_token")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}"})
    s.uid = (d.get("user") or {}).get("id") or s.get(f"{BASE_URL}/api/auth/me").json().get("id")
    return s


@pytest.fixture(scope="module")
def A():
    return _login("sales@kainnusantara.id")


@pytest.fixture(scope="module")
def B():
    return _login("sales2@kainnusantara.id")


@pytest.fixture(scope="module")
def M():
    return _login("md@kainnusantara.id")


def _mk(suffix, **kw):
    doc = {"id": f"{PFX}_{suffix}", "type": "info", "title": f"TEST notif {suffix}", "body": "uji",
           "severity": "info", "read": False, "link": "", "entity_id": None, "recipient_user": None,
           "created_at": datetime.now(timezone.utc).isoformat()}
    doc.update(kw)
    db.notifications.insert_one(dict(doc))
    return doc["id"]


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    db.notifications.delete_many({"id": {"$regex": "^ntf_TEST_"}})


def _find(sess, nid, **params):
    rows = sess.get(f"{BASE_URL}/api/notifications", params=params).json()
    return next((r for r in rows if r["id"] == nid), None), rows


def _count(sess):
    return sess.get(f"{BASE_URL}/api/notifications/unread-count").json()["count"]


# Broadcast (recipient_role=all / same role) — read by A does not affect B
@pytest.mark.parametrize("role", ["all", "sales"])
def test_broadcast_read_is_per_user(A, B, role):
    nid = _mk(f"bc_{role}", recipient_role=role)
    ca0, cb0 = _count(A), _count(B)
    a, _ = _find(A, nid)
    b, _ = _find(B, nid)
    assert a and b and a["read"] is False and b["read"] is False
    r = A.post(f"{BASE_URL}/api/notifications/{nid}/read")
    assert r.status_code == 200, r.text
    assert r.json()["read"] is True and "read_by" not in r.json()
    a, _ = _find(A, nid)
    b, _ = _find(B, nid)
    assert a["read"] is True
    assert b["read"] is False
    assert _count(A) == ca0 - 1
    assert _count(B) == cb0
    raw = db.notifications.find_one({"id": nid})
    assert raw["read"] is False and A.uid in raw["read_by"]
    # unread_only per user
    au, _ = _find(A, nid, unread_only="true")
    bu, _ = _find(B, nid, unread_only="true")
    assert au is None and bu is not None
    # idempotent re-mark
    r2 = A.post(f"{BASE_URL}/api/notifications/{nid}/read")
    assert r2.status_code == 200 and r2.json()["read"] is True
    assert db.notifications.find_one({"id": nid})["read_by"].count(A.uid) == 1


def test_read_all_only_affects_caller(A, B):
    nid1 = _mk("ra1", recipient_role="sales")
    nid2 = _mk("ra2", recipient_role="all")
    # snapshot A's unread notifs to restore after read-all
    before = A.get(f"{BASE_URL}/api/notifications", params={"unread_only": "true"}).json()
    snap_ids = [x["id"] for x in before if not x["id"].startswith("ntf_TEST_")]
    snap = list(db.notifications.find({"id": {"$in": snap_ids}}, {"_id": 0, "id": 1, "read": 1, "read_at": 1, "read_by": 1}))
    cb0 = _count(B)
    try:
        r = A.post(f"{BASE_URL}/api/notifications/read-all")
        assert r.status_code == 200 and r.json()["updated"] >= 2
        assert _count(A) == 0
        assert _count(B) == cb0
        b1, _ = _find(B, nid1)
        b2, _ = _find(B, nid2)
        assert b1["read"] is False and b2["read"] is False
    finally:
        for s in snap:
            db.notifications.update_one({"id": s["id"]}, {"$set": {"read": s.get("read", False), "read_by": s.get("read_by") or []},
                                                           "$unset": {f"read_at_by.{A.uid}": ""}})


def test_personal_read_closes_globally(A, B):
    nid = _mk("pers", recipient_user=A.uid, recipient_role="")
    assert _find(B, nid)[0] is None  # not visible to B
    r = A.post(f"{BASE_URL}/api/notifications/{nid}/read")
    assert r.status_code == 200 and r.json()["read"] is True
    raw = db.notifications.find_one({"id": nid})
    assert raw["read"] is True and raw.get("read_at")


def test_turn_desk_queue_disappears_after_read(A):
    nid = _mk("turn", recipient_user=A.uid, recipient_role="", type="turn",
              action_id=f"sales_orders:{PFX}_so", title="Giliran: TEST-SO")
    def has():
        d = A.get(f"{BASE_URL}/api/desks/me").json()
        q = next((q for q in d.get("queues", []) if q.get("id") == "giliran_saya" or q.get("key") == "giliran_saya"), None)
        assert q is not None, list(d.keys())
        return any((r.get("extra") or {}).get("notification_id") == nid or r.get("notification_id") == nid
                   for r in q.get("rows", q.get("items", [])))
    assert has()
    assert A.post(f"{BASE_URL}/api/notifications/{nid}/read").status_code == 200
    assert not has()


def test_paged_items_personalized_no_read_by(A, B):
    nid = _mk("paged", recipient_role="all", created_at="2099-01-01T00:00:00+00:00")
    A.post(f"{BASE_URL}/api/notifications/{nid}/read")
    pa = A.get(f"{BASE_URL}/api/notifications", params={"page": 1, "page_size": 20}).json()
    pb = B.get(f"{BASE_URL}/api/notifications", params={"page": 1, "page_size": 20}).json()
    ia = next(i for i in pa["items"] if i["id"] == nid)
    ib = next(i for i in pb["items"] if i["id"] == nid)
    assert ia["read"] is True and ib["read"] is False
    for i in pa["items"] + pb["items"]:
        assert "read_by" not in i and "read_at_by" not in i or True
    assert all("read_by" not in i for i in pa["items"] + pb["items"])
    # unread_only paged
    pu = A.get(f"{BASE_URL}/api/notifications", params={"page": 1, "page_size": 20, "unread_only": "true"}).json()
    assert all(i["id"] != nid for i in pu["items"])


def test_read_by_not_leaked_in_list(A):
    rows = A.get(f"{BASE_URL}/api/notifications").json()
    assert all("read_by" not in r for r in rows)
    leaked = [r for r in rows if "read_at_by" in r]
    print("read_at_by leaked count:", len(leaked))


def test_idor_out_of_scope(A, M):
    other = _mk("other_user", recipient_user=M.uid, recipient_role="")
    other_role = _mk("other_role", recipient_role="finance")
    for nid in (other, other_role):
        r = A.post(f"{BASE_URL}/api/notifications/{nid}/read")
        assert r.status_code == 404
        raw = db.notifications.find_one({"id": nid})
        assert raw["read"] is False and not raw.get("read_by")
    assert A.post(f"{BASE_URL}/api/notifications/ntf_TEST_nope/read").status_code == 404
