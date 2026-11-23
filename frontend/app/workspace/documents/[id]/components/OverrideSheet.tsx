"use client";

import React, { useState, useEffect } from "react";
import { Button, Badge, Icon } from "../../../../components/AppShell";
import { apiError } from "../../../../lib/api";
import { VALID_DOCUMENT_TYPES, toBackendCategory } from "@/app/classification";


export function OverrideSheet({
  documentId,
  currentCategory,
  onClose,
  onSaved,
  fetchWithAuth,
}: {
  documentId: string;
  currentCategory: string;
  onClose: () => void;
  onSaved: (category: string, confidence: number | null, status: string) => void;
  fetchWithAuth: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
}) {
  const [rationale, setRationale] = useState("");
  const [type, setType] = useState(VALID_DOCUMENT_TYPES[0].categoryName);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  async function handleSave() {
    setSubmitting(true);
    const canonicalCategory = toBackendCategory(type);
    if (!canonicalCategory) {
      setError("Choose a valid document type.");
      setSubmitting(false);
      return;
    }

    try {
      const response = await fetchWithAuth(`/api/documents/${documentId}/classification`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ category: canonicalCategory, notes: rationale }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(apiError(result, `Save failed (${response.status}).`));
      }
      onSaved(type, result.confidence ?? null, result.status || "CLASSIFIED");
      onClose();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Could not save the classification.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="sheet-backdrop" onMouseDown={onClose} role="dialog" aria-modal="true" aria-label="Classification Override Drawer">
      <aside className="override-sheet" onMouseDown={(e) => e.stopPropagation()}>
        <div className="sheet-bar">
          <span>
            <Icon name="pencil" /> CLASSIFICATION OVERRIDE
          </span>
          <button type="button" onClick={onClose} aria-label="Close drawer">
            ×
          </button>
        </div>
        <div className="sheet-form">
          <div>
            <h2>Reviewer Classification Override</h2>
            <p>
              Your judgment takes precedence. Correct the document genre and leave a reason for the audit ledger.
            </p>
          </div>
          <div className="affected">
            <Icon name="file" size={18} />
            <div>
              <b>{documentId}</b>
              <code>Audited Scope</code>
            </div>
          </div>
          <label>
            <span>CURRENT CLASSIFICATION</span>
            <div className="readonly">
              {currentCategory} <Badge>AI · Evaluated</Badge>
            </div>
          </label>
          {error && <p role="alert" className="error-text">{error}</p>}
          <label>
            <span>PROPOSED CLASSIFICATION</span>
            <select value={type} onChange={(e) => setType(e.target.value)} aria-label="Proposed Classification">
              {VALID_DOCUMENT_TYPES.map((t) => (
                <option key={t.value} value={t.categoryName}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>
              RATIONALE <em>Required</em>
            </span>
            <textarea
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              placeholder="Audit justification for permanent ledger..."
              aria-label="Rationale"
            />
            <small>Explain what you reviewed and why the classification should change.</small>
          </label>
        </div>
        <div className="sheet-foot">
          <p>
            <Icon name="stamp" /> The backend records the corrected classification and reviewer rationale in the document audit history.
          </p>
          <Button
            variant="primary"
            icon="stamp"
            disabled={!rationale || submitting}
            onClick={handleSave}
          >
            {submitting ? "Saving..." : "Save Classification"}
          </Button>
        </div>
      </aside>
    </div>
  );
}
