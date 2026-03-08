import { useParams } from "react-router-dom";
import DashboardLayout from "@/components/DashboardLayout";
import Breadcrumbs from "@/components/Breadcrumbs";
import AuditTimeline from "@/components/AuditTimeline";
import StatusBadge from "@/components/StatusBadge";
import { SmartRoutingPanel, NameMatchPanel } from "@/components/AIFeaturePanels";
import StepUpAuthDialog from "@/components/StepUpAuthDialog";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { useState } from "react";
import { toast } from "sonner";
import {
  RotateCcw, Copy, Download,
  Hash, CreditCard, Shield,
} from "lucide-react";

const payoutData: Record<string, any> = {
  "PO-2026-00847": {
    id: "PO-2026-00847", beneficiary: "Acme Corp", account: "HDFC ****4821", ifsc: "HDFC0001234",
    amount: "₹4,52,000", rail: "IMPS", status: "SUCCESS", initiated: "Mar 7, 2026 14:02:18",
    settled: "Mar 7, 2026 14:02:22", settlementTime: "4s", utr: "HDFC262660024821",
    tenant: "Acme Financial Services", createdBy: "System · API", purpose: "vendor_payment",
    narration: "Invoice INV-2026-0471", fee: "₹5.90", gst: "₹1.06", netDebit: "₹4,52,006.96",
  },
  "PO-2026-00844": {
    id: "PO-2026-00844", beneficiary: "BlueStar Ltd", account: "Axis ****3301", ifsc: "UTIB0002187",
    amount: "₹2,15,000", rail: "NEFT", status: "FAILED_RETRYABLE", initiated: "Mar 7, 2026 13:50:04",
    settled: "—", settlementTime: "—", utr: "—", failureReason: "BENE_INACTIVE",
    tenant: "Acme Financial Services", createdBy: "Arjun Kapoor", purpose: "salary",
    narration: "March salary — ID 4401", fee: "₹0", gst: "₹0", netDebit: "₹0",
  },
};

const timelineEvents = [
  { id: "t1", time: "14:02:22", title: "Payout settled", description: "UTR HDFC262660024821 confirmed by bank.", type: "system" as const },
  { id: "t2", time: "14:02:19", title: "Bank acknowledgement received", description: "IMPS accepted by HDFC.", type: "system" as const },
  { id: "t3", time: "14:02:18", title: "Payout submitted to rail", description: "IMPS via provider: RazorpayX", type: "system" as const },
  { id: "t4", time: "14:02:17", title: "Balance validated", description: "Sufficient balance in settlement account.", type: "system" as const },
  { id: "t5", time: "14:02:16", title: "Risk check passed", description: "No AML flags. Velocity check OK.", type: "ai" as const },
  { id: "t6", time: "14:02:15", title: "Payout created", description: "Created via API POST /v1/payouts", actor: "System · API", type: "user" as const },
];

const failedTimeline = [
  { id: "t1", time: "13:50:12", title: "Payout failed", description: "Reason: BENE_INACTIVE — Beneficiary account is inactive or closed.", type: "system" as const },
  { id: "t2", time: "13:50:08", title: "Bank rejection received", description: "NEFT rejected by Axis Bank.", type: "system" as const },
  { id: "t3", time: "13:50:04", title: "Payout submitted to rail", description: "NEFT via provider: YesBank", type: "system" as const },
  { id: "t4", time: "13:50:03", title: "Balance validated", type: "system" as const },
  { id: "t5", time: "13:50:02", title: "Risk check passed", type: "ai" as const },
  { id: "t6", time: "13:50:01", title: "Payout created", actor: "Arjun Kapoor", type: "user" as const },
];

