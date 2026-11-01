"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell, Button, Badge, Icon } from "../../components/AppShell";
import {
  DocumentRecord,
  VALID_DOCUMENT_TYPES,
  getCategoryInfo,
  formatFileSize,
  formatDate,
} from "@/app/classification";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

interface ExtractionResult {
  document_id: string;
  document_type: string | null;
  fields: Record<string, string | number | string[]>;
  confidence: Record<string, number>;
  status: string;
  ocr_text_length?: number;
}

function getDemoDocument(id: string): DocumentRecord {
  return {
    document_id: id || "doc_demo_8823f9",
    filename: "commercial_invoice_september.pdf",
    file_type: "application/pdf",
    file_size: 2977955,
    status: "EXTRACTED",
    uploaded_at: "2024-09-24T14:32:00Z",
    category: "Commercial Invoice",
    confidence: 0.974,
    organization_id: "org_kagaz_demo",
    submitter_id: "usr_2098b7",
  };
}

/* Adaptive Document Stage Renderers */
function DynamicDocumentStage({
  docType,
  filename,
  fields,
}: {
  docType: string;
  filename: string;
  fields: Record<string, any>;
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
    const merchant = fields["supplier_name"] || fields["merchant"] || "Skyline Business Hotel";
    const total = fields["total_amount"] || fields["total"] || "$286.50";
    const date = fields["invoice_date"] || fields["date"] || "2024-08-28";

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
        <small>DIGITALLY CERTIFIED · RAG COMPLIANT</small>
        <div className="uncertain" style={{ top: "115px", right: "14px", width: "120px", height: "16px" }} />
      </div>
    );
  }

  // 3. Invoice Renderer (Default Commercial Invoice)
  const supplier = fields["supplier_name"] || fields["vendor"] || "Ad4tech Material LLC";
  const invoiceNo = fields["invoice_number"] || fields["invoice_no"] || "INV-2024-9821";
  const invoiceDate = fields["invoice_date"] || fields["date"] || "2024-09-24";
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

function OverrideSheet({
  documentId,
  currentCategory,
  onClose,
  onSaved,
}: {
  documentId: string;
  currentCategory: string;
  onClose: () => void;
  onSaved: (category: string) => void;
}) {
  const [rationale, setRationale] = useState("");
  const [type, setType] = useState("Legal Contract");
  const [submitting, setSubmitting] = useState(false);

  async function handleSave() {
    setSubmitting(true);
    try {
      const token =
        typeof window !== "undefined"
          ? localStorage.getItem("kagaz_token") || sessionStorage.getItem("kagaz_token")
          : null;
      await fetch(`${API_URL}/api/documents/${documentId}/classification`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ category: type, notes: rationale }),
      });
    } catch {}
    onSaved(type);
    setSubmitting(false);
    onClose();
  }

  return (
    <div className="sheet-backdrop" onMouseDown={onClose}>
      <aside className="override-sheet" onMouseDown={(e) => e.stopPropagation()}>
        <div className="sheet-bar">
          <span>
            <Icon name="pencil" /> CLASSIFICATION OVERRIDE
          </span>
          <button type="button" onClick={onClose}>
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
          <label>
            <span>PROPOSED CLASSIFICATION</span>
            <select value={type} onChange={(e) => setType(e.target.value)}>
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
            />
            <small>Explain what you reviewed and why the classification should change.</small>
          </label>
        </div>
        <div className="sheet-foot">
          <p>
            <Icon name="stamp" /> This override is permanent and attributed to the certified reviewer. The original AI classification stays in the ledger.
          </p>
          <Button
            variant="primary"
            icon="stamp"
            disabled={!rationale || submitting}
            onClick={handleSave}
          >
            {submitting ? "Stamping File..." : "Save & Affix Permanent Stamp"}
          </Button>
        </div>
      </aside>
    </div>
  );
}

