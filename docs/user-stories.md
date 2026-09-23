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