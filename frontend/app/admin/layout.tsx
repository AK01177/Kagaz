"use client";

import { ProtectedRoute } from "../components/ProtectedRoute";
import { ADMIN_ROLES } from "../lib/roles";

// Everything under /admin is only for these roles; the backend enforces the same rules.
export default function AreaLayout({ children }: { children: React.ReactNode }) {
  return <ProtectedRoute allowedRoles={ADMIN_ROLES}>{children}</ProtectedRoute>;
}
