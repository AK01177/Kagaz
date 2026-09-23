# Kagaz — User Stories & Acceptance Criteria

## Reading the cards

**Front of Card** = the user story: who needs something, what they need, and why.

**Back of Card** = acceptance criteria that make the story objectively testable.

**Traceability** identifies the source requirement(s).  
**Stakeholder(s)** identifies the people whose needs are served.

Where a story comes from the stakeholder/elicitation material rather than a fully specified functional requirement, it is marked **Elicitation-derived / provisional** rather than pretending the source defines more than it does.

---

# EPIC 1 — Identity, Roles & Organization Control

## CARD US-01 — Secure Login

### FRONT

**As a registered Kagaz user,**  
I want to log in using my valid credentials,  
**so that I can securely access the functions and documents permitted to me.**

**Stakeholder:** Submitter, Reviewer, Approver, Org Admin, System Admin, Compliance Officer, IT Stakeholder, Auditor  
**Traceability:** FR-01, NFR-SEC-01

### BACK — Acceptance Criteria

**AC1.** Given a registered user with valid credentials, when the user submits the login request, then Kagaz authenticates the user and creates an authenticated session.

**AC2.** Given invalid credentials, when the user attempts to log in, then access is denied and the user receives an appropriate error message.

**AC3.** Given an unauthenticated user, when the user attempts to access a protected function or protected document, then Kagaz denies access.

**AC4.** Authentication must be enforced before access to protected user or organization functions.

**AC5.** User-facing authentication errors must not expose sensitive implementation details.

---

## CARD US-02 — Platform User & Role Management

### FRONT

**As a System Admin,**  
I want to create, update, disable, and assign roles to user accounts,  
**so that platform access can be administered centrally and securely.**

**Stakeholder:** System Admin  
**Traceability:** FR-02

### BACK — Acceptance Criteria

**AC1.** The System Admin can create a user account.

**AC2.** The System Admin can update an existing user account.

**AC3.** The System Admin can disable an existing user account.

**AC4.** The System Admin can assign an appropriate role from the supported role model.

**AC5.** Supported initial roles include Submitter, Reviewer, Approver, and System Admin.

**AC6.** A disabled user cannot access protected functions.

**AC7.** User-management actions are recorded in the audit history.

---

## CARD US-03 — Organization-Level User Administration

### FRONT

**As an Organization Admin,**  
I want to manage users and permissions within my organization,  
**so that my organization can control its own Kagaz access without affecting other organizations.**

**Stakeholder:** Org Admin  
**Traceability:** Stakeholder documentation and elicitation requirements; NFR-SEC-02, NFR-SEC-03  
**Status:** **Elicitation-derived / provisional**

### BACK — Acceptance Criteria

**AC1.** The Org Admin can view and manage users belonging to the Org Admin’s organization, subject to the agreed permission model.

**AC2.** The Org Admin cannot administer users belonging to another organization.

**AC3.** Organization-level user management does not expose another organization’s documents, policies, workflow records, or audit information.

**AC4.** Permission changes take effect for subsequent protected operations.

**AC5.** Administrative actions are attributable to the responsible administrator.

---

## CARD US-04 — Role-Based Access & Tenant Isolation

### FRONT

**As a Kagaz platform stakeholder,**  
I want access and actions to be restricted by role and organization,  
**so that users can only see and perform what they are authorized to do.**

**Stakeholder:** All stakeholders  
**Traceability:** FR-03, NFR-SEC-02, NFR-SEC-03

### BACK — Acceptance Criteria

**AC1.** A user can perform an action only when their assigned role permits it.

**AC2.** A user cannot access documents belonging to an organization for which they are unauthorized.

**AC3.** Unauthorized access to another organization’s policies, knowledge-base data, workflow records, or audit information is rejected.

**AC4.** The same access restrictions apply through every supported application entry point.

**AC5.** Access-control failures are logged for operational diagnosis without unnecessarily exposing sensitive document content.

---

## CARD US-05 — Organization Onboarding & Configuration

### FRONT

**As a System Admin,**  
I want to onboard additional organizations and configure organization-specific settings, policies, and workflow data,  
**so that Kagaz can scale as a multi-organization platform without changing its core processing workflow.**

**Stakeholder:** System Admin, Org Admin, Compliance Officer  
**Traceability:** NFR-SCAL-01, NFR-MAIN-02  
**Status:** **Elicitation-derived / provisional**

### BACK — Acceptance Criteria

**AC1.** A new organization can be added through organization configuration or stored organizational data.

**AC2.** Adding an organization does not require modifying the core document-processing workflow.

**AC3.** Organization-specific policies and workflow configuration are stored as configurable data wherever practical.

**AC4.** Organization configuration is isolated from other organizations.

**AC5.** The system supports the addition of organizations without redesigning the core processing architecture.

---

# EPIC 2 — Submission, File Handling & Ingestion

## CARD US-06 — Document Submission

### FRONT

**As a Submitter,**  
I want to upload a document in a supported format,  
**so that Kagaz can begin processing it without requiring manual re-entry of the document content.**

**Stakeholder:** Submitter  
**Traceability:** FR-04, NFR-INT-01

### BACK — Acceptance Criteria

**AC1.** The Submitter can upload supported PDF, DOCX, and scanned image documents.

**AC2.** A valid supported file is accepted and creates a document record.

**AC3.** An unsupported file type is rejected.

**AC4.** When a file is rejected, Kagaz clearly tells the user that the file cannot be accepted.

**AC5.** Supported document types are handled consistently across the upload and processing workflow.

---

## CARD US-07 — External Vendor Submission

### FRONT

**As a Vendor,**  
I want to submit invoices and billing documents through a restricted submission path and receive confirmation of their status,  
**so that I can participate in the Finance workflow without requiring internal system access.**