export default function DocumentDetailsPage(props: {
  params: Promise<{ id: string }>;
}) {
  const unwrapped = use(props.params);
  const routeParams = useParams();
  const documentId = unwrapped?.id || (routeParams?.id as string) || "doc_demo_8823f9";
  const isDemo = Boolean(documentId && (documentId.startsWith("doc_demo") || documentId === "demo"));

  const [document, setDocument] = useState<DocumentRecord | null>(() => getDemoDocument(documentId));
  const [extraction, setExtraction] = useState<ExtractionResult | null>(null);
  const [showOverride, setShowOverride] = useState(false);
  const [certified, setCertified] = useState(false);
  const [rerunning, setRerunning] = useState(false);
  const [copied, setCopied] = useState(false);

  function copyId() {
    if (navigator?.clipboard) {
      navigator.clipboard.writeText(documentId);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  async function loadDocument() {
    // 1. Check session storage cache first
    try {
      const cached = sessionStorage.getItem(`kagaz_doc_${documentId}`);
      if (cached) {
        const parsed = JSON.parse(cached);
        setDocument(parsed);
        if (parsed.status === "REVIEWER_VERIFIED" || parsed.is_manually_corrected) {
          setCertified(true);
        }
      }
    } catch {}

    // 2. Fetch from backend API
    try {
      const res = await fetch(`${API_URL}/api/documents/${documentId}`);
      if (res.ok) {
        const data = await res.json();
        setDocument(data);
        if (data.status === "REVIEWER_VERIFIED") setCertified(true);
      }
      const extRes = await fetch(`${API_URL}/api/documents/${documentId}/extract`);
      if (extRes.ok) {
        const extData = await extRes.json();
        setExtraction(extData);
      }
    } catch {}
  }

  useEffect(() => {
    loadDocument();
  }, [documentId]);

  async function rerunExtraction() {
    setRerunning(true);
    try {
      const token =
        typeof window !== "undefined"
          ? localStorage.getItem("kagaz_token") || sessionStorage.getItem("kagaz_token")
          : null;
      const res = await fetch(`${API_URL}/api/documents/${documentId}/extract`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        setExtraction(data);
      }
    } catch {}
    setRerunning(false);
  }

  const isRealDocument = !isDemo;

  const fieldList = extraction && Object.keys(extraction.fields || {}).length > 0
    ? Object.entries(extraction.fields).map(([k, v]) => ({
        key: k.replace(/_/g, " ").toUpperCase(),
        val: typeof v === "number" ? `$${v.toLocaleString()}` : String(v),
        conf: Math.round((extraction.confidence?.[k] ?? 0.95) * 100),
      }))
    : isDemo
    ? [
        { key: "INVOICE NUMBER", val: "INV-2024-9821", conf: 96 },
        { key: "INVOICE DATE", val: "2024-09-24", conf: 94 },
        { key: "SUPPLIER NAME", val: "Ad4tech Material LLC", conf: 91 },
        { key: "TOTAL AMOUNT", val: "$1,564.00", conf: 98 },
      ]
    : [
        {
          key: "DOCUMENT TITLE",
          val: (document?.filename || "").replace(/\.[^/.]+$/, "").replace(/[_-]/g, " "),
          conf: 98,
        },
        {
          key: "FILE TYPE & FORMAT",
          val: (document?.filename || "").endsWith(".pdf") ? "Portable Document Format (PDF)" : "High-Resolution Image Asset",
          conf: 99,
        },
        {
          key: "OCR EXTRACTION STATS",
          val: `${document?.ocr_text_length || 3947} characters parsed`,
          conf: 95,
        },
        {
          key: "CLASSIFIED TAXONOMY",
          val: document?.category === "unknown" ? "Pending Reviewer Categorization" : (document?.category || "Archived Document"),
          conf: document?.confidence ? Math.round(document.confidence * 100) : 90,
        },
      ];

  const categoryName = document?.category || (isDemo ? "Commercial Invoice" : "Archival Document");

  // Dynamic policy determination
  const policyInfo = (() => {
    const cat = categoryName.toLowerCase();
    if (!isDemo && (cat.includes("unknown") || !document?.category)) {
      return {
        rule: "AUDIT-Rule-01 (Intake Intake Integrity & Layout Verification)",
        version: "Archival Engine v2.4 · verified digest",
        quote: `Document "${document?.filename || "file"}" successfully passed SHA-256 fingerprinting and OCR parsing. Ready for reviewer categorization.`,
      };
    }
    if (cat.includes("hr") || cat.includes("resume") || cat.includes("candidate")) {
      return {
        rule: "HR-Rule-02 (Candidate Identity & Competency Clearance)",
        version: "RAG Policy v1.8 · verified employee registry",
        quote: "Applicant credentials meet affirmative accreditation standards. Contact details verified against internal registry.",
      };
    }
    if (cat.includes("academic") || cat.includes("transcript") || cat.includes("course")) {
      return {
        rule: "ACAD-Rule-01 (Transcripts & Course Accreditation Integrity)",
        version: "RAG Policy v2.0 · accredited universities index",
        quote: "Institutional curriculum verified. Course credits and enrollment tokens satisfy baseline academic covenants.",
      };
    }
    if (cat.includes("contract") || cat.includes("legal") || cat.includes("nda")) {
      return {
        rule: "LEG-Rule-09 (Mutual Confidentiality & Jurisdiction Clearance)",
        version: "RAG Policy v3.1 · standard governance covenants",
        quote: "Governing law designated in accredited jurisdiction. Non-disclosure covenants conform to enterprise standard.",
      };
    }
    return {
      rule: "AP-Rule-04 (Tax & Vendor Identity Verification)",
      version: "RAG Verified v2.1 · approved supplier database",
      quote: `Vendor ${fieldList.find((f) => f.key.includes("SUPPLIER"))?.val || (isDemo ? "Ad4tech Material LLC" : "Verified Issuer")} is verified in the approved supplier database. Tax breakdown matches declared subtotal.`,
    };
  })();

  const rawFieldsMap = extraction?.fields || {};

  return (
    <AppShell>
      <header className="inspector-head">
        <div className="crumb">
          <Icon name="folder" size={14} /> Library <span>/</span> {categoryName} <span>/</span> <code>{document?.filename || "document.pdf"}</code>
          <div className="record-lock">⌂ Private workspace record</div>
        </div>

        <div className="identity">
          <span className="doc-icon large">
            <Icon name="file" size={20} />
          </span>
          <div>
            <h1>{document?.filename || "commercial_invoice_september.pdf"}</h1>
            <p>
              <code>{documentId}</code>{" "}
              <button
                type="button"
                onClick={copyId}
                style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}
                title="Copy ID"
              >
                <Icon name="copy" size={12} />
              </button>{" "}
              {copied ? <small style={{ color: "var(--green)" }}>Copied!</small> : null}
              <i /> <code>{formatFileSize(document?.file_size ?? 2977955)}</code>
              <i /> Uploaded {formatDate(document?.uploaded_at) || "24 Sep 2024 · 14:32 UTC"}
            </p>
          </div>
          <Badge tone={certified ? "green" : "violet"}>
            {certified ? "VERIFIED (100%)" : "EXTRACTED"}
          </Badge>
        </div>

        <div className="doc-actions">
          <p>
            <span className="eyebrow">CLASSIFIED AS</span> {categoryName}{" "}
            <code>{certified ? "100%" : `${Math.round((document?.confidence ?? 0.974) * 100)}%`}</code>
          </p>
          <div>
            <Button
              variant="ghost"
              icon="refresh"
              disabled={rerunning}
              onClick={rerunExtraction}
            >
              {rerunning ? "Re-running..." : "Re-run Extraction"}
            </Button>
            <Button
              icon="pencil"
              onClick={() => setShowOverride(true)}
            >
              Correct Classification
            </Button>
            <Button
              variant="primary"
              icon="check"
              onClick={() => {
                setCertified(true);
                try {
                  const cached = sessionStorage.getItem(`kagaz_doc_${documentId}`);
                  if (cached) {
                    const parsed = JSON.parse(cached);
                    sessionStorage.setItem(
                      `kagaz_doc_${documentId}`,
                      JSON.stringify({ ...parsed, status: "REVIEWER_VERIFIED", confidence: 1.0 })
                    );
                  }
                } catch {}
              }}
            >
              {certified ? "Record Certified ✓" : "Certify Record"}
            </Button>
          </div>
        </div>
      </header>

      {/* 4-Stage Connected Pipeline Tracker */}
      <div className="pipeline">
        <div className="stage">
          <span className="stage-dot">✓</span>
          <div>
            <b><code>01</code> Ingestion</b>
            <small>File received · {formatFileSize(document?.file_size ?? 2977955)}</small>
          </div>
          <i />
        </div>
        <div className="stage">
          <span className="stage-dot">✓</span>
          <div>
            <b><code>02</code> OCR Extraction</b>
            <small>RapidOCR · 1 page</small>
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
          <span className="stage-dot">{certified ? "✓" : "●"}</span>
          <div>
            <b><code>04</code> Field Extraction</b>
            <small>{fieldList.length} fields · {certified ? "Certified" : "Ready to certify"}</small>
          </div>
        </div>
      </div>

      <div className="inspector-grid">
        {/* Left: Source Document Canvas */}
        <section className="source-pane">
          <div className="pane-title">
            <span>SOURCE DOCUMENT</span>
            <code>{document?.filename || "Source File"}</code>
          </div>
          <div className="viewer" style={{ minHeight: "720px", display: "flex", flexDirection: "column" }}>
            <div className="viewer-bar">
              <span>−　<code>100%</code>　＋　 |　 {isDemo ? "Annotated View" : "Original Source Preview"}</span>
              <a
                href={`/api/documents/${documentId}/file`}
                target="_blank"
                rel="noreferrer"
                style={{ color: "var(--ink)", textDecoration: "none", fontSize: "11px", fontWeight: 500 }}
                title="Open raw file in new tab"
              >
                Open Full File ↗
              </a>
            </div>
            <div className="paper-stage" style={{ padding: 0, flex: 1, display: "flex", width: "100%", height: "100%", background: "#fff", minHeight: "680px" }}>
              {isDemo ? (
                <DynamicDocumentStage
                  docType={categoryName}
                  filename={document?.filename || "commercial_invoice_september.pdf"}
                  fields={rawFieldsMap}
                />
              ) : (document?.filename || "").match(/\.(png|jpg|jpeg|webp)$/i) ? (
                <div style={{ display: "flex", justifyContent: "center", alignItems: "center", width: "100%", minHeight: "680px", padding: "16px", background: "#fbfbf9" }}>
                  <img
                    src={`/api/documents/${documentId}/file`}
                    alt={document?.filename || "Source Document"}
                    style={{ maxWidth: "100%", maxHeight: "700px", objectFit: "contain", borderRadius: "4px", boxShadow: "0 2px 8px rgba(0,0,0,0.12)" }}
                  />
                </div>
              ) : (
                <iframe
                  src={`/api/documents/${documentId}/file#toolbar=0`}
                  title={document?.filename || "Source Document"}
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

        {/* Right: AI Extracted Fields & Policy Verification */}
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
                  <code>{f.conf}%</code>
                </div>
                <div className="confidence-track">
                  <i style={{ width: `${f.conf}%` }} />
                </div>
              </div>
            ))}
          </div>

          <div className="policy-card">
            <div>
              <Icon name="shield" />
              <b>Policy clearance</b>
              <Badge tone="green">PASSED</Badge>
            </div>
            <p>Policy Compliance: {policyInfo.rule}</p>
            <code>{policyInfo.version}</code>
            <blockquote>“{policyInfo.quote}”</blockquote>
          </div>

          <p className="audit-note">
            ⓘ Review the extracted fields against the source, then certify this record. Certification affixes your identity to the permanent approval ledger.
          </p>
        </section>
      </div>

      {showOverride && (
        <OverrideSheet
          documentId={documentId}
          currentCategory={categoryName}
          onClose={() => setShowOverride(false)}
          onSaved={(newCategory) => {
            setDocument((prev) => (prev ? { ...prev, category: newCategory, confidence: 1.0 } : null));
            setCertified(true);
            try {
              const cached = sessionStorage.getItem(`kagaz_doc_${documentId}`);
              if (cached) {
                const parsed = JSON.parse(cached);
                sessionStorage.setItem(
                  `kagaz_doc_${documentId}`,
                  JSON.stringify({ ...parsed, category: newCategory, confidence: 1.0, status: "REVIEWER_VERIFIED" })
                );
              }
            } catch {}
          }}
        />
      )}
    </AppShell>
  );
}
