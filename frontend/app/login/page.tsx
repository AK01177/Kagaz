"use client";

import React, { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AppShell, Button, Badge, Icon } from "../components/AppShell";
import { useAuth } from "../context/AuthContext";
import { supabase } from "../lib/supabase";

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
    register,
    createOrganization,
    logout,
    clearSessionExpiredNotice,
  } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [isRegistering, setIsRegistering] = useState(false);
  const [loading, setLoading] = useState(false);
  // Signed in with Supabase, but this email is in no organization yet: offer to create one.
  const [needsOrg, setNeedsOrg] = useState(false);
  const [orgName, setOrgName] = useState("");
  const redirectParam = searchParams.get("redirect");
  // After signing in, everyone picks an organization first (the picker then opens their home page).
  const pickerPath = redirectParam ? `/org-select?redirect=${encodeURIComponent(redirectParam)}` : "/org-select";
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

    const result = isRegistering
      ? await register(fullName, loginEmail, password)
      : await login(loginEmail, password);
    setLoading(false);

    if (result.needsWorkspace) {
      setNeedsOrg(true);
      return;
    }

    if (!result.success) {
      setNotice({
        type: "error",
        message: result.error || "Authentication failed. Please verify your credentials.",
      });
      return;
    }

    if (isRegistering && "confirmationRequired" in result && result.confirmationRequired) {
      setPassword("");
      setNotice({ type: "success", message: "Account created. Check your email to confirm it, then sign in to set up your organization." });
      return;
    }
    clearSessionExpiredNotice();
    setPassword("");
    setNotice({
      type: "success",
      message: "Authentication successful! Redirecting to workspace...",
    });

    setTimeout(() => {
      router.push(pickerPath);
    }, 600);
  }

  function handleLogout() {
    logout();
    setNotice({ type: "success", message: "Signed out successfully." });
  }

  const activeOrgName =
    memberships.find((m) => m.organization_id === (activeOrgId || user?.organization_id))?.organization_name ||
    activeOrgId ||
    user?.organization_id;

  async function handleCreateOrganization(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setNotice(null);
    const result = await createOrganization(orgName.trim());
    setLoading(false);
    if (!result.success) {
      setNotice({ type: "error", message: result.error || "Could not create the organization." });
      return;
    }
    router.push(pickerPath);
  }

  const roleColor = (role?: string) => {
    switch (role) {
      case "SYSTEM_ADMIN":
      case "ORG_ADMIN":
        return "violet";
      case "APPROVER":
      case "REVIEWER":
        return "green";
      default:
        return "green";
    }
  };

  if (needsOrg && !isAuthenticated) {
    return (
      <div className="intake-body" style={{ maxWidth: "520px" }}>
        {notice && (
          <p role="alert" style={{ padding: "10px 12px", background: "var(--red-bg, #fef2f2)", color: "var(--red, #dc2626)", borderRadius: "5px", fontSize: "12px" }}>
            {notice.message}
          </p>
        )}
        <div className="library-card" style={{ marginTop: 0, padding: "24px" }}>
          <span className="eyebrow">ONE LAST STEP</span>
          <h2 style={{ margin: "6px 0 8px", font: "22px 'Newsreader', serif" }}>Name your organization</h2>
          <p style={{ margin: "0 0 16px", fontSize: "12px", color: "var(--muted)", lineHeight: 1.5 }}>
            Your email isn&apos;t part of any organization yet. Create yours and you&apos;ll be its administrator: you can then add your team, upload policies and start processing documents.
            If you are joining an existing company instead, ask its admin to add your email, then sign in again.
          </p>
          <form onSubmit={handleCreateOrganization} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <label style={{ fontSize: "11px", fontWeight: 500 }}>
              Organization name
              <input
                required minLength={2} maxLength={120} value={orgName} onChange={(e) => setOrgName(e.target.value)}
                placeholder="e.g. Gamma Ltd" autoFocus
                style={{ display: "block", width: "100%", height: "36px", marginTop: "6px", border: "1px solid var(--line2, #e0ddd5)", borderRadius: "5px", padding: "0 12px", fontSize: "12px" }}
              />
            </label>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <Button variant="secondary" onClick={() => { logout(); setNeedsOrg(false); }}>Sign out</Button>
              <Button variant="primary" type="submit" disabled={loading}>{loading ? "Creating…" : "Create organization"}</Button>
            </div>
          </form>
        </div>
      </div>
    );
  }

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
              <b>{activeOrgName}</b>
            </div>
            <div>
              <span style={{ color: "var(--muted)", display: "block" }}>Membership Role</span>
              <b>{user.role}</b>
            </div>
            <div>
              <span style={{ color: "var(--muted)", display: "block" }}>Auth Mechanism</span>
              <b>Supabase Auth session</b>
            </div>
          </div>

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
              href={pickerPath}
              className="btn primary"
              style={{ textDecoration: "none", fontSize: "12px" }}
            >
              Choose organization →
            </Link>
          </div>
        </div>
      ) : null}

      <div className="library-card" style={{ marginTop: 0, padding: "24px" }}>
        <span className="eyebrow">SUPABASE AUTHENTICATION</span>
        <h2 style={{ margin: "6px 0 16px", font: "20px 'Newsreader', serif" }}>
          {isRegistering ? "Create your Kagaz account" : isAuthenticated ? "Sign in with a different account" : "Sign In to Kagaz"}
        </h2>

        {!supabase && (
          <p role="alert" style={{ margin: "0 0 16px", padding: "10px 12px", background: "var(--red-bg, #fef2f2)", color: "var(--red, #dc2626)", borderRadius: "5px", fontSize: "12px" }}>
            Sign-in is unavailable: Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and
            NEXT_PUBLIC_SUPABASE_ANON_KEY in frontend/.env, then restart the dev server.
          </p>
        )}

        <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {isRegistering && <div>
            <label htmlFor="name-input" style={{ display: "block", fontSize: "11px", fontWeight: 500, marginBottom: "6px" }}>Full Name</label>
            <input id="name-input" type="text" required value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name" style={{ width: "100%", height: "36px", border: "1px solid var(--line2, #e0ddd5)", borderRadius: "5px", padding: "0 12px", background: "white", fontSize: "12px" }} />
          </div>}
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
              autoComplete="email"
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
              minLength={8}
              autoComplete={isRegistering ? "new-password" : "current-password"}
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
              {isRegistering ? "Joining a company that already uses Kagaz? Ask its admin to add your email first, then sign in." : "Kagaz checks which organizations your email belongs to."}
            </span>
            <Button type="submit" variant="primary" icon="check" disabled={loading}>
              {loading ? (isRegistering ? "Creating account..." : "Signing in...") : (isRegistering ? "Create Account →" : "Sign In →")}
            </Button>
          </div>
        </form>
        <button type="button" className="btn secondary" style={{ marginTop: "14px" }} onClick={() => { setIsRegistering((value) => !value); setNotice(null); }}>
          {isRegistering ? "Already registered? Sign in" : "New to Kagaz? Create an account"}
        </button>
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
            <p className="subline">SUPABASE IDENTITY · ORGANIZATION ROLE AUTHORIZATION</p>
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <Link href="/workspace/documents" className="btn secondary" style={{ textDecoration: "none" }}>
              Intake Desk →
            </Link>
            <Link href="/workspace/review" className="btn primary" style={{ textDecoration: "none" }}>
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
