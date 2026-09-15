# Kagaz – Requirement Elicitation

## 1. Introduction

Requirement elicitation is used to understand what different stakeholders
expect from Kagaz and what problems the system should solve.

Kagaz is intended to handle documents from Academic, HR, and Finance
domains. Since different stakeholders interact with documents at different
stages, different elicitation techniques are used according to their role.

The elicitation process is iterative. Some requirements may change as the
team gathers more information.

---

## 2. Elicitation Approach

The team will use the following techniques:

| Technique         | Purpose                                           |
| ----------------- | ------------------------------------------------- |
| Interview         | Understand detailed needs, problems and decisions |
| Survey            | Collect common requirements from multiple users   |
| Observation       | Understand how users currently perform their work |
| Workshop          | Discuss roles, permissions and workflows together |
| Document Analysis | Understand existing policies and rules            |
| Questionnaire     | Collect structured feedback                       |
| Prototyping       | Understand expectations for AI-based interactions |

The selected technique depends on the type of information expected from
each stakeholder.

---

## 3. Stakeholder-wise Elicitation

### 3.1 Submitter

**Selected Techniques:** Survey and Interview

The Submitter is the person who starts the document workflow. This role
may represent employees or external users such as vendors.

The survey will help identify common problems across users, while interviews
will provide more detailed information about individual experiences.

**Main areas to investigate:**

- Documents commonly submitted
- Problems during submission
- Information users find difficult to provide
- Expected feedback after submission
- Expected document status information
- Problems caused by missing or incorrect information

**Expected result:**

A clear understanding of the submission process and the information and
feedback users expect from Kagaz.

**Status:** Ongoing

---

### 3.2 Reviewer

**Selected Techniques:** Interview and Observation

The Reviewer checks documents that require additional attention. Their
requirements are closely related to how documents are checked and corrected.

Interviews will identify what information reviewers need, while observation
can help understand the actual review process.

**Main areas to investigate:**

- Information checked during review
- Common reasons for manual review
- How incorrect information is corrected
- How reviewers handle incomplete documents
- Information needed before forwarding a document
- Problems with current review processes

**Expected result:**

Requirements for reviewing, correcting and handling documents that cannot
be processed automatically.

**Status:** Ongoing

---

### 3.3 Approver

**Selected Technique:** Interview

The Approver is responsible for making the final decision on a document.
The interview will focus on the information needed to make that decision
and how the approval process currently works.

**Main areas to investigate:**

- Information required before making a decision
- Conditions for approval or rejection
- How documents reach the correct approver
- Information that should be visible during approval
- Requirements for comments and reasons
- Situations requiring reassignment or escalation

**Expected result:**

A clear approval workflow and requirements for approval, rejection and
routing.

**Status:** Ongoing

---

### 3.4 System Admin

**Selected Technique:** Workshop

A workshop is suitable because administration involves several related
topics such as users, roles, permissions and system settings.

The team will discuss these topics together instead of treating each
administrative function separately.

**Main areas to investigate:**

- Required user roles
- Permissions for each role
- User management
- System configuration
- Administrative information
- Audit and system activity

**Expected result:**

A basic model for user management, roles, permissions and administration.

**Status:** Not Started

---

### 3.5 Compliance Officer

**Selected Techniques:** Document Analysis and Interview

The Compliance Officer is responsible for the policies that Kagaz may use
during document validation.

First, relevant policy documents can be studied to understand the rules.
An interview can then clarify rules that are unclear or difficult to
interpret.

**Main areas to investigate:**

- Policies applicable to different document types
- Mandatory information
- Conditions that make a document non-compliant
- Rules suitable for automatic checking
- Evidence required to support a validation result
- Handling of updated policies

**Expected result:**

A set of policy and compliance requirements that can later be used for
validation and RAG.

**Status:** Ongoing

---

### 3.6 Auditor

**Selected Technique:** Questionnaire

The Auditor is mainly concerned with whether document processing can be
traced and verified.

A questionnaire can collect these requirements in a structured way.

**Main areas to investigate:**

- Actions that need to be recorded
- Information required during an audit
- Required document history
- Evidence needed for decisions
- Access required by auditors
- Information needed to verify AI decisions

**Expected result:**

Requirements for audit trails, traceability and retained evidence.

**Status:** Not Started

---

### 3.7 IT Stakeholder

**Selected Techniques:** Document Analysis and Interview

The IT Stakeholder focuses on technical and operational concerns.

Existing technical or organizational guidelines can first be reviewed,
followed by an interview to identify practical constraints.

**Main areas to investigate:**

- Deployment requirements
- Security expectations
- Infrastructure limitations
- Monitoring requirements
- Logging requirements
- Performance and availability expectations
- Maintenance requirements

**Expected result:**

Technical and operational constraints that influence the system design.

**Status:** Ongoing

---

### 3.8 Management Stakeholder

**Selected Technique:** Interview

Management is mainly interested in the overall purpose and value of Kagaz
rather than its technical implementation.

The interview will therefore focus on business goals, priorities and
information needed for monitoring.

**Main areas to investigate:**

- Main problems Kagaz should solve
- Expected benefits
- Important workflow information
- Useful reports and dashboards
- Important performance indicators
- Features that should receive higher priority

**Expected result:**

Business priorities and high-level expectations for the system.

**Status:** Not Started

---

## 4. Elicitation Progress

| Stakeholder            | Technique                     | Current Status |
| ---------------------- | ----------------------------- | -------------- |
| Submitter              | Survey + Interview            | Ongoing        |
| Reviewer               | Interview + Observation       | Ongoing        |
| Approver               | Interview                     | Ongoing        |
| System Admin           | Workshop                      | Not Started    |
| Compliance Officer     | Document Analysis + Interview | Ongoing        |
| Auditor                | Questionnaire                 | Not Started    |
| IT Stakeholder         | Document Analysis + Interview | Ongoing        |
| Management Stakeholder | Interview                     | Not Started    |

The status will be updated as the team completes each elicitation activity.

---

## 5. Handling the Three Domains

The initial Kagaz scope contains three domains:

- Academic
- HR
- Finance

The same stakeholder role may exist across different domains.

For example, a Submitter may be a student in the Academic domain,
an employee in the HR domain, or an employee/vendor in the Finance domain.

Similarly, Reviewers and Approvers may be different people depending on
the document and organization.

Therefore, the team will first define general stakeholder requirements
and then identify domain-specific requirements where necessary.

---

## 6. Assumptions

- Kagaz is currently a course project and does not have access to a real
  organization's internal stakeholders.
- Stakeholder roles are based on typical document-processing workflows.
- Role-play personas may be used during elicitation.
- Public documents may be used when examples of policies or rules are
  required.
- Requirements gathered from assumptions or role-play will be treated as
  provisional.
- Requirements may be modified as elicitation continues.
