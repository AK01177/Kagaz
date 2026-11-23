// Three areas: /workspace (submitters, reviewers, approvers), /org (org admins), /admin (system admins).
export const WORKSPACE_ROLES = ["SUBMITTER", "REVIEWER", "APPROVER"];
export const ORG_ROLES = ["ORG_ADMIN", "SYSTEM_ADMIN"];
export const ADMIN_ROLES = ["SYSTEM_ADMIN"];

/** The page each role lands on after choosing an organization. */
export function homeForRole(role?: string | null): string {
  if (role === "SYSTEM_ADMIN") return "/admin/organizations";
  if (role === "ORG_ADMIN") return "/org/members";
  return "/workspace/dashboard";
}

export const ROLE_LABELS: Record<string, string> = {
  SUBMITTER: "Submitter",
  REVIEWER: "Reviewer",
  APPROVER: "Approver",
  ORG_ADMIN: "Organization Admin",
  SYSTEM_ADMIN: "System Admin",
};
