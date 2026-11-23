"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "../context/AuthContext";
import { NotificationCenter } from "./NotificationCenter";

export type IconName =
  | "grid"
  | "inbox"
  | "stamp"
  | "check"
  | "book"
  | "shield"
  | "settings"
  | "file"
  | "copy"
  | "pencil"
  | "refresh"
  | "search"
  | "alert"
  | "receipt"
  | "contact"
  | "sliders"
  | "flag"
  | "history"
  | "folder";

export const icons: Record<IconName, string> = {
  grid: "ceced.svg",
  inbox: "18058.svg",
  stamp: "69248.svg",
  check: "de16a.svg",
  book: "4a03d.svg",
  shield: "697c2.svg",
  settings: "68b56.svg",
  file: "9255a.svg",
  copy: "cfdbc.svg",
  pencil: "a9f88.svg",
  refresh: "b5ef0.svg",
  search: "588c6.svg",
  alert: "51a24.svg",
  receipt: "8f8ab.svg",
  contact: "60c88.svg",
  sliders: "c0509.svg",
  flag: "f38bc.svg",
  history: "d3618.svg",
  folder: "fed02.svg",
};

export function Icon({ name, size = 15 }: { name: IconName; size?: number }) {
  return (
    /* eslint-disable-next-line @next/next/no-img-element */
    <img
      className="icon"
      src={`/assets/${icons[name] || "9255a.svg"}`}
      width={size}
      height={size}
      alt=""
    />
  );
}

export function Button({
  children,
  icon,
  variant = "secondary",
  onClick,
  disabled = false,
  type = "button",
}: {
  children: React.ReactNode;
  icon?: IconName;
  variant?: "primary" | "secondary" | "ghost";
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
}) {
  return (
    <button
      type={type}
      className={`btn ${variant}`}
      onClick={onClick}
      disabled={disabled}
    >
      {icon && <Icon name={icon} size={14} />}
      {children}
    </button>
  );
}

