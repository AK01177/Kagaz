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
    <header className="header">
      <Link className="wordmark" href="/">
        Kagaz<span>.</span>
      </Link>
      <nav>
        <Link
          href="/"
          className={isHome ? "active" : ""}
        >
          Manifesto
        </Link>
        <Link
          href={isAuthenticated ? homeForRole(user?.role) : "/login"}
          className={isLogin ? "active" : ""}
        >
          {isAuthenticated ? "Open Workspace" : "Sign In"}
        </Link>
      </nav>
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        {isAuthenticated && <NotificationCenter align="right" />}
        <Link
          href={isAuthenticated ? homeForRole(user?.role) : "/login"}
          className="session"
          style={{ textDecoration: "none" }}
          title={isAuthenticated ? `Active in ${activeOrgId || user?.organization_id}` : "Sign in to workspace"}
        >
          <i style={isAuthenticated ? { background: "var(--success)" } : undefined} />
          {isAuthenticated && displayName ? displayName : "Sign In"}
        </Link>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer>
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <span style={{ fontWeight: 600, color: "var(--ink)" }}>KAGAZ</span>
        <span>· Archival Document Intelligence &amp; Governance</span>
      </div>
      <span>Private Enclave · End-to-End Cryptographic Audit Ledger</span>
      <code>VERIFIED BUILD 2.4.0</code>
    </footer>
  );
}
