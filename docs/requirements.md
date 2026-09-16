# Kagaz -- Functional Requirements

## 1. Purpose

This document defines the functional requirements of Kagaz.

Kagaz is intended to automate the processing of documents from upload to
final decision. The system reduces repetitive manual work while allowing
authorized users to review, correct and approve documents when required.

The initial scope covers Academic, HR and Finance documents.

## 2. Main Document Workflow

The main workflow of Kagaz is:

**Upload → Text Extraction → Classification → Field Extraction →
Validation → Issue Detection → Routing → Review/Approval**

Not every document will follow exactly the same path. Documents with
missing, inconsistent or low-confidence information may be sent for
manual review.

## 3. Functional Requirements

### FR-01: User Login and Authentication

Kagaz shall allow registered users to log in using valid credentials.
The system shall create an authenticated session after successful login
and shall prevent unauthenticated users from accessing protected
functions.

### FR-02: User and Role Management

The System Admin shall be able to create, update, disable and manage
user accounts and assign appropriate roles. The initial roles shall
include Submitter, Reviewer, Approver and System Admin.

### FR-03: Role-Based Access Control

Kagaz shall restrict documents and system actions according to the
user's assigned role and permissions. Users shall only be able to
perform actions authorized for their role.

### FR-04: Document Upload

A Submitter shall be able to upload documents for processing. The system
shall support the defined document formats, including PDF, DOCX and
scanned images, and shall reject unsupported files with a clear message.

### FR-05: Document Metadata and Storage

Kagaz shall store uploaded documents together with relevant metadata
such as document name, upload date and time, submitter, file type,
document status and document type. The stored file shall remain
associated with its document record.

### FR-06: Text Extraction and OCR

Kagaz shall extract text from machine-readable documents and use OCR for
scanned or image-based documents. The extracted text shall be made
available to the subsequent processing stages.

### FR-07: Document Classification

Kagaz shall automatically classify uploaded documents into the
applicable document type. The initial document types shall include
Transcript, Scholarship Form, Fee Receipt, Resume, Offer Letter, Leave
Application, Invoice, Purchase Order and Expense Claim.

### FR-08: Classification Confidence and Correction

Kagaz shall store the classification result and, where available, its
confidence information. An authorized Reviewer shall be able to correct
an incorrect classification, and the correction shall be recorded in the
document history.

### FR-09: Key-Field Extraction

After classification, Kagaz shall extract relevant fields according to
the document type. For example, invoice fields may include invoice
number, date, supplier and amount, while resume fields may include
candidate name, contact details and skills.

### FR-10: Extracted Information Review and Correction

Kagaz shall display extracted fields to authorized users. A Reviewer
shall be able to correct incomplete or incorrect extracted information,
and the system shall retain the corrected values and record the changes.

### FR-11: Policy and Knowledge Base Management

An authorized user shall be able to add or update policy and reference
documents used by Kagaz for validation and AI-assisted responses. The
system shall maintain information about the relevant policy version.

### FR-12: Policy-Based Validation

Kagaz shall validate relevant document information against the available
policies and rules. The validation shall use information from the policy
knowledge base when applicable.

### FR-13: Validation Results and Evidence

For each applicable validation check, Kagaz shall provide and store a
result indicating whether the document appears to satisfy the relevant
rule. The system shall display supporting policy information or evidence
when available.

### FR-14: Missing and Inconsistent Information Detection

Kagaz shall identify required information that is missing from a
document and detect information that appears inconsistent or
contradictory. Detected issues shall be recorded for review.

### FR-15: Low-Confidence and Processing Issue Handling

When classification, extraction or validation results are below the
defined confidence threshold, Kagaz shall flag the document for human
review. The system shall show the reason for the review.

### FR-16: Review Queue

Kagaz shall provide a queue containing documents that require manual
review. Reviewers shall be able to view documents assigned to them or
documents available to them according to their permissions.

### FR-17: Document Review

A Reviewer shall be able to open a document and view the original file,
extracted text, classification, extracted fields, validation results,
detected issues and relevant policy evidence available to them.

### FR-18: Review Notes and Corrections

A Reviewer shall be able to add review notes and make supported
corrections to document information. The system shall record the user
responsible for each correction or review action.

