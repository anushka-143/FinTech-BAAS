import { useNavigate } from "react-router-dom";
import DashboardLayout from "@/components/DashboardLayout";
import MetricCard from "@/components/MetricCard";
import StatusBadge from "@/components/StatusBadge";
import { StaggerContainer, StaggerItem } from "@/components/PageTransition";
import { AttentionPanel, AttentionItem } from "@/components/AttentionPanel";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { ArrowUpRight, Download, RefreshCw } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";
import { useState, useEffect } from "react";
import { payoutsAPI } from "@/lib/api";

const MOCK_RECENT_PAYOUTS = [
  { id: "PO-2026-00847", beneficiary: "Acme Corp", amount: "₹4,52,000", rail: "IMPS", status: "SUCCESS", time: "2m ago" },
  { id: "PO-2026-00846", beneficiary: "Zenith Technologies", amount: "₹12,80,000", rail: "RTGS", status: "PENDING", time: "5m ago" },
  { id: "PO-2026-00845", beneficiary: "Nova Finance", amount: "₹89,500", rail: "UPI", status: "SUCCESS", time: "8m ago" },
  { id: "PO-2026-00844", beneficiary: "BlueStar Ltd", amount: "₹2,15,000", rail: "NEFT", status: "FAILED", time: "12m ago" },
  { id: "PO-2026-00843", beneficiary: "QuickPay Inc", amount: "₹1,45,000", rail: "UPI", status: "SUCCESS", time: "18m ago" },
];

const sv = (s: string) => {
  if (s === "SUCCESS") return "success" as const;
  if (s === "PENDING") return "warning" as const;
  if (s === "FAILED") return "destructive" as const;
  return "default" as const;
};

