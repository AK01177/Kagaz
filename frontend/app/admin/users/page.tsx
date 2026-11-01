"use client";

import { useState } from "react";
import Link from "next/link";
import { AppShell, Button, Badge, Icon } from "../../components/AppShell";

interface UserRecord {
  id: string;
  name: string;
  email: string;
  role: "REVIEWER" | "SUBMITTER" | "APPROVER" | "ORG_ADMIN";
  status: "Active" | "Inactive";
  lastLogin: string;
}

const DEFAULT_USERS: UserRecord[] = [
  {
    id: "usr_soham_doshi",
    name: "Soham Doshi",
    email: "soham.reviewer@kagaz.ai",
    role: "REVIEWER",
    status: "Active",
    lastLogin: "Just now",
  },
  {
    id: "usr_jane_submitter",
    name: "Jane Doe",
    email: "jane.submitter@kagaz.ai",
    role: "SUBMITTER",
    status: "Active",
    lastLogin: "Today · 14:10",
  },
  {
    id: "usr_klaus_reinhardt",
    name: "Klaus Reinhardt",
    email: "klaus.reinhardt@acme.de",
    role: "REVIEWER",
    status: "Active",
    lastLogin: "Yesterday · 08:30",
  },
  {
    id: "usr_budget_head",
    name: "Marcus Vance",
    email: "m.vance@acme.com",
    role: "APPROVER",
    status: "Active",
    lastLogin: "24 Sep · 11:20",
  },
  {
    id: "usr_admin",
    name: "System Administrator",
    email: "admin@kagaz.ai",
    role: "ORG_ADMIN",
    status: "Active",
    lastLogin: "Today · 09:15",
  },
];

