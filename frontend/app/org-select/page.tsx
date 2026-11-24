"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "../context/AuthContext";
import { Badge, Icon } from "../components/AppShell";
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
    const home = homeForRole(role);
    const wanted = searchParams.get("redirect") || "";
    const sameArea = wanted.startsWith("/") && wanted.split("/")[1] === home.split("/")[1];
    router.push(sameArea ? wanted : home);
  }

  if (isLoading || !isAuthenticated || !user) {
    return (
      <div style={{ textAlign: "center", marginTop: "30vh", color: "var(--secondary)" }}>
        <span style={{ display: "inline-block", animation: "pulseGlow 2s infinite", color: "var(--brand)" }}>
          <Icon name="refresh" size={24} />
        </span>
        <p style={{ marginTop: "12px", fontSize: "13px", fontWeight: 500 }}>Loading your authorized organizations…</p>
      </div>
    );
  }

  return (
    <div className="intake-body" style={{ maxWidth: "580px", margin: "6vh auto" }}>
      <div className="library-card" style={{ padding: "36px", boxShadow: "var(--shadow-lg)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
          <span className="eyebrow" style={{ color: "var(--brand)" }}>STEP 2 OF 2</span>
          <span style={{ color: "var(--line2)" }}>·</span>
          <span style={{ font: "600 10px 'JetBrains Mono', monospace", color: "var(--muted)" }}>IDENTITY VERIFIED</span>
        </div>
        <h1 style={{ margin: "6px 0 6px", font: "600 28px 'Newsreader', Georgia, serif", color: "var(--ink)" }}>Choose your workspace</h1>
        <p style={{ margin: "0 0 24px", color: "var(--secondary)", fontSize: "13px", lineHeight: 1.5 }}>
          Signed in as <b style={{ color: "var(--ink)" }}>{user.email}</b>. Ingestion pipelines and policy checks will execute in the organization enclave you select.
        </p>

        {error && (
          <p role="alert" style={{ margin: "0 0 16px", padding: "12px 14px", background: "var(--error-bg)", border: "1px solid var(--error-border)", color: "var(--error)", borderRadius: "8px", fontSize: "12px", fontWeight: 500 }}>
            {error}
          </p>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {memberships.map((m) => {
            const isSelected = m.organization_id === activeOrgId;
            return (
              <button
                key={m.organization_id}
                type="button"
                disabled={busyOrg !== null}
                onClick={() => choose(m.organization_id, m.role)}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: "14px",
                  padding: "16px 20px",
                  textAlign: "left",
                  cursor: busyOrg ? "wait" : "pointer",
                  background: isSelected ? "var(--brand-surface)" : "#FFFFFF",
                  borderRadius: "10px",
                  font: "inherit",
                  border: `1.5px solid ${isSelected ? "var(--brand)" : "var(--line)"}`,
                  boxShadow: "var(--shadow-xs)",
                  transition: "all 0.2s var(--ease-spring)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = "translateY(-1px)";
                  e.currentTarget.style.borderColor = "var(--brand)";
                  e.currentTarget.style.boxShadow = "var(--shadow-sm)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = "none";
                  e.currentTarget.style.borderColor = isSelected ? "var(--brand)" : "var(--line)";
                  e.currentTarget.style.boxShadow = "var(--shadow-xs)";
                }}
              >
                <div>
                  <b style={{ display: "block", fontSize: "14px", color: "var(--ink)", fontWeight: 600 }}>{m.organization_name || m.organization_id}</b>
                  <small style={{ color: "var(--secondary)", fontSize: "11px", marginTop: "2px", display: "block" }}>
                    {busyOrg === m.organization_id ? "Initializing workspace..." : "Open this workspace enclave →"}
                  </small>
                </div>
                <Badge tone={m.role.endsWith("ADMIN") ? "violet" : "green"}>
                  {ROLE_LABELS[m.role] || m.role}
                </Badge>
              </button>
            );
          })}
          {memberships.length === 0 && (
            <p style={{ fontSize: "13px", color: "var(--secondary)", padding: "12px", background: "var(--surface-secondary)", borderRadius: "8px" }}>
              Your account isn&apos;t a member of any organization yet. Ask an administrator to add your email.
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={() => { logout(); router.push("/login"); }}
          style={{
            marginTop: "24px",
            background: "none",
            border: "none",
            color: "var(--muted)",
            fontSize: "12px",
            fontWeight: 500,
            cursor: "pointer",
            padding: 0,
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
          }}
        >
          ← Sign out of current identity
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
