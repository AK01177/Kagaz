"use client";

import { ProtectedRoute } from "../components/ProtectedRoute";
import { WORKSPACE_ROLES } from "../lib/roles";

// Everything under /workspace is only for these roles; the backend enforces the same rules.
export default function AreaLayout({ children }: { children: React.ReactNode }) {
  return <ProtectedRoute allowedRoles={WORKSPACE_ROLES}>{children}</ProtectedRoute>;
}
