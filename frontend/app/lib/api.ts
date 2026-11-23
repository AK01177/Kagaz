// The backend always answers errors as { error: { code, message } }.
// Older routes may still send { detail: ... }, so accept both.
export function apiError(data: unknown, fallback: string): string {
  const body = data as { error?: { message?: unknown }; detail?: { message?: unknown } | string } | null;
  const message = body?.error?.message ?? (typeof body?.detail === "string" ? body.detail : body?.detail?.message);
  return typeof message === "string" && message ? message : fallback;
}
