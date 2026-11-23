"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell, Button, Badge, Icon, IconName } from "../components/AppShell";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { useAuth } from "../context/AuthContext";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

interface ReviewField {
  field: string;
  val: string;
  conf: string;
}

interface QueueItem {
  id: string;
  name: string;
  time: string;
  score: string;
  state: string;
  icon: IconName;
  fields: ReviewField[];
}

function DocumentSourceNotice({ item }: { item?: QueueItem }) {
  if (!item) return null;
  return (
    <div className="receipt-paper" style={{ minHeight: "220px", display: "grid", placeContent: "center", gap: "12px", textAlign: "center" }}>
      <b>{item.name}</b>
      <span>The review queue does not display the source file here.</span>
      <Link href={`/documents/${item.id}`} className="btn secondary" style={{ textDecoration: "none" }}>
        Open document details ↗
      </Link>
    </div>
  );
}

function EmptyQueueView({ onRefresh }: { onRefresh: () => void }) {
  return (
    <div className="empty-wrap">
      <div className="empty-card">
        <div className="empty-head">
          <div>
            <h2>Verification Desk</h2>
            <span>HUMAN VERIFICATION QUEUE · 0 PENDING</span>
          </div>
          <code>● Review queue clear.</code>
        </div>
        <div className="empty-center">
          <div className="paper-stack">
            <span />
            <b>✓</b>
          </div>
          <h1>No documents currently need review.</h1>
          <p>
            Nothing needs your attention in this queue. When new documents are uploaded or routed for review, they will appear here.
          </p>
          <div style={{ display: "flex", gap: "10px" }}>
            <Link href="/documents" className="btn secondary" style={{ textDecoration: "none" }}>
              Intake Dropzone →
            </Link>
            <Button icon="refresh" onClick={onRefresh}>
              Refresh Queue
            </Button>
          </div>
        </div>
        <div className="empty-metrics">
          <div>
            <code>✓ Clean</code>
            <span>Queue status</span>
          </div>
          <div>
            <code>0</code>
            <span>Awaiting review</span>
          </div>
          <div>
            <code>Online</code>
            <span>Workflow engine</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function ReviewContent() {
  const { fetchWithAuth, activeOrgId, user } = useAuth();
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "review" | "low">("all");
  const [search, setSearch] = useState("");
  const [savedNotice, setSavedNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Changes Request Modal State
  const [showChangesModal, setShowChangesModal] = useState(false);
  const [changesComment, setChangesComment] = useState("");
  const [submittingAction, setSubmittingAction] = useState(false);

  // Comment Modal State
  const [showCommentModal, setShowCommentModal] = useState(false);
  const [newComment, setNewComment] = useState("");

  // Authenticated file preview for active document
  const [filePreview, setFilePreview] = useState<{ documentId: string; url: string } | null>(null);
  const [filePreviewFailure, setFilePreviewFailure] = useState<{ documentId: string; message: string } | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);

  const currentOrg = activeOrgId || user?.organization_id || "Enterprise Workspace";

  const loadReviewQueue = useCallback(async () => {
    setLoading(true);
    setActionError(null);
    try {
      const res = await fetchWithAuth(`${API_URL}/api/documents/workflow/review-queue`);
      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(errData?.detail?.message || `HTTP ${res.status}`);
      }

      const data = await res.json();
      const rawItems = data.items || [];

      const mapped: QueueItem[] = rawItems.map((item: {
        id: string;
        filename: string;
        status: string;
        classification?: string;
        uploaded_at: string;
        confidence?: number;
        uploaded_by?: string;
      }) => {
        const confNum = item.confidence != null ? Math.round(item.confidence * 100) : null;
        const classification = (item.classification || "").toLowerCase();

        let icon: IconName = "file";
        if (classification.includes("invoice")) {
          icon = "receipt";
        } else if (classification.includes("receipt") || classification.includes("expense")) {
          icon = "receipt";
        } else if (classification.includes("contract") || classification.includes("legal")) {
          icon = "book";
        } else if (classification.includes("identity") || classification.includes("hr")) {
          icon = "contact";
        }

        return {
          id: item.id,
          name: item.filename,
          time: new Date(item.uploaded_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          score: confNum !== null ? `${confNum}%` : "Pending",
          state: item.status === "NEEDS_REVIEW" ? "Needs Human Review" : item.status,
          icon,
          fields: [
            { field: "Document ID", val: item.id, conf: "—" },
            { field: "File name", val: item.filename, conf: "—" },
            { field: "Classification", val: item.classification || "Unclassified document", conf: confNum !== null ? `${confNum}%` : "—" },
            { field: "Workflow state", val: item.status, conf: "—" },
          ],
        };
      });

      setQueue(mapped);
      setActive(0);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Failed to load review queue from server.");
    } finally {
      setLoading(false);
    }
  }, [fetchWithAuth]);

  useEffect(() => {
    const timer = setTimeout(() => {
      loadReviewQueue();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadReviewQueue]);

  // Fetch full review details for active document
  const activeDoc = queue[active] || null;
  const activeDocId = activeDoc?.id || null;
  const activeDocName = activeDoc?.name || "";

  useEffect(() => {
    if (!activeDocId) return;
    let ignore = false;

    async function fetchDocReviewDetail() {
      try {
        const res = await fetchWithAuth(`${API_URL}/api/documents/${activeDocId}/review`);
        if (res.ok && !ignore) {
          const detail = await res.json();
          if (Array.isArray(detail.extractions) && detail.extractions.length > 0) {
            const dynamicFields: ReviewField[] = detail.extractions.map(
              (e: { field_name: string; value: unknown; confidence?: number }) => ({
                field: e.field_name.replace(/_/g, " "),
                val: String(e.value ?? ""),
                conf: e.confidence == null ? "—" : `${Math.round(e.confidence * 100)}%`,
              })
            );

            setQueue((prev) =>
              prev.map((item) =>
                item.id === activeDocId
                  ? {
                      ...item,
                      fields: [
                        { field: "Document type", val: detail.document?.classification || activeDocName, conf: "—" },
                        ...dynamicFields,
                      ],
                    }
                  : item
              )
            );
          }
        }
      } catch {
        // Fallback to existing fields
      }
    }

    fetchDocReviewDetail();
    return () => {
      ignore = true;
    };
  }, [activeDocId, activeDocName, fetchWithAuth]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setShowChangesModal(false);
        setShowCommentModal(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    if (!activeDocId) return;
    let cancelled = false;
    let objectUrl: string | null = null;

    const timer = setTimeout(() => {
      if (!cancelled) {
        setLoadingPreview(true);
        setFilePreviewFailure(null);
      }
    }, 0);

    fetchWithAuth(`${API_URL}/api/documents/${encodeURIComponent(activeDocId)}/file`)
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => null);
          const message = payload?.error?.message || payload?.detail?.message || payload?.detail;
          throw new Error(typeof message === "string" ? message : `File request failed (${response.status})`);
        }
        return response.blob();
      })
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setFilePreview({ documentId: activeDocId, url: objectUrl });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setFilePreviewFailure({
            documentId: activeDocId,
            message: error instanceof Error ? error.message : "Could not load the source file.",
          });
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingPreview(false);
      });

    return () => {
      cancelled = true;
      clearTimeout(timer);
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [activeDocId, fetchWithAuth]);

  // Submit for Approval
  const handleSubmitForApproval = async () => {
    if (!activeDoc) return;
    setSubmittingAction(true);
    setActionError(null);

    try {
      const res = await fetchWithAuth(`${API_URL}/api/documents/${activeDoc.id}/submit-for-approval`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ auto_route: true, comment: "Reviewed and routed for executive sign-off" }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail?.message || "Failed to submit document for approval.");
      }

      setSavedNotice(`Document ${activeDoc.name} routed to Approval Ledger.`);
      setTimeout(() => {
        loadReviewQueue();
      }, 700);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Submission for approval failed.");
    } finally {
      setSubmittingAction(false);
    }
  };

  // 3. Request Changes
  const handleRequestChanges = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeDoc || !changesComment.trim()) return;
    setSubmittingAction(true);
    setActionError(null);

    try {
      const res = await fetchWithAuth(`${API_URL}/api/documents/${activeDoc.id}/request-changes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment: changesComment.trim() }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail?.message || "Failed to request changes.");
      }

      setSavedNotice(`Changes requested on ${activeDoc.name}. Document returned to submitter.`);
      setShowChangesModal(false);
      setChangesComment("");
      setTimeout(() => {
        loadReviewQueue();
      }, 700);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Failed to request changes.");
    } finally {
      setSubmittingAction(false);
    }
  };

  // 4. Add Review Comment
  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeDoc || !newComment.trim()) return;
    setSubmittingAction(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/api/documents/${activeDoc.id}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment: newComment.trim() }),
      });
      if (res.ok) {
        setSavedNotice("Review comment recorded to audit ledger.");
        setShowCommentModal(false);
        setNewComment("");
      }
    } catch {
      // Ignored
    } finally {
      setSubmittingAction(false);
    }
  };

  const filteredQueue = queue.filter((doc) => {
    if (search && !doc.name.toLowerCase().includes(search.toLowerCase())) return false;
    const state = doc.state.toUpperCase();
    if (filter === "review") return state.includes("REVIEW") || state.includes("AMBIGUOUS") || state.includes("NEEDS");
    if (filter === "low") return parseFloat(doc.score) < 75;
    return true;
  });

  if (loading && queue.length === 0) {
    return (
      <AppShell>
        <div style={{ padding: "60px", textAlign: "center", color: "var(--muted)" }}>
          <p style={{ font: "20px 'Newsreader', serif", margin: "0 0 8px" }}>Loading Verification Queue...</p>
          <small>Synchronizing permitted workflow records for {currentOrg}</small>
        </div>
      </AppShell>
    );
  }

  if (queue.length === 0) {
    return (
      <AppShell>
        <EmptyQueueView onRefresh={loadReviewQueue} />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <header className="review-head">
        <div className="crumb">
          <Icon name="stamp" size={14} /> Workspace <span>/</span> Verification Desk
          <div className="sync">
            <span className="brand-dot" /> Live Queue ({queue.length})
          </div>
        </div>
        <div className="head-main">
          <div>
            <h1>A human eye. A trusted record.</h1>
            <p className="subline">
              {currentOrg.toUpperCase()} · HUMAN VERIFICATION QUEUE · {queue.length} DOCUMENTS TO REVIEW
            </p>
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <Button icon="refresh" variant="secondary" onClick={loadReviewQueue}>
              Sync Queue
            </Button>
            <Link href="/approvals" className="btn primary" style={{ textDecoration: "none" }}>
              Approval Ledger →
            </Link>
          </div>
        </div>
      </header>

      {actionError && (
        <div
          style={{
            margin: "0 32px 16px",
            padding: "10px 16px",
            background: "var(--red-bg, #fef2f2)",
            border: "1px solid var(--red, #dc2626)",
            color: "var(--red, #dc2626)",
            borderRadius: "6px",
            fontSize: "12px",
          }}
        >
          <b>Review Action Notice:</b> {actionError}
        </div>
      )}

      {savedNotice && (
        <div
          style={{
            margin: "0 32px 16px",
            padding: "10px 16px",
            background: "var(--green-bg, #f0fdf4)",
            border: "1px solid var(--green, #16a34a)",
            color: "var(--green, #16a34a)",
            borderRadius: "6px",
            fontSize: "12px",
          }}
        >
          <b>Workflow Action Success:</b> {savedNotice}
        </div>
      )}

      <div className="review-body">
        {/* Left Queue Rail */}
        <aside className="queue-rail">
          <div className="queue-filters">
            <label className="search" htmlFor="review-search-input">
              <Icon name="search" size={13} />
              <input
                id="review-search-input"
                placeholder="Find a document…"
                aria-label="Find a document"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <kbd>⌘ K</kbd>
            </label>
            <div>
              <b
                style={{
                  cursor: "pointer",
                  background: filter === "all" ? "var(--violet-bg)" : undefined,
                  color: filter === "all" ? "var(--violet)" : undefined,
                }}
                onClick={() => setFilter("all")}
              >
                All ({queue.length})
              </b>
              <span
                style={{ cursor: "pointer", fontWeight: filter === "review" ? 600 : undefined }}
                onClick={() => setFilter("review")}
              >
                Needs Review ({queue.filter((q) => /REVIEW|AMBIGUOUS|NEEDS/i.test(q.state)).length})
              </span>
              <span
                style={{ cursor: "pointer", fontWeight: filter === "low" ? 600 : undefined }}
                onClick={() => setFilter("low")}
              >
                Low Conf. ({queue.filter((q) => parseFloat(q.score) < 75).length})
              </span>
            </div>
          </div>

          <div className="queue-items">
            {filteredQueue.map((doc) => {
              const originalIndex = queue.findIndex((q) => q.id === doc.id);
              const isSelected = originalIndex === active;
              return (
                <div
                  key={doc.id}
                  className={`queue-item ${isSelected ? "active" : ""}`}
                  onClick={() => setActive(originalIndex)}
                  style={{ cursor: "pointer" }}
                >
                  <div className="q-left">
                    <Icon name={doc.icon} />
                  </div>
                  <div className="q-mid">
                    <b>{doc.name}</b>
                    <span>
                      {doc.time} · ID: {doc.id.slice(0, 8)}…
                    </span>
                  </div>
                  <div className="q-right">
                    <span className={parseFloat(doc.score) < 75 ? "amber-score" : ""}>
                      {doc.score}
                    </span>
                    <small>{doc.state}</small>
                  </div>
                </div>
              );
            })}
          </div>
        </aside>

        {/* Center Workspace */}
        {activeDoc && (
          <section className="review-center">
            {/* Stage Bar */}
            <div className="stage-bar">
              <div>
                <h2>
                  Review: <em>{activeDoc.name}</em>
                </h2>
                <span>
                  DOCUMENT ID: <code>{activeDoc.id}</code> · AI RECOGNITION CONFIDENCE: {activeDoc.score}
                </span>
              </div>
              <div style={{ display: "flex", gap: "8px" }}>
                <Link
                  href={`/documents/${activeDoc.id}`}
                  className="btn secondary"
                  style={{ textDecoration: "none" }}
                >
                  Document View ↗
                </Link>
                <Button variant="secondary" onClick={() => setShowCommentModal(true)}>
                  Add Comment +
                </Button>
              </div>
            </div>

            <div className="correction-work">
              {/* Source document preview */}
              <div className="receipt-side" style={{ display: "flex", flexDirection: "column" }}>
                <div className="pane-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                  <span>ORIGINAL DOCUMENT PREVIEW</span>
                  <Link
                    href={`/documents/${activeDoc.id}`}
                    style={{ fontSize: "11px", color: "var(--brand)", textDecoration: "none", fontWeight: 500 }}
                  >
                    Open document details ↗
                  </Link>
                </div>
                <div
                  className="receipt-viewer"
                  style={{
                    flex: 1,
                    minHeight: "480px",
                    border: "1px solid var(--line2, #e0ddd5)",
                    borderRadius: "6px",
                    background: "#fbfbf9",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    overflow: "hidden",
                  }}
                >
                  {loadingPreview ? (
                    <div style={{ color: "var(--muted)", fontSize: "12px", textAlign: "center", padding: "20px" }}>
                      Loading source document preview...
                    </div>
                  ) : (filePreviewFailure?.documentId === activeDocId) ? (
                    <div style={{ color: "var(--muted)", fontSize: "12px", textAlign: "center", padding: "20px" }}>
                      <p style={{ margin: "0 0 8px" }}>Preview unavailable: {filePreviewFailure.message}</p>
                      <Link href={`/documents/${activeDoc.id}`} className="btn secondary" style={{ textDecoration: "none" }}>
                        View in Document Inspector ↗
                      </Link>
                    </div>
                  ) : (filePreview?.documentId === activeDocId && filePreview.url) ? (
                    activeDoc.name.match(/\.(png|jpg|jpeg|webp)$/i) ? (
                      /* eslint-disable-next-line @next/next/no-img-element */
                      <img
                        src={filePreview.url}
                        alt={activeDoc.name}
                        style={{
                          maxWidth: "100%",
                          maxHeight: "650px",
                          objectFit: "contain",
                          borderRadius: "4px",
                        }}
                      />
                    ) : (
                      <iframe
                        src={`${filePreview.url}#toolbar=0`}
                        title={activeDoc.name}
                        style={{
                          width: "100%",
                          height: "100%",
                          minHeight: "540px",
                          border: "none",
                          backgroundColor: "#fff",
                        }}
                      />
                    )
                  ) : (
                    <DocumentSourceNotice item={activeDoc} />
                  )}
                </div>
                <p style={{ fontSize: "11px", color: "var(--muted)", marginTop: "8px" }}>
                  Inspect the source document side-by-side with extracted fields before approval.
                </p>
              </div>

              {/* Extracted fields */}
              <div className="correction-side">
                <div className="pane-title">
                  <span>EXTRACTED FIELDS</span>
                  <Badge tone="amber">{activeDoc.fields.length} fields</Badge>
                </div>

                <div className="edit-table">
                  <div className="edit-head">
                    <b>FIELD / REVIEWED VALUE</b>
                    <b>AI CONF.</b>
                  </div>
                  {activeDoc.fields.map((f) => (
                    <div className="edit-row" key={f.field}>
                      <div>
                        <span>{f.field}</span>
                        <span>{f.val || "Not extracted"}</span>
                      </div>
                      <code className={parseInt(f.conf) < 75 ? "amber-text" : "green-text"}>
                        {f.conf}
                      </code>
                    </div>
                  ))}
                </div>

                <p className="history">
                  <Icon name="history" size={12} /> Use the workflow actions below to record comments, change requests, or approval routing.
                </p>
              </div>
            </div>

            {/* Review Actions Bar */}
            <div className="review-actions">
              <div style={{ display: "flex", gap: "8px" }}>
                <Button
                  variant="ghost"
                  onClick={() => setShowChangesModal(true)}
                  disabled={submittingAction}
                >
                  Request Changes ↺
                </Button>
                <Button
                  variant="secondary"
                  onClick={handleSubmitForApproval}
                  disabled={submittingAction}
                >
                  Submit for Approval ↥
                </Button>
                <Button onClick={() => setActive((prev) => (prev + 1) % queue.length)}>
                  Skip for now
                </Button>
              </div>
            </div>
          </section>
        )}
      </div>

      {/* Request Changes Modal */}
      {showChangesModal && activeDoc && (
        <div className="sheet-backdrop" onMouseDown={() => setShowChangesModal(false)} role="dialog" aria-modal="true" aria-label="Request Submitter Changes">
          <aside className="override-sheet" onMouseDown={(e) => e.stopPropagation()}>
            <div className="sheet-bar">
              <span>
                <Icon name="alert" /> REQUEST SUBMITTER CHANGES
              </span>
              <button type="button" onClick={() => setShowChangesModal(false)}>
                ×
              </button>
            </div>
            <form onSubmit={handleRequestChanges} className="sheet-form">
              <div>
                <h2>Request Corrections from Submitter</h2>
                <p>
                  Document <code>{activeDoc.name}</code> will be routed back to the submitter with your revision guidance.
                </p>
              </div>
              <div>
                <label style={{ display: "block", fontSize: "11px", fontWeight: 600, marginBottom: "6px" }}>
                  Revision Guidance / Reason *
                </label>
                <textarea
                  required
                  rows={4}
                  placeholder="Specify what needs correction (e.g. Total tax amount discrepancy; missing itemized receipt page 2)..."
                  value={changesComment}
                  onChange={(e) => setChangesComment(e.target.value)}
                  style={{
                    width: "100%",
                    border: "1px solid var(--line2, #e0ddd5)",
                    borderRadius: "5px",
                    padding: "8px 12px",
                    fontSize: "12px",
                    background: "white",
                  }}
                />
              </div>
              <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end", marginTop: "12px" }}>
                <Button variant="secondary" onClick={() => setShowChangesModal(false)}>
                  Cancel
                </Button>
                <Button type="submit" variant="primary" icon="alert" disabled={submittingAction}>
                  {submittingAction ? "Routing..." : "Send Revision Request →"}
                </Button>
              </div>
            </form>
          </aside>
        </div>
      )}

      {/* Add Comment Modal */}
      {showCommentModal && activeDoc && (
        <div className="sheet-backdrop" onMouseDown={() => setShowCommentModal(false)} role="dialog" aria-modal="true" aria-label="Add Audit Comment">
          <aside className="override-sheet" onMouseDown={(e) => e.stopPropagation()}>
            <div className="sheet-bar">
              <span>
                <Icon name="pencil" /> ADD AUDIT COMMENT
              </span>
              <button type="button" onClick={() => setShowCommentModal(false)}>
                ×
              </button>
            </div>
            <form onSubmit={handleAddComment} className="sheet-form">
              <div>
                <h2>Affix Reviewer Note</h2>
                <p>Record notes or observations on this document without altering its current workflow stage.</p>
              </div>
              <div>
                <label style={{ display: "block", fontSize: "11px", fontWeight: 600, marginBottom: "6px" }}>
                  Comment Text *
                </label>
                <textarea
                  required
                  rows={4}
                  placeholder="Reviewer observation..."
                  value={newComment}
                  onChange={(e) => setNewComment(e.target.value)}
                  style={{
                    width: "100%",
                    border: "1px solid var(--line2, #e0ddd5)",
                    borderRadius: "5px",
                    padding: "8px 12px",
                    fontSize: "12px",
                    background: "white",
                  }}
                />
              </div>
              <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end", marginTop: "12px" }}>
                <Button variant="secondary" onClick={() => setShowCommentModal(false)}>
                  Cancel
                </Button>
                <Button type="submit" variant="primary" icon="check" disabled={submittingAction}>
                  {submittingAction ? "Saving..." : "Record Comment"}
                </Button>
              </div>
            </form>
          </aside>
        </div>
      )}
    </AppShell>
  );
}

export default function ReviewPage() {
  return (
    <ProtectedRoute
      allowedRoles={[
        "REVIEWER",
        "APPROVER",
        "ORG_ADMIN",
        "SYSTEM_ADMIN",
        "COMPLIANCE",
        "AUDITOR",
      ]}
    >
      <ReviewContent />
    </ProtectedRoute>
  );
}
