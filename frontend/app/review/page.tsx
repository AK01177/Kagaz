"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell, Button, Badge, Icon, IconName } from "../components/AppShell";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

interface ReviewField {
  field: string;
  val: string;
  conf: string;
}

interface QueueItem {
  id: string;
  name: string;
  time: string;
  score: string;
  state: string;
  icon: IconName;
  docType: "receipt" | "identity" | "invoice" | "contract" | "general";
  verified?: boolean;
  fields: ReviewField[];
}

const DEFAULT_QUEUE_DOCS: QueueItem[] = [
  {
    id: "doc_demo_74a2c1",
    name: "travel_expense_aug.pdf",
    time: "09:42",
    score: "58.2%",
    state: "Needs Human Review",
    icon: "receipt",
    docType: "receipt",
    fields: [
      { field: "Merchant", val: "Skyline Business Hotel", conf: "62%" },
      { field: "Receipt date", val: "2024-08-28", conf: "54%" },
      { field: "Total amount", val: "$286.50", conf: "48%" },
      { field: "Currency", val: "USD", conf: "99%" },
      { field: "Expense category", val: "Travel & Lodging", conf: "84%" },
    ],
  },
  {
    id: "doc_qr_0284f",
    name: "identity_scan_0041.pdf",
    time: "08:15",
    score: "71.4%",
    state: "Ambiguous",
    icon: "contact",
    docType: "identity",
    fields: [
      { field: "Document holder", val: "Klaus Reinhardt", conf: "74%" },
      { field: "ID number", val: "T220001293", conf: "68%" },
      { field: "Issuing authority", val: "Federal Republic of Germany", conf: "82%" },
      { field: "Document type", val: "Personalausweis (ID)", conf: "71%" },
      { field: "Validity date", val: "2031-08-14", conf: "62%" },
    ],
  },
  {
    id: "doc_qr_0384f",
    name: "supplier_invoice_88.pdf",
    time: "Yesterday",
    score: "86.9%",
    state: "Standard",
    icon: "file",
    docType: "invoice",
    fields: [
      { field: "Vendor", val: "Alpine Hardware GmbH", conf: "88%" },
      { field: "Client", val: "Kagaz Technologies", conf: "92%" },
      { field: "Invoice reference", val: "INV-88-2024", conf: "89%" },
      { field: "Total VAT incl", val: "$14,950.00", conf: "86%" },
      { field: "Payment terms", val: "Net 15", conf: "79%" },
    ],
  },
  {
    id: "doc_qr_0484f",
    name: "nda_executed_final.pdf",
    time: "Yesterday",
    score: "✓ 100%",
    state: "Certified",
    icon: "check",
    docType: "contract",
    verified: true,
    fields: [
      { field: "Disclosing party", val: "Kagaz Systems Inc.", conf: "98%" },
      { field: "Receiving party", val: "Apex Dynamics LLC", conf: "97%" },
      { field: "Term length", val: "36 Months Confidentiality", conf: "95%" },
      { field: "Governing law", val: "Frankfurt am Main, Germany", conf: "99%" },
      { field: "Execution date", val: "2024-09-22", conf: "94%" },
    ],
  },
];

