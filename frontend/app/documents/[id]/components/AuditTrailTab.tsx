"use client";

import React from "react";
import { Button } from "../../../components/AppShell";
import { formatDate } from "@/app/classification";
import { AuditEvent } from "../types";

interface AuditTrailTabProps {
  auditEvents: AuditEvent[];
  loadingAudit: boolean;
  onRefreshAudit: () => void;
}

export function AuditTrailTab({
  auditEvents,
  loadingAudit,
  onRefreshAudit,
}: AuditTrailTabProps) {
  return (
    <div className="audit-timeline-container">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          background: "white",
          padding: "16px 20px",
          border: "1px solid var(--line)",
          borderRadius: "8px",
        }}
      >
        <div>
          <h3 style={{ margin: "0 0 4px", fontSize: "15px", fontWeight: 600, color: "var(--ink)" }}>
            Permanent Action History &amp; Audit Trail
          </h3>
          <p style={{ margin: 0, fontSize: "11px", color: "var(--muted)" }}>
            Immutable ledger of all transitions, classification overrides, reviewer certifications, and validation runs.
          </p>
        </div>
        <Button
          variant="ghost"
          icon="refresh"
          disabled={loadingAudit}
          onClick={onRefreshAudit}
        >
          {loadingAudit ? "Refreshing..." : "Refresh Trail"}
        </Button>
      </div>

      {auditEvents.length === 0 ? (
        <div
          style={{
            background: "white",
            border: "1px dashed var(--line2)",
            borderRadius: "8px",
            padding: "40px",
            textAlign: "center",
            color: "var(--muted)",
            fontSize: "12px",
          }}
        >
          No audit trail events recorded yet for this document.
        </div>
      ) : (
        <div className="audit-list">
          {auditEvents.map((evt) => (
            <div className="audit-item" key={evt.id}>
              <div className="audit-item-marker">✓</div>
              <div className="audit-item-card">
                <div className="audit-item-head">
                  <span className="audit-action-name">{evt.action}</span>
                  <div className="audit-item-meta">
                    <span>Actor: <code>{evt.actor_id || "system"}</code></span>
                    <span>·</span>
                    <span>{formatDate(evt.created_at) || evt.created_at}</span>
                  </div>
                </div>
                {evt.details && Object.keys(evt.details).length > 0 && (
                  <div
                    style={{
                      marginTop: "10px",
                      background: "var(--bg)",
                      border: "1px solid var(--line)",
                      borderRadius: "4px",
                      padding: "8px 12px",
                      fontSize: "10px",
                      fontFamily: "'JetBrains Mono', monospace",
                      color: "var(--body)",
                      overflowX: "auto",
                    }}
                  >
                    <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                      {JSON.stringify(evt.details, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
