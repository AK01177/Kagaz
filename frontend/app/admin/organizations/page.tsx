"use client";

import React, { useCallback, useEffect, useState } from "react";
import { AppShell, Button, Badge, Icon } from "../../components/AppShell";
import { useAuth } from "../../context/AuthContext";
import { apiError } from "../../lib/api";

interface Organization {
  organization_id: string;
  name: string;
  slug: string;
  is_active: boolean;
  active_member_count: number;
}

export default function OrganizationsPage() {
  const { fetchWithAuth, isAuthenticated } = useAuth();
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    try {
      const res = await fetchWithAuth("/api/admin/organizations");
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(apiError(data, `HTTP ${res.status}`));
      setOrgs(data.organizations);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load organizations.");
    } finally {
      setLoading(false);
    }
  }, [fetchWithAuth, isAuthenticated]);

  useEffect(() => {
    const timer = setTimeout(load, 0);
    return () => clearTimeout(timer);
  }, [load]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    setNotice(null);
    try {
      const res = await fetchWithAuth("/api/admin/organizations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), admin_email: adminEmail.trim() }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(apiError(data, `Could not create the organization (HTTP ${res.status}).`));
      setNotice(`"${data.name}" created. ${adminEmail.trim()} should now sign up on the login page to become its admin.`);
      setName("");
      setAdminEmail("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the organization.");
    } finally {
      setCreating(false);
    }
  }

  const input = { display: "block", width: "100%", height: "36px", marginTop: "6px", border: "1px solid var(--line2, #e0ddd5)", borderRadius: "5px", padding: "0 12px", fontSize: "12px" } as const;

  return (
    <AppShell>
      <header className="page-head">
        <div className="crumb">
          <Icon name="book" size={14} /> Platform <span>/</span> Organizations
        </div>
        <div className="head-main">
          <div>
            <h1>Organizations</h1>
            <p className="subline">{orgs.length} ORGANIZATIONS ON THE PLATFORM</p>
          </div>
          <Button variant="secondary" icon="refresh" onClick={load}>Refresh</Button>
        </div>
      </header>

      <div className="intake-body">
        {error && (
          <p role="alert" style={{ padding: "12px 16px", background: "var(--red-bg)", border: "1px solid var(--red)", color: "var(--red)", borderRadius: "6px", fontSize: "12px" }}>{error}</p>
        )}
        {notice && (
          <p style={{ padding: "12px 16px", background: "var(--green-bg)", border: "1px solid var(--green)", color: "var(--green)", borderRadius: "6px", fontSize: "12px" }}>{notice}</p>
        )}

        <section className="library-card" style={{ padding: "20px", marginBottom: "24px" }}>
          <h2 style={{ margin: "0 0 4px", font: "18px 'Newsreader', serif" }}>Create an organization</h2>
          <p style={{ margin: "0 0 14px", fontSize: "12px", color: "var(--muted)" }}>
            Enter the first administrator&apos;s email. They sign up with it and can then add their own team.
          </p>
          <form onSubmit={handleCreate} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "14px", alignItems: "end" }}>
            <label style={{ fontSize: "11px", fontWeight: 500 }}>
              Organization name
              <input style={input} required minLength={2} value={name} onChange={(e) => setName(e.target.value)} placeholder="Gamma Ltd" />
            </label>
            <label style={{ fontSize: "11px", fontWeight: 500 }}>
              First admin&apos;s email
              <input style={input} required type="email" value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} placeholder="admin@gamma.com" />
            </label>
            <Button variant="primary" type="submit" disabled={creating}>{creating ? "Creating…" : "Create organization"}</Button>
          </form>
        </section>

        <section className="library-card" style={{ padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
            <thead>
              <tr style={{ textAlign: "left", color: "var(--muted)", borderBottom: "1px solid var(--line2, #e0ddd5)" }}>
                <th style={{ padding: "12px 16px" }}>Name</th>
                <th>Slug</th>
                <th>Active members</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {loading && <tr><td colSpan={4} style={{ padding: "20px 16px", color: "var(--muted)" }}>Loading…</td></tr>}
              {!loading && orgs.length === 0 && <tr><td colSpan={4} style={{ padding: "20px 16px", color: "var(--muted)" }}>No organizations yet.</td></tr>}
              {orgs.map((o) => (
                <tr key={o.organization_id} style={{ borderBottom: "1px solid var(--line2, #e0ddd5)" }}>
                  <td style={{ padding: "12px 16px" }}><b>{o.name}</b></td>
                  <td><code>{o.slug}</code></td>
                  <td>{o.active_member_count}</td>
                  <td><Badge tone={o.is_active ? "green" : "amber"}>{o.is_active ? "Active" : "Inactive"}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </AppShell>
  );
}
