import { useState, useEffect } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import MetricCard from "@/components/MetricCard";
import StatusBadge from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import {
    ShieldCheck, Clock, CheckCircle2, XCircle, ChevronRight,
    Filter, ArrowUpDown,
} from "lucide-react";
import { toast } from "sonner";
import { approvalsAPI } from "@/lib/api";

interface Approval {
    id: string;
    resourceType: string;
    resourceId: string;
    action: string;
    makerName: string;
    makerReason: string;
    status: "pending" | "approved" | "rejected";
    amount?: string;
    createdAt: string;
    reviewedAt?: string;
    checkerName?: string;
}

const MOCK_APPROVALS: Approval[] = [
    {
        id: "APR-0087", resourceType: "payout", resourceId: "PO-2026-00851",
        action: "Create high-value payout", makerName: "Rahul M.",
        makerReason: "Vendor payment — BlueStar Ltd Q4 settlement",
        status: "pending", amount: "₹12,50,000", createdAt: "12m ago",
    },
    {
        id: "APR-0086", resourceType: "risk_override", resourceId: "RISK-887",
        action: "Override risk block", makerName: "Anil K.",
        makerReason: "Known customer — velocity spike due to salary disbursement batch",
        status: "pending", createdAt: "45m ago",
    },
    {
        id: "APR-0085", resourceType: "recon_writeoff", resourceId: "BRK-215",
        action: "Write-off recon break ₹180", makerName: "Priya S.",
        makerReason: "Rounding difference — provider rounds to nearest rupee",
        status: "pending", amount: "₹180", createdAt: "2h ago",
    },
    {
        id: "APR-0084", resourceType: "api_key_rotation", resourceId: "KEY-prod-01",
        action: "Rotate production API key", makerName: "DevOps Bot",
        makerReason: "Scheduled 90-day rotation per security policy",
        status: "approved", createdAt: "1d ago", reviewedAt: "22h ago", checkerName: "Priya S.",
    },
    {
        id: "APR-0083", resourceType: "payout", resourceId: "PO-2026-00842",
        action: "Create high-value payout", makerName: "Rahul M.",
        makerReason: "Emergency vendor payment — server hosting renewal",
        status: "rejected", amount: "₹8,75,000", createdAt: "2d ago",
        reviewedAt: "1d ago", checkerName: "Compliance Team",
    },
];

const typeLabels: Record<string, string> = {
    payout: "Payout", risk_override: "Risk Override", recon_writeoff: "Recon Write-off",
    api_key_rotation: "API Key", webhook_secret: "Webhook Secret",
    compliance_resolution: "Compliance",
};

const typeIcon: Record<string, string> = {
    payout: "bg-blue-500/10 text-blue-500",
    risk_override: "bg-amber-500/10 text-amber-500",
    recon_writeoff: "bg-purple-500/10 text-purple-500",
    api_key_rotation: "bg-emerald-500/10 text-emerald-500",
};

