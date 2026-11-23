"use client";

import React, { useEffect, useState, useCallback } from "react";
import { AppShell, Button, Badge, Icon } from "../../components/AppShell";
import { ProtectedRoute } from "../../components/ProtectedRoute";
import { useAuth } from "../../context/AuthContext";
import { apiError } from "../../lib/api";


interface AdminUser {
  user_id: string;
  email: string;
  full_name?: string | null;
  user_active: boolean;
  organization_id: string;
  role: string;
  membership_active: boolean;
}

interface AdminOrgSummary {
  organization_id: string;
  name: string;
  slug: string;
  is_active: boolean;
  active_member_count: number;
}

function AdminUsersContent() {
  const { user, activeOrgId, fetchWithAuth, isAuthenticated } = useAuth();
  const currentOrg = activeOrgId || user?.organization_id || "ACME GLOBAL ENTERPRISE";

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [orgSummary, setOrgSummary] = useState<AdminOrgSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successNotice, setSuccessNotice] = useState<string | null>(null);

  // Invite Info Modal
  const [showInviteModal, setShowInviteModal] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setShowInviteModal(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("SUBMITTER");
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviting, setInviting] = useState(false);
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);

  const loadAdminData = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    setError(null);
    try {
      const [usersRes, orgRes] = await Promise.allSettled([
        fetchWithAuth(`/api/admin/users`),
        fetchWithAuth(`/api/admin/organization`),
      ]);

      if (orgRes.status === "fulfilled" && orgRes.value.ok) {
        const orgData = await orgRes.value.json().catch(() => null);
        if (orgData) setOrgSummary(orgData);
      }

      if (usersRes.status === "fulfilled" && usersRes.value.ok) {
        const data = await usersRes.value.json().catch(() => null);
        if (data && Array.isArray(data.users)) {
          setUsers(data.users);
          return;
        }
      } else if (usersRes.status === "fulfilled") {
        const errData = await usersRes.value.json().catch(() => null);
        const msg = apiError(errData, `HTTP ${usersRes.value.status}`);
        setError(`User directory unavailable: ${msg}`);
      } else {
        setError("Network error communicating with user administration service.");
      }

      setUsers([]);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load organization members.");
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }, [fetchWithAuth, isAuthenticated]);

  useEffect(() => {
    const timer = setTimeout(() => {
      loadAdminData();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadAdminData]);

  async function handleAddMember(e: React.FormEvent) {
    e.preventDefault();
    setInviting(true);
    setInviteError(null);
    try {
      const res = await fetchWithAuth("/api/admin/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: inviteEmail.trim(), role: inviteRole }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setInviteError(apiError(data, `Could not add member (HTTP ${res.status}).`));
        return;
      }
      setShowInviteModal(false);
      setInviteEmail("");
      setSuccessNotice(`${data.email} added as ${inviteRole}. Ask them to sign up with this email.`);
      loadAdminData();
    } catch {
      setInviteError("Could not reach the server. Try again.");
    } finally {
      setInviting(false);
    }
  }

  async function handleRoleChange(targetUserId: string, newRole: string) {
    setUpdatingUserId(targetUserId);
    setError(null);
    setSuccessNotice(null);

    try {
      const res = await fetchWithAuth(`/api/admin/users/${targetUserId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          organization_id: currentOrg,
          role: newRole,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(apiError(data, `HTTP ${res.status}`));
      }

      setUsers((prev) =>
        prev.map((u) => (u.user_id === targetUserId ? { ...u, role: newRole } : u))
      );
      setSuccessNotice(`Member role updated to ${newRole}.`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update member role on server.");
    } finally {
      setUpdatingUserId(null);
    }
  }

  async function handleToggleActive(targetUserId: string, currentActive: boolean) {
    setUpdatingUserId(targetUserId);
    setError(null);
    setSuccessNotice(null);

    const nextActive = !currentActive;

    try {
      const res = await fetchWithAuth(`/api/admin/users/${targetUserId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          organization_id: currentOrg,
          is_active: nextActive,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(apiError(data, `HTTP ${res.status}`));
      }

      setUsers((prev) =>
        prev.map((u) =>
          u.user_id === targetUserId ? { ...u, membership_active: nextActive } : u
        )
      );
      setSuccessNotice(`Member account status changed to ${nextActive ? "Active" : "Inactive"}.`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update member status.");
    } finally {
      setUpdatingUserId(null);
    }
  }

  const roleCounts = {
    reviewers: users.filter((u) => u.role === "REVIEWER").length,
    submitters: users.filter((u) => u.role === "SUBMITTER").length,
    approvers: users.filter((u) => u.role === "APPROVER").length,
    admins: users.filter((u) => u.role === "ORG_ADMIN" || u.role === "SYSTEM_ADMIN").length,
  };

  return (
    <AppShell>
      <header className="page-head">
        <div className="crumb">
          <Icon name="contact" size={14} /> Workspace <span>/</span> User Management
          <div className="sync">
            <span className="brand-dot" /> {loading ? "Syncing Directory..." : "RBAC Authority"}
          </div>
        </div>
        <div className="head-main">
          <div>
            <h1>Organization User Management</h1>
            <p className="subline">
              {(orgSummary?.name || currentOrg).toUpperCase()} · ROLE-BASED ACCESS CONTROL · {users.length} TEAM MEMBERS
            </p>
          </div>
          <div style={{ display: "flex", gap: "10px" }}>
            <Button variant="secondary" icon="refresh" onClick={loadAdminData}>
              Sync Directory
            </Button>
            <Button variant="primary" icon="contact" onClick={() => setShowInviteModal(true)}>
              Invite User +
            </Button>
          </div>
        </div>
      </header>

      <div className="intake-body">
        {error && (
          <div
            style={{
              padding: "12px 16px",
              background: "var(--red-bg)",
              border: "1px solid var(--red)",
              color: "var(--red)",
              borderRadius: "6px",
              marginBottom: "20px",
              fontSize: "12px",
            }}
          >
            <b>Administration Notice:</b> {error}
          </div>
        )}

        {successNotice && (
          <div
            style={{
              padding: "12px 16px",
              background: "var(--green-bg)",
              border: "1px solid var(--green)",
              color: "var(--green)",
              borderRadius: "6px",
              marginBottom: "20px",
              fontSize: "12px",
            }}
          >
            <b>Success:</b> {successNotice}
          </div>
        )}

        {/* Metric Summary Blocks matching Figma Board 13 */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: "14px",
            marginBottom: "24px",
          }}
        >
          <div
            style={{
              background: "white",
              border: "1px solid var(--line)",
              borderRadius: "8px",
              padding: "16px 20px",
            }}
          >
            <span className="eyebrow" style={{ display: "block", marginBottom: "6px" }}>
              ACTIVE REVIEWERS
            </span>
            <strong style={{ fontSize: "22px", fontFamily: "'JetBrains Mono', monospace", color: "var(--green)" }}>
              {roleCounts.reviewers}
            </strong>
          </div>

          <div
            style={{
              background: "white",
              border: "1px solid var(--line)",
              borderRadius: "8px",
              padding: "16px 20px",
            }}
          >
            <span className="eyebrow" style={{ display: "block", marginBottom: "6px" }}>
              SUBMITTERS
            </span>
            <strong style={{ fontSize: "22px", fontFamily: "'JetBrains Mono', monospace", color: "var(--violet)" }}>
              {roleCounts.submitters}
            </strong>
          </div>

          <div
            style={{
              background: "white",
              border: "1px solid var(--line)",
              borderRadius: "8px",
              padding: "16px 20px",
            }}
          >
            <span className="eyebrow" style={{ display: "block", marginBottom: "6px" }}>
              APPROVERS
            </span>
            <strong style={{ fontSize: "22px", fontFamily: "'JetBrains Mono', monospace", color: "var(--amber)" }}>
              {roleCounts.approvers}
            </strong>
          </div>

          <div
            style={{
              background: "white",
              border: "1px solid var(--line)",
              borderRadius: "8px",
              padding: "16px 20px",
            }}
          >
            <span className="eyebrow" style={{ display: "block", marginBottom: "6px" }}>
              ORGANIZATION ADMINS
            </span>
            <strong style={{ fontSize: "22px", fontFamily: "'JetBrains Mono', monospace", color: "var(--ink)" }}>
              {roleCounts.admins}
            </strong>
          </div>
        </div>

        {/* User Directory Table */}
        <section className="library-card" style={{ marginTop: 0 }}>
          <div className="library-toolbar">
            <div>
              <span className="eyebrow">ACCREDITED ACCOUNTS</span>
              <h2>Team Directory</h2>
            </div>
            <span style={{ fontSize: "11px", color: "var(--muted)" }}>
              Changes take effect immediately across all Kagaz APIs and access gates.
            </span>
          </div>

          <div className="library-table">
            <div className="lib-row lib-head" style={{ gridTemplateColumns: "2fr 1.2fr 1fr 1fr" }}>
              <span>USER NAME</span>
              <span>ROLE</span>
              <span>STATUS</span>
              <span style={{ textAlign: "right" }}>ACTIONS</span>
            </div>

            {loading ? (
              <div style={{ padding: "40px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
                Loading organization member directory from backend...
              </div>
            ) : users.length === 0 ? (
              <div style={{ padding: "48px 24px", textAlign: "center" }}>
                <Icon name="contact" size={32} />
                <h3 style={{ margin: "12px 0 4px", font: "18px 'Newsreader', serif" }}>
                  {error ? "User Directory Unavailable" : "No users found"}
                </h3>
                <p style={{ margin: "0 auto 16px", maxWidth: "420px", fontSize: "12px", color: "var(--muted)" }}>
                  {error || `There are no accredited accounts in organization ${currentOrg}.`}
                </p>
                <Button variant="secondary" icon="refresh" onClick={loadAdminData}>
                  Retry Directory Sync
                </Button>
              </div>
            ) : (
              users.map((u) => {
                const displayName = u.full_name || u.email.split("@")[0];
                const initials = displayName.slice(0, 2).toUpperCase();

                return (
                  <div
                    key={u.user_id}
                    className="lib-row"
                    style={{ gridTemplateColumns: "2fr 1.2fr 1fr 1fr", cursor: "default" }}
                  >
                    <span className="doc-name">
                      <span
                        style={{
                          width: "32px",
                          height: "32px",
                          borderRadius: "50%",
                          background: "var(--side)",
                          display: "grid",
                          placeItems: "center",
                          fontWeight: 500,
                          fontSize: "11px",
                        }}
                      >
                        {initials}
                      </span>
                      <div>
                        <b>{displayName}</b>
                        <small style={{ display: "block", color: "var(--muted)", fontSize: "10px" }}>
                          {u.email}
                        </small>
                      </div>
                    </span>

                    <div>
                      <select
                        value={u.role}
                        disabled={updatingUserId === u.user_id}
                        onChange={(e) => handleRoleChange(u.user_id, e.target.value)}
                        style={{
                          background: "var(--surface)",
                          border: "1px solid var(--line)",
                          borderRadius: "4px",
                          padding: "3px 6px",
                          fontSize: "11px",
                          cursor: "pointer",
                        }}
                      >
                        <option value="REVIEWER">REVIEWER</option>
                        <option value="SUBMITTER">SUBMITTER</option>
                        <option value="APPROVER">APPROVER</option>
                        <option value="ORG_ADMIN">ORG_ADMIN</option>
                        {user?.role === "SYSTEM_ADMIN" && (
                          <option value="SYSTEM_ADMIN">SYSTEM_ADMIN</option>
                        )}
                      </select>
                    </div>

                    <div>
                      <Badge tone={u.membership_active ? "green" : "red"}>
                        {u.membership_active ? "Active" : "Inactive"}
                      </Badge>
                    </div>

                    <div style={{ textAlign: "right" }}>
                      <button
                        type="button"
                        disabled={updatingUserId === u.user_id}
                        onClick={() => handleToggleActive(u.user_id, u.membership_active)}
                        style={{
                          background: "transparent",
                          border: "1px solid var(--line)",
                          borderRadius: "4px",
                          padding: "3px 8px",
                          fontSize: "10px",
                          cursor: "pointer",
                          color: u.membership_active ? "var(--red)" : "var(--green)",
                        }}
                      >
                        {u.membership_active ? "Deactivate" : "Activate"}
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </section>
      </div>

      {/* Invite Member Limitation & Instructions Modal */}
      {showInviteModal && (
        <div
          className="sheet-backdrop"
          onClick={() => setShowInviteModal(false)}
        >
          <div
            className="library-card"
            style={{
              maxWidth: "520px",
              margin: "100px auto",
              padding: "28px",
              background: "white",
              boxShadow: "0 20px 40px rgba(0,0,0,0.15)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Icon name="contact" size={18} />
                <h3 style={{ margin: 0, font: "20px 'Newsreader', serif" }}>
                  Add Organization Member
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowInviteModal(false)}
                style={{ background: "none", border: "none", fontSize: "20px", cursor: "pointer", color: "var(--muted)" }}
              >
                ×
              </button>
            </div>

            <form onSubmit={handleAddMember} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <p style={{ fontSize: "12px", color: "var(--body)", lineHeight: 1.6, margin: 0 }}>
                Add a person to <b>{orgSummary?.name || "this organization"}</b>. They then sign up on the login page with <b>this same email</b> and will land here with the role you choose.
              </p>
              <label style={{ fontSize: "11px", fontWeight: 500 }}>
                Email
                <input
                  type="email" required value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="name@company.com"
                  style={{ display: "block", width: "100%", height: "36px", marginTop: "6px", border: "1px solid var(--line2, #e0ddd5)", borderRadius: "5px", padding: "0 12px", fontSize: "12px" }}
                />
              </label>
              <label style={{ fontSize: "11px", fontWeight: 500 }}>
                Role
                <select
                  value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}
                  style={{ display: "block", width: "100%", height: "36px", marginTop: "6px", border: "1px solid var(--line2, #e0ddd5)", borderRadius: "5px", padding: "0 8px", fontSize: "12px", background: "white" }}
                >
                  <option value="SUBMITTER">Submitter: uploads documents</option>
                  <option value="REVIEWER">Reviewer: checks assigned documents</option>
                  <option value="APPROVER">Approver: approves or rejects</option>
                  <option value="ORG_ADMIN">Organization Admin: manages members and policies</option>
                </select>
              </label>
              {inviteError && (
                <p role="alert" style={{ margin: 0, color: "var(--red, #dc2626)", fontSize: "12px" }}>{inviteError}</p>
              )}
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                <Button variant="secondary" onClick={() => setShowInviteModal(false)}>Cancel</Button>
                <Button variant="primary" type="submit" disabled={inviting}>{inviting ? "Adding…" : "Add member"}</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppShell>
  );
}

export default function AdminUsersPage() {
  return (
    <ProtectedRoute allowedRoles={["ORG_ADMIN", "SYSTEM_ADMIN"]}>
      <AdminUsersContent />
    </ProtectedRoute>
  );
}
