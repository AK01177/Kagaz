"use client";

import React, { useEffect, useState, useRef } from "react";
import { AppShell, Button, Badge, Icon } from "../../components/AppShell";
import { ProtectedRoute } from "../../components/ProtectedRoute";
import { useAuth } from "../../context/AuthContext";
import { apiError } from "../../lib/api";


interface PolicyVersion {
  id: string;
  policy_id: string;
  version: string;
  status: "PROCESSING" | "ACTIVE" | "ARCHIVED" | "FAILED";
  chunk_count: number;
  error_message?: string | null;
  created_at: string;
}

interface Policy {
  id: string;
  organization_id: string;
  name: string;
  domain?: string | null;
  document_type?: string | null;
  description?: string | null;
  is_active: boolean;
  current_version?: string | null;
  created_at: string;
  updated_at: string;
  versions?: PolicyVersion[];
}

// The document categories the classifier assigns. A policy applies to one of them, or to all.
const APPLIES_TO_OPTIONS = [
  { value: "", label: "All document types" },
  { value: "financial", label: "Financial (invoices, receipts, expense claims)" },
  { value: "hr_documents", label: "HR (resumes, forms, offer letters)" },
  { value: "academics", label: "Academic (transcripts, records)" },
  { value: "general_confidential", label: "General / confidential (contracts, IDs, other)" },
];

function appliesToLabel(documentType?: string | null): string {
  const option = APPLIES_TO_OPTIONS.find((item) => item.value === (documentType || ""));
  return option ? option.label.split(" (")[0] : documentType || "All document types";
}

