import { createContext, useContext, useState, useCallback, useEffect, ReactNode } from "react";

export type AppRole = "admin" | "ops_analyst" | "finance_operator" | "compliance_reviewer" | "developer" | "readonly_auditor";

export interface UserSession {
  id: string;
  device: string;
  ip: string;
  location: string;
  lastActive: string;
  current: boolean;
}

export interface OrgProfile {
  companyName: string;
  industry: string;
  userRole: string;
}

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  initials: string;
  role: AppRole;
  tenant: string;
  tenantName: string;
  environment: "production" | "sandbox";
  mfaEnabled: boolean;
  lastLogin: string;
  sessions: UserSession[];
  orgProfile?: OrgProfile;
  onboardingComplete: boolean;
}

interface Permission {
  canViewPayouts: boolean;
  canCreatePayouts: boolean;
  canRetryPayouts: boolean;
  canViewKYC: boolean;
  canApproveKYC: boolean;
  canViewLedger: boolean;
  canViewRisk: boolean;
  canManageRisk: boolean;
  canViewRecon: boolean;
  canResolveRecon: boolean;
  canViewWebhooks: boolean;
  canManageWebhooks: boolean;
  canViewEvents: boolean;
  canViewSettings: boolean;
  canManageSettings: boolean;
  canManageAPIKeys: boolean;
  canExportData: boolean;
  canViewAICopilot: boolean;
  canViewCollections: boolean;
  canManageTeam: boolean;
  canViewCases: boolean;
  canViewApprovals: boolean;
}

const rolePermissions: Record<AppRole, Permission> = {
  admin: {
    canViewPayouts: true, canCreatePayouts: true, canRetryPayouts: true,
    canViewKYC: true, canApproveKYC: true, canViewLedger: true,
    canViewRisk: true, canManageRisk: true, canViewRecon: true, canResolveRecon: true,
    canViewWebhooks: true, canManageWebhooks: true, canViewEvents: true,
    canViewSettings: true, canManageSettings: true, canManageAPIKeys: true,
    canExportData: true, canViewAICopilot: true, canViewCollections: true, canManageTeam: true,
    canViewCases: true, canViewApprovals: true,
  },
  ops_analyst: {
    canViewPayouts: true, canCreatePayouts: true, canRetryPayouts: true,
    canViewKYC: true, canApproveKYC: false, canViewLedger: true,
    canViewRisk: true, canManageRisk: false, canViewRecon: true, canResolveRecon: true,
    canViewWebhooks: true, canManageWebhooks: false, canViewEvents: true,
    canViewSettings: false, canManageSettings: false, canManageAPIKeys: false,
    canExportData: true, canViewAICopilot: true, canViewCollections: true, canManageTeam: false,
    canViewCases: true, canViewApprovals: false,
  },
  finance_operator: {
    canViewPayouts: true, canCreatePayouts: true, canRetryPayouts: true,
    canViewKYC: false, canApproveKYC: false, canViewLedger: true,
    canViewRisk: false, canManageRisk: false, canViewRecon: true, canResolveRecon: true,
    canViewWebhooks: false, canManageWebhooks: false, canViewEvents: false,
    canViewSettings: false, canManageSettings: false, canManageAPIKeys: false,
    canExportData: true, canViewAICopilot: false, canViewCollections: true, canManageTeam: false,
    canViewCases: false, canViewApprovals: false,
  },
  compliance_reviewer: {
    canViewPayouts: true, canCreatePayouts: false, canRetryPayouts: false,
    canViewKYC: true, canApproveKYC: true, canViewLedger: true,
    canViewRisk: true, canManageRisk: true, canViewRecon: true, canResolveRecon: false,
    canViewWebhooks: false, canManageWebhooks: false, canViewEvents: true,
    canViewSettings: false, canManageSettings: false, canManageAPIKeys: false,
    canExportData: true, canViewAICopilot: true, canViewCollections: false, canManageTeam: false,
    canViewCases: true, canViewApprovals: true,
  },
  developer: {
    canViewPayouts: true, canCreatePayouts: false, canRetryPayouts: false,
    canViewKYC: false, canApproveKYC: false, canViewLedger: false,
    canViewRisk: false, canManageRisk: false, canViewRecon: false, canResolveRecon: false,
    canViewWebhooks: true, canManageWebhooks: true, canViewEvents: true,
    canViewSettings: true, canManageSettings: false, canManageAPIKeys: true,
    canExportData: false, canViewAICopilot: true, canViewCollections: false, canManageTeam: false,
    canViewCases: false, canViewApprovals: false,
  },
  readonly_auditor: {
    canViewPayouts: true, canCreatePayouts: false, canRetryPayouts: false,
    canViewKYC: true, canApproveKYC: false, canViewLedger: true,
    canViewRisk: true, canManageRisk: false, canViewRecon: true, canResolveRecon: false,
    canViewWebhooks: true, canManageWebhooks: false, canViewEvents: true,
    canViewSettings: true, canManageSettings: false, canManageAPIKeys: false,
    canExportData: false, canViewAICopilot: false, canViewCollections: true, canManageTeam: false,
    canViewCases: true, canViewApprovals: false,
  },
};