/* Dynamic Excerpt Canvas for the active document */
function DynamicExcerpt({ item }: { item: QueueItem }) {
  if (item.docType === "identity") {
    const holder = item.fields.find((f) => f.field.includes("holder"))?.val || "Klaus Reinhardt";
    const idNum = item.fields.find((f) => f.field.includes("number"))?.val || "T220001293";
    const auth = item.fields.find((f) => f.field.includes("authority"))?.val || "Federal Republic of Germany";

    return (
      <div className="receipt-paper" style={{ transform: "none", margin: "24px auto", background: "#fcfbf7" }}>
        <b>{auth.toUpperCase()}</b>
        <small style={{ letterSpacing: "1px" }}>STATE IDENTITY CREDENTIAL</small>
        <hr />
        <p>
          HOLDER <span>{holder.toUpperCase()}</span><br />
          DOC NO. <span>{idNum}</span><br />
          ISSUED <span>BERLIN · DE</span>
        </p>
        <hr />
        <p>
          NATIONALITY <span>DEUTSCH</span><br />
          EXPIRY <span>2031-08-14</span>
        </p>
        <strong>
          AUTHENTICATED EXCERPT <span>VERIFIED</span>
        </strong>
        <small>OCR SCAN ACCREDITATION LEVEL 2</small>
        <i className="uncertain" style={{ top: "105px", right: "16px", width: "110px", height: "18px" }} />
      </div>
    );
  }

  if (item.docType === "invoice") {
    const vendor = item.fields.find((f) => f.field.includes("Vendor"))?.val || "Alpine Hardware GmbH";
    const total = item.fields.find((f) => f.field.includes("Total"))?.val || "$14,950.00";
    const ref = item.fields.find((f) => f.field.includes("reference"))?.val || "INV-88-2024";

    return (
      <div className="receipt-paper" style={{ transform: "none", margin: "24px auto" }}>
        <b>{vendor.toUpperCase()}</b>
        <small>COMMERCIAL TAX INVOICE</small>
        <hr />
        <p>
          INVOICE NO <span>{ref}</span><br />
          CLIENT <span>KAGAZ TECH</span><br />
          TERMS <span>NET 15</span>
        </p>
        <hr />
        <strong>
          TOTAL BALANCE <span>{total}</span>
        </strong>
        <small>TAX INVOICE EXCERPT · HIGH FIDELITY</small>
      </div>
    );
  }

  if (item.docType === "contract") {
    const parties = item.fields.find((f) => f.field.includes("party"))?.val || "Kagaz Systems & Apex";
    const term = item.fields.find((f) => f.field.includes("Term"))?.val || "36 Months";

    return (
      <div className="receipt-paper" style={{ transform: "none", margin: "24px auto" }}>
        <b>MUTUAL NON-DISCLOSURE</b>
        <small>LEGAL COVENANT EXCERPT</small>
        <hr />
        <p>
          PARTIES <span>{parties}</span><br />
          COVENANT <span>CONFIDENTIALITY</span><br />
          DURATION <span>{term}</span>
        </p>
        <hr />
        <strong>
          LEGAL GOVERNANCE <span>CLEARANCE PASSED</span>
        </strong>
        <small>PERMANENT ARCHIVAL SEAL AFFIXED</small>
      </div>
    );
  }

  // Default Receipt Excerpt
  return (
    <div className="receipt-paper">
      <b>SKYLINE</b>
      <small>
        BUSINESS HOTEL<br />
        210 N Michigan Ave, Chicago IL<br />
        Tel: (312) 555-0198
      </small>
      <hr />
      <p>
        DATE <span>08/28/2024　07:36</span><br />
        RECEIPT <span>SK-008298</span><br />
        GUEST <span>SOHAM DOSHI</span><br />
        ROOM <span>614</span>
      </p>
      <hr />
      <p>
        ROOM CHARGE (1 NIGHT) <span>250.00</span><br />
        STATE &amp; CITY TAX <span>36.50</span>
      </p>
      <strong>
        TOTAL USD <span>286.50</span>
      </strong>
      <small>
        VISA **** 4208 · APPROVED<br />
        <br />
        THANK YOU FOR YOUR STAY
      </small>
      <i className="uncertain u1" />
      <i className="uncertain u2" />
    </div>
  );
}

