"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "../lib/supabase";
import { apiError } from "../lib/api";


export interface AuthUser {
  user_id: string;
  email: string;
  name: string;
  role: string;
  organization_id: string;
  active: boolean;
}
export interface OrganizationMembership { organization_id: string; organization_name?: string; role: string }
export interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  activeOrgId: string | null;
  memberships: OrganizationMembership[];
  isAuthenticated: boolean;
  isLoading: boolean;
  /** True once the user has picked an organization in this browser session. */
  orgConfirmed: boolean;
  sessionExpired: boolean;
  /** needsWorkspace: signed in, but this email belongs to no organization yet. */
  login: (email: string, password: string, organizationId?: string) => Promise<{ success: boolean; error?: string; needsWorkspace?: boolean }>;
  register: (name: string, email: string, password: string) => Promise<{ success: boolean; error?: string; confirmationRequired?: boolean; needsWorkspace?: boolean }>;
  /** Self-service sign-up: create my own organization and become its admin. */
  createOrganization: (name: string) => Promise<{ success: boolean; error?: string }>;
  logout: (options?: { reason?: string }) => void;
  switchOrganization: (organizationId: string) => Promise<{ success: boolean; error?: string }>;
  selectOrganization: (organizationId: string) => Promise<{ success: boolean; error?: string }>;
  fetchWithAuth: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
  clearSessionExpiredNotice: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const ORG_CONFIRMED_KEY = "kagaz_org_confirmed";