### FR-19: Document Routing and Reassignment

Kagaz shall route documents to the appropriate Reviewer or Approver
according to defined workflow rules. Authorized users shall be able to
reassign documents when necessary, and reassignment details shall be
recorded.

### FR-20: Approval Queue

Kagaz shall provide Approvers with a list of documents waiting for their
decision. The Approver shall be able to open a document and view the
information required for making the decision.

### FR-21: Document Approval and Rejection

An authorized Approver shall be able to approve or reject a document.
When rejecting a document, the Approver shall be able to provide a
reason or comment. The decision and updated document status shall be
recorded.

### FR-22: Document Status Tracking

Kagaz shall maintain the current status of every document throughout its
workflow. Statuses may include Uploaded, Processing, Classified, Review
Required, Waiting for Approval, Approved, Rejected and Processing
Failed.

### FR-23: Document History and Audit Trail

Kagaz shall maintain a history of significant document and system
actions, including upload, processing, classification, corrections,
validation, review, routing, approval and rejection. Each important
event shall include the responsible user or system action and its time.

### FR-24: Notifications

Kagaz shall notify relevant users when a document requires their action
or when an important workflow event occurs. Notifications may include
new review assignments, approval assignments, approvals, rejections and
returned documents.

### FR-25: Document Search and Filtering

Authorized users shall be able to search for documents using relevant
information such as document type, status, submitter and date. The
system shall provide filters to help users find documents relevant to
their work.

### FR-26: Document Details and Summary

Kagaz shall provide a detailed view of an individual document containing
the available document information, processing results, current status
and workflow history. The system shall also generate a summary for
supported documents highlighting important information.

### FR-27: AI Chatbot and RAG-Based Assistance

Kagaz shall provide an AI chatbot that can answer supported questions
about accessible documents and policies. For policy-related questions,
the chatbot shall retrieve relevant information from the system
knowledge base and, where applicable, provide supporting policy
evidence.

### FR-28: Error Handling and Workflow Completion

Kagaz shall detect and record processing failures, unsupported documents
and unusable content without silently continuing normal processing.
Where possible, failed documents shall be retried or sent for manual
handling. The system shall mark a document as completed when all
required workflow steps have been successfully finished and shall retain
its final outcome and history.

## 4. Initial Document Scope

  Domain     Initial Document Types
  ---------- -------------------------------------------
  Academic   Transcript, Scholarship Form, Fee Receipt
  HR         Resume, Offer Letter, Leave Application
  Finance    Invoice, Purchase Order, Expense Claim

These document types represent the initial scope and may be expanded
later.

## 5. Requirement Notes

### 5.1 AI-Assisted Results

Classification, extraction and validation are AI-assisted functions.
Kagaz shall provide mechanisms for authorized users to review and
correct results when the system is uncertain or incorrect.

### 5.2 Human Decisions

Kagaz automates repetitive document processing, but final review and
approval remain human-controlled where required.

### 5.3 Requirement Evolution

Detailed policies, workflow rules and document fields may be refined as
the project progresses and further requirements are elicited.

## 6. Requirement Coverage

  Area                            Requirements
  ------------------------------- ---------------------
  Access and users                FR-01, FR-02, FR-03
  Document ingestion              FR-04, FR-05
  Text processing                 FR-06
  Classification                  FR-07, FR-08
  Information extraction          FR-09, FR-10
  Policy and validation           FR-11, FR-12, FR-13
  Issue detection                 FR-14, FR-15
  Review                          FR-16, FR-17, FR-18
  Routing and approval            FR-19, FR-20, FR-21
  Workflow tracking               FR-22, FR-23
  Notifications                   FR-24
  Search and document view        FR-25, FR-26
  AI assistance                   FR-27
  Error handling and completion   FR-28

## 7. Acceptance Criteria

-   All major functional areas of Kagaz are covered.
-   Every functional requirement has a unique ID.
-   Each requirement describes a specific system behaviour.
-   Requirements are clear enough to be reviewed and tested.
-   The requirements cover the complete document workflow and supporting
    functions.
-   AI processing, human review, routing, approval, audit and access
    control are represented.