function PoliciesContent() {
  const { fetchWithAuth, activeOrgId, user } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Upload Form State
  const [showUploadForm, setShowUploadForm] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setShowUploadForm(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [policyName, setPolicyName] = useState("");
  const [versionStr, setVersionStr] = useState("1.0.0");
  const [domain, setDomain] = useState("Finance");
  const [appliesTo, setAppliesTo] = useState("");
  const [description, setDescription] = useState("");
  const [isIngesting, setIsIngesting] = useState(false);

  // Versions expanded tracker
  const [expandedPolicyId, setExpandedPolicyId] = useState<string | null>(null);
  const [policyVersions, setPolicyVersions] = useState<Record<string, PolicyVersion[]>>({});
  const [loadingVersions, setLoadingVersions] = useState<Record<string, boolean>>({});
  const [retryingVersionId, setRetryingVersionId] = useState<string | null>(null);

  const currentOrg = activeOrgId || user?.organization_id || "Enterprise Workspace";

  const loadPolicies = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth(`/api/policies`);
      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(apiError(errData, `HTTP ${res.status}`));
      }
      const data: Policy[] = await res.json();
      setPolicies(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load policies from server.");
    } finally {
      setLoading(false);
    }
  }, [fetchWithAuth]);

  useEffect(() => {
    const timer = setTimeout(() => {
      loadPolicies();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadPolicies]);

  const loadVersions = async (policyId: string) => {
    setLoadingVersions((prev) => ({ ...prev, [policyId]: true }));
    try {
      const res = await fetchWithAuth(`/api/policies/${policyId}/versions`);
      if (res.ok) {
        // The API names these fields differently from the list below, so map them once here.
        const rows: Array<Record<string, string | number | null>> = await res.json();
        const versionsData: PolicyVersion[] = rows.map((row) => ({
          id: String(row.policy_version_id),
          policy_id: policyId,
          version: String(row.version),
          status: row.status as PolicyVersion["status"],
          chunk_count: Number(row.chunk_count ?? 0),
          error_message: row.ingestion_error ? String(row.ingestion_error) : null,
          created_at: String(row.created_at ?? ""),
        }));
        setPolicyVersions((prev) => ({ ...prev, [policyId]: versionsData }));
      }
    } catch {
      // Ignored
    } finally {
      setLoadingVersions((prev) => ({ ...prev, [policyId]: false }));
    }
  };

  const toggleExpand = (policyId: string) => {
    if (expandedPolicyId === policyId) {
      setExpandedPolicyId(null);
    } else {
      setExpandedPolicyId(policyId);
      if (!policyVersions[policyId]) {
        loadVersions(policyId);
      }
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) {
      setError("Please select a policy file (PDF, DOCX or TXT) to upload.");
      return;
    }
    if (!policyName.trim()) {
      setError("Policy title is required.");
      return;
    }

    setIsIngesting(true);
    setError(null);
    setSuccessMsg(null);

    const formData = new FormData();
    formData.append("file", uploadFile);
    formData.append("policy_name", policyName.trim());
    formData.append("version", versionStr.trim() || "1.0.0");
    if (domain) formData.append("domain", domain.trim());
    if (appliesTo) formData.append("document_type", appliesTo);
    if (description) formData.append("description", description.trim());

    try {
      const res = await fetchWithAuth(`/api/policies/ingest`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        const msg = apiError(data, `Ingestion failed with status ${res.status}`);
        throw new Error(msg);
      }

      if (data.status !== "ACTIVE") {
        // The API answers 201 even when indexing failed; the reason is stored on the version.
        await loadPolicies();
        throw new Error(
          `'${policyName.trim()}' v${data.version} was saved but is not searchable yet: ${data.ingestion_error || data.status}. Open the policy and use "Retry Ingestion" once the cause is fixed.`
        );
      }
      setSuccessMsg(
        `Policy '${policyName.trim()}' v${data.version} ingested successfully (${data.chunk_count} searchable chunks).`
      );
      setShowUploadForm(false);
      setUploadFile(null);
      setPolicyName("");
      setDescription("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      await loadPolicies();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Policy ingestion failed.");
    } finally {
      setIsIngesting(false);
    }
  };

  const handleToggleActive = async (policy: Policy) => {
    try {
      const nextActive = !policy.is_active;
      const res = await fetchWithAuth(`/api/policies/${policy.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: nextActive }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(apiError(data, "Failed to update policy status."));
      }

      setPolicies((prev) =>
        prev.map((p) => (p.id === policy.id ? { ...p, is_active: nextActive } : p))
      );
      setSuccessMsg(`Policy '${policy.name}' is now ${nextActive ? "Active" : "Inactive"}.`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error updating policy status.");
    }
  };

  const handleRetryIngestion = async (policyId: string, versionId: string) => {
    setRetryingVersionId(versionId);
    setError(null);
    try {
      const res = await fetchWithAuth(
        `/api/policies/${policyId}/versions/${versionId}/retry`,
        { method: "POST" }
      );
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(apiError(data, "Retry failed."));
      }
      const retried = await res.json().catch(() => null);
      if (retried && retried.status !== "ACTIVE") {
        throw new Error(`Retry did not succeed: ${retried.ingestion_error || retried.status}.`);
      }
      setSuccessMsg("Policy version ingestion retry completed successfully.");
      await loadVersions(policyId);
      await loadPolicies();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to retry policy ingestion.");
    } finally {
      setRetryingVersionId(null);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "ACTIVE":
        return <Badge tone="green">ACTIVE</Badge>;
      case "PROCESSING":
        return <Badge tone="violet">PROCESSING</Badge>;
      case "FAILED":
        return <Badge tone="red">FAILED</Badge>;
      case "ARCHIVED":
        return <Badge tone="amber">ARCHIVED</Badge>;
      default:
        return <Badge tone="amber">{status}</Badge>;
    }
  };

  return (
    <AppShell>
      <header className="page-head">
        <div className="crumb">
          <Icon name="shield" size={14} /> Workspace <span>/</span> Governance <span>/</span> Policies
          <div className="sync">
            <span className="brand-dot" /> Admin Authority
          </div>
        </div>
        <div className="head-main">
          <div>
            <h1>Policy Governance &amp; Ingestion</h1>
            <p className="subline">
              {currentOrg.toUpperCase()} · RAG KNOWLEDGE BASE · {policies.length} ENTERPRISE POLICIES
            </p>
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <Button
              variant="primary"
              icon="stamp"
              onClick={() => setShowUploadForm(!showUploadForm)}
            >
              {showUploadForm ? "Close Form" : "Upload Policy +"}
            </Button>
            <Button variant="secondary" icon="refresh" onClick={loadPolicies}>
              Refresh
            </Button>
          </div>
        </div>
      </header>

      <div className="intake-body" style={{ maxWidth: "1000px" }}>
        {error && (
          <div
            style={{
              padding: "12px 16px",
              background: "var(--red-bg, #fef2f2)",
              border: "1px solid var(--red, #dc2626)",
              color: "var(--red, #dc2626)",
              borderRadius: "6px",
              marginBottom: "20px",
              fontSize: "12px",
            }}
          >
            <b>Policy Operation Error:</b> {error}
          </div>
        )}

        {successMsg && (
          <div
            style={{
              padding: "12px 16px",
              background: "var(--green-bg, #f0fdf4)",
              border: "1px solid var(--green, #16a34a)",
              color: "var(--green, #16a34a)",
              borderRadius: "6px",
              marginBottom: "20px",
              fontSize: "12px",
            }}
          >
            <b>Success:</b> {successMsg}
          </div>
        )}

        {/* Upload Form Modal / Drawer */}
        {showUploadForm && (
          <div
            className="library-card"
            style={{
              marginTop: 0,
              padding: "24px",
              marginBottom: "24px",
              border: "1px solid var(--violet, #7c3aed)",
              background: "#faf9fd",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "16px" }}>
              <div>
                <span className="eyebrow" style={{ color: "var(--violet, #7c3aed)" }}>
                  INGEST NEW POLICY KNOWLEDGE
                </span>
                <h2 style={{ margin: "4px 0", font: "20px 'Newsreader', serif" }}>
                  Upload Policy File &amp; Vectorize
                </h2>
                <p style={{ margin: 0, fontSize: "11px", color: "var(--muted)" }}>
                  Uploaded PDF, DOCX and TXT files are split into clauses with their section and page, and indexed for policy validation and the assistant.
                </p>
              </div>
            </div>

            <form onSubmit={handleUploadSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "11px", fontWeight: 600, marginBottom: "6px" }}>
                    Policy Title *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Accounts Payable & Tax Compliance Policy"
                    value={policyName}
                    onChange={(e) => setPolicyName(e.target.value)}
                    style={{
                      width: "100%",
                      height: "36px",
                      border: "1px solid var(--line2, #e0ddd5)",
                      borderRadius: "5px",
                      padding: "0 12px",
                      fontSize: "12px",
                      background: "white",
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "11px", fontWeight: 600, marginBottom: "6px" }}>
                    Version Tag *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. 1.0.0 or 2026.Q4"
                    value={versionStr}
                    onChange={(e) => setVersionStr(e.target.value)}
                    style={{
                      width: "100%",
                      height: "36px",
                      border: "1px solid var(--line2, #e0ddd5)",
                      borderRadius: "5px",
                      padding: "0 12px",
                      fontSize: "12px",
                      background: "white",
                    }}
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "11px", fontWeight: 600, marginBottom: "6px" }}>
                    Domain / Category
                  </label>
                  <select
                    value={domain}
                    onChange={(e) => setDomain(e.target.value)}
                    style={{
                      width: "100%",
                      height: "36px",
                      border: "1px solid var(--line2, #e0ddd5)",
                      borderRadius: "5px",
                      padding: "0 12px",
                      fontSize: "12px",
                      background: "white",
                    }}
                  >
                    <option value="Finance">Finance &amp; Procurement</option>
                    <option value="Travel">Travel &amp; Entertainment</option>
                    <option value="Legal">Legal &amp; Contracts</option>
                    <option value="HR">HR &amp; Personnel</option>
                    <option value="Security">Security &amp; Compliance</option>
                    <option value="General">General Governance</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "11px", fontWeight: 600, marginBottom: "6px" }}>
                    Applies to
                  </label>
                  <select
                    value={appliesTo}
                    onChange={(e) => setAppliesTo(e.target.value)}
                    style={{
                      width: "100%",
                      height: "36px",
                      border: "1px solid var(--line2, #e0ddd5)",
                      borderRadius: "5px",
                      padding: "0 12px",
                      fontSize: "12px",
                      background: "white",
                    }}
                  >
                    {APPLIES_TO_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "11px", fontWeight: 600, marginBottom: "6px" }}>
                    Select Policy File (PDF, DOCX or TXT) *
                  </label>
                  <input
                    ref={fileInputRef}
                    type="file"
                    required
                    accept=".pdf,.docx,.txt"
                    onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                    style={{
                      width: "100%",
                      height: "36px",
                      border: "1px solid var(--line2, #e0ddd5)",
                      borderRadius: "5px",
                      padding: "5px 10px",
                      fontSize: "11px",
                      background: "white",
                    }}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "11px", fontWeight: 600, marginBottom: "6px" }}>
                  Description / Governance Intent (Optional)
                </label>
                <textarea
                  rows={2}
                  placeholder="Summary of policy guidelines and applicable review ceilings..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  style={{
                    width: "100%",
                    border: "1px solid var(--line2, #e0ddd5)",
                    borderRadius: "5px",
                    padding: "8px 12px",
                    fontSize: "12px",
                    background: "white",
                    resize: "vertical",
                  }}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "8px" }}>
                <Button variant="secondary" onClick={() => setShowUploadForm(false)}>
                  Cancel
                </Button>
                <Button type="submit" variant="primary" icon="check" disabled={isIngesting}>
                  {isIngesting ? "Parsing & Indexing Embeddings..." : "Ingest Policy File →"}
                </Button>
              </div>
            </form>
          </div>
        )}

        {/* Policy List Card */}
        <section className="library-card" style={{ marginTop: 0 }}>
          <div className="library-toolbar">
            <div>
              <span className="eyebrow">ORGANIZATION KNOWLEDGE</span>
              <h2>Registered Governance Policies</h2>
            </div>
            <span style={{ fontSize: "11px", color: "var(--muted)" }}>
              Changes take immediate effect across document validation workflows.
            </span>
          </div>

          {loading ? (
            <div style={{ padding: "40px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              Loading policy catalog from backend...
            </div>
          ) : policies.length === 0 ? (
            <div style={{ padding: "48px 24px", textAlign: "center" }}>
              <Icon name="shield" size={32} />
              <h3 style={{ margin: "12px 0 4px", font: "18px 'Newsreader', serif" }}>
                No policies configured for this organization
              </h3>
              <p style={{ margin: "0 auto 16px", maxWidth: "400px", fontSize: "12px", color: "var(--muted)" }}>
                Upload an official organizational policy (PDF, DOCX or TXT) to activate layout-aware compliance verification and AI policy assistant retrieval.
              </p>
              <Button variant="primary" icon="stamp" onClick={() => setShowUploadForm(true)}>
                Upload First Policy
              </Button>
            </div>
          ) : (
            <div className="library-table">
              <div
                className="lib-row lib-head"
                style={{ gridTemplateColumns: "2.5fr 1.2fr 1fr 1fr 1.5fr" }}
              >
                <span>POLICY NAME</span>
                <span>DOMAIN</span>
                <span>STATUS</span>
                <span>ACTIVE VER.</span>
                <span style={{ textAlign: "right" }}>ACTIONS</span>
              </div>

              {policies.map((p) => {
                const isExpanded = expandedPolicyId === p.id;
                const versions = policyVersions[p.id] || [];
                const isLoadingVer = loadingVersions[p.id];

                return (
                  <React.Fragment key={p.id}>
                    <div
                      className="lib-row"
                      style={{
                        gridTemplateColumns: "2.5fr 1.2fr 1fr 1fr 1.5fr",
                        cursor: "pointer",
                        background: isExpanded ? "var(--side, #f8f7f4)" : undefined,
                      }}
                      onClick={() => toggleExpand(p.id)}
                    >
                      <span className="doc-name">
                        <span className="doc-icon">
                          <Icon name="shield" />
                        </span>
                        <div>
                          <b>{p.name}</b>
                          {p.description && (
                            <small
                              style={{
                                display: "block",
                                color: "var(--muted)",
                                fontSize: "10px",
                                textOverflow: "ellipsis",
                                overflow: "hidden",
                                whiteSpace: "nowrap",
                                maxWidth: "280px",
                              }}
                            >
                              {p.description}
                            </small>
                          )}
                        </div>
                      </span>

                      <span>
                        {p.domain || "General"}
                        <small style={{ display: "block", color: "var(--muted)", fontSize: "10px" }}>
                          Applies to: {appliesToLabel(p.document_type)}
                        </small>
                      </span>

                      <div>
                        {p.is_active ? (
                          <Badge tone="green">ACTIVE</Badge>
                        ) : (
                          <Badge tone="red">INACTIVE</Badge>
                        )}
                      </div>

                      <code>{p.current_version ? `v${p.current_version.replace(/^v/i, "")}` : "None"}</code>

                      <div
                        style={{ display: "flex", gap: "6px", justifyContent: "flex-end" }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Button
                          variant="secondary"
                          onClick={() => handleToggleActive(p)}
                        >
                          {p.is_active ? "Deactivate" : "Activate"}
                        </Button>
                        <Button
                          variant="secondary"
                          icon="sliders"
                          onClick={() => toggleExpand(p.id)}
                        >
                          {isExpanded ? "Hide Versions" : "Versions"}
                        </Button>
                      </div>
                    </div>

                    {/* Versions Expanded Sub-Table */}
                    {isExpanded && (
                      <div
                        style={{
                          background: "#fff",
                          padding: "16px 24px",
                          borderBottom: "1px solid var(--line2, #e0ddd5)",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            marginBottom: "12px",
                          }}
                        >
                          <span
                            className="eyebrow"
                            style={{ fontSize: "10px", color: "var(--ink)", fontWeight: 600 }}
                          >
                            INDEXED VERSIONS FOR {p.name.toUpperCase()}
                          </span>
                          <span style={{ fontSize: "11px", color: "var(--muted)" }}>
                            Policy ID: <code>{p.id}</code>
                          </span>
                        </div>

                        {isLoadingVer ? (
                          <div style={{ fontSize: "11px", color: "var(--muted)", padding: "10px 0" }}>
                            Fetching version history...
                          </div>
                        ) : versions.length === 0 ? (
                          <div style={{ fontSize: "11px", color: "var(--muted)", padding: "10px 0" }}>
                            No version records found for this policy.
                          </div>
                        ) : (
                          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                            {versions.map((ver) => (
                              <div
                                key={ver.id}
                                style={{
                                  display: "flex",
                                  justifyContent: "space-between",
                                  alignItems: "center",
                                  padding: "10px 14px",
                                  background: "var(--side, #f8f7f4)",
                                  borderRadius: "6px",
                                  border: "1px solid var(--line2, #e0ddd5)",
                                  fontSize: "11px",
                                }}
                              >
                                <div style={{ display: "flex", gap: "16px", alignItems: "center" }}>
                                  <b>v{ver.version}</b>
                                  {getStatusBadge(ver.status)}
                                  <span style={{ color: "var(--muted)" }}>
                                    Chunks: <b>{ver.chunk_count}</b>
                                  </span>
                                  {ver.error_message && (
                                    <span style={{ color: "var(--red, #dc2626)", maxWidth: "280px" }}>
                                      Error: {ver.error_message}
                                    </span>
                                  )}
                                </div>

                                <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                                  <span style={{ color: "var(--muted)", fontSize: "10px" }}>
                                    {ver.created_at ? new Date(ver.created_at).toLocaleDateString() : ""}
                                  </span>
                                  {ver.status === "FAILED" && (
                                    <Button
                                      variant="secondary"
                                      disabled={retryingVersionId === ver.id}
                                      onClick={() => handleRetryIngestion(p.id, ver.id)}
                                    >
                                      {retryingVersionId === ver.id ? "Retrying..." : "Retry Ingestion"}
                                    </Button>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}

export default function PoliciesPage() {
  return (
    <ProtectedRoute allowedRoles={["ORG_ADMIN", "SYSTEM_ADMIN"]}>
      <PoliciesContent />
    </ProtectedRoute>
  );
}