export function clearStoredSession() {
  for (const key of ["kagaz_token", "kagaz_active_org", "kagaz_user_email", "kagaz_user_role", "kagaz_user_name", ORG_CONFIRMED_KEY]) {
    try { localStorage.removeItem(key); sessionStorage.removeItem(key); } catch { /* restricted storage */ }
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [activeOrgId, setActiveOrgId] = useState<string | null>(null);
  const [memberships, setMemberships] = useState<OrganizationMembership[]>([]);
  const [isLoading, setIsLoading] = useState(() => Boolean(supabase));
  const [sessionExpired, setSessionExpired] = useState(false);
  const [orgConfirmed, setOrgConfirmed] = useState(() => {
    try { return typeof window !== "undefined" && sessionStorage.getItem(ORG_CONFIRMED_KEY) === "1"; } catch { return false; }
  });

  const loadIdentity = useCallback(async (
    session: Session | null,
    targetOrg?: string | null,
  ): Promise<{ success: boolean; error?: string; code?: string }> => {
    if (!session || !supabase) {
      setToken(null); setUser(null); setActiveOrgId(null); setMemberships([]);
      return { success: false, error: "No active Supabase session was returned." };
    }
    setToken(session.access_token); setUser(null); setActiveOrgId(null); setMemberships([]);
    const headers: Record<string, string> = { Authorization: `Bearer ${session.access_token}` };
    if (targetOrg) headers["X-Organization-Id"] = targetOrg;
    try {
      const [profileRes, membershipsRes] = await Promise.all([
        fetch(`/api/auth/me`, { headers }),
        fetch(`/api/auth/memberships`, { headers }),
      ]);
      if (profileRes.status === 401) {
        setSessionExpired(true); setUser(null); setToken(null);
        return { success: false, error: "Kagaz rejected the Supabase access token. Check the backend Supabase URL and key, then restart the backend." };
      }
      if (!profileRes.ok) {
        const data = await profileRes.json().catch(() => null);
        return {
          success: false,
          code: data?.error?.code ?? data?.detail?.code,
          error: apiError(data, `Kagaz API returned HTTP ${profileRes.status}.`),
        };
      }
      const profile = await profileRes.json();
      const nextUser: AuthUser = {
        user_id: profile.user_id, email: profile.email || session.user.email || "",
        name: profile.name || profile.email || "Kagaz User", role: profile.role,
        organization_id: profile.organization_id, active: profile.active ?? true,
      };
      const membershipData = membershipsRes.ok ? await membershipsRes.json() : null;
      setToken(session.access_token); setUser(nextUser); setActiveOrgId(nextUser.organization_id);
      setMemberships(membershipData?.memberships?.length ? membershipData.memberships : [{ organization_id: nextUser.organization_id, role: nextUser.role }]);
      setSessionExpired(false);
      return { success: true };
    } catch (error) {
      setToken(session.access_token);
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
    try { sessionStorage.removeItem(ORG_CONFIRMED_KEY); } catch { /* restricted storage */ }
    setOrgConfirmed(false);
    const identity = await loadIdentity(data.session, organizationId);
    if (identity.code === "MEMBERSHIP_REQUIRED") return { success: false, needsWorkspace: true };
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
    // No session means email confirmation is switched on: the user confirms, then signs in.
    if (!data.session) return { success: true, confirmationRequired: true };
    // Signed in already: the next step is naming their organization.
    const identity = await loadIdentity(data.session);
    return { success: true, needsWorkspace: identity.code === "MEMBERSHIP_REQUIRED" };
  }, [loadIdentity]);

  const createOrganization = useCallback(async (name: string) => {
    if (!supabase) return { success: false, error: "Supabase is not configured." };
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return { success: false, error: "Your session ended. Sign in again." };
    const response = await fetch("/api/auth/organizations", {
      method: "POST",
      headers: { Authorization: `Bearer ${session.access_token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const body = await response.json().catch(() => null);
    if (!response.ok) return { success: false, error: apiError(body, `Could not create the organization (HTTP ${response.status}).`) };
    try { sessionStorage.removeItem(ORG_CONFIRMED_KEY); } catch { /* restricted storage */ }
    setOrgConfirmed(false);
    const identity = await loadIdentity(session, body.organization_id);
    return identity.success ? { success: true } : { success: false, error: identity.error };
  }, [loadIdentity]);

  const logout = useCallback((options?: { reason?: string }) => {
    if (supabase) void supabase.auth.signOut();
    clearStoredSession(); setOrgConfirmed(false); setToken(null); setUser(null); setActiveOrgId(null); setMemberships([]);
    if (options?.reason === "expired") setSessionExpired(true);
  }, []);

  const switchOrganization = useCallback(async (organizationId: string) => {
    if (!token || !memberships.some((membership) => membership.organization_id === organizationId)) return { success: false, error: "You are not a member of that organization." };
    const response = await fetch(`/api/auth/me`, { headers: { Authorization: `Bearer ${token}`, "X-Organization-Id": organizationId } });
    if (!response.ok) return { success: false, error: "Unable to switch organization. Confirm your membership with an administrator." };
    const profile = await response.json();
    setUser({ user_id: profile.user_id, email: profile.email || "", name: profile.name || profile.email || "Kagaz User", role: profile.role, organization_id: profile.organization_id, active: profile.active ?? true });
    setActiveOrgId(profile.organization_id);
    try { localStorage.setItem("kagaz_active_org", profile.organization_id); } catch { /* restricted storage */ }
    return { success: true };
  }, [token, memberships]);

  // Used by the organization picker: switch, then remember the choice for this browser session.
  const selectOrganization = useCallback(async (organizationId: string) => {
    const result = await switchOrganization(organizationId);
    if (result.success) {
      try { sessionStorage.setItem(ORG_CONFIRMED_KEY, "1"); } catch { /* restricted storage */ }
      setOrgConfirmed(true);
    }
    return result;
  }, [switchOrganization]);

  const fetchWithAuth = useCallback(async (input: RequestInfo | URL, init?: RequestInit) => {
    const headers = new Headers(init?.headers || {});
    if (token) headers.set("Authorization", `Bearer ${token}`);
    if (activeOrgId) headers.set("X-Organization-Id", activeOrgId);
    const response = await fetch(input, { ...init, headers });
    if (response.status === 401) logout({ reason: "expired" });
    return response;
  }, [token, activeOrgId, logout]);

  const value: AuthContextType = {
    user, token, activeOrgId, memberships, isAuthenticated: !!token && !!user,
    isLoading, orgConfirmed, sessionExpired, login, register, createOrganization, logout, switchOrganization, selectOrganization, fetchWithAuth,
    clearSessionExpiredNotice: () => setSessionExpired(false),
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
}
