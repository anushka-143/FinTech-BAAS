import { useState } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import StatusBadge from "@/components/StatusBadge";
import { Shield, Smartphone, Monitor, Globe, LogOut, Key, Mail, Clock, Fingerprint, Loader2, CheckCircle2, Camera, Building2, Briefcase, UserCircle } from "lucide-react";
import { toast } from "sonner";

function EditProfileDialog({ open, onClose, user }: { open: boolean; onClose: () => void; user: any }) {
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState(user?.name || "");
  const [email, setEmail] = useState(user?.email || "");

  const handleSave = async () => {
    setLoading(true);
    await new Promise(r => setTimeout(r, 800));
    setLoading(false);
    toast.success("Profile updated", { description: "Your changes have been saved." });
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle className="text-[18px] tracking-[-0.02em]">Edit profile</DialogTitle>
          <DialogDescription>Update your personal information.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="flex items-center gap-4 mb-2">
            <div className="w-16 h-16 rounded-full bg-primary/10 border-2 border-primary/20 flex items-center justify-center text-xl font-semibold text-primary relative group cursor-pointer">
              {user?.initials}
              <div className="absolute inset-0 rounded-full bg-foreground/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                <Camera className="w-5 h-5 text-primary-foreground" />
              </div>
            </div>
            <div>
              <p className="text-[13px] text-foreground font-medium">Profile photo</p>
              <p className="text-[11px] text-muted-foreground">Click avatar to change</p>
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-[12px] text-muted-foreground uppercase tracking-wide font-medium">Full name</label>
            <Input value={name} onChange={e => setName(e.target.value)} className="h-10 text-[13px]" />
          </div>
          <div className="space-y-2">
            <label className="text-[12px] text-muted-foreground uppercase tracking-wide font-medium">Email address</label>
            <Input value={email} onChange={e => setEmail(e.target.value)} className="h-10 text-[13px]" type="email" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="text-[13px]">Cancel</Button>
          <Button onClick={handleSave} disabled={loading} className="text-[13px] gap-1.5">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            {loading ? "Saving…" : "Save changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ChangePasswordDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [loading, setLoading] = useState(false);
  const [current, setCurrent] = useState("");
  const [newPass, setNewPass] = useState("");
  const [confirm, setConfirm] = useState("");

  const handleSave = async () => {
    if (newPass !== confirm) { toast.error("Passwords don't match"); return; }
    if (newPass.length < 12) { toast.error("Password must be at least 12 characters"); return; }
    setLoading(true);
    await new Promise(r => setTimeout(r, 800));
    setLoading(false);
    toast.success("Password changed", { description: "Your password has been updated." });
    setCurrent(""); setNewPass(""); setConfirm("");
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle className="text-[18px] tracking-[-0.02em]">Change password</DialogTitle>
          <DialogDescription>Enter your current password and choose a new one.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <label className="text-[12px] text-muted-foreground uppercase tracking-wide font-medium">Current password</label>
            <Input type="password" value={current} onChange={e => setCurrent(e.target.value)} className="h-10 text-[13px]" />
          </div>
          <div className="space-y-2">
            <label className="text-[12px] text-muted-foreground uppercase tracking-wide font-medium">New password</label>
            <Input type="password" value={newPass} onChange={e => setNewPass(e.target.value)} className="h-10 text-[13px]" placeholder="Min 12 characters" />
          </div>
          <div className="space-y-2">
            <label className="text-[12px] text-muted-foreground uppercase tracking-wide font-medium">Confirm new password</label>
            <Input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} className="h-10 text-[13px]" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="text-[13px]">Cancel</Button>
          <Button onClick={handleSave} disabled={loading || !current || !newPass} className="text-[13px] gap-1.5">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            {loading ? "Updating…" : "Update password"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function ProfilePage() {
  const { user, roleLabel, revokeSession } = useAuth();
  const [editOpen, setEditOpen] = useState(false);
  const [passwordOpen, setPasswordOpen] = useState(false);

  if (!user) return null;

  const handleRevoke = (sessionId: string) => {
    revokeSession(sessionId);
    toast.success("Session revoked", { description: "The device has been signed out." });
  };

  const sessionIcon = (device: string) => {
    if (device.toLowerCase().includes("iphone") || device.toLowerCase().includes("android")) return Smartphone;
    return Monitor;
  };

  return (
    <DashboardLayout title="Profile" subtitle="Your account, security, and active sessions">
      <div className="max-w-4xl space-y-6">
        {/* Identity card */}
        <div className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
          <div className="px-5 md:px-6 py-5 border-b border-border">
            <div className="flex flex-col sm:flex-row sm:items-center gap-4">
              <div className="w-14 h-14 rounded-full bg-primary/10 border-2 border-primary/20 flex items-center justify-center text-lg font-semibold text-primary shrink-0">
                {user.initials}
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="text-[18px] font-semibold text-foreground tracking-[-0.01em]">{user.name}</h2>
                <p className="text-[13px] text-muted-foreground mt-0.5">{user.email}</p>
                <div className="flex flex-wrap items-center gap-2 mt-2">
                  <StatusBadge status={roleLabel} variant="info" />
                  <StatusBadge status={user.environment} variant={user.environment === "production" ? "success" : "warning"} />
                </div>
              </div>
              <Button variant="outline" size="sm" className="h-8 text-[12px] self-start shrink-0" onClick={() => setEditOpen(true)}>
                Edit profile
              </Button>
            </div>
          </div>
          <div className="divide-y divide-border/50">
            {[
              { icon: Mail, label: "Email", value: user.email },
              { icon: Shield, label: "Role", value: roleLabel },
              { icon: Globe, label: "Tenant", value: user.tenantName },
              { icon: Building2, label: "Company", value: user.orgProfile?.companyName || "—" },
              { icon: Briefcase, label: "Industry", value: user.orgProfile?.industry || "—" },
              { icon: UserCircle, label: "Your role", value: user.orgProfile?.userRole || "—" },
              { icon: Key, label: "User ID", value: user.id, mono: true },
              { icon: Clock, label: "Last login", value: new Date(user.lastLogin).toLocaleString() },
            ].map((item) => (
              <div key={item.label} className="flex flex-col sm:flex-row sm:items-center justify-between px-5 md:px-6 py-3.5 gap-1">
                <div className="flex items-center gap-2.5">
                  <item.icon className="w-3.5 h-3.5 text-muted-foreground" strokeWidth={1.75} />
                  <span className="text-[13px] text-muted-foreground">{item.label}</span>
                </div>
                <span className={`text-[13px] text-foreground ${item.mono ? "font-mono text-[12px]" : ""}`}>{item.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Security */}
        <div className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
          <div className="px-5 md:px-6 py-4 border-b border-border">
            <div className="flex items-center gap-2.5">
              <Shield className="w-4 h-4 text-muted-foreground" strokeWidth={1.75} />
              <span className="text-[14px] font-semibold text-foreground">Security</span>
            </div>
          </div>
          <div className="divide-y divide-border/50">
            <div className="flex items-center justify-between px-5 md:px-6 py-4">
              <div>
                <p className="text-[13px] font-medium text-foreground">Multi-factor authentication</p>
                <p className="text-[12px] text-muted-foreground mt-0.5">Require MFA for sign-in and high-risk actions</p>
              </div>
              <Switch
                checked={user.mfaEnabled}
                onCheckedChange={(checked) => {
                  toast.success(checked ? "MFA enabled" : "MFA disabled", {
                    description: checked ? "MFA is now required for all sign-ins." : "MFA has been disabled. This is not recommended.",
                  });
                }}
              />
            </div>
            <div className="flex items-center justify-between px-5 md:px-6 py-4">
              <div>
                <p className="text-[13px] font-medium text-foreground">Passkey authentication</p>
                <p className="text-[12px] text-muted-foreground mt-0.5">Use biometrics or security keys for passwordless sign-in</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-[11px] gap-1.5 shrink-0"
                onClick={() => toast.success("Passkey registered", { description: "Touch ID passkey added successfully." })}
              >
                <Fingerprint className="w-3 h-3" />
                Set up
              </Button>
            </div>
            <div className="flex items-center justify-between px-5 md:px-6 py-4">
              <div>
                <p className="text-[13px] font-medium text-foreground">Change password</p>
                <p className="text-[12px] text-muted-foreground mt-0.5">Update your account password</p>
              </div>
              <Button variant="outline" size="sm" className="h-7 text-[11px] shrink-0" onClick={() => setPasswordOpen(true)}>
                Update
              </Button>
            </div>
          </div>
        </div>

        {/* Active sessions */}
        <div className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
          <div className="px-5 md:px-6 py-4 border-b border-border flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Monitor className="w-4 h-4 text-muted-foreground" strokeWidth={1.75} />
              <span className="text-[14px] font-semibold text-foreground">Active sessions</span>
            </div>
            <span className="text-[11px] text-muted-foreground">{user.sessions.length} devices</span>
          </div>
          <div className="divide-y divide-border/50">
            {user.sessions.map((session) => {
              const Icon = sessionIcon(session.device);
              return (
                <div key={session.id} className="flex flex-col sm:flex-row sm:items-center justify-between px-5 md:px-6 py-4 gap-3">
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center shrink-0 mt-0.5">
                      <Icon className="w-4 h-4 text-muted-foreground" strokeWidth={1.75} />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-[13px] font-medium text-foreground">{session.device}</p>
                        {session.current && <StatusBadge status="Current" variant="success" />}
                      </div>
                      <p className="text-[12px] text-muted-foreground mt-0.5">
                        {session.ip} · {session.location} · {session.lastActive}
                      </p>
                    </div>
                  </div>
                  {!session.current && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-[11px] text-destructive hover:text-destructive hover:bg-destructive/10 gap-1.5 self-start shrink-0"
                      onClick={() => handleRevoke(session.id)}
                    >
                      <LogOut className="w-3 h-3" />
                      Revoke
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <EditProfileDialog open={editOpen} onClose={() => setEditOpen(false)} user={user} />
      <ChangePasswordDialog open={passwordOpen} onClose={() => setPasswordOpen(false)} />
    </DashboardLayout>
  );
}
