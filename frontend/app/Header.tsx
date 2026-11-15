"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "./context/AuthContext";
import { NotificationCenter } from "./components/NotificationCenter";

interface HeaderProps {
  queueCount?: number;
}

export function Header({ queueCount }: HeaderProps) {
  const pathname = usePathname();
  const { user, isAuthenticated, activeOrgId, fetchWithAuth } = useAuth();
  const [liveQueueCount, setLiveQueueCount] = useState<number | null>(null);

  useEffect(() => {
    if (queueCount !== undefined || !isAuthenticated) {
      return;
    }
    let isMounted = true;
    async function loadCount() {
      try {
        const res = await fetchWithAuth("/api/documents/workflow/review-queue");
        if (res.ok) {
          const data = await res.json().catch(() => null);
          const items = data?.items || (Array.isArray(data) ? data : []);
          if (isMounted) setLiveQueueCount(items.length);
        } else {
          if (isMounted) setLiveQueueCount(0);
        }
      } catch {
        if (isMounted) setLiveQueueCount(0);
      }
    }
    loadCount();
    return () => {
      isMounted = false;
    };
  }, [queueCount, isAuthenticated, fetchWithAuth]);

  const isHome = pathname === "/";
  const isIntake = pathname === "/documents";
  const isReview = pathname.startsWith("/review");
  const isLogin = pathname === "/login";

  const displayName = user?.name || user?.email?.split("@")[0];
  const displayCount = queueCount !== undefined ? queueCount : liveQueueCount;

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
          href="/documents"
          className={isIntake ? "active" : ""}
          style={isIntake ? { color: "var(--ink)", fontWeight: 600 } : undefined}
        >
          Files
        </Link>
        <Link
          href="/review"
          className={isReview ? "active" : ""}
          style={isReview ? { color: "var(--ink)", fontWeight: 600 } : undefined}
        >
          Review {displayCount !== null && displayCount > 0 && <span className="nav-count">{displayCount}</span>}
        </Link>
        <Link
          href="/login"
          className={isLogin ? "active" : ""}
          style={isLogin ? { color: "var(--ink)", fontWeight: 600 } : undefined}
        >
          {isAuthenticated ? "Workspace" : "Sign In"}
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
