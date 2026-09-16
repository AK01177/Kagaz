# Kagaz – Non-Functional Requirements

## 1. Purpose

This document defines the Non-Functional Requirements (NFRs) for Kagaz, a multi-organization AI-powered document workflow automation platform.

Kagaz supports multiple organizations. Each organization can configure policies for the Academic, HR, and Finance domains. Authorized users can submit documents, which Kagaz processes through text extraction/OCR, classification, information extraction, policy-based validation, issue detection, routing, review, and approval.

These requirements define the quality attributes, constraints, and measurable expectations for the system rather than specific business functions.

---

## 2. NFR Categories

The requirements are grouped into:

- Performance
- Scalability
- Security and Privacy
- Reliability and Availability
- AI and RAG Quality
- Usability and Accessibility
- Maintainability
- Auditability and Traceability
- Interoperability
- Observability

---

# 3. Performance Requirements

## NFR-PERF-01: API Response Time

**Requirement:**  
For normal synchronous API operations that do not perform long-running AI processing, Kagaz shall return a response within **2 seconds for at least 95% of requests** under the defined normal test workload.

**Rationale:**  
Users should receive prompt feedback when interacting with the application.

**Measurement:**  
Measure API latency during performance testing and verify that at least 95% of requests meet the target.

---

## NFR-PERF-02: Document Upload Acknowledgement

**Requirement:**  
Kagaz shall acknowledge a valid document upload within **3 seconds**, excluding the time required for the actual background AI processing of the document.

**Rationale:**  
Users should not have to wait for OCR, classification, extraction, or RAG processing before receiving confirmation that the document was accepted.

**Measurement:**  
Measure the time from upload submission to upload acknowledgement.

---

## NFR-PERF-03: Background Processing

**Requirement:**  
Long-running operations such as OCR, classification, extraction, and policy validation shall execute asynchronously and shall not block normal user interface operations.

**Rationale:**  
Large or complex documents may require significant processing time.

**Measurement:**  
Verify that document-processing jobs run independently while normal authenticated requests remain responsive.

---

# 4. Scalability Requirements

## NFR-SCAL-01: Multi-Organization Scalability

**Requirement:**  
Kagaz shall support the addition of new organizations without requiring changes to the core document-processing workflow.

**Rationale:**  
The system is designed as a multi-organization platform.

**Measurement:**  
Demonstrate onboarding of additional organizations using configuration or stored organizational data rather than changes to core application logic.

---

## NFR-SCAL-02: Document Volume Scalability

**Requirement:**  
The system architecture shall support growth in the number of stored documents and processing jobs without requiring a redesign of the core architecture.

**Rationale:**  
Document volume is expected to increase as organizations use the platform.

**Measurement:**  
Perform load testing with increasing document and job volumes and verify acceptable operation.

---

## NFR-SCAL-03: Concurrent Processing

**Requirement:**  
Kagaz shall support concurrent document-processing jobs through a background processing mechanism without causing failure of unrelated jobs.

**Rationale:**  
Multiple users may submit documents simultaneously.

**Measurement:**  
Submit multiple processing jobs concurrently and verify successful completion, queueing, retry behavior, and isolation of failures.

---

# 5. Security and Privacy Requirements

## NFR-SEC-01: Authentication

**Requirement:**  
Kagaz shall require authentication before granting access to protected user or organization functions.

**Rationale:**  
Documents, policies, and workflow information must not be accessible anonymously.

**Measurement:**  
Verify that unauthenticated requests to protected resources are denied.

---

## NFR-SEC-02: Role-Based Access Control

**Requirement:**  
Kagaz shall enforce role-based access control so that users can perform only actions authorized for their assigned roles.

**Rationale:**  
Submitters, reviewers, approvers, organization administrators, system administrators, auditors, and other stakeholders have different responsibilities.

**Measurement:**  
Test protected operations with authorized and unauthorized roles.

---

## NFR-SEC-03: Organization-Level Data Isolation

**Requirement:**  
Kagaz shall prevent users from accessing documents, policies, knowledge-base data, workflow records, and audit information belonging to organizations for which they are not authorized.

**Rationale:**  
Multi-organization data isolation is a critical security requirement.

**Measurement:**  
Perform cross-organization access tests and verify that unauthorized requests are rejected.

---

## NFR-SEC-04: Data Encryption in Transit

**Requirement:**  
Kagaz shall protect sensitive data transmitted between the client, backend services, storage services, and external AI services using secure transport mechanisms.

**Rationale:**  
Academic, HR, and financial documents may contain sensitive information.

**Measurement:**  
Verify that deployed network communication uses HTTPS/TLS.

---

## NFR-SEC-05: Secure Credential and Secret Management

**Requirement:**  
Kagaz shall not store API keys, database passwords, authentication secrets, or other sensitive credentials directly in source code or committed repository files.

**Rationale:**  
Exposed credentials can compromise the platform.

**Measurement:**  
Review the repository and deployment configuration for hard-coded secrets.

