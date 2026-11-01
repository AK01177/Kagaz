"use client";

import { useState } from "react";
import Link from "next/link";
import { AppShell, Button, Badge, Icon } from "../components/AppShell";

interface ApprovalItem {
  id: string;
  name: string;
  type: string;
  amount: string;
  policy: string;
  policyStatus: "PASSED" | "FLAGGED";
  submitter: string;
  date: string;
}

const DEFAULT_APPROVALS: ApprovalItem[] = [
  {
    id: "doc_demo_8823f9",
    name: "commercial_invoice_september.pdf",
    type: "Commercial Invoice",
    amount: "$1,564.00",
    policy: "AP-Rule-04 (Tax Verification)",
    policyStatus: "PASSED",
    submitter: "usr_2098b7 (Procurement)",
    date: "Today · 14:32",
  },
  {
    id: "doc_demo_74a2c1",
    name: "travel_expense_aug.pdf",
    type: "Travel & Expense",
    amount: "$286.50",
    policy: "EXP-Rule-12 (Lodging Ceiling)",
    policyStatus: "PASSED",
    submitter: "usr_soham (Engineering)",
    date: "Today · 09:42",
  },
];

export default function ApprovalsPage() {
  const [items, setItems] = useState<ApprovalItem[]>(DEFAULT_APPROVALS);
  const [decisions, setDecisions] = useState<Record<string, "approved" | "rejected">>({});

  function handleDecision(id: string, decision: "approved" | "rejected") {
    setDecisions((prev) => ({ ...prev, [id]: decision }));
  }

  return (
    <AppShell>
      <header className="page-head">
        <div className="crumb">
          <Icon name="check" size={14} /> Workspace <span>/</span> Approval Ledger
          <div className="sync">
            <span className="brand-dot" /> Synced just now
          </div>
        </div>
        <div className="head-main">
          <div>
            <h1>Managerial Approval Ledger</h1>
            <p className="subline">AUTHORIZED GOVERNANCE · {items.length} FILES AWAITING DECISION</p>
          </div>
          <Button icon="sliders">Approval policies</Button>
        </div>
      </header>

      <div className="intake-body">
        <div className="library-card" style={{ marginTop: 0 }}>
          <div className="library-toolbar">
            <div>
              <span className="eyebrow">PENDING SIGN-OFF</span>
              <h2>Files Requiring Action</h2>
            </div>
            <span style={{ fontSize: "11px", color: "var(--muted)" }}>
              All approvals are cryptographically attributed to the signing authority.
            </span>
          </div>

          <div className="library-table">
            <div className="lib-row lib-head" style={{ gridTemplateColumns: "2fr 1fr 1fr 1.5fr 1.5fr" }}>
              <span>FILE NAME</span>
              <span>TYPE</span>
              <span>AMOUNT</span>
              <span>POLICY EVIDENCE</span>
              <span style={{ textAlign: "right" }}>DECISION</span>
            </div>

            {items.map((item) => {
              const decision = decisions[item.id];
              return (
                <div
                  key={item.id}
                  className="lib-row"
                  style={{ gridTemplateColumns: "2fr 1fr 1fr 1.5fr 1.5fr", cursor: "default" }}
                >
                  <span className="doc-name">
                    <span className="doc-icon">
                      <Icon name="file" />
                    </span>
                    <div>
                      <Link
                        href={`/documents/${item.id}`}
                        style={{ color: "var(--ink)", textDecoration: "none", fontWeight: 500 }}
                      >
                        {item.name}
                      </Link>
                      <small style={{ display: "block", color: "var(--muted)", fontSize: "10px" }}>
                        {item.submitter} · {item.date}
                      </small>
                    </div>
                  </span>

                  <span>{item.type}</span>
                  <code>{item.amount}</code>

                  <div>
                    <Badge tone={item.policyStatus === "PASSED" ? "green" : "amber"}>
                      {item.policyStatus}
                    </Badge>
                    <small style={{ display: "block", color: "var(--muted)", fontSize: "9px", marginTop: "3px" }}>
                      {item.policy}
                    </small>
                  </div>

                  <div style={{ display: "flex", gap: "6px", justifyContent: "flex-end" }}>
                    {decision ? (
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 600,
                          color: decision === "approved" ? "var(--green)" : "var(--red)",
                        }}
                      >
                        {decision === "approved" ? "✓ Approved & Stamped" : "✗ Rejected"}
                      </span>
                    ) : (
                      <>
                        <Button
                          variant="primary"
                          icon="check"
                          onClick={() => handleDecision(item.id, "approved")}
                        >
                          Approve
                        </Button>
                        <Button
                          variant="secondary"
                          onClick={() => handleDecision(item.id, "rejected")}
                        >
                          Reject
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