**Stakeholder:** Vendor  
**Traceability:** Stakeholder documentation: Vendor profile and workflow responsibilities; FR-04, FR-24  
**Status:** **Elicitation-derived / provisional**

### BACK — Acceptance Criteria

**AC1.** A Vendor can submit supported Finance documents through the restricted submission mechanism defined for external submitters.

**AC2.** A Vendor cannot access internal functions outside the permissions granted for external submission.

**AC3.** The Vendor receives confirmation after a valid submission is accepted.

**AC4.** The Vendor can receive relevant approval or rejection status notifications.

**AC5.** Vendor access does not expose unrelated organizational data.

---

## CARD US-08 — Secure File Validation & Document Storage

### FRONT

**As a System Admin,**  
I want uploaded files to be validated and securely associated with their document records,  
**so that invalid or unsafe files do not enter normal processing and submitted documents remain traceable.**

**Stakeholder:** System Admin, IT Stakeholder  
**Traceability:** FR-05, NFR-SEC-06

### BACK — Acceptance Criteria

**AC1.** Kagaz validates file type, size, and basic integrity before processing.

**AC2.** Oversized, malformed, or unsupported files are not silently processed.

**AC3.** A successfully accepted document is stored with relevant metadata.

**AC4.** Stored metadata includes document name, upload date/time, submitter, file type, document status, and document type when available.

**AC5.** The stored file remains associated with its document record.

**AC6.** A rejection or validation failure produces an understandable user-facing message.

---

## CARD US-09 — Fast Upload Acknowledgement

### FRONT

**As a Submitter,**  
I want immediate confirmation that my document has been accepted,  
**so that I do not have to wait for OCR, classification, extraction, or validation to finish before knowing my submission succeeded.**

**Stakeholder:** Submitter, Vendor  
**Traceability:** NFR-PERF-02

### BACK — Acceptance Criteria

**AC1.** A valid upload is acknowledged within **3 seconds**, excluding background AI processing time.

**AC2.** The acknowledgement identifies the accepted submission/document sufficiently for the user to track it.

**AC3.** The acknowledgement is returned before long-running AI processing is required to complete.

---

## CARD US-10 — Asynchronous Document Processing

### FRONT

**As a Submitter,**  
I want long-running document processing to happen in the background,  
**so that the Kagaz interface remains usable while my document is being processed.**

**Stakeholder:** Submitter, Reviewer, Approver, System Admin, IT Stakeholder  
**Traceability:** FR-06 to FR-15 workflow behavior; NFR-PERF-03, NFR-SCAL-03

### BACK — Acceptance Criteria

**AC1.** OCR, classification, extraction, and policy validation execute asynchronously.

**AC2.** Background processing does not block normal authenticated user-interface operations.

**AC3.** Multiple processing jobs can exist concurrently.

**AC4.** Failure of one processing job does not automatically fail unrelated jobs.

**AC5.** The current processing state remains observable to authorized users.

---

# EPIC 3 — AI Processing, Extraction & Exception Detection

## CARD US-11 — OCR & Text Extraction

### FRONT

**As a Reviewer,**  
I want Kagaz to extract machine-readable text and OCR scanned documents,  
**so that subsequent classification, extraction, validation, and review stages can operate on usable content.**

**Stakeholder:** Reviewer, IT Stakeholder  
**Traceability:** FR-06, NFR-INT-01

### BACK — Acceptance Criteria

**AC1.** Machine-readable documents have their text extracted.

**AC2.** Scanned or image-based documents are processed using OCR.

**AC3.** Extracted text is made available to subsequent processing stages.

**AC4.** An unusable document is not silently treated as successfully processed.

**AC5.** OCR or extraction failure results in an appropriate processing state or manual-handling path.

---

## CARD US-12 — Automatic Document Classification

### FRONT

**As a Submitter,**  
I want Kagaz to automatically identify the type of my document,  
**so that the appropriate fields, policies, and workflow can be applied without manual classification.**

**Stakeholder:** Submitter, Reviewer, Compliance Officer  
**Traceability:** FR-07

### BACK — Acceptance Criteria

**AC1.** Kagaz classifies an uploaded document into an applicable document type.

**AC2.** Initial supported types include Transcript, Scholarship Form, Fee Receipt, Resume, Offer Letter, Leave Application, Invoice, Purchase Order, and Expense Claim.

**AC3.** The classification result is stored with the document.

**AC4.** Classification confidence information is stored where available.

**AC5.** Classification is completed before document-type-specific field extraction.

---

## CARD US-13 — Reviewer Correction of Classification

### FRONT

**As a Reviewer,**  
I want to correct an incorrect AI classification,  
**so that the document enters the correct downstream processing path.**

**Stakeholder:** Reviewer  
**Traceability:** FR-08, NFR-AI-01

### BACK — Acceptance Criteria

**AC1.** An authorized Reviewer can see the system’s classification result.

**AC2.** The Reviewer can correct the classification when it is incorrect.

**AC3.** The corrected document type becomes the effective classification for subsequent processing where workflow permits.

**AC4.** The original classification and corrected classification remain traceable.

**AC5.** The correction records the responsible user and time.

---

## CARD US-14 — Key-Field Extraction

### FRONT

**As a Reviewer,**  
I want Kagaz to extract the fields relevant to the classified document type,  
**so that I can verify information without manually transcribing the document.**

**Stakeholder:** Reviewer, Submitter, Approver  
**Traceability:** FR-09

### BACK — Acceptance Criteria

**AC1.** Field extraction occurs after document classification.

**AC2.** The system extracts fields appropriate to the detected document type.

**AC3.** For an invoice, supported extracted information may include invoice number, date, supplier, and amount.

