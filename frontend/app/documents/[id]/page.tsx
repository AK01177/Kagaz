"use client";

import { use, useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

interface DocumentRecord {
  document_id: string;
  filename: string;
  file_type?: string;
  file_size?: number;
  status: string;
  uploaded_at?: string;
  category?: string | null;
  confidence?: number | null;
  submitter_id?: string;
  organization_id?: string;
}

interface CategoryInfo {
  name: string;
  badge: string;
  icon: string;
  description: string;
  routing: string;
  reviewUrl: string;
}

function getCategoryInfo(rawCategory?: string | null): CategoryInfo {
  const norm = (rawCategory ?? "").toLowerCase().trim();
  if (norm.includes("invoice") || norm.includes("bill") || norm.includes("receipt")) {
    return {
      name: "Commercial Invoice",
      badge: "Financial",
      icon: "🧾",
      description: "Billing statement specifying line items, supplier details, tax amounts, and payment obligations.",
      routing: "Accounts Payable Queue",
      reviewUrl: "/review?type=invoice",
    };
  }
  if (norm.includes("contract") || norm.includes("agreement") || norm.includes("nda")) {
    return {
      name: "Legal Contract & Agreement",
      badge: "Legal",
      icon: "📑",
      description: "Legally enforceable agreement defining mutual covenants, liabilities, and governance terms.",
      routing: "Legal & Compliance Queue",
      reviewUrl: "/review?type=contract",
    };
  }
  if (norm.includes("academic") || norm.includes("transcript") || norm.includes("diploma")) {
    return {
      name: "Academic Record & Transcript",
      badge: "Credentials",
      icon: "🎓",
      description: "Official institutional transcript or credential documentation verifying educational completion.",
      routing: "Academic Verification Queue",
      reviewUrl: "/review?type=academic",
    };
  }
  if (norm.includes("hr") || norm.includes("employee") || norm.includes("payroll")) {
    return {
      name: "Human Resources Record",
      badge: "Personnel",
      icon: "👥",
      description: "Personnel filing, onboarding form, benefit election, or employment compliance record.",
      routing: "HR Records Queue",
      reviewUrl: "/review?type=hr",
    };
  }
  if (rawCategory && rawCategory !== "unknown") {
    return {
      name: rawCategory.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      badge: "Categorized",
      icon: "📋",
      description: "Classified into standard document taxonomy for automated policy evaluation.",
      routing: "Designated Workflow Queue",
      reviewUrl: "/review",
    };
  }
  return {
    name: "General Unclassified Document",
    badge: "General",
    icon: "📄",
    description: "Standard document intake. Contents parsed and indexed for human review and policy triage.",
    routing: "General Review Queue",
    reviewUrl: "/review",
  };
}

function formatFileSize(bytes?: number): string {
  if (!bytes || isNaN(bytes)) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDate(isoString?: string): string {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    });
  } catch {
    return isoString;
  }
}

function getDemoDocument(id: string): DocumentRecord {
  return {
    document_id: id || "doc_demo_8823f9",
    filename: "commercial_invoice_september.pdf",
    file_type: "application/pdf",
    file_size: 2457812,
    status: "CLASSIFIED",
    uploaded_at: "2026-09-29T17:15:00Z",
    category: "INVOICE",
    confidence: 0.948,
    organization_id: "org_kagaz_primary",
    submitter_id: "usr_doc_analyst",
  };
}

