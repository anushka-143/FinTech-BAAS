import { useState, useEffect } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import MetricCard from "@/components/MetricCard";
import StatusBadge from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import {
    FolderOpen, Clock, AlertTriangle, CheckCircle2, User, MessageSquare,
    ChevronRight, Filter, Plus,
} from "lucide-react";
import { toast } from "sonner";

type CaseStatus = "open" | "assigned" | "in_progress" | "pending_info" | "resolved" | "closed" | "escalated";
type CasePriority = "low" | "medium" | "high" | "critical";

interface Case {
    id: string;
    caseType: string;
    title: string;
    status: CaseStatus;
    priority: CasePriority;
    assignee: string;
    slaDeadline: string;
    slaStatus: "ok" | "warning" | "breached";
    createdAt: string;
    resourceRef: string;
    commentCount: number;
    aiSummary?: string;
}

const MOCK_CASES: Case[] = [
    {
        id: "CASE-1042", caseType: "kyc_review", title: "Meridian Finserv — GST director name mismatch",
        status: "in_progress", priority: "high", assignee: "Priya S.", slaDeadline: "2h 15m",
        slaStatus: "warning", createdAt: "42m ago", resourceRef: "KYC-4821", commentCount: 3,
        aiSummary: "GST certificate shows Suresh K. vs PAN shows Suresh Kumar. Likely abbreviation — AI confidence 74%.",
    },
    {
        id: "CASE-1041", caseType: "payout_failure", title: "BlueStar Ltd — NEFT payout BENE_INACTIVE",
        status: "assigned", priority: "medium", assignee: "Rahul M.", slaDeadline: "5h 30m",
        slaStatus: "ok", createdAt: "1h ago", resourceRef: "PO-2026-00844", commentCount: 1,
        aiSummary: "Beneficiary account marked dormant 3 days ago. Recommend re-verification + IMPS retry.",
    },
    {
        id: "CASE-1040", caseType: "recon_break", title: "₹450 mismatch — inter-bank processing fee",
        status: "pending_info", priority: "low", assignee: "Anil K.", slaDeadline: "12h",
        slaStatus: "ok", createdAt: "3h ago", resourceRef: "BRK-221", commentCount: 5,
        aiSummary: "Provider statement shows ₹450 deducted as fee. Recommend classifying as fee journal entry.",
    },
    {
        id: "CASE-1039", caseType: "risk_alert", title: "Unusual velocity — 47 payouts in 1 hour from MerchantX",
        status: "escalated", priority: "critical", assignee: "Compliance Team", slaDeadline: "BREACHED",
        slaStatus: "breached", createdAt: "5h ago", resourceRef: "RISK-882", commentCount: 8,
    },
    {
        id: "CASE-1038", caseType: "kyc_review", title: "NovaTech Solutions — PAN-Aadhaar cross-check passed",
        status: "resolved", priority: "medium", assignee: "Priya S.", slaDeadline: "—",
        slaStatus: "ok", createdAt: "1d ago", resourceRef: "KYC-4819", commentCount: 2,
        aiSummary: "All documents verified. Auto-approved by AI with 94% confidence.",
    },
];

const statusVariant: Record<CaseStatus, "success" | "warning" | "destructive" | "default" | "info"> = {
    open: "default", assigned: "default", in_progress: "warning",
    pending_info: "warning", resolved: "success", closed: "default", escalated: "destructive",
};

const priorityColor: Record<CasePriority, string> = {
    low: "text-muted-foreground", medium: "text-foreground",
    high: "text-amber-500", critical: "text-red-500 font-semibold",
};

const typeLabels: Record<string, string> = {
    kyc_review: "KYC Review", payout_failure: "Payout Failure",
    recon_break: "Recon Break", risk_alert: "Risk Alert",
    compliance: "Compliance", support: "Support",
};