**AC4.** For a resume, supported extracted information may include candidate name, contact details, and skills.

**AC5.** Extracted information is stored and made available to authorized users.

---

## CARD US-15 — Reviewer Correction of Extracted Fields

### FRONT

**As a Reviewer,**  
I want to correct incomplete or incorrect extracted fields,  
**so that downstream validation and approval use verified information rather than erroneous AI output.**

**Stakeholder:** Reviewer  
**Traceability:** FR-10, NFR-AI-01

### BACK — Acceptance Criteria

**AC1.** Authorized users can view extracted fields.

**AC2.** A Reviewer can edit supported fields.

**AC3.** Corrected values are retained.

**AC4.** The system records what was changed and who changed it.

**AC5.** The corrected information is used by downstream workflow steps where applicable.

---

## CARD US-16 — Missing & Inconsistent Information Detection

### FRONT

**As a Reviewer,**  
I want Kagaz to detect missing required information and apparent contradictions,  
**so that incomplete or internally inconsistent documents are surfaced for human attention.**

**Stakeholder:** Reviewer, Compliance Officer, Approver  
**Traceability:** FR-14

### BACK — Acceptance Criteria

**AC1.** Kagaz identifies required information that is missing.

**AC2.** Kagaz identifies information that appears contradictory or inconsistent.

**AC3.** Detected issues are stored against the document.

**AC4.** Detected issues are visible to authorized reviewers.

**AC5.** Issue detection does not silently pass an identified issue as though no issue existed.

---

## CARD US-17 — Low-Confidence Human Review

### FRONT

**As a Reviewer,**  
I want low-confidence AI results to be flagged with the reason they require review,  
**so that uncertain automated decisions are not treated as final without human verification.**

**Stakeholder:** Reviewer, Compliance Officer, Approver  
**Traceability:** FR-15, NFR-AI-01

### BACK — Acceptance Criteria

**AC1.** Kagaz compares applicable AI results against the configured confidence threshold.

**AC2.** A classification or extraction result below the configured threshold is flagged when human verification is required.

**AC3.** The document is routed into the appropriate human-review path.

**AC4.** The reviewer can see why the document was flagged.

**AC5.** A low-confidence result is not silently treated as final where the workflow requires human verification.

---

# EPIC 4 — Policy, Validation & RAG

## CARD US-18 — Policy Knowledge Base Management

### FRONT

**As a Compliance Officer,**  
I want to add and update the policies used by Kagaz,  
**so that validation and AI assistance reflect the organization’s current approved rules.**

**Stakeholder:** Compliance Officer, Org Admin  
**Traceability:** FR-11, NFR-MAIN-02

### BACK — Acceptance Criteria

**AC1.** An authorized user can add policy or reference documents.

**AC2.** An authorized user can update policy/reference content.

**AC3.** Each policy remains associated with relevant version information.

**AC4.** Policy changes are organization-scoped.

**AC5.** Updating a policy does not require hard-coding the changed rule into core application logic where configuration is practical.

---

## CARD US-19 — Policy-Based Document Validation

### FRONT

**As a Compliance Officer,**  
I want Kagaz to validate relevant document information against applicable policies and rules,  
**so that document compliance can be checked consistently against the organization’s configured requirements.**

**Stakeholder:** Compliance Officer, Reviewer, Approver  
**Traceability:** FR-12, NFR-AI-02, NFR-AI-03

### BACK — Acceptance Criteria

**AC1.** Applicable validation rules are identified for the document type and organization.

**AC2.** Document information is checked against relevant policy content when applicable.

**AC3.** Validation results are stored with the document.

**AC4.** Validation does not use another organization’s policy information.

**AC5.** Domain-appropriate policy information is used for the validation.

---

## CARD US-20 — Validation Result & Evidence

### FRONT

**As an Approver,**  
I want to see the result of each applicable validation check together with supporting policy evidence,  
**so that I can understand the basis of an AI-assisted result before making a decision.**

**Stakeholder:** Approver, Reviewer, Compliance Officer, Auditor  
**Traceability:** FR-13, NFR-AI-04

### BACK — Acceptance Criteria

**AC1.** Each applicable validation check has a stored result.

**AC2.** The result indicates whether the document appears to satisfy the applicable rule.

**AC3.** Supporting policy information or evidence is displayed when available.

**AC4.** The evidence is associated with the validation result it supports.

**AC5.** The evidence/reference used for the result is preserved for later traceability.

---

## CARD US-21 — Policy-Grounded AI Assistant

### FRONT

**As a Submitter or authorized reviewer,**  
I want to ask supported questions about accessible documents and policies,  
**so that I can get useful answers based on information Kagaz is actually authorized to access.**

**Stakeholder:** Submitter, Reviewer, Compliance Officer  
**Traceability:** FR-27, NFR-AI-02

### BACK — Acceptance Criteria

**AC1.** The chatbot can answer supported questions about accessible documents and policies.

**AC2.** Policy-related answers use relevant content from the organization’s knowledge base.

**AC3.** Policy explanations do not rely solely on unsupported model-generated content.

**AC4.** Supporting policy evidence is provided where applicable.

**AC5.** The chatbot respects the requesting user’s access permissions.

---

## CARD US-22 — Organization- and Domain-Aware Retrieval

### FRONT

**As a Compliance Officer,**  
I want RAG retrieval to use only the correct organization and domain policy information,  
**so that validation and policy answers are not contaminated by unrelated rules.**

**Stakeholder:** Compliance Officer, IT Stakeholder, Auditor  
**Traceability:** NFR-AI-03

### BACK — Acceptance Criteria

**AC1.** Retrieval identifies the applicable organization before returning policy information.

**AC2.** Retrieval limits policy information to the applicable domain.

**AC3.** Another organization’s policy content cannot be returned as supporting context.

