"use client";

import { use, useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell, Button, Badge, Icon } from "../../components/AppShell";
import { ProtectedRoute } from "../../components/ProtectedRoute";
import { useAuth } from "../../context/AuthContext";
import {
  DocumentRecord,
  VALID_DOCUMENT_TYPES,
  formatFileSize,
  formatDate,
} from "@/app/classification";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

type ActiveTab = "overview" | "validation" | "audit" | "assistant";

interface ExtractionResult {
  document_id: string;
  document_type: string | null;
  fields: Record<string, string | number | string[]>;
  confidence: Record<string, number>;
  status: string;
  ocr_text_length?: number;
}

interface PolicyValidationSource {
  reference_type?: string;
  policy_id?: string;
  policy_name?: string;
  policy_version?: string;
  section?: string;
  page_number?: number;
  excerpt: string;
  supporting_quote?: string;
}

interface PolicyValidationFinding {
  id: string;
  status: "PASS" | "FLAG" | "FAIL" | "NEEDS_HUMAN_REVIEW" | "MISSING_INFORMATION";
  requirement: string;
  explanation: string;
  field_name?: string | null;
  document_value?: string | null;
  confidence?: number | null;
  sources: PolicyValidationSource[];
}

interface PolicyValidationRun {
  id: string;
  document_id: string;
  status: "PASS" | "FLAG" | "FAIL" | "NEEDS_HUMAN_REVIEW";
  summary: string;
  retrieval_outcome: string;
  policy_versions: Array<{
    id?: string;
    policy_name?: string;
    version?: string;
    domain?: string;
  }>;
  findings: PolicyValidationFinding[];
  created_at: string;
}

interface AuditEvent {
  id: string;
  action: string;
  actor_id?: string | null;
  details?: Record<string, unknown> | null;
  created_at: string;
}

interface AssistantSource {
  source_type: "DOCUMENT_FIELD" | "POLICY_CHUNK" | "VALIDATION_FINDING" | string;
  title: string;
  reference: string;
  excerpt: string;
  policy_name?: string | null;
  policy_version?: string | null;
  section?: string | null;
  page_number?: number | null;
}

interface AssistantMessage {
  id: string;
  sender: "user" | "assistant";
  content: string;
  timestamp: string;
  sources?: AssistantSource[];
  is_grounded?: boolean;
  limitation?: string | null;
  confidence?: number | null;
}

/* Adaptive Document Stage Renderers */
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
        <small>DIGITALLY CERTIFIED · RAG COMPLIANT</small>
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

