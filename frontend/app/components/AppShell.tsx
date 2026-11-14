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
  const { user, memberships, activeOrgId, switchOrganization, logout, isAuthenticated } =
    useAuth();

  const [intakeCount, setIntakeCount] = useState(3);
  const [reviewCount, setReviewCount] = useState(2);
  const [orgSwitchError, setOrgSwitchError] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      try {
        const storedDocKeys = Object.keys(sessionStorage).filter((k) =>
          k.startsWith("kagaz_doc_")
        );
        setIntakeCount(3 + storedDocKeys.length);

        const unverifiedCount = storedDocKeys.filter((k) => {
          try {
            const item = JSON.parse(sessionStorage.getItem(k) || "{}");
            return item.status !== "REVIEWER_VERIFIED" && item.confidence && item.confidence < 0.8;
          } catch {
            return false;
          }
        }).length;
        setReviewCount(4 + unverifiedCount);
      } catch {}
    }, 0);
    return () => clearTimeout(timer);
  }, [pathname]);

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
    <aside className="sidebar">
      <div className="brand-row">
        <Link href="/dashboard" className="brand">
          Kagaz.
        </Link>
        <span className="brand-dot" />
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "4px" }}>
          <NotificationCenter />
          <button type="button" className="collapse" aria-label="Collapse">
            ◫
          </button>
        </div>
      </div>

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

      <div className="divider" />

      <span className="eyebrow side-label">WORKSPACE</span>

      <nav className="side-nav">
        <Link href="/dashboard" className={isDashboard ? "active" : ""}>
          <Icon name="grid" />
          Workspace Overview
        </Link>

        <Link href="/documents" className={isIntake ? "active" : ""}>
          <Icon name="inbox" />
          Intake &amp; Library <em>{intakeCount}</em>
        </Link>

        <Link
          href="/review"
          className={isReview ? "active" : ""}
          style={!canAccessReview && isAuthenticated ? { opacity: 0.6 } : undefined}
          title={!canAccessReview && isAuthenticated ? "Requires Reviewer or Admin role" : undefined}
        >
          <Icon name="stamp" />
          Verification Desk{" "}
          {canAccessReview || !isAuthenticated ? (
            <em className="amber-count">{reviewCount}</em>
          ) : (
            <em style={{ fontSize: "9px", opacity: 0.8 }}>Restricted</em>
          )}
        </Link>

        <Link
          href="/approvals"
          className={isApprovals ? "active" : ""}
          style={!canAccessApprovals && isAuthenticated ? { opacity: 0.6 } : undefined}
          title={!canAccessApprovals && isAuthenticated ? "Requires Approver or Admin role" : undefined}
        >
          <Icon name="check" />
          Approval Ledger{" "}
          {canAccessApprovals || !isAuthenticated ? (
            <em>2</em>
          ) : (
            <em style={{ fontSize: "9px", opacity: 0.8 }}>Restricted</em>
          )}
        </Link>

        <Link
          href="/policies"
          className={isPolicies ? "active" : ""}
          style={!canAccessAdmin && isAuthenticated ? { opacity: 0.6 } : undefined}
          title={!canAccessAdmin && isAuthenticated ? "Requires Organization Admin role" : undefined}
        >
          <Icon name="shield" />
          Policy Governance{" "}
          {!canAccessAdmin && isAuthenticated && (
            <em style={{ fontSize: "9px", opacity: 0.8 }}>Admin</em>
          )}
        </Link>

        <Link
          href="/admin/users"
          className={isAdmin ? "active" : ""}
          style={!canAccessAdmin && isAuthenticated ? { opacity: 0.6 } : undefined}
          title={!canAccessAdmin && isAuthenticated ? "Requires Organization Admin role" : undefined}
        >
          <Icon name="contact" />
          User Management{" "}
          {!canAccessAdmin && isAuthenticated && (
            <em style={{ fontSize: "9px", opacity: 0.8 }}>Admin</em>
          )}
        </Link>

        <Link href="/login" className={isLogin ? "active" : ""}>
          <Icon name="book" />
          {isAuthenticated ? "Session & Switchboard" : "Access & Auth"}
        </Link>
      </nav>

      <div className="side-bottom">
        <div className="side-note">
          <Icon name="shield" size={18} />
          <p>
            Every document. Every decision.
            <br />A permanent, traceable record.
          </p>
        </div>

        <div className="backend">
          <span className="brand-dot" /> Backend Online
        </div>

        <div className="divider" />

        <div className="profile">
          <span>{userInitials}</span>
          <div style={{ minWidth: 0 }}>
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

          {isAuthenticated ? (
            <button
              type="button"
              onClick={() => {
                logout();
                router.push("/login");
              }}
              title="Sign Out of Session"
              aria-label="Sign Out"
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
              title="Session Sign In"
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
