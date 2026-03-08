import { useState } from "react";
import { Bell, Check, AlertTriangle, Info, CreditCard, Users, FileSearch, Webhook } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";

interface Notification {
  id: string;
  type: "critical" | "warning" | "info" | "success";
  icon: typeof Bell;
  title: string;
  description: string;
  time: string;
  read: boolean;
}

const initialNotifications: Notification[] = [
  { id: "n1", type: "critical", icon: CreditCard, title: "Payout failed — BlueStar Ltd", description: "NEFT PO-2026-00844 · BENE_INACTIVE · retryable", time: "12m ago", read: false },
  { id: "n2", type: "warning", icon: Users, title: "KYC case requires review", description: "KYC-4821 Meridian Finserv · 87% confidence", time: "31m ago", read: false },
  { id: "n3", type: "critical", icon: AlertTriangle, title: "OFAC sanctions match", description: "RSK-1203 Sunita Verma · 78% confidence", time: "35m ago", read: false },
  { id: "n4", type: "info", icon: FileSearch, title: "Recon break auto-resolved", description: "BRK-219 duplicate callback deduplicated", time: "1h ago", read: true },
  { id: "n5", type: "success", icon: CreditCard, title: "Payout batch completed", description: "142 payouts settled · ₹2.4Cr volume", time: "2h ago", read: true },
  { id: "n6", type: "warning", icon: Webhook, title: "Webhook delivery failed", description: "payout.completed · 3 retries exhausted", time: "3h ago", read: true },
  { id: "n7", type: "info", icon: Info, title: "OCR pipeline recovered", description: "PP-StructureV3 back to operational", time: "4h ago", read: true },
];

const typeColors = {
  critical: "text-destructive bg-destructive/10",
  warning: "text-warning bg-warning/10",
  info: "text-info bg-info/10",
  success: "text-success bg-success/10",
};

export default function NotificationCenter() {
  const [notifications, setNotifications] = useState(initialNotifications);
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const unreadCount = notifications.filter(n => !n.read).length;
  const filtered = filter === "unread" ? notifications.filter(n => !n.read) : notifications;

  const markAllRead = () => setNotifications(ns => ns.map(n => ({ ...n, read: true })));
  const markRead = (id: string) => setNotifications(ns => ns.map(n => n.id === id ? { ...n, read: true } : n));

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button className="relative w-8 h-8 flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
          <Bell className="w-4 h-4" strokeWidth={1.75} />
          {unreadCount > 0 && (
            <span className="absolute top-1 right-1 w-[18px] h-[18px] rounded-full bg-destructive text-destructive-foreground text-[10px] font-semibold flex items-center justify-center leading-none">
              {unreadCount}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-[400px] p-0" align="end" sideOffset={8}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <span className="text-[14px] font-semibold text-foreground">Notifications</span>
          <div className="flex items-center gap-2">
            <div className="flex items-center h-7 rounded-md border border-border bg-accent/50 overflow-hidden text-[11px] font-medium">
              <button onClick={() => setFilter("all")} className={`px-2.5 h-full transition-colors ${filter === "all" ? "bg-foreground text-card" : "text-muted-foreground"}`}>All</button>
              <button onClick={() => setFilter("unread")} className={`px-2.5 h-full transition-colors ${filter === "unread" ? "bg-foreground text-card" : "text-muted-foreground"}`}>Unread</button>
            </div>
            {unreadCount > 0 && (
              <Button variant="ghost" size="sm" className="h-7 text-[11px] px-2 text-muted-foreground" onClick={markAllRead}>
                <Check className="w-3 h-3 mr-1" />Mark all read
              </Button>
            )}
          </div>
        </div>
        <div className="max-h-[420px] overflow-y-auto">
          {filtered.length === 0 ? (
            <div className="py-12 text-center text-[13px] text-muted-foreground">No notifications</div>
          ) : (
            filtered.map(n => (
              <div
                key={n.id}
                onClick={() => markRead(n.id)}
                className={`flex gap-3 px-4 py-3.5 border-b border-border/50 hover:bg-accent/30 cursor-pointer transition-colors ${!n.read ? "bg-accent/20" : ""}`}
              >
                <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${typeColors[n.type]}`}>
                  <n.icon className="w-3.5 h-3.5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className={`text-[13px] leading-tight ${!n.read ? "font-medium text-foreground" : "text-foreground/80"}`}>{n.title}</p>
                    {!n.read && <span className="w-2 h-2 rounded-full bg-primary shrink-0 mt-1.5" />}
                  </div>
                  <p className="text-[12px] text-muted-foreground mt-0.5 truncate">{n.description}</p>
                  <p className="text-[11px] text-muted-foreground/60 mt-1">{n.time}</p>
                </div>
              </div>
            ))
          )}
        </div>
        <div className="px-4 py-2.5 border-t border-border">
          <Button variant="ghost" size="sm" className="w-full h-8 text-[12px] text-muted-foreground">View all notifications</Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
