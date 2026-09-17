# Kagaz – Stakeholder Documentation

## 1. Objective

Identify the key stakeholders who interact with, manage, govern, or depend on **Kagaz**, an AI-powered document workflow platform supporting the **Academic**, **HR**, and **Finance** domains across multiple organizations.

> **Note:** Developed for **IT314 – Software Engineering**. Stakeholder needs are based on standard organizational workflows and iterative requirement elicitation.

---

## 2. Stakeholders at a Glance

| Stakeholder | Category | Scope | Influence | Primary Goal |
|---|---|---|---|---|
| **Submitter** | End User | Org / Domain | Low | Quick upload, instant acknowledgement, and clear status tracking |
| **Reviewer** | End User | Org / Domain | Moderate | Quickly verify flagged items and correct AI extraction errors |
| **Approver** | End User | Org / Domain | High | Make fast, well-informed approval decisions backed by evidence |
| **Org Admin** | Admin | Single Org | High | Manage org users, permissions, workflow settings, and policy docs |
| **System Admin** | Admin | Platform-wide | High | Maintain platform uptime, security, multi-tenancy, and health |
| **Compliance Officer** | Governance | Org / Domain | High | Ensure document validation rules reflect current policies |
| **IT Stakeholder** | Technical | Platform | Moderate–High | Ensure secure deployment, robust infrastructure, and low maintenance |
| **Auditor** | Third Party | Org / External | Design High / Ops Low | Trace end-to-end processing history and verify policy compliance |
| **Management** | End User (Indirect) | Org / Dept | Moderate | High-level visibility into throughput, bottlenecks, and ROI |
| **Vendor** | Third Party | Finance | Low | Submit invoices easily and track approval status externally |

---

## 3. Domain-Specific Roles

| Stakeholder Role | Academic Domain | HR Domain | Finance Domain |
|---|---|---|---|
| **Submitter** | Student, Applicant | Job Candidate, Employee | Employee, Vendor |
| **Reviewer** | Admissions Staff, Registrar | HR Specialist, Recruiter | AP Clerk, Finance Analyst |
| **Approver** | Department Chair, Dean | HR Manager, Hiring Lead | Finance Controller, Budget Head |
| **Compliance Officer** | Academic Board Coordinator | Labor Law / HR Policy Lead | Corporate Tax & Audit Officer |
| **Sample Documents** | *Transcript, Scholarship Form, Fee Receipt* | *Resume, Offer Letter, Leave Application* | *Invoice, Purchase Order, Expense Claim* |

---

## 4. Stakeholder Profiles

### 4.1 Submitter (Internal)
- **Role:** Uploads documents into Kagaz for processing.
- **Goals:** Simple upload, fast receipt confirmation, transparent progress tracking.
- **Pain Points:** Unclear rejection reasons, black-box processing delays.
- **Key Touchpoints:** Document upload (`FR-04`), status tracking (`FR-22`), AI chatbot policy queries (`FR-27`).

### 4.2 Reviewer
- **Role:** Human-in-the-loop reviewer who inspects low-confidence or flagged documents.
- **Goals:** Quickly resolve exceptions without re-entering data from scratch.
- **Pain Points:** Unexplained AI flags, low-confidence extractions lacking source context.
- **Key Touchpoints:** Review queue (`FR-16`), field corrections (`FR-10`), policy evidence citations (`FR-13`).

### 4.3 Approver
- **Role:** Authorized manager who makes final approval or rejection decisions.
- **Goals:** Rapid, well-substantiated decisions with minimal manual document parsing.
- **Pain Points:** Improperly routed documents, missing justification or policy evidence.
- **Key Touchpoints:** Approval queue (`FR-20`), AI document summary (`FR-26`), approval/rejection (`FR-21`).

### 4.4 Organization Admin
- **Role:** Manages a single organization's tenant instance, users, and policy knowledge base.
- **Goals:** Maintain tenant security, assign roles, and keep organizational rules updated.
- **Pain Points:** Risk of cross-organization data leaks, complex policy updates.
- **Key Touchpoints:** User & role management (`FR-02`), policy & RAG management (`FR-11`), org data isolation (`NFR-SEC-03`).

