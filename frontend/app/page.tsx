"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Header, Footer } from "./Header";
import { useAuth } from "./context/AuthContext";
import { formatDate } from "./classification";
import { Icon } from "./components/AppShell";

interface RecentFile {
  id: string;
  name: string;
  date: string;
  category: string;
}

export default function HomePage() {
  const { isAuthenticated, fetchWithAuth } = useAuth();
  const [recentFiles, setRecentFiles] = useState<RecentFile[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) return;
    let isMounted = true;
    async function fetchRecent() {
      setLoadingFiles(true);
      try {
        const res = await fetchWithAuth("/api/documents");
        if (res.ok) {
          const data = await res.json().catch(() => null);
          const list = Array.isArray(data) ? data : data?.documents || [];
          if (isMounted) {
            setRecentFiles(
              list.slice(0, 5).map((d: { id?: string; document_id?: string; filename?: string; name?: string; created_at?: string; category?: string; document_type?: string }) => ({
                id: d.document_id || d.id || "",
                name: d.filename || d.name || "Untitled File",
                date: d.created_at ? formatDate(d.created_at) : "Recently added",
                category: d.category || d.document_type || "Classified Document",
              }))
            );
          }
        }
      } catch {
        // Honest fallback - empty state
      } finally {
        if (isMounted) setLoadingFiles(false);
      }
    }
    fetchRecent();
    return () => {
      isMounted = false;
    };
  }, [isAuthenticated, fetchWithAuth]);

  return (
    <>
      <Header />
      <main className="page">
        {/* Hero Section */}
        <div className="landing-hero">
          <div className="section-mark">
            <Icon name="shield" size={13} /> § 00 · ARCHIVAL DOCUMENT INTELLIGENCE
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: "24px", marginTop: "24px" }}>
            <div>
              <h1>
                From unstructured files to <em>clearer workflows.</em>
              </h1>
              <p>
                Kagaz ingests corporate filings, extracts key-value schemas, classifies genres via deterministic AI, and powers automated policy governance loops.
              </p>
            </div>
            <div className="spec">
              SPEC: PDF · PNG · JPG · JPEG · TAXONOMY V2.4 · 10 MB CEILING
            </div>
          </div>

          <div className="cta-row" style={{ marginTop: "24px" }}>
            <Link href="/workspace/documents" className="button primary" style={{ textDecoration: "none", padding: "12px 24px", fontSize: "13px" }}>
              <Icon name="inbox" size={15} /> Deposit File into Intake
            </Link>
            <Link href="/workspace/review" className="button secondary" style={{ textDecoration: "none", padding: "12px 20px", fontSize: "13px" }}>
              <Icon name="stamp" size={15} /> Open Verification Desk →
            </Link>
            <Link href="/login" className="button ghost" style={{ textDecoration: "none", padding: "12px 18px", fontSize: "13px" }}>
              Sign In to Workspace
            </Link>
          </div>
        </div>

        {/* 3 Pillars of the Kagaz Engine */}
        <section className="landing-features">
          <div className="feature-card">
            <span className="feature-num">01 · INGESTION &amp; EXTRACTION</span>
            <h3>Strict File Intake</h3>
            <p>
              PDF and high-resolution scans are verified and cached within your organization&apos;s enclave. Robust dual-engine pipeline extracts native digital text and runs local OCR for scanned imagery.
            </p>
            <div style={{ marginTop: "24px" }}>
              <Link href="/workspace/documents" style={{ color: "var(--brand)", fontSize: "12px", textDecoration: "none", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: "5px" }}>
                Test Intake Dropzone →
              </Link>
            </div>
          </div>

          <div className="feature-card">
            <span className="feature-num">02 · DETERMINISTIC TAXONOMY</span>
            <h3>AI Multi-Genre Classifier</h3>
            <p>
              Classifies commercial invoices, legal contracts, HR records, academic credentials, and regulatory filings with confidence scores and automated routing queues.
            </p>
            <div style={{ marginTop: "24px" }}>
              <Link href="/workspace/documents" style={{ color: "var(--brand)", fontSize: "12px", textDecoration: "none", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: "5px" }}>
                Open File Repository →
              </Link>
            </div>
          </div>

          <div className="feature-card">
            <span className="feature-num">03 · HUMAN VERIFICATION</span>
            <h3>Reviewer Override Desk</h3>
            <p>
              Flagged, low-confidence, or policy-violating documents route to human reviewers. Corrections, rationale notes, and certified decisions are logged into an immutable audit trail.
            </p>
            <div style={{ marginTop: "24px" }}>
              <Link href="/workspace/review" style={{ color: "var(--brand)", fontSize: "12px", textDecoration: "none", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: "5px" }}>
                Launch Verification Desk →
              </Link>
            </div>
          </div>
        </section>

        {/* Manifesto Quote */}
        <section className="manifesto-quote">
          <blockquote>
            &ldquo;Classification is derived from document structure, legal covenants, and semantic markers &mdash; not filename alone.&rdquo;
          </blockquote>
          <cite>Kagaz Archival Standard · Rule 12.B</cite>
        </section>

        {/* Live Workspace Ledger Sample */}
        <section className="ledger-section">
          <div className="section-heading">
            <div>
              <span>ACTIVE ARCHIVAL LEDGER</span>
              <h2>Recent Workspace Files</h2>
            </div>
            <Link href="/workspace/documents">Enter full workspace →</Link>
          </div>

          <div className="table">
            <div className="tr th">
              <span>File name</span>
              <span>Unique ID</span>
              <span>Timestamp</span>
              <span>Detected genre</span>
              <span style={{ textAlign: "right" }}>Action</span>
            </div>

            {loadingFiles ? (
              <div style={{ padding: "36px 20px", textAlign: "center", color: "var(--muted)" }}>
                Loading recent files...
              </div>
            ) : recentFiles.length === 0 ? (
              <div style={{ padding: "48px 20px", textAlign: "center", color: "var(--muted)" }}>
                <p style={{ margin: "0 0 6px", fontSize: "14px", fontWeight: 600, color: "var(--ink)" }}>No files deposited in this workspace yet.</p>
                <small style={{ fontSize: "12px", color: "var(--muted)" }}>Deposit a file in the Intake dropzone to begin extraction and classification.</small>
              </div>
            ) : (
              recentFiles.map((file, idx) => (
                <Link key={file.id} href={`/workspace/documents/${file.id}`} className="tr">
                  <span className="file-name">
                    <b>{String(idx + 1).padStart(2, "0")}</b> {file.name}
                  </span>
                  <code>{file.id}</code>
                  <span style={{ color: "var(--secondary)", fontSize: "12px" }}>{file.date}</span>
                  <span style={{ fontWeight: 500, color: "var(--ink)" }}>{file.category}</span>
                  <span className="inspect">Inspect File →</span>
                </Link>
              ))
            )}
          </div>
        </section>

        {/* Call to action card */}
        <div style={{
          marginTop: "64px",
          padding: "48px 36px",
          background: "linear-gradient(135deg, rgba(79, 70, 229, 0.04) 0%, rgba(14, 165, 233, 0.04) 100%), #FFFFFF",
          border: "1px solid var(--brand-border)",
          textAlign: "center",
          borderRadius: "14px",
          boxShadow: "var(--shadow-sm)"
        }}>
          <h2 style={{ font: "600 30px 'Newsreader', Georgia, serif", color: "var(--ink)", marginBottom: "10px" }}>
            Ready to index enterprise documents?
          </h2>
          <p style={{ color: "var(--secondary)", maxWidth: "560px", margin: "0 auto 24px", fontSize: "14px", lineHeight: 1.6 }}>
            Experience document intake, confidence-based routing, and reviewer verification in action.
          </p>
          <div style={{ display: "flex", gap: "12px", justifyContent: "center", flexWrap: "wrap" }}>
            <Link href="/workspace/documents" className="button primary" style={{ textDecoration: "none", padding: "12px 24px" }}>
              Start Document Intake →
            </Link>
            <Link href="/login" className="button secondary" style={{ textDecoration: "none", padding: "12px 20px" }}>
              Sign In to Your Workspace
            </Link>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
