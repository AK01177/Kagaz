"use client";

import React from "react";
import { Button, Badge, Icon } from "../../../components/AppShell";
import { DocumentRecord, formatFileSize } from "@/app/classification";
import { PolicyValidationRun } from "../types";

function DynamicDocumentStage({
  docType,
  filename,
  fields,
}: {
  docType: string;
  filename: string;
  fields: Record<string, string | number | string[]>;
}) {
  const typeLower = (docType || "").toLowerCase();

  // 1. Resume / Candidate Profile Renderer
  if (typeLower.includes("hr") || typeLower.includes("resume") || typeLower.includes("candidate")) {
    const candidate = fields["candidate_name"] || fields["name"] || "Jane Doe";
    const email = fields["email"] || "jane.doe@example.com";
    const phone = fields["phone"] || "+1-555-0149";
    const skills = Array.isArray(fields["skills"])
      ? fields["skills"]
      : typeof fields["skills"] === "string"
      ? fields["skills"].split(",")
      : ["Python", "FastAPI", "React", "TypeScript", "SQL"];

    return (
      <div className="invoice-paper" style={{ padding: "32px 28px", fontSize: "9px" }}>
        <div style={{ borderBottom: "1px solid var(--line2)", paddingBottom: "14px" }}>
          <b style={{ fontSize: "18px", color: "var(--ink)", display: "block" }}>{candidate}</b>
          <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: "8px" }}>
            {email} · {phone} · Austin, Texas
          </p>
        </div>
        <div style={{ marginTop: "16px" }}>
          <b style={{ display: "block", fontSize: "10px", color: "var(--ink)", marginBottom: "6px" }}>
            PROFESSIONAL COMPETENCIES
          </b>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
            {skills.map((s: string) => (
              <span
                key={s}
                style={{
                  background: "var(--side)",
                  border: "1px solid var(--line2)",
                  padding: "3px 7px",
                  borderRadius: "3px",
                  fontSize: "8px",
                }}
              >
                {s.trim()}
              </span>
            ))}
          </div>
        </div>
        <div style={{ marginTop: "18px" }}>
          <b style={{ display: "block", fontSize: "10px", color: "var(--ink)", marginBottom: "4px" }}>
            ACCREDITED EXPERIENCE
          </b>
          <p style={{ margin: 0, lineHeight: 1.6, color: "var(--body)" }}>
            Senior Software Architect · Acme Dynamics · 2021 – Present<br />
            Full-stack document pipeline &amp; distributed async message broker.
          </p>
        </div>
        <div className="annotation" style={{ left: "24px", top: "28px", width: "160px", height: "24px" }} />
        <div className="annotation" style={{ left: "24px", top: "85px", width: "280px", height: "35px" }} />
      </div>
    );
  }

  // 2. Receipt / Travel Expense Renderer
  if (typeLower.includes("receipt") || typeLower.includes("expense")) {
    const merchant = String(fields["supplier_name"] || fields["merchant"] || "Skyline Business Hotel");
    const total = fields["total_amount"] || fields["total"] || "$286.50";
    const date = String(fields["invoice_date"] || fields["date"] || "2024-08-28");

    return (
      <div className="receipt-paper" style={{ transform: "none", margin: "auto" }}>
        <b>{merchant.toUpperCase()}</b>
        <small>AUTHENTICATED RECEIPT ARCHIVE</small>
        <hr />
        <p>
          DATE <span>{date}</span><br />
          FILE <span>{filename}</span><br />
          STATUS <span>VERIFIED</span>
        </p>
        <hr />
        <strong>
          TOTAL CHARGED <span>{typeof total === "number" ? `$${total.toLocaleString()}` : total}</span>
        </strong>
        <small>EXTRACTED DOCUMENT FIELDS</small>
        <div className="uncertain" style={{ top: "115px", right: "14px", width: "120px", height: "16px" }} />
      </div>
    );
  }

  // 3. Invoice Renderer (Default Commercial Invoice)
  const supplier = String(fields["supplier_name"] || fields["vendor"] || "Ad4tech Material LLC");
  const invoiceNo = String(fields["invoice_number"] || fields["invoice_no"] || "INV-2024-9821");
  const invoiceDate = String(fields["invoice_date"] || fields["date"] || "2024-09-24");
  const total = fields["total_amount"] || fields["total"] || "$1,564.00";

  return (
    <div className="invoice-paper">
      <div className="invoice-top">
        <div>
          <b>{supplier.split(" ")[0].toLowerCase()}</b>
          <small>MATERIAL SOLUTIONS &amp; SUPPLY</small>
        </div>
        <h3>Invoice</h3>
      </div>
      <hr />
      <div className="invoice-cols">
        <div>
          <small>ISSUED BY</small>
          <b>{supplier}</b>
          <p>
            1200 Industrial Parkway<br />
            Austin, TX 78758, United States<br />
            Tax ID: US-84-7629103
          </p>
        </div>
        <div>
          <small>INVOICE NUMBER</small>
          <code>{invoiceNo}</code>
          <p>
            Issued: {invoiceDate}<br />
            Due: Net 30
          </p>
        </div>
      </div>
      <div className="bill">
        <small>BILL TO</small>
        <b>Acme Global Enterprise</b>
        <p>
          Finance &amp; Procurement Department<br />
          450 Mission Street, San Francisco, CA 94105
        </p>
      </div>
      <div className="mini-table">
        <b>
          DESCRIPTION <span>QTY &nbsp;&nbsp; RATE &nbsp;&nbsp; AMOUNT</span>
        </b>
        <p>
          Industrial material supply <span>12 &nbsp; $95.00 &nbsp; $1,140.00</span>
        </p>
        <p>
          Packaging &amp; handling <span>1 &nbsp; $240.00 &nbsp; $240.00</span>
        </p>
        <p>
          Freight &amp; delivery <span>1 &nbsp; $100.00 &nbsp; $100.00</span>
        </p>
      </div>
      <div className="invoice-total">
        <span>Payment terms: Net 30</span>
        <b>
          Total due &nbsp; <code>{typeof total === "number" ? `$${total.toLocaleString()}` : total}</code>
        </b>
      </div>
      <div className="annotation a1" />
      <div className="annotation a2" />
      <div className="annotation a3" />
    </div>
  );
}

