"use client";

import React, { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useAuth } from "../context/AuthContext";
import { AppShell, Button, Badge, Icon } from "./AppShell";
import { homeForRole } from "../lib/roles";

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: string[];
  fallbackPath?: string;
}

export function ProtectedRoute({
  children,
  allowedRoles,
  fallbackPath,
}: ProtectedRouteProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, isLoading, orgConfirmed, sessionExpired, user, logout } = useAuth();

  useEffect(() => {
    if (!isLoading) {
      if (sessionExpired) {
        router.push(`/login?session_expired=true&redirect=${encodeURIComponent(pathname)}`);
      } else if (!isAuthenticated) {
        router.push(`/login?redirect=${encodeURIComponent(pathname)}`);
      } else if (!orgConfirmed) {
        router.push(`/org-select?redirect=${encodeURIComponent(pathname)}`);
      }
    }
  }, [isLoading, isAuthenticated, orgConfirmed, sessionExpired, pathname, router]);

  if (isLoading || (isAuthenticated && !orgConfirmed)) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--bg, #f6f5f1)",
          fontFamily: "var(--font-sans, system-ui, sans-serif)",
          padding: "24px",
        }}
      >
        <div style={{ textAlign: "center", maxWidth: "360px" }}>
          <div
            style={{
              fontFamily: "'Newsreader', serif",
              fontSize: "28px",
              fontWeight: 600,
              letterSpacing: "-0.5px",
              marginBottom: "8px",
            }}
          >
            Kagaz<span style={{ color: "var(--sage, #6c8c7c)" }}>.</span>
          </div>
          <p style={{ fontSize: "12px", color: "var(--muted, #666)", marginBottom: "16px" }}>
            Verifying identity and organization workspace context...
          </p>
          <div
            style={{
              width: "120px",
              height: "2px",
              background: "var(--line2, #e0ddd5)",
              margin: "0 auto",
              overflow: "hidden",
              borderRadius: "2px",
            }}
          >
            <div
              style={{
                width: "40%",
                height: "100%",
                background: "var(--ink, #1f2328)",
                animation: "pulse 1.2s infinite ease-in-out",
              }}
            />
          </div>
        </div>
      </div>
    );
  }

  if (sessionExpired || !isAuthenticated || !user) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--bg, #f6f5f1)",
          padding: "24px",
        }}
      >
        <div
          className="library-card"
          style={{
            maxWidth: "420px",
            width: "100%",
            padding: "28px",
            textAlign: "center",
            background: "white",
            borderRadius: "8px",
            border: "1px solid var(--line2, #e0ddd5)",
          }}
        >
          <div
            style={{
              width: "44px",
              height: "44px",
              borderRadius: "50%",
              background: "var(--amber-bg, #fffbeb)",
              color: "var(--amber, #b45309)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 16px",
              fontSize: "20px",
            }}
          >
            !
          </div>
          <h2 style={{ fontSize: "18px", margin: "0 0 8px", font: "18px 'Newsreader', serif" }}>
            {sessionExpired ? "Session Expired" : "Authentication Required"}
          </h2>
          <p style={{ fontSize: "12px", color: "var(--muted, #666)", margin: "0 0 20px", lineHeight: 1.5 }}>
            {sessionExpired
              ? "Your signed credentials have expired. Please sign in again to re-authenticate."
              : "Access to this workspace requires a verified session with valid organization credentials."}
          </p>
          <Link
            href={`/login?redirect=${encodeURIComponent(pathname)}`}
            className="btn primary"
            style={{
              display: "inline-block",
              textDecoration: "none",
              padding: "10px 20px",
              fontSize: "12px",
            }}
          >
            Sign In to Kagaz →
          </Link>
        </div>
      </div>
    );
  }

  // Check role authorization if specified
  if (allowedRoles && allowedRoles.length > 0 && !allowedRoles.includes(user.role)) {
    return (
      <AppShell>
        <header className="page-head">
          <div className="crumb">
            <Icon name="shield" size={14} /> Workspace <span>/</span> Access Control
            <div className="sync">
              <span className="brand-dot" style={{ background: "var(--red, #dc2626)" }} /> Restricted
            </div>
          </div>
          <div className="head-main">
            <div>
              <h1>Access Restricted</h1>
              <p className="subline">AUTHORIZATION POLICY · ROLE ENFORCEMENT</p>
            </div>
          </div>
        </header>

        <div className="intake-body" style={{ maxWidth: "680px" }}>
          <div
            className="library-card"
            style={{
              padding: "28px",
              background: "white",
              border: "1px solid var(--line2, #e0ddd5)",
              borderRadius: "8px",
            }}
          >
            <div style={{ display: "flex", alignItems: "flex-start", gap: "16px", marginBottom: "20px" }}>
              <div
                style={{
                  width: "40px",
                  height: "40px",
                  borderRadius: "6px",
                  background: "var(--red-bg, #fef2f2)",
                  color: "var(--red, #dc2626)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  fontSize: "18px",
                  fontWeight: "bold",
                }}
              >
                ✕
              </div>
              <div>
                <h3 style={{ margin: "0 0 6px", font: "18px 'Newsreader', serif" }}>
                  Insufficient Role Permissions
                </h3>
                <p style={{ margin: 0, fontSize: "12px", color: "var(--muted, #666)", lineHeight: 1.5 }}>
                  Your account is authenticated as <b>{user.name}</b> with role{" "}
                  <Badge tone="violet">{user.role}</Badge> in organization{" "}
                  <code>{user.organization_id}</code>. This section requires one of the following roles:
                </p>
              </div>
            </div>

            <div
              style={{
                background: "var(--side, #f8f7f4)",
                padding: "12px 16px",
                borderRadius: "6px",
                marginBottom: "20px",
                fontSize: "12px",
                display: "flex",
                flexWrap: "wrap",
                gap: "8px",
                alignItems: "center",
              }}
            >
              <span style={{ color: "var(--muted, #666)", fontWeight: 500 }}>Required Roles:</span>
              {allowedRoles.map((role) => (
                <span
                  key={role}
                  style={{
                    fontFamily: "monospace",
                    fontSize: "11px",
                    background: "white",
                    padding: "3px 8px",
                    borderRadius: "4px",
                    border: "1px solid var(--line2, #e0ddd5)",
                  }}
                >
                  {role}
                </span>
              ))}
            </div>

            <p style={{ fontSize: "11px", color: "var(--muted, #666)", marginBottom: "24px" }}>
              Note: The Kagaz backend remains authoritative and rejects unauthorized operations with HTTP 403 Forbidden.
              If you require access, please contact your organization administrator to update your membership role.
            </p>

            <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
              <Button variant="secondary" onClick={() => logout()}>
                Sign Out
              </Button>
              <Link href={fallbackPath ?? homeForRole(user.role)} className="btn primary" style={{ textDecoration: "none" }}>
                Go to my home page →
              </Link>
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  return <>{children}</>;
}
