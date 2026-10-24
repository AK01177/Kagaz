"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

interface HeaderProps {
  queueCount?: number;
}

export function Header({ queueCount = 4 }: HeaderProps) {
  const pathname = usePathname();
  const isHome = pathname === "/";
  const isIntake = pathname === "/documents";
  const isReview = pathname.startsWith("/review");
  const isLogin = pathname === "/login";

  const [userEmail] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      try {
        return (
          localStorage.getItem("kagaz_user_email") ||
          sessionStorage.getItem("kagaz_user_email") ||
          null
        );
      } catch {}
    }
    return null;
  });

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
          {userEmail ? "Account" : "Sign In"}
        </Link>
      </nav>
      <Link
        href="/login"
        className="session"
        style={{ textDecoration: "none" }}
        title="View session credentials"
      >
        <i /> {userEmail ? userEmail.split("@")[0] : "Session Active"}
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
