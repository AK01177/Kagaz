"use client";

import React, { useState } from "react";
import { Button, Badge, Icon } from "../../../../components/AppShell";
import { DocumentRecord, formatFileSize, formatDate } from "@/app/classification";

interface DocumentHeaderProps {
  document: DocumentRecord;
  documentId: string;
  categoryName: string;
  approved: boolean;
  rerunning: boolean;
  onRerunExtraction: () => void;
  onOpenOverride: () => void;
}

export function DocumentHeader({
  document,
  documentId,
  categoryName,
  approved,
  rerunning,
  onRerunExtraction,
  onOpenOverride,
}: DocumentHeaderProps) {
  const [copied, setCopied] = useState(false);

  function copyId() {
    if (navigator?.clipboard) {
      navigator.clipboard.writeText(documentId);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  const confidenceNum = document.confidence !== null && document.confidence !== undefined
    ? Math.round(document.confidence > 1 ? document.confidence : document.confidence * 100)
    : null;

  return (
    <header className="inspector-head">
      <div className="crumb">
        <Icon name="folder" size={14} /> Library <span>/</span> {categoryName} <span>/</span>{" "}
        <code>{document.filename}</code>
        <div className="record-lock">
          <span className="brand-dot" /> Private Enclave Record
        </div>
      </div>

      <div className="identity">
        <span className="doc-icon large">
          <Icon name="file" size={22} />
        </span>
        <div>
          <h1>{document.filename}</h1>
          <p>
            <code>{documentId}</code>{" "}
            <button
              type="button"
              onClick={copyId}
              style={{
                background: "var(--surface-secondary)",
                border: "1px solid var(--line)",
                borderRadius: "4px",
                cursor: "pointer",
                padding: "2px 6px",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                fontSize: "11px",
                color: "var(--secondary)"
              }}
              title="Copy ID"
              aria-label="Copy document ID"
            >
              <Icon name="copy" size={12} />
              {copied ? <span style={{ color: "var(--success)", fontWeight: 600 }}>Copied!</span> : <span>Copy</span>}
            </button>{" "}
            {document.file_size ? (
              <>
                <i /> <code>{formatFileSize(document.file_size)}</code>
              </>
            ) : null}
            {document.uploaded_at ? (
              <>
                <i /> Uploaded {formatDate(document.uploaded_at)}
              </>
            ) : null}
          </p>
        </div>
        <Badge tone={approved ? "green" : document.status === "UPLOADED" ? undefined : "violet"}>
          {document.status}
        </Badge>
      </div>

      <div className="doc-actions">
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span className="eyebrow">CLASSIFIED AS</span>
          <span style={{ fontWeight: 600, color: "var(--ink)" }}>{categoryName}</span>
          <Badge tone={confidenceNum && confidenceNum >= 85 ? "green" : "amber"}>
            {confidenceNum !== null ? `${confidenceNum}% Confidence` : "Not evaluated"}
          </Badge>
        </div>
        <div>
          <Button
            variant="ghost"
            icon="refresh"
            disabled={rerunning}
            onClick={onRerunExtraction}
          >
            {rerunning ? "Re-running..." : "Re-run Extraction"}
          </Button>
          <Button variant="primary" icon="pencil" onClick={onOpenOverride}>
            Correct Classification
          </Button>
        </div>
      </div>
    </header>
  );
}