interface OverviewTabProps {
  document: DocumentRecord;
  categoryName: string;
  fieldList: Array<{ key: string; val: string; conf: number | null }>;
  rawFieldsMap: Record<string, string | number | string[]>;
  ocrTextLength: number;
  isDemo: boolean;
  filePreviewUrl: string | null;
  filePreviewError: string | null;
  validationRun: PolicyValidationRun | null;
  onNavigateToValidation: () => void;
}

export function OverviewTab({
  document,
  categoryName,
  fieldList,
  rawFieldsMap,
  ocrTextLength,
  isDemo,
  filePreviewUrl,
  filePreviewError,
  validationRun,
  onNavigateToValidation,
}: OverviewTabProps) {
  return (
    <>
      {/* 4-Stage Connected Pipeline Tracker */}
      <div className="pipeline">
        <div className="stage">
          <span className="stage-dot">✓</span>
          <div>
            <b><code>01</code> Ingestion</b>
            <small>File received{document.file_size ? ` · ${formatFileSize(document.file_size)}` : ""}</small>
          </div>
          <i />
        </div>
        <div className="stage">
          <span className="stage-dot">{ocrTextLength > 0 ? "✓" : "!"}</span>
          <div>
            <b><code>02</code> OCR Extraction</b>
            <small>{ocrTextLength > 0 ? `${ocrTextLength.toLocaleString()} characters extracted` : "No OCR text recorded"}</small>
          </div>
          <i />
        </div>
        <div className="stage">
          <span className="stage-dot">✓</span>
          <div>
            <b><code>03</code> Genre Classification</b>
            <small>{categoryName}</small>
          </div>
          <i />
        </div>
        <div className="stage current">
          <span className="stage-dot">●</span>
          <div>
            <b><code>04</code> Field Extraction</b>
            <small>{fieldList.length ? `${fieldList.length} extracted fields` : "No structured fields extracted"}</small>
          </div>
        </div>
      </div>

      <div className="inspector-grid">
        {/* Left: Source Document Canvas */}
        <section className="source-pane">
          <div className="pane-title">
            <span>SOURCE DOCUMENT</span>
            <code>{document.filename || "Source File"}</code>
          </div>
          <div className="viewer" style={{ minHeight: "720px", display: "flex", flexDirection: "column" }}>
            <div className="viewer-bar">
              <span>−　<code>100%</code>　＋　 |　 {isDemo ? "Annotated View" : "Original Source Preview"}</span>
              <a
                href={filePreviewUrl || undefined}
                target="_blank"
                rel="noreferrer"
                onClick={(event) => { if (!filePreviewUrl) event.preventDefault(); }}
                style={{ color: "var(--ink)", textDecoration: "none", fontSize: "11px", fontWeight: 500 }}
                title="Open raw file in new tab"
              >
                Open Full File ↗
              </a>
            </div>
            <div
              className="paper-stage"
              style={{
                padding: 0,
                flex: 1,
                display: "flex",
                width: "100%",
                height: "100%",
                background: "#fff",
                minHeight: "680px",
              }}
            >
              {isDemo ? (
                <DynamicDocumentStage
                  docType={categoryName}
                  filename={document.filename || "commercial_invoice_september.pdf"}
                  fields={rawFieldsMap}
                />
              ) : filePreviewError ? (
                <div style={{ margin: "auto", padding: "24px", color: "var(--muted)" }}>
                  Could not load preview: {filePreviewError}
                </div>
              ) : !filePreviewUrl ? (
                <div style={{ margin: "auto", padding: "24px", color: "var(--muted)" }}>
                  Loading source document…
                </div>
              ) : (document.filename || "").match(/\.(png|jpg|jpeg|webp)$/i) ? (
                <div
                  style={{
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    width: "100%",
                    minHeight: "680px",
                    padding: "16px",
                    background: "#fbfbf9",
                  }}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={filePreviewUrl}
                    alt={document.filename || "Source Document"}
                    style={{
                      maxWidth: "100%",
                      maxHeight: "700px",
                      objectFit: "contain",
                      borderRadius: "4px",
                      boxShadow: "0 2px 8px rgba(0,0,0,0.12)",
                    }}
                  />
                </div>
              ) : (
                <iframe
                  src={`${filePreviewUrl}#toolbar=0`}
                  title={document.filename || "Source Document"}
                  style={{
                    width: "100%",
                    minHeight: "720px",
                    height: "100%",
                    border: "none",
                    borderRadius: "4px",
                    backgroundColor: "#fff",
                  }}
                />
              )}
            </div>
          </div>
          <p className="legend">
            <i /> Actual source document rendered directly from archival storage.
          </p>
        </section>

        {/* Right: AI Extracted Fields & Quick Policy Clearance */}
        <section className="fields-pane">
          <div className="pane-title">
            <span>AI EXTRACTED FIELDS</span>
            <code>LLM + RAPIDOCR</code>
          </div>
          <div className="field-grid">
            {fieldList.map((f) => (
              <div className="field-card" key={f.key}>
                <span>{f.key}</span>
                <strong>{f.val}</strong>
                <div>
                  <small>Extraction confidence</small>
                  <code>{f.conf == null ? "—" : `${f.conf}%`}</code>
                </div>
                <div className="confidence-track">
                  <i style={{ width: `${f.conf ?? 0}%` }} />
                </div>
              </div>
            ))}
            {fieldList.length === 0 && (
              <p style={{ color: "var(--muted)", fontSize: "12px", padding: "12px" }}>
                No structured fields are available for this document yet. Choose “Re-run Extraction” to retry.
              </p>
            )}
          </div>

          {/* Policy Clearance Card */}
          <div className="policy-card">
            <div>
              <Icon name="shield" />
              <b>Policy Compliance Summary</b>
              <Badge tone={validationRun?.status === "PASS" ? "green" : validationRun?.status === "FAIL" ? "red" : "amber"}>
                {validationRun?.status || "NOT RUN"}
              </Badge>
            </div>
            <p>
              {validationRun?.summary ||
                "No policy validation run is available for this document yet."}
            </p>
            <div style={{ marginTop: "14px" }}>
              <Button variant="ghost" onClick={onNavigateToValidation}>
                View Detailed Policy Findings &amp; Citations →
              </Button>
            </div>
          </div>

          <p className="audit-note">
            ⓘ Compare extracted fields with the source file. Use the review workflow to record comments or submit the document for approval.
          </p>
        </section>
      </div>
    </>
  );
}
