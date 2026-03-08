import { useState } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Key, Shield, Globe, Database, RotateCcw, Plus, Loader2, CheckCircle2, Copy, Eye, EyeOff, Building2 } from "lucide-react";
import { toast } from "sonner";
import { authAPI } from "@/lib/api";

interface ConfigDialogProps {
  open: boolean;
  onClose: () => void;
  section: string;
}

function ConfigDialog({ open, onClose, section }: ConfigDialogProps) {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSave = async () => {
    setLoading(true);
    await new Promise(r => setTimeout(r, 1000));
    setLoading(false);
    setSuccess(true);
    toast.success("Settings updated", { description: `${section} configuration saved.` });
    setTimeout(() => { setSuccess(false); onClose(); }, 1000);
  };

  const configs: Record<string, { fields: { label: string; type: string; value: string; options?: string[] }[] }> = {
    "API Keys": {
      fields: [
        { label: "Key name", type: "text", value: "Production API Key" },
        { label: "Expiry", type: "select", value: "90", options: ["30 days", "60 days", "90 days", "Never"] },
        { label: "Rate limit", type: "text", value: "1000 req/min" },
      ],
    },
    "Security & Auth": {
      fields: [
        { label: "Session timeout (minutes)", type: "text", value: "30" },
        { label: "MFA policy", type: "select", value: "high-risk", options: ["All actions", "High-risk actions", "Login only", "Disabled"] },
        { label: "IP allowlist", type: "text", value: "103.21.58.0/24, 49.36.12.0/24" },
      ],
    },
    "Tenant Configuration": {
      fields: [
        { label: "Default payout rail", type: "select", value: "IMPS", options: ["IMPS", "NEFT", "RTGS", "UPI", "Auto"] },
        { label: "KYC auto-approve threshold", type: "text", value: "92" },
        { label: "Max payout amount", type: "text", value: "50,00,000" },
      ],
    },
    "Infrastructure": {
      fields: [
        { label: "Database pool size", type: "text", value: "20" },
        { label: "Cache TTL (seconds)", type: "text", value: "300" },
        { label: "Event retention", type: "select", value: "30", options: ["7 days", "14 days", "30 days", "90 days"] },
      ],
    },
  };

  const config = configs[section] || configs["API Keys"];

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[440px]">
        {success ? (
          <div className="py-8 text-center">
            <CheckCircle2 className="w-10 h-10 text-success mx-auto mb-3" />
            <p className="text-[16px] font-semibold text-foreground">Settings saved</p>
            <p className="text-[13px] text-muted-foreground mt-1">{section} configuration updated.</p>
          </div>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle className="text-[18px] tracking-[-0.02em]">{section}</DialogTitle>
              <DialogDescription>Configure {section.toLowerCase()} settings for this environment.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              {config.fields.map((field) => (
                <div key={field.label} className="space-y-2">
                  <label className="text-[12px] text-muted-foreground uppercase tracking-wide font-medium">{field.label}</label>
                  {field.type === "select" && field.options ? (
                    <Select defaultValue={field.value}>
                      <SelectTrigger className="h-10 text-[13px]"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {field.options.map(o => (
                          <SelectItem key={o} value={o} className="text-[13px]">{o}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input defaultValue={field.value} className="h-10 text-[13px]" />
                  )}
                </div>
              ))}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={onClose} className="text-[13px]">Cancel</Button>
              <Button onClick={handleSave} disabled={loading} className="text-[13px] gap-1.5">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {loading ? "Saving…" : "Save changes"}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function APIKeyRotateDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [loading, setLoading] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [showKey, setShowKey] = useState(false);

  const handleRotate = async () => {
    setLoading(true);
    try {
      const res = await authAPI.login("rotate", "key"); // Try real API first
      setNewKey((res as any)?.data?.access_token || "sk_live_" + Math.random().toString(36).substring(2, 18));
    } catch {
      setNewKey("sk_live_" + Math.random().toString(36).substring(2, 18));
    }
    setLoading(false);
    toast.success("API key rotated", { description: "The old key will remain active for 24 hours." });
  };

  return (
    <Dialog open={open} onOpenChange={() => { onClose(); setNewKey(null); setShowKey(false); }}>
      <DialogContent className="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle className="text-[18px] tracking-[-0.02em]">Rotate API key</DialogTitle>
          <DialogDescription>
            Generate a new API key. The previous key will remain active for 24 hours to allow migration.
          </DialogDescription>
        </DialogHeader>
        {newKey ? (
          <div className="space-y-4 py-4">
            <div className="rounded-lg bg-accent/50 border border-border px-4 py-3">
              <p className="text-[11px] text-muted-foreground uppercase tracking-wide font-medium mb-2">New API key</p>
              <div className="flex items-center gap-2">
                <code className="text-[13px] font-mono text-foreground flex-1 break-all">
                  {showKey ? newKey : newKey.replace(/./g, "•").substring(0, 24) + newKey.slice(-4)}
                </code>
                <button onClick={() => setShowKey(!showKey)} className="text-muted-foreground hover:text-foreground">
                  {showKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
                <button onClick={() => { navigator.clipboard.writeText(newKey); toast.success("Copied"); }} className="text-muted-foreground hover:text-foreground">
                  <Copy className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
            <div className="px-3.5 py-2.5 rounded-lg bg-warning/8 border border-warning/20 text-[12px] text-warning">
              Save this key now. It won't be shown again.
            </div>
          </div>
        ) : (
          <div className="py-4">
            <div className="px-3.5 py-3 rounded-lg bg-destructive/6 border border-destructive/15 text-[13px] text-foreground mb-4">
              This will generate a new key and schedule the old one for deletion in 24 hours.
            </div>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => { onClose(); setNewKey(null); setShowKey(false); }} className="text-[13px]">
            {newKey ? "Done" : "Cancel"}
          </Button>
          {!newKey && (
            <Button onClick={handleRotate} disabled={loading} variant="destructive" className="text-[13px] gap-1.5">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
              {loading ? "Rotating…" : "Rotate key"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const sections = [
  {
    icon: Key,
    title: "API Keys",
    description: "Key management, rotation, HMAC signing configuration",
    items: [
      { label: "Production key", value: "sk_live_••••••••a4f2", status: "Active", action: "rotate" },
      { label: "Sandbox key", value: "sk_test_••••••••b7e1", status: "Active", action: null },
    ],
  },
  {
    icon: Shield,
    title: "Security & Auth",
    description: "Authentication policies, MFA requirements, session management",
    items: [
      { label: "MFA requirement", value: "High-risk actions", status: "Enforced", action: null },
      { label: "Session timeout", value: "30 minutes", status: "Active", action: null },
      { label: "IP allowlist", value: "3 CIDR ranges", status: "Active", action: null },
    ],
  },
  {
    icon: Globe,
    title: "Tenant Configuration",
    description: "Multi-tenant settings, feature flags, provider routing",
    items: [
      { label: "Active tenants", value: "4", status: "", action: null },
      { label: "Default payout rail", value: "IMPS", status: "", action: null },
      { label: "KYC auto-approve threshold", value: "≥ 92% confidence", status: "Active", action: null },
    ],
  },
  {
    icon: Database,
    title: "Infrastructure",
    description: "Database, cache, event bus, workflow engine status",
    items: [
      { label: "PostgreSQL", value: "v17.9 — 3 replicas", status: "Healthy", action: null },
      { label: "Redis", value: "v8.2.4 — cluster mode", status: "Healthy", action: null },
      { label: "Redpanda", value: "14 topics, 56 partitions", status: "Healthy", action: null },
      { label: "Temporal", value: "3 workers, 7 active workflows", status: "Healthy", action: null },
    ],
  },
];

export default function SettingsPage() {
  const { user, updateOrgProfile } = useAuth();
  const [configDialog, setConfigDialog] = useState<string | null>(null);
  const [rotateKeyOpen, setRotateKeyOpen] = useState(false);
  const [orgEditing, setOrgEditing] = useState(false);
  const [orgName, setOrgName] = useState(user?.orgProfile?.companyName || "");
  const [orgIndustry, setOrgIndustry] = useState(user?.orgProfile?.industry || "");
  const [orgRole, setOrgRole] = useState(user?.orgProfile?.userRole || "");

  const handleOrgSave = () => {
    updateOrgProfile({ companyName: orgName, industry: orgIndustry, userRole: orgRole });
    setOrgEditing(false);
    toast.success("Organization updated");
  };

  return (
    <DashboardLayout title="Settings" subtitle="Platform configuration, security, and infrastructure">
      <div className="space-y-4 md:space-y-6 max-w-4xl">
        {/* Organization */}
        <div className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between px-4 md:px-5 py-4 border-b border-border gap-3">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center shrink-0">
                <Building2 className="w-4 h-4 text-muted-foreground" strokeWidth={1.75} />
              </div>
              <div className="min-w-0">
                <span className="text-[14px] font-semibold text-foreground block">Organization</span>
                <span className="text-[12px] text-muted-foreground block mt-0.5">Company name, industry, and your role</span>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="h-8 text-[12px] px-3 text-muted-foreground self-start sm:self-auto shrink-0"
              onClick={() => orgEditing ? handleOrgSave() : setOrgEditing(true)}
            >
              {orgEditing ? "Save" : "Edit"}
            </Button>
          </div>
          <div className="divide-y divide-border/50">
            {orgEditing ? (
              <div className="px-4 md:px-5 py-4 space-y-4">
                <div className="space-y-2">
                  <label className="text-[12px] text-muted-foreground uppercase tracking-wide font-medium">Company name</label>
                  <Input value={orgName} onChange={e => setOrgName(e.target.value)} className="h-10 text-[13px]" />
                </div>
                <div className="space-y-2">
                  <label className="text-[12px] text-muted-foreground uppercase tracking-wide font-medium">Industry</label>
                  <Input value={orgIndustry} onChange={e => setOrgIndustry(e.target.value)} className="h-10 text-[13px]" />
                </div>
                <div className="space-y-2">
                  <label className="text-[12px] text-muted-foreground uppercase tracking-wide font-medium">Your role</label>
                  <Input value={orgRole} onChange={e => setOrgRole(e.target.value)} className="h-10 text-[13px]" />
                </div>
              </div>
            ) : (
              <>
                {[
                  { label: "Company name", value: user?.orgProfile?.companyName || "—" },
                  { label: "Industry", value: user?.orgProfile?.industry || "—" },
                  { label: "Your role", value: user?.orgProfile?.userRole || "—" },
                ].map(item => (
                  <div key={item.label} className="flex flex-col sm:flex-row sm:items-center justify-between px-4 md:px-5 py-3 gap-1">
                    <span className="text-[13px] text-foreground">{item.label}</span>
                    <span className="text-[12px] text-muted-foreground">{item.value}</span>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>

        {sections.map((section) => (
          <div key={section.title} className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between px-4 md:px-5 py-4 border-b border-border gap-3">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center shrink-0">
                  <section.icon className="w-4 h-4 text-muted-foreground" strokeWidth={1.75} />
                </div>
                <div className="min-w-0">
                  <span className="text-[14px] font-semibold text-foreground block">{section.title}</span>
                  <span className="text-[12px] text-muted-foreground block mt-0.5">{section.description}</span>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-[12px] px-3 text-muted-foreground self-start sm:self-auto shrink-0"
                onClick={() => setConfigDialog(section.title)}
              >
                Configure
              </Button>
            </div>
            <div className="divide-y divide-border/50">
              {section.items.map((item) => (
                <div key={item.label} className="flex flex-col sm:flex-row sm:items-center justify-between px-4 md:px-5 py-3 gap-1">
                  <span className="text-[13px] text-foreground">{item.label}</span>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-[12px] text-muted-foreground">{item.value}</span>
                    {item.status && (
                      <span className="text-[11px] font-medium text-success">{item.status}</span>
                    )}
                    {item.action === "rotate" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-[10px] px-2 text-muted-foreground hover:text-foreground gap-1"
                        onClick={() => setRotateKeyOpen(true)}
                      >
                        <RotateCcw className="w-3 h-3" />Rotate
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {configDialog && (
        <ConfigDialog open={!!configDialog} onClose={() => setConfigDialog(null)} section={configDialog} />
      )}
      <APIKeyRotateDialog open={rotateKeyOpen} onClose={() => setRotateKeyOpen(false)} />
    </DashboardLayout>
  );
}
