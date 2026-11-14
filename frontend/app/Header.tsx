"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "./context/AuthContext";

interface HeaderProps {
  queueCount?: number;
}

export function Header({ queueCount = 4 }: HeaderProps) {
  const pathname = usePathname();
  const { user, isAuthenticated, activeOrgId } = useAuth();

  const isHome = pathname === "/";
  const isIntake = pathname === "/documents";
  const isReview = pathname.startsWith("/review");
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
          style={isHome ? { color: "var(--ink)", fontWeight: 600 } : undefined}
        >
          Manifesto
        </Link>
        <Link
          href="/documents"
          className={isIntake ? "active" : ""}
          style={isIntake ? { color: "var(--ink)", fontWeight: 600 } : undefined}
        >
          Intake
        </Link>
        <Link
          href="/review"
          className={isReview ? "active" : ""}
          style={isReview ? { color: "var(--ink)", fontWeight: 600 } : undefined}
        >
          Review Queue <span className="nav-count">{queueCount}</span>
        </Link>
        <Link
          href="/login"
          className={isLogin ? "active" : ""}
          style={isLogin ? { color: "var(--ink)", fontWeight: 600 } : undefined}
        >
          {isAuthenticated ? "Workspace" : "Sign In"}
        </Link>
      </nav>
      <Link
        href="/login"
        className="session"
        style={{ textDecoration: "none" }}
        title={isAuthenticated ? `Active in ${activeOrgId || user?.organization_id}` : "Sign in to workspace"}
      >
        <i style={isAuthenticated ? { background: "var(--green)" } : undefined} />{" "}
        {isAuthenticated && displayName ? displayName : "Sign In"}
      </Link>
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
