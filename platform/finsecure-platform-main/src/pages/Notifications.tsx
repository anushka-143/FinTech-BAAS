import { useState, useEffect } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import MetricCard from "@/components/MetricCard";
import StatusBadge from "@/components/StatusBadge";
import {
    Bell, CheckCheck, Mail, Webhook, MessageSquare, Smartphone,
    Filter, ChevronRight,
} from "lucide-react";
import { notificationsAPI } from "@/lib/api";

interface Notification {
    id: string;
    type: string;
    severity: "low" | "medium" | "high" | "critical";
    title: string;
    body: string;
    channels: string[];
    channelsDelivered: string[];
    status: "delivered" | "partially_delivered" | "failed";
    createdAt: string;
    resourceRef?: string;
    read: boolean;
}

const MOCK_NOTIFICATIONS: Notification[] = [
    {
        id: "NTF-1201", type: "risk.alert", severity: "critical",
        title: "Critical risk alert — unusual velocity detected",
        body: "MerchantX triggered 47 payouts in 1 hour, exceeding 7-day 99th percentile by 4.2x",
        channels: ["in_app", "email", "webhook", "slack"], channelsDelivered: ["in_app", "email", "webhook", "slack"],
        status: "delivered", createdAt: "12m ago", resourceRef: "RISK-882", read: false,
    },
    {
        id: "NTF-1200", type: "payout.completed", severity: "medium",
        title: "Payout PO-2026-00849 completed",
        body: "₹4,52,000 sent to HDFC account ending 1234 via NEFT",
        channels: ["in_app", "email", "webhook"], channelsDelivered: ["in_app", "email", "webhook"],
        status: "delivered", createdAt: "28m ago", resourceRef: "PO-2026-00849", read: false,
    },
    {
        id: "NTF-1199", type: "kyc.approved", severity: "medium",
        title: "KYC case KYC-4819 auto-approved",
        body: "NovaTech Solutions — all documents verified with 94% AI confidence",
        channels: ["in_app", "email"], channelsDelivered: ["in_app", "email"],
        status: "delivered", createdAt: "1h ago", resourceRef: "KYC-4819", read: true,
    },
    {
        id: "NTF-1198", type: "webhook.delivery_failed", severity: "high",
        title: "Webhook delivery failed — endpoint timeout",
        body: "Endpoint https://api.merchant.com/webhooks returned 504 after 3 retries",
        channels: ["in_app", "email", "slack"], channelsDelivered: ["in_app", "email"],
        status: "partially_delivered", createdAt: "2h ago", resourceRef: "WH-EP-003", read: true,
    },
    {
        id: "NTF-1197", type: "recon.break_found", severity: "low",
        title: "Recon break — ₹180 rounding difference",
        body: "Provider rounds to nearest rupee. Matches expected pattern for fee pass-through.",
        channels: ["in_app"], channelsDelivered: ["in_app"],
        status: "delivered", createdAt: "3h ago", resourceRef: "BRK-221", read: true,
    },
    {
        id: "NTF-1196", type: "approval.required", severity: "high",
        title: "Approval required — ₹12,50,000 payout",
        body: "Rahul M. initiated high-value payout to BlueStar Ltd. Requires maker-checker approval.",
        channels: ["in_app", "email", "slack"], channelsDelivered: ["in_app", "email", "slack"],
        status: "delivered", createdAt: "4h ago", resourceRef: "APR-0087", read: true,
    },
];

const severityColor: Record<string, string> = {
    low: "bg-muted-foreground/10 text-muted-foreground",
    medium: "bg-blue-500/10 text-blue-500",
    high: "bg-amber-500/10 text-amber-500",
    critical: "bg-red-500/10 text-red-500 font-semibold",
};

const channelIcons: Record<string, typeof Bell> = {
    in_app: Bell, email: Mail, webhook: Webhook, slack: MessageSquare, sms: Smartphone,
};

const typeLabels: Record<string, string> = {
    "risk.alert": "Risk Alert", "payout.completed": "Payout",
    "kyc.approved": "KYC", "webhook.delivery_failed": "Webhook",
    "recon.break_found": "Recon", "approval.required": "Approval",
};