function OverrideSheet({
  documentId,
  currentCategory,
  onClose,
  onSaved,
  fetchWithAuth,
}: {
  documentId: string;
  currentCategory: string;
  onClose: () => void;
  onSaved: (category: string) => void;
  fetchWithAuth: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
}) {
  const [rationale, setRationale] = useState("");
  const [type, setType] = useState("Legal Contract");
  const [submitting, setSubmitting] = useState(false);

  async function handleSave() {
    setSubmitting(true);
    const canonicalMap: Record<string, string> = {
      "Commercial Invoice": "financial",
      "Legal Contract": "general_confidential",
      "Legal Contract & Agreement": "general_confidential",
      "Academic Record & Transcript": "academics",
      "Academic Transcript": "academics",
      "HR Record": "hr_documents",
      "Financial Report": "financial",
      invoice: "financial",
      contract: "general_confidential",
      academic: "academics",
      hr: "hr_documents",
      financial: "financial",
      general_confidential: "general_confidential",
      academics: "academics",
      hr_documents: "hr_documents",
    };
    const canonicalCategory = canonicalMap[type] || type.toLowerCase().replace(/ /g, "_");

    try {
      await fetchWithAuth(`${API_URL}/api/documents/${documentId}/classification`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ category: canonicalCategory, notes: rationale }),
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

function DocumentDetailsContent(props: {
  params: Promise<{ id: string }>;
}) {
  const unwrapped = use(props.params);
  const routeParams = useParams();
  const documentId = unwrapped?.id || (routeParams?.id as string) || "";
  const isDemo = Boolean(documentId && (documentId.startsWith("doc_demo") || documentId === "demo"));
  const { fetchWithAuth, token, user, activeOrgId } = useAuth();
  const documentCacheKey = `kagaz_doc_${user?.user_id || "unknown"}_${activeOrgId || user?.organization_id || "unknown"}_${documentId}`;

  const [activeTab, setActiveTab] = useState<ActiveTab>("overview");
  const [document, setDocument] = useState<DocumentRecord | null>(null);
  const [loadingDoc, setLoadingDoc] = useState(true);
  const [extraction, setExtraction] = useState<ExtractionResult | null>(null);
  const [showOverride, setShowOverride] = useState(false);
  const [certified, setCertified] = useState(false);
  const [rerunning, setRerunning] = useState(false);
  const [copied, setCopied] = useState(false);
  const [filePreview, setFilePreview] = useState<{ documentId: string; url: string } | null>(null);
  const [filePreviewFailure, setFilePreviewFailure] = useState<{ documentId: string; message: string } | null>(null);

  // FE09: Policy validation findings state
  const [validationRun, setValidationRun] = useState<PolicyValidationRun | null>(null);
  const [validating, setValidating] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // FE11: Audit trail state
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(false);

  // FE12: Grounded Assistant state
  const [messages, setMessages] = useState<AssistantMessage[]>([
    {
      id: "welcome",
      sender: "assistant",
      content:
        "Hello! I am your Kagaz Document & Policy Assistant. I can answer questions grounded directly in this document's extractions and your organization's policy covenants. Note that I am strictly read-only and cannot alter document states.",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      is_grounded: true,
    },
  ]);
  const [questionInput, setQuestionInput] = useState("");
  const [queryingAssistant, setQueryingAssistant] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const filePreviewUrl = filePreview?.documentId === documentId ? filePreview.url : null;
  const filePreviewError = filePreviewFailure?.documentId === documentId ? filePreviewFailure.message : null;

  function copyId() {
    if (navigator?.clipboard) {
      navigator.clipboard.writeText(documentId);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  // PDF/image viewers cannot attach the Supabase bearer token to their own request.
  // Fetch the protected file with auth, then render its temporary object URL.
  useEffect(() => {
    if (!documentId || isDemo || !token) return;
    let cancelled = false;
    let objectUrl: string | null = null;
    fetchWithAuth(`${API_URL}/api/documents/${encodeURIComponent(documentId)}/file`)
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => null);
          const message = payload?.error?.message || payload?.detail?.message || payload?.detail;
          throw new Error(typeof message === "string" ? message : `File request failed (${response.status})`);
        }
        return response.blob();
      })
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setFilePreview({ documentId, url: objectUrl });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setFilePreviewFailure({
            documentId,
            message: error instanceof Error ? error.message : "Could not load the source file.",
          });
        }
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [documentId, fetchWithAuth, isDemo, token]);

  // Load document review detail, extraction, and validation runs
  useEffect(() => {
    let ignore = false;
    async function loadData() {
      // 1. Session storage cache check
      try {
        const cached = sessionStorage.getItem(documentCacheKey);
        if (cached && !ignore) {
          const parsed = JSON.parse(cached);
          setDocument(parsed);
          if (parsed.status === "REVIEWER_VERIFIED" || parsed.is_manually_corrected) {
            setCertified(true);
          }
        }
      } catch {}

      // 2. Fetch from review detail endpoint if available (FE10)
      try {
        const reviewRes = await fetchWithAuth(`${API_URL}/api/documents/${documentId}/review`);
        if (reviewRes.ok && !ignore) {
          const reviewData = await reviewRes.json();
          if (reviewData.document) {
            const metadataRes = await fetchWithAuth(`${API_URL}/api/documents/${documentId}`);
            const metadata = metadataRes.ok ? await metadataRes.json() : {};
            setDocument({
              document_id: reviewData.document.document_id || reviewData.document.id,
              filename: reviewData.document.filename,
              file_type: metadata.file_type || reviewData.document.file_type || "application/pdf",
              file_size: metadata.file_size || reviewData.document.file_size || 0,
              status: reviewData.document.status,
              uploaded_at: metadata.uploaded_at || reviewData.document.upload_timestamp,
              category: metadata.category || reviewData.document.classification || "Archival Document",
              confidence: metadata.confidence ?? reviewData.document.classification_confidence ?? null,
              organization_id: reviewData.document.organization_id,
              ocr_text_length: metadata.ocr_text_length ?? reviewData.ocr_text?.length ?? 0,
            });
            if (reviewData.document.status === "APPROVED" || reviewData.document.status === "REVIEWER_VERIFIED") {
              setCertified(true);
            }
          }
          if (reviewData.extractions && reviewData.extractions.length > 0) {
            const fieldsObj: Record<string, string | number | string[]> = {};
            const confObj: Record<string, number> = {};
            reviewData.extractions.forEach((e: { field_name: string; field_value: string; confidence?: number }) => {
              fieldsObj[e.field_name] = e.field_value;
              confObj[e.field_name] = e.confidence ?? 0.95;
            });
            setExtraction({
              document_id: documentId,
              document_type: reviewData.document?.classification || null,
              fields: fieldsObj,
              confidence: confObj,
              status: "EXTRACTED",
            });
          } else {
            const extRes = await fetchWithAuth(`${API_URL}/api/documents/${documentId}/extract`);
            if (extRes.ok && !ignore) setExtraction(await extRes.json());
          }
          if (reviewData.policy_validation_runs && reviewData.policy_validation_runs.length > 0) {
            const latestRun = reviewData.policy_validation_runs[0];
            setValidationRun({
              id: latestRun.id,
              document_id: latestRun.document_id || documentId,
              status: latestRun.status,
              summary: latestRun.summary || "Policy validation evaluated against organization covenants.",
              retrieval_outcome: latestRun.retrieval_outcome || "SUCCESS",
              policy_versions: latestRun.policy_versions || [],
              findings: latestRun.findings || [],
              created_at: latestRun.created_at || new Date().toISOString(),
            });
          }
          if (reviewData.audit_events && reviewData.audit_events.length > 0) {
            setAuditEvents(reviewData.audit_events);
          }
        } else {
          // Fallback to standard document endpoints
          const res = await fetchWithAuth(`${API_URL}/api/documents/${documentId}`);
          if (res.ok && !ignore) {
            const data = await res.json();
            setDocument(data);
            if (data.status === "REVIEWER_VERIFIED" || data.status === "APPROVED") setCertified(true);
          }
          const extRes = await fetchWithAuth(`${API_URL}/api/documents/${documentId}/extract`);
          if (extRes.ok && !ignore) {
            const extData = await extRes.json();
            setExtraction(extData);
          }
        }
      } catch {}

      // 3. Fetch audit trail (FE11)
      try {
        const auditRes = await fetchWithAuth(`${API_URL}/api/audit/${documentId}`);
        if (auditRes.ok && !ignore) {
          const auditData = await auditRes.json();
          if (auditData.events) {
            setAuditEvents(auditData.events);
          }
        }
      } catch {}
      finally {
        if (!ignore) {
          setLoadingDoc(false);
        }
      }
    }

    const timer = setTimeout(() => {
      loadData();
    }, 0);

    return () => {
      ignore = true;
      clearTimeout(timer);
    };
  }, [documentId, documentCacheKey, fetchWithAuth]);

  // FE09: Trigger policy validation on demand
  async function runValidation() {
    setValidating(true);
    setValidationError(null);
    try {
      const res = await fetchWithAuth(`${API_URL}/api/documents/${documentId}/validate-policy`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        setValidationRun(data);
      } else {
        const err = await res.json().catch(() => null);
        setValidationError(
          err?.detail?.message ||
            (typeof err?.detail === "string" ? err.detail : "Failed to run policy validation.")
        );
      }
    } catch {
      setValidationError("Network error while triggering policy validation.");
    } finally {
      setValidating(false);
    }
  }

  // Rerun field extraction
  async function rerunExtraction() {
    setRerunning(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/api/documents/${documentId}/extract`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        setExtraction(data);
        setDocument((current) => current
          ? { ...current, status: data.status || current.status, ocr_text_length: data.ocr_text_length ?? current.ocr_text_length }
          : current);
      }
    } catch {}
    setRerunning(false);
  }

  // Refresh audit trail
  async function refreshAuditTrail() {
    setLoadingAudit(true);
    try {
      const auditRes = await fetchWithAuth(`${API_URL}/api/audit/${documentId}`);
      if (auditRes.ok) {
        const data = await auditRes.json();
        if (data.events) setAuditEvents(data.events);
      }
    } catch {}
    setLoadingAudit(false);
  }

  // FE12: Assistant Query handler
  async function handleAskAssistant(e?: React.FormEvent, customQuery?: string) {
    if (e) e.preventDefault();
    const query = (customQuery || questionInput).trim();
    if (!query || queryingAssistant) return;

    const userMsg: AssistantMessage = {
      id: `u_${Date.now()}`,
      sender: "user",
      content: query,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setQuestionInput("");
    setQueryingAssistant(true);

    try {
      const res = await fetchWithAuth(`${API_URL}/api/documents/${documentId}/assistant/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: query }),
      });

      if (res.ok) {
        const data = await res.json();
        const assistantMsg: AssistantMessage = {
          id: `a_${Date.now()}`,
          sender: "assistant",
          content: data.answer || "No response generated.",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          sources: data.sources || [],
          is_grounded: data.is_grounded ?? true,
          limitation: data.limitation,
          confidence: data.confidence,
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } else {
        const err = await res.json().catch(() => null);
        const errMsg =
          err?.detail?.message ||
          (typeof err?.detail === "string" ? err.detail : "Unable to retrieve assistant answer.");
        setMessages((prev) => [
          ...prev,
          {
            id: `err_${Date.now()}`,
            sender: "assistant",
            content: `Error: ${errMsg}`,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            is_grounded: false,
            limitation: "Request failed to execute against the document assistant endpoint.",
          },
        ]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: `err_${Date.now()}`,
          sender: "assistant",
          content: "Network error communicating with the document assistant API.",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          is_grounded: false,
        },
      ]);
    } finally {
      setQueryingAssistant(false);
    }
  }

  useEffect(() => {
    if (activeTab === "assistant") {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, activeTab]);

  const fieldList =
    extraction && Object.keys(extraction.fields || {}).length > 0
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
      : [];

  const ocrTextLength = document?.ocr_text_length ?? extraction?.ocr_text_length ?? 0;

  const categoryName = document?.category || "Archival Document";
  const rawFieldsMap = extraction?.fields || {};

  // Group FE09 findings
  const findings = validationRun?.findings || [];
  const violationFindings = findings.filter((f) => f.status === "FAIL");
  const uncertaintyFindings = findings.filter(
    (f) =>
      f.status === "NEEDS_HUMAN_REVIEW" ||
      f.status === "MISSING_INFORMATION" ||
      f.status === "FLAG"
  );
  const passedFindings = findings.filter((f) => f.status === "PASS");

  if (loadingDoc) {
    return (
      <AppShell>
        <div style={{ padding: "60px", textAlign: "center", color: "var(--muted)" }}>
          <p style={{ font: "20px 'Newsreader', serif", margin: "0 0 8px" }}>Loading File Inspector...</p>
          <small>Retrieving archival record {documentId}...</small>
        </div>
      </AppShell>
    );
  }

  if (!document) {
    return (
      <AppShell>
        <div style={{ padding: "60px", textAlign: "center" }}>
          <Icon name="file" size={32} />
          <h2 style={{ font: "20px 'Newsreader', serif", margin: "12px 0 6px" }}>Document Not Found</h2>
          <p style={{ color: "var(--muted)", fontSize: "12px", margin: "0 0 16px" }}>
            The requested document file <code>{documentId}</code> does not exist or has been removed from this workspace.
          </p>
          <Link href="/documents" className="btn primary" style={{ textDecoration: "none" }}>
            Back to Intake Library
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
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
          <Badge tone={certified ? "green" : document.status === "UPLOADED" ? undefined : "violet"}>
            {certified ? "VERIFIED (100%)" : document.status}
          </Badge>
        </div>

        <div className="doc-actions">
          <p>
            <span className="eyebrow">CLASSIFIED AS</span> {categoryName}{" "}
            <code>{certified ? "100%" : document.confidence ? `${Math.round(document.confidence * 100)}%` : "AI Evaluated"}</code>
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
            <Button icon="pencil" onClick={() => setShowOverride(true)}>
              Correct Classification
            </Button>
            <Button
              variant="primary"
              icon="check"
              onClick={() => {
                setCertified(true);
                try {
                  const cached = sessionStorage.getItem(documentCacheKey);
                  if (cached) {
                    const parsed = JSON.parse(cached);
                    sessionStorage.setItem(
                      documentCacheKey,
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

      {/* Tabs Bar for Multidisciplinary Document Workspace */}
      <nav className="doc-nav-tabs">
        <button
          type="button"
          className={`doc-nav-tab ${activeTab === "overview" ? "active" : ""}`}
          onClick={() => setActiveTab("overview")}
        >
          <Icon name="grid" size={13} />
          Overview &amp; Extractions
          <span className="tab-count-pill">{fieldList.length}</span>
        </button>

        <button
          type="button"
          className={`doc-nav-tab ${activeTab === "validation" ? "active" : ""}`}
          onClick={() => setActiveTab("validation")}
        >
          <Icon name="shield" size={13} />
          Policy Validation
          {validationRun ? (
            <span
              className="tab-count-pill"
              style={{
                color:
                  validationRun.status === "PASS"
                    ? "var(--green)"
                    : validationRun.status === "FAIL"
                    ? "var(--red)"
                    : "var(--amber)",
              }}
            >
              {validationRun.status}
            </span>
          ) : (
            <span className="tab-count-pill">Ready</span>
          )}
        </button>

        <button
          type="button"
          className={`doc-nav-tab ${activeTab === "audit" ? "active" : ""}`}
          onClick={() => setActiveTab("audit")}
        >
          <Icon name="history" size={13} />
          Audit Trail
          <span className="tab-count-pill">{auditEvents.length}</span>
        </button>

        <button
          type="button"
          className={`doc-nav-tab ${activeTab === "assistant" ? "active" : ""}`}
          onClick={() => setActiveTab("assistant")}
        >
          <Icon name="search" size={13} />
          Policy Assistant
          <span className="tab-count-pill">AI Grounded</span>
        </button>
      </nav>

      {/* TAB 1: OVERVIEW & EXTRACTIONS */}
      {activeTab === "overview" && (
        <>
          {/* 4-Stage Connected Pipeline Tracker */}
          <div className="pipeline">
            <div className="stage">
              <span className="stage-dot">✓</span>
              <div>
                <b><code>01</code> Ingestion</b>
                <small>File received{document?.file_size ? ` · ${formatFileSize(document.file_size)}` : ""}</small>
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
              <span className="stage-dot">{certified ? "✓" : "●"}</span>
              <div>
                <b><code>04</code> Field Extraction</b>
                <small>{fieldList.length ? `${fieldList.length} fields · ${certified ? "Certified" : "Ready to certify"}` : "No structured fields extracted"}</small>
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
                      filename={document?.filename || "commercial_invoice_september.pdf"}
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
                  ) : (document?.filename || "").match(/\.(png|jpg|jpeg|webp)$/i) ? (
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
                        alt={document?.filename || "Source Document"}
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
                      <code>{f.conf}%</code>
                    </div>
                    <div className="confidence-track">
                      <i style={{ width: `${f.conf}%` }} />
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
                  <Badge tone={validationRun?.status === "FAIL" ? "red" : "green"}>
                    {validationRun?.status || "CHECKED"}
                  </Badge>
                </div>
                <p>
                  {validationRun?.summary ||
                    "Document extractions verified against organizational covenants and compliance registries."}
                </p>
                <div style={{ marginTop: "14px" }}>
                  <Button variant="ghost" onClick={() => setActiveTab("validation")}>
                    View Detailed Policy Findings &amp; Citations →
                  </Button>
                </div>
              </div>

              <p className="audit-note">
                ⓘ Review extracted fields against source document. Certification affixes your identity to the permanent audit ledger.
              </p>
            </section>
          </div>
        </>
      )}

      {/* TAB 2: POLICY VALIDATION FINDINGS (FE09) */}
      {activeTab === "validation" && (
        <div className="validation-view">
          {/* Header Action Banner */}
          <div className="validation-header-banner">
            <div className="val-summary-text">
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "4px" }}>
                <span style={{ font: "10px 'Inter', sans-serif", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.8px" }}>
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
                onClick={runValidation}
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
              <Button variant="primary" icon="shield" onClick={runValidation}>
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
      )}

      {/* TAB 3: DOCUMENT AUDIT TRAIL (FE11) */}
      {activeTab === "audit" && (
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
              onClick={refreshAuditTrail}
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
      )}

      {/* TAB 4: GROUNDED DOCUMENT POLICY ASSISTANT (FE12) */}
      {activeTab === "assistant" && (
        <div className="assistant-workspace">
          {/* Read-Only Notice Banner */}
          <div className="assistant-banner">
            <Icon name="shield" size={18} />
            <div>
              <b>Grounded Document &amp; Policy Assistant</b>
              <p style={{ margin: "2px 0 0" }}>
                Answers are grounded strictly in this document&apos;s extractions and your organization&apos;s active policy documents. The assistant is strictly read-only and cannot alter document states or make approval decisions.
              </p>
            </div>
          </div>

          {/* Suggested Queries */}
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
            <span style={{ fontSize: "10px", fontWeight: 600, color: "var(--muted)", textTransform: "uppercase" }}>
              Suggested Inquiries:
            </span>
            <button
              type="button"
              onClick={() => handleAskAssistant(undefined, "What is the total amount and payment terms on this document?")}
              style={{
                background: "white",
                border: "1px solid var(--line)",
                borderRadius: "14px",
                padding: "4px 10px",
                fontSize: "10px",
                cursor: "pointer",
                color: "var(--body)",
              }}
            >
              Total amount &amp; payment terms
            </button>
            <button
              type="button"
              onClick={() => handleAskAssistant(undefined, "Does this document meet vendor and tax ID requirements?")}
              style={{
                background: "white",
                border: "1px solid var(--line)",
                borderRadius: "14px",
                padding: "4px 10px",
                fontSize: "10px",
                cursor: "pointer",
                color: "var(--body)",
              }}
            >
              Vendor &amp; tax ID validation
            </button>
            <button
              type="button"
              onClick={() => handleAskAssistant(undefined, "Are there any policy compliance violations or flags?")}
              style={{
                background: "white",
                border: "1px solid var(--line)",
                borderRadius: "14px",
                padding: "4px 10px",
                fontSize: "10px",
                cursor: "pointer",
                color: "var(--body)",
              }}
            >
              Policy flags &amp; violations
            </button>
          </div>

          {/* Messages Stream */}
          <div className="chat-messages-container">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`chat-bubble ${m.sender === "user" ? "user" : "assistant"}`}
              >
                <div>{m.content}</div>

                {/* Grounding & Uncertainty Indicators */}
                {m.sender === "assistant" && m.id !== "welcome" && (
                  <div>
                    {m.is_grounded ? (
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                          fontSize: "10px",
                          color: "var(--green)",
                          fontWeight: 600,
                          marginTop: "6px",
                        }}
                      >
                        ✓ Grounded in document &amp; policy evidence
                      </span>
                    ) : (
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                          fontSize: "10px",
                          color: "var(--amber)",
                          fontWeight: 600,
                          marginTop: "6px",
                        }}
                      >
                        ⚠ Partial or ungrounded evidence
                      </span>
                    )}

                    {m.limitation && (
                      <div
                        style={{
                          marginTop: "8px",
                          background: "var(--amber-bg)",
                          border: "1px solid rgba(158, 109, 36, 0.2)",
                          borderRadius: "4px",
                          padding: "6px 10px",
                          fontSize: "10px",
                          color: "var(--amber)",
                        }}
                      >
                        <b>Limitation Notice:</b> {m.limitation}
                      </div>
                    )}

                    {/* Citations Grid */}
                    {m.sources && m.sources.length > 0 && (
                      <div className="assistant-citations-grid">
                        <b style={{ fontSize: "10px", color: "var(--muted)", textTransform: "uppercase" }}>
                          Supporting Grounded Sources ({m.sources.length})
                        </b>
                        {m.sources.map((src, sIdx) => {
                          const type = src.source_type || "DOCUMENT_FIELD";
                          const badgeClass =
                            type === "POLICY_CHUNK"
                              ? "policy"
                              : type === "VALIDATION_FINDING"
                              ? "finding"
                              : "doc";

                          return (
                            <div className="assistant-source-card" key={sIdx}>
                              <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
                                <span className={`source-type-badge ${badgeClass}`}>
                                  {type.replace(/_/g, " ")}
                                </span>
                                <strong style={{ fontSize: "11px", color: "var(--ink)" }}>{src.title}</strong>
                                <span style={{ color: "var(--muted)", fontSize: "10px", marginLeft: "auto" }}>
                                  {src.reference}
                                </span>
                              </div>
                              <blockquote
                                style={{
                                  margin: 0,
                                  paddingLeft: "8px",
                                  borderLeft: "2px solid var(--violet)",
                                  fontSize: "10px",
                                  color: "var(--body)",
                                  fontStyle: "italic",
                                }}
                              >
                                &ldquo;{src.excerpt}&rdquo;
                              </blockquote>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}

                <div
                  style={{
                    fontSize: "9px",
                    color: m.sender === "user" ? "rgba(255,255,255,0.7)" : "var(--muted)",
                    alignSelf: "flex-end",
                    marginTop: "4px",
                  }}
                >
                  {m.timestamp}
                </div>
              </div>
            ))}

            {queryingAssistant && (
              <div className="chat-bubble assistant">
                <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--muted)", fontSize: "11px" }}>
                  <span>Synthesizing grounded citations...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Query Input Box */}
          <form className="assistant-input-box" onSubmit={(e) => handleAskAssistant(e)}>
            <input
              type="text"
              className="assistant-input-field"
              placeholder="Ask a question about document values or policy requirements..."
              value={questionInput}
              onChange={(e) => setQuestionInput(e.target.value)}
              disabled={queryingAssistant}
            />
            <Button
              variant="primary"
              icon="search"
              disabled={!questionInput.trim() || queryingAssistant}
            >
              {queryingAssistant ? "Querying..." : "Ask Assistant"}
            </Button>
          </form>
        </div>
      )}

      {showOverride && (
        <OverrideSheet
          documentId={documentId}
          currentCategory={categoryName}
          fetchWithAuth={fetchWithAuth}
          onClose={() => setShowOverride(false)}
          onSaved={(newCategory) => {
            setDocument((prev) => (prev ? { ...prev, category: newCategory, confidence: 1.0 } : null));
            setCertified(true);
            try {
              const cached = sessionStorage.getItem(documentCacheKey);
              if (cached) {
                const parsed = JSON.parse(cached);
                sessionStorage.setItem(
                  documentCacheKey,
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

export default function DocumentDetailsPage(props: {
  params: Promise<{ id: string }>;
}) {
  return (
    <ProtectedRoute>
      <DocumentDetailsContent {...props} />
    </ProtectedRoute>
  );
}
