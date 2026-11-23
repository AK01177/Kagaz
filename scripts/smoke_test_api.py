"""Live API smoke test: logs in as each demo role and checks every endpoint group.

Needs the backend running on :8001 and demo accounts (python -m app.db.seed_demo).
Run from the repo root:  python scripts/smoke_test_api.py
"""
import os
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
ENV = dotenv_values(ROOT / "backend" / ".env")
API = os.environ.get("API_URL", "http://127.0.0.1:8001")
PASSWORD = "KagazDemo#2026"
SAMPLE = ROOT / "sample" / "invoice_1.pdf"
results = []


def login(role):
    r = httpx.post(f"{ENV['SUPABASE_URL']}/auth/v1/token?grant_type=password",
                   headers={"apikey": ENV["SUPABASE_ANON_KEY"]},
                   json={"email": f"demo.{role}@kagaz-demo.test", "password": PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"} if r.status_code == 200 else None


def call(label, who, method, path, expect, **kw):
    r = httpx.request(method, API + path, headers=H[who], timeout=120, **kw)
    ok = r.status_code in (expect if isinstance(expect, tuple) else (expect,))
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {label:<48} {who:<9} {method:<5} -> {r.status_code}"
          + ("" if ok else f"  (expected {expect}) {r.text[:150]}"))
    try:
        return r.json()
    except ValueError:
        return {}


H = {r: login(r) for r in ["sysadmin", "orgadmin", "reviewer", "approver", "submitter", "submitter2", "other", "multi"]}
print("logins:", {k: bool(v) for k, v in H.items()})
if not all(H.values()):
    sys.exit("Login failed - run: cd backend && python -m app.db.seed_demo")

print("\n== Auth ==")
for role in H:
    me = call("GET /auth/me", role, "GET", "/api/auth/me", 200)
    print(f"      role={me.get('role')} org={str(me.get('organization_id'))[:8]}")
ms = call("GET /auth/memberships", "submitter", "GET", "/api/auth/memberships", 200)
print(f"      org name in memberships: {ms.get('memberships', [{}])[0].get('organization_name')}")
r = httpx.get(API + "/api/documents"); results.append(r.status_code == 401)
print(f"{'PASS' if r.status_code == 401 else 'FAIL'}  no token -> 401                                  anon      GET   -> {r.status_code}")

print("\n== Organization picker (one person, two organizations) ==")
mm = call("memberships lists both orgs", "multi", "GET", "/api/auth/memberships", 200)
orgs = {m["organization_name"]: m for m in mm.get("memberships", [])}
print("      " + ", ".join(f"{n} as {m['role']}" for n, m in orgs.items()))
ok = set(orgs) == {"Kagaz Demo", "Kagaz Demo Two"}
results.append(ok)
print(f"{'PASS' if ok else 'FAIL'}  two organizations, with names")
for name, role in (("Kagaz Demo", "SUBMITTER"), ("Kagaz Demo Two", "REVIEWER")):
    if name not in orgs:
        continue
    r = httpx.get(API + "/api/auth/me", timeout=60,
                  headers={**H["multi"], "X-Organization-Id": orgs[name]["organization_id"]})
    good = r.status_code == 200 and r.json().get("role") == role
    results.append(good)
    print(f"{'PASS' if good else 'FAIL'}  choose {name} -> role {r.json().get('role')}")
r = httpx.get(API + "/api/auth/me", headers={**H["multi"], "X-Organization-Id": "not-my-org"}, timeout=60)
results.append(r.status_code == 403)
print(f"{'PASS' if r.status_code == 403 else 'FAIL'}  organization the user is NOT in -> {r.status_code}")

print("\n== Role access (admin / policies / queues) ==")
call("admin org (org admin)", "orgadmin", "GET", "/api/admin/organization", 200)
call("admin users (org admin)", "orgadmin", "GET", "/api/admin/users", 200)
call("admin users (system admin)", "sysadmin", "GET", "/api/admin/users", 200)
call("admin users DENIED (submitter)", "submitter", "GET", "/api/admin/users", 403)
call("admin users DENIED (reviewer)", "reviewer", "GET", "/api/admin/users", 403)
call("list orgs (system admin)", "sysadmin", "GET", "/api/admin/organizations", 200)
call("list orgs DENIED (org admin)", "orgadmin", "GET", "/api/admin/organizations", 403)
call("org admin sees NO documents", "orgadmin", "GET", "/api/documents", 403)
call("policies list (submitter can read)", "submitter", "GET", "/api/policies", 200)
call("policy create DENIED (submitter)", "submitter", "POST", "/api/policies", 403, json={"name": "x"})
call("review queue (reviewer)", "reviewer", "GET", "/api/documents/workflow/review-queue", 200)
call("review queue DENIED (submitter)", "submitter", "GET", "/api/documents/workflow/review-queue", 403)
call("approval queue (approver)", "approver", "GET", "/api/documents/workflow/approval-queue", 200)
call("approval queue DENIED (reviewer)", "reviewer", "GET", "/api/documents/workflow/approval-queue", 403)
call("notifications (submitter)", "submitter", "GET", "/api/notifications", 200)

print("\n== Document pipeline ==")
call("upload DENIED (reviewer)", "reviewer", "POST", "/api/documents", 403,
     files={"file": ("invoice_1.pdf", SAMPLE.read_bytes(), "application/pdf")})
call("upload bad type rejected", "submitter", "POST", "/api/documents", (400, 415, 422),
     files={"file": ("x.exe", b"MZ", "application/octet-stream")})
doc = call("upload PDF (submitter)", "submitter", "POST", "/api/documents", 201,
           files={"file": ("invoice_1.pdf", SAMPLE.read_bytes(), "application/pdf")})
doc_id = doc.get("id") or doc.get("document_id")
print(f"      doc_id={doc_id}  status={doc.get('status')}  type={doc.get('document_type') or doc.get('category')}")
if doc_id:
    d = f"/api/documents/{doc_id}"
    call("list documents", "submitter", "GET", "/api/documents", 200)
    call("get document", "submitter", "GET", d, 200)
    call("download file", "submitter", "GET", d + "/file", 200)
    call("other org CANNOT read document", "other", "GET", d, (403, 404))
    call("other submitter CANNOT read document", "submitter2", "GET", d, 403)
    call("other submitter list is empty", "submitter2", "GET", "/api/documents", 200)
    call("reviewer CANNOT see unsubmitted doc", "reviewer", "GET", d, 403)
    call("approver CANNOT see unsubmitted doc", "approver", "GET", d, 403)
    call("org admin CANNOT read doc", "orgadmin", "GET", d, 403)
    call("validate", "submitter", "POST", d + "/validate", (200, 202))
    call("validate-policy", "submitter", "POST", d + "/validate-policy", (200, 202, 404, 409))
    call("assistant query", "submitter", "POST", d + "/assistant/query", 200, json={"question": "What is the invoice total?"})
    call("audit trail", "submitter", "GET", f"/api/audit/{doc_id}", 200)
    call("workflow status", "submitter", "GET", d + "/workflow", 200)

    print("\n== Review -> approval workflow ==")
    revs = call("eligible reviewers", "submitter", "GET", "/api/documents/workflow/reviewers", 200)
    call("submit for review", "submitter", "POST", d + "/submit", 200, json={"auto_route": True})
    call("classify DENIED (submitter)", "submitter", "POST", d + "/classify", 403)
    call("classify (assigned reviewer)", "reviewer", "POST", d + "/classify", (200, 202))
    call("extract DENIED (submitter)", "submitter", "POST", d + "/extract", 403)
    call("extract (assigned reviewer)", "reviewer", "POST", d + "/extract", (200, 202))
    call("get extraction (reviewer)", "reviewer", "GET", d + "/extract", 200)
    call("approver CANNOT see doc still in review", "approver", "GET", d, (200, 403))
    call("review queue has doc", "reviewer", "GET", "/api/documents/workflow/review-queue", 200)
    call("review detail", "reviewer", "GET", d + "/review", 200)
    call("add comment", "reviewer", "POST", d + "/comments", 201, json={"comment": "Looks fine"})
    call("correct classification (valid)", "reviewer", "PATCH", d + "/classification", 200, json={"category": "financial", "notes": "ok"})
    call("invalid category rejected", "reviewer", "PATCH", d + "/classification", 422, json={"category": "Verified Document", "notes": "x"})
    call("submit for approval", "reviewer", "POST", d + "/submit-for-approval", 200, json={"auto_route": True})
    call("approval queue", "approver", "GET", "/api/documents/workflow/approval-queue", 200)
    call("approve DENIED (reviewer)", "reviewer", "POST", d + "/approve", 403, json={"comment": "x"})
    call("approve (approver)", "approver", "POST", d + "/approve", 200, json={"comment": "Approved"})
    call("final workflow status", "submitter", "GET", d + "/workflow", 200)
    call("audit trail after workflow", "approver", "GET", f"/api/audit/{doc_id}", 200)

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