**AC4.** An unrelated domain’s policy cannot be silently substituted for the applicable domain.

**AC5.** Tests using distinguishable organization/domain policies return only applicable policy content.

---

## CARD US-23 — Policy Version Traceability

### FRONT

**As an Auditor,**  
I want every policy-based validation or explanation to remain linked to the policy version used at the time,  
**so that historical decisions remain reproducible after policies change.**

**Stakeholder:** Auditor, Compliance Officer  
**Traceability:** NFR-AUD-03

### BACK — Acceptance Criteria

**AC1.** Every applicable validation result stores the policy version used.

**AC2.** Policy-related processing stores the version associated with the result.

**AC3.** Updating the current policy does not silently rewrite historical validation results.

**AC4.** An auditor can identify which policy version was used for a historical result.

---

# EPIC 5 — Human Review, Routing & Approval

## CARD US-24 — Review Queue

### FRONT

**As a Reviewer,**  
I want a queue of documents requiring manual attention,  
**so that I can work through exceptions systematically instead of searching the entire document repository.**

**Stakeholder:** Reviewer  
**Traceability:** FR-16

### BACK — Acceptance Criteria

**AC1.** Documents requiring manual review appear in the review queue.

**AC2.** A Reviewer can see documents assigned to them.

**AC3.** A Reviewer can see documents available to them according to their permissions.

**AC4.** The queue reflects the current review state.

**AC5.** Access to the queue respects role and organization restrictions.

---

## CARD US-25 — Full Document Review Workspace

### FRONT

**As a Reviewer,**  
I want one review view showing the original document, extracted text, classification, extracted fields, validation results, issues, and available policy evidence,  
**so that I can resolve exceptions using the complete available context.**

**Stakeholder:** Reviewer  
**Traceability:** FR-17, FR-26

### BACK — Acceptance Criteria

**AC1.** The Reviewer can open the original document.

**AC2.** Extracted text is visible when available.

**AC3.** The current classification is visible.

**AC4.** Extracted fields are visible.

**AC5.** Validation results are visible.

**AC6.** Detected issues are visible.

**AC7.** Relevant policy evidence is visible when available and authorized.

**AC8.** The information shown represents the current stored processing state.

---

## CARD US-26 — Review Notes & Corrections

### FRONT

**As a Reviewer,**  
I want to add review notes and make supported corrections while reviewing a document,  
**so that my decisions and corrections become part of the document’s traceable workflow history.**

**Stakeholder:** Reviewer, Auditor  
**Traceability:** FR-18, NFR-AUD-01, NFR-AUD-02

### BACK — Acceptance Criteria

**AC1.** A Reviewer can add a review note.

**AC2.** A Reviewer can perform supported corrections.

**AC3.** Every correction records the responsible user.

**AC4.** Every review action records the relevant event time.

**AC5.** Historical review actions remain available in the document history.

---

## CARD US-27 — Automated Routing & Reassignment

### FRONT

**As an authorized workflow administrator,**  
I want documents to be routed to the appropriate Reviewer or Approver and reassigned when necessary,  
**so that every document reaches the correct decision-maker without losing workflow traceability.**

**Stakeholder:** Org Admin, System Admin, Reviewer, Approver  
**Traceability:** FR-19

### BACK — Acceptance Criteria

**AC1.** Kagaz routes documents according to the defined workflow rules.

**AC2.** Documents requiring review can be routed to an appropriate Reviewer.

**AC3.** Documents requiring approval can be routed to an appropriate Approver.

**AC4.** An authorized user can reassign a document where permitted.

**AC5.** Reassignment records the relevant details.

**AC6.** Unauthorized users cannot redirect documents.

---

## CARD US-28 — Approval Queue

### FRONT

**As an Approver,**  
I want a queue containing documents waiting for my decision,  
**so that I can quickly identify and act on pending approvals.**

**Stakeholder:** Approver  
**Traceability:** FR-20

### BACK — Acceptance Criteria

**AC1.** Documents awaiting approval appear in the approval queue.

**AC2.** The Approver can open a queued document.

**AC3.** The Approver can see the information required for the decision.

**AC4.** The queue does not expose documents outside the Approver’s permissions.

---

## CARD US-29 — Evidence-Based Approval or Rejection

### FRONT

**As an Approver,**  
I want to approve or reject a document after reviewing its relevant evidence,  
**so that the final outcome is an explicit human decision supported by the available document and policy information.**

**Stakeholder:** Approver, Submitter, Vendor, Auditor  
**Traceability:** FR-21

### BACK — Acceptance Criteria

**AC1.** An authorized Approver can approve a document.

**AC2.** An authorized Approver can reject a document.

**AC3.** When rejecting a document, the Approver can provide a reason or comment.

**AC4.** The decision is stored against the document.

**AC5.** The document status is updated to reflect the decision.

**AC6.** The decision records the responsible Approver and event time.

**AC7.** The decision becomes part of the document’s audit history.

---

## CARD US-30 — End-to-End Document Status

### FRONT

**As a Submitter,**  
I want to see the current status of my document throughout processing,  
**so that I know whether Kagaz is processing it, needs my document reviewed, is waiting for approval, or has completed the workflow.**

**Stakeholder:** Submitter, Vendor, Reviewer, Approver, Management  
**Traceability:** FR-22

### BACK — Acceptance Criteria

**AC1.** Kagaz maintains one current status for each document.

**AC2.** Supported statuses include Uploaded, Processing, Classified, Review Required, Waiting for Approval, Approved, Rejected, and Processing Failed.

**AC3.** Status changes reflect actual workflow transitions.

**AC4.** Authorized users can view the current status.

**AC5.** A failed document is not represented as successfully completed.

---

## CARD US-31 — Action Notifications

