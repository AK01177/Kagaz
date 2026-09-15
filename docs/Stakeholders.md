# Kagaz – Stakeholder Documentation

## Objective

Identify and document the stakeholders who interact with, depend on, or are affected by Kagaz.

> **Assumption:** Kagaz is a course project, so there is no real organization to interview. The details below are based on typical document approval and compliance workflows.

## Stakeholders at a Glance

| Stakeholder | Type |
|---|---|
| Submitter | Primary user |
| Reviewer | Primary user |
| Approver | Primary user |
| System Admin | Internal user |
| Compliance Officer | Domain expert |
| Auditor | External party |
| IT Stakeholder | Internal stakeholder |
| Management Stakeholder | Internal stakeholder |

## 1. Submitter

**Role**  
Uploads documents such as invoices, contracts, and HR forms into Kagaz for processing.

**Goals**  
Submit documents easily and receive fast and accurate processing.

**Problems**  
Unclear document status and unclear reasons for delays or rejection.

**Information Needed**  
Upload confirmation, status updates, and reasons for flagged documents.

**Information Provided**  
Documents and metadata entered during upload.

**Influence on the System**  
Low. The Submitter starts the workflow but does not control later stages.

**Assumption**  
The Submitter may be an employee or, occasionally, an external party such as a vendor.

## 2. Reviewer

**Role**  
Checks documents flagged by Kagaz for missing or inconsistent information before final approval.

**Goals**  
Quickly verify system results without repeating work that is already correct.

**Problems**  
Low-confidence AI outputs and unclear reasons for flags.

**Information Needed**  
Extracted fields, confidence scores, and relevant policy clauses.

**Information Provided**  
Corrections, review notes, and escalation or forwarding decisions.

**Influence on the System**  
Moderate. The Reviewer can correct system results within defined limits.

**Assumption**  
The Reviewer works between automated processing and final approval.

## 3. Approver

**Role**  
The manager or authorized person who gives final approval or rejection.

**Goals**  
Make quick and informed decisions using sufficient supporting information.

**Problems**  
Incorrect routing and insufficient evidence for decisions.

**Information Needed**  
Document summary, extracted fields, validation results, and supporting evidence.

**Information Provided**  
Approval or rejection decision, comments, and occasional reassignment.

**Influence on the System**  
High. The Approver directly determines document outcomes and contributes to the audit trail.

## 4. System Admin

**Role**  
Manages user accounts, roles, permissions, and general system health.

**Goals**  
Maintain accurate access control and keep the system secure and available.

**Problems**  
Incorrect role assignments and limited system-wide visibility.

**Information Needed**  
User and role lists, system health data, and error logs.

**Information Provided**  
Account setup, role changes, and configuration updates.

**Influence on the System**  
High. The System Admin controls user access and system configuration.

## 5. Compliance Officer

**Role**  
Owns the policies used by Kagaz to validate documents.

**Goals**  
Ensure documents are checked against current policies with clear reasoning.

**Problems**  
Outdated policies or incorrect policy references.

**Information Needed**  
Current policy documents and validation results with cited clauses.

**Information Provided**  
Policy documents, policy updates, and clarification of ambiguous rules.

**Influence on the System**  
High. The policies provided by the Compliance Officer directly affect validation logic.

## 6. Auditor

**Role**  
An external reviewer who checks Kagaz records for compliance, usually after processing.

**Goals**  
Confirm that documents were handled correctly and consistently with policy.

**Problems**  
Incomplete or editable logs and unclear document-to-decision history.

**Information Needed**  
Complete audit trails and the policy version active at the time of processing.

**Information Provided**  
**Assumption:** Usually nothing directly. The Auditor may report process issues to Compliance or Admin.

**Influence on the System**  
Low in daily operations but high in system design because auditing requirements must be supported.

## 7. IT Stakeholder

**Role**  
Represents IT or DevOps and focuses on integration, deployment, and security.

**Goals**  
Ensure smooth deployment, strong security, and low maintenance effort.

**Problems**  
Integration limitations, security gaps, and scaling issues.

**Information Needed**  
Architecture, deployment plans, and security implementation details.

**Information Provided**  
Infrastructure constraints and security requirements.

**Influence on the System**  
Moderate to high. The IT Stakeholder shapes the technical setup and can restrict unsuitable designs.

## 8. Management Stakeholder

**Role**  
Sets priorities and evaluates the overall value of Kagaz.

**Goals**  
Improve visibility, reduce manual work, and reduce operational risk.

**Problems**  
Limited high-level performance visibility and unclear return on investment.

**Information Needed**  
Dashboards showing document volume, processing time, approval rates, and flagged issues.

**Information Provided**  
Priorities and approval for major process or policy changes.

**Influence on the System**  
Moderate. The Management Stakeholder shapes priorities, scope, and major decisions.

**Assumption**  
Represents department heads or executives who focus on outcomes rather than daily system operations.

## Methodology Note

No real organization was available for stakeholder interviews. Therefore, stakeholder needs were derived from role-based assumptions and typical document approval, invoice processing, HR, and compliance workflows.
