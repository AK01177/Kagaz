"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

export interface AuthUser {
  user_id: string;
  email: string;
  name: string;
  role: string;
  organization_id: string;
  active: boolean;
}

export interface OrganizationMembership {
  organization_id: string;
  role: string;
}

export interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  activeOrgId: string | null;
  memberships: OrganizationMembership[];
  isAuthenticated: boolean;
  isLoading: boolean;
  sessionExpired: boolean;
  login: (
    email: string,
    password: string,
    organizationId?: string
  ) => Promise<{ success: boolean; error?: string }>;
  logout: (options?: { reason?: string }) => void;
  switchOrganization: (
    organizationId: string
  ) => Promise<{ success: boolean; error?: string }>;
  fetchWithAuth: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
  clearSessionExpiredNotice: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function decodeJwtPayload(token: string): { exp?: number; [key: string]: unknown } | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const json = atob(base64);
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export function isTokenExpired(token: string): boolean {
  const payload = decodeJwtPayload(token);
  if (!payload || !payload.exp) return false;
  // Expired if current time exceeds exp (with 5-second buffer)
  return Date.now() >= (payload.exp - 5) * 1000;
}

export function clearStoredSession(): void {
  const keys = [
    "kagaz_token",
    "kagaz_active_org",
    "kagaz_user_email",
    "kagaz_user_role",
    "kagaz_user_name",
  ];
  for (const k of keys) {
    try {
      localStorage.removeItem(k);
      sessionStorage.removeItem(k);
    } catch {
      // Ignore storage access errors in restricted environments
    }
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [activeOrgId, setActiveOrgId] = useState<string | null>(null);
  const [memberships, setMemberships] = useState<OrganizationMembership[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [sessionExpired, setSessionExpired] = useState<boolean>(false);

  const logout = useCallback(
    (options?: { reason?: string }) => {
      clearStoredSession();
      setToken(null);
      setUser(null);
      setActiveOrgId(null);
      setMemberships([]);
      if (options?.reason === "expired") {
        setSessionExpired(true);
      }
    },
    []
  );

  const clearSessionExpiredNotice = useCallback(() => {
    setSessionExpired(false);
  }, []);

  // Fetch verified profile and membership records from backend
  const refreshIdentity = useCallback(
    async (authToken: string, targetOrgId?: string | null) => {
      if (isTokenExpired(authToken)) {
        logout({ reason: "expired" });
        return false;
      }

      try {
        const headers: Record<string, string> = {
          Authorization: `Bearer ${authToken}`,
        };
        if (targetOrgId) {
          headers["X-Organization-Id"] = targetOrgId;
        }

        const [profileRes, membershipsRes] = await Promise.all([
          fetch(`${API_URL}/api/auth/me`, { headers }),
          fetch(`${API_URL}/api/auth/memberships`, { headers }),
        ]);

        if (profileRes.status === 401 || membershipsRes.status === 401) {
          logout({ reason: "expired" });
          return false;
        }

        if (!profileRes.ok) {
          // If the target organization is invalid/forbidden for the user, reset org context
          if (profileRes.status === 403 && targetOrgId) {
            const fallbackRes = await fetch(`${API_URL}/api/auth/me`, {
              headers: { Authorization: `Bearer ${authToken}` },
            });
            if (fallbackRes.ok) {
              const fallbackProfile = await fallbackRes.json();
              setUser({
                user_id: fallbackProfile.user_id,
                email: fallbackProfile.email || "",
                name: fallbackProfile.name || fallbackProfile.email,
                role: fallbackProfile.role,
                organization_id: fallbackProfile.organization_id,
                active: fallbackProfile.active ?? true,
              });
              setActiveOrgId(fallbackProfile.organization_id);
              try {
                localStorage.setItem("kagaz_active_org", fallbackProfile.organization_id);
                sessionStorage.setItem("kagaz_active_org", fallbackProfile.organization_id);
              } catch {}
            }
          }
          return false;
        }

        const profileData = await profileRes.json();
        const profileUser: AuthUser = {
          user_id: profileData.user_id,
          email: profileData.email || "",
          name: profileData.name || profileData.email,
          role: profileData.role,
          organization_id: profileData.organization_id,
          active: profileData.active ?? true,
        };

        let resolvedMemberships: OrganizationMembership[] = [
          { organization_id: profileUser.organization_id, role: profileUser.role },
        ];

        if (membershipsRes.ok) {
          const membershipsData = await membershipsRes.json();
          if (Array.isArray(membershipsData.memberships) && membershipsData.memberships.length > 0) {
            resolvedMemberships = membershipsData.memberships;
          }
        }

        setUser(profileUser);
        setActiveOrgId(profileUser.organization_id);
        setMemberships(resolvedMemberships);
        setToken(authToken);

        // Sync local storage
        try {
          localStorage.setItem("kagaz_token", authToken);
          sessionStorage.setItem("kagaz_token", authToken);
          localStorage.setItem("kagaz_active_org", profileUser.organization_id);
          sessionStorage.setItem("kagaz_active_org", profileUser.organization_id);
          localStorage.setItem("kagaz_user_email", profileUser.email);
          sessionStorage.setItem("kagaz_user_email", profileUser.email);
          localStorage.setItem("kagaz_user_role", profileUser.role);
          sessionStorage.setItem("kagaz_user_role", profileUser.role);
          localStorage.setItem("kagaz_user_name", profileUser.name);
          sessionStorage.setItem("kagaz_user_name", profileUser.name);
        } catch {}

        return true;
      } catch {
        // Backend temporarily unreachable; do not clear session if token is still valid
        return false;
      }
    },
    [logout]
  );

  // Restore session from localStorage on initial mount
  useEffect(() => {
    let ignore = false;

    async function initAuth() {
      try {
        const storedToken =
          localStorage.getItem("kagaz_token") || sessionStorage.getItem("kagaz_token");
        const storedOrg =
          localStorage.getItem("kagaz_active_org") || sessionStorage.getItem("kagaz_active_org");

        if (!storedToken || storedToken === "undefined" || storedToken === "null") {
          setIsLoading(false);
          return;
        }

        if (isTokenExpired(storedToken)) {
          clearStoredSession();
          if (!ignore) {
            setSessionExpired(true);
            setIsLoading(false);
          }
          return;
        }

        if (!ignore) {
          setToken(storedToken);
          if (storedOrg) setActiveOrgId(storedOrg);
        }

        await refreshIdentity(storedToken, storedOrg);
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }

    initAuth();

    return () => {
      ignore = true;
    };
  }, [refreshIdentity]);

  const login = async (
    email: string,
    password: string,
    organizationId?: string
  ): Promise<{ success: boolean; error?: string }> => {
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail || !password) {
      return { success: false, error: "Email and password are required." };
    }

    try {
      const payload: { email: string; password: string; organization_id?: string } = {
        email: cleanEmail,
        password,
      };
      if (organizationId && organizationId.trim()) {
        payload.organization_id = organizationId.trim();
      }

      const res = await fetch(`${API_URL}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        const message =
          data?.error?.message ||
          data?.detail?.message ||
          (typeof data?.detail === "string" ? data.detail : null) ||
          "Authentication failed. Please check your credentials.";
        return { success: false, error: message };
      }

      const accessToken = data.access_token;
      if (!accessToken) {
        return { success: false, error: "No access token received from server." };
      }

      setToken(accessToken);
      setSessionExpired(false);

      // Verify and load full memberships
      await refreshIdentity(accessToken, organizationId || data.user?.organization_id);

      return { success: true };
    } catch {
      return {
        success: false,
        error: "Unable to connect to the authentication server.",
      };
    }
  };

  const switchOrganization = async (
    organizationId: string
  ): Promise<{ success: boolean; error?: string }> => {
    if (!token) {
      return { success: false, error: "Authentication required to switch organizations." };
    }

    // Verify membership client-side first
    const hasMembership = memberships.some((m) => m.organization_id === organizationId);
    if (memberships.length > 0 && !hasMembership) {
      return {
        success: false,
        error: `You are not a member of organization '${organizationId}'.`,
      };
    }

    try {
      const res = await fetch(`${API_URL}/api/auth/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Organization-Id": organizationId,
        },
      });

      if (res.status === 401) {
        logout({ reason: "expired" });
        return { success: false, error: "Session expired. Please sign in again." };
      }

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        const msg =
          data?.detail?.message ||
          data?.error?.message ||
          "Unable to switch active organization.";
        return { success: false, error: msg };
      }

      const updatedProfile = await res.json();
      const updatedUser: AuthUser = {
        user_id: updatedProfile.user_id,
        email: updatedProfile.email || "",
        name: updatedProfile.name || updatedProfile.email,
        role: updatedProfile.role,
        organization_id: updatedProfile.organization_id,
        active: updatedProfile.active ?? true,
      };

      setUser(updatedUser);
      setActiveOrgId(updatedUser.organization_id);

      try {
        localStorage.setItem("kagaz_active_org", updatedUser.organization_id);
        sessionStorage.setItem("kagaz_active_org", updatedUser.organization_id);
        localStorage.setItem("kagaz_user_role", updatedUser.role);
        sessionStorage.setItem("kagaz_user_role", updatedUser.role);
      } catch {}

      return { success: true };
    } catch {
      return { success: false, error: "Network error while switching organization." };
    }
  };

  const fetchWithAuth = useCallback(
    async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const currentToken =
        token ||
        (typeof window !== "undefined"
          ? localStorage.getItem("kagaz_token") || sessionStorage.getItem("kagaz_token")
          : null);

      if (currentToken && isTokenExpired(currentToken)) {
        logout({ reason: "expired" });
        throw new Error("SESSION_EXPIRED");
      }

      const headers = new Headers(init?.headers || {});
      if (currentToken && !headers.has("Authorization")) {
        headers.set("Authorization", `Bearer ${currentToken}`);
      }

      const org =
        activeOrgId ||
        (typeof window !== "undefined"
          ? localStorage.getItem("kagaz_active_org") || sessionStorage.getItem("kagaz_active_org")
          : null);

      if (org && !headers.has("X-Organization-Id")) {
        headers.set("X-Organization-Id", org);
      }

      const response = await fetch(input, {
        ...init,
        headers,
      });

      if (response.status === 401) {
        logout({ reason: "expired" });
      }

      return response;
    },
    [token, activeOrgId, logout]
  );

  const value: AuthContextType = {
    user,
    token,
    activeOrgId,
    memberships,
    isAuthenticated: !!token && !!user && !sessionExpired,
    isLoading,
    sessionExpired,
    login,
    logout,
    switchOrganization,
    fetchWithAuth,
    clearSessionExpiredNotice,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
