"use client";

import { useEffect, useState, useMemo } from "react";
import { useAuth } from "../../../context/AuthContext";
import { DocumentRecord } from "@/app/classification";
import {
  ActiveTab,
  ExtractionResult,
  PolicyValidationRun,
  PolicyValidationFinding,
  PolicyValidationSource,
  AuditEvent,
  AssistantMessage,
} from "../types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

export function useDocumentDetails(documentId: string, isDemo: boolean) {
  const { fetchWithAuth, token, user, activeOrgId } = useAuth();

  const [activeTab, setActiveTab] = useState<ActiveTab>("overview");
  const [document, setDocument] = useState<DocumentRecord | null>(null);
  const [loadingDoc, setLoadingDoc] = useState(true);
  const [extraction, setExtraction] = useState<ExtractionResult | null>(null);
  const [showOverride, setShowOverride] = useState(false);
  const [rerunning, setRerunning] = useState(false);
  const [filePreview, setFilePreview] = useState<{ documentId: string; url: string } | null>(null);
  const [filePreviewFailure, setFilePreviewFailure] = useState<{ documentId: string; message: string } | null>(null);

  // Policy validation findings state
  const [validationRun, setValidationRun] = useState<PolicyValidationRun | null>(null);
  const [validating, setValidating] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Audit trail state
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(false);

  // Grounded Assistant state
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

  const filePreviewUrl = filePreview?.documentId === documentId ? filePreview.url : null;
  const filePreviewError = filePreviewFailure?.documentId === documentId ? filePreviewFailure.message : null;

  // Protected file preview loading
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
      try {
        const cacheKey = `kagaz_doc_${user?.user_id || ""}_${activeOrgId || user?.organization_id || ""}_${documentId}`;
        const cached = sessionStorage.getItem(cacheKey);
        if (cached && !ignore) {
          setDocument(JSON.parse(cached));
        }
      } catch {}

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
          }
          if (reviewData.extractions && reviewData.extractions.length > 0) {
            const fieldsObj: Record<string, string | number | string[]> = {};
            const confObj: Record<string, number> = {};
            reviewData.extractions.forEach((e: { field_name: string; value: string; confidence?: number }) => {
              fieldsObj[e.field_name] = e.value;
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
              findings: (latestRun.findings || []).map((finding: PolicyValidationFinding & { source_references?: PolicyValidationSource[] }) => ({
                ...finding,
                sources: finding.sources || finding.source_references || [],
              })),
              created_at: latestRun.created_at || new Date().toISOString(),
            });
          }
          if (reviewData.audit_events && reviewData.audit_events.length > 0) {
            setAuditEvents(reviewData.audit_events);
          }
        } else {
          const res = await fetchWithAuth(`${API_URL}/api/documents/${documentId}`);
          if (res.ok && !ignore) setDocument(await res.json());
          const extRes = await fetchWithAuth(`${API_URL}/api/documents/${documentId}/extract`);
          if (extRes.ok && !ignore) setExtraction(await extRes.json());
        }
      } catch {}

      try {
        const auditRes = await fetchWithAuth(`${API_URL}/api/audit/${documentId}`);
        if (auditRes.ok && !ignore) {
          const auditData = await auditRes.json();
          if (auditData.events) setAuditEvents(auditData.events);
        }
      } catch {}
      finally {
        if (!ignore) setLoadingDoc(false);
      }
    }

    const timer = setTimeout(() => { loadData(); }, 0);
    return () => { ignore = true; clearTimeout(timer); };
  }, [activeOrgId, documentId, fetchWithAuth, user?.organization_id, user?.user_id]);

  async function runValidation() {
    setValidating(true);
    setValidationError(null);
    try {
      const res = await fetchWithAuth(`${API_URL}/api/documents/${documentId}/validate-policy`, { method: "POST" });
      if (res.ok) {
        setValidationRun(await res.json());
      } else {
        const err = await res.json().catch(() => null);
        setValidationError(err?.detail?.message || (typeof err?.detail === "string" ? err.detail : "Failed to run policy validation."));
      }
    } catch {
      setValidationError("Network error while triggering policy validation.");
    } finally {
      setValidating(false);
    }
  }

  async function rerunExtraction() {
    setRerunning(true);
    try {
      const res = await fetchWithAuth(`${API_URL}/api/documents/${documentId}/extract`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setExtraction(data);
        setDocument((curr) => curr ? { ...curr, status: data.status || curr.status, ocr_text_length: data.ocr_text_length ?? curr.ocr_text_length } : curr);
      }
    } catch {}
    setRerunning(false);
  }

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
        setMessages((prev) => [
          ...prev,
          {
            id: `a_${Date.now()}`,
            sender: "assistant",
            content: data.answer || "No response generated.",
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            sources: data.sources || [],
            is_grounded: data.is_grounded ?? true,
            limitation: data.limitation,
            confidence: data.confidence,
          },
        ]);
      } else {
        const err = await res.json().catch(() => null);
        const errMsg = err?.detail?.message || (typeof err?.detail === "string" ? err.detail : "Unable to retrieve assistant answer.");
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

  const fieldList = useMemo(() => {
    if (extraction && Object.keys(extraction.fields || {}).length > 0) {
      return Object.entries(extraction.fields).map(([k, v]) => ({
        key: k.replace(/_/g, " ").toUpperCase(),
        val: typeof v === "number" ? `$${v.toLocaleString()}` : String(v),
        conf: extraction.confidence?.[k] == null ? null : Math.round(extraction.confidence[k] * 100),
      }));
    }
    if (isDemo) {
      return [
        { key: "INVOICE NUMBER", val: "INV-2024-9821", conf: 96 },
        { key: "INVOICE DATE", val: "2024-09-24", conf: 94 },
        { key: "SUPPLIER NAME", val: "Ad4tech Material LLC", conf: 91 },
        { key: "TOTAL AMOUNT", val: "$1,564.00", conf: 98 },
      ];
    }
    return [];
  }, [extraction, isDemo]);

  const categoryName = document?.category || "Archival Document";
  const ocrTextLength = document?.ocr_text_length ?? extraction?.ocr_text_length ?? 0;

  return {
    activeTab,
    setActiveTab,
    document,
    setDocument,
    loadingDoc,
    extraction,
    showOverride,
    setShowOverride,
    rerunning,
    filePreviewUrl,
    filePreviewError,
    validationRun,
    validating,
    validationError,
    auditEvents,
    loadingAudit,
    messages,
    questionInput,
    setQuestionInput,
    queryingAssistant,
    runValidation,
    rerunExtraction,
    refreshAuditTrail,
    handleAskAssistant,
    fieldList,
    categoryName,
    ocrTextLength,
    fetchWithAuth,
    user,
    activeOrgId,
  };
}