---

## NFR-SEC-06: Secure File Handling

**Requirement:**  
Kagaz shall validate uploaded files for supported type, size, and basic integrity before processing them.

**Rationale:**  
File validation reduces the risk of unsafe or invalid content entering the processing pipeline.

**Measurement:**  
Test unsupported file types, oversized files, malformed files, and valid files.

---

# 6. Reliability and Availability Requirements

## NFR-REL-01: Processing Failure Isolation

**Requirement:**  
Failure of OCR, classification, extraction, RAG, or policy-validation processing for one document shall not cause unrelated document-processing jobs to fail.

**Rationale:**  
A single problematic document or service failure should not stop the entire system.

**Measurement:**  
Inject a processing failure for one job and verify that other jobs continue to process.

---

## NFR-REL-02: Retry and Recovery

**Requirement:**  
Kagaz shall support retry or recovery for transient background-processing failures without requiring users to upload the same document again.

**Rationale:**  
Temporary service or infrastructure errors should be recoverable.

**Measurement:**  
Simulate a transient processing failure and verify that the job can be retried or recovered.

---

## NFR-REL-03: Data Durability

**Requirement:**  
Successfully stored document metadata, workflow results, decisions, and audit records shall remain available after normal application restarts.

**Rationale:**  
Processing history and decisions must not be lost during routine restarts.

**Measurement:**  
Restart application services and verify persistence of previously stored records.

---

## NFR-REL-04: Graceful Degradation

**Requirement:**  
When a non-critical external dependency such as an AI provider is temporarily unavailable, Kagaz shall fail gracefully by showing an appropriate processing state or error instead of silently producing incomplete or misleading results.

**Rationale:**  
Users need clear visibility when automated processing cannot be completed.

**Measurement:**  
Simulate external-service failure and verify user-visible failure handling and document status updates.

---

# 7. AI and RAG Quality Requirements

## NFR-AI-01: Low-Confidence Handling

**Requirement:**  
Kagaz shall not treat classification or extraction results below the configured confidence threshold as final when the workflow requires human verification.

**Rationale:**  
AI-generated results may be uncertain and should support human review.

**Measurement:**  
Provide low-confidence test cases and verify that they are routed according to the configured workflow threshold.

---

## NFR-AI-02: Policy-Grounded RAG Responses

**Requirement:**  
Policy-related chatbot responses and policy explanations shall use relevant content from the applicable organization's knowledge base rather than relying solely on unsupported model-generated content.

**Rationale:**  
Validation and policy explanations should be grounded in the organization's configured policies.

**Measurement:**  
Test policy questions against known policy documents and verify that retrieved content supports the response.

---

## NFR-AI-03: Organization and Domain-Aware Retrieval

**Requirement:**  
RAG retrieval shall restrict policy information to the correct organization and applicable domain before generating a policy-related response or validation result.

**Rationale:**  
Using another organization's or another domain's policy could produce an incorrect result.

**Measurement:**  
Create multiple organizations and domains with distinguishable policies and verify that retrieval returns only applicable content.

---

## NFR-AI-04: AI Evidence Traceability

**Requirement:**  
Where policy evidence is available, Kagaz shall preserve and present the supporting policy source or reference associated with the AI-generated validation or policy-related answer.

**Rationale:**  
Users and reviewers need to understand the basis of AI-assisted results.

**Measurement:**  
Verify that policy-based results contain an associated source or policy reference.

---

# 8. Usability and Accessibility Requirements

## NFR-USE-01: Clear User Feedback

**Requirement:**  
Kagaz shall clearly communicate document-processing states, errors, missing information, low-confidence results, and required user actions.

**Rationale:**  
Users need to understand what is happening and what they must do next.

**Measurement:**  
Review each major workflow state and verify that an understandable status or action message is displayed.

---

## NFR-USE-02: Consistent User Interface

**Requirement:**  
The web interface shall use consistent navigation, terminology, controls, status indicators, and layouts across user, reviewer, approver, and organization-management views.

**Rationale:**  
Consistency reduces user confusion and training effort.

**Measurement:**  
Conduct UI review against the approved interface guidelines.

---

## NFR-USE-03: Accessibility

**Requirement:**  
The user interface should follow recognized web accessibility practices, including keyboard accessibility, meaningful labels, readable contrast, and appropriate alternative text for informative images.

**Rationale:**  
The platform should be usable by people with different accessibility needs.

**Measurement:**  
Perform accessibility checks using automated tooling and manual keyboard review.

---

# 9. Maintainability Requirements

## NFR-MAIN-01: Modular Architecture

**Requirement:**  
Kagaz shall use a modular architecture that separates major concerns such as authentication, organizations, documents, AI processing, RAG, policies, workflows, approvals, notifications, and auditing.

**Rationale:**  
Modularity makes the system easier to test, modify, and extend.

**Measurement:**  
Review the architecture and repository structure against the defined modules.

---

## NFR-MAIN-02: Configurability

