"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { AppShell, Badge, Icon, Button } from "../../components/AppShell";
import { ProtectedRoute } from "../../components/ProtectedRoute";
import { useAuth } from "../../context/AuthContext";
import { formatDate } from "../../classification";

interface DashboardDoc {
  id: string;
  name: string;
  date: string;
  type: string;
  conf: string;
  status: string;
}

function DashboardContent() {
  const { user, activeOrgId, fetchWithAuth, isAuthenticated } = useAuth();
  const currentOrg = activeOrgId || user?.organization_id || "Enterprise Workspace";

  const [loading, setLoading] = useState(true);
  const [totalDocsCount, setTotalDocsCount] = useState(0);
  const [reviewQueueCount, setReviewQueueCount] = useState(0);
  const [approvalQueueCount, setApprovalQueueCount] = useState(0);
  const [validatedRate, setValidatedRate] = useState("—");
  const [recentDocs, setRecentDocs] = useState<DashboardDoc[]>([]);

  const loadDashboardData = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    try {
      const [docsRes, reviewRes, approvalRes] = await Promise.allSettled([
        fetchWithAuth("/api/documents"),
        fetchWithAuth("/api/documents/workflow/review-queue"),
        fetchWithAuth("/api/documents/workflow/approval-queue"),
      ]);

      let docsList: Array<{
        id?: string;
        document_id?: string;
        filename?: string;
        name?: string;
        created_at?: string;
        category?: string;
        document_type?: string;
        confidence?: number;
        status?: string;
      }> = [];
      if (docsRes.status === "fulfilled" && docsRes.value.ok) {
        const raw = await docsRes.value.json().catch(() => []);
        docsList = Array.isArray(raw) ? raw : raw?.documents || [];
        setTotalDocsCount(docsList.length);
      } else {
        setTotalDocsCount(0);
      }

      let reviewCount = 0;
      if (reviewRes.status === "fulfilled" && reviewRes.value.ok) {
        const revData = await reviewRes.value.json().catch(() => ({}));
        const items = revData?.items || (Array.isArray(revData) ? revData : []);
        reviewCount = items.length;
        setReviewQueueCount(reviewCount);
      } else {
        setReviewQueueCount(0);
      }

      let approvalCount = 0;
      if (approvalRes.status === "fulfilled" && approvalRes.value.ok) {
        const appData = await approvalRes.value.json().catch(() => ({}));
        const items = appData?.items || (Array.isArray(appData) ? appData : []);
        approvalCount = items.length;
        setApprovalQueueCount(approvalCount);
      } else {
        setApprovalQueueCount(0);
      }

      if (docsList.length > 0) {
        const validated = docsList.filter((d) => d.status === "VALIDATED" || d.status === "APPROVED").length;
        const rate = Math.round((validated / docsList.length) * 100);
        setValidatedRate(`${rate}%`);

        const formatted = docsList.slice(0, 5).map((d) => ({
          id: d.id || d.document_id || "doc_unknown",
          name: d.filename || d.name || "document.pdf",
          date: d.created_at ? formatDate(d.created_at) : "Recently Added",
          type: d.category || d.document_type || "Unclassified document",
          conf: d.confidence != null
            ? `${(d.confidence > 1 ? d.confidence : d.confidence * 100).toFixed(1)}%`
            : "—",
          status: d.status || "UPLOADED",
        }));
        setRecentDocs(formatted);
      } else {
        setValidatedRate("—");
        setRecentDocs([]);
      }
    } catch {
      // Keep empty clean view
      setRecentDocs([]);
      setValidatedRate("—");
    } finally {
      setLoading(false);
    }
  }, [fetchWithAuth, isAuthenticated]);

  useEffect(() => {
    const timer = setTimeout(() => {
      loadDashboardData();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadDashboardData]);

  const stats = [
    {
      label: "TOTAL INGESTED",
      sub: "Active repository volume",
      value: totalDocsCount.toString(),
      icon: "file" as const,
      color: "var(--brand)",
      bg: "var(--brand-surface)",
      badge: "Realtime",
    },
    {
      label: "VALIDATED RATE",
      sub: "Policy clearance score",
      value: validatedRate,
      icon: "check" as const,
      color: "var(--success)",
      bg: "var(--success-bg)",
      badge: validatedRate !== "—" ? "Compliant" : "Calculating",
    },
    {
      label: "AWAITING VERIFICATION",
      sub: "Review queue backlog",
      value: reviewQueueCount.toString(),
      icon: "stamp" as const,
      color: reviewQueueCount > 0 ? "var(--warning)" : "var(--muted)",
      bg: reviewQueueCount > 0 ? "var(--warning-bg)" : "var(--surface-secondary)",
      badge: reviewQueueCount > 0 ? "Action Required" : "Clear",
    },
    {
      label: "APPROVALS PENDING",
      sub: "Sign-off authorizations",
      value: approvalQueueCount.toString(),
      icon: "shield" as const,
      color: approvalQueueCount > 0 ? "var(--violet)" : "var(--muted)",
      bg: approvalQueueCount > 0 ? "var(--violet-bg)" : "var(--surface-secondary)",
      badge: approvalQueueCount > 0 ? "Pending" : "Zero Queued",
    },
  ];

  return (
    <AppShell>
      <header className="page-head">
        <div className="crumb">
          <Icon name="grid" size={14} /> Workspace <span>/</span> Overview
          <div className="record-lock">
            <span className="brand-dot" /> {loading ? "Syncing..." : "Authenticated Enclave Active"}
          </div>
        </div>
        <div className="head-main">
          <div>
            <h1>Workspace Overview</h1>
            <p className="subline">{currentOrg.toUpperCase()} · AUTONOMOUS DOCUMENT OPERATIONS</p>
          </div>
          <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
            <Button variant="ghost" icon="refresh" onClick={loadDashboardData} disabled={loading}>
              Sync Data
            </Button>
            <Link href="/workspace/documents" className="btn primary" style={{ textDecoration: "none" }}>
              <Icon name="inbox" size={15} /> Deposit File ↥
            </Link>
          </div>
        </div>
      </header>

      <div className="intake-body">
        {/* Metric Cards Row */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: "18px",
            marginBottom: "28px",
          }}
        >
          {stats.map((s) => (
            <div
              key={s.label}
              style={{
                background: "#FFFFFF",
                border: "1px solid var(--line)",
                borderRadius: "12px",
                padding: "22px 24px",
                boxShadow: "var(--shadow-xs)",
                transition: "all 0.25s var(--ease-spring)",
                position: "relative",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-2px)";
                e.currentTarget.style.boxShadow = "var(--shadow-md)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "none";
                e.currentTarget.style.boxShadow = "var(--shadow-xs)";
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "14px" }}>
                <span
                  style={{
                    width: "38px",
                    height: "38px",
                    borderRadius: "10px",
                    background: s.bg,
                    display: "grid",
                    placeItems: "center",
                    color: s.color,
                  }}
                >
                  <Icon name={s.icon} size={18} />
                </span>
                <span
                  style={{
                    font: "600 10px 'JetBrains Mono', monospace",
                    padding: "3px 8px",
                    borderRadius: "9999px",
                    background: s.bg,
                    color: s.color,
                  }}
                >
                  {s.badge}
                </span>
              </div>
              <strong
                style={{
                  display: "block",
                  fontSize: "30px",
                  fontWeight: 600,
                  fontFamily: "'JetBrains Mono', monospace",
                  color: "var(--ink)",
                  marginBottom: "4px",
                }}
              >
                {s.value}
              </strong>
              <div style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.06em", color: "var(--muted)", textTransform: "uppercase" }}>
                {s.label}
              </div>
              <div style={{ fontSize: "12px", color: "var(--secondary)", marginTop: "2px" }}>
                {s.sub}
              </div>
            </div>
          ))}
        </div>

        {/* Verification Alert Callout if Review Items Exist */}
        {reviewQueueCount > 0 && (
          <div
            style={{
              background: "linear-gradient(135deg, rgba(217, 119, 6, 0.08) 0%, rgba(245, 158, 11, 0.03) 100%), #FFFFFF",
              border: "1px solid var(--warning-border)",
              borderRadius: "12px",
              padding: "20px 24px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "28px",
              flexWrap: "wrap",
              gap: "16px",
              boxShadow: "var(--shadow-xs)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
              <span
                style={{
                  width: "42px",
                  height: "42px",
                  borderRadius: "10px",
                  background: "var(--warning-bg)",
                  border: "1px solid var(--warning-border)",
                  color: "var(--warning)",
                  display: "grid",
                  placeItems: "center",
                  flexShrink: 0,
                }}
              >
                <Icon name="alert" size={20} />
              </span>
              <div>
                <b style={{ color: "var(--ink)", fontSize: "14px", fontWeight: 600 }}>
                  {reviewQueueCount} {reviewQueueCount === 1 ? "document requires" : "documents require"} human verification
                </b>
                <p style={{ margin: "4px 0 0", color: "var(--secondary)", fontSize: "12px", lineHeight: 1.5 }}>
                  Low-confidence extractions or policy variances require human accreditation before downstream ledger clearance.
                </p>
              </div>
            </div>
            <Link href="/workspace/review" className="btn primary" style={{ textDecoration: "none" }}>
              <Icon name="stamp" size={15} /> Open Verification Desk →
            </Link>
          </div>
        )}

        {/* Deposit Quick Panel */}
        <Link
          href="/workspace/documents"
          className="upload-panel"
          style={{
            textDecoration: "none",
            color: "inherit",
            marginBottom: "28px",
            cursor: "pointer",
          }}
        >
          <span className="upload-icon">
            <Icon name="inbox" size={24} />
          </span>
          <h2>Deposit a file into the archival pipeline.</h2>
          <p>Drop a PDF or image here to launch RapidOCR and deterministic genre classification.</p>
          <span className="upload-spec">PDF · PNG · JPG · JPEG · CEILING 10 MB</span>
        </Link>

        {/* Recent Files Table */}
        <section className="library-card" style={{ marginTop: 0 }}>
          <div className="library-toolbar">
            <div>
              <span className="eyebrow">ACTIVITY STREAM</span>
              <h2>Recent Workspace Files</h2>
            </div>
            <Link href="/workspace/documents" className="btn secondary" style={{ textDecoration: "none" }}>
              View All {totalDocsCount} Files →
            </Link>
          </div>

          <div className="library-table">
            <div className="lib-row lib-head">
              <span>FILE NAME</span>
              <span>UNIQUE ID</span>
              <span>UPLOADED</span>
              <span>CLASSIFICATION</span>
              <span>CONFIDENCE &amp; STATUS</span>
            </div>

            {recentDocs.length === 0 ? (
              <div style={{ padding: "48px 20px", textAlign: "center", color: "var(--muted)" }}>
                <p style={{ margin: "0 0 6px", fontSize: "14px", fontWeight: 600, color: "var(--ink)" }}>No files deposited in this workspace yet.</p>
                <small style={{ fontSize: "12px", color: "var(--secondary)" }}>Deposit a file above to begin RapidOCR ingestion, classification, and validation.</small>
              </div>
            ) : (
              recentDocs.map((d) => (
                <Link className="lib-row" key={d.id} href={`/workspace/documents/${d.id}`}>
                  <span className="doc-name">
                    <span className="doc-icon">
                      <Icon name="file" size={16} />
                    </span>
                    <b>{d.name}</b>
                  </span>
                  <code>{d.id}</code>
                  <span style={{ color: "var(--secondary)", fontSize: "12px" }}>{d.date}</span>
                  <span style={{ fontWeight: 500, color: "var(--ink)" }}>{d.type}</span>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <Badge tone={d.status === "NEEDS REVIEW" ? "amber" : "green"}>
                      {d.conf}
                    </Badge>
                    <small style={{ color: "var(--muted)", fontSize: "11px", fontWeight: 500 }}>{d.status}</small>
                  </div>
                </Link>
              ))
            )}
          </div>
        </section>
      </div>
    </AppShell>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}
