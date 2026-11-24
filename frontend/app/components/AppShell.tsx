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

export function Icon({ name, size = 16, className = "" }: { name: IconName; size?: number; className?: string }) {
  const props = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    className: `icon ${className}`,
    style: { display: "inline-block", verticalAlign: "middle", flexShrink: 0 },
  };

  switch (name) {
    case "grid":
      return (
        <svg {...props}>
          <rect x="3" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="14" width="7" height="7" rx="1.5" />
          <rect x="3" y="14" width="7" height="7" rx="1.5" />
        </svg>
      );
    case "inbox":
      return (
        <svg {...props}>
          <polyline points="22 12 16 12 14 15 10 15 8 12 2 12" />
          <path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
        </svg>
      );
    case "stamp":
      return (
        <svg {...props}>
          <path d="M5 22h14" />
          <path d="M19.27 13.73A2.5 2.5 0 0 0 17.5 13h-11a2.5 2.5 0 0 0-1.77.73l-1.5 1.5A2.5 2.5 0 0 0 2.5 17V18h19v-1a2.5 2.5 0 0 0-.73-1.77l-1.5-1.5z" />
          <path d="M14 13V8.5a2 2 0 0 0-2-2h0a2 2 0 0 0-2 2V13" />
        </svg>
      );
    case "check":
      return (
        <svg {...props}>
          <polyline points="20 6 9 17 4 12" />
        </svg>
      );
    case "book":
      return (
        <svg {...props}>
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
        </svg>
      );
    case "shield":
      return (
        <svg {...props}>
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        </svg>
      );
    case "settings":
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      );
    case "file":
      return (
        <svg {...props}>
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
        </svg>
      );
    case "copy":
      return (
        <svg {...props}>
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </svg>
      );
    case "pencil":
      return (
        <svg {...props}>
          <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
        </svg>
      );
    case "refresh":
      return (
        <svg {...props}>
          <polyline points="23 4 23 10 17 10" />
          <polyline points="1 20 1 14 7 14" />
          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
        </svg>
      );
    case "search":
      return (
        <svg {...props}>
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      );
    case "alert":
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      );
    case "receipt":
      return (
        <svg {...props}>
          <path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1-2-1Z" />
          <line x1="8" y1="8" x2="16" y2="8" />
          <line x1="8" y1="12" x2="16" y2="12" />
          <line x1="8" y1="16" x2="12" y2="16" />
        </svg>
      );
    case "contact":
      return (
        <svg {...props}>
          <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
          <circle cx="12" cy="7" r="4" />
        </svg>
      );
    case "sliders":
      return (
        <svg {...props}>
          <line x1="4" y1="21" x2="4" y2="14" />
          <line x1="4" y1="10" x2="4" y2="3" />
          <line x1="12" y1="21" x2="12" y2="12" />
          <line x1="12" y1="8" x2="12" y2="3" />
          <line x1="20" y1="21" x2="20" y2="16" />
          <line x1="20" y1="12" x2="20" y2="3" />
          <line x1="1" y1="14" x2="7" y2="14" />
          <line x1="9" y1="8" x2="15" y2="8" />
          <line x1="17" y1="16" x2="23" y2="16" />
        </svg>
      );
    case "flag":
      return (
        <svg {...props}>
          <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" />
          <line x1="4" y1="22" x2="4" y2="15" />
        </svg>
      );
    case "history":
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
      );
    case "folder":
      return (
        <svg {...props}>
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
        </svg>
      );
    default:
      return (
        /* eslint-disable-next-line @next/next/no-img-element */
        <img
          className={`icon ${className}`}
          src={`/assets/${icons[name] || "9255a.svg"}`}
          width={size}
          height={size}
          alt=""
        />
      );
  }
}

export function Button({
  children,
  icon,
  variant = "secondary",
  onClick,
  disabled = false,
  type = "button",
  className = "",
}: {
  children: React.ReactNode;
  icon?: IconName;
  variant?: "primary" | "secondary" | "ghost";
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
  className?: string;
}) {
  return (
    <button
      type={type}
      className={`btn ${variant} ${className}`}
      onClick={onClick}
      disabled={disabled}
    >
      {icon && <Icon name={icon} size={15} />}
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

  const links: { href: string; label: string; icon: IconName; count?: boolean }[] =
    userRole === "SUBMITTER"
      ? [
          { href: "/workspace/dashboard", label: "Overview", icon: "grid" },
          { href: "/workspace/documents", label: "My Files", icon: "file", count: true },
        ]
      : userRole === "REVIEWER"
      ? [
          { href: "/workspace/dashboard", label: "Overview", icon: "grid" },
          { href: "/workspace/review", label: "Verification Desk", icon: "stamp", count: true },
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
    const role = memberships.find((m) => m.organization_id === targetOrg)?.role;
    router.push(homeForRole(role));
  };

  return (
    <aside className={`sidebar ${isCollapsed ? "collapsed" : ""}`}>
      <div className="brand-row">
        <Link href={homeForRole(userRole)} className="brand" title="Kagaz Intelligence Platform">
          {isCollapsed ? "K" : "Kagaz"}
          <span className="brand-dot" />
        </Link>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "6px" }}>
          {!isCollapsed && <NotificationCenter align="left" />}
          <button
            type="button"
            className="collapse"
            onClick={() => setIsCollapsed(!isCollapsed)}
            title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label="Toggle Sidebar"
          >
            {isCollapsed ? "⇥" : "⇤"}
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
                  padding: "4px 8px",
                  fontSize: "11px",
                  fontFamily: "inherit",
                  background: "rgba(255, 255, 255, 0.08)",
                  border: "1px solid rgba(255, 255, 255, 0.15)",
                  borderRadius: "6px",
                  color: "#FFFFFF",
                  cursor: "pointer",
                  outline: "none",
                }}
              >
                {memberships.map((m) => (
                  <option key={m.organization_id} value={m.organization_id} style={{ background: "#0F172A", color: "#FFFFFF" }}>
                    {m.organization_name || m.organization_id} ({ROLE_LABELS[m.role] || m.role})
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <span>{isAuthenticated ? ROLE_LABELS[userRole] || userRole : "Enterprise workspace"}</span>
          )}

          {orgSwitchError && (
            <span style={{ color: "#EF4444", fontSize: "10px", marginTop: "2px" }}>
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
            <Icon name={link.icon} size={16} />
            {!isCollapsed && (
              <>
                <span className="nav-label" style={{ flex: 1 }}>{link.label}</span>
                {link.count && isAuthenticated && badgeCount !== null && badgeCount > 0 && (
                  <em>{badgeCount}</em>
                )}
              </>
            )}
          </Link>
        ))}
        {!isAuthenticated && (
          <Link href="/login" title="Sign In">
            <Icon name="book" size={16} />
            {!isCollapsed && "Sign In"}
          </Link>
        )}
      </nav>

      <div className="side-bottom">
        {!isCollapsed && (
          <div className="side-note">
            <p style={{ color: "#94A3B8", fontSize: "11px", margin: 0, lineHeight: 1.5 }}>
              Archival Intelligence.
              <br />
              Deterministic Governance.
            </p>
          </div>
        )}

        {!isCollapsed && (
          <div className="backend">
            <span className="brand-dot" /> Verified Enclave Active
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
              title="Sign out of workspace"
              aria-label="Log out"
              style={{
                background: "rgba(255, 255, 255, 0.06)",
                border: "none",
                cursor: "pointer",
                color: "#94A3B8",
                padding: "6px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: "6px",
                transition: "all 0.15s ease",
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