function EmptyQueueView({ onReset }: { onReset: () => void }) {
  return (
    <div className="empty-wrap">
      <div className="empty-card">
        <div className="empty-head">
          <div>
            <h2>Verification Desk</h2>
            <span>HUMAN VERIFICATION QUEUE · 0 PENDING</span>
          </div>
          <code>● Ingestion idle.</code>
        </div>
        <div className="empty-center">
          <div className="paper-stack">
            <span />
            <b>✓</b>
          </div>
          <h1>All documents verified.</h1>
          <p>
            Nothing needs your attention. New documents will appear here when they’re ready for a human review.
          </p>
          <div style={{ display: "flex", gap: "10px" }}>
            <Link href="/documents" className="btn secondary" style={{ textDecoration: "none" }}>
              Intake Dropzone →
            </Link>
            <Button icon="check" onClick={onReset}>
              Reset Demo Queue
            </Button>
          </div>
        </div>
        <div className="empty-metrics">
          <div>
            <code>12</code>
            <span>Certified today</span>
          </div>
          <div>
            <code>0</code>
            <span>Awaiting review</span>
          </div>
          <div>
            <code>14:36 UTC</code>
            <span>Last certification</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ReviewPage() {
  const [queue, setQueue] = useState<QueueItem[]>(DEFAULT_QUEUE_DOCS);
  const [active, setActive] = useState(0);
  const [filter, setFilter] = useState<"all" | "review" | "low" | "verified">("all");
  const [search, setSearch] = useState("");
  const [showEmpty, setShowEmpty] = useState(false);
  const [savedNotice, setSavedNotice] = useState(false);

  // Load newly uploaded files from sessionStorage that require review
  useEffect(() => {
    try {
      const keys = Object.keys(sessionStorage).filter((k) => k.startsWith("kagaz_doc_"));
      const dynamicItems: QueueItem[] = [];
      for (const k of keys) {
        const item = JSON.parse(sessionStorage.getItem(k) || "{}");
        if (item && item.document_id && item.filename && !DEFAULT_QUEUE_DOCS.some((d) => d.id === item.document_id)) {
          const conf = item.confidence ? Number((item.confidence * 100).toFixed(1)) : 72.0;
          const isVerified = item.status === "REVIEWER_VERIFIED" || item.is_manually_corrected;
          dynamicItems.push({
            id: item.document_id,
            name: item.filename,
            time: "Recently Added",
            score: isVerified ? "✓ 100%" : `${conf}%`,
            state: isVerified ? "Certified" : conf < 75 ? "Needs Human Review" : "Standard",
            icon: item.category?.toLowerCase().includes("invoice") ? "file" : "receipt",
            docType: item.category?.toLowerCase().includes("invoice") ? "invoice" : "receipt",
            verified: isVerified,
            fields: [
              { field: "File name", val: item.filename, conf: "100%" },
              { field: "Document type", val: item.category || "Classified File", conf: `${conf}%` },
              { field: "Scope anchor", val: item.organization_id || "Acme Global Enterprise", conf: "99%" },
              { field: "Validation status", val: isVerified ? "Certified" : "Awaiting Human Sign-off", conf: isVerified ? "100%" : "68%" },
            ],
          });
        }
      }
      if (dynamicItems.length > 0) {
        setQueue([...dynamicItems, ...DEFAULT_QUEUE_DOCS]);
      }
    } catch {}
  }, []);

  const activeDoc = queue[active] || queue[0];

  function handleFieldChange(fieldIndex: number, newVal: string) {
    setQueue((prev) =>
      prev.map((item, idx) => {
        if (idx !== active) return item;
        const updatedFields = [...item.fields];
        updatedFields[fieldIndex] = { ...updatedFields[fieldIndex], val: newVal };
        return { ...item, fields: updatedFields };
      })
    );
  }

  function handleConfirmNext() {
    setSavedNotice(true);

    // Call backend API or persist to sessionStorage if real document
    if (activeDoc && activeDoc.id && !activeDoc.id.startsWith("doc_demo")) {
      try {
        const token =
          localStorage.getItem("kagaz_token") || sessionStorage.getItem("kagaz_token");
        fetch(`${API_URL}/api/documents/${activeDoc.id}/classification`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ category: activeDoc.fields[1]?.val || "Commercial Invoice", notes: "Verified in review desk" }),
        }).catch(() => {});

        const cached = sessionStorage.getItem(`kagaz_doc_${activeDoc.id}`);
        if (cached) {
          const parsed = JSON.parse(cached);
          sessionStorage.setItem(
            `kagaz_doc_${activeDoc.id}`,
            JSON.stringify({ ...parsed, status: "REVIEWER_VERIFIED", confidence: 1.0 })
          );
        }
      } catch {}
    }

    setQueue((prev) =>
      prev.map((item, idx) =>
        idx === active
          ? { ...item, score: "✓ 100%", state: "Certified", verified: true }
          : item
      )
    );

    setTimeout(() => {
      setSavedNotice(false);
      if (active < queue.length - 1) {
        setActive(active + 1);
      } else {
        setShowEmpty(true);
      }
    }, 600);
  }

  // Keyboard shortcut listener (Cmd+Enter / Ctrl+Enter)
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        handleConfirmNext();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [active, queue]);

  const filteredQueue = queue.filter((doc) => {
    if (search && !doc.name.toLowerCase().includes(search.toLowerCase())) return false;
    if (filter === "review") return doc.state.includes("Review") || doc.state.includes("Ambiguous");
    if (filter === "low") return parseFloat(doc.score) < 75 && !doc.verified;
    if (filter === "verified") return doc.verified;
    return true;
  });

  if (showEmpty) {
    return (
      <AppShell>
        <EmptyQueueView
          onReset={() => {
            setQueue(DEFAULT_QUEUE_DOCS);
            setActive(0);
            setShowEmpty(false);
          }}
        />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <header className="review-head">
        <div className="crumb">
          <Icon name="stamp" size={14} /> Workspace <span>/</span> Verification Desk
          <div className="sync">
            <span className="brand-dot" /> Synced just now
          </div>
        </div>
        <div className="head-main">
          <div>
            <h1>A human eye. A trusted record.</h1>
            <p className="subline">HUMAN VERIFICATION QUEUE · {queue.length} files requiring certification</p>
          </div>
          <Button icon="sliders" onClick={() => setShowEmpty(true)}>
            Queue preferences
          </Button>
        </div>
      </header>

      <div className="review-body">
        {/* Left Queue Rail */}
        <aside className="queue-rail">
          <div className="queue-filters">
            <label className="search">
              <Icon name="search" size={13} />
              <input
                placeholder="Find a document…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <kbd>⌘ K</kbd>
            </label>
            <div>
              <b
                style={{
                  cursor: "pointer",
                  background: filter === "all" ? "var(--violet-bg)" : undefined,
                  color: filter === "all" ? "var(--violet)" : undefined,
                }}
                onClick={() => setFilter("all")}
              >
                All ({queue.length})
              </b>
              <span
                style={{ cursor: "pointer", fontWeight: filter === "review" ? 600 : undefined }}
                onClick={() => setFilter("review")}
              >
                Needs Review ({queue.filter((q) => !q.verified && parseFloat(q.score) < 80).length})
              </span>
              <span
                style={{ cursor: "pointer", fontWeight: filter === "low" ? 600 : undefined }}
                onClick={() => setFilter("low")}
              >
                Low Conf. ({queue.filter((q) => !q.verified && parseFloat(q.score) < 75).length})
              </span>
              <span
                style={{ cursor: "pointer", fontWeight: filter === "verified" ? 600 : undefined }}
                onClick={() => setFilter("verified")}
              >
                Verified ({queue.filter((q) => q.verified).length})
              </span>
            </div>
          </div>

          <div className="queue-sort">
            <b>DOCUMENTS</b>
            <span>Oldest first ↯</span>
          </div>

          {filteredQueue.map((d, i) => {
            const isSelected = active === i;
            const isAmber = parseFloat(d.score) < 75 && !d.verified;
            return (
              <button
                type="button"
                className={`queue-doc ${isSelected ? "active" : ""}`}
                key={d.id}
                onClick={() => setActive(i)}
              >
                <div>
                  <Icon name={d.icon} />
                  <code>{d.time}</code>
                </div>
                <b>{d.name}</b>
                <p className={d.verified ? "green-text" : isAmber ? "amber-text" : "green-text"}>
                  <code>{d.score}</code> · {d.state}
                </p>
              </button>
            );
          })}

          <div className="queue-assigned">
            ♙ Assigned to you
            <small>All decisions are recorded in the ledger.</small>
          </div>
        </aside>

        {/* Right Active Review Pane */}
        <section className="active-review">
          <div className="active-head">
            <div>
              <h2>{activeDoc.name}</h2>
              <p>
                <code>{activeDoc.id}</code> · {activeDoc.docType.toUpperCase()} EXCERPT · 1 page
              </p>
            </div>
            <code>
              {active + 1} of {queue.length} &nbsp; ‹ &nbsp; ›
            </code>
          </div>

          <div className="warning">
            <Icon name="alert" />
            <div>
              <b>
                {activeDoc.verified
                  ? "✓ Record Verified and Certified by Reviewer."
                  : `AI Confidence (${activeDoc.score}) requires human verification before downstream ERP export.`}
              </b>
              <p>
                {activeDoc.verified
                  ? "Permanent audit trail affixed to ledger. Classification and field extractions locked at 100%."
                  : "Compare the OCR excerpt against detected fields. Edits are recorded in the permanent audit trail."}
              </p>
            </div>
          </div>

          <div className="correction-work">
            {/* Scanned Excerpt Viewer */}
            <div className="receipt-side">
              <div className="pane-title">
                <span>SCANNED EXCERPT</span>
                <code>1 / 1</code>
              </div>
              <div className="receipt-viewer">
                <div className="viewer-bar">
                  <span>−　100%　＋</span>
                  <span>⛶</span>
                </div>
                <DynamicExcerpt item={activeDoc} />
              </div>
              <p>Amber regions indicate uncertain OCR tokens. Compare the source before confirming.</p>
            </div>

            {/* Editable Field Correction Table */}
            <div className="correction-side">
              <div className="pane-title">
                <span>REVIEW &amp; CORRECT</span>
                <Badge tone={activeDoc.verified ? "green" : "amber"}>
                  {activeDoc.verified ? "Verified" : `${activeDoc.fields.length} fields`}
                </Badge>
              </div>

              <div className="edit-table">
                <div className="edit-head">
                  <b>FIELD / REVIEWED VALUE</b>
                  <b>AI CONF.</b>
                </div>
                {activeDoc.fields.map((f, i) => (
                  <label className="edit-row" key={f.field}>
                    <div>
                      <span>{f.field}</span>
                      <input
                        value={f.val}
                        onChange={(e) => handleFieldChange(i, e.target.value)}
                      />
                    </div>
                    <code className={parseInt(f.conf) < 75 && !activeDoc.verified ? "amber-text" : "green-text"}>
                      {activeDoc.verified ? "100%" : f.conf}
                    </code>
                  </label>
                ))}
              </div>

              <p className="history">
                <Icon name="history" size={12} /> Original values and reviewer edits are preserved in the audit trail.
              </p>
            </div>
          </div>

          {/* Review Actions Bar */}
          <div className="review-actions">
            <div>
              <Button
                variant="ghost"
                icon="flag"
                onClick={() => {
                  alert(`Flagged ${activeDoc.name} for senior compliance review.`);
                }}
              >
                Flag issue
              </Button>
              <Button onClick={() => setActive((prev) => (prev + 1) % queue.length)}>
                Skip for now
              </Button>
            </div>
            <div>
              <span>Press ⌘+Enter</span>
              <Button
                variant="primary"
                icon="check"
                onClick={handleConfirmNext}
              >
                {savedNotice ? "Confirmed ✓" : activeDoc.verified ? "Re-Certify" : "Confirm & Next"}
              </Button>
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