### FRONT

**As a workflow participant,**  
I want to be notified when a document requires my action or reaches an important workflow milestone,  
**so that work does not remain blocked because someone did not know the document was waiting for them.**

**Stakeholder:** Submitter, Reviewer, Approver, Vendor  
**Traceability:** FR-24

### BACK — Acceptance Criteria

**AC1.** Relevant users receive notifications when a document requires their action.

**AC2.** New review assignments can generate notifications.

**AC3.** Approval assignments can generate notifications.

**AC4.** Approval and rejection outcomes can generate notifications to relevant recipients.

**AC5.** Returned documents can generate notifications.

**AC6.** Notifications do not disclose information to unauthorized recipients.

---

# EPIC 6 — Search, Visibility & Management Information

## CARD US-32 — Document Search & Filtering

### FRONT

**As an authorized user,**  
I want to search and filter documents using relevant attributes,  
**so that I can quickly find the documents relevant to my current task.**

**Stakeholder:** Submitter, Reviewer, Approver, Org Admin, Auditor, Management  
**Traceability:** FR-25

### BACK — Acceptance Criteria

**AC1.** Authorized users can search for documents.

**AC2.** Users can filter by document type.

**AC3.** Users can filter by status.

**AC4.** Users can filter by submitter.

**AC5.** Users can filter by date.

**AC6.** Search and filtering respect organization and permission boundaries.

---

## CARD US-33 — Document Details & AI Summary

### FRONT

**As an Approver,**  
I want a detailed document summary containing the important information and current workflow state,  
**so that I can understand a document without manually reconstructing the entire processing history.**

**Stakeholder:** Approver, Reviewer, Management  
**Traceability:** FR-26

### BACK — Acceptance Criteria

**AC1.** The document details view contains available document information.

**AC2.** Processing results are displayed.

**AC3.** The current document status is displayed.

**AC4.** Workflow history is available.

**AC5.** Supported documents have a generated summary highlighting important information.

**AC6.** Summary content is associated with the correct document.

---

## CARD US-34 — Management Operational Dashboard

### FRONT

**As a Management stakeholder,**  
I want high-level visibility into document throughput, turnaround time, bottlenecks, and approval activity,  
**so that I can monitor operational performance and the business value of Kagaz.**

**Stakeholder:** Management  
**Traceability:** Stakeholder profile, elicitation expectations  
**Status:** **Elicitation-derived / provisional**

### BACK — Acceptance Criteria

**AC1.** The management view presents agreed high-level workflow metrics.

**AC2.** The view provides visibility into document throughput.

**AC3.** The view provides visibility into turnaround-time performance.

**AC4.** The view identifies workflow bottlenecks using agreed operational measures.

**AC5.** Approval activity is represented using agreed metrics.

**AC6.** Metrics are based on stored workflow data rather than manually entered estimates.

**AC7.** Management reporting does not expose information outside the stakeholder’s authorized organizational scope.

> Note: the source identifies dashboards, throughput, turnaround time, straight-through processing, bottlenecks, and approval analytics as management needs, but it does not yet define exact KPI formulas. Those formulas should be elicited and baselined before implementation.

---

# EPIC 7 — Audit, Traceability & Governance

## CARD US-35 — Immutable Audit Trail

### FRONT

**As an Auditor,**  
I want important document, workflow, policy, user, and decision events recorded in a tamper-resistant audit trail,  
**so that I can rely on the system history when verifying process integrity.**

**Stakeholder:** Auditor, Compliance Officer, System Admin  
**Traceability:** FR-23, NFR-AUD-01

### BACK — Acceptance Criteria

**AC1.** Upload, processing, classification, correction, validation, review, routing, approval, rejection, policy, user, and relevant decision events are recorded as applicable.

**AC2.** Each important event records the responsible user or system action.

**AC3.** Each important event includes its event time.

**AC4.** Ordinary users cannot modify or delete historical audit records through normal application functions.

**AC5.** Audit records remain available after normal application restart.

---

## CARD US-36 — End-to-End Traceability

### FRONT

**As an Auditor,**  
I want to reconstruct a document’s complete lifecycle from submission to final decision,  
**so that I can verify how the final outcome was produced.**

**Stakeholder:** Auditor, Compliance Officer  
**Traceability:** NFR-AUD-02

### BACK — Acceptance Criteria

**AC1.** An authorized Auditor can trace a completed document from submission onward.

**AC2.** The history shows the major AI-processing stages.

**AC3.** The history shows validation.

**AC4.** The history shows routing and reassignment when applicable.

**AC5.** The history shows human review and corrections.

**AC6.** The history shows the final approval or rejection decision.

**AC7.** Each major event can be associated with its responsible actor or system action and time.

---

# EPIC 8 — Reliability, Recovery & Operational Control

## CARD US-37 — Processing Failure Isolation

### FRONT

**As a System Admin,**  
I want failures in one document’s processing chain isolated from other jobs,  
**so that one problematic document or unavailable processing component does not stop unrelated work.**

**Stakeholder:** System Admin, IT Stakeholder  
**Traceability:** NFR-REL-01, NFR-SCAL-03

### BACK — Acceptance Criteria

**AC1.** A failure in OCR, classification, extraction, RAG, or policy validation for one document does not fail unrelated processing jobs.

**AC2.** Concurrent jobs can continue processing when one job fails.

**AC3.** The failed document receives an appropriate processing state.

**AC4.** The failure is recorded for diagnosis.

**AC5.** Failure isolation is verified under concurrent-processing tests.

---

## CARD US-38 — Retry & Recovery

### FRONT

**As a System Admin,**  
I want transient processing failures to be retried or recovered without re-uploading the document,  
**so that temporary service failures do not force users to repeat completed work.**

