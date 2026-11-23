"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "../context/AuthContext";
import { NotificationCenter } from "./NotificationCenter";
import { ROLE_LABELS, homeForRole } from "../lib/roles";

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

  // One number per role: submitters count their files, reviewers their queue, approvers their approvals.
  const [badgeCount, setBadgeCount] = useState<number | null>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [orgSwitchError, setOrgSwitchError] = useState<string | null>(null);

  const userRole = user?.role || "GUEST";
  const countUrl: Record<string, string> = {
    SUBMITTER: "/api/documents",
    REVIEWER: "/api/documents/workflow/review-queue",
    APPROVER: "/api/documents/workflow/approval-queue",
  };

  useEffect(() => {
    const url = countUrl[userRole];
    if (!isAuthenticated || !url) return;
    let isMounted = true;
    fetchWithAuth(url)
      .then(async (res) => {
        const data = res.ok ? await res.json().catch(() => null) : null;
        const list = Array.isArray(data) ? data : data?.documents || data?.items || [];
        if (isMounted) setBadgeCount(list.length);
      })
      .catch(() => isMounted && setBadgeCount(0));
    return () => {
      isMounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname, activeOrgId, isAuthenticated, userRole, fetchWithAuth]);

  const userName = user?.name || user?.email?.split("@")[0] || "Guest Visitor";
  const userInitials = (userName || "K").slice(0, 2).toUpperCase();

  const currentOrgId = activeOrgId || user?.organization_id || "";
  const currentOrg = memberships.find((m) => m.organization_id === currentOrgId)?.organization_name || currentOrgId || "Kagaz";

  // Each role only sees the links it can use.
  const links: { href: string; label: string; icon: IconName; count?: boolean }[] =
    userRole === "SUBMITTER"
      ? [
          { href: "/workspace/dashboard", label: "Overview", icon: "grid" },
          { href: "/workspace/documents", label: "My Files", icon: "file", count: true },
        ]
      : userRole === "REVIEWER"
      ? [
          { href: "/workspace/dashboard", label: "Overview", icon: "grid" },
          { href: "/workspace/review", label: "Verification Queue", icon: "stamp", count: true },
        ]
      : userRole === "APPROVER"
      ? [
          { href: "/workspace/dashboard", label: "Overview", icon: "grid" },
          { href: "/workspace/approvals", label: "Approvals", icon: "check", count: true },
        ]
      : userRole === "ORG_ADMIN" || userRole === "SYSTEM_ADMIN"
      ? [
          ...(userRole === "SYSTEM_ADMIN" ? [{ href: "/admin/organizations", label: "Organizations", icon: "book" as IconName }] : []),
          { href: "/org/members", label: "Members", icon: "contact" },
          { href: "/org/policies", label: "Policies", icon: "shield" },
        ]
      : [];
  const areaLabel = userRole === "SYSTEM_ADMIN" ? "PLATFORM" : userRole === "ORG_ADMIN" ? "ORGANIZATION" : "WORKSPACE";

  const handleOrgSwitch = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const targetOrg = e.target.value;
    setOrgSwitchError(null);
    const result = await switchOrganization(targetOrg);
    if (!result.success) {
      setOrgSwitchError(result.error || "Failed to switch organization");
      return;
    }
    // The role can differ per organization, so go to that role's home page.
    const role = memberships.find((m) => m.organization_id === targetOrg)?.role;
    router.push(homeForRole(role));
  };

  return (
    <aside className={`sidebar ${isCollapsed ? "collapsed" : ""}`} style={isCollapsed ? { width: "64px", minWidth: "64px", padding: "20px 8px" } : undefined}>
      <div className="brand-row">
        <Link href={homeForRole(userRole)} className="brand" title="Kagaz">
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
          <b title={currentOrg} style={{ textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap", display: "block" }}>
            {currentOrg}
          </b>

          {memberships.length > 1 ? (
            <div style={{ marginTop: "4px" }}>
              <select
                value={currentOrgId}
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
                    {m.organization_name || m.organization_id} ({ROLE_LABELS[m.role] || m.role})
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <span>{isAuthenticated ? ROLE_LABELS[userRole] || userRole : "Enterprise workspace"}</span>
          )}

          {orgSwitchError && (
            <span style={{ color: "var(--red, #dc2626)", fontSize: "9px", marginTop: "2px" }}>
              {orgSwitchError}
            </span>
          )}
        </div>
      )}

      <div className="divider" />

      {!isCollapsed && <span className="eyebrow side-label">{areaLabel}</span>}

      <nav className="side-nav">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={pathname === link.href || pathname.startsWith(link.href + "/") ? "active" : ""}
            title={link.label}
          >
            <Icon name={link.icon} />
            {!isCollapsed && (
              <>
                <span className="nav-label">{link.label} {link.count && isAuthenticated && badgeCount !== null && badgeCount > 0 && <em>{badgeCount}</em>}</span>
              </>
            )}
          </Link>
        ))}
        {!isAuthenticated && (
          <Link href="/login" title="Sign In">
            <Icon name="book" />
            {!isCollapsed && "Sign In"}
          </Link>
        )}
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
              <small>{isAuthenticated ? ROLE_LABELS[userRole] || userRole : "Not Signed In"}</small>
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
