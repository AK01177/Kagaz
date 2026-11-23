"use client";

import React from "react";
import { Button, Badge, Icon } from "../../../../components/AppShell";
import { PolicyValidationRun, PolicyValidationFinding } from "../types";

interface PolicyValidationTabProps {
  validationRun: PolicyValidationRun | null;
  validating: boolean;
  validationError: string | null;
  onRunValidation: () => void;
}

export function PolicyValidationTab({
  validationRun,
  validating,
  validationError,
  onRunValidation,
}: PolicyValidationTabProps) {
  const violationFindings: PolicyValidationFinding[] = (validationRun?.findings || []).filter(
    (f) => f.status === "FAIL"
  );
  const uncertaintyFindings: PolicyValidationFinding[] = (validationRun?.findings || []).filter(
    (f) => f.status === "NEEDS_HUMAN_REVIEW" || f.status === "FLAG" || f.status === "MISSING_INFORMATION"
  );
  const passedFindings: PolicyValidationFinding[] = (validationRun?.findings || []).filter(
    (f) => f.status === "PASS"
  );

  return (
    <div className="validation-view">
      {/* Header Action Banner */}
      <div className="validation-header-banner">
        <div className="val-summary-text">
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "4px" }}>
            <span
              style={{
                font: "10px 'Inter', sans-serif",
                fontWeight: 700,
                color: "var(--muted)",
                textTransform: "uppercase",
                letterSpacing: "0.8px",
              }}
            >
              POLICY VALIDATION RUN
            </span>
            {validationRun && (
              <Badge
                tone={
                  validationRun.status === "PASS"
                    ? "green"
                    : validationRun.status === "FAIL"
                    ? "red"
                    : "amber"
                }
              >
                {validationRun.status}
              </Badge>
            )}
          </div>
          <h3>
            {validationRun
              ? `Evaluated against ${validationRun.policy_versions.length || 1} active governance policy`
              : "No policy validation executed yet"}
          </h3>
          <p>
            {validationRun?.summary ||
              "Execute automated rule verification against ingested policy documents to evaluate compliance, detect violations, and flag missing criteria."}
          </p>
          {validationRun?.policy_versions && validationRun.policy_versions.length > 0 && (
            <div style={{ display: "flex", gap: "6px", marginTop: "10px", flexWrap: "wrap" }}>
              {validationRun.policy_versions.map((pv, idx) => (
                <span
                  key={idx}
                  style={{
                    fontSize: "10px",
                    background: "var(--bg)",
                    border: "1px solid var(--line)",
                    padding: "2px 8px",
                    borderRadius: "4px",
                    color: "var(--muted)",
                  }}
                >
                  📜 {pv.policy_name || "Policy"} · v{pv.version || "1.0"} ({pv.domain || "general"})
                </span>
              ))}
            </div>
          )}
        </div>

        <div>
          <Button
            variant="primary"
            icon="shield"
            disabled={validating}
            onClick={onRunValidation}
          >
            {validating ? "Validating Policies..." : "Run Policy Validation"}
          </Button>
        </div>
      </div>

      {validationError && (
        <div
          style={{
            background: "var(--red-bg)",
            border: "1px solid rgba(184, 75, 75, 0.3)",
            padding: "12px 16px",
            borderRadius: "6px",
            color: "var(--red)",
            fontSize: "11px",
          }}
        >
          ⚠ {validationError}
        </div>
      )}

      {/* Empty / No-Policy State */}
      {!validationRun && !validating && (
        <div
          style={{
            background: "white",
            border: "1px dashed var(--line2)",
            borderRadius: "8px",
            padding: "48px 24px",
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "12px",
          }}
        >
          <div
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "50%",
              background: "var(--violet-bg)",
              display: "grid",
              placeItems: "center",
              color: "var(--violet)",
            }}
          >
            <Icon name="shield" size={24} />
          </div>
          <h3 style={{ margin: 0, fontSize: "16px", color: "var(--ink)" }}>
            No Policy Findings Recorded
          </h3>
          <p style={{ margin: 0, maxWidth: "480px", color: "var(--muted)", fontSize: "12px", lineHeight: 1.6 }}>
            Click &ldquo;Run Policy Validation&rdquo; to evaluate extracted document fields against organizational covenants and generate verified compliance findings with citations.
          </p>
          <Button variant="primary" icon="shield" onClick={onRunValidation}>
            Run Policy Validation Now
          </Button>
        </div>
      )}

      {/* GROUP 1: Confirmed Violations (FAIL) */}
      {violationFindings.length > 0 && (
        <div>
          <div className="findings-section-title">
            <h4 style={{ color: "var(--red)" }}>
              Confirmed Policy Violations ({violationFindings.length})
            </h4>
            <Badge tone="red">CRITICAL BREACH</Badge>
          </div>
          <div className="findings-cards-list">
            {violationFindings.map((finding) => (
              <div className="finding-box fail" key={finding.id}>
                <div className="finding-top-row">
                  <span className="finding-req-title">{finding.requirement}</span>
                  <Badge tone="red">VIOLATION</Badge>
                </div>

                <p style={{ margin: "4px 0", fontSize: "12px", color: "var(--body)", lineHeight: 1.5 }}>
                  {finding.explanation}
                </p>

                {(finding.field_name || finding.document_value) && (
                  <div className="finding-meta-pills">
                    {finding.field_name && (
                      <span className="field-val-pill">
                        Field: <code>{finding.field_name}</code>
                      </span>
                    )}
                    {finding.document_value && (
                      <span className="field-val-pill">
                        Observed Value: <code>{finding.document_value}</code>
                      </span>
                    )}
                  </div>
                )}

                {finding.sources && finding.sources.length > 0 && (
                  <div className="citation-container">
                    <b>Policy Source Reference &amp; Covenants</b>
                    {finding.sources.map((src, sIdx) => (
                      <div key={sIdx} style={{ marginBottom: "6px" }}>
                        <span style={{ fontSize: "10px", color: "var(--muted)", fontWeight: 600 }}>
                          {src.policy_name || "Governance Standard"}{" "}
                          {src.policy_version ? `(v${src.policy_version})` : ""}{" "}
                          {src.section ? `· ${src.section}` : ""}{" "}
                          {src.page_number ? `· p.${src.page_number}` : ""}
                        </span>
                        <blockquote>&ldquo;{src.supporting_quote || src.excerpt}&rdquo;</blockquote>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* GROUP 2: Missing Information & Uncertainties (NEEDS_HUMAN_REVIEW, FLAG) */}
      {uncertaintyFindings.length > 0 && (
        <div>
          <div className="findings-section-title">
            <h4 style={{ color: "var(--amber)" }}>
              Missing Information &amp; Human Review Required ({uncertaintyFindings.length})
            </h4>
            <Badge tone="amber">ACTION REQUIRED</Badge>
          </div>
          <div className="findings-cards-list">
            {uncertaintyFindings.map((finding) => (
              <div className="finding-box uncertain" key={finding.id}>
                <div className="finding-top-row">
                  <span className="finding-req-title">{finding.requirement}</span>
                  <Badge tone="amber">
                    {finding.status === "MISSING_INFORMATION"
                      ? "MISSING DATA"
                      : "NEEDS HUMAN REVIEW"}
                  </Badge>
                </div>

                <p style={{ margin: "4px 0", fontSize: "12px", color: "var(--body)", lineHeight: 1.5 }}>
                  {finding.explanation}
                </p>

                {(finding.field_name || finding.document_value) && (
                  <div className="finding-meta-pills">
                    {finding.field_name && (
                      <span className="field-val-pill">
                        Target Field: <code>{finding.field_name}</code>
                      </span>
                    )}
                    {finding.document_value ? (
                      <span className="field-val-pill">
                        Current Value: <code>{finding.document_value}</code>
                      </span>
                    ) : (
                      <span className="field-val-pill" style={{ color: "var(--amber)" }}>
                        Value Not Detected
                      </span>
                    )}
                  </div>
                )}

                {finding.sources && finding.sources.length > 0 && (
                  <div className="citation-container">
                    <b>Regulatory Requirement Citation</b>
                    {finding.sources.map((src, sIdx) => (
                      <div key={sIdx} style={{ marginBottom: "6px" }}>
                        <span style={{ fontSize: "10px", color: "var(--muted)", fontWeight: 600 }}>
                          {src.policy_name || "Governance Standard"}{" "}
                          {src.policy_version ? `(v${src.policy_version})` : ""}{" "}
                          {src.section ? `· ${src.section}` : ""}
                        </span>
                        <blockquote>&ldquo;{src.supporting_quote || src.excerpt}&rdquo;</blockquote>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* GROUP 3: Satisfied Requirements (PASS) */}
      {passedFindings.length > 0 && (
        <div>
          <div className="findings-section-title">
            <h4 style={{ color: "var(--green)" }}>
              Cleared Compliance Requirements ({passedFindings.length})
            </h4>
            <Badge tone="green">PASSED</Badge>
          </div>
          <div className="findings-cards-list">
            {passedFindings.map((finding) => (
              <div className="finding-box pass" key={finding.id}>
                <div className="finding-top-row">
                  <span className="finding-req-title">{finding.requirement}</span>
                  <Badge tone="green">CLEARED</Badge>
                </div>

                <p style={{ margin: "4px 0", fontSize: "12px", color: "var(--body)", lineHeight: 1.5 }}>
                  {finding.explanation}
                </p>

                {(finding.field_name || finding.document_value) && (
                  <div className="finding-meta-pills">
                    {finding.field_name && (
                      <span className="field-val-pill">
                        Field: <code>{finding.field_name}</code>
                      </span>
                    )}
                    {finding.document_value && (
                      <span className="field-val-pill">
                        Verified: <code>{finding.document_value}</code>
                      </span>
                    )}
                  </div>
                )}

                {finding.sources && finding.sources.length > 0 && (
                  <div className="citation-container">
                    <b>Verified Policy Covenant</b>
                    {finding.sources.map((src, sIdx) => (
                      <div key={sIdx}>
                        <span style={{ fontSize: "10px", color: "var(--muted)", fontWeight: 600 }}>
                          {src.policy_name || "Enterprise Rule"}{" "}
                          {src.policy_version ? `(v${src.policy_version})` : ""}{" "}
                          {src.section ? `· ${src.section}` : ""}
                        </span>
                        <blockquote>&ldquo;{src.supporting_quote || src.excerpt}&rdquo;</blockquote>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
