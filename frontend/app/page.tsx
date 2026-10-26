import Link from "next/link";
import { Header, Footer } from "./Header";

export default function HomePage() {
  return (
    <>
      <Header />
      <main className="page">
        {/* Hero Section */}
        <div className="landing-hero">
          <div className="section-mark">§ 00 · ARCHIVAL DOCUMENT INTELLIGENCE</div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: "24px", marginTop: "24px" }}>
            <div>
              <h1>
                From unstructured files to <em>certified certainty.</em>
              </h1>
              <p>
                Kagaz transforms incoming documents into classified, policy-cleared, and permanently audited records through neural layout intelligence and accredited human judgment.
              </p>
            </div>
            <div className="spec">SPEC: MULTI-PAGE PDF · TAXONOMY V2.4 · 10 MB CEILING</div>
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
          <div className="feature-card">
            <span className="feature-num">01 · INGESTION &amp; EXTRACTION</span>
            <h3>Strict File Intake</h3>
            <p>
              Byte-level PDF verification, SHA-256 fingerprinting, layout analysis, and optical text extraction. Every document is anchored to an encrypted enterprise scope.
            </p>
            <div style={{ marginTop: "20px" }}>
              <Link href="/documents" style={{ color: "var(--sage)", fontSize: "12px", textDecoration: "none", fontWeight: 500 }}>
                Test Intake Dropzone →
              </Link>
            </div>
          </div>

          <div className="feature-card">
            <span className="feature-num">02 · NEURAL CLASSIFICATION</span>
            <h3>Deterministic Taxonomy</h3>
            <p>
              Automated classification into commercial invoices, legal contracts, HR records, academic transcripts, and financial filings with real-time confidence scores.
            </p>
            <div style={{ marginTop: "20px" }}>
              <Link href="/documents/doc_demo_8823f9" style={{ color: "var(--sage)", fontSize: "12px", textDecoration: "none", fontWeight: 500 }}>
                Inspect Demo File Result →
              </Link>
            </div>
          </div>

          <div className="feature-card">
            <span className="feature-num">03 · HUMAN VERIFICATION</span>
            <h3>Reviewer Override Desk</h3>
            <p>
              Low-confidence files are flagged with wax-seal alerts. Certified reviewers examine simulated scan excerpts, override categories, and stamp files with permanent audit trails.
            </p>
            <div style={{ marginTop: "20px" }}>
              <Link href="/review" style={{ color: "var(--sage)", fontSize: "12px", textDecoration: "none", fontWeight: 500 }}>
                Launch Review Ledger →
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
        <section className="ledger-section" style={{ marginTop: "40px" }}>
          <div className="section-heading">
            <div>
              <span>ACTIVE ARCHIVAL LEDGER</span>
              <h2>Recent Workspace Files</h2>
            </div>
            <Link href="/documents">Enter full workspace →</Link>
          </div>

          <div className="table">
            <div className="tr th">
              <span>File name</span>
              <span>Unique ID</span>
              <span>Timestamp</span>
              <span>Detected genre</span>
              <span style={{ textAlign: "right" }}>Action</span>
            </div>

            <Link href="/documents/doc_demo_8823f9" className="tr">
              <span className="file-name">
                <b>01</b>commercial_invoice_september.pdf
              </span>
              <code>doc_demo_8823f9</code>
              <code>24 Sep 2024 · 14:32</code>
              <span>Commercial Invoice</span>
              <span className="inspect">Inspect File →</span>
            </Link>

            <Link href="/documents/doc_62ad119c" className="tr">
              <span className="file-name">
                <b>02</b>vendor_master_agreement.pdf
              </span>
              <code>doc_62ad119c</code>
              <code>23 Sep 2024 · 09:18</code>
              <span>Legal Contract</span>
              <span className="inspect">Inspect File →</span>
            </Link>

            <Link href="/review?id=doc_qr_0184f" className="tr">
              <span className="file-name">
                <b>03</b>travel_expense_aug.pdf
              </span>
              <code>doc_qr_0184f</code>
              <code>Today · 09:42</code>
              <span style={{ color: "var(--red)" }}>Financial (Needs Review)</span>
              <span className="inspect" style={{ color: "var(--red)" }}>Verify Now →</span>
            </Link>
          </div>
        </section>

        {/* Call to action card */}
        <div style={{ marginTop: "64px", padding: "40px", background: "var(--paper)", border: "1px solid var(--line-dark)", textAlign: "center" }}>
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