const ROLE_LABELS: Record<AppRole, string> = {
  admin: "Administrator",
  ops_analyst: "Operations Analyst",
  finance_operator: "Finance Operator",
  compliance_reviewer: "Compliance Reviewer",
  developer: "Developer",
  readonly_auditor: "Read-only Auditor",
};

const mockUser: AuthUser = {
  id: "usr_01HZQW8K3N",
  email: "arjun.kapoor@finstack.io",
  name: "Arjun Kapoor",
  initials: "AK",
  role: "admin",
  tenant: "tnt_acme",
  tenantName: "Acme Financial Services",
  environment: "production",
  mfaEnabled: true,
  lastLogin: "2026-03-07T08:12:00Z",
  onboardingComplete: false,
  sessions: [
    { id: "ses_01", device: "Chrome · macOS", ip: "103.21.58.xx", location: "Mumbai, IN", lastActive: "2m ago", current: true },
    { id: "ses_02", device: "Safari · iPhone", ip: "103.21.58.xx", location: "Mumbai, IN", lastActive: "1h ago", current: false },
    { id: "ses_03", device: "Firefox · Windows", ip: "49.36.12.xx", location: "Bangalore, IN", lastActive: "3d ago", current: false },
  ],
};

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  permissions: Permission;
  roleLabel: string;
  login: (email: string, password: string) => Promise<{ requiresMFA: boolean }>;
  verifyMFA: (code: string) => Promise<boolean>;
  logout: () => void;
  forgotPassword: (email: string) => Promise<void>;
  resetPassword: (token: string, password: string) => Promise<void>;
  switchRole: (role: AppRole) => void;
  switchEnvironment: (env: "production" | "sandbox") => void;
  revokeSession: (sessionId: string) => void;
  sessionTimeoutVisible: boolean;
  dismissSessionTimeout: () => void;
  stepUpAuth: () => Promise<boolean>;
  hasPermission: (key: keyof Permission) => boolean;
  completeOnboarding: (profile: OrgProfile) => void;
  updateOrgProfile: (profile: Partial<OrgProfile>) => void;
}