export default function Notifications() {
    const [filter, setFilter] = useState<string>("all");
    const [notifications, setNotifications] = useState<Notification[]>(MOCK_NOTIFICATIONS);

    useEffect(() => {
        notificationsAPI.list().then(res => {
            if (res.data && Array.isArray(res.data) && res.data.length > 0) setNotifications(res.data as unknown as Notification[]);
        }).catch(() => { });
    }, []);

    const filtered = filter === "all"
        ? notifications
        : filter === "unread"
            ? notifications.filter(n => !n.read)
            : notifications.filter(n => n.severity === filter);

    const unreadCount = notifications.filter(n => !n.read).length;

    return (
        <DashboardLayout title="Notifications" subtitle="Multi-channel notification history and delivery tracking">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-5 mb-6 md:mb-8">
                <MetricCard label="Unread" value={String(unreadCount)} changeType={unreadCount > 5 ? "negative" : "neutral"} />
                <MetricCard label="Sent today" value="42" changeType="neutral" />
                <MetricCard label="Delivery rate" value="98.2%" change="Across all channels" changeType="positive" />
                <MetricCard label="Channels active" value="4/5" change="SMS disabled" changeType="neutral" />
            </div>

            {/* Filters */}
            <div className="flex items-center gap-2 mb-5 flex-wrap">
                <Filter className="w-4 h-4 text-muted-foreground" />
                {["all", "unread", "critical", "high", "medium", "low"].map(s => (
                    <button
                        key={s}
                        onClick={() => setFilter(s)}
                        className={`text-[11px] px-2.5 py-1 rounded-md border transition-colors ${filter === s
                            ? "bg-primary/10 border-primary/30 text-primary font-medium"
                            : "border-border text-muted-foreground hover:text-foreground hover:bg-accent"
                            }`}
                    >
                        {s === "all" ? "All" : s.charAt(0).toUpperCase() + s.slice(1)}
                        {s === "unread" && unreadCount > 0 && (
                            <span className="ml-1 px-1 py-0.5 bg-primary/20 rounded text-primary text-[9px] font-semibold">{unreadCount}</span>
                        )}
                    </button>
                ))}
            </div>

            {/* Notification list */}
            <div className="space-y-2">
                {filtered.map(n => (
                    <div
                        key={n.id}
                        className={`rounded-lg border bg-card shadow-card overflow-hidden transition-colors cursor-pointer group ${n.read ? "border-border" : "border-primary/20 bg-primary/[0.02]"
                            }`}
                    >
                        <div className="flex items-start gap-3.5 px-4 md:px-5 py-3.5">
                            {/* Unread dot */}
                            <div className="pt-1.5 shrink-0">
                                {!n.read ? (
                                    <div className="w-2 h-2 rounded-full bg-primary" />
                                ) : (
                                    <div className="w-2 h-2 rounded-full bg-transparent" />
                                )}
                            </div>

                            {/* Content */}
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-0.5">
                                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${severityColor[n.severity]}`}>
                                        {n.severity.toUpperCase()}
                                    </span>
                                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent border border-border text-muted-foreground">
                                        {typeLabels[n.type] || n.type}
                                    </span>
                                    {n.status === "partially_delivered" && (
                                        <StatusBadge status="partial" variant="warning" />
                                    )}
                                    {n.status === "failed" && (
                                        <StatusBadge status="failed" variant="destructive" />
                                    )}
                                </div>
                                <p className={`text-[13px] ${n.read ? "text-foreground" : "text-foreground font-medium"}`}>{n.title}</p>
                                <p className="text-[12px] text-muted-foreground mt-0.5 line-clamp-1">{n.body}</p>

                                <div className="flex items-center gap-3 mt-2">
                                    {/* Channels */}
                                    <div className="flex items-center gap-1.5">
                                        {n.channels.map(ch => {
                                            const Icon = channelIcons[ch] || Bell;
                                            const delivered = n.channelsDelivered.includes(ch);
                                            return (
                                                <div
                                                    key={ch}
                                                    className={`w-5 h-5 rounded flex items-center justify-center ${delivered ? "bg-emerald-500/10 text-emerald-500" : "bg-red-500/10 text-red-500"
                                                        }`}
                                                    title={`${ch}: ${delivered ? "delivered" : "failed"}`}
                                                >
                                                    <Icon className="w-3 h-3" strokeWidth={1.75} />
                                                </div>
                                            );
                                        })}
                                    </div>
                                    <span className="text-[11px] text-muted-foreground">{n.createdAt}</span>
                                    {n.resourceRef && (
                                        <span className="font-mono text-[11px] text-muted-foreground">ref:{n.resourceRef}</span>
                                    )}
                                </div>
                            </div>

                            <ChevronRight className="w-4 h-4 text-muted-foreground/50 group-hover:text-foreground transition-colors mt-1" />
                        </div>
                    </div>
                ))}
            </div>
        </DashboardLayout>
    );
}