### 4.5 System Admin
- **Role:** Platform super-admin managing multi-tenant infrastructure, configuration, and security.
- **Goals:** High availability, seamless tenant onboarding, strong data isolation.
- **Pain Points:** System outages, background job failures, API rate limits.
- **Key Touchpoints:** System monitoring (`NFR-OBS-02`), tenant scaling (`NFR-SCAL-01`), failure recovery (`FR-28`).

### 4.6 Compliance Officer
- **Role:** Owns the regulatory and institutional policies used by Kagaz for validation.
- **Goals:** Ensure AI validation strictly adheres to current policies with verifiable citations.
- **Pain Points:** AI hallucinations, applying outdated policy versions to new documents.
- **Key Touchpoints:** Policy rule authoring (`FR-11`), RAG retrieval validation (`NFR-AI-02`), policy versioning (`NFR-AUD-03`).

### 4.7 IT Stakeholder
- **Role:** Focuses on deployment, containerization, security, and service integrations.
- **Goals:** Stable CI/CD pipelines, clean service abstraction (AI/OCR providers), secure secret management.
- **Pain Points:** Vendor lock-in, hardcoded secrets, unsafe file handling.
- **Key Touchpoints:** External service adapters (`NFR-INT-02`), file validation (`NFR-SEC-06`), logging (`NFR-OBS-01`).

### 4.8 Auditor
- **Role:** Independent reviewer verifying compliance, fairness, and process integrity.
- **Goals:** Reconstruct complete, tamper-proof document histories and policy states.
- **Pain Points:** Incomplete logs, editable audit records, untraceable AI decisions.
- **Key Touchpoints:** Immutable audit trails (`FR-23`, `NFR-AUD-01`), AI evidence traceability (`NFR-AI-04`).

### 4.9 Management Stakeholder
- **Role:** Department head or executive tracking high-level efficiency and business value.
- **Goals:** Monitor document turnaround times, straight-through processing rates, and bottlenecks.
- **Pain Points:** Lack of aggregate operational visibility and unclear ROI metrics.
- **Key Touchpoints:** Executive dashboards, throughput metrics, approval analytics (`FR-22`, `FR-26`).

### 4.10 Vendor (External Submitter)
- **Role:** Third-party supplier submitting invoices and billing documents directly into Kagaz.
- **Goals:** Friction-free upload, instant confirmation, clear payment/approval status.
- **Pain Points:** Delayed payments, uncommunicated document rejections.
- **Key Touchpoints:** Restricted submission portal (`FR-04`), automated status notifications (`FR-24`).

---

## 5. Stakeholder Influence vs. Interest

| Category | Stakeholders | Management Strategy |
|---|---|---|
| **High Influence, High Interest** | Org Admin, System Admin, Compliance Officer, Approver | **Manage Closely:** Core drivers of system rules, security, and workflow success. |
| **High Influence, Moderate Interest** | IT Stakeholder, Auditor, Management Stakeholder | **Keep Satisfied:** Governance and tech gatekeepers; meet security and audit expectations. |
| **Low Influence, High Interest** | Submitter, Reviewer, Vendor | **Keep Informed:** Primary day-to-day users; focus on usability, speed, and clear feedback. |
| **Low Influence, Low Interest** | Occasional / Casual Submitters | **Monitor:** Ensure intuitive self-service requiring no training. |

---

## 6. Document Workflow & Role Responsibilities

| Workflow Stage | Primary Actor | Supporting / Secondary Actors |
|---|---|---|
| **1. Upload & Ingestion** | Submitter / Vendor | IT Stakeholder (Security), System Admin |
| **2. OCR & Text Extraction** | Automated Pipeline | IT Stakeholder (Engine integration) |
| **3. Classification** | Automated AI | Reviewer (Correction), Compliance Officer (Types) |
| **4. Field Extraction** | Automated AI | Reviewer (Correction) |
| **5. Policy Validation (RAG)** | Automated AI | Compliance Officer (Rules), Org Admin (Knowledge base) |
| **6. Human Review** | Reviewer | Submitter (Receives flag notices) |
| **7. Final Decision** | Approver | Submitter / Vendor (Receives decision) |
| **8. Audit & Archival** | Auditor | Compliance Officer, IT Stakeholder |