const emptyPermissions: Permission = {
  canViewPayouts: false, canCreatePayouts: false, canRetryPayouts: false,
  canViewKYC: false, canApproveKYC: false, canViewLedger: false,
  canViewRisk: false, canManageRisk: false, canViewRecon: false, canResolveRecon: false,
  canViewWebhooks: false, canManageWebhooks: false, canViewEvents: false,
  canViewSettings: false, canManageSettings: false, canManageAPIKeys: false,
  canExportData: false, canViewAICopilot: false, canViewCollections: false, canManageTeam: false,
  canViewCases: false, canViewApprovals: false,
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [pendingMFA, setPendingMFA] = useState(false);
  const [sessionTimeoutVisible, setSessionTimeoutVisible] = useState(false);
  const [pendingTokens, setPendingTokens] = useState<{ access: string; refresh: string } | null>(null);

  const permissions = user ? rolePermissions[user.role] : emptyPermissions;
  const roleLabel = user ? ROLE_LABELS[user.role] : "";

  const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

  // Helper: decode JWT payload (no verification — server is authoritative)
  function decodeJWT(token: string): Record<string, unknown> {
    const payload = token.split(".")[1];
    return JSON.parse(atob(payload));
  }

  // Helper: build AuthUser from JWT payload
  function buildUserFromToken(payload: Record<string, unknown>): AuthUser {
    const email = (payload.email as string) || "";
    const nameParts = email.split("@")[0].split(".");
    const name = nameParts.map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
    const initials = nameParts.map(p => p[0]?.toUpperCase() || "").join("").slice(0, 2);
    const role = (payload.role as AppRole) || "admin";
    const savedProfile = localStorage.getItem("finstack_org_profile");
    const orgProfile = savedProfile ? JSON.parse(savedProfile) as OrgProfile : undefined;

    return {
      id: payload.sub as string || "unknown",
      email,
      name,
      initials,
      role,
      tenant: (payload.tenant_id as string) || "default",
      tenantName: orgProfile?.companyName || "My Organization",
      environment: "production",
      mfaEnabled: true,
      lastLogin: new Date().toISOString(),
      onboardingComplete: !!orgProfile,
      orgProfile,
      sessions: [
        { id: "ses_current", device: "Browser", ip: "", location: "", lastActive: "now", current: true },
      ],
    };
  }

  // Restore session from stored token on mount
  useEffect(() => {
    const storedToken = localStorage.getItem("auth_token");
    if (storedToken) {
      try {
        const payload = decodeJWT(storedToken);
        const exp = (payload.exp as number) || 0;
        if (exp * 1000 > Date.now()) {
          setUser(buildUserFromToken(payload));
        } else {
          localStorage.removeItem("auth_token");
          localStorage.removeItem("refresh_token");
        }
      } catch {
        localStorage.removeItem("auth_token");
      }
    }
  }, []);

  // Session timeout warning — 25 min
  useEffect(() => {
    if (!user) return;
    const timer = setTimeout(() => setSessionTimeoutVisible(true), 25 * 60 * 1000);
    return () => clearTimeout(timer);
  }, [user]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/v1/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Login failed" }));
      throw new Error(err.detail || "Invalid credentials");
    }

    const json = await res.json();
    const data = json.data || json;

    // Store tokens
    setPendingTokens({ access: data.access_token, refresh: data.refresh_token });
    setPendingMFA(true);
    return { requiresMFA: true };
  }, [API_BASE]);

  const verifyMFA = useCallback(async (code: string) => {
    if (code.length >= 6 && pendingTokens) {
      // Accept any 6-digit code (backend has no MFA endpoint yet)
      localStorage.setItem("auth_token", pendingTokens.access);
      localStorage.setItem("refresh_token", pendingTokens.refresh);
      localStorage.setItem("tenant_id", "default");

      const payload = decodeJWT(pendingTokens.access);
      if (payload.tenant_id) {
        localStorage.setItem("tenant_id", payload.tenant_id as string);
      }

      const authUser = buildUserFromToken(payload);
      setPendingMFA(false);
      setPendingTokens(null);
      setUser(authUser);
      return true;
    }
    return false;
  }, [pendingTokens]);

  const logout = useCallback(() => {
    setUser(null);
    setPendingMFA(false);
    setPendingTokens(null);
    setSessionTimeoutVisible(false);
    localStorage.removeItem("auth_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("tenant_id");
  }, []);

  const forgotPassword = useCallback(async (_email: string) => {
    await new Promise(r => setTimeout(r, 800));
  }, []);

  const resetPassword = useCallback(async (_token: string, _password: string) => {
    await new Promise(r => setTimeout(r, 800));
  }, []);

  const switchRole = useCallback((role: AppRole) => {
    if (user) setUser({ ...user, role });
  }, [user]);

  const switchEnvironment = useCallback((env: "production" | "sandbox") => {
    if (user) setUser({ ...user, environment: env });
  }, [user]);

  const revokeSession = useCallback((sessionId: string) => {
    if (user) {
      setUser({
        ...user,
        sessions: user.sessions.filter(s => s.id !== sessionId),
      });
    }
  }, [user]);

  const dismissSessionTimeout = useCallback(() => {
    setSessionTimeoutVisible(false);
  }, []);

  const stepUpAuth = useCallback(async () => {
    // In production, this would open MFA/password re-entry
    await new Promise(r => setTimeout(r, 500));
    return true;
  }, []);

  const hasPermission = useCallback((key: keyof Permission) => {
    return permissions[key];
  }, [permissions]);

  const completeOnboarding = useCallback((profile: OrgProfile) => {
    if (user) {
      localStorage.setItem("finstack_org_profile", JSON.stringify(profile));
      setUser({ ...user, orgProfile: profile, onboardingComplete: true, tenantName: profile.companyName });
    }
  }, [user]);

  const updateOrgProfile = useCallback((updates: Partial<OrgProfile>) => {
    if (user && user.orgProfile) {
      const updated = { ...user.orgProfile, ...updates };
      localStorage.setItem("finstack_org_profile", JSON.stringify(updated));
      setUser({ ...user, orgProfile: updated, tenantName: updated.companyName });
    }
  }, [user]);

  return (
    <AuthContext.Provider value={{
      user, isAuthenticated: !!user, permissions, roleLabel,
      login, verifyMFA, logout, forgotPassword, resetPassword,
      switchRole, switchEnvironment, revokeSession,
      sessionTimeoutVisible, dismissSessionTimeout,
      stepUpAuth, hasPermission, completeOnboarding, updateOrgProfile,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export { ROLE_LABELS, rolePermissions };
export type { Permission };
