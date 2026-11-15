"use client";

import React, { useState } from "react";

export type PaperType = "invoice" | "receipt" | "identity" | "contract" | "general";

interface PaperStageProps {
  type?: PaperType;
  fileUrl?: string | null;
  fileName?: string;
  annotations?: Array<{
    id: string;
    label: string;
    uncertain?: boolean;
    top: number | string;
    left: number | string;
    width: number | string;
    height: number | string;
  }>;
  extractedValues?: Record<string, string | number | null | undefined>;
}

export function InvoicePaper({
  extractedValues,
}: {
  extractedValues?: Record<string, string | number | null | undefined>;
  fileName?: string;
}) {
  const invNumber =
    String(extractedValues?.invoice_number || extractedValues?.invoice_id || "—");
  const invDate = String(extractedValues?.invoice_date || "—");
  const supplier = String(extractedValues?.supplier_name || extractedValues?.vendor || "Vendor / Supplier");
  const totalAmount = String(extractedValues?.total_amount || "—");

  return (
    <div className="invoice-paper">
      <div className="invoice-top">
        <div>
          <b>ad4tech</b>
          <small>MATERIAL SOLUTIONS</small>
        </div>
        <h3>Invoice</h3>
      </div>
      <hr />
      <div className="invoice-cols">
        <div>
          <small>ISSUED BY</small>
          <b>{supplier}</b>
          <p>
            1200 Industrial Parkway
            <br />
            Austin, TX 78758, United States
            <br />
            Tax ID: US-84-7629103
          </p>
        </div>
        <div>
          <small>INVOICE NUMBER</small>
          <code>{invNumber}</code>
          <p>
            Issued: {invDate}
            <br />
            Due: 2024-10-24
          </p>
        </div>
      </div>
      <div className="bill">
        <small>BILL TO</small>
        <b>Acme Global Enterprise</b>
        <p>
          Finance &amp; Procurement Department
          <br />
          450 Mission Street, San Francisco, CA 94105
        </p>
      </div>
      <div className="mini-table">
        <b>
          DESCRIPTION <span>QTY &nbsp;&nbsp; RATE &nbsp;&nbsp; AMOUNT</span>
        </b>
        <p>
          Industrial material supply <span>12 &nbsp; $95.00 &nbsp; $1,140.00</span>
        </p>
        <p>
          Packaging &amp; handling <span>1 &nbsp; $240.00 &nbsp; $240.00</span>
        </p>
        <p>
          Freight &amp; delivery <span>1 &nbsp; $100.00 &nbsp; $100.00</span>
        </p>
      </div>
      <div className="invoice-total">
        <span>Payment terms: Net 30</span>
        <b>
          Total due &nbsp; <code>{totalAmount}</code>
        </b>
      </div>
      <div className="annotation a1" title="Vendor details linked to supplier DB" />
      <div className="annotation a2" title="Invoice identifier validated" />
      <div className="annotation a3" title="Total amount matched against subtotal" />
    </div>
  );
}

export function ReceiptPaper({
  extractedValues,
}: {
  extractedValues?: Record<string, string | number | null | undefined>;
}) {
  const merchant = String(extractedValues?.merchant || extractedValues?.vendor || "SKYLINE BUSINESS HOTEL");
  const date = String(extractedValues?.date || extractedValues?.receipt_date || "08/28/2024 07:36");
  const total = String(extractedValues?.total || extractedValues?.total_amount || "$286.50");
  const tax = String(extractedValues?.tax || "36.50");

  return (
    <div className="receipt-paper">
      <b>{merchant.toUpperCase()}</b>
      <small>
        BUSINESS HOTEL &amp; TRAVEL SUITES
        <br />
        210 N Michigan Ave, Chicago IL
        <br />
        Tel: (312) 555-0198
      </small>
      <hr />
      <p>
        DATE <span>{date}</span>
        <br />
        RECEIPT <span>SK-008298</span>
        <br />
        GUEST <span>SOHAM DOSHI</span>
        <br />
        ROOM <span>614</span>
      </p>
      <hr />
      <p>
        ROOM CHARGE (1 NIGHT) <span>250.00</span>
        <br />
        STATE &amp; CITY TAX <span>{tax}</span>
      </p>
      <strong>
        TOTAL USD <span>{total}</span>
      </strong>
      <small>
        VISA **** 4208 · APPROVED
        <br />
        <br />
        THANK YOU FOR YOUR STAY
      </small>
      <i className="uncertain u1" title="Uncertain OCR character scan" />
      <i className="uncertain u2" title="Tax sub-calculation requires check" />
    </div>
  );
}

