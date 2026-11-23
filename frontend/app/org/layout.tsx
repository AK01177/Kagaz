"use client";

import { ProtectedRoute } from "../components/ProtectedRoute";
import { ORG_ROLES } from "../lib/roles";

// Everything under /org is only for these roles; the backend enforces the same rules.
export default function AreaLayout({ children }: { children: React.ReactNode }) {
  return <ProtectedRoute allowedRoles={ORG_ROLES}>{children}</ProtectedRoute>;
}
