import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard, Users, CreditCard, ArrowUpDown, BookOpen,
  ShieldAlert, FileSearch, Webhook, Settings, Cpu, Building2,
  PanelLeftClose, PanelLeft, LogOut, X, UsersRound, ScrollText,
  FolderOpen, ShieldCheck, Bell,
} from "lucide-react";
import { useAuth, Permission } from "@/contexts/AuthContext";
import { useIsMobile } from "@/hooks/use-mobile";
import logoImage from "@/assets/logo.png";

interface NavItem {
  icon: typeof LayoutDashboard;
  label: string;
  path: string;
  permission?: keyof Permission;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const navGroups: NavGroup[] = [
  {
    label: "Overview",
    items: [
      { icon: LayoutDashboard, label: "Dashboard", path: "/" },
    ],
  },
  {
    label: "Core",
    items: [
      { icon: Users, label: "KYC / KYB", path: "/kyc", permission: "canViewKYC" },
      { icon: Building2, label: "Collections", path: "/collections", permission: "canViewCollections" },
      { icon: CreditCard, label: "Payouts", path: "/payouts", permission: "canViewPayouts" },
      { icon: BookOpen, label: "Ledger", path: "/ledger", permission: "canViewLedger" },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { icon: ShieldAlert, label: "Risk & AML", path: "/risk", permission: "canViewRisk" },
      { icon: FileSearch, label: "Reconciliation", path: "/reconciliation", permission: "canViewRecon" },
      { icon: Cpu, label: "AI Copilot", path: "/ai-copilot", permission: "canViewAICopilot" },
    ],
  },
  {
    label: "Operations",
    items: [
      { icon: FolderOpen, label: "Cases", path: "/cases", permission: "canViewCases" },
      { icon: ShieldCheck, label: "Approvals", path: "/approvals", permission: "canViewApprovals" },
      { icon: Bell, label: "Notifications", path: "/notifications" },
    ],
  },
  {
    label: "Platform",
    items: [
      { icon: Webhook, label: "Webhooks", path: "/webhooks", permission: "canViewWebhooks" },
      { icon: ArrowUpDown, label: "Events", path: "/events", permission: "canViewEvents" },
      { icon: UsersRound, label: "Team", path: "/team", permission: "canManageTeam" },
      { icon: ScrollText, label: "Audit log", path: "/audit-log" },
      { icon: Settings, label: "Settings", path: "/settings", permission: "canViewSettings" },
    ],
  },
];

interface AppSidebarProps {
  collapsed: boolean;
  setCollapsed: (v: boolean) => void;
  mobileOpen: boolean;
  setMobileOpen: (v: boolean) => void;
}

export default function AppSidebar({ collapsed, setCollapsed, mobileOpen, setMobileOpen }: AppSidebarProps) {
  const location = useLocation();
  const { user, hasPermission, logout, roleLabel } = useAuth();
  const isMobile = useIsMobile();

  const isOpen = isMobile ? mobileOpen : true;
  const sidebarWidth = isMobile ? 280 : collapsed ? 56 : 240;

  const handleNavClick = () => {
    if (isMobile) setMobileOpen(false);
  };

  return (
    <>
      {/* Mobile overlay backdrop */}
      {isMobile && mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-foreground/20 backdrop-blur-sm transition-opacity"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside
        className={`fixed left-0 top-0 bottom-0 z-50 flex flex-col bg-sidebar overflow-hidden border-r border-sidebar-border transition-all duration-200 ease-in-out ${isMobile ? (mobileOpen ? "translate-x-0" : "-translate-x-full") : "translate-x-0"
          }`}
        style={{ width: sidebarWidth }}
      >
        {/* Brand */}
        <div className="flex items-center justify-between h-[60px] px-4 shrink-0 border-b border-sidebar-border">
          <div className="flex items-center gap-3 min-w-0">
            <img src={logoImage} alt="Logo" className="w-12 h-12 rounded-lg shrink-0" />
            {(!collapsed || isMobile) && (
              <div className="flex flex-col min-w-0">
                <span className="text-[14px] font-semibold text-foreground tracking-[-0.01em] leading-tight">FinStack</span>
                <span className="text-[11px] text-muted-foreground leading-tight">Infrastructure</span>
              </div>
            )}
          </div>
          {isMobile && (
            <button
              onClick={() => setMobileOpen(false)}
              className="w-8 h-8 flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-sidebar-accent/60 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-3 pt-4 pb-3">
          {navGroups.map((group, gi) => {
            const visibleItems = group.items.filter(
              item => !item.permission || hasPermission(item.permission)
            );
            if (visibleItems.length === 0) return null;

            return (
              <div key={group.label} className={gi > 0 ? "mt-6" : ""}>
                {(!collapsed || isMobile) && (
                  <p className="text-[11px] uppercase tracking-[0.06em] text-muted-foreground font-medium px-3 mb-2 select-none">
                    {group.label}
                  </p>
                )}
                <div className="space-y-0.5">
                  {visibleItems.map((item) => {
                    const isActive = location.pathname === item.path;
                    return (
                      <Link
                        key={item.path}
                        to={item.path}
                        onClick={handleNavClick}
                        className={`group relative flex items-center gap-3 h-9 rounded-lg text-[13px] font-medium transition-colors duration-100 ${(collapsed && !isMobile) ? "justify-center px-0" : "px-3"
                          } ${isActive
                            ? "bg-sidebar-accent text-foreground"
                            : "text-muted-foreground hover:text-foreground hover:bg-sidebar-accent/60"
                          }`}
                      >
                        {isActive && (
                          <div className="absolute left-0 top-2 bottom-2 w-[3px] rounded-full bg-primary" />
                        )}
                        <item.icon className={`w-4 h-4 shrink-0 transition-colors ${isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground"}`} strokeWidth={1.75} />
                        {(!collapsed || isMobile) && <span className="truncate">{item.label}</span>}
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </nav>

        {/* User section */}
        {user && (!collapsed || isMobile) && (
          <div className="px-3 py-3 border-t border-sidebar-border shrink-0">
            <div className="flex items-center gap-3 px-2 mb-2">
              <div className="w-7 h-7 rounded-full bg-primary/10 border border-border flex items-center justify-center text-[10px] font-semibold text-primary shrink-0">
                {user.initials}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[12px] font-medium text-foreground truncate">{user.name}</p>
                <p className="text-[10px] text-muted-foreground truncate">{roleLabel}</p>
              </div>
              <button
                onClick={logout}
                className="w-7 h-7 flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-sidebar-accent/60 transition-colors shrink-0"
                title="Sign out"
              >
                <LogOut className="w-3.5 h-3.5" strokeWidth={1.75} />
              </button>
            </div>
          </div>
        )}

        {/* Collapse + user icon when collapsed (desktop only) */}
        {!isMobile && (
          <div className={`px-3 py-3 border-t border-sidebar-border shrink-0 ${!collapsed && user ? "border-t-0 pt-0" : ""}`}>
            {collapsed && user && (
              <button
                onClick={logout}
                className="flex items-center justify-center w-full h-8 rounded-lg text-muted-foreground hover:text-foreground hover:bg-sidebar-accent/60 transition-colors mb-1"
                title="Sign out"
              >
                <LogOut className="w-4 h-4" strokeWidth={1.5} />
              </button>
            )}
            <button
              onClick={() => setCollapsed(!collapsed)}
              className="flex items-center justify-center w-full h-8 rounded-lg text-muted-foreground hover:text-foreground hover:bg-sidebar-accent/60 transition-colors"
            >
              {collapsed ? <PanelLeft className="w-4 h-4" strokeWidth={1.5} /> : <PanelLeftClose className="w-4 h-4" strokeWidth={1.5} />}
            </button>
          </div>
        )}
      </aside>
    </>
  );
}
