"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "../context/AuthContext";
import { Badge } from "../components/AppShell";
import { ROLE_LABELS, homeForRole } from "../lib/roles";

function OrgPicker() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, memberships, activeOrgId, isAuthenticated, isLoading, selectOrganization, logout } = useAuth();
  const [busyOrg, setBusyOrg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.replace("/login");
  }, [isLoading, isAuthenticated, router]);

  async function choose(organizationId: string, role: string) {
    setBusyOrg(organizationId);
    setError(null);
    const result = await selectOrganization(organizationId);
    if (!result.success) {
      setError(result.error || "Could not open this organization.");
      setBusyOrg(null);
      return;
    }
    // Go back to the page the user wanted only if it belongs to the area their role can use.
    const home = homeForRole(role);
    const wanted = searchParams.get("redirect") || "";
    const sameArea = wanted.startsWith("/") && wanted.split("/")[1] === home.split("/")[1];
    router.push(sameArea ? wanted : home);
  }

  if (isLoading || !isAuthenticated || !user) {
    return <p style={{ textAlign: "center", marginTop: "30vh", color: "var(--muted)" }}>Loading your organizations…</p>;
  }

  return (
    <div className="intake-body" style={{ maxWidth: "560px", margin: "8vh auto" }}>
      <div className="library-card" style={{ padding: "28px" }}>
        <span className="eyebrow">STEP 2 OF 2</span>
        <h1 style={{ margin: "6px 0 4px", font: "26px 'Newsreader', serif" }}>Choose your organization</h1>
        <p style={{ margin: "0 0 20px", color: "var(--muted)", fontSize: "12px", lineHeight: 1.5 }}>
          Signed in as <b>{user.email}</b>. Everything you upload and every policy check will use the organization you pick.
        </p>

        {error && (
          <p role="alert" style={{ margin: "0 0 14px", padding: "10px 12px", background: "var(--red-bg, #fef2f2)", color: "var(--red, #dc2626)", borderRadius: "5px", fontSize: "12px" }}>
            {error}
          </p>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {memberships.map((m) => (
            <button
              key={m.organization_id}
              type="button"
              disabled={busyOrg !== null}
              onClick={() => choose(m.organization_id, m.role)}
              style={{
                display: "flex", justifyContent: "space-between", alignItems: "center", gap: "12px",
                padding: "14px 16px", textAlign: "left", cursor: busyOrg ? "wait" : "pointer",
                background: "white", borderRadius: "6px", font: "inherit",
                border: `1px solid ${m.organization_id === activeOrgId ? "var(--ink, #1f2328)" : "var(--line2, #e0ddd5)"}`,
              }}
            >
              <span>
                <b style={{ display: "block", fontSize: "14px" }}>{m.organization_name || m.organization_id}</b>
                <small style={{ color: "var(--muted)" }}>{busyOrg === m.organization_id ? "Opening…" : "Open this organization →"}</small>
              </span>
              <Badge tone={m.role.endsWith("ADMIN") ? "violet" : "green"}>{ROLE_LABELS[m.role] || m.role}</Badge>
            </button>
          ))}
          {memberships.length === 0 && (
            <p style={{ fontSize: "12px", color: "var(--muted)" }}>
              Your account isn&apos;t a member of any organization yet. Ask an administrator to add your email.
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={() => { logout(); router.push("/login"); }}
          style={{ marginTop: "20px", background: "none", border: "none", color: "var(--muted)", fontSize: "12px", cursor: "pointer", padding: 0 }}
        >
          Sign out
        </button>
      </div>
    </div>
  );
}

export default function OrgSelectPage() {
  return (
    <Suspense fallback={null}>
      <OrgPicker />
    </Suspense>
  );
}