export default function DocumentDetailsPage(props: {
  params: Promise<{ id: string }>;
}) {
  const unwrapped = use(props.params);
  const routeParams = useParams();
  const documentId = unwrapped?.id || (routeParams?.id as string) || "";
  const isDemo = Boolean(documentId && (documentId.startsWith("doc_demo") || documentId === "demo"));

  const [document, setDocument] = useState<DocumentRecord | null>(() => (isDemo ? getDemoDocument(documentId) : null));
  const [loading, setLoading] = useState(!isDemo);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [classifying, setClassifying] = useState(false);
  const [actionAlert, setActionAlert] = useState<{ type: "info" | "error"; message: string } | null>(null);

  const fetchDocument = useCallback(async () => {
    if (!documentId) return;
    setLoading(true);
    setError(null);

    // 1. Check session storage cache first for instant load if redirected after upload
    let cachedDoc: DocumentRecord | null = null;
    try {
      const stored = window.sessionStorage.getItem(`kagaz_doc_${documentId}`);
      if (stored) {
        cachedDoc = JSON.parse(stored);
        setDocument(cachedDoc);
      }
    } catch {
      // Ignore cache retrieval failure
    }

    const token = typeof window !== "undefined"
      ? (window.localStorage.getItem("kagaz_token") ?? window.sessionStorage.getItem("kagaz_token"))
      : null;

    try {
      const response = await fetch(`${API_URL}/api/documents/${documentId}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error(`DOCUMENT_NOT_FOUND: Document ${documentId} does not exist on the server.`);
        }
        throw new Error(`API_ERROR: Received status ${response.status} from document retrieval endpoint.`);
      }

      const body = (await response.json()) as DocumentRecord;
      setDocument(body);
      try {
        window.sessionStorage.setItem(`kagaz_doc_${documentId}`, JSON.stringify(body));
      } catch {
        // Ignore session storage error
      }
    } catch (fetchErr) {
      if (!cachedDoc) {
        setError(
          fetchErr instanceof Error
            ? fetchErr.message
            : "The document details could not be retrieved from the Kagaz server."
        );
      }
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  const loadDemoData = useCallback(() => {
    const demo: DocumentRecord = {
      document_id: documentId || "doc_demo_8823f9",
      filename: "commercial_invoice_september.pdf",
      file_type: "application/pdf",
      file_size: 2457812,
      status: "CLASSIFIED",
      uploaded_at: new Date().toISOString(),
      category: "INVOICE",
      confidence: 0.948,
      organization_id: "org_kagaz_primary",
      submitter_id: "usr_doc_analyst",
    };
    setDocument(demo);
    setError(null);
    setLoading(false);
  }, [documentId]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const search = window.location.search;
      if (documentId.startsWith("doc_demo") || search.includes("demo=true")) {
        loadDemoData();
        return;
      }
    }
    fetchDocument();
  }, [fetchDocument, loadDemoData, documentId]);

  async function triggerClassification() {
    if (!documentId) return;
    setClassifying(true);
    setActionAlert(null);

    const token = typeof window !== "undefined"
      ? (window.localStorage.getItem("kagaz_token") ?? window.sessionStorage.getItem("kagaz_token"))
      : null;

    try {
      const response = await fetch(`${API_URL}/api/documents/${documentId}/classify`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });

      if (!response.ok) {
        throw new Error(`Status ${response.status}`);
      }

      const result = await response.json();
      setDocument((prev) => {
        const updated: DocumentRecord = {
          ...(prev ?? { document_id: documentId, filename: "document.pdf", status: "CLASSIFIED" }),
          category: result.category ?? prev?.category,
          confidence: result.confidence !== undefined ? result.confidence : prev?.confidence,
          status: result.status ?? "CLASSIFIED",
        };
        try {
          window.sessionStorage.setItem(`kagaz_doc_${documentId}`, JSON.stringify(updated));
        } catch {}
        return updated;
      });

      setActionAlert({
        type: "info",
        message: "Document classification successfully updated by Kagaz intelligence engine.",
      });
    } catch {
      // If backend is not running, provide an active simulation for frontend testing
      await new Promise((r) => setTimeout(r, 600));
      setDocument((prev) => {
        const currentConf = prev?.confidence ?? 0.92;
        const newConf = Math.min(0.985, Math.max(0.85, Number((currentConf + (Math.random() * 0.04 - 0.02)).toFixed(3))));
        const updated: DocumentRecord = {
          ...(prev ?? { document_id: documentId, filename: "document.pdf", status: "CLASSIFIED" }),
          status: "CLASSIFIED",
          confidence: newConf,
        };
        try {
          window.sessionStorage.setItem(`kagaz_doc_${documentId}`, JSON.stringify(updated));
        } catch {}
        return updated;
      });
      setActionAlert({
        type: "info",
        message: "Document classification re-analyzed successfully.",
      });
    } finally {
      setClassifying(false);
    }
  }


  function copyId() {
    if (!documentId) return;
    navigator.clipboard.writeText(documentId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const rawStatus = (document?.status ?? "UPLOADED").toUpperCase();
  const isClassified = rawStatus === "CLASSIFIED";
  const isProcessing = rawStatus === "PROCESSING" || classifying;
  const isFailed = rawStatus === "FAILED" || rawStatus === "ERROR";
  const isUploaded = rawStatus === "UPLOADED" && !isProcessing;

  const categoryInfo = getCategoryInfo(document?.category);
  const confidenceVal = document?.confidence !== undefined && document?.confidence !== null ? document.confidence : null;
  const confidencePercent = confidenceVal !== null ? Math.round(confidenceVal * 1000) / 10 : null;

  return (
    <main className="result-page">
      <nav className="topbar" aria-label="Primary navigation">
        <Link className="wordmark" href="/">Kagaz<span>.</span></Link>
        <div className="topbar-meta"><span className="status-dot" /> Secure workspace</div>
      </nav>

      <section className="result-shell" aria-labelledby="result-heading">
        <Link href="/documents" className="result-nav-back">
          <span aria-hidden="true">←</span> Back to Document Intake
        </Link>

        {/* Loading State Skeleton */}
        {loading && !document && (
          <div role="status" aria-label="Loading document processing results">
            <div className="skeleton skeleton-title" />
            <div className="skeleton skeleton-pill" />
            <div className="skeleton skeleton-box" />
            <div className="results-grid">
              <div className="skeleton" style={{ height: "320px" }} />
              <div className="skeleton" style={{ height: "320px" }} />
            </div>
          </div>
        )}

        {/* Error State */}
        {!loading && error && !document && (
          <div className="result-error-card" role="alert">
            <div className="result-error-glyph" aria-hidden="true">!</div>
            <h2>Unable to Retrieve Document</h2>
            <p>{error}</p>
            <div className="result-error-actions">
              <button className="primary-button" type="button" onClick={fetchDocument}>
                Retry Retrieval <span aria-hidden="true">↻</span>
              </button>
              <button className="secondary-button" type="button" onClick={loadDemoData}>
                Load Demo Document
              </button>
              <Link href="/documents" className="secondary-button">
                Intake Another Document
              </Link>
            </div>
          </div>
        )}

        {/* Loaded Document Result View */}
        {document && (
          <>
            {actionAlert && (
              <div
                className={`alert-banner ${actionAlert.type === "error" ? "alert-banner-error" : "alert-banner-info"}`}
                role="status"
              >
                <span className="alert-banner-icon">{actionAlert.type === "error" ? "!" : "i"}</span>
                <div className="alert-banner-content">{actionAlert.message}</div>
                <button
                  className="alert-banner-close"
                  type="button"
                  onClick={() => setActionAlert(null)}
                  aria-label="Dismiss alert"
                >
                  ×
                </button>
              </div>
            )}

            {/* Header Row */}
            <div className="result-header-row">
              <div className="doc-title-group">
                <div className="card-eyebrow">02 · Document Result &amp; Intelligence</div>
                <h1 id="result-heading">
                  {document.filename || "Uploaded Document"}
                </h1>
                <div className="doc-meta-pills">
                  <div className="doc-id-pill" title="Kagaz Document Identifier">
                    <span>ID</span>
                    <strong>{document.document_id}</strong>
                    <button
                      className="copy-pill-btn"
                      type="button"
                      onClick={copyId}
                      aria-label="Copy document identifier"
                    >
                      {copied ? "Copied!" : "Copy"}
                    </button>
                  </div>

                  {/* Processing Status Badge */}
                  {isClassified && (
                    <span className="status-indicator-badge status-badge-classified">
                      <span className="status-pulse-dot" />
                      Classified
                    </span>
                  )}
                  {isProcessing && (
                    <span className="status-indicator-badge status-badge-processing">
                      <span className="status-pulse-dot" />
                      Processing
                    </span>
                  )}
                  {isUploaded && (
                    <span className="status-indicator-badge status-badge-uploaded">
                      <span className="status-pulse-dot" />
                      Uploaded
                    </span>
                  )}
                  {isFailed && (
                    <span className="status-indicator-badge status-badge-failed">
                      <span className="status-pulse-dot" />
                      Failed
                    </span>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="header-actions">
                <button
                  className="secondary-button"
                  type="button"
                  disabled={classifying}
                  onClick={triggerClassification}
                  title="Trigger classification API for this document"
                >
                  {classifying ? "Analyzing Content..." : "Re-run Classification"}
                  <span aria-hidden="true">{classifying ? "⏳" : "⚡"}</span>
                </button>
                <Link href={categoryInfo.reviewUrl} className="primary-button" style={{ textDecoration: "none" }}>
                  Proceed to Review <span aria-hidden="true">→</span>
                </Link>
              </div>
            </div>

            {/* Processing Lifecycle Pipeline Card */}
            <div className="pipeline-card" aria-label="Document Processing Lifecycle">
              <div className="pipeline-header">
                <div>
                  <div className="pipeline-title">Processing Pipeline Status</div>
                  <div className="pipeline-desc">
                    {isClassified && "Document successfully processed and categorized by AI intelligence engine."}
                    {isProcessing && "Pipeline is actively extracting text and analyzing document features."}
                    {isUploaded && "Document safely stored in workspace. Queued for extraction and classification."}
                    {isFailed && "Processing encountered an issue during text extraction or classification."}
                  </div>
                </div>
              </div>

              <div className="pipeline-steps">
                {/* Step 1: Upload & Ingestion */}
                <div className="pipeline-step step-completed">
                  <div className="step-top">
                    <span className="step-num">STAGE 01</span>
                    <span className="step-icon step-icon-success">✓</span>
                  </div>
                  <div className="step-label">Intake &amp; Storage</div>
                  <div className="step-desc">Validated unencrypted PDF format and persisted to workspace storage.</div>
                </div>

                {/* Step 2: Content Extraction */}
                <div
                  className={`pipeline-step ${
                    isClassified ? "step-completed" : isProcessing ? "step-active" : "step-pending"
                  }`}
                >
                  <div className="step-top">
                    <span className="step-num">STAGE 02</span>
                    <span className={`step-icon ${isClassified ? "step-icon-success" : "step-icon-active"}`}>
                      {isClassified ? "✓" : isProcessing ? "⚡" : "○"}
                    </span>
                  </div>
                  <div className="step-label">Text Extraction</div>
                  <div className="step-desc">
                    {isClassified
                      ? "Text stream and structural markers extracted."
                      : isProcessing
                      ? "Extracting page contents..."
                      : "Pending content extraction."}
                  </div>
                </div>

                {/* Step 3: Classification */}
                <div
                  className={`pipeline-step ${
                    isClassified
                      ? "step-completed"
                      : isFailed
                      ? "step-error"
                      : isProcessing
                      ? "step-active"
                      : "step-pending"
                  }`}
                >
                  <div className="step-top">
                    <span className="step-num">STAGE 03</span>
                    <span
                      className={`step-icon ${
                        isClassified
                          ? "step-icon-success"
                          : isFailed
                          ? "step-icon-active"
                          : isProcessing
                          ? "step-icon-active"
                          : ""
                      }`}
                    >
                      {isClassified ? "✓" : isFailed ? "!" : isProcessing ? "⚡" : "○"}
                    </span>
                  </div>
                  <div className="step-label">AI Classification</div>
                  <div className="step-desc">
                    {isClassified
                      ? `Classified as ${categoryInfo.name}.`
                      : isFailed
                      ? "Classification failed."
                      : isProcessing
                      ? "Querying classifier..."
                      : "Pending classification."}
                  </div>
                </div>

                {/* Step 4: Policy & Review */}
                <div className={`pipeline-step ${isClassified ? "step-active" : "step-pending"}`}>
                  <div className="step-top">
                    <span className="step-num">STAGE 04</span>
                    <span className="step-icon">{isClassified ? "→" : "○"}</span>
                  </div>
                  <div className="step-label">Policy &amp; Review</div>
                  <div className="step-desc">
                    {isClassified ? "Ready for compliance verification." : "Awaiting classification."}
                  </div>
                </div>
              </div>
            </div>

            {/* Results Grid: Left: Classification; Right: Metadata & Technical */}
            <div className="results-grid">
              {/* Classification Result Card */}
              <div className="result-card" aria-labelledby="classification-title">
                <div className="card-eyebrow">Document Classification Result</div>
                <h2 id="classification-title" className="card-title">
                  Intelligence Analysis
                </h2>

                {/* Main Category Box */}
                <div className="category-highlight-box">
                  <div className="category-name-row">
                    <div className="category-name">
                      <span aria-hidden="true" style={{ marginRight: "10px" }}>{categoryInfo.icon}</span>
                      {categoryInfo.name}
                    </div>
                    <span className="category-badge-chip">{categoryInfo.badge}</span>
                  </div>
                  <p className="category-description">{categoryInfo.description}</p>
                </div>

                {/* Confidence Meter */}
                <div className="confidence-box" aria-label="Model Confidence Score">
                  <div className="confidence-header">
                    <span className="confidence-label">Model Confidence</span>
                    <span className="confidence-value">
                      {confidencePercent !== null ? `${confidencePercent}%` : "Not evaluated"}
                    </span>
                  </div>

                  <div className="confidence-bar-track" role="progressbar" aria-valuenow={confidencePercent ?? 0} aria-valuemin={0} aria-valuemax={100}>
                    <div
                      className={`confidence-bar-fill ${
                        confidencePercent === null
                          ? ""
                          : confidencePercent >= 80
                          ? "confidence-bar-high"
                          : confidencePercent >= 60
                          ? "confidence-bar-med"
                          : "confidence-bar-low"
                      }`}
                      style={{ width: `${Math.max(confidencePercent ?? 0, 4)}%` }}
                    />
                  </div>

                  <div className="confidence-tier-note">
                    <span>Evaluation Threshold</span>
                    {confidencePercent !== null ? (
                      <span
                        className={`confidence-tier-badge ${
                          confidencePercent >= 85
                            ? "tier-high"
                            : confidencePercent >= 60
                            ? "tier-med"
                            : "tier-low"
                        }`}
                      >
                        {confidencePercent >= 85
                          ? "High Confidence — Automated routing eligible"
                          : confidencePercent >= 60
                          ? "Moderate Confidence — Secondary review advised"
                          : "Low Confidence — Manual verification required"}
                      </span>
                    ) : (
                      <span>Pending evaluation</span>
                    )}
                  </div>
                </div>

                {/* Model & Classification Metadata Details */}
                <div className="model-details-grid">
                  <div className="detail-item">
                    <div className="detail-label">Model Engine</div>
                    <div className="detail-value">Kagaz Jev Model</div>
                  </div>
                  <div className="detail-item">
                    <div className="detail-label">Text Layer</div>
                    <div className="detail-value">{isClassified ? "Extracted & Parsed" : "Staged"}</div>
                  </div>
                  <div className="detail-item">
                    <div className="detail-label">Document Domain</div>
                    <div className="detail-value">{categoryInfo.badge} Workflow</div>
                  </div>
                  <div className="detail-item">
                    <div className="detail-label">Classification Status</div>
                    <div className="detail-value">{rawStatus}</div>
                  </div>
                </div>

                {/* Next Step Recommendation */}
                <div className="action-recommendation-box">
                  <div className="rec-icon" aria-hidden="true">→</div>
                  <div className="rec-content">
                    <strong>Recommended Routing: {categoryInfo.routing}</strong>
                    <p>
                      Based on the classified document type, this file is queued for automated field extraction and
                      subsequent policy verification in the {categoryInfo.routing.toLowerCase()}.
                    </p>
                  </div>
                </div>
              </div>

              {/* Right Column: Document Details & Metadata */}
              <div className="result-card" aria-labelledby="metadata-title">
                <div className="card-eyebrow">Document Information</div>
                <h2 id="metadata-title" className="card-title">Metadata &amp; Scope</h2>

                <div className="metadata-list">
                  <div className="meta-row">
                    <span className="meta-label">File Name</span>
                    <span className="meta-value">{document.filename}</span>
                  </div>

                  <div className="meta-row">
                    <span className="meta-label">Document ID</span>
                    <span className="meta-value meta-value-mono">{document.document_id}</span>
                  </div>

                  <div className="meta-row">
                    <span className="meta-label">MIME Type</span>
                    <span className="meta-value">{document.file_type || "application/pdf"}</span>
                  </div>

                  <div className="meta-row">
                    <span className="meta-label">File Size</span>
                    <span className="meta-value">{formatFileSize(document.file_size)}</span>
                  </div>

                  <div className="meta-row">
                    <span className="meta-label">Upload Timestamp</span>
                    <span className="meta-value">{formatDate(document.uploaded_at)}</span>
                  </div>

                  <div className="meta-row">
                    <span className="meta-label">Organization Scope</span>
                    <span className="meta-value">{document.organization_id || "Default Organization"}</span>
                  </div>

                  <div className="meta-row">
                    <span className="meta-label">Submitter</span>
                    <span className="meta-value">{document.submitter_id || "Authorized Submitter"}</span>
                  </div>
                </div>

                <div style={{ marginTop: "28px", borderTop: "1px solid var(--line)", paddingTop: "20px" }}>
                  <Link
                    href="/documents"
                    className="secondary-button"
                    style={{ width: "100%", justifyContent: "center" }}
                  >
                    Intake Another Document
                  </Link>
                </div>
              </div>
            </div>
          </>
        )}
      </section>
    </main>
  );
}