export default function Dashboard() {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [refreshing, setRefreshing] = useState(false);
  const [recentPayouts, setRecentPayouts] = useState(MOCK_RECENT_PAYOUTS);

  useEffect(() => {
    payoutsAPI.list({ limit: "5" }).then(res => {
      if (res.data && Array.isArray(res.data) && res.data.length > 0) setRecentPayouts(res.data as typeof MOCK_RECENT_PAYOUTS);
    }).catch(() => { });
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await new Promise(r => setTimeout(r, 800));
    setRefreshing(false);
    toast.success("Dashboard refreshed", { description: "All metrics updated." });
  };

  return (
    <DashboardLayout
      title="Dashboard"
      subtitle="Today's operational overview"
      actions={
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0 text-muted-foreground"
            onClick={handleRefresh}
            disabled={refreshing}
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
          </Button>
          {hasPermission("canExportData") && (
            <Button variant="outline" size="sm" className="h-8 text-[12px] px-3 text-muted-foreground" onClick={() => {
              toast.success("Export started", { description: "Dashboard report will be downloaded shortly." });
            }}>
              <Download className="w-3.5 h-3.5 mr-1.5" />Export
            </Button>
          )}
        </div>
      }
    >
      {/* Alert summary */}
      <div className="flex flex-wrap items-center gap-3 md:gap-4 mb-6 text-[12px]">
        <span className="flex items-center gap-1.5 text-destructive font-medium cursor-pointer hover:underline" onClick={() => navigate("/payouts")}>
          <span className="w-2 h-2 rounded-full bg-destructive animate-pulse" />2 payout failures
        </span>
        <span className="flex items-center gap-1.5 text-warning font-medium cursor-pointer hover:underline" onClick={() => navigate("/kyc")}>
          <span className="w-2 h-2 rounded-full bg-warning" />1 KYC review required
        </span>
        <span className="flex items-center gap-1.5 text-info font-medium cursor-pointer hover:underline" onClick={() => navigate("/reconciliation")}>
          <span className="w-2 h-2 rounded-full bg-info" />1 recon mismatch
        </span>
      </div>

      {/* KPI row */}
      <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-5 mb-6 md:mb-8">
        <StaggerItem><MetricCard label="Total payouts" value="₹2.4Cr" change="+18.2% vs yesterday" changeType="positive" /></StaggerItem>
        <StaggerItem><MetricCard label="Collections received" value="₹1.8Cr" change="+6.4% vs yesterday" changeType="positive" /></StaggerItem>
        <StaggerItem><MetricCard label="KYC cases open" value="37" change="12 pending OCR review" changeType="neutral" /></StaggerItem>
        <StaggerItem><MetricCard label="Recon breaks" value="4" change="2 auto-resolved today" changeType="positive" /></StaggerItem>
      </StaggerContainer>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 md:gap-6">
        {/* Main area — recent payouts */}
        <div className="lg:col-span-8">
          <div className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
            <div className="flex items-center justify-between px-4 md:px-5 py-3.5 border-b border-border">
              <span className="text-section text-foreground">Recent payouts</span>
              <Link to="/payouts">
                <Button variant="ghost" size="sm" className="h-7 text-[12px] text-muted-foreground hover:text-foreground px-2.5 gap-1">
                  View all <ArrowUpRight className="w-3.5 h-3.5" />
                </Button>
              </Link>
            </div>
            {/* Mobile card view */}
            <div className="md:hidden divide-y divide-border/50">
              {recentPayouts.map((p) => (
                <div
                  key={p.id}
                  className="px-4 py-3 hover:bg-accent/30 transition-colors cursor-pointer active:bg-accent/50"
                  onClick={() => navigate(`/payouts/${p.id}`)}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[13px] text-foreground font-medium">{p.beneficiary}</span>
                    <span className="font-mono text-[13px] text-foreground tabular">{p.amount}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <StatusBadge status={p.status} variant={sv(p.status)} />
                      <span className="font-mono text-[11px] text-muted-foreground">{p.rail}</span>
                    </div>
                    <span className="text-[11px] text-muted-foreground">{p.time}</span>
                  </div>
                </div>
              ))}
            </div>
            {/* Desktop table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-table-head text-muted-foreground uppercase border-b border-border bg-accent/30">
                    <th className="text-left px-5 py-2.5 font-medium">Beneficiary</th>
                    <th className="text-right px-5 py-2.5 font-medium">Amount</th>
                    <th className="text-center px-5 py-2.5 font-medium">Rail</th>
                    <th className="text-left px-5 py-2.5 font-medium">Status</th>
                    <th className="text-right px-5 py-2.5 font-medium">Time</th>
                    <th className="text-left px-5 py-2.5 font-medium">ID</th>
                  </tr>
                </thead>
                <tbody>
                  {recentPayouts.map((p) => (
                    <tr
                      key={p.id}
                      className="border-b border-border/50 hover:bg-accent/30 transition-colors cursor-pointer"
                      onClick={() => navigate(`/payouts/${p.id}`)}
                    >
                      <td className="px-5 py-3.5 text-[13px] text-foreground font-medium">{p.beneficiary}</td>
                      <td className="px-5 py-3.5 text-right font-mono text-[13px] text-foreground tabular">{p.amount}</td>
                      <td className="px-5 py-3.5 text-center font-mono text-[11px] text-muted-foreground">{p.rail}</td>
                      <td className="px-5 py-3.5"><StatusBadge status={p.status} variant={sv(p.status)} /></td>
                      <td className="px-5 py-3.5 text-right text-[12px] text-muted-foreground">{p.time}</td>
                      <td className="px-5 py-3.5 font-mono text-[11px] text-muted-foreground">{p.id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right rail */}
        <div className="lg:col-span-4 space-y-4 md:space-y-6">
          <AttentionPanel title="Needs attention">
            <AttentionItem
              severity="critical"
              id="RSK-1203"
              title="OFAC sanctions match — Sunita Verma"
              meta="78% confidence · 31m ago"
              action="Review"
              onAction={() => navigate("/kyc/KYC-4816")}
            />
            <AttentionItem
              severity="warning"
              id="PO-2026-00844"
              title="NEFT payout failed — BlueStar Ltd"
              meta="BENE_INACTIVE · retryable"
              action="Retry"
              onAction={() => navigate("/payouts/PO-2026-00844")}
            />
            <AttentionItem
              severity="warning"
              id="BRK-221"
              title="Recon break — ₹450 mismatch"
              meta="AI triaged · fee deduction"
              action="Resolve"
              onAction={() => navigate("/reconciliation/BRK-221")}
            />
            <AttentionItem
              severity="info"
              id="KYC-4821"
              title="KYB review pending — Meridian Finserv"
              meta="87% OCR confidence"
              action="Open case"
              onAction={() => navigate("/kyc/KYC-4821")}
            />
          </AttentionPanel>

          {/* System status */}
          <div className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
            <div className="px-4 py-3 border-b border-border">
              <span className="text-section text-foreground">System status</span>
            </div>
            <div className="px-4 py-1">
              {[
                { label: "API Gateway", ok: true },
                { label: "Payout Engine", ok: true },
                { label: "OCR Pipeline", ok: false },
                { label: "Ledger Service", ok: true },
                { label: "Event Bus", ok: true },
              ].map((s) => (
                <div key={s.label} className="flex items-center justify-between py-2.5 border-b border-border/40 last:border-0">
                  <span className="text-[13px] text-foreground">{s.label}</span>
                  <span className={`flex items-center gap-1.5 text-[11px] font-medium ${s.ok ? "text-success" : "text-warning"}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${s.ok ? "bg-success" : "bg-warning animate-pulse"}`} />
                    {s.ok ? "Operational" : "Degraded"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