**Requirement:**  
Organization-specific policy and workflow configuration shall be stored as data or configuration where practical rather than hard-coded into application logic.

**Rationale:**  
Different organizations may use different policies while the core Kagaz platform remains the same.

**Measurement:**  
Demonstrate organization-specific configuration without changing core business logic.

---

## NFR-MAIN-03: Code Quality and Documentation

**Requirement:**  
Source code shall follow the project's agreed coding conventions, and major modules and APIs shall include sufficient documentation for another team member to understand and maintain them.

**Rationale:**  
The project is collaboratively developed and must remain maintainable throughout development.

**Measurement:**  
Perform code review using the team's coding standards and documentation checklist.

---

# 10. Auditability and Traceability Requirements

## NFR-AUD-01: Audit Record Integrity

**Requirement:**  
Important document, workflow, policy, user, and decision events shall be recorded in a way that prevents ordinary users from modifying historical audit records through normal application functions.

**Rationale:**  
Audit records must provide trustworthy evidence of system activity.

**Measurement:**  
Verify that non-authorized users cannot edit or delete audit records through the application.

---

## NFR-AUD-02: End-to-End Traceability

**Requirement:**  
Kagaz shall allow an authorized reviewer or auditor to trace a document from submission through AI processing, validation, routing, review, and final decision.

**Rationale:**  
The complete document lifecycle should be reconstructable.

**Measurement:**  
Select a completed document and verify that each major workflow event can be reconstructed from stored records.

---

## NFR-AUD-03: Policy Version Traceability

**Requirement:**  
Validation and policy-related processing results shall remain associated with the specific policy version used at the time of processing.

**Rationale:**  
Historical results must not be silently changed when an organization updates its policies.

**Measurement:**  
Process a document under one policy version, update the policy, and verify that the historical result still references the original version.

---

# 11. Interoperability Requirements

## NFR-INT-01: Supported Document Formats

**Requirement:**  
Kagaz shall consistently handle the supported document formats defined by the functional requirements, including PDF, DOCX, and scanned image documents.

**Rationale:**  
Users may submit documents in different formats.

**Measurement:**  
Test each supported format through the upload and processing workflow.

---

## NFR-INT-02: External Service Abstraction

**Requirement:**  
Integration with external AI, OCR, storage, or notification providers shall be implemented behind clearly defined service interfaces so that individual providers can be replaced with minimal changes to core business logic.

**Rationale:**  
External providers may change, become unavailable, or need replacement.

**Measurement:**  
Review service boundaries and demonstrate provider replacement through configuration or an adapter implementation.

---

# 12. Observability Requirements

## NFR-OBS-01: Application Logging

**Requirement:**  
Kagaz shall maintain structured application logs for significant processing events, errors, warnings, and service failures without exposing sensitive document content unnecessarily.

**Rationale:**  
Logs are required for troubleshooting and operational visibility.

**Measurement:**  
Trigger representative success and failure scenarios and verify useful structured log entries.

---

## NFR-OBS-02: Processing Monitoring

**Requirement:**  
The system shall provide sufficient operational information to identify documents or background jobs that are queued, processing, completed, failed, or waiting for human action.

**Rationale:**  
Administrators need visibility into system and workflow health.

**Measurement:**  
Verify that job and document states can be monitored during normal and failed processing.

---

## NFR-OBS-03: Error Visibility and Diagnosis

**Requirement:**  
System errors shall provide sufficient diagnostic information to authorized administrators or developers while presenting user-facing error messages that do not expose sensitive implementation details.

**Rationale:**  
Users need understandable errors while developers need enough information to diagnose problems securely.

**Measurement:**  
Test representative failures and verify both user-facing messages and internal diagnostic information.

---

# 13. NFR Summary

| Category | Count |
|---|---:|
| Performance | 3 |
| Scalability | 3 |
| Security & Privacy | 6 |
| Reliability & Availability | 4 |
| AI & RAG Quality | 4 |
| Usability & Accessibility | 3 |
| Maintainability | 3 |
| Auditability & Traceability | 3 |
| Interoperability | 2 |
| Observability | 3 |
| **Total** | **34** |

> **Note:** The team may merge closely related requirements before final submission if the course requires a target closer to 25–30 NFRs. The current document intentionally keeps the requirements atomic so they can be individually tested and traced.

---

# 14. Highest-Priority NFRs for Kagaz

The following requirements are especially important to the initial Kagaz architecture:

- NFR-SEC-03 – Organization-Level Data Isolation
- NFR-SEC-02 – Role-Based Access Control
- NFR-AI-01 – Low-Confidence Handling
- NFR-AI-02 – Policy-Grounded RAG Responses
- NFR-AI-03 – Organization and Domain-Aware Retrieval
- NFR-AUD-02 – End-to-End Traceability
- NFR-AUD-03 – Policy Version Traceability
- NFR-REL-02 – Retry and Recovery
- NFR-MAIN-02 – Configurability
- NFR-OBS-02 – Processing Monitoring
