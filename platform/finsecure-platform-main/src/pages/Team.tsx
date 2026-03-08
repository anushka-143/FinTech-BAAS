import DashboardLayout from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import StatusBadge from "@/components/StatusBadge";
import { UserPlus, MoreHorizontal, Shield, Trash2, Edit2, Loader2 } from "lucide-react";
import { ROLE_LABELS } from "@/contexts/AuthContext";
import { toast } from "sonner";
import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { AppRole } from "@/contexts/AuthContext";

const initialMembers = [
  { id: "usr_01", name: "Arjun Kapoor", email: "arjun.kapoor@finstack.io", role: "admin" as AppRole, status: "Active", initials: "AK", lastActive: "2m ago" },
  { id: "usr_02", name: "Priya Sharma", email: "priya.sharma@finstack.io", role: "ops_analyst" as AppRole, status: "Active", initials: "PS", lastActive: "15m ago" },
  { id: "usr_03", name: "Ravi Patel", email: "ravi.patel@finstack.io", role: "finance_operator" as AppRole, status: "Active", initials: "RP", lastActive: "1h ago" },
  { id: "usr_04", name: "Ananya Desai", email: "ananya.desai@finstack.io", role: "compliance_reviewer" as AppRole, status: "Active", initials: "AD", lastActive: "3h ago" },
  { id: "usr_05", name: "Vikram Singh", email: "vikram.singh@finstack.io", role: "developer" as AppRole, status: "Invited", initials: "VS", lastActive: "Pending" },
];