export function IdentityPaper({
  extractedValues,
}: {
  extractedValues?: Record<string, string | number | null | undefined>;
}) {
  const name = String(extractedValues?.full_name || extractedValues?.holder || "KLAUS REINHARDT");
  const idNumber = String(extractedValues?.id_number || extractedValues?.document_number || "T220001293");
  const authority = String(extractedValues?.authority || extractedValues?.issuer || "FEDERAL REPUBLIC OF GERMANY");

  return (
    <div className="receipt-paper" style={{ transform: "none", margin: "24px auto", background: "#fcfbf7" }}>
      <b>{authority.toUpperCase()}</b>
      <small style={{ letterSpacing: "1px" }}>STATE IDENTITY CREDENTIAL</small>
      <hr />
      <p>
        HOLDER <span>{name.toUpperCase()}</span>
        <br />
        DOC NO. <span>{idNumber}</span>
        <br />
        ISSUED <span>BERLIN · DE</span>
      </p>
      <hr />
      <p>
        NATIONALITY <span>DEUTSCH</span>
        <br />
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

export function ContractPaper({
  extractedValues,
}: {
  extractedValues?: Record<string, string | number | null | undefined>;
}) {
  const partyA = String(extractedValues?.party_a || "Party A");
  const partyB = String(extractedValues?.party_b || "Party B");
  const jurisdiction = String(extractedValues?.jurisdiction || "Designated Jurisdiction");

  return (
    <div className="invoice-paper" style={{ fontFamily: "'Inter', sans-serif" }}>
      <div style={{ textAlign: "center", borderBottom: "1px solid var(--line2)", paddingBottom: "12px", marginBottom: "16px" }}>
        <b style={{ fontSize: "14px", letterSpacing: "1px", textTransform: "uppercase" }}>MASTER SERVICES AGREEMENT</b>
        <p style={{ margin: "4px 0 0", fontSize: "8px", color: "var(--muted)" }}>CONFIDENTIAL ARCHIVAL COVENANT</p>
      </div>
      <p style={{ fontSize: "8px", lineHeight: "1.6", margin: "0 0 12px", color: "var(--body)" }}>
        This Master Agreement is entered into by and between <b>{partyA}</b> (&ldquo;Client&rdquo;) and <b>{partyB}</b> (&ldquo;Contractor&rdquo;).
      </p>
      <div style={{ background: "var(--side)", padding: "10px", borderRadius: "4px", fontSize: "7px", marginBottom: "12px" }}>
        <b>SECTION 4.1 · GOVERNING LAW &amp; JURISDICTION</b>
        <p style={{ margin: "4px 0 0" }}>This Covenant shall be governed by and construed in accordance with the laws of {jurisdiction}.</p>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: "40px", paddingTop: "12px", borderTop: "1px solid var(--line2)", fontSize: "7px" }}>
        <div>
          <span>AUTHORIZED SIGNATORY</span>
          <br />
          <b>Jane Doe · Vice President</b>
        </div>
        <div style={{ textAlign: "right" }}>
          <span>TIMESTAMPED AUDIT HASH</span>
          <br />
          <code>0x882a...91f2</code>
        </div>
      </div>
    </div>
  );
}

export function PaperStage({
  type = "invoice",
  fileUrl,
  fileName,
  extractedValues,
}: PaperStageProps) {
  const [zoom, setZoom] = useState<number>(100);
  const [rotation, setRotation] = useState<number>(0);
  const [showRaw, setShowRaw] = useState<boolean>(false);

  const zoomIn = () => setZoom((z) => Math.min(180, z + 15));
  const zoomOut = () => setZoom((z) => Math.max(60, z - 15));
  const resetZoom = () => {
    setZoom(100);
    setRotation(0);
  };
  const rotateDoc = () => setRotation((r) => (r + 90) % 360);

  return (
    <div className="viewer" style={{ display: "flex", flexDirection: "column" }}>
      <div className="viewer-bar">
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <button
            type="button"
            onClick={zoomOut}
            aria-label="Zoom out"
            style={{ background: "none", border: "none", padding: "2px 6px", cursor: "pointer" }}
          >
            −
          </button>
          <code>{zoom}%</code>
          <button
            type="button"
            onClick={zoomIn}
            aria-label="Zoom in"
            style={{ background: "none", border: "none", padding: "2px 6px", cursor: "pointer" }}
          >
            ＋
          </button>
          <span style={{ color: "var(--line2)", margin: "0 4px" }}>|</span>
          <button
            type="button"
            onClick={resetZoom}
            style={{ background: "none", border: "none", fontSize: "10px", cursor: "pointer" }}
          >
            Fit
          </button>
          <button
            type="button"
            onClick={rotateDoc}
            title="Rotate 90°"
            aria-label="Rotate document"
            style={{ background: "none", border: "none", fontSize: "11px", cursor: "pointer" }}
          >
            ↻
          </button>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {fileUrl && (
            <button
              type="button"
              onClick={() => setShowRaw(!showRaw)}
              style={{
                background: showRaw ? "var(--brand-surface)" : "transparent",
                color: showRaw ? "var(--brand)" : "var(--body)",
                border: "1px solid var(--line)",
                borderRadius: "4px",
                padding: "2px 8px",
                fontSize: "10px",
                cursor: "pointer",
              }}
            >
              {showRaw ? "Simulated View" : "Live Scan"}
            </button>
          )}
          {fileUrl && (
            <a
              href={fileUrl}
              target="_blank"
              rel="noreferrer"
              title="Download source file"
              style={{ color: "inherit", textDecoration: "none" }}
            >
              ⇩
            </a>
          )}
        </div>
      </div>

      <div
        className="paper-stage"
        style={{
          flex: 1,
          overflow: "auto",
          transform: `scale(${zoom / 100}) rotate(${rotation}deg)`,
          transformOrigin: "center center",
          transition: "transform 0.15s ease",
        }}
      >
        {fileUrl && showRaw ? (
          <div style={{ width: "100%", height: "100%", minHeight: "440px" }}>
            {fileUrl.endsWith(".pdf") ? (
              <iframe
                src={fileUrl}
                title="Source PDF File"
                style={{ width: "100%", height: "100%", minHeight: "440px", border: "none" }}
              />
            ) : (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={fileUrl}
                alt="Source Document File"
                style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain", margin: "auto" }}
              />
            )}
          </div>
        ) : type === "receipt" ? (
          <ReceiptPaper extractedValues={extractedValues} />
        ) : type === "identity" ? (
          <IdentityPaper extractedValues={extractedValues} />
        ) : type === "contract" ? (
          <ContractPaper extractedValues={extractedValues} />
        ) : (
          <InvoicePaper extractedValues={extractedValues} fileName={fileName} />
        )}
      </div>
    </div>
  );
}
