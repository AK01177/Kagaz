"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

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
  const [userName, setUserName] = useState("Soham Doshi");
  const [userRole, setUserRole] = useState("Reviewer");
  const [intakeCount, setIntakeCount] = useState(3);
  const [reviewCount, setReviewCount] = useState(2);

  useEffect(() => {
    const timer = setTimeout(() => {
      try {
        // Dynamic user detection from localStorage / sessionStorage / JWT
        const email =
          localStorage.getItem("kagaz_user_email") ||
          sessionStorage.getItem("kagaz_user_email");
        const role =
          localStorage.getItem("kagaz_user_role") ||
          sessionStorage.getItem("kagaz_user_role");
        const name =
          localStorage.getItem("kagaz_user_name") ||
          sessionStorage.getItem("kagaz_user_name");

        if (name) {
          setUserName(name);
        } else if (email) {
          setUserName(email.split("@")[0].replace(".", " ").replace(/\b\w/g, (c) => c.toUpperCase()));
        }

        if (role) {
          setUserRole(role.charAt(0).toUpperCase() + role.slice(1).toLowerCase());
        }

        // Dynamic count of documents in session storage
        const storedDocKeys = Object.keys(sessionStorage).filter((k) => k.startsWith("kagaz_doc_"));
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
  const isLogin = pathname === "/login";

  return (
    <aside className="sidebar">
      <div className="brand-row">
        <Link href="/dashboard" className="brand">
          Kagaz.
        </Link>
        <span className="brand-dot" />
        <button type="button" className="collapse" aria-label="Collapse">
          ◫
        </button>
      </div>

      <div className="org">
        <b>Acme Global Enterprise</b>
        <span>Enterprise workspace</span>
      </div>

      <div className="divider" />

      <span className="eyebrow side-label">WORKSPACE</span>

      <nav className="side-nav">
        <Link
          href="/dashboard"
          className={isDashboard ? "active" : ""}
        >
          <Icon name="grid" />
          Workspace Overview
        </Link>
        <Link
          href="/documents"
          className={isIntake ? "active" : ""}
        >
          <Icon name="inbox" />
          Intake &amp; Library <em>{intakeCount}</em>
        </Link>
        <Link
          href="/review"
          className={isReview ? "active" : ""}
        >
          <Icon name="stamp" />
          Verification Desk <em className="amber-count">{reviewCount}</em>
        </Link>
        <Link
          href="/approvals"
          className={isApprovals ? "active" : ""}
        >
          <Icon name="check" />
          Approval Ledger <em>2</em>
        </Link>
        <Link
          href="/admin/users"
          className={isAdmin ? "active" : ""}
        >
          <Icon name="contact" />
          User Management
        </Link>
        <Link
          href="/login"
          className={isLogin ? "active" : ""}
        >
          <Icon name="book" />
          Access &amp; Auth
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
          <span>{userName.slice(0, 2).toUpperCase()}</span>
          <div>
            <b>{userName}</b>
            <small>{userRole}</small>
          </div>
          <Link href="/login" style={{ color: "inherit", textDecoration: "none" }} title="Session settings">
            <Icon name="settings" />
          </Link>
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