export default function AdminUsersPage() {
  const [users, setUsers] = useState<UserRecord[]>(DEFAULT_USERS);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newRole, setNewRole] = useState<"REVIEWER" | "SUBMITTER" | "APPROVER" | "ORG_ADMIN">("SUBMITTER");

  function handleAddUser(e: React.FormEvent) {
    e.preventDefault();
    if (!newEmail || !newName) return;
    const newUser: UserRecord = {
      id: `usr_${newEmail.split("@")[0].replace(".", "_")}`,
      name: newName,
      email: newEmail,
      role: newRole,
      status: "Active",
      lastLogin: "Invited",
    };
    setUsers((prev) => [newUser, ...prev]);
    setNewName("");
    setNewEmail("");
    setShowAddModal(false);
  }

  function toggleStatus(id: string) {
    setUsers((prev) =>
      prev.map((u) =>
        u.id === id ? { ...u, status: u.status === "Active" ? "Inactive" : "Active" } : u
      )
    );
  }

  const roleCounts = {
    reviewers: users.filter((u) => u.role === "REVIEWER").length,
    submitters: users.filter((u) => u.role === "SUBMITTER").length,
    approvers: users.filter((u) => u.role === "APPROVER").length,
    admins: users.filter((u) => u.role === "ORG_ADMIN").length,
  };

  return (
    <AppShell>
      <header className="page-head">
        <div className="crumb">
          <Icon name="contact" size={14} /> Workspace <span>/</span> User Management
          <div className="sync">
            <span className="brand-dot" /> Synced just now
          </div>
        </div>
        <div className="head-main">
          <div>
            <h1>Organization User Management</h1>
            <p className="subline">ROLE-BASED ACCESS CONTROL · {users.length} TEAM MEMBERS</p>
          </div>
          <Button variant="primary" icon="contact" onClick={() => setShowAddModal(true)}>
            Invite User +
          </Button>
        </div>
      </header>

      <div className="intake-body">
        {/* Metric Summary Blocks */}
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
              SYSTEM ADMINS
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
              Changes take effect immediately across all Kagaz APIs.
            </span>
          </div>

          <div className="library-table">
            <div className="lib-row lib-head" style={{ gridTemplateColumns: "2fr 1.2fr 1fr 1fr 1fr" }}>
              <span>USER NAME</span>
              <span>ROLE</span>
              <span>STATUS</span>
              <span>LAST LOGIN</span>
              <span style={{ textAlign: "right" }}>ACTIONS</span>
            </div>

            {users.map((u) => (
              <div
                key={u.id}
                className="lib-row"
                style={{ gridTemplateColumns: "2fr 1.2fr 1fr 1fr 1fr", cursor: "default" }}
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
                    {u.name.slice(0, 2).toUpperCase()}
                  </span>
                  <div>
                    <b>{u.name}</b>
                    <small style={{ display: "block", color: "var(--muted)", fontSize: "10px" }}>
                      {u.email}
                    </small>
                  </div>
                </span>

                <div>
                  <Badge
                    tone={
                      u.role === "REVIEWER"
                        ? "green"
                        : u.role === "ORG_ADMIN"
                        ? "amber"
                        : "violet"
                    }
                  >
                    {u.role}
                  </Badge>
                </div>

                <div>
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                      fontSize: "10px",
                      fontWeight: 500,
                      color: u.status === "Active" ? "var(--green)" : "var(--muted)",
                    }}
                  >
                    <i
                      style={{
                        width: "6px",
                        height: "6px",
                        borderRadius: "50%",
                        background: u.status === "Active" ? "var(--green)" : "var(--muted)",
                      }}
                    />
                    {u.status}
                  </span>
                </div>

                <span>{u.lastLogin}</span>

                <div style={{ display: "flex", gap: "6px", justifyContent: "flex-end" }}>
                  <Button
                    variant="ghost"
                    onClick={() => toggleStatus(u.id)}
                  >
                    {u.status === "Active" ? "Deactivate" : "Activate"}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Invite User Modal */}
      {showAddModal && (
        <div className="sheet-backdrop" onMouseDown={() => setShowAddModal(false)}>
          <aside className="override-sheet" onMouseDown={(e) => e.stopPropagation()} style={{ width: "420px" }}>
            <div className="sheet-bar">
              <span>
                <Icon name="contact" /> INVITE TEAM MEMBER
              </span>
              <button type="button" onClick={() => setShowAddModal(false)}>
                ×
              </button>
            </div>

            <form onSubmit={handleAddUser} className="sheet-form">
              <div>
                <h2>Grant Workspace Access</h2>
                <p>
                  Invite an authorized user to this organization. Assigned roles determine whether they can upload, review, or approve documents.
                </p>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "11px", fontWeight: 500, marginBottom: "6px" }}>
                  Full Name
                </label>
                <input
                  required
                  placeholder="e.g. Alex Morgan"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  style={{
                    width: "100%",
                    height: "36px",
                    border: "1px solid var(--line2)",
                    borderRadius: "5px",
                    padding: "0 12px",
                    fontSize: "12px",
                  }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "11px", fontWeight: 500, marginBottom: "6px" }}>
                  Work Email Address
                </label>
                <input
                  type="email"
                  required
                  placeholder="alex@acme.com"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  style={{
                    width: "100%",
                    height: "36px",
                    border: "1px solid var(--line2)",
                    borderRadius: "5px",
                    padding: "0 12px",
                    fontSize: "12px",
                  }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "11px", fontWeight: 500, marginBottom: "6px" }}>
                  Role &amp; Permissions
                </label>
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value as any)}
                  style={{
                    width: "100%",
                    height: "36px",
                    border: "1px solid var(--line2)",
                    borderRadius: "5px",
                    padding: "0 12px",
                    background: "white",
                    fontSize: "12px",
                  }}
                >
                  <option value="SUBMITTER">Submitter (Can deposit documents)</option>
                  <option value="REVIEWER">Reviewer (Can inspect &amp; correct low-confidence files)</option>
                  <option value="APPROVER">Approver (Can certify or reject policy items)</option>
                  <option value="ORG_ADMIN">Organization Admin (Full administration)</option>
                </select>
              </div>

              <div style={{ marginTop: "auto", display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                <Button variant="secondary" onClick={() => setShowAddModal(false)}>
                  Cancel
                </Button>
                <Button type="submit" variant="primary" icon="check">
                  Send Workspace Invite
                </Button>
              </div>
            </form>
          </aside>
        </div>
      )}
    </AppShell>
  );
}
