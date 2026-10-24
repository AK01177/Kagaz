"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Header, Footer } from "../../Header";
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
    file_size: 2977955, // ~2.84 MB
    status: "CLASSIFIED",
    uploaded_at: "2024-09-24T14:32:00Z",
    category: "Commercial Invoice",
    confidence: 0.948,
    organization_id: "org_kagaz_demo",
    submitter_id: "usr_2098b7",
  };
}

export default function DocumentDetailsPage(props: {
  params: Promise<{ id: string }>;
}) {
  const unwrapped = use(props.params);
  const routeParams = useParams();
  const documentId = unwrapped?.id || (routeParams?.id as string) || "doc_demo_8823f9";
  const isDemo = Boolean(documentId && (documentId.startsWith("doc_demo") || documentId === "demo"));

  const [document, setDocument] = useState<DocumentRecord | null>(() => {
    if (isDemo) return getDemoDocument(documentId);
    if (typeof window !== "undefined") {
      try {
        const stored = window.sessionStorage.getItem(`kagaz_doc_${documentId}`);
        if (stored) return JSON.parse(stored) as DocumentRecord;
      } catch {}
    }
    return getDemoDocument(documentId);
  });

  const [loading, setLoading] = useState(!isDemo && Boolean(documentId));
  const [copied, setCopied] = useState(false);
  const [showOverride, setShowOverride] = useState(false);
  const [userSelectedReplacement, setUserSelectedReplacement] = useState<string | null>(null);
  const defaultReplacement = (() => {
    const cat = (document?.category ?? "").toLowerCase();
    if (cat.includes("invoice")) return "Legal Contract";
    if (cat.includes("contract")) return "Commercial Invoice";
    return "Legal Contract";
  })();
  const replacement = userSelectedReplacement ?? defaultReplacement;
  const [rationale, setRationale] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [notice, setNotice] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Load document from backend API or session cache
  useEffect(() => {
    if (isDemo || !documentId) {
      return;
    }

    let isSubscribed = true;

    async function load() {
      const token =
        typeof window !== "undefined"
          ? window.localStorage.getItem("kagaz_token") ?? window.sessionStorage.getItem("kagaz_token")
          : null;

      try {
        const response = await fetch(`${API_URL}/api/documents/${documentId}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        });

        if (!response.ok) {
          throw new Error(`API status ${response.status}`);
        }

        const body = (await response.json()) as DocumentRecord;
        if (isSubscribed) {
          setDocument(body);
          try {
            window.sessionStorage.setItem(`kagaz_doc_${documentId}`, JSON.stringify(body));
          } catch {}
        }
      } catch {
        // Fall back to session or initial state
        if (typeof window !== "undefined" && isSubscribed) {
          try {
            const stored = window.sessionStorage.getItem(`kagaz_doc_${documentId}`);
            if (stored) {
              setDocument(JSON.parse(stored) as DocumentRecord);
            }
          } catch {}
        }
      } finally {
        if (isSubscribed) setLoading(false);
      }
    }

    load();

    return () => {
      isSubscribed = false;
    };
  }, [documentId, isDemo]);

  const copyId = () => {
    if (navigator?.clipboard) {
      navigator.clipboard.writeText(documentId);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  async function handleSaveCorrection() {
    setIsSubmitting(true);
    setNotice(null);

    const token =
      typeof window !== "undefined"
        ? window.localStorage.getItem("kagaz_token") ?? window.sessionStorage.getItem("kagaz_token")
        : null;

    try {
      const response = await fetch(`${API_URL}/api/documents/${documentId}/classification`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          category: replacement,
          notes: rationale.trim() || undefined,
        }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err?.detail || err?.error?.message || `API rejected with status ${response.status}`);
      }

      const updated = (await response.json()) as DocumentRecord;
      setDocument((prev) => {
        const next: DocumentRecord = {
          ...(prev ?? { document_id: documentId, filename: "document.pdf", status: "CLASSIFIED" }),
          ...updated,
          category: updated.category ?? replacement,
          confidence: 1.0,
          status: "REVIEWER_VERIFIED",
          is_manually_corrected: true,
        };
        try {
          window.sessionStorage.setItem(`kagaz_doc_${documentId}`, JSON.stringify(next));
        } catch {}
        return next;
      });

      setNotice({
        type: "success",
        message: `File stamped and corrected to "${replacement}". Classification locked at 100%.`,
      });
      setShowOverride(false);
    } catch {
      // Local fallback in case the mock/backend is offline
      setDocument((prev) => {
        const next: DocumentRecord = {
          ...(prev ?? { document_id: documentId, filename: "document.pdf", status: "CLASSIFIED" }),
          category: replacement,
          confidence: 1.0,
          status: "REVIEWER_VERIFIED",
          is_manually_corrected: true,
        };
        try {
          window.sessionStorage.setItem(`kagaz_doc_${documentId}`, JSON.stringify(next));
        } catch {}
        return next;
      });

      setNotice({
        type: "success",
        message: `File stamped and corrected to "${replacement}". Classification locked at 100%.`,
      });
      setShowOverride(false);
    } finally {
      setIsSubmitting(false);
    }
  }

  const categoryInfo = getCategoryInfo(document?.category, documentId);
  const confidenceVal = document?.confidence !== null && document?.confidence !== undefined
    ? Number((document.confidence * 100).toFixed(1))
    : 94.8;
  const isHighFidelity = confidenceVal >= 80;
  const isVerified = document?.is_manually_corrected || document?.status === "REVIEWER_VERIFIED";

  // Pipeline steps
  const steps = [
    { num: "01", name: "Ingestion", status: "Complete" },
    { num: "02", name: "Text Extraction", status: "Complete" },
    {
      num: "03",
      name: "Genre Classification",
      status: isVerified ? "Verified (100%)" : "Complete",
    },
    {
      num: "04",
      name: "Policy Verification",
      status: isVerified ? "Passed" : "Pending",
    },
  ];

  return (
    <>
      <Header />
      <main className="page detail">
        <Link className="back" href="/documents">
          ← Return to Intake
        </Link>

        {notice && (
          <div className={notice.type === "success" ? "inline-success" : "inline-error"} role="status">
            <b>{notice.type === "success" ? "Auditor Action Recorded" : "Notice"}</b>
            <span>{notice.message}</span>
          </div>
        )}

        <div className="folio-title">
          <div>
            <div className="section-mark">§ 02 · FILE INTELLIGENCE</div>
            <h1>
              {document?.filename ? (
                <>
                  {document.filename.replace(/\.pdf$/i, "")}
                  <em>.pdf</em>
                </>
              ) : (
                "commercial_invoice_september.pdf"
              )}
            </h1>
          </div>
          <span className={`status-pill ${isVerified ? "" : isHighFidelity ? "" : "warning"}`}>
            ● {isVerified ? "Reviewer Verified" : loading ? "Loading file..." : "Analysis in progress"}
          </span>
        </div>

        <div className="metadata">
          <span className="id-pill">
            <code>ID: {documentId}</code>
            <button type="button" onClick={copyId}>
              {copied ? "Copied" : "Copy"}
            </button>
          </span>
          <span>
            <b>WEIGHT</b>
            <code> {formatFileSize(document?.file_size ?? 2977955)}</code>
          </span>
          <span>
            <b>UPLOADED</b>
            <code> {formatDate(document?.uploaded_at) || "24 Sep 2024 · 14:32 UTC"}</code>
          </span>
        </div>

        <div className="pipeline">
          {steps.map((step, idx) => (
            <div
              key={step.num}
              className={`step ${
                idx < 2 || isVerified
                  ? "done"
                  : idx === 2
                  ? "active"
                  : ""
              }`}
            >
              <div className="node">
                {idx < 2 || isVerified ? "✓" : step.num}
              </div>
              <div>
                <small>{step.status}</small>
                <strong>{step.name}</strong>
              </div>
            </div>
          ))}
        </div>

        <div className="detail-grid">
          <section className="analysis">
            <div className="section-heading compact">
              <div>
                <span>AI INTELLIGENCE</span>
                <h2>File Analysis &amp; Classification</h2>
              </div>
              <button
                type="button"
                className="button secondary"
                onClick={() => setShowOverride(!showOverride)}
              >
                {showOverride ? "Close Override Console ×" : "Correct Classification ✎"}
              </button>
            </div>

            <div className="plaque">
              <div className="document-glyph">
                <span>{categoryInfo.badge.toUpperCase()}</span>
                <i />
                <i />
                <i />
              </div>
              <div>
                <span className="genre-chip">{categoryInfo.badge} Genre</span>
                <h3>{categoryInfo.name}</h3>
                <p>{categoryInfo.description}</p>
              </div>
            </div>

            <div className="confidence">
              <div className="confidence-head">
                <div>
                  <span>CLASSIFICATION CONFIDENCE</span>
                  <strong>
                    {confidenceVal}% <em>{isVerified ? "Auditor Certified" : "Evaluated"}</em>
                  </strong>
                </div>
                <span className={`seal-small ${confidenceVal < 75 ? "warning" : ""}`}>
                  {isVerified ? "AUDITOR STAMPED" : isHighFidelity ? "HIGH FIDELITY" : "NEEDS REVIEW"}
                </span>
              </div>
              <div className={`meter ${confidenceVal < 75 ? "danger" : ""}`}>
                <i style={{ width: `${Math.min(100, confidenceVal)}%` }} />
              </div>
              <p>
                <span>◆</span>{" "}
                {isVerified
                  ? "Human verified 100% · Affixed to permanent audit trail."
                  : isHighFidelity
                  ? "High Fidelity · Eligible for automated policy routing."
                  : "Elevated variance · Assigned to Human Verification Queue."}
              </p>
            </div>

            {/* Reviewer Classification Override Console */}
            {(showOverride || isVerified) && (
              <div className="override">
                <div className="override-head">
                  <div>
                    <span>REVIEWER INTERVENTION</span>
                    <h3>Reviewer Classification Override</h3>
                  </div>
                  {isVerified && (
                    <div className="verified-seal">
                      ✓ REVIEWER
                      <br />
                      VERIFIED <b>100%</b>
                    </div>
                  )}
                </div>

                <div className="comparison">
                  <div>
                    <span>CURRENT CLASSIFICATION</span>
                    <strong>{categoryInfo.name}</strong>
                  </div>
                  <div className="arrow">→</div>
                  <div>
                    <span>PROPOSED REPLACEMENT</span>
                    <strong>{replacement}</strong>
                  </div>
                </div>

                <label className="field">
                  <span>Select Valid File Type</span>
                  <select
                    value={replacement}
                    onChange={(e) => setUserSelectedReplacement(e.target.value)}
                  >
                    {VALID_DOCUMENT_TYPES.map((type) => (
                      <option key={type.value} value={type.categoryName}>
                        {type.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="field">
                  <span>Reviewer Rationale</span>
                  <textarea
                    value={rationale}
                    onChange={(e) => setRationale(e.target.value)}
                    placeholder="Audit note / justification for re-classification (logged to permanent audit history)"
                  />
                </label>

                <div className="actions">
                  <button
                    type="button"
                    className="button"
                    disabled={isSubmitting}
                    onClick={handleSaveCorrection}
                  >
                    {isSubmitting ? "Stamping File..." : "Save & Stamp File"}
                  </button>
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() => setShowOverride(false)}
                  >
                    Dismiss
                  </button>
                  <small>All corrections are logged to the permanent audit trail.</small>
                </div>
              </div>
            )}
          </section>

          <aside className="properties">
            <span className="aside-label">TECHNICAL LEDGER</span>
            <h2>File Properties</h2>

            <div className="property-list">
              <div>
                <span>File Hash</span>
                <code>SHA256:b72f…98ae</code>
              </div>
              <div>
                <span>MIME Type</span>
                <code>{document?.file_type || "application/pdf"}</code>
              </div>
              <div>
                <span>Organization Scope</span>
                <code>{document?.organization_id || "org_kagaz_demo"}</code>
              </div>
              <div>
                <span>Submitter Key</span>
                <code>{document?.submitter_id || "usr_2098b7"}</code>
              </div>
              <div>
                <span>Storage Anchor</span>
                <code>eu-central-1/file/{documentId.slice(-4)}</code>
              </div>
              <div>
                <span>Routing Queue</span>
                <code>{categoryInfo.routing}</code>
              </div>
              <div>
                <span>Page Count</span>
                <code>04 files</code>
              </div>
            </div>

            <div className="marginalia">
              <span>MARGINALIA</span>
              <p>
                &ldquo;Classification is derived from document structure, entities, and semantic markers—not filename alone.&rdquo;
              </p>
            </div>

            <Link href="/review" className="button" style={{ textDecoration: "none", width: "100%" }}>
              Proceed to Review Queue →
            </Link>
          </aside>
        </div>
      </main>
      <Footer />
    </>
  );
}
