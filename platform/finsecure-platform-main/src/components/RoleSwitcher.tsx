import { useAuth, AppRole, ROLE_LABELS } from "@/contexts/AuthContext";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Shield } from "lucide-react";

const roles: AppRole[] = ["admin", "ops_analyst", "finance_operator", "compliance_reviewer", "developer", "readonly_auditor"];

export default function RoleSwitcher() {
  const { user, switchRole } = useAuth();
  if (!user) return null;

  return (
    <div className="flex items-center gap-2">
      <Shield className="w-3.5 h-3.5 text-muted-foreground" />
      <Select value={user.role} onValueChange={(v) => switchRole(v as AppRole)}>
        <SelectTrigger className="h-7 text-[11px] border-border bg-card w-auto min-w-[140px] gap-1.5">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {roles.map(r => (
            <SelectItem key={r} value={r} className="text-[12px]">
              {ROLE_LABELS[r]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