**Stakeholder:** System Admin, Submitter, IT Stakeholder  
**Traceability:** FR-28, NFR-REL-02

### BACK — Acceptance Criteria

**AC1.** A transient background-processing failure is detected.

**AC2.** The failed job can be retried or recovered without requiring the user to upload the same document again.

**AC3.** Retry/recovery activity is recorded.

**AC4.** A permanently unusable document is routed for manual handling or marked failed as appropriate.

**AC5.** The system does not falsely mark an unsuccessful retry as completed.

---

## CARD US-39 — Graceful External-Service Failure

### FRONT

**As an IT Stakeholder,**  
I want Kagaz to fail gracefully when a non-critical external dependency is temporarily unavailable,  
**so that users receive an honest processing state rather than incomplete or misleading results.**

**Stakeholder:** IT Stakeholder, System Admin, Submitter, Reviewer  
**Traceability:** NFR-REL-04, FR-28

### BACK — Acceptance Criteria

**AC1.** Temporary AI/OCR/external-service failure is detected.

**AC2.** Kagaz does not silently generate an apparently valid but incomplete result.

**AC3.** The document enters an appropriate processing or failure state.

**AC4.** The user receives an understandable message.

**AC5.** Internal diagnostics contain enough information for authorized personnel to diagnose the failure.

---

## CARD US-40 — Data Durability After Restart

### FRONT

**As an Auditor or System Admin,**  
I want stored document and workflow records to survive normal application restarts,  
**so that processing history and decisions are not lost during routine operations.**

**Stakeholder:** Auditor, System Admin, Compliance Officer  
**Traceability:** NFR-REL-03

### BACK — Acceptance Criteria

**AC1.** Successfully stored document metadata remains available after restart.

**AC2.** Workflow results remain available after restart.

**AC3.** Approval/rejection decisions remain available after restart.

**AC4.** Audit records remain available after restart.

**AC5.** The relationship between a document and its stored metadata/history remains intact.

---

# EPIC 9 — Performance, Scalability & Observability

## CARD US-41 — Responsive Application APIs

### FRONT

**As a Kagaz user,**  
I want normal application operations to respond quickly,  
**so that routine interaction with the platform does not feel blocked by unnecessary latency.**

**Stakeholder:** All application users  
**Traceability:** NFR-PERF-01

### BACK — Acceptance Criteria

**AC1.** Normal synchronous API operations that do not perform long-running AI work return within **2 seconds for at least 95% of requests** under the defined normal test workload.

**AC2.** Long-running AI operations are not counted as normal synchronous operations for this requirement.

**AC3.** Performance is validated using measured latency during performance testing.

---

## CARD US-42 — Scalable Concurrent Processing

### FRONT

**As a System Admin,**  
I want Kagaz to process increasing document volumes and concurrent jobs without redesigning the core architecture,  
**so that platform usage can grow without making the workflow unreliable.**

**Stakeholder:** System Admin, IT Stakeholder  
**Traceability:** NFR-SCAL-02, NFR-SCAL-03

### BACK — Acceptance Criteria

**AC1.** Increasing document volume does not require redesign of the core document-processing architecture.

**AC2.** Multiple document-processing jobs can run concurrently.

**AC3.** Increased workload does not cause unrelated jobs to fail merely because another job is problematic.

**AC4.** Load testing demonstrates acceptable operation at increasing document and job volumes.

**AC5.** Queueing and retry behavior remain observable under concurrent workload.

---

## CARD US-43 — Processing & System Monitoring

### FRONT

**As a System Admin,**  
I want operational visibility into queued, processing, completed, failed, and human-action-required work,  
**so that I can identify platform and workflow problems before they become invisible backlogs.**

**Stakeholder:** System Admin, IT Stakeholder  
**Traceability:** NFR-OBS-02

### BACK — Acceptance Criteria

**AC1.** Operational information identifies queued processing jobs.

**AC2.** Operational information identifies processing jobs.

**AC3.** Operational information identifies completed jobs.

**AC4.** Operational information identifies failed jobs.

**AC5.** Operational information identifies documents waiting for human action.

**AC6.** Authorized administrators can use the information to distinguish processing issues from human workflow backlog.

---

## CARD US-44 — Structured Operational Logging

### FRONT

**As an IT Stakeholder,**  
I want structured logs for significant system and processing events,  
**so that operational failures can be investigated without exposing unnecessary document content.**

**Stakeholder:** IT Stakeholder, System Admin  
**Traceability:** NFR-OBS-01

### BACK — Acceptance Criteria

**AC1.** Significant processing events generate structured log entries.

**AC2.** Errors generate structured log entries.

**AC3.** Warnings generate structured log entries where applicable.

**AC4.** Service failures generate structured log entries.

**AC5.** Logs avoid exposing sensitive document content unnecessarily.

**AC6.** Representative success and failure scenarios produce useful operational log records.

---

## CARD US-45 — Safe Error Visibility & Diagnosis

### FRONT

**As an IT Stakeholder,**  
I want detailed diagnostic information internally while users receive safe, understandable error messages,  
**so that problems can be resolved without leaking sensitive implementation details.**

**Stakeholder:** IT Stakeholder, System Admin, Submitter, Reviewer  
**Traceability:** NFR-OBS-03, NFR-USE-01

### BACK — Acceptance Criteria

**AC1.** User-facing failures provide an understandable explanation of what happened and what action, if any, is required.

**AC2.** Internal diagnostics contain sufficient information for authorized administrators or developers to investigate the problem.

**AC3.** User-facing errors do not expose sensitive implementation details.

**AC4.** Error handling communicates processing failures, missing information, and low-confidence states clearly.

---

# EPIC 10 — Usability, Accessibility & Maintainability

## CARD US-46 — Clear Workflow Feedback

