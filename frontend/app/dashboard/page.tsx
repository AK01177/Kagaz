"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { AppShell, Badge, Icon, Button } from "../components/AppShell";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { useAuth } from "../context/AuthContext";
import { formatDate } from "../classification";

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
  const [autoClearedRate, setAutoClearedRate] = useState("—");
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
        const cleared = docsList.filter(
          (d) =>
            d.status === "VALIDATED" ||
            d.status === "APPROVED" ||
            d.status === "CERTIFIED" ||
            (d.confidence && d.confidence >= 0.85)
        ).length;
        const rate = Math.round((cleared / docsList.length) * 100);
        setAutoClearedRate(`${rate}%`);

        const formatted = docsList.slice(0, 5).map((d) => ({
          id: d.id || d.document_id || "doc_unknown",
          name: d.filename || d.name || "document.pdf",
          date: d.created_at ? formatDate(d.created_at) : "Recently Added",
          type: d.category || d.document_type || "Classified Document",
          conf: d.confidence
            ? `${(d.confidence > 1 ? d.confidence : d.confidence * 100).toFixed(1)}%`
            : "—",
          status: d.status || "CLASSIFIED",
        }));
        setRecentDocs(formatted);
      } else {
        setAutoClearedRate("—");
        setRecentDocs([]);
      }
    } catch {
      // Keep empty clean view
      setRecentDocs([]);
      setAutoClearedRate("—");
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
    { label: "WORKSPACE FILES", value: totalDocsCount.toString(), tone: totalDocsCount > 0 ? "neutral" : "neutral" },
    { label: "AUTO-CLEARED RATE", value: autoClearedRate, tone: autoClearedRate !== "—" ? "green" : "neutral" },
    { label: "AWAITING VERIFICATION", value: reviewQueueCount.toString(), tone: reviewQueueCount > 0 ? "amber" : "neutral" },
    { label: "APPROVALS PENDING", value: approvalQueueCount.toString(), tone: approvalQueueCount > 0 ? "violet" : "neutral" },
  ];

  return (
    <AppShell>
      <header className="page-head">
        <div className="crumb">
          <Icon name="grid" size={14} /> Workspace <span>/</span> Overview
          <div className="sync">
            <span className="brand-dot" /> {loading ? "Syncing Workspace..." : "Authenticated · Real-Time"}
          </div>
        </div>
        <div className="head-main">
          <div>
            <h1>Workspace Overview</h1>
            <p className="subline">{currentOrg.toUpperCase()} · ARCHIVAL INTELLIGENCE HUB</p>
          </div>
          <div style={{ display: "flex", gap: "10px" }}>
            <Button variant="ghost" icon="refresh" onClick={loadDashboardData}>
              Sync Data
            </Button>
            <Link href="/documents" className="btn primary" style={{ textDecoration: "none" }}>
              Deposit New File ↥
            </Link>
          </div>
        </div>
      </header>

      <div className="intake-body">
        {/* Metric Cards Row */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "16px",
            marginBottom: "24px",
          }}
        >
          {stats.map((s) => (
            <div
              key={s.label}
              style={{
                background: "white",
                border: "1px solid var(--line)",
                borderRadius: "8px",
                padding: "20px",
                boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
              }}
            >
              <span
                style={{
                  display: "block",
                  fontSize: "10px",
                  fontWeight: 600,
                  letterSpacing: "0.8px",
                  color: "var(--muted)",
                  marginBottom: "8px",
                  fontFamily: "'Inter', sans-serif",
                }}
              >
                {s.label}
              </span>
              <strong
                style={{
                  display: "block",
                  fontSize: "26px",
                  fontFamily: "'JetBrains Mono', monospace",
                  color:
                    s.tone === "amber"
                      ? "var(--amber)"
                      : s.tone === "green"
                      ? "var(--green)"
                      : s.tone === "violet"
                      ? "var(--violet)"
                      : "var(--ink)",
                }}
              >
                {s.value}
              </strong>
            </div>
          ))}
        </div>

        {/* Verification Alert Callout if Review Items Exist */}
        {reviewQueueCount > 0 && (
          <div
            style={{
              background: "var(--amber-bg)",
              border: "1px solid #eadcc4",
              borderRadius: "8px",
              padding: "16px 20px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "24px",
              flexWrap: "wrap",
              gap: "12px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <Icon name="alert" size={18} />
              <div>
                <b style={{ color: "var(--amber)", fontSize: "12px" }}>
                  {reviewQueueCount} {reviewQueueCount === 1 ? "file requires" : "files require"} human verification
                </b>
                <p style={{ margin: "4px 0 0", color: "#8b744e", fontSize: "11px" }}>
                  Low confidence extractions or policy variances require human accreditation before downstream ledger clearance.
                </p>
              </div>
            </div>
            <Link href="/review" className="btn primary" style={{ textDecoration: "none" }}>
              Open Verification Desk →
            </Link>
          </div>
        )}

        {/* Deposit Quick Panel */}
        <Link
          href="/documents"
          className="upload-panel"
          style={{
            textDecoration: "none",
            color: "inherit",
            marginBottom: "24px",
            cursor: "pointer",
          }}
        >
          <span className="upload-icon">↥</span>
          <h2>Deposit a file for intelligence.</h2>
          <p>Drop a PDF or image here to launch RapidOCR and genre classification.</p>
          <span className="upload-spec">PDF · PNG · JPG · JPEG · MAXIMUM 10 MB</span>
        </Link>

        {/* Recent Files Table */}
        <section className="library-card" style={{ marginTop: 0 }}>
          <div className="library-toolbar">
            <div>
              <span className="eyebrow">ACTIVITY STREAM</span>
              <h2>Recent Workspace Files</h2>
            </div>
            <Link href="/documents" className="btn secondary" style={{ textDecoration: "none" }}>
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
              <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--muted)" }}>
                <p style={{ margin: "0 0 6px", fontSize: "13px", fontWeight: 500 }}>No files deposited in this workspace yet.</p>
                <small style={{ fontSize: "11px" }}>Deposit a file above to begin RapidOCR ingestion, classification, and validation.</small>
              </div>
            ) : (
              recentDocs.map((d) => (
                <Link className="lib-row" key={d.id} href={`/documents/${d.id}`}>
                  <span className="doc-name">
                    <span className="doc-icon">
                      <Icon name="file" />
                    </span>
                    <b>{d.name}</b>
                  </span>
                  <code>{d.id}</code>
                  <span>{d.date}</span>
                  <span>{d.type}</span>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <Badge tone={d.status === "NEEDS REVIEW" ? "amber" : "green"}>
                      {d.conf}
                    </Badge>
                    <small style={{ color: "var(--muted)", fontSize: "10px" }}>{d.status}</small>
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
