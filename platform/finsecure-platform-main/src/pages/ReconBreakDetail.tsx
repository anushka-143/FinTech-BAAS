import { useParams, useNavigate } from "react-router-dom";
import DashboardLayout from "@/components/DashboardLayout";
import Breadcrumbs from "@/components/Breadcrumbs";
import AuditTimeline from "@/components/AuditTimeline";
import StatusBadge from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ActionDialogs";
import { useAuth } from "@/contexts/AuthContext";
import { Cpu, CheckCircle2, ArrowRight, AlertCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

const breakData: Record<string, any> = {
  "BRK-221": {
    id: "BRK-221", type: "AMOUNT_MISMATCH", status: "AI_TRIAGED",
    internal: { ref: "PO-2026-00847", amount: "₹4,52,000", rail: "IMPS", beneficiary: "Acme Corp" },
    provider: { ref: "HDFC262660024821", amount: "₹4,51,550", statement: "HDFC Bank Statement" },
    diff: "₹450", diffPct: "0.10%",
    reconRun: "REC-0047", reconTime: "Mar 7, 2026 14:00",
    aiSummary: "Amount mismatch of ₹450 (0.10%) between internal record (₹4,52,000) and provider statement (₹4,51,550). Analysis: This appears to be a fee deduction by the provider. Recommendation: Auto-classify as fee journal entry and close break.",
    aiRecommendation: "auto_resolve_fee",
    aiConfidence: 94,
  },
  "BRK-220": {
    id: "BRK-220", type: "MISSING_PROVIDER", status: "OPEN",
    internal: { ref: "PO-2026-00841", amount: "₹3,80,000", rail: "IMPS", beneficiary: "TechNova AI" },
    provider: { ref: "—", amount: "—", statement: "—" },
    diff: "₹3,80,000", diffPct: "100%",
    reconRun: "REC-0045", reconTime: "Mar 7, 2026 12:00",
    aiSummary: "Internal payout PO-2026-00841 has no corresponding provider record. This is likely a reversal that has not yet been reflected in the provider statement. Recommend waiting 24 hours for settlement.",
    aiRecommendation: "wait_24h",
    aiConfidence: 82,
  },
};

const breakTimeline = [
  { id: "t1", time: "14:05", title: "AI triage completed", description: "Classified as provider fee deduction. 94% confidence.", type: "ai" as const },
  { id: "t2", time: "14:02", title: "Break identified", description: "Amount mismatch ₹450 between internal and provider.", type: "system" as const },
  { id: "t3", time: "14:00", title: "Reconciliation run completed", description: "REC-0047 · 142 matched, 2 breaks.", type: "system" as const },
];

export default function ReconBreakDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const brk = breakData[id || ""] || breakData["BRK-221"];
  const [resolveOpen, setResolveOpen] = useState(false);
  const [escalateOpen, setEscalateOpen] = useState(false);

  return (
    <DashboardLayout title="Recon break" subtitle={brk.id}>
      <Breadcrumbs items={[
        { label: "Reconciliation", path: "/reconciliation" },
        { label: brk.id },
      ]} />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between mb-6 gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-3 mb-2">
            <h2 className="text-[20px] md:text-[24px] font-semibold text-foreground tracking-[-0.02em]">Break: {brk.type.replace("_", " ")}</h2>
            <StatusBadge status={brk.status} variant={brk.status === "AI_TRIAGED" ? "info" : "warning"} />
          </div>
          <p className="text-[13px] text-muted-foreground">
            Difference: <span className="font-mono font-medium text-destructive">{brk.diff}</span> ({brk.diffPct})
            {" · "}Run {brk.reconRun} · {brk.reconTime}
          </p>
        </div>
        {hasPermission("canResolveRecon") && (
          <div className="flex items-center gap-2 shrink-0">
            <Button variant="outline" size="sm" className="h-8 text-[12px] gap-1.5" onClick={() => setEscalateOpen(true)}>
              <AlertCircle className="w-3.5 h-3.5" />Escalate
            </Button>
            <Button size="sm" className="h-8 text-[12px] gap-1.5" onClick={() => setResolveOpen(true)}>
              <CheckCircle2 className="w-3.5 h-3.5" />Resolve break
            </Button>
          </div>
        )}
      </div>

      {/* AI suggestion */}
      <div className="mb-6 rounded-lg border border-info/20 bg-info/4 overflow-hidden">
        <div className="flex items-center gap-2 px-4 md:px-5 py-3 border-b border-info/10">
          <Cpu className="w-4 h-4 text-info" />
          <span className="text-[13px] font-medium text-info">AI triage</span>
          <span className="font-mono text-[11px] text-info/60 ml-auto">{brk.aiConfidence}% confidence · inference</span>
        </div>
        <div className="px-4 md:px-5 py-4">
          <p className="text-[13px] text-foreground leading-relaxed">{brk.aiSummary}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 md:gap-6">
        <div className="lg:col-span-5 space-y-4 md:space-y-6">
          {/* Comparison */}
          <div className="rounded-lg border border-border bg-card shadow-card overflow-hidden">
            <div className="px-4 md:px-5 py-3.5 border-b border-border">
              <span className="text-section text-foreground">Comparison</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 sm:divide-x divide-border">
              <div className="p-4 md:p-5">
                <p className="text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-medium mb-3">Internal</p>
                {[
                  { label: "Reference", value: brk.internal.ref },
                  { label: "Amount", value: brk.internal.amount },
                  { label: "Rail", value: brk.internal.rail },
                  { label: "Beneficiary", value: brk.internal.beneficiary },
                ].map((item, i) => (
                  <div key={i} className="flex justify-between py-2">
                    <span className="text-[11px] text-muted-foreground">{item.label}</span>
                    <span className="font-mono text-[11px] text-foreground">{item.value}</span>
                  </div>
                ))}
              </div>
              <div className="p-4 md:p-5 border-t sm:border-t-0 border-border">
                <p className="text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-medium mb-3">Provider</p>
                {[
                  { label: "Reference", value: brk.provider.ref },
                  { label: "Amount", value: brk.provider.amount },
                  { label: "Source", value: brk.provider.statement },
                ].map((item, i) => (
                  <div key={i} className="flex justify-between py-2">
                    <span className="text-[11px] text-muted-foreground">{item.label}</span>
                    <span className="font-mono text-[11px] text-foreground">{item.value}</span>
                  </div>
                ))}
                <div className="flex justify-between py-2 mt-2 pt-2 border-t border-border/50">
                  <span className="text-[11px] font-medium text-destructive">Difference</span>
                  <span className="font-mono text-[11px] font-medium text-destructive">{brk.diff}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="lg:col-span-7">
          <AuditTimeline events={breakTimeline} title="Break timeline" />
        </div>
      </div>

      <ConfirmDialog
        open={resolveOpen}
        onClose={() => setResolveOpen(false)}
        onConfirm={() => {
          toast.success("Break resolved", { description: `${brk.id} marked as resolved. Fee journal entry created.` });
          setTimeout(() => navigate("/reconciliation"), 1000);
        }}
        title="Resolve break"
        description={`Resolve ${brk.id} (${brk.type.replace("_", " ")})? The AI recommendation is: ${brk.aiRecommendation.replace(/_/g, " ")}. A corresponding journal entry will be created.`}
        confirmLabel="Resolve"
      />
      <ConfirmDialog
        open={escalateOpen}
        onClose={() => setEscalateOpen(false)}
        onConfirm={() => {
          toast.success("Break escalated", { description: `${brk.id} has been escalated to the finance team for manual review.` });
        }}
        title="Escalate break"
        description={`Escalate ${brk.id} to the finance team? The break will be flagged for manual investigation.`}
        confirmLabel="Escalate"
      />
    </DashboardLayout>
  );
}
