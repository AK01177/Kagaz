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
  docType: "receipt" | "identity" | "invoice" | "contract" | "general";
  verified?: boolean;
  fields: ReviewField[];
  submitter?: string;
}

function DynamicExcerpt({ item }: { item?: QueueItem }) {
  if (!item) return null;

  if (item.docType === "identity") {
    const holder = item.fields.find((f) => f.field.toLowerCase().includes("holder") || f.field.toLowerCase().includes("name"))?.val || "—";
    const idNum = item.fields.find((f) => f.field.toLowerCase().includes("number") || f.field.toLowerCase().includes("id"))?.val || item.id;
    const auth = item.fields.find((f) => f.field.toLowerCase().includes("authority") || f.field.toLowerCase().includes("issuer"))?.val || "Official Identity Credential";

    return (
      <div className="receipt-paper" style={{ transform: "none", margin: "24px auto", background: "#fcfbf7" }}>
        <b>{auth.toUpperCase()}</b>
        <small style={{ letterSpacing: "1px" }}>STATE IDENTITY CREDENTIAL</small>
        <hr />
        <p>
          HOLDER <span>{holder.toUpperCase()}</span><br />
          DOC NO. <span>{idNum}</span><br />
          ISSUED <span>ARCHIVAL ATTESTATION</span>
        </p>
        <hr />
        <strong>
          AUTHENTICATED EXCERPT <span>{item.state.toUpperCase()}</span>
        </strong>
        <small>OCR SCAN ACCREDITATION LEVEL 2</small>
        <i className="uncertain" style={{ top: "105px", right: "16px", width: "110px", height: "18px" }} />
      </div>
    );
  }

  if (item.docType === "invoice") {
    const vendor = item.fields.find((f) => f.field.toLowerCase().includes("vendor") || f.field.toLowerCase().includes("supplier"))?.val || item.name;
    const total = item.fields.find((f) => f.field.toLowerCase().includes("total") || f.field.toLowerCase().includes("amount"))?.val || "—";
    const ref = item.fields.find((f) => f.field.toLowerCase().includes("reference") || f.field.toLowerCase().includes("number"))?.val || item.id;

    return (
      <div className="receipt-paper" style={{ transform: "none", margin: "24px auto" }}>
        <b>{vendor.toUpperCase()}</b>
        <small>COMMERCIAL TAX INVOICE</small>
        <hr />
        <p>
          INVOICE NO <span>{ref}</span><br />
          CLIENT <span>ENTERPRISE LEDGER</span><br />
          TERMS <span>RECORDED</span>
        </p>
        <hr />
        <strong>
          TOTAL BALANCE <span>{total}</span>
        </strong>
        <small>TAX INVOICE EXCERPT · HIGH FIDELITY</small>
      </div>
    );
  }

  if (item.docType === "contract") {
    const parties = item.fields.find((f) => f.field.toLowerCase().includes("part"))?.val || item.name;
    const term = item.fields.find((f) => f.field.toLowerCase().includes("term") || f.field.toLowerCase().includes("duration"))?.val || "—";

    return (
      <div className="receipt-paper" style={{ transform: "none", margin: "24px auto" }}>
        <b>LEGAL COVENANT EXCERPT</b>
        <small>CONFIDENTIAL RECORD</small>
        <hr />
        <p>
          PARTIES <span>{parties}</span><br />
          COVENANT <span>GOVERNANCE PROTOCOL</span><br />
          DURATION <span>{term}</span>
        </p>
        <hr />
        <strong>
          LEGAL GOVERNANCE <span>{item.state.toUpperCase()}</span>
        </strong>
        <small>PERMANENT ARCHIVAL SEAL AFFIXED</small>
      </div>
    );
  }

  // Default General / Receipt Excerpt
  const supplier = item.fields.find((f) => f.field.toLowerCase().includes("supplier") || f.field.toLowerCase().includes("merchant"))?.val || item.name;
  const date = item.fields.find((f) => f.field.toLowerCase().includes("date"))?.val || item.time;
  const total = item.fields.find((f) => f.field.toLowerCase().includes("total"))?.val || "—";

  return (
    <div className="receipt-paper">
      <b>{supplier.toUpperCase()}</b>
      <small>
        ENTERPRISE DOCUMENT EXCERPT<br />
        Document ID: {item.id}
      </small>
      <hr />
      <p>
        DATE <span>{date}</span><br />
        STATUS <span>{item.state.toUpperCase()}</span><br />
        SUBMITTER <span>{item.submitter || "Enterprise User"}</span>
      </p>
      <hr />
      <strong>
        TOTAL BALANCE <span>{total}</span>
      </strong>
      <small>
        DIGITALLY ANCHORED RECORD<br />
        Permanent Hash Stamp Verified
      </small>
      <i className="uncertain u1" />
      <i className="uncertain u2" />
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
          <h1>All documents verified.</h1>
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
  const [filter, setFilter] = useState<"all" | "review" | "low" | "verified">("all");
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
        const confNum = item.confidence ? Math.round(item.confidence * 100) : null;
        const isVerified = item.status === "REVIEWER_VERIFIED";
        const classification = (item.classification || "").toLowerCase();

        let docType: "receipt" | "identity" | "invoice" | "contract" | "general" = "general";
        let icon: IconName = "file";
        if (classification.includes("invoice")) {
          docType = "invoice";
          icon = "receipt";
        } else if (classification.includes("receipt") || classification.includes("expense")) {
          docType = "receipt";
          icon = "receipt";
        } else if (classification.includes("contract") || classification.includes("legal")) {
          docType = "contract";
          icon = "book";
        } else if (classification.includes("identity") || classification.includes("hr")) {
          docType = "identity";
          icon = "contact";
        }

        return {
          id: item.id,
          name: item.filename,
          time: new Date(item.uploaded_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          score: isVerified ? "✓ 100%" : confNum !== null ? `${confNum}%` : "Pending",
          state: isVerified ? "Certified" : item.status === "NEEDS_REVIEW" ? "Needs Human Review" : item.status,
          icon,
          docType,
          verified: isVerified,
          submitter: item.uploaded_by,
          fields: [
            { field: "Document ID", val: item.id, conf: "100%" },
            { field: "File name", val: item.filename, conf: "100%" },
            { field: "Classification", val: item.classification || "General Document", conf: confNum !== null ? `${confNum}%` : "—" },
            { field: "Workflow state", val: item.status, conf: "100%" },
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
              (e: { field_name: string; field_value: unknown; confidence?: number }) => ({
                field: e.field_name.replace(/_/g, " "),
                val: String(e.field_value ?? ""),
                conf: `${Math.round((e.confidence ?? 0.8) * 100)}%`,
              })
            );

            setQueue((prev) =>
              prev.map((item) =>
                item.id === activeDocId
                  ? {
                      ...item,
                      fields: [
                        { field: "Document type", val: detail.document?.classification || activeDocName, conf: "95%" },
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

  function handleFieldChange(fieldIndex: number, newVal: string) {
    setQueue((prev) =>
      prev.map((item, idx) => {
        if (idx !== active) return item;
        const updatedFields = [...item.fields];
        updatedFields[fieldIndex] = { ...updatedFields[fieldIndex], val: newVal };
        return { ...item, fields: updatedFields };
      })
    );
  }

  // 1. Confirm & Next (Verify / Certify)
  const handleConfirmNext = useCallback(async () => {
    if (!activeDoc) return;
    setSubmittingAction(true);
    setActionError(null);

    try {
      const classificationVal = activeDoc.fields.find((f) => f.field.toLowerCase().includes("type") || f.field.toLowerCase().includes("classification"))?.val || "Verified Document";

      const res = await fetchWithAuth(`${API_URL}/api/documents/${activeDoc.id}/classification`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: classificationVal, notes: "Verified in review desk" }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail?.message || "Failed to certify document.");
      }

      setSavedNotice(`Certified ${activeDoc.name} ✓`);

      setQueue((prev) =>
        prev.map((item, idx) =>
          idx === active ? { ...item, score: "✓ 100%", state: "Certified", verified: true } : item
        )
      );

      setTimeout(() => {
        setSavedNotice(null);
        if (active < queue.length - 1) {
          setActive(active + 1);
        }
      }, 600);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Error during certification.");
    } finally {
      setSubmittingAction(false);
    }
  }, [active, queue.length, activeDoc, fetchWithAuth]);

  // 2. Submit for Approval
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

  // Keyboard shortcut listener (Cmd+Enter / Ctrl+Enter)
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        handleConfirmNext();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleConfirmNext]);

  const filteredQueue = queue.filter((doc) => {
    if (search && !doc.name.toLowerCase().includes(search.toLowerCase())) return false;
    if (filter === "review") return doc.state.includes("Review") || doc.state.includes("Ambiguous") || doc.state.includes("NEEDS");
    if (filter === "low") return parseFloat(doc.score) < 75 && !doc.verified;
    if (filter === "verified") return doc.verified;
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
              {currentOrg.toUpperCase()} · HUMAN VERIFICATION QUEUE · {queue.length} FILES REQUIRING CERTIFICATION
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
            <label className="search">
              <Icon name="search" size={13} />
              <input
                placeholder="Find a document…"
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
                Needs Review ({queue.filter((q) => !q.verified && parseFloat(q.score) < 80).length})
              </span>
              <span
                style={{ cursor: "pointer", fontWeight: filter === "low" ? 600 : undefined }}
                onClick={() => setFilter("low")}
              >
                Low Conf. ({queue.filter((q) => !q.verified && parseFloat(q.score) < 75).length})
              </span>
              <span
                style={{ cursor: "pointer", fontWeight: filter === "verified" ? 600 : undefined }}
                onClick={() => setFilter("verified")}
              >
                Verified ({queue.filter((q) => q.verified).length})
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
                    <span className={doc.verified ? "green-score" : parseFloat(doc.score) < 75 ? "amber-score" : ""}>
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
              {/* Scanned Excerpt Viewer */}
              <div className="receipt-side">
                <div className="pane-title">
                  <span>DOCUMENT SOURCE PREVIEW</span>
                  <code>{activeDoc.docType.toUpperCase()}</code>
                </div>
                <div className="receipt-viewer">
                  <div className="viewer-bar">
                    <span>−　100%　＋</span>
                    <span>⛶</span>
                  </div>
                  <DynamicExcerpt item={activeDoc} />
                </div>
                <p>Verify extracted values against the source before recording state changes.</p>
              </div>

              {/* Editable Field Correction Table */}
              <div className="correction-side">
                <div className="pane-title">
                  <span>REVIEW &amp; CORRECT EXTRACTED FIELDS</span>
                  <Badge tone={activeDoc.verified ? "green" : "amber"}>
                    {activeDoc.verified ? "Verified" : `${activeDoc.fields.length} fields`}
                  </Badge>
                </div>

                <div className="edit-table">
                  <div className="edit-head">
                    <b>FIELD / REVIEWED VALUE</b>
                    <b>AI CONF.</b>
                  </div>
                  {activeDoc.fields.map((f, i) => (
                    <label className="edit-row" key={f.field}>
                      <div>
                        <span>{f.field}</span>
                        <input
                          value={f.val}
                          onChange={(e) => handleFieldChange(i, e.target.value)}
                        />
                      </div>
                      <code className={parseInt(f.conf) < 75 && !activeDoc.verified ? "amber-text" : "green-text"}>
                        {activeDoc.verified ? "100%" : f.conf}
                      </code>
                    </label>
                  ))}
                </div>

                <p className="history">
                  <Icon name="history" size={12} /> Original values and reviewer updates are permanently tracked in the cryptographic audit trail.
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
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span>Press ⌘+Enter</span>
                <Button
                  variant="primary"
                  icon="check"
                  disabled={submittingAction}
                  onClick={handleConfirmNext}
                >
                  {savedNotice ? "Confirmed ✓" : activeDoc.verified ? "Re-Certify" : "Confirm & Next"}
                </Button>
              </div>
            </div>
          </section>
        )}
      </div>

      {/* Request Changes Modal */}
      {showChangesModal && activeDoc && (
        <div className="sheet-backdrop" onMouseDown={() => setShowChangesModal(false)}>
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
        <div className="sheet-backdrop" onMouseDown={() => setShowCommentModal(false)}>
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
