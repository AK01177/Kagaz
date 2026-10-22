"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import {
  DocumentRecord,
  VALID_DOCUMENT_TYPES,
  getCategoryInfo,
  formatFileSize,
  formatDate,
} from "@/app/classification";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const DEFAULT_REVIEW_QUEUE: DocumentRecord[] = [
  {
    document_id: "doc_demo_8823f9",
    filename: "commercial_invoice_september.pdf",
    file_type: "application/pdf",
    file_size: 2457812,
    status: "CLASSIFIED",
    uploaded_at: "2026-09-29T17:15:00Z",
    category: "invoice",
    confidence: 0.948,
    organization_id: "org_kagaz_primary",
    submitter_id: "usr_doc_analyst",
  },
  {
    document_id: "doc_demo_unverified_42a",
    filename: "vendor_services_agreement_draft.pdf",
    file_type: "application/pdf",
    file_size: 1420500,
    status: "PROCESSING",
    uploaded_at: "2026-10-02T11:30:00Z",
    category: "contract",
    confidence: 0.582,
    organization_id: "org_kagaz_primary",
    submitter_id: "usr_legal_clerk",
  },
  {
    document_id: "doc_demo_transcript_99c",
    filename: "official_transcript_fall_2025.pdf",
    file_type: "application/pdf",
    file_size: 980120,
    status: "CLASSIFIED",
    uploaded_at: "2026-10-05T09:20:00Z",
    category: "academic_record",
    confidence: 0.641,
    organization_id: "org_kagaz_primary",
    submitter_id: "usr_applicant",
  },
];

function getInitialQueue(): DocumentRecord[] {
  if (typeof window === "undefined") return DEFAULT_REVIEW_QUEUE;
  const extraDocs: DocumentRecord[] = [];
  try {
    for (let i = 0; i < window.sessionStorage.length; i++) {
      const key = window.sessionStorage.key(i);
      if (key && key.startsWith("kagaz_doc_")) {
        const itemStr = window.sessionStorage.getItem(key);
        if (itemStr) {
          const parsed = JSON.parse(itemStr) as DocumentRecord;
          if (parsed && parsed.document_id) {
            extraDocs.push(parsed);
          }
        }
      }
    }
  } catch {}

  if (extraDocs.length > 0) {
    const existingIds = new Set(DEFAULT_REVIEW_QUEUE.map((d) => d.document_id));
    return [...extraDocs.filter((d) => !existingIds.has(d.document_id)), ...DEFAULT_REVIEW_QUEUE];
  }
  return DEFAULT_REVIEW_QUEUE;
}