### FRONT

**As a Submitter or Reviewer,**  
I want Kagaz to clearly communicate processing states, errors, missing information, low-confidence results, and required actions,  
**so that I always understand what is happening and what I need to do next.**

**Stakeholder:** Submitter, Reviewer, Approver, Vendor  
**Traceability:** NFR-USE-01

### BACK — Acceptance Criteria

**AC1.** Processing states are clearly communicated.

**AC2.** Errors are clearly communicated.

**AC3.** Missing-information issues are clearly communicated.

**AC4.** Low-confidence results are clearly identified.

**AC5.** Required user actions are clearly identified.

**AC6.** User messages are understandable without exposing implementation details.

---

## CARD US-47 — Consistent & Accessible Interface

### FRONT

**As a Kagaz user,**  
I want the interface to use consistent navigation, terminology, controls, and accessible interaction patterns,  
**so that I can use the system predictably regardless of my role or accessibility needs.**

**Stakeholder:** All application users  
**Traceability:** NFR-USE-02, NFR-USE-03

### BACK — Acceptance Criteria

**AC1.** User, reviewer, approver, and organization-management views use consistent terminology.

**AC2.** Navigation and controls follow consistent patterns.

**AC3.** Status indicators and layouts are used consistently.

**AC4.** Core interactions are keyboard accessible.

**AC5.** Interface controls have meaningful labels.

**AC6.** Informative images have appropriate alternative text.

**AC7.** Text and UI elements meet the project’s approved readability and contrast requirements.

---

## CARD US-48 — Modular Platform Architecture

### FRONT

**As an IT Stakeholder,**  
I want Kagaz’s major concerns separated into clear modules,  
**so that individual areas can be changed, tested, and extended without unnecessarily affecting the rest of the platform.**

**Stakeholder:** IT Stakeholder, System Admin  
**Traceability:** NFR-MAIN-01

### BACK — Acceptance Criteria

**AC1.** Authentication is separated as a distinct concern.

**AC2.** Organization management is separated as a distinct concern.

**AC3.** Documents are separated from AI-processing concerns.

**AC4.** RAG and policy functionality are separated from workflow and approval concerns.

**AC5.** Notification and auditing concerns are independently identifiable.

**AC6.** Module boundaries are documented and reviewable.

---

## CARD US-49 — Replaceable External Service Providers

### FRONT

**As an IT Stakeholder,**  
I want external AI, OCR, storage, and notification providers accessed through defined interfaces,  
**so that a provider can be replaced without rewriting core business logic.**

**Stakeholder:** IT Stakeholder, System Admin  
**Traceability:** NFR-INT-02

### BACK — Acceptance Criteria

**AC1.** External AI services are accessed behind a defined service boundary.

**AC2.** OCR services are accessed behind a defined service boundary.

**AC3.** Storage services are accessed behind a defined service boundary.

**AC4.** Notification services are accessed behind a defined service boundary.

**AC5.** Provider-specific implementation is isolated from core workflow logic.

**AC6.** A provider can be replaced through configuration or adapter implementation with minimal changes to core business logic.

---

## CARD US-50 — Secure Credential & Secret Management

### FRONT

**As an IT Stakeholder,**  
I want credentials and integration secrets managed outside application source code,  
**so that deployment and source repositories do not become a source of platform compromise.**

**Stakeholder:** IT Stakeholder, System Admin  
**Traceability:** NFR-SEC-05

### BACK — Acceptance Criteria

**AC1.** API keys are not hard-coded in source code.

**AC2.** Database passwords are not committed to the repository.

**AC3.** Authentication secrets are not committed to the repository.

**AC4.** Deployment configuration does not expose secrets in source-controlled files.

**AC5.** Repository and deployment review can verify the absence of hard-coded secrets.

---

## CARD US-51 — Maintainable Code & Documentation

### FRONT

**As an IT Stakeholder,**  
I want the codebase and major APIs documented according to agreed conventions,  
**so that another team member can understand, maintain, test, and extend Kagaz safely.**

**Stakeholder:** IT Stakeholder  
**Traceability:** NFR-MAIN-03

### BACK — Acceptance Criteria

**AC1.** Source code follows agreed project coding conventions.

**AC2.** Major modules have sufficient documentation.

**AC3.** Major APIs have sufficient documentation.

**AC4.** Documentation is sufficient for another team member to understand the relevant component.

**AC5.** Code review checks coding standards and documentation expectations.

---

# MASTER STAKEHOLDER COVERAGE

| Stakeholder | Covered by cards |
|---|---|
| **Submitter** | US-01, US-04, US-06, US-09, US-10, US-12, US-21, US-30, US-31, US-32, US-33, US-39, US-46, US-47 |
| **Reviewer** | US-04, US-06, US-10, US-11, US-12, US-13, US-14, US-15, US-16, US-17, US-19, US-20, US-21, US-24, US-25, US-26, US-27, US-31, US-32, US-33, US-39, US-45, US-46, US-47 |
| **Approver** | US-04, US-10, US-14, US-16, US-17, US-19, US-20, US-21, US-25, US-27, US-28, US-29, US-30, US-31, US-32, US-33, US-47 |
| **Org Admin** | US-03, US-04, US-05, US-18, US-27, US-32 |
| **System Admin** | US-01, US-02, US-04, US-05, US-08, US-10, US-27, US-34, US-37, US-38, US-40, US-42, US-43, US-44, US-45, US-48, US-49, US-50 |
| **Compliance Officer** | US-03, US-05, US-12, US-16, US-17, US-18, US-19, US-20, US-21, US-22, US-23, US-35, US-36, US-40 |
| **IT Stakeholder** | US-04, US-08, US-10, US-11, US-37, US-38, US-39, US-40, US-41, US-42, US-43, US-44, US-45, US-47, US-48, US-49, US-50, US-51 |
| **Auditor** | US-20, US-23, US-26, US-29, US-32, US-35, US-36, US-40 |
| **Management** | US-30, US-32, US-33, US-34 |
| **Vendor** | US-07, US-09, US-30, US-31 |