export default function TeamPage() {
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<AppRole>("ops_analyst");
  const [loading, setLoading] = useState(false);
  const [members, setMembers] = useState(initialMembers);
  const [editMember, setEditMember] = useState<typeof initialMembers[0] | null>(null);
  const [editRole, setEditRole] = useState<AppRole>("ops_analyst");
  const [removeOpen, setRemoveOpen] = useState<string | null>(null);

  const handleInvite = async () => {
    if (!inviteEmail) return;
    setLoading(true);
    await new Promise(r => setTimeout(r, 800));
    const initials = inviteEmail.split("@")[0].split(".").map(p => p[0]?.toUpperCase() || "").join("").slice(0, 2);
    setMembers(prev => [...prev, {
      id: `usr_${Date.now()}`,
      name: inviteEmail.split("@")[0].replace(".", " ").replace(/\b\w/g, c => c.toUpperCase()),
      email: inviteEmail,
      role: inviteRole,
      status: "Invited",
      initials,
      lastActive: "Pending",
    }]);
    setLoading(false);
    setInviteOpen(false);
    setInviteEmail("");
    toast.success("Invitation sent", { description: `Invited ${inviteEmail} as ${ROLE_LABELS[inviteRole]}.` });
  };

  const handleRoleChange = async () => {
    if (!editMember) return;
    setLoading(true);
    await new Promise(r => setTimeout(r, 600));
    setMembers(prev => prev.map(m => m.id === editMember.id ? { ...m, role: editRole } : m));
    setLoading(false);
    setEditMember(null);
    toast.success("Role updated", { description: `${editMember.name} is now ${ROLE_LABELS[editRole]}.` });
  };

  const handleRemove = async (id: string) => {
    setLoading(true);
    await new Promise(r => setTimeout(r, 600));
    const member = members.find(m => m.id === id);
    setMembers(prev => prev.filter(m => m.id !== id));
    setLoading(false);
    setRemoveOpen(null);
    toast.success("Member removed", { description: `${member?.name} has been removed from the team.` });
  };

  return (
    <DashboardLayout
      title="Team"
      subtitle="Manage team members, roles, and access"
      actions={
        <Button size="sm" className="h-8 text-[12px] gap-1.5" onClick={() => setInviteOpen(true)}>
          <UserPlus className="w-3.5 h-3.5" />
          Invite member
        </Button>
      }
    >
      <div className="max-w-4xl">
        <div className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
          <div className="px-5 md:px-6 py-4 border-b border-border flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Shield className="w-4 h-4 text-muted-foreground" strokeWidth={1.75} />
              <span className="text-[14px] font-semibold text-foreground">Team members</span>
            </div>
            <span className="text-[11px] text-muted-foreground">{members.length} members</span>
          </div>
          <div className="divide-y divide-border/50">
            {members.map((member) => (
              <div key={member.id} className="flex flex-col sm:flex-row sm:items-center justify-between px-5 md:px-6 py-4 gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-full bg-primary/10 border border-border flex items-center justify-center text-[11px] font-semibold text-primary shrink-0">
                    {member.initials}
                  </div>
                  <div className="min-w-0">
                    <p className="text-[13px] font-medium text-foreground truncate">{member.name}</p>
                    <p className="text-[12px] text-muted-foreground truncate">{member.email}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 sm:gap-4 shrink-0">
                  <StatusBadge status={ROLE_LABELS[member.role]} variant="default" />
                  <StatusBadge status={member.status} variant={member.status === "Active" ? "success" : "warning"} />
                  <span className="text-[11px] text-muted-foreground hidden md:inline w-16 text-right">{member.lastActive}</span>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="ghost" size="sm" className="w-7 h-7 p-0">
                        <MoreHorizontal className="w-3.5 h-3.5 text-muted-foreground" />
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-[160px] p-1.5" align="end">
                      <button
                        onClick={() => { setEditMember(member); setEditRole(member.role); }}
                        className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-[12px] text-foreground hover:bg-accent transition-colors"
                      >
                        <Edit2 className="w-3 h-3 text-muted-foreground" />
                        Change role
                      </button>
                      {member.id !== "usr_01" && (
                        <button
                          onClick={() => setRemoveOpen(member.id)}
                          className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-[12px] text-destructive hover:bg-destructive/10 transition-colors"
                        >
                          <Trash2 className="w-3 h-3" />
                          Remove
                        </button>
                      )}
                    </PopoverContent>
                  </Popover>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Invite Dialog */}
      <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-[16px]">Invite team member</DialogTitle>
            <DialogDescription>Send an invitation to join this workspace.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <label className="text-[12px] font-medium text-muted-foreground uppercase tracking-wide">Email address</label>
              <Input placeholder="colleague@company.com" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} className="h-10" />
            </div>
            <div className="space-y-1.5">
              <label className="text-[12px] font-medium text-muted-foreground uppercase tracking-wide">Role</label>
              <Select value={inviteRole} onValueChange={(v) => setInviteRole(v as AppRole)}>
                <SelectTrigger className="h-10"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(Object.keys(ROLE_LABELS) as AppRole[]).map(r => (
                    <SelectItem key={r} value={r}>{ROLE_LABELS[r]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setInviteOpen(false)} className="text-[13px]">Cancel</Button>
            <Button onClick={handleInvite} disabled={!inviteEmail || loading} className="text-[13px] gap-1.5">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              {loading ? "Sending…" : "Send invite"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Role Dialog */}
      <Dialog open={!!editMember} onOpenChange={() => setEditMember(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-[16px]">Change role</DialogTitle>
            <DialogDescription>Update the role for {editMember?.name}.</DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Select value={editRole} onValueChange={(v) => setEditRole(v as AppRole)}>
              <SelectTrigger className="h-10"><SelectValue /></SelectTrigger>
              <SelectContent>
                {(Object.keys(ROLE_LABELS) as AppRole[]).map(r => (
                  <SelectItem key={r} value={r}>{ROLE_LABELS[r]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditMember(null)} className="text-[13px]">Cancel</Button>
            <Button onClick={handleRoleChange} disabled={loading} className="text-[13px] gap-1.5">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              {loading ? "Updating…" : "Update role"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Remove Confirmation */}
      <Dialog open={!!removeOpen} onOpenChange={() => setRemoveOpen(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-[16px]">Remove team member</DialogTitle>
            <DialogDescription>
              This will immediately revoke access for {members.find(m => m.id === removeOpen)?.name}. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="pt-4">
            <Button variant="outline" onClick={() => setRemoveOpen(null)} className="text-[13px]">Cancel</Button>
            <Button variant="destructive" onClick={() => removeOpen && handleRemove(removeOpen)} disabled={loading} className="text-[13px] gap-1.5">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              {loading ? "Removing…" : "Remove member"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </DashboardLayout>
  );
}
