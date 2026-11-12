"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AppShell, Button, Badge, Icon } from "../components/AppShell";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

interface AuthUser {
  user_id: string;
  name: string;
  email: string;
  role: string;
  organization_id: string;
}

function clearStoredSession(): void {
  for (const key of ["kagaz_token", "kagaz_user_email", "kagaz_user_role", "kagaz_user_name"]) {
    localStorage.removeItem(key);
    sessionStorage.removeItem(key);
  }
}

export default function LoginPage() {
  const router = useRouter();
  const [activeUser, setActiveUser] = useState<AuthUser | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    let ignore = false;

    async function verifyStoredSession() {
      try {
        const token =
          localStorage.getItem("kagaz_token") || sessionStorage.getItem("kagaz_token");
        if (!token || token === "undefined" || token === "null" || !token.includes(".")) {
          clearStoredSession();
          return;
        }
        const res = await fetch(`${API_URL}/api/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
          clearStoredSession();
          return;
        }
        const profile = await res.json();
        if (!ignore) {
          setActiveUser({
            user_id: profile.user_id,
            name: profile.name || profile.email,
            email: profile.email || "",
            role: profile.role,
            organization_id: profile.organization_id,
          });
        }
      } catch {
        // Leave existing activeUser unset if backend is unreachable
      }
    }

    verifyStoredSession();
    return () => {
      ignore = true;
    };
  }, []);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setNotice(null);

    const loginEmail = email.trim().toLowerCase();
    if (!loginEmail || !password) {
      setNotice({ type: "error", message: "Email and password are required." });
      setLoading(false);
      return;
    }

    try {
      const res = await fetch(`${API_URL}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: loginEmail, password }),
      });

      const data = await res.json().catch(() => null);
      if (!res.ok) {
        const serverMessage =
          data?.error?.message || data?.detail?.message || "Invalid email or password.";
        setNotice({ type: "error", message: serverMessage });
        setLoading(false);
        return;
      }

      const token = data.access_token;
      const user: AuthUser = data.user;

      localStorage.setItem("kagaz_token", token);
      sessionStorage.setItem("kagaz_token", token);
      localStorage.setItem("kagaz_user_email", user.email);
      sessionStorage.setItem("kagaz_user_email", user.email);
      localStorage.setItem("kagaz_user_role", user.role);
      sessionStorage.setItem("kagaz_user_role", user.role);
      localStorage.setItem("kagaz_user_name", user.name);
      sessionStorage.setItem("kagaz_user_name", user.name);

      setActiveUser(user);
      setPassword("");
      setNotice({
        type: "success",
        message: `Authenticated as ${user.name} (${user.role}).`,
      });
      setTimeout(() => {
        router.push("/documents");
      }, 600);
    } catch {
      setNotice({
        type: "error",
        message: "Unable to reach the authentication service.",
      });
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    clearStoredSession();
    setActiveUser(null);
    setNotice({ type: "success", message: "Signed out successfully." });
  }

  return (
    <AppShell>
      <header className="page-head">
        <div className="crumb">
          <Icon name="book" size={14} /> Workspace <span>/</span> Access &amp; Authentication
          <div className="sync">
            <span className="brand-dot" /> Identity Verified
          </div>
        </div>
        <div className="head-main">
          <div>
            <h1>Session &amp; Credentials</h1>
            <p className="subline">ROLE-BASED GOVERNANCE · SIGNED JWT AUTHORIZATION</p>
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <Link href="/documents" className="btn secondary" style={{ textDecoration: "none" }}>
              Intake Desk →
            </Link>
            <Link href="/review" className="btn primary" style={{ textDecoration: "none" }}>
              Review Desk →
            </Link>
          </div>
        </div>
      </header>

      <div className="intake-body" style={{ maxWidth: "720px" }}>
        {notice && (
          <div
            style={{
              padding: "12px 16px",
              background: notice.type === "success" ? "var(--green-bg)" : "var(--red-bg)",
              border: `1px solid ${notice.type === "success" ? "var(--green)" : "var(--red)"}`,
              color: notice.type === "success" ? "var(--green)" : "var(--red)",
              borderRadius: "6px",
              marginBottom: "20px",
              fontSize: "12px",
            }}
          >
            <b>{notice.type === "success" ? "Session Updated:" : "Authentication Failed:"}</b>{" "}
            {notice.message}
          </div>
        )}

        {activeUser ? (
          <div
            className="library-card"
            style={{ marginTop: 0, padding: "24px", marginBottom: "24px" }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <span className="eyebrow">ACTIVE CREDENTIALS</span>
                <h2 style={{ margin: "6px 0 2px", font: "22px 'Newsreader', serif" }}>
                  {activeUser.name}
                </h2>
                <p style={{ margin: 0, color: "var(--muted)", fontSize: "11px" }}>
                  <code>{activeUser.email}</code> · User ID: <code>{activeUser.user_id}</code>
                </p>
              </div>
              <Badge tone={activeUser.role === "REVIEWER" ? "green" : "violet"}>
                {activeUser.role}
              </Badge>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                gap: "12px",
                margin: "20px 0",
                padding: "14px",
                background: "var(--side)",
                borderRadius: "6px",
                fontSize: "11px",
              }}
            >
              <div>
                <span style={{ color: "var(--muted)", display: "block" }}>Organization</span>
                <b>{activeUser.organization_id}</b>
              </div>
              <div>
                <span style={{ color: "var(--muted)", display: "block" }}>Membership Role</span>
                <b>{activeUser.role}</b>
              </div>
              <div>
                <span style={{ color: "var(--muted)", display: "block" }}>Auth Mechanism</span>
                <b>HS256 Bearer Token</b>
              </div>
            </div>

            <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
              <Button variant="secondary" onClick={handleLogout}>
                Sign Out of Workspace
              </Button>
            </div>
          </div>
        ) : null}

        <div className="library-card" style={{ marginTop: 0, padding: "24px" }}>
          <span className="eyebrow">REGISTERED CREDENTIALS</span>
          <h2 style={{ margin: "6px 0 16px", font: "20px 'Newsreader', serif" }}>
            Sign In to Kagaz
          </h2>

          <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: 500, marginBottom: "6px" }}>
                Work Email Address
              </label>
              <input
                type="email"
                required
                placeholder="name@enterprise.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={{
                  width: "100%",
                  height: "36px",
                  border: "1px solid var(--line2)",
                  borderRadius: "5px",
                  padding: "0 12px",
                  background: "white",
                  fontSize: "12px",
                }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: 500, marginBottom: "6px" }}>
                Password
              </label>
              <input
                type="password"
                required
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={{
                  width: "100%",
                  height: "36px",
                  border: "1px solid var(--line2)",
                  borderRadius: "5px",
                  padding: "0 12px",
                  background: "white",
                  fontSize: "12px",
                }}
              />
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "8px" }}>
              <Button type="submit" variant="primary" icon="check" disabled={loading}>
                {loading ? "Authenticating..." : "Authenticate Session →"}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </AppShell>
  );
}