export default function PayoutDetail() {
  const { id } = useParams<{ id: string }>();
  const { hasPermission } = useAuth();
  const [retryDialog, setRetryDialog] = useState(false);
  const payout = payoutData[id || ""] || payoutData["PO-2026-00847"];
  const isFailed = payout.status.includes("FAILED");
  const [copied, setCopied] = useState<string | null>(null);

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    toast.success("Copied", { description: `${label} copied to clipboard` });
    setTimeout(() => setCopied(null), 1500);
  };

  const sv = (s: string) => {
    if (s === "SUCCESS") return "success" as const;
    if (s === "PENDING") return "warning" as const;
    if (s.includes("FAILED")) return "destructive" as const;
    if (s === "REVERSED") return "info" as const;
    return "default" as const;
  };

  return (
    <DashboardLayout title="Payout detail" subtitle={payout.id}>
      <Breadcrumbs items={[
        { label: "Payouts", path: "/payouts" },
        { label: payout.id },
      ]} />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between mb-6 gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-3 mb-2">
            <h2 className="text-kpi text-foreground tabular">{payout.amount}</h2>
            <StatusBadge status={payout.status} variant={sv(payout.status)} />
          </div>
          <p className="text-[14px] text-muted-foreground">
            {payout.beneficiary} · {payout.rail} · {payout.narration}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {isFailed && hasPermission("canRetryPayouts") && (
            <Button size="sm" className="h-8 text-[12px] gap-1.5" onClick={() => setRetryDialog(true)}>
              <RotateCcw className="w-3.5 h-3.5" />Retry payout
            </Button>
          )}
          <Button variant="outline" size="sm" className="h-8 text-[12px] gap-1.5" onClick={() => toast.info("Receipt download started")}>
            <Download className="w-3.5 h-3.5" />Receipt
          </Button>
        </div>
      </div>

      {/* Failed reason banner */}
      {isFailed && (
        <div className="mb-6 px-4 py-3.5 rounded-lg bg-destructive/6 border border-destructive/15">
          <div className="flex items-start gap-3">
            <Shield className="w-4 h-4 text-destructive mt-0.5 shrink-0" />
            <div>
              <p className="text-[13px] font-medium text-destructive">Failure reason: {payout.failureReason}</p>
              <p className="text-[12px] text-destructive/70 mt-0.5">
                The beneficiary account is inactive or closed. Verify account details before retrying.
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 md:gap-6">
        {/* Left — metadata */}
        <div className="lg:col-span-5 space-y-4 md:space-y-6">
          {/* AI Panels */}
          <SmartRoutingPanel />
          <NameMatchPanel />

          <div className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
            <div className="px-4 md:px-5 py-3.5 border-b border-border">
              <span className="text-section text-foreground">Transaction details</span>
            </div>
            <div className="px-4 md:px-5 py-1">
              {[
                { icon: Hash, label: "Payout ID", value: payout.id, copyable: true },
                { icon: CreditCard, label: "Amount", value: payout.amount },
                { icon: null, label: "Rail", value: payout.rail },
                { icon: null, label: "Purpose", value: payout.purpose },
                { icon: null, label: "Narration", value: payout.narration },
                { icon: null, label: "Fee", value: payout.fee },
                { icon: null, label: "GST", value: payout.gst },
                { icon: null, label: "Net debit", value: payout.netDebit },
                ...(payout.utr !== "—" ? [{ icon: null, label: "UTR", value: payout.utr, copyable: true }] : []),
              ].map((item, i) => (
                <div key={i} className="flex items-center justify-between py-3 border-b border-border/40 last:border-0 gap-2">
                  <span className="text-[12px] text-muted-foreground shrink-0">{item.label}</span>
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-[12px] text-foreground">{item.value}</span>
                    {item.copyable && (
                      <button
                        onClick={() => copyToClipboard(item.value, item.label)}
                        className="text-muted-foreground hover:text-foreground transition-colors"
                        title="Copy"
                      >
                        <Copy className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
            <div className="px-4 md:px-5 py-3.5 border-b border-border">
              <span className="text-section text-foreground">Beneficiary</span>
            </div>
            <div className="px-4 md:px-5 py-1">
              {[
                { label: "Name", value: payout.beneficiary },
                { label: "Account", value: payout.account },
                { label: "IFSC", value: payout.ifsc },
              ].map((item, i) => (
                <div key={i} className="flex items-center justify-between py-3 border-b border-border/40 last:border-0">
                  <span className="text-[12px] text-muted-foreground">{item.label}</span>
                  <span className="font-mono text-[12px] text-foreground">{item.value}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
            <div className="px-4 md:px-5 py-3.5 border-b border-border">
              <span className="text-section text-foreground">Metadata</span>
            </div>
            <div className="px-4 md:px-5 py-1">
              {[
                { label: "Initiated", value: payout.initiated },
                { label: "Settled", value: payout.settled },
                { label: "Settlement time", value: payout.settlementTime },
                { label: "Tenant", value: payout.tenant },
                { label: "Created by", value: payout.createdBy },
              ].map((item, i) => (
                <div key={i} className="flex items-center justify-between py-3 border-b border-border/40 last:border-0">
                  <span className="text-[12px] text-muted-foreground">{item.label}</span>
                  <span className="text-[12px] text-foreground">{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right — timeline */}
        <div className="lg:col-span-7">
          <AuditTimeline
            events={isFailed ? failedTimeline : timelineEvents}
            title="Audit trail"
          />
        </div>
      </div>

      <StepUpAuthDialog
        open={retryDialog}
        onClose={() => setRetryDialog(false)}
        onConfirm={() => {
          setRetryDialog(false);
          toast.success("Payout retry queued", { description: `${payout.amount} to ${payout.beneficiary} will be retried via ${payout.rail}.` });
        }}
        title="Confirm payout retry"
        description={`Retry ${payout.amount} to ${payout.beneficiary} via ${payout.rail}. Enter your authenticator code to proceed.`}
      />
    </DashboardLayout>
  );
}
