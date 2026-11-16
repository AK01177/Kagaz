"use client";

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "../lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

export interface AuthUser {
  user_id: string;
  email: string;
  name: string;
  role: string;
  organization_id: string;
  active: boolean;
}
export interface OrganizationMembership { organization_id: string; role: string }
export interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  activeOrgId: string | null;
  memberships: OrganizationMembership[];
  isAuthenticated: boolean;
  isLoading: boolean;
  sessionExpired: boolean;
  login: (email: string, password: string, organizationId?: string) => Promise<{ success: boolean; error?: string }>;
  register: (name: string, email: string, password: string) => Promise<{ success: boolean; error?: string; confirmationRequired?: boolean }>;
  logout: (options?: { reason?: string }) => void;
  switchOrganization: (organizationId: string) => Promise<{ success: boolean; error?: string }>;
  fetchWithAuth: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
  clearSessionExpiredNotice: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function clearStoredSession() {
  for (const key of ["kagaz_token", "kagaz_active_org", "kagaz_user_email", "kagaz_user_role", "kagaz_user_name"]) {
    try { localStorage.removeItem(key); sessionStorage.removeItem(key); } catch { /* restricted storage */ }
  }
  try {
    for (const storage of [localStorage, sessionStorage]) {
      for (const key of Object.keys(storage)) {
        if (key.startsWith("kagaz_doc_")) storage.removeItem(key);
      }
    }
  } catch { /* storage may be unavailable */ }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [activeOrgId, setActiveOrgId] = useState<string | null>(null);
  const [memberships, setMemberships] = useState<OrganizationMembership[]>([]);
  const [isLoading, setIsLoading] = useState(() => Boolean(supabase));
  const [sessionExpired, setSessionExpired] = useState(false);
  const identityRequestId = useRef(0);

  const loadIdentity = useCallback(async (
    session: Session | null,
    targetOrg?: string | null,
  ): Promise<{ success: boolean; error?: string }> => {
    const requestId = ++identityRequestId.current;
    if (!session || !supabase) {
      setToken(null); setUser(null); setActiveOrgId(null); setMemberships([]);
      return { success: false, error: "No active Supabase session was returned." };
    }
    // Keep the current identity visible while Supabase rotates its access token.
    // Clearing user here briefly made ProtectedRoute redirect during refresh.
    setToken(session.access_token);
    const headers: Record<string, string> = { Authorization: `Bearer ${session.access_token}` };
    if (targetOrg) headers["X-Organization-Id"] = targetOrg;
    try {
      const [profileRes, membershipsRes] = await Promise.all([
        fetch(`${API_URL}/api/auth/me`, { headers }),
        fetch(`${API_URL}/api/auth/memberships`, { headers }),
      ]);
      if (profileRes.status === 401) {
        if (requestId === identityRequestId.current) {
          setSessionExpired(true); setUser(null); setToken(null);
        }
        return { success: false, error: "Kagaz rejected the Supabase access token. Check the backend Supabase URL and key, then restart the backend." };
      }
      if (!profileRes.ok) {
        const data = await profileRes.json().catch(() => null);
        return {
          success: false,
          error: data?.detail?.message || data?.error?.message || `Kagaz API returned HTTP ${profileRes.status}.`,
        };
      }
      const profile = await profileRes.json();
      const nextUser: AuthUser = {
        user_id: profile.user_id, email: profile.email || session.user.email || "",
        name: profile.name || profile.email || "Kagaz User", role: profile.role,
        organization_id: profile.organization_id, active: profile.active ?? true,
      };
      const membershipData = membershipsRes.ok ? await membershipsRes.json() : null;
      if (requestId !== identityRequestId.current) return { success: false, error: "A newer authentication session replaced this request." };
      setToken(session.access_token); setUser(nextUser); setActiveOrgId(nextUser.organization_id);
      setMemberships(membershipData?.memberships?.length ? membershipData.memberships : [{ organization_id: nextUser.organization_id, role: nextUser.role }]);
      setSessionExpired(false);
      return { success: true };
    } catch (error) {
      if (requestId === identityRequestId.current) setToken(session.access_token);
      return { success: false, error: error instanceof Error ? error.message : "Could not connect to the Kagaz backend." };
    }
  }, []);

  useEffect(() => {
    if (!supabase) return;
    let active = true;
    supabase.auth.getSession().then(({ data }) => {
      if (active) void loadIdentity(data.session, localStorage.getItem("kagaz_active_org"));
    }).finally(() => { if (active) setIsLoading(false); });
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (active) void loadIdentity(session, localStorage.getItem("kagaz_active_org"));
    });
    return () => { active = false; subscription.unsubscribe(); };
  }, [loadIdentity]);

  const login = useCallback(async (email: string, password: string, organizationId?: string) => {
    if (!supabase) return { success: false, error: "Supabase is not configured. Set the frontend Supabase URL and anon key." };
    const { data, error } = await supabase.auth.signInWithPassword({ email: email.trim().toLowerCase(), password });
    if (error) return { success: false, error: error.message };
    const identity = await loadIdentity(data.session, organizationId);
    if (!identity.success) return { success: false, error: `Supabase sign-in succeeded, but Kagaz could not load your workspace: ${identity.error}` };
    return { success: true };
  }, [loadIdentity]);

  const register = useCallback(async (name: string, email: string, password: string) => {
    if (!supabase) return { success: false, error: "Supabase is not configured. Set the frontend Supabase URL and anon key." };
    const { data, error } = await supabase.auth.signUp({
      email: email.trim().toLowerCase(), password,
      options: { data: { full_name: name.trim() }, emailRedirectTo: `${window.location.origin}/login` },
    });
    if (error) return { success: false, error: error.message };
    if (data.session) await supabase.auth.signOut();
    return { success: true, confirmationRequired: true };
  }, []);

  const logout = useCallback((options?: { reason?: string }) => {
    if (supabase) void supabase.auth.signOut();
    clearStoredSession(); setToken(null); setUser(null); setActiveOrgId(null); setMemberships([]);
    if (options?.reason === "expired") setSessionExpired(true);
  }, []);

  const switchOrganization = useCallback(async (organizationId: string) => {
    if (!token || !memberships.some((membership) => membership.organization_id === organizationId)) return { success: false, error: "You are not a member of that organization." };
    const response = await fetch(`${API_URL}/api/auth/me`, { headers: { Authorization: `Bearer ${token}`, "X-Organization-Id": organizationId } });
    if (!response.ok) return { success: false, error: "Unable to switch organization. Confirm your membership with an administrator." };
    const profile = await response.json();
    setUser({ user_id: profile.user_id, email: profile.email || "", name: profile.name || profile.email || "Kagaz User", role: profile.role, organization_id: profile.organization_id, active: profile.active ?? true });
    setActiveOrgId(profile.organization_id);
    try { localStorage.setItem("kagaz_active_org", profile.organization_id); } catch { /* restricted storage */ }
    return { success: true };
  }, [token, memberships]);

  const fetchWithAuth = useCallback(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = (accessToken: string | null) => {
      const headers = new Headers(init?.headers || {});
      if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
      if (activeOrgId) headers.set("X-Organization-Id", activeOrgId);
      return fetch(input, { ...init, headers });
    };

    // Ask Supabase for the current session first; getSession refreshes an
    // expired access token when a valid refresh token is still available.
    const { data } = supabase ? await supabase.auth.getSession() : { data: { session: null } };
    let response = await request(data.session?.access_token || token);
    if (response.status !== 401 || !supabase) return response;

    // A request can race token refresh or use an access token that expired
    // between getSession() and the API call. Refresh once and retry before
    // declaring the user's session expired.
    const refreshed = await supabase.auth.refreshSession();
    if (refreshed.error || !refreshed.data.session) {
      logout({ reason: "expired" });
      return response;
    }

    response = await request(refreshed.data.session.access_token);
    if (response.status === 401) logout({ reason: "expired" });
    return response;
  }, [token, activeOrgId, logout]);

  const value: AuthContextType = {
    user, token, activeOrgId, memberships, isAuthenticated: !!token && !!user,
    isLoading, sessionExpired, login, register, logout, switchOrganization, fetchWithAuth,
    clearSessionExpiredNotice: () => setSessionExpired(false),
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
}
