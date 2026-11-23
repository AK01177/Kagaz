"use client";

import { use } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell, Icon } from "../../components/AppShell";
import { ProtectedRoute } from "../../components/ProtectedRoute";

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
    user,
    activeOrgId,
  } = useDocumentDetails(documentId, isDemo);

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
          fetchWithAuth={fetchWithAuth}
          onClose={() => setShowOverride(false)}
          onSaved={(newCategory, confidence, status) => {
            setDocument((prev) => (prev ? { ...prev, category: newCategory, confidence, status } : null));
            try {
              const cacheKey = `kagaz_doc_${user?.user_id || ""}_${activeOrgId || user?.organization_id || ""}_${documentId}`;
              const cached = sessionStorage.getItem(cacheKey);
              if (cached) {
                const parsed = JSON.parse(cached);
                sessionStorage.setItem(cacheKey, JSON.stringify({ ...parsed, category: newCategory, confidence, status }));
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
