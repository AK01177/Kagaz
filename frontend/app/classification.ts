export interface DocumentRecord {
  document_id: string;
  filename: string;
  file_type?: string;
  file_size?: number;
  status: string;
  uploaded_at?: string;
  category?: string | null;
  confidence?: number | null;
  submitter_id?: string;
  organization_id?: string;
  is_manually_corrected?: boolean;
  last_corrected_at?: string;
  classification_history?: Array<{
    previous_category?: string | null;
    previous_confidence?: number | null;
    updated_category: string;
    corrected_at: string;
    notes?: string;
    corrected_by?: string;
  }>;
}

export interface DocumentTypeOption {
  value: string;
  label: string;
  categoryName: string;
  badge: string;
  icon: string;
  description: string;
  routing: string;
}

export const VALID_DOCUMENT_TYPES: DocumentTypeOption[] = [
  {
    value: "invoice",
    label: "Commercial Invoice",
    categoryName: "Commercial Invoice",
    badge: "Financial",
    icon: "🧾",
    description: "Billing statement specifying line items, supplier details, tax amounts, and payment obligations.",
    routing: "Accounts Payable Queue",
  },
  {
    value: "contract",
    label: "Legal Contract & Agreement",
    categoryName: "Legal Contract & Agreement",
    badge: "Legal",
    icon: "📑",
    description: "Legally enforceable agreement defining mutual covenants, liabilities, and governance terms.",
    routing: "Legal & Compliance Queue",
  },
  {
    value: "hr_form",
    label: "Human Resources Record",
    categoryName: "Human Resources Record",
    badge: "Personnel",
    icon: "👥",
    description: "Personnel filing, onboarding form, resume, or employment compliance record.",
    routing: "HR Records Queue",
  },
  {
    value: "academic_record",
    label: "Academic Record & Transcript",
    categoryName: "Academic Record & Transcript",
    badge: "Credentials",
    icon: "🎓",
    description: "Official institutional transcript or credential documentation verifying educational completion.",
    routing: "Academic Verification Queue",
  },
  {
    value: "financial_report",
    label: "Financial Statement & Report",
    categoryName: "Financial Statement & Report",
    badge: "Audit & Fiscal",
    icon: "📊",
    description: "Balance sheet, income statement, audit documentation, or corporate fiscal disclosure.",
    routing: "Finance & Accounting Queue",
  },
  {
    value: "identity_document",
    label: "Identity & Verification Record",
    categoryName: "Identity & Verification Record",
    badge: "KYC Compliance",
    icon: "🪪",
    description: "Official identification, verification credential, or identity compliance filing.",
    routing: "Identity Verification Queue",
  },
  {
    value: "policy_document",
    label: "Policy & Governance Document",
    categoryName: "Policy & Governance Document",
    badge: "Governance",
    icon: "⚖️",
    description: "Institutional policy standard, compliance charter, or operating procedure.",
    routing: "Policy Governance Queue",
  },
  {
    value: "other",
    label: "Other / General Business Document",
    categoryName: "Enterprise Business Document",
    badge: "General",
    icon: "📄",
    description: "Standard document intake. Contents parsed and indexed for policy validation.",
    routing: "General Review Queue",
  },
];

export interface CategoryInfo {
  name: string;
  badge: string;
  icon: string;
  description: string;
  routing: string;
  reviewUrl: string;
}

export function getCategoryInfo(rawCategory?: string | null, documentId?: string): CategoryInfo {
  const norm = (rawCategory ?? "").toLowerCase().trim();
  const docQuery = documentId ? `&id=${encodeURIComponent(documentId)}` : "";

  if (norm.includes("invoice") || norm.includes("bill") || norm.includes("receipt")) {
    return {
      name: "Commercial Invoice",
      badge: "Financial",
      icon: "🧾",
      description: "Billing statement specifying line items, supplier details, tax amounts, and payment obligations.",
      routing: "Accounts Payable Queue",
      reviewUrl: `/review?type=invoice${docQuery}`,
    };
  }
  if (norm.includes("contract") || norm.includes("agreement") || norm.includes("nda") || norm.includes("lease")) {
    return {
      name: "Legal Contract & Agreement",
      badge: "Legal",
      icon: "📑",
      description: "Legally enforceable agreement defining mutual covenants, liabilities, and governance terms.",
      routing: "Legal & Compliance Queue",
      reviewUrl: `/review?type=contract${docQuery}`,
    };
  }
  if (norm.includes("academic") || norm.includes("transcript") || norm.includes("diploma") || norm.includes("degree")) {
    return {
      name: "Academic Record & Transcript",
      badge: "Credentials",
      icon: "🎓",
      description: "Official institutional transcript or credential documentation verifying educational completion.",
      routing: "Academic Verification Queue",
      reviewUrl: `/review?type=academic${docQuery}`,
    };
  }
  if (norm.includes("hr") || norm.includes("employee") || norm.includes("payroll") || norm.includes("resume") || norm.includes("cv")) {
    return {
      name: "Human Resources Record",
      badge: "Personnel",
      icon: "👥",
      description: "Personnel filing, onboarding form, resume, or employment compliance record.",
      routing: "HR Records Queue",
      reviewUrl: `/review?type=hr${docQuery}`,
    };
  }
  if (norm.includes("financial") || norm.includes("tax") || norm.includes("statement") || norm.includes("audit") || norm.includes("report")) {
    return {
      name: "Financial Statement & Report",
      badge: "Audit & Fiscal",
      icon: "📊",
      description: "Balance sheet, income statement, audit documentation, or corporate fiscal disclosure.",
      routing: "Finance & Accounting Queue",
      reviewUrl: `/review?type=financial${docQuery}`,
    };
  }
  if (norm.includes("identity") || norm.includes("id") || norm.includes("passport") || norm.includes("kyc")) {
    return {
      name: "Identity & Verification Record",
      badge: "KYC Compliance",
      icon: "🪪",
      description: "Official identification, verification credential, or identity compliance filing.",
      routing: "Identity Verification Queue",
      reviewUrl: `/review?type=identity${docQuery}`,
    };
  }
  if (norm.includes("policy") || norm.includes("guideline") || norm.includes("rule")) {
    return {
      name: "Policy & Governance Document",
      badge: "Governance",
      icon: "⚖️",
      description: "Institutional policy standard, compliance charter, or operating procedure.",
      routing: "Policy Governance Queue",
      reviewUrl: `/review?type=policy${docQuery}`,
    };
  }
  if (rawCategory && rawCategory !== "unknown" && rawCategory !== "general_document") {
    return {
      name: rawCategory.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      badge: "Categorized",
      icon: "📋",
      description: "Classified into standard document taxonomy for automated policy evaluation.",
      routing: "Designated Workflow Queue",
      reviewUrl: `/review?type=${encodeURIComponent(rawCategory)}${docQuery}`,
    };
  }
  return {
    name: "Enterprise Business Document",
    badge: "General",
    icon: "📄",
    description: "Standard document intake. Contents parsed and indexed for policy validation.",
    routing: "General Review Queue",
    reviewUrl: `/review${docQuery ? `?${docQuery.slice(1)}` : ""}`,
  };
}

export function formatFileSize(bytes?: number): string {
  if (!bytes || isNaN(bytes)) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function formatDate(isoString?: string): string {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    });
  } catch {
    return isoString;
  }
}