export default function Cases() {
    const [filter, setFilter] = useState<string>("all");
    const [cases, setCases] = useState<Case[]>(MOCK_CASES);

    useEffect(() => {
        import("@/lib/api").then(({ casesAPI }) => {
            casesAPI.list().then(res => {
                if (res.data && Array.isArray(res.data) && res.data.length > 0) setCases(res.data as unknown as Case[]);
            }).catch(() => { });
        });
    }, []);

    const filtered = filter === "all" ? cases : cases.filter(c => c.status === filter);
    const openCount = cases.filter(c => !["resolved", "closed"].includes(c.status)).length;
    const breachedCount = cases.filter(c => c.slaStatus === "breached").length;

    return (
        <DashboardLayout title="Case Management" subtitle="Unified ops case lifecycle — KYC, payouts, recon, risk">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-5 mb-6 md:mb-8">
                <MetricCard label="Open cases" value={String(openCount)} changeType="neutral" />
                <MetricCard label="SLA breached" value={String(breachedCount)} changeType={breachedCount > 0 ? "negative" : "positive"} />
                <MetricCard label="Avg resolution" value="4.2h" change="−18% vs last week" changeType="positive" />
                <MetricCard label="AI-assisted" value="68%" change="Cases with AI summary" changeType="neutral" />
            </div>

            {/* Filters */}
            <div className="flex items-center gap-2 mb-5 flex-wrap">
                <Filter className="w-4 h-4 text-muted-foreground" />
                {["all", "open", "assigned", "in_progress", "pending_info", "escalated", "resolved"].map(s => (
                    <button
                        key={s}
                        onClick={() => setFilter(s)}
                        className={`text-[11px] px-2.5 py-1 rounded-md border transition-colors ${filter === s
                            ? "bg-primary/10 border-primary/30 text-primary font-medium"
                            : "border-border text-muted-foreground hover:text-foreground hover:bg-accent"
                            }`}
                    >
                        {s === "all" ? "All" : s.replace("_", " ")}
                    </button>
                ))}
                <div className="flex-1" />
                <Button size="sm" variant="outline" className="h-7 text-[11px] gap-1.5" onClick={() => toast.info("Create case dialog")}>
                    <Plus className="w-3 h-3" /> New case
                </Button>
            </div>

            {/* Case list */}
            <div className="space-y-3">
                {filtered.map(c => (
                    <div key={c.id} className="rounded-lg border border-border bg-card shadow-card overflow-hidden hover:border-border/80 transition-colors cursor-pointer group">
                        <div className="flex items-start gap-4 px-4 md:px-5 py-4">
                            {/* Left: icon */}
                            <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${c.priority === "critical" ? "bg-red-500/10" : c.priority === "high" ? "bg-amber-500/10" : "bg-accent"
                                }`}>
                                <FolderOpen className={`w-4 h-4 ${priorityColor[c.priority]}`} strokeWidth={1.75} />
                            </div>

                            {/* Center: details */}
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="font-mono text-[11px] text-muted-foreground">{c.id}</span>
                                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent border border-border text-muted-foreground">
                                        {typeLabels[c.caseType] || c.caseType}
                                    </span>
                                    <StatusBadge status={c.status.replace("_", " ")} variant={statusVariant[c.status]} />
                                </div>
                                <p className="text-[13px] font-medium text-foreground truncate">{c.title}</p>
                                {c.aiSummary && (
                                    <p className="text-[12px] text-muted-foreground mt-1 line-clamp-1">
                                        <span className="text-primary/70 font-medium">AI:</span> {c.aiSummary}
                                    </p>
                                )}
                                <div className="flex items-center gap-4 mt-2 text-[11px] text-muted-foreground">
                                    <span className="flex items-center gap-1"><User className="w-3 h-3" />{c.assignee}</span>
                                    <span className="flex items-center gap-1"><MessageSquare className="w-3 h-3" />{c.commentCount}</span>
                                    <span>ref:{c.resourceRef}</span>
                                    <span>{c.createdAt}</span>
                                </div>
                            </div>

                            {/* Right: SLA + arrow */}
                            <div className="flex items-center gap-3 shrink-0">
                                <div className={`text-right ${c.slaStatus === "breached" ? "text-red-500" : c.slaStatus === "warning" ? "text-amber-500" : "text-muted-foreground"}`}>
                                    <div className="flex items-center gap-1 text-[11px]">
                                        {c.slaStatus === "breached" ? <AlertTriangle className="w-3 h-3" /> : <Clock className="w-3 h-3" />}
                                        <span className="font-mono">{c.slaDeadline}</span>
                                    </div>
                                    <span className="text-[10px]">SLA</span>
                                </div>
                                <ChevronRight className="w-4 h-4 text-muted-foreground/50 group-hover:text-foreground transition-colors" />
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </DashboardLayout>
    );
}
