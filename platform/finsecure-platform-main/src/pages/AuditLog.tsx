import { useState, useEffect } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import StatusBadge from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Download, Filter, X, ChevronLeft, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { auditAPI } from "@/lib/api";

const MOCK_AUDIT_EVENTS = [
  { id: "aud_01", time: "2026-03-07 09:12:04", actor: "Arjun Kapoor", action: "payout.created", entity: "PO-2026-00891", ip: "103.21.58.xx", status: "success" },
  { id: "aud_02", time: "2026-03-07 09:10:22", actor: "System", action: "kyc.auto_approved", entity: "KYC-4521", ip: "—", status: "success" },
  { id: "aud_03", time: "2026-03-07 09:08:15", actor: "Priya Sharma", action: "recon.break_resolved", entity: "BRK-221", ip: "49.36.12.xx", status: "success" },
  { id: "aud_04", time: "2026-03-07 09:05:41", actor: "Arjun Kapoor", action: "user.role_changed", entity: "usr_05", ip: "103.21.58.xx", status: "success" },
  { id: "aud_05", time: "2026-03-07 09:02:33", actor: "System", action: "payout.failed", entity: "PO-2026-00890", ip: "—", status: "failure" },
  { id: "aud_06", time: "2026-03-07 08:55:19", actor: "Ravi Patel", action: "webhook.endpoint_created", entity: "wh_ep_07", ip: "103.21.58.xx", status: "success" },
  { id: "aud_07", time: "2026-03-07 08:50:02", actor: "Ananya Desai", action: "kyc.manual_review", entity: "KYC-4519", ip: "49.36.12.xx", status: "success" },
  { id: "aud_08", time: "2026-03-07 08:42:18", actor: "System", action: "risk.alert_created", entity: "ALT-0093", ip: "—", status: "warning" },
  { id: "aud_09", time: "2026-03-07 08:35:07", actor: "Arjun Kapoor", action: "api_key.rotated", entity: "key_prod_01", ip: "103.21.58.xx", status: "success" },
  { id: "aud_10", time: "2026-03-07 08:12:00", actor: "Arjun Kapoor", action: "user.login", entity: "usr_01", ip: "103.21.58.xx", status: "success" },
];

