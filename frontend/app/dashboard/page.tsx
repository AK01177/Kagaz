"use client";

import Link from "next/link";
import { AppShell, Badge, Icon } from "../components/AppShell";

export default function DashboardPage() {
  const stats = [
    { label: "FILES INTAKEN", value: "128", tone: "violet" },
    { label: "AUTO-CLEARED", value: "91.4%", tone: "green" },
    { label: "AWAITING VERIFICATION", value: "4", tone: "amber" },
    { label: "APPROVALS PENDING", value: "2", tone: "violet" },
  ];

  const recentFiles = [
    {
      name: "commercial_invoice_september.pdf",
      id: "doc_demo_8823f9",
      date: "24 Sep 2024 · 14:32",
      type: "Commercial Invoice",
      conf: "97.4%",
      status: "EXTRACTED",
    },
    {
      name: "travel_expense_aug.pdf",
      id: "doc_demo_74a2c1",
      date: "24 Sep 2024 · 09:42",
      type: "Financial Report",
      conf: "58.2%",
      status: "NEEDS REVIEW",
    },
    {
      name: "vendor_master_agreement.pdf",
      id: "doc_62ad119c",
      date: "23 Sep 2024 · 09:18",
      type: "Legal Contract",
      conf: "92.1%",
      status: "CLASSIFIED",
    },
    {
      name: "candidate_record_024.pdf",
      id: "doc_307fa912",
      date: "21 Sep 2024 · 17:06",
      type: "HR Record",
      conf: "88.7%",
      status: "CLASSIFIED",
    },
  ];

  return (
    <AppShell>
      <header className="page-head">
        <div className="crumb">
          <Icon name="grid" size={14} /> Workspace <span>/</span> Overview
          <div className="sync">
            <span className="brand-dot" /> Synced just now
          </div>
        </div>
        <div className="head-main">
          <div>
            <h1>Workspace Overview</h1>
            <p className="subline">ACME GLOBAL ENTERPRISE · INTELLIGENCE HUB</p>
          </div>
          <Link href="/documents" className="btn primary" style={{ textDecoration: "none" }}>
            Deposit New File ↥
          </Link>
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
                }}
              >
                {s.label}
              </span>
              <strong
                style={{
                  display: "block",
                  fontSize: "24px",
                  fontFamily: "'JetBrains Mono', monospace",
                  color: s.tone === "amber" ? "var(--amber)" : s.tone === "green" ? "var(--green)" : "var(--ink)",
                }}
              >
                {s.value}
              </strong>
            </div>
          ))}
        </div>

        {/* Verification Alert Callout */}
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
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <Icon name="stamp" size={18} />
            <div>
              <b style={{ color: "var(--amber)", fontSize: "12px" }}>4 files require human verification</b>
              <p style={{ margin: "4px 0 0", color: "#8b744e", fontSize: "11px" }}>
                Low confidence OCR extractions or policy variances have been routed to the Verification Desk.
              </p>
            </div>
          </div>
          <Link href="/review" className="btn primary" style={{ textDecoration: "none" }}>
            Open Verification Desk →
          </Link>
        </div>

        {/* Recent Files Table */}
        <section className="library-card" style={{ marginTop: 0 }}>
          <div className="library-toolbar">
            <div>
              <span className="eyebrow">ACTIVITY STREAM</span>
              <h2>Recent Workspace Files</h2>
            </div>
            <Link href="/documents" className="btn secondary" style={{ textDecoration: "none" }}>
              View All 128 Files →
            </Link>
          </div>

          <div className="library-table">
            <div className="lib-row lib-head">
              <span>FILE NAME</span>
              <span>UNIQUE ID</span>
              <span>UPLOADED</span>
              <span>CLASSIFICATION</span>
              <span>STATUS</span>
            </div>

            {recentFiles.map((d) => (
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
                <Badge tone={d.status === "NEEDS REVIEW" ? "amber" : "green"}>
                  {d.status}
                </Badge>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
