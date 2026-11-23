"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "./context/AuthContext";
import { NotificationCenter } from "./components/NotificationCenter";
import { homeForRole } from "./lib/roles";

export function Header() {
  const pathname = usePathname();
  const { user, isAuthenticated, activeOrgId } = useAuth();

  const isHome = pathname === "/";
  const isLogin = pathname === "/login";
  const displayName = user?.name || user?.email?.split("@")[0];

  return (
    <header className="header" style={{ background: "#FFFFFF", borderBottom: "1px solid var(--line)" }}>
      <Link className="wordmark" href="/">
        Kagaz<span>.</span>
      </Link>
      <nav>
        <Link
          href="/"
          className={isHome ? "active" : ""}
          style={isHome ? { color: "var(--ink)", fontWeight: 600 } : undefined}
        >
          Manifesto
        </Link>
        <Link
          href={isAuthenticated ? homeForRole(user?.role) : "/login"}
          className={isLogin ? "active" : ""}
          style={isLogin ? { color: "var(--ink)", fontWeight: 600 } : undefined}
        >
          {isAuthenticated ? "Open workspace" : "Sign In"}
        </Link>
      </nav>
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        {isAuthenticated && <NotificationCenter />}
        <Link
          href="/login"
          className="session"
          style={{ textDecoration: "none" }}
          title={isAuthenticated ? `Active in ${activeOrgId || user?.organization_id}` : "Sign in to workspace"}
        >
          <i style={isAuthenticated ? { background: "var(--green)" } : undefined} />{" "}
          {isAuthenticated && displayName ? displayName : "Sign In"}
        </Link>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer>
      <span>KAGAZ DOCUMENT INTELLIGENCE</span>
      <span>Private workspace · Encrypted at rest</span>
      <code>SESSION 7F-8823</code>
    </footer>
  );
}
