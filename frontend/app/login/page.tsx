"use client";

import React, { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AppShell, Button, Badge, Icon } from "../components/AppShell";
import { useAuth } from "../context/AuthContext";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    user,
    activeOrgId,
    memberships,
    isAuthenticated,
    sessionExpired,
    login,
    logout,
    switchOrganization,
    clearSessionExpiredNotice,
  } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [orgInput, setOrgInput] = useState("");
  const [loading, setLoading] = useState(false);
  const redirectPath = searchParams.get("redirect") || "/documents";
  const wasExpired = searchParams.get("session_expired") === "true" || sessionExpired;

  const [notice, setNotice] = useState<{
    type: "success" | "error" | "warning";
    message: string;
  } | null>(() =>
    wasExpired
      ? {
          type: "warning",
          message:
            "Your session has expired or is invalid. Please sign in again to continue working in your organization workspace.",
        }
      : null
  );

  useEffect(() => {
    if (sessionExpired) {
      const timer = setTimeout(() => {
        setNotice({
          type: "warning",
          message:
            "Your session has expired or is invalid. Please sign in again to continue working in your organization workspace.",
        });
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [sessionExpired]);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setNotice(null);

    const loginEmail = email.trim().toLowerCase();
    if (!loginEmail || !password) {
      setNotice({ type: "error", message: "Email and password are required." });
      setLoading(false);
      return;
    }

    const result = await login(loginEmail, password, orgInput || undefined);
    setLoading(false);

    if (!result.success) {
      setNotice({
        type: "error",
        message: result.error || "Authentication failed. Please verify your credentials.",
      });
      return;
    }

    clearSessionExpiredNotice();
    setPassword("");
    setNotice({
      type: "success",
      message: "Authentication successful! Redirecting to workspace...",
    });

    setTimeout(() => {
      router.push(redirectPath);
    }, 600);
  }

  async function handleOrgSwitch(targetOrgId: string) {
    setNotice(null);
    const result = await switchOrganization(targetOrgId);
    if (!result.success) {
      setNotice({
        type: "error",
        message: result.error || "Failed to switch active organization.",
      });
    } else {
      setNotice({
        type: "success",
        message: `Active organization context switched to ${targetOrgId}.`,
      });
    }
  }

  function handleLogout() {
    logout();
    setNotice({ type: "success", message: "Signed out successfully." });
  }

  const roleColor = (role?: string) => {
    switch (role) {
      case "SYSTEM_ADMIN":
      case "ORG_ADMIN":
        return "violet";
      case "APPROVER":
      case "REVIEWER":
        return "green";
      case "COMPLIANCE":
      case "AUDITOR":
        return "amber";
      default:
        return "green";
    }
  };

  return (
    <div className="intake-body" style={{ maxWidth: "720px" }}>
      {notice && (
        <div
          style={{
            padding: "12px 16px",
            background:
              notice.type === "success"
                ? "var(--green-bg, #f0fdf4)"
                : notice.type === "warning"
                ? "var(--amber-bg, #fffbeb)"
                : "var(--red-bg, #fef2f2)",
            border: `1px solid ${
              notice.type === "success"
                ? "var(--green, #15803d)"
                : notice.type === "warning"
                ? "var(--amber, #b45309)"
                : "var(--red, #dc2626)"
            }`,
            color:
              notice.type === "success"
                ? "var(--green, #15803d)"
                : notice.type === "warning"
                ? "var(--amber, #b45309)"
                : "var(--red, #dc2626)",
            borderRadius: "6px",
            marginBottom: "20px",
            fontSize: "12px",
            lineHeight: 1.5,
          }}
        >
          <b>
            {notice.type === "success"
              ? "Session Updated:"
              : notice.type === "warning"
              ? "Session Notification:"
              : "Authentication Failed:"}
          </b>{" "}
          {notice.message}
        </div>
      )}

      {isAuthenticated && user ? (
        <div
          className="library-card"
          style={{ marginTop: 0, padding: "24px", marginBottom: "24px" }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              flexWrap: "wrap",
              gap: "12px",
            }}
          >
            <div>
              <span className="eyebrow">ACTIVE CREDENTIALS</span>
              <h2 style={{ margin: "6px 0 2px", font: "22px 'Newsreader', serif" }}>
                {user.name}
              </h2>
              <p style={{ margin: 0, color: "var(--muted)", fontSize: "11px" }}>
                <code>{user.email}</code> · User ID: <code>{user.user_id}</code>
              </p>
            </div>
            <Badge tone={roleColor(user.role)}>{user.role}</Badge>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "12px",
              margin: "20px 0",
              padding: "14px",
              background: "var(--side, #f8f7f4)",
              borderRadius: "6px",
              fontSize: "11px",
            }}
          >
            <div>
              <span style={{ color: "var(--muted)", display: "block" }}>Active Organization</span>
              <b>{activeOrgId || user.organization_id}</b>
            </div>
            <div>
              <span style={{ color: "var(--muted)", display: "block" }}>Membership Role</span>
              <b>{user.role}</b>
            </div>
            <div>
              <span style={{ color: "var(--muted)", display: "block" }}>Auth Mechanism</span>
              <b>Signed JWT Bearer Token</b>
            </div>
          </div>

          {/* Multi-Organization Switcher if user has multiple memberships */}
          {memberships.length > 1 && (
            <div
              style={{
                marginBottom: "20px",
                padding: "16px",
                border: "1px solid var(--line2, #e0ddd5)",
                borderRadius: "6px",
                background: "white",
              }}
            >
              <label
                style={{
                  display: "block",
                  fontSize: "11px",
                  fontWeight: 600,
                  marginBottom: "6px",
                  color: "var(--ink)",
                }}
              >
                Switch Active Organization Context ({memberships.length} available)
              </label>
              <p style={{ fontSize: "11px", color: "var(--muted)", margin: "0 0 10px" }}>
                Select an organization you belong to. The backend strictly validates membership before granting access.
              </p>
              <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
                <select
                  value={activeOrgId || user.organization_id}
                  onChange={(e) => handleOrgSwitch(e.target.value)}
                  style={{
                    height: "36px",
                    padding: "0 12px",
                    fontSize: "12px",
                    border: "1px solid var(--line2, #e0ddd5)",
                    borderRadius: "5px",
                    background: "white",
                    minWidth: "260px",
                    cursor: "pointer",
                  }}
                  aria-label="Select organization"
                >
                  {memberships.map((m) => (
                    <option key={m.organization_id} value={m.organization_id}>
                      {m.organization_id} — Role: {m.role}
                    </option>
                  ))}
                </select>
                <span style={{ fontSize: "11px", color: "var(--muted)" }}>
                  Current active context: <b>{activeOrgId || user.organization_id}</b>
                </span>
              </div>
            </div>
          )}

          <div
            style={{
              display: "flex",
              gap: "10px",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
            }}
          >
            <Button variant="secondary" onClick={handleLogout}>
              Sign Out of Workspace
            </Button>
            <Link
              href={redirectPath}
              className="btn primary"
              style={{ textDecoration: "none", fontSize: "12px" }}
            >
              Continue to Workspace →
            </Link>
          </div>
        </div>
      ) : null}

      <div className="library-card" style={{ marginTop: 0, padding: "24px" }}>
        <span className="eyebrow">ENTERPRISE AUTHENTICATION</span>
        <h2 style={{ margin: "6px 0 16px", font: "20px 'Newsreader', serif" }}>
          {isAuthenticated ? "Sign in with a different account" : "Sign In to Kagaz"}
        </h2>

        <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div>
            <label
              htmlFor="email-input"
              style={{ display: "block", fontSize: "11px", fontWeight: 500, marginBottom: "6px" }}
            >
              Work Email Address
            </label>
            <input
              id="email-input"
              type="email"
              required
              placeholder="user@organization.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{
                width: "100%",
                height: "36px",
                border: "1px solid var(--line2, #e0ddd5)",
                borderRadius: "5px",
                padding: "0 12px",
                background: "white",
                fontSize: "12px",
              }}
            />
          </div>

          <div>
            <label
              htmlFor="password-input"
              style={{ display: "block", fontSize: "11px", fontWeight: 500, marginBottom: "6px" }}
            >
              Password
            </label>
            <input
              id="password-input"
              type="password"
              required
              placeholder="••••••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{
                width: "100%",
                height: "36px",
                border: "1px solid var(--line2, #e0ddd5)",
                borderRadius: "5px",
                padding: "0 12px",
                background: "white",
                fontSize: "12px",
              }}
            />
          </div>

          <div>
            <label
              htmlFor="org-input"
              style={{ display: "block", fontSize: "11px", fontWeight: 500, marginBottom: "6px" }}
            >
              Target Organization ID <span style={{ color: "var(--muted)", fontWeight: "normal" }}>(Optional)</span>
            </label>
            <input
              id="org-input"
              type="text"
              placeholder="e.g. org_kagaz_primary or leave blank for primary"
              value={orgInput}
              onChange={(e) => setOrgInput(e.target.value)}
              style={{
                width: "100%",
                height: "36px",
                border: "1px solid var(--line2, #e0ddd5)",
                borderRadius: "5px",
                padding: "0 12px",
                background: "white",
                fontSize: "12px",
              }}
            />
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginTop: "8px",
              flexWrap: "wrap",
              gap: "12px",
            }}
          >
            <span style={{ fontSize: "11px", color: "var(--muted)" }}>
              Backend strictly validates organization tenant isolation.
            </span>
            <Button type="submit" variant="primary" icon="check" disabled={loading}>
              {loading ? "Authenticating..." : "Authenticate Session →"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <AppShell>
      <header className="page-head">
        <div className="crumb">
          <Icon name="book" size={14} /> Workspace <span>/</span> Access &amp; Authentication
          <div className="sync">
            <span className="brand-dot" /> Identity Verified
          </div>
        </div>
        <div className="head-main">
          <div>
            <h1>Session &amp; Credentials</h1>
            <p className="subline">ROLE-BASED GOVERNANCE · SIGNED JWT AUTHORIZATION</p>
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <Link href="/documents" className="btn secondary" style={{ textDecoration: "none" }}>
              Intake Desk →
            </Link>
            <Link href="/review" className="btn primary" style={{ textDecoration: "none" }}>
              Review Desk →
            </Link>
          </div>
        </div>
      </header>

      <Suspense fallback={<div style={{ padding: "32px", fontSize: "12px" }}>Loading session form...</div>}>
        <LoginForm />
      </Suspense>
    </AppShell>
  );
}
