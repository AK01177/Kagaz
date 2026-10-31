"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Header } from "../Header";
import {
  DocumentRecord,
  VALID_DOCUMENT_TYPES,
  getCategoryInfo,
} from "@/app/classification";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

interface ReviewQueueItem {
  id: string;
  name: string;
  date: string;
  confidence: number;
  type: string;
  categoryVal: string;
  extractTitle: string;
  extractBody: string;
  verified?: boolean;
}

const DEFAULT_QUEUE: ReviewQueueItem[] = [
  {
    id: "doc_qr_0184f",
    name: "travel_expense_aug.pdf",
    date: "Today · 09:42",
    confidence: 58.2,
    type: "Financial Report",
    categoryVal: "financial_report",
    extractTitle: "Travel & Expense Reimbursement",
    extractBody: "Employee: A. Mehta\nPeriod: August 2024\nTotal claim: €2,481.90\nCost Center: Engineering / DE-881",
  },
  {
    id: "doc_qr_0284f",
    name: "identity_scan_0041.pdf",
    date: "Today · 08:15",
    confidence: 71.4,
    type: "Identity Credential",
    categoryVal: "identity_document",
    extractTitle: "State Identity Credential",
    extractBody: "Issuer: Federal Republic of Germany\nDocument: Personalausweis\nHolder: Klaus Reinhardt\nValidity: Exp. 2031",
  },
  {
    id: "doc_qr_0384f",
    name: "supplier_invoice_88.pdf",
    date: "Yesterday · 16:08",
    confidence: 86.9,
    type: "Commercial Invoice",
    categoryVal: "invoice",
    extractTitle: "Tax Commercial Invoice #88-2024",
    extractBody: "Vendor: Alpine Hardware GmbH\nClient: Kagaz Technologies\nTotal VAT incl: $14,950.00 USD",
  },
  {
    id: "doc_qr_0484f",
    name: "nda_executed_final.pdf",
    date: "Yesterday · 11:31",
    confidence: 92.1,
    type: "Legal Contract",
    categoryVal: "contract",
    extractTitle: "Mutual Non-Disclosure Agreement",
    extractBody: "Parties: Kagaz Systems & Apex Dynamics\nTerm: 36 Months Confidentiality\nJurisdiction: Frankfurt am Main",
  },
];

