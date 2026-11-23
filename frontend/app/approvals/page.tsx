"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { AppShell, Button, Badge, Icon } from "../components/AppShell";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { useAuth } from "../context/AuthContext";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

interface ApprovalQueueItem {
  id: string;
  organization_id: string;
  uploaded_by: string;
  filename: string;
  file_type?: string;
  file_size?: number;
  status: string;
  classification?: string;
  confidence?: number;
  uploaded_at: string;
  assigned_reviewer_id?: string | null;
  assigned_approver_id?: string | null;
}

function ApprovalsContent() {
  const { fetchWithAuth, user, activeOrgId } = useAuth();
  const [items, setItems] = useState<ApprovalQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successNotice, setSuccessNotice] = useState<string | null>(null);

  // Decision Modal State
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [decisionType, setDecisionType] = useState<"approve" | "reject" | null>(null);
  const [reasonInput, setReasonInput] = useState("");
  const [commentInput, setCommentInput] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const currentOrg = activeOrgId || user?.organization_id || "Enterprise Workspace";

  const loadApprovalQueue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth(`${API_URL}/api/documents/workflow/approval-queue`);
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail?.message || data?.error?.message || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setItems(data.items || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load approval queue.");
    } finally {
      setLoading(false);
    }
  }, [fetchWithAuth]);

  useEffect(() => {
    const timer = setTimeout(() => {
      loadApprovalQueue();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadApprovalQueue]);

  const closeDecisionModal = useCallback(() => {
    setSelectedDocId(null);
    setDecisionType(null);
    setReasonInput("");
    setCommentInput("");
  }, []);

  const openDecisionModal = (docId: string, type: "approve" | "reject") => {
    setSelectedDocId(docId);
    setDecisionType(type);
    setReasonInput(type === "approve" ? "Approved in accordance with enterprise policy limits" : "");
    setCommentInput("");
  };

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        closeDecisionModal();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [closeDecisionModal]);

  const submitDecision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDocId || !decisionType) return;
    if (decisionType === "reject" && !reasonInput.trim()) {
      setError("A rejection reason is strictly required by the audit governance protocol.");
      return;
    }

    setSubmitting(true);
    setError(null);
    setSuccessNotice(null);

    const endpoint =
      decisionType === "approve"
        ? `${API_URL}/api/documents/${selectedDocId}/approve`
        : `${API_URL}/api/documents/${selectedDocId}/reject`;

    try {
      const res = await fetchWithAuth(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reason: reasonInput.trim() || undefined,
          comment: commentInput.trim() || undefined,
        }),
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        const msg =
          data?.detail?.message ||
          data?.error?.message ||
          `Decision failed with status ${res.status}`;
        throw new Error(msg);
      }

      setSuccessNotice(
        `Document ${selectedDocId} has been successfully ${
          decisionType === "approve" ? "approved" : "rejected"
        }. Permanent audit transition recorded.`
      );
      closeDecisionModal();
      await loadApprovalQueue();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to record approval decision.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AppShell>
      <header className="page-head">
        <div className="crumb">
          <Icon name="check" size={14} /> Workspace <span>/</span> Approval Ledger
          <div className="sync">
            <span className="brand-dot" /> Verified Authority
          </div>
        </div>
        <div className="head-main">
          <div>
            <h1>Managerial Approval Ledger</h1>
            <p className="subline">
              {currentOrg.toUpperCase()} · AUTHORIZED GOVERNANCE · {items.length} FILES AWAITING DECISION
            </p>
          </div>
          <Button variant="secondary" icon="refresh" onClick={loadApprovalQueue}>
            Refresh Ledger
          </Button>
        </div>
      </header>

      <div className="intake-body">
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
            <b>Authorization Notice:</b> {error}
          </div>
        )}

        {successNotice && (
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
            <b>Decision Recorded:</b> {successNotice}
          </div>
        )}

        <div className="library-card" style={{ marginTop: 0 }}>
          <div className="library-toolbar">
            <div>
              <span className="eyebrow">PENDING SIGN-OFF</span>
              <h2>Files Requiring Managerial Action</h2>
            </div>
            <span style={{ fontSize: "11px", color: "var(--muted)" }}>
              Approval and rejection actions are associated with the authenticated user in the audit history.
            </span>
          </div>

          {loading ? (
            <div style={{ padding: "40px", textAlign: "center", color: "var(--muted)", fontSize: "12px" }}>
              Loading approval ledger from backend...
            </div>
          ) : items.length === 0 ? (
            <div style={{ padding: "48px 24px", textAlign: "center" }}>
              <Icon name="check" size={32} />
              <h3 style={{ margin: "12px 0 4px", font: "18px 'Newsreader', serif" }}>
                Approval ledger is clear
              </h3>
              <p style={{ margin: "0 auto 16px", maxWidth: "420px", fontSize: "12px", color: "var(--muted)" }}>
                There are currently no documents pending final sign-off in organization <code>{currentOrg}</code>.
              </p>
              <div style={{ display: "flex", gap: "8px", justifyContent: "center" }}>
                <Link href="/review" className="btn primary" style={{ textDecoration: "none" }}>
                  Verification Queue →
                </Link>
                <Link href="/documents" className="btn secondary" style={{ textDecoration: "none" }}>
                  Intake Dropzone →
                </Link>
              </div>
            </div>
          ) : (
            <div className="library-table">
              <div className="lib-row lib-head" style={{ gridTemplateColumns: "2fr 1fr 1fr 1.5fr 1.5fr" }}>
                <span>FILE NAME</span>
                <span>CLASSIFICATION</span>
                <span>SUBMITTER</span>
                <span>STATUS / EVIDENCE</span>
                <span style={{ textAlign: "right" }}>DECISION</span>
              </div>

              {items.map((item) => {
                const confPercent = item.confidence ? `${Math.round(item.confidence * 100)}%` : "Verified";
                return (
                  <div
                    key={item.id}
                    className="lib-row"
                    style={{ gridTemplateColumns: "2fr 1fr 1fr 1.5fr 1.5fr", cursor: "default" }}
                  >
                    <span className="doc-name">
                      <span className="doc-icon">
                        <Icon name="file" />
                      </span>
                      <div>
                        <Link
                          href={`/documents/${item.id}`}
                          style={{ color: "var(--ink)", textDecoration: "none", fontWeight: 500 }}
                        >
                          {item.filename}
                        </Link>
                        <small style={{ display: "block", color: "var(--muted)", fontSize: "10px" }}>
                          ID: <code>{item.id}</code> · {new Date(item.uploaded_at).toLocaleDateString()}
                        </small>
                      </div>
                    </span>

                    <span>{item.classification || "General Document"}</span>
                    <code>{item.uploaded_by}</code>

                    <div>
                      <Badge tone="violet">{item.status}</Badge>
                      <small style={{ display: "block", color: "var(--muted)", fontSize: "9px", marginTop: "3px" }}>
                        AI Confidence: {confPercent}
                      </small>
                    </div>

                    <div style={{ display: "flex", gap: "6px", justifyContent: "flex-end" }}>
                      <Button
                        variant="primary"
                        icon="check"
                        onClick={() => openDecisionModal(item.id, "approve")}
                      >
                        Approve
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => openDecisionModal(item.id, "reject")}
                      >
                        Reject
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Decision Modal / Sheet */}
        {selectedDocId && decisionType && (
          <div
            className="sheet-backdrop"
            onMouseDown={closeDecisionModal}
            role="dialog"
            aria-modal="true"
            aria-label={decisionType === "approve" ? "Approve Document Modal" : "Reject Document Modal"}
          >
            <aside
              className="override-sheet"
              onMouseDown={(e) => e.stopPropagation()}
              style={{ maxWidth: "480px" }}
            >
              <div className="sheet-bar">
                <span>
                  <Icon name={decisionType === "approve" ? "check" : "alert"} />
                  {decisionType === "approve" ? "APPROVE DOCUMENT" : "REJECT DOCUMENT"}
                </span>
                <button type="button" onClick={closeDecisionModal} aria-label="Close dialog">
                  ×
                </button>
              </div>

              <form onSubmit={submitDecision} className="sheet-form">
                <div>
                  <h2 style={{ font: "20px 'Newsreader', serif", margin: "0 0 6px" }}>
                    {decisionType === "approve"
                      ? "Affix Executive Approval Stamp"
                      : "Record Formal Document Rejection"}
                  </h2>
                  <p style={{ margin: 0, fontSize: "12px", color: "var(--muted)", lineHeight: 1.5 }}>
                    Target document: <code>{selectedDocId}</code>. This action changes the document state and records an audit event.
                  </p>
                </div>

                <div>
                  <label htmlFor="decision-reason" style={{ display: "block", fontSize: "11px", fontWeight: 600, marginBottom: "6px" }}>
                    Reason for {decisionType === "approve" ? "Approval" : "Rejection"} *
                  </label>
                  <input
                    id="decision-reason"
                    type="text"
                    required
                    placeholder={
                      decisionType === "approve"
                        ? "e.g. Cleared under AP-Rule-04 procurement ceiling"
                        : "e.g. Lodging reimbursement ceiling exceeded by $86.50"
                    }
                    value={reasonInput}
                    onChange={(e) => setReasonInput(e.target.value)}
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
                  <label htmlFor="decision-comment" style={{ display: "block", fontSize: "11px", fontWeight: 600, marginBottom: "6px" }}>
                    Internal Governance Comment (Optional)
                  </label>
                  <textarea
                    id="decision-comment"
                    rows={3}
                    placeholder="Provide details or instructions for submitter / compliance..."
                    value={commentInput}
                    onChange={(e) => setCommentInput(e.target.value)}
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

                <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end", marginTop: "12px" }}>
                  <Button variant="secondary" onClick={closeDecisionModal}>
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant={decisionType === "approve" ? "primary" : "secondary"}
                    icon="check"
                    disabled={submitting}
                  >
                    {submitting
                      ? "Recording Decision..."
                      : decisionType === "approve"
                      ? "Sign & Approve Document →"
                      : "Confirm Rejection ✗"}
                  </Button>
                </div>
              </form>
            </aside>
          </div>
        )}
      </div>
    </AppShell>
  );
}

export default function ApprovalsPage() {
  return (
    <ProtectedRoute allowedRoles={["APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN"]}>
      <ApprovalsContent />
    </ProtectedRoute>
  );
}