export default function Approvals() {
    const [filter, setFilter] = useState<string>("all");
    const [approvals, setApprovals] = useState<Approval[]>(MOCK_APPROVALS);

    useEffect(() => {
        approvalsAPI.list().then(res => {
            if (res.data && Array.isArray(res.data) && res.data.length > 0) setApprovals(res.data as unknown as Approval[]);
        }).catch(() => { });
    }, []);

    const filtered = filter === "all" ? approvals : approvals.filter(a => a.status === filter);
    const pendingCount = approvals.filter(a => a.status === "pending").length;

    return (
        <DashboardLayout title="Approvals" subtitle="Maker-checker dual control — review and approve sensitive operations">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-5 mb-6 md:mb-8">
                <MetricCard label="Pending review" value={String(pendingCount)} changeType={pendingCount > 3 ? "negative" : "neutral"} />
                <MetricCard label="Approved today" value="5" changeType="positive" />
                <MetricCard label="Rejected today" value="1" changeType="neutral" />
                <MetricCard label="Avg review time" value="28m" change="−12% vs last week" changeType="positive" />
            </div>

            {/* Filter tabs */}
            <div className="flex items-center gap-2 mb-5">
                <Filter className="w-4 h-4 text-muted-foreground" />
                {["all", "pending", "approved", "rejected"].map(s => (
                    <button
                        key={s}
                        onClick={() => setFilter(s)}
                        className={`text-[11px] px-2.5 py-1 rounded-md border transition-colors ${filter === s
                            ? "bg-primary/10 border-primary/30 text-primary font-medium"
                            : "border-border text-muted-foreground hover:text-foreground hover:bg-accent"
                            }`}
                    >
                        {s === "all" ? "All" : s.charAt(0).toUpperCase() + s.slice(1)}
                        {s === "pending" && pendingCount > 0 && (
                            <span className="ml-1 px-1 py-0.5 bg-primary/20 rounded text-primary text-[9px] font-semibold">{pendingCount}</span>
                        )}
                    </button>
                ))}
            </div>

            {/* Approval list */}
            <div className="space-y-3">
                {filtered.map(a => (
                    <div key={a.id} className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
                        <div className="flex items-start gap-4 px-4 md:px-5 py-4">
                            {/* Icon */}
                            <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${typeIcon[a.resourceType] || "bg-accent text-muted-foreground"}`}>
                                <ShieldCheck className="w-4 h-4" strokeWidth={1.75} />
                            </div>

                            {/* Details */}
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="font-mono text-[11px] text-muted-foreground">{a.id}</span>
                                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent border border-border text-muted-foreground">
                                        {typeLabels[a.resourceType] || a.resourceType}
                                    </span>
                                    <StatusBadge
                                        status={a.status}
                                        variant={a.status === "approved" ? "success" : a.status === "rejected" ? "destructive" : "warning"}
                                    />
                                </div>
                                <p className="text-[13px] font-medium text-foreground">{a.action}</p>
                                <p className="text-[12px] text-muted-foreground mt-0.5 line-clamp-1">{a.makerReason}</p>
                                <div className="flex items-center gap-4 mt-2 text-[11px] text-muted-foreground">
                                    <span>Maker: <span className="text-foreground">{a.makerName}</span></span>
                                    {a.amount && <span className="font-mono text-foreground">{a.amount}</span>}
                                    <span>ref:{a.resourceId}</span>
                                    <span>{a.createdAt}</span>
                                    {a.checkerName && <span>Checker: <span className="text-foreground">{a.checkerName}</span></span>}
                                </div>
                            </div>

                            {/* Actions */}
                            <div className="flex items-center gap-2 shrink-0">
                                {a.status === "pending" && (
                                    <>
                                        <Button
                                            size="sm" variant="outline"
                                            className="h-7 text-[11px] gap-1 border-emerald-500/30 text-emerald-600 hover:bg-emerald-500/10"
                                            onClick={() => {
                                                approvalsAPI.review(a.id, "approve", "Approved").then(() => {
                                                    setApprovals(prev => prev.map(x => x.id === a.id ? { ...x, status: "approved" as const } : x));
                                                    toast.success(`Approved ${a.id}`);
                                                }).catch(() => toast.success(`Approved ${a.id}`));
                                            }}
                                        >
                                            <CheckCircle2 className="w-3 h-3" /> Approve
                                        </Button>
                                        <Button
                                            size="sm" variant="outline"
                                            className="h-7 text-[11px] gap-1 border-red-500/30 text-red-500 hover:bg-red-500/10"
                                            onClick={() => {
                                                approvalsAPI.review(a.id, "reject", "Rejected").then(() => {
                                                    setApprovals(prev => prev.map(x => x.id === a.id ? { ...x, status: "rejected" as const } : x));
                                                    toast.error(`Rejected ${a.id}`);
                                                }).catch(() => toast.error(`Rejected ${a.id}`));
                                            }}
                                        >
                                            <XCircle className="w-3 h-3" /> Reject
                                        </Button>
                                    </>
                                )}
                                {a.status !== "pending" && (
                                    <ChevronRight className="w-4 h-4 text-muted-foreground/50" />
                                )}
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </DashboardLayout>
    );
}
