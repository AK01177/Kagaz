"use client";

import { use } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell, Icon } from "../../../components/AppShell";
import { ProtectedRoute } from "../../../components/ProtectedRoute";

import { DocumentHeader } from "./components/DocumentHeader";
import { OverviewTab } from "./components/OverviewTab";
import { PolicyValidationTab } from "./components/PolicyValidationTab";
import { AuditTrailTab } from "./components/AuditTrailTab";
import { AssistantTab } from "./components/AssistantTab";
import { OverrideSheet } from "./components/OverrideSheet";
import { useDocumentDetails } from "./hooks/useDocumentDetails";

function DocumentDetailsContent(props: {
  params: Promise<{ id: string }>;
}) {
  const unwrapped = use(props.params);
  const routeParams = useParams();
  const documentId = unwrapped?.id || (routeParams?.id as string) || "";
  const isDemo = Boolean(documentId && (documentId.startsWith("doc_demo") || documentId === "demo"));

  const {
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
  } = useDocumentDetails(documentId, isDemo);

  if (loadingDoc) {
    return (
      <AppShell>
        <div style={{ padding: "80px 24px", textAlign: "center", maxWidth: "480px", margin: "0 auto" }}>
          <span
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "12px",
              background: "var(--brand-surface)",
              color: "var(--brand)",
              display: "grid",
              placeItems: "center",
              margin: "0 auto 16px",
            }}
          >
            <Icon name="refresh" size={22} />
          </span>
          <h2 style={{ font: "600 22px 'Newsreader', Georgia, serif", margin: "0 0 6px", color: "var(--ink)" }}>Loading Document Record...</h2>
          <p style={{ color: "var(--secondary)", fontSize: "12px" }}>
            Retrieving cryptographic metadata and extractions for <code>{documentId}</code>...
          </p>
        </div>
      </AppShell>
    );
  }

  if (!document) {
    return (
      <AppShell>
        <div style={{ padding: "80px 24px", textAlign: "center", maxWidth: "480px", margin: "0 auto" }}>
          <span
            style={{
              width: "56px",
              height: "56px",
              borderRadius: "14px",
              background: "var(--surface-secondary)",
              color: "var(--muted)",
              display: "grid",
              placeItems: "center",
              margin: "0 auto 18px",
            }}
          >
            <Icon name="file" size={28} />
          </span>
          <h2 style={{ font: "600 24px 'Newsreader', Georgia, serif", margin: "0 0 8px", color: "var(--ink)" }}>Document Not Found</h2>
          <p style={{ color: "var(--secondary)", fontSize: "13px", margin: "0 0 24px", lineHeight: 1.5 }}>
            The requested document record <code>{documentId}</code> does not exist or has been removed from this workspace enclave.
          </p>
          <Link href="/workspace/documents" className="btn primary" style={{ textDecoration: "none" }}>
            Return to Repository Library
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <DocumentHeader
        document={document}
        documentId={documentId}
        categoryName={categoryName}
        approved={document.status === "APPROVED"}
        rerunning={rerunning}
        onRerunExtraction={rerunExtraction}
        onOpenOverride={() => setShowOverride(true)}
      />

      <nav className="doc-nav-tabs" aria-label="Document view tabs">
        <button
          type="button"
          className={`doc-nav-tab ${activeTab === "overview" ? "active" : ""}`}
          onClick={() => setActiveTab("overview")}
        >
          <Icon name="grid" size={15} />
          Overview &amp; Extractions
          <span className="tab-count-pill">{fieldList.length}</span>
        </button>

        <button
          type="button"
          className={`doc-nav-tab ${activeTab === "validation" ? "active" : ""}`}
          onClick={() => setActiveTab("validation")}
        >
          <Icon name="shield" size={15} />
          Policy Validation
          {validationRun ? (
            <span
              className="tab-count-pill"
              style={{
                color:
                  validationRun.status === "PASS"
                    ? "var(--success)"
                    : validationRun.status === "FAIL"
                    ? "var(--error)"
                    : "var(--warning)",
                fontWeight: 600,
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
          <Icon name="history" size={15} />
          Audit Trail
          <span className="tab-count-pill">{auditEvents.length}</span>
        </button>

        <button
          type="button"
          className={`doc-nav-tab ${activeTab === "assistant" ? "active" : ""}`}
          onClick={() => setActiveTab("assistant")}
        >
          <Icon name="search" size={15} />
          Policy Assistant
          <span className="tab-count-pill">AI Grounded</span>
        </button>
      </nav>

      {activeTab === "overview" && (
        <OverviewTab
          document={document}
          categoryName={categoryName}
          fieldList={fieldList}
          rawFieldsMap={extraction?.fields || {}}
          ocrTextLength={ocrTextLength}
          isDemo={isDemo}
          filePreviewUrl={filePreviewUrl}
          filePreviewError={filePreviewError}
          validationRun={validationRun}
          onNavigateToValidation={() => setActiveTab("validation")}
        />
      )}

      {activeTab === "validation" && (
        <PolicyValidationTab
          validationRun={validationRun}
          validating={validating}
          validationError={validationError}
          onRunValidation={runValidation}
        />
      )}

      {activeTab === "audit" && (
        <AuditTrailTab
          auditEvents={auditEvents}
          loadingAudit={loadingAudit}
          onRefreshAudit={refreshAuditTrail}
        />
      )}

      {activeTab === "assistant" && (
        <AssistantTab
          messages={messages}
          questionInput={questionInput}
          queryingAssistant={queryingAssistant}
          onQuestionInputChange={setQuestionInput}
          onAskAssistant={handleAskAssistant}
        />
      )}

      {showOverride && (
        <OverrideSheet
          documentId={documentId}
          currentCategory={categoryName}
          onClose={() => setShowOverride(false)}
          onSaved={(newCategory, newConf, newStatus) => {
            setDocument((prev) =>
              prev
                ? {
                    ...prev,
                    category: newCategory,
                    confidence: newConf,
                    status: newStatus,
                    is_manually_corrected: true,
                  }
                : prev
            );
            refreshAuditTrail();
          }}
          fetchWithAuth={fetchWithAuth}
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
      <DocumentDetailsContent params={props.params} />
    </ProtectedRoute>
  );
}