export function Badge({
  children,
  tone = "green",
}: {
  children: React.ReactNode;
  tone?: "green" | "amber" | "violet" | "red";
}) {
  return (
    <span className={`badge ${tone}`}>
      <i />
      {children}
    </span>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, memberships, activeOrgId, switchOrganization, logout, isAuthenticated, fetchWithAuth } =
    useAuth();

  const [intakeCount, setIntakeCount] = useState<number | null>(null);
  const [reviewCount, setReviewCount] = useState<number | null>(null);
  const [approvalCount, setApprovalCount] = useState<number | null>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [orgSwitchError, setOrgSwitchError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function fetchCounts() {
      if (!isAuthenticated) {
        if (isMounted) {
          setIntakeCount(null);
          setReviewCount(null);
          setApprovalCount(null);
        }
        return;
      }
      try {
        const [docsRes, reviewRes, approvalRes] = await Promise.allSettled([
          fetchWithAuth("/api/documents"),
          fetchWithAuth("/api/documents/workflow/review-queue"),
          fetchWithAuth("/api/documents/workflow/approval-queue"),
        ]);
        if (!isMounted) return;

        if (docsRes.status === "fulfilled" && docsRes.value.ok) {
          const docsData = await docsRes.value.json().catch(() => null);
          const list = Array.isArray(docsData) ? docsData : docsData?.documents || [];
          setIntakeCount(list.length);
        } else {
          setIntakeCount(0);
        }

        if (reviewRes.status === "fulfilled" && reviewRes.value.ok) {
          const reviewData = await reviewRes.value.json().catch(() => null);
          const items = reviewData?.items || (Array.isArray(reviewData) ? reviewData : []);
          setReviewCount(items.length);
        } else {
          setReviewCount(0);
        }

        if (approvalRes.status === "fulfilled" && approvalRes.value.ok) {
          const appData = await approvalRes.value.json().catch(() => null);
          const items = appData?.items || (Array.isArray(appData) ? appData : []);
          setApprovalCount(items.length);
        } else {
          setApprovalCount(0);
        }
      } catch {
        if (isMounted) {
          setIntakeCount(0);
          setReviewCount(0);
          setApprovalCount(0);
        }
      }
    }

    fetchCounts();
    return () => {
      isMounted = false;
    };
  }, [pathname, activeOrgId, isAuthenticated, fetchWithAuth]);

  const isIntake = pathname === "/documents" || pathname.startsWith("/documents/");
  const isReview = pathname.startsWith("/review");
  const isDashboard = pathname === "/dashboard";
  const isApprovals = pathname === "/approvals";
  const isAdmin = pathname.startsWith("/admin");
  const isPolicies = pathname.startsWith("/policies");
  const isLogin = pathname === "/login";

  const userRole = user?.role || "GUEST";
  const userName = user?.name || user?.email?.split("@")[0] || "Guest Visitor";
  const userInitials = (userName || "K").slice(0, 2).toUpperCase();

  const currentOrg = activeOrgId || user?.organization_id || "Acme Global Enterprise";

  const canAccessReview = ["REVIEWER", "APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN", "COMPLIANCE", "AUDITOR"].includes(
    userRole
  );
  const canAccessApprovals = ["APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN"].includes(userRole);
  const canAccessAdmin = ["ORG_ADMIN", "SYSTEM_ADMIN"].includes(userRole);

  const handleOrgSwitch = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const targetOrg = e.target.value;
    setOrgSwitchError(null);
    const result = await switchOrganization(targetOrg);
    if (!result.success) {
      setOrgSwitchError(result.error || "Failed to switch organization");
    } else {
      router.refresh();
    }
  };

  return (
    <aside className={`sidebar ${isCollapsed ? "collapsed" : ""}`} style={isCollapsed ? { width: "64px", minWidth: "64px", padding: "20px 8px" } : undefined}>
      <div className="brand-row">
        <Link href="/dashboard" className="brand" title="Kagaz Enterprise">
          {isCollapsed ? "K." : "Kagaz."}
        </Link>
        <span className="brand-dot" />
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "4px" }}>
          {!isCollapsed && <NotificationCenter align="left" />}
          <button
            type="button"
            className="collapse"
            onClick={() => setIsCollapsed(!isCollapsed)}
            title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label="Toggle Sidebar"
          >
            ◫
          </button>
        </div>
      </div>

      {!isCollapsed && (
        <div className="org">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <b title={currentOrg} style={{ textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
              {currentOrg}
            </b>
            {memberships.length > 1 && (
              <span
                style={{
                  fontSize: "9px",
                  background: "var(--line2, #e0ddd5)",
                  padding: "1px 5px",
                  borderRadius: "3px",
                  color: "var(--ink)",
                }}
              >
                {memberships.length} orgs
              </span>
            )}
          </div>

          {memberships.length > 1 ? (
            <div style={{ marginTop: "4px" }}>
              <select
                value={activeOrgId || user?.organization_id || ""}
                onChange={handleOrgSwitch}
                aria-label="Active Organization"
                style={{
                  width: "100%",
                  padding: "3px 6px",
                  fontSize: "10px",
                  fontFamily: "inherit",
                  background: "white",
                  border: "1px solid var(--line2, #e0ddd5)",
                  borderRadius: "4px",
                  color: "var(--body)",
                  cursor: "pointer",
                }}
              >
                {memberships.map((m) => (
                  <option key={m.organization_id} value={m.organization_id}>
                    {m.organization_id} ({m.role})
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <span>{isAuthenticated ? `Role: ${userRole}` : "Enterprise workspace"}</span>
          )}

          {orgSwitchError && (
            <span style={{ color: "var(--red, #dc2626)", fontSize: "9px", marginTop: "2px" }}>
              {orgSwitchError}
            </span>
          )}
        </div>
      )}

      <div className="divider" />

      {!isCollapsed && <span className="eyebrow side-label">WORKSPACE</span>}

      <nav className="side-nav">
        <Link href="/dashboard" className={isDashboard ? "active" : ""} title="Overview">
          <Icon name="grid" />
          {!isCollapsed && <span className="nav-label">Overview</span>}
        </Link>

        <Link href="/documents" className={isIntake ? "active" : ""} title="Files">
          <Icon name="file" />
          {!isCollapsed && (
            <span className="nav-label">
              Files {intakeCount !== null && intakeCount > 0 && <em>{intakeCount}</em>}
            </span>
          )}
        </Link>

        <Link
          href="/review"
          className={isReview ? "active" : ""}
          style={!canAccessReview && isAuthenticated ? { opacity: 0.6 } : undefined}
          title={!canAccessReview && isAuthenticated ? "Requires Reviewer or Admin role" : "Verification Queue"}
        >
          <Icon name="stamp" />
          {!isCollapsed && (
            <span className="nav-label">
              Verification Queue{" "}
              {canAccessReview && reviewCount !== null && reviewCount > 0 ? (
                <em className="amber-count">{reviewCount}</em>
              ) : null}
            </span>
          )}
        </Link>

        <Link
          href="/approvals"
          className={isApprovals ? "active" : ""}
          style={!canAccessApprovals && isAuthenticated ? { opacity: 0.6 } : undefined}
          title={!canAccessApprovals && isAuthenticated ? "Requires Approver or Admin role" : "Approvals"}
        >
          <Icon name="check" />
          {!isCollapsed && (
            <span className="nav-label">
              Approvals{" "}
              {canAccessApprovals && approvalCount !== null && approvalCount > 0 ? (
                <em>{approvalCount}</em>
              ) : null}
            </span>
          )}
        </Link>

        <Link
          href="/policies"
          className={isPolicies ? "active" : ""}
          style={!canAccessAdmin && isAuthenticated ? { opacity: 0.6 } : undefined}
          title={!canAccessAdmin && isAuthenticated ? "Requires Organization Admin role" : "Policy Governance"}
        >
          <Icon name="shield" />
          {!isCollapsed && <span className="nav-label">Policy Governance</span>}
        </Link>

        <Link
          href="/admin/users"
          className={isAdmin ? "active" : ""}
          style={!canAccessAdmin && isAuthenticated ? { opacity: 0.6 } : undefined}
          title={!canAccessAdmin && isAuthenticated ? "Requires Organization Admin role" : "User Management"}
        >
          <Icon name="contact" />
          {!isCollapsed && <span className="nav-label">User Management</span>}
        </Link>

        <Link href="/login" className={isLogin ? "active" : ""} title="Session & Switchboard">
          <Icon name="book" />
          {!isCollapsed && (
            <span className="nav-label">
              {isAuthenticated ? "Switchboard" : "Sign In"}
            </span>
          )}
        </Link>
      </nav>

      <div className="side-bottom">
        {!isCollapsed && (
          <div className="side-note">
            <p style={{ color: "var(--muted)", fontSize: "11px", margin: 0, lineHeight: 1.5 }}>
              Every document.
              <br />
              Every decision. Accounted for.
            </p>
          </div>
        )}

        {!isCollapsed && (
          <div className="backend" style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "10px", color: "var(--brand)" }}>
            <span className="brand-dot" /> Backend online
          </div>
        )}

        <div className="divider" />

        <div className="profile">
          <span>{userInitials}</span>
          {!isCollapsed && (
            <div style={{ minWidth: 0, flex: 1 }}>
              <b
                style={{
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  display: "block",
                }}
                title={userName}
              >
                {userName}
              </b>
              <small>{isAuthenticated ? userRole : "Not Signed In"}</small>
            </div>
          )}

          {isAuthenticated ? (
            <button
              type="button"
              onClick={() => {
                logout();
                router.push("/login");
              }}
              title="Log out"
              aria-label="Log out"
              style={{
                background: "transparent",
                border: "none",
                cursor: "pointer",
                color: "var(--muted, #666)",
                padding: "6px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: "4px",
              }}
            >
              <Icon name="history" size={14} />
            </button>
          ) : (
            <Link
              href="/login"
              style={{ color: "inherit", textDecoration: "none" }}
              title="Sign In"
            >
              <Icon name="settings" size={14} />
            </Link>
          )}
        </div>
      </div>
    </aside>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-shell">
      <Sidebar />
      <main className="workspace">{children}</main>
    </div>
  );
}
