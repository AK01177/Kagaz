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

  return (
    <header className="inspector-head">
      <div className="crumb">
        <Icon name="folder" size={14} /> Library <span>/</span> {categoryName} <span>/</span>{" "}
        <code>{document.filename}</code>
        <div className="record-lock">⌂ Private workspace record</div>
      </div>

      <div className="identity">
        <span className="doc-icon large">
          <Icon name="file" size={20} />
        </span>
        <div>
          <h1>{document.filename}</h1>
          <p>
            <code>{documentId}</code>{" "}
            <button
              type="button"
              onClick={copyId}
              style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}
              title="Copy ID"
              aria-label="Copy document ID"
            >
              <Icon name="copy" size={12} />
            </button>{" "}
            {copied ? <small style={{ color: "var(--green)" }}>Copied!</small> : null}
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
        <p>
          <span className="eyebrow">CLASSIFIED AS</span> {categoryName}{" "}
          <code>
            {document.confidence !== null && document.confidence !== undefined
              ? `${Math.round(document.confidence * 100)}%`
              : "Not available"}
          </code>
        </p>
        <div>
          <Button
            variant="ghost"
            icon="refresh"
            disabled={rerunning}
            onClick={onRerunExtraction}
          >
            {rerunning ? "Re-running..." : "Re-run Extraction"}
          </Button>
          <Button icon="pencil" onClick={onOpenOverride}>
            Correct Classification
          </Button>
        </div>
      </div>
    </header>
  );
}