function ReviewQueueContent() {
  const searchParams = useSearchParams();
  const queryDocId = searchParams.get("id") || searchParams.get("document_id");

  const [queue, setQueue] = useState<DocumentRecord[]>(getInitialQueue);
  const [selectedId, setSelectedId] = useState<string>(() => queryDocId || getInitialQueue()[0].document_id);

  // Derived selected document
  const selectedDoc = queue.find((doc) => doc.document_id === selectedId) || queue[0] || null;

  // Reviewer correction form state
  const [replacementCategory, setReplacementCategory] = useState<string>(() => {
    const initialDoc = getInitialQueue()[0];
    const rawCat = (initialDoc?.category ?? "").toLowerCase().trim();
    const matched = VALID_DOCUMENT_TYPES.find(
      (opt) => opt.value === rawCat || rawCat.includes(opt.value)
    );
    return matched ? matched.value : "invoice";
  });
  const [notes, setNotes] = useState<string>("");
  const [saving, setSaving] = useState<boolean>(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  function handleSelectDocument(doc: DocumentRecord) {
    setSelectedId(doc.document_id);
    const rawCat = (doc.category ?? "").toLowerCase().trim();
    const matched = VALID_DOCUMENT_TYPES.find(
      (opt) => opt.value === rawCat || rawCat.includes(opt.value)
    );
    setReplacementCategory(matched ? matched.value : "invoice");
    setNotes("");
    setApiError(null);
    setSuccessMessage(null);
  }

  // Fetch document by query parameter if not present in the initial queue
  useEffect(() => {
    if (!queryDocId) return;

    let isMounted = true;
    const fetchDoc = async () => {
      const token = typeof window !== "undefined"
        ? (window.localStorage.getItem("kagaz_token") ?? window.sessionStorage.getItem("kagaz_token"))
        : null;

      try {
        const res = await fetch(`${API_URL}/api/documents/${queryDocId}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        });
        if (res.ok && isMounted) {
          const doc = (await res.json()) as DocumentRecord;
          setQueue((prev) => {
            if (prev.some((d) => d.document_id === doc.document_id)) return prev;
            return [doc, ...prev];
          });
          setSelectedId(doc.document_id);
          const rawCat = (doc.category ?? "").toLowerCase().trim();
          const matched = VALID_DOCUMENT_TYPES.find(
            (opt) => opt.value === rawCat || rawCat.includes(opt.value)
          );
          setReplacementCategory(matched ? matched.value : "invoice");
        }
      } catch {
        // Ignore fetch failure
      }
    };

    fetchDoc();
    return () => {
      isMounted = false;
    };
  }, [queryDocId]);

  // Handle Reviewer Save Action
  async function handleSaveCorrection() {
    if (!selectedDoc || !replacementCategory) return;
    setSaving(true);
    setApiError(null);
    setSuccessMessage(null);

    const token = typeof window !== "undefined"
      ? (window.localStorage.getItem("kagaz_token") ?? window.sessionStorage.getItem("kagaz_token"))
      : null;

    try {
      const response = await fetch(`${API_URL}/api/documents/${selectedDoc.document_id}/classification`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          category: replacementCategory,
          notes: notes.trim() || undefined,
        }),
      });

      if (!response.ok) {
        let errorDetail = `API Error (HTTP ${response.status}): Failed to save correction.`;
        try {
          const body = await response.json();
          if (body?.detail) {
            errorDetail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
          } else if (body?.error?.message) {
            errorDetail = body.error.message;
          }
        } catch {}
        throw new Error(errorDetail);
      }

      const updated = (await response.json()) as DocumentRecord;
      const targetCategoryInfo = getCategoryInfo(replacementCategory);

      // Update state with updated document
      const nextDoc: DocumentRecord = {
        ...selectedDoc,
        ...updated,
        category: updated.category ?? replacementCategory,
        confidence: updated.confidence !== undefined ? updated.confidence : 1.0,
        status: updated.status ?? "CLASSIFIED",
        is_manually_corrected: true,
      };

      setQueue((prev) => prev.map((d) => (d.document_id === nextDoc.document_id ? nextDoc : d)));

      try {
        window.sessionStorage.setItem(`kagaz_doc_${nextDoc.document_id}`, JSON.stringify(nextDoc));
      } catch {}

      setSuccessMessage(`Document classification successfully corrected to "${targetCategoryInfo.name}".`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to connect to correction API.";
      setApiError(msg);
    } finally {
      setSaving(false);
    }
  }

  const categoryInfo = getCategoryInfo(selectedDoc?.category);
  const confidenceVal = selectedDoc?.confidence !== undefined && selectedDoc?.confidence !== null ? selectedDoc.confidence : null;
  const confidencePercent = confidenceVal !== null ? Math.round(confidenceVal * 1000) / 10 : null;

  return (
    <main className="result-page">
      <nav className="topbar" aria-label="Primary navigation">
        <Link className="wordmark" href="/">Kagaz<span>.</span></Link>
        <div className="topbar-meta">
          <span className="status-dot" /> Reviewer Verification Workspace
        </div>
      </nav>

      <section className="review-page-shell" aria-labelledby="review-heading">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: "14px" }}>
          <div>
            <div className="card-eyebrow">Review Queue · Classification Verification</div>
            <h1 id="review-heading" style={{ fontSize: "clamp(32px, 4vw, 48px)", margin: "4px 0 10px" }}>
              Human Verification &amp; <em>Correction</em>
            </h1>
            <p className="intro" style={{ margin: 0, maxWidth: "600px" }}>
              Examine automated document classifications, check model confidence scores, and correct any misclassified document to ensure proper downstream routing.
            </p>
          </div>

          <Link href="/documents" className="secondary-button" style={{ alignSelf: "flex-start" }}>
            ← Back to Document Intake
          </Link>
        </div>

        {/* Global Notifications */}
        {successMessage && (
          <div className="alert-banner alert-banner-info" role="status" style={{ marginTop: "24px" }}>
            <span className="alert-banner-icon">✓</span>
            <div className="alert-banner-content">{successMessage}</div>
            <button className="alert-banner-close" type="button" onClick={() => setSuccessMessage(null)}>×</button>
          </div>
        )}

        {apiError && (
          <div className="alert-banner alert-banner-error" role="alert" style={{ marginTop: "24px" }}>
            <span className="alert-banner-icon">!</span>
            <div className="alert-banner-content">
              <strong>Correction API Error:</strong> {apiError}
            </div>
            <button className="alert-banner-close" type="button" onClick={() => setApiError(null)}>×</button>
          </div>
        )}

        <div className="review-grid">
          {/* Left Column: Review Queue List */}
          <aside className="review-queue-sidebar" aria-label="Review Queue Documents">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <strong style={{ fontSize: "14px", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                Queue Documents
              </strong>
              <span className="doc-id-pill">{queue.length} items</span>
            </div>

            <div className="queue-list" role="list">
              {queue.map((doc) => {
                const conf = doc.confidence !== undefined && doc.confidence !== null ? Math.round(doc.confidence * 100) : null;
                const isLow = conf !== null && conf < 75 && !doc.is_manually_corrected;
                const isActive = doc.document_id === selectedId;

                return (
                  <div key={doc.document_id} role="listitem">
                    <button
                      type="button"
                      className={`queue-card ${isActive ? "queue-card-active" : ""}`}
                      onClick={() => handleSelectDocument(doc)}
                      aria-current={isActive ? "true" : undefined}
                    >
                      <div className="queue-card-title">{doc.filename}</div>
                      <div className="queue-card-meta">
                        <span>{doc.category ? getCategoryInfo(doc.category).name : "Unclassified"}</span>
                        <span className={`queue-status-pill ${doc.is_manually_corrected ? "queue-status-normal" : isLow ? "queue-status-low" : "queue-status-normal"}`}>
                          {doc.is_manually_corrected ? "Verified" : conf !== null ? `${conf}%` : "Pending"}
                        </span>
                      </div>
                    </button>
                  </div>
                );
              })}
            </div>
          </aside>

          {/* Right Column: Active Document Details & Correction Control */}
          <div className="result-card" aria-label="Document Review & Correction Panel">
            {selectedDoc ? (
              <>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "14px", borderBottom: "1px solid var(--line)", paddingBottom: "20px", marginBottom: "24px" }}>
                  <div>
                    <div className="card-eyebrow">Document Under Verification</div>
                    <h2 style={{ fontSize: "28px", fontWeight: 400, margin: "6px 0 10px", color: "var(--ink)" }}>
                      {selectedDoc.filename}
                    </h2>
                    <div className="doc-meta-pills">
                      <div className="doc-id-pill">
                        <span>ID</span> <strong>{selectedDoc.document_id}</strong>
                      </div>
                      <span className="doc-id-pill">
                        Size: {formatFileSize(selectedDoc.file_size)}
                      </span>
                      <span className="doc-id-pill">
                        Uploaded: {formatDate(selectedDoc.uploaded_at)}
                      </span>
                    </div>
                  </div>

                  <Link href={`/documents/${selectedDoc.document_id}`} className="secondary-button" style={{ fontSize: "12px" }}>
                    View Full Details Page →
                  </Link>
                </div>

                {/* Scope Display 1: Current Document Type */}
                <div className="category-highlight-box">
                  <div className="category-name-row">
                    <div className="category-name">
                      <span aria-hidden="true" style={{ marginRight: "10px" }}>{categoryInfo.icon}</span>
                      {categoryInfo.name}
                    </div>
                    <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                      {selectedDoc.is_manually_corrected && (
                        <span className="correction-badge-verified">
                          ✓ Reviewer Verified
                        </span>
                      )}
                      <span className="category-badge-chip">{categoryInfo.badge}</span>
                    </div>
                  </div>
                  <p className="category-description">{categoryInfo.description}</p>
                </div>

                {/* Scope Display 2: Confidence */}
                <div className="confidence-box" aria-label="Classification Confidence">
                  <div className="confidence-header">
                    <span className="confidence-label">
                      {selectedDoc.is_manually_corrected ? "Verification Status" : "Classification Confidence"}
                    </span>
                    <span className="confidence-value">
                      {selectedDoc.is_manually_corrected ? "100%" : confidencePercent !== null ? `${confidencePercent}%` : "Not evaluated"}
                    </span>
                  </div>

                  <div className="confidence-bar-track" role="progressbar" aria-valuenow={selectedDoc.is_manually_corrected ? 100 : (confidencePercent ?? 0)} aria-valuemin={0} aria-valuemax={100}>
                    <div
                      className={`confidence-bar-fill ${
                        selectedDoc.is_manually_corrected
                          ? "confidence-bar-high"
                          : confidencePercent === null
                          ? ""
                          : confidencePercent >= 80
                          ? "confidence-bar-high"
                          : confidencePercent >= 60
                          ? "confidence-bar-med"
                          : "confidence-bar-low"
                      }`}
                      style={{ width: `${selectedDoc.is_manually_corrected ? 100 : Math.max(confidencePercent ?? 0, 4)}%` }}
                    />
                  </div>

                  <div className="confidence-tier-note">
                    <span>Routing Policy Rule</span>
                    {selectedDoc.is_manually_corrected ? (
                      <span className="confidence-tier-badge tier-high">
                        Human Verified — Overridden by Authorized Reviewer
                      </span>
                    ) : confidencePercent !== null && confidencePercent < 75 ? (
                      <span className="confidence-tier-badge tier-low">
                        Flagged for Review — Confidence is below automated routing threshold
                      </span>
                    ) : (
                      <span className="confidence-tier-badge tier-high">
                        Automated threshold satisfied — Reviewer correction available
                      </span>
                    )}
                  </div>
                </div>

                {/* Scope Display 3, 4, 5: Correction Control, Save Action, Success/Error State */}
                <div className="correction-box" role="region" aria-label="Reviewer Correction Controls">
                  <div className="correction-header">
                    <div>
                      <h3 className="correction-title">Reviewer Classification Correction</h3>
                      <div className="correction-subtitle">
                        Select a valid replacement category to correct inaccurate AI classification.
                      </div>
                    </div>
                    <span className="correction-badge-verified">Authorized Reviewer Control</span>
                  </div>

                  <div className="correction-form">
                    {/* Current Document Type Display */}
                    <div className="form-group">
                      <span className="form-label">Current Document Type</span>
                      <div className="form-current-preview">
                        <span aria-hidden="true">{categoryInfo.icon}</span>
                        <span>
                          <strong>{categoryInfo.name}</strong> ({categoryInfo.badge}) ·{" "}
                          {selectedDoc.is_manually_corrected ? "100% (Human Verified)" : confidencePercent !== null ? `${confidencePercent}% confidence` : "Unrated"}
                        </span>
                      </div>
                    </div>

                    {/* Correction Control: Valid Replacement Dropdown */}
                    <div className="form-group">
                      <label htmlFor="reviewer-replacement-select" className="form-label">
                        Select Valid Replacement Document Type
                      </label>
                      <select
                        id="reviewer-replacement-select"
                        className="form-select"
                        value={replacementCategory}
                        onChange={(e) => setReplacementCategory(e.target.value)}
                        disabled={saving}
                        aria-label="Select valid replacement document type"
                      >
                        {VALID_DOCUMENT_TYPES.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label} — {opt.badge} ({opt.routing})
                          </option>
                        ))}
                      </select>
                      <span className="form-hint">
                        Target Queue: {VALID_DOCUMENT_TYPES.find((t) => t.value === replacementCategory)?.routing}
                      </span>
                    </div>

                    {/* Reviewer Audit Rationale Input */}
                    <div className="form-group">
                      <label htmlFor="reviewer-notes" className="form-label">
                        Reviewer Correction Notes (Optional)
                      </label>
                      <input
                        id="reviewer-notes"
                        type="text"
                        className="form-input"
                        placeholder="e.g., Document contains billing terms and line items, reclassified as invoice"
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        disabled={saving}
                      />
                    </div>

                    {/* Inline API Error Notice */}
                    {apiError && (
                      <div className="correction-alert-inline correction-alert-inline-error" role="alert">
                        <span aria-hidden="true">⚠️</span>
                        <div>
                          <strong>Correction Failed:</strong> {apiError}
                        </div>
                      </div>
                    )}

                    {/* Inline Success Notice */}
                    {successMessage && (
                      <div className="correction-alert-inline correction-alert-inline-success" role="status">
                        <span aria-hidden="true">✓</span>
                        <div>{successMessage}</div>
                      </div>
                    )}

                    {/* Scope: Save Action */}
                    <div className="correction-actions">
                      <button
                        className="primary-button"
                        type="button"
                        disabled={saving || !replacementCategory}
                        onClick={handleSaveCorrection}
                        style={{ padding: "12px 24px" }}
                      >
                        {saving ? "Saving Correction..." : "Save Classification"}
                        <span aria-hidden="true">{saving ? "⏳" : "✓"}</span>
                      </button>

                      {notes && (
                        <button
                          className="secondary-button"
                          type="button"
                          disabled={saving}
                          onClick={() => setNotes("")}
                        >
                          Clear Notes
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div style={{ textAlign: "center", padding: "60px 20px", color: "var(--muted)" }}>
                <p>No document selected for review. Please select a document from the queue on the left.</p>
              </div>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}

export default function ReviewPage() {
  return (
    <Suspense fallback={<div style={{ padding: "40px", textAlign: "center" }}>Loading Review Workspace...</div>}>
      <ReviewQueueContent />
    </Suspense>
  );
}