export default function AuditLogPage() {
  const [showFilters, setShowFilters] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("__all__");
  const [actorFilter, setActorFilter] = useState("__all__");
  const [page, setPage] = useState(0);
  const [allAuditEvents, setAllAuditEvents] = useState(MOCK_AUDIT_EVENTS);
  const pageSize = 8;

  useEffect(() => {
    auditAPI.list().then(res => {
      if (res.data && Array.isArray(res.data) && res.data.length > 0) setAllAuditEvents(res.data as typeof MOCK_AUDIT_EVENTS);
    }).catch(() => { });
  }, []);

  const filtered = allAuditEvents.filter(e => {
    if (statusFilter !== "__all__" && e.status !== statusFilter) return false;
    if (actorFilter !== "__all__" && e.actor !== actorFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return e.action.includes(q) || e.entity.toLowerCase().includes(q) || e.actor.toLowerCase().includes(q);
    }
    return true;
  });

  const totalPages = Math.ceil(filtered.length / pageSize);
  const paged = filtered.slice(page * pageSize, (page + 1) * pageSize);
  const actors = [...new Set(allAuditEvents.map(e => e.actor))];

  const exportAudit = () => {
    const header = "Timestamp,Actor,Action,Entity,IP,Status";
    const rows = filtered.map(e => `"${e.time}","${e.actor}","${e.action}","${e.entity}","${e.ip}","${e.status}"`);
    const csv = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "audit-log.csv";
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Export complete", { description: `${filtered.length} audit events exported.` });
  };

  const clearFilters = () => {
    setSearch("");
    setStatusFilter("__all__");
    setActorFilter("__all__");
    setPage(0);
  };

  const hasFilters = search || statusFilter !== "__all__" || actorFilter !== "__all__";

  return (
    <DashboardLayout
      title="Audit log"
      subtitle="Immutable record of all platform actions"
      actions={
        <Button variant="outline" size="sm" className="h-8 text-[12px] gap-1.5" onClick={exportAudit}>
          <Download className="w-3.5 h-3.5" />
          Export
        </Button>
      }
    >
      <div className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
        <div className="px-4 md:px-5 py-3 border-b border-border flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <div className="relative flex-1 md:max-w-[240px]">
              <Input
                value={search}
                onChange={e => { setSearch(e.target.value); setPage(0); }}
                placeholder="Search actions…"
                className="h-8 text-[13px] bg-accent/30 border-border pl-3"
              />
            </div>
            <span className="text-[12px] text-muted-foreground">{filtered.length} events</span>
          </div>
          <div className="flex items-center gap-2">
            {hasFilters && (
              <Button variant="ghost" size="sm" className="h-7 text-[11px] px-2 text-muted-foreground" onClick={clearFilters}>
                <X className="w-3 h-3 mr-1" />Clear
              </Button>
            )}
            <Button
              variant={showFilters ? "secondary" : "ghost"}
              size="sm"
              className="h-7 text-[11px] gap-1.5 text-muted-foreground"
              onClick={() => setShowFilters(!showFilters)}
            >
              <Filter className="w-3 h-3" />
              Filter
            </Button>
          </div>
        </div>

        {showFilters && (
          <div className="flex flex-wrap gap-2 px-4 md:px-5 py-2.5 border-b border-border bg-accent/20">
            <Select value={statusFilter} onValueChange={v => { setStatusFilter(v); setPage(0); }}>
              <SelectTrigger className="h-8 text-[12px] border-border bg-card w-auto min-w-[110px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__" className="text-[12px]">All statuses</SelectItem>
                <SelectItem value="success" className="text-[12px]">Success</SelectItem>
                <SelectItem value="failure" className="text-[12px]">Failure</SelectItem>
                <SelectItem value="warning" className="text-[12px]">Warning</SelectItem>
              </SelectContent>
            </Select>
            <Select value={actorFilter} onValueChange={v => { setActorFilter(v); setPage(0); }}>
              <SelectTrigger className="h-8 text-[12px] border-border bg-card w-auto min-w-[130px]">
                <SelectValue placeholder="Actor" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__" className="text-[12px]">All actors</SelectItem>
                {actors.map(a => (
                  <SelectItem key={a} value={a} className="text-[12px]">{a}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {/* Desktop table */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                <th className="text-left font-medium text-muted-foreground px-5 py-2.5 text-[11px] uppercase tracking-[0.04em]">Timestamp</th>
                <th className="text-left font-medium text-muted-foreground px-5 py-2.5 text-[11px] uppercase tracking-[0.04em]">Actor</th>
                <th className="text-left font-medium text-muted-foreground px-5 py-2.5 text-[11px] uppercase tracking-[0.04em]">Action</th>
                <th className="text-left font-medium text-muted-foreground px-5 py-2.5 text-[11px] uppercase tracking-[0.04em]">Entity</th>
                <th className="text-left font-medium text-muted-foreground px-5 py-2.5 text-[11px] uppercase tracking-[0.04em]">IP</th>
                <th className="text-left font-medium text-muted-foreground px-5 py-2.5 text-[11px] uppercase tracking-[0.04em]">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {paged.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-5 py-12 text-center text-[13px] text-muted-foreground">
                    No events match your filters.
                  </td>
                </tr>
              ) : (
                paged.map((event) => (
                  <tr key={event.id} className="hover:bg-muted/20 transition-colors">
                    <td className="px-5 py-3 font-mono text-[12px] text-muted-foreground whitespace-nowrap">{event.time}</td>
                    <td className="px-5 py-3 text-foreground">{event.actor}</td>
                    <td className="px-5 py-3 font-mono text-[12px] text-foreground">{event.action}</td>
                    <td className="px-5 py-3 font-mono text-[12px] text-muted-foreground">{event.entity}</td>
                    <td className="px-5 py-3 font-mono text-[12px] text-muted-foreground">{event.ip}</td>
                    <td className="px-5 py-3">
                      <StatusBadge
                        status={event.status}
                        variant={event.status === "success" ? "success" : event.status === "failure" ? "destructive" : "warning"}
                      />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Mobile cards */}
        <div className="md:hidden divide-y divide-border/50">
          {paged.length === 0 ? (
            <div className="px-4 py-12 text-center text-[13px] text-muted-foreground">No events match your filters.</div>
          ) : (
            paged.map((event) => (
              <div key={event.id} className="px-4 py-3.5 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[12px] text-foreground">{event.action}</span>
                  <StatusBadge
                    status={event.status}
                    variant={event.status === "success" ? "success" : event.status === "failure" ? "destructive" : "warning"}
                  />
                </div>
                <div className="flex items-center justify-between text-[12px] text-muted-foreground">
                  <span>{event.actor}</span>
                  <span className="font-mono">{event.entity}</span>
                </div>
                <div className="text-[11px] text-muted-foreground font-mono">{event.time} · {event.ip}</div>
              </div>
            ))
          )}
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between px-4 md:px-5 py-3 border-t border-border">
          <span className="text-[12px] text-muted-foreground">
            {filtered.length} event{filtered.length !== 1 ? "s" : ""}
            {totalPages > 1 && ` · Page ${page + 1} of ${totalPages}`}
          </span>
          {totalPages > 1 && (
            <div className="flex items-center gap-1">
              <Button variant="outline" size="sm" className="h-7 w-7 p-0" disabled={page === 0} onClick={() => setPage(p => p - 1)}>
                <ChevronLeft className="w-3.5 h-3.5" />
              </Button>
              <Button variant="outline" size="sm" className="h-7 w-7 p-0" disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>
                <ChevronRight className="w-3.5 h-3.5" />
              </Button>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
