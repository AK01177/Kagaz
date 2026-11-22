"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Header, Footer } from "./Header";
import { useAuth } from "./context/AuthContext";
import { formatDate } from "./classification";

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
      <main className="page" style={{ background: "#FFFFFF" }}>
        {/* Hero Section */}
        <div className="landing-hero" style={{ background: "#FFFFFF" }}>
          <div className="section-mark">§ 00 · ARCHIVAL DOCUMENT INTELLIGENCE</div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: "24px", marginTop: "24px" }}>
            <div>
              <h1>
                From unstructured files to <em>clearer workflows.</em>
              </h1>
              <p>
                Kagaz accepts documents, extracts text and fields, classifies them when AI services are configured, and supports policy checks and review workflows.
              </p>
            </div>
            <div className="spec">SPEC: PDF · PNG · JPG · JPEG · TAXONOMY V2.4 · 10 MB CEILING</div>
          </div>

          <div className="cta-row" style={{ marginTop: "12px" }}>
            <Link href="/documents" className="button" style={{ textDecoration: "none", padding: "14px 24px", fontSize: "13px" }}>
              Deposit File into Intake ↥
            </Link>
            <Link href="/review" className="button secondary" style={{ textDecoration: "none", padding: "14px 22px", fontSize: "13px" }}>
              Open Human Verification Queue →
            </Link>
            <Link href="/login" className="button secondary" style={{ textDecoration: "none", padding: "14px 18px", fontSize: "13px" }}>
              Sign In to Workspace
            </Link>
          </div>
        </div>

        {/* 3 Pillars of the Kagaz Engine */}
        <section className="landing-features">
          <div className="feature-card" style={{ background: "#FFFFFF", border: "1px solid var(--line)" }}>
            <span className="feature-num">01 · INGESTION &amp; EXTRACTION</span>
            <h3>Strict File Intake</h3>
            <p>
              PDF and image files are checked and stored locally by default. Text extraction uses PDF text when available and OCR for scanned pages and images.
            </p>
            <div style={{ marginTop: "20px" }}>
              <Link href="/documents" style={{ color: "var(--brand)", fontSize: "12px", textDecoration: "none", fontWeight: 500 }}>
                Test Intake Dropzone →
              </Link>
            </div>
          </div>

          <div className="feature-card" style={{ background: "#FFFFFF", border: "1px solid var(--line)" }}>
            <span className="feature-num">02 · AI CLASSIFICATION</span>
            <h3>Deterministic Taxonomy</h3>
            <p>
              Automated classification into commercial invoices, legal contracts, HR records, academic transcripts, and financial filings with real-time confidence scores.
            </p>
            <div style={{ marginTop: "20px" }}>
              <Link href="/documents" style={{ color: "var(--brand)", fontSize: "12px", textDecoration: "none", fontWeight: 500 }}>
                Open File Repository →
              </Link>
            </div>
          </div>

          <div className="feature-card" style={{ background: "#FFFFFF", border: "1px solid var(--line)" }}>
            <span className="feature-num">03 · HUMAN VERIFICATION</span>
            <h3>Reviewer Override Desk</h3>
            <p>
              Documents can be routed through review and approval workflows. Reviewers can add comments and request changes; the review screen links to document details for the source file.
            </p>
            <div style={{ marginTop: "20px" }}>
              <Link href="/review" style={{ color: "var(--brand)", fontSize: "12px", textDecoration: "none", fontWeight: 500 }}>
                Launch Review Ledger →
              </Link>
            </div>
          </div>
        </section>

        {/* Manifesto Quote */}
        <section className="manifesto-quote" style={{ background: "#FFFFFF", borderTop: "1px solid var(--line)", borderBottom: "1px solid var(--line)" }}>
          <blockquote>
            &ldquo;Classification is derived from document structure, legal covenants, and semantic markers &mdash; not filename alone.&rdquo;
          </blockquote>
          <cite style={{ color: "var(--brand)" }}>Kagaz Archival Standard · Rule 12.B</cite>
        </section>

        {/* Live Workspace Ledger Sample */}
        <section className="ledger-section" style={{ marginTop: "40px" }}>
          <div className="section-heading">
            <div>
              <span>ACTIVE ARCHIVAL LEDGER</span>
              <h2>Recent Workspace Files</h2>
            </div>
            <Link href="/documents" style={{ color: "var(--brand)" }}>Enter full workspace →</Link>
          </div>

          <div className="table" style={{ background: "#FFFFFF", border: "1px solid var(--line)" }}>
            <div className="tr th" style={{ background: "#FFFFFF", borderBottom: "1px solid var(--line)" }}>
              <span>File name</span>
              <span>Unique ID</span>
              <span>Timestamp</span>
              <span>Detected genre</span>
              <span style={{ textAlign: "right" }}>Action</span>
            </div>

            {loadingFiles ? (
              <div style={{ padding: "32px 20px", textAlign: "center", color: "var(--muted)" }}>
                Loading recent files...
              </div>
            ) : recentFiles.length === 0 ? (
              <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--muted)" }}>
                <p style={{ margin: "0 0 6px", fontSize: "13px", fontWeight: 500 }}>No files deposited in this workspace yet.</p>
                <small style={{ fontSize: "11px" }}>Deposit a file in the Intake dropzone to begin extraction and classification.</small>
              </div>
            ) : (
              recentFiles.map((file, idx) => (
                <Link key={file.id} href={`/documents/${file.id}`} className="tr" style={{ background: "#FFFFFF", borderBottom: "1px solid var(--line)" }}>
                  <span className="file-name">
                    <b>{String(idx + 1).padStart(2, "0")}</b> {file.name}
                  </span>
                  <code>{file.id}</code>
                  <code>{file.date}</code>
                  <span>{file.category}</span>
                  <span className="inspect" style={{ color: "var(--brand)" }}>Inspect File →</span>
                </Link>
              ))
            )}
          </div>
        </section>

        {/* Call to action card */}
        <div style={{ marginTop: "64px", padding: "40px", background: "#FFFFFF", border: "1px solid var(--line)", textAlign: "center", borderRadius: "8px" }}>
          <h2 style={{ font: "400 34px 'Newsreader', serif", color: "var(--ink)", marginBottom: "12px" }}>
            Ready to index enterprise files?
          </h2>
          <p style={{ color: "var(--muted)", maxWidth: "540px", margin: "0 auto 24px", fontSize: "14px" }}>
            Experience document intake, confidence-based routing, and reviewer verification in action.
          </p>
          <div style={{ display: "flex", gap: "12px", justifyContent: "center", flexWrap: "wrap" }}>
            <Link href="/documents" className="button" style={{ textDecoration: "none", padding: "12px 22px" }}>
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
