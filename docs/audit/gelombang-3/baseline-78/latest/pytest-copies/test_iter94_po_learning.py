"""Iter94: PO correction learning tests.
Verifies:
  1. PATCH grn line with new po_ref stores ocr_po_ref & corrected_fields includes 'po_ref'
  2. Reverting po_ref back to ai value removes 'po_ref' from corrected_fields
  3. When a non-sample OCR GRN of Cirebon Craft is turned into a sample, dn-profile.corrections includes 'Baris N nomor PO'
"""
import os, requests, pytest

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ENT = "ent_ksc"
SUP_CIREBON = "sup_44c069fa4f55"
TARGET_GRN = "grn_a8e3eedb541a"       # KSC/GRN-00009 (already a sample)
CANDIDATE_GRNS = ["grn_aeaa7ca13a57"]  # KSC/GRN-00002

@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
    assert r.status_code == 200, r.text
    return r.json()["token"]

@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}", "X-Entity-Id": ENT, "Content-Type": "application/json"}


class TestPoLearningOnGrn9:
    def test_patch_po_and_revert(self, H):
        r = requests.get(f"{BASE}/api/goods-receipts/{TARGET_GRN}", headers=H); r.raise_for_status()
        grn = r.json()
        line = grn["lines"][1]  # line 2 (index 1)
        assert line["line_no"] == 2
        ai_po = (line["read"] or {}).get("po_ref") or ""
        print(f"AI po_ref on line 2: {ai_po!r}")
        assert ai_po == "3351/SCB/0926", f"expected AI value 3351/SCB/0926 got {ai_po!r}"
        version = grn["version"]

        # Step A: change po to something different
        new_po = "3351/SCB/0926-EDIT"
        r = requests.patch(f"{BASE}/api/goods-receipts/{TARGET_GRN}/lines/2",
                           headers=H, json={"expected_version": version, "po_ref": new_po})
        assert r.status_code == 200, r.text
        grn2 = r.json()
        line2 = grn2["lines"][1]
        assert line2["read"]["po_ref"] == new_po
        assert line2.get("ocr_po_ref") == ai_po
        assert "po_ref" in (line2.get("corrected_fields") or []), f"corrected_fields={line2.get('corrected_fields')}"
        print("Step A OK: ocr_po_ref stored, po_ref in corrected_fields:", line2["corrected_fields"])
        v2 = grn2["version"]

        # Step B: revert to AI value → po_ref should be removed from corrected_fields
        r = requests.patch(f"{BASE}/api/goods-receipts/{TARGET_GRN}/lines/2",
                           headers=H, json={"expected_version": v2, "po_ref": ai_po})
        assert r.status_code == 200, r.text
        grn3 = r.json()
        line3 = grn3["lines"][1]
        assert line3["read"]["po_ref"] == ai_po
        assert "po_ref" not in (line3.get("corrected_fields") or []), f"corrected_fields={line3.get('corrected_fields')}"
        print("Step B OK: reverted, corrected_fields now:", line3.get("corrected_fields"))


class TestPoLearningToProfile:
    """Correct a PO on a non-sample Cirebon Craft OCR GRN → make sample → dn-profile.corrections includes 'Baris X nomor PO'.
    Cleanup: revert PO, delete sample. dn-profile itself is left alone."""

    def test_correct_po_then_from_grn_records_correction(self, H):
        chosen = None
        for gid in CANDIDATE_GRNS:
            r = requests.get(f"{BASE}/api/goods-receipts/{gid}", headers=H)
            if r.status_code != 200:
                continue
            g = r.json()
            if g.get("status") != "review":
                print(f"skip {gid} status={g.get('status')}")
                continue
            if g.get("sample_id") or g.get("ocr_sample_id"):
                print(f"skip {gid} already a sample"); continue
            # Find an OCR line with a po_ref
            for ln in g.get("lines") or []:
                if (ln.get("read") or {}).get("source") == "ocr":
                    chosen = (gid, g, ln); break
            if chosen: break
        if not chosen:
            pytest.skip("No eligible non-sample OCR GRN of Cirebon Craft with OCR po_ref found")

        gid, g, ln = chosen
        line_no = ln["line_no"]
        ai_po = (ln["read"] or {}).get("po_ref") or ""
        new_po = "TEST_PO/XX/9999" if not ai_po else f"{ai_po}-Z"
        print(f"Using GRN {gid} line {line_no}, AI po={ai_po!r} → new={new_po!r}")

        # Correct
        r = requests.patch(f"{BASE}/api/goods-receipts/{gid}/lines/{line_no}", headers=H,
                          json={"expected_version": g["version"], "po_ref": new_po})
        assert r.status_code == 200, r.text
        grn_patched = r.json()

        sample_id = None
        try:
            # Make sample
            r = requests.post(f"{BASE}/api/ocr-samples/from-grn/{gid}", headers=H, json={})
            assert r.status_code == 200, r.text
            sample_id = r.json().get("id")
            print("Sample created:", sample_id)

            # Fetch profiles - look for correction
            r = requests.get(f"{BASE}/api/goods-receipts/dn-profiles", headers=H); r.raise_for_status()
            profs = r.json()
            prof = next((p for p in profs if p.get("partner_id") == SUP_CIREBON), None)
            assert prof is not None, "Cirebon Craft profile missing"
            correction_texts = [c.get("field", "") + ": " + str(c.get("ocr", "")) + " → " + str(c.get("final", ""))
                                for c in (prof.get("corrections") or [])]
            print("Corrections after from-grn:")
            for c in correction_texts: print(" -", c)
            has_po = any(f"Baris {line_no} nomor PO" in c or f"Baris {line_no} po" in c.lower() for c in correction_texts)
            assert has_po, f"Expected 'Baris {line_no} nomor PO' correction, got: {correction_texts}"
        finally:
            # Cleanup: revert po
            try:
                r = requests.get(f"{BASE}/api/goods-receipts/{gid}", headers=H)
                if r.status_code == 200:
                    gg = r.json()
                    requests.patch(f"{BASE}/api/goods-receipts/{gid}/lines/{line_no}", headers=H,
                                   json={"expected_version": gg["version"], "po_ref": ai_po})
                    print("Reverted po_ref on", gid)
            except Exception as e:
                print("Revert failed:", e)
            # Delete sample
            if sample_id:
                dr = requests.delete(f"{BASE}/api/ocr-samples/{sample_id}", headers=H)
                print("Delete sample:", dr.status_code)