---

# FUNCTIONAL REQUIREMENT TRACEABILITY

| Functional Requirement | Covered by |
|---|---|
| FR-01 Authentication | US-01 |
| FR-02 User & role management | US-02 |
| FR-03 Role-based access | US-04 |
| FR-04 Document upload | US-06, US-07 |
| FR-05 Metadata & storage | US-08 |
| FR-06 OCR / text extraction | US-11 |
| FR-07 Classification | US-12 |
| FR-08 Classification correction | US-13 |
| FR-09 Key-field extraction | US-14 |
| FR-10 Extraction correction | US-15 |
| FR-11 Policy & knowledge base | US-18 |
| FR-12 Policy validation | US-19 |
| FR-13 Validation evidence | US-20 |
| FR-14 Missing/inconsistent information | US-16 |
| FR-15 Low-confidence handling | US-17 |
| FR-16 Review queue | US-24 |
| FR-17 Document review | US-25 |
| FR-18 Review notes/corrections | US-26 |
| FR-19 Routing/reassignment | US-27 |
| FR-20 Approval queue | US-28 |
| FR-21 Approval/rejection | US-29 |
| FR-22 Status tracking | US-30 |
| FR-23 Audit trail | US-35 |
| FR-24 Notifications | US-31 |
| FR-25 Search/filtering | US-32 |
| FR-26 Document details/summary | US-33 |
| FR-27 AI chatbot/RAG | US-21, US-22 |
| FR-28 Error handling/completion | US-38, US-39, US-45 |

---

# NFR COVERAGE

| NFR | Covered by |
|---|---|
| NFR-PERF-01 API response time | US-41 |
| NFR-PERF-02 Upload acknowledgement | US-09 |
| NFR-PERF-03 Async processing | US-10 |
| NFR-SCAL-01 Multi-organization scalability | US-05 |
| NFR-SCAL-02 Document-volume scalability | US-42 |
| NFR-SCAL-03 Concurrent processing | US-10, US-37, US-42 |
| NFR-SEC-01 Authentication | US-01 |
| NFR-SEC-02 RBAC | US-02, US-03, US-04 |
| NFR-SEC-03 Organization isolation | US-04, US-05 |
| NFR-SEC-04 Encryption in transit | Deployment acceptance criterion / technical validation |
| NFR-SEC-05 Secret management | US-50 |
| NFR-SEC-06 Secure file handling | US-08 |
| NFR-REL-01 Failure isolation | US-37 |
| NFR-REL-02 Retry/recovery | US-38 |
| NFR-REL-03 Durability | US-40 |
| NFR-REL-04 Graceful degradation | US-39 |
| NFR-AI-01 Low-confidence handling | US-13, US-15, US-17 |
| NFR-AI-02 Policy-grounded RAG | US-19, US-21 |
| NFR-AI-03 Org/domain-aware retrieval | US-19, US-22 |
| NFR-AI-04 AI evidence traceability | US-20 |
| NFR-USE-01 Clear feedback | US-45, US-46 |
| NFR-USE-02 Consistent UI | US-47 |
| NFR-USE-03 Accessibility | US-47 |
| NFR-MAIN-01 Modular architecture | US-48 |
| NFR-MAIN-02 Configurability | US-05, US-18 |
| NFR-MAIN-03 Code/documentation quality | US-51 |
| NFR-AUD-01 Audit integrity | US-35 |
| NFR-AUD-02 End-to-end traceability | US-36 |
| NFR-AUD-03 Policy version traceability | US-23 |
| NFR-INT-01 Supported formats | US-06, US-11 |
| NFR-INT-02 External service abstraction | US-49 |
| NFR-OBS-01 Application logging | US-44 |
| NFR-OBS-02 Processing monitoring | US-43 |
| NFR-OBS-03 Error diagnosis/visibility | US-45 |

---

# EPIC SUMMARY

| Epic | Cards |
|---|---:|
| Identity, Roles & Organization Control | 5 |
| Submission, File Handling & Ingestion | 5 |
| AI Processing, Extraction & Exception Detection | 7 |
| Policy, Validation & RAG | 6 |
| Human Review, Routing & Approval | 8 |
| Search, Visibility & Management Information | 3 |
| Audit, Traceability & Governance | 2 |
| Reliability, Recovery & Operational Control | 4 |
| Performance, Scalability & Observability | 5 |
| Usability, Accessibility & Maintainability | 6 |
| **Total** | **51** |

---

# Definition of a Strong Completed Card

A card should be considered implementation-ready when:

### The Front
- identifies one primary stakeholder;
- expresses one coherent capability;
- explains the stakeholder value;
- is traceable to a source requirement or clearly marked as elicitation-derived.

### The Back
- contains observable, testable behavior;
- defines both the happy path and important failure/exception behavior;
- enforces authorization where relevant;
- preserves traceability/auditability where relevant;
- does not invent unsupported business rules;
- uses configured/agreed values where the source has not yet fixed a value.

---

# Important Requirement Gaps That Should Not Be Silently Invented

The four source documents do **not** currently specify several implementation details such as exact file-size limits, exact confidence percentages, notification channels, exact management KPI formulas, detailed workflow-routing rules, or the precise policy-authoring syntax.

The elicitation document explicitly says requirements may change as elicitation continues, and some stakeholder requirements are still marked ongoing or not started.

Those should therefore be treated as **open requirements / acceptance-criteria parameters**, not guessed values.
