import { ReactNode, useState } from "react";
import { Link } from "react-router-dom";
import AppSidebar from "./AppSidebar";
import RoleSwitcher from "./RoleSwitcher";
import EnvironmentSwitcher from "./EnvironmentSwitcher";
import NotificationCenter from "./NotificationCenter";
import LiveIndicator from "./LiveIndicator";
import PageTransition from "./PageTransition";
import { Search, Menu } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useIsMobile } from "@/hooks/use-mobile";

interface DashboardLayoutProps {
  children: ReactNode;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}

export default function DashboardLayout({ children, title, subtitle, actions }: DashboardLayoutProps) {
  const { user } = useAuth();
  const isMobile = useIsMobile();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const openCommandPalette = () => {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }));
  };

  const sidebarWidth = isMobile ? 0 : collapsed ? 56 : 240;

  return (
    <div className="min-h-screen bg-background">
      <AppSidebar
        collapsed={collapsed}
        setCollapsed={setCollapsed}
        mobileOpen={mobileOpen}
        setMobileOpen={setMobileOpen}
      />
      <main
        className="transition-all duration-200"
        style={{ marginLeft: sidebarWidth }}
      >
        <header className="sticky top-0 z-30 bg-card/80 backdrop-blur-md border-b border-border">
          <div className="flex items-center justify-between px-4 md:px-8 h-[60px]">
            <div className="flex items-center gap-3 min-w-0">
              {isMobile && (
                <button
                  onClick={() => setMobileOpen(true)}
                  className="w-9 h-9 flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors shrink-0"
                >
                  <Menu className="w-5 h-5" />
                </button>
              )}
              <div className="flex items-baseline gap-4 min-w-0">
                <h1 className="text-[16px] font-semibold text-foreground tracking-[-0.01em] truncate">{title}</h1>
                {subtitle && (
                  <span className="text-meta text-muted-foreground hidden lg:inline">{subtitle}</span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 md:gap-3 shrink-0">
              <div className="hidden lg:flex">
                <LiveIndicator />
              </div>
              <div className="hidden md:flex items-center gap-3">
                <div className="w-px h-5 bg-border" />
                <EnvironmentSwitcher />
                <RoleSwitcher />
                <div className="w-px h-5 bg-border" />
              </div>
              <button
                onClick={openCommandPalette}
                className="w-9 h-9 flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                aria-label="Search"
              >
                <Search className="w-[18px] h-[18px]" />
              </button>
              <NotificationCenter />
              {user && (
                <Link to="/profile" className="w-8 h-8 rounded-full bg-primary/10 border border-border flex items-center justify-center text-[11px] font-semibold text-primary hover:ring-2 hover:ring-primary/20 transition-all">
                  {user.initials}
                </Link>
              )}
              {actions && <div className="hidden sm:flex items-center gap-2 ml-2 pl-2 border-l border-border">{actions}</div>}
            </div>
          </div>
          {/* Mobile actions row */}
          {actions && (
            <div className="sm:hidden flex items-center gap-2 px-4 pb-3">
              {actions}
            </div>
          )}
        </header>
        <PageTransition>
          <div className="px-4 md:px-8 py-5 md:py-7">
            {children}
          </div>
        </PageTransition>
      </main>
    </div>
  );
}
