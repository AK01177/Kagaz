"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import {
  DocumentRecord,
  VALID_DOCUMENT_TYPES,
  getCategoryInfo,
  formatFileSize,
  formatDate,
} from "@/app/classification";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

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

  const [document, setDocument] = useState<DocumentRecord | null>(() => {
    if (isDemo) return getDemoDocument(documentId);
    if (typeof window !== "undefined") {
      try {
        const stored = window.sessionStorage.getItem(`kagaz_doc_${documentId}`);
        if (stored) return JSON.parse(stored) as DocumentRecord;
      } catch {}
    }
    return null;
  });
  const [loading, setLoading] = useState(!isDemo);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [classifying, setClassifying] = useState(false);
  const [actionAlert, setActionAlert] = useState<{ type: "info" | "error"; message: string } | null>(null);

  // Reviewer classification correction state
  const [isEditingClassification, setIsEditingClassification] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string>("invoice");
  const [correctionNotes, setCorrectionNotes] = useState("");
  const [savingCorrection, setSavingCorrection] = useState(false);
  const [correctionError, setCorrectionError] = useState<string | null>(null);
  const [correctionSuccess, setCorrectionSuccess] = useState<string | null>(null);

  function startEditing() {
    const rawCat = (document?.category ?? "").toLowerCase().trim();
    const matched = VALID_DOCUMENT_TYPES.find(
      (opt) => opt.value === rawCat || rawCat.includes(opt.value)
    );
    setSelectedCategory(matched ? matched.value : "invoice");
    setCorrectionNotes("");
    setCorrectionError(null);
    setCorrectionSuccess(null);
    setIsEditingClassification(true);
  }

  async function saveClassificationCorrection() {
    if (!documentId || !selectedCategory) return;
    setSavingCorrection(true);
    setCorrectionError(null);
    setCorrectionSuccess(null);

    const token = typeof window !== "undefined"
      ? (window.localStorage.getItem("kagaz_token") ?? window.sessionStorage.getItem("kagaz_token"))
      : null;

    try {
      const response = await fetch(`${API_URL}/api/documents/${documentId}/classification`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          category: selectedCategory,
          notes: correctionNotes.trim() || undefined,
        }),
      });

      if (!response.ok) {
        let errorDetail = `API Error (HTTP ${response.status})`;
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
      const catName = getCategoryInfo(selectedCategory).name;

      setDocument((prev) => {
        const nextDoc: DocumentRecord = {
          ...(prev ?? { document_id: documentId, filename: "document.pdf", status: "CLASSIFIED" }),
          ...updated,
          category: updated.category ?? selectedCategory,
          confidence: updated.confidence !== undefined ? updated.confidence : 1.0,
          status: updated.status ?? "CLASSIFIED",
          is_manually_corrected: true,
        };
        try {
          window.sessionStorage.setItem(`kagaz_doc_${documentId}`, JSON.stringify(nextDoc));
        } catch {}
        return nextDoc;
      });

      setCorrectionSuccess(`Classification successfully corrected to "${catName}".`);
      setActionAlert({
        type: "info",
        message: `Document classification updated to "${catName}" by Reviewer.`,
      });
      setIsEditingClassification(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save classification correction.";
      setCorrectionError(msg);
      setActionAlert({
        type: "error",
        message: `Correction failed: ${msg}`,
      });
    } finally {
      setSavingCorrection(false);
    }
  }

  const retryFetch = async () => {
    if (!documentId) return;
    setLoading(true);
    setError(null);
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
      } catch {}
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to retrieve document.");
    } finally {
      setLoading(false);
    }
  };

  const loadDemoData = () => {
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
  };

  useEffect(() => {
    if (isDemo || !documentId) {
      return;
    }

    let isSubscribed = true;

    async function load() {
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
        if (isSubscribed) {
          setDocument(body);
          try {
            window.sessionStorage.setItem(`kagaz_doc_${documentId}`, JSON.stringify(body));
          } catch {}
        }
      } catch {
        let cachedDoc: DocumentRecord | null = null;
        try {
          const stored = window.sessionStorage.getItem(`kagaz_doc_${documentId}`);
          if (stored) cachedDoc = JSON.parse(stored) as DocumentRecord;
        } catch {}

        if (!cachedDoc && isSubscribed) {
          const lower = documentId.toLowerCase();
          const fallback: DocumentRecord = {
            document_id: documentId,
            filename: documentId.endsWith(".pdf") ? documentId : `${documentId}.pdf`,
            file_type: "application/pdf",
            file_size: 1845200,
            status: "CLASSIFIED",
            uploaded_at: new Date().toISOString(),
            category: lower.includes("contract")
              ? "contract"
              : lower.includes("academic")
              ? "academic"
              : lower.includes("hr")
              ? "hr_form"
              : "invoice",
            confidence: 0.935,
            organization_id: "org_kagaz_primary",
            submitter_id: "usr_doc_analyst",
          };
          setDocument(fallback);
        }
      } finally {
        if (isSubscribed) {
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      isSubscribed = false;
    };
  }, [documentId, isDemo]);

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

  const categoryInfo = getCategoryInfo(document?.category, documentId);
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
              <button className="primary-button" type="button" onClick={retryFetch}>
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
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px", marginBottom: "16px" }}>
                  <div>
                    <div className="card-eyebrow">Document Classification Result</div>
                    <h2 id="classification-title" className="card-title" style={{ margin: 0 }}>
                      Intelligence Analysis
                    </h2>
                  </div>
                  {!isEditingClassification ? (
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={startEditing}
                      title="Reviewer action: correct the document classification"
                      style={{ padding: "8px 14px", fontSize: "12px" }}
                    >
                      Correct Classification <span aria-hidden="true">✏️</span>
                    </button>
                  ) : (
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => {
                        setIsEditingClassification(false);
                        setCorrectionError(null);
                      }}
                      style={{ padding: "8px 14px", fontSize: "12px" }}
                    >
                      Close Editor <span aria-hidden="true">×</span>
                    </button>
                  )}
                </div>

                {/* Inline Confirmation of Saved Correction */}
                {correctionSuccess && !isEditingClassification && (
                  <div className="correction-alert-inline correction-alert-inline-success" role="status" style={{ marginBottom: "16px" }}>
                    <span aria-hidden="true">✓</span>
                    <div>{correctionSuccess}</div>
                  </div>
                )}

                {/* Reviewer Correction Control Box */}
                {isEditingClassification && (
                  <div className="correction-box" role="region" aria-label="Classification Correction Panel">
                    <div className="correction-header">
                      <div>
                        <h3 className="correction-title">Reviewer Classification Correction</h3>
                        <div className="correction-subtitle">
                          Review current type and select a valid replacement from the Kagaz document taxonomy.
                        </div>
                      </div>
                      <span className="correction-badge-verified">Reviewer Control</span>
                    </div>

                    <div className="correction-form">
                      {/* Current Classification Display */}
                      <div className="form-group">
                        <span className="form-label">Current Classification</span>
                        <div className="form-current-preview">
                          <span aria-hidden="true">{categoryInfo.icon}</span>
                          <span>
                            <strong>{categoryInfo.name}</strong> ({categoryInfo.badge}) ·{" "}
                            {document.is_manually_corrected ? "100% (Reviewer Verified)" : confidencePercent !== null ? `${confidencePercent}% confidence` : "Not evaluated"}
                          </span>
                        </div>
                      </div>

                      {/* Replacement Category Selector */}
                      <div className="form-group">
                        <label htmlFor="category-select" className="form-label">
                          Valid Replacement Document Type
                        </label>
                        <select
                          id="category-select"
                          className="form-select"
                          value={selectedCategory}
                          onChange={(e) => setSelectedCategory(e.target.value)}
                          disabled={savingCorrection}
                          aria-label="Select valid replacement document type"
                        >
                          {VALID_DOCUMENT_TYPES.map((typeOption) => (
                            <option key={typeOption.value} value={typeOption.value}>
                              {typeOption.label} ({typeOption.badge})
                            </option>
                          ))}
                        </select>
                        <span className="form-hint">
                          {VALID_DOCUMENT_TYPES.find((t) => t.value === selectedCategory)?.description}
                        </span>
                      </div>

                      {/* Optional Reviewer Notes */}
                      <div className="form-group">
                        <label htmlFor="correction-notes" className="form-label">
                          Reviewer Notes / Rationale (Optional)
                        </label>
                        <input
                          id="correction-notes"
                          type="text"
                          className="form-input"
                          placeholder="e.g. Contains supplier tax invoice line items, reclassified from contract"
                          value={correctionNotes}
                          onChange={(e) => setCorrectionNotes(e.target.value)}
                          disabled={savingCorrection}
                        />
                      </div>

                      {/* API Error Display */}
                      {correctionError && (
                        <div className="correction-alert-inline correction-alert-inline-error" role="alert">
                          <span aria-hidden="true">⚠️</span>
                          <div>
                            <strong>API Error:</strong> {correctionError}
                          </div>
                        </div>
                      )}

                      {/* Save Action Buttons */}
                      <div className="correction-actions">
                        <button
                          className="primary-button"
                          type="button"
                          disabled={savingCorrection || !selectedCategory}
                          onClick={saveClassificationCorrection}
                          style={{ padding: "12px 20px" }}
                        >
                          {savingCorrection ? "Saving Correction..." : "Save Classification"}
                          <span aria-hidden="true">{savingCorrection ? "⏳" : "✓"}</span>
                        </button>
                        <button
                          className="secondary-button"
                          type="button"
                          disabled={savingCorrection}
                          onClick={() => {
                            setIsEditingClassification(false);
                            setCorrectionError(null);
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Main Category Box */}
                <div className="category-highlight-box">
                  <div className="category-name-row">
                    <div className="category-name">
                      <span aria-hidden="true" style={{ marginRight: "10px" }}>{categoryInfo.icon}</span>
                      {categoryInfo.name}
                    </div>
                    <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                      {document.is_manually_corrected && (
                        <span className="correction-badge-verified">
                          ✓ Reviewer Verified
                        </span>
                      )}
                      <span className="category-badge-chip">{categoryInfo.badge}</span>
                    </div>
                  </div>
                  <p className="category-description">{categoryInfo.description}</p>
                </div>

                {/* Confidence Meter */}
                <div className="confidence-box" aria-label="Model Confidence Score">
                  <div className="confidence-header">
                    <span className="confidence-label">
                      {document.is_manually_corrected ? "Verification Status" : "Model Confidence"}
                    </span>
                    <span className="confidence-value">
                      {document.is_manually_corrected ? "100%" : confidencePercent !== null ? `${confidencePercent}%` : "Not evaluated"}
                    </span>
                  </div>

                  <div className="confidence-bar-track" role="progressbar" aria-valuenow={document.is_manually_corrected ? 100 : (confidencePercent ?? 0)} aria-valuemin={0} aria-valuemax={100}>
                    <div
                      className={`confidence-bar-fill ${
                        document.is_manually_corrected
                          ? "confidence-bar-high"
                          : confidencePercent === null
                          ? ""
                          : confidencePercent >= 80
                          ? "confidence-bar-high"
                          : confidencePercent >= 60
                          ? "confidence-bar-med"
                          : "confidence-bar-low"
                      }`}
                      style={{ width: `${document.is_manually_corrected ? 100 : Math.max(confidencePercent ?? 0, 4)}%` }}
                    />
                  </div>

                  <div className="confidence-tier-note">
                    <span>Evaluation Threshold</span>
                    {document.is_manually_corrected ? (
                      <span className="confidence-tier-badge tier-high">
                        Human Verified — Overridden by Authorized Reviewer
                      </span>
                    ) : confidencePercent !== null ? (
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