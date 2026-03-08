import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList, CommandSeparator,
} from "@/components/ui/command";
import {
  LayoutDashboard, Users, CreditCard, BookOpen, ShieldAlert, FileSearch,
  Webhook, ArrowUpDown, Settings, Cpu, Building2, Plus, Search, ArrowRight,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const navigationItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/", permission: null },
  { icon: Users, label: "KYC / KYB", path: "/kyc", permission: "canViewKYC" as const },
  { icon: Building2, label: "Collections", path: "/collections", permission: "canViewCollections" as const },
  { icon: CreditCard, label: "Payouts", path: "/payouts", permission: "canViewPayouts" as const },
  { icon: BookOpen, label: "Ledger", path: "/ledger", permission: "canViewLedger" as const },
  { icon: ShieldAlert, label: "Risk & AML", path: "/risk", permission: "canViewRisk" as const },
  { icon: FileSearch, label: "Reconciliation", path: "/reconciliation", permission: "canViewRecon" as const },
  { icon: Cpu, label: "AI Copilot", path: "/ai-copilot", permission: "canViewAICopilot" as const },
  { icon: Webhook, label: "Webhooks", path: "/webhooks", permission: "canViewWebhooks" as const },
  { icon: ArrowUpDown, label: "Events", path: "/events", permission: "canViewEvents" as const },
  { icon: Settings, label: "Settings", path: "/settings", permission: "canViewSettings" as const },
];

const quickActions = [
  { icon: Plus, label: "Create payout", action: "/payouts", permission: "canCreatePayouts" as const },
  { icon: Plus, label: "New KYC case", action: "/kyc", permission: "canApproveKYC" as const },
  { icon: Search, label: "Search payouts", action: "/payouts", permission: "canViewPayouts" as const },
  { icon: ArrowRight, label: "Run reconciliation", action: "/reconciliation", permission: "canViewRecon" as const },
];

const recentSearches = [
  { type: "Payout", label: "PO-2026-00847 — Acme Corp", path: "/payouts/PO-2026-00847" },
  { type: "KYC", label: "KYC-4821 — Meridian Finserv", path: "/kyc/KYC-4821" },
  { type: "Risk", label: "RSK-1203 — OFAC match", path: "/risk" },
  { type: "Recon", label: "BRK-221 — Amount mismatch", path: "/reconciliation/BRK-221" },
];

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { hasPermission, isAuthenticated } = useAuth();

  useEffect(() => {
    if (!isAuthenticated) return;
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen(o => !o);
      }
      // G + key shortcuts
      if (e.key === "p" && !e.metaKey && !e.ctrlKey && document.activeElement === document.body) {
        navigate("/payouts");
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, [isAuthenticated, navigate]);

  const runCommand = useCallback((command: () => void) => {
    setOpen(false);
    command();
  }, []);

  if (!isAuthenticated) return null;

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Search pages, payouts, cases, actions…" />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        <CommandGroup heading="Quick actions">
          {quickActions
            .filter(a => hasPermission(a.permission))
            .map(a => (
              <CommandItem key={a.label} onSelect={() => runCommand(() => navigate(a.action))}>
                <a.icon className="mr-2 h-4 w-4 text-muted-foreground" />
                <span>{a.label}</span>
              </CommandItem>
            ))}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Navigate">
          {navigationItems
            .filter(n => !n.permission || hasPermission(n.permission))
            .map(n => (
              <CommandItem key={n.path} onSelect={() => runCommand(() => navigate(n.path))}>
                <n.icon className="mr-2 h-4 w-4 text-muted-foreground" />
                <span>{n.label}</span>
              </CommandItem>
            ))}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Recent searches">
          {recentSearches.map(s => (
            <CommandItem key={s.path} onSelect={() => runCommand(() => navigate(s.path))}>
              <Search className="mr-2 h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground text-[11px] font-mono mr-2">{s.type}</span>
              <span>{s.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