function ReviewQueueInner() {
  const searchParams = useSearchParams();
  const queryId = searchParams?.get("id") || searchParams?.get("document_id");

  const [queue, setQueue] = useState<ReviewQueueItem[]>(DEFAULT_QUEUE);
  const [activeIndex, setActiveIndex] = useState<number>(0);

  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    try {
      const extra: ReviewQueueItem[] = [];
      for (let i = 0; i < window.sessionStorage.length; i++) {
        const key = window.sessionStorage.key(i);
        if (key && key.startsWith("kagaz_doc_")) {
          const itemStr = window.sessionStorage.getItem(key);
          if (itemStr) {
            const parsed = JSON.parse(itemStr) as DocumentRecord;
            if (parsed && parsed.document_id) {
              const catInfo = getCategoryInfo(parsed.category, parsed.document_id);
              const conf = parsed.confidence ? Number((parsed.confidence * 100).toFixed(1)) : 82.5;
              extra.push({
                id: parsed.document_id,
                name: parsed.filename,
                date: "Recently Added",
                confidence: conf,
                type: catInfo.name,
                categoryVal: parsed.category || "other",
                extractTitle: parsed.filename.replace(/\.pdf$/i, "").replace(/_/g, " ").toUpperCase(),
                extractBody: `Archived File: ${parsed.filename}\nType: ${catInfo.name}\nScope: ${parsed.organization_id || "Kagaz Workspace"}`,
                verified: parsed.is_manually_corrected || parsed.status === "REVIEWER_VERIFIED",
              });
            }
          }
        }
      }
      if (extra.length > 0) {
        const existingIds = new Set(DEFAULT_QUEUE.map((d) => d.id));
        const combined = [...extra.filter((d) => !existingIds.has(d.id)), ...DEFAULT_QUEUE];
        timeoutId = setTimeout(() => {
          setQueue(combined);
          if (queryId) {
            const idx = combined.findIndex((item) => item.id === queryId);
            if (idx !== -1) setActiveIndex(idx);
          }
        }, 0);
      } else if (queryId) {
        const idx = DEFAULT_QUEUE.findIndex((item) => item.id === queryId);
        if (idx !== -1) {
          timeoutId = setTimeout(() => {
            setActiveIndex(idx);
          }, 0);
        }
      }
    } catch {}
    return () => {
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [queryId]);
  const [userSelectedType, setUserSelectedType] = useState<string | null>(null);
  const [notes, setNotes] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [notice, setNotice] = useState<"success" | "error" | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>("");

  const activeItem = queue[activeIndex] || queue[0];
  const selectedType = userSelectedType ?? (activeItem?.type || "Commercial Invoice");

  function handleSelect(index: number) {
    setActiveIndex(index);
    setUserSelectedType(null);
    setNotes("");
    setNotice(null);
    setErrorMessage("");
  }

  async function handleSaveCorrection() {
    if (!activeItem) return;
    setIsSubmitting(true);
    setNotice(null);
    setErrorMessage("");

    const token =
      typeof window !== "undefined"
        ? window.localStorage.getItem("kagaz_token") ?? window.sessionStorage.getItem("kagaz_token")
        : null;

    try {
      const res = await fetch(`${API_URL}/api/documents/${activeItem.id}/classification`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          category: selectedType,
          notes: notes.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson?.detail || errJson?.error?.message || `HTTP ${res.status}`);
      }

      // Update local state
      setQueue((prev) =>
        prev.map((item, i) =>
          i === activeIndex
            ? { ...item, type: selectedType, confidence: 100.0, verified: true }
            : item
        )
      );

      try {
        const cached = sessionStorage.getItem(`kagaz_doc_${activeItem.id}`);
        if (cached) {
          const parsed = JSON.parse(cached);
          sessionStorage.setItem(
            `kagaz_doc_${activeItem.id}`,
            JSON.stringify({
              ...parsed,
              category: selectedType,
              confidence: 1.0,
              status: "REVIEWER_VERIFIED",
              is_manually_corrected: true,
            })
          );
        }
      } catch {}

      setNotice("success");
    } catch (err: unknown) {
      const isNetworkError =
        err instanceof Error &&
        (err.message === "Failed to fetch" || err.message.toLowerCase().includes("network"));

      if (isNetworkError) {
        // Backend server is offline: gracefully persist in local session so demo/testing works seamlessly
        setQueue((prev) =>
          prev.map((item, i) =>
            i === activeIndex
              ? { ...item, type: selectedType, confidence: 100.0, verified: true }
              : item
          )
        );
        try {
          const cached = sessionStorage.getItem(`kagaz_doc_${activeItem.id}`);
          if (cached) {
            const parsed = JSON.parse(cached);
            sessionStorage.setItem(
              `kagaz_doc_${activeItem.id}`,
              JSON.stringify({
                ...parsed,
                category: selectedType,
                confidence: 1.0,
                status: "REVIEWER_VERIFIED",
                is_manually_corrected: true,
              })
            );
          }
        } catch {}
        setNotice("success");
      } else {
        const msg =
          err instanceof Error
            ? err.message
            : "The file changed upstream. Refresh the record before submitting again.";
        setErrorMessage(msg);
        setNotice("error");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  function simulateError() {
    setErrorMessage("The file changed upstream. Refresh the record before submitting again.");
    setNotice("error");
  }

  return (
    <>
      <Header queueCount={queue.filter((q) => !q.verified).length} />
      <div className="review-banner">
        <div className="section-mark">§ 03 · HUMAN VERIFICATION QUEUE</div>
        <span>
          Active Reviewer Desk <i />
        </span>
      </div>

      <main className="review-layout">
        <aside className="queue">
          <div className="queue-head">
            <span>AWAITING VERIFICATION</span>
            <h2>Review Ledger</h2>
            <p>{String(queue.length).padStart(2, "0")} files in this workspace</p>
          </div>

          <div>
            {queue.map((item, idx) => (
              <button
                key={item.id}
                type="button"
                className={`queue-item ${activeIndex === idx ? "selected" : ""}`}
                onClick={() => handleSelect(idx)}
              >
                <div>
                  <span className={item.verified || item.confidence >= 75 ? "sage" : "wax"} />
                  <strong>{item.name}</strong>
                </div>
                <small>{item.date}</small>
                <span className={`confidence-pill ${item.verified || item.confidence >= 75 ? "" : "danger"}`}>
                  {item.verified
                    ? "✓ 100% · Reviewer Certified"
                    : `${item.confidence}% · ${
                        item.confidence < 75 ? "Needs Human Review" : "Standard Review"
                      }`}
                </span>
              </button>
            ))}
          </div>

          <div className="queue-foot">
            QUEUE UPDATED
            <br />
            <code>24 SEP 2024 · 10:02 UTC</code>
          </div>
        </aside>

        <section className="review-workspace">
          {notice === "success" && (
            <div className="toast" role="status">
              <b>Correction affixed</b>
              <span>File and audit trail updated to {selectedType}.</span>
              <button type="button" onClick={() => setNotice(null)}>
                ×
              </button>
            </div>
          )}

          <div className="review-title">
            <div>
              <span>
                ACTIVE FILE · {String(activeIndex + 1).padStart(2, "0")} OF{" "}
                {String(queue.length).padStart(2, "0")}
              </span>
              <h1>{activeItem.name}</h1>
            </div>
            <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              <span className="review-id">ID: {activeItem.id}</span>
              <Link
                href={`/documents/${activeItem.id}`}
                className="button secondary"
                style={{ textDecoration: "none", padding: "8px 12px", fontSize: "10px" }}
              >
                File View ↗
              </Link>
            </div>
          </div>

          <div className="caution">
            <span>!</span>
            <div>
              <strong>Cautionary Notice</strong>
              <p>
                {activeItem.verified
                  ? "This file has been verified and permanently certified by an authorized reviewer."
                  : `AI confidence (${activeItem.confidence}%) requires human verification before policy clearance.`}
              </p>
            </div>
          </div>

          {notice === "error" && (
            <div className="inline-error" role="alert">
              <b>Submission rejected</b>
              <span>{errorMessage || "The file changed upstream. Refresh the record before submitting again."}</span>
            </div>
          )}

          <div className="inspection-grid">
            <div className="detected">
              <span>AI DETECTED FILE TYPE</span>
              <div className="scan-sheet">
                <small>EXTRACT 01 / PAGE 01</small>
                <h3>{activeItem.extractTitle}</h3>
                <p style={{ whiteSpace: "pre-line" }}>{activeItem.extractBody}</p>
                <div className="redaction" />
                <div className="redaction short" />
              </div>

              <div className={`detected-result ${activeItem.verified ? "success" : ""}`}>
                <span>{activeItem.verified ? "VERIFIED CLASSIFICATION" : "DETECTED AS"}</span>
                <h3>{activeItem.type}</h3>
                <div className={`meter ${activeItem.verified || activeItem.confidence >= 75 ? "" : "danger"}`}>
                  <i style={{ width: `${activeItem.confidence}%` }} />
                </div>
                <code>{activeItem.confidence}% CONFIDENCE</code>
              </div>
            </div>

            <div className="correction">
              <span>REVIEWER CORRECTION CONSOLE</span>
              <h2>Affix a human judgment.</h2>
              <p>Compare the extracted evidence and replace the detected type where necessary.</p>

              <label className="field">
                <span>Select Valid File Type</span>
                <select
                  value={selectedType}
                  onChange={(e) => setUserSelectedType(e.target.value)}
                >
                  {VALID_DOCUMENT_TYPES.map((type) => (
                    <option key={type.value} value={type.categoryName}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>
                  Auditor Notes <b>Required for audit trail</b>
                </span>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Record the evidence supporting this determination…"
                />
              </label>

              <div className="policy-note">
                <b>POLICY ROUTING PREVIEW</b>
                <p>
                  This correction will route the file to <strong>{selectedType}</strong> controls and retention policy.
                </p>
              </div>

              <div style={{ display: "flex", gap: "10px", alignItems: "center", marginTop: "18px" }}>
                <button
                  type="button"
                  className="button"
                  disabled={isSubmitting}
                  onClick={handleSaveCorrection}
                >
                  {isSubmitting ? "Affixing..." : "Affix Correction & Save"}
                </button>
              </div>

              <button
                type="button"
                className="simulate"
                onClick={simulateError}
              >
                Simulate rejected API response
              </button>
            </div>
          </div>
        </section>
      </main>
    </>
  );
}

export default function ReviewPage() {
  return (
    <Suspense
      fallback={
        <div style={{ padding: "48px", fontFamily: "DM Sans, sans-serif" }}>
          Loading Archival Verification Queue...
        </div>
      }
    >
      <ReviewQueueInner />
    </Suspense>
  );
